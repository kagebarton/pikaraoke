"""Decode an existing vocal stem .m4a back to WAV for whisper input.

Used by the backfill CLI when the vocal/nonvocal m4a stems already
exist on disk but the karaoke .ass or subtitles .srt do not — skips the
expensive separator pass and feeds the cached vocal stem straight to
LyricAlignStage.
"""

import logging

from pikaraoke.pipeline.context import Phase, StageContext
from pikaraoke.pipeline.stages._ffmpeg_helpers import run_ffmpeg
from pikaraoke.pipeline.stages.base import BaseStage

logger = logging.getLogger(__name__)


class LoadVocalFromM4aStage(BaseStage):
    """Decode <song>/vocal/<stem>---vocal.m4a back to WAV in tmp_dir."""

    name = "load_vocal"

    def run(self, ctx: StageContext) -> None:
        vocal_m4a = ctx.song_path.parent / "vocal" / f"{ctx.song_path.stem}---vocal.m4a"
        if not vocal_m4a.is_file():
            raise FileNotFoundError(f"Vocal stem missing: {vocal_m4a}")

        vocal_wav = ctx.tmp_dir / f"{ctx.song_path.stem}_vocal.wav"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-i",
            str(vocal_m4a),
            "-ac",
            "2",
            "-ar",
            "44100",
            "-sample_fmt",
            "s16",
            str(vocal_wav),
        ]
        logger.info(f"[{self.name}] Decoding cached vocal stem: {vocal_m4a.name}")
        run_ffmpeg(cmd, ctx, Phase.EXTRACT)

        ctx.artifacts["vocal_wav"] = vocal_wav
        # LyricAlignStage only reads vocal_wav; instrumental is unused there.
        logger.info(f"[{self.name}] Vocal WAV ready: {vocal_wav.name}")
