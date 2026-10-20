Model: Claude Opus 5.5 (design + judge); executor Sonnet per the phase table below

# Chinese character timing — standalone probe (Mandarin + Cantonese)

**Goal.** Find out whether any alignment method can give per-character
karaoke timing on Mandarin and Cantonese songs that Ken would sing to,
and what it costs. This is a measurement, not a build: nothing here
changes `pikaraoke/`. Whether and how to wire a winner into the pipeline
is decided after GATE Z2, from what this probe finds.

**Status: DRAFT 2026-10-20.** Phase 0 executed 2026-10-20 (see Results
log); waiting on Ken's confirmed sheets before Phase 1.

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
| 2 | corpus: surviving arms, GATE Z2 | Sonnet | Opus + Ken eyeball |
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

### Phase 2 — corpus (GATE Z2)

Surviving arms on the whole corpus, same artifacts and review sheets as
Phase 1. Pilot songs are not re-run.

**GATE Z2 (pre-registered; Ken may adjust the numbers before the run,
not after).** Per language, an arm **works** if it is singable (as is,
or with a few bad lines) on at least 7 of 8 songs. Among working arms,
the **pick** is the one with the most *singable as is* songs, then the
fewest bad lines in total, then the lower cost (time per song, VRAM,
download). No working arm for a language means no pick for it. Ken's
eyeball veto stands over the count.

### Phase 3 — write-up

Opus writes the record: the pick per language (or none), its cost, and
where it failed. It also lists what a production build would need,
without committing to one: language label and routing, the sheet
problems Phase 0b worked around, the caption-translation and Genius-query
issues, and how a per-character track meets the existing `.ass` writer.
Ken rules whether to plan a build.

## Out of scope

- Any change to `pikaraoke/` or to the shipped routes.
- Language detection (Ken labels each song by hand here).
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
