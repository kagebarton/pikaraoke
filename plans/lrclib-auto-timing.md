Model: Claude Opus 5.5 (author, loose draft 2026-11-03). To be fully specced (Opus) before a
Claude Sonnet 5.5 executor runs it. GATE M goes to Opus, then Ken.

# LRCLIB auto-timing at download

**Status: LOOSE DRAFT.** Scope and decisions are settled; phases are outlined, not specced.
"Open for the spec" below lists what the full spec must settle before an executor starts.

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

## Phases (loose)

### Phase 0: prerequisites

- Ken pushes his unpushed cue-align work (realigning lines with signs of bad windowing) to a
  branch. Check whether it touches the route choice in
  `pikaraoke/pipeline/stages/lyric_align.py` (around the `if cue_spans:` branch) or the
  de-reverb gate. The measurement does not depend on it; Phase 2's anchors might.

### Phase 1: measurement -> GATE M

A read-only, GPU-free probe on the VM (network for LRCLIB). Likely a new script beside
`scripts/lrc_timing_report.py`, reusing `srt_slice_fit.fit_slice` and `heard_streams`.

- **Population:** songs with an uploader caption, `subtitles/<stem>.srt` with no
  `.srt.generated` marker (those are PiKaraoke's own output), whose bundle holds transcribe
  words. About 60; count it. The caption is timed to our video and independent of the fit's
  inputs (the fit's ASR stream is YouTube's auto-caption, a different track).
- **Two ways to pick the LRC** (one arm each):
  - *Today's pick:* `select_candidate` as the download does, with the caption's text standing
    in for the Genius sheet (caption songs have no Genius pick).
  - *Best fit:* every synced candidate from the search, each fitted, keep the best.
- **Per song, raw:** fit status, speed, matched of total, spread, mistimed lines, unheard runs,
  gap to the video, per stream.
- **Against the caption:** map the fitted LRC lines to caption cues by text, and record each
  mapped line's start difference.
- **Coverage on the real target:** the same bar values on the current joint songs (no
  reference there, so coverage only).
- Cache every LRCLIB response in the scratchpad so reruns don't hit the network and the run
  is reproducible. Nothing in the library is written. No LRC or lyric text in a commit.

**GATE M (Opus, then Ken):** set the bar's thresholds so no caption song is wrongly accepted,
choose the pick arm, and report coverage. Ken rules go or stop on coverage.

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

## Open for the spec

- **The wrong-acceptance rule**, fixed before any number exists: how far a mapped line may
  sit from its caption cue, and over how many lines, before an accepted LRC counts as wrong.
  Uploader captions can be loose, so each wrong acceptance gets an eyeball to tell a bad LRC
  from a bad caption.
- **The bar's shape**, also fixed before the run, with only thresholds left to GATE M.
  Candidate conjuncts: fit passes; normal speed (Popular and Defying Gravity both landed on
  the PAL factor, Best Part Of Me at 0.986); no mistimed line; no unheard run (or none at the
  first or last lines); matched share high; gap within a few seconds. Which streams must pass:
  transcribe only, or ASR too when on disk.
- **Overfitting.** The bar is set on the set it is scored on. GATE M should leave margin, not
  sit at the edge of the first wrong acceptance.
- **The LRCLIB search for caption songs:** what query stands in for the Genius title and
  artist (the YouTube title, cleaned as `library_tools` does for its LRCLIB search box).
- **How the pipeline knows a run is a first-time download**, not a Regenerate or a Repair to
  Genius (Decision 3).
- **Running the de-reverb gate once:** `_run_joint` runs it inside; the switch needs its words
  before choosing the route.
- **Reset:** Repair's LRC sheet survives Reset. Author default: the auto sheet does too, since
  with Decision 3 a dropped auto sheet would leave the song on joint for good.
- **Edit words on an auto sheet:** becomes "LRCLIB timing (edited)" or an edited-auto kind.
- **An off switch:** author default is none (no speculative flags); `lrclib_fill` already
  gates the LRC fetch.

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
