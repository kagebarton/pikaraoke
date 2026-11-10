Model: Claude Sonnet 5.5 (executor, Phases 1-3). Author: Claude Fable 5.2, 2026-11-10. Judge
at GATE P: Claude Opus 5.5, then Ken. Phases 4-6 are loose and get their spec after the gate.

# LRCLIB timing at download, picked by fit

**Status: PLANNED 2026-11-10. Nothing built, nothing measured under this plan.**

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
17. The holdout is short: twelve songs the author listed (Phase 0), not thirty of Ken's
    choosing.

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
- **Ken adds these twelve songs** with `add_songs` on Windows, taking the Genius pick at each
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

- **How they were chosen** (author, 2026-11-10): artists and kinds of video already among
  Ken's Repair picks (Bruno Mars, The Lonely Island, Jessie J, Disney sing-alongs, Camp Rock,
  2000s pop), found by a YouTube search from the VM, keeping the official or Disney upload
  when it carries no uploader English captions, so the song takes a Genius pick. LRCLIB was
  not consulted for any of them, and must not be before Phase 3 runs.
- Phases 1 and 2 do not wait for this. Phase 3 does.

## Phase 1: the measure, the pick and the probe (Sonnet)

Read-only on the library, GPU-free, on the VM, network for LRCLIB only.

- [ ] **1a. Anchor check.** On branch `lrclib_fit_pick`. Confirm these exist as this plan uses
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

- [ ] **1b. `SliceFit.unclaimed_run`** in `pikaraoke/lib/srt_slice_fit.py`. A new field,
  `int`, 0 unless the status is `fits`, defined as in "The bar and the pick". It is computed in
  `_fit_one_stream` from the second pass's token-to-word assignment and the final speed and
  shift, on the stream that fit used. Share the expected-times loop with `_match_by_time`
  instead of repeating it. Update the `SliceFit` docstring. No caller changes.
  Tests in `tests/unit/test_srt_slice_fit.py`, made-up words: a sheet covering every heard
  word; a sheet missing a middle stretch (the run equals the heard words in it); a sheet that
  stops early (the tail); a word the match takes but more than 5 s from its token's time is
  not claimed; a refused fit gives 0.
  Commit: `feat(lyrics): the LRC fit counts heard words no line claims`.

- [ ] **1c. `pikaraoke/lib/lrc_auto_pick.py`**, new, pure (no I/O). This is the code the
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

- [ ] **1d. `scripts/lrc_fit_pick_probe.py`.** One command:
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

- [ ] **1e. Check the measure against the exploration.** Run the probe on the four GATE M
  songs only, to a scratch folder:
  `python scripts/lrc_fit_pick_probe.py --folder "<library>" --out <scratch> --old-cache
  ~/.pikaraoke/tmp/lrclib_auto_timing/cache --only GZXHBgjQjNM --only AJWtLf4-WWs --only
  UAWcs5H-qgQ --only T6wbugWrfLU`. Table K's unclaimed run must read: 12572148 -> 89;
  35468507 -> 20; 33133897 -> 20; 6800151, 28307055, 34352818 -> 14; 20242140 -> 6. Any other
  value means the measure is not the one explored: STOP and report the values, do not adjust
  anything to match. A record `not found` is not a mismatch; say so.

- [ ] **1f. Self-review and record.** Self-review per CLAUDE.md; 1b and 1c are new logic in
  the fit path, so track them as pending review. Results log row with the three commits and
  the 1e values. Plan-only commit. Stop (checkpoint: `/compact`, review due).

## Phase 2: the library run (Sonnet)

- [ ] **2a. Run.**
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
- [ ] **2b. Record.** Results log row: command, checks, paths. Paste Tables P, S, K, X, V and
  L raw into "Report output: library run". No tallies beyond the script's, no reading of the
  numbers. Plan-only commit.
- [ ] **2c. Stop.** Give Ken, in plain words: where the listen files are and how to use them
  (below), and Table L's first 10 rows as listening session 2. Then the handoff prompt for
  Opus (see "Executor rules"). Do not start Phase 3.

**How Ken judges a pick.** Open the song's video in VLC, add the pick's `.srt` from
`D:\Shared\lrclib-listen` as the subtitle file, and watch: do the lines come up when they are
sung, and is any sung line missing? This shows the LRC's lines at their fitted times, which
is what the route would hand to cue align. It does not show the finished word-by-word
karaoke; that is Phase 6. One verdict per song: right, wrong (where), or unsure.

## Phase 3: the holdout run (Sonnet, after Phase 0)

- [ ] **3a. Preconditions.** A dry look at the library (`library_statuses` against the
  baseline and Phase 0's list): at least 10 of the twelve listed songs are there and in a
  group (they have heard words). Fewer: STOP and tell Ken which are missing. Record how many
  took a Genius pick (`joint`, or `picks` if Ken has since retimed one on Repair) and how
  many timed from a caption after all. Other new songs Ken added meanwhile are measured too
  and marked `new` like these. A new id that is a file stem matching a renamed baseline song:
  STOP and name it.
- [ ] **3b. Run** the 2a command with `--out ~/.pikaraoke/tmp/lrclib_fit_pick_holdout`
  (a fresh cache: LRCLIB as it is that day). Same unavailable and read-only rules.
- [ ] **3c. Record.** As 2b, into "Report output: holdout run", with every table. Plan-only
  commit.
- [ ] **3d. Stop.** Give Ken listening session 3: the `new` rows of Table L, first 10. If
  more than 10 new picks have no reference, say how many sessions that makes. Handoff prompt
  for Opus.

## GATE P (Opus, then Ken)

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
- At 2c and 3d the Opus handoff prompt carries: branch and HEAD, this file's report sections
  and "GATE P", both `<out>` paths, "do not rerun the probe", and that Ken's verdicts arrive
  in chat.

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
| 1 | 2026-11-10 | 0 | Branch `lrclib_fit_pick` off `dev` `37d8d93`. Baseline id list written, read-only on the library (`library_statuses`): 168 songs. Origins: `srt` 112, `lrclib_srt` 28, `movie_srt` 7, `genius`/joint 4, `custom`/joint 3, no bundle 14. | `~/.pikaraoke/tmp/lrclib_fit_pick/baseline_ids.txt`, sha256 `610e84eeee4209473ba33b50d583ea4739d3086c85bf940cde950e5645315eb7`. |
| 2 | 2026-11-10 | 0 | Ken declined a 30-song import and asked for a shorter list picked for him (Decision 17). Twelve songs listed in Phase 0, found with `yt-dlp` searches from the VM (`ytsearch3:` per song, uploader captions read from each result). Control: the search reported the uploader caption on a library caption song (`4fndeDfaWCg`). None of the twelve is in the baseline. LRCLIB not consulted. | List and selection rule in Phase 0. |

## Report output: library run

(Phase 2b.)

## Report output: holdout run

(Phase 3c.)
