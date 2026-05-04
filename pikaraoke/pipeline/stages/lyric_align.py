"""Lyric alignment/transcription stage: generate ASS (and SRT) from vocal stem.

Two modes:
- Alignment (lyrics_path provided): aligns the given .txt or .srt lyrics to
  the vocal stem via stable-ts model.align(), then refines timestamps.
- Transcription (no lyrics_path): runs model.transcribe() directly; stable-ts
  determines segment/word boundaries from the audio alone.

In both modes the same ASS and SRT generators are used. The difference is
how line objects are built: alignment pairs words to predefined lyric lines
by count; transcription uses stable-ts segments directly as lines.

Each model call is wrapped in its own cancellation activity scope
(Phase.ALIGN / Phase.TRANSCRIBE). The refine phase is now folded into
the worker's align_refine / transcribe_refine methods, so Phase.REFINE
no longer exists on the parent side.

ASS/SRT are written to ctx.tmp_dir first and moved to the final output
directory only after both writes succeed — preventing orphan files on
cancellation.

ASS generation ported from snippets/stable_align.py, but reads all
styling/timing parameters from PipelineConfig instead of module-level
constants.
"""

import datetime
import logging
import re
import shutil
from pathlib import Path

import srt

from pikaraoke.lib.genius_lyrics import parse_genius_sections
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

        if lyrics_path is not None:
            # --- Alignment mode: ALIGN (includes refine) ---
            lyrics_text, lyrics_format, lyrics_structure = self._load_lyrics(lyrics_path)
            ctx.artifacts["lyrics_text"] = lyrics_text
            ctx.artifacts["lyrics_format"] = lyrics_format
            if lyrics_structure is not None:
                ctx.artifacts["lyrics_structure"] = lyrics_structure

            logger.info(f"[{self.name}] Aligning lyrics to vocal stem: {Path(vocal_wav).name}")
            line_objects = _model_call(
                ctx,
                Phase.ALIGN,
                lambda: self._worker.align_refine(
                    vocal_path=vocal_wav,
                    lyrics_text=lyrics_text,
                    cancel_event=ctx.cancel.event if ctx.cancel else None,
                ),
            )
            write_srt = self._should_write_srt(ctx.song_path)
        else:
            # --- Transcription mode: TRANSCRIBE (includes refine) ---
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

    # --- Helpers ---

    def _load_lyrics(self, lyrics_path: Path) -> tuple[str, str, list[dict] | None]:
        """Return ``(lyrics_text, lyrics_format, structure)``.

        ``structure`` is a list of ``{line, section, attribution}`` dicts
        when the input is Genius-formatted ``.txt``, else ``None``.

        For Genius ``.txt``:
        - Parse section headers with :func:`parse_genius_sections`.
        - Strip header lines and empty lines from the text.
        - The remaining text (using ``align_text`` from each line) is what
          stable-ts aligns to.
        - ``structure`` preserves header context for each surviving line.

        For non-Genius ``.txt`` and ``.srt``: behaves as today;
        ``structure`` is ``None``.
        """
        suffix = Path(lyrics_path).suffix.lower()
        if suffix == ".srt":
            raw = lyrics_path.read_text(encoding="utf-8")
            subs = list(srt.parse(raw))
            lyrics_text = "\n".join(sub.content for sub in subs)
            return lyrics_text, "srt", None
        else:
            raw = lyrics_path.read_text(encoding="utf-8")

            # Detection heuristic: presence of any section-header line
            header_re = re.compile(r"^\s*\[.*\]\s*$", re.MULTILINE)
            if header_re.search(raw):
                sections = parse_genius_sections(raw)
                if sections:
                    # Use align_text (inline parens stripped) for alignment
                    lyrics_text = "\n".join(line["align_text"] for line in sections)
                    return lyrics_text, "txt", sections

            # Plain .txt (no Genius headers)
            return raw, "txt", None

    def _generate_ass(self, line_objects: list[dict]) -> str:
        """Build .ass content from line objects using config styling/timing.

        Ported from snippets/stable_align.py:generate_enhanced_karaoke_ass.
        All styling/timing values come from self._config instead of
        module-level constants.
        """
        cfg = self._config
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
            f"Style: Karaoke,{cfg.font_name},{cfg.font_size},"
            f"{cfg.primary_color},{cfg.secondary_color},"
            f"{cfg.outline_color},{cfg.back_color},"
            f"0,0,0,0,100,100,0,0,1,"
            f"{cfg.outline_width},{cfg.shadow_offset},2,"
            f"{cfg.margin_left},{cfg.margin_right},{cfg.margin_vertical},1\n"
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
            # Tracking prev_end from here means the gap to the first word
            # automatically becomes the silent lead-in tag.
            prev_end = event_start
            parts = []

            for i, word_data in enumerate(words):
                word = word_data["word"]

                word_start = word_data["start"]
                # Apply first_word_nudge_cs: push back the first word of a
                # segment if it starts almost immediately after the previous
                # segment (within ~50ms of the expected lead-in gap),
                # preventing word clipping.
                if (
                    word_data.get("is_segment_first")
                    and abs(word_start - prev_end - cfg.line_lead_in_cs / 100.0) < 0.05
                ):
                    word_start += cfg.first_word_nudge_cs / 100.0

                word_end = word_data["end"]
                word_dur_cs = max(10, round((word_end - word_start) * 100))

                # Silent cursor advance through any gap before this word.
                # For the first word this gap = LINE_LEAD_IN_CS (the lead-in).
                # For subsequent words it covers natural pauses between words.
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
        ]
        return srt.compose(subtitles)

    @staticmethod
    def _should_write_srt(song_path: Path) -> bool:
        """Skip SRT generation when yt-dlp already provided one.

        Replaces the previous ``write_srt = lyrics_format == "txt"`` /
        ``write_srt = True`` assignments with a filesystem check,
        decoupled from input mode.
        """
        subs = song_path.parent / "subtitles"
        return not (
            (subs / f"{song_path.stem}.en.srt").exists()
            or (subs / f"{song_path.stem}.srt").exists()
        )


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


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format: H:MM:SS.cc (centiseconds)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)  # centiseconds
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
