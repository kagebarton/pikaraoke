Model: Claude Fable 5 (design, 2026-07-14); executor: Claude Sonnet 5

# SRT provenance: corpus cleanup + generated-caption marker

## Context

Uploader captions and the pipeline's own generated subtitles collide at the
same path. `download_manager._move_downloaded_subtitle`
(`pikaraoke/lib/download_manager.py:420-453`) promotes downloaded captions to
`subtitles/<stem>.srt`; `LyricAlignStage` writes its generated SRT to the
identical path (`pikaraoke/pipeline/stages/lyric_align.py:235-241`). Nothing
on disk distinguishes the two provenances afterward.

Consequences, all previously documented in
`plans/matcher-accuracy-hardening.md`'s Results log (3b entry + GATE outcome,
2026-07-13):

1. **Flag contamination on every second run.** The ground-truth probe
   (`lyric_align.py:318-343`) guards the same-run case (`wrote_srt`), but on
   a regen of an already-processed song `_should_write_srt` finds the stale
   generated SRT, `wrote_srt` is False, the re-probe finds the same file, and
   the bundle records `youtube_srt_present: True`. This poisoned the three
   2026-07-13 live-regen songs (Bloodstream, HUNTR_X, Defying Gravity),
   shrinking the harness corpus (`replay_ytasr_third_source.py:370` filters
   on the flag) from 17 to 14 and hard-blocking both `plans/
   lrclib-fill-absence-study.md` (its L0.1 cross-check requires the joint set
   to equal the harness filter at 17 songs) and Phase 4.5's G1 enumeration.
2. **Live self-adoption hazard.** `lyrics_fetch._find_srt`
   (`pikaraoke/pipeline/stages/lyrics_fetch.py:175-186`) would adopt the
   pipeline's own prior `.srt` as an uploader caption and route through
   cue_align on it, freezing prior output (including leaked phantoms) as
   cues.
3. **Stale sidecars.** `_should_write_srt` never refreshes an existing
   generated SRT, so `.ass` and `.srt` drift apart across regens (both
   Bloodstream's and HUNTR_X's `.srt`s still contain lines the veto later
   demoted from the `.ass`).

**Ken's provenance ruling (2026-07-14):** verified on YouTube that none of
the three songs has an uploader SRT — the on-disk `subtitles/<stem>.srt`
files for Bloodstream, HUNTR_X, and Defying Gravity are pipeline-generated.

Prior art acknowledging the same root cause, none of it a durable fix:
`regen_alignment_bundles._reuse_plan` distrusts the flag outright
(`regen_alignment_bundles.py:258-262`); `repair_ytasr_from_backup.
clear_generated_srt` deletes generated SRTs so a re-run can write fresh
ones; the probe's own comment (`lyric_align.py:318-322`) names the "stale,
from a prior run" case it cannot detect.

This plan has two parts. **Part 1** (data only, no production code) corrects
the three bundles and re-baselines the harness at 17 songs — run it first;
it unblocks the LRCLIB study and Phase 4.5a. **Part 2** (one production
commit) adds a provenance marker so the contamination cannot recur — it must
land before the next regen of any already-processed song (Phase 4.5's G6
regens Bloodstream and Defying Gravity, which would re-poison them).

Executor discipline from `matcher-accuracy-hardening.md` applies verbatim:
specs are contracts; any mismatch between this file and code reality is a
STOP + report, never a bridge; every Results-log number comes from a command
run in that session with the invocation recorded; byte-identical claims
require a real `diff` of saved outputs.

## Part 1 — corpus cleanup (data, before the studies; no code commit)

Song library: `D:\shared\pikaraoke-songs` (Windows box). Corpus filenames
contain soft hyphens (U+00AD) and other metacharacters: locate the three
songs by globbing `alignment_debug/*.json` and substring-matching
(`Bloodstream`, `HUNTR`, `Defying`) — never reconstruct a path from a
printed name.

1. **Pre-patch harness run** (the self-contained baseline for step 5):
   `replay_ytasr_third_source.py "D:\shared\pikaraoke-songs" --alpha 2.0
   --beta 2.0`, table saved to the session scratchpad. Expect 14 rows
   matching the post-E3a baseline (`replay_post_e3a.txt` values, recorded in
   the Phase 4 GATE close).
2. **Back up** the three bundle JSONs unmodified to
   `D:\shared\pikaraoke-songs\provenance_backup_<UTC-stamp>\` before
   touching them.
3. **Patch each bundle.** Preconditions (assert all three per file; any
   failure is a STOP): `pipeline_decisions.method_used == "joint"`,
   `ground_truth_refs.youtube_srt_present is True`,
   `ground_truth_refs.youtube_srt_is_lyric_source is False`. Then set
   `ground_truth_refs.youtube_srt_present = False` and
   `ground_truth_refs.youtube_srt_path = None` (matching what the stage
   records when no caption exists, `lyric_align.py:335-343`). Serialize
   exactly as `alignment_capture.write_bundle` does
   (`json.dumps(bundle, indent=2, ensure_ascii=False)`, UTF-8, no trailing
   newline) so the file diff is minimal. **Verify:** `diff` old vs new per
   file shows exactly the two changed lines; anything else is a STOP.
4. **Mark the three generated SRTs** per Ken's ruling: write the Part 2
   marker file next to each song's `subtitles/<stem>.srt` (convention in
   D1 below; the marker is inert until Part 2's code lands — writing it
   early is deliberate so the files are safe the moment the code ships).
   Do not delete or move the `.srt`s — playback consumes them
   (`playback_controller._find_subtitles`), and post-Part-2 the next regen
   refreshes them.
5. **Post-patch harness run**, same invocation, table saved. Pre-registered
   expectations:
   - **17 rows**: the 14 prior rows byte-identical to step 1's table, plus
     new rows for Bloodstream, HUNTR_X, Defying Gravity. No expectations on
     the three new rows' values — they are additive baseline rows, never
     diffed against anything earlier.
   - **Known flake carve-out:** the harness live-fetches a held-out LRCLIB
     reference for songs without a local cache; an HTTPS timeout changes
     only that song's `src`/bail-label cell (`bail:no_reference`) with all
     matcher-derived columns (placed / MAD / crawl / overlap / coverage)
     unchanged. If a row differs *only* that way and the run log shows the
     timeout, re-run; a difference in any matcher-derived column is a STOP.
6. **Record** in `matcher-accuracy-hardening.md`'s Results log: Ken's
   ruling, the backup path, the per-file diff confirmation, both
   invocations, and the 17-row table — which becomes the post-Phase-4
   baseline superseding the 14-row `replay_post_e3a.txt` values. The
   Bloodstream/HUNTR_X/Defying Gravity harness-exclusion caveat in the
   Phase 4 GATE close is resolved by this entry (note that there).
   Commit the plan-doc updates alone (docs commit); nothing else in Part 1
   is committed.

Executor stops at the artifacts (tables + diffs); the judge reads them
before the 17-song table is blessed as the new baseline.

## Part 2 — generated-caption marker (locked design)

### D1. New module `pikaraoke/lib/srt_provenance.py`

Marker convention: a generated `subtitles/<stem>.srt` is accompanied by
`subtitles/<stem>.srt.generated` — a one-line UTF-8 text file (content:
`Generated by PiKaraoke's lyric-align stage; not an uploader caption.`).
Sidecar file, not SRT content: SubRip has no comment syntax, and the marker
must survive tools that rewrite the `.srt`'s body.

```python
_MARKER_SUFFIX = ".generated"

def _marker_for(srt_path: Path) -> Path:
    return srt_path.parent / (srt_path.name + _MARKER_SUFFIX)

def mark_generated(srt_path: Path) -> None: ...
def is_generated(srt_path: Path) -> bool: ...
def clear_generated_marker(srt_path: Path) -> None:  # missing marker is a no-op
```

No imports beyond `pathlib`. Uploader `.en.srt` files are never marked
(only the stage's write site calls `mark_generated`), so the helpers need
no name-pattern logic.

### D2. Write site — `lyric_align.py`

After the generated SRT is promoted to its final location
(`shutil.move(str(tmp_srt), str(final_srt))`, `lyric_align.py:239`), call
`mark_generated(final_srt)`. Applies to both routes that set
`write_srt=True` (alignment and transcribe modes — the write site is
shared).

### D3. Discovery sites — treat marked files as "no caption"

One-line change in each; the mirrored-function structure stays (consolidating
the three copies is out of scope, D6):

- `lyric_align._find_youtube_srt_path` (`lyric_align.py:1009-1021`): a
  candidate with `is_generated(candidate)` is skipped. Effects: on a regen
  of a generated-SRT song, `_should_write_srt` returns True (the stale
  sidecar is refreshed and re-marked — heals hazard 3) and the ground-truth
  probe records `youtube_srt_present: False` (fixes hazard 1). The existing
  `wrote_srt` guard at line 323 stays — still correct, now redundant on
  first runs only.
- `lyrics_fetch._find_srt` (`lyrics_fetch.py:175-186`): same skip — a
  generated SRT is never adopted as a lyric source (fixes hazard 2). A real
  `<stem>.en.srt` next to a marked `<stem>.srt` is still found first,
  unchanged.
- `regen_alignment_bundles._find_local_srt`
  (`regen_alignment_bundles.py:217-224`) and
  `backfill_artifacts._find_local_srt` (`backfill_artifacts.py:252-259`):
  same skip, for consistency (srt-origin songs never have generated SRTs,
  so this is defense in depth, not a behavior change on the current
  library).

### D4. Promotion sites — clear a stale marker when a real caption lands

When a downloaded uploader caption is promoted onto `<stem>.srt`, any marker
left from a previously generated file at that path now lies about a real
caption; remove it:

- `download_manager._move_downloaded_subtitle`: after the successful
  `source.rename(target)` (`download_manager.py:443`), call
  `clear_generated_marker(target)`.
- `regen_alignment_bundles.py` fetch promotion: after
  `os.replace(srt_path, playback_srt)` (line 490), call
  `clear_generated_marker(playback_srt)`.

### D5. Deliberately untouched

- `playback_controller._find_subtitles`: playback is provenance-agnostic —
  generated SRTs exist for it.
- `regen_alignment_bundles._reuse_plan`'s flag distrust
  (`regen_alignment_bundles.py:258-262`): stays as defense in depth.
- `repair_ytasr_from_backup.clear_generated_srt`: historical one-shot,
  already run; not updated.

### D6. Non-goals (locked)

- No consolidation of the three `_find*srt` copies into a shared lookup —
  smallest-change fork rule; the shared piece is the `is_generated`
  predicate only.
- No content-based SRT provenance heuristics.
- No changes to bundle schema, harness, or matcher.
- No retro-marking of songs whose provenance a bundle cannot determine
  (see backfill below — they are reported, not guessed).

### Tests

- `tests/unit/test_srt_provenance.py` (new): mark → `is_generated` True;
  no marker → False; `clear_generated_marker` removes it and is a no-op
  when absent.
- `tests/unit/test_lyric_align.py`: extend the `_should_write_srt` group
  (lines 92-118) — True when the only on-disk SRT is marked; extend the
  probe-honesty test (lines 689-722) with the second-run scenario: a stale
  *marked* SRT on disk → `youtube_srt_present` False; assert the write site
  leaves a marker next to the generated SRT.
- `tests/unit/test_lyrics_fetch.py`: extend the `_find_srt` group (lines
  61-92) — marked `<stem>.srt` → None; marked `<stem>.srt` with real
  `<stem>.en.srt` present → the `.en.srt`.
- Download-manager promotion clears a pre-existing marker (add to the
  existing `_move_downloaded_subtitle` tests).

### Library backfill (scratchpad script, after the commit lands)

Existing generated SRTs across the library predate the marker; without
backfill, hazard 1 recurs per song on its next regen. Deterministic rule —
first-run bundle flags are trustworthy (the `wrote_srt` guard); only the
three Part-1 songs were ever regened, and Part 1 fixed them:

For every song directory with a `subtitles/<stem>.srt`:

- bundle exists, `lyrics.origin == "srt"` → real caption, skip;
- bundle exists, origin != "srt", `youtube_srt_present` is False (post-
  Part-1) → generated, `mark_generated`;
- bundle exists, origin != "srt", `youtube_srt_present` is True → a real
  caption existed alongside a non-SRT lyric choice, skip;
- no bundle → undeterminable: report the song, do not mark.

Script lives in the session scratchpad (never committed); invocation plus
the per-song action table and the undeterminable list go into this file's
Results log. Reversible by deleting `*.srt.generated` files.

A read-only survey (Fable, 2026-07-14) already established the rule's
reach on the current library: 33 songs, 33 bundles, zero bundle-less
songs, zero orphan SRTs; 17 genius+joint (the three contaminated ones the
only flag-True among them) and 16 srt+cue_align (all
`youtube_srt_is_lyric_source: True`). Both the "flag True, origin !=
srt" and "no bundle" branches are empty, so the rule fully determines
the library. Ken additionally verifies provenance per song on YouTube
(no-uploader-captions expected for the 17 genius songs;
manual-captions-present expected for the 16 srt songs); his answers are
gold labels recorded in the Results log. A genius song found to *have*
YouTube captions still gets marked (its first-run flag proves no caption
was on disk when the stage wrote the SRT) — note it as a
fetchable-caption opportunity only. An srt song found to *lack* YouTube
captions is a STOP: its adopted SRT has unknown provenance and the
cue-corpus circularity question reopens for it.

### Validation

Unit suite (the known Windows-baseline failures are not regressions) +
`pre-commit run --config code_quality/.pre-commit-config.yaml` on changed
files + import-smoke. No corpus replay: the harness reads bundle flags, not
SRT discovery, so Part 2 cannot move Part 1's table — any observed
difference would itself be a STOP.

### Commit

One commit: `feat(pipeline): provenance marker for generated SRTs`
(new module + the D2-D4 call sites + tests). Docs/Results-log updates ride
separately per the established pattern.

## Results log

### Caption provenance gold labels + LRCLIB provisioning (Ken + Fable judge read, 2026-07-14)

Ken's YouTube caption survey: `D:\shared\pikaraoke-songs\caption_report.txt`
(32 songs; format `STATUS|title|Manual: <tracks>|ASR: <langs>`; auto-ASR
tracks are not captions for this purpose).

- **Genius/joint (List A), 17 of 17: zero manual captions — all gold.**
  Every reported song reads ASR-only or NONE. Two rows resolved verbally
  the same day: Seasons of Love (HD) was absent from the report file —
  Ken confirms English ASR only, no manual captions; NSYNC - Paradise is
  **not a YouTube video at all** (manually-added library file — its
  ID-less stem agrees), so its report row (an unrelated same-title video)
  is void and no uploader caption can exist for it by construction.
  Combined with the three 2026-07-13/14 affirmations, the "generated"
  label on all 17 `subtitles/<stem>.srt` files is gold, not rule-derived.
- **SRT/cue (List B), all 16: manual captions present** (MANUAL or BOTH).
  The pre-registered STOP (an srt-origin song lacking YouTube captions)
  did not fire; the cue-corpus circularity question is retired for the
  existing library.

LRCLIB flat cache (`D:\shared\pikaraoke-songs\lrclib\<stem>`): Ken
provisioned 'Free' (Sony Animation), Jessie J - Domino, and Seasons of
Love (HD) on 2026-07-14; all three verified parsing as clean
`[mm:ss.xx]` LRC under the exact bundle stems. (An earlier judge note
flagged Free as missing — false alarm from a truncated directory
listing; the file was present.) Joint-corpus offline coverage is now
14 of 17. Popular / HUNTR_X / Defying Gravity have **no matching LRCLIB
variant** per Ken's vetting (deliberate cache absence — a wrong-version
reference is worse than none). Note the harness still runs its tier-3
live search for them on every invocation, and for Popular that search
has historically returned a candidate — now known to be a wrong version,
so any reference-derived cell (`mad`, `off`, bail label) on these three
rows is void as evidence and their cells are **unpinned** in Part 1's
expectations: they are additive rows with no baseline bar. Popular sits
in the 14 shared rows, where only the byte-identical bar applies (the
timeout carve-out already covers its live-fetch flake). Ken notes the
Free and
Domino variants differ from these mixes **by constant offset only** —
harmless for scoring: the harness's acceptance statistic is MAD about the
median offset (`offset_mad_against_cues`), which is invariant to a
constant shift; the executor must not treat a large `off` on these songs
as an anomaly.
