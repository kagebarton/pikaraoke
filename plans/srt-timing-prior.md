# SRT timing prior for the joint matcher

Model: Claude Fable 5

Status: **shipped 2026-06-12.** Design recorded 2026-06-11; steps 1–2
(LRCLIB references + ceiling) and step 3 (implementation, measured
75 → 50 corpus gross) completed 2026-06-12 — see "Step 3 results"
below.

## Motivation

The YouTube SRT (manual captions) is the last timing signal the matcher
does not use. For songs whose lyrics were sourced from the SRT
(`lyrics.source_kind == "srt"`), every lyric line *already carries an
uploader-synced timestamp on disk* that the matcher discards. Verified on
the corpus (2026-06-11): 9/23 songs are srt-sourced, and the line-to-cue
mapping is perfect identity on all three spot-checked songs (Mirrors
120/120, Bye Bye Bye 75/75, Can You Feel the Love Tonight 32/32). No
mapping risk, no new download: the timing comes free with the text.

LRCLIB is *not* available to the matcher — standing constraint, verbatim:
"I wanted the LRCLIB timings to only be used as a way to verify matcher
coverage and accuracy, they will not be available to the matcher or the
deployed project." The YT SRT is different: it ships with the video and is
available at deploy time.

## Design: audio calibrates the clock, SRT fills the gaps

The SRT clock has an unknown display lead (the eval fits a per-song offset
for exactly this reason), so raw cue times cannot be trusted. Pass-1
provides the calibration:

1. **Pass-1 joint DP as today** (audio only).
2. **Fit the offset**: robust median of (placed_start - cue_start) over
   trusted lines — the Phase 3 anchor criteria are directly reusable
   (>=4 tokens, sheet-unique normalized sequence, transcribe corroboration
   >= 0.75). Check the spread (MAD); if anchors are few or the spread is
   wide (variable lead, sloppy captions), bail out and change nothing.
3. **Repair**: lines where pass-1 disagrees with cue+offset by more than
   ~2 s are by construction the gross-error population (wrong chorus
   instance, drifted interp) — snap to cue+offset, or treat as suspects
   for the windowed re-align.
4. **Coverage fill**: unplaced/interp lines get cue+offset, tagged
   `source="srt"`.

Improves both axes. The coverage win lands exactly where audio
fundamentally cannot: the Mirrors outro (lead vocal over chant — parked as
unplaceable from audio) has uploader-synced caption times for every one of
those lines, as do the ~12 lines corpus-wide that the Phase 3
susp_careful merge honestly un-places.

Composes with Phase 3: SRT-corroborated lines make extra span anchors,
shrinking re-align windows; SRT-vs-pass1 disagreement is a sharper suspect
detector than transcribe corroboration alone.

## Eval circularity (the trap)

The 9 srt-sourced songs are currently *scored against that same SRT*.
With SRT-informed placement their gross count goes to ~0 by construction —
the eval would grade the matcher against its own input. Required order:

1. **Fetch LRCLIB syncs for the 9 srt-sourced songs** (mainstream titles;
   LRCLIB almost certainly has them) and hand-vet like the existing 14.
   LRCLIB stays verification-only, consistent with the constraint.
2. **Measure the ceiling with zero matcher code**: score the raw
   offset-corrected SRT cues themselves against LRCLIB. If manual captions
   are accurate to ~0.5 s after the offset fit, the design above is mostly
   plumbing; if some videos have sloppy or variable-lead captions, the
   bail-out spread check earns its keep and the repair threshold gets
   tuned from data.
3. Only then implement, and measure those 9 songs against the LRCLIB
   reference.

## Sizing

The srt-sourced songs hold roughly a third of the 58 remaining corpus
gross (post-Phase-3; Mirrors 14 alone), and all of those are by definition
disagreements-with-SRT — large honest upside if step 2 confirms caption
quality. Production cost is near zero (no GPU work; pure post-pass
arithmetic).

## Step 2 results (2026-06-12): the ceiling measurement

LRCLIB syncs fetched for 8 of the 9 srt-sourced songs. **For Good has
none** — it is a live #OutOfOz performance; LRCLIB syncs target studio
masters, and a different performance's deltas would be meaningless. It
stays SRT-scored, which becomes circular once the prior ships: exclude
it from post-prior eval claims (58 scored lines). Two extra files were
fetched for songs without capture bundles (It's Gonna Be Me,
Incomplete) — corpus-expansion candidates if stems + captures are made.

Vetting: all 8 files parse cleanly; mapping rates against the sheet
lines range 36/39 (More Than That) down to 30/79 (Selfish — LRCLIB's
sync is coarser than the SRT's line splits; unmapped lines fall out of
scoring, the conservative direction). No structural breaks; drift fit
~0 everywhere; SRT-vs-LRCLIB master offsets up to ±20 s absorbed by the
per-song fit (irrelevant in production, where the offset is fit
pass-1 ↔ SRT on the same video clock). Triangulation flagged ~6 lines
of LRCLIB-side noise (audio + SRT agree against them: Let It Go L0/L34,
Mirrors L57/L90, Bye Bye Bye L73 +20 s, More Than That L21).

**Ceiling** (raw SRT cue starts as "placed", scored against LRCLIB with
the production offset+drift fit; /tmp/eval_srt_prior/ceiling.py):

| | scored | med-of-med | ≤0.5 s | ≤1.0 s | gross |
| --- | --- | --- | --- | --- | --- |
| SRT cues vs LRCLIB (8 songs) | 350 | 0.27 s | 74.0% | 91.4% | **9** |
| matcher pass-1 vs LRCLIB (same songs) | 337 | — | — | — | **34** |

Per-song ceiling gross: Mirrors 5 (of 106 lines), Let It Go 2, More
Than That 1, Bye Bye Bye 1, rest 0. Of the 9, triangulation attributes
most to LRCLIB noise or threshold-borderline cases, not caption error.

**Verdict: captions are accurate — the design is mostly plumbing.**
Verified headroom ≈ 25 gross lines on these 8 songs (34 → ~9 floor), of
which 21 are the Mirrors chant outro where matcher-vs-SRT and
matcher-vs-LRCLIB agree to within fractions of a second on how wrong
the audio placement is — two independent references corroborate the
SRT cue times for exactly the lines audio cannot place.

Nuances for implementation:

- Two songs have ~0.5 s-sloppy captions (More Than That 50% ≤0.5 s,
  Let It Go 47%): cue+offset is gross-repair quality, not sub-second
  polish. Snap only disagreeing (>~2 s) and unplaced lines; never blend
  cues into well-corroborated audio placements.
- The repair threshold ~2 s is well-supported: ceiling gross rate is
  2.6% — snapping a >2 s disagreement to cue+offset is overwhelmingly
  likely to improve it.
- Honest pre-prior baseline (eval `--prefer-lrclib`, all 23 songs):
  925 scored / 0.36 s / 62.6% ≤0.5 s / 82.7% ≤1.0 s / **78 gross**
  (vs the SRT-circular 1070/77 — gross ~flat confirms pass-1 never
  benefited from the circularity; the scored drop is LRCLIB's coarser
  mapping). /tmp/eval_srt_prior/baseline_lrclib.json is the comparison
  point for the implementation.

Artifacts: /tmp/eval_srt_prior/{ceiling.py,ceiling.json,
baseline_lrclib.json}; references in `<songs>/lrclib/` (8 new + 2
extra); `--prefer-lrclib` shipped in scripts/eval_alignment.py
(default path verified bit-identical to the Phase 2c baseline).

## Step 3 results (2026-06-12): implementation shipped

`pikaraoke/lib/srt_prior.py` (pure logic, windowed_realign style):
`cue_spans_from_srt` (the production cue extraction; `_load_lyrics` and
the eval's `parse_reference_cues` both delegate to it) and
`apply_srt_prior` (anchor reuse via `analyze_pass1`, median offset fit,
MAD bail-out, snap repair, coverage fill). Hooked at the end of
`_run_joint` after the windowed re-align, behind
`PipelineConfig.joint_srt_prior` (default on), degrade-on-exception.
Eval replays it with `--srt-prior` (pass-1 + prior; production also has
pass 2 between them, so production should only be better). Knobs:
`PRIOR_MIN_ANCHORS = 4`, `PRIOR_MAX_MAD_S = 0.75`,
`SNAP_DISAGREE_S = 2.0`.

Measured (`--prefer-lrclib --srt-prior`, vs the honest baseline; For
Good excluded as circular — its 60 lines score against the SRT the
prior consumes):

| 22 lrclib-scored songs | scored | med-of-med | ≤0.5 s | ≤1.0 s | gross |
| --- | --- | --- | --- | --- | --- |
| baseline (pass-1) | 867 | 0.36 s | 63.6% | 82.9% | **75** |
| with SRT prior | 880 | 0.33 s | 66.1% | 85.7% | **50** |

- **No song regressed on any column.** The −25 gross matches the
  step-2 verified headroom exactly. Mirrors: 24 → 3 gross (22 snapped,
  11 filled — the chant outro renders for the first time); Speechless
  1 → 0; Can You Feel the Love Tonight 2 → 0; Part of Your World
  2 → 1.
- **Zero bail-outs fired**: anchors 16–32 per song, anchor-residual MAD
  0.20–0.48 s — all under the 0.75 s threshold, including the two
  sloppy-caption songs (their slop is symmetric, so the median offset
  stays well-calibrated for gross repair).
- Remaining gross is dominated by reference noise: Let It Go L0/L34 and
  Mirrors L57/L90 are the step-2 LRCLIB-noise lines; Mirrors L76 is the
  repeated chant-outro text the two references map to different
  repetitions (ceiling already gross there, +32.6 s). Let It Go also
  shows ±0.03 s threshold-edge wobble (L35 2.03 → out, L12 → 2.01 in).
- Regression safety: with the flag off, both the default eval and
  `--prefer-lrclib` outputs are bit-identical to the pre-change
  baselines (the `parse_reference_cues` delegation is behavior-neutral).
- Artifacts: /tmp/eval_srt_prior/prior_lrclib.json (vs
  baseline_lrclib.json).

Follow-ups, not blocking: txt-sourced songs (14/23) are untouched by
design — their headroom is the subject of
plans/lrclib-timing-prior.md (and, for videos with manual captions,
the separate-SRT mapping open question below); For Good can only be
honestly evaluated by ear or a new reference.

## Open questions

- Cue granularity for *non*-srt-sourced songs whose videos still have
  manual captions (fetched lyrics + separate SRT): needs
  `map_lines_to_cues` at match time and a quality gate on the mapping.
  Empty set in the current corpus; defer until a real case appears.
- Whether repair should snap to cue+offset directly or only feed the
  windowed re-align suspect set (snap is simpler; re-align keeps word-level
  timing honest). *Step 2 data: snap is safe for the gross class
  (ceiling gross rate 2.6%) but two songs' captions are too sloppy for
  sub-second placement — snap repairs, don't refine with cues.*
- Per-section variable lead: offset-fit residual spread detects it; a
  piecewise or drift fit is possible but probably overkill.
