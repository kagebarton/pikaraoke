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
| 15 | 2026-11-16 | extra, **not in the plan**: encoding of the two Kickapoo stems | Fable 5.2, this worktree (85d3a1b7). `ffprobe -show_entries stream=codec_name,profile,sample_rate,channels,bit_rate,duration:format_tags=encoder` on `$X/lib/vocal/` and `~/pikaraoke-songs/vocal/`, read-only | Scratch stem (made here): aac LC, 44100 Hz, 2 ch, 263.5 s, bit_rate 179336, encoder `Lavf60.16.100`. Library stem (Windows-made): aac LC, 44100 Hz, 2 ch, 263.5 s, bit_rate 189954, encoder `Lavf62.12.101`. |
| 16 | 2026-11-17 | 10 seed (Windows arms) | Opus 5.5 on the VM, worktree `.claude/worktrees/whisper_input_fresh_vs_regen` at aa8bee03 (`git diff --stat 97bd57f3 HEAD -- pikaraoke scripts` empty). w1: `cp --parents` from the library of every file holding the video ID, outside `regen_backups/` and `karaoke/`; w2: `cp -r $X/seed`, then `$X/lib/vocal` and `$X/lib/nonvocal`; w0: `cp -r $X/seed` | w1: 4 videos, 4 v11 bundles, 3 `.lrc` (none for `pXNd2V88d60`), 3 `.en.asr.json3`, 4 `.srt` + `.srt.generated`, 4 vocal + 4 nonvocal; every file `cmp`-equal to the library's. w2 and w0: `diff -rq` equal to `$X/seed`; w2's stems `diff -rq` equal to `$X/lib`. Vocal SHA256 (first 16): w1 Kickapoo `53e41e87e8c0d2c3`, `1YiAzyCzZzw` `631afe0b39cac9f8`, `pXNd2V88d60` `142b3769d4572640`, `GI6CfKcMhjY` `767d746d0addc2d4`; w2 Kickapoo `9a823f343c413e38`, Here I Go `8b9c5d09aeea9f0b`. Nonvocal: w1 `f54f68d96546301a`, `62c899bb81e68683`, `01acccb7db95566c`, `e1a33ffbc2c38e8e` (same order); w2 `5de73d5e770c8e55`, `f3a1d9b40bde99d3`. **Not done: the check of w1 against `$LV/sha256.txt`** (`linux_v12` not on D: yet). Kickapoo's stem (row 7) and v11 bundle (`cmp` with `$X/seed`) are already known equal to what the Linux library v12 read; the other three wait for `$LV`. |
| 17 | 2026-11-17 | 11 dry runs | same, `python scripts/regen_alignment_bundles.py $WX/<run> --dry-run < /dev/null` | w1: `GI6CfKcMhjY`, `1YiAzyCzZzw`, `pXNd2V88d60` `reuse genius+ytasr`, Kickapoo `reuse genius`. w2 and w0: Kickapoo `reuse genius`, Here I Go `reuse genius+ytasr`. Every bundle v11; no caption fetch, no prompt; exit 0 each. |
| 18 | 2026-11-17 | 12 decode, VM | same; ffmpeg `6.1.1-3ubuntu5`. The 44.1 kHz WAV was written to the session scratchpad instead of `$WX/decode/vm/` (the D: link runs at about 2 MB/s), one file overwritten per stem | `$WX/decode/vm/`, size in bytes and SHA256 (first 16): `win-hvvjiE4AdUI.pcm` 8,432,002 `c40415b895f8584d`; `win-1YiAzyCzZzw.pcm` 6,526,108 `f7cdc21b11abb149`; `win-pXNd2V88d60.pcm` 11,510,410 `9debd722efec3e05`; `win-GI6CfKcMhjY.pcm` 6,298,738 `2f6d919b8d3942fb`; `lin-hvvjiE4AdUI.pcm` 8,432,002 `dc7823eeee5b520a`; `lin-kHwpS0LakeU.pcm` 5,495,514 `6d15a0a6707e0781`. |
| 19 | 2026-11-17 | 13 GPU runs | Ken, Windows clone `C:\temp\Github\pikaraoke` at aa8bee03 (fetched from `vm`), PiKaraoke closed; step 13's block as written, then step 14's. **W1 ran before step 10's check against `$LV`** for its three non-Kickapoo songs (offered to Ken 2026-11-17; step 9 not yet run) | `versions.txt`: `2.6.0+cu124 12.4 NVIDIA RTX A2000`. Logs `$WX/{w1,w2,w0}_run.log` end `Done. succeeded=4 failed=0 skipped=0`, `succeeded=2 failed=0 skipped=0`, `succeeded=2 failed=0 skipped=0`; the console's exit lines were not relayed. Times below are the logs' (Windows local, UTC-5). Every run: ONNX's "CUDAExecutionProvider not available" warning; no `dereverb/` folder; no `.lrc` besides the seeded ones. |
| 20 | 2026-11-17 | 13 run W1 | `$WX/w1_run.log` | 10:33:34 to 10:47:26, then the LRCLIB backfill for 4 genius-origin songs; `pXNd2V88d60`: "no synced match". Stages per song: load_vocal, seed_artifacts, lyric_align; whisper read `<stem>_vocal.wav`. First joint match line per song (align / transcribe / ytasr / interp): `GI6CfKcMhjY` 41/16/7/2, windowed re-align 3 of 15 spans; `1YiAzyCzZzw` 1/45/10/19, 10 of 16; `pXNd2V88d60` 29/10/13/19, 7 of 7; Kickapoo 25/16/0/3, 1 of 4 (38 anchors, 3 suspects). Onset snap starts / ends: `GI6CfKcMhjY` 7/66 (+0.58 s), 18/74 (+1.75 s); `1YiAzyCzZzw` 3/75 (+0.88 s), 21/57 (+1.14 s); `pXNd2V88d60` 16/71 (+2.37 s), 25/63 (+19.71 s); Kickapoo 27/44 (+3.86 s), 16/43 (+5.08 s). |
| 21 | 2026-11-17 | 13 run W2 | `$WX/w2_run.log` | 10:47:43 to 10:53:03, then the backfill; Here I Go: "no synced match". Stages as W1. Kickapoo 32/12/0/0, re-align 1 of 4 (38 anchors, 3 suspects); onset 26/44 (+1.76 s), ends 14/47 (+5.39 s). Here I Go 15/4/49/2, re-align 3 of 12 (48 anchors, 4 suspects); onset 3/70 (+0.62 s), ends 10/68 (+1.13 s). |
| 22 | 2026-11-17 | 13 run W0 | `$WX/w0_run.log` | 10:53:12 to 11:01:00, then the backfill; Here I Go: "no synced match". Stages: ffmpeg_extract, loudnorm_analyze, stem_separation, ffmpeg_transcode, seed_artifacts, lyric_align; whisper read `<stem>_input_(vocals)_vocals_mel_band_roformer.wav`. Kickapoo 32/12/0/0, re-align 1 of 4 (38 anchors, 3 suspects); onset 28/44 (+3.86 s), ends 17/45 (+8.03 s). Here I Go 15/4/49/2, re-align 3 of 12 (48 anchors, 4 suspects); onset 3/70 (+0.54 s), ends 10/68 (+1.15 s). |
| 23 | 2026-11-17 | 15 stems | Opus 5.5 on the VM, `sha256sum`, `stat -c %s`, `ffprobe -show_entries stream=bit_rate:format_tags=encoder` on `$WX/*/vocal/` | w1 and w2 vocal hashes equal to row 16. w0 Kickapoo `53e41e87e8c0d2c3`, 6,303,466 B, bit_rate 189954, `Lavf62.12.101`. w0 Here I Go `bebfc718a39dceb9`, 5,508,602 B, bit_rate 255155, `Lavf62.12.101` (the library's, Linux-made: `8b9c5d09aeea9f0b`, 5,583,424 B, 258640, `Lavf60.16.100`). The Linux box's `versions.txt`: not yet (step 9). |
| 24 | 2026-11-17 | 16 decode compare | same; numpy over `$WX/decode/{win,vm}/*.pcm` as int16 | All six: SHA256 equal, sample counts equal, largest absolute difference 0. `win-hvvjiE4AdUI` 4,216,001 samples; `win-1YiAzyCzZzw` 3,263,054; `win-pXNd2V88d60` 5,755,205; `win-GI6CfKcMhjY` 3,149,369; `lin-hvvjiE4AdUI` 4,216,001; `lin-kHwpS0LakeU` 2,747,757. Whether the VM's ffmpeg is the Linux box's build: not yet (step 9). |
| 25 | 2026-11-17 | 17 pairs (without `$LV`) | same; scratch `compare_win.py` (step 7's matching and measures), kept with its output in `$WX/compare_win.py` and `$WX/compare_win_out.txt`. "win v11" = the library's bundle; "lin A/B" = `$X/armA`, `$X/armB`. Per pair: transcribe_words; words; pass 1; lines whose `selected_source` differs | K W1 vs win v11: n 455/455, unmatched 0/0, >=11 ms 22, >=0.3 s 1, max 0.400 (end 0.040); words 455/455, 84, 38, max 32.132 (end 31.200); pass 1 moved 5 [18, 20, 41, 42, 43], sharing 3/0; source differs [17, 18, 31, 40, 41, 42, 43]. P W1 vs win v11: n 433/443, unmatched 7/17, 35, 2, max 4.436 (end 2.320); words 358/358, 97, 45, max 2.580 (end 2.580); pass 1 moved 7 [57, 58, 59, 60, 61, 63, 64], sharing 9/2; source [57, 58, 59, 62, 63]. R W1 vs win v11: n 349/343, unmatched 22/16, 31, 6, max 7.980 (end 12.460); words 528/528, 261, 96, max 8.784 (end 9.344); pass 1 moved 12 [14-22, 42, 47, 48], sharing 16/16; source [8, 42, 46, 47, 48]. J W1 vs win v11: n 504/503, unmatched 18/17, 109, 0, max 0.280 (end 0.280); words 532/532, 140, 6, max 1.400 (end 1.420); pass 1 moved 7 [12, 13, 19, 20, 30, 57, 58], sharing 0/0; source [10, 11, 12, 13, 15, 57, 58]. K W1 vs W2: n 455/458, unmatched 40/43, 119, 7, max 9.970 (end 9.260); words 455/455, 29, 20, max 32.132 (end 30.644); pass 1 moved 8 [5, 14, 18, 28, 38, 41, 42, 43], sharing 3/0; source [16, 17, 18, 28, 41, 42, 43]. K W2 vs lin B: n 458/460, unmatched 42/44, 121, 9, max 9.230 (end 9.280); words 455/455, 2, 0, max 0.160 (end 0.160); pass 1 moved 7 [14, 25, 28, 29, 30, 36, 38], sharing 0/0; source [16, 25, 28, 29, 30, 31]. H W2 vs lin B: n 440/440, unmatched 0/0, 6, 0, max 0.120 (end 0.120); words 455/455, 1, 0, max 0.020; pass 1 moved 0, sharing 0/0; source none. K W0 vs win v11: transcribe_words, words and pass 1 all 0 moved, max 0.000; source none. K W0 vs lin A: n 455/455, unmatched 0/0, 7, 0, max 0.020; words 455/455, 62, 22, max 30.685 (end 31.000); pass 1 moved 0, sharing 0/0; source [31, 40]. H W0 vs lin A: n 439/438, unmatched 2/1, 10, 1, max 0.560 (end 0.360); words 455/455, 1, 0, max 0.020; pass 1 moved 0, sharing 0/0; source none. **Not run: W1 vs Linux library v12** (needs `$LV`). |
| 26 | 2026-11-17 | 17 R14 lines | same | Pass-1 start-end and selected source; `interpolated_line_ids`; pass-1 lines sharing a start; `monotone_discard` entries for these lines as (line, best_t0, selected_t0). K win v11: L41 236.61-237.52 align / L42 237.52-237.86 align / L43 238.38-238.56 align; interp []; sharing 0; none. K W1: L41-43 230.62-230.62 interp; interp [41, 42, 43]; sharing 3; (41, 97.16, None), (42, 207.316, None), (43, 210.416, None); sources align 25 / transcribe 16 / interp 3. K W2 and K W0: L41-43 as K win v11 to the hundredth; interp []; none. P win v11: L57 177.74-177.84 transcribe / L58 178.98-179.44 transcribe / L59 179.76-180.08 transcribe / L60 180.08-180.50 interp; (57, 62.34, 177.74), (58, 63.24, 178.98), (60, 76.04, None). P W1: L57-60 175.14-176.06 interp; interp gains 57, 58, 59, 62, 63; sharing 9; (57, 62.34, None), (58, 63.24, None), (60, 76.04, None). R win v11: L56 285.59-292.81 / L57 292.83-294.05 / L58 294.05-302.57 / L59 302.57-307.81 / L60 307.81-313.71 / L61 313.71-316.55 / L62 316.55-322.59, all align; sharing 16. R W1: the same lines and sources, L59 302.57-307.77, L60 307.77-313.71; interp list equal to v11's; sharing 16. J win v11: L12 27.84-29.52 ytasr / L62 168.64-175.92 transcribe; (62, 171.4, 168.64). J W1: L12 23.48-28.42 align / L62 168.64-175.94 transcribe; (62, 171.4, 168.64). |
| 27 | 2026-11-17 | extra, **not in the plan**: final line times of R14's lines | same; `output_line_timings` of win v11 and W1, read to match R14's quoted numbers | K win v11: L41 237.43-243.35 / L42 237.53-243.89 / L43 243.89-252.03; K W1: L41-43 230.62-230.62. P win v11: L57 178.03-178.73 / L58 178.90-179.55 / L59 179.55-180.39 / L60 180.19-180.49; P W1: L57-60 175.14-176.06. R win v11: L56 287.98-292.84 / L57 292.84-294.12 / L58 294.12-302.60 / L59 302.60-308.30 / L60 308.30-310.76 / L61 310.76-313.56 / L62 313.56-328.84; R W1: the same, L58 294.12-302.58, L59 302.58-308.30. J win v11: L12 27.84-29.52 / L62 168.64-177.32; J W1: L12 23.47-28.53 / L62 168.64-177.34. R14 quotes the Linux library v12 at K 41-43 230.62, P 57-60 175.14, R 56-62 296.08, J line 12 23.48 and line 62 171.94 (J as pass 1). |
| 28 | 2026-11-18 | 10 check W1 against `$LV/sha256.txt` | Sonnet 5.5 on the VM, worktree `.claude/worktrees/whisper_input_fresh_vs_regen` at c483b56b (clean; `git diff --stat 97bd57f3 HEAD -- pikaraoke scripts` empty). **`$LV` is not at the planned path:** Ken's copy is `D:\Shared\whisper_regen_linux\` (VM `/home/ken/shared-drives/D:/Shared/whisper_regen_linux`); no `whisper_regen\linux_v12` exists. It holds the four bundles, `sha256.txt` (12 entries, written 2026-11-17 22:18) and `versions.txt`. Scratch script (not kept) hashed `$WX/w1/{vocal,nonvocal}/*.m4a` and the W1 v11 bundles, matching by relative path. The v11 bundles are `$WX/w1/regen_backups/20261117T153332Z/alignment_debug/*.json`, where W1's regen moved them (`$WX/w1/alignment_debug/` now holds W1's v12 output). Also hashed the library's current copies, read-only | 12 of 12 equal, 0 mismatches. Vocal (first 16): Kickapoo `53e41e87e8c0d2c3`, `1YiAzyCzZzw` `631afe0b39cac9f8`, `pXNd2V88d60` `142b3769d4572640`, `GI6CfKcMhjY` `767d746d0addc2d4`. Nonvocal: `f54f68d96546301a`, `62c899bb81e68683`, `01acccb7db95566c`, `e1a33ffbc2c38e8e`. Bundles vs the Linux backup `regen_backups/20261116T160237Z/alignment_debug/` (same order, all v11): `e66f57e654c778e4`, `f3056aba2fca012b`, `9d24c77b1de3cd5d`, `d5c804abadc5a465`. The library's current stems and bundles equal the same hashes. `$LV`'s four bundles: schema 12, captured_at 2026-11-16 `16:41:48Z` (Kickapoo), `16:18:06Z` (`1YiAzyCzZzw`), `16:24:13Z` (`pXNd2V88d60`), `16:14:34Z` (`GI6CfKcMhjY`); W1's bundles: schema 12, 2026-11-17 `15:47:26Z`, `15:40:45Z`, `15:45:11Z`, `15:36:44Z` (same order). W1 therefore ran on the stems and v11 bundles the Linux library v12 read. |
| 29 | 2026-11-18 | 16 ffmpeg-build check | same; first line of `$LV/versions.txt` against `ffmpeg -version \| head -1` on the VM, byte comparison; `dpkg-query` on the VM | `$LV`: `ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers`. VM: the same line; byte-equal. VM packages: `ffmpeg`, `libavcodec60`, `libavformat60` all `7:6.1.1-3ubuntu5`. `versions.txt` carries only that first line, so the libav* lines were not compared. Torch lines: Linux box `2.11.0+cu126 12.6 NVIDIA GeForce RTX 2060`; Windows `2.6.0+cu124 12.4 NVIDIA RTX A2000` (row 19). Windows ffmpeg `8.1.1-full_build-www.gyan.dev` (plan, Ken). Rows 18 and 24 decoded on this VM ffmpeg. |
| 30 | 2026-11-18 | 17 pairs: W1 vs Linux library v12, four songs | `compare_win.py` extended (adds `lin v12` bundles from `$LV` and the four pairs, appended after the existing ones; the file on D: is now the extended one) and rerun: `$WX/compare_win.py`, output `$WX/compare_win_out2.txt` (the row 25 output `compare_win_out.txt` is untouched). Inputs as a folder of symlinks in the VM scratchpad (layout in the script's docstring). `diff` of the new output against `compare_win_out.txt`: additions only, so every row 25 pair reproduces | K W1 vs lin v12: n 455/455, unmatched 0/0, >=11 ms 7, >=0.3 s 1, max 0.400 (end 0.020); words 455/455, 4, 0, max 0.060 (end 0.060); pass 1 lines 44/44, moved 0, sharing 3/3; source differs none. P: n 433/432, unmatched 7/6, 8, 0, max 0.040 (end 0.040); words 358/358, 0, 0, max 0.000 (end 0.000); pass 1 75/75, moved 0, sharing 9/11; source none. R: n 349/348, unmatched 6/5, 25, 16, max 9.420 (end 9.420); words 528/528, 204, 188, max 44.132 (end 39.428); pass 1 71/71, moved 15 [0, 47, 49, 50, 52-62], sharing 16/23; source differs [45, 46, 52-62]. J: n 504/507, unmatched 133/136, 169, 16, max 2.380 (end 2.320); words 532/532, 3, 1, max 0.385 (end 0.020); pass 1 66/66, moved 9 [28, 29, 30, 31, 35, 57, 58, 62, 63], sharing 0/0; source differs [27, 28, 29, 30, 34, 35, 45, 47, 48, 57, 58, 61, 62, 63, 64]. |
| 31 | 2026-11-18 | 17 R14 lines, W1 and Linux library v12 | same; pass-1 start-end and selected source; `interpolated_line_ids`; lines sharing a start; `monotone_discard` as (line, best_t0, selected_t0); source counts. W1's lines and sources are in row 26; interp lists, counts and discards for W1 are from the same run | K: W1 and lin v12 identical. L41-43 230.62-230.62 interp; interp [41, 42, 43]; sharing 3; (41, 97.16, None), (42, 207.316, None), (43, 210.416, None); align 25 / transcribe 16 / interp 3. P: L57-60 175.14-176.06 interp in both; interp lists equal (19 ids: 2, 32, 34, 36, 37, 40, 43, 54, 56, 57, 58, 59, 60, 62, 63, 66, 68, 70, 72); sharing W1 9, lin v12 11; (57, 62.34, None), (58, 63.24, None), (60, 76.04, None) in both; align 1 / interp 19 / transcribe 45 / ytasr 10 in both. R: lin v12 L56-62 all 296.08-329.15 interp; interp 26 ids (9, 12, 14-22, 27, 28, 30, 31, 56-62, 66, 68-70); sharing 23; (56, 228.38, None), (57, 227.32, None), (58, 103.32, None), (59, 106.752, None), (60, 106.752, None), (61, 109.56, None), (62, 226.76, None); align 16 / interp 26 / transcribe 12 / ytasr 17. R W1: L56-62 align (row 26); interp 19 ids (the same without 56-62); sharing 16; the same best_t0s, selected_t0 285.592 / 292.832 / 294.052 / 302.572 / 307.772 / 313.712 / 316.552; align 29 / interp 19 / transcribe 10 / ytasr 13. J: lin v12 L12 23.48-28.42 align, L62 171.94-178.38 align; interp [14, 45, 47]; sharing 0; discards none; align 43 / interp 3 / transcribe 13 / ytasr 7. J W1: L12 23.48-28.42 align, L62 168.64-175.94 transcribe; interp [14, 61]; sharing 0; (62, 171.4, 168.64); align 41 / interp 2 / transcribe 16 / ytasr 7. |
| 32 | 2026-11-18 | extra, **not in the plan**: Windows versions | Ken, Windows clone `C:\temp\Github\pikaraoke`, PowerShell: one `uv run python -c` line printing python, platform, torch, CUDA, cuDNN, GPU name and compute capability, and `torch.backends` TF32 / benchmark / deterministic flags; `nvidia-smi --query-gpu=name,driver_version`; `ffmpeg -version` lines starting `ffmpeg version` or `lib`; `uv pip freeze`. Output `$WX/versions_full.txt`, read by Opus 5.5 on the VM. `git diff --stat aa8bee03 HEAD -- uv.lock pyproject.toml` empty on the branch | python 3.12.13, `Windows-11-10.0.26200-SP0`. torch `2.6.0+cu124`, CUDA 12.4, cuDNN 90100. GPU `NVIDIA RTX A2000`, compute capability (8, 6), driver 581.80. `allow_tf32`: matmul False, cudnn True; cudnn benchmark False, deterministic False. ffmpeg `8.1.1-full_build-www.gyan.dev`; libavutil 60.26.101, libavcodec 62.28.101, libavformat 62.12.101, libavdevice 62.3.101, libavfilter 11.14.101, libswscale 9.5.101, libswresample 6.3.101. 129 pinned packages, among them stable-ts 2.19.1, openai-whisper 20250625, torchaudio 2.6.0+cu124, numpy 2.4.6, numba 0.65.1, llvmlite 0.47.0, tiktoken 0.13.0, scipy 1.17.1, librosa 0.11.0, audio-separator 0.44.2, onnxruntime 1.26.0 and onnxruntime-gpu 1.26.0, faster-whisper 1.2.1, ctranslate2 4.7.2. For reference, the VM's `pik` env (not the Linux box): stable-ts 2.19.1, openai-whisper 20250625, torch 2.11.0. No precision is set in `pikaraoke/` (no `fp16`, `float16` or `tf32` outside tests), so whisper runs at the library default. The Linux box's package versions: not read. |
| 33 | 2026-11-23 | extra, **not in the plan**: box listen, `GI6CfKcMhjY` and `pXNd2V88d60` | Sheet `D:\Shared\whisper_box_listen\listening-sheet.html` (written 2026-11-18 after row 32, not logged then): seven stretches holding every line whose final start or end differs by 0.3 s or more between the two boxes, or that one box hides; Kickapoo and `1YiAzyCzZzw` left out as the same on both boxes. Files in that folder, checked by Opus 5.5 on the VM: `<song>.windows.ass` SHA256-equal to `$WX/w1/karaoke/` (`1ab2e665...` Jack Sparrow, `fd536e9e...` Rent); `<song>.linux.ass` (`7677c6bc...`, `8d8d819c...`) Dialogue starts equal to `$LV`'s `output_line_timings` starts less the 0.8 s lead-in (checked on Rent). Ken played each stretch in mpv with each file, on Windows | Ken, verbatim: "my initial impression is that one song is better on windows, the other on linux"; then, to Opus's guess that it was Rent on Windows and Jack Sparrow on Linux: "as you've said, rent better on windows and jack sparrow on linux". No per-stretch labels. Wordless lines (`output_line_timings` `n_words` 0) and `joint_stats.interpolated_line_ids`, read from the bundles: `GI6CfKcMhjY` Windows v11 and W1 wordless [14, 61], interp [14, 61]; Linux v12 wordless [14, 45, 47], interp [14, 45, 47]; no pass-1 line shares a start in any of the three. `pXNd2V88d60` Windows v11 and W1: the same 21 wordless and 19 interp ids, 16 lines sharing a start; Linux v12: those plus 56-62 in all three lists. Line texts: 61 "Got a basehead wife (Yeah), her womb is polluted (Woo)", 45 "(What?),", 47 "(No)", 56-62 the "Leap of faith" run. |

Notes on the numbers (rows 8-14):

- Word lists are matched by text with `difflib.SequenceMatcher` (equal blocks), so a changed or dropped word does not shift the pairs after it. Moves are measured on matched words only. "Moved" is the change in `start`; the largest change in `end` is given in brackets. 11 ms and 0.3 s are tested as `>=`.
- "Sharing a start with a neighbour" counts lines whose pass-1 start equals the previous or next line's, at 1 ms. The two figures are the first and second bundle of the pair.
- Pass-1 line timings are `joint_stats.pass1_line_timings`; final line times were not compared.
- Library v12 was read in place (`~/pikaraoke-songs/alignment_debug/`, captured_at 2026-11-16T16:41:48Z).
- Rows 4-6 `armA` and `armB` hold only `alignment_debug/` and `karaoke/`, as the plan says.

## Reading (Claude Fable 5.2, 2026-11-16)

Interpretation of rows 1-15, kept apart from the log. Nothing here was
listened to, and only Kickapoo was examined; the other three stacked songs
from R14 are assumed to follow it, not checked.

**What the library v12 Kickapoo stack means**

- The input format is not the cause. Arm B read an AAC stem and did not stack
  (row 14). The library v12 run heard nearly what the WAV runs heard: no word
  text differs, largest move 0.14 s (row 13).
- The aligner loses its place near 195 s in every bundle. All four list a line
  near 195 s in `monotone_discard` (row 14); in arm A index 419-436 sit at
  195.456-195.496 before it recovers at 220.48 (row 11).
- In library v12 it does not recover. Index 437-454 land about 30 s early
  (row 12), lines 41-43 are discarded as out of order, and all three are
  interpolated to 230.62-230.62 (row 14). That is the stack.
- Near-identical input tips it either way. Windows v11 and arm A heard the same
  words within 0.02 s, yet their aligned `words` differ by up to 30.685 s
  (row 11). The Windows-made stem is the input that tipped it, not a bad stem.
- Ruled out for Kickapoo: the v12 code (A and B ran on it, neither stacks), the
  Linux box (row 8 repeats exactly; row 11 heard words within 0.02 s), and AAC
  as such (B).

Two defects follow: the aligner collapsing at the tail, and the joint match
giving several interpolated lines one zero-length timestamp.

**WAV or AAC for whisper**

- Not ranked. The experiment measured difference, not accuracy.
- The AAC made on this box moves what whisper hears: Kickapoo 21 of 455 heard
  words unmatched and 7 of 44 pass-1 lines moved 0.3 s or more (row 10); Here I
  Go 2 of 438 and no lines (row 9).
- The Windows-made AAC barely moves it (row 13). The two encodes differ: a
  newer ffmpeg and about 6% more bitrate on Windows (row 15). Whether that
  explains the gap is untested.

**Regen reading WAV: recommended no**

- It would not fix the stack; the WAV arm shows the same collapse at 195 s.
- Nothing shows WAV timings are better, only different.
- Regen has no WAV; it would need a re-separation per song or lossless stems
  kept on disk.
- If a fresh add and a regen should agree, the cheaper route is the reverse:
  a fresh add reads the decoded saved stem too.

**A higher stem bitrate: not worth testing yet**

It can only show AAC-heard words moving closer to WAV-heard ones, it would not
touch the stack, and it helps future songs only. A listen comes first: A/B arms
A and B on Kickapoo lines 5, 20, 25, 29, 30, 36, 38 (row 10). If A is clearly
tighter, the bitrate test has a target; if not, the question is closed.

## Ideas for the two defects

From the bundles only; none is checked against `joint_match.py`. Not a plan.

When the aligner loses its place:

1. Treat a pile-up (many words within a fraction of a second) as a trigger for
   the existing windowed re-align of that stretch.
2. Fence aligned words with the heard words: reject an aligned word far from
   where the same word was heard.

When lines are rejected:

3. Use the other evidence before interpolating. Library v12 holds the three
   `Rock` words at 236.586 / 238.110 / 238.210 (row 14) and still interpolated
   lines 41-43. Find out why first; it may be a small fix.
4. When a line's best candidate is out of order, take its next candidate that
   is in order instead of discarding the line.
5. Never give interpolated lines one shared timestamp; spread them across the
   gap they belong in.

Around the aligner:

6. A regen guard: compare the new bundle with the one it replaces, and keep the
   old one and flag the song when lines newly stack or newly interpolate.

Suggested order: 6 and 3, then 5. Ideas 1, 2 and 4 sit close to the matcher
filters rejected in July for collateral (hardening 4.5a) and need a probe
across the library before any code.

## Open, Ken's call

- Log the two defects in `plans/open-issues.md`.
- Whether a fresh add and a regen should read the same input.
- The Kickapoo A/B listen above.
- Kickapoo's library bundle is still stacked; a regen from the same stem and
  code would likely repeat it.

## Windows arms (added 2026-11-17)

Model: Claude Sonnet 5.5 on the VM for steps 10-12 and 15-17; Ken runs step 9 on the
Linux box and steps 13-14 on Windows. Reading: Opus 5.5.

### Question

Rows 1-15 ran on the Linux box only. Kickapoo stacked when the Linux box read the
Windows-made stem, and not when it read a Linux-made stem or a fresh WAV. Is that the
stem file or the machine reading it? The full regen at the onset-loud-start landing runs
on Windows, so the answer also says whether that regen will stack these songs.

State of D: on 2026-11-17 (checked from the VM):

- The library's Kickapoo stem is byte-identical to the one the Linux library v12 read
  (`53e41e87...`, row 7); its bundle there is still the Windows v11 (equal to `$X/seed`'s).
- `1YiAzyCzZzw`, `pXNd2V88d60` and `GI6CfKcMhjY` (the other R14 songs whose pass 1 moved
  most) hold Windows-made stems (encoder `Lavf62.12.101`) and Windows v11 bundles, each
  captured minutes after its stem was written.
- Here I Go's library stem is the Linux-made one (`8b9c5d09...`, encoder `Lavf60.16.100`).
- `$X` was copied to `D:\Shared\whisper_regen\exp\`. It has both arms but not the Linux
  library v12 bundles.
- Windows ffmpeg: `8.1.1-full_build-www.gyan.dev`, libavformat 62.12.101 (Ken, 2026-11-17).
  The VM's: `6.1.1-3ubuntu5`.

### Runs

| run | songs | stems on disk | what it isolates |
|---|---|---|---|
| W1 | Kickapoo, `1YiAzyCzZzw`, `pXNd2V88d60`, `GI6CfKcMhjY` | the library's (Windows-made) | against Linux library v12: the box only (same stem bytes, same code); against Windows v11: fresh WAV vs saved stem, on Windows |
| W2 | Kickapoo, Here I Go | the Linux-made ones in `$X/lib` | against Linux arm B: the box only; W1 vs W2 on Kickapoo: the stem only, on Windows |
| W0 | Kickapoo, Here I Go | none (fresh separation) | Kickapoo against Windows v11: does Windows repeat itself; both against Linux arm A: the box only, WAV-heard; the new stems' hashes: does a Windows separation repeat byte for byte |
| decode | the six vocal stems of W1 and W2 | - | the saved-stem path's two ffmpeg steps (`load_vocal.py`, then whisper's loader), Windows ffmpeg vs the VM's; the fresh path's resample is not covered |

Kickapoo once W1 and W2 are in:

| | Windows-made stem | Linux-made stem |
|---|---|---|
| Linux box | library v12 (stacked, rows 12, 14) | arm B (row 6) |
| Windows box | W1 | W2 |

### Paths

| name | VM | Windows |
|---|---|---|
| `$WX` | `/home/ken/shared-drives/D:/Shared/whisper_regen/win` | `D:\Shared\whisper_regen\win` |
| `$X` (the Linux scratch, copied) | `/home/ken/shared-drives/D:/Shared/whisper_regen/exp` | `D:\Shared\whisper_regen\exp` |
| `$LV` (from the Linux box, step 9) | `/home/ken/shared-drives/D:/Shared/whisper_regen/linux_v12` | `D:\Shared\whisper_regen\linux_v12` |
| library | `/home/ken/shared-drives/D:/Shared/pikaraoke-songs` | `D:\Shared\pikaraoke-songs` |

The VM sees D: only while an RDP session is connected.

### Rules

- Read-only on the library, `$X` and `$LV`. Every write goes under `$WX`.
- VM steps run from the VM worktree `.claude/worktrees/whisper_input_fresh_vs_regen`
  with `/home/ken/miniconda3/envs/pik/bin/python`, CPU only. The script puts its own
  checkout first on `sys.path`, so it runs this branch's code, not the editable install.
- Windows: PiKaraoke closed, nothing else on the GPU, runs in the order W1, W2, W0.
- Stop and report instead of improvising if: a hash in step 10 differs from the Linux
  box's, a dry run shows anything other than a reuse plan, or a run fails.
- Results continue the log above from row 16: raw numbers, no verdicts. Commit this file
  alone when the log is written, then stop with a short report to Ken.

### Steps

9. **From the Linux box (Ken).** The four current library v12 bundles, the hashes of
   what they read, and the box's versions:

   ```bash
   mkdir -p ~/whisper_regen_linux && cd ~/pikaraoke-songs
   cp -p alignment_debug/*{hvvjiE4AdUI,1YiAzyCzZzw,pXNd2V88d60,GI6CfKcMhjY}*.json ~/whisper_regen_linux/
   sha256sum {vocal,nonvocal}/*{hvvjiE4AdUI,1YiAzyCzZzw,pXNd2V88d60,GI6CfKcMhjY}*.m4a \
     regen_backups/20261116T160237Z/alignment_debug/*{hvvjiE4AdUI,1YiAzyCzZzw,pXNd2V88d60,GI6CfKcMhjY}*.json \
     > ~/whisper_regen_linux/sha256.txt
   ffmpeg -version | head -1 > ~/whisper_regen_linux/versions.txt
   /home/ken/miniconda3/envs/pik/bin/python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))" >> ~/whisper_regen_linux/versions.txt
   ```

   Then copy `~/whisper_regen_linux/` to `D:\Shared\whisper_regen\linux_v12\`.

10. **Seed (VM).** Plain `cp -r`; the D: mount keeps no modes, and the regen picks songs
    by bundle schema, not file dates.

    - `$WX/w1`: for each W1 song, every library file whose name holds its video ID,
      outside `regen_backups/` and `karaoke/`, at the same subfolder: the video, the v11
      bundle, `subtitles/`, `lyrics/`, `vocal/`, `nonvocal/`. Check against
      `$LV/sha256.txt`: the four vocal and four nonvocal stems equal the Linux library's,
      and the four bundles equal the Linux backup's.
    - `$WX/w2`: a copy of `$X/seed` (Here I Go's extra json3 included), plus
      `$X/lib/vocal/` and `$X/lib/nonvocal/`. Vocal hashes as row 7.
    - `$WX/w0`: a copy of `$X/seed` alone.

11. **Dry runs (VM).** `python scripts/regen_alignment_bundles.py $WX/<run> --dry-run`
    for w1, w2 and w0. Every song must show a reuse plan (Kickapoo `reuse genius`, Here I
    Go `reuse genius+ytasr`), no caption fetch, no prompt.

12. **Decode on the VM.** The pipeline's two decodes of each vocal stem, to 16 kHz mono
    PCM:

    ```bash
    cd /home/ken/shared-drives/D:/Shared/whisper_regen && mkdir -p win/decode/vm
    for s in win/w1/vocal/*---vocal.m4a exp/lib/vocal/*---vocal.m4a; do
      id=$(basename "$s" | sed -E 's/^.*---(.{11})---vocal\.m4a$/\1/')
      case "$s" in exp/*) tag=lin ;; *) tag=win ;; esac
      wav="win/decode/vm/$tag-$id.wav"
      ffmpeg -hide_banner -loglevel warning -y -i "$s" -ac 2 -ar 44100 -sample_fmt s16 "$wav"
      ffmpeg -loglevel error -nostdin -threads 0 -y -i "$wav" -f s16le -ac 1 -acodec pcm_s16le -ar 16000 "win/decode/vm/$tag-$id.pcm"
      rm "$wav"
    done
    ```

13. **GPU runs (Ken, PowerShell, after step 11).** If `git worktree list` shows the
    branch checked out in a worktree, `cd` there and use
    `git fetch vm; git merge --ff-only vm/whisper_input_fresh_vs_regen` instead of the
    checkout line.

    ```powershell
    cd C:\temp\Github\pikaraoke
    git fetch vm
    git checkout -B whisper_input_fresh_vs_regen vm/whisper_input_fresh_vs_regen
    git diff --stat 97bd57f3 HEAD -- pikaraoke scripts   # must print nothing
    uv run python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))" | Out-File -Encoding ascii D:\Shared\whisper_regen\win\versions.txt
    $env:PYTHONUTF8 = "1"
    foreach ($r in "w1", "w2", "w0") {
        cmd /c "uv run python scripts\regen_alignment_bundles.py D:\Shared\whisper_regen\win\$r --yes < NUL > D:\Shared\whisper_regen\win\${r}_run.log 2>&1"
        "$r exit $LASTEXITCODE"
        if ($LASTEXITCODE -ne 0) { break }
    }
    ```

14. **Decode on Windows (Ken, same window).** Step 12 with Windows ffmpeg:

    ```powershell
    $out = "D:\Shared\whisper_regen\win\decode\win"
    New-Item -ItemType Directory -Force $out | Out-Null
    $stems = @(Get-ChildItem -LiteralPath "D:\Shared\whisper_regen\win\w1\vocal") + @(Get-ChildItem -LiteralPath "D:\Shared\whisper_regen\exp\lib\vocal")
    foreach ($s in $stems) {
        $id = $s.Name -replace '^.*---(.{11})---vocal\.m4a$', '$1'
        $tag = if ($s.DirectoryName -like "*\exp\lib\vocal") { "lin" } else { "win" }
        $wav = Join-Path $out "$tag-$id.wav"
        ffmpeg -hide_banner -loglevel warning -y -i $s.FullName -ac 2 -ar 44100 -sample_fmt s16 $wav
        ffmpeg -loglevel error -nostdin -threads 0 -y -i $wav -f s16le -ac 1 -acodec pcm_s16le -ar 16000 (Join-Path $out "$tag-$id.pcm")
        Remove-Item -LiteralPath $wav
    }
    (Get-ChildItem -LiteralPath $out).Count   # expect 6
    ```

15. **Runs (VM).** Per run, as rows 3 and 6: exit, start and end, stages, the file whisper
    read, LRCLIB result, joint match counts, onset snap counts, any `dereverb/` file, any
    `.lrc` that was not seeded. SHA256 of every stem under `$WX/*/vocal/`: w1 and w2
    unchanged from step 10; w0's two new ones against the library's Kickapoo
    (`53e41e87...`) and Here I Go (`8b9c5d09...`), with ffprobe bit rate and encoder tag.
    Both boxes' `versions.txt`.

16. **Decode compare (VM).** Per stem, the SHA256 of `decode/win/<f>.pcm` and
    `decode/vm/<f>.pcm`; where they differ, sample counts, largest absolute sample
    difference and RMS of the difference (int16). Whether `$LV/versions.txt` names the
    VM's ffmpeg build; if not, the VM stands in for the Linux box only approximately.

17. **Compare (VM).** Step 7's measures, by a scratch copy of
    `D:\Shared\whisper_regen\compare.py` (not kept), on:

    | pair | what it isolates |
    |---|---|
    | W1 vs Linux library v12, each of the four | box only, same stem bytes |
    | W1 vs Windows v11, each of the four | fresh WAV vs saved stem, on Windows |
    | W1 vs W2, Kickapoo | Windows-made vs Linux-made stem, on Windows (row 12's mirror) |
    | W2 vs Linux arm B, Kickapoo and Here I Go | box only, same stem bytes |
    | W0 vs Windows v11, Kickapoo | does Windows repeat itself |
    | W0 vs Linux arm A, Kickapoo and Here I Go | box only, both WAV-heard |

    And R14's lines in every W bundle and in the bundle it is compared with: pass-1 start
    and end, selected source, `interpolated_line_ids`, and lines sharing a start with a
    neighbour. Kickapoo 41-43, `1YiAzyCzZzw` 57-60, `pXNd2V88d60` 56-62, `GI6CfKcMhjY`
    12 and 62. As in step 7, no final line times between a v11 bundle and a new one.

Cost: eight song-runs, two of them separating, about 20 minutes of A2000 GPU. About
450 MB under `$WX`. Network: LRCLIB lookups for the genius-origin songs only. The fill
comes after pass 1, so a new LRCLIB match does not touch the compared fields.

### Reading the result (for Ken's report, not the log)

- W1 stacks the same lines as Linux library v12: the stack follows the stem file, not
  the box. The Windows full regen at landing would stack these songs, so the regen guard
  (idea 6) or a defect fix comes first.
- W1 does not stack: the same stem and code give a different result on another machine.
  R14's Linux regen then does not predict a Windows one, which songs a regen stacks
  cannot be known before it runs, and the regen guard is the only protection.
- The four songs split: both, song by song.
- W2 equals arm B on Here I Go: the box alone does not move a well-behaved song when the
  input bytes match. If it differs, the pair says by how much.
- Decoded PCM equal on both boxes: ffmpeg is not part of the box difference; the GPU and
  torch stack is. Unequal: part of it is ffmpeg, which can be pinned.
- W0's Kickapoo differs from Windows v11 (Linux repeated exactly, row 8): Windows does not
  repeat itself, and W1 and W2 each need a second run before they are read. W0's
  Kickapoo stem equal to `53e41e87...`: a Windows separation and encode repeat byte for
  byte.

### Reading (Windows arms) (Claude Opus 5.5, 2026-11-18)

Interpretation of rows 16-31 against the key above, kept apart from the log. Read from
the bundles, run logs and `compare_win_out2.txt` on D:; nothing was listened to. "Linux
library v12" is `$LV`'s copy at `D:\Shared\whisper_regen_linux\` (row 28); row 28 also
confirms, after the fact, that W1 read the stem and v11 bytes the Linux regen read.

**The four songs split (the key's third case)**

| song | W1, Windows | Linux library v12 | the R14 lines follow |
|---|---|---|---|
| Kickapoo | L41-43 stacked at 230.62 | the same | the stem |
| `1YiAzyCzZzw` | L57-60 stacked at 175.14 | the same | the stem |
| `pXNd2V88d60` | L56-62 aligned, as Windows v11 | L56-62 stacked at 296.08 | the box |
| `GI6CfKcMhjY` | no stack; L12 23.48 align, L62 168.64 transcribe | no stack; L12 23.48 align, L62 171.94 align | L12 the stem, L62 the box |

- Kickapoo is the clean case. In the 2x2 the Windows-made stem stacks on both boxes and
  the Linux-made stem on neither (rows 26, 31). With the same stem, W1 and Linux v12 agree
  on every pass-1 line, no source differing (row 30).
- `1YiAzyCzZzw` repeats that on the one stem tested: the same stacked lines, interp list
  and discards; aligned words equal (rows 30, 31).
- `pXNd2V88d60` splits. Same stem bytes, same code, and all three bundles discard L56-62
  as out of order with the same far-early best candidates (row 31). Windows v11 and W1
  then place them; Linux v12 does not, and interpolates all seven to one time. The aligned
  words differ by up to 44 s between the boxes (row 30), so the aligner itself landed
  differently, not only the choice made after it. Its other 16 shared starts are in every
  bundle; only 56-62 are new.
- `GI6CfKcMhjY` never stacked. Its line 12 move in R14 (ytasr 27.84 to align 23.48) comes
  with the saved stem: W1 makes it too. Its line 62 move (168.64 to 171.94) is the Linux
  box's: W1 keeps Windows v11's time.

For the Windows full regen at the onset-loud-start landing:

- It would stack Kickapoo and `1YiAzyCzZzw` as the Linux regen did. On Windows too both
  stacks are new with the regen: the fresh-WAV Windows v11 has neither (rows 25, 26).
- It would not stack `pXNd2V88d60`, which the Linux regen did. R14's Linux list does not
  predict a Windows regen in either direction, so which songs a regen stacks cannot be
  known before it runs. The regen guard (idea 6), or a fix for the two defects, comes
  before that regen.

**What W2, W0 and the decode check say about the box**

- Decoded PCM is byte-equal across the two ffmpeg builds for all six stems (row 24), and
  the VM's ffmpeg is the Linux box's build (row 29). Step 12's second command matches
  stable-whisper's streaming loader as installed in the VM's `pik` env (stable-ts 2.19.1);
  Windows runs the same stable-ts and openai-whisper (row 32); the Linux box's were not
  read. With that caveat, whisper got identical samples on both boxes on the
  saved-stem path, and ffmpeg is not part of the box difference. What is left is the rest
  of the box: GPU, torch and CUDA (rows 19, 29), and any Python package that differs
  between the Windows install and the Linux `pik` env. Nothing here separates those. The
  fresh path's resample is not covered.
- Each box repeats itself. W0's Kickapoo equals Windows v11 to 0.000 s on every compared
  field, and its new stem is byte-equal to the library's (rows 23, 25); Linux did the same
  in row 8. The box differences are fixed per box, not run-to-run noise, so W1 and W2 need
  no second run. W0 covers the WAV path only; after the decode, the saved-stem path runs
  the same code.
- W2 on Here I Go equals Linux arm B: aligned words within 0.02 s, no pass-1 line moved,
  no source changed (row 25). The box alone does not move a well-behaved song.
- On some songs the box moves what whisper hears from identical samples: Kickapoo's
  Linux-made stem, 42 of 458 heard words unmatched and 7 pass-1 lines moved through
  transcribe-sourced lines (W2 vs arm B, row 25); `GI6CfKcMhjY`, 133 of 504 unmatched (row
  30). On others it barely does: Kickapoo's Windows-made stem 0, `1YiAzyCzZzw` 7. Across
  boxes the aligned words hold steadier than the heard ones, except where the aligner
  collapses (`pXNd2V88d60`).

**Against the 2026-11-16 reading**

- "Ruled out for Kickapoo: the Linux box" still holds for Kickapoo, not in general:
  `pXNd2V88d60` stacked on Linux and not on Windows from the same bytes.
- "The Windows-made stem is the input that tipped it" holds for Kickapoo and
  `1YiAzyCzZzw` on both boxes. On Windows as on Linux, the fresh WAV did not stack them
  and the saved stem did, so a fresh add and a regen can disagree on either box.
- The two defects (the aligner collapsing, interpolated lines sharing one timestamp) now
  show on two songs on both boxes and on a third on one box.

**Open, Ken's call (adds to the list above)**

- The regen guard (or a defect fix) before the Windows landing regen. Recommended: this
  is what the split says, since neither box's run predicts the other's.
- The Linux library still holds R14's stacked v12 bundles for Kickapoo, `1YiAzyCzZzw` and
  `pXNd2V88d60`; their v11 bundles are in `regen_backups/20261116T160237Z/`. A regen from
  the same stems on either box would stack Kickapoo and `1YiAzyCzZzw` again.
- Which part of the box moves `pXNd2V88d60` and `GI6CfKcMhjY` is unknown. Windows's
  versions are row 32; the Linux box's are not read. The two GPUs are different
  generations (compute capability 8.6 against the 2060's 7.5) on different torch builds,
  so matching the Python packages is not expected to make the boxes agree on its own. Not
  needed for the guard decision. (Added 2026-11-18, after row 32.)

### Reading (box listen) (Claude Opus 5.5, 2026-11-23)

From row 33.

- Neither box is the better one to regen on: each made the worse result on one of the two
  songs.
- Rent: the Linux regen's new stack (lines 56-62) is what Ken heard as worse. Idea 6 as
  written would catch it (lines newly interpolated and newly sharing a start) and keep the
  old bundle, which is the one Ken preferred.
- Jack Sparrow: the Linux regen newly interpolates and hides two ad-lib lines (45, 47) and
  recovers line 61, which both Windows bundles hide. Ken preferred the Linux result. Idea 6
  as written would flag it for the two new interpolated lines and keep the old bundle, the
  one he found worse.
- So the guard should set a flagged result aside for a listen, not decide on its own which
  bundle the song keeps. A guard that only counts lines newly interpolated would get this
  song wrong.
