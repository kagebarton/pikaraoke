Model: Claude Opus 5.5 (author, 2026-11-09). Executor: Claude Sonnet 5.5.

# Defer timing: import playlists now, time them later with LRCLIB

## Goal

Ken will ask guests to build YouTube playlists for him to import. Songs headed for joint
alignment (Genius lyrics, no usable caption) usually end up retimed with an LRCLIB match on
Song Info, so the joint alignment run at import is wasted. A mass import can now skip it:
the song is separated and transcribed, which is all the LRCLIB check on Song Info needs, and
no lyric timing is made. The song waits on a library list until Ken times it with LRCLIB, or
with a plain Regenerate when LRCLIB has nothing that fits.

The same change retires `scripts/backfill_artifacts.py`.

Base: `dev` at `37d8d93`. Branch `defer_timing` (made by the author, 2026-11-09).

## Rulings (Ken, 2026-11-09)

1. **Opt-in, mass import only.** Two ways in: an `add_songs.py` flag, and a switch on the
   needs-a-pick page (`/library/picks`) that applies to songs listed from a playlist. Never the
   default, and never a single-song path: the search page's picker, a single-video link,
   Regenerate, and `regen_alignment_bundles.py` have no way to ask for it.
2. **Every joint-bound song skips**, whether or not the download found an LRCLIB match. One
   with no match waits on the list until Ken searches LRCLIB by hand or regenerates it.
3. **No lyrics until it is timed.** No karaoke file is written; a guest who queues the song
   early gets a plain video (stems and the vocal volume still work).
4. **A library list, "Waiting for LRCLIB timing"**, each row linking to its Song Info.
5. **Backfill is retired outright.** No stems-only mode in regen: a song with timed lyrics
   nearly always has stems, and Ken has never needed stems alone.
6. **The web switch lives on the needs-a-pick page**, not on the Add playlist form.

Assumptions stated to Ken on 2026-11-09, not objected to:

- The Genius prompt (CLI) and the Genius pick (web) stay. The download's LRCLIB search runs
  with the Genius title and artist and is scored against its lines, and the repair page
  starts its own LRCLIB search from them.
- Songs with a usable caption (cue route) and transcribe picks are untouched.
- In an `add_songs.py` run with a video link next to a playlist link, the video is timed
  fully even with the flag. A video in both: the first link that names it decides.

Decided by the author, flagged to Ken in the relay (overrule before Phase 2 if wrong):

- **Stale sweeps leave a deferred song alone** (CLI default run, web "Update"): it has no
  timing for a newer schema to redo. Every run that names it or rebuilds everything times it
  fully: `regen --song`, `regen --reset`, Song Info's Regenerate, web "Reprocess" and
  "Reset". The skip is never applied outside an import.

## What the code does today (read 2026-11-09 at `37d8d93`)

- **The LRCLIB check needs heard words, not timing.** `LibraryTools._fit_to_clip`
  (`pikaraoke/lib/library_tools.py`) fits the match against `heard_streams(job.bundle,
  asr_json3)` (`pikaraoke/lib/srt_slice_fit.py`): the bundle's `transcribe_words` plus the
  YouTube auto-caption `subtitles/<stem>.en.asr.json3` if the download got one. No bundle and
  no auto-caption: the fit returns `NO_REFERENCE`. The repair's LRCLIB search scores its
  matches against the bundle's `lyrics.lines` (`current_lines`) and starts from
  `lyrics.genius` (`repair_defaults`).
- **Where the transcribe words come from.** `LyricAlignStage._dereverb_gate`
  (`pikaraoke/pipeline/stages/lyric_align.py`) is the shared first step of the joint and cue
  routes: transcribe without refine, and below the yield floor de-reverb the stem and
  transcribe again. The joint route then runs `align_refine` (a second whisper pass over the
  whole stem), the DP matcher, the windowed re-align (more align passes on suspect spans),
  the LRCLIB fill plan, the veto and the edge snap, and writes the ASS, the SRT and the bundle.
- **The LRCLIB repair re-transcribes anyway.** It saves the fitted match as a sheet
  (`_lrc_repair_plan` -> `sheet_plan(..., "lrclib", ...)`) and regenerates through the cue
  route, which runs its own `_dereverb_gate`. The deferred run's transcribe exists only for
  the check.
- **A Genius pick reaches the pipeline as a choice file.** `genius.write_choice(yt_id,
  {"genius_id": N})`; `LyricsFetchStage` branch a reads it, fetches Genius, sets
  `lyrics_origin`, `genius`, `ytasr`, resolves the `.lrc` (`_resolve_lrclib` ->
  `lrclib.ensure_lrc`), and deletes the file. Writers: the search page's picker, the web
  needs-a-pick list (`LibraryTools.pick_lyrics` -> `_choice_for`), and regen's
  `prepare_lyrics` for a `sidecar` plan.
- **CLI import.** `add_songs.py` expands links (`resolve_urls`; `UrlEntry(id, source,
  status)`), downloads through `DownloadManager`, and hands every new or unprocessed song to
  `regen_alignment_bundles.resolve_and_run` via `handoff`. Songs without a usable caption get
  the Genius prompt, so their plan is `sidecar`.
- **Web import.** Add playlist (`LibraryTools.add_playlist`) downloads; `_check_download`
  queues a song with a usable caption and lists the rest on the needs-a-pick list with
  `source="playlist"` (single downloads: `"download"`). `pick_lyrics` writes the choice and
  enqueues the song in the processing manager.
- **Status.** `library_status.song_status`: no bundle -> `no_lyrics` (karaoke file) or
  `not_processed`; a bundle -> `behind` or `current` by schema. Lists are `SONG_LISTS`; web
  "Update" runs `songs_in_list("behind")`, "Reprocess" and "Reset" run `"all"`. The CLI's
  default scan (`library_regen.scan_folder`) takes a missing bundle or an old schema.
- **Backfill** (`scripts/backfill_artifacts.py`, 558 lines, tests
  `tests/unit/test_backfill_artifacts.py`) fills missing stems, karaoke or SRT with its own
  scan, prompt, lyric resolution and stage list. Its `LyricAlignStage` gets no stem worker,
  so it has no de-reverb retry, and it has no caption gate. Mentioned in `scripts/README.md`,
  `docs/README.md` (feature bullet, contents entry, "Backfilling an existing library"),
  `scripts/song_select.py`, `pikaraoke/lib/genius_lyrics.py`,
  `pikaraoke/lib/library_regen.py` (`build_stages` docstring) and
  `pikaraoke/pipeline/stages/load_vocal.py` (docstring; regen uses the stage too, so it stays).
  `plans/open-issues.md` on `dev` names "backfill's queued path".

## Design

### One trigger: a field in the choice file

A Genius pick that should skip timing writes `{"genius_id": N, "defer_timing": true}`.
`LyricsFetchStage` branch a, after a successful Genius fetch, sets
`ctx.artifacts["defer_timing"] = True` when `choice.get("defer_timing") is True` (read before
`delete_choice`). No other branch sets it, so a caption, a transcribe pick or a Genius failure
that falls through never defers.

Only two writers set the field: `prepare_lyrics` for a `sidecar` plan whose `SongJob` has
`defer_timing` (only `add_songs.py` sets that), and `pick_lyrics` for a playlist row. The
search page's picker and every regen path never do.

### The deferred route in `LyricAlignStage`

In alignment mode, when the lyrics carry no cue spans (the joint route) and
`ctx.artifacts.get("defer_timing")` is set, `run` calls a new `_run_deferred` and returns:

- `_dereverb_gate(ctx, vocal_wav)` for the transcribe words and the de-reverb stats.
- No align, matcher, windowed re-align, LRCLIB fill, veto or edge snap. No ASS, no SRT.
- `ctx.artifacts["lyric_method"] = f"{lyrics_origin}+deferred"`.
- The bundle through `_write_debug_capture`: `method_used="deferred"`, `words=None`,
  `joint_stats={"dereverb": stats}` when the gate ran a retry (else `None`),
  `transcribe_words`, `line_objects=[]`, `wrote_srt=False`, and `lrclib_ref` built exactly
  as the joint route builds it. Pull that build out of `run` into one helper both routes call,
  so the `lyrics.lrclib` record can't drift between them.

`capture_alignment_debug` is never off outside tests, so the deferred route needs no special
case for it.

**No `SCHEMA_VERSION` bump.** Only new bundles carry the new method, and a bump would mark
every song in the library behind.

`library_regen.is_deferred(bundle) -> bool` (`pipeline_decisions.method_used ==
"deferred"`) is the one test; everything below uses it.

### What reads a deferred bundle

- **Status:** `song_status` gives category `"deferred"`, checked before the schema test (a
  deferred song is never "behind"). `SONG_LISTS["deferred"] = category == "deferred"`.
- **CLI default scan:** `scan_folder` skips a deferred bundle unless `include_all` or `songs`
  names it. `--song` and `--reset` reach `reuse_plan`, which replays the Genius seed (no
  flag), so they time it fully.
- **Web runs:** "Update" takes the `behind` list, so it skips deferred songs with no change.
  "Reprocess" and "Reset" take `all` and time them fully. Song Info's Regenerate
  (`_regen_job` -> `reuse_plan`) times it fully. Check each of these with a test; no code
  change is expected.
- **Import paths:** a deferred song has a bundle, so `library_links.file_status` and
  `LibraryTools._is_unprocessed` count it as processed, and no later import offers it again.
  Check with a test; no code change is expected.
- **The LRCLIB repair:** works as is (bundle `transcribe_words`, `lyrics.lines`,
  `lyrics.genius`). After it the song is cue-route and leaves the list.
- **Words on pages:** `routes/library.py` `_subline` for the `deferred` list says whether an
  LRCLIB match is on disk ("LRCLIB match found" / "No LRCLIB match"; `status.lrc_match`), and
  the category fallthrough says "Waiting for LRCLIB timing". On Song Info, read every tile
  and branch that tests `category` or `method`, or shows line counts. A deferred song says
  "Waiting for LRCLIB timing" where a timed song shows timing, never "0 lines timed".
  Processing page `lyricLabel`: `+deferred` reads "Genius, timing later".

### `add_songs.py --defer-timing`

- `UrlEntry` gains `playlist: bool` (the link's `classify_url` kind).
- `--defer-timing` help: "For songs from a playlist link that get Genius lyrics: separate and
  transcribe, but leave lyric timing out, so you can time each one with an LRCLIB match on
  Song Info. They play without lyrics until then. Songs from video links, and songs with a
  usable caption, are timed as usual."
- `handoff` takes the playlist songs' paths and sets `SongJob.defer_timing = True` on their
  jobs (new field, default `False`). Map a downloaded path to its entry by
  `extract_youtube_id`.
- `prepare_lyrics`: a `sidecar` plan on a job with `defer_timing` writes the field into the
  choice. Every other plan kind ignores it: a caption is cue-route, `t` transcribes, `k` skips.
- With the flag, the report ends with one line: how many playlist songs will skip timing if
  they get Genius lyrics.
- `regen_alignment_bundles.py` gets no flag.

### The needs-a-pick switch

- `pick_lyrics(song_path, pick)` accepts `pick["defer_timing"] is True` only with `kind ==
  "genius"` on an entry whose `source == "playlist"`. Otherwise it raises
  `RegenError("Only songs from a playlist can skip timing.")`. `_choice_for` writes the field.
- `pick_pass.html` in list mode (the `/library/picks` page only, never a run's pick pass): a
  switch above the list, off on every page load, shown only when a listed song came from a
  playlist. Label: "Skip timing for playlist songs", with an (i) note: "Separates and
  transcribes them but leaves lyric timing out, so you can time each one with an LRCLIB match
  on Song Info. They play without lyrics until then. Single downloads are always timed." With
  it on, a Genius pick on a playlist row sends `defer_timing: true`. Each row already says
  where the song came from. Make sure that shows, so it's clear which rows the switch covers.
- Strings go through `_()` like the rest of the page.

### Accepted edges

- **A song LRCLIB can't time pays twice.** It is transcribed at import and then fully timed by
  a later Regenerate. The time saved only lands on songs the LRCLIB repair times.
- **The repair transcribes again** through the cue route, so the deferred run's transcribe
  is only there for the check.
- **No stale karaoke file to clean up.** Both import paths only process songs that have no
  bundle and no karaoke file.

## Phases

Stop after each phase: relay a short summary, give the checkpoint prompts (CLAUDE.md
Checkpoints), and let Ken `/compact` before the next. Claude can't run the GPU pipeline on
the VM: tests mock the workers, and Ken runs real imports on Windows in Phase 5.

### Phase 1: retire backfill

1. Delete `scripts/backfill_artifacts.py` and `tests/unit/test_backfill_artifacts.py`.
2. `scripts/README.md`: drop the backfill sections; rewrite "Architecture notes" for regen
   alone (the duplicated stage list is now `processing_manager.start()` against
   `library_regen.build_stages`); drop the `Files` entry for the script, keep
   `load_vocal.py` (regen uses it).
3. `docs/README.md`: replace the backfill bullet, contents entry and section with one on
   adding songs and reprocessing from the command line (`add_songs.py`,
   `regen_alignment_bundles.py`, pointing at `scripts/README.md`).
4. Docstrings that name backfill: `scripts/song_select.py`, `pikaraoke/lib/genius_lyrics.py`,
   `pikaraoke/lib/library_regen.py` (`build_stages`), `pikaraoke/pipeline/stages/load_vocal.py`.
5. Full test run; `grep -rn backfill_artifacts` comes back empty outside `plans/`.

Commit: `chore(scripts): retire backfill_artifacts.py; regen and add_songs cover it`.
At landing, the `plans/open-issues.md` line "backfill's queued path" is edited on `dev` in a
plan-only commit.

### Phase 2: the deferred route, its bundle and its status

1. `LyricsFetchStage` sets `defer_timing` from the choice (tests in `test_lyrics_fetch.py`:
   set with the field, unset without it, unset when Genius fails).
2. `LyricAlignStage._run_deferred` and the shared LRCLIB-ref helper (tests in
   `test_lyric_align.py` with the worker mocked: transcribe called, `align_refine` never
   called, no ASS or SRT written, the bundle's method, transcribe words, lines, Genius and
   LRCLIB records; the joint route runs as before without the flag).
3. `is_deferred`, the `deferred` status category and list, and the `scan_folder` skip (tests
   in `test_library_status.py` and `test_library_regen.py`: deferred at an old schema is not
   behind; default scan skips it, `--song` and `include_all` take it; `reuse_plan` on it gives
   a Genius seed without the flag; it counts as processed for `file_status`).
4. Tests in `test_library_tools.py`: "Update" leaves it out, "Reprocess" includes it,
   `_regen_job` gives a full plan, and `check_lrc_timing` fits against its transcribe words.

Commits: `feat(pipeline): a Genius pick can defer lyric timing` (steps 1-2);
`feat(library): deferred songs wait on their own status and skip stale sweeps` (steps 3-4).

### Phase 3: `add_songs.py --defer-timing`

1. `UrlEntry.playlist`, `SongJob.defer_timing`, `handoff`, `prepare_lyrics`, the flag and its
   report line.
2. Tests in `test_add_songs.py` and `test_library_regen.py`: a playlist song's Genius pick
   writes the field; a video link's doesn't; without the flag nothing does; a caption plan or
   `t` with the flag writes no choice field; a video in both links follows the first one.
3. `scripts/README.md` `add_songs.py` section: the flag and what it does.

Commit: `feat(scripts): add_songs --defer-timing for playlist imports`.

### Phase 4: the web switch, the list and the words

1. `pick_lyrics` / `_choice_for` validation (tests: playlist row accepted and the choice
   carries the field; download row refused; transcribe with the field refused).
2. The switch and its (i) note on `/library/picks`; the `deferred` list where the library
   lists are offered; `_subline`; Song Info wording; the processing label.
3. Route tests in `test_library_routes.py` for the pick with the field and for the list.
4. `ui-check` (VM, fake jobs): the switch shows only with a playlist row listed, is off on
   load, a pick with it on sends the field. The list shows a deferred song with its line and
   a working link. Song Info for a deferred song reads sensibly at phone width.

Commits: `feat(library): needs-a-pick switch to skip timing for playlist songs`;
`feat(ui): Waiting for LRCLIB timing list and wording`.

### Phase 5: Ken's checks

Ken fetches the branch on Windows and runs the test plan below. No code unless he finds
something.

## Test plan (manual, for the PR)

- [ ] `add_songs.py <playlist> --defer-timing` on a small playlist with at least one song that
      has a usable caption and one that doesn't. The caption song is timed. The Genius one has
      stems, no karaoke file, and is on "Waiting for LRCLIB timing".
- [ ] Its processing is visibly shorter than a full joint run of a similar song.
- [ ] On its Song Info, the LRCLIB check fits, Repair with LRCLIB times it, and it leaves the
      list.
- [ ] Same playlist without the flag: the Genius song is fully timed.
- [ ] A video link next to the playlist link, with the flag: the video is fully timed.
- [ ] Web: Add playlist, then on the needs-a-pick page turn the switch on and pick Genius for
      a playlist song: processed without timing. A single download on the same page is timed.
      Reload: the switch is off.
- [ ] Queue a deferred song: it plays as a plain video; the vocal volume works.
- [ ] Regenerate on a deferred song times it fully.
- [ ] A default `regen_alignment_bundles.py` run lists no deferred song.

## Follow-ups (not in this plan)

None yet.

## Results log

(Executor: one row per phase: commit hashes, test counts, ui-check outcome, anything that
deviated from this plan and why.)
