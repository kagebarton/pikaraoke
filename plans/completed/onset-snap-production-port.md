# Onset-snap: production port, crawl re-check, and review

Model: Claude Opus 4.8

Working record for the session that ported the line-initial onset-snap
post-pass onto the production matcher, re-measured the slow-crawl artifact
against the new matcher, and code-reviewed the result.

## What onset-snap is

`pikaraoke/lib/onset_snap.py` — `snap_line_onsets(line_objects, vocal_path)`,
a post-pass wired into `LyricAlignStage.run()` right before ASS generation (so
it covers every timing source).

**Artifact it fixes:** "first word sweeps early, stalls, line recovers at word
2." Whisper's word onsets after an instrumental gap are its least reliable
timestamps: cross-attention smears the first word's start back into the gap,
and VAD/silence suppression can't clip it because a separated vocal stem
carries reverb tails/bleed there rather than silence. The ASS writer re-anchors
the karaoke cursor at every inter-word gap, which is why word 2 recovers.

**Detector:** for each line's first word, search `[word1.start, word2.start]`
in the stem's RMS envelope for the first sustained energy rise (>=10 dB step)
that lands near the line's own sung level, then shift the word start forward to
it. A reverb tail decays monotonically so it cannot fake a rise — the exact
failure mode that defeats an absolute silence threshold. Shifts are
forward-only and bounded by word 2, so an on-time line is never made worse.
Two-tier acceptance (hard: near sung level; soft: below but sustained 0.4 s),
plus a continuity-to-word-2 check and an on-time guard (near sung level at the
claimed start AND across the claimed span) to protect staccato lines.

**Key structural property:** onset-snap can only ever *shorten* word 1 (start
moves forward, end kept or carried). It therefore cannot create a slow crawl or
a next-line collision — it can only reduce them.

## Branch topology

- `lead_in_out_snap` (formerly `srt_windowed_align`) — the experimental lineage
  (ytasr 3rd-source, cue-align, LRCLIB priors) with the onset-snap commit
  `dee7f06e` on top. Left intact as historical record.
- `pathed_align_ship` — the current production "2-path matcher" (cue_align for
  SRT + 3-source joint route). It reworked much of `lead_in_out_snap`'s
  experiments and **deliberately dropped** the timing priors ("drop the
  snap/fill prior", "drop timing priors").
- `onset_snap_on_ship` — **this port**: `pathed_align_ship` + onset-snap only.
  Tip commit `d1bd4dee`.

A full rebase of `lead_in_out_snap` was rejected: 22 of its 23 commits are the
superseded/dropped experiments and would conflict heavily. Only `dee7f06e` (the
onset-snap tip) was ported, via cherry-pick onto a new branch.

## This session

### 1. Slow-crawl re-check

Scanned `.onsetsnap.ass` for slow crawls (a `{\kf N}` sweep filling very slowly:
high centiseconds-per-character). Metric calibration: median fill ~10 cs/char,
p99.5 ~111; e.g. Bye Bye Bye "I know that I can't take no more" had `{\kf276}I`
= 2.76 s on one character. Narrowed to crawls that push their line onto the
**next** line (the visible "two lines highlighting at once" bug), attributing
overlap to the crawl via a counterfactual (shrink the crawl word to line-median
fill and remeasure). 15 such collisions in the stale files.

### 2. Staleness discovery (the key finding)

The `.onsetsnap.ass` on disk were **stale**: mtime 07-02, built on the *old*
matcher. Production `.ass` was rebuilt 07-04 by `pathed_align_ship`. Evidence:
Bye Bye Bye line, old-file "I" = 276 cs vs current-production "I" = 10 cs; and
onset-snap can only shorten, so a 276 cs "I" could only have come from the old
matcher, not from onset-snap. A clean scan of **current production** found
**0 crawl-caused next-line collisions** (1788 lines, 133 crawl-words; the
deepest line overlaps are repeated-hook doubling like "You are, you are the love
of my life", not smears). The new matcher independently eliminated the gross
crawls. Deleted one contaminating stale file.

### 3. Port onto the production matcher

`git checkout -b onset_snap_on_ship pathed_align_ship`, then cherry-picked
`dee7f06e`. The three new files (`onset_snap.py`, `test_onset_snap.py`,
`onset_snap_ass.py`) applied clean; only the import block in `lyric_align.py`
conflicted. Resolved by keeping `pathed_align_ship`'s
`from pikaraoke.lib.srt_cues import cue_spans_from_srt` and adding the
`onset_snap` import, **dropping** the stale
`from pikaraoke.lib.srt_prior import apply_srt_prior` line (that module/prior
was removed on the new base). The hook auto-merged correctly (`vocal_wav` and
`capture_joint_stats` both in scope; `_generate_ass` -> module-level
`generate_ass` intact). Full suite 1301 pass.

### 4. Regenerate onsetsnap from current production

Ran `scripts/onset_snap_ass.py` off the new branch: **32 fresh** `.onsetsnap.ass`
(the script writes nothing for 0-snap songs; deleted the leftover stale Mulan
file). Result: **407 real snaps** (median 0.50 s, max 2.83 s), **0 collisions**
introduced. Conclusion: **onset-snap is NOT redundant** on the new matcher — it
still corrects the subtle early-onset smear on ~407 line-initial words. Strong
correctness signal: Belle "Little town" lands at 0:17.89, matching the
hand-verified 17.90 benchmark from the original work.

Biggest snaps (>=1.5 s, eyeball for over-firing): narrative lines like Popular
"When I see depressing creatures" (+2.81 s) and Belle "Little town" (+1.77 s)
look like correct smear fixes; short/held-note lines like "For good" (+2.47 s),
"Bees'll buzz" (+2.11 s), "Come on baby" (+2.57 s), and Domino "You got me
losin' my mind" (+2.49 s, a known-ambiguous soft pickup) are the ones to check.

### 5. Code review + fixes (amended)

Ran `/code-review` (high effort, 3 finders on CLAUDE.md's Correctness /
Robustness / Simplicity+Conventions axes, per the review-policy memory). No
common-path bug found (detector math, snap clamping, copy semantics, and
short-input fallbacks are sound). Two edge/quality findings applied and
**amended** into the commit (`da598c29` -> `d1bd4dee`):

1. **Decode `except` too narrow** — broadened
   `(CalledProcessError, FileNotFoundError)` to `(CalledProcessError, OSError)`
   so `PermissionError`/other `OSError` decode failures bail gracefully instead
   of crashing the stage. Matches the repo norm (`ffmpeg.py` catches `OSError`,
   `youtube_dl.py` catches `PermissionError`). Bail test parametrized to cover
   all three.
2. **Unclamped on-time-guard frame index** — clamped `a` into the envelope like
   `_detect_rise`, killing an empty-slice nan `RuntimeWarning` for a first word
   at/after the stem's end.

Left the third finding (offline `onset_snap_ass.py` re-derives the `.ass` wire
format — a DRY/single-source concern) as-is: it's an offline eyeball tool and no
shared `.ass` reader exists to reuse. Full suite **1303 pass**.

Refuted during verification: bail-stats KeyError (no consumer indexes the
sub-keys), odd-byte `np.frombuffer` (s16le is always even), missing word keys
(invariant of all timing sources), no-ffmpeg-timeout (consistent with
`ffmpeg.py`'s local-decode norm).

## Current state / next steps

- `onset_snap_on_ship` @ `d1bd4dee` is review-clean on the production base; full
  suite green; 32 fresh `.onsetsnap.ass` regenerated.
- **NEXT:** user eyeballs the fresh onsetsnap output (start with the held-note
  snaps above, the over-firing risk) to decide on folding onset-snap into
  `pathed_align_ship` proper.
- Upstream Belle/Next-Ten-Minutes-class failures (multi-singer windows, words
  placed in silence) are out of the forward-bounded snap's reach and belong to
  the matcher roadmap, not onset-snap.
