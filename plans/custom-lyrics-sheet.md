Model: Claude Opus 5.5 (author, 2026-10-28). Executor: Claude Sonnet 5.5.

# Custom lyric sheets

## Goal

The admin types, pastes or loads their own lyrics on **Repair lyrics** and the
song is timed from them. The sheet is hand-crafted, so it outlives every later
run: Regenerate, Repair to the same source, a bulk Update, Reprocess or **Reset**
all use it again. Only a Repair to another source (caption, Genius, transcribe)
removes it.

Closes the open-issues entry "Upload hand-checked lyrics" (`plans/open-issues.md`,
"Ruled: own branch or plan").

## Decisions (Ken, 2026-10-28)

1. **Input: edit box, prefilled.** A new "Custom lyrics" source on Repair opens a
   text box holding the song's current lyrics (or blank). The admin edits or
   pastes; an "Open file" button loads a `.txt` into the box (read in the
   browser, nothing uploaded on its own).
2. **Helpers: both, as for Genius.** The YouTube auto-caption (YTASR third
   source) is used whenever its json3 is on disk and passes the quality gate.
   Repair shows the LRCLIB step after the sheet, with matches scored against
   the custom sheet.
3. **Leaving custom: Repair to another source.** A successful run from any
   non-custom plan deletes the sheet. The backup taken before the run still
   holds it. No separate "Remove" button.
4. **Survives Reset.** Settled by Ken before the questions: custom sheets are
   hand-crafted.
5. **Sequencing: wait for the other agent.** Another agent has uncommitted edits
   to `song_repair.html`, `song_info.html`, `library_run.html`, `processing.html`
   and `library-pages.{js,css}` in the main working tree. Start only after that
   work is committed to `dev` (Phase 0 checks it).

## Design

### Where the sheet lives

`<library>/lyrics/<stem>.custom.txt`, UTF-8, the admin's text verbatim with line
ends normalized to `\n`. The file on disk is the single source of truth for
"this song uses custom lyrics". The bundle only records `lyrics.origin:
"custom"` so the pages can say so.

Not stored in the bundle because a Reset ignores bundle provenance
(`resolve_plan(reset=True)`) and a transcribe result deletes the bundle
(`finish_regen_job`).

Reset keeps it: `KEEP_ON_RESET` (`library_regen.py`) already keeps `lyrics/*.lrc`
for the same reason. The backup before every run (`BACKUP_DIRS` includes
`lyrics`) copies it.

### Plan resolution: the sheet wins

One function, `custom_plan(job) -> Plan | None`, in `library_regen.py`. It
returns a plan when the sheet exists:

```python
Plan(kind="seed", lyrics_path=<sheet>, seed={"lyrics_origin": "custom"}, label="custom sheet")
```

Every path that picks a song's plan without an explicit admin choice consults
it first:

- `resolve_plan`: before the `reset` branch, so Reset uses the sheet. The CLI
  (`scripts/regen_alignment_bundles.py`) gets this for free.
- `reuse_plan`: first line, so Regenerate and bulk "reuse" use it.
- `LibraryTools._regen_job`: check custom **before** the `no_lyrics` →
  transcribe shortcut.
- `LibraryTools._caption_plan` calls `resolve_plan(job, reset=True)` and expects
  `fetch`. With the sheet winning inside `resolve_plan`, a caption Repair on a
  custom song would wrongly raise "no YouTube ID". Change it to call
  `_fetch_or_prompt_plan(job.song_path)` directly. That function is private; make
  it public as `fetch_or_prompt_plan` (one rename, two callers).
- Bulk run `_Run.undecided_group`: a custom song goes to `reuse` in **every**
  mode, reset included, ahead of the `all`-mode `no_lyrics` check. Add
  `custom: bool` to `_Entry` (set in `LibraryTools._entry` from the sheet's
  existence) rather than re-reading disk inside `_Run`.

The `.txt` suffix routes the sheet through `parse_lyric_lines` and the same
joint route Genius lyrics take (`LyricAlignStage._load_lyrics` branches on
suffix, not origin). The plan's `lyrics_path` is the sheet itself, with no temp
copy. The sheet keeps the admin's stanza breaks, so the wrap-join hazard that
forces blank-line separation on replayed bundle lines
(`_join_wrapped_lines` docstring) is the same as for raw Genius text.

### Writing and removing the sheet (run time, undone on failure)

New `Plan` field `custom_text: str | None`, set only by a custom Repair.
`apply_custom_choice(job)` runs in `prepare_lyrics` beside `apply_lrclib_choice`:

- `custom_text is not None` → write the sheet (atomic write).
- Plan is not custom-origin and the sheet exists → delete it. Only an explicit
  admin choice can reach here with a sheet on disk: every automatic path
  resolves to `custom_plan` first. That covers a caption, Genius or transcribe
  Repair, and a bulk-run pick on a custom song, if Phase 0 finds one is
  possible.

A failed run must leave the sheet as it was, exactly as the `.lrc` is handled
today. `ProcessingManager` snapshots the `.lrc` before `prepare_regen_job` and
calls `put_back_lrc` when the run does not succeed. Do the same for the sheet.
`lrclib.snapshot_lrc` / `restore_lrc` / `_write_text_atomic` are path-generic.
Rename them to `snapshot_file` / `restore_file` / `write_text_atomic` (public)
and use them for both files rather than copying them. Keep them in `lrclib.py`;
moving modules is out of scope. Generalise `put_back_lrc` the same way (or call
`restore_file` for the sheet beside it, whichever reads cleaner, but don't
duplicate the never-raises wrapper).

### YTASR for custom songs

Today `LyricsFetchStage._resolve_ytasr` (Genius route only) gates the on-disk
json3 and stashes `ctx.artifacts["ytasr"]` + `media_duration_s`. Extract its body
into `ytasr.resolve_on_disk(song_path) -> tuple[dict | None, float | None]` (the
record and the probed duration; never raises, same logs). The stage calls it and
stashes. `prepare_lyrics` calls it for custom plans and puts the results into
`plan.seed` before building `SeedArtifactsStage`. Resolve fresh on every run (it
is one ffprobe and a json parse), so a caption fetched after the Repair counts
next time.

### LRCLIB for custom songs

- **On Repair:** step 2 always forces an explicit pick or "None" (the Send button
  is disabled until one is chosen). `apply_lrclib_choice` writes the record or
  the skip marker exactly as for Genius. No automatic search for custom: it has
  no title/artist identity to search with.
- **On later runs:** the `.lrc` on disk (kept by Reset) is reused by the fill.
  `backfill_lrc` stays Genius-only. A custom song with no `.lrc` simply has no
  fill until the admin picks one on Repair.
- **Scoring:** `LibraryTools.lrclib_candidates(song, genius_id, title, artist)`
  becomes `lrclib_candidates(song, sheet_lines, title, artist)`. The routes
  resolve the sheet lines: GET with `genius_id` (unchanged for Genius), or a new
  POST to the same URL with JSON `{song, title, artist, text}` for custom (the
  sheet can be long; keep it out of the query string).
- **Search box prefill for custom:** the bundle's Genius title/artist when the
  song has one, else `default_query(song)` in Title and Artist blank. Phase 0
  finds how the Genius flow prefills these and mirrors it.

### Validation (one helper, `custom_sheet_lines(text) -> list[str]`)

In `library_tools.py`. It raises `RegenError` with an admin-facing message when
`text` is:

- not a string;
- longer than 100,000 characters;
- yields no lyric lines after `parse_lyric_lines`.

It normalizes `\r\n` / `\r` to `\n`. Both the Repair POST and the LRCLIB-search
POST call it, so the rule lives in one place. It returns the display lines (for
scoring).

### Repair backend

`LibraryTools.repair(song, source, genius_id=None, lrclib_id=None,
lrclib_skip=False, text=None)`: `source == "custom"` builds
`Plan(kind="seed", lyrics_path=<sheet path>, seed={"lyrics_origin": "custom"},
custom_text=<normalized text>, label="custom sheet")`, plus the LRCLIB choice.
Extract the record lookup now inside `_genius_plan` into a shared
`_apply_lrclib_pick(plan, lrclib_id, lrclib_skip)` so Genius and custom use one
copy. Queue with `reset=True`, label `"Repair"`, as the other sources do.

The route `POST /song_info/repair` accepts `text` (passed through; validated in
`repair`). `_current_source` returns `"custom"` for `origin == "custom"`.

### Display

`SongStatus.origin` gains `"custom"`. Every place that branches on
`origin == "genius"` to decide something LRCLIB-related or route-related must
treat custom the same way. Each place that names the source must say "Custom
lyrics". Known sites (Phase 0 greps for more):

- `library_status._lrclib_state`: `n/a` only when origin is not genius/custom.
- `routes/song_info.py`:
  - `_source_name` → "Custom lyrics".
  - `_lrclib_tile` → applies to custom; the not-applicable sub becomes "Genius
    or custom lyrics only".
  - `_alignment` → the fit block runs for custom too.
  - `_route_text` → custom wording for the joint route ("Custom lyrics, timed
    by combining …", both YTASR variants).
  - `song_info()` → `source=`, and replace the `genius_song` flag with what the
    template actually needs: show the LRCLIB pick row for genius **or** custom,
    and the Genius pick row for genius only. Check `song_info.html` around the
    `{% if genius_song %}` block.
- History tab: `HistoryEntry` gains `origin`. `_versions` labels a custom version
  "Custom lyrics" and keeps its LRCLIB label. Today anything without a Genius
  identity is labelled "YouTube captions", which would be wrong for custom.
- Bulk run: `LibraryTools._now` → `{"source": "custom"}`; `routes/library.py
  _now_text` → "Now: custom lyrics".

The Processing page needs no change. A custom Repair is an ordinary `"Repair"`
row. **Do not edit `processing.html`.**

### Repair page UI (`song_repair.html`)

- Add a fourth source card, `data-source="custom"`: "Custom lyrics", with the
  description "Type or paste the lyrics, or open a .txt file." Show the
  `current` tag when `current_source == 'custom'`. Place it after "Genius
  lyrics".
- Add a `#custom-section` shown only for this source, like `#genius-section`:
  - A `<textarea>` prefilled server-side with `custom_prefill`: the sheet's text
    if one exists, else the bundle's `lyrics.lines` joined by `\n`, else empty.
    Jinja autoescapes inside the element.
  - An "Open file" button backed by a hidden
    `<input type="file" accept=".txt,text/plain">`, read with `FileReader` as
    UTF-8 into the box.
  - The step is complete when the box has non-blank text. The server does the
    real check.
- **Go** for custom goes to step 2, like Genius. Step 2's subtitle (`#genius-pick`)
  reads "Custom lyrics, N lines" for custom. N is a client-side count of
  non-blank lines; mark it approximate in the code comment, or omit N if it
  would mislead.
- `searchLrclib` for custom POSTs `{song, title, artist, text}`; for Genius it
  keeps the GET.
- `#send` for custom posts `{source: 'custom', text, lrclib_id | lrclib_skip}`.
- Reuse `libraryPages` helpers and the existing `.rp-*` classes. No new CSS file.
  New strings go through `{{ _('…') | tojson }}` in `T`. Regenerating the
  translation catalogue is out of scope (web plan D9).

## Out of scope

- Delete song / Rename leaving the sheet behind: it joins the existing open
  issue ("Delete song and Rename leave the song's files behind"). Add
  `.custom.txt` to that entry's list in `plans/open-issues.md` in Phase 5.
- A fresh **download** of a song that already has a sheet (same stem) runs the
  normal fetch path. Not handled.
- Timed uploads (`.lrc`, `.srt`): plain text only.
- Showing the parsed line list before sending.

## Execution rules (executor)

- Branch `custom_lyrics` off `dev` once Phase 0 passes. Never commit to `master`.
- One commit per phase, tests riding with their code. Before each commit:
  import-smoke the changed modules, run the affected test files, read
  `git diff --cached` against the phase's intent.
- Tests: `/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit/<file>`
  per phase, the full suite at the end of Phase 4. Use real `EventSystem` and
  `PreferenceManager`. Mock subprocess, ffprobe and network.
- Pre-commit scoped to changed files:
  `pre-commit run --config code_quality/.pre-commit-config.yaml --files <files>`
  (never `--all-files`: it reformats `plans/`).
- **STOP and report** (don't improvise) if a Phase 0 fact is false, or a design
  rule above turns out impossible as written.
- Append each phase's outcome to the Results log below: commit hash, tests run
  and counts, anything seen and not changed.

## Phases

### Phase 0: preconditions and fact checks (no code)

1. `git status` on `dev` shows none of the other agent's files modified
   (`song_repair.html`, `song_info.html`, `library_run.html`, `processing.html`,
   `playlist.html`, `library-pages.{js,css}`, `tests/unit/test_library_routes.py`).
   If any are still modified, STOP: the other agent hasn't committed.
2. Confirm each of these against the code; STOP on any mismatch:
   - `LyricAlignStage._load_lyrics` picks the route by file suffix, and nothing
     in `lyric_align.py` gates YTASR or the LRCLIB fill on `lyrics_origin`.
   - `library_regen._claims` / `_owner` attribute `lyrics/<stem>.custom.txt` to
     `<stem>`, including when another song's stem is a prefix of this one.
   - `KEEP_ON_RESET` / `_clear_dir` keep one suffix per folder (so Phase 1
     must widen it to a tuple).
   - Whether a bulk-run pick (`save_pick` / `_valid_pick`) can target a song in
     the `reuse` group. Record the answer; the deletion rule covers it either
     way.
   - How step 2's Title/Artist boxes are prefilled for a Genius pick.
   - Every `origin == "genius"` / `"genius"` source branch in `routes/`,
     `library_status.py`, `library_tools.py` and the templates. List them in the
     Results log; Phase 3 must cover each one or say why not.

### Phase 1: sheet storage and plan resolution

- Rename the three `lrclib` file helpers (see Design) and update callers.
- `custom_sheet_path(song)` and `custom_plan(job)` in `library_regen.py`. Hook
  `custom_plan` into `resolve_plan`, `reuse_plan` and `_regen_job`. Do the
  `fetch_or_prompt_plan` rename and the `_caption_plan` change.
- `Plan.custom_text`; `apply_custom_choice` in `prepare_lyrics`.
- `KEEP_ON_RESET`: `lyrics` keeps `(".lrc", ".custom.txt")`.
- `ytasr.resolve_on_disk`; `LyricsFetchStage._resolve_ytasr` delegates to it;
  `prepare_lyrics` fills the custom seed from it.
- `ProcessingManager`: snapshot the sheet with the `.lrc` and restore it on a
  failed run.
- Tests (`test_library_regen.py`, `test_library_tools.py`, the processing
  manager tests, and the lyrics-fetch tests for the extraction):
  - Sheet present → `resolve_plan` returns the custom plan with and without
    `reset`.
  - `reuse_plan` and `_regen_job` prefer it, including over `no_lyrics`.
  - `_caption_plan` still returns `fetch` for a custom song with a YouTube id.
  - `clear_output_folders` keeps the sheet and still removes the song's other
    `lyrics/` files.
  - `apply_custom_choice` writes the sheet for `custom_text` and deletes it for
    a caption, Genius or transcribe plan.
  - A failed regen restores the sheet, both a deleted one and an overwritten
    one.
  - The custom seed carries `ytasr` when the json3 passes the gate and omits it
    when the gate fails.
- Commit: `feat(regen): a custom lyric sheet on disk wins every plan and survives Reset`.

### Phase 2: Repair and LRCLIB search backend

- `custom_sheet_lines` validation.
- `repair(..., text=)` with `source == "custom"`, and the shared
  `_apply_lrclib_pick`.
- `lrclib_candidates(song, sheet_lines, title, artist)`; the GET route resolves
  Genius lines; add the POST variant for custom.
- `POST /song_info/repair` passes `text`. `_current_source` → `"custom"`.
- Tests (`test_library_tools.py`, `test_library_routes.py`):
  - Custom repair queues a plan with the normalized text.
  - Empty, whitespace-only, header-only (`[Chorus]`), non-string and over-cap
    text is refused with a message, and nothing is queued or backed up.
  - An LRCLIB id or skip rides on a custom repair.
  - The POST search scores against the posted sheet.
  - The GET search is unchanged.
- Commit: `feat(repair): queue a custom lyric sheet, with its LRCLIB match`.

### Phase 3: display everywhere

- Every site from the Phase 0 list, plus `HistoryEntry.origin` and the bulk run
  (`undecided_group`, `_Entry.custom`, `_now`, `_now_text`).
- Tests (`test_library_status.py`, `test_library_routes.py`,
  `test_library_tools.py`):
  - A custom-origin bundle shows "Custom lyrics" on the tile, the source row,
    the route text and History.
  - The LRCLIB tile and fit block appear for custom.
  - A bulk run in `reset` mode puts a custom song in `reuse` and builds the
    custom plan; `all` mode does the same.
  - `_now_text` → "Now: custom lyrics".
- Commit: `feat(ui): Song Info and library runs name custom lyrics`.

### Phase 4: Repair page UI

- The source card, the editor, Open file, step 2 for custom, and the send body,
  as in Design.
- Route test: the repair page renders the custom card and the prefill in all
  three cases (existing sheet, bundle lines, nothing).
- Full test suite. The known Windows-box failures in `open-issues.md` don't
  apply on this Linux box; report any failure verbatim.
- Commit: `feat(ui): Repair lyrics takes a custom sheet`.

### Phase 5: hand-off

- Write the manual checklist below into the Results log for Ken. The executor
  cannot run the real app with GPU alignment for him; run the app only if the
  `run` skill applies and the GPU is free, and say which checks were actually
  done.
- Add `.custom.txt` to the Delete/Rename entry in `plans/open-issues.md`, and
  strike the "Upload hand-checked lyrics" entry with the commit range.
- Self-review on the three CLAUDE.md axes. This is multi-file core-pipeline
  work, so flag `/code-review` as **pending** (three finder angles:
  correctness, simplicity, robustness). Do not launch it.

## Manual checks (Ken)

1. Repair a Genius song → Custom lyrics: the box is prefilled with its current
   lines. Fix one word, pick an LRCLIB match, then Regenerate. Song Info shows
   "Custom lyrics", the LRCLIB tile, and the fixed word on playback.
2. Open file: load a `.txt` with blank lines and `[Chorus]` headers. The run
   drops the headers and keeps every lyric line.
3. Reset that song with the CLI (`regen --song <it> --reset`); a bulk Reset run
   would redo the whole library. It is still custom, the fixed word survives,
   and `lyrics/<stem>.custom.txt` is still there. Then Regenerate it from Song
   Info: same result.
4. Repair it to Genius: after the run, the sheet is gone and
   `regen_backup_*/lyrics/` holds it.
5. Force a failed custom Repair (e.g. cancel it mid-run, or make the song file
   unreadable). The old sheet, or no sheet, is back exactly as before.
6. Paste only `[Verse 1]`, then Regenerate: refused with a message, and nothing
   queued.

## Results log

| Phase | Commit | Tests | Notes |
| ----- | ------ | ----- | ----- |
| 0 | none (no code; the plan file is first committed with Phase 1) | baseline, 8 affected test files (`test_library_regen`, `_tools`, `_status`, `_routes`, `test_lrclib`, `test_lyrics_fetch`, `test_ytasr`, `test_processing_manager`): 753 passed | Passed, branch `custom_lyrics` cut from `dev` at `8b89c17`. See "Phase 0 findings" below. |
| 1 | `6b02e63` | 811 passed across the 9 affected files (Phase 0's 8 + `test_regen_alignment_bundles`); pre-commit clean on the changed files | Done as written. Details below under "Phase 1 notes". |
| 2 | `35badb7` | 867 passed across the same 9 files; pre-commit clean | Done as written. Notes below. |
| 3 | `0c2eba6` | 885 passed across the same 9 files; pre-commit clean | Done as written. Notes below. |
| 4 | `cb4c581` | full suite 2505 passed; pre-commit clean; 46 headless-browser checks of the real page passed (script kept out of the repo) | Done. Notes below. |
| 5 | this commit | not applicable (documentation) | Hand-off below. |

### Phase 0 findings

Preconditions: `git status` on `dev` showed no tracked file modified; the other
agent's work is committed (`8b89c17`, `fcc34fb` and earlier touch the repair,
song-info and run templates and `library-pages.js`).

Confirmed against the code:

- `LyricAlignStage._load_lyrics` branches on `Path(lyrics_path).suffix` only.
  `lyric_align.py` reads `lyrics_origin` in exactly two places: the
  `lyric_method` label (`"<origin>+joint"`) and the bundle's `lyrics.origin`.
  Nothing gates the YTASR words (`_ytasr_words` reads `ctx.artifacts["ytasr"]`)
  or the LRCLIB fill (`capture_method_used == "joint" and cfg.lrclib_fill`) on
  origin.
- `_claims` / `_owner` attribute `lyrics/<stem>.custom.txt` to `<stem>` with
  `Song`, `Song.live`, `Song Live` and an 11-char-id stem all in the library
  (run, not just read).
- `KEEP_ON_RESET` is `{"subtitles": ASR_JSON3_SUFFIX, "lyrics": ".lrc"}`;
  `_clear_dir` tests `entry.name.endswith(keep_suffix)`, and `str.endswith`
  takes a tuple, so Phase 1 widens the value to a tuple and the type to
  `str | tuple[str, ...] | None`.

Looked up and recorded:

- **Bulk-run pick on a reuse-group song:** not possible through the API.
  `save_pick` raises "That song doesn't need a pick." unless the song's
  undecided group is `needs_pick`, and `keep_all` has the same guard; a custom
  song is always `reuse`. Two stale routes remain, both already the
  open-issues "a run doesn't see a Repair made while it is open" window: a pick
  saved before the song became custom comes back through `_load_run`
  (`_valid_pick` doesn't look at the group), and a run opened before a custom
  Repair keeps `custom=False`. Either queues a non-custom plan, so
  `apply_custom_choice`'s deletion rule fires and the backup holds the sheet.
- **How step 2's Title/Artist are prefilled for a Genius pick: they are not.**
  `showStep(2)` sets only `#genius-pick` and renders the results; `#lrclib-title`
  and `#lrclib-artist` are never assigned (no `.val(...)` anywhere, since
  `4a30955`). The admin types both. The Design's rule for custom (bundle Genius
  title and artist, else `default_query(song)` in Title, Artist blank) is
  explicit and stands without anything to mirror, so Phase 4 implements it for
  custom only. Genius stays blank; that is the other agent's flow and not
  touched here.
- **`origin == "genius"` / Genius-source branches** (Phase 3 covers each):
  - `library_status.py`: `SongStatus.origin` comment; `_lrclib_state`
    (`origin != "genius"` -> `n/a`); `HistoryEntry` has no origin.
  - `routes/song_info.py`: `_source_name`; `_lrclib_tile`; `_alignment` (fit
    block); `_route_text` (keys on `method`, not origin, so a custom song would
    read "Genius lyrics, timed by ..."); `_versions` (`entry.genius` else "YouTube
    captions"); `song_info()` (`source=`, `genius_song=`); `_current_source`;
    `lrclib_search` (GET needs `genius_id`).
  - `routes/library.py`: `_now_text`.
  - `library_tools.py`: `repair` source branch; `lrclib_candidates`
    (Genius-only scoring); `_genius_plan` (LRCLIB pick, to extract); `_now`;
    `_Run.undecided_group` / `_Entry` / `_entry`; `_caption_plan` (calls
    `resolve_plan(reset=True)`). Pick kinds (`_PICK_GROUPS`, `_valid_pick`,
    `_choice_for`, `keep_all`) are about the bulk-run picks, not a song's
    origin, and stay as they are.
  - `song_info.html`: `{% if genius_song %}` wraps the Genius row, the LRCLIB
    row and the Captions row together; Phase 3 splits it.
  - `library_run.html` / `pick_pass.html`: `genius` is a pick kind or run group,
    not an origin. A custom song shows in `reuse` with the server's `now` text.
  - `processing.html` `lyricLabel` (not editable here): a `custom+joint`
    `lyric_method` matches no prefix and falls through to the raw string, so the
    Processing row will say `custom+joint`. Seen, not changed (rule: don't edit
    `processing.html`).
- **Other `lrclib` file-helper callers** the rename must reach:
  `processing_manager._run_regen` and `scripts/regen_alignment_bundles.py`
  (`snapshot_lrc` + `put_back_lrc`); `tests/unit/test_lrclib.py`,
  `test_library_regen.py` and `test_processing_manager.py` (they patch
  `restore_lrc` / `snapshot_lrc`).
- **Seen, not changed:** a library with a song whose stem is literally
  `<other stem>.custom` makes `_owner` give `<other stem>.custom.txt` to that
  song, not to `<other stem>`. The same limit already holds for every suffix
  file (`Song.en.srt` against a song named `Song.en`); no fix here.

### Phase 1 notes

- Renames: `lrclib.snapshot_lrc` / `restore_lrc` / `_write_text_atomic` ->
  `snapshot_file` / `restore_file` / `write_text_atomic`. The `.lrc` put-back is
  now one pair in `library_regen`: `snapshot_lyric_files(song)` (both files, taken
  before anything changes) and `put_back_lyric_files(snapshot)` (never raises,
  one warning per failed file, the second file is still restored). This replaces
  `put_back_lrc`; `processing_manager` and `scripts/regen_alignment_bundles.py`
  call the new pair, and neither imports `lrclib` any more.
- `fetch_or_prompt_plan` is public (callers: `resolve_plan`,
  `gate_on_disk_caption`, `LibraryTools._caption_plan`).
- `ytasr.resolve_on_disk` reads `ASR_JSON3_SUFFIX` with a function-level import:
  `youtube_dl` already imports `ytasr`, so a top-level import would be circular
  (both import orders checked). The constant did not move. On a parse failure it
  still returns the probed duration, as the stage's old code left it stashed.
- `custom_sheet_plan(song, text=None)` is the one place the custom `Plan` is
  built; `custom_plan(job)` calls it when the sheet exists, and Phase 2's repair
  calls it with the typed text. `is_custom_plan(plan)` is the matching test.
- `prepare_lyrics` builds a new seed (`{**plan.seed, **ytasr_seed}`) instead of
  editing `plan.seed`: `prepare_regen_job` works on a shallow copy of the song
  job, so editing the plan would change the queued job's.
- `lyric_method` for a custom run is `custom+joint`; the Processing page shows
  that raw (see Phase 0). Not changed.
- Seen, not changed: on Windows `write_text` writes the sheet with CRLF line
  ends and a restored sheet likewise (the open-issues "restored `.lrc` comes
  back with CRLF" entry); every reader uses `read_text`, so it parses the same.

### Phase 2 notes

- `custom_sheet_lines(text)` is in `library_tools.py` as specified. Its
  line-end normalization lives in a private `_sheet_text(text)` (type check, cap,
  `\r\n` / `\r` -> `\n`); the repair needs the normalized text as well as the
  lines, so `_custom_repair_plan` calls both rather than widening the return type.
  The cap is `CUSTOM_SHEET_MAX_CHARS = 100_000`, checked on the raw text.
- `lrclib_candidates(song, sheet, title, artist)` no longer touches Genius. The
  GET route gets the lines from a new `LibraryTools.genius_sheet_lines(id)` (the
  line the old method had inline) and still answers 502 when Genius is down; the
  POST is a second view on the same URL (`lrclib_search_custom`), and
  flask-smorest merges both into one OpenAPI path (checked). Both share
  `_lrclib_results` for the fit text and video length.
- Title and Artist in the POST body count as empty unless they are strings.
- `_current_source` returns `"custom"`; the page's script says so, and Phase 4
  gives it a card to mark.

### Phase 3 notes

- The Phase 0 site list is covered as follows. `library_status._lrclib_state`
  (genius or custom); `HistoryEntry.origin`; `_source_name`, `_lrclib_tile`,
  `_alignment`, `_route_text` (both YTASR variants), `_versions`; `song_info()`
  and `song_info.html`; `_current_source` (Phase 2); `library_tools._now` and
  `_Run.undecided_group` / `_Entry.custom` / `_entry`; `routes/library._now_text`.
  `_caption_plan`, `repair` and `lrclib_candidates` were Phases 1 and 2. Not
  touched on purpose: `_PICK_GROUPS`, `_valid_pick`, `_choice_for`, `keep_all` and
  the two run templates' `genius` (pick kind / group, not an origin).
- `genius_song` is gone from the template context. The page asks
  `library_status` whether LRCLIB applies (`status.lrclib_state != "n/a"`, in
  `_lrclib_tile`, `_alignment` and `song_info.html`) so "which sources have
  LRCLIB" is one rule, in `_lrclib_state`. The Genius row shows for
  `status.origin == 'genius'` only; the LRCLIB and Captions rows show for both.
- History: `genius_changed` now compares `(origin, genius id)`, not the id alone.
  Without the origin, captions -> custom (both id-less) would not be marked as a
  change. A Genius -> Genius pick with the same id is still unmarked.
- Added beyond the list: the Reset run's explanation says songs with custom
  lyrics keep them (`routes/library._run_explanation`). Without it the page tells
  the admin every song's source is chosen again, which is no longer true. One
  sentence, no layout change; the translation catalogue is not regenerated.
- A song counts as custom in a run only if the sheet file exists. A bundle that
  says `origin: custom` with the sheet deleted by hand is treated as an ordinary
  song (a Reset re-resolves it), while its "Now:" line still reads "custom
  lyrics" from the bundle. Accurate on both counts.

### Phase 4 notes

- The page's server inputs come from one `LibraryTools.custom_start(song)`:
  `text` (the sheet on disk, else the bundle's `lyrics.lines` joined by `\n`, else
  empty; an unreadable sheet is logged and falls back to the lines), and the search
  `title` / `artist` (the bundle's Genius song, else `default_query(song)` and no
  artist). The route puts them in `custom_prefill` and `custom_terms`; Jinja
  escapes the box's content, and `tojson` the terms.
- **Step 2 carries no line count** ("Custom lyrics.", not "Custom lyrics, N
  lines"). The plan allowed omitting N: the server drops `[Chorus]`-style headers,
  so a count of typed rows disagrees with the "matches X of Y lines" shown beside
  it as soon as a pasted sheet has a header.
- **Title/Artist prefill is for custom only**, as Phase 0 found (Genius has none).
  It fills only when both boxes are empty, so a visit back from step 2 doesn't
  overwrite what the admin typed.
- Found by self-review and fixed in this commit: matches listed for one source's
  lyrics stayed on screen after switching to the other source (custom <-> Genius).
  `chooseSource` now drops them; the browser check fails without that line.
- `dropLrclibMatches()` is the extracted reset (Genius pick, custom edit, source
  switch). The existing route test that grepped the Genius handler for
  `state.lrclibSeq++` now checks the handler calls the helper and the helper bumps
  the sequence.
- The browser check used the unit tests' `Env` (real `LibraryTools` over a tmp
  library; processing manager, Genius and LRCLIB faked) behind a real werkzeug
  server, driven by headless Chromium: prefill in all three cases, edit, Open file
  (UTF-8 with `[Chorus]` and blank lines, no request made), Next, the prefilled
  search, the POST body, the Send body, the stale-match drop, a header-only sheet
  refused with the server's message and nothing queued, a custom song opening on
  its own card, and the other sources unchanged. No JS errors.

### Phase 5 hand-off

**What was checked for real, and how.** The GPU was free (7 MiB used), so the real
pipeline ran on a scratch copy of one library song (Bloodstream: video, both
stems, its auto-caption; `~/pikaraoke-songs` was only read from and nothing in it
changed). The web app itself (the processing manager's thread and the live
Processing page) was **not** run; the driver mirrors `ProcessingManager._run_regen`
step for step instead.

- Custom Repair (the web's Repair -> Custom lyrics, with a `[Verse 1]` header,
  blank stanza breaks and one word changed): finished in 136 s; the sheet is on
  disk verbatim; bundle `origin: custom`, `source_kind: txt`, the header dropped and
  all 74 lines kept; the changed word is in the bundle and on the `.ass`; the
  auto-caption was adopted as the 3rd source; `method_used: joint`;
  `lyric_method: custom+joint`; the backup holds the previous Genius bundle; Song
  Info's status reads custom with the auto-caption used. Timing summary identical to
  the Genius run of the same lines (47 of 74 timed, same first and last line).
- Reset through the real CLI (`regen_alignment_bundles.py <folder> --song <id>
  --reset --yes`): plan "custom sheet", finished, still custom, the changed word
  survived, the sheet was in its backup.
- Regenerate (the plan `reuse_plan` gives): finished, still custom, same word.
- A failed custom Repair (new text written, then the run forced to fail): the old
  sheet came back and the old bundle stayed custom.
- A Repair to transcribe, standing in for "another source": the sheet was deleted,
  the newest backup still holds it, the old bundle was removed, and a later plan
  for the song is no longer custom. **A Repair to Genius itself was not run** (it
  needs a live Genius answer); it takes the same deletion path, which is unit-tested
  for the sidecar plan.

**Manual checks left for Ken** (the plan's six; what is already covered is noted):

1. Repair a Genius song -> Custom lyrics: the box is prefilled with its current
   lines. Fix one word, pick an LRCLIB match, then Regenerate. Song Info shows
   "Custom lyrics", the LRCLIB tile, and the fixed word on playback. *(Page and
   pipeline each checked above; the live app end to end, and playback, are not.)*
2. Open file: load a `.txt` with blank lines and `[Chorus]` headers. The run drops
   the headers and keeps every lyric line. *(Browser load and a real run with
   headers checked; a file picked in the real app is not.)*
3. Reset that song with the CLI (`regen --song <it> --reset`); it is still custom,
   the fixed word survives, and `lyrics/<stem>.custom.txt` is still there. Then
   Regenerate it from Song Info: same result. *(Both checked on the scratch song,
   through the CLI and the driver; Song Info's button not.)*
4. Repair it to Genius: the sheet is gone afterwards and `regen_backup_*/lyrics/`
   holds it. *(Checked with a transcribe Repair; Genius not run.)*
5. Force a failed custom Repair (cancel it mid-run, or make the song file
   unreadable): the old sheet, or no sheet, is back exactly as before. *(A forced
   failure checked; a real cancel from the Processing page is not.)*
6. Paste only `[Verse 1]`, then Regenerate: refused with a message, and nothing
   queued. *(Checked in the browser and by route tests; the message shows as a
   notification on the Send step.)*

**Self-review (CLAUDE.md axes) of the whole branch.**

- *Correctness:* the sheet wins `resolve_plan`, `reuse_plan`, `_regen_job` and the
  bulk run's grouping; a caption Repair no longer routes through `resolve_plan`; a
  failed or cancelled run restores the `.lrc` and the sheet together; the seed is
  rebuilt, not edited, so a retried queued job isn't touched. One defect found
  and fixed during Phase 4 (stale matches across a source switch).
- *Simplicity:* one constructor for the custom plan, one validation rule, one
  snapshot/put-back pair, one "does LRCLIB apply" rule (`lrclib_state`); the
  `genius_song` template flag and `put_back_lrc` are gone, not left beside their
  replacements. Beyond the plan's list: the Reset explanation sentence,
  `custom_start`, and the history `(origin, id)` comparison, each explained above.
- *Robustness:* every refusal (not text, over 100,000 characters, no lyric lines)
  comes before the backup and the queue; the file helpers never raise on restore;
  the box is escaped as text, the search terms by `tojson`; a bundle claiming
  `custom` with no sheet on disk is treated as an ordinary song.

**`/code-review` is PENDING, not run** (multi-file core-pipeline work: the plan
resolution, the failure restore and the LRCLIB scoring). When asked, use exactly
three finder angles: correctness, simplicity, robustness. Range:
`6b02e63`..`cb4c581` plus this commit's two plan files.

**Seen, not changed:**

- `lyric_method` `custom+joint` shows raw on the Processing row
  (`processing.html`'s `lyricLabel` knows only srt, genius, none and override); the
  rule was not to edit that page.
- **The prefill joins the bundle's lines with a single `\n`** (as the plan says),
  but the replay writers separate stored lines with a blank line because a stray
  `(` or `[` in one line can pair with a closer a line or two below and fuse two
  lyric lines (`_join_wrapped_lines`). An admin who sends a prefilled sheet
  unedited, for a song with such a stray, would get the fused line the replay
  writers avoid. Typed or pasted sheets carry the same hazard by design. Safe
  alternative if Ken wants it: join the prefill with a blank line (the box looks
  double-spaced).
- Genius's step 2 has no Title/Artist prefill (the admin types both); only custom
  has one now. Left as the other agent's flow.
- A fresh **download** of a song that already has a sheet with the same stem runs
  the normal fetch path and ignores it (out of scope in the plan).
- A song whose stem is literally `<other stem>.custom` makes `_owner` give
  `<other stem>.custom.txt` to that song (Phase 0).
- On Windows a written or restored sheet gets CRLF line ends (the open-issues
  `.lrc` entry); every reader uses `read_text`, so it parses the same.
- A run opened before a custom Repair, or a pick saved before it, can still queue
  a non-custom plan for that song; the deletion rule then removes the sheet and the
  backup holds it (the open-issues "a run doesn't see a Repair made while it is
  open" entry, now with one more consequence).
- A step-2 line count, Timed uploads (`.lrc`, `.srt`) and a preview of the parsed
  lines are out of scope, as the plan says.
