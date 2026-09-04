# Glossary of technical terms used in the plans

High-level explanations of the acronyms and jargon that appear across the
files in `plans/`. Terms are grouped by theme; within each group they are
alphabetical. Cross-references are written as `→ <term>`.

## Audio / alignment core

- **ASS** — Advanced SubStation Alpha subtitle format (`.ass`). The karaoke
  output the pipeline writes; supports per-word highlight timing so the
  singer sees a sweeping fill as the song plays. `generate_ass` in the
  pipeline builds it from `line_objects`.
- **CTC (Connectionist Temporal Classification)** — a neural-network
  training/decoding scheme that maps an audio sequence to a shorter token
  sequence without pre-aligned labels. In this project it powers
  *forced alignment*: given the audio and the known transcript, the CTC
  model says (roughly) which frame each word starts and ends on. See
  also → MMS_FA.
- **Emission** — the per-frame probability distribution over the model's
  vocabulary that a CTC model outputs. Sliced and re-decoded cheaply to
  align windows; orbiting everything in the engine branch. "Emission
  oracle" / "score oracle" = using the emission to score any hypothesized
  timing.
- **Forced alignment** — given audio and a transcript, find each word's
  start/end time. The pipeline does this with two aligners: → whisper
  (`align_refine`) and → MMS_FA (CTC).
- **Melisma** — one syllable of lyric text sung over many notes (e.g.
  "o-o-oh"). Hard for whisper because the phonetic content stops while the
  note keeps sounding; the end-snap feature was built to recover these.
- **Onset / end-of-line snap** — post-passes in `onset_snap.py` that repair
  whisper's two systematic line-edge errors by reading the vocal stem's
  RMS loudness curve: onset snap pulls a smeared-back first word forward
  to the real rise; end snap extends a clipped held final word through to
  where the note fades. Both are forward/extend-only and bounded, so they
  can never make a correct line worse.
- **Stem** — the isolated vocal track from a song (extracted by the stem
  worker). "Wet stem" = the raw separated vocal; "dry stem" / "dereverb
  stem" = the same after the de-reverb gate removes reverb. Alignment
  typically runs on whichever stem the de-reverb gate chose.

## Lyric / timing sources

- **Genius (sheet)** — the Genius lyrics page the user picks at download
  time; provides plain text lines (no timing). The "sheet" every route
  renders or maps onto.
- **LRCLIB** — a synced-lyrics community database returning line-level
  LRC. Permanently out of the matcher/DP path by ruling; used only (a)
  held-out scoring reference for the tuning harness, and (b) gated fill
  of matcher-unplaced lines per `lrclib-fill-absence-study.md`.
- **LRC** — plain line-timed lyrics format (`[mm:ss.xx] line`). "Line
  LRC" or "line timing" = one timestamp per line; "enhanced LRC" with
  inline `<mm:ss.xx>` word tags = word timing.
- **NetEase** — a second synced-lyrics catalog reachable through
  `syncedlyrics`. The installed provider only returns line-level LRC
  (its `yrc` word-level field is not parsed), so NetEase is treated as
  line-only fallback when Musixmatch misses.
- **MMS_FA** — the specific torchaudio CTC forced-alignment model
  (`torchaudio.pipelines.MMS_FA`) used for the CTC probe and engine.
  Latin charset only (MMS = Massively Multilingual Speech), so non-Latin
  lines need an ASCII-fold/fallback path.
- **Musixmatch richsync** — Musixmatch's word-level timing format. Each
  line carries `ts`/`te` (line start/end) and a word list with per-word
  offsets. Sampled via the `syncedlyrics` package. The only large free
  source of human-authored word timing.
- **SRT** — the SubRip subtitle format (`.srt`). Uploader SRT captions
  are trusted line cues for the SRT cue-align route; the pipeline's own
  generated SRTs are marked with a `.srt.generated` sidecar so they
  cannot be mistaken for uploader captions. → provenance marker.
- **Stanza** — a structural unit in a lyric sheet (verse/chorus block),
  separated by blank lines or `[Verse]/[Chorus]` headers. `parse_lyric_lines`
  historically discarded these breaks; preserving them is a prerequisite
  for any transition-cost DP that knows where gaps are plausible.
- **syncedlyrics** — a Python package wrapping several providers'
  (Musixmatch, NetEase, …) synced-lyric APIs. Used by the coverage probes
  and the E0 timing-fetch pillar.

## Statistics / metrics

- **AUC** — Area Under the (ROC) Curve. A single number (0–1) summarizing
  how well a statistic separates two classes; 0.5 = random, 1 = perfect.
  Used at GATE O to judge whether an emission score cleanly separates
  synced vs desynced lines.
- **MAD (Median Absolute Deviation)** — a robust spread measure:
  `median(|x_i − median(x)|)`. Used everywhere as the gate statistic
  for fit quality (scaffold warp, offset fit, fill gates) because it
  ignores a few outlier anchors instead of blowing up like standard
  deviation. `WARP_MAD_GATE_S`, `PRIOR_MAX_MAD_S` are MAD-based thresholds.
- **Map-rate (map_rate)** — fraction of the lyric sheet's lines that a
  candidate's LRC text maps to via `map_lines_to_cues` (a monotone 1:1
  line mapper). The candidate-quality key used to pick among Musixmatch
  /NetEase candidates; `< 0.5` is treated as wrong-song.
- **Monotonic / monotone** — in this codebase, "ordered, non-decreasing."
  A *monotone assignment* of words to tokens preserves order in both
  streams (the DP in `match_words_to_tokens` maximizes matches subject
  to that constraint). A *monotonic DP* refuses to reorder lines, which
  is a chorus-steal defense but can cost on genuinely reordered sections.
- **Offset fit / constant-offset gate (arm A)** — fit `placed_start =
  cue_start + offset` (slope fixed at 1.0) over trusted anchors, judge
  by MAD. The production-shaped LRCLIB gate; bails `wide_spread` /
  `few_anchors`.
- **Residual** — observed minus predicted value for one anchor in a fit.
  Per-line |residual| distributions and p50/p90/max are reported to judge
  whether a fit is trustworthy vs. driven by a few outliers.
- **Re-pace %** — fraction of lines whose timing the aligner had to
  re-space (rescue) because the original placement failed. Lower is
  better; a headline corpus metric alongside worst-overlap and flags.
- **RMS envelope (dB)** — a frame-by-frame loudness curve of the vocal
  stem, decoded once and reused by the snap post-passes and the energy
  veto. Roughly "how loud is the voice at time *t*."
- **Slope (tempo)** — in the affine model `placed = slope * cue + intercept`,
  `slope` is the tempo ratio between the external timing source and the
  audio. Near 1.0 = same tempo; far from 1.0 (e.g. Defying Gravity 0.79)
  = different recording.
- **Theil-Sen fit** — a robust linear regression: the slope is the
  median of all pairwise slopes, so a few bad anchors don't corrupt it.
  Used for the scaffold warp (`warp_scaffold_cues`) and the LRCLIB arm-B
  (reach) gate; contrasts with least-squares which is outlier-sensitive.
- **Worst-overlap** — the largest rendered-line overlap (seconds) on a
  song; the main "are two lines highlighting at once" metric. A headline
  corpus quality metric.
- **z-normalization (robust, per-song)** — subtracting the median and
  dividing by the MAD across a song's word scores so thresholds are
  comparable across songs with different absolute score scales.

## Architecture / routing

- **Align candidate / align route** — in the joint matcher, a line's
  placement derived from the forced-aligner's word timings (whisper's
  `align_refine` or CTC). Scores `alpha` and a graded self-evidence
  (`align_agreement`).
- **Anchor** — a line whose placement is trusted enough to fit a timing
  transform against. Selected by `analyze_pass1` from corroborated
  placements; anchors drive the offset/Theil-Sen warp that maps an
  external timing source onto the audio clock.
- **Bail / bail label** — when a gate rejects a fit it reports a reason
  string (`bail:wide_spread`, `bail:no_reference`, `bail:few_anchors`).
  Routes degrade rather than failing the song.
- **Bundle (alignment_debug bundle)** — a per-song JSON captured by
  `alignment_capture` holding the inputs and inferred outputs of one
  pipeline run (lyrics, align words, transcribe words, ytasr, stats).
  The corpus the harnesses replay from.
- **Catch-all (joint) route** — the bottom-of-the-ladder flow for songs
  with no uploader SRT and no matching external synced timing: the joint
  multi-witness DP on the Genius sheet plus windowed re-align.
- **Corroboration / corrob_ratio** — independent agreement on a line's
  placement from a *second* source (transcribe words, ytasr words) beyond
  the one that placed it. `corrob_ratio = matched/len(seq)`; high-ratio
  interior lines are protected from being overwritten by a lower-context
  replay.
- **Cue / cue span** — a `(start, end)` time window a line belongs to,
  from SRT cues, LRCLIB, or densified anchors. The scaffold path aligns
  text *inside* its cue window via → slice_align.
- **Densify** — turning sparse anchors into a complete cue span set by
  linear interpolation across gaps. Fallback in `warp_scaffold_cues`
  when the warp fit fails.
- **De-reverb (gate)** — a stage that, on poor-quality separated vocals,
  swaps the wet stem for a de-reverbed variant before alignment. The gate
  fires on a quality signal; downstream paths read `ctx.artifacts["aligned_stem"]`.
- **DP (dynamic programming)** — the joint matcher's placement engine:
  `_best_tiling_by_time` picks a non-overlapping, order-preserving set of
  line placements maximizing total score. The "transition-cost DP" Phase 6
  considers would add a penalty for implausible gaps between adjacent
  placements.
- **Engine branch (E1–E5)** — the build path under `plans/ctc-sync-engine.md`
  where a single CTC sync engine (emission oracle + score gate + guided
  windowed CTC) backs every non-SRT route. Licensed by GATE O = O-1
  (or O-1′) **and** GATE S S-5 = engine. Currently OFF (S-5 =
  scaffold-first by rule).
- **Evidence veto** — a post-pass (`evidence_veto.py`) that demotes
  zero-corroboration align-won lines (a) over digital silence (Phase 3b)
  and (b) over loud non-lyric singing via counter-evidence (Phase 4.5).
  Demote-only; never moves a line.
- **Fallback branch (F1/F2)** — the build path the engine plan falls back
  to: F1 = verified-richsync word route; F2 = scaffold cue-align route with
  a whisper/CTC `slice_align` per GATE S S-2. Currently active
  (S-5 = scaffold-first).
- **GATE (marker)** — a hard stop in the plans where the executor reports
  numbers and a judge/Ken rules before work proceeds. Each GATE has a
  pre-registered mechanical read-off rule (e.g. GATE O, GATE R, GATE S,
  GATE X, GATE J1, GATE L1) plus a gray zone for Ken.
- **Guided windowed CTC** — using an external timing prior (richsync,
  LRC, or scaffold anchors) to define windows, then running CTC forced
  alignment inside each window via emission slicing. The engine plan's
  word/line-route mechanism.
- **Joint matcher** — the multi-witness DP over three sources
  (align-words / transcribe / ytasr) that places Genius-sheet lines on
  songs with no SRT. Routing + windowed re-align + evidence veto.
- **Phantom line** — a line rendered onto audio where it isn't actually
  sung (different lyric version, instrumental gap, wrong mix). The core
  failure class the matcher-hardening, evidence veto, and LRCLIB absence
  study all attack.
- **Prior (timing prior)** — an external timing source used to supply
  approximate locations (richsync, LRC, anchors) so CTC or whisper only
  has to refine inside a window, not search the whole song. Priors
  supply text/structure/window, never final on-clock timing.
- **Provenance marker** — the `<stem>.srt.generated` sidecar file that
  marks a `subtitles/<stem>.srt` as pipeline-generated (not an uploader
  caption) so it isn't mis-adopted on regen or counted wrongly in ground
  truth. See `plans/completed/srt-provenance-marker.md`.
- **Section / segment_by_gaps** — `cue_align`'s step that splits an SRT
  cue list into alignment sections at gaps > `SECTION_GAP_S`. Sections
  become → slice_align windows; `MAX_SECTION_DUR_S` caps runaway
  single-section drift on padded-cue SRTs.
- **Sidecar** — a small JSON file beside a song holding a fetched result
  (e.g. `lyrics/<stem>.timing.json` for Musixmatch/NetEase timing,
  `lyrics/<stem>.lrc` for LRCLIB). Disk-first reuse-on-disk contract;
  one fetch per song, no refetch unless corrupt.
- **Slice_align** — the per-section contract `(t0, t1, text, label) ->
  words | None`: align the text inside a window. Both whisper (via
  ffmpeg-sliced `WhisperWorker.align_refine`) and CTC (via emission
  slicing) implement it; the S-B arm proved the contract works for both.
- **Transcribe** — whisper's *transcription* pass (not forced alignment):
  outputs free-decoded words + probabilities over the whole stem. Used as
  independent evidence for anchors, verify, and the de-reverb gate.
- **Warp / warp_scaffold_cues** — mapping an external (foreign-clock)
  line-timing source onto the audio clock by fitting slope+offset
  (Theil-Sen) over trusted-anchor pairs. New rescue tier: when the affine
  fit fails, try constant-offset (slope=1.0) before densify.
- **Windowed re-align** — a repair pass over suspected spans: re-run a
  sub-match on each span's window using the captured align/transcribe/
  ytasr words, then merge results back. Phases 4a (3rd source) and 4b
  (corroborated-line protection) revised it.

## Workflow / process

- **Executor discipline** — the rules binding whoever implements a plan:
  specs are contracts (a mismatch is a STOP, never a bridge); every
  Results-log number comes from a command actually run in that session;
  pre-registered protocols/thresholds never move after seeing data;
  "unchanged" claims require a real diff; GATEs/MODEL BREAKs are hard stops.
- **Fable / Opus / Sonnet (roles)** — the three model roles in the plans'
  "Model switching": **Design** (Fable, locked; Opus drafts if Fable
  unavailable), **Implement/run** (Sonnet 5), **Judge results** (Opus,
  escalate to Fable on ambiguity). Escalations that previously said "to
  Fable" now go to Ken (Fable became unavailable 2026-07-19).
- **Fork rule** — new behavior goes in new files; smallest possible touch
  to existing modules. Keeps changes reviewable and avoids circular
  imports (e.g. `joint_match` may not import `cue_align`; `token_align`
  imports from neither).
- **Honest abstention** — the design principle that a route may decline
  to place a line rather than guess. Opposite of blanket interp-render,
  which the hardening plan rejects (~70% wrong).
- **Pre-registered (protocol / criterion / read-off)** — a decision rule
  fixed *before* seeing the data it's applied to, so thresholds can't be
  tuned to a result. The judge "executes the procedure verbatim"; an
  uncovered case is a STOP → Ken, never a model invention.
- **Replacement path + gated cutover** — the build strategy for shipping
  the new engine: build alongside the existing stack (never modify it in
  place), parallel A/B on the full corpus, then one commit flips routing
  and only afterward delete the old modules.
- **Scratchpad** — session-local throwaway scripts/outputs, never
  committed. Two named exceptions persist in-repo
  (`scripts/musixmatch_coverage_improve.py`, the Phase 0 harness port);
  everything else is reproduced from the plan when needed.
