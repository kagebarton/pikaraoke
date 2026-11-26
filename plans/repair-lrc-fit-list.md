Model: Claude Sonnet 5.5 (executor, Phase 1). Author and judge: Claude Opus 5.5, 2026-11-26.

# Repair's LRCLIB timing list, scored by the fit

Branch `repair_lrc_fit_list` off `dev` at `efb91f2d`, worktree
`.claude/worktrees/repair_lrc_fit_list`.

**Status: planned 2026-11-26, every decision ruled (1-8). Next: Phase 1, Sonnet. No code.**

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
  plan stays on the branch. On `dev`, plan-only: close the two entries (decision 7) and update
  "Landing order".

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
