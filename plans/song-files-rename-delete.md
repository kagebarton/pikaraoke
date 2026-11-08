Model: Claude Opus 5.5 (author, 2026-11-08). Executor: Claude Sonnet 5.5.

# Rename and delete carry every file a song owns

## Problem

`SongManager.rename` and `SongManager.delete` (`pikaraoke/lib/song_manager.py`)
move or remove only four sidecar kinds, from a fixed list in
`_get_companion_files`: `subtitles/<stem>.srt`, `karaoke/<stem>.ass`,
`vocal/<stem>---vocal.m4a`, `nonvocal/<stem>---nonvocal.m4a`. Every kind added
since stays under the old name. A probe (fake library, one rename and one
delete) left 13 of 17 kinds behind both times:

| Folder | Kind | Handled today |
| --- | --- | --- |
| `subtitles/` | `<stem>.srt` | yes |
| `subtitles/` | `<stem>.srt.generated` (provenance marker) | no |
| `subtitles/` | `<stem>.en.srt` | no |
| `subtitles/` | `<stem>.en.asr.json3` (YTASR source) | no |
| `subtitles/` | `<stem>.en.vtt` (download leftover) | no |
| `karaoke/` | `<stem>.ass` | yes |
| `lyrics/` | `<stem>.lrc` | no |
| `lyrics/` | `<stem>.custom.txt`, `.custom.srt`, `.lrclib.srt` | no |
| `lyrics/` | `<stem>.caption-edited.srt`, `.movie-edited.srt`, `.lrclib-edited.srt` | no |
| `alignment_debug/` | `<stem>.json` (bundle) | no |
| `vocal/`, `nonvocal/` | `<stem>---vocal.m4a`, `<stem>---nonvocal.m4a` | yes |
| `dereverb/` | `<stem>---dereverb.m4a` | no |

What a rename does to the song, from that:

- Loses its hand-made sheet, so the next regen or repair times it from another source.
- Loses its bundle: song info shows no timing detail, `file_status` says "not processed".
- Its pipeline-made `.srt` moves without its `.generated` marker, so the next
  regen reads it as an uploader caption (`find_local_srt`, `is_generated`).

Two more holes in the same code:

- **Busy songs.** Rename and delete refuse only songs in the play queue. Deleting
  a song mid-run lets the run write its `.ass`/`.srt`/marker after the song is
  gone. Renaming one mid-run puts those files under the old name and leaves the
  renamed song `pending`. The library has 11 orphan sets matching the delete case
  (Chinese songs processed 2026-11-03: video, stems, DB row gone; `.ass`, `.srt`,
  `.srt.generated` left; no bundle because they took the transcribe route). Not
  proven: no logs.
- **Guests can rename.** `files.rename_file` (`routes/files.py`) flashes "no
  permission" for a non-admin and then renames anyway (no `return`).
  `batch_song_renamer.rename_song` has no admin check at all.

## Decisions (Ken, 2026-11-08)

1. **Delete backs up the hand-made sheet** (Ken: "move it to some backup
   folder"). Built as: before removing anything, delete snapshots the song's own
   text files with the existing `backup_text_folders(folder, stems=[stem])`
   (`library_regen.py`) into `regen_backups/<UTC>/`, the same root and layout
   every regen backup uses. That covers the sheet and also the bundle,
   captions, karaoke file and `.lrc`: one existing helper, a few KB, and the
   delete is undoable for every text file. Restore is a manual copy-back; a
   re-download does not pick it up on its own. Stems and the video are not
   backed up (regenerable / re-downloadable).
2. **A busy song: refuse both.** Rename and delete refuse a song that is
   processing, queued for processing, or waiting for a lyrics pick, with an
   error like the play-queue one. The admin cancels first.
3. **Scope.** The guest-rename fix is in, as its own commit. The 11 orphan sets
   are **not** cleaned up.
4. **Verify.** Tests, then a live rename round-trip on one real song (Step 4).
   No real delete.

## Base

`dev` at `225da7b`, branch `song_files` (created; this plan is uncommitted).
Work in the main checkout. Ken's own `pikaraoke` instance is running from it;
switching branches does not disturb it until it restarts, but Step 4 needs it
stopped (one instance at a time: shared `~/.pikaraoke` and library).

## Design

### Which files a song owns (`library_regen.py`)

The ownership rule already exists for backups: `_claims` / `_owner` /
`_all_stems`. A folder entry belongs to the longest song stem it equals or
starts with plus `"."`, so `Song` never claims `Song.live.srt`. Reuse it; add
next to it:

```python
# Per-song audio stems: ``<dir>/<stem>---<dir>.m4a``.
STEM_DIRS = ("vocal", "nonvocal", "dereverb")


def song_files(song: Path) -> list[Path]:
    """Every file ``song`` owns beside it: its own entries in BACKUP_DIRS and its stems.

    ``song`` need not exist yet: asking about a new name lists what that name
    would take over.
    """
```

- Text folders: each file in `song.parent / sub` for `sub` in `BACKUP_DIRS`
  whose `_owner(name, all_stems) == song.stem`, with
  `all_stems = _all_stems(song.parent) | {song.stem}` (the union is what makes a
  not-yet-existing name work).
- Stem folders: `song.parent / d / f"{song.stem}---{d}.m4a"` for `d` in
  `STEM_DIRS`, when it is a file.
- Files only; nothing writes a per-song folder.
- `.m4a` only. The old `.M4A` check is dropped: every writer
  (`ffmpeg_transcode`, `lyric_align`) and the player (`playback_controller`)
  use `.m4a`.

`song_manager.py` imports it (checked: no import cycle, `library_regen` loads
in ~0.4 s, no torch). Delete `_get_companion_files`.

### Rename (`SongManager.rename`)

Same signature and return. Changes:

1. **The song stays in its own folder:** `new_path = dirname(song_path) / (new_name + ext)`.
   Today it is `download_path / ...`, which moves a song in a subfolder to the
   library root while its sidecars stay behind (the scanner walks subfolders).
2. **Check everything before touching anything.** Raise `FileExistsError`
   (nothing moved, SongList and DB untouched) when any of these hold:
   - `new_path` exists, or another song file has the new stem with any
     extension (`new_stem in _all_stems(folder)`; catches `New.mp3` beside `X.mp4`);
   - `song_files(new_path)` is not empty (orphans the new name would take over,
     e.g. a stray `subtitles/New.srt.generated` that would mark the renamed
     song's real caption as generated);
   - any destination below already exists (covers `Old.live.srt` ->
     `New.live.srt` when a song `New.live` owns that name).
3. **Moves.** `[(song, new_path)] + [(f, f.parent / (new_stem + f.name[len(old_stem):])) for f in song_files(song)]`.
   Every owned name starts with the old stem, so one rule covers the text and
   stem folders.
4. **A failed move rolls back.** On `OSError`, move the done pairs back in
   reverse (log any that fail), then re-raise. SongList and DB are updated only
   after every move succeeded (as today).

### Delete (`SongManager.delete`)

1. `backup_text_folders(song.parent, stems=[song.stem])` first, while the song
   is still on disk (`_all_stems` needs it). An `OSError` propagates and
   nothing is deleted. Log the backup folder at info when one was made
   (`None` means the song had no text files; no empty folder is created).
2. `files = song_files(song)`, then remove the song and each file, suppressing
   `FileNotFoundError` as today.
3. SongList, DB, `song_deleted` event as today.

`pipeline_tracker._delete_song` (a cancelled download's file) calls this too and
already catches and logs.

### Routes

- `files.rename_file`: drop its own `os.path.isfile(...)` pre-check (superseded
  by `SongManager.rename`). Catch `FileExistsError` first and flash the existing
  "Filename already exists" string; keep the `OSError` branch.
- `files.delete_file`: catch `OSError` from `delete` and flash an error (new
  string) instead of the "Song deleted" one.
- `batch_song_renamer.rename_song`: drop its `os.path.isfile` pre-check too (its
  case-only two-step stays). Use `rename`'s return value for the temp path and
  for `new_file_name` instead of rebuilding them from `download_path`. Catch
  `FileExistsError` -> the existing "already exists" error response, other
  `OSError` -> an error response.

### Busy guard

One helper in `routes/files.py`, imported by `batch_song_renamer.py`:

```python
def song_busy_message(song_path: str) -> str | None:
    """Why a song can't be renamed or deleted right now, or None."""
```

It returns a new translatable message (with a `# MSG:` comment) when
`k.library_tools.is_busy(song_path)` or `k.library_tools.is_waiting_for_pick(song_path)`.
Called by `delete_file`, `edit_file` (GET), `rename_file` (POST) and
`rename_song`, after their admin check, beside the existing play-queue check.
The play-queue checks and their translated messages stay as they are.

It lives in the routes, not `SongManager`: the manager doesn't know about
processing, and the tracker's cancel-then-delete of a download calls `delete`
itself once the job has stopped.

Translation catalogs are not touched (regenerated in batches).

## Order

**Step 0.** Commit this plan (`docs(plans): rename and delete carry every file a
song owns`). Run the full suite for a baseline count (Results log row 0).
`graphify affected "SongManager.rename"` and `"SongManager.delete"` list the
tests to start from.

**Step 1: `fix(routes): a guest can't rename a song`.**
- `rename_file`: `return redirect(referrer)` after the non-admin flash.
- `rename_song`: non-admin gets `_error_response` with the existing "You don't
  have permission to edit songs" string.
- Tests (`test_files_routes.py`, `test_batch_renamer.py`, each file's own
  admin setup): a non-admin POST to each route leaves the song where it was and
  never calls `rename`. Mutation-check each (remove the guard, test fails).

**Step 2: `fix(song_manager): rename and delete carry every file a song owns`.**
- `song_files` + `STEM_DIRS`, Rename, Delete and the Routes changes above.
- Tests in `test_song_manager.py` on real files in `tmp_path`, real
  `EventSystem` and `KaraokeDatabase`:
  1. Rename moves each of the 17 kinds in the table (parametrized): present
     under the new name, gone under the old.
  2. Delete removes each of the 17 kinds (parametrized).
  3. `Song` beside `Song.live`: renaming or deleting `Song` leaves every file of
     `Song.live` alone.
  4. Rename refuses, with nothing moved and SongList/DB unchanged, when: the new
     name is another song with a different extension; an orphan the new name
     would own exists (`subtitles/New.srt.generated`).
  5. A move failing partway (patch `os.rename` to raise on a later call) puts
     every file back under the old name, raises, and leaves DB/SongList unchanged.
  6. Delete copies the song's sheet and bundle into `regen_backups/<UTC>/lyrics/`
     and `.../alignment_debug/` before removing them; a song with no text files
     makes no backup folder; a backup that raises `OSError` deletes nothing.
  7. A song in a subfolder is renamed in place, not moved to the library root.
- Route tests that exercised the dropped `isfile` pre-checks now expect the
  same flash/response from a `FileExistsError` raised by `rename`.

**Step 3: `fix(routes): rename and delete refuse a song still processing`.**
- `song_busy_message` and its four call sites.
- Tests: each of the four routes refuses a song `is_busy` and a song
  `is_waiting_for_pick` (file left in place, `rename`/`delete` not called), and
  still acts on a song that is neither. Mutation-check the helper.

Each step: compile/import-smoke, pre-commit on the changed files
(`pre-commit run --config code_quality/.pre-commit-config.yaml --files ...`),
full suite, read `git diff --cached`, commit, then a Results log row.

**Step 4: live round-trip (no commit).**
1. Ken's instance is running (`pgrep -af pikaraoke`). **Ask Ken before
   stopping it.** Then start the branch:
   `/home/ken/miniconda3/envs/pik/bin/python -m pikaraoke.app` (background).
2. Song: `Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ.mp4`
   (two spaces after "Good"). It has 10 sidecars: `subtitles/` `.srt`,
   `.srt.generated`, `.en.asr.json3`; `karaoke/` `.ass`; `lyrics/` `.custom.srt`,
   `.lrc`; `alignment_debug/` `.json`; `vocal/`, `nonvocal/`, `dereverb/` stems.
   Record `sha1sum` of all 11 files.
3. Log in as admin with a cookie jar (`POST /auth`; password in
   `~/.pikaraoke/config.ini`, never print it). `POST /files/edit` with
   `old_file_name` = the full path, `new_file_name` = `Wicked - For Good (rename test)`
   (the route appends `---wzSeub9W4QQ`).
4. Check: 11 files under the new stem, none under the old; song info for the
   new path names movie subtitles as the lyric source and shows per-line timing.
5. Rename back to the original stem. The 11 checksums match step 2, at the
   original paths.
6. Stop the branch instance and tell Ken to restart his own.

## Not covered

- An open bulk library run still lists a renamed or deleted song by its old
  path; queuing the run then fails that song's job. Pre-existing.
- `regen_backups/` snapshots keep the old name, so a renamed song's history
  shows only its current bundle.
- The bundle records the old stem inside (`song_stem`, `lyrics.source_path`).
  Nothing reads `song_stem`; `source_path` is read only for its suffix
  (`is_edited`). Left as the record of that run.
- The 11 orphan sets (Decision 3), `movie_subs/`, `backups/`, `zh_probe/` (not
  per-song), and the Genius pick cache (keyed by video ID, unaffected by a rename).

## Stop

After Step 4. Don't land on `dev` and don't run `/code-review`. Report the
Results log and say a review is due: Step 2 is multi-file and rewrites the file
moves.

## Results log

| Step | Commit | Tests | Notes |
| --- | --- | --- | --- |
| 0 | `b0dadb5` (plan) | 3354 passed | Baseline at `225da7b` + the plan commit. |
| 1 | `dee0850` | 3356 passed (+2) | Guard in `rename_file` and `rename_song`; one guest-POST test each, both fail with their guard removed. `test_files_routes.py` fixture gained a `secret_key` so `flash` works; `test_batch_renamer.py` gained a Flask client fixture (it had no route tests). |
