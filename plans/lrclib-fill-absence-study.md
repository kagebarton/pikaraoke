Model: Claude Fable 5 (design); executor: Claude Sonnet 5 (2026-07-12 — see
Model switching)

# LRCLIB gated fill + absence evidence — offline value study

## Goal

Answer, with numbers and zero production changes, whether a *narrow, gated*
reintroduction of LRCLIB earns its way back in for either of two uses:

- **E1 — gated fill**: render lines the matcher left unplaced (interp/absent)
  at LRCLIB cue time, only behind version/offset/energy gates. This is NOT the
  blanket interp-render that `plans/matcher-accuracy-hardening.md` rejects
  (~57 correct drops vs ~22 real-but-unplaced; blanket fill wrong ~70%): the
  gates are designed to flip those odds by abstaining per-song (wrong variant)
  and per-line (version over-count).
- **E2 — absence evidence**: demote *placed* lines whose text has no
  counterpart in a version-verified LRC — the phantom class the energy veto
  cannot reach because those phantoms sit on top of *other* real singing.

Everything runs offline from the schema-v8 bundle corpus, the on-disk vocal
stems, and cached LRCLIB fetches. The deliverable is a Results-log verdict
against pre-registered bars (Appendix C). Only if a bar is met does a separate
production-wiring plan get written; nothing in this study touches
`pikaraoke/` or ships.

## Standing decision being revisited

Ken ruled LRCLIB permanently out of production on 2026-07-01 (ytasr
third-source experiment; the prior's snap/fill was the sweep's overlap source,
and In Summer's regression was accepted as the cost of removing priors). Ken
re-opened the question on 2026-07-06 for these two narrow uses. Whatever the
verdict, the ruling gets re-stated precisely at the end (Phase L4): either
"stays out entirely" or "out of scoring/timing paths; gated fill and/or
absence evidence excepted". The `matcher-accuracy-hardening.md` "Explicitly
rejected" section is amended only on a GO.

Prior art this study reuses rather than re-derives:

- The fill-only production implementation existed once: `jointrefine` commits
  `d3827a32` (search-quality probe) → `ad541fad` (prior measurement) →
  `c7bd17af` (fill-only in production). Its gate/fill mechanics are the
  starting point here, not a new design.
- The probe's findings stand: 22/24 songs HIT a usable variant; Bloodstream
  is the canonical SAFE-SKIP (album vs 4:07 awards edit — anchor MAD bails).
- The fill-width caps (`MAX_FILL_WORD_DUR_S = 0.7`, `MIN_FILL_DUR_S = 1.2`)
  from the slow-sweep diagnosis are mandatory: LRC stamps carry no ends (end
  is inferred as the next start), measured ~11x looser than SRT fill.

## Ground rules

- Environment: Linux conda env `pik`
  (`/home/ken/miniconda3/envs/pik/bin/python`). **No GPU needed** — matcher
  replays run from captured bundle words; energy checks decode stems with
  ffmpeg on CPU.
- Study workspace: `/home/ken/pikaraoke-songs/lrclib_study/` — holds the study
  script(s), the LRCLIB fetch cache, and per-line dumps. It lives in the song
  library (outside git) on purpose: the study spans sessions and Ken-eyeball
  pauses, and the session scratchpad does not survive those. Nothing from the
  workspace is ever committed.
- Network: LRCLIB is queried live exactly once per song (L0), then served
  from the fetch cache — reruns must be offline and byte-reproducible (the
  Phase 0 reproducibility bar).
- **The hand-vetted flat cache `pikaraoke-songs/lrclib/<stem>` is
  reference-only.** The study's *input* variant always comes from the
  production-shaped live search (L0). Reading the flat cache in the input
  path would measure the hand-vetted file, not the pipeline.
- Results tables, dumps worth keeping, and the verdict go into this file's
  Results log (plans/ is pre-commit-exempt). Nothing is committed to the repo
  by this study; there is no /code-review batch.
- Corpus filenames contain soft hyphens (U+00AD) and other metacharacters:
  always iterate bundles via `glob`, never reconstruct a path from a printed
  name.

## Sequencing

Run after matcher-accuracy-hardening **Phase 3** (landed 2026-07-07:
`evidence_veto.py` demotes zero-evidence align lines whose span median sits
below the absolute `MIN_REF_DB` floor — reuse that convention, A.6) and
ideally after
**Phase 4** (windowed-realign revision shifts the unplaced population this
study measures). Before the Phase 6 checkpoint — E2's verdict is an input to
the transition-cost decision (both attack phantoms; Ken should weigh them
together). If Phase 4 has not landed when this runs, note it in the Results
log and expect the E1 target population to be slightly larger.

## Model switching

The whole study is executable by Sonnet 5 from this spec plus Appendices
A-C; the design decisions are locked there. Executor discipline: run
appendix code as written (lift it, don't reinterpret it — any mismatch with
the committed surfaces is a STOP + report, not a workaround); every
Results-log number comes from a command run in that session with the
invocation recorded; the Appendix B predictions and Appendix C bars are
never adjusted after seeing data. GATEs report to Ken — never proceed past
one on your own judgment. Escalate (ask Ken to `/model` — Opus first, Fable
only if still available) only if:

- L1's gate table contradicts the predictions in Appendix C.1 (e.g.
  Bloodstream or Defying Gravity PASSES the arm-A gate) — the study's safety
  story rests on those bails;
- the harness-import architecture (Appendix A.1) cannot be made to work
  without modifying committed files beyond the letter of A.1;
- a pre-registered criterion turns out to be ambiguous on real data.

## Phase L0 — corpus audit + production-shaped variant fetch

1. Corpus = `/home/ken/pikaraoke-songs/alignment_debug/*.json` where
   `pipeline_decisions.method_used == "joint"`. Cross-check: this set must
   equal the harness's own filter (`not ground_truth_refs.youtube_srt_present`)
   and count 17 songs; if not, STOP and report.
2. Per song, fetch the input variant exactly as production would
   (Appendix A.3): `lrclib.search(genius.title, genius.artist)` →
   `lrclib.select_candidate(records, lines, media_duration_s)`. Persist the
   query, the full record list (metadata only), and the chosen record
   (including `syncedLyrics`) to the fetch cache. Songs with no `genius`
   block or no synced candidate are NO-VARIANT.
3. Circularity flag per song: `same_variant` = the chosen input variant
   parses to the same (normalized text, start±0.05s) cue sequence as the
   held-out reference the harness resolves (Appendix A.4). Where
   `same_variant`, every timing agreement with the reference is void as
   evidence — only energy and eyeball count for those songs.
4. Output: per-song table — variant found?, record name/artist/duration,
   duration delta vs `media_duration_s`, mapping rate, `same_variant`.

No GATE; L0 is bookkeeping. Its table rides into L1's report.

## Phase L1 — version gates + reach accounting

Replay each song once at the bundle's own knobs (α=2.0, β=2.0, captured
realign spans — Appendix A.2) and fit both gate arms against the input
variant's cues:

- **Arm A (primary, production-shaped)**: trusted anchors via
  `analyze_pass1`, then `offset_mad_against_cues(anchors, input_cues)` —
  PASS iff `bailed is None` (≥4 anchors, MAD ≤ 0.75 s). This is the
  constant-offset gate the old fill-only prior shipped with.
- **Arm B (reach probe only)**: Theil-Sen tempo+offset fit over the same
  anchor pairs, gates `WARP_MIN_ANCHORS = 5`, `WARP_MAD_GATE_S = 2.0` —
  ported from `git show 835ba2c7:pikaraoke/lib/cue_align.py`
  (`_theil_sen`, `warp_scaffold_cues`). Arm B exists to measure how much
  reach a warp-gated variant would add; it never drives the wiring verdict.

Report per song: arm-A pass/bail(reason) + offset/MAD, arm-B pass/bail +
fit slope/intercept/MAD, `n_placed`, `n_unplaced`, `same_variant`. Plus two
corpus-level reach numbers:

- fraction of all unplaced lines that live on arm-A-passing songs (E1's
  structural ceiling);
- fraction of the known overhang mass (Defying Gravity, Bloodstream) on
  bailing songs (E2's structural blind spot — expected ≈ all of it).

**GATE L1**: table to Ken. Expected per Appendix C.1: Bloodstream and
Defying Gravity bail arm A; roughly 2/3 of songs pass. If the expectations
are contradicted, escalate per Model switching before running L2/L3.

## Phase L2 — E1: gated fill simulation

On arm-A-passing songs (and separately arm-B-passing, same code, warped
times):

1. Unplaced set = lids whose post-merge line object is missing or has empty
   `words` (Appendix A.2 — the stats ids are pass-1-only and must not be
   used here).
2. For each unplaced lid with a mapped input cue: fill span =
   `(cue_start + offset, cue_end + offset)` (arm B: warp both ends), then
   build the line via the capped `_fill_line` port (Appendix A.5) — even-
   paced words, `MAX_FILL_WORD_DUR_S = 0.7` per token, `MIN_FILL_DUR_S = 1.2`
   floor, anchored at the corrected cue start.
3. Per fill, three automatic checks (Appendix A.6):
   - **collision**: overlaps a placed line's span by > 0.2 s (report only —
     a production policy would clamp; the sim just counts);
   - **energy**: median stem-envelope dB over the fill span within the sung
     band — `median_env ≥ max(sung_ref − SOFT_NEAR_DB, MIN_REF_DB)`, void if
     `sung_ref < MIN_REF_DB` (the floor conjunct keeps PASS consistent with
     the shipped veto's absolute-silence convention, A.6);
   - **cross-variant timing** (only where NOT `same_variant`): fill start
     within 1.0 s of `reference_cue_start + reference_offset`.
4. Render eyeball material: for each song with ≥1 fill, write
   `karaoke/<stem>.lrcfill.ass` via the harness's `_write_ass_variant`
   (placed lines + fills; tag `lrcfill`), and a plain per-fill dump
   (lid, text, span, check verdicts, mapped cue text) into the workspace.

**GATE L2**: per-song and corpus tables to Ken — *numbers first, then* Ken
eyeballs the `.lrcfill.ass` renders and marks each fill good/bad. Expected
volume is small (ceiling ≈ 20 lines corpus-wide), so a full eyeball is
feasible. The E1 verdict then reads off Appendix C.2.

Honesty caveats to carry into the report: energy cannot catch a fill placed
over *someone else's* singing (the collision check partially covers);
`same_variant` songs contribute no automatic timing evidence; LRC end
inference means fill ends are soft even when starts are right.

## Phase L3 — E2: absence-evidence simulation

On arm-A-passing songs:

1. Demotion candidates = placed lids **not** in
   `map_lines_to_cues(lines, input_cue_texts)` — the monotone 1:1 alignment
   refuses them a counterpart in the version-verified LRC.
2. Split candidates by discriminative strength (Appendix A.7):
   - **strong-absence**: the line's text has NO fuzzy match (difflib ratio ≥
     `lrclib._MAP_MIN_RATIO`) against ANY input cue text — the LRC genuinely
     lacks this text;
   - **twin-blocked**: some cue text fuzzy-matches but the monotone
     assignment gave it to another instance (repeat count mismatch or
     segmentation drift) — weaker evidence, tallied separately.
3. Per candidate record: lid, text, placed span + `source`, corroboration
   (from the object-carried `evidence` key, shipped in Phase 3b — A.7),
   energy verdict over the placed span. The headline
   marginal-value count is **strong-absence ∧ energy-PASS** — phantoms over
   real singing, exactly the class Phase 3b's veto cannot touch.
4. Eyeball list for Ken: every strong-absence candidate (with timestamps so
   he can check the video), plus all candidates on the known different-mix
   songs that passed the gate (per L1 — likely only In Summer of the P3
   trio).

**GATE L3**: tables + eyeball list to Ken; verdict per Appendix C.3. Carry
the structural blind spot forward explicitly: the biggest overhang songs bail
the gate, so E2's corpus-wide recall is bounded by L1's reach numbers — the
question is whether the reachable candidates are precise, not whether E2
solves the phantom problem alone.

## Phase L4 — verdict and follow-ups

- Write the Results-log verdict for E1 and E2 against Appendix C.
- On any GO: write a separate production-wiring plan (resurrecting the
  `c7bd17af` fetch-stage + fill-only mechanics for E1, a new
  `pikaraoke/lib/` module for E2 per the fork rule; the harness's held-out
  scoring must tag-and-exclude filled/demoted lines). Do not start it inside
  this study.
- Either way: update the LRCLIB ruling in the auto-memory
  (`project_ytasr_third_source_experiment` carries "LRCLIB permanently out")
  and, on a GO, amend `matcher-accuracy-hardening.md`'s "Explicitly
  rejected" section to reference this study.
- Flag the checkpoint to Ken as a good /compact point.

---

## Appendix A — implementation sketch (locked)

### A.1 Script architecture

One study module `lrclib_study.py` in the workspace
(`/home/ken/pikaraoke-songs/lrclib_study/`), run as
`.../pik/bin/python lrclib_study.py <phase> [--arm A|B]` with subcommands
`l0 | l1 | l2 | l3`. It bootstraps imports the same way the harness does:

```python
import sys
from pathlib import Path

REPO = Path("/home/ken/pikaraoke")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
import replay_ytasr_third_source as harness  # main() is __main__-guarded
```

Reused from `harness` (do not reimplement): `_replay_output`,
`_replay_spans_at_alpha`, `_load_ytasr_words`, `_load_lrclib_reference`
(reference resolution ONLY), `_selected_sources`, `summarize`,
`_write_ass_variant`. Reused from `pikaraoke.lib`: `lrclib` (whole surface),
`srt_cues.offset_mad_against_cues`, `windowed_realign.analyze_pass1`,
`onset_snap.rms_envelope_db` / `_sung_level_ref` / `HOP_S` / `SOFT_NEAR_DB` /
`MIN_REF_DB`, and `evidence_veto` (shipped: `veto_uncorroborated_lines`,
absolute `MIN_REF_DB` floor).

If a needed harness helper turns out not to be importable as-is, lift its
body into `lrclib_study.py` with a comment naming the source — do NOT modify
the committed harness for this study.

### A.2 Replay (per song, computed once, cached in-process)

```python
bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
song_root = bundle_path.parent.parent          # /home/ken/pikaraoke-songs
ytasr_words = harness._load_ytasr_words(bundle, song_root)
realign = harness._replay_spans_at_alpha(bundle, 2.0)
objs, stats = harness._replay_output(bundle, ytasr_words, 2.0, 2.0, realign)
```

α=β=2.0 are the corpus bundles' own knobs (`pipeline_decisions.joint_alpha`/
`joint_beta`); assert they read 2.0 rather than hardcoding blind. Placed =
objects with non-empty `words`; unplaced = every other lid in
`range(len(lines))`. Derive both from the **merged** `objs`, never from
`stats["interpolated_line_ids"]`/`absent_line_ids` — those are computed
before `merge_spans` runs and go stale whenever a span replay changes a
placement. `lines = bundle["lyrics"]["lines"]`,
`align_lines = bundle["lyrics"]["align_lines"]`,
`knobs = bundle["joint_stats"]["knobs"]` (margin_s, max_edit_ratio).

### A.3 Input variant fetch + cache (L0)

```python
cache = WORKSPACE / "fetch" / f"{bundle_path.stem}.json"
if cache.exists():
    payload = json.loads(cache.read_text(encoding="utf-8"))
else:
    g = bundle["lyrics"].get("genius")           # {"title","artist"} or None
    records = lrclib.search(g["title"], g["artist"]) if g else []
    chosen = lrclib.select_candidate(records, lines, bundle["media_duration_s"])
    payload = {"query": g, "records": [lrclib.record_meta(r) for r in records],
               "chosen": chosen}                  # chosen keeps syncedLyrics
    cache.write_text(json.dumps(payload, ...), encoding="utf-8")
```

From `chosen["syncedLyrics"]`:
`cue_texts, spans = lrclib.cue_spans_from_lrc(synced)` and
`input_cues = lrclib.cue_spans_for_lines(synced, lines)` (lid → span).

### A.4 `same_variant` detection (L0)

`reference_cues = harness._load_lrclib_reference(bundle, song_root,
bundle_path.stem)` (the harness's 3-tier resolution; tier 1 is absent in v8
bundles, so this is flat-cache-or-live). `same_variant` = both resolve AND
the input's `(normalize_line(text), start)` cue sequence equals the
reference's within 0.05 s per start. When the reference itself came from a
live fetch, `same_variant` is expected True (same selection path) — still
compute it, don't assume. Note: `_load_lrclib_reference` returns lid-mapped
spans, not raw cues; for the sequence comparison parse the reference LRC
directly (flat-cache file via `lrclib.read_lrc`, or the live record's
`syncedLyrics`) with `cue_spans_from_lrc` — mirror the harness's tier order
when picking which text to parse.

### A.5 Gates + fill construction (L1/L2)

Arm A:

```python
sources = harness._selected_sources(objs, len(lines))
anchors, _ = analyze_pass1(align_lines, objs, {"selected_source": sources},
                           bundle["transcribe_words"],
                           margin_s=knobs["margin_s"],
                           max_edit_ratio=knobs["max_edit_ratio"])
fit = offset_mad_against_cues(anchors, input_cues)   # PASS iff not fit["bailed"]
```

Arm B: over the same `(cue_start, placed_start)` anchor pairs run the
Theil-Sen fit ported verbatim from `git show
835ba2c7:pikaraoke/lib/cue_align.py` (`_theil_sen` + the gate logic of
`warp_scaffold_cues`; lift only the fit+gate, not the densify fallback).
Warped time = `a * t + b`.

Fill: port `_fill_line` and its two constants verbatim from `git show
pathed_align:pikaraoke/lib/srt_prior.py` (lines ~237-260; constants at
~63-66) into the study module, with a source comment. Call as
`_fill_line(lid, lines[lid], align_lines[lid], t0, t1, "lrclib_fill")` where
`t0, t1` are the offset-corrected (arm A) or warped (arm B) cue ends.

### A.6 Energy check (L2/L3)

```python
vocal = song_root / "vocal" / f"{bundle['song_stem']}---vocal.m4a"
# assert vocal.exists(); if not, glob song_root/"vocal" for the stem prefix
env = rms_envelope_db(vocal)                     # one value per HOP_S (0.025 s)
placed_words = [w for o in objs if o["words"] for w in o["words"]]
ref = _sung_level_ref(env, placed_words)
```

Void if `ref is None or ref < MIN_REF_DB` (report as `energy=void`).
Otherwise `median(env[int(t0/HOP_S):max(int(t1/HOP_S), int(t0/HOP_S)+1)])`
and PASS iff `median ≥ max(ref - SOFT_NEAR_DB, MIN_REF_DB)` (16 dB — the
onset-snap "near sung level" band, floored at the absolute silence level).
The shipped veto (`evidence_veto.py`, matcher-accuracy-hardening Appendix
D) deliberately uses only the absolute `MIN_REF_DB` floor; the study keeps
the stricter relative band because E1/E2 ask "is there singing here", not
"is this dead silent" — the `max(…, MIN_REF_DB)` conjunct guarantees the
study never calls sung what the veto calls silent. Import all three
constants from `onset_snap`; never copy values.

### A.7 E2 candidate classification (L3)

```python
mapping = lrclib.map_lines_to_cues(lines, cue_texts)   # monotone 1:1
candidates = [lid for lid in placed_lids if lid not in mapping]
```

Strong-absence vs twin-blocked: for each candidate, compute
`max(difflib.SequenceMatcher(None, normalize_line(lines[lid]),
normalize_line(ct)).ratio() for ct in cue_texts)` (use
`lrclib.normalize_line`; `autojunk=False` to match the mapper). Strong iff
the max ratio `< lrclib._MAP_MIN_RATIO` (0.85). Corroboration column: read
the object-carried `evidence` key off the replayed line objects (shipped in
Phase 3b, commit `5625d855`: `_materialise_line_objects` attaches it and it
survives `merge_spans`); uncorroborated ⇔ `transcribe_match == 0 and
ytasr_agreement == 0.0` — the shipped veto's own eligibility test.

### A.8 Outputs

All tables print as aligned text AND persist as JSON under
`WORKSPACE/out/` (`l0_variants.json`, `l1_gates.json`, `l2_fills_<arm>.json`,
`l3_absence.json`) so GATE reports and the Results log are copy-paste, and
reruns diff cleanly. Two consecutive L1-L3 runs from a warm fetch cache must
be byte-identical (Phase 0 reproducibility bar) — verify once and say so in
the Results log.

## Appendix B — predictions (written before running; check at GATE L1)

- NO-VARIANT or arm-A bail on: Bloodstream (album vs 4:07 cut — the probe's
  SAFE-SKIP), Defying Gravity (LRCLIB master ~354 s vs media ~257 s),
  HUNTR_X (Phase 0 reference bails wide_spread), plus 1-3 more of the Phase 0
  `bail:wide_spread` songs (Popular, Best Part Of Me, I'll Make a Man Out of
  You are the candidates).
- Roughly 10-12 of 17 songs pass arm A; arm B adds tempo-mismatched variants
  (Defying Gravity is the test case) but NOT different-content cuts
  (Bloodstream stays out — a linear warp cannot manufacture missing verses).
- E1 ceiling: ~20 real-but-unplaced lines corpus-wide pre-Phase-4, several
  on bailing songs; expect single-digit fills. If Phase 4a landed first,
  fewer.
- E2: strong-absence candidates concentrate on gate-passing songs with
  version drift; expect a small count (the big overhang mass is on bailing
  songs by construction).

## Appendix C — pre-registered decision criteria (locked)

Numbers are stated before any data is unblinded; Ken may tighten or loosen
them at a GATE only *before* his eyeball pass for that phase.

### C.1 L1 sanity

The study's safety story requires the gate to bail on the known
different-version songs. If Bloodstream or Defying Gravity passes arm A,
STOP — the gate is weaker than believed; escalate per Model switching.

### C.2 E1 verdict (arm A only)

- `good fill` = energy-PASS ∧ collision-free ∧ Ken-eyeball correct.
- `bad fill surviving gates` = energy-PASS ∧ collision-free ∧ eyeball says
  the line is not sung there.
- **GO** (write the production-wiring plan) iff `good ≥ 6` corpus-wide AND
  `bad surviving = 0`. A single surviving bad fill is disqualifying — a
  rendered phantom is the exact failure the hardening plan exists to
  prevent — unless a specific, mechanical gate addition removes it, in which
  case re-run L2 with that gate and re-read this criterion once.
- Below the bar: NO-GO, record the counts. The `.lrcfill.ass` renders and
  the fetch cache stay in the workspace for future re-tests.

### C.3 E2 verdict (arm A only)

- `true demotion` = strong-absence candidate Ken confirms is a phantom;
  `wrong demotion` = strong-absence candidate that is actually sung
  (coverage loss).
- **GO** (design a follow-up, likely folded into the Phase 6 checkpoint
  discussion) iff veto-immune true demotions (strong-absence ∧ energy-PASS)
  `≥ 5` corpus-wide AND wrong demotions `= 0` among eyeballed
  strong-absence candidates. Twin-blocked candidates never count toward GO;
  report them as context only.

### C.4 Arm B

Never drives a GO by itself. If arm B at least doubles arm-A reach (songs or
lines) at equal eyeball precision, record "warp-gated variant merits its own
study" in the Results log for Ken to prioritize.

## Results log

### Phase L0 — corpus audit + variant fetch artifacts (Sonnet, 2026-07-16)

Executor stops at artifacts per this doc's Model switching / the
established executor-judge split; no interpretation below, per Ken's
instruction to hand this straight to a judge session.

**Environment substitution** (Ground rules name the Linux conda box;
this ran on the Windows/uv box instead — capabilities are equivalent,
nothing in L0 is GPU- or OS-dependent): `REPO` = this checkout,
`SONG_ROOT`/`WORKSPACE` = `D:\shared\pikaraoke-songs` /
`D:\shared\pikaraoke-songs\lrclib_study`, invocation `uv run python`
in place of the conda interpreter. Script:
`D:\shared\pikaraoke-songs\lrclib_study\lrclib_study.py` (not committed,
per this file's own "nothing is committed to the repo by this study").

**Invocation:** `uv run python
"D:/shared/pikaraoke-songs/lrclib_study/lrclib_study.py" l0`

**Step-1 corpus cross-check:** `method_used=="joint"` count and
`not youtube_srt_present` count both 17, sets equal — script printed
`Corpus cross-check OK` and did not STOP.

**Artifacts saved** (durable, outside git, in the study workspace):
- `D:\shared\pikaraoke-songs\lrclib_study\out\l0_variants.json` — full
  per-song structured output (A.8).
- `D:\shared\pikaraoke-songs\lrclib_study\out\l0_console.txt` — raw
  stdout/stderr of the run above, byte-for-byte (includes 5
  `LRCLIB search failed ... Read timed out` lines and the printed
  table), copied out of the ephemeral task-output path so a separate
  session can read it.
- `D:\shared\pikaraoke-songs\lrclib_study\fetch\*.json` — per-song input
  variant fetch cache (A.3): query, record metadata list, chosen record
  incl. `syncedLyrics`.

Raw table (verbatim from `l0_console.txt`):

```
song                                           variant record (artist)                             dur  delta_s   map%  same_var
--------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary Ed   False -                                             -        -      -         -
'Free' _ Official Lyric Video _ Sony Animation    True Free (Rumi)                                 188        -     88     False
'Popular' - Wicked 20th Anniversary Edition _     True Popular (Kristin Chen)                      224    +12.7     68         -
Beauty and the Beast (1991) - Be Our Guest [UH   False -                                             -        -      -         -
Beauty and the Beast (1991) - Belle [UHD]---ot    True Belle (Paige O'Hara)                        306     +8.6     59     False
Ed Sheeran - Best Part Of Me (feat. YEBBA) (Li    True Best Part of Me (Ed Sheeran)                247     -0.0     95     False
Ed Sheeran & Rudimental­ - Bloodstream­ [Offici    True Bloodstream (Ed Sheeran)                    289    +41.7     76     False
HUNTR_X 'This Is What It Sounds Like' (Music V   False -                                             -        -      -         -
Jessie J - Domino (Official Video)---UJtB55Mao    True Domino (Jessie J)                           232        -     91      True
Josh Gad - In Summer (From 'Frozen'_Sing-Along    True In Summer (Josh Gad)                        111        -     48      True
Mulan _ I'll Make a Man Out of You _ @disneyki    True I'll Make a Man Out of Y (Donny Osmond)     219    -21.9     89      True
NSYNC - Paradise                                  True Paradise (Justin Timbe)                     267        -     74     False
Pocahontas - Colors of the Wind (Blu-ray 1080p    True Colors of the Wind (Judy Kuhn)              211     +8.3     95      True
Seasons of Love (HD)---UvyHuse6buY               False -                                             -        -      -         -
The Lion King - Hakuna Matata Music Video I 4K    True Hakuna Matata (Lane, Nathan)                214    -34.0     48      True
The Next Ten Minutes Lyrics---0j8kL24ph8U         True The Next Ten Minutes (Anna Kendric)         452        -     93      True
Wicked - For Good  (2025) 4K - The Girl in the    True The Girl in the Bubble (Ariana Grand)       220    +25.9    100      True
```

5 `LRCLIB search failed ... Read timed out` lines were printed for:
Defying Gravity, Popular, Be Our Guest, HUNTR_X ("What It Sounds
Like"), Seasons of Love. No re-run or retry was attempted. No reading
of this table (against Appendix B's predictions, C.1, or otherwise) is
offered here — deferred to the judge.

**Follow-up check (mechanical, not interpretation):** per song, each
`fetch/<stem>.json` cache records its raw `records` count and whether
`chosen` is non-null. Confirmed 4 of the 17 caches are `0 records,
chosen=null` — Defying Gravity, Be Our Guest, HUNTR_X, Seasons of
Love — matching 4 of the 5 timeout lines exactly; these 4 are the
entire `variant=False` set in the table above. Popular's timeout does
not appear here (its cache holds 20 records, `chosen` non-null) — that
timeout came from a different call (the separate reference-resolution
path, A.4, consistent with its `same_variant=None`), not the input
fetch. Cross-referencing those 4 against
`D:\shared\pikaraoke-songs\lrclib\` (the hand-vetted flat cache,
reference-only — never read as this study's input, by design, Ground
rules): a file exists there for Be Our Guest
(`Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjABn8`) and
Seasons of Love (`Seasons of Love (HD)---UvyHuse6buY`); no matching
file exists for Defying Gravity or HUNTR_X either way. Recorded as a
fact for the judge to weigh, not a conclusion.

**Separate open item, found while scoping L1 (not yet acted on):**
Appendix A.2's replay sketch calls `harness._replay_spans_at_alpha(bundle,
2.0)`, which does not exist in the current harness
(`scripts/replay_ytasr_third_source.py`). The live function is
`_replay_spans(bundle, ytasr_words, alpha, beta)` — Phase 4a
(`matcher-accuracy-hardening.md` Appendix E, locked one day after this
plan's Appendix A) added the `ytasr_words`/`beta` threading. A.2's own
sketch already has both values in scope (`ytasr_words` computed
earlier, `beta=2.0` used on the following line), so the literal
substitution is mechanical, but it is a real mismatch against a locked
appendix, not implemented, and not for the executor to resolve
unilaterally per this file's Model switching section.

### Phase L0 — judge read (Opus, 2026-07-16)

Independent re-derivation from the raw artifacts (not the printed
summaries): re-read the plan end to end, re-computed the cross-check
from the 33 `alignment_debug/*.json` directly, re-tallied
`l0_variants.json`, opened the five timed-out `fetch/*.json` caches,
and read the current harness surfaces (`_replay_spans`,
`_replay_output`, `_load_lrclib_reference`, `lrclib.search`) rather
than trusting the write-up. Environment substitution (Windows/uv for
Linux/conda) is sound — L0 touches no GPU and no OS-specific path;
verified, not taken on faith.

**1. Corpus cross-check — CONFIRMED.** My own pass: 33 total bundles;
`method_used=="joint"` = 17; `not youtube_srt_present` = 17; sets
equal; symmetric difference empty. The step-1 invariant holds from the
JSON, not just from the printed `Corpus cross-check OK`. `l0_variants.json`
is 17 rows, `has_genius` True on all 17.

**2. Predictions (Appendix B) — resolved rows consistent; NO-VARIANT
rows unreadable.** 13 variant-found, 4 NO-VARIANT, `same_variant` 7
True / 5 False / 5 None. The resolved rows line up with B: Bloodstream
found but +41.7 s long (album vs the 4:07 cut — the predicted arm-A
SAFE-SKIP, to be confirmed at L1, not L0); the version-drift songs
(Hakuna Matata −34.0 s, Girl in the Bubble +25.9 s, I'll Make a Man
−21.9 s) carry the large deltas B expects. The 7 `same_variant=True`
are unsurprising per A.4 (live-fetch reference ⇒ same selection path)
— but they mean **over half the resolved corpus (7/13) yields no
automatic timing evidence**, so L1/L2's independent-evidence base is
narrower than the 13 headline suggests; energy + eyeball carry those
songs. Not a blocker, but carry it into L1's reach accounting. The one
genuine surprise is structural and belongs to check 3: **there are
zero confirmed NO-VARIANT songs** — every `variant=False` row is a
network artifact, so the "variant found?" column cannot yet be read
against B at all for those four.

**3. The five timeouts — RULING: retry mandatory before L1; four of
the four NO-VARIANTs are false.** The executor's mechanical read is
correct and I confirm it end to end. `lrclib.search` swallows the
`ReadTimeout` and returns `[]` (lrclib.py:235, "Returns `[]` on any
failure"); `_fetch_input_variant` then writes `records:[], chosen:null`
to the cache and, on any rerun, reads that cache instead of
re-searching (lrclib_study.py:132-134). So a transient network failure
is baked as a *permanent* NO-VARIANT that a rerun cannot self-heal.
The four `variant=False` caches (Defying Gravity, Be Our Guest,
HUNTR_X, Seasons of Love) each hold `0 records / chosen=null` and each
match an **input-fetch** timeout line by title/artist; they are the
entire `variant=False` set. Popular is the fifth timeout but its input
cache holds 20 records — its timeout was the uncached reference search
(A.4), leaving only `same_variant=None`, which self-heals on any rerun
where the network cooperates (that path is never cached). So the split
is 4 input + 1 reference, exactly.

This is not a real absence signal:
- **Two of the four are provably present.** I independently confirmed a
  hand-vetted flat-cache reference exists at
  `D:\shared\pikaraoke-songs\lrclib\` for Be Our Guest and Seasons of
  Love (none for Defying Gravity or HUNTR_X). A human already found an
  LRCLIB variant for those two, so their NO-VARIANT is a definite false
  negative; the other two are genuinely unknown pending a successful
  fetch.
- **Defying Gravity is arm B's designated test case.** Appendix B and
  C.4 name it *the* tempo-mismatched variant arm B exists to rescue
  (LRCLIB master ~354 s vs media ~257 s). With no input variant cached,
  arm B cannot be evaluated on the one song it was written for — a
  silent hole in the study, not a data point.
- **The reproducibility bar would falsely pass.** A warm-cache rerun is
  byte-identical *because* it re-reads the empty caches — it reproduces
  the failure, it does not reproduce a fetch.

Action before L1: delete the four empty input caches (Defying Gravity,
Be Our Guest, HUNTR_X, Seasons of Love) and re-run L0; leave Popular's
20-record cache (its `same_variant` re-resolves live on its own). This
does **not** violate the "query live exactly once per song" rule — that
rule's intent is one *successful* frozen fetch per song; a timeout is
the query failing, and re-issuing it to actually obtain the answer
honors the rule rather than breaking it. Only after the four re-fetch
(whatever they then return — variant or a genuine empty result) can the
`variant=False` column, the "~10-12 pass arm A" prediction, and arm B's
reach be read honestly. (Related latent note for the reproducibility
bar: the reference/`same_variant` search path is uncached and hits the
network every L0 run, so it is not offline-reproducible — immaterial to
L1-L3, which the bar actually governs, but worth stating.)

**4. A.2 signature mismatch — CONFIRMED, and the substitution is
correct.** Verified against the current file myself: the harness has
only `_replay_spans(bundle, ytasr_words, alpha, beta)` at
replay_ytasr_third_source.py:213; `_replay_spans_at_alpha` does not
exist. The substitution is not merely name-compatible but
**contract-compatible**: `_replay_spans` returns `(spans, results)` or
`None` (lines 215, 249), and `_replay_output`'s `realign` parameter is
typed exactly `tuple[list, list] | None` and unpacked as
`spans, results = realign` (lines 257, 285-286). A.2 already has
`ytasr_words` in scope and passes `2.0, 2.0` to `_replay_output` on the
very next line, so:

```python
realign = harness._replay_spans(bundle, ytasr_words, 2.0, 2.0)
objs, stats = harness._replay_output(bundle, ytasr_words, 2.0, 2.0, realign)
```

is the right fix. Beyond "allowed": using the **same** `(ytasr_words,
alpha, beta)` in both calls is *required* for correctness — Phase 4a
threaded ytasr/beta into the sub-match, so replaying spans at different
knobs than the main DP would mis-match the merge. Ruling: apply this
substitution verbatim when L1 is implemented; it is a mechanical
appendix-vs-code drift from Phase 4a landing a day later, not a design
change, so it does not require re-locking A.2 — record the substitution
in L1's Results entry and proceed.

**Verdict.** L0's bookkeeping is sound where the network cooperated:
the cross-check is real, the 13 resolved rows are trustworthy and
consistent with the predictions, the circularity flags are computed
correctly, and both open items the executor flagged are real and
correctly diagnosed. But L0 does **not** yet ride cleanly into L1: all
four NO-VARIANT rows are timeout artifacts (two provably false), and
Defying Gravity — arm B's test case — is among them. Re-fetch those
four first, then L1. The A.2 substitution is approved as written. No
escalation to Ken's judgment is triggered under Model switching (no
prediction is contradicted by *data* — the contradiction is with the
network), but the four re-fetches are a prerequisite, not an optional
cleanup, and L0's table should not be quoted as final until they land.
