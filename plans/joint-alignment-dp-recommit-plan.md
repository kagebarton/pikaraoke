Model: Claude Opus 4.7

# Re-commit plan: `joint-alignment-dp` → clean reviewed branch

## Goal

Reconstruct the cumulative diff between `master` and `joint-alignment-dp`
(141 messy commits, ~227 files, +51k/−20k) as a sequence of ~51 small,
logically-isolated commits on a fresh branch, performing a strict code
review along the way.

This is **not** a history replay. Diarization code that was added and
later removed must never appear — we build toward the *end state* of
`joint-alignment-dp`, organized cleanly. Commit messages on the source branch
are unreliable and are ignored; grouping is driven entirely by diff
content.

We build toward jad's end state **minus its bugs**: finding and fixing as many
correctness/robustness bugs as possible along the way is the priority, so the
final tree deliberately diverges from `joint-alignment-dp` wherever review
warrants. Matching jad byte-for-byte is **not** a goal (see Decisions →
Review).

> **Source branch note.** This plan was first written against `removediarize`
> (then at commit `971db07`). The source branch is now **`joint-alignment-dp`**,
> which is `971db07` plus the joint-alignment-DP matcher line of work. The two
> branches **diverged at `81ac04cb`**: `removediarize` continued with a
> walk-interpolation re-time and a concentrated-failure tiling escalation
> (commits `9a9c2646`, `e7401594`) that the joint matcher *superseded and
> replaced*, so that work is intentionally **not** reconstructed here. Because
> `971db07` is an ancestor of `joint-alignment-dp`, the original C0–C47 entries
> (which describe `master..971db07`) remain accurate; the joint work layers on
> top — folded into the commits that already own each file (per the re-fold
> decision), plus one new matcher commit **C26A**. All `--source=` /
> `git diff <branch>` commands below pull from `joint-alignment-dp`; pulling
> from the now-divergent `removediarize` would reproduce abandoned work and
> miss the matcher.

## Execution log (reconstruction branch `next`, worktree `../pk-next`)

Live progress + review decisions, updated as each commit is **verified by the
user**, so the reconstruction can be resumed on another machine. The code
commits live on **`next`** (worktree `../pk-next`); this plan + log lives on
`joint-alignment-dp`. To resume elsewhere: `git fetch`, then open this plan on
`joint-alignment-dp`, `git worktree add ../pk-next next`, and continue at the
first commit not marked ✅. **Requires `next` and `joint-alignment-dp` to be
pushed** — see the Resume checklist.

Legend: ✅ verified by user · 🔨 built + auto-tested, awaiting verification · ◐ partial (built; some verification still pending) · ⤳ relocated to another commit · ⬜ not started

**Lean-ledger:** verified commits are collapsed to a one-line row here and their phase-spec replaced by a pointer; the authoritative per-commit narrative is the `next` commit message (`git show <sha>`), carry-forward items in Standing deviations. In-flight commits (C9, C11–C15) keep their full row/spec until verified.

**Phase status:** A ✅ verified 2026-06-01 (C0–C3) · B 🔨 **built** (C4/C7 ✅; C5/C5A/C6/C8/C10 ✅ live-verified 2026-06-02; C9 ◐ partial — stem-rename pending Phase D stems) · C ✅ **built** (C11/C12/C14/C15/C16 🔨 built 2026-06-03, live-verify deferred to C18; **C17/C18** 🔨 built 2026-06-04; **app-boot fix `18f1225`** closes the C17→C32 no-boot window (app runs core karaoke from here); **C18A `52cf2f6`** ffmpeg drop ✅ 2026-06-05 — **all Phase C commits built**; full-playback live-verify slips to C32; next: Phase D) · D 🔨 **begun** (**C19 `d4e2f6c`** scaffolding — config/context/stage-base, 18-test `test_pipeline_config.py`, 707 pass, /code-review clean (retroactive 2026-06-05; 1 C26A watch: `activity()` `sys.exc_info` exit check); **C20 `6f92ffe`** ffmpeg stages — extract/transcode/loudnorm/load-vocal + `run_ffmpeg`, 14-test `test_pipeline_ffmpeg_stages.py`, 721 pass, /code-review clean (retroactive 2026-06-05; 2 C27 watches: orphan-ffmpeg enter-window, loudnorm JSON-walker fragility) ✅ 2026-06-05; **C21 `8e406fd`** stem-separation worker — out-of-process Melband-Roformer (spawn IPC, OOM-exit+auto-restart, per-chunk cancel hook) + `StemSeparationStage`, 25-test `test_pipeline_stem_worker.py`, 746 pass, /code-review 2-agent clean (1 fix folded: `BaseProcess` annotation) ✅ 2026-06-05; **C22 `a8bf796`** whisper alignment worker — out-of-process faster-whisper (clears GPU cache every job; `refine=False` kwarg + back-compat 2/3-tuple `transcribe_words` dispatch) + `build_bundle` joint fields (schema stays v4); ported jad's 33-test `test_whisper_worker.py`, 779 pass, /code-review 2-agent clean (1 Review-fix folded: stale `align_refine` docstring) ✅ 2026-06-05; **C23 `956d79f`** Genius lyrics — `GeniusClient` (thread-safe `lyricsgenius` wrapper, empty-token→\[\]/raises, all-artists, query-aware blocked-term, INFO-log suppression) + atomic sidecar I/O; `genius_lyrics` differentiated cleanup (paren-contents kept, shared txt/SRT cleaners), 65 genius tests, 844 pass, /code-review 2-agent — 2 user-adjudicated Review-fixes folded (`search()` malformed-response guard honoring the `[] on any failure` contract; `_HAS_LETTER_RE`→Unicode-letter so non-Latin lyrics survive) + 1 not-a-bug (`clean_genius_query` NOISE reuse, intentional) 2026-06-08; **C24 `f023895`** two-pointer walk word matcher — `match_words_to_lines`/`_with_stats`: lockstep two-pointer walk (asymmetric lookahead + confirmed re-sync + whisper-skip budget; no DP table, no fuzzy scoring), short-run interpolation, long/degenerate-run drop, collapsed-matched-run demotion, per-run stats telemetry; diarization-free; 30-test `test_word_alignment.py`, 874 pass, /code-review 2-agent — **0 Review-fixes** (Agent-1 ≈28k-trial fuzz clean; Agent-2's 8 candidates all not-a-bug/out-of-scope: telemetry naming consumed as-is by `alignment_capture`'s knob-tuner, cross-line monotonicity = new feature beyond jad, early-return `start=0.0`-vs-`None` **refuted** — both ASS/SRT generators gate on `words` not `start`), **== jad at tip** (faithful pull); **subject corrected NW→walk** (historical NW port superseded before the jad tip; end-state is the walk matcher) 2026-06-08; **C25 `f1370e8`** tiling matcher — order-independent `match_words_to_lines_tiling`/`_with_stats`: `find_candidates` (sliding-window word-Levenshtein, raw matched-token score for coverage-max) + `best_tiling` (weighted-interval-scheduling DP, O(m log m)) + `find_anchor_candidates` (contiguous-run fallback for zero-candidate units); substantial-paren match-unit split (ad-libs stay inline); reuses C24 `_normalize_token`/`_walk_align`; 33-test `test_tiling_match.py`, 907 pass, /code-review 2-agent — **0 Review-fixes** (Agent-1 100k/50k-trial fuzz vs reference impls + brute-force DP: clean; Agent-2's 7 candidates all not-a-bug: cross-pass score scale is intended coverage-max + anchor is a zero-candidate last resort, `del align_lines` is documented API parity, rest are test-gaps on jad's faithful test file with code paths verified-correct), **== jad at tip**; **C26 `7238bd9`** lyric-fetch + lyric-align stages — **first multi-concern file split.** `LyricsFetchStage` (per-job source resolution: Genius / YouTube-SRT / raw-transcribe / SRT-fallback) + `LyricAlignStage` (walk/auto/tiling match with auto-escalation; `_load_lyrics` SRT-noise cleanup + inline-paren-kept TXT; tmp-then-move ASS+SRT). Restored whole from jad then surgically dropped the 9 opt-in-`joint` pieces (import, `use_joint` branch, `_run_joint`, capture locals/params, `joint_alpha`); `test_lyric_align.py` truncated to drop `TestJointRoute` — **C26→jad delta is exactly the joint pieces** (+ `elif`→`if`), re-added verbatim at C26A; `joint_match.py` correctly absent. 5 files (test_lyric_align 16 / test_lyrics_fetch 21 / test_lyric_conversion 16), 960 pass, /code-review 2-agent — **0 Review-fixes** (Agent-1 bug-hunt clean: all config reads real, 11 `build_bundle` kwargs match, ASS field counts + non-negative k/kf + no cs-rollover, lyrics_fetch branches + no-delete-on-GeniusUnavailable; Agent-2 split-integrity clean: no dangling joint refs (ruff F), `line_objects` bound on every path, `build_bundle` valid sans joint args, **interim `match_method="joint"` empirically → no crash, valid ASS, `none+walk`** benign fall-through). **2 files diverge by isort/black only** (`lyrics_fetch.py`/`test_lyrics_fetch.py` — jad not lint-clean under next's 100-char); `lyric_align.py` == jad-minus-joint. Spec's "default subtitle delay" not in these files — omitted from body. **C26A `702259f`** joint alignment DP matcher + opt-in route — `lib/joint_match.py` (679 ln): per lyric line, 1 align candidate (at alignment's span) + 0..n transcribe candidates (reuses C25 `find_candidates`/`find_anchor_candidates`), score `transcribe_match + α·align_agreement·alpha_weight`, `_best_tiling_by_time` interval-DP picks the max-score **monotonic-by-line_id + time-non-overlap** subset; per-word timings from the winner; unplaced lines soft-dropped (interp span). Wired into `LyricAlignStage` behind `match_method=="joint"` (joint route + `_run_joint` + capture-joint plumbing re-added — **the other half of the C26 split; `lyric_align.py`/`test_lyric_align.py` now == jad tip**, C26→C26A delta = exactly the joint pieces). Ships the **3 absorbed historical fixes** (lyric-id-monotonic DP = the Hakuna dialogue-interlude fix, lexical-set-intersection α-gate ≥2 words, `bisect_left` window bounds). 4 files (test_joint_match 35 / TestJointRoute 3), **test_joint_match green in isolation** (matcher needs no stage), 998 pass, /code-review 2-agent — **1 Review-fix folded** (corrected `_interpolate_missing` docstring: described per-word interp timings + a `source:"absent"` path the code never produces — missing lines are empty-words `interp` soft-drops). Agent-2 **220k-trial brute-force fuzz of `_best_tiling_by_time` → 0 mismatches** (score-optimal; all-negative empty-set edge unreachable, scores ≥0 by construction); Agent-1 verified all 3 fixes + DP/scoring/windowing sound. **Surfaced not-a-bug/design calls (left as jad's corpus-validated form):** soft-drop discards unplaceable lines' text+words (intended per joint design doc — opt-in; walk/tiling gap-fill instead), the `>` tie-break drops zero-score conflict-free lines (proven score-optimal), the dead `absent` stat path (schema-bearing telemetry). joint_match.py == jad **minus the docstring fix**. **C27 `48ada56`** orchestrator — `PipelineOrchestrator` runs stages in order with per-job cancellation (fresh `CancelToken`+`Event` per `run_one_async`), owns the eager/idempotent stem+whisper worker lifecycle, per-job tmp_dir create+rmtree, phase→`on_stage_change`; **new** 25-test `test_orchestrator.py` (the pipeline's first integration-seam coverage), 1023 pass, manual 3-axis gate + core /code-review clean — **2 Review-fixes folded** (leak-free worker start/stop on the OOM 2nd-start path; **closed C20's orphan-ffmpeg watch** — `run_ffmpeg` SIGKILL+reaps a proc cancelled in the Popen→`activity().__enter__` window); model-name watch defers to construction site C-PROC/C32, loudnorm-walker safe-today ✅ 2026-06-08; **C30 `0120d7e`** PTY process terminal pulled ahead of C28 (C28→C30 forward-dep) — verbatim jad + new 7-test smoke, 1030 pass, /code-review: test clean + 5 source findings all pre-existing verbatim-jad (3 relay/shutdown DEFERRED->**folded into C30 `2ef99c7` 2026-06-14**, 2 not-a-bug) ✅ 2026-06-08; **C28 `8d229dd`** ProcessingManager job queue — thin adapter over `PipelineOrchestrator` (daemon loop drains pending queue → 5-stage pipeline w/ phase-targeted cancel; owns ProcessTerminal + thread-name-gated PTY log routing), jad's 42-test file, 1072 pass, **2 dead-code cleanups folded** (redundant inner `import os`, dangling `# Helpers` divider), /code-review: test clean + 4 cancel/lifecycle BUGs DEFERRED to C-PROC (**#2/#3/#4 folded into C28 `9f8df45` 2026-06-14; #1 stop/_orchestrator left-unreachable**) (**no callers on `next` yet** — Flask/karaoke cancel+enqueue is C-PROC wiring; naive #4 fix proven wrong → needs `_run_loop` integration tests + live verify) ✅ 2026-06-08; **C29 `f9726b5`** PipelineTracker — download/processing monitor (lazy `get_status` derivation + server-side action-auth; no callers yet — wiring at C32/C-PROC); /code-review: **1 lock-scope deadlock fixed** (3 inside-`_lock` `_notify_change` dedented → `pipeline_tracker.py` == jad minus those 3), 3 deferred to C-PROC, 2 not-a-bug; 1072 pass ✅ 2026-06-09; **C32 `895bb19a`** karaoke.py processing wiring — GeniusClient/ProcessingManager(.start())/PipelineTracker built in `__init__` (processing auto-starts on a real download), temp_dir resolved + threaded to download/processing, `stop()` stops processing; **plan-directed deferred-fix folded** (`_cleanup_partial_downloads` now sweeps temp_dir — non-empty temp_dir → yt-dlp `--paths temp:` else orphans on cancel; jad has the bug; +1 regression); /code-review 1-agent: 0 bugs, 1 deferred (`ProcessingManager.stop()` unguarded `_orchestrator` if start() partially fails → C28 lifecycle bucket @ C-PROC), 1 not-a-bug (download_manager no graceful stop = jad); residual karaoke.py vs jad = exactly C35 + C38 + 3 C18-deviations; 1073 pass ✅ 2026-06-09; **Phase D complete**) · E 🔨 **begun** (**C34 `7080a3e`** live-controls prefs-half — `set()` skip block so saving a default `volume`/`subtitle_delay`/`vocal_volume` no longer jolts the live song (still persists → applies at next song start) + `routes/preferences.py` overlay/audio-delay live-refresh wiring held back from C15 (derefs `k.playback_controller.refresh_overlays`/`k.mpv_controller.set_audio_delay`, exposed only at C18); all 3 files == jad exactly; 1073 pass; /code-review 1-agent: 0 folded, 1 deferred (unvalidated `float(val)` on the `audio_delay` route — admin-only/no-template-UI/verbatim-jad) ✅ 2026-06-09; **C31/C33 fold-stubs → C-PROC**; **C35 `a06560d`** playback/UI half — `volume` property/setter (system-sink sync), live `transpose_current`/`set_subtitle_delay`/`set_vocal_volume`/`set_sub_mode`, `restart`→pc.restart, reset/get_now_playing additions; playback_controller 3 setters (race-free `pause()` deviation preserved); controller.py + conftest whole == jad; `routes/info.py` deferred to C38 (atomic render_template = settings-page rework); 1074 pass; /code-review 0 bugs / 2 deferred (route `float()`→500 low-sev; mpv `sub_delay`-outside-srt pre-existing); residual karaoke.py vs jad = C38 `admin_password` + 3 C18 deviations ✅ 2026-06-09; **C36 `4ca4c9d`** queue routes → processing model — **pull-forward (next was BEHIND, not ahead)**: adds `pause` queue action (`toggle_pause_song`) + labels, the server-side enqueue gate (`get_pipeline_state` in `pending`/`failed` → 409), and user self-service routes (`/queue/user/delete` ownership-checked via `_verify_ownership`, `/queue/user/pause` step-away). queue.py + test_queue_routes.py **whole-restored == jad** (all called symbols — `toggle_pause_song`/`toggle_pause_user`/`move_to_*`, `get_pipeline_state`, `Schema`/`fields` — already on next; pure-additive diff so the **C5A download-status removal is not re-added** (it'd show as a `-`-to-restore and none appears); `test_queue_socketio.py` already == jad, untouched despite the plan listing it); 1083 pass (+9); /code-review 1-agent — **0 fix-now bugs, 1 not-a-bug + 1 deferred**: gate-blocks-pending/failed is **jad-intentional** (`_process_song` deliberately leaves `pending` on cancel w/ "needs reprocessing" badge + jad has a dedicated 409 gate test class — a real "reprocess-before-queue" UX tradeoff but the owner's tested design, surfaced not overturned); file-browser **silent no-op on rejection** (gate's 409 + scalar `success` unhandled by files.html's `$.get`/`obj.success[0]` which expects the `[bool,msg]` success-path shape) **deferred → done in `fix(enqueue)` `2b9b5c5`** — the un-reconciled consumer is template-rework scope, and queue.py's 409 contract is deliberately tested so the fix belongs in the consumer ✅ 2026-06-09; **C37 `adc51e0`** search routes — **pull-forward (next was BEHIND: master-era search.py)**: reworked `search()` (drops the " karaoke" suffix / `non_karaoke` toggle, enriches each result via `find_by_id` to flag downloaded songs), `preview()`→single-call `get_preview_info` returning `(stream_url, srt_available)`, new `lyrics_search`/`lyrics_select` routes; `youtube_dl` `get_stream_url`→`get_preview_info` (the multi-concern file's last owed concern — reaches tip). search.py + test_search_routes.py whole-restored == jad-modulo-Black; youtube_dl.py hunk-applied (preserves next's dropped commented `--paths download:` line). 1097 pass (+14); /code-review 1-agent — **1 docstring bug-fix folded** (`get_preview_info` docstring claimed auto-captions; code checks only manual `%(subtitles)j`, matching the `--write-subs` download path — confirmed correct, docstring corrected), 1 not-a-bug (blank-line filter misorder unreachable: yt-dlp prints `NA` not empty); **search.html + test_search_render.py folded in here 2026-06-09** (the route's 6-tuple result else 500'd the /search results page — `ValueError: too many values to unpack`; C43 dissolved) ✅ 2026-06-09; **C38 `bda7ecb`** info/files/admin routes — **pull-forward (next was BEHIND: 3 master-era route files — info.py last touched by upstream flasgger→smorest `#777`, files.py by `#802`, admin.py by the sqlite-db commit)**: info.py settings `render_template` context reworked to the fork's options (`subtitle_delay`/`audio_delay`/`vocal_volume` from prefs, `audio_device` + `_audio_devices_for_render` unplugged-device helper + `/info/audio_devices`) dropping the upstream bg-music/scoring/avsync/cdg/score_phrases set — **net-fixes the route** since next's master-era info.py already `AttributeError`'d on `k.bg_music_volume` etc. (0 on next); files.py `browse()` enriches each page song into `{path,pipeline_state,tracker_status,is_active}` (per-page batched, no N+1, all 3 managers resolve); admin.py absorbs **Fix exit bug** (`sys.exit()`→`os._exit(0)` — threaded `delayed_halt` only killed its own thread, process never terminated) + guarded temp_dir rmtree on halt + failed-auth `admin.login`→`info.info` (`admin.login` was a **nonexistent endpoint → BuildError**). All 3 whole-restored **== jad byte-identical** (jad lint-clean here → pre-commit no-op, zero Black deviation). **Deviation (dead-code omission):** jad's `admin_password` `__init__` param **not added** — `apply_all` already sets `self.admin_password` from the DEFAULTS key (C17), `cli_args` is generic `locals()`, and **neither next's nor jad's app.py passes it to `Karaoke()`** → inert even in jad's end-state (CLAUDE.md no-dead-code); app.py `ADMIN_PASSWORD` line + controller.py already == jad. Residual karaoke.py vs jad = this param + 3 C18 deviations. Manual 3-axis (pre-existing bare `except:` in `get_system_stats` noted, not C38-introduced) + /code-review 1-agent **0 findings** (enrichment guards / info type-safety / temp-cleanup+`info.info`+`os._exit` + `auth` `next_url.startswith("/")` no-open-redirect verified; `/info/audio_devices` non-sensitive = jad parity). **Matching templates folded into C38 (2026-06-09):** info.html + files.html brought to jad end state **in this commit** (route rework else 500'd /info+/browse) + render tests; only the files.html enqueue-gate JS reconcile → **C42**. Residual info/files/admin.py + both templates vs jad = 0. 1097 pass (no test files in scope; `-k "info or files or admin or controller"` = 67 controller/mpv green); `import pikaraoke.{app,routes.info,routes.files,routes.admin}` OK; pre-commit clean ✅ 2026-06-09; **Phase E complete** (C34–C38 routes/live-controls; C31/C33 dissolved → C-PROC)) · F 🔨 **begun** (**C39 `cab05dc`** fontello regen — adds the clock glyph (clock overlay/info page) + spinner/minus/minus-circled/spin3 consumed by later Phase-F commits; whole-restored `static/fontello/*` **== jad byte-identical**, **next was BEHIND** (master-era, last touched upstream `#676`/`#564`; no recommit), 0 residual; **assets-only** — no auto-test, **no agent /code-review** (zero executable logic; proportionate manual gate = config↔css↔LICENSE↔font-cmap coherence, 5 unique code-points, no template consumers yet), `static/` pre-commit-excluded; 1097 pass (unchanged); **transient:** consumers (info.html clock → C38, home/queue minus/spinner → C40–C42) land ✅ 2026-06-09; **C40 `ffadef0`** base-layout styles hook + fork control-box CSS — **next BEHIND** (master-era base.html/custom.css, last touched upstream `#676`/`#777`/`#619`/sqlite). custom.css whole-restored **== jad byte-identical** (control-box `--controls-link-*` var-ization + subtitle-mode-btn block); base.html gains only the `{% block styles %}` hook (home.html C41 injects its `:root` vars through it). **Deferred to C-PROC** (jad grouped them in `97d62b16 Song Processing tracker`): the `#processing` nav `<a>` + base.html/spa-navigation.js active-state — `url_for('processing.processing')` would BuildError every render until the blueprint registers; spa-navigation.js untouched (single-bind already on next from upstream SPA, sole delta = processing active-state → C-PROC). **subject adjusted** (plan: "shared base layout + single-bind SPA navigation"; SPA single-bind already on next & untouched). **Zero executable logic → no agent /code-review** (like C39); gate = Jinja-parse + 238 render tests + full-suite. **Transients:** custom.css `var(--…)` defs land C41 (graceful degrade until then), subtitle-mode-btn consumer C38/C41. 1097 pass (unchanged — no Python); base.html pre-commit clean, custom.css `static/`-excluded ✅ 2026-06-09; **C41 `1145224`** home/now-playing overhaul — **next BEHIND** (master-era home.html, last touched upstream `#727`/`#657`/`#619`). Whole-restored from jad, then **3 bug-fix deviations** (bug-fix-first): (1+2) null-guard the seek/time `getElementById` derefs in `handleNowPlaying` + the `playback_position` handler — both stay bound to the shared socket after navigating away (NO page `.off`s playback_position; only queue `.off`s now_playing), so the raw `.innerHTML`/`.value` threw a TypeError every position-tick / now_playing-push on any non-home page during playback; (3) added the missing `else { hide() }` to the control-box owner check so a non-admin ex-owner loses controls when the song advances to another user's track. **Closes C40's transient:** home.html's `{% block styles %}` `:root` defines `--controls-link-*` et al. that custom.css consumes. All backend already on next (`/seek`//`sub_mode`//`vocal_volume`//`subtitle_delay` routes + now_playing payload fields incl. subs_available/dual_stem/sub_mode). **Logic-heavy → 3-agent /code-review** (line-by-line · removed-behavior+data-contract · socket-lifecycle): 2 BUGs fixed above; **deferred watch** — the visibilitychange reconnect branch rebinds only now_playing (not playback_position) on the fresh socket → seek bar freezes after a background-tab socket reconnect (now null-safe/no-crash; candidate for a socket-lifecycle follow-up); not-a-bug — step-button null-derefs safe by construction (icons share the gated section with their sliders), controller routes server-ungated is pre-existing & out-of-file-scope. Jinja-parse OK, 1097 pass (unchanged — no Python), home.html pre-commit clean ✅ 2026-06-09; **FOLD (2026-06-09):** C38's render-window 500s — /info (`UndefinedError: score_phrases`) + /browse (`TypeError: ...not dict`), both from the route rework (`bda7ecb`) shipping ahead of its master-era templates — closed by folding info.html + files.html (jad end state) + render tests **into C38 itself** (absorbing the out-of-band browse fix `70b940d`); fold exact (C38 was last to touch both routes), verified green at C38 (4 render tests pass there). C38..C41 re-SHA'd; only the files.html enqueue-JS reconcile → C42 ✅ 2026-06-09; **C42 `521081e`** queue page rework — `queue.html` whole-restored from jad **== byte-identical** (JS-driven live page: fetch `/get_queue`+`/now_playing`, snapshot-diff redraw of `#auto-refresh`, admin Sortable drag-reorder→`/queue/reorder`); route already at jad (**C36**) so **no render-window gap** (no server-side queue loop; "queue seems fine" pre-swap), all url_for resolve (`now_playing.now_playing` registered), context (queue/admin/site_title/title) matches; **verbatim restore → proportionate gate, no agent review** (render-smoke /queue 200 admin/non-admin × empty/populated, pre-commit clean, **1103 unchanged**); 0 residual; the enqueue-gate JS reconcile (files/search 409 no-op) is split to its own `fix(enqueue)` **bug-fix-first divergence** (jad has the bug; queue.html has no enqueue handler) ✅ 2026-06-09; **FIX `2b9b5c5`** enqueue-gate 409 client reconcile — files.html `$.get` `.fail()` + search.html selectize `error:` cb + `enqueueLocalSong` `result.success[0]` unpack (the `[ok,msg]` list is always-truthy → the old check left the else **dead**; now-live else surfaces `success[1]`) & always-toast error parity, no selectize-wipe on failure; **closes the long-tracked C42 watch** (bug-fix-first divergence — jad ships the bug; queue.html untouched == jad); manual 3-axis + /code-review 2-finders (3 findings = the fixes), **1103 unchanged**, render-tests/pre-commit clean; **C-PROC `54138f0`** processing page — `routes/processing.py` + `processing.html` + 41-test `test_processing_routes.py` whole-restored **== jad**; app.py `processing_bp` reg + `_pipeline_changed`→`_on_change` push (== jad); **+ nav fold (base.html navbar `<a>`/active-state + spa-navigation.js SPA active-state, the C40-deferred menu entry — user-reported "page not on the UI")**; the cancel UI goes live → **3 Review-fixes folded** (broadcast_event import NameError that killed the push; `_cancelling` flag suppressing the spurious danger toast on user-cancel; `cancel_pending_download` `_cancelled_urls` permanent leak + silent-re-queue, incl. the **review-caught active-misroute TOCTOU** → delegate to `cancel_active_download` when the URL is actually downloading); absorbs the processing-UI bug class + tracker-debounce (UI half; model = C29); **/code-review 2 convergent finders both caught the TOCTOU leak + a false-green in-flight test** → fixed (kill-not-record + a real worker skip+discard integration test); +6 download_manager tests, **1150 pass**, pre-commit clean; still-deferred: ProcessingManager.stop()/`_orchestrator` (unreachable) + pre-existing C5 dup-URL desync (**C28 #2/#3/#4 + C30 #1/#2/#3 races folded into their commits 2026-06-14**) ✅ 2026-06-10; **Phase F complete**) · G 🔨 **begun** (**C46 `09af50c`** i18n catalog regen — documented `_TRANSLATION.md` pybabel extract/update/compile on next's source; the regenerated 237-msgid pot == a fresh extract from jad's own source (0 set-diff both ways), removed-UI/download-status strings retire to `#~` obsolete & drop out of the .mo, processing/clock strings go active, the repo's `#.` translator comments restored (jad's bare extract had dropped all of them), compiled w/o `-f` so uncertain fuzzy auto-matches fall back to untranslated English; pure data regen → no agent review; 31 files, all 15 .mo load, `import pikaraoke.app` OK, pre-commit clean. **jad's stale 2026-05-02 catalogs intentionally NOT the target** — translation files diverge from jad by design. **C47 `a5567d7`** backfill script — `scripts/backfill_artifacts.py` (511 ln) + `scripts/README.md` whole-restored from jad, the last code commit; `--match-method {auto,walk,tiling,joint}` / `--use-bundle-lyrics` flags in final form; cross-file seams all verified, 3-agent /code-review, **2 Review-fixes folded** (worker `start()` moved inside `run_jobs`'s try/finally so an OOM 2nd-start no longer leaks the 1st worker's GPU subprocess; stale README updated to document `joint` + `--use-bundle-lyrics`), 3 candidates left by-design; `--help` auto-test + pre-commit clean, 1150 pass ✅ 2026-06-10. **FINAL GATE ◐ run 2026-06-10 — static + CPU-side complete** (see GATE row): full suite **1150 green** + pre-commit **--all-files clean** after 2 gate fixes (the 6 `processing.processing` render-fixture failures **folded into C-PROC** — fixup+autosquash re-SHA'd C-PROC→`54138f0`/C46→`09af50c`/C47→`a5567d7`; 2 all-files-only lint stragglers → tip `style:` **`a5072a5`**); `git diff joint-alignment-dp` review **PASS** (every source hunk = a recorded Review-fix; translations intentionally large per C46); **CPU e2e smoke PASS** (boot/search/enqueue→dual-stem playback w/ `.ass` subs + overlays screenshot-verified, clock pref toggle, controls, de/fr locales, download→tracker→cancel→clean quit). **DEFERRED → GPU env (user instruction 2026-06-10): all inference legs** — processing-to-complete (stem+whisper), the **joint-route smoke** (`backfill_artifacts --match-method joint`), `--hide-clock` boot check. **PR not opened** (user instruction).)

| Commit | Status | `next` sha | Decisions / review-fixes / deviations |
|--------|--------|-----------|----------------------------------------|
| C0 | ✅ 2026-06-01 | `4f8f9e4` | Full dependency manifest (pyproject/requirements/uv.lock, win32 cu124 index). **Windows `uv sync`/`uv lock --check` verify still pending**; wart#2 pin reconcile on Windows lock regen — see Standing deviations. |
| C1 | ✅ 2026-06-01 | `4b89376` | Remove dead static assets + model-folder gitignores. `raspi_wifi_config` removal deferred to C15 (done there); `logo.png` kept. |
| C2 | ✅ 2026-06-01 | `288836e` | Central `get_temp_directory()` helper. Caller wiring + temp-dir verify deferred to C18/C32. |
| C3 | ✅ 2026-06-01 | `a6a5267` | Docs: compact CLAUDE.md, correct README playback (libmpv, not browser). |
| C4 | ✅ 2026-06-01 | `bae9793` | yt-dlp `--impersonate chrome` on all calls + unrestricted default search. (youtube_dl multi-concern: `get_stream_url`→`get_preview_info` still owed at C37 — Standing deviations.) |
| C5 | ✅ 2026-06-02 | `6134499` | DownloadManager: serialized worker, hardened errors, literal-safe partial-glob (library-wipe fix absorbed), `.srt`→`subtitles/`. Cancel error-toast suppression owed at C-PROC — Standing deviations. |
| C5A | ✅ 2026-06-02 | `2664381` | Remove obsolete download-status polling surface (brought forward; C36/C42/C-PROC keep their other changes — Standing deviations). |
| C6 | ✅ 2026-06-02 | `41be63f` | Canonical `extract_youtube_id()` helper (single source; scanner routed through it at C8). |
| C7 | ✅ 2026-06-01 | `7af1b75` | DB schema: `pipeline_state` + `loudnorm_offset_db`, idempotent v1→v2 migration + accessors. Loudnorm DB layer absorbed here, **not C14** — Standing deviations. |
| C8 | ✅ 2026-06-02 | `bb51f4a` | Scanner: stamp `pipeline_state`, bare-extension format, route through `extract_youtube_id` + drop the duplicate private extractor (deviation — Standing deviations). |
| C10 | ✅ 2026-06-02 | `80840c8` | queue_manager paused-song model (`pop_next` skips paused, `has_playable_song`, `toggle_pause_song/user`). Dormant until `routes/queue.py` wires the pause UI (later commit). |
| C9 | ◐ 2026-06-02 | `72b9e02` | `song_manager`: companion handling rewritten to manage **stem tracks** (`vocal/`+`nonvocal/` `---vocal.m4a`/`---nonvocal.m4a`), downloaded `.srt` (in `subtitles/`), and karaoke `.ass` (in `karaoke/`) in their subfolders; `rename` keeps each companion in its own subfolder via a basename-tail (`os.path.basename(c)[len(base):]`). Adds `events=` ctor arg (default `None`; `karaoke.py:207` caller unchanged) and a `song_deleted` emit on delete. `register_download` stamps `pipeline_state="pending"`. **Pipeline_state forwarders included** (`set/get_pipeline_state`, `get_pipeline_states` → C7 DB methods); **loudnorm forwarders excluded → C14.** **Plan-language deviation:** the plan's C9 "Cancel deletes via a literal-safe glob (absorbs the library-wipe fix)" is **stale** — that fix landed in **C5** (`_cleanup_partial_downloads`); C9's `song_manager` has **no glob** (literal `os.path.exists` paths), so the no-wipe property holds by construction (dropped the line from the commit msg). **Manual review: clean** — `os.path.exists` replaces `os.listdir`+`OSError` guard (fewer syscalls, no swallow); `events=None` dormant until Phase D wires `pipeline_tracker._on_song_deleted` (the only `song_deleted` listener). **New tests beyond end-state** (end-state only swapped `.cdg/.ass`→`.srt`): stem+caption delete, stem rename-within-subfolder, `song_deleted` emit, and `test_delete_leaves_unrelated_song` (bracketed-name sibling survives — documents the no-wipe guarantee). 29 song_manager tests green; lint clean. **Verify now (runnable):** rename a song with a separated stem → the stem renames too; delete a song with brackets in the name → only that song goes. **Partially verified 2026-06-02:** delete-bracketed + rename OK; **stem-rename pending — no stems exist until Phase D processing.** |
| C12 | 🔨 2026-06-03 | `4e9350f` | **Built before C11 (build-order swap):** `mpv_controller.py` (C11) imports `overlay_manager` at module top, so C12 must land first (overlay_manager imports mpv_controller only under `TYPE_CHECKING` — no runtime cycle). **C-CLK collapsed into this commit (user-approved):** shipped `overlay_manager.py` whole, clock OSD render included, rather than excluding it for a dedicated C-CLK (the clock-split would have required `e`-exclusions from 8 commits; see standing deviation). **/code-review run (per-commit, from C11 on).** Folded Review-fix (concern-owner = this commit, single-touch file): `invalidate()` no longer does `self._last_sent = {}` (which would orphan now-undesired overlays on the next frame); instead sets a `_force_resend` flag so the next `apply()` still re-diffs and clears overlays no longer desired (`elif new is not None and (new != old or self._force_resend)`), then resets the flag before `self._last_sent = desired`. Added regression test `test_invalidate_still_clears_now_undesired_overlays`. **Folded Review-fix 2 (reopen 2026-06-04, bug-fix-first; reattributed from C11):** `_ass_escape()` neutralizes ASS metacharacters in user-supplied overlay text — `{`/`}` (override-block delimiters) → parens, `\` (line-break codes `\N`/`\h`) → a lookalike glyph — applied per user field (title/singer/now-playing/url) so a YouTube title with `{…}` or `\N` can't inject styling tags or line breaks into the OSD; the builders' own intentional override tags + row separators stay intact. +8 tests. **Dormant at this tip** — not wired until C18. Verify: live behavior at C18 once wired. |
| C11 | 🔨 2026-06-03 | `2001949` | `mpv_controller.py` (libmpv wrapper: `_safe` decorator, `play`/`stop`, single/dual-stem Rubberband `build_filter`, subtitle modes, `set_vocal_volume` via ZMQ, volume backend wpctl/pactl/amixer, QR generation) + `test_mpv_controller_audio_device.py` (from plan). **New tests (plan-required):** `test_mpv_controller.py`, 18 tests — callback registration, song-end (idle) hook + re-entry guard, pause toggle, property/playback setters, `build_filter` single/dual-stem ± normalization. **/code-review: 4 finder angles.** Folded Review-fixes (all concern-owned here; file is single-touch → no clobber): (a) `logging.*`→`log.*` (module logger); (b) single top-level `import re` (dropped 3 fn-local); (c) `get_system_volume` `except Exception as e: log.warning(...)` not silent pass; (d) `quit()` two excepts `log.debug` not pass; (e) `set_vocal_volume` ZMQ socket closed in `finally` + `LINGER=0`; (f) `send_qr_bitmap` `with Image.open(qr_path) as qr_src:`; (g) `play()` duration guard — only set `self.duration` when `float(player.duration or 0)` > 0. **Resolved (folded on reopen 2026-06-04, bug-fix-first — `Review-fix:` block 2, +15 mocked tests):** dual-stem audio-add race (blind `time.sleep(0.2)` → bounded poll on the track list until both added audio tracks register); `_duration_ready` clear/set race (`self.duration` reset alongside the event so a missed observer can't keep the prior song's duration); play/stop shutdown race (capture the player, no-op when None, swallow `mpv.ShutdownError`); wpctl muted-sink (report 0 for a `[MUTED]` sink). **Reattributed → C12:** ASS metachar escaping is C12's concern — the user-text ASS composition lives in `overlay_manager.py`; `mpv_controller.osd_overlay` only passes data through. Fixed at **C12** (`4e9350f`). **Not-a-bug (intentional / correct-at-tip):** `_server_url` empty until C18 (wired there); QR-height duplication (cosmetic dup); sub-remove segfault-workaround (a deliberate libmpv workaround — fragile but functional). **Resolved:** `_build_url_overlay` `screen_w` div-by-zero (fixed at C14 — `osd_size` clamps falsy→1920/1080). **Dormant at this tip** — not wired until C18/C14. Reopened 2026-06-04 to fold the four fixes above; full unit suite green at tip; lint clean. Verify: live behavior at C14/C18 once wired. |
| C13 | ⤳ relocated | — | **Relocated to C18A** (user decision 2026-06-03). Helpers stay inert dead code through C14–C17; dropped whole at C18A. Rationale → Standing deviations; build spec → C18A. |
| C14 | 🔨 2026-06-03 | `0fe8613` | `playback_controller` migrated onto `MpvController` (play/pause/seek/skip/restart, `_find_subtitles` `.ass`/`.srt` + `_find_companions` dual-stem, `build_overlay_state`/`refresh_overlays`/`broadcast_position`). **Loudnorm folded whole:** `get_loudnorm_offset` injection (default `lambda→None`, dormant until C18 wires it) + applied as MPV filter via `mpv.play(normalization_db=)` + graceful DB-read failure (try/except → no normalization); `song_manager` `get/set_loudnorm_offset` forwarders (`karaoke_database` layer already in C7 — **not touched here**). **Split (clean, by method):** pulled `playback_controller.py` whole minus the 3 C35 live setters (`set_subtitle_delay`/`set_sub_mode`/`set_vocal_volume`) + their one test (`test_set_subtitle_delay`) → those ride C35; file diffs jad by exactly that until C35. **/code-review: 4 finder angles.** **Folded Review-fix (DEVIATION from end-state, user-approved — see standing deviation):** restored `pause()`'s `self.is_paused = not self.is_paused` toggle + derive the notification from it instead of the observer-lagged `self.mpv.is_paused`. The MPV migration had regressed this from the pre-MPV code: `/pause` (`routes/controller.py:28`) reads `pc.is_paused` to pick its broadcast, and the `_on_pause` observer updates `mpv.is_paused` only later on mpv's event thread → stale broadcast + invertible Pause/Resume notification. Both regressions persisted in jad. Regression test `test_pause_toggles_controller_state_independently_of_mpv_lag` added. **Not-a-bug (intentional / dormant — left as-is):** `get_loudnorm_offset` default-lambda seam (dormant until C18 wires it); 3× subtitle `os.path.exists` recompute (efficiency nit, bounded-to-bugs); `now_playing_duration` cache-vs-live (intentional cache); `end_song`'s defensive mpv-reset block (deliberate guard). **Resolved:** the C11-flagged `_build_url_overlay` `screen_w` div-by-zero — `osd_size` clamps falsy→1920/1080 and the provider (`build_overlay_state`) sources `screen_w` from it, so it can't be 0. **Intermediate window:** `Karaoke()` instantiation breaks C14→C18 (karaoke.py still passes `streaming_format=`, omits `mpv`); `import pikaraoke.app` unaffected (construction is inside `Karaoke.__init__`); no test constructs the real `Karaoke`. 749 unit pass (24 in `test_playback_controller`, incl. regression); lint clean (Black reformatted the added test). **Verify:** live behavior at C18 once wired; loudnorm audible after a song is processed (C20+). |
| C16 | 🔨 2026-06-03 | `47bab42` | gevent→threading + splash-socket teardown. **`app.py` (C16 hunks):** drop gevent (`monkey.patch_all`/`WSGIServer`/`spawn`), `async_mode="threading"`, **add** `_NoGetFilter` werkzeug access-log filter, `socketio.run(allow_unsafe_werkzeug=True)` + daemon `k.run`/`upgrade_youtubedl` threads + `k.stop()`/temp-cleanup `finally`; drop Browser/file_resolver/stream/splash/bg-music imports + blueprint-list entries + the browser-launch block. **Restores `import pikaraoke.app`** (closes the C15 standing deviation). **`routes/socket_events.py` whole** (drop `register_splash`/`handle_playback_position`/`handle_disconnect`/`start_song` + splash globals + `import logging`; keep `end_song`/`clear_notification`). **Split — `n`-skipped, owned later:** Karaoke ctor kwargs → **C32**; `processing_bp` import+registration + `_pipeline_changed` push wiring → **C-PROC**; `ADMIN_PASSWORD` source → **C38**. So `app.py` diffs jad by those deferred hunks **plus the Review-fixes below**, and so will **not** equal jad at the tip (see Standing deviations). **Commit-message correction (not a code deviation):** the plan's suggested body said the werkzeug filter is *removed* — the code *adds* it (threading reintroduces the GET/2xx-3xx access-log noise gevent silenced via `log=None`); wrote an accurate message. **Test-routing deferrals:** conftest + `test_karaoke_utils` `now_playing_url`/`now_playing_subtitle_url` drop → **C18** (its conftest hunk is mixed with the mpv-mock additions; pure catch-up since C14 already dropped these from the real PC, and C16 stays green without it); `test_song_list` "(CDG format)" docstring → **C17**. **Manual gate + automated /code-review (xhigh: 2 convergent finder angles + verify + sweep):** top finding — the shutdown `finally`'s `k.temp_dir`/`k.stop()` `AttributeError` at this commit — **verified correct-at-tip** (jad's `Karaoke` wires `temp_dir` + an mpv-quitting `stop()` at C18; the atomic `try/finally socketio.run` can't split from C16), so it is an expected intermediate-window artifact resolved at C18, not a bug. **Review-fixes folded (DEVIATIONS — bug-fix-first; folded 2026-06-04, re-verify):** (1) purged the dead `get_platform`/`is_windows`/`get_data_directory` imports + the orphaned `platform = get_platform()` local (Android-block removal stranded `platform`; the other two were already dead in master); (2) anchored `_NoGetFilter`'s status match to the access-log line tail (`r'" [23]\d\d \S+\s*$'`) so a non-access record or a crafted path echoing `" 2xx "` can't be over-suppressed (was a bare substring match); (3) dropped `socket_events.py`'s unused `from flask import request` (pycln tolerated it). `app.py`/`socket_events.py` no longer equal jad. **Cross-file tracer cleared the deletions** — zero live emitters/listeners for `start_song`/`register_splash`/`playback_position`/`splash_role`. 657 unit pass (17 slow deselected) + 16 routes; `import pikaraoke.app` OK; pre-commit clean. **Verify (deferred to C18/tip):** app starts + serves pages; queue change pushes to browser; Ctrl-C shuts down cleanly. |
| C15 | 🔨 2026-06-03 | `981bee0` | Removed the legacy streaming stack — `git rm` of `lib/{stream_manager,file_resolver,browser,omxclient,raspi_wifi_config}.py`, `routes/{stream,splash,background_music}.py`, `templates/splash.html`, `static/{fireworks.js,js/splash.js,js/subtitles-octopus*,score.*,screensaver.*}`, and the 3 superseded tests (`test_stream_manager`/`test_file_resolver`/`test_splash_routes`). **raspi_wifi_config dropped here** (closes the C1→C15 standing deviation — its only consumer was `routes/splash.py`). **`preferences.py` split (clean, by concern):** the score-phrase teardown (drop `_get_active_score_phrases` import + `_SCORE_PHRASE_KEYS` + the two `score_phrases_update` broadcasts) lands here per "splash/score teardown → C15/C16"; the **overlay/audio-delay live-refresh wiring** (`_OVERLAY_PREFS`/`refresh_overlays()`/`set_audio_delay()`) is **deferred to C34** (it needs `k.mpv_controller`, which doesn't exist until C18). `test_preference_routes.py` reaches its **end-state here** — the entire master..jad diff for that file is score-teardown (drop the `_get_active_score_phrases` patch, delete the 2 score-phrase tests, simplify the reset test, swap the removed `disable_bg_video` pref for `volume`); restored whole from jad. **/code-review: 2 finder angles (removed-behavior auditor + cross-file tracer).** **Zero hard breaks in surviving files** — no Python/JS/template/socket consumer of any deleted symbol remains (verified `routes/info.py:77` builds its `score_phrases` template var from `k.low/mid/high_score_phrases` attrs, **not** the deleted helper, so `/info` still renders). **Deferred-fix (vestigial — removed when each file reaches end-state):** `info.html`'s Score-phrases form + `info.py`'s `score_phrases` context still exist here (no display surface now that splash is gone; saves still persist). jad drops `score_phrases` entirely (0 refs vs master's 4 in `info.py` / 13 in `info.html`): the `info.py` context rides with **C38** (info routes), the `info.html` form with **C38** (info template); the `*_score_phrases` DEFAULTS drop at **C17**. Not left as jad design. **Intermediate import break (see standing deviation):** `app.py` still imports `browser`/`file_resolver`/`stream`/`splash`/`background_music` at module level → `import pikaraoke.app` fails this one commit; **C16** removes those imports + the browser/temp-dir lifecycle as a cohesive unit. No test imports `app`, so the suite is unaffected — **674 unit pass** (749 − 3 deleted test files − 2 removed score tests); lint clean. **Verify:** at C16/tip — app boots; `/splash` & `/stream` 404; `/info` renders; no console errors on remaining pages. |
| C17 | 🔨 2026-06-04 | `78724d9` | args + preference renames for overlays. **`args.py` whole (single-concern):** dropped the ~19 splash/browser/streaming/bg-music/score/admin/dolphly flags, renamed `--hide-overlay`→`--hide-now-playing-overlay`, inverted `--show-splash-clock`→`--hide-clock` (opt-out overlay; **`--hide-clock` rides here per C-CLK dissolution**), reworded `--logo-path` for the MPV window. **`preference_manager.py` `DEFAULTS` hunk only:** dropped the removed keys (incl. the **`*_score_phrases` DEFAULTS drop** owed since C15 + the vestigial splash/streaming keys), renamed `hide_overlay`→`hide_now_playing_overlay`, added the MPV-era keys (`subtitle_delay`/`audio_delay`/`vocal_volume`/`temp_dir`/`hide_clock`/`blocked_processing_words`/`admin_password`/`genius_token`/`audio_device`). **Split (clean, by concern):** the `get()` signature reformat + the per-song-override skip block stay at master here → **C34** (file diffs jad by exactly those two until C34). **Tests:** `test_preference_manager.py` DEFAULTS-coupled hunks (unicode key swap, `defaults_exist` set, `defaults_types`) land here; the `test_set_syncs_target_object` `volume`→`splash_delay` hunk is skip-block-coupled → **C34**. `test_song_list` "(CDG format)" docstring trim caught up here (deferred from C16). `test_args.py`/`test_preference_routes.py` already at end-state (empty diff). **Bug-fix-first: no bug in the C17 end-state — faithful reconstruction, no Review-fix.** **Cross-file grep (plan review step):** every surviving reader of the removed/renamed prefs is in a legitimately-deferred file — `app.py`'s `Karaoke(...)` call-site reads the removed `args.*` flags → **C32** (the documented "won't fully boot C17→C32" window; `import pikaraoke.app` still OK — the call is inside `main()`); `ffmpeg.py` `build_ffmpeg_cmd` params inert → **C18A**; `info.py` `k.*` attrs consistent at this tip (karaoke.py keeps them until C18) → **C38**; karaoke.py signature/attrs → **C18**. 695 unit pass; `import pikaraoke.app` OK; pre-commit clean. **Verify (deferred to C18/tip):** `pikaraoke --help` lists `--hide-now-playing-overlay`/`--hide-clock`, not the removed flags. |
| C18 | 🔨 2026-06-04 | `77eb029` | karaoke.py MPV wiring — "playback goes live." **Hand-split the four shared atomic hunks** (imports / `__init__` signature / class attrs / docstring) to take only the mpv concern; **C32/C35/C38 modules don't exist yet so the split is mandatory, not optional** (the plan's "merge C18+C32" fallback is unavailable here). **C18 took:** drop `import socket` + `supports_hardware_h264_encoding` (import+probe); add `MpvController`/`QueuedSong` imports; signature/attr legacy removals (`bg_music_*`/`bg_video_*`/`streaming_format`/`prefer_hostname`/`hide_splash_screen`/`screensaver_timeout`/`default_bg_*`) + renames (`hide_overlay`→`hide_now_playing_overlay`, `show_splash_clock`→`hide_clock`); MpvController init + `set_callbacks`(`_on_song_end`/resize/tick) + `start(audio_device, audio_delay)` + post-start `set_system_volume`; overlay-state-provider block; `get_url` prefer_hostname-branch drop; `stop()` `mpv_controller.quit()`; run-loop `is_running` guard + `broadcast_position` + `has_playable_song()` + drop `log_output()`; `get_now_playing` up-next paused-skip; datefmt `%H:%M:%S`. **Key simplification:** `PreferenceManager.apply_all()` setattrs **every** DEFAULTS key (added in C17) onto the instance, so C18 needs **zero new signature params** — `self.audio_delay`/`self.audio_device` resolve from DEFAULTS; the new params (`genius_token`/`blocked_processing_words`/`temp_dir`→C32, `subtitle_delay`/`audio_delay`/`vocal_volume`→C35, `admin_password`→C38) defer to their owners. **Deferred (residual karaoke.py diff vs jad = exactly these):** C32 processing/pipeline/Genius imports+blocks + `temp_dir` resolve + `song_manager events=` + `download_manager temp_dir=` + `stop()` processing-stop; C35 `_volume` property + `transpose_current`/`volume_change`/`restart` rewrites + `set_subtitle_delay`/`set_vocal_volume`/`set_sub_mode` + `reset/get_now_playing` additions; C38 `admin_password` param. **Tests:** conftest `mpv_controller` MagicMock (C18's `stop()` quits MPV) + `MagicMock` import + drop `now_playing_url`/`now_playing_subtitle_url` (class attr/reset/dict); `test_karaoke_utils`/`test_queue_socketio` drop those stream fields; `test_queue_socketio` gains `TestQueuePauseSocketEmissions` (4 tests: toggle_pause emits, up-next skips/nulls on paused) validating the up-next paused-skip; the now_playing_url/conftest cleanups were **deferred here from C16**. C35 mocks (`restart`/`set_pitch`/`broadcast_position`/`set_subtitle_delay`, `subtitle_delay`/`vocal_volume`/`temp_dir`) + C32 `processing_manager` mock deferred (not needed until those methods are tested). **MockKaraoke binds the real `Karaoke` methods**, so deferred (master) `volume_change`/`restart`/`reset/get_now_playing` stay green; suite can't catch method-level correctness (no test builds the real `Karaoke`), so the split is for review-cleanliness — the hard gates are *imports clean* + *suite green*. **Bug-scan:** every C18 call maps to a real C11/C14 API (`start(audio_device,audio_delay)`, `set_callbacks`, `set_overlay_state_provider`, `tick_overlays`, `PlaybackController(mpv=,get_loudnorm_offset=)`, `broadcast_position`, `build_overlay_state`, `_playback_lock`, `song_manager.get_loudnorm_offset`) — no latent runtime bug. **/code-review (xhigh: 3 finder angles + verify + sweep):** one verified finding — the `try/except RuntimeError` around mpv `start()`/`set_system_volume()` was **dead**: a missing libmpv raises `OSError` at module-top `import mpv` (before `__init__`); `mpv.MPV()` start failures raise python-mpv exceptions, not `RuntimeError`; `start()`'s sole `RuntimeError` (audio-backend probe) is caught inside `start()`; and `set_system_volume` swallows its own errors — so the handler matched nothing `start()` throws and its "Install MPV" message was unreachable. **Resolved (Review-fix, bug-fix-first — user chose _drop_ over lazy-import-in-C11 / leave-as-is):** removed the dead try/except; behavior-neutral for real failures (they propagate either way), deletes the misleading message (`77eb029` amended in). Review verified-clean otherwise: `audio_delay` ordering (set by `apply_all` before `start`), every C11/C14 call signature, `has_playable_song`/up-next paused-skip vs `pop_next`, no surviving `now_playing_url` reader (py/html/js/tests), `broadcast_position`'s `if self.is_playing and socketio` None-guard, the `_on_song_end`/`_playback_lock`/`end_song` lock contract. **DEVIATIONS from jad (carried):** (1) the post-start system-volume comment describes the plain attr — jad's references the `.volume` property setter, which lands in **C35** (C35 reconciles the comment when it adds the property); (2) three event-bridge lambdas keep their unparenthesized, Black-clean form (jad has redundant parens); (3) `log_and_send` "danger" still logs at `logging.error` (jad downgraded to `warning`) — the sole karaoke.py line still at master, a non-mpv log-noise tweak kept as a deliberate divergence — error-severity is correct for a danger notification; see Standing deviations — not reconciled to jad. 699 unit pass; `import pikaraoke.{karaoke,app}` OK; pre-commit clean. **Verify (full boot needs C32 — slips to C32/tip):** queue a song → plays in MPV with audio; now-playing/up-next overlays; pause/skip/restart/±volume; live transpose. **\[Superseded — app boots from `18f1225` below; live playback verifiable there or via the standalone smoke.\]** |
| app-boot | 🔨 2026-06-04 | `18f1225` | **App-boot fix — closes the C17→C32 no-boot window** (new commit between C18 and C18A; pulls C32's call-site + C38's ADMIN_PASSWORD line forward, per user decision to restore per-commit runnability). Two `app.py main()` refs broke against C17's args removal + C18's signature: the `Karaoke(...)` call-site passed dropped/renamed kwargs (`streaming_format`/`hide_overlay`/`bg_music_*`/…) → `TypeError`; and `ADMIN_PASSWORD = args.admin_password` read the C17-removed `--admin-password` → `AttributeError`. Fixed both to jad end-state: call-site passes only surviving kwargs (rest hydrate from DEFAULTS via `apply_all`); `ADMIN_PASSWORD = k.admin_password or None` (`""`→None here). **Residual app.py vs jad now = only the C16 cleaner-than-jad bits (purged get_platform imports, anchored `_NoGetFilter` regex, dropped `platform` local) + the C-PROC processing_bp/pipeline_tracker wiring** — the call-site + ADMIN_PASSWORD hunks are gone, so **C32 no longer touches app.py's call-site and C38 no longer touches ADMIN_PASSWORD**. **Still degraded (expected, by design):** no processing pipeline → songs play as their full downloaded mix (C-PROC/C32); `/info` 500s on `k.hide_overlay`/`k.show_splash_clock` reads until **C38**. **Verified by isolated real boot** (temp HOME/DB, empty lib, port 5599; confirmed `pikaraoke.__file__` = pk-next, not the jad editable-install — see \[\[project-editable-install-runs-jad-worktree\]\]): MPV starts, "PiKaraoke started at" logs, Flask serves on 5599, clean SIGINT → "MPV stopped"; no stem/whisper workers, no traceback. 699 unit pass; pre-commit clean. |
| C18A | 🔨 2026-06-05 | `52cf2f6` | **ffmpeg drop (relocated from C13)** — single-touch `lib/ffmpeg.py` to its end state: dropped `build_ffmpeg_cmd`/`get_media_duration`/`supports_hardware_h264_encoding` + the imports they pulled in (`ffmpeg`, `platform`, `logging`, the `FileResolver` `TYPE_CHECKING` import, `__future__`/`typing`), leaving `get_ffmpeg_version`/`is_transpose_enabled`/`is_ffmpeg_installed` over a lone `import subprocess`. C18 cleared the last consumer (karaoke.py) and C15 had already dropped stream_manager/file_resolver, so all three were dead. **Plan-note correction (stale `git rm`):** jad does **not** delete `tests/unit/test_ffmpeg.py` — it keeps a *reduced* file. So this commit **reconciles** the test (not `git rm`): dropped the `TestGetMediaDuration` + `TestSupportsHardwareH264Encoding`(+`IndexError`) classes and their two imports (−10 tests), kept the surviving-fn coverage. Both files brought to jad via `git checkout joint-alignment-dp -- …` → **`git diff joint-alignment-dp` empty for both**. **Bug-fix-first: no bug — pure dead-code/test reconciliation, no Review-fix.** Cross-grep confirmed zero remaining importers of the three helpers in `pikaraoke/` or `tests/` (besides the test classes removed here). `import pikaraoke.app` OK; **689 unit pass** (699 − 10 helper tests); pre-commit clean. **Verify (at tip):** app boots; pitch/transpose controls still detect ffmpeg support. |
| C19 | 🔨 2026-06-05 | `d4e2f6c` | **Phase D begins — pipeline scaffolding.** Five new wholly-C19-owned files brought to jad end-state via `git checkout joint-alignment-dp -- …` (**`git diff joint-alignment-dp` empty** for all five): `pipeline/{__init__,config,context}.py`, `pipeline/stages/{__init__,base}.py`. `config.py` = `PipelineConfig` + nested `WhisperModelConfig` sections (load_model/align/transcribe/refine/2×post-process), loudnorm targets, ASS styling, ffmpeg/karaoke-timing knobs, and the **matcher knobs at corpus-tuned end-state** (`joint_alpha=2.0` from the 27-song α-sweep — *not* the 4.0 design prior — and `joint_margin_s=0.3`; inert data until the joint route consumes them at **C26A**, per Fix-absorption: "corpus-tune α=2" is absorbed into this final value, never a later config bump). `context.py` = `Phase` enum, `CancelToken` (`activity()` contextmanager + cancel-before/during ordering invariant), `Cancellable` protocol (`KillProcess`/`SetEvent`), `PipelineCancelled`, `StageContext`. `base.py` = `PipelineStage` protocol + `BaseStage`. Ownership map confirms only `lyric_align.py` splits across Phase D commits — config/context/base are single-commit-owned, so end-state is correct here; later refs are read-only (C27 reads `context`, C28 reads `config` tuning — neither re-touches these files). **No bug, no Review-fix — pure additive scaffolding** (stdlib-only `config`; `context` imports `config`; `base` imports `context`; no stage/worker/orchestrator imports, no runtime path). **New `test_pipeline_config.py` (18 tests, written fresh — jad has no pipeline-config test):** pins the corpus-tuned defaults (incl. `joint_alpha`/`joint_margin_s`) + the `default_factory` per-instance isolation, and exercises the `CancelToken` cancellation contract every stage relies on (cancel-before-activity, cancel-during + synthesised raise on clean exit, body-exception-not-masked, target.cancel signalled, on_phase_change callback). Pure-Python, no GPU/subprocess. **707 unit pass** (689 + 18); `import pikaraoke.app` + pipeline modules OK; pre-commit clean. **/code-review (retroactive gate-closure 2026-06-05) — no real bugs** (traced `CancelToken.activity()`'s cancel-synthesis + `cancel()` ordering/lock discipline, `KillProcess`/`SetEvent`, the `field(default_factory=)` defaults, and config's str-typed argv values). **C26A/C27 watch (not a C19 defect):** `activity()`'s exit check uses `sys.exc_info()[0] is None` to mean "the body didn't raise" — correct only because every current call site (`_ffmpeg_helpers`, `stem_separation`) opens it from a clean stack, never inside an `except`. If a later stage (lyric-align at **C26A**) ever opens `activity()` from within an `except` block, a genuine mid-activity cancel would be silently swallowed — confirm new call sites enter clean, or harden to a local `raised` flag (`try: yield; except BaseException: raised = True; raise; … if self.cancelled and not raised:`). **Verify:** none (no user-facing behavior; the joint route is exercised at C26A/C-PROC). |
| C20 | 🔨 2026-06-05 | `6f92ffe` | **ffmpeg stages.** Five new wholly-C20-owned files brought to jad end-state (**`git diff joint-alignment-dp` empty** for all five): `stages/_ffmpeg_helpers.py` (`run_ffmpeg()` — spawns ffmpeg under a `CancelToken.activity()`/`KillProcess` scope, routes stdout/stderr to the optional `pty_slave_fd`, raises `PipelineCancelled` on cancel / `RuntimeError` on non-zero exit, decodes captured stderr), `ffmpeg_extract.py` (video→44.1k s16 stereo WAV), `ffmpeg_transcode.py` (vocal/instrumental WAV→M4A, tmp-then-move so a cancel leaves no orphans), `loudnorm_analyze.py` (loudnorm 1st-pass; backward stderr walk for the last balanced JSON block + measurement artifacts), `load_vocal.py` (decode cached vocal m4a→WAV for backfill). Intra-pipeline + stdlib only; no runtime path yet (orchestrator wiring at **C27**). **DEVIATION from jad (Black, behavior-identical):** Black split the `"-loglevel", "warning"` arg pair onto two lines in `ffmpeg_extract`+`ffmpeg_transcode` (jad's files weren't Black-clean there) — the only diff vs jad. **New `test_pipeline_ffmpeg_stages.py` (14 tests, mocked subprocess; jad has none):** `run_ffmpeg` success/DEVNULL, non-zero→RuntimeError, capture-decode w/ replacement, pty-fd routing, pre-cancelled→raise-before-wait; loudnorm JSON walker (trailing block, last-of-multiple, none-without-brace) + artifact population + missing-wav/missing-field guards; transcode/load-vocal guard raises + stage names. **721 unit pass** (707 + 14); import smoke + `import pikaraoke.app` OK; pre-commit clean. **/code-review (retroactive gate-closure 2026-06-05) — no real bugs** (traced `run_ffmpeg`'s pty/capture/cancel branch matrix incl. the normal-cancel SIGKILL→reaped-by-`wait()`→activity-re-raise path, the loudnorm JSON-from-stderr walker + field validation, the command builders/guards, and the producer→consumer artifact-key contract). **Two C27 watch items (not C20 defects — no runtime path until the orchestrator drives cancel concurrency):** (1) **orphan-ffmpeg window** — a cancel landing between `Popen()` and `activity().__enter__` raises `PipelineCancelled` without SIGKILLing the just-spawned proc (it isn't registered as the cancel target yet), leaving a brief orphaned ffmpeg that finishes into the doomed per-job `tmp_dir`; when C27 wires cancel, kill `proc` on a pre-registration cancel (e.g. `try`/`except PipelineCancelled` around the activity that kills the proc); (2) **JSON-walker fragility** — `_extract_json_from_stderr`'s "last line ending in `}`" heuristic would grab trailing junk if any post-JSON log line ended in `}`; safe today because loudnorm runs `-f null -` with no `-stats` (the stats JSON prints last), but a brace-counting scan is strictly more robust if that command ever changes. (Field extraction not catching `TypeError` for a `null`/list value is impossible-state — loudnorm always emits quoted strings — left per [CLAUDE.md](../CLAUDE.md).) **Verify:** none here (processed-audio normalization exercised at **C-PROC**). |
| C21 | 🔨 2026-06-05 | `8e406fd` | **Stem-separation worker (out-of-process).** Four new wholly-C21-owned files brought to jad end-state (**`git diff joint-alignment-dp` empty**, modulo the two divergence notes below): `workers/{__init__,_ipc}.py`, `workers/stem_worker.py` (597 ln), `stages/stem_separation.py`. Melband-Roformer runs in a persistent **spawn**'d subprocess (model loaded once). Absorbs the robustness fixes that motivated the out-of-process move: **OOM-exit + auto-restart** (OOM mid-demix leaves audio-separator/CUDA-allocator unsafe → worker sends `("error",…)` and exits; next `separate()` sees the dead proc and restarts with a fresh CUDA context — the OOM job itself still fails); **per-chunk cancel hook** (a `register_forward_pre_hook` on `model_run` polls a cancel Pipe between demix chunks and raises `_CancelledInsideDemix`, unwinding to the worker loop without killing/reloading — weights are GPU attrs, not stack locals; **re-raises even when audio-separator swallows the exception and returns `[]`**, so a cancel never masquerades as a stem-ID failure); **spawn-only IPC** (`_ipc.py` — fork-after-CUDA duplicates a broken CUDA context, so a dedicated `WORKER_CONTEXT = mp.get_context("spawn")`; shared `forward_cancel`/`drain_pipe`). `StemSeparationStage` is a thin adapter (orchestrator-injected worker, `separate()` wrapped in a `CancelToken.activity(STEM_SEPARATION, SetEvent)` scope) translating `WorkerCancelledError`→`PipelineCancelled` / `WorkerDiedError`→`RuntimeError` (no-cancel path treats a stray cancel as a bug). `whisper_worker.py` is **C22**, not pulled here. No runtime path yet (worker constructed at **C27**). **/code-review (2 convergent agents) — no real bugs** (traced the cancel-token state machine, OOM-exit/auto-restart, the forward-pre-hook incl. swallowed-cancel re-raise, the stage translation matrix). **Bug-fix-first: one finding folded** — jad's `self._process: Process | None` referenced an *unimported* `Process` in an unevaluated annotation; fixed to `BaseProcess | None` (a spawn-context Process is a `SpawnProcess`/`BaseProcess`, not a `multiprocessing.Process`). **C27 watch (review note, not acted on):** `config.separator_model_name` (`vocals_mel_band_roformer.ckpt`) ≠ worker `DEFAULT_MODEL_NAME` (`mel_band_roformer_karaoke_aufr33_viperx…`); inert until the orchestrator wires config→worker — confirm the canonical model then. **Two divergences vs jad (both behavior-identical):** isort collapsed a double blank line in `_ipc.py` (jad wasn't isort-clean there); and the `BaseProcess` annotation fix above. **New `test_pipeline_stem_worker.py` (25 tests, mocked subprocess + real in-process Pipes; jad has none):** `_ipc` (spawn-context, `forward_cancel` send + broken-pipe-swallow, `drain_pipe`); `separate()` state machine (`ok`/`cancelled`/`error` tag dispatch, no-process→died, **dead-subprocess auto-restart**, death-mid-wait→died, cancel-event path completes); cancel hook (pending-signal→raise, **swallowed-cancel re-raise**, clean-run stem-ID + hook removal); stem-ID heuristic (vocals/instrumental, `(Other)`→instrumental, unidentifiable→raise); stage matrix (missing-wav guard, no-cancel happy/died/cancelled, cancel-token happy passes `token.event`/cancelled→`PipelineCancelled`(phase)/died→RuntimeError). **746 unit pass** (721 + 25); `-k stem` = 47 pass; import smoke + `StemWorker()` construct OK; pre-commit clean. **Verify:** none here ((at C-PROC) a processed song yields vocal+instrumental stems; cancel mid-run leaves no zombie). |
| C22 | 🔨 2026-06-05 | `a8bf796` | **Whisper alignment worker (out-of-process) + alignment-capture joint fields.** Three new wholly-C22-owned files brought to jad end-state (**`git diff joint-alignment-dp` = exactly the one Review-fix docstring line below — pre-commit clean, nothing else reformatted**): `workers/whisper_worker.py` (1203 ln), `lib/alignment_capture.py` (136 ln), and **ported jad's `tests/unit/test_whisper_worker.py` (712 ln, 33 tests) as-is** — unlike C19–C21, jad ships this suite. faster-whisper transcription/alignment runs in a persistent **spawn**'d subprocess mirroring the stem worker (model loaded once; **clears the GPU cache after every job**, not just on cancel — so a wedged/OOM'd CUDA context can't accumulate across songs); shares the cancel-Pipe `forward_cancel`/`drain_pipe` plumbing + `WorkerDiedError` contract via `_ipc`. **`refine` kwarg:** `transcribe_words` (and inner `_do_transcribe_words`) gain keyword-only `refine: bool = True`; `refine=False` skips the refine pass and logs "Skipping refine pass". To stay IPC-back-compat **without a protocol-version flag**, the worker dispatcher unpacks `("transcribe_words", path, *rest)` so the legacy **2-tuple** (refine on) and the new **3-tuple** both run — only the joint route (**C26A**) sends refine off. **`alignment_capture.build_bundle`** gains optional `joint_stats` / `transcribe_words` kwargs; **schema stays v4** (additions, not renames) and they're populated only on joint runs, wired in by the lyric-align stage at **C26A**. No runtime path yet (worker constructed at **C27**). **Ported test suite (33 tests, mocked subprocess + real in-process Pipes):** ready-block/auto-restart/tag-dispatch state machine, cancel forwarding, is-alive, stop/kill, `_extract_words`/`_segments_to_line_objects`/`_extract_align_failure_ratio`, and the facade methods — incl. **`transcribe_words` defaults to refine=True and threads refine=False through to the 3-tuple request**. **779 unit pass** (746 + 33); pre-commit clean. **/code-review (2 convergent agents) — no real bugs** (traced the `_run_job` auto-restart/death-mid-wait state machine, the encoder forward-pre-hook cancel incl. clean unwind across multi-pass jobs — no cancel lost between transcribe/refine since drains are job-boundary-only — GPU-cache clear on every path, the `align_check`→`refine_from_cached` single-entry cache protocol incl. stale-`result_id`→error, and the `refine` 2/3-tuple back-compat). **Two findings left as not-a-bug:** the `forward_cancel` daemon thread parks until cancel (one Thread + retained Event/Connection per completed job) — but that's **C21's documented `_ipc` design** (`stem_worker` calls out the "leaked cancel-forwarder daemon thread"; drained at job boundaries), owned by C21 not C22; and the OOM-handler's `vocal_path` read can't fire on the non-binding branches (`discard_cached`/unknown do no GPU work) — a defensive default there would be error-handling for an impossible state ([CLAUDE.md](../CLAUDE.md)). **One Review-fix folded (bug-fix-first; the sole jad divergence, behavior-identical):** `align_check`'s `Raises:` referenced **`align_refine`**, a method that no longer exists (split into `align_check` + `refine_from_cached`); retargeted the dangling cross-reference (the `_do_refine_from_cached` "old align_refine path" comment is hedged-historical, left as-is). **Verify:** none here ((at C-PROC) GPU memory returns to baseline between runs; a legacy 2-tuple `transcribe_words` still runs with refine on). |
| C23 | 🔨 2026-06-08 | `956d79f` | **Genius lyrics integration.** Four new wholly-C23-owned files brought to jad end-state then diverged by two Review-fixes (below): `lib/genius.py` (`GeniusClient` — thread-safe `lyricsgenius.Genius` wrapper behind a `threading.Lock`; always-constructed, empty-token→`search()`=\[\]/`fetch_lyrics()` raises `GeniusUnavailable` so callers never check `None`; `search()` shows all artists via `artist_names` + query-aware blocked-term filter; raises only the `lyricsgenius` logger to WARNING to kill INFO "Done." noise; module-level atomic-JSON sidecar I/O `choices_dir`/`write_choice`/`read_choice`/`delete_choice`), `lib/genius_lyrics.py` (`parse_lyric_lines` keeps paren *contents* in `align_text` but brackets in display `text`; `normalize_lyric_line`/`clean_srt_line` shared txt/SRT cleaners — SRT additionally drops `(stage-direction)` parens; `clean_genius_query` light query cleaner) + the two test files. No runtime path yet (consumed by lyric stages at **C26/C26A**). **/code-review (2 convergent agents) — 3 genuine findings, all surfaced as bug-vs-design judgment calls; user adjudicated.** **Two Review-fixes folded (DEVIATIONS — bug-fix-first):** (1) `search()`'s result-parsing loop ran *outside* the network `try/except`, so a malformed-but-truthy response (null section `{"sections":[None]}`, null `primary_artist`, or a song hit missing `id`/`title`) escaped as an unhandled `KeyError`/`AttributeError`, breaking the documented "\[\] on any failure" contract — wrapped the loop in `except (KeyError, AttributeError, TypeError)`→log+`[]` (+3-payload regression test); (2) `_HAS_LETTER_RE` was ASCII-only `[A-Za-z]`, so `parse_lyric_lines`/`clean_srt_line` silently dropped every non-Latin (CJK/Cyrillic/Greek/accented) lyric line as letter-less — widened to any Unicode letter `[^\W\d_]` (digit/punct-only still dropped; +2 regression tests). **One not-a-bug (user-confirmed):** `clean_genius_query` reuses `metadata_parser.NOISE_PATTERN`, which strips generic title words (`by`/`live`/`hd` → "Stand By Me"→"Stand Me") — deliberate YT-noise targeting + Genius fuzzy search, left as jad designed. **Third divergence (behavior-identical):** Black collapsed the `_CURLY_QUOTES_TABLE` `str.maketrans` literal onto one line (jad wasn't Black-clean). So `genius.py`/`genius_lyrics.py` will **not** equal jad at the tip — see Standing deviations. 62 ported-shape + 3 regression = 65 genius tests; **844 unit pass**; `import pikaraoke.app` + both modules OK; pre-commit clean. **Verify (deferred to C-PROC):** with a token set, search returns multiple artists and logs aren't spammed with "Done."; a Genius `(I can't help) Falling in love` aligns with parens kept, an SRT `(gentle music)` line is dropped. |
| C24 | 🔨 2026-06-08 | `f023895` | **Two-pointer walk word matcher.** Two new wholly-C24-owned files brought to jad end-state (**`git diff joint-alignment-dp` empty for both — == jad at tip**): `lib/word_alignment.py` (543 ln) + ported-shape `tests/unit/test_word_alignment.py` (30 tests). `match_words_to_lines`/`match_words_to_lines_with_stats` align fetched lyric tokens to whisper words via a lockstep two-pointer walk — **no DP table, no fuzzy scoring** (stable-ts emits words in reference order). Biases: asymmetric lookahead (lyric=3/whisper=10), confirmed re-sync (reject an anchor unless the next `confirm_matches-1` pairs also match), whisper-skip budget (absorb noisy whisper runs). Unmatched lyric runs interpolate linearly between matched anchors; runs longer than `max_interp_run` or below `min_interp_slot` are dropped (lyrics absent from audio); collapsed matched runs (stable-ts pinning a section to one instant) are demoted so the interp/drop logic applies. `_with_stats` returns per-run telemetry (matched/collapsed/dropped/interp run-lengths, mapping, empty-line reasons) for the offline knob-tuner (`alignment_capture`, later). **No diarization** — audit found zero `diariz`/`speaker` refs in the module or any `next` caller (the lone `genius_lyrics.py:17` hit *documents* removal; `whisper_worker.py:14` is a docstring pointer now resolvable). No runtime path yet (consumed by `lyric_align.py` at **C26**). **/code-review (2 convergent agents) — 0 Review-fixes.** Agent-1 line-scan + Python-pitfall (≈28k fuzz trials): clean — verified walk termination, `confirm_matches=1`→empty-`range` degradation, the `run_len>0` division guard (always true inside run branches), `token_words[k-1]` never-None, loop-var reuse safe. Agent-2 raised 8 candidates, **all adjudicated not-a-bug / out-of-scope / faithful-to-tip:** (a) demote→**interpolate** under custom knobs (`max_collapsed_run<max_interp_run`) — the inline + `max_collapsed_run` param docstrings already say "interp/drop", and spreading a *short* demoted run over real time is correct, not phantom-animation (only the module header is loosely worded); (b/c) `whisper_consumed`/`matched_count` naming + pre-vs-post-demote — internally reconciled by the log's demote count (matched+demoted=raw) and consumed as-is by jad's own `alignment_capture` knob-tuner (renaming would desync the consumer); (d) early-return `start=0.0` vs normal-empty `start=None` — **refuted at the tip**: jad's ASS generator gates `if not words: continue` (lyric_align.py:448) and the SRT generator filters `if line_obj["words"]` (line 499), so `start` is never read for empty-words lines → zero behavioral divergence; (e) cross-line non-monotonic output on out-of-order whisper timestamps — a *new* feature beyond jad's end-state under near-impossible (stable-ts monotonic) input; (f/g/h) the matching test gaps ride those non-bugs — the stats contract is tested via its consumer in jad, so the faithful pull is correct. **874 unit pass** (844 + 30); `import pikaraoke.lib.word_alignment` OK; pre-commit clean. **Subject corrected NW→walk** (historical "Needleman–Wunsch" label superseded before the jad tip — end-state is the walk matcher; recorded in the commit body, not a code deviation). **Verify (deferred to C-PROC):** unit-covered; exercised when the lyric-align stage drives it. |
| C25 | 🔨 2026-06-08 | `f1370e8` | **Tiling matcher (order-independent).** Two new wholly-C25-owned files brought to jad end-state (**`git diff --cached joint-alignment-dp` empty for both — == jad at tip**): `lib/tiling_match.py` (593 ln) + ported-shape `tests/unit/test_tiling_match.py` (33 tests). Alternative to C24's walk matcher: instead of trusting reference order, it finds every fuzzy occurrence of each lyric line in the whisper token stream and picks the best non-overlapping tiling — resilient to remixes / live re-orderings / repeated choruses, at the cost of silently dropping unfindable lines. **Two phases:** `find_candidates` (sliding-window word-level Levenshtein scan; `max_edit_ratio` gate + `min(2,n)` overlap floor; **raw matched-token score `n−dist`** not a ratio, so the DP maximizes total coverage and short paren-units can't tie long lines on ratio) → `best_tiling` (weighted interval-scheduling DP via `bisect_right`, O(m log m)). `find_anchor_candidates` is a relaxed **contiguous-anchor-run** re-scan (`min_run = max(3, n//3)`) restricted to zero-candidate units. Lyric lines split into **match units** on *substantial* parens (≥3 tokens — backing vocals whisper transcribes as their own run); ad-lib parens (`(Oh)`/`(Yeah)`) stay inline; short-main-after-split abandons the split. `_build_line_object` reuses C24 `_walk_align` *within* the selected window (`confirm_matches=1`/`whisper_skip_budget=1` to neutralize whole-song biases) + interpolates unmatched runs. `_with_stats` returns per-pass telemetry (per-unit candidate counts/best score, zero-candidate + anchor-recovered unit ids, selected windows) for the offline knob-tuner. Imports only C24 `_normalize_token`/`_walk_align` + stdlib (`re`/`bisect`); no runtime path yet (consumed by `lyric_align.py` at **C26**; the DP/candidate machinery is reused by the joint matcher at **C26A**). **Cleanup-feature touchpoint rides along:** the reworded `match_words_to_lines_tiling_with_stats` paren-split docstring (matches C23's "keep paren contents" change) is part of the whole-file end-state — no separate handling. **/code-review (2 convergent agents) — 0 Review-fixes.** Agent-1 line-scan + numeric (100k fuzz vs reference `_edit_distance`/`_longest_contiguous_run`; **50k brute-force vs `best_tiling` incl. shared-endpoint intervals** → optimal + non-overlapping): clean — verified the window `break`-on-monotonic-size, `range(T−w+1)` bounds, the bisect/`dp[j+1]`/backtrack, all None-run interpolation fills (`tw[0]`/`tw[-1]` safe), the `substantial_set` membership + short-main fallback. Agent-2's 7 candidates **all adjudicated not-a-bug / faithful-to-tip:** (a) cross-pass score scale — anchor run-length vs main `n−dist` are the *same* token-count scale, the DP's coverage-maximization deliberately prefers more matched tokens, and anchor candidates only exist for zero-main-candidate units (a last-resort recovery); the docstring's "never beat the *same* line" is a per-line claim, accurate as written — intended heuristic, "fixing" it = design change beyond jad; (b) `del align_lines` is documented API-parity (`align_lines` is only the bracket-stripped form of `lines`, never diverges in word content); (c–g) anchor-integration / within-window-interp / clamp / stats-dict / identical-paren-content are coverage gaps on jad's faithful test file, with the underlying paths verified-correct (stats tested via its consumer in jad). **907 unit pass** (874 + 33); `import pikaraoke.lib.tiling_match` OK; pre-commit clean. **Verify (deferred to C-PROC):** unit-covered; exercised when the lyric-align tiling/joint route drives it. |
| C26 | 🔨 2026-06-08 | `7238bd9` | **Lyric-fetch + lyric-align stages — first multi-concern file split of the phase.** Five new files: `stages/lyrics_fetch.py` (`LyricsFetchStage` — per-job lyric-source resolution: explicit Genius selection→fetch+write `lyrics.txt`, raw/force-transcribe, explicit YouTube-SRT, or SRT-fallback discovery; Genius failures surface before audio work and **don't delete the choice file** so re-runs retry), `stages/lyric_align.py` (`LyricAlignStage` — aligns lyrics→vocal stem → karaoke ASS+SRT; walk/auto/tiling match with auto-escalation to tiling on **fail-ratio OR collapse-ratio** gates; `_load_lyrics` cleans SRT noise via `clean_srt_line`+drops letter-less, TXT keeps inline-paren contents in `align_lines`; tmp-then-move output so cancel leaves no orphans), + `test_lyric_align.py` (16), `test_lyrics_fetch.py` (21), `test_lyric_conversion.py` (16). **Split mechanics:** `lyric_align.py` restored whole from jad then the **9 opt-in-`joint` pieces surgically removed** (import, `use_joint` branch, `_run_joint`, the `capture_joint_stats`/`capture_transcribe_words` locals + `joint_stats`/`transcribe_words` params threaded through `_write_debug_capture`→`build_bundle`, `joint_alpha` in `pipeline_decisions`); `test_lyric_align.py` truncated to drop `TestJointRoute` (3 tests). **The C26→jad delta is exactly those joint pieces** (+ the necessary `elif not use_tiling:`→`if not use_tiling:`), verified by `git diff --no-index` vs jad's blob, so **C26A re-adds them verbatim**. `joint_match.py` correctly absent. **/code-review (2 convergent agents) — 0 Review-fixes.** Agent-1 (bug-hunt): every `self._config.X`/`cfg.X` is a real `PipelineConfig` field, all 11 `build_bundle` kwargs match the dep signature, ASS Style=23-field / Dialogue=10-field + non-negative `\k`/`\kf` durations + `_seconds_to_ass_time` no cs-rollover, `line_objects`/`write_srt` bound before use on every path, `_find_youtube_srt_path`↔`_find_srt` discovery order identical, lyrics_fetch branches a/b/b2/c + the `is not None` override + GeniusUnavailable-no-delete — clean (two impossible-input items left per CLAUDE.md: `int(genius_id)` on a malformed sidecar, `srt.parse` on a corrupt SRT — controlled internal inputs). Agent-2 (split-integrity): no dangling joint refs (ruff F clean), `line_objects` bound for auto/walk/tiling/joint/transcribe + transcription-mode paths, `build_bundle` joint params default `None` so the call is valid, **interim `match_method="joint"` empirically run → no crash, valid ASS, `lyric_method="none+walk"`** (benign fall-through to walk; "joint" not exposed until C26A/C47), test truncation clean (`_make_stage_and_ctx` still consumed by `TestMatchMethodEscalation`). **960 unit pass** (907 + 53); pre-commit clean. **2 files diverge from jad by formatting only** — isort/black reflowed `lyrics_fetch.py` + `test_lyrics_fetch.py` (jad wasn't lint-clean under next's 100-char config); `lyric_align.py`/`test_lyric_align.py`/`test_lyric_conversion.py` == jad-minus-joint. **Commit body trimmed:** the spec's "default subtitle delay" isn't in these files (no `delay` ref) — omitted. **Verify (deferred to C-PROC):** a processed song plays time-synced subtitles; an SRT source with `♪`/wraps/`(stage direction)` yields clean subtitle lines. |
| C26A | 🔨 2026-06-08 | `702259f` | **Joint alignment DP matcher + opt-in stage route — the other half of the C26 split.** New `lib/joint_match.py` (679 ln) + ported `tests/unit/test_joint_match.py` (35 tests); the joint route re-added to `stages/lyric_align.py` (import + `use_joint` branch + `_run_joint` + capture-joint plumbing: `capture_joint_stats`/`capture_transcribe_words` locals, `joint_stats`/`transcribe_words` threaded to `build_bundle`, `joint_alpha` in `pipeline_decisions`) + `TestJointRoute` (3 tests) re-added to `test_lyric_align.py`. **`lyric_align.py`/`test_lyric_align.py` now == jad tip exactly** — the C26→C26A delta is precisely the joint pieces C26 removed (verified: 1 line `if not use_tiling:`→`elif`, 82 lines added back). The matcher: per lyric line build 1 **align candidate** (at forced-alignment's predicted span, `align_agreement=1.0`, `transcribe_match` = how well transcribe corroborates) + 0..n **transcribe candidates** (reuse C25 `find_candidates`/`find_anchor_candidates`, `align_agreement` = time-overlap with align's window); score `transcribe_match + α·align_agreement·alpha_weight`; `_best_tiling_by_time` (O(M²) weighted-interval DP, sorted `(line_id,t0)`) picks the max-score subset that is **both monotonic-by-line_id and time-non-overlapping**; per-word timings from the winning source (align's refined words when align wins → clean-song precision preserved); unplaced lines soft-dropped with a bracketed interp span (1:1 output). `match_method=="joint"` runs align_check→refine→transcribe(**refine=False**, C22 kwarg)→matcher with `joint_alpha`/`joint_margin_s` (C19); opt-in, default stays `auto`. **Ships the 2 historical `fix(joint-match)` commits absorbed in-place (no replay):** (1) **lyric-id-monotonic DP** — the `cj["line_id"]>=ci["line_id"]: continue` guard + `(line_id,t0)` sort stop a chorus repeat / dialogue interlude from placing a later lyric at an earlier time (the Hakuna Matata failure); (2) **`_alpha_weight` binary gate on raw lexical set-intersection** (≥`_ALPHA_GATE_COUNT=2` words heard AND none are the lyric's → zero the α-bonus), not the edit-distance `find_candidates` score (which over-rejected mistranscribed-but-correct lines); (3) **`_transcribe_match_and_count_in_window` uses `bisect_left`** on both window bounds (was `bisect_right-1`, over-included a word starting before the window). **/code-review (2 convergent agents).** Agent-2 **differential brute-force fuzz: 220k trials (130k non-negative + 90k negative-allowed, multi-seed) → 0 score mismatches, 0 constraint violations** vs an exhaustive-subset reference — `_best_tiling_by_time` is score-optimal on its domain; the lone divergence (all-negative scores → DP returns least-negative single vs empty-set's 0) is **unreachable** since every score is a sum of non-negative terms (`transcribe_match≥0`, `α>0`, `align_agreement∈[0,1]`, `alpha_weight∈{0,1}`); end-to-end API sanity (clean→align wins w/ exact align timings, wrong-audio line→transcribe re-places it, empty transcribe→no crash, output 1:1+sorted) all held. Agent-1 verified all 3 absorbed fixes CORRECT (adversarial line_id-vs-time-disagreement case rejected; transitive pairwise non-overlap; `end_idx` exclusive so `[end_idx-1].end` right; `zip(toks,aw)` length-safe by construction; no div-by-zero — `a_dur<=0` short-circuits). **1 Review-fix folded (bug-fix-first; the sole jad divergence, behavior-identical):** `_interpolate_missing`'s docstring claimed interp lines get "per-word timings equally spaced" + a `source:"absent"` no-token path — the code emits `{"words":[],"text":"","source":"interp"}` for **every** missing line (a silent soft-drop skipped by the ASS/SRT `if not words` gates), so the docstring was wrong on both counts; rewrote it to describe the actual soft-drop. **Three findings surfaced as not-a-bug / design calls, left as jad's corpus-validated form:** (a) the soft-drop discards an unplaceable line's **text+words entirely** so it never renders (walk/tiling gap-fill so every token shows) — intended per `plans/joint-alignment-dp.md`; the opt-in joint matcher trades coverage for placement confidence; (b) the DP's strict-`>` tie-break drops zero-score-but-conflict-free candidates — **score-optimal** (the 220k fuzz confirms total-score parity with brute force; these are exactly the α-gated wrong-audio lines); (c) the `absent` source path is dead (`absent_line_ids` always `[]`) but the key is part of the capture-bundle schema consumed by the offline knob-tuner — same class as C24's telemetry-shape call, left intact. **998 unit pass** (960 + 35 + 3); `import pikaraoke.lib.joint_match` OK; pre-commit clean. `joint_match.py` == jad **minus the docstring fix**; the 3 other files == jad tip. **Verify:** `pytest tests/unit/test_joint_match.py` green in isolation ✅ (matcher needs no stage); **(at C-PROC)** processing with `--match-method joint` (C47) places lines — clean songs keep align timings, a misplaced long line routes to transcribe. |
| C27 | 🔨 2026-06-08 | `48ada56` | **Stage orchestrator — Phase D's integration seam.** New `pipeline/orchestrator.py` (`PipelineOrchestrator`, 226 ln) + **new** `tests/unit/test_orchestrator.py` (25 tests — jad leaves this seam untested). Owns both worker lifecycles (eager idempotent `start()`/`stop()`; `stop()` swallows+logs per-worker teardown errors), creates+`rmtree`s the per-job tmp_dir under a `finally`, runs stages sequentially with a between-stage `check_cancelled()`, exposes phase to an injected `on_stage_change` callback. Sync (`run`/`run_one`) + async (`run_one_async`→bg thread; `join` re-raises the caught exception; `cancel_active`); **each `run_one_async()` mints a FRESH `CancelToken`+`Event`** so a stale cancel-forwarder can't leak across songs. Workers are *injected* (built by the driver at C-PROC/C32), so the orchestrator never reads model-name config. **Manual 3-axis gate; the core /code-review ran clean on the build machine — this fold re-verified by the manual gate + targeted tests.** **2 Review-fixes folded (bug-fix-first):** (1) **leak-free worker start/stop** — `start()` sets `_workers_started` *before* spawning + `run()` moved `start()` inside its `try`, so a 2nd-worker (whisper) start failure (the GPU-OOM this eager start exists to surface) still lets `finally stop()` reap the stem worker that did start rather than leak it (`orchestrator.py` == jad **plus this fix** + 2 Black inline-comment-spacing fixes; jad wasn't Black-clean there); (2) **closed C20's earmarked orphan-ffmpeg watch** — C27 is the first code to drive `run_ffmpeg`'s cancel concurrently, making live the window where a cancel between `Popen()` and `activity().__enter__` (before `KillProcess` is the registered target) raised `PipelineCancelled` without SIGKILLing the just-spawned ffmpeg; wrapped the activity in `except PipelineCancelled: proc.kill(); proc.wait(); raise` so the orphan is reaped before it finishes into the about-to-be-`rmtree`d tmp_dir (no-op if the cancel mechanism already killed it in-body). `_ffmpeg_helpers.py` == jad **plus this fix**; the C20 `test_precancelled_token_*` test updated to assert the reap (kill+wait called, body never runs). **Other two C27 watches dispositioned (not C27 defects):** **config↔worker model-name mismatch** (`config.separator_model_name`=`vocals_mel_band_roformer.ckpt` ≠ worker `DEFAULT_MODEL_NAME`=`mel_band_roformer_karaoke_aufr33_…`) is **inert here** — the orchestrator takes pre-built workers and never wires model names; reconcile at the worker-construction site (**C-PROC/C32**). **loudnorm JSON-walker** unchanged + safe-today (loudnorm's `-f null -` has no `-stats`, so its JSON prints last); brace-counting hardening still deferred, not a bug. The **C19 `activity()` `sys.exc_info` watch is not triggered** — the orchestrator opens no `activity()` (stages do, from clean stacks) and the new `except` re-raises without opening one. **1023 unit pass** (998 + 25); `import pikaraoke.pipeline.orchestrator` OK; pre-commit clean. **Verify (deferred to C-PROC):** a queued song runs extract→stems→whisper→align end-to-end; cancel mid-stage tears down cleanly with no zombie ffmpeg/worker. |
| C30 | 🔨 2026-06-08 | `0120d7e` | **PTY process terminal — pulled BEFORE C28 (forward-dep fix).** `lib/process_terminal.py` (284 ln) + `lib/process_terminal_reader.py` (64 ln), both **byte-identical to jad** (`git diff joint-alignment-dp` empty). **Reordered ahead of C28** because C28's `processing_manager.py` imports `ProcessTerminal` at module top-level (and its test imports the module), so C28 can't collect green without it; these two files are standalone (stdlib + `get_platform` only; the reader is launched as a `python -m` subprocess by module-string, never imported), so landing them first is clean and keeps each commit's tree green. `ProcessTerminal` opens a PTY pair, drains the master fd on a daemon relay thread → forwards bytes to a Unix-socket client (64 KB pre-connect buffer so the worker never blocks before the terminal attaches), spawns a terminal emulator running the reader; `get_slave_fd`/`get_slave_path` feed workers; Windows = logged no-op. **New** focused `tests/unit/test_process_terminal.py` (7 tests — jad has none): terminal-emulator discovery (Pi/macOS/generic candidate order via mocked `shutil.which`), Windows-noop `start()`, pre-start accessors, reader usage-guard. **Manual 3-axis gate + 2-agent /code-review:** test-agent clean (patch targets non-vacuous; no real PTY/socket/subprocess side effects); source-agent surfaced **5 findings, all pre-existing verbatim-jad runtime/concurrency paths not unit-testable here** — **3 DEFERRED to C-PROC** (only the live PTY makes them verifiable; a fix written now is unverifiable until then): (1) `_relay_loop` bind/listen unguarded → if the socket path is in-use (a 2nd instance sharing the data dir), the daemon relay dies silently and the undrained PTY master blocks a worker writing >64 KB **forever**; (2) `_server_socket` assigned before `bind` → fd leak on a `start()` retry past that failure; (3) `stop()` closes+nulls `_master_fd` while the relay may still `select([_master_fd])` → `TypeError`/closed-fd read if the 3 s join times out — **plus 2 not-a-bug** (check-then-act `_server_socket` race is benign, double-close swallowed; fast-finish worker dropping buffered output before the retrying reader connects is cosmetic). **1030 unit pass** (1023 + 7); `import pikaraoke.lib.process_terminal{,_reader}` OK; pre-commit clean. **Verify (at C-PROC):** live subprocess output streams into the processing-page terminal; the 3 deferred relay/shutdown findings were re-audited reachable + **fixed in this commit 2026-06-14 (deferred-fix fold, bug-fix-first; fold `2ef99c7`):** (1) `_relay_loop` `bind`/`listen` guarded — on failure the loop still drains the PTY master (runs clientless) so a worker writing >64KB can't block forever; (2) `self._server_socket` assigned only after a successful bind (loop uses a local `server` ref), failed setup closes the half-open fd; (3) `select([_master_fd])` guarded to break cleanly if `stop()` closes the fd under it. +2 `TestRelayLoopGuards` tests; 3-axis gate + 1-agent /code-review clean. |
| C28 | 🔨 2026-06-08 | `8d229dd` | **ProcessingManager job queue — thin adapter over `PipelineOrchestrator`.** `lib/processing_manager.py` (now 466 ln) + jad's 42-test `tests/unit/test_processing_manager.py`. A daemon orchestrator-loop thread drains a `queue.Queue` of pending songs and runs each through the 5-stage pipeline (extract→loudnorm→stem→transcode→lyric_align via `run_one_async`+`join`), with phase-targeted cancellation; owns/spawns the C30 `ProcessTerminal` for its lifetime and routes pipeline-thread Python logs to it via a thread-name-gated `_PtyHandler`/`_PipelineThreadFilter` (`PIPELINE_THREAD_PREFIX`), lifecycle records echoed to both terminals. Public API (`enqueue`/`cancel_pending`/`cancel_active`/`get_active_job`/`get_active_phase`/`start`/`stop`) preserved for the karaoke.py wiring at C-PROC. **Pulled from jad with 2 dead-code cleanups folded** (surfaced by the review, per CLAUDE.md delete-dead-code): dropped a redundant inner `import os` in `start()` (already module-level) and a dangling empty `# Helpers` divider at EOF → **`processing_manager.py` == jad minus those two; `test_processing_manager.py` == jad**. **Manual 3-axis gate + 2-agent /code-review:** test-agent — patch targets all correct (module-top names patched at `pikaraoke.lib.processing_manager.*`), no handler/thread leaks (the lone real-thread `start()` test forces `is_windows=True` so no PTY attaches and `stop()` joins it); source-agent surfaced **4 concurrency/lifecycle BUGs, all DEFERRED to C-PROC** — **none triggerable on `next` yet: ProcessingManager has no callers** (the Flask routes + `karaoke.py` that drive cancel/enqueue are the deferred C-PROC wiring), and a naive fix for #4 was **proven wrong** (it corrupts `pending_jobs` for the active job), so these need real `_run_loop` integration tests + live verification authored alongside the wiring: (1) `stop()` before `start()` → `AttributeError` on the never-assigned `self._orchestrator` (partial-init is defensive for `_process_terminal`/`_pty_log_handler` but not the orchestrator); (2) `cancel_active()` calls `orchestrator.cancel_active()` **outside** `_state_lock` → if the active token rotated to the next job in the validate→call window, the **next** job is cancelled (fix: hold the lock across validate+cancel — safe, `token.cancel()` takes no lock); (3) `_active` is set **after** `run_one_async()` already launched the pipeline thread → a cancel landing in that window is dropped as "non-active" (fix: set `_active` under the same lock hold as `run_one_async`); (4) `cancel_pending()` on a path that is actually **active** (not in `pending_jobs`) seeds `_cancelled_paths` permanently → a later re-enqueue of that path is silently discarded at dequeue. **Test-coverage gaps DEFERRED to C-PROC** (belong with the cancel-surface fixes): `_run_loop` is entirely untested (cancelled-skip, finally cleanup, stem-worker eager-restart), plus cancel-active end-to-end, blocked-words *allow* path, loudnorm float-conversion failure, `song_manager=None`+offset; and the vestigial `_ActiveJob.cancelling` field's test asserts a set-but-never-read flag (revisit/remove when C-PROC touches the cancel surface). **1072 unit pass** (1030 + 42); pre-commit clean (pylint accepts the file as-is). **Verify (at C-PROC):** queue two songs → processed one at a time; cancel-pending drops a queued song, cancel-active tears down the running one mid-stage; the 4 deferred races were re-audited under the live cancel route (`pipeline_tracker.cancel`->`cancel_active`/`cancel_pending`) and **#2/#3/#4 fixed in this commit 2026-06-14 (deferred-fix fold, bug-fix-first; fold `9f8df45`):** #2 `cancel_active()` fires `orchestrator.cancel_active()` **inside** `_state_lock` (active can't rotate onto the wrong job); #3 `run_one_async()` + the `_active` assignment share one `_state_lock` hold (no dropped-as-non-active window); #4 `cancel_pending()` seeds `_cancelled_paths` only when the path isn't active (no permanent leak / silent re-enqueue skip — the naive `pending_jobs`-gate avoided since an active job stays in `pending_jobs` until its `finally`). **#1 (`stop()`/`_orchestrator`) left — genuinely unreachable.** +5 tests; 3-axis gate + 1-agent /code-review clean (self-deadlock REFUTED — `run_one_async` fires no synchronous phase-change; `cancel()` takes the token's own lock, not `_state_lock`). |
| C29 | 🔨 2026-06-09 | `f9726b5` | **PipelineTracker — download/processing monitor.** New `lib/pipeline_tracker.py` (460 ln), the single source of per-song pipeline status for the processing page. `PipelineItem` carries download/processing status + phase + `lyric_method`; `PipelineTracker` subscribes to nine manager events (download_queued / song_downloaded / download_error / processing_complete / cancelled / error / skipped / song_deleted / pipeline_stage_changed) and **derives status lazily in `get_status()`** by reading live `ProcessingManager` (`get_active_job`/`get_active_phase`/`pending_jobs`) + `DownloadManager.active_url`, also computing each item's allowed `actions` server-side (auth in one place, not the client). `cancel`/`enqueue`/`remove` run file I/O (`song_manager.delete`) + `_notify_change` **outside** `_lock`. **No callers on `next` yet** (karaoke.py instantiation = C32, routes = C-PROC; coverage arrives via jad's `test_processing_routes.py` at C-PROC — jad ships **no dedicated tracker test**). **Integration touchpoints verified** against the built managers — all 8 reach-ins resolve (PM `get_active_job`/`get_active_phase`/`pending_jobs`/`cancel_pending`/`cancel_active`; DM `active_url`/`cancel_active_download`/`cancel_pending_download`) + `queue_manager.enqueue(log_action=)` + `song_manager.delete`; module imports clean. **Manual 3-axis gate + 1-agent source /code-review** (no test file to review): **1 BUG fixed (Review-fix folded), 3 DEFERRED to C-PROC, 2 not-a-bug.** **Review-fix:** three handlers (`_on_processing_complete`/`_on_processing_error`/`_on_processing_skipped`) fired `_notify_change()` **inside** `_lock` → the external `on_change` callback re-entering a lock-guarded method (e.g. `get_status` to build the push payload) self-deadlocks the emitting worker thread on the non-reentrant lock; **dedented all three** to the file's own dominant outside-lock idiom (zero behavior change; the other nine notify sites, incl. cancel/enqueue/remove, already defer via flags) → **`pipeline_tracker.py` == jad minus exactly these 3 dedents**. **Deferred to C-PROC** (need the live route/download wiring to be reachable): (a) `_on_song_downloaded` attaches a downloaded path to an item by 11-char id + `break` → two queue entries for the **same URL** leave the 2nd orphaned at `pending` forever (needs a dedup product call); (b) `enqueue()` guards only `song_path is not None`, not `processing_status=="complete"` → currently an **impossible state** (the `_item_to_dict` action-auth only surfaces the button when both stages complete — CLAUDE.md don't-guard-impossible-states), revisit when the route exists; (c) cancel-pending-on-active seeding `_cancelled_paths` is the **same root as C28 #4** (lives in ProcessingManager) — already tracked. **Not-a-bug:** `get_status` re-deriving to `complete` in an event-lag window is transient/self-correcting (one render; `not in (complete,error)` guards delivered terminal states); `_notify_change`'s `except Exception`→`debug` is intentional fire-and-forget (could bump to `warning` at C-PROC). **1072 unit pass** (unchanged — no new test file); pre-commit clean. **Verify (at C-PROC):** processing page shows live phase per song; cancel pending vs active; duplicate-URL submit behavior; deadlock-free push under the real `on_change`. |
| C32 | 🔨 2026-06-09 | `895bb19a` | **karaoke.py processing/pipeline/Genius wiring — second `e`-pass on the C18-shared import/signature/attr hunks.** `Karaoke.__init__` now: imports `GeniusClient`/`PipelineTracker`/`ProcessingManager` + `get_temp_directory`; declares the `pipeline_tracker` attr; adds `blocked_processing_words`/`genius_token`/`temp_dir` CLI-override params (forwarded via `_load_preferences`→`apply_all`); resolves `self.temp_dir = get_temp_directory(self.temp_dir)`; passes `events=` to SongManager + `temp_dir=` to DownloadManager; builds `GeniusClient(api_token=genius_token or "")` → `ProcessingManager(...).start()` (auto-processes on the `song_downloaded` event) → `PipelineTracker(...)` (`on_change` defaults None — UI push wired at C-PROC); `stop()` calls `processing_manager.stop()` before MPV quit. **No app.py work** — the `Karaoke(...)` call-site was already reconciled by the `18f1225` boot-fix; app.py's residual diff vs jad is all C-PROC (`processing_bp` reg + `_pipeline_changed`→`_on_change` push) + unrelated divergences. **Forward-deps clear:** the GeniusClient/ProcessingManager/PipelineTracker call args all match the built C23/C28/C29 constructors, and DownloadManager already accepts `temp_dir=` + SongManager `events=` (no TypeError; no use-before-assign — verified every `self.X` read at the wiring site is set earlier in `__init__`). **Residual karaoke.py vs jad = exactly the deferred set:** C35 (`_volume` property + `transpose_current`/`volume_change`/`restart` rewrites + `set_subtitle_delay`/`set_vocal_volume`/`set_sub_mode` + `reset`/`get_now_playing` subtitle+vocal fields) + C38 (`admin_password` param) + the 3 C18-carried deviations (dead try/except removal, Black-clean lambda parens, `log_and_send` danger `error` vs jad's `warning`). **conftest:** MockKaraoke gains `temp_dir` + a `processing_manager` MagicMock so the real bound `stop()` stays green; residual conftest vs jad = exactly C35 (4 `MockPlaybackController` methods + `subtitle_delay`/`vocal_volume`). **Plan-directed deferred-fix FOLDED (bug-beyond-jad):** resolving a non-empty `temp_dir` activates yt-dlp `--paths temp:{temp_dir}` (youtube_dl.py:192), so `.part`/merge intermediates land in temp_dir — but `_cleanup_partial_downloads` (sole caller `cancel_active_download`) globbed only `download_path`, orphaning them on cancel; **jad has the bug too.** Fixed: sweep `temp_dir` as well (id-keyed `*{video_id}*`, skipped when `== download_path`, so unrelated temp files survive) + new `test_cancel_cleans_partials_in_separate_temp_dir`. Unit-verifiable now (direct cleanup call), so folded despite cancel wiring landing at C-PROC. **Manual 3-axis gate + 1-agent source /code-review: 0 BUGs, 1 DEFERRED, 1 not-a-bug.** Review verified-clean on the failure-prone axes (every constructor arg matches; `song_downloaded` order `register_download`→PM.enqueue→tracker satisfies the DB-`pending`-row dependency; no event double-subscribe; PipelineTracker reads only `__init__`-set PM attrs). **Deferred:** `ProcessingManager.stop()` derefs the bare-annotation `self._orchestrator` (assigned only at the END of `start()`) unguarded → `AttributeError` if `start()` raises early; **not reachable today** (start() is in `__init__`; a partial failure propagates so `k` never binds → `stop()` never runs) and the proper fix (Optional `_orchestrator` + guard, rippling through 4 other uses) needs the live start/stop exercise → **C28 lifecycle bucket @ C-PROC.** **Not-a-bug:** `stop()` doesn't stop `download_manager` (matches jad; daemon worker, no `stop()` by design). **1073 unit pass** (1072 + 1 temp_dir regression); `import pikaraoke.{karaoke,app}` OK; pre-commit clean. **Verify (at C-PROC):** download a non-karaoke song → processing auto-starts + temp artifacts land under the resolved temp dir; cancel sweeps temp_dir; app boots + plays (no signature/call-site mismatch). |
| C34 | 🔨 2026-06-09 | `7080a3e` | **Live now-playing controls — preference half (Phase E opener).** Three files pulled straight from jad end-state (`git diff joint-alignment-dp` empty for all three == jad exactly). **`preference_manager.py`:** the per-song-override **skip block** in `set()`'s target-sync — when a registered target exists, saving `subtitle_delay`/`volume`/`vocal_volume` early-returns `(True, …)` **before** the live `setattr(self._target, …)`, so the currently-playing song isn't jolted; the cosmetic `get()` signature reflow rides along. **Key invariant verified:** the config-file WRITE (`set()` L112-121) happens **before** the target-sync block, so the new default still **persists** and applies at the next song start (re-read via `get_or_default` in karaoke.py/playback_controller, not from the skipped target attr). **`routes/preferences.py`:** the overlay/audio-delay **live-refresh wiring held back from C15** (it derefs `k.playback_controller.refresh_overlays()`/`k.mpv_controller.set_audio_delay()`, which karaoke.py didn't expose until C18) — `_OVERLAY_PREFS={hide_url,hide_now_playing_overlay,hide_clock}`→`refresh_overlays()`, `audio_delay`→`set_audio_delay(float(val))`. **Forward-deps confirmed:** `refresh_overlays` (playback_controller.py:385, no-arg), `set_audio_delay` (mpv_controller.py:601, float secs), `_` imported+used in `set()`. **`test_preference_manager.py`:** the one skip-block-coupled test (`test_set_syncs_target_object` `volume`→`splash_delay`/int — jad changed only this one); `test_preference_routes.py` already reached end-state at C15 (0 diff) so it is **not** touched (per Standing deviation). **Test-impact analysis:** many tests call `set("volume", …)` with a registered target, but only `test_set_syncs_target_object` asserts the live setattr; the rest are persistence/`apply_all`/reset-based (config write precedes sync) → unaffected. **Manual 3-axis gate + 1-agent /code-review: 0 BUGs folded, 1 DEFERRED, 1 test-gap.** Review confirmed the skip design sound (persist-before-skip; no stale `k.subtitle_delay`/`k.vocal_volume` live reads — both re-read from config at song start). **DEFERRED:** `float(val)` on unvalidated `audio_delay` at the route (`preferences.py` ~L40) → a non-numeric admin submit persists the bad value, then `float()` raises → 500; **verbatim jad, admin-gated, no template UI input** (only the raw `change_preferences` endpoint reaches it); the proper fix is route-level type validation (no pref is type-validated at the route today — conversion is downstream in `get()`), out of C34 scope + beyond jad. **Test-gap (deferred):** the route wiring ships untested (jad has no coverage either); minor. **1073 unit pass** (modified one test in place, added none); pre-commit clean; all 3 files == jad. **Verify:** while a song plays, change default `volume` in prefs → the playing song's volume doesn't jump; toggle an overlay pref / change `audio_delay` → refreshes live. |
| C35 | 🔨 2026-06-09 | `a06560d` | **Live now-playing controls — playback/UI half; clears most of the residual karaoke.py-vs-jad delta.** karaoke.py controls split out of the C18-shared hunks (`admin_password` param + try/except + lambda-parens + `log_and_send` left behind): **`volume` is now a `@property`/`@setter`** over `_volume` — the setter syncs the system sink whenever `mpv_controller` exists+running (slider / pref-save / vol_up-down / startup all funnel through one path; the `getattr(self,"mpv_controller",None)` guard no-ops the `apply_all`-during-`__init__` write, bridged by the explicit post-start `set_system_volume`); **`transpose_current` rewritten** to live `playback_controller.set_pitch()` (no restart, no re-enqueue); **`set_subtitle_delay`/`set_vocal_volume`/`set_sub_mode`** track the value on the Karaoke instance + forward + log + notify; **`restart()`** now calls `playback_controller.restart()`; **`reset_now_playing`** resets `subtitle_delay`/`vocal_volume` to config defaults; **`get_now_playing`** exposes both; signature gains the `subtitle_delay`/`audio_delay`/`vocal_volume` params (the C35 share; `admin_password`→C38). The post-start volume comment reconciled to reference the property setter (the C18-earmarked update). **playback_controller.py:** the 3 live setters (guard `is_playing`→forward to `self.mpv`→track `now_playing_sub_mode`/`now_playing_vocal_volume`→emit) applied **as a hunk, NOT whole-restore**, so next's documented race-free `pause()` deviation (deterministic `self.is_paused` toggle + its regression test, vs jad's observer-lagged `self.mpv.is_paused`) is preserved — playback_controller.py residual vs jad = **exactly that pause hunk**. **routes/controller.py + conftest.py:** pure-C35, whole-restored == jad (controller adds `/subtitle_delay`/`/vocal_volume`/`/sub_mode`(mode-validated→400)/`/seek` + drops the now-needless `broadcast_event("skip")` from `/transpose`; conftest adds 4 `MockPlaybackController` methods + `subtitle_delay`/`vocal_volume` attrs). **test_playback_controller.py:** only `test_set_subtitle_delay` added — the pause regression test is **kept** and jad's loudnorm single-line reformats left as next's Black-wrapped form. **`routes/info.py` deferred to C38** (plan refinement): its residual is a **single atomic `render_template` context rewrite** (legacy-key teardown + temp_dir/genius/audio_device/blocked-words exposure + audio-devices helper/route) = the settings-page rework, not these now-playing controls; no separable "volume/subtitle-delay-only" hunk exists, and `test_info_routes.py` is already at end-state (0 residual) so the suite is unaffected. **Forward-deps confirmed:** mpv `set_subtitle_delay`/`set_sub_mode`/`set_vocal_volume` (mpv_controller.py:591/583/516), playback `set_pitch`/`restart` (398/429); `subtitle_delay`/`audio_delay`/`vocal_volume` are DEFAULTS keys so `apply_all` sets the instance attrs before any reader. **Manual 3-axis gate + 1-agent /code-review: 0 BUGs, 2 deferred/awareness.** Review REFUTED all 6 probed risks (property `__init__`-window guard sound; DEFAULTS-backed attrs always set pre-read; `now_playing_*` class-attr-initialized; transpose no correctness loss + the dropped skip-broadcast is correct since there's no song change; no `.volume`-as-plain-attr caller breaks — `MockKaraoke` is standalone). **Deferred:** (1) `float()` on `/subtitle_delay`/`/vocal_volume`/`/seek` URL params → 500 on non-numeric — low-sev, **consistent with existing `/transpose`/`/vol` routes** + same class as C34's `audio_delay`; (2) `mpv_controller.set_subtitle_delay` writes `sub_delay` even outside `srt` mode (invariant wants 0) — **pre-existing in mpv_controller (C11, unchanged by C35; C35 only forwards)**, self-healing on next `set_sub_mode`, benign (karaoke mode renders subs via ASS overlay, not mpv's sub track). **Residual karaoke.py vs jad after C35 = exactly C38 `admin_password` param + the 3 permanent/deferred C18 deviations** (dead try/except removal, Black-clean lambda parens, `log_and_send` danger `error`→C-PROC). **1074 unit pass** (1073 + `test_set_subtitle_delay`); `import pikaraoke.{karaoke,app}` OK; pre-commit clean. **Verify:** during playback the now-playing remote adjusts subtitle delay / sub mode / (dual-stem) vocal volume live; each resets on the next song; live transpose; volume slider syncs the system sink. |
| C36 | 🔨 2026-06-09 | `4ca4c9d` | **Queue routes → processing model. Direction inversion: next was BEHIND jad here (not ahead) — the `git diff joint-alignment-dp` was pure-`-` = "in jad, missing from next", so this is a normal forward pull, not a feature removal.** Adds three pieces back: **(1)** `queue_edit` `pause` action → `k.queue_manager.toggle_pause_song(song)` + its success/error labels; **(2)** `_do_enqueue` **server-side gate** — `state = k.song_manager.get_pipeline_state(song); if state in ("pending","failed"): → 409 {success:False, error}`; **(3)** **user self-service routes** `/queue/user/delete` (`_verify_ownership` scans `k.queue_manager.queue` for `item["file"]==song` → `item["user"]==user`, else 403) and `/queue/user/pause` (`toggle_pause_user`, step-away). **Pull mechanics:** `queue.py` + `test_queue_routes.py` **whole-restored from jad** (`git restore --source`), `test_queue_socketio.py` **left untouched** (already == jad — absent from the residual stat — despite the plan line listing it). **Pre-flight verified all called symbols already exist on next:** `toggle_pause_song`/`toggle_pause_user` (queue_manager.py:261/275), `move_to_top`/`move_to_bottom`, `get_pipeline_state` (song_manager.py:153), `Schema`/`fields` already imported. **C5A interaction satisfied for free:** the diff is purely additive (zero `+` lines next-vs-jad), so a whole-restore re-adds nothing the C5A download-status removal dropped — confirmed jad's queue.py carries no download-status surface (else it'd appear as a `-`-to-restore). **Manual 3-axis gate** clean (3 jad-faithful design notes: `_do_enqueue` reads `query["song"]` w/o `unquote` unlike `queue_edit` — REFUTED as a bug, Flask auto-decodes + DB key matches `enqueue`; `user_*` trust self-asserted `form["user"]` = app-wide username trust model; `_verify_ownership` assumes `file`/`user` keys — always present per `enqueue`). **1083 pass** (+9 user-queue-controls tests); `import pikaraoke.routes.queue` OK; pre-commit clean. **/code-review 1-agent — 0 fix-now, 1 not-a-bug + 1 deferred:** **(A) NOT-A-BUG — gate blocks playable pending/failed downloads:** confirmed jad-**intentional** — `_process_song` deliberately leaves state `pending` on user-cancel ("The stale-pending badge surfaces it... needs reprocessing") and sets `failed` on a stage exception, and jad ships a dedicated 409 gate **test class** (`test_pending_song_rejected_with_409`/`_failed_..._409`). A real "reprocess-before-queue" UX tradeoff (a download whose *optional* stem/lyric processing was cancelled/errored is un-queueable until reprocessed), but it's the owner's deliberate, tested design — **surfaced for product awareness, not overturned** (changing the policy is a product call). **(B) DEFERRED → C42 — file-browser silent no-op on rejection:** the gate's `409 + {success:False}` (scalar) is unhandled by `templates/files.html`'s `$.get(...)` enqueue handler, which expects the success-path `success:[bool,msg]` list and reads `obj.success[0]`/`[1]` — on 409 jQuery's success callback never fires → click does nothing, no notification. Genuine end-state rough edge (jad's files.html JS is un-reconciled with its own gate), but **the fix belongs in the consumer (files.html JS — C42 template rework), not queue.py**: the backend `409`+error contract is *deliberately tested*, so "fixing" it in queue.py would mean rewriting jad's own gate tests. C42 watch (**closed by `fix(enqueue)` `2b9b5c5`**): handle the 409/error shape in the enqueue handlers. **Residual queue.py / test_queue_routes.py / test_queue_socketio.py vs jad = 0** (all == jad tip). **Verify:** add/remove/reorder from the queue page push live to other clients; a `pending`/`failed` badged song shows its badge on the files page. |
| C37 | 🔨 2026-06-09 | `adc51e0` | **Search routes → reworked search page. Direction: next was BEHIND jad** — next's `search.py` was the **master-era** version (last touched by upstream `e49d4b81`, not a recommit), so this is a forward pull, not a removal. **Scope is THREE files, not the spec's two** — Standing-deviation L113 (user-approved split-map omission) puts the `youtube_dl` `get_stream_url`→`get_preview_info` concern in C37 alongside `routes/search.py`; `test_youtube_dl.py` is **NOT** touched (its only residual vs jad is a Black wrap — already at jad content; whole-restoring would reintroduce a >100-char line). **search.py changes:** `search()` drops the master-era " karaoke"-suffix / `non_karaoke` toggle and instead searches the raw string + enriches each result tuple with `k.song_manager.songs.find_by_id(k.download_path, r[2])` (4th element = downloaded-path-or-None, lets the UI flag already-downloaded hits); `preview()` → `get_preview_info` returning `(stream_url, srt_available)` (single yt-dlp call) in place of `get_stream_url`; **two new routes** `lyrics_search` (`clean_genius_query`→`k.genius_client.search`→JSON `[{id,title,artist}]`, `[]`/200 on disabled/empty) and `lyrics_select` (validates the 11-char `_YT_ID_RE`, int-coerces `genius_id`, gates `mode∈{raw,srt}`, requires one of genius_id/mode→400, `write_choice` sidecar→204). **youtube_dl `get_preview_info`:** one `--skip-download` call with `--print url` + `--print %(subtitles)j`, JSON-parses the subtitles line for any `en*` key. **Pull mechanics:** `search.py` + `test_search_routes.py` **whole-restored** (search.py 0-residual pre-Black; test_search_routes.py byte-identical to jad, then Black-wrapped); `youtube_dl.py` **hunk-applied via Edit** (replaces only the `get_stream_url` function body, **preserves next's dropped commented `# cmd += ["--paths", f"download:{temp_dir}"]` line** = a C32-era cleanliness deviation — re-adding it would commit commented code, against CLAUDE.md). **Pre-flight verified all called symbols on next:** `write_choice` (genius.py:179), `clean_genius_query` (genius_lyrics.py:107), `genius_client` (karaoke.py:270), `find_by_id` (song_list.py:140), `json` imported (youtube_dl.py:3); `get_stream_url`'s only consumers were youtube_dl(def)+search.py(import+call) — both updated, no orphan. **Manual 3-axis gate** clean (single-call preview is more efficient than 2 calls; lyrics_select validation thorough). **/code-review 1-agent — 1 fix-now (docstring) + 1 not-a-bug:** **(A) FIXED (bug-fix-first) — `get_preview_info` docstring lied:** it claimed "either manual subtitles **or auto-generated captions**" but the code checks only `%(subtitles)j` (manual). Investigated downstream — `build_ytdl_download_command` (youtube_dl.py:183) fetches **`--write-subs` (manual only), NOT `--write-auto-subs`** — so the **manual-only check is correct** (preview must predict the download's source; detecting auto-captions would make `srt_available` true for videos whose download then finds no SRT). Behavior right, docstring wrong → **corrected the docstring** to state manual-subs-only + the why (the `--write-subs` path). **(B) NOT-A-BUG — blank-line filter line-misorder:** the `[l for l in … if l.strip()]` could in theory swap url/subtitles lines if the url line were empty on rc==0, but yt-dlp prints `NA` (non-empty) for missing fields → empty url line on success is unreachable; filter only strips trailing blanks. **Matching template folded in (fold 2026-06-09):** `search.html` was brought to its jad end state **in this commit** — originally split to C43, but the route's new result shape 500'd `/search` on any results page (`ValueError: too many values to unpack (expected 5)`) because the master-era template unpacked only 5 of the now-**6-tuple** `(title,url,id,channel,duration,existing_path)`; folded back here, the floor since this is the last commit to touch `search.py`. jad's `search.html` unpacks the 6-tuple and drops the dead `non_karaoke` post. **Render test added** (`tests/unit/test_search_render.py`, route-through-template) — reproduces the prior 500 against the master-era template (the bare `/search` page rendered fine, which is why a route-only test missed it); template byte-identical to the reviewed jad end state, so no fresh agent /code-review. **Residual vs jad:** search.py = Black-only (1 long-error-string wrap); test_search_routes.py = Black-only (`json.dumps({…})` arg wraps); youtube_dl.py = dropped comment + Black-clean cmd list (logic == jad). **1097 unit pass** (+14 search-route tests); `import pikaraoke.{app,routes.search,lib.youtube_dl}` OK; pre-commit clean. **Verify:** search returns results and renders cards; preview + add-to-queue work from the search page. |
| C38 | 🔨 2026-06-09 | `bda7ecb` | **Info / files / admin routes → settings/processing model. Direction: next was BEHIND jad** — all three were master-era (info.py last touched by upstream flasgger→smorest `#777`, files.py by `#802` admin-security, admin.py by the sqlite-db commit), so a forward pull, not a removal. **Scope collapsed from the spec's 6 targets to 3 files:** `app.py`'s `ADMIN_PASSWORD = k.admin_password or None` line + `controller.py` already == jad (0 residual, landed earlier), and `karaoke.py`'s only owed C38 hunk (the `admin_password` `__init__` param) is **omitted as dead code** (see deviation). **info.py:** settings `render_template` context reworked to the fork's options (`subtitle_delay`/`audio_delay`/`vocal_volume` from prefs, `audio_device` + `_audio_devices_for_render` — prepends a synthetic "(unavailable)" entry so a saved-but-unplugged device stays selectable instead of silently rebinding to auto, `genius_token`, `blocked_processing_words`, `temp_dir`) dropping the upstream `bg_music_volume`/`disable_*`/`avsync`/`cdg_pixel_scaling`/`screensaver_timeout`/`score_phrases` set; **adds `/info/audio_devices`** endpoint. **Net-fixes the route:** next's master-era info.py was *already broken* — referenced `k.bg_music_volume`/`k.disable_score`/`k.avsync` etc. which the reworked Karaoke no longer defines (grep: 0 on next) → `AttributeError` on every `/info` GET; jad's version references only attrs that resolve on next (`hide_clock`/`hide_now_playing_overlay` are `__init__` params set via `apply_all`; `temp_dir` present; rest are `preferences.get_or_default` reads). **files.py:** `browse()` enriches each page song into `{path, pipeline_state, tracker_status, is_active}` for badge rendering — per-page batched (`get_pipeline_states(page_songs)` + one `pipeline_tracker.get_status()` + one `get_active_job()`, no N+1); all 3 managers resolve on next (song_manager.py:157 / `get_status` yields `song_path`+`processing_status` / processing_manager.py:357). **admin.py (absorbs "Fix exit bug"):** `delayed_halt` `sys.exit()`→\*\*`os._exit(0)`\*\* — the halt runs in a background thread, `sys.exit()` only raises there so the process never terminated; + guarded `shutil.rmtree(temp_dir, ignore_errors=True)` cleanup; + failed-auth `url_for("admin.login")`→\*\*`url_for("info.info")`\*\* — `admin.login` is a **nonexistent endpoint** (no `login` view in admin_bp) so the master-era failed-login path raised `BuildError`; jad's `info.info` exists. **Pull mechanics:** all 3 **whole-restored from jad** (`git restore --source`), **== jad byte-identical** (jad lint-clean under next's 100-char → pre-commit no-op, **zero formatting deviation** unlike C37). **Deviation (dead-code omission):** karaoke.py's `admin_password: str | None = None` `__init__` param (jad has it) is **not added** — `_load_preferences`→`preferences.apply_all` already sets `self.admin_password` from the DEFAULTS key (C17) regardless, `cli_args` is built generically from `locals()`, and **neither next's nor jad's app.py passes `admin_password` to `Karaoke()`** → in jad's own end-state the param is never-passed and behaviorally inert; adding it = a dead constructor arg (CLAUDE.md no-dead-code). Residual karaoke.py vs jad now = this param + the 3 C18 deviations. **Manual 3-axis gate** clean (pre-existing bare `except:` in `get_system_stats` noted — unchanged jad code, not a C38 regression). **/code-review 1-agent — 0 findings:** verified files.py enrichment guards (`if tracker else None`, `if item.get("song_path")`, `.get(song_path,"skipped")`), info.py type-safety (`get_or_default` floats → `int(*100)` safe; device dicts always have name/description), admin.py guarded temp cleanup + intentional `os._exit`/`info.info` + `auth` still validates `next_url.startswith("/")` (no open redirect); unguarded `/info/audio_devices` adjudicated **non-sensitive** (same device list is on the public `/info`; design parity with jad). **Matching templates folded in (fold 2026-06-09):** info.html + files.html were brought to their jad end state **in this commit** — originally split to C44, but the route rework shipped ahead of them and 500'd `/info` (`UndefinedError: score_phrases`) and `/browse` (`TypeError: ...not dict`) for any populated page; folded back here (with the out-of-band browse fix `70b940d`, now absorbed) so neither route ever breaks between the route change and the template catch-up. The fold is exact because this was the **last commit to touch both routes**. info.html drops the `score_phrases`/`bg_music_volume`/`avsync` refs that else raise `UndefinedError`; files.html iterates `song.path` + renders the `processing`/`pending`/`failed` status badges. **Render tests added** (`tests/unit/test_info_routes.py` + `test_files_routes.py`, route-through-template against the real context shape) — each **reproduces the prior 500** when run against the master-era template (the empty-library `/browse` render is exactly why a route-only test missed it). Templates are **byte-identical to the reviewed jad end state**, so no fresh agent /code-review. Only the files.html **enqueue-gate JS reconcile** (jad's `obj.success[0]` add-song handler vs the scalar-`success`/409 gate → mis-toast, not a 500) remains → **C42** (cross-page, with search). **Residual info/files/admin.py + info.html + files.html vs jad = 0.** **1101 unit pass** (+4 render tests); `import pikaraoke.{app,routes.info,routes.files,routes.admin}` OK; pre-commit clean. **Verify:** set/unset admin password in prefs → admin actions gate accordingly; the "exit" admin action terminates the process; `/info` renders the fork's settings (audio device, subtitle/vocal/audio-delay, genius token, clock toggle); `/browse` lists songs with status badges. |
| C39 | 🔨 2026-06-09 | `cab05dc` | **Fontello regeneration → clock glyph (Phase F opens). Direction: next was BEHIND jad** — `static/fontello/*` last touched only by upstream PRs (`#676` drag-drop, `#564` styling); no recommit ever touched it → master-era forward pull, not a removal. **jad's regenerated set adds 5 glyphs** the master-era set lacked: `clock` (`\e827`, Entypo — the clock overlay/info-page icon), `spinner` (`\f110`, Font Awesome), `minus` (`\e828`), `minus-circled` (`\e829`), `spin3` (`\e832`, Fontelico) — hence jad's larger font binaries (eot 19976→21188, woff2 9756→10316). **Pull mechanics:** whole-restored the entire `pikaraoke/static/fontello/` dir from jad (`git restore --source`), **== jad byte-identical, 0 residual** across all 13 files (config.json / 4 css / demo.html / LICENSE / 4 font binaries / svg). **Assets-only — no executable logic, no Python/template change.** **Gate = proportionate manual consistency check** (a multi-agent /code-review has nothing to adjudicate on machine-generated font data + auto-assigned CSS content codes): verified config.json ↔ fontello-codes.css ↔ embedded-font cmap coherence (whole-restore guarantees byte-identity, no code/glyph mismatch possible), each of the 5 new code-points appears **exactly once** (no collision), and LICENSE.txt now attributes the new sources (Entypo, Fontelico, Font Awesome). **No agent /code-review, no auto-test** (ledger: assets); **pre-commit skipped** — all 13 files are under `static/`, which CLAUDE.md excludes (no-op). **Transient (asset-before-template, like C37/C38):** no template on `next` references the 5 new icon classes yet — consumers arrive in later Phase-F commits (info.html clock toggle → **C38**; home/queue `minus`/`spinner` → **C40–C42**). **1097 unit pass** (unchanged — no Python touched). **Verify (final smoke):** icons render across pages; the clock OSD glyph displays where the info-page toggle / `--hide-clock` drive it. |
| C40 | 🔨 2026-06-09 | `ffadef0` | **Shared base-layout styles hook + fork control-box CSS (Phase F template run begins). Direction: next was BEHIND jad** — base.html/custom.css/spa-navigation.js last touched only by upstream PRs (`#676`/`#777`/`#619`/sqlite); no recommit → master-era forward pull. **custom.css whole-restored == jad byte-identical:** control-box links/icons var-ized to `--controls-link-color`/`--controls-link-hover` (was hardcoded `#cccccc`/`#74ccb3`) + the subtitle-mode-btn styling block added. **base.html:** added only the `{% block styles %}{% endblock %}` hook; this is the shared-layout seam through which child templates inject page-scoped `:root` CSS vars — **the C41 home page defines `--controls-link-*` et al. inside its own `{% block styles %}`**, so the hook must exist first. **spa-navigation.js untouched** — the single-bind SPA navigation (the "script-stacking fix") is already on next from the upstream SPA commits (`c12bee0d`/`9409817b`); its sole jad-delta is the `#processing` active-state. **Deferred to C-PROC** (jad introduced them together in `97d62b16 Song Processing tracker`): the `#processing` nav `<a href="{{ url_for('processing.processing') }}">` + both active-state handlers (base.html inline JS + spa-navigation.js) — registering them before the processing blueprint exists would `BuildError` **every** page render (boot-window discipline). **Subject adjusted** from the plan's `refactor(ui): shared base layout + single-bind SPA navigation` since the SPA single-bind is pre-existing & untouched here. **Zero executable logic → no agent /code-review** (same disposition as C39; the predicted "logic-bearing" SPA-nav work turned out pre-existing). **Proportionate gate:** Jinja-parse of all 6 page templates (i18n ext) clean, 238 route/render tests pass, full suite 1097 unchanged (no Python touched). **base.html pre-commit clean** (whitespace/EOL/no-master); **custom.css `static/`-excluded** (no-op). **Transients (asset-before-consumer):** custom.css's `var(--…)` definitions land C41 (until then control-box link color degrades gracefully — undefined var → declaration ignored → inherits; subtitle-mode-btn rules match no elements until info.html C38). **Verify (final smoke):** navigate between pages repeatedly — no duplicated handlers / console errors / stacked scripts. |
| C41 | 🔨 2026-06-09 | `1145224` | **Home / now-playing page overhaul (Phase F continues). Direction: next was BEHIND jad** — `home.html` last touched only by upstream PRs (`#727`/`#657`/`#619`); no recommit → master-era forward pull. **Whole-restored from jad** (replaces the master-era now-playing page with the full control surface: inline singer display, live **seek bar**, +/- **step buttons** for pitch/subtitle-delay/vocal-volume, **Karaoke/Subtitles/Off** subtitle-mode toggle consuming C40's `.subtitle-mode-btn` CSS, dual-stem **vocal-volume** section, tightened vertical rhythm; controls now shown to the song's **owner** not just admins). **Closes C40's asset-before-consumer transient:** home.html's `{% block styles %}` `:root` block DEFINES `--controls-link-*` / `--button-*` / `--time-text-*` / `--controls-*` that C40's custom.css references. **Whole-restore was safe — all backend already on next:** controller.py `/seek`//`/sub_mode`//`/vocal_volume`//`/subtitle_delay` routes, and `get_now_playing()` (karaoke wrapper over playback_controller) emits every consumed key (now_playing_duration/position, subs_available, dual_stem, sub_mode, vocal_volume, + up_next/next_user/volume/subtitle_delay); `playback_position` socket emit at playback_controller.py:396. **Logic-heavy (519-line JS) → manual 3-axis gate + 3-agent /code-review** (line-by-line correctness · removed-behavior + data-contract trace · socket/SPA lifecycle). **3 bug-fix deviations from the jad end-state (bug-fix-first; documented divergences):** **(BUG 1+2 — null-deref crash, CONFIRMED) FIXED:** `home.html`'s `playback_position` handler is bound ONLY here and **no other template `.off`s it** (only queue.html `.off`s `now_playing`), so both it and `handleNowPlaying` persist on the shared `window.socket` after navigating away; their raw `getElementById("seek-bar"/"time-total"/"time-elapsed").value/.innerHTML` then threw a TypeError on **every** position-tick / now_playing-push on any non-home SPA page during playback (continuous console-error spam, dead position handler). Guarded all the seek/time lookups (existence check → return/skip when off-page). **(BUG 3 — sticky control-box, CONFIRMED) FIXED:** the owner-visibility `if (isAdmin || cookie===now_playing_user) show()` had no `else`, so when the song advanced to a **different** user's track a non-admin ex-owner kept a live control box (pause/skip/seek/transpose) for someone else's song; added the matching `else { hide() }`. **Deferred watch (real, lower-severity, not fixed):** the `visibilitychange` reconnect branch does `window.socket = io()` then re-registers ONLY `now_playing`, never `playback_position` → after a background-tab socket drop+reconnect the seek bar stops live-updating until the next navigation (now null-safe so no crash; fixing it cleanly needs naming the handler / a `bindPlaybackPosition()` extract → reserved for a focused socket-lifecycle follow-up). **Not-a-bug (adjudicated):** step-button raw `getElementById(...).value` is safe by construction (the +/- icons live inside the same `{% if is_transpose_enabled %}` / display-gated section as their slider, so they're unclickable when the slider is absent); the dropped transpose `confirm()` is an intentional jad UX change (live step transpose), not a lost guard; controller.py routes being server-ungated is **pre-existing on next** and out of this template commit's file scope (separate auth concern). **Residual vs jad:** exactly the 3 fixes above (else-hide + two null-guards); everything else byte-identical. **Gate results:** Jinja-parse (i18n ext) OK, 238 route/render tests pass, full suite **1097 unchanged** (no Python touched), home.html pre-commit clean. **Verify (final smoke):** now-playing shows correct title/singer; +/- pitch/subtitle/vocal buttons + seek bar work; subtitle-mode toggle switches modes; layout not cramped; **navigate away mid-playback → no console errors**; a non-owner sees no control box once another user's song starts. |
| C42 | 🔨 2026-06-09 | `521081e` | **Queue page rework (Phase F). Direction: next was BEHIND jad** — `queue.html` last touched by upstream PRs; no recommit → master-era forward pull. **Whole-restored from jad == byte-identical** (verbatim, no deviations). The master-era page rendered queue rows server-side; jad's is a **JS-driven live page**: `queuePage_getQueue` fetches `/get_queue` + `/now_playing`, diffs against the previous snapshot (skip redundant redraws), and rebuilds `#auto-refresh` client-side via `queuePage_generateHTML`; admin-only Sortable drag-reorder converts DOM→queue indices (now_playing offset) and POSTs to `/queue/reorder`. **No render-window gap:** the consuming route (queue.py) reached jad at **C36** and the page rendered on next throughout (no server-side `{% for %}` over the queue to break — also why this swap fixes no 500; user confirmed "queue seems fine"). **All url_for endpoints resolve on next** (`now_playing.now_playing` blueprint registered app.py:88/103, `queue.get_queue`/`queue.reorder` on queue_bp, `static`); route supplies exactly the consumed context (`queue`, `admin`, `site_title`, `title`). **Template-only verbatim restore → proportionate gate (C39–C41 precedent), no agent /code-review** (zero new/diverged logic; the JS is jad's reviewed end state): render-smoke `/queue` 200 for admin/non-admin × empty/populated (`admin|tojson` → true/false, shell markers present), Jinja-parse OK, pre-commit clean (trailing-ws/EOF only — template not `static/`-excluded), full suite **1103 unchanged** (no Python). **Residual queue.html vs jad = 0.** The files.html/search.html enqueue-gate JS reconcile (silent no-op on the C36 409) is **NOT here** — bug-fix-first jad-divergence (jad has the bug; queue.html itself has no enqueue handler), its own `fix(enqueue)` commit (**`2b9b5c5`**, done — closes the C42 watch). **Verify:** queue reflects current state; add/remove/reorder works and updates live across clients. |
| fix(enqueue) | 🔨 2026-06-09 | `2b9b5c5` | **Enqueue-gate 409 client reconcile (bug-fix-first divergence; closes the long-tracked C42 watch — NOT a jad-pull, jad ships the bug).** The C36 server gate returns **409** `{success:false, error}` on a pending/failed `pipeline_state`, but jad's three client enqueue handlers had only `success:` callbacks → on a 409 jQuery never fired them → clicking "add to queue" on a pending/failed song was a **silent no-op** (bare "!" on the result-button path). Reconciled all three to the gate's two shapes (200 `success:[ok,msg]` list from `queue_manager.enqueue`; 409 scalar `success:false`+`error`): **(1) files.html** `a.add-song-link` (`$.get`) → add `.fail()` parsing `error` (generic fallback on non-JSON); **(2) search.html** selectize add (`$.ajax` POST) → add `error:` cb toasting the reason, **without** clearing the selectize on failure (keeps the selection to retry; only success clears); **(3) search.html** `enqueueLocalSong` (`$.ajax` GET) → `if(result.success)`→`if(result.success[0])` (a non-empty `[ok,msg]` array is **always truthy**, so the old check took the ok-branch unconditionally and the else was **dead**) — now-live else surfaces the real `result.success[1]` (e.g. the per-user queue limit, not just hardcoded "Already queued") and its `error:` cb always toasts a reason (parity). `showNotification` = base.html page-global; `$select` encloses the selectize handler. **No server change** (409 contract is C36's, own gate tests). **Manual 3-axis + /code-review (2 finders):** 3 findings = these fixes (verified `success[0]`/`obj.success[0]` safe — 200 body's success is always a list; `.fail()` chain valid; 409→`.fail`/`error` not success). **Known-and-left (out of scope):** bare-literal fallback toasts (jad's existing JS + the server `error` f-string are un-translated; client-only localization would be a partial fix → separate i18n pass); the 3× parse-toast block not extracted to a global helper (would broaden the divergence into base.html). Render-tests (Jinja-parse) + full suite **1103 unchanged** (no Python); pre-commit clean. **Residual vs jad:** files.html (+5) + search.html (+13/−2) carry exactly these fixes; queue.html == jad. **Verify:** add a pending/failed-badged song from /browse and /search → a red toast names the reason (no silent no-op); a normal add still works + live-updates. |
| C-PROC | 🔨 2026-06-10 | `54138f0` | **Processing page — routes + push + template, the Phase F closer (absorbs C31 + C33 + the processing-UI bug class).** Three new files **whole-restored from jad == byte-identical, 0 residual** (`routes/processing.py` server-driven action endpoints; `templates/processing.html` push-driven status + fetchStatus-debounce + safe-remove; `tests/unit/test_processing_routes.py` 41 tests). **app.py:** the 3 C-PROC hunks now == jad — `processing_bp` import + `_internal_blueprints` registration + the `_pipeline_changed`→`k.pipeline_tracker._on_change` wiring (Socket.IO `pipeline_updated` push replacing the 1s poll). The cancel UI goes live here (`/processing/<id>/cancel` → `pipeline_tracker.cancel` → `download_manager.cancel_active_download`/`cancel_pending_download`), so the deferred download-cancel fixes land with it. **Nav fold (2026-06-10, user-reported "page restored but not on the UI"):** the route + template shipped with no menu entry — the navbar link C40 had deferred to C-PROC was never pulled. Restored **== jad** the two pieces C40 punted here: `base.html` (the `<a href="{{ url_for('processing.processing') }}">` navbar item + its inline `/processing` active-state highlight) and `static/spa-navigation.js` (the `/processing` SPA-route active-state branch). Page is now reachable from the menu and highlights when open; `url_for('processing.processing')` resolves (`/processing`), 41 route tests still render base.html green. **3 Review-fixes (bug-fix-first; the only divergences from jad):** **(1) app.py NameError — push dead on arrival:** jad calls `broadcast_event("pipeline_updated")` but imports only `get_karaoke_instance` from `current_app` → the `_pipeline_changed` callback would raise `NameError` the first time the tracker changed (the page never gets a push); added `broadcast_event` to the import. **(2) spurious danger toast on cancel:** a user cancel kills yt-dlp → `_execute_download` sees `rc!=0` and emitted an "Error downloading" danger toast + `download_error` for a deliberate stop; added a `_cancelling` flag (set in `cancel_active_download` when killing, reset at each download's start, consumed in the `rc!=0` branch). **(3) `_cancelled_urls` permanent leak + silent re-queue skip:** `cancel_pending_download` unconditionally `.add`ed the URL then rebuilt the queue to drop it, so the worker never dequeued it to discard the entry → the set leaked forever and a later re-queue of the same URL was silently skipped at the worker's skip-check; now the URL is recorded **only** for the in-flight (just-dequeued, not-yet-active) window, a still-queued item being dropped by the rebuild alone. **/code-review (2 convergent finders) caught a TOCTOU the plan's deferred-fix #2 missed:** the tracker flips `download_status` "pending"→"active" only lazily in `get_status()` (pipeline_tracker.py:115), so an **already-active** download can be routed through the pending path → `not removed` → recorded → leaks (worker is past its skip-check, never discards, download never killed). Fixed by delegating to `cancel_active_download` when `video_url == self.active_url` (kill, don't record). The other convergent finding (the in-flight test was a false-green — asserted the record, never drove the discard) fixed by replacing it with a real worker skip+discard integration test + an active-misroute kill test. **6 download_manager tests added** (toast-suppression; queued-drop-without-record; keep-others; just-dequeued-records-skip; active-misroute-kills-not-records; worker-skips-and-discards). **Absorbs** the historical "Eliminate processing UI bug class" + "Fix tracker remove-race + fetchStatus debounce" (UI half; the model half — `_on_change` hook + remove-atomicity — landed at C29). **3-axis manual gate** clean (`_on_change` is the real fired-at-386 hook, exception-guarded; `k.pipeline_tracker` exists post-C32; restored route API matches the C29 tracker — 41 route tests green). **Still-deferred (left):** ProcessingManager.stop() unguarded `self._orchestrator` deref (the C32 "C28 lifecycle bucket" — still unreachable: start() is in `__init__`, a partial failure means `k` never binds so `stop()` never runs); and the **pre-existing** (C5-owned, surfaced by review) duplicate-URL shadow/queue desync (shadow filter drops all copies, queue rebuild drops only the first). **Correction (2026-06-14):** this note originally implied the *other* deferrals weren't made-live — wrong. A deferred-fix audit found C28 #2/#3/#4 (cancel-races) and C30 #1/#2/#3 (PTY relay/shutdown) **were** reachable via the live cancel route + PTY; they were folded into their owning commits (C28 `9f8df45` / C30 `2ef99c7`) 2026-06-14, not here. Only C28 #1 (`stop()`/`_orchestrator`, unreachable) and the C5 dup-URL desync remain. **1150 unit pass** (+6 cancel/worker tests); `import pikaraoke.{app,routes.processing}` OK; pre-commit clean. **Residual vs jad:** routes/processing.py + test_processing_routes.py + processing.html + base.html + spa-navigation.js = 0; app.py = the broadcast_event Review-fix + pre-existing dead-import/regex divergences; download_manager.py = the 2 cancel Review-fixes atop the pre-existing temp-dir-cleanup fix. **Verify:** process a song → phases advance live with no manual refresh; cancel an active download → no spurious error toast, no ghost row; pending songs show pending state; two clients both update from the push. **Gate fold (2026-06-10):** + `processing.processing` stubs in the 3 recommit-born render-test fixtures (`test_files_routes`/`test_info_routes`/`test_search_render`) — the nav fold's `url_for` post-dated their stub lists, 500'ing 6 render tests at the final gate; folded here as the owning commit (fixup+autosquash, `7b78971`→`54138f0`; C46/C47 re-SHA'd in tow). |
| C46 | 🔨 2026-06-10 | `09af50c` | **i18n catalog regen — Phase G opener; regenerated, not carried.** Ran the documented `_TRANSLATION.md` workflow on next's source (from `pikaraoke/`): `pybabel extract -F babel.cfg -o messages.pot --add-comments="MSG:" --strip-comment-tags --sort-by-file .` → `update -i messages.pot -d translations` → `compile -d translations`. 31 files (`messages.pot` + 15×{`.po`,`.mo`}). **Verified next == jad's *source* string set:** a fresh extract from jad's own worktree yields the **identical 237-msgid set** (0 set-diff both directions), so next has reached jad's translatable end-state exactly; the only pot delta vs a jad-source extract is **106 `#:` location-line shifts** from next's Review-fix code (no msgid/msgstr content differs). **Removed-UI strings retire to `#~` obsolete** (excluded from the compiled `.mo`, kept for translation memory per repo convention — master 89 / jad 198 / now 261): the C5A download-status surface ("Queued"/"Failed"/"Pending downloads"/"Download queue"/"Download Errors") + old "Show clock" + splash/score; **new strings active**: "Processing"/"Added for processing..."/"Hide clock"/"No songs in the processing pipeline."/audio-device + restart settings. **2 deliberate choices (documented in the commit body):** (1) **compiled without `-f`** so the pre-existing uncertain fuzzy auto-matches fall back to untranslated English in the `.mo` rather than shipping a possibly-wrong translation (gettext default; the C46 spec also omits `-f`); (2) **restored the repo's `#.` translator comments** (master carries 203; jad's bare extract had dropped all → 0; now 175 for the current UI) — e.g. the "Processing" nav link's `MSG` comment, extracted from `base.html:228` + `processing.html:4` (the comment added in the C-PROC nav fold). **jad's committed catalogs intentionally NOT the target** — they are **stale** (POT-Creation-Date 2026-05-02, generated before jad's final template changes; the download-status strings are still **ACTIVE** in them), so the translation files **diverge from jad by design** (the whole point of C46); expect a large `git diff joint-alignment-dp -- pikaraoke/translations pikaraoke/messages.pot` at the final gate — **not a missed hunk**. **Pure data regen, zero logic → no agent /code-review** (proportionate gate: msgid-set == jad-source verified; all 15 `.mo` load via `gettext.GNUTranslations` + "Processing" resolves; `import pikaraoke.app` OK; pre-commit clean — the trailing-ws hook stripped trailing space off empty `#,` flag-lines on 5 `.po`, recompiled those `.mo`, re-ran → clean). **Residual vs jad:** intentional & large (stale-catalog divergence above) — NOT zero, by design. **Verify:** switch UI language — pages translate, no missing/garbled strings, no leftover splash/score/download-status text. |
| C47 | 🔨 2026-06-10 | `a5567d7` | **Backfill artifacts script — Phase G closer; the last code commit.** Two new files **whole-restored from jad** then bug-fixed: `scripts/backfill_artifacts.py` (511 ln) + `scripts/README.md`. The CLI scans a song folder, classifies each video's missing artifacts (stems / karaoke `.ass` / subtitles), prompts Genius once up front for songs needing lyric work, then runs a **minimal per-song stage subset** (`build_stages_for`) via `PipelineOrchestrator.run_one` with an explicit `lyrics_path` resolved in-CLI (`resolve_lyrics_path`) — deliberately bypassing the live app's YouTube-ID-keyed `LyricsFetchStage` sidecar so manually-added (non-11-char-ID) songs can still use Genius. Imports the same stage classes/workers/config as the live app (matcher/config changes propagate). **Two flags land in final form:** `--match-method {auto,walk,tiling,joint}` (default `None` → override `config.match_method` for the run, comparing matchers without editing config; `joint` works because C19/C22/C26A precede it) and `--use-bundle-lyrics` (reuse cleaned `lyrics.align_lines` from `alignment_debug/<stem>.json`, write `<stem>.txt`, choice `("bundle", path)`, instead of the interactive Genius prompt; songs without a bundle still prompt). **Cross-file seams all verified** (1-agent angle, `[]`): `PipelineOrchestrator(stages, stem_worker, whisper_worker, config)`/`.run_one(song, lyrics_path)`, every stage ctor (`FFmpegExtractStage(config)`/`StemSeparationStage(stem_worker)`/`LoadVocalFromM4aStage()`/`LyricAlignStage(whisper, config)`/…), `StemWorker(model_dir=,model_name=)`/`WhisperWorker(config.whisper)` + `.start()`/`.stop()`, `GeniusClient(api_token=)`/`.search(limit=)`/`.fetch_lyrics`/`GeniusUnavailable`, and `run_one` does set `ctx.artifacts["lyrics_path"]` (README claim confirmed); `youtube_id_suffix` strips the extension internally so `_default_query`'s `stem[:-len(suffix)]` slice is correct (not an over-trim). **Logic-bearing → 3-agent /code-review (line-by-line · cross-file seam · cleanup/altitude); 2 Review-fixes folded (bug-fix-first divergences):** **(1) worker-leak on OOM:** `run_jobs` started the stem+whisper workers **above** the `try/finally`, so a second-worker `start()` failure (CUDA OOM when both models contend for one GPU — the exact case the eager start exists to surface) skipped the `finally` and leaked the already-started worker's GPU subprocess; moved both `start()` calls **inside** the try (`stop()` early-returns when `_process is None`, so the move is safe — verified both workers' `stop()` guards). **(2) stale README:** jad's `scripts/README.md` documented only `--match-method {auto,walk,tiling}` and omitted both `joint` and `--use-bundle-lyrics` that the final script ships; updated the usage block, matcher prose, and lyrics-resolution list (added the `bundle` source) to match `--help`. **3 review candidates NOT acted on (deliberate):** subtitles-only-missing re-aligns + overwrites an existing good `.ass` (**README documents this** — "No SRT-only generation… the pipeline writes ASS and SRT together… Acceptable for now" — by-design); empty-bundle → empty lyrics `.txt` (requires malformed/instrumental bundle; bundles come from successful aligns + malformed JSON already caught → guarding a near-impossible state = speculative); and the cleanup findings (reuse `LyricsFetchStage._find_srt`, simplify `_make_genius` singleton, `genius._token` private access, path-convention duplication) are real-but-cosmetic — acting would diverge from jad for **style only**, noising the final diff gate without fixing a bug. **Gate:** `py_compile` OK, `--help` lists both flags (auto-test), `import pikaraoke.app` OK, pre-commit clean (pylint + shebang/executable-bit + markdown all pass; file is `100755` with `#!/usr/bin/env python3`); **1150 unit pass** (no test files in scope — the script is a manual maintenance tool exercised by the final-gate joint-route smoke). **Residual vs jad:** exactly the 2 Review-fixes (the worker-start move + the README flag/bundle docs); nothing else. **Verify (final smoke):** run on one existing song → stems/subtitles/loudnorm produced + a non-YouTube-ID song resolves lyrics via Genius; `--match-method joint` forces the joint matcher; `--use-bundle-lyrics` skips the Genius prompt for a song with a saved bundle. |
| GATE | ✅ 2026-06-14 | `a5072a5` | **Final gate — COMPLETE: static + CPU-side (2026-06-10) + GPU inference legs (2026-06-14, local RTX 2060) all verified; only the PR remains, held per user instruction.** **(a) Full suite:** 6 render-test failures (`BuildError: processing.processing` — C-PROC's nav fold post-dates the recommit-born render fixtures' stub lists) → stubs added to `test_files_routes`/`test_info_routes`/`test_search_render`, **folded into C-PROC** (fixup + `GIT_SEQUENCE_EDITOR=true rebase -i --autosquash`; **re-SHA: C-PROC→`54138f0`, C46→`09af50c`, C47→`a5567d7`** — both pushed SHAs churned, `next` needs a force-push when syncing) → **1150 green**. **(b) pre-commit --all-files:** 2 stragglers the per-commit (changed-files-only) runs never covered — black on `test_tiling_match.py` (== jad; jad isn't black-clean under this env's black) + requirements-txt-fixer sort of `requirements.txt` (header comment moved above a blank line so the hook keeps it top-of-file) → this `style:` tip commit `a5072a5`; **all 16 hooks pass**. **(c) Diff review PASS:** `git diff joint-alignment-dp -- . ':!QWEN.md' ':!mockup/**' ':!plans/**'` read hunk-by-hunk — translations large+intentional (C46), static deletions (C1), test files are recommit-born additions, and **every source hunk maps to a recorded Review-fix in its owning row** (app.py broadcast_event+log-regex; karaoke.py mpv-start propagation + danger→error; download_manager cancel trilogy + temp-sweep + `glob.escape`; genius `[]`-contract guard; Unicode-letter regex; joint_match docstring; scanner ID-dedup; mpv_controller shutdown-races + track-poll + MUTED + zmq LINGER/close + Image ctx-mgr; overlay `_ass_escape` + `invalidate()`; tracker `_notify_change` outside lock; pause-race; `get_preview_info` manual-subs; orchestrator started-flag order; `run_ffmpeg` cancel-window kill; `BaseProcess`; enqueue-409 JS; home.html seek null-guards + control-box hide) — **nothing unexplained**. **(d) CPU e2e smoke PASS** (box has no GPU/driver; torch cu130 falls back to CPU): isolated-HOME boot (`HOME=/tmp/pk_home_next`, mpv + stem/whisper workers start, scan, Flask :5555) · all 6 pages 200 (nav `url_for` resolves) · `/search` returns live yt-dlp results · enqueue → **dual-stem playback** (duration 214s detected, lavfi vocal/nonvocal) with karaoke `.ass` subs + URL/QR + now-playing overlays **screenshot-verified** (ffmpeg x11grab) · clock overlay default-on **12:36 PM bottom-left**, pref-off **actually clears** (exercises the `invalidate()` fix), restored on · pause/resume/transpose+2/vocal-volume 0.8 (ZMQ)/seek 60/skip all state-correct via `/now_playing` · de+fr locales translate (C46) · download (8s) → tracker `active` + server-driven actions → pipeline handoff (reached `stem_separation`) → **admin cancel** settles clean (no spurious toast, actions emptied, "Processing cancelled" logged, stale-pending per design) → `/quit` tears down processing/workers/mpv, **exit 0**. **(e) GPU legs DONE 2026-06-14 — this Linux box has an RTX 2060 (6GB); the gate's earlier "no GPU" no longer holds.** Both inference legs ran green via `scripts/backfill_artifacts.py <stage> --match-method joint --use-bundle-lyrics --yes`: **(i) joint-route smoke** on two cached-stem songs (Let It Go `YVVTZgwYwVo` clean + the actual Hakuna Matata `fwLxDUQBdEg` — substituting the planned `cwLRQn61oUY`/`jbTj2M3vmts`, which are absent from this box's library) → whisper-align inference, `succeeded=2 failed=0`; **(ii) full processing-to-complete** on one mp4+bundle-only stage (stems omitted → forced **stem-separation (roformer) inference**): ffmpeg_extract→loudnorm→stem_separation→transcode→lyric_align→joint, `succeeded=1 failed=0`. **No OOM** — both models co-resident peaked at **5.4GB/6GB** @100% util (large-v3-turbo fits the documented contend-on-one-GPU case); both unloaded cleanly each run (no worker leak). **Joint matcher** `absent=0` at alpha=2.00 on all 3 runs (Let It Go 68/68; Hakuna cached 40/40; Hakuna from-scratch 40/40). **Output verified:** every SRT monotonic + non-overlapping, zero empty cues, **1:1 with lyric lines** (each sung line → one cue; non-sung intro/instrumental lines correctly omit a cue; karaoke `.ass` Dialogue-line count == SRT cue count); **clean lines keep align timings** — Hakuna's 26 directly-comparable clean lines matched the library reference SRT at **0ms** drift (median+max). The Let It Go 49→68 bundle-reuse line expansion is correct `source_kind=srt`→`txt` flattening (splits embedded `\n`, strips `♪`), not a bug. **`--hide-clock`** parses True-with-flag / False-without, wired CLI→args→Karaoke ctor→overlay (clock render-clearing already screenshot-verified in (d)). **(f) PR not opened** (user instruction — gate only). |

### Resume checklist (cross-machine)

1. On this machine: `git push origin joint-alignment-dp` (plan + log) **and** `git push origin next` (reconstruction commits).
2. On the other machine: `git fetch origin`, `git checkout joint-alignment-dp` (read this log), `git worktree add ../pk-next next`.
3. Continue at the first commit above not marked ✅. Re-read its Decisions cell, and the Standing deviations below, for in-flight changes.

### Standing deviations from the written plan (carry forward until done)

- ~~**C15** must also `git rm pikaraoke/lib/raspi_wifi_config.py` (deferred from C1)~~ — **done at C15** (`981bee0`), removed alongside its only consumer `routes/splash.py`.
- **C15 auto-test diverges from the plan: `import pikaraoke.app` cannot pass at C15** (built 2026-06-03). `app.py` still imports the deleted `browser`/`file_resolver`/`stream`/`splash`/`background_music` at module level; those imports + the browser/temp-dir lifecycle are removed together in **C16** (the gevent→threading teardown — a cohesive unit not worth fragmenting just to keep one intermediate commit's smoke green). Per the reconstruction's "only the tip must boot," this single-commit break is accepted; C15 was verified instead via scoped import checks (surviving modules import; suite green — no test imports `app`). **Resolved: C16 (`47bab42`) drops those module-level imports + the browser/temp-dir lifecycle, so `import pikaraoke.app` passes again.**
- **`preferences.py` is split across C15/C34** (built 2026-06-03). Score-phrase teardown landed at **C15**; the overlay/audio-delay live-refresh wiring (`_OVERLAY_PREFS` + `k.playback_controller.refresh_overlays()` + `k.mpv_controller.set_audio_delay()`) is **deferred to C34** because it dereferences `k.mpv_controller`, which `karaoke.py` does not expose until **C18**. `tests/unit/test_preference_routes.py` already reached end-state at C15 (its whole diff was score-teardown), so **C34 touches `preferences.py` only, not that test file.**
- **C13 (ffmpeg simplification) relocated to C18A** (user decision 2026-06-03) — *canonical rationale for this deviation; other mentions point here.* `lib/ffmpeg.py`'s `build_ffmpeg_cmd`/`get_media_duration`/`supports_hardware_h264_encoding` are still imported at module level by code that dies later: `stream_manager`/`file_resolver` (C15) and `karaoke.py` (C18). Because `pikaraoke/__init__.py` eagerly imports `Karaoke`, dropping them at the original C13 slot breaks `import pikaraoke` (hence the C14–C17 auto-tests, not just live boot) — same hazard as the C1→C15 raspi deferral. They ride as inert dead code through C14–C17, then drop whole in **C18A** (`52cf2f6`), immediately after C18 removes the last consumer. ffmpeg.py reaches the tip only at C18A. **(Done.)** `test_ffmpeg.py` was **reduced, not removed** — jad keeps the file (the three surviving fns' coverage); C18A only dropped the two removed-helper test classes (the build spec's earlier `git rm` note was stale).
- **C-CLK dissolved — the clock rides with its owning files, not a dedicated vertical commit** (user decision 2026-06-03; supersedes every `→ C-CLK` routing note below, incl. Per-file refs + the C-CLK commit spec). A standalone clock commit needed `e`/`n`-exclusions from ~8 commits for marginal benefit; instead each clock touchpoint ships with the file that owns it: (a) **clock OSD render → C12** (`overlay_manager.py` committed whole, clock included — done, `4e9350f`); (b) **`--hide-clock` arg → C17** (`args.py`: stop `n`-skipping it — include the add_argument hunk); (c) **`hide_clock` DEFAULTS line → C17** (`preference_manager.py`: stop `e`-extracting it — keep the line); (d) **`hide_clock=` ctor kwarg + clock tick wiring → C18** (`karaoke.py`, part of the signature/attr hand-split). When building C17/C18, treat the `hide_clock` lines as in-scope (the worked `e`-extract example at "Worked example — `e`-extracting one line" no longer applies and is retained only as a mechanics illustration).
- **C14 diverges from end-state on `playback_controller.pause()`** (user-approved Review-fix, 2026-06-03). The end-state `pause()` dropped the pre-MPV `self.is_paused = not self.is_paused` toggle and reads the observer-lagged `self.mpv.is_paused`; C14 restores the controller-side toggle (deterministic source for `routes/controller.py:28`'s `/pause` broadcast + the Pause/Resume notification). Consequence: `pikaraoke/lib/playback_controller.py` will **not** equal `joint-alignment-dp` at the tip — the only delta is this `pause()` fix (+ regression test in `test_playback_controller.py`). If a real upstream pause fix later lands in the branch, reconcile against this.
- **C7 absorbs the loudnorm DB layer (plan + Fix-absorption audit put it in C14).** `karaoke_database.py`'s `loudnorm_offset_db` column + `get/set_loudnorm_offset` ship in **C7** (whole-file), inseparable from `pipeline_state` at the v2-migration + shared-migration-test level. **C14 must NOT touch `karaoke_database.py`** — it consumes C7's accessors and ships only the playback loudnorm filter + the `song_manager` `get/set_loudnorm_offset` forwarders.
- **C8 consolidates YouTube-ID extraction to one source (deviation from end-state, user-approved).** `library_scanner.build_song_record` routes through `metadata_parser.extract_youtube_id`; the private `library_scanner._extract_youtube_id` + its 4 duplicate tests are deleted (the branch left both). Realizes the C6 docstring's stated intent and makes C6's "rewired in C8" true. Consequence: `library_scanner.py` + `test_library_scanner.py` will **not** equal the tip — the only delta is this dedupe.
- **C9's "literal-safe glob / library-wipe" language is stale** — that fix is **C5**'s (`download_manager._cleanup_partial_downloads`). C9's `song_manager` has **no glob**; companion paths are built literally via `os.path.exists`, so a delete can never reach an unrelated sibling. Dropped the glob line from C9's commit message. **C14** still excludes nothing new here — it adds only the `song_manager` `get/set_loudnorm_offset` forwarders (C9 already shipped the pipeline_state forwarders + `events=` ctor arg).
- **C0 wart #2**: when regenerating `uv.lock` on Windows, reconcile the `pre-commit` pin between `[project.optional-dependencies].dev` and `[dependency-groups].dev` (and drop the stray blank line).
- **`youtube_dl.py` + `test_youtube_dl.py` are multi-concern** (split-map omission, user-approved split): C4 = impersonation (done). C5 = `build_ytdl` final shape + test rewrite (done). **C37** still owes `get_stream_url`→`get_preview_info` (returns `(url, has_en_captions)`) alongside `routes/search.py`; the two files equal the tip **only after C37**.
- **Download-status surface fully removed (producer C5, consumers C5A).** C36 (`routes/queue.py`), C42 (`templates/queue.html`), C-PROC (`app.py`) must **not** re-remove these (C5A already did) but must still apply their *other* changes so each file reaches tip. Net per file: master − download-status-surface (C5A) + that commit's own rework = tip. When building C36/C42/C-PROC, expect their diff-vs-master to already be partly applied.
- **C16 folds three Review-fixes (bug-fix-first; `app.py` + `socket_events.py`).** (1) Dropped the unused `get_platform`/`is_windows`/`get_data_directory` imports + the orphaned `platform = get_platform()` local (Android-block removal stranded `platform`; the other two were already dead in master, `get_data_directory` only in a commented-out log-path example); (2) anchored `_NoGetFilter`'s status match to the access-log line tail so a non-access record or crafted path echoing `" 2xx "` can't be over-suppressed; (3) dropped `socket_events.py`'s unused `from flask import request`. pycln tolerates the dead imports, but the plan's fidelity scope (purge transition-era orphans) + bug-fix-first warrant all three. Consequence: `pikaraoke/app.py` and `pikaraoke/routes/socket_events.py` will **not** equal `joint-alignment-dp` at the tip — the deltas are these three Review-fixes (the in-flight C32/C-PROC/C38 splits otherwise converge to jad). C32 (Karaoke kwargs), C-PROC (`processing_bp` + `_pipeline_changed`), and C38 (`admin_password`) pull only their own hunks, none of which re-introduce the dead symbols, so the removal persists to the tip. The `# log_path = … get_data_directory()` comment is left as an inert illustrative example.
- **C23 folds two Review-fixes (bug-fix-first; user-adjudicated 2026-06-08) → `genius.py` + `genius_lyrics.py` won't equal jad.** (1) `genius.py search()` wraps its result-parsing loop in `except (KeyError, AttributeError, TypeError)`→log+`[]`, so a malformed Genius response (null section, null `primary_artist`, hit missing `id`/`title`) honors the documented "\[\] on any failure" contract (jad's loop sat outside the network `try/except`). (2) `genius_lyrics._HAS_LETTER_RE` widened from `[A-Za-z]` to any Unicode letter `[^\W\d_]`, so `parse_lyric_lines`/`clean_srt_line` keep non-Latin (CJK/Cyrillic/accented) lyric lines instead of dropping them as letter-less. Plus a behavior-identical Black reformat of `_CURLY_QUOTES_TABLE` (one line). **Not-a-bug (left as jad):** `clean_genius_query` reuses `NOISE_PATTERN` (strips generic title words like `by`/`live`/`hd`); deliberate per user. No later commit re-pulls these whole files, so the deltas persist to the tip.
- **C18 keeps `karaoke.py` `log_and_send`'s "danger" branch at `logging.error`** (deliberate divergence, documented 2026-06-15) → `karaoke.py` won't equal jad on this line. jad downgraded the "danger" category from master's `logging.error` to `logging.warning` (a log-noise tweak); next keeps `logging.error` because a danger-category notification is error-severity, so error-level logging is the more correct choice (bug-fix-first). The C18 cell originally filed this as "to reconcile to jad's `warning` in a later `log_and_send` touch (C35/C-PROC)"; that reconciliation is intentionally **not** done — it is a kept divergence, not an outstanding TODO. No later commit re-pulls the whole file, so the delta persists to the tip; together with the C18 mpv-start `try/except` removal + the three unparenthesized event-bridge lambdas + the dropped `admin_password` param, this is the full residual `karaoke.py` diff vs jad.

## Decisions (confirmed)

- **Feature-aligned commits.** Every commit is a single feature unit — an
  addition, a modification, or a removal — and ships its code in final, correct
  form. The source branch's historical "Fix…" commits (volume bug, pause-toggle
  glitch, pipeline-tracker remove-race, glob library-wipe, stem-worker OOM,
  subtitle race, …) are **absorbed** into the feature commit that owns the code —
  pulling jad's end-state content *is* the fix — never replayed as standalone fix
  commits. Where a commit description below mentions a past bug, it means "this
  feature's final code already behaves correctly."
  **Review-fixes fold into the owning commit, never a follow-up.** When review
  finds a bug, fold the fix into the commit that owns the code: amend it if it's
  the current tip, or `fixup`/`--autosquash` into an earlier already-built commit
  — which **amends the owner in place**, not a standalone "fix C<n>" commit.
  (The autosquash must run interactively:
  `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <sha>~1` — plain
  `git rebase --autosquash` without `-i` silently no-ops.)
  Reopening an earlier commit to fix a real bug — **including an already-verified
  one (C0–C10)** — is expected and the default; flag each reopened commit for
  re-verification.
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
- **Testability:** each commit's own associated tests pass, and commits are
  ordered so nothing is left half-wired longer than necessary; the **full pytest
  suite must be green at the tip**. A few intermediate commits can't
  `import pikaraoke.app` in isolation (the signature/call-site split spans
  commits) — only the **tip** must boot, not every intermediate (see Building
  each commit → "Expected weirdness").
- **Review — fix the bug (bug-fix-first).** Finding and fixing genuine
  correctness/robustness bugs is the priority, so **every genuine bug gets
  fixed**, folded into the commit that owns its concern. Divergence from
  `joint-alignment-dp` is *expected*, not exceptional: record each fix as a
  `Review-fix:` trailer in that commit's body for **traceability only** — no
  per-case approval needed. Most findings live in jad's own end-state design
  (most commits *restore* jad code); fix those too, by default. A `Review-fix`
  corrects the *original branch's* code in place.
  **Where a fix lands (anti-clobber).** Place it in the commit that **owns the
  concern** of the fixed lines (via the split map + per-file references), not
  mechanically the last commit. Move it later only for a real **clobber risk** —
  a *later* commit re-materializes the *same* lines, either (a) an **atomic
  shared hunk** two commits both stage (a constructor signature, the `DEFAULTS`
  dict) or (b) a later **whole-file re-pull** (`git checkout … -- <path>`). Then
  it rides with the **last** commit that materializes those lines (already where
  the shared hunk lands). When later commits stage only their own *different*
  hunks (the normal `git restore -p` split), the fix is safe in its
  concern-owner even if that's an earlier commit. If the bug is in code a later
  commit **removes or rewrites**, don't spend the fix on code about to be thrown
  away — track it as a **deferred-fix** (see the review gate) against the
  end-state owner and apply it when that commit is built.
- **Per-commit manual review gate (mandatory for every C-n).** Before a commit
  is finalized it gets a **strict manual review on three axes** over *its own
  diff* (while still unstaged/staged so findings fold in): **efficacy** (does the
  change do what the *Commit:*/*Review:* field intends, end-to-end),
  **efficiency** (no redundant work, dead code, duplicate globs, or needless
  IO/allocation; reuse existing helpers), and **robustness** (specific excepts,
  context-managed resources, no races/TOCTOU, globs that can't wipe the library,
  metacharacter/edge inputs handled). Fix every genuine finding by default and
  fold it into the owning commit per the **Review** rule (`Review-fix:` trailer);
  record the outcome in the execution-log cell. This gate is **mandatory on every
  commit, including pure deletion/move/rename ones** — there it is the *primary*
  gate (the automated pass below is tiered off it). Most findings live in jad's
  **end-state design** (most commits *restore* jad code), and bug-fix-first fixes
  those too — no per-case approval. Surface a finding to the user only when it's a
  genuine **judgment call on whether it's a bug at all** (intentional design vs.
  defect), not to ask permission for a clear fix.
  **A finding left unfixed falls into one of two honest buckets** — record which,
  with the reason, in the cell:
  - **deferred-fix** — a real bug that *will* be fixed, but at a later commit
    that owns or rewrites the code (a tracked must-do, resolved when that commit
    is built). Not a "maybe."
  - **not-a-bug** — intentional end-state design, or correct-at-tip: an
    intermediate-window artifact that resolves at a later commit (e.g. C16's
    `k.temp_dir`/`k.stop()` `AttributeError`, which jad wires at C18). Only this
    bucket is genuinely left alone.
- **Automated `/code-review` pass (per-commit, run from the `next` worktree).**
  `/code-review` diffs the harness cwd, so running Claude Code **from the
  `../pk-next` worktree** — where the reconstruction commits live — lets it
  target each commit's diff directly; the main-repo-cwd limitation that forced
  batching is gone. **Tiered by commit kind (refined 2026-06-03, from C16 on):**
  run the full `/code-review` pass on commits that **add or rewrite logic**
  (controllers, app wiring, socket handlers, anything with new conditionals or
  state) — there the finder breadth earns its keep; **skip it on pure
  deletion / move / rename** commits, where the three-axis manual gate + the
  commit's tests already backstop and the finder pass has no new logic to find
  (it only burns context). The manual gate runs on *every* commit regardless.
  Fold any findings back into the owning commit (`Review-fix:` via
  fixup/autosquash, or amend before the next commit) and note the outcome in the
  cell. (C0–C10 were built under the earlier **batched** policy — phase
  boundaries + the substantive commits, e.g. C8 — from the main repo before the
  cwd switch; C11–C14 each ran their own pass; that history stands, and C6's
  cell records the one pass that couldn't run then.)
- **Cruft:** dropped from the new branch entirely — `QWEN.md`, `mockup/`,
  and all WIP/scratch docs under `plans/` (including this file's siblings and
  `plans/joint-alignment-dp.md`, the matcher's design doc — it documents the
  α-sweep and the superseded repair line, not current code). Final tree is
  leaner than `joint-alignment-dp`.
- **Fidelity scope:** the branch should represent *current* functionality, so
  reconstruction also (a) purges transition-era orphaned assets the branch left
  behind, (b) corrects user-facing docs that describe removed features, (c) adds
  focused tests for untested new core logic, and (d) fixes the bugs review finds
  (bug-fix-first). All of these deliberately diverge from a literal jad
  reproduction and are called out as `Review-fix:` / new-test items on the
  relevant commits. **Bounded to bugs** — opportunistic cruft cleanup is fine
  when already in a file, but correctness, not open-ended restyling, is the
  mission.
- **Status:** the reconstruction is in flight on `next` (worktree `../pk-next`).
  Live progress is the execution-log ledger above; carry-forward items are in
  Standing deviations.

## Building each commit

Work in a throwaway worktree so `master` and `joint-alignment-dp` stay untouched
— nothing here touches the source, so you cannot lose it by experimenting:

```bash
git worktree add ../pk-next -b next master
cd ../pk-next
```

Branch name is **`next`** — a short-lived integration branch renamed to `master`
once reviewed and verified (it becomes the new mainline). Each commit pulls its
end-state content from `joint-alignment-dp` — whole file, a partial-file `-p`
split, or `git rm` — per the per-commit loop below. Historical bug-fixes are
absorbed automatically (jad's content already contains them); Review-fixes fold
into the owning commit (Decisions → Feature-aligned commits / Review).

### Vocabulary

For interactive staging (`git restore -p` / `git add -p`):

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

For review routing (Decisions → Review / review gate):

- **Review-fix** — a deliberate divergence from jad that fixes a real bug,
  folded into the owning commit and recorded as a `Review-fix:` trailer.
- **deferred-fix** — a real bug whose fix is tracked to land at a *later* commit
  that owns or rewrites the code; a must-do, not a maybe.
- **not-a-bug** — a finding left alone: intentional end-state design, or an
  intermediate-window artifact that's correct-at-tip.
- **tip** — either the current `next` HEAD (the latest built commit) or the
  *eventual* final branch tip, by context; "green/equal at the tip" means the
  latter, "correct-at-tip" the former.

### The per-commit loop — do this for every C-n

Use the project's conda env for every `python`/`pytest`/`pre-commit` call —
either `conda activate pik` first, or prefix with
`/home/ken/miniconda3/envs/pik/bin/`. Bare `pytest` will hit missing deps.
(On Windows, run these under `uv` instead — see *Dev environments* below.)

```bash
# 1. Bring the end-state content for this commit's files into the worktree.
git restore --source=joint-alignment-dp --staged --worktree -- <whole-file>   # whole file: stages it directly
#    …or, for a file shared across commits, pull only this commit's hunks:
git restore --source=joint-alignment-dp -p -- <shared-file>                   # y/n/s/e per hunk (updates worktree only)
git add -- <shared-file>                                                 # then stage what you kept

# 2. Sanity-check it's not half-wired before committing:
python -m py_compile $(git diff --cached --name-only -- '*.py')          # syntax
python -c "import pikaraoke.app"                                         # import smoke
git diff --cached --stat                                                 # eyeball: only the files/lines you intend

# 3. Run THIS commit's *Auto-test* line.

# 4. Manual review gate (mandatory — see Decisions → per-commit manual review gate):
#    strict review of THIS commit's diff for efficacy / efficiency / robustness,
#    satisfying the commit's *Review:* field. Fix EVERY genuine finding by
#    default and fold it into the commit that OWNS the fixed lines (anti-clobber
#    rule, Decisions → Review) — not blindly the last commit; never a follow-up
#    fix commit. Record the outcome (and any deferred-fix / not-a-bug) in the cell.
#    Then, IF this commit adds or rewrites logic, run the automated /code-review
#    pass on THIS commit too (tiered from C16 on — skip it for pure
#    deletion/move/rename, where the manual gate + tests are the gate; see
#    Decisions). Claude Code runs from the ../pk-next worktree so the pass
#    targets this commit's diff. Fold its findings the same way: amend before
#    step 5, or fixup/autosquash right after.
git add -- <changed-files>                                               # re-stage any review-fixes

# 5. Commit with the title + body from the *Commit:* field (subject, blank line, body):
git commit -m "feat(mpv): add MpvController for libmpv playback" \
           -m "libmpv-backed player — window, OSD, volume, pitch, pause."

# 6. Tick the file(s) off /tmp/recommit-manifest.txt.
```

Run `pre-commit run --config code_quality/.pre-commit-config.yaml --files <changed>`
before step 5 if you want each commit lint-clean; if Black/isort reformats,
re-stage and commit (content equals the tip, so changes should be tiny).

### Interactive staging keys (`git restore -p` / `git add -p`)

`y` stage this hunk · `n` skip it (leave for later) · `s` split into smaller
hunks (try this before `e`) · `e` edit the hunk by hand · `q` quit · `?` help.

### Worked example — `e`-extracting one line

*(Illustrative mechanics only — no live split needs this now that C-CLK is
dissolved; kept as a reference for the `e` technique.)* Say you're staging a
`DEFAULTS` change but want to hold one newly-added line back for a later commit.
`s` won't separate adjacent added lines, so press `e`. Git opens the hunk:

```
         "normalize_audio": False,
+        "hide_now_playing_overlay": False,
+        "some_other_key": False,
+        "subtitle_delay": 0,
```

**Rule:** to *not* stage an added (`+`) line, delete that whole line from the
buffer. (To *not* stage a removed `-` line, change its leading `-` to a space.)
Delete the `+        "some_other_key": False,` line, save, close. The commit now
omits it; the line stays in the working tree for a later commit. Verify with
`git diff --cached -- <file>` (shouldn't mention the held-back key) and
`git diff -- …` (should still show it, unstaged).

### Is the reconstruction tracking jad?

Two diff-vs-jad checks — but under bug-fix-first **divergence is expected**, so
these are *review surfaces* (expected vs. unexpected deltas), not missed-hunk
alarms:

- *Per file:* after the last commit that touches a file,
  `git diff joint-alignment-dp -- <file>` should show **only that file's recorded
  Review-fixes** (empty if it has none). Anything else is a missed hunk — stage
  it into the right commit (`--amend` if it's the one you just made).
- *Whole tree* (after the final commit):
  ```bash
  git diff joint-alignment-dp -- . ':!QWEN.md' ':!mockup/**' ':!plans/**'
  ```
  Only intentionally-dropped cruft and the deliberate Review-fixes recorded in
  the ledger should show. Reconcile every delta against those records; an
  unrecorded one is either a missed hunk or an unlogged fix.

### Expected weirdness — don't panic

- **`ImportError` mid-reconstruction** → you committed a file before a module
  it imports exists. That import belongs in a later commit; `e`-extract it out.
- **App boot gap C17→C32 — now CLOSED at `18f1225`** (app-boot fix, user
  decision to restore per-commit runnability). Originally the `Karaoke(...)`
  signature (C18) and its call site (C32) changed in different commits, leaving
  the app un-bootable C17→C32. `18f1225` pulls the call-site + ADMIN_PASSWORD
  forward, so from there the app **boots and plays core karaoke** through all of
  Phase D (Phase D builds the pipeline in isolated new files that don't touch
  app boot). Still degraded until their owners: no stem/lyric processing
  (C-PROC/C32); `/info` 500s on renamed overlay/clock attrs (C38). The
  "only the **tip** must boot" invariant still holds as the floor — this just
  raises the actual floor much earlier.
- **A test errors on import of a not-yet-created module** → that test belongs
  to a later commit. Tests ride with their code — don't add a test before the
  code it exercises lands.
- **Whisper/stem tests are slow** → while iterating, deselect them
  (`pytest -k "not whisper and not stem"`); run the full suite only at the tip.

### Safety net (the worktree is disposable)

- Undo the last commit but keep the changes staged: `git reset --soft HEAD~1`.
- Throw away uncommitted edits to a file: `git checkout -- <file>`.
- Start the whole branch over: `git worktree remove ../pk-next` then re-add it.
- Nothing here touches `master` or `joint-alignment-dp`, so you cannot lose the
  source by experimenting.

### First-run costs (for the end-to-end smoke)

The first stem/whisper run **downloads model files (~GB)** and needs network,
disk, and a GPU for reasonable speed. Budget time for it; it's a one-time cost
per machine, not per song.

### Dev environments — Linux/conda vs Windows/uv (where to run each step)

This plan's commands are written for **Linux + the conda `pik` env** (the
`/home/ken/miniconda3/envs/pik/bin/...` prefix, bash). Two facts decide where
each step has to run:

- **No commit's *auto-test* needs a GPU.** C21/C22 mock the stem/whisper
  subprocess+IPC boundary, so every commit C0–C47 can be built, auto-tested,
  and reviewed on Linux/conda (home box *or* the CPU-only work VM). Committing
  and `pytest` never force the switch.
- **The switch is forced by *live verification* only.** The Verify items that
  actually run a model at GPU speed are **C32** (processing auto-starts on a
  real download), **C-PROC** (live processing page), **C26A's joint route**
  (via `--match-method joint`, C47), **C47** (backfill on a real song), and the
  **final end-to-end smoke**. Those need **Windows + uv** with the `cu124`
  index — the work VM's CPU is too slow. Every other commit's live Verify is
  deferred and marked "(at C-PROC)", so it costs nothing on Linux/conda.

**Setup-on-Windows milestone = C0.** C0 lands `pyproject`/`uv.lock`/
`.python-version` with the Windows `cu124` index, so the project first becomes
uv-installable on Windows *at C0*. From C0 onward you can dev on either
platform; the plan's Linux/conda commands then need only **sporadic, mechanical**
translation depending on where you are — e.g. on Windows drop the conda-path
prefix and use `uv run python -m pytest` / PowerShell paths, and the `cu124`
index supplies CUDA torch automatically. The commit *content* never changes by
platform; only the invocation does.

**Practical flow.** Build, auto-test, and review the whole reconstruction
(C0–C47) on Linux/conda; batch the five GPU verification points above into one
Windows + uv session.

## Phase 0 — Pre-rebase prep (do before branching)

The point of this phase is to clean and validate the *source* tree first,
so reconstruction inherits a clean target instead of re-committing code
that review would delete. Verified findings (2026-05-21) are noted inline.

1. **Green baseline on the source tip.** Reconstruction targets the end
   state, so confirm it is actually green before trusting it:
   ```bash
   git checkout joint-alignment-dp
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
   pre-commit run --config code_quality/.pre-commit-config.yaml --all-files   # pycln (unused imports) + pylint already configured
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
   git diff --name-status master...joint-alignment-dp > /tmp/recommit-manifest.txt
   ```
5. **Read the full diff once, end to end**, before slicing — with 220 files
   it's the only way to catch cross-file couplings the per-file plan can't
   see (e.g. a template depending on a route field):
   ```bash
   git diff master...joint-alignment-dp > /tmp/full.diff
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
| `args.py` | MPV/overlay args + removal of streaming/buffer/avsync + logo + `--hide-clock` → C17 (clock no longer split out — see Standing deviations) |
| `tests/conftest.py` | shared mock fixtures, split across the features they back: drop `MockPlaybackController.now_playing_url`/`now_playing_subtitle_url` → C16/C18 (streaming removal); add `restart`/`set_pitch`/`set_subtitle_delay`/`broadcast_position` + `mpv_controller` → C18/C35; add `subtitle_delay`/`vocal_volume`/`temp_dir` → C35; add `processing_manager` → C32. Each hunk rides with the commit whose behavior its test exercises (per the test-cleanup note below). |
| `pipeline/stages/lyric_align.py` | base lyric-align/fetch stage + the SRT/Genius cleanup loader (`clean_srt_line` import, `_load_lyrics` rewrite) → C26; the joint route (`joint_match` import, `use_joint` branch, `_run_joint`, joint capture plumbing) → C26A. `test_lyric_align.py` splits the same way (base/cleanup tests → C26, three joint tests → C26A). |

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
  …) → C17; `hide_clock` param → **C18** (with the signature hand-split);
  `temp_dir` → C2; `genius_token`, `blocked_processing_words` → C32;
  `subtitle_delay`/`audio_delay`/`vocal_volume` → C35; `admin_password` → C38.
- class attrs `~L61–78` — `pipeline_tracker` → C32; `_volume` → C35; drop
  `default_bg_music_path`/`default_bg_video_path`/`screensaver_timeout` → C17;
  `show_splash_clock`→`hide_clock` attr → **C18**.
- docstring `~L120–150` — mirror the signature splits.

*Cleanly separable method/body hunks:*

- **C18 (mpv):** mpv init block `~L191` (`MpvController()`, `PlaybackController(mpv=…)`,
  `_on_song_end`, `set_callbacks`, `mpv_controller.start`, `set_system_volume`);
  `get_url` simplification `~L406`; `stop()` `self.mpv_controller.quit()` `~L577`;
  `run()` `is_running` guard + "started at" log `~L631`; `broadcast_position`
  - remove `log_output()` `~L647–674`; datefmt `~L139`.
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
  - `refresh_overlays`; `broadcast_position`; `seek`; `restart`; `set_pitch`.
- **C35 (live setters):** `set_subtitle_delay`, `set_sub_mode`, `set_vocal_volume`.

### `app.py`

- **C16:** drop `gevent` (`monkey.patch_all`, `WSGIServer`, `spawn`),
  `async_mode="threading"`, `_NoGetFilter`, drop `Browser`/`delete_tmp_dir`/
  `background_music_bp`/`stream_bp`/`splash_bp` imports + blueprint lists,
  browser-launch block removal in `main()`, `socketio.run(...)` +
  `Thread(target=k.run)` + temp cleanup `finally`.
- **C32:** ~~the `Karaoke(...)` instantiation kwargs in `main()`~~ **DONE — pulled
  forward to `18f1225`** (app-boot fix). The call-site now matches the C18
  signature (passes only surviving kwargs; rest hydrate from DEFAULTS); C32 no
  longer touches app.py's call-site.
- **C-PROC:** add `processing_bp` import+registration; replace `_broadcast_in_context`
  download wiring with `_pipeline_changed` → `k.pipeline_tracker._on_change`.
- **C38:** ~~`app.config["ADMIN_PASSWORD"] = k.admin_password or None`~~ **DONE —
  pulled forward to `18f1225`** (was required for boot once C17 dropped
  `--admin-password`). C38's remaining app.py work: none; its info.py/info.html
  admin+overlay reads still ride with C38.

### `preference_manager.py`

- **C17:** `DEFAULTS` hunk `~L28` (drop `complete_transcode_before_play`,
  `buffer_size`, `screensaver_timeout`, `disable_bg_*`, `bg_music_volume`,
  `disable_score`, `cdg_pixel_scaling`, `avsync`, `*_score_phrases`,
  `show_splash_clock`; `hide_overlay`→`hide_now_playing_overlay`; **and** the new
  keys `subtitle_delay`/`audio_delay`/`vocal_volume`/`temp_dir`/`hide_clock`/
  `blocked_processing_words`/`admin_password`/`genius_token`/`audio_device` — they
  ride along whole (declaring a default early is harmless; no `e`-extract needed
  now that the clock isn't split out). `get()` signature reformat is cosmetic.
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
| feat+fix loudnorm offset (DB→playback) | **C7** (db column + accessors) + **C14** (playback filter + song_manager forwarders) | spans (db inseparable from `pipeline_state` at C7 — see Standing deviations) |
| Invert clock → `hide_clock` | distributed: render **C12**, arg+DEFAULTS **C17**, ctor/tick **C18**, toggle UI **C38** (route + template — folded) | spans (C-CLK dissolved — see Standing deviations) |
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
| Fix pages stacking scripts | C40 (spa-navigation.js) + C41–C42 & C-PROC (per page) | spans (shared + per-page) |
| Refine global temp folder | C2 (helper) + usage in C5/C14/C18/C28/C32 | spans (cross-cutting plumbing) |
| Filter logs · reduce clutter · simplify HTTP filter | C16 (app filter) + C28 (mgr) + C21 (workers) | spans (per-emitter) |
| `fix(scripts)` resolve lyrics in-CLI | C47 (script) + C20 (load_vocal touch) | spans |
| `fix(joint-match)` monotonic DP + bisect; corpus-tune α=2 | C26A (matcher fns) + C19 (`joint_alpha=2.0`) | spans (code/config) |
| `fix(joint-match)` gate on lexical overlap | C26A (`_alpha_weight`) | single |
| `feat(lyric-clean)` differentiated SRT/Genius cleanup, keep parens | C23 (genius_lyrics) + C25 (tiling docstring) + C26 (loader) | spans (per-source) |

The **joint matcher** is itself a feature spanning C19 (config knobs) + C22
(whisper `refine=False` + capture fields) + **C26A** (the new matcher module
*and* its opt-in `lyric_align` route) + C47 (`--match-method joint`). The matcher
module and its stage route are kept together in C26A (one vertical feature); the
inert touchpoints in shared files ride with those files' commits (C19/C22). Like
the other **spans** rows, no commit fixes an earlier one: each carries its file's
end-state and the route works once C26A lands. It is opt-in (default
`match_method` stays `auto`), so every pre-existing matcher test stays green at
each step. Flipping the default to `joint` and retiring walk/tiling was *not* in
the source diff (`master..joint-alignment-dp` keeps all three) and is therefore
not in scope.

Two cleanup notes:

- **"Test fixes" / "Test update after removal"** are *not* commits — each
  test change rides with the module commit whose behavior it exercises (tests
  and code move together — and CLAUDE.md's "delete old tests when superseded"
  is honored in the same commit). Note the **module-less test edits**:
  `tests/unit/test_karaoke_utils.py` drops two `now_playing_url` reset
  assertions (its `karaoke_utils`/playback module is otherwise unchanged) — that
  hunk rides with the streaming-removal / now-playing rework (**C16/C18**);
  `tests/unit/test_song_list.py` only drops "(CDG format)" from a docstring
  (the `song_list` module is unchanged) — it rides with the **CDG-removal**
  hunks (C16 call-site / C17 prefs). `tests/conftest.py` is shared and splits
  per the split-map row above.
- **"Fixes after removal"** (splash/score teardown follow-ups) dissolve into
  the removal commits C15/C16 and the home-page commit C41 — there is no
  post-removal cleanup commit.

Where a row says **spans**, confirm during execution that each touched commit
carries only its layer's hunks and the feature works once the *last* of its
commits lands — that is the per-commit-relevant-tests / green-at-tip contract,
not a deferred fix.

______________________________________________________________________

## Phase A — Hygiene & foundations (no behavior coupling)

C0–C3 — built + verified 2026-06-01. Per-commit detail is in the `next` commit messages (`git show <sha>`); status + pending items are in the execution-log ledger above, carry-forward items in Standing deviations. Specs trimmed (lean-ledger pass 2026-06-03).

______________________________________________________________________

## Phase B — Data layer: download / library / DB

C4–C8 + C10 — built + verified (C4/C7 2026-06-01; C5/C5A/C6/C8/C10 2026-06-02); detail in commit messages, carry-forward in Standing deviations. **C9 remains in flight** — build done, stem-rename live-verify pending Phase D stems (spec kept below). Specs trimmed (lean-ledger pass 2026-06-03).

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
  - \[ \] rename a song — its accompaniment track renames too
  - \[ \] delete a song with brackets/special chars in the name — only that song goes

______________________________________________________________________

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
  - \[ \] (live behavior verified at C18 once wired)

**C12 — Overlay manager**

- *Commit:* `feat(overlay): add OverlayManager for now-playing/up-next OSD`
  > Renders now-playing, up-next, and clock OSD overlays with a TV-readable
  > palette.
- `lib/overlay_manager.py` (now-playing/up-next overlays incl. `QueuedSong`,
  **plus the clock OSD render — shipped whole**) +
  `tests/unit/test_overlay_manager.py`. **C-CLK dissolved (see Standing
  deviations):** the clock render lands here, not in a separate vertical commit;
  the `hide_clock` flag/pref/ctor touchpoints ride with C17/C18.
- *Review:* TV-readability palette.
- *Auto-test:* `pytest tests/unit/test_overlay_manager.py`
- *Verify:*
  - \[ \] (live behavior verified at C18 once wired)

**C13 — ffmpeg simplification → RELOCATED to C18A (after C18).**
Dropping the three ffmpeg helpers at this slot would break `import pikaraoke`
for C14–C17; the "delete old stack" work belongs after C18 clears the last
consumer. Full rationale in Standing deviations; build spec under **C18A** below.

**C14 — playback_controller on MPV + loudnorm offset**

- *Commit:* `feat(playback): drive playback via MPV, apply loudnorm offset`
  > Migrate PlaybackController onto MpvController; play/pause/seek/skip,
  > companion-track + subtitle resolution, overlay state. Folds the loudnorm
  > feature whole: DB accessors + apply-as-filter + graceful read-failure.
- `lib/playback_controller.py` (core migration — see Per-file refs) +
  `tests/unit/test_playback_controller.py`.
- **Loudnorm feature (folded here, not smeared):** `playback_controller`'s
  `get_loudnorm_offset` param + applying the offset as an MPV filter + the
  DB-read exception handling (absorbs both `feat: wire loudnorm` and `fix: loudnorm DB read exception handling`); plus the `get/set_loudnorm_offset`
  forwarders in `lib/song_manager.py`. The `karaoke_database.py` column + get/set
  shipped in **C7** (inseparable from `pipeline_state` — see Standing
  deviations); **C14 does not touch it**. The pipeline *writes* the offset later
  via the loudnorm_analyze stage (C20), which consumes these.
- *Review:* singer playback controls work. Loudnorm read failures degrade
  gracefully (no playback crash).
- *Auto-test:* `pytest tests/unit/test_playback_controller.py`
- *Verify:*
  - \[ \] (live behavior verified at C18; loudnorm audible after a song is processed, C20+)

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
  - \[ \] app boots; visiting `/splash` or `/stream` 404s; no console errors on the remaining pages

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
  - \[ \] app starts and serves pages; real-time updates (queue change) still push to the browser
  - \[ \] Ctrl-C shuts down cleanly

**C17 — args + preference renames for overlays**

- *Commit:* `feat(args): rename overlay flags, drop streaming/buffer/avsync`
  > Drop `--streaming-format`/`--buffer-size`/`--avsync`; rename
  > `--hide-overlay`→`--hide-now-playing-overlay`; add `--logo` and
  > `--hide-clock`. Prefs `DEFAULTS` updated to match.
- `args.py`: remove `--streaming-format`, `--buffer-size`, `--avsync`; rename
  `--hide-overlay`→`--hide-now-playing-overlay`; add `--logo` and `--hide-clock`
  (the clock arg rides here now that C-CLK is dissolved — see Standing deviations).
- `preference_manager.py`: `DEFAULTS` hunk committed **whole** here (including
  the `hide_clock` key — no `e`-extract needed now); renames + removals + the
  other new keys ride along — see Per-file refs.
  `tests/unit/test_preference_manager.py` rename hunks.
- Note: karaoke.py's matching signature removals/renames are *not* here —
  they live in C18's hand-split (the signature is one atomic hunk; the
  `hide_clock` param rides there too).
- *Review:* every reader of `hide_overlay`/`streaming_format` updated (grep).
- *Auto-test:* `pytest tests/unit/test_preference_manager.py tests/unit/test_preference_routes.py`
- *Verify:*
  - \[ \] `pikaraoke --help` lists `--hide-now-playing-overlay`/`--logo`, not the removed flags

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
  - \[ \] start pikaraoke, queue a song — it plays in the MPV window with audio
  - \[ \] now-playing + up-next overlays show; pause/skip/restart and ±volume work
  - \[ \] transpose changes pitch live without restarting the song

**C18A — ffmpeg simplification (relocated from C13)**

- *Commit:* `refactor(ffmpeg): drop HLS/transcode-streaming helpers`
  > Remove streaming/transcode helpers obsoleted by MPV; keep transpose +
  > version detection.
- `lib/ffmpeg.py` (drop `build_ffmpeg_cmd`, `get_media_duration`,
  `supports_hardware_h264_encoding`, and the `ffmpeg`/`platform`/`logging`/
  `FileResolver` imports; keep `get_ffmpeg_version`, `is_transpose_enabled`,
  `is_ffmpeg_installed`) + **reduce** `tests/unit/test_ffmpeg.py` to jad's end
  state (drop the `get_media_duration` + `supports_hardware_h264_encoding` test
  classes/imports; keep the three surviving fns' coverage). NB: jad keeps this
  file — an earlier `git rm` note here was stale; built as a reconcile.
- *Why here, not C13:* landing the drop only after C18 (the last consumer)
  keeps every intermediate commit importable — full rationale in Standing
  deviations. ffmpeg.py is **single-touch** in the reconstruction, so any
  review-fix folds here with no clobber risk.
- *Review:* nothing in pipeline stages still imports removed ffmpeg helpers
  (cross-check before Phase D); end-state ffmpeg.py == `git diff joint-alignment-dp -- pikaraoke/lib/ffmpeg.py` empty.
- *Auto-test:* `python -c "import pikaraoke.app"` (now passes again — C18
  cleared the last consumer) + full unit suite collects clean.
- *Verify:*
  - \[ \] app boots; pitch/transpose controls still detect ffmpeg support

______________________________________________________________________

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
- *Joint-matcher knobs land here (config end-state).* `config.py` ships the
  three `match_method == "joint"` tunables in their final, corpus-tuned form
  (they're inert data until the joint route consumes them in C26A):
  - `match_method` gains a documented `"joint"` value (default stays `"auto"`).
  - `joint_alpha: float = 2.0` — weight on the align prior in the joint score
    (`score = transcribe_match + joint_alpha * align_agreement * alpha_weight`).
    Ships at the corpus-tuned **2.0**, not the design-prior 4.0 — the historical
    `fix(joint-match) … corpus-tune alpha=2` is absorbed into this final value
    (see Fix-absorption audit), never a later config bump.
  - `joint_margin_s: float = 0.3` — window/overlap time slack (reuses the prior
    repair-margin value).
- *New test:* these have no direct coverage. Add a small
  `test_pipeline_config.py` asserting the config defaults/validation and the
  `context` construction the stages rely on — cheap, pure-Python, and it
  pins the many tunables in `config.py` (including `joint_alpha`/`joint_margin_s`).
- *Auto-test:* `pytest -k "pipeline_config or context"`
- *Verify:*
  - \[ \] (no user-facing behavior; the joint route is exercised at C26A / C-PROC)

**C20 — ffmpeg stages**

- *Commit:* `feat(pipeline): add ffmpeg extract/transcode/loudnorm/load-vocal stages`
  > Audio extraction, transcode, loudnorm analysis, and vocal-load stages
  > with quiet subprocess output and specific exception handling.
- `stages/_ffmpeg_helpers.py`, `ffmpeg_extract.py`, `ffmpeg_transcode.py`,
  `loudnorm_analyze.py`, `load_vocal.py`.
- *Review:* reduced subprocess verbosity; specific exception handling.
- *Auto-test:* targeted stage tests if present, else import smoke.
- *Verify:*
  - \[ \] (exercised at C-PROC — processed audio is normalized)

**C21 — Stem separation (worker + IPC)**

- *Commit:* `feat(pipeline): add out-of-process stem-separation worker`
  > Melband-Roformer separation in an isolated subprocess with IPC, OOM-exit
  >
  > - auto-restart, and a cancel hook (absorbs those robustness fixes).
- `pipeline/workers/__init__.py`, `workers/_ipc.py`, `workers/stem_worker.py`,
  `stages/stem_separation.py`. Melband Roformer model + Rubberband settings.
- *Review:* OOM-exit-and-restart logic; cancel hook; subprocess isolation
  rationale documented.
- *Auto-test:* `pytest tests/unit/ -k stem` (mock subprocess/IPC).
- *Verify:*
  - \[ \] (at C-PROC) processing a song produces vocal + instrumental stems; cancel mid-run leaves no zombie process

**C22 — Whisper worker + alignment capture**

- *Commit:* `feat(pipeline): add out-of-process whisper alignment worker`
  > Faster-whisper transcription/alignment in a subprocess; clears GPU cache
  > after every run. `transcribe_words` takes an optional `refine` kwarg so
  > callers can skip the second whole-song refine pass. Ships the
  > out-of-process move in final, stable form.
- `workers/whisper_worker.py`, `lib/alignment_capture.py` +
  `tests/unit/test_whisper_worker.py`.
- *`refine=False` kwarg (worker end-state).* `transcribe_words` and the inner
  `_do_transcribe_words` gain a keyword-only `refine: bool = True`; when
  `False`, the `_refine_pass` is skipped (logs `"Skipping refine pass"`) and
  post-process/extract runs on the un-refined result. The worker dispatcher
  stays **backward-compatible**: it unpacks `("transcribe_words", path, *rest)`
  so the legacy 2-tuple (`refine=True` implicit) and the new 3-tuple both work.
  `refine=True` is still the default — only the joint route (C26A) passes
  `False`. The added `test_whisper_worker.py` cases cover both tuple forms and
  the skip-refine path.
- *`alignment_capture` joint fields (additive, no schema bump).* `build_bundle`
  gains two optional kwargs, `joint_stats: dict | None = None` and
  `transcribe_words: list[dict] | None = None`, emitted into the bundle dict.
  Schema stays **v4** (additions only); both are populated only on joint runs
  so a saved bundle can re-run the joint matcher offline at other α without
  paying for whisper again. Wired by the lyric-align stage in C26A.
- *Review:* GPU-cache clear after every run; the worker runs out-of-process
  in its final, stable form (the follow-up out-of-process corrections are
  absorbed here, not separate commits); the tuple dispatch handles the legacy
  arity without a version flag.
- *Auto-test:* `pytest tests/unit/test_whisper_worker.py`
- *Verify:*
  - \[ \] (at C-PROC) GPU memory returns to baseline between processed songs
  - \[ \] a legacy 2-tuple `transcribe_words` request still runs with refine on

**C23 — Genius lyrics integration**

- *Commit:* `feat(lyrics): add Genius search + lyric fetch + line cleanup`
  > GeniusClient search/select/fetch; shows all artists in results; narrowly
  > suppresses lyricsgenius INFO log noise. `genius_lyrics` ships the
  > differentiated per-line cleanup: `parse_lyric_lines` keeps paren
  > *contents* (sung backing vocals), and `normalize_lyric_line` /
  > `clean_srt_line` are the shared txt/SRT line cleaners.
- `lib/genius.py`, `lib/genius_lyrics.py` +
  `tests/unit/test_genius.py`, `test_genius_lyrics.py`.
- *Differentiated cleanup (genius_lyrics end-state).* This is the
  `feat(lyric-clean)` content, owned here because it lives in `genius_lyrics.py`
  (the SRT/tiling/stage touchpoints fold into C25/C26 — see Fix-absorption
  audit, "spans"):
  - `parse_lyric_lines` no longer strips paren *contents* from `align_text`;
    it removes only the `(`/`)` characters and keeps the words (corpus audit:
    Genius parens are almost always sung backing vocals / call-and-response,
    not stage directions — stripping them hid audible tokens from the matcher).
  - New `normalize_lyric_line` (source-agnostic): collapses 2-line wraps,
    strips HTML tags, `[stage directions]`, musical-note glyphs (`♪♫♬♩`),
    normalizes curly quotes. Does **not** touch parens.
  - New `clean_srt_line`: `normalize_lyric_line` + drop `(stage direction)`
    contents (SRT parens are non-lyric in the corpus, unlike Genius) +
    return `""` for letter-less lines so the SRT loader can drop them.
  - Lines with no letters after normalization are dropped in `parse_lyric_lines`
    too (kills the stray `(`/`)`/`]`/`'` fragments that became empty matcher
    lines). `_INLINE_PAREN_RE` is replaced by `_PAREN_CONTENT_RE`/
    `_BRACKET_CONTENT_RE`/`_HTML_TAG_RE`/`_MUSICAL_NOTE_RE`/`_HAS_LETTER_RE`.
- *Review:* lyricsgenius INFO-log suppression scoped narrowly; token handling;
  align_text keeps paren contents while display text keeps the brackets; SRT vs
  txt paren handling is intentionally different (asserted in the new tests).
- *Auto-test:* `pytest tests/unit/test_genius.py tests/unit/test_genius_lyrics.py`
- *Verify:*
  - \[ \] with a Genius token set, search returns multiple artists; logs aren't spammed with "Done."
  - \[ \] a Genius line like `"(I can't help) Falling in love"` aligns as `"I can't help Falling in love"` (parens kept); an SRT `"(gentle music)"` line is dropped

**C24 — Word alignment (two-pointer walk)** — *built `f023895`; see ledger row.*

- *Commit:* `feat(lyrics): add two-pointer walk word matcher`
  > Word-level alignment between fetched lyrics and transcript via a lockstep
  > two-pointer walk (no DP table, no fuzzy scoring). No diarization.
- `lib/word_alignment.py` + `tests/unit/test_word_alignment.py`.
  (Two-pointer walk matcher with gap interpolation; **no diarization**. The
  historical "Needleman–Wunsch" label was superseded — the jad end-state
  implements the walk, not an NW DP; subject corrected accordingly.)
- *Review:* confirm zero diarization references survive here or in callers.
- *Auto-test:* `pytest tests/unit/test_word_alignment.py`
- *Verify:*
  - \[ \] (unit-covered; exercised at C-PROC)

**C25 — Tiling matcher** — *built `f1370e8`; see ledger row.*

- *Commit:* `feat(lyrics): add tiling matcher for lyric/transcript alignment`
  > Raw matched-token scoring; keeps ad-lib parens inline.
- `lib/tiling_match.py` + `tests/unit/test_tiling_match.py`.
  (Raw matched-token scoring; inline ad-lib parens.)
- *Cleanup-feature touchpoint (end-state).* `match_words_to_lines_tiling_with_stats`'s
  paren-split docstring is reworded to match C23's change — it splits on the
  display `lines` because `align_lines` now has only the bracket *characters*
  removed (contents kept), not the contents stripped. Docstring-only; rides
  with the `feat(lyric-clean)` span (see Fix-absorption audit). C26A reuses this
  module's `find_candidates` / `find_anchor_candidates` / DP shape.
- *Auto-test:* `pytest tests/unit/test_tiling_match.py`
- *Verify:*
  - \[ \] (unit-covered; exercised at C-PROC)

**C26 — Lyric align & fetch stages + conversion** — *built `7238bd9`; see ledger row.*

- *Commit:* `feat(pipeline): add lyric-fetch + lyric-align stages`
  > Fetch (Genius / YouTube captions) and align lyrics into subtitles;
  > race-free subtitle resolution; default subtitle delay. Walk/auto/tiling
  > match methods; differentiated SRT/Genius line cleanup at load time. (The
  > opt-in `joint` route is split out to C26A.)
- `stages/lyric_align.py` (base + cleanup hunks only — **not** the joint route,
  see split map), `stages/lyrics_fetch.py` +
  `tests/unit/test_lyric_align.py` (base + cleanup tests),
  `test_lyrics_fetch.py`, `test_lyric_conversion.py`. YouTube-captions source
  option; race-free subtitle resolution; default subtitle delay.
- *Multi-concern file — `lyric_align.py` splits across two commits:* (a) the
  base lyric-align/fetch stage + (b) the cleanup-loader rewrite land here; (c)
  the joint route lands in **C26A**. Stage with `git restore -p`: take the
  `_load_lyrics`/base hunks and `n`-skip the `joint_match` import, the
  `use_joint` branch, `_run_joint`, and the `joint_stats`/`transcribe_words`
  capture params.
- *Cleanup loader (b — the `feat(lyric-clean)` span lands its stage piece
  here).* `_load_lyrics` now imports `clean_srt_line` from `genius_lyrics`
  (C23): the `.srt` branch runs each subtitle through `clean_srt_line` and
  drops letter-less results; the `.txt` branch's docstring documents that
  `align_lines` keeps paren contents. No more pass-through of raw SRT noise
  (notes, wraps, HTML, stage directions).
- *Review:* walk/auto/tiling behavior changes only via the cleaner inputs; no
  `joint_match` import here (that arrives with the route in C26A).
- *Auto-test:* `pytest tests/unit/ -k "lyric"`
- *Verify:*
  - \[ \] (at C-PROC) a processed song plays with time-synced subtitles
  - \[ \] an SRT source with `♪`, wraps, and `(stage direction)` lines yields clean subtitle lines

**C26A — Joint alignment DP matcher + opt-in stage route** — *built `702259f`; see ledger row.*

- *Commit:* `feat(lyrics): add joint alignment DP matcher + opt-in stage route`
  > Single-pass matcher that consumes align words + transcribe words + lyric
  > lines together, plus the `LyricAlignStage` route that uses it behind
  > `match_method == "joint"`. Per line it builds one align candidate (at forced
  > alignment's predicted span) and zero-or-more transcribe candidates (via
  > tiling's `find_candidates`/`find_anchor_candidates`); each scores
  > `transcribe_match + alpha * align_agreement * alpha_weight`, and an
  > interval-scheduling DP picks the highest-scoring monotonic, non-overlapping
  > subset. Per-word timings come from whichever source won each line; unplaced
  > lines are interpolated between bracketing neighbours so output is 1:1 with
  > the lyric lines. Opt-in — default `match_method` stays `auto`.
- New module `lib/joint_match.py` + `tests/unit/test_joint_match.py` (public
  API `match_words_to_lines_joint_with_stats(...)` and the thin
  `match_words_to_lines_joint(...)`; imports the candidate/DP machinery from
  `tiling_match`, C25).
- `stages/lyric_align.py` (joint-route hunks only — the other half of the
  C26 split): the `from pikaraoke.lib.joint_match import match_words_to_lines_joint_with_stats` import, the `use_joint` branch in
  `run()`, the `_run_joint` method (`align_check` → `refine_from_cached` →
  `transcribe_words(refine=False)` → `match_words_to_lines_joint_with_stats`
  with `joint_alpha`/`joint_margin_s` from config), and the capture-joint
  plumbing (`capture_joint_stats`/`capture_transcribe_words` locals + the
  `joint_stats`/`transcribe_words` params threaded into `build_bundle`, plus
  `joint_alpha` in `pipeline_decisions`). No escalation/gating layer — the DP
  arbitrates per line.
- `tests/unit/test_lyric_align.py` (the three joint tests, riding with the
  route): the three-call flow (refine=False on transcribe), align-timings on
  clean lines, and the Hakuna-shape route-to-transcribe case.
- *Ordering.* **After C25** (uses `tiling_match`) **and after C26** (adds the
  route to the `lyric_align.py` that C26 creates). The `joint_alpha`/
  `joint_margin_s` knobs it reads live in C19; the whisper `refine=False` kwarg
  and `build_bundle` joint fields it uses live in C22. Nothing between here and
  C-PROC needs it (the orchestrator C27 doesn't import it).
- *Fix absorption (no fix-of-earlier-commit).* Ships the matcher in its final,
  corpus-validated form; the two historical `fix(joint-match)` commits fold into
  the functions they touched, never replayed:
  - `_best_tiling_by_time` enforces **lyric-id monotonicity** (sorted by
    `(line_id, t0)`, O(M²)) in addition to time non-overlap — so chorus repeats
    / dialogue interludes can't make the DP place a later lyric at an earlier
    time (the Hakuna Matata failure). \[from `fix … monotonic DP`\]
  - `_alpha_weight` is a binary gate that zeroes the align bonus when transcribe
    heard substantial speech (≥2 words) in the window but **none of the lyric's
    tokens appear there** — gated on raw **set-intersection / lexical overlap**,
    not the edit-distance `find_candidates` score (which over-rejected
    mistranscribed-but-correct lines). \[from both fix commits\]
  - `_transcribe_match_and_count_in_window` uses `bisect_left` on start times
    (was `bisect_right - 1`, which over-included a word starting before the
    window). \[from `fix … monotonic DP`\]
  - The `joint_alpha=2.0` default lives in C19; the whisper `refine=False` kwarg
    and `build_bundle` joint fields live in C22.
- *Review:* the route is genuinely opt-in (walk/auto/tiling untouched, so the
  existing tests stay green); `refine=False` is passed only here; the DP
  respects forced alignment's lyric order; the gate keys on lexical overlap; no
  diarization; equal-score tie-break deterministically favours align.
- *Auto-test:* `pytest tests/unit/test_joint_match.py tests/unit/test_lyric_align.py`
- *Verify:*
  - \[ \] `pytest tests/unit/test_joint_match.py` green in isolation (matcher needs no stage)
  - \[ \] processing with `--match-method joint` (via C47) places lines; clean songs keep align timings, a misplaced long line routes to transcribe

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
  - \[ \] (at C-PROC) a video that's already a karaoke track is rejected, not reprocessed

**C28 — ProcessingManager**

- *Commit:* `feat(processing): add ProcessingManager job queue`
  > Owns the processing queue + worker lifecycle; routes thread-named logs to
  > the PTY; clears caches proactively (no lazy load).
- `lib/processing_manager.py` + `tests/unit/test_processing_manager.py`.
- *Review:* thread-name→PTY log routing; proactive cache clear (no lazy load).
- *Auto-test:* `pytest tests/unit/test_processing_manager.py`
- *Verify:*
  - \[ \] (at C-PROC) queueing two songs processes them one at a time

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
  - \[ \] (at C-PROC) removing a song mid-processing doesn't crash or leave a ghost row

**C30 — Process terminal (PTY)**

- *Commit:* `feat(processing): add PTY process terminal for live logs`
  > PTY-backed terminal + reader so subprocess output streams to the
  > processing page; timestamp format matches the worker subprocess (no date).
- `lib/process_terminal.py`, `lib/process_terminal_reader.py`. Timestamp
  format (no date) to match worker subprocess.
- *Auto-test:* `pytest tests/unit/ -k "terminal"` (or import smoke).
- *Verify:*
  - \[ \] (at C-PROC) live subprocess output streams into the processing page terminal

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
  kwarg rides with C18, matching the signature). Commit with karaoke.py's
  signature so the call matches (avoids a broken-boot window).
- **Deferred-fix (review, new — fix in this commit when wiring `temp_dir`):** once a non-empty `temp_dir` is
  resolved here, `build_ytdl_download_command` adds `--paths temp:{temp_dir}` so
  yt-dlp writes `.part`/merge intermediates under `temp_dir` — but
  `download_manager._cleanup_partial_downloads` globs only `download_path`, so a
  cancelled download orphans its partials in `temp_dir`. Make cleanup sweep
  `temp_dir` too (or pass it in). Dormant until this commit wires `temp_dir`
  (and cancel is wired at C-PROC).
- *Auto-test:* `pytest tests/unit/ -k "karaoke or processing"`
- *Verify:*
  - \[ \] download a non-karaoke song — processing starts automatically; temp artifacts land under the resolved temp dir
  - \[ \] app still boots and plays (no signature/call-site mismatch)

**C33 — → folded into C-PROC** (Processing page, Phase F)

- The `app.py` push wiring (`processing_bp` registration + `_pipeline_changed`
  → `k.pipeline_tracker._on_change`, `pipeline_updated` push replacing 1s
  polling) is part of the same vertical feature as the route and template, so
  it moves to C-PROC. (`socket_events.py` was fully handled in C16.)

______________________________________________________________________

## Phase E — Preferences, routes & misc behavior

> C34–C35 are the two halves of one feature — **live now-playing controls**
> (volume, subtitle delay, sub mode, vocal volume). The historical `Fix volume bug` and `Sub delay fixes` (which spanned karaoke/prefs/controller/info)
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
  - \[ \] while a song plays, change the default volume in preferences — the playing song's volume doesn't jump

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
  (admin/option-reorder + clock-toggle hunks → C38; `info.py` is a multi-feature
  file).
- *Review:* single source of truth for delay/volume state (no duplicated
  offsets); the live-override pref half (C34) and these setters agree.
- *Auto-test:* `pytest tests/unit/ -k "controller or playback"`
- *Verify:*
  - \[ \] during playback, the now-playing remote adjusts subtitle delay, sub mode, and (dual-stem) vocal volume live
  - \[ \] each control resets to its default on the next song

**C36 — Queue routes & socketio**

- *Commit:* `refactor(queue): update queue routes, drop download queue surface`
  > Queue REST/Socket.IO endpoints aligned to the new model; the separate
  > download-queue UI surface is removed.
- `routes/queue.py` + `tests/unit/test_queue_routes.py`,
  `test_queue_socketio.py`. Remove download queue from queue surface.
- *Auto-test:* `pytest tests/unit/test_queue_routes.py tests/unit/test_queue_socketio.py`
- *Verify:*
  - \[ \] add/remove/reorder from the queue page — updates push live to other open clients

**C37 — Search routes**

- *Commit:* `feat(search): update search routes`
  > Search endpoints + result shape for the reworked search page.
- `routes/search.py` + `tests/unit/test_search_routes.py`.
- *Auto-test:* `pytest tests/unit/test_search_routes.py`
- *Verify:*
  - \[ \] search returns results; preview + add-to-queue work from the search page

**C38 — Info / files / admin / controller routes**

- *Commit:* `feat(routes): admin password from prefs; info/files/controller updates`
  > Source `ADMIN_PASSWORD` from the preference/`Karaoke`, reorder info-page
  > options, misc files/controller updates; absorbs `Fix exit bug` (admin).
- `routes/info.py` (admin/option-reorder + `hide_clock` toggle-route hunks —
  the volume/subtitle-delay hunks went to C35), `routes/files.py`,
  `routes/admin.py` (`Fix exit bug` absorbed here), `routes/controller.py`.
  Admin-password behavior change; option reordering; the clock-toggle endpoint
  (clock no longer split out — see Standing deviations; the pref-save path rides
  with `routes/preferences.py`'s owner, C34).
- `app.py` (C38 portion): `app.config["ADMIN_PASSWORD"] = k.admin_password or None` (now sourced from the pref/`Karaoke`, not `args.admin_password`). The
  `admin_password` `__init__` param rides in karaoke.py's C32 signature pass;
  its DEFAULTS key landed in C17.
- *Review:* admin-password change does not weaken any existing auth gate.
- *Auto-test:* `pytest tests/unit/ -k "info or files or admin or controller"`
- *Verify:*
  - \[ \] set an admin password in prefs — admin actions require it; unset — they don't
  - \[ \] the "exit" admin action works without error

______________________________________________________________________

## Phase F — UI (templates / CSS / icons)

> Split per page so a template regression bisects to one screen. Each is
> verified manually (no unit coverage); ship behind the corresponding
> backend commit.

**C39 — Fontello update (clock icon)**

- *Commit:* `feat(ui): add clock icon to the fontello set`
  > Regenerated fontello config/css/fonts including the clock glyph used by
  > the clock overlay and info page.
- `static/fontello/*` (config, css, font binaries, demo).
- *Auto-test:* none (assets).
- *Verify:*
  - \[ \] icons render across pages; the new clock glyph displays where used

**C40 — Shared layout/CSS**

- *Commit:* `refactor(ui): shared base layout + single-bind SPA navigation`
  > Base template + custom CSS; SPA navigation binds each page's scripts once
  > (absorbs the script-stacking fix).
- `templates/base.html`, `static/custom.css`, `static/spa-navigation.js`,
  single-binding of page scripts on navigation (no stacking).
- *Auto-test:* none (templates).
- *Verify:*
  - \[ \] navigate between pages repeatedly — no duplicated handlers, no console errors, no stacked scripts

**C41 — Home page overhaul**

- *Commit:* `feat(ui): overhaul home / now-playing page`
  > Now-playing layout, ±volume buttons, tighter vertical spacing.
- `templates/home.html`. Now-playing tweaks, +/− buttons, vertical spacing.
- *Auto-test:* none (template).
- *Verify:*
  - \[ \] now-playing shows correct title/singer; ±volume buttons work; layout isn't cramped

**C42 — Queue page** — 🔨 built `521081e` 2026-06-09

- *Commit:* `feat(ui): rework queue page`
  > Queue page aligned to the new queue model + live updates.
- `templates/queue.html`.
- *Auto-test:* none (template).
- *Verify:*
  - \[ \] queue reflects current state; add/remove/reorder works and updates live

**C43 — DISSOLVED (search.html folded into C37)**
`templates/search.html` was folded into **C37** (`adc51e0`) on 2026-06-09:
C37's route rework changed the result tuple to 6 elements and 500'd `/search`
on any results page, so the matching template (+ render test) was moved back
into the same commit. search.html reached its jad end state there (results
loop unpacks the 6-tuple, preview modal with loading overlay, search tweaks).
Nothing remains for a separate C43 commit.

**C44 — DISSOLVED (info.html + files.html folded into C38)**
Both templates were folded into **C38** (`bda7ecb`) on 2026-06-09: C38's route
rework had shipped ahead of them and 500'd `/info` (`UndefinedError`) and
`/browse` (`TypeError`), so the matching templates (+ render tests) were moved
back into the same commit. info.html reached its jad end state there (clock-toggle
UI included — clock no longer split out, see Standing deviations), as did
files.html. Nothing remains for a separate C44 commit; the only open template
item is the files.html enqueue-JS reconcile, closed by `fix(enqueue)` `2b9b5c5` (was the **C42 watch**)
(cross-page, with search).

- *Auto-test:* none (template).
- *Verify:*
  - \[ \] info-page controls act on playback/prefs

**C-PROC — Processing page (routes + push + template), vertical**

- *Commit:* `feat(processing): processing page with server-driven actions + push updates`
  > Whole processing-UI feature as one slice: server-driven action endpoints,
  > Socket.IO `pipeline_updated` push (replaces 1s polling), and the
  > push-driven template with `fetchStatus` debounce + safe-remove. Absorbs
  > `Eliminate processing UI bug class` and `Fix tracker … debounce`.
  > *(absorbs former C31 + C33 + the processing.html frontend; runs here in
  > Phase F, after base layout C40, since it includes the template)*
- `routes/processing.py` + `tests/unit/test_processing_routes.py` (server-driven
  action endpoints).
- `app.py`: `processing_bp` registration + `_pipeline_changed` →
  `k.pipeline_tracker._on_change` (`pipeline_updated` push, replaces 1s polling).
- `templates/processing.html`: push-driven status, pending-state display,
  `fetchStatus` debounce, safe-remove markup.
- This is the whole **"processing UI" feature** as one vertical slice. The
  historical `Eliminate processing UI bug class` and `Fix tracker … debounce`
  absorb here in final form (the `pipeline_tracker` model's `_on_change` hook
  - remove-atomicity live in C29, its data layer).
- **Deferred-fix (apply when wiring cancel here):** (1) the C5-flagged
  `cancel_active_download` kill-vs-`active_url` TOCTOU + the killed-yt-dlp
  `download_error`/danger-toast suppression (set a cancelling flag); (2) **new:**
  `cancel_pending_download` adds the URL to `_cancelled_urls` *and* rebuilds the
  queue to drop the item — the worker never dequeues the removed item, so the
  `_cancelled_urls` entry leaks permanently and a later re-queue of the same URL
  is silently skipped. Drop the redundant `_cancelled_urls.add` for pending
  items (the queue rebuild already removes them); reserve the set for the
  in-flight case only.
- *Auto-test:* `pytest tests/unit/test_processing_routes.py`
- *Verify:*
  - \[ \] process a song — phases advance live on the page with no manual refresh
  - \[ \] pending songs show a pending state; cancel/remove during processing is safe (no ghost rows, no crash)
  - \[ \] open two clients — both update from the push

**C-CLK — DISSOLVED (clock distributed to its owning commits)**
The clock feature does **not** get a dedicated vertical commit (user decision
2026-06-03 — see Standing deviations). A standalone clock commit needed
`e`/`n`-exclusions from ~8 commits for marginal benefit; instead each touchpoint
ships with the file that owns it:

- clock OSD render + test → **C12** (`overlay_manager.py`, shipped whole — done)
- `--hide-clock` arg + `hide_clock` DEFAULTS line (+ test) → **C17**
- `hide_clock` param/attr + clock-tick wiring
  (`karaoke.py`/`playback_controller.py`) + `hide_clock=` in the `Karaoke(...)`
  call (`app.py`) → **C18** (with the overlay wiring)
- info-page toggle: route + template (`routes/info.py` + `templates/info.html`)
  → **C38** (folded together); the pref-save path rides with
  `routes/preferences.py`'s owner (C34)
- clock glyph → **C39** (fontello)

`Invert clock overlay preference from show_clock to hide_clock` is absorbed into
whichever commit owns each line (no replay); `--hide-now-playing-overlay` is a
*different* overlay (C17/C18). Verify the clock at the **final smoke**: the
info-page toggle shows/hides the OSD clock, and `--hide-clock` starts hidden.

______________________________________________________________________

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
  - \[ \] switch UI language — pages translate, no missing/garbled strings, no leftover splash/score text

**C47 — Backfill artifacts script**

- *Commit:* `feat(scripts): backfill stems/lyrics for existing library`
  > Standalone script to (re)generate stems/subtitles/loudnorm for songs
  > already in the library; resolves lyrics in-CLI so non-YouTube-ID songs
  > use Genius. `--match-method` forces the matcher for the run and
  > `--use-bundle-lyrics` reuses cleaned lyrics from saved alignment bundles.
- `scripts/backfill_artifacts.py`, `scripts/README.md`,
  `scripts/*lyrics*` resolve lyrics in-CLI (so non-YouTube-ID songs use Genius).
- *Matcher-comparison + offline-replay flags (script end-state).* Two args land
  in final form (the staged `--match-method walk|tiling` → then `joint` history
  collapses to one option list):
  - `--match-method {auto,walk,tiling,joint}` (default `None`) overrides
    `config.match_method` for the run, so matchers can be compared on one
    library without editing config. (`joint` only works once C19/C22/C26A
    are in; ordering already satisfies that.)
  - `--use-bundle-lyrics`: for a song missing karaoke/subtitles, if
    `<folder>/alignment_debug/<stem>.json` exists, reuse its cleaned
    `lyrics.align_lines` (write `<stem>.txt`, choice `("bundle", path)`) instead
    of an interactive Genius prompt; songs without a bundle still prompt. Lets
    the joint matcher be re-verified on a curated set without re-running Genius.
    `_load_lyrics`/`parse_lyric_lines` still run (idempotent on cleaned text).
- *Auto-test:* `python scripts/backfill_artifacts.py --help` (lists
  `--match-method`/`--use-bundle-lyrics`).
- *Verify:*
  - \[ \] run it on one existing song — stems/subtitles/loudnorm get produced; a non-YouTube-ID song resolves lyrics via Genius
  - \[ \] `--match-method joint` forces the joint matcher; `--use-bundle-lyrics` skips the Genius prompt for a song that has a saved bundle

______________________________________________________________________

## Final gate

```bash
/home/ken/miniconda3/envs/pik/bin/python -m pytest          # full suite green
pre-commit run --config code_quality/.pre-commit-config.yaml --all-files
git diff joint-alignment-dp -- . ':!QWEN.md' ':!mockup/**' ':!plans/**'  # only review-fixes show
```

**End-to-end smoke (not just unit-green).** The wiring commits (C18/C32/C-PROC)
are exactly what unit tests don't exercise, so run the real path once:
boot the app → search → download a song → process it (stem + whisper +
lyric align) → libmpv playback with now-playing/clock overlays and
subtitles → exercise queue + singer playback controls. This is the only
check that proves the integration seams actually connect.

Also exercise the **joint route** end-to-end (its stage → worker → matcher
seam — `transcribe_words(refine=False)` feeding the joint DP — is unit-mocked,
not run for real by the suite):
`python scripts/backfill_artifacts.py <song-folder> --match-method joint`
on a couple of reference songs (one clean, one Hakuna-shaped). Confirm
subtitles land 1:1 with the lyric lines and clean lines keep align timings.

Open the PR from `next` with a test plan mirroring the manual-verification
items in Phases C–F. Once reviewed and the end-to-end smoke passes, `next`
is renamed to `master` (the new mainline).

## Open items to confirm before executing

1. Any commits here that you'd rather **split further or merge**.

*Resolved:*

- **Branch name** = `next`, renamed to `master` once verified.
- **Heavy deps** stay **hard deps** — the model-dependent features are core,
  not optional. So `pyproject.toml` keeps `audio-separator[gpu]`/`torch`/
  `torchaudio`/`faster-whisper`/`stable-ts` as required (C0), with the Windows
  `cu124` uv index supplying CUDA wheels there. C21–C22 tests mock the
  subprocess/IPC boundary, so they run in CI without a GPU; only the GPU
  verification points (C32 / C-PROC / C26A-joint / C47) and the end-to-end
  smoke need real models + hardware.
- **Translations** regenerated, not carried (C46).
- **Dependencies + `requirements.txt`** tracked and consolidated into C0,
  reproducing `joint-alignment-dp@b7500370`. An optional CI sync-check between
  `requirements.txt` and pyproject is worth adding since both files are kept.
