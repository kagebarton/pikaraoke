Model: Claude Fable 5 (design); executors per the phase table in `plans/PROGRAM.md`

# Route: line timing (LRCLIB / Musixmatch-line / NetEase, + demoted richsync)

**Ladder rung 2, foreign-clock half.** A provider gives line-level
timings on its own clock, so the cues cannot be trusted as-is: they enter
as a **warped scaffold** (`warp_scaffold_cues`) driving the same windowed
aligner the SRT route uses. Uploader-SRT cues are the trusted-as-is half
of rung 2 and live in `plans/route-srt.md`.

**Status: licensed, NOT YET BUILT.** GATE S ruled S-1 = GO, S-2 = CTC as
the section aligner for this path, S-5 = scaffold-first. The production
build is **F2** in `plans/ctc-sync-engine.md` — a carve-out that is
zero-regret to build at any point. Until F2 lands, a song with line
timing but no SRT still routes to the joint matcher
(`plans/route-no-timing.md`); LRCLIB participates only as the gated
post-pass fill, never as a routing tier.

**Blocking caveat added 2026-09-04 — do not start F2 without reading
this.** S-2's genius arm (the ruling that selected CTC for this path) is
the one **unwitnessed selection** in the live ruling set: it rested on
four criteria, two of them overlap-based, and Ken's next-day S-C eyeball
reframed what a falling overlap number means — CTC may be under-reporting
a second voice rather than mis-timing it. **M6** re-reads that arm and is
sequenced after M1-M3 but *before* any F2 build. See the eyeball-
provenance audit in `plans/shared-aligner-form.md`.

**Also inherits the demoted word sidecars** from
`plans/route-word-timing.md`: their `ts`/`te` improve scaffold ends even
though the word route itself is NO-GO.

**Open work:** M6 (blocks F2), S-E (Phase 3's unrun optional arm), and
GATE L below. *M6's read-off rules were pre-registered and ratified
2026-09-04 — see the entry at the end of this log.*

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
