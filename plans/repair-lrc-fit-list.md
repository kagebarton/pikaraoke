Model: Claude Sonnet 5.5 (executor, Phase 1). Author and judge: Claude Opus 5.5, 2026-11-26.

# Repair's LRCLIB timing list, scored by the fit

Branch `repair_lrc_fit_list` off `dev` at `efb91f2d`, worktree
`.claude/worktrees/repair_lrc_fit_list`.

**Status: Phase 1 built and ui-checked 2026-11-26 (`535c817e`, `5a7e397e`, `503090f1`); raw readings in the
Results log. Opus judged it 2026-11-26: passes, three fixes ruled (Results log, "Phase 1 rulings"). Next: Ken's
`/code-review`, whose fix pass also makes the three ruled fixes.**

## The problem

On Repair's LRCLIB timing, the line under each search result and the Check fit card both say
"matches N of M lines", but count different things:

- **The row** (`LibraryTools.lrclib_candidates`, via `/song_info/lrc_search`): how many of the
  song's current lyric lines (`current_lines`, the bundle's `lyrics.lines`) map by text to the
  match's lines (`lrclib.map_lines_to_cues`). M is the song's line count. Its "best fit" tag is
  `lrclib.select_candidate` (text plus length), the Genius route's rule.
- **Check fit** (`check_lrc_timing`, via `/song_info/lrc_fit`): how many of the match's own lines
  were found in the clip's heard words (`srt_slice_fit.fit_slice` over `heard_streams`, the
  transcriber's words and the YouTube auto-caption). M is the match's line count inside the clip.

Measured 2026-11-26 on 12 library songs with a `.lrc` on disk (scratch script, transcribe stream
only, not kept):

| Song | Row count | Check fit |
|---|---|---|
| #OutofOz - Defying Gravity (`EFbuID1QG0Y`) | 69/86 | refused, 43/76 |
| Beauty and the Beast (1991) - Belle (`otxTf5hZ0Yw`) | 49/122 | fits, 72/82 |
| Beauty and the Beast (1991) - Be Our Guest | 61/92 | fits, 68/79 |
| Bruno Mars - Just The Way You Are | 38/49 | fits, 53/54 |
| Beyond - 海闊天空 | 6/35 | refused, 5/31 |

One fit took 4-139 ms (median about 60 ms) on the VM.

Successful fits also show no lyric text, so a clean match can't be read before it is used.

## Decisions (Ken, 2026-11-26)

1. **Rows are scored by Check fit's own fit.** Each search result is fitted exactly as Check fit
   fits it (same streams, same clip length), and its row shows Check fit's count and verdict.
   Check fit stays, for the full card.
2. **"Best fit" is the download's pick.** The bar and pick order of `lrc_auto_pick` (the code
   download-time LRCLIB auto-timing runs) mark `best`, and the list comes in its order: passing
   records first in pick order, then the rest in LRCLIB's order. No passing record, no tag.
3. **Check fit drops the length limit** (`LRC_MAX_GAP_S`), as the download's bar did
   (`plans/lrclib-fit-pick.md` on `archive/lrclib_fit_pick`, "Two GATE M conditions are dropped").
   The "Use this match anyway" box and `allow_gap` go with it. Any fit with status `fits` may
   regenerate, as Movie subtitles already work. The length stays on the card as a plain line.
4. **"Preview selected timing" under the LRCLIB timing list**, as step 2 of the Genius route
   has it. It shows the picked match's lines with LRCLIB's own times, whatever its fit, before or
   after Check fit. No toggle inside each row.
5. **The Genius route's step 2 keeps its text count** and `select_candidate` tag: there the
   question is whether the match is the same lyrics, which the text count answers.
6. **A song with no heard words** shows "can't check" on every row and no best tag, as Check fit
   says today.
7. **At landing**, two `plans/open-issues.md` entries close: "Repair's LRCLIB list in the bar's
   order" and "Repair's LRCLIB search scores against the backing lines too" (the rows stop
   counting the song's lines, and `current_lines` goes).

### 8. What a fit says when the download's bar refuses it (Ken, 2026-11-26)

The download dropped the length limit because the bar's unclaimed-run check covers what it was
for: singing the match has no line for, such as a section the video adds. Repair's card today
does not show the bar at all, and with the length limit gone nothing would tell the admin about
such a section. A row could also read "fits" in green and not be "best" with no reason given.

**Ruled:** the card and the row follow `lrc_auto_pick.refusal(fit)` too. A fit the bar
passes reads as today. A fit the bar refuses gets the warning tone ("fits, check first" on the
row), the head "Fits, but read the warning first." and one warning line for the refusal:

| Refusal | Warning line |
|---|---|
| `speed` | today's "Speed adjusted by N%." line, shown and marked as a warning |
| `mistimed` | "%(num)d lines are heard far from their time." (`ngettext`) |
| `unclaimed` | "The clip has %(num)d words in a row that no line of this match has. The video may have a section this match lacks." |
| `shifted` | "%(num)d lines in a row are heard a few seconds off their time. The video may be a different cut here." |

Regenerate stays on for every `fits`: on Repair the admin is the check
(`plans/open-issues.md`, "An LRCLIB match the admin has checked becomes the song's timing").

Not chosen: no warning lines, the bar showing only as the best tag. Repair stays less strict
than the download on purpose; the warnings show what the download would have refused. Wording is
Ken's to amend at review.

## Checked against the code (`dev` `efb91f2d`)

- `lrc_search` (`routes/song_info.py`) is the only caller of `current_lines` and the LRCLIB
  timing list's only search. The Genius route's step 2 uses `lrclib_search` (GET and POST); both
  go through `_lrclib_results` and `lrclib_candidates`, which stay as they are.
- `check_lrc_timing` -> `_fit_lrc_timing` -> `_fit_to_clip` fits with
  `heard_streams(job.bundle, self._asr_on_disk(song))`. `fit_slice` fits each stream and keeps
  the better. `lrc_auto_pick.evaluate(records, words, clip_length)` fits `{TRANSCRIBE: words}`
  only; its callers are `lrc_auto_timing.check` and `scripts/lrc_fit_pick_probe.py:638`.
- `LRC_MAX_GAP_S` is read in `library_tools.py` (`_fit_lrc_timing`, docstrings) and
  `routes/song_info.py` (`_lrc_fit_card`, `_override_tip`). `allow_gap`: `repair`,
  `_lrc_repair_plan`, the `repair` route, the page's `#go` handler. `overridable`,
  `override_tip`, `lrcOverride`, `#lt-override`: card, page, tests.
- Movie subtitles gate Regenerate on `state.movieCard.status === 'fits'` and `_movie_repair_plan`
  refuses unless `fit.status == FITS`. LRCLIB timing gates on `viable || (overridable &&
  lrcOverride)`.
- The page's rows come from one builder, `matchOption(candidate, name, selected, currentLabel,
  showMapped, onPick)`, shared by step 2 and LRCLIB timing. `fitLine` colours the length by
  `fit_near`. The match on disk is `LRC_MATCH` (`_lrc_match`), merged in `lrcRows` with its search
  row when the search lists it (`mapped`, `sheet_lines`, `best`). It carries no lyric text.
- Step 2's preview (`#lrclib-preview-toggle`, `showTimingPreview`, `closePreview`) shows the
  picked search row's `syncedLyrics`. The Genius preview fetches lyrics and shares `closePreview`.
  The LRCLIB timing preview would be a third copy, so the two timing previews share one function.
- `SliceFit` carries `unclaimed_run`, `shift_run`, `mistimed` and `speed` for a fit with status
  `fits`, everything `refusal` reads.
- No song on the VM's library lacks heard words (every bundle has transcriber words or the song
  has an auto-caption), so decision 6 is checked by tests only.

## Phase 1: build (Sonnet)

Before each commit: the touched tests, pre-commit on the changed files, `git diff --cached`
read against this spec. Full suite after commit 3. New msgids stay English until the next catalog
regen (Ken); no catalog edits.

### Commit 1: Check fit follows the bar, not the length limit

`fix(repair): LRCLIB timing's Check fit drops the length limit for the download's bar`

- `LrcTimingCheck`: drop `viable` and `overridable`; add `refusal: str | None`, set to
  `lrc_auto_pick.refusal(fit)`. `gap_s` and `clip_s` stay, for the length line.
- Delete `LRC_MAX_GAP_S`. `_lrc_repair_plan` refuses unless `fit.status == FITS`, as
  `_movie_repair_plan` does. `allow_gap` goes from `repair`, `_lrc_repair_plan`, the `repair`
  route (body key and its 400) and the page.
- Card (`routes/song_info.py`): one function, `_lrc_verdict(check)`, decides the tone and head,
  so commit 2's row reads the same answer:
  - status not `fits`: as today (`_lrc_refusal_card`);
  - `fits`, bar passes, no flagged runs: good, "Fits. This match can time this song.";
  - `fits`, bar passes, flagged runs: bad, "Fits, but check these lines first.";
  - `fits`, bar refuses: per decision 8.
- The length line stays second, plain, never a warning; the `too_far` heads and the warning flag
  go. Drop `viable`, `overridable`, `override_tip` from the card; delete `_override_tip`.
- Page: delete `#lt-override`, its CSS (`.rp-override`, if nothing else uses it), `lrcOverride`
  and its handler, and `body.allow_gap`. Regenerate gates on
  `state.lrcCard.status === 'fits'`, as Movie subtitles does.
- Tests: delete the override, `allow_gap` and `LRC_MAX_GAP_S` tests (`test_library_tools.py`
  around lines 1012, 1405-1500, 1634-1696; `test_library_routes.py` around 2127-2163, 2721,
  2837-2852). Add: a fit with a 35 s gap regenerates with no override; each refusal's tone, head
  and warning line; Repair queues a `fits` whatever the gap and refuses anything else.

### Commit 2: rows scored with Check fit's fit

`fix(repair): LRCLIB timing's search scores each match with Check fit's own fit`

- `lrc_auto_pick.evaluate(records, streams, clip_length)`: `streams` in `heard_streams`' shape,
  passed to `fit_slice` as is. `lrc_auto_timing.check` passes `heard_streams({"transcribe_words":
  words}, None)`; the probe passes `{TRANSCRIBE: words}`. The download's behaviour is unchanged.
- `LibraryTools.lrc_timing_candidates(song_path, query) -> dict`: a video only (as
  `check_lrc_timing`), the job read once, clip length by `_clip_length`. Search and remember the
  records through one helper shared with `lrclib_candidates`, not a copy. Then
  `evaluate(records, heard_streams(bundle, asr), length)`. Each entry becomes an `LrcTimingCheck`
  through the builder `_fit_lrc_timing` uses: split it into the fit and the check built from a
  fit, so both paths make the same check. Return the candidates in `evaluate`'s order, each with
  `record_meta`, `duration_diff_s`, `best` (the first entry, if it passes), `current`,
  `syncedLyrics` and its check. `lrc_auto_pick`'s refusal and `LrcTimingCheck.refusal` must agree.
- Delete `current_lines` and its tests.
- `lrc_search` route: calls `lrc_timing_candidates`. A `RegenError` returns 400, LRCLIB
  unreachable returns 502, as the Genius routes do. Each row gets `fit` (the length, with
  `fit_near` None, so it is not coloured: length is no rule here) and `verdict`:
  `{"tone", "text"}`, with the tone from `_lrc_verdict` and the text a short label plus " · "
  and the card's "matches %(n)s of %(m)s lines" when the fit has lines. Labels: good "fits",
  bad with status `fits` "fits, check first", other bad "doesn't fit", info "can't check".
  `_lrc_match` (the disk row) also sends `fit_near` None.
- Page: `matchOption` takes the row's score element from its caller in place of `showMapped`.
  Step 2 passes the text count (same look as today); LRCLIB timing passes the verdict, coloured
  by tone (good `rp-good`, bad `rp-bad`, info `rp-muted`). `lrcRows` merges the disk row's
  `verdict` and `best` from its search row in place of `mapped` and `sheet_lines`. Rows keep the
  server's order.
- Tests: rows in bar order with `best` on the first passing record; no `best` when none passes;
  no heard words gives every row "can't check" and no `best`; a row's verdict equals
  `check_lrc_timing`'s card tone for the same record and song; the auto-caption stream is used;
  step 2's rows unchanged.

### Commit 3: Preview selected timing on LRCLIB timing

`feat(repair): preview the picked LRCLIB timing match's lyrics`

- `#lt-preview-toggle` ("Preview selected timing", `rp-link`) and `#lt-preview`
  (`rp-preview`) directly under `#lt-matches`. Off when nothing is picked; shows the picked row's
  `syncedLyrics`; follows the pick while open; closes when the pick goes.
- `_lrc_match` adds the disk match's text (`lrclib.read_song_lrc(song).text`), read once at
  render.
- Step 2's preview and this one share one function. The Genius preview keeps its fetch.
- Tests: the toggle's place and initial state, the disk row carries its text, the shared preview
  function serves both lists.

### ui-check on the VM (Sonnet)

Skill `ui-check`, port 5743 (confirm the listener is this instance's), `WORKDIR` the session
scratchpad, `CHECKOUT` this worktree. Before the first launch, fill `lib5743` with every file of
the four check songs: the video, `alignment_debug/<stem>.json`, and each file starting with the
stem at the top level and in `lyrics/` and `subtitles/`. `launch.sh` then copies nothing of its
own, and nothing in the real library can change. Join as admin (`POST /singer`, then the
`user` and `singer_token` cookies; reference memory "ui-check join form"). Never press
Regenerate.

Songs: `#OutofOz - 'Defying Gravity' WICKED Studio Sessions _ WICKED the Musical---EFbuID1QG0Y`,
`Beauty and the Beast (1991) - Belle---otxTf5hZ0Yw`,
`John Legend - Love Me Now (Official Video)---NmCFY1oYDeM` (its record is 35 s shorter than the
video, so it needs the override today), `Adele - Rolling in the Deep (Official Music
Video)---rYEDA3JcQqw` (its `.lrc` is the download's pick, record 35807678).

Readings, raw, into `.claude/ui-check/repair_lrc_fit_list/results.json` (untracked) with
screenshots beside it, 390 x 844:

1. Each song: Repair with `?source=lrclib`; the disk row's text; the search with the default
   query and its wall time; for every row its label, tone class and best tag, then pick it,
   Check fit, and record the card's tone, head and lines.
2. Love Me Now's disk row: the card, whether an override box exists, whether Regenerate is on.
3. Preview: the disk row before any search (first three lines), then another row picked while
   open (first three lines).
4. Shots: the list after a search, a good card, a warning card if any row gives one, the preview
   open.
5. Page errors.

**Stop when the artifacts are saved:** paths and raw readings in the Results log, no tallies, no
verdicts. Then Opus judges (read-only), then Ken's `/code-review`.

## After Phase 1

- `/code-review` over commits 1-3 (Ken runs it), then the fixes.
- Ken's checks on his phone: the four songs' lists and cards, the warning card's wording, the
  preview's place.
- Landing: commits 1-3 and their fixes copied onto `dev` one by one (CLAUDE.md, Branches); this
  plan stays on the branch. On `dev`, plan-only: close the two entries (decision 7), add the
  disk-row entry (Results log, "Phase 1 rulings", R4) and update "Landing order".

## Not in this plan

- Showing each row's card on pick, which would retire the Check fit button: the rows are fitted
  anyway, so it is the next simplification, but not what was agreed.
- The Genius route's step 2 scoring (decision 5).
- The bar itself: its thresholds were measured on transcriber words; on Repair it reads whichever
  stream Check fit kept, so "best" can differ from the download's pick when the auto-caption
  wins.

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
| 2026-11-26 | plan | (this commit) | Planned (Opus) against `dev` `efb91f2d`: decisions 1-7 (Ken), O1 open. Measured table above from a scratch script over 12 songs with a `.lrc` on disk. No code. |
| 2026-11-26 | plan | (this commit) | Ken ruled O1 as recommended; it is decision 8. No code. |
| 2026-11-26 | 1, commit 1 | `535c817e` | Check fit follows the bar, not the length limit. `LrcTimingCheck` drops `viable`/`overridable`, gains `refusal`; `LRC_MAX_GAP_S`, `allow_gap` (lib, route, page), `_override_tip`, `#lt-override`, `.rp-override`, `lrcOverride` deleted; `_lrc_repair_plan` refuses unless `fits`; `_lrc_verdict` and `_bar_warning` added. Touched test files: 919 passed after. |
| 2026-11-26 | 1, commit 2 | `5a7e397e` | Rows scored with Check fit's fit. `evaluate`/`pick` take streams; `lrc_auto_timing.check` passes `heard_streams({"transcribe_words": words}, None)`, the probe `{TRANSCRIBE: words}`; `LibraryTools.lrc_timing_candidates`, `_search_synced`, `_lrc_on_disk_id`, `_lrc_check` (the check built from a fit, shared with `_fit_lrc_timing`); `current_lines` and its tests deleted; `/song_info/lrc_search` rewritten with `verdict`; `matchOption` takes a `score` element. Touched test files (library tools, library routes, lrc auto pick, lrc auto timing, probe): 1056 passed after. |
| 2026-11-26 | 1, commit 3 | `503090f1` | `#lt-preview-toggle` / `#lt-preview`, `_lrc_match(status, song)` carries the disk text, `showTimingPreview(which, picked)` and `toggleTimingPreview` shared by step 2 and LRCLIB timing. Full suite after commit 3: 4561 passed (86.8 s). |
| 2026-11-26 | 1, ui-check | (artifacts, untracked) | Port 5743 on this worktree at `503090f1`, four songs, readings below. Artifacts: `.claude/ui-check/repair_lrc_fit_list/` (`results.json`, 25 screenshots, `check_repair_lrc.py`, `extra_readings.py`). Regenerate never pressed. |
| 2026-11-26 | 1, judge | (this commit) | Opus judged the readings and commits 1-3 against decisions 1-8 and the Phase 1 spec, read-only. Passes; rulings R1-R4 below. No code. |

### Phase 1 executor notes (facts, no verdicts)

- Commit 1's four cases of `_lrc_verdict` are built as specified. The third (bar passes, flagged runs, head "Fits,
  but check these lines first.") needs at least two mistimed lines (`MIN_FLAGGED_RUN` 2) while the bar refuses more than
  one (`MAX_MISTIMED` 1), so a fit read from a real check reaches the "read the warning first" head instead; only the one
  hand-made-check test reaches the third head. In the ui-check, Rolling in the Deep rows 11-18 (16 mistimed lines, a run
  of 21 lines) read "Fits, but read the warning first."
- `_fit_lines` gained `show_speed`: a `speed` refusal always shows the "Speed adjusted by N%." line, also when the change
  rounds to 0.0% (that line is then marked as the warning). The card marks the warning line `warn`; the length line is
  second and never marked.
- The card keeps "No line was heard far from its time." only when there is no warning line, no run, no unheard stretch
  and no mistimed line (a `speed` refusal alone still shows it).
- `pick` (no production caller, tests only) changed with `evaluate` to take streams. `_lrclib_results`, `lrclib_candidates`
  and step 2's rows are untouched; the two `TestLrcTimingRepair` tests that remembered records through
  `lrclib_candidates` now remember them through `lrc_timing_candidates`.
- `/song_info/lrc_search` sends each row `verdict` {tone, text}, `fit` (length) and `fit_near` null; it no longer sends
  `mapped`, `sheet_lines` or the check object. The disk row from `_lrc_match` sends `fit_near` null and `syncedLyrics`.
- ui-check harness facts: the page checks the disk match on load for a `?source=lrclib` link (`PRESELECT`), so "card
  after load" is that check. Row 0 is already picked, so pressing it fires no change; its `card_after_pick_shown` reading
  is the earlier answer still showing. All four songs have a match on disk, so a pick always remains and "the preview
  closes when the pick goes" was not exercised in the browser (tests only). `shifted` was not seen as a refusal in
  these four songs' rows; `speed`, `mistimed` and `unclaimed` were (rows below).
- An `rm` of the folder's earlier smoke-run files was blocked by the harness's safety check and not retried; the full run
  wrote the same file names over them, so every screenshot in the folder is from the full run.
- Belle: the match on disk is not in the search's list, so its row has no verdict and no best tag after a search; the
  search's own row 1 carries "best fit". Love Me Now's disk row (35 s shorter than the clip) was a "use anyway" case
  before this branch.

### Phase 1 readings (Sonnet, 2026-11-26)

Source: `.claude/ui-check/repair_lrc_fit_list/results.json` (untracked; every reading below is copied from it)
with the screenshots (390 x 844 at 2x, `<song>_0_load`, `_1_list`, `_2_card_<kind>_row<n>`, `_4_preview_disk`,
`_4_preview_other`) and the two scripts that made them (`check_repair_lrc.py`, `extra_readings.py`). App on port 5743,
`PYTHONPATH` = this worktree at `503090f1`, `lib5743` holding only the four songs' files (copies), LRCLIB live.
Regenerate (`#go`) was never pressed. Row columns: `n` is the row's place in the list; `row text` is the second
span of the row's fit line and its class; `card` is Check fit's answer after picking the row and pressing Check fit
(`Regen` = Regenerate disabled after that answer).

#### #OutofOz - 'Defying Gravity' WICKED Studio Sessions _ WICKED the Musical---EFbuID1QG0Y

- Page opened with `?source=lrclib`. Disk row text: `Defying Gravity` · tags ['on disk'] · `5:53 · 84 s longer` · score element: None.
  Embedded row keys ['albumName', 'artistName', 'fit', 'fit_near', 'id', 'syncedLyrics', 'trackName']; `syncedLyrics` 3437 characters, the `.lrc` on disk 3437, first lines ['[ti:Defying Gravity]', '[ar:Kristin Chenoweth]', '[al:Wicked (Original Broadway Cast Recording)]'].
- Card after load (the page checks the disk match on a `?source=lrclib` link): tone `bad`, head "Doesn't fit.", lines ["Found 43 of 76 lines, but they don't agree on one timing.", 'The match is 5:53; this video is 4:29 (84 s longer).'], runs [], unheard [], Regen True, override elements on the page 0, "Use this match anyway" on the page False.
- Preview toggle on load: {'text': 'Preview selected timing', 'disabled': False, 'preview_hidden': True}; `#lt-matches`'s next sibling is `lt-preview-toggle`. Toggle boxes (closed): preview {'x': 25, 'y': 852, 'w': 148, 'h': 44}, search toggle {'x': 176, 'y': 852, 'w': 91, 'h': 44} (text "Search LRCLIB"); open: preview {'x': 25, 'y': 852, 'w': 83, 'h': 44}, box {'x': 25, 'y': 896, 'w': 340, 'h': 240}, search toggle {'x': 25, 'y': 1144, 'w': 91, 'h': 44}.
- Preview, disk row, before any search: first three lines ['[ti:Defying Gravity]', '[ar:Kristin Chenoweth]', '[al:Wicked (Original Broadway Cast Recording)]'], toggle text "Hide preview".
- Search: default query `Defying Gravity Kristin Chenoweth`, page wall time 3.018 s (click to rows drawn), `/song_info/lrc_search` direct 2.979 s, 19 rows, video label "video is 4:29". The LRCLIB GET alone (`urllib`, same query, two trials): [[1.009, 20], [0.985, 20]] (seconds, records). `_POLITE_SLEEP_S` in `lrclib._search` is 0.3 s.
- Preview left open through the search: first three lines ['[ti:Defying Gravity]', '[ar:Kristin Chenoweth]', '[al:Wicked (Original Broadway Cast Recording)]'].
- Another row picked while open (row 1, "Defying Gravity", doesn't fit · matches 43 of 76 lines): first three lines ["[00:00.11] Elphaba, why couldn't you have stayed calm for once?", '[00:03.78] Instead of flying off the handle!', "[00:05.85] I hope you're happy"], toggle "Hide preview".
- A new search (the pick drops back to the disk row): first three lines ['[ti:Defying Gravity]', '[ar:Kristin Chenoweth]', '[al:Wicked (Original Broadway Cast Recording)]'], hidden False. Toggle pressed again: {'hidden': True, 'toggle_text': 'Preview selected timing'}.
- Page errors (console, uncaught, failed requests), both sessions: [] / [].

| n | label | tags | length | row text (class) | card tone · head | warning line | runs | unheard | Regen |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Defying Gravity | on disk | 5:53 · 84 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 1 | Defying Gravity | - | 5:54 · 85 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 2 | Kristin Chenoweth & Idina Menzel | - | 5:57 · 87 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 3 | Defying Gravity | - | 5:53 · 84 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 4 | Defying Gravity | - | 5:57 · 88 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 5 | Defying Gravity | - | 5:58 · 89 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 6 | Defying Gravity | - | 5:57 · 88 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 7 | Defying Gravity | - | 5:57 · 88 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 8 | Defying Gravity | - | 5:53 · 84 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 9 | Defying Gravity | - | 5:57 · 88 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 10 | Defying Gravity | - | 5:57 · 88 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 11 | Defying Gravity | - | 5:54 · 85 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 12 | Defying Gravity | - | 5:57 · 88 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 13 | Defying Gravity | - | 5:57 · 88 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 14 | Defying Gravity | - | 5:57 · 88 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 15 | Defying Gravity | - | 5:59 · 90 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 16 | Defying Gravity | - | 5:54 · 85 s longer | doesn't fit · matches 43 of 76 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 17 | What Is This Feeling? | - | 3:32 · 57 s shorter | doesn't fit · matches 0 of 74 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 18 | Popular | - | 3:44 · 45 s shorter | doesn't fit · matches 0 of 64 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |

Card screenshots: defying_gravity_2_card_bad_other_row0.png.

#### Beauty and the Beast (1991) - Belle---otxTf5hZ0Yw

- Page opened with `?source=lrclib`. Disk row text: `Belle` · tags ['on disk'] · `5:02 · 5 s longer` · score element: None.
  Embedded row keys ['albumName', 'artistName', 'fit', 'fit_near', 'id', 'syncedLyrics', 'trackName']; `syncedLyrics` 3199 characters, the `.lrc` on disk 3199, first lines ['[ti:Belle]', "[ar:Paige O'Hara]", '[al:Walt Disney Records The Legacy Collection: Beauty and the Beast]'].
- Card after load (the page checks the disk match on a `?source=lrclib` link): tone `bad`, head "Fits, but read the warning first.", lines ['matches 72 of 82 lines', 'The match is 5:02; this video is 4:57 (5 s longer).', 'Line times move 0:00:06 earlier.', 'The clip has 100 words in a row that no line of this match has. The video may have a section this match lacks. [warn]'], runs [], unheard ['4:10–4:15 · 5 lines'], Regen False, override elements on the page 0, "Use this match anyway" on the page False.
- Preview toggle on load: {'text': 'Preview selected timing', 'disabled': False, 'preview_hidden': True}; `#lt-matches`'s next sibling is `lt-preview-toggle`. Toggle boxes (closed): preview {'x': 25, 'y': 828, 'w': 148, 'h': 44}, search toggle {'x': 176, 'y': 828, 'w': 91, 'h': 44} (text "Search LRCLIB"); open: preview {'x': 25, 'y': 828, 'w': 83, 'h': 44}, box {'x': 25, 'y': 872, 'w': 340, 'h': 240}, search toggle {'x': 25, 'y': 1120, 'w': 91, 'h': 44}.
- Preview, disk row, before any search: first three lines ['[ti:Belle]', "[ar:Paige O'Hara]", '[al:Walt Disney Records The Legacy Collection: Beauty and the Beast]'], toggle text "Hide preview".
- Search: default query `Beauty and the Beast - Belle`, page wall time 4.315 s (click to rows drawn), `/song_info/lrc_search` direct 4.372 s, 14 rows, video label "video is 4:57". The LRCLIB GET alone (`urllib`, same query, two trials): [[1.048, 20], [1.019, 20]] (seconds, records). `_POLITE_SLEEP_S` in `lrclib._search` is 0.3 s.
- Preview left open through the search: first three lines ['[ti:Belle]', "[ar:Paige O'Hara]", '[al:Walt Disney Records The Legacy Collection: Beauty and the Beast]'].
- Another row picked while open (row 1, "Belle", fits · matches 96 of 104 lines): first three lines ["[00:26.04] Little town it's a quiet village", '[00:30.86] Everyday like the one before', '[00:35.89] Little town full of little people, waking up to say'], toggle "Hide preview".
- A new search (the pick drops back to the disk row): first three lines ['[ti:Belle]', "[ar:Paige O'Hara]", '[al:Walt Disney Records The Legacy Collection: Beauty and the Beast]'], hidden False. Toggle pressed again: {'hidden': True, 'toggle_text': 'Preview selected timing'}.
- Page errors (console, uncaught, failed requests), both sessions: [] / [].

| n | label | tags | length | row text (class) | card tone · head | warning line | runs | unheard | Regen |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Belle | on disk | 5:02 · 5 s longer | none | bad · Fits, but read the warning first. | The clip has 100 words in a row that no line of this match has. The video may have a section this match lacks. | - | 4:10–4:15 · 5 lines | False |
| 1 | Belle | best fit | 5:09 · 12 s longer | fits · matches 96 of 104 lines (rp-good) | good · Fits. This match can time this song. | - | - | 4:09–4:14 · 3 lines | False |
| 2 | Belle | - | 4:45 · 13 s shorter | fits · matches 96 of 104 lines (rp-good) | good · Fits. This match can time this song. | - | - | 4:09–4:14 · 3 lines | False |
| 3 | Belle | - | 5:26 · 29 s longer | fits · matches 96 of 104 lines (rp-good) | good · Fits. This match can time this song. | - | - | 4:09–4:14 · 3 lines | False |
| 4 | Belle | - | 5:09 · 12 s longer | fits · matches 96 of 104 lines (rp-good) | good · Fits. This match can time this song. | - | - | 4:09–4:14 · 3 lines | False |
| 5 | Belle (From "Beauty and the Beast"/Soundtrack Version) | - | 5:33 · 36 s longer | doesn't fit · matches 71 of 106 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 6 | Belle (From "Beauty and the Beast"/Soundtrack Version) | - | 5:09 · 12 s longer | fits, check first · matches 107 of 121 lines (rp-bad) | bad · Fits, but read the warning first. | Speed adjusted by 0.3%. | - | 4:09–4:14 · 5 lines | False |
| 7 | Belle (From "Beauty and the Beast"/Audio Only) | - | 5:35 · 38 s longer | doesn't fit · matches 71 of 106 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 8 | Belle | - | 5:33 · 36 s longer | doesn't fit · matches 70 of 99 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 9 | Belle (From "Beauty and the Beast"/Soundtrack Version) | - | 5:07 · 10 s longer | fits, check first · matches 107 of 121 lines (rp-bad) | bad · Fits, but read the warning first. | Speed adjusted by 0.3%. | - | 4:09–4:14 · 5 lines | False |
| 10 | belle | - | 5:34 · 37 s longer | doesn't fit · matches 71 of 106 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 11 | Belle | - | 5:09 · 12 s longer | fits, check first · matches 107 of 121 lines (rp-bad) | bad · Fits, but read the warning first. | Speed adjusted by 0.3%. | - | 4:09–4:14 · 5 lines | False |
| 12 | Belle | - | 5:33 · 36 s longer | doesn't fit · matches 71 of 106 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |
| 13 | Belle | - | 5:35 · 38 s longer | doesn't fit · matches 71 of 106 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |

Card screenshots: belle_2_card_bad_fits_row0.png, belle_2_card_good_row1.png, belle_2_card_bad_other_row5.png.

#### John Legend - Love Me Now (Official Video)---NmCFY1oYDeM

- Page opened with `?source=lrclib`. Disk row text: `Love Me Now` · tags ['on disk'] · `3:40 · 35 s shorter` · score element: None.
  Embedded row keys ['albumName', 'artistName', 'fit', 'fit_near', 'id', 'syncedLyrics', 'trackName']; `syncedLyrics` 2559 characters, the `.lrc` on disk 2559, first lines ['[ti:Love Me Now]', '[ar:John Legend]', '[al:Love Me Now]'].
- Card after load (the page checks the disk match on a `?source=lrclib` link): tone `good`, head "Fits. This match can time this song.", lines ['matches 44 of 45 lines', 'The match is 3:40; this video is 4:15 (35 s shorter).', 'Line times move 0:00:12 later.', 'No line was heard far from its time.'], runs [], unheard [], Regen False, override elements on the page 0, "Use this match anyway" on the page False.
- Preview toggle on load: {'text': 'Preview selected timing', 'disabled': False, 'preview_hidden': True}; `#lt-matches`'s next sibling is `lt-preview-toggle`. Toggle boxes (closed): preview {'x': 25, 'y': 809, 'w': 148, 'h': 44}, search toggle {'x': 176, 'y': 809, 'w': 91, 'h': 44} (text "Search LRCLIB"); open: preview {'x': 25, 'y': 809, 'w': 83, 'h': 44}, box {'x': 25, 'y': 853, 'w': 340, 'h': 240}, search toggle {'x': 25, 'y': 1101, 'w': 91, 'h': 44}.
- Preview, disk row, before any search: first three lines ['[ti:Love Me Now]', '[ar:John Legend]', '[al:Love Me Now]'], toggle text "Hide preview".
- Search: default query `Love Me Now John Legend`, page wall time 2.734 s (click to rows drawn), `/song_info/lrc_search` direct 2.781 s, 20 rows, video label "video is 4:15". The LRCLIB GET alone (`urllib`, same query, two trials): [[1.023, 20], [1.015, 20]] (seconds, records). `_POLITE_SLEEP_S` in `lrclib._search` is 0.3 s.
- Preview left open through the search: first three lines ['[ti:Love Me Now]', '[ar:John Legend]', '[al:Love Me Now]'].
- Another row picked while open (row 1, "Love Me Now", fits · matches 44 of 45 lines): first three lines ['[00:16.08] Pulling me further', "[00:19.06] Further than I've been before", '[00:24.09] Making me stronger'], toggle "Hide preview".
- A new search (the pick drops back to the disk row): first three lines ['[ti:Love Me Now]', '[ar:John Legend]', '[al:Love Me Now]'], hidden False. Toggle pressed again: {'hidden': True, 'toggle_text': 'Preview selected timing'}.
- Page errors (console, uncaught, failed requests), both sessions: [] / [].

| n | label | tags | length | row text (class) | card tone · head | warning line | runs | unheard | Regen |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Love Me Now | best fit, on disk | 3:40 · 35 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 1 | Love Me Now | - | 3:39 · 36 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 2 | Love Me Now | - | 4:15 · within a few s | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 3 | Love Me Now | - | 3:30 · 45 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 4 | Love Me Now | - | 3:39 · 36 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 5 | Love Me Now | - | 3:40 · 35 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 6 | Love Me Now | - | 18:33 · 858 s longer | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 7 | Love Me Now | - | 1:29 · 166 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 8 | Love Me Now | - | 3:30 · 45 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 9 | Love me now | - | 3:30 · 45 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 10 | Love Me Now [FazMusic.Net] | - | 3:30 · 45 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 11 | Love Me Now | - | 3:30 · 45 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 12 | 037-john legend - love me now | - | 3:31 · 44 s shorter | fits · matches 44 of 45 lines (rp-good) | good · Fits. This match can time this song. | - | - | - | False |
| 13 | John Legend - Love Me Now (Official Video) | - | 4:15 · within a few s | fits, check first · matches 44 of 45 lines (rp-bad) | bad · Fits, but read the warning first. | Speed adjusted by 0.7%. | - | - | False |
| 14 | John Legend - Love Me Now (Official Video) | - | 4:15 · within a few s | fits, check first · matches 44 of 45 lines (rp-bad) | bad · Fits, but read the warning first. | Speed adjusted by 0.7%. | - | - | False |
| 15 | Love Me Now | - | 4:14 · within a few s | fits, check first · matches 44 of 45 lines (rp-bad) | bad · Fits, but read the warning first. | Speed adjusted by 0.7%. | - | - | False |
| 16 | Love Me Now (Official Video) | - | 4:15 · within a few s | fits, check first · matches 44 of 45 lines (rp-bad) | bad · Fits, but read the warning first. | Speed adjusted by 0.7%. | - | - | False |
| 17 | Love Me Now (Official Video) | - | 4:15 · within a few s | fits, check first · matches 44 of 45 lines (rp-bad) | bad · Fits, but read the warning first. | Speed adjusted by 0.7%. | - | - | False |
| 18 | Love Me Now (Dave Audé Remix Radio Edit) | - | 3:39 · 36 s shorter | fits, check first · matches 50 of 54 lines (rp-bad) | bad · Fits, but read the warning first. | 12 lines are heard far from their time. | 3:08–3:42 · 12 lines | - | False |
| 19 | Love Me Now (Armand Van Helden remix radio edit) | - | 3:40 · 35 s shorter | doesn't fit · matches 52 of 55 lines (rp-bad) | bad · Doesn't fit. | - | - | - | True |

Card screenshots: love_me_now_2_card_good_row0.png, love_me_now_2_card_bad_fits_row13.png, love_me_now_2_card_bad_other_row19.png.

#### Adele - Rolling in the Deep (Official Music Video)---rYEDA3JcQqw

- Page opened with `?source=lrclib`. Disk row text: `Adele - Rolling in the Deep` · tags ['on disk'] · `3:54 · within a few s` · score element: None.
  Embedded row keys ['albumName', 'artistName', 'fit', 'fit_near', 'id', 'syncedLyrics', 'trackName']; `syncedLyrics` 3582 characters, the `.lrc` on disk 3582, first lines ['[ti:Adele - Rolling in the Deep]', '[ar:Adele]', '[al:Adele]'].
- Card after load (the page checks the disk match on a `?source=lrclib` link): tone `good`, head "Fits. This match can time this song.", lines ['matches 50 of 58 lines', 'The match is 3:54; this video is 3:54.', 'Line times move 0:00:01 earlier.'], runs [], unheard ['3:29–3:36 · 3 lines'], Regen False, override elements on the page 0, "Use this match anyway" on the page False.
- Preview toggle on load: {'text': 'Preview selected timing', 'disabled': False, 'preview_hidden': True}; `#lt-matches`'s next sibling is `lt-preview-toggle`. Toggle boxes (closed): preview {'x': 25, 'y': 809, 'w': 148, 'h': 44}, search toggle {'x': 176, 'y': 809, 'w': 91, 'h': 44} (text "Search LRCLIB"); open: preview {'x': 25, 'y': 809, 'w': 83, 'h': 44}, box {'x': 25, 'y': 853, 'w': 340, 'h': 240}, search toggle {'x': 25, 'y': 1101, 'w': 91, 'h': 44}.
- Preview, disk row, before any search: first three lines ['[ti:Adele - Rolling in the Deep]', '[ar:Adele]', '[al:Adele]'], toggle text "Hide preview".
- Search: default query `Rolling in the Deep Adele`, page wall time 3.347 s (click to rows drawn), `/song_info/lrc_search` direct 3.432 s, 19 rows, video label "video is 3:54". The LRCLIB GET alone (`urllib`, same query, two trials): [[1.305, 20], [1.001, 20]] (seconds, records). `_POLITE_SLEEP_S` in `lrclib._search` is 0.3 s.
- Preview left open through the search: first three lines ['[ti:Adele - Rolling in the Deep]', '[ar:Adele]', '[al:Adele]'].
- Another row picked while open (row 1, "Adele - Rolling in the Deep", fits · matches 50 of 58 lines): first three lines ["[00:05.19] There's a fire starting in my heart", "[00:09.76] Reaching a fever pitch, it's bringing me out the dark", '[00:14.26] Finally I can see you crystal clear'], toggle "Hide preview".
- A new search (the pick drops back to the disk row): first three lines ['[ti:Adele - Rolling in the Deep]', '[ar:Adele]', '[al:Adele]'], hidden False. Toggle pressed again: {'hidden': True, 'toggle_text': 'Preview selected timing'}.
- Page errors (console, uncaught, failed requests), both sessions: [] / [].

| n | label | tags | length | row text (class) | card tone · head | warning line | runs | unheard | Regen |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Adele - Rolling in the Deep | best fit, on disk | 3:54 · within a few s | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:36 · 3 lines | False |
| 1 | Adele - Rolling in the Deep | - | 3:54 · within a few s | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:36 · 3 lines | False |
| 2 | Adele - Rolling in the Deep (Official Music Video) | - | 3:48 · 6 s shorter | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:37 · 3 lines | False |
| 3 | Adele - Rolling in the Deep (Official Music Video) | - | 3:54 · within a few s | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:37 · 3 lines | False |
| 4 | Rolling in the Deep | - | 3:48 · 6 s shorter | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:36 · 3 lines | False |
| 5 | Rolling in the Deep | - | 3:48 · 6 s shorter | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:36 · 3 lines | False |
| 6 | Adele - Rolling In The Deep | - | 3:48 · 6 s shorter | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:36 · 3 lines | False |
| 7 | Adele - Rolling in the Deep | - | 3:48 · 6 s shorter | fits · matches 50 of 59 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:36 · 3 lines | False |
| 8 | Adele - Rolling in the Deep | - | 3:49 · 5 s shorter | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:36 · 3 lines | False |
| 9 | Rolling In The Deep - Adele  🎵 | - | 4:07 · 13 s longer | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:29–3:36 · 3 lines | False |
| 10 | Adele - Rolling in the Deep (Official Music Video) | - | 3:54 · within a few s | fits · matches 50 of 58 lines (rp-good) | good · Fits. This match can time this song. | - | - | 3:30–3:36 · 3 lines | False |
| 11 | Rolling in the Deep (Adele Cover) | - | 3:25 · 29 s shorter | fits, check first · matches 50 of 58 lines (rp-bad) | bad · Fits, but read the warning first. | 16 lines are heard far from their time. | 2:15–3:26 · 21 lines | 3:12–3:19 · 3 lines | False |
| 12 | Rolling In The Deep (Adele Cover) | - | 3:38 · 16 s shorter | fits, check first · matches 50 of 58 lines (rp-bad) | bad · Fits, but read the warning first. | 16 lines are heard far from their time. | 2:15–3:26 · 21 lines | 3:12–3:19 · 3 lines | False |
| 13 | Rolling in the Deep | - | 0:03 · 231 s shorter | fits, check first · matches 50 of 58 lines (rp-bad) | bad · Fits, but read the warning first. | 16 lines are heard far from their time. | 2:15–3:26 · 21 lines | 3:12–3:19 · 3 lines | False |
| 14 | Rolling in the Deep | - | 2:50 · 64 s shorter | fits, check first · matches 50 of 58 lines (rp-bad) | bad · Fits, but read the warning first. | 16 lines are heard far from their time. | 2:15–3:26 · 21 lines | 3:12–3:19 · 3 lines | False |
| 15 | Rolling in the Deep | - | 3:35 · 19 s shorter | fits, check first · matches 50 of 58 lines (rp-bad) | bad · Fits, but read the warning first. | 16 lines are heard far from their time. | 2:15–3:26 · 21 lines | 3:12–3:19 · 3 lines | False |
| 16 | Rolling in the Deep | - | 4:04 · 10 s longer | fits, check first · matches 50 of 58 lines (rp-bad) | bad · Fits, but read the warning first. | 16 lines are heard far from their time. | 2:15–3:26 · 21 lines | 3:12–3:19 · 3 lines | False |
| 17 | Rolling in the Deep | - | 1:20 · 154 s shorter | fits, check first · matches 50 of 58 lines (rp-bad) | bad · Fits, but read the warning first. | 16 lines are heard far from their time. | 2:15–3:26 · 21 lines | 3:12–3:19 · 3 lines | False |
| 18 | Rolling in the Deep | - | 5:11 · 77 s longer | fits, check first · matches 50 of 58 lines (rp-bad) | bad · Fits, but read the warning first. | 16 lines are heard far from their time. | 2:15–3:26 · 21 lines | 3:12–3:19 · 3 lines | False |

Card screenshots: rolling_in_the_deep_2_card_good_row0.png, rolling_in_the_deep_2_card_bad_fits_row11.png.

### Phase 1 rulings (Opus, 2026-11-26)

Read: commits `535c817e`, `5a7e397e`, `503090f1` (`git diff c1f938a7..503090f1`), the readings above,
`love_me_now_0_load.png` and `love_me_now_1_list.png`. Against the decisions: 1, 2, 3 and 8 as read in the four
songs' tables (each row's label, tone and count equal its own card; passing rows first; `best` on the first passing
row, none on Defying Gravity; Love Me Now's disk match, 35 s short, regenerates with no override box; speed,
mistimed and unclaimed warnings live, shifted by tests). 5: step 2's rows keep the text count (`lrclibOption`
unchanged in substance). 6: tests only (`test_library_tools.py:1802`, `test_library_routes.py:3293`). Download
unchanged: `lrc_auto_timing.check` now passes `{}` where it passed `{TRANSCRIBE: []}` for no words, and `fit_slice`
drops empty streams before anything else (`srt_slice_fit.py:304-306`), so both give `NO_REFERENCE`.

Fixes, made in the `/code-review` fix pass:

- **R1. Delete `_lrc_verdict`'s flagged-runs case** (head "Fits, but check these lines first.",
  `routes/song_info.py:961`) and the hand-made-check test that reaches it (`test_library_routes.py` around 2891).
  Unreachable: `flagged_runs` needs `MIN_FLAGGED_RUN` (2) mistimed lines, and `refusal` returns `mistimed` above
  `MAX_MISTIMED` (1), checked before; the check's `refusal` is always `lrc_auto_pick.refusal(fit)` (`_lrc_check`).
  A fit with a run reads "Fits, but read the warning first." and its runs still list on the card. The msgid leaves
  the catalogs at the next regen (Ken); no catalog edits. The Commit 1 spec's third case was a spec miss.
- **R2. `#lt-preview-toggle` and `#lt-search-toggle` each on their own line**, preview first (decision 4), search
  below. Both are `.rp-link` (`inline-flex`), so with the preview closed they sit on one line, about 3 px apart
  (`x` 25 + `w` 148, then `x` 176, same `y`), and read as one link "Preview selected timing Search LRCLIB"
  (`love_me_now_0_load.png`). With the preview open the search link already falls below the box.
- **R3. The disk row's preview shows the timed lines only.** `_lrc_match` sends `read_song_lrc(song).text`, the
  whole file (`read_lrc`: "its header tags are harmless to the cue parser"), so the disk preview's first lines are
  the ID tags (`[ti:]`, `[ar:]`, `[al:]`, `[length:]`, `[lrclib_id:]`; readings 3 in all four songs), where the
  same record picked from the search starts on its first timed line. Strip the ID-tag lines from the disk row's
  `syncedLyrics`; the repair path re-reads the file and is unaffected.

Logged, not fixed here:

- **R4. The disk row has no verdict when the search does not list its record** (Belle: the disk match is refused,
  `unclaimed`, and sits first with no label above row 1's `best fit`; only the card the page loads for a
  `?source=lrclib` link says so). Not a regression (before this branch it had no score either) and outside
  decision 1, which covers search results. Fitting it with the rest raises whether the disk record joins the pick
  order and can take `best`. Proposed `plans/open-issues.md` entry, added at landing: "Repair's LRCLIB timing: the
  match on disk gets no verdict when the search doesn't list it."

Noted, no action: the search's wall time (2.7-4.3 s on the page, against 1.0-1.3 s for the LRCLIB GET alone) is
the per-record fitting decision 1 accepted; Ken's phone checks judge it.
