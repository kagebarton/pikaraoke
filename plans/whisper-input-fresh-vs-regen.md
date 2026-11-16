# Whisper input: fresh WAV vs saved AAC stem

Model: Claude Sonnet 5.5

One experiment, no code change. It answers the open question left by
`plans/onset-loud-start.md` block R14: why the 13-song regen heard different
words than the bundles it replaced.

## Question

A newly added song has whisper read the separator's lossless WAV. A regen has
it read `vocal/<stem>---vocal.m4a` decoded back to WAV (`LoadVocalFromM4aStage`).
Is that difference, and not the Windows/Linux box, what moved the heard words
and stacked lines in R14?

Evidence so far (Fable, 2026-11-16, from bundles and file dates only):

- `22QYya-LGDY`: old bundle made on this box from the saved stem; equals today's
  word for word.
- Rent - I'll Cover You: old bundle captured on this box 3 minutes after its
  stem was written (so WAV-heard); differs from today's in 24 of 221 words.
- `pj6FCKm8dhM`, `fJ9rUzIMcZQ`, `MiraOCjABn8`: old bundles made on Windows from
  months-old saved stems; heard words have the same text and move at most
  0.08 s against today's.
- All four stacked-line cases are Windows bundles captured minutes after their
  stem was written.
- Nothing in the `pik` env was installed after 2026-04-08; the model file's
  SHA256 is OpenAI's published one.

## Rules

- Read-only on `~/pikaraoke-songs`, on `/media/ken/Data`, and on all code. Copy
  out of the library, never move, never write into it.
- All work in one scratch folder outside the repo and the library; call it
  `$X`. The scratch library is `$X/lib`.
- Run from this worktree (`.claude/worktrees/whisper_input_fresh_vs_regen`, `models/`
  already symlinked) with `/home/ken/miniconda3/envs/pik/bin/python`. Its code
  equals the R14 regen's (`97bd57f3..f9c1e7d6` is plan text only); check that
  `git diff --stat 97bd57f3 HEAD -- pikaraoke scripts` is still empty.
- The app must not be running (`pgrep -af pikaraoke.app`). One GPU job at a time.
- The comparison script is scratch, not kept. Results go in the Results log
  below, raw numbers, no verdicts. Commit this file alone when the log is
  written. Then stop with a short report to Ken.
- Stop and report instead of improvising if: a dry run shows anything other
  than a reuse plan, a Genius prompt appears, or a run fails.

## Songs

| role | song stem | old bundle (v11) | old text files |
|---|---|---|---|
| the stacked case | `TENACIOUS D - Kickapoo---hvvjiE4AdUI` | `regen_backups/20261116T160237Z/alignment_debug/` (Windows, fresh, 11-12) | same backup: `subtitles/` (`.srt`, `.srt.generated`), `lyrics/` (`.lrc`) |
| same-box control | `The Lonely Island - Here I Go (feat. Charli xcx)---kHwpS0LakeU` | live `alignment_debug/` (this box, fresh, 11-08 UTC, never regenerated) | live `subtitles/` (`.srt`, `.srt.generated`, `.en.asr.json3`); it has no `.lrc` |

Paths are under `~/pikaraoke-songs`. Rent is not used: its video was replaced
on 11-09, after its stem was made, so a fresh separation cannot repeat it.

Kickapoo's current library bundle (v12, made today from the Windows-made saved
stem) is the fifth thing compared; read it in place.

## Steps

1. **Seed.** In `$X/lib` put, for both songs: the video in the root, the old
   bundle in `alignment_debug/`, the old text files in `subtitles/` and
   `lyrics/`. No `vocal/`, `nonvocal/`, `dereverb/` or `karaoke/`. Keep a
   second copy of the seed in `$X/seed` for step 4.
2. **Arm A, fresh.** `python scripts/regen_alignment_bundles.py $X/lib --dry-run`.
   Both songs must show a reuse plan (`reuse genius` or `reuse genius+ytasr`),
   no caption fetch, no prompt. Then the same with `--yes`. With no stems on
   disk the script separates here and whisper reads that WAV; it also writes
   the new `.m4a` stems into `$X/lib`.
3. **Save A.** Copy `$X/lib/alignment_debug` and `$X/lib/karaoke` to `$X/armA`.
   Record whether a `dereverb/` file appeared, and whether Here I Go now has a
   `.lrc`.
4. **Reseed for arm B.** Copy the old bundles and old text files from `$X/seed`
   back over `$X/lib` (the bundles are schema 12 now and would be skipped).
   Leave `vocal/`, `nonvocal/`, any `dereverb/`, and any `.lrc` arm A wrote, so
   both arms use the same LRCLIB match.
5. **Arm B, saved stem.** Dry run again (reuse plans, stems now present), then
   `--yes`. Whisper reads the AAC stem that arm A just wrote. Copy the outputs
   to `$X/armB`.
6. **Hashes.** SHA256 of each scratch `vocal` stem and of the library's stem for
   the same song.
7. **Compare** the five pairs below. Per pair, on `transcribe_words` and on
   `words`: word counts, words whose text differs, words moved 11 ms or more,
   words moved 0.3 s or more, largest move. On
   `joint_stats.pass1_line_timings`: lines whose start moved 0.3 s or more,
   and lines sharing a start with a neighbour. Do not compare final line
   times between a v11 bundle and a new one: the onset change moves those by
   design.

   | pair | what it isolates |
   |---|---|
   | Here I Go: old v11 vs A | does a fresh run repeat on this box (expected: equal) |
   | Here I Go: A vs B | lossless vs AAC, nothing else changed |
   | Kickapoo: A vs B | the same, on the stacked song |
   | Kickapoo: Windows v11 vs A | box only, both WAV-heard |
   | Kickapoo: library v12 vs B | Windows-made stem vs Linux-made stem, both AAC-heard |

8. **Kickapoo lines 41-43** ("Rock" x3): pass 1 start and end in Windows v11,
   library v12, A and B, plus `interpolated_line_ids` for each. R14 has v11 at
   237.43 / 237.53 / 243.89 and v12 all at 230.62.

Cost: two runs of two songs, about 10 minutes of GPU in total, about 40 MB of
scratch disk. Network: at most one LRCLIB lookup (Here I Go).

## Reading the result (for Ken's report, not for the log)

- A matches the old bundles (Here I Go equal, Kickapoo within the small box
  drift, lines 41-43 apart) and B stacks: the AAC round trip is the cause.
- A stacks on Kickapoo too: the box matters more than the cue songs showed.
- Neither arm stacks: the Windows-made stem itself differs from a Linux-made
  one; step 6's hashes and the last pair in step 7 say by how much.
- Here I Go's A differs from its old bundle: separation does not repeat on this
  box, or the code changed since 11-08. The control failed; say so, and A vs B
  still stands on its own.

## Results log

| # | date | step | who, where, command | result |
|---|---|---|---|---|
| 1 | 2026-11-16 | 1 seed | Sonnet 5.5, this worktree (b277bc3a; `git diff --stat 97bd57f3 HEAD -- pikaraoke scripts` empty). `cp -p` out of `~/pikaraoke-songs` into `$X/lib`, then `cp -a $X/lib $X/seed`. `$X` = `/tmp/claude-1000/-home-ken-projects-pikaraoke/547959ab-4735-43e8-b326-e118eaf3c196/scratchpad/exp` | Seeded as the Songs table says. **One extra seed file, approved by Ken:** a copy of Here I Go's `.en.asr.json3` under the name its v11 bundle records, `subtitles/Here I Go (ft. Charli xcx) - Uncensored Version---kHwpS0LakeU.en.asr.json3`, in both `$X/seed` and `$X/lib`; byte-identical to the current-name copy, which is kept. No file with the recorded name exists in the library (the song was renamed after the bundle was captured). Scratch size after seeding: 62 MB. |
| 2 | 2026-11-16 | 2 dry run, without the extra file | `python scripts/regen_alignment_bundles.py $X/lib --dry-run` | Kickapoo `reuse genius`; Here I Go `reuse genius (ytasr json3 missing; two-source)`. Stopped and reported. Old Here I Go bundle: ytasr_won 49, align_won 15, transcribe_won 4, n_ytasr_words 412. The same dry run on a throwaway folder holding the extra file: `reuse genius+ytasr`. |
| 3 | 2026-11-16 | 2 dry run, then arm A (fresh) | `... $X/lib --dry-run`, then `... $X/lib --yes < /dev/null`; log `$X/armA_run.log` | Dry run: Kickapoo `reuse genius`, Here I Go `reuse genius+ytasr`; no caption fetch, no prompt. Run 21:06:06Z to 21:11:10Z, exit 0, succeeded=2 failed=0. Stages: ffmpeg_extract, loudnorm_analyze, stem_separation, ffmpeg_transcode, seed_artifacts, lyric_align. Whisper aligned `<stem>_input_(vocals)_vocals_mel_band_roformer.wav`, the separator's WAV. LRCLIB: no synced match for Here I Go. Joint match: Kickapoo align 30 / transcribe 14 / ytasr 0 / interp 0 (windowed re-align 1 of 4 spans, 38 anchors, 3 suspects); Here I Go align 15 / transcribe 4 / ytasr 49 / interp 2. Onset snap: Kickapoo 26/44 starts moved (max +3.86 s), 17/46 ends (+5.08 s); Here I Go 3/70 (+0.54 s), 10/68 (+1.15 s). Log warning: `CUDAExecutionProvider not available in ONNXruntime` (separator). |
| 4 | 2026-11-16 | 3 save A | `cp -a $X/lib/alignment_debug $X/lib/karaoke $X/armA/` | No `dereverb/` folder appeared. Here I Go has no `.lrc` (none written, no skip marker). Kickapoo `.lrc` byte-identical to the seed's. A bundles: schema 12, captured_at 21:09:06Z (Kickapoo) and 21:11:09Z (Here I Go). |
| 5 | 2026-11-16 | 4 reseed, 5 dry run | `cp -a $X/seed/{alignment_debug,subtitles,lyrics}/. $X/lib/<same>/`; `--dry-run` | alignment_debug, subtitles and lyrics identical to the seed (`diff -rq`); bundles back to schema 11; `vocal/` and `nonvocal/` untouched, hashes equal to those taken after A. Dry run: Kickapoo `reuse genius`, Here I Go `reuse genius+ytasr`. |
| 6 | 2026-11-16 | 5 arm B (saved stem) | `... $X/lib --yes < /dev/null`; log `$X/armB_run.log` | Run 21:11:58Z to 21:14:54Z, exit 0, succeeded=2 failed=0. `load_vocal` decoded `vocal/<stem>---vocal.m4a` to `<stem>_vocal.wav`; no separation. Joint match: Kickapoo align 32 / transcribe 12 / ytasr 0 / interp 0; Here I Go align 15 / transcribe 4 / ytasr 49 / interp 2. Onset snap: Kickapoo 23/44 (max +1.76 s), ends 18/49 (+5.16 s); Here I Go 3/70 (+0.62 s), ends 10/68 (+1.13 s). Stem hashes unchanged after B; no `dereverb/`. B bundles schema 12, captured_at 21:13:41Z and 21:14:52Z. Outputs copied to `$X/armB`. |
| 7 | 2026-11-16 | 6 hashes | `sha256sum`, `stat -c %s` on `$X/lib/vocal/*.m4a` and `~/pikaraoke-songs/vocal/*.m4a` | Kickapoo scratch (made here): `9a823f343c413e385c071464391fc22c392043ca6508e09d1132817a95c05652`, 5,953,698 B. Kickapoo library (Windows-made): `53e41e87e8c0d2c3359395b62740648c1de97a7ed2fe8c64cbdf59818ccfe0d5`, 6,303,466 B. Here I Go scratch: `8b9c5d09aeea9f0b5c7b7b18ec493310b85fe6072f2e9461e5ea5f5f084a1ddd`, 5,583,424 B. Here I Go library: the same hash, 5,583,424 B. |
| 8 | 2026-11-16 | 7 pair: Here I Go, old v11 vs A | scratch `compare.py` (not kept) | transcribe_words: n 438/438, text differs 0, moved ≥11 ms 0, ≥0.3 s 0, max start move 0.000 s (end 0.000 s). words: n 455/455, text differs 0, ≥11 ms 0, ≥0.3 s 0, max 0.000 s (end 0.000 s). pass-1 lines: 70/70, starts moved ≥0.3 s 0, sharing a start with a neighbour 0/0. |
| 9 | 2026-11-16 | 7 pair: Here I Go, A vs B | same | transcribe_words: n 438/440, unmatched 2/4 (436 matched), ≥11 ms 50, ≥0.3 s 1, max 0.560 s (end 0.270 s). words: n 455/455, text differs 0, ≥11 ms 46, ≥0.3 s 0, max 0.280 s (end 0.500 s). pass-1 lines: 70/70, starts moved ≥0.3 s 0, sharing 0/0. |
| 10 | 2026-11-16 | 7 pair: Kickapoo, A vs B | same | transcribe_words: n 455/460, unmatched 21/26 (434 matched), ≥11 ms 95, ≥0.3 s 6, max 0.740 s (end 0.180 s). words: n 455/455, text differs 0, ≥11 ms 22, ≥0.3 s 2, max 0.500 s (end 0.140 s). pass-1 lines: 44/44, starts moved ≥0.3 s 7 (lines 5, 20, 25, 29, 30, 36, 38), sharing 0/0. |
| 11 | 2026-11-16 | 7 pair: Kickapoo, Windows v11 vs A | same | transcribe_words: n 455/455, text differs 0, ≥11 ms 7, ≥0.3 s 0, max 0.020 s (end 0.020 s). words: n 455/455, text differs 0, ≥11 ms 62, ≥0.3 s 22, max 30.685 s (end 31.000 s); the 22 are index 309 `magical` (152.376 to 152.796) and index 419-439 `from` to `art`: in A, index 419-436 all sit at 195.456-195.496, index 437 `of` at 220.480, 438-439 at 225.964 and 226.120; v11 has index 419-439 at 220.480-226.896. pass-1 lines: 44/44, starts moved ≥0.3 s 0, sharing 0/0. |
| 12 | 2026-11-16 | 7 pair: Kickapoo, library v12 vs B | same | transcribe_words: n 455/460, unmatched 21/26 (434 matched), ≥11 ms 96, ≥0.3 s 6, max 0.740 s (end 0.180 s). words: n 455/455, text differs 0, ≥11 ms 30, ≥0.3 s 20, max 32.132 s (end 30.624 s); the 20 are index 56 `He` (+0.350), 184 `Rock` (-0.555), and index 437-454 `of` to the last three `Rock`: library v12 has them at 195.496 then 201.806-210.416 (index 442-451 within 204.116-204.416), B at 220.480-238.545. pass-1 lines: 44/44, starts moved ≥0.3 s 10 (lines 5, 18, 25, 29, 30, 36, 38, 41, 42, 43), sharing a start with a neighbour 3/0. |
| 13 | 2026-11-16 | 7 extra pairs, **not in the plan** (added to read rows 10 and 12) | same | Kickapoo library v12 vs A: transcribe_words text differs 0, ≥11 ms 22, ≥0.3 s 0, max 0.140 s; words ≥0.3 s 21, max 32.132 s; pass-1 lines starts moved ≥0.3 s 5 (lines 18, 20, 41, 42, 43), sharing 3/0. Kickapoo library v12 vs Windows v11: transcribe_words text differs 0, ≥11 ms 23, ≥0.3 s 0, max 0.140 s; words ≥0.3 s 38, max 32.132 s; pass-1 starts moved ≥0.3 s 5 (lines 18, 20, 41, 42, 43), sharing 3/0. Kickapoo Windows v11 vs B: transcribe_words n 455/460, unmatched 21/26, ≥11 ms 98, ≥0.3 s 6, max 0.740 s; words ≥0.3 s 23, max 30.685 s; pass-1 starts moved ≥0.3 s 7 (lines 5, 20, 25, 29, 30, 36, 38), sharing 0/0. |
| 14 | 2026-11-16 | 8 Kickapoo lines 41-43 | same | Pass 1 start-end for lines 41 / 42 / 43. Windows v11: 236.61-237.52 / 237.52-237.86 / 238.38-238.56, interpolated_line_ids []. Library v12: 230.62-230.62 for all three, interpolated_line_ids [41, 42, 43]. A: 236.61-237.52 / 237.52-237.88 / 238.41-238.58, []. B: 236.61-237.50 / 237.50-238.02 / 238.54-238.72, []. Selected source for lines 41-43: align in v11, A and B; interp in library v12. R14's 237.43 / 237.53 / 243.89 are not in pass1_line_timings; v11's `windowed_realign` span words for the three `Rock`s start at 237.426, 243.894, 243.894 (the first one ends at 237.526). The same `Rock` word starts: A 236.598 / 237.718 / 238.772; B 236.590 / 237.678 / 238.262; library v12 236.586 / 238.110 / 238.210. `monotone_discard` lists lines 41, 42, 43 (best_t0 97.16 / 207.316 / 210.416, selected_t0 None) in library v12 only; v11, A and B each list one line near 195 s (among others): line 38 (v11) or line 39 (A, B), with best_t0 195.436 / 195.476 / 195.476 and selected_t0 220.48 / 223.9 / 223.88. Lines whose selected source differs between any two of the four bundles: L17, L18 (library v12 transcribe, others align), L25 (B transcribe, others align), L29, L30 (B align, others transcribe), L31 (A and library v12 transcribe, v11 and B align), L40 (v11 align, others transcribe), L41-43 (library v12 interp, others align). selected_source counts: library v12 align 25 / transcribe 16 / interp 3. |

Notes on the numbers (rows 8-14):

- Word lists are matched by text with `difflib.SequenceMatcher` (equal blocks), so a changed or dropped word does not shift the pairs after it. Moves are measured on matched words only. "Moved" is the change in `start`; the largest change in `end` is given in brackets. 11 ms and 0.3 s are tested as `>=`.
- "Sharing a start with a neighbour" counts lines whose pass-1 start equals the previous or next line's, at 1 ms. The two figures are the first and second bundle of the pair.
- Pass-1 line timings are `joint_stats.pass1_line_timings`; final line times were not compared.
- Library v12 was read in place (`~/pikaraoke-songs/alignment_debug/`, captured_at 2026-11-16T16:41:48Z).
- Rows 4-6 `armA` and `armB` hold only `alignment_debug/` and `karaoke/`, as the plan says.
