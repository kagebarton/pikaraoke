"""Lyric alignment/transcription stage: generate ASS (and SRT) from vocal stem.

Two modes:
- Alignment (lyrics_path provided): aligns the given .txt or .srt lyrics to
  the vocal stem via stable-ts model.align() + refine, transcribes the stem
  independently, and feeds both placements into the joint matcher — which
  scores each lyric line's align candidate against its transcribe candidates
  and picks the max-score non-overlapping subset (see
  pikaraoke.lib.joint_match). Every lyric line ends up in the karaoke output.
- Transcription (no lyrics_path): runs model.transcribe() directly; stable-ts
  determines segment/word boundaries from the audio alone.

In both modes the same ASS and SRT generators are used. The difference is
how line objects are built: alignment maps words onto predefined lyric lines
via the joint matcher; transcription uses stable-ts segments directly as lines.

Each model call is wrapped in its own cancellation activity scope.
Alignment transcribes first (Phase.TRANSCRIBE, no refine) for the de-reverb
gate, then aligns (Phase.ALIGN, align + refine in one worker call) once on the
gated stem. Transcription mode stays a single Phase.TRANSCRIBE call.

On the alignment route, a reverb-washed vocal stem (whole-stem transcribe
yield below ``dereverb_yield_wpm``) triggers a de-reverb retry: the stem
worker swaps to the de-reverb roformer and re-transcribes on the dry stem,
which is then adopted for the single align pass. Any retry failure keeps the
wet-stem result — the retry can only improve a song, never fail it.

ASS/SRT are written to ctx.tmp_dir first and moved to the final output
directory only after both writes succeed — preventing orphan files on
cancellation.
"""

import dataclasses
import datetime
import logging
import shutil
import wave
from pathlib import Path

import srt

from pikaraoke.lib import alignment_capture, ytasr
from pikaraoke.lib.genius_lyrics import parse_lyric_lines
from pikaraoke.lib.joint_match import match_words_to_lines_joint_with_stats
from pikaraoke.lib.srt_cues import cue_spans_from_srt
from pikaraoke.lib.windowed_realign import (
    analyze_pass1,
    build_spans,
    merge_spans,
    replay_span,
    span_align_lines,
    span_needs_realign,
)
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.context import Phase, PipelineCancelled, SetEvent, StageContext
from pikaraoke.pipeline.stages._ffmpeg_helpers import run_ffmpeg
from pikaraoke.pipeline.stages.base import BaseStage
from pikaraoke.pipeline.workers.stem_worker import StemWorker, WorkerCancelledError
from pikaraoke.pipeline.workers.whisper_worker import (
    AlignmentCancelledError,
    WhisperWorker,
)

logger = logging.getLogger(__name__)


class LyricAlignStage(BaseStage):
    """Align lyrics to vocal stem and generate karaoke ASS + optional SRT."""

    name = "lyric_align"

    def __init__(
        self,
        whisper_worker: WhisperWorker,
        config: PipelineConfig,
        stem_worker: StemWorker | None = None,
    ) -> None:
        self._worker = whisper_worker
        self._config = config
        # Used only by the joint route's de-reverb retry; None disables it.
        self._stem_worker = stem_worker

    def run(self, ctx: StageContext) -> None:
        lyrics_path = ctx.artifacts.get("lyrics_path")
        vocal_wav = ctx.artifacts.get("vocal_wav")

        if vocal_wav is None:
            raise RuntimeError(f"[{self.name}] No vocal_wav in artifacts")

        # Debug-capture scratchpad: populated as the stage progresses,
        # written at the end only on the alignment-mode happy paths.
        capture_words: list | None = None
        capture_words_source: str | None = None
        capture_joint_stats: dict | None = None
        capture_transcribe_words: list | None = None
        capture_method_used: str | None = None

        if lyrics_path is not None:
            # --- Alignment mode (joint matcher) ---
            lyrics_lines, align_lines, _ = self._load_lyrics(lyrics_path)
            lyrics_text = "\n".join(align_lines)

            logger.info(f"[{self.name}] Aligning lyrics to vocal stem: {Path(vocal_wav).name}")

            (
                line_objects,
                capture_words,
                capture_transcribe_words,
                capture_joint_stats,
            ) = self._run_joint(
                ctx,
                vocal_wav,
                lyrics_text,
                lyrics_lines,
                align_lines,
            )
            capture_words_source = "refine"
            capture_method_used = "joint"

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
        # the processing-page row can render it (e.g. "genius+joint" shows
        # the lyric source at a glance). Independent of the debug capture
        # flag below — the UI label must work even with capture off.
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
                joint_stats=capture_joint_stats,
                transcribe_words=capture_transcribe_words,
                method_used=capture_method_used,
                line_objects=line_objects,
                wrote_srt=write_srt,
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
        joint_stats: dict | None,
        transcribe_words: list | None,
        method_used: str | None,
        line_objects: list[dict],
        wrote_srt: bool,
    ) -> None:
        """Assemble + write the alignment-debug JSON. Errors are logged
        and swallowed — capture failure must never fail the pipeline.

        ``wrote_srt`` is the stage's own SRT-write decision; it determines
        whether a *real* YouTube caption existed (see ``ground_truth_refs``).
        """
        try:
            cfg = self._config
            config_snapshot = {
                "joint_windowed_realign": cfg.joint_windowed_realign,
                "joint_alpha": cfg.joint_alpha,
                "joint_beta": cfg.joint_beta,
                "joint_margin_s": cfg.joint_margin_s,
                "joint_max_edit_ratio": cfg.joint_max_edit_ratio,
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
            # The adopted YouTube ASR caption (txt-sourced songs): the persisted
            # .en.asr.json3 path plus word-count / wpm provenance.
            ytasr_ref = ctx.artifacts.get("ytasr")
            if ytasr_ref is not None:
                lyrics["ytasr"] = ytasr_ref
            # The Genius song identity (id/title/artist) for genius-origin songs,
            # so a regen can re-resolve the source without re-prompting.
            genius_ref = ctx.artifacts.get("genius")
            if genius_ref is not None:
                lyrics["genius"] = genius_ref
            pipeline_decisions = {
                "method_used": method_used,
                "joint_alpha": cfg.joint_alpha if method_used == "joint" else None,
                "joint_beta": cfg.joint_beta if method_used == "joint" else None,
            }
            # A real YouTube caption existed iff the stage did NOT generate its
            # own SRT this run (``_should_write_srt`` is True only when no SRT
            # is on disk). Re-probing the filesystem here would re-find a
            # just-written — or stale, from a prior run — generated SRT at
            # ``subtitles/<stem>.srt`` and mislabel it as a caption.
            yt_srt = None if wrote_srt else _find_youtube_srt_path(ctx.song_path)
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
                joint_stats=joint_stats,
                transcribe_words=transcribe_words,
                output_summary=alignment_capture.summarize_line_objects(line_objects),
                output_line_timings=alignment_capture.output_line_timings(line_objects),
                ground_truth_refs=ground_truth_refs,
                media_duration_s=ctx.artifacts.get("media_duration_s"),
            )
            path = alignment_capture.write_bundle(ctx.song_path, bundle)
            logger.info(f"[{self.name}] Alignment-debug capture written: {path}")
        except Exception:
            logger.exception(f"[{self.name}] Failed to write alignment-debug capture")

    def _load_lyrics(
        self, lyrics_path: Path
    ) -> tuple[list[str], list[str], list[tuple[float, float]] | None]:
        """Return ``(display_lines, align_lines, cue_spans)``.

        For ``.srt``: each subtitle's content is run through
        :func:`clean_srt_line` (strips HTML tags, musical notes,
        ``[stage directions]``, ``(stage directions)``, collapses
        2-line wraps, normalizes curly quotes). Lines with no letters
        after cleanup are dropped. ``align_lines`` mirrors
        ``display_lines`` — SRT has no separate align/display
        distinction. ``cue_spans`` carries each kept line's
        uploader-synced ``(start, end)`` (consumed by the SRT cue-align
        path).

        For ``.txt``: split into per-line ``{text, align_text}`` via
        :func:`parse_lyric_lines`. ``align_lines`` has the bracket
        characters removed but keeps their contents (so ``"(I can't
        help) Falling in love"`` aligns as ``"I can't help Falling in
        love"`` while the display preserves the parens). ``cue_spans``
        is None — plain lyrics carry no timing.
        """
        suffix = Path(lyrics_path).suffix.lower()
        if suffix == ".srt":
            raw = lyrics_path.read_text(encoding="utf-8")
            lines, spans = cue_spans_from_srt(raw)
            return lines, list(lines), spans

        raw = lyrics_path.read_text(encoding="utf-8")
        parsed = parse_lyric_lines(raw)
        if not parsed:
            # Fallback for genuinely empty input — keep the matcher's
            # contract of always receiving lists.
            return [], [], None
        display_lines = [item["text"] for item in parsed]
        align_lines = [item["align_text"] for item in parsed]
        return display_lines, align_lines, None

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

    def _run_joint(
        self,
        ctx: StageContext,
        vocal_wav: Path,
        lyrics_text: str,
        lyrics_lines: list[str],
        align_lines: list[str],
    ) -> tuple[list[dict], list[dict], list[dict], dict]:
        """Run the joint matcher route: de-reverb gate (transcribe-first) →
        align + refine on the gated stem → joint DP matcher.

        YouTube ASR words (when the lyrics-fetch stage adopted a caption) join
        align + transcribe as the third candidate source; absent, the matcher
        runs plain two-source.

        Returns ``(line_objects, refined_align_words, transcribe_words, joint_stats)``.
        Refined align words and the transcribe words are returned for the
        capture bundle — both are needed to re-run the joint matcher
        offline at different α values.
        """
        # Transcribe-first de-reverb gate (shared prefix): transcribe, gate on
        # yield, adopt a de-reverbed stem if the wet one is reverb-washed. Then
        # align once on the final stem — one saved align pass when the gate fires.
        vocal_wav, transcribe_words, dereverb_stats = self._dereverb_gate(ctx, vocal_wav)

        align_words = _model_call(
            ctx,
            Phase.ALIGN,
            lambda: self._worker.align_refine(
                vocal_path=vocal_wav,
                lyrics_text=lyrics_text,
                cancel_event=ctx.cancel.event if ctx.cancel else None,
            ),
        )

        ytasr_words = self._ytasr_words(ctx)
        line_objects, joint_stats = match_words_to_lines_joint_with_stats(
            align_words,
            transcribe_words,
            lyrics_lines,
            align_lines,
            alpha=self._config.joint_alpha,
            beta=self._config.joint_beta,
            margin_s=self._config.joint_margin_s,
            max_edit_ratio=self._config.joint_max_edit_ratio,
            ytasr_words=ytasr_words,
        )
        # Snapshot the pass-1 placements before windowed re-align mutates them —
        # the baseline an offline pass-1 re-run validates against
        # (output_line_timings holds the final placements).
        joint_stats["pass1_line_timings"] = alignment_capture.output_line_timings(line_objects)
        if dereverb_stats is not None:
            joint_stats["dereverb"] = dereverb_stats
        if self._config.joint_windowed_realign:
            try:
                line_objects = self._realign_windows(
                    ctx,
                    vocal_wav,
                    line_objects,
                    joint_stats,
                    lyrics_lines,
                    align_lines,
                    align_words,
                    transcribe_words,
                )
            except PipelineCancelled:
                raise
            except Exception:
                logger.exception(
                    "[%s] windowed re-align failed; keeping pass-1 placements", self.name
                )
        return line_objects, align_words, transcribe_words, joint_stats

    def _ytasr_words(self, ctx: StageContext) -> list[dict] | None:
        """Words from the adopted YouTube ASR caption, for the joint 3rd source.

        The lyrics-fetch stage stashes ``ctx.artifacts["ytasr"]`` only for a
        caption that cleared the quality gates, so this just parses the
        persisted json3. Returns None (absent/unreadable) — the matcher then
        runs plain two-source.
        """
        ref = ctx.artifacts.get("ytasr")
        if not ref:
            return None
        try:
            text = (ctx.song_path.parent / ref["asr_file"]).read_text(encoding="utf-8")
            words, _ = ytasr.parse_json3(text)
            return words or None
        except (OSError, ValueError, KeyError):
            logger.warning("[%s] YTASR json3 unreadable; running two-source", self.name)
            return None

    def _dereverb_gate(
        self, ctx: StageContext, vocal_wav: Path
    ) -> tuple[Path, list[dict], dict | None]:
        """Transcribe-first de-reverb gate: the shared prefix of the audio routes.

        Transcribe (no refine) on the vocal stem; a reverb-washed stem starves
        transcribe (the one corpus case yields 14.4 wpm vs >= 50.5 everywhere
        else), which guts both joint scoring and windowed re-align. Below
        ``dereverb_yield_wpm`` the stem is de-reverbed and re-transcribed, and
        the dry stem is adopted; any failure keeps the wet stem. Returns
        ``(stem_to_align, transcribe_words, dereverb_stats | None)``.
        """
        logger.info(
            f"[{self.name}] Transcribing (no refine) for joint match: {Path(vocal_wav).name}"
        )
        transcribe_words = _model_call(
            ctx,
            Phase.TRANSCRIBE,
            lambda: self._worker.transcribe_words(
                vocal_path=vocal_wav,
                cancel_event=ctx.cancel.event if ctx.cancel else None,
                refine=False,
            ),
        )
        dereverb_stats: dict | None = None
        yield_wpm = self._transcribe_yield_wpm(transcribe_words, vocal_wav)
        if yield_wpm is not None and yield_wpm < self._config.dereverb_yield_wpm:
            logger.warning(
                "[%s] transcribe yield %.1f wpm < %.1f — vocal stem looks "
                "reverb-washed; retrying on a de-reverbed stem",
                self.name,
                yield_wpm,
                self._config.dereverb_yield_wpm,
            )
            dereverb_stats = {"yield_wpm": round(yield_wpm, 1), "succeeded": False}
            retried = self._dereverb_retry(ctx, vocal_wav)
            if retried is not None:
                vocal_wav, transcribe_words = retried
                retry_wpm = self._transcribe_yield_wpm(transcribe_words, vocal_wav)
                dereverb_stats["succeeded"] = True
                dereverb_stats["retry_yield_wpm"] = (
                    round(retry_wpm, 1) if retry_wpm is not None else None
                )
        return vocal_wav, transcribe_words, dereverb_stats

    def _transcribe_yield_wpm(self, transcribe_words: list[dict], vocal_wav: Path) -> float | None:
        """Whole-stem transcribe yield in words per minute.

        None when the de-reverb retry is unavailable (no stem worker,
        knob disabled) or the stem duration can't be read — the gate
        treats None as "don't retry".
        """
        cfg = self._config
        if self._stem_worker is None or cfg.dereverb_yield_wpm <= 0 or not cfg.dereverb_model_name:
            return None
        try:
            minutes = _wav_duration(vocal_wav) / 60.0
        except (wave.Error, OSError, EOFError):
            return None
        if minutes <= 0:
            return None
        return len(transcribe_words) / minutes

    def _dereverb_retry(
        self,
        ctx: StageContext,
        vocal_wav: Path,
    ) -> tuple[Path, list[dict]] | None:
        """De-reverb the vocal stem and re-transcribe on it.

        Returns ``(dry_vocal_wav, transcribe_words)``, or None to keep the
        wet-stem result — a retry must never fail the song. The single align
        pass runs on whichever stem the gate returns, so no align happens here.
        Cancellation always propagates.
        """
        cancel_event = ctx.cancel.event if ctx.cancel else None
        try:
            dry_wav = self._load_cached_dereverb(ctx)
            if dry_wav is None:
                dry_wav, _reverb_tail = _model_call(
                    ctx,
                    Phase.DEREVERB,
                    lambda: self._stem_worker.separate(
                        wav_path=Path(vocal_wav),
                        output_dir=ctx.tmp_dir,
                        cancel_event=cancel_event,
                        model_name=self._config.dereverb_model_name,
                    ),
                )
                self._persist_dereverb(ctx, dry_wav)
            transcribe_words = _model_call(
                ctx,
                Phase.TRANSCRIBE,
                lambda: self._worker.transcribe_words(
                    vocal_path=dry_wav,
                    cancel_event=cancel_event,
                    refine=False,
                ),
            )
        except PipelineCancelled:
            raise
        except Exception as exc:
            logger.warning(
                "[%s] de-reverb retry failed, keeping wet-stem results: %s",
                self.name,
                exc,
            )
            return None
        return dry_wav, transcribe_words

    def _dereverb_cache_path(self, ctx: StageContext) -> Path:
        """Persisted de-reverb stem location: ``<song>/dereverb/<stem>---dereverb.m4a``.

        Mirrors the ``vocal/<stem>---vocal.m4a`` layout so the regen tool and a
        human can find it the same way.
        """
        return ctx.song_path.parent / "dereverb" / f"{ctx.song_path.stem}---dereverb.m4a"

    def _load_cached_dereverb(self, ctx: StageContext) -> Path | None:
        """Decode the cached de-reverb stem to WAV, or None to separate fresh.

        Returns None when caching is off, no cache exists, or the decode fails
        (a corrupt cache just means we re-separate). Cancellation propagates.
        """
        if not self._config.cache_dereverb_stem:
            return None
        cache = self._dereverb_cache_path(ctx)
        if not cache.is_file():
            return None
        dry_wav = ctx.tmp_dir / f"{ctx.song_path.stem}_dereverb.wav"
        try:
            run_ffmpeg(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "warning",
                    "-y",
                    "-i",
                    str(cache),
                    "-ac",
                    "2",
                    "-ar",
                    "44100",
                    "-sample_fmt",
                    "s16",
                    str(dry_wav),
                ],
                ctx,
                Phase.EXTRACT,
            )
        except PipelineCancelled:
            raise
        except RuntimeError:
            logger.warning("[%s] cached de-reverb stem decode failed; re-separating", self.name)
            return None
        logger.info("[%s] reusing cached de-reverb stem: %s", self.name, cache.name)
        return dry_wav

    def _persist_dereverb(self, ctx: StageContext, dry_wav: Path) -> None:
        """Transcode the dry stem to the de-reverb cache (best-effort).

        Caching failures are logged and swallowed — a missing cache only costs a
        re-separation next time, never the song. Cancellation propagates. Writes
        to ``tmp_dir`` first and moves into place so a cancel can't leave a
        partial m4a at the cache path.
        """
        if not self._config.cache_dereverb_stem:
            return
        cache = self._dereverb_cache_path(ctx)
        tmp_out = ctx.tmp_dir / cache.name
        try:
            run_ffmpeg(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "warning",
                    "-y",
                    "-threads",
                    self._config.ffmpeg_threads,
                    "-i",
                    str(dry_wav),
                    "-c:a",
                    "aac",
                    "-q:a",
                    self._config.aac_quality,
                    str(tmp_out),
                ],
                ctx,
                Phase.TRANSCODE,
            )
            cache.parent.mkdir(exist_ok=True)
            shutil.move(str(tmp_out), str(cache))
        except PipelineCancelled:
            raise
        except (RuntimeError, OSError):
            logger.warning("[%s] failed to cache de-reverb stem: %s", self.name, cache)
            return
        logger.info("[%s] cached de-reverb stem: %s", self.name, cache.name)

    def _realign_windows(
        self,
        ctx: StageContext,
        vocal_wav: Path,
        line_objects: list[dict],
        joint_stats: dict,
        lyrics_lines: list[str],
        align_lines: list[str],
        align_words: list[dict],
        transcribe_words: list[dict],
    ) -> list[dict]:
        """Second pass: re-align suspect spans between trusted anchors.

        Per-span failures degrade to the pass-1 placement — a refinement
        must never fail the song. Cancellation always propagates.
        """
        cfg = self._config
        anchors, suspects = analyze_pass1(
            align_lines,
            line_objects,
            joint_stats,
            transcribe_words,
            margin_s=cfg.joint_margin_s,
            max_edit_ratio=cfg.joint_max_edit_ratio,
        )
        telemetry = {
            "n_anchors": len(anchors),
            "n_suspects": len(suspects),
            "n_spans": 0,
            "n_realigned": 0,
            "n_spans_kept_pass1": 0,
        }
        joint_stats["windowed_realign"] = telemetry
        if not suspects or not anchors:
            # No suspects: nothing to repair. No anchors (transcribe
            # found nothing to corroborate): the lone full-song span
            # would just repeat pass-1 at full GPU cost for no possible
            # gain — new placements need transcribe corroboration.
            logger.info(
                "[%s] windowed re-align skipped: %s",
                self.name,
                "no suspect lines" if not suspects else "no trusted anchors",
            )
            return line_objects

        spans = build_spans(anchors, len(lyrics_lines), _wav_duration(vocal_wav))
        todo = [s for s in spans if span_needs_realign(s, suspects)]
        telemetry["n_spans"] = len(spans)
        telemetry["n_realigned"] = len(todo)
        if not todo:
            return line_objects

        logger.info(
            "[%s] windowed re-align: %d/%d spans have suspect lines (%d anchors, %d suspects)",
            self.name,
            len(todo),
            len(spans),
            len(anchors),
            len(suspects),
        )
        results: list = []
        span_captures: list[dict] = []
        for k, span in enumerate(todo):
            result, span_words = self._realign_one_span(
                ctx, vocal_wav, span, k, lyrics_lines, align_lines, transcribe_words
            )
            results.append(result)
            # Capture each span's refined align words (absolute song time) so
            # the re-align replays offline via replay_span + merge_spans with
            # no inference. align_words is None when the slice align failed or
            # was skipped — that span kept its pass-1 placement.
            span_captures.append({**span, "align_words": span_words})
        telemetry["spans"] = span_captures
        telemetry["n_spans_kept_pass1"] = sum(1 for r in results if r is None)
        return merge_spans(line_objects, todo, results, len(lyrics_lines), align_words)

    def _realign_one_span(
        self,
        ctx: StageContext,
        vocal_wav: Path,
        span: dict,
        span_idx: int,
        lyrics_lines: list[str],
        align_lines: list[str],
        transcribe_words: list[dict],
    ) -> tuple[tuple[dict[int, dict], dict[int, str]] | None, list[dict] | None]:
        """Slice + re-align one span.

        Returns ``(replay_result, span_words)``. ``replay_result`` is None
        when the span keeps pass-1 (nothing alignable, or the slice align
        failed). ``span_words`` is the slice's refined align words shifted
        to absolute song time — captured for offline replay — or None
        whenever no inference ran for the span.
        """
        sub_lines = span_align_lines(span, align_lines)
        if sub_lines is None:
            return None, None
        slice_path = ctx.tmp_dir / f"realign_span{span_idx:02d}.wav"
        try:
            # -ss/-to as input options: sample-exact for PCM WAV and
            # seeks instead of decoding everything before t0.
            run_ffmpeg(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    f"{span['t0']:.3f}",
                    "-to",
                    f"{span['t1']:.3f}",
                    "-i",
                    str(vocal_wav),
                    str(slice_path),
                ],
                ctx,
                Phase.EXTRACT,
            )
            words = _model_call(
                ctx,
                Phase.ALIGN,
                lambda: self._worker.align_refine(
                    vocal_path=slice_path,
                    lyrics_text="\n".join(sub_lines),
                    cancel_event=ctx.cancel.event if ctx.cancel else None,
                ),
            )
        except PipelineCancelled:
            raise
        except Exception as exc:
            # A dead worker is also just a degraded span: the next
            # worker job auto-restarts the subprocess.
            logger.warning(
                "[%s] span L%d-%d re-align failed, keeping pass-1: %s",
                self.name,
                span["lid_lo"],
                span["lid_hi"],
                exc,
            )
            return None, None
        finally:
            slice_path.unlink(missing_ok=True)
        for w in words:
            w["start"] += span["t0"]
            w["end"] += span["t0"]
        replay_result = replay_span(
            span,
            words,
            transcribe_words,
            lyrics_lines,
            align_lines,
            alpha=self._config.joint_alpha,
            margin_s=self._config.joint_margin_s,
            max_edit_ratio=self._config.joint_max_edit_ratio,
        )
        return replay_result, words


# ---------------------------------------------------------------------------
# Pipeline call wrapper
# ---------------------------------------------------------------------------


def _model_call(ctx, phase: Phase, fn):
    """Wrap a single model call in an activity scope (or run it bare
    when ctx.cancel is None).  Translates both workers' cancellation
    exceptions to PipelineCancelled so the orchestrator only needs to
    catch one exception type.
    """
    if ctx.cancel is None:
        return fn()
    cancel_event = ctx.cancel.event
    try:
        with ctx.cancel.activity(phase, SetEvent(cancel_event)):
            return fn()
    except (AlignmentCancelledError, WorkerCancelledError):
        raise PipelineCancelled(phase)


def _wav_duration(path: Path) -> float:
    """Duration in seconds from the WAV header.

    Both vocal-WAV producers (load_vocal's ffmpeg decode and the stem
    separator) emit 16-bit PCM, which the stdlib reader handles; an
    exotic format raises wave.Error, which the caller's degrade-to-pass-1
    guard absorbs.
    """
    with wave.open(str(path)) as wav:
        return wav.getnframes() / wav.getframerate()


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
