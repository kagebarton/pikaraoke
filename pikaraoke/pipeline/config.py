from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODELS_DIR = str(_REPO_ROOT / "models")
_DEFAULT_MODEL = str(_REPO_ROOT / "models" / "large-v3-turbo.pt")


@dataclass
class LoadModelKwargs:
    """Splatted into ``stable_whisper.load_model(model_path, **rest)``.

    ``model_path`` is consumed positionally; everything else flows in
    as a kwarg.
    """

    model_path: str = _DEFAULT_MODEL
    device: str = "auto"  # 'auto' → 'cuda' if available else 'cpu'


@dataclass
class AlignKwargs:
    """Splatted into ``model.align(audio, text, **kwargs)`` — walk path.

    Walk mode uses a two-pointer matcher with gap interpolation, so
    we maximize anchor words (low ``min_word_dur``) and trust the
    matcher to interpolate between them.
    """

    language: str = "en"

    # Silero VAD pre-pass: gates whisper to voiced regions only.
    vad: bool = True
    vad_threshold: float = 0.05  # lower = more sensitive

    # Suppress timestamps in silent regions.
    suppress_silence: bool = True
    suppress_word_ts: bool = True

    # Restrict mel features to the human vocal range (~85-3000 Hz).
    only_voice_freq: bool = True

    # Word duration floor / ceiling. None = stable-ts default.
    min_word_dur: float = 0.1  # more anchor words for walk matcher
    max_word_dur: float | None = 5.0  # trust walk matcher interpolation

    # Drop zero-duration words instead of leaving 0-cs entries.
    remove_instant_words: bool = True

    # Treat each '\n' in alignment text as a segment boundary.
    original_split: bool = False

    # Abort alignment if zero-duration-word fraction exceeds this.
    failure_threshold: float | None = None

    # Skip non-speech regions (relies on VAD/suppress_silence accuracy).
    nonspeech_skip: float | None = None

    # Max tokens aligned per pass. Higher reduces misalignment risk.
    # None → stable-ts default (100).
    token_step: int | None = 150


@dataclass
class TranscribeKwargs:
    """Splatted into ``model.transcribe(audio, **kwargs)`` — transcribe path.

    No lyrics are supplied. Segment-level filters are relaxed because
    singing has lower per-token logprobs and higher compression ratios
    (chorus repetition) than speech, so speech-tuned defaults reject
    valid content.
    """

    language: str = "en"

    vad: bool = True
    vad_threshold: float = 0.05

    suppress_silence: bool = True
    suppress_word_ts: bool = True

    only_voice_freq: bool = True

    min_word_dur: float = 0.1

    word_timestamps: bool = True

    # Decoding
    temperature: float = 0.0
    beam_size: int = 5
    patience: float | None = 1.0
    length_penalty: float | None = 1.0

    # Whisper segment-level filters — relaxed for sung vocals.
    no_speech_threshold: float | None = 0.3  # was 0.6 — keep "uncertain" segments
    logprob_threshold: float | None = None  # was -1.0 — disable; trips on singing
    compression_ratio_threshold: float | None = 3.0  # was 2.4 — allow repeat-heavy choruses

    # False avoids hallucination/skip cascades when one segment goes wrong.
    condition_on_previous_text: bool = False

    # Optional text hint to guide style/vocab.
    initial_prompt: str | None = None


@dataclass
class RefineKwargs:
    """Splatted into ``model.refine(audio, result, **kwargs)`` — shared by both paths."""

    steps: str = "se"  # 's' = starts, 'e' = ends, 'se' = both
    word_level: bool = True


@dataclass
class PostProcessKwargs:
    """``WhisperResult`` post-processing applied after refine().

    Each field controls a separate call on the result object — these
    are NOT splatted into one method:
      * ``adjust_gaps_threshold`` → ``result.adjust_gaps(duration_threshold=)``
      * ``merge_by_gap_min``      → ``result.merge_by_gap(min_gap=)``
      * ``min_word_probability``  → filter inside ``_extract_words``

    Used as two independent instances on ``WhisperModelConfig`` —
    ``align_post_process`` and ``transcribe_post_process`` — so each
    path can tune the thresholds independently.
    """

    # Word probability floor used by _extract_words. Words below this
    # are silent-region hallucinations clustered at zero-duration
    # timestamps. 0 disables the filter.
    min_word_probability: float = 0

    # Merge words closer than this. None disables.
    adjust_gaps_threshold: float | None = None

    # Merge tiny adjacent segments. None disables.
    merge_by_gap_min: float | None = None


# Stable-ts regroup expression for the transcribe path.
# Methods chained with "_"; args follow "=". Shortcuts:
#   cm = clamp_max, sp = split_by_punctuation, sg = split_by_gap,
#   mg = merge_by_gap (min_gap+max_words).
_DEFAULT_REGROUP = "cm_sp=.* /,/?/!/。_sg=.3_mg=.2+5"


@dataclass
class WhisperModelConfig:
    """Top-level whisper config — one section per stable-ts call.

    All defaults are baked into the section dataclasses. Instantiating
    ``WhisperModelConfig()`` produces a fully-tuned config — the walk
    path reads ``align``, the transcribe path reads ``transcribe`` and
    ``regroup``, both paths share ``load_model`` and ``refine``, and
    each path has its own post-process section.

    To tune a value, edit the default on the relevant section dataclass.
    To add a new stable-ts kwarg, add a field to the matching section —
    no worker edit required.
    """

    load_model: LoadModelKwargs = field(default_factory=LoadModelKwargs)
    align: AlignKwargs = field(default_factory=AlignKwargs)
    transcribe: TranscribeKwargs = field(default_factory=TranscribeKwargs)
    refine: RefineKwargs = field(default_factory=RefineKwargs)
    align_post_process: PostProcessKwargs = field(default_factory=PostProcessKwargs)
    transcribe_post_process: PostProcessKwargs = field(default_factory=PostProcessKwargs)

    # Used by the transcribe path only; ignored by the walk path.
    regroup: str = _DEFAULT_REGROUP


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

    # --- Lyric match method ---
    # "walk" — stable-ts align() + two-pointer walk matcher with gap
    #   interpolation. Trusts word order; covers every lyric line.
    # "tiling" — stable-ts transcribe() + order-independent fuzzy
    #   candidate + interval-scheduling DP. Resilient to
    #   remixes/repeats/drift; may drop unmatched lines.
    # "joint" — align + transcribe (no internal refine) fed simultaneously
    #   into a single interval-scheduling DP. Each lyric line scores its
    #   align candidate AND its transcribe candidates; the DP picks the
    #   max-score non-overlapping subset. Per-word timings come from
    #   whichever source won each line — align's refined timings on
    #   clean lines (preserving walk-level precision) and transcribe's
    #   word_timestamps on lines align misplaced. No routing/gating
    #   layer; one matcher covers walk-clean, align-collapse, and
    #   walk-against-wrong-audio (Hakuna-style) failure modes uniformly.
    # "auto" (default) — run walk, but if stable-ts align() fails more
    #   than ``align_failure_escalation`` of its segments, discard the
    #   align result and re-run with the tiling matcher on an honest
    #   transcription. The escalation happens *before* the refine pass,
    #   so a discarded align doesn't pay for refine.
    match_method: str = "auto"

    # Fraction of stable-ts align() segments that must fail before the
    # "auto" gate escalates to the tiling matcher. 0.1 → escalate at >10%
    # (e.g. 7/48 ≈ 0.15 triggers).
    align_failure_escalation: float = 0.1

    # Complementary escalation signal: fraction of lyric tokens caught by
    # the walk matcher's collapse demotion (stable-ts force-placing many
    # tokens at a single timestamp, looking like alignment success at the
    # segment level but garbage at the word level). Computed from a quick
    # walk on the pre-refine word list — refine doesn't add or remove
    # tokens, so the collapse pattern is preserved. 0.15 → escalate at
    # >15% (e.g. Pocahontas "Colors of the Wind" hits 0.35 here while its
    # fail_ratio is only 0.07 — collapse catches what fail_ratio misses).
    collapse_escalation_threshold: float = 0.15

    # --- Joint-matcher knobs (used only when match_method == "joint") ---

    # Weight on the align prior in the joint scoring formula:
    #   score = transcribe_match + joint_alpha * align_agreement
    # Roughly the number of "free" matched-token credits an align
    # candidate gets just by being where forced alignment placed the
    # line. Higher → trust align more (regress toward walk on clean
    # songs); lower → trust transcribe more (regress toward tiling).
    # 4.0 is the design prior (≈ one short line of free credit) pending
    # the α-sweep on the 23-song corpus called for in the plan.
    joint_alpha: float = 4.0

    # Time slack on each side of a candidate window when deciding which
    # transcribe words count as "inside" for transcribe_match scoring,
    # and how much collapsed align candidates get padded for the DP's
    # non-overlap constraint. Reuses the previous repair-margin value.
    joint_margin_s: float = 0.3

    # When True, the lyric-align stage writes a JSON bundle to
    # ``<song_dir>/alignment_debug/<stem>.json`` capturing the matcher
    # inputs (whisper words + lyric lines), the knob values that ran,
    # and per-pass telemetry. Used for offline tuning of the walk/tiling
    # knobs (see pikaraoke.lib.alignment_capture). Cheap (~50–200 KB/song)
    # and easy to wipe; flip off once the corpus is sufficient.
    capture_alignment_debug: bool = True

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

    # --- FFmpeg transcoding ---
    aac_quality: str = "2"  # ≈ 128 kbps VBR AAC
    ffmpeg_threads: str = "4"
