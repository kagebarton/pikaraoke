# Matcher Timing Eval + Accuracy Roadmap

Model: Claude Fable 5

Goal: maximize joint-matcher timing accuracy across the whole corpus, not just
the hand-curated troublesome songs. Four phases; this plan tracks 1–3 (4 is
contingency).

## Ground truth: YouTube manual captions

LRCLIB timings proved inaccurate; no other line-timing database is reliable.
The chosen truth source: YouTube **manual** subtitle tracks (the downloader
passes `--write-subs` without `--write-auto-subs`, so every downloaded SRT is
human-uploaded; official channels time them professionally).

Design: for songs whose lyric source *was* the YT SRT (`yt_is_source=True` in
the debug bundle), the matcher consumed the SRT **text** while
`_load_lyrics` provably discarded the cue **timings**. Comparing matcher
output timings to cue timings is therefore a held-out, text-identical, pure
timing evaluation.

Known confounds and mitigations:

| Confound | Mitigation |
| --- | --- |
| Subtitle display lead (cues start before vocals) | Fit one global offset per song (median of per-line deltas); score residuals |
| Pipeline-written SRTs masquerade as YT captions (same `subtitles/<stem>.srt` name; capture's `youtube_srt_present` is self-contaminated) | Verify provenance upstream via yt-dlp metadata per video ID; cache results |
| Selection bias toward clean official videos | This corpus measures *accuracy*; the 10 hand-verified baselines in /home/ken/Videos remain the *regression* suite |
| Cleanup drift between capture time and eval time | Map bundle lines to SRT cues by sequence matching on text, not by position |

## Phase 1 — eval harness

- `pikaraoke/lib/alignment_eval.py`: pure logic — line→cue mapping
  (difflib over cleaned cue texts vs bundle lines), median offset fit,
  residual metrics (median |Δt|, % within 0.5 s / 1.0 s, gross >2 s count),
  joint-matcher replay from a bundle at arbitrary knob values.
- `scripts/eval_alignment.py`: CLI — discovers eligible songs (bundle with
  `source_kind == "srt"` + verified upstream manual captions), replays the
  matcher (or `--as-run` to score `output_line_timings`), prints per-song +
  corpus table, `--json` for sweep diffing. Provenance cache:
  `<songs_dir>/alignment_debug/yt_subtitle_provenance.json`.
- Unit tests for mapping/offset/metrics in `tests/unit/test_alignment_eval.py`.
- Deliverable: baseline numbers on the eligible corpus (~8 songs today).

## Phase 2 — cheap knob sweeps (measured against Phase 1 harness)

1. `initial_prompt` on the transcribe pass (song-specific vocabulary).
2. Temperature fallback schedule vs fixed 0.0.
3. Word-probability retention (`_extract_words` currently drops
   `word.probability`) + probability-weighted `transcribe_match`/gate.
4. `large-v3` vs `large-v3-turbo` A/B.

Items 1, 2, 4 need fresh whisper passes per config (GPU time); item 3 needs a
worker+matcher change plus one fresh pass to capture probabilities.

## Phase 3 — windowed re-align two-pass

Forced alignment's catastrophic mode is global desync. After the joint DP
selects high-confidence placements, re-run `align()` on the audio slice
between consecutive anchors with only the unplaced lines belonging there.
Converts interp/absent lines into real placements. Gate adoption on Phase 1
metrics + the regression suite.

## Phase 4 (contingency) — CTC forced aligner as third timing source

Only if the harness shows headroom after Phases 2–3.

## Status ledger

| Step | State |
| --- | --- |
| Plan written | done |
| Provenance verification | done — 10/10 SRT-sourced songs have manual EN captions upstream |
| Eval lib + tests | done — 17 tests, suite 1018 passed |
| Eval CLI | done — replay + --as-run modes |
| Baseline numbers | done — see below |
| Phase 2a: replay knob sweep | done — max_edit_ratio 0.25 → 0.75 shipped; α/margin/fallback confirmed |
| Phase 2b: probability weighting | done — rejected by measurement (flat at every exponent); corpus refreshed with probabilities |
| Corpus expansion: LRCLIB refs | done — 14 non-SRT songs added; corpus now 23 songs / 989 lines |
| De-reverb experiment | done — corpus-validated; ship as gated retry (transcribe yield < ~30 words/min), not always-on |
| De-reverb pipeline integration | done — gated retry shipped (stem-worker model swap + lyric_align yield gate < 30 wpm); Bubble end-to-end verify: 14.4 → 43.5 wpm, 13/13 lines placed, dereverb demix peak 2132 ≤ karaoke 2190 MiB, combined two-worker peak 5378 MiB |
| Phase 2c: GPU sweeps (initial_prompt, temp fallback, model A/B) | done — all decode knobs rejected (prompt/temp flat; conditioning harmful, 77 → 106 gross); large-v3 A/B is a real win (gross 77 → 60, median 0.34 → 0.27 s) but needs +1 GB VRAM and 3-4× wall-clock — not deployable on the 2060, parked |
| Homoglyph fold + fuzzy cue mapping | done — Paradise's 7 "gross" were an eval mapping artifact; new baseline below |
| Phase 3 | done — windowed re-align promoted: lib/windowed_realign.py + lyric_align hook + 24 tests; corpus gross 77 → 58; GPU cost 0 on clean songs, up to ~2× align+refine on suspect-heavy (mean 46% of audio) |
| Phase 4: SRT timing prior | done 2026-06-12 — shipped: lib/srt_prior.py + lyric_align hook + eval `--srt-prior` + 9 tests; measured vs held-out LRCLIB (For Good excluded as circular): corpus gross **75 → 50** across 22 songs, scored 867 → 880, ≤1.0 s 82.9% → 85.7%, no song regressed, zero bail-outs (anchor MAD 0.20–0.48 s), zero GPU cost; Mirrors 24 → 3 gross (22 snapped + 11 filled — the chant outro renders); remaining gross dominated by LRCLIB reference noise — details in plans/srt-timing-prior.md |
| Phase 5: LRCLIB timing prior (txt-sourced songs) | plan sketched 2026-06-12, nothing started — txt songs hold ~35–40 of the remaining 50 gross; measurement-first (step 1: auto-search probe vs the 24 hand-fetched files; step 2: LRCLIB-as-input ceiling on the srt-sourced testbed, judged by YT SRT); requires re-opening the LRCLIB verification-only constraint before any production wiring — plans/lrclib-timing-prior.md |

## Baseline (2026-06-10)

Corpus: 8 songs replayable (9 as-run; Bye Bye Bye lacks cached
transcribe_words, I Want It That Way's SRT left the library).

| Mode | Songs | Scored | Median abs residual | ≤0.5 s | ≤1.0 s | Gross >2 s |
| --- | --- | --- | --- | --- | --- | --- |
| Joint replay (α=2.0, production knobs) | 8 | 410 | 0.24 s | 77.6% | 93.4% | **4** |
| As-run walk pipeline output | 9 | 544 | 0.17 s | 83.3% | 89.9% | **35** |

Headline: joint eliminates gross misplacements (35 → 4; Mirrors alone
had 23 wrong-chorus-instance placements under walk) but drops ~25% of
lines to interp, which never render. Phase 3 (windowed re-align)
targets exactly that coverage gap; Mirrors (76/120 placed) is the
test case.

## Phase 2a results (2026-06-10): replay knob sweep

Grid: α ∈ {0.5, 1, 2, 3, 3.5, 4, 6} × margin ∈ {0.15, 0.3, 0.5},
max_edit_ratio ∈ {0.15 … 1.0}, anchor_fallback on/off. All replayed
from cached bundles (no GPU).

- **α**: flat across \[0.5, 3\] (identical metrics), cliff at 3.5+
  entirely from Mirrors — it force-places 14 more lines but 26 land on
  the wrong chorus instance (gross 4 → 28 pooled). Production α=2.0 is
  correct; the function default was 4.0 (inside the cliff) and has been
  fixed to 2.0.
- **margin_s**: insensitive in \[0.15, 0.5\]; 0.3 kept.
- **anchor_fallback**: off loses 21 placed lines and adds a gross;
  on (current) confirmed.
- **max_edit_ratio**: the win. 0.25 → 0.75 lifts coverage
  85.6% → 89.4% (410 → 428 scored), median 0.24 → 0.22 s, gross
  unchanged at 4. The 18 newly admitted lines score median 0.13 s
  residual (17/18 within 0.5 s, none gross), and the looser gate fixes
  a Mirrors gross error (L65 −3.30 s → +0.20 s). One regression: More
  Than That L4 −0.45 → −3.11 s (appears by 0.5 already). Coverage
  saturates at 0.75; flat to 1.0. Regression proxy on the 14
  replayable non-SRT bundles: most byte-identical, gains of 1–2
  plausible lines (Beauty and the Beast, Hakuna Matata), no
  reshuffling. **Shipped: `joint_max_edit_ratio = 0.75` in
  PipelineConfig, passed at the lyric_align call site.**

Remaining gross at production knobs (Phase 2b/3 targets): For Good
final-line repeat (−6.7 s), Can You Feel The Love Tonight (1),
Mirrors (1), More Than That L4 (1).

## Phase 2b results (2026-06-10): probability weighting + corpus refresh

The worker now retains whisper word probabilities in extracted word
dicts (`_extract_words`), and `scripts/refresh_alignment_capture.py`
re-captured the corpus with them: align + refine and transcribe (no
refine) against the cached vocal stems — exactly the joint production
passes — written to `<songs>/alignment_debug_probs/` for
`eval_alignment.py --debug-dir`. The library is untouched. Bye Bye
Bye is replayable again (no cached transcribe_words before), so the
corpus is 9 songs / 540 scored lines.

**Probability weighting: rejected.** A `prob_exp` knob (scale
`transcribe_match` by mean window word probability \*\* exp) swept at
{0, 0.5, 1, 2, 4} moved nothing: coverage identical, median 0.35–0.36 s,
gross 34–37 with no consistent direction. The gross lines are real
sung vocals — whisper is confident on *every* instance of a repeated
line, so probability cannot disambiguate instances. The matcher
plumbing was removed after measurement (this commit's history has it);
the worker-side retention stays for diagnostics.

**The bigger finding: the corpus baseline moved under us.** Fresh
inputs at identical knobs score much worse than the May-era bundles
(median 0.36 vs 0.22 s, gross 36 vs 4) — because the May lyric-cleanup
change (keep-paren-contents etc.) altered what align sees. Old
captures fed align junk tokens (`♪`, `(upbeat music)`); align
quality was visibly bad, so the DP left hard lines unplaced (Mirrors
76/120) and gross stayed low *by accident of under-placement*.
Today's cleaner lines make align confident nearly everywhere: joint
now places 97.3% of lines, and align's classic failure — desync
across long repeated-line blocks — flows straight through the DP.
All 22 Mirrors gross lines are align-won placements of the
"You are, you are the love of my life" outro repeats (residuals −4 to
−50 s). Transcribe can't veto: every instance matches every window.

Consequences:

- `alignment_debug_probs` (via `--debug-dir`) is the eval corpus
  from now on; the old `alignment_debug` numbers describe inputs the
  pipeline no longer produces.
- Current true baseline (production knobs): 9 songs, 540 scored,
  median 0.36 s, 62.2% ≤ 0.5 s, 84.4% ≤ 1.0 s, **36 gross**, 97.3%
  coverage.
- Phase 3's primary target changes: not just interp coverage, but
  **repeat-block instance disambiguation** — anchor on distinct lines
  around a repeated block and re-align the block within the anchored
  audio slice. Mirrors' outro (22 gross) is the test case; For Good /
  Bye Bye Bye / Can You Feel (3 each) are secondary.

## Corpus expansion (2026-06-11): LRCLIB timing references

Non-SRT-sourced songs now score against hand-vetted LRCLIB synced
lyrics placed at `<songs>/lrclib/<stem>` (no extension). LRCLIB is a
*timing reference only* — its text variants have no quality control and
were already rejected as a lyric source — so the matcher still consumes
its real production lyrics; only the eval's reference cues come from
the LRC.

Trust model per reference kind:

- `yt-srt`: same video, professional sync. Constant offset fit
  (display lead), as before.
- `lrclib`: usually synced to a *different master*. Offset + linear
  drift fit (robust Theil–Sen), with model selection — the drift term
  is kept only when it fits better than the constant. This rescued
  Mulan (drift −2.55 s/min ≈ 4% tempo difference: median 1.68 s → 0.12 s,
  gross 14 → 0) and Best Part Of Me (−1.60 s/min), while
  structural-break references — video edits with inserted sections the
  LRC doesn't have — correctly fall back and stay visibly bad
  (Hakuna Matata +105 s dialog insert, Bloodstream extended YTMAs
  edit). Treat gross counts on those two as reference noise, not
  matcher error.

Pooled stats are reported per reference kind; mapping coverage is
naturally lower for lrclib songs (different text variant, e.g. ZAYN
33/72 mapped) — unmapped lines drop out of scoring instead of
mispairing.

The refresh driver also captures these songs now (their original
lyric txts lived in temp dirs and are gone, so it reuses each
bundle's capture-time lines verbatim). That added two songs that were
never replayable before (NSYNC Paradise, The Girl In The Bubble —
fresh passes regenerate both word streams). Defying Gravity, Popular,
Wicked-For-Good soundtrack, and the stray "paradise" bundle have no
LRC and stay out of the corpus.

### Numbers

Old May-era bundles, replay at production knobs:

| Pool | Songs | Scored | Median | ≤0.5 s | ≤1.0 s | Gross |
| --- | --- | --- | --- | --- | --- | --- |
| yt-srt | 8 | 428 | 0.22 s | 77.1% | 93.7% | 4 |
| lrclib | 12 | 409 | 0.29 s | 69.9% | 85.8% | 23 |

As-run walk-era output: 23 songs / 979 scored / 62 gross (Mirrors 23).

**Fresh corpus (current baseline), replay at production knobs:**

| Pool | Songs | Scored | Median | ≤0.5 s | ≤1.0 s | Gross |
| --- | --- | --- | --- | --- | --- | --- |
| yt-srt | 9 | 540 | 0.36 s | 62.2% | 84.4% | 36 |
| lrclib | 14 | 449 | 0.30 s | 67.7% | 84.2% | 35 |
| **combined** | **23** | **989** | **0.33 s** | **64.7%** | **84.3%** | **71** |

Consistency check: the txt songs' fresh captures reuse the same lyric
lines as their old bundles, and their scores match the old replay
almost exactly (lrclib gross 23 → 35 is fully explained by the two
newly added songs). This independently confirms the Phase 2b finding:
the yt-srt fresh-capture regression came from the lyric-cleanup input
change, not whisper nondeterminism.

Phase 3 target list (fresh corpus): Mirrors outro 22 gross,
NSYNC Paradise +73 s verse block (7), Girl In The Bubble (5 — its
transcribe pass heard only 57 words; weak vocal stem is a separate
diagnostic), then singles. Hakuna/Bloodstream gross are reference
noise.

## De-reverb experiment (2026-06-11): starved-stem recovery

Girl In The Bubble's vocal stem is audible but drenched in
reverb/echo; whisper transcribe heard only 57 words for the whole song
(14.4 words/min, zero in the 100–220 s middle) and the matcher placed
19/36 lines. De-reverbing the stem before the whisper passes
(audio-separator `dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt`,
same MelBand Roformer family as the vocal model; 913 MB, ~35 s/song on
the RTX 2060) recovered it completely:

| Bubble | placed | median | ≤1.0 s | gross | transcribe words |
| --- | --- | --- | --- | --- | --- |
| wet stem | 19/36 | 0.75 s | 68.4% | 5 | 57 |
| anvuew de-reverb | 36/36 | 0.21 s | 94.4% | 0 | 180 |

The Sucial de-reverb-echo v2 model was also tested and rejected:
transcribe yield unchanged (57), matcher slightly worse than baseline.

Corpus-wide validation (all 23 songs de-reverbed, fresh captures with
identical lyric lines, replay at production knobs): pooled gross
71 → 59, ≤1.0 s 84.3% → 85.1%, placed 989 → 962. But the wins
concentrate in two songs — Bubble (above) and Mirrors (gross 22 → 5,
≤1.0 s 74.3% → 88.4%; the align pass tracks the repeat outro better on
dry audio and drops untrackable lines to interp instead of placing
them wrong, 109 → 86 placed) — while 8 previously-clean songs
regressed: Bye Bye Bye gross 3 → 6 and placed 74 → 61, More Than That
0 → 2, Be Our Guest 0 → 1, Belle 5 → 7, plus median upticks. On some
dry stems de-reverb removes real content (Can You Feel The Love
Tonight transcribe yield 186 → 121).

**Decision: gate it, don't default it.** Wet-stem transcribe yield
separates perfectly on this corpus: Bubble 14.4 words/min, every other
song ≥ 50.5. Integration shape: after the transcribe pass, if yield
< ~30 words/min, de-reverb the stem and re-run align + transcribe.
Cost lands only on affected songs. Mirrors' improvement is forfeited
by the gate (76 words/min) — that failure class is Phase 3's target.

Artifacts: de-reverbed stems in `<songs>/dereverb/`
(`<stem>---vocal-dereverb.wav`), capture bundles in
`<songs>/alignment_debug_dereverb/`, eval JSONs
/tmp/eval_dereverb.json vs /tmp/eval_fresh_combined.json.

### Integration VRAM plan (2026-06-12, user-approved)

RTX 2060 6 GB; melband + large-v3-turbo + mpv (vo=gpu, no hwdec,
~100-300 MB constant) already fill it. Design: swap models inside the
stem worker — unload melband (drop `model_instance`, gc,
`empty_cache`), load anvuew, demix, eager reload of melband (overlaps
the whisper re-align in the other process). Whisper never reloads.
Every configuration is isomorphic to one the system survives today;
no new peak. Trap: `Separator.load_model()` constructs the new model
on GPU *before* dropping the old reference — the explicit drop must
come first. OOM safety net: worker exits → parent auto-restart with
default model → retry degrades to wet-stem pass-1. The anvuew
dereverb model emits `(noreverb)`/`(reverb)` stems — needs its own
identification branch. Pre-download the ckpt to `models/`.

Groundwork shipped: per-job `_clear_gpu_state` in the stem worker
(smoke-measured: 2190 MiB demix peak falls back to 1034 MiB post-job
instead of holding near peak — this was the manual
"clear cache between runs" pain) + `PYTORCH_CUDA_ALLOC_CONF=`
`expandable_segments:True` defaulted in both workers before CUDA init.

Shipped (2026-06-12): stem-worker jobs carry an optional model
override; swap = drop instance → gc → empty_cache → load →
empty_cache again (the load's transient allocator blocks otherwise
idle the worker at 1870 instead of ~1016 MiB under the overlapped
whisper re-align). Eager default restore right after the override job.
`(Noreverb)`/`(Reverb)` identification checked before the
vocal/instrumental names — de-reverb output names embed the input's
"(Vocals)". lyric_align's joint route gates on whole-stem transcribe
yield (`dereverb_yield_wpm`, 30; 0 disables) and re-runs align +
transcribe + matcher on the dry stem; any failure keeps wet-stem
results; cancellation propagates (`_model_call` now also translates
`WorkerCancelledError`). ckpt pre-downloaded to models/. End-to-end
verify on Bubble (RTX 2060, both workers resident): gate trips at
14.4 wpm, retry yield 43.5 wpm, joint match places 13/13 lines with
zero suspects (windowed re-align skipped — Bubble was the corpus's
worst song); dereverb swap+demix peak 2132 MiB ≤ karaoke demix peak
2190; combined two-worker peak 5378 MiB (budget 6144, mpv ~300);
retry wall-clock ≈ 79 s (38 s swap+demix + dry whisper legs). Later
refinement: per-span dereverb slices (Mirrors) reuse the same swap
machinery — one swap, N slices, restore after the last; demix then
refine run sequentially, never overlapped (measurement below).

### Concurrency measurement (2026-06-22): demix‖refine rejected, sequential confirmed

Probed the per-span optimization's open question — can de-reverb demix
overlap whisper refine to hide its cost — on an A2000 6 GB (same class as
the 2060), driving the real StemWorker (anvuew) + WhisperWorker. Drivers:
`plans/probe_concurrent_vram.py`, `plans/probe_load_during_inference.py`.

- **VRAM is not the constraint.** Both models co-resident *and* inferencing
  peak at ~5.5 GB production-equivalent (workload delta + mpv 300), fitting
  6144 with 500-1100 MiB headroom. Co-residency (weights + 2 CUDA contexts)
  is ~4.65 GB; activation sets add only tens of MiB. Confirmed with real
  anvuew vs the size-matched vocals-roformer proxy (both 871 MiB): concurrent
  peak 5494 MiB, headroom 650.
- **Concurrent inference is catastrophically slow — overlap rejected.**
  demix ‖ refine ran 3.6-11x SLOWER than sequential (a 6 s demix ballooned
  to 2.5-4.5 min). Cause is WDDM time-slicing contention, not memory pressure
  (it was *worse* with more free VRAM); no MPS on Windows, so no true
  co-execution on the target. The "pipeline demix behind refine" idea is dead.
- **A model LOAD during inference is benign.** Load slows 1.08x; whisper
  slows 1.8x but only during the ~5 s load window; concurrent wall ≈
  sequential. The shipped eager-restore-overlaps-re-align design is validated
  — keep it.

Consequence for per-span de-reverb: keep the free per-span yield gate (from
pass-1 transcribe) + batched swap (co-residency is cheap on VRAM), but run
demix and refine SEQUENTIALLY — batch-demix the flagged slices (whisper
idle), then refine the dry slices (stem idle). Never overlap two GPU
inferences on this card.

## Eval reference-mapping fixes (2026-06-11): homoglyph fold + fuzzy cue mapping

Phase 3's anchor diagnostic exposed two eval-infrastructure bugs that
were inflating the gross counts and mis-shaping the target list:

1. **Homoglyph watermarks** (`391c9be`). Lyric sites watermark fetched
   text with Cyrillic lookalikes (Belle, Paradise, Bubble each carry 2×
   U+0435 "е"); Be Our Guest has real French accents whisper writes
   unaccented. Neither side folded, so token equality silently failed
   in every matcher and `normalize_line` couldn't pair watermarked
   lines with reference cues. `_normalize_token` and `normalize_line`
   now ASCII-fold confusables + diacritics (`fold_to_ascii`,
   evidence-based 10-char table). Apostrophe deletion must precede the
   fold (U+00B4 NFKD-decomposes to space + combining mark).

2. **Instance-slip in cue mapping** (`9cd57bf`). difflib's
   exact-equality longest-block matching paired NSYNC Paradise's sheet
   chorus *instance 2* with the LRC's *instance 1* cues (the sheet's
   first instance differs by line splits / "waitin'"-style drift /
   the watermark), producing a 6-line +72 s phantom gross block while
   the matcher had actually placed both instances correctly.
   `map_lines_to_cues` is now Needleman-Wunsch fuzzy alignment;
   threshold swept: 0.85 (0.65 admits cross-split mis-pairs — ZAYN 6
   vs 1 phantom gross). yt-srt pool is a clean control: byte-identical
   before/after.

Known deferred: leading gaps free / trailing gaps charged in the NW
fill could bias zero-context instance ambiguity toward the late
instance — no corpus case at 0.85; revisit if one appears.

**New baseline (alignment_debug_probs, production knobs):**

| Pool | Songs | Scored | Median | ≤0.5 s | ≤1.0 s | Gross |
| --- | --- | --- | --- | --- | --- | --- |
| yt-srt | 9 | 540 | 0.36 s | 62.2% | 84.4% | 36 |
| lrclib | 14 | 530 | 0.32 s | 67.2% | 84.5% | 41 |
| **combined** | **23** | **1070** | **0.34 s** | **64.7%** | **84.5%** | **77** |

Eval JSON: /tmp/eval_newmap_085.json. More lines scored than the old
mapping (989 → 1070) so gross 71 → 77 is not a regression — newly
visible errors plus reference noise on newly mapped lines.

**Real Phase 3 target list** (was: Mirrors 22, Paradise 7, Bubble 5):

- Mirrors outro **22** — real align desync (dereverb independently
  confirmed: gross 22 → 5 on dry audio). THE windowed re-align target.
- Belle market scene **7** (L60–64 dialog block ±5–8 s) and CYFTLT
  **3** (speaker-tagged lines) — dialog-dense desync, plausibly
  windowed-re-align-fixable.
- Next Ten Minutes **5** — short-repeat lines ("I do" −12.9/−2.8,
  "Forever" −9.1).
- Bubble **5** — handled by the de-reverb gate, not Phase 3.
- Paradise **1** (was 7 — mapping artifact), ZAYN 1, Mulan 1, ambiguous
  outro repeats; singles in Best Part Of Me 4, Bye Bye Bye 3 (−2.5 s
  borderline), Speechless 2, Part of Your World 2, Let It Go 1.
- Hakuna 3 + Bloodstream 11 — reference noise (structural breaks).

Anchor-selection diagnostic (for the windowed re-align design): naive
criteria (placed + unique normalized text + ≥4 tokens + transcribe
corroboration ≥0.5) give ~620 anchors corpus-wide but are NOT
gross-proof — wrong-but-corroborated anchors exist where the same text
is *sung* at the placed spot too (repeats split differently than the
sheet). Anchor criteria must add local-consistency checks (agreement
of placement slope with neighboring anchors) before pinning re-align
windows.

## Phase 3 experiment (2026-06-11): windowed re-align

Two-pass design, measured corpus-wide by replay (scripts:
/tmp/phase3_window_capture.py GPU capture, /tmp/phase3_window_score.py
offline merge/score; captures in /tmp/phase3_windows{,_dr}/):

1. Pass 1: production joint match (cached bundle replay).
2. Anchors: placed + sheet-unique + ≥4 tokens + corroboration ≥0.75.
   Re-run diagnostic post-eval-fix: 19 gross / 616 anchors; criteria
   sweeps barely move it, and gross anchors cluster in the target
   regions — so the design tolerates wrong-ish edges instead of
   chasing gross-proof anchors (no local-consistency filter needed).
3. Spans between consecutive anchors (virtual song-start/end edges),
   sliced from the wet vocal stem with 0.75 s pad, anchor lines
   included as context; stable-ts align+refine on the slice with only
   the span's lines; joint matcher re-run as a sub-problem (transcribe
   words filtered to the window).
4. Merge interior lines back under a policy.

Policy sweep (pooled, 23 songs): anchor-movement tolerance gates
consistently *hurt* (rejected spans were mostly ones that would have
helped). The winner is **susp_careful**: only merge spans whose
interior has a suspect pass-1 line (interp/absent or corroboration
<0.5 — also the production GPU gate, ~40% of spans), and only let
pass 2 *newly place* a line when the span replay selected it from the
transcribe stream. Newly-placed-uncorroborated lines were the source
of all regressions (Paradise "Ooh" +10.4 s, Ariana intro −8.1 s).

| Policy | Scored | ≤0.5 s | ≤1.0 s | Gross |
| --- | --- | --- | --- | --- |
| pass 1 baseline | 1070 | 64.7% | 84.5% | 77 |
| accept-all | 1082 | 65.3% | 84.9% | 69 |
| suspect-gated | 1082 | 65.4% | 84.7% | 69 |
| **susp_careful** | **1058** | **66.4%** | **85.7%** | **58** |

Per-song (gross, pass1 → susp_careful): Mirrors 22→14, Bloodstream
11→9, NTM 5→3, Best Part 4→3, For Good 3→1, Bye Bye Bye 3→1, CYFTLT
3→2, Part of Your World 2→0, Ariana 1→2 (borderline −1.7 s → −2.6 s
threshold crossing), rest unchanged. Coverage cost −12 lines: careful
merge honestly un-places uncorroborated lines (interp beats 20 s
wrong on display).

Findings beyond the headline:

- **Belle 7 gross reclassified as reference noise**: windowed re-align
  independently reproduces pass-1's Gaston-dialog placements to ±0.1 s
  (two whisper passes on different audio scopes agree); the LRCLIB cues
  have a 16.5 s mid-dialog structural gap (synced to a different cut).
  Same class as Hakuna/Bloodstream. Agreement between pass 1 and an
  independent slice re-align is a usable reference-noise detector.
- **Mirrors chant blocks need dry audio**: wet-slice re-align gets
  22→17 (accept-all); de-reverbed slices (cached anvuew stems) get
  22→11 with coverage 97 vs full-song-dereverb's 86/5-gross collapse.
  Lead-vocal-over-chant overlap caps what any placement can do there
  (user call: parked). Suggests the de-reverb retry should eventually
  be *per-span* (slice-level gated), not whole-song.

Promoted (2026-06-11): `pikaraoke/lib/windowed_realign.py` (pure logic:
anchors, spans, suspects, span replay, careful merge) + orchestration
hook in `_run_joint` (`LyricAlignStage._realign_windows`), gated by
`PipelineConfig.joint_windowed_realign` (default True; joint route
only). The lib reproduces the experiment's susp_careful policy
bit-for-bit against the captured spans (structure identity on all 23
songs; pooled 1058 scored / 58 gross). 21 lib + 3 stage unit tests;
suite 1054 passed. Production behaviour notes:

- Suspect-free songs skip the second pass entirely — no duration
  probe, no slicing, no GPU (measured: More Than That, 0/5 spans).
- GPU cost on suspect-heavy songs approaches the full align+refine leg
  again: Bye Bye Bye +88% over pass 1 (179 s slice audio / 239 s song),
  Mirrors +96% (438/500 s). Corpus mean: 46% of audio re-aligned
  (71/177 spans).
- Per-span failures (e.g. stable-ts refine padding crash on degenerate
  slices) log a warning and keep pass-1 for that span; cancellation
  propagates; any other hook failure degrades the whole pass to pass-1.

Review (3 angles: efficacy / efficiency / robustness), fixes folded in:

- Careful merge gained an edge guard: adopted interior placements may
  intrude at most 0.5 s into a kept anchor's window, else pass-1 is
  kept. Corpus re-validated: gross 58 unchanged, ≤1.0 s 85.7 → 85.8%
  (the guard caught a real sub-gross intrusion).
- No-anchor songs (transcribe-hostile: nothing to corroborate) skip
  the pass — the lone full-song span could never improve anything but
  cost a full extra align+refine.
- WAV duration now read from the header (stdlib wave) — removed the
  repo's only ffprobe dependency, which was also an unguarded
  song-failing subprocess.
- ffmpeg slices use input-side seeking (-ss before -i): byte-identical
  output, ~5× faster per slice, kills the O(song²) decode pattern.
- Dead-worker re-raise dropped: _run_job auto-restarts the subprocess
  on the next job, so a dead worker is just another degraded span.
- Separate commit: pre-existing cancel-forwarder daemon-thread leak in
  both workers (one stranded thread per uncancelled job, amplified 2/span
  by this feature) fixed with a done-event release.

## Phase 2c results (2026-06-12): GPU sweeps

Drivers in /tmp/eval2c/ call the worker's module-level job functions
in-process (exact production code paths, per-call config). The
decode-knob variants re-run only the transcribe pass and reuse the
baseline bundles' align words — initial_prompt and temperature never
touch the align/refine legs. The model A/B re-runs all three legs with
lyric lines reused verbatim from the baseline bundles, so the only
changed variable is the model.

| Variant | Scored | ≤0.5 s | ≤1.0 s | Gross |
| --- | --- | --- | --- | --- |
| baseline (turbo, production knobs) | 1070 | 64.7% | 84.5% | 77 |
| temperature fallback (0.0 … 1.0) | 1073 | 64.7% | 84.4% | 78 |
| initial_prompt (per-song vocab) | 1067 | 63.9% | 83.9% | 79 |
| prompt + condition_on_previous_text | 970 | 52.5% | 73.3% | 132 |
| condition_on_previous_text alone | 1034 | 59.7% | 79.3% | 106 |
| **large-v3 (fp16 weights)** | **1051** | **72.0%** | **87.2%** | **60** |

**All decode knobs rejected; production values confirmed.**

- Temperature fallback: flat (±2 per-song noise). With
  logprob_threshold=None, fallback only fires on compression-ratio
  collapse, which barely occurs on stems.
- initial_prompt: mechanically inert under production config — whisper
  resets the prompt after the first 30 s window when
  condition_on_previous_text=False (prompt_reset_since in the decode
  loop), so a vocab prompt conditions only the song intro.
- Conditioning (the only way to make the prompt persist) is harmful
  alone (77 → 106 gross, broad-based) and catastrophic with the vocab
  prompt (132; NSYNC Paradise 1 → 19 — whisper hallucinates sheet
  vocabulary at wrong positions, poisoning the transcribe evidence
  stream with exactly the text the matcher is looking for). The
  config comment's hallucination/skip-cascade rationale is now
  measurement-backed.

**large-v3 vs turbo: a real accuracy win, parked on VRAM/latency.**
Gross 77 → 60 (yt-srt 36 → 23), median 0.34 → 0.27 s, ≤0.5 s
64.7 → 72.0%; Mirrors 22 → 12, Next Ten Minutes 5 → 1, Bubble 5 → 1,
CYFTLT 3 → 1. Regressions small and scattered (More Than That 0 → 2,
Hakuna +3 = reference noise). Coverage dips 1070 → 1051. Cost on the
RTX 2060: peak 4605 MiB standalone (vs turbo's 3630 in the production
worker — combined two-worker peak would go ~5378 → ~6350, over the
6144 budget before mpv) and 3-4× lyric_align wall-clock (128–165 s vs
~40 s per song, full three-leg capture). Not deployable on the target
hardware; first knob to flip if a bigger GPU lands. Notes for any
future promotion: align fail_ratio runs higher under large-v3 on
dialog-dense songs (CYFTLT 0.38, Colors of the Wind 0.24) — check the
stage's fail_ratio handling; Bubble's stem is still starved under
large-v3 (56 transcribe words), so the de-reverb gate stays necessary
regardless of model.

**Enabler worth knowing: fp16 weights.** Vanilla whisper stores fp32
weights and casts per-layer to the input dtype at compute time, so
fp32 large-v3 (6.2 GB) OOMs the 2060 at load. Loading on CPU, halving
the weights, restoring LayerNorms to fp32 (whisper's LayerNorm
upcasts input internally; halved norm weights raise a dtype error),
then moving to GPU is numerically identical under fp16 decoding —
the same per-op fp16 cast, stored once. The same trick on turbo would
free ~1.5 GB of today's whisper-worker budget at identical output —
unshipped, candidate if the VRAM budget ever tightens.

Artifacts: /tmp/eval2c/ (drivers, per-variant bundles, logs),
eval JSONs /tmp/eval2c_*.json, large-v3.pt kept in models/
(gitignored, 3.1 GB — delete if unwanted).
