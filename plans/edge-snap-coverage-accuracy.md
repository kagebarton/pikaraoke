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

*Phase 3 read-off note (Opus, 2026-09-15):* this expectation was unsized and
did not hold: both diffs were empty. The branch needs the bound inside the
stem's final 75 ms, and no line on either corpus comes within 3.45 s (12.8 s
for single-word lines at Phase 4's bound). See "### Phase 3 read-off".

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

*Phase 3 read-off note (Opus, 2026-09-15):* carried from 2026-07 unsized,
like Phase 3's, which did not hold. For the read only: a contrary diff is not
a STOP.

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
> 3. **Ownership. ANSWERED 2026-09-17 — see "### Phase 6 scope ruling" in
>    the Results log.** Ken: loudness is not a usable timing indicator
>    *inside* a line, because lines rarely contain long pauses. That kills
>    the general form and leaves only the narrow one this phase already
>    specifies (runs separated by a real gap ≥ `RUN_GAP_S`, where the
>    envelope does have something to see). `PROGRAM.md` Part 2's "Word
>    boundaries inside a placed line" row is NOT reopened for the general
>    case; whether the narrow case justifies rewriting it at all is a live
>    question, and rests on the re-measured interior-gap count in item 4.
> 4. **Gate and sizing.**
>    - "Lines without interior gaps byte-identical" needs a mechanical
>      input filter like Phase 4's `--multi-word-only`, for the same
>      bound-coupling reason.
>    - ~~The 388-word count is Linux; re-measure it on this corpus.~~
>      **MEASURED 2026-09-17 — see "### Phase 6 interior-gap count" in the
>      Results log.** 148 split sites on the replay read (18 joint songs),
>      406 on the shipped corpus (34 songs) -- the same order as the Linux
>      388. 15-19% of lines, every song in both populations. The phase is
>      NOT small, so it cannot be closed on size; what remains unmeasured
>      is how many of those sites the snap would actually *move*, which
>      needs the detector run against run edges.
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

*Phase 2 read-off note (Opus, 2026-09-15):* `n_undetectable` overcounts. At
least 24 of its 50 replay lines did find a rise, so it is not the "cannot
qualify" population. Size and trigger 7b on lines that are both
undetectable and `n_no_rise`, bounded above by `n_no_rise`, on the replay
harness. Re-pin this when Phase 7 is pinned. See "### Phase 2 read-off".

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

### Phase 2

`edge_p1_*.txt` (Phase 1's scratchpad files) still resolved; their
`total onset` lines matched the ones pasted under Phase 1 exactly. No
re-run. Phase 2 diffs below are against those files.

**Change.** `snap_line_onsets`: `n_fired`, `n_no_rise`, `n_below_min_shift`,
`n_undetectable`, `n_single_word` added. `n_fired` and the `n_undetectable`
diagnostic (`ref - p20 < STEP_DB`, `p20` the 20th percentile of
`env[lo:hi]` over `[w1s, w2s]`) are computed once the on-time guard passes,
before `_detect_rise`. `n_no_rise` increments at the `onset is None`
branch, `n_below_min_shift` at the `new_start - w1s < MIN_SHIFT_S` branch,
`n_single_word` at the `len(words) < 2` gate when `len(words) == 1`.
Comment added: `n_fired == n_snapped + n_no_rise + n_below_min_shift`.

`snap_line_ends`: `n_below_min_shift` and `n_single_word` added; the
existing `n_fired` untouched. `n_below_min_shift` increments at the
`new_end - w_end < MIN_SHIFT_S` branch, `n_single_word` at the
`len(words) < 2` gate. Comment added:
`n_fired == n_extended + n_below_min_shift`.

Tests: `test_no_rise_untouched` now asserts `n_low_ref == 1`,
`n_fired == 0` (its flat -50dB construction is claimed by the Phase 1 gate
before rise detection, per the plan's Refresh record correction 5). New
`test_step_below_threshold_counts_no_rise` added to `TestSnapLineOnsets` at
the plan's stated construction. `test_shift_below_jitter_threshold_untouched`
and `test_sub_jitter_extension_untouched` extended with the stated stats
assertions.

**Suite.**

Invocation: `uv run --no-sync python -m pytest tests/unit -q`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p2_suite.txt`

```
FAILED tests/unit/test_genius.py::TestSidecarIO::test_write_overwrites_existing
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple
FAILED tests/unit/test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close
4 failed, 1518 passed, 2 skipped in 33.45s
```

Only the known four; 1518 = 1517 + the one new test.

**Replay harness.**

Invocation: `uv run --no-sync python scripts/edge_snap_replay.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p2_replay.txt`
Diff: `diff edge_p1_replay.txt edge_p2_replay.txt > edge_p2_replay.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p2_replay.diff`

Record view (Process "Record view" filter) against `edge_p1_replay.txt`:
empty.

```
total songs=18
total onset n_below_min_shift=125 n_fired=344 n_lines=1010 n_low_ref=13 n_no_rise=28 n_single_word=21 n_snapped=191 n_undetectable=50
total end n_below_min_shift=104 n_extended=237 n_fired=341 n_lines=1010 n_low_ref=7 n_single_word=21
```

**Coverage harness.**

Invocation: `uv run --no-sync python scripts/edge_snap_ass.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p2_coverage.txt`
Diff: `diff edge_p1_coverage.txt edge_p2_coverage.txt > edge_p2_coverage.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p2_coverage.diff`

Record view (Process "Record view" filter) against `edge_p1_coverage.txt`:
empty.

```
total songs=34
total onset n_below_min_shift=623 n_fired=688 n_lines=1823 n_low_ref=19 n_no_rise=62 n_single_word=61 n_snapped=3 n_undetectable=152
total end n_below_min_shift=349 n_extended=15 n_fired=364 n_lines=1823 n_low_ref=10 n_single_word=61
```

**Population gate.** `n_single_word`, pre-registered: coverage onset 61 /
end 61, replay onset 21 / end 21. Observed: coverage onset 61 / end 61,
replay onset 21 / end 21.

Suite: known failures only. Both record-view diffs: empty. Commit: (this
entry rides with it).

### Phase 2 read-off (Opus, 2026-09-15)

**Checked against the record.**

- `git show 1d90960 -- pikaraoke/lib/onset_snap.py tests/unit/test_onset_snap.py`,
  against the Phase 2 block (anchors per `7ba3bc8`):
  - Onset: `n_single_word` inside the `len(words) < 2` gate, only when
    `len(words) == 1`. `n_fired` sits after the on-time guard's `continue`,
    before `_detect_rise`. The `n_undetectable` `lo`/`hi`/`p20` block is the
    plan's text verbatim, count-and-continue. `n_no_rise` is in the
    `onset is None` branch and `n_below_min_shift` in the
    `new_start - w1s < MIN_SHIFT_S` branch. The invariant comment and the
    five stats keys are present.
  - End: `n_below_min_shift` in the `new_end - w_end < MIN_SHIFT_S` branch,
    `n_fired += 1` unmoved, `n_single_word` at the gate, invariant comment
    and two stats keys present.
  - All three Phase 2 anchors matched their `7ba3bc8` line numbers at
    `385c881`; no drift to log.
  - The `n_undetectable` block adds only reads. `lo <= len(env) - 1` and
    `hi >= lo + 1` keep `env[lo:hi]` non-empty for any non-empty `env`, and
    an empty `env` never reaches it (`_sung_level_ref` returns None first).
  - Tests: the four changes match the Phase 2 block's constructions and
    assertions. `uv run --no-sync python -m pytest tests/unit/test_onset_snap.py -q`
    at `1d90960`: `33 passed`.
- Both `edge_p1_*.txt` and `edge_p2_*.txt` re-read. Record views (Process
  "Record view" filter), P1 vs P2: empty for both harnesses. Every
  pre-existing total key (`n_lines`, `n_low_ref`, `n_snapped`, `n_extended`,
  end `n_fired`) is equal between P1 and P2 in both harnesses.
- Invariants on the pasted totals:

| harness | path | invariant | values | holds |
|---|---|---|---|---|
| replay | onset | `n_fired == n_snapped + n_no_rise + n_below_min_shift` | 344 = 191 + 28 + 125 | yes |
| replay | end | `n_fired == n_extended + n_below_min_shift` | 341 = 237 + 104 | yes |
| coverage | onset | `n_fired == n_snapped + n_no_rise + n_below_min_shift` | 688 = 3 + 62 + 623 | yes |
| coverage | end | `n_fired == n_extended + n_below_min_shift` | 364 = 15 + 349 | yes |

- Per song, so offsetting errors can't hide in the totals. Script
  `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\4d761251-d0b5-493b-a519-1f8202696d9f\scratchpad\p2judge\invariants.py`
  over the executor's `edge_p2_*.txt` `  stats ` lines. Output
  (`...\p2judge\invariants.txt`):

```
replay stats_lines=36 invariant_violations=0 onset_fired=344 n_undetectable=50 n_no_rise=28 sum_over_songs_max0(n_undetectable-n_no_rise)=24
coverage stats_lines=68 invariant_violations=0 onset_fired=688 n_undetectable=152 n_no_rise=62 sum_over_songs_max0(n_undetectable-n_no_rise)=93
```

- Population gate: `n_single_word` coverage 61/61, replay 21/21, equal to
  pre-registration.

**Finding.**

1. Phase 2 is exactly the spec'd change. Both gates pass, both invariants
   hold per song, and no behaviour moved.
2. **`n_undetectable` does not measure what 7b's trigger reads it as.** The
   Phase 2 block calls it "lines where the step detector cannot qualify a
   rise", but `ref - p20 < STEP_DB` only says the window's quiet floor sits
   within 10 dB of the sung level. A rise can still qualify when the step
   lands above the reference. The record shows this directly: summed over
   songs, at least 24 of 50 replay lines and 93 of 152 coverage lines
   counted as undetectable are in excess of that song's `n_no_rise`, i.e.
   they did find a rise. The proxy is a plan design error (Opus refresh),
   not an executor error: the code is the plan's text verbatim.
3. Consequence for 7b's trigger ("`n_undetectable` > 5% of fired lines"):
   read literally it fires at 50/344 replay and 152/688 coverage, but most
   of that is lines the detector already handles. The population a lower
   step floor could add snaps to is bounded by `n_no_rise` (28 replay,
   62 coverage). That bound alone is also above 5% of fired lines, so the
   literal outcome does not flip; the size 7b quotes must not come from
   `n_undetectable`. The coverage harness's fired count is dominated by
   already-snapped shipped lines (623 below `MIN_SHIFT_S`), so 7b sizes on
   the replay harness.
4. Minor: no unit test asserts `n_undetectable`. Its test construction
   would give 1 (`ref - p20` = 9 < 10). Carried to the Phase 5 review; not a
   gate.

**Ruling.**

1. Phase 2 is accepted as committed (`1d90960`). No re-run, no change.
2. **Phase 3 is unblocked.** Diff it against the executor's `edge_p2_*`
   files above if they still resolve. Otherwise re-run both harnesses on
   `1d90960` first; both `total` lines must match those pasted in
   "### Phase 2" exactly, else STOP → Opus.
3. 7b is annotated in place (see its "Phase 2 read-off note"). Its trigger
   and sizing are re-pinned when Phase 7 is pinned, not now. Phases 3-5 do
   not read `n_undetectable`.
4. `/code-review` on the Phase 0-2 commits stays pending until the Phase 5
   checkpoint. Phase 2 alone is simple enough that self-review covers it.

### Phase 3

`edge_p2_*.txt` (Phase 2's scratchpad files) still resolved; their `total`
lines matched the ones pasted under Phase 2 exactly. No re-run. Phase 3
diffs below are against those files.

**Change.** `_detect_rise`: `b` split into `b_word2 = int(t1 / HOP_S)` and
`b_env = len(env) - EDGE_FRAMES`. The trust branch (`b - i < sustain_frames`)
now returns only when `b_word2 <= b_env`, else `continue`s the scan instead
of trusting a rise whose remaining room was the envelope running out.
Matches the plan's diff verbatim. New test
`test_rise_truncated_by_stem_end_rejected` added to `TestSnapLineOnsets` at
the plan's stated construction; `test_soft_rise_just_before_word2_accepted`
(the intended-trust case this change must not break) still passes,
unchanged.

**Suite.**

Invocation: `uv run --no-sync python -m pytest tests/unit -q`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p3_suite.txt`

```
FAILED tests/unit/test_genius.py::TestSidecarIO::test_write_overwrites_existing
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple
FAILED tests/unit/test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close
4 failed, 1519 passed, 2 skipped in 37.56s
```

Only the known four; 1519 = 1518 + the one new test.

**Replay harness.**

Invocation: `uv run --no-sync python scripts/edge_snap_replay.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p3_replay.txt`
Diff: `diff edge_p2_replay.txt edge_p3_replay.txt > edge_p3_replay.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p3_replay.diff`

Diff: empty.

**Coverage harness.**

Invocation: `uv run --no-sync python scripts/edge_snap_ass.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p3_coverage.txt`
Diff: `diff edge_p2_coverage.txt edge_p3_coverage.txt > edge_p3_coverage.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p3_coverage.diff`

Diff: empty.

**Against the plan's recorded expectation** ("a handful of onset records
near song ends disappear, mainly on the replay harness"): both diffs came
back empty. Population probe (read-only; reuses
`edge_snap_replay._replay_song` / `onset_snap_ass.parse_ass_lines` and
`onset_snap`'s own `ref is None` / `ref < MIN_REF_DB` / `MIN_WORD_DUR_S`
gates unmodified, up to the point `snap_line_onsets` would call
`_detect_rise`): among every multi-word line in both corpora that reaches
`_detect_rise`, `b_word2 = int(w2s / HOP_S)` compared against
`b_env = len(env) - EDGE_FRAMES`.

Script (replay, 18 songs): `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\probe_p3_population.py`
Output: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\probe_p3_population.txt`: `n_env_limited_candidates=0`

Script (coverage, 34 songs): `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\probe_p3_coverage.py`
Output: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\probe_p3_coverage_out.txt`: `n_env_limited_candidates=0`

Suite: known failures only. Commit: (this entry rides with it).

### Phase 3 read-off (Opus, 2026-09-15)

**Checked against the record.**

- `git show 1e05ceb -- pikaraoke/lib/onset_snap.py tests/unit/test_onset_snap.py`:
  the `_detect_rise` hunk is the plan's diff verbatim (`b_word2`, `b_env`,
  `b = min(b_word2, b_env)`, trust branch returns only on
  `b_word2 <= b_env`, else `continue`; the median branch is unchanged). The
  new test is the plan's construction verbatim. No other code changed.
- Diff files: `edge_p3_replay.diff` and `edge_p3_coverage.diff` are 0 bytes.
  They diff the full outputs, `total` lines included, so the P3 totals equal
  the P2 totals pasted under "### Phase 2".
- Snap tests at `1e05ceb`: `34 passed` (`uv run --no-sync python -m pytest
  tests/unit/test_onset_snap.py -q`).
- **Positive control** (the empty harness diffs make the unit test the only
  evidence the change is live). Scratch worktree at `1d90960` with the
  `1e05ceb` test file copied in, run with `PYTHONPATH` set to the worktree
  (module path printed from the worktree, confirming the old code loaded):

  ```
  E       AssertionError: assert {'end': 5.4, 'start': 4.625, 'words': [{'end': 4.95, 'start': 4.625, 'word': 'w0'}, {'end': 5.4, 'start': 4.95, 'word': 'w1'}]} is {'end': 5.4, 'start': 3.0, 'words': [{'end': 4.6, 'start': 3.0, 'word': 'w0'}, {'end': 5.4, 'start': 4.95, 'word': 'w1'}]}
  FAILED tests/unit/test_onset_snap.py::TestSnapLineOnsets::test_rise_truncated_by_stem_end_rejected
  1 failed, 1 passed, 32 deselected in 0.81s
  ```

  Pre-change the line snaps to 4.625, as the plan recorded; the paired
  `test_soft_rise_just_before_word2_accepted` passes on both commits.
  Worktree removed afterwards.

**The executor's probe.** Its condition, `int(w2s / HOP_S) > len(env) -
EDGE_FRAMES`, is the exact term that separates the old and new code paths:
when `b_word2 <= b_env`, `b` and both branches are unchanged. So "zero such
lines" and "empty diff" are the same fact, and the probe logic is sound. It
prints no denominator, though (songs iterated, lines examined), so a zero from
it cannot be told apart from an empty loop. Independent re-check with
denominators and no line filters (a superset of the lines that reach
`_detect_rise`). `margin = b_env - int(bound / HOP_S)`, and the changed branch
needs `margin < 0`. Multi-word bound is word 2's start (Phase 3 as shipped);
single-word bound is word 1's end (the bound Phase 4 will pass).

Script: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\4d761251-d0b5-493b-a519-1f8202696d9f\scratchpad\p3judge\margins.py`
Output: `...\p3judge\margins.txt`

```
coverage songs=34 multi_lines=1762 multi_min_margin_s=3.45 multi_neg=0 single_lines=61 single_min_margin_s=12.80 single_neg=0 min_tail_after_last_word_s=0.16
replay songs=18 multi_lines=827 multi_min_margin_s=3.85 multi_neg=0 single_lines=21 single_min_margin_s=31.88 single_neg=0 min_tail_after_last_word_s=0.14
```

Song counts match both harnesses; single-word counts match Phase 2's
`n_single_word` gate (61 / 21).

**Findings.**

1. Phase 3 is the exact specified change and it is live (positive control).
   The empty diffs are correct, not a harness or implementation fault.
2. **The recorded expectation was wrong, and the error is the plan's.** It
   came from the 2026-07 text ("expect a handful of snaps near song ends to
   disappear") and the 2026-09-15 refresh carried it forward without sizing
   it. The changed branch does not fire "near the end of a song". It fires
   only when the bound lands inside the final `EDGE_FRAMES` hops (75 ms) of
   the stem, which requires a line's word 2 to *start* in that sliver. The
   closest word 2 on either corpus starts 3.45 s before the stem end. Songs
   end on an outro or trailing audio, and a line's *last* word (at best
   0.14 s from the end) is never its word 2 unless the line is two words that
   both land in the last 75 ms.
3. **The Phase 3 motivation does not hold on this corpus either.** The plan
   says Phase 4 "will feed this branch more cases near the stem end". With
   Phase 4's bound (word 1's claimed end), the closest single-word line is
   12.8 s clear. So the guard stays inert through Phase 4 here. It is kept:
   the unit test shows it rejects a real false snap when a stem ends
   mid-phrase (a truncated or clipped stem), it is a few lines, and it
   changes nothing on this corpus.
4. Probes that report a zero must print their denominators. Not a gate; a
   note for the executor prompt.
5. Phase 5's recorded expectation ("a small number of end-extend changes,
   concentrated on lines with a long first word") was carried from 2026-07
   the same way and is equally unsized. It remains for-the-read only; a
   contrary diff there is not a STOP.

**Ruling.**

1. Phase 3 is accepted as committed (`1e05ceb`). No re-run, no change.
2. **Phase 4 is unblocked.** Diff it against the executor's `edge_p3_*`
   files above if they still resolve. Otherwise re-run both harnesses on
   `1e05ceb` first; both `total` lines must match those pasted in
   "### Phase 2" exactly (P3 equals P2), else STOP → Opus. The
   `--multi-word-only` re-run on `1e05ceb` is already part of Phase 4's own
   Verify.
3. The Phase 1 read-off's hand-check (the de-reverbed song's one-word lines
   before reading `n_low_ref` rejections as misplacement) still applies at
   the Phase 4 read.
4. `/code-review` on the Phase 0-3 commits stays pending until the Phase 5
   checkpoint. Phase 3 alone is simple enough that self-review covers it.

### Phase 4

`edge_p3_*.txt` (Phase 3's scratchpad files) still resolved; used directly
as the P3 baseline per the Phase 3 read-off's ruling 2 ("diff it against
the executor's `edge_p3_*` files above if they still resolve"). No re-run
against Phase 2 totals was needed.

**Change.**

- 4a `_sung_level_ref`: new module constant `SINGLE_WORD_REF_PCT = 80.0`.
  When `len(words) == 1`, returns the 80th percentile over word 1's own
  claimed span (same index construction and bounds filter as the existing
  path); the `len(words) >= 2` path is untouched.
- 4b `snap_line_onsets`: the `len(words) < 2` gate replaced with
  `if not words:`; `n_single_word` now counts every one-word line seen
  (previously only those skipped). `w2s` eliminated in favour of
  `bound = words[1]["start"] if len(words) >= 2 else words[0]["end"]`,
  used at the narrow-window skip, the `_detect_rise` call and the clamp
  (the three sites the plan names), plus the end-carry branch's fallback
  bound (the plan's fourth, discussed site: "no special-casing needed").
- 4c `snap_line_ends`: the `len(words) < 2` gate replaced the same way;
  nothing else changed (`words[-1]` already generalizes to a one-word
  list; confirmed by reading the function, no other line references word
  2).
- Docstrings updated on `_sung_level_ref`, `snap_line_onsets` (the
  known-limitation note: `_detect_rise`'s continuity check now demands the
  voice hold to the claimed end for a single-word line) and
  `snap_line_ends` (the ordering-dividend note).

**Flagged for the read (not a STOP): a fifth `w2s` site the plan doesn't
name.** Phase 4's text is frozen at `385c881`, before Phase 2 landed.
Phase 2 added a `w2s` reference that the plan's "use `bound` everywhere
`w2s` is used today" list does not enumerate: the `n_undetectable`
diagnostic's `hi = min(max(int(w2s / HOP_S), lo + 1), len(env))`. Since
`bound` replaces `w2s` as a variable (the assignment
`w2s = words[1]["start"]` no longer exists), leaving this occurrence as
literal `w2s` would crash on a single-word line before ever reaching it.
Applied the plan's own stated generalization rule to this occurrence too,
rather than leaving it or inventing an alternative. No design judgement
beyond that stated rule was exercised.

**Suite.**

Invocation: `uv run --no-sync python -m pytest tests/unit -q`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p4_suite.txt`

```
FAILED tests/unit/test_genius.py::TestSidecarIO::test_write_overwrites_existing
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple
FAILED tests/unit/test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close
4 failed, 1524 passed, 2 skipped in 32.60s
```

Only the known four; 1524 = 1519 + 5 new tests. `tests/unit/test_onset_snap.py`
alone (`uv run --no-sync python -m pytest tests/unit/test_onset_snap.py -q`):
34 -> 39 passed. `tests/unit/test_lrclib_fill.py` (the other
`_sung_level_ref` caller, run separately): 28 passed.

New tests: `test_single_word_smeared_start_snaps`,
`test_single_word_on_time_untouched`, `test_single_word_in_silence_untouched`
(`TestSnapLineOnsets`); `test_single_word_clipped_end_extends`
(`TestSnapLineEnds`); `test_single_word_both_edges` (`TestSnapLineEdges`).
Both `test_short_lines_skipped` renamed to `test_empty_words_skipped`, the
one-word case removed per the plan (moved to the new tests).

**Supplementary check (not in the plan's Verify list): per-line invariant
audit.** Read-only, reparses the harnesses' own printed `stats`/`total`
lines; no new logic beyond arithmetic already implied by the two
Phase-2-documented invariants. Checks both invariants
(`n_fired == n_snapped + n_no_rise + n_below_min_shift` onset;
`n_fired == n_extended + n_below_min_shift` end) on every per-song line of
both Phase 4 outputs, not just the totals.

Script: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\check_invariants.py`

```
edge_p4_coverage.txt: onset_lines_checked=35 end_lines_checked=35 violations=0
edge_p4_replay.txt: onset_lines_checked=19 end_lines_checked=19 violations=0
```

**Replay harness (unfiltered).**

Invocation: `uv run --no-sync python scripts/edge_snap_replay.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p4_replay.txt`
Diff: `diff edge_p3_replay.txt edge_p4_replay.txt > edge_p4_replay.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p4_replay.diff`

```
20a21
>   rec end [1w] L88 +4.450
22c23
<   stats end n_below_min_shift=2 n_extended=17 n_fired=19 n_lines=89 n_low_ref=0 n_single_word=3
---
>   stats end n_below_min_shift=2 n_extended=18 n_fired=20 n_lines=89 n_low_ref=0 n_single_word=3
56a58
>   rec end [1w] L16 +0.285
64,65c66,67
<   stats onset n_below_min_shift=6 n_fired=18 n_lines=62 n_low_ref=1 n_no_rise=1 n_single_word=2 n_snapped=11 n_undetectable=2
<   stats end n_below_min_shift=6 n_extended=9 n_fired=15 n_lines=62 n_low_ref=0 n_single_word=2
---
>   stats onset n_below_min_shift=7 n_fired=19 n_lines=62 n_low_ref=1 n_no_rise=1 n_single_word=2 n_snapped=11 n_undetectable=2
>   stats end n_below_min_shift=6 n_extended=10 n_fired=16 n_lines=62 n_low_ref=0 n_single_word=2
96a99
>   rec onset [1w] L22 +0.495
117a121
>   rec end [1w] L22 +0.150
134,135c138,139
<   stats onset n_below_min_shift=13 n_fired=34 n_lines=110 n_low_ref=0 n_no_rise=3 n_single_word=3 n_snapped=18 n_undetectable=4
<   stats end n_below_min_shift=4 n_extended=25 n_fired=29 n_lines=110 n_low_ref=0 n_single_word=3
---
>   stats onset n_below_min_shift=14 n_fired=36 n_lines=110 n_low_ref=0 n_no_rise=3 n_single_word=3 n_snapped=19 n_undetectable=4
>   stats end n_below_min_shift=4 n_extended=26 n_fired=30 n_lines=110 n_low_ref=0 n_single_word=3
168a173
>   rec end [1w] L0 +0.390
178c183
<   stats end n_below_min_shift=4 n_extended=8 n_fired=12 n_lines=74 n_low_ref=0 n_single_word=1
---
>   stats end n_below_min_shift=4 n_extended=9 n_fired=13 n_lines=74 n_low_ref=0 n_single_word=1
223a229
>   rec end [1w] L33 +0.409
237,238c243,244
<   stats onset n_below_min_shift=11 n_fired=30 n_lines=67 n_low_ref=0 n_no_rise=2 n_single_word=4 n_snapped=17 n_undetectable=5
<   stats end n_below_min_shift=10 n_extended=23 n_fired=33 n_lines=67 n_low_ref=0 n_single_word=4
---
>   stats onset n_below_min_shift=12 n_fired=31 n_lines=67 n_low_ref=0 n_no_rise=2 n_single_word=4 n_snapped=17 n_undetectable=5
>   stats end n_below_min_shift=10 n_extended=24 n_fired=34 n_lines=67 n_low_ref=0 n_single_word=4
239a246
>   rec onset [1w] L2 +1.880
261,262c268,269
<   stats onset n_below_min_shift=3 n_fired=17 n_lines=31 n_low_ref=1 n_no_rise=0 n_single_word=1 n_snapped=14 n_undetectable=0
<   stats end n_below_min_shift=8 n_extended=7 n_fired=15 n_lines=31 n_low_ref=0 n_single_word=1
---
>   stats onset n_below_min_shift=3 n_fired=18 n_lines=31 n_low_ref=1 n_no_rise=0 n_single_word=1 n_snapped=15 n_undetectable=0
>   stats end n_below_min_shift=8 n_extended=7 n_fired=15 n_lines=31 n_low_ref=1 n_single_word=1
299a307
>   rec end [1w] L0 +2.450
309a318
>   rec end [1w] L23 +1.455
328,329c337,339
<   stats onset n_below_min_shift=7 n_fired=26 n_lines=65 n_low_ref=0 n_no_rise=3 n_single_word=4 n_snapped=16 n_undetectable=3
<   stats end n_below_min_shift=6 n_extended=28 n_fired=34 n_lines=65 n_low_ref=0 n_single_word=4
---
>   rec end [1w] L62 +1.355
>   stats onset n_below_min_shift=8 n_fired=27 n_lines=65 n_low_ref=0 n_no_rise=3 n_single_word=4 n_snapped=16 n_undetectable=3
>   stats end n_below_min_shift=6 n_extended=31 n_fired=37 n_lines=65 n_low_ref=0 n_single_word=4
418c428
<   stats onset n_below_min_shift=4 n_fired=8 n_lines=40 n_low_ref=2 n_no_rise=0 n_single_word=2 n_snapped=4 n_undetectable=0
---
>   stats onset n_below_min_shift=4 n_fired=8 n_lines=40 n_low_ref=3 n_no_rise=0 n_single_word=2 n_snapped=4 n_undetectable=0
484,485c494,495
< total onset n_below_min_shift=125 n_fired=344 n_lines=1010 n_low_ref=13 n_no_rise=28 n_single_word=21 n_snapped=191 n_undetectable=50
< total end n_below_min_shift=104 n_extended=237 n_fired=341 n_lines=1010 n_low_ref=7 n_single_word=21
---
> total onset n_below_min_shift=129 n_fired=350 n_lines=1010 n_low_ref=14 n_no_rise=28 n_single_word=21 n_snapped=193 n_undetectable=50
> total end n_below_min_shift=104 n_extended=245 n_fired=349 n_lines=1010 n_low_ref=8 n_single_word=21
```

**Coverage harness (unfiltered).**

Invocation: `uv run --no-sync python scripts/edge_snap_ass.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p4_coverage.txt`
Diff: `diff edge_p3_coverage.txt edge_p4_coverage.txt > edge_p4_coverage.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p4_coverage.diff`

```
6a7
>   rec end [1w] 3:45.25 -> 3:49.70 (+4.45s)  ... Down!
8c9,10
<   stats end n_below_min_shift=6 n_extended=0 n_fired=6 n_lines=51 n_low_ref=0 n_single_word=3
---
>   stats end n_below_min_shift=6 n_extended=1 n_fired=7 n_lines=51 n_low_ref=0 n_single_word=3
>   wrote 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM.edgesnap.ass
12a15
>   rec end [1w] 0:47.54 -> 0:47.83 (+0.28s)  ... Popular
14,15c17,18
<   stats onset n_below_min_shift=17 n_fired=18 n_lines=51 n_low_ref=1 n_no_rise=1 n_single_word=2 n_snapped=0 n_undetectable=1
<   stats end n_below_min_shift=8 n_extended=1 n_fired=9 n_lines=51 n_low_ref=0 n_single_word=2
---
>   stats onset n_below_min_shift=18 n_fired=19 n_lines=51 n_low_ref=1 n_no_rise=1 n_single_word=2 n_snapped=0 n_undetectable=1
>   stats end n_below_min_shift=8 n_extended=2 n_fired=10 n_lines=51 n_low_ref=0 n_single_word=2
17a21,32
>   rec onset [1w] 0:40.91 -> 0:41.23 (+0.32s)  Unexpectedly ...
>   rec onset [1w] 1:36.48 -> 1:37.23 (+0.75s)  Oh ...
>   rec onset [1w] 1:52.87 -> 1:53.08 (+0.21s)  Oh ...
>   rec onset [1w] 3:16.63 -> 3:16.85 (+0.22s)  Beast ...
>   rec end [1w] 1:30.47 -> 1:33.68 (+3.21s)  ... Oh
>   rec end [1w] 1:37.70 -> 1:39.53 (+1.82s)  ... Oh
>   rec end [1w] 1:46.30 -> 1:51.40 (+5.10s)  ... Oh
>   rec end [1w] 1:54.37 -> 1:56.07 (+1.70s) to_bound  ... Oh
>   rec end [1w] 1:59.57 -> 1:59.96 (+0.39s) to_bound  ... Oh
>   rec end [1w] 2:05.49 -> 2:06.02 (+0.53s) to_bound  ... Yeah
>   rec end [1w] 2:32.02 -> 2:33.18 (+1.16s)  ... Oh
>   rec end [1w] 2:43.56 -> 2:46.08 (+2.52s) to_bound  ... Oh
19,20c34,41
<   stats onset n_below_min_shift=15 n_fired=16 n_lines=56 n_low_ref=0 n_no_rise=1 n_single_word=21 n_snapped=0 n_undetectable=8
<   stats end n_below_min_shift=12 n_extended=1 n_fired=13 n_lines=56 n_low_ref=0 n_single_word=21
---
>   rec end [1w] 3:05.84 -> 3:06.06 (+0.22s) to_bound  ... Mmm-mmm
>   rec end 3:16.53 -> 3:16.75 (+0.22s) to_bound  ... Beauty and the...
>   rec end [1w] 3:18.13 -> 3:20.12 (+2.00s)  ... Beast
>   rec end [1w] 3:22.55 -> 3:24.80 (+2.25s) to_bound  ... Oh
>   rec end [1w] 3:26.40 -> 3:26.95 (+0.55s)  ... Oh
>   rec end [1w] 3:47.59 -> 3:51.25 (+3.66s)  ... Beast
>   stats onset n_below_min_shift=18 n_fired=23 n_lines=56 n_low_ref=0 n_no_rise=1 n_single_word=21 n_snapped=4 n_undetectable=10
>   stats end n_below_min_shift=12 n_extended=15 n_fired=27 n_lines=56 n_low_ref=0 n_single_word=21
24,25c45,48
<   stats onset n_below_min_shift=5 n_fired=7 n_lines=27 n_low_ref=0 n_no_rise=2 n_single_word=2 n_snapped=0 n_undetectable=2
<   stats end n_below_min_shift=10 n_extended=1 n_fired=11 n_lines=27 n_low_ref=0 n_single_word=2
---
>   rec end [1w] 2:55.63 -> 3:00.15 (+4.52s)  ... Alone
>   rec end [1w] 3:41.16 -> 3:43.58 (+2.42s)  ... Incomplete
>   stats onset n_below_min_shift=6 n_fired=8 n_lines=27 n_low_ref=0 n_no_rise=2 n_single_word=2 n_snapped=0 n_undetectable=3
>   stats end n_below_min_shift=10 n_extended=3 n_fired=13 n_lines=27 n_low_ref=0 n_single_word=2
34,35c57,61
<   stats onset n_below_min_shift=32 n_fired=34 n_lines=101 n_low_ref=0 n_no_rise=2 n_single_word=3 n_snapped=0 n_undetectable=6
<   stats end n_below_min_shift=9 n_extended=0 n_fired=9 n_lines=101 n_low_ref=0 n_single_word=3
---
>   rec onset [1w] 1:20.98 -> 1:21.48 (+0.50s)  Bonjour ...
>   rec end [1w] 1:21.90 -> 1:22.05 (+0.15s)  ... Bonjour
>   stats onset n_below_min_shift=33 n_fired=36 n_lines=101 n_low_ref=0 n_no_rise=2 n_single_word=3 n_snapped=1 n_undetectable=6
>   stats end n_below_min_shift=9 n_extended=1 n_fired=10 n_lines=101 n_low_ref=0 n_single_word=3
>   wrote Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw.edgesnap.ass
44a71
>   rec end [1w] 0:02.56 -> 0:02.95 (+0.39s)  ... Na-na-na-na
46c73,74
<   stats end n_below_min_shift=3 n_extended=0 n_fired=3 n_lines=47 n_low_ref=0 n_single_word=1
---
>   stats end n_below_min_shift=3 n_extended=1 n_fired=4 n_lines=47 n_low_ref=0 n_single_word=1
>   wrote Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I.edgesnap.ass
53a82
>   rec end [1w] 1:58.11 -> 1:58.53 (+0.41s)  ... Ooh-ooh-ooh-ooh
55,56c84,85
<   stats onset n_below_min_shift=27 n_fired=29 n_lines=63 n_low_ref=0 n_no_rise=2 n_single_word=4 n_snapped=0 n_undetectable=11
<   stats end n_below_min_shift=15 n_extended=1 n_fired=16 n_lines=63 n_low_ref=0 n_single_word=4
---
>   stats onset n_below_min_shift=28 n_fired=30 n_lines=63 n_low_ref=0 n_no_rise=2 n_single_word=4 n_snapped=0 n_undetectable=11
>   stats end n_below_min_shift=15 n_extended=2 n_fired=17 n_lines=63 n_low_ref=0 n_single_word=4
59,60c88,91
<   stats onset n_below_min_shift=28 n_fired=30 n_lines=54 n_low_ref=2 n_no_rise=2 n_single_word=5 n_snapped=0 n_undetectable=6
<   stats end n_below_min_shift=15 n_extended=0 n_fired=15 n_lines=54 n_low_ref=0 n_single_word=5
---
>   rec onset [1w] 1:22.43 -> 1:23.03 (+0.60s)  Street ...
>   stats onset n_below_min_shift=29 n_fired=33 n_lines=54 n_low_ref=3 n_no_rise=3 n_single_word=5 n_snapped=1 n_undetectable=7
>   stats end n_below_min_shift=15 n_extended=0 n_fired=15 n_lines=54 n_low_ref=1 n_single_word=5
>   wrote Jodi Benson - Part of Your World (From 'The Little Mermaid')---SXKlJuO07eM.edgesnap.ass
62,63c93,96
<   stats onset n_below_min_shift=17 n_fired=17 n_lines=29 n_low_ref=1 n_no_rise=0 n_single_word=1 n_snapped=0 n_undetectable=1
<   stats end n_below_min_shift=10 n_extended=0 n_fired=10 n_lines=29 n_low_ref=0 n_single_word=1
---
>   rec onset [1w] 0:02.48 -> 0:04.36 (+1.88s)  Nope! ...
>   stats onset n_below_min_shift=17 n_fired=18 n_lines=29 n_low_ref=1 n_no_rise=0 n_single_word=1 n_snapped=1 n_undetectable=1
>   stats end n_below_min_shift=10 n_extended=0 n_fired=10 n_lines=29 n_low_ref=1 n_single_word=1
>   wrote Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY.edgesnap.ass
65,66c98,101
<   stats onset n_below_min_shift=35 n_fired=37 n_lines=84 n_low_ref=1 n_no_rise=2 n_single_word=2 n_snapped=0 n_undetectable=5
<   stats end n_below_min_shift=13 n_extended=0 n_fired=13 n_lines=84 n_low_ref=1 n_single_word=2
---
>   rec onset [1w] 4:00.67 -> 4:01.35 (+0.68s)  Drums ...
>   stats onset n_below_min_shift=35 n_fired=38 n_lines=84 n_low_ref=1 n_no_rise=2 n_single_word=2 n_snapped=1 n_undetectable=5
>   stats end n_below_min_shift=15 n_extended=0 n_fired=15 n_lines=84 n_low_ref=1 n_single_word=2
>   wrote Justin Timberlake - Like I Love You (Official Video)---FQ3slUz7Jo8.edgesnap.ass
77,78c112,113
<   stats onset n_below_min_shift=39 n_fired=40 n_lines=103 n_low_ref=2 n_no_rise=1 n_single_word=2 n_snapped=0 n_undetectable=1
<   stats end n_below_min_shift=23 n_extended=0 n_fired=23 n_lines=103 n_low_ref=1 n_single_word=2
---
>   stats onset n_below_min_shift=40 n_fired=41 n_lines=103 n_low_ref=3 n_no_rise=1 n_single_word=2 n_snapped=0 n_undetectable=1
>   stats end n_below_min_shift=23 n_extended=0 n_fired=23 n_lines=103 n_low_ref=2 n_single_word=2
84a120,121
>   rec end [1w] 1:53.15 -> 1:53.30 (+0.15s)  ... Indescribable
>   rec end [1w] 1:55.70 -> 1:56.18 (+0.47s)  ... Feeling
86,87c123,124
<   stats onset n_below_min_shift=16 n_fired=17 n_lines=54 n_low_ref=0 n_no_rise=1 n_single_word=4 n_snapped=0 n_undetectable=4
<   stats end n_below_min_shift=9 n_extended=1 n_fired=10 n_lines=54 n_low_ref=0 n_single_word=4
---
>   stats onset n_below_min_shift=16 n_fired=17 n_lines=54 n_low_ref=1 n_no_rise=1 n_single_word=4 n_snapped=0 n_undetectable=4
>   stats end n_below_min_shift=9 n_extended=3 n_fired=12 n_lines=54 n_low_ref=2 n_single_word=4
93,94c130,135
<   stats onset n_below_min_shift=14 n_fired=14 n_lines=49 n_low_ref=0 n_no_rise=0 n_single_word=3 n_snapped=0 n_undetectable=4
<   stats end n_below_min_shift=11 n_extended=0 n_fired=11 n_lines=49 n_low_ref=0 n_single_word=3
---
>   rec end [1w] 1:57.30 -> 1:57.52 (+0.22s) to_bound  ... Speechless!
>   rec end [1w] 2:45.48 -> 2:47.10 (+1.62s) to_bound  ... Speechless!
>   rec end [1w] 3:04.22 -> 3:10.18 (+5.96s)  ... Speechless!
>   stats onset n_below_min_shift=15 n_fired=15 n_lines=49 n_low_ref=0 n_no_rise=0 n_single_word=3 n_snapped=0 n_undetectable=5
>   stats end n_below_min_shift=11 n_extended=3 n_fired=14 n_lines=49 n_low_ref=0 n_single_word=3
>   wrote Naomi Scott - Speechless (from Aladdin) (Official Video)---mw5VIEIvuMI.edgesnap.ass
100a142,143
>   rec end [1w] 0:01.50 -> 0:03.95 (+2.45s)  ... Ooh
>   rec end [1w] 2:00.42 -> 2:01.88 (+1.46s)  ... Paradise
102,103c145,147
<   stats onset n_below_min_shift=22 n_fired=25 n_lines=53 n_low_ref=0 n_no_rise=3 n_single_word=4 n_snapped=0 n_undetectable=7
<   stats end n_below_min_shift=10 n_extended=1 n_fired=11 n_lines=53 n_low_ref=0 n_single_word=4
---
>   rec end [1w] 4:24.06 -> 4:25.43 (+1.36s)  ... Paradise
>   stats onset n_below_min_shift=23 n_fired=26 n_lines=53 n_low_ref=0 n_no_rise=3 n_single_word=4 n_snapped=0 n_undetectable=7
>   stats end n_below_min_shift=10 n_extended=4 n_fired=14 n_lines=53 n_low_ref=0 n_single_word=4
123c167
<   stats onset n_below_min_shift=8 n_fired=8 n_lines=33 n_low_ref=2 n_no_rise=0 n_single_word=2 n_snapped=0 n_undetectable=1
---
>   stats onset n_below_min_shift=8 n_fired=8 n_lines=33 n_low_ref=3 n_no_rise=0 n_single_word=2 n_snapped=0 n_undetectable=1
133c177
<   stats onset n_below_min_shift=8 n_fired=10 n_lines=60 n_low_ref=0 n_no_rise=2 n_single_word=1 n_snapped=0 n_undetectable=5
---
>   stats onset n_below_min_shift=8 n_fired=10 n_lines=60 n_low_ref=1 n_no_rise=2 n_single_word=1 n_snapped=0 n_undetectable=5
136,137c180,181
< total onset n_below_min_shift=623 n_fired=688 n_lines=1823 n_low_ref=19 n_no_rise=62 n_single_word=61 n_snapped=3 n_undetectable=152
< total end n_below_min_shift=349 n_extended=15 n_fired=364 n_lines=1823 n_low_ref=10 n_single_word=61
---
> total onset n_below_min_shift=634 n_fired=708 n_lines=1823 n_low_ref=24 n_no_rise=63 n_single_word=61 n_snapped=11 n_undetectable=157
> total end n_below_min_shift=351 n_extended=44 n_fired=395 n_lines=1823 n_low_ref=15 n_single_word=61
```

**`--multi-word-only` gate (Phase 3 code vs Phase 4 code).**

Phase 3 code re-run method: `git stash push` (shelved the uncommitted
Phase 4 edit together with the pre-existing `pyproject.toml`/`uv.lock`
edits), confirmed `pikaraoke/lib/onset_snap.py` had no
`SINGLE_WORD_REF_PCT` (Phase 3 content), ran both harnesses with
`--multi-word-only`, then `git stash pop` and confirmed via `git status`
and `grep` that the Phase 4 edit was restored.

Replay, Phase 3 code. Invocation:
`uv run --no-sync python scripts/edge_snap_replay.py --folder D:/shared/pikaraoke-songs --multi-word-only`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p3_mwo_replay.txt`

Coverage, Phase 3 code. Invocation:
`uv run --no-sync python scripts/edge_snap_ass.py --folder D:/shared/pikaraoke-songs --multi-word-only`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p3_mwo_coverage.txt`

Replay, Phase 4 code. Invocation:
`uv run --no-sync python scripts/edge_snap_replay.py --folder D:/shared/pikaraoke-songs --multi-word-only`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p4_mwo_replay.txt`

Coverage, Phase 4 code. Invocation:
`uv run --no-sync python scripts/edge_snap_ass.py --folder D:/shared/pikaraoke-songs --multi-word-only`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p4_mwo_coverage.txt`

Gate, record views (`  stats `, `  wrote `, `total ` lines stripped):
`diff edge_p3_mwo_replay.rv.txt edge_p4_mwo_replay.rv.txt` -> empty (0
bytes). `diff edge_p3_mwo_coverage.rv.txt edge_p4_mwo_coverage.rv.txt` ->
empty (0 bytes). Record-view files:
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p3_mwo_replay.rv.txt`,
`...edge_p4_mwo_replay.rv.txt`, `...edge_p3_mwo_coverage.rv.txt`,
`...edge_p4_mwo_coverage.rv.txt` (same folder). Diff artifacts (both 0
bytes): `...\edge_snap\edge_p4_mwo_replay.diff`,
`...\edge_snap\edge_p4_mwo_coverage.diff`.

`n_single_word=0` in every `--multi-word-only` stats line on both
harnesses (the filter's own population, by construction).

**Phase 1 hand-check** (the de-reverb-adopted song,
`Wicked - For Good ... Movieclips---wzSeub9W4QQ`): both harnesses print
`n_single_word=0` for this song's block, unchanged between P3 and P4
(coverage `n_lines=29`; replay `n_lines=36`). The replay harness's
per-song record block for this song is byte-for-byte identical between
`edge_p3_replay.txt` and `edge_p4_replay.txt` (11 records, same shifts,
same stats). Both blocks, P3 and P4 (identical):

Coverage:

```
Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ
  stats onset n_below_min_shift=8 n_fired=9 n_lines=29 n_low_ref=3 n_no_rise=1 n_single_word=0 n_snapped=0 n_undetectable=0
  stats end n_below_min_shift=8 n_extended=0 n_fired=8 n_lines=29 n_low_ref=2 n_single_word=0
```

Replay:

```
Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ
  rec onset L7 +1.250
  rec onset L22 +0.770
  rec onset L25 +0.618
  rec onset L28 +0.710
  rec onset L29 +0.245
  rec end L5 +0.645
  rec end L6 +0.250
  rec end L20 +0.680
  rec end L22 +0.160 to_bound
  rec end L28 +1.145
  rec end L29 +0.630
  stats onset n_below_min_shift=4 n_fired=9 n_lines=36 n_low_ref=4 n_no_rise=0 n_single_word=0 n_snapped=5 n_undetectable=0
  stats end n_below_min_shift=6 n_extended=6 n_fired=12 n_lines=36 n_low_ref=3 n_single_word=0
```

Suite: known failures only. Commit: (this entry rides with it).

### Phase 4 read-off (Opus, 2026-09-17)

**Checked against the record.** Code read at `aab7358` against the Phase 4
spec text: 4a (`SINGLE_WORD_REF_PCT = 80.0`, the `len(words) == 1`
percentile branch with the same index construction and bounds filter),
4b (`if not words:`, the counter moved to "seen", `bound` at the narrow-
window skip / `_detect_rise` call / clamp / end-carry fallback), 4c
(`if not words:` plus the counter, nothing else), 4d (five new tests, the
two `test_short_lines_skipped` renamed and their one-word cases removed).
All present, nothing else changed. The `len(words) >= 2` branch of
`_sung_level_ref` is byte-identical, so `lrclib_fill.py`'s caller is
untouched.

Tests re-run by the judge at `aab7358`:
`uv run --no-sync python -m pytest tests/unit/test_onset_snap.py
tests/unit/test_lrclib_fill.py -q` -> `67 passed` (39 + 28), matching the
executor's split. The commit touches three files only; `pyproject.toml`
and `uv.lock` left unstaged.

**Gate, stronger than the plan required.** The plan's gate is the
`--multi-word-only` *record views* byte-identical at P3 and P4. They are
(both `.diff`s 0 bytes). The `  stats `/`total ` lines, which the record
view strips, were also compared and are identical in both harnesses — so
no multi-word counter moved either, not just no multi-word record. That
matches the code reading: for `len(words) >= 2`, `bound` is
`words[1]["start"]`, which is what `w2s` was.

**Both unfiltered diffs are strictly additive.** Zero `<` record lines in
either harness: no P3 record was removed, and none changed value (a changed
value would appear as a `<`/`>` pair). Every delta is a new record.

| | replay | coverage |
| --- | --- | --- |
| added `rec onset [1w]` | 2 | 8 |
| added `rec end [1w]` | 8 | 28 |
| added multi-word records | 0 | 1 (end) |
| removed or changed records | 0 | 0 |

Totals reconcile exactly against those counts: coverage onset `n_fired`
+20 = +8 snapped +1 no_rise +11 below_min_shift; coverage end `n_fired`
+31 = +29 extended +2 below_min_shift; replay onset +6 = +2 +0 +4; replay
end +8 = +8 +0. Both documented invariants hold at `total` level in all
four files (judge re-check; the executor's audit covers per-song).
`n_lines` is unchanged (1823 / 1010) and `n_single_word` is unchanged at
61 / 21 across the counter's redefinition from "skipped" to "seen" — every
one-word line was skipped before and is seen now, so the number must not
move, and it does not.

**The one collateral multi-word record is explained and correct.**
Coverage, Ariana Grande / John Legend "Beauty and the Beast":
`rec end 3:16.53 -> 3:16.75 (+0.22s) to_bound  ... Beauty and the...`
appears because the following one-word `Beast` line's onset moved from
196.63 to 196.85, widening the previous line's bound. The previous line's
voice traces to 196.75 and `Beast` now starts at 196.85: the two records
are consistent with each other, not competing for the same audio.

**Independent quality audit of the new records.** The snap's own gates use
a line-local reference, so re-reading the records with that reference would
be circular. Scored instead against song-wide envelope percentiles:
`level = (median(region) - p10_song) / (p95_song - p10_song)`, where 1.0 is
the song's loud anchor and 0.0 its floor. An end extension should land on
LOUD audio; an onset snap's vacated span should be QUIET.

Script: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\4d761251-d0b5-493b-a519-1f8202696d9f\scratchpad\p4judge\audit.py`

```
== coverage (songs=34) ==
  end-extension region loudness   : n=28 min=0.35 p25=0.91 median=0.96 max=1.04
  onset vacated region loudness   : n=8 min=-0.06 p25=0.03 median=0.36 max=0.81
  onset kept region loudness      : n=8 min=0.34 p25=0.83 median=0.93 max=1.01
  low_ref claimed-span loudness   : n=6 min=0.00 p25=0.00 median=0.07 max=0.30
== replay (songs=18) ==
  end-extension region loudness   : n=8 min=0.35 p25=0.84 median=0.86 max=1.04
  onset vacated region loudness   : n=2 min=0.04 p25=0.06 median=0.07 max=0.11
  onset kept region loudness      : n=2 min=0.34 p25=0.42 median=0.50 max=0.67
  low_ref claimed-span loudness   : n=1 min=0.19 p25=0.19 median=0.19 max=0.19
```

Every end extension lands on audio well above the floor. Per-snap context
for the onset snaps whose vacated span is not quiet (script
`...\p4judge\context.py`):

```
  [1w] 'Unexpectedly' claimed 40.91-42.41 -> start 41.23 (+0.32s)
        vacated level=0.60  kept level=0.92
        prev line ends 40.91 (gap +0.00s), prev text: 'Then somebody bends'
  [1w] 'Oh' claimed 96.48-97.70 -> start 97.23 (+0.75s)
        vacated level=0.72  kept level=0.95
        prev line ends 90.47 (gap +6.01s), prev text: 'Oh'
  [1w] 'Beast' claimed 196.63-198.13 -> start 196.85 (+0.22s)
        vacated level=0.81  kept level=0.94
        prev line ends 196.53 (gap +0.10s), prev text: 'Beauty and the...'
```

Two of the three are back-to-back lines where the loud vacated audio is the
*previous* line's own voice, i.e. the claimed start was smeared back into
it — the target defect, snapped correctly. The third (`Oh` at 96.48; this
song is a duet) has no previous line within 6 s, so its vacated span is
audio at 0.72 of the loud anchor with a >= `STEP_DB` rise on top of it at
97.23. The envelope cannot say whether that is a harmony under the lead's
entry or the lead itself. One line, corpus-wide.

Final one-word span durations, both harnesses (script
`...\p4judge\spans.py`): coverage 32 one-word lines moved, 5 now shorter;
replay 9 moved, 2 now shorter.

```
   1.98s ->  0.10s  'Nope!'  Josh Gad - In Summer
   1.22s ->  0.54s  'Drums'  Justin Timberlake - Like I Love You
   0.92s ->  0.58s  'Bonjour'  Beauty and the Beast (1991) - Belle
   1.40s ->  0.80s  'Street'  Jodi Benson - Part of Your World
   0.49s ->  0.91s  'Ooh-ooh-ooh-ooh'  Jessie J - Domino
```

**Findings.**

1. Phase 4 is the specified change, and it is the headline coverage
   landing: 46 new records across the two harnesses, all on lines the
   `len(words) < 2` gates used to drop.
2. Nothing regressed. Both diffs are strictly additive, the multi-word
   gate holds on stats as well as records, and the only multi-word record
   that moved is the documented bound-widening collateral, verified
   consistent with the one-word snap that caused it.
3. **New interaction, recorded for Phase 7 and not a gate.** A one-word
   line's onset clamp is `bound - MIN_WORD_DUR_S` with `bound` its *own*
   claimed end, so a large forward snap can squeeze the line to the 0.1 s
   floor. The end path then re-derives its reference over that squeezed
   span, which can fall under `MIN_REF_DB` and block the extension that
   would have restored the duration. It happened exactly once: `Nope!`
   (In Summer), 1.98 s -> 0.10 s, in both harnesses, with the end path
   newly reporting `n_low_ref` on that song. Net still an improvement — the
   wipe was 1.98 s starting 1.88 s early, and `generate_ass` pads the event
   by `line_lead_in_cs=80` / `line_lead_out_cs=20`, so the line is still on
   screen ~1.1 s — but a minimum one-word display duration is a real
   Phase 7 question.
4. The duet `Oh` above is the documented multi-singer blind spot reaching
   the one-word population for the first time. Expected, sized at one line,
   no action.
5. Docstring drift introduced by widening `_detect_rise`'s `t1`: its
   docstring still reads "hold through to ``t1`` (word 2's start)" and its
   local is still `b_word2`, but `t1` is word 1's claimed end on a one-word
   line; and `snap_line_ends`' inline comment still asserts "the shared
   words-2..n reference applies unchanged", which a one-word line no longer
   obeys. Cosmetic, fold into Phase 5.

**Flagged item 1 — the fifth `w2s` site. Confirmed, with one correction to
the record.** The escalation was right, and was right to be logged rather
than folded in silently. `bound` replaces `w2s` as a *variable*: after 4b
the assignment `w2s = words[1]["start"]` is gone, so leaving the
`n_undetectable` window's `hi = min(max(int(w2s / HOP_S), lo + 1),
len(env))` as literal `w2s` is a `NameError` on **every** line that reaches
`n_fired`, not only on a single-word line as the entry states. The
substitution is the plan's own stated rule applied to an occurrence the
frozen text could not have enumerated (Phase 2 added it after `385c881`),
`bound` is the only in-scope end of that search window, and the site is
diagnostic-only — `n_undetectable` drives no behaviour, and the Phase 2
read-off already ruled it overcounts and moved 7b's sizing to `n_no_rise`.
No design judgement was exercised beyond the stated rule.

**Flagged item 2 — the Phase 1 hand-check. Satisfied; do not move it to
another song.** The check as written is vacuous here: the de-reverb-adopted
song carries `n_single_word=0` in both harnesses and its replay block is
byte-identical between P3 and P4, so there is no one-word population on it
to inspect. Its *substance* — a floor-level reference can come from a
sparse, speech-like delivery and not only from a misplaced line — is
answerable on the population Phase 4 actually created, and is discharged:
every one-word line rejected at `MIN_REF_DB` has a claimed span at or below
0.30 of its own song's loud anchor (coverage n=6, median 0.07, max 0.30;
replay n=1 at 0.19), i.e. genuinely quiet, not sung-but-sparse. Moving the
hand-check to a different de-reverbed song is not possible (one corpus song
adopted a de-reverbed stem) and is not needed. Note also that a `n_low_ref`
rejection on a one-word line is a no-op against Phase 3, where the line was
skipped at the gate: it can cost coverage, never correctness.

**Ruling.**

1. Phase 4 is accepted as committed (`aab7358`). No re-run, no change.
2. Flagged item 1 confirmed; the "crash on a single-word line" wording is
   corrected above to "on every line". Flagged item 2 satisfied and closed.
3. **Phase 5 is unblocked.** Diff against the executor's `edge_p4_*` files
   if they still resolve; otherwise re-run both harnesses on `aab7358`
   first and match the Phase 4 `total` lines above exactly, else STOP ->
   Opus. Phase 5's recorded expectation is unsized (Phase 3 read-off,
   finding 5): a contrary diff is for the read, not a STOP.
4. Fold finding 5's docstring drift into the Phase 5 commit, which already
   rewrites `_sung_level_ref`'s docstring.
5. Findings 3 and 4 carry to Phase 7 as sizing questions, not gates.
6. `/code-review` on the Phase 0-4 commits runs at the Phase 5 checkpoint,
   as scheduled. Phase 4 is the commit in this set that needs it: a new
   reference path plus a bound generalization across two functions is past
   what self-review covers.

### Phase 4 eyeball session (Ken, 2026-09-17)

The two lines the read-off could not settle from the envelope were checked
by ear. Setup note: the `.edgesnap.ass` files then on disk were from the
`--multi-word-only` run and had one-word lines *deleted* (18 of 22 files;
e.g. Speechless carried 46 Dialogue lines against the shipped file's 49).
The coverage harness was re-run unfiltered at `aab7358` and reproduces
`edge_p4_coverage.txt` byte-for-byte. Re-run output:
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\4d761251-d0b5-493b-a519-1f8202696d9f\scratchpad\p4judge\rerun_coverage.txt`

**1. Ariana Grande / John Legend "Beauty and the Beast", the lone `Oh`
(96.48 -> 97.23, +0.75 s).** Ken: *"beauty and the beast is fine"*.

The snap is correct. **Finding 4 closes.** The vacated span at 0.72 of the
song's loud anchor with no previous line within 6 s was a harmony sitting
under the lead's entry, not the lead. The multi-singer blind spot did not
fire on the one-word population's only candidate for it.

**2. Josh Gad "In Summer", `Nope!` (2.48-4.46 claimed, snapped to
4.36-4.46).** Ken: *"summer is late but right duration with edge snap, and
early, long, but ends in right spot in production"*.

Both versions end in the same place — the end path rejected this line at
`MIN_REF_DB` over its squeezed span, so the claimed end never moved — and
that shared end is the one Ken reads as correct. The whole difference is
the start: production's is early and the wipe runs long; Phase 4's has the
right duration but arrives late.

**Finding 3 is confirmed and sharpened.** The defect is not only the
duration collapse the read-off recorded. The onset search *overshot*: it
placed the start later than the word. Note the asymmetry this exposes —
on this line whisper's claimed **end** was trustworthy and its claimed
**start** was not, which is the opposite of what the one-word bound
assumes when it searches all the way to the claimed end and then clamps
against it.

**What this changes.** Neither verdict disturbs the Phase 4 ruling or the
Phase 5 go. Finding 4 is closed as verified-correct. Finding 3 keeps its
Phase 7 home but is now a sized, heard defect rather than a suspected one,
and the shape of a fix is visible: reject a one-word snap that would
collapse the line, rather than clamping it into a sliver. That leaves
production's early-but-correctly-ended behaviour, which by this reading is
the better of the two wrong answers.

### Phase 5

`edge_p4_*.txt` (Phase 4's scratchpad files) still resolved; their `total`
lines matched the ones pasted under the Phase 4 read-off exactly. No
re-run against those totals was needed. Phase 5 diffs below are against
those files.

**Change.**

- `_sung_level_ref` gains `end: bool = False`. For `len(words) >= 2`, the
  reference is still the median over `words[1:]`, with `words[0]` joining
  it when `end` is true and `words[0]["end"] - words[0]["start"] >
  MIN_WORD_DUR_S`. The `len(words) == 1` percentile path is unchanged and
  independent of `end`, per the plan.
- `snap_line_ends`'s call becomes `_sung_level_ref(env, words, end=True)`.
  `snap_line_onsets`'s call and `lrclib_fill.py:279` keep the default,
  unmodified.
- Docstring rewrite on `_sung_level_ref`: the "both snaps gate on this
  same reference" sentence is gone, replaced with the default/`end=True`
  split above.

**Comment tidy-up folded in (Phase 4 read-off finding 5, ruling item 4).**
`_detect_rise`'s docstring said "hold through to `t1` (word 2's start)"
and its local was `b_word2`; both predate Phase 4's generalization of `t1`
to word 1's own claimed end on a one-word line. Docstring reworded to name
both cases; `b_word2` renamed `b_bound` throughout the function (its two
inline comments' "word 2" wording generalized to "the bound" the same
way); the test file's one comment naming `b_word2`
(`test_rise_truncated_by_stem_end_rejected`) updated to match. Separately,
`snap_line_ends`'s inline comment above the `_sung_level_ref` call said
"the shared words-2..n reference applies unchanged" — no longer true now
that `end=True` can pull word 1 in — rewritten to state why `end=True` is
safe here (onsets already ran) alongside the pre-existing point it still
needed (the last word's own span is fair to reference even where it
dominates `words[1:]`). No behavior change from any edit in this
paragraph.

**Test:** `test_end_ref_includes_long_word1` added to `TestSnapLineEnds`,
at the plan's stated construction and values.

**Suite.**

Invocation: `uv run --no-sync python -m pytest tests/unit -q`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p5_suite.txt`

```
FAILED tests/unit/test_genius.py::TestSidecarIO::test_write_overwrites_existing
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job
FAILED tests/unit/test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple
FAILED tests/unit/test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close
4 failed, 1525 passed, 2 skipped in 37.23s
```

Only the known four; 1525 = 1524 + 1 new test.

Invocation: `uv run --no-sync python -m pytest tests/unit/test_onset_snap.py tests/unit/test_lrclib_fill.py -q`
-> `68 passed` (40 + 28), matching the split (39 -> 40 in `test_onset_snap.py`).

**Supplementary check (not in the plan's Verify list): per-line invariant
audit,** same script and invariants as Phase 4's.

Script: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\check_invariants.py`

```
edge_p5_coverage.txt: onset_lines_checked=35 end_lines_checked=35 violations=0
edge_p5_replay.txt: onset_lines_checked=19 end_lines_checked=19 violations=0
```

**Replay harness.**

Invocation: `uv run --no-sync python scripts/edge_snap_replay.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p5_replay.txt`
Diff: `diff edge_p4_replay.txt edge_p5_replay.txt > edge_p5_replay.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p5_replay.diff`
(171 lines).

```
9,11c9,11
<   rec end L40 +0.440
<   rec end L41 +0.351
<   rec end L42 +0.445
---
>   rec end L40 +0.390
>   rec end L41 +0.376
>   rec end L42 +0.470
40c40
<   rec end L31 +2.320
---
>   rec end L31 +2.345
43c43
<   stats end n_below_min_shift=4 n_extended=7 n_fired=11 n_lines=41 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=3 n_extended=7 n_fired=10 n_lines=41 n_low_ref=0 n_single_word=0
81a82
>   rec end L34 +0.150
83c84
<   rec end L39 +0.685
---
>   rec end L39 +0.710
91c92
<   stats end n_below_min_shift=1 n_extended=12 n_fired=13 n_lines=77 n_low_ref=1 n_single_word=0
---
>   stats end n_below_min_shift=0 n_extended=13 n_fired=13 n_lines=77 n_low_ref=1 n_single_word=0
112,113c113,114
<   rec end L1 +0.880
<   rec end L2 +0.385
---
>   rec end L1 +0.930
>   rec end L2 +0.410
125c126
<   rec end L49 +0.445
---
>   rec end L49 +0.345
154c155
<   rec end L14 +1.995
---
>   rec end L14 +1.970
161c162
<   stats end n_below_min_shift=11 n_extended=6 n_fired=17 n_lines=38 n_low_ref=1 n_single_word=0
---
>   stats end n_below_min_shift=11 n_extended=6 n_fired=17 n_lines=38 n_low_ref=0 n_single_word=0
174c175
<   rec end L7 +0.205
---
>   rec end L7 +0.230
220c221
<   rec end L3 +0.325
---
>   rec end L3 +0.350
224c225
<   rec end L19 +0.205
---
>   rec end L19 +0.230
228c229,230
<   rec end L28 +0.519
---
>   rec end L28 +0.544
>   rec end L31 +0.154
244c246
<   stats end n_below_min_shift=10 n_extended=24 n_fired=34 n_lines=67 n_low_ref=0 n_single_word=4
---
>   stats end n_below_min_shift=9 n_extended=25 n_fired=34 n_lines=67 n_low_ref=0 n_single_word=4
267c269
<   rec end L30 +3.295
---
>   rec end L30 +3.320
269c271
<   stats end n_below_min_shift=8 n_extended=7 n_fired=15 n_lines=31 n_low_ref=1 n_single_word=1
---
>   stats end n_below_min_shift=7 n_extended=7 n_fired=14 n_lines=31 n_low_ref=1 n_single_word=1
271c273
<   rec end L0 +0.615
---
>   rec end L0 +0.640
274c276
<   rec end L8 +0.816
---
>   rec end L8 +0.841
279c281
<   rec end L31 +0.950
---
>   rec end L31 +0.975
287c289
<   rec end L46 +1.170
---
>   rec end L46 +1.145
312c314
<   rec end L13 +0.530
---
>   rec end L13 +0.505
326c328
<   rec end L35 +0.265
---
>   rec end L35 +0.315
328c330
<   rec end L37 +0.295
---
>   rec end L37 +0.345
334c336
<   rec end L47 +1.020
---
>   rec end L47 +0.995
364c366
<   rec end L28 +0.305
---
>   rec end L28 +0.280
368c370
<   rec end L32 +0.255
---
>   rec end L32 +0.280
370c372
<   stats end n_below_min_shift=8 n_extended=16 n_fired=24 n_lines=37 n_low_ref=1 n_single_word=0
---
>   stats end n_below_min_shift=8 n_extended=16 n_fired=24 n_lines=37 n_low_ref=0 n_single_word=0
382c384
<   rec end L11 +1.940
---
>   rec end L11 +1.990
385c387
<   rec end L15 +5.820
---
>   rec end L15 +5.795
408c410
<   rec end L20 +0.209
---
>   rec end L20 +0.234
413c415
<   stats end n_below_min_shift=10 n_extended=9 n_fired=19 n_lines=38 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=9 n_extended=9 n_fired=18 n_lines=38 n_low_ref=0 n_single_word=0
420c422
<   rec end L5 +0.350
---
>   rec end L5 +0.375
423d424
<   rec end L14 +0.210 to_bound
426c427
<   rec end L28 +1.105
---
>   rec end L28 +1.130
429c430
<   stats end n_below_min_shift=4 n_extended=9 n_fired=13 n_lines=40 n_low_ref=0 n_single_word=2
---
>   stats end n_below_min_shift=4 n_extended=8 n_fired=12 n_lines=40 n_low_ref=0 n_single_word=2
461c462
<   rec end L40 +0.295
---
>   rec end L40 +0.320
471c472
<   rec end L62 +5.100
---
>   rec end L62 +5.600
478c479
<   stats end n_below_min_shift=15 n_extended=22 n_fired=37 n_lines=71 n_low_ref=1 n_single_word=1
---
>   stats end n_below_min_shift=14 n_extended=22 n_fired=36 n_lines=71 n_low_ref=2 n_single_word=1
490c491
<   rec end L29 +0.630
---
>   rec end L29 +0.655
492c493
<   stats end n_below_min_shift=6 n_extended=6 n_fired=12 n_lines=36 n_low_ref=3 n_single_word=0
---
>   stats end n_below_min_shift=6 n_extended=6 n_fired=12 n_lines=36 n_low_ref=4 n_single_word=0
495c496
< total end n_below_min_shift=104 n_extended=245 n_fired=349 n_lines=1010 n_low_ref=8 n_single_word=21
---
> total end n_below_min_shift=98 n_extended=246 n_fired=344 n_lines=1010 n_low_ref=8 n_single_word=21
```

**Coverage harness.**

Invocation: `uv run --no-sync python scripts/edge_snap_ass.py --folder D:/shared/pikaraoke-songs`
Artifact: `C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p5_coverage.txt`
Diff: `diff edge_p4_coverage.txt edge_p5_coverage.txt > edge_p5_coverage.diff`, at
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\d51ed6ab-8aef-45a0-b94e-f5d57771998a\scratchpad\edge_snap\edge_p5_coverage.diff`
(123 lines).

```
2a3,6
>   rec end 2:49.14 -> 2:49.54 (+0.40s) to_bound  ... Because I knew you
>   rec end 2:57.20 -> 2:57.52 (+0.32s) to_bound  ... just to clear the air
>   rec end 4:03.90 -> 4:04.05 (+0.15s)  ... Because I knew you
>   rec end 4:18.70 -> 4:22.98 (+4.28s)  ... For good
4c8
<   stats end n_below_min_shift=16 n_extended=0 n_fired=16 n_lines=60 n_low_ref=2 n_single_word=0
---
>   stats end n_below_min_shift=12 n_extended=4 n_fired=16 n_lines=60 n_low_ref=1 n_single_word=0
9c13
<   stats end n_below_min_shift=6 n_extended=1 n_fired=7 n_lines=51 n_low_ref=0 n_single_word=3
---
>   stats end n_below_min_shift=7 n_extended=1 n_fired=8 n_lines=51 n_low_ref=0 n_single_word=3
13c17
<   stats end n_below_min_shift=4 n_extended=0 n_fired=4 n_lines=40 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=3 n_extended=0 n_fired=3 n_lines=40 n_low_ref=0 n_single_word=0
35d38
<   rec end 3:16.53 -> 3:16.75 (+0.22s) to_bound  ... Beauty and the...
41c44
<   stats end n_below_min_shift=12 n_extended=15 n_fired=27 n_lines=56 n_low_ref=0 n_single_word=21
---
>   stats end n_below_min_shift=10 n_extended=14 n_fired=24 n_lines=56 n_low_ref=0 n_single_word=21
52c55
<   stats end n_below_min_shift=0 n_extended=0 n_fired=0 n_lines=39 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=1 n_extended=0 n_fired=1 n_lines=39 n_low_ref=0 n_single_word=0
64c67
<   stats end n_below_min_shift=8 n_extended=0 n_fired=8 n_lines=37 n_low_ref=1 n_single_word=0
---
>   stats end n_below_min_shift=8 n_extended=0 n_fired=8 n_lines=37 n_low_ref=0 n_single_word=0
68c71
<   stats end n_below_min_shift=15 n_extended=1 n_fired=16 n_lines=38 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=16 n_extended=1 n_fired=17 n_lines=38 n_low_ref=0 n_single_word=0
81a85
>   rec end 1:53.99 -> 1:54.15 (+0.16s)  ... Don't you know?
83c87
<   rec end 3:41.90 -> 3:45.25 (+3.35s)  ... the moonlight In the moonlight
---
>   rec end 3:41.90 -> 3:44.08 (+2.17s)  ... the moonlight In the moonlight
85c89
<   stats end n_below_min_shift=15 n_extended=2 n_fired=17 n_lines=63 n_low_ref=0 n_single_word=4
---
>   stats end n_below_min_shift=14 n_extended=3 n_fired=17 n_lines=63 n_low_ref=0 n_single_word=4
90c94
<   stats end n_below_min_shift=15 n_extended=0 n_fired=15 n_lines=54 n_low_ref=1 n_single_word=5
---
>   stats end n_below_min_shift=13 n_extended=0 n_fired=13 n_lines=54 n_low_ref=1 n_single_word=5
95c99
<   stats end n_below_min_shift=10 n_extended=0 n_fired=10 n_lines=29 n_low_ref=1 n_single_word=1
---
>   stats end n_below_min_shift=9 n_extended=0 n_fired=9 n_lines=29 n_low_ref=1 n_single_word=1
100c104
<   stats end n_below_min_shift=15 n_extended=0 n_fired=15 n_lines=84 n_low_ref=1 n_single_word=2
---
>   stats end n_below_min_shift=15 n_extended=0 n_fired=15 n_lines=84 n_low_ref=0 n_single_word=2
106d109
<   rec end 4:35.30 -> 4:35.45 (+0.15s) to_bound  ... like you're my mirror, oh-oh
109c112
<   stats end n_below_min_shift=12 n_extended=4 n_fired=16 n_lines=120 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=12 n_extended=3 n_fired=15 n_lines=120 n_low_ref=0 n_single_word=0
115a119
>   rec end 1:03.06 -> 1:03.23 (+0.17s)  ... bad for my mental, but
117c121
<   stats end n_below_min_shift=16 n_extended=0 n_fired=16 n_lines=79 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=15 n_extended=1 n_fired=16 n_lines=79 n_low_ref=0 n_single_word=0
119a124
>   rec end 1:40.12 -> 1:40.28 (+0.15s)  ... It's crystal clear
124c129
<   stats end n_below_min_shift=9 n_extended=3 n_fired=12 n_lines=54 n_low_ref=2 n_single_word=4
---
>   stats end n_below_min_shift=9 n_extended=4 n_fired=13 n_lines=54 n_low_ref=2 n_single_word=4
137c142
<   rec end 0:22.37 -> 0:23.05 (+0.68s)  ... Bye bye
---
>   rec end 2:23.39 -> 2:24.05 (+0.66s)  ... you that I've had enough
139c144
<   stats end n_below_min_shift=9 n_extended=1 n_fired=10 n_lines=75 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=11 n_extended=1 n_fired=12 n_lines=75 n_low_ref=0 n_single_word=0
144d148
<   rec end 4:01.22 -> 4:01.38 (+0.15s)  ... 'Cause I waited
147c151
<   stats end n_below_min_shift=10 n_extended=4 n_fired=14 n_lines=53 n_low_ref=0 n_single_word=4
---
>   stats end n_below_min_shift=11 n_extended=3 n_fired=14 n_lines=53 n_low_ref=0 n_single_word=4
152c156
<   stats end n_below_min_shift=18 n_extended=1 n_fired=19 n_lines=37 n_low_ref=1 n_single_word=0
---
>   stats end n_below_min_shift=18 n_extended=1 n_fired=19 n_lines=37 n_low_ref=0 n_single_word=0
159c163
<   stats end n_below_min_shift=17 n_extended=0 n_fired=17 n_lines=38 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=16 n_extended=0 n_fired=16 n_lines=38 n_low_ref=0 n_single_word=0
160a165
>   rec end 0:56.74 -> 0:57.50 (+0.76s)  ... With all its living things
163c168
<   stats end n_below_min_shift=7 n_extended=1 n_fired=8 n_lines=32 n_low_ref=0 n_single_word=0
---
>   stats end n_below_min_shift=6 n_extended=2 n_fired=8 n_lines=32 n_low_ref=0 n_single_word=0
166c171
<   rec end 3:30.79 -> 3:32.60 (+1.81s)  ... It's our problem-free philosophy
---
>   rec end 3:30.79 -> 3:32.62 (+1.83s)  ... It's our problem-free philosophy
168c173
<   stats end n_below_min_shift=6 n_extended=1 n_fired=7 n_lines=33 n_low_ref=0 n_single_word=2
---
>   stats end n_below_min_shift=7 n_extended=1 n_fired=8 n_lines=33 n_low_ref=0 n_single_word=2
172c177
<   stats end n_below_min_shift=25 n_extended=0 n_fired=25 n_lines=67 n_low_ref=1 n_single_word=1
---
>   stats end n_below_min_shift=23 n_extended=0 n_fired=23 n_lines=67 n_low_ref=3 n_single_word=1
175c180
<   stats end n_below_min_shift=8 n_extended=0 n_fired=8 n_lines=29 n_low_ref=2 n_single_word=0
---
>   stats end n_below_min_shift=8 n_extended=0 n_fired=8 n_lines=29 n_low_ref=3 n_single_word=0
181c186
< total end n_below_min_shift=351 n_extended=44 n_fired=395 n_lines=1823 n_low_ref=15 n_single_word=61
---
> total end n_below_min_shift=342 n_extended=49 n_fired=391 n_lines=1823 n_low_ref=14 n_single_word=61
```

**Against the plan's recorded expectation** ("a small number of
end-extend changes, concentrated on lines with a long first word, mainly
on the replay harness") and the Phase 4 ruling's carry-forward note
("Phase 5's recorded expectation is unsized... a contrary diff is for the
read, not a STOP"): both diffs are pasted above for the read.

Suite: known failures only. Commit: (this entry rides with it).

### Phase 5 read-off + Phases 0-5 checkpoint (Opus, 2026-09-17)

**Checked against the record.** Code read at `7a41c6e` against the Phase 5
spec text. `_sung_level_ref(env, words, end=False)` present; the `len(words)
>= 2` path adds `words[0]` to `ref_words` when `end` and
`words[0]["end"] - words[0]["start"] > MIN_WORD_DUR_S`, otherwise slices
`words[1:]` as before; the `len(words) == 1` percentile path returns before
`ref_words` is built, so it is independent of `end` as specified;
`snap_line_ends` passes `end=True`; the docstring's "both snaps gate on this
same reference" sentence is gone. The folded-in tidy-up (finding 5, ruling
item 4) is wording and rename only. Callers enumerated:
`onset_snap.py:251` (onset) and `lrclib_fill.py:279` both keep the default,
so both are untouched. Three files in the commit; `pyproject.toml` and
`uv.lock` left unstaged.

Tests re-run by the judge at `7a41c6e`:
`uv run --no-sync python -m pytest tests/unit/test_onset_snap.py
tests/unit/test_lrclib_fill.py -q` -> `68 passed` (40 + 28), matching the
executor's split.

**The onset side is provably untouched, independently confirmed.** Grepping
both harness outputs down to their onset lines and diffing P4 against P5
gives zero differences in both harnesses — records, per-song stats and
totals alike. Every changed line in both diffs carries ` end `. The onset
`total` lines are identical in both harnesses (replay
`n_snapped=193 n_fired=350`, coverage `n_snapped=11 n_fired=708`).

**Totals and invariants.** The end invariant `n_fired == n_extended +
n_below_min_shift` holds at `total` in all four files: replay P4 245+104=349,
P5 246+98=344; coverage P4 44+351=395, P5 49+342=391. `n_lines` (1010 /
1823) and `n_single_word` (21 / 61) unchanged.

| | replay | coverage |
| --- | --- | --- |
| `n_fired` | 349 -> 344 (-5) | 395 -> 391 (-4) |
| `n_extended` | 245 -> 246 (+1) | 44 -> 49 (+5) |
| `n_below_min_shift` | 104 -> 98 (-6) | 351 -> 342 (-9) |
| `n_low_ref` | 8 -> 8 | 15 -> 14 |

**Replay render regenerated at Phase 5 code, and it reproduces the record.**
`uv run --no-sync python scripts/edge_snap_replay.py --folder
D:/shared/pikaraoke-songs --write-ass`; stripping its `  wrote ` lines
reproduces `edge_p5_replay.txt` exactly (CRLF aside). 18
`.edgereplay.ass` written. Output:
`C:\Users\TsangK\AppData\Local\Temp\claude\c--temp-Github-pikaraoke\4d761251-d0b5-493b-a519-1f8202696d9f\scratchpad\p5judge\replay_writeass.txt`

**Per-line disagreement audit.** Counter deltas do not say which lines
changed or whether the new answer is better, and re-reading the records with
the snap's own line-local reference would be circular. Instead the end path
was run twice over identical input at each phase's behaviour -- P5 as
committed, and P4 reproduced by monkeypatching the module's
`_sung_level_ref` to drop `end` -- and every line where the two disagree was
scored on the DISPUTED span against song-wide envelope percentiles,
`level = (median - p10_song) / (p95_song - p10_song)`, 1.0 = the song's loud
anchor.

Scripts: `...\p5judge\audit5.py`, `...\p5judge\audit5b.py`

```
== coverage (songs=34) ==
  LOST    : n=4   disputed-span level min=0.53 median=0.84 max=0.90
  GAINED  : n=9   disputed-span level min=0.64 median=0.85 max=0.97
  SHORTER : n=1   disputed-span level 0.89
  LONGER  : n=1   (0.025s)
== replay (songs=18) ==
  LOST    : n=1   disputed-span level 0.93
  GAINED  : n=2   disputed-span level 0.91 / 0.73
  SHORTER : n=8   LONGER: n=24   (one +0.50s; all other 31 <= 0.100s)
```

The audit reconciles exactly with the harness: coverage
`n_extended` +5 = 9 gained - 4 lost; replay +1 = 2 - 1. That is the
cross-check that the P4 replica is faithful.

Every disagreement of `|delta| >= 0.15s`:

```
  GAINED  +4.28s nw=2 disputed=0.85 w1=0.85 last=0.66 | ref -53.3 -> -41.5 'For good'  #OutOfOz - 'For Good'
  GAINED  +0.76s nw=5 disputed=0.64 w1=0.65 last=0.74 | ref -34.1 -> -35.1 'all its living things'  Lion King - Can You Feel
  GAINED  +0.66s nw=9 disputed=0.95 w1=0.87 last=0.97 | ref -23.3 -> -23.9 'that I've had enough'  NSYNC - Bye Bye Bye
  GAINED  +0.40s nw=4 disputed=0.74 w1=0.74 last=0.83 | ref -34.7 -> -35.2 'Because I knew you'  #OutOfOz - 'For Good'
  GAINED  +0.32s nw=6 disputed=0.79 w1=0.87 last=0.94 | ref -27.4 -> -30.3 'to clear the air'  #OutOfOz - 'For Good'
  GAINED  +0.17s nw=6 disputed=0.88 w1=0.46 last=0.89 | ref -22.4 -> -22.7 'for my mental, but'  JT - Selfish
  GAINED  +0.16s nw=3 disputed=0.91 w1=0.84 last=1.02 | ref -19.0 -> -20.0 'Don't you know?'  Jessie J - Domino
  GAINED  +0.16s nw=3 disputed=0.97 w1=0.83 last=0.99 | ref -18.1 -> -24.1 'It's crystal clear'  A Whole New World
  GAINED  +0.15s nw=4 disputed=0.82 w1=0.84 last=0.87 | ref -32.1 -> -32.5 'Because I knew you'  #OutOfOz - 'For Good'
  LOST    -0.68s nw=2 disputed=0.90 w1=1.01 last=0.92 | ref -27.8 -> -21.5 'Bye bye'  NSYNC - Bye Bye Bye
  LOST    -0.22s nw=3 disputed=0.81 w1=0.95 last=0.82 | ref -32.9 -> -27.5 'Beauty and the...'  Ariana Grande / John Legend
  LOST    -0.15s nw=3 disputed=0.88 w1=0.99 last=0.85 | ref -16.8 -> -15.2 ''Cause I waited'  NSYNC - Paradise
  LOST    -0.15s nw=7 disputed=0.53 w1=0.89 last=0.83 | ref -24.1 -> -23.7 'you're my mirror, oh-oh'  JT - Mirrors
  SHORTER -1.17s nw=8 disputed=0.89 w1=0.93 last=0.91 | ref -23.1 -> -22.4 'moonlight In the moonlight'  Jessie J - Domino
  [replay] LOST -0.21s nw=3 disputed=0.93 w1=0.93 last=0.73 | ref -41.2 -> -31.6 'He was ashamed'  Lion King - Hakuna Matata
  [replay] LONGER +0.50s nw=3 disputed=0.77 w1=0.75 last=0.97 | ref -27.7 -> -38.8 'Until I do'  The Next Ten Minutes
```

**Reference-shift census.** The phase's stated mechanism is that word 1 is a
long HELD note, so including it RAISES the reference and stops
over-extension. Measured over every multi-word line the end path evaluates
(script `...\p5judge\refshift.py`):

```
== coverage ==                                == replay ==
  multi-word lines reaching the ref: 1762       827
  word 1 long enough to be included: 1624 (92%) 774 (94%)
  reference UP  :  451  median +0.4 dB          242  median +0.4 dB
  reference DOWN:  880  median -0.4 dB          402  median -0.4 dB
  reference flat:  293                          130
  |shift| >= 2 dB: 146   >= 5 dB: 31            90 / 26
  word 1's share of the ref frames: med 0.16    med 0.15
    p90 0.40                                      p90 0.43
  MIN_REF_DB rescued: 7   newly rejected: 4     4 / 2
```

(The rescued/rejected counts are reference-level; they do not map one-to-one
onto the `n_low_ref` counter, which the harness only reaches after the
`bound - w_end < MIN_SHIFT_S` early-out.)

**Findings.**

1. **Phase 5 is the specified change**, the onset path and `lrclib_fill.py`
   are provably untouched, the tidy-up is wording and rename only, and the
   new test encodes the plan's worked values.
2. **The plan's recorded expectation is wrong in both of its terms, and the
   Phase 3 read-off's note already covered that.** It expected the changes
   "concentrated on lines with a long first word, mainly on the replay
   harness". Replay is jitter -- 31 of its 33 value changes are <= 0.100 s,
   one line moves +0.50 s, and the net is one extension. The substance is on
   coverage: 9 gained, 4 lost, 1 shortened. Not a STOP, per that note.
3. **The gate is near-vacuous, and the commit subject oversells it.**
   `words[0]["end"] - words[0]["start"] > MIN_WORD_DUR_S` is "longer than
   100 ms", which admits word 1 on 92-94% of multi-word lines. "A
   substantial word 1" in the subject and docstring reads as a selective
   filter; in practice the change is "include word 1 in the end reference".
   The plan specified this threshold, so this is the plan's wording, not an
   executor deviation -- but a later phase reading "substantial" would be
   misled. Recorded, not a STOP.
4. **The dominant direction is the inverse of the stated mechanism**, about
   2:1 down. Because the reference is a median over FRAMES, a long word 1
   that is *quieter* than the trailing words pulls it down, and that is the
   commoner shape. The justification still holds in both directions --
   excluding word 1 exists to defend against onset smear, onsets have
   already run, and using more of the line is the better estimator -- but the
   phase is not doing mainly what its text says it does.
5. **The residual poisoning risk is real and bounded.** Onsets running first
   only repairs word 1 on lines where the onset snap actually fired; on a
   line it skipped, a still-smeared word 1 now drags the end reference down,
   which is the exact failure the default exclusion exists to prevent. What
   bounds it is that the reference is a median and word 1 is a median 0.16
   frame share, so 293 lines do not move at all and only 31 of 1624 shift
   >= 5 dB. The visible suspect is `JT - Selfish` (word 1 at 0.46 of the
   loud anchor against a 0.89 tail), and it moved the reference 0.3 dB and
   the end 0.17 s. Sized, not gating.
6. **The intended mechanism does fire, and its clearest win is a
   `MIN_REF_DB` rescue.** On `#OutOfOz - 'For Good'` the tail-only median sat
   at -53.3 dB, below the -45 floor, so the whole song's end path was
   switched off; including word 1 lifts it to -41.5 and the song gains four
   extensions, among them a 4.28 s final held note at 4:18.70 whose span
   sits at 0.85 of the song's loud anchor. That single line is the largest
   behavioural change in the phase.
7. **The four lost extensions cannot be settled from the envelope.** Their
   disputed spans are loud (0.53-0.90), so the song-wide test cannot call
   them false positives the way it could in Phase 4. All four are lines
   where word 1 is louder than the tail (w1 0.89-1.01), so the reference
   rose and the clip evidence stopped firing -- the mechanism working as
   designed, on lines where we cannot yet say the design is right. Three are
   0.15-0.22 s; one, `Bye bye` at 0:22.37 in NSYNC, is 0.68 s. These are
   eyeball items.
8. **The `Beauty and the Beast` `to_bound` record the Phase 4 read-off
   explained is gone, and its going is consistent.** Phase 4 recorded it as
   collateral: the following one-word `Beast` onset moved to 196.85, which
   widened this line's bound and let it extend 196.53 -> 196.75. At Phase 5
   the raised reference stops it firing at all. The Phase 4 explanation is
   not invalidated -- it explained why the record *appeared*, and that
   remains true of Phase 4's code. It is one of the four in finding 7 and
   rides with them to the eyeball.
9. **`MIN_WORD_DUR_S` is now doing two unrelated jobs.** It is the onset
   path's clamp floor and, as of this phase, the end path's "is word 1 worth
   referencing" threshold. The two meanings can diverge under any future
   tuning of either. A review note, not a defect.

**Ruling.**

1. **Phase 5 is accepted as committed (`7a41c6e`).** No re-run, no change.
   The change is the spec, the onset path and the LRCLIB caller are
   provably untouched, the invariants hold, and the audit reconciles with
   the harness totals.
2. Findings 3, 4, 5 and 9 are recorded against the code, not against the
   executor: each traces to the plan's own frozen text, which the executor
   applied exactly. They are inputs to `/code-review`, not rework.
3. **Finding 7 is the open question of this phase** and is deliberately left
   to the eyeball rather than ruled from the envelope. It cannot regress
   correctness silently: an extension that does not happen leaves the
   production timing, so the cost is coverage, not a wrong edge.
4. **`/code-review` is due now**, on the five Phase 1-5 code commits:
   `15f4806`, `1d90960`, `1e05ceb`, `aab7358`, `7a41c6e`. Ken launches it;
   it is never launched unprompted. Three finder angles, one per CLAUDE.md
   axis. Findings 3, 4, 5 and 9 above are the judge's standing input to it.
5. **Phase 6 is NOT PINNED, and is blocked on Ken, not on Opus.** See the
   checkpoint entry below.
6. Merging Phases 0-5 is Ken's call and is not gated on Phase 6.

### Phases 0-5 checkpoint -- eyeball list and Phase 6 ruling (Opus, 2026-09-17)

**Stale-render warning, same class as Phase 4's trap.** 21 of the 22
`.edgesnap.ass` files on disk are from the executor's Phase 5 coverage run.
The 22nd, `The Next Ten Minutes Lyrics---0j8kL24ph8U.edgesnap.ass`, is from
an earlier phase: that song has `n_snapped=0 n_extended=0` in the coverage
harness at both P4 and P5, so the harness never rewrote it. **Do not open
that file for this eyeball.** The same song IS worth hearing, via its
`.edgereplay.ass`, which is current.

**Eyeball list.** Renders: `karaoke/<stem>.edgesnap.ass` (coverage, Phase 5)
and `karaoke/<stem>.edgereplay.ass` (replay, written at `7a41c6e`). Play with
`mpv "<video>" --sub-file="karaoke/<stem>.<tag>.ass"`.

Ordered by what the read could not settle, not by size.

1. **`#OutOfOz - 'For Good'`, `.edgesnap.ass`** -- the phase's headline.
   Listen to the final line at **4:18.70**: the wipe now runs 4.28 s longer.
   Three smaller gains on the same song at 2:49.14, 2:57.20 and 4:03.90.
   Question: does the last note hold that long, or is the wipe now sitting
   on a tail? This song had its end path switched off entirely before Phase
   5, so everything end-side on it is new.
2. **`NSYNC - Bye Bye Bye`, `.edgesnap.ass`** -- one loss and one gain in one
   file. **0:22.37** (`Bye bye`): Phase 4 extended it 0.68 s, Phase 5 does
   not. Question: does "bye" still sound after 0:22.4? If yes, Phase 5 cut
   it short. **2:23.39** (`...that I've had enough`): a new 0.66 s
   extension, the opposite direction. Nothing crowds either -- the next line
   is 4.9 s away from the first.
3. **`Jessie J - Domino`, `.edgesnap.ass`** -- the one shortening.
   **3:41.90** (`In the moonlight`): Phase 4 ran to 3:45.25, Phase 5 stops at
   3:44.08. Both land on loud audio, so the envelope cannot say which is
   right. Question: where does the held note actually release? Also a small
   new extension at 1:53.99.
4. *(optional, lowest stakes)* **`The Next Ten Minutes`, `.edgereplay.ass`**
   -- the only replay change worth hearing, `Until I do`, 0.50 s longer,
   on the largest downward reference shift in the corpus (-11 dB). This is
   finding 5's mechanism at its most extreme. Nothing follows for 7.8 s.

Items 1-3 cover the biggest gain, the biggest loss and the biggest
shortening, and between them every coverage song where anything substantive
moved except `JT - Mirrors` and `NSYNC - Paradise` (0.15 s each, below what
an ear will separate).

**Phase 6 ruling: NOT PINNED. Blocked on Ken's ownership call, not on
Opus.** Of the four open items on the phase:

- **Item 3 (ownership) is Ken's and must be answered first.** Moving
  interior word boundaries rewrites `PROGRAM.md` Part 2's "Word boundaries
  inside a placed line" row, which has read "joint matcher's words" since
  GATE W closed. Opus cannot pre-empt that. If the answer is no, the phase
  dies and items 1, 2 and 4 are wasted work -- which is why the pinning pass
  should not start before it.
- **Item 2 (interior-run reference) is settled here, by Phase 5's
  measurement.** Phase 6's "compute ref once (unchanged semantics)" is no
  longer well defined, because Phase 5 created two references. The rule the
  two phases together imply: *the reference excludes spans whose claimed
  extent may be wrongly WIDE, and includes spans that may be wrongly
  NARROW.* Onset pass -- exclude every run's first word, since each is a
  repair candidate that may be smeared across its preceding gap; that is
  Phase 5's exclusion generalized from one word to one per run. End pass --
  exclude nothing, which is what `end=True` now means and why the last
  word's own clipped span is already fair to reference. Phase 5's census
  sizes the risk this rule manages: a single word is a median 0.16 frame
  share of a line-level median, but on a line split into runs the runs are
  shorter, so each run-first word is a larger share and the poisoning
  concern in item 2 gets *worse*, not better, as runs multiply. Pin the
  reference this way or the phase inherits finding 5 amplified.
- **Item 4 (gate and sizing) is settled here in mechanism.** The filter is
  Phase 4's `--multi-word-only` pattern applied to interior gaps, and the
  gate is the filtered record views byte-identical -- with the Phase 4
  strengthening kept: compare the `stats`/`total` lines too, which Phase 4
  showed costs nothing and catches counter movement a record view hides.
  The replay harness is the exact read. The 388-word count is Linux and must
  be re-measured before it is quoted.
- **Item 1 (worked test values) stays open on purpose.** It is the bulk of
  the pinning work and it is downstream of item 3.

**Sequencing recommendation, for Ken, not a ruling.** Phase 6 is the biggest
coverage multiplier, and it multiplies the detector as it currently stands --
including the harmony blind spot, which is 202 `to_bound` records in
production on this corpus and is what Phase 7a exists to size. Phases 4 and 5
have both now produced exactly one line each that the envelope could not
adjudicate and that needed Ken's ear. Running 7a before 6 would give the
expansion a detector whose worst-known failure has been measured first, and
would not waste the pinning pass if the ownership answer is no. The plan as
written runs 6 first; this is a recommendation to swap them, and it is Ken's
call either way.

### Phase 5 eyeball session (Ken, 2026-09-17)

All four eyeball items were checked by ear at the renders listed above.
Ken: *"wicked is good, 1st one in bye bye bye is good, second one went long
mistaking an oooohhh for a note extension"*; *"domino has an 'in the
moonlight' echo that starts DURING the line, the line ends correctly but the
intraline timing is off as a result"*; and, correcting a hypothesis formed
in this session, *"the echo is actually sung, not a reverb artifact"*.

**1. `#OutOfOz - 'For Good'`, final line 4:18.70 (+4.28 s).** Correct.
**Finding 6 is confirmed.** The `MIN_REF_DB` rescue is the phase's largest
behavioural change and it is right: the tail-only median sat below the
floor, the whole song's end path was switched off, and including word 1
re-enabled it. The held note does run that long.

**2. `NSYNC - Bye Bye Bye`, 0:22.37 `Bye bye` (0.68 s extension lost).**
Correct as lost. **Finding 7's largest item closes as verified-correct.**
Phase 4 was over-extending here; the raised reference stopping the clip
evidence is the stated mechanism working, on the one line where it mattered
most. The remaining three of finding 7 (0.15-0.22 s, including the
`Beauty and the Beast` `to_bound` record of finding 8) were not heard and
stay unverified; this verdict leans them correct without settling them.

**3. `NSYNC - Bye Bye Bye`, 2:23.39 (+0.66 s gained).** **Wrong.** The
extension rode a sustained backing `oooohhh`, not the lead's note
continuing. The trace kept the envelope above its release threshold on
another voice.

**4. `Jessie J - Domino`, 3:41.90 `In the moonlight` (3:45.25 -> 3:44.08).**
The **end is correct** -- Phase 5's shortening is right and Phase 4's was
long. The line's **interior** word timings are wrong, pulled by a *sung*
echo of the line that begins while the lead is still on it. That is not the
snap's doing: the snap does not move interior boundaries, and those are the
joint matcher's words.

**What this changes.**

**A. The Phase 5 ruling stands unchanged.** Three of four verdicts confirm
the change -- the biggest gain, the biggest loss and the only shortening are
all correct. Acceptance, `/code-review` status and the merge call are
untouched.

**B. Both wrong cases are one root cause: the multi-singer blind spot, now
heard on the end side.** The vocal stem carries every vocal -- lead, backing,
doubled and echo parts -- and neither the snap's envelope nor the joint
matcher can tell which is the lead. Item 3's `oooohhh` holds the release
test open; item 4's sung echo drags interior words. Phase 4's eyeball closed
the blind spot's only *onset* candidate as a false alarm; this eyeball opens
it on the *end* side with two confirmed instances. Phase 5 did not create the
blind spot, but finding 4's mostly-downward reference gives it more
opportunities to fire.

**C. Correction against this read-off's own evidence, not against the
executor.** The disagreement audit scored disputed spans against song-wide
loudness percentiles. A sung backing part is loud. So "the gained span lands
on loud audio" separates an extension onto *silence or noise floor* -- which
is what Phase 4 needed and what the technique is sound for -- from nothing
else, and is **blind to an extension onto another voice**. Of the nine gained
extensions, two were heard: one correct, one wrong. The finding-6 and
finding-7 level scores should be read as "not extended into silence", not as
"correct". No conclusion in the read-off is retracted, but the nine gains
rest on thinner evidence than the numbers implied.

**D. Phase 6: the 7a-before-6 recommendation is materially strengthened, and
is no longer only a sequencing preference.** Two reasons, both new here.
First, the blind spot now has heard instances rather than zero, and Phase 6
multiplies exactly the mechanism that produced them -- more traces and more
releases, on shorter runs. Second, **Domino is the strongest case *for*
interior ownership (item 3) and simultaneously the case against answering it
blind**: the interior is visibly wrong while the snap's own edges are right,
which is the argument for handing the interior to the snap -- but the snap
would read an envelope containing the same sung echo that fooled the
aligner, with no lead/backing discrimination of its own. Interior ownership
does not obviously fix the case that motivates it, and could reproduce the
error with the plan's blessing. Sizing that discrimination gap is therefore
a substantive input to item 3, not just a scheduling nicety. **The ownership
call remains Ken's; Phase 6 remains NOT PINNED.**

**E. Ruled out -- do not chase.** De-reverb is not a remedy for the Domino
line: the echo is a sung production element and is in the vocal stem by
design. Recorded because this session formed the opposite hypothesis and
checked the corpus before Ken corrected it. The check itself stands as fact
and is worth keeping: of the 34 bundles only `Wicked - For Good` carries a
`joint_stats.dereverb` block at all (`yield_wpm` 18.2 -> retry 30.3,
succeeded), because de-reverb triggers on low aligner word yield rather than
on detected reverb. Neither fact bears on this line.

### Phase 6 scope ruling (Ken, 2026-09-17)

Ken, on the interior-ownership question the Phase 5 eyeball raised: *"it's
very unlikely that loudness will be a good timing indicator inside a line as
there are usually no long pauses in it; no need to explore that."*

**What it settles.** The general form of interior refinement -- moving word
boundaries *within* continuous singing, which is what would be needed to fix
`Domino` -- is ruled out on mechanism, not on cost. The envelope can only
locate an edge where the level actually falls and rises; inside a sung line
it does not. `PROGRAM.md` Part 2's "Word boundaries inside a placed line"
row stays at "joint matcher's words" and is **not reopened**; it already
reads that way from GATE W (2026-09-15, interior refinement not adopted),
so no `PROGRAM.md` edit falls out of this.

**What it leaves.** Phase 6 as written never proposed the general form. It
splits a line at gaps `>= RUN_GAP_S` (0.5 s) and snaps only the edges of the
resulting runs -- which is precisely the "long pause" case where the ruling
says the envelope *does* have something to see. The ruling therefore sizes
Phase 6 rather than killing it, and sharpens the question to a single
number: **how many lines on this corpus actually carry an interior gap of at
least 0.5 s?** The plan's 388-word figure is from the 2026-07 Linux corpus
and has never been re-measured here (open item 4). That count now decides
the phase:

- If it is small, Phase 6 is not worth rewriting a row Ken closed two days
  earlier, and the plan effectively ends at the merge.
- If it is large, the phase proceeds in its narrow form, the reference rule
  from the Phases 0-5 checkpoint applies, and the row rewrite goes to Ken
  with the count in hand.

Measuring it is read-only, cheap, and does not execute the phase. **RUN
2026-09-17 at Ken's instruction -- see "### Phase 6 interior-gap count"
below. It came back large (148 replay / 406 shipped, 15-19% of lines), so
the first branch above does not fire and the phase is not closed on size.**

**Unchanged by this ruling.** 7a is a *pitch/voicing* study, not a loudness
one -- it is the alternative to the envelope, not an instance of it -- so
the ruling does not touch it. It also does not touch `Domino`'s finding:
the interior defect there is real and now simply has no owner in this plan.

### Phase 6 interior-gap count (Opus, 2026-09-17)

The measurement the scope ruling asked for, run at `ca4b46c` on
`edge_snap_refine` at Ken's instruction. Read-only: the two harness
populations are enumerated and their interior word gaps counted. No
detector runs, no envelope is read, nothing is written and no production
path is touched. Scratchpad: `p5judge/gapcount.py`, `p5judge/gapcount2.py`.

**Method.** A *split site* is an index `k` with `words[k]["start"] -
words[k-1]["end"] >= 0.5`, i.e. exactly `_split_runs`'s condition as Phase 6
specifies it. Each site is one extra run, and contributes at most two
candidate words: the previous run's last word (an end candidate) and the
next run's first word (an onset candidate).

- *Replay* population: joint bundles only, post-veto pre-snap line objects
  from `_replay_song(..., multi_word_only=False)`. This is the exact read
  per open item 4 -- no ASS round trip.
- *Coverage* population: the 34 shipped `.ass` via `parse_ass_lines`.
  Approximate (already-snapped timings, ASS centisecond resolution), but it
  is the closest analogue to the plan's 388, which counted a whole shipped
  corpus.

| | replay (joint) | coverage (shipped `.ass`) |
|---|---:|---:|
| songs | 18 | 34 |
| lines | 848 | 1823 |
| multi-word lines | 827 | 1762 |
| words | 5534 | 11223 |
| interior gaps of any size | 824 | 2306 |
| **split sites (gap >= 0.5 s)** | **148** | **406** |
| lines carrying at least one | 129 (15.2%) | 340 (18.7%) |
| ... as % of multi-word lines | 15.6% | 19.3% |
| songs carrying at least one | 18 / 18 | 34 / 34 |
| candidate words (2 per site) | 296 | 812 |
| runs per split line (2/3/4/5) | 114/12/2/1 | 288/40/10/2 |

Gap width, all interior gaps (both populations, p50 = 0.26 s, p75 = 0.42 s):

| threshold | replay | coverage |
|---|---:|---:|
| >= 0.30 s | 381 | 1094 |
| >= 0.40 s | 228 | 649 |
| >= 0.50 s | 148 | 406 |
| >= 0.75 s | 77 | 190 |
| >= 1.00 s | 48 | 104 |
| >= 1.50 s | 26 | 48 |

Split sites by band:

| band | replay | coverage |
|---|---:|---:|
| 0.50-0.75 s | 71 (48.0%) | 216 (53.2%) |
| 0.75-1.00 s | 29 (19.6%) | 86 (21.2%) |
| 1.00-2.00 s | 30 (20.3%) | 84 (20.7%) |
| 2.00-3.00 s | 5 (3.4%) | 7 (1.7%) |
| >= 3.00 s | 13 (8.8%) | 13 (3.2%) |

Widest sites (replay; coverage's list is the same songs and sites to within
ASS rounding):

| gap | t | word | line dur | before \| after | song |
|---:|---:|---|---:|---|---|
| 18.12 s | 183.52 | 5/7 | 24.10 s | `the colors of` \| `the wind` | Colors of the Wind |
| 9.46 s | 85.52 | 6/7 | 16.14 s | `when it kicks` \| `in` | Bloodstream |
| 7.26 s | 136.78 | 3/4 | 11.00 s | `My friend, stay` \| `gold` | Stay Gold |
| 7.10 s | 205.50 | 1/5 | 11.72 s | `Lately,` \| `everything's making se` | Best Part Of Me |
| 6.56 s | 95.52 | 9/10 | 14.00 s | `colors of the` \| `wind?` | Colors of the Wind |
| 6.44 s | 111.80 | 12/13 | 11.10 s | `here by your` \| `side` | This Is What It Sounds Like |
| 4.84 s | 8.10 | 4/6 | 11.81 s | `matata, what a` \| `wonderful phrase` | Hakuna Matata |
| 4.60 s | 24.36 | 2/3 | 10.00 s | `You don't` \| `know` | Colors of the Wind |

**What it says.**

1. **The count is not small, and the plan's Linux figure holds up here.**
   406 split sites over the 34-song shipped corpus against the plan's 388
   over the Linux corpus -- the same order, measured independently. One line
   in six or seven carries a genuine interior pause, and *every* song in
   both populations carries at least one. The "there are usually no long
   pauses" premise is right about the median line (p50 gap 0.26 s) and wrong
   about the corpus: the exception is common enough that Phase 6 cannot be
   dismissed on size. This contradicts the expectation stated in the scope
   ruling's relay.
2. **These are sites, not defects.** Nothing here says the snap would move
   any of them. The phase's own stated expectation is the opposite -- that
   interior candidates die on `MIN_SHIFT_S` at a higher rate than line
   edges, because whisper's interior timestamps are better than its line
   edges. The 148/406 are an upper bound on what Phase 6 could touch, and
   the number that would actually decide the phase is how many of them move
   -- which cannot be read off the structure and needs the detector run
   against run edges.
3. **Half the sites sit in the narrowest band.** 48-53% are 0.50-0.75 s.
   That is the band where the envelope has least to work with: a release,
   a reverb tail and a re-attack inside three quarters of a second, judged
   by the same reference the detector lessons warn is poisonable.
4. **The widest sites are not all musical.** The 18.12 s gap splits a 24 s
   "line" of `Colors of the Wind`, and several others are 1-word-then-pause
   shapes. Some of these are the matcher spreading a line across a repeat or
   an instrumental, not a singer holding a rest -- so a slice of the
   population is a matcher artifact that Phase 6 would silently re-time
   rather than flag.
5. **The blind spot scales with this count.** The Phase 5 eyeball confirmed
   twice, on the end side, that the snap cannot tell lead from backing.
   Every split site is an additional place for that to fire, positioned
   *inside* a line -- which is where Ken heard the `Domino` defect and where
   nothing in the pipeline is watching.

Open item 4's first half is answered by this entry. The gate mechanism
(the `--multi-word-only`-style input filter, and the replay harness as the
exact read) is unchanged and still stands as written.
