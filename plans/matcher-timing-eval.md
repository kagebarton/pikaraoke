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
| Phase 2c: GPU sweeps (initial_prompt, temp fallback, model A/B) | not started |
| Phase 3 | not started — primary target updated: repeat-block align desync (see 2b) |

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
