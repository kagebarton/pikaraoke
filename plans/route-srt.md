Model: Claude Fable 5 (design); executors per the phase table in `plans/PROGRAM.md`

# Route: uploader SRT (cue-align)

**Ladder rung 2, trusted-clock half.** The uploader's caption already
gives line-to-time 1:1 on the media's own clock, so global placement is
skipped entirely: cues are grouped into silence-bounded sections, words
are force-aligned *inside* each trusted cue window, and a monotone
max-match DP assigns them to lines. The matcher's structural artifacts
become impossible by construction.

**Status: SHIPPED — this is the production route today.**
`pikaraoke/lib/cue_align.py`, reached whenever `_load_lyrics` returns
non-empty `cue_spans`. Hardened through
`plans/completed/matcher-accuracy-hardening.md` phases 0-6, all closed.

**Standing constraint: this route must stay byte-identical through the
joint-matcher refit.**

**Aligner ruling (GATE S, S-2 SRT arm / S-C, 2026-07-20): CTC was
REJECTED here; whisper is retained by default.** The cap failure and
Ken's eyeball veto converged — CTC is weak on overlapping-voice
separation, and this corpus is full of duets. Note the asymmetry with
`plans/route-line-timing.md`, where S-2 selected CTC for the non-SRT
scaffold path; that genius-arm selection is now under re-read (M6),
partly *because* this arm's eyeball reframed the shared overlap metric.

**Rulings not to re-litigate** (from the shipped route's own hardening;
full detail in `plans/completed/matcher-accuracy-hardening.md`):

- **Never clamp a re-paced line's end to the next line's start.** ZAYN
  and Aladdin SRTs have genuinely overlapping cues (max 2 concurrent);
  the overlap is real duet vocals and clamping truncates them.
- **Containment belongs on re-align *acceptance*, not bad-line
  *detection*** — except for identical-text repeats, where
  `_repeat_detection_slacks` handles the aliasing.
- **ffmpeg `silencedetect` is rejected as a sectioning signal.** Only 67%
  of >1.5 s SRT section gaps overlap any detected silence at -30 dB. The
  SRT's own line gaps are the better phrase-structure signal.
- **Splitting sections harder does not fix drift.** The cue-fallback
  repair layers fixed it, not finer sectioning.

**Open work: none.** This lane is closed unless the refit disturbs it.

## Results log

### 2026-07-20 — Phase 3 S-C (CTC on the SRT cue-align corpus), Sonnet 5 executor, Windows box

Ken ruled the corpus for this arm is the full 16 SRT-sourced songs (see
the Phase 3 amendment above — the plan's original "13-song" figure never
matched the actual corpus). Run on the Windows dev box (uv, not conda;
first CTC/torchaudio use here — `torch 2.6.0+cu124`/`torchaudio
2.6.0+cu124`, CUDA confirmed, MMS_FA bundle freshly downloaded and
cached). Corpus presence re-verified after the machine move: all 16
songs' bundle/uploader-SRT/vocal-stem/`karaoke/<stem>.cuealign.ass`
(the on-disk 5b whisper baseline) confirmed present and stem-matched.

**Harness hook** (mirrors S-B's committed pattern exactly):
`cue_align_song.run_song` gained a `make_slice_align` parameter
(default: the existing whisper factory, `_make_slice_align`) and a
`--slice-align-module` CLI flag; `cue_align_corpus.py` gained the same
`--slice-align-module PATH` flag (dynamic `importlib` load of a
module's `make_slice_align`, identical to `scaffold_align_corpus.py`'s
loader) plus an output-suffix guard: with a module loaded, the corpus
runner writes `<stem>.cuealign.<module-stem>.ass` instead of
`<stem>.cuealign.ass`, so a probe run never overwrites the whisper
baseline files on disk (unlike the scaffold pair, this corpus script's
default output *is* the file S-C diffs against, so the collision is
real here and wasn't on the scaffold path). Import-smoke clean;
pre-commit (`--files scripts/cue_align_song.py scripts/cue_align_corpus.py`)
clean, no findings.

**Run 1 — whisper baseline refresh** (`cue_align_corpus.py --songs-root
D:/shared/pikaraoke-songs`): **16/16 placed, 0/16 drift**
(`gapL`/`instL` both zero every song) — reproduces the documented 5b
numbers almost exactly, including the five known `MAX_SECTION_DUR_S`
overlap deltas (Mirrors 0.7→0.8, ZAYN 7.8→4.1, Mena/Scott Whole New
World 2.6→2.1, Beauty and the Beast 0.2→0.1, Part of Your World
0.7→2.5 — all within rounding of the recorded figures). Confirms the
port/tree is unchanged on this box, consistent with the ground rules'
reuse license, but this is a fresh same-run table so S-2's comparison
below is apples-to-apples rather than cross-session.

**Run 2 — CTC arm** (`--slice-align-module scripts/sb_ctc_adapter.py`):
**16/16 placed, 0/16 drift**, all 16 songs completed with no
`RuntimeError`s (unlike S-B's scaffold corpus, no "targets length too
long" failures here — SRT sections are shorter/more numerous than the
scaffold path's warped sections). No emission cache existed on this
box (cold — Phase 1b's cache is scratchpad-local, box-specific), so
each song paid a fresh full-song MMS_FA forward pass; still
substantially faster wall-clock than the whisper arm (92 log lines vs.
774 — no per-slice ffmpeg+subprocess round trips).

Per-song comparison (whisper → CTC; `ovl` = worst inter-line overlap,
`rep%` = repaced-from-cue fraction of placed lines):

| song | lines | wh ovl | ctc ovl | Δovl | wh rep% | ctc rep% |
| --- | --- | --- | --- | --- | --- | --- |
| Like I Love You | 84 | 0.0 | 0.1 | +0.1 | 0.0 | 1.2 |
| Let It Go | 47 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| More Than That | 39 | 0.0 | 0.0 | 0.0 | 5.1 | 0.0 |
| Mirrors | 120 | 0.8 | 2.6 | **+1.8** | 6.7 | 16.7 |
| Selfish | 79 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| ZAYN Whole New World | 60 | 4.1 | 0.4 | -3.7 | 3.3 | 1.7 |
| Mena/Scott Whole New World | 54 | 2.1 | 1.8 | -0.3 | 0.0 | 1.9 |
| For Good | 60 | 1.7 | 0.0 | -1.7 | 8.3 | 0.0 |
| Part of Your World | 54 | 2.5 | 0.0 | -2.5 | 0.0 | 0.0 |
| Rock Your Body | 103 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Can You Feel the Love Tonight | 32 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Beauty and the Beast | 56 | 0.1 | 0.0 | -0.1 | 7.1 | 1.8 |
| Happier | 38 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Incomplete | 27 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Speechless | 49 | 0.1 | 0.0 | -0.1 | 4.1 | 0.0 |
| Bye Bye Bye | 75 | 1.3 | 0.0 | -1.3 | 1.3 | 2.7 |

S-2's three mechanical inputs, computed same-run:

- Mean re-pace %: whisper 2.25% vs CTC 1.62% (CTC lower).
- Mean worst-overlap: whisper 0.794s vs CTC 0.306s (CTC lower).
- Flag count (gapL + instL): 0 vs 0 on both arms (tie).
- Per-song cap ("no song > 1.0s worse on overlap"): **Mirrors
  violates it** — CTC's worst overlap is 1.8s worse than whisper's on
  that song (0.8s → 2.6s), the same song whose repace fraction nearly
  triples (6.7% → 16.7%). No other song comes close (next-largest
  same-direction delta is Like I Love You at +0.1s). Note for the
  read-off: Mirrors is the one song the 5b Ken-read already flagged as
  *not* a genuine two-voice overlap (unlike the other four
  `MAX_SECTION_DUR_S`-delta songs) — its whisper-arm 0.7→0.8s bump was
  already anomalous before CTC made it worse.

This is a table, not a verdict — S-2's rule requires *all three*
aggregate metrics to be at least as good AND the per-song cap to hold;
two of three aggregates favor CTC clearly but the cap fails on one
song. Left for Opus's read-off + Ken's eyeball veto (mechanical
read-off role per the model-switching table); Mirrors' `.cuealign.ass`
vs `.cuealign.sb_ctc_adapter.ass` are both on disk at
`D:/shared/pikaraoke-songs/karaoke/` for the eyeball.

### 2026-07-20 — Ken's eyeball (S-C) — CTC weak on overlapping-voice separation

Ken eyeballed Mirrors, ZAYN's Whole New World (End Title), Part of Your
World, and Bye Bye Bye (whisper vs CTC, per the mpv A/B commands
above). Verdict: **CTC has tighter word timing but struggles with
actual overlapping voices that whisper better separates.** This is the
eyeball veto S-2's SRT-arm clause calls for ("the same rule plus Ken's
eyeball veto — extra caution on the proven path") — it both explains
Mirrors' per-song cap failure mechanically (a real overlapping-vocal
passage, not a degenerate-anchor artifact) and reframes the
overlap-improvement songs: an overlap number dropping to 0.0s under
CTC is not unambiguously a fix if CTC's failure mode on overlapping
voices is to under-report rather than mis-time them — worth weighing
against the tighter-timing win rather than reading the aggregate means
at face value.

### 2026-07-20 — GATE S read-off (S-2, SRT arm / S-C) — CTC rejected on the SRT path; whisper retained by default, cap failure and eyeball veto converge

**(Opus executing the locked S-2 rule verbatim against the same-run S-C
table above; no threshold invented. Arithmetic reproduces the
executor's three inputs.)**

**S-2 SRT arm — WHISPER RETAINED (CTC not selected).** The rule
requires *all three* aggregates at least as good AND no song > 1.0 s
worse on overlap. The aggregates favor CTC (re-pace 1.62% vs 2.25%;
worst-overlap 0.306 s vs 0.794 s; flags 0 = 0 tie — "at least as good"
holds on all three). **But the per-song cap FAILS: Mirrors regresses
+1.8 s on worst-overlap (0.8 → 2.6), well past the 1.0 s bar.** One cap
violation is dispositive — the conjunction is not met. Mechanically
the rule falls to its **default clause: whisper, the proven default.**
This is objective from the table, not a judgment call.

**Ken's eyeball veto — corroborates, no daylight.** The SRT arm's rule
explicitly adds Ken's eyeball ("extra caution on the proven path"), and
it was supplied. His finding — CTC has tighter word timing but
struggles to separate genuinely overlapping voices — is not a *second,
independent* objection; it **explains why Mirrors fails the cap.** The
executor already noted Mirrors is the one 5b `MAX_SECTION_DUR_S`-delta
song Ken had flagged as *not* a genuine two-voice overlap and already
anomalous (0.7 → 0.8 pre-CTC); Ken's read reclassifies its CTC blowup
as a real overlapping-vocal passage CTC mishandles, not a
degenerate-anchor artifact. Mechanical failure and eyeball veto point
the same way. Additionally Ken's reframe — a CTC overlap dropping to
0.0 may be *under-reporting* a second voice, not resolving it —
undercuts confidence in the two aggregates that favored CTC, so even
the "2-of-3 clearly better" reading is softer than the numbers alone
suggest. This strengthens, and does not complicate, the whisper
outcome.

**STOP status — none. The rule resolves this without a fresh Ken
decision.** Unlike S-1 (whose conjuncts left load-bearing gray zones
needing ratification), S-2 here is self-contained: cap fail → default
→ whisper, and the pre-registered eyeball input landed on the same
result. No open gray-zone call remains for Ken; the veto he already
gave is the input the rule asked for, and it agrees with the mechanics.
GATE S's SRT arm is closed by execution.

**Appendix D constant (updated wording, supersedes the S-4 "S-C
unrun" line):** *S-2 = CTC on the genius-origin scaffold path; whisper
retained on the SRT cue-align path — S-C ran 2026-07-20 (16-song SRT
corpus), CTC cleared all three aggregates but failed the per-song
overlap cap on Mirrors (+1.8 s), a real overlapping-vocal passage;
Ken's eyeball veto corroborated (CTC weak on overlapping-voice
separation), so the rule defaults to whisper. Edge-snap default on the
SRT path is unaffected (stays as-is; the CTC snap-off default applies
only where CTC is the aligner).*

---
