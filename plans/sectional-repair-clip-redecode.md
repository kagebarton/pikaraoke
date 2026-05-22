# Sectional Repair — Clip Re-decode ("#3")

Model: Claude Opus 4.7

Follow-on to [sectional-tiling-repair.md](sectional-tiling-repair.md) (#2,
the windowed merge — shipped). Read that first; this plan only changes how
the repair routine *acquires its words for a span*, nothing downstream.

## Motivation

#2 repairs concentrated walk failures by tiling each failed span against the
words of **one whole-song `transcribe()`**, time-filtered to the span's audio
window. That whole-song transcribe is the wasteful part: a 4-minute song with
a single 24-second broken section still decodes all 4 minutes, then throws
away ~94% of the words. #3 replaces it with a **clip transcribe** — decode
only the `[t0, t1]` audio of each failed span.

The seam was built into #2 for exactly this: the repair routine gets its
words through a provider `words_for_window(t0, t1) -> list[word]`. In #2 that
provider filters the whole-song transcribe; in #3 it transcribes a clip.
Everything downstream (tile → remap → splice → reassemble) is byte-identical.
**#3 is a provider swap plus one timestamp-offset step — not a re-architecture.**

## Scope

- Replace the single whole-song transcribe on the repair route with a
  per-span clip transcribe, behind a config flag (`repair_clip_transcribe`),
  with the #2 whole-song path retained as the fallback.
- No whisper-worker change: `WhisperWorker.transcribe_words(path, …)` already
  accepts an arbitrary audio path, and the plan that introduced #2 anticipated
  feeding it "an extracted `[t0,t1]` wav". The worker stays untouched.
- The repair *decision* (concentration-only routing, `_decide_route`,
  `_build_repair_ranges`, `_splice_range`, reassembly) is unchanged.

## The provider seam (data structure)

```python
# type alias (lyric_align.py)
WordsForWindow = Callable[[float, float], list[dict]]
```

A `WordsForWindow` takes an absolute audio window `(t0, t1)` and returns
whisper words **in absolute song time** (`{word, start, end}`). Margin and
(for #3) clip-relative→absolute offsetting are the provider's responsibility,
so `_repair_spans` is provider-agnostic.

Two concrete providers, both built in `LyricAlignStage.run` on the repair route:

- **#2 whole-song filter** (fallback): closes over the one whole-song
  `transcribe_words` list + `repair_window_margin_s`; just calls the existing
  `_words_for_window(words, t0, t1, margin)`.
- **#3 clip transcribe** (new default after validation): closes over
  `ctx` + `vocal_wav` + config; extracts a `[t0-margin, t1+margin]` clip,
  transcribes it, offsets the words back to absolute time.

## Flow

`LyricAlignStage.run`, repair route, post-refine ranges non-empty:

```
build provider = _make_clip_provider(ctx, vocal_wav)        # or whole-song closure
line_objects, capture_repair_ranges =
    _repair_spans(line_objects, repair_ranges, provider, lyrics_lines, align_lines)
```

`_repair_spans` per range `[L0, L1]` (only the words-source line changes vs #2):

```
t0 = _good_line_end_before(line_objects, L0, range_lines)        # 0.0 at head
t1 = _good_line_start_after(line_objects, L1, range_lines, last) # last end at tail
window_words = words_for_window(t0, t1)        # <-- provider (filter OR clip transcribe)
repair_objs, _ = match_words_to_lines_tiling_with_stats(
    window_words, lines[L0:L1+1], align_lines[L0:L1+1])
remap line_id += L0; _splice_range(...); record meta
```

`_make_clip_provider(ctx, vocal_wav)` returns `words_for_window(t0, t1)`:

```
lo = max(0.0, t0 - margin); hi = t1 + margin
lo, hi = _pad_to_min_duration(lo, hi, repair_clip_min_duration_s)   # whisper context
clip = _extract_clip_wav(ctx, vocal_wav, lo, hi)        # ffmpeg -ss lo -t (hi-lo)
try:
    clip_words = _model_call(ctx, Phase.TRANSCRIBE,
                             lambda: worker.transcribe_words(clip, cancel_event))
finally:
    clip.unlink(missing_ok=True)
return [{**w, "start": w["start"] + lo, "end": w["end"] + lo} for w in clip_words]
```

The clip-relative→absolute offset (`+ lo`) is the one genuinely new step;
without it the spliced objects land at the wrong song time.

## Per-file changes

### `pikaraoke/pipeline/context.py`

Add a phase for the clip-extract ffmpeg (its own cancellable — a `KillProcess`
on the Popen — distinct from the worker's `SetEvent`):

```python
CLIP_EXTRACT = "clip_extract"  # lyric_align: extract a [t0,t1] vocal clip for repair
```

Each clip *transcribe* reuses the existing `Phase.TRANSCRIBE`.

### `pikaraoke/pipeline/stages/lyric_align.py`

New imports: `run_ffmpeg` from `._ffmpeg_helpers`, `Callable` from `typing`.

- **`_repair_spans` signature change:** replace the `transcribe_words: list`
  parameter with `words_for_window: WordsForWindow`. Body change is one line
  (`window_words = words_for_window(t0, t1)` in place of the `_words_for_window`
  call). Margin handling moves entirely into the providers, so `_repair_spans`
  no longer reads `repair_window_margin_s`. `_words_for_window` stays (used by
  the #2 provider).

- **`_make_clip_provider(self, ctx, vocal_wav) -> WordsForWindow`** (new
  method): builds the #3 closure above. Captures `ctx`, `vocal_wav`,
  `self._worker`, and the two clip knobs.

- **`_pad_to_min_duration(lo, hi, min_dur) -> tuple[float, float]`** (new pure
  function): if `hi - lo < min_dur`, widen symmetrically to `min_dur`, shifting
  the deficit to the high side when `lo` clamps at 0.0. No song-duration
  argument needed — a `hi` past EOF is harmless to ffmpeg `-t`. Pure, so it's
  unit-tested directly.

- **`_extract_clip_wav(self, ctx, vocal_wav, lo, hi) -> Path`** (new method):

  ```python
  clip = ctx.tmp_dir / f"{ctx.song_path.stem}.repair_{int(lo*1000)}_{int(hi*1000)}.wav"
  cmd = ["ffmpeg", "-ss", f"{lo:.3f}", "-i", str(vocal_wav), "-t", f"{hi-lo:.3f}",
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-y", str(clip)]
  run_ffmpeg(cmd, ctx, Phase.CLIP_EXTRACT)
  return clip
  ```

  `-ss` *before* `-i` is sample-accurate for the separator's PCM wav and
  faster than post-input seek; move it after `-i` only if `vocal_wav` ever
  becomes a compressed format. 16 kHz mono pcm matches whisper's native input
  so the clip is tiny and needs no internal resample. `ctx.tmp_dir` is the
  per-job scratch dir the orchestrator already cleans; the provider also
  `unlink`s each clip right after transcribing.

- **`_make_whole_song_provider(self, words) -> WordsForWindow`** (new, tiny):
  the #2 fallback closure — `lambda t0, t1: _words_for_window(words, t0, t1,
  margin)` as a named function (avoids a bare lambda; keeps margin local).

- **`run` repair branch:** instead of always doing one whole-song transcribe,
  branch on `self._config.repair_clip_transcribe`:

  ```python
  if repair_ranges:
      if self._config.repair_clip_transcribe:
          provider = self._make_clip_provider(ctx, vocal_wav)
      else:
          whole = _model_call(ctx, Phase.TRANSCRIBE,
                              lambda: self._worker.transcribe_words(vocal_wav, cancel_event))
          provider = self._make_whole_song_provider(whole)
      line_objects, capture_repair_ranges = self._repair_spans(
          line_objects, repair_ranges, provider, lyrics_lines, align_lines)
      capture_method_used = "walk+repair"
      capture_escalation_trigger = "concentration"
  ```

  `keep_walk` / `whole_tiling` routes are untouched.

### `pikaraoke/pipeline/config.py`

```python
# Repair words-source. True (#3): transcribe only each failed span's audio
# clip. False (#2): one whole-song transcribe, time-filtered per span.
repair_clip_transcribe: bool = False        # flip to True after corpus validation

# Pad a clip window out to at least this many seconds (centred, clamped to
# the song) before transcribing, so whisper keeps enough acoustic/LM context
# to decode the span as well as it would inside the whole song.
repair_clip_min_duration_s: float = 6.0
```

`repair_window_margin_s` is reused as the clip margin (the audio pulled in on
each side before min-duration padding).

### `pikaraoke/pipeline/workers/whisper_worker.py`

**No change required** — `transcribe_words(path, cancel_event)` already does
transcribe → regroup → refine → flatten on any path. *Optional* later
refinement: a `transcribe_clip` job kind that skips the regroup step (tiling
re-segments anyway, so regroup is wasted work on a clip). Marginal; not in
scope.

### `pikaraoke/lib/alignment_capture.py`

Additive (schema stays v4, additions only):

- `pipeline_decisions.repair_words_source`: `"clip" | "whole_song_filter"`,
  recorded once per song (the provider `run` chose).
- each `repair_ranges[]` entry gains `words`: the absolute-timed window words
  that were tiled for that span. **Decided addition** — clip words are small,
  and storing the actual tiling input lets the repair *tiling* be re-tuned
  offline without re-running whisper, which is exactly what the corpus phase
  needs. `window_word_count` stays as the quick scalar.

`_repair_spans` writes `words` into each range's meta; `run` sets
`repair_words_source` and threads it through `_write_debug_capture`.

## Quality risks specific to clips (and mitigations)

These are the reason #3 ships behind a flag, defaulting off until validated:

- **Context loss.** Whisper decodes a 2–3 s clip with less acoustic and
  language-model context than the same region inside the whole song, and VAD
  edge effects bite harder. → `repair_clip_min_duration_s` pads short windows;
  `repair_window_margin_s` includes a little real neighbour audio. The splice
  fallback bounds the damage: if the clip transcribe is too garbled to tile,
  the line keeps walk's (smeared-but-present) timing.
- **Boundary words.** A word straddling the clip edge may come back as a
  fragment. Mitigated by the margin; bounded by the splice.
- **Margin bleed.** The margin decodes a little of the neighbouring good
  lines, whose words could fuzzy-match a range line (repeated lyrics). Same
  risk as #2's filter margin, slightly higher because #3 actually decodes that
  audio. Keep the margin small (≤ 0.5 s); the per-line splice contains it.

## Cost

- **#2 repair:** align + refine + one whole-song transcribe.
- **#3 repair:** align + refine + **one clip transcribe per range**, each
  bounded by `max(t1-t0+2·margin, repair_clip_min_duration_s)`. For the common
  case (1–2 short holes) this is seconds of audio vs. minutes — the whole point.

The crossover: a song with *many* ranges pays many clip transcribes whose
total audio can approach the whole song, while #2 pays exactly one. So #3 is a
clear win only when ranges are few/short.

## Adaptive provider (optional)

Because the crossover is range-count-driven, an optional refinement: in `run`,
pick the clip provider when `len(repair_ranges) <= repair_clip_max_ranges`
(e.g. 3) and the whole-song provider otherwise. This caps #3's worst case at
the #2 cost while keeping the win on the common path. Defer until the corpus
shows whether many-range repairs actually occur (they coincide with the
pervasive-medium-collapse open question in #2).

## Edge cases

- **Range at song head/tail:** `lo` clamps to 0.0; `hi` past EOF is harmless
  (`-t` just stops at end of file). Min-duration padding at the tail may
  request past EOF — fine.
- **Empty/garbled clip transcribe:** provider returns `[]` → tiling finds
  nothing → `_splice_range` keeps walk for the whole range (never regress to
  absent). Identical to #2's empty-window behaviour.
- **Multiple ranges:** N sequential clip extracts + transcribes (the worker
  processes one job at a time); each clip is unlinked after use.
- **Cancellation:** the clip extract runs under `Phase.CLIP_EXTRACT`
  (`KillProcess`) and the clip transcribe under `Phase.TRANSCRIBE`
  (`SetEvent`); a cancel mid-repair raises `PipelineCancelled` out of the
  provider and unwinds `_repair_spans` cleanly. Partial clip files are in
  `ctx.tmp_dir`, cleaned by the orchestrator.
- **Cache interaction:** `refine_from_cached` has already popped the align
  result before the clip transcribes run, so there's no cache contention.

## Testing

Unit:
- `_extract_clip_wav`: builds the expected ffmpeg argv (`-ss lo`, `-t hi-lo`,
  16k/mono/pcm, clip path under `ctx.tmp_dir`); `run_ffmpeg` mocked.
- clip provider: mock the worker to return clip-relative words; assert the
  returned words are offset by `lo` (absolute) and the clip is unlinked.
- min-duration padding: a 1 s window → padded to `repair_clip_min_duration_s`,
  centred; head clamp keeps `lo == 0.0`.
- `_repair_spans` is provider-agnostic: run the existing #2 splice tests with
  a fake clip provider and assert identical splice/reassembly output.

Integration (mocked worker + mocked `run_ffmpeg`):
- auto repair route with `repair_clip_transcribe=True`: `transcribe_words`
  called once **per range** with a clip path (never on `vocal_wav`); `refine`
  still called once; final line_objects adopt the (offset) clip timing on
  repaired lines and keep walk elsewhere.
- `repair_clip_transcribe=False`: one `transcribe_words(vocal_wav)`, repair
  output identical to today (regression guard for the #2 path).
- cancellation: `_model_call` raising `PipelineCancelled` inside the provider
  propagates out of `run`.

## Staging

1. Add `WordsForWindow`, refactor `_repair_spans` to take a provider, add
   `_make_whole_song_provider`, route `run` through it — **#2 behaviour
   unchanged** (provider just wraps today's filter). Pure refactor + tests.
2. Add `Phase.CLIP_EXTRACT`, `_extract_clip_wav`, `_make_clip_provider`, the
   two config knobs, capture fields. Flag defaults **False** (dark landing).
3. Validate clip transcribe quality against the corpus on the other host
   (compare `walk+repair` output with the flag off vs on for the named songs);
   then flip `repair_clip_transcribe` to True.
4. (Optional) adaptive provider + `repair_clip_max_ranges`.

## Open questions

- **`repair_clip_min_duration_s` (6 s) and `repair_window_margin_s` reuse.**
  The real dial for clip quality. Validate by re-decoding the #2-repaired
  spans as clips and diffing the tiled result; raise the floor if short clips
  transcribe worse. A separate, larger `repair_clip_margin_s` may beat reusing
  the filter margin — measure.
- **Default flip.** Keep `repair_clip_transcribe=False` until the corpus shows
  clip quality matches whole-song on the repaired spans; then default True and
  consider removing the #2 whole-song branch (don't carry both forever).
- **Many-range songs.** If the pervasive-medium-collapse case (open in #2)
  routes to repair with many ranges, the adaptive provider becomes worth it.
  Confirm from the same corpus run.
