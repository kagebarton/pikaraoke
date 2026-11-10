Model: Claude Sonnet 5.5 (executor, Phases 1-3). Author: Claude Fable 5.2, 2026-11-10. Judge
at GATE P: Claude Fable 5.2 (Ken's call, 2026-11-10), then Ken. Phases 4-6 are
loose and get their spec after the gate.

# LRCLIB timing at download, picked by fit

**Status: Phase 1 built 2026-11-10 (Results row 4). Phase 2 run and recorded 2026-11-10
(Results row 5, tables below); stopped at 2c for Ken's listening session 2. Phase 3 run and
recorded 2026-11-10 (Results row 6, tables below); stopped at 3d for listening session 3.
Ken's verdicts are in for all 21 `new` picks, all 16 not-new no-reference picks and one caption
pick, Colbie Caillat - Realize (Results rows 7-10). **GATE P read 2026-11-10 by Fable: rule 3 is
not met, seven wrong picks ("GATE P read", Results row 11). Ken's ruling (go or stop,
Decision 8) is pending.**

## Goal

A first-time download with a Genius lyric pick is timed from an LRCLIB record automatically
(cue align, the record's own lines as the sheet) when a record passes a fixed bar against the
words the transcriber heard. Otherwise it goes to the joint matcher exactly as today, with no
message. Today the LRCLIB route is reached only by hand, on Repair.

This revives `archive/lrclib_auto_timing` (stopped at GATE M, 2026-11-06). Read that plan's
"GATE M read" first: `git show archive/lrclib_auto_timing:plans/lrclib-auto-timing.md`.

## What changed since GATE M

GATE M stopped because the fit could not see singing that no LRC line claims: an LRC that
stops early or skips sung lines passed. Two changes answer that.

1. **A new check: heard words no line claims.** After the fit, each heard word is either
   claimed by an LRC line near its fitted time or not. The measure is the longest run of
   consecutive unclaimed words.
2. **Pick by fit.** Every record LRCLIB returns is fitted, and the pick is made among the
   records that pass, clean ones first. GATE M judged the bar over every candidate, since
   "whichever record arrives meets the bar". Here the pick order is part of the bar.

Two GATE M conditions are dropped: the length gap and the unheard end lines. Both refused good
records (movie clips, songs with an outro the transcriber missed), and the new check covers
what they were for.

## Decisions

Carried from the archived plan (Ken, 2026-11-03), unchanged:

1. The LRC's own lyrics are the karaoke words.
2. The download page is unchanged. The switch happens after the download.
3. New downloads only. Regenerate, bulk runs and Repair never switch a song.
4. Genius picks only. Pasted custom lyrics stay on joint.
5. Its own lyric source type and label.
6. The label stays after review.
7. Measure first.
8. The bar is set for zero wrong picks on the measurement. If it is not reached, the feature
   stops.

Ken, 2026-11-10:

9. It applies to every first-time download with a Genius pick: search page, direct link,
   playlist rows, `add_songs`.
10. It lands before `defer_timing`, which stays parked.
11. Pick by fit, as defined below.
12. One mistimed line is allowed. Ken heard all seven of his Repair picks that carry one; each
    is fine (an instrumental break, a one-word line, a repeat).
13. Coverage of 23 of his 28 Repair picks is enough to build.
14. Excusing an unclaimed stretch the Genius sheet lacks too (video dialog, backing vocals) is
    a later add-on, not in this plan.
15. Ken judges about 10 songs a session.
16. A refused song goes to joint silently.
17. The holdout is thirty songs the author listed (Phase 0), in two batches, all meant to take
    a Genius pick. Ken adds them; he does not choose them.

## The bar and the pick (pre-registered)

Fixed here, before any number under this plan exists. GATE P reads these values only.

**The bar.** A record passes when its fit against the transcribe stream
(`fit_slice(lrc_to_srt(synced), {"transcribe": words}, clip_length)`) has all of:

- status `fits`;
- `speed == 1.0`;
- at most 1 mistimed line;
- longest unclaimed run of at most 12 heard words.

**Unclaimed run.** A heard word is *claimed* when the fit's second-pass match gives it to a
sheet token and the word starts within `FLAG_TOLERANCE_S` (5 s) of that token's expected time
under the final speed and shift. Token times are spread evenly over their cue, as the second
pass does. Tokens of cues that fall outside the clip count like any other. The unclaimed run is
the longest stretch of consecutive heard words, in stream order, with none claimed.

**The pick.** Over the synced records of one LRCLIB search:

1. Fit each. Keep those that pass the bar.
2. Records share a *timing* when their synced text is equal after stripping each line and
   dropping empty lines. A timing's size is the number of the search's synced records that
   carry it.
3. Order the passing records by: fewer mistimed lines; larger timing; shorter track name;
   shorter album name; lower id. The pick is the first. With none passing there is no pick.

**The search.** Free text, the query Repair's LRCLIB box starts with
(`LibraryTools.custom_start`): `" ".join(t for t in lrclib.clean_key(genius_title or
default_query(song), genius_artist or "") if t)`, sent with `lrclib.search_query`. The build
will search the same way. Today's unattended fetch searches by title and artist fields so a
text-only pick can't land on another song; with a fit deciding, the wider search is safe and
finds more records.

## Where the bar came from (exploratory, 2026-11-10)

Not a gate read. The limits were chosen with these results in sight, on scratch scripts that
are not in the repo.

- The unclaimed run on the GATE M LRC-wrong records: The A Team 12572148, 89 words; That's The
  Way It Is, 20; Stronger, 14; Drowning, 6. On Ken's Repair picks that pass, 2 to 11.
- Drowning's wrong records are caught only by their one mistimed line. That flag is on 7 of
  the song's 20 records; a clean record exists and the pick order takes it. On Ken's good
  picks the one flag is on every record of the song, because it comes from the hearing.
- Ken's 28 Repair picks: 23 pass. The five that don't: three long unclaimed stretches (video
  dialog, backing vocals the sheet lacks), one repeated-words song Ken hears as mistimed in
  the middle, one that fits only at another speed.
- Caption songs: about 60 of 112 get a pick. None is a GATE M LRC-wrong record. About half of
  those picks were never judged by anyone.

So what is unproven: the limits were fitted to four wrong songs and 28 good ones, and the
caption-song picks are unjudged. This plan judges those picks and adds songs the exploration
never saw.

**Known hole, accepted by Ken (Decision 12):** a song whose every record carries the same
real one-line error would be picked. No example is known.

## Phase 0: holdout songs (Ken, any time)

The exploration used every song in the library, so the holdout must be new songs.

- **Baseline, done 2026-11-10:** `~/.pikaraoke/tmp/lrclib_fit_pick/baseline_ids.txt`, 168
  lines, sha256 `610e84eeee4209473ba33b50d583ea4739d3086c85bf940cde950e5645315eb7`. One id per
  library song (YouTube id, or the file stem for a song without one). A song not in it is
  *new*. Renaming a song without a YouTube id would make it look new; Phase 3 checks for that.
- **Ken adds these thirty songs** (a batch of twelve, then eighteen) with `add_songs` on Windows, taking the Genius pick at each
  prompt. They time by joint as today and stay in the library.

  | Song | YouTube id |
  |---|---|
  | Bruno Mars - Just The Way You Are | `LjhCEhWiKXk` |
  | Bruno Mars - When I Was Your Man | `ekzHIouo8Q4` |
  | The Lonely Island - I'm On A Boat | `avaSdC0QOUM` |
  | The Lonely Island - Jack Sparrow | `GI6CfKcMhjY` |
  | Jessie J - Price Tag | `qMxX-QOV9tI` |
  | Tangled - I See the Light (Sing-Along) | `ILRs2r6lcHY` |
  | Frozen - For the First Time in Forever (Sing-Along) | `ZrX1XKtShSI` |
  | Frozen 2 - Into the Unknown (Sing-Along) | `mzhv_dg_UBA` |
  | Encanto - We Don't Talk About Bruno (Sing-Along) | `YRpvIiz9G8A` |
  | Camp Rock 2 - Wouldn't Change a Thing | `62llzl7iKkE` |
  | Michelle Branch - Everywhere | `HLCasyAh7ic` |
  | Westlife - Flying Without Wings | `vKPGxGCFgTs` |
  | Bruno Mars - Grenade | `SR6iYWJxHqs` |
  | Bruno Mars - The Lazy Song | `fLexgOxsZu0` |
  | Bruno Mars - Locked Out Of Heaven | `e-fA-gBCkj0` |
  | Silk Sonic - After Last Night | `-cy_tDQPXHk` |
  | The Lonely Island - YOLO | `z5Otla5157c` |
  | The Lonely Island - I Just Had Sex | `lQlIhraqL7o` |
  | Ingrid Michaelson - Be OK | `vpMI8Qu5fsc` |
  | Sara Bareilles - Gravity | `rEXhAMtbaec` |
  | Sara Bareilles - King of Anything | `eR7-AUmiNcA` |
  | Jessie J - Flashlight | `DzwkcbTQ7ZE` |
  | Backstreet Boys - Show Me The Meaning Of Being Lonely | `aBt8fN7mJNg` |
  | NSYNC - I Want You Back (US Version) | `n-2C2wOFavc` |
  | Moana - Where You Are (Sing-Along) | `RTWhvp_OD6s` |
  | Frozen 2 - Show Yourself | `nrZxwPwmgrw` |
  | Frozen 2 - Lost in the Woods (Sing-Along) | `_8jNbZIsBQU` |
  | Tangled - I've Got a Dream (Sing-Along) | `zi5Z6rNU9Hw` |
  | Tangled - Mother Knows Best (Sing-Along) | `-7jWt3JvJto` |
  | Encanto - Surface Pressure (Sing-Along) | `X-NH1uUfr0U` |

- **How they were chosen** (author, 2026-11-10): artists and kinds of video already among
  Ken's Repair picks (Bruno Mars, The Lonely Island, Jessie J, Disney sing-alongs, Camp Rock,
  2000s pop), found by a YouTube search from the VM, keeping the official or Disney upload
  when it carries no uploader English captions, so the song takes a Genius pick. LRCLIB was
  not consulted for any of them, and must not be before Phase 3 runs.
- Phases 1 and 2 do not wait for this. Phase 3 does.

## Phase 1: the measure, the pick and the probe (Sonnet)

Read-only on the library, GPU-free, on the VM, network for LRCLIB only.

- [x] **1a. Anchor check.** On branch `lrclib_fit_pick`. Confirm these exist as this plan uses
  them, else STOP and say what differs:
  `srt_slice_fit.fit_slice`, `heard_streams`, `lrc_to_srt`, `flagged_runs`, `unheard_runs`,
  `SliceFit`, `_fit_one_stream`, `_match_by_time`, `_best_speed`, `_CueTokens`,
  `FLAG_TOLERANCE_S`, `MIN_UNHEARD_RUN`; `cue_align._token_expected_times`;
  `lrclib.search_query` (raises `LrclibUnavailable`), `clean_key`, `read_song_lrc`;
  `library_regen.default_query`, `read_bundle`, `media_duration`, `SongJob`, `LRC_ORIGIN`;
  `library_status.library_statuses` and `SongStatus` (`origin`, `method`, `edited`,
  `youtube_id`, `path`); `srt_cues.cue_spans_from_srt`; `get_platform.get_temp_directory`.
  The archived probe is the model for reading a song and caching a search:
  `git show archive/lrclib_auto_timing:scripts/lrc_auto_timing_probe.py` (`group_of`,
  `search_query_for`, `search_records`, `candidate_entries`, `disk_record`, `read_caption`,
  `caption_ok`, `title`, `md_table`, `write_tsv`). Copy what fits; do not restore the file.

- [x] **1b. `SliceFit.unclaimed_run`** in `pikaraoke/lib/srt_slice_fit.py`. A new field,
  `int`, 0 unless the status is `fits`, defined as in "The bar and the pick". It is computed in
  `_fit_one_stream` from the second pass's token-to-word assignment and the final speed and
  shift, on the stream that fit used. Share the expected-times loop with `_match_by_time`
  instead of repeating it. Update the `SliceFit` docstring. No caller changes.
  Tests in `tests/unit/test_srt_slice_fit.py`, made-up words: a sheet covering every heard
  word; a sheet missing a middle stretch (the run equals the heard words in it); a sheet that
  stops early (the tail); a word the match takes but more than 5 s from its token's time is
  not claimed; a refused fit gives 0.
  Commit: `feat(lyrics): the LRC fit counts heard words no line claims`.

- [x] **1c. `pikaraoke/lib/lrc_auto_pick.py`**, new, pure (no I/O). This is the code the
  build will call, so the probe measures what ships.
  - `MAX_MISTIMED = 1`, `MAX_UNCLAIMED_RUN = 12`, each with a comment pointing at this plan.
  - `refusal(fit: SliceFit) -> str | None`: the first bar condition the fit fails, as
    `"no_fit"`, `"speed"`, `"mistimed"`, `"unclaimed"`; None when it passes.
  - `timing_key(synced: str) -> str` as in the pick's step 2.
  - `evaluate(records, words, clip_length)`: every synced record with its fit, refusal and
    timing size, the passing ones first in pick order.
  - `pick(records, words, clip_length)`: the first passing entry of `evaluate`, or None.
  Tests in `tests/unit/test_lrc_auto_pick.py`, with `fit_slice` patched or small made-up
  sheets: each bar condition refusing; a clean record beating a one-flag record from a larger
  timing; the larger timing winning among clean ones; track name, album name and id as
  tie-breaks; records without synced text ignored; none passing gives None.
  Commit: `feat(lyrics): pick an LRCLIB record by how it fits the heard words`.

- [x] **1d. `scripts/lrc_fit_pick_probe.py`.** One command:
  `python scripts/lrc_fit_pick_probe.py --folder PATH [--out DIR] [--baseline FILE]
  [--old-cache DIR] [--listen-dir DIR] [--only ID ...]`.
  - `--out` defaults to `Path(get_temp_directory()) / "lrclib_fit_pick"`. It holds lyric text
    (cache, sheets), so nothing in it is ever committed. Write `<out>/started` first. A run
    with `--only` covers just those songs.
  - **Groups**, from the library as it stands:

    | Group | Rule |
    |---|---|
    | `picks` | origin `lrclib_srt`, bundle has `transcribe_words` |
    | `joint` | origin `genius`, method `joint`, `transcribe_words` |
    | `caption` | origin `srt`, not edited, `transcribe_words`, `subtitles/<stem>.srt` exists with no `.srt.generated` beside it |
    | `out_of_scope` | everything else, with the reason (`custom`, `movie_srt`, `no_bundle`, `no_words`, `edited`, `no_caption_file`) |

    A song in a group but with no clip length is skipped as `no_length`. With `--baseline`,
    a song whose id is not in the file is marked `new`.
  - **Records.** `<out>/cache/<youtube_id>.json` holds `{"query", "records"}` (synced records
    as returned). Read it when present, else search and write it. On `LrclibUnavailable` write
    nothing, give the song the reason `lrclib_unavailable`, go on.
  - **Pool and pick.** The pool is the search's synced records. The pick is
    `lrc_auto_pick.pick` over the pool. The song's on-disk `.lrc`, when it is a match, is
    fitted and reported in its own columns; it joins the pool only if the search returned its
    id.
  - **Reference (`caption` songs).** Fit the caption itself, as the archived probe did:
    `ref_ok` when it fits, `speed == 1.0`, `|shift_s| <= 1.5` and
    `flagged_runs(mistimed, unheard, MIN_FLAGGED_RUN)` is empty. On a `ref_ok` song, every
    record that passes the bar also gets a *reference fit*: the same `fit_slice` call with
    the caption as the heard stream, `{"caption": caption_stream}`. The caption stream is each
    caption cue's tokens (tokenised as the fit tokenises sheet lines) at times spread evenly
    over the cue, as `{norm, start}`. Add it as `srt_slice_fit.sheet_stream(srt_text)` beside
    `heard_streams`, with a test; it rides in this commit.
  - **Reference flag** (a screen, not a verdict). A passing record on a `ref_ok` song is
    flagged when any holds, and the row names which: the reference fit is not `fits`
    (`ref_refused`); it has a mistimed line (`ref_mistimed`); its unclaimed run is over 12
    (`ref_unclaimed`: caption words no LRC line claims); `unheard_runs(unheard,
    MIN_UNHEARD_RUN)` is not empty (`ref_unheard`: LRC lines the caption lacks); its shift
    differs from the transcribe fit's by more than 1.5 s (`ref_shift`).
  - **Needs a verdict.** Every pick, except a `picks` song whose pick has the same timing as
    its on-disk record (Ken already sings on it).
  - **Listen files** (lyric text, local only). For every pick that needs a verdict, write the
    transcribe fit's corrected subtitle text (`fit.srt`, already in clip time) to
    `<listen-dir>/<song stem>.<lrclib_id>.srt`. `--listen-dir` defaults to `<out>/listen`.
  - **Sheets** (lyric text, local only). For every pick, and for every flagged passing record
    that was not picked (one per timing, named by its lowest id):
    `<out>/sheets/<youtube_id>/<lrclib_id>.txt`. One time-ordered list with a kind column:
    `L` an LRC line at its fitted start (with `M`/`U` from the transcribe fit and `m`/`u`
    from the reference fit), `C` a caption cue at its start (`caption` songs), `X` an
    unclaimed run of 5 or more heard words at its first word's start (with its word count
    and words). Once per song, `words.txt`: the heard words (start, word).
  - **`<out>/candidates.tsv`**, one row per record, no lyric text: group, new, youtube_id,
    title (40 chars), lrclib_id, in_pool, on_disk, picked, track and album name lengths,
    timing (the lowest id sharing it), timing size, record duration, length gap, and from the
    transcribe fit status, reason, speed, shift_s, spread_s, matched, total, dropped, mistimed
    (count and indexes), unheard (indexes), unclaimed_run, refusal; for passing records on
    `ref_ok` songs the reference fit's status, shift_s, matched, total, mistimed, unheard,
    unclaimed_run and the flag names.
  - **`<out>/songs.tsv`**, one row per song, skipped ones too.
  - **Printed** (stdout, no lyric text):
    - Table P: per group and for `new` songs apart: songs, `no_length`, `lrclib_unavailable`,
      no synced record, with a pick; then the `out_of_scope` reasons.
    - Table S: one row per in-scope song: group, new, youtube_id, title, records, timings,
      passing records, records per refusal (`no_fit/speed/mistimed/unclaimed`), pick id, its
      mistimed count, unclaimed run and timing size, `ref_ok`, reference flags (`none`, the
      names, or `no reference`), on-disk id, on-disk refusal, whether the pick has the
      on-disk timing, needs a verdict.
    - Table K: the GATE M LRC-wrong records below. Each record comes from the pool, else
      from `--old-cache/<youtube_id>.json`, else the row says `not found`. Columns: in pool,
      status, speed, mistimed, unclaimed run, refusal, picked.

      | youtube_id | lrclib ids |
      |---|---|
      | `GZXHBgjQjNM` | 20242140, 21912586, 27023721, 31535578, 32140003, 35793714, 36228137 |
      | `AJWtLf4-WWs` | 6800151, 28307055, 34352818 |
      | `UAWcs5H-qgQ` | 12572148 |
      | `T6wbugWrfLU` | 35468507, 3458703, 6335685, 7720552, 9641374, 12149023, 12377831, 12515974, 15413449, 17099666, 20411476, 23305471, 24586049, 24809544, 31956521, 32182355, 32691192, 33133897, 34902348 |

    - Table X: flagged passing records that were not picked, one row per timing: song, ids,
      flag names, mistimed, unclaimed run.
    - Table V (sensitivity, never read for the verdict): songs with a pick per group, and
      `new` apart, at mistimed limit 0 and 1 by unclaimed limit 8, 10, 12, 15, 20.
    - Table L, the listen list: the picks that need a verdict, ranked: no reference first
      (not a `caption` song, or not `ref_ok`); then flagged; then by unclaimed run, longest
      first; then mistimed count; then youtube_id. Columns: rank, group, new, title,
      youtube_id, lrclib_id, why, listen file name.
  - Tests, `tests/unit/test_lrc_fit_pick_probe.py`, pure parts with made-up values: the group
    rule (each row of the table); the reference flag (each name, and none); needs-a-verdict
    (a `picks` song with and without its on-disk timing); the listen ranking; Table K's source
    order (pool, old cache, not found); the sensitivity count. No network, no library.
  Commit: `feat(scripts): LRCLIB fit-pick probe for GATE P`.

- [x] **1e. Check the measure against the exploration.** Run the probe on the four GATE M
  songs only, to a scratch folder:
  `python scripts/lrc_fit_pick_probe.py --folder "<library>" --out <scratch> --old-cache
  ~/.pikaraoke/tmp/lrclib_auto_timing/cache --only GZXHBgjQjNM --only AJWtLf4-WWs --only
  UAWcs5H-qgQ --only T6wbugWrfLU`. Table K's unclaimed run must read: 12572148 -> 89;
  35468507 -> 20; 33133897 -> 20; 6800151, 28307055, 34352818 -> 14; 20242140 -> 6. Any other
  value means the measure is not the one explored: STOP and report the values, do not adjust
  anything to match. A record `not found` is not a mismatch; say so.

- [x] **1f. Self-review and record.** Self-review per CLAUDE.md; 1b and 1c are new logic in
  the fit path, so track them as pending review. Results log row with the three commits and
  the 1e values. Plan-only commit. Stop (checkpoint: `/compact`, review due).

## Phase 2: the library run (Sonnet)

- [x] **2a. Run.**
  `python scripts/lrc_fit_pick_probe.py --folder
  "/home/ken/shared-drives/D:/Shared/pikaraoke-songs" --baseline
  ~/.pikaraoke/tmp/lrclib_fit_pick/baseline_ids.txt --old-cache
  ~/.pikaraoke/tmp/lrclib_auto_timing/cache --listen-dir
  "/home/ken/shared-drives/D:/Shared/lrclib-listen" > <out>/report.md`.
  First check the baseline's sha256 against Phase 0. If more than 5 songs come back
  `lrclib_unavailable`, run once more (the cache keeps the rest); if still more than 5, STOP.
  Then the read-only check: `find "<library>" -newer <out>/started` prints nothing that this
  run could have written (Ken may be adding holdout songs meanwhile: new song folders and
  files are his; anything else, STOP and say what changed).
- [x] **2b. Record.** Results log row: command, checks, paths. Paste Tables P, S, K, X, V and
  L raw into "Report output: library run". No tallies beyond the script's, no reading of the
  numbers. Plan-only commit.
- [ ] **2c. Stop.** Give Ken, in plain words: where the listen files are and how to use them
  (below), and Table L's first 10 rows as listening session 2. Then the handoff prompt for
  Fable (see "Executor rules"). Do not start Phase 3.

**How Ken judges a pick.** Open the song's video in VLC, add the pick's `.srt` from
`D:\Shared\lrclib-listen` as the subtitle file, and watch: do the lines come up when they are
sung, and is any sung line missing? This shows the LRC's lines at their fitted times, which
is what the route would hand to cue align. It does not show the finished word-by-word
karaoke; that is Phase 6. One verdict per song: right, wrong (where), or unsure.

## Phase 3: the holdout run (Sonnet, after Phase 0)

- [x] **3a. Preconditions.** A dry look at the library (`library_statuses` against the
  baseline and Phase 0's list): at least 25 of the thirty listed songs are there and in a
  group (they have heard words). Fewer: STOP and tell Ken which are missing. Record how many
  took a Genius pick (`joint`, or `picks` if Ken has since retimed one on Repair) and how
  many timed from a caption after all. Other new songs Ken added meanwhile are measured too
  and marked `new` like these. A new id that is a file stem matching a renamed baseline song:
  STOP and name it.
- [x] **3b. Run** the 2a command with `--out ~/.pikaraoke/tmp/lrclib_fit_pick_holdout`
  (a fresh cache: LRCLIB as it is that day). Same unavailable and read-only rules.
- [x] **3c. Record.** As 2b, into "Report output: holdout run", with every table. Plan-only
  commit.
- [ ] **3d. Stop.** Give Ken listening session 3: the `new` rows of Table L, first 10. If
  more than 10 new picks have no reference, say how many sessions that makes. Handoff prompt
  for Fable.

## GATE P (Fable, then Ken)

Read-only. Inputs: both report sections, the files under both `<out>` folders, Ken's verdicts.
Read once both runs and Ken's sessions are in; a pre-read after Phase 2 may only produce
questions and extra listening requests, never a verdict.

**A wrong pick**, as at GATE M: the LRC times words the video does not sing there, or leaves
out a stretch the video sings. Ken's ear on 2026-11-10 sets the tolerance: a one-word line
slightly early or long, line ends drawn out, missing video dialog and missing backing vocals
are not wrong. A sung lead line shown several seconds off, or sung lead lines never shown, is
wrong. One missing lead line, or one line 3 to 5 s off, is `minor`: listed apart, and Ken
rules whether minor counts.

1. **Table K, both runs.** No GATE M LRC-wrong record is its song's pick. One picked: the
   gate fails.
2. **A verdict for every pick that needs one**, both runs.
   - Ken's verdict where he gave one. It overrides a sheet read.
   - On a `ref_ok` caption song the judge may rule from the sheet: every flagged pick is
     read; of the unflagged ones, in youtube_id order every third until 10 are read (GATE M
     found omissions the screens missed).
   - A pick with no reference has no verdict until Ken has judged it. The gate is not read
     while any `new` pick or any no-reference pick lacks one.
3. **Zero wrong picks** over both runs passes the bar. Any wrong pick: STOP for Ken
   (Decision 8). A tighter bar is a new plan with a fresh holdout; Table V is there to size
   one, not to rescue this one.
4. **Coverage**, reported, not judged against a floor: songs with a pick among Ken's 28
   Repair picks (23 expected), the `joint` songs, the `new` Genius-pick songs (`joint` or
   `picks`), and the `caption` songs as a stand-in. Name the songs where the on-disk record passes but nothing
   in the pool does (coverage the search loses).
5. **Exposure.** From Table X, the songs where a record ruled wrong passes the bar and only
   the pick order kept it out. This is the residual risk of Decision 12; count it for Ken.
6. **Report to Ken**, plainly: wrong picks (none, or which), minor ones, coverage, exposure,
   and the caveats: `caption` songs are the easy case; the limits were fitted to the library
   songs, so only the `new` songs are a clean test, and they are few; the listen check shows
   line times, not
   the finished karaoke. Ken rules go or stop. Record the read and the ruling in this file.

## Phases 4-6 (loose; spec after GATE P)

### Phase 4: the pipeline switch

In `LyricAlignStage.run`, before the route choice (`if cue_spans:`), on a song that would go
joint: when the run is a first-time download and the origin is Genius, take the transcribe
words, search LRCLIB, `lrc_auto_pick.pick`.

- A pick: write the `.lrc`, save its fitted sheet as the new sheet kind, set the origin, run
  cue align on it.
- No pick: joint and the LRCLIB fill, as today.
- The bundle records the check and its outcome either way. The Genius pick stays stored, so
  Repair can return the song to Genius without a search.

### Phase 5: source type, labels, lists

A new entry in `library_regen.SHEETS`, its own origin and label (e.g. "LRCLIB timing
(auto)"), a Tools-tab list, Song Info and History wording, the run page's "Now:" text.
Translation catalogs in their own commits.

### Phase 6: Ken's checks

Download new songs, at least one expected to pass and one to fail. Check the list, Song Info,
and the karaoke by ear. Return one to Genius on Repair.

### Open for the Phase 4-6 spec

- How the pipeline knows a run is a first-time download (Decision 3).
- Running the de-reverb gate once: `_run_joint` and `_run_cue_align` each run it inside, and
  the switch needs its words before choosing the route.
- The search and up to 20 fits now run in the align stage; today's `ensure_lrc` runs in
  `lyrics_fetch`. Which of the two writes the `.lrc`, and what a search failure does.
- Whether Repair's LRCLIB candidate list takes the same order (Ken's complaint that today's
  pick lands on compilation records).
- Reset and Edit words on an auto sheet (the archived plan's defaults: the sheet survives
  Reset; an edit makes it an edited kind).
- `defer_timing` assumes the fit and pick stay manual; revisit that line when this lands.

## Executor rules

- Stop at every STOP and at 1f, 2c and 3d. If a step contradicts the code, stop and say so.
- No library writes, no GPU, no lyric text in any commit or in this plan. The listen folder
  and both `<out>` folders hold lyric text and stay off the repo.
- No verdicts: tables go in raw. Do not say whether the bar held.
- Feature branch `lrclib_fit_pick` (off `dev` `37d8d93`). Plan edits in their own commits.
- At 2c and 3d the Fable handoff prompt carries: branch and HEAD, this file's report sections
  and "GATE P", both `<out>` paths, "do not rerun the probe", and that Ken's verdicts arrive
  in chat.

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
| 1 | 2026-11-10 | 0 | Branch `lrclib_fit_pick` off `dev` `37d8d93`. Baseline id list written, read-only on the library (`library_statuses`): 168 songs. Origins: `srt` 112, `lrclib_srt` 28, `movie_srt` 7, `genius`/joint 4, `custom`/joint 3, no bundle 14. | `~/.pikaraoke/tmp/lrclib_fit_pick/baseline_ids.txt`, sha256 `610e84eeee4209473ba33b50d583ea4739d3086c85bf940cde950e5645315eb7`. |
| 2 | 2026-11-10 | 0 | Ken declined a 30-song import and asked for a shorter list picked for him (Decision 17). Twelve songs listed in Phase 0, found with `yt-dlp` searches from the VM (`ytsearch3:` per song, uploader captions read from each result). Control: the search reported the uploader caption on a library caption song (`4fndeDfaWCg`). None of the twelve is in the baseline. LRCLIB not consulted. | List and selection rule in Phase 0. |
| 3 | 2026-11-10 | 0 | Ken asked how many songs are needed and for a command for the rest. Eighteen more listed the same way (same searches, same rule, LRCLIB not consulted), which makes the thirty first planned, now all of the Genius-pick kind. None is in the baseline. | Phase 0 lists thirty; 3a needs 25 of them. |
| 4 | 2026-11-10 | 1 | Phase 1 on `lrclib_fit_pick`, VM, read-only on the library. **1a:** every anchor the step names exists as the plan uses it. **Commits:** 1b `ddefad8` (`SliceFit.unclaimed_run`); 1c `71c916f` (`lrc_auto_pick`: bar, `evaluate`, `pick`); `810665f`, not in the plan (`SliceFit.unclaimed_runs`: every run as first heard word and length; the sheets' `X` rows need the place and the longest length cannot give it; `unclaimed_run` is now the longest of the list); 1d `f96db34` (probe, `srt_slice_fit.sheet_stream` and `CAPTION`, tests). **Tests:** full suite 3648 passed on the final tree; pre-commit passes on every changed file. **1e:** probe on the four GATE M songs to a fresh scratch folder with a live LRCLIB search, all 30 listed records found in the pool (none from `--old-cache`, none `not found`). Table K unclaimed run as read: 12572148 -> 89; 35468507 -> 20; 33133897 -> 20; 6800151, 28307055, 34352818 -> 14; 20242140 -> 6. A first run, before the 1d commit, printed the same Table K. `find <library> -newer started` listed `vocal/`, `nonvocal/` and `vocal/Bruno Mars - Just The Way You Are (Official Music Video)---LjhCEhWiKXk---vocal.m4a`: Ken's holdout import (`LjhCEhWiKXk` is Phase 0's first song), nothing the probe writes. **Where the plan was silent:** `--folder` is required; `classify` gives a song no listed rule names the reason `other`; a `new` song counts in its group's row of Tables P and V and again in the `new` row; Table K has Source and Note columns; Table V counts songs with at least one passing record at the limits; reference flags are read only when the reference fit fits (`ref_refused` alone otherwise). A test caught a Table K crash (a record in neither the pool nor the old cache) that the 1e run could not, since every record was in the pool. Plan commit `a17e6e3` (thirty-song holdout, another session) landed between 1b and 1c and touches Phase 0 and 3a only. No `graphify-out` on this VM, so no `graphify update`. **Self-review** (correctness, simplicity, robustness) done on the four code commits. **Review pending:** `ddefad8`, `71c916f`, `810665f`, and the probe's reference flags and sheet logic in `f96db34`. | Scratch outputs `/tmp/claude-1000/-home-ken-pikaraoke/95747b31-9b15-4134-9c73-c44d4fc6bb5b/scratchpad/probe1e_final` (`.report.md` beside it): TSVs, sheets, listen files; lyric text, not committed. Command: 1e as written. |
| 5 | 2026-11-10 | 2 | Phase 2 on `lrclib_fit_pick` (HEAD `be542b1`), VM, read-only on the library. **2a:** the baseline file's sha256 checked first: `610e84ee…5eb7`, 168 lines, equal to row 1. Command as written, `<out>` the default `~/.pikaraoke/tmp/lrclib_fit_pick`, live LRCLIB search, stdout to `<out>/report.md`, progress log to the scratchpad. One song came back `lrclib_unavailable` (limit 5), so no rerun. 180 songs read. **Read-only check:** `find <library> -newer <out>/started` (run started 11:08:51) printed the directories `lyrics/`, `nonvocal/`, `vocal/` and three files of `ZrX1XKtShSI` (`.lrc`, `---nonvocal.m4a`, `---vocal.m4a`, written 11:13:22-33): Ken's holdout import, Phase 0's `ZrX1XKtShSI`. Its video was already in the library at 11:08:07 and the probe read the song as `out_of_scope` `no_bundle` (its row is in `songs.tsv`); Phase 3 will measure it with its bundle. Nothing else changed. **Files:** the listen folder holds 76 `.srt`, one per Table L row; `<out>/sheets` holds a folder per song with a pick. **How the tables count:** Table V's Songs column counts the songs the probe fitted (not skipped), so its caption row is one less than Table P's (the `lrclib_unavailable` song); the `youtube_id` column holds the file stem for a song whose filename has no id, as `song_id` does and as the baseline lists it. **2b:** Tables P, S, K, X, V and L pasted raw below, headings one level down; no tallies, no reading of the numbers. Plan-only commit. **Review pending:** unchanged from row 4. | Outputs `~/.pikaraoke/tmp/lrclib_fit_pick/` (`report.md`, `songs.tsv`, `candidates.tsv`, `sheets/`, `cache/`, `started`); listen files `D:\Shared\lrclib-listen` (`/home/ken/shared-drives/D:/Shared/lrclib-listen` on the VM). Lyric text; not committed. |
| 6 | 2026-11-10 | 3 | Phase 3 on `lrclib_fit_pick` (HEAD `971415f`), VM, read-only on the library. **3a:** the baseline file's sha256 checked first: `610e84ee…5eb7`, 168 lines, equal to row 1. A dry look (`library_statuses` against the baseline and Phase 0's list, a scratch script outside the repo): 198 songs in the library, 168 baseline plus 30 new, and the 30 new are exactly the thirty listed; none was in the baseline. 29 of the 30 are in a group, all `joint` (Genius pick): none `picks`, none `caption`. The 30th, `YRpvIiz9G8A` (Encanto - We Don't Talk About Bruno), has no bundle: Ken's regen log says Genius returned empty lyrics for id 11315631 and the pipeline fell back; Ken regenerated it twice (the first rewrote its `.ass` and `.srt` at 13:52, still no bundle) and ruled to leave it out. It is `out_of_scope` `no_bundle` in this run. No other new ids, and no baseline id missing from the library, so no renamed baseline song looks new. **3b:** command as 2a with `--out ~/.pikaraoke/tmp/lrclib_fit_pick_holdout` (a fresh cache, live LRCLIB search), stdout to `<out>/report.md`, progress log to the scratchpad; started 13:53:54, finished 14:00:32; 198 songs read, none `lrclib_unavailable`, so no rerun. **Read-only check:** `find <library> -newer <out>/started` printed only directories: `regen_backups/` and `regen_backups/20261110T185829Z` with its `karaoke/` and `subtitles/`, created 13:58:29, during the run. The backup holds the `.ass`, `.srt` and `.srt.generated` of `YRpvIiz9G8A` and nothing else, so it is Ken's second regen of that song; `find -type f -newer started` printed nothing, and no `alignment_debug` file changed. **How the tables count:** Table P's `new` row counts every song not in the baseline, `YRpvIiz9G8A` included, so it reads 30 songs while Table V's `new` rows read 29 (the songs the probe fitted). **Against run 5, same code, a fresh cache:** 18 songs were not in the library for run 5; 10 songs that run 5 read as `out_of_scope` `no_bundle` (Ken was still importing) are now `joint`; `MEb2CecR11I` (Backstreet Boys - Larger Than Life), `lrclib_unavailable` in run 5, now has 20 records, 6 timings, no pick, so Table V's caption row reads 112 songs, not 111; two caption songs differ in the pool: `GlZxZ2n2zpw` (Colbie Caillat - Realize) picks 37946467 where run 5 picked 586041 (the pool has 9 timings, not 12), `axySrE0Kg6k` (Beauty and the Beast) keeps its pick with a timing size of 5, not 6. No other song's records, passing count or pick changed. **Listen folder:** Table L has 96 rows, 21 of them `new`; the folder holds 97 files: run 5's 76, 20 files for new songs (`LjhCEhWiKXk`'s was rewritten, same name) and Colbie Caillat - Realize's new pick; its run 5 file `Colbie Caillat - Realize---GlZxZ2n2zpw.586041.srt` is no longer in Table L and is still on disk. **3c:** Tables P, S, K, X, V and L pasted raw below, headings one level down; no tallies, no reading of the numbers. Plan-only commit. **Review pending:** unchanged from row 4. | Outputs `~/.pikaraoke/tmp/lrclib_fit_pick_holdout/` (`report.md`, `songs.tsv`, `candidates.tsv`, `sheets/`, `cache/`, `started`); listen files `D:\Shared\lrclib-listen`. Lyric text; not committed. |
| 7 | 2026-11-10 | 3 | Ken's listening session 3, the first ten `new` rows of Table L (ranks 2, 3, 8-15), reported in chat after 3d. Recorded as he said it; no ruling here. **His words:** "those songs are good except" two. Good, by his word: The Lazy Song (rank 3), Wouldn't Change a Thing (8), Just The Way You Are (9), Locked Out Of Heaven (10), I Just Had Sex (12), Everywhere (13), Price Tag (14), YOLO (15). **Where You Are** (rank 2, `RTWhvp_OD6s`, pick 28421947): "uniformly late from 2:39 onwards, like there's an extra gap in the subs just before that". **When I Was Your Man** (rank 11, `ekzHIouo8Q4`, pick 26614056): "late from 0:40 onwards, resyncs around 1:00", and one line he named from that stretch (text not recorded here) "shows a few secs"; he did not say early or late. **Raw values for the two picks** (`candidates.tsv` and Table S): Where You Are: status fits, speed 1.0, shift 0.39 s, spread 0.308 s, matched 59 of 64, mistimed 0, unheard lines 11, 28, 48, 49, 50, unclaimed run 10, timing size 7 (the song has 20 records, 6 timings, 20 passing), clip 209.6 s against record 210.0 s. When I Was Your Man: status fits, speed 1.0, shift 23.43 s, spread 0.349 s, matched 46 of 46, mistimed 0, no unheard line, unclaimed run 7, timing size 2 (19 records, 16 timings, 19 passing), clip 234.1 s against record 237.4 s. **Not ruled:** whether either counts as wrong, `minor` or neither is GATE P's read, with Ken (Decision 8 stops the feature on a wrong pick). The other eleven `new` picks are not yet heard. | Verdicts in this row only (chat is not kept). |
| 8 | 2026-11-10 | 3 | Ken's listening session 4, the other eleven `new` rows of Table L (ranks 17, 18, 22, 23, 24, 27, 29, 30, 31, 33, 36), reported in chat. Recorded as he said it; no ruling here. **His words:** two have a problem, "otherwise the others are good". Good, by his word: Jack Sparrow (17), Be OK (18), Show Me The Meaning Of Being Lonely (22), Gravity (23), I've Got a Dream (24), Flashlight (27), I Want You Back (29), Flying Without Wings (30), For the First Time in Forever (33). **Grenade** (rank 31, `SR6iYWJxHqs`, pick 38953751): "opening line comes in early and leaves early". **Into the Unknown** (rank 36, `mzhv_dg_UBA`, pick 36372778): "the opening few lines of siren chant chant don't line up but the rest of the lyrics do". **Raw values for the two picks** (`candidates.tsv` and `songs.tsv`): Grenade: status fits, speed 1.0, shift 0.02 s, spread 0.330 s, matched 49 of 49, mistimed 0, no unheard line, unclaimed run 2, timing size 2 (19 records, 11 timings, 9 passing), clip 220.7 s against record 221.0 s. Into the Unknown: status fits, speed 1.0, shift 15.69 s, spread 0.176 s, matched 40 of 50, mistimed 0, unheard lines 0, 1, 2, 37, 40, 41, 42, 43, 44, 45, unclaimed run 2, timing size 10 (20 records, 7 timings, 16 passing), clip 213.7 s against record 194.0 s (gap -20). **Still open from row 7:** whether the line Ken named in When I Was Your Man is early or late. **Not ruled:** whether either counts as wrong, `minor` or neither is GATE P's read, with Ken. **Verdicts still missing for GATE P (rule 2):** the 16 not-new picks with no reference in this run's Table L (14 `picks`, 2 `caption`), of which session 2 was to cover the first nine (its verdicts are not in this file); and Colbie Caillat - Realize's new pick 37946467. | Verdicts in this row only (chat is not kept). |
| 9 | 2026-11-10 | 3 | Ken's listening session 5, the seven not-new no-reference rows of this run's Table L that were not in the first ten rows of run 5's Table L (ranks 25, 26, 28, 32, 34, 35, 37), reported in chat. Recorded as he said it; no ruling here. **His words:** "those 7 songs are also good". The seven: She Used To Be Mine (`53GIADHxVzM`, pick 12564402), My Heart Will Go On (`9bFHsd3o1w0`, 22553995), I'm Alive (`NJsa6-y4sDs`, 28130840), Domino (`UJtB55MaoD0`, 28220836), Threw It On The Ground (`gAYL5H46QnQ`, 35338143), When Will My Life Begin (`kRXmAIHYQR4`, 24795512), The Way I Am (`Vh74KE3o4Bs`, 1781541). Five are `picks` songs whose pick has a different timing from the on-disk record Ken retimed on Repair; two are `caption` songs with no usable reference. **Open: session 2.** No verdict is recorded for the nine not-new rows of run 5's Table L ranks 1-10: Frozen In Summer (`9tcaM06eGrY`, 3630452), Camp Rock This Is Me (`6HCUoMgviwU`, 17015895), KPop Demon Hunters Your Idol (`fGyTN5UjnL4`, 23310716), Takedown (`j5itLHDMJsE`, 30356707), Golden (`yebNIHKAC4A`, 23163059), The Lonely Island Jose & Mark (`68LBPvFhMx0`, 2554162), Frozen Do You Want to Build a Snowman (`TeQ_TTyLGMs`, 3514723), Jung Kook Seven (`1QYBiNRu1ok`, 31432999), Pocahontas Colors of the Wind (`9ThO76peOw0`, 34484694); the same pick ids stand in this run's Table L. The plan, its git history and the memory notes hold none, and the Phase 3 session began from a handoff that said nothing was judged. Row 8's "session 2 was to cover the first nine" assumed it had been heard; no record shows that. **Still open from row 7:** early or late for the line Ken named in When I Was Your Man. **Still open:** Colbie Caillat - Realize's new pick 37946467 (the judge may rule from the sheet). | Verdicts in this row only (chat is not kept). |
| 10 | 2026-11-10 | 3 | Ken's listening session 6, reported in chat. Recorded as he said it; no ruling here. **His words:** "all those are good as well, including colbie", answering the list of session 2's nine (row 9) and Colbie Caillat - Realize's new pick 37946467. The nine: Frozen In Summer (`9tcaM06eGrY`, 3630452), Camp Rock This Is Me (`6HCUoMgviwU`, 17015895), KPop Demon Hunters Your Idol (`fGyTN5UjnL4`, 23310716), Takedown (`j5itLHDMJsE`, 30356707), Golden (`yebNIHKAC4A`, 23163059), The Lonely Island Jose & Mark (`68LBPvFhMx0`, 2554162), Frozen Do You Want to Build a Snowman (`TeQ_TTyLGMs`, 3514723), Jung Kook Seven (`1QYBiNRu1ok`, 31432999), Pocahontas Colors of the Wind (`9ThO76peOw0`, 34484694). He did not say which of the two Colbie files in the listen folder he used (`...586041.srt` is run 5's pick, `...37946467.srt` this run's); the question put to him named 37946467. **Row 7's open item:** "that line from when i was your man was early" (the line he named in the 0:40 to 1:00 stretch, text not recorded here). **State:** no verdict is outstanding for any `new` pick or any no-reference pick. The picks without a verdict from Ken are the `caption` songs with a reference (7 flagged and 52 unflagged, not-new, in this run's Table L; Colbie, whom Ken has heard, is one of the 52), which GATE P rule 2 lets the judge read from the sheet. | Verdicts in this row only (chat is not kept). |
| 11 | 2026-11-10 | GATE P | GATE P read by Fable on `lrclib_fit_pick` (HEAD `bc222f9`), read-only: both report sections, both `<out>` folders, Ken's verdicts (rows 7-10). Neither probe was rerun. The library share was not mounted during the read, so captions were read from the sheets' `C` rows. Scratch scripts outside the repo. | Rule 1 met. Rule 2 complete. **Rule 3 not met: seven wrong picks**, two `new` by Ken's ear, five `caption` by the sheets. Two `minor`. Detail in "GATE P read". Ken's ruling pending. |

## GATE P read (Fable, 2026-11-10)

Read-only, on HEAD `bc222f9`. Inputs: both report sections, `songs.tsv`, `candidates.tsv`,
`cache/` and `sheets/` under `~/.pikaraoke/tmp/lrclib_fit_pick_holdout` (the holdout run covers
every library song, so it is the run read; the library run was read for Table K), and Ken's
verdicts in Results rows 7-10. Neither probe was rerun.

**How lines were compared.** For a record, each line's *offset* is the start of the first
heard word the fit's second pass gives that line, minus the line's fitted start (the same
match, speed and shift the bar uses). Negative means the line is shown late. On `caption`
songs the same offset was also taken against the caption: the sheet's `C` rows as a word
stream (a cue's words spread from its start to the next cue's start, 4 s at most), fitted
with its own shift. The library share was not mounted during the read, so the caption files
themselves were not opened. A single line's offset by heard words is noisy (repeated words);
a run of lines off the same way, seen by both streams or by Ken's ear, is what the rulings
below rest on. Scratch scripts, not in the repo.

### Rule 1: Table K

Met in both runs. No GATE M LRC-wrong record is its song's pick. The seven Drowning records
pass the bar and are not picked; every other listed record is refused as `unclaimed`.

### Rule 2: verdicts

Complete. Ken judged all 21 `new` picks, all 16 not-new no-reference picks and Colbie Caillat -
Realize. The 59 `caption` picks with a reference were ruled from the sheets: all 7 flagged
sheets read; all 52 unflagged compared line by line as above, and the sheet read wherever the
comparison showed a run. This replaces the every-third sample (which would have read Perfect,
I Want It That Way, Cry, Realize, So Sick, Shape Of My Heart, I Should Tell You, One Song
Glory, What You Own, Part of Your World). The two unflagged wrong picks below are 31st and
33rd in id order and outside that sample.

### Rule 3: wrong picks

**Not met. Seven wrong picks.** Offsets in seconds; "caption" and "heard" name the stream.

| Song | youtube_id | Pick | Group | Judged by | What is wrong |
|---|---|---|---|---|---|
| Moana - Where You Are (Sing-Along) | `RTWhvp_OD6s` | 28421947 | joint, new | Ken (row 7) | The last 17 of 64 lines (fitted 161-201 s): the 14 the transcriber heard are 2.0 to 2.7 late; the lines before are within 0.5 but for two (0.8 and 1.1). All six timings of the song carry the same step. |
| Bruno Mars - When I Was Your Man | `ekzHIouo8Q4` | 26614056 | joint, new | Ken (rows 7, 10) | Four lines in a row (fitted 44-50 s) are 4.1, 2.3, 2.5 and 1.4 late by heard words. 13 of the song's 16 timings show no line 1.5 off; all 19 records pass with no mistimed line and the same unclaimed run, so the order fell to timing size and name length. |
| The Last Five Years - A Summer in Ohio | file stem | 23648746 | caption, unflagged | sheet | Twelve lines in a row (fitted 15-76 s) are 2.9 to 4.6 late by the caption and 2.7 to 4.9 late by heard words; from 82 s on no run. |
| The Last Five Years - Nobody Needs to Know | file stem | 4626353 | caption, unflagged | sheet | The last eight lines (fitted 333-391 s) are 2.4 to 3.1 early by the caption; six of them 2.1 to 3.3 early by heard words. |
| Britney Spears - (You Drive Me) Crazy | `Q4VK9_CfOLQ` | 2137556 | caption, `ref_mistimed` | sheet | After a spoken break in the video (about 124 s), thirteen lines (fitted 134-190 s) are 1.8 to 4.7 early by the caption. The transcriber heard none of them (16 unheard lines in the fit). |
| Flight of the Conchords - Bowie | file stem | 19452078 | caption, `ref_refused` | sheet | Seven lines (fitted 21-43 s) are 3.9 to 6.4 late by the caption; three of them 3.8 to 6.6 late by heard words. |
| Christina Aguilera - Reflection | `RNprQYHenNI` | 685756 | caption, `ref_mistimed` | sheet | The last two lines (fitted 191 and 196 s) are 4.7 and 6.1 early by the caption. Both unheard by the transcriber. The smallest of the seven. |

**`minor`, listed apart (Ken rules whether minor counts):**

| Song | youtube_id | Pick | Judged by | What |
|---|---|---|---|---|
| Bruno Mars - Grenade | `SR6iYWJxHqs` | 38953751 | Ken (row 8) | The opening line is 4.0 early by heard words, the second 1.4 early. Two of the song's passing timings carry it; the others do not. One line in the 3 to 5 s band. |
| Frozen 2 - Into the Unknown (Sing-Along) | `mzhv_dg_UBA` | 36372778 | Ken (row 8) | The three opening lines are a wordless call the transcriber heard nothing of; by Ken's ear they do not line up, the rest does. Not lead words, so not wrong by the tolerance; three lines, so not clean either. |

**Read and ruled right:** Drowning (`ref_shift`), Happier, Get Down and (God Must Have Spent) A
Little More Time On You (`ref_unclaimed`): the flags are ad libs and backing chants. The Next
Ten Minutes: only the last repeated two-word lines differ. Colbie Caillat - Realize: Ken's
verdict stands; which of the two listen files he heard is not recorded, and the comparison of
37946467 shows four separate lines 1.7 to 2.3 early, no run.

**Not ruled, needs Ken's ear if the feature goes on:** Backstreet Boys - Quit Playing Games
(`Ug88HO2mg44`, 33413907): around 117-125 s three to five chorus lines are about 2 late by
both streams, among repeats that the caption and the record split differently; 21 unheard
lines.

### Why the bar let them through

Six of the seven share one cause: the video's cut differs from the record by 2 to 6 s for a
stretch (a shorter gap, a spoken break, film dialog), and the bar calls a line mistimed only
past 5 s (`FLAG_TOLERANCE_S`). A whole section 2 to 4.6 s off raises no flag, claims every
heard word, and passes. On Where You Are every record has the step, so no pick order helps.
When I Was Your Man is the other cause: a poorly synced record among good ones, all equal
under the bar, chosen by timing size and name length. On Crazy and Reflection the shifted
lines were not heard at all, which is what GATE M's unheard-end condition (dropped here) was
for.

### Rule 4: coverage (reported, not judged)

| Set | Songs | With a pick |
|---|---|---|
| Ken's Repair picks (`picks`) | 28 | 23 |
| `joint`, not new | 4 | 0 |
| `new` Genius-pick songs | 29 fitted (30 listed, `YRpvIiz9G8A` has no bundle) | 21 |
| `caption` | 112 | 61 |

The five `picks` songs with no pick: I Just Might, Thinking Of You, Miss Independent, Leave
the Door Open (`unclaimed`), Best Part Of Me (`speed`); as expected. No song has an on-disk
record that passes while nothing in the pool does. Of the 21 `new` picks Ken heard 17 as
good, 2 are wrong and 2 `minor`.

### Rule 5: exposure

One song in Table X has a ruled-wrong record that passes the bar and is kept out only by the
pick order: Drowning, one timing of seven records (the GATE M ones), behind a clean timing.
The other Table X rows are not ruled. When I Was Your Man shows the order does not protect
when every record is clean under the bar.

### Sizing only (rule 3: not a rescue of this bar)

A screen read after the verdicts, on the same songs: three or more lines in a row each 1.5 s
or more off the same way by heard words. Of the 105 picks it marks seven: five of the seven
wrong picks (not Crazy and not Reflection, whose shifted lines went unheard), Quit Playing
Games, and KPop Demon Hunters - Takedown, which Ken heard as good. Any such bar is a new plan
with a fresh holdout.

### Caveats

- `caption` songs are the easy case, and five of their 59 referenced picks are wrong.
- The limits were fitted to the library songs; only the 29 `new` songs are a clean test.
- The five `caption` rulings are from sheets, not from Ken's ear. The listen files are in the
  listen folder if he wants to hear them.
- The listen check and the sheets show line times, not the finished karaoke. Cue align pads a
  section by 0.75 s, so a section 2 s or more off is not expected to recover; not measured
  (GPU).
- The Phase 1 code review is still pending (row 4).

### Ruling

Ken's, pending: stop under Decision 8, or a new plan with a tighter bar and a fresh holdout.

## Report output: library run

Verbatim from `~/.pikaraoke/tmp/lrclib_fit_pick/report.md` (2a); the table headings are one level down.

Bar in force: mistimed <= 1, unclaimed run <= 12, speed 1.0. 180 songs in /home/ken/shared-drives/D:/Shared/pikaraoke-songs; output in /home/ken/.pikaraoke/tmp/lrclib_fit_pick; listen files in /home/ken/shared-drives/D:/Shared/lrclib-listen.

### Table P: groups and skip reasons

| Group | Songs | no_length | lrclib_unavailable | No synced record | With a pick |
|---|---|---|---|---|---|
| picks | 28 | 0 | 0 | 0 | 23 |
| joint | 5 | 0 | 0 | 1 | 1 |
| caption | 112 | 0 | 1 | 1 | 61 |
| new | 12 | 0 | 0 | 0 | 1 |

| out_of_scope reason | Songs |
|---|---|
| custom | 3 |
| movie_srt | 7 |
| no_bundle | 25 |
| no_words | 0 |
| edited | 0 |
| no_caption_file | 0 |
| other | 0 |

### Table S: songs

| Group | New | youtube_id | Title | Skipped | Records | Timings | Passing | no_fit/speed/mistimed/unclaimed | Pick | Mistimed | Unclaimed | Timing_size | ref_ok | Reference_flags | On_disk_id | On_disk_refusal | Pick_has_disk_timing | Needs_verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| joint | 0 | jeRu6h4XbUU | A-Lin - 幸福在歌唱 (Happiness Is Singing) |  | 2 | 1 | 0 | 2/0/0/0 |  |  |  |  |  |  | 38356656 | no_fit |  |  |
| caption | 0 | hLQl3WQQoQ0 | Adele - Someone Like You |  | 20 | 13 | 19 | 0/1/0/0 | 23116607 | 0 | 2 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | eitDnP0_83k | Aladdin (2019) - A Whole New World |  | 16 | 10 | 0 | 5/5/0/6 |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | mw5VIEIvuMI | Aladdin (2019) - Speechless |  | 13 | 12 | 10 | 0/1/1/1 | 19793188 | 0 | 3 | 2 | 1 | none |  |  |  | yes |
| caption | 0 | axySrE0Kg6k | Ariana Grande & John Legend - Beauty and |  | 20 | 10 | 19 | 0/1/0/0 | 31988497 | 0 | 5 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | WMweEpGlu_U | BTS 방탄소년단 - Butter |  | 19 | 12 | 15 | 0/0/0/4 | 32156281 | 0 | 7 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | pj6FCKm8dhM | Backstreet Boys - All I Have To Give |  | 18 | 7 | 0 | 1/0/17/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 0Gl2QnHNpkA | Backstreet Boys - As Long As You Love Me |  | 20 | 11 | 7 | 11/0/2/0 | 3722851 | 0 | 8 | 3 | 1 | none |  |  |  | yes |
| picks | 0 | W5kM5wAwRug | Backstreet Boys - Chances (Official Vide |  | 19 | 11 | 12 | 6/1/0/0 | 2031559 | 1 | 3 | 8 |  | no reference | 33832441 | passes | yes | no |
| caption | 0 | GZXHBgjQjNM | Backstreet Boys - Drowning |  | 20 | 9 | 18 | 1/1/0/0 | 14595571 | 0 | 6 | 3 | 1 | ref_shift |  |  |  | yes |
| caption | 0 | 6M6samPEMpM | Backstreet Boys - Everybody (Backstreet' |  | 20 | 17 | 0 | 0/2/0/18 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 0LSYuZRSGcY | Backstreet Boys - Get Down (You're The O |  | 20 | 11 | 20 | 0/0/0/0 | 1124886 | 0 | 5 | 6 | 1 | ref_unclaimed |  |  |  | yes |
| caption | 0 | 4fndeDfaWCg | Backstreet Boys - I Want It That Way |  | 20 | 15 | 19 | 0/1/0/0 | 11268019 | 0 | 6 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | kDcCSiakaU4 | Backstreet Boys - I'll Never Break Your  |  | 20 | 10 | 0 | 0/0/20/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | WVe80iZtlYU | Backstreet Boys - Incomplete |  | 20 | 10 | 17 | 0/3/0/0 | 19180415 | 1 | 4 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | qGDF_QcsKVI | Backstreet Boys - Inconsolable |  | 14 | 6 | 14 | 0/0/0/0 | 35522789 | 0 | 6 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | MEb2CecR11I | Backstreet Boys - Larger Than Life (Offi | lrclib_unavailable | 0 | 0 | 0 | 0/0/0/0 |  |  |  |  |  |  |  |  |  |  |
| caption | 0 | 1OwfYjemrYw | Backstreet Boys - More Than That |  | 20 | 11 | 20 | 0/0/0/0 | 36314729 | 0 | 4 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | Ug88HO2mg44 | Backstreet Boys - Quit Playing Games (Wi |  | 20 | 11 | 1 | 3/2/0/14 | 33413907 | 0 | 5 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | OT5msu-dap8 | Backstreet Boys - Shape Of My Heart |  | 20 | 12 | 15 | 0/5/0/0 | 22503174 | 0 | 6 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | wMOkm57vu0k | Backstreet Boys - The Call |  | 20 | 11 | 0 | 0/0/20/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Q4VK9_CfOLQ | Britney Spears - (You Drive Me) Crazy |  | 20 | 9 | 1 | 14/5/0/0 | 2137556 | 1 | 7 | 1 | 1 | ref_mistimed |  |  |  | yes |
| caption | 0 | C-u5WLJ9Yk4 | Britney Spears - ...Baby One More Time |  | 20 | 10 | 16 | 4/0/0/0 | 32110280 | 0 | 4 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | CduA0TULnow | Britney Spears - Oops!...I Did It Again |  | 20 | 16 | 0 | 3/1/0/16 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | AJWtLf4-WWs | Britney Spears - Stronger |  | 19 | 9 | 0 | 2/0/0/17 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | luotSpkyCVU | Bruno Mars - I Just Might |  | 20 | 6 | 0 | 0/0/0/20 |  |  |  |  |  |  | 26520597 | unclaimed |  |  |
| joint | 1 | LjhCEhWiKXk | Bruno Mars - Just The Way You Are (Offic |  | 20 | 13 | 10 | 0/7/3/0 | 9888181 | 0 | 7 | 2 |  | no reference | 7470259 | passes | no | yes |
| picks | 0 | 6HCUoMgviwU | Camp Rock (2008) - This Is Me (Sing-Alon |  | 19 | 13 | 1 | 3/0/15/0 | 17015895 | 0 | 9 | 1 |  | no reference | 28926432 | passes | no | yes |
| caption | 0 | RNprQYHenNI | Christina Aguilera - Reflection (Mulan,  |  | 20 | 7 | 20 | 0/0/0/0 | 685756 | 0 | 3 | 12 | 1 | ref_mistimed |  |  |  | yes |
| caption | 0 | GlZxZ2n2zpw | Colbie Caillat - Realize |  | 19 | 12 | 15 | 1/1/2/0 | 586041 | 0 | 12 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | CX11yw6YL1w | Céline Dion - Ashes (Deadpool 2, 2018) |  | 20 | 9 | 0 | 0/3/0/17 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | NJsa6-y4sDs | Céline Dion - I'm Alive (Stuart Little 2 |  | 20 | 9 | 19 | 0/1/0/0 | 28130840 | 0 | 3 | 6 | 0 | no reference |  |  |  | yes |
| caption | 0 | 9bFHsd3o1w0 | Céline Dion - My Heart Will Go On (Titan |  | 19 | 11 | 12 | 2/4/1/0 | 22553995 | 0 | 3 | 9 | 0 | no reference |  |  |  | yes |
| caption | 0 | T6wbugWrfLU | Céline Dion - That's The Way It Is |  | 20 | 11 | 0 | 0/0/1/19 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | wGyh_53ecgg | Ed Sheeran - Best Part Of Me (feat. YEBB |  | 20 | 10 | 0 | 0/20/0/0 |  |  |  |  |  |  | 28383401 | speed |  |  |
| caption | 0 | K0ibBPhiaG0 | Ed Sheeran - Castle On The Hill |  | 20 | 11 | 18 | 2/0/0/0 | 23335586 | 0 | 2 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | iWZmdoY1aTE | Ed Sheeran - Happier |  | 20 | 11 | 19 | 1/0/0/0 | 29277988 | 0 | 6 | 5 | 1 | ref_unclaimed |  |  |  | yes |
| caption | 0 | 2Vv-BfVoq4g | Ed Sheeran - Perfect |  | 20 | 10 | 15 | 0/4/0/1 | 19853882 | 1 | 2 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | JGwWNGJdvx8 | Ed Sheeran - Shape of You |  | 19 | 12 | 18 | 0/1/0/0 | 22081383 | 0 | 6 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | UAWcs5H-qgQ | Ed Sheeran - The A Team |  | 20 | 9 | 19 | 0/0/0/1 | 19121007 | 0 | 3 | 8 | 1 | none |  |  |  | yes |
| caption | 0 | lp-EO5I60KA | Ed Sheeran - Thinking Out Loud |  | 20 | 13 | 18 | 1/1/0/0 | 20756048 | 1 | 3 | 4 | 1 | none |  |  |  | yes |
| picks | 0 | xFYQQPAOz7Y | Eminem - Lose Yourself (8 Mile, 2002) |  | 15 | 4 | 15 | 0/0/0/0 | 18835951 | 0 | 3 | 11 |  | no reference | 19680363 | passes | yes | no |
| caption | 0 | Flight of the Conchords (2007) - Bowie | Flight of the Conchords (2007) - Bowie |  | 20 | 1 | 20 | 0/0/0/0 | 19452078 | 1 | 10 | 20 | 1 | ref_refused |  |  |  | yes |
| caption | 0 | Flight of the Conchords (2007) - Business Time | Flight of the Conchords (2007) - Busines |  | 20 | 5 | 0 | 6/0/14/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Carol Brown | Flight of the Conchords (2007) - Carol B |  | 20 | 5 | 0 | 2/0/0/18 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Foux du Fafa | Flight of the Conchords (2007) - Foux du |  | 20 | 4 | 0 | 20/0/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | Flight of the Conchords (2007) - Hiphopo |  | 20 | 5 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Hurt Feelings | Flight of the Conchords (2007) - Hurt Fe |  | 20 | 4 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Inner City Pressure | Flight of the Conchords (2007) - Inner C |  | 20 | 4 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Ladies of the World | Flight of the Conchords (2007) - Ladies  |  | 20 | 2 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Robots | Flight of the Conchords (2007) - Robots |  | 20 | 5 | 0 | 19/1/0/0 |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Sugalumps | Flight of the Conchords (2007) - Sugalum |  | 8 | 3 | 0 | 2/0/6/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - The Most Beautiful Girl (In the Room) | Flight of the Conchords (2007) - The Mos |  | 14 | 7 | 0 | 4/0/10/0 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | TeQ_TTyLGMs | Frozen (2013) - Do You Want to Build a S |  | 16 | 10 | 12 | 3/1/0/0 | 3514723 | 1 | 4 | 3 |  | no reference | 35805385 | passes | no | yes |
| picks | 0 | 9tcaM06eGrY | Frozen (2013) - In Summer (Sing-Along) |  | 13 | 8 | 8 | 2/0/0/3 | 3630452 | 0 | 11 | 3 |  | no reference | 36231531 | passes | no | yes |
| caption | 0 | YVVTZgwYwVo | Frozen (2013) - Let It Go |  | 9 | 9 | 2 | 7/0/0/0 | 15035688 | 0 | 3 | 1 | 1 | none |  |  |  | yes |
| picks | 0 | kQDw88hEr2c | Frozen (2013) - Love Is an Open Door (Si |  | 18 | 10 | 18 | 0/0/0/0 | 14494965 | 0 | 2 | 7 |  | no reference | 32050687 | passes | yes | no |
| picks | 0 | Vh74KE3o4Bs | Ingrid Michaelson - The Way I Am |  | 19 | 6 | 18 | 1/0/0/0 | 1781541 | 0 | 1 | 8 |  | no reference | 3161577 | passes | no | yes |
| picks | 0 | XdEN1b-dwlw | Ingrid Michaelson - You and I |  | 16 | 5 | 14 | 0/2/0/0 | 10035896 | 0 | 3 | 11 |  | no reference | 29026140 | passes | yes | no |
| joint | 0 | DYptgVvkVLQ | Jay Chou 周杰倫 - 晴天 (Sunny Day) |  | 19 | 3 | 0 | 19/0/0/0 |  |  |  |  |  |  | 22847808 | no_fit |  |  |
| caption | 0 | RPWDeLqsN0g | Jay Chou 周杰倫 - 龍捲風 (Tornado) |  | 2 | 2 | 0 | 2/0/0/0 |  |  |  |  | 0 |  |  |  |  |  |
| picks | 0 | UJtB55MaoD0 | Jessie J - Domino |  | 18 | 9 | 15 | 2/1/0/0 | 28220836 | 0 | 2 | 8 |  | no reference | 37465712 | passes | no | yes |
| caption | 0 | 450p7goxZqg | John Legend - All of Me |  | 19 | 12 | 19 | 0/0/0/0 | 22517354 | 0 | 1 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | Z3x9i7njCCo | Jung Kook 정국 - 3D (feat. Jack Harlow) (L |  | 20 | 12 | 8 | 9/0/3/0 | 8987220 | 0 | 6 | 4 | 1 | none |  |  |  | yes |
| picks | 0 | 1QYBiNRu1ok | Jung Kook 정국 - Seven (feat. Latto) |  | 20 | 13 | 18 | 0/0/2/0 | 31432999 | 0 | 4 | 4 |  | no reference | 33562631 | passes | no | yes |
| caption | 0 | 6q0JnftlH-I | Jung Kook 정국 - Standing Next to You |  | 18 | 10 | 0 | 0/1/17/0 |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | FQ3slUz7Jo8 | Justin Timberlake - Like I Love You |  | 19 | 7 | 17 | 1/0/0/1 | 19983370 | 0 | 4 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | uuZE_IRwLNI | Justin Timberlake - Mirrors |  | 20 | 7 | 0 | 0/0/1/19 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | TSVHoHyErBQ | Justin Timberlake - Rock Your Body |  | 20 | 8 | 0 | 0/0/17/3 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | je0roKRn3nY | Justin Timberlake - Selfish |  | 20 | 9 | 20 | 0/0/0/0 | 5659554 | 0 | 2 | 8 | 1 | none |  |  |  | yes |
| caption | 0 | IsUsVbTj2AY | Justin Timberlake - Suit & Tie (feat. JA |  | 15 | 10 | 13 | 1/0/1/0 | 30120287 | 0 | 11 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | KPop Demon Hunters (2025) - Free | KPop Demon Hunters (2025) - Free |  | 17 | 10 | 0 | 4/0/0/13 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | yebNIHKAC4A | KPop Demon Hunters (2025) - Golden |  | 14 | 8 | 4 | 5/4/0/1 | 23163059 | 0 | 8 | 3 |  | no reference | 31005537 | passes | no | yes |
| caption | 0 | KPop Demon Hunters (2025) - How It's Done | KPop Demon Hunters (2025) - How It's Don |  | 14 | 7 | 0 | 0/0/0/14 |  |  |  |  | 1 |  |  |  |  |  |
| joint | 0 | 983bBbJx0Mk | KPop Demon Hunters (2025) - Soda Pop |  | 19 | 8 | 0 | 19/0/0/0 |  |  |  |  |  |  | 36713302 | no_fit |  |  |
| picks | 0 | j5itLHDMJsE | KPop Demon Hunters (2025) - Takedown |  | 20 | 8 | 19 | 0/1/0/0 | 30356707 | 0 | 8 | 3 |  | no reference | 22746532 | passes | no | yes |
| caption | 0 | KPop Demon Hunters (2025) - What It Sounds Like | KPop Demon Hunters (2025) - What It Soun |  | 15 | 7 | 0 | 0/15/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | fGyTN5UjnL4 | KPop Demon Hunters (2025) - Your Idol |  | 18 | 9 | 16 | 1/0/1/0 | 23310716 | 1 | 8 | 4 |  | no reference | 37123328 | passes | no | yes |
| caption | 0 | Ra-Om7UMSJc | Kelly Clarkson - Because Of You |  | 19 | 8 | 15 | 0/4/0/0 | 18765707 | 0 | 2 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | zABLecsR5UE | Lewis Capaldi - Someone You Loved |  | 20 | 13 | 19 | 0/1/0/0 | 27564454 | 0 | 4 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | cPAbx5kgCJo | Moana (2016) - How Far I'll Go |  | 14 | 13 | 2 | 11/0/0/1 | 3292118 | 0 | 2 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | 93lrosBEW-Q | Moana (2016) - Shiny |  | 13 | 7 | 0 | 1/0/11/1 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 79DijItQXMM | Moana (2016) - You're Welcome |  | 5 | 4 | 0 | 1/0/0/4 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | -fxh7jAJR8U | NSYNC - (God Must Have Spent) A Little M |  | 20 | 13 | 4 | 1/8/7/0 | 28155617 | 0 | 11 | 3 | 1 | ref_unclaimed |  |  |  | yes |
| caption | 0 | Eo-KmOd3i7s | NSYNC - Bye Bye Bye |  | 20 | 13 | 0 | 13/2/0/5 |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | saxnXiBKEaY | NSYNC - Girlfriend |  | 18 | 9 | 0 | 0/0/17/1 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | IbRwSI8yi1o | NSYNC - Gone |  | 20 | 12 | 15 | 4/0/0/1 | 32643931 | 0 | 7 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | GQMlWwIXg3M | NSYNC - It's Gonna Be Me |  | 20 | 14 | 20 | 0/0/0/0 | 13572204 | 0 | 5 | 4 | 1 | none |  |  |  | yes |
| picks | 0 | NSYNC - Paradise | NSYNC - Paradise |  | 18 | 5 | 18 | 0/0/0/0 | 9488086 | 1 | 6 | 9 |  | no reference | 27903107 | passes | yes | no |
| caption | 0 | TWZKw_MgUPI | NSYNC - Pop |  | 20 | 12 | 0 | 0/0/20/0 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | PodgxWsZw9s | NSYNC - Thinking Of You (I Drive Myself  |  | 20 | 9 | 0 | 0/7/0/13 |  |  |  |  |  |  | 36176943 | unclaimed |  |  |
| caption | 0 | 6thmPrTxBtI | NSYNC - This I Promise You |  | 20 | 10 | 8 | 3/2/7/0 | 23889061 | 0 | 5 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | atz_aZA3rf0 | Ne-Yo - Because Of You |  | 20 | 9 | 0 | 0/2/4/14 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | k6M5C-oKw9k | Ne-Yo - Miss Independent |  | 20 | 10 | 0 | 0/0/0/20 |  |  |  |  |  |  | 12997477 | unclaimed |  |  |
| caption | 0 | 6tpl9LtkRRw | Ne-Yo - One In A Million |  | 20 | 9 | 0 | 0/0/7/13 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | IxszlJppRQI | Ne-Yo - So Sick |  | 18 | 11 | 14 | 0/2/2/0 | 16652439 | 0 | 7 | 3 | 1 | none |  |  |  | yes |
| picks | 0 | 9ThO76peOw0 | Pocahontas (1995) - Colors of the Wind |  | 11 | 6 | 1 | 6/4/0/0 | 34484694 | 0 | 4 | 1 |  | no reference | 35708272 | passes | no | yes |
| caption | 0 | fJ9rUzIMcZQ | Queen - Bohemian Rhapsody |  | 19 | 12 | 17 | 0/0/2/0 | 21655132 | 0 | 7 | 8 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Another Day | Rent (2005) - Another Day |  | 12 | 5 | 9 | 0/3/0/0 | 6156119 | 0 | 9 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - I Should Tell You | Rent (2005) - I Should Tell You |  | 20 | 7 | 15 | 1/4/0/0 | 6191521 | 0 | 3 | 10 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - I'll Cover You | Rent (2005) - I'll Cover You |  | 17 | 4 | 14 | 3/0/0/0 | 6191556 | 0 | 3 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Light My Candle | Rent (2005) - Light My Candle |  | 15 | 5 | 3 | 0/0/0/12 | 36678024 | 0 | 4 | 2 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - One Song Glory | Rent (2005) - One Song Glory |  | 20 | 6 | 17 | 0/3/0/0 | 6932651 | 0 | 3 | 15 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Out Tonight | Rent (2005) - Out Tonight |  | 20 | 6 | 14 | 0/6/0/0 | 6932715 | 0 | 5 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Santa Fe | Rent (2005) - Santa Fe |  | 20 | 7 | 0 | 6/0/4/10 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Rent (2005) - Seasons of Love | Rent (2005) - Seasons of Love |  | 12 | 7 | 10 | 0/0/0/2 | 36786874 | 0 | 6 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Today 4 U | Rent (2005) - Today 4 U |  | 4 | 2 | 0 | 0/0/0/4 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Rent (2005) - What You Own | Rent (2005) - What You Own |  | 14 | 5 | 5 | 0/9/0/0 | 28181941 | 0 | 2 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Without You | Rent (2005) - Without You |  | 17 | 7 | 12 | 0/5/0/0 | 6934735 | 1 | 2 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Your Eyes | Rent (2005) - Your Eyes |  | 19 | 8 | 9 | 0/10/0/0 | 21412032 | 0 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | WB9_sf6oV1o | S Club 7 - Never Had A Dream Come True |  | 20 | 8 | 20 | 0/0/0/0 | 32607617 | 0 | 2 | 11 | 1 | none |  |  |  | yes |
| picks | 0 | 53GIADHxVzM | Sara Bareilles - She Used To Be Mine |  | 19 | 9 | 14 | 1/4/0/0 | 12564402 | 0 | 3 | 6 |  | no reference | 9845205 | passes | no | yes |
| picks | 0 | wIyNAsmGrl0 | Silk Sonic (Bruno Mars & Anderson .Paak) |  | 20 | 12 | 0 | 1/0/5/14 |  |  |  |  |  |  | 1952973 | unclaimed |  |  |
| picks | 0 | CEw-7cMnBDY | Silk Sonic (Bruno Mars & Anderson .Paak) |  | 20 | 8 | 20 | 0/0/0/0 | 11390531 | 0 | 7 | 8 |  | no reference | 14315468 | passes | yes | no |
| picks | 0 | kRXmAIHYQR4 | Tangled (2010) - When Will My Life Begin |  | 18 | 10 | 18 | 0/0/0/0 | 24795512 | 0 | 2 | 3 |  | no reference | 13183578 | passes | no | yes |
| caption | 0 | _lK4cX5xGiQ | Tenacious D - Tribute |  | 20 | 5 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - A Miracle Would Happen & When You Come Home to Me | The Last Five Years (2014) - A Miracle W |  | 9 | 4 | 0 | 2/0/7/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - A Summer in Ohio | The Last Five Years (2014) - A Summer in |  | 10 | 5 | 2 | 0/5/3/0 | 23648746 | 0 | 10 | 2 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - Climbing Uphill | The Last Five Years (2014) - Climbing Up |  | 15 | 4 | 0 | 7/3/5/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Goodbye Until Tomorrow & I Could Never Rescue You | The Last Five Years (2014) - Goodbye Unt |  | 9 | 5 | 0 | 4/0/5/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - I Can Do Better Than That | The Last Five Years (2014) - I Can Do Be |  | 12 | 5 | 6 | 0/6/0/0 | 4179244 | 0 | 10 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - I'm a Part of That | The Last Five Years (2014) - I'm a Part  |  | 0 | 0 | 0 | 0/0/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - If I Didn't Believe in You | The Last Five Years (2014) - If I Didn't |  | 10 | 5 | 0 | 1/3/0/6 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Moving Too Fast | The Last Five Years (2014) - Moving Too  |  | 11 | 5 | 0 | 7/0/4/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Nobody Needs to Know | The Last Five Years (2014) - Nobody Need |  | 16 | 5 | 7 | 6/3/0/0 | 4626353 | 1 | 4 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - See I'm Smiling | The Last Five Years (2014) - See I'm Smi |  | 19 | 9 | 0 | 19/0/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Shiksa Goddess | The Last Five Years (2014) - Shiksa Godd |  | 11 | 5 | 0 | 5/0/6/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Still Hurting | The Last Five Years (2014) - Still Hurti |  | 17 | 8 | 6 | 3/8/0/0 | 4188091 | 0 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - The Next Ten Minutes | The Last Five Years (2014) - The Next Te |  | 17 | 6 | 8 | 3/6/0/0 | 4189082 | 0 | 6 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - The Schmuel Song | The Last Five Years (2014) - The Schmuel |  | 13 | 6 | 0 | 4/1/3/5 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | GibiNy4d4gc | The Lion King (1994) - Circle of Life |  | 9 | 6 | 0 | 1/4/0/4 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | SXKlJuO07eM | The Little Mermaid (1989) - Part of Your |  | 14 | 10 | 2 | 10/2/0/0 | 30097702 | 0 | 2 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | GC_mV1IpjWA | The Little Mermaid (1989) - Under the Se |  | 17 | 8 | 0 | 3/14/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| joint | 0 | kHwpS0LakeU | The Lonely Island - Here I Go (feat. Cha |  | 0 | 0 | 0 | 0/0/0/0 |  |  |  |  |  |  |  |  |  |  |
| picks | 0 | 68LBPvFhMx0 | The Lonely Island - Jose & Mark |  | 5 | 2 | 5 | 0/0/0/0 | 2554162 | 0 | 5 | 4 |  | no reference | 17370761 | passes | no | yes |
| picks | 0 | hj4e709GYf4 | The Lonely Island - Let's Bash |  | 7 | 1 | 7 | 0/0/0/0 | 1116686 | 0 | 3 | 7 |  | no reference | 17273734 | passes | yes | no |
| picks | 0 | gAYL5H46QnQ | The Lonely Island - Threw It On The Grou |  | 20 | 10 | 20 | 0/0/0/0 | 35338143 | 0 | 2 | 6 |  | no reference | 39765748 | passes | no | yes |
| picks | 0 | XzbHPqULtdA | The Outsiders (2024) - Stay Gold |  | 13 | 7 | 4 | 9/0/0/0 | 27305964 | 0 | 2 | 4 |  | no reference | 34445486 | passes | yes | no |
| caption | 0 | EUW0eDhKoxw | The Philosopher Kings - Cry |  | 5 | 1 | 5 | 0/0/0/0 | 28361150 | 0 | 9 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | 6X4bhT1FWjI | The Philosopher Kings - Hurts To Love Yo |  | 4 | 2 | 0 | 4/0/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | AI7F8qlN44E | The Philosopher Kings - You Don't Love M |  | 6 | 2 | 0 | 0/0/0/6 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | tz_NxOF7RB4 | Vitamin C - Graduation (Friends Forever) |  | 20 | 7 | 1 | 2/0/17/0 | 9980085 | 1 | 10 | 1 |  | no reference | 9980085 | passes | yes | no |
| caption | 0 | 3JWTaaS7LdU | Whitney Houston - I Will Always Love You |  | 20 | 9 | 11 | 4/5/0/0 | 29741730 | 0 | 1 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | TZ0pXUb5jVU | Wicked (2003) - For Good |  | 17 | 6 | 0 | 8/9/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | rg_zwK_sSEY | ZAYN & Zhavia Ward - A Whole New World ( |  | 20 | 9 | 20 | 0/0/0/0 | 7428207 | 0 | 9 | 5 | 1 | none |  |  |  | yes |

### Table K: GATE M LRC-wrong records

| youtube_id | lrclib_id | Source | In_pool | Status | Speed | Mistimed | Unclaimed | Refusal | Picked | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| GZXHBgjQjNM | 20242140 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 21912586 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 27023721 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 31535578 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 32140003 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 35793714 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 36228137 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| AJWtLf4-WWs | 6800151 | pool | yes | fits | 1.0000 | 1 | 14 | unclaimed | no |  |
| AJWtLf4-WWs | 28307055 | pool | yes | fits | 1.0000 | 1 | 14 | unclaimed | no |  |
| AJWtLf4-WWs | 34352818 | pool | yes | fits | 1.0000 | 1 | 14 | unclaimed | no |  |
| UAWcs5H-qgQ | 12572148 | pool | yes | fits | 1.0000 | 0 | 89 | unclaimed | no |  |
| T6wbugWrfLU | 35468507 | pool | yes | fits | 1.0000 | 0 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 3458703 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 6335685 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 7720552 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 9641374 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 12149023 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 12377831 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 12515974 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 15413449 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 17099666 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 20411476 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 23305471 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 24586049 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 24809544 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 31956521 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 32182355 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 32691192 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 33133897 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 34902348 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |

### Table X: flagged passing records not picked

| Song | youtube_id | Ids of the timing | Flags | Mistimed | Unclaimed |
|---|---|---|---|---|---|
| Backstreet Boys - Drowning | GZXHBgjQjNM | 19447935, 26104541 | ref_shift | 0 | 6 |
| Backstreet Boys - Drowning | GZXHBgjQjNM | 20242140, 21912586, 27023721, 31535578, 32140003, 35793714, 36228137 | ref_mistimed | 1 | 6 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 3654026 | ref_unclaimed | 0 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 10249637 | ref_unclaimed | 0 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 13474015 | ref_unclaimed | 0 | 8 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 13609412, 33966854 | ref_mistimed ref_unclaimed | 1 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 13641580 | ref_unclaimed | 0 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 22381484, 34452636, 35231491, 36285083 | ref_unclaimed | 0 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 36673394 | ref_unclaimed | 0 | 8 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 3742260 | ref_mistimed | 0 | 3 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 13013886, 15818656, 17214765 | ref_mistimed | 0 | 3 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 21931798 | ref_mistimed | 0 | 3 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 24678599 | ref_mistimed | 0 | 3 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 31572444 | ref_mistimed | 0 | 2 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 2854250 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 6674983, 7260734, 8325988, 9595552 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 8097534 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 10039069 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 10503213 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 12512210 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 23858174 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 32633585, 33790241, 35467074 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 40073089 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Perfect | 2Vv-BfVoq4g | 2943073, 36009208 | ref_unheard | 1 | 2 |
| Ed Sheeran - Shape of You | JGwWNGJdvx8 | 38587774 | ref_unclaimed ref_unheard | 0 | 11 |
| Frozen (2013) - Let It Go | YVVTZgwYwVo | 14494777 | ref_mistimed | 1 | 3 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 4830039, 17014461 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 6563397, 29351856 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 14357227 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 16431444 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 28278766, 35648481 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 37912453 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 38381482 | ref_unclaimed | 0 | 11 |
| NSYNC - (God Must Have Spent) A Little M | -fxh7jAJR8U | 39499684 | ref_unclaimed | 0 | 11 |
| Rent (2005) - What You Own | Rent (2005) - What You Own | 14409292, 39413351 | ref_unheard | 0 | 2 |
| The Last Five Years (2014) - The Next Te | The Last Five Years (2014) - The Next Ten Minutes | 13769166, 25808567, 37998862 | ref_unheard | 0 | 2 |

### Table V: songs with a pick at other limits

| Group | Mistimed <= | Songs | Unclaimed <= 8 | Unclaimed <= 10 | Unclaimed <= 12 | Unclaimed <= 15 | Unclaimed <= 20 |
|---|---|---|---|---|---|---|---|
| picks | 0 | 28 | 16 | 17 | 18 | 18 | 19 |
| picks | 1 | 28 | 20 | 22 | 23 | 23 | 24 |
| joint | 0 | 5 | 1 | 1 | 1 | 1 | 1 |
| joint | 1 | 5 | 1 | 1 | 1 | 1 | 1 |
| caption | 0 | 111 | 48 | 51 | 54 | 56 | 60 |
| caption | 1 | 111 | 54 | 58 | 61 | 64 | 69 |
| new | 0 | 1 | 1 | 1 | 1 | 1 | 1 |
| new | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

### Table L: the listen list

| Rank | Group | New | Title | youtube_id | lrclib_id | Why | Listen_file |
|---|---|---|---|---|---|---|---|
| 1 | picks | 0 | Frozen (2013) - In Summer (Sing-Along) | 9tcaM06eGrY | 3630452 | no reference | Frozen (2013) - In Summer (Sing-Along)---9tcaM06eGrY.3630452.srt |
| 2 | picks | 0 | Camp Rock (2008) - This Is Me (Sing-Alon | 6HCUoMgviwU | 17015895 | no reference | Camp Rock (2008) - This Is Me (Sing-Along)---6HCUoMgviwU.17015895.srt |
| 3 | picks | 0 | KPop Demon Hunters (2025) - Your Idol | fGyTN5UjnL4 | 23310716 | no reference | KPop Demon Hunters (2025) - Your Idol---fGyTN5UjnL4.23310716.srt |
| 4 | picks | 0 | KPop Demon Hunters (2025) - Takedown | j5itLHDMJsE | 30356707 | no reference | KPop Demon Hunters (2025) - Takedown---j5itLHDMJsE.30356707.srt |
| 5 | picks | 0 | KPop Demon Hunters (2025) - Golden | yebNIHKAC4A | 23163059 | no reference | KPop Demon Hunters (2025) - Golden---yebNIHKAC4A.23163059.srt |
| 6 | joint | 1 | Bruno Mars - Just The Way You Are (Offic | LjhCEhWiKXk | 9888181 | no reference | Bruno Mars - Just The Way You Are (Official Music Video)---LjhCEhWiKXk.9888181.srt |
| 7 | picks | 0 | The Lonely Island - Jose & Mark | 68LBPvFhMx0 | 2554162 | no reference | The Lonely Island - Jose & Mark---68LBPvFhMx0.2554162.srt |
| 8 | picks | 0 | Frozen (2013) - Do You Want to Build a S | TeQ_TTyLGMs | 3514723 | no reference | Frozen (2013) - Do You Want to Build a Snowman (Sing-Along)---TeQ_TTyLGMs.3514723.srt |
| 9 | picks | 0 | Jung Kook 정국 - Seven (feat. Latto) | 1QYBiNRu1ok | 31432999 | no reference | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok.31432999.srt |
| 10 | picks | 0 | Pocahontas (1995) - Colors of the Wind | 9ThO76peOw0 | 34484694 | no reference | Pocahontas (1995) - Colors of the Wind---9ThO76peOw0.34484694.srt |
| 11 | picks | 0 | Sara Bareilles - She Used To Be Mine | 53GIADHxVzM | 12564402 | no reference | Sara Bareilles - She Used To Be Mine---53GIADHxVzM.12564402.srt |
| 12 | caption | 0 | Céline Dion - My Heart Will Go On (Titan | 9bFHsd3o1w0 | 22553995 | no reference | Céline Dion - My Heart Will Go On (Titanic, 1997)---9bFHsd3o1w0.22553995.srt |
| 13 | caption | 0 | Céline Dion - I'm Alive (Stuart Little 2 | NJsa6-y4sDs | 28130840 | no reference | Céline Dion - I'm Alive (Stuart Little 2, 2002)---NJsa6-y4sDs.28130840.srt |
| 14 | picks | 0 | Jessie J - Domino | UJtB55MaoD0 | 28220836 | no reference | Jessie J - Domino---UJtB55MaoD0.28220836.srt |
| 15 | picks | 0 | The Lonely Island - Threw It On The Grou | gAYL5H46QnQ | 35338143 | no reference | The Lonely Island - Threw It On The Ground---gAYL5H46QnQ.35338143.srt |
| 16 | picks | 0 | Tangled (2010) - When Will My Life Begin | kRXmAIHYQR4 | 24795512 | no reference | Tangled (2010) - When Will My Life Begin (Sing-Along)---kRXmAIHYQR4.24795512.srt |
| 17 | picks | 0 | Ingrid Michaelson - The Way I Am | Vh74KE3o4Bs | 1781541 | no reference | Ingrid Michaelson - The Way I Am---Vh74KE3o4Bs.1781541.srt |
| 18 | caption | 0 | NSYNC - (God Must Have Spent) A Little M | -fxh7jAJR8U | 28155617 | flagged: ref_unclaimed | NSYNC - (God Must Have Spent) A Little More Time On You----fxh7jAJR8U.28155617.srt |
| 19 | caption | 0 | Flight of the Conchords (2007) - Bowie | Flight of the Conchords (2007) - Bowie | 19452078 | flagged: ref_refused | Flight of the Conchords (2007) - Bowie.19452078.srt |
| 20 | caption | 0 | Britney Spears - (You Drive Me) Crazy | Q4VK9_CfOLQ | 2137556 | flagged: ref_mistimed | Britney Spears - (You Drive Me) Crazy---Q4VK9_CfOLQ.2137556.srt |
| 21 | caption | 0 | Backstreet Boys - Drowning | GZXHBgjQjNM | 14595571 | flagged: ref_shift | Backstreet Boys - Drowning---GZXHBgjQjNM.14595571.srt |
| 22 | caption | 0 | Ed Sheeran - Happier | iWZmdoY1aTE | 29277988 | flagged: ref_unclaimed | Ed Sheeran - Happier---iWZmdoY1aTE.29277988.srt |
| 23 | caption | 0 | Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 1124886 | flagged: ref_unclaimed | Backstreet Boys - Get Down (You're The One For Me)---0LSYuZRSGcY.1124886.srt |
| 24 | caption | 0 | Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 685756 | flagged: ref_mistimed | Christina Aguilera - Reflection (Mulan, 2020)---RNprQYHenNI.685756.srt |
| 25 | caption | 0 | Colbie Caillat - Realize | GlZxZ2n2zpw | 586041 | unflagged | Colbie Caillat - Realize---GlZxZ2n2zpw.586041.srt |
| 26 | caption | 0 | Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 30120287 | unflagged | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY.30120287.srt |
| 27 | caption | 0 | The Last Five Years (2014) - A Summer in | The Last Five Years (2014) - A Summer in Ohio | 23648746 | unflagged | The Last Five Years (2014) - A Summer in Ohio.23648746.srt |
| 28 | caption | 0 | The Last Five Years (2014) - I Can Do Be | The Last Five Years (2014) - I Can Do Better Than That | 4179244 | unflagged | The Last Five Years (2014) - I Can Do Better Than That.4179244.srt |
| 29 | caption | 0 | The Philosopher Kings - Cry | EUW0eDhKoxw | 28361150 | unflagged | The Philosopher Kings - Cry---EUW0eDhKoxw.28361150.srt |
| 30 | caption | 0 | Rent (2005) - Another Day | Rent (2005) - Another Day | 6156119 | unflagged | Rent (2005) - Another Day.6156119.srt |
| 31 | caption | 0 | ZAYN & Zhavia Ward - A Whole New World ( | rg_zwK_sSEY | 7428207 | unflagged | ZAYN & Zhavia Ward - A Whole New World (End Title) (Aladdin, 2019)---rg_zwK_sSEY.7428207.srt |
| 32 | caption | 0 | Backstreet Boys - As Long As You Love Me | 0Gl2QnHNpkA | 3722851 | unflagged | Backstreet Boys - As Long As You Love Me---0Gl2QnHNpkA.3722851.srt |
| 33 | caption | 0 | NSYNC - Gone | IbRwSI8yi1o | 32643931 | unflagged | NSYNC - Gone---IbRwSI8yi1o.32643931.srt |
| 34 | caption | 0 | Ne-Yo - So Sick | IxszlJppRQI | 16652439 | unflagged | Ne-Yo - So Sick---IxszlJppRQI.16652439.srt |
| 35 | caption | 0 | BTS 방탄소년단 - Butter | WMweEpGlu_U | 32156281 | unflagged | BTS 방탄소년단 - Butter---WMweEpGlu_U.32156281.srt |
| 36 | caption | 0 | Queen - Bohemian Rhapsody | fJ9rUzIMcZQ | 21655132 | unflagged | Queen - Bohemian Rhapsody---fJ9rUzIMcZQ.21655132.srt |
| 37 | caption | 0 | Backstreet Boys - I Want It That Way | 4fndeDfaWCg | 11268019 | unflagged | Backstreet Boys - I Want It That Way---4fndeDfaWCg.11268019.srt |
| 38 | caption | 0 | Ed Sheeran - Shape of You | JGwWNGJdvx8 | 22081383 | unflagged | Ed Sheeran - Shape of You---JGwWNGJdvx8.22081383.srt |
| 39 | caption | 0 | Backstreet Boys - Shape Of My Heart | OT5msu-dap8 | 22503174 | unflagged | Backstreet Boys - Shape Of My Heart---OT5msu-dap8.22503174.srt |
| 40 | caption | 0 | Rent (2005) - Seasons of Love | Rent (2005) - Seasons of Love | 36786874 | unflagged | Rent (2005) - Seasons of Love.36786874.srt |
| 41 | caption | 0 | The Last Five Years (2014) - The Next Te | The Last Five Years (2014) - The Next Ten Minutes | 4189082 | unflagged | The Last Five Years (2014) - The Next Ten Minutes.4189082.srt |
| 42 | caption | 0 | Jung Kook 정국 - 3D (feat. Jack Harlow) (L | Z3x9i7njCCo | 8987220 | unflagged | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo.8987220.srt |
| 43 | caption | 0 | Backstreet Boys - Inconsolable | qGDF_QcsKVI | 35522789 | unflagged | Backstreet Boys - Inconsolable---qGDF_QcsKVI.35522789.srt |
| 44 | caption | 0 | NSYNC - This I Promise You | 6thmPrTxBtI | 23889061 | unflagged | NSYNC - This I Promise You---6thmPrTxBtI.23889061.srt |
| 45 | caption | 0 | NSYNC - It's Gonna Be Me | GQMlWwIXg3M | 13572204 | unflagged | NSYNC - It's Gonna Be Me---GQMlWwIXg3M.13572204.srt |
| 46 | caption | 0 | Rent (2005) - Out Tonight | Rent (2005) - Out Tonight | 6932715 | unflagged | Rent (2005) - Out Tonight.6932715.srt |
| 47 | caption | 0 | Backstreet Boys - Quit Playing Games (Wi | Ug88HO2mg44 | 33413907 | unflagged | Backstreet Boys - Quit Playing Games (With My Heart)---Ug88HO2mg44.33413907.srt |
| 48 | caption | 0 | Ariana Grande & John Legend - Beauty and | axySrE0Kg6k | 31988497 | unflagged | Ariana Grande & John Legend - Beauty and the Beast (Beauty and the Beast, 2017)---axySrE0Kg6k.31988497.srt |
| 49 | caption | 0 | The Last Five Years (2014) - Nobody Need | The Last Five Years (2014) - Nobody Needs to Know | 4626353 | unflagged | The Last Five Years (2014) - Nobody Needs to Know.4626353.srt |
| 50 | caption | 0 | Backstreet Boys - Incomplete | WVe80iZtlYU | 19180415 | unflagged | Backstreet Boys - Incomplete---WVe80iZtlYU.19180415.srt |
| 51 | caption | 0 | Backstreet Boys - More Than That | 1OwfYjemrYw | 36314729 | unflagged | Backstreet Boys - More Than That---1OwfYjemrYw.36314729.srt |
| 52 | caption | 0 | Britney Spears - ...Baby One More Time | C-u5WLJ9Yk4 | 32110280 | unflagged | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4.32110280.srt |
| 53 | caption | 0 | Justin Timberlake - Like I Love You | FQ3slUz7Jo8 | 19983370 | unflagged | Justin Timberlake - Like I Love You---FQ3slUz7Jo8.19983370.srt |
| 54 | caption | 0 | Rent (2005) - Light My Candle | Rent (2005) - Light My Candle | 36678024 | unflagged | Rent (2005) - Light My Candle.36678024.srt |
| 55 | caption | 0 | Lewis Capaldi - Someone You Loved | zABLecsR5UE | 27564454 | unflagged | Lewis Capaldi - Someone You Loved---zABLecsR5UE.27564454.srt |
| 56 | caption | 0 | Ed Sheeran - Thinking Out Loud | lp-EO5I60KA | 20756048 | unflagged | Ed Sheeran - Thinking Out Loud---lp-EO5I60KA.20756048.srt |
| 57 | caption | 0 | Rent (2005) - I Should Tell You | Rent (2005) - I Should Tell You | 6191521 | unflagged | Rent (2005) - I Should Tell You.6191521.srt |
| 58 | caption | 0 | Rent (2005) - I'll Cover You | Rent (2005) - I'll Cover You | 6191556 | unflagged | Rent (2005) - I'll Cover You.6191556.srt |
| 59 | caption | 0 | Rent (2005) - One Song Glory | Rent (2005) - One Song Glory | 6932651 | unflagged | Rent (2005) - One Song Glory.6932651.srt |
| 60 | caption | 0 | Ed Sheeran - The A Team | UAWcs5H-qgQ | 19121007 | unflagged | Ed Sheeran - The A Team---UAWcs5H-qgQ.19121007.srt |
| 61 | caption | 0 | Frozen (2013) - Let It Go | YVVTZgwYwVo | 15035688 | unflagged | Frozen (2013) - Let It Go---YVVTZgwYwVo.15035688.srt |
| 62 | caption | 0 | Aladdin (2019) - Speechless | mw5VIEIvuMI | 19793188 | unflagged | Aladdin (2019) - Speechless---mw5VIEIvuMI.19793188.srt |
| 63 | caption | 0 | Ed Sheeran - Perfect | 2Vv-BfVoq4g | 19853882 | unflagged | Ed Sheeran - Perfect---2Vv-BfVoq4g.19853882.srt |
| 64 | caption | 0 | Rent (2005) - Without You | Rent (2005) - Without You | 6934735 | unflagged | Rent (2005) - Without You.6934735.srt |
| 65 | caption | 0 | Ed Sheeran - Castle On The Hill | K0ibBPhiaG0 | 23335586 | unflagged | Ed Sheeran - Castle On The Hill---K0ibBPhiaG0.23335586.srt |
| 66 | caption | 0 | Kelly Clarkson - Because Of You | Ra-Om7UMSJc | 18765707 | unflagged | Kelly Clarkson - Because Of You---Ra-Om7UMSJc.18765707.srt |
| 67 | caption | 0 | Rent (2005) - What You Own | Rent (2005) - What You Own | 28181941 | unflagged | Rent (2005) - What You Own.28181941.srt |
| 68 | caption | 0 | The Little Mermaid (1989) - Part of Your | SXKlJuO07eM | 30097702 | unflagged | The Little Mermaid (1989) - Part of Your World---SXKlJuO07eM.30097702.srt |
| 69 | caption | 0 | S Club 7 - Never Had A Dream Come True | WB9_sf6oV1o | 32607617 | unflagged | S Club 7 - Never Had A Dream Come True---WB9_sf6oV1o.32607617.srt |
| 70 | caption | 0 | Moana (2016) - How Far I'll Go | cPAbx5kgCJo | 3292118 | unflagged | Moana (2016) - How Far I'll Go---cPAbx5kgCJo.3292118.srt |
| 71 | caption | 0 | Adele - Someone Like You | hLQl3WQQoQ0 | 23116607 | unflagged | Adele - Someone Like You---hLQl3WQQoQ0.23116607.srt |
| 72 | caption | 0 | Justin Timberlake - Selfish | je0roKRn3nY | 5659554 | unflagged | Justin Timberlake - Selfish---je0roKRn3nY.5659554.srt |
| 73 | caption | 0 | Whitney Houston - I Will Always Love You | 3JWTaaS7LdU | 29741730 | unflagged | Whitney Houston - I Will Always Love You (The Bodyguard, 1992)---3JWTaaS7LdU.29741730.srt |
| 74 | caption | 0 | John Legend - All of Me | 450p7goxZqg | 22517354 | unflagged | John Legend - All of Me---450p7goxZqg.22517354.srt |
| 75 | caption | 0 | Rent (2005) - Your Eyes | Rent (2005) - Your Eyes | 21412032 | unflagged | Rent (2005) - Your Eyes.21412032.srt |
| 76 | caption | 0 | The Last Five Years (2014) - Still Hurti | The Last Five Years (2014) - Still Hurting | 4188091 | unflagged | The Last Five Years (2014) - Still Hurting.4188091.srt |

## Report output: holdout run

Verbatim from `~/.pikaraoke/tmp/lrclib_fit_pick_holdout/report.md` (3b); the table headings are one level down.

Bar in force: mistimed <= 1, unclaimed run <= 12, speed 1.0. 198 songs in /home/ken/shared-drives/D:/Shared/pikaraoke-songs; output in /home/ken/.pikaraoke/tmp/lrclib_fit_pick_holdout; listen files in /home/ken/shared-drives/D:/Shared/lrclib-listen.

### Table P: groups and skip reasons

| Group | Songs | no_length | lrclib_unavailable | No synced record | With a pick |
|---|---|---|---|---|---|
| picks | 28 | 0 | 0 | 0 | 23 |
| joint | 33 | 0 | 0 | 1 | 21 |
| caption | 112 | 0 | 0 | 1 | 61 |
| new | 30 | 0 | 0 | 0 | 21 |

| out_of_scope reason | Songs |
|---|---|
| custom | 3 |
| movie_srt | 7 |
| no_bundle | 15 |
| no_words | 0 |
| edited | 0 |
| no_caption_file | 0 |
| other | 0 |

### Table S: songs

| Group | New | youtube_id | Title | Skipped | Records | Timings | Passing | no_fit/speed/mistimed/unclaimed | Pick | Mistimed | Unclaimed | Timing_size | ref_ok | Reference_flags | On_disk_id | On_disk_refusal | Pick_has_disk_timing | Needs_verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| joint | 0 | jeRu6h4XbUU | A-Lin - 幸福在歌唱 (Happiness Is Singing) |  | 2 | 1 | 0 | 2/0/0/0 |  |  |  |  |  |  | 38356656 | no_fit |  |  |
| caption | 0 | hLQl3WQQoQ0 | Adele - Someone Like You |  | 20 | 13 | 19 | 0/1/0/0 | 23116607 | 0 | 2 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | eitDnP0_83k | Aladdin (2019) - A Whole New World |  | 16 | 10 | 0 | 5/5/0/6 |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | mw5VIEIvuMI | Aladdin (2019) - Speechless |  | 13 | 12 | 10 | 0/1/1/1 | 19793188 | 0 | 3 | 2 | 1 | none |  |  |  | yes |
| caption | 0 | axySrE0Kg6k | Ariana Grande & John Legend - Beauty and |  | 20 | 11 | 19 | 0/1/0/0 | 31988497 | 0 | 5 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | WMweEpGlu_U | BTS 방탄소년단 - Butter |  | 19 | 12 | 15 | 0/0/0/4 | 32156281 | 0 | 7 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | pj6FCKm8dhM | Backstreet Boys - All I Have To Give |  | 18 | 7 | 0 | 1/0/17/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 0Gl2QnHNpkA | Backstreet Boys - As Long As You Love Me |  | 20 | 11 | 7 | 11/0/2/0 | 3722851 | 0 | 8 | 3 | 1 | none |  |  |  | yes |
| picks | 0 | W5kM5wAwRug | Backstreet Boys - Chances (Official Vide |  | 19 | 11 | 12 | 6/1/0/0 | 2031559 | 1 | 3 | 8 |  | no reference | 33832441 | passes | yes | no |
| caption | 0 | GZXHBgjQjNM | Backstreet Boys - Drowning |  | 20 | 9 | 18 | 1/1/0/0 | 14595571 | 0 | 6 | 3 | 1 | ref_shift |  |  |  | yes |
| caption | 0 | 6M6samPEMpM | Backstreet Boys - Everybody (Backstreet' |  | 20 | 17 | 0 | 0/2/0/18 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 0LSYuZRSGcY | Backstreet Boys - Get Down (You're The O |  | 20 | 11 | 20 | 0/0/0/0 | 1124886 | 0 | 5 | 6 | 1 | ref_unclaimed |  |  |  | yes |
| caption | 0 | 4fndeDfaWCg | Backstreet Boys - I Want It That Way |  | 20 | 15 | 19 | 0/1/0/0 | 11268019 | 0 | 6 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | kDcCSiakaU4 | Backstreet Boys - I'll Never Break Your  |  | 20 | 10 | 0 | 0/0/20/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | WVe80iZtlYU | Backstreet Boys - Incomplete |  | 20 | 10 | 17 | 0/3/0/0 | 19180415 | 1 | 4 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | qGDF_QcsKVI | Backstreet Boys - Inconsolable |  | 14 | 6 | 14 | 0/0/0/0 | 35522789 | 0 | 6 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | MEb2CecR11I | Backstreet Boys - Larger Than Life (Offi |  | 20 | 6 | 0 | 17/3/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 1OwfYjemrYw | Backstreet Boys - More Than That |  | 20 | 11 | 20 | 0/0/0/0 | 36314729 | 0 | 4 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | Ug88HO2mg44 | Backstreet Boys - Quit Playing Games (Wi |  | 20 | 11 | 1 | 3/2/0/14 | 33413907 | 0 | 5 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | OT5msu-dap8 | Backstreet Boys - Shape Of My Heart |  | 20 | 12 | 15 | 0/5/0/0 | 22503174 | 0 | 6 | 6 | 1 | none |  |  |  | yes |
| joint | 1 | aBt8fN7mJNg | Backstreet Boys - Show Me The Meaning Of |  | 20 | 7 | 20 | 0/0/0/0 | 19923333 | 0 | 4 | 11 |  | no reference | 7255301 | passes | no | yes |
| caption | 0 | wMOkm57vu0k | Backstreet Boys - The Call |  | 20 | 11 | 0 | 0/0/20/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Q4VK9_CfOLQ | Britney Spears - (You Drive Me) Crazy |  | 20 | 9 | 1 | 14/5/0/0 | 2137556 | 1 | 7 | 1 | 1 | ref_mistimed |  |  |  | yes |
| caption | 0 | C-u5WLJ9Yk4 | Britney Spears - ...Baby One More Time |  | 20 | 10 | 16 | 4/0/0/0 | 32110280 | 0 | 4 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | CduA0TULnow | Britney Spears - Oops!...I Did It Again |  | 20 | 16 | 0 | 3/1/0/16 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | AJWtLf4-WWs | Britney Spears - Stronger |  | 19 | 9 | 0 | 2/0/0/17 |  |  |  |  | 1 |  |  |  |  |  |
| joint | 1 | SR6iYWJxHqs | Bruno Mars - Grenade (Official Music Vid |  | 19 | 11 | 9 | 1/9/0/0 | 38953751 | 0 | 2 | 2 |  | no reference | 3851492 | speed | no | yes |
| picks | 0 | luotSpkyCVU | Bruno Mars - I Just Might |  | 20 | 6 | 0 | 0/0/0/20 |  |  |  |  |  |  | 26520597 | unclaimed |  |  |
| joint | 1 | LjhCEhWiKXk | Bruno Mars - Just The Way You Are (Offic |  | 20 | 13 | 10 | 0/7/3/0 | 9888181 | 0 | 7 | 2 |  | no reference | 7470259 | passes | no | yes |
| joint | 1 | e-fA-gBCkj0 | Bruno Mars - Locked Out Of Heaven (Offic |  | 20 | 12 | 3 | 0/17/0/0 | 6936310 | 0 | 7 | 2 |  | no reference | 12586557 | speed | no | yes |
| joint | 1 | fLexgOxsZu0 | Bruno Mars - The Lazy Song (Official Mus |  | 20 | 12 | 20 | 0/0/0/0 | 6706711 | 0 | 10 | 6 |  | no reference | 8097183 | passes | yes | yes |
| joint | 1 | ekzHIouo8Q4 | Bruno Mars - When I Was Your Man (Offici |  | 19 | 16 | 19 | 0/0/0/0 | 26614056 | 0 | 7 | 2 |  | no reference | 7076945 | passes | no | yes |
| joint | 1 | -cy_tDQPXHk | Bruno Mars, Anderson .Paak, Silk Sonic - |  | 20 | 10 | 0 | 0/0/0/20 |  |  |  |  |  |  | 9680068 | unclaimed |  |  |
| picks | 0 | 6HCUoMgviwU | Camp Rock (2008) - This Is Me (Sing-Alon |  | 19 | 13 | 1 | 3/0/15/0 | 17015895 | 0 | 9 | 1 |  | no reference | 28926432 | passes | no | yes |
| caption | 0 | RNprQYHenNI | Christina Aguilera - Reflection (Mulan,  |  | 20 | 7 | 20 | 0/0/0/0 | 685756 | 0 | 3 | 12 | 1 | ref_mistimed |  |  |  | yes |
| caption | 0 | GlZxZ2n2zpw | Colbie Caillat - Realize |  | 19 | 9 | 16 | 1/1/1/0 | 37946467 | 0 | 12 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | CX11yw6YL1w | Céline Dion - Ashes (Deadpool 2, 2018) |  | 20 | 9 | 0 | 0/3/0/17 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | NJsa6-y4sDs | Céline Dion - I'm Alive (Stuart Little 2 |  | 20 | 9 | 19 | 0/1/0/0 | 28130840 | 0 | 3 | 6 | 0 | no reference |  |  |  | yes |
| caption | 0 | 9bFHsd3o1w0 | Céline Dion - My Heart Will Go On (Titan |  | 19 | 11 | 12 | 2/4/1/0 | 22553995 | 0 | 3 | 9 | 0 | no reference |  |  |  | yes |
| caption | 0 | T6wbugWrfLU | Céline Dion - That's The Way It Is |  | 20 | 11 | 0 | 0/0/1/19 |  |  |  |  | 1 |  |  |  |  |  |
| joint | 1 | 62llzl7iKkE | Demi Lovato, Joe Jonas - Wouldn't Change |  | 16 | 10 | 15 | 0/1/0/0 | 33991259 | 0 | 7 | 3 |  | no reference | 25091390 | passes | yes | yes |
| joint | 1 | -7jWt3JvJto | Donna Murphy - Mother Knows Best (From ' |  | 20 | 4 | 0 | 3/0/17/0 |  |  |  |  |  |  | 36177014 | mistimed |  |  |
| picks | 0 | wGyh_53ecgg | Ed Sheeran - Best Part Of Me (feat. YEBB |  | 20 | 10 | 0 | 0/20/0/0 |  |  |  |  |  |  | 28383401 | speed |  |  |
| caption | 0 | K0ibBPhiaG0 | Ed Sheeran - Castle On The Hill |  | 20 | 11 | 18 | 2/0/0/0 | 23335586 | 0 | 2 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | iWZmdoY1aTE | Ed Sheeran - Happier |  | 20 | 11 | 19 | 1/0/0/0 | 29277988 | 0 | 6 | 5 | 1 | ref_unclaimed |  |  |  | yes |
| caption | 0 | 2Vv-BfVoq4g | Ed Sheeran - Perfect |  | 20 | 10 | 15 | 0/4/0/1 | 19853882 | 1 | 2 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | JGwWNGJdvx8 | Ed Sheeran - Shape of You |  | 19 | 12 | 18 | 0/1/0/0 | 22081383 | 0 | 6 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | UAWcs5H-qgQ | Ed Sheeran - The A Team |  | 20 | 9 | 19 | 0/0/0/1 | 19121007 | 0 | 3 | 8 | 1 | none |  |  |  | yes |
| caption | 0 | lp-EO5I60KA | Ed Sheeran - Thinking Out Loud |  | 20 | 13 | 18 | 1/1/0/0 | 20756048 | 1 | 3 | 4 | 1 | none |  |  |  | yes |
| picks | 0 | xFYQQPAOz7Y | Eminem - Lose Yourself (8 Mile, 2002) |  | 15 | 4 | 15 | 0/0/0/0 | 18835951 | 0 | 3 | 11 |  | no reference | 19680363 | passes | yes | no |
| caption | 0 | Flight of the Conchords (2007) - Bowie | Flight of the Conchords (2007) - Bowie |  | 20 | 1 | 20 | 0/0/0/0 | 19452078 | 1 | 10 | 20 | 1 | ref_refused |  |  |  | yes |
| caption | 0 | Flight of the Conchords (2007) - Business Time | Flight of the Conchords (2007) - Busines |  | 20 | 5 | 0 | 6/0/14/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Carol Brown | Flight of the Conchords (2007) - Carol B |  | 20 | 5 | 0 | 2/0/0/18 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Foux du Fafa | Flight of the Conchords (2007) - Foux du |  | 20 | 4 | 0 | 20/0/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | Flight of the Conchords (2007) - Hiphopo |  | 20 | 5 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Hurt Feelings | Flight of the Conchords (2007) - Hurt Fe |  | 20 | 4 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Inner City Pressure | Flight of the Conchords (2007) - Inner C |  | 20 | 4 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Ladies of the World | Flight of the Conchords (2007) - Ladies  |  | 20 | 2 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Robots | Flight of the Conchords (2007) - Robots |  | 20 | 5 | 0 | 19/1/0/0 |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Sugalumps | Flight of the Conchords (2007) - Sugalum |  | 8 | 3 | 0 | 2/0/6/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - The Most Beautiful Girl (In the Room) | Flight of the Conchords (2007) - The Mos |  | 14 | 7 | 0 | 4/0/10/0 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | TeQ_TTyLGMs | Frozen (2013) - Do You Want to Build a S |  | 16 | 10 | 12 | 3/1/0/0 | 3514723 | 1 | 4 | 3 |  | no reference | 35805385 | passes | no | yes |
| picks | 0 | 9tcaM06eGrY | Frozen (2013) - In Summer (Sing-Along) |  | 13 | 8 | 8 | 2/0/0/3 | 3630452 | 0 | 11 | 3 |  | no reference | 36231531 | passes | no | yes |
| caption | 0 | YVVTZgwYwVo | Frozen (2013) - Let It Go |  | 9 | 9 | 2 | 7/0/0/0 | 15035688 | 0 | 3 | 1 | 1 | none |  |  |  | yes |
| picks | 0 | kQDw88hEr2c | Frozen (2013) - Love Is an Open Door (Si |  | 18 | 10 | 18 | 0/0/0/0 | 14494965 | 0 | 2 | 7 |  | no reference | 32050687 | passes | yes | no |
| joint | 1 | lQlIhraqL7o | I Just Had Sex (feat. Akon) |  | 20 | 10 | 20 | 0/0/0/0 | 11579404 | 0 | 7 | 5 |  | no reference | 13910631 | passes | no | yes |
| joint | 1 | mzhv_dg_UBA | Idina Menzel, AURORA - Into the Unknown  |  | 20 | 7 | 16 | 1/1/0/2 | 36372778 | 0 | 2 | 10 |  | no reference | 31283528 | passes | yes | yes |
| joint | 1 | nrZxwPwmgrw | Idina Menzel, Evan Rachel Wood - Show Yo |  | 19 | 10 | 0 | 0/0/0/19 |  |  |  |  |  |  | 16764056 | unclaimed |  |  |
| joint | 1 | vpMI8Qu5fsc | Ingrid Michaelson 'Be OK' (Official Vide |  | 19 | 11 | 3 | 2/14/0/0 | 326004 | 0 | 5 | 2 |  | no reference | 29819320 | speed | no | yes |
| picks | 0 | Vh74KE3o4Bs | Ingrid Michaelson - The Way I Am |  | 19 | 6 | 18 | 1/0/0/0 | 1781541 | 0 | 1 | 8 |  | no reference | 3161577 | passes | no | yes |
| picks | 0 | XdEN1b-dwlw | Ingrid Michaelson - You and I |  | 16 | 5 | 14 | 0/2/0/0 | 10035896 | 0 | 3 | 11 |  | no reference | 29026140 | passes | yes | no |
| joint | 1 | GI6CfKcMhjY | Jack Sparrow (feat. Michael Bolton) |  | 19 | 6 | 16 | 3/0/0/0 | 22000139 | 0 | 5 | 7 |  | no reference | 20031525 | passes | yes | yes |
| joint | 0 | DYptgVvkVLQ | Jay Chou 周杰倫 - 晴天 (Sunny Day) |  | 19 | 3 | 0 | 19/0/0/0 |  |  |  |  |  |  | 22847808 | no_fit |  |  |
| caption | 0 | RPWDeLqsN0g | Jay Chou 周杰倫 - 龍捲風 (Tornado) |  | 2 | 2 | 0 | 2/0/0/0 |  |  |  |  | 0 |  |  |  |  |  |
| joint | 1 | X-NH1uUfr0U | Jessica Darrow - Surface Pressure (From  |  | 20 | 12 | 0 | 4/0/0/16 |  |  |  |  |  |  | 2261532 | unclaimed |  |  |
| picks | 0 | UJtB55MaoD0 | Jessie J - Domino |  | 18 | 9 | 15 | 2/1/0/0 | 28220836 | 0 | 2 | 8 |  | no reference | 37465712 | passes | no | yes |
| joint | 1 | DzwkcbTQ7ZE | Jessie J - Flashlight (from Pitch Perfec |  | 19 | 10 | 11 | 0/1/5/2 | 37730119 | 0 | 3 | 3 |  | no reference | 9244184 | mistimed | no | yes |
| joint | 1 | qMxX-QOV9tI | Jessie J - Price Tag ft. B.o.B |  | 19 | 12 | 10 | 1/0/8/0 | 6900889 | 0 | 6 | 2 |  | no reference | 6900889 | passes | yes | yes |
| caption | 0 | 450p7goxZqg | John Legend - All of Me |  | 19 | 12 | 19 | 0/0/0/0 | 22517354 | 0 | 1 | 6 | 1 | none |  |  |  | yes |
| joint | 1 | _8jNbZIsBQU | Jonathan Groff - Lost in the Woods (From |  | 20 | 5 | 0 | 0/0/0/20 |  |  |  |  |  |  | 23363506 | unclaimed |  |  |
| caption | 0 | Z3x9i7njCCo | Jung Kook 정국 - 3D (feat. Jack Harlow) (L |  | 20 | 12 | 8 | 9/0/3/0 | 8987220 | 0 | 6 | 4 | 1 | none |  |  |  | yes |
| picks | 0 | 1QYBiNRu1ok | Jung Kook 정국 - Seven (feat. Latto) |  | 20 | 13 | 18 | 0/0/2/0 | 31432999 | 0 | 4 | 4 |  | no reference | 33562631 | passes | no | yes |
| caption | 0 | 6q0JnftlH-I | Jung Kook 정국 - Standing Next to You |  | 18 | 10 | 0 | 0/1/17/0 |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | FQ3slUz7Jo8 | Justin Timberlake - Like I Love You |  | 19 | 7 | 17 | 1/0/0/1 | 19983370 | 0 | 4 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | uuZE_IRwLNI | Justin Timberlake - Mirrors |  | 20 | 7 | 0 | 0/0/1/19 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | TSVHoHyErBQ | Justin Timberlake - Rock Your Body |  | 20 | 8 | 0 | 0/0/17/3 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | je0roKRn3nY | Justin Timberlake - Selfish |  | 20 | 9 | 20 | 0/0/0/0 | 5659554 | 0 | 2 | 8 | 1 | none |  |  |  | yes |
| caption | 0 | IsUsVbTj2AY | Justin Timberlake - Suit & Tie (feat. JA |  | 15 | 10 | 13 | 1/0/1/0 | 30120287 | 0 | 11 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | KPop Demon Hunters (2025) - Free | KPop Demon Hunters (2025) - Free |  | 17 | 10 | 0 | 4/0/0/13 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | yebNIHKAC4A | KPop Demon Hunters (2025) - Golden |  | 14 | 8 | 4 | 5/4/0/1 | 23163059 | 0 | 8 | 3 |  | no reference | 31005537 | passes | no | yes |
| caption | 0 | KPop Demon Hunters (2025) - How It's Done | KPop Demon Hunters (2025) - How It's Don |  | 14 | 7 | 0 | 0/0/0/14 |  |  |  |  | 1 |  |  |  |  |  |
| joint | 0 | 983bBbJx0Mk | KPop Demon Hunters (2025) - Soda Pop |  | 19 | 8 | 0 | 19/0/0/0 |  |  |  |  |  |  | 36713302 | no_fit |  |  |
| picks | 0 | j5itLHDMJsE | KPop Demon Hunters (2025) - Takedown |  | 20 | 8 | 19 | 0/1/0/0 | 30356707 | 0 | 8 | 3 |  | no reference | 22746532 | passes | no | yes |
| caption | 0 | KPop Demon Hunters (2025) - What It Sounds Like | KPop Demon Hunters (2025) - What It Soun |  | 15 | 7 | 0 | 0/15/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | fGyTN5UjnL4 | KPop Demon Hunters (2025) - Your Idol |  | 18 | 9 | 16 | 1/0/1/0 | 23310716 | 1 | 8 | 4 |  | no reference | 37123328 | passes | no | yes |
| caption | 0 | Ra-Om7UMSJc | Kelly Clarkson - Because Of You |  | 19 | 8 | 15 | 0/4/0/0 | 18765707 | 0 | 2 | 9 | 1 | none |  |  |  | yes |
| joint | 1 | ZrX1XKtShSI | Kristen Bell, Idina Menzel - For the Fir |  | 20 | 7 | 18 | 2/0/0/0 | 14589928 | 0 | 2 | 7 |  | no reference | 7840239 | passes | yes | yes |
| caption | 0 | zABLecsR5UE | Lewis Capaldi - Someone You Loved |  | 20 | 13 | 19 | 0/1/0/0 | 27564454 | 0 | 4 | 4 | 1 | none |  |  |  | yes |
| joint | 1 | ILRs2r6lcHY | Mandy Moore, Zachary Levi - I See the Li |  | 20 | 8 | 0 | 20/0/0/0 |  |  |  |  |  |  | 34228750 | no_fit |  |  |
| joint | 1 | HLCasyAh7ic | Michelle Branch - Everywhere [Official M |  | 17 | 8 | 14 | 3/0/0/0 | 19297649 | 0 | 6 | 8 |  | no reference | 30723998 | passes | yes | yes |
| caption | 0 | cPAbx5kgCJo | Moana (2016) - How Far I'll Go |  | 14 | 13 | 2 | 11/0/0/1 | 3292118 | 0 | 2 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | 93lrosBEW-Q | Moana (2016) - Shiny |  | 13 | 7 | 0 | 1/0/11/1 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 79DijItQXMM | Moana (2016) - You're Welcome |  | 5 | 4 | 0 | 1/0/0/4 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | -fxh7jAJR8U | NSYNC - (God Must Have Spent) A Little M |  | 20 | 13 | 4 | 1/8/7/0 | 28155617 | 0 | 11 | 3 | 1 | ref_unclaimed |  |  |  | yes |
| caption | 0 | Eo-KmOd3i7s | NSYNC - Bye Bye Bye |  | 20 | 13 | 0 | 13/2/0/5 |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | saxnXiBKEaY | NSYNC - Girlfriend |  | 18 | 9 | 0 | 0/0/17/1 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | IbRwSI8yi1o | NSYNC - Gone |  | 20 | 12 | 15 | 4/0/0/1 | 32643931 | 0 | 7 | 4 | 1 | none |  |  |  | yes |
| joint | 1 | n-2C2wOFavc | NSYNC - I Want You Back (US Version - Of |  | 16 | 9 | 2 | 1/0/0/13 | 6955667 | 0 | 3 | 1 |  | no reference | 32016974 | unclaimed | no | yes |
| caption | 0 | GQMlWwIXg3M | NSYNC - It's Gonna Be Me |  | 20 | 14 | 20 | 0/0/0/0 | 13572204 | 0 | 5 | 4 | 1 | none |  |  |  | yes |
| picks | 0 | NSYNC - Paradise | NSYNC - Paradise |  | 18 | 5 | 18 | 0/0/0/0 | 9488086 | 1 | 6 | 9 |  | no reference | 27903107 | passes | yes | no |
| caption | 0 | TWZKw_MgUPI | NSYNC - Pop |  | 20 | 12 | 0 | 0/0/20/0 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | PodgxWsZw9s | NSYNC - Thinking Of You (I Drive Myself  |  | 20 | 9 | 0 | 0/7/0/13 |  |  |  |  |  |  | 36176943 | unclaimed |  |  |
| caption | 0 | 6thmPrTxBtI | NSYNC - This I Promise You |  | 20 | 10 | 8 | 3/2/7/0 | 23889061 | 0 | 5 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | atz_aZA3rf0 | Ne-Yo - Because Of You |  | 20 | 9 | 0 | 0/2/4/14 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | k6M5C-oKw9k | Ne-Yo - Miss Independent |  | 20 | 10 | 0 | 0/0/0/20 |  |  |  |  |  |  | 12997477 | unclaimed |  |  |
| caption | 0 | 6tpl9LtkRRw | Ne-Yo - One In A Million |  | 20 | 9 | 0 | 0/0/7/13 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | IxszlJppRQI | Ne-Yo - So Sick |  | 18 | 11 | 14 | 0/2/2/0 | 16652439 | 0 | 7 | 3 | 1 | none |  |  |  | yes |
| picks | 0 | 9ThO76peOw0 | Pocahontas (1995) - Colors of the Wind |  | 11 | 6 | 1 | 6/4/0/0 | 34484694 | 0 | 4 | 1 |  | no reference | 35708272 | passes | no | yes |
| caption | 0 | fJ9rUzIMcZQ | Queen - Bohemian Rhapsody |  | 19 | 12 | 17 | 0/0/2/0 | 21655132 | 0 | 7 | 8 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Another Day | Rent (2005) - Another Day |  | 12 | 5 | 9 | 0/3/0/0 | 6156119 | 0 | 9 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - I Should Tell You | Rent (2005) - I Should Tell You |  | 20 | 7 | 15 | 1/4/0/0 | 6191521 | 0 | 3 | 10 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - I'll Cover You | Rent (2005) - I'll Cover You |  | 17 | 4 | 14 | 3/0/0/0 | 6191556 | 0 | 3 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Light My Candle | Rent (2005) - Light My Candle |  | 15 | 5 | 3 | 0/0/0/12 | 36678024 | 0 | 4 | 2 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - One Song Glory | Rent (2005) - One Song Glory |  | 20 | 6 | 17 | 0/3/0/0 | 6932651 | 0 | 3 | 15 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Out Tonight | Rent (2005) - Out Tonight |  | 20 | 6 | 14 | 0/6/0/0 | 6932715 | 0 | 5 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Santa Fe | Rent (2005) - Santa Fe |  | 20 | 7 | 0 | 6/0/4/10 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Rent (2005) - Seasons of Love | Rent (2005) - Seasons of Love |  | 12 | 7 | 10 | 0/0/0/2 | 36786874 | 0 | 6 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Today 4 U | Rent (2005) - Today 4 U |  | 4 | 2 | 0 | 0/0/0/4 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Rent (2005) - What You Own | Rent (2005) - What You Own |  | 14 | 5 | 5 | 0/9/0/0 | 28181941 | 0 | 2 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Without You | Rent (2005) - Without You |  | 17 | 7 | 12 | 0/5/0/0 | 6934735 | 1 | 2 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Your Eyes | Rent (2005) - Your Eyes |  | 19 | 8 | 9 | 0/10/0/0 | 21412032 | 0 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | WB9_sf6oV1o | S Club 7 - Never Had A Dream Come True |  | 20 | 8 | 20 | 0/0/0/0 | 32607617 | 0 | 2 | 11 | 1 | none |  |  |  | yes |
| joint | 1 | rEXhAMtbaec | Sara Bareilles - Gravity (Official HD Vi |  | 19 | 8 | 13 | 1/5/0/0 | 36844599 | 0 | 4 | 8 |  | no reference | 29516072 | passes | yes | yes |
| joint | 1 | eR7-AUmiNcA | Sara Bareilles - King of Anything (Offic |  | 19 | 5 | 0 | 0/0/0/19 |  |  |  |  |  |  | 7856460 | unclaimed |  |  |
| picks | 0 | 53GIADHxVzM | Sara Bareilles - She Used To Be Mine |  | 19 | 9 | 14 | 1/4/0/0 | 12564402 | 0 | 3 | 6 |  | no reference | 9845205 | passes | no | yes |
| picks | 0 | wIyNAsmGrl0 | Silk Sonic (Bruno Mars & Anderson .Paak) |  | 20 | 12 | 0 | 1/0/5/14 |  |  |  |  |  |  | 1952973 | unclaimed |  |  |
| picks | 0 | CEw-7cMnBDY | Silk Sonic (Bruno Mars & Anderson .Paak) |  | 20 | 8 | 20 | 0/0/0/0 | 11390531 | 0 | 7 | 8 |  | no reference | 14315468 | passes | yes | no |
| picks | 0 | kRXmAIHYQR4 | Tangled (2010) - When Will My Life Begin |  | 18 | 10 | 18 | 0/0/0/0 | 24795512 | 0 | 2 | 3 |  | no reference | 13183578 | passes | no | yes |
| joint | 1 | zi5Z6rNU9Hw | Tangled - Cast - I've Got a Dream (From  |  | 20 | 8 | 17 | 0/3/0/0 | 29290799 | 0 | 4 | 5 |  | no reference | 29201073 | passes | no | yes |
| caption | 0 | _lK4cX5xGiQ | Tenacious D - Tribute |  | 20 | 5 | 0 | 0/0/0/20 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - A Miracle Would Happen & When You Come Home to Me | The Last Five Years (2014) - A Miracle W |  | 9 | 4 | 0 | 2/0/7/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - A Summer in Ohio | The Last Five Years (2014) - A Summer in |  | 10 | 5 | 2 | 0/5/3/0 | 23648746 | 0 | 10 | 2 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - Climbing Uphill | The Last Five Years (2014) - Climbing Up |  | 15 | 4 | 0 | 7/3/5/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Goodbye Until Tomorrow & I Could Never Rescue You | The Last Five Years (2014) - Goodbye Unt |  | 9 | 5 | 0 | 4/0/5/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - I Can Do Better Than That | The Last Five Years (2014) - I Can Do Be |  | 12 | 5 | 6 | 0/6/0/0 | 4179244 | 0 | 10 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - I'm a Part of That | The Last Five Years (2014) - I'm a Part  |  | 0 | 0 | 0 | 0/0/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - If I Didn't Believe in You | The Last Five Years (2014) - If I Didn't |  | 10 | 5 | 0 | 1/3/0/6 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Moving Too Fast | The Last Five Years (2014) - Moving Too  |  | 11 | 5 | 0 | 7/0/4/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Nobody Needs to Know | The Last Five Years (2014) - Nobody Need |  | 16 | 5 | 7 | 6/3/0/0 | 4626353 | 1 | 4 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - See I'm Smiling | The Last Five Years (2014) - See I'm Smi |  | 19 | 9 | 0 | 19/0/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Shiksa Goddess | The Last Five Years (2014) - Shiksa Godd |  | 11 | 5 | 0 | 5/0/6/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Still Hurting | The Last Five Years (2014) - Still Hurti |  | 17 | 8 | 6 | 3/8/0/0 | 4188091 | 0 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - The Next Ten Minutes | The Last Five Years (2014) - The Next Te |  | 17 | 6 | 8 | 3/6/0/0 | 4189082 | 0 | 6 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - The Schmuel Song | The Last Five Years (2014) - The Schmuel |  | 13 | 6 | 0 | 4/1/3/5 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | GibiNy4d4gc | The Lion King (1994) - Circle of Life |  | 9 | 6 | 0 | 1/4/0/4 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | SXKlJuO07eM | The Little Mermaid (1989) - Part of Your |  | 14 | 10 | 2 | 10/2/0/0 | 30097702 | 0 | 2 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | GC_mV1IpjWA | The Little Mermaid (1989) - Under the Se |  | 17 | 8 | 0 | 3/14/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| joint | 0 | kHwpS0LakeU | The Lonely Island - Here I Go (feat. Cha |  | 0 | 0 | 0 | 0/0/0/0 |  |  |  |  |  |  |  |  |  |  |
| joint | 1 | avaSdC0QOUM | The Lonely Island - I'm On A Boat (Expli |  | 20 | 7 | 0 | 0/0/0/20 |  |  |  |  |  |  | 36394001 | unclaimed |  |  |
| picks | 0 | 68LBPvFhMx0 | The Lonely Island - Jose & Mark |  | 5 | 2 | 5 | 0/0/0/0 | 2554162 | 0 | 5 | 4 |  | no reference | 17370761 | passes | no | yes |
| picks | 0 | hj4e709GYf4 | The Lonely Island - Let's Bash |  | 7 | 1 | 7 | 0/0/0/0 | 1116686 | 0 | 3 | 7 |  | no reference | 17273734 | passes | yes | no |
| picks | 0 | gAYL5H46QnQ | The Lonely Island - Threw It On The Grou |  | 20 | 10 | 20 | 0/0/0/0 | 35338143 | 0 | 2 | 6 |  | no reference | 39765748 | passes | no | yes |
| picks | 0 | XzbHPqULtdA | The Outsiders (2024) - Stay Gold |  | 13 | 7 | 4 | 9/0/0/0 | 27305964 | 0 | 2 | 4 |  | no reference | 34445486 | passes | yes | no |
| caption | 0 | EUW0eDhKoxw | The Philosopher Kings - Cry |  | 5 | 1 | 5 | 0/0/0/0 | 28361150 | 0 | 9 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | 6X4bhT1FWjI | The Philosopher Kings - Hurts To Love Yo |  | 4 | 2 | 0 | 4/0/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | AI7F8qlN44E | The Philosopher Kings - You Don't Love M |  | 6 | 2 | 0 | 0/0/0/6 |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | tz_NxOF7RB4 | Vitamin C - Graduation (Friends Forever) |  | 20 | 7 | 1 | 2/0/17/0 | 9980085 | 1 | 10 | 1 |  | no reference | 9980085 | passes | yes | no |
| joint | 1 | vKPGxGCFgTs | Westlife - Flying Without Wings (Officia |  | 20 | 9 | 17 | 0/3/0/0 | 1512603 | 0 | 3 | 8 |  | no reference | 7834744 | passes | no | yes |
| joint | 1 | RTWhvp_OD6s | Where You Are (From 'Moana'_Sing-Along) |  | 20 | 6 | 20 | 0/0/0/0 | 28421947 | 0 | 10 | 7 |  | no reference | 4490148 | passes | no | yes |
| caption | 0 | 3JWTaaS7LdU | Whitney Houston - I Will Always Love You |  | 20 | 9 | 11 | 4/5/0/0 | 29741730 | 0 | 1 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | TZ0pXUb5jVU | Wicked (2003) - For Good |  | 17 | 6 | 0 | 8/9/0/0 |  |  |  |  | 1 |  |  |  |  |  |
| joint | 1 | z5Otla5157c | YOLO (feat. Adam Levine & Kendrick Lamar |  | 19 | 10 | 19 | 0/0/0/0 | 1019299 | 0 | 6 | 5 |  | no reference | 17904967 | passes | no | yes |
| caption | 0 | rg_zwK_sSEY | ZAYN & Zhavia Ward - A Whole New World ( |  | 20 | 9 | 20 | 0/0/0/0 | 7428207 | 0 | 9 | 5 | 1 | none |  |  |  | yes |

### Table K: GATE M LRC-wrong records

| youtube_id | lrclib_id | Source | In_pool | Status | Speed | Mistimed | Unclaimed | Refusal | Picked | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| GZXHBgjQjNM | 20242140 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 21912586 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 27023721 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 31535578 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 32140003 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 35793714 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 36228137 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| AJWtLf4-WWs | 6800151 | pool | yes | fits | 1.0000 | 1 | 14 | unclaimed | no |  |
| AJWtLf4-WWs | 28307055 | pool | yes | fits | 1.0000 | 1 | 14 | unclaimed | no |  |
| AJWtLf4-WWs | 34352818 | pool | yes | fits | 1.0000 | 1 | 14 | unclaimed | no |  |
| UAWcs5H-qgQ | 12572148 | pool | yes | fits | 1.0000 | 0 | 89 | unclaimed | no |  |
| T6wbugWrfLU | 35468507 | pool | yes | fits | 1.0000 | 0 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 3458703 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 6335685 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 7720552 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 9641374 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 12149023 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 12377831 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 12515974 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 15413449 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 17099666 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 20411476 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 23305471 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 24586049 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 24809544 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 31956521 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 32182355 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 32691192 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 33133897 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 34902348 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |

### Table X: flagged passing records not picked

| Song | youtube_id | Ids of the timing | Flags | Mistimed | Unclaimed |
|---|---|---|---|---|---|
| Backstreet Boys - Drowning | GZXHBgjQjNM | 19447935, 26104541 | ref_shift | 0 | 6 |
| Backstreet Boys - Drowning | GZXHBgjQjNM | 20242140, 21912586, 27023721, 31535578, 32140003, 35793714, 36228137 | ref_mistimed | 1 | 6 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 3654026 | ref_unclaimed | 0 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 10249637 | ref_unclaimed | 0 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 13474015 | ref_unclaimed | 0 | 8 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 13609412, 33966854 | ref_mistimed ref_unclaimed | 1 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 13641580 | ref_unclaimed | 0 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 22381484, 34452636, 35231491, 36285083 | ref_unclaimed | 0 | 5 |
| Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 36673394 | ref_unclaimed | 0 | 8 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 3742260 | ref_mistimed | 0 | 3 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 13013886, 15818656, 17214765 | ref_mistimed | 0 | 3 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 21931798 | ref_mistimed | 0 | 3 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 24678599 | ref_mistimed | 0 | 3 |
| Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 31572444 | ref_mistimed | 0 | 2 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 2854250 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 6674983, 7260734, 8325988, 9595552 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 8097534 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 10039069 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 10503213 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 12512210 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 23858174 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 32633585, 33790241, 35467074 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Happier | iWZmdoY1aTE | 40073089 | ref_unclaimed | 0 | 6 |
| Ed Sheeran - Perfect | 2Vv-BfVoq4g | 2943073, 36009208 | ref_unheard | 1 | 2 |
| Ed Sheeran - Shape of You | JGwWNGJdvx8 | 38587774 | ref_unclaimed ref_unheard | 0 | 11 |
| Frozen (2013) - Let It Go | YVVTZgwYwVo | 14494777 | ref_mistimed | 1 | 3 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 4830039, 17014461 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 6563397, 29351856 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 14357227 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 16431444 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 28278766, 35648481 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 37912453 | ref_unclaimed | 0 | 11 |
| Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 38381482 | ref_unclaimed | 0 | 11 |
| NSYNC - (God Must Have Spent) A Little M | -fxh7jAJR8U | 39499684 | ref_unclaimed | 0 | 11 |
| Rent (2005) - What You Own | Rent (2005) - What You Own | 14409292, 39413351 | ref_unheard | 0 | 2 |
| The Last Five Years (2014) - The Next Te | The Last Five Years (2014) - The Next Ten Minutes | 13769166, 25808567, 37998862 | ref_unheard | 0 | 2 |

### Table V: songs with a pick at other limits

| Group | Mistimed <= | Songs | Unclaimed <= 8 | Unclaimed <= 10 | Unclaimed <= 12 | Unclaimed <= 15 | Unclaimed <= 20 |
|---|---|---|---|---|---|---|---|
| picks | 0 | 28 | 16 | 17 | 18 | 18 | 19 |
| picks | 1 | 28 | 20 | 22 | 23 | 23 | 24 |
| joint | 0 | 33 | 19 | 21 | 21 | 21 | 23 |
| joint | 1 | 33 | 19 | 21 | 21 | 22 | 24 |
| caption | 0 | 112 | 48 | 51 | 54 | 56 | 60 |
| caption | 1 | 112 | 54 | 58 | 61 | 64 | 69 |
| new | 0 | 29 | 19 | 21 | 21 | 21 | 23 |
| new | 1 | 29 | 19 | 21 | 21 | 22 | 24 |

### Table L: the listen list

| Rank | Group | New | Title | youtube_id | lrclib_id | Why | Listen_file |
|---|---|---|---|---|---|---|---|
| 1 | picks | 0 | Frozen (2013) - In Summer (Sing-Along) | 9tcaM06eGrY | 3630452 | no reference | Frozen (2013) - In Summer (Sing-Along)---9tcaM06eGrY.3630452.srt |
| 2 | joint | 1 | Where You Are (From 'Moana'_Sing-Along) | RTWhvp_OD6s | 28421947 | no reference | Where You Are (From 'Moana'_Sing-Along)---RTWhvp_OD6s.28421947.srt |
| 3 | joint | 1 | Bruno Mars - The Lazy Song (Official Mus | fLexgOxsZu0 | 6706711 | no reference | Bruno Mars - The Lazy Song (Official Music Video)---fLexgOxsZu0.6706711.srt |
| 4 | picks | 0 | Camp Rock (2008) - This Is Me (Sing-Alon | 6HCUoMgviwU | 17015895 | no reference | Camp Rock (2008) - This Is Me (Sing-Along)---6HCUoMgviwU.17015895.srt |
| 5 | picks | 0 | KPop Demon Hunters (2025) - Your Idol | fGyTN5UjnL4 | 23310716 | no reference | KPop Demon Hunters (2025) - Your Idol---fGyTN5UjnL4.23310716.srt |
| 6 | picks | 0 | KPop Demon Hunters (2025) - Takedown | j5itLHDMJsE | 30356707 | no reference | KPop Demon Hunters (2025) - Takedown---j5itLHDMJsE.30356707.srt |
| 7 | picks | 0 | KPop Demon Hunters (2025) - Golden | yebNIHKAC4A | 23163059 | no reference | KPop Demon Hunters (2025) - Golden---yebNIHKAC4A.23163059.srt |
| 8 | joint | 1 | Demi Lovato, Joe Jonas - Wouldn't Change | 62llzl7iKkE | 33991259 | no reference | Demi Lovato, Joe Jonas - Wouldn't Change a Thing (From 'Camp Rock 2 - The Final Jam'_Sing-Along)---62llzl7iKkE.33991259.srt |
| 9 | joint | 1 | Bruno Mars - Just The Way You Are (Offic | LjhCEhWiKXk | 9888181 | no reference | Bruno Mars - Just The Way You Are (Official Music Video)---LjhCEhWiKXk.9888181.srt |
| 10 | joint | 1 | Bruno Mars - Locked Out Of Heaven (Offic | e-fA-gBCkj0 | 6936310 | no reference | Bruno Mars - Locked Out Of Heaven (Official Music Video)---e-fA-gBCkj0.6936310.srt |
| 11 | joint | 1 | Bruno Mars - When I Was Your Man (Offici | ekzHIouo8Q4 | 26614056 | no reference | Bruno Mars - When I Was Your Man (Official Music Video)---ekzHIouo8Q4.26614056.srt |
| 12 | joint | 1 | I Just Had Sex (feat. Akon) | lQlIhraqL7o | 11579404 | no reference | I Just Had Sex (feat. Akon)---lQlIhraqL7o.11579404.srt |
| 13 | joint | 1 | Michelle Branch - Everywhere [Official M | HLCasyAh7ic | 19297649 | no reference | Michelle Branch - Everywhere [Official Music Video]---HLCasyAh7ic.19297649.srt |
| 14 | joint | 1 | Jessie J - Price Tag ft. B.o.B | qMxX-QOV9tI | 6900889 | no reference | Jessie J - Price Tag ft. B.o.B---qMxX-QOV9tI.6900889.srt |
| 15 | joint | 1 | YOLO (feat. Adam Levine & Kendrick Lamar | z5Otla5157c | 1019299 | no reference | YOLO (feat. Adam Levine & Kendrick Lamar)---z5Otla5157c.1019299.srt |
| 16 | picks | 0 | The Lonely Island - Jose & Mark | 68LBPvFhMx0 | 2554162 | no reference | The Lonely Island - Jose & Mark---68LBPvFhMx0.2554162.srt |
| 17 | joint | 1 | Jack Sparrow (feat. Michael Bolton) | GI6CfKcMhjY | 22000139 | no reference | Jack Sparrow (feat. Michael Bolton)---GI6CfKcMhjY.22000139.srt |
| 18 | joint | 1 | Ingrid Michaelson 'Be OK' (Official Vide | vpMI8Qu5fsc | 326004 | no reference | Ingrid Michaelson 'Be OK' (Official Video)---vpMI8Qu5fsc.326004.srt |
| 19 | picks | 0 | Frozen (2013) - Do You Want to Build a S | TeQ_TTyLGMs | 3514723 | no reference | Frozen (2013) - Do You Want to Build a Snowman (Sing-Along)---TeQ_TTyLGMs.3514723.srt |
| 20 | picks | 0 | Jung Kook 정국 - Seven (feat. Latto) | 1QYBiNRu1ok | 31432999 | no reference | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok.31432999.srt |
| 21 | picks | 0 | Pocahontas (1995) - Colors of the Wind | 9ThO76peOw0 | 34484694 | no reference | Pocahontas (1995) - Colors of the Wind---9ThO76peOw0.34484694.srt |
| 22 | joint | 1 | Backstreet Boys - Show Me The Meaning Of | aBt8fN7mJNg | 19923333 | no reference | Backstreet Boys - Show Me The Meaning Of Being Lonely (Official Video)---aBt8fN7mJNg.19923333.srt |
| 23 | joint | 1 | Sara Bareilles - Gravity (Official HD Vi | rEXhAMtbaec | 36844599 | no reference | Sara Bareilles - Gravity (Official HD Video)---rEXhAMtbaec.36844599.srt |
| 24 | joint | 1 | Tangled - Cast - I've Got a Dream (From  | zi5Z6rNU9Hw | 29290799 | no reference | Tangled - Cast - I've Got a Dream (From 'Tangled'_Sing-Along)---zi5Z6rNU9Hw.29290799.srt |
| 25 | picks | 0 | Sara Bareilles - She Used To Be Mine | 53GIADHxVzM | 12564402 | no reference | Sara Bareilles - She Used To Be Mine---53GIADHxVzM.12564402.srt |
| 26 | caption | 0 | Céline Dion - My Heart Will Go On (Titan | 9bFHsd3o1w0 | 22553995 | no reference | Céline Dion - My Heart Will Go On (Titanic, 1997)---9bFHsd3o1w0.22553995.srt |
| 27 | joint | 1 | Jessie J - Flashlight (from Pitch Perfec | DzwkcbTQ7ZE | 37730119 | no reference | Jessie J - Flashlight (from Pitch Perfect 2) (Official Video)---DzwkcbTQ7ZE.37730119.srt |
| 28 | caption | 0 | Céline Dion - I'm Alive (Stuart Little 2 | NJsa6-y4sDs | 28130840 | no reference | Céline Dion - I'm Alive (Stuart Little 2, 2002)---NJsa6-y4sDs.28130840.srt |
| 29 | joint | 1 | NSYNC - I Want You Back (US Version - Of | n-2C2wOFavc | 6955667 | no reference | NSYNC - I Want You Back (US Version - Official Video)---n-2C2wOFavc.6955667.srt |
| 30 | joint | 1 | Westlife - Flying Without Wings (Officia | vKPGxGCFgTs | 1512603 | no reference | Westlife - Flying Without Wings (Official Video)---vKPGxGCFgTs.1512603.srt |
| 31 | joint | 1 | Bruno Mars - Grenade (Official Music Vid | SR6iYWJxHqs | 38953751 | no reference | Bruno Mars - Grenade (Official Music Video)---SR6iYWJxHqs.38953751.srt |
| 32 | picks | 0 | Jessie J - Domino | UJtB55MaoD0 | 28220836 | no reference | Jessie J - Domino---UJtB55MaoD0.28220836.srt |
| 33 | joint | 1 | Kristen Bell, Idina Menzel - For the Fir | ZrX1XKtShSI | 14589928 | no reference | Kristen Bell, Idina Menzel - For the First Time in Forever (From 'Frozen'_Sing-Along)---ZrX1XKtShSI.14589928.srt |
| 34 | picks | 0 | The Lonely Island - Threw It On The Grou | gAYL5H46QnQ | 35338143 | no reference | The Lonely Island - Threw It On The Ground---gAYL5H46QnQ.35338143.srt |
| 35 | picks | 0 | Tangled (2010) - When Will My Life Begin | kRXmAIHYQR4 | 24795512 | no reference | Tangled (2010) - When Will My Life Begin (Sing-Along)---kRXmAIHYQR4.24795512.srt |
| 36 | joint | 1 | Idina Menzel, AURORA - Into the Unknown  | mzhv_dg_UBA | 36372778 | no reference | Idina Menzel, AURORA - Into the Unknown (From 'Frozen 2'_Sing-Along)---mzhv_dg_UBA.36372778.srt |
| 37 | picks | 0 | Ingrid Michaelson - The Way I Am | Vh74KE3o4Bs | 1781541 | no reference | Ingrid Michaelson - The Way I Am---Vh74KE3o4Bs.1781541.srt |
| 38 | caption | 0 | NSYNC - (God Must Have Spent) A Little M | -fxh7jAJR8U | 28155617 | flagged: ref_unclaimed | NSYNC - (God Must Have Spent) A Little More Time On You----fxh7jAJR8U.28155617.srt |
| 39 | caption | 0 | Flight of the Conchords (2007) - Bowie | Flight of the Conchords (2007) - Bowie | 19452078 | flagged: ref_refused | Flight of the Conchords (2007) - Bowie.19452078.srt |
| 40 | caption | 0 | Britney Spears - (You Drive Me) Crazy | Q4VK9_CfOLQ | 2137556 | flagged: ref_mistimed | Britney Spears - (You Drive Me) Crazy---Q4VK9_CfOLQ.2137556.srt |
| 41 | caption | 0 | Backstreet Boys - Drowning | GZXHBgjQjNM | 14595571 | flagged: ref_shift | Backstreet Boys - Drowning---GZXHBgjQjNM.14595571.srt |
| 42 | caption | 0 | Ed Sheeran - Happier | iWZmdoY1aTE | 29277988 | flagged: ref_unclaimed | Ed Sheeran - Happier---iWZmdoY1aTE.29277988.srt |
| 43 | caption | 0 | Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 1124886 | flagged: ref_unclaimed | Backstreet Boys - Get Down (You're The One For Me)---0LSYuZRSGcY.1124886.srt |
| 44 | caption | 0 | Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 685756 | flagged: ref_mistimed | Christina Aguilera - Reflection (Mulan, 2020)---RNprQYHenNI.685756.srt |
| 45 | caption | 0 | Colbie Caillat - Realize | GlZxZ2n2zpw | 37946467 | unflagged | Colbie Caillat - Realize---GlZxZ2n2zpw.37946467.srt |
| 46 | caption | 0 | Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 30120287 | unflagged | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY.30120287.srt |
| 47 | caption | 0 | The Last Five Years (2014) - A Summer in | The Last Five Years (2014) - A Summer in Ohio | 23648746 | unflagged | The Last Five Years (2014) - A Summer in Ohio.23648746.srt |
| 48 | caption | 0 | The Last Five Years (2014) - I Can Do Be | The Last Five Years (2014) - I Can Do Better Than That | 4179244 | unflagged | The Last Five Years (2014) - I Can Do Better Than That.4179244.srt |
| 49 | caption | 0 | The Philosopher Kings - Cry | EUW0eDhKoxw | 28361150 | unflagged | The Philosopher Kings - Cry---EUW0eDhKoxw.28361150.srt |
| 50 | caption | 0 | Rent (2005) - Another Day | Rent (2005) - Another Day | 6156119 | unflagged | Rent (2005) - Another Day.6156119.srt |
| 51 | caption | 0 | ZAYN & Zhavia Ward - A Whole New World ( | rg_zwK_sSEY | 7428207 | unflagged | ZAYN & Zhavia Ward - A Whole New World (End Title) (Aladdin, 2019)---rg_zwK_sSEY.7428207.srt |
| 52 | caption | 0 | Backstreet Boys - As Long As You Love Me | 0Gl2QnHNpkA | 3722851 | unflagged | Backstreet Boys - As Long As You Love Me---0Gl2QnHNpkA.3722851.srt |
| 53 | caption | 0 | NSYNC - Gone | IbRwSI8yi1o | 32643931 | unflagged | NSYNC - Gone---IbRwSI8yi1o.32643931.srt |
| 54 | caption | 0 | Ne-Yo - So Sick | IxszlJppRQI | 16652439 | unflagged | Ne-Yo - So Sick---IxszlJppRQI.16652439.srt |
| 55 | caption | 0 | BTS 방탄소년단 - Butter | WMweEpGlu_U | 32156281 | unflagged | BTS 방탄소년단 - Butter---WMweEpGlu_U.32156281.srt |
| 56 | caption | 0 | Queen - Bohemian Rhapsody | fJ9rUzIMcZQ | 21655132 | unflagged | Queen - Bohemian Rhapsody---fJ9rUzIMcZQ.21655132.srt |
| 57 | caption | 0 | Backstreet Boys - I Want It That Way | 4fndeDfaWCg | 11268019 | unflagged | Backstreet Boys - I Want It That Way---4fndeDfaWCg.11268019.srt |
| 58 | caption | 0 | Ed Sheeran - Shape of You | JGwWNGJdvx8 | 22081383 | unflagged | Ed Sheeran - Shape of You---JGwWNGJdvx8.22081383.srt |
| 59 | caption | 0 | Backstreet Boys - Shape Of My Heart | OT5msu-dap8 | 22503174 | unflagged | Backstreet Boys - Shape Of My Heart---OT5msu-dap8.22503174.srt |
| 60 | caption | 0 | Rent (2005) - Seasons of Love | Rent (2005) - Seasons of Love | 36786874 | unflagged | Rent (2005) - Seasons of Love.36786874.srt |
| 61 | caption | 0 | The Last Five Years (2014) - The Next Te | The Last Five Years (2014) - The Next Ten Minutes | 4189082 | unflagged | The Last Five Years (2014) - The Next Ten Minutes.4189082.srt |
| 62 | caption | 0 | Jung Kook 정국 - 3D (feat. Jack Harlow) (L | Z3x9i7njCCo | 8987220 | unflagged | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo.8987220.srt |
| 63 | caption | 0 | Backstreet Boys - Inconsolable | qGDF_QcsKVI | 35522789 | unflagged | Backstreet Boys - Inconsolable---qGDF_QcsKVI.35522789.srt |
| 64 | caption | 0 | NSYNC - This I Promise You | 6thmPrTxBtI | 23889061 | unflagged | NSYNC - This I Promise You---6thmPrTxBtI.23889061.srt |
| 65 | caption | 0 | NSYNC - It's Gonna Be Me | GQMlWwIXg3M | 13572204 | unflagged | NSYNC - It's Gonna Be Me---GQMlWwIXg3M.13572204.srt |
| 66 | caption | 0 | Rent (2005) - Out Tonight | Rent (2005) - Out Tonight | 6932715 | unflagged | Rent (2005) - Out Tonight.6932715.srt |
| 67 | caption | 0 | Backstreet Boys - Quit Playing Games (Wi | Ug88HO2mg44 | 33413907 | unflagged | Backstreet Boys - Quit Playing Games (With My Heart)---Ug88HO2mg44.33413907.srt |
| 68 | caption | 0 | Ariana Grande & John Legend - Beauty and | axySrE0Kg6k | 31988497 | unflagged | Ariana Grande & John Legend - Beauty and the Beast (Beauty and the Beast, 2017)---axySrE0Kg6k.31988497.srt |
| 69 | caption | 0 | The Last Five Years (2014) - Nobody Need | The Last Five Years (2014) - Nobody Needs to Know | 4626353 | unflagged | The Last Five Years (2014) - Nobody Needs to Know.4626353.srt |
| 70 | caption | 0 | Backstreet Boys - Incomplete | WVe80iZtlYU | 19180415 | unflagged | Backstreet Boys - Incomplete---WVe80iZtlYU.19180415.srt |
| 71 | caption | 0 | Backstreet Boys - More Than That | 1OwfYjemrYw | 36314729 | unflagged | Backstreet Boys - More Than That---1OwfYjemrYw.36314729.srt |
| 72 | caption | 0 | Britney Spears - ...Baby One More Time | C-u5WLJ9Yk4 | 32110280 | unflagged | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4.32110280.srt |
| 73 | caption | 0 | Justin Timberlake - Like I Love You | FQ3slUz7Jo8 | 19983370 | unflagged | Justin Timberlake - Like I Love You---FQ3slUz7Jo8.19983370.srt |
| 74 | caption | 0 | Rent (2005) - Light My Candle | Rent (2005) - Light My Candle | 36678024 | unflagged | Rent (2005) - Light My Candle.36678024.srt |
| 75 | caption | 0 | Lewis Capaldi - Someone You Loved | zABLecsR5UE | 27564454 | unflagged | Lewis Capaldi - Someone You Loved---zABLecsR5UE.27564454.srt |
| 76 | caption | 0 | Ed Sheeran - Thinking Out Loud | lp-EO5I60KA | 20756048 | unflagged | Ed Sheeran - Thinking Out Loud---lp-EO5I60KA.20756048.srt |
| 77 | caption | 0 | Rent (2005) - I Should Tell You | Rent (2005) - I Should Tell You | 6191521 | unflagged | Rent (2005) - I Should Tell You.6191521.srt |
| 78 | caption | 0 | Rent (2005) - I'll Cover You | Rent (2005) - I'll Cover You | 6191556 | unflagged | Rent (2005) - I'll Cover You.6191556.srt |
| 79 | caption | 0 | Rent (2005) - One Song Glory | Rent (2005) - One Song Glory | 6932651 | unflagged | Rent (2005) - One Song Glory.6932651.srt |
| 80 | caption | 0 | Ed Sheeran - The A Team | UAWcs5H-qgQ | 19121007 | unflagged | Ed Sheeran - The A Team---UAWcs5H-qgQ.19121007.srt |
| 81 | caption | 0 | Frozen (2013) - Let It Go | YVVTZgwYwVo | 15035688 | unflagged | Frozen (2013) - Let It Go---YVVTZgwYwVo.15035688.srt |
| 82 | caption | 0 | Aladdin (2019) - Speechless | mw5VIEIvuMI | 19793188 | unflagged | Aladdin (2019) - Speechless---mw5VIEIvuMI.19793188.srt |
| 83 | caption | 0 | Ed Sheeran - Perfect | 2Vv-BfVoq4g | 19853882 | unflagged | Ed Sheeran - Perfect---2Vv-BfVoq4g.19853882.srt |
| 84 | caption | 0 | Rent (2005) - Without You | Rent (2005) - Without You | 6934735 | unflagged | Rent (2005) - Without You.6934735.srt |
| 85 | caption | 0 | Ed Sheeran - Castle On The Hill | K0ibBPhiaG0 | 23335586 | unflagged | Ed Sheeran - Castle On The Hill---K0ibBPhiaG0.23335586.srt |
| 86 | caption | 0 | Kelly Clarkson - Because Of You | Ra-Om7UMSJc | 18765707 | unflagged | Kelly Clarkson - Because Of You---Ra-Om7UMSJc.18765707.srt |
| 87 | caption | 0 | Rent (2005) - What You Own | Rent (2005) - What You Own | 28181941 | unflagged | Rent (2005) - What You Own.28181941.srt |
| 88 | caption | 0 | The Little Mermaid (1989) - Part of Your | SXKlJuO07eM | 30097702 | unflagged | The Little Mermaid (1989) - Part of Your World---SXKlJuO07eM.30097702.srt |
| 89 | caption | 0 | S Club 7 - Never Had A Dream Come True | WB9_sf6oV1o | 32607617 | unflagged | S Club 7 - Never Had A Dream Come True---WB9_sf6oV1o.32607617.srt |
| 90 | caption | 0 | Moana (2016) - How Far I'll Go | cPAbx5kgCJo | 3292118 | unflagged | Moana (2016) - How Far I'll Go---cPAbx5kgCJo.3292118.srt |
| 91 | caption | 0 | Adele - Someone Like You | hLQl3WQQoQ0 | 23116607 | unflagged | Adele - Someone Like You---hLQl3WQQoQ0.23116607.srt |
| 92 | caption | 0 | Justin Timberlake - Selfish | je0roKRn3nY | 5659554 | unflagged | Justin Timberlake - Selfish---je0roKRn3nY.5659554.srt |
| 93 | caption | 0 | Whitney Houston - I Will Always Love You | 3JWTaaS7LdU | 29741730 | unflagged | Whitney Houston - I Will Always Love You (The Bodyguard, 1992)---3JWTaaS7LdU.29741730.srt |
| 94 | caption | 0 | John Legend - All of Me | 450p7goxZqg | 22517354 | unflagged | John Legend - All of Me---450p7goxZqg.22517354.srt |
| 95 | caption | 0 | Rent (2005) - Your Eyes | Rent (2005) - Your Eyes | 21412032 | unflagged | Rent (2005) - Your Eyes.21412032.srt |
| 96 | caption | 0 | The Last Five Years (2014) - Still Hurti | The Last Five Years (2014) - Still Hurting | 4188091 | unflagged | The Last Five Years (2014) - Still Hurting.4188091.srt |
