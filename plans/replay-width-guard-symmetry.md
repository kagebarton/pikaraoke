# Replay-side width guard symmetry (post-Phase-4 review fix)

Model: Claude Fable 5 (design). Executor: Claude Sonnet 5.

## Context

The Phase 4 code review (Opus, 2026-07-14, commits `b825fc5`+`6a73386`+`ad9dae0`)
surfaced one PLAUSIBLE defect and two cleanups, all in the same block of
`pikaraoke/lib/windowed_realign.py`:

1. **Asymmetric width guard (the defect).** E3a's `PROTECT_MAX_PACE_S` gates
   the *pass-1* corroboration ratio in `analyze_pass1`, but `replay_span`
   computes the replay candidate's `corrob_ratio` with no pace guard. The
   merge protection compares them directly (`cand.corrob_ratio >=
   pass1_ratios[lid]` un-protects). So a replay that smears a protected
   interior line over a bloated window manufactures `corrob_ratio ~ 1.0`,
   clears the bar, and overwrites a good pass-1 placement — the same
   manufactured-corroboration mechanism E3a fixed on the pass-1 side, open on
   the replay side. **Latent**: no corpus instance fires today (the E3a
   re-validation changed exactly one row), so the pre-registered expectation
   below is byte-identical output.
2. **Duplicated ratio idiom.** The `matched, _, _ =
   _transcribe_match_and_count_in_window(...); ratio = matched / len(seq)`
   computation is copy-pasted between `analyze_pass1` and `replay_span` —
   which is exactly how one copy got the pace guard and the other didn't.
3. **Redundant full-sheet tokenisation.** `replay_span` tokenises the entire
   `align_lines` per span but only reads the `[lo..hi]` slice.

One change closes all three: a shared corroboration helper that owns the
ratio *and* the width judgment, called by both sides, plus the slice
tokenisation while that block is being rewritten.

## Design (locked — implement exactly, no redesign)

### D1. Shared helper

Add to `windowed_realign.py`, above `analyze_pass1`:

```python
def _corroboration_ratio(
    seq: tuple[str, ...] | list[str],
    t_norms: list[str],
    t_starts: list[float],
    start: float,
    end: float,
    margin_s: float,
    max_edit_ratio: float,
) -> tuple[float, bool]:
    """Transcribe-corroboration ratio for a placed line, plus width sanity.

    Returns ``(matched / len(seq), pace <= PROTECT_MAX_PACE_S)``. The ratio
    is computed over the line's own window, so a width-insane placement
    manufactures corroboration (see ``PROTECT_MAX_PACE_S``); callers must
    treat the ratio as protection evidence only when the flag is True.
    Empty ``seq`` returns ``(0.0, False)``.
    """
    if not seq:
        return 0.0, False
    matched, _, _ = _transcribe_match_and_count_in_window(
        list(seq), t_norms, t_starts, start, end, margin_s, max_edit_ratio
    )
    pace = (end - start) / len(seq)
    return matched / len(seq), pace <= PROTECT_MAX_PACE_S
```

This becomes the only place `matched / len(seq)` and
`pace <= PROTECT_MAX_PACE_S` appear.

### D2. `analyze_pass1` uses it

Replace the inline `matched, _, _ = ...` / `ratio = ...` / `pace = ...` block
with:

```python
ratio, width_sane = _corroboration_ratio(
    seq, t_norms, t_starts, obj["start"], obj["end"], margin_s, max_edit_ratio
)
if width_sane:
    ratios[lid] = ratio
if ratio < SUSPECT_RATIO:
    suspects.add(lid)
```

**Explicitly unchanged:** the suspect gate and the anchor gate keep using the
*raw* ratio. Width-gating those would change suspect classification and span
formation across the whole corpus — out of scope; Phase 4's validated
baseline must not move.

While editing the docstring's `ratios` sentence, trim the re-derived
rationale (the "computed over the line's own window ... 77s" passage) down to
a pointer at `PROTECT_MAX_PACE_S`, whose comment is the single home for it
(review finding #4).

### D3. `replay_span` uses it, zeroing width-insane candidates

Replace the corroboration block (and the full-sheet `norm_seqs`) with:

```python
norm_seqs = [
    tuple(norm for norm, _raw in t) for t in _tokenise_lines(align_lines[lo : hi + 1])
]
```

and inside the placement loop (note: read `seq` by **local** id before
shifting):

```python
shifted = dict(obj)
seq = norm_seqs[obj["line_id"]]
shifted["line_id"] = lo + obj["line_id"]
# The replay's own transcribe corroboration, so merge_spans can judge
# whether this placement earns the right to overwrite a well-corroborated
# pass-1 line. Width-insane placements score 0.0: their corroboration is
# manufactured by window bloat, symmetric with analyze_pass1's guard.
ratio, width_sane = _corroboration_ratio(
    seq, window_norms, window_starts, obj["start"], obj["end"], margin_s, max_edit_ratio
)
shifted["corrob_ratio"] = ratio if width_sane else 0.0
placed[shifted["line_id"]] = shifted
```

The old `if seq: ... else: 0.0` branch dissolves into the helper's empty-seq
return. A zeroed candidate can never meet a protected line's bar (protection
implies pass-1 ratio >= `SUSPECT_RATIO` = 0.5 > 0.0). For unprotected or
suspect lines nothing changes: `merge_spans` reads `corrob_ratio` only inside
the protection branch.

### D4. `merge_spans`: zero edits.

## Tests (`tests/unit/test_windowed_realign.py`)

1. **`test_replay_smeared_placement_zeroes_corrob_ratio`** — drive
   `replay_span` so the joint matcher places a short line wide (e.g. align
   words "i" and "do" ~19s apart -> pace > `PROTECT_MAX_PACE_S`) with
   transcribe echoing both tokens somewhere in that window; assert the placed
   object's `corrob_ratio == 0.0`. Mirror the fixture style of the existing
   `replay_span` corrob tests.
2. **`test_replay_span_with_offset_lid_lo_scores_correct_line`** — a span
   with `lid_lo > 0` whose interior line has distinct tokens from line 0;
   assert its `corrob_ratio` reflects *its own* tokens (guards the classic
   off-by-`lo` bug the slice refactor could introduce). Skip if an existing
   test already exercises `lid_lo > 0` through the corrob path — check first.
3. **Existing tests must pass unmodified.** In particular
   `test_corrob_ratio_attached_when_transcribe_fully_echoes` (its fixture is
   width-sane, so it must keep its real ratio). If any existing test fails,
   that is a STOP-and-report, not a fixture to tweak.

## Validation (pre-registered — executor stops at artifacts)

1. `PATH="$PWD/.venv/Scripts:$PATH" PYTHONIOENCODING=utf-8 uv run python -m
   pytest tests/unit/test_windowed_realign.py tests/unit/test_lyric_align.py`
   — all green. Then the full unit sweep; the 4 known Windows baseline
   failures (pipe/sidecar I/O) are not regressions.
2. Offline corpus replay: the exact invocation recorded in the Phase 4 GATE /
   E3a re-validation entries of `plans/matcher-accuracy-hardening.md`
   (defaults alpha=2.0, beta=2.0). Save to scratchpad
   `phase4_review_fix/replay_post_width_sym.txt`.
3. **Full-width** diff (no column truncation) against the post-Phase-4
   baseline `replay_post_e3a.txt`. Pre-registered expectation:
   **byte-identical, all 14 rows** — the guard is latent on the corpus and
   the refactor is behavior-preserving. **Any diff is a STOP**: save
   artifacts, report paths + raw tables, no interpretation.
4. Executor's turn ends at artifact paths + raw tables. The judge read
   (Opus/Fable, separate turn) closes it.

## Commit

One commit on `fable_matcher_refine` (never `master`), nothing from Ken's
in-flight working-tree files (`pyproject.toml`, `uv.lock`, `.kilo/`,
`plans/two-path-matcher-ship.md`):

```
fix(windowed-realign): width-guard replay corroboration via shared helper

The E3a pace guard only covered pass-1 self-corroboration; a width-insane
replay placement could still manufacture corrob_ratio ~ 1.0 over its own
bloated window and overwrite a protected line. Route both sides through
one _corroboration_ratio helper that owns the ratio and the width
judgment; tokenise only the span's slice while rewriting the block.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

## Results log

**Executor run (Sonnet, 2026-07-14).** Implemented D1-D4 exactly as
specified in `pikaraoke/lib/windowed_realign.py` (no edits to
`merge_spans`, per D4). Added the two specified tests to
`tests/unit/test_windowed_realign.py`, fixtures verified against live
`replay_span` output via throwaway scratchpad probes before writing
assertions:
- `phase4_review_fix/probe_smeared_replay.py` output confirmed the
  "i"/"do" ~19.5s-apart fixture produces `pace=9.90` (>4.0) and
  `corrob_ratio=0.0` despite `evidence.transcribe_match=2.0` (full
  pre-guard match) — the guard firing, not absence of evidence.
- `phase4_review_fix/probe_offset_lid_lo.py` output confirmed a
  `lid_lo=5` span scores line 5 (`corrob_ratio=1.0`) and line 6
  (`corrob_ratio=0.0`) against their own distinct tokens.

Test commands and results:
```
pytest tests/unit/test_windowed_realign.py tests/unit/test_lyric_align.py -q
76 passed in 10.76s
```
```
pytest tests/unit -q
4 failed, 1381 passed, 2 skipped in 30.41s
```
The 4 failures are `test_genius.py::TestSidecarIO::test_write_overwrites_existing`,
`test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job`,
`test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple`,
`test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close`
— the standing Windows/uv pipe+sidecar baseline (4, unchanged count).

`pre-commit run --config code_quality/.pre-commit-config.yaml --files
pikaraoke/lib/windowed_realign.py tests/unit/test_windowed_realign.py`:
Black reformatted `windowed_realign.py` once (whitespace/wrapping only);
second run clean on all hooks. Tests re-run post-Black: 76 passed
(unchanged).

Committed `72a93d0` (only the two files above staged; none of
`pyproject.toml`/`uv.lock`/`.kilo/`/`plans/two-path-matcher-ship.md`
included).

Offline corpus replay, exact pre-registered invocation:
```
python scripts/replay_ytasr_third_source.py "D:\shared\pikaraoke-songs" --alpha 2.0 --beta 2.0
```
Run 1, saved to `phase4_review_fix/replay_post_width_sym.txt`, diffed
full-width against baseline `phase4_gate/replay_post_e3a.txt`:
```
+LRCLIB search failed for 'Popular' / 'Kristin Chenoweth': HTTPSConnectionPool(host='lrclib.net', port=443): Read timed out. (read timeout=30.0)
-'Popular' - Wicked 20th Anniversary Edition _  3src bail:wide_spread   2.0   2.0      3->3           0.0->0.0          52->52         52/62!
+'Popular' - Wicked 20th Anniversary Edition _  3src bail:no_reference   2.0   2.0      3->3           0.0->0.0          52->52         52/62!
```
Re-ran (mechanical retry, not interpretation) twice more, same
invocation. Run 2, saved to
`phase4_review_fix/replay_post_width_sym_rerun2.txt`:
```
+LRCLIB search failed for 'Domino' / 'Jessie J': HTTPSConnectionPool(host='lrclib.net', port=443): Read timed out. (read timeout=30.0)
-Jessie J - Domino (Official Video)---UJtB55Mao 2src         0.43s/7a   2.0   n/a      0->0           0.0->0.1          62->63          63/67
+Jessie J - Domino (Official Video)---UJtB55Mao 2src bail:no_reference   2.0   n/a      0->0           0.0->0.1          62->63          63/67
```
Run 3, saved to `phase4_review_fix/replay_post_width_sym_rerun3.txt`:
```
diff exit 0 — byte-identical to phase4_gate/replay_post_e3a.txt, all 14 rows.
```

All three runs: every `mad`/`crawl`/`overlap`/`placed`/`coverage`
column identical across all 14 rows in all 3 runs. The only variance
across runs is the `src` column's bail-reason label on one row per
run, each time preceded by a `LRCLIB search failed ... Read timed out`
line naming a different song, each in the `3src`-labeled row set for
songs the pre-registered validation's own byte-identical expectation
covers via the other 4 unaffected columns.

Per pre-registration, a non-byte-identical diff is a STOP — flagging
runs 1 and 2 as such rather than characterizing them further. Artifact
paths, this session, all under
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\653d471a-1cff-4c9c-a1bd-2a7e90ca03ac\scratchpad\`:
- `phase4_review_fix/probe_smeared_replay.py`,
  `phase4_review_fix/probe_offset_lid_lo.py` (fixture-verification probes)
- `phase4_review_fix/replay_post_width_sym.txt` (run 1)
- `phase4_review_fix/replay_post_width_sym_rerun2.txt` (run 2)
- `phase4_review_fix/replay_post_width_sym_rerun3.txt` (run 3, clean)
- `phase4_gate/replay_post_e3a.txt` (pre-existing baseline, diffed against)

**Judge read (Fable, 2026-07-14): expectation met; STOPs resolved as
harness-external; ADOPT.** All comparisons re-derived from the raw
artifacts and the committed diff, not the executor summary.

- **Spec conformance** (from `git show 72a93d0` directly): D1 helper
  verbatim (modulo a Black line-wrap); D2 routes `analyze_pass1` through
  it with the suspect gate still on the raw ratio and the anchor gate
  untouched; D3 slice-tokenises and reads `seq` by local id before the
  shift, zeroing width-insane candidates; D4 holds — `merge_spans` is
  absent from the diff. Tests are pure additions (no existing test
  modified); the smear fixture pins pace 9.9 s/token with transcribe
  echoing both tokens (`transcribe_match=2.0` pre-guard, per the probe),
  so the zero is the guard firing, not absent evidence. Commit contains
  exactly the two intended files.
- **The two flagged STOPs (runs 1-2) are external, not implementation
  deltas.** Mechanism read off the harness source: `_load_lrclib_reference`
  falls back to a live LRCLIB search when a song has no cached `.lrc`,
  and on timeout `_score_against_lrclib` returns `bailed: no_reference` —
  the held-out *scoring* reference, "fetched for comparison only and
  never fed into a matcher." In both runs the only moved cell is that
  label on the timed-out song (Popular in run 1, Domino in run 2, each
  preceded by the matching stderr timeout line), and every
  matcher-derived column — crawl, overlap, placed, coverage — is
  identical to baseline on all 14 rows in all 3 runs. Same commit across
  runs: a code-caused delta would repeat deterministically; this
  co-varies exactly with the network timeout.
- **Run 3 is byte-identical to `replay_post_e3a.txt`** (diff exit 0,
  re-derived) — the pre-registered expectation, met directly.

Verdict: **`72a93d0` adopted.** Review findings #1-#4 all close: the
width guard is now symmetric and structurally single-sourced, the
duplicated idiom and full-sheet tokenisation are gone, the rationale
lives only at the constant. The change is confirmed inert on the
corpus, so `replay_post_e3a.txt` values remain the post-Phase-4
baseline unchanged. Operational note, no action required: Popular and
Domino lack local LRCLIB caches, so harness runs are network-dependent
for those two rows' MAD column only.
