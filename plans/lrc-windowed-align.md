Model: Claude Opus 4.8

# LRCLIB-scaffold windowed alignment for non-SRT songs

## Goal

A matcher for songs with **no uploader SRT** (the Genius-lyric group: YouTube ASR
captions and/or LRCLIB available). Extend the cue-anchored *windowed* path that
already works for SRT songs (`pikaraoke/lib/cue_align.py`,
`scripts/cue_align_song.py`) instead of the global joint matcher, whose
drift / repeat-pileup / slow-sweep artifacts the windowed path structurally
avoids.

The windowed path needs a **dense, correctly-ordered, 1:1 cue scaffold** (line ->
time). SRT supplies that for free. This work is about building an equivalent
scaffold for non-SRT songs from the audio + external sources.

## Journey (what was tried, on the 10 ASR-caption corpus songs)

All A/B numbers are over the 10 songs, per-section force-align on a local GPU.
Honest quality metrics: **re-pace %** (fraction of lines that fell back to cue
interpolation because the audio align failed — lower = more lines audio-placed)
and **worst inter-line overlap** (the crawl/repeat signature). LRCLIB residual
MAD (Theil-Sen fit to audio anchors) is the cross-check oracle where non-circular.

1. **ASR-only densify** — map YouTube ASR words onto Genius lines
   (`ytasr.cue_spans_for_lines`), densify the sparse cues
   (`cue_align.densify_cue_spans`). Coverage was the bottleneck: ASR mapped
   12-97% of lines (Hakuna 5/40). Sparse anchors -> heavy interpolation ->
   scattered, out-of-order placements. Mean re-pace 40%, overlap 4.1s.

2. **+ whisper transcribe pass (union anchors)** — also map the whisper
   transcribe word stream onto the lines and union the two anchor sets
   (transcribe preferred on ties; `cue_align.merge_cue_spans`). Transcribe of the
   vocal stem is far denser than YouTube ASR (Belle 31->86, Be Our Guest 35->62,
   Hakuna 5->18); where both map a line they agree to ~0.1-0.4s. **Clear win:**
   mean re-pace 40->32%, overlap 4.1->3.2s. Two single-pair overlap regressions
   on already-good songs (Be Our Guest, Girl in Bubble) on *interpolated* lines
   neither source mapped.

3. **+ align-pass warp (REJECTED)** — fill the interpolated lines from the global
   forced-align pass (`words` in the bundle), warped onto the anchors. Fixed the
   clean songs (Be Our Guest interp overlap 4.0->0.1) but **imported the global
   align's drift** on repeat-heavy songs (Man Out re-pace 32->60, Best Part
   2.0->4.5). Net wash, and it re-derives the joint matcher the windowed path
   exists to avoid. Dropped.

4. **LRCLIB scaffold, warped onto audio anchors (ADOPTED)** — fetch LRCLIB by the
   Genius artist/title (production `lrclib` fetcher), use it as the dense ordered
   scaffold, warp it onto the audio clock with the ASR+transcribe anchors. LRCLIB
   is a clean human/community transcription (no drift, complete, correctly
   ordered) — a much better dense source than the align pass, and it keeps the
   path distinct from the matcher. **Best on both metrics:**

   | scaffold | mean re-pace | mean overlap | median re-pace |
   |---|---|---|---|
   | ASR-only | 40% | 4.1s | 47% |
   | +transcribe union | 32% | 3.2s | 40% |
   | **LRCLIB-warped** | **20%** | **2.2s** | **18%** |

   Re-pace nearly halved vs union: LRCLIB sections the song correctly, so
   per-section align succeeds on far more lines. Standouts: Hakuna re-pace
   58->20 (worst-coverage song), **Girl in Bubble fully recovered (0 overlap, 0%
   re-pace)** despite needing dereverb in production — the dense scaffold bounds
   the sections correctly even on the wet stem.

## Adopted architecture

For a non-SRT song, build the cue scaffold then run the shared windowed driver
(`align_with_cues`): silence-bounded sections -> per-section force-align -> split
to lines -> re-pace the unplaceable.

Scaffold, in order of trust:

1. **LRCLIB** (dense, ordered, complete) fetched by the Genius artist/title —
   the dominant signal. Only its per-line *start* is trusted (its line *ends* are
   just the next line's start).
2. **ASR ∪ transcribe** audio-clock anchors — fit a robust tempo+offset
   (Theil-Sen) and **warp LRCLIB onto the audio clock** (LRCLIB's master often
   differs: Defying Gravity 354s vs 257s video). The anchors also fill lines
   LRCLIB misses; remaining lines are interpolated.
3. **Gate / fallback**: warp residual MAD > 2s (a structurally different LRCLIB
   recording, e.g. Defying Gravity) or no LRCLIB match -> fall back to the
   ASR+transcribe union scaffold (`densify_cue_spans`).

Line *ends* are paced (capped at the next start, clamped to duration) so the
silences `segment_by_gaps` splits on survive; the per-section align then sets the
absolute word timing from audio — so the wrong LRCLIB clock never reaches the
output.

## Components

- `pikaraoke/lib/cue_align.py` (pure, tested):
  - `densify_cue_spans` — sparse audio anchors -> dense list (also the warp's
    fallback). Demotes non-advancing-start anchors (a refrain the ASR
    transcribed once maps two identical lines to one cue -> push the repeat
    forward instead of stacking).
  - `merge_cue_spans` — union of two anchor dicts.
  - `warp_scaffold_cues` — LRCLIB warped onto anchors, Theil-Sen + MAD gate.
- `scripts/lrc_align_song.py` — standalone single-song harness (reads Genius
  lyrics + transcribe words + Genius keys from the debug bundle, ASR + vocal from
  disk, LRCLIB live). Writes `<stem>.lrcalign.ass`. Touches nothing in the
  pipeline.
- `scripts/cue_align_song.py` — the shared windowed driver `align_with_cues`
  (SRT path's `align_song` is a thin loader over it).

## Validation

- Hand-picked LRCLIB files (`pikaraoke-songs/lrclib/<song>`) as a timing oracle:
  match output lines to the LRC by text, Theil-Sen fit (absorbs LRCLIB's wrong
  tempo/offset), residual MAD = real placement error. Be Our Guest 0.2s, Colors
  0.31s, Bloodstream 0.59s where measurable. NOTE: once LRCLIB is the *scaffold*,
  this oracle is partly circular — judge on re-pace + overlap instead.
- The genius-keyed LRCLIB search finds usable synced lyrics for all 10 corpus
  songs (the metadata survey's "no match" was stale); after a tempo+offset fit,
  LRCLIB's relative structure matches the audio to sub-second MAD on 9/10.

## Bugs found + fixed this session

- `warp` initially **piecewise through every common point** = non-robust; one bad
  anchor flung lines to wrong times (Belle 23.7s, Colors 11.6s overlap). Switched
  to a robust **global** Theil-Sen fit + MAD gate.
- LRCLIB line ends are the *next line's start* -> contiguous cues, no gaps ->
  `segment_by_gaps` made the whole song one section (Colors 65% re-pace). Fixed by
  pacing the ends and capping at the next start.
- Warped cues past the video end produced an inverted ffmpeg slice (Bloodstream).
  Fixed by clamping to `[0, duration]`.

## Next steps

- **Live (bundle-free) integration.** Everything the harness reads from a bundle
  already exists in the pipeline: Genius lyrics + id/title/artist (`lyrics_fetch`),
  ASR (`ytasr`), whisper transcribe words (`_run_joint`). A pipeline stage can
  build the scaffold from fresh passes instead of a bundle — the new functions are
  pure over word lists / cue dicts to make that drop-in.
- Dereverb gate before the audio passes (as production does) for reverb-washed
  stems; LRCLIB coverage made it unnecessary on Girl in Bubble here, but a song
  with poor LRCLIB + reverb would still need it.
- Minor: Belle (union slightly beat LRCLIB on overlap) and Best Part (live version
  vs studio LRCLIB) — candidates for a per-song best-of, but not worth the
  complexity yet.
