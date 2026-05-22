Model: Claude Opus 4.7

# Re-commit plan: `removediarize` → clean reviewed branch

## Goal

Reconstruct the cumulative diff between `master` and `removediarize`
(129 messy commits, ~220 files, +45k/−20k) as a sequence of ~50 small,
logically-isolated commits on a fresh branch, performing a strict code
review along the way.

> **Coverage:** this plan reconstructs `removediarize` **up to and including
> tip `6137ed6`** (`feat(tiling): keep ad-lib parens inline instead of
> splitting them off`, 2026-05-18) on base `master` `e7bc348`. If
> `removediarize` has advanced past `6137ed6` when you execute, the plan no
> longer covers the full diff — re-run the baseline sweep and fold any new
> commits into the relevant feature commits before starting.

This is **not** a history replay. Diarization code that was added and
later removed must never appear — we build toward the *end state* of
`removediarize`, organized cleanly. Commit messages on the source branch
are unreliable and are ignored; grouping is driven entirely by diff
content.

## Decisions (confirmed)

- **Feature-aligned commits, no fix-of-earlier-commit.** Every commit is a
  single feature unit — an addition, a modification, or a removal — and ships
  its code already in final, correct form. Because we reconstruct the *end
  state*, no commit in this series ever fixes an earlier commit in the series.
  The 129-branch's historical "Fix…" commits (volume bug, pause-toggle glitch,
  pipeline-tracker remove-race, glob library-wipe, stem-worker OOM, subtitle
  race, …) are **absorbed** into the feature commit that owns the code, never
  replayed as standalone fixes. Where a commit description below mentions a
  past bug, it means "this feature's final code already behaves correctly,"
  not "a later commit fixes it."
- **The commit unit is the feature, not the file.** A file touched by several
  features is split across those feature commits (the original multi-concern
  request). A feature spanning several files is *one* commit touching them all
  — so a historical fix that spanned files (e.g. loudnorm: song_manager +
  playback_controller) folds into that single feature commit. **Caveat —
  atomic hunks:** where a feature's touchpoint sits inside a shared atomic
  hunk (the `karaoke.py` constructor, `preference_manager.DEFAULTS`), that
  structural change lands *once* in the wiring/teardown commit and the
  feature's other-file hunks attach around it; this is unavoidable, not a
  deferred fix. See the Fix-absorption audit for the per-fix landing spot.
- **Testability:** each commit is logically self-contained and its own
  associated tests pass; the **full pytest suite must be green at the tip**.
  Commits are ordered so nothing is left half-wired longer than necessary.
- **Review:** fix issues as they are found, folded **into** the owning feature
  commit (never as a follow-up fix commit). The final tree may therefore
  differ from `removediarize` where review warranted a change; record each
  such deviation as a `Review-fix:` trailer in that feature commit's body. A
  `Review-fix` corrects the *original branch's* code in place — it is not a
  fix of an earlier commit in this series.
- **Cruft:** dropped from the new branch entirely — `QWEN.md`, `mockup/`,
  and all WIP/scratch docs under `plans/` (including this file's siblings).
  Final tree is leaner than `removediarize`.
- **Fidelity scope:** the branch should represent *current* functionality,
  so reconstruction also (a) purges transition-era orphaned assets the
  branch left behind, (b) corrects user-facing docs that describe removed
  features, and (c) adds focused tests for untested new core logic. These
  go beyond a literal reproduction and are called out as `Review-fix:` /
  new-test items on the relevant commits.
- **Deliverable:** this plan only. No branch/commits created yet.

## Execution baseline & review gates

*(Added for strict-review execution. Captured 2026-05-22 against
`origin/removediarize`. `removediarize` is **remote-only** — before
starting, either `git branch removediarize origin/removediarize` or
substitute `origin/removediarize` in every command in this plan.)*

### Baseline metrics (the verification spine)

| Metric | Value |
|---|---|
| Merge-base (`git merge-base master origin/removediarize`) | `e7bc348a61ca9db0d692bf24d294a164f9757757` |
| `master` tip | `e7bc348` — **equals the merge-base**, so `next` from master is the exact diff baseline; no drift |
| `removediarize` tip | `6137ed6` |
| Net diff | 220 files, +45011 / −19954 (94 A · 94 M · 32 D) |
| **Baseline test count** | **947** (`pytest --collect-only`, 0 collection errors) |
| **Baseline skip/xfail** | **0** (no `@pytest.mark.skip`/`xfail`/`pytest.skip(` anywhere in `tests/`) |

Tip green-ness alone does **not** catch a silently-dropped test file — a
smaller suite is still green. So at the tip: `pytest --collect-only -q | tail -1`
must report **≥ 947**, and the skip count must stay **0** (any new skip needs a
written justification in the owning commit body). The final
`git diff removediarize` gate is the backstop for dropped *files*; this count
is the fast smoke for dropped *tests*.

### Split-completeness sweep (Split-Candidates audit)

All 90 files with >200 changed lines were checked against the split map. No
large file is silently staged-whole-without-consideration. Breakdown:

- **OMIT (cruft):** every `plans/**`, `mockup/**`, `QWEN.md` — dropped, LOC irrelevant.
- **Regenerated (C46):** all `translations/**/messages.po` + `messages.pot` — rebuilt, not staged.
- **Pure deletions (C1/C13/C15):** `subtitles-octopus.js`, `splash.js`, `COPYRIGHT`,
  `stream_manager.py`, `file_resolver.py`, `splash.html`, `stream.py`, `ffmpeg.py` (net),
  and their tests.
- **New single-concern modules — WHOLE-justified** (one new module = one concern,
  nothing to bisect across): `mpv_controller`, `whisper_worker`, `stem_worker`,
  `tiling_match`, `word_alignment`, `lyric_align`, `genius`, `processing_manager`,
  `pipeline_tracker`, `process_terminal`, `orchestrator`, `config`,
  `backfill_artifacts`, `processing.html`, + their tests.
- **Modified, multi-concern, >200 — already SPLIT in the map:** `karaoke.py`,
  `playback_controller.py`, `info.html`.
- **Modified, WHOLE-justified by the per-page rule** (a template regression
  bisects to one screen): `home.html` (761), `search.html` (629), `queue.html` (383).
- **Modified, WHOLE single-refactor:** `download_manager.py` (257 — one concern).

`app.py`, `args.py`, `preference_manager.py` are <200 lines but still split —
they trip the *>3-concerns* half of the threshold and are already in the map.
**Verdict: clean — no unflagged split candidate.**

### Upstream-file gate (fork-maintenance rule)

These pre-existing (upstream-inherited) code/template files are modified by the
reconstruction. Per CLAUDE.md, each edit must be the smallest necessary change;
flag any edit here for extra review. **New files** (everything under
`pipeline/`, `mpv_controller`, `overlay_manager`, `genius*`, `tiling_match`,
`word_alignment`, `processing_manager`, `pipeline_tracker`, `process_terminal`,
`alignment_capture`, etc.) are exempt — they are the feature surface.

`app.py`, `karaoke.py`, `lib/{args,download_manager,ffmpeg,get_platform,
karaoke_database,library_scanner,metadata_parser,playback_controller,
preference_manager,queue_manager,song_manager,youtube_dl}.py`,
`routes/{admin,controller,files,info,preferences,queue,search,socket_events}.py`,
`templates/{base,files,home,info,queue,search}.html`, `static/custom.css`,
`static/spa-navigation.js`, `static/fontello/*`, `.gitignore`, `pyproject.toml`.

### Standing gates (apply to every commit during review)

- No debug prints. **Exception:** the `print()`s in `args.py` /
  `process_terminal_reader.py` are legitimate CLI output — allowed.
- No commented-out code; delete instead.
- No bare `except:` — specific exceptions, log don't swallow, context managers for resources.
- No new `@pytest.mark.skip`/`xfail` (baseline 0); a new skip needs a written reason.
- No upstream-file edit beyond the smallest necessary (see Upstream-file gate).
- Working state at the boundary: `python -c "import pikaraoke.app"` +
  `pytest --collect-only` succeed. **Tip must be fully green**; the C17→C32 boot
  window is the only sanctioned non-booting stretch.
- Pre-commit clean per the policy below.

### Risk register (scrutinize hardest, in order)

1. **C5 / C9 — glob library-wipe absorption.** Data-loss risk: confirm the
   cancel/delete glob is literal-safe and cannot match unintended library paths.
2. **C18 / C32 — karaoke.py shared atomic hunks, two `e` passes.** Highest
   chance of a leaked/missed hunk; the C32 `Karaoke(...)` call site must match
   the signature in the same commit or boot breaks.
3. **C-PROC — vertical processing UI.** Integration seam (routes + push wiring +
   template) with no unit coverage on the push path; verify `_on_change` →
   `pipeline_updated` actually fires and remove is race-safe.
4. **C21 / C22 — out-of-process workers.** Subprocess IPC, OOM-exit/restart, GPU
   cache clear, cancel hook; hard to fully unit-test — lean on the C-PROC smoke.
5. **C14 — playback on MPV + loudnorm fold.** Multi-file; loudnorm read failure
   must degrade gracefully (no playback crash).
6. **C16 — gevent→threading + splash teardown.** Server-model change; verify
   clean Ctrl-C shutdown and that real-time push still works.
7. **C-CLK — clock feature gathered from 8 commits' exclusions.** Risk that an
   earlier commit failed to `n`-skip/`e`-extract a clock hunk (or over-excluded);
   after C-CLK, `git diff removediarize -- <each listed file>` must be empty.

### Rollback tags & pre-commit policy

- **Tag before starting:** `git tag next-backup` (worktree is disposable, but the
  tag makes resets explicit).
- **Tag each boundary:** after a commit's Test passes, `git tag next-step-<N>`.
  A bad commit then resets cleanly: `git reset --hard next-step-<N-1>` without
  recounting. On failure: capture the test output + `git diff next-step-<N-1> HEAD`,
  diagnose (missing hunk = staging error; leaked hunk = wrong anchor, fix the
  plan first; test depends on unstaged code = move the test later), **update this
  plan**, then re-stage.
- **Pre-commit policy = every commit.** Since each commit's content equals the
  tip, formatter churn is minimal. Before each commit run
  `pre-commit run --config code_quality/.pre-commit-config.yaml --files <changed>`;
  if Black/isort reformats, re-stage and commit.

## Mechanics

Work in a throwaway worktree so `master` and `removediarize` stay untouched:

```bash
git worktree add ../pk-next -b next master
cd ../pk-next
```

Branch name is **`next`** — a short-lived integration branch that, once
reviewed and verified, is renamed to `master` (it becomes the new mainline,
so the name only needs to signal "the future master," not describe content).

Build each commit by pulling end-state content from `removediarize`:

- Whole file: `git checkout removediarize -- <path>`
- **Partial file (multi-concern split):** `git restore --source=removediarize -p -- <path>`
  and stage only the hunks belonging to the current concern. This is the
  key tool for splitting `karaoke.py`, `app.py`, `args.py`, and
  `preference_manager.py`, each of which is touched by several concerns.
- Deletions: `git rm <path>`

**No commit fixes an earlier commit.** Two ways this discipline is enforced
during execution:
- *Historical fixes are absorbed, not replayed.* You pull end-state content
  from `removediarize`, which already contains every historical bug-fix. So
  the feature commit that introduces (say) `pipeline_tracker.py` ships the
  already-race-free version — there is no "introduce, then fix" pair. If you
  ever find yourself wanting to write "fix the X added in C<n>", stop: the
  fix belongs *inside* C<n>'s content, because C<n> should have pulled the
  final code.
- *Review-fixes fold into the owning commit.* When the strict review turns up
  an issue, stage the correction into the commit that owns that code (via
  `git commit --fixup=<sha>` then `git rebase --autosquash`, or amend before
  moving on) — never as a trailing fix commit. Each commit reads as final
  intent.

After each commit, run that commit's **Test** command. After the final
commit, run the full suite + pre-commit. Then verify completeness:

```bash
# Only intentionally-dropped cruft and deliberate review-fixes should show.
git diff removediarize -- . ':!QWEN.md' ':!mockup/**' ':!plans/**'
```

Anything unexpected in that diff is a hunk that was missed during the
partial-file splits.

## Implementer's guide (read this first if you're new to interactive staging)

### Vocabulary used in this plan
- **hunk** — a contiguous block of changed lines `git` offers you as one
  yes/no unit during `-p` (patch) staging.
- **atomic hunk** — a hunk that unavoidably mixes lines belonging to several
  commits (e.g. a constructor signature). You can't take "half a hunk" with
  yes/no; you must hand-edit it (`e`).
- **`n`-skip** — when `git` shows a hunk you don't want in *this* commit, press
  `n`; it stays in the working tree for a later commit.
- **`e`-extract** — split a mixed hunk by hand (see worked example below).
- **fold / absorb** — the historical fix already lives in the end-state file,
  so pulling that file's final content *is* the fix; there's no separate step.
- **fold-stub** — a plan entry (C31, C33) that does nothing on its own; its
  work was moved into another commit (C-PROC).

### The per-commit loop — do this for every C-n
Use the project's conda env for every `python`/`pytest`/`pre-commit` call —
either `conda activate pik` first, or prefix with
`/home/ken/miniconda3/envs/pik/bin/`. Bare `pytest` will hit missing deps.
```bash
# 1. Bring the end-state content for this commit's files into the worktree.
git restore --source=removediarize --staged --worktree -- <whole-file>   # whole file: stages it directly
#    …or, for a file shared across commits, pull only this commit's hunks:
git restore --source=removediarize -p -- <shared-file>                   # y/n/s/e per hunk (updates worktree only)
git add -- <shared-file>                                                 # then stage what you kept

# 2. Sanity-check it's not half-wired before committing:
python -m py_compile $(git diff --cached --name-only -- '*.py')          # syntax
python -c "import pikaraoke.app"                                         # import smoke
git diff --cached --stat                                                 # eyeball: only the files/lines you intend

# 3. Run THIS commit's *Auto-test* line.

# 4. Commit with the title + body from the *Commit:* field (subject, blank line, body):
git commit -m "feat(mpv): add MpvController for libmpv playback" \
           -m "libmpv-backed player — window, OSD, volume, pitch, pause."

# 5. Tick the file(s) off /tmp/recommit-manifest.txt.
```
Run `pre-commit run --config code_quality/.pre-commit-config.yaml --files <changed>`
before step 4 if you want each commit lint-clean; if Black/isort reformats,
re-stage and commit (content equals the tip, so changes should be tiny).

### Interactive staging keys (`git restore -p` / `git add -p`)
`y` stage this hunk · `n` skip it (leave for later) · `s` split into smaller
hunks (try this before `e`) · `e` edit the hunk by hand · `q` quit · `?` help.

### Worked example — `e`-extracting one line (the `hide_clock` default, C17 vs C-CLK)
When building **C17** you want the whole `DEFAULTS` change *except* the new
`hide_clock` line (that belongs to C-CLK). `s` won't separate them (adjacent
added lines), so press `e`. Git opens the hunk in your editor:
```
         "normalize_audio": False,
+        "hide_now_playing_overlay": False,
+        "hide_clock": False,
+        "subtitle_delay": 0,
```
**Rule:** to *not* stage an added (`+`) line, delete that whole line from the
buffer. (To *not* stage a removed `-` line, change its leading `-` to a space.)
So delete the `+        "hide_clock": False,` line, save, close. C17 now omits
it; the line stays in the working tree and C-CLK picks it up later. Verify with
`git diff --cached -- pikaraoke/lib/preference_manager.py` (should not mention
`hide_clock`) and `git diff -- …` (should still show it, unstaged).

### "Is this file done?" check
After the last commit that touches a file, `git diff removediarize -- <file>`
should be **empty**. If it isn't, you missed a hunk — stage it into the right
commit (use `--amend` if it's the commit you just made).

### Expected weirdness — don't panic
- **`ImportError` mid-reconstruction** → you committed a file before a module
  it imports exists. That import belongs in a later commit; `e`-extract it out.
- **App won't fully boot between C17 and C32** → expected. The `Karaoke(...)`
  signature and its call site change in different commits; only the **tip**
  must boot, not every intermediate commit.
- **A test errors on import of a not-yet-created module** → that test belongs
  to a later commit. Tests ride with their code — don't add a test before the
  code it exercises lands.
- **Whisper/stem tests are slow** → while iterating, deselect them
  (`pytest -k "not whisper and not stem"`); run the full suite only at the tip.

### Safety net (the worktree is disposable)
- Undo the last commit but keep the changes staged: `git reset --soft HEAD~1`.
- Throw away uncommitted edits to a file: `git checkout -- <file>`.
- Start the whole branch over: `git worktree remove ../pk-next` then re-add it.
- Nothing here touches `master` or `removediarize`, so you cannot lose the
  source by experimenting.

### First-run costs (for the end-to-end smoke)
The first stem/whisper run **downloads model files (~GB)** and needs network,
disk, and a GPU for reasonable speed. Budget time for it; it's a one-time cost
per machine, not per song.

## Phase 0 — Pre-rebase prep (do before branching)

The point of this phase is to clean and validate the *source* tree first,
so reconstruction inherits a clean target instead of re-committing code
that review would delete. Verified findings (2026-05-21) are noted inline.

1. **Green baseline on the source tip.** Reconstruction targets the end
   state, so confirm it is actually green before trusting it:
   ```bash
   git checkout removediarize
   /home/ken/miniconda3/envs/pik/bin/python -m pytest
   pre-commit run --config code_quality/.pre-commit-config.yaml --all-files
   ```
2. **Close the env gap.** `curl_cffi` is the one new dependency not yet
   installed in `pik`; without it C4 (yt-dlp impersonation) and its tests
   can't run. Install it before starting. All other heavy deps (`mpv`,
   `torch`, `faster_whisper`, `audio_separator`, `lyricsgenius`) already
   import.
   ```bash
   /home/ken/miniconda3/envs/pik/bin/pip install curl_cffi
   ```
3. **Dead-code sweep on the tip, folded into the relevant commits.** The
   layered history (HLS → browser → CLI-mpv → libmpv, plus repeated pipeline
   refactors) is the main source of risk: the net diff already collapses to
   the end state, but refactor *sediment* (orphaned modules/functions) can
   survive. Catch it before reconstruction, not after:
   ```bash
   /home/ken/miniconda3/envs/pik/bin/pip install vulture
   vulture pikaraoke/ --min-confidence 80
   pre-commit run --all-files   # pycln (unused imports) + pylint already configured
   ```
   Delete whatever is flagged on the tip first; reconstruction then inherits
   the clean version. (Verified clean already: no `mpv/` prototype dir, no
   CLI-mpv subprocess remnants, no dangling refs to removed
   modules/assets, diarization fully gone except a dropped mockup. The
   `print()`s in `args.py`/`process_terminal_reader.py` are legitimate CLI
   output, not debug cruft — leave them.)
4. **Snapshot a file manifest for the final gate.** The completeness check
   above catches missed *hunks*, not missed *whole files*. Capture the list
   up front and tick files off as you commit:
   ```bash
   git diff --name-status master...removediarize > /tmp/recommit-manifest.txt
   ```
5. **Read the full diff once, end to end**, before slicing — with 220 files
   it's the only way to catch cross-file couplings the per-file plan can't
   see (e.g. a template depending on a route field):
   ```bash
   git diff master...removediarize > /tmp/full.diff
   ```

Why this works: the net-diff approach beats history-replay precisely
*because* of the layered history — you commit the one surviving playback
generation and the final pipeline cleanly, instead of re-deriving four
playback generations and every pipeline refactor.

## Multi-concern file split map

These files carry hunks for several concerns and are deliberately split
across commits via `git restore -p`:

| File | Concerns / target commits |
|------|---------------------------|
| `karaoke.py` | **(most-split)** MPV wiring (C18) + processing/pipeline/Genius wiring (C32) — these two **share four atomic hunks** (see below); live delay/volume control methods (C35). Helper-only temp work stays in C2. |
| `playback_controller.py` | core MPV migration + overlay-state methods (C14); subtitle/sub-mode/vocal-volume live setters (C35). Splits cleanly — distinct methods. |
| `app.py` | gevent→threading + stream/splash/browser/bg-music removal + werkzeug filter + `socketio.run` (C16); `Karaoke(...)` call-site kwargs (C32, must match karaoke.py signature); `processing_bp` + pipeline-tracker push wiring (C-PROC); `ADMIN_PASSWORD` source (C38) |
| `preference_manager.py` | `DEFAULTS` dict — one atomic hunk mixing renames/removals + new keys; park whole in C17. Live-override skip block in `get()` (C34). |
| `routes/socket_events.py` | **correction:** this is splash-handler *removal* only (`register_splash`/`handle_playback_position`/`handle_disconnect`/`start_song` + globals) → C16. No pipeline events here. |
| `args.py` | MPV/overlay args + removal of streaming/buffer/avsync + logo → C17; `--hide-clock` arg → C-CLK |

### Two constraints that force some "concerns" to co-commit

1. **Atomic shared hunks.** A file's import block, a constructor signature,
   a class-attribute block, and a dict literal are each *one contiguous
   hunk*. When a hunk mixes concerns, plain hunk-selection (`git restore -p`
   y/n/s) can't separate them — you must use `e` to hand-edit the hunk, or
   commit it whole to one concern. The offenders: `karaoke.py` (imports,
   `__init__` signature, class attrs, docstring) and `preference_manager.py`
   (`DEFAULTS`).
2. **Module-existence + call-site ordering.** A file can't be committed
   until the modules it imports exist and its call-sites match. `karaoke.py`'s
   import hunk pulls in `ProcessingManager`/`PipelineTracker`/`GeniusClient`
   (Phase D), so any karaoke.py commit that touches imports must land *after*
   Phase D — and `app.py`'s `Karaoke(...)` call must change in lockstep with
   karaoke.py's signature.

**Consequence:** to keep C18 (mpv) and C32 (processing) as separate working
commits, hand-split karaoke.py's four shared hunks with `e`. Fallback if you
don't want to hand-edit: merge karaoke.py's C18+C32 work into one post-Phase-D
wiring commit (coarser, but no `e` surgery). The method-body changes split
cleanly either way — see the symbol map below.

## Per-file execution references

Line numbers are new-side (`+`) and approximate — they drift as you stage;
the **method/symbol** is the reliable anchor during `git restore -p`.

### `karaoke.py`

*Shared atomic hunks* (hand-split with `e`, or commit whole in C32):
- imports `~L13–37` — mpv side: `MpvController`, `QueuedSong`, drop
  `supports_hardware_h264_encoding` → C18; processing side: `GeniusClient`,
  `PipelineTracker`, `ProcessingManager` → C32; `get_temp_directory` → C2.
- `__init__` signature `~L85–116` — removals/renames (`bg_music_*`,
  `streaming_format`, `prefer_hostname`, `hide_overlay`→`hide_now_playing_overlay`,
  …) → C17; `hide_clock` param → **C-CLK** (`e`-extract); `temp_dir` → C2;
  `genius_token`, `blocked_processing_words` → C32;
  `subtitle_delay`/`audio_delay`/`vocal_volume` → C35; `admin_password` → C38.
- class attrs `~L61–78` — `pipeline_tracker` → C32; `_volume` → C35; drop
  `default_bg_music_path`/`default_bg_video_path`/`screensaver_timeout` → C17;
  `show_splash_clock`→`hide_clock` attr → **C-CLK**.
- docstring `~L120–150` — mirror the signature splits.

*Cleanly separable method/body hunks:*
- **C18 (mpv):** mpv init block `~L191` (`MpvController()`, `PlaybackController(mpv=…)`,
  `_on_song_end`, `set_callbacks`, `mpv_controller.start`, `set_system_volume`);
  `get_url` simplification `~L406`; `stop()` `self.mpv_controller.quit()` `~L577`;
  `run()` `is_running` guard + "started at" log `~L631`; `broadcast_position`
  + remove `log_output()` `~L647–674`; datefmt `~L139`.
- **C32 (processing):** `~L267` block (`download_manager(temp_dir=…)`,
  `GeniusClient`, `ProcessingManager(...).start()`, `PipelineTracker(...)`,
  overlay-state provider); `stop()` `processing_manager.stop()` `~L577`.
- **C35 (controls):** `volume` property+setter `~L466`; `volume_change` `~L514`;
  `set_subtitle_delay`/`set_vocal_volume`/`set_sub_mode` `~L531`; `restart()`
  rewrite `~L569`; `transpose_current` live-pitch rewrite `~L473`;
  `reset_now_playing` additions `~L594`; `get_now_playing` dict additions `~L617`.

### `playback_controller.py` (clean — by method)
- **C14 (core mpv):** `__init__(mpv=…, get_loudnorm_offset=…)`; `self.mpv =`;
  drop `ffmpeg_process` prop + `log_output`; `start_song` rewrite +
  `_find_subtitles`/`_find_companions`; idle/`load_placeholder`; pause
  `toggle_pause`; `get_now_playing` (`position`/`is_paused`); `build_overlay_state`
  + `refresh_overlays`; `broadcast_position`; `seek`; `restart`; `set_pitch`.
- **C35 (live setters):** `set_subtitle_delay`, `set_sub_mode`, `set_vocal_volume`.

### `app.py`
- **C16:** drop `gevent` (`monkey.patch_all`, `WSGIServer`, `spawn`),
  `async_mode="threading"`, `_NoGetFilter`, drop `Browser`/`delete_tmp_dir`/
  `background_music_bp`/`stream_bp`/`splash_bp` imports + blueprint lists,
  browser-launch block removal in `main()`, `socketio.run(...)` +
  `Thread(target=k.run)` + temp cleanup `finally`.
- **C32:** the `Karaoke(...)` instantiation kwargs in `main()` (remove
  streaming/bg_music/avsync/cdg, rename `hide_overlay`) — commit with (or
  immediately after) karaoke.py's signature so the call matches. The
  `hide_clock=` kwarg is `e`-extracted to **C-CLK**.
- **C-PROC:** add `processing_bp` import+registration; replace `_broadcast_in_context`
  download wiring with `_pipeline_changed` → `k.pipeline_tracker._on_change`.
- **C38:** `app.config["ADMIN_PASSWORD"] = k.admin_password or None`.

### `preference_manager.py`
- **C17:** `DEFAULTS` hunk `~L28` (drop `complete_transcode_before_play`,
  `buffer_size`, `screensaver_timeout`, `disable_bg_*`, `bg_music_volume`,
  `disable_score`, `cdg_pixel_scaling`, `avsync`, `*_score_phrases`,
  `show_splash_clock`; `hide_overlay`→`hide_now_playing_overlay`;
  **and** the new keys `subtitle_delay`/`audio_delay`/`vocal_volume`/`temp_dir`/
  `blocked_processing_words`/`admin_password`/`genius_token`/`audio_device` —
  they ride along since splitting a dict literal needs `e` and harmlessly
  (the `hide_clock` key is the one line `e`-extracted to **C-CLK**)
  declaring a default early is fine). `get()` signature reformat is cosmetic.
- **C34:** the live-override skip block in `get()` `~L129`
  (`if preference in ("subtitle_delay", "volume", "vocal_volume")`).

### `routes/socket_events.py` (single concern → C16)
- Remove `splash_connections`/`master_splash_id` globals, `register_splash`,
  `handle_playback_position`, `handle_disconnect`, `start_song`, `import logging`;
  keep `end_song`/`clear_notification`.

`pyproject.toml` is the one shared file deliberately **not** split: all
dependency changes land together in C0 (because `requirements.txt` mirrors
the full set and can't be partially staged). Later commits reference their
deps but don't re-touch the manifest.

## Fix-absorption audit

Every historical "Fix…"/"Tune…" commit traced to the feature commit that
absorbs its final code. **Single-commit** = the fix folds wholly into one
feature commit (the common case). **Spans** = the feature is inherently
multi-file/multi-layer; the fix distributes across that feature's commits,
never as a standalone fix commit.

| Historical commit | Lands in | Kind |
|---|---|---|
| Fix glob char-class library-wipe | C5 (download_manager) | single |
| Fix subtitle resolution race | C5 (download) + C28 (processing) | spans (producer/consumer) |
| Fix pause toggle glitch · Optimize Rubberband | C11 (mpv_controller) | single |
| feat+fix loudnorm offset (DB→playback) | **C14** (playback + song_manager/db accessors) | single (now named) |
| Invert clock → `hide_clock` | **C-CLK** (dedicated vertical commit) | single (consolidated) |
| genius: show all artists · suppress INFO logs | C23 (genius) | single |
| lyric-align: None-timing · dup-text remap · debug capture | C24–C26 (lyric-align) | single (within feature) |
| whisper align/refine IPC split | C22 (whisper) + C26 (lyric_align caller) | spans (worker/caller) |
| Clear GPU cache ×2 · OOM exit · auto-restart · hook cancel · Melband | C21/C22 (workers) | single |
| Bugs surfaced by out-of-process move | C21/C22 workers + C28 mgr + C30 terminal | spans (the move itself) |
| Remove lazy loading · proactive cache clear · Tune whisper | C28 (processing_mgr) + C19 (config) | spans (config/runtime) |
| Fix processing log · Processing terminal fixes | C28 (processing_mgr) + C30 (terminal) | spans |
| Fix pipeline phase UI lag | C27 (orchestrator) + C19 (context) | spans |
| Fix tracker remove-race + fetchStatus debounce | C29 (model) + **C-PROC** (UI) | 2 commits (consolidated from 4) |
| Eliminate processing-UI bug class | C29 (model) + **C-PROC** (routes+push+template) | 2 commits (consolidated from 4) |
| Fix volume bug | C34 (pref override) + C35 (karaoke/info) | spans → C34–C35 feature pair |
| Sub delay fixes | C34 (pref override) + C35 (controls/controller/info) | spans → C34–C35 feature pair |
| Fix exit bug | C38 (admin route) | single |
| Fix pages stacking scripts | C40 (spa-navigation.js) + C41–C44 & C-PROC (per page) | spans (shared + per-page) |
| Refine global temp folder | C2 (helper) + usage in C5/C14/C18/C28/C32 | spans (cross-cutting plumbing) |
| Filter logs · reduce clutter · simplify HTTP filter | C16 (app filter) + C28 (mgr) + C21 (workers) | spans (per-emitter) |
| `fix(scripts)` resolve lyrics in-CLI | C47 (script) + C20 (load_vocal touch) | spans |

Two cleanup notes:
- **"Test fixes" / "Test update after removal"** are *not* commits — each
  test change rides with the module commit whose behavior it exercises (tests
  and code move together, per CLAUDE.md).
- **"Fixes after removal"** (splash/score teardown follow-ups) dissolve into
  the removal commits C15/C16 and the home-page commit C41 — there is no
  post-removal cleanup commit.

Where a row says **spans**, confirm during execution that each touched commit
carries only its layer's hunks and the feature works once the *last* of its
commits lands — that is the per-commit-relevant-tests / green-at-tip contract,
not a deferred fix.

---

## Phase A — Hygiene & foundations (no behavior coupling)

**C0 — Dependency manifest** *(already committed on `removediarize` as
`5475c153`; reproduce it as the first commit here)*
- *Commit:* `build(deps): declare full runtime manifest in pyproject + requirements`
  > Final dependency set plus the synced `requirements.txt` mirror. Drops
  > `gevent`/`ffmpeg-python`; adds `python-mpv`, `curl_cffi`,
  > `audio-separator[gpu]`, `faster-whisper`, `stable-ts`, `torch`,
  > `lyricsgenius`, `srt`; declares previously-transitive
  > `marshmallow`/`Pillow`/`pyzmq`. ML deps are core, not an optional extra.
- The complete final `pyproject.toml [project.dependencies]` **and**
  `requirements.txt` in one commit. `requirements.txt` mirrors the full dep
  set, so it can't be split per-feature — it lands whole here, and every
  later code commit then has its imports already declared.
- *Review:* `requirements.txt` stays in sync with pyproject; no dep declared
  that nothing imports (`pip-check`/grep).
- *Auto-test:* `pip install -e .` resolves; `python -c "import pikaraoke.app"`.
- *Verify:*
  - [ ] `pip install -e .` completes in a clean env
  - [ ] app starts without an import/dependency error

**C1 — Repo ignores & dead binary assets**
- *Commit:* `chore: remove dead static assets, ignore model folders`
  > Delete unused bundled audio/video/images plus HLS and jQuery-UI
  > leftovers; add model-folder `.gitignore` entries. Pure deletions —
  > nothing at the tip references these.
- `.gitignore` (model-folder ignores), remove unused binaries:
  `static/sounds/*`, `static/video/*`, `static/music/*`,
  `static/images/dolphly.png`, `static/js/default.woff2`,
  `static/js/COPYRIGHT`, `static/images/placeholder.png` (add).
- *Review-fix — transition-era orphans the branch left behind* (verified
  unreferenced in templates/JS/py at the tip; these survived the branch's
  own cleanup because no commit happened to touch them):
  - `static/hls-1.6.15.min.js` — dead since HLS playback removed
  - `static/video/test_autoplay.mp4` — stray test asset
  - `static/images/ui-icons_*.png` (6 jQuery-UI sprite remnants)
  - `static/images/logo.png`, `static/images/stage.jpg` — **verify first**:
    the new `--logo` arg may resolve a default to `logo.png` via a
    constructed path that a basename grep won't catch. Remove only if truly
    unreferenced.
- *Review:* confirm no template/JS still references removed assets.
- *Auto-test:* `python -c "import pikaraoke.app"` (import smoke).
- *Verify:*
  - [ ] app boots; home page renders with no 404s in the browser console

**C2 — Central temp directory (helper only)**
- *Commit:* `feat(platform): add central get_temp_directory() helper`
  > Single source of truth for the working temp dir. Callers are wired in
  > the karaoke commits (C18/C32).
- `lib/get_platform.py` (`get_temp_directory()`) only. karaoke.py's
  consumption (`temp_dir` param, `self.temp_dir = get_temp_directory(...)`,
  `download_manager(temp_dir=…)`) rides in the karaoke wiring commits (C18/C32)
  because it's entangled in the shared signature/import hunks — see Per-file
  execution references.
- *Review:* every former `tempfile.gettempdir()`/hardcoded path now routes
  through the helper (CLAUDE.md rule).
- *Auto-test:* `pytest tests/unit/test_get_platform.py` if present, else import smoke.
- *Verify:*
  - [ ] (deferred to C18/C32) temp artifacts land under the resolved dir, not the OS default

**C3 — Docs: CLAUDE.md compaction + README fidelity**
- *Commit:* `docs: compact CLAUDE.md, correct README playback description`
  > Drop the stale `mpv/` prototype line; reword the README's browser/splash
  > "Dedicated Player" lines to describe the libmpv window.
- `CLAUDE.md` compaction. (`QWEN.md` intentionally dropped.)
- *Review-fix:* drop the stale "The mpv prototype is in the `mpv/` subfolder
  under the project root" line — that folder no longer exists in the tip.
- *Review-fix — `docs/README.md` misrepresents current playback* (verified):
  - line 8: "Dedicated Player: High-performance splash screen that can be
    opened on any web browser…" — playback is libmpv now, not browser.
  - line 83: "Launches the player in headed mode via your default browser."
  Reword both to describe the libmpv window. Leave `CHANGELOG.md`'s HLS/
  splash mentions untouched — that file is history, not current-state docs.
- *Auto-test:* none (docs).
- *Verify:*
  - [ ] README no longer claims browser playback; CLAUDE.md has no `mpv/` reference

---

## Phase B — Data layer: download / library / DB

**C4 — yt-dlp impersonation**
- *Commit:* `feat(youtube): impersonate chrome on all yt-dlp calls`
  > Add `--impersonate chrome` to every yt-dlp invocation (via `curl_cffi`,
  > declared in C0) and default search to unrestricted, reducing bot-blocks.
- `lib/youtube_dl.py` `--impersonate chrome` on all yt-dlp invocations +
  default unrestricted search hunk.
- *Review:* impersonate flag applied uniformly.
- *Auto-test:* `pytest tests/unit/test_youtube_dl.py`
- *Verify:*
  - [ ] search returns results; download a song end-to-end succeeds

**C5 — download_manager refactor**
- *Commit:* `refactor(download): serialize downloads, harden error handling`
  > Rework DownloadManager error handling (specific excepts, context
  > managers). Absorbs the glob char-class library-wipe fix and the subtitle
  > resolution-race producer side.
- `lib/download_manager.py` + `tests/unit/test_download_manager.py`.
- *Review:* error handling (specific excepts), resource context managers; the
  cancel/cleanup glob cannot match unintended paths.
- *Auto-test:* `pytest tests/unit/test_download_manager.py`
- *Verify:*
  - [ ] download a song; cancel a download mid-flight — library is untouched, partial files cleaned

**C6 — Filename / metadata parsing**
- *Commit:* `feat(metadata): parse title/artist/id from filenames`
  > Metadata parsing honoring the 11-char YouTube-ID filename rule.
- `lib/metadata_parser.py` + `tests/unit/test_metadata_parser.py`.
- *Review:* 11-char YouTube-ID filename rule honored.
- *Auto-test:* `pytest tests/unit/test_metadata_parser.py`
- *Verify:*
  - [ ] a downloaded `Title [11charID].mp4` shows correct title/artist in the library

**C7 — karaoke_database schema/changes**
- *Commit:* `feat(db): extend karaoke_database schema`
  > Schema/query changes. Excludes the loudnorm column + accessors (those
  > ship with the loudnorm feature, C14).
- `lib/karaoke_database.py` + `tests/unit/test_karaoke_database.py`.
  *Excludes* the `loudnorm_offset` column + get/set — those ship with the
  loudnorm feature (C14), since `karaoke_database.py` serves two features here.
- *Auto-test:* `pytest tests/unit/test_karaoke_database.py`
- *Verify:*
  - [ ] start with an existing DB — it migrates/loads cleanly, library intact

**C8 — library_scanner changes**
- *Commit:* `refactor(library): update library scanner`
  > Scanner changes for the new metadata/DB shape.
- `lib/library_scanner.py` + `tests/unit/test_library_scanner.py`.
- *Auto-test:* `pytest tests/unit/test_library_scanner.py`
- *Verify:*
  - [ ] point at a songs folder — all expected songs appear after scan

**C9 — song_manager: rename/delete accompaniment tracks**
- *Commit:* `feat(songs): manage accompaniment tracks on rename/delete`
  > Rename/delete now handles companion stem tracks; emits events. Cancel
  > deletes via a literal-safe glob (absorbs the library-wipe fix). Excludes
  > the loudnorm forwarders (C14).
- `lib/song_manager.py` (incl. `events=` ctor arg) + `tests/unit/test_song_manager.py`.
  *Excludes* the `get/set_loudnorm_offset` forwarders — those ship with the
  loudnorm feature (C14).
- *Review:* cancel deletes accompaniment tracks via a literal-safe glob —
  verify it cannot wipe the library (the historical character-class
  library-wipe is absorbed into this commit's final code).
- *Auto-test:* `pytest tests/unit/test_song_manager.py`
- *Verify:*
  - [ ] rename a song — its accompaniment track renames too
  - [ ] delete a song with brackets/special chars in the name — only that song goes

**C10 — queue_manager changes**
- *Commit:* `feat(queue): update queue manager`
  > Queue model changes (paused-song handling, playable lookup).
- `lib/queue_manager.py` + `tests/unit/test_karaoke_queue.py` /
  `test_queue_manager.py` portions.
- *Auto-test:* `pytest tests/unit/test_queue_manager.py tests/unit/test_karaoke_queue.py`
- *Verify:*
  - [ ] add/remove/reorder songs in the queue from a remote — order holds

---

## Phase C — MPV migration

> Ordering: introduce MPV stack first, migrate playback onto it, *then*
> delete the old streaming stack, so the old path is never removed before
> its replacement exists.

**C11 — Add MpvController**
- *Commit:* `feat(mpv): add MpvController for libmpv playback`
  > libmpv-backed player — window, OSD, volume, pitch (Rubberband), pause.
  > Ships final-form pause toggle and single/dual-stem Rubberband settings
  > (absorbs those historical fixes). Not yet wired (see C18).
- `lib/mpv_controller.py` + `tests/unit/test_mpv_controller_audio_device.py`.
  (The `python-mpv` dep is in C0.)
- *Review:* the `libmpv corrupts stdin` workaround and audio-device handling
  are documented; no bare excepts around the C bindings.
- *New test:* the module ships with only an audio-device test. Add focused
  coverage (mocking the `mpv.MPV` object) for the pause toggle, volume/property
  setters, callback registration, and the song-end hook.
- *Auto-test:* `pytest tests/unit/test_mpv_controller_audio_device.py`
- *Verify:*
  - [ ] (live behavior verified at C18 once wired)

**C12 — Overlay manager**
- *Commit:* `feat(overlay): add OverlayManager for now-playing/up-next OSD`
  > Renders now-playing and up-next OSD overlays with a TV-readable palette.
  > Excludes the clock overlay (its own feature, C-CLK).
- `lib/overlay_manager.py` (now-playing/up-next overlays incl. `QueuedSong`) +
  `tests/unit/test_overlay_manager.py`. *Excludes* the clock OSD render +
  `hide_clock` inversion — those go to C-CLK (clock is its own vertical feature).
- *Review:* TV-readability palette.
- *Auto-test:* `pytest tests/unit/test_overlay_manager.py`
- *Verify:*
  - [ ] (live behavior verified at C18 once wired)

**C13 — ffmpeg simplification**
- *Commit:* `refactor(ffmpeg): drop HLS/transcode-streaming helpers`
  > Remove streaming/transcode helpers obsoleted by MPV; keep transpose +
  > version detection.
- `lib/ffmpeg.py` (drop HLS/transcode-streaming helpers, keep
  transpose/version) + delete `tests/unit/test_ffmpeg.py` if superseded,
  else update it.
- *Review:* nothing in pipeline stages still imports removed ffmpeg helpers
  (cross-check before Phase D).
- *Auto-test:* import smoke + `pytest -k ffmpeg`
- *Verify:*
  - [ ] app boots; pitch/transpose controls still detect ffmpeg support

**C14 — playback_controller on MPV + loudnorm offset**
- *Commit:* `feat(playback): drive playback via MPV, apply loudnorm offset`
  > Migrate PlaybackController onto MpvController; play/pause/seek/skip,
  > companion-track + subtitle resolution, overlay state. Folds the loudnorm
  > feature whole: DB accessors + apply-as-filter + graceful read-failure.
- `lib/playback_controller.py` (core migration — see Per-file refs) +
  `tests/unit/test_playback_controller.py`.
- **Loudnorm feature (folded here, not smeared):** `playback_controller`'s
  `get_loudnorm_offset` param + applying the offset as an MPV filter + the
  DB-read exception handling (absorbs both `feat: wire loudnorm` and `fix:
  loudnorm DB read exception handling`); plus the loudnorm accessors in
  `lib/song_manager.py` (`get/set_loudnorm_offset` forwarders) and
  `lib/karaoke_database.py` (column + get/set). The pipeline *writes* the
  offset later via the loudnorm_analyze stage (C20), which consumes these.
- *Review:* singer playback controls work. Loudnorm read failures degrade
  gracefully (no playback crash).
- *Auto-test:* `pytest tests/unit/test_playback_controller.py`
- *Verify:*
  - [ ] (live behavior verified at C18; loudnorm audible after a song is processed, C20+)

**C15 — Remove legacy streaming stack**
- *Commit:* `refactor: remove legacy HLS/browser/splash streaming stack`
  > Delete stream/file-resolver/browser/omx modules, the splash + background
  > -music routes/templates, and their JS/CSS now that MPV owns playback.
- `git rm` `lib/stream_manager.py`, `lib/file_resolver.py`, `lib/browser.py`,
  `lib/omxclient.py`, `routes/stream.py`, `routes/splash.py`,
  `routes/background_music.py`, `templates/splash.html`,
  `static/js/splash.js`, `static/js/subtitles-octopus*`, `static/score.*`,
  `static/screensaver.*`, `static/fireworks.js`; delete
  `tests/unit/test_stream_manager.py`, `test_file_resolver.py`,
  `test_splash_routes.py`.
- *Review:* grep app/templates/routes for any lingering import or
  `url_for('stream...')`/`splash` reference.
- *Auto-test:* `python -c "import pikaraoke.app"`
- *Verify:*
  - [ ] app boots; visiting `/splash` or `/stream` 404s; no console errors on the remaining pages

**C16 — gevent → threading + blueprint/splash teardown**
- *Commit:* `refactor(server): switch gevent→threading, drop splash sockets`
  > Replace the gevent WSGI server with `socketio.run` on threading; run the
  > karaoke loop in a daemon thread; remove splash socket handlers and the
  > werkzeug access-log noise filter.
- `app.py` (C16 portion — see Per-file refs): drop gevent
  (`monkey.patch_all`/`WSGIServer`/`spawn`), `async_mode="threading"`,
  `_NoGetFilter`, drop `Browser`/`delete_tmp_dir`/`stream_bp`/`splash_bp`/
  `background_music_bp`, browser-launch removal, `socketio.run(...)` +
  `Thread(target=k.run)` + temp-cleanup `finally`.
- `routes/socket_events.py` (whole): remove splash handlers/globals
  (`register_splash`, `handle_playback_position`, `handle_disconnect`,
  `start_song`).
- *Review:* no residual gevent imports anywhere.
- *Auto-test:* import smoke + app boot in test client (`pytest -k routes` subset).
- *Verify:*
  - [ ] app starts and serves pages; real-time updates (queue change) still push to the browser
  - [ ] Ctrl-C shuts down cleanly

**C17 — args + preference renames for overlays**
- *Commit:* `feat(args): rename overlay flags, drop streaming/buffer/avsync`
  > Drop `--streaming-format`/`--buffer-size`/`--avsync`; rename
  > `--hide-overlay`→`--hide-now-playing-overlay`; add `--logo`. Prefs
  > `DEFAULTS` updated to match.
- `args.py`: remove `--streaming-format`, `--buffer-size`, `--avsync`; rename
  `--hide-overlay`→`--hide-now-playing-overlay`; add `--logo`. (`--hide-clock`
  is a separate add_argument hunk → `n`-skip it; it lands in C-CLK.)
- `preference_manager.py`: `DEFAULTS` hunk committed **whole** here *except*
  the one `hide_clock` line (`e`-extract → C-CLK); renames + removals + the
  other new keys ride along — see Per-file refs.
  `tests/unit/test_preference_manager.py` rename hunks.
- Note: karaoke.py's matching signature removals/renames are *not* here —
  they live in C18's hand-split (the signature is one atomic hunk).
- *Review:* every reader of `hide_overlay`/`streaming_format` updated (grep).
- *Auto-test:* `pytest tests/unit/test_preference_manager.py tests/unit/test_preference_routes.py`
- *Verify:*
  - [ ] `pikaraoke --help` lists `--hide-now-playing-overlay`/`--logo`, not the removed flags

**C18 — karaoke.py MPV wiring**
- *Commit:* `feat(karaoke): wire MPV playback into the coordinator`
  > Construct and start MpvController, register song-end/overlay-tick
  > callbacks, apply saved volume after start, simplify URL, quit MPV on
  > stop. This is where playback goes live. (Processing wiring is C32.)
- `karaoke.py` (mpv portion — **hand-split the shared import/signature/attr/
  docstring hunks with `e`**, see Per-file refs): mpv imports, legacy
  removals/renames, `MpvController` init + `set_callbacks` + `_on_song_end` +
  `start` + `set_system_volume`, overlay tick wiring, `get_url` simplification,
  `stop()` `mpv.quit()`, run-loop `is_running` guard, `broadcast_position`,
  drop `log_output()`. Processing imports/body are deferred to C32.
- *Review:* volume preference applied after MPV start (comment explains the
  ordering hazard).
- *Auto-test:* `pytest tests/unit/ -k "playback or karaoke"`
- *Verify:*
  - [ ] start pikaraoke, queue a song — it plays in the MPV window with audio
  - [ ] now-playing + up-next overlays show; pause/skip/restart and ±volume work
  - [ ] transpose changes pitch live without restarting the song

---

## Phase D — Processing pipeline

> Built bottom-up: config/context → stages → workers → orchestrator →
> manager/tracker/terminal → routes → wiring. Each stage commit ships with
> its targeted test.

**C19 — Pipeline scaffolding**
- *Commit:* `feat(pipeline): add config/context scaffolding + stage base`
  > Pipeline `config` (tunables), `context` (per-song state), and the stage
  > base class. No runtime path yet.
- `pipeline/__init__.py`, `pipeline/config.py`, `pipeline/context.py`,
  `pipeline/stages/__init__.py`, `pipeline/stages/base.py`.
- *New test:* these have no direct coverage. Add a small
  `test_pipeline_config.py` asserting the config defaults/validation and the
  `context` construction the stages rely on — cheap, pure-Python, and it
  pins the many tunables in `config.py`.
- *Auto-test:* `pytest -k "pipeline_config or context"`
- *Verify:*
  - [ ] (no user-facing behavior; exercised end-to-end at C-PROC)

**C20 — ffmpeg stages**
- *Commit:* `feat(pipeline): add ffmpeg extract/transcode/loudnorm/load-vocal stages`
  > Audio extraction, transcode, loudnorm analysis, and vocal-load stages
  > with quiet subprocess output and specific exception handling.
- `stages/_ffmpeg_helpers.py`, `ffmpeg_extract.py`, `ffmpeg_transcode.py`,
  `loudnorm_analyze.py`, `load_vocal.py`.
- *Review:* reduced subprocess verbosity; specific exception handling.
- *Auto-test:* targeted stage tests if present, else import smoke.
- *Verify:*
  - [ ] (exercised at C-PROC — processed audio is normalized)

**C21 — Stem separation (worker + IPC)**
- *Commit:* `feat(pipeline): add out-of-process stem-separation worker`
  > Melband-Roformer separation in an isolated subprocess with IPC, OOM-exit
  > + auto-restart, and a cancel hook (absorbs those robustness fixes).
- `pipeline/workers/__init__.py`, `workers/_ipc.py`, `workers/stem_worker.py`,
  `stages/stem_separation.py`. Melband Roformer model + Rubberband settings.
- *Review:* OOM-exit-and-restart logic; cancel hook; subprocess isolation
  rationale documented.
- *Auto-test:* `pytest tests/unit/ -k stem` (mock subprocess/IPC).
- *Verify:*
  - [ ] (at C-PROC) processing a song produces vocal + instrumental stems; cancel mid-run leaves no zombie process

**C22 — Whisper worker + alignment capture**
- *Commit:* `feat(pipeline): add out-of-process whisper alignment worker`
  > Faster-whisper transcription/alignment in a subprocess; clears GPU cache
  > after every run. Ships the out-of-process move in final, stable form.
- `workers/whisper_worker.py`, `lib/alignment_capture.py` +
  `tests/unit/test_whisper_worker.py`.
- *Review:* GPU-cache clear after every run; the worker runs out-of-process
  in its final, stable form (the follow-up out-of-process corrections are
  absorbed here, not separate commits).
- *Auto-test:* `pytest tests/unit/test_whisper_worker.py`
- *Verify:*
  - [ ] (at C-PROC) GPU memory returns to baseline between processed songs

**C23 — Genius lyrics integration**
- *Commit:* `feat(lyrics): add Genius search + lyric fetch`
  > GeniusClient search/select/fetch; shows all artists in results; narrowly
  > suppresses lyricsgenius INFO log noise.
- `lib/genius.py`, `lib/genius_lyrics.py` +
  `tests/unit/test_genius.py`, `test_genius_lyrics.py`.
- *Review:* lyricsgenius INFO-log suppression scoped narrowly; token handling.
- *Auto-test:* `pytest tests/unit/test_genius.py tests/unit/test_genius_lyrics.py`
- *Verify:*
  - [ ] with a Genius token set, search returns multiple artists; logs aren't spammed with "Done."

**C24 — Word alignment (NW)**
- *Commit:* `feat(lyrics): add Needleman–Wunsch word matcher`
  > Word-level alignment between fetched lyrics and transcript. No diarization.
- `lib/word_alignment.py` + `tests/unit/test_word_alignment.py`.
  (Needleman–Wunsch matcher; **no diarization**.)
- *Review:* confirm zero diarization references survive here or in callers.
- *Auto-test:* `pytest tests/unit/test_word_alignment.py`
- *Verify:*
  - [ ] (unit-covered; exercised at C-PROC)

**C25 — Tiling matcher**
- *Commit:* `feat(lyrics): add tiling matcher for lyric/transcript alignment`
  > Raw matched-token scoring; keeps ad-lib parens inline.
- `lib/tiling_match.py` + `tests/unit/test_tiling_match.py`.
  (Raw matched-token scoring; inline ad-lib parens.)
- *Auto-test:* `pytest tests/unit/test_tiling_match.py`
- *Verify:*
  - [ ] (unit-covered; exercised at C-PROC)

**C26 — Lyric align & fetch stages + conversion**
- *Commit:* `feat(pipeline): add lyric-fetch + lyric-align stages`
  > Fetch (Genius / YouTube captions) and align lyrics into subtitles;
  > race-free subtitle resolution; default subtitle delay.
- `stages/lyric_align.py`, `stages/lyrics_fetch.py` +
  `tests/unit/test_lyric_align.py`, `test_lyrics_fetch.py`,
  `test_lyric_conversion.py`. YouTube-captions source option; subtitle
  race-free subtitle resolution; default subtitle delay.
- *Auto-test:* `pytest tests/unit/ -k "lyric"`
- *Verify:*
  - [ ] (at C-PROC) a processed song plays with time-synced subtitles

**C27 — Orchestrator**
- *Commit:* `feat(pipeline): add stage orchestrator`
  > Runs stages in order, rejects already-karaoke videos, and exposes phase
  > to callbacks (phase tracks stage execution in lock-step).
- `pipeline/orchestrator.py`.
- *Review:* stage ordering; karaoke-video rejection; phase exposure hooks.
- *New test:* add `test_orchestrator.py` driving the orchestrator with
  stub stages to assert run order, the karaoke-video rejection path, and
  phase-callback emission. This is the integration seam of the whole
  pipeline and currently has no direct test.
- *Auto-test:* `pytest tests/unit/test_orchestrator.py`
- *Verify:*
  - [ ] (at C-PROC) a video that's already a karaoke track is rejected, not reprocessed

**C28 — ProcessingManager**
- *Commit:* `feat(processing): add ProcessingManager job queue`
  > Owns the processing queue + worker lifecycle; routes thread-named logs to
  > the PTY; clears caches proactively (no lazy load).
- `lib/processing_manager.py` + `tests/unit/test_processing_manager.py`.
- *Review:* thread-name→PTY log routing; proactive cache clear (no lazy load).
- *Auto-test:* `pytest tests/unit/test_processing_manager.py`
- *Verify:*
  - [ ] (at C-PROC) queueing two songs processes them one at a time

**C29 — Pipeline tracker**
- *Commit:* `feat(processing): add PipelineTracker state model`
  > Aggregates download/processing/queue state for the processing page;
  > atomic remove (race-free) and an `_on_change` push hook.
- `lib/pipeline_tracker.py`.
- *Review:* remove path is atomic (race-free); phases update in lock-step
  with stage execution; `_on_change` callback hook present.
- *New test:* add `test_pipeline_tracker.py` covering add/update/remove
  state transitions, the atomic-remove path, and that `_on_change` fires.
  Pure-Python state machine, no external I/O — cheap to test and the part
  most prone to races.
- *Auto-test:* `pytest tests/unit/test_pipeline_tracker.py`
- *Verify:*
  - [ ] (at C-PROC) removing a song mid-processing doesn't crash or leave a ghost row

**C30 — Process terminal (PTY)**
- *Commit:* `feat(processing): add PTY process terminal for live logs`
  > PTY-backed terminal + reader so subprocess output streams to the
  > processing page; timestamp format matches the worker subprocess (no date).
- `lib/process_terminal.py`, `lib/process_terminal_reader.py`. Timestamp
  format (no date) to match worker subprocess.
- *Auto-test:* `pytest tests/unit/ -k "terminal"` (or import smoke).
- *Verify:*
  - [ ] (at C-PROC) live subprocess output streams into the processing page terminal

**C31 — → folded into C-PROC** (Processing page, Phase F)
- `routes/processing.py` + its test move into the vertical processing-page
  commit, since the page's server-driven actions, push wiring, and template
  are one feature. Nothing between here and C-PROC imports the route (app.py
  registers it in C-PROC), so deferring it is safe. `pipeline_tracker.py`
  itself stays at C29 — karaoke's wiring (C32) imports it.

**C32 — karaoke.py + app.py processing wiring**
- *Commit:* `feat(karaoke): wire processing pipeline + tracker into coordinator`
  > Construct GeniusClient/ProcessingManager/PipelineTracker, resolve temp
  > dir, wire the overlay-state provider, stop the manager on shutdown; match
  > the `Karaoke(...)` call site to the new signature.
- `karaoke.py` (processing portion — **second `e` pass** on the same shared
  import/signature/attr hunks touched in C18): add `GeniusClient`/
  `PipelineTracker`/`ProcessingManager` imports + `pipeline_tracker` attr +
  `genius_token`/`blocked_processing_words`/`temp_dir` params; the `~L267`
  init block (`GeniusClient`, `ProcessingManager(...).start()`,
  `PipelineTracker(...)`, `download_manager(temp_dir=…)`, overlay-state
  provider); `stop()` `processing_manager.stop()`.
- `app.py` (C32 portion): the `Karaoke(...)` call-site kwargs in `main()` —
  remove streaming/bg_music/avsync/cdg, rename `hide_overlay` (the `hide_clock=`
  kwarg `e`-extracts to C-CLK). Commit with karaoke.py's signature so the call
  matches (avoids a broken-boot window).
- *Auto-test:* `pytest tests/unit/ -k "karaoke or processing"`
- *Verify:*
  - [ ] download a non-karaoke song — processing starts automatically; temp artifacts land under the resolved temp dir
  - [ ] app still boots and plays (no signature/call-site mismatch)

**C33 — → folded into C-PROC** (Processing page, Phase F)
- The `app.py` push wiring (`processing_bp` registration + `_pipeline_changed`
  → `k.pipeline_tracker._on_change`, `pipeline_updated` push replacing 1s
  polling) is part of the same vertical feature as the route and template, so
  it moves to C-PROC. (`socket_events.py` was fully handled in C16.)

---

## Phase E — Preferences, routes & misc behavior

> C34–C35 are the two halves of one feature — **live now-playing controls**
> (volume, subtitle delay, sub mode, vocal volume). The historical `Fix volume
> bug` and `Sub delay fixes` (which spanned karaoke/prefs/controller/info)
> absorb into this pair; nothing about them is a later fix.

**C34 — Live controls: preference half**
- *Commit:* `feat(prefs): don't override live song state on default save`
  > Saving `subtitle_delay`/`volume`/`vocal_volume` defaults no longer jolts
  > the current song (absorbs `Fix volume bug` + `Sub delay fixes`, pref side).
- `preference_manager.py`: the live-override skip block in `get()` only
  (`if preference in ("subtitle_delay", "volume", "vocal_volume")`) — this *is*
  the `Fix volume bug` / `Sub delay fixes` behavior (saving a default must not
  jolt the current song). The `genius_token`/`blocked_processing_words` DEFAULTS
  keys already landed whole in C17, so they're not re-touched here.
- `routes/preferences.py` + `tests/unit/test_preference_routes.py`.
- *Auto-test:* `pytest tests/unit/test_preference_manager.py tests/unit/test_preference_routes.py`
- *Verify:*
  - [ ] while a song plays, change the default volume in preferences — the playing song's volume doesn't jump

**C35 — Live controls: playback/UI half**
- *Commit:* `feat(playback): live volume, subtitle-delay, sub-mode, vocal-volume`
  > Now-playing controls applied live via MPV: volume property, subtitle
  > delay, subtitle mode, vocal volume for dual-stem; plus restart/transpose
  > rewrites. Absorbs `Fix volume bug` + `Sub delay fixes`, playback side.
- `karaoke.py` (controls portion — separate method hunks, no `e` needed):
  `volume` property+setter, `volume_change`, `set_subtitle_delay`/
  `set_vocal_volume`/`set_sub_mode`, `restart`/`transpose_current` rewrites,
  `reset_now_playing` + `get_now_playing` additions; plus the
  `subtitle_delay`/`audio_delay`/`vocal_volume` params (final `e` pass on the
  signature hunk, or fold into C32's pass).
- `playback_controller.py`: `set_subtitle_delay`/`set_sub_mode`/
  `set_vocal_volume` setters. `routes/controller.py` delay/mode endpoints.
- `routes/info.py`: the volume / subtitle-delay control hunks only
  (admin/option-reorder hunks → C38, clock toggle → C-CLK; `info.py` is a
  three-way multi-feature file).
- *Review:* single source of truth for delay/volume state (no duplicated
  offsets); the live-override pref half (C34) and these setters agree.
- *Auto-test:* `pytest tests/unit/ -k "controller or playback"`
- *Verify:*
  - [ ] during playback, the now-playing remote adjusts subtitle delay, sub mode, and (dual-stem) vocal volume live
  - [ ] each control resets to its default on the next song

**C36 — Queue routes & socketio**
- *Commit:* `refactor(queue): update queue routes, drop download queue surface`
  > Queue REST/Socket.IO endpoints aligned to the new model; the separate
  > download-queue UI surface is removed.
- `routes/queue.py` + `tests/unit/test_queue_routes.py`,
  `test_queue_socketio.py`. Remove download queue from queue surface.
- *Auto-test:* `pytest tests/unit/test_queue_routes.py tests/unit/test_queue_socketio.py`
- *Verify:*
  - [ ] add/remove/reorder from the queue page — updates push live to other open clients

**C37 — Search routes**
- *Commit:* `feat(search): update search routes`
  > Search endpoints + result shape for the reworked search page.
- `routes/search.py` + `tests/unit/test_search_routes.py`.
- *Auto-test:* `pytest tests/unit/test_search_routes.py`
- *Verify:*
  - [ ] search returns results; preview + add-to-queue work from the search page

**C38 — Info / files / admin / controller routes**
- *Commit:* `feat(routes): admin password from prefs; info/files/controller updates`
  > Source `ADMIN_PASSWORD` from the preference/`Karaoke`, reorder info-page
  > options, misc files/controller updates; absorbs `Fix exit bug` (admin).
- `routes/info.py` (admin/option-reorder hunks only — volume/subtitle-delay
  hunks went to C35; the clock-toggle hunk goes to C-CLK), `routes/files.py`,
  `routes/admin.py` (`Fix exit bug` absorbed here), `routes/controller.py`.
  Admin-password behavior change; option reordering.
- `app.py` (C38 portion): `app.config["ADMIN_PASSWORD"] = k.admin_password or
  None` (now sourced from the pref/`Karaoke`, not `args.admin_password`). The
  `admin_password` `__init__` param rides in karaoke.py's C32 signature pass;
  its DEFAULTS key landed in C17.
- *Review:* admin-password change does not weaken any existing auth gate.
- *Auto-test:* `pytest tests/unit/ -k "info or files or admin or controller"`
- *Verify:*
  - [ ] set an admin password in prefs — admin actions require it; unset — they don't
  - [ ] the "exit" admin action works without error

---

## Phase F — UI (templates / CSS / icons)

> Split per page so a template regression bisects to one screen. Each is
> verified manually (no unit coverage); ship behind the corresponding
> backend commit.

**C39 — Fontello update (clock icon)**
- *Commit:* `feat(ui): add clock icon to the fontello set`
  > Regenerated fontello config/css/fonts including the clock glyph used by
  > the clock overlay (C-CLK) and info page.
- `static/fontello/*` (config, css, font binaries, demo).
- *Auto-test:* none (assets).
- *Verify:*
  - [ ] icons render across pages; the new clock glyph displays where used

**C40 — Shared layout/CSS**
- *Commit:* `refactor(ui): shared base layout + single-bind SPA navigation`
  > Base template + custom CSS; SPA navigation binds each page's scripts once
  > (absorbs the script-stacking fix).
- `templates/base.html`, `static/custom.css`, `static/spa-navigation.js`,
  single-binding of page scripts on navigation (no stacking).
- *Auto-test:* none (templates).
- *Verify:*
  - [ ] navigate between pages repeatedly — no duplicated handlers, no console errors, no stacked scripts

**C41 — Home page overhaul**
- *Commit:* `feat(ui): overhaul home / now-playing page`
  > Now-playing layout, ±volume buttons, tighter vertical spacing.
- `templates/home.html`. Now-playing tweaks, +/− buttons, vertical spacing.
- *Auto-test:* none (template).
- *Verify:*
  - [ ] now-playing shows correct title/singer; ±volume buttons work; layout isn't cramped

**C42 — Queue page**
- *Commit:* `feat(ui): rework queue page`
  > Queue page aligned to the new queue model + live updates.
- `templates/queue.html`.
- *Auto-test:* none (template).
- *Verify:*
  - [ ] queue reflects current state; add/remove/reorder works and updates live

**C43 — Search page**
- *Commit:* `feat(ui): rework search page + preview modal`
  > Search UI tweaks; video preview modal with loading overlay + smoother
  > transitions.
- `templates/search.html`. Preview modal loading overlay; search tweaks.
- *Auto-test:* none (template).
- *Verify:*
  - [ ] search; open a preview (loading overlay → plays); add a result to the queue

**C44 — Info & files pages**
- *Commit:* `feat(ui): update info + files pages`
  > Info-page controls wired; files page updates. Excludes the clock toggle
  > (C-CLK).
- `templates/info.html` (excludes the clock-toggle UI → C-CLK),
  `templates/files.html`. Wire info-page controls.
- *Auto-test:* none (templates).
- *Verify:*
  - [ ] info-page controls act on playback/prefs; files page lists and manages songs

**C-PROC — Processing page (routes + push + template), vertical**
- *Commit:* `feat(processing): processing page with server-driven actions + push updates`
  > Whole processing-UI feature as one slice: server-driven action endpoints,
  > Socket.IO `pipeline_updated` push (replaces 1s polling), and the
  > push-driven template with `fetchStatus` debounce + safe-remove. Absorbs
  > `Eliminate processing UI bug class` and `Fix tracker … debounce`.
*(absorbs former C31 + C33 + the processing.html frontend; runs here in
Phase F, after base layout C40, since it includes the template)*
- `routes/processing.py` + `tests/unit/test_processing_routes.py` (server-driven
  action endpoints).
- `app.py`: `processing_bp` registration + `_pipeline_changed` →
  `k.pipeline_tracker._on_change` (`pipeline_updated` push, replaces 1s polling).
- `templates/processing.html`: push-driven status, pending-state display,
  `fetchStatus` debounce, safe-remove markup.
- This is the whole **"processing UI" feature** as one vertical slice. The
  historical `Eliminate processing UI bug class` and `Fix tracker … debounce`
  absorb here in final form (the `pipeline_tracker` model's `_on_change` hook
  + remove-atomicity live in C29, its data layer).
- *Auto-test:* `pytest tests/unit/test_processing_routes.py`
- *Verify:*
  - [ ] process a song — phases advance live on the page with no manual refresh
  - [ ] pending songs show a pending state; cancel/remove during processing is safe (no ghost rows, no crash)
  - [ ] open two clients — both update from the push

**C-CLK — Clock overlay + `hide_clock` preference, vertical**
- *Commit:* `feat(overlay): add clock overlay with hide_clock preference`
  > One dedicated commit for the clock feature: OSD clock render + tick, the
  > `hide_clock` preference/`--hide-clock` flag, and the info-page toggle.
  > Absorbs `Invert clock overlay preference from show_clock to hide_clock`.
*(a feature that otherwise smears across 8 commits; runs last in Phase F,
after every file it touches has its non-clock changes)*
- Gathers all clock-overlay hunks: `overlay_manager.py` (clock OSD render) +
  its test, `playback_controller.py` (clock tick), `args.py` (`--hide-clock`),
  `preference_manager.py` (`hide_clock` DEFAULTS line) + its test,
  `karaoke.py` (`hide_clock` param/attr + tick wiring), `app.py`
  (`hide_clock=` in the `Karaoke(...)` call), `routes/info.py` +
  `routes/preferences.py` (toggle endpoint), `templates/info.html` (toggle UI).
- Absorbs `Invert clock overlay preference from show_clock to hide_clock`
  whole. (`--hide-now-playing-overlay` is a *different* overlay — it stays in
  C17/C18.)
- **Exclusions to apply while building earlier commits** so their content is
  clock-free: C12, C14, C17, C18, C32, C34, C38, C44 each `n`-skip their
  clock hunks. Two need `e` (the hunk also carries non-clock lines): the
  `hide_clock` line in `preference_manager.DEFAULTS` (C17) and the `hide_clock`
  param in karaoke's signature (C18/C32). The rest are separable hunks.
- *Auto-test:* `pytest tests/unit/test_overlay_manager.py tests/unit/test_preference_manager.py`
- *Verify:*
  - [ ] toggle the clock on the info page — OSD clock shows/hides on the player
  - [ ] launching with `--hide-clock` starts with the clock hidden

---

## Phase G — i18n & tooling

**C46 — Regenerate translations (don't carry stale catalogs)**
- *Commit:* `i18n: regenerate translation catalogs for current UI`
  > Rebuild `.pot`/`.po`/`.mo` from the current source so removed-UI strings
  > (splash/score/screensaver) drop out and new strings appear. Regenerated,
  > not hand-edited.
- Regenerate rather than copy the branch's files, so the catalogs describe
  the *current* UI: `pybabel extract` → `update` → `compile`. Removed-UI
  msgids (splash/score/screensaver strings) must drop out; new strings must
  appear.
  ```bash
  pybabel extract -F babel.cfg -o pikaraoke/messages.pot pikaraoke/
  pybabel update -i pikaraoke/messages.pot -d pikaraoke/translations
  pybabel compile -d pikaraoke/translations
  ```
- `messages.pot` + all `translations/*/LC_MESSAGES/messages.{po,mo}`.
- *Review:* no orphaned splash/score msgids remain; `.mo` rebuilt from `.po`,
  never hand-edited.
- *Auto-test:* `pybabel compile` clean; app boots with each locale.
- *Verify:*
  - [ ] switch UI language — pages translate, no missing/garbled strings, no leftover splash/score text

**C47 — Backfill artifacts script**
- *Commit:* `feat(scripts): backfill stems/lyrics for existing library`
  > Standalone script to (re)generate stems/subtitles/loudnorm for songs
  > already in the library; resolves lyrics in-CLI so non-YouTube-ID songs
  > use Genius.
- `scripts/backfill_artifacts.py`, `scripts/README.md`,
  `scripts/*lyrics*` resolve lyrics in-CLI (so non-YouTube-ID songs use Genius).
- *Auto-test:* `python scripts/backfill_artifacts.py --help`.
- *Verify:*
  - [ ] run it on one existing song — stems/subtitles/loudnorm get produced; a non-YouTube-ID song resolves lyrics via Genius

---

## Final gate

```bash
/home/ken/miniconda3/envs/pik/bin/python -m pytest          # full suite green
pre-commit run --config code_quality/.pre-commit-config.yaml --all-files
git diff removediarize -- . ':!QWEN.md' ':!mockup/**' ':!plans/**'  # only review-fixes show
```

**End-to-end smoke (not just unit-green).** The wiring commits (C18/C32/C-PROC)
are exactly what unit tests don't exercise, so run the real path once:
boot the app → search → download a song → process it (stem + whisper +
lyric align) → libmpv playback with now-playing/clock overlays and
subtitles → exercise queue + singer playback controls. This is the only
check that proves the integration seams actually connect.

Open the PR from `next` with a test plan mirroring the manual-verification
items in Phases C–F. Once reviewed and the end-to-end smoke passes, `next`
is renamed to `master` (the new mainline).

## Open items to confirm before executing

1. Any commits here that you'd rather **split further or merge**.

*Resolved:*
- **Branch name** = `next`, renamed to `master` once verified.
- **Heavy deps** stay **hard deps** — the model-dependent features are core,
  not optional. So `pyproject.toml` keeps `audio-separator[gpu]`/`torch`/
  `faster-whisper`/`stable-ts` as required (C0). C21–C22 tests mock the
  subprocess/IPC boundary, so they run in CI without a GPU; only the
  end-to-end smoke needs real models + hardware.
- **Translations** regenerated, not carried (C46).
- **Dependencies + `requirements.txt`** tracked and consolidated into C0,
  reproducing `removediarize@5475c153`. An optional CI sync-check between
  `requirements.txt` and pyproject is worth adding since both files are kept.
