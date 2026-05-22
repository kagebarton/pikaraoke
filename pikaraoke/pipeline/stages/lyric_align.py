"""Lyric alignment/transcription stage: generate ASS (and SRT) from vocal stem.

Two modes:
- Alignment (lyrics_path provided): aligns the given .txt or .srt lyrics to
  the vocal stem via stable-ts model.align(), then refines timestamps. A
  two-pointer walk matcher pairs lyric tokens to whisper words with gap
  interpolation for unmatched references — every lyric token ends up in
  the karaoke output, gap-free. In "auto" mode the stage routes on
  concentrated walk failures alone (see ``_decide_route``): a clean song
  keeps walk; a concentrated missing section in an otherwise-healthy song
  is *repaired* in place (walk everywhere, the order-independent tiling
  matcher only over the failed span's audio window); a song broken nearly
  everywhere falls back to whole-song tiling.
- Transcription (no lyrics_path): runs model.transcribe() directly; stable-ts
  determines segment/word boundaries from the audio alone.

In both modes the same ASS and SRT generators are used. The difference is
how line objects are built: alignment pairs words to predefined lyric lines
via the walk matcher; transcription uses stable-ts segments directly as lines.

Each model call is wrapped in its own cancellation activity scope.
Alignment splits Phase.ALIGN_CHECK (align only — its pre-refine words feed
a quick walk whose loss_spans drive routing) from Phase.REFINE (refine the
cached align result), so a whole-song-tiling route can discard the align
output before paying refine. The repair route additionally runs
Phase.TRANSCRIBE after refine to tile the failed spans. Transcription mode
stays a single Phase.TRANSCRIBE call.

ASS/SRT are written to ctx.tmp_dir first and moved to the final output
directory only after both writes succeed — preventing orphan files on
cancellation.
"""

import dataclasses
import datetime
import logging
import shutil
from pathlib import Path

import srt

from pikaraoke.lib import alignment_capture
from pikaraoke.lib.genius_lyrics import parse_lyric_lines
from pikaraoke.lib.tiling_match import match_words_to_lines_tiling_with_stats
from pikaraoke.lib.word_alignment import match_words_to_lines_with_stats
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.context import Phase, PipelineCancelled, SetEvent, StageContext
from pikaraoke.pipeline.stages.base import BaseStage
from pikaraoke.pipeline.workers.whisper_worker import (
    AlignmentCancelledError,
    WhisperWorker,
)

logger = logging.getLogger(__name__)


class LyricAlignStage(BaseStage):
    """Align lyrics to vocal stem and generate karaoke ASS + optional SRT."""

    name = "lyric_align"

    def __init__(self, whisper_worker: WhisperWorker, config: PipelineConfig) -> None:
        self._worker = whisper_worker
        self._config = config

    def run(self, ctx: StageContext) -> None:
        lyrics_path = ctx.artifacts.get("lyrics_path")
        vocal_wav = ctx.artifacts.get("vocal_wav")

        if vocal_wav is None:
            raise RuntimeError(f"[{self.name}] No vocal_wav in artifacts")

        # Debug-capture scratchpad: populated as the stage progresses,
        # written at the end only on the alignment-mode happy paths.
        capture_words: list | None = None
        capture_words_source: str | None = None
        capture_walk_stats: dict | None = None
        capture_tiling_stats: dict | None = None
        capture_fail_ratio: float | None = None
        capture_collapse_ratio: float | None = None
        capture_max_loss_run: int | None = None
        capture_escalated = False
        capture_escalation_trigger: str | None = None
        capture_method_used: str | None = None
        capture_repair_ranges: list | None = None

        if lyrics_path is not None:
            # --- Alignment mode ---
            lyrics_lines, align_lines = self._load_lyrics(lyrics_path)
            lyrics_text = "\n".join(align_lines)

            logger.info(f"[{self.name}] Aligning lyrics to vocal stem: {Path(vocal_wav).name}")

            method = self._config.match_method

            if method == "tiling":
                # Forced whole-song tiling: skip align entirely.
                route = "whole_tiling"
                result_id = None
            else:
                # walk / auto: run align() first so we can route on a quick
                # pre-refine walk *before* paying for refine. align_check
                # returns the pre-refine word list; refine only nudges
                # timestamps, so the quick walk's loss_spans honestly locate
                # a concentrated failure (the failure mode where stable-ts
                # force-places a long run of tokens at one timestamp —
                # segment-level success, word-level garbage).
                check = _model_call(
                    ctx,
                    Phase.ALIGN_CHECK,
                    lambda: self._worker.align_check(
                        vocal_path=vocal_wav,
                        lyrics_text=lyrics_text,
                        cancel_event=ctx.cancel.event if ctx.cancel else None,
                    ),
                )
                result_id = check["result_id"]
                capture_fail_ratio = check["fail_ratio"]
                raw_words = check["words"]

                _, raw_stats = match_words_to_lines_with_stats(raw_words, lyrics_lines, align_lines)
                # fail_ratio / collapse_ratio no longer gate routing — kept
                # as telemetry so a kept-walk song that should have escalated
                # can be spotted retroactively. Routing is concentration-only.
                n_raw_tokens = raw_stats["n_tokens"]
                capture_collapse_ratio = (
                    sum(raw_stats["collapsed_run_lengths"]) / n_raw_tokens if n_raw_tokens else 0.0
                )
                capture_max_loss_run = max(
                    raw_stats["collapsed_run_lengths"] + raw_stats["dropped_run_lengths"],
                    default=0,
                )

                if method == "walk":
                    route = "keep_walk"
                else:  # auto — route on concentrated missing sections alone
                    route, routing_ranges = _decide_route(
                        raw_stats["loss_spans"],
                        len(lyrics_lines),
                        self._config.concentration_escalation_run,
                        self._config.repair_max_line_fraction,
                    )
                    logger.info(
                        "[%s] route=%s (fail_ratio=%.0f%%, collapse_ratio=%.0f%%, "
                        "max_loss_run=%d, concentration_run=%d, repair_ranges=%d)",
                        self.name,
                        route,
                        capture_fail_ratio * 100,
                        capture_collapse_ratio * 100,
                        capture_max_loss_run,
                        self._config.concentration_escalation_run,
                        len(routing_ranges),
                    )

            if route == "whole_tiling":
                if result_id is not None:
                    # Came from auto coverage cap (broken nearly everywhere):
                    # discard the align result so we don't pay refine on it.
                    self._discard_cached_safely(result_id, "escalation")
                    capture_escalated = True
                    capture_escalation_trigger = "coverage_cap"
                logger.info(f"[{self.name}] Transcribing for tiling match: {Path(vocal_wav).name}")
                words = _model_call(
                    ctx,
                    Phase.TRANSCRIBE,
                    lambda: self._worker.transcribe_words(
                        vocal_path=vocal_wav,
                        cancel_event=ctx.cancel.event if ctx.cancel else None,
                    ),
                )
                line_objects, capture_tiling_stats = match_words_to_lines_tiling_with_stats(
                    words, lyrics_lines, align_lines
                )
                capture_words = words
                capture_words_source = "transcribe"
                capture_method_used = "tiling"
            else:
                # keep_walk and repair both refine + walk; repair then tiles
                # the failed spans on top.
                words = _model_call(
                    ctx,
                    Phase.REFINE,
                    lambda: self._worker.refine_from_cached(
                        result_id=result_id,
                        vocal_path=vocal_wav,
                        cancel_event=ctx.cancel.event if ctx.cancel else None,
                    ),
                )
                line_objects, capture_walk_stats = match_words_to_lines_with_stats(
                    words, lyrics_lines, align_lines
                )
                capture_words = words
                capture_words_source = "refine"
                capture_method_used = "walk"

                if route == "repair":
                    # Recompute ranges from post-refine timing — windows
                    # depend on it, so the pre-refine routing estimate is
                    # not reused here.
                    repair_ranges = _build_repair_ranges(
                        capture_walk_stats["loss_spans"],
                        self._config.concentration_escalation_run,
                    )
                    if repair_ranges:
                        logger.info(
                            f"[{self.name}] Transcribing to repair {len(repair_ranges)} "
                            f"span(s): {Path(vocal_wav).name}"
                        )
                        transcribe_words = _model_call(
                            ctx,
                            Phase.TRANSCRIBE,
                            lambda: self._worker.transcribe_words(
                                vocal_path=vocal_wav,
                                cancel_event=ctx.cancel.event if ctx.cancel else None,
                            ),
                        )
                        line_objects, capture_repair_ranges = self._repair_spans(
                            line_objects,
                            repair_ranges,
                            transcribe_words,
                            lyrics_lines,
                            align_lines,
                        )
                        capture_method_used = "walk+repair"
                        capture_escalation_trigger = "concentration"
                    else:
                        # Refine dissolved the pre-refine concentration —
                        # pure walk, no transcribe paid.
                        logger.info(
                            f"[{self.name}] repair route: no post-refine ranges, keeping walk"
                        )

            write_srt = self._should_write_srt(ctx.song_path)
        else:
            # --- Transcription mode ---
            logger.info(f"[{self.name}] Transcribing vocal stem: {Path(vocal_wav).name}")
            line_objects = _model_call(
                ctx,
                Phase.TRANSCRIBE,
                lambda: self._worker.transcribe_refine(
                    vocal_path=vocal_wav,
                    cancel_event=ctx.cancel.event if ctx.cancel else None,
                ),
            )
            write_srt = self._should_write_srt(ctx.song_path)
            capture_method_used = "transcribe"

        # Surface the lyric source + matcher combination on the context so
        # the processing-page row can render it (e.g. "genius+tiling" flags
        # the worst-case combo at a glance). Independent of the debug
        # capture flag below — the UI label must work even with capture off.
        lyrics_origin = ctx.artifacts.get("lyrics_origin", "none")
        if lyrics_path is None:
            ctx.artifacts["lyric_method"] = "transcribe"
        else:
            ctx.artifacts["lyric_method"] = f"{lyrics_origin}+{capture_method_used}"

        ass_content = self._generate_ass(line_objects)
        srt_content = self._generate_srt(line_objects) if write_srt else None

        # Write to tmp_dir first, then move to final destinations — prevents
        # orphan files on cancellation (tmp_dir is cleaned by orchestrator).
        tmp_ass = ctx.tmp_dir / f"{ctx.song_path.stem}.ass"
        tmp_ass.write_text(ass_content, encoding="utf-8")

        tmp_srt = None
        if write_srt:
            tmp_srt = ctx.tmp_dir / f"{ctx.song_path.stem}.srt"
            tmp_srt.write_text(srt_content, encoding="utf-8")

        # Promote to final locations
        karaoke_dir = ctx.song_path.parent / "karaoke"
        karaoke_dir.mkdir(exist_ok=True)
        final_ass = karaoke_dir / tmp_ass.name
        shutil.move(str(tmp_ass), str(final_ass))
        ctx.artifacts["ass_file"] = final_ass
        logger.info(f"[{self.name}] ASS written: {final_ass}")

        if write_srt and tmp_srt is not None:
            subtitles_dir = ctx.song_path.parent / "subtitles"
            subtitles_dir.mkdir(exist_ok=True)
            final_srt = subtitles_dir / tmp_srt.name
            shutil.move(str(tmp_srt), str(final_srt))
            ctx.artifacts["srt_file"] = final_srt
            logger.info(f"[{self.name}] SRT written: {final_srt}")

        if self._config.capture_alignment_debug and lyrics_path is not None:
            self._write_debug_capture(
                ctx,
                lyrics_path=lyrics_path,
                lyrics_lines=lyrics_lines,
                align_lines=align_lines,
                words=capture_words,
                words_source=capture_words_source,
                walk_stats=capture_walk_stats,
                tiling_stats=capture_tiling_stats,
                fail_ratio=capture_fail_ratio,
                collapse_ratio=capture_collapse_ratio,
                max_loss_run=capture_max_loss_run,
                method_used=capture_method_used,
                escalated=capture_escalated,
                escalation_trigger=capture_escalation_trigger,
                repair_ranges=capture_repair_ranges,
                line_objects=line_objects,
            )

    # --- Helpers ---

    def _write_debug_capture(
        self,
        ctx: StageContext,
        *,
        lyrics_path: Path,
        lyrics_lines: list[str],
        align_lines: list[str],
        words: list | None,
        words_source: str | None,
        walk_stats: dict | None,
        tiling_stats: dict | None,
        fail_ratio: float | None,
        collapse_ratio: float | None,
        max_loss_run: int | None,
        method_used: str | None,
        escalated: bool,
        escalation_trigger: str | None,
        repair_ranges: list | None,
        line_objects: list[dict],
    ) -> None:
        """Assemble + write the alignment-debug JSON. Errors are logged
        and swallowed — capture failure must never fail the pipeline.
        """
        try:
            cfg = self._config
            config_snapshot = {
                "match_method": cfg.match_method,
                # Routing is concentration-only; the next two are telemetry.
                "align_failure_escalation": cfg.align_failure_escalation,
                "collapse_escalation_threshold": cfg.collapse_escalation_threshold,
                "concentration_escalation_run": cfg.concentration_escalation_run,
                "repair_max_line_fraction": cfg.repair_max_line_fraction,
                "repair_window_margin_s": cfg.repair_window_margin_s,
                "whisper": dataclasses.asdict(cfg.whisper),
            }
            lyrics_suffix = Path(lyrics_path).suffix.lower().lstrip(".")
            try:
                lyrics_rel = str(Path(lyrics_path).relative_to(ctx.song_path.parent))
            except ValueError:
                lyrics_rel = str(lyrics_path)
            lyrics = {
                "origin": ctx.artifacts.get("lyrics_origin", "unknown"),
                "source_path": lyrics_rel,
                "source_kind": lyrics_suffix or "unknown",
                "lines": list(lyrics_lines),
                "align_lines": list(align_lines),
            }
            pipeline_decisions = {
                "align_check_fail_ratio": fail_ratio,
                "collapse_ratio": collapse_ratio,
                "max_loss_run": max_loss_run,
                "method_used": method_used,
                "escalated_to_tiling": escalated,
                "escalation_trigger": escalation_trigger,
                "repair_ranges": repair_ranges or [],
            }
            yt_srt = _find_youtube_srt_path(ctx.song_path)
            # When the YT SRT *is* the lyric source (common — the lyrics
            # stage often hands us the YT captions directly), it can't
            # serve as an independent ground-truth reference. Detect via
            # resolved-path equality and null out the ref so offline
            # analysis can skip it cleanly.
            yt_srt_is_lyric_source = False
            if yt_srt is not None:
                try:
                    yt_srt_is_lyric_source = Path(yt_srt).resolve() == Path(lyrics_path).resolve()
                except OSError:
                    yt_srt_is_lyric_source = False
            ground_truth_refs = {
                "youtube_srt_present": yt_srt is not None,
                "youtube_srt_is_lyric_source": yt_srt_is_lyric_source,
                "youtube_srt_path": (
                    str(yt_srt.relative_to(ctx.song_path.parent))
                    if yt_srt is not None and not yt_srt_is_lyric_source
                    else None
                ),
            }
            bundle = alignment_capture.build_bundle(
                song_stem=ctx.song_path.stem,
                config_snapshot=config_snapshot,
                lyrics=lyrics,
                pipeline_decisions=pipeline_decisions,
                words=words,
                words_source=words_source,
                walk_stats=walk_stats,
                tiling_stats=tiling_stats,
                output_summary=alignment_capture.summarize_line_objects(line_objects),
                output_line_timings=alignment_capture.output_line_timings(line_objects),
                ground_truth_refs=ground_truth_refs,
            )
            path = alignment_capture.write_bundle(ctx.song_path, bundle)
            logger.info(f"[{self.name}] Alignment-debug capture written: {path}")
        except Exception:
            logger.exception(f"[{self.name}] Failed to write alignment-debug capture")

    def _load_lyrics(self, lyrics_path: Path) -> tuple[list[str], list[str]]:
        """Return ``(display_lines, align_lines)``.

        For ``.srt``: parsed subtitle content; ``align_lines`` mirrors
        ``display_lines``.

        For ``.txt``: split into per-line ``{text, align_text}`` via
        :func:`parse_lyric_lines`. ``align_lines`` has inline parens
        stripped (so ``"(I can't help) Falling in love"`` aligns as
        ``"Falling in love"`` while the display preserves the parens).
        """
        suffix = Path(lyrics_path).suffix.lower()
        if suffix == ".srt":
            raw = lyrics_path.read_text(encoding="utf-8")
            subs = list(srt.parse(raw))
            lines = [sub.content.strip() for sub in subs if sub.content.strip()]
            return lines, list(lines)

        raw = lyrics_path.read_text(encoding="utf-8")
        parsed = parse_lyric_lines(raw)
        if not parsed:
            # Fallback for genuinely empty input — keep the matcher's
            # contract of always receiving lists.
            return [], []
        display_lines = [item["text"] for item in parsed]
        align_lines = [item["align_text"] for item in parsed]
        return display_lines, align_lines

    def _generate_ass(self, line_objects: list[dict]) -> str:
        """Build .ass content from line objects using the single Karaoke style."""
        cfg = self._config
        styles_block = (
            f"Style: Karaoke,{cfg.font_name},{cfg.font_size},"
            f"{cfg.primary_color},{cfg.secondary_color},"
            f"{cfg.outline_color},{cfg.back_color},"
            f"0,0,0,0,100,100,0,0,1,"
            f"{cfg.outline_width},{cfg.shadow_offset},2,"
            f"{cfg.margin_left},{cfg.margin_right},{cfg.margin_vertical},1\n"
        )

        header = (
            f"[Script Info]\n"
            f"Title: Karaoke Subtitles\n"
            f"ScriptType: v4.00+\n"
            f"PlayResX: 1920\n"
            f"PlayResY: 1080\n"
            f"Timer: 100.0000\n"
            f"\n"
            f"[V4+ Styles]\n"
            f"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            f"OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            f"ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            f"Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"{styles_block}"
            f"\n"
            f"[Events]\n"
            f"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        events = []
        for line_obj in line_objects:
            words = line_obj["words"]
            if not words:
                continue

            # Pad the event window around the sung word boundaries
            event_start = max(0.0, words[0]["start"] - cfg.line_lead_in_cs / 100.0)
            event_end = words[-1]["end"] + cfg.line_lead_out_cs / 100.0

            # Karaoke cursor starts at the event start time.
            prev_end = event_start
            parts = []

            for i, word_data in enumerate(words):
                word = word_data["word"]
                word_start = word_data["start"]
                word_end = word_data["end"]
                word_dur_cs = max(10, round((word_end - word_start) * 100))

                # Silent cursor advance through any gap before this word.
                gap_cs = max(0, round((word_start - prev_end) * 100))
                if gap_cs > 0:
                    parts.append(f"{{\\k{gap_cs}}}")

                # \kf = left-to-right fill sweep over word_dur_cs centiseconds
                parts.append(f"{{\\kf{word_dur_cs}}}{word}")
                prev_end = word_end

                if i < len(words) - 1:
                    parts.append(" ")

            karaoke_text = "".join(parts)
            events.append(
                f"Dialogue: 0,{_seconds_to_ass_time(event_start)},"
                f"{_seconds_to_ass_time(event_end)},Karaoke,,0,0,0,,{karaoke_text}"
            )

        return header + "\n".join(events) + "\n"

    def _generate_srt(self, line_objects: list[dict]) -> str:
        """Build .srt from line objects so SRT inherits the same segmentation as ASS.

        In alignment mode this preserves the lyric file's curated line breaks;
        in transcription mode line_objects mirror stable-ts segments.
        """
        subtitles = [
            srt.Subtitle(
                index=i,
                start=datetime.timedelta(seconds=line_obj["start"]),
                end=datetime.timedelta(seconds=line_obj["end"]),
                content=line_obj["text"],
            )
            for i, line_obj in enumerate(line_objects, start=1)
            if line_obj["words"]
        ]
        return srt.compose(subtitles)

    @staticmethod
    def _should_write_srt(song_path: Path) -> bool:
        """Skip SRT generation when yt-dlp already provided one."""
        return _find_youtube_srt_path(song_path) is None

    def _discard_cached_safely(self, result_id: str, context_msg: str) -> None:
        """Evict a cached align result; log and swallow if the worker died."""
        try:
            self._worker.discard_cached(result_id)
        except Exception as exc:
            logger.debug("discard_cached failed during %s: %s", context_msg, exc)

    def _repair_spans(
        self,
        line_objects: list[dict],
        repair_ranges: list[dict],
        transcribe_words: list,
        lines: list[str],
        align_lines: list[str],
    ) -> tuple[list[dict], list[dict]]:
        """Repair concentrated walk failures by re-tiling each failed span
        against the transcribe words in its audio window, splicing per line.

        walk's good lines are kept everywhere outside the ranges; inside a
        range, tiling's timing replaces a line only when tiling found it (a
        line walk had is never dropped — mistimed-but-present beats absent).
        Each range's window is bracketed by its good-line neighbours, so the
        spliced objects fall between them and overall timing stays ordered.

        Returns ``(line_objects, repair_meta)`` — repair_meta is the per-range
        capture record (window, lines repaired/kept, window word count).
        """
        n_lines = len(lines)
        range_lines: set[int] = set()
        for r in repair_ranges:
            range_lines.update(range(r["line_start"], r["line_end"] + 1))
        # One-sided right boundary for a range at the song's tail.
        ends = [o["end"] for o in line_objects if o["words"] and o["end"] is not None]
        global_last_end = max(ends) if ends else 0.0
        margin = self._config.repair_window_margin_s

        spliced_by_range: dict[tuple[int, int], list[dict]] = {}
        repair_meta: list[dict] = []
        for r in repair_ranges:
            l0, l1 = r["line_start"], r["line_end"]
            t0 = _good_line_end_before(line_objects, l0, range_lines)
            t1 = _good_line_start_after(line_objects, l1, range_lines, global_last_end)
            window_words = _words_for_window(transcribe_words, t0, t1, margin)
            repair_objs, _stats = match_words_to_lines_tiling_with_stats(
                window_words, lines[l0 : l1 + 1], align_lines[l0 : l1 + 1]
            )
            for obj in repair_objs:
                obj["line_id"] += l0  # remap sublist line_id to absolute
            spliced_by_range[(l0, l1)] = _splice_range(line_objects, repair_objs, l0, l1)
            repaired = {o["line_id"] for o in repair_objs}
            repair_meta.append(
                {
                    "line_start": l0,
                    "line_end": l1,
                    "t0": t0,
                    "t1": t1,
                    "lines_repaired": len(repaired),
                    "lines_kept_from_walk": (l1 - l0 + 1) - len(repaired),
                    "window_word_count": len(window_words),
                }
            )

        # Reassemble in lyric order: walk lines between ranges, then each
        # range's spliced objects in place. Ranges are disjoint.
        result: list[dict] = []
        cursor = 0
        for r in sorted(repair_ranges, key=lambda x: x["line_start"]):
            l0, l1 = r["line_start"], r["line_end"]
            for li in range(cursor, l0):
                walk_obj = line_objects[li]
                walk_obj.setdefault("line_id", li)
                result.append(walk_obj)
            result.extend(spliced_by_range[(l0, l1)])
            cursor = l1 + 1
        for li in range(cursor, n_lines):
            walk_obj = line_objects[li]
            walk_obj.setdefault("line_id", li)
            result.append(walk_obj)

        return result, repair_meta


# ---------------------------------------------------------------------------
# Pipeline call wrapper
# ---------------------------------------------------------------------------


def _model_call(ctx, phase: Phase, fn):
    """Wrap a single model call in an activity scope (or run it bare
    when ctx.cancel is None).  Translates AlignmentCancelledError to
    PipelineCancelled so the orchestrator only needs to catch one
    exception type.
    """
    if ctx.cancel is None:
        return fn()
    cancel_event = ctx.cancel.event
    try:
        with ctx.cancel.activity(phase, SetEvent(cancel_event)):
            return fn()
    except AlignmentCancelledError:
        raise PipelineCancelled(phase)


def _find_youtube_srt_path(song_path: Path) -> Path | None:
    """Return the YouTube-supplied SRT for ``song_path`` if one exists.

    Mirrors the discovery logic in
    :meth:`pikaraoke.pipeline.stages.lyrics_fetch.LyricsFetchStage._find_srt`
    so both stages agree on which file represents the YT captions.
    """
    subs = song_path.parent / "subtitles"
    for name in (f"{song_path.stem}.en.srt", f"{song_path.stem}.srt"):
        candidate = subs / name
        if candidate.is_file():
            return candidate
    return None


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format: H:MM:SS.cc (centiseconds)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)  # centiseconds
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ---------------------------------------------------------------------------
# Sectional tiling repair (windowed merge) — pure helpers
# ---------------------------------------------------------------------------


def _build_repair_ranges(loss_spans: list[dict], concentration_run: int) -> list[dict]:
    """Merge adjacent failed-token runs into line-ranges, keeping those
    whose combined collapsed/dropped token count reaches ``concentration_run``.

    Merge-then-threshold: adjacent (touching or with no fully-good line
    between) loss spans combine first, then a merged range qualifies only if
    its total failed tokens >= N. Two sub-N collapses on neighbouring lines
    thus combine into one repair range instead of both being missed, while a
    lone small run still falls through to walk's interpolation.

    Returns ``[{line_start, line_end, failed_tokens}]`` in line order.
    """
    if not loss_spans:
        return []
    spans = sorted(loss_spans, key=lambda s: (s["line_start"], s["line_end"]))
    merged: list[dict] = []
    for s in spans:
        tokens = s["token_end"] - s["token_start"]
        if merged and s["line_start"] <= merged[-1]["line_end"] + 1:
            merged[-1]["line_end"] = max(merged[-1]["line_end"], s["line_end"])
            merged[-1]["failed_tokens"] += tokens
        else:
            merged.append(
                {
                    "line_start": s["line_start"],
                    "line_end": s["line_end"],
                    "failed_tokens": tokens,
                }
            )
    return [m for m in merged if m["failed_tokens"] >= concentration_run]


def _decide_route(
    loss_spans: list[dict],
    n_lines: int,
    concentration_run: int,
    max_line_fraction: float,
) -> tuple[str, list[dict]]:
    """Route an auto-mode song on its concentrated failures alone.

    Returns ``(route, repair_ranges)`` where route is one of ``"keep_walk"``
    (no concentrated hole — interpolation handles it), ``"whole_tiling"``
    (ranges cover more than ``max_line_fraction`` of lines — broken nearly
    everywhere, so discard align entirely), or ``"repair"`` (concentrated
    holes in an otherwise-healthy song).
    """
    ranges = _build_repair_ranges(loss_spans, concentration_run)
    if not ranges:
        return "keep_walk", ranges
    lines_covered = sum(r["line_end"] - r["line_start"] + 1 for r in ranges)
    if n_lines > 0 and lines_covered / n_lines > max_line_fraction:
        return "whole_tiling", ranges
    return "repair", ranges


def _words_for_window(words: list, t0: float, t1: float, margin: float) -> list:
    """Transcribe words whose start falls in ``[t0 - margin, t1 + margin]``
    (inclusive). The small margin avoids clipping a boundary word.

    This is the seam for #3 (clip re-decode): in #2 it filters the one
    whole-song transcribe; later it becomes a clip transcribe over the
    extracted ``[t0, t1]`` audio. Everything downstream is identical.
    """
    lo = t0 - margin
    hi = t1 + margin
    return [w for w in words if lo <= w["start"] <= hi]


def _splice_range(
    walk_line_objects: list[dict],
    repair_objects: list[dict],
    l0: int,
    l1: int,
) -> list[dict]:
    """Per-line preference splice for one repair range ``[l0, l1]``.

    For each lyric line in the range: if tiling produced object(s) for it
    (matched by absolute ``line_id``), use them (repeats sorted by start);
    otherwise keep walk's existing object so a line walk had never
    disappears — mistimed-but-present beats absent. Returns the range's
    objects in lyric order.
    """
    by_line: dict[int, list[dict]] = {}
    for obj in repair_objects:
        by_line.setdefault(obj["line_id"], []).append(obj)
    spliced: list[dict] = []
    for line_id in range(l0, l1 + 1):
        if line_id in by_line:
            spliced.extend(sorted(by_line[line_id], key=lambda o: o["start"]))
        else:
            walk_obj = walk_line_objects[line_id]
            walk_obj.setdefault("line_id", line_id)
            spliced.append(walk_obj)
    return spliced


def _good_line_end_before(line_objects: list[dict], l0: int, range_lines: set[int]) -> float:
    """End time of the last good line before ``l0`` (0.0 at the song head).

    A good line is one not in any repair range and with real timing.
    """
    for li in range(l0 - 1, -1, -1):
        if li in range_lines:
            continue
        obj = line_objects[li]
        if obj.get("start") is not None and obj.get("end") is not None:
            return obj["end"]
    return 0.0


def _good_line_start_after(
    line_objects: list[dict], l1: int, range_lines: set[int], global_last_end: float
) -> float:
    """Start time of the first good line after ``l1`` (``global_last_end``
    at the song tail). See :func:`_good_line_end_before`.
    """
    for li in range(l1 + 1, len(line_objects)):
        if li in range_lines:
            continue
        obj = line_objects[li]
        if obj.get("start") is not None:
            return obj["start"]
    return global_last_end
