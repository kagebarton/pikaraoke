# YouTube auto-caption (ASR) timing prior

Model: Claude Opus 4.8

## Context

For a given YouTube video we currently draw timing from four sources: stable-ts
forced-alignment, stable-ts transcription, the uploader's **manual** SRT
(`srt_prior`), and an **LRCLIB** `.lrc` (`lrclib` prior). One free source is
deliberately left on the table: YouTube's **auto-generated (ASR) captions**.

[youtube_dl.py:244-247](pikaraoke/lib/youtube_dl.py#L244-L247) excludes
auto-captions — correctly, **for lyric text** (ASR mis-hears lyrics over backing
music). But that rationale does not extend to **timing**. Auto-captions are:

- **Same-clock** as the video (unlike LRCLIB's different master), so there is no
  sync ambiguity — only a small constant ASR emission lag.
- **Word-level**, carrying per-word timestamps (LRCLIB is line-level).

So for a song whose authoritative lyrics came from Genius (txt), auto-captions
are a strictly better timing prior than LRCLIB when present. This plan wires them
in as a prior on the Genius/txt path, mirroring the LRCLIB integration, and
**reuses the existing `apply_srt_prior` machinery** (offset fit + MAD gate +
snap/fill) verbatim.

### Corpus validation (2026-06-26, 15 genius-cohort songs)

Confirmed the premise on the real corpus before building:

- **Availability:** 10/15 genius songs have an English auto-caption with true
  word-level timing (per-word `tOffsetMs` in json3). The other 5 have none and
  fall back to LRCLIB unchanged — the feature is strictly additive.
- **Same-clock:** median ASR-vs-(pass-1 audio) |offset| = **0.34s** (the ASR
  emission lag), median MAD = **0.33s**. LRCLIB-vs-audio median |offset| =
  **13.2s** (arbitrary, different master) with MAD 0.86s. ASR is same-clock AND
  tighter than LRCLIB.
- **Engage rate:** the prior's MAD ≤ 0.75 gate would ENGAGE on 8/10; the 2 that
  bail (Hakuna Matata — heavy repetition; Bloodstream — borderline) bail
  *correctly*, never degrading the song.
- **Beats LRCLIB** on several songs where LRCLIB is wrong-sync (Defying Gravity
  LRC MAD 11.98 → ASR 0.45; Mulan LRC offset +31.6s → ASR 0.17).
- **Coverage is partial** on long songs (ASR drops words during dense harmony:
  Belle 31/102 lines, Be Our Guest 35/77) but fills 13 lines audio missed across
  the cohort — fine for a repair/fill prior.
- **srt-origin out of scope confirmed:** captioned videos expose only a
  line-level, manual-derived "auto" track (0 word-level events) — no independent
  word-level ASR to gain.

### The `[Music]` degeneracy problem

Music-video auto-captions often degenerate to tagging instrumental stretches as
`[Music]` / `♪` / `[Applause]` instead of transcribing. Such a caption carries
almost no real word timing and must not be adopted. Handled at two levels:

1. **Token filter** (per segment): drop bracket/paren/musical-note-only segments
   while parsing — reuse the same regexes `genius_lyrics.clean_srt_line` already
   applies (`_BRACKET_CONTENT_RE`, `_PAREN_CONTENT_RE`, `_MUSICAL_NOTE_RE`).
2. **Density gate** (whole caption): after filtering, if real words-per-minute
   over media duration falls below a floor (reuse the regen tool's
   `MIN_CAPTION_WPM = 15.0` value), reject the caption entirely and fall through
   to LRCLIB / audio-only. This is exactly the case the user described.

## Scope (v1)

- **Genius/txt-origin songs only** — sibling to the LRCLIB prior, where it
  delivers the most. The manual-SRT path is untouched (it already has same-clock
  line timing). Transcribe-origin and manually-added library files are N/A.
- **Prior, not joint candidate.** Reduce the ASR word stream to per-line cue
  spans and feed `apply_srt_prior(..., source="ytasr")`. Using the word-level
  timing directly (3rd joint candidate / dropping the whisper transcribe pass)
  is a deliberate future step, noted but out of scope.
- **Precedence:** manual-SRT prior (srt-origin, existing) > **YTASR** > LRCLIB.
  On the Genius branch, try YTASR first; adopt it and skip the LRCLIB fetch when
  it passes the gates, else fall back to LRCLIB as today.
- **No manual-caption tier on the Genius path — by UI invariant.** The search
  preview flow routes a video *with* manual captions to SRT-primary mode and
  never auto-runs a Genius search
  ([search.html:876-882](pikaraoke/templates/search.html#L876-L882);
  `srt_available` counts manual subs only,
  [youtube_dl.py:244-247](pikaraoke/lib/youtube_dl.py#L244-L247)). So
  genius-origin ⟹ no manual caption (confirmed: every corpus genius song has
  `srt_present=False`), and a manual-mirrored "fake ASR" track cannot occur here.
  On the Genius path the fetched auto track is therefore *real word-level ASR or
  nothing* — making "Word-ASR > LRCLIB" complete, not a simplification. The
  word-seg-fraction gate's real job here is degeneracy detection (`[Music]`/
  sparse); manual-mirrored rejection is just safety for the rare manual
  "More options → Genius on a captioned video" override.

## Changes

### 1. Fetch — `pikaraoke/lib/youtube_dl.py`

Add `download_auto_en_subs(video_url, dest_dir, stem) -> str | None`, mirroring
`download_manual_en_subs` ([youtube_dl.py:323](pikaraoke/lib/youtube_dl.py#L323))
+ `_select_en_srt` ([youtube_dl.py:293](pikaraoke/lib/youtube_dl.py#L293)) but:

- `--write-auto-subs` (not `--write-subs`), `--sub-langs "en.*"`,
  **`--sub-format json3`**, `--skip-download`, and **no `--convert-subs`**
  (converting to SRT collapses word timing and creates the rolling-window
  duplicate mess).
- **Select the real ASR track by content, not name** (a `_select_asr_track`
  helper paralleling `_select_en_srt`): parse every downloaded `<stem>.<lang>.json3`,
  compute its word-seg fraction, pick the max; if `>= WORD_SEG_MIN_FRAC` promote
  it to the canonical `subtitles/<stem>.en.asr.json3` and delete the rest; else
  delete all and return `None`. Naming-agnostic — we don't assume the ASR is
  `en` vs `en-orig` vs anything else.
- Returns the canonical json3 path, or `None` on no-real-ASR / failure / timeout.

Why content-based selection (validated on corpus): `en.*` pulls every English
auto track in one call — typically `en`, `en-orig`, `en-en` (translations to
other languages are named by their target lang, so the glob doesn't drag them
in). Among them only the *real* ASR is word-level:

- `TZ0pXUb5jVU` (has manual **and** real ASR): `en-orig`=77%, `en`=77%,
  `en-en`=0% (a manual-derived "English from English" track). Selector picks the
  77% track.
- `1OwfYjemrYw` (manual only): `en` is vtt-only (manual mirrored, line-level),
  `en-en`=0%. Best 0% → `None` → falls back to LRCLIB.

The track *name* lies (BSB's "auto" `en` is the manual mirrored back); the
word-seg fraction does not. Real ASR runs 73–82% across the genius cohort,
manual/manual-mirrored/translation is 0% — so the `>= 0.5` cut is unambiguous,
and it makes the genius-only scope self-enforcing. (Edge: a track may be
vtt-only; real ASR reliably offers json3 in the corpus, so json3-only parsing is
fine for v1 — vtt-only tracks seen are all manual-mirrored line-level.)

The `.en.asr.json3` suffix is distinct from `.en.srt`/`.srt`, so the existing
`_find_youtube_srt_path` / `_should_write_srt` discovery never mistakes it for a
manual caption.

### 2. Parse + map — new `pikaraoke/lib/ytasr.py`

Mirrors `lrclib.py`'s role (parse → quality-gate → derive cue spans):

- `parse_json3(text) -> tuple[list[dict], float]` — flatten `events[].segs[]`
  into a `[{word, start, end}]` stream plus the **word-seg fraction** (segs with
  `tOffsetMs` / non-empty segs — the real-ASR discriminator). Word
  `start = (tStartMs + tOffsetMs)/1000`; `end` = next word's start (clamped).
  Skip whitespace-only segs; drop segments empty after the
  bracket/paren/musical-note filter; dedupe consecutive identical `(text, start)`
  tokens (auto-caption roll-up artifact).
- `WORD_SEG_MIN_FRAC = 0.5` + `MIN_CAPTION_WPM = 15.0` +
  `is_usable(words, word_seg_frac, media_dur) -> bool` — two gates: reject a
  manual-mirrored/line-level track (`word_seg_frac < 0.5`; measured separation is
  73–82% real ASR vs 0% manual), and reject the `[Music]`-only degeneracy
  (`wpm < 15`, the case the user flagged). Either failure → fall back to LRCLIB.
  An unknown media duration is rejected too — the degeneracy gate can't run
  without it, so bail rather than adopt unchecked.
- `cue_spans_for_lines(words, align_lines) -> dict[int, tuple] | None` — the
  YTASR analog of `lrclib.cue_spans_for_lines`. **Per-line fuzzy candidate
  search**, NOT a single whole-song align: reuse
  `candidate_match.find_candidates`
  ([candidate_match.py:64](pikaraoke/lib/candidate_match.py#L64)) on the ASR
  token stream, pick each line's best-scoring candidate, then keep a
  greedy/monotonic subset (start index never moves backward); each kept candidate's span is
  `(words[start].start, words[end-1].end)`. Lines with no candidate get no cue
  (the prior leaves/fills them). **Validated:** a single whole-song `_walk_align`
  collapses on long/repetitive songs (Belle mapped 1/102 lines); the per-line
  `find_candidates` approach recovered it to 31/102 at MAD 0.17. `max_edit_ratio`
  ≈ 0.34 worked well against ASR noise.

### 3. Fetch wiring — `pikaraoke/pipeline/stages/lyrics_fetch.py`

On the Genius branch (Branch a,
[lyrics_fetch.py:91](pikaraoke/pipeline/stages/lyrics_fetch.py#L91)), replace the
direct `_fetch_lrclib_prior` call with a `_fetch_timing_prior` that:

1. Probes media duration once (reused by both priors).
2. If `config.joint_ytasr_prior`: reuse an existing `*.en.asr.json3`, else
   download via `download_auto_en_subs` (watch URL built from `yt_id`). Parse,
   filter, density-gate. If usable, stash
   `ctx.artifacts["ytasr"] = {asr_file, n_words, wpm}` and **return** (skip
   LRCLIB).
3. Otherwise fall through to the existing `_fetch_lrclib_prior`.

Never raises — any failure logs and degrades to LRCLIB / audio (matches the
existing best-effort prior philosophy).

### 4. Apply wiring — `pikaraoke/pipeline/stages/lyric_align.py`

In `_run_joint` precedence chain
([lyric_align.py:528-554](pikaraoke/pipeline/stages/lyric_align.py#L528-L554)),
insert a YTASR branch before the LRCLIB `elif`:

```
if cue_spans is not None and joint_srt_prior:            # manual srt
    ...
elif joint_ytasr_prior and ctx.artifacts.get("ytasr"):  # NEW
    line_objects = self._apply_ytasr_prior(...)
elif joint_lrclib_prior and ctx.artifacts.get("lrclib"):
    ...
```

`_apply_ytasr_prior` mirrors `_apply_lrclib_prior`
([lyric_align.py:557](pikaraoke/pipeline/stages/lyric_align.py#L557)): parse the
persisted json3, `ytasr.cue_spans_for_lines(...)`, call
`apply_srt_prior(..., source="ytasr")`, stash
`joint_stats["ytasr_prior"]` with inlined `cue_spans_by_line` for offline replay.
Degrades to audio on any failure.

Also add `lyrics["ytasr"]` to the debug-capture lyrics dict alongside the
existing `lrclib`/`genius` refs
([lyric_align.py:238-245](pikaraoke/pipeline/stages/lyric_align.py#L238-L245)),
and add `joint_ytasr_prior` to the `config_snapshot`.

### 5. Config — `pikaraoke/pipeline/config.py`

Add `joint_ytasr_prior: bool = True` beside `joint_lrclib_prior`
([config.py:270](pikaraoke/pipeline/config.py#L270)) with a comment noting it is
preferred over LRCLIB (same-clock) and gated by the density floor.

`apply_srt_prior` already takes a `source` parameter
([srt_prior.py:84](pikaraoke/lib/srt_prior.py#L84)) — no change needed there.

### 6. Bundle schema bump — `pikaraoke/lib/alignment_capture.py`

Bump `SCHEMA_VERSION` 6 → **7** with a v7 doc block describing the additive
fields (`lyrics.ytasr`, `joint_stats.ytasr_prior` with `cue_spans_by_line`,
`config.joint_ytasr_prior`). The fields are additive, but this follows the v5
precedent of a **milestone bump for a run-affecting prior** — and it makes the
regen tool treat existing v6 bundles as stale so a default (non-`--reset`) run
reprocesses the whole corpus.

### 7. Regen tool — `scripts/regen_alignment_bundles.py`

Required for the corpus reprocess to actually exercise YTASR. The default reuse
path for genius songs ([_reuse_plan:289-303](scripts/regen_alignment_bundles.py#L289-L303))
builds a `seed` plan that reuses bundled lyrics + the on-disk `.lrc` and **never
runs `LyricsFetchStage`** — so without a hook, a default regen reprocesses but
stays on LRCLIB.

Add a YTASR fetch+seed step parallel to `execute_fetches`
([regen:453](scripts/regen_alignment_bundles.py#L453)) and the `.lrc` reuse: for
each genius-origin seed job with a yt_id (gated by `config.joint_ytasr_prior`),
ensure `subtitles/<stem>.en.asr.json3` exists (reuse if on disk; else
`download_auto_en_subs` once — offline-safe like the `.lrc`), run the
word-seg-fraction + wpm gates, and on success add `seed["ytasr"]` (the json3 ref).
`SeedArtifactsStage` already injects the seed dict, so the align stage's elif
chain prefers the seeded `ytasr` over the seeded `lrclib` with no further change.
Real-run-only (after the backup), like `execute_fetches`.

## Tests

- **`tests/unit/test_ytasr.py`** (new): `parse_json3` word extraction + offset
  math; `[Music]`/`♪`/`(applause)` segments filtered; a `[Music]`-only caption
  fails `is_usable`; a dense caption passes; `cue_spans_for_lines` maps lines via
  `_walk_align` and leaves unmatched lines uncued.
- **`tests/unit/test_youtube_dl.py`**: `download_auto_en_subs` builds the
  `--write-auto-subs --sub-format json3` command and returns the json3 path /
  `None` (mirror the `download_manual_en_subs` tests at
  [test_youtube_dl.py:394](tests/unit/test_youtube_dl.py#L394)).
- **`tests/unit/test_lyrics_fetch.py`**: usable ASR adopted → `ytasr` artifact
  set, LRCLIB skipped; degenerate/absent ASR → falls back to LRCLIB.
- **`tests/unit/test_lyric_align.py`**: YTASR branch chosen over LRCLIB when both
  artifacts present; prior bail keeps audio placements; capture bundle carries
  `ytasr_prior`.
- **`tests/unit/test_regen_alignment_bundles.py`**: a genius seed job with a
  usable on-disk/downloaded `.en.asr.json3` gets `seed["ytasr"]` (and the align
  stage would prefer it over `lrclib`); degenerate/absent ASR leaves the seed on
  LRCLIB. Mirror the existing caption-gate tests
  ([test_regen_alignment_bundles.py:300](tests/unit/test_regen_alignment_bundles.py#L300)).

All external I/O (yt-dlp subprocess, file reads) mocked per the testing
guidance; real `apply_srt_prior`.

## Verification

1. `python -m pytest tests/unit/test_ytasr.py tests/unit/test_youtube_dl.py
   tests/unit/test_lyrics_fetch.py tests/unit/test_lyric_align.py`
2. End-to-end on a Genius-origin song that has YouTube auto-captions:
   process it, confirm `subtitles/<stem>.en.asr.json3` is written, the log shows
   `YTASR prior applied: offset=... N snapped, M filled`, and the alignment-debug
   bundle contains `joint_stats.ytasr_prior` with `cue_spans_by_line`.
3. Negative: a music video whose auto-captions are mostly `[Music]` — confirm the
   density gate rejects it (`too sparse ... discarding` log) and the song falls
   back to LRCLIB / audio unchanged.
4. Offline reuse: re-run with the `.en.asr.json3` already on disk — confirm no
   network call and identical placements.
5. Corpus apply (the intended rollout): run the regen tool (default mode — the
   v7 bump makes all v6 bundles stale) over `D:\shared\pikaraoke-songs`; confirm
   genius songs with ASR pick up `ytasr_prior` (and the 8/10 corpus engage rate
   roughly holds), genius songs without ASR stay on LRCLIB, and srt-origin songs
   are untouched.

## Out of scope (future)

- YTASR as a 3rd joint candidate / replacing the whisper transcribe pass for
  songs that have auto-captions (the higher-quality, larger change).
- A manual-caption line-level prior on the **genius path** for the rare manual
  override (captioned video where the user drilled into "More options → Genius").
  Today that song uses LRCLIB; ideally it would use its same-clock manual caption
  as a line prior above LRCLIB. Deferred: a non-case under default UI routing,
  and must gate on a *real* caption (`youtube_srt_present`), never the
  possibly-pipeline-generated on-disk `<stem>.srt` (circular).
- Extending the YTASR (word-level) prior to manual-SRT-origin songs for finer
  word timing than the line-level SRT prior gives.
- Other `syncedlyrics` providers (Musixmatch word-level, NetEase).
