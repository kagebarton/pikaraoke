Model: Claude Opus 5.5 (author, 2026-10-29). Executor: Claude Sonnet 5.5. GATE A
goes to Opus; GATE B and Phase 7 go to Ken.

# Lyric-source lists and LRCLIB timing

## Goal

Ken wants two things:

1. In the app, see which songs are timed by **cue align** and which by the **joint
   matcher**, and from which lyric source. Each song gets a Repair link next to it.
2. Move joint songs onto cue align wherever he can.

The route always follows the source (`lyric_align.py:143-164`):

- A YouTube caption (`srt`) or movie subtitles (`movie_srt`) always go through cue
  align.
- Genius or custom lyrics always go through joint.
- No lyrics means transcription.

So one list per source answers both questions.

A Repair link on its own moves no song. The Repair page's only cue-route sources are
a YouTube caption and movie subtitles, and joint songs are mostly the ones where
neither applies. What moves them is the **LRCLIB timing** repair: an LRCLIB match
the admin has checked becomes the song's timing. Its shape was ruled in
`plans/open-issues.md` (entry "An LRCLIB match the admin has checked becomes the
song's timing (Repair)").

## Decisions

From `plans/open-issues.md` (Ken, 2026-10-29), restated so this plan stands on its
own:

1. **The LRC's own lyrics are the sheet**, since they are what the timing is checked
   against.
2. **Preview = flagged lines first.** After the fit, mark each line by whether heard
   words landed near its fitted time. A cut verse or an extra repeat shows up as a
   run of flagged lines. The fit's spread check can't catch that, because it ignores
   a minority of lines that disagree. Playback with the lines overlaid is held back
   until flagged lines prove not enough.
3. **Offered only once the fit makes it viable**; otherwise the pick stays a fill, as
   today.

Ken, 2026-10-29 (this plan):

4. **Viable = the fit passes AND the length gap to the video is small**, and the
   flagged lines are shown before Ken confirms. The gap limit is set at GATE A.
5. **Both parts on one branch**: the lists first, then LRCLIB timing.
6. **The Repair link opens Repair with a source already picked**:
   - LRCLIB timing when the song has a usable LRC on disk;
   - otherwise YouTube caption (joint songs only);
   - otherwise nothing.
7. **Joint songs with no usable LRC get a list of their own**, "No timed source".

Ken, 2026-10-29, at GATE A (Results rows 10-11):

8. **Flags come in two kinds.** A line heard far from its fitted time is
   *mistimed*; a line nothing was heard for is *unheard*. Only mistimed lines make
   a flagged run, the warning. Unheard stretches get a quieter "couldn't check
   these lines" note. This refines Decision 2: on the library, a run of unheard
   lines was as often a transcriber gap as a wrong edit. Known weak spot: a section
   cut at the very end of a song only shows as unheard.
9. **The length-gap limit is 15 s**, not 5. Fits with no flagged run had gaps of up
   to 14 s (a music video's longer intro or outro), and the flags now catch the
   edit mismatches the gap was there for.

Ken, 2026-10-29, after Phase 6 (Results row 17):

10. **Decision 6 is limited to joint songs.** The Repair link picks a source only
    for a joint song (LRCLIB timing with an LRC on disk, else YouTube caption). A cue
    song, including one with a leftover `.lrc` and one already timed from an LRCLIB
    match, gets the plain Repair page.

Ken, 2026-10-30, before the review (Phase 6.1):

11. **A fit that passes may override the length limit.** When the fit passes but
    the gap is over `LRC_MAX_GAP_S`, the card offers a checkbox that enables
    Regenerate. Case: `NSYNC - Paradise`, a concert clip with talk before the
    song. Its fit passes (shift about +24 s, speed 1, no flagged run), and the
    whole 38 s gap is talk and applause outside the fitted lines. A refused fit
    is never overridable. The checkbox's label is short and its explanation sits
    behind an (i) `info_tip`, like the card's other notes. What it gives up: the
    gap was the only guard against extra or cut material at the very start or
    end, which the flags can't see, so the admin's ear is that check.

Defaults (author's; not ruled, so raise them if they look wrong):

- The lists go by what the **last run used** (the bundle's `lyrics.origin` and
  `method_used`), as the existing lists do. Lists may overlap, as "Looks poor"
  already does.
- **"Usable LRC" is read from disk, not from the bundle.** Bundles from before
  schema 9 never recorded the match, so 6 joint songs show `lrclib_state == "none"`
  while a real match sits at `lrclib.lrc_path(song)`. Usable means: the file exists
  and `lrclib.is_skip_marker(path)` is false. Today all 17 joint songs have one, so
  "No timed source" starts empty.
- LRCLIB timing uses the **LRC on disk** by default; the existing LRCLIB search
  lets Ken pick a different one.
- The new sheet is a third kind of custom sheet, `lyrics/<stem>.lrclib.srt`, with
  origin `lrclib_srt`. Like the movie sheet, it outlives Regenerate, bulk runs and
  Reset, and only a Repair to another source removes it. One sheet per song,
  whatever its kind.
- Flagged lines are computed inside `fit_slice` for every caller, but shown only on
  the LRCLIB timing card. Showing them for movie subtitles too would be unrequested.

## Library facts (2026-10-29)

66 songs:

| Lyric source | Route | Songs |
|---|---|---|
| YouTube caption | cue align | 40 (22 current, 18 behind) |
| Movie subtitles | cue align | 7 |
| Genius | joint | 15 |
| Custom | joint | 2 |
| No lyrics | transcribe | 2 |

## Test songs (Phase 3 report, GATE A)

The 17 joint songs, from a read-only status pass on 2026-10-29. Column notes:

- **LRCLIB**: the bundle's `lrclib_state`.
- **gap**: how many seconds longer the match is than the video (negative means
  shorter).
- **heard**: the bundle's `transcribe_words` count.
- **ASR**: whether `subtitles/<stem>.en.asr.json3` exists.
- **guessed**: guessed lines out of all lines.

| Song (short) | Source | LRCLIB | gap s | heard | ASR | guessed | Note |
|---|---|---|---|---|---|---|---|
| Defying Gravity (Wicked 20th) | custom | rejected | +97 | 267 | yes | 0/45 | **Known bad:** structural mismatch (S-1). Must be refused. |
| Popular (Wicked 20th) | genius | none* | ? | 319 | yes | 11/62 | **Known bad:** edit mismatch in the tail (S-1). Must flag a run. |
| Jessie J - Domino | genius | none* | ? | 330 | no | 4/67 | **Known bad:** S-1 matched a "UK Radio Edit", with lines 0-16 only fitted. The LRC on disk now is from the "weekend vibes" album, so it may differ from the S-1 one. |
| 晴天 (Jay Chou) | genius | rejected | -19 | 79 | no | 24/42 | Mandarin; few heard words. Expect a refusal. |
| Soda Pop | genius | rejected | 0 | 209 | no | 5/64 | |
| Bloodstream | custom | rejected | 0 | 324 | yes | 6/58 | |
| Lose Yourself | genius | used | -1 | 792 | no | 1/87 | Rap: dense lines. |
| She Used To Be Mine | genius | used | 0 | 295 | no | 0/46 | |
| Stay Gold | genius | used | 0 | 280 | no | 0/38 | |
| Your Idol | genius | used | -14 | 300 | no | 9/71 | |
| Golden | genius | used | -4 | 286 | no | 5/51 | |
| Takedown | genius | used | -10 | 343 | no | 13/67 | Choreography video. |
| Seven (Jung Kook) | genius | used | -14 | 472 | yes | 2/79 | |
| Best Part Of Me (Live) | genius | none* | ? | 234 | yes | 1/38 | Live take, compared against a studio LRC. |
| In Summer (Frozen) | genius | none* | ? | 212 | no | 2/31 | |
| NSYNC - Paradise | genius | none* | ? | 339 | no | 12/65 | The LRC's artist reads Justin Timberlake. |
| Colors of the Wind (Blu-ray) | genius | none* | ? | 311 | yes | 0/37 | A movie clip. `~/pikaraoke-songs/movie_subs/pocahontas.srt` already gives it the movie route. |

`*` marks a behind bundle (schema 8): an LRC is on disk, but the bundle doesn't
record it. The report computes the gap from the LRC file's own `duration`.

## Design

### Lists (`pikaraoke/lib/library_status.py`)

`SongStatus` gains `lrc_on_disk: bool`, the "usable LRC" check from the Defaults. It
is one `is_file` plus a skip-marker read, and `song_status` already reads the sheet
paths.

`SONG_LISTS` gains these. `overview_counts` picks them up without changes.

| key | rule |
|---|---|
| `caption` | `origin == "srt"` |
| `movie` | `origin == "movie_srt"` |
| `genius` | `origin == "genius"` |
| `custom` | `origin == "custom"` |
| `no_timed_source` | `method == "joint" and not lrc_on_disk` |
| `lrc` (Phase 6) | `origin == LRC_ORIGIN` |

### Rows (`pikaraoke/routes/library.py`)

- `_subline(name, status)`, for the new lists:
  - cue lists: "Cue align".
  - joint lists: the parts that apply, joined with " · ":
    - "with captions" when `ytasr_used`;
    - the LRCLIB part:
      - `used`: "LRCLIB filled N lines" (`ngettext`, as in
        `song_info._lrclib_tile`);
      - `rejected`: "LRCLIB not used";
      - `skipped`: "LRCLIB skipped";
      - otherwise: "LRC on disk" if `lrc_on_disk`, else "no LRCLIB match".
- Each row dict gains `repair_url`:
  `url_for("song_info.repair_page", song=path, source=_repair_source(status))`.
  `url_for` drops a `None` argument, so a song with no preselect gets the plain
  URL.
- `_repair_source(status) -> str | None`:
  - Phase 1: `"caption"` if `status.method == "joint"`, else `None`.
  - Phase 6: `"lrclib"` first, when `status.lrc_on_disk`.

### Tools tab (`pikaraoke/templates/processing.html`)

- Add a second `pr-sec` header, "By lyric source", plus a `pr-card` below the
  existing list card. Same `.pr-list` / `.pr-link[data-list]` markup. Labels:
  - YouTube caption · cue align
  - Movie subtitles · cue align
  - Genius · joint
  - Custom · joint
  - No timed source

  Each gets a count tag (`tag is-light`). No-timed-source gets `is-warning`.
- In `openList`, each row is a whole `<a>` today, and a second link can't sit inside
  it. Change it to a `div.pr-song` holding the name and summary link (to `info_url`,
  `no-spa`) and a small "Repair" link (to `repair_url`, `no-spa`). Apply this to
  every list, so the existing four get the link too.
- The info tip gains one line: "Cue align times each line from a timed source.
  Joint combines the lyric aligner with what is heard; it is the fallback."

### Repair page preselect (`routes/song_info.py:repair_page`, `templates/song_repair.html`)

- `repair_page` reads `request.args.get("source")` and passes it as `preselect` only
  if it is one of `caption`, `genius`, `custom`, `movie`, `transcribe` (Phase 6
  adds `lrclib`). Anything else becomes `None`.
- In the JS, `var PRESELECT = {{ preselect | tojson }};`:
  - If the card is enabled on load, call `chooseSource(PRESELECT)`.
  - The caption card enables only after the caption check (around line 167), so
    choose it there too when `PRESELECT === 'caption'`. Mirror how
    `CURRENT_SOURCE` is handled at that spot.
  - A failed caption check leaves nothing chosen.

### One `sheet_kind` (Phase 2)

This resolves the open issue "SongStatus carries two overlapping sheet flags".

- Replace `SongStatus.custom_sheet` and `.movie_sheet` with
  `sheet_kind: str | None`, which is one of `"custom"`, `"movie"` or (Phase 5)
  `"lrc"`.
- Add `library_regen.sheet_kind(path) -> str | None`, mapping a sheet's suffix to
  its kind. It is the only place the suffix test lives.
- Readers to move: `song_info._current_source`, `library_tools` (`_now`, `_Entry`
  and the other `custom_sheet`/`movie_sheet` users), and
  `library_regen.custom_plan`.
- Find every reader with `graphify affected "SongStatus"` and
  `grep -rn "custom_sheet\b\|movie_sheet\b" pikaraoke tests`.

### Fit and flagged lines (`pikaraoke/lib/srt_slice_fit.py`, Phase 3)

- Add `lrc_to_srt(lrc_text: str) -> str`: `lrclib.cue_spans_from_lrc`, then one
  `srt.Subtitle` per cue, then `srt.compose`. An empty LRC returns `""`, which
  `fit_slice` already refuses as `not_srt`.
- `SliceFit` gains `flagged: tuple[int, ...] = ()`. These are indexes into the
  in-clip cues of the corrected SRT, in order, and are set only on `FITS`.
- In `_fit_one_stream`, on the `FITS` path, an in-clip cue `k` is flagged when
  either:
  - `k` is not in `found`; or
  - its anchor's start differs from its fitted start (`speed * spans[k][0] + shift`)
    by more than `FLAG_TOLERANCE_S`.

  `_cue_anchors` already returns the anchors; keep them as a `{lid: start}` dict to
  look them up.
- Map cue indexes to the corrected SRT's numbering. `_corrected_srt` drops the cues
  outside the clip, so build the in-clip index list once and use it for both.
- `FLAG_TOLERANCE_S = 2.0` is a **placeholder**, so that the module runs. GATE A
  sets it. Write it with a comment that says so, as `MIN_MATCHED_SHARE` was handled
  in the movie plan.
- Add `flagged_runs(flagged: tuple[int, ...], min_run: int) -> list[tuple[int, int]]`:
  runs of consecutive flagged lines at least `min_run` long, as `(first, last)`.
  `MIN_FLAGGED_RUN = 3` is a placeholder; GATE A sets it.

**As amended at GATE A (Decision 8, commit `2cde053`)**, superseding the three
bullets on `flagged` above:

- `SliceFit.flagged` is replaced by `mistimed` (an anchor more than
  `FLAG_TOLERANCE_S` from the fitted start) and `unheard` (no anchor). Same
  numbering, both set only on `FITS`.
- `flagged_runs(mistimed, unheard, min_run)`: runs of at least `min_run` mistimed
  lines, as `(first, last)` mistimed line. An unheard line between two mistimed
  ones does not end a run; a line heard on time does.
- `unheard_runs(unheard, min_run)`: runs of consecutive unheard lines (the old
  `flagged_runs` body).
- `FLAG_TOLERANCE_S = 5.0`, `MIN_FLAGGED_RUN = 2`, `MIN_UNHEARD_RUN = 3`.

### Storage and plan (`pikaraoke/lib/library_regen.py`, Phase 5)

- Add `LRC_SRT_SUFFIX = ".lrclib.srt"` and append it to `CUSTOM_SHEET_SUFFIXES`.
  `_claims`/`_owner` already treat `<stem>.<anything>` as the song's file, so backups
  take it in. A unit test proves this.
- Add `LRC_ORIGIN = "lrclib_srt"`.
- `custom_sheet_plan` and `movie_sheet_plan` differ only in suffix, origin and label,
  and the LRC sheet would be the third copy. Extract
  `_sheet_plan(song, suffix, origin, label, text) -> Plan`, and make
  `lrc_sheet_plan(song, text=None)` a one-liner over it.
- `custom_plan` dispatches on `sheet_kind`.
- One sheet per song: find where saving a movie sheet removes the `.custom.txt`, and
  make it remove every other suffix in `CUSTOM_SHEET_SUFFIXES`. Test all three.
- The cue route needs nothing new. The sheet is an `.srt`, so `_load_lyrics` yields
  cue spans, and `method_used` becomes `cue_align`.

### Check and Repair (`pikaraoke/lib/library_tools.py`, Phase 5)

- Add a frozen dataclass `LrcTimingCheck`: `fit: SliceFit`, `gap_s: int | None`,
  `record: dict` (from `lrclib.record_meta`), `viable: bool`, `regenerate_helps:
  bool`.
- `check_lrc_timing(song_path, lrclib_id: int | None) -> LrcTimingCheck`:
  - The record comes from `lrclib_id`, through `_lrclib_records`, or else
    `lrclib.get_record`. If `lrclib_id` is `None`, use the LRC on disk
    (`lrclib.read_lrc(lrclib.lrc_path(song))`).
  - Raise `RegenError` when there is neither, or the record has no
    `syncedLyrics`.
  - Then `lrc_to_srt`, then `fit_slice(srt, heard_streams(job.bundle,
    self._asr_on_disk(song)), media_duration(job))`, as `_fit_movie_slice` does.
  - `gap_s = length_gap_s(record["duration"], length)`.
  - `viable = fit.status == FITS and gap_s is not None and abs(gap_s) <=
    LRC_MAX_GAP_S`.
  - `LRC_MAX_GAP_S = 15` (Decision 9, set at GATE A). It is its own constant, not
    `song_info._LENGTH_GAP_NOTED_S` (5), which stays as the length line's
    "within a few s" cut-off.
- Add `class LrcTimingRefused(RegenError)`, carrying the check, as
  `MovieSliceRefused` does.
- In `repair(...)`, add `source == "lrclib"`, which calls
  `_lrc_repair_plan(job, lrclib_id)`:
  - It runs the check again on the server, so what gets saved never comes from
    numbers the page sent.
  - If the check is not viable, raise `LrcTimingRefused(check)`.
  - Otherwise return `lrc_sheet_plan(song, check.fit.srt)`, and record the match on
    the plan through the existing `_apply_lrclib_pick(plan, record_id, False)`, so
    the bundle notes which LRC timed it.
- `job.replaces_custom = source not in ("custom", "movie", "lrclib")`.

### Routes and page (`pikaraoke/routes/song_info.py`, `templates/song_repair.html`, Phase 6)

These are built to the mockup ratified at GATE B. Until then, the expected shape:

- `POST /song_info/lrc_fit`, body `{song, lrclib_id?}`, returns a card:
  - a head line (fits, or refused and why);
  - "matches x of y lines";
  - the length line, reusing `_lrclib_fit`'s wording;
  - the flagged runs (`flagged_runs(fit.mistimed, fit.unheard, MIN_FLAGGED_RUN)`),
    each as its lines' text with `m:ss` times;
  - a quieter note for the unheard stretches
    (`unheard_runs(fit.unheard, MIN_UNHEARD_RUN)`): "couldn't check these lines",
    with their text and times;
  - `viable`.
- Reuse `_card` / `_card_text`.
- `repair()` maps `LrcTimingRefused` to `_card_text`, as it does for
  `MovieSliceRefused`.
- A new source card, "LRCLIB timing" ("Time the song from an LRCLIB match's own
  line times"). Its section:
  - the match on disk (title · artist · length), plus a "Search LRCLIB" link that
    reuses the step-2 search and list markup. Score candidates against the bundle's
    current `lyrics.lines`.
  - Check fit, then the card.
- Regenerate is enabled only on `viable`. It's a single step; there is no step 2.
- When `PRESELECT === 'lrclib'`, select the card on load and run the check on the
  disk match.
- Labels:
  - `song_info._source_name`: "LRCLIB".
  - `_route_text`: "Lyrics from an LRCLIB match, timed against its own line times."
  - `_current_source`: return `"lrclib"` for `sheet_kind == "lrc"`.
  - History's origin label.
  - The tools-tab list "LRCLIB · cue align".

## Phases

### Phase 0: branch and baseline

- [x] `git switch -c lyric_source_lists dev` (done 2026-10-29 by the author, at
      `9e0acfd`). The plan file is untracked.
- [x] Full suite on the branch. Log the pass count in the Results log as the
      baseline.

### Phase 1: by-source lists and Repair link

- [x] Do the Lists, Rows, Tools tab and Repair page preselect sections above, using
      `"caption"` as the only preselect.
- [x] Tests:
  - `tests/unit/test_library_status.py`: each new list's rule on a fake bundle;
    `lrc_on_disk` for a missing file, a skip marker, and a real LRC; the overview
    keys.
  - `tests/unit/test_library_routes.py`: the joint sublines for each
    `lrclib_state`; `repair_url` carries `source=caption` for a joint song and no
    `source` for a cue song.
  - The route test for `repair_page`: a known `source` is passed through, an
    unknown one becomes `None`.
- [x] Smoke check, read-only: `library_statuses(~/pikaraoke-songs)` gives
      caption 40, movie 7, genius 15, custom 2, no_timed_source 0. Log it. Any
      other numbers are fine if the library changed; log the actual ones.
- [x] Commit: `feat(library): lists songs by lyric source, with a Repair link per song`
      (`4a43799`).
- [ ] Checkpoint (CLAUDE.md): Ken can look at the tab now. Flag `/compact`.

### Phase 2: one `sheet_kind`

- [x] Do the One `sheet_kind` section. No behaviour change: the existing
      custom-sheet and movie tests pass unchanged, apart from the field renames.
- [x] Commit: `refactor(library): one sheet_kind for a song's custom sheet`
      (`b9cdbda`).
- [x] Add a strike-through to the `plans/open-issues.md` entry ("SongStatus carries
      two overlapping sheet flags"), citing the commit hash. This is a separate
      `docs(plans)` commit.

### Phase 3: LRC fit with flagged lines, then the report -> GATE A (Opus)

- [x] Do the Fit and flagged lines section, with tests in
      `tests/unit/test_srt_slice_fit.py`, on synthetic cues only:
  - `lrc_to_srt`: the last line holds `LRC_LAST_LINE_HOLD_S`; an empty LRC gives
    `""`.
  - An LRC at clip times fits at shift ~0, speed 1, with no flags.
  - A cut verse: the LRC has 6 lines the heard words never sing, mid-song. The fit
    still passes and the 6 lines form one flagged run.
  - An extra repeat: the video sings a chorus twice, the LRC once. Record what the
    flags do, without asserting a verdict.
  - Unheard single lines scattered (no run) give no run at `MIN_FLAGGED_RUN`.
  - `flagged_runs` edge cases.
  - Every existing movie-slice test passes unchanged; `flagged` is new data only.
- [x] Commit: `feat(lyrics): an LRC fits to the clip with flagged lines` (`34a806e`).
- [x] Add a report script, `scripts/lrc_timing_report.py`, modelled on
      `scripts/movie_srt_fit_report.py` (`0ae28a3`).
  - For every joint song in `~/pikaraoke-songs` with a usable LRC, and for each heard
    stream separately, print: status, reason, matched/total, shift, speed, spread,
    anchors, gap_s, the flagged indexes, and the runs at `min_run` 2, 3 and 4.
  - Then print the flagged indexes again at tolerances of 1.0, 1.5, 2.0, 3.0 and
    4.0 s, so GATE A can choose one without re-running anything.
  - Read only: nothing is written next to a song.
  - LRC files are copyrighted lyric text, so the script prints no line text, only
    indexes.
- [x] Run it. Paste the raw output into a "GATE A report output" section at the
      end of this plan, and add one Results log row describing it.
- [x] **GATE A: stop and hand off to Opus.** Do not pick numbers on the executor
      side. Opus sets `FLAG_TOLERANCE_S`, `MIN_FLAGGED_RUN` and `LRC_MAX_GAP_S`
      against these pass conditions:
  - Defying Gravity is refused, either by its gap or by the fit.
  - Popular and Domino each show a flagged run where the S-1 record puts the
    mismatch (Popular: the tail; Domino: after line 16), or are refused.
  - On the songs with gap ≈ 0 and few guessed lines (She Used To Be Mine, Stay
    Gold, Lose Yourself, Bloodstream, Soda Pop), the runs are reported raw for Ken
    to judge.

  If the flags can't tell the known-bad songs from the rest, Opus stops for Ken:
  Decision 2's fallback (playback with overlaid lines) would then be the
  question.

  Outcome: the flags as built could not (Results row 10). Ken ruled Decisions 8
  and 9 instead of the fallback.
- [x] GATE A amendment (Opus): split `flagged` into `mistimed` and `unheard`, add
      `unheard_runs`, set the three constants, update the tests and the report
      script; commit `2cde053` `feat(lyrics): an LRC fit tells mistimed lines from
      unheard ones`. Rerun the report and log it (Results row 11).

### Phase 4: mockup -> GATE B (Ken)

- [x] Build an HTML mockup of Repair lyrics with the LRCLIB timing source, styled
      from `song_repair.html`'s own CSS (`rp-*`), and publish it with the Artifact
      tool. The movie-subtitles mockup is the reference: its link is in Results
      row 3 of `git show archive/movie_subtitles:plans/movie-subtitle-slice.md`.
      States to show:
  - picked, with the disk match shown;
  - checking;
  - fits and viable, no flagged runs;
  - fits and viable, with flagged runs (line text with times; use invented lyrics);
  - fits and viable, with an unheard stretch only (the quieter "couldn't check
    these lines" note);
  - fits and viable, with a flagged run and an unheard stretch next to it (a cut
    verse looks like this);
  - fits but the gap is too big (not viable);
  - refused, too few;
  - refused, disagree;
  - no heard words;
  - no LRC on disk (search only);
  - preselected from the tools list;
  - the source when it is `current`.
- [x] **GATE B: Ken ratifies the mockup.** Record his changes in the Results log.
      No page code before this. If the mockup changes what the check returns,
      update the `LrcTimingCheck` fields first.

### Phase 5: storage, plan, Repair (server side)

- [x] Do the Storage and plan section, and the Check and Repair section.
- [x] Tests:
  - `tests/unit/test_library_regen.py`:
    - `_sheet_plan` for all three kinds;
    - saving any one kind removes the other two;
    - Reset keeps a `.lrclib.srt`;
    - a Genius, caption or transcribe Repair removes it;
    - the bulk run sends an LRC-sheet song to `reuse` in every mode, as is tested
      for movie songs;
    - the backup claims `<stem>.lrclib.srt`.
  - `tests/unit/test_library_tools.py`:
    - `check_lrc_timing` gives viable, gap-refused and fit-refused results, uses
      the disk LRC when there is no id, and raises `RegenError` when there is no
      LRC and no id;
    - `repair(source="lrclib")` runs the fit again and refuses on its own result
      (mock `fit_slice` so the second call differs);
    - the bundle records the match.
- [x] Commit: `feat(repair): LRCLIB timing saves a clip-timed sheet on the cue route` (`fffe85b`).

### Phase 6: page, labels, lists

- [x] Build the ratified mockup into `song_repair.html`, and add the route and the
      labels from Routes and page.
- [x] Add the `lrc` list to `SONG_LISTS` and its row in the tools tab, and make
      `_repair_source` prefer `"lrclib"`.
- [x] Route tests: admin only; one JSON response for each card status; Repair runs
      the fit again on the server; `preselect` accepts `lrclib`.
- [x] Commit: `feat(repair): LRCLIB timing as a lyric source on Repair lyrics` (`a014414`).
- [ ] Checkpoint: review moved to after Phase 6.1 (see Checkpoints below).

### Phase 6.1: length override (Decision 11)

Model: Claude Sonnet 5.5. Built on HEAD `4e8cb26`.

- [x] `LrcTimingCheck` (`library_tools.py`) gains `overridable: bool`: the fit is
      `FITS` and `viable` is false, so the gap is over the limit or unknown. Keep
      `viable` as it is.
- [x] `repair(...)` gains `allow_gap: bool = False`, passed to `_lrc_repair_plan`.
      It refuses unless `check.viable or (allow_gap and check.overridable)`, still
      on the check it runs itself. The other sources ignore `allow_gap`.
- [x] `routes/song_info.py`:
  - the LRC card (around line 884) also sends `overridable`;
  - `repair()` reads `allow_gap` from the body. Anything but a JSON boolean is a
    400, the way `_non_number` handles the ids.
- [x] `song_repair.html`: when the card is `overridable`, show a checkbox under
      it, labelled "Use this match anyway". Put the explanation behind an
      `info_tip`, like the card's other notes: "The video is more than 15 s longer
      or shorter than this match. That's fine if the extra is talk, applause or an
      intro before or after the song; those parts get no lyrics. It's wrong if the
      video skips or adds a section at the start or end. The checks above can't
      see that, so listen first." Take the 15 s from `LRC_MAX_GAP_S`, not a
      literal.
  - Regenerate (line 279) is enabled on `viable`, or on `overridable` with the
    box ticked.
  - A new Check fit or a different match clears the box.
  - Send `allow_gap: true` only when the box is ticked.
- [x] Tests:
  - tools: an overridable check with `allow_gap` queues the sheet; without it,
    it refuses; a refused fit refuses even with `allow_gap`; `overridable` is
    false on a viable check and on a refused fit;
  - routes: the card carries `overridable`; a non-boolean `allow_gap` is a 400;
    `allow_gap` reaches `repair`.
- [x] Commit: `feat(repair): an LRCLIB fit that passes may override the length limit` (`6af0f06`).
- [x] Results row, in its own `docs(plans)` commit.
- [x] Checkpoint: review due (see Checkpoints below). Two reviews ran, the whole
      branch (`4a43799^..HEAD`) and then Ken's angles (`b513150^..HEAD`), both on
      `7ba29f3`. Their findings are Phase 6.2.

### Phase 6.2: review fixes

Model: Claude Opus 5.5 (Ken: "I'll do it here"). Built on HEAD `7ba29f3`.

- [x] **LRC sheet cues** (`srt_slice_fit.lrc_to_srt`, `lrclib`), one commit (`dc7b4ca`):
  - duet lines (one start) share a cue on the start as parsed, not as a
    `timedelta` gives it back (01:08.04 lost the first line; 1792 of 30000
    centisecond stamps don't survive the round trip);
  - a blank timed line (LRCLIB's mark for a break) ends the line before it, so
    that line no longer runs across the instrumental. The fill keeps
    `cue_spans_from_lrc` as it is; only the sheet and its fit change.
- [x] **A clamped line is flagged from its clip start** (`srt_slice_fit`, `76f2931`): a
      line the clip cuts into is checked against the start the card shows, not
      its earlier one. `_clip_span` runs once per cue for both. Doesn't move the
      GATE A constants.
- [x] **One table of sheet kinds** (`library_regen`, `c93657f`): `SHEETS`, kind ->
      suffix, origin, label; `sheet_kind`, the sheet files, `sheet_plan` and the
      repair sources read it. Replaces the suffix constants and list,
      `_SHEET_KINDS`, the three plan wrappers, `_SHEET_PLANS` and `SHEET_KINDS`.
- [x] **One `.lrc` reader** (`read_song_lrc`, `3b81aa0`):
  - the status carries the on-disk match (`lrc_match`, replacing `lrc_on_disk`),
    so the repair page reads the file once and `custom_start` stops catching
    `RegenError` for it;
  - the pipeline's two readers (`lyrics_fetch` skip check, `lyric_align` fill)
    use it. An unreadable file still isn't searched over (it was put there on
    purpose): it logs as unreadable and the fill records `unreadable_lrc`, not
    `error`. Skip markers and matches behave as before. `is_skip_marker` and
    `_find_lrclib_lrc` are deleted.
- [x] Small: the flagged-run loop tests a set (in `76f2931`); the snapshot
      docstring says every kind, not both (in `c93657f`).
- Dropped from the sort: the empty LRCLIB search box. All three search boxes
  already refuse an empty query in the page, so the server never sees one.
- Not fixed (reviewed and accepted):
  - the override can apply to a match re-read at Repair time, not the one shown:
    Ken's listen judges the video, and any match that gets through still fits;
  - library status reads every song's `.lrc`: slow only over the VM's share;
  - the card and the saved sheet clean text separately, and can differ on
    all-caps only when the lines outside the clip flip that vote;
  - `_lrclib_results`' old hint said `-> dict` for a Flask response, and the
    route helpers beside it carry none.
- [x] Commits by feature, tests with each; Results row in its own `docs(plans)` commit.
- [x] `scripts/lrc_timing_report.py` before and after: only the fixed rows change
      (none did; Results row 19).
- [x] Checkpoint: review due on 6.2's commits only (see Checkpoints below). Ran
      2026-10-30 (`/code-review high 7ba29f3..HEAD`, Ken's three angles); its
      fixes are Phase 6.3.

### Phase 6.3: review fixes

Model: Claude Opus 5.5 (Ken: "go", fixed in-session). Built on HEAD `233f589`.
Nine findings; Opus sorted them, Ken took the critical and worthwhile ones.

- [x] **The report runs again** (`c8f5369`): `scripts/lrc_timing_report.py` read
      `lrc_on_disk`, renamed to `lrc_match` in `3b81aa0`; it also reads the
      `.lrc` through `read_song_lrc` now.
- [x] **An unreadable `.lrc` is named** (`ac4a42a`): the status has an
      `unreadable` state after `skipped` and before the bundle's record (the
      file blocks every later search, so the disk wins); the list subline, the
      LRCLIB tile (warn) and the pick row name it. `read_song_lrc` logs it at
      debug; the align stage and the repair refusal warn. The fetch stage's log
      names a file gone after `ensure_lrc` as gone.
- [x] **A skip is recorded as a skip** (`cfe1738`): the fill's bundle record says
      `reason: skipped`, not `no_mapping`; the `lrc_file`-only reference stays.
- [x] **History reads `SHEETS`** (`3ab4d13`): `_pick` takes the sheet origins from
      it. The labels stay in `_versions` (its own wording, and the custom kind
      carries an LRCLIB label).
- [x] **Comment** (`fdc4f65`): `LRC_LAST_LINE_HOLD_S` says the LRC sheet uses it too
      and ends a line at a break stamp where the fill doesn't.
- Not fixed (reviewed and accepted):
  - two rules for a line's end: Phase 6.2 kept the fill's spans on purpose;
  - `SongStatus` derives the on-disk match twice (`lrclib` and `lrc_match`):
    merging needs a check that `record_meta` keeps every key the readers use;
  - the fetch stage re-reads the `.lrc` after `ensure_lrc` to pick its log line.
- [ ] Checkpoint: the self-review covers it (small, one read-through each).

### Phase 7: end to end -> Ken's manual checks

Run the app from the worktree (`python -m pikaraoke.app`, with `models/`
symlinked; one instance at a time). Log each step in the Results log.

- [ ] Tools tab: the by-source counts add up to the library total.
- [ ] From the Genius list, use Repair on She Used To Be Mine. The LRCLIB timing
      should come preselected and auto-checked. Regenerate it on the local GPU.
      Then confirm:
  - Song Info's route reads cue align;
  - the song is now in the LRCLIB list;
  - Ken's read of the karaoke.
- [ ] Use Repair on Popular: confirm the flagged run shows and Ken's read of it.
      Don't regenerate unless Ken says to.
- [ ] Use Repair on Domino: confirm the "couldn't check" note shows over lines
      43-50 (its second chorus, 2:14-2:39) and no flagged run does.
- [ ] Defying Gravity: confirm Repair refuses with the gap stated, and that no
      override box shows (its fit is refused).
- [ ] Paradise: the card refuses on length and shows the override box with its
      (i). Tick it, Regenerate on the local GPU, and get Ken's read: no lyrics over
      the talk, and the song lines on time.
- [ ] Reset one repaired song: the `.lrclib.srt` survives and is reused.
- [ ] Update `plans/open-issues.md` in one `docs(plans)` commit:
  - strike the LRCLIB-timing entry and point it at this branch's commits;
  - record point 3's ruling (Decision 4) and GATE A's numbers.

## Rules for the executor

- Plain-language chat. Raw tables and numbers go in the Results log, not in chat
  (CLAUDE.md, Communication).
- Never commit LRC text, real lyrics or report output that contains line text.
  Unit tests use invented lines.
- Tests: `/home/ken/miniconda3/envs/pik/bin/python -m pytest`. Run pre-commit on
  changed files only:
  `pre-commit run --config code_quality/.pre-commit-config.yaml --files <files>`.
- Before each commit, import-smoke the changed modules and read
  `git diff --cached` against the phase's checklist.
- Don't commit `plans/lyric-source-lists.md` together with code. Plan updates go
  in their own `docs(plans)` commits, so landing on `dev` can drop them.
- After code changes: `graphify update .`.
- Stop at GATE A and GATE B. If a step contradicts the code, stop and say so;
  don't reinterpret the plan.

## Checkpoints

- After Phase 1: Ken looks at the tab; flag `/compact`.
- After Phase 3, at GATE A: hand off to Opus with the branch, HEAD, this file's
  "GATE A report output" section, and the instruction to set the three constants
  and log a Results row.
- After Phase 6.1: review due, over the whole branch.
  `/code-review high 4a43799^..HEAD`, files in
  `pikaraoke/lib/{library_status,library_regen,library_tools,srt_slice_fit,lrclib}.py`,
  `pikaraoke/routes/{library,song_info}.py`, and
  `pikaraoke/templates/{processing,song_info,song_repair}.html`. The three finder
  angles:
  1. **Correctness**: is the fit run again on the server, can the override ever
     pass a refused fit, and does a reset keep the sheet kind?
  2. **Simplicity**: one `sheet_kind`, one `_sheet_plan`, no copy of the movie
     card.
  3. **Robustness**: a missing or skip-marker LRC, an LRCLIB network failure, and
     a song that is busy.
- After Phase 6.2: review due on its commits only.
  `/code-review high 7ba29f3..HEAD`, files in
  `pikaraoke/lib/{srt_slice_fit,lrclib,library_regen,library_status,library_tools}.py`,
  `pikaraoke/pipeline/stages/{lyric_align,lyrics_fetch}.py`, and
  `pikaraoke/routes/{library,song_info}.py`. The three finder angles:
  1. **Correctness**: does an LRC sheet keep every sung line (duets, a blank stamp
     at a line's own start, the last line), and does the fill see the same `.lrc`
     text as before?
  2. **Simplicity**: is `SHEETS` the only listing of the sheet kinds, and
     `read_song_lrc` the only reader of a song's `.lrc`?
  3. **Robustness**: an unreadable `.lrc` in the fetch stage, the fill, the status
     and the repair page; a skip marker in the fill's bundle record.

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
| 1 | 2026-10-29 | 0 | `git switch -c lyric_source_lists dev` | Branch at `9e0acfd`. The plan file is untracked. |
| 2 | 2026-10-29 | 0 | Full suite on the branch (`python -m pytest -q`) | Baseline: 2748 passed in 33.84 s. |
| 3 | 2026-10-29 | 1 | Smoke, read-only: `overview_counts(library_statuses(~/pikaraoke-songs))` | `behind 0, poor 4, no_lyrics 2, caption 40, movie 7, genius 15, custom 2, no_timed_source 0, all 66`. The plan's expected five source counts hold. 17 of 17 joint songs have a usable LRC. |
| 4 | 2026-10-29 | 1 | Library changed since the plan's status pass | Every bundle is now schema 11 (64 of 64; 2 songs have none), `behind` is 0, and the six songs the plan marks `none*` now record a match: Popular, Best Part Of Me, In Summer are `rejected`; Domino, NSYNC, Colors of the Wind are `used`. Joint songs: 10 `used`, 7 `rejected`, 0 `none`. The `*` caveat in the Test songs table (gap computed from the LRC file's own duration) no longer applies to those six, so the GATE A report reads the gap from the bundle's record as well as the file and prints both. The table's Source / LRCLIB / gap / guessed columns are the 2026-10-29 morning values. |
| 5 | 2026-10-29 | 1 | Commit `4a43799` `feat(library): lists songs by lyric source, with a Repair link per song`; suite after: 2783 passed (+35) | Existing tests changed for the new shape, not for behaviour: overview counts (status, routes, library_tools), the first list-row dict (gains `repair_url`), the Processing page's list count (4 to 9), and the pinned `chooseSource` line on Repair (now `START_SOURCE`). The tip line "Cue align times each line..." went on the existing Library tip, reading "The info tip gains one line" literally. `repair_url` is built from the path's bytes (`surrogateescape`), because `url_for` raises on a non-UTF-8 file name, which is why `info_url` was already built by hand; a test covers it. |
| 6 | 2026-10-29 | 2 | Commit `b9cdbda` `refactor(library): one sheet_kind for a song's custom sheet`; suite after: 2785 passed | No behaviour change. Readers moved: `library_status.song_status`, `library_regen.custom_plan`, `_Run.undecided_group` and `LibraryTools._now` (`library_tools.py`), `song_info._current_source`. `_Entry` and `_regen_job` read neither flag. The only test changes are the `TestCustomSheet` field renames in `test_library_status.py` (the old assertions on `custom_sheet` / `movie_sheet` became `sheet_kind`), plus two new `library_regen.sheet_kind` tests (suffix to kind; `None` and a non-sheet file give `None`). Open-issues strike-through: `docs(plans)` commit after `b9cdbda`. |
| 7 | 2026-10-29 | 3 | Commit `34a806e` `feat(lyrics): an LRC fits to the clip with flagged lines`; suite after: 2804 passed (+19) | 19 new tests, all on synthetic cues (`TestLrcToSrt` 2, `TestFlaggedLines` 10, `TestFlaggedRuns` 7); the 29 tests that were in `test_srt_slice_fit.py` pass unchanged. Two things differ from the plan's wording. (1) `flagged` numbers the lines the pipeline loads from `fit.srt`, not the raw cues of the corrected SRT: a cue that cleans to nothing (an LRCLIB `♪` line) is no line, and `cue_spans_from_srt` drops it where `_corrected_srt` keeps it, so raw cue numbers and line numbers part ways after one. Phase 6 should read the line text from `cue_spans_from_srt(fit.srt)`. A test pins it. (2) The flag rule is a helper, `_flagged_lines`, called from `_fit_one_stream`; it uses the pass-2 anchors, and the "not found" test is the anchor lookup, because the anchors are exactly the found cues. Two mutations checked by hand: dropping the time rule fails 2 tests; numbering by cue index instead of by place in the clip survived until the "lines before the clip" test was added, then failed it. |
| 8 | 2026-10-29 | 3 | What the flags do for an extra repeat (synthetic, 30 lines, spread 0, 30 of 30 found in all three) | Chorus of 4 lines sung twice in the video, once in the LRC. Repeat at lines 24-27: shift 0.0 s, flagged 28, 29 (a 2-line run, under `MIN_FLAGGED_RUN`). Repeat at 14-17: shift +20.0 s, flagged 0-13 (one run of 14). Repeat at 4-7: shift +20.0 s, flagged 0-3. The fit passes every one, so the spread check does not see them. The flags mark whichever side of the repeat holds the minority of lines, since the median timing follows the majority; a repeat late in the song flags the lines after it, one mid-song flags the lines before it. No verdict asserted; `test_what_the_flags_do_for_an_extra_repeat` records it. |
| 9 | 2026-10-29 | 3 | Commit `0ae28a3` `feat(scripts): report the LRC fit and flagged lines for every joint song`; ran `python scripts/lrc_timing_report.py` read only (nothing in `~/pikaraoke-songs` newer than the script afterwards) | Raw output is in "GATE A report output" below: 17 joint songs with a usable LRC, 23 stream rows (transcribe for all 17, ASR for 6). 18 rows fit, 4 refuse as `disagree` (Defying Gravity both streams, Soda Pop, Bloodstream transcribe), 1 refuses as `too_few` (Jay Chou, 0 of 53 found). Gap from the bundle and from the LRC file agree on every row. The Test songs table's `?` gaps are now known: Popular +13, Domino -1, Best Part Of Me -1, In Summer +1, NSYNC -38, Colors of the Wind +8. Pass-condition songs, at 2.0 s: Defying Gravity refused by the fit (spread 4.1 s) and by its +97 s gap; Popular fits on both streams with flagged run 52-61 (the last 10 of 62 lines), the ASR stream also flagging 0, 1, 37; Domino fits with flagged 35, 39, 43-50, 67-68. Gap-near-0 songs: She Used To Be Mine 1 flagged (19), no run; Stay Gold none at 2.0 s (3 at 1.0 s); Lose Yourself 5 flagged (0, 32, 50, 59, 73), no run; Bloodstream transcribe refused, ASR fits 28/57 with 35 flagged in runs 15-22 and 31-56; Soda Pop transcribe refused (its only stream). Two things the numbers show that the plan did not anticipate: Defying Gravity and Popular both land on speed 0.9590, the movie fit's PAL factor, which scales the LRC's clock down by 4% (for Popular, whose LRC is 13 s longer than the video); and NSYNC fits (49/56, shift +23.93 s) with a -38 s gap, so a passing fit alone does not see the gap. No thresholds chosen. |
| 10 | 2026-10-29 | 3 (GATE A) | Opus read of the report, plus a read-only scratch probe (not committed) that prints, for each fit, every in-clip line's fitted start against its anchor's start, and the heard words inside the line's window | By the letter, at the placeholders: Defying Gravity is refused by the fit on both streams (and has a +97 s gap); Popular shows run 52-61 (the tail); Domino shows run 43-50 (after line 16). The probe splits flagged lines into two kinds: **heard elsewhere** (an anchor more than 2.0 s from the fitted start) and **unheard** (no anchor). Lines heard 10 s or more from their fitted start occur on two rows only: Popular (transcribe 53-56 at -15 to -19 s; ASR 53, 54, 56, 60, 61 at -14 to -19 s) and Bloodstream ASR (31, 32, 37, 38, 52 at -21 to -23 s). The largest anywhere else: NSYNC 54 at -9 s, Your Idol 46 at -8 s; every other heard-elsewhere line is within 4 s (Takedown 20, 21, 29, 37 at -3 to -4 s; Lose Yourself 0 at -4 s; Best Part ASR 15, 28, 33 at +2 to +3 s; Best Part transcribe 34 at -3 s). Unheard lines per row: Popular 7 / 7 (transcribe / ASR), Best Part 4 / 11, Bloodstream ASR 29, Lose Yourself 4, Domino 12, NSYNC 7, Your Idol 18, Golden 9, Takedown 9, Seven 3 / 9, In Summer, Colors of the Wind (both), She Used To Be Mine and Stay Gold 0. Domino's run 43-50 is unheard lines only: the transcribe stream holds no word from 134.0 s to 164.8 s, lines 42 and 51 either side sit +0.1 s and +1.7 s from their fitted starts, and no heard line of Domino is more than 1.7 s off. Its LRC on disk (gap -1 s) is not the "UK Radio Edit" S-1 recorded. Your Idol 0-10 and 28-36, Golden 0-2 and Best Part transcribe 0-2 are unheard runs too (0-3 heard words in each line's window), over an intro chant, Korean lines and a sung intro. Gaps of the rows that fit with no line heard 10 s or more off: Seven -14, Colors of the Wind +8, Takedown -10, Your Idol -14, NSYNC -38; Popular, which has such lines, is +13. Constants not set; GATE A stopped for Ken: under the built rule, run length does not set Popular's 10-line run apart from Your Idol's 11- and 9-line runs or Domino's 8, and Domino's run is a stretch the transcriber did not hear. |
| 11 | 2026-10-29 | 3 (GATE A) | Ken ruled Decisions 8 and 9 (split the flags; gap limit 15 s). Commit `2cde053` `feat(lyrics): an LRC fit tells mistimed lines from unheard ones`; suite after: 2812 passed (+8). Reran `python scripts/lrc_timing_report.py` read only; output in "GATE A report output, after the ruling" below | Constants: `FLAG_TOLERANCE_S` 5.0, `MIN_FLAGGED_RUN` 2, `MIN_UNHEARD_RUN` 3, `LRC_MAX_GAP_S` 15 (Phase 5, not coded). Test changes in `test_srt_slice_fit.py`: the "cut verse" test was a stretch the transcriber missed (heard words removed, times unchanged), so it became `test_a_stretch_nobody_heard_is_unheard_and_flags_no_run`; a new cut-verse test has the video skip six lines so the later ones come early (mistimed 24-29, unheard 18-23, flagged run 24-29). The extra-repeat record became a requirement: all three repeats now leave a flagged run (28-29, 0-13, 0-3), where at 2.0 s with unheard lines counted the late one gave only a 2-line run under the old `MIN_FLAGGED_RUN` 3. `TestFlaggedRuns` covers the new rule (an unheard line does not end a run, does not count toward it, and is not part of its edges); `TestUnheardRuns` takes the old consecutive-run cases. One mutation checked by hand: letting an unheard line end a run fails `test_unheard_lines_between_mistimed_ones_do_not_end_a_run`. The script's mode was 644 with a shebang (pre-commit's shebang hook failed on it); now 755, as `movie_srt_fit_report.py` is. Rerun, at the new constants: flagged runs on two rows only, Popular (transcribe 53-56, ASR 53-61) and Bloodstream ASR (31-52). Mistimed lines elsewhere: NSYNC 54 and Your Idol 46, one each. Unheard runs: Popular 57-61 / 57-59, Best Part 0-2 / 29-32 34-36, Bloodstream ASR 15-22 33-36 39-51 53-56, Domino 43-50, Your Idol 0-9 28-35, Golden 0-2, Takedown 0-3, Seven ASR 45-47. Mistimed lines at 3-10 s tolerance: Popular and Bloodstream unchanged from 4.0 to 10.0 s; at 3.0 s Takedown gains 29, 37, Best Part 34 / 33, Lose Yourself 0, Bloodstream 10. With `LRC_MAX_GAP_S` 15, the fit's best stream gives viable for Popular (+13, run 53-56), Best Part, Bloodstream (ASR, run 31-52), Lose Yourself, Domino, In Summer, Colors of the Wind (+8), She Used To Be Mine, Stay Gold, Your Idol (-14), Golden, Takedown (-10), Seven (-14); not viable: Defying Gravity (refused, +97), Soda Pop (refused), NSYNC (-38), Jay Chou (refused). Phase 7 gains a Domino check. |
| 12 | 2026-10-29 | 4 | Mockup published as a Design (artboard) Artifact: https://claude.ai/artifact/LJ6fQCTj7bCMi6sjcHrqva (private; Ken's account). Built from the app's dark tokens and the `rp-*` rules of `song_repair.html`; the movie-subtitles mockup (Results row 3 of `archive/movie_subtitles`) is the model. | 15 boards, 420 px wide, one component (`Main`) drawing the whole Repair page, every state a preset of it. **Try it** (`Main`, clickable: a mock-only strip picks what the next Check fit returns, Check fit shows "checking" for 0.9 s, Regenerate turns on only for a viable answer, Search LRCLIB opens the list, picking another match clears the answer, every (i) opens). Static boards, numbered as the plan's list: 1 picked with the disk match shown; 2 checking; 3 fits, no flagged runs; 4 fits with flagged runs (two runs); 5 fits with an unheard stretch only; 6 fits with a flagged run next to an unheard stretch; 7 fits but the length is too far off; 8 refused, too few; 9 refused, disagree; 10 no heard words; 11 no LRC on disk (search only); 12 opened from a list; 13 the source when it is current; plus a last board listing every (i) note's wording, since static boards cannot be hovered. Invented song ("Harbor Lights", "The Lantern Fields") and invented lyrics only. **Not rendered, screenshotted or syntax-checked** (the Design type forbids verifying unless asked; no `node` on the box). Risks if a board looks wrong: the `dc-import` of `Main` with a `variant` prop, style holes (`border-top`, `border`, `opacity`) and a `value=` on a read-only input. |
| 13 | 2026-10-29 | 4 | What the mockup commits to (for Ken to ratify at GATE B) | (a) **Where**: a new source card "LRCLIB timing" between Movie subtitles and No lyrics, description "Time the song from an LRCLIB match's own line times." (b) **Section**: title with an (i); the match on disk as one row (title, artist and album, length like "3:31 · within a few s", an "on disk" tag, no "matches x of y" until a search is open); a "Search LRCLIB" link that opens the step-2 search box and results (rows as in step 2, "best fit" and "on disk" tags, "matches x of y lines" per row); Check fit; the answer; the usual buttons. With no LRC on disk (board 11) the row and link are gone and the search is open at once, best fit picked. (c) **Heads**: "Fits. This match can time this song." (green) for a clean fit or an unheard stretch only; "Fits, but check these lines first." (amber) when a flagged run shows, **Regenerate stays on** (Decision 4: Ken sees the lines, then confirms); "The lines fit, but the length is too far off." (amber, Regenerate off); "Doesn't fit." (amber, Regenerate off) with the hint behind an (i); "Can't check yet." (blue) with a Go to Song info link, worded as the movie card. (d) **Lines** reused from the movie card: "matches x of y lines", "Line times move h:mm:ss earlier/later" (the movie card says "Subtitle times"), "Speed adjusted by x%." with its (i). New: the length line, reusing `_lrclib_fit`'s wording ("The match is 3:44; this video is 3:31 (13 s longer)."), and "No line was heard far from its time." when nothing is flagged, so a clean fit says the check ran. Not drawn in any state: the movie card's "n lines fall outside the clip and are dropped." line, which would still print when `fit.dropped` is above 0. (e) **Flagged runs** (amber, with a warning mark): "Heard far from where this match puts them" with an (i); each run a header "m:ss–m:ss · n lines" and its lines as "m:ss text" in a dark box capped near six lines, then scrolling. Times are the lines' fitted clip times; no line numbers shown. **Unheard stretches** (muted, no mark): "Couldn't check these lines" with an (i), same list shape, below the flagged runs. (f) **Length colour**: the match row keeps step 2's 5 s rule (amber from 5 s), the card's length line turns amber only past the 15 s limit. So at +13 s (board 4) the row is amber, the card line is plain and Regenerate is on; if that reads as a contradiction, the row could follow the 15 s limit instead. (g) The row's "matches x of y lines" (candidate text against the song's lyrics) and the card's (heard words against the clip) share wording and differ in meaning. (h) Greys `#a3b0b2` and info blue `#5cb0ee` carried over from the ratified movie mockup. (i) Board 12 is board 3 reached without a click, so the only visible difference is the caption card still saying "Checking the caption…". (j) Board 13: "current" tag on the card, idle line "This is the saved timing. Check fit confirms it, then Regenerate turns on." (a saved sheet needs a re-check, as the saved movie slice does). (k) **No `LrcTimingCheck` field change**: the runs' text and times come from `cue_spans_from_srt(fit.srt)` indexed by `fit.mistimed` and `fit.unheard` (row 7: the numbering is the lines the pipeline loads), and the other lines from `SliceFit` fields the movie card already reads. |
| 14 | 2026-10-29 | 4 (GATE B) | Ken: "ratified". Applies to the Artifact as built (https://claude.ai/artifact/LJ6fQCTj7bCMi6sjcHrqva, version 17, rows 12-13). | No changes asked, so no `LrcTimingCheck` field change. Takes the open calls at the mockup's choices: Regenerate stays on with a flagged run; unheard stretches muted below the runs; the match row's 5 s colour rule beside the card's 15 s limit; the movie card's lines reused plus the length line and "No line was heard far from its time."; a current source needing a re-check before Regenerate. The Artifact was never rendered, so Phase 6 builds from the markup in rows 12-13 and the live page's own CSS, not from a screenshot. Phases 5-6 next. |
| 15 | 2026-10-29 | 5 | Commit `fffe85b` `feat(repair): LRCLIB timing saves a clip-timed sheet on the cue route` (`library_regen.py`, `library_tools.py`, `test_library_regen.py`, `test_library_tools.py`, `tests/unit/movie_slices.py`); suite after: 2870 passed (+58) | **Built as planned**: `LRC_SRT_SUFFIX` in `CUSTOM_SHEET_SUFFIXES` (so backups, Reset, scoped wipes and the put-back all take it with no further change), `LRC_ORIGIN`, `_sheet_plan` under the three sheet plans, `custom_plan` dispatching on `sheet_kind` through a table, `LrcTimingCheck`, `LrcTimingRefused`, `LRC_MAX_GAP_S` 15, `check_lrc_timing`, `repair(source="lrclib")`, `replaces_custom` false for it. **Different from the plan's wording**: (1) the LRC repair does not call `_apply_lrclib_pick`. The match is read once (`_lrc_record`: the record by id, else the `.lrc` on disk) and the same record is fitted and, when it came by id, set as `plan.lrclib_record`, so the lines fitted are the lines saved (a second lookup could differ). `_apply_lrclib_pick` and the LRC path now share one `_lrclib_record` lookup. (2) The movie and LRC checks share `_fit_to_clip` and `_clip_length`; `_fit_movie_slice` was reduced to use them. (3) **The bundle does not note which LRC timed the song.** `lyrics.lrclib` is written only by the joint route (`pipeline/stages/lyric_align.py`, `capture_method_used == "joint"`), so a cue run records nothing; the `.lrc` on disk with its header is the only record. The plan's "so the bundle notes which LRC timed it" does not happen, and `lrclib_state` will read `none` for an LRC-timed song until Phase 6 reads the `.lrc` instead. **Left for Phase 6** (the plan's label list lacks them): `library._now_text` has no `lrc` wording (it reads "Now: no recorded lyric source"); the `movie_srt` origin tests in `song_info.py` (`_source_name`, `_route_text`, History) need `lrclib_srt`; the card needs a line for a match with no length (`gap_s` None is not viable, no mockup state) and for `not_srt` (an LRC with no timed lines must not say "Not an SRT file"). `repair` already passes `source` through, so `source="lrclib"` is reachable by an admin POST now; the route must parse `lrclib_id` as an int. **Tests**: 58 new. `test_library_regen.py`: the three plan shapes; resolve and reuse prefer an LRC sheet; saving any one kind leaves only that kind; a repair to caption, Genius or transcribe removes an LRC sheet; Reset and the scoped wipe keep it; the scoped backup claims `<stem>.lrclib.srt` and not a sibling's; the seed origin and no third source; a reset replays it; the put-back restores it. `test_library_tools.py` (`TestLrcTimingRepair`, `TestRunsReplayLrcSheets`; `lrc_slice` added to `movie_slices.py`, invented words): the disk LRC and a record by id are checked; a listed record is not asked of LRCLIB again; the gap at 0, +15, -15 (viable) and +16, -16 (not); no length is not viable; a refused fit and an LRC with no stamps are not viable; no heard words; flagged lines (8-11) come back and do not stop a viable fit; no LRC, a skip marker, an unreadable LRC, a gone or unsynced record, an unreadable clip length, an audio file and a busy song are each refused; the saved sheet is in clip time (an LRC 3 s late); the `.lrc` stays unless the record came by id; a refusal leaves the queue, the backups and an old sheet alone; a second fit that differs is the one the repair obeys; bulk runs send an LRC-sheet song to `reuse` in every mode and queue its plan. **Mutations checked by hand** (source changed, a test failed, source restored): gap limit exclusive; gap ignored; fit status ignored; a non-viable check queued; the raw LRC saved instead of the fit; the record always put on the plan; `lrclib` left out of `replaces_custom`; the skip-marker check removed; the repair using the disk record instead of the id; `lrc` replayed as the movie plan; the LRC suffix left out of the sheet suffixes; the origin changed; `is_custom_plan` widened to the LRC origin. All 13 caught on the first run. |
| 16 | 2026-10-29 | 6 | Commit `a014414` `feat(repair): LRCLIB timing as a lyric source on Repair lyrics` (13 files: `library_regen`, `library_status`, `library_tools`, `routes/library`, `routes/song_info`, the `processing`, `song_info` and `song_repair` templates, five test files); suite after: 2948 passed (+77) | **Built to the ratified mockup** (rows 12-14): the "LRCLIB timing" source card between Movie subtitles and No lyrics; the section with the match on disk as one row ("on disk" tag), a Search LRCLIB link, Check fit, the card (head, matches, length, move, speed, dropped, "No line was heard far from its time."), the flagged runs in amber and the "Couldn't check these lines" note muted below them, each stretch as "m:ss-m:ss · n lines" with its lines and clip times; Regenerate only on a viable answer; a list's link opens it already checked. New: `POST /song_info/lrc_fit`, `GET /song_info/lrc_search` (matches scored against the bundle's current lines, `LibraryTools.current_lines`), `repair` mapping `LrcTimingRefused` to the card's words, `custom_start()["lrc"]` for the match on disk, the `lrc` list and its Tools-tab row ("LRCLIB · cue align"), `_repair_source` preferring `lrclib` when `lrc_on_disk`. **Different from the plan or the mockup**: (1) the sheet kind is `"lrclib"`, not `"lrc"`, the page's own source name, so `_current_source` and `_now` need no mapping (the `lrc` list keeps its key). (2) `LrcTimingCheck` gained `clip_s`: row 13 (k) said no field change, but the length line names the video's length, which the check alone did not carry. (3) Labels beyond the plan's list, found in Phase 5: the run page's "Now: LRCLIB timing"; Song Info's LRCLIB tile ("Timing · times this song") and pick row; `SongStatus.lrclib` for an LRCLIB-timed song is read off its `.lrc` header, since a cue run's bundle records none. (4) Wording the mockup had no state for: a match with no length ("The lines fit, but the match has no length to check.", no length line), an LRC with no timed lines ("This match has no timed lines.", not "Not an SRT file"), more than 3,000 lines, and no lines to check. (5) "No line was heard far from its time." shows only when nothing is mistimed at all and no stretch is shown, so a single mistimed line (below `MIN_FLAGGED_RUN`) does not make it a false claim; the mockup's wording was "when nothing is flagged". (6) `_repair_source` follows Decision 6 literally: any song with a usable LRC opens on LRCLIB timing, including a caption-timed song that still has a leftover `.lrc` from an earlier Genius run. (7) The movie card's markup and script are now shared: one `answer_area` macro and one `showCard(prefix, card)`, and one `matchOption` row builder for step 2's list and this one; three tests that pinned the old names (`showMovieCard`, `el('li', null, ...)`, the `inArray` list) changed with them. (8) With no match on disk the search is open from the start (no search runs until asked, the box starts from the Genius title and artist); a search picks its best fit and clears any answer; with the search closed only the picked row shows. **Checked in a real browser, beyond the unit tests**: a scratch harness (`scratchpad/lrc_page_smoke.py`, not committed) serves the real routes and templates over a synthetic library (invented words, no network) and drives them in headless Chromium: a list link auto-checks and Regenerate queues the lrclib plan (record None, sheet in clip time); a run beside an unheard stretch; an unheard stretch alone; a length 38 s off (Regenerate off, length line amber); no LRC on disk, search, pick, check, then another pick drops the answer; the current-source line; no heard words (link shown); a refusal. Screenshots read: they match the mockup. No page script errors; the only console errors are 404s for socket.io, which the harness does not serve. **Tests**: 77 new, in `test_library_routes.py` (`TestLrcCard` 18, `TestLrcFitRoute`, `TestLrcSearchRoute`, `TestLrcRepairRoute`, page, Song Info, History, lists, run view), `test_library_status.py` (`TestLrclibTimedMatch`), `test_library_tools.py` (`custom_start`'s match, `current_lines`, `clip_s`). **Mutations checked by hand** (22, source changed, a test failed, source restored; all caught on the first run): the link no longer preferring lrclib; lrclib left out of the preselectable sources; a run no longer the warning; one mistimed line claiming all was well; the length line not marked; `lrc_fit` open to guests; the Repair not catching the refusal; a run losing its last line; the `lrc` list rule; the match not read off the `.lrc`; Song Info hiding the LRCLIB row; the search scored against no lines; the run page's wording; a refusal without its length line; the length line first; the page sending no id; a new pick keeping the answer; Regenerate ignoring `viable`; no auto-check from a list; Regenerate sending no id; the match not handed to the page; the check without the clip length. **Not done**: translation catalogs (they go in their own i18n commits); a length comparison on Song Info's Alignment tab for an LRCLIB-timed song. Phase 5's note that the route must parse `lrclib_id` was already true (`repair` validated it); `lrc_fit` shares the check. |
| 17 | 2026-10-29 | 6 (after) | Ken ruled Decision 10 (Decision 6 limited to joint songs), answering row 16 (6). Commit `9cb2465` `fix(library): a list's Repair link picks a source only for joint songs`; suite after: 2950 passed (+2) | `_repair_source` returns None for any song whose method is not `joint`, else `lrclib` with an LRC on disk, else `caption`. Songs that lose their picked source: a cue song with a leftover `.lrc`; an LRCLIB-timed song (its Repair page still opens on its current source, LRCLIB timing, without the auto-check); a song with no bundle. Joint songs are unchanged (row 16's Genius-list check still applies in Phase 7). Two tests added (a leftover-LRC cue song; an LRCLIB-timed song). One mutation checked by hand: the old rule back in place fails both. |
| 18 | 2026-10-30 | 6.1 | Commit `6af0f06` `feat(repair): an LRCLIB fit that passes may override the length limit` (`library_tools`, `routes/song_info`, `song_repair.html`, `test_library_tools`, `test_library_routes`); suite after: 2982 passed (+27, from 2955 at `4e8cb26`) | **Built as planned**: `LrcTimingCheck.overridable` (`FITS` and not `viable`, so the gap is over the limit or unknown; `viable` unchanged), `repair(allow_gap=False)` into `_lrc_repair_plan`, which refuses unless `check.viable or (allow_gap and check.overridable)` on the check it runs itself, the card's `overridable`, `repair()` reading `allow_gap`, and the page's "Use this match anyway" box under the card (shown when overridable, Regenerate on for `viable` or an overridable card with the box ticked, the box cleared by a new Check fit or another pick, `allow_gap: true` sent only when ticked). **Different from the plan's wording**: (1) the card also carries `override_tip`, the (i) text built on the server, so the 15 s is `LRC_MAX_GAP_S` and not a literal in the page; the plan's wording is verbatim for a match over the limit. (2) A match with no length is overridable too (plan: "over the limit or unknown"), and "The video is more than 15 s longer or shorter" would be false for it, so its tip opens "The match has no length, so the video can't be compared with it." and carries the plan's remaining sentences unchanged. (3) A non-boolean `allow_gap` is a 400 "allow_gap must be true or false", written as the `lrclib_skip` check beside it, not through `_non_number` (that helper is for whole numbers; two copies of the boolean check is under the third-copy bar). A JSON `null` is a 400, as for `lrclib_skip`. (4) One existing page test pinned "Regenerate on only for `viable`"; it is replaced by two (the enable rule, and the body Regenerate sends). **Tests**: 27 new. Tools: `overridable` on a viable check (false), over the limit and no length (true), a refused fit at gap 0 and +53 and no heard words (false); an overridable fit queues the sheet with `allow_gap` for a 38 s gap and for no length, and refuses without it (default and `False`); `allow_gap` changes nothing for a viable match; a refused fit stays refused with it; the second fit the repair runs itself, when it differs, still refuses with it; a transcribe repair ignores it. Routes: the card's `overridable` and tip (over the limit, no length, and not for clean, flagged, too few, not SRT, no reference); the preview route's `overridable`; the repair route queues a 38 s fit only with `allow_gap: true`, refuses a refused fit with it, and 400s `"true"`, 1, 0, `null`, `[True]`; a Genius repair 400s a bad `allow_gap` too; page pins for the enable rule, the body sent, the box under the card with its note and its clearing. **Mutations checked by hand** (8, source changed, a test failed, source restored; all caught on the first run): `allow_gap` alone passing a refused fit; `allow_gap` ignored; `overridable` passing without `allow_gap`; `overridable` ignoring the fit status; the route dropping `allow_gap`; the card never overridable; the page always sending `allow_gap`; a new pick leaving the box ticked. **Checked in a real browser** (the VM's `ui-check` app, a synthetic library of empty video files with invented words, a scratch script not committed): a clean fit shows no box and Regenerate on; a refused fit shows no box and Regenerate off; a 38 s gap shows the box with its (i) (text as above), Regenerate off until ticked, a new Check fit unticks the box and turns Regenerate off again, and Regenerate with the box ticked posts `{source: lrclib, lrclib_id: null, allow_gap: true}` and lands on Song info; a match with no length shows the box with its own (i). Screenshot read: the box sits under the card, label and (i) on one line. No page script errors; the one console error is a 404 on the Song info page the repair redirects to (not in the app log). **Not done**: translation catalogs (own i18n commit); Phase 7's Paradise check, which needs the real song on the GPU box. |
| 19 | 2026-10-30 | 6.2 | Two `/code-review high` runs on `7ba29f3` (whole branch `4a43799^..HEAD`; Ken's angles `b513150^..HEAD`), sorted by Opus with Ken's "go". Commits: `dc7b4ca` `fix(repair): an LRC sheet keeps duet lines and ends a line at a break`; `76f2931` `fix(repair): a line the clip cuts into is checked from the clip's start`; `c93657f` `refactor(library): the custom sheet kinds are one table`; `3b81aa0` `refactor(library): every reader of a song's .lrc goes through read_song_lrc`. Suite after: 2987 passed (+5 from 2982). `scripts/lrc_timing_report.py` on the D: library before (at `7ba29f3`) and after `dc7b4ca` and `76f2931`: identical output, 39 lines. Library sizing for the break fix: 21 of 24 `.lrc` files carry a blank timed line; 25 blank stamps follow a sung line, the gap to the next line is >=5 s for 10, >=10 s for none, max 9.4 s. Duet round trip: 1792 of 30000 centisecond stamps (0:00.00-4:59.99) do not survive `timedelta(seconds=t).total_seconds() == t`; 01:08.04 reproduced the lost line. | Seven fixes from the sort became four commits (fix 4, the empty search box, dropped: all three search boxes refuse an empty query in the page). The report is unchanged because it shows verdicts and flags; the break fix moves line ends and no library LRC hit the duet round trip or a clamped first line. Not fixed, as listed under Phase 6.2: override match re-read, status reading every `.lrc`, card vs saved-sheet cleaning on all-caps, `_lrclib_results` hint. No GPU run; the break fix reaches LRCLIB-timed songs at their next Regenerate. |
| 20 | 2026-10-30 | 6.3 | `/code-review high 7ba29f3..HEAD`, Ken's three angles (correctness, simplicity, robustness): 9 findings, sorted by Opus, Ken's "go". Commits: `c8f5369` `fix(scripts): the LRC timing report reads the status's lrc_match`; `ac4a42a` `fix(library): an unreadable .lrc shows as unreadable, not as no match`; `cfe1738` `fix(align): a skip marker is recorded in the bundle as a skip`; `3ab4d13` `refactor(song_info): the History tab takes the sheet origins from SHEETS`; `fdc4f65` `docs(lrclib): the last-line hold is shared with the LRC sheet`. Suite after: 2989 passed (+2 from 2987). `scripts/lrc_timing_report.py` on the D: library at `76f2931` (worktree) and after `c8f5369`: identical output, 39 lines; at `3b81aa0`..`233f589` it raised AttributeError. | Findings on the correctness angle (duet lines, a blank stamp at a line's own start, the last line, the fill's `.lrc` text): none. One existing test pinned an unreadable `.lrc` falling through to the bundle's `rejected`; it now pins `unreadable`. The repair's unreadable test pinned the `read_song_lrc` warning; the repair refusal warns itself now. Not fixed, as listed under Phase 6.3. No GPU run; no browser check (the new state is two labels and a tile, pinned by route tests). |

## Hand-off prompt (executor)

> Execute `plans/lyric-source-lists.md` from Phase 0 on branch
> `lyric_source_lists` (already created off `dev`). Phases 1-2 are
> self-contained; commit each one. Phase 3 ends at GATE A: stop and hand the
> report to Opus, and don't choose thresholds. Phase 4 is a mockup published as
> an Artifact; stop at GATE B for Ken. Log every phase's raw results in the
> plan's Results log. LRC and lyric text never go into a commit.

## GATE A report output

Raw output of `python scripts/lrc_timing_report.py` on 2026-10-29, at `34a806e` plus
the script, with the placeholders in force (`FLAG_TOLERANCE_S` 2.0, `MIN_FLAGGED_RUN` 3).
Read only. Line numbers count the lines the pipeline loads from the LRC's own text
(the LRC is the sheet), so they are not the Genius sheet's numbers that the S-1 record
uses. The "Gap s" columns are how many seconds longer the match is than the video.

Placeholders in force: FLAG_TOLERANCE_S=2.0, MIN_FLAGGED_RUN=3, MIN_MATCHED_SHARE=0.25. 17 joint songs with a usable LRC in /home/ken/pikaraoke-songs.

| Song | Origin | LRCLIB | Heard | Words | Clip s | Status | Matched | Shift s | Speed | Spread s | Anchors | Gap s (bundle) | Gap s (file) | Flagged | Runs>=2 | Runs>=3 | Runs>=4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 'Defying Gravity' - Wicked 20th Annivers | custom | rejected | transcribe | 267 | 257 | refused/disagree | 45/89 | -69.25 | 0.9590 | 4.113 | 45 | +97 | +97 | - | - | - | - |
| 'Defying Gravity' - Wicked 20th Annivers | custom | rejected | asr | 233 | 257 | refused/disagree | 36/89 | -67.14 | 0.9590 | 4.100 | 36 | +97 | +97 | - | - | - | - |
| 'Popular' - Wicked 20th Anniversary Edit | genius | rejected | transcribe | 319 | 211 | fits | 55/62 | -12.02 | 0.9590 | 0.227 | 55 | +13 | +13 | 11: 0,52,53,54,55,56,57,58,59,60,61 | 52-61 | 52-61 | 52-61 |
| 'Popular' - Wicked 20th Anniversary Edit | genius | rejected | asr | 312 | 211 | fits | 55/62 | -11.90 | 0.9590 | 0.182 | 55 | +13 | +13 | 13: 0,1,37,52,53,54,55,56,57,58,59,60,61 | 0-1 52-61 | 52-61 | 52-61 |
| 'Soda Pop' Official Lyric Video _ KPop D | genius | rejected | transcribe | 209 | 170 | refused/disagree | 31/59 | 15.27 | 1.0000 | 0.830 | 31 | +0 | +0 | - | - | - | - |
| Ed Sheeran - Best Part Of Me (feat. YEBB | genius | rejected | transcribe | 234 | 248 | fits | 34/38 | 2.21 | 0.9859 | 0.334 | 34 | -1 | -1 | 5: 0,1,2,32,34 | 0-2 | 0-2 | - |
| Ed Sheeran - Best Part Of Me (feat. YEBB | genius | rejected | asr | 213 | 248 | fits | 27/38 | 1.78 | 0.9888 | 0.539 | 27 | -1 | -1 | 14: 1,6,7,15,27,28,29,30,31,32,33,34,35,36 | 6-7 27-36 | 27-36 | 27-36 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | custom | rejected | transcribe | 324 | 247 | refused/disagree | 38/71 | -10.88 | 1.0000 | 1.095 | 38 | +0 | +0 | - | - | - | - |
| Ed Sheeran & Rudimental­ - Bloodstream [ | custom | rejected | asr | 231 | 247 | fits | 28/57 | -10.24 | 1.0000 | 0.560 | 31 | +0 | +0 | 35: 10,15,16,17,18,19,20,21,22,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56 | 15-22 31-56 | 15-22 31-56 | 15-22 31-56 |
| Eminem - Lose Yourself | genius | used | transcribe | 777 | 328 | fits | 89/93 | -0.51 | 1.0000 | 0.200 | 89 | -1 | -1 | 5: 0,32,50,59,73 | - | - | - |
| Jessie J - Domino (Official Video) | genius | used | transcribe | 330 | 235 | fits | 57/69 | -0.43 | 1.0000 | 0.184 | 57 | -1 | -1 | 12: 35,39,43,44,45,46,47,48,49,50,67,68 | 43-50 67-68 | 43-50 | 43-50 |
| Josh Gad - In Summer (From 'Frozen'_Sing | genius | rejected | transcribe | 212 | 113 | fits | 21/21 | -0.44 | 1.0000 | 0.156 | 21 | +1 | +1 | - | - | - | - |
| NSYNC - Paradise | genius | used | transcribe | 339 | 305 | fits | 49/56 | 23.93 | 1.0000 | 0.280 | 49 | -38 | -38 | 8: 0,1,33,42,43,50,54,55 | 0-1 42-43 54-55 | - | - |
| Pocahontas - Colors of the Wind (Blu-ray | genius | used | transcribe | 311 | 203 | fits | 37/37 | -6.38 | 1.0000 | 0.300 | 37 | +8 | +8 | - | - | - | - |
| Pocahontas - Colors of the Wind (Blu-ray | genius | used | asr | 310 | 203 | fits | 37/37 | -5.98 | 1.0000 | 0.100 | 37 | +8 | +8 | - | - | - | - |
| Sara Bareilles - She Used To Be Mine (Of | genius | used | transcribe | 295 | 253 | fits | 45/45 | -0.20 | 1.0000 | 0.228 | 45 | +0 | +0 | - | - | - | - |
| Stay Gold (Official Music Video) from Th | genius | used | transcribe | 280 | 246 | fits | 51/51 | -0.06 | 1.0000 | 0.054 | 51 | +0 | +0 | - | - | - | - |
| ‘Your Idol’ Lyric Video _ KPop Demon Hun | genius | used | transcribe | 300 | 206 | fits | 41/59 | -0.15 | 1.0000 | 0.150 | 41 | -14 | -14 | 21: 0,1,2,3,4,5,6,7,8,9,10,28,29,30,31,32,33,34,35,36,46 | 0-10 28-36 | 0-10 28-36 | 0-10 28-36 |
| “Golden” Official Lyric Video _ KPop Dem | genius | used | transcribe | 286 | 199 | fits | 37/46 | 3.16 | 1.0000 | 0.130 | 37 | -4 | -4 | 9: 0,1,2,16,19,21,34,43,45 | 0-2 | 0-2 | - |
| “Takedown” Official Choreography _ KPop  | genius | used | transcribe | 343 | 193 | fits | 43/52 | 0.06 | 1.0000 | 0.390 | 43 | -10 | -10 | 13: 0,1,2,3,20,21,23,28,29,30,36,37,41 | 0-3 20-21 28-30 36-37 | 0-3 28-30 | 0-3 |
| 周杰倫 Jay Chou【晴天 Sunny Day】-Official Musi | genius | rejected | transcribe | 103 | 318 | refused/too_few | 0/53 | 0.00 | 1.0000 |  | 0 | -19 | -19 | - | - | - | - |
| 정국 (Jung Kook) 'Seven (feat. Latto)' Off | genius | used | transcribe | 472 | 204 | fits | 74/77 | 7.22 | 1.0000 | 0.135 | 74 | -14 | -14 | 3: 6,28,46 | - | - | - |
| 정국 (Jung Kook) 'Seven (feat. Latto)' Off | genius | used | asr | 433 | 204 | fits | 68/77 | 7.32 | 1.0000 | 0.125 | 68 | -14 | -14 | 9: 3,6,24,25,39,45,46,47,51 | 24-25 45-47 | 45-47 | - |

| Song | Heard | Status | Flagged @ 1.0 s | Flagged @ 1.5 s | Flagged @ 2.0 s | Flagged @ 3.0 s | Flagged @ 4.0 s |
|---|---|---|---|---|---|---|---|
| 'Defying Gravity' - Wicked 20th Annivers | transcribe | refused/disagree | - | - | - | - | - |
| 'Defying Gravity' - Wicked 20th Annivers | asr | refused/disagree | - | - | - | - | - |
| 'Popular' - Wicked 20th Anniversary Edit | transcribe | fits | 14: 0,1,5,10,52,53,54,55,56,57,58,59,60,61 | 11: 0,52,53,54,55,56,57,58,59,60,61 | 11: 0,52,53,54,55,56,57,58,59,60,61 | 11: 0,52,53,54,55,56,57,58,59,60,61 | 11: 0,52,53,54,55,56,57,58,59,60,61 |
| 'Popular' - Wicked 20th Anniversary Edit | asr | fits | 15: 0,1,5,6,37,52,53,54,55,56,57,58,59,60,61 | 13: 0,1,37,52,53,54,55,56,57,58,59,60,61 | 13: 0,1,37,52,53,54,55,56,57,58,59,60,61 | 12: 0,37,52,53,54,55,56,57,58,59,60,61 | 12: 0,37,52,53,54,55,56,57,58,59,60,61 |
| 'Soda Pop' Official Lyric Video _ KPop D | transcribe | refused/disagree | - | - | - | - | - |
| Ed Sheeran - Best Part Of Me (feat. YEBB | transcribe | fits | 8: 0,1,2,8,15,29,32,34 | 6: 0,1,2,29,32,34 | 5: 0,1,2,32,34 | 5: 0,1,2,32,34 | 4: 0,1,2,32 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | asr | fits | 17: 1,5,6,7,14,15,22,27,28,29,30,31,32,33,34,35,36 | 14: 1,6,7,15,27,28,29,30,31,32,33,34,35,36 | 14: 1,6,7,15,27,28,29,30,31,32,33,34,35,36 | 12: 1,6,7,27,29,30,31,32,33,34,35,36 | 11: 1,6,7,27,29,30,31,32,34,35,36 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | transcribe | refused/disagree | - | - | - | - | - |
| Ed Sheeran & Rudimental­ - Bloodstream [ | asr | fits | 36: 4,10,15,16,17,18,19,20,21,22,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56 | 35: 10,15,16,17,18,19,20,21,22,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56 | 35: 10,15,16,17,18,19,20,21,22,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56 | 35: 10,15,16,17,18,19,20,21,22,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56 | 34: 15,16,17,18,19,20,21,22,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56 |
| Eminem - Lose Yourself | transcribe | fits | 5: 0,32,50,59,73 | 5: 0,32,50,59,73 | 5: 0,32,50,59,73 | 5: 0,32,50,59,73 | 4: 32,50,59,73 |
| Jessie J - Domino (Official Video) | transcribe | fits | 13: 35,39,43,44,45,46,47,48,49,50,51,67,68 | 13: 35,39,43,44,45,46,47,48,49,50,51,67,68 | 12: 35,39,43,44,45,46,47,48,49,50,67,68 | 12: 35,39,43,44,45,46,47,48,49,50,67,68 | 12: 35,39,43,44,45,46,47,48,49,50,67,68 |
| Josh Gad - In Summer (From 'Frozen'_Sing | transcribe | fits | 2: 3,17 | 2: 3,17 | - | - | - |
| NSYNC - Paradise | transcribe | fits | 10: 0,1,14,30,33,42,43,50,54,55 | 9: 0,1,30,33,42,43,50,54,55 | 8: 0,1,33,42,43,50,54,55 | 8: 0,1,33,42,43,50,54,55 | 8: 0,1,33,42,43,50,54,55 |
| Pocahontas - Colors of the Wind (Blu-ray | transcribe | fits | 1: 6 | 1: 6 | - | - | - |
| Pocahontas - Colors of the Wind (Blu-ray | asr | fits | 1: 28 | - | - | - | - |
| Sara Bareilles - She Used To Be Mine (Of | transcribe | fits | 1: 19 | - | - | - | - |
| Stay Gold (Official Music Video) from Th | transcribe | fits | 3: 28,42,45 | 1: 45 | - | - | - |
| ‘Your Idol’ Lyric Video _ KPop Demon Hun | transcribe | fits | 25: 0,1,2,3,4,5,6,7,8,9,10,24,28,29,30,31,32,33,34,35,36,42,46,51,55 | 21: 0,1,2,3,4,5,6,7,8,9,10,28,29,30,31,32,33,34,35,36,46 | 21: 0,1,2,3,4,5,6,7,8,9,10,28,29,30,31,32,33,34,35,36,46 | 19: 0,1,2,3,4,5,6,7,8,9,28,29,30,31,32,33,34,35,46 | 19: 0,1,2,3,4,5,6,7,8,9,28,29,30,31,32,33,34,35,46 |
| “Golden” Official Lyric Video _ KPop Dem | transcribe | fits | 10: 0,1,2,16,19,21,26,34,43,45 | 9: 0,1,2,16,19,21,34,43,45 | 9: 0,1,2,16,19,21,34,43,45 | 9: 0,1,2,16,19,21,34,43,45 | 9: 0,1,2,16,19,21,34,43,45 |
| “Takedown” Official Choreography _ KPop  | transcribe | fits | 21: 0,1,2,3,5,17,18,20,21,23,28,29,30,32,33,36,37,41,48,50,51 | 15: 0,1,2,3,20,21,23,28,29,30,32,36,37,41,50 | 13: 0,1,2,3,20,21,23,28,29,30,36,37,41 | 11: 0,1,2,3,23,28,29,30,36,37,41 | 10: 0,1,2,3,23,28,29,30,36,41 |
| 周杰倫 Jay Chou【晴天 Sunny Day】-Official Musi | transcribe | refused/too_few | - | - | - | - | - |
| 정국 (Jung Kook) 'Seven (feat. Latto)' Off | transcribe | fits | 3: 6,28,46 | 3: 6,28,46 | 3: 6,28,46 | 3: 6,28,46 | 3: 6,28,46 |
| 정국 (Jung Kook) 'Seven (feat. Latto)' Off | asr | fits | 9: 3,6,24,25,39,45,46,47,51 | 9: 3,6,24,25,39,45,46,47,51 | 9: 3,6,24,25,39,45,46,47,51 | 9: 3,6,24,25,39,45,46,47,51 | 9: 3,6,24,25,39,45,46,47,51 |

## GATE A report output, after the ruling

Raw output of `python scripts/lrc_timing_report.py` on 2026-10-29 at `2cde053`, with the
constants set at GATE A. Read only. Same numbering and gap sign as above.

Constants in force: FLAG_TOLERANCE_S=5.0, MIN_FLAGGED_RUN=2, MIN_UNHEARD_RUN=3, MIN_MATCHED_SHARE=0.25. 17 joint songs with a usable LRC in /home/ken/pikaraoke-songs.

| Song | Origin | LRCLIB | Heard | Words | Clip s | Status | Matched | Shift s | Speed | Spread s | Anchors | Gap s (bundle) | Gap s (file) | Mistimed | Unheard | Runs>=2 | Runs>=3 | Runs>=4 | Unheard runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 'Defying Gravity' - Wicked 20th Annivers | custom | rejected | transcribe | 267 | 257 | refused/disagree | 45/89 | -69.25 | 0.9590 | 4.113 | 45 | +97 | +97 | - | - | - | - | - | - |
| 'Defying Gravity' - Wicked 20th Annivers | custom | rejected | asr | 233 | 257 | refused/disagree | 36/89 | -67.14 | 0.9590 | 4.100 | 36 | +97 | +97 | - | - | - | - | - | - |
| 'Popular' - Wicked 20th Anniversary Edit | genius | rejected | transcribe | 319 | 211 | fits | 55/62 | -12.02 | 0.9590 | 0.227 | 55 | +13 | +13 | 4: 53,54,55,56 | 7: 0,52,57,58,59,60,61 | 53-56 | 53-56 | 53-56 | 57-61 |
| 'Popular' - Wicked 20th Anniversary Edit | genius | rejected | asr | 312 | 211 | fits | 55/62 | -11.90 | 0.9590 | 0.182 | 55 | +13 | +13 | 5: 53,54,56,60,61 | 7: 0,37,52,55,57,58,59 | 53-61 | 53-61 | 53-61 | 57-59 |
| 'Soda Pop' Official Lyric Video _ KPop D | genius | rejected | transcribe | 209 | 170 | refused/disagree | 31/59 | 15.27 | 1.0000 | 0.830 | 31 | +0 | +0 | - | - | - | - | - | - |
| Ed Sheeran - Best Part Of Me (feat. YEBB | genius | rejected | transcribe | 234 | 248 | fits | 34/38 | 2.21 | 0.9859 | 0.334 | 34 | -1 | -1 | - | 4: 0,1,2,32 | - | - | - | 0-2 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | genius | rejected | asr | 213 | 248 | fits | 27/38 | 1.78 | 0.9888 | 0.539 | 27 | -1 | -1 | - | 11: 1,6,7,27,29,30,31,32,34,35,36 | - | - | - | 29-32 34-36 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | custom | rejected | transcribe | 324 | 247 | refused/disagree | 38/71 | -10.88 | 1.0000 | 1.095 | 38 | +0 | +0 | - | - | - | - | - | - |
| Ed Sheeran & Rudimental­ - Bloodstream [ | custom | rejected | asr | 231 | 247 | fits | 28/57 | -10.24 | 1.0000 | 0.560 | 31 | +0 | +0 | 5: 31,32,37,38,52 | 29: 15,16,17,18,19,20,21,22,33,34,35,36,39,40,41,42,43,44,45,46,47,48,49,50,51,53,54,55,56 | 31-52 | 31-52 | 31-52 | 15-22 33-36 39-51 53-56 |
| Eminem - Lose Yourself | genius | used | transcribe | 777 | 328 | fits | 89/93 | -0.51 | 1.0000 | 0.200 | 89 | -1 | -1 | - | 4: 32,50,59,73 | - | - | - | - |
| Jessie J - Domino (Official Video) | genius | used | transcribe | 330 | 235 | fits | 57/69 | -0.43 | 1.0000 | 0.184 | 57 | -1 | -1 | - | 12: 35,39,43,44,45,46,47,48,49,50,67,68 | - | - | - | 43-50 |
| Josh Gad - In Summer (From 'Frozen'_Sing | genius | rejected | transcribe | 212 | 113 | fits | 21/21 | -0.44 | 1.0000 | 0.156 | 21 | +1 | +1 | - | - | - | - | - | - |
| NSYNC - Paradise | genius | used | transcribe | 339 | 305 | fits | 49/56 | 23.93 | 1.0000 | 0.280 | 49 | -38 | -38 | 1: 54 | 7: 0,1,33,42,43,50,55 | - | - | - | - |
| Pocahontas - Colors of the Wind (Blu-ray | genius | used | transcribe | 311 | 203 | fits | 37/37 | -6.38 | 1.0000 | 0.300 | 37 | +8 | +8 | - | - | - | - | - | - |
| Pocahontas - Colors of the Wind (Blu-ray | genius | used | asr | 310 | 203 | fits | 37/37 | -5.98 | 1.0000 | 0.100 | 37 | +8 | +8 | - | - | - | - | - | - |
| Sara Bareilles - She Used To Be Mine (Of | genius | used | transcribe | 295 | 253 | fits | 45/45 | -0.20 | 1.0000 | 0.228 | 45 | +0 | +0 | - | - | - | - | - | - |
| Stay Gold (Official Music Video) from Th | genius | used | transcribe | 280 | 246 | fits | 51/51 | -0.06 | 1.0000 | 0.054 | 51 | +0 | +0 | - | - | - | - | - | - |
| ‘Your Idol’ Lyric Video _ KPop Demon Hun | genius | used | transcribe | 300 | 206 | fits | 41/59 | -0.15 | 1.0000 | 0.150 | 41 | -14 | -14 | 1: 46 | 18: 0,1,2,3,4,5,6,7,8,9,28,29,30,31,32,33,34,35 | - | - | - | 0-9 28-35 |
| “Golden” Official Lyric Video _ KPop Dem | genius | used | transcribe | 286 | 199 | fits | 37/46 | 3.16 | 1.0000 | 0.130 | 37 | -4 | -4 | - | 9: 0,1,2,16,19,21,34,43,45 | - | - | - | 0-2 |
| “Takedown” Official Choreography _ KPop  | genius | used | transcribe | 343 | 193 | fits | 43/52 | 0.06 | 1.0000 | 0.390 | 43 | -10 | -10 | - | 9: 0,1,2,3,23,28,30,36,41 | - | - | - | 0-3 |
| 周杰倫 Jay Chou【晴天 Sunny Day】-Official Musi | genius | rejected | transcribe | 103 | 318 | refused/too_few | 0/53 | 0.00 | 1.0000 |  | 0 | -19 | -19 | - | - | - | - | - | - |
| 정국 (Jung Kook) 'Seven (feat. Latto)' Off | genius | used | transcribe | 472 | 204 | fits | 74/77 | 7.22 | 1.0000 | 0.135 | 74 | -14 | -14 | - | 3: 6,28,46 | - | - | - | - |
| 정국 (Jung Kook) 'Seven (feat. Latto)' Off | genius | used | asr | 433 | 204 | fits | 68/77 | 7.32 | 1.0000 | 0.125 | 68 | -14 | -14 | - | 9: 3,6,24,25,39,45,46,47,51 | - | - | - | 45-47 |

| Song | Heard | Status | Mistimed @ 3.0 s | Mistimed @ 4.0 s | Mistimed @ 5.0 s | Mistimed @ 7.0 s | Mistimed @ 10.0 s |
|---|---|---|---|---|---|---|---|
| 'Defying Gravity' - Wicked 20th Annivers | transcribe | refused/disagree | - | - | - | - | - |
| 'Defying Gravity' - Wicked 20th Annivers | asr | refused/disagree | - | - | - | - | - |
| 'Popular' - Wicked 20th Anniversary Edit | transcribe | fits | 4: 53,54,55,56 | 4: 53,54,55,56 | 4: 53,54,55,56 | 4: 53,54,55,56 | 4: 53,54,55,56 |
| 'Popular' - Wicked 20th Anniversary Edit | asr | fits | 5: 53,54,56,60,61 | 5: 53,54,56,60,61 | 5: 53,54,56,60,61 | 5: 53,54,56,60,61 | 5: 53,54,56,60,61 |
| 'Soda Pop' Official Lyric Video _ KPop D | transcribe | refused/disagree | - | - | - | - | - |
| Ed Sheeran - Best Part Of Me (feat. YEBB | transcribe | fits | 1: 34 | - | - | - | - |
| Ed Sheeran - Best Part Of Me (feat. YEBB | asr | fits | 1: 33 | - | - | - | - |
| Ed Sheeran & Rudimental­ - Bloodstream [ | transcribe | refused/disagree | - | - | - | - | - |
| Ed Sheeran & Rudimental­ - Bloodstream [ | asr | fits | 6: 10,31,32,37,38,52 | 5: 31,32,37,38,52 | 5: 31,32,37,38,52 | 5: 31,32,37,38,52 | 5: 31,32,37,38,52 |
| Eminem - Lose Yourself | transcribe | fits | 1: 0 | - | - | - | - |
| Jessie J - Domino (Official Video) | transcribe | fits | - | - | - | - | - |
| Josh Gad - In Summer (From 'Frozen'_Sing | transcribe | fits | - | - | - | - | - |
| NSYNC - Paradise | transcribe | fits | 1: 54 | 1: 54 | 1: 54 | 1: 54 | - |
| Pocahontas - Colors of the Wind (Blu-ray | transcribe | fits | - | - | - | - | - |
| Pocahontas - Colors of the Wind (Blu-ray | asr | fits | - | - | - | - | - |
| Sara Bareilles - She Used To Be Mine (Of | transcribe | fits | - | - | - | - | - |
| Stay Gold (Official Music Video) from Th | transcribe | fits | - | - | - | - | - |
| ‘Your Idol’ Lyric Video _ KPop Demon Hun | transcribe | fits | 1: 46 | 1: 46 | 1: 46 | 1: 46 | - |
| “Golden” Official Lyric Video _ KPop Dem | transcribe | fits | - | - | - | - | - |
| “Takedown” Official Choreography _ KPop  | transcribe | fits | 2: 29,37 | 1: 29 | - | - | - |
| 周杰倫 Jay Chou【晴天 Sunny Day】-Official Musi | transcribe | refused/too_few | - | - | - | - | - |
| 정국 (Jung Kook) 'Seven (feat. Latto)' Off | transcribe | fits | - | - | - | - | - |
| 정국 (Jung Kook) 'Seven (feat. Latto)' Off | asr | fits | - | - | - | - | - |
