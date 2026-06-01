# Joint Alignment DP — Session-Import Briefing

Model: Claude Opus 4.7

Paste-ready summary for resuming work on the `joint-alignment-dp` branch
in a fresh Claude Code session. Self-contained — covers project context,
architecture, current state, and open items.

---

## 1. Project

**pikaraoke** karaoke pipeline fork.

- Working dir: `/home/ken/pikaraoke`
- Conda env: `pik` — Python at `/home/ken/miniconda3/envs/pik/bin/python`
- Tests: `/home/ken/miniconda3/envs/pik/bin/python -m pytest`
- Pre-commit config: `code_quality/.pre-commit-config.yaml` (excludes `plans/`, `static/`)
- Plans live in `plans/` with `Model:` header on first line
- No emoji in source; `CLAUDE.md` governs style
- Songs library: `/home/ken/pikaraoke-songs/` with vocal stems cached under
  `vocal/<stem>---vocal.m4a`

Allow-list at `.claude/settings.local.json` is configured for unattended
runs: auto mode + wildcards for `pytest *`, `pre-commit run *`, git read-ops,
`python -c "..."` (both quote styles), `python /tmp/*.py`,
`PYTORCH_CUDA_ALLOC_CONF=... python /tmp/*.py`, `ffprobe`, and common unix
utilities (`grep/awk/sed/head/tail/wc/cut/sort/uniq/cat/tee/ls/du/find/cp/mv/echo/until *`).
Destructive ops (`rm -rf`, `git push --force`) still require approval.

---

## 2. The architectural problem

The earlier matcher path was align → walk → tiling-on-failure with routing
gates (fail_ratio, collapse_ratio, concentration_run, coverage_cap) and a
sectional repair pipeline. Each new failure mode forced a new gate.

**The Hakuna Matata case broke this approach structurally.** The Disney
song has dialogue between 120-200s with several "Hakuna Matata" mentions.
Forced alignment confidently placed lyric lines 25-39 into that 120-130s
window (fuzzy-matching dialogue audio that happened to contain similar
words). Walk reported `max_loss_run=0` — every token "matched", just to
wrong audio. No gate detects this because the same source (align+walk) is
both matcher and quality judge.

**The fix is joint DP**: one matcher consuming align + transcribe + lyrics
simultaneously. For each lyric line, build candidates from BOTH:

- one **align candidate** at the time span forced alignment placed the line
- zero-or-more **transcribe candidates** via existing `tiling_match.find_candidates`

Score `transcribe_match + α * align_agreement * alpha_weight`. Interval-
scheduling DP picks the max-score subset under non-overlap + lyric-id
monotonicity. Per-word timings come from whichever source won each line —
align's refined timings on clean wins (preserving walk-level precision),
transcribe's word_timestamps on lines align lost.

One whole-song refine on align stays. Transcribe runs without internal
refine (`refine: bool = True` kwarg on `transcribe_words` defaults true,
the joint route passes False).

---

## 3. Branch `joint-alignment-dp`

Branched from `81ac04cb` (`feat(scripts): add --match-method to force walk
or tiling matcher`) to drop the entire sectional-tiling-repair / concentration-
gate / clip-redecode line of work that joint DP supersedes.

Commits:

| SHA | Phase | Description |
|---|---|---|
| `a85b0d6` | 0 | `docs(plans): add joint-alignment DP plan (unified matcher)` |
| `c5a7043` | 1 | `feat(joint-match): joint alignment DP matcher (in isolation)` |
| `81f97ad` | 2 | `feat(whisper-worker): add refine=False kwarg on transcribe_words` |
| `7b17cb2` | 3 | `feat(lyric-align): integrate joint matcher behind match_method='joint'` |
| `91245e0` | 3.5 | `fix(joint-match): monotonic DP + alpha-weight gate; corpus-tune alpha=2` |

Working tree is clean as of `91245e0`. 979 unit tests pass.

Stash list contains (DON'T apply on this branch):
- `superseded: corpus-tuning comments on config + two old plans` — old-branch
  edits to `pikaraoke/pipeline/config.py`, `plans/sectional-tiling-repair.md`,
  `plans/sectional-repair-clip-redecode.md`.

---

## 4. Key files

### `pikaraoke/lib/joint_match.py`

The matcher. Public entry:

```python
def match_words_to_lines_joint_with_stats(
    align_words, transcribe_words, lines, align_lines,
    *, alpha=4.0, margin_s=0.3, max_edit_ratio=0.25,
    lookahead=3, anchor_fallback=True,
) -> tuple[list[dict], dict]
```

Internal pieces:

- **`_tokenise_lines(align_lines)`** — `[(norm, raw), ...]` per line. Same
  tokenizer the walk matcher uses; assumes `align_words` corresponds 1:1
  with the flat token stream from `align_lines`.
- **`_line_align_ranges(line_tokens, align_words)`** — per-line
  `{t0, t1, token_start, token_end}` or `None` if align ran short.
- **`_align_agreement_for_window(t0, t1, align_range)`** — overlap fraction
  in `[0, 1]`. 1.0 if candidate IS the align candidate; partial overlap
  fraction for transcribe candidates near align's window; 0 if disjoint.
- **`_transcribe_match_and_count_in_window(...)`** — returns `(matched, count)`.
  Uses `bisect_left` on word start times (a previous `bisect_right - 1` bug
  was over-including words starting strictly before the window).
- **`_alpha_weight(matched, count)`** — **binary gate**: returns `0.0` if
  `count >= _ALPHA_GATE_COUNT (=2) AND matched == 0`, else `1.0`. Drops
  the align bonus when transcribe heard substantial speech but none of it
  matched the line.
- **`_build_align_candidates(...)`** — one cand per line. Score with
  alpha_weight applied. Pads collapsed align cands to `_MIN_ALIGN_WIDTH_S
  = 0.1` so the DP can reject stacks of them.
- **`_build_transcribe_candidates(...)`** — wraps tiling-style
  `(start_idx, end_idx, line_id, score)` into joint candidates with
  computed `align_agreement` and `alpha_weight`.
- **`_best_tiling_by_time(candidates)`** — **monotonic DP**. Sorted by
  `(line_id, t0)`. For each cand `i`, predecessor must have strictly
  smaller `line_id` AND `t1 <= cand[i].t0`. O(M²); fine for our scale.
  Returns selected subset in line order.
- **`_materialise_line_objects(...)`** — source-aware per-word timing:
  align win reads `align_words` for the line's token range; transcribe win
  calls `tiling_match._build_line_object` on the transcribe slice.
- **`_interpolate_missing(...)`** — fills lines with no selected cand by
  linear interp between bracketing placed neighbours. Output is 1:1 with
  `lyrics_lines`, sorted by `line_id`. Each object has explicit `line_id`
  back-reference + a `source` field (`"align" | "transcribe" | "interp" | "absent"`).

### `pikaraoke/pipeline/workers/whisper_worker.py`

`transcribe_words(vocal_path, cancel_event, *, refine: bool = True)`.
Worker dispatcher accepts both legacy 2-tuple `("transcribe_words", path)`
and new 3-tuple `("transcribe_words", path, refine)`. `_do_transcribe_words`
conditionally skips `_refine_pass` when `refine=False`. Tested via new
`_fake_worker_captures` helper that captures the IPC tuple alongside
canned replies.

### `pikaraoke/pipeline/stages/lyric_align.py`

`LyricAlignStage.run()` checks `match_method` first for `"joint"`:

```python
if use_joint:
    (line_objects, capture_words, capture_transcribe_words,
     capture_joint_stats) = self._run_joint(
        ctx, vocal_wav, lyrics_text, lyrics_lines, align_lines)
    capture_words_source = "refine"
    capture_method_used = "joint"
elif not use_tiling:
    # existing walk/auto path (escalation gates intact)
    ...
```

`_run_joint()` sequences `align_check` → `refine_from_cached` →
`transcribe_words(refine=False)` → `match_words_to_lines_joint_with_stats`.
No escalation, no gating. Returns `(line_objects, align_words, transcribe_words, joint_stats)`.

Default `match_method` is still `"auto"` (existing escalation behaviour).
`"joint"` is opt-in via config or `--match-method joint` on the backfill
script.

### `pikaraoke/lib/alignment_capture.py`

Additive (schema_version stays 4):
- `pipeline_decisions.joint_alpha`
- top-level `joint_stats` field
- top-level `transcribe_words` field

`build_bundle()` gained two optional kwargs: `joint_stats=None`,
`transcribe_words=None`. Bundles can now hold both align AND transcribe
words verbatim, so the joint matcher can be re-run offline at different α
values without paying for whisper again.

### `pikaraoke/pipeline/config.py`

```python
match_method: str = "auto"      # opt-in joint via "joint"
joint_alpha: float = 2.0        # corpus-tuned (was 4.0 design prior)
joint_margin_s: float = 0.3
```

Comment block on `joint_alpha` documents the α-sweep findings.

### `scripts/backfill_artifacts.py`

`--match-method` choices include `joint`. Help text updated.

---

## 5. Tests (979 pass)

- **`tests/unit/test_joint_match.py`** — 27 tests covering tokenisation,
  align-range mapping, alpha_agreement, transcribe_match scoring, align
  candidate construction (including collapsed-pad case), DP monotonicity
  (non-overlapping kept; overlap picks higher score; touching kept;
  monotonic order enforced), end-to-end clean / Hakuna-shape / chorus /
  align-only / no-transcribe cases, interpolation.
  - **Hakuna-shape test scenario**: line 2's correct audio sits AFTER
    line 1's transcribe location (otherwise monotonicity rejects line 2's
    align cand at 9-12s after line 1 took 15-19s).
- **`tests/unit/test_lyric_align.py::TestJointRoute`** — 3 stage tests:
  joint calls all three workers with `refine=False` on transcribe; clean
  song lines use align timings; misplaced long line routes to transcribe.
- **`tests/unit/test_whisper_worker.py`** — 2 new tests: default
  `transcribe_words` call passes `refine=True`; explicit `refine=False`
  threads through.

---

## 6. The 27-song corpus

Located at `/home/ken/pikaraoke-songs/alignment_debug/*.json`. All
schema_version 4. Each bundle now carries:

- `walk_stats.align_words` (for the 7 originally tiling-route songs;
  populated by offline align rerun)
- top-level `words` + `words_source` (refined align for 16 walk songs;
  transcribe for the 7 tiling songs)
- `lyrics.lines` + `lyrics.align_lines`
- `walk_stats.loss_spans` (current-matcher regenerated)
- top-level `transcribe_words` (populated by `/tmp/joint_alpha_sweep.py`
  for the 16 walk-route bundles that lacked it; with `refine=False`)

Vocal stems at `/home/ken/pikaraoke-songs/vocal/<stem>---vocal.m4a` — cached
separator output. Multiple backups at `alignment_debug.bak.*`.

---

## 7. α-sweep results (committed in `91245e0`'s plan doc update)

Script: `/tmp/joint_alpha_sweep.py`. Loads 27 bundles (1639 total lyric
lines), runs joint matcher per song at α ∈ {1, 2, 4, 6, 8, 12, 16}, prints
corpus totals + per-song flip counts + Hakuna-specific diagnostic.

**Corpus totals (current binary-gate matcher):**

```
   α    align  transcribe  interp   total
 1.0      406         873     360    1639
 2.0      426         853     360    1639   ← chosen default
 4.0      457         826     356    1639
 6.0      483         807     349    1639
 8.0      511         756     372    1639
12.0      519         739     381    1639
16.0      550         655     434    1639
```

**Hakuna late-line placement (lines ≥ 25; dialogue region 120-200s):**

```
   α    in_dialogue   post_dialogue   pre_dialogue
 1.0           1              9              5      ← correct
 2.0           1              9              5      ← correct
 4.0           7              0              8      ← regression
 6-16          same as α=4
```

**Decision**: α=2 chosen. α=4 keeps Hakuna's late lyrics misplaced
because the DP prefers an all-align chain when the per-line α bonus is
high enough. The binary alpha-weight gate handles high-density mismatch
(line 31 at 118-122s with dialogue text gets gated to 0) but is blind to
collapsed align windows under 0.1s (count < 2 escapes the gate). Lowering
α to 2 absorbs the residual blind spot at the cost of ~30 lines / 1639
(~2%) shifting from align to transcribe across the rest of the corpus —
within the ~100-200ms precision band of whisper word_timestamps.

---

## 8. Open todos

1. **Verify on the 5 test songs.** They were re-processed earlier with the
   old (auto) pipeline; old `.ass`/`.srt` are in `/home/ken/Videos/`. To
   compare:
   ```bash
   # Move new .ass/.srt out of the way (back into /home/ken/Videos or elsewhere),
   # then run backfill with the joint method:
   /home/ken/miniconda3/envs/pik/bin/python scripts/backfill_artifacts.py \
       /home/ken/pikaraoke-songs --yes --match-method joint
   ```
   Expected: Hakuna's late lines land at the sung reprise (200-220s) and
   outro (240s) instead of dialogue. Other 4 songs should match or exceed
   their walk/repair counterparts. The 5 songs are: Best Part of Me,
   Popular, Bloodstream, Pocahontas, Hakuna Matata.

2. **Phase 4: flip the default.** Once test-set verification passes,
   change `match_method` default from `"auto"` to `"joint"` and delete:
   - `pikaraoke/pipeline/stages/lyric_align.py`: the walk/auto branch
     (`align_check` → `match_words_to_lines_with_stats` for the routing
     decision, the `use_tiling = method == "tiling"` escalation logic,
     `_discard_cached_safely`, the `if use_tiling` block).
   - `pikaraoke/pipeline/config.py`: `align_failure_escalation`,
     `collapse_escalation_threshold`.
   - Probably also schema bump v4 → v5 if any field renames happen.
   - Keep `match_method=walk` and `match_method=tiling` as forced-mode
     escape hatches.

3. **Walk retirement (later).** If joint mode handles every clean-song
   case the corpus contains, eventually delete
   `pikaraoke/lib/word_alignment.py` and remove the walk escape hatch.

4. **(Future) Sectional refine.** If profiling shows refine cost is
   pressing, slice the align `WhisperResult` to selected-align-window
   segments before refining. Out of scope until measured.

5. **(Future) Alpha-weight gate refinement.** Current binary gate
   (`count >= 2 AND matched == 0`) misses tiny collapsed align windows.
   A min-width neighborhood (e.g. `max(window, 0.5s)`) would tighten it.
   α=2 absorbs the gap empirically; defer until a counter-example
   surfaces.

---

## 9. Key knobs reference

```python
# pikaraoke/pipeline/config.py
match_method: str = "auto"           # "auto" | "walk" | "tiling" | "joint"
joint_alpha: float = 2.0             # align-prior weight (corpus-tuned)
joint_margin_s: float = 0.3          # window word-inclusion + collapsed-cand padding

# pikaraoke/lib/joint_match.py
_MIN_ALIGN_WIDTH_S = 0.1             # pad collapsed align cands to this width
_ALPHA_GATE_COUNT = 2                # min transcribe words in window to trigger gate
```

---

## 10. Useful scratch scripts (in `/tmp/`)

- `/tmp/joint_alpha_sweep.py` — α-sweep. Idempotent (reads cached
  `transcribe_words` from bundles; offline-transcribes any that lack
  them). Output goes to stdout; redirect to a log file.
- `/tmp/hakuna_transcribe.py` — standalone transcribe of Hakuna Matata's
  vocal stem. Used during initial diagnosis.
- `/tmp/alpha_sweep_v3.log` — full output of last sweep run.

---

## 11. Quick-reference commands

```bash
# Resume work — confirm state
cd /home/ken/pikaraoke
git -C . branch --show-current   # joint-alignment-dp
git log --oneline -6              # see the 5-commit stack
git status                        # should be clean

# Run unit tests
/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit/ -q

# Re-run α-sweep (CPU-only; transcribe is cached in bundles)
/home/ken/miniconda3/envs/pik/bin/python /tmp/joint_alpha_sweep.py | grep -v "^Transcribe"

# Verify on the 5 test songs
/home/ken/miniconda3/envs/pik/bin/python scripts/backfill_artifacts.py \
    /home/ken/pikaraoke-songs --yes --match-method joint
```

---

## 12. Decision context — why α=2 over α=4

The plan's design prior was α=4 (≈ one short line of free credit). Sweep
showed α=4 left Hakuna's late lyrics in the dialogue region. The binary
alpha-weight gate fixed *some* misplaced cands (line 31 at 118-122s with
4-word dialogue context, t_match=0 → gate fires → score 0) but missed
collapsed cands at 124-126s where the window was sub-second and only 0-1
transcribe words fit (gate doesn't fire below count threshold).

Two options to fix:
- (a) Tighten the gate (min-width neighborhood for count)
- (b) Lower α so the residual ungated bonus is small enough that
  transcribe cands at correct positions beat it in the global DP chain

Option (b) was simpler and the corpus showed it had minimal collateral
on clean songs (~2% line shift). Option (a) is deferred — see open todos.

---

This briefing is itself committed in `plans/joint-alignment-dp-session-briefing.md`
on the `joint-alignment-dp` branch.
