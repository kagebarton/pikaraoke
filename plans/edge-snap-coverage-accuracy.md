# Edge snap: coverage and accuracy improvements

Model: Claude Opus 5 (design + judge; refreshed 2026-09-15); executor Claude
Sonnet 5. Originally designed 2026-07-12 (Opus 4.8, executor Sonnet 5).

> **Status (2026-09-15): LIVE, not started.** Written 2026-07-12 as a
> parallel track and **never executed**: branch `edge_snap_refine` was
> never created, the Results log was empty, and none of its changes are in
> `onset_snap.py`. The 2026-09-04 tidy-up (`370f663`) misfiled it into
> `completed/`. Opus refreshed it on 2026-09-15 against
> `joint_catchall_refit` at `0871216` and the Windows box. The "Refresh
> record" section lists every correction and why it was made.
> **Phases 0-5 are executable as written. Phase 6 is not: STOP at the
> Phase 5 checkpoint** (see Phase 6).

Execution plan for extending the edge snap (`pikaraoke/lib/onset_snap.py`)
to more cases (single-word lines, interior run edges) and improving its
accuracy. It folds in the six findings from the review in
`plans/completed/edge-snap-review-interleaved.md`, which is a genuinely
closed review doc. Designed and validated (corpus scan plus a 17-song
reference study) in a prior session. The doc is written so it can be
executed phase by phase without re-deriving the analysis.

**Line anchors.** The `onset_snap.py` and test line numbers in Phases 2-5
are at `385c881` (after Phase 1), refreshed 2026-09-15; see the Refresh
record. Each phase's own edit shifts the numbers later phases cite, so a
cited number is a locator only. The quoted code or named symbol is the
anchor.

- A number that is off while the quoted code matches, uniquely, in the named
  function is expected drift, not a STOP. Log the actual line in the Results
  log and proceed.
- Quoted code that is absent, changed, or found in more than one place is a
  STOP.

## Standing rulings this plan works inside

- **The snap stays and owns line edges** (Ken, 2026-09-10; `PROGRAM.md`
  "snap ruling"). Nothing here touches routing or placement.
- **GATE W closed 2026-09-15.** Nothing refines word boundaries inside a
  placed line. `PROGRAM.md` Part 2's row "Word boundaries inside a placed
  line" reads "joint matcher's words, unchanged".
  - Phases 1-5 move line edges only. A one-word line's edges are line
    edges.
  - Phase 6 would move interior word boundaries, which changes that row.
    See Phase 6.
- **Harness input: both harnesses** (Ken, 2026-09-15).
  - The shipped `.ass` files cover all 34 songs and measure new coverage.
  - An exact pre-snap replay of the 18 joint songs measures the fixes that
    change lines production already snaps.
  - See Phase 0.

## Context

The edge snap repairs two systematic whisper errors against the vocal
stem's RMS envelope. It is wired into `LyricAlignStage.run()`:

- `lyric_align.py:196-197` picks the stem (`aligned_stem`, the de-reverbed
  stem when the gate adopted one) and decodes the envelope once.
- On the joint route, the evidence veto runs on that envelope first
  (`:245-250`).
- `snap_line_edges(line_objects, snap_stem, env=env)` runs at `:252`,
  onsets first, then ends.
- LRCLIB fills are spliced in afterwards (`:256-257`), so fills are never
  snapped.

The two snaps:

- **Onset snap** (`snap_line_onsets`): whisper smears a line-opening word's
  start back into the preceding instrumental gap. The detector finds the
  first qualifying energy rise in `[word1.start, word2.start]` and pulls
  the start forward to it. Forward-only, bounded by word 2.
- **End snap** (`snap_line_ends`): whisper clips a held line-final word
  when its phonetic content stops. When the voice is still near sung level
  at the claimed end (clip evidence), the detector traces the voiced run to
  its first sustained fall. Extend-only, bounded by the next line's first
  word.

Both gate on a per-line sung-level reference: `_sung_level_ref` is the
median envelope level over words 2..n. Word 1 is excluded because its span
is the thing being repaired.

**Callers that constrain the change:**

- **Public signatures** of `snap_line_onsets`, `snap_line_ends` and
  `snap_line_edges` must not change. Callers:
  - `lyric_align.py:252`
  - `scripts/onset_snap_ass.py:77`, `scripts/end_snap_ass.py:33`,
    `scripts/edge_snap_ass.py:93,105` and `scripts/edge_snap_replay.py:77`
  - `tests/unit/test_lyric_align.py:597-599,738`, which monkeypatch it
- **`_sung_level_ref` has a second caller.** `lrclib_fill.py:279` computes
  a song-wide reference over every placed word.
  - Any parameter you add must default to today's behaviour.
  - The ≥2-word median path must stay byte-identical under default
    arguments.
  - `tests/unit/test_lrclib_fill.py` must stay green.
  - In practice the fill never reaches a one-word call: planning only runs
    on an eligible song, which has many placed words.
- **Shared constants.** `MIN_REF_DB`, `HOP_S` and `SOFT_NEAR_DB` are
  imported by `evidence_veto.py`, `lrclib_fill.py` and their tests. No
  phase renames or retunes them.

### Measured ground truth

**Historical: 2026-07 Linux corpus** (`/home/ken/pikaraoke-songs`, 1791
lines, the design basis). Not re-derived.

- **64 single-word lines** are skipped on both edges by the `len(words) <
  2` gates.
  - Median duration 1.04s, max 5.62s.
  - 35 are ≥ 1s held notes, the exact shape both snaps exist to repair.
  - This is the headline coverage gap.
- **114 multi-word lines** are skipped by `w2s - w1s < MIN_WORD_DUR_S`. Not
  worth chasing: the clamp `new_start <= w2s - MIN_WORD_DUR_S` caps any
  shift below `MIN_SHIFT_S` by construction, so the skip is exact, not
  conservative.
- **388 interior words** sit after an intra-line gap ≥ 0.5s. The ASS writer
  re-anchors at every inter-word gap, so these show the same smear and clip
  artifacts. They are out of scope today only because the walk visits line
  edges.

**Reference study** (17-song sample, 909 multi-word lines, 36 single-word
lines). It compares the current reference (median over words 2..n) against
an 80th percentile over all word spans.

- **Multi-word lines:** the percentile sits a median of **+2.2 dB** above
  the current reference (p90 +5.3 dB), and **7.2% of lines differ by more
  than 6 dB**.
  - A blanket swap would silently retune `NEAR_SUNG_DB`, `SUSTAIN_NEAR_DB`
    and `MIN_REF_DB` corpus-wide.
  - **Rejected** as a global change. The percentile is used only where the
    current reference cannot exist.
- **Single-word lines:** the percentile over the word's own span gives a
  usable reference (≥ `MIN_REF_DB`) for **35 of 36**.
  - The one rejection is a genuinely misplaced line landing at the floor,
    which is the correct outcome.
  - The percentile resists the defect being repaired because smeared gap
    frames are *low* outliers. As long as ≥ 20% of the claimed span is
    truly sung, the 80th percentile lands inside the sung level.

**Current: Windows corpus facts** (`d:/shared/pikaraoke-songs`). Opus read
these from the capture bundles on 2026-09-15, read-only.

- **34 songs** have both a bundle and a vocal stem.
  - 18 are on the joint route and 16 on the cue-align (SRT) route.
  - 33 bundles are schema v8 and one is v9.
- **1823 placed lines** (846 joint, 977 cue).
- **61 one-word lines** (21 joint, 40 cue), counted as `n_words == 1` in
  `output_line_timings`.
- **Production's recorded edge snap** (`joint_stats.edge_snap`, present in
  all 34 bundles): 417 onset snaps and 484 end extends, 202 of them
  `to_bound`.
- **No LRCLIB fills** in any bundle (`filled_lids` is empty everywhere).
- **One song adopted the de-reverbed stem**, so production snapped it
  against `dereverb/<stem>---dereverb.m4a`, not the vocal stem. It is
  `Wicked - For Good (2025) 4K - The Girl in the Bubble (7_8) _
  Movieclips---wzSeub9W4QQ` (joint route, `joint_stats.dereverb.succeeded`
  true).
- The 114 and 388 counts above were **not** re-measured on this corpus.

### Do not do (already analyzed and rejected)

- **A blanket percentile reference for multi-word lines.** It retunes every
  threshold (see the study above). Use it as the single-word fallback only.
- **The 114 narrow-window lines.** Their maximum possible shift is below
  `MIN_SHIFT_S`.
- **Moving the end-side `n_fired += 1` below the `MIN_SHIFT_S` gate** (one
  of review #2's two options). That would make `n_fired` identically equal
  to `n_extended` and thus useless. Add an `n_below_min_shift` counter
  instead (the review's other option).

## Process

- **Branch:** `git checkout -b edge_snap_refine joint_catchall_refit`, from
  its tip at execution time. This refreshed plan is already committed
  there.
  - Never commit to `master`.
  - The working tree carries unrelated uncommitted `pyproject.toml` and
    `uv.lock` edits. Never stage them.
- **Environment:** Windows box, uv. Run everything from the repo root.
  - Python: `uv run --no-sync python ...`.
  - Tests: `uv run --no-sync python -m pytest tests/unit -q`.
  - Baseline at `0871216` (2026-09-15): 4 failed, 1516 passed, 2 skipped.
    The four are the known Windows-only failures:
    - `test_genius.py::TestSidecarIO::test_write_overwrites_existing`
    - `test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job`
    - `test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple`
    - `test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close`
  - Any failure outside that set is a STOP.
  - Pre-commit: `uv run --no-sync pre-commit run --config
    code_quality/.pre-commit-config.yaml --all-files` (`plans/` is excluded
    by policy).
- **Song library:** `d:/shared/pikaraoke-songs`.
  - Song names contain soft hyphens, non-breaking spaces and `[...]`.
  - Capture harness output with the Bash tool's raw redirect:
    `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 uv run --no-sync python scripts/...
    > <file>`.
  - Never pipe it through PowerShell (mojibake), and never print it to the
    console (cp1252 crash).
- **Tests:** `tests/unit/test_onset_snap.py` collects **31 tests** (29
  functions, one parametrized ×3). All new tests go there.
  - Use the existing `_env` / `_line` helpers and the `use_env` fixture
    (`test_onset_snap.py:23-48`). The `_env` floor is -60 dB.
  - Every expected value below was verified by executing the phase's change
    on a scratch copy. Assert with `pytest.approx(value, abs=0.01)`.
  - Detector arithmetic worth knowing before reading the values:
    - **Onset snaps** land 0.075s before a synthetic step, not 0.05s. The
      soft-onset tier accepts the frame just before the step: its 3-frame
      post-mean already sits within `SOFT_NEAR_DB` and sustains.
    - **Release traces** trigger on the 8-frame *windowed mean*. With a
      -20 dB run meeting the -60 floor, that happens once ≤ 5 loud frames
      remain, i.e. 0.125s before the visual edge.
- **Two harnesses, both built in Phase 0:**
  - **Coverage harness** `scripts/edge_snap_ass.py`: shipped `.ass` files,
    all 34 songs.
  - **Replay harness** `scripts/edge_snap_replay.py`: exact pre-snap line
    objects, 18 joint songs.
- **Artifacts:** save to `edge_snap/` in the session scratchpad, named
  `edge_p<N>_<harness>.txt` (and `.diff`).
  - Record each artifact's **absolute path** in the Results log, so a later
    session can diff against it.
  - Compute every diff with `diff`, never by eye.
- **Record view:** a harness output with its `  stats `, `  wrote ` and
  `total ` lines removed. For example,
  `grep -v -e '^  stats ' -e '^  wrote ' -e '^total ' <file>`. Byte-identity
  gates below compare record views.
- **Commits:** one per phase (Phase 0 has two), tests riding with the code.
- **Executor discipline (Sonnet 5).** The phases assume a literal executor.
  - **STOP on any mismatch** between a stated anchor, constant, expected
    value or worked example and the code or corpus. Report the exact
    mismatch. Never bridge it with your own design, and never tune a
    constant the phase does not name. A shifted line number whose quoted
    code still matches is not a mismatch (see **Line anchors** at the top).
  - **Your mechanical gates:**
    - the suite result against the known-failure set
    - Phase 0's fidelity guard
    - the pre-registered byte-identity gates (diff empty or not)
    - the population counts pre-registered in Phase 2
  - Any gate failure is a STOP. A failing test is a STOP, not a
    retry-until-green.
  - **Results log:** the invocation, the artifact paths, the harnesses'
    own printed totals and the diffs, pasted verbatim. No verdicts, no
    tallies derived past what a harness prints, and no characterisation of
    what changed (`PROGRAM.md` "Model switching").
  - Phase 7 items are study-only. Each ends at STOP plus report, and 7d is
    design work that goes to Ken before any implementation, whatever the
    telemetry shows.

## Phase 0 — Harnesses and baseline

The harness written into this plan in 2026-07 re-snapped the shipped
`.ass` files. That was valid then, because the shipped files predated the
snap. **Today every shipped file is already snapped**, so re-snapping it
cannot show a phase that changes lines production already moved (Phases 1,
3 and 5). Phase 0 therefore fixes the coverage harness, adds an exact
replay harness, and records the baseline on both.

### 0a. Coverage harness (`scripts/edge_snap_ass.py`)

**Changes:**

1. **Population.** Iterate `<folder>/alignment_debug/*.json` in sorted
   order instead of globbing `karaoke/*.ass`. Per bundle, `stem =
   bundle_path.stem` and the shipped file is `karaoke/<stem>.ass`. When it
   is missing, print `  skipped (no shipped .ass)` and continue.
2. **Stem.** Add a module-level helper
   `snap_stem_path(folder: Path, stem: str, bundle: dict) -> Path`.
   - It returns `folder / "dereverb" / f"{stem}---dereverb.m4a"` when
     `((bundle.get("joint_stats") or {}).get("dereverb") or
     {}).get("succeeded")` is true.
   - Otherwise it returns `folder / "vocal" / f"{stem}---vocal.m4a"`.
   - This mirrors production's `aligned_stem`. When the file is missing,
     print `  skipped (no stem)`.
3. **`--folder`** becomes `required=True`, dropping the Linux default.
4. **`--multi-word-only`** drops every line object with exactly one word
   before snapping. It is used by the Phase 4 gate.
5. **Output format**, fixed from this phase on so later diffs carry no
   format noise:
   - Record lines:
     - onset: `  rec onset <tag><old> -> <new> (+<shift>s)  <first 5 words> ...`
     - end: `  rec end <tag><old> -> <new> (+<extend>s)<flag>  ... <last 5 words>`
     - `<tag>` is `[1w] ` for a one-word line and empty otherwise.
     - `<flag>` is ` to_bound` or empty.
   - One `  stats onset k=v ...` and one `  stats end k=v ...` line per
     song. Print **every integer-valued key** of that stats dict in sorted
     key order, so counters added by later phases appear with no harness
     edit.
   - Keep the `  wrote <file>` line.
   - Totals: `total songs=<n>`, then `total onset k=v ...` and
     `total end k=v ...`, summing every integer key across songs.
6. **Docstring.** State the fidelity limits:
   - (i) Shipped files are already snapped, so this harness's absolute
     counts are second-application artifacts. Only phase-to-phase diffs
     are read, and only for lines production's snap never touches:
     one-word lines, and interior runs in Phase 6.
   - (ii) The ASS round-trip floors word durations at 10 cs and rounds to
     cs, so parsed word times drift from production's inside multi-word
     lines. One-word lines round-trip to within 1 cs.

No unit tests (offline tool, like its siblings). Commit:
`fix(edge-snap-harness): bundle population, production's snap stem, stable output`

### 0b. Replay harness (`scripts/edge_snap_replay.py`, new)

Rebuilds each joint song's **pre-snap** line objects exactly as production
built them, then runs the checked-out snap on them.

**Pipeline, per bundle with `pipeline_decisions.method_used == "joint"`.**
Cue-route bundles are skipped silently: they need whisper per cue slice, so
they cannot be replayed offline.

1. `song_root = folder`; `knobs = bundle["joint_stats"]["knobs"]`.
2. `ytasr_words = _load_ytasr_words(bundle, song_root)`.
3. `realign = _replay_spans(bundle, ytasr_words, knobs["alpha"],
   knobs["beta"])`, then `objs, _ = _replay_output(bundle, ytasr_words,
   knobs["alpha"], knobs["beta"], realign)`.
   - Import the three helpers from `scripts/replay_ytasr_third_source.py`,
     the shipped replay chassis. Do not copy them.
   - Import `snap_stem_path` from `edge_snap_ass`.
4. `stem_path = snap_stem_path(folder, stem, bundle)`;
   `env = rms_envelope_db(stem_path)`. A decode failure is a STOP.
5. `objs, veto_stats = veto_uncorroborated_lines(objs, env)`.
6. `if args.multi_word_only`: drop one-word line objects. The filter
   applies after the veto, exactly where the coverage harness applies it
   relative to its input.
7. `final, edge_stats = snap_line_edges(objs, stem_path, env=env)`.

**Output.** Same format as 0a, except record lines carry the line id:

- `  rec onset <tag>L<line_id> +<shift_s>`
- `  rec end <tag>L<line_id> +<extend_s><flag>`

The `stats` and `total` lines are identical in form to 0a.

**`--write-ass`** renders `generate_ass(final, PipelineConfig())` to
`karaoke/<stem>.edgereplay.ass`, never the shipped file. Add `".edgereplay"`
to `SKIP_SUFFIXES` in `scripts/onset_snap_ass.py`.

**`--guard`: the fidelity guard.** Run at Phase 0 on unmodified snap code.
Per song, all of these must hold:

- **(i) Veto:** `veto_stats["n_vetoed"]` and the set of vetoed line ids
  equal the recorded `joint_stats.evidence_veto`.
- **(ii) Snap records:**
  - `edge_stats["onset"]["snaps"]` equals the recorded
    `joint_stats.edge_snap.onset.snaps` exactly (list equality).
  - `edge_stats["end"]["extends"]` equals the recorded
    `edge_snap.end.extends` exactly.
  - Every key present in the recorded onset and end stats dicts has an
    equal value.
- **(iii) Output timings:** `alignment_capture.output_line_timings(final)`
  matches the recorded `output_line_timings`.
  - The two lists have the same length.
  - Per index: equal `line_id` and `n_words`, with `start` and `end` within
    1e-6 (`None` matches only `None`).
- **(iv) No fills:** the recorded `joint_stats.lrclib_fill.filled_lids`,
  when present, is empty. Fills are not replayed.

Print `  GUARD PASS` or `  GUARD FAIL <check> first_line_id=<id>` per song,
and exit non-zero if any song fails.

No unit tests; the guard is the test. Commit:
`feat(edge-snap-harness): exact pre-snap replay for the joint route`

### 0c. Baseline (no snap-code change)

1. **Unit suite.** Record the pass/fail/skip line and the names of every
   failure. They must be exactly the four known failures listed under
   Process.
2. **Guard.** `scripts/edge_snap_replay.py --folder d:/shared/pikaraoke-songs
   --guard` → `edge_p0_guard.txt`.
   - **Every one of the 18 songs must print `GUARD PASS`.** Any `GUARD
     FAIL` is a STOP → Opus.
   - Do not exclude songs, loosen tolerances, or patch the replay.
   - The matcher changed after the bundles were captured (`fcefcce`,
     2026-09-01), which is exactly what the guard exists to catch.
     **Corrected at the Phase 0 read-off:** `fcefcce` is telemetry-only.
     The behaviour change since capture is `ad51a86` (GATE T, ytasr
     candidate edit ratio 0.34 -> 0.45). Every corpus bundle predates it,
     so the guard reproduces the bundles only at 0.34. See "Phase 0
     read-off" in the Results log for the probe.
3. **Baseline runs:**
   - replay harness → `edge_p0_replay.txt`
   - coverage harness → `edge_p0_coverage.txt`
4. **Results log.** Paste both files' `total` lines verbatim.

## Phase 1 — Symmetric silence gate on the onset path (review #4)

**Prerequisite for Phase 4.** The single-word design leans on `MIN_REF_DB`
rejecting floor-level references, and the onset path has no such gate
today.

**Change** in `snap_line_onsets`: insert the gate after the `ref is None`
check at `onset_snap.py:203-206` and *before* the on-time guard at
`218-225`.

```python
if ref < MIN_REF_DB:
    n_low_ref += 1
    out.append(obj)
    continue
```

Initialize `n_low_ref = 0` alongside `snaps`, and add `"n_low_ref"` to the
onset stats dict. Placement before the guard matters. Over near-silence
the reference drags to the floor and the guard becomes trivially true, so
the gate must own that rejection, not the guard.

**Test:** `test_line_in_silence_untouched` in `TestSnapLineOnsets`, mirroring
the end-side test at `test_onset_snap.py:314`. The construction is one
where the guard does NOT fire and a rise WOULD be accepted without the
gate, so the test actually discriminates.

- `_env(8.0, [(2.5, 3.0, -48.0), (3.2, 4.0, -50.0)])`
- line `_line((2.0, 3.0), (3.2, 3.5), (3.6, 4.0))`
- The ref is the median over the spans of words 2..3, i.e. -50. That is
  below `MIN_REF_DB` (-45), so the line is gated.
- Without the gate:
  - The guard's start check is -60 >= ref - 8 = -58, which is False, so the
    guard lets the line through.
  - The -60→-48 bump at 2.5s is a 12 dB step landing above -58 with a
    passing continuity median, so it would snap to **2.45**. Verified:
    current code does exactly this.
- Assert the line is untouched, `stats["n_low_ref"] == 1` and
  `n_snapped == 0`.

**Verify:**

- Suite: only the known failures.
- Replay harness → `edge_p1_replay.txt` and
  `diff edge_p0_replay.txt edge_p1_replay.txt > edge_p1_replay.diff`.
- Coverage harness → `edge_p1_coverage.txt`, with its `.diff` against P0.
- Paste both diffs.

Recorded expectation, for the Opus read at the checkpoint (not an executor
gate):

- Onset records disappear on lines production snapped over a floor-level
  reference.
- An end record may change on the line *before* each disappeared onset,
  because an un-snapped start narrows the previous line's end bound.

Commit: `fix(onset-snap): reject low-reference lines on the onset path too`

## Phase 2 — Telemetry symmetry (reviews #2 and #6, plus sizing counters)

All counters, no behaviour change. These make every later phase's tuning
data-driven and give Phase 7 its GO/NO-GO numbers.

**End path** (`snap_line_ends`):

- Add `n_below_min_shift`, incremented in the `new_end - w_end <
  MIN_SHIFT_S` rejection at `onset_snap.py:352-354`.
- Leave `n_fired += 1` where it is (`336`). Its meaning stays "clip evidence
  present".
- State the resulting invariant in a comment:
  `n_fired == n_extended + n_below_min_shift`.

**Onset path** (`snap_line_onsets`), mirroring the end path's counters:

- `n_fired`: incremented when a line passes the on-time guard, i.e. it
  shows smear evidence and reaches rise detection.
- `n_no_rise`: `_detect_rise` returned None.
- `n_below_min_shift`: the `new_start - w1s < MIN_SHIFT_S` rejection at
  `238-240`.
- `n_undetectable`: among fired lines, those where the step detector
  cannot qualify a rise.
  - The condition is `ref - p20 < STEP_DB`.
  - `lo = min(int(w1s / HOP_S), len(env) - 1)`
  - `hi = min(max(int(w2s / HOP_S), lo + 1), len(env))`
  - `p20 = float(np.percentile(env[lo:hi], 20))`
  - Count and continue. Do NOT skip the line: this is a measurement for
    Phase 7b, not a gate.
- Invariant, in a comment:
  `n_fired == n_snapped + n_no_rise + n_below_min_shift`.

**Both paths:** add `n_single_word`, counting lines with exactly one word.
They are currently skipped at the `len(words) < 2` gates. Phase 4
re-purposes the counter to "single-word lines seen", with the same
definition.

**Tests:** extend existing tests with stats assertions, plus one new test.

- `test_shift_below_jitter_threshold_untouched`: assert onset
  `n_fired == 1`, `n_below_min_shift == 1` and `n_no_rise == 0`.
- `test_no_rise_untouched`: **its construction never reaches rise
  detection.**
  - On a flat -50 dB envelope the reference is -50. Before Phase 1 the
    on-time guard claimed the line; from Phase 1 on, the low-reference
    gate claims it.
  - Assert `n_low_ref == 1` and `n_fired == 0`, and add a one-line comment
    saying so.
- New `test_step_below_threshold_counts_no_rise` in `TestSnapLineOnsets`:
  - `_env(5.0, [(0.5, 2.5, -41.0), (2.5, 4.5, -32.0)])`
  - line `_line((1.2, 1.4), (2.5, 2.7), (3.0, 4.0))`
  - The ref is -32 (words 2..3 lie in the -32 patch). The guard fails
    because -41 < ref - 8 = -40.
  - The only step is -41 → -32, i.e. 9 dB < `STEP_DB`, so there is no rise.
  - Assert the line is untouched, `n_fired == 1`, `n_no_rise == 1`,
    `n_below_min_shift == 0` and `n_snapped == 0`. Verified.
- End-side `test_sub_jitter_extension_untouched`: assert `n_fired == 1`,
  `n_below_min_shift == 1` and `n_extended == 0`.

**Verify:**

- Suite: only the known failures.
- Both harnesses → `edge_p2_*.txt`.
- **Gate:** each harness's record view is byte-identical to its Phase 1
  record view (counters only). A non-empty record-view diff is a STOP.
- **Gate:** the harnesses' printed totals give `n_single_word`:
  - coverage harness: onset **61**, end **61**
  - replay harness: onset **21**, end **21**
  - These are the counts read from the bundles. Any other number is a STOP.
- Paste the `total` lines, including `n_undetectable`, which sizes 7b.

Commit: `feat(edge-snap): symmetric onset/end telemetry counters`

## Phase 3 — Stem-end truncation split in `_detect_rise` (review #1)

The trust branch at `onset_snap.py:170` accepts a rise when the remaining
run is shorter than the sustain window. It cannot tell *word-2 proximity*
(the intended exception) from *the envelope running out* (a truncation
artifact). Single-word lines cluster in outros and fades, so Phase 4 will
feed this branch more cases near the stem end. Fix it first.

**Change:** compute the two bounds separately and trust only the word-2
case.

```python
b_word2 = int(t1 / HOP_S)
b_env = len(env) - EDGE_FRAMES
b = min(b_word2, b_env)
...
        if b - i < sustain_frames:
            # Continuity with word 2 is trustworthy; the envelope running
            # out is not — onsets near the stem end are unreliable.
            if b_word2 <= b_env:
                return i * HOP_S
            continue
        if float(np.median(env[i:b])) >= ref_db - SUSTAIN_NEAR_DB:
            return i * HOP_S
```

Use `continue`, not `return None`: later candidates in the same scan hit
the same truncated-window branch and fall out naturally. `b_word2 == b_env`
counts as word-2 proximity, because word 2 genuinely starts there.

**Test:** `test_rise_truncated_by_stem_end_rejected` in `TestSnapLineOnsets`.
The envelope ends at 5.0s, so `len(env) = 200` and `b_env = 197`.

- `_env(5.0, [(4.7, 5.0, -20.0)])`
- line `_line((3.0, 4.6), (4.95, 5.4))`
- Word 2 starts at 4.95, so `b_word2 = 198 > b_env = 197` and the window is
  env-truncated.
- Word 2's span keeps 2 in-envelope frames at -20, so the ref is -20 and
  there is no `ref is None` bail.
- The soft tier accepts frame 187, one hop before the 4.7s step. There
  `b - i = 10 < sustain_frames = 16`, so the trust branch fires.
  - **Pre-change:** snaps to **4.625** (verified).
  - **Post-change:** rejected, line untouched (verified).
- Assert the line is untouched and `stats["n_no_rise"] == 1` (the rejection
  surfaces as no-rise).
- The existing `test_soft_rise_just_before_word2_accepted` (`:173`) must
  still pass, and it does: 2.225 before and after. That is the
  intended-trust case this change must not break.

**Verify:**

- Suite: only the known failures.
- Both harnesses → `edge_p3_*.txt`, with `.diff`s against P2. Paste both.

Recorded expectation, for the Opus read: a handful of onset records near
song ends disappear, mainly on the replay harness.

Commit: `fix(onset-snap): reject rises truncated by the stem end`

## Phase 4 — Single-word line support (the headline coverage gap)

**Design.** The only structural blocker on both edges is the reference.
Everything else generalizes with a one-variable change of bound.

**4a. Reference** (`_sung_level_ref`, `onset_snap.py:127-141`). Add a new
module constant:

```python
# Single-word lines have no words 2..n to reference. A high percentile of
# the word's own claimed span works instead: smeared gap frames are LOW
# outliers, so with >= ~20% of the span genuinely sung the percentile lands
# at the sung level; a span lying wholly in a gap yields a floor-level
# reference that MIN_REF_DB rejects. Validated at 35/36 usable on corpus.
SINGLE_WORD_REF_PCT = 80.0
```

Inside `_sung_level_ref`, when `len(words) == 1`, return
`float(np.percentile(env[span_idx], SINGLE_WORD_REF_PCT))` over word 1's
own span.

- Use the same index construction and bounds filter as today. A sub-frame
  span still yields ≥ 1 frame, so no extra guard is needed.
- The ≥2-word path must stay byte-identical, because `lrclib_fill.py:279`
  calls it.
- Update the docstring: the "word 1 is excluded" rationale now applies
  only to the multi-word case.

**4b. Onset path** (`snap_line_onsets`):

- Replace the `len(words) < 2` gate (`195-197`) with `if not words:`, plus
  `n_single_word` counting (now "seen", not "skipped").
- Generalize the bound:

  ```python
  bound = words[1]["start"] if len(words) >= 2 else words[0]["end"]
  ```

- Use `bound` everywhere `w2s` is used today:
  - the narrow-window skip (`200`)
  - the `_detect_rise` call (`232`)
  - the clamp (`237`, `bound - MIN_WORD_DUR_S`)
- For a single-word line the end-carry branch at `245-248` is unreachable,
  because the clamp keeps `new_start <= w1e - MIN_WORD_DUR_S`. No
  special-casing is needed: the existing `[{**words[0], ...}] + words[1:]`
  construction is already correct for a 1-element list.

Known, accepted limitation (note it in the docstring): `_detect_rise`'s
continuity check now demands that the voice hold to the *claimed end*.

- For held notes this is correct. They are the case that matters: whisper
  clips their ends early, so the claimed end is inside the true run.
- A staccato word with a wildly long claimed span won't snap. That is the
  safe direction.

**4c. End path** (`snap_line_ends`):

- Replace the `len(words) < 2` gate (`302-304`) with `if not words:`, plus
  the counter.
- Nothing else changes. The bound search, the `MIN_REF_DB` gate, clip
  evidence and the release trace never reference word 2.
- Note the ordering dividend in the docstring: ends run after onsets, so a
  single-word line's reference at end-snap time is computed over the
  already-snapped (cleaner) span.

**4d. Tests.** Rework the two `test_short_lines_skipped` tests (`210`,
`357`).

- Keep the empty-words object as `test_empty_words_skipped` in each class.
- The one-word cases move to the new tests below.
- All values were verified by executing this phase on a scratch copy.

1. `test_single_word_smeared_start_snaps`:
   - `_env(8.0, [(3.5, 5.0, -20.0)])`, line `_line((2.0, 5.0))`,
     `snap_line_onsets`.
   - The ref is pct80 over [2.0, 5.0] = -20 (60 of 121 frames sung). The
     guard fails at -60.
   - Expect start **3.425**, end unchanged at 5.0, and `n_snapped == 1`.
2. `test_single_word_on_time_untouched`:
   - `_env(8.0, [(2.0, 4.0, -20.0)])`, line `_line((2.0, 4.0))`,
     `snap_line_onsets`.
   - The guard fires, so the line is untouched with `n_fired == 0`.
3. `test_single_word_clipped_end_extends`:
   - `_env(10.0, [(2.0, 6.0, -20.0)])`, line `_line((2.0, 3.0))`, no next
     line, `snap_line_ends`.
   - Clip evidence at 3.0 (-20 >= -28).
   - Expect end **5.875**, `n_fired == 1` and `n_extended == 1`.
4. `test_single_word_in_silence_untouched`:
   - `_env(12.0, [(1.0, 4.0, -28.0)])`, line `_line((6.0, 7.0))`.
   - pct80 is -60 < `MIN_REF_DB`.
   - Call `snap_line_onsets` and `snap_line_ends` separately on the same
     input. For each, assert untouched and `n_low_ref == 1`.
5. `test_single_word_both_edges` (in `TestSnapLineEdges`, injecting the
   envelope like `test_single_decode_fixes_both_edges`, `:386`):
   - `_env(10.0, [(3.5, 6.5, -20.0)])`, line `_line((2.0, 4.5))`.
   - The onset pass snaps the start to **3.425**.
   - The end pass then re-derives the ref over the snapped span, sees clip
     evidence at 4.5 and traces to **6.375**.
   - This is the held-"Oooh" showcase: both edges envelope-derived.

**Verify:**

- Suite: only the known failures. `tests/unit/test_lrclib_fill.py` is
  included and must be green.
- Both harnesses unfiltered → `edge_p4_*.txt`, with `.diff`s against P3.
- Both harnesses with `--multi-word-only` at Phase 3 **and** Phase 4 code.
  The Phase 3 run is a re-run on the Phase 3 commit.
  - Output files: `edge_p3_mwo_*.txt` and `edge_p4_mwo_*.txt`.
- **Gate:** for each harness, the `--multi-word-only` record views at P3
  and P4 are byte-identical. A non-empty diff is a STOP.
  - This replaces the 2026-07 gate "multi-word records byte-identical on
    the full corpus", which was unsound. A one-word line's forward onset
    snap widens the *previous* line's end bound, so a multi-word end record
    can legitimately change in the unfiltered run.
- Paste the unfiltered diffs.

Commit:
`feat(edge-snap): single-word line support via own-span percentile reference`

## Phase 5 — End-path reference includes word 1 (review #3)

The end snap borrows the onset snap's "exclude word 1" rule, but it has no
onset-smear problem to defend against: by the time ends run, onsets have
already been repaired. On lines that are mostly one long held note plus
short words, the tail-only median misstates the sung level.

**Change:** `_sung_level_ref(env, words, end=False)`.

- For `len(words) >= 2`: include `words[0]`'s span when `end` is true and
  `words[0]["end"] - words[0]["start"] > MIN_WORD_DUR_S`. Otherwise slice
  `words[1:]` as today.
- The `len(words) == 1` percentile path from Phase 4 is independent of
  `end`.
- `snap_line_ends` passes `end=True` at its `_sung_level_ref` call (`:320`).
  The onset call and
  `lrclib_fill.py:279` keep the default.
- Rewrite the docstring: "both snaps gate on this same reference" is no
  longer the contract.

**Test:** `test_end_ref_includes_long_word1` in `TestSnapLineEnds`.

- `_env(10.0, [(1.0, 3.0, -20.0), (3.2, 5.5, -34.0)])`
- line `_line((1.0, 3.0), (3.2, 3.4), (3.6, 4.0))`
- **Old ref** (words 2..3 only) is -34. Clip evidence at 4.0 fires
  (-34 >= -42), and the line extends along the -34 patch to **5.4**.
  Verified at Phase 4 code.
- **New ref** is -20, because word 1's 81 frames dominate the median. Clip
  evidence fails (-34 < ref - 8 = -28): the last word has already fallen
  14 dB below the line's true sung level, i.e. it has already released.
  Verified.
- Assert the line is untouched and `n_fired == 0`.

**Verify:**

- Suite: only the known failures.
- Both harnesses → `edge_p5_*.txt`, with `.diff`s against P4. Paste both.

Recorded expectation, for the Opus read: a small number of end-extend
changes, concentrated on lines with a long first word, mainly on the replay
harness.

Commit:
`fix(end-snap): include a substantial word 1 in the end-path sung reference`

**Checkpoint (STOP).** Phases 0-5 are done. The executor hands off with the
Results log filled in (invocations, paths, totals, diffs) and asks Ken to
`/model` to Opus. Then:

1. **Opus reads Phases 0-5** read-only from the artifacts.
2. **Opus picks eyeball lines for Ken** from the diffs.
   - Renders: the coverage harness's `.edgesnap.ass`, and
     `edge_snap_replay.py --write-ass` at Phase 5 code.
   - Play with `mpv "<video>" --sub-file="karaoke/<stem>.<tag>.ass"`.
3. **Opus flags that `/code-review` is due** on the Phase 1-5 commits. Ken
   launches it.
4. **Ken rules on merging.** Nothing past this point runs until Opus has
   pinned Phase 6.

## Phase 6 — Run-edge generalization (interior gaps)

> **NOT EXECUTABLE AS WRITTEN (refresh 2026-09-15).** It is held for an
> Opus pinning pass after the Phase 5 checkpoint. Open items:
>
> 1. **Worked examples are unpinned.** The four tests below are described,
>    not constructed with computed values. A literal executor would have
>    to design them, which the discipline forbids.
> 2. **Interior-run reference.** "Compute ref once (unchanged semantics)"
>    puts each interior run's first word inside the words-2..n median.
>    That word's span is the one being repaired.
>    - This is the poisoning the detector lessons warn about: a stretched
>      span drags the reference down until reverb tails pass for singing.
>    - It is diluted by the rest of the line, but not absent.
>    - Decide the reference before building.
> 3. **Ownership.** Moving interior run-edge word boundaries changes
>    `PROGRAM.md` Part 2's "Word boundaries inside a placed line" row
>    (joint matcher's words, unchanged since GATE W closed). Ken rules on
>    that. If he approves, the row is rewritten in the same turn the phase
>    lands.
> 4. **Gate and sizing.**
>    - "Lines without interior gaps byte-identical" needs a mechanical
>      input filter like Phase 4's `--multi-word-only`, for the same
>      bound-coupling reason.
>    - The 388-word count is Linux; re-measure it on this corpus.
>    - The coverage harness's ASS round-trip drift matters inside
>      multi-word lines, so the replay harness is the exact read here.
>
> The design text below is kept as the starting point for that pass.

This is the biggest coverage multiplier. 388 interior words (Linux corpus)
follow an intra-line gap ≥ 0.5s and show the same artifacts, because the
ASS writer re-anchors the karaoke fill at every inter-word gap.

The change reframes both snaps from "line edge" to "run edge":

- Split each line's words into voiced runs at large gaps.
- Onset-snap each run's first word, and end-snap each run's last word.
- A line without interior gaps is one run (today's behaviour). A
  single-word line is one run of one word (Phase 4's machinery).

**Constants:**

```python
# Intra-line gaps at least this long split a line into separate voiced
# runs; each run's edges get the same repair as line edges (the ASS
# writer re-anchors the fill at every inter-word gap).
RUN_GAP_S = 0.5
```

**Structure** (keep public signatures; refactor internals):

- `_split_runs(words) -> list[tuple[int, int]]`: inclusive (first, last)
  word-index pairs, split where `words[k]["start"] - words[k-1]["end"] >=
  RUN_GAP_S`.
- `snap_line_onsets`: per line, compute the ref once (see open item 2).
  Then, for each run, apply the existing per-line onset logic to the run's
  first word `k`.
  - Bound: `words[k+1]["start"]` if `k+1` is inside the same run, else
    `words[k]["end"]`. That is the Phase 4 single-word rule: never search
    across the gap toward the next run.
  - The on-time guard evaluates at word `k`'s claimed start and span,
    exactly as it does for word 0 today.
- `snap_line_ends`: per run, apply the existing end logic to the run's last
  word.
  - Bound, when the next run is in the same line: the next run's
    first-word start minus `NEXT_LINE_GAP_S`.
  - Bound, for the line's final run: the existing next-line scan
    (`307-312`).
  - The two-pass onsets-then-ends order already guarantees that a run's
    end bound sees the next run's *snapped* start.
- Stats: snap and extend records gain `"word_idx"`, and both stats dicts
  gain `n_runs`.
  - Expect interior candidates to die on `MIN_SHIFT_S` at a higher rate
    than line edges, because whisper's interior timestamps are better.
  - That is the telemetry confirming the expansion is safe, not a bug.

**Tests (to be pinned):**

1. **Interior smeared word:** a 1.5s gap mid-line, with the word after the
   gap claimed early over the floor and singing resuming later. Expect it
   snapped to the rise, with the words before the gap untouched.
2. **Interior clipped end:** a held note before a 1.5s gap, still at sung
   level at its claimed end. Expect it extended, and capped at the next
   run's start minus `NEXT_LINE_GAP_S`.
3. **Sub-threshold gap (0.4s):** the line stays one run, and an interior
   "smeared" word is NOT touched (a regression pin for `RUN_GAP_S`).
4. **No-gap regression:** reuse the construction of an existing multi-word
   test and assert output equality with the single-run path (behaviour
   identical to Phase 5 for gap-free lines).

**Verify (to be pinned):**

- Suite green.
- Lines without interior gaps are byte-identical under a filter.
- Record how many interior candidates fire vs die on `MIN_SHIFT_S`.
- Eyeball 2-3 songs with interior snaps end to end. This is the phase most
  worth watching in mpv before trusting.

Commit: `feat(edge-snap): snap interior run edges, not just line edges`

## Phase 7 — Gated offline experiments (each: study first, STOP, report)

None of these touch production code without an explicit GO from Ken. Each
produces a script under `scripts/` plus a Results-log entry, read by Opus.

**7a. Voicing trace for the harmony blind spot.**

- **Problem.** The release trace follows RMS, so backing harmonies that
  hold the level past the lead's release drag extensions to the bound.
  These are the `to_bound` records: **202 in production's recorded snap on
  this corpus** (2026-09-15 bundles; ~240 on the 2026-07 Linux corpus).
- **Study.** Per `to_bound` line:
  - compute a frame-rate autocorrelation f0/voicing track from the same
    16 kHz mono PCM over `[claimed_end, bound]`
  - find where the pitch track active at the claimed end breaks
  - compare that against the RMS bound
- **Report** the distribution of (voicing break − RMS end), and eyeball 5
  songs.
- **GO gate:** voicing finds an earlier, plausible release for ≥ half the
  suspects, and the eyeballs agree.

**7b. Adaptive step floor.** Only if Phase 2's `n_undetectable` is material
(rule of thumb: > 5% of fired lines). Prototype in the harness:
`required_step = max(5.0, min(STEP_DB, 0.6 * (ref - p20(window))))`. Diff
which new snaps appear, and eyeball before proposing production adoption.

**7c. Sub-frame attack refinement (review #5).**

- Replace `SNAP_MARGIN_S` with a real attack locator:
  - keep the decoded PCM available (extend `rms_envelope_db` or add a
    sibling helper)
  - inside the detected rise frame, find the amplitude crossing between
    the pre and post levels, and snap there
- This deletes the margin constant and the two-frame empty lead-in.
- Update `test_reverb_tail_start_snaps_to_rise` (it asserts 2.15 for a rise
  at 2.2) with a comment, per the review. It is a deliberate tuning knob,
  so change it loudly.

**7d. Backward onset search (late starts).** Forward-only snapping cannot
fix a word whisper placed late, where the voice is already at sung level
before `w1s`. A bounded backward search breaks the "never make an on-time
line worse" invariant if it misfires. So design it only after Phases 1-6
telemetry shows the case is common, and bring the design to Ken before
implementing.

## Refresh record

### 2026-09-15 — Opus refresh against `0871216` and the Windows box

Ken asked for a refresh after the plan was found misfiled. The refresh
compared the plan against current code, callers, tests, harnesses and the
Windows corpus, and executed the plan's worked examples on scratch copies.
Scratch files were not committed: `snaprefresh/make_variants.py` builds
per-phase copies of `onset_snap.py` with the plan's changes applied
literally, and `snaprefresh/check_examples.py` runs every construction.

**Held as written:**

- **Every design decision, rejected option, constant and phase change
  (Phases 1-5).** Only one design point changed: Phase 4's gate (see below).
- **Every `onset_snap.py`, test and harness line anchor.** Since `89d28c46`
  the file only gained the `_decode_env` → `decode_env_db` rename and
  `snap_line_edges(env=)`, both line-neutral above `snap_line_edges`. The
  2026-07-12 note anticipated that merge; it has since landed (`5625d85`),
  so nothing is owed.
- **Worked-example values verified by execution:**
  - Phase 1 (current code snaps to 2.45; the gate rejects)
  - Phase 2's end-side and shift-below counters
  - Phase 3's regression pin
  - Phase 4 tests 2, 3 (5.875) and 4, and test 5's end (6.375)
  - Phase 5 (5.4 → untouched)

**Corrected:**

1. **Location and status.** Moved out of `completed/`, with a status banner
   added. PROGRAM.md's file table gains a row.
2. **Callers.** Two callers that postdate the plan are now named.
   - `lrclib_fill.py:279` calls `_sung_level_ref` for a song-wide
     reference, so Phases 4-5 must keep its default path byte-identical.
   - `evidence_veto.py` and `lrclib_fill.py` import the shared constants.
   - The stage wiring moved to `lyric_align.py:196-197,252`, with the veto
     before the snap and fills after.
3. **Environment.** Linux/conda became Windows/uv, with the library path,
   the capture-encoding rules, and a test count of 31 (was 28).
4. **Harness validity.** The 2026-07 harness is no longer valid.
   - The shipped files are already snapped, so it is blind to Phases 1, 3
     and 5.
   - Its ASS round-trip drifts inside multi-word lines.
   - It used the wrong stem on the one de-reverb-adopted song.
   - It had a Linux default folder and an outdated skip-suffix list.
   - Ken ruled for both harnesses (coverage on shipped files, exact joint
     replay with a fidelity guard). Phase 0 was rewritten accordingly.
5. **Phase 2's `test_no_rise_untouched` assertion was wrong.** Its flat
   -50 dB construction never reaches rise detection: the on-time guard
   claims it today and the Phase 1 gate claims it afterwards, so the
   planned `n_no_rise == 1` would fail. It is replaced by an `n_low_ref`
   assertion plus a new, verified no-rise test.
6. **Phases 3 and 4: expected onset values were one hop late.** The soft
   tier accepts the frame straddling the step.
   - Phase 3 pre-change: 4.65 → **4.625**.
   - Phase 4 tests 1 and 5: 3.45 → **3.425**.
   - Test 1's "61 of 121 frames sung" → **60**.
7. **Phase 4's byte-identity gate was unsound.** A one-word line's forward
   onset snap widens the previous line's end bound, so multi-word end
   records can legitimately change. It is replaced by the
   `--multi-word-only` input filter, which removes both the one-word
   records and their bound effect.
8. **Phase 4's in-silence test named no calls.** It now calls both paths
   separately.
9. **Checkpoint moved.** It was after Phase 6 and is now after Phase 5.
   Phase 6 is held for pinning (four open items in its banner).
10. **Corpus numbers.** The Linux numbers are kept as historical, and
    Windows facts were added. The `n_single_word` population counts (61
    and 21) are pre-registered as a Phase 2 gate. 7a's suspect count comes
    from production's recorded snap.
11. **Executor/judge split.** Updated to current practice: the executor
    records raw evidence, and Opus reads at the checkpoint.

### 2026-09-15 — Opus anchor refresh against `385c881` (Phase 2 pre-flight STOP)

The Phase 2 executor stopped before writing code. All three Phase 2
`onset_snap.py` anchors pointed at unrelated lines. Cause: Phase 1's own
edit (`15f4806`), which the 2026-09-15 refresh against `0871216` predates.

`git diff 0871216 385c881 -- pikaraoke/lib/onset_snap.py` accounts for the
whole shift. It has three hunks, all inside `snap_line_onsets`:

- `n_low_ref = 0`: +1 from line 191.
- The `MIN_REF_DB` gate: +4 more from line 208, so +5 from there.
- The stats dict expanded to 6 lines: +5 more, so +10 from there to the end
  of the file.

`_sung_level_ref` and `_detect_rise` sit above every hunk and did not move.
`test_onset_snap.py` gained the 14-line `test_line_in_silence_untouched` at
`:196`, which moves every test below it by +14.

Each anchor below was read off `git show 385c881:<file>`. The code was
matched by quote, not inferred from the offset.

| Phase | Anchor (quoted code / symbol) | `0871216` | `385c881` |
|---|---|---|---|
| 2 | end `new_end - w_end < MIN_SHIFT_S` rejection | 342-344 | 352-354 |
| 2 | end `n_fired += 1` | 326 | 336 |
| 2 | onset `new_start - w1s < MIN_SHIFT_S` rejection | 233-235 | 238-240 |
| 3 | `_detect_rise` trust branch `if b - i < sustain_frames or ...` | 170 | 170 |
| 3 | `test_soft_rise_just_before_word2_accepted` | 173 | 173 |
| 4a | `_sung_level_ref` | 127-141 | 127-141 |
| 4b | onset `if len(words) < 2:` gate | 194-196 | 195-197 |
| 4b | narrow-window skip `if w2s - w1s < MIN_WORD_DUR_S:` | 199 | 200 |
| 4b | `onset = _detect_rise(env, w1s, w2s, ref)` | 227 | 232 |
| 4b | clamp `new_start = min(max(...), w2s - MIN_WORD_DUR_S)` | 232 | 237 |
| 4b | end-carry `if w1e >= new_start + MIN_WORD_DUR_S:` ... `else:` | 240-243 | 245-248 |
| 4c | end `if len(words) < 2:` gate | 292-294 | 302-304 |
| 4d | `TestSnapLineOnsets.test_short_lines_skipped` | 196 | 210 |
| 4d | `TestSnapLineEnds.test_short_lines_skipped` | 343 | 357 |
| 4d | `test_single_decode_fixes_both_edges` (envelope injection) | 372 | 386 |
| 5 | `snap_line_ends` `ref = _sung_level_ref(env, words)` | 310 | 320 |
| 6 | end next-line bound scan `bound = len(env) * HOP_S` ... `break` | 297-302 | 307-312 |

The Context section's caller list was also stale. Phase 0 rewrote
`edge_snap_ass.py`, added `edge_snap_replay.py` as a new caller, and added
one line to `onset_snap_ass.py`'s skip list. The refreshed callers:

| Caller | `0871216` | `385c881` |
|---|---|---|
| `scripts/onset_snap_ass.py` `snap_line_onsets(` | 76 | 77 |
| `scripts/end_snap_ass.py` `snap_line_ends(` | 33 | 33 |
| `scripts/edge_snap_ass.py` `snap_line_onsets(` / `snap_line_ends(` | 41, 49 | 93, 105 |
| `scripts/edge_snap_replay.py` `snap_line_edges(` | (new) | 77 |

`git diff --stat 0871216 385c881` touches no other code file, so the
`lyric_align.py`, `lrclib_fill.py` and `test_lyric_align.py` anchors hold.
Phase 1's own anchors are historical now that Phase 1 has landed.

**Rule change.** Phases 2-4 each shift the numbers later phases cite, so
another refresh would go stale at the next commit. The anchor rule at the
top of the plan now says:

- the quoted code is the anchor and the number is a locator;
- a shifted number whose quoted code matches uniquely is logged and is not
  a STOP;
- absent, changed or ambiguous code is still a STOP.

The executor's STOP was correct under the old wording, which called the
anchors verified. The previous intro sentence ("re-anchor by symbol name")
contradicted the STOP-on-anchor-mismatch rule, and this change resolves
that.

No design, constant, expected value or gate changed. The Phase 2
carry-forward gate (the `edge_p1_*` totals match the Phase 1 log) is
separate from this refresh and was reported clean by the executor.

## Results log

(Per phase: invocation, artifact absolute paths, harness `total` lines and
diffs pasted verbatim. No verdicts; Opus reads at the checkpoint.)

### Phase 0

Branch `edge_snap_refine` created from `joint_catchall_refit` at `90ccdb0`.
Commits: `24df69a` (0a), plus 0b's commit (this Results-log entry rides
with it).

**0c.1 Unit suite.**

Invocation: `uv run --no-sync python -m pytest tests/unit -q`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p0_suite.txt`

```
FAILED tests/unit/test_genius.py::TestSidecarIO::test_write_overwrites_existing
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple
FAILED tests/unit/test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close
4 failed, 1516 passed, 2 skipped in 35.69s
```

Matches the known-failure set exactly.

**0c.2 Guard.**

Invocation: `uv run --no-sync python scripts/edge_snap_replay.py --folder D:/shared/pikaraoke-songs --guard`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p0_guard.txt`
Exit code: 1

```
'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM
  GUARD FAIL end_extends first_line_id=35
'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q
  GUARD PASS
'Popular' - Wicked 20th Anniversary Edition _ WICKED the Musical---22QYya-LGDY
  GUARD PASS
Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjABn8
  GUARD PASS
Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw
  GUARD FAIL onset_snaps first_line_id=33
Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg
  GUARD FAIL onset_snaps first_line_id=22
Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I
  GUARD FAIL onset_snaps first_line_id=11
HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA
  GUARD PASS
Jessie J - Domino (Official Video)---UJtB55MaoD0
  GUARD PASS
Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY
  GUARD PASS
Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY
  GUARD FAIL end_extends first_line_id=8
NSYNC - Paradise
  GUARD PASS
Pocahontas - Colors of the Wind (Blu-ray 1080p HD)---9ThO76peOw0
  GUARD PASS
Seasons of Love (HD)---UvyHuse6buY
  GUARD PASS
Stay Gold (Official Music Video) from The Outsiders – A New Broadway Musical.---XzbHPqULtdA
  GUARD PASS
The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fwLxDUQBdEg
  GUARD FAIL output_timings first_line_id=16
The Next Ten Minutes Lyrics---0j8kL24ph8U
  GUARD PASS
Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ
  GUARD FAIL end_stats:n_low_ref first_line_id=n/a
```

11/18 GUARD PASS, 7/18 GUARD FAIL. Per Process, this is a STOP -> Opus;
no song excluded, no tolerance loosened, nothing in the replay patched.

Supporting facts gathered while checking this wasn't a harness bug
before recording it as a STOP (raw evidence, not a verdict):

- This bundle's `captured_at` is `2026-07-16T20:58:17+00:00`; `fcefcce`
  (2026-09-01, the commit named in Process) postdates it, and two more
  months of `joint_catchall_refit` commits sit between capture and
  `90ccdb0`.
- The pre-existing, unmodified `scripts/replay_ytasr_third_source.py`,
  run standalone at the corpus's fixed `alpha=2.0 beta=2.0` with no
  edge-snap code involved at all, already shows recorded-vs-replayed
  differences on several of the same songs (e.g. "Defying Gravity"
  `crawl(rec>new) 4->3`; other songs' rows print `0->0`/`1->1`
  identical, so the drift is song-specific, not universal).
- On the one de-reverb-adopted song (`Wicked - For Good`), whose
  `end_stats:n_low_ref` guard check fails here: `snap_stem_path`
  resolved to the `dereverb/` file (confirmed to exist), and both the
  onset `snaps` list (6/6) and the end `extends` list (6/6) matched the
  recorded bundle byte-for-byte, including every `shift_s`/`extend_s`
  value. Only `n_low_ref` (2 recorded vs 3 replayed) differed -- a
  single line crossing the `MIN_REF_DB` threshold, consistent with
  small matcher-drift movement in that line's word timings rather than
  a stem- or veto-level bug.

**0c.3 Baseline runs.**

Replay harness.
Invocation: `uv run --no-sync python scripts/edge_snap_replay.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p0_replay.txt`

```
total songs=18
total onset n_lines=1010 n_snapped=192
total end n_extended=237 n_fired=341 n_lines=1010 n_low_ref=7
```

Coverage harness.
Invocation: `uv run --no-sync python scripts/edge_snap_ass.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p0_coverage.txt`

```
total songs=34
total onset n_lines=1823 n_snapped=3
total end n_extended=15 n_fired=364 n_lines=1823 n_low_ref=10
```

Note on artifact durability: these paths are this session's scratchpad
(`...\d51ed6ab-8aef-45a0-b94e-f5d57771998a\...`), which is
session-scoped per the harness's own environment contract. Phase 0's
Process section directs artifacts to "the session scratchpad" by name,
so this follows the plan as written; flagging it so whichever session
runs Phase 1 knows to re-derive or re-locate these files first if it is
not this same session.

### Phase 0 read-off (Opus, 2026-09-15)

Read-only judge round on the 0c.2 guard STOP. No harness, snap or matcher
code touched.

**Correction to Process.** 0c.2 names `fcefcce` as the post-capture
matcher change. `fcefcce` adds telemetry only ("Zero behaviour change: no
placement reads these"). The behaviour change between the bundles'
capture (2026-07-16/22) and `90ccdb0` in the replayed path
(`joint_match`, `candidate_match`, `windowed_realign`, `ytasr`,
`token_align`, `evidence_veto`, `onset_snap`, the chassis script) is
`ad51a86` (2026-09-10, GATE T): `ytasr.CANDIDATE_MAX_EDIT_RATIO` 0.34 ->
0.45. The bundle does not record this ratio (flagged in `ad51a86`'s own
message). `joint_match` reads it module-side at call time. Three July
commits also touch those files after the earliest capture (`443ecad`
`ytasr.py`, `6a8153d` `windowed_realign.py` + chassis, `0d9f03e`
chassis); the probe below shows they do not move the replay.

**Probe.** Rerun the unmodified 0c.2 guard with only that constant set
back to its capture-time value, module-side, as the GATE T sweep drivers
do. Scratch script (not committed), run from the repo root on `7005b74`:

```python
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "scripts"))
from pikaraoke.lib import ytasr
ytasr.CANDIDATE_MAX_EDIT_RATIO = float(sys.argv[1])
print(f"CANDIDATE_MAX_EDIT_RATIO={ytasr.CANDIDATE_MAX_EDIT_RATIO}")
folder = Path("D:/shared/pikaraoke-songs")
for p in sorted((folder / "alignment_debug").glob("*.json")):
    b = json.loads(p.read_text(encoding="utf-8"))
    if (b.get("pipeline_decisions") or {}).get("method_used") == "joint":
        print("captured_at", b.get("captured_at"), p.stem[:50])
import edge_snap_replay
sys.argv = ["edge_snap_replay.py", "--folder", str(folder), "--guard"]
raise SystemExit(edge_snap_replay.main())
```

Invocation: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 uv run --no-sync python <scratchpad>/p0judge/guard_at_ratio.py 0.34`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\4d761251-d0b5-493b-a519-1f8202696d9f\scratchpad\p0judge\guard_034.txt`
Exit code: 0

```
CANDIDATE_MAX_EDIT_RATIO=0.34
captured_at 2026-07-16T20:58:17+00:00 'Defying Gravity' - Wicked 20th Anniversary Editio
captured_at 2026-07-16T20:59:11+00:00 'Free' _ Official Lyric Video _ Sony Animation---f
captured_at 2026-07-16T21:00:54+00:00 'Popular' - Wicked 20th Anniversary Edition _ WICK
captured_at 2026-07-16T21:08:14+00:00 Beauty and the Beast (1991) - Be Our Guest [UHD]--
captured_at 2026-07-16T21:10:19+00:00 Beauty and the Beast (1991) - Belle [UHD]---otxTf5
captured_at 2026-07-16T21:11:42+00:00 Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live A
captured_at 2026-07-16T21:15:44+00:00 Ed Sheeran & Rudimental­ - Bloodstream [Official M
captured_at 2026-07-16T21:16:39+00:00 HUNTR_X 'This Is What It Sounds Like' (Music Video
captured_at 2026-07-16T21:19:58+00:00 Jessie J - Domino (Official Video)---UJtB55MaoD0
captured_at 2026-07-16T21:21:57+00:00 Josh Gad - In Summer (From 'Frozen'_Sing-Along)---
captured_at 2026-07-16T21:33:56+00:00 Mulan _ I'll Make a Man Out of You _ @disneykids--
captured_at 2026-07-16T21:38:08+00:00 NSYNC - Paradise
captured_at 2026-07-16T21:39:50+00:00 Pocahontas - Colors of the Wind (Blu-ray 1080p HD)
captured_at 2026-07-16T21:41:06+00:00 Seasons of Love (HD)---UvyHuse6buY
captured_at 2026-07-22T18:02:11+00:00 Stay Gold (Official Music Video) from The Outsider
captured_at 2026-07-16T21:43:25+00:00 The Lion King - Hakuna Matata Music Video I 4K Ult
captured_at 2026-07-16T21:45:43+00:00 The Next Ten Minutes Lyrics---0j8kL24ph8U
captured_at 2026-07-16T21:46:54+00:00 Wicked - For Good  (2025) 4K - The Girl in the Bub
```

Guard lines: all 18 songs print `  GUARD PASS` (same song order as 0c.2).

**Finding.** At the capture-time ratio the replay reproduces every joint
bundle exactly: veto, onset and end snap records, every recorded stats
key, and output timings. The 7 failures in 0c.2 are the GATE T ratio
change and nothing else. The replay harness is exact; no harness bug.

**Ruling (Opus).**

1. **Phases 1-5 proceed on the shipped ratio (0.45).** That is today's
   production matcher, so the phases measure the snap on the input it
   will actually receive. The probe proves every other part of the replay
   against recorded production. Every phase diff compares two runs at the
   same ratio, so the diffs mean what the plan says. The 0c.3 baselines
   were run at 0.45 and stand as the P0 baseline.
2. **No recapture, no guard narrowing, no per-song dig.** A recapture
   needs a GPU pass and would prove nothing the probe did not. Do not
   patch the harness to pin 0.34; the guard is a Phase 0 gate and has
   passed.
3. **Artifacts from another session.** If the `edge_p0_*` files above do
   not resolve, the Phase 1 session re-runs the two 0c.3 baseline
   invocations on `7005b74` first. Mechanical gate: both `total` lines
   must equal the ones pasted in 0c.3 exactly, else STOP -> Opus. Then
   diff Phase 1 against those fresh files.
4. **Pending review.** The `/code-review` on `24df69a` and `7005b74`
   stays pending to the Phase 5 checkpoint, alongside the snap changes.

Phase 0 is closed. Phase 1 is unblocked.

### Phase 1

New session; the prior session's `edge_p0_*` scratch files were not
assumed valid. Re-ran both 0c.3 baseline invocations unmodified on
`0d79165` (same harness code as `7005b74`) into
`...\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\p1_reverify\`.
Both `total` lines matched the ones logged under 0c.3 exactly, and a full
`diff` against the original `edge_p0_replay.txt` / `edge_p0_coverage.txt`
in that same session's `edge_snap/` folder came back empty. Gate passed;
Phase 1 diffs below are against the original `edge_p0_*` files.

**Change.** `snap_line_onsets`: low-reference gate inserted after the
`ref is None` check and before the on-time guard, `n_low_ref` initialized
alongside `snaps` and added to the onset stats dict. Matches the plan's
diff verbatim. New test `test_line_in_silence_untouched` added to
`TestSnapLineOnsets` in `tests/unit/test_onset_snap.py`, mirroring the
end-side test at the plan's stated construction.

**Suite.**

Invocation: `uv run --no-sync python -m pytest tests/unit -q`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p1_suite.txt`

```
FAILED tests/unit/test_genius.py::TestSidecarIO::test_write_overwrites_existing
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple
FAILED tests/unit/test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close
4 failed, 1517 passed, 2 skipped in 36.21s
```

Only the known failures; 1517 = 1516 + the one new test.

**Replay harness.**

Invocation: `uv run --no-sync python scripts/edge_snap_replay.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p1_replay.txt`
Diff: `diff edge_p0_replay.txt edge_p1_replay.txt > edge_p1_replay.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p1_replay.diff`

```
21c21
<   stats onset n_lines=89 n_snapped=2
---
>   stats onset n_lines=89 n_low_ref=1 n_snapped=2
41c41
<   stats onset n_lines=41 n_snapped=10
---
>   stats onset n_lines=41 n_low_ref=0 n_snapped=10
64c64
<   stats onset n_lines=62 n_snapped=11
---
>   stats onset n_lines=62 n_low_ref=1 n_snapped=11
88c88
<   stats onset n_lines=77 n_snapped=9
---
>   stats onset n_lines=77 n_low_ref=1 n_snapped=9
134c134
<   stats onset n_lines=110 n_snapped=18
---
>   stats onset n_lines=110 n_low_ref=0 n_snapped=18
156c156
<   stats onset n_lines=38 n_snapped=13
---
>   stats onset n_lines=38 n_low_ref=1 n_snapped=13
177c177
<   stats onset n_lines=74 n_snapped=10
---
>   stats onset n_lines=74 n_low_ref=0 n_snapped=10
194c194
<   stats onset n_lines=53 n_snapped=12
---
>   stats onset n_lines=53 n_low_ref=0 n_snapped=12
237c237
<   stats onset n_lines=67 n_snapped=17
---
>   stats onset n_lines=67 n_low_ref=0 n_snapped=17
261c261
<   stats onset n_lines=31 n_snapped=14
---
>   stats onset n_lines=31 n_low_ref=1 n_snapped=14
281c281
<   stats onset n_lines=47 n_snapped=0
---
>   stats onset n_lines=47 n_low_ref=0 n_snapped=0
328c328
<   stats onset n_lines=65 n_snapped=16
---
>   stats onset n_lines=65 n_low_ref=0 n_snapped=16
359c359
<   stats onset n_lines=37 n_snapped=12
---
>   stats onset n_lines=37 n_low_ref=1 n_snapped=12
379c379
<   stats onset n_lines=34 n_snapped=3
---
>   stats onset n_lines=34 n_low_ref=0 n_snapped=3
402c402
<   stats onset n_lines=38 n_snapped=11
---
>   stats onset n_lines=38 n_low_ref=0 n_snapped=11
418c418
<   stats onset n_lines=40 n_snapped=4
---
>   stats onset n_lines=40 n_low_ref=2 n_snapped=4
467c467
<   stats onset n_lines=71 n_snapped=24
---
>   stats onset n_lines=71 n_low_ref=1 n_snapped=24
471d470
<   rec onset L19 +0.150
482c481
<   stats onset n_lines=36 n_snapped=6
---
>   stats onset n_lines=36 n_low_ref=4 n_snapped=5
485c484
< total onset n_lines=1010 n_snapped=192
---
> total onset n_lines=1010 n_low_ref=13 n_snapped=191
```

**Coverage harness.**

Invocation: `uv run --no-sync python scripts/edge_snap_ass.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p1_coverage.txt`
Diff: `diff edge_p0_coverage.txt edge_p1_coverage.txt > edge_p1_coverage.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p1_coverage.diff`

```
3c3
<   stats onset n_lines=60 n_snapped=1
---
>   stats onset n_lines=60 n_low_ref=2 n_snapped=1
7c7
<   stats onset n_lines=51 n_snapped=0
---
>   stats onset n_lines=51 n_low_ref=1 n_snapped=0
10c10
<   stats onset n_lines=40 n_snapped=0
---
>   stats onset n_lines=40 n_low_ref=0 n_snapped=0
14c14
<   stats onset n_lines=51 n_snapped=0
---
>   stats onset n_lines=51 n_low_ref=1 n_snapped=0
19c19
<   stats onset n_lines=56 n_snapped=0
---
>   stats onset n_lines=56 n_low_ref=0 n_snapped=0
24c24
<   stats onset n_lines=27 n_snapped=0
---
>   stats onset n_lines=27 n_low_ref=0 n_snapped=0
28c28
<   stats onset n_lines=39 n_snapped=0
---
>   stats onset n_lines=39 n_low_ref=0 n_snapped=0
31c31
<   stats onset n_lines=77 n_snapped=0
---
>   stats onset n_lines=77 n_low_ref=1 n_snapped=0
34c34
<   stats onset n_lines=101 n_snapped=0
---
>   stats onset n_lines=101 n_low_ref=0 n_snapped=0
37c37
<   stats onset n_lines=37 n_snapped=0
---
>   stats onset n_lines=37 n_low_ref=1 n_snapped=0
41c41
<   stats onset n_lines=38 n_snapped=0
---
>   stats onset n_lines=38 n_low_ref=0 n_snapped=0
45c45
<   stats onset n_lines=47 n_snapped=0
---
>   stats onset n_lines=47 n_low_ref=0 n_snapped=0
48c48
<   stats onset n_lines=32 n_snapped=0
---
>   stats onset n_lines=32 n_low_ref=0 n_snapped=0
51c51
<   stats onset n_lines=47 n_snapped=0
---
>   stats onset n_lines=47 n_low_ref=0 n_snapped=0
55c55
<   stats onset n_lines=63 n_snapped=0
---
>   stats onset n_lines=63 n_low_ref=0 n_snapped=0
59c59
<   stats onset n_lines=54 n_snapped=0
---
>   stats onset n_lines=54 n_low_ref=2 n_snapped=0
62c62
<   stats onset n_lines=29 n_snapped=0
---
>   stats onset n_lines=29 n_low_ref=1 n_snapped=0
65c65
<   stats onset n_lines=84 n_snapped=0
---
>   stats onset n_lines=84 n_low_ref=1 n_snapped=0
73c73
<   stats onset n_lines=120 n_snapped=1
---
>   stats onset n_lines=120 n_low_ref=0 n_snapped=1
77c77
<   stats onset n_lines=103 n_snapped=0
---
>   stats onset n_lines=103 n_low_ref=2 n_snapped=0
81c81
<   stats onset n_lines=79 n_snapped=1
---
>   stats onset n_lines=79 n_low_ref=0 n_snapped=1
86c86
<   stats onset n_lines=54 n_snapped=0
---
>   stats onset n_lines=54 n_low_ref=0 n_snapped=0
90c90
<   stats onset n_lines=36 n_snapped=0
---
>   stats onset n_lines=36 n_low_ref=0 n_snapped=0
93c93
<   stats onset n_lines=49 n_snapped=0
---
>   stats onset n_lines=49 n_low_ref=0 n_snapped=0
97c97
<   stats onset n_lines=75 n_snapped=0
---
>   stats onset n_lines=75 n_low_ref=0 n_snapped=0
102c102
<   stats onset n_lines=53 n_snapped=0
---
>   stats onset n_lines=53 n_low_ref=0 n_snapped=0
107c107
<   stats onset n_lines=37 n_snapped=0
---
>   stats onset n_lines=37 n_low_ref=1 n_snapped=0
111c111
<   stats onset n_lines=25 n_snapped=0
---
>   stats onset n_lines=25 n_low_ref=0 n_snapped=0
114c114
<   stats onset n_lines=38 n_snapped=0
---
>   stats onset n_lines=38 n_low_ref=0 n_snapped=0
118c118
<   stats onset n_lines=32 n_snapped=0
---
>   stats onset n_lines=32 n_low_ref=0 n_snapped=0
123c123
<   stats onset n_lines=33 n_snapped=0
---
>   stats onset n_lines=33 n_low_ref=2 n_snapped=0
127c127
<   stats onset n_lines=67 n_snapped=0
---
>   stats onset n_lines=67 n_low_ref=1 n_snapped=0
130c130
<   stats onset n_lines=29 n_snapped=0
---
>   stats onset n_lines=29 n_low_ref=3 n_snapped=0
133c133
<   stats onset n_lines=60 n_snapped=0
---
>   stats onset n_lines=60 n_low_ref=0 n_snapped=0
136c136
< total onset n_lines=1823 n_snapped=3
---
> total onset n_lines=1823 n_low_ref=19 n_snapped=3
```

No gate failure: suite matches the known-failure set, both diffs are
`n_low_ref`-counter noise plus exactly one vanished onset record
(replay harness, `L19`). Commit: (this entry rides with it).

### Phase 1 read-off (Opus, 2026-09-15)

**Checked against the record.**

- `git show 15f4806 -- pikaraoke/lib/onset_snap.py tests/unit/test_onset_snap.py`:
  the gate, its placement (after `ref is None`, before the on-time guard),
  the counter and the stats key match the Phase 1 block verbatim. The test
  uses the stated construction and asserts untouched, `n_low_ref == 1`,
  `n_snapped == 0`.
- Both pasted diffs were regenerated from the executor's artifacts with
  `diff edge_p0_X.txt edge_p1_X.txt | cmp - edge_p1_X.diff`: identical, for
  both harnesses.
- Record views (Process "Record view" filter), P0 vs P1:
  - replay: `437d436 <   rec onset L19 +0.150` and nothing else
  - coverage: empty
- `total end` lines are unchanged in both harnesses.
- The vanished record belongs to
  `Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ`,
  the one de-reverb-adopted song. Its P0 end records are
  `L5 L6 L20 L22 L28 L29`: there is no `L18` end record in P0 or P1.

**Probe on the vanished record.** Script
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\4d761251-d0b5-493b-a519-1f8202696d9f\scratchpad\p1judge\probe_l19.py`
calls `edge_snap_replay._replay_song` on that bundle (checked-out code at
`15f4806`, shipped ytasr ratio). It prints each multi-word line's
`_sung_level_ref` against the snap stem, and the envelope across L19.
Output:
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\4d761251-d0b5-493b-a519-1f8202696d9f\scratchpad\p1judge\probe_l19.txt`.

Stem: `...---wzSeub9W4QQ---dereverb.m4a`. Lines with ref < `MIN_REF_DB`:
`L4 -120.0`, `L19 -50.0`, `L31 -59.3`, `L35 -57.2`.

| word (L19, "It's hard to unsee what you've seen") | start-end | median dB | max dB |
|---|---|---|---|
| It's | 81.200-81.520 | -53.5 | -38.7 |
| hard | 81.520-82.400 | -62.8 | -38.8 |
| to | 82.400-82.720 | -48.8 | -33.2 |
| unsee | 82.720-84.080 | -47.0 | -24.0 |
| what | 84.080-84.400 | -45.2 | -29.1 |
| you've | 84.400-84.640 | -48.8 | -39.5 |
| seen | 84.640-86.640 | -71.1 | -24.6 |

Envelope excerpt at word 1: 81.200 -60.4, 81.375 -54.3, 81.400 -48.0,
81.425 -40.6, 81.450 -38.7, holding -39 to -42 through 81.800. The P0 snap
put word 1 at 81.35, i.e. the rise at 81.40 minus the snap margin.

**Finding.**

1. Both recorded expectations hold.
   - Onset records vanished only on a line whose reference is below
     `MIN_REF_DB`: one record, L19 at -50.0.
   - The "end record may change on the line before" clause did not trigger
     anywhere. L18 has no end record in either run, and no end record or
     end total moved.
2. The other 12 replay and 19 coverage `n_low_ref` lines produced no
   record change: the gate claimed lines that the guard or detector already
   left alone.
3. **The one lost record was a correct snap on a correctly placed line.**
   This is not the "misplaced over near-silence" case that `MIN_REF_DB`'s
   comment describes.
   - Every L19 word has voiced peaks between -24 and -40 dB.
   - The reference sits at -50 because the de-reverbed stem drops to
     -65..-120 dB between the words of a sparse, speech-like delivery. Word
     spans that straddle those gaps drag the median below the floor.
   - The snap it cost was +0.150, exactly `MIN_SHIFT_S`.
   - The end path has applied the same gate on the same reference since
     before Phase 1. L19 never reaches it there: its bound check at
     `onset_snap.py:313` exits first, because L20 starts at 86.80, giving
     a bound of 86.70, only 0.06s past L19's end at 86.64.
4. The cost is one record at jitter level on one song. That is no reason to
   STOP or retune: the plan names no constant to tune here, and Phase 1
   gives the onset path the gate the end path already had.

**Ruling.**

1. Phase 1 is accepted as committed (`15f4806`). No re-run, no change.
2. **Phase 2 is unblocked.**
   - Diff it against the executor's `edge_p1_*` files above if they still
     resolve.
   - Otherwise re-run both harnesses on `15f4806` first. Both `total` lines
     must match those pasted in "### Phase 1" exactly, else STOP → Opus.
3. **Carry to the Phase 4 read, not a gate.** A floor-level reference also
   comes from gap-heavy delivery on the de-reverbed stem, not only from
   misplacement. When Phase 4's single-word reference is read, check the
   `Wicked - For Good` one-word lines by hand before treating `n_low_ref`
   rejections there as misplaced lines.
4. `/code-review` on the Phase 0-1 commits stays pending until the Phase 5
   checkpoint.

**Process note.** The Phase 1 entry's closing line ("counter noise") and
the commit body ("Both harnesses confirm") characterise the diff. Process
asks for none. The record itself is complete and verbatim, so nothing is
re-run for it.
