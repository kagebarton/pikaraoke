Model: Claude Fable 5 (design); executors per the phase table in `plans/PROGRAM.md`

# Route: line timing (LRCLIB / Musixmatch-line / NetEase, + demoted richsync)

**Ladder rung 2, foreign-clock half.** A provider gives line-level
timings on its own clock, so the cues cannot be trusted as-is: they enter
as a **warped scaffold** (`warp_scaffold_cues`) driving the same windowed
aligner the SRT route uses. Uploader-SRT cues are the trusted-as-is half
of rung 2 and live in `plans/route-srt.md`.

**Status: CLOSED 2026-09-08 (Ken) — S-1 withdrawn, work ceased, F2
never built.** A song with line timing but no SRT routes to the joint
matcher (`plans/route-no-timing.md`), permanently; fetched line timing
reaches production only through that route's gated fill, which is to be
widened from LRCLIB to the sidecar sources there (its Phase 5). The
closing entry at the end of this log records the Fable assessment, the
ruling, and what survives. Nothing in this file is open: M6-d is moot,
the S-3 extension is moot, S-E is not run, and GATE L (Phase 4 below)
is re-homed to the joint route's aligner.

**Do not re-open this route with a per-song gate.** Two facts on record
here are the reason it closed: the fetched sidecar tracks our recording
on 4 of 17 songs (M7-a), and no per-song test constructible from what is
on disk separates the sound ones from the wrong-edit ones (the warp gate
accepted 5 of 6; the shape diagnostic catches 2 of those; the duration
signal that catches Domino also rejects Colors of the Wind). Where the
source is right the timing is good — that is why it survives as a
per-line fill source, where a wrong-edit line loses on its own.

*Kept as the record of GATE S, M6, M7 and the stratified fallback. The
status block that stood from 2026-07-19 to 2026-09-08 is superseded by
the entries below and is not restated here.*

## Phase 3 — scaffold + engine corpus probe (GATE S)

GPU corpus run via the Phase 0 harness, over the genius-origin songs
with any line timing (per the coverage table: all 17 minus Girl in the
Bubble; line sources = Musixmatch line, NetEase, LRCLIB `.lrc` already
on disk from the E1 fill path, and — for word songs — richsync line
starts). Fetch line bodies for the 8 line-level winners the same
`--save-bodies` way (same sidecar format, `kind: line`, LRC text body):
Defying Gravity, Be Our Guest, I'll Make a Man Out of You, NSYNC
Paradise, Hakuna Matata, What It Sounds Like, In Summer, The Next Ten
Minutes — the last three re-fetched even though NetEase/title-only won
them in a2, so every sidecar records its winning mechanism.

*Amendment (2026-07-19, Decision C — see Results log):* I'll Make a Man
Out of You re-fetched as `word`/0.745 (its full query now surfaces a
confident richsync, so the locked early-exit never re-queried the
title-only variant that won a2). The line-bodies fixture set is **7**;
the song participates in Phase 3 as a word song via the
richsync-line-starts source above, and is exempted from the
recorded-map_rate regression assert on resume.

*Amendment 2 (2026-07-19, Ken-ratified — warp offset-rescue tier; see
the Results log's "S-A warp diagnostic" entry):* `warp_scaffold_cues`
gains a constant-offset rescue tier — when the affine Theil-Sen fit
fails its MAD gate, fit `offset = median(anchor_start −
scaffold_start)` with slope fixed at 1.0 over the same common lines,
accepted iff its residual MAD clears the same `WARP_MAD_GATE_S` and
the same `WARP_MIN_ANCHORS` floor; otherwise densify fallback exactly
as before. Reuses the locked constants — no new thresholds. S-A
re-runs on the amended machinery *before* S-B is built and run, so
both arms and the S-1 re-read share one warp.

Arms, in order; later arms only where earlier ones justify the GPU time:

- **S-A (required):** scaffold + whisper `slice_align`. Metrics per
  song: re-pace %, worst overlap, flags, warp fit stats
  (`n_common`, MAD, gate fired?). Compare against: (a) the Phase 0
  fresh joint baseline for the same songs — **this is the scaffold-route
  GO/NO-GO comparison**; (b) the `835ba2c7` 10-song numbers where the
  song overlaps (sanity: the port didn't lose the win).
- **S-B (GATE C-1 = yes, satisfied):** same run, CTC `slice_align`
  adapter (windowed MMS_FA over the section slice — the windowed prior
  is exactly the constraint C-3's smear pattern needs; scratchpad
  adapter reusing Phase 1's proven recipe/normalization verbatim,
  wrapped to the `(t0, t1, text, label) -> words | None` contract).
  Same metrics.
- **S-B2 (if GATE O = O-1):** the **CTC-first engine arm** — full-song
  CTC align of the sheet (Phase 1's own output, recomputed), per-line
  score gate, windowed repair only on failing sections (repair windows
  from the warped scaffold via the trusted lines' Theil-Sen fit;
  windows sliced from the cached emission, no audio re-slicing). Same
  metrics plus fraction-of-lines-repaired. This is the engine
  architecture's direct A/B against scaffold-first (S-A/S-B).
  *(Does not run — GATE O′ ruled engine OFF, 2026-07-19.)*
- **S-C (if S-B or S-B2 looks competitive):** CTC `slice_align` on the
  SRT cue-align corpus vs the 5b whisper baseline — the direct
  "can CTC improve cue align" measurement on the proven path.
  *Amendment (2026-07-20, Ken-ruled): this bullet's original "13-song"
  figure never matched the corpus (16/16 SRT-sourced songs per
  Baseline 2 and the current on-disk count, confirmed on the Windows
  box after the machine move). Ken confirmed all 16 have proper
  uploader SRTs — S-C runs the full 16, not a 13-song subset.*
- **S-D (diagnostic, cheap, no GPU):** for warp-gate-failed songs, record
  what the fallback would be — union-anchor densify vs joint matcher —
  by comparing S-A's fallback output against the joint baseline for
  those songs.
- **S-E (optional, offline, no GPU align):** CTC words swapped in as
  the joint matcher's align stream in the replay harness over the
  genius-origin corpus, vs the Phase 0 fresh baseline — measures Ken's
  GATE C observation ("synced sections beat whisper even on mismatch
  songs") and informs the engine plan's deletion inventory.

**GATE S** — mechanical read-offs (Opus executes; Ken retains eyeball
veto everywhere and rules anything a rule leaves open):

- S-1: scaffold-route GO iff, vs the Phase 0 joint baseline over the
  same songs: mean worst-overlap strictly lower, flagged-song count no
  higher, rendered-line coverage no lower, and no single song's worst
  overlap regresses by > 1.0 s without a recorded cause Ken accepts.
  Ken's spot-eyeball vetoes any new artifact class the metrics missed.
  *Status (2026-07-19, final): **GO on the S-B arm** — mean PASS
  (0.47 vs 0.54), coverage PASS, flag count PASS (Ken ratified the
  any-defensible-mapping reading), per-song cap PASS (Ken accepted
  both causes: Defying Gravity = correctly-gated structural mismatch,
  Man Out of You = genuine two-voice overlap on baseline-hidden
  lines). See the GATE S final-rulings entry.*
- S-2 (aligner per path): the CTC arm is selected for a path iff it is
  at least as good as the whisper arm on all three of mean re-pace,
  mean worst-overlap, and flag count, with no song > 1.0 s worse on
  overlap; otherwise whisper (proven default). The SRT switch (S-C vs
  the 5b baseline) uses the same rule plus Ken's eyeball veto — extra
  caution on the proven path.
  *Status (2026-07-19): CTC SELECTED for the non-SRT scaffold path —
  strictly better on all three metrics, cap holds (worst worsening
  +0.6). S-C has not run; the SRT switch stays open. Ken intent
  (2026-07-19): S-C **will eventually run** — unordered, not a
  sequenced phase (the SRT route is fully separate; no gate depends
  on it, its GATE C-1 license is already satisfied). Motivation: CTC
  may give tighter word timings on the SRT route and eliminate the
  need for edge snapping (consistent with GATE C's finding and
  Appendix D's snap-off-on-CTC default). Same rule + Ken's eyeball
  veto when it runs; the S-B adapter already proves the slice_align
  contract — the SRT harness just needs the same pluggable hook the
  scaffold harness got.*
- S-3: warp-failure branch = densify fallback iff its flags + overlap
  on the warp-failed songs are ≤ the joint baseline's on those songs;
  tie → densify (one fewer code path).
  *Status (2026-07-19, final): **joint-matcher routing** — densify
  FAILS on Defying Gravity (2.6 vs 0.2 s, robust to arm choice) and
  Ken accepted the coverage trade (crammed interpolated dialog is
  unacceptable for karaoke). Scope: warp-failed = MAD-gate reject
  only. See the GATE S final-rulings entry.*
- S-4: **Appendix D/E constants recorded** (Opus, in
  `plans/ctc-sync-engine.md` — both are already locked as
  design/procedure; this step only fills measured constants such as
  the snap re-enable exception and the gate band).
- S-5: **architecture ruling** — engine branch iff GATE O ∈ {O-1, or
  O-GRAY with Ken's explicit GO} AND S-B2 meets the S-2 comparison
  rule against the best scaffold arm AND Ken concurs on eyeball;
  anything else → scaffold-first (fully specified, lower risk).
  *Status (2026-07-19): the GATE O condition is now unmeetable
  (O′-GRAY ruled, no GO) — S-5 = scaffold-first by rule; what stays
  live at GATE S is S-1/S-2/S-3 on the best scaffold arm.*

Scoring-circularity rule (pre-registered): LRCLIB held-out MAD is **not
a metric for any scaffold-routed song** — once LRCLIB feeds the
scaffold, that oracle is circular (already noted in `835ba2c7`'s plan).
Scaffold/engine quality is judged on re-pace/overlap/flags + eyeball;
the harness's held-out scoring remains valid only for joint-matcher
replays.


## Phase 4 — non-Latin alignment form (GATE L)

> **Re-homed 2026-09-08.** The line route is closed, so the romanizer
> attaches to the joint route's aligner (whichever GATE J1 selects) and
> is tracked from `plans/route-no-timing.md`. The arms below stand as
> written; only their host changed. Still blocked on the Mandarin corpus.

Commissioned by Ken 2026-09-01. Rung 2 (the line route) silently drops
every line it cannot romanize: `sb_ctc_adapter.make_slice_align` builds
`kept = [(raw, normalize_word(raw)) ...]` and filters the empties, so a
Hanzi line normalizes to nothing, `kept` empties, and the adapter
returns `None` — the whole line re-paces from its cue. Appendix D's
non-Latin carve-out was locked 2026-07-18 as data-independent design
caution, **not** as a measured finding: no CJK audio has ever been put
through MMS_FA in this project. This phase measures it.

**Scope: Mandarin only.** One character = one syllable = one pinyin
token, so timing-to-character back-mapping is 1:1, without the sub-word
ambiguity the Latin path carries. Japanese (mixed kana/kanji), Korean,
Thai and Arabic do not share that property and stay on the whisper
rescue, untouched. Appendix D's rule is already per-line and
majority-based, so the romanizer gates on majority-CJK lines and
nothing else changes.

**Display text is not at stake.** Appendix A locks the line route to
render the sheet, and the adapter already carries `raw` beside the
alignment form into its returned word list. The romanization is an
internal alignment form only; the singer reads the original script by
construction. No display work is in this phase.

**Prerequisite (Ken's action, blocks the phase):** a Mandarin corpus
with Genius sheets or uploader SRTs, sized like S-C's. No arm runs
until it exists; nothing else in this plan waits on it.

Arms, in order; later arms only where earlier ones justify the cost:

- **L-0 (diagnostic, cheap, no GPU):** on one Mandarin song, dump the
  uroman-style alignment form beside `pypinyin` + `jieba` and record
  heteronym and segmentation damage (多音字 — 长 chang/zhang, 了
  le/liao, 行 xing/hang are common in lyrics; uroman converts
  char-by-char with no context, so it picks wrong readings and runs
  syllables together). Establishes which failure mode is live before
  any GPU time is spent — romanizer quality, or emission quality.
- **L-A:** `pypinyin` + `jieba` word segmentation as the alignment
  form, MMS_FA unchanged, per-character back-map. Adapter delta is one
  function (`normalize_word` → a pluggable alignment-form callable).
  Stated hypothesis: MMS_FA was itself trained on uroman-ized text
  across its 1000+ languages including Mandarin, so its emissions are
  not inherently blind to romanized Chinese — the model has seen it.
  Tones are lost; forced alignment does not need them.
- **L-B (only if L-A fails GATE L):** a second CTC bundle with a Hanzi
  vocabulary, routed on majority-CJK lines.
  `torchaudio.functional.forced_align` is model-agnostic — it takes any
  emission matrix plus token ids — so the emission-slicing recipe
  carries over unchanged. Candidates: character-level CTC fine-tunes
  emitting Hanzi directly from a ~3–5k character vocab
  (`jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn`, the
  TencentGameMate `chinese-wav2vec2` fine-tunes). Out-of-vocab
  characters fall into the existing OOV-skip bookkeeping. Per-character
  timing is what Chinese karaoke wants anyway, one char being one sung
  syllable. Costs: a second model download and VRAM (~1.2 GB for the
  large variant; smaller exist) plus a routing switch on majority-CJK
  lines. The singing-vs-speech domain gap applies, but it is the same
  gap MMS_FA already tolerates on the Latin path. (Charsiu, a
  purpose-built Mandarin forced aligner, is noted and not adopted: its
  frame-classification API does not slot into the emission recipe.)

**GATE L** — the S-2 rule restated on the Mandarin corpus, no new
threshold invented: the romanized-CTC arm is selected iff it is at
least as good as the whisper arm on all three of mean re-pace, mean
worst-overlap and flag count, with no song > 1.0 s worse on overlap;
otherwise whisper (proven default) and Appendix D's carve-out stands as
written. Ken retains the eyeball veto. Rationale for reusing S-2
verbatim: whisper fallback is already acceptable on rung 2, so a
romanized CTC arm only earns its place if it beats whisper on the
failure modes CTC was brought in for — melisma robustness and line-edge
sharpness.

Rulings produced here:

- L-1: romanized alignment form GO/NO-GO (the S-2 restatement above).
- L-2: which romanizer — L-A's `pypinyin`+`jieba`, or L-B's Hanzi-vocab
  bundle. L-B is only reached if L-A fails L-1.
- L-3: **Appendix D's non-Latin bullet amended** with the resulting
  constant, recorded there the way S-2 was.

**Dependencies if L-A ships:** `pypinyin` (pure Python, small) and
`jieba` (~5 MB dictionary) become runtime dependencies, needed only on
the F2 path. Fork rule: the alignment-form callable lands in a new
`pikaraoke/lib/align_form.py`, not as edits to `token_align.py`.


## Results log

### 2026-07-19 — Phase 3 setup (--save-line-bodies) — STOPPED at song 3/8; Decision C

Sonnet's line-bodies fetch (the Phase 3 list of 8, same `ensure_timing`
path as `--save-bodies`) ran 2/8 clean, then STOPPED at I'll Make a Man
Out of You (`vGfJeW_CcFY`): the full query now returns a richsync
candidate that clears the confidence bar on its own (track 84351940,
"I'll Make A Man Out Of You" / "Donny Osmond feat. Disney Characters",
`word`, map_rate 0.745), so `reference_pick`'s locked early-exit
returned it without ever re-querying title-only — the variant that
produced a2's recorded `line`/0.851 (that run's full query came back
unconfident, firing the retry). The one-sided map_rate regression guard
fired (0.851 → 0.745); the kind *upgrade* itself was already an
accepted outcome of the line-bodies guard. Sidecar persisted as-fetched
(disk-first contract).

**Design ruling (Fable, 2026-07-19) — Decision C: the early-exit stays
as locked; word/0.745 is the conformant pick; no Appendix B amendment,
no code change; per-song guard exemption; line-bodies cohort 8 → 7.**
(Issued under the same Ken-convened window as Decisions A/B; folded at
Ken's direction.) This is neither a Bloodstream-class ranking question
nor a clean_key-class deviation: Appendix B locks the early-exit
explicitly ("title-only tried only when the full query yields nothing
confident") and today's run executed it exactly. The 0.851 line
candidate was not demoted or mis-ranked — it was **never retrieved this
run**, because a2's result was the same procedure answering different
provider state. Both runs conformant; Musixmatch's index moved
underneath. The guard did its job: surfaced cross-run drift for
adjudication instead of swallowing it. Where Bloodstream was a
*ranking* event (the key adjudicated; the guard caught a kind change),
this is a *retrieval* event (the key never adjudicated; the guard
caught provider drift) — they stress different parts of the pillar, and
both parts held.

**Why no change:** (1) both proposed kind-aware early-exits gate on the
full-query winner's kind, and the winner here is `word` — the best
achievable kind — so both would still skip the retry and change
nothing; adopting either is spec churn. (2) The only change that
recovers 0.851/line is unconditionally running both variants and
key-comparing — doubling query cost corpus-wide (the exact cost the
locked gate exists to avoid) on n=1 evidence of *provider drift*, not
of a procedure defect: Decision A's n=1 refusal again. (3) No
correctness pressure: the word candidate is the original Mulan
recording (Donny Osmond is the film's singing voice — no
Arty-Remix-style version-mismatch flag) and 0.745 clears the bar
comfortably. Had both candidates been on the table, the key would
legitimately have picked 0.851/line (line demotion is first-class per
Decision A) — but nothing obliges the procedure to go looking, and a
selection-time kind preference in either direction stays ruled out.
The 0.851 candidate is *unretrieved*, not "irrelevant because word
exists" — that framing would smuggle in the kind preference Decision A
rejected. Cross-run stability is the disk-first sidecar's job, not the
query surface's: drift only bites on forced refetches, which are
batch-tool territory with exactly this guard armed.

**Disposition:** the word/0.745 sidecar stands as-fetched. It cannot
serve as a line-bodies fixture (a richsync body is a different
artifact), so the song exits that cohort (**8 → 7**) — not orphaned
from Phase 3, whose line-source enumeration already covers it ("for
word songs — richsync line starts"); it participates as a word song
with scaffold line timing from its richsync `ts` values. It does
**not** retroactively join 2b's word cohort (pre-registered cohorts
shrink via guards, they don't grow mid-flight; 2b stays 14);
production routing is cohort-agnostic and routes it word-level per
Appendix A on its sidecar alone.

**Resume (song 3 exempted, songs 4–8 fresh):** exempt the song from
the recorded-map_rate regression assert the same flag-and-accept way
as Bloodstream's `kind_demoted_ruling` (suggested sidecar field:
`query_drift_ruling`), citing this ruling as provenance; the guard
stays armed for the remaining songs.

**2026-07-19 — resume executed, 8/8 clean, 0 STOPs.** Implemented the
exemption: `LINE_BODIES_SONGS` gained a `query_drift_exempt` flag
(mirroring `kind_exempt`'s shape, distinct name — this is a retrieval
event, not a ranking one); I'll Make a Man Out of You's already-persisted
word/0.745 sidecar was reused unchanged from disk (disk-first, no
refetch) and gained `query_drift_ruling` on top. Re-ran
`--save-line-bodies`: the 2 already-fetched songs (Defying Gravity, Be
Our Guest) reused their sidecars unchanged; the remaining 5 fetched
clean:

| song | recorded | new | delta | kind | variant |
| --- | --- | --- | --- | --- | --- |
| NSYNC Paradise | 0.785 | 0.785 | +0.000 | line | netease |
| Hakuna Matata | 0.625 | 0.625 | +0.000 | line | netease |
| What It Sounds Like | 0.811 | 0.811 | +0.000 | line | full |
| In Summer | 0.581 | 0.581 | +0.000 | line | netease |
| The Next Ten Minutes | 0.958 | 0.930 | -0.028 | line | full |

The Next Ten Minutes' -0.028 delta is inside the one-sided 0.05
tolerance (recorded-rate regression, not a STOP) — ordinary reference-pick
variance, not flagged further. All 5 matched their expected `kind: line`
and cleared the guard. **8/8 sidecars persisted (7 line-bodies fixtures
+ 1 query-drift word exemption), 0 STOPs.** `pikaraoke-songs/lyrics/`
now holds 25 sidecars total (17 from Phase 2a + these 8) — Phase 3
setup is complete; the S-A/S-B corpus run can proceed.

Commit: `feat(scripts): --save-line-bodies richsync/line persistence for
the Phase 3 corpus cohort` (script + this Results log entry together).

### 2026-07-19 — Phase 3 S-A (scaffold + whisper corpus run), Sonnet 5 executor

Ran `scripts/scaffold_align_corpus.py` (`--timing sidecar`, default) over
all 17 genius-origin bundles. First pass surfaced two real harness gaps,
neither a design decision — fixed directly (commit
`fix(scripts): scaffold harness tolerates missing YouTube ASR /
media_duration_s`), not escalated: **6/17 songs never had YouTube ASR
captions fetched** (confirmed absent from disk and every backup —
Free, What It Sounds Like, Domino, In Summer, NSYNC Paradise, The Next
Ten Minutes), so `run_song`'s `asr_path` is now `Optional`, degrading
to transcribe-only anchors instead of the corpus runner skipping the
song; **7/17 bundles have `media_duration_s: None`** (the 6 above plus
Seasons of Love), so `duration` now falls back to the vocal stem's own
probed wav length when the bundle field is absent. Verified via a
single-song smoke test (Domino, hit by both gaps) before rerunning the
full corpus.

**17/17 songs aligned clean, 0 failures, 0 hidden lines**, 6/17 show a
drift flag (gap/instant-line signature), 45 mostly-instant lines total
across the corpus (0 parked-tail gap lines):

```
song                                        plc  hid  rea  rep rsec  maxgap gapL instL   anc   scf   ovl(old>new)
----------------------------------------------------------------------------------------------------------------
Jessie J - Domino (Official Video)---UJtB5   67    0    3   20    -    2.0s    0     1    14    61   1.3->4.6  s
Seasons of Love (HD)---UvyHuse6buY           34    0    0    7    -    1.9s    0     0    13    31   5.8->0.7  s
Ed Sheeran & Rudimental­ - Bloodstream [Of   74    0    0   46    -    1.7s    0    13    23    52   9.8->2.3  s
Ed Sheeran - Best Part Of Me (feat. YEBBA)   38    0    0    4    -    1.7s    0     0    16    33   1.1->0.0  s
Wicked - For Good  (2025) 4K - The Girl in   36    0    1   19    -    1.7s    0    17    23     0  31.1->3.2  s
Beauty and the Beast (1991) - Be Our Guest   77    0    2    5    -    1.7s    0     0    61    53   0.0->3.0  s
'Popular' - Wicked 20th Anniversary Editio   62    0    0   13    -    1.6s    0     1    44    39   2.9->1.7  s
NSYNC - Paradise                             65    0    4   26    -    1.3s    0     0    12    51   6.1->5.3  s
'Defying Gravity' - Wicked 20th Anniversar   89    0    3   39    -    1.3s    0     2    43    61   8.4->4.3  s
Josh Gad - In Summer (From 'Frozen'_Sing-A   31    0    0    2    -    1.3s    0     0    24    18   1.4->1.2  s
The Next Ten Minutes Lyrics---0j8kL24ph8U    71    0    1    2    -    1.3s    0     0    63    66  13.4->0.5  s
Beauty and the Beast (1991) - Belle [UHD]-  110    0    1    5    -    1.1s    0     0    85    94   1.5->1.3  s
'Free' _ Official Lyric Video _ Sony Anima   41    0    0    0    -    1.1s    0     0    28    33   4.6->0.0  s
HUNTR_X 'This Is What It Sounds Like' (Mus   53    0    0   22    -    1.1s    0    11    15    43   5.5->0.5  s
Mulan _ I'll Make a Man Out of You _ @disn   47    0    0    7    -    1.0s    0     0    22    35   1.7->2.4  s
Pocahontas - Colors of the Wind (Blu-ray 1   37    0    0    2    -    0.9s    0     0    35    35   0.0->0.0  s
The Lion King - Hakuna Matata Music Video    40    0    0    2    -    0.7s    0     0    19    25   0.0->2.8  s
```

`ovl(old>new)` here is `max_line_overlap` on the bundle's stored
`output_line_timings` (today's persisted production output for that
song) vs. this run's scaffold output — **not** the same measurement as
Phase 0's fresh joint-route replay table above (that table's own
`overlap(rec>new)` column is the joint matcher's internal metric,
computed offline, never written back to the bundle). The two are
different instruments on different routes; reconciling them into the
S-1 GO/NO-GO comparison (mean worst-overlap, flagged-song count,
rendered-line coverage vs. the Phase 0 baseline, same songs) is Opus's
mechanical read-off, not this executor's call — this entry reports the
raw table per the Model-switching discipline ("Output at a GATE is a
table, never a verdict"), it does not rule on S-1.

Per the plan text, Girl in the Bubble is excluded from the S-1
comparison (no line timing at all — `n_scaffold=0` above confirms it,
`n_anchors=23` from ASR+transcribe only); it ran in this table for
completeness since the harness now handles it identically to every
other song, not because it's in scope for S-1.

S-B (CTC `slice_align`, licensed by GATE C-1=yes) has not been run —
it needs a new scratchpad windowed-CTC adapter (Phase 1's recipe,
wrapped to the `(t0, t1, text, label) -> words | None` contract) that
doesn't exist yet, a distinct build step from S-A. Stopping here to
report S-A rather than starting it without a checkpoint.

### 2026-07-19 — GATE S-1 read-off (S-A arm) — NO-GO

**GATE S-1 read-off (Fable executing the locked rule, 2026-07-19) —
S-1: NO-GO on the S-A arm's evidence. Two of the four conjuncts fail
decisively; one passes decisively; one is not mechanically decidable
and goes to Ken (moot for this verdict).** (The Model-switching table
assigns this read-off to Opus; executed by Fable at the requester's
direction in the same convened window as Decisions A–C. Nothing here
trades on design authority — the rule was applied as locked, no
thresholds invented, and Opus re-executing the arithmetic will
reproduce it.)

*Reconciliation recorded (the S-A entry left this to the read-off):*
the Phase 0 table's `overlap(rec>new)` right value and the S-A table's
`ovl(old>new)` right value are different instruments, but both report
the same physical quantity — that route's worst rendered-line overlap
in seconds — so the mechanical pairing is right-value vs right-value
per song, over the 16 in-scope songs (Girl in the Bubble excluded per
the plan text; `scf=0` confirms). Cross-check that the instruments are
comparable enough: on the two songs where both routes render the
identical full sheet, the instruments agree exactly where nothing
changed (Colors of the Wind 0.0 → 0.0) and disagree only where the
scaffold genuinely regressed (Be Our Guest 0.0 → 3.0).

- **Mean worst-overlap strictly lower: FAIL.** Scaffold 1.91 s vs
  baseline 0.54 s (needed < 0.54). Not a gray-zone margin — 3.5× the
  bar in the wrong direction.
- **No song regresses > 1.0 s without a recorded cause Ken accepts:
  FAIL.** Nine songs regress: NSYNC Paradise +4.6, Domino +4.5,
  Defying Gravity +4.1, Be Our Guest +3.0, Hakuna Matata +2.8, Man
  Out of You +2.4, Popular +1.7, Belle +1.3, In Summer +1.2. The S-A
  entry records no causes, so none exist for Ken to have accepted.
  Improvements for the record: Bloodstream 6.7 → 2.3 and Free
  1.0 → 0.0.
- **Rendered-line coverage no lower: PASS decisively.** Scaffold
  renders the full sheet with zero hidden lines on all 16; strictly
  higher than baseline on 14, equal on 2 (Be Our Guest, Colors of the
  Wind).
- **Flagged-song count no higher: NOT MECHANICALLY DECIDABLE → Ken.**
  The baseline flag marks coverage shortfall (8 in-scope songs carry
  the `!` marker); the S-A flag marks drift signature (5 in-scope:
  Domino, Bloodstream, Popular, Defying Gravity, HUNTR_X — the
  entry's 6th, Girl in the Bubble, is excluded). These measure
  different failure modes on different routes — one of which the
  scaffold structurally cannot exhibit (it always renders everything)
  and one the joint route doesn't emit. A naive 5 ≤ 8 favors the
  scaffold, but the rule defines no cross-system mapping and the
  read-off declines to invent one. Moot: the conjunction already
  fails twice.

*What the verdict does and doesn't mean:* the rule's conjunction was
built exactly for this trade — the scaffold bought total coverage at
the price of overlap, and the locked rule says that trade is not GO.
Two things are Ken's, not the read-off's: (1) whether "overlap on
lines the baseline never rendered" is an acceptable recorded cause
for some of the nine regressions — noting it cannot excuse all of
them, since Be Our Guest regresses +3.0 s on an identical 77/77
rendered set, and Domino/Belle/In Summer regress on near-identical
sets; (2) whether the mean clause should ever be recomputed on a
common rendered set — that is a rule amendment, not a read-off.
Procedurally, NO-GO here binds the S-A arm's showing only: S-1
governs the scaffold route, S-B (CTC `slice_align`) has not run, and
the route's final S-1 standing should be re-derived on the best
scaffold arm once S-B lands — consistent with S-2/S-5 already
waiting on it.

**Regression diagnosis (Ken eyeball → mechanism, 2026-07-19).** Ken
eyeballed the nine regressions (scaffold `.ass` vs the joint `.ass`,
same clips). On NSYNC Paradise ~3:25 the overlapping lines are not a
local over-hold — they are from *different sections of the sheet*
(pre-hook and chorus rendering concurrently). That ruled out "the
scaffold just paces line ends too long" and prompted a mechanism
trace (`warp_scaffold_cues` reproduced offline, no GPU — it is pure
text-match + Theil-Sen). The nine split cleanly into two unrelated
failure modes; neither is fixed by changing scaffold selection.

```
song            Δovl  anchors  MAD    mode
NSYNC Paradise  +4.6  12/65    3.28   1: scaffold DISCARDED -> densify fallback
Defying Gravity +4.1  43/89    5.80   1: scaffold DISCARDED -> densify fallback
Domino          +4.5  14/67    0.19   2: warp used; align displaces a repeat
Be Our Guest    +3.0  61/77    0.17   2: warp used; align displaces a line
Hakuna Matata   +2.8  19/40    0.12   2: warp used (signature)
Man Out of You  +2.4  22/47    0.30   2: warp used (signature)
Popular         +1.7  44/62    0.43   2: warp used (signature)
Belle           +1.3  85/110   0.12   2: warp used (signature)
In Summer       +1.2  24/31    0.06   2: warp used (signature)
```

*Mode 1 — scaffold discarded, densify fallback (Paradise, Defying
Gravity).* The MAD gate fired (Paradise 3.28 s over 9 common lines;
Defying Gravity 5.80 s): the external master's clock genuinely does
not fit the audio (Paradise fit slope 1.25 ≈ 25 % tempo delta), so the
scaffold is *correctly* rejected. The route then densifies the anchors
alone — and Paradise has no YouTube ASR, so whisper-transcribe placed
only 12/65 sheet lines, clustered at line-ids 2–12 plus a lone 41.
`densify_cue_spans` linearly interpolates across the 29-line hole
(id 12→41), spreading whole sheet sections across a span they aren't
sung in; that interpolation ramp is why unrelated sections render
concurrently. Root cause is upstream — a sheet/audio version mismatch
(only 12/65 lines even transcribe-match). The warp gate did its job;
the damage is the fallback, which owns to **GATE S-3** (densify-fallback
branch) and **Appendix A routing**: version-mismatch songs should route
to the joint matcher or flag, not densify sparse clustered anchors.
*(Correction, later same day: Paradise's half of this reading is
superseded — the gate firing was anchor contamination, not a version
mismatch or tempo delta; Ken's ground truth + the offline refit are in
the S-A warp diagnostic entry below. The Defying Gravity half stands.)*

*Mode 2 — warp clean, overlap enters at the align stage (the other
seven).* Theil-Sen fit MAD ≤ 0.43 on all seven; the scaffold is
accepted and the warp cue_spans are monotonic and non-overlapping.
Verified on two, including the read-off's strongest counter-case:
Domino's warp cues place L29 "…tension" [1:31.15–1:34.70] then L30
"Now I'm breathin'" [1:34.70–1:38.48] in order, but the `.ass` pulls
L30 (a repeat — the same line also sits at L5) back to 1:29.82, swapped
before L29 and overrunning it; Be Our Guest's warp cues place L69 "Let
us help you…" [3:08.12–3:09.77] then L70 "Course by course…"
[3:09.77–3:11.42] in order, but the `.ass` pulls L70 back to 3:05.79,
before L69, fully containing it. In both the overlap is introduced by
`align_song`'s windowed whisper pass displacing a line several seconds
outside its (correct) cue window — the repeat-line displacement class
the SRT cue-align path already hardened against, re-exposed here because
warp cue windows are looser at repeats than tight SRT cues. Downstream
of a healthy warp; independent of the scaffold decision.

*What this settles for the read-off.* (1) The eyeball **confirms** the
NO-GO — genuine artifacts, not the metric mis-scoring a fine render.
(2) The acceptable-cause question the read-off left to Ken — whether
"overlap on lines the baseline never rendered" excuses some regressions
— does **not** apply to the seven Mode-2 songs: their overlaps are
same-line align displacements, not new-line artifacts (Be Our Guest,
+3.0 on an identical 77/77 set, is the proof), so that excuse is
unavailable for exactly the songs the read-off flagged it couldn't
cover. (3) The two modes are separately owned — Mode 1 → S-3 /
Appendix A, Mode 2 → an `align_song` repeat-displacement fix portable
from the cue-align path — and weighting the scaffold differently fixes
neither.

### 2026-07-19 — S-A warp diagnostic (Paradise) + Ken-ratified amendment: constant-offset rescue tier

Trigger: Ken supplied ground truth on NSYNC Paradise — he made the
video himself: the studio track prepended with live-concert dialog
footage, so the correct scaffold model is a *constant offset*, not a
tempo change. That contradicts the regression diagnosis above, whose
Mode-1 reading for Paradise ("fit slope 1.25 ≈ 25% tempo delta …
sheet/audio version mismatch; the warp gate did its job") is hereby
superseded; the Defying Gravity half of Mode 1 stands.

**Mechanism (offline reproduction, no GPU — Fable).** Paradise ran on
12 transcribe-only anchors (no YouTube ASR); 9 are common with the
51-line sidecar scaffold, and 3 of the 9 are mis-mapped onto repeated
lyric lines (residuals +46 s, +72 s, +72 s — chorus text matched to
the wrong occurrence). Theil-Sen draws slopes from point *pairs*, so
3-of-9 bad points contaminate 21 of 36 pairwise slopes (58%) — the
affine fit came out slope 1.248 / MAD 3.28 s, fired the 2.0 s gate,
and the 51-line scaffold was discarded for densify over the same 12
anchors (3 of them wrong): the actual source of the +4.6 s
regression. Fixing the slope at 1.0 and taking `offset =
median(anchor − scaffold)` gives +24.24 s with residual MAD 0.47 s —
the 6 clean anchors agree to under a second. The mis-mapped repeat
anchors themselves are the known upstream lyric-repeat lever, out of
scope; the offset tier contains their damage.

**All-16 sweep (same offline harness).** 14/16 songs fit affine with
slope 0.99–1.02 and MAD ≤ 0.45 s — the warp is not their problem, and
all seven Mode-2 regressions sit in this group (overlap enters at the
align stage; owned as recorded above — the S-B/S-2 comparison
measures whether the CTC arm removes it before any
repeat-displacement port is considered). The only other gate-firer is
Defying Gravity, where rejection is *correct*: slope 0.79 / MAD
5.80 s, and the offset-only model also fails (MAD 10.27 s) — a
structurally different recording. Discrimination is clean on exactly
this corpus. Residual-trimming the affine fit was considered and
**rejected**: it "rescues" Defying Gravity onto 5 cherry-picked
points (MAD 0.27 — would wrongly accept a bad scaffold) while leaving
Paradise below the 5-anchor floor (4 survivors).

**Ratified change (Ken, 2026-07-19).** `warp_scaffold_cues` gains a
constant-offset rescue tier, tried only when the affine path fails
(fit `None` or MAD > gate) and `len(common) ≥ WARP_MIN_ANCHORS`:
`offset = median(anchor_start − scaffold_start)` over the common
lines; accept iff `median(|residual|) ≤ WARP_MAD_GATE_S`; on accept,
proceed through the existing warp body with `slope = 1.0, intercept =
offset`; on reject, densify fallback unchanged. Both constants are
the locked existing ones — no new thresholds. Strictly additive: the
14 affine-clean songs cannot reach the new code path.

**Execution (Sonnet, sequenced before S-B):** implement + unit tests
(a Paradise-shaped contaminated-common case rescued; a
Defying-Gravity-shaped case still densifies; an affine-clean case
untouched), log which warp path each song takes, re-run S-A over all
17. Expected: Paradise is the only rescue; Defying Gravity stays
densify; any *other* song changing path = STOP → Ken. Output is the
raw table, never a verdict; the S-1 re-read happens on the best
scaffold arm after S-B runs.

### 2026-07-19 — Offset-rescue tier landed + S-A re-run on amended machinery, Sonnet 5 executor

Implemented the Ken-ratified constant-offset rescue tier
(`pikaraoke/lib/cue_align.py:warp_scaffold_cues`, commit `9b4229b`):
when the affine Theil-Sen fit misses `mad_gate` (or has no fit), a
fixed-slope offset model — `offset = median(anchor_start -
scaffold_start)` over the same common lines — is tried, accepted
under the identical `mad_gate`/`WARP_MIN_ANCHORS`; on reject, densify
fallback exactly as before. No new constants. Three unit tests added
(affine-clean unchanged, Paradise-shaped contaminated-common rescued,
DG-shaped both-models-fail still densifies) — 63/63 `test_cue_align.py`
green. Each call now logs its path (`affine-ok` / `offset-rescue` /
`densify-fallback` / `densify-fallback (no scaffold)` for the
pre-existing empty-scaffold branch, added for full per-song coverage).

Re-ran `scripts/scaffold_align_corpus.py` over all 17 genius-origin
songs on the amended machinery. Per-song warp path (run order):

| # | song | warp path |
|---|---|---|
| 1 | Defying Gravity | densify-fallback (MAD gate, both models fail) |
| 2 | Free | affine-ok (slope 0.9974) |
| 3 | Popular | affine-ok (slope 1.0074) |
| 4 | Be Our Guest | affine-ok (slope 1.0017) |
| 5 | Belle | affine-ok (slope 1.0009) |
| 6 | Best Part Of Me | affine-ok (slope 1.0002) |
| 7 | Bloodstream | affine-ok (slope 0.9939) |
| 8 | HUNTR/X | affine-ok (slope 1.0147) |
| 9 | Domino | affine-ok (slope 1.0124) |
| 10 | In Summer | affine-ok (slope 0.9975) |
| 11 | Man Out of You | affine-ok (slope 0.9881) |
| 12 | Paradise | **offset-rescue** (offset +24.241s) |
| 13 | Colors of the Wind | affine-ok (slope 0.9991) |
| 14 | Seasons of Love | affine-ok (slope 0.9542) |
| 15 | Hakuna Matata | affine-ok (slope 1.0078) |
| 16 | Next Ten Minutes | affine-ok (slope 1.0005) |
| 17 | Girl in the Bubble | densify-fallback (no scaffold found) |

Guards held exactly: Paradise is the only offset-rescue, Defying
Gravity is the only MAD-gate densify, no other song's path changed
from the pre-amendment run (Girl in the Bubble's "no scaffold" branch
is unchanged pre-existing behaviour, only newly logged). 14 affine-ok
+ 1 offset-rescue + 2 densify = 17, matching the warp diagnostic's
all-16-sweep count (14 clean + DG) plus Paradise now resolved and
Girl in the Bubble's separately-known no-sidecar case.

Full corpus metrics table (`plc`=placed, `hid`=hidden, `rea`=realigned,
`rep`=repaced, `rsec`=resectioned, `maxgap`/`gapL`/`instL`=artifact
counts, `anc`/`scf`=anchor/scaffold coverage, `ovl`=max inter-line
overlap old→new pipeline):

```
song                                        plc  hid  rea  rep rsec  maxgap gapL instL   anc   scf   ovl(old>new)
----------------------------------------------------------------------------------------------------------------
Jessie J - Domino (Official Video)---UJtB5   67    0    3   20    -    2.0s    0     1    14    61   1.3->4.6  s
Seasons of Love (HD)---UvyHuse6buY           34    0    0    7    -    1.9s    0     0    13    31   5.8->0.7  s
Ed Sheeran & Rudimental­ - Bloodstream [Of   74    0    0   46    -    1.7s    0    13    23    52   9.8->2.3  s
Ed Sheeran - Best Part Of Me (feat. YEBBA)   38    0    0    4    -    1.7s    0     0    16    33   1.1->0.0  s
Wicked - For Good  (2025) 4K - The Girl in   36    0    1   19    -    1.7s    0    17    23     0  31.1->3.2  s
Beauty and the Beast (1991) - Be Our Guest   77    0    2    5    -    1.7s    0     0    61    53   0.0->3.0  s
'Popular' - Wicked 20th Anniversary Editio   62    0    0   13    -    1.6s    0     1    44    39   2.9->1.7  s
'Defying Gravity' - Wicked 20th Anniversar   89    0    3   39    -    1.3s    0     2    43    61   8.4->4.3  s
Josh Gad - In Summer (From 'Frozen'_Sing-A   31    0    0    2    -    1.3s    0     0    24    18   1.4->1.2  s
The Next Ten Minutes Lyrics---0j8kL24ph8U    71    0    1    2    -    1.3s    0     0    63    66  13.4->0.5  s
Beauty and the Beast (1991) - Belle [UHD]-  110    0    1    5    -    1.1s    0     0    85    94   1.5->1.3  s
'Free' _ Official Lyric Video _ Sony Anima   41    0    0    0    -    1.1s    0     0    28    33   4.6->0.0  s
HUNTR_X 'This Is What It Sounds Like' (Mus   53    0    0   22    -    1.1s    0    11    15    43   5.5->0.5  s
Mulan _ I'll Make a Man Out of You _ @disn   47    0    0    7    -    1.0s    0     0    22    35   1.7->2.4  s
Pocahontas - Colors of the Wind (Blu-ray 1   37    0    0    2    -    0.9s    0     0    35    35   0.0->0.0  s
NSYNC - Paradise                             65    0    0    3    -    0.9s    0     1    12    51   6.1->0.4  s
The Lion King - Hakuna Matata Music Video    40    0    0    2    -    0.7s    0     0    19    25   0.0->2.8  s
```

Paradise: old_ovl→new_ovl 6.1s→0.4s, consistent with the diagnostic's
prediction that the rescue removes the densify-caused regression
(previously discarding the 51-line scaffold for 12 anchors, 3 of them
mis-mapped). No crashes; two per-line whisper `align_refine` errors
(pre-existing worker fallback path, "re-pacing from cue") on unrelated
lines, not warp-related. Output is the raw table, never a verdict —
the S-1 re-read happens on the best scaffold arm after S-B runs, per
the diagnostic's own sequencing.

### 2026-07-19 — Phase 3 S-B (CTC slice_align adapter + corpus run), Sonnet 5 executor

Built a CTC forced-align adapter behind the same `cue_align.align_song`
`slice_align` contract the whisper arm uses (`(t0, t1, text, label) ->
absolute-time words | None`), wrapping Phase 1's proven MMS_FA recipe
verbatim (chunked forward pass, `normalize_word` charset filter with
dual raw/normalized bookkeeping so an OOV word drops from the
tokenizer input but every surviving word keeps its real display text,
frame->seconds via the cached `ratio`) — the same recipe Phase 1b's
33/33-clean run and this plan's Phase 1 eyeball already validated, no
changes to the alignment math itself.

Adapter (`sb_ctc_adapter.py`) lives in the scratchpad only, per ground
rules. Emissions: **sliced from Phase 1b's cached full-song emissions**
(`scratchpad/emissions/<stem>.pt`, scratchpad-to-scratchpad reuse, all
17 corpus songs already cached from the 33-song Phase 1b run) rather
than a fresh per-slice GPU forward pass — one whole-song forward pass
per song, already on disk, sliced by frame index on every section/line
call. This made the corpus run essentially GPU-forward-pass-free
(seconds, not minutes).

Committed harness hook (commit `1d5a1a0`): `scaffold_align_song.run_song`
gained a `make_slice_align` parameter (default: the existing whisper
factory), and `scaffold_align_corpus.py` gained a generic
`--slice-align-module PATH` flag that dynamically loads a module's
`make_slice_align` — no scratchpad path or CTC-specific code committed,
the hook is aligner-agnostic. 63/63 `test_cue_align.py` unaffected (no
production code touched, only the two scaffold scripts); import-smoke
clean.

Ran the same 17-song corpus (`--slice-align-module
sb_ctc_adapter.py`), same metrics, same table format. Warp paths were
identical to the S-A re-run (warp is computed once from the anchors/
scaffold, independent of which forced-aligner slices the audio) —
confirms the two arms are being compared on the same cue-span
foundation, as intended.

Two songs threw a CTC-specific `RuntimeError` ("targets length is too
long for CTC") on one large multi-line section each: Bloodstream
(lines 36-73, 38 lines) and HUNTR/X (lines 33-52, 20 lines). Root-caused
before recording: in both cases the section's real time window is
degenerate (Bloodstream's is 245.65s-246.90s, ~1.25s, for 38 lines/283
words) because the underlying cue anchors themselves collapsed onto
nearly one timestamp — this is Bloodstream's already-flagged "2:58-end,
same overlap chants" desync region from Ken's Phase 1b labels, an
upstream anchor-data pathology, not an adapter defect. The existing
broad `except RuntimeError: return None` (mirroring
`_make_slice_align`'s own `except (RuntimeError, subprocess.
CalledProcessError)`) catches it exactly as designed, and
`align_song`'s cue-repace fallback takes over — both arms degrade
identically on these lines (S-A's whisper pass also repaces 46/74 and
22/53 lines on these same two songs). Not a STOP: the contract already
specifies "None on any aligner failure", and this is a new failure
*mode* under that same contract, not a new failure *case* requiring an
unspecified design choice.

**Chunk-seam validation (post-hoc, Ken's question):** reusing the
cached whole-song emission (chunked into independent, non-overlapping
20s forward passes per Phase 1b's recipe) instead of a fresh per-slice
forward pass is architecturally sound for CTC in a way it is not for
whisper — the acoustic-model step (`model(audio) -> emission`) takes
no text and is agnostic to how it will later be sliced, unlike
`stable_whisper`'s `align_refine`, which jointly aligns a given audio
window against given text and cannot be decoupled that way. The actual
alignment DP (`aligner(emission_slice, token_ids)`) still runs fresh
per `(t0, t1, text)` call; only the underlying per-frame log-probs are
reused. This is the same technique Phase 1b already ran (33/33 eyeball
clean) for word/line scoring and the S-shift rescue variant.

The one real risk this raises — a section boundary landing inside a
20s chunk seam, which a fresh un-chunked recompute wouldn't have — is
not hypothetical on this corpus: Bloodstream's "lines 6-11" section
(21.93s-40.20s) straddles the emission's chunk boundary at 40s.
Spot-checked directly: sliced-from-cache word timings vs. a fresh,
un-chunked forward pass over exactly that window agree to ≤20ms
(one frame) on 33/34 word boundaries, with the one exception (a word
ending exactly at the 40s seam) off by 100ms. Two orders of magnitude
under this pipeline's own timing tolerances (`PAUSE_SLACK_S`,
`DRIFT_GAP_S`, `MAX_WORD_DUR_S` are all ≥0.5s) — the reuse does not
threaten the table below. Script: scratchpad `chunk_seam_check.py`,
not committed.

Full corpus metrics table (same columns as the S-A table above):

```
song                                        plc  hid  rea  rep rsec  maxgap gapL instL   anc   scf   ovl(old>new)
----------------------------------------------------------------------------------------------------------------
Josh Gad - In Summer (From 'Frozen'_Sing-A   31    0    0    0    -    1.8s    0     0    24    18   1.4->0.0  s
'Defying Gravity' - Wicked 20th Anniversar   89    0    0    2    -    1.8s    0     0    43    61   8.4->2.6  s
Jessie J - Domino (Official Video)---UJtB5   67    0    0    1    -    1.4s    0     0    14    61   1.3->0.0  s
'Free' _ Official Lyric Video _ Sony Anima   41    0    0    0    -    1.4s    0     0    28    33   4.6->0.0  s
HUNTR_X 'This Is What It Sounds Like' (Mus   53    0    0   21    -    1.3s    0    11    15    43   5.5->0.5  s
'Popular' - Wicked 20th Anniversary Editio   62    0    0    1    -    1.3s    0     0    44    39   2.9->0.0  s
Ed Sheeran & Rudimental­ - Bloodstream [Of   74    0    0   38    -    1.3s    0    13    23    52   9.8->0.5  s
Wicked - For Good  (2025) 4K - The Girl in   36    0    0    1  yes    1.3s    0     1    23     0  31.1->0.0  s
The Next Ten Minutes Lyrics---0j8kL24ph8U    71    0    1    0    -    1.3s    0     0    63    66  13.4->0.0  s
Ed Sheeran - Best Part Of Me (feat. YEBBA)   38    0    0    0    -    1.3s    0     0    16    33   1.1->0.0  s
Beauty and the Beast (1991) - Belle [UHD]-  110    0    0    0    -    1.3s    0     0    85    94   1.5->0.0  s
NSYNC - Paradise                             65    0    0    2    -    1.2s    0     0    12    51   6.1->1.0  s
The Lion King - Hakuna Matata Music Video    40    0    0    1    -    1.2s    0     0    19    25   0.0->0.0  s
Seasons of Love (HD)---UvyHuse6buY           34    0    0    1    -    1.1s    0     0    13    31   5.8->0.0  s
Mulan _ I'll Make a Man Out of You _ @disn   47    0    0    3    -    1.1s    0     0    22    35   1.7->2.6  s
Beauty and the Beast (1991) - Be Our Guest   77    0    0    2    -    0.9s    0     0    61    53   0.0->0.3  s
Pocahontas - Colors of the Wind (Blu-ray 1   37    0    0    0    -    0.8s    0     0    35    35   0.0->0.0  s
```

prevalence: 3/17 songs show drift (vs the S-A re-run's 7/17); 0
parked-tail lines, 25 mostly-instant lines total. No crashes beyond
the two root-caused CTC RuntimeErrors above.

Output is the raw table, never a verdict — S-1 re-read and S-2 are
read-offs that happen after this entry, per the model-switching table
(Judge = Opus, escalations to Ken).

### 2026-07-19 — GATE S read-off (S-2, S-1 re-read, S-3) — CTC arm selected; S-1 hinges on two Ken rulings; densify fails S-3 on Defying Gravity

**(Fable executing the locked rules at Ken's direction, same convened
window; order S-2 → S-1 → S-3 per S-5's status note — the arm must be
picked before the route is re-read. Rules applied as locked, no
thresholds invented; Opus re-executing the arithmetic will reproduce
it. Both arms ran the identical warp foundation — the S-B entry
confirms per-song warp paths matched the S-A re-run exactly — so S-2
is a pure aligner comparison.)**

**S-2 — CTC (S-B) SELECTED.** Same-instrument head-to-head over the
16 in-scope songs (Girl in the Bubble excluded per the plan text,
`scf=0`; including it changes nothing — S-B is better there too,
3.2 → 0.0). Reading recorded for "mean re-pace": mean over songs of
the per-song re-paced fraction `rep/plc`; the verdict is unchanged
under the alternative total-lines reading (S-A 179/936 = 19.1 % vs
S-B 72/936 = 7.7 %).

- Mean re-pace: S-B 7.1 % vs S-A 17.5 % — **S-B better.**
- Mean worst-overlap: S-B 0.47 s vs S-A 1.61 s — **S-B better.**
- Flag count (drift signature, in-scope): S-B 2 (Bloodstream,
  HUNTR/X) vs S-A 6 (those plus Domino, Popular, Defying Gravity,
  Paradise) — **S-B better.**
- No song > 1.0 s worse on overlap: worst worsenings are Man Out of
  You +0.2 (2.4 → 2.6) and Paradise +0.6 (0.4 → 1.0), both ≤ 1.0 —
  **PASS.**

All three metrics strictly better plus the cap holds → the rule
selects CTC for the non-SRT scaffold path.

*Caution (added 2026-09-04 by the eyeball-provenance audit; see that
entry): two of the four criteria above are overlap-based, and the day
after this read-off Ken's S-C eyeball reframed what a falling overlap
number means. This entry has not been re-read against that reframe —
M6 does so. Do not treat the S-2 genius-arm selection as settled on the
strength of this entry alone.* (The SRT switch, S-C vs
the 5b baseline, has not run and stays open — separate decision,
extra caution per the rule.) Notable inside the comparison: CTC
removed six of the seven Mode-2 align-displacement overlaps outright
(Domino 4.6 → 0.0, Be Our Guest 3.0 → 0.3, Hakuna 2.8 → 0.0, Man Out
of You is the exception), confirming the S-B hypothesis that the
whisper repeat-displacement class dies with the aligner swap.

**S-1 re-read (S-B arm vs Phase 0 joint baseline)** — same
reconciliation as the `658d052` precedent: Phase 0 `overlap(rec>new)`
right value vs scaffold `ovl(old>new)` right value, per song, 16
in-scope songs.

- **Mean worst-overlap strictly lower: PASS.** S-B 0.47 s vs baseline
  0.54 s. The margin is real but thin (0.075 s) and driven by
  Bloodstream 6.7 → 0.5; recorded so no one mistakes it for a rout.
- **Rendered-line coverage no lower: PASS decisively.** Full sheet,
  zero hidden lines on all 16; strictly higher than baseline on 14,
  equal on 2 (Be Our Guest, Colors of the Wind).
- **Flagged-song count no higher: NOT MECHANICALLY DECIDABLE → Ken**
  (precedent followed: baseline `!` = coverage shortfall, 8 in-scope;
  S-B drift signature = 2; different failure modes, no cross-system
  mapping in the rule, and the read-off again declines to invent
  one). Unlike the precedent this conjunct is now load-bearing, so it
  needs Ken's ratification — noting that every defensible mapping
  passes (2 ≤ 8; totals including Girl in the Bubble, 3 ≤ 9; the
  scaffold structurally cannot exhibit the baseline's flag class
  since it renders everything).
- **No song regresses > 1.0 s without a recorded cause Ken accepts:
  FAIL as it stands — exactly two songs, both → Ken.** Defying
  Gravity 0.2 → 2.6 (+2.4): a recorded cause exists (warp diagnostic:
  structurally different recording, both warp models correctly
  rejected, MAD 5.80/10.27; the damage is the densify fallback — i.e.
  precisely the S-3 question below) but Ken has not formally accepted
  it. Man Out of You 0.0 → 2.6 (+2.6): **no recorded cause** — the
  S-A Mode-2 diagnosis (whisper repeat displacement) does not carry,
  because CTC removed the other six Mode-2 overlaps but not this one;
  the "overlap on lines the baseline never rendered" excuse is
  plausibly available (baseline rendered 36/47, S-B renders 47/47)
  but establishing it requires a diagnostic or Ken's eyeball, not
  this read-off.

**Verdict: mechanically not GO as it stands — but this is not the
S-A NO-GO.** Nothing fails on numbers where the rule is
self-contained; the conjunction hinges entirely on two open Ken
items: (1) cause-acceptance for Defying Gravity and Man Out of You,
(2) the flag-count mapping. If S-3 resolves to routing warp-failures
back to the joint matcher, Defying Gravity exits the scaffold route
in production and its regression becomes moot — the two rulings
interlock. Paradise, the original NO-GO's headline regression
(+4.6), is resolved by the offset rescue: S-A amended 0.7 → 0.4,
S-B 0.7 → 1.0, both inside the cap.

**S-3 (warp-failure branch) — densify FAILS the rule on Defying
Gravity's evidence.** Scope call recorded: "warp-failed" = the
MAD-gate reject only, i.e. **Defying Gravity alone** — Girl in the
Bubble never reaches the warp decision (no scaffold exists; densify
is the only possible path, no branch to rule on) and is excluded from
scaffold comparisons plan-wide. (For completeness: including it would
not change the outcome — its overlap ties 0.0 = 0.0 and naive flags
tie 1 = 1 → tie → densify, per the rule's tie-break.) On Defying
Gravity: densify overlap 2.6 s (best arm; 4.3 s on the whisper arm —
robust to arm choice) vs baseline 0.2 s → **not ≤** → the rule says
the warp-failure branch should *not* be densify; the alternative is
Appendix A routing (send warp-rejected songs back to the joint
matcher), consistent with the Mode-1 diagnosis already recorded. Left
open for Ken: the rule ignores the coverage trade (baseline renders
51/89 with its 0.2 s; densify renders 89/89 with 2.6 s) — accepting
joint routing means accepting the 38 dropped lines on such songs.

### 2026-07-19 — GATE S final rulings (Ken) — S-1 GO; S-3 = joint routing; wrapped-header artifact class; S-4 constants recorded

**Ken's rulings, closing everything the read-off left open:**

1. **Cause-acceptance (S-1 per-song cap): both accepted.** Defying
   Gravity's cause "is clear" (correctly-gated structural mismatch;
   the damage is the fallback — the S-3 question). Man Out of You:
   Ken's eyeball found it "actually fine" except a square-bracket
   line at ~2:10 and minor end-of-song wobble.
2. **Flag-count mapping: ratified** — Ken accepted the
   any-defensible-mapping reading (every reading passes, 2 ≤ 8; the
   conjunct's PASS rests on this ruling, not an invented threshold).
3. **S-3: joint-matcher routing for warp-rejected songs.** Ken keeps
   the joint route for DG-like songs — crammed interpolated dialog
   lines are unacceptable for karaoke; hiding unplaceable lines is
   the lesser harm. Direction for the production phase (recorded in
   the build plan): the joint route may adopt CTC as its aligner and
   be refactored to target exactly this warp-reject/version-mismatch
   class.

**⇒ S-1 = GO on the S-B arm** (all four conjuncts now pass). With
S-2 = CTC and S-5 = scaffold-first, GATE S is complete; F2's license
in the build plan is satisfied. F1 still awaits GATE R (2b unrun).
S-C (the SRT switch) never ran; the SRT path keeps whisper by the
rule's default.

**Man Out of You decomposition (Fable verification of Ken's
eyeball, S-B output confirmed by mtime):** the 2.6 s metric and the
2:10 artifact are different things. (a) The measured max overlap is
the *final-chorus* "Be a man" chant under "With all the strength of
a raging fire" (~3:33) — a genuine two-voice overlap on lines the
baseline never rendered (baseline 36/47, chants hidden; scaffold
47/47), the same class Ken ruled genuine at 5b. (b) The 2:10
artifact is sheet dirt: the stored genius-origin `.txt` wraps the
section header across two lines (`line[19]='[SHANG &'`,
`line[20]='SOLDIERS'`); `genius_lyrics.py`'s `_HEADER_RE` /
`_BRACKET_CONTENT_RE` both require the matched bracket pair on one
physical line, so the wrapped header survives as two "lyric" lines —
invisible on the joint route (unmatched → hidden), surfaced by the
render-everything scaffold route, contributing only ~1.0 s pairs
(not the 2.6 s driver). (c) End-of-song wobble = dense
call-and-response chant sequencing, nothing structural.

**Corpus scan of the artifact class:** 5/17 stored genius sheets
carry wrap dirt (15 lines). Rendering header fragments: Man Out of
You (`[SHANG &`/`SOLDIERS`) and Defying Gravity (`[CITIZENS OF OZ
&`/`ELPHABA`, confirmed rendering at 3:28 in its scaffold output).
Stray lone-paren wrap fragments (HUNTR/X, Paradise, Free, DG,
ManOut) do not survive to display text. **Disposition: fix-item,
not an eyeball veto** — production fix recorded in the build plan
(harden `parse_lyric_lines` for unterminated bracket lines;
preferred over refetching, which risks wholesale lyric-version
swaps on five songs).

**S-4 executed:** the S-constants are recorded in the build plan's
Appendix D — S-2 = CTC on the genius scaffold path / whisper stays
on SRT (S-C unrun), S-3 = joint routing (Appendix A precedence 3
resolves to route 4), snap re-enable exception = none (no named
flag class the snap fixes appears in the S-arm tables; the S-B
drift flags are degenerate-anchor artifacts). Appendix E's gate
band stays unfilled (engine off).

### 2026-09-04 — M6 pre-registration (RATIFIED by Ken, before either arm ran)

**(Executor. Ratified by Ken 2026-09-04 and committed before the probe was written. M6 was commissioned by the eyeball-provenance audit in
`plans/shared-aligner-form.md` with its read-off rules explicitly left
unwritten — `plans/route-word-timing.md` records M6 under "Not pre-registered
by this entry". This entry writes them, before the probe is written, following
the M1/M2 pattern Ken ratified: the criterion goes into version control while
the numbers do not exist. Nothing here changes a shipped route.)**

#### What M6 decides

Whether **S-2's selection of CTC for the genius-origin scaffold path stands**.
It is the one *unwitnessed selection* in the live ruling set, two of its four
criteria are overlap-based, and Ken's next-day S-C eyeball reframed what a
falling overlap number means. F2 builds on this path, so M6 gates F2.

Three outcomes are named now: **STANDS**, **FLIPS to whisper**, **NO AWARD →
Ken**.

#### Four pre-run findings that change the commissioned shape

Recorded before running, which is what a pre-registration is for.

1. **Per-line data from neither 2026-07-19 arm survives, so both arms must be
   re-run.** `scaffold_align_corpus.py` computes `max_line_overlap` on
   in-memory `line_objects` and prints the table; only the `.ass` is written.
   The `.ass` carries a render-time lead-in (a constant `{\k80}` = 0.80 s
   first chunk on every Dialogue) plus a variable tail hold, so the metric is
   not recoverable from it — computing max-overlap directly on the survivors'
   Dialogue spans reproduces neither recorded table (Be Our Guest 1.31 s
   against S-A 3.00 and S-B 0.30; 0 of 17 songs land within 0.15 s of either).
   The commissioning assumed only the whisper arm needed re-rendering. Both
   supporting measurements it asks for are per-line, so both arms are needed.
   *Artifact: `m6/arm_id.py`.*

2. **The survivor's arm is identified by circumstance, not by content.** The
   17 `karaoke/*.scaffold.ass` are stamped 2026-07-19 18:18-18:19, four
   minutes after commit `1d5a1a0` landed the `--slice-align-module` hook that
   makes a CTC arm possible at all, and all 17 wrote inside about 90 s — too
   fast for whisper's per-slice `align_refine`, consistent with CTC slicing
   cached emissions. That points at S-B but does not prove it. **Verified, not
   assumed:** arm C re-runs one song first and its `.ass` is diffed against the
   preserved survivor. All 17 survivors are already copied to
   `m6/survivor_2026-07-19/`; the runs clobber `karaoke/*.scaffold.ass`.

3. **No uploader SRT exists anywhere on this corpus, by construction.** The
   harness selects songs whose `lyrics.source_kind != "srt"`; all 18
   candidates report `youtube_srt_present = False`, and every `.srt` on disk
   has a `.srt.generated` sibling marking it as PiKaraoke's own output. So the
   "computable maximum authored simultaneity" that
   `plans/completed/matcher-accuracy-hardening.md` establishes — the reference
   the audit cites as the one the overlap metric ignores — **is not available
   on this corpus**. Nothing independent of the two arms can say whether a
   given overlap is a real two-voice passage. That is why Ken's eyeball is the
   arbiter here and not a tiebreak.

4. **The corpus has drifted: 18 genius-origin songs today against 17 on
   2026-07-19** ("Stay Gold (Official Music Video) from The Outsiders" is
   new). M6 runs **the recorded 17 and excludes Stay Gold**, so the recomputed
   means stay comparable with the S-A/S-B tables. Girl in the Bubble stays out
   of the in-scope statistics exactly as S-2 had it (`scf=0`): rendered and
   reported, not counted.

#### What gets run

Two arms over the same 17 songs, one machine, one code state
(`joint_catchall_refit` at the ratifying commit), identical
`--timing sidecar --pad 0.75`:

- **Arm W (whisper)** — default backend, the S-A instrument.
- **Arm C (CTC)** — `--slice-align-module scripts/sb_ctc_adapter.py`, the S-B
  instrument. 7 of the 17 emissions are cached; 10 are fresh whole-song
  forward passes.

One harness change, the smallest that makes the commissioned measurements
computable: a `--dump-json` flag on `scaffold_align_corpus.py` writing each
song's `line_objects` alongside the `.ass`. No change to the alignment path.
Each arm's `.ass` renders are archived per-arm before the other arm runs.

#### The measurements, fixed now

- **M6-a — same-location overlap.** For every adjacent pair
  `(prev_id, cur_id)` occurring in both arms' time-sorted placed lines, report
  `ovl_W` and `ovl_C`. Per song: each arm's worst overlap *and its location*,
  the other arm's overlap **at that same location**, and whether the two worst
  locations coincide. This is the comparison S-2 never made — its deltas are
  per-song maxes across two runs.
- **M6-b — worst-pair movement.** Per song,
  `moved = worst_pair_W != worst_pair_C`, reported as a raw count over the
  in-scope 16. No threshold.
- **M6-c — the clipping decomposition (the discriminator).** At each shared
  location the difference decomposes exactly:
  `ovl_W - ovl_C = (end_W(prev) - end_C(prev)) - (start_W(cur) - start_C(cur))`.
  Every CTC overlap win is therefore attributable to **earlier line ends** —
  the clipping signature the audit predicts — or to **later next-line starts**,
  a genuine placement fix. Both components reported per location. No
  threshold, no verdict.
- **M6-d — Ken's eyeball, the arbiter.** Be Our Guest and Hakuna Matata, both
  arms, same clips — the two ensemble songs carrying the largest overlap
  "wins" (3.0 -> 0.3 and 2.8 -> 0.0). The question is fixed now so that no
  render can select it afterwards: *at the location of the whisper arm's worst
  overlap, does the CTC render (i) time both voices correctly, (ii) drop or
  clip the second voice, or (iii) neither — whisper is simply wrong there and
  CTC is right for an unrelated reason?* Plus a free judgment on which render
  he would rather sing to.

#### Read-off rule

- **STANDS** if Ken returns (i) or (iii) on **both** songs — CTC's showcase
  overlap wins are not clipping, and the two overlap-based criteria S-2 leaned
  on were reading what they claimed to read.
- **FLIPS to whisper** if Ken returns (ii) on **both** songs — the two showcase
  wins are under-reporting, and the criteria that produced the selection
  rewarded exactly the artifact the S-C reframe named.
- **Split (one (ii), one not) → NO AWARD → Ken.** Not resolved by the
  supporting measurements.
- **M6-a/b/c cannot flip or confirm the selection on their own.** They are
  evidence for Ken's reading, never a tiebreak that overrides it. Stated
  explicitly so a large M6-c number is not later read as a verdict — the whole
  reason M6 exists is that a metric was read as a verdict once already.

#### Reproduction check — declared, and it can suspend the read-off

Arm C's per-song `ovl` is compared against the recorded S-B table, arm W's
against the recorded S-A re-run table. Non-reproduction is **reported as
found**. If arm C does not reproduce S-B within 0.2 s on the two eyeball
songs, **the M6 read-off is suspended and goes to Ken**: what is being re-read
would then not be what was recorded, and no eyeball on a different render can
settle a claim about the recorded one.

#### One-shot

No adjust-and-re-run. If a song crashes it is reported as failed and excluded,
not retried with different settings. The robustness columns declared now — all
16 in-scope per-song tables, the recomputed mean worst-overlap per arm, the
reproduction deltas — are robustness only and can never become primary.

#### Not pre-registered by this entry

Any change to the aligner, `cue_align`, snap policy, or the F2 build; GATE
J1/J2's separate CTC-in-the-joint-matcher question; the S-C vs 5b SRT switch,
which stays open; S-E and GATE L.

### 2026-09-04 — M6 run — both arms, raw tables, no read-off beyond the pre-registered ones

**(Executor. The pre-registration above was ratified and committed (`6d9cdcc`)
before the probe was written, so every rule applied below was fixed in version
control while the numbers did not exist. The read-off itself is M6-d and is
Ken's: nothing here decides whether S-2's genius arm stands. One probe defect
found and corrected mid-analysis is disclosed in full below.)**

**Artifacts** — session scratchpad `m6/`: `prereg.md`, `arm_id.py`,
`m6_probe.py`, `m6_results.txt`, `m6_rows.json`, `armW_run.log`,
`armC_run.log`, per-line dumps `armW/`, `armC/`, renders `renders_W/`,
`renders_C/`, the 2026-07-19 originals `survivor_2026-07-19/`, the frozen
cohort `debug17/`, and the two eyeball songs staged in `eyeball/`.

Both arms ran on the Windows box against the frozen 17-bundle cohort, same
code state, `--timing sidecar --pad 0.75`. Arm C took about 4 minutes for all
17 songs (one whole-song forward pass each, sliced by frame index); arm W took
about 2.4 minutes *per song* (451+ sequential `align_refine` calls on ~3 s
windows). Recorded as context; the pre-registration makes speed no part of any
criterion.

#### Reproduction check — both arms reproduce, decisively

The pre-registered suspension clause (arm C within 0.2 s of S-B on the two
eyeball songs) does not fire. Every one of the 17 `ovl` values reproduces in
both arms, and so do `plc`/`hid`/`rea`/`anc`/`scf`/`maxgap` and the corpus
lines `prevalence: 3/17` (arm C) and `7/17` (arm W).

```
song                               W     S-A       d |       C     S-B       d
Defying Gravity                 4.26    4.30   -0.04 |    2.61    2.60   +0.01
Free                            0.00    0.00   +0.00 |    0.00    0.00   +0.00
Popular                         1.72    1.70   +0.02 |    0.00    0.00   +0.00
Be Our Guest                    2.96    3.00   -0.04 |    0.31    0.30   +0.01
Belle                           1.27    1.30   -0.03 |    0.00    0.00   +0.00
Best Part Of Me                 0.00    0.00   +0.00 |    0.00    0.00   +0.00
Bloodstream                     2.25    2.30   -0.05 |    0.50    0.50   +0.00
This Is What It Sounds Like     0.50    0.50   +0.00 |    0.50    0.50   +0.00
Domino                          4.58    4.60   -0.02 |    0.00    0.00   +0.00
In Summer                       1.17    1.20   -0.03 |    0.00    0.00   +0.00
Man Out of You                  2.43    2.40   +0.03 |    2.64    2.60   +0.04
Paradise                        0.38    0.40   -0.03 |    1.03    1.00   +0.03
Colors of the Wind              0.00    0.00   +0.00 |    0.00    0.00   +0.00
Seasons of Love                 0.75    0.70   +0.05 |    0.00    0.00   +0.00
Hakuna Matata                   2.82    2.80   +0.02 |    0.00    0.00   +0.00
Next Ten Minutes                0.50    0.50   +0.00 |    0.00    0.00   +0.00
Girl in the Bubble              3.16    3.20   -0.04 |    0.00    0.00   +0.00
```

Every delta is within rounding of the recorded one-decimal tables. Two arm-C
songs differ by one in the re-paced count only (Popular and Seasons of Love,
`rep` 1 → 0), which moves no overlap. Arm C's two "targets length is too long
for CTC" warnings are the two root-caused failures the S-B entry already
records. This also settles the arm-identity question raised in the
pre-registration's finding 2: the surviving `.scaffold.ass` are the CTC arm,
and that arm reproduces seven weeks later on a different machine.

#### Probe defect found and corrected mid-analysis — disclosed

The first run of `m6_probe.py` evaluated "the other arm's overlap at that same
location" by applying the *first* arm's `(prev, cur)` order to the second arm's
spans. Where the two arms place the same two lines in **opposite time order**,
that computes `end(later) - start(earlier)` — the pair's total span, not an
overlap — and reads as a large false positive. It produced C@locW values of
7.71 s on Domino, 3.22 s on Hakuna Matata and 14.84 s on Girl in the Bubble,
which would have read as "CTC overlaps *more* at the location it claims to
have fixed".

Caught by hand-checking the Hakuna Matata spans before reporting, not by the
probe. The fix re-derives the ordering inside each arm — `ovl_at` now sorts the
pair by start time, reproducing exactly what `max_line_overlap` would report
for that pair within that arm. Corrected values follow. M6-c was **not**
affected: it iterates the shared-*adjacency* set, and a shared adjacency has
the same order in both arms by construction. The probe's `worst()` was
self-tested against the harness's own `max_line_overlap` on 17/17 arm-C songs
before either table was produced.

#### M6-a / M6-b — same-location worst overlaps and worst-pair movement

`loc` is a `(prev, cur)` line-id pair. `C@locW` is arm C's overlap at arm W's
worst location and vice versa. `flip` marks the pairs the two arms place in
opposite order — descriptive, not commissioned, and reported because `C@locW`
cannot be read without it.

```
song                            ovl_W loc_W         C@locW flip |    ovl_C loc_C         W@locC  moved
Defying Gravity                  4.26 (78, 85)       -6.99   no |     2.61 (86, 82)        2.90  yes
Free                             0.00 None           n/a      - |     0.00 None           n/a    no
Popular                          1.72 (51, 53)       -0.50   no |     0.00 None           n/a    yes
Be Our Guest                     2.96 (70, 69)        0.00  yes |     0.31 (59, 60)        0.00  yes
Belle                            1.27 (3, 4)          0.00   no |     0.00 None           n/a    yes
Best Part Of Me                  0.00 None           n/a      - |     0.00 None           n/a    no
Bloodstream                      2.25 (26, 27)       -0.12   no |     0.50 (37, 38)        0.50  yes
This Is What It Sounds Like      0.50 (48, 49)        0.50   no |     0.50 (48, 49)        0.50  no
Domino                           4.58 (30, 29)       -0.04  yes |     0.00 None           n/a    yes
In Summer                        1.17 (4, 5)          0.00   no |     0.00 None           n/a    yes
Man Out of You                   2.43 (18, 19)        0.00   no |     2.64 (45, 44)        0.00  yes
Paradise                         0.38 (26, 27)       -0.12   no |     1.03 (20, 21)        0.00  yes
Colors of the Wind               0.00 None           n/a      - |     0.00 None           n/a    no
Seasons of Love                  0.75 (30, 31)       -0.22   no |     0.00 None           n/a    yes
Hakuna Matata                    2.82 (31, 30)       -0.12  yes |     0.00 None           n/a    yes
Next Ten Minutes                 0.50 (50, 51)       -0.72   no |     0.00 None           n/a    yes
Girl in the Bubble               3.16 (30, 13)      -13.21  yes |     0.00 None           n/a    yes
```

```
worst pair moved                 : 12 / 16 in-scope songs
mean worst-overlap (in-scope)    : W 1.599 s   C 0.475 s
```

The mean pair is the recomputation of S-2's second criterion on this run
(S-2 recorded S-B 0.47 s vs S-A 1.61 s). It is a declared robustness column,
not a criterion.

#### M6-c — clipping decomposition

Over every shared adjacency where arm C reduces a real arm-W overlap:
`ovl_W - ovl_C = (end_W(prev) - end_C(prev)) - (start_W(cur) - start_C(cur))`.
`from_end` positive means CTC ends the previous line **earlier** — the
clipping signature the audit predicted. `from_start` positive means CTC starts
the next line **later**.

```
song                           wins  sum_dovl  from_end from_start end_share
Defying Gravity                  13      6.96     -2.57      9.53      -37%
Free                              0      0.00      0.00      0.00         -
Popular                           6      3.56     -3.94      7.50     -111%
Be Our Guest                      2      1.11      0.01      1.09        1%
Belle                             2      1.88      1.12      0.75       60%
Best Part Of Me                   0      0.00      0.00      0.00         -
Bloodstream                       1      2.37     -0.40      2.77      -17%
This Is What It Sounds Like       1      0.19     -1.14      1.33     -597%
Domino                            4      2.32     -2.52      4.85     -109%
In Summer                         1      1.17      0.29      0.88       25%
Man Out of You                    4      5.12      2.34      2.77       46%
Paradise                          1      0.50      1.53     -1.04      309%
Colors of the Wind                0      0.00      0.00      0.00         -
Seasons of Love                   2      1.49     -1.28      2.77      -86%
Hakuna Matata                     0      0.00      0.00      0.00         -
Next Ten Minutes                  2      1.57     -4.04      5.62     -257%
Girl in the Bubble                7      0.83    -39.94     40.76    -4831%
```

```
in-scope total: from earlier ends -10.59 s, from later next-starts 38.83 s
share of CTC's overlap reduction attributable to earlier ends: -37%
```

Girl in the Bubble is out of scope (S-2's exclusion, `scf=0`) and is excluded
from the totals; it is printed because it was rendered. Reported as computed
and not interpreted here: the in-scope `from_end` total is negative, and
Hakuna Matata contributes zero rows because arm C reduces no shared-adjacency
overlap on it.

#### The two eyeball locations, both arms

Arm W's worst-overlap location on each of the two showcase songs, with the
neighbouring lines and the `source` field of each.

```
Be Our Guest  — whisper worst overlap 2.96 s at lines (70, 69)
 arm W   line 68  3:06.25 -> 3:07.90  cue_align_fill  While the candlelight's still glowing
         line 70  3:06.60 -> 3:10.86  cue_align       Course by course, one by one
         line 69  3:07.90 -> 3:09.55  cue_align_fill  Let us help you, we'll keep going
         line 71  3:10.86 -> 3:14.08  cue_align       'Til you shout, "Enough, I'm done"
 arm C   line 68  3:05.74 -> 3:07.96  cue_align       While the candlelight's still glowing
         line 69  3:07.96 -> 3:09.14  cue_align       Let us help you, we'll keep going
         line 70  3:09.14 -> 3:10.82  cue_align       Course by course, one by one
         line 71  3:10.98 -> 3:14.23  cue_align       'Til you shout, "Enough, I'm done"

Hakuna Matata — whisper worst overlap 2.82 s at lines (31, 30)
 arm W   line 29  2:41.90 -> 2:43.28  cue_align       Hakuna matata, hakuna matata
         line 31  2:42.60 -> 2:46.10  cue_align_fill  It means no worries for the rest of your day
         line 30  2:43.28 -> 2:45.44  cue_align       Hakuna matata, haku...
         line 32  2:48.18 -> 2:49.00  cue_align       It's our problem-free philosophy
 arm C   line 29  2:41.88 -> 2:43.92  cue_align       Hakuna matata, hakuna matata
         line 30  2:43.94 -> 2:44.64  cue_align       Hakuna matata, haku...
         line 31  2:44.76 -> 2:47.17  cue_align       It means no worries for the rest of your day
         line 32  2:48.18 -> 2:48.94  cue_align       It's our problem-free philosophy
```

#### Not commissioned by the pre-registration — flagged

- **Arm W logged 117 `AttributeError: 'NoneType' object has no attribute
  'language'` failures inside `whisper_worker._do_align_refine`**, each falling
  back to the "re-pacing from cue" path, plus one `RuntimeError` on a padding
  size. Zero songs failed outright. The S-A entry recorded "two per-line
  whisper `align_refine` errors" for the original run; the per-song `rep`
  counts reproduce exactly, so the fallback was equally active then and the
  original entry under-reported it. Recorded because it bears on how arm W's
  spans should be read: a `cue_align_fill` line's timing is not whisper's
  alignment, it is the cue re-paced.
- **At both eyeball locations, arm W's overlap involves a `cue_align_fill`
  line and arm C's four lines are all `cue_align`.** Stated as a fact about
  the two renders, not as an interpretation of what either sounds like.

#### What is Ken's

M6-d. Watch both arms on Be Our Guest from 3:02 and Hakuna Matata from 2:38
and answer the pre-registered question: at the location of the whisper arm's
worst overlap, does the CTC render (i) time both voices correctly, (ii) drop
or clip the second voice, or (iii) neither — whisper is simply wrong there and
CTC is right for an unrelated reason? Both (i)/(iii) → S-2 stands; both (ii) →
S-2 flips; split → no award. The tables above are evidence for that reading
and, per the ratified rule, cannot flip or confirm the selection on their own.

No further probe is commissioned by this entry, and nothing here touches a
shipped route.

### 2026-09-04 — M6-d eyeball (Ken) — observations recorded, no ruling taken

**(Executor recording Ken's viewing as data. The pre-registered pair is Be Our
Guest and Hakuna Matata; the three follow-up songs were selected by criteria
stated to Ken in-session **before** he watched but not committed to version
control first — recorded here as the weaker provenance it is. No verdict on
S-2 is taken in this entry.)**

#### The pre-registered pair — neither can answer the question as posed

- **Be Our Guest.** Both arms overlap at the location. Whisper sweeps "Course
  by course, one by one" properly; the collision is prior lines that "didn't
  place". Scrolling further back, Ken reads whisper as handling the massive
  overlaps *better* than CTC, though both are "fairly chaotic".
- **Hakuna Matata.** The location is a **spoken dialogue section absent from
  the lyric sheet**, so both arms are placing lyric lines onto non-lyric audio.
  The pre-registered question — does CTC drop or clip a second voice — cannot
  be asked there at all. This is a finding about the corpus, not a null result.

The pre-registered read-off is therefore **not answerable on its own pair**.

#### Why, structurally — overlap never arises between two aligned lines

Source of every line in every overlapping adjacent pair, both arms, all 17
songs:

```
arm W: 142 pairs with positive overlap    arm C: 62 pairs
   fill + fill            82                 fill + fill            56
   cue_align + fill       46                 cue_align + fill        6
   cue_align + realign     9                 cue_align + cue_align   0
   fill + realign          5
   cue_align + cue_align   0
```

**Zero overlaps in either arm arise between two normally-aligned lines.** Every
one involves a line the aligner failed on, which then fell back to re-pacing
from the cue (`cue_align_fill`) or to re-alignment (`cue_align_line`). Overlap arises
*only* at fallback lines; **magnitude does not track fallback count** (arm C:
Bloodstream 38 fallbacks -> 0.50 s, Man Out of You 3 -> 2.64 s). Corrected
2026-09-04 by the S-1 re-read below, which withdrew a stronger ranking claim. On this corpus
`cue_align_song.max_line_overlap` tracks **fallback prevalence**, not
simultaneity. Recorded as measured; what it implies for S-2's two overlap-based
criteria is Ken's.

#### The three follow-up songs

Selection criteria, stated before viewing: a control with zero fallback lines
in both arms (Free); the song where the arms differ most (Defying Gravity, 42
whisper fallbacks against 2); the song where the metric says CTC is *worse*
(Man Out of You, 2.43 → 2.64).

- **Free (control).** Both arms struggle on the long-note phrases from 2:00.
  Whisper **drops the second half of lines**; CTC **comes in correctly but
  rushes the sweep significantly**. The control does discriminate — and it
  isolates a difference S-2 never measured, since neither arm has a single
  fallback line here.
- **Defying Gravity.** CTC opens with a dump of the sheet's dialogue and keeps
  doing so through the song, usually resyncing quickly. That is what is
  happening at the trouble spot. Whisper's trouble spot is the same dialogue.
  Timing where each gets it right is "roughly similar".
- **Man Out of You.** The trouble spot is a square-bracket attribution that
  survived parsing, present in both arms. "Roughly similar."

#### Two of the three trouble spots are a known unfixed artifact, not an aligner difference

Confirmed against the stored sheets:

```
Man Out of You   sheet line 18  'Now I really wish that I knew how to swim!'
                 sheet line 19  '[SHANG &'          <- whisper worst overlap is (18, 19)
                 sheet line 20  'SOLDIERS'
Defying Gravity  sheet line 81  'Get her!'
                 sheet line 82  '[CITIZENS OF OZ &' <- CTC worst overlap is (86, 82)
                 sheet line 83  'ELPHABA'
```

Both fragments reach both arms' rendered `.ass`. **So neither of those two
comparisons was testing the aligners** — both arms were handed a non-lyric line
and both placed it somewhere.

**Why the existing mechanism misses them.** `genius_lyrics.parse_lyric_lines`
has two bracket defences and **both require a closing `]`**:
`_HEADER_RE = ^\s*\[[^\]]*\]\s*$` drops a line that is entirely a *closed*
bracket, and `_BRACKET_CONTENT_RE = \[[^\]]*\]` strips *closed* bracket spans
inline. Genius wraps long attributions across two lines, so `[SHANG &` is
unterminated: it matches neither pattern, `_HAS_LETTER_RE` then sees "SHANG",
and the line is kept as a lyric.

This is not new. The 2026-07-19 GATE S corpus scan in this file already
recorded it — "5/17 stored genius sheets carry wrap dirt (15 lines)",
explicitly naming Man Out of You (`[SHANG &`/`SOLDIERS`) and Defying Gravity
(`[CITIZENS OF OZ &`/`ELPHABA`, "confirmed rendering at 3:28 in its scaffold
output"). CTC's worst overlap in this run is at **3:28.56**. It was
dispositioned then as a fix-item rather than an eyeball veto and **has not been
built**. It remains open.

The other class Ken saw on Defying Gravity is different and has no mechanism:
**spoken dialogue present in the Genius sheet as ordinary un-bracketed text**.
Nothing textual distinguishes it from lyrics, and no filter was ever specified
for it.

#### Ken's forming read, recorded as not yet a ruling

"I am beginning to question whether CTC adds anything helpful other than
tighter word timing, which edge snap helps eliminate the most obvious negatives
of anyways." Recorded verbatim. It is not entered as the M6 read-off. Note it
touches GATE J2, which owns whether edge snap retires on CTC-timed routes — if
edge snap is what neutralizes whisper's loose endings, then J2's question and
M6's are coupled in a way neither entry currently states.

### 2026-09-04 — S-1 re-read after M6 (Fable judge round) — GO stands as a ruling, not as a finding; F2's license suspended pending Ken

**(Judge round at Ken's escalation, read-only; nothing was written to the repo
by the judge. Verdict doc saved verbatim: scratchpad `m6/m6_s1_readoff.md`.
The executor spot-verified the two load-bearing new claims — the cram and the
clean-subset clipping sign — and both reproduce exactly. Three items below are
Ken's and are open.)**

#### The read-off

**S-1's GO stands as a ruling and no longer stands as a finding.** Nothing in
M6 shows the scaffold route is *worse* than the joint route — the two arms were
never compared against the joint render. What M6 removes is the evidence that
it is *better*. Both metric conjuncts are scored, by construction, by each
route's own fallback class (fills here, hidden lines there), and both of the
conjuncts Ken ruled lean on the same property. **F2's license (S-1 GO + S-5) is
suspended pending re-derivation, not revoked.**

#### The finding that carries it — the cram is on warp-*accepted* songs

```
Bloodstream  lines 36-73 : n=38  span 246.40 -> 246.90 s  (0.50 s total)
HUNTR/X      lines 33-52 : n=20  span 159.76 -> 160.26 s  (0.50 s total)
             every line exactly 0.50 s; all cue_align_fill; both arms
```

`_repace_line`'s `t1 = t0 + 0.5` floor. Both songs take the **affine-ok** warp
path — this is not the MAD-gate reject class S-3 was scoped to. The overlap
metric reads 0.5 s *because every line is 0.5 s long*, so the corpus's
"best-improved" song is one where the back half is unreadable.

Every other non-zero arm-C overlap is also a fallback artifact: Defying
Gravity's 2.61 is the `[CITIZENS OF OZ &` fragment (drop lines 82-83 and it is
0.00); Paradise's 1.03 is line 21, text `e`, a Genius wrap of "lik|e" (drop it
and it is 0.00); Man Out of You's 2.64 is an aligned line over a "Be a man"
chant that is itself a fill; Be Our Guest's 0.31 is align-over-fill.

#### Conjunct by conjunct

- **Mean worst-overlap strictly lower — disturbed.** The arithmetic passes and
  reproduces, but the pass is carried entirely by Bloodstream, i.e. by the cram
  above. Excluding that song the conjunct fails by 3.5x. This is PROGRAM.md's
  "the pre-registered rule does not cover the case observed": it passes as a
  read-off and does not as evidence, and which governs is **STOP -> Ken**.
- **Rendered-line coverage no lower — intact as arithmetic, ill-posed as a
  criterion.** It scores two *contracts* against each other and counts dirt and
  lyrics alike on both sides. The scaffold cannot lose it (`hid = 0` by
  construction) and the joint route cannot win it. A criterion one side wins by
  construction restates which contract was chosen; it does not measure
  improvement. The version that could discriminate — "the extra rendered lines
  are sung lyrics, placed where they are sung" — needs a reference this corpus
  lacks and neither route computes.
- **Flag count — Ken's ruling, and M6 bears on its argument.** The numbers
  reproduce. The ratified reading rested on "the scaffold structurally cannot
  exhibit the baseline's flag class since it renders everything", which is the
  coverage property again. Note the two S-B drift flags **are** the two cram
  songs: the flag sees the cram, and the mapping is what treats two crams as
  better than eight coverage shortfalls.
- **Per-song cap — Ken's rulings; one moot, one imprecise.** Defying Gravity's
  accepted cause is right about the cue window but the number is specifically
  the bracket fragment; moot in production, since S-3 routes that song to the
  joint matcher. Man Out of You was accepted with the bracket line in view, so
  M6 adds no new artifact — it adds that the number is an align-over-fill pair,
  the same class as every other overlap in the corpus.

#### Corrections to the record

- **The joint route's suppression is incidental, not a lyrics test.** The
  contract that hides the two bracket fragments also hid **9 real "Be a man"
  chants** on Man Out of You and **36 non-fragment lines** on Defying Gravity
  (the opening exchange, "I hope you're happy" x8, "Glinda, come with me").
  The M6-d entry above states only the half that suppressed dirt.
- **The clipping decomposition must not be read as refuting the audit.** M6-c's
  aggregate is a population artifact: 29 of 39 win-locations have a fill as the
  whisper-side previous line. On the 10 locations where the previous line is
  cleanly aligned in *both* arms, the end delta is **+6.32 s** — the audit's
  predicted sign. Equally consistent with whisper over-holding; the verdict is
  M6-d's, not this entry's.
- **The overlap/fallback relation is a necessary condition, not a ranking.**
  Corrected in the M6-d entry above: overlap arises *only* at fallback lines,
  but magnitude does not track fallback count.
- **Arm W's 118 `align_refine` exceptions are not a defect in the arm** —
  documented stable_whisper behaviour when `remove_instant_words=True` and
  alignment fails. 106 of 118 are the ~3 s per-line rescue window. Arm W
  reproduces S-A exactly, so this held on Linux in July. No re-run owed.
- **The judge withdraws its own 2026-07-19 characterisation** of Man Out of
  You's 2.6 s as "a genuine two-voice overlap": the second line is a fill.
  Ken's ear may still be right about the audio; the metric was not measuring it.
- The wrap-dirt class is **wider than the recorded fix-item**. Beyond the two
  unterminated brackets, Paradise carries `I` and `e` as sheet lines (wraps of
  "Between you and I (" and "lik|e"), and `e` is the whole of CTC's Paradise
  overlap. The fix-item as written covers unterminated brackets only, so it
  would miss those and the plain-text second halves `SOLDIERS` / `ELPHABA`.

#### What is Ken's — three open items

1. **Re-affirm or withdraw S-1**, knowing the GO cannot be re-derived from the
   S-1 rule on this evidence.
2. **Whether the S-3 principle extends past its scope.** The *phenomenon*
   extends — the cram appears on warp-accepted songs, from a degenerate section
   window rather than densify. Applying the principle there is a new ruling,
   and it is **prior to the aligner question**, because both arms produce the
   identical cram.
3. ~~**Whether the parser fix sits inside or outside measure-first.**~~
   **CLOSED 2026-09-08 — Ken ruled it inside; built, see the entry at the
   end of this file.** It is
   production code in `genius_lyrics.py`, route-independent, a bug fix — but
   "no remaining probe needs production code" was measure-first's license.
   Harden-vs-refetch was already ruled; only scope and timing are open.

#### The minimum for F2 to stay licensed, and the sequencing that follows

What would have to be true: on the songs F2 would actually take — genius
origin, line source, warp-accepted — the scaffold render is at least as
singable as the joint render on the lines both render, and the lines only the
scaffold renders are sung lyrics, not fragments, dialogue or crams.

**No witnessed scaffold-vs-joint comparison on a warp-accepted song exists.**
The nine-regression eyeball was the whisper arm; the Man Out of You acceptance
was the S-B render alone; M6-d was whisper vs CTC. Production `.ass` and
`armC.ass` exist for all 17 songs, so the missing evidence is **an eyeball, not
a GPU run**: joint vs arm C, pre-registered, on the warp-accepted songs the
dirt scan clears — Free, Colors of the Wind, Best Part of Me, Belle, In Summer,
Seasons of Love, Next Ten Minutes, Popular, Domino, Be Our Guest. **Not**
Hakuna Matata (off-sheet dialogue). Bloodstream and HUNTR/X are shown
separately as the cram item.

Order: **parser fix -> one pre-registered eyeball -> Ken rules S-1 and the S-3
extension -> M6-d re-posed if the route survives -> F2.**

**M6-d stays open and is sequenced after this.** Its commissioned pair cannot
answer its own question, and it is moot if the license falls. Two facts for a
re-pose: 106 of arm W's 118 fallbacks are the per-line rescue failing on a ~3 s
window, and M6-c's clean-subset sign is +6.32 s.

### 2026-09-08 — Lyric-parser wrap fix (Ken ruled it inside measure-first; S-1 item 3 CLOSED)

**(Ken's ruling on open item 3 of the S-1 re-read: "proceed with the fix" —
the fix sits **inside** measure-first. Items 1 and 2 remain open. Commit
`2516ca8`; corpus evidence in scratchpad `m6/wrapscan.txt`, `m6/wrapdiff.txt`,
and the probes that produced them.)**

#### The cause is one thing, and it is not "unterminated brackets"

The recorded fix-item described the class as unterminated brackets. The raw
Genius sheets show a single upstream mechanism instead: **Genius breaks one
logical lyric line across several physical lines at the edges of an annotated
or styled span.** The bracket case is one instance of it:

```
Man Out of You  L25 '[SHANG & '       Defying Gravity  L102 '[CITIZENS OF OZ & '
                L26 'SOLDIERS'                         L103 'ELPHABA'
                L27 ']'                                L104 ']'

Man Out of You  L28 '('               Paradise         L20 'Between you and I ('
                L29 'Be a man'                         L21 'I'
                L30 ') We must be swift...'            L22 ')'
```

So the same wrap produces both the attribution dirt Ken saw **and** lines
that begin with a stray `)`. The two are not separable: the `)` belongs to the
`(Be a man)` span. `_HEADER_RE` and `_BRACKET_CONTENT_RE` both require a
closing `]`, which is why neither fired.

Full scan of the 17 frozen sheets, by class:

```
UNBAL (physical line leaves '[' or '(' open)   30
TRAIL (physical line ends with whitespace)      4   (2 of them also UNBAL)
LEAD  (physical line starts with whitespace)    1
songs carrying any of it: 5 of 17
```

#### The fix

`_join_wrapped_lines` in `genius_lyrics.py`: while a line leaves `[` or `(`
open, absorb following non-blank lines until it balances. Fragments are
concatenated with **no separator** — the wrap replaced nothing, and the source
carries the real word spacing (`'[SHANG & '`). A stanza blank line bounds the
join, so a genuinely stray delimiter can swallow at most its own stanza.

This repairs the input rather than adding a filter: `[SHANG & SOLDIERS]` then
becomes the bracket-only line `_HEADER_RE` was already written to drop, and
`(Be a man) We must be swift as the coursing river` is exactly the shape the
parser's paren contract documents.

#### Corpus effect — raw

Every one of the 17 bundles' recorded `lyrics.lines` reproduces the pre-fix
parse exactly (17/17), so the before/after diff is against the arms' own input.

```
song                        lines            letters
Defying Gravity             89 -> 86         1879 -> 1860   (-19)
Man Out of You              47 -> 36         1059 -> 1046   (-13)
Free                        41 -> 40         identical
HUNTR/X                     53 -> 52         identical
Paradise                    65 -> 64         identical
other 12 songs              unchanged        identical
```

**The only letters removed corpus-wide are the two attributions**: -19 is
`CITIZENSOFOZ` + `ELPHABA`, -13 is `SHANG` + `SOLDIERS`. Every other line-count
drop is regrouping, not loss. 13 broken lines are repaired — 9 of them Man Out
of You's `) We must be swift as the coursing river` class, which becomes
`(Be a man) We must be swift as the coursing river`.

**Note the rendering change this carries on Man Out of You**: the 9 `Be a man`
chants no longer stand as their own karaoke lines, they lead the line they
belong to. That is the Genius sheet's own structure; the `.lrc` for that song
times them separately. Recorded, not ruled.

#### Residual — the whitespace-wrap class, not fixed

```
Paradise  L10 'Oh, '  + "we've been down a long, long road now..."
Paradise  L26 'lik'   + 'e' + ' (Ohh)'
HUNTR/X   L16 "Show me what's underneath, " + "I'll find your harmony<glued>"
```

Two junk lines survive on Paradise (`Oh,` and `e`). The delimiter signal does
not reach them, and the whitespace signal does not close the case either:
`lik` has no trailing space and `e` has no leading space, so a trailing/leading
whitespace rule would still leave two fragments, while adding a heuristic that
can merge two genuine lyric lines on sheets outside this corpus. Left unfixed
deliberately; extending it is available if Ken wants it.

#### What this costs the pending eyeball

The 5 changed songs' stored bundles are now stale. Of the ten warp-accepted
songs cleared for the pre-registered joint-vs-arm-C eyeball, **only Free is
affected** — Man Out of You, Defying Gravity and Paradise are not in that ten,
and HUNTR/X is shown separately as the cram item. So the eyeball needs one
song's bundles regenerated, not the cohort.

#### Tests

4 new cases in `tests/unit/test_genius_lyrics.py`, keyed to the real corpus
shapes: the wrapped attribution, the wrapped paren line, the wrapped fragment,
and the stanza bound on a delimiter that never closes. Full suite 1516 pass /
4 fail — the 4 are the box's pre-existing Windows failures, unrelated.

### 2026-09-08 — M7 commissioned (RATIFIED by Ken): re-derive S-1 against a route-independent timing reference

**(Ken ratified the approach, not yet a read-off. Pre-registration of M7's
rules is owed before any number is looked at — see "Still owed" below.
Availability figures from scratchpad `m6/refcheck.py`; cohort counts
re-derived at the same session. Nothing has been run.)**

#### What this is for

The S-1 re-read left the GO standing as a ruling that cannot be re-derived,
because both of its metric conjuncts are scored by each route's own fallback
class. The scaffold route places **every** sheet line (no drop branch exists in
`cue_align.py` — a bad line is re-aligned or re-paced, never dropped), so it
cannot lose on coverage; the joint route hides the lines it could not place,
so those lines cannot overlap and it cannot lose on overlap. Every aggregate
comparison between the two is decided by the contract rather than the timing.
M7 exists to replace that with a comparison neither route can win by
construction.

#### The enabling fact — there is an unread timing reference on disk

`timing_fetch.ensure_timing` writes `lyrics/<stem>.timing.json` at add time
(Musixmatch richsync/subtitle, NetEase fallback), selected reference-free by
text map-rate. `lyrics_fetch.py` stashes it as `ctx.artifacts["synced_timing"]`
above the confidence bar — and **no router consumes it**; the stage's own
docstring records that it "is inert until one does". Grep confirms the only
two mentions of `synced_timing` in the tree are the write and the docstring.

So it is independent of both routes under comparison: neither the warp
scaffold nor the joint matcher has ever read it. That independence, not its
quality, is what makes it usable here.

#### Availability — raw

```
song                     source      map_rate  kind   in eyeball ten
Colors of the Wind       musixmatch  0.946     word   TEN
Next Ten Minutes         musixmatch  0.930     line   TEN
Seasons of Love          musixmatch  0.912     word   TEN
Domino                   musixmatch  0.910     word   TEN
Best Part of Me          musixmatch  0.868     word   TEN
Belle                    musixmatch  0.855     word   TEN
HUNTR/X                  musixmatch  0.811     line   -
Free                     musixmatch  0.805     word   TEN
Paradise                 netease     0.785     line   -
Man Out of You           musixmatch  0.745     word   -
Bloodstream              musixmatch  0.703     line   -
Be Our Guest             musixmatch  0.688     line   TEN
Defying Gravity          musixmatch  0.685     line   -
Hakuna Matata            netease     0.625     line   -
Popular                  musixmatch  0.629     word   TEN
In Summer                netease     0.581     line   TEN
Girl in the Bubble       MISSING                      -

16 of 17 corpus songs carry a sidecar; all 16 are above WRONG_SONG_MAP_RATE.
All 10 of the cleared eyeball cohort carry one; 7 of those 10 are word-level.
Validation cohort (uploader .srt AND timing sidecar, library-wide): 26 songs.
  ^ WRONG — corrected by the pre-registration below (finding 1). 18 of the 34
    .srt carry a .srt.generated marker and are PiKaraoke's own output. The real
    cohort is 7 uploader + 10 ASR = 17, of which 10 are corpus songs and 6 are
    in the cleared eyeball ten. Left in place as the figure the ratification
    was given on.
```

#### M7-a — does the reference track *our* recording?

The gate on everything else. These are movie clips, live cuts and
20th-anniversary re-records; the reference is fetched against title/artist and
is very likely timed to a studio release. `map_rate` scores *text* mapping, and
PROGRAM.md's demotion-gate table already records that it is adequate for
wrong-*song* only (M2, 32/32 controls) with wrong-*edit* left open as "a
routing-time warp-gate question". M7-a is that question, asked at last.

Method: compare each sidecar against the song's own `subtitles/<stem>.srt` cue
times. Both YouTube uploader captions and YouTube ASR captions are timed to
**our** video, which is the property M7-a needs; provenance of each `.srt`
(uploader vs auto) is confirmed at setup, and either serves. Cohort 26 songs.

If the reference drifts against captions, M7 stops here and the fallback below
runs instead.

#### M7-b — score both routes against the reference

On the lines the reference covers, both routes have committed to a timing for
the same line and neither is credited for its own fallback class. The scaffold's
extra lines stop being a free coverage win and become checkable — the reference
either places a line there or it does not. The joint route's hidden lines stop
being a free overlap win and become a measurable loss wherever the reference
says something was sung there.

Pairing key is the line id: both routes parse the same sheet through
`parse_lyric_lines`, so index *i* denotes the same line on both sides —
**provided both sides were parsed post-`2516ca8`.** Of the ten eyeball songs
only Free changed under the parser fix, so nine pair against existing artifacts
and Free needs regenerated bundles.

#### M7-c — eyeball only the residual

Map rates run 0.58-0.95, so roughly a third of sheet lines will have no
reference line. That remainder is where the dialogue and the wrap residue live
and it needs Ken's eyes — but as a bounded set against a known question, not as
a general impression of a whole song.

#### Fallback if M7-a fails

Compare the two routes only on lines **both** rendered, and treat the lines
only one route renders as a separate signed judgment: real lyrics wrongly
hidden counts against the joint route, dirt or crammed filler counts against
the scaffold. Both signs have already been observed once (Man Out of You's nine
chants; Bloodstream's cram). This is fair but remains a proxy — it removes the
rigging without supplying a reference.

#### Still owed before M7 runs

Pre-registered read-off rules, one-shot, committed before any number is looked
at — the discipline that caught M6's arm-identity problem before it cost a run.
M7-a's pass/fail bar and M7-b's comparison statistic both need fixing in
version control first. **Ken has ratified the approach only.**

#### Sequencing

M7 replaces "one pre-registered eyeball" as step 2 of the post-M6 order; M7-c
is that eyeball, narrowed. S-1 and the S-3 extension remain Ken's and are
unchanged by this entry.

### 2026-09-08 — M7 pre-registration (RATIFIED by Ken — read-off rules fixed before any number exists)

**(Executor. RATIFIED by Ken 2026-09-08, unchanged from the draft he read.
The M7 commissioning entry above records the approach Ken
ratified and states that read-off rules were owed. This entry writes them,
before the probe is written, following the M1/M2/M6 pattern: the criterion
goes into version control while the numbers do not exist. Nothing here
changes a shipped route. Cohort figures below are availability counts from
`m6/cohort.py` and `m6/cohort_ten.py` — no timing has been compared.)**

#### What M7 decides

Whether **S-1 (scaffold route GO) can be re-derived** against a reference
neither route can win by construction. The commissioning entry states the
problem: the scaffold route has no drop branch so it cannot lose on coverage,
the joint route hides what it cannot place so it cannot lose on overlap, and
every aggregate comparison between them is settled by contract rather than by
timing.

Three outcomes are named now: **RE-DERIVED**, **FAILS RE-DERIVATION**,
**NO AWARD -> Ken**.

#### Four pre-run findings that change the commissioned shape

Recorded before running, which is what a pre-registration is for.

1. **The recorded 26-song validation cohort does not exist. The real figure
   is 17, and only 10 of them are corpus songs.** `subtitles/` holds 34
   `.srt`, but **18 carry a `.srt.generated` marker** — a 69-byte sibling
   reading "Generated by PiKaraoke's lyric-align stage; not an uploader
   caption." Those are our own route output and cannot validate anything;
   counting them was the error. Genuine uploader captions: 16. Adding the 11
   YouTube ASR `.json3` (also timed to our video, and the commissioning entry
   already admits either) and intersecting with the 24 confident sidecars
   gives **7 uploader + 10 ASR = 17 songs library-wide, 10 of them in the
   GATE S corpus.**

2. **Every corpus reference is ASR; every uploader reference is outside the
   corpus.** This is M6 pre-run finding 3 restated: the GATE S corpus was
   *selected* for `lyrics.source_kind != "srt"`, so no corpus song has an
   uploader caption, by construction. The 7 uploader songs (Backstreet Boys,
   Let It Go, Part of Your World, Like I Love You, Mirrors, Rock Your Body,
   Can You Feel The Love Tonight) are all non-corpus. So the cleanest
   validation happens on songs M7-b will never score, and the songs M7-b does
   score are validated against a noisier reference. **M7-a is designed for a
   coarse question and this is tolerable** — see M7-a below — but it is a real
   weakening of the commissioned shape and is not hidden.

3. **YouTube ASR is live in the shipped joint matcher.**
   `lyrics_fetch._resolve_ytasr` feeds `subtitles/<stem>.en.asr.json3` to
   `joint_match` as its third source. So on the 10 corpus songs the joint
   route has already read the file M7-a uses as certifier. This does **not**
   make M7-b circular: the yardstick is the *sidecar*, whose content comes
   from Musixmatch/NetEase and which neither route has read. But it means the
   joint route has an information source timed to our video that the scaffold
   route does not. That is a real advantage of that route, not a metric
   artifact, and M7-b measures it as such — recorded here so it is not later
   mistaken for a missed dependency.

4. **Two certifiable songs need re-running after the parser fix; Free does
   not, and its regeneration is moot.** `2516ca8` changed 5 of 17 corpus
   sheets (Defying Gravity, Free, HUNTR/X, Man Out of You, Paradise). Of the
   10 certifiable songs only **Defying Gravity and Man Out of You** are in
   that set, so 8 pair against existing artifacts and those 2 need regenerated
   bundles and re-run arms. **Free, HUNTR/X and Paradise have no
   route-independent reference at all**, so they leave the cohort regardless —
   the Free regeneration flagged when the fix landed is not needed for M7.

   Of the ten cleared eyeball songs, **6 are certifiable and 4 are not**
   (Free, In Summer, Next Ten Minutes, Domino have a sidecar but only a
   PiKaraoke-generated caption).

#### What gets run

M6's two arm dumps already carry the scaffold placements (`armW/` and
`armC/`, 17 songs each, `--dump-json` `line_objects`); `debug17/` carries the
joint route's. **No aligner runs.** The only new work is regenerating the two
parser-fix songs and writing the probe.

#### M7-a — does the reference track *our* recording? (per-song, certifying)

The gate on everything else, and the wrong-*edit* question the demotion-gate
table left open after M2 settled wrong-*song*.

For each of the 17 songs: take the sidecar's cue starts (richsync `ts` with
text `x` for `kind == "word"`; `cue_spans_from_lrc` for `kind == "line"`) and
the reference's (`cue_spans_from_srt` for uploader; for ASR, a monotonic
token-window match of each sidecar cue's normalized text against the
`ytasr.parse_json3` word stream, taking the matched window's first word
start). Over matched anchors, `residual = sidecar_start - ref_start`, then:

- `n_anchors` — matched pairs
- `offset` — median residual (the sidecar clock legitimately differs; the
  codebase already records this in `parse_lrc_lines`' docstring)
- `frac_within_1s` — share of anchors with `|residual - offset| <= 1.0 s`
- `drift` — median residual of the last third minus that of the first third

**CERTIFIED** iff all three hold: `n_anchors >= 8`, `frac_within_1s >= 0.90`,
`|drift| <= 2.0 s`.

Each number answers a named failure mode, and none is borrowed from a
different question:

- `n_anchors >= 8` — below this the median offset is not robust.
  `srt_cues.PRIOR_MIN_ANCHORS = 4` is the codebase's floor for nudging a
  calibration; doubled here because a wrong certification propagates into
  every M7-b number downstream.
- `+/- 1.0 s` — wide enough to absorb ASR cue-boundary granularity and
  line-start-vs-word-start difference, narrow enough that an edit difference
  (cut verse, added repeat, extra intro) sits far outside it. Deliberately
  **not** `PRIOR_MAX_MAD_S = 0.75`: that constant was swept for display lead
  of audio placements against cues, a different question, and borrowing it
  would be borrowing a threshold across questions.
- `>= 0.90` — one anchor in ten may fall out to text-mapping error without
  indicting the edit.
- `|drift| <= 2.0 s` — a different master's rate mismatch accumulates
  monotonically and a constant offset cannot hide it; 2.0 s is far above
  anchor noise and far below any real re-record divergence.

`mad` is reported but is **robustness only and can never become primary** —
its scale is confounded by ASR granularity, which is exactly why the primary
is a share-within-a-window and not a spread.

**Stop rule.** If fewer than **6** corpus songs certify, M7-b is not run and
the fallback in the commissioning entry runs instead. Below 6 the M7-b margin
below is not reachable on evidence, and a comparison nobody can act on is
worse than an honest proxy.

#### M7-b — score both routes against the certified reference

On every sidecar-covered line of every certified song, both routes are scored
by the same rule, and **each route's fallback class is stripped of its free
win**:

- A line the joint route **hid counts as a miss**, not as absent. That is what
  removes its free overlap win.
- A scaffold line placed by `SOURCE_FILL` or `SOURCE_REALIGN` is scored like
  any other: existing earns nothing, it has to be *right*. That is what
  removes its free coverage win.

Pairing is by line id (both routes parse the same sheet through
`parse_lyric_lines`, so index *i* denotes the same line on both sides,
provided both were parsed post-`2516ca8`), and line -> sidecar cue by
`map_lines_to_cues`.

**Primary statistic: `hit@0.5s`** — the share of sidecar-covered lines the
route starts within 0.5 s of the sidecar's start, after per-song, per-route
median-offset calibration. 0.5 s because that is roughly where a late karaoke
line stops being singable; the calibration is per-route so neither is charged
for the sidecar's clock.

A song contributes only if it has **>= 10** sidecar-covered lines; otherwise
it is reported and excluded.

**Read across songs by sign, not by mean.** Per certified song, whichever
route has the higher `hit@0.5s` wins that song. M6's lesson was that a
per-song max averaged across runs concealed the comparison that mattered.

Robustness only, never primary: `hit@0.3s`, `hit@1.0s`, median absolute
residual, per-route placed-vs-hidden counts, and the arm-vs-arm difference.

#### Read-off rule

Both M6 arms are scored, because S-2 is unresolved and the S-1 answer must not
depend on it. With `w_s` scaffold song-wins and `w_j` joint song-wins:

- **S-1 RE-DERIVED** if, in **both** arms, `w_s - w_j >= 3`.
- **S-1 FAILS RE-DERIVATION** if, in **both** arms, `w_j - w_s >= 3`.
- **NO AWARD -> Ken** otherwise — including, explicitly, the arms disagreeing.

A margin of 3 rather than a bare majority: at N = 6..10 a one-song lead is
noise. Requiring both arms means the conclusion survives either resolution of
S-2.

**M7-b's arm-vs-arm difference can never rule on S-2.** M6-d is unresolved and
only Ken's eyeball settles it. Stated explicitly because the whole reason M6
exists is that a metric was read as a verdict once already.

#### M7-c — eyeball only the residual

Sidecar map rates run 0.58-0.95, so a third of sheet lines will have no
reference line, and the 7 uncertifiable corpus songs have none at all. That
remainder is where the dialogue and the wrap residue live. M7-c puts it to Ken
as a bounded set against a fixed question — *is this line real lyric, dirt, or
crammed filler?* — not as a general impression of a whole song. The question
is fixed now so no render can select it afterwards.

#### One-shot

No adjust-and-re-run. A song that fails to parse or score is reported as
failed and excluded, not retried with different settings. Every robustness
column declared above stays robustness and can never be promoted.

#### Not pre-registered by this entry

The S-3 extension (still Ken's, and prior to the aligner question); M6-d;
any change to `cue_align`, the joint matcher, snap policy, or the F2 build;
GATE J1/J2; S-E and GATE L. M7 re-derives S-1 or it does not — it does not
license F2 by itself.

### 2026-09-08 — M7-a run (raw). Pre-registered stop rule fires; no read-off taken

**(Executor. Rules ratified and committed at `d75499b` before any timing was
compared. One-shot, as pre-registered: nothing was re-run with different
settings. Probes `m6/m7a.py`, `m6/m7a_diag.py`, `m6/m7a_attrib.py`; artifacts
`m6/m7a.txt`, `m6/m7a_rows.json`, `m6/m7a_attrib.txt`, `m6/m7a_attrib.json`.
No route output was read — M7-a compares the sidecar against a caption
reference only.)**

#### M7-a certification table

`*` = GATE S corpus song. `n` = matched anchors, `offset` = median residual
(s), `within` = share of anchors inside 1.0 s of that offset, `drift` = last
third minus first third (s), `mad` robustness only. CERTIFIED iff `n >= 8`,
`within >= 0.90`, `|drift| <= 2.0`.

```
C cert  ref      kind    n  offset  within  drift   mad  song
* NO    asr      line   45   72.97   0.178  51.37  6.54  'Defying Gravity' - Wicked 20th Anniv
* NO    asr      word   59    7.10   0.610  -1.20  0.77  'Popular' - Wicked 20th Anniversary
* NO    asr      line   53    3.30   0.830   0.13  0.19  Be Our Guest [UHD]
* YES   asr      word   40    7.73   0.950  -0.02  0.31  Belle [UHD]
* NO    asr      word   33    0.51   0.788  -0.34  0.36  Ed Sheeran - Best Part Of Me
* NO    asr      line   32    9.59   0.656   9.21  0.41  Ed Sheeran & Rudimental - Bloodstream
* NO    asr      word   38  -31.52   0.474 -13.01  1.18  Mulan - I'll Make a Man Out of You
* YES   asr      word   37    5.94   0.973   0.11  0.10  Pocahontas - Colors of the Wind
* NO    asr      word    4  -18.21   0.500  35.22  6.82  Seasons of Love (HD)
* NO    asr      line   12   -8.95   0.333 -29.82 42.09  The Lion King - Hakuna Matata
  YES   uploader word   36  -13.59   0.917   0.12  0.14  Backstreet Boys - More Than That
  NO    uploader word   33  -38.53   0.212 -42.78  7.90  Idina Menzel - Let It Go
  NO    uploader word   38    1.19   0.658   2.01  0.59  Jodi Benson - Part of Your World
  NO    uploader word   73    3.74   0.808  -0.05  0.43  Justin Timberlake - Like I Love You
  YES   uploader word  106    0.04   0.906  -0.11  0.23  Justin Timberlake - Mirrors
  NO    uploader word  101   -0.42   0.683 -28.37  0.49  Justin Timberlake - Rock Your Body
  NO    uploader word   28   25.97   0.071  13.11  6.08  The Lion King - Can You Feel The Love

corpus songs with a reference: 10
corpus certified            : 2
library certified           : 4
```

#### Failure attribution (added after the run; does not alter any figure above)

The pre-registered statistic cannot distinguish three causes of a `NO`, so
each row was attributed afterwards. `ceil` = order-free token overlap between
sidecar and reference (how much shared content exists at all), `cov` = what
the monotonic anchoring actually matched, `gap = ceil - cov`. A large gap
means the anchoring missed an alignment that was there; a low ceiling means
there was little to align. `refdur`/`siddur` are the reference's and
sidecar's own covered spans in seconds.

```
C cert  ref         ceil    cov    gap  refdur  siddur  cause
* NO    asr         0.41   0.38   0.03     231     344  EDIT     Defying Gravity
* NO    asr         0.86   0.86   0.00     207     193  EDIT     Popular
* NO    asr         0.58   0.50   0.08     210     189  EDIT     Be Our Guest
* YES   asr         0.40   0.39   0.02     295     273  OK       Belle
* NO    asr         0.69   0.61   0.08     218     215  EDIT     Best Part Of Me
* NO    asr         0.40   0.36   0.04     228     260  EDIT     Bloodstream
* NO    asr         0.79   0.75   0.04     232     171  EDIT     Man Out of You
* YES   asr         0.96   0.96   0.00     201     175  OK       Colors of the Wind
* NO    asr         0.04   0.03   0.02      60     187  SPARSE   Seasons of Love
* NO    asr         0.78   0.26   0.52     243     167  MATCHER  Hakuna Matata
  YES   uploader    0.93   0.93   0.00     211     207  OK       More Than That
  NO    uploader    1.00   0.99   0.00     201     117  EDIT     Let It Go
  NO    uploader    0.97   0.97   0.00     171     157  EDIT     Part of Your World
  NO    uploader    0.95   0.95   0.00     268     264  EDIT     Like I Love You
  YES   uploader    0.98   0.98   0.00     457     453  OK       Mirrors
  NO    uploader    0.95   0.95   0.00     286     250  EDIT     Rock Your Body
  NO    uploader    0.94   0.94   0.00     165     197  EDIT     Can You Feel The Love

corpus OK 2 | EDIT 6 | MATCHER 1 | SPARSE 1
```

**One anchoring instrument failure, on Hakuna Matata** (`ceil` 0.78 against
`cov` 0.26). The monotonic block matcher mis-pairs heavily repeated sections —
the exact failure `map_lines_to_cues`' own docstring records for exact-block
matching, which is why that function is fuzzy per-line. **Seasons of Love's
caption file is degenerate**: 26 ASR words covering 60 s of a 187 s song, 4%
token overlap, so nothing about the sidecar is testable there. Both are
recorded as found; neither was re-run.

**Every other row's anchoring reached the available ceiling** (`gap <= 0.08`).
On the seven uploader-caption songs the text agreement is 0.93-1.00 and the
anchoring achieves it, yet five of the seven still fail certification — Let It
Go at `ceil` 1.00 pairs perfect text against a 117 s sidecar span for a 201 s
video. Those failures are not an artifact of the matcher.

#### Stop rule

Pre-registered: *"If fewer than 6 corpus songs certify, M7-b is not run and
the fallback in the commissioning entry runs instead."* Corpus certified is
**2**. The two attributable-to-instrument songs (Hakuna Matata, Seasons of
Love) could not lift the count past **4** even if both were repaired and both
then certified, so the rule's outcome does not depend on either.

No read-off is taken here and no verdict on S-1 is recorded. The fallback,
`route-line-timing.md`'s commissioning entry, is a shared-lines-only
comparison plus a signed judgment on each route's exclusive lines.

### 2026-09-08 — M7 fallback, pre-work (raw). Two structural findings; no rules drafted, no verdict

**(Executor. Structural only — nothing here scores a timing and no comparison
statistic was computed. Probes `m6/fb_avail.py`, `m6/fb_hidden.py`,
`m6/fb_render.py`, `m6/fb_pop.py`; artifacts `m6/fb_avail.txt`,
`m6/fb_hidden.txt`, `m6/fb_render.txt`, `m6/fb_pop.txt`. Sources: the 17
scaffold arm dumps from M6 (`m6/armW`, `m6/armC`, 2026-09-04) and the shipped
joint route's bundles in `alignment_debug/` (2026-07-16). Both sides predate
`2516ca8`, so line ids pair consistently on all 17 songs, Free included.)**

The fallback is "a shared-lines-only comparison plus a signed judgment on each
route's exclusive lines". Sizing that population first turned up two facts
that bear on what the fallback can be, so they are recorded before any rule is
written.

#### Finding 1 — what "rendered" means, and where the joint route's hidden lines are

`_write_ass` skips any line object with no words (`lyric_align.py:1121`,
`if not words: continue`), so a line carries a subtitle event iff it has
words. `scaffold_align_corpus.py` already scores it that way
(`placed = sum(1 for o in line_objects if o["words"])`).

On the joint side the hidden set is **not** `absent_line_ids` — that list is
**empty on all 17 songs**. Lines the matcher does not place are handed to
`_interpolate_missing` and tagged `interp`; they receive a start and end but no
words, so `output_line_timings` has a row for every sheet line while the ASS
has an event only for the placed ones. On 12 songs the wordless set is exactly
`interpolated_line_ids`; on 5 (Popular, Belle, Bloodstream, HUNTR/X, Seasons of
Love) it is larger by 1-6 lines, so a few *selected* lines also end wordless.

On the scaffold side **no placed line is wordless on any song** — `SOURCE_FILL`
paces words across the window — so the scaffold renders every sheet line.

Population, therefore: `scfOnly` is the joint route's hidden set, and
`joint-only` is **0 on every song**.

```
   song                        sheet  scfRnd  jntRnd  shared scfOnly
   Defying Gravity                89      89      51      51      38
T  Free                           41      41      40      40       1
T  Popular                        62      62      51      51      11
T  Be Our Guest                   77      77      77      77       0
T  Belle                         110     110     101     101       9
T  Best Part Of Me                38      38      37      37       1
   Bloodstream                    74      74      47      47      27
   This Is What It Sounds Like     53      53      32      32      21
T  Domino                         67      67      63      63       4
T  In Summer                      31      31      29      29       2
   Man Out of You                 47      47      36      36      11
   Paradise                       65      65      53      53      12
T  Colors of the Wind             37      37      37      37       0
T  Seasons of Love                34      34      25      25       9
   Hakuna Matata                  40      40      33      33       7
T  Next Ten Minutes               71      71      67      67       4
x  Girl in the Bubble             36      36      29      29       7

T = one of the ten cleared for eyeball work; x = out of scope (M6 convention)
in-scope totals: sheet 936  shared 779  scaffold-only 157
scaffold-only lines within the ten: 41
joint-only lines, every song: 0
```

Both of the commissioning entry's example signs live in this one set: Man Out
of You's nine chants (real lyric the joint route hid) and Bloodstream's cram
(filler the scaffold placed) are both scaffold-only lines. The set is
one-sided in membership and two-sided in sign, which is what the fallback
asked for. Within the cleared ten it is 41 lines.

#### Finding 2 — the scaffold arm's scaffold source is the sidecar M7-a just measured

`scaffold_align_corpus.py` defaults to `--timing sidecar`, and
`scaffold_align_song.sidecar_scaffold_cues` reads
`lyrics/<stem>.timing.json` — the same file M7-a certified against a caption
reference. Both M6 arms ran on that default.

Cross-tabbing the two recorded tables — M7-a's attribution and the per-song
warp path from the 2026-09-04 amendment entry — over the 10 corpus songs that
have a reference:

```
song                 M7-a        warp path (arm W)
Defying Gravity      EDIT        densify-fallback (MAD gate, both models fail)
Popular              EDIT        affine-ok (slope 1.0074, intercept -8.075)
Be Our Guest         EDIT        affine-ok (slope 1.0017, intercept -3.430)
Best Part Of Me      EDIT        affine-ok (slope 1.0002, intercept -0.643)
Bloodstream          EDIT        affine-ok (slope 0.9939, intercept -9.496)
Man Out of You       EDIT        affine-ok (slope 0.9881, intercept 32.285)
Belle                OK          affine-ok (slope 1.0009, intercept -7.867)
Colors of the Wind   OK          affine-ok (slope 0.9991, intercept -6.286)
Seasons of Love      SPARSE      affine-ok (slope 0.9542, intercept  1.227)
Hakuna Matata        MATCHER     affine-ok (slope 1.0078, intercept  8.717)

6 EDIT: warp gate rejected 1, accepted 5.
2 OK: accepted (correctly).
2 instrument-attributable, uninformative about the sidecar either way.
```

The affine warp absorbs an offset and a rate difference by construction, which
is what the large intercepts are. M7-a's EDIT failures are not all of that
shape — the recorded residuals include drift of 9-51 s and, on the uploader
rows, sidecar spans far short of the video — and an affine fit cannot express a
cut verse or an added repeat. Whether the accepted-EDIT songs are the affine
kind or the structural kind is **not** established by anything above; it is a
cross-tab of two tables, not a measurement.

Bearing: `synced_timing` is inert in the shipped pipeline, so this touches no
shipped route. It touches the scaffold arm that M6 and S-1's evidence were
produced on, and the fetch-pillar sidecar is F2's designed scaffold source.

#### Nothing ruled

No fallback read-off rules are drafted by this entry, no statistic was
computed, and no verdict on S-1 is recorded. What the fallback should measure,
given Finding 2, is Ken's.

### 2026-09-08 — Fable judge round on the path forward (Ken commissioned; recommendation recorded, no verdict)

**(Judge round, read-only, one billed pass, commissioned by Ken after the
fallback pre-work. The round recommends a path; the ruling on S-1, and on the
gate question it raises, stays Ken's. The executor verified its load-bearing
code claims against source and artifacts before recording — see "verified"
below — and found one instance the round did not report.)**

#### Recommendation, as given

Run the fallback, but pre-register it as a **stratified** comparison: a
GPU-free warp-fit shape diagnostic that labels each song's scaffold from the
arm's own inputs, then the shared/exclusive read-off taken **per stratum**,
with the eyeball bounded by a pre-registered selector. Option A with option C
folded in as a declared stratification column rather than a separate step.
Options B (re-run with the scaffold source disabled or swapped) and D (finding
2 alone is sufficient) were rejected; the reasons are recorded under "what the
round says the program has wrong".

#### The mechanism it identified

The cram is the **duration clamp**, and the gate cannot see the condition that
produces it.

`warp_scaffold_cues` builds its fit population as
`common = [(scaffold[lid][0], anchors[lid][0]) for lid in scaffold if lid in
anchors]` (`cue_align.py:408`) — only lines that both the fetched scaffold and
the audio anchors place. A section the video never sings has no anchor, so it
never enters the check that is supposed to catch it. Acceptance is
`median(abs(residual)) <= WARP_MAD_GATE_S` (2.0 s) over that population, and
Theil-Sen supplies the fit, so both the fit and the gate are medians: the gate
rejects when more than half the *sung* lines are off, which is not the same
question as whether the source describes a different edit. Its docstring says
"above this MAD only when it is a structurally different recording"; that is
not what the code does.

Every scaffold line that warps past the end of the video is then pinned by
`starts[lid] = min(max(0.0, slope * scaffold[lid][0] + intercept), duration)`
(`cue_align.py:441`), stacks on one timestamp, yields a zero-width cue, fails
its align and is re-paced at the floor. The floor named by the S-1 re-read is
the symptom; the clamp is the cause.

#### Verified by the executor before recording

```
claim                                                     result
common = scaffold ∩ anchors only (cue_align.py:408)       confirmed verbatim
gate = median(|residual|) <= WARP_MAD_GATE_S = 2.0        confirmed
duration clamp at cue_align.py:441                        confirmed verbatim
WARP_MIN_ANCHORS = 5                                      confirmed
arm W Bloodstream: 38 lines share one start (246.70)      confirmed
arm W HUNTR/X:     20 lines share one start (159.76)      confirmed
arm W Belle:       no stacked start                       confirmed
diagnostic needs no GPU and no audio decode               confirmed: align_lines,
  transcribe_words and media_duration_s all come from the bundle, ASR from the
  .json3 on disk, scaffold from the sidecar; the ffmpeg/wav path in run_song is
  a duration fallback only
m6/debug17 is byte-identical to the 17 production bundles  confirmed (17/17)
duration match is only a map_rate tie-break at fetch       confirmed: best_by_reference
  sorts on key = (rate, dur_key) with dur_key = -abs(track_length - media_dur), so a
  source describing a different-length recording is preferred whenever its text maps
  better; track_length is carried into the sidecar, so the signal is on disk already
```

**One instance the round did not report.** The same expression clamps at the
front: `max(0.0, ...)`. Arm W Popular has **5 lines pinned to 0.0**. The
mechanism bites at both ends, so the diagnostic below tests both.

#### What the round says the program has wrong

Recorded as given, unruled:

1. "Which shape those 5 are is not established" is half true. Two corpus crams
   are resolved by the above (sidecar longer than video, clamped, invisible to
   the gate); Man Out of You is the other direction and resolvable from the
   recorded tables (a first-to-last-third step far larger than the fitted slope
   over that span can produce). Popular, Be Our Guest and Best Part of Me are
   genuinely open and look affine.
2. **"Warp-accepted" never meant "same edit", so S-3's scope was drawn on a
   meaning the code does not implement.** The open extension question is not
   "does the principle extend to warp-accepted songs" but "the gate does not
   implement the principle Ken already ruled" — a code fact, rulable without
   the fallback and **prior** to it.
3. The fetch pillar's premise is false for this library, and the signal that
   says so was already fetched — **verified above**. Bearing on S-1's
   economics: F2's value is (delta on sound songs) x (fraction sound), and the
   pre-work bounds the second factor low.
4. The fallback's two motivating signs are both outside its bounded eyeball,
   and one no longer exists: post-`2516ca8` Man Out of You's nine chants are
   prefixes of the following lines, not lines. The 41-line set tests the class,
   not the named instances.
5. The cleared ten is the easy set for both routes — it was cleared as
   "warp-accepted + dirt-free", which after (2) means "dirt-free". Do not
   expand it; Man Out of You now qualifies on the criterion but its bundles are
   stale, so it is recorded as the known blind spot.
6. Out of remit, passed on as given: if S-1 falls, M7-a's evidence points at
   the fetched timing entering the **joint matcher as one per-line candidate
   among others** — where a wrong-edit line simply loses — rather than at a
   per-song route with a per-song gate. That is a J1-adjacent build, not F2,
   and nothing in the program has priced it.

#### Not ruled

The round recommends; it does not rule. S-1, the gate question in (2), and
whether to accept this path are Ken's. No gate has been changed.

### 2026-09-08 — M7 fallback pre-registration, stratified (RATIFIED by Ken — rules fixed before any number existed)

**(Ratified unchanged by Ken on 2026-09-08, before the diagnostic was
computed. Rules fixed before any number exists, per the discipline that has governed
every read-off in this lane. Ken accepted the judge round's path; these are the
rules that path needs. Nothing below has been run: the diagnostic has not been
computed, no stratum membership is known, and no arithmetic has been taken.
One-shot, as before.)**

#### Why stratified

The fallback compares the two routes without a reference. The pre-work
established that the scaffold arm's own scaffold source misdescribes the edit
on part of the corpus, and the judge round established that the gate cannot see
the worst of that by construction. An unstratified comparison would therefore
average "the route on a sound input" against "the route on a broken input" and
call the result the route's licence. Stratifying separates the two readings:
within sound scaffolds the comparison is about the route; within leaked ones it
is about the input, and belongs to the S-3 extension rather than to S-1.

#### Part 1 — warp-fit shape diagnostic (no GPU, all 17 songs)

Recompute what the arm computed, by **calling the same functions, not
reimplementing them**: `scaffold_align_song.sidecar_scaffold_cues`,
`ytasr.parse_json3` / `cue_spans_for_lines` / `normalize_words`,
`cue_align.merge_cue_spans`, and `cue_align._theil_sen`. Inputs are
`m6/debug17` (byte-identical to the production bundles, so `align_lines`,
`transcribe_words` and `media_duration_s` all come from there), the `.json3`
ASR on disk, and `lyrics/<stem>.timing.json`.

**Reproduction check, declared, and able to suspend the read-off.** The
recomputed slope and intercept must match `m6/armW_run.log` to the logged
precision on every warp-applied song. A song that fails to reproduce is
reported and excluded. If more than two fail, the diagnostic is suspended and
nothing below is read.

Per song, from the accepted fit:

- `n_clamp_end` — scaffold lines whose warped start is `>= duration` **before**
  the clamp. This is the cram, counted exactly, and it is what the gate cannot
  see.
- `n_clamp_zero` — scaffold lines whose warped start is `<= 0.0` before the
  clamp. The same failure at the front.
- `off_run` — the longest contiguous run, by line id, of `common` lines whose
  post-fit residual exceeds `WARP_MAD_GATE_S`. This is the other direction:
  content the video has and the source does not.
- `share_within_gate` — share of `common` lines within `WARP_MAD_GATE_S` of the
  fit. **Robustness only.**
- `len_ratio` — |source track length − media duration| / media duration.
  **Robustness only**, and reported because it is the signal the fetch stage
  already holds.

**Strata, fixed here:**

- **REJECTED** — the warp never applied the source (`densify-fallback` or
  `densify-fallback (no scaffold)`). Reported; read in neither stratum.
- **STRUCTURAL** — `n_clamp_end >= 3` or `n_clamp_zero >= 3` or `off_run >= 4`.
- **AFFINE** — everything else.

Constants, each with the failure mode it names:

- **3 clamped lines.** A boundary rounding artifact can pin at most the final
  (or first) cue, so three is the smallest stack that cannot be one, and is
  already a visible stack on screen. Too low and a song with one overhanging
  cue is called structural; too high and a short tail cram is called affine.
- **A 4-line run.** The shortest run that spans a whole lyric section rather
  than a few mis-anchored lines. Too low and ordinary anchor noise over a
  repeated section reads as structure; too high and a displaced verse reads as
  affine.
- **`WARP_MAD_GATE_S` is deliberately reused here**, unlike M7-a's refusal to
  borrow `PRIOR_MAX_MAD_S`. That refusal was right because the constant had
  been swept for a different question; this one is the gate's own per-line
  tolerance, and the question is precisely what the gate does not see, so the
  diagnostic must be on the gate's own scale.

#### Part 2 — arithmetic on the cleared ten (no GPU)

Population: the ten cleared for eyeball work, on the pre-`2516ca8` artifacts
both sides already share, so line ids pair. Both arms computed. The six
out-of-set songs get Part 1 and this arithmetic as a **declared out-of-set
column**, never an eyeball and never a read.

- **Shared lines** (both routes render): `delta = start_scaffold -
  start_joint`. Per song report median `delta`, share `|delta| <= 0.5 s`, and
  the count over 2.0 s.
- **Exclusive lines**: all of them within the ten — 41, by the pre-work's
  count, which is fixed by the artifacts and not by anything measured here.

**The arithmetic selects; the eye scores.** No reference exists on shared
lines, so `delta` cannot say which route is right and is never read as a
score. Its only job is to choose what Ken looks at.

**Selector, fixed now so no render can choose it afterwards:** per song, the
three shared lines with the largest `|delta|`, ties to the lower line id, and
only lines with `|delta| > 0.5 s` qualify — a song where the routes agree
contributes fewer than three, or none. Ceiling: 30 shared looks + 41 exclusive
= **71**.

#### Part 3 — the eyeball and the read-off

The sitting is on **arm C** (`.ass` over the video, against the production
`.ass`), whose provenance is checked against the 2026-07-16 bundle before the
sitting starts — the M6 arm-identity lesson. Two fixed questions:

- **Shared, disagreeing line:** *which route shows this line when it is sung?*
  -> scaffold / joint / both wrong / cannot tell.
- **Exclusive line:** *what is this?* -> sung lyric shown when sung / sung
  lyric at the wrong time / not a lyric (dirt, dialogue) / filler or cram /
  cannot tell.

**Presentation — an on-screen marker (Ken's request, 2026-09-08).** The
selected sections are lopsided across the ten, so seeking to 71 timestamps is
worse than watching the heavy songs through. Each song's subtitle file is
copied with a banner track added at the top of the frame, lit from a few
seconds before each selected section until its end, carrying that section's
fixed question. mpv already loads the subtitle file as a sidecar
(`m6/eyeball.ps1`), so this needs no re-render and no GPU, and the karaoke
line's own position is untouched. The existing seek-to-timestamp path stays
for songs with only one or two selections.

Three constraints, because presentation must not become selection:

- The banner is **generated mechanically from the Part 2 selector output, in
  one pass, before the sitting**. It is never hand-placed and never revised
  after any section has been watched — otherwise it is a second, unregistered
  chance to choose what gets looked at.
- It carries **only** the section's fixed question and an index into the
  look-list. Never the `delta` that selected the line, never a rank, never a
  route name, never a stratum label.
- It is **byte-identical across the two versions of a song**. A banner that
  differed would tell Ken which route he is watching and would bias the shared
  question, which turns on not knowing.

The marker changes no rule above and no figure below; it is a viewing aid over
an already-fixed set.

Per song:

- `A` = (#scaffold) - (#joint). "Both wrong" and "cannot tell" score zero.
- `B` = (#lyric shown when sung) - (#not a lyric + #filler or cram). "Wrong
  time" and "cannot tell" score **zero**: a real lyric placed wrongly is a
  failure of both contracts — the joint route hid it and the scaffold
  misplaced it — and must not decide between them.
- The **scaffold wins the song** if `A >= 0` and `B >= 0` and at least one is
  positive; the **joint wins** symmetrically; otherwise the song is NO AWARD
  and counts for neither.

**Read across songs by sign, within stratum, never by mean.** With `w_s` and
`w_j` the song wins in a stratum:

- **AFFINE stratum** — `w_s - w_j >= 3` supports S-1 on sound scaffolds;
  `w_j - w_s >= 3` is against it; otherwise **NO AWARD -> Ken**.
- **STRUCTURAL stratum** — the identical statistic is **S-3-extension
  evidence, not S-1 evidence**, and is labelled that way wherever it is
  reported.
- A stratum with fewer than **4** songs is reported and **not read**.

A margin of 3 rather than a bare majority, matching M7-b: at these stratum
sizes a one-song lead is noise, and this read-off has an eyeball where M7-b
would have had a reference, so it should be no less stringent.

**Declared limit on S-2, stated before the run.** Both conjuncts need eyes and
the sitting is on arm C only, so this read-off **cannot** show that its
conclusion survives either resolution of S-2 — unlike M7-b, which required its
margin in both arms. Guard: arm W's shared-line arithmetic is computed for
every read song, and if its median `delta` disagrees in sign with arm C's on
**3 or more** of them, the read-off is suspended and goes to Ken.

**Robustness only, never primary:** `share_within_gate`, `len_ratio`, raw
clamp counts, the pooled-ten read across strata, per-song `delta`
distributions, the out-of-set six, and the arm-vs-arm difference. As in M7-b,
**the arm-vs-arm difference can never rule on S-2.**

#### One-shot

No adjust-and-re-run. A song that fails to reproduce, parse or score is
reported as failed and excluded, not retried with different settings. Every
robustness column declared above stays robustness and can never be promoted.

#### Not pre-registered by this entry

The gate question the judge round raised (that `common` excludes exactly the
lines a wrong-edit source adds, so the gate does not implement the S-3
principle) — that is a code fact, rulable without this measurement and prior
to it; S-2 and M6-d; any change to `cue_align`, the warp gate, the joint
matcher, snap policy, or the F2 build; the fetch-time duration check; the
"fetched timing as a joint-matcher candidate" idea; GATE J1/J2; S-E and GATE
L. This measurement re-derives S-1 on sound scaffolds or it does not — it does
not license F2 by itself.

### 2026-09-08 — M7 fallback, Parts 1-2 run (raw). Reproduction clean; the declared sign guard fires; no eyeball taken, no read-off

**(Executed against the entry above, ratified unchanged by Ken before any
number existed. One-shot, as pre-registered. Nothing below is a verdict; the
guard's consequence is Ken's, not the executor's.)**

**Provenance.** `m6/fb_part1.py` -> `m6/fb_part1.txt`, `m6/fb_part1.json`;
`m6/fb_part2.py` -> `m6/fb_part2.txt`, `m6/fb_looks.json`. Inputs as
pre-registered: `m6/debug17` bundles, `subtitles/<stem>.en.asr.json3`,
`lyrics/<stem>.timing.json`, and the pre-`2516ca8` arm dumps `m6/armC` and
`m6/armW`. No GPU, no alignment, no render. Part 1 calls the arm's own
functions rather than reimplementing them: `sidecar_scaffold_cues`,
`ytasr.parse_json3` / `cue_spans_for_lines` / `normalize_words`,
`merge_cue_spans`, `_theil_sen`, and the gate constants as imported.

**Two harness facts, recorded because they touch the reproduction claim.**

1. Seven of the seventeen bundles carry a null `media_duration_s`, so arm W
   itself fell back to the converted vocal stem's own length
   (`scaffold_align_song.run_song`: `duration = bundle.get("media_duration_s")
   or wav_dur`). Since `duration` is the clamp bound the diagnostic counts
   against, the fallback is reproduced the same way -- same ffmpeg conversion,
   same wav-header read -- rather than approximated from a container probe.
   Per-song provenance is in `fb_part1.json` (`dur_src`).
2. The first execution reported one reproduction failure, on the no-scaffold
   song. It was a defect in the comparison string in the harness, not in the
   recomputation: the recomputed warp decision was already identical to the
   log, but the harness built its label without the log's `warp path=` prefix
   on that one branch. The label was corrected and Part 1 re-run. This is
   recorded rather than quietly fixed because the pre-registration forbids
   adjust-and-re-run: no rule, threshold, stratum boundary or input changed,
   the affected song is REJECTED under either spelling and is read in no
   stratum, and no shape column was recomputed.

#### Part 1 — reproduction check

All 17 warp decisions reproduce exactly, to the logged precision, against
`m6/armW_run.log`: 14 `affine-ok` with matching slope and intercept, 1
`offset-rescue` with matching offset, 2 `densify-fallback`. **Failures: 0**
(declared suspension threshold: more than 2). The diagnostic is therefore not
suspended.

```
warp path=densify-fallback                                 'Defying Gravity' - Wicked 20th Anniversary Edition
warp path=affine-ok (slope=0.9974, intercept=-0.009)       'Free' _ Official Lyric Video _ Sony Animation
warp path=affine-ok (slope=1.0074, intercept=-8.075)       'Popular' - Wicked 20th Anniversary Edition
warp path=affine-ok (slope=1.0017, intercept=-3.430)       Beauty and the Beast (1991) - Be Our Guest [UHD]
warp path=affine-ok (slope=1.0009, intercept=-7.867)       Beauty and the Beast (1991) - Belle [UHD]
warp path=affine-ok (slope=1.0002, intercept=-0.643)       Ed Sheeran - Best Part Of Me (feat. YEBBA)
warp path=affine-ok (slope=0.9939, intercept=-9.496)       Ed Sheeran & Rudimental - Bloodstream
warp path=affine-ok (slope=1.0147, intercept=-0.497)       HUNTR/X 'This Is What It Sounds Like'
warp path=affine-ok (slope=1.0124, intercept=-0.441)       Jessie J - Domino (Official Video)
warp path=affine-ok (slope=0.9975, intercept=-0.724)       Josh Gad - In Summer (From 'Frozen')
warp path=affine-ok (slope=0.9881, intercept=32.285)       Mulan _ I'll Make a Man Out of You
warp path=offset-rescue (offset=24.241)                    NSYNC - Paradise
warp path=affine-ok (slope=0.9991, intercept=-6.286)       Pocahontas - Colors of the Wind
warp path=affine-ok (slope=0.9542, intercept=1.227)        Seasons of Love (HD)
warp path=affine-ok (slope=1.0078, intercept=8.717)        The Lion King - Hakuna Matata
warp path=affine-ok (slope=1.0005, intercept=0.967)        The Next Ten Minutes Lyrics
warp path=densify-fallback (no scaffold)                   Wicked - For Good (2025) - The Girl in the Bubble
```

#### Part 1 — shape table, all 17 (primary: clampEnd, clampZero, offRun; withinGate and lenRatio are declared robustness only)

```
stratum      clampEnd clampZero offRun  nCommon nScaf nAnch nLines withinGate lenRatio  dur      song
AFFINE              0         0      0       21    33    28     41      1.000    0.0211  192.052 'Free' _ Official Lyric Video
AFFINE              0         0      1       43    53    61     77      0.977    0.0376  217.803 Be Our Guest [UHD]
AFFINE              0         0      0       72    94    85    110      1.000    0.0288  297.424 Belle [UHD]
AFFINE              0         0      2       14    33    16     38      0.786    0.0182  247.501 Best Part Of Me
AFFINE              0         0      1       12    61    14     67      0.917    0.1481  234.777 Jessie J - Domino
AFFINE              0         0      0       16    18    24     31      1.000         -  113.035 In Summer
AFFINE              0         0      2       20    35    22     47      0.900    0.1615  240.907 Man Out of You
AFFINE              0         0      3        9    51    12     65      0.667         -  305.017 NSYNC - Paradise
AFFINE              0         0      1       34    35    35     37      0.971    0.1345  202.733 Colors of the Wind
AFFINE              0         0      1       12    31    13     34      0.833    0.0673  194.885 Seasons of Love
AFFINE              0         0      1       16    25    19     40      0.875         -  248.036 Hakuna Matata
AFFINE              0         0      1       58    66    63     71      0.983    0.0065  454.043 The Next Ten Minutes
REJECTED            -         -      -       39    61    43     89          -         -  257.231 Defying Gravity
REJECTED            -         -      -        -     0    23     36          -         -  194.119 Girl in the Bubble
STRUCTURAL          0         1      4       33    39    44     62      0.879    0.0459  211.302 'Popular'
STRUCTURAL         18         0      1       22    52    23     74      0.864    0.5999  246.898 Bloodstream
STRUCTURAL         15         0      1       13    43    15     53      0.923    0.5100  160.264 This Is What It Sounds Like
```

Strata over all 17: AFFINE 12, STRUCTURAL 3, REJECTED 2.

#### Part 2 — shared-line arithmetic on the cleared ten

`delta = start_scaffold - start_joint`, per the pre-registered population
(scaffold-rendered = both arms emit words; joint-rendered = the bundle's
`output_line_timings` carries `n_words`). Both arms computed. **`delta` has no
reference behind it and is not read as a score.**

```
stratum      song                 nShared      medC  shrC<=.5    C>2.0 |      medW  shrW<=.5    W>2.0
AFFINE       Be Our Guest              77    +0.294     0.740       11 |    +0.010     0.740        9
AFFINE       Belle                    101    +0.149     0.792        3 |    -0.010     0.832        2
AFFINE       Best Part Of Me           37    +0.198     0.676        1 |    +0.018     0.649        2
AFFINE       Colors of the Wind        37    +0.049     0.946        1 |    -0.442     0.568        1
AFFINE       Domino                    63   -13.928     0.238       43 |   -13.404     0.317       37
AFFINE       Free                      40    +0.126     0.900        1 |    -0.030     0.875        1
AFFINE       In Summer                 29    +0.117     0.655        4 |    -0.226     0.621        4
AFFINE       Next Ten Minutes          67    +0.155     0.746        6 |    -0.080     0.522        4
AFFINE       Seasons of Love           25    +0.077     0.440       11 |    -0.005     0.640        6
STRUCTURAL   Popular                   51    +0.212     0.588        7 |    +0.001     0.588        8
```

**Stratum sizes within the cleared ten:** AFFINE 9 (Be Our Guest, Belle, Best
Part Of Me, Colors of the Wind, Domino, Free, In Summer, Next Ten Minutes,
Seasons of Love); STRUCTURAL 1 (Popular); REJECTED 0. The STRUCTURAL stratum
is below the pre-registered 4-song floor, so it is reported and **not read** --
the S-3-extension reading the pre-registration provided for is not available
from this corpus.

#### Part 2 — the declared sign guard against S-2

Pre-registered as: *"arm W's shared-line arithmetic is computed for every read
song, and if its median `delta` disagrees in sign with arm C's on 3 or more of
them, the read-off is suspended and goes to Ken."* Read songs are the AFFINE
nine.

```
same  Be Our Guest         C=+0.294  W=+0.010
DIFF  Belle                C=+0.149  W=-0.010
same  Best Part Of Me      C=+0.198  W=+0.018
DIFF  Colors of the Wind   C=+0.049  W=-0.442
same  Domino               C=-13.928  W=-13.404
DIFF  Free                 C=+0.126  W=-0.030
DIFF  In Summer            C=+0.117  W=-0.226
DIFF  Next Ten Minutes     C=+0.155  W=-0.080
DIFF  Seasons of Love      C=+0.077  W=-0.005
```

**Sign disagreements: 6 of 9, against a threshold of 3. The guard fires.** It
is computable before the sitting, and it has been computed before the sitting,
so it stops the eyeball as well as the read-off: no section has been watched
and no score exists. Per the pre-registration this goes to Ken and the
executor takes no verdict on it.

Recorded as raw fact and not as argument: on 5 of the 6 disagreeing songs both
medians are inside +/-0.5 s of zero, so the sign is being read off a quantity
smaller than the gate's own per-line tolerance; on Colors of the Wind arm W's
median is -0.442 s against arm C's +0.049 s. The guard as ratified counts signs
and does not carry a deadband. Whether that makes it a guard against S-2 or a
guard against noise is a rule question, and rule questions are Ken's.

#### Part 2 — the look-list (selector output, fixed before any render)

Selector as pre-registered: per song the three shared lines with the largest
`|delta|`, ties to the lower line id, only `|delta| > 0.5 s` qualifying, plus
every exclusive line. Taken on **arm C**, because arm C is the arm the sitting
watches; arm W's arithmetic is the guard above. **70 looks** against the
pre-registered ceiling of 71 (Colors of the Wind contributes two shared looks,
not three -- only two of its shared lines clear 0.5 s). Windows are
`[min(start) - 3 s, max(end)]` over both routes for a shared look and
`[start - 3 s, end]` for an exclusive one; identical in both versions of a
song, per the marker constraint.

```
idx  song                 stratum     kind         lid  winStart    winEnd
1    Be Our Guest         AFFINE      shared        68   174.190   187.961
2    Be Our Guest         AFFINE      shared        69   177.120   189.143
3    Be Our Guest         AFFINE      shared        70   181.150   190.824
4    Belle                AFFINE      shared         0    12.710    21.960
5    Belle                AFFINE      shared         4    31.319    41.075
6    Belle                AFFINE      shared        53   165.700   175.940
7    Belle                AFFINE      exclusive     81   250.179   253.359
8    Belle                AFFINE      exclusive     86   252.781   256.682
9    Belle                AFFINE      exclusive     87   253.702   257.103
10   Belle                AFFINE      exclusive     89   254.643   257.863
11   Belle                AFFINE      exclusive     93   256.365   259.785
12   Belle                AFFINE      exclusive     94   256.785   259.966
13   Belle                AFFINE      exclusive     95   256.966   261.447
14   Belle                AFFINE      exclusive     98   259.568   262.809
15   Belle                AFFINE      exclusive     99   259.809   263.529
16   Best Part Of Me      AFFINE      shared         3    27.490    34.800
17   Best Part Of Me      AFFINE      shared        29   167.467   180.700
18   Best Part Of Me      AFFINE      exclusive     32   188.837   192.718
19   Best Part Of Me      AFFINE      shared        34   202.375   216.320
20   Colors of the Wind   AFFINE      shared         2     2.340     7.600
21   Colors of the Wind   AFFINE      shared        36   174.840   201.940
22   Domino               AFFINE      exclusive     12    40.476    44.976
23   Domino               AFFINE      exclusive     16    50.553    54.314
24   Domino               AFFINE      exclusive     58   168.412   172.133
25   Domino               AFFINE      shared        63   179.554   215.406
26   Domino               AFFINE      shared        64   183.977   219.723
27   Domino               AFFINE      shared        65   185.419   221.326
28   Domino               AFFINE      exclusive     66   191.934   197.545
29   Free                 AFFINE      shared        19    81.800    88.518
30   Free                 AFFINE      exclusive     35   143.182   147.463
31   Free                 AFFINE      shared        36   148.340   167.860
32   Free                 AFFINE      shared        37   163.860   171.253
33   In Summer            AFFINE      exclusive      0     0.000     0.721
34   In Summer            AFFINE      shared         5     8.672    15.710
35   In Summer            AFFINE      shared         8    18.740    26.834
36   In Summer            AFFINE      exclusive     16    50.716    55.738
37   In Summer            AFFINE      shared        30    98.640   107.080
38   Next Ten Minutes     AFFINE      exclusive      7    44.498    48.179
39   Next Ten Minutes     AFFINE      shared        26   133.380   146.420
40   Next Ten Minutes     AFFINE      shared        50   261.360   274.221
41   Next Ten Minutes     AFFINE      shared        51   266.980   278.586
42   Next Ten Minutes     AFFINE      exclusive     63   328.657   332.178
43   Next Ten Minutes     AFFINE      exclusive     64   331.298   335.659
44   Next Ten Minutes     AFFINE      exclusive     65   335.906   339.366
45   Popular              STRUCTURAL  exclusive      0     0.000     0.120
46   Popular              STRUCTURAL  exclusive      1     0.000     1.442
47   Popular              STRUCTURAL  exclusive      2     0.000     2.102
48   Popular              STRUCTURAL  exclusive      3     0.000     2.202
49   Popular              STRUCTURAL  exclusive      4     0.000     2.783
50   Popular              STRUCTURAL  exclusive     35    97.097   100.558
51   Popular              STRUCTURAL  exclusive     37   102.922   107.864
52   Popular              STRUCTURAL  exclusive     51   147.519   152.041
53   Popular              STRUCTURAL  exclusive     52   149.061   152.542
54   Popular              STRUCTURAL  exclusive     53   149.542   153.102
55   Popular              STRUCTURAL  exclusive     54   150.182   153.923
56   Popular              STRUCTURAL  shared        59   159.570   187.181
57   Popular              STRUCTURAL  shared        60   166.170   193.366
58   Popular              STRUCTURAL  shared        61   167.430   197.212
59   Seasons of Love      AFFINE      shared         0    19.661    46.592
60   Seasons of Love      AFFINE      shared         1    25.997    52.425
61   Seasons of Love      AFFINE      shared         3    32.854    62.440
62   Seasons of Love      AFFINE      exclusive     14   113.843   118.204
63   Seasons of Love      AFFINE      exclusive     16   125.262   128.842
64   Seasons of Love      AFFINE      exclusive     26   163.113   167.294
65   Seasons of Love      AFFINE      exclusive     28   165.856   169.296
66   Seasons of Love      AFFINE      exclusive     29   166.356   170.617
67   Seasons of Love      AFFINE      exclusive     30   167.976   175.520
68   Seasons of Love      AFFINE      exclusive     31   172.741   177.983
69   Seasons of Love      AFFINE      exclusive     32   180.373   184.494
70   Seasons of Love      AFFINE      exclusive     33   181.975   188.238
```

Looks per song: Be Our Guest 3, Belle 12, Best Part Of Me 4, Colors of the
Wind 2, Domino 7, Free 4, In Summer 5, Next Ten Minutes 7, Popular 14, Seasons
of Love 12.

#### Stop

The pre-registered guard fired before any section was watched. The banner
generator is **not** built: it exists to present this look-list, and whether
this look-list gets watched at all is now Ken's ruling. The look-list is fixed
and saved (`m6/fb_looks.json`), so nothing about it can move afterwards
whichever way the ruling goes.

No gate changed. No verdict on S-1, on the S-3 extension, or on S-2. S-1
remains suspended and remains Ken's.

### 2026-09-08 — Second Fable judge round: how to buy the S-2 robustness (Ken commissioned; recommendation and executor verification recorded, no verdict)

**(Ken chose "buy the robustness" over ruling on the fired guard, then
commissioned a round on the design. Read-only round. Recorded as given, with
the executor's independent check of every load-bearing count. Nothing has been
built and no rule has changed: the sitting still needs a new pre-registration,
and two design choices in it are Ken's.)**

#### The recommendation, as given

**Buy the two-arm sitting, but only in the form that costs about what the
one-arm sitting would have cost:** one pass per look with all three versions
of a line on screen at once as three karaoke rows in sealed random order, not
three sequential passes over three files. Score with the ratified pairwise
statistics computed twice from the same observation (arm C vs joint, arm W vs
joint) and read off with M7-b's rule verbatim — margin of 3 required in
**both** arms. Selection: keep the fixed arm-C look-list whole and add arm W's
top three under the identical selector, additive only.

Reasoning offered for the shape: sequential passes cost roughly three times
the window time for a robustness statement the arithmetic already suggests
will be satisfied, because **the guard fired on medians and the medians are
noise, while the tails the selector actually picks are arm-robust**. A
three-way *statistic* would be new and unpre-registered, and would invite
reading arm C against arm W as S-2 evidence, which both M7-b and the fallback
forbid; a three-row *presentation* scored pairwise avoids that.

**Two things the round says Ken should settle before spending the time.**

1. **The ratified song-win rule is nearly one-sided on this population.** A
   song is won by the scaffold on `A >= 0 and B >= 0` with one positive, by
   the joint route symmetrically. Seven of the nine readable songs carry
   exclusive lines, and the ten were chosen dirt-free, so `B < 0` on those
   songs requires filler or cram. The joint route can therefore win only the
   two songs with no exclusive lines, plus any song whose exclusive lines all
   score zero. "Fails re-derivation" is close to unreachable and NO AWARD is
   the modal outcome. The round notes this was knowable from the pre-work's
   population table, which predates the ratified entry, so naming it now is
   not a data-driven adjustment; it calls it a design flaw of the ratified
   rule. Two legitimate responses, **Ken's choice**: keep the song-win rule as
   primary with the one-sidedness disclosed, or re-pre-register the two
   clauses as separate primary reads (a sign read on `A` across the nine, a
   sign read on `B` across the seven with exclusive lines, margin 3, both arms
   each) and demote the song-win rule to a declared secondary column. The
   round leans to the split and states the counter-argument itself: changing a
   ratified primary in the same entry that retires a fired guard is the
   pattern the discipline exists to prevent.
2. **Whether a scaffold win on nine dirt-free affine songs would change his
   S-1 ruling at all.** If library-level economics dominate, the S-1 product
   of this sitting is moot and only its dual-use product remains.

**The dual-use argument for spending the time at all.** The thirty exclusive
lines in the readable nine are the "fetched timing as one joint-matcher
candidate" question in miniature: lines the joint matcher could not place from
audio evidence, which the scaffold placed from the sidecar. Scored "sung lyric
shown when sung", sidecar-timed candidates would have filled the joint route's
holes; scored "wrong time" or "filler", they would not. So the sitting informs
the next build whether or not the route survives.

**What the round says the sitting still cannot deliver:** anything on S-2 (the
arm-vs-arm difference stays declared robustness); anything on the STRUCTURAL
class, which is where the route is dangerous; F2's economics, since it
measures the per-song delta on the easy set and M7-a already bounds the
fraction of the library that is sound; and nothing on the gate question, which
is a code fact and prior.

**Blinding, as recommended.** One file per song, three rows, row-to-version
assignment a per-song random permutation from a seed recorded in the
pre-registration commit, written to a sealed file not opened until the scores
are committed. Rows differ only in vertical position. Filenames and the mpv
command line carry no arm or route identifier. **And a declared blind-check
column**, because the round holds that the timing itself is a tell that cannot
be removed without changing what is being judged: after each song Ken writes
which row he believes is which, and agreement with the sealed mapping is
reported. If he is mostly right, the record says blinding was cosmetic and the
finding rests on the observational form of the question ("which row lights
when the singer starts this line") rather than on a blind Ken cannot have.

**Fallback presentation, pre-registered rather than chosen mid-sitting:** if
the stacked display is unreadable on the Popular dry run, revert to sequential
viewing of three files per song under the same sealed permutation, same
questions, three passes.

#### Executor verification

Reproduced independently (`m6/fb_verify.py` -> `m6/fb_verify.txt`), from the
same inputs the selector used. Every quantity below is a selection input or a
presentation fact, both outside the scored population.

- **Union counts, exact match.** Over the ten: arm C 29, arm W 30,
  intersection 23, union 36. Over the readable nine: 26 -> 33, i.e. **+7
  shared looks**, and the round named all seven correctly (Free 38, Be Our
  Guest 67, Best Part Of Me 33, Domino 60, Colors of the Wind 9 and 21, Next
  Ten Minutes 45). Exclusive 30. **Read looks 63 against 56 arm-C-only.**
  Popular contributes 14, unread.
- **Window time, exact match** on the arm-C list: 538 s (9.0 min) over the
  readable nine. One correction: the union adds 85 s, not "roughly a minute" —
  623 s (10.4 min) per pass.
- **The tails are arm-robust.** Over the readable nine's 33 union looks the two
  arms agree in sign on **29** and both exceed the selector's own threshold on
  **28**. The round quoted 30 of 36, which is the same statistic over all ten;
  both are true, and the nine is the read population.
- **Seven of the nine readable songs carry exclusive lines**, and the two that
  do not are Be Our Guest and Colors of the Wind. The one-sidedness argument
  therefore stands as a reading of the ratified rule.
- **Style block identical across all three row sources**, checked on Belle,
  Seasons of Love and Domino: the production render and both arm renders share
  a byte-identical header. So there is no style tell to remove.
- **The timing tell is real**, direction confirmed on the same three songs:
  arm C's median karaoke sweep is 14-18 cs against 30-38 cs for arm W and
  32-44 cs for the production render, with roughly twice the adjacent-tag
  count. The round's exact percentages were a different statistic from mine,
  but the conclusion holds and the blind-check column is warranted.
- **The excluded render.** The `karaoke/<stem>.scaffold.ass` in the songs
  directory is stamped 2026-09-04 12:56:34, before either arm run began, so it
  is neither arm's output and must not be used as a row source. Confirmed; its
  provenance is still unestablished.

**One claim corrected.** The round described Popular's five front looks as
"five lines pinned at 0.000 s". In arm C exactly one line starts at 0.000; the
five are crammed into the first 2.8 s, consecutive and near-zero width. Both
descriptions point at the same front cram, and Part 1's own front-clamp count
for Popular is 1, so the corrected figure is the consistent one. The earlier
record's "5 at 0.0" was arm W, a different arm.

**Flagged unverified by the round, and still unverified.** Whether libass and
mpv render three stacked karaoke rows correctly under explicit positioning.
This is the single largest risk in the recommendation: the whole
cost-neutrality argument rests on it, and if it fails the sitting reverts to
three passes.

#### Standing

No gate changed. No verdict on S-1, S-2 or S-3. The fired guard has been
neither re-scored nor re-specified. The sitting has no ratified rules yet: the
new pre-registration is owed once Ken settles the song-win-versus-split-reads
question, and it must be ratified before any file is generated.

### 2026-09-08 — Route CLOSED (Ken) — S-1 withdrawn, work ceased; S-3 extension and M6-d moot; the Fable assessment recorded as given

**(Judge session, read-only, no code, no plan edits until this entry.
Commissioned by Ken's question rather than by a GATE: "given the difficulty
and the ambiguity we are having in validating the line timing scaffold
route, do you recommend continuing to work on it? is it likely to perform
much better than the joint route? would our efforts be better off
implementing the planned improvements for the joint route?" Fable read the
Build-session transcript since 2026-09-04, this log from M6 through the
second judge round, `PROGRAM.md`, `route-no-timing.md`, and the warp gate,
fill and fetch code. Transcript:
`C:/Users/TsangK/.claude/projects/c--temp-Github-pikaraoke/2e78ce4d-ba7c-4695-9899-733d01031abe.jsonl`.
Ken ruled in the same session; the ruling and the docs it changes are
listed at the end.)**

#### The assessment, as given

**Recommendation: stop working the line route as a separate per-song
route. Do not spend the stacked-row sitting on S-1. Move to the joint
route's planned improvements, and bring the line route's one real asset,
fetched line timing, back as a per-line source inside the joint matcher
rather than as a route with its own gate.**

Why it will not perform much better than the joint route:

- Where the sidecar is right, the timing is good. The R-1 eyeball found 6
  of 10 usable and Colors of the Wind beating production; M7-a's certified
  songs sit within a fraction of a second. The mechanism was never in
  doubt.
- It is right for a minority of songs: M7-a certified 4 of 17 library-wide
  and 2 of 10 in the corpus, with a different edit of the song as the
  dominant failure.
- Nothing can tell the two apart. R-4 produced zero discriminative
  statistics for word timing. The warp gate accepted 5 of the 6
  edit-mismatched corpus songs, for the verified reason that its fit
  population never sees the sections the video does not sing and the
  duration clamp crams them instead of rejecting the source.
- On a wrong source this route is worse than the joint route, because it
  has no drop branch: every sheet line renders somewhere. The joint route
  hides what it cannot place. Ken's M6-d observations said the same: both
  scaffold arms chaotic on Be Our Guest, wrong lines through Hakuna
  Matata's dialogue, production's dialogue suppression better.
- Net value is the gain on sound songs times the fraction sound, minus the
  damage on unsound songs the gate lets through; with the gate as it
  stands the damage term wins. That is structural, not bad luck.

Why the validation kept stalling: every comparison was decided by the two
routes' contracts rather than by timing, and every gate tried was
per-song. Per-song verification failed at R-4 and at the warp gate. The
second judge round had already said what the stacked-row sitting could
not deliver (nothing on S-2, nothing on the STRUCTURAL class, nothing on
F2's economics) and that its song-win rule was nearly one-sided, so the
modal outcome was NO AWARD. What remained was the sitting, its
pre-registration and libass test, an S-1 ruling, M6-d re-posed for S-2, a
gate redesign M4 was parked for, the F2 build and GATE V2 — two or three
more billed read-offs for a route with zero production miles.

What to do instead, as given: (1) joint plan Phase 1.1 — **corrected in
the same session, see below: do not delete the fill**; (2) Phase 2a then
GATE J1/J2, the one remaining item in either plan that is a genuine
mechanism selection, with NO-GO an acceptable outcome that costs one
probe; (3) design the sidecar-as-source build once J1 has picked the
aligner — the joint matcher already sums align, transcribe and ytasr
candidates into one pool, a wrong-edit line loses to audio evidence, a
right line fills a hole, no per-song gate, no F2, no S-1; (4) Phase 3
knob re-tune and GATE T. The joint route ships today, so every step lands
for every non-SRT song, a larger population than songs with a sound
sidecar. Two rulings were Ken's with no Fable needed: the S-3 extension
as a code fact, and S-1 withdrawn or parked with the route re-scoped to
"line timing as a joint-matcher witness".

#### The LRCLIB fill: why refit Phase 1.1 existed, and why it is cancelled

Ken asked for the rationale. As written in `route-no-timing.md`: under the
target ladder a song with LRCLIB line timing would take its own route, so
anything still arriving at the joint catch-all with an `.lrc` had by
construction failed or lacked that route, making the `.lrc` a
wrong-version text and the fill harmful. Persistence stayed because the
`.lrc` is the held-out tuning reference and was F2's line source.

That rationale is conditional on F2 existing. With the line route
withdrawn, the fill is the only door through which line timing reaches
production, and it is the shipped precursor of the recommended design:
matcher-unplaced lines only, cue time plus a constant offset, per-song
offset-consistency and unity-slope gates, per-line collision rejection, a
placed line never moved, 16 good / 0 bad on the 17-song corpus after
Ken's GATE L2 eyeball (`plans/completed/lrclib-fill-absence-study.md`;
history: ruled out of production 2026-07-01, re-opened 2026-07-06 for two
narrow uses, the absence-evidence use descoped, warped fill times
rejected at GATE L2 so the fit is a gate only, DP-candidate use still
banned for circularity with the tuning reference). **Phase 1.1 is
cancelled; the fill is kept and is to be widened to the sidecar sources
(`route-no-timing.md`, Phase 5).** Two caveats carried: the fill's gate
shares the warp gate's blind spot (it fits on placed lines only) but the
damage is capped because it never overrides a placed line; and entering
the DP as a candidate rather than a post-pass is a ruling Ken would have
to re-open.

#### The S-3 extension: analysis recorded, ruling moot

Ken asked for help deciding it before ruling on the route. Recorded so
nobody re-derives it.

What was on file: S-3 as ruled 2026-07-19 says the cram is the
unacceptable harm and hiding lines the lesser one, and was never built (a
warp failure still densifies in the harness). The cram also appears on
songs the gate accepts (Bloodstream 38 lines on one timestamp, HUNTR/X
20, Popular pinned at the front). The first judge round found the
mechanism and the executor verified it: the gate fits only lines both
source and audio place, it is a median so rejects only when more than
half the sung lines are off, and lines warping past either end are
clamped and stack — "warp-accepted" never meant "same edit". The shape
diagnostic labelled 3 of 17 STRUCTURAL and the gate accepted all three;
of the 6 songs M7-a attributed to a different edit the gate rejected 1
and the diagnostic would catch 2 of the other 5 (Be Our Guest, Best Part
of Me, Man Out of You and Domino are wrong edits that look affine). The
duration signal is not clean either: a threshold tight enough to catch
Domino also rejects Colors of the Wind. The measurement path was closed
(one STRUCTURAL song in the cleared ten, below the floor).

Options put to Ken: (1) affirm the principle, record the code fact, build
nothing — recommended; (2) affirm and promote the diagnostic's clamp and
off-run tests into the warp gate — safe, partial, only worth it if F2 is
built; (3) decline the extension — contradicts S-3's own rationale; (4)
let it lapse with the route, into which (1) collapses if S-1 is
withdrawn. The recommendation's core: a clean per-song structure test is
not constructible from what is on disk, which is the conclusion R-4
reached for word timing, and the strongest argument for timing entering
per line and losing per line.

**Ruling (Ken, 2026-09-08): moot.** "yes, I am going to cease work on the
scaffold route so this decision should be moot." The principle survives
as a design constraint on the fill: never fill past the media ends, never
over an audio-placed line.

#### Ruling (Ken, 2026-09-08)

**Work on the scaffold/line route ceases. S-1 is withdrawn. F2 is not
built. The S-3 extension and M6-d are moot. The stacked-row sitting is
not run. A new session starts on the joint matcher.**

What survives, and where:

- The fetched sidecar (`lyrics/<stem>.timing.json`) stays written at add
  time and stays inert in routing. Its designed future is a second source
  for the joint route's gated fill — `route-no-timing.md`, Phase 5,
  design owed after GATE J1.
- The fallback's fixed look-list (`m6/fb_looks.json`, Build-session
  scratchpad) and both arm dumps stay as optional evidence for Phase 5:
  the 30 scaffold-only lines on the nine readable songs are that
  question in miniature. Viewing them needs no pre-registration change.
- M7-a's certification table is the library-economics bound (4 of 17
  sound) that any future per-song proposal must beat.
- The lyric-parser fix (`2516ca8`) stands on its own; it is
  route-independent.
- GATE L (Phase 4 above) re-homes to the joint route's aligner.
- The warp gate's blind spot and the shape diagnostic stay on record
  here as the reason no per-song admission test is to be reused.

Docs changed by this ruling, one commit: this file's status block and
this entry; `PROGRAM.md` (header, Part 2 target routing and tables, open
decisions, execution order, ownership table); `route-no-timing.md`
(START HERE block, context, phase order, 1.1 cancelled, 1.2 done, Phase 5
added, out-of-scope, Results log); `ctc-sync-engine.md` (licensing table,
F2, Appendix A precedence 3 and fill sentence, Results log);
`shared-aligner-form.md` (M6-d moot). **No code changed. No constant
moved. No GATE J1/J2 rule changed.**

Not decided by this ruling: GATE J1/J2; whether the sidecar may enter the
DP as a candidate (the ban stands until Ken re-opens it); Phase 5's
design and gate; the Mandarin corpus for GATE L.
