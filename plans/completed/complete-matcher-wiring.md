# Complete matcher wiring: cue_align (SRT) + YTASR (3rd source)

Model: Claude Opus 4.8

## Problem

A `high`-effort review of the integration range (`da1ce02a^..HEAD`) found that
**both integrated paths are present as code but neither fires in the live
pipeline**:

- **YTASR 3rd source is dead.** The read-side is fully wired
  (`lyrics_fetch._resolve_ytasr` -> `ctx.artifacts["ytasr"]` ->
  `lyric_align._ytasr_words` -> joint matcher), but nothing writes the input
  `subtitles/<stem>.en.asr.json3`. `download_auto_en_subs` (its only writer) has
  zero production callers, so `_resolve_ytasr` always early-returns and every
  song runs plain two-source.
- **cue_align is unwired.** `LyricAlignStage` aligns SRT songs with the joint
  matcher and discards the SRT cue_spans (`lyric_align.py:100`, the `_`).
  `cue_align.py` is imported only by tests; its orchestration lived in
  `pathed_align`'s `scripts/cue_align_song.py::align_with_cues`, which was not
  ported.

## Decisions (confirmed)

1. **Replace for SRT** — SRT songs route through cue_align only; the joint
   matcher becomes txt/genius-only. Matches the roadmap "cue-align for SRT,
   3-source for non-SRT".
2. **Share the de-reverb gate** — the SRT cue route runs the same
   transcribe-first de-reverb gate before aligning.
3. Plan first, then implement.

## Fix 1 — YTASR live fetch (small)

`download_auto_en_subs` already exists and works; it just needs a live caller.

- **Hook:** `download_manager.py`, in the success branch right after
  `song_path` is resolved and `_move_downloaded_subtitle(song_path)` runs
  (~line 279). Add a best-effort call:
  `download_auto_en_subs(video_url, str(song_path.parent / "subtitles"), song_path.stem)`.
- **Best-effort:** wrap so any failure (no auto-captions, network error) is
  logged and swallowed — it must never fail or delay the download. The json3
  lands at `subtitles/<stem>.en.asr.json3`, exactly where `_resolve_ytasr`
  looks.
- Fetched for **every** download (we don't know at download time whether the
  user will pick Genius or SRT); `_resolve_ytasr` still only consumes it on the
  Genius branch, unchanged.
- **Outward-facing note:** this adds a second yt-dlp invocation per download
  (extra network call + one small file on disk). Acceptable per the design
  ("fetched at download time").

## Fix 2 — cue_align live route (larger)

Port `align_with_cues` into `LyricAlignStage` as `_run_cue_align`, reusing the
stage's existing infra instead of the script's standalone helpers.

### Routing in `run()`

`_load_lyrics` already returns `cue_spans` (populated for `.srt`, `None` for
`.txt`). Change the discard at line 100 to branch:

```
lyrics_lines, align_lines, cue_spans = self._load_lyrics(lyrics_path)
if cue_spans:
    line_objects = self._run_cue_align(ctx, vocal_wav, lyrics_lines, align_lines, cue_spans)
    capture_method_used = "cue_align"
else:
    ... existing _run_joint ...
    capture_method_used = "joint"
```

- `lyric_method` label becomes `"srt+cue_align"` for SRT songs (was
  `"srt+joint"`), `"genius+joint"` unchanged.
- Empty/degenerate SRT (all lines dropped in cleaning -> `cue_spans == []`):
  guard falls through to the joint/transcribe path rather than raising
  `align_with_cues`'s `ValueError`. In practice SRT lines always carry spans,
  so this is just a safety net.

### `_run_cue_align(ctx, vocal_wav, display_lines, align_lines, cue_spans)`

1. **Shared de-reverb gate:** `vocal_wav, _tw, dereverb_stats = self._dereverb_gate(ctx, vocal_wav)`.
   The cue route ignores the transcribe words (it is cue-driven) but adopts the
   dry stem when the gate fires.
2. `duration = _wav_duration(vocal_wav)`.
3. `align_pass(spans)`:
   - `sections = segment_by_gaps(spans, duration=duration)` (module defaults
     `SECTION_GAP_S=1.5`/`SECTION_PAD_S=0.75` already match the old driver
     overrides — no override args needed).
   - per section: `_cue_align_slice(ctx, vocal_wav, t0, t1, sub_text)` ->
     `split_section_to_lines(section, words, display_lines, align_lines, spans)`.
4. `offset = fit_offset(line_objects, cue_spans, align_lines)`; if
   `abs(offset) > SECTION_PAD_S`, rebuild shifted spans and re-run `align_pass`.
5. `repace_bad_lines(line_objects, spans, display_lines, align_lines, duration=duration, realign=realign_line)`
   where `realign_line(lid, t0, t1)` runs a narrow per-line slice-align over the
   padded cue window (returns `None` for a \<0.2s window).
6. Return `line_objects`.

### Reuse (do NOT copy the script helpers)

- **Slicing + align:** the stage already has this exact pattern in
  `_realign_one_span` (ffmpeg `-ss/-to` slice via `run_ffmpeg`, `_model_call`
  with `Phase.ALIGN`, `worker.align_refine`, shift words by `t0`, degrade to
  `None`/`[]` on failure, `finally: unlink`). Extract a shared
  `_slice_align(ctx, vocal_wav, t0, t1, text, label) -> list[dict]` helper and
  have both `_realign_one_span` and `_run_cue_align`'s `align_pass`/`realign_line`
  call it. This avoids the script's bare `subprocess.run`/`_ffmpeg` and gets
  cancellation + Phase scoping for free.
- **Duration:** reuse the stage's `_wav_duration`.
- **ASS render:** already the stage's `_generate_ass` (the script borrowed it).
- **No 16 kHz pre-downsample:** the joint route passes the vocal WAV straight to
  `align_refine`; keep the cue route consistent (align_refine handles decode).
  Drop the script's `-ac 1 -ar 16000` master-wav step.

### Debug capture

`build_bundle` already accepts `joint_stats=None`, `words=None`,
`transcribe_words=None`, so the cue route can write a bundle with
`method_used="cue_align"` and those None. Keep capture minimal (no joint
stats); guard `_write_debug_capture`'s joint-only fields on `method_used`.

## Fold-in review findings

- **Untyped `realign` param (cue_align.py:310):** DONE. Now called live; added
  `realign: Callable[[int, float, float], list[dict] | None] | None = None`.
- **Collapsed-span agreement (joint_match.py:645):** DEFERRED. On closer read,
  returning 1.0 for containment of a zero-width ref is *consistent* with the
  non-collapsed full-containment case (which also yields 1.0), not a
  discontinuity. `joint_match.py` is byte-identical to the branch where beta was
  tuned; changing it risks regressing that tuning for a PLAUSIBLE-not-CONFIRMED
  issue. Revisit only if a real mis-rescue is observed.
- **Dead `offset_mad_against_cues` (srt_cues.py:51):** DEFERRED. Same
  "tuning-harness reference" category as the still-open question of whether to
  port `replay_ytasr_third_source.py` here. Deleting now pre-empts that decision.

## Post-wiring review round (high, a82232d7..HEAD)

No correctness bugs. Applied: extracted `cue_align.align_song` (pure driver,
injected `slice_align`, unit-tested with a stub) so the sectioning/offset/
re-pace orchestration lives in the library not the stage (#2); guarded the
vocal-duration read so an unreadable stem degrades to cue-pacing instead of
crashing (#1); threaded cue telemetry into the debug bundle (#4); fixed the
stale `cue_align` module docstring (scripts driver -> injected aligner).
Accepted: the shared de-reverb gate's transcribe is only "wasted" when
de-reverb is disabled (default `dereverb_yield_wpm=30` keeps it on) (#3).
Refuted: the `max(0.0, c0+offset, c1+offset)` end-clamp is a real
inverted-span guard, not dead code.

## Out of scope (separate follow-ups)

- Stale `lrclib` seed in `regen_alignment_bundles.py` (regen tooling, not the
  live pipeline).
- joint_match 3-builder copy-paste and the cue_align double-tokenise micro-opt
  (pure cleanups; do only if cheap while in the file).

## Tests

- `test_lyric_align`: SRT input routes `_run_cue_align` (mock the shared
  `_slice_align` + `_dereverb_gate`), asserting the joint matcher is NOT called;
  txt input still routes `_run_joint`. Degenerate-cue SRT falls through.
- `test_download_manager`: `download_auto_en_subs` is invoked after a successful
  download; a raised exception is swallowed and the download still succeeds.
- `test_joint_match`: collapsed ytasr reference span no longer yields agreement
  1.0 for bare containment.
- Delete `offset_mad_against_cues` tests from `test_srt_cues`.

## Test plan (manual)

- \[ \] Add a YouTube song that has an SRT -> `subtitles/<stem>.en.asr.json3`
  appears at download; alignment logs the cue-align route; ASS produced.
- \[ \] Add a Genius song -> log "YTASR: adopted N words ... as the 3rd source";
  joint runs three-source.
- \[ \] Reverb-washed SRT song -> de-reverb gate fires before cue_align.
- \[ \] A song with no auto-captions -> download still succeeds; alignment logs
  two-source / cue-align without ytasr.
