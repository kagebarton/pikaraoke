Model: Claude Opus 5.5 (author, 2026-11-02). Executor: Claude Sonnet 5.5. GATE E1, Phase 5
and GATE R go to Ken.

# Edit words on a cue-timed song

## Goal

An admin can fix the words of a song timed by cue align (a YouTube caption, movie
subtitles or an LRCLIB match) line by line. Every line keeps its time, so only the words
change. Uses: caption and subtitle errors, LRCLIB typos, junk lines, and romanizing the
Hangul lines of a mixed-language song. A later phase tests an automatic Korean romanizer.

This replaces the Genius-on-LRCLIB plan, retired 2026-11-02 as tag
`archive/genius_lrc_timing` (plan `plans/genius-lrc-timing.md` on the tag). Its GATE N1
showed that Genius and LRCLIB split lines differently on most songs, so Genius text on
LRC times left many lines timed roughly. Editing in place never changes the splits.

Base: `dev` at `daf183a`. Branch `edit_words`, worktree `/home/ken/pik-edit-words`
(made by the author, 2026-11-02; this plan is untracked there).

## Rulings (Ken, 2026-11-02)

1. **All three cue sources**: YouTube captions, movie subtitles and LRCLIB timing.
   Captions have had errors too.
2. **One box per line, with its time.** The boxes hold the *cleaned* lines, the
   ones the cue route times and shows, not the raw sheet with parentheses or
   singer names.
3. **Label: the source and "(edited)"**, for example "LRCLIB (edited)".
4. **Automatic romanization: a test in a later phase** (Phase 6, GATE R).
5. **Place: an "Edit words" button on Song Info**, beside Repair lyrics and
   Regenerate, shown only for cue-timed songs, opening a page of its own.
6. **Repeated lines: offer to apply.** Editing a line whose text appears on other
   lines offers "Apply to N identical lines".
7. **"Play this line": a later phase**, not scheduled.

Assumptions stated to Ken on 2026-11-02, not objected to:

- Only songs whose next Regenerate reads a cue sheet can be edited. Others keep
  Custom lyrics on Repair.
- Times are shown, never edited. Clearing a box drops the line. Lines can't be
  added or split.
- Saving queues a regen, with the backup first, like Repair.
- The edited sheet survives Regenerate, bulk runs and Reset, as the other sheets
  do. A Repair to any source, the same one included, removes it; the backup keeps
  it. No separate revert button.
- An edited song stays on its source's library list and in its count.
- Text the cleaning would change (parentheses, a singer name) is shown cleaned
  before it is saved.
- No GATE before building: caption errors justify it alone. Whether romanized
  words time well (the retired plan's GATE N2) is heard in Phase 5.

## What the code does today (read 2026-11-02 at `daf183a`)

- **Sheet kinds** are one table, `library_regen.SHEETS` (suffix, origin, label):
  `custom` `.custom.txt`, `movie` `.custom.srt`, `lrclib` `.lrclib.srt`. A sheet
  in `lyrics/` is the record that a song uses it. `custom_plan` replays it ahead of
  everything, Reset included; `KEEP_ON_RESET` and the backup suffixes read the
  table; `apply_custom_choice` writes a just-saved sheet (`Plan.custom_text`) at
  run time and removes the other kinds; `sheet_kind` tells a kind by `endswith`
  on the suffix, first hit.
- **Captions are not a sheet.** A caption song's bundle says `origin: "srt"`, and
  `reuse_plan` replays `subtitles/<stem>.en.srt` (`find_local_srt`). A queued run
  with `reset=True` wipes `subtitles/` except the ASR json3, so a caption edit
  must live in `lyrics/` as a sheet to survive Reset.
- **Cleaning** is `srt_cues.cue_spans_from_srt`: per cue, strip speaker labels,
  `*` song marks and dialogue dashes, then `genius_lyrics.clean_srt_line`
  (parentheses, brackets, notes, HTML, curly quotes, Cyrillic watermark letters).
  It drops cues that clean to nothing, and recases a whole file typed in capitals
  (decided per file). The lyric-align stage loads an `.srt` with exactly this
  (`LyricAlignStage._load_lyrics`), and the cleaned text is both the aligner's input
  and the karaoke's display.
- **The bundle records the sheet's path** as `lyrics.source_path` (relative, e.g.
  `lyrics/<stem>.lrclib.srt`), so old versions in History can tell an edited sheet
  by its suffix with no new bundle field.
- **Origin tests by name** sit in `routes/song_info.py` (`_source_name`,
  `_lrclib_tile`, `_route_text`, `_versions`, `_pick`, `lrclib_row`,
  `_current_source`), `lib/library_status.py` (`SONG_LISTS`, the `lrclib=` line,
  `_lrclib_state`), `lib/library_tools.py` (`_now`, `REPAIR_SOURCES`,
  `undecided_group`) and `routes/library.py` (`_now_text`, the "Cue align"
  subline).

## Design

### Edited sheets share their source's origin

Three new `SHEETS` entries, one per cue source. Each records the **same origin as
its source**, so every origin test listed above keeps working unchanged (lists,
counts, LRCLIB tile, route text, "Cue align" subline). The edit shows only where a
label is written.

```python
class SheetKind(NamedTuple):
    suffix: str
    origin: str
    label: str
    edits: str | None = None  # the repair source whose words this kind edits

SHEETS = {
    "custom": ...,
    "movie": ...,
    "lrclib": ...,
    "caption_edited": SheetKind(".caption-edited.srt", "srt", "YouTube caption (edited)", "caption"),
    "movie_edited": SheetKind(".movie-edited.srt", MOVIE_ORIGIN, "movie subtitles (edited)", "movie"),
    "lrclib_edited": SheetKind(".lrclib-edited.srt", LRC_ORIGIN, "LRCLIB timing (edited)", "lrclib"),
}
```

- No suffix ends in another's (`sheet_kind` matches with `endswith`, first hit).
  Test each new suffix both ways against the old three.
- Reset, the backup, the one-sheet rule and `custom_plan` read the table and need
  no change. Saving an edited sheet removes the source's sheet (`.lrclib.srt`,
  `.custom.srt`); the backup taken before the run holds it.
- Helpers in `library_regen.py`, beside `sheet_kind`:
  - `edited_kind(origin) -> str | None`: the kind an edit of a cue sheet with
    that origin saves as (`"srt"` gives `caption_edited`).
  - `repair_source(kind) -> str`: `SHEETS[kind].edits or kind`.
  - `is_edited(path) -> bool`: the file at `path` (a `Path` or a bundle's
    `source_path` string, or None) is an edited sheet, by its suffix.
- `REPAIR_SOURCES` lists only the kinds with `edits is None`, so a Repair can't
  be sent an edited kind.

### Cleaning in place (`srt_cues.py`)

- `clean_cue_texts(contents: list[str]) -> list[str]`: each cue's cleaned text in
  its own position, `""` for one that cleans to nothing, with the file-level
  capitals rule decided over the whole list. `cue_spans_from_srt` calls it and
  keeps the non-empty ones, so it stays the one place the rules live. Existing
  `test_srt_cues.py` tests must pass unchanged.
- `cues_to_srt(lines, spans) -> str`: one cue per line at its span (`srt.compose`),
  the inverse of `cue_spans_from_srt` on cleaned lines. Test: a round trip gives
  the same lines and spans. `archive/genius_lrc_timing:pikaraoke/lib/lrc_pairing.py`
  has `timed_sheet_srt`, a round-trip-tested version, to read before writing it.

### The edit (`pikaraoke/lib/word_edit.py`, new; pure)

```python
@dataclass(frozen=True)
class WordSheet:
    kind: str                         # the edited kind a save writes
    lines: list[str]                  # cleaned, as the cue route times them
    spans: list[tuple[float, float]]  # each line's (start, end), clip seconds

class WordsCleaned(RegenError):
    """A save the cleaning would change; ``cleaned`` maps each such line's index to
    its cleaned text ("" when the cleaning drops it)."""

def edited_srt(sheet: WordSheet, original: object, lines: object) -> str: ...
```

`edited_srt` checks, in order, and raises `RegenError` with these messages
(they are admin-facing):

1. `original` is not a list equal to `sheet.lines`: "This song's lyrics changed
   since the page opened. Reload the page." It stops a stale page from saving
   over a sheet a Repair replaced meanwhile.
2. `lines` is not a list of strings as long as `sheet.lines`: the same message.
3. A line longer than `EDIT_LINE_MAX_CHARS` (300): "Line N is too long."
   Each line is whitespace-collapsed first (`" ".join(line.split())`).
4. Every line equals its original: "No line was changed."
5. Every line is empty: "Every line is cleared. To replace the lyrics, use
   Repair lyrics."
6. `clean_cue_texts` on the kept (non-empty) lines changes any of them: raise
   `WordsCleaned` with those lines' indexes, in the page's numbering.

It then returns `cues_to_srt(kept lines, their spans)`.

Unchanged lines must never trip check 6: the cleaning must give the same result
when run a second time. Phase 2 checks that on every cue sheet in the library.

### Library tools (`library_tools.py`)

- `word_sheet(song_path) -> WordSheet | None`: from `_regen_job(song)` (the plan
  a plain Regenerate uses). None unless the plan is a `seed` whose `lyrics_path`
  ends in `.srt`. That covers caption reuse, movie, LRCLIB and the edited kinds,
  and nothing else. Read the file (unreadable: log a warning, None), clean it with
  `cue_spans_from_srt`, and set `kind = edited_kind(plan.seed["lyrics_origin"])`.
  A sheet with no lines is None.
- `edit_words(song_path, original, lines) -> None`: video and busy checks as in
  `repair`. A song with no `word_sheet` gets "This song isn't timed from a
  caption or subtitles, so its words can't be edited here." Then
  `text = edited_srt(...)`, `job.plan = sheet_plan(song, sheet.kind, text)`, and
  `self._queue(job, reset=False, label="Edit words")`. `reset=False` because the
  source is unchanged. It keeps the caption in `subtitles/`, which only a Repair
  to captions replaces.

### Status, labels and History

- `SongStatus.edited` and `HistoryEntry.edited`: `is_edited(lyrics.source_path)`
  of that bundle. It is what the run timed, read as `origin` is. False with no
  bundle.
- `routes/song_info.py`:
  - `_source_name`: the source's name, then "(edited)" (one translatable
    `"%(source)s (edited)"`), so the Lyrics tile reads "LRCLIB (edited)".
  - `_route_text`: a cue-align text gains "The words were edited here."
  - `_versions`: the three cue rows gain "(edited)". `_pick` compares
    `(origin, edited, lines)` for every origin in `SHEETS`. That set now holds
    `"srt"`, so two caption versions compare by their lines too, and one whose
    words changed is marked changed. Expected, not a STOP; test it.
  - `_current_source`: `repair_source(status.sheet_kind)`. The Repair page gets
    `current_edited`, and its "current" tag then reads "current (edited)".
  - Song Info gets `can_edit_words` (`video` and `word_sheet` not None). Its button
    is disabled while busy, as Repair's is.
- `library_tools._now`: an edited sheet gives its source's `_now` name (`captions`,
  `movie`, `lrclib`) and `"edited": True`. `routes/library._now_text` appends
  "(edited)".
- `library_status.py`: only the `SongStatus` field comments change.

### Route and page (Phase 4, to the ratified mockup)

- `GET /song_info/edit_words?song=`: admin only. A song that isn't a video or
  has no `word_sheet` redirects to Song Info. Renders `song_edit_words.html` with
  the lines, their start times (`m:ss`, or as ratified), the source name
  (`_source_name(status)`) and `busy`.
- `POST /song_info/edit_words`: JSON `{song, original, lines}`. Calls
  `edit_words`. On `WordsCleaned` it returns 400 with `{"cleaned": {index: text}}`
  and on `RegenError` 400 with the message, as `/song_info/repair` does.
- The page: one box per line. A changed line is marked, and a cleared one is
  marked "dropped". A changed line whose original text matches other, still
  unchanged lines offers "Apply to N identical lines" (client side, exact
  match on the original text). On a `cleaned` answer, the page writes each cleaned
  text into its box, marks it with a note saying what was removed, and leaves Save
  for the admin to press again. Save is labelled "Regenerate song" and reuses the
  Repair page's regenerate tip; success returns to Song Info.
- CSS: reuse `library-pages.css` classes where they exist; page-only rules inline,
  as `song_repair.html` does.

## Phases

### Phase 0: branch and baseline

- [ ] In `/home/ken/pik-edit-words` (never switch branches in `/home/ken/pikaraoke`):
      commit this plan, `docs(plans): edit-words plan`.
- [ ] Full suite: `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q
      -p no:cacheprovider`. Log the pass count as the baseline (Results row).
      Check the run used the worktree's code. The retired plan's Results row 3
      (on the tag) shows how, and warns that a bare `python -P -c "import
      pikaraoke"` reaches the main checkout.
- [ ] Stop for Ken's `/compact`.

### Phase 1: sheet kinds and cleaning in place

- [ ] `srt_cues.py`: `clean_cue_texts`, `cues_to_srt`, with tests in
      `test_srt_cues.py` (positions kept, `""` for a dropped cue, the capitals rule
      decided over the list, round trip). Commit: `refactor(srt): clean each cue in
      place, and write cleaned lines back as an SRT`.
- [ ] `library_regen.py`: `SheetKind.edits`, the three kinds, `edited_kind`,
      `repair_source`, `is_edited`; `REPAIR_SOURCES` without the edited kinds.
      Tests in `test_library_regen.py`:
      - `sheet_kind` tells each new suffix from the old three, both ways;
      - `custom_plan` replays an edited sheet with its source's origin;
      - an edited sheet survives Reset and is in the backup;
      - saving an edited kind removes the source's sheet, and a Repair to the
        source removes the edited one (`apply_custom_choice`);
      - a Repair to captions removes `caption_edited`.
      Commit: `feat(regen): a word edit of a cue sheet is a sheet kind of its own`.
- [ ] Import-smoke, pre-commit on the changed files, full suite count in a
      Results row. Stop for `/compact`.

### Phase 2: the edit, server side

- [ ] `word_edit.py` and `tests/unit/test_word_edit.py`, using invented lines
      only. Cover each check in order: a stale `original`, wrong length or type,
      a line too long, nothing changed, every line cleared, a cleaning change. For
      the cleaning case, cover a line with parentheses, a singer label, and one
      that cleans to nothing; the indexes count the page's lines, cleared ones
      included. Then success: spans are kept, cleared lines are dropped, and the
      output reloads through `cue_spans_from_srt` to the kept lines.
- [ ] `LibraryTools.word_sheet` and `edit_words`, with tests in
      `test_library_tools.py`:
      - `word_sheet` for a caption song, a movie sheet, an LRCLIB sheet, each edited
        kind (same kind back), a Genius song, a custom `.txt` sheet, a
        transcribed song, an unreadable sheet;
      - `edit_words` queues `sheet_plan(song, kind, text)` with `reset=False` and
        label "Edit words";
      - it refuses a busy song, a non-video and a song with no sheet;
      - a second edit of an edited sheet keeps its kind.
- [ ] Read only, not committed: a scratchpad script that runs `clean_cue_texts` over
      the cleaned lines of every cue sheet in the library
      (`/home/ken/shared-drives/D:/Shared/pikaraoke-songs`: each `word_sheet`).
      It counts lines that change on the second pass and prints counts only, never
      lyric text. Expected 0 everywhere; anything else is a STOP (the page would
      refuse lines nobody touched).
- [ ] Commit: `feat(library): edit the words of a song's cue sheet, keeping its
      line times`. Results row with the count and the suite. Stop for `/compact`.

### Phase 3: mockup -> GATE E1 (Ken)

- [ ] Build an HTML mockup of the Edit words page and the label changes, styled
      from `song_repair.html` and `song_info.html`, and publish it as an Artifact.
      Invented lyrics only. States:
  - the page for an LRCLIB song, about 40 lines, nothing changed (Save disabled);
  - one line changed; one cleared ("dropped");
  - a changed chorus line offering "Apply to 3 identical lines", and after it;
  - after a save the cleaning changed: the cleaned texts in their boxes, marked;
  - a stale page, a busy song, every line cleared (the error texts);
  - Song Info with the "Edit words" button and the Lyrics tile "LRCLIB (edited)";
  - a History row "LRCLIB timing (edited)";
  - the Repair page's source list with "current (edited)" on LRCLIB timing.
- [ ] **GATE E1: Ken ratifies the mockup.** Log his changes in the Results log. No
      page code before this.

### Phase 4: page, route and labels

- [ ] The route, the page and the Song Info button, to the ratified mockup.
      Route tests in `test_library_routes.py`: admin only; a non-cue song
      redirects; the page lists the cleaned lines and their times; the POST passes
      `original` and `lines` through; a `WordsCleaned` answer carries `cleaned`; a
      `RegenError` answer carries its message. Commit: `feat(song_info): Edit
      words, for songs timed from a caption or subtitles`.
- [ ] The labels (Design, Status, labels and History) with route and status
      tests:
      - the Lyrics tile, the route text and the History rows read "(edited)";
      - `_pick` marks an edit as a change, and two caption versions with the
        same lines as no change;
      - the Repair page's current tag for an edited song;
      - `_now_text`;
      - an edited song stays on its source's list.
      Commit: `feat(ui): an edited sheet reads "(edited)" beside its source`.
- [ ] Use the `ui-check` skill to drive the page on the VM (fake jobs): edit, apply
      to identical lines, the cleaning answer, back to Song Info. Results row.
- [ ] Checkpoint: review due (Checkpoints below). Stop.

### Phase 4.1: review fixes (Ken, 2026-11-02)

The Phase 4 `/code-review` (`f775b1b^..62d4818`, high) found eight things. Ken took
six of them (row 8). One commit each, in this order, each with its tests. Anchors are
quoted code at `62d4818`; a line-number offset alone is not a STOP.

- [ ] **4.1a: every edited line is written back, in sheet order** (review 1).
      `cues_to_srt` writes through `srt.compose(...)` with its defaults. Those drop a
      cue whose start is at or after its end and sort the rest by start, so a kept
      line can vanish or move on save. `cue_spans_from_srt` keeps every cue in file
      order, so the page shows the line. Number the cues from 1 in
      `cues_to_srt` and compose with `reindex=False`. Tests in `test_srt_cues.py`: a
      zero-length cue and two cues out of start order both round-trip in file order
      with their spans. Commit: `fix(srt): write every edited line back, in sheet
      order`.
- [ ] **4.1b: a cleaned cue cleans to itself** (review 3). The cleaning strips
      speaker labels before `clean_srt_line` removes parentheses and tags, so a label
      behind them survives one pass and goes on the next: `(softly) MARA: hey there`
      loads as `MARA: hey there`, and `<i>MEN:</i> go now` as `MEN: go now`. A save
      then refuses lines nobody touched. Even past the save, the run cleans the
      saved sheet again and drops the label from the karaoke without a word.
      In `clean_cue_texts`, repeat each cue's
      `clean_srt_line(_strip_subtitle_marks(...))` until it stops changing (one
      private helper). The capitals decision and the recasing stay as they are. Check
      that no step can make the text longer. If one can, the loop could cycle: STOP.
      Tests: those two cues load as `hey there` and `go now`. For every input
      already in `test_srt_cues.py`, cleaning the cleaned lines again changes nothing.
      In `test_word_edit.py`, a sheet loaded from those cues saves one changed line
      and is not refused. Existing tests pass unchanged.
      **Scan, read only, not committed:** a scratchpad script compares the new
      `cue_spans_from_srt` with the one at `62d4818` (exported with `git archive`
      into the scratchpad) on every `.srt` in the library's `lyrics/` and
      `subtitles/` folders (`/home/ken/shared-drives/D:/Shared/pikaraoke-songs`;
      skip `is_generated` files). Count the files and lines whose cleaned text
      differs. Print counts only. Phase 2's second-pass scan found 0, so expect 0.
      Anything else is a STOP: that song's timing would move at its next regen.
      Commit: `fix(srt): a cleaned cue cleans to itself`.
- [ ] **4.1c: a cue sheet that can't be read says so** (review 2 and 6).
      `word_sheet` catches `OSError, ValueError, srt.SRTParseError` but not
      `OverflowError`, which `srt.parse` raises for an out-of-range timestamp
      (`_srt_word_count` in `library_regen.py` catches it). Song Info calls
      `word_sheet` on every view, so such a sheet gives a 500. And an unreadable sheet
      gets the same None as a song that isn't cue-timed, so the button vanishes and a
      save says the song "isn't timed from a caption or subtitles".
      - `LibraryTools.can_edit_words(song_path) -> bool`: the next regen replays a
        cue sheet (`_regen_job`, a `seed` plan whose origin has an `edited_kind`).
        It reads no file. Song Info's `can_edit_words` uses it, so a view no longer
        parses the sheet.
      - `word_sheet(song_path) -> WordSheet` raises `RegenError` and never returns None.
        A song that `can_edit_words` refuses gets the existing "This song isn't timed
        from a caption or subtitles, so its words can't be edited here." A sheet that
        can't be read (the three exceptions plus `OverflowError`) or has no lines
        left after cleaning still logs its warning, then raises "This song's
        subtitles can't be read or hold no lyric lines, so its words can't be edited.
        Repair lyrics can replace them." The plan read is shared with
        `can_edit_words` (one private helper), not repeated. `edit_words` lets the
        error through, so the POST answers 400 with the message.
      - GET `/song_info/edit_words`: a non-video song, or one `can_edit_words` refuses,
        redirects to Song Info as now. A `RegenError` from `word_sheet` is flashed
        (`is-danger`), then redirects.
      - Tests: `TestWordSheet`'s None cases become the matching `RegenError`.
        `can_edit_words` is tested for each cue kind and each non-cue kind, and
        never reads the sheet. A sheet holding `99999999999999:00:00,000` raises the
        unreadable message. Route tests: Song Info renders for that song with the
        button. The page redirects with the flash, and the POST answers 400 with
        the message. Commit: `fix(library): a cue sheet that can't be read says so`.
- [ ] **4.1d: the Edit words page names the sheet it edits** (review 4). The page
      takes its source from the bundle (`_source_name(tools.status(song))`), not
      from the sheet it shows. When the two disagree, the header names one source
      and the boxes hold another's lines.
      - `WordSheet` gains `edited: bool`: the sheet read is already an edit,
        `is_edited(plan.lyrics_path)`.
      - `routes/song_info.py`: split the origin branches out of `_origin_name` into
        `_name_of_origin(origin: str | None) -> str | None`. `_origin_name` keeps the
        category fallback. The page's `source` is
        `_name_of_origin(SHEETS[sheet.kind].origin)`, through `_edited_name` when
        `sheet.edited`.
      - Tests: a song whose bundle says caption with an `.lrclib.srt` on disk shows
        "LRCLIB" on the page. An edited LRCLIB sheet shows "LRCLIB (edited)". Song
        Info's labels are unchanged (the existing tests). Commit: `fix(song_info):
        the Edit words page names the sheet it edits`.
- [ ] **4.1e: one test for an edited sheet kind** (review 8). "Is this kind an
      edit" is written out by hand in three places, beside `is_edited`, which only
      takes a path: `current_edited` in `repair_page`,
      `SHEETS[status.sheet_kind].edits` in `LibraryTools._now`, and
      `sheet.edits is None` in `REPAIR_SOURCES`. Add
      `is_edited_kind(kind: str | None) -> bool` to `library_regen.py`, make
      `is_edited` call it, and use it at those three sites. Not in scope: the
      `"caption"` -> `"captions"` name in `_now`. Existing tests cover the sites and
      must pass unchanged. Add one `is_edited_kind` test (None, each source kind,
      each edited kind). Commit: `refactor(regen): one test for an edited sheet kind`.
- [ ] **4.1f: a recased label is no label** (Ken, 2026-11-02, from the executor's find
      at 4.1b, row 9). A file typed in capitals keeps its speaker labels and is recased,
      which leaves `U2:` as it was. The next cleaning sees a file no longer in capitals,
      takes `U2:` for a label and strips it. `_SPEAKER_LABEL_RE` takes a label of two
      capitals in a row at least, which sentence case never produces. The capitals
      decision and the recasing stay as they are. Tests in `test_srt_cues.py`; same
      read-only library scan as 4.1b. Commit: `fix(srt): a speaker label has two
      capitals in a row`.
- [ ] Import-smoke, pre-commit on the changed files, full suite, a `ui-check` pass on
      the Edit words page (one save, the cleaning answer, the flashed unreadable
      sheet). Results row with the scan counts and the suite. Checkpoint: review due
      (Checkpoints, after Phase 4.1). Stop.

### Phase 4.2: review fixes (Ken, 2026-11-02, executed by Opus 5.5)

The Phase 4.1 `/code-review` (`1271b4b^..58de998`, high) found ten things (row 11).
Ken took the cleaning fixes and three small ones; the double plan read on the Edit words
GET and the three origin-name lists in `song_info.py` wait (the History wording may
differ on purpose).

- [x] **4.2a** `8ee7938` `fix(srt): a mark is found on every line of a cue, and a label is
      one sentence case changes`. `genius_lyrics.strip_srt_markup` (tags, brackets,
      notes, quotes, lookalikes, parentheses; line breaks kept) runs on the raw cue before
      the per-line label, dash and star rules. `_drop_label` keeps a label that
      `_recase_line` returns unchanged; the two-capitals lookahead is gone. The loop
      stays: "MEN: MARA: hey" needs it. Line-start dashes go as one run
      (`-[-\s]*`); the glued dash's spaces need `(?<!\s)`.
- [x] **4.2b** `49ad4ac` `edited_kind` uses `is_edited_kind`.
- [x] **4.2c** `bcccdcd` `_sheet_source_name` falls back to "—".
- [x] **4.2d** `ac8fcb5` `WordSheet.edited` has no default.

### Phase 4.3: review fixes (Ken, 2026-11-03, executed by Opus 5.5)

The Phase 4.2 `/code-review` (`8ee7938^..ac8fcb5`, high) found nine things (row 13). Ken
took the per-line cleaning with the star fix and its tests. Kept as they are: labels of
digits, dots or "I"s (`T.I.:`, `U2:`) stay words, a spaced dash run mid-line before a
glued dash stays, quotes or an ellipsis before a label are not decoration. The "—"
fallback stays (Ken's 4.2c).

- [x] **4.3a** `11b35cf` `fix(srt): a cue line's marks are stripped on that line, before
      the join`. Each line loops on its own labels, dashes and stars, then the lines are
      joined (`splitlines`, so `\r` and U+2028 split too); the joined text still loops to a
      fixed point. A dropped label leaves a space. The sentence-end dash takes a run
      (`-[-\s]*`), as the line-start one does.

### Phase 5: Ken's checks (Windows, GPU)

Hand Ken one PowerShell block: fetch the branch from remote `vm`, start the app with
`uv run` (memory `project_gpu_runs_via_windows` has the remote and the D: rules).

- [ ] A caption song with an error Ken knows: fix it, Regenerate, see the fix in the
      karaoke. Song Info reads "YouTube captions (edited)"; History, the Repair
      tag, the bulk run's "Now" and the captions list agree.
- [ ] Your Idol (LRCLIB timing today): replace its Hangul lines with the romanized
      text from Genius page 12047339 (Saja Boys - Your Idol (Romanized)), and
      Regenerate. Ken listens to those lines against the backup: are romanized
      words timed well enough by the English aligner? This is the retired plan's
      GATE N2 question.
- [ ] A movie-subtitle song: one edit, Regenerate, label.
- [ ] Type "(oh)" or "RUMI:" into a line: the page shows the cleaned text first.
- [ ] Reset Your Idol: the edited sheet is replayed and keeps "(edited)".
- [ ] Repair Your Idol to LRCLIB timing: the edit is gone, the LRC's own text back.
- [ ] Log Ken's read in the Results log.

### Phase 6: Korean romanizer test -> GATE R (Ken)

No feature code until GATE R.

- [ ] Pick a romanizer. It must be pure Python with a wheel for Windows, Linux and
      the Pi, and have a permissive license. It must apply the sound changes
      between syllables, giving what is sung rather than the spelling. Check:
      합니다 -> hamnida, 같이 -> gachi, 신라 -> silla. First candidate to check:
      `korean-romanizer` on PyPI. Install it into the `pik` env for the probe only,
      not `pyproject.toml`. Log the candidates and the checks in the Results log.
- [ ] `scripts/romanize_probe.py`, read only. Arguments: `--folder` (default
      `get_default_dl_dir`), `--song "<name part>"` (repeatable), `--out DIR`
      (refuses the library folder). For each song's `word_sheet`, take the lines
      holding Hangul and romanize only the Hangul runs, keeping Latin words. Write
      `<stem>.romanized.txt` into `DIR`: index, start time, line, suggestion.
      Stdout carries counts only. Run it into `D:\Shared\romanize_probe\`
      (`/home/ken/shared-drives/D:/Shared/romanize_probe/` here) for Your Idol and
      Takedown. Those two are on LRCLIB timing today. Golden needs a Repair to LRCLIB
      timing first, and Soda Pop's LRC fit is refused, so neither can be edited now.
- [ ] Commit the script: `feat(scripts): try a Korean romanizer on a song's cue
      lines`. The output holds lyric text and stays off git.
- [ ] **GATE R: Ken compares the suggestions** with the Genius romanized pages
      (Your Idol 12047339, Takedown 12100816). He may paste some into the editor
      and listen. He rules: build a per-line "Romanize" suggestion in the editor
      (Korean lines only, filling the box for the admin to accept), or stop here.
      A build is planned after the ruling, not before.

### Later (not scheduled)

- "Play this line": a button per line that plays the song from the line's start
  (Ken, 2026-11-02: a later phase). No admin page plays audio today, so it needs a
  route that serves the song's audio.
- The Repair page's Movie subtitles box after a word edit (review 5 at Phase 4,
  not taken for 4.1). An edit removes `.custom.srt`, which `custom_start` fills
  the box from. A `movie_edited` song then opens Repair with that box empty, while
  its card says "current (edited)". Needs a ruling on which sheet fills the box.

### Landing

After Phase 5, and after Phase 6 if GATE R builds anything: copy the code commits
onto `dev` one by one, in order (CLAUDE.md, Branches and Archive Tags). Leave out
this plan's commits. Then retire the branch as `archive/edit_words`.

## Rules for the executor

- Plain-language chat. Raw tables go in the Results log (CLAUDE.md, Communication).
- Never commit lyric text. Tests use invented lines; probe output on stdout is
  counts and indexes only.
- Work in `/home/ken/pik-edit-words` only. Run Python with `-P`. A script run from
  the worktree puts its own repo root first on `sys.path`, as
  `scripts/lrc_timing_report.py` does.
- Tests: `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest`. Pre-commit on
  changed files only:
  `pre-commit run --config code_quality/.pre-commit-config.yaml --files <files>`.
- Import-smoke the changed modules and read `git diff --cached` before each
  commit. Plan edits go in their own `docs(plans)` commits.
- After code changes: `graphify update .` if graphify is installed (it was not in
  the `pik` env on 2026-10-30).
- Stop at each GATE and after each phase's relay, so Ken can `/compact`. If a step
  contradicts the code, stop and say so.

## Checkpoints

- After Phase 4: review due.
  `/code-review high <Phase 1 first code commit>^..HEAD`, files in
  `pikaraoke/lib/{srt_cues,library_regen,word_edit,library_tools,library_status}.py`,
  `pikaraoke/routes/{song_info,library}.py`,
  `pikaraoke/templates/{song_edit_words,song_info,song_repair}.html`. Three finder
  angles:
  1. **Correctness**: does every kept line keep its span? Does a save re-read the
     sheet on the server and refuse a stale page? Does every label site show
     "(edited)" from the sheet's suffix?
  2. **Simplicity**: is there one cleaning function, used both to load and to
     check a save? Is `SHEETS` still the one table? Does any site test an edited
     kind by name where the source's origin already works?
  3. **Robustness**: a busy song, a stale page, every line cleared, a cleaning
     that drops a line, a suffix `sheet_kind` could misread, an unreadable sheet,
     a file typed in capitals.
- After Phase 4.1: review due.
  `/code-review high <4.1a commit>^..HEAD`, files in
  `pikaraoke/lib/{srt_cues,word_edit,library_tools,library_regen}.py`,
  `pikaraoke/routes/song_info.py`. Three finder angles:
  1. **Correctness**: does an edited sheet come back with every kept line, in
     file order, at its span? Does any cleaned line change on a second cleaning?
     Does the Edit words page name the sheet it shows?
  2. **Simplicity**: is the plan read for `can_edit_words` and `word_sheet` one
     helper? Is `is_edited_kind` the one test for an edited kind?
  3. **Robustness**: an out-of-range timestamp, a sheet that cleans to nothing, a
     zero-length or out-of-order cue, a label behind parentheses or a tag, a
     cleaning loop that might not stop, a file typed in capitals whose recased
     label looks like one (`U2:`, `I I:`).
- After Phase 4.2: review due.
  `/code-review high 8ee7938^..ac8fcb5`, files in
  `pikaraoke/lib/{srt_cues,genius_lyrics,library_regen,word_edit}.py`,
  `pikaraoke/routes/song_info.py`. Three finder angles:
  1. **Correctness**: does every cue line lose its label, dash and star whatever sits
     before it? Is every cleaned line a fixed point? Do `clean_srt_line` and
     `normalize_lyric_line` give what they gave at `daf183a`?
  2. **Simplicity**: is the cleaning loop still needed, and is anything in the label
     and dash patterns now dead?
  3. **Robustness**: long runs of any single mark (dashes, spaces, stars, labels,
     tags) in one cue; a recased label of digits, dots or "I"s.

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
| 1 | 2026-11-02 | - | Author (Opus 5.5): `genius_lrc_timing` retired as `archive/genius_lrc_timing` (`64332cf`, pushed and checked on gh-ssh; branch and worktree deleted). `git worktree add ../pik-edit-words -b edit_words daf183a`. Code read for this plan at `daf183a`. | Plan untracked in the worktree. |
| 2 | 2026-11-02 | 0 | Executor (Sonnet 5.5): plan committed as `8fe3d85` on `edit_words` (HEAD `daf183a` + the plan only). `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q -p no:cacheprovider` in `/home/ken/pik-edit-words`, with a throwaway plugin (scratchpad, not committed) printing `pikaraoke.__file__` at session end | **2998 passed**, 0 failed, 57.8 s. This is the baseline; it equals the retired plan's row 3 (code identical to `daf183a`). The run used the worktree's code: `/home/ken/pik-edit-words/pikaraoke/__init__.py`. |
| 3 | 2026-11-02 | 1 | Executor (Sonnet 5.5): `f775b1b` `refactor(srt): clean each cue in place, and write cleaned lines back as an SRT` (`clean_cue_texts`, `cues_to_srt`, `cue_spans_from_srt` calls the first); `14d1da2` `feat(regen): a word edit of a cue sheet is a sheet kind of its own` (`SheetKind.edits`, the three `*_edited` kinds, `edited_kind`, `repair_source`, `is_edited`; `REPAIR_SOURCES` filters on `edits is None`). Pre-commit clean on the changed files; import-smoke with the worktree first on `sys.path` (a bare `python -P -c "import pikaraoke"` reaches the main checkout, as the plan warns). graphify not installed in `pik`, no update. Full suite `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q -p no:cacheprovider` in `/home/ken/pik-edit-words` | **3062 passed**, 0 failed, 53.4 s (baseline row 2: 2998; +64 tests). `test_srt_cues.py` 23 passed with the pre-existing tests unchanged. Plan spec held without deviation. One effect to expect, not a STOP: `routes/song_info.py::_pick` tests `entry.origin in {sheet.origin for sheet in SHEETS.values()}`, and that set now holds `"srt"`, so two caption versions in History compare by their lines from `14d1da2` on (the plan's Design, `_versions`/`_pick`; Phase 4 adds `edited` to the key and tests it). No existing test changed on it. |
| 4 | 2026-11-02 | 2 | Executor (Sonnet 5.5): `61d192b` `feat(library): edit the words of a song's cue sheet, keeping its line times` (`pikaraoke/lib/word_edit.py`: `WordSheet`, `WordsCleaned`, `edited_srt` with the six ordered checks, `EDIT_LINE_MAX_CHARS=300`; `LibraryTools.word_sheet`, `edit_words`; `tests/unit/test_word_edit.py`, `TestWordSheet` and `TestEditWords` in `test_library_tools.py`). Pre-commit clean; import-smoke with the worktree first on `sys.path`; graphify not installed. Read-only scan, scratchpad `words_second_pass.py` (not committed; counts only, library files newer than the scan start: 0): `LibraryTools.word_sheet` over the 103 videos in `/home/ken/shared-drives/D:/Shared/pikaraoke-songs`, then `clean_cue_texts` a second time on each sheet's lines. Full suite `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q -p no:cacheprovider` in `/home/ken/pik-edit-words` | **Scan: 90 cue sheets (76 caption, 7 movie, 7 LRCLIB; 13 songs have none), 5911 lines. Lines changed by a second cleaning pass: 0. Lines not already whitespace-collapsed: 0. `cues_to_srt` -> `cue_spans_from_srt` round trip differs from the sheet: 0 songs.** No STOP. Suite **3127 passed**, 0 failed, 54.1 s (row 3: 3062; +65 tests). Two choices the plan left open: "Line N" in the too-long message counts from 1, `WordsCleaned` indexes from 0 (the page's array index; Phase 3 can change either); `word_sheet` tells a cue sheet by the plan's origin (`edited_kind`), not also by the `.srt` suffix, since a seed plan with such an origin always has an `.srt`. A song holding both a source sheet and its edited sheet is not a state the app makes (the save removes the source's sheet); `custom_sheet_path` would pick the source's. |
| 5 | 2026-11-02 | 3 | Executor (Sonnet 5.5): mockup built and published as a private Artifact, https://claude.ai/artifact/MYuyn6Ed4PFgH7QULTPECr (version 1; source `/tmp/claude-1000/-home-ken-pikaraoke/57ce6112-52dc-4e9c-979f-cf065bc7dee8/scratchpad/edit_words_mockup.html`, not committed, read the Artifact for it). Invented lyrics only: a 40-line song, a credit line first, a typo in all four chorus places. Styled from `song_repair.html`, `song_info.html`, `library-pages.css` and the `--dark-*` tokens. States: Edit words page untouched (Save off); one changed + one dropped; chorus line fixed with the offer "Apply to 3 identical lines"; after applying; after a save the cleaning changed (three lines: a singer label, a bracketed word, a line that cleans to nothing); stale page; busy song; every line cleared; Song Info (Edit words button, Lyrics tile and Source row "LRCLIB (edited)", Alignment route text + "The words were edited here."); History tab ("LRCLIB timing (edited)" over its backup); Repair lyrics source list ("current (edited)" on LRCLIB timing). The Edit words states are live (type, clear, Undo, Apply, Regenerate song, with a stand-in cleaner); Phone/Wide width. Headless Chromium run on the VM: all 11 states render, 0 console errors, 0 page errors, no horizontal overflow at 430 px or 1100 px; live path exercised (fix one line -> "1 changed"; offer "Apply to 3 identical lines" -> "4 changed"; a typed parenthesis -> cleaned text in the box, banner, nothing queued; second press -> Song Info). Server texts are the code's own (`STALE_MESSAGE`, `BUSY_MESSAGE`, the all-cleared and cleaned messages). | Awaiting GATE E1 (Ken). Items put to Ken on the page: (1) each box shows its number from 1 and its start time, so "Line N is too long" names the box marked N and the 0-based cleaned indexes stay internal; (2) additions beyond the plan, each removable: an Undo link on changed/dropped/cleaned lines, "Was: ..." under a changed or dropped line, a bottom bar (count + Regenerate song) that stays on screen, the all-cleared notice shown at once instead of after Save; (3) busy song: boxes locked + Save off (alternative: boxes editable, Save off); (4) after a cleaning change the cleaned text is in the box, marked Cleaned, with "You typed: ..." under it, and Save stays on; (5) three buttons on Song Info need `.si-btn` padding reduced to `0 .5em` at 370 px content width, and the Lyrics tile wraps to two lines at phone width. Not on the page: the `word_sheet` origin-vs-suffix choice (row 4), which has no screen. |
| 6 | 2026-11-02 | 3 | GATE E1, Ken: "keep the buttons as is, UI is ratified." He had asked whether the Song Info buttons should read "Repair timing" and "Edit lyrics"; the executor listed what renaming "Repair lyrics" touches (user-facing messages in `library_tools.py`, `library_regen`, the processing manager and `word_edit.py`, the Repair page title, about six tests); Ken declined both renames. | Ratified as drawn: Artifact version 1 (https://claude.ai/artifact/MYuyn6Ed4PFgH7QULTPECr), no change to it. Button names stay "Repair lyrics" and "Edit words". The row 4 `word_sheet` origin-vs-suffix choice was not addressed by Ken and stays as built. No page code was written before this row. Phase 4 unblocked. |
| 7 | 2026-11-02 | 4 | Executor (Sonnet 5.5): `acadcd8` `feat(song_info): Edit words, for songs timed from a caption or subtitles` (`GET/POST /song_info/edit_words`, `song_edit_words.html`, `can_edit_words` and the Edit words button on Song Info, `.si-btn` side padding `0.5em`; the `rp-*` rules both the Repair and Edit words pages draw, which were inline in `song_repair.html`, moved unchanged into `library-pages.css`); `98d080c` `feat(ui): an edited sheet reads "(edited)" beside its source` (`SongStatus.edited`, `HistoryEntry.edited` from `is_edited(lyrics.source_path)`; `_source_name`, `_route_text`, `_versions`, `_pick` key `(origin, edited, lines)`, `_current_source` = `repair_source(sheet_kind)` with `current_edited` and a `current_tag` macro on the Repair page; `LibraryTools._now` names an edited sheet's source with `"edited": True`, `routes/library._now_text` appends it). Pre-commit clean on the changed files; import-smoke with the worktree first on `sys.path`; graphify not installed. Mutation check (scratchpad, files restored byte for byte): `_pick` without `edited`, `_current_source` on the raw kind, `_now` without the flag, History row without the label each fail one new test. Full suite `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q -p no:cacheprovider` in `/home/ken/pik-edit-words`. ui-check skill (`FAKE_JOB_S` set, app run from the worktree on port 5591, headless Chromium 430 px and 1100 px; a 40-line invented song seeded once as a caption song and once as an LRCLIB song; scratchpad scripts `seed_edit_words.py`, `ew_check.py`, `ew_busy_check.py`, `ew_labels_check.py`, `css_compare.py`, not committed). | Suite **3218 passed**, 0 failed, 57.8 s (row 4: 3127; `acadcd8` 3165, +38; `98d080c` 3218, +53). Browser, 29 of 30 checks in `ew_check.py` pass on the committed code: 40 rows with number and start time; "No changes yet" and Save off; a chorus fix gives "1 changed", "Was: ...", "Apply to 3 identical lines" and, after it, "4 changed" and "Applied to 3 identical lines."; Undo; a cleared line is "Dropped" ("4 changed · 1 dropped"); a typed singer label and a typed "(la la la)" come back from the server as "Cleaned" and "Cleaned away" with "You typed: ...", the server's banner text, the page still on Edit words and Save on; a sheet changed on disk gives the stale text as a toast; the next save returns to Song Info with the regen note and Repair lyrics and Edit words off; every box cleared shows the all-cleared card with a Repair lyrics link and Save off; no horizontal overflow at 430 px or 1100 px; Song Info's three buttons share one row at 430 px. The one check that failed in `ew_check.py` is the busy page after that save: the ui-check fake does not hold a regen job (the log shows `Processing failed ... Stem worker died unexpectedly during separation` within 14 s of the regen starting), so the song was no longer busy; `ew_busy_check.py` queues a regen through `/song_info/regenerate` and opens the page at once: 40 boxes disabled, Save off, "This song has a regen waiting or running." with the Processing link. Labels, `ew_labels_check.py` on an edited LRCLIB song with a plain backup (7 of 7 pass, 0 console errors): Lyrics tile and Source row "LRCLIB (edited)"; Alignment route text ends "The words were edited here."; History "LRCLIB timing (edited)" over "LRCLIB timing", one `si-chg`; Repair page tag "current (edited)" on the LRCLIB timing card only. Repair page styles after the CSS move: `css_compare.py` took computed styles of the visible `.rp-muted`, `.rp-sec`, `.rp-sec.has-tip`, `.rp-name`, `.go-row.rp-buttons`, `.rp-buttons .button`, `.rp-buttons .button.is-primary`, `.go-row.rp-buttons .info-tip-btn` and `.rp-src` on the same song in this tree and in `6bf4cf4` exported with `git archive`: no differences. Where the build differs from the plan or the mockup: (1) the plan said page-only rules inline and shared ones from `library-pages.css`; the `rp-*` rules were in no shared file, so they moved rather than being copied (above). (2) The cleaned banner's head is the server's own `error` text from the 400, not a second copy in the page; the all-cleared card text is a client copy of the server text, as the mockup showed it at once. (3) `.ew-acts` gets `align-items: center` (the mockup left the note above the Undo link's baseline when both showed). (4) `song_info` now reads and cleans the song's sheet on every view for `can_edit_words`. (5) Not touched: the reset-run explanation still names only custom lyrics and movie subtitles as kept (an existing test asserts it). Not done: the `word_sheet` origin-vs-suffix choice (row 4) stays as built. |
| 8 | 2026-11-02 | 4 | Author (Opus 5.5): `/code-review high f775b1b^..62d4818`, run from `/home/ken/pik-edit-words` with the Checkpoints angles. Eight findings: (1) `cues_to_srt` drops a zero-length cue and sorts by start (run: a 2s->2s cue vanishes); (2) `word_sheet` misses `OverflowError` (run: `srt.parse` on `99999999999999:00:00,000` raises it), so Song Info 500s; (3) cleaning not idempotent, label behind parentheses or a tag (run: `(softly) MARA: hey there` -> `MARA: hey there`, `<i>MEN:</i> go now` -> `MEN: go now`); (4) Edit words page source from the bundle, not the sheet; (5) Repair's movie box empty after a `movie_edited` save; (6) an unreadable sheet reads as "isn't timed from a caption"; (7) `song_info` parses the sheet on every view; (8) the edited-kind test written out at three sites. Left out by the review: History comparing caption versions by lines (expected, row 3). Note for the read: row 4's scans found 0 second-pass changes and 0 round-trip differences in the library, so (1) and (3) affect no song today. | Ken ruled: fix 1, 2, 3, 4, 6, 8 as Phase 4.1. (5) to Later. (7) not taken, though 4.1c's `can_edit_words` removes the per-view parse. |
| 9 | 2026-11-02 | 4.1 | Executor (Sonnet 5.5): Phase 4.1, one commit each, tests with the code: `1271b4b` 4.1a `fix(srt): write every edited line back, in sheet order`; `3a47fb1` 4.1b `fix(srt): a cleaned cue cleans to itself`; `26da8b1` 4.1c `fix(library): a cue sheet that can't be read says so`; `666bcc0` 4.1d `fix(song_info): the Edit words page names the sheet it edits`; `48936b9` 4.1e `refactor(regen): one test for an edited sheet kind`. The uncommitted Phase 4.1 text and row 8 in the worktree went in first as `67fade8` (docs). Pre-commit clean on the changed files each time (Black reformatted a test file before staging in 4.1b and 4.1c); import-smoke with the worktree first on `sys.path`; graphify not installed. Mutation checks (scratchpad, files restored): 4.1a the old `cues_to_srt` fails its two new tests; 4.1b the old cleaning fails three (the label pair, `test_a_cleaned_cue_cleans_to_itself` on that pair, the `test_word_edit.py` save) and every other input already in `test_srt_cues.py` was already stable; 4.1c without `OverflowError` in the catch fails three (the `time_out_of_range` case, the page flash, the POST 400), and a `can_edit_words` that reads the sheet fails `test_it_never_reads_the_sheet` and the Song Info button test for the unreadable sheet; 4.1d the old page source fails both new page tests. 4.1b length check: no step of the cleaning lengthens a text (marks, tags, brackets, notes, parentheses and stars are removed; quotes, Cyrillic lookalikes, newlines and dashes are replaced one for one or by a single space; whitespace runs collapse), so the repeat ends; no STOP. 4.1b scan, read only, scratchpad `clean_scan.py` (counts only; library files newer than the scan: 0): `cue_spans_from_srt` at `62d4818` (`git archive` into the scratchpad `old_62d4818`) against the worktree's, on every `.srt` in `/home/ken/shared-drives/D:/Shared/pikaraoke-songs`. ui-check skill: app from the worktree on port 5593 (fresh workdir `uic41`, `FAKE_JOB_S=45`), headless Chromium 430 px; four songs with invented lyrics (Josh Gad caption, Lion King LRCLIB sheet, Aladdin caption with a cue time of `99999999999999:00:00,000`, the Eason Chan video with a caption bundle and an LRCLIB sheet on disk); scripts `seed_edit_words.py`, `seed41_more.py`, `ew41_check.py`, `ew41_write_sheet.py`, `ew41_after.py`, not committed. Full suite `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q -p no:cacheprovider` in `/home/ken/pik-edit-words`; 4.1a and 4.1b ran only the test files they touch plus the cue and library files (452 and 523 passed). | **4.1b scan: `lyrics/` 14 files read, 0 generated skipped, 858 lines, 0 unreadable, files differing 0, lines differing 0; `subtitles/` 76 files read, 27 generated skipped, 5053 lines, 0 unreadable, files differing 0, lines differing 0; `movie_subs/` (a third folder, beyond the plan's two) 13 files read, 5914 lines, 1 unreadable under both versions (`UnicodeDecodeError`, a raw movie file that is not UTF-8), files differing 0, lines differing 0.** No STOP. Suite **3266 passed**, 0 failed, 59 s (row 7: 3218; 4.1c 3257, 4.1d 3259, 4.1e 3266). Browser, `ew41_check.py` 13 of 16 pass on the committed code: the Edit words page of the caption-bundle song with an LRCLIB sheet on disk reads "Source: LRCLIB · 3 lines" with the sheet's lines in its boxes; the Aladdin song's Song Info opens (no 500) with its Edit words button, the button returns to Song Info with the red flash "This song's subtitles can't be read or hold no lyric lines, so its words can't be edited. Repair lyrics can replace them." (screenshot `ew41_unreadable.png`), a POST for it answers 400 with the message; typing "(oh)" into a line and saving stays on the page with the cleaned text in the box, the server's banner and Save on; one fixed line and Save returns to Song Info with the regen note, and the app log shows `Queued for regen (Edit words)`. The three that failed: two expected "Source: YouTube captions (edited)" after that save, but the ui-check fake's run dies (`Stem worker died unexpectedly during separation`) and writes no sheet, which the real run does, so `lyrics/` held no `.caption-edited.srt`; the third, "no console errors", saw one line, `Failed to load resource: ... 400`, the cleaning answer's own 400. `ew41_after.py` 4 of 4 pass with the edited sheet written by hand as the run writes it: header "Source: YouTube captions (edited) · 40 lines", the edited line in its box, 0 console errors on opening, and the cleaning answer adds exactly one console line, that 400. Where the build differs from the plan: (1) `WordSheet.edited` has a default of `False`, so the existing `WordSheet(...)` calls in tests stay as they were; `word_sheet` always passes it. (2) The page's source is a small `_sheet_source_name(sheet)` in `routes/song_info.py`, the plan's expression with the "(edited)" rule beside `_source_name`. (3) A sheet that cleans to no lines logs its warning too, as the plan asked; before it logged only an unreadable one. (4) The unreadable message is the constant `UNREADABLE_SHEET_MESSAGE` in `library_tools.py`; the "isn't timed" message stays inline in `word_sheet`. (5) The page no longer reads the song's status for its source. (6) `edited_kind` and `repair_source` still read `.edits` themselves: they need its value, not a yes or no. Found, not fixed, outside the plan ("the capitals decision and the recasing stay as they are"): in a file typed in capitals the first cleaning keeps labels and the recasing can leave a line shaped like one; the second cleaning no longer sees capitals and strips it. Run: `clean_cue_texts(["U2: LIVE TONIGHT", "WE ARE HERE"])` gives `["U2: live tonight", "We are here"]`, and the same call on that result gives `["live tonight", "We are here"]`. The shape is one capital letter followed only by digits or the label's punctuation. Row 4's second-pass scan found 0 changes in the library, and the scan above 0, so no song today; on the Edit words page of such a song the save would be refused as a cleaning change on a line nobody touched. Not done: review 5 stays in Later; review 7 was not taken. |
| 10 | 2026-11-02 | 4.1 | Executor (Sonnet 5.5): `d46be20` `fix(srt): a speaker label has two capitals in a row` (4.1f, Ken: "fix it now", on the find in row 9). `_SPEAKER_LABEL_RE` in `srt_cues.py` now needs two capitals in a row inside the label (a lookahead); the capitals decision and `_recase_line` are as they were. The first attempt, a label of two capitals not necessarily adjacent, was committed and amended the same minute before this row: a probe showed `I I: SO`, `A. B: GO` and `I. A: YES` in a capitals file still changed on a second cleaning, because their recased text is all capitals and spaces. Two in a row cannot come out of sentence case (a recased capital is a sentence start or a lone `I`, each followed by a lower-case letter or a non-letter). Plan: 4.1f added to Phase 4.1; the review-due robustness angle gained the capitals case. Pre-commit clean; the old code was run against the new tests first (3 fail: the label test and two idempotence cases). Probe, `clean_cue_texts([first, "WE ARE HERE TONIGHT"])` then the same call on its result, for `I I: SO`, `A. B: GO`, `I. A: YES`, `OK. I: SO`, `MR. T: GO`, `A.J.: HI`, `U.S.: HELLO`, `U2: LIVE TONIGHT`, `I-I-I: HEY`. Read-only scan, scratchpad `clean_scan.py` (counts only), `cue_spans_from_srt` at `48936b9` (`git archive` into the scratchpad `old_48936b9`) against the worktree's on every `.srt` in the library. | Probe: all nine stable on a second cleaning (before: `I I: SO` -> `I I: so` -> `so`; `A. B: GO` -> `A. B: go` -> `go`; `I. A: YES` -> `I. A: yes` -> `yes`; `U2: LIVE TONIGHT` -> `U2: live tonight` -> `live tonight`). **Scan: `lyrics/` 14 files read, 858 lines, files differing 0, lines differing 0; `subtitles/` 76 files read (27 generated skipped), 5053 lines, 0, 0; `movie_subs/` 13 files read, 5914 lines (1 unreadable under both), 0, 0.** No STOP. The scan against `62d4818` (row 9) was 0 and this one is against `48936b9`, so the new rule differs from `62d4818` on no library line either. Suite **3270 passed**, 0 failed, 59 s (row 9: 3266). Behaviour change in every file, not only capitals ones: a label made of one capital and digits or marks (`U2:`, `A1:`, `R2-D2:`) is now kept as words, where before it was stripped; `C3PO:`, `MEN:`, `MR. POTTS:` still are labels. No library cue has that shape. No browser pass for this commit (cleaning only; the Edit words page's own cleaning answer was checked in row 9). |
| 11 | 2026-11-02 | 4.1 | `/code-review high 1271b4b^..58de998` (run from `/home/ken/pikaraoke` by Opus 5.5 on Ken's prompt), Checkpoints angles. Ten findings: (1) a label behind a tag or parentheses survives on a cue's later lines (run: `clean_cue_texts(["<i>Hi there</i>\n<i>MEN:</i> go now", "x"])` gives "Hi there MEN: go now"); (2) the two-capitals lookahead makes `_SPEAKER_LABEL_RE` quadratic (8000 chars: 0.002 s -> 0.66 s); (3) the two-capitals rule keeps "T.I.:", "M.I.A.:", "E-40:", "A1:", "R2-D2:" in every file; (4) the loop patches a step order; (5) the Edit words GET reads the plan twice; (6) `_sheet_source_name` typed `str` can return None; (7) `edited_kind` tests `k.edits` itself; (8) three origin-name lists in `song_info.py`; (9) `WordSheet.edited` defaults to False; (10) three cleanings per cue. | Ken: fix 1-4, 6, 7, 9 now (10 goes with 4); 5 and 8 wait. |
| 12 | 2026-11-02 | 4.2 | Opus 5.5: `8ee7938`, `49ad4ac`, `bcccdcd`, `ac8fcb5`. The loop was kept, against the relay to Ken: without it "MEN: MARA: hey" gives "MARA: hey" and "- - hey" gives "- hey". Timing (scratchpad, not committed), `clean_cue_texts([ch*n + "x", "a"])`: before 4.2a, 80000 spaces 61.5 s (the glued-dash alternative, same on `daf183a`) and 80000 "- " did not finish in 120 s (one dash per loop pass); after, at 8000 every mark tried (dash, space, star, `<i>`, note, "- ", " -", "a - ", "a. - ", "* ", "MEN: ", "A: ", "-a ", "a -", "U2: ") is under 0.02 s, and unclosed "[" and "<" take 0.27 s (`_BRACKET_CONTENT_RE`, `_HTML_TAG_RE` in `genius_lyrics.py`, same on `daf183a`, and "(" via `_PAREN_CONTENT_RE`; not changed here). Library scan, read only (`scan.py` in the scratchpad, `git archive` of `daf183a` and `58de998`): 130 `.srt` found, 103 not generated; new vs `daf183a` 0 files / 0 lines differ, new vs `58de998` 0 / 0. Full suite in the worktree (`PYTHONPATH` set): **3276 passed**. Pre-commit clean on the changed files. | Review due (Checkpoints, after Phase 4.2). |
| 13 | 2026-11-03 | 4.2 | `/code-review high 8ee7938^..ac8fcb5` (run from `/home/ken/pikaraoke` by Opus 5.5 on Ken's prompt), Checkpoints angles. Unchanged since `daf183a` on 300,000 random inputs: `clean_srt_line`, `normalize_lyric_line`; every cleaned line a fixed point on 300,000 random cues and files. Nine findings: (1) every loop pass after the first runs on the joined cue, so a second label or dash on a later line is kept (`"Hey\nMEN: WOMEN: go"` -> `"Hey WOMEN: go"`) and a capitals line above is taken into a label (`"OH\nMEN: WOMEN: go"` -> `"go"`); (2) `_drop_label` returns group 1 alone, so `"*MEN: go"` -> `"*go"`; (3) digit, dot and "I" labels (`T.I.:`, `E-40:`, `U2:`) kept as words in a normally cased file; (4) quadratic on long runs (`"MEN: "` x2000 about 6 s; `"Hey. " + "- "` x4000 3.8 s); (5) `"man - - -With"` -> `"man - - With"`; (6) lines split on `\n` only, so `"A\u2028MEN: go"` -> `"go"`, and quotes or `...` before a label keep it; (7) the `_clean_cue` docstring's `"- - hey"` no longer needs the loop; (8) markup stripped again on every pass; (9) the `or "—"` fallback in `_sheet_source_name` is for an impossible state. | Ken: fix 1, 2, 7 now, with 4, 6 (line breaks) and 8 as they fall out of 1; 3, 5, the quotes half of 6 stay; 9 stays (his 4.2c). |
| 14 | 2026-11-03 | 4.3 | Opus 5.5: `11b35cf`. Probe (scratchpad `fix_check.py`, not committed): the review's cases all clean as meant (`"OH\nMEN: WOMEN: go"` -> `"OH go"`, `"*MEN: go"` -> `"go"`, `"A\u2028MEN: go"` -> `"A go"`); 100,000 random cues of labels, dashes, stars, tags, line breaks and words, each in a normal and a capitals file: 0 not fixed points. Timing, `clean_cue_texts([mark*8000 + "x", "a"])`: `"MEN: "` 0.06 s, `"- MEN: "` 0.08 s, `"Hey. - "` 0.08 s, `"U2: "` 0.05 s, `"- "`, `" "`, `"*"`, `"* - "` 0.02 s or less; `"Hey. " + "- "` x4000 0.00 s. `"-*"` x8000 takes 10.9 s (16.6 s at `ac8fcb5`): one dash and its glued star per pass. One join case is left: `"OH\nU2: go"` -> `"go"`, since `"OH U2:"` recases to something else; the loop keeps it a fixed point. Library scan, read only (scratchpad `scan.py`, `git archive` of `ac8fcb5`): 584 `.srt` under the library not ending `.generated.srt`, 1 unreadable under both, 38733 lines, 0 files / 0 lines differ. The two new tests fail on `ac8fcb5`. Pre-commit clean on the changed files. Full suite in the worktree: **3280 passed**. | No review due: one function's structure, checked by the probe and the scan. |
| 15 | 2026-11-03 | 5 | Ken's checks on Windows, `edit_words` fetched from remote `vm` at `188f03c`. The executor (Sonnet 5.5) handed over the six checks and ran none of them. Ken's read, word for word, in the order he sent it. While on check 4 he asked: "for 4, where does it show the revised line? RUMI: just stays in the box". The executor's answer was that the page cleans when Regenerate song is pressed, not while typing (`edited_srt` refuses the save, the 400 carries `cleaned`, the page's `showCleaned` fills the boxes), as ratified at GATE E1 (row 5 item 4, row 6). Its provenance: scratchpad `ew_rumi.py` (not committed), the ui-check app run from the worktree at `188f03c` on port 5595, a 40-line invented song, `RUMI:` typed into line 3: before the press the box read `RUMI:` and the count "1 changed"; after it the box was empty, tagged "Cleaned away" with "You typed: RUMI:", the banner shown and nothing queued. `RUMI: Every window knows my name` gave the box `Every window knows my name`, tagged "Cleaned". Also run on `clean_cue_texts`: `Golden RUMI: in the light`, `Rumi:` and `RUMI` come back unchanged. | Ken: "everything checks out, your idol is now on LRCLIB timing" |
