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
