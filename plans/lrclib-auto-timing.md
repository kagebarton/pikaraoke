Model: Claude Opus 5.5 (author: loose draft 2026-11-03, Phase 1 spec 2026-11-06). Phase 1
executor: Claude Sonnet 5.5. GATE M goes to Opus, then Ken. Phases 2-4 are still loose and get
specced (Opus) after GATE M.

# LRCLIB auto-timing at download

**Status: Phase 0 DONE, Phase 1 SPECCED (ready for a Sonnet executor), Phases 2-4 loose.**
"Open for the spec" below lists what the Phase 2-4 spec must settle.

## Goal

A newly downloaded song whose LRCLIB match clears a strict fit is timed from that match
automatically (cue align, the LRC's own lines as the sheet), not by the joint matcher.
Today this only happens when Ken picks LRCLIB timing on Repair
(`archive/lyric_source_lists`, landed on `dev` 2026-10-30).

## Decisions (Ken, 2026-11-03)

1. **The LRC's own lyrics are the karaoke words** from the first run, as on Repair.
2. **The download page is unchanged.** The user still picks Genius lyrics. The switch happens
   after the download, once the transcriber has heard the vocal stem. (A pre-download check
   was considered and dropped: the fit needs the transcriber's words, and only YouTube's
   auto-captions exist before download, usable on 14 of 103 library songs.)
3. **New downloads only.** Regenerate, bulk runs and Repair never switch a song. Existing
   joint songs move only through Repair, as today.
4. **Genius picks only.** A song with pasted custom lyrics stays on joint.
5. **Its own lyric source type**, separate from Repair's LRCLIB timing, so Ken can review
   auto-timed songs later. No separate "check me" list.
6. **The label stays** after review. It records how the song got its timing.
7. **Measure first.** No build until the measurement is read.
8. **The bar is set for zero wrong acceptances** on the measurement. If the bar that reaches
   zero lets too few songs through, the feature stops there.

## Why this is not S-1 again

S-1 (the per-song scaffold route) was withdrawn 2026-09-08. Record:
`archive/edge_snap_refine:plans/route-line-timing.md` (status block and closing entry) and
`plans/PROGRAM.md` on the same tag. Its status block says "do not re-open this route with a
per-song gate". Ken lifts that for this feature, on the grounds below. The full spec should
restate them against the record.

| S-1 failure | Now |
|---|---|
| Warp gate fitted a median, so a minority of disagreeing lines (cut verse, extra repeat) never reached it; it accepted 5 of 6 wrong-edit songs | `srt_slice_fit` flags each line: mistimed (heard far from its fitted time) and unheard. A cut verse or extra repeat leaves a mistimed run (GATE A: Popular, Bloodstream ASR) |
| Duration clamp crammed lines past the ends onto one timestamp | Lines outside the clip are dropped (`SliceFit.dropped`) |
| Genius text timed by a foreign source through a line mapping | The LRC's own text is the sheet |
| Route F2 never built | Feeds the shipped cue-align route |
| Source was mostly the Musixmatch/NetEase sidecar, sound on 4 of 17 | LRCLIB, but the pick is still text-first (`lrclib.select_candidate`, length only as a tie-break), so wrong edits still arrive and the fit must catch them |

What has not changed and the bar must answer:

- **Edits at the very start or end show only as unheard.** Flags need lines on both sides of
  a mismatch. On Repair the 15 s gap limit and Ken's ear cover this; here only the bar does.
- **A wrong acceptance is worse than staying joint.** Joint hides lines it can't place; cue
  align renders every line.
- **Small evidence base.** GATE A had 17 songs, about 4 known bad. Best Part Of Me (live take,
  an S-1 wrong-edit song) passes Repair's fit with nothing mistimed; never heard.

## Phase 0: prerequisites -- DONE 2026-11-06 (Opus)

Ken's cue-align work landed as `cue_align_windows` (on `dev` 2026-11-05, `f47f879`..`2e5d389`,
retired as `archive/cue_align_windows`); this branch now sits on `dev` `4497f4d`. What it
changed in `pikaraoke/pipeline/stages/lyric_align.py` (`git diff f627112 4497f4d`):

- `_run_cue_align` returns five values, not three: it also returns the aligned stem's loudness
  envelope (decoded inside the cue route to place the line-rescue windows) and the rescue's
  inputs for the bundle (`cue_inputs`). `run` skips its own envelope decode on the cue route
  and reuses that one for the edge snap.
- The edge snap is passed `doubted_sources={SOURCE_REALIGN}`.
- **Not touched:** the route choice (`if cue_spans:` in `run`) and `_dereverb_gate`.

For Phase 2: the switch still goes before `if cue_spans:`, and both `_run_joint` and
`_run_cue_align` still call `_dereverb_gate` inside, so "run the gate once" stays open. An
auto-timed LRC sheet would go through `cue_align.align_song` and so get the line rescue
(re-aligning lines whose windows look bad) with no extra work; that matters more for an LRC
than for a caption, since an LRC stamps only line starts. Phase 1 does not depend on any of
it.

## Phase 1: measurement -> GATE M (SPEC, Sonnet executor)

### What it answers

For each candidate LRCLIB match of a song we can check, does a fixed-shape bar accept it, and
when it does, is the LRC timed to this video? "Timed to this video" is judged against an
independent reference: the uploader caption, which is timed to our video and is not an input
to the fit (the fit reads the bundle's transcribe words only). GATE M then sets the bar's
thresholds so nothing wrong is accepted, and reports how many songs the bar lets through.

Read-only, GPU-free, on the VM, with network for LRCLIB. Nothing in the library is written.

### Library facts (checked 2026-11-06, `/home/ken/shared-drives/D:/Shared/pikaraoke-songs`, 115 songs)

- Bundle origin `srt` (uploader caption, cue align): 76, one of them edited. 59 bundles hold
  `transcribe_words`; the 17 that don't are The Last Five Years (11), KPop Demon Hunters (3),
  Lewis Capaldi - Someone You Loved, Jung Kook (2). None of the 76 carries a
  `subtitles/<stem>.srt.generated` marker, none has an `.lrc`, 2 have an ASR json3.
- Origin `genius`, method `joint`: 8, all with an `.lrc` match and transcribe words.
- Origin `lrclib_srt` (Ken's Repair picks): 7, all with an `.lrc` match and transcribe words.
- Origin `custom`, joint: 3 (Defying Gravity, Popular, Bloodstream). Popular's `.lrc` is a skip
  marker since 2026-10-29.
- Known-bad LRCs on disk, unchanged since before GATE A's run (2026-10-29):
  - Defying Gravity `AoON1CyhQAM`, LRCLIB id 34563601 (GATE A: refused, +97 s gap).
  - Bloodstream `Orq_75kFi8I`, id 36006882 (GATE A: transcribe refused, ASR flagged runs).
  - Best Part Of Me `wGyh_53ecgg`, id 27081884 (an S-1 wrong-edit song; GATE A: fits at speed
    0.986, nothing mistimed; never heard). Treated as bad here.

### Groups

The executor counts each group from the library; the numbers above are what to expect.

| Group | Rule | Used for |
|---|---|---|
| `ref` | origin `srt`, not edited, bundle has `transcribe_words`, `subtitles/<stem>.srt` exists, no `.srt.generated` beside it | wrong acceptances and coverage |
| `joint` | origin `genius`, method `joint`, `transcribe_words` | coverage on the real target |
| `repair` | origin `lrclib_srt`, `transcribe_words` | coverage on songs Ken already timed from LRCLIB |
| `known` | the three songs above, their on-disk LRC only | must be rejected |

A song in `known` is in that group only (Best Part Of Me is not also in `joint`). A song with no
clip length is skipped with reason `no_length`. Every other song is skipped as `out_of_scope`.

### Settled for the measurement (pre-registered: fixed before any number exists)

1. **Streams.** The bar reads the **transcribe** stream (the bundle's `transcribe_words`, which
   is what the de-reverb gate gives Phase 2). The ASR json3 is on 2 of the `ref` songs, so an
   ASR-stream bar can't be measured; ASR enters only as an optional veto (dimension V below).
2. **Candidates.** Every synced record LRCLIB's search returns for the song, plus the song's
   on-disk `.lrc` when it is a match and its id is not among them. **Zero wrong acceptances is
   counted over all candidates**, not only the one a pick rule would choose: in production
   whichever record arrives meets the bar, so the bar must refuse every wrong one.
3. **Query.** As Repair's LRCLIB search box starts (`LibraryTools.custom_start`):
   `" ".join(t for t in lrclib.clean_key(genius_title or default_query(song), genius_artist or "") if t)`,
   with the Genius title and artist from the bundle's `lyrics.genius` when it has one, searched
   with `lrclib.search_query` (free text). Production searches by the Genius title and artist
   fields instead (`lrclib.search` in `ensure_lrc`); `ref` songs have no Genius pick, so this is
   the stand-in. Rule 2 makes the difference matter less.
4. **The two pick arms.**
   - *A, today's pick:* `ref`: `lrclib.select_candidate(records, caption_texts, clip_length)`,
     with the caption's cleaned cue texts standing in for the Genius sheet. Other groups: the
     on-disk `.lrc` (what production or Ken picked); with none, `select_candidate` against the
     bundle's `lyrics.lines`.
   - *B, best fit:* among the song's candidates the bar accepts, the highest matched share,
     then the smallest `|gap|`, then the smallest spread, then the lowest LRCLIB id.
5. **Caption check (is the reference usable).** For each `ref` song, the caption itself is
   fitted: `fit_slice(caption_srt, {"transcribe": words}, clip_length)`. `ref_ok` when it
   fits, `speed == 1.0`, `|shift_s| <= 1.5`, and `flagged_runs(mistimed, unheard,
   MIN_FLAGGED_RUN)` is empty. Only `ref_ok` songs count toward wrong acceptances or `ref`
   coverage. `caption_shift` is that fit's `shift_s` (the caption's own lead or lag against the
   heard words).
6. **Class of a candidate on a `ref_ok` song** (only when its transcribe fit `fits`; otherwise
   `no_fit`). Map the fitted LRC lines to caption cues by text:
   `lrclib.map_lines_to_cues([text for text, _ in fit.lines], caption_texts)`. For each mapped
   pair, `d = lrc_start - (caption_start + caption_shift)`. Then, first rule that applies:
   - `unjudged`: fewer than 8 mapped lines, or mapped / `len(fit.lines)` below 0.5.
   - `wrong_timing`: `|median(d)| > 1.5` s, or a run of 2 or more consecutive mapped lines with
     `|d| > 3.0` s (consecutive in LRC line order; an unmapped line between two such lines does
     not end the run, as `flagged_runs` treats an unheard line).
   - `hole`: a run of 4 or more consecutive fitted LRC lines with no caption cue mapped, or 4 or
     more consecutive caption cues with no LRC line mapped (a run at either end counts: an LRC
     that starts a verse late or stops early).
   - `right`: none of the above.

   `hole` and `unjudged` are not verdicts: GATE M eyeballs any it would accept.
7. **The bar's shape.** Fixed conjuncts on the transcribe fit, at every grid point: status
   `fits`; `speed == 1.0` (the plain factor won; PAL or a free speed means another edit);
   the record's duration is known (gap not None). Swept dimensions, each listed strict to
   loose:

   | Dim | Condition | Values (strict -> loose) |
   |---|---|---|
   | M | mistimed lines <= | 0, 1 |
   | R | matched / total >= | 0.9, 0.8, 0.7, 0.6, 0.5 |
   | G | `|gap|` s <= | 2, 3, 5, 10, 15 |
   | E | longest unheard stretch touching the first or last line <= | 0, 1, 2 |
   | I | an interior unheard run of 3+ lines (`MIN_UNHEARD_RUN`) | forbidden, allowed |
   | D | dropped lines <= | 0, any |
   | P | spread s <= | 0.3, 0.5, any |
   | V | ASR veto: when the song has an ASR stream, its fit must not refuse as `disagree` nor have a flagged run | on, off |

   3,600 points. GATE M picks values from this grid only; it adds no conjunct.
8. **Margin.** A point is `margin_safe` when it has no `wrong_timing` and no `known`
   acceptance, and neither does any point one step looser in exactly one dimension (a
   dimension already at its loosest has no such neighbour).

### Steps

- [ ] **1a. Anchor check.** Confirm these are as quoted above, else STOP and say what
  differs: `srt_slice_fit.fit_slice`, `heard_streams`, `lrc_to_srt`, `flagged_runs`,
  `unheard_runs`, `SliceFit` fields (`status`, `reason`, `matched`, `total`, `shift_s`, `speed`,
  `dropped`, `spread_s`, `lines`, `mistimed`, `unheard`); `lrclib.search_query` (raises
  `LrclibUnavailable`), `select_candidate`, `map_lines_to_cues`, `clean_key`, `read_song_lrc`;
  `library_regen.default_query`, `read_bundle`, `media_duration`, `SongJob`;
  `library_status.library_statuses`, `length_gap_s`; `srt_cues.cue_spans_from_srt`;
  `get_platform.get_temp_directory`. `scripts/lrc_timing_report.py` is the model for reading
  a song (bundle, clip length, streams); copy its shape.
- [ ] **1b. Write `scripts/lrc_auto_timing_probe.py`.** One command does everything:
  `python scripts/lrc_auto_timing_probe.py --folder PATH [--out DIR]`.
  - `--out` defaults to `Path(get_temp_directory()) / "lrclib_auto_timing"`. Everything the
    run writes goes there. It holds lyric text (cache, sheets), so it is never committed and
    never copied into the repo. Write `<out>/started` first (for the read-only check in 1e).
  - Groups as above. The `known` songs are found by YouTube ID; if a known song's on-disk
    `.lrc` id is not the one listed, STOP (the label no longer applies).
  - **Cache.** `<out>/cache/<youtube_id>.json` holds `{"query": ..., "records": [...]}`
    (synced records as LRCLIB returned them). Read it when present, else search and write it.
    On `LrclibUnavailable` write nothing for that song, give it the row reason
    `lrclib_unavailable`, and go on.
  - For every candidate: the transcribe fit and, when the song has an ASR json3, the ASR fit,
    each with `fit_slice(lrc_to_srt(synced), {name: words}, clip_length)` on one stream (as
    the report script does). The class (`ref_ok` songs) and arm A pick as settled above.
  - **Derived per candidate** from the transcribe fit: `end_unheard` = the longer of the
    unheard run that starts at line 0 and the one that ends at line `total - 1` (0 when that
    line was heard); `interior_unheard` = whether `unheard_runs(unheard, MIN_UNHEARD_RUN)` has
    a run touching neither end.
  - **`<out>/candidates.tsv`**, one row per candidate, no lyric text: group, youtube_id, short
    title (40 chars, as the report script), lrclib_id, on_disk, arm_a, record duration, gap,
    and from the transcribe fit status, reason, speed, shift_s, spread_s, matched, total,
    dropped, mistimed (count and indexes), unheard (indexes), end_unheard, interior_unheard;
    ASR fit status, reason, flagged-run count (empty with no ASR); for `ref` songs mapped,
    median_d, max_abs_d, off runs, lrc_hole_max, caption_hole_max, class; `known` rows get
    class `known_bad`.
  - **`<out>/songs.tsv`**, one row per song (skipped ones too, with reason): group,
    youtube_id, short title, candidates, arm-A id, and for `ref` the caption fit's status,
    speed, shift_s, flagged runs, `ref_ok`.
  - **Eyeball sheets** (lyric text, local only): for every `ref_ok` candidate whose transcribe
    fit `fits` and whose class is `wrong_timing`, `hole` or `unjudged`,
    `<out>/sheets/<youtube_id>/<lrclib_id>.txt`: the fitted LRC lines (index, fitted start,
    M or U flag, mapped cue index, d, text) and then the caption cues (index,
    start + caption_shift, mapped LRC index, text). Once per song,
    `<out>/sheets/<youtube_id>/words.txt`: the transcribe words (start, word).
  - **Sweep** over the grid in Settled 7. Per point, counted over `ref_ok` songs (all
    candidates) unless said: `wrong` (`wrong_timing` accepted), `holes`, `unjudged`, `known`
    (`known_bad` accepted), `margin_safe`; `a_ref` and `a_ref_any` (`ref_ok` songs whose arm-A
    pick is accepted and `right` / accepted at all); `b_ref` and `b_ref_any` (same for the
    arm-B pick); `a_joint`, `b_joint`, `a_repair`, `b_repair` (songs accepted, any class).
    Write every point to `<out>/sweep.tsv`.
  - **Printed** (stdout, no lyric text):
    - Table P: group counts and skip reasons.
    - Table C: `songs.tsv` as markdown.
    - Table S1: points with `wrong == 0`, `known == 0` and `margin_safe`, sorted by `b_ref`
      desc, then `a_ref` desc, then the sum of their step indexes asc (stricter first); top 30.
    - Table S2: every `hole` or `unjudged` candidate an S1 point accepts, as `title | youtube_id
      | lrclib_id | class | S1 rows that accept it`.
    - Table K: the three `known` candidates' transcribe fit (status, speed, matched/total,
      gap, mistimed, end_unheard) and the loosest grid point that would accept each, or "none".
- [ ] **1c. Tests**, `tests/unit/test_lrc_auto_timing_probe.py`, on the pure parts with made-up
  numbers: `end_unheard` and `interior_unheard` (runs at either end, none, whole song); the
  class rule (each of the four outcomes; an unmapped line inside an off run; median offset
  alone; a hole at an end); a grid point's acceptance (each conjunct turning a candidate away);
  `margin_safe` (a looser neighbour with a wrong acceptance makes it false; a dimension at
  its loosest has no neighbour); the arm-B ordering. No network, no library. Run
  `/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit/test_lrc_auto_timing_probe.py`
  and the pre-commit on both files.
- [ ] **1d. Commit** script and test together: `feat(scripts): LRCLIB auto-timing probe for
  GATE M`. Self-review per CLAUDE.md; this is a new algorithm in one file, so say whether it
  is simple enough to verify in one read-through.
- [ ] **1e. Run** `python scripts/lrc_auto_timing_probe.py --folder
  "/home/ken/shared-drives/D:/Shared/pikaraoke-songs" > <out>/report.md`. If more than 5 songs
  come back `lrclib_unavailable`, run it once more (the cache keeps the rest); if still more
  than 5, STOP. Then the read-only check: `find "<folder>" -newer <out>/started` prints
  nothing, else STOP and say what changed. STOP too if `ref` has fewer than 40 songs.
- [ ] **1f. Record.** Results log row: the commit, the command, the read-only check, the paths
  of `report.md`, `candidates.tsv`, `songs.tsv`, `sweep.tsv` and `sheets/`. Paste tables P,
  C, S1, S2 and K raw into a "GATE M report output" section below the Results log. No tallies
  beyond what the script printed, no reading of the numbers, no thresholds. Plan-only commit:
  `docs(plans): lrclib-auto-timing records the Phase 1 run`.
- [ ] **1g. Stop for GATE M.** Hand off to Opus (see "Executor rules"). Do not start Phase 2.

### GATE M (Opus, then Ken)

Read-only. Inputs: the "GATE M report output" section and the files under `<out>`.

1. Table K: the three known-bad LRCs must be refused at the point chosen (S1 already filters on
   this); note which conjunct turns each away.
2. Starting from S1's top rows, eyeball every `hole` and `unjudged` candidate the point and
   its one-step-looser neighbours accept, using its sheet and the song's `words.txt`. Rule
   each **LRC wrong** (it times words the video doesn't sing there, or leaves out a stretch
   the video sings) or **text only** (same words sung at the same place; the mismatch is
   spelling, line breaks or a caption's sloppiness). One line each in the Results log, with no
   lyric text.
3. A point stands when it is in S1 and no candidate it or its one-step-looser neighbours accept
   was ruled LRC wrong. With none standing: the bar can't reach zero; record it and STOP
   (Decision 8) for Ken's ruling.
4. Choose the arm. B only if it covers clearly more songs than A: it moves the LRCLIB pick out
   of `lyrics_fetch` into the align stage (a search and several fits per new download), which
   reshapes Phase 2.
5. Report to Ken, plainly: the bar, the arm, how many `ref_ok` songs it lets through (a stand-in
   for new downloads), how many of the 7 `joint` (Best Part Of Me is in `known`) and 7
   `repair` songs, and the caveats below.
   Ken rules go or stop.

Caveats the read must carry:

- `ref` songs are mostly official videos with uploader captions, the easy case for LRCLIB
  (the studio edit). New downloads that need a Genius pick are the songs without such a
  caption: lyric videos, live takes, uploads of other edits. Coverage on `ref` likely runs high
  for them.
- The `ref` search is free text on the video title, not production's Genius title and artist.
- Arm A on `ref` scores against the caption text, a cleaner sheet than a Genius page.

### Executor rules

- Stop at every STOP above and at 1g. If a step contradicts the code, stop and say so.
- No library writes, no GPU, no lyric text in any commit or in the plan.
- At 1g give Ken a handoff prompt for Opus: branch `lrclib_auto_timing` and HEAD, this file's
  "GATE M report output" section and GATE M steps, the `<out>` path, and "do not rerun the
  probe".

## Phases 2-4 (loose)

### Phase 2: pipeline switch

In `LyricAlignStage`, on a song that would take the joint route:

- When it is a first-time download, the origin is Genius, and a usable `.lrc` is on disk: get
  the transcribe words (the de-reverb gate's), fit the LRC, apply the bar.
- **Passes:** save the fitted sheet as the new sheet kind, set the origin, run cue align on it.
- **Fails:** joint plus the LRCLIB fill, as today.
- Either way, the bundle records the check and its outcome.
- The Genius pick stays stored, so Repair can return the song to Genius without a search.

### Phase 3: source type, labels, lists

- A new entry in `library_regen.SHEETS` (beside `"lrclib"`), its own origin and label, e.g.
  "LRCLIB timing (auto)". Most readers follow the table since the Phase 6.2 refactor of
  `archive/lyric_source_lists`.
- A Tools-tab list for it, Song Info and History wording, the run page's "Now:" text.
- Repair to another source removes it, as with the other sheet kinds.
- Translation catalogs in their own commits.

### Phase 4: Ken's checks

Download a few new songs, at least one expected to pass the bar and one to fail. Check the
list, Song Info's route and source, and the karaoke by ear. Return one to Genius via Repair.

## Open for the Phase 2-4 spec

- **How the pipeline knows a run is a first-time download**, not a Regenerate or a Repair to
  Genius (Decision 3).
- **Running the de-reverb gate once:** `_run_joint` and `_run_cue_align` each run it inside
  (unchanged by `cue_align_windows`); the switch needs its words before choosing the route.
- **The arm.** If GATE M picks B, the LRCLIB pick moves to the align stage.
- **The ASR veto**, if GATE M keeps it: Phase 2 then also fits the ASR json3 when on disk.
- **Reset:** Repair's LRC sheet survives Reset. Author default: the auto sheet does too, since
  with Decision 3 a dropped auto sheet would leave the song on joint for good.
- **Edit words on an auto sheet:** becomes "LRCLIB timing (edited)" or an edited-auto kind.
- **An off switch:** author default is none (no speculative flags); `lrclib_fill` already
  gates the LRC fetch.

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
| 1 | 2026-11-06 | 0 | Branch moved from `f627112` to `dev` `4497f4d`; loose plan committed (`aada4d2`). Overlap check: `git diff f627112 4497f4d -- pikaraoke/pipeline/stages/lyric_align.py` | `cue_align_windows` changed `_run_cue_align`'s return (adds envelope and `cue_inputs`), the edge snap's envelope reuse and its `doubted_sources`; route choice and `_dereverb_gate` untouched. Details in Phase 0. |
| 2 | 2026-11-06 | 1 | Library counts for the spec, read-only (`library_statuses` + `read_bundle`), 115 songs | origin `srt` 76 (1 edited), 59 with `transcribe_words`, 0 with `.srt.generated`, 0 with `.lrc`, 2 with ASR json3; `genius`+`joint` 8 (8 `.lrc`, 8 words); `lrclib_srt` 7 (7 `.lrc`, 7 words); `custom`+`joint` 3; `movie_srt` 7; no bundle 14. Known-bad `.lrc` ids and dates: Defying Gravity 34563601 (2026-10-28), Bloodstream 36006882 (2026-10-28), Best Part Of Me 27081884 (2026-10-19). |
