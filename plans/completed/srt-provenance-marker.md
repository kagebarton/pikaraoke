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
`plans/completed/matcher-accuracy-hardening.md`'s Results log (3b entry + GATE outcome,
2026-07-13):

1. **Flag contamination on every second run.** The ground-truth probe
   (`lyric_align.py:318-343`) guards the same-run case (`wrote_srt`), but on
   a regen of an already-processed song `_should_write_srt` finds the stale
   generated SRT, `wrote_srt` is False, the re-probe finds the same file, and
   the bundle records `youtube_srt_present: True`. This poisoned the three
   2026-07-13 live-regen songs (Bloodstream, HUNTR_X, Defying Gravity),
   shrinking the harness corpus (`replay_ytasr_third_source.py:370` filters
   on the flag) from 17 to 14 and hard-blocking both
   `plans/completed/lrclib-fill-absence-study.md` (its L0.1 cross-check
   requires the joint set to equal the harness filter at 17 songs) and
   Phase 4.5's G1 enumeration.
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

### Part 2 implementation — module, wiring, tests, library backfill (Sonnet, 2026-07-14)

Every D1-D4 line reference (write site, the three `_find*srt` discovery
copies, the two promotion sites) was re-read from live code before editing;
all matched the plan exactly.

**D1.** `pikaraoke/lib/srt_provenance.py` added verbatim to the locked
design: `_marker_for`, `mark_generated`, `is_generated`,
`clear_generated_marker`; no imports beyond `pathlib`. Marker content
matches Part 1's hand-written sidecars byte-for-byte (`"Generated by
PiKaraoke's lyric-align stage; not an uploader caption.\n"`), so the three
songs Part 1 marked early needed no rewrite.

**D2-D3.** `lyric_align.py` (`mark_generated` after the SRT move;
`is_generated` skip in `_find_youtube_srt_path`, which `_should_write_srt`
delegates to unchanged), `lyrics_fetch.py` (`_find_srt`),
`regen_alignment_bundles.py` (`_find_local_srt`), `backfill_artifacts.py`
(`_find_local_srt`) — each a one-line skip-if-generated addition, exactly
as specified.

**D4 — one deviation from the literal spec, Ken-approved.** While wiring
`download_manager._move_downloaded_subtitle`, empirically confirmed (small
throwaway script, not kept) that `Path.rename` raises `FileExistsError` on
this Windows box when the target already exists — POSIX `rename` would
replace it silently. Left as spec'd, the scenario D4 exists to fix (a real
caption promoted onto a path already holding a generated, marked SRT)
would silently no-op on Windows: the `except OSError` catch swallows the
rename failure before `clear_generated_marker` is ever reached. Flagged to
Ken with three options (implement literally and accept the gap; a narrow
unlink-only-if-`is_generated` pre-check; swap to `os.replace`, matching
the sibling D4 call site already using it in `regen_alignment_bundles.py`)
— he chose the `os.replace` swap. Changed `source.rename(target)` to
`os.replace(source, target)` with a comment explaining why, then added
`clear_generated_marker(target)` after the successful replace, per D4.
The `regen_alignment_bundles.py` fetch-promotion site already used
`os.replace`; only the `clear_generated_marker` call was added there.

**Tests — exactly the plan's four bullets, nothing added beyond them.**
`tests/unit/test_srt_provenance.py` (new): mark -> `is_generated` True; no
marker -> False; `clear_generated_marker` removes it / no-ops when absent.
`test_lyric_align.py`: `TestShouldWriteSrt` gained the marked-SRT-> True
case; `TestYoutubeSrtProvenance` gained an assertion that the write site
marks its own output, plus a new second-run test (a stale marked SRT on
disk -> `youtube_srt_present` stays False, the sidecar is rewritten
losing its old "stale" content, and re-marked). `test_lyrics_fetch.py`:
`TestFindSrt` gained marked-> None and marked-with-real-`.en.srt`
present -> the `.en.srt`. `test_download_manager.py`: new test asserting
a stale marker doesn't survive a real caption's promotion onto the same
path. The `regen_alignment_bundles.py`/`backfill_artifacts.py` D3 sites
and the `regen_alignment_bundles.py` D4 site have no dedicated new tests,
matching the plan's own framing of those two discovery sites as "defense
in depth, not a behavior change on the current library" and the fact that
`clear_generated_marker` itself is already covered directly in
`test_srt_provenance.py`.

**Validation.** Targeted run (the new + all four extended test files): 99
passed. Full `tests/unit`: 1390 passed, 2 skipped, 4 failed — all four
(`test_genius.py::TestSidecarIO::test_write_overwrites_existing`,
both `test_pipeline_stem_worker.py::TestStemWorkerSeparate` cases,
`test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close`)
are inside the pre-established 5-item Windows baseline; the fifth
(`test_mpv_controller.py::test_stop_aborts_cleanly_on_shutdown`) simply
didn't trip this run (documented as flaky). Zero new failures.
Import-smoke: `pikaraoke.lib.srt_provenance`, `.download_manager`,
`.pipeline.stages.lyric_align`, `.pipeline.stages.lyrics_fetch` all import
cleanly; both scripts (which `sys.path.insert` themselves and so can't be
plain-imported) parse and run `--help` cleanly. `pre-commit` on every
changed file: clean except one pre-existing, unrelated finding —
`scripts/regen_alignment_bundles.py` is git-tracked at mode `100644`
despite carrying a shebang (`check-shebang-scripts-are-executable`
fails); `git ls-files -s` confirms that mode predates this session (only
file *content* was touched, via `Edit`, which never changes git mode
bits) — not fixed here, left for Ken/judge to decide since it's orthogonal
to Part 2 and touching git file-mode metadata as a bundled side effect of
an unrelated feature commit seemed like its own decision.

**Commit.** `df5e3489b9a8a15e68f1ca3f4fbda8e7d9d9a7eb` —
`feat(pipeline): provenance marker for generated SRTs`, 10 files changed
(180 insertions, 6 deletions): the new module + test file, and the four
D2-D4 production files + their four test files. Staged explicitly by
filename (not `git add -A`) so the pre-existing, unrelated working-tree
state (`pyproject.toml`, `uv.lock` modifications; the untracked `.kilo/`
and `plans/two-path-matcher-ship.md`) stayed out of the commit.

**Library backfill.** Ran the scratchpad script `backfill_srt_markers.py`
(session scratchpad, never committed) against `D:\shared\pikaraoke-songs`,
implementing the plan's deterministic rule via the now-committed
`pikaraoke.lib.srt_provenance` helpers directly (`is_generated` /
`mark_generated`) rather than reimplementing marker I/O. Invocation:
`uv run python <scratchpad>/backfill_srt_markers.py`. Pre-run cross-check:
33 bare `subtitles/<stem>.srt` files, 0 `.en.srt` files, 33 bundles —
matches the Fable 2026-07-14 survey above exactly before any marking
happened.

Results (33/33 accounted for by the script's own internal assertion):

- **Newly marked as generated (14):** 'Free' (Sony Animation), 'Popular'
  (Wicked 20th Anniversary), Beauty and the Beast — Be Our Guest [UHD],
  Beauty and the Beast — Belle [UHD], Ed Sheeran - Best Part Of Me (Live),
  Jessie J - Domino, Josh Gad - In Summer, Mulan - I'll Make a Man Out of
  You, NSYNC - Paradise, Pocahontas - Colors of the Wind, Seasons of Love
  (HD), The Lion King - Hakuna Matata, The Next Ten Minutes Lyrics, Wicked
  - For Good (2025) - The Girl in the Bubble.
- **Already marked, no-op (3):** Defying Gravity, Bloodstream, HUNTR_X —
  Part 1's early hand-written markers; confirmed identical, not rewritten.
- **Skipped — srt origin, real caption (16):** #OutOfOz - For Good,
  Ariana Grande/John Legend - Beauty and the Beast, Backstreet Boys -
  Incomplete, Backstreet Boys - More Than That, Ed Sheeran - Happier,
  Idina Menzel - Let It Go, Jodi Benson - Part of Your World, Justin
  Timberlake - Like I Love You, Justin Timberlake - Mirrors, Justin
  Timberlake - Rock Your Body, Justin Timberlake - Selfish, Mena
  Massoud/Naomi Scott - A Whole New World, Naomi Scott - Speechless,
  NSYNC - Bye Bye Bye, The Lion King - Can You Feel the Love Tonight,
  ZAYN/Zhavia Ward - A Whole New World (End Title).
- **Skipped — real caption alongside a non-srt lyric choice (0):** none.
- **Undeterminable — no bundle or unexpected flag state (0):** none.

14 + 3 = 17 genius+joint songs marked, 16 srt+cue_align songs skipped, 0
edge cases — an exact match to the Fable survey's stated reach, with zero
discrepancy. Independently reverified afterward via a fresh glob:
`subtitles/*.srt.generated` count on disk = 17. Reversible by deleting
`*.srt.generated` files, per the plan.

This entry records artifacts and check results only — commit contents,
test/pre-commit/import-smoke outcomes, and the backfill counts with their
cross-check against the pre-existing survey. It does not pronounce Part 2
correct or complete; consistent with this file's and
`matcher-accuracy-hardening.md`'s established executor/judge split, that
read is left to the judge.

### Part 2 judge read — independent re-derivation of the locked design (Opus, 2026-07-14)

Re-derived from live files/commits, not the write-up. `git show df5e3489`
(+ `a5c3df3` docs) against my own D1-D4 spec.

**D1 — module.** `pikaraoke/lib/srt_provenance.py`: sole import
`from pathlib import Path`; `_MARKER_SUFFIX = ".generated"`, `_marker_for`,
`mark_generated`, `is_generated` (existence via `.is_file()`),
`clear_generated_marker` (`unlink(missing_ok=True)`) — all verbatim to
D1. The added `_MARKER_CONTENT` constant carries D1's exact string.
**Match.**

**D2 — write site.** `mark_generated(final_srt)` sits immediately after
`shutil.move(...)` at `lyric_align.py:241`, inside the single shared
`if write_srt and tmp_srt is not None:` block — the one promotion point
both the alignment and transcribe routes funnel through. Both routes
covered by one call, as D2 requires. **Match.**

**D3 — four discovery sites.** Each gains the identical
`and not is_generated(candidate)` guard: `_find_youtube_srt_path`
(`lyric_align.py:1021`, which `_should_write_srt` delegates to),
`lyrics_fetch._find_srt`, `regen_alignment_bundles._find_local_srt`,
`backfill_artifacts._find_local_srt`. Mirrored structure preserved (D6).
**Match.**

**D4 — two promotion sites.** `download_manager` clears the marker after
a successful replace; `regen` fetch clears after its existing
`os.replace` (only the `clear_generated_marker` line added there).
**Match.**

**The deviation is real and sound.** Verified empirically on this box
(`uv run python`, throwaway): `Path.rename` onto an existing target
raises `FileExistsError` — which *is* an `OSError`, so the existing
`except OSError` in `_move_downloaded_subtitle` would have caught it,
warned, and `return`ed *before* `clear_generated_marker` ran; `os.replace`
replaces silently and unlinks the source. So the literal D4 spec would
have silently no-op'd on Windows in exactly the target-exists scenario D4
exists to fix. Scope of the swap: it diverges from `Path.rename` *only*
in the Windows target-exists case (POSIX rename already replaced
silently, and the sibling regen site already used `os.replace`); `source`
is always a video-sibling from a non-recursive glob, never the
`subtitles/` target, so no self-replace edge. No behavior change D4 did
not intend. Ken-approved and correctly implemented.

**Tests exercise what's claimed, read line-by-line.** The second-run
test (`test_lyric_align.py:723`) reproduces the actual contamination:
pre-seeds a *marked* stale `.srt` holding `"stale"`, runs the full stage,
then asserts `youtube_srt_present` stays False (hazard 1), the sidecar is
rewritten (`"stale" not in` its text — hazard 3) and re-marked. The
download-manager test (`test_download_manager.py:418`) seeds a marked
stale target + a real `.en.srt`, promotes, and asserts the real content
landed **and** `not is_generated` — which would itself fail on Windows
under the pre-deviation `Path.rename`, so it doubles as the deviation's
regression guard. `_should_write_srt`→True on a marked SRT, write-site-
marks-its-own-output, and the `lyrics_fetch` marked→None / marked+real-
`.en.srt`→`.en.srt` cases all present and substantive. Not superficial.

**Re-ran the suite myself.** `uv run python -m pytest tests/unit -q`:
1390 passed, 2 skipped, 4 failed — the 4 are exactly the pre-established
Windows baseline (`test_genius` sidecar-overwrite, both
`test_pipeline_stem_worker::TestStemWorkerSeparate`,
`test_whisper_worker` pipe-close), none touching Part 2 code; the 5th
(mpv_controller) didn't trip. Zero new failures. Targeted Part-2 set: 99
passed. `pre-commit ... --files <10 changed>`: every quality hook (pycln,
isort, black, pylint) clean; sole failure the pre-existing
`check-shebang-scripts-are-executable` on `regen_alignment_bundles.py` —
`git ls-tree` shows mode `100644` on both `df5e3489` and its parent
(`fe8f54b`→`53ee772` is a content-only change), so it predates this
session as claimed.

**Recomputed the backfill independently** (read-only, live
`D:\shared\pikaraoke-songs` only, backups excluded): 33 bare `.srt`, 0
`.en.srt`, 17 `.srt.generated`. Applying the plan's deterministic rule
straight off the bundles → mark 17 / skip-srt-origin 16 / real-caption
0 / undeterminable 0. Perfect bijection: every rule-marked stem has a
marker on disk and every on-disk marker is rule-derived (no leak either
way). mtimes corroborate the 14+3 split — the 3 Part-1 markers
(Defying Gravity, Bloodstream, HUNTR_X) at 12:00:16 predate the 12:57:49
commit and were left untouched; the 14 backfill markers at 12:59:24-25.
All 17 markers byte-identical, no orphans. Exact match to the claim.

**One cosmetic nit, not a defect, no action.** The on-disk marker bytes
are CRLF-terminated (`Path.write_text` applies Windows text-mode newline
translation), so the write-up's "byte-for-byte `...caption.\n`" describes
the source literal, not the disk bytes (which end `\r\n`). Immaterial:
`is_generated` keys on file *existence*, never content, and all 17
markers are mutually identical, so the "3 Part-1 markers confirmed
identical, not rewritten" claim holds regardless.

**Verdict.** The implementation matches the locked D1-D4 design; the sole
deviation is necessary, correct, and its behavior change is confined to
the case D4 targets. Tests, suite, pre-commit, and the backfill all
re-verify independently. **Part 2 is ready to close, and with Part 1's
gold-label entry already recorded, this plan — both parts — is done.**
