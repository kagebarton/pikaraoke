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
| Phase 2 | not started |
| Phase 3 | not started |

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
