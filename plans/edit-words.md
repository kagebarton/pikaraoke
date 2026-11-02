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

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
| 1 | 2026-11-02 | - | Author (Opus 5.5): `genius_lrc_timing` retired as `archive/genius_lrc_timing` (`64332cf`, pushed and checked on gh-ssh; branch and worktree deleted). `git worktree add ../pik-edit-words -b edit_words daf183a`. Code read for this plan at `daf183a`. | Plan untracked in the worktree. |
| 2 | 2026-11-02 | 0 | Executor (Sonnet 5.5): plan committed as `8fe3d85` on `edit_words` (HEAD `daf183a` + the plan only). `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q -p no:cacheprovider` in `/home/ken/pik-edit-words`, with a throwaway plugin (scratchpad, not committed) printing `pikaraoke.__file__` at session end | **2998 passed**, 0 failed, 57.8 s. This is the baseline; it equals the retired plan's row 3 (code identical to `daf183a`). The run used the worktree's code: `/home/ken/pik-edit-words/pikaraoke/__init__.py`. |
| 3 | 2026-11-02 | 1 | Executor (Sonnet 5.5): `f775b1b` `refactor(srt): clean each cue in place, and write cleaned lines back as an SRT` (`clean_cue_texts`, `cues_to_srt`, `cue_spans_from_srt` calls the first); `14d1da2` `feat(regen): a word edit of a cue sheet is a sheet kind of its own` (`SheetKind.edits`, the three `*_edited` kinds, `edited_kind`, `repair_source`, `is_edited`; `REPAIR_SOURCES` filters on `edits is None`). Pre-commit clean on the changed files; import-smoke with the worktree first on `sys.path` (a bare `python -P -c "import pikaraoke"` reaches the main checkout, as the plan warns). graphify not installed in `pik`, no update. Full suite `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q -p no:cacheprovider` in `/home/ken/pik-edit-words` | **3062 passed**, 0 failed, 53.4 s (baseline row 2: 2998; +64 tests). `test_srt_cues.py` 23 passed with the pre-existing tests unchanged. Plan spec held without deviation. One effect to expect, not a STOP: `routes/song_info.py::_pick` tests `entry.origin in {sheet.origin for sheet in SHEETS.values()}`, and that set now holds `"srt"`, so two caption versions in History compare by their lines from `14d1da2` on (the plan's Design, `_versions`/`_pick`; Phase 4 adds `edited` to the key and tests it). No existing test changed on it. |
| 4 | 2026-11-02 | 2 | Executor (Sonnet 5.5): `61d192b` `feat(library): edit the words of a song's cue sheet, keeping its line times` (`pikaraoke/lib/word_edit.py`: `WordSheet`, `WordsCleaned`, `edited_srt` with the six ordered checks, `EDIT_LINE_MAX_CHARS=300`; `LibraryTools.word_sheet`, `edit_words`; `tests/unit/test_word_edit.py`, `TestWordSheet` and `TestEditWords` in `test_library_tools.py`). Pre-commit clean; import-smoke with the worktree first on `sys.path`; graphify not installed. Read-only scan, scratchpad `words_second_pass.py` (not committed; counts only, library files newer than the scan start: 0): `LibraryTools.word_sheet` over the 103 videos in `/home/ken/shared-drives/D:/Shared/pikaraoke-songs`, then `clean_cue_texts` a second time on each sheet's lines. Full suite `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q -p no:cacheprovider` in `/home/ken/pik-edit-words` | **Scan: 90 cue sheets (76 caption, 7 movie, 7 LRCLIB; 13 songs have none), 5911 lines. Lines changed by a second cleaning pass: 0. Lines not already whitespace-collapsed: 0. `cues_to_srt` -> `cue_spans_from_srt` round trip differs from the sheet: 0 songs.** No STOP. Suite **3127 passed**, 0 failed, 54.1 s (row 3: 3062; +65 tests). Two choices the plan left open: "Line N" in the too-long message counts from 1, `WordsCleaned` indexes from 0 (the page's array index; Phase 3 can change either); `word_sheet` tells a cue sheet by the plan's origin (`edited_kind`), not also by the `.srt` suffix, since a seed plan with such an origin always has an `.srt`. A song holding both a source sheet and its edited sheet is not a state the app makes (the save removes the source's sheet); `custom_sheet_path` would pick the source's. |
| 5 | 2026-11-02 | 3 | Executor (Sonnet 5.5): mockup built and published as a private Artifact, https://claude.ai/artifact/MYuyn6Ed4PFgH7QULTPECr (version 1; source `/tmp/claude-1000/-home-ken-pikaraoke/57ce6112-52dc-4e9c-979f-cf065bc7dee8/scratchpad/edit_words_mockup.html`, not committed, read the Artifact for it). Invented lyrics only: a 40-line song, a credit line first, a typo in all four chorus places. Styled from `song_repair.html`, `song_info.html`, `library-pages.css` and the `--dark-*` tokens. States: Edit words page untouched (Save off); one changed + one dropped; chorus line fixed with the offer "Apply to 3 identical lines"; after applying; after a save the cleaning changed (three lines: a singer label, a bracketed word, a line that cleans to nothing); stale page; busy song; every line cleared; Song Info (Edit words button, Lyrics tile and Source row "LRCLIB (edited)", Alignment route text + "The words were edited here."); History tab ("LRCLIB timing (edited)" over its backup); Repair lyrics source list ("current (edited)" on LRCLIB timing). The Edit words states are live (type, clear, Undo, Apply, Regenerate song, with a stand-in cleaner); Phone/Wide width. Headless Chromium run on the VM: all 11 states render, 0 console errors, 0 page errors, no horizontal overflow at 430 px or 1100 px; live path exercised (fix one line -> "1 changed"; offer "Apply to 3 identical lines" -> "4 changed"; a typed parenthesis -> cleaned text in the box, banner, nothing queued; second press -> Song Info). Server texts are the code's own (`STALE_MESSAGE`, `BUSY_MESSAGE`, the all-cleared and cleaned messages). | Awaiting GATE E1 (Ken). Items put to Ken on the page: (1) each box shows its number from 1 and its start time, so "Line N is too long" names the box marked N and the 0-based cleaned indexes stay internal; (2) additions beyond the plan, each removable: an Undo link on changed/dropped/cleaned lines, "Was: ..." under a changed or dropped line, a bottom bar (count + Regenerate song) that stays on screen, the all-cleared notice shown at once instead of after Save; (3) busy song: boxes locked + Save off (alternative: boxes editable, Save off); (4) after a cleaning change the cleaned text is in the box, marked Cleaned, with "You typed: ..." under it, and Save stays on; (5) three buttons on Song Info need `.si-btn` padding reduced to `0 .5em` at 370 px content width, and the Lyrics tile wraps to two lines at phone width. Not on the page: the `word_sheet` origin-vs-suffix choice (row 4), which has no screen. |
