Model: Claude Opus 5.5 (design + judge); executor Sonnet per the phase table below

# Chinese character timing — standalone probe (Mandarin + Cantonese)

**Goal.** Find out whether any alignment method can give per-character
karaoke timing on Mandarin and Cantonese songs that Ken would sing to,
and what it costs. This is a measurement, not a build: nothing here
changes `pikaraoke/`. Whether and how to wire a winner into the pipeline
is decided after GATE Z2, from what this probe finds.

**Status: DRAFT 2026-10-20.** Phase 0 executed 2026-10-20; the four pilot
sheets confirmed 2026-10-27; Phase 1 runner built, GPU run done 2026-10-27
(14 arm-song artifacts saved); Ken's listening calls recorded 2026-10-30;
GATE Z1 read 2026-10-30: no arm dropped, Hal stands for Cantonese H
(see Results log). Ken's rulings 2026-10-30 retired W and R, added Phase 1b
(half precision + language guess) and put language detection in scope.
Phase 1b scripts built 2026-11-03 (`8452230`) and run the same day; the 1b-i run was
repeated with the app open (see Results log). GATE Z1b read 2026-11-03: half
precision does not fit beside the running app, so both languages run at full
precision in Phase 2 and Phase 3 records the fallback; Ken's four fp16 calls
are *as is*, no worse than Phase 1 (they bear on the fallback, not on Z1b).
Phase 0b's fetch for the twelve non-pilot songs ran on the VM 2026-11-03 (see Results
log); Ken's sheets for them are open. His Phase 0a for them is in (read off the library
the same day, see Results log).
The worksheet builder for them was built and tested on the pilot the same day; it waits
for a GPU transcribe (see Results log). Ken ran that transcribe 2026-11-03; the two pages
(Mandarin #3-8, Cantonese #10 and #12-16) were then built and published as private
artifacts, and wait for his friend's sheets (see Results log).

## Why now, and what this replaces

The `add_songs` real-world run (2026-10-20, `plans/library-tools.md` on
`library_tools`) put the first Chinese songs through the shipped
pipeline. Sunny Day (`DYptgVvkVLQ`, Genius sheet, joint route) came out
with 18 of 42 lines on screen and no character timing at all. Its
alignment bundle shows why:

- whisper runs with `language: "en"` for both align and transcribe
  (`pipeline/config.py`, both `language` fields);
- each Chinese line reaches whisper as a single "word" (a line has no
  spaces), so the best possible output is one highlight sweep per line.

So today's pipeline has no Chinese path at all. A probe of the pipeline
as-is would only measure that. This plan instead tests alignment methods
directly on the audio, outside the app.

**Supersedes GATE L** (`route-no-timing.md` / `route-line-timing.md`
Phase 4 on `edge_snap_refine`). GATE L was Mandarin-only and asked
whether romanized text helps the old CTC aligner beat whisper on the
retired line route. Its arms survive here as Arm R and Arm H, now
measured against whisper run in the right language and extended to
Cantonese. When GATE Z2 is read, GATE L closes with a pointer here.

## Ken's rulings (2026-10-20)

1. **Target is per-character timing.** Line-level timing is not the bar.
2. **Display is the source text as given.** No pinyin or jyutping on
   screen; Traditional/Simplified stays as the source wrote it. Any
   conversion is alignment-internal only.
3. **Mandarin and Cantonese both.** Japanese and Korean are out.
4. **Independent of the current code.** Caption-translation leaks,
   Genius dropping CJK from its query, language detection and the
   hard-coded `en` are implementation problems for after a method works.
   They are listed under "Out of scope", not fixed here.
5. **Judge is Ken's eye.** He reads Chinese well enough to tell whether
   characters are timed right.
6. **Other models are allowed** in the probe; cost is weighed at the
   end, not used to exclude arms up front.

## Ken's rulings (2026-10-30, after the GATE Z1 read)

7. **W and R retire now**, by Ken's eye over the gate (Z1 kept them):
   the character-CTC models were better on all four pilot songs. W-L
   goes with W. Phase 2 runs H (Mandarin) and Hal (Cantonese) only.
8. **Whisper should stay loaded** in production, since its reload is
   the longest. Phase 1b first tests H and Hal at half precision next to
   the app's resident models; if that fails, the fallback is to unload
   whisper while a Chinese song aligns and reload it afterwards.
9. **Language detection is in scope** (amends ruling 4): a build has to
   route a song to H or Hal, so the probe measures how to tell Mandarin
   from Cantonese. The other items in ruling 4 stay out.

## Ground rules

- **No `pikaraoke/` change.** Probe code lives in `scripts/zh_probe/` on
  this branch. It may import the app's *fetch* clients (Genius, LRCLIB)
  for convenience; it must not import alignment, matcher, snap or
  `.ass` writer code, so that the result does not depend on English
  heuristics tuned for the shipped routes.
- **Inputs from the library, read-only.** Each song's video and its
  `vocal/` stem (stem separation is language-independent). Songs enter
  the library through `add_songs` (Phase 0a); the app's own
  lyric outputs for them are ignored.
- **Outputs** go to `d:/shared/pikaraoke-songs/zh_probe/` (same
  precedent as `lrclib_study/`), one folder per phase, never into the
  library's `lyrics/`, `subtitles/` or `karaoke/`.
- **Extra packages via `uv run --with ...`**, nothing added to
  `pyproject.toml` or `uv.lock`. Model downloads go to the default
  caches and are recorded (name, size) in the Results log.
- **The lyric text is held fixed.** Every arm aligns the same
  Ken-confirmed sheet per song (Phase 0b). This isolates timing quality
  from text-source quality; text sourcing is an implementation problem.
- **One GPU job at a time** (`concurrent-gpu-inference-rejected`).
- **Executor / judge split as in `PROGRAM.md`:** the executor saves
  artifacts and pastes raw tables, no tallies or verdicts. Opus reads
  each gate against the rule written here; Ken's eyeball rules.

## Corpus

Aim: about 8 songs per language, spread over the things most likely to
break an aligner: tempo, voice range, duets, mixed-language lines, and
old recordings. Ken confirms or swaps; official uploads preferred.

| # | Lang | Song | Video (channel, length) | Why it's in |
|---|---|---|---|---|
| 1 | Mandarin | 周杰倫 晴天 | [`DYptgVvkVLQ`](https://www.youtube.com/watch?v=DYptgVvkVLQ) (周杰倫 Jay Chou) | in library; solfège lines (`Re So So Si...`), long intro |
| 2 | Mandarin | 周杰倫 龍捲風 | [`RPWDeLqsN0g`](https://www.youtube.com/watch?v=RPWDeLqsN0g) (周杰倫 Jay Chou) | in library; needs a Genius sheet (its SRT is an English translation) |
| 3 | Mandarin | 周杰倫 雙截棍 | [`OR-0wptI_u0`](https://www.youtube.com/watch?v=OR-0wptI_u0) (周杰倫 Jay Chou, 3:25) | fast rap: stress test |
| 4 | Mandarin | 周杰倫 & 費玉清 千里之外 | [`ocDo3ySyHSI`](https://www.youtube.com/watch?v=ocDo3ySyHSI) (周杰倫 Jay Chou, 4:32) | duet, two very different voices |
| 5 | Mandarin | 鄧麗君 月亮代表我的心 | [`IgvDMB5fR-8`](https://www.youtube.com/watch?v=IgvDMB5fR-8) (鄧麗君 Teresa Teng, 3:29) | slow, female, old recording |
| 6 | Mandarin | 孫燕姿 遇見 | [`m4nu_F_9dWU`](https://www.youtube.com/watch?v=m4nu_F_9dWU) (Timeless Music, 3:27) | female, modern ballad |
| 7 | Mandarin | 陳奕迅 十年 | [`JM9rx_hN1Ko`](https://www.youtube.com/watch?v=JM9rx_hN1Ko) (英皇娛樂 eeg music, 3:25) | pair with #9 (same melody) |
| 8 | Mandarin | 陳奕迅 愛情轉移 | [`RIq7Tz9nYD8`](https://www.youtube.com/watch?v=RIq7Tz9nYD8) (Eason Chan, 4:20; album audio) | pair with #10 (same melody) |
| 9 | Cantonese | 陳奕迅 明年今日 | [`8NJVNkzhJM4`](https://www.youtube.com/watch?v=8NJVNkzhJM4) (英皇娛樂 eeg music, 3:25) | pair with #7 |
| 10 | Cantonese | 陳奕迅 富士山下 | [`7qeShSmmsNg`](https://www.youtube.com/watch?v=7qeShSmmsNg) (Eason Chan, 4:20; album audio) | pair with #8 |
| 11 | Cantonese | Beyond 海闊天空 | [`qu_FSptjRic`](https://www.youtube.com/watch?v=qu_FSptjRic) (滾石唱片 ROCK RECORDS, 5:18) | band, rock |
| 12 | Cantonese | 張國榮 風繼續吹 | [`UmTB6E5mU5w`](https://www.youtube.com/watch?v=UmTB6E5mU5w) (華星唱片 Capital Artists, 5:19) | old recording, slow |
| 13 | Cantonese | 楊千嬅 少女的祈禱 | [`CvKvXNiXQZc`](https://www.youtube.com/watch?v=CvKvXNiXQZc) (華星唱片 Capital Artists, 3:37) | female |
| 14 | Cantonese | 王菲 容易受傷的女人 (粵語版) | [`tDw_ULjZWA8`](https://www.youtube.com/watch?v=tDw_ULjZWA8) (FayeWongVEVO, 4:20) | female, different timbre |
| 15 | Cantonese | 林子祥 男兒當自強 | [`U_EgeFUTbW4`](https://www.youtube.com/watch?v=U_EgeFUTbW4) (Timeless Music Hong Kong, 4:21) | male, older recording, brisk anthem |
| 16 | Cantonese | Twins 下一站天后 | [`cPKfUWDmNbo`](https://www.youtube.com/watch?v=cPKfUWDmNbo) (英皇娛樂 eeg music, 3:33) | duet, two female voices, upbeat |

All are label or artist-channel uploads, picked with yt-dlp search on
2026-10-20. 張學友 每天愛你多一些 was dropped for want of an official
studio upload. No truly fast Cantonese song is in; a later swap for one
is welcome.

The same-melody pairs (7/9, 8/10) are the only controlled comparison in
the corpus: same singer, same tune, different language, so a difference
between them points at the language, not the song.

**Pilot subset** (Phase 1): #1, #2, #9, #11. #1 and #2 are already in
the library; Phase 0a adds #9 and #11.

## Arms

**W, R and W-L retired 2026-10-30 (ruling 7); Hsk dropped at the GATE Z1
read.** From Phase 1b on, the arms are H (Mandarin) and Hal (Cantonese).
The descriptions below stay as the record of what Phase 1 ran.

Every arm takes the same input (vocal stem + confirmed sheet +
Ken's language label) and writes one JSON (per character: text, start,
end, line id) and one `.ass` with a `\kf` per character, rendered by a
small writer in the probe (not the app's).

- **Arm W — whisper, right language.** `stable_whisper` align with
  `language="zh"` (Mandarin) or `"yue"` (Cantonese) on the
  `large-v3-turbo.pt` already in `models/`. Whisper's own word split
  for these languages is per token, and a token can be several
  characters, so the run records how many characters got their own
  timing versus shared a token (shared spans are split evenly and
  flagged). **W-L** (full `large-v3`, a ~3 GB download) runs only if
  Arm W is not singable on Cantonese at the pilot.
- **Arm R — romanized CTC** (GATE L's L-A). torchaudio `MMS_FA` with
  each character converted to its syllable: `pypinyin` (+ `jieba`
  segmentation for multi-reading characters) for Mandarin,
  `ToJyutping` for Cantonese; tones stripped. One character maps to one
  syllable, so timing maps straight back.
- **Arm H — character CTC** (GATE L's L-B). A wav2vec2 fine-tune that
  outputs Chinese characters directly, via `transformers`, aligned with
  `torchaudio.functional.forced_align`. Mandarin candidate:
  `jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn`. Cantonese
  candidate: identified in Phase 0c (Common Voice zh-HK fine-tunes).
  If a model's vocabulary is Simplified, Traditional text is converted
  with OpenCC character-by-character for alignment only.
- **Baseline** — the app's existing `.ass` for #1 and #2, shown for
  contrast only. Not re-run.

Known shared limit: forced alignment assumes the sheet is exactly what
is sung. Phase 0b removes that variable by fixing the sheet; how each
arm behaves on a mismatched sheet is a later question, not this one.

## Phases

| Phase | What | Executor | Reads it |
|---|---|---|---|
| 0 | corpus, sheets, model check (no GPU alignment) | Sonnet | Ken picks sheets |
| 1 | pilot: all arms on 4 songs, GATE Z1 | Sonnet | Opus + Ken eyeball |
| 1b | half precision next to the app's models (GATE Z1b); language guess on the pilot + English controls | Sonnet | Opus + Ken eyeball |
| 2 | corpus: H and Hal, language guess, GATE Z2 + GATE ZL | Sonnet | Opus + Ken eyeball |
| 3 | write-up: per-language pick, cost, what a build needs | Opus | Ken rules |

### Phase 0 — corpus, sheets, models

- **0a. Corpus in.** The executor adds the songs it needs (the pilot's
  #9 and #11 first) with `scripts/add_songs.py` from the
  `library_tools` branch, run from a worktree of that branch with
  `--folder d:/shared/pikaraoke-songs --yes` (the tool's default
  folder is wrong on this box), while the app is idle. Any Genius
  prompt is answered by piping `t` (transcribe) on stdin, one blank
  query line plus `t` per song, e.g. `printf '\nt\n\nt\n' |`: the
  pipeline only has to run so the `vocal/` stem exists, and its lyric
  output is ignored. A worktree's fresh `.venv` lacks `libmpv-2.dll`;
  copy it from the main checkout's `.venv\Scripts\` first. The
  executor then records per song: id, language label, duration,
  whether a `vocal/` stem exists.
- **0b. Sheet per song.** Executor fetches every text source it can
  (Genius, LRCLIB, NetEase via `syncedlyrics`) and saves each raw, side
  by side, one file per song. It also records whether NetEase offers
  word-timed lyrics (`yrc`) for the song; if it does, that file is kept
  as a possible extra reference for Phase 3, not as a gate input. Ken
  then picks or hand-edits one sheet per song so it matches the
  recording: repeats written out, credit lines (`詞：`, `曲：`) and
  section headers removed, non-Chinese lines kept as sung. The
  confirmed sheet is saved as `zh_probe/sheets/<id>.txt`.
- **0c. Models and tools.** Executor downloads each arm's model, checks
  it loads on the A2000 (peak VRAM on a 30 s clip), and for Arm H
  reports what fraction of each confirmed sheet's characters is in the
  model's vocabulary (after OpenCC if used), and for Arm R which
  characters the romanizer could not convert. Raw numbers only.

### Phase 1 — pilot (GATE Z1)

Executor runs Arms W, R, H on the pilot four and saves, per song and arm:
the JSON, the `.ass`, wall time and peak VRAM. It also writes a review
sheet per song: one row per sheet line with each arm's start time, and
blank columns for Ken. Ken plays each with
`mpv "<video>" --sub-file="<ass>"` and marks each line bad when any
character highlights visibly early or late or is skipped, plus one
overall call per song and arm: **singable as is / singable with a few
bad lines / not singable**.

**GATE Z1 (pre-registered).** Per language, an arm is dropped if Ken
calls it *not singable* on both pilot songs of that language; otherwise
it goes to Phase 2. If every arm is dropped for a language, that
language stops here and Phase 3 reports why, without a corpus run. W-L
is added to Phase 2 only under the Arm W condition above.

### Phase 1b — half precision and language guess (GATE Z1b)

Two runs on Windows, both GPU, one at a time.

- **1b-i. Half precision next to the app.** PiKaraoke runs on Windows
  with its whisper and stem workers loaded and a song playing in mpv,
  and no song processing. With that state on the card, the executor
  runs H on #1 and #2 and Hal on #9 and #11, each at full precision
  (as in Phase 1) and at half precision: model weights and inputs in
  fp16, emissions cast back to fp32 before `log_softmax` and
  `forced_align`. Per song and precision it saves the JSON and `.ass`
  (half-precision outputs only; the full-precision ones exist from
  Phase 1), align wall time, torch peak, and the **device-wide** peak
  of used memory (`nvidia-smi`, polled through the align), plus the
  device-wide figure before the probe loads its model. A full-precision
  run that OOMs is recorded as such, not retried. Ken plays the four
  half-precision `.ass` files and gives the overall call only (same
  three-way scale; no per-line marks).
- **1b-ii. Language guess.** With the app closed, a probe script loads
  the app's `large-v3-turbo.pt` and runs whisper's language detection
  on the vocal stem of the four pilot songs and four English library
  songs that have `vocal/` stems (executor's choice, ids in the log).
  It cuts the stem into consecutive 30 s windows and saves, per window,
  the stem RMS (dBFS), whisper's top three languages with
  probabilities, and p(`zh`) and p(`yue`). Per song it saves two
  guesses: **stock** (the first window only, as whisper's own
  `transcribe` would decide) and **aggregate** (the language with the
  highest summed log-probability over windows whose RMS is within 20 dB
  of the song's loudest window). On each Chinese song's confirmed sheet
  it also counts the characters from this fixed list of colloquial
  Cantonese: 嘅 咗 唔 佢 冇 啲 喺 嚟 嘢 睇 哋 嗰 噉 㗎. That is a raw
  count only. It is reported next to the guess and is not part of any gate.

**GATE Z1b (pre-registered).** Per language, the half-precision arm
replaces the full-precision one for Phase 2 if, on both pilot songs of
that language, (a) the device-wide peak leaves at least 256 MB of the
card free and (b) Ken's call is no worse than his Phase 1 call for that
arm and song. Otherwise the language runs at full precision in Phase 2,
and Phase 3 records the fallback (unload whisper while that song
aligns, then reload it), priced from the Phase 1 load times. 1b-ii has
no gate of its own; it feeds GATE ZL.

### Phase 2 — corpus (GATE Z2, GATE ZL)

Needs Phase 0a and 0b for the 12 non-pilot songs first: only the pilot
four are in the library with stems and confirmed sheets.

H on the Mandarin corpus and Hal on the Cantonese corpus, at the
precision GATE Z1b picked. Artifacts are the same as in Phase 1, except that review sheets
carry the overall call only. The 1b-ii language guess runs on every new
song too. Pilot songs are not re-run.

**GATE Z2 (pre-registered; Ken may adjust the numbers before the run,
not after).** Per language, the arm **works** if it is singable (as is,
or with a few bad lines) on at least 7 of 8 songs. The pilot calls count
(the half-precision calls if Z1b switched that language). If it works,
it is the pick for that language; if not, the language has no pick.
Ken's eyeball veto stands over the count.

**GATE ZL (pre-registered; Ken may adjust before the Phase 2 run).**
Whisper's **aggregate** guess routes correctly if it says `zh` on all 8
Mandarin songs, `yue` on all 8 Cantonese songs, and neither on the 4
English controls. If it does, Phase 3 routes on it. If it misses any song,
Phase 3 lists the misses with the stock guess and the
colloquial-character count beside each, and the build needs another
source for the label.

### Phase 3 — write-up

Opus writes the record: the pick per language (or none), its cost, and
where it failed. It also lists what a production build would need,
without committing to one: language routing (from GATE ZL), how the
model sits next to whisper on a 6 GB card (from GATE Z1b), the sheet
problems Phase 0b worked around, the caption-translation and Genius-query
issues, and how a per-character track meets the existing `.ass` writer.
Ken rules whether to plan a build.

## Out of scope

- Any change to `pikaraoke/` or to the shipped routes.
- Building language detection into the app. Measuring it is in scope since
  ruling 9 (Phase 1b-ii, GATE ZL); the alignment arms still take Ken's
  hand label.
- Lyric sourcing quality, caption-translation filtering, Genius CJK
  search: noted in Phase 3, not worked on.
- Pinyin/jyutping display, Traditional/Simplified display conversion.
- Japanese, Korean, other non-Latin scripts.
- Sheet-vs-recording mismatch handling.

## Results log

### 2026-10-20 — Phase 0 executed (Sonnet 5.5), awaiting Ken's sheets

Pilot songs only (#1, #2, #9, #11). All outputs under
`d:/shared/pikaraoke-songs/zh_probe/phase0/`; probe code in
`scripts/zh_probe/` (`corpus.py`, `fetch_sheets.py`, `phase0c_vocab.py`,
`phase0c_gpu.py`). `pikaraoke/` untouched. The probe imports only the
Genius and LRCLIB fetch clients.

**0a. Corpus in.** `add_songs.py` from the `library_tools` worktree
(`0bfa02a`), `--folder d:/shared/pikaraoke-songs --yes`, app idle, one job at
a time, stdin `\nt\n\nt\n`. Logs: `add_songs.log`,
`add_songs_qu_FSptjRic.log`.

| # | video id | lang label | video s | `vocal/` stem | stem bytes |
|---|---|---|---|---|---|
| 1 | `DYptgVvkVLQ` | zh | 318.3 | yes (already in library) | 7486396 |
| 2 | `RPWDeLqsN0g` | zh | 254.2 | yes (already in library) | 6628857 |
| 9 | `8NJVNkzhJM4` | yue | 205.0 | yes | 5103819 |
| 11 | `qu_FSptjRic` | yue | 317.6 | yes | 7968929 |

Run notes. The first call downloaded #11 in full (317.6 s) but `add_songs`
crashed on it with `UnicodeDecodeError: 'charmap'` in
`download_manager._execute_download` (`process.communicate()`, cp1252 decode
of yt-dlp output), reported "Failed: 1", and ran the pipeline for #9 only. A
`--dry-run` then listed #11 as "in library, not processed"; a second call with
`PYTHONUTF8=1` and stdin `\nt\n` ran its pipeline. `add_songs` was not edited.
The pipeline's own lyric outputs for #9 and #11 (`karaoke/`, `subtitles/`) are
ignored per the Ground rules.

**0b. Sources fetched, not chosen.** Per song:
`zh_probe/phase0/sheets_raw/<video id>/` holds every raw source file, an
`index.json`, and `sources.txt`, which stacks the distinct texts under a header
line naming each source (identical texts share one block). Ken's confirmed
sheet goes to `zh_probe/sheets/<video id>.txt`; nothing there yet.

| # | Genius files | LRCLIB `.txt` | NetEase `.lrc` | NetEase word-timed | distinct texts in `sources.txt` |
|---|---|---|---|---|---|
| 1 | 2 | 45 | 1 (`186016`, by hand) | `yrc` no, `klyric` no | 9 |
| 2 | 2 | 44 | 2 (`186160` by hand; `3319986894` is a cover with no Han text) | no, no | 12 |
| 9 | 1 | 40 | 1 (`65952`) | `yrc` **yes** (`netease_65952.yrc`), `klyric` no | 5 |
| 11 | 1 | 40 | 1 (`1357375695`) | no, no | 5 |

Fetch notes. LRCLIB is searched with Traditional, Simplified and English
track/artist keys; records whose track name does not contain any of the
song's titles are dropped (the id list is in each `index.json`
`lrclib_dropped` row); an empty LRCLIB answer is retried up to 3 times
because `lrclib.search` returns `[]` on a 503. NetEase's search hides Jay
Chou's official tracks (only covers return for 晴天 and 龍捲風), but
`/api/song/lyric?id=` serves them: ids `186016` (晴天) and `186160` (龙卷风)
were looked up by hand from the artist's album listing and are set in
`corpus.py`. `lrc` bodies include credit lines (作词 etc.). Genius text is
the `lyricsgenius` scrape with section headers removed, as the app fetches it.

**0c. Models and tools.** `large-v3-turbo.pt` from the main checkout's
`models/` (1618 MB). Downloads to default caches (snapshot sizes include every
format in the repo): `jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn`
2552 MB; `scottykwok/wav2vec2-large-xlsr-cantonese` 3796 MB;
`alvanlii/wav2vec2-BERT-cantonese` 4538 MB; torchaudio `MMS_FA` (torch hub
cache). Packages via `uv run --with`: transformers, huggingface_hub, pypinyin,
jieba, ToJyutping, opencc-python-reimplemented, syncedlyrics.

Cantonese Arm H candidates found on the Hub (all Common Voice zh-HK):

| model | downloads | weights MB | vocab tokens | license |
|---|---|---|---|---|
| `scottykwok/wav2vec2-large-xlsr-cantonese` | 32115 | 1276 | 3555 | cc-by-sa-4.0 |
| `ctl/wav2vec2-large-xlsr-cantonese` | 1202 | 1277 | 3581 | apache-2.0 |
| `w11wo/wav2vec2-xls-r-300m-zh-HK-v2` | 34 | 1277 | 3653 | apache-2.0 |
| `alvanlii/wav2vec2-BERT-cantonese` | 4049 | 2434 | 2697 | apache-2.0 |
| `jonatasgrosman/...-chinese-zh-cn` (Mandarin) | 1838246 | 1276 | 3503 | apache-2.0 |

Vocabulary and romanizer coverage was computed for all five. Peak VRAM was
measured for the Mandarin model plus `scottykwok` and `alvanlii` only; `ctl` and
`w11wo` were not downloaded. Columns are Han characters in the text that are in
the model vocabulary raw / after per-character OpenCC `t2s` / after `s2t`. "R
failed" is Han characters with no reading from pypinyin (zh) or ToJyutping
(yue). Candidate texts stand in for the confirmed sheets; `phase0c_vocab.py`
re-runs on `sheets/<id>.txt` once those exist (listed as `CONFIRMED`).

#1 (`jonatasgrosman` zh-cn):

| text | han | R failed | raw/t2s/s2t |
|---|---|---|---|
| genius_6347511 | 477 | 0 | 365/473/365 |
| genius_6666632 | 362 | 0 | 359/359/279 |
| lrclib_20129676 | 478 | 0 | 367/474/367 |
| lrclib_21669952 | 490 | 0 | 486/486/373 |
| lrclib_21715222 | 498 | 0 | 378/494/378 |
| lrclib_24316052 | 489 | 0 | 373/485/371 |
| lrclib_30010752 | 362 | 0 | 276/359/276 |
| netease_186016 | 546 | 0 | 542/542/409 |

#2 (`jonatasgrosman` zh-cn):

| text | han | R failed | raw/t2s/s2t |
|---|---|---|---|
| genius_425304 | 253 | 0 | 187/251/187 |
| genius_7581612 | 476 | 0 | 472/472/370 |
| lrclib_13116435 | 476 | 0 | 360/472/360 |
| lrclib_16478482 | 492 | 0 | 373/488/373 |
| lrclib_17422839 | 475 | 0 | 359/471/359 |
| lrclib_18801737 | 475 | 0 | 359/471/359 |
| lrclib_23725471 | 500 | 0 | 495/495/377 |
| lrclib_24807575 | 476 | 0 | 360/472/360 |
| lrclib_30295911 | 433 | 0 | 327/433/327 |
| netease_186160 | 573 | 0 | 566/566/415 |
| netease_3319986894 | 0 | - | - |

#9 (yue; column per model, raw/t2s/s2t):

| text | han | R failed | scottykwok | ctl | w11wo | alvanlii |
|---|---|---|---|---|---|---|
| genius_5401147 | 290 | 0 | 288/220/285 | 288/220/285 | 288/220/288 | 287/218/284 |
| lrclib_17464933 | 286 | 0 | 284/216/281 | 284/216/281 | 284/216/284 | 282/214/280 |
| lrclib_19120435 | 290 | 0 | 288/220/285 | 288/220/285 | 288/220/288 | 286/218/284 |
| netease_65952 | 315 | 0 | 231/231/309 | 231/231/309 | 231/231/312 | 230/230/309 |

#11 (yue):

| text | han | R failed | scottykwok | ctl | w11wo | alvanlii |
|---|---|---|---|---|---|---|
| genius_4642002 | 345 | 0 | 343/256/343 | 343/256/343 | 343/256/343 | 339/254/339 |
| lrclib_18238243 | 325 | 0 | 323/239/323 | 323/239/323 | 323/239/323 | 319/237/319 |
| lrclib_33352647 | 345 | 0 | 254/254/343 | 254/254/343 | 254/254/343 | 252/252/339 |
| netease_1357375695 | 340 | 0 | 246/246/338 | 246/246/338 | 246/246/338 | 244/244/332 |

Characters not in vocabulary after the best conversion (from
`phase0c_vocab.txt`): zh-cn model, 颳 x3 and 盪 x1 on #1, 悄 x4 on #2;
Cantonese models, 褥 x2 on #9, 恍 and 惚 on #11; `alvanlii` also 瀉 on #9 and 羈
x4 on #11. The romanizer failure check was tested against a rare-character
string (ToJyutping returns `None` for 𠮷; pypinyin path patched to a sentinel
after the first draft would have raised on a failure).

Load check on the RTX A2000 (6138 MB), one 30 s clip of the vocal stem from
60 s (#1 clip RMS -23.9 dB, #9 clip RMS -17.4 dB), fp32, torch `max_memory_*`
(excludes the CUDA context). Whisper arm ran `transcribe` with the language
label, since no sheet is confirmed yet.

| arm | song / lang | model | load s | load peak alloc / reserved MB | infer s | infer peak alloc / reserved MB | output frames |
|---|---|---|---|---|---|---|---|
| W | 1 / zh | `large-v3-turbo.pt` | 10.43 | 3159 / 3230 | 15.05 (first CUDA call) | 3638 / 3848 | 10 segments |
| W | 9 / yue | `large-v3-turbo.pt` | 9.76 | 3167 / 3250 | 2.04 | 3567 / 3770 | 3 segments |
| R | 1 | MMS_FA | 3.69 | 1213 / 1226 | 0.72 | 1971 / 2078 | 1499 x 28 |
| R | 9 | MMS_FA | 3.60 | 1213 / 1226 | 0.57 | 1971 / 2078 | 1499 x 28 |
| H | 1 / zh | `jonatasgrosman` zh-cn | 6.31 | 1227 / 1240 | 0.66 | 1983 / 2092 | 1499 x 3503 |
| H | 9 / yue | `scottykwok` | 3.81 | 1227 / 1240 | 0.63 | 1983 / 2092 | 1499 x 3555 |
| H | 9 / yue | `alvanlii` w2v-BERT | 6.94 | 2329 / 2344 | 1.39 | 3214 / 3258 | 750 x 2699 |

Frame stride: 20 ms for MMS_FA and the two XLSR models (1499 frames in 30 s),
40 ms for `alvanlii` (750 frames). The whisper and greedy-decode texts for each
clip are in `phase0c_gpu.json` and are not read here.

Artifacts:

- `zh_probe/phase0/add_songs.log`, `add_songs_qu_FSptjRic.log`
- `zh_probe/phase0/sheets_raw/<video id>/` (`sources.txt`, `index.json`, raw files)
- `zh_probe/phase0/phase0c_vocab.json`, `phase0c_vocab.txt`
- `zh_probe/phase0/phase0c_gpu.json`, `phase0c_gpu.log`

Open for Ken: pick or hand-edit one sheet per pilot song into
`zh_probe/sheets/<video id>.txt` (repeats written out, credit lines and section
headers removed, non-Chinese lines kept as sung). Phase 1 is blocked on that.

### 2026-10-20 — Phase 0b narrowing aid: whisper transcript vs each candidate (Sonnet 5.5)

Ken asked whether transcribing the vocal stems could narrow the candidate
texts. Nothing here picks a sheet; the pick is still Ken's. New code in
`scripts/zh_probe/`: `phase0b_transcribe.py` (GPU), `phase0b_score.py` (CPU,
re-runnable, includes the `CONFIRMED` sheet once saved). The candidate-text
helpers moved from `phase0c_vocab.py` into `corpus.py`; `phase0c_vocab.py`
re-run afterwards gave byte-identical `phase0c_vocab.json` and `.txt`.

Method. Whisper `large-v3-turbo.pt` on the full `vocal/` stem (16 kHz mono),
`language` = the song's label, `condition_on_previous_text=False`, app idle.
Each candidate (credit lines such as `词：`/`曲：` dropped first) and the
transcript are reduced to Han characters, converted to Simplified one character
at a time, with 著/着 and 妳/你 folded. `lcs` is the longest common subsequence
of the two strings; recall = lcs / transcript Han, precision = lcs / candidate
Han, f1 their harmonic mean. `diff` is the character count a candidate differs
by from the top row (difflib). Identical texts share a row (first file shown).

| # | segments | whisper wall s | transcript Han |
|---|---|---|---|
| 1 | 59 | 23 | 415 |
| 2 | 66 | 13 | 466 |
| 9 | 39 | 8 | 269 |
| 11 | 43 | 41 | 317 |

On #11 the first two segments (0.0-21.4 s) are non-Chinese text and add no Han
characters. Visible in the transcripts: homophone errors, Mandarin spellings
for the Cantonese songs, and a short last segment on #1 (210.5 s).

#1 晴天:

| text | source | f1 | recall | prec | lcs | han | credit lines dropped | diff |
|---|---|---|---|---|---|---|---|---|
| lrclib_24316052 | lrclib 晴天 / 周杰倫, 270.0 s | 0.799 | 0.860 | 0.745 | 357 | 479 | 1 | 0 |
| genius_6347511 | genius 晴天 (Sunny Day) | 0.798 | 0.858 | 0.746 | 356 | 477 | 0 | 2 |
| lrclib_20129676 | lrclib 晴天 / 周杰伦, 269.0 s | 0.797 | 0.858 | 0.745 | 356 | 478 | 0 | 2 |
| lrclib_21669952 | lrclib 晴天 / 周杰倫, 葉惠美 | 0.796 | 0.860 | 0.741 | 357 | 482 | 2 | 8 |
| lrclib_21715222 | lrclib 晴天 / 周杰倫, 叶惠美 | 0.789 | 0.860 | 0.729 | 357 | 490 | 2 | 16 |
| netease_186016 | netease 186016 | 0.770 | 0.860 | 0.697 | 357 | 512 | 5 | 38 |
| lrclib_30010752 | lrclib Sunny Day (Live), 250.0 s | 0.731 | 0.684 | 0.785 | 284 | 362 | 0 | 120 |
| genius_6666632 | genius 晴天 / Andy Luidje (Ft. 周杰倫) | 0.726 | 0.680 | 0.779 | 282 | 362 | 0 | 117 |

#2 龍捲風:

| text | source | f1 | recall | prec | lcs | han | credit lines dropped | diff |
|---|---|---|---|---|---|---|---|---|
| lrclib_17422839 | lrclib 龙卷风 / 周杰伦, The One演唱会 CD2 | 0.899 | 0.908 | 0.891 | 423 | 475 | 0 | 0 |
| lrclib_13116435 | lrclib 龍捲風 / 周杰倫, JAY | 0.898 | 0.908 | 0.889 | 423 | 476 | 0 | 1 |
| lrclib_24807575 | lrclib Tornado / Jay Chou, Jay | 0.898 | 0.908 | 0.889 | 423 | 476 | 0 | 3 |
| lrclib_18801737 | lrclib 龍捲風 / 周杰倫, 魔天倫世界巡迴演唱會 | 0.897 | 0.906 | 0.888 | 422 | 475 | 0 | 1 |
| lrclib_23725471 | lrclib 龙卷风 / 周杰伦, 254.0 s | 0.893 | 0.908 | 0.879 | 423 | 481 | 4 | 6 |
| lrclib_16478482 | lrclib 龍捲風 Tornado / Jay Chou | 0.881 | 0.906 | 0.858 | 422 | 492 | 0 | 18 |
| genius_7581612 | genius 龍捲風 (Tornado) / 五月天 (Ft. 周杰倫) | 0.834 | 0.843 | 0.826 | 393 | 476 | 0 | 81 |
| netease_186160 | netease 186160 | 0.831 | 0.908 | 0.766 | 423 | 552 | 6 | 77 |
| genius_425304 | genius 龍捲風 (Tornado) / 周杰倫 | 0.623 | 0.481 | 0.885 | 224 | 253 | 0 | 222 |
| lrclib_30295911 | lrclib Big Ben + Secret Sign + Rainbow + Tornado (Live) | 0.345 | 0.333 | 0.358 | 155 | 433 | 0 | 649 |
| netease_3319986894 | netease Tornado / 短腿柯基 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 475 |

#9 明年今日:

| text | source | f1 | recall | prec | lcs | han | credit lines dropped | diff |
|---|---|---|---|---|---|---|---|---|
| genius_5401147 | genius 明年今日 (Next Year Today) | 0.826 | 0.859 | 0.797 | 231 | 290 | 0 | 0 |
| lrclib_19120435 | lrclib 明年今日, DUO演唱会 | 0.826 | 0.859 | 0.797 | 231 | 290 | 0 | 0 |
| netease_65952 | netease 65952 | 0.826 | 0.859 | 0.797 | 231 | 290 | 5 | 0 |
| lrclib_17464933 | lrclib 明年今日, 48首選, 205.2 s | 0.825 | 0.851 | 0.801 | 229 | 286 | 0 | 4 |

#11 海闊天空:

| text | source | f1 | recall | prec | lcs | han | credit lines dropped | diff |
|---|---|---|---|---|---|---|---|---|
| genius_4642002 | genius 海闊天空 (Boundless Oceans, Vast Skies) | 0.804 | 0.839 | 0.771 | 266 | 345 | 0 | 0 |
| lrclib_33352647 | lrclib 海阔天空 / Beyond, 华纳廿三周年纪念精选系列 | 0.804 | 0.839 | 0.771 | 266 | 345 | 0 | 7 |
| lrclib_18238243 | lrclib 海闊天空 / Beyond, 326.0 s | 0.769 | 0.779 | 0.760 | 247 | 325 | 0 | 24 |
| netease_1357375695 | netease 海阔天空 / Beyond | 0.769 | 0.779 | 0.760 | 247 | 325 | 3 | 25 |

Artifacts:

- `zh_probe/phase0/transcripts/<video id>.json` (segments with times) and `.txt`
- `zh_probe/phase0/phase0b_score.json`, `phase0b_score.txt` (the tables above)
- `zh_probe/phase0/phase0b_diffs.txt`: for every candidate within 0.05 f1 of the
  top row, each place it differs from the top row (2 characters of context), the
  start-end time of the transcript segment that place aligns to (the last matched
  character before it when whisper wrote nothing there, so approximate), and
  whether each variant, with its context, appears in whisper's text within one
  segment either side. A difference shared by several candidates is one line.
  The first version of this file tested the whole transcript instead of one
  segment either side, which a phrase sung several times satisfies from another
  place in the song; it was replaced the same day.

Whisper's transcript is not the sung text, so these numbers rank resemblance to
what whisper heard and nothing more. The open item for Ken is unchanged.

### 2026-10-27 — sheets confirmed; Phase 1 runner built (Sonnet 5.5), GPU run next

**Sheets.** A Chinese-speaking friend of Ken's filled in a worksheet (claude.ai
artifact `EqY8foQNriiDuW8pCnavYE`): per pilot song a starting sheet (its
version A, raw files in `phase0/worksheet_labels.json`) plus listening
questions at each place the candidates differ. Their pasted result is saved verbatim as
`zh_probe/phase0/worksheet_result.txt`; the four confirmed sheets are
`zh_probe/sheets/<video id>.txt`. Each is the friend's sheet text with only
these edits, all ratified by Ken 2026-10-27: the friend's
`(music break in video)` marker on #1 dropped (an instrumental break, not
sung); and on #1 three places where their typed sheet disagreed with their own
ticked listening answers: 3:01 second chorus `我還留著 yeah` -> `我還留著`,
4:41 last chorus `我才能在你身邊` -> `我才能夠在你身邊` (they heard 够; the
sheet is Traditional), 4:51 last chorus `但偏偏 風漸漸` -> `但偏偏 雨漸漸`.
#2, #9 and #11 are the friend's text unchanged. On #11 the friend left the
2:27 question unanswered; the sheet keeps 那 there, as in their 1:28 answer.

| # | sheet lines | Han characters | Latin words |
|---|---|---|---|
| 1 | 40 | 450 | 17 (solfege, `Re-sol-sol-si-do-si-la` etc.) |
| 2 | 24 | 477 | 2 (`Baby`) |
| 9 | 22 | 290 | 0 |
| 11 | 35 | 345 | 14 (`Oh no`, `Oh yeah`) |

**Phase 1 runner.** `scripts/zh_probe/`: `sheet.py`, `track.py`, `arms.py`,
`phase1_run.py` (GPU), `phase1_review.py` (CPU); `corpus.py` gained two
environment overrides for the dev VM. Choices the judge should know about:

- **Unit.** One per Han character and one per Latin word; spaces and
  punctuation stay in the display text and are not timed. All arms time the
  same units.
- **Arm W.** `stable_whisper` `align`, `original_split=True` (one segment per
  sheet line), every other option at its default. Whisper's words (a token each,
  often several characters) are mapped back onto units; a word that spans
  several units splits evenly and marks them `shared`.
- **Arm R.** Pinyin: OpenCC `t2s`, `jieba` segmentation, `pypinyin` without
  tones. Jyutping: `ToJyutping`, digits stripped. Latin words are used
  lower-cased as written. MMS_FA via `torchaudio`.
- **Arm H.** Three models, since the Cantonese pick was left open in Phase 0c:
  `H` = `jonatasgrosman` zh-cn (Mandarin songs), `Hsk` = `scottykwok` and `Hal`
  = `alvanlii` w2v-BERT (Cantonese songs). Each character looks up its own
  token, then its other case, then OpenCC `t2s`, then `s2t`; a unit with no
  token is placed evenly between its neighbours' onsets and marked
  `interpolated`.
- **CTC arms (R, H).** Per song, 30 s windows each shown 2 s of neighbouring
  audio that is then dropped, log-probabilities concatenated, then
  `torchaudio.functional.forced_align` on CPU. A unit runs from its first
  token's first frame to its last token's end frame.
- **`.ass`.** One event per sheet line, shown 1.5 s before its first character
  until 0.5 s after its last. Each character sweeps from its start to the next
  character's start; a line's last character from its start to its end, at
  least 0.2 s. Same writer for every arm.
- **stable-ts and Cantonese.** `stable-ts` 2.19.1 (`alignment.py`, the
  `split_words_by_space` lines) splits words by character only for `zh`, `ja`,
  `th`, `lo`, `my`; `yue` is missing, though whisper's own tokenizer lists it.
  Smoke test on #9 without a workaround: 44 words for 290 characters, all 290
  `shared`, 48 zero-length. Arm W therefore passes `align` a whisper `yue`
  tokenizer whose `language_code` is set to `zh`, which is the only thing
  stable-ts reads for that decision; the decoder still gets the `yue` token.
  With it, #9: 266 words, 48 `shared`, 4 zero-length. Mandarin is unpatched.
- **Output.** `zh_probe/phase1/<video id>/<arm>.{json,ass}` (JSON carries wall
  time and peak VRAM, load and align separately), `review_<video id>.csv`,
  `commands.txt` (mpv per song and arm, plus the app's existing `.ass` for #1
  and #2), `runs.txt` (raw run table).

Smoke test, not Phase 1 data: the dev VM has no GPU (torch 2.11, CPU fp32),
so every arm was run end to end on CPU against a scratch library, W and R on
#1 and #9, H on #1, Hsk and Hal on #9, plus the review script; nothing was
written to `zh_probe/phase1/`. Not yet run on the A2000: peak VRAM of the CTC
windows and of W's align on a 5-minute stem. The first W align on CUDA will
include CUDA start-up (15 s in Phase 0c).

### 2026-10-27 — Phase 1 GPU run (Sonnet 5.5), artifacts saved, awaiting Ken's calls

Ken ran `phase1_run.py` and then `phase1_review.py` on Windows (RTX A2000,
6 GB; output on D:, read here over the RDP redirect). Code is `9a3823a`;
nothing in `pikaraoke/` or the lock files changed. Every arm ran on every song
of its languages (all 14 artifact pairs exist, so no arm-song failed). Arms W, R and H on #1 and #2;
W, R, Hsk and Hal on #9 and #11: 14 artifact pairs.

Saved under `zh_probe/phase1/`: `<video id>/<arm>.json` and `.ass` for each of
the 14, `review_<video id>.csv` (4), `commands.txt`, `runs.txt` (the table
below, verbatim columns). The `.ass` paths in `commands.txt` are Windows
paths, as Ken ran the review script there.

Mechanical check of the 14 JSONs (data validity only, not quality): unit
counts equal the sheet's (467, 479, 290, 359) and every sheet line has units;
in every file unit starts are non-decreasing and no unit ends before it starts.

**Run table** (`runs.txt`; load and align are separate, MB are torch peak
allocated / reserved around the call):

| song | arm | align s | align peak MB | units | shared | interpolated | zero-duration | frames |
|---|---|---|---|---|---|---|---|---|
| #1 | W | 28.05 | 3763 / 4310 | 467 | 56 | 0 | 120 | |
| #1 | R | 10.12 | 2069 / 2880 | 467 | 0 | 0 | 0 | 15914 |
| #1 | H | 5.80 | 2081 / 2894 | 467 | 0 | 4 | 0 | 15914 |
| #2 | W | 18.75 | 3763 / 4004 | 479 | 71 | 0 | 20 | |
| #2 | R | 4.37 | 2069 / 2882 | 479 | 0 | 0 | 0 | 12711 |
| #2 | H | 4.11 | 2081 / 2894 | 479 | 0 | 4 | 0 | 12711 |
| #9 | W | 6.48 | 3763 / 4004 | 290 | 48 | 0 | 4 | |
| #9 | R | 4.24 | 2069 / 2880 | 290 | 0 | 0 | 0 | 10250 |
| #9 | Hsk | 3.53 | 2081 / 2894 | 290 | 0 | 2 | 0 | 10250 |
| #9 | Hal | 10.76 | 3457 / 4088 | 290 | 0 | 3 | 0 | 5125 |
| #11 | W | 9.04 | 3763 / 4004 | 359 | 58 | 0 | 8 | |
| #11 | R | 4.86 | 2069 / 2880 | 359 | 0 | 0 | 0 | 15879 |
| #11 | Hsk | 5.13 | 2081 / 2894 | 359 | 0 | 16 | 0 | 15879 |
| #11 | Hal | 16.31 | 3457 / 4088 | 359 | 0 | 6 | 0 | 7940 |

**Model load** (once per arm; the same figures repeat on each of its songs in
`runs.txt`):

| arm | model | load s | load peak MB (alloc / reserved) |
|---|---|---|---|
| W | large-v3-turbo.pt | 12.84 | 3159 / 3230 |
| R | torchaudio MMS_FA | 5.38 | 1212 / 1224 |
| H | jonatasgrosman zh-cn | 137.2 | 1226 / 1238 |
| Hsk | scottykwok cantonese | 4.22 | 1226 / 1238 |
| Hal | alvanlii w2v-BERT cantonese | 9.38 | 2329 / 2346 |

The 137.2 s for H is the first model loaded by the run (arm order W, R, H, Hsk,
Hal puts it third; not investigated, so not attributed). Align peaks are
identical per arm across songs, as expected if one fixed-size window sets the
peak (inference, not checked). Frame counts: 20 ms per frame for R, H and Hsk
(#1: 15914 frames for the stem), 40 ms for Hal (half as many).

**First start and last end per song and arm** (seconds in the stem; from the
JSONs):

| song | W | R | H / Hsk | Hal |
|---|---|---|---|---|
| #1 | 44.24 -> 274.14 | 43.98 -> 301.92 | 44.00 -> 301.56 | |
| #2 | 28.50 -> 254.24 | 28.14 -> 254.22 | 28.06 -> 238.18 | |
| #9 | 16.70 -> 181.88 | 16.64 -> 186.96 | 16.66 -> 181.68 | 16.56 -> 181.56 |
| #11 | 19.00 -> 261.38 | 18.98 -> 313.84 | 19.02 -> 259.82 | 18.96 -> 259.68 |

No verdicts here. Per `review_<video id>.csv`, Ken plays each arm with the
`commands.txt` line, marks bad lines, and gives one overall call per song and
arm (singable as is / singable with a few bad lines / not singable). Opus
reads GATE Z1 from those calls. Both Cantonese H candidates were run, so the
read also has to say which one stands for H in Phase 2 if H survives.

### 2026-10-30 — Phase 1 eyeball calls recorded (Sonnet 5.5), GATE Z1 not yet read

Ken entered an overall call for each of the 14 arm-song outputs in the Pilot
Listening Sheet, a private artifact
(https://claude.ai/artifact/3moyiEpQwFu36GHUVpuGxv, built from
`review_<video id>.csv` and `commands.txt`; sheet-line times shown per arm).
The page stores its marks in collection `marks`, one document per video id;
this entry is those four documents read back with `ArtifactData` (versions
and last-saved times below), nothing re-derived.

Ken said the winners were clear to him, so he **skipped the line-by-line
section**. Every per-line `bad` list is empty and there are no line notes, so
an empty list here means *not marked*, not *no bad lines*. His evidence is the
overall calls and the arm notes below.

**Overall calls** (store values `as_is` / `few_bad` / `not_singable`; blank =
arm not run on that song):

| song | lang | W | R | H | Hsk | Hal |
|---|---|---|---|---|---|---|
| #1 晴天 `DYptgVvkVLQ` | zh | not singable | few bad | as is | | |
| #2 龍捲風 `RPWDeLqsN0g` | zh | few bad | few bad | as is | | |
| #9 明年今日 `8NJVNkzhJM4` | yue | few bad | as is | | as is | as is |
| #11 海闊天空 `qu_FSptjRic` | yue | few bad | not singable | | few bad | as is |

**Hsk-vs-Hal pick field** (the sheet's Cantonese question): #9 `Hal`; #11
left blank.

**Arm notes**, verbatim (spelling as typed; `base` cards had no marks):

- #1 晴天 (doc v42, saved 2026-10-30 18:01Z)
  - W: "fast line at 2:40, missed lines till 3:00, slow crawl at 3:15, fast
    crawls over cello break, rap totally missing"
  - R: "the sol-la-si section is rushed, same lines over break at 2:40, slow
    crawl over cello break, rap appears"
  - H: "sol-la-si section slightly rushed, breaks have no problems, rap comes
    in slightly late but catches up quickly"
- #2 龍捲風 (doc v50, saved 2026-10-30 17:28Z)
  - W: "onset snap isn't working very well, 2 slow crawls, one just before the
    instrumental break, and the last line (likely because it trails to
    silence)"
  - R: "start end timing better first half, less so after, better than
    whisper, slow crawl only at the end, but missing the choruses around
    3:20-3:35"
  - H: "best character timing of the 3, tight onset, mostly missed held
    endings, only one to stick the ending that trails to silence"
- #9 明年今日 (doc v34, saved 2026-10-30 18:11Z)
  - W: "slow crawl over instrumentals at 1:40, loose word timings with some
    weird jumps, "
  - R: "tighter timing than whisper, better onset/endings, no slow crawl"
  - Hsk: "best word timing, though it loses to romanized for onset/endings"
  - Hal: "best of the bunch"
- #11 海闊天空 (doc v29, saved 2026-10-30 18:17Z)
  - W: "slow crawl 1:35, lines during the break at 2:40 (the lines are not
    there, the video has hard subs to compare to)"
  - R: "some slow crawls, onset ending misses, massive missed around 4:01 from
    which it never recovers"
  - Hsk: "some onset/ending misses, some rushed lines, some slow crawls"
  - Hal: "best of the bunch"

No verdicts here. The GATE Z1 rule is not applied in this entry. Opus reads
it from the table above, and picks Hsk or Hal for Phase 2 if H survives for
Cantonese. The marks live only in the artifact's store and in this entry;
nothing was written to the library.

**Addendum, same day, Ken in chat after the marks were read back** (not in the
sheet's store; this fills the blank `cantonese_h` on #11): "Hal is better than Hsk for
both songs, and makes for almost perfect karaoke output". So Ken's Hsk-vs-Hal
preference is Hal on both Cantonese songs. His overall calls for Hsk and Hal
are unchanged and stay as in the table.

### 2026-10-30 — GATE Z1 read (Opus 5.5)

Read from the overall calls and the addendum in the entry above, against
the rule as pre-registered under Phase 1. Per-line marks were skipped, so
only the overall calls and the arm notes are evidence here. Nothing was
re-run and the listening artifact was not re-read.

Rule: per language, an arm is dropped only if it is *not singable* on both
pilot songs of that language.

| lang | arm | pilot calls | not singable on both? | Phase 2 |
|---|---|---|---|---|
| zh | W | #1 not singable, #2 few bad | no | goes |
| zh | R | #1 few bad, #2 few bad | no | goes |
| zh | H | #1 as is, #2 as is | no | goes |
| yue | W | #9 few bad, #11 few bad | no | goes |
| yue | R | #9 as is, #11 not singable | no | goes |
| yue | H (Hsk) | #9 as is, #11 few bad | no | H goes, as Hal |
| yue | H (Hal) | #9 as is, #11 as is | no | H goes, as Hal |

**Read.** No arm is dropped in either language, so neither language stops
here. Phase 2 runs W, R, H on the Mandarin corpus and W, R, Hal on the
Cantonese corpus.

**H for Cantonese is Hal.** Both candidates pass the gate. Hal is called
*as is* on both songs, Hsk on one; Ken's notes call Hal "best of the bunch"
on both, and his addendum prefers Hal on both songs ("almost perfect karaoke
output"). Hsk is not carried into Phase 2. Cost against Hsk on the pilot:
align about 3x slower (10.76 vs 3.53 s on #9, 16.31 vs 5.13 s on #11)
and about 1.4 GB more peak allocated (3457 vs
2081 MB), within the A2000's 6 GB.

**W-L is not added.** Its condition (Arm W not singable on Cantonese at the
pilot) is not met: W is *few bad* on both Cantonese songs.

**Carried into GATE Z2** (facts from the rule, not new verdicts). Z2 counts
8 songs per language and the pilot songs are not re-run, so their calls
count. Mandarin W and Cantonese R each start with one *not singable*, so
either fails Z2's 7-of-8 on one more. Z2's second tie-break (fewest bad
lines in total) needs per-line marks, which the pilot does not have.

**Before Phase 2 can run.** Only the four pilot songs are in the library
with stems, and only their sheets exist in `zh_probe/sheets/`. Phase 2
needs Phase 0a (add the other 12 songs) and 0b (Ken confirms 12 sheets)
first. Z2's numbers may be adjusted only before the run.

### 2026-10-30 — Ken's rulings after the Z1 read; co-residency estimate (Opus 5.5)

Rulings 7-9 (top of plan) came out of this exchange. Ken asked what retiring
W would cost in model loading if whisper stays loaded. The estimate he ruled
on is below. It is an estimate made by combining figures from separate runs,
not a co-residency measurement; Phase 1b-i measures it.

Sources: this plan's Phase 0c load check and Phase 1 run table (fp32, torch
peaks, no CUDA context); `archive/jointrefine:plans/matcher-timing-eval.md`,
"Concurrency measurement (2026-06-22)", A2000 6 GB: whisper + stem worker
co-resident (weights + 2 CUDA contexts) about 4.65 GB, about 5.5 GB at
concurrent peak with mpv's ~300 MB; the separator model is 871 MiB.

| next to whisper (separator unloaded) | arm align peak MB | estimated device total |
|---|---|---|
| H (zh) | 2081 | about 6.1 GB of 6.0 |
| Hal (yue) | 3214-3457 | about 7.3 GB |
| Hsk (yue) | 2081 | about 6.1 GB |

Load times (s): whisper 9.8-12.8, Hal 6.9-9.4, H 6.3 (Phase 0c; the 137.2
in the Phase 1 run is not explained and not used), Hsk 3.8-4.2. The fallback
of unloading whisper for a Chinese song costs one Hal or H load plus one
whisper reload, about 20 s per switch between languages. Ken chose: test half precision
first (Phase 1b-i), fall back to the unload. In the fallback, whisper is still
loaded when a song arrives, so it can guess the language before it is
unloaded.

Language guess design (Phase 1b-ii, GATE ZL), chosen by Opus at Ken's
request to place it: whisper's detection on the vocal stem is the candidate
router because whisper is already loaded and the check is cheap. Its
reliability on singing, and on `yue` against `zh` in particular, is
unmeasured: every probe run so far was given Ken's label. The sheet's
colloquial-character count is recorded beside it because it
catches only colloquial lyrics (海闊天空 is mostly standard written Chinese),
so it is evidence, not a router. English controls are there to check that
no English song would be routed to a Chinese model; the corpus alone cannot
show that.

### 2026-11-03 — Phase 1b scripts built (Sonnet 5.5), GPU runs next

Code is `8452230`: `scripts/zh_probe/phase1b_half.py` (1b-i), `phase1b_lang.py`
(1b-ii) and a small change to `arms.py`. Nothing in `pikaraoke/` or the lock
files changed. No GPU run has happened; this entry holds no results.

**Commands** (Windows, PowerShell, in the Windows clone's `chinese_karaoke`
worktree, `C:\temp\Github\pikaraoke\.claude\worktrees\chinese_karaoke`, where that
branch is checked out; no model downloads: H and Hal are in the Hugging Face
cache from Phase 1, whisper is `models\large-v3-turbo.pt`). 1b-ii first, with
the app closed:

```
cd C:\temp\Github\pikaraoke\.claude\worktrees\chinese_karaoke
git fetch vm; git merge --ff-only vm/chinese_karaoke
$env:PYTHONUTF8 = "1"
uv run python scripts/zh_probe/phase1b_lang.py
```

Then 1b-i, with PiKaraoke open (whisper and stem workers loaded, a song playing
in mpv, no song processing) and left alone while it runs:

```
$env:PYTHONUTF8 = "1"
uv run --with transformers --with huggingface_hub --with opencc-python-reimplemented `
  python scripts/zh_probe/phase1b_half.py
```

**Outputs** under `zh_probe/phase1b/`:

- 1b-i: `half_runs.txt` / `half_runs.json` (one row per song, arm and precision;
  failures are rows, not exits), `half/<video id>/<arm>.{json,ass}` for fp16
  runs only, `commands.txt` (mpv line per fp16 `.ass`, for Ken's overall call).
  The script prints the device-wide memory used before it loads anything; the
  Phase 1b-i estimate for the app in this state is about 5 GB, so a figure far
  below that means the workers are not loaded.
- 1b-ii: `lang/<video id>.json` per song, `lang_songs.txt` (one row per song),
  `lang_windows.txt` (one row per window).

**Choices the judge should know.**

- **fp16 (`arms.py`).** `make_arm(name, half=True)` converts the Hugging Face
  model's weights to fp16 on the CPU and then moves them to the card; the
  features are cast to fp16; the emission is cast to fp32 before `log_softmax`
  and `forced_align` (that cast was already in the code). W and R refuse
  `half`. The CTC run info gained `nonfinite`, a count of NaN or inf entries in
  the emission, because fp16 can overflow without raising. The fp32 path is
  otherwise unchanged (Phase 1's load sizes, H 1226 MB and Hal 2329 MB, are
  fp32-sized).
- **Device-wide memory.** One `nvidia-smi --id=0` call after another on a
  thread (no sleep), so the rate is one call's duration; `device_samples` is the
  reading count behind each peak. Peaks cover the model load and each align,
  plus one reading taken after the block ends. `device_before_load_mb` is read
  before each model load (so the fp16 load's figure includes the CUDA context
  left by the fp32 pass); the figure before the probe touches the card is the
  first line the script prints, and it is read again just before the first
  load (H, fp32). `device_total_mb` is nvidia-smi's total; free at peak is not
  computed. On a CUDA run the script exits if nvidia-smi cannot be read.
- **Failures.** Any `ValueError` or `RuntimeError` in a load or align becomes a
  row; "out of memory" or `ALLOC_FAILED` in the message sets `status` to `oom`,
  anything else to `error` (traceback printed). A failed run is not retried. A
  rerun with `--arms` or `--songs` keeps the other rows (merged on song, arm,
  precision).
- **Run order.** For each arm: fp32 load and all its songs, unload, then fp16.
  fp32 runs save no artifacts (Phase 1 has them).
- **Language windows.** The log-mel is computed once over the whole stem and cut
  into 3000-frame slices, which is how whisper's `transcribe` slices its
  segments, so the stock guess is whisper's own first-window decision. The last
  window can be shorter than 30 s; it is kept, its length is in `len_s`, and it
  counts like any other (the plan does not say otherwise). A window counts for
  the aggregate when its RMS is at least the loudest window's RMS minus 20 dB.
  Each window's file entry also holds the full 100-language distribution, so the
  aggregate can be recomputed under another rule.
- **English controls** (executor's choice; all have a `vocal/` stem): Adele
  Someone Like You `hLQl3WQQoQ0` (sparse ballad), Eminem Lose Yourself
  `xFYQQPAOz7Y` (fast rap), Queen Bohemian Rhapsody `fJ9rUzIMcZQ` (harmonised
  voices, a few non-English words), Ed Sheeran Shape of You `JGwWNGJdvx8`
  (rhythmic pop).
- **Colloquial count.** Per Chinese song: total occurrences of the 14 listed
  characters, the count per character, and the sheet's Han character count.

**What was and was not tested before handing over** (dev VM, CPU only, scratch
library with 20-75 s stem clips and a fake `nvidia-smi`; nothing written to
`zh_probe/` in the real library):

- Tested: `phase1b_half.py` at fp32 with H on #1 and #2 (rows, device readings
  and `nonfinite` written correctly); its fp16 save path, `commands.txt`, an
  out-of-memory row and an error row, with a stand-in arm; both modules import;
  `phase1b_lang.py`'s stock and aggregate logic on made-up windows; whisper's
  `detect_language` through the real `large-v3-turbo.pt` on one 20 s window of
  the Adele stem (100 languages returned, `en` 0.985).
- Not tested: fp16 on a real model (fp16 on this CPU was too slow to finish; two
  attempts stopped), Hal in any form, `phase1b_lang.py`'s per-song loop and file
  writing, and anything on CUDA.

### 2026-11-03 — Phase 1b GPU runs (Sonnet 5.5), artifacts saved, awaiting Ken's calls

Ken ran both scripts on Windows (RTX A2000, 6 GB; output on D:, read here over
the RDP redirect), from the Windows clone's `chinese_karaoke` worktree at
`2e5f0fd` (code `8452230`). 1b-ii ran first with the app closed, then 1b-i.
Nothing in `pikaraoke/` or the lock files changed. All 8 run-table rows are
`ok`: no run failed or ran out of memory. Saved under `zh_probe/phase1b/`:
`half_runs.{txt,json}`, `half/<video id>/<arm>.{json,ass}` (4 pairs),
`commands.txt`, `lang/<video id>.json` (8), `lang_songs.txt`, `lang_windows.txt`.

**Flag for the read (a fact about the run, not a verdict).** The device-wide
memory used before the probe loaded its first model was **919 MB**, and 1121 or
1129 MB before the later loads (table below). The Phase 1b-i spec and the
co-residency estimate (previous entry) put the app with whisper and the stem
worker resident at about 5 GB. These figures do not look like that state: the
run table does not show whether the app was open with its workers loaded.

#### 1b-i: H and Hal, fp32 then fp16

Memory in MB; `device_total_mb` is 6138 on every row. Load figures repeat on
each song of an arm and precision. Order of runs: H fp32, H fp16, Hal fp32, Hal
fp16. "device before load" is the reading just before that model's load (the
fp16 rows follow an fp32 pass, so the probe's own CUDA context may be in it).

| song | arm | prec | status | load s | align s | torch load alloc / reserved | torch align alloc / reserved | device before load | device load peak | device after load | device align peak | readings | nonfinite |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | H | fp32 | ok | 35.6 | 5.98 | 1217 / 1220 | 2081 / 2876 | 919 | 2117 | 2117 | 3797 | 38 | 0 |
| #2 | H | fp32 | ok | 35.6 | 4.21 | 1217 / 1220 | 2081 / 3076 | 919 | 2117 | 2117 | 3997 | 28 | 0 |
| #1 | H | fp16 | ok | 3.44 | 2.62 | 617 / 624 | 1045 / 1458 | 1121 | 1545 | 1545 | 2387 | 20 | 0 |
| #2 | H | fp16 | ok | 3.44 | 1.63 | 617 / 624 | 1045 / 1458 | 1121 | 1545 | 1545 | 2387 | 14 | 0 |
| #9 | Hal | fp32 | ok | 9.85 | 10.74 | 2329 / 2340 | 3458 / 4082 | 1129 | 3269 | 3269 | 5011 | 64 | 0 |
| #11 | Hal | fp32 | ok | 9.85 | 16.42 | 2329 / 2340 | 3458 / 4082 | 1129 | 3269 | 3269 | 5011 | 93 | 0 |
| #9 | Hal | fp16 | ok | 7.74 | 5.06 | 1169 / 1188 | 1745 / 2086 | 1121 | 2109 | 2109 | 3009 | 32 | 0 |
| #11 | Hal | fp16 | ok | 7.74 | 7.16 | 1169 / 1188 | 1745 / 2092 | 1121 | 2109 | 2109 | 3078 | 46 | 0 |

Frame counts equal Phase 1's (15914, 12711, 5125, 7940). `readings` is the
number of nvidia-smi readings behind the align peak.

**The four fp16 outputs against the Phase 1 fp32 outputs** (mechanical, from the
JSONs; not a gate input):

| song | arm | units | starts non-decreasing | ends before start | interpolated fp16 / fp32 | first start -> last end (both) | units whose start differs | largest start difference s | starts differing by more than 0.1 s |
|---|---|---|---|---|---|---|---|---|---|
| #1 | H | 467 | yes | 0 | 4 / 4 | 44.00 -> 301.56 | 10 | 0.40 | 1 |
| #2 | H | 479 | yes | 0 | 4 / 4 | 28.06 -> 238.18 | 1 | 0.16 | 1 |
| #9 | Hal | 290 | yes | 0 | 3 / 3 | 16.56 -> 181.56 | 0 | 0.00 | 0 |
| #11 | Hal | 359 | yes | 0 | 6 / 6 | 18.96 -> 259.68 | 0 | 0.00 | 0 |

Ken's overall call on each fp16 `.ass` (`phase1b/commands.txt`, same three-way
scale, no per-line marks) is not in yet.

#### 1b-ii: whisper language detection on the vocal stems

Model `large-v3-turbo.pt`, cuda, 1.2 to 2.9 s per song. Window = 30 s, counted
for the aggregate when its RMS is within 20 dB of the song's loudest. The
colloquial count is the 14-character list on the confirmed sheet (0 on all four
sheets; Han characters on the sheets 450, 477, 290, 345).

| song | label | audio s | windows | counted | loudest dBFS | stock | stock p | aggregate | aggregate top 3 (summed log-prob) | colloquial chars |
|---|---|---|---|---|---|---|---|---|---|---|
| #1 周杰倫 晴天 | zh | 318.3 | 11 | 10 | -21.05 | en | 0.4971 | zh | zh -5.304; en -41.902; ja -67.917 | 0 |
| #2 周杰倫 龍捲風 | zh | 254.2 | 9 | 8 | -20.71 | zh | 0.9625 | zh | zh -0.132; en -41.429; ja -57.827 | 0 |
| #9 陳奕迅 明年今日 | yue | 205.0 | 7 | 7 | -16.53 | zh | 0.8109 | zh | zh -1.558; en -14.948; ja -36.679 | 0 |
| #11 Beyond 海闊天空 | yue | 317.6 | 11 | 9 | -16.14 | zh | 0.9186 | zh | zh -3.944; en -16.194; ja -46.545 | 0 |
| Adele - Someone Like You | en | 285.0 | 10 | 9 | -12.29 | en | 0.9724 | en | en -0.244; es -49.627; fr -50.205 |  |
| Eminem - Lose Yourself | en | 327.6 | 11 | 9 | -21.53 | en | 0.5934 | en | en -0.083; es -59.458; fr -62.927 |  |
| Queen - Bohemian Rhapsody | en | 359.5 | 12 | 11 | -16.93 | en | 0.9858 | en | en -0.215; es -66.438; fr -67.836 |  |
| Ed Sheeran - Shape of You | en | 263.3 | 9 | 8 | -10.94 | en | 0.99 | en | en -0.115; es -49.646; fr -51.244 |  |

Every window (`top` entries are language and probability; `p(yue)` rounds to
0.0 at four places in the table, see below):

```
song     win  len s     dBFS  counted top 1      top 2      top 3         p(zh)  p(yue)
#1         0   30.0   -64.48  False   en 0.4971  de 0.0742  fr 0.0662    0.0069     0.0
#1         1   30.0   -26.98  True    zh 0.9521  en 0.0358  ja 0.0037    0.9521     0.0
#1         2   30.0   -23.88  True    zh 0.9752  en 0.0192  ja 0.0017    0.9752     0.0
#1         3   30.0   -22.82  True    zh 0.9779  en 0.0181  ja 0.0012    0.9779     0.0
#1         4   30.0   -21.19  True    zh 0.9935  en 0.0047  ja 0.0006    0.9935     0.0
#1         5   30.0   -25.21  True    zh 0.9743  en 0.0214  ja 0.0013    0.9743     0.0
#1         6   30.0   -21.94  True    zh 0.9943  en 0.0042  ja 0.0005    0.9943     0.0
#1         7   30.0   -39.47  True    en 0.8751  fr 0.0361  es 0.0162    0.0058     0.0
#1         8   30.0   -21.05  True    zh 0.9947  en 0.0036  ja 0.0006    0.9947     0.0
#1         9   30.0   -23.92  True    zh 0.9942  en 0.004   ja 0.0006    0.9942     0.0
#1        10   18.3   -34.22  True    zh 0.9872  en 0.0097  ja 0.0006    0.9872     0.0
#2         0   30.0   -35.55  True    zh 0.9625  en 0.0298  ja 0.0019    0.9625     0.0
#2         1   30.0    -25.3  True    zh 0.9963  en 0.0021  ja 0.0006    0.9963     0.0
#2         2   30.0   -23.39  True    zh 0.996   en 0.0026  ja 0.0005     0.996     0.0
#2         3   30.0    -23.4  True    zh 0.9974  en 0.0016  ja 0.0003    0.9974     0.0
#2         4   30.0   -21.95  True    zh 0.9936  en 0.0045  ja 0.0006    0.9936     0.0
#2         5   30.0   -27.31  True    zh 0.9954  en 0.0033  ja 0.0004    0.9954     0.0
#2         6   30.0   -20.71  True    zh 0.9926  en 0.0051  ja 0.0007    0.9926     0.0
#2         7   30.0   -23.33  True    zh 0.9371  en 0.0516  ja 0.0026    0.9371     0.0
#2         8  14.24  -134.65  False   en 0.3542  ru 0.1253  pt 0.0754    0.0115     0.0
#9         0   30.0   -36.34  True    zh 0.8109  en 0.1488  ja 0.009     0.8109     0.0
#9         1   30.0   -26.79  True    zh 0.9418  en 0.0447  ja 0.0038    0.9418     0.0
#9         2   30.0   -17.43  True    zh 0.6366  en 0.3329  ja 0.0061    0.6366     0.0
#9         3   30.0   -22.46  True    zh 0.7801  en 0.1942  ja 0.0067    0.7801     0.0
#9         4   30.0   -16.53  True    zh 0.6496  en 0.3117  ja 0.0073    0.6496     0.0
#9         5   30.0   -18.27  True    zh 0.8846  en 0.0992  ja 0.004     0.8846     0.0
#9         6  25.01   -36.18  True    zh 0.9667  en 0.0242  ja 0.0029    0.9667     0.0
#11        0   30.0   -28.62  True    zh 0.9186  en 0.066   ja 0.004     0.9186     0.0
#11        1   30.0    -24.8  True    zh 0.7735  en 0.1986  ja 0.0058    0.7735     0.0
#11        2   30.0   -21.11  True    zh 0.7713  en 0.1981  ja 0.0061    0.7713     0.0
#11        3   30.0   -22.08  True    zh 0.8397  en 0.1339  ja 0.0055    0.8397     0.0
#11        4   30.0   -18.23  True    zh 0.7479  en 0.2246  ja 0.0058    0.7479     0.0
#11        5   30.0   -24.48  True    en 0.5859  zh 0.1381  nl 0.0526    0.1381     0.0
#11        6   30.0   -19.38  True    zh 0.9355  en 0.0545  ja 0.0034    0.9355     0.0
#11        7   30.0   -16.14  True    zh 0.905   en 0.0749  ja 0.0048     0.905     0.0
#11        8   30.0   -18.73  True    en 0.4968  zh 0.4815  ja 0.0049    0.4815     0.0
#11        9   30.0   -48.29  False   en 0.5963  ru 0.0648  fr 0.0616    0.0087     0.0
#11       10   17.6   -87.69  False   en 0.3671  pt 0.0996  ru 0.0816    0.0081     0.0
Adele      0   30.0   -17.59  True    en 0.9724  es 0.0044  de 0.0043     0.002     0.0
Adele      1   30.0   -14.11  True    en 0.9802  de 0.0035  fr 0.003     0.0015     0.0
Adele      2   30.0   -13.05  True    en 0.969   es 0.0058  fr 0.0047    0.0023     0.0
Adele      3   30.0    -14.6  True    en 0.9592  es 0.0075  fr 0.007     0.0032     0.0
Adele      4   30.0   -13.11  True    en 0.9828  es 0.0029  fr 0.0027    0.0012     0.0
Adele      5   30.0   -12.93  True    en 0.953   es 0.0082  fr 0.0076     0.004     0.0
Adele      6   30.0   -12.29  True    en 0.9904  fr 0.0014  es 0.0014     0.001     0.0
Adele      7   30.0   -13.18  True    en 0.9836  fr 0.003   es 0.0026    0.0013     0.0
Adele      8   30.0   -12.53  True    en 0.9693  es 0.0058  fr 0.0049    0.0023     0.0
Adele      9  14.98  -124.85  False   en 0.3144  ru 0.1152  pt 0.1009    0.0086     0.0
Eminem     0   30.0   -61.44  False   en 0.5934  es 0.0917  pt 0.0655    0.0026     0.0
Eminem     1   30.0    -27.1  True    en 0.9979  es 0.0004  de 0.0002    0.0001     0.0
Eminem     2   30.0   -21.99  True    en 0.996   es 0.0009  fr 0.0005    0.0002     0.0
Eminem     3   30.0   -21.57  True    en 0.9766  es 0.0049  fr 0.0036    0.0014     0.0
Eminem     4   30.0   -22.76  True    en 0.9909  es 0.0019  fr 0.0013    0.0006     0.0
Eminem     5   30.0   -22.04  True    en 0.9827  es 0.0033  fr 0.0029    0.0012     0.0
Eminem     6   30.0   -21.67  True    en 0.9868  es 0.0026  fr 0.0019    0.0008     0.0
Eminem     7   30.0   -21.88  True    en 0.9964  es 0.0007  fr 0.0005    0.0002     0.0
Eminem     8   30.0   -21.53  True    en 0.9922  es 0.0016  fr 0.0011    0.0005     0.0
Eminem     9   30.0    -26.3  True    en 0.9975  es 0.0005  fr 0.0003    0.0002     0.0
Eminem    10  27.56   -75.55  False   en 0.3249  ja 0.1873  pt 0.0748    0.0197     0.0
Queen      0   30.0   -22.48  True    en 0.9858  fr 0.002   es 0.0018    0.0009     0.0
Queen      1   30.0   -23.38  True    en 0.9956  es 0.0008  de 0.0006    0.0002     0.0
Queen      2   30.0   -23.64  True    en 0.9844  de 0.0021  fr 0.0021    0.0012     0.0
Queen      3   30.0   -25.14  True    en 0.9709  de 0.0046  fr 0.0043     0.002     0.0
Queen      4   30.0    -20.0  True    en 0.9819  es 0.0026  de 0.0022    0.0016     0.0
Queen      5   30.0   -20.56  True    en 0.985   de 0.0024  es 0.0023    0.0008     0.0
Queen      6   30.0   -19.51  True    en 0.9893  es 0.0018  fr 0.0015    0.0005     0.0
Queen      7   30.0   -16.93  True    en 0.9817  es 0.003   fr 0.0025    0.0008     0.0
Queen      8   30.0   -17.53  True    en 0.9852  es 0.0022  fr 0.002     0.0008     0.0
Queen      9   30.0   -23.07  True    en 0.9379  es 0.0132  de 0.008     0.0029     0.0
Queen     10   30.0   -28.32  True    en 0.9909  de 0.0015  es 0.0014    0.0005     0.0
Queen     11  29.49   -43.45  False   en 0.9352  es 0.012   fr 0.0104    0.0068     0.0
Sheeran    0   30.0   -16.14  True    en 0.99    es 0.0017  fr 0.0014    0.0007     0.0
Sheeran    1   30.0   -11.79  True    en 0.9882  es 0.0018  fr 0.0018    0.0009     0.0
Sheeran    2   30.0   -10.94  True    en 0.9779  es 0.0039  fr 0.0031    0.0018     0.0
Sheeran    3   30.0   -12.32  True    en 0.9961  es 0.0007  fr 0.0005    0.0003     0.0
Sheeran    4   30.0   -11.01  True    en 0.9892  es 0.0019  fr 0.0015    0.0009     0.0
Sheeran    5   30.0   -11.45  True    en 0.9912  es 0.0014  fr 0.0011    0.0008     0.0
Sheeran    6   30.0   -13.87  True    en 0.9681  es 0.005   fr 0.0048    0.0032     0.0
Sheeran    7   30.0   -12.28  True    en 0.9857  es 0.0024  fr 0.0018    0.0014     0.0
Sheeran    8  23.27   -48.09  False   en 0.4796  ru 0.0908  pt 0.085     0.0067     0.0
```

In the saved distributions, p(yue) is at most 7.3e-10 in any of the 80 windows,
and in the 18 windows of the two Cantonese songs `yue` ranks 100th of 100
languages in 17 and 99th in one. The windows not counted (RMS more than 20 dB under the song's loudest) are: #1 window 0
(-64.48 dBFS), #2 window 8 (-134.65), #11 windows 9 and 10 (-48.29, -87.69),
Adele window 9 (-124.85), Eminem windows 0 and 10 (-61.44, -75.55), Queen window
11 (-43.45) and Sheeran window 8 (-48.09).

No verdicts here. Opus reads GATE Z1b from the 1b-i rows and Ken's four calls;
GATE ZL is read after Phase 2.

### 2026-11-03 — Phase 1b-i rerun with the app open (Sonnet 5.5), artifacts saved, awaiting Ken's calls

Ken ran `phase1b_half.py` again, from the same Windows worktree (code
`8452230`, nothing changed). **Ken says the previous entry's 1b-i run was made
with the app closed.** This time the app was launched from the main Windows
checkout (`uv run pikaraoke -d d:/shared/pikaraoke-songs`, workers started at
launch) before the probe; the run table does not show whether a song was
playing in mpv or whether the workers had finished loading, only the device-wide
readings below. 1b-ii was not rerun (it is specified with the app closed, and
that run stands). All 8 rows are `ok`: no out-of-memory, no non-finite
emissions. `half_runs.{txt,json}` now hold this run's rows (the previous run's
rows are in the previous entry only), and `half/<video id>/<arm>.{json,ass}` and
`commands.txt` were rewritten.

Memory in MB; `device_total_mb` is 6138. Load figures repeat on each song of an
arm and precision. "highest" is the larger of the row's load peak and align
peak; "free" is 6138 minus that (plain subtraction, not a gate read).

| song | arm | prec | status | load s | align s | torch load alloc / reserved | torch align alloc / reserved | device before load | device load peak | device after load | device align peak | highest | free | readings | nonfinite |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #1 | H | fp32 | ok | 65.18 | 23.48 | 1217 / 1220 | 2081 / 2876 | 5365 | 5880 | 5719 | 5787 | 5880 | 258 | 142 | 0 |
| #2 | H | fp32 | ok | 65.18 | 7.38 | 1217 / 1220 | 2081 / 3076 | 5365 | 5880 | 5719 | 5715 | 5880 | 258 | 48 | 0 |
| #1 | H | fp16 | ok | 3.89 | 2.96 | 617 / 624 | 1045 / 1458 | 3107 | 3531 | 3514 | 4373 | 4373 | 1765 | 22 | 0 |
| #2 | H | fp16 | ok | 3.89 | 1.80 | 617 / 624 | 1045 / 1458 | 3107 | 3531 | 3514 | 4373 | 4373 | 1765 | 14 | 0 |
| #9 | Hal | fp32 | ok | 8.74 | 61.89 | 2329 / 2340 | 3458 / 4082 | 3115 | 5272 | 5272 | 5600 | 5600 | 538 | 391 | 0 |
| #11 | Hal | fp32 | ok | 8.74 | 97.74 | 2329 / 2340 | 3458 / 4082 | 3115 | 5272 | 5272 | 5684 | 5684 | 454 | 603 | 0 |
| #9 | Hal | fp16 | ok | 8.08 | 5.17 | 1169 / 1188 | 1745 / 2086 | 3076 | 4052 | 4052 | 4952 | 4952 | 1186 | 32 | 0 |
| #11 | Hal | fp16 | ok | 8.08 | 7.73 | 1169 / 1188 | 1745 / 2092 | 3076 | 4052 | 4052 | 5078 | 5078 | 1060 | 47 | 0 |

Frame counts equal Phase 1's (15914, 12711, 5125, 7940). Torch's own figures
(alloc and reserved) equal the previous run's to the MB on every row.

**Facts about the run for the read (no verdicts).**

- **The device-wide reading before the probe loaded its first model was 5365 MB**,
  against 919 MB in the previous (app-closed) run.
- **The reading before each later load was 2250 to 2290 MB lower than before the
  first one**: 3107 before H fp16, 3115 before Hal fp32, 3076 before Hal fp16. The
  probe had released a model before each of those loads (`arm.unload()`,
  `free_memory()`). The table does not say what else left the card between the
  first and second reading. One candidate, not tested here: Windows moves GPU
  memory of an idle process out to system RAM when the card is nearly full,
  and the first row's highest reading (5880 of 6138) was the nearest the run came
  to full.
- **The H fp16 and Hal fp16 rows therefore ran against a baseline 2250 to 2290 MB
  lower than the H fp32 rows did.** The Hal fp32 rows ran against the lower one
  too.
- On the Hal fp32 rows, baseline plus torch's reserved pool (3115 + 4082) is
  more than the card's 6138, while the device-wide highest reading was 5600 and
  5684\. The table does not show how that fits.
- Wall times against the app-closed run (previous entry), load / align:
  H fp32 35.6 -> 65.18 s load, 5.98 -> 23.48 s and 4.21 -> 7.38 s align;
  Hal fp32 9.85 -> 8.74 s load, 10.74 -> 61.89 s and 16.42 -> 97.74 s align;
  H fp16 3.44 -> 3.89 s load, 2.62 -> 2.96 s and 1.63 -> 1.80 s align;
  Hal fp16 7.74 -> 8.08 s load, 5.06 -> 5.17 s and 7.16 -> 7.73 s align.

**The four fp16 outputs against the Phase 1 fp32 outputs** (mechanical, from the
JSONs; not a gate input). The figures are the same as in the previous entry's
table for every column it had. The previous run's fp16 files were overwritten,
so the two runs' files cannot be compared one to one.

| song | arm | units | starts non-decreasing | ends before start | units whose start differs | largest start difference s | starts differing by more than 0.1 s | units whose end differs | largest end difference s |
|---|---|---|---|---|---|---|---|---|---|
| #1 | H | 467 | yes | 0 | 10 | 0.40 | 1 | 9 | 0.44 |
| #2 | H | 479 | yes | 0 | 1 | 0.16 | 1 | 1 | 0.16 |
| #9 | Hal | 290 | yes | 0 | 0 | 0.00 | 0 | 0 | 0.00 |
| #11 | Hal | 359 | yes | 0 | 0 | 0.00 | 0 | 0 | 0.00 |

Ken's overall call on each fp16 `.ass` (`phase1b/commands.txt`, same three-way
scale, no per-line marks) is not in yet.

No verdicts here. Opus reads GATE Z1b from the 1b-i rows of this entry and the
previous one, and Ken's four calls; GATE ZL is read after Phase 2.

### 2026-11-03 — GATE Z1b read (Opus 5.5)

Read from the 1b-i rows of the two entries above (app closed, then app open),
the Phase 1 calls, and a read-only check of the artifacts and code. Nothing was
re-run. Ken's four fp16 calls came in after the read (end of this entry); they
do not change the outcome.

**Checks made.** `phase1b/half_runs.json` matches the rerun's table on every
row. The fp16-vs-fp32 timing table was recomputed from `phase1/<id>/<arm>.json`
and `phase1b/half/<id>/<arm>.json` and agrees (H: 10 and 1 characters moved,
largest 0.40 s; Hal: none). Code: between blocks the probe calls `arm.unload()`
then `free_memory()` (`gc.collect()`, `torch.cuda.empty_cache()`), so it keeps
only its CUDA context; the app's whisper and stem workers release their models
only when their subprocess exits (`whisper_worker.py` and `stem_worker.py`,
the `finally` blocks that log "model unloaded"). No idle unload exists.

**What the 2.2 GB drop is.** It is the app's memory leaving the card while the
probe held nothing but its context. Two causes fit, and the artifacts cannot
tell them apart: Windows moved the idle workers' memory to system RAM (it comes
back when they next use the card), or a worker process exited. The app log for
the run (a "model unloaded" line or a worker restart) or Task Manager's shared
GPU memory column would tell them apart. Either way, every row after the first
block ran beside less of the app than Phase 1b-i specified, so the fp16 rows'
device peaks are not readings of the state the gate is about.

**The device-wide peak cannot show a non-fit on this card.** The H fp32 rows
needed far more than the card holds beside a 5365 MB baseline, yet nothing
failed: the reading stopped at 5880 MB (258 MB free, which passes the 256 MB
test as written) and align ran 1.75-3.9x slower. Hal fp32 behaved the same way
against the lower baseline (5600-5684 MB read, about 6x slower). So on this
driver an allocation past the card does not fail; it lands in system memory or
pushes another process out, and the cost shows as time, not as a reading over
the limit. (The NVIDIA Windows driver's sysmem fallback setting would do this;
not checked.)

**Fit computed from the measured footprints.** The probe's device-wide rise at
fp16 is the same in both runs to within 45 MB, so it can be placed on the
5365 MB state without a run. Rise = align peak minus the reading before the
probe touched the card (app-closed run, so the probe's own CUDA context is
included, as it would be in a fresh fp16-only run):

| arm (fp16) | rise MB, app closed (919 base) | rise over before-load, app closed / app open | projected peak on 5365 | gate limit (6138 - 256) | over by | largest baseline that fits |
|---|---|---|---|---|---|---|
| H | 2387 - 919 = 1468 | 1266 / 1266 | 6833 | 5882 | 951 | 4414 |
| Hal (#9) | 3009 - 919 = 2090 | 1888 / 1876 | 7455 | 5882 | 1573 | 3792 |
| Hal (#11) | 3078 - 919 = 2159 | 1957 / 2002 | 7524 | 5882 | 1642 | 3723 |

The H fp16 load alone (1545 - 919 = 626) would put the card at 5991, over the
limit before any align. The app's share of the 5365 is about 4.45 GB over the
919 desktop; for H to fit it would have to be under about 3.5 GB, for Hal under
about 2.8 GB.

**Read.** Condition (a) is not met for either language. The literal peaks in
the rerun pass it, but they were taken after about 2.25 GB of the app had left
the card, and the same reading passes the H fp32 rows, which plainly did not
fit. The measured fp16 footprints do not fit beside the app as measured, by
about 1 GB for H and 1.6 GB for Hal, and would not fit beside any plausible
app state. **By the pre-registered rule, both languages run at full precision
in Phase 2, and Phase 3 records the fallback** (unload whisper while the song
aligns, then reload it).

**An fp16-only run from the 5.4 GB baseline is not needed.** It cannot pass
(a): the footprint it would measure is already measured twice and does not
fit, and on this card a non-fit reads as a near-full peak, not a failure, so
its peak could not be read against (a) either. At most it would show the
slowdown again.

**For Phase 3 (facts the fallback's pricing does not yet cover).**

- Whether the fallback fits is unmeasured. Unloading whisper leaves the stem
  worker's separator and context and mpv on the card. Hal fp32's rise
  (5011 - 919 = 4092 MB) is close to the whole app's 4.45 GB share, so Hal
  fp32 fits beside the stem worker only if whisper's process alone held about
  3.6 GB; H fp32 (rise about 2.9-3.1 GB) needs whisper to free about 2.4-2.6 GB.
  At fp16 the needs are about 1.0 GB (H) and 1.6 GB (Hal). Whisper's share was
  not measured, so which precision the fallback can run at is open, and that is
  where Ken's four fp16 calls bear.
- A third option the rerun showed without testing it: leave whisper loaded and
  let Windows move it off the card. In the rerun that cost the first block
  (H fp32 load 65 s against 36 s, first align about 4x), after which fp16 ran at
  app-closed speed. Whisper's page-in cost on its next job was not measured, nor
  whether the app stayed healthy.
- On this card an out-of-memory turns into a slowdown rather than an error, so
  a build cannot rely on catching OOM to detect a non-fit.

**Condition (b): Ken's four fp16 calls** (given in chat after the read). He
listened only where the fp16 `.ass` differs from the Phase 1 one: `cmp` shows
both Hal files byte-identical, and the H files differ on 3 dialogue lines (#1,
starting 0:57.84, 3:14.38, 4:35.58) and 1 line (#2, starting 1:35.06).

| song | arm | Phase 1 call | fp16 call | no worse? |
|---|---|---|---|---|
| #1 晴天 | H | as is | as is | yes |
| #2 龍捲風 | H | as is | as is | yes |
| #9 明年今日 | Hal | as is | as is (carried over, identical file) | yes |
| #11 海闊天空 | Hal | as is | as is (carried over, identical file) | yes |

Ken's note on #1, verbatim except the bracketed word (typed "line"): "most of the spot checks are fine, just 4:35 in
晴天 is an overlapping section so the second line starts \[late\] and rushes, not
sure if that was already there from before". It was: the 4:35.58 line
(颳風這天 我試過握著你手, 11 characters) spans 2.14 s in both files, and
in both files four of 我試過握著 get 2 cs and the fifth 8 cs; fp16 moved four
of the line's durations by 2-6 cs. The same line at 3:14.38 spans 8.72 s. Ken kept *as is* for #1 with
that known. **For Phase 2 and Phase 3:** H squeezes the second of two
overlapping lines; it is not an fp16 effect, and the corpus listen should
watch for it.

Condition (b) holds on all four songs. Z1b still sends both languages to full
precision in Phase 2, because (a) is not met.

### 2026-11-03 — Phase 0b fetch for the twelve non-pilot songs (Sonnet 5.5), awaiting Ken's sheets

Songs #3-8, #10 and #12-16, fetched on the Ubuntu VM with code `9d15d32`
(`corpus.py` gains the twelve songs, `fetch_sheets.py` runs on the VM and skips
any song whose folder already holds an `index.json`). The four pilot folders were
not touched (newest file in each is still 2026-10-20). `pikaraoke/` is
untouched; the probe imports only the Genius and LRCLIB clients and the
`syncedlyrics` NetEase provider. Outputs are under
`/home/ken/shared-drives/D:/Shared/pikaraoke-songs/zh_probe/phase0/sheets_raw/<video id>/`
(`sources.txt`, `index.json`, raw files, as for the pilot). Ken's confirmed
sheets go to `zh_probe/sheets/<video id>.txt`; nothing there for these twelve.
No worksheet and no transcript aid were made. Phase 0a is not recorded: Ken has
not reported it done.

**How it ran.** `ZH_PROBE_LIBRARY` set to the RDP-redirected library, conda `pik`
Python with `-P`, Genius token from `~/.pikaraoke/config.ini`. `syncedlyrics` is
not in `pik`; it was installed with `pip install --target` into a scratch
directory put on `PYTHONPATH`, so the env is unchanged (that directory also holds
`requests` 2.34.2, which shadows the env's 2.32.5 for these runs only). Keys,
Genius queries and the two hand-set NetEase ids are in `corpus.py`.

**NetEase ids set by hand.** #3 `186137` (双截棍, album 范特西 `18915`) and #4
`185880` (千里之外, album 依然范特西 `18893`), from Jay Chou's artist listing
(`/api/artist/albums/6452`, then `/api/album/<id>`), as for #1 and #2. The album
listing also shows a second 双截棍 track, `3454649690`, on the single 双截棍影音单曲
(`406469560`); it was not fetched.

**LRCLIB retries.** `lrclib.search` returns `[]` on a 503, and a test of its
search URL from the VM alternated 200, 503, 200, 503 at 5 s spacing. The pilot
fetch retried an empty answer 3 times; this fetch retries 5 times
(`LRCLIB_ATTEMPTS`), sleeping 2, 4, 6, 8 and 10 s after the failed attempts. A first smoke run of #3 with 3
attempts had 2 of its 3 keys fail all 3 attempts; that folder was deleted and #3
fetched again in the full run. After the full run, #14's Traditional key and
#7's English key had used all 5 attempts without an answer, so those two folders
were deleted and fetched again (`--songs 7,14`); no key used all 5 in that
second fetch. The tables are from the files now on disk. An empty answer with no
503 is retried too and leaves no warning, so a key with no warning is not shown
to have answered. Warnings per search key (a key listed with N warnings failed N
attempts before its last):

| # | search key (track / artist) | 503 warnings |
|---|---|---|
| 4 | 千里之外 / 周杰倫 | 2 |
| 4 | 千里之外 / 周杰伦 | 1 |
| 4 | Thousand Miles / Jay Chou | 4 |
| 5 | The Moon Represents My Heart / Teresa Teng | 2 |
| 6 | 遇見 / 孫燕姿 | 2 |
| 6 | Yu Jian / Stefanie Sun | 1 |
| 7 (first fetch) | Ten Years / Eason Chan | 5 (no answer) |
| 7 (second fetch) | Ten Years / Eason Chan | 1 |
| 10 | Under Mount Fuji / Eason Chan | 2 |
| 12 | Wind Blows On / Leslie Cheung | 3 |
| 13 | 少女的祈禱 / 楊千嬅 | 2 |
| 13 | 少女的祈祷 / 杨千嬅 | 1 |
| 14 (first fetch) | 容易受傷的女人 / 王菲 | 5 (no answer) |
| 14 (second fetch) | 容易受傷的女人 / 王菲 | 2 |
| 15 | 男兒當自強 / 林子祥 | 1 |
| 15 | 男儿当自强 / 林子祥 | 1 |
| 16 | 下一站天后 / TWINS | 1 |
| 16 | Next Stop / Twins | 2 |

Songs #3, #8 had no warnings. Every song's `lrclib_dropped` count is 0.

**Per song.** Counts of the saved files, in the pilot's columns (LRCLIB also shows
how many of the `.txt` files have a synced `.lrc` beside them):

| # | Genius files | LRCLIB `.txt` (synced `.lrc`) | NetEase `.lrc` | NetEase word-timed | distinct texts in `sources.txt` |
|---|---|---|---|---|---|
| 3 | 2 | 40 (15) | 1 (`186137` by hand) | `yrc` **yes** (`netease_186137.yrc`), `klyric` no | 7 |
| 4 | 1 | 40 (38) | 3 (`37460604`, `1403637218`, `185880` by hand) | `yrc` **yes** (`netease_37460604.yrc`, `netease_185880.yrc`), `klyric` no | 8 |
| 5 | 2 | 40 (40) | 1 (`1847408145`) | `yrc` **yes** (`netease_1847408145.yrc`), `klyric` no | 5 |
| 6 | 1 | 20 (20) | 1 (`454828887`) | `yrc` **yes** (`netease_454828887.yrc`), `klyric` no | 4 |
| 7 | 2 | 41 (41) | 1 (`66842`) | `yrc` **yes** (`netease_66842.yrc`), `klyric` no | 5 |
| 8 | 1 | 40 (38) | 1 (`65536`) | `yrc` no, `klyric` no | 6 |
| 10 | 1 | 40 (40) | 1 (`65766`) | `yrc` **yes** (`netease_65766.yrc`), `klyric` no | 5 |
| 12 | 1 | 41 (37) | 1 (`2650715912`) | `yrc` no, `klyric` no | 6 |
| 13 | 1 | 39 (39) | 2 (`3312508535`, `29207675`) | `yrc` **yes** (`netease_29207675.yrc`), `klyric` no | 8 |
| 14 | 1 | 20 (20) | 1 (`298880`) | `yrc` **yes** (`netease_298880.yrc`), `klyric` no | 5 |
| 15 | 1 | 48 (42) | 2 (`406001540`, `116113`) | `yrc` **yes** (`netease_406001540.yrc`, `netease_116113.yrc`), `klyric` no | 8 |
| 16 | 1 | 31 (31) | 1 (`382844`) | `yrc` **yes** (`netease_382844.yrc`), `klyric` no | 4 |

**NetEase hits.** Every NetEase hit the fetch tried, search hits and hand ids
(`klyric` is `no` for all):

| # | NetEase id | title / artist | `.lrc` | `yrc` | `klyric` | by hand |
|---|---|---|---|---|---|---|
| 3 | `1372718837` | Nunchucks / Goto | no | no | no |  |
| 3 | `186137` | (looked up by hand, no search record) | yes | yes | no | yes |
| 4 | `37460604` | 千里之外 / 费玉清 | yes | yes | no |  |
| 4 | `2008026147` | 千里之外 (钢琴版) \[原唱: 周杰伦 feat. 费玉清\] / 贵族钢琴轻音乐 | no | no | no |  |
| 4 | `1403637218` | Thousand Miles / DYGL | yes | no | no |  |
| 4 | `185880` | (looked up by hand, no search record) | yes | yes | no | yes |
| 5 | `2032373645` | 月亮代表我的心 / 鄧麗君 | no | no | no |  |
| 5 | `1847408145` | 月亮代表我的心 / 邓丽君 | yes | yes | no |  |
| 5 | `5224559` | The Moon Represents My Heart / Jeremy | no | no | no |  |
| 6 | `454828887` | 遇见 / 孙燕姿 | yes | yes | no |  |
| 6 | `3365987741` | 遇见 (2026 Rock Stefanie Sun Cover) / 重塑伝説 | no | no | no |  |
| 7 | `66842` | 十年 / 陈奕迅 | yes | yes | no |  |
| 7 | `3356382410` | 回应的 / Eason Chan | no | no | no |  |
| 8 | `65536` | 爱情转移 / 陈奕迅 | yes | no | no |  |
| 10 | `65766` | 富士山下 / 陈奕迅 | yes | yes | no |  |
| 10 | `3455813963` | Under Mount Fuji / 乖乖娃 | no | no | no |  |
| 12 | `2650715912` | 风继续吹 (Live) / 张国荣 | yes | no | no |  |
| 12 | `22445693` | Way That the Wind Blows / Leslie 'Hutch' Hutchinson | no | no | no |  |
| 13 | `3312508535` | 少女的祈祷 / 杨千嬅 | yes | no | no |  |
| 13 | `29207675` | prayer / Φ串Φ | yes | yes | no |  |
| 14 | `298880` | 容易受伤的女人 / 王菲 | yes | yes | no |  |
| 14 | `1498238619` | Vulnerable woman / Lynn Lyly | no | no | no |  |
| 15 | `406001540` | 男儿当自強 / 林子祥 | yes | yes | no |  |
| 15 | `116113` | 男儿当自强 / 林子祥 | yes | yes | no |  |
| 16 | `382844` | 下一站天后 / Twins | yes | yes | no |  |
| 16 | `1916186400` | Next Stop / Portico Quartet | no | no | no |  |

Artifacts:

- `zh_probe/phase0/fetch_sheets_nonpilot.log` (the full run, #7 and #14 as first fetched)
- `zh_probe/phase0/fetch_sheets_nonpilot_rerun_7_14.log` (the second fetch of #7 and #14)
- `zh_probe/phase0/sheets_raw/<video id>/` for the twelve ids in the Corpus table

Open for Ken: pick or hand-edit one sheet per song into
`zh_probe/sheets/<video id>.txt` (same rules as the pilot), and Phase 0a for the
twelve songs. The worksheet and any transcript aid need his GPU run after 0a.

### 2026-11-03 — Phase 0b worksheet builder for the twelve (Sonnet 5.5), waiting for 0a and transcripts

Ken asked for a worksheet for his friend "like last time" (the pilot's claude.ai
artifact `EqY8foQNriiDuW8pCnavYE`: a tab per song, candidate texts as versions A, B, ...,
a list of spots where they disagree with a play-from link, an editor, a Send back tab).
His answers to my questions:

- **Spot times and shortlist:** wait for Phase 0a, then his GPU transcribe, as for the
  pilot. Not built from synced lyrics.
- **Split:** two pages, Mandarin (#3-8) and Cantonese (#10, #12-16).
- **Changes:** tell the friend not to write music-break markers; warn when a ticked wording is
  not in the sheet text. His note: the pilot friend asked whether her ticks had to match her
  sheet edits, and what she was supposed to give back since the page does not save for her.
  He asked for both to be made more coherent.

No page was built or published for the twelve: only #3 has a vocal stem in the library
(2026-11-03 fetch time), so there are no transcripts. New in `scripts/zh_probe/`, code
`53f57a6`:

- `phase0b_worksheet.py` (CPU, needs `opencc-python-reimplemented`): per song, reads the
  transcript, ranks the candidates as `phase0b_score.py` does, keeps those within 0.05 f1 of the
  best (at most 6) as versions in file-name order (genius, lrclib, netease), and merges texts
  that are identical once cleaned. Cleaning drops credit lines, `[...]` tag and section lines,
  NetEase `label : name` credit lines, leading title/artist lines, and strips `Sa：`-style
  singer labels; the count per kind is in `<tag>_build.txt`. Spots are the spans where any
  version differs from the best one, on Han characters (folded to Simplified) and Latin
  letters, merged when within 3 characters of each other; a spot where no version has a Han
  character and the difference touches a Latin letter (`Sol` / `So`) is left out. Each spot's
  time is the transcript segment of the matched character at or before it (the first segment
  when none matches), the link starting 3 s earlier. Output: `<tag>.html`, `<tag>_labels.json`,
  `<tag>_build.txt`.
- `worksheet_template.html`: the pilot page with the three changes above plus a save note.
  Instructions now say a tick only records what was heard and does not edit the text; a line
  under each spot says whether the sheet text has the wording ticked ("has" / "does not have
  this wording yet"), the tab shows "n to fix", a note under Done shows the count, and the
  export marks such spots. The match ignores script, punctuation and line breaks and
  looks for the n-th occurrence of the wording, n being its place among repeats of the same
  words in the version it was taken from. The first version of the check looked anywhere in
  the text; on the pilot's #1 a wrong tick at the second chorus passed because the first
  chorus has the same words, so it was replaced. The Send back tab lists three steps (check
  Done, press Copy all or Download, paste into a message to whoever sent the link), says
  nothing is sent from the page, and the page says where its work is kept and when it last
  saved, with a warning when the browser cannot store it.
- `phase0b_transcribe.py`: now covers the twelve songs (`--songs`), skips a song whose transcript
  exists, and reads the whisper path from `corpus.py`.

**Test on the pilot** (the four pilot transcripts exist; the pilot's `CONFIRMED` sheets were
excluded). The rebuilt pages against the published pilot page's data:

| # | versions published / rebuilt | spots published / rebuilt | spot start times |
|---|---|---|---|
| 1 | 5 / 5 | 5 / 5 | same five |
| 2 | 6 / 6 | 10 / 8 | the rebuilt page merges the two spots at 3:17 and the two at 3:31, which lie within 3 characters of each other; the rest are the same |
| 9 | 4 / 4 | 2 / 2 | same two |
| 11 | 4 / 4 | 12 / 12 | same, except the first spot: 0:01 published, 0:00 rebuilt (no Han character is matched before it, the transcript's first segments hold none) |

The page was driven in headless Chromium on the pilot data (the skill's `launch` helper):
a tick that matches the text shows "has"; a tick that does not shows the warning, "1 to fix" on
the tab and the count under Done; editing the text clears it; the Send back tab shows the
steps, the save note and a Copy all button; a reload keeps the tab, the text and the ticks; no
console errors; no horizontal scroll at 400 px wide. Not tested: a real friend using it, the
page on the twelve songs' data, publishing, and the Download button (it needs the artifact
runtime).

**Next, in order:**

1. Ken finishes Phase 0a (`add_songs` for the twelve; each needs its `vocal/` stem).
2. Ken runs on Windows, from the repo root with the VM's remote fetched
   (`PYTHONUTF8=1`, `uv run python scripts/zh_probe/phase0b_transcribe.py`): about
   10-40 s per song on the A2000, output `zh_probe/phase0/transcripts/<id>.{json,txt}`.
3. Executor builds the two pages with `phase0b_worksheet.py --tag mandarin --songs 3,4,5,6,7,8`
   and `--tag cantonese --songs 10,12,13,14,15,16`, publishes each as an artifact, and
   records the build tables here.

### 2026-11-03 — Phase 0a for the twelve, read off the library (Sonnet 5.5)

Ken reported "the 12 songs have been added". Read from the library on disk
(`/home/ken/shared-drives/D:/Shared/pikaraoke-songs`), same columns as the pilot's 0a table.
Language labels are the `lang` field in `scripts/zh_probe/corpus.py`; video seconds are
`ffprobe` `format=duration` of the `.mp4`.

| # | video id | lang label | video s | `vocal/` stem | stem bytes | stem written |
|---|---|---|---|---|---|---|
| 3 | `OR-0wptI_u0` | zh | 204.6 | yes | 5403320 | 13:08 |
| 4 | `ocDo3ySyHSI` | zh | 271.4 | yes | 7591440 | 13:12 |
| 5 | `IgvDMB5fR-8` | zh | 208.4 | yes | 6804831 | 13:17 |
| 6 | `m4nu_F_9dWU` | zh | 206.6 | yes | 4852329 | 13:23 |
| 7 | `JM9rx_hN1Ko` | zh | 204.2 | yes | 5289432 | 13:27 |
| 8 | `RIq7Tz9nYD8` | zh | 260.0 | yes | 7538600 | 13:30 |
| 10 | `7qeShSmmsNg` | yue | 259.1 | yes | 7878269 | 13:37 |
| 12 | `UmTB6E5mU5w` | yue | 318.9 | yes | 8744245 | 13:42 |
| 13 | `CvKvXNiXQZc` | yue | 217.0 | yes | 4954585 | 13:46 |
| 14 | `tDw_ULjZWA8` | yue | 259.9 | yes | 6758323 | 13:55 |
| 15 | `U_EgeFUTbW4` | yue | 261.1 | yes | 7087674 | 14:00 |
| 16 | `cPKfUWDmNbo` | yue | 212.7 | yes | 5866158 | 14:05 |

All times are 2026-11-03. Each id also has, in the library: the `.mp4`, a
`nonvocal/...---nonvocal.m4a`, a `karaoke/...ass`, a `subtitles/...srt` and a
`subtitles/...srt.generated`. None has a `lyrics/...lrc`, a `dereverb/` file or an
`alignment_debug/` json (the pilot's #1 has all three). `add_songs` logs were not looked at.

Transcripts: `zh_probe/phase0/transcripts/` holds only the four pilot ids
(`8NJVNkzhJM4`, `DYptgVvkVLQ`, `qu_FSptjRic`, `RPWDeLqsN0g`, each `.json` and `.txt`); none for
the twelve. The worksheet pages are still waiting on Ken's Windows run of
`phase0b_transcribe.py`.

### 2026-11-03 — Phase 0b worksheet pages built and published for the twelve (Sonnet 5.5), awaiting the friend's sheets

Ken ran `phase0b_transcribe.py` on Windows (the `chinese_karaoke` worktree at `6ca6bed`); the
twelve transcripts were written 14:13-14:17 to `zh_probe/phase0/transcripts/<id>.{json,txt}`.
Then `phase0b_worksheet.py --tag mandarin --songs 3,4,5,6,7,8` and
`--tag cantonese --songs 10,12,13,14,15,16` (library path and opencc as in the earlier entry).

Transcripts (from the json files):

| # | video id | language passed | model | audio s | whisper wall s | segments | last segment end s |
|---|---|---|---|---|---|---|---|
| 3 | `OR-0wptI_u0` | zh | large-v3-turbo.pt | 204.6 | 36.3 | 48 | 179.5 |
| 4 | `ocDo3ySyHSI` | zh | large-v3-turbo.pt | 271.4 | 12.0 | 66 | 262.58 |
| 5 | `IgvDMB5fR-8` | zh | large-v3-turbo.pt | 208.4 | 6.2 | 31 | 193.64 |
| 6 | `m4nu_F_9dWU` | zh | large-v3-turbo.pt | 206.6 | 6.3 | 26 | 192.68 |
| 7 | `JM9rx_hN1Ko` | zh | large-v3-turbo.pt | 204.2 | 7.4 | 45 | 181.9 |
| 8 | `RIq7Tz9nYD8` | zh | large-v3-turbo.pt | 260.0 | 14.1 | 68 | 239.96 |
| 10 | `7qeShSmmsNg` | yue | large-v3-turbo.pt | 259.2 | 32.8 | 61 | 239.28 |
| 12 | `UmTB6E5mU5w` | yue | large-v3-turbo.pt | 318.9 | 34.5 | 63 | 301.62 |
| 13 | `CvKvXNiXQZc` | yue | large-v3-turbo.pt | 217.0 | 16.2 | 40 | 198.14 |
| 14 | `tDw_ULjZWA8` | yue | large-v3-turbo.pt | 259.9 | 17.3 | 56 | 236.0 |
| 15 | `U_EgeFUTbW4` | yue | large-v3-turbo.pt | 261.1 | 19.1 | 46 | 250.1 |
| 16 | `cPKfUWDmNbo` | yue | large-v3-turbo.pt | 212.7 | 26.1 | 63 | 212.54 |

Build, per song. "Files scored" is every candidate text for the song against its transcript
(f1 of Han characters, `phase0b_score.py`); "within 0.05 of best" is the shortlist size;
"credit-type lines dropped" is the cleaning count summed over the cleaned files; "reference" is
the version the spots are measured against (the best scorer):

| # | page | video id | transcript Han | files scored | best f1 | lowest f1 | within 0.05 of best | credit-type lines dropped | versions | reference | spots |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | mandarin | `OR-0wptI_u0` | 434 | 6 | 0.402 | 0.000 | 5 | credit 7, singer_label_stripped 1 | 5 | A | 11 |
| 4 | mandarin | `ocDo3ySyHSI` | 389 | 7 | 0.797 | 0.000 | 5 | credit 3, title_or_artist 1 | 5 | E | 2 |
| 5 | mandarin | `IgvDMB5fR-8` | 190 | 4 | 0.966 | 0.000 | 3 | title_or_artist 2, credit 3 | 3 | B | 3 |
| 6 | mandarin | `m4nu_F_9dWU` | 230 | 3 | 0.955 | 0.955 | 3 | credit 3 | 3 | A | 0 |
| 7 | mandarin | `JM9rx_hN1Ko` | 265 | 4 | 0.909 | 0.115 | 3 | credit 3, netease_credit 4 | 3 | A | 0 |
| 8 | mandarin | `RIq7Tz9nYD8` | 518 | 5 | 0.901 | 0.886 | 5 | credit 6, singer_label_stripped 3 | 5 | A | 3 |
| 10 | cantonese | `7qeShSmmsNg` | 503 | 4 | 0.741 | 0.728 | 4 | tag_or_section 5, title_or_artist 1, credit 8, singer_label_stripped 3 | 4 | A | 1 |
| 12 | cantonese | `UmTB6E5mU5w` | 427 | 5 | 0.778 | 0.752 | 5 | credit 2 | 5 | A | 15 |
| 13 | cantonese | `CvKvXNiXQZc` | 390 | 7 | 0.783 | 0.040 | 6 | title_or_artist 1, credit 5 | 5 | D | 7 |
| 14 | cantonese | `tDw_ULjZWA8` | 360 | 4 | 0.846 | 0.832 | 4 | tag_or_section 2, credit 8, netease_credit 2 | 4 | A | 2 |
| 15 | cantonese | `U_EgeFUTbW4` | 198 | 7 | 0.513 | 0.000 | 6 | credit 5 | 6 | B | 15 |
| 16 | cantonese | `cPKfUWDmNbo` | 375 | 3 | 0.779 | 0.770 | 3 | credit 3, singer_label_stripped 8, netease_credit 1 | 3 | A | 2 |

#6 and #7 have no spots: their shortlisted versions agree after the script fold. #13 has six
shortlisted files in five versions (two cleaned to the same text). The full per-song score rows
and version-to-file lists are in the build files named below.

Browser check on the real pages (headless Chromium, 1280 px and 400 px): both load with no
console error; each song tab shows its spots; ticking a wording in the first spot of every song
that has spots shows "Your text has this wording."; the Send back tab shows the three steps and
an export that starts with the song's `=== <id> | <name> | NOT marked done | sheet ===` header; no
horizontal scroll at 400 px. It showed one defect: a song with no spots had a "Check these spots"
heading over an empty box. Fixed in `b2fc4ea` (it now reads "Nothing to compare" and goes on to
the editor); both pages were rebuilt after it. Not tested: a real friend using them, and the
Download button (it needs the artifact runtime).

Published as private artifacts (`downloads` capability, `document` icon, readable only by Ken
until he shares them):

- Mandarin Lyric Sheets: https://claude.ai/artifact/MbmJTXu1FKvwP9i6XuvQHa
- Cantonese Lyric Sheets: https://claude.ai/artifact/XyBcLGKi37Yokxwfgj3EFQ

Artifacts on the library, `zh_probe/phase0/worksheets/`: `mandarin.html`, `cantonese.html` (the
published page sources), `<tag>_labels.json` (version letter to candidate file names, per video
id; needed to read the friend's answers back) and `<tag>_build.txt` (the full score, cleaning and
version tables).

**Next:** Ken shares the two links with his friend (sharing is set from each page's Share menu;
the executor cannot change it). She pastes back the Copy-all or Download text; the executor then
splits it into `zh_probe/sheets/<video id>.txt` per song, as for the pilot.
