Model: Claude Fable 5 (design); executors per the phase table in `plans/PROGRAM.md`

# Cross-cutting: aligner choice, engine architecture, ruling provenance

Everything here spans **every** timing source, so it belongs to no single
lane. Three questions live in this file:

1. **Which aligner?** whisper `align_refine` vs CTC (torchaudio MMS_FA) —
   GATE C established CTC is usable at all; each lane then rules
   separately on whether to adopt it (SRT said no, the scaffold path said
   yes and is now under re-read).
2. **Which architecture?** the emission score-oracle probe (GATE O) that
   decided whether a full CTC sync *engine* was worth building.
   **Ruled: engine branch OFF (O-GRAY, Ken).**
3. **How well-evidenced is each live ruling?** the eyeball-provenance
   audit, which sorts the live set by whether a human ever witnessed the
   outcome.

Measurement infrastructure (the Phase 0 harness port) also lives here,
since every lane is measured with it.

## Phase 0 — port the scaffold machinery + fresh baselines

The scaffold core already exists on `pathed_align` (commit `835ba2c7`)
and was corpus-validated there; ship's `cue_align.align_song` is
already cue-source-agnostic (takes `cue_spans` + a `slice_align`
callable), so the port is three pure functions plus one helper — **not**
a driver rewrite. Read sources with `git show pathed_align:<path>`.

1. Port into ship `pikaraoke/lib/cue_align.py`:
   `densify_cue_spans`, `merge_cue_spans`, `warp_scaffold_cues`,
   `_theil_sen`, and the `DENSIFY_*` / `WARP_*` constants
   (`835ba2c7` lines ~90–370). **Drift check done at planning time
   (2026-07-18):** these functions depend only on `_tokenise_lines`,
   `median`, the new constants, and each other — all already
   imported/available in ship's module — so this is a near-verbatim
   copy-in. The port is **additive**; do not overwrite any ship
   function. Ship's `align_song` consumes `warp_scaffold_cues`' output
   list directly (same `list[tuple[float, float]]` contract as
   `cue_spans_from_srt`). Port the three functions' unit tests
   alongside, adapted to ship's test module layout.
2. Port `ytasr.cue_spans_for_lines` (on `pathed_align`'s `ytasr.py:142`;
   absent from ship) into ship `pikaraoke/lib/ytasr.py`, with tests.
   Also lift the 8-line `normalize_words` adapter (whisper-transcribe
   words → `{norm, start, end}`) from
   `pathed_align:scripts/lrc_align_song.py:67` into `ytasr.py` next to
   it (both the harness and Phase 2b's probe need it; a scripts-local
   copy would be duplicated three times).
3. New harness pair mirroring the existing cue pair's structure exactly:
   `scripts/scaffold_align_song.py` imports the reusable shims from
   `scripts/cue_align_song.py` (`_make_slice_align`, `find_vocal`,
   `artifact_metrics`, `max_line_overlap` — same `sys.path` sibling
   import `cue_align_corpus.py` already uses) and does:
   bundle + on-disk audio → anchors (`ytasr.cue_spans_for_lines` over
   YTASR words, and over bundle transcribe words via `normalize_words`)
   → `merge_cue_spans` (transcribe primary) → `warp_scaffold_cues` with
   an injected line-timing source (`--timing <sidecar|lrc>` flag) →
   `cue_align.align_song` → `karaoke/<stem>.scaffold.ass` (never the
   production name) + re-pace/overlap/flag/warp-fit report.
   `scripts/scaffold_align_corpus.py` mirrors `cue_align_corpus.py`:
   selects genius-origin bundles (`lyrics.source_kind != "srt"`), loads
   the model once, loops the single-song shim, prints the flag table.
   Design source: `pathed_align:scripts/lrc_align_song.py`.
   **Supersession note:** the matcher plan's Phase 0 banned porting that
   file as dead exploration; that ban was scoped to that plan's harness
   port and is deliberately superseded here — write the new harness
   clean against ship signatures rather than copying the dead file.
4. Baselines (paste into Results log):
   - Fresh joint-route replay over the genius-origin corpus songs at
     current HEAD (`scripts/replay_ytasr_third_source.py`) — the matcher
     has moved since the matcher plan's Phase 0 table; that table is
     stale for comparison purposes.
   - Cue corpus flag counts: reuse the 5b validation numbers if the tree
     is unchanged since, else re-run `scripts/cue_align_corpus.py`.
5. Commit: `feat(cue-align): port scaffold warp machinery from
   pathed_align` (+ separate harness commit).


## Phase 1 — CTC forced-align eyeball (GATE C) — EXECUTED

Executed 2026-07-18 per `plans/completed/ctc-forced-align-eyeball.md`; that file
carries the run summary pointer, this file's Results log carries the
GATE C verdicts (C-1 YES, C-2 YES-for-the-aligner, C-3 calibration +
constraints). S-B, S-B2 and S-C arms unblocked.


## Phase 1b — emission score oracle probe (GATE O)

Keystone for the engine architecture in `plans/ctc-sync-engine.md`:
does the CTC emission separate synced from desynced lines? Offline
scratchpad; GPU needed only for emission forward passes (seconds per
song). Honest precedent, stated up front: whisper align-word
probabilities failed the equivalent separation test (matcher plan
Phase 2a) — a NO here is a live outcome, and the fallback branch
exists for it.

1. Recompute emissions for the 33 songs (Phase 1's chunked recipe;
   cache each song's emission tensor in the scratchpad — the same
   compute-once/slice-many contract the engine plan's Appendix E
   specifies).
2. Score the existing `ctc_review/` alignments per word and per line:
   mean and min per-word emission score over the aligned span (the
   MMS_FA aligner's `TokenSpan.score`), z-normalized per song.
3. Labels — no new eyeballing needed:
   - **Desynced:** the sections Ken identified at GATE C — Bloodstream's
     crammed 2nd hook, the Popular and Defying Gravity desync
     stretches. Ken supplies rough time ranges; the executor records
     them as line-id ranges in the Results log before computing scores
     (pre-registered labels).
   - **Synced:** the same songs' good stretches per Ken, plus 5
     well-behaved songs end-to-end (Belle, Rock Your Body + 3 more of
     Ken's choosing).
   - **Cross-check:** score the *production* `.ass` timings for 2–3
     known-bad line groups from the matcher-plan era (e.g. Defying
     Gravity's OST-only outro lines 79–88) against the same emissions —
     phantom lines should score low against audio they were never in.
4. Rescue statistics (pre-registered 2026-07-19, Ken-directed) —
   computed in the **same run** whatever the primary read-off comes to,
   so a GATE O failure costs no second probe. Precedent motivating
   them: whisper's align *probabilities* failed the separation test,
   but the transcribe *cross-check* worked — so the rescues are
   categorical/relative tests, not more confidence scores. Every
   statistic is oriented higher = more synced, and every statistic
   (including step 2's two span-score variants) is computed both
   per-line and as a 5-line centered rolling median within its song
   (clamped at song edges) — the rolling variant targets the
   *sectional* shape of the GATE C desyncs:
   - **S-decode (decode agreement):** slice the cached emission over
     the line's aligned span (first word's start frame → last word's
     end frame); CTC greedy decode it (per-frame argmax, collapse
     repeats, drop blanks, MMS_FA charset); statistic =
     `difflib.SequenceMatcher(None, decoded, expected).ratio()` over
     space-stripped normalized character strings, where expected = the
     line's normalized alignment text. Asks "is this text actually
     there," which is immune to the quiet-but-correct trap (Girl in
     the Bubble's opener) that sinks confidence scores.
   - **S-shift (free-realign displacement):** re-align the line's
     tokens alone against the emission slice of its span padded
     ±5.0 s each side (clamped to song bounds; emission slicing, no
     audio recompute); statistic = −|realigned line midpoint −
     current line midpoint| in seconds. A synced line stays put; a
     desynced line jumps to where its text really is. Realign
     returning `None` → assign the labeled-set minimum; count these.
   - **S-tx (transcribe corroboration):** from the bundle's
     `transcribe_words` (verified present for 17/33 songs — including
     all three desync-labeled songs and Belle; SRT-era songs have
     `null`): window = line span padded ±2.0 s; statistic = |multiset
     intersection of the line's normalized tokens with the normalized
     transcribe tokens whose midpoints fall inside the window| /
     (line token count). Lines from songs without `transcribe_words`
     are excluded from S-tx only (record per-class coverage); S-tx is
     read off only if both label classes retain ≥ 10 lines.
5. Table: per-line distributions for synced vs desynced labels for
   **all ten variants** — {mean-word z, min-word z, S-decode, S-shift,
   S-tx} × {per-line, rolling-5} — each row with its AUC, overlap
   region, and candidate gate band. Ten AUCs is a multiple-comparisons
   exposure; the guard is that qualification below requires the
   conjunctive O-1 bars (band + phantom cross-check), never AUC alone.

**GATE O** — mechanical read-off (Opus executes; Ken rules the gray
zone). Compute AUC over the labeled lines for both line-score variants
(mean-word z and min-word z); the better variant is the candidate gate
statistic and both AUCs are recorded:

- **O-1 (separation clean):** best AUC ≥ 0.85, AND a cut exists with
  ≤ 10% of synced lines below it and ≤ 10% of desynced lines above it,
  AND the phantom cross-check agrees directionally (the production
  phantom group's median score < the synced group's p25). Licenses
  score-gating as a design primitive: 2b's emission-score statistics,
  Phase 3's S-B2 arm, and the engine branch (subject to S-5). The cut
  becomes the candidate gate band recorded in the build plan's
  Appendix E.
- **O-2 (separation absent):** best AUC < 0.65. The CTC-first engine
  architecture is OFF; the build plan proceeds on its fallback branch
  and this plan's remaining probes run exactly as originally written.
- **O-GRAY (anything else):** best AUC in [0.65, 0.85), or the band or
  cross-check fails. Ken decides with the table; the engine branch
  then requires his explicit GO recorded here. No model resolves the
  gray zone on its own.

A primary read-off of O-2 or O-GRAY is **not final** until GATE O′
below has been read — the rescue statistics were computed in the same
run, so the read-off is free.

**GATE O′ — rescue read-off (mechanical; Opus executes; runs only when
the primary read-off is O-2 or O-GRAY).** Apply O-1's exact bars —
AUC ≥ 0.85, AND a cut with ≤ 10% synced lines below / ≤ 10% desynced
lines above, AND the phantom cross-check directional (phantom group
scored with the *same* statistic against the production timings,
median < synced p25) — to each of the eight rescue variants (the
non-span-score rows of the table):

- **O-1′ (rescued separation):** at least one rescue variant clears
  all three bars. Adopt the highest-AUC qualifier; ties break
  S-decode > S-shift > S-tx (emission-internal preferred — no
  gate-time dependency on a transcribe pass having run). **O-1′
  counts as O-1 for every downstream license**: the engine branch,
  Phase 3's S-B2 arm, 2b's emission-score statistics, the build
  plan's licensing table, and Appendix C's emission-family rule. The
  adopted statistic, variant, and band are recorded in the build
  plan's Appendix E exactly as O-1's would have been.
- **O-2 (confirmed):** no rescue variant reaches AUC ≥ 0.65 either.
  The engine architecture is OFF; the build plan proceeds on its
  fallback branch exactly as originally written.
- **O′-GRAY (anything else):** Ken decides with the full ten-row
  table; the engine branch then requires his explicit GO recorded
  here. No model resolves it alone.

*Status (2026-07-19): read off — primary = O-GRAY, rescue = O′-GRAY
(no variant clears the band; five clear the 0.65 floor). Ken ruled:
engine branch OFF on this evidence — no explicit GO; scaffold-first
with the S-B windowed-CTC arm next. See the Results-log entry for the
verification, the ruling's riders (s_tx_roll5 kept as an optional
advisory demote-only signal; S-shift pad artifact noted, no
re-probe), and its consequences.*

If S-tx is the adopted gate statistic: whisper transcribe — already
retained in the engine branch for anchors — becomes a gate-time input;
a song with no transcribe output runs **ungated** on that route (lines
ship as aligned; containment per build-plan Appendix A, never a song
failure). The asymmetric-evidence requirement for corroboration
(agreement confirms sync; disagreement only demotes) is satisfied
structurally: the engine's score gate only ever routes lines into the
repair/fill loop (build-plan Appendix E) and never blocks a song.


## Verification matrix (Phase 0 / 2a code)

1. Import-smoke changed modules; full unit suite on the Linux box.
2. `pre-commit run --config code_quality/.pre-commit-config.yaml --files
   <changed>`.
3. The phase's own validation (baseline diff, corpus run).
4. Self-review (correctness / simplicity / robustness), commit, alert
   Ken when a /code-review batch + /compact point is reached.


## Results log

### 2026-07-19 — Phase 0 (port + harness + baselines), Sonnet 5 executor

Branch `timing_pillars` cut off `musix_ctc` (tip `22c15e4`).

**Port** (`pikaraoke/lib/cue_align.py`): `densify_cue_spans`,
`merge_cue_spans`, `_theil_sen`, `warp_scaffold_cues` +
`DENSIFY_DEFAULT_PACE_S`/`DENSIFY_MIN_LINE_DUR_S`/`WARP_MAD_GATE_S`/
`WARP_MIN_ANCHORS`, copied verbatim from `pathed_align:835ba2c7` per the
drift check — additive only, no existing function touched. 24 ported
unit tests (`TestDensifyCueSpans`/`TestMergeCueSpans`/
`TestWarpScaffoldCues`) pass unmodified against ship's module.

`pikaraoke/lib/ytasr.py`: `cue_spans_for_lines` (ported from
`pathed_align`'s `ytasr.py:142`, reusing ship's existing
`spans_from_candidates`/`CANDIDATE_MAX_EDIT_RATIO` verbatim — only the
`find_candidates` import and the function itself were missing) +
`normalize_words` (lifted from `pathed_align:scripts/lrc_align_song.py:67`).
16 new tests (`TestCueSpansForLines` ported + 2 new `TestNormalizeWords`).

Full unit suite: **1482 passed** (was 1482 + this port's ~40 new tests
net of the pre-existing 1456 5b baseline). Import-smoke clean.
Pre-commit (`--files` scoped to the changed modules): clean.

**Harness** (`scripts/scaffold_align_song.py` + `scaffold_align_corpus.py`):
built clean against ship signatures per the plan's supersession note
(not a port of the dead `pathed_align:scripts/lrc_align_song.py`).
Single-song driver builds ASR+transcribe anchors
(`ytasr.cue_spans_for_lines` over parsed YTASR words and over
`normalize_words(bundle["transcribe_words"])`, unioned transcribe-primary
via `merge_cue_spans`), warps an external `--timing {sidecar,lrc,none}`
scaffold onto them (`warp_scaffold_cues`), and hands the dense cues to
the shared production `cue_align.align_song` — reusing
`cue_align_song.py`'s `_make_slice_align`/`find_vocal`/`_ffmpeg`/
`_wav_duration`/`report` shims rather than duplicating the ffmpeg/whisper
plumbing. Writes `karaoke/<stem>.scaffold.ass` (never the production
name). The `sidecar` mode reads the Appendix B fetch-pillar sidecar
(`lyrics/<stem>.timing.json`, not yet populated for any song this
session — Phase 2a below only *fetches and persists* it, this run
carries no sidecar-mode corpus pass); `lrc` mode mirrors the dead
script's live LRCLIB fetch. Corpus runner mirrors `cue_align_corpus.py`'s
structure (song selection, model-once loop, flag table), selecting
`lyrics.source_kind != "srt"` bundles. Neither script has unit tests,
matching the existing SRT pair's precedent (GPU-driven, validated by
corpus run + eyeball, not pytest). Import-smoke clean; pre-commit
(isort reformatted the import block, otherwise clean).

**Baseline 1 — fresh joint-route replay** (genius-origin corpus, current
HEAD): `replay_ytasr_third_source.py /home/ken/pikaraoke-songs --alpha
2.0 --beta 2.0` (production's own `PipelineConfig` defaults). 17/17
genius-origin songs replayed, matches the 07-16 Environment-note
composite table in `plans/completed/matcher-accuracy-hardening.md` (matcher logic
unchanged since — 5b/Phase 6 touched only `cue_align.py`/docs) to
within the documented live-LRCLIB-fetch MAD jitter (e.g. Domino
0.43s/7a -> 0.39s/7a here; the 07-16 note already characterizes this as
network flake, not matcher drift, confirmed determinism-checked there
3x):

```
song                                            src        mad(best) alpha  beta crawl(rec>new)   overlap(rec>new)  placed(rec>new)   coverage
----------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary Ed 3src bail:wide_spread   2.0   2.0      4->3           0.2->0.2          51->51         51/89!
'Free' _ Official Lyric Video _ Sony Animation 2src        0.20s/16a   2.0   n/a      2->1           1.0->1.0          40->40          40/41
'Popular' - Wicked 20th Anniversary Edition _  3src bail:wide_spread   2.0   2.0      3->3           0.0->0.0          51->52         52/62!
Beauty and the Beast (1991) - Be Our Guest [UH 3src        0.16s/49a   2.0   2.0      1->0           0.0->0.0          77->77          77/77
Beauty and the Beast (1991) - Belle [UHD]---ot 3src        0.39s/55a   2.0   2.0      1->1           0.0->0.0         101->101       101/110
Ed Sheeran - Best Part Of Me (feat. YEBBA) (Li 3src bail:wide_spread   2.0   2.0      2->2           0.0->0.0          37->37          37/38
Ed Sheeran & Rudimental­ - Bloodstream [Offici 3src        0.60s/11a   2.0   2.0      1->1           6.7->6.7          47->48         48/74!
HUNTR_X 'This Is What It Sounds Like' (Music V 2src bail:wide_spread   2.0   n/a      0->0           0.0->0.0          32->33         33/53!
Jessie J - Domino (Official Video)---UJtB55Mao 2src         0.39s/7a   2.0   n/a      0->0           0.0->0.1          63->63          63/67
Josh Gad - In Summer (From 'Frozen'_Sing-Along 2src        0.22s/14a   2.0   n/a      2->2           0.0->0.0          29->29          29/31
Mulan _ I'll Make a Man Out of You _ @disneyki 3src bail:wide_spread   2.0   2.0      0->0           0.0->0.0          36->36         36/47!
NSYNC - Paradise                               2src        0.27s/10a   2.0   n/a      3->2           0.7->0.7          53->53         53/65!
Pocahontas - Colors of the Wind (Blu-ray 1080p 3src        0.19s/31a   2.0   2.0      2->2           0.0->0.0          37->37          37/37
Seasons of Love (HD)---UvyHuse6buY             2src         0.52s/5a   2.0   n/a      8->3           0.0->0.0          25->25         25/34!
The Lion King - Hakuna Matata Music Video I 4K 3src         0.41s/8a   2.0   2.0      4->3           0.0->0.0          33->33         33/40!
The Next Ten Minutes Lyrics---0j8kL24ph8U      2src        0.46s/52a   2.0   n/a      5->2           0.0->0.0          67->67          67/71
Wicked - For Good  (2025) 4K - The Girl in the 3src        0.39s/15a   2.0   2.0      2->2           0.0->0.0          29->29         29/36!
```

This table, not the 07-16 one, is Phase 3's fresh joint-baseline
comparison point (S-A criterion (a)).

**Baseline 2 — cue corpus flag counts (SRT songs)**: reused per the
ground rules' explicit license ("reuse the 5b validation numbers if the
tree is unchanged since") rather than re-run — `cue_align.py`'s SRT-path
logic (`segment_by_gaps`/`align_song`/`repace_bad_lines`) is untouched
by this session's port (additive-only, new functions never called by
the SRT path), so the 5b-validated state
(`plans/completed/matcher-accuracy-hardening.md`, "Phase 5b implement +
validation") still holds exactly: **16/16 SRT songs, 0/16 drift**
(`gapL`/`instL` both zero every song), 0 lines placed->hidden, flag
table identical to the 07-16 Phase-0-baseline table there except 5
known overlap deltas from the `MAX_SECTION_DUR_S` section-cap fix
(Mirrors 0.7->0.8, ZAYN 7.8->4.0, Mena/Scott 2.6->2.1, Beauty and the
Beast 0.2->0.1, Part of Your World 0.7->2.5s — Ken's 5b read: all but
Mirrors are genuine two-voice overlaps, not defects). No fresh GPU run
executed this session for this baseline.

**Commits**: `feat(cue-align): port scaffold warp machinery from
pathed_align` (lib + tests) and `feat(scripts): scaffold-align harness
pair` (the two new scripts), per the plan.

### 2026-07-18 — Phase 1 (CTC eyeball) run + GATE C

Run (Ken, scratchpad probe per `plans/completed/ctc-forced-align-eyeball.md`;
source of numbers: `pikaraoke-songs/ctc_review/SUMMARY.md`): **33/33
songs aligned on plain vocal stems, zero failures, zero degenerate
flags.** Only flagged row: Seasons of Love "late start 43.16s" —
explained, not a defect (~40s piano vamp plus the OOV-skipped numeral
opener `525,600`). Chunked-emission recipe held on the 6 GB card
through the 500s Mirrors.

GATE C (Ken eyeball verdicts 2026-07-18; Fable judge read):

- **C-1: YES — S-B and S-C unblocked.** Ken: best line-start/interior/
  end syllable timing seen in this project; 1:1 text/audio songs
  "undoubtedly superior", many acceptable even *without* windowing;
  recovers lines whisper drops (the long held "Free, free" in Free).
- **C-2: YES for the aligner.** All 23 production-dereverbed songs held
  on wet stems; Girl in the Bubble (the canonical de-reverb case)
  essentially perfect — its 0.00s first word is a quietly-sung long
  note, not intro smear. Recorded nuance: the de-reverb gate's *other*
  consumers (transcribe → tier-2 anchors, tier-1 verify) may still need
  it; decided at the Appendix D lock.
- **C-3 (calibration, confirmed + extended):** version-mismatch songs
  (Bloodstream, Popular, Defying Gravity) sync/desync in sections;
  desynced lines borrow syllable-level timing from the wrong words
  (Bloodstream visibly crams the missing 2nd hook, then re-syncs at the
  2nd verse — not always that clean). Synced sections still beat
  whisper on the same songs. Two hard constraints for any production
  CTC adapter: MMS_FA is Latin-only (hangul dropped on HUNTR_X — CTC
  routes need a non-Latin fallback, relevant to What It Sounds Like in
  tier 2) and numerals need spoken-form expansion (`525,600`, `30`).

New observations recorded for later locks (not scope changes now):

- Edge/onset snap may be redundant — possibly harmful — on CTC-timed
  lines (Ken: CTC edge timing already beats the snap's). Whether the
  snap post-passes run on CTC-timed routes is an Appendix D decision
  item with S-B data.
- CTC words as a joint-matcher (tier-3) evidence/align source — Ken:
  synced sections outperform whisper even on mismatch songs. Promoted
  to the optional S-E arm (2026-07-18 revision); also informs the
  build plan's deletion inventory.

### 2026-07-19 — Phase 1b pre-registered labels (Ken time ranges → line-id ranges), Sonnet 5 executor

Ken supplied rough time ranges (2026-07-19) for 6 songs' desync
sections plus 4 additional well-behaved end-to-end songs. Per step 3's
instruction ("Ken supplies rough time ranges; the executor records
them as line-id ranges... before computing scores"), each range is
mapped here against that song's bundle `output_line_timings` (line
included iff its `[start, end]` span overlaps Ken's range at all;
boundary lines noted). No scores computed yet — this is the label
registration only.

**Desynced (line-id ranges, per song):**

| song | Ken's range | line-ids | note |
| --- | --- | --- | --- |
| Bloodstream | start–0:06 | 0–1 | line1 (hummed intro) extends to 0:11.26, only its head is in-range |
| Bloodstream | 1:55–2:00 (crammed 2nd hook) | 26–31 | lines 27–30 are 4 repeats collapsed onto one identical [1:57.94–1:58.84] span — the cram signature itself |
| Bloodstream | 2:20–2:40 | 36–38 | lines 36/37 are concurrent duplicate spans |
| Bloodstream | 2:58–end | 51–73 | includes the fully-collapsed zero-width block 66–73 [3:52.33–4:02.17] shared by 8 lines |
| Popular | start–0:04 | 0–5 | lines 0–4 are spoken dialog collapsed to [0:00.00–0:02.92] |
| Popular | 2:28–2:32 | 50–51 | |
| Popular | 2:45–2:51 | 59–61 | |
| Defying Gravity | 0:07–0:56 | 0–31 | lines 0–20 are the pre-song dialog block collapsed to [0:00.00–0:08.36] |
| Defying Gravity | 1:38–1:41 | 44–46 | |
| Defying Gravity | 2:19–2:36 | 55–66 | includes the 9-line collapsed dialog block 56–64 [2:26.67–2:30.59] |
| Defying Gravity | 3:29–end | 78–88 | **= the matcher-plan-era known-bad OST-only outro group (79–88)** — reuse directly as step 3's phantom cross-check fixture, no separate list needed; line80 is zero-width |
| Hakuna Matata | 0:30–0:48 | 3–4 | line4 nominally ends 0:35.32; the described "drag" is the 14.4s unfilled gap to line5 at 0:49.72, not a sheet line — flag as a fallback/interpolation artifact, not a scored line span |
| Hakuna Matata | 1:55–end | 29–39 | line28 ends 1:53.98, just before Ken's 1:55 mark, so it's excluded by the overlap rule; lines 34–39 are zero-width (the dialog swallowed them to nothing — expected desync signature) |
| Rock Your Body | 2:28–3:10 | 68–72 | ~31.5s unfilled gap after (2:40.73→3:12.24) — the quiet-outro/adlib stretch Ken flagged has no sheet line to score at all |
| Rock Your Body | 4:00–end | 95–102 | ~18.3s unfilled gap before (3:57.65→4:15.99), same signature |
| Zayn | 1:55–2:05 | 28–33 | lines 32/33 overlap out of chronological order in the production timing itself (line33 starts 2:03.86, before line32's 2:04.28) — the "overlapping vocals" Ken described |
| Zayn | 3:30–end | 55–59 | |

**Synced — same songs' good stretches:** the complement of the above
ranges within each of the 6 songs (e.g. Bloodstream lines 2–25, 32–35,
39–50, 74 is n/a since 73 is last — i.e. everything not listed above).
Zero-width lines inside a "good" complement (none found outside the
ranges above) would be excluded the same way at scoring time.

**Synced — well-behaved end-to-end:** Belle (110 lines), Girl in the
Bubble (36 lines), John Legend/Ariana Grande Beauty and the Beast (56
lines), Incomplete (27 lines). **Only 4, not the plan's target of 5**
— Rock Your Body was the plan's other suggested pick, but Ken's own
data for it (above) shows two real desync stretches, so it no longer
qualifies as end-to-end clean and was not substituted into this set.
Flagging for Ken/Opus visibility, not blocking: the labeled pool is
already large (6 partial + 4 full songs) and step 5's read-off doesn't
require exactly 5 end-to-end songs, but a 5th is Ken's to add if he
wants one.

**Not yet done (at label-registration time):** emissions had not been
recomputed, no scores existed, no AUCs computed — see the follow-on
entry below for the completed run.

### 2026-07-19 — Phase 1b run (GATE O primary + GATE O′ rescue), Sonnet 5 executor

Scratchpad scripts (never committed, per ground rules — this is neither
of the two named exceptions):
`phase1b_score_oracle.py`/`phase1b_labels.py`/`phase1b_auc.py`/
`phase1b_phantom.py`/`phase1b_rescue.py`/`phase1b_rescue_auc.py`.
Emissions, line-scores, and rescue-scores caches also live in the
scratchpad, not the repo.

**Step 1–2 (emission recompute + primary score).** Re-ran the eyeball
probe's chunked ~20 s recipe (`plans/completed/ctc-forced-align-eyeball.md` §"CTC
recipe" — that script itself was never on disk, run by Ken directly
from a scratchpad copy) over all 33 corpus songs: MMS_FA emission
cached per song, forced aligner re-run over `align_lines` to recover
per-word `TokenSpan.score` (not persisted by the original eyeball run),
grouped into per-line mean/min-word raw scores, z-normalized per song.
**33/33 clean**, no failures. One environment fix needed: this
torchaudio build's `torchaudio.load` requires `torchcodec`, not
installed in `pik`; switched to `soundfile.read` for the decoded-wav
load, no recipe change.

**Implementation-time bug caught + fixed (S-decode only, step 4):** a
raw unconstrained argmax over the emission's full 29-class output
*always* selects the star class (id 28) — checked directly:
`emission[:, 28]` is exactly `0.0` (log-prob 1.0) on every frame of
every song inspected, a constant DP-padding column the aligner appends
for its own constrained-alignment use, not a real per-frame prediction.
Greedy decode must argmax over `emission[:, :28]` only; fixed before
any S-decode numbers were recorded (caught via a targeted debug probe
on Popular line 5, where decode against the padded 29-class slice
produced an empty string every time).

**Step 3 (labels + cross-check).** Labels: the pre-registered ranges
above (140 desynced lines, 517 synced lines — the 6 partial songs'
flagged ranges + complements, plus the 4 end-to-end songs). Coverage:
100% of labeled lines scored (every line in every labeled range has at
least one alignable word — the sheet-text-driven score doesn't depend
on production's own placement, so production's degenerate/zero-width
groups don't cost coverage here). Phantom cross-check (Defying Gravity
79–88, production-placed spans, `mean_word_raw` scored directly against
those fixed spans — not the CTC's own free placement): 9/10 lines
scored (line 80 has no production span), z-normalized against Defying
Gravity's own song-level mean/sd —

```
line  span(s)              mean_word_raw   mean_word_z
 79   [210.47,214.63]         0.0549          -0.764
 81   [214.63,217.07]         0.2037          -0.026
 82   [216.47,217.17]         0.0114          -0.760   (concurrent w/ 83,84)
 83   [216.47,217.17]         0.0470          -0.673
 84   [216.47,217.17]         0.0343          -0.624
 85   [217.17,218.85]         0.1622          -0.184
 86   [218.85,219.51]         0.0104          -0.763
 87   [219.51,221.55]         0.0108          -0.760
 88   [221.55,225.25]         0.0989          -0.426
```

phantom median z = **−0.624**, vs the labeled synced pool's p25 on the
same statistic = **−0.719** (from the table below). −0.624 is *not*
below −0.719 — **the cross-check does not confirm directionally** on
the candidate primary statistic (mean_word_z).

**Steps 4–5 (rescue stats + full ten-row table).** Computed all five
statistic families for the 10 labeled songs, each per-line and as a
5-line centered rolling median (clamped at song edges): mean/min-word-z
(reused from the primary pass), S-decode (`difflib.SequenceMatcher`
ratio, decoded vs. expected normalized text over the line's own aligned
span), S-shift (`-|realigned midpoint − current midpoint|`, realigned
within the line's own span ±5.0 s, clamped to song bounds), S-tx
(normalized-token multiset-intersection fraction against
`transcribe_words` in the line's span ±2.0 s — **4/10 labeled songs
have no `transcribe_words`**: Rock Your Body, Zayn, John Legend/Ariana
Grande Beauty and the Beast, Incomplete; S-tx coverage drops to 116
desynced / 295 synced with those excluded, still ≥10 per class so it is
read off per the plan's coverage rule).

**GATE O primary table** (mean-word-z, min-word-z; AUC = P(random
synced line scores higher than random desynced line), band = does a
cut exist with ≤10% synced below it and ≤10% desynced above it):

| variant | AUC | synced p25 | band cut | synced_below | desynced_above | band_ok |
| --- | --- | --- | --- | --- | --- | --- |
| mean_word_z | 0.7162 | −0.719 | −0.260 | 38.7% | 17.9% | **False** |
| min_word_z | 0.5693 | −0.630 | −0.153 | 58.0% | 10.0% | **False** |

Best AUC (mean_word_z, 0.7162) is in [0.65, 0.85); band fails; phantom
cross-check fails directionally (above). Per-song coverage: 140/140
desynced lines scored, 517/517 synced lines scored across all 10
songs — full detail (per-song breakdown) in the scratchpad
`auc_final.txt`, reproducible via `phase1b_auc.py`.

**GATE O′ rescue table** (the 8 non-primary-per-line rows: mean/min-
word-z rolling-5, S-decode/S-shift/S-tx × {per-line, rolling-5}); O-1's
exact bars applied identically to each:

| variant | n_desync | n_sync | AUC | band cut | synced_below | desynced_above | band_ok |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mean_word_z_roll5 | 140 | 517 | 0.7536 | 0.003 | 43.7% | 10.0% | False |
| min_word_z_roll5 | 140 | 517 | 0.5931 | −0.375 | 49.1% | 13.6% | False |
| s_decode | 140 | 517 | 0.7933 | 0.358 | 33.1% | 13.6% | False |
| s_decode_roll5 | 140 | 517 | 0.8270 | 0.360 | 30.6% | 7.9% | False |
| s_shift | 140 | 517 | 0.5386 | −1.476 | 27.9% | 62.9% | False |
| s_shift_roll5 | 140 | 517 | 0.5824 | −1.476 | 14.1% | 65.0% | False |
| s_tx | 116 | 295 | 0.8767 | 0.652 | 20.3% | 7.8% | False |
| s_tx_roll5 | 116 | 295 | **0.8964** | 0.633 | 18.3% | 8.6% | False |

**No variant's band clears the ≤10%/≤10% bar** — including s_tx and
s_tx_roll5, whose AUCs alone clear the O-1 AUC bar (≥0.85). Since O-1′
requires all three bars (AUC + band + phantom) on the *same* variant,
band failure alone already disqualifies every rescue variant; the
phantom cross-check was not separately computed for the 8 rescue
variants; per the S-1 read-off's own precedent for a moot conjunct,
that check would not change the outcome once band has failed.

**Observation, not a proposed change:** S-shift's AUC (0.54/0.58, near
chance) is the weakest of the eight — plausibly because its pre-
registered ±5.0 s realign pad is narrow relative to this corpus's
actual desync spans (several run 15–60 s, e.g. Defying Gravity's dialog
blocks, Hakuna Matata's swallowed outro), so a desynced line's true
position is often outside the window the realign is allowed to search,
capping how far it can jump regardless of how wrong the current
placement is. The pad is a locked plan constant; flagging for Ken/Opus
to weigh, not adjusting it unilaterally.

**What this does and doesn't settle.** Mechanical facts only, no
verdict computed (executor discipline — Judge is Opus, escalations go
to Ken): best primary AUC (0.7162) is ≥0.65 so the primary read-off is
not O-2 by that bar; it is also not O-1 (AUC <0.85, band fails, phantom
fails). Of the 8 rescue variants, none clears all three O-1 bars
simultaneously (band is the universal blocker), but several clear the
AUC ≥0.65 floor (mean_word_z_roll5, S-decode, S-decode_roll5, S-tx,
S-tx_roll5), so the rescue read is not a clean O-2 confirmation either.
Reproducible via `phase1b_auc.py` / `phase1b_rescue_auc.py` /
`phase1b_phantom.py` against the cached scratchpad emissions.

### 2026-07-19 — GATE O + GATE O′ read-off and Ken's ruling — engine branch OFF; S-B next

**Read-off (mechanical, applied to the run entry above):** primary =
**O-GRAY** — best AUC 0.7162 (mean_word_z) lies in [0.65, 0.85), the
≤10%/≤10% band fails (38.7%/17.9% at the best cut), and the phantom
cross-check fails directionally (phantom median z −0.624 is not below
the synced p25 −0.719). Rescue = **O′-GRAY** — no rescue variant
clears all three O-1 bars (the band is the universal blocker,
including for s_tx/s_tx_roll5 whose AUCs 0.8767/0.8964 clear the AUC
bar alone), and five variants sit above the 0.65 floor
(mean_word_z_roll5, s_decode, s_decode_roll5, s_tx, s_tx_roll5), so
the rescue read is not an O-2 confirmation either. Per the locked
rule, O′-GRAY goes to Ken with the full ten-row table. Process note:
the Model-switching table assigns GATE read-offs to Opus; executed by
Fable at Ken's direction, same convened window as the S-1 read-off —
rule applied as locked, nothing interpreted.

**Verification (Fable, before advising on the ruling):** the three
headline rescue AUCs were independently recomputed from the raw
per-line score caches (`rescue_scores/*.json`), not via the AUC
scripts — exact match (s_tx_roll5 0.8964 at 116/295, s_decode_roll5
0.8270 and mean_word_z_roll5 0.7536 at 140/517). A full cut sweep on
s_tx_roll5 confirmed no threshold clears ≤10%/≤10%; the true minimax
cut (0.500) reaches 12.5% synced-below / 9.5% desynced-above. The
synced false-flag mass at that cut concentrates in Girl in the Bubble
(16 lines) and Belle (9) — wet/ensemble vocals where transcribe token
recall collapses — so the band failure is systematic (an instrument
weakness on the transcribe side), not sampling noise: a gate adopting
s_tx_roll5 would routinely route GATE C's showcase-perfect song into
repair.

**Analysis put to Ken for the gray ruling:** (1) the whisper
precedent replicated — confidence-type statistics fail (AUC
0.57–0.75) while content-corroboration statistics almost work
(0.88–0.90); the emission does not know when it is wrong, a second
engine's transcript nearly does. (2) The CTC-first engine's
distinctive premise — *emission-internal* self-policing — is
specifically what did not qualify (best emission-internal variant
s_decode_roll5, AUC 0.827, ~30% synced false-flags). (3) Every
statistic family improves under rolling-5 → the separable object is
the section, not the line, matching GATE C's C-3; sectional desync
under free whole-song alignment is exactly the failure mode a
scaffold prior with windowed alignment prevents by construction.
(4) S-1's NO-GO on the whisper-scaffold arm and this O′-GRAY point at
the same untested cell: scaffold + windowed CTC = Phase 3 S-B.

**Ken's ruling (2026-07-19):** engine branch **OFF** on this evidence
— no explicit GO; proceed scaffold-first with the S-B windowed-CTC
arm next. Consequences: S-B2 does not run; 2b's GATE-O-conditional
emission-score statistics stay off; GATE S ruling S-5's engine
condition is unmeetable, so S-5 = scaffold-first by rule (S-1, S-2,
S-3 remain live on the best scaffold arm); the build plan proceeds on
the fallback branch (F1/F2) and its Appendix E gate band stays
unfilled. Riders: **s_tx_roll5** (AUC 0.8964) is recorded as an
optional *advisory, demote-only* corroboration signal adoptable later
at Ken's discretion — its structural role already only routes lines
toward repair and never blocks a song, so the asymmetric-evidence
requirement is preserved; **S-shift** is not re-probed despite the
plausible ±5.0 s-pad artifact — a displacement statistic detects
free-alignment drift, which the windowed architecture eliminates, so
a wider-pad re-run only earns its cost if a score gate is ever
revisited. Ken also deferred the pending /code-review batch
(`2dc88a2`, `b3da6f7`, `2ef39f7`, `4c8698a`) until the production
phase begins.

### 2026-09-01 — Ken rulings: 2b arm (iv) runs, emission family eligible; measure-first sequencing; Phase 4 (GATE L) commissioned

Three rulings, no probe run. Recorded because each resolves a case a
locked procedure did not cover (STOP → Ken per Ground rules).

**1. Phase 2b arm (iv) runs.** The arm's precondition read "if GATE
O = O-1", which never happened — but Appendix C's R-5 rule is written
unconditionally and presumes (iv) exists, so honoring the precondition
literally would have left R-5 undefined and defaulted the word route to
the foreign-clock warp by omission rather than by comparison. Ken ruled
the arm runs: the precondition was written when (iv) meant engine
machinery (emission oracle + score gate), whereas the arm needs only a
windowed CTC align — which GATE S selected on evidence (S-2) and
`scripts/sb_ctc_adapter.py` already implements. Phase 2b is a four-arm
probe; R-5 applies as locked.

**2. Appendix C's emission-score family is eligible.** Its clause read
"only if GATE O ≠ O-2"; GATE O came out GRAY — neither O-1 nor a
confirmed O-2 — leaving eligibility undefined. Ken ruled eligible on
the ground that the bullet's own adoption rule self-guards
(discriminative on 2b's cohorts → primary gate, otherwise dropped), so
the pre-registered procedure decides rather than a judgment call
pre-empting it. Phase 1b emissions are cached, so the arm adds no
forward passes.

**3. Measure first, lock once.** The remaining probe program runs to
completion before the build design is consolidated. Licensing fact
recorded: no remaining probe needs production code — only the V-gates
are validation of shipped code. Order and rationale in "Remaining
execution order" above; F2 recorded there as a zero-regret exception.

**Also commissioned: Phase 4 (GATE L)**, the non-Latin alignment-form
probe — phase text above. Motivation (Ken): multi-language support is
in the project's future, and Appendix D's non-Latin carve-out means the
CTC path abstains exactly when that content arrives. The alternative
considered and **rejected** was retiring CTC and running whisper
everywhere: S-1 passed only on the S-B (CTC) arm (0.47 s against the
0.54 s bar), while the whisper arm read 1.61 s and NO-GO, so retiring
CTC would have un-licensed F2 on this plan's own recorded evidence.
Recorded so it is not re-litigated: CTC stays, and the multi-language
question is answered by widening CTC's eligibility, not by removing it.

### 2026-09-04 — Eyeball-provenance audit of the in-progress plans (Ken-directed) — S-2's genius arm flagged; M6 commissioned

**(Executor audit at Ken's direction, prompted by R-1: the eyeball
overturned two things the statistics implied, so which other live
rulings rest on unwitnessed proxy statistics? Read-only; no ruling is
reversed here.)**

**Organizing principle used.** A NO-GO that preserves the status quo is
cheap to be wrong about — the cost is a forgone opportunity. A GO that
*selects a mechanism* is expensive to be wrong about, because
everything downstream is built on it. Sorting the live rulings that
way leaves exactly one unwitnessed selection.

| ruling | evidence behind it | class |
| --- | --- | --- |
| GATE C (CTC usable at all) | Ken's eyeball, 33/33 | witnessed |
| S-1 (scaffold route GO) | Ken's eyeball on the nine regressions | witnessed |
| S-2 SRT arm / S-C (whisper retained) | Ken's eyeball — which *flipped* the metric reading | witnessed |
| R-1 (word route) | Ken's eyeball, 10 songs, 2026-09-03 | witnessed |
| **S-2 genius arm (CTC selected)** | **aggregate metrics only; 2 of 4 criteria now suspect** | **unwitnessed selection** |
| GATE O / O′ (engine branch OFF) | AUC — but computed against Ken's own eyeballed desync ranges | labels grounded; outcome conservative |
| GATE P (no section-level DP) | telemetry tables, no eyeball | conservative; Fable recorded its own upper-bound caveat |
| S-3 (densify NO-GO) | metrics only | conservative — rejected new machinery |

**The finding — S-2's genius arm was never re-read against Ken's own
S-C reframe.** On 2026-07-19 S-2 selected CTC for the non-SRT scaffold
path on four criteria, two of them overlap-based (mean worst-overlap
0.47 s vs 1.61 s, and the "no song > 1.0 s worse" cap). On 2026-07-20
Ken's S-C eyeball produced a reframe recorded in this log: *an overlap
dropping to 0.0 s under CTC is not unambiguously a fix if CTC's failure
mode on overlapping voices is to under-report rather than mis-time
them.* That reframe was applied only to the SRT arm's read-off, but it
is a claim about what the metric measures, so it is path-independent.
The genius arm has never been re-read against it. Three strands:

1. **The metric mechanically rewards clipping.**
   `cue_align_song.max_line_overlap` is `prev_end - cur_start` over
   time-sorted placed lines. Ken confirmed CTC produces tighter word
   endings; tighter endings shrink `prev_end`, so measured overlap
   falls. On a genuine two-voice passage that is not a correction — it
   is the second singer's tail being dropped.
2. **The showcase wins are ensemble numbers.** S-2's own entry
   highlights "CTC removed six of the seven Mode-2 align-displacement
   overlaps outright (Domino 4.6 → 0.0, **Be Our Guest 3.0 → 0.3,
   Hakuna 2.8 → 0.0**)". Be Our Guest and Hakuna Matata are ensemble
   Disney numbers — precisely where under-reporting is most likely.
3. **Both caveats were already documented on another path, before S-2
   was read.** `plans/completed/matcher-accuracy-hardening.md`
   establishes that source SRTs author genuine two-voice passages as
   stacked cue pairs with identical spans, giving each song "a
   computable maximum authored simultaneity" — explicitly "a reference
   the overlap metric ignores" — and warns that the statistic is a
   per-song max whose *location can move between runs*, so a delta
   "was never a same-location comparison". S-2's deltas are per-song
   maxes across two runs. Neither caveat was carried into the S-2
   read-off.

**Stakes.** S-2 is what selected the aligner for the genius-origin
scaffold path, and F2 builds on that path. If CTC is the wrong choice
there, an F2 built on CTC is regret — and F2 is otherwise the
zero-regret build that may be pulled forward at any point in the
measurement block. This audit does not claim S-2 is wrong; it records
that the evidence for it is weaker than the entry reads, and that the
weakness was knowable from material already in the repo.

**M6 commissioned (added to the R-1 ruling's M1-M5 block).**
*Re-read S-2's genius arm against the S-C reframe.* Re-render the
whisper arm on the genius scaffold corpus — the `.scaffold.ass` files
on disk are a single 2026-07-19 run, so only one arm survives — then
Ken eyeballs whisper vs CTC on **Be Our Guest** and **Hakuna Matata**,
the two ensemble songs carrying the largest overlap "wins". Needs GPU
plus the emission cache (already regenerated on the Windows box for 16
songs). Sequenced after M1-M3, which are pure offline analysis, but
**before any F2 build starts**. Two supporting measurements, both
cheap: recompute the S-2 overlap deltas as same-location comparisons
rather than per-song maxes, and record whether each song's worst pair
moved between arms.

**Not commissioned.** GATE O is second-tier rather than dismissed: its
read was AUC, but its labels were Ken's eyeballed desync ranges, and
its outcome kept the simpler architecture, so a revisit can only add
complexity and costs GPU. GATE P and S-3 are conservative NO-GOs whose
cost of error is a forgone opportunity. Ken's call if any of these
should be reopened later.
