Model: Claude Sonnet 5

# CTC forced-align eyeball (whole corpus)

## Objective

Run torchaudio CTC forced alignment (MMS_FA) over the **whole 33-song corpus**,
aligning **whatever lyric text each song currently uses**, and emit karaoke `.ass`
per song so the results can be eyeballed against the video in mpv. This is a
**quick, exploratory look** — "does CTC alignment look right?" — not a measured
comparison.

**Secondary question:** can CTC skip de-reverb? Align on the **plain vocal stem
only** (never the dereverbed variant), so the run doubles as a test of whether
CTC is robust enough on raw separated vocals that the de-reverb stage is
unnecessary for it. The 23 songs that production de-reverbed are the ones to
scrutinize for reverb-induced smearing.

**In scope:** produce one playable CTC `.ass` per song, plus a short run summary.

**Out of scope:** no accuracy metrics, no numeric comparison against the current
whisper/cue-align timings, no pipeline wiring, no new product dependency. The
existing `karaoke/<stem>.ass` (current pipeline output) is available for
side-by-side eyeballing, but computing a diff is a later step, not this one.

## Everything needed is already on disk (verified)

- **Audio (vocal stem):** always use `pikaraoke-songs/vocal/<stem>---vocal.m4a`
  (all 33). **Do not use the `dereverb/` variants** — the point is to see whether
  CTC copes with raw separated vocals and de-reverb can be skipped. No stem
  separation to run.
- **Text:** the bundle's `lyrics.align_lines` (the exact lines the pipeline feeds
  the aligner — SRT text for SRT songs, Genius sheet for Genius songs). One
  bundle per song at `pikaraoke-songs/alignment_debug/<stem>.json`. All 33 have
  `align_lines`.
- **Aligner:** `torchaudio.pipelines.MMS_FA` (confirmed present in torchaudio
  2.11.0+cu126, `sample_rate=16000`, CUDA available). Zero new dependencies.
- **ASS output:** reuse `generate_ass(line_objects, cfg)` from
  [lyric_align.py:1088](../pikaraoke/pipeline/stages/lyric_align.py#L1088). It
  needs only `line_obj["words"] = [{"word": str, "start": float, "end": float}]`
  per line — so CTC word timings produce an `.ass` byte-format-identical to the
  pipeline's, directly A/B-able in the same player.

## STEP 0 — one-song smoke test before the corpus run

MMS_FA's exact aligner call has shifted across torchaudio releases. Prove the
recipe on **one short song** (e.g. `Josh Gad - In Summer`) end to end — audio →
emission → aligner → word seconds → `.ass` that plays in mpv — before looping the
corpus. Reconcile the aligner usage against torchaudio's CTC forced-alignment
tutorial for 2.11 if the reference below drifts.

## CTC recipe

```python
import torchaudio
bundle = torchaudio.pipelines.MMS_FA
model = bundle.get_model().to("cuda").eval()
tokenizer = bundle.get_tokenizer()
aligner = bundle.get_aligner()   # (emission[T,V], List[token-ids]) -> List[List[TokenSpan]]
SR = bundle.sample_rate          # 16000
```

1. **Decode the vocal to 16 kHz mono WAV** via ffmpeg into your scratchpad
   (robust — avoids torchaudio's m4a backend quirks). Load it with
   `torchaudio.load`.
2. **Long audio must be chunked** — a full 4–5 min song in one `model(waveform)`
   forward will OOM the 6 GB card (attention is O(n²) over ~15k frames). Run the
   model over **~20 s non-overlapping waveform chunks**, collect each chunk's
   emission, and `torch.cat` them along the time dim into one emission tensor.
   (Chunk-boundary edge effects are negligible for an eyeball.)
3. **Normalize + tokenize the transcript** (see gotcha below), tokenize the full
   word list, run `aligner(emission, token_ids)` → one `TokenSpan` list per word.
4. **Frames → seconds:** `ratio = num_wave_samples / emission.size(0)` (time
   frames); `word_start = spans[0].start * ratio / SR`,
   `word_end = spans[-1].end * ratio / SR`.
5. Free GPU between songs (`del emission; torch.cuda.empty_cache()`).

## Text normalization + the word-count gotcha (main correctness risk)

The line grouping only works if the flat CTC word list maps back to lines 1:1.

- Keep, per word, **both** the original display token (for the `.ass` text, with
  caps/apostrophes) **and** its normalized alignment form (lowercased, restricted
  to the MMS_FA dictionary charset; drop OOV chars). MMS_FA is latin/romanized —
  a few non-English lines exist (e.g. "Ma chère mademoiselle"); ASCII-fold or let
  OOV chars drop, and note any line that came out empty.
- If a word's normalized form is **empty** (pure punctuation / a stray symbol),
  exclude it from the tokenizer input **and** remember it was skipped, so the
  per-word spans returned by the aligner still line up with the non-empty words.
  Skipped words simply get no karaoke highlight (rare, fine for an eyeball).
- Track `words_per_line` from `align_lines` (post-normalization word counts) so
  the flat aligned-word list slices cleanly back into per-line groups.

## Line grouping → ASS

Group the flat aligned words back into lines using `words_per_line`, build
`line_objects = [{"words": [{"word", "start", "end"}, ...]}, ...]`, and call
`generate_ass(line_objects, cfg)`. Construct `cfg` as the pipeline does —
instantiate the default `PipelineConfig` (`from pikaraoke.pipeline.config import
PipelineConfig`); mirror the app's construction if it needs arguments.

Write each result to `pikaraoke-songs/ctc_review/<stem>.ass`.

## Expected rough edges (this is what you're eyeballing, not bugs to fix)

Forced alignment fits **exactly the text you give it** to the audio, so expect
smearing where text and audio diverge: instrumental intros/outros, un-sung lyric
lines, or a sheet that lists a chorus more times than it's actually sung (the
known lyric-version-overcount issue). Long silences with no matching text are the
worst case. Note which songs look smeared in the summary — that's signal about
where CTC needs a timing prior / windowing, not something to patch here.

## Output

1. **`pikaraoke-songs/ctc_review/<stem>.ass`** for every song that aligned.
2. **A run summary** (print + a short `ctc_review/SUMMARY.md`): per song — #lines,
   #words aligned, first/last word time, whether it was one of the **23 songs
   production de-reverbed** (scrutinize those for reverb smearing, since they're
   the de-reverb-skip test cases), and any failure/empty-line/OOV notes. Flag
   songs whose alignment looks degenerate (e.g. first word > 30 s in, or all
   words crammed into a fraction of the duration).
3. **The eyeball command**, printed once:
   `mpv "<song>.mp4" --sub-file="ctc_review/<stem>.ass"`
   (add `--sub-file="karaoke/<stem>.ass"` too for a current-vs-CTC A/B).

## Robustness

- Per-song `try/except Exception`: log the song + error, continue. One bad song
  must not abort the corpus run.
- Load the MMS_FA model **once**, reuse across all songs; only the emission is
  per-song.
- Decode temp WAVs into the scratchpad via `get_temp_directory()` conventions;
  clean them up.

## Success criteria

- All 33 songs attempted; each produces an `.ass` or a recorded failure.
- STEP 0 smoke song visibly tracks the vocal in mpv before the full run.
- Summary lists per-song word counts + flags the degenerate-looking ones.

## Non-goals

- No accuracy scoring or numeric diff vs the current timings.
- No edits to pipeline code, `requirements.txt`, or `pyproject.toml`; the probe
  script lives in the scratchpad. (`generate_ass`/`PipelineConfig` are imported
  read-only.)

## Results (run 2026-07-18)

33/33 songs aligned on plain vocal stems, zero failures, zero degenerate
flags; per-song table in `pikaraoke-songs/ctc_review/SUMMARY.md`. Only
flagged row (Seasons of Love, late start) explained by the piano vamp +
OOV-skipped numeral opener. GATE C verdicts (Ken eyeball): **C-1 YES**
(often superior to whisper; best edge/syllable timing in the project),
**C-2 YES** for the aligner (Girl in the Bubble essentially perfect on
the wet stem), C-3 sectional desync on version-mismatch songs confirmed
(windowing is the anticipated fix). Full read + recorded observations:
`plans/shared-aligner-form.md` → Results log, GATE C entry (was
`plans/timing-source-pillars.md` before the lane split).
