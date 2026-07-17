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
    """Splatted into ``model.align(audio, text, **kwargs)``.

    Forced alignment is the joint matcher's align-candidate source. The
    matcher pairs lyric tokens to words with gap interpolation, so we
    maximize anchor words (low ``min_word_dur``) and trust it to
    interpolate between them.
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
    min_word_dur: float = 0.1  # more anchor words for the joint matcher
    max_word_dur: float | None = 5.0  # trust matcher gap interpolation

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

    steps: str = "s"  # starts only; halves refine vs "se"
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
    ``WhisperModelConfig()`` produces a fully-tuned config — the align
    pass reads ``align``, the transcribe pass reads ``transcribe`` and
    ``regroup``, both share ``load_model`` and ``refine``, and each has
    its own post-process section.

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

    # Used by the transcribe pass only; ignored by the align pass.
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

    # --- Joint matcher ---
    # Alignment runs stable-ts align() + refine and an independent
    # transcribe() pass, then feeds both placements into a single
    # interval-scheduling DP (pikaraoke.lib.joint_match). Each lyric line
    # scores its align candidate AND its transcribe candidates; the DP picks
    # the max-score non-overlapping subset. Per-word timings come from
    # whichever source won each line — align's refined timings on clean
    # lines, transcribe's word_timestamps on lines align misplaced. One
    # matcher covers clean songs, align-collapse, and align-against-wrong-
    # audio (Hakuna-style) failure modes uniformly.

    # Weight on the align prior in the joint scoring formula:
    #   score = transcribe_match + joint_alpha * align_agreement * alpha_weight
    # Roughly the number of "free" matched-token credits an align
    # candidate gets just by being where forced alignment placed the
    # line. Higher → trust align more (all-align on clean songs); lower
    # → trust transcribe more (all-transcribe on misaligned songs).
    # Corpus-tuned: 2.0 from the 27-song α-sweep. The design prior
    # was 4.0; the sweep
    # showed α=4 keeps Hakuna Matata's late lyrics misplaced into the
    # dialogue region (the DP prefers an all-align chain with α=4's
    # bonus), while α=2 routes them correctly to the sung reprise.
    # Corpus aggregate moves by ~30 lines / 1639 (≈2%) between α=2 and
    # α=4 — most songs are insensitive in that range.
    joint_alpha: float = 2.0

    # Weight on the YTASR agreement term in the joint scoring formula,
    # symmetric to joint_alpha. Only affects songs whose YouTube ASR caption
    # was adopted as the third candidate source; absent, ytasr_agreement is 0
    # and this has no effect. Corpus-tuned: 2.0 from the 16-song
    # YTASR-third-source sweep (see plans/ytasr-third-source-experiment.md).
    joint_beta: float = 2.0

    # Time slack on each side of a candidate window when deciding which
    # transcribe words count as "inside" for transcribe_match scoring,
    # and how much collapsed align candidates get padded for the DP's
    # non-overlap constraint. Reuses the previous repair-margin value.
    joint_margin_s: float = 0.3

    # Edit-distance gate for transcribe candidate generation: windows
    # whose normalized edit ratio against the lyric line exceeds this
    # are never candidates. Whisper mishears sung vocals often, so a
    # strict gate rejects weak-but-correct matches the DP score would
    # have ranked fine anyway. The held-out caption eval showed
    # 0.25 -> 0.75 lifts placed
    # coverage 85.6% -> 89.4% with median residual improved and gross
    # misplacements unchanged; coverage saturates at 0.75.
    joint_max_edit_ratio: float = 0.75

    # Second pass for the joint matcher: spans between trusted pass-1
    # anchors whose interior holds a suspect line (unplaced or weakly
    # corroborated) are re-aligned in isolation — the audio slice plus
    # only that span's lyric lines — and merged back conservatively
    # (see pikaraoke.lib.windowed_realign). Corpus-measured (Phase 3):
    # gross misplacements 77 -> 58
    # across 23 songs. GPU cost: zero on fully-corroborated songs, up
    # to ~2x the align+refine leg on suspect-heavy ones (corpus mean:
    # 46% of song audio re-aligned).
    joint_windowed_realign: bool = True

    # Gated LRCLIB fill (E1, plans/lrclib-fill-absence-study.md Phase L4):
    # on the joint route, lines the matcher leaves unplaced are filled at
    # LRCLIB-cue-plus-offset times, iff the song's own audio-vs-LRCLIB
    # tempo/arrangement-consistency gates pass (see pikaraoke.lib.
    # lrclib_fill.plan_fills). Fill-only: LRCLIB is never a matcher/DP
    # candidate source. Covers both the LyricsFetchStage fetch leg and the
    # LyricAlignStage fill hook. Ships on -- every unsafe case is caught by
    # the gates (that is what the study validated).
    lrclib_fill: bool = True

    # De-reverb retry for the joint route. When the whole-stem transcribe
    # yield falls below this many words per minute, the vocal stem is
    # treated as reverb-washed: the stem worker swaps to the de-reverb
    # roformer, de-reverbs the stem, and transcribe re-runs on the dry
    # stem (then adopted for the single align pass; any failure keeps the
    # wet-stem result). Corpus evidence: the one reverb-washed song yields
    # 14.4 wpm; every other song >= 50.5.
    # 0 disables the retry.
    dereverb_yield_wpm: float = 30.0

    # Same MelBand Roformer family and size as the karaoke model, so the
    # swap never exceeds today's proven VRAM peak. Keep the ckpt
    # pre-downloaded in models/ — a missing file means a 913 MB fetch in
    # the middle of the first gated song.
    dereverb_model_name: str = "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt"

    # When True, a successful de-reverb retry persists its dry stem to
    # ``<song_dir>/dereverb/<stem>---dereverb.m4a`` and a later retry reuses
    # it instead of re-separating. Off for the live app (the dry stem is
    # ephemeral there); the bundle-regen tool flips it on so repeated regens
    # of a reverb-washed song pay the de-reverb separation only once.
    cache_dereverb_stem: bool = False

    # When True, the lyric-align stage writes a JSON bundle to
    # ``<song_dir>/alignment_debug/<stem>.json`` capturing the matcher
    # inputs (whisper words + lyric lines), the knob values that ran,
    # and per-pass telemetry. Used for offline tuning of the joint matcher
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
