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

### Phase L0 — retry artifacts (Sonnet, 2026-07-16)

Executed the judge's ruling above, no interpretation added.

**Action:** deleted the 4 poisoned caches after re-verifying each was
still `0 records, chosen=null` (`fetch/`'s Defying Gravity, Be Our
Guest, HUNTR_X, Seasons of Love); left Popular's 20-record cache
untouched, as ruled. Re-ran the same invocation: `uv run python
"D:/shared/pikaraoke-songs/lrclib_study/lrclib_study.py" l0`.

**Outcome:** corpus cross-check still 17==17. All 17 songs now show
`variant=True` — zero NO-VARIANT rows remain. One timeout printed this
run, again for Popular
(`LRCLIB search failed for 'Popular' / 'Kristin Chenoweth': ... Read
timed out`) — matches the judge's note that the reference/`same_variant`
search path is uncached and hits the network on every run; Popular's
`same_variant` is `None` again, unchanged from before, not a new
failure.

Updated raw table (`l0_console.txt` and `l0_variants.json` overwritten
in place with this run's output):

```
song                                           variant record (artist)                             dur  delta_s   map%  same_var
--------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary Ed    True Defying Gravity (Kristin Chen)              354    +96.8     87      True
'Free' _ Official Lyric Video _ Sony Animation    True Free (Rumi)                                 188        -     88     False
'Popular' - Wicked 20th Anniversary Edition _     True Popular (Kristin Chen)                      224    +12.7     68         -
Beauty and the Beast (1991) - Be Our Guest [UH    True Be Our Guest (Jerry Orbach)                 223     +5.2     88      True
Beauty and the Beast (1991) - Belle [UHD]---ot    True Belle (Paige O'Hara)                        306     +8.6     59     False
Ed Sheeran - Best Part Of Me (feat. YEBBA) (Li    True Best Part of Me (Ed Sheeran)                247     -0.0     95     False
Ed Sheeran & Rudimental­ - Bloodstream­ [Offici    True Bloodstream (Ed Sheeran)                    289    +41.7     76     False
HUNTR_X 'This Is What It Sounds Like' (Music V    True What It Sounds Like (HUNTR/X)               250        -     81      True
Jessie J - Domino (Official Video)---UJtB55Mao    True Domino (Jessie J)                           232        -     91      True
Josh Gad - In Summer (From 'Frozen'_Sing-Along    True In Summer (Josh Gad)                        111        -     48      True
Mulan _ I'll Make a Man Out of You _ @disneyki    True I'll Make a Man Out of Y (Donny Osmond)     219    -21.9     89      True
NSYNC - Paradise                                  True Paradise (Justin Timbe)                     267        -     74     False
Pocahontas - Colors of the Wind (Blu-ray 1080p    True Colors of the Wind (Judy Kuhn)              211     +8.3     95      True
Seasons of Love (HD)---UvyHuse6buY                True Seasons of Love (Cast Of The )              183        -     62     False
The Lion King - Hakuna Matata Music Video I 4K    True Hakuna Matata (Lane, Nathan)                214    -34.0     48      True
The Next Ten Minutes Lyrics---0j8kL24ph8U         True The Next Ten Minutes (Anna Kendric)         452        -     93      True
Wicked - For Good  (2025) 4K - The Girl in the    True The Girl in the Bubble (Ariana Grand)       220    +25.9    100      True
```

No reading of this table offered here (whether it's now clean enough
to start L1, what Defying Gravity's resolved +96.8s delta means for
arm B, etc.) — deferred to the judge, same as the first L0 pass.

### Phase L1 — version gates + reach accounting artifacts (Sonnet, 2026-07-16)

Executor stops at artifacts, same posture as both L0 entries: no
reading of the table against Appendix C.1's predictions, and no
decision about proceeding to L2, is offered below — deferred to a
judge session per this study's standing process.

**Invocation:** `uv run python
"D:/shared/pikaraoke-songs/lrclib_study/lrclib_study.py" l1`, run
twice from the fully-warm L0 fetch cache (see Reproducibility below).
Zero network calls this phase: the input-variant fetch reuses L0's
`fetch/*.json` cache (all 17 populated after the retry) and
`same_variant` is read from L0's persisted `out/l0_variants.json`
rather than re-resolving the held-out reference (that path is
uncached and would break offline reproducibility — see the L0 judge
read's note on Popular).

**Step-1 corpus cross-check:** still 17==17, script printed `Corpus
cross-check OK` and did not STOP.

**Two appendix-vs-code deviations applied, both flagged rather than
resolved as design choices:**

1. **A.2 replay substitution** — already judge-approved in the L0
   judge-read entry above; applied verbatim as ruled:
   `harness._replay_spans(bundle, ytasr_words, alpha, beta)` then
   `harness._replay_output(bundle, ytasr_words, alpha, beta, realign)`,
   with `alpha`/`beta` read from the bundle's own
   `pipeline_decisions.joint_alpha`/`joint_beta` and asserted `== 2.0`
   (not hardcoded blind, per A.2's own instruction). Assertion held
   for all 17 songs.
2. **NEW — A.5 arm A's `analyze_pass1` unpack.** The appendix sketch's
   `anchors, _ = analyze_pass1(...)` does not execute as written:
   `analyze_pass1` returns a 3-tuple `(anchors, suspect_line_ids,
   ratios)` per its own signature and docstring
   (`pikaraoke/lib/windowed_realign.py`), so a 2-target unpack raises
   `ValueError: too many values to unpack`. Fixed to `anchors,
   _suspects, _ratios = analyze_pass1(...)`, matching the harness's
   own identical call in `_score_against_lrclib`
   (`scripts/replay_ytasr_third_source.py:202`). Unlike A.2, this is a
   fixed-arity elision in the sketch's shorthand, not a
   renamed/reshaped function — no alternative reading exists, and
   unlike A.2 there was no option to defer it (L1 cannot produce any
   output without this line executing). Flagged here for judge review
   rather than treated as pre-approved. Recorded in
   `lrclib_study.py`'s `_arm_a_gate` docstring with the same reasoning.

Separately, not a deviation but worth recording: Appendix A.5's arm B
instruction to port `_theil_sen` + `warp_scaffold_cues`'s fit/gate
logic "verbatim from `git show 835ba2c7:pikaraoke/lib/cue_align.py`"
turns out to be non-optional, not just a reproducibility nicety —
grepped `pikaraoke/lib/cue_align.py` at HEAD for `_theil_sen`,
`WARP_MIN_ANCHORS`, `WARP_MAD_GATE_S`, `warp_scaffold_cues` before
porting and confirmed all four absent: this code was deleted from the
live file entirely (consistent with LRCLIB's removal from
production). The port (fit + gate only, never the `densify_cue_spans`
fallback, per A.5) is in `lrclib_study.py` with a source comment.

**Reproducibility:** ran phase `l1` twice back-to-back from the same
warm, no-network cache; `out/l1_gates.json` from both runs diffed
byte-identical. Satisfies Appendix A.8's reproducibility bar for L1.

**Artifacts saved** (durable, outside git, in the study workspace):
- `D:\shared\pikaraoke-songs\lrclib_study\out\l1_gates.json` — full
  per-song structured output (`rows`) plus the two corpus-level reach
  numbers (`reach`), per A.8.
- `D:\shared\pikaraoke-songs\lrclib_study\out\l1_console.txt` — raw
  stdout of the second (byte-compared) run, redirected straight to
  file rather than copied from a terminal transcript.

Raw table (verbatim from `l1_console.txt`; `arm A`/`arm B` columns
report `bail:<reason>` or `PASS <offset/fit stats>`):

```
song                                             placed                                arm A                                    arm B  same_var
-----------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary Ed    51/89                     bail:wide_spread                         bail:wide_spread      True
'Free' _ Official Lyric Video _ Sony Animation    40/41        PASS off=-0.13s mad=0.20s/16a       PASS a=1.002 b=-0.18 mad=0.19s/16a     False
'Popular' - Wicked 20th Anniversary Edition _     52/62                     bail:wide_spread      PASS a=0.949 b=-11.25 mad=0.64s/28a         -
Beauty and the Beast (1991) - Be Our Guest [UH    77/77        PASS off=-3.24s mad=0.16s/49a       PASS a=1.002 b=-3.45 mad=0.15s/49a      True
Beauty and the Beast (1991) - Belle [UHD]---ot  101/110        PASS off=-5.79s mad=0.32s/39a       PASS a=1.002 b=-6.07 mad=0.32s/39a     False
Ed Sheeran - Best Part Of Me (feat. YEBBA) (Li    37/38        PASS off=+0.12s mad=0.73s/25a       PASS a=0.979 b=+2.36 mad=0.30s/25a     False
Ed­Sheeran­&­Rudimental­­- Bloodstream­[Offici    48/74                     bail:wide_spread      PASS a=1.022 b=-21.94 mad=0.37s/11a     False
HUNTR_X 'This Is What It Sounds Like' (Music V    33/53                     bail:wide_spread       PASS a=1.027 b=-1.14 mad=0.42s/18a      True
Jessie J - Domino (Official Video)---UJtB55Mao    63/67         PASS off=-1.61s mad=0.43s/7a        PASS a=0.995 b=-1.15 mad=0.39s/7a      True
Josh Gad - In Summer (From 'Frozen'_Sing-Along    29/31        PASS off=-0.74s mad=0.36s/14a       PASS a=0.987 b=+0.04 mad=0.46s/14a      True
Mulan _ I'll Make a Man Out of You _ @disneyki    36/47                     bail:wide_spread      PASS a=0.958 b=+35.62 mad=0.10s/22a      True
NSYNC - Paradise                                  55/65       PASS off=+24.02s mad=0.32s/10a      PASS a=1.000 b=+23.98 mad=0.32s/10a     False
Pocahontas - Colors of the Wind (Blu-ray 1080p    37/37        PASS off=-6.03s mad=0.17s/31a       PASS a=1.001 b=-6.15 mad=0.19s/31a      True
Seasons of Love (HD)---UvyHuse6buY                25/34        PASS off=+18.58s mad=0.52s/5a       PASS a=0.958 b=+21.06 mad=0.10s/5a     False
The Lion King - Hakuna Matata Music Video I 4K    33/40         PASS off=+9.16s mad=0.35s/8a       PASS a=0.969 b=+11.06 mad=0.15s/8a      True
The Next Ten Minutes Lyrics---0j8kL24ph8U         67/71        PASS off=+0.76s mad=0.46s/52a       PASS a=1.002 b=+0.38 mad=0.36s/52a      True
Wicked - For Good  (2025) 4K - The Girl in the    29/36       PASS off=-23.12s mad=0.38s/15a      PASS a=1.001 b=-23.25 mad=0.38s/15a      True
```

(Bloodstream's row above has its embedded soft-hyphen/NBSP
metacharacters written out literally rather than as the
console's mangled `�` — see `l1_console.txt` for the exact raw
bytes; cosmetic terminal-encoding artifact only, same as L0, does
not touch any computed value: song identity flows through `Path`
objects from `glob`, never the printed string.)

Corpus-level reach (verbatim):

```
Corpus-level reach:
  unplaced lines on arm-A-PASS songs (E1 structural ceiling): 54/159 (34%)
  Defying Gravity + Bloodstream placed lines on arm-A-bail songs (E2 structural blind spot): 99/99 (100%)
```

No reading of either table against Appendix C.1's predictions or
either reach number's significance is offered here — deferred to the
judge.

### Phase L1 — judge read (Opus, 2026-07-16)

Independent re-derivation from the raw artifacts and code, not the
write-up: recomputed every gate verdict and both reach numbers from
`l1_gates.json`, regenerated the formatted table from the JSON and
diffed it against `l1_console.txt` and the quote above, read
`_arm_a_gate` / `_arm_b_gate` / `_theil_sen` / `phase_l1` /
`_reach_numbers` against Appendix A.5 and their upstream sources
(`srt_cues.offset_mad_against_cues`, `windowed_realign.analyze_pass1`,
`git show 835ba2c7:pikaraoke/lib/cue_align.py`), and re-ran phase `l1`
end to end from this session.

**1. Table + reach — CONFIRMED, including a full independent re-run.**
Gate logic recomputed from the stored scalars with the spec constants
(arm A: `PRIOR_MIN_ANCHORS = 4`, `PRIOR_MAX_MAD_S = 0.75` in
`srt_cues.py`; arm B: `WARP_MIN_ANCHORS = 5`, `WARP_MAD_GATE_S = 2.0`,
matching the pinned commit): 0/17 rows inconsistent. Both reach
numbers recompute exactly (54/159 = 34%; 99/99 = 100%);
`n_anchors == n_anchors_fit` on all 17 rows is structural (both arms
filter anchors by lid-in-cues identically). All 17 table rows and both
reach lines regenerate verbatim from the JSON. My own
`uv run … lrclib_study.py l1` produced a byte-identical
`l1_gates.json` — the third identical run, first from a different
session — with empty stderr: zero network, so the offline
reproducibility claim is confirmed, not just repeated. The
`_theil_sen` port is verbatim against `835ba2c7` (docstring shortened,
body identical); the arm-B gate mirrors `warp_scaffold_cues`'s
fit+gate exactly (same pair orientation, same median-abs-residual
test; the study's `degenerate_fit` label splits out a case the source
folds into its densify fallback — reporting-only, unused in this
data). All four warp symbols confirmed absent at HEAD, so the pin is
mandatory, as recorded.

**2. A.5 unpack — fix APPROVED as forced; classification corrected.**
The 3-target unpack is right and is not a design call: against the
code the study runs on, `analyze_pass1` returns
`(anchors, suspect_line_ids, ratios)` (windowed_realign.py:107), a
2-target unpack raises `ValueError`, anchors is the first element
under either arity, the two extra returns are merge-protection
diagnostics irrelevant to the gate, and the harness's own call
(replay_ytasr_third_source.py:202) is the identical form. But the
executor's classification — "a fixed-arity elision in the sketch's
shorthand" — is wrong as history: the plan was locked 2026-07-12
(`31837f4`) and `analyze_pass1` returned a 2-tuple until `6a73386`
(2026-07-13, the merge-protection commit) added `ratios`. The sketch
was executable as written when locked; this is appendix-vs-code drift
of exactly A.2's class (adjacent work landing after lock), which if
anything strengthens the ruling — same as A.2: mechanical drift, no
re-lock needed. Correct the `_arm_a_gate` docstring's characterization
whenever the file is next touched; nothing operational changes.

**3. C.1 — satisfied; no STOP, no escalation.** Bloodstream and
Defying Gravity both bail arm A (`wide_spread`, mad 0.84 s and
7.14 s) — the STOP condition is untriggered. 12/17 pass = 71% ≈
"roughly 2/3", the top edge of Appendix B's "10-12 of 17". The bail
set (Defying Gravity, Bloodstream, HUNTR_X, Popular, Mulan) is B's
three named songs plus two of its three named candidates — as
on-target as a pre-registration gets. One fragility footnote: Best
Part Of Me passed at mad 0.73 s against the 0.75 s gate; a 0.02 s
wobble makes it 11/17. Carry, don't act.

**4. Arm B — computed correctly; Appendix B's arm-B prediction is
inverted, and the inversion is the phase's most instructive datum.**
B predicted Defying Gravity (the designated test case) rescued and
Bloodstream held out ("a linear warp cannot manufacture missing
verses"). Observed: Defying Gravity is the *only* arm-B bail
(mad 3.51 s over 34 anchors — its +96.8 s master is structurally
longer, not linearly slower), while Bloodstream passes cleanly
(slope 1.022, mad 0.37 s/11a): its anchors all live on shared
content, so the missing verses contribute no anchors to expose the
warp. The warp gate is blind to exactly the different-content case
the constant-offset gate exists to block — the data now demonstrate
why C.4 makes arm B a reach probe that never drives GO. The genuine
rescues look real (Mulan is a textbook linear-tempo variant, slope
0.958 mad 0.097 s/22a; Popular and HUNTR_X similar). Arm-B reach:
16/17 songs, 121/159 unplaced lines (76%) = 2.24x arm A — nominally
past C.4's doubling bar on lines (not songs: 12 → 16), but "at equal
eyeball precision" is unanswerable until L2, and the added reach
includes Bloodstream's 26 unplaced lines, i.e. the phantom-fill
danger case itself. L2 runs the arm-B leg anyway, so no escalation —
but do NOT record C.4's "merits its own study" line unless
Bloodstream's arm-B fills survive Ken's eyeball; that render is now
the study's sharpest safety test.

**5. Transcription wart, same class as Part 1's.** The quoted
Bloodstream row above wrote soft-hyphens (U+00AD) where the true stem
has NBSPs (U+00A0) — literal metacharacters, but the wrong ones (the
one real soft-hyphen is placed correctly). Numeric cells exact; the
other 16 rows are byte-identical to the console capture.
`l1_console.txt` (cp1252 — NBSP and soft-hyphen both encode there, so
it decodes losslessly; no U+FFFD anywhere) and `l1_gates.json`
(UTF-8) stay byte-authoritative; annotated, not rewritten. Also
endorsed: reading `same_variant` from L0's persisted output rather
than re-resolving — spec-conformant (A.4 makes it an L0 output) and
required for the offline bar, per the L0 read's latent note;
Popular's `None` is the correct carried value.

**Verdict.** Everything checks out; no STOP was missed. C.1 is
satisfied and no Model-switching escalation is triggered. The L1
table and both reach numbers are blessed; L2 may proceed on the 12
arm-A-pass songs (plus the arm-B leg per spec), with two carries:
Best Part Of Me's fragile pass, and Bloodstream's arm-B fills as the
eyeball to watch.

### Phase L2 — gated fill simulation artifacts (Sonnet, 2026-07-16)

Executor stops at artifacts, same posture as L0/L1: no GATE L2 verdict
(Appendix C.2 needs Ken's eyeball of the `.lrcfill_*.ass` renders, which
this phase cannot do) and no reading of the numbers below is offered —
deferred to a judge session, then to Ken's eyeball pass.

**Bundled refactor, not a new deviation.** The L1 judge read above ruled
`_arm_a_gate`'s docstring should be corrected "whenever the file is next
touched"; L2 needed the exact same `analyze_pass1` anchor set a second
time (fit against the held-out reference cues, for the cross-variant
check), so this touch extracts `_trusted_anchors(bundle, objs)` out of
`_arm_a_gate` and applies the judge's correction in the same edit
(appendix-vs-code drift of A.2's class, not "sketch elision"). Regression
check before trusting it: backed up `l1_gates.json`, re-ran phase `l1`
end to end, diffed — byte-identical. The refactor changes no computed
value.

**A real bug, found and fixed.** First `l2` run crashed partway through
the arm-B leg (`UnicodeEncodeError` printing a HUNTR/X fill's lyric text:
Windows' cp1252 console codepage can't represent every Unicode
character LRC/Genius lyric text contains — L0/L1 never hit this because
they only ever printed song stems). Arm A's `l2_fills_a.json` had
already written successfully at crash time; arm B's had not. Fix:
`sys.stdout.reconfigure(encoding="utf-8", errors="replace")` (and
`stderr`) near the top of the script — UTF-8 has no undefined
codepoints, so this alone stops the crash; `errors="replace"` is
defensive, not load-bearing. Re-ran clean end to end afterward (see
Reproducibility). The JSON outputs were always `encoding="utf-8"` and
were never at risk; only the console printer was fragile.

**Invocation:** `uv run python
"D:/shared/pikaraoke-songs/lrclib_study/lrclib_study.py" l2`, run twice
back-to-back after the encoding fix. Reuses L0's fetch cache and L1's
persisted `l1_gates.json` (offset/slope/intercept read off it, not
recomputed) — zero network calls.

**Interpretive calls made this phase, flagged for judge review (none
pre-approved, unlike the A.2 substitution):**

1. **Cross-variant reference resolution gated on `same_variant is
   False` specifically**, not merely falsy. Phase L2 step 3 says the
   check applies "only where NOT `same_variant`", which is ambiguous
   between `same_variant in (False, None)` and `same_variant is
   False`. Read as the latter: `same_variant is True` makes the check
   inapplicable (versions match, nothing to cross-check), and
   `same_variant is None` means L0 never resolved a reference at all
   (Popular) — re-attempting resolution here for a `None` song would
   risk the exact network call L1 deliberately avoided for offline
   reproducibility (Appendix A.8). Since `same_variant` is only ever a
   bool when both sides already resolved in L0, gating on `is False`
   is also the only reading that's guaranteed cache-hit-safe. Confirmed
   zero network calls this phase either way (see Invocation).
2. **`_vocal_path` scans the directory instead of `Path.glob`-ing the
   stem.** Appendix A.6's comment says "glob `song_root/"vocal"` for
   the stem prefix"; implemented as a plain `.startswith()` scan
   instead, because this project's own filename convention brackets a
   YouTube ID (`Title [dQw4w9WgXcQ].mp4`, per CLAUDE.md) and `[...]` is
   a glob character class — glob-matching a raw stem would misparse a
   bracketed one. Not exercised on this corpus (every song's exact
   `<stem>---vocal.m4a` existed), so no observed behavior difference,
   but the literal instruction was unsafe as written.
3. **`onset_snap.decode_env_db` used instead of raw `rms_envelope_db`.**
   A.6's sketch calls `rms_envelope_db` directly, which raises on an
   undecodable file; `decode_env_db` is the same project's own
   existing decode-or-bail wrapper for this exact scenario (used by the
   shipped onset-snap pass and the evidence veto). Same constants, same
   caller-visible contract (`None` on failure) A.6 already designed
   the energy check around (`env is None` -> void).
4. **Energy-check index bounds are clamped**, not in the appendix
   sketch. Validated by this run's own data, not just theory: Wicked -
   For Good's arm-A offset (-23.12 s) places `lid=0`'s fill at
   `t0=-1.86s` (a negative index would have wrapped a numpy slice from
   the array's tail instead of raising or correctly reading near-zero);
   Bloodstream's and HUNTR_X's arm-B warps place several fills
   (Bloodstream lid 66-73, HUNTR_X lid 33-52) past the end of their
   decoded vocal envelope entirely (`window.size == 0` after
   clamping) — both songs' media are shorter cuts than the LRCLIB
   master the warp is keyed to, so a warped late-song cue projects
   past the actual audio. The clamp reports these as `energy=void`
   rather than crashing or silently reading wrong data.
5. **ASS render tag split into `lrcfill_a` / `lrcfill_b`.** The plan
   names a single `lrcfill` tag; L2 runs two legs producing two
   different fill sets for songs that pass both arms (e.g. Belle), so
   one tag would collide. Both still sit alongside the shipped
   `<stem>.ass`, never overwriting it.
6. **`auto_pass` is a new, non-appendix metric** = `energy-PASS AND
   collision-free` per fill. Appendix C.2's `good`/`bad-surviving`
   fill categories both require Ken's eyeball, which this phase cannot
   supply; `auto_pass` is the pre-eyeball ceiling GATE L2's "numbers
   first" asks for — every eventual `good` fill is a subset of
   `auto_pass`, nothing outside it can become `good`.
7. **"Plain per-fill dump... into the workspace" (step 4) read as
   satisfied by the redirected console capture** (`l2_console.txt`),
   consistent with Appendix A.8's own established text-and-JSON dual
   persistence, rather than inventing a third per-song file format.

**Reproducibility:** two consecutive `l2` runs from the warm cache;
`l2_fills_a.json` and `l2_fills_b.json` diffed byte-identical across
both. Zero network calls (confirmed by the interpretive-call-1
gating; no exceptions logged).

**Artifacts saved** (durable, outside git, in the study workspace):
- `D:\shared\pikaraoke-songs\lrclib_study\out\l2_fills_a.json`,
  `l2_fills_b.json` — full per-song fill lists (lid, text, span, cue
  text, collision/energy/cross_variant, `auto_pass`) plus each leg's
  corpus summary.
- `D:\shared\pikaraoke-songs\lrclib_study\out\l2_console.txt` — raw
  stdout of the second (byte-compared) run.
- `karaoke/<stem>.lrcfill_a.ass` / `.lrcfill_b.ass` next to each
  fill-bearing song's shipped `.ass`, under
  `D:\shared\pikaraoke-songs\karaoke\` — 9 arm-A files, 13 arm-B
  files, both counts matching each leg's `n_songs_with_fills` exactly.

Full raw console output (verbatim from `l2_console.txt`):

```
Corpus cross-check OK: 17 songs (method_used==joint == not youtube_srt_present)

Arm A leg (offset-shift fill, arm-A-passing songs):
  'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q unplaced=  1 fills=  1 auto_pass=  0
      lid= 35 [ 160.89- 162.29] collision=True  energy=PASS  cross_variant=PASS  text='Free, free' cue='(Free, free)'
  Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjAB unplaced=  0 fills=  0 auto_pass=  0
  Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw      unplaced=  9 fills=  7 auto_pass=  5
      lid= 81 [ 252.76- 253.35] collision=False energy=PASS  cross_variant=PASS  text='Bonjour' cue='Bonjour'
      lid= 86 [ 255.91- 256.46] collision=False energy=PASS  cross_variant=PASS  text='What lovely grapes' cue='What lovely grapes'
      lid= 87 [ 256.46- 257.11] collision=True  energy=PASS  cross_variant=PASS  text='Some cheese' cue='Some cheese'
      lid= 89 [ 257.63- 258.08] collision=False energy=PASS  cross_variant=bail  text='One pound' cue='One pound'
      lid= 93 [ 260.56- 261.04] collision=False energy=PASS  cross_variant=PASS  text='This bread' cue='This bread'
      lid= 94 [ 261.04- 261.59] collision=False energy=PASS  cross_variant=PASS  text='Those fish' cue='Those fish'
      lid= 95 [ 261.59- 262.11] collision=True  energy=PASS  cross_variant=PASS  text="It's stale" cue="It's stale"
  Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Ro unplaced=  1 fills=  1 auto_pass=  1
      lid= 32 [ 193.71- 196.51] collision=False energy=PASS  cross_variant=void  text='Da-dum, da-dum, da-dum, da-dum' cue='Da-dum, da-dum, da-dum, da-dum'
  Jessie J - Domino (Official Video)---UJtB55MaoD0             unplaced=  4 fills=  4 auto_pass=  1
      lid= 12 [  42.83-  44.03] collision=True  energy=PASS  cross_variant=void  text='(Ooh-ooh-ooh-ooh)' cue='Ooh, ooh, ooh, ooh'
      lid= 16 [  50.43-  51.63] collision=True  energy=PASS  cross_variant=void  text='(Ooh-ooh-ooh-ooh)' cue='Ooh, ooh, ooh, ooh'
      lid= 58 [ 193.94- 195.14] collision=True  energy=PASS  cross_variant=void  text='(Ooh-ooh-ooh-ooh)' cue='Ooh, ooh, ooh, ooh'
      lid= 66 [ 222.32- 226.32] collision=False energy=PASS  cross_variant=void  text="Take me down like I'm a domino" cue="Take me down like I'm a domino"
  Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGr unplaced=  2 fills=  0 auto_pass=  0
  NSYNC - Paradise                                             unplaced= 10 fills=  6 auto_pass=  2
      lid=  1 [  40.78-  41.98] collision=False energy=PASS  cross_variant=PASS  text='Ooh' cue='Ooh'
      lid= 39 [ 183.29- 185.39] collision=False energy=PASS  cross_variant=PASS  text="Everything that's happenin'" cue="Everything that's happening"
      lid= 42 [ 193.00- 194.20] collision=True  energy=PASS  cross_variant=PASS  text='Paradise' cue='Paradise (I)'
      lid= 51 [ 227.87- 229.27] collision=True  energy=PASS  cross_variant=PASS  text='And everything' cue='And everything'
      lid= 52 [ 230.17- 232.97] collision=True  energy=PASS  cross_variant=PASS  text="Everything is happenin' (Oh)" cue='Everything is happening (oh, whoa)'
      lid= 59 [ 253.90- 256.25] collision=True  energy=PASS  cross_variant=PASS  text="Everything is happenin' (Everything is h" cue='Everything is happening (everything is h'
  Pocahontas - Colors of the Wind (Blu-ray 1080p HD)---9ThO76p unplaced=  0 fills=  0 auto_pass=  0
  Seasons of Love (HD)---UvyHuse6buY                           unplaced=  9 fills=  6 auto_pass=  4
      lid= 26 [ 163.43- 165.53] collision=True  energy=PASS  cross_variant=void  text='Remember the love' cue='Remember the love'
      lid= 28 [ 168.90- 170.80] collision=False energy=PASS  cross_variant=void  text='Remember the love' cue='Remember the love'
      lid= 30 [ 178.01- 181.84] collision=False energy=PASS  cross_variant=void  text='Measure, measure your life in love' cue='(Measure, measure your life in love)'
      lid= 31 [ 181.84- 183.94] collision=False energy=PASS  cross_variant=void  text='Seasons of love' cue='Seasons of love'
      lid= 32 [ 187.68- 189.78] collision=False energy=PASS  cross_variant=void  text='Seasons of love' cue='Seasons of love'
      lid= 33 [ 189.87- 193.87] collision=False energy=bail  cross_variant=void  text='Measure your life, measure your life in ' cue='(Measure your life, measure your life in'
  The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fw unplaced=  7 fills=  2 auto_pass=  0
      lid= 35 [ 180.56- 181.97] collision=False energy=bail  cross_variant=void  text='Hakuna matata, hakuna matata' cue='(Hakuna matata!) Hakuna matata!'
      lid= 36 [ 186.97- 188.38] collision=False energy=bail  cross_variant=void  text='Hakuna matata' cue='Hakuna matata!'
  The Next Ten Minutes Lyrics---0j8kL24ph8U                    unplaced=  4 fills=  4 auto_pass=  3
      lid=  7 [  46.63-  47.83] collision=False energy=bail  cross_variant=void  text='Cathy' cue='Cathy'
      lid= 63 [ 330.78- 332.18] collision=False energy=PASS  cross_variant=void  text='I do' cue='I do'
      lid= 64 [ 334.13- 335.53] collision=False energy=PASS  cross_variant=void  text='I do' cue='I do'
      lid= 65 [ 337.17- 338.57] collision=False energy=PASS  cross_variant=void  text='I do' cue='I do'
  Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8)  unplaced=  7 fills=  7 auto_pass=  5
      lid=  0 [  -1.86-  -0.66] collision=False energy=bail  cross_variant=void  text='Look' cue='Look'
      lid=  8 [  29.38-  32.88] collision=False energy=PASS  cross_variant=void  text='She spins such beautiful stories' cue='She spins such beautiful stories'
      lid= 15 [  65.39-  68.19] collision=False energy=PASS  cross_variant=void  text='Of seeping on in' cue='Of seeping on in'
      lid= 18 [  77.62-  78.82] collision=True  energy=PASS  cross_variant=void  text='Eventually' cue='Eventually'
      lid= 32 [ 143.30- 146.10] collision=False energy=PASS  cross_variant=void  text='For the popular girl' cue='For the popular girl'
      lid= 33 [ 148.69- 151.49] collision=False energy=PASS  cross_variant=void  text='High in the bubble' cue='High in the bubble'
      lid= 35 [ 175.06- 178.56] collision=False energy=PASS  cross_variant=void  text='For her bubble to pop?' cue='For her bubble to pop?'

Wrote D:\shared\pikaraoke-songs\lrclib_study\out\l2_fills_a.json
  corpus: 38 fills across 9 songs, 21 auto_pass (energy-PASS and collision-free; NOT yet Ken's eyeball -- GATE L2 per Appendix C.2)

Arm B leg (warp fill, arm-B-passing songs):
  'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q unplaced=  1 fills=  1 auto_pass=  0
      lid= 35 [ 161.09- 162.49] collision=True  energy=PASS  cross_variant=PASS  text='Free, free' cue='(Free, free)'
  'Popular' - Wicked 20th Anniversary Edition _ WICKED the Mus unplaced= 10 fills=  4 auto_pass=  0
      lid=  1 [ -10.93-  -6.31] collision=False energy=bail  cross_variant=void  text="Now that we're friends, I've decided to " cue="Elphie, now that we're friends, I've dec"
      lid=  2 [  -6.31-  -4.18] collision=False energy=bail  cross_variant=void  text="You really don't have to do that" cue="You really don't have to do that"
      lid=  4 [  -4.18-   0.02] collision=False energy=bail  cross_variant=void  text="That's what makes me so nice" cue="I know. That's what makes me so nice!"
      lid= 37 [ 105.04- 106.44] collision=False energy=bail  cross_variant=void  text='La-la, la-la' cue='La la, la la!'
  Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjAB unplaced=  0 fills=  0 auto_pass=  0
  Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw      unplaced=  9 fills=  7 auto_pass=  5
      lid= 81 [ 252.87- 253.46] collision=False energy=PASS  cross_variant=PASS  text='Bonjour' cue='Bonjour'
      lid= 86 [ 256.02- 256.57] collision=False energy=PASS  cross_variant=PASS  text='What lovely grapes' cue='What lovely grapes'
      lid= 87 [ 256.57- 257.22] collision=True  energy=PASS  cross_variant=PASS  text='Some cheese' cue='Some cheese'
      lid= 89 [ 257.75- 258.20] collision=False energy=PASS  cross_variant=bail  text='One pound' cue='One pound'
      lid= 93 [ 260.68- 261.16] collision=False energy=PASS  cross_variant=PASS  text='This bread' cue='This bread'
      lid= 94 [ 261.16- 261.71] collision=False energy=PASS  cross_variant=PASS  text='Those fish' cue='Those fish'
      lid= 95 [ 261.71- 262.23] collision=True  energy=PASS  cross_variant=PASS  text="It's stale" cue="It's stale"
  Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Ro unplaced=  1 fills=  1 auto_pass=  1
      lid= 32 [ 191.83- 194.61] collision=False energy=PASS  cross_variant=void  text='Da-dum, da-dum, da-dum, da-dum' cue='Da-dum, da-dum, da-dum, da-dum'
  Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video unplaced= 26 fills= 20 auto_pass=  0
      lid= 27 [ 117.94- 122.21] collision=True  energy=PASS  cross_variant=void  text="Oh, no, no, don't leave me lonely now" cue="Oh, no, no, don't leave me alone lonely "
      lid= 28 [ 122.21- 127.81] collision=True  energy=PASS  cross_variant=void  text="If you loved me, how'd you never learn?" cue="If you loved me, how'd you never learn?"
      lid= 29 [ 128.33- 132.09] collision=True  energy=PASS  cross_variant=void  text='Ooh, coloured crimson in my eyes' cue='Ooh, coloured crimson in my eyes'
      lid= 30 [ 132.09- 136.99] collision=True  energy=PASS  cross_variant=void  text='One or two could free my mind' cue='One or two could free my mind'
      lid= 39 [ 185.27- 187.90] collision=True  energy=PASS  cross_variant=bail  text="Callin' out across the line" cue='Calling out across the line'
      lid= 43 [ 196.01- 198.71] collision=True  energy=PASS  cross_variant=bail  text="Callin' out across the line" cue='Calling out across the line'
      lid= 44 [ 198.71- 201.44] collision=True  energy=PASS  cross_variant=bail  text='All the voices in my mind' cue='All the voices in my mind'
      lid= 45 [ 201.44- 204.15] collision=True  energy=PASS  cross_variant=bail  text="Callin' out across the line" cue='Calling out across the line'
      lid= 46 [ 204.15- 206.84] collision=True  energy=PASS  cross_variant=bail  text='All the voices in my mind' cue='All the voices in my mind'
      lid= 47 [ 206.84- 209.48] collision=True  energy=PASS  cross_variant=bail  text="Callin' out across the line" cue='Calling out across the line'
      lid= 48 [ 209.48- 212.26] collision=True  energy=PASS  cross_variant=bail  text='All the voices in my mind' cue='All the voices in my mind'
      lid= 49 [ 212.26- 215.17] collision=True  energy=PASS  cross_variant=bail  text="Callin' out across the line" cue='Calling out across the line'
      lid= 66 [ 258.67- 261.80] collision=False energy=void  cross_variant=void  text='So, tell me when it kicks in' cue='So tell me when it kicks in'
      lid= 67 [ 261.80- 264.19] collision=False energy=void  cross_variant=void  text='And I saw scars upon her' cue='And I saw scars upon her'
      lid= 68 [ 264.19- 267.36] collision=False energy=void  cross_variant=bail  text='Tell me when it kicks in' cue='Tell me when it kicks in'
      lid= 69 [ 267.36- 268.56] collision=False energy=void  cross_variant=void  text='Brokenhearted' cue='Broken-hearted'
      lid= 70 [ 269.27- 272.42] collision=False energy=void  cross_variant=void  text='And tell me when it kicks in' cue='Tell me when it kicks in'
      lid= 71 [ 272.42- 274.79] collision=False energy=void  cross_variant=void  text='And I saw scars upon her' cue='And I saw scars upon her'
      lid= 72 [ 274.79- 277.84] collision=False energy=void  cross_variant=void  text='Tell me when it kicks in' cue='Tell me when it kicks in'
      lid= 73 [ 277.84- 279.04] collision=False energy=void  cross_variant=void  text='Brokenhearted' cue='Broken-hearted'
  HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop D unplaced= 20 fills= 15 auto_pass=  0
      lid= 33 [ 164.62- 166.71] collision=False energy=void  cross_variant=void  text='This is what it sounds like' cue='This is what it sounds like'
      lid= 35 [ 172.50- 174.60] collision=False energy=void  cross_variant=void  text='This is what it sounds like' cue='This is what it sounds like'
      lid= 37 [ 180.63- 183.80] collision=False energy=void  cross_variant=void  text='This is what it sounds like' cue='This is what it sounds like'
      lid= 40 [ 183.80- 187.72] collision=False energy=void  cross_variant=void  text='We broke into a million pieces, and we c' cue='We broke into a million pieces, and we c'
      lid= 41 [ 187.72- 191.71] collision=False energy=void  cross_variant=void  text="But now I'm seeing all the beauty in the" cue="But now I'm seeing all the beauty in the"
      lid= 42 [ 191.71- 195.78] collision=False energy=void  cross_variant=void  text='The scars are part of me, darkness and h' cue='The scars are part of me, darkness and h'
      lid= 43 [ 195.78- 199.54] collision=False energy=void  cross_variant=void  text='My voice without the lies, this is what ' cue='My voice without the lies, this is what '
      lid= 44 [ 199.54- 203.76] collision=False energy=void  cross_variant=void  text='Why did we cover up the colors stuck ins' cue='Why did we cover up the colors stuck ins'
      lid= 45 [ 203.76- 207.59] collision=False energy=void  cross_variant=void  text='Get up and let the jagged edges meet the' cue='Get up and let the jagged edges meet the'
      lid= 46 [ 207.59- 211.77] collision=False energy=void  cross_variant=void  text="Show me what's underneath, I'll find you" cue="Show me what's underneath, I'll find you"
      lid= 47 [ 211.77- 215.54] collision=False energy=void  cross_variant=void  text='Fearless and undefined, this is what it ' cue='Fearless and undefined, this is what it '
      lid= 48 [ 215.54- 219.61] collision=False energy=void  cross_variant=void  text='(어둠을 밝히려) My voice without the lies, thi' cue='My voice without the lies, this is what '
      lid= 49 [ 219.61- 223.43] collision=False energy=void  cross_variant=void  text='(우리 노래 부르리라) Fearless and undefined, thi' cue='Fearless and undefined, this is what it '
      lid= 50 [ 223.43- 227.31] collision=False energy=void  cross_variant=void  text='(Broken world 거치리라) Truth after all this' cue='Truth after all this time, our voices al'
      lid= 52 [ 227.31- 231.41] collision=False energy=void  cross_variant=void  text=') When darkness meets the light, this is' cue='When darkness meets the light, this is w'
  Jessie J - Domino (Official Video)---UJtB55MaoD0             unplaced=  4 fills=  4 auto_pass=  1
      lid= 12 [  43.06-  44.26] collision=True  energy=PASS  cross_variant=void  text='(Ooh-ooh-ooh-ooh)' cue='Ooh, ooh, ooh, ooh'
      lid= 16 [  50.62-  51.82] collision=True  energy=PASS  cross_variant=void  text='(Ooh-ooh-ooh-ooh)' cue='Ooh, ooh, ooh, ooh'
      lid= 58 [ 193.40- 194.60] collision=True  energy=PASS  cross_variant=void  text='(Ooh-ooh-ooh-ooh)' cue='Ooh, ooh, ooh, ooh'
      lid= 66 [ 221.64- 225.62] collision=False energy=PASS  cross_variant=void  text="Take me down like I'm a domino" cue="Take me down like I'm a domino"
  Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGr unplaced=  2 fills=  0 auto_pass=  0
  Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_Cc unplaced= 11 fills=  9 auto_pass=  1
      lid= 21 [ 132.07- 133.44] collision=True  energy=PASS  cross_variant=void  text='Be a man' cue='(Be a man)'
      lid= 23 [ 136.15- 137.28] collision=True  energy=PASS  cross_variant=void  text='Be a man' cue='(Be a man)'
      lid= 25 [ 140.06- 141.47] collision=True  energy=PASS  cross_variant=void  text='Be a man' cue='(Be a man)'
      lid= 33 [ 184.54- 185.83] collision=True  energy=PASS  cross_variant=void  text='Be a man' cue='(Be a man)'
      lid= 35 [ 188.66- 189.78] collision=True  energy=PASS  cross_variant=void  text='Be a man' cue='(Be a man)'
      lid= 37 [ 192.58- 193.93] collision=True  energy=PASS  cross_variant=void  text='Be a man' cue='(Be a man)'
      lid= 40 [ 204.70- 206.02] collision=True  energy=PASS  cross_variant=void  text='Be a man' cue='(Be a man)'
      lid= 42 [ 209.03- 210.02] collision=False energy=PASS  cross_variant=void  text='Be a man' cue='(Be a man)'
      lid= 44 [ 212.84- 214.17] collision=True  energy=PASS  cross_variant=void  text='Be a man' cue='(Be a man)'
  NSYNC - Paradise                                             unplaced= 10 fills=  6 auto_pass=  2
      lid=  1 [  40.74-  41.94] collision=False energy=PASS  cross_variant=PASS  text='Ooh' cue='Ooh'
      lid= 39 [ 183.29- 185.39] collision=False energy=PASS  cross_variant=PASS  text="Everything that's happenin'" cue="Everything that's happening"
      lid= 42 [ 193.01- 194.21] collision=True  energy=PASS  cross_variant=PASS  text='Paradise' cue='Paradise (I)'
      lid= 51 [ 227.89- 229.29] collision=True  energy=PASS  cross_variant=PASS  text='And everything' cue='And everything'
      lid= 52 [ 230.19- 232.99] collision=True  energy=PASS  cross_variant=PASS  text="Everything is happenin' (Oh)" cue='Everything is happening (oh, whoa)'
      lid= 59 [ 253.93- 256.28] collision=True  energy=PASS  cross_variant=PASS  text="Everything is happenin' (Everything is h" cue='Everything is happening (everything is h'
  Pocahontas - Colors of the Wind (Blu-ray 1080p HD)---9ThO76p unplaced=  0 fills=  0 auto_pass=  0
  Seasons of Love (HD)---UvyHuse6buY                           unplaced=  9 fills=  6 auto_pass=  4
      lid= 26 [ 159.86- 161.96] collision=True  energy=PASS  cross_variant=void  text='Remember the love' cue='Remember the love'
      lid= 28 [ 165.10- 166.92] collision=True  energy=PASS  cross_variant=void  text='Remember the love' cue='Remember the love'
      lid= 30 [ 173.83- 177.50] collision=False energy=PASS  cross_variant=void  text='Measure, measure your life in love' cue='(Measure, measure your life in love)'
      lid= 31 [ 177.50- 179.60] collision=False energy=PASS  cross_variant=void  text='Seasons of love' cue='Seasons of love'
      lid= 32 [ 183.09- 185.19] collision=False energy=PASS  cross_variant=void  text='Seasons of love' cue='Seasons of love'
      lid= 33 [ 185.19- 189.03] collision=False energy=PASS  cross_variant=void  text='Measure your life, measure your life in ' cue='(Measure your life, measure your life in'
  The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fw unplaced=  7 fills=  2 auto_pass=  1
      lid= 35 [ 177.19- 178.56] collision=False energy=bail  cross_variant=void  text='Hakuna matata, hakuna matata' cue='(Hakuna matata!) Hakuna matata!'
      lid= 36 [ 183.41- 184.81] collision=False energy=PASS  cross_variant=void  text='Hakuna matata' cue='Hakuna matata!'
  The Next Ten Minutes Lyrics---0j8kL24ph8U                    unplaced=  4 fills=  4 auto_pass=  3
      lid=  7 [  46.33-  47.53] collision=False energy=bail  cross_variant=void  text='Cathy' cue='Cathy'
      lid= 63 [ 331.00- 332.39] collision=False energy=PASS  cross_variant=void  text='I do' cue='I do'
      lid= 64 [ 334.35- 335.75] collision=False energy=PASS  cross_variant=void  text='I do' cue='I do'
      lid= 65 [ 337.40- 338.80] collision=False energy=PASS  cross_variant=void  text='I do' cue='I do'
  Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8)  unplaced=  7 fills=  7 auto_pass=  5
      lid=  0 [  -1.97-  -0.77] collision=False energy=bail  cross_variant=void  text='Look' cue='Look'
      lid=  8 [  29.30-  32.80] collision=False energy=PASS  cross_variant=void  text='She spins such beautiful stories' cue='She spins such beautiful stories'
      lid= 15 [  65.34-  68.14] collision=False energy=PASS  cross_variant=void  text='Of seeping on in' cue='Of seeping on in'
      lid= 18 [  77.58-  78.78] collision=True  energy=PASS  cross_variant=void  text='Eventually' cue='Eventually'
      lid= 32 [ 143.32- 146.12] collision=False energy=PASS  cross_variant=void  text='For the popular girl' cue='For the popular girl'
      lid= 33 [ 148.71- 151.51] collision=False energy=PASS  cross_variant=void  text='High in the bubble' cue='High in the bubble'
      lid= 35 [ 175.11- 178.61] collision=False energy=PASS  cross_variant=void  text='For her bubble to pop?' cue='For her bubble to pop?'

Wrote D:\shared\pikaraoke-songs\lrclib_study\out\l2_fills_b.json
  corpus: 86 fills across 13 songs, 23 auto_pass (energy-PASS and collision-free; NOT yet Ken's eyeball -- GATE L2 per Appendix C.2)
```

(Bloodstream's row above has its embedded NBSP/soft-hyphen metacharacters
written out literally, same annotation as the L0/L1 entries — cosmetic
console-encoding artifact only, `l2_console.txt`/`l2_fills_b.json` stay
byte-authoritative.)

No breakdown beyond the script's own printed output above is computed
here (per Ken's 2026-07-16 tightening: executor verifies artifacts
exist, does not tally or cross-reference them) and no reading against
Appendix C.2's bar is offered — GATE L2 per the plan's own text needs
Ken's eyeball of the `.lrcfill_a.ass` / `.lrcfill_b.ass` renders before
any fill can be called `good`.

### Phase L2 — judge read (Opus, 2026-07-16)

Independent re-derivation from the raw artifacts and code, not the
write-up — this round **read-only, by Ken's direction** (new standing
process: judge rounds reuse the artifacts on disk; end-to-end re-runs
only on a trigger — an inconsistency in the read-only checks, or a
determinism claim with nothing behind it. Neither triggered.)
Re-derived: every fill's `t0/t1` arithmetic from the on-disk inputs
(fetch-cache cue spans + `l1_gates.json` scalars + the ported caps),
all tallies and corpus breakdowns, the full console, the plan quote,
the `_fill_line` port against its pinned source, the `onset_snap` and
`_write_ass_variant` contracts, and the flat-cache basis of the
offline claim. (The entry above was tightened mid-round — its corpus
breakdown block retracted as executor over-reach; the corresponding
numbers below are my own derivation from the JSONs, which happens to
confirm what the retracted block said.)

**1. Tables + tallies — CONFIRMED; all 124 fills re-derived
independently.** For every fill in both JSONs I recomputed `t0/t1`
from `cue_spans_for_lines` over the cached input variant, the L1 gate
scalars (`offset_s` for arm A, `slope`/`intercept` for arm B — the
leg reads them off `l1_gates.json`, so the rounded persisted values
are the exact inputs), and a replica of the `_fill_line` caps:
124/124 exact, plus `text` and `cue_text` (via my own
`map_lines_to_cues` recompute) exact. `auto_pass` arithmetic holds on
every fill; per-song and corpus tallies confirm (arm A 38/9/21, arm B
86/13/23); leg membership equals L1's pass sets in bundle order;
`n_unplaced` matches `l1_gates.json` row-for-row. The **entire
163-line console regenerates from the two JSONs with zero differing
lines**. Judge-derived corpus breakdowns: collision=True 12/38 (A)
and 33/86 (B); energy PASS/bail/void 33/5/0 (A) and 56/7/23 (B);
cross-variant PASS/bail/void 13/1/24 (A) and 13/10/63 (B); the four
arm-B-only songs (Popular, Bloodstream, HUNTR_X, Mulan) contribute
48 fills and exactly 1 auto_pass (Mulan lid 42). Renders: 9 `_a` +
13 `_b` files exist and match every `ass_path`. Scope note:
energy/collision verdict *values* were not re-derived per fill (they
need the audio decode and the replay's placed spans — that is what a
re-run would buy); the code paths are audited below and the
aggregates are internally consistent — arm B's `energy void=23`
decomposes exactly into the two past-media-end groups the entry
names (Bloodstream lids 66-73 = 8, HUNTR_X lids 33-52 = 15).

**2. Reproducibility — mtime forensics in place of a re-run; offline
claim verified structurally; refactor regression independently
confirmed.** All L2 artifacts postdate the script's final edit
(11:18:05), so nothing on disk is stale against the code reviewed.
One wrinkle: `l2_console.txt` (11:20:19) predates the on-disk JSONs
(11:22:25 / 11:23:06), so the console capture and the JSONs come from
*different* runs of the byte-compared pair — the entry's "raw stdout
of the second (byte-compared) run" label is off by one run. Under the
executor's determinism claim this is moot, and the 163/163
regeneration proves console↔JSON content equivalence directly.
Offline: the only network-capable path this phase is
`_load_lrclib_reference` inside the cross-variant setup; it runs only
for `same_variant is False` songs, and all six of those stems have
flat-cache files under `lrclib/` on disk (tier-2 hits; Popular, the
one song whose resolution would go live, is gated out by call 1). The
`_trusted_anchors` refactor: current `l1_gates.json` is
SHA-256-identical to my own pre-refactor backup from the L1 judge
round — an independent regression, no re-run needed. (Footnote: the
on-disk `l1_gates.json` (11:14:15) predates the encoding fix
(11:18:05), so the executor's regression ran on the pre-fix script;
that edit is I/O-only — `sys.stdout/stderr` reconfigure — so the
conclusion carries.)

**3. The seven interpretive calls — all APPROVED**, with precision
notes:

1. `same_variant is False` gating: the only reading that is both
   semantically defined (the check compares against a resolved
   *different-variant* reference; under `None` no reference ever
   resolved, so there is nothing to check) and offline-safe
   (re-resolving Popular hits the network, breaking A.8). Data
   consistent: every fill on a True/None song is `void`. The
   additional un-specced void condition — `reference_offset` bailed —
   is likewise forced: without a trustworthy offset there is no
   target to be "within 1.0 s" of. That is why Best Part Of Me's and
   Seasons of Love's fills are all void despite `same_variant=False`
   (their anchor fits against the *reference* cues bail or lack
   per-lid cues), while Belle/Free/NSYNC/Bloodstream get real
   PASS/bail verdicts.
2. `_vocal_path` directory scan: the literal "glob for the stem
   prefix" is unsafe under this project's own bracketed-ID filename
   convention (`[...]` is a glob character class), and I reproduced
   that hazard myself this round: a bracket-blind `Test-Path` on
   Belle's flat cache false-negatived until a literal directory
   listing showed the file. The scan is a strict superset; not
   exercised (every direct `<stem>---vocal.m4a` existed).
3. `decode_env_db` over raw `rms_envelope_db`: verified
   `rms_envelope_db` raises `CalledProcessError` on undecodable input
   and `decode_env_db` is the project's shared decode-or-None wrapper
   (same constants, same `None` contract A.6's void case already
   handles). Reuse over reimplementation is the right call.
4. Energy-check clamping: the numpy tail-wrap hazard is real (an
   unclamped negative index reads from the array's *end*). Two
   behaviors, restated precisely where the entry lumps them: a window
   wholly past the envelope end → `void` (all 23 observed); a
   negative `t0` → clamped read at the array head — Girl in the
   Bubble lid 0 evaluated `env[0:1]` and got `bail`, semantically
   right for a pre-roll span. Footnote: a wholly negative span is
   *evaluated* at the head rather than voided; had the audio opened
   loud it would PASS on non-evidence. Immaterial here (the one
   instance bailed; production would clamp spans first), but it is
   the sim's one soft spot if this code is ever reused.
5. `lrcfill_a`/`lrcfill_b` tag split: forced — nine songs carry
   renders in both legs; the plan's single `lrcfill` tag would have
   the arm-B leg overwrite arm A's render. Verified
   `_write_ass_variant` writes `<stem>.<tag>.ass` alongside the
   shipped `.ass`, never over it.
6. `auto_pass`: it is exactly C.2's two automatic conjuncts, so
   `good ⊆ auto_pass` by construction and it is the correct "numbers
   first" ceiling. Excluding `cross_variant` from it is right (C.2
   does not include it); the column stays evidence for the eyeball,
   not a gate.
7. Console capture as the per-fill dump: all step-4 fields are
   present and it sits in the workspace, consistent with A.8's dual
   text+JSON persistence. Nit: the console truncates `text`/`cue` at
   40 chars; the JSON is the complete record.

**4. One render defect found — eyeball material, not a bug to fix.**
The shipped `generate_ass` clamps an event's *start* to ≥ 0 but not
its *end*, so a fill ending before t=0 formats a negative-hour
timestamp (`Dialogue: 0,0:00:00.00,-1:59:59.54,…` — verified in the
file) and the event can never display. Affected: Girl in the Bubble
lid 0 in both renders, Popular `_b` lids 1-2 (invisible) and lid 4 (a
sub-second flash at t=0). All are energy-bail, none `auto_pass`, so
nothing eyeball-relevant is hidden — noted so Ken doesn't chase
missing lines. Not a production concern: the pipeline never produces
negative times; the sim feeds the generator out-of-domain input by
design ("report only"). Also: the quoted Bloodstream row's wart this
time is NBSP→plain-space normalization with the real soft-hyphen
preserved (Part 1's wart class, not L1's soft-hyphen substitution);
numeric cells exact, console/JSON byte-authoritative as annotated.

**5. Pre-eyeball guidance — the arm-B renders are not worth Ken's
time, and the numbers already close two open questions.**

- **The GATE is the arm-A eyeball: 21 auto_pass fills across 7
  renders** (Belle 5, Girl in the Bubble 5, Seasons of Love 4, Next
  Ten Minutes 3, NSYNC 2, Best Part Of Me 1, Domino 1). `good` and
  `bad_surviving` both read off auto_pass fills only, so the Free and
  Hakuna Matata renders (0 auto_pass) are optional context. The C.2
  bar is reachable (ceiling 21 ≥ 6).
- **Arm-B renders: skip.** C.2 is arm-A-only by its own header, and
  C.4 is already decided by the automatic gates: raw reach 86 vs 38
  fills (2.26x) collapses to 23 vs 21 auto_pass (1.10x) — the
  arm-B-only songs contribute 48 fills and exactly 1 auto_pass.
  "At least doubles at equal eyeball precision" cannot trigger
  regardless of what an eyeball finds, because the doubling never
  survives the gates. C.4's "merits its own study" line is **not
  recorded**.
- **The L1 carry resolved at the gate level.** Bloodstream's 20
  arm-B fills — the designated sharpest safety test — all fail
  automatically: 12 collide with placed lines (album-only verses
  projected onto occupied audio) and 8 land past the 4:07 cut's
  audio end (`void`). The phantom-danger fills never reach a render;
  the gates themselves neutralized the case the L1 read flagged.
- **Skeptical-attention list within the 21:** Belle lid 89 ("One
  pound") is auto_pass with `cross_variant=bail` — the only
  automatic timing signal available says it is mistimed; Best Part
  Of Me lid 32 rides the fragile 0.73-mad L1 pass with no
  corroborating timing evidence (cross-variant voided); and the
  repeat/chant fills (Seasons' two "Seasons of love" + "Remember the
  love", Next Ten's three "I do"s) sit on the known repeat-instance
  weak spot. Corroboration split of the 21: 6 cross-variant PASS
  (Belle 4, NSYNC 2), 1 bail (Belle 89), 14 void.

**Verdict.** All executor numbers confirmed; all seven interpretive
calls approved; the refactor is regression-clean against my
independent pre-refactor backup. GATE L2 now waits on exactly one
thing: Ken's eyeball of the 7 arm-A renders (21 auto_pass fills)
against C.2's `good ≥ 6 AND bad_surviving = 0`. The arm-B leg is
closed as a data exercise — its renders need no eyeball, and C.4
stays unrecorded.

### GATE L2 — eyeball verdicts and mechanical gate addition (Opus, 2026-07-16)

Ken eyeballed the 7 arm-A renders (the 21 auto_pass fills, per the
judge read's scope ruling; arm-B renders skipped as ruled).
Verdicts:

- **16 good**: Belle 5 (including lid 89 "One pound", the one fill
  the cross-variant check had flagged — a false alarm from the
  reference side), Girl in the Bubble 5, Next Ten Minutes 3,
  NSYNC 2, Domino 1.
- **5 bad_surviving**: Best Part Of Me lid 32 — the "Da-dum" line
  does not exist in this unplugged arrangement at all; it is
  replaced by a wordless multi-tone vocalization, so the energy
  check passed honestly over the wrong content (exactly the phantom
  class Phase L2's honesty caveats predicted no automatic gate can
  catch). Seasons of Love lids 28/30/31/32 — the lines exist and the
  fills sit in the right section, but all are late "by quite a lot"
  (judge classification: not sung during the swept span →
  `bad_surviving` under C.2's definition). Ken also observed some of
  the *placed* lines in that section running late — a separate
  matcher artifact on a sparse song (5 anchors, 25/34 placed),
  recorded here as context for the repeat-pileup/matcher-quality
  thread, not actionable in this study.

**C.2 read-off:** `good = 16 ≥ 6` clears; `bad_surviving = 5 ≠ 0`
fails — GO is blocked as written. C.2's escape clause is invoked:
one specific, mechanical gate addition, one L2 re-run with it, one
re-read of the criterion. This entry records the gate; the re-run is
the next executor leg.

**Judge diagnosis (mechanisms behind both failures, from data
already in `l1_gates.json`):** Seasons of Love is a genuine ~4%
tempo mismatch — its arm-B Theil-Sen fit (slope 0.9582, mad
0.097 s) is 5x tighter than its arm-A constant-offset fit (mad
0.52 s), and the constant-offset model's predicted error at the four
fill positions is 3.8-4.6 s late, matching the eyeball exactly. Best
Part Of Me carried two warnings: the fragile L1 pass (mad 0.73 vs
0.75) and slope 0.9787 (2.1% off unity) — tempo drift as a proxy for
the arrangement mismatch that replaced the lyric. Considered and
rejected: promoting arm B to fill placer. It would very likely fix
Seasons' timing (its warp puts lid 28 at 165.1 vs arm A's 168.9) but
cannot fix Best Part — a nonexistent line has no correct time; arm
B's version of that fill ([191.8-194.6]) is still collision-free
energy-PASS, still a phantom → still NO-GO — and arm B's gate is
content-blind at admission (L1's Bloodstream finding), which is the
riskier failure class.

**Adopted gate (Ken, 2026-07-16): tempo/arrangement-consistency.**
A song is fill-eligible iff arm A passes AND its L1 arm-B Theil-Sen
slope satisfies `|slope − 1| ≤ FILL_MAX_SLOPE_DEV = 0.01`; a song
whose arm B bailed has no trustworthy slope estimate and is
ineligible (conservative; the case is empty on this corpus — all 12
arm-A-pass songs pass arm B). Mechanistic, not fitted: a
constant-offset fill is invalid by construction when the true
cue-to-media relation is a warp, and slope drift doubles as an
arrangement-mismatch signal — the two observed failure modes.
Separation on this corpus: the two bad songs sit at 4.2% (Seasons)
and 2.1% (Best Part) deviation; the worst good-fill song is Domino
at 0.51%; In Summer (1.34%) and Hakuna Matata (3.07%) are also
excluded at zero cost (no auto_pass fills). The gate reads off the
already-persisted `l1_gates.json` — no new measurement.

**Re-run instructions (executor leg):** re-run phase `l2` with the
gate applied to the arm-A fill leg only (the arm-B leg is closed as
a data exercise; leave it as-is). Fills are per-song independent, so
the 16 surviving fills must reproduce unchanged; expected arm-A leg:
10 songs in leg, 7 with fills, 31 fills, 16 auto_pass. Delete the
two stale renders (`Seasons of Love …lrcfill_a.ass`, `Ed Sheeran -
Best Part Of Me …lrcfill_a.ass`) so the render set matches the
eligible set. Then the judge re-reads C.2 once — the final allowed
pass. Ken's verdicts above carry over to the unchanged 16 fills
(expected read: `good = 16, bad_surviving = 0` → GO, which per
Phase L4 means writing the separate production-wiring plan — not
starting it inside this study).

### Phase L2 re-run — mechanical gate applied, by derivation not re-execution (Sonnet, 2026-07-16)

**Environment note.** This leg was actioned from the Linux box, which
has no access to `D:\shared\pikaraoke-songs\lrclib_study\` — the
workspace holding `lrclib_study.py`, `l1_gates.json`, the L0 fetch
cache, and the `.lrcfill_a.ass` renders all live there exclusively.
Ken confirmed the flat `pikaraoke-songs/lrclib/<stem>` cache is
equivalent on both machines, but on inspection it wasn't needed
either: the gate itself requires **no new measurement** (it reads off
already-persisted `l1_gates.json` scalars — a pure filter), and both
source tables it filters are already captured byte-verbatim in this
file's own Results log, each independently reproduced twice and
judge-confirmed: the L1 gate table (arm-B `slope` per song, Phase L1
artifacts entry above) and the L2 arm-A console dump (per-song
fills/auto_pass + per-fill collision/energy, Phase L2 artifacts entry
above). Re-executing the script would re-derive numbers already
established twice over; instead this leg extracted both blocks
verbatim from the committed plan file via `sed` (not hand-transcribed:
`l1_table_rows.txt` = lines 798-814, `l2_armA_console.txt` = lines
1057-1112 of this file) and applied the gate programmatically —
`gate_l2_rerun.py` in the session scratchpad, parses both blocks with
anchored regexes (the L1 row parser is anchored on the fixed-format
`placed` field, `\d+/\d+`, specifically because "For Good  (2025)"'s
internal double-space would otherwise be mistaken for a column
boundary) and asserts its own parse against known totals (17 L1 rows,
12 arm-A-pass song blocks, pre-gate 38 fills/21 auto_pass) before
computing anything.

**Result — gate excludes 4 songs, not 2.** Applying
`|slope − 1| ≤ FILL_MAX_SLOPE_DEV = 0.01` to all 12 arm-A-pass songs'
arm-B slopes (not just the two named in the "Re-run instructions"
paragraph above):

```
song                                                      slope   dev%  gate  fills  auto_pass
-----------------------------------------------------------------------------------------------
'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q   1.002  0.20%  PASS      1          0
Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjAB   1.002  0.20%  PASS      0          0
Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw   1.002  0.20%  PASS      7          5
Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Ro   0.979  2.10%  FAIL      1          1
Jessie J - Domino (Official Video)---UJtB55MaoD0          0.995  0.50%  PASS      4          1
Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGr   0.987  1.30%  FAIL      0          0
NSYNC - Paradise                                          1.000  0.00%  PASS      6          2
Pocahontas - Colors of the Wind (Blu-ray 1080p HD)---9ThO76p   1.001  0.10%  PASS      0          0
Seasons of Love (HD)---UvyHuse6buY                        0.958  4.20%  FAIL      6          4
The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fw   0.969  3.10%  FAIL      2          0
The Next Ten Minutes Lyrics---0j8kL24ph8U                 1.002  0.20%  PASS      4          3
Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8)   1.001  0.10%  PASS      7          5

Post-gate: 8 songs in leg, 6 with fills, 5 with auto_pass fills,
29 fills, 16 auto_pass
```

Excluded: Best Part Of Me (2.1%), In Summer (1.3%), Seasons of Love
(4.2%), Hakuna Matata (3.1%) — all four percentages match the ones
already named in the "Adopted gate" paragraph above (that paragraph
itself says "In Summer (1.34%) and Hakuna Matata (3.07%) are also
excluded at zero cost", so the fuller 4-song exclusion was already
correctly derived there; the immediately-following "Re-run
instructions" paragraph's "10 songs in leg... delete the two stale
renders" undercounts it to 2). This entry's 8/6/29 read is the one
consistent with applying the adopted gate literally and identically to
every song, and is what I'm treating as authoritative.

**The discrepancy is verdict-inert.** In Summer contributed 0 fills
before or after (nothing changes whether it's counted "in leg" or
not); Hakuna Matata contributed 0 auto_pass fills before or after
(only its 2 non-auto_pass fills drop from the raw corpus tally, moving
"fills" 31→29). The number that actually feeds C.2 — **auto_pass = 16**
— is identical under either reading, because neither newly-excluded
song had any auto_pass fill to lose. One practical consequence:
Hakuna Matata's `.lrcfill_a.ass` render is a third stale render that
also needs deleting on the Windows box alongside the two already named
(In Summer never had a render — 0 fills throughout) — a pending
hygiene action outside this session's reach.

**The surviving 16 auto_pass fills, independently re-enumerated:**

```
Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw: 5 -> lids [81, 86, 89, 93, 94]
Jessie J - Domino (Official Video)---UJtB55MaoD0: 1 -> lids [66]
NSYNC - Paradise: 2 -> lids [1, 39]
The Next Ten Minutes Lyrics---0j8kL24ph8U: 3 -> lids [63, 64, 65]
Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8): 5 -> lids [8, 15, 32, 33, 35]
```

This set matches Ken's own GATE L2 eyeball breakdown exactly, song for
song and count for count ("Belle 5 (including lid 89 'One pound'...),
Girl in the Bubble 5, Next Ten Minutes 3, NSYNC 2, Domino 1") — lid 89
is confirmed present in Belle's surviving 5. Neither excluded song
(Best Part Of Me, Seasons of Love) contributes any lid to this set, so
none of Ken's 16 "good" verdicts or 5 "bad_surviving" verdicts change
meaning — the bad_surviving set (Best Part lid 32, Seasons lids
28/30/31/32) is fully and only carried by the two now-excluded songs.

**Numbers read against C.2: good = 16, bad_surviving = 0 — bar met.**
Per this study's established executor/judge split (same posture as
L0/L1/L2 above), this entry stops at the derivation and its
cross-checks; it does not itself pronounce the criterion satisfied.
Flagging for the judge round the "Re-run instructions" paragraph asked
for: the arithmetic above is triple cross-referenced (my own parse's
internal assertions against known pre-gate totals; the four gate
percentages against the "Adopted gate" paragraph's own text; the 16
surviving lids against Ken's per-song eyeball breakdown) and none of
the three disagree, so I believe this is ready for Ken to treat as the
final C.2 read, contingent on confirming the 8-vs-10/29-vs-31
discrepancy above doesn't change anything he intended — it is a
documentation undercount in the GATE L2 entry's own instructions
paragraph, not a new data question.

### Phase L2 re-run — judge read (Fable, 2026-07-16)

Independent re-derivation from the raw artifacts, not the write-up —
here the "raw artifacts" are necessarily the same two blocks the
executor derived from (the L1 gate table and the L2 arm-A console
dump, quoted verbatim in this file's own Phase L1/L2 artifacts
entries), since the Windows workspace is unreachable from this box
too. Re-derived twice over: by hand from the quoted blocks, and by a
fresh programmatic parse written this session (the executor's
`gate_l2_rerun.py` was NOT reused — it lived in a prior session's
scratchpad and is gone; my parser locates both blocks by content
rather than line number, asserts the same pre-gate invariants — 17 L1
rows, 12 arm-A-pass songs, all 12 with an arm-B slope, 38 fills / 21
auto_pass — and additionally re-verifies every printed per-song
`auto_pass` counter against its own per-fill collision/energy rows).

**1. Gate-filter result — CONFIRMED, cell for cell.** Applying
`|slope − 1| ≤ 0.01` to the 12 arm-A-pass songs: excluded = Best Part
Of Me (0.979, 2.1%), In Summer (0.987, 1.3%), Seasons of Love (0.958,
4.2%), Hakuna Matata (0.969, 3.1%); the arm-B-bail ineligibility
clause is vacuously satisfied (every arm-A-pass row in the L1 table
shows arm B PASS). Post-gate: 8 songs in leg; 6 with fills (Free 1,
Belle 7, Domino 4, NSYNC 6, Next Ten 4, Girl in the Bubble 7) = 29
fills; auto_pass 0+5+1+2+3+5 = 16 on 5 songs. All 12 of the entry's
table rows and its post-gate summary line reproduce exactly. One
precision check the entry did not make explicit: its deviations come
from the L1 table's 3-decimal *printed* slopes, not the
full-precision `l1_gates.json` values. That is lossless here —
printed-rounding uncertainty is ±0.05 percentage points and the
nearest verdict to the 1% boundary (In Summer, 1.30% printed / 1.34%
full-precision per the Adopted-gate paragraph) sits 0.30 points clear
on the FAIL side, with Domino (0.50%/0.51%) the nearest PASS at 0.50
points clear; no rounding can flip any of the 12 verdicts, and all
four FAIL songs' full-precision deviations are independently quoted
in GATE L2's own Adopted-gate paragraph and agree.

**2. Derivation-not-execution — APPROVED, for this leg's specific
shape.** Legitimacy rests on three facts, each verified rather than
assumed: (i) the adopted gate is a pure per-song filter over
already-persisted L1 scalars — GATE L2's own text says "no new
measurement", and nothing in the filter touches audio, replay, or
network; (ii) both source blocks carry unusually strong provenance —
the L1 table is byte-identical across three runs (two executor, one
judge, different sessions) and the L2 arm-A console regenerates
163/163 lines from the twice-byte-identical JSONs per the L2 judge
read, with numeric cells verified exact in the plan quotes both
times; (iii) fills are per-song computed (each song's spans derive
from its own L1 offset, cues, and stem; collision is against its own
placed lines), so removing songs from the leg cannot alter any
surviving song's fills or verdicts — a true re-execution would
reproduce the 8 surviving blocks byte-identically. Given (i)-(iii),
re-running the script would have measured nothing new; the derivation
*is* the re-run, minus workspace side effects (finding 6b). Scope
note carried forward honestly: per-fill energy/collision *values*
were never re-derived by any judge (they need the audio; the L2 judge
audited the code paths instead) — but the 16 survivors carry the
strongest per-fill confirmation available, Ken's own eyeball.

No STOP was owed. Model switching's escalation triggers govern
pre-registered criteria and appendix-vs-code mismatches; C.2 plus its
escape clause is unambiguous on this data (one mechanical gate, one
re-run, one re-read). The ambiguity the executor hit is an internal
inconsistency within the GATE L2 entry itself — post-data
instructions, not a pre-registered criterion — and the executor took
the only defensible reading (the gate's adopted definition over the
instructions paragraph's derived bookkeeping), flagged the
discrepancy prominently, and deferred the C.2 pronouncement to this
read. That is escalation in substance. The executor-discipline bar
("every Results-log number comes from a command run in that session")
is met: the numbers came from a recorded programmatic parse with
pre-asserted totals, and the cited line ranges (798-814, 1057-1112)
both verify correct against the current file. One weakness, noted not
fixed: unlike every prior leg, no durable artifact sits behind this
one (the derivation script was session-ephemeral). Mitigated — the
computation is fully re-derivable from this file alone, and this read
just did so independently.

**3. The 2-vs-4 undercount — CONFIRMED, and confirmed
verdict-inert.** The Re-run instructions' expected 10/7/31/16
reproduces exactly under "exclude only Best Part and Seasons"
(12−2 songs, 9−2 fill-bearing, 38−1−6 fills, 21−1−4 auto_pass) — an
arithmetic slip against the Adopted-gate paragraph's own text, which
had already named In Summer (1.34%) and Hakuna Matata (3.07%) as
additional zero-cost exclusions. The correct figures are 8/6/29/16.
The difference lives entirely in In Summer (0 fills — no effect
anywhere) and Hakuna Matata (2 fills, both energy-bail, 0 auto_pass —
moves fills 31→29 only); auto_pass, the only number C.2 reads, is 16
under either reading. Also confirmed: Hakuna Matata had 2 fills so a
`.lrcfill_a.ass` render was written and is now a third stale render;
In Summer never had one (0 fills throughout). The pending Windows-box
hygiene is three deletions (Seasons, Best Part, Hakuna Matata), not
the two GATE L2 named.

**4. Surviving 16 vs Ken's verdicts — EXACT MATCH, verified by
partition.** My own auto_pass enumeration from the per-fill dump:
Belle lids 81/86/89/93/94 (87 and 95 collide), Domino 66 (12/16/58
collide), NSYNC 1/39 (42/51/52/59 collide), Next Ten 63/64/65 (7
energy-bail), Girl in the Bubble 8/15/32/33/35 (0 energy-bail, 18
collides) — identical to the entry's list, lid for lid. Cross-walk to
GATE L2: the 21 pre-gate auto_pass fills partition into Ken's 16 good
+ 5 bad_surviving; the 5 bad are itemized (Best Part 32; Seasons
28/30/31/32), and I verified those are *exactly* the auto_pass sets
of those two songs — so the bad mass is fully and only carried by two
now-excluded songs, and the surviving 16 are forced by complement to
be exactly Ken's 16 good. Song counts confirm (Belle 5 incl. lid 89,
Girl in the Bubble 5, Next Ten 3, NSYNC 2, Domino 1). No surviving
fill lacks an eyeball verdict; no eyeballed-good fill is lost.

**5. C.2 re-read — the escape clause's single allowed re-read: bar
MET.** `good = 16 ≥ 6` and `bad_surviving = 0`. Under C.2 as written,
**E1 = GO**: gated fill earns the separate production-wiring plan,
with the gate spec now arm-A pass AND `|arm-B Theil-Sen slope − 1| ≤
FILL_MAX_SLOPE_DEV = 0.01` (arm-B bail → ineligible) on top of the
existing caps/energy/collision machinery. Per Phase L4 and the
study's own text, writing that plan is a separate deliverable on
Ken's go — not started here. Scope note: this closes E1 only; Phase
L3 (E2, absence evidence) has not run, and whether to run or descope
it is Ken's call at the same checkpoint.

**6. Residual notes, none blocking.** (a) Any future workspace re-run
should read full-precision `l1_gates.json` slopes and expect
8/6/29/16 — not the Re-run instructions' 10/7/31/16. (b) When the
Windows box is next touched: delete the three stale renders, and fold
`FILL_MAX_SLOPE_DEV` into `lrclib_study.py`'s arm-A leg with a
regenerated `l2_fills_a.json`, so the durable workspace matches this
file's authoritative numbers (currently the gated result exists only
in this Results log). (c) The entry's line-number citations are
correct today but fragile under any future edit above them; the
durable anchors are the fenced blocks in the Phase L1/L2 artifacts
entries themselves. (d) Cosmetic: the entry's phrase "the two
now-excluded songs" (bad_surviving discussion) means Best Part and
Seasons specifically, while four songs are excluded overall — clear
in context, noted to prevent a misread.

**Verdict.** The re-run-by-derivation is confirmed number for number
(4 excluded / 8 in leg / 6 with fills / 29 fills / 16 auto_pass;
surviving lids exact), the methodology is legitimate for precisely
this leg's shape — a measurement-free filter over twice-reproduced,
judge-verified inputs with per-song independence — and no STOP was
missed; the GATE L2 instructions' undercount is real and
verdict-inert as claimed. C.2's single allowed re-read: `good = 16,
bad_surviving = 0` → **E1 = GO**. On Ken: the three-render deletion +
workspace persistence (hygiene), the L3/E2 decision, and Phase L4 —
including whether and when the separate production-wiring plan is
written.
