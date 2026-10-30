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
Next: Phase 1b.

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
