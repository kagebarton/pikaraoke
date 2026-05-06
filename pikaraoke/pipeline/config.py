from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODELS_DIR = str(_REPO_ROOT / "models")


@dataclass
class WhisperModelConfig:
    # --- Model loading ---
    model_path: str = str(_REPO_ROOT / "models" / "large-v3-turbo.pt")
    device: str = "auto"

    # --- Language / VAD ---
    language: str = "en"
    vad: bool = True
    vad_threshold: float = 0.1  # lower = more sensitive; 0.1 catches soft vocals

    # --- Silence handling ---
    # False: preserve timing in quiet regions (breathing, held pauses between phrases).
    # On a pre-separated vocal stem there is no background noise to suppress.
    suppress_silence: bool = False
    suppress_word_ts: bool = False  # keep word-level timestamps in quiet regions

    # --- Frequency filtering ---
    # True: restrict mel features to the human vocal range (~85–3000 Hz).
    # Always beneficial on a vocal stem — removes any residual low-frequency bleed.
    only_voice_freq: bool = True

    # --- Transcription decoding ---
    temperature: float = 0.0  # 0 = greedy/deterministic; best for alignment accuracy
    beam_size: int = 5  # beam search width for transcription
    condition_on_previous_text: bool = False  # False prevents hallucination drift in long songs
    initial_prompt: str = ""  # optional text hint to guide transcription style/vocab

    # --- Word duration floor ---
    # 0.05 s allows short syllables in fast lyrics (default stable-ts is 0.1 s).
    min_word_dur: float = 0.025

    # --- Refinement ---
    refine_steps: str = "se"  # 's' = refine starts, 'e' = ends, 'se' = both
    refine_word_level: bool = True

    # --- Regrouping (transcription mode only) ---
    regroup: str = ""  # stable-ts regroup expression; empty = no regrouping


@dataclass
class PipelineConfig:
    # --- Model paths ---
    separator_model_dir: str = _MODELS_DIR
    separator_model_name: str = "vocals_mel_band_roformer.ckpt"

    # --- Intermediate files directory ---
    intermediate_dir: str = ""  # Empty = system temp dir; adapter resolves via get_temp_directory()

    # --- Loudnorm targets ---
    loudnorm_target_i: float = -24.0  # Target integrated loudness (LUFS)
    loudnorm_target_tp: float = -2.0  # Target true peak (dBTP)
    loudnorm_target_lra: float = 7.0  # Target loudness range (LU)

    # --- Whisper alignment options ---
    whisper: WhisperModelConfig = field(default_factory=WhisperModelConfig)

    # --- ASS styling ---
    font_name: str = "Arial"
    font_size: int = 60
    primary_color: str = "&H00D7FF&"  # Soft Yellow
    secondary_color: str = "&H00FFFFFF"  # White (not yet sung)
    outline_color: str = "&H00000000"  # Black outline
    back_color: str = "&H80000000&"  # Translucent shadow
    outline_width: int = 3
    shadow_offset: int = 2
    margin_left: int = 50
    margin_right: int = 50
    margin_vertical: int = 150

    # --- Karaoke timing (centiseconds) ---
    line_lead_in_cs: int = 80
    line_lead_out_cs: int = 20

    # --- Speaker diarization colors palette ---
    # Per-speaker colors for multi-speaker karaoke ASS output.
    # Index 0 → first dominant_speaker seen, etc.
    # Format: &HAABBGGRR& (8 hex digits, alpha + reversed RGB, trailing &).
    #
    # Ordering rule: every consecutive pair must be visually distinct so
    # that a 2-singer duet, 3-singer trio, etc. all read as obviously
    # different colors. RGB primaries lead (muted cyan / red / green — each
    # complementary to the next), then the secondaries are interleaved so
    # the two pinks are never adjacent.
    speaker_colors: list = field(
        default_factory=lambda: [
            "&H00A8A800&",  # 0 — muted cyan
            "&H003232B4&",  # 1 — muted red
            "&H0028D28C&",  # 2 — muted lime (more green)
            "&H00A03264&",  # 3 — muted plum (more purple, darker)
            "&H006E82A0&",  # 4 — muted sage
            "&H006464C8&",  # 5 — muted dusty rose
        ]
    )
    ensemble_color: str = "&H0000D7FF&"  # goldenrod for unlabeled lines

    # --- FFmpeg transcoding ---
    aac_quality: str = "2"  # ≈ 128 kbps VBR AAC
    ffmpeg_threads: str = "4"
