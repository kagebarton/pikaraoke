"""Lyric alignment/transcription stage: generate ASS (and SRT) from vocal stem.

Two modes:
- Alignment (lyrics_path provided): aligns the given .txt or .srt lyrics to
  the vocal stem via stable-ts model.align(), then refines timestamps. A
  two-pointer walk matcher pairs lyric tokens to whisper words with gap
  interpolation for unmatched references — every lyric token ends up in
  the karaoke output, gap-free. On poor walk alignment quality, escalates
  to the order-independent tiling matcher.
- Transcription (no lyrics_path): runs model.transcribe() directly; stable-ts
  determines segment/word boundaries from the audio alone.

In both modes the same ASS and SRT generators are used. The difference is
how line objects are built: alignment pairs words to predefined lyric lines
via the walk matcher; transcription uses stable-ts segments directly as lines.

Each model call is wrapped in its own cancellation activity scope.
Alignment uses two scopes — Phase.ALIGN_CHECK (align only, captures
stable-ts's segment-failure ratio) followed by Phase.REFINE (refine the
cached align result). Splitting these means a future escalation policy
can discard the align output before paying refine's cost. Transcription
mode stays a single Phase.TRANSCRIBE call.

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
        capture_escalated = False
        capture_method_used: str | None = None

        if lyrics_path is not None:
            # --- Alignment mode ---
            lyrics_lines, align_lines = self._load_lyrics(lyrics_path)
            lyrics_text = "\n".join(align_lines)

            logger.info(f"[{self.name}] Aligning lyrics to vocal stem: {Path(vocal_wav).name}")

            method = self._config.match_method
            use_tiling = method == "tiling"

            if not use_tiling:
                # walk / auto: run align() first so we can gate on its
                # failure ratio *before* paying for refine.
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
                fail_ratio = check["fail_ratio"]
                capture_fail_ratio = fail_ratio
                threshold = self._config.align_failure_escalation

                if method == "auto" and fail_ratio > threshold:
                    logger.warning(
                        "[%s] align() failed %.0f%% of segments (> %.0f%% threshold) "
                        "— escalating to tiling matcher",
                        self.name,
                        fail_ratio * 100,
                        threshold * 100,
                    )
                    self._discard_cached_safely(result_id, "escalation")
                    use_tiling = True
                    capture_escalated = True

                if not use_tiling:
                    if method == "auto":
                        logger.info(
                            "[%s] align() failure ratio %.0f%% within threshold "
                            "— keeping walk match",
                            self.name,
                            fail_ratio * 100,
                        )
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

            if use_tiling:
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
                method_used=capture_method_used,
                escalated=capture_escalated,
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
        method_used: str | None,
        escalated: bool,
        line_objects: list[dict],
    ) -> None:
        """Assemble + write the alignment-debug JSON. Errors are logged
        and swallowed — capture failure must never fail the pipeline.
        """
        try:
            cfg = self._config
            config_snapshot = {
                "match_method": cfg.match_method,
                "align_failure_escalation": cfg.align_failure_escalation,
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
                "method_used": method_used,
                "escalated_to_tiling": escalated,
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
