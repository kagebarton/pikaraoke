Model: Claude Opus 5.5 (author, 2026-10-28). Executor: Claude Sonnet 5.5.

# Movie subtitle slices

## Goal

For a video clipped from a movie, the admin pastes the stretch of the movie's
SRT subtitles that the clip covers, on **Repair lyrics**. A **Check fit** finds
where that stretch sits in the clip and says whether it fits. If it does, the
slice is saved with clip times and the song is timed by cue align from it.

The saved slice is a second kind of custom sheet: it outlives Regenerate, bulk
runs and Reset exactly as a `.custom.txt` sheet does, and only a Repair to
another source removes it.

## Decisions (Ken, 2026-10-28)

1. **Separate source.** A new "Movie subtitles" source on Repair, not SRT
   detection inside the Custom lyrics box. Storage and the survives-Reset rule
   are shared with custom sheets. **Ken ratifies a UI mockup (an Artifact)
   before any page code is written** (GATE A).
2. **No heard words on disk -> no check.** The page says to run Regenerate
   first. The check never queues GPU work.
3. **Dialogue stays.** Every pasted line is kept; removing spoken lines makes
   whisper trip over the speech it can no longer place.
4. **Singing the slice doesn't cover: say nothing.** Whisper may be
   hallucinating there; the matcher handles it.
5. **Branch off `dev`.** `custom_lyrics` and `similar_song_flag` have both
   landed there.

Defaults stated to Ken and not objected to:

- A Repair to any other source removes the `.custom.srt`, Custom lyrics
  included; saving either kind of sheet removes the other. One sheet per song.
- Coming back to Repair, the box holds the saved (already clip-timed) slice. A
  re-check of it fits at a zero shift, which also confirms the save.
- A two-speaker cue (`- line` / `- line`) stays one karaoke line, dashes
  removed: a cue has one time span.
- Movie subtitles carry markup the caption cleaner doesn't know (found in
  Ken's slices, 2026-10-28). Already handled at load by `clean_srt_line`:
  `[French accent]`, `(MEN GRUNTING)`, `<i>`, `♪`; a cue left empty is
  dropped. Not handled, and now stripped by the shared SRT cleanup (below):
  - **Speaker labels**, `MULAN:` / `TIMON:` / `MEN: Be a man`, at the start of
    a cue line, alone or inline. These are real tokens: they would show on the
    karaoke screen and be timed as sung. Capitals-only, so a lyric like
    `Listen: ...` survives; skipped when the whole file is typed in capitals
    (`srt_cues._is_all_caps`), where every line would look like a label.
  - **`*` used as a song marker** (`* Hakuna matata *`, the Lion King slices),
    as a standalone token only, so a censored `f***` keeps its stars.
  - **Dialogue dashes**, at a line start or after `.`/`!`/`?`
    (`- Hakuna matata. - What?`).

  The tokeniser already drops `*` and `-` for matching, so those two are
  display-only; labels are the one that hurts the align.

  **Where (Ken, 2026-10-28): the shared SRT cleanup, not a movie-only one.**
  It goes in `srt_cues.cue_spans_from_srt`, the one funnel every SRT file
  passes through (pipeline load, `library_regen` prefill, this feature's fit),
  applied per raw cue line before `clean_srt_line`, with the capitals guard
  taken over the whole file. `clean_srt_line` itself is untouched, so the
  YouTube auto-caption filter in `ytasr` (which calls it per segment) keeps its
  behaviour. Scan of the 48 YouTube caption SRTs in the library, 2026-10-28:
  one has labels (The Lion King - Can You Feel The Love Tonight, `NALA:`
  `SIMBA:` `CHORUS:` `BOTH:`, 5 lines), none has `*` markers or dialogue
  dashes, so the other 47 should load unchanged (Phase 2 smoke checks it).

  Known limit, accepted (review of `1f0b07b..615146a`, finding 5): in a
  normally cased file the label rule also eats a lyric line that opens with a
  capitals word and a colon (`OK: let's go` -> `let's go`, `I SAID: go` ->
  `go`). No library caption has one. Narrowing the rule further would start
  missing real labels.

## Decisions (Ken, 2026-10-29)

6. **Whole films are supported** (Phase 3 item 4). A pasted SRT may be the
   whole film's; the fit finds the clip's stretch. Cap: 3,000 cues
   (`srt_slice_fit.MAX_CUES`, refused as `too_long`), plus a 1,000,000-character
   ceiling before parsing (`library_tools.MOVIE_SUBTITLES_MAX_CHARS`). The
   typed sheet keeps its 100,000.
7. **Heard words get their own file, for every song, later** (review of
   `99409f5..1a6f1da`, finding 2). A transcribe run keeps no heard words, so
   movie subtitles can't be checked on a song that was only ever transcribed.
   Fix chosen: move the heard words out of the bundle into a file of their
   own that every route writes (not a lyric-less bundle). Its own feature after
   Phase 4 of this branch; logged in `plans/open-issues.md`. Until then
   decision 2's "Regenerate first" is said only to a song with a bundle; a
   song with none is told it doesn't keep heard words yet.

## Test songs

Movie clips in the library (Ken, 2026-10-28). Heard words = the bundle's
`transcribe_words`; ASR = `subtitles/<stem>.en.asr.json3` on disk.

| Song (short) | Origin now | Heard words | ASR | Note |
|---|---|---|---|---|
| Be Our Guest (1991, UHD) | genius | 414 | yes | Blu-ray rip: speed-factor candidate |
| Belle (1991, UHD) | genius | 592 | yes | Blu-ray rip: speed-factor candidate |
| Colors of the Wind (Blu-ray) | genius | 311 | yes | Blu-ray rip: speed-factor candidate |
| Mulan, I'll Make a Man Out of You | genius | 312 | yes | |
| Hakuna Matata (4K) | custom | 352 | yes | has a hand-made `.custom.txt`; a movie Repair removes it (backup keeps it) |
| The Next Ten Minutes | genius | 359 | no | lyric video over movie audio |
| Seasons of Love (HD) | genius | 176 | yes | compilation: fits only if the *audio* is one continuous take; else the refusal case |
| Wicked: For Good (Movieclips) | genius | 98 | yes | dialogue-heavy; no slice, so the low-match case rests on Mulan and synthetic tests |
| Can You Feel the Love Tonight | srt | 0 | no | needs one Regenerate on Phase 3 code first |
| Part of Your World | srt | 0 | no | same |
| A Whole New World (Mena Massoud) | srt | 0 | no | same |

**Real slices stay out of the repo.** Movie subtitles are copyrighted text and
`origin` is public GitHub. Ken supplies them in
`~/pikaraoke-songs/movie_subs/`, named by song title, not video stem (2026-10-28:
`belle`, `be our guest`, `can you feel the love tonight`, `hakuna matata`,
`mulan`, `pocahontas` = Colors of the Wind, `seasons of love`, `the next ten
minutes`). No slice for For Good, Part of Your World or A Whole New World.
Unit tests use short synthetic cues only.

## Design

### Where the slice lives

`<library>/lyrics/<stem>.custom.srt`, UTF-8, the pasted cues with **clip
times** (the fit applied, cues outside the video dropped, edge cues clamped).
Cue text is kept as pasted (labels, `*`, dashes, italics tags, `[...]`,
`(...)`, `♪`); the pipeline's load step (`cue_spans_from_srt`) is the one
cleaner, so the check and the karaoke see the same lines.

The `.srt` suffix sends the sheet down the cue-align route with no pipeline
change: `LyricAlignStage._load_lyrics` routes by suffix. It must **not** live in
`subtitles/`: `find_local_srt` and `_find_youtube_srt_path` would read it as a
YouTube caption.

### Custom sheets become two kinds

In `library_regen.py`:

- `CUSTOM_SHEET_SUFFIX` becomes the pair `.custom.txt` / `.custom.srt`.
  `custom_sheet_path(song)` becomes a lookup of the one that exists (None for
  neither); writers name the kind they write.
- The plan for an SRT sheet: `Plan(kind="seed", lyrics_path=<.custom.srt>,
  seed={"lyrics_origin": "movie_srt"}, custom_text=..., label="movie subtitles")`.
  The bundle origin `"movie_srt"` is new: `"srt"` already means the YouTube
  caption, and History reads origins from old bundles where no file says the kind.
- `is_custom_plan` covers both origins (Reset, `replaces_custom` and the
  bulk-run `custom` flag all key on it). `_ytasr_seed` stays txt-only: the cue
  route never reads the third source.
- `apply_custom_choice` writes the plan's kind and deletes the other kind.
- `KEEP_ON_RESET` and `snapshot_lyric_files` cover both suffixes.
- `library_tools.repair`: new source `"movie"`; `replaces_custom = source not
  in ("custom", "movie")`. No LRCLIB pick: the cue route never uses LRCLIB
  fills, and `_lrclib_state` already returns `"n/a"` for any origin outside
  genius/custom.

`library_status.SongStatus.custom_sheet` stays a bool (either kind on disk);
the pages that need the kind read `origin` or the sheet's suffix.

### The fit check: `pikaraoke/lib/srt_slice_fit.py` (new, pure)

Input: the pasted text, the heard-word streams on disk, the video length.
Output: a `SliceFit` with `status` (`fits` / `refused` / `no_reference` /
`not_srt`), a refusal reason, matched and total cue counts, the shift, the
speed factor, the dropped-cue count, and the corrected SRT text when it fits.

1. **Parse.** `srt.parse` (strict; an `SRTParseError` -> `not_srt`). The cleaned
   cue texts and spans for matching come from `cue_spans_from_srt`, so they
   match what the pipeline will load. The rewrite works on the raw parsed cues.
2. **Heard words.** Bundle `transcribe_words` and the ASR json3 words
   (`ytasr.parse_json3`), each tried on its own and the better fit kept (more
   matched cues). They are never merged: overlapping duplicates would confuse
   an in-order match. Neither present -> `no_reference`.
3. **Pass 1, order only.** Tokenise cue texts (`joint_match._tokenise_lines`,
   `token_align._normalize_token`). Give both streams pseudo-times by rank
   (0..1) and run `token_align.match_words_to_tokens`. Movie times can't be used
   yet: the time tiebreak is meaningless at an hour's distance. Each cue's
   anchor is the start of its first matched word.
4. **Fit.** For each speed factor `s` in {1, 25/23.976, 23.976/25} (PAL
   speed-up and its reverse; a subtitle file made for a 25 fps release of a
   23.976 fps film drifts about 8 s over three minutes), scale the cue spans by
   `s` and call `srt_cues.offset_mad_against_cues`. Keep the factor with the
   smallest spread that didn't bail. **GATE B:** when every factor bails on
   spread, a free (Theil-Sen) speed within 10% of 1 is tried and vetted by the
   same spread limit (Results row 14: two real clips run at about 1.07). The
   earlier "free speed fits noise" worry did not hold: on wrong-song anchors it
   passes about as rarely as the factors do. **GATE B follow-up (row 15):** the
   free speed is computed on every pick, and it also replaces a factor that
   passed when its spread is lower and it moves the cues more than 0.75 s
   across the slice (`|free - factor| x` the anchors' cue-start span). The
   factor then leaves at most about 0.4 s at the slice's ends.
5. **Pass 2, timed.** Rematch with the tokens' cue-expected times mapped
   through `(s, shift)`, then refit, speed included (the same pick as step 4,
   on pass 2's anchors). This fixes the repeated chorus lines that pass 1 can
   hand to the wrong instance.
6. **Verdict.** Fits when the fit didn't bail and the matched share of the
   cues that land inside the video clears a floor (0.25, set at GATE B).
   Refusal reasons: too few matched; matches disagree (worded for the admin as
   "the clip may be cut from several scenes, or these subtitles are for a
   different release").
7. **Rewrite.** Map every cue `t -> s*t + shift`, drop cues wholly outside
   `[0, video length]`, clamp the edge ones, renumber, `srt.compose`.

Known effect to check at GATE B: the fitted shift is the median of
`heard start - cue start`, so it absorbs the subtitles' display lead and the
saved cues sit on sung onsets. Cue align's own lead fit (`fit_offset`) should
then come out near zero, and its section pad covers the onset.

The Repair POST **re-runs the fit on the server** and saves that result. The
page's check is a preview and its numbers are never trusted.

### Heard words on the cue route

`LyricAlignStage._run_cue_align` transcribes the whole stem (via
`_dereverb_gate`) and discards the words. Return them and pass them to the
debug capture as `transcribe_words`, as the joint route does. Then a song timed
from a YouTube caption or a movie slice keeps a reference for its next check.

### Page and labels

Built to the mockup ratified at GATE A. Until then, the expected shape:

- `song_repair.html`: a "Movie subtitles" source, a box with Open file
  (`.srt`), **Check fit**, a result line, and Regenerate enabled only by a
  passing check of the box's current text (any edit clears the result). No
  step 2.
- `song_info.py`: a route `POST /song_info/subtitle_fit {song, text}` -> the
  `SliceFit` fields, admin only. `repair` passes `source="movie"`.
  `_current_source`, `_source_name`, `_route_text` (the cue_align text today
  says "YouTube caption"), `_pick` and `_versions` learn `movie_srt`.
- `library.py` `_now_text` and `library_tools._now`: "Now: movie subtitles".
- `library_tools.custom_start`: the movie box's prefill is the saved
  `.custom.srt`, else blank.

## Phases

### Phase 0: branch and fixtures

- [x] `git switch -c movie_subtitles dev`; tree clean apart from untracked
      `plans/`.
- [x] Ken's slices present in `~/pikaraoke-songs/movie_subs/` (stop and ask if
      not; Phase 1 does not need them, Phase 2 does).

### Phase 1: mockup -> GATE A (Ken)

- [x] Build an HTML mockup of Repair lyrics with the new source, styled from
      `song_repair.html`'s own CSS (dark page, `rp-*` classes), published with
      the Artifact tool. Clickable states: source picked and empty; pasted, not
      checked; checking; **fits** (matched x of y, shift as h:mm:ss, speed note
      only when not 1, dropped-cue note only when > 0); **refused** (each
      reason); **no heard words** (Regenerate first); **not SRT**; text edited
      after a pass (result cleared, Regenerate off); the source when it is
      `current`.
- [x] **GATE A: Ken ratifies the mockup.** Record his changes in the Results
      log. No page code before this. If the mockup changes what the check
      returns, update the `SliceFit` fields above first. (Row 7: taken as ratified
      as built, v20; row 12: Ken said so in words.)

### Phase 2: fit module -> GATE B (Opus)

- [x] Shared SRT cleanup in `cue_spans_from_srt` (Decisions), its own commit,
      first: the fit's matching depends on it. Tests in the `srt_cues` tests:
      label alone on a line and inline, label after a dialogue dash,
      capitals-only file keeps its "labels", `*` markers stripped but `f***`
      kept, mid-line dialogue dash; and a smoke that the other 47 library
      caption SRTs produce the same lines before and after (log the count).

- [x] `srt_slice_fit.py` per the design, with tests on synthetic cues: plain
      shift; PAL speed in both directions; a cut clip (two shifts) refused; cues
      past both ends dropped and clamped; dialogue lines with no heard match
      don't sink a fit; a repeated chorus matched to the right instance;
      `no_reference`; `not_srt`; a re-check of a corrected slice fits at zero
      shift and speed 1.
- [x] A calibration script, `scripts/movie_srt_fit_report.py`, runs the fit
      for every slice in `~/pikaraoke-songs/movie_subs/` against that song's
      on-disk words. Slices are named by title: resolve each to its library
      stem by case-insensitive substring, and stop on zero or several matches
      (`pocahontas` needs a one-line alias to Colors of the Wind). It prints per song: heard source used, matched/total, cues
      in the video, shift, speed, spread, verdict, for both heard sources. Rows
      go to the Results log raw.
- [x] **GATE B (hand to Opus): set the matched-share floor, and confirm or
      replace `offset_mad_against_cues`' anchor count and spread limits for
      this use.** Don't pick the numbers on the executor side.
      Two checks from the review of `1f0b07b..615146a` ride on the same table:
      (a) pass 2 keeps pass 1's speed and never re-picks it from pass 2's
      anchors; if any row's speed is wrong against its `Slope`, run pass 2
      per speed factor and keep the best (3x the match cost). (b) A cue's
      anchor is its first matched word, compared against the cue start with
      no allowance for unheard opening words; if correct slices sit near the
      spread limit, subtract that word's in-cue expected offset
      (`_token_expected_times`) first.
      (Row 14: floor 0.25; anchor count 4 and spread 0.75 s confirmed; free
      speed added; (a) done as a re-pick on pass 2's anchors; (b) not needed.
      Row 15: the free speed also replaces a passing factor when its spread is
      lower and it drifts more than 0.75 s across the slice; code by the
      executor.)

### Phase 3: storage, plan, cue-route words

- [x] The two-kind custom sheet in `library_regen.py` / `library_tools.py`
      / `library_status.py`, per the design. Extend the existing custom-sheet
      tests: Reset keeps `.custom.srt`; saving one kind deletes the other; a
      Genius/caption/transcribe Repair removes either; the bulk run sends a
      movie song to `reuse` in every mode. (Row 21.)
- [x] The cue route captures `transcribe_words`; test it reaches the bundle. (Row 22.)
- [x] `repair(source="movie", text=...)` re-runs the fit and refuses
      (`RegenError`, admin wording) anything but `fits`. (Row 23.)
- [x] (Timings row 24; real films row 25; decision 6; commit `459e43c`, row 26.) Decide a size cap on the pasted text (review of `1f0b07b..615146a`,
      finding 8). The match is pure Python, runs twice per stream, and runs on
      both the preview and the Repair POST; a whole pasted movie SRT (~1500
      cues) costs seconds per request on a server worker. The slices run
      33-122 cues. Time a whole-film paste, then pick a cue-count limit and
      the page's wording for refusing it. The free speed (GATE B) adds a
      pairwise slope, quadratic in anchors: 0.36 s at 1500, and since row 15
      on every speed pick (twice per stream).

### Phase 4: page and labels

- [x] (Rows 28-30: labels `7f07006`, route `4822725`, page `cc88169`.) The ratified mockup, built into `song_repair.html`, plus the route and
      the label changes listed above. The speed note's (i) says the subtitles
      "were made for a different frame rate"; since GATE B a free speed can be
      any change up to 10% (Belle: 7.1%), so word it to cover a sped-up or
      slowed clip too. Route tests: admin only; each status's
      JSON; Repair re-fits on the server.
      Since row 26-27: the page also shows `too_long` (the cue cap), and the
      no-heard-words refusal has two wordings, picked by whether the song has
      a bundle (`_slice_refusal(fit, regenerate_helps)`); the preview route
      calls `check_movie_slice` and must pass the same flag. Review finding 3
      of `99409f5..1a6f1da` lands here: Song Info's and History's labels and
      `_current_source` for the `movie_srt` origin.

### Phase 5: end to end -> Ken's manual checks

- [x] (Row 35.) Repair Belle, Seasons of Love and Hakuna Matata (labels, `*` markers,
      and it replaces a custom sheet) from Ken's slices on the local GPU. Record per song: verdict, cue align's fitted lead (expect near zero),
      cue-align fill/realign line counts, and Ken's read of the karaoke.
- [x] (Row 35.) Regenerate Can You Feel the Love Tonight (the one caption song with a
      slice) on its YouTube caption: its karaoke no longer shows `NALA:` etc.,
      and the cue route's saved words make its slice checkable. Then check it.
- [x] (Row 35.) Reset one movie song: the `.custom.srt` survives and is reused.

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
| 1 | 2026-10-28 | 0 | `git switch -c movie_subtitles dev`; `git status --short` | Branch `movie_subtitles` at `1f0b07b` (dev HEAD). Tree: `?? plans/movie-subtitle-slice.md` only. Plan file still untracked (not committed; no instruction to). |
| 2 | 2026-10-28 | 0 | `ls -la ~/pikaraoke-songs/movie_subs/`; `git check-ignore` on a slice | 8 files, all present: `belle.srt` 7559 B, `be our guest.srt` 5768, `can you feel the love tonight.srt` 3020, `hakuna matata.srt` 6083, `mulan.srt` 3604, `pocahontas.srt` 2910, `seasons of love.srt` 2269, `the next ten minutes.srt` 4204. Git reports the path is outside the repository, so nothing there can be staged. Not opened or read in Phase 0/1. |
| 3 | 2026-10-28 | 1 | Mockup published as a Design (artboard) Artifact: https://claude.ai/artifact/NoQJAQknmdz2s1CcJD3vNJ (private) | 13 artboards, 420 px wide. **Try it** (`Main`, clickable: Open file loads a sample, Check fit returns the outcome picked in a mock-only strip, Regenerate on only after a pass, any edit clears the result, Cancel resets). Static boards, one per state, all rendered from `Main` via `variant`: empty; pasted, not checked; checking; edited after a pass; fits; fits with speed + dropped lines; current source (saved slice, unchecked); saved slice re-checked (zero shift); refused: too few matched; refused: matches disagree; no heard words; not SRT. Sample cues are invented, no real film text. Built from the app's dark tokens and `rp-*` rules. **Not rendered, screenshotted or syntax-checked**: no `node` on the box, and the Design type forbids verifying unless asked. |
| 4 | 2026-10-28 | 1 | What the mockup commits to (for Ken to ratify at GATE A) | (a) "matches x of y": y = cues inside the clip; cues outside are dropped and counted on their own line. Consistent with Design step 6, so no `SliceFit` field change. (b) Shift reads "move 0:42:05 earlier" / "later"; zero reads "Timing unchanged (0:00:00)". (c) Speed note only when the factor is not 1 ("Speed adjusted by 4.3%: the subtitles were made for a different frame rate"); dropped note only when > 0. (d) Regenerate stays off until the current box text passes; any edit clears the result; a saved (current) slice also needs a re-check. (e) Check fit is a teal outline, the only new control style. (f) Box label folds in decision 2 (words already heard, never queues work) instead of an (i). (g) No step 2: Regenerate queues straight away, same (i) text as caption/transcribe. (h) Muted text is `#a3b0b2`, not the app's `#8c9b9d`: the app's grey is about 3.8:1 on the `#343c3d` source cards, under 4.5:1. Info-blue likewise lightened to `#5cb0ee`. Ken's call whether to match the app exactly. (i) Wording clash: the no-heard-words message tells the admin to "Regenerate the song from Song info", and this page's own button is "Regenerate song". |
| 5 | 2026-10-28 | 1 | GATE A | **Open. Awaiting Ken.** No page code written. Ken's changes go in this log as row 6 onward. |
| 6 | 2026-10-28 | 1 | Ken: "Follow the conventions in commit 8b89c17 and refine the mockup by putting long notes behind (i) icons". Read `git show 8b89c17` (`info_tip.html`, `library-pages.css`, `library-pages.js`, `song_repair.html`). Published as versions 15-20 of the same Artifact, one file per publish: `Main`, `TipBox`, `TipSpeed`, `TipRefusal`, `TipRegen`, `canvas.json`. Not rendered or syntax-checked. | Conventions copied: (i) beside what it explains; hover shows, tap pins until a tap elsewhere, tap on a pinned one closes; note 13 px on `#1f2424` with a `#8c9b9d` border, max 300 px, below the (i) or above it at the page bottom; 16 px icon, 36 px tap area (44 px in the button row), muted until open then link teal; back link above the title (13 px, snug); a source's description only once it is chosen. **Behind an (i):** the box explanation (heading "Movie subtitles"; the textarea's visible label is gone, `aria-label` instead), the frame-rate reason on the speed line (visible line now "Speed adjusted by 4.3%."), the what-to-try hint on each refusal (on the headline: too few, disagree, not SRT), the Regenerate note (was a `title` attribute). **Still visible:** headlines, counts, shift, dropped-lines line, the no-heard-words reason and action with its link, the status line under Check fit (empty, not checked, edited, saved slice), the "current" tag, the chosen source's description. New row of 4 boards ("Notes open") pins one note each, because static boards cannot be hovered: box, speed, refusal (disagree), Regenerate. Mock limits: notes anchor to their row, not centred on the (i) as `library-pages.js` places them; no Escape-to-close, no scroll-to-close. Real-page cost to note for Phase 4: `.rp-sec` is `justify-content: space-between`, so a heading with an (i) needs the (i) inside the title span; the Custom lyrics label stays visible on the live page, so only this section drops its label. |
| 7 | 2026-10-28 | 1 | GATE A | Ken's resume prompt (after `/compact`) read: "Resume plans/movie-subtitle-slice.md at GATE A ... Next: Phase 2 starting with the shared SRT cleanup in cue_spans_from_srt. Stop at GATE B for Opus; don't pick thresholds." It carried no changes to the mockup and the "Ken's changes" line of the earlier draft was gone. Executor read this as ratified as built (Artifact v20, rows 3, 4 and 6); Ken has not said so in words. The open calls from row 4 (h, i), row 6 (refusal hints behind the (i)) and the saved-slice re-check stand at the mockup's choices, unresolved. `SliceFit` fields: none of the mockup's states needs a field the design lacked. |
| 8 | 2026-10-28 | 2 | Shared SRT cleanup, commit `fc6c485` (`srt_cues.py`, `test_srt_cues.py`). Census of Ken's slices first (marker shapes only, text not copied): labels `can you feel the love tonight` WOMAN/SIMBA/NALA/CHORUS x1 each, all inline before a `*` marker; `hakuna matata` TIMON x3, PUMBAA x1, SIMBA x2, some alone on a line; `mulan` MUSHU, MULAN, SHANG, MEN x1 each, three alone on a line, `MEN:` inline; `*` lines: 53 (can you feel), 57 (hakuna); dash lines: belle 3, hakuna 12, the next ten minutes 6; `<i>` tags: none in any slice. Smoke: old (`git show HEAD:...`) vs new `cue_spans_from_srt` over every `subtitles/*.srt` | 48 files: **47 identical, 1 changed** (The Lion King - Can You Feel The Love Tonight: 5 cue lines lost their `NALA:` `SIMBA:` `NALA:` `CHORUS:` `BOTH:` prefix, cue count 32 -> 32, spans untouched). Tests: `test_srt_cues.py` 8 -> 14 (own-line label drops the cue; inline label, `MR. POTTS:`, `<i>MEN:`; `Listen:` survives; label after a dash or star; capitals-only file keeps its labels; `*` stripped, `f***` kept; dialogue dash at line start and after `.!?`, `-derful` kept). Full suite 2594 passed. Self-review caught one defect before commit: the leading-decoration pattern (a repeated group whose first branch was itself `[-*]+`) could backtrack exponentially on a long run of `*`/`-`; now a single-character alternative. Timed on 5000-char runs of `*`, `- `, `<i>`, capitals: <= 1 ms each. Rules as built: label = capitals/digits/`.'&/+ -` (2-30 chars) then `:` then space or end, after any leading dashes, stars, notes, tags; dash = `-` run followed by whitespace (an attached hyphen is a word split across cues); star = a `*` run with no non-space neighbour. |
| 9 | 2026-10-28 | 2 | `srt_slice_fit.py` and `test_srt_slice_fit.py`, commit `6aa4b14` | Built to the Design section, with these choices the plan did not fix: (a) a cue is **found** when at least half its tokens matched (`FOUND_MIN_TOKEN_SHARE = 0.5`), anchor = first matched word's start; `matched` counts found cues. (b) `MIN_MATCHED_SHARE = 0.5` is a **placeholder** so the module runs, not calibrated: GATE B sets it. (c) If pass 1 bails on spread for every factor, pass 2 still runs on the least-spread factor (it can repair a mixed-instance match); it stops only on `few_anchors`. (d) `total` = cues inside the clip once (speed, shift) is known (`dropped` = cues wholly outside), else every cue pasted; a `disagree` refusal carries the (unreliable) shift. (e) The module reads nothing: `heard_streams(bundle, asr_json3_text)` shapes the two streams, so the Phase 3 caller does the file reads (`read_bundle`, the `.en.asr.json3`) and the clip length. (f) The matcher DP and offset limits are the shared ones, untouched (`PRIOR_MIN_ANCHORS = 4`, `PRIOR_MAX_MAD_S = 0.75`). Pass 1 and 2 are `_match_by_order` / `_match_by_time`. Tests 16: plain shift; PAL both directions; clip cut from two scenes -> refused/disagree; cues past both ends (2 + 7 dropped, first cue starts 0, last ends at the clip length, renumbered); 6 unheard dialogue cues of 30 still fit (24/30); re-check of a corrected slice -> speed 1, shift < 0.01, 30/30, dropped 0; wrong text -> refused/too_few; better stream kept; no_reference; not_srt (prose, empty, blank); CRLF input; `heard_streams`; repeated chorus. Full suite 2610 passed. The chorus case is tested on `_match_by_time` directly: end to end the median ignores a few wrong-instance anchors, so `SliceFit` cannot show it. Seeded search for a case where pass 1 picks a wrong instance and pass 2 repairs it (1500 trials, 6 chorus-ish blocks, 35% of lines heard): pass 1 shift right in 1490, off in 6, no result in 4; final: 107 fits-right, 1393 refused (share under the placeholder), no repaired case found. Timing (random words, 600 heard words, two streams, pass 1 only): 122 cues 0.1 s, 500 cues 0.4 s, 1500 cues 1.3 s. |
| 10 | 2026-10-28 | 2 | Calibration script, commit `615146a` (amended once: `chmod +x`, the shebang hook failed). `python scripts/movie_srt_fit_report.py --cross` over `~/pikaraoke-songs/movie_subs/`. Raw output in "Phase 2 calibration output" below. `--cross` (each slice against every other slice's song, transcribe words) is an addition to the plan, for the wrong-song cases a floor must refuse. | All 8 slice names resolved to exactly one video by substring, `pocahontas` included (its filename says "Pocahontas - Colors of the Wind"), so the planned alias was not needed and was not written. Songs fit by the fixed factors: Hakuna Matata (1.0, spread 0.155 / 0.142 s, 75/94 and 72/94), Mulan (0.9590, 0.280 / 0.240, 49/50 and 44/50), Colors of the Wind (1.0, 0.253 / 0.081, 40/40 both), The Next Ten Minutes (transcribe only, 1.0, 0.280, 67/70), Seasons of Love (transcribe 0.9590, 0.232, 26/33; its ASR has 26 words, 0 found). **Refused as disagree under the fixed factors: Belle** (best factor 1.0427, spread 1.713 / 1.470 s) **and Be Our Guest** (1.0427, 1.007 / 0.867 s). Can You Feel the Love Tonight: no heard words (as expected until Phase 3 code is regenerated) -> no_reference. Wrong-song runs: 40 of 42 found 0 cues; the other 6 found 4-6 cues (refused/disagree, spread 7.1-49.9 s). Bundle `media_duration_s` is None for Seasons of Love and The Next Ten Minutes (schema 8); the script fell back to `probe_duration` (195 s, 454 s). |
| 11 | 2026-10-28 | 2 | Exploratory, not in the repo: free Theil-Sen slope of heard time vs cue time over the order-only anchors (printed as the `Slope` column), then pass 2 refitted at that free slope. | Free slopes: Belle 1.0714 (transcribe) / 1.0726 (asr); Be Our Guest 1.0664 / 1.0647; Mulan 0.9611 / 0.9599; Seasons of Love 0.9558; Hakuna Matata 1.0012 / 1.0016; Colors of the Wind 0.9981 / 1.0001; The Next Ten Minutes 1.0004. The speed factors tried are 1.0427 and 0.9590. Refit at the free slope: Belle transcribe 113 anchors, 113/122 found, spread 0.212 s, no bail; Belle asr 50 anchors, 50/122, 0.271; Be Our Guest transcribe 77, 77/92, 0.206; asr 52, 52/92, 0.219; Mulan 49 anchors 49/50 0.314 / 44, 44/50, 0.249; Seasons of Love transcribe 26, 26/33, 0.156. |
| 12 | 2026-10-28 | 1 | GATE A, in words | Ken: "the artboard is ratified". Applies to the Artifact as built, v20 (rows 3, 4, 6). Takes the open calls at the mockup's choices: refusal hints behind the (i), lightened greys `#a3b0b2` / `#5cb0ee`, the Regenerate wording, a saved slice needing a re-check before Regenerate. No changes asked, so no `SliceFit` field change. Phase 4 builds to this. Nothing else started: Phase 2 still stops at GATE B. |
| 13 | 2026-10-28 | 2 | `/code-review high 1f0b07b..615146a`, 3 axis finders, 10 findings | Fixed in one commit: (1) `fit_slice` caught only `SRTParseError`, so an out-of-range timestamp raised `OverflowError`; now `not_srt`. (4) a dialogue dash after `*`/`♪` survived (`* - What?`); the dash rule's line-start prefix now takes `*♪♫` and tags (not dashes: a dash-eating prefix made a 20,000-dash line take 1.9 s). (6) a zero-length cue counted as inside the clip but was dropped from the sheet; one `_clip_span` rule now does both. (9) dead `if best else None` in `_best_speed`; hand-numbering `srt.compose` redoes. (10) report script fell back to clip length 0.0, which printed a plausible `too_few` row; now exits. Checks: 2612 tests pass; `cue_spans_from_srt` output identical to HEAD on all 56 SRTs (48 library captions + 8 slices); `--cross` report output byte-identical to HEAD. Deferred to GATE B: (2) speed not re-picked in pass 2, (3) anchor in-cue offset. Phase 3: (8) paste size cap. Accepted, not fixed: (5) label false positives (Decisions); (7) `fit_slice`'s stream pick compares `matched` across refusal kinds, where it counts different things; only changes which refusal hint shows. Left: double parse in `fit_slice`, double `clean_srt_line` in `cue_spans_from_srt` (the first strips `[MUSIC]`-style capitals before the all-caps share). |
| 14 | 2026-10-28 | 2 | GATE B (Opus), commit `9c03f50` (`srt_slice_fit.py`, `movie_srt_fit_report.py`, `test_srt_slice_fit.py`). Raw output in "GATE B calibration output" below. | **Speed.** Belle and Be Our Guest were refused/disagree under all three factors; their free slopes (row 11) are 1.0714/1.0726 and 1.0664/1.0647, no factor near. Changed: when every factor bails on spread, `free_speed` (Theil-Sen, pairs more than 20 s apart in cue time, `MIN_SLOPE_SEPARATION_S` moved from the script) is tried if within `MAX_FREE_SPEED_CHANGE = 0.1` of 1, vetted by the same spread limit. Result: Be Our Guest fits at 1.0667 / 1.0660 (spread 0.192 / 0.271, 77/92 and 52/92); Belle at 1.0711 / 1.0741 (0.205 / 0.252, 113/122 and 50/122). Every row that fit at row 10 is identical (factor kept). Wrong-song runs: all 49 still refused (44 too_few with 0 cues, 5 disagree with 4-6 anchors, spread 7.1-49.9 s; one spread moved 9.700 -> 7.512). Row 10's "40 of 42 found 0 cues; the other 6" miscounted the same 49 runs: 44 found 0, 5 found 4-6. Simulation, scratch, not in the repo (`freeslope_sim.py`, 20,000 trials per n, n sorted-uniform cue starts over 60-300 s against n sorted-uniform heard starts over 120-450 s, i.e. in-order wrong anchors): share with spread <= 0.75 s at the best factor / at a bounded free slope: n=4 0.49% / 0.53%; 5 0.43 / 0.47; 6 0.06 / 0.07; 8 0.005 / 0.025; 10 0.01 / 0.005; 12-20 0 / 0. So no separate anchor minimum for the free speed. Timing of `free_speed` (synthetic, one anchor per cue): 122 anchors 0.00 s, 500 0.03 s, 1500 0.36 s. **Floor.** `MIN_MATCHED_SHARE` 0.5 -> **0.25**. Right-song shares: Belle asr 50/122 = 0.41 (lowest; refused at 0.5 though spread 0.252 with 50 anchors), Be Our Guest asr 0.57, Hakuna Matata 0.77 / 0.80, Seasons of Love 0.79, Be Our Guest 0.84, Mulan 0.88 / 0.98, Belle 0.93, The Next Ten Minutes 0.96, Colors of the Wind 1.00 / 1.00. Wrong-song: at most 6/94 = 0.064. 0.25 is 1.6x under the lowest right share and 3.9x over the highest wrong one. A low share with a tight spread leaves the unheard cues at the subtitles' own shifted times. **Anchor count and spread: confirmed** at the shared `PRIOR_MIN_ANCHORS = 4`, `PRIOR_MAX_MAD_S = 0.75`, no slice-specific constants. Right fits: 26-113 anchors, spread 0.081-0.280 s (free-speed fits 0.192-0.271). Wrong: 0-6 anchors, spread >= 7.1 s. No real case between. Residual risk the data cannot rule out: per the simulation, 4-5 wrong in-order anchors agree within 0.75 s about 0.5% of the time, and the 0.25 floor only stops them on a slice of more than 16-20 in-clip cues. **Review check (a)** (pass 2 never re-picks speed): every factor row's speed sat on its slope (Hakuna 1.0 vs 1.0012/1.0016, Mulan 0.9590 vs 0.9611/0.9599, Colors 1.0 vs 0.9981/1.0001, Ten Minutes 1.0 vs 1.0004, Seasons 0.9590 vs 0.9558); Belle and Be Our Guest were wrong against theirs, but no factor was right, so per-factor pass 2 would not have helped. Done instead as a re-pick: pass 2 calls the same `_best_speed` on its own anchors (no extra match, not 3x the cost). It changed no factor row. **Review check (b)** (anchor in-cue offset): not needed. Right slices' spreads, 0.081-0.280 s, are at most 37% of the 0.75 s limit. **Not checked here:** cue align's own lead (`fit_offset`) near zero after the shift absorbs the display lead (Design, "Known effect"); it needs a cue-align run, so it rides on Phase 5's per-song record. Tests: +2 (speed 1.07 fits free within 0.001; 1.15 refused/disagree, and it fits when the bound is raised to 0.2, so the bound is what refuses it), placeholder-floor test removed; 19 in the file; full suite 2613 passed. |
| 15 | 2026-10-28 | 2 | GATE B follow-up (Opus): margin for the free speed beating a passing factor. Review finding: `_best_speed` (`srt_slice_fit.py:308`) tries the free speed only when every factor bails, so a factor that just passes beats a near-exact free speed. Scratch scripts, not in the repo: `margin_real.py`, `margin_sim.py`, `margin_eval.py`, `margin_patch.py` (the candidate, monkeypatched over `_best_speed`), `margin_verify.py`. Raw output in "GATE B follow-up output" below. No code changed. | **Form: drift**, the time the free speed moves the cues across the slice against the best factor, `abs(free - factor) * (max - min of the anchors' cue starts)`, in seconds. **Value: 0.75 s**, together with the free spread being lower than the factor's. The rule as decided: compute `free_speed` on every `_best_speed` call (bound `MAX_FREE_SPEED_CHANGE` unchanged). If the best factor bailed, behaviour as at row 14. If it passed, the free speed replaces it only when its spread is lower and its drift is > 0.75 s. With the shift at the median offset, a kept factor's worst cue error is about drift / 2, so at most about 0.4 s at the slice's ends. **Real slices** (pass 2 anchors, same for both rules): true-factor rows drift 0.02-0.47 s (Mulan transcribe 0.47, Seasons 0.40, Hakuna 0.36 / 0.35, Colors 0.34 / 0.02, Ten Minutes 0.17, Mulan asr 0.20); the off-factor rows, already free, drift 3.45-7.33 s. Spread gain of free over the factor on true-factor rows: -0.034 to +0.077 s (ratio 0.67-1.17); off-factor +0.68 to +1.51 s (ratio 0.12-0.28). All three forms separate the real rows; the simulation decides. Candidate, end to end: all 13 real stream rows identical to row 14 (status, matched, speed, shift, spread); wrong-song runs 0 fits of 49; unit tests 19 passed. **Review cases** (test helpers, 20 lines = 100 s, exact heard times, clip 120 s): speed 1.02 / 1.065 / 1.07 fit at 1.0 / 1.0427 / 1.0427 with max cue error 0.931 / 0.995 / 1.212 s today, and at 1.0200 / 1.0650 / 1.0700 with max error <= 0.001 s under the candidate. 1.0, 1.0427, 0.9590 keep the exact factor (error <= 0.001); 1.15 still refused. **Simulation** (`margin_sim.py`, seed 11): test helpers, heard line starts jittered per line by Gaussian sigma 0.1 / 0.25 / 0.4 s with 0 / 5 / 10% outliers uniform +-5 s, clips 8 / 12 / 20 / 40 / 80 lines (40-400 s); true speeds the 3 factors (60 runs each per cell), off speeds 0.97, 0.98, 0.99, 1.01, 1.02, 1.03, 1.055, 1.065, 1.07 (25 runs each per cell); only runs where the best factor passes kept (2693 true, 2367 off). Scored per run on pass 2 anchors: "switch" = free replaces the factor; error = max cue-start error against truth. Over clips >= 60 s, rate of true-factor runs switched / true-factor runs left > 0.5 s off / off-factor runs left > 0.5 s off: factor always 0 / 0.1% / 52% at 60 s, 94% at 100 s, 100% at 200 s; no margin 54.5% / 1.2% / 5.9%; spread gain > 0.1 s 1.5% / 0.5% / 14.6%; > 0.15 s 0.5% / 0.3% / 22.2%; drift > 0.5 s and lower spread 3.5% / 1.1% / 6.3%; **drift > 0.75 s and lower spread 0.8% / 0.6% / 8.6%**; drift > 1.0 s and lower spread leaves 21.1% of the off 100 s runs > 0.5 s off (8.1% at 0.75 s, 5.6% at 0.5 s). Ratio rules were worse than spread-gain rules at every switch rate (ratio < 0.67: 6.5% switched, 17.0% off left > 0.5 s, all lengths). Why drift beats spread gain: noise in the heard times shrinks the spread gain of a real drift, so a spread margin big enough to ignore noise (true-factor gain up to 0.29 s at 40-60 s clips, sigma 0.4) also ignores 1 s drifts on 100 s clips (p95 error 1.03-1.15 s at 0.15). Wrong switches are not free: a switched true-factor run went from median error 0.17 to 0.52 s, so the margin protects accuracy as well as the written speed. Drift > 0.75 s still switches some true-factor runs on short noisy clips: 19 of about 530 at 40 s, 12 at 60 s, 6 at 100 s, none at >= 200 s. On short noisy clips no rule tells 1.0 from 1.02; keeping the factor there is the safer call. **Test for the executor, checked:** 30 lines at speed 1.0, heard line starts jittered by `random.Random(4).gauss(0, 0.3)`, keeps speed exactly 1.0 under the candidate; without the margin it fits at 0.9980 (drift 0.28 s). **Not done here:** the Phase 3 cost note now covers the free speed running on every pick. Side finding: 14 "The Last Five Years (2014)" clips were added to the songs folder at 21:11 today, so the slice `the next ten minutes` now matches two videos and `movie_srt_fit_report.py` exits on it. The film clip has no heard words yet (no bundle, no caption), so it is not a data point. |
| 16 | 2026-10-28 | 2 | Review fixes for `5913461..9c03f50`, applied as commit `66713b9` (`srt_slice_fit.py`, `test_srt_slice_fit.py`), on the Movie Sub Review session's handoff. | **#1** `_best_speed` now computes `free_speed` on every call. Best factor bailed: as row 14. Best factor passed: the free speed replaces it only when its spread is lower and its drift, `abs(free - factor) * (max - min of the anchors' cue starts)`, is over `MIN_FREE_SPEED_DRIFT_S = 0.75` (row 15's rule). **#6** one scoring helper (`_fit_at`: scaled spans, `offset_mad_against_cues`) feeds the factors and the free speed; `_SpeedFit` (speed, stats, `rank`) replaces the tuple, and `best` is never None. **#4** `free_speed` pairs test `abs(t2 - t1)`, so cue starts out of file order are kept. **#7** the `SPEED_FACTORS` comment no longer says the free speed passes about as rarely; it states when the free speed is used and points at rows 14-15. **#5** tests 19 -> 24: (a) 20 lines, clip 120 s, true speeds 1.02 / 1.065 / 1.07 each fit at their own speed with max cue error under 0.002 s; (b) 30 lines at speed 1.0 with `random.Random(4).gauss(0, 0.3)` heard-start jitter keeps speed 1.0; (c) `free_speed` is None when no pair is over 20 s apart; (d) pass 2 re-pick: pass 1 stubbed to the first 5 cues picks 1.0427, pass 2 picks 1.07 with a different shift, and the result uses pass 2's; (e) `free_speed` on descending cue starts gives the slope. **Checks.** Each new test fails when its fix is undone (scratch `mutate_check.py`, mutating the source and restoring it): drift constant 0 fails (b); free only when the factor bailed fails (a) and (d); ordered pairs only fails (e); pass 2 keeping pass 1's pick fails (d). All 13 real stream rows, working tree against the HEAD `9c03f50` module (scratch `rows_vs_head.py`; status, reason, matched/total, speed, shift, spread): 13 of 13 identical, and equal to row 14's table (Be Our Guest 1.0667 / 1.0660, Belle 1.0711 / 1.0741, Hakuna 1.0, Mulan 0.9590, Colors 1.0, Seasons transcribe 0.9590 and asr refused/too_few, Ten Minutes 1.0). Full suite 2618 passed; pre-commit clean on the two files. **Not done, as sent:** #2 (free speed cost on large pastes, in the Phase 3 cost note), #3 (wrong-song simulation through pass 2, the gate's job after this commit), the two-video name match on `the next ten minutes` (`movie_srt_fit_report.py` still exits on it; the scratch check pinned that slice to the lyric video). |
| 17 | 2026-10-29 | 2 | GATE B, review item #3 (Opus): the wrong-song simulation run through pass 2, since pass 2 re-picks speed (free speed and margin included). HEAD `0faf557` (drift over the in-clip anchored cues; its own log row is not written), one commit past the `66713b9` the handoff named. Scratch scripts, not in the repo: `cross_all.py` (instrumented pass 1 + pass 2 from the module's own functions), `synth_cross.py`, `synth_cross_1216.py`, `synth_sum.py`. Raw output in "GATE B #3 output" below. No code changed. | Variants, all on the same pass 1 and the same pass-2 match: **HEAD** (pass 2 re-picks with `_best_speed`, free speed and margin); **NOREPICK** (pass 2 keeps pass 1's speed, offset refitted on pass 2's anchors); **NOFREE** (factors only, both passes, as at `5913461`). Harness check: HEAD status and speed equal `fit_slice` per stream on 600 sampled runs, 0 mismatches. **Real library cross:** every slice (8, Can You Feel the Love Tonight included as a slice) against every library song with heard words other than its own (24 songs: 15 with both streams, 9 with one; songs whose filename holds the slice's song excluded, both Next Ten Minutes videos for that slice), each stream: 275 runs. All three variants: 255 too_few, 20 disagree, 0 fits. Pass 1 reached 4 anchors in 25 runs (max 7); pass 2 max 7 anchors. Lowest pass-2 spread among them 1.07 s (5 anchors); the free speed was picked at pass 2 in 1 run (refused). **Synthetic cross:** slices built from one song's transcribe words (lines of 3-8 words, random window of k lines, at a random speed of 1.0 / 1.0427 / 0.9590 / 1.03 / 1.07, movie offset 3600 s), against every other song's streams; control = the same window against its own song's ASR stream. 173,640 wrong runs over k = 6, 10, 12, 16, 20, 40. Wrong fits, HEAD / NOREPICK / NOFREE: k=6 2 / 2 / 2 of 30,320; k=10 3 / 0 / 3 of 30,320; k=12 1 / 1 / 1 of 30,320; k=16 4 / 2 / 2 of 28,920; k=20 0 / 0 / 0 of 27,560; k=40 0 / 0 / 0 of 26,200. All 10 HEAD wrong fits have exactly 4 pass-2 anchors (share 4/6, 4/10, 4/12, 4/16). Of HEAD's extra fits over NOREPICK: the 3 at k=10 are a pass-2 re-pick to another factor (0.9590 over 1.0427); the 2 at k=16 are the free speed (0.9226, 0.934) taking over from a factor that bailed, at share 4/16, exactly the floor. The drift margin did not bear on any wrong fit (each free pick replaced a bailed factor). Wrong runs whose pass-2 spread passed and which reached the share test, HEAD / NOREPICK / NOFREE: k=40 98 / 62 / 75 (4-7 anchors, share at most 7/40 = 0.175, all refused too_few); k=20 4 / 4 / 4 (4 anchors, 0.20); below k=20 only the fits above. So the re-pick and the free speed let more wrong runs past the spread test, and at 20 or more in-clip cues the 0.25 floor refuses all of them. Controls (right song, other stream), HEAD fits: k=6 367/480, 10 391/480, 12 396/480, 16 410/480, 20 382/440, 40 397/400; NOFREE at k=40 361/400 (the 1.07 windows: 290 / 330 of 388 overall NOFREE / HEAD). Control fits with exactly 4 pass-2 anchors: k=6 45, 10 10, 12 4, 16 6, 20 0, 40 0. Real right fits (row 14): 26-113 anchors. **Report script:** `the next ten minutes` matches the lyric video and `The Last Five Years (2014) - The Next Ten Minutes.mp4`, so `resolve_song` exits. The film clip now has a bundle (`media_duration_s` 302.1) with 0 `transcribe_words` and no `.en.asr.json3`, so it has no heard words yet. The two videos are the same song, and the film clip is the slice's own source. |
| 18 | 2026-10-29 | 2 | Commit `0faf557` (`srt_slice_fit.py`, `test_srt_slice_fit.py`), written in the Opus session (trailer `Co-Authored-By: Claude Opus 5.5`). Its row was missing; this one is written afterwards from the diff and a run at the commit. | `_drift_s(anchors, spans, best, free, length)` counts only the anchors whose cue `_clip_span` places inside the clip at the best factor's speed and shift; before, it took the extent (`max - min`) of every anchor's cue start, so one anchor on a far cue stretched it. It returns 0.0 when no anchor is inside the clip. `_best_speed(anchors, spans, length)` takes the clip length, and `_fit_one_stream` passes `video_length` in both passes. The `SPEED_FACTORS` comment and the `_clip_span` docstring are reworded to match. Tests: a fixed 30-value `JITTER_S` list replaces `random.Random(4).gauss` in the noisy-keep test (`import random` dropped); new `TestBestSpeed`: `test_a_free_speed_with_less_spread_replaces_a_bailed_factor_however_little_it_drifts` (12 anchors; factor 1.0 bails `wide_spread`; asserts the picked speed does not bail and its drift from the factor is under 0.75 s) and `test_a_wrong_line_anchor_far_down_the_paste_does_not_stretch_the_drift` (20 anchors plus one on a cue at 700 s, 300 s clip; asserts speed 1.0). The recording wrapper in `TestPassTwoPick` takes `*args`. At `0faf557`: `test_srt_slice_fit.py` 26 passed (24 at `66713b9`); full suite 2620 passed. Real slices at `0faf557`: row 19. |
| 19 | 2026-10-29 | 2 | Commit `fe22ff6` (`scripts/movie_srt_fit_report.py`, `scripts/README.md`), the "Report script" note in row 17. `python scripts/movie_srt_fit_report.py --cross` over `~/pikaraoke-songs/movie_subs/` (8 slices), on the commit's code (`0faf557` + the script change). The output is not kept in the repo. | **Change.** `resolve_song` is now `resolve_songs`: returns every matching video, exits only on none. `load_song` takes one video. `main` builds `{slice: [Song, ...]}` and prints one block per video. `cross_report` flattens the videos, skips every video of the slice itself and any video with no `transcribe_words`, and the slice column joins that slice's video titles with ` + `. **Run.** Exit 0, stderr empty, 75 lines (one blank between the tables). Main table: 21 rows (row 14: 20): 18 fits, 2 no_reference, 1 refused/too_few (row 14: 18 / 1 / 1). The 20 rows of row 14 are in the output unchanged and in the same order. The one new row is `The Last Five Years (2014) - The Next Te`, heard `none`, clip 302 s (from `media_duration_s`; 0 `transcribe_words`, no `.en.asr.json3`), `no_reference`, matched 0/0, dropped 0, shift 0.00, speed 1.0000, 0 anchors, printed just before the lyric video's rows. Cross table: 49 rows (row 14: 49); 44 refused/too_few and 5 refused/disagree in both; every column but the first equal row by row. The first column of the 6 `The Next Ten Minutes` rows is now `The Last Five Years (2014) - The Next Te + The Next Ten Minutes Lyrics` (was the lyric video's title alone). The film clip is not an "Against" row: it has no `transcribe_words`. `pre-commit` clean on both files; full suite 2620 passed (the script has no tests). |
| 20 | 2026-10-29 | 2 | Review fixes for `66713b9..0faf557` (`/code-review`, 3 axis finders, 8 findings), applied as commit `99409f5` (`srt_slice_fit.py`, `test_srt_slice_fit.py`). | **#3** `_drift_s(anchors, a, b)` = `abs(a - b) * (max - min of the anchors' heard starts)`. Heard starts all lie in the clip, so the stray far anchor cannot stretch the extent; the `length` parameter of `_best_speed`, both call sites' `video_length`, and the `_clip_span` call in `_drift_s` are removed, and `_clip_span`'s docstring is back to counting and writing. This also closes **#4** (filter map vs pass-2 writer map), **#5** (zero-length cues excluded, silent 0.0) and **#8** (test ran the filter on a bailed factor). Heard extent and cue extent differ by the speed, at most 10%. **#6** `MIN_FREE_SPEED_DRIFT_S` comment: drift is over the heard stretch, with the reason it is not over the whole clip. **#7** the stray-anchor test asserts the free speed's rank beats the factor's and its drift is under the margin: free 0.99703, spread 0.185 vs 0.2 s, drift 0.282 s (0.75 s margin); the `66713b9` measure (all anchors' cue starts) gives 2.08 s on the same input, so the test fails under it. **Checks.** `python scripts/movie_srt_fit_report.py --cross`, working tree against `0faf557` (stash): 75 lines, byte-identical. Full suite 2620 passed; pre-commit clean on both files. **Not done, as decided:** #2 (drift over the anchored stretch under-reports a clustered set at the clip's far end): kept by design, since a free speed is only as precise as its anchor stretch and drift over the whole clip would let noise from a short cluster replace a right factor (row 15's failure). #1 (the stray anchor still feeds `free_speed` and both `_fit_at` stats): deferred. Theil-Sen moved 0.99909 -> 0.99703 on the test input; the bad case needs every in-clip anchor within 20 s, a stray slope within 10% of 1, and lower spread than the factor. The fix would drop anchors outside the clip before fitting. |
| 21 | 2026-10-29 | 3 | Two-kind custom sheet, commit `4eafb35` (`library_regen.py`, `library_status.py`, `library_tools.py`, and the tests of those three plus `test_processing_manager.py`). Phase 3 item 1 of the handoff of 2026-10-29. | **library_regen.** `CUSTOM_SHEET_SUFFIX` is now `CUSTOM_TEXT_SUFFIX` (`.custom.txt`), `CUSTOM_SRT_SUFFIX` (`.custom.srt`) and `CUSTOM_SHEET_SUFFIXES` (the pair). Origins `CUSTOM_ORIGIN` = `custom`, `MOVIE_ORIGIN` = `movie_srt`. `custom_sheet_file(song, suffix)` is the path of one kind; `custom_sheet_path(song)` is the one on disk, `.custom.txt` checked first, or None (it was always a Path before). `movie_sheet_plan(song, text=None)`: `Plan(kind="seed", lyrics_path=<.custom.srt>, seed={"lyrics_origin": "movie_srt"}, custom_text=text, label="movie subtitles")`. `custom_plan` returns the plan of the kind on disk. `is_custom_plan` is true for both origins; new `is_movie_plan` for the movie one. `apply_custom_choice`: a plan with `custom_text` writes `plan.lyrics_path`, then deletes the other kind; `replaces_custom` deletes both; any other job returns with both untouched. `snapshot_lyric_files` takes the `.lrc` and both sheet files. `KEEP_ON_RESET["lyrics"]` is `(".lrc", ".custom.txt", ".custom.srt")`. `prepare_lyrics` adds `_ytasr_seed` to a custom plan that is not a movie plan, so a movie plan's seed is `{"lyrics_origin": "movie_srt"}` alone. **library_status.** `custom_sheet` is `custom_sheet_path(song) is not None` (both call sites); `_lrclib_state` unchanged, `movie_srt` falls to `n/a`. **library_tools.** `_sheet_on_disk` reads the `.custom.txt` file only, so the Custom lyrics box never starts from SRT text; `repair`, `_now`, `custom_start`'s return shape and the routes are untouched (`repair(source="movie")` is Phase 3 item 3; `_now` and the song_info labels are Phase 4, so a movie song reads "custom lyrics" in the run lists until then). **Tests**, files 126 -> 147 (`test_library_regen`), 42 -> 45 (`test_library_status`), 274 -> 282 (`test_library_tools`), 111 -> 112 (`test_processing_manager`); full suite 2620 -> 2653 passed. New: movie sheet beats a reusable bundle with and without a bundle, reset or not; `custom_sheet_path` for typed, movie, neither, another song; reset keeps `.custom.srt`, whole-folder and scoped; saving a movie sheet deletes the typed one and the reverse; another song's sheet left alone; a repair to caption/genius/transcribe deletes either kind (now parametrized over both); a replayed movie sheet is left alone; `prepare_lyrics` for a movie plan (file is the sheet, origin `movie_srt`, a typed sheet text is written first, no third source even with a passing ASR caption on disk); a reset replays the movie sheet; `put_back_lyric_files` restores a movie sheet a typed one replaced; the same through the processing manager's failed-run path; status `custom_sheet` for `.custom.srt` with and without a bundle, `lrclib_state` `n/a` for `movie_srt` with a skip marker on disk; plain regenerate replays a movie sheet; the Custom box starts from the bundle's lines when the sheet is a movie one; the bulk run (`all`, `reset`, and an update of a song behind) sends a movie song to `reuse`, with no yt-dlp call and no pick, and queues the movie plan with `replaces_custom` false (new `TestRunsReplayMovieSheets`; `opened` and `group_of` moved to a shared `OpensRuns` base). Five existing `test_processing_manager` tests called `custom_sheet_path` for a path that does not exist yet and failed on None; they now call `custom_sheet_file(song, CUSTOM_TEXT_SUFFIX)`. **Checks.** Each of nine source changes undone in turn (scratch `mutate_sheets.py`, `mutate_prefill.py`, one inline) fails at least one test: reset keeps typed only; saving leaves the other kind; snapshot without the movie file (in `test_library_regen` and in `test_processing_manager`); movie plan given the third source; `custom_plan` ignoring the kind; `is_custom_plan` missing the movie origin; box prefill reading any sheet (only the movie-sheet test fails); status ignoring the sheet with no bundle. Pre-commit clean on the seven files (Black reformatted two on the first run). `graphify update .` run. Not done here: item 2 (cue-route words), item 3 (`repair(source="movie")`, `replaces_custom = source not in ("custom", "movie")`), item 4 (size cap). |
| 22 | 2026-10-29 | 3 | Cue route keeps its heard words, commit `8276dc8` (`lyric_align.py`, `alignment_capture.py` comment only, `test_lyric_align.py`). Phase 3 item 2 of the handoff. | `LyricAlignStage._run_cue_align` returns `(line_objects, transcribe_words, stats)` (was `(line_objects, stats)`); `run` assigns the words to `capture_transcribe_words`, which `_write_debug_capture` already wrote as the bundle's `transcribe_words`. The words are the ones `_dereverb_gate` returns, so after a de-reverb retry they are the dry stem's. Only the cue-route call site changed; the joint route and the LRCLIB fill (joint only) are untouched. No `SCHEMA_VERSION` change (11): the capture schema notes say older cue-route bundles hold None. Tests: `test_lyric_align.py` 48 -> 50, full suite 2653 -> 2655 passed. Added in `TestCueAlignRoute`: the gate's transcribe words equal the bundle's `transcribe_words` and `method_used` is `cue_align`; with the yield gate tripped (2 words over a 30 s stem against 30 wpm) and a dry-stem retry adopted, the bundle holds the retry's words, not the first pass's. **Checks.** Undoing the change (the cue route returning None for the words) fails both new tests; making the gate keep the wet words after a retry fails the second only (inline mutation script). Pre-commit clean on the three files; `graphify update .` run. Not run here: a real cue-route Regenerate, so no bundle on disk has words from this code yet (Phase 5 does Can You Feel the Love Tonight). |
| 23 | 2026-10-29 | 3 | `repair(source="movie", text=...)`, commit `1a6f1da` (`library_tools.py`, `test_library_tools.py`). Phase 3 item 3 of the handoff. | **New in `LibraryTools`.** `check_movie_slice(song_path, text) -> SliceFit`: `_sheet_text(text)` (text type, the existing `CUSTOM_SHEET_MAX_CHARS` = 100,000 character limit, `\n` line ends), the song's bundle, `media_duration(job)` (bundle value, else ffprobe), the on-disk `subtitles/<stem>.en.asr.json3` via the new `_asr_on_disk` (None for no file; a file that cannot be read or decoded logs `Could not read the auto-caption` and is ignored), then `fit_slice(text, heard_streams(bundle, asr), length)`. A refused answer is returned, not raised; `RegenError` for non-text, over the character limit, or no clip length (`Could not read this clip's length.`). `repair`: `source == "movie"` builds the plan with `_movie_repair_plan`, which raises `RegenError` unless `fit.status == "fits"` and otherwise returns `movie_sheet_plan(song, fit.srt)`, the corrected slice, never the pasted text; `replaces_custom = source not in ("custom", "movie")`. The refusal runs before `_queue`'s backup. **Admin wording**, from the ratified mockup's headline plus the hint behind its (i), in `_slice_refusal`: `not_srt` "Not an SRT file. SRT subtitles are numbered cues with times, like 00:01:02,500 --> 00:01:05,000."; `no_reference` "Can't check yet. This song has no heard words yet, so there is nothing to compare the subtitles with. Regenerate the song from Song info first, then try again."; `refused/disagree` "Doesn't fit. Found x of y lines, but they don't agree on one timing. The clip may be cut from several scenes, or these subtitles are for a different release."; `refused/too_few` "Doesn't fit. Only x of y lines were found in the clip. Check that these subtitles are from this movie and cover the part this clip shows."; and a case the mockup has no state for, a slice whose cues all clean away (`total` 0): "Doesn't fit. These subtitles have no lines to check." Row 4's wording clash (i) carries over: the no-heard-words message says "Regenerate the song from Song info". The Artifact had a newer version (`1793233316-fff2`) than the v20 the plan names when read here; only `project/Main.dc.html`'s `OUT` copy was read, and its strings are the ones above. **Reachability.** `routes/song_info.py` `repair` passes `body.get("source")` straight through, so `source="movie"` is reachable by an admin POST now; the only size limit on the text is the 100,000-character one (the message says "The lyrics are too long"), the cue-count cap is item 4. **Tests**: `test_library_tools.py` 282 -> 299, full suite 2655 -> 2672 passed. New `TestMovieRepair` on a synthetic 12-line slice (invented words, movie times an hour after the clip's): a fit queues the sheet plan (`movie_srt`, `.custom.srt`, label `movie subtitles`, label `Repair`, reset) with cue starts within 0.1 s of the heard line starts and not the pasted times; `replaces_custom` false and nothing written before the run; CRLF paste; the YouTube auto-caption alone carries a fit; a bundle with no `media_duration_s` takes the probed length; refusals (not SRT, cues that clean to nothing, wrong words, a clip cut from two scenes, `None`, a list, over the character limit) each raise with the message and leave the queue, the backups and an old typed sheet untouched; no heard words; no clip length; an unreadable auto-caption is ignored with a log line; `check_movie_slice` answers a refusal without raising and its `srt` is the text the repair queues. **Checks.** Five source changes undone in turn (inline script) each fail a test: the raw paste saved instead of `fit.srt` (3 tests); a refused fit queued (3); `replaces_custom` still true for movie (1); auto-caption ignored (2); no length check (1). Pre-commit clean on both files (Black reformatted the test file once); `graphify update .` run. Not done: the preview route (`POST /song_info/subtitle_fit`), `_now`, the song_info labels and the page (Phase 4). |
| 24 | 2026-10-29 | 3 | Phase 3 item 4, whole-film paste timing. HEAD `1a6f1da` (`srt_slice_fit.py` unchanged since `99409f5`). Scratch script `size_timing.py`, not in the repo; raw output in "Phase 3 whole-film timing output" below. **No cap chosen.** | **Machine:** AMD Ryzen 9 4900H, 16 CPUs, one Python process, the `pik` env; not a Raspberry Pi. **Input:** no film text. A synthetic film of N cues of 3-12 words drawn by frequency from the 1,451 distinct words heard across the library's bundles (top 20 words = 31% of all heard words), cue starts uniform over 7,200 s. Heard words are a real library song's: Lose Yourself (transcribe 792, no ASR), Belle (transcribe 592 + ASR 264), Seven (transcribe 472 + ASR 433). Scenarios: `wrong` (nothing of the clip in the film); `right` (the song's own transcribe words planted as 5-8-word cues at a movie offset of 3,000 s, film cues in that window removed, so the film has N cues in all); `repeat` (every cue the same six words); `common` (every cue 8 words from the top 20); `singles` (one cue per heard word, in order, plus film cues up to N: the most anchors a clip's words can give). N = 122, 500, 1000, 1500, 2000, 3000. Each cell: `fit_slice` 3 times (min and median), then once with `match_words_to_tokens` and `free_speed` wrapped to split the time. **Size of the paste:** synthetic cues average 72 characters (108,688 chars at 1,500 cues; 72,268 at 1,000; 35,881 at 500; 8,885 at 122), so the existing 100,000-character limit (`CUSTOM_SHEET_MAX_CHARS`) falls at about 1,380 such cues; Ken's real slices are 2,269-7,559 bytes (row 2) for 33-122 cues. **Seconds per `fit_slice` call (median, range over the three songs):** `wrong`: 122 cues 0.07-0.08; 500 0.28-0.30; 1,000 0.57-0.63; 1,500 0.86-0.96; 2,000 1.20-1.34; 3,000 1.71-1.92. `right`: 122 0.13-0.15; 500 0.53-0.60; 1,000 1.10-1.23; 1,500 1.65-1.89; 2,000 2.23-2.53; 3,000 3.29-3.79. `repeat`: 3,000 cues 1.23-1.41; `common`: 3,000 cues 1.73-1.99; `wrong`, `repeat` and `common` refused at pass 1 in every cell with 0 cues found and 0 anchors. `singles` (467-792 anchors): 122-500 cues 0.14-0.24 (the planted single-word cues alone are 467-792, so the film is that size whatever N); 1,000 0.45-0.79; 1,500 0.98-1.44; 2,000 1.55-2.12; 3,000 2.70-3.39. **Where the time goes:** `match_words_to_tokens` is, in cells of 1,000 or more cues, 91-93% of the wrapped run in `wrong` and `repeat`, 92-94% in `common`, 95-96% in `right` and 73-94% in `singles` (for example `right` at 3,000 cues, min of 3 runs / wrapped matcher seconds: 3.25 / 3.09, 3.45 / 3.29, 3.78 / 3.72); it runs once per stream when pass 1 finds under 4 anchors and twice per stream (passes 1 and 2) otherwise (calls column). `free_speed` ran only where a fit reached `_best_speed`: 2 calls (one stream) or 4 (two streams); 0.00 s at 75-123 anchors (`right`), 0.09 s for 2 calls at 792 anchors, 0.05 s for 4 calls at 585, 0.04 s for 4 at 467 (`singles`). The most anchors any cell gave was 792 (Lose Yourself `singles`, one anchor per heard word, 792 transcribe words); row 14's 0.36 s was one call at 1,500 anchors; the largest `free_speed` time in any cell was 0.09 s. Time outside the matcher and `free_speed` (parse, tokenise, rewrite): 0.10-0.18 s at 3,000 cues, 0.05-0.09 s at 1,500. **Per cue:** whole `fit_slice` call at 3,000 cues, `wrong` 0.57-0.64 ms per cue and `right` 1.10-1.26 ms per cue; the time grows in proportion to the cue count across 122-3,000 (`wrong`, Lose Yourself: 0.07 s at 122, 1.71 s at 3,000, 24.6 times the cues). A Repair costs the preview's fit plus the POST's (`check_movie_slice` runs in both). **Outcomes:** `right` fit in all 18 cells (matched = total = 123, 93 and 75 in-clip cues, whatever N); `singles` fit in all 18. |
| 25 | 2026-10-29 | 3 | Whole-film paste on real SRTs, Phase 3 item 4. HEAD `1a6f1da` for the first run, re-run at `c55cb77` (output below: same fits, times within 0.02 s). Ken added five whole-film SRTs to `~/pikaraoke-songs/movie_subs/`: `Beauty.And.The.Beast.1991.SE.iNTERNAL.DVDRip.XviD-SLeTDiVX.en.srt` (1,639 cues, 106,070 B, CRLF), `Disney - Pocahontas [DVD DivX].srt` (942, 74,285 B, CRLF), `Mulan.1998.720p.BRrip.x264.GAZ.YIFY.srt` (1,261, 85,634 B, UTF-8 BOM, CRLF), `Rent.REAL.DVDRip.XviD-LMG.srt` (1,782, 127,214 B, CRLF), `The Lion King I - [1994].srt` (1,677, 110,223 B, ISO-8859, CRLF). Scratch script `full_film.py`, not in the repo: decodes UTF-8-sig, else cp1252, normalises line ends, then `fit_slice` on the whole film and on the song's hand-trimmed slice, against the song's streams as `movie_srt_fit_report.load_song` reads them; one timed call per film run. | Every song with heard words: whole film `fits` with the slice's shift and speed (Belle -175.06 / 1.0711, Be Our Guest -2288.83 / 1.0667, Colors of the Wind -2363.11 / 1.0000, Hakuna Matata -2683.96 / 1.0000, Seasons of Love -66.53 vs -66.57 / 0.9590, Mulan -2139.28 vs -2139.46 / 0.9590). Mulan's whole film kept `src=asr` (44/51) where its slice kept transcribe (49/50). Kept cues equal the slice's first and last cue for Belle, Be Our Guest, Seasons of Love; one to three more edge cues for Pocahontas (+1), Mulan (+3), Hakuna Matata (+2), each inside the clip's span (dialogue the hand trim left out). 0.45-1.27 s per whole-film call on the Ryzen 9 4900H. Can You Feel the Love Tonight: no streams, `no_reference` both ways (Test songs table: needs a Regenerate). |
| 26 | 2026-10-29 | 3 | Size cap, commit `459e43c` (`srt_slice_fit.py`, `library_tools.py`, their tests). Decision 6. | `MAX_CUES = 3000`; `fit_slice` returns `SliceFit(TOO_LONG, total=<parsed cues>)` above it, after the `not_srt` checks and before the streams check. `_sheet_text` became `_pasted_text(text, kind, max_chars)`: typed lyrics `"lyrics"`, 100,000; movie subtitles `"subtitles"`, `MOVIE_SUBTITLES_MAX_CHARS = 1_000_000`. `_slice_refusal` wording for `too_long`: "These subtitles have more than 3,000 lines. Paste only the part of the movie with the song." New tests: `TestTooLong` (3,001 cues); repair refusals `too_long` (characters) and `too_many` (3,001 cues); a 600-filler-cue film over 100,000 characters around the 12-line slice fits and keeps the 12. Suite 2,675 passed at this commit. |
| 27 | 2026-10-29 | 3 | Review of `99409f5..1a6f1da` (3 finders: correctness, simplicity, robustness; 10 findings, dedup only, not verified), fixes in commit `c55cb77` (`library_regen.py`, `library_tools.py`, `srt_slice_fit.py`, their tests). Findings 1 (cap) went to row 26, 2's design to decision 7. | Fixed: 2 (wording: `regenerate_helps = job.bundle is not None`; with no bundle, "Can't check. This song has no heard words to compare the subtitles with, and a song whose lyrics were transcribed doesn't keep them yet."), 4 (`is_custom_plan` is `origin == custom` again, `is_movie_plan` deleted, tests read `plan.seed`), 6 + 8 (`check_movie_slice` checks `is_video`, then `_fit_movie_slice(job, text)`, which `_movie_repair_plan(job, text)` calls on the job `repair` already read), 7 (`apply_custom_choice` compares sheet file names; test with the song path spelled `lyrics/../`), 10 (`heard_streams` catches `ValueError`, `AttributeError`, `TypeError`; test with `[]`, a non-dict seg, a non-dict event). Not fixed: 3 (Phase 4 item), 5 (helper names; left), 9 (two sheets after a failed put-back plus a failed unlink; left). Checked while fixing: the bundle is written only when `capture_alignment_debug` is on (`lyric_align.py:290`, default True, `pipeline/config.py:291`). Suite 2,678 passed. |
| 28 | 2026-10-29 | 4 | Labels for the `movie_srt` origin (review finding 3 of `99409f5..1a6f1da`), commit `7f07006` (`library_status.py`, `library_tools.py`, `routes/library.py`, `routes/song_info.py`, their tests). | `SongStatus.movie_sheet` (new field): the sheet `custom_sheet_path` finds ends in `.custom.srt`; with both kinds on disk the typed one comes first, so it is false. Read from disk: `LibraryTools._now` returns `{"source": "movie"}`, `routes/library._now_text` says "Now: movie subtitles", `song_info._current_source` returns `"movie"`. Read from the bundle origin `movie_srt`: `_source_name` "Movie subtitles", `_route_text` "Lyrics from the movie's subtitles, timed against the subtitles' own line times.", `_versions` "Movie subtitles" with no LRCLIB label, `_pick` is `(origin, lines)` like custom. The Reset help now reads "except songs with custom lyrics or movie subtitles, which keep them" (its test string changed). Not changed: `song_info.html` (reads the worded `source` only), the translation catalogs (regenerated in their own commits). 9 mutations (one per changed branch), each caught by a named test. Suite 2,689 passed (2,678 at row 27). Pre-commit clean after Black reformatted `test_library_routes.py`. |
| 29 | 2026-10-29 | 4 | Check fit route, commit `4822725` (`library_tools.py`, `routes/song_info.py`, `tests/unit/movie_slices.py` new, the route, tools and status tests). | `POST /song_info/subtitle_fit {song, text}` answers a worded card `{status, tone, head, tip, lines: [{text, tip}], song_info_link}`, not the raw `SliceFit` fields the Design listed. Statuses answer 200: fits, refused (too_few, disagree, no lines), not_srt, too_long, no_reference. 403 for a guest; 400 for a song outside the library, a non-video, non-text, over 1,000,000 characters, or a clip length that can't be read (the `RegenError` text). Nothing is saved or queued. `check_movie_slice` returns `MovieSliceCheck(fit, regenerate_helps)`; `regenerate_helps` is `job.bundle is not None`, read once in `_fit_movie_slice`, for the preview and the Repair alike. Wording is the mockup's. A fit reads "unchanged" when the shift rounds to 0 s and the speed change rounds to 0.0%; otherwise "move h:mm:ss earlier" for a negative shift, "later" for zero or positive. The speed line shows when the change rounds to more than 0.0%, with the tip "The subtitles run at a different speed than the clip. That happens when they were made for a different frame rate, or when the clip was sped up or slowed down." `_slice_refusal`'s no-heard-words tail changed from "then try again" to "then come back and check", the mockup's line. A test joins each preview card's head, lines and tip and compares it with `_slice_refusal` for six refusals, with and without `regenerate_helps` (12 cases). Test helpers (`slice_line`, `heard_words`, `movie_slice`, `clip_starts`, `asr_json3`, three constants) moved from `test_library_tools.py` to `tests/unit/movie_slices.py`. Suite 2,731 passed (2,689 at row 28; 42 new tests). 15 mutations: 13 caught first run; the 2 that survived were a wrong `-k` selector and a change to wording no test asserts, both caught after retargeting. Black reformatted `song_info.py` and `test_library_routes.py`. Not done here: the page, `custom_start`'s movie text. |
| 30 | 2026-10-29 | 4 | The Movie subtitles page, commit `cc88169` (`song_repair.html`, `library_tools.py` `custom_start`, `routes/song_info.py` `repair_page`, route and tools tests). Driven in headless Chromium (scratch scripts, not in the repo) over the unit tests' `Env`, synthetic clip and cues, before the commit. | `custom_start` returns a new `movie` key, the saved `.custom.srt` text or empty; `_sheet_on_disk(song, suffix)` reads either kind, and its unreadable-file warning now names the suffix. `repair_page` passes it as `movie_prefill`. Page: source card between Custom and transcribe ("Time the song from the movie's own subtitles.", the `current` tag); section with the (i) note, box, Open file, Check fit, answer area. State: Regenerate is on only while `state.movieCard.status` is `fits` for the box's current text; any edit clears the card, bumps `movieSeq` (a late answer is dropped) and sets the "changed" hint if a card had been shown; the saved-slice hint shows while the box still equals the loaded text. A saved slice preselects the source on load. Open file: `readAsArrayBuffer`, strict UTF-8 `TextDecoder` (drops a BOM), else `windows-1252`; Ken's five film SRTs in row 25 include one BOM file and one ISO-8859 file. Browser walk, 47 checks, all passed: empty, pasted, checking, fits, edited, not SRT (with its (i) opened), too few, late answer dropped, Regenerate posts `movie` and the server queues the movie plan, a BOM file and a Windows-1252 file open with the accent kept, no-words with and without a bundle (link shown, link absent), a saved slice (preselected, in the box, the "saved slice" hint, fits at zero, Regenerate on after the check). Failed requests in the run: socket.io polling 404s (the test app has no socket server) and the offline YouTube thumbnail. Two things only the browser showed, fixed before the commit: the answer list took Bulma's `.content ul` bullets and 1em margins (the fits card measured 127 px, now 98 px), and the "!" and "i" icons drew as stray ticks without round line caps. Not checked: a real Regenerate run of a movie song, a touch screen, any language but English (the new strings are not in the catalogs yet, so they show in English). Suite 2,749 passed (2,731 at row 29; 18 new: 4 `custom_start`, 14 page). 17 mutations of the wiring: 16 caught first run or retargeted; one first-run survivor was a no-op change (an attribute, not an order change), replaced by two order mutations, both caught. Black reformatted `test_library_routes.py` several times. |
| 31 | 2026-10-29 | 4 | `/code-review` of `7f07006^..cc88169` (3 finders, one per Self-Review axis). | 10 findings. 1: the card's move line showed `shift_s` (the time map's value at movie time 0), wrong under a speed change. 2: `regenerate_helps = job.bundle is not None` also covers never-processed songs and unreadable bundles. 3: the 1,000,000-character cap does not bound the fit's cost (tokens x heard words, pure-Python DP on the request thread). 4: an edit during a check turned Check fit back on while the first check kept running, so checks could stack. 5: the file reader decoded UTF-16 SRTs as mojibake. 6: an unchanged fit's headline said "the saved slice" for any paste, and a sub-second move read as "Timing unchanged (0:00:00)". 7: refusal wording held twice (`_slice_refusal`, `_slice_card`). 8: `SongStatus.custom_sheet` / `movie_sheet` overlap. 9: `movieEdited` flag derivable; `infoTip()` copies the `info_tip` macro in JS. 10: Song Info names the source from the bundle, Repair and the run lists from the sheet on disk. Ken: fix 1, 4, 5, 6 and 3; 2 left as worded (a never-processed song has no Regenerate to offer; `regenerate_helps` unchanged), its mislabeled test fixed; 7 and 9 next; 8 and 10 to open issues. |
| 32 | 2026-10-29 | 4 | Review fixes, commits `733cc91` (findings 1, 6, 2's test), `19d3f41` (4, 5), `a0a67f1` (3). | `SliceFit.move_s = (speed - 1) * first_inside_cue_start + shift_s`; the card's move line reads it. Headline "Fits. The timing already matches the clip." when the move rounds to 0 s and the speed change to 0.0%, else "Fits. These subtitles can time this song."; the "Timing unchanged" line is gone (departs from mockup row 4b, Ken agreed). Page: an edit no longer clears `movieChecking`; done/fail always clear it and apply their answer only for the current `movieSeq`. File reader: BOM `FF FE` -> UTF-16 LE, `FE FF` -> UTF-16 BE, else strict UTF-8, then Windows-1252. `MOVIE_SUBTITLES_MAX_CHARS` 1,000,000 -> 300,000. Fit timings on this box (synthetic, `fit_slice` alone): 1,500 cues / 120k chars 2.1 s; 3,000 x 8 words 4.1 s; 3,000 x 16 (377k chars) 16.5 s; 1M chars (3,000 x 60) 236 s. Real whole-film SRTs are 70-120k chars (row 26 output). Not timed on a Pi. Driven in headless Chromium: Check fit stays off through a mid-check edit, the stale answer is dropped, one check on the server at a time; UTF-16 LE/BE and cp1252 files decode. Suite 2,751. |
| 33 | 2026-10-29 | 4 | Review findings 7, 9, then 8 and 10 recorded, commits `5fe6666`, `e0d0edf`, `fd48a46`. | 7: `_slice_refusal` deleted; `_movie_repair_plan` raises `MovieSliceRefused(check)` (a `RegenError` carrying the `MovieSliceCheck`); the repair route answers it with `_card_text(_slice_card(check))` (head, lines, tip). `MovieSliceCheck` kept (the card's input and the refusal's payload). The 12-case parity test is replaced by a route test posting the same text to `subtitle_fit` and `repair` (not_srt, disagree) with the refusal pinned. Lib tests assert the carried check's status/reason/counts and `regenerate_helps`. 9: `movieEdited` replaced by `movieAnswered`, the text the last shown answer was for; the note shows when the box differs from it. Behaviour change: a first check edited before it answers now reads "Not checked yet" (was "changed since the last check"). Card tips cloned from `<template id="movie-tip">` holding an empty `info_tip()`; `T.moreInfo` removed. Driven in Chromium: tip opens (`aria-expanded` true), not stacked on re-check, notes as described. 8, 10: `plans/open-issues.md` "Library tools: small, unruled". Suite 2,742 (the parity test's 12 cases gone). |
| 34 | 2026-10-29 | 5 | Glued dialogue dashes, commit `ab7e13d` (`srt_cues.py`, `test_srt_cues.py`). Ken saw `-What?`-style lines on the karaoke. | `_DIALOGUE_DASH_RE`: line-start and after-sentence-end dashes no longer need a following space; new third branch `\s+-+(?=[^\s-])` (a dash glued to the next word mid-line). Census over 85 SRTs (`subtitles/*.srt`, `lyrics/*.custom.srt`, `movie_subs/*.srt`): glued line-start dashes in Belle, Mulan, Seasons of Love, How It's Done and every whole-film SRT; word splits across cues (`letter-` line end with a glued `-lowercase` next): 0 (one `nine-to-` line end, next cue not dash-led). Old vs new `cue_spans_from_srt`: 71 files identical, 14 changed (Rent 381 lines, Mulan film 104, Belle 6, Mulan slice 8, How It's Done 6, Pocahontas 5, Seasons 1, Belle film 9), cue counts and spans identical in all; after the change no line keeps a start or space-led dash except `The Lion King - 23.976 fps`. Songs whose karaoke was built before need a Regenerate (sheets keep raw text). Suite 2,744. |
| 35 | 2026-10-29 | 5 | Ken's manual checks (Phase 5), app run from the main checkout on `movie_subtitles`. | Belle: Repair from `movie_subs/belle.srt` done; a one-song reset (`scripts/regen_alignment_bundles.py ~/pikaraoke-songs --reset --song "Belle" --yes`; dry run planned `movie subtitles`) kept the `.custom.srt` and the song still reads movie subtitles. Seasons of Love: fits (Ken: the audio is likely one continuous take). Hakuna Matata: Repair almost instant. Whole-film paste: "doesn't take much time at all". Can You Feel the Love Tonight: Check fit showed the regenerate-first prompt; after a Regenerate on its caption the slice checked. Ken saw glued dashes on the karaoke (row 34). Not recorded: cue align's fitted lead and fill/realign line counts per song. |

## Phase 2 calibration output (raw, 2026-10-28)

`python scripts/movie_srt_fit_report.py --cross`, HEAD `615146a`. Song names are cut at 40 characters by the script. Verdicts use the placeholder `MIN_MATCHED_SHARE = 0.5` and the shared spread limit 0.75 s. `Matched` is found cues over cues inside the clip (cues pasted, on a refusal); `Slope` is not used by the fit.

| Song | Heard | Words | Clip s | Status | Matched | Dropped | Shift s | Speed | Spread s | Anchors | Slope |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Beauty and the Beast (1991) - Be Our Gue | transcribe | 414 | 218 | refused/disagree | 77/92 | 0 | -2235.55 | 1.0427 | 1.007 | 77 | 1.0664 |
| Beauty and the Beast (1991) - Be Our Gue | asr | 296 | 218 | refused/disagree | 52/92 | 0 | -2235.54 | 1.0427 | 0.867 | 52 | 1.0647 |
| Beauty and the Beast (1991) - Be Our Gue | both->transcribe |  | 218 | refused/disagree | 77/92 | 0 | -2235.55 | 1.0427 | 1.007 | 77 |  |
| Beauty and the Beast (1991) - Belle [UHD | transcribe | 592 | 297 | refused/disagree | 113/122 | 0 | -167.19 | 1.0427 | 1.713 | 113 | 1.0714 |
| Beauty and the Beast (1991) - Belle [UHD | asr | 264 | 297 | refused/disagree | 49/122 | 0 | -166.00 | 1.0427 | 1.470 | 49 | 1.0726 |
| Beauty and the Beast (1991) - Belle [UHD | both->transcribe |  | 297 | refused/disagree | 113/122 | 0 | -167.19 | 1.0427 | 1.713 | 113 |  |
| The Lion King - Can You Feel The Love To | none |  | 175 | no_reference | 0/0 | 0 | 0.00 | 1.0000 |  | 0 |  |
| The Lion King - Hakuna Matata Music Vide | transcribe | 352 | 248 | fits | 75/94 | 0 | -2683.96 | 1.0000 | 0.155 | 75 | 1.0012 |
| The Lion King - Hakuna Matata Music Vide | asr | 339 | 248 | fits | 72/94 | 0 | -2683.85 | 1.0000 | 0.142 | 72 | 1.0016 |
| The Lion King - Hakuna Matata Music Vide | both->transcribe |  | 248 | fits | 75/94 | 0 | -2683.96 | 1.0000 | 0.155 | 75 |  |
| Mulan _ I'll Make a Man Out of You _ @di | transcribe | 312 | 241 | fits | 49/50 | 0 | -2139.46 | 0.9590 | 0.280 | 49 | 0.9611 |
| Mulan _ I'll Make a Man Out of You _ @di | asr | 281 | 241 | fits | 44/50 | 0 | -2139.28 | 0.9590 | 0.240 | 44 | 0.9599 |
| Mulan _ I'll Make a Man Out of You _ @di | both->transcribe |  | 241 | fits | 49/50 | 0 | -2139.46 | 0.9590 | 0.280 | 49 |  |
| Pocahontas - Colors of the Wind (Blu-ray | transcribe | 311 | 203 | fits | 40/40 | 0 | -2363.11 | 1.0000 | 0.253 | 40 | 0.9981 |
| Pocahontas - Colors of the Wind (Blu-ray | asr | 310 | 203 | fits | 40/40 | 0 | -2362.63 | 1.0000 | 0.081 | 40 | 1.0001 |
| Pocahontas - Colors of the Wind (Blu-ray | both->transcribe |  | 203 | fits | 40/40 | 0 | -2363.11 | 1.0000 | 0.253 | 40 |  |
| Seasons of Love (HD) | transcribe | 176 | 195 | fits | 26/33 | 0 | -66.57 | 0.9590 | 0.232 | 26 | 0.9558 |
| Seasons of Love (HD) | asr | 26 | 195 | refused/too_few | 0/33 | 0 | 0.00 | 1.0000 |  | 0 | 0.0937 |
| Seasons of Love (HD) | both->transcribe |  | 195 | fits | 26/33 | 0 | -66.57 | 0.9590 | 0.232 | 26 |  |
| The Next Ten Minutes Lyrics | transcribe | 359 | 454 | fits | 67/70 | 0 | -2629.54 | 1.0000 | 0.280 | 67 | 1.0004 |

| Slice (song) | Against | Status | Matched | Spread s | Anchors |
|---|---|---|---|---|---|
| Beauty and the Beast (1991) - Be Our Gue | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | Seasons of Love (HD) | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | The Next Ten Minutes Lyrics | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | Seasons of Love (HD) | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | The Next Ten Minutes Lyrics | refused/disagree | 5/122 | 18.666 | 5 |
| The Lion King - Can You Feel The Love To | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | Seasons of Love (HD) | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | The Next Ten Minutes Lyrics | refused/disagree | 4/48 | 49.870 | 4 |
| The Lion King - Hakuna Matata Music Vide | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/94 |  | 0 |
| The Lion King - Hakuna Matata Music Vide | Beauty and the Beast (1991) - Belle [UHD | refused/disagree | 6/94 | 9.700 | 6 |
| The Lion King - Hakuna Matata Music Vide | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/94 |  | 0 |
| The Lion King - Hakuna Matata Music Vide | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/94 |  | 0 |
| The Lion King - Hakuna Matata Music Vide | Seasons of Love (HD) | refused/too_few | 0/94 |  | 0 |
| The Lion King - Hakuna Matata Music Vide | The Next Ten Minutes Lyrics | refused/disagree | 4/94 | 26.874 | 4 |
| Mulan _ I'll Make a Man Out of You _ @di | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | Seasons of Love (HD) | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | The Next Ten Minutes Lyrics | refused/too_few | 0/50 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | Seasons of Love (HD) | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | The Next Ten Minutes Lyrics | refused/too_few | 0/40 |  | 0 |
| Seasons of Love (HD) | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | The Next Ten Minutes Lyrics | refused/too_few | 0/33 |  | 0 |
| The Next Ten Minutes Lyrics | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/70 |  | 0 |
| The Next Ten Minutes Lyrics | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/70 |  | 0 |
| The Next Ten Minutes Lyrics | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/70 |  | 0 |
| The Next Ten Minutes Lyrics | Mulan _ I'll Make a Man Out of You _ @di | refused/disagree | 4/70 | 7.110 | 4 |
| The Next Ten Minutes Lyrics | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/70 |  | 0 |
| The Next Ten Minutes Lyrics | Seasons of Love (HD) | refused/too_few | 0/70 |  | 0 |

## GATE B calibration output (raw, 2026-10-28)

`python scripts/movie_srt_fit_report.py --cross`, HEAD `9c03f50`. Same columns as the Phase 2 table. Verdicts use `MIN_MATCHED_SHARE = 0.25`, the shared spread limit 0.75 s, and the free-speed fallback.

| Song | Heard | Words | Clip s | Status | Matched | Dropped | Shift s | Speed | Spread s | Anchors | Slope |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Beauty and the Beast (1991) - Be Our Gue | transcribe | 414 | 218 | fits | 77/92 | 0 | -2288.83 | 1.0667 | 0.192 | 77 | 1.0664 |
| Beauty and the Beast (1991) - Be Our Gue | asr | 296 | 218 | fits | 52/92 | 0 | -2287.41 | 1.0660 | 0.271 | 52 | 1.0647 |
| Beauty and the Beast (1991) - Be Our Gue | both->transcribe |  | 218 | fits | 77/92 | 0 | -2288.83 | 1.0667 | 0.192 | 77 |  |
| Beauty and the Beast (1991) - Belle [UHD | transcribe | 592 | 297 | fits | 113/122 | 0 | -175.06 | 1.0711 | 0.205 | 113 | 1.0714 |
| Beauty and the Beast (1991) - Belle [UHD | asr | 264 | 297 | fits | 50/122 | 0 | -176.07 | 1.0741 | 0.252 | 50 | 1.0726 |
| Beauty and the Beast (1991) - Belle [UHD | both->transcribe |  | 297 | fits | 113/122 | 0 | -175.06 | 1.0711 | 0.205 | 113 |  |
| The Lion King - Can You Feel The Love To | none |  | 175 | no_reference | 0/0 | 0 | 0.00 | 1.0000 |  | 0 |  |
| The Lion King - Hakuna Matata Music Vide | transcribe | 352 | 248 | fits | 75/94 | 0 | -2683.96 | 1.0000 | 0.155 | 75 | 1.0012 |
| The Lion King - Hakuna Matata Music Vide | asr | 339 | 248 | fits | 72/94 | 0 | -2683.85 | 1.0000 | 0.142 | 72 | 1.0016 |
| The Lion King - Hakuna Matata Music Vide | both->transcribe |  | 248 | fits | 75/94 | 0 | -2683.96 | 1.0000 | 0.155 | 75 |  |
| Mulan _ I'll Make a Man Out of You _ @di | transcribe | 312 | 241 | fits | 49/50 | 0 | -2139.46 | 0.9590 | 0.280 | 49 | 0.9611 |
| Mulan _ I'll Make a Man Out of You _ @di | asr | 281 | 241 | fits | 44/50 | 0 | -2139.28 | 0.9590 | 0.240 | 44 | 0.9599 |
| Mulan _ I'll Make a Man Out of You _ @di | both->transcribe |  | 241 | fits | 49/50 | 0 | -2139.46 | 0.9590 | 0.280 | 49 |  |
| Pocahontas - Colors of the Wind (Blu-ray | transcribe | 311 | 203 | fits | 40/40 | 0 | -2363.11 | 1.0000 | 0.253 | 40 | 0.9981 |
| Pocahontas - Colors of the Wind (Blu-ray | asr | 310 | 203 | fits | 40/40 | 0 | -2362.63 | 1.0000 | 0.081 | 40 | 1.0001 |
| Pocahontas - Colors of the Wind (Blu-ray | both->transcribe |  | 203 | fits | 40/40 | 0 | -2363.11 | 1.0000 | 0.253 | 40 |  |
| Seasons of Love (HD) | transcribe | 176 | 195 | fits | 26/33 | 0 | -66.57 | 0.9590 | 0.232 | 26 | 0.9558 |
| Seasons of Love (HD) | asr | 26 | 195 | refused/too_few | 0/33 | 0 | 0.00 | 1.0000 |  | 0 | 0.0937 |
| Seasons of Love (HD) | both->transcribe |  | 195 | fits | 26/33 | 0 | -66.57 | 0.9590 | 0.232 | 26 |  |
| The Next Ten Minutes Lyrics | transcribe | 359 | 454 | fits | 67/70 | 0 | -2629.54 | 1.0000 | 0.280 | 67 | 1.0004 |

| Slice (song) | Against | Status | Matched | Spread s | Anchors |
|---|---|---|---|---|---|
| Beauty and the Beast (1991) - Be Our Gue | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | Seasons of Love (HD) | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Be Our Gue | The Next Ten Minutes Lyrics | refused/too_few | 0/92 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | Seasons of Love (HD) | refused/too_few | 0/122 |  | 0 |
| Beauty and the Beast (1991) - Belle [UHD | The Next Ten Minutes Lyrics | refused/disagree | 5/122 | 18.666 | 5 |
| The Lion King - Can You Feel The Love To | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | Seasons of Love (HD) | refused/too_few | 0/48 |  | 0 |
| The Lion King - Can You Feel The Love To | The Next Ten Minutes Lyrics | refused/disagree | 4/48 | 49.870 | 4 |
| The Lion King - Hakuna Matata Music Vide | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/94 |  | 0 |
| The Lion King - Hakuna Matata Music Vide | Beauty and the Beast (1991) - Belle [UHD | refused/disagree | 6/94 | 7.512 | 6 |
| The Lion King - Hakuna Matata Music Vide | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/94 |  | 0 |
| The Lion King - Hakuna Matata Music Vide | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/94 |  | 0 |
| The Lion King - Hakuna Matata Music Vide | Seasons of Love (HD) | refused/too_few | 0/94 |  | 0 |
| The Lion King - Hakuna Matata Music Vide | The Next Ten Minutes Lyrics | refused/disagree | 4/94 | 26.874 | 4 |
| Mulan _ I'll Make a Man Out of You _ @di | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | Seasons of Love (HD) | refused/too_few | 0/50 |  | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | The Next Ten Minutes Lyrics | refused/too_few | 0/50 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | Seasons of Love (HD) | refused/too_few | 0/40 |  | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | The Next Ten Minutes Lyrics | refused/too_few | 0/40 |  | 0 |
| Seasons of Love (HD) | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | Mulan _ I'll Make a Man Out of You _ @di | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/33 |  | 0 |
| Seasons of Love (HD) | The Next Ten Minutes Lyrics | refused/too_few | 0/33 |  | 0 |
| The Next Ten Minutes Lyrics | Beauty and the Beast (1991) - Be Our Gue | refused/too_few | 0/70 |  | 0 |
| The Next Ten Minutes Lyrics | Beauty and the Beast (1991) - Belle [UHD | refused/too_few | 0/70 |  | 0 |
| The Next Ten Minutes Lyrics | The Lion King - Hakuna Matata Music Vide | refused/too_few | 0/70 |  | 0 |
| The Next Ten Minutes Lyrics | Mulan _ I'll Make a Man Out of You _ @di | refused/disagree | 4/70 | 7.110 | 4 |
| The Next Ten Minutes Lyrics | Pocahontas - Colors of the Wind (Blu-ray | refused/too_few | 0/70 |  | 0 |
| The Next Ten Minutes Lyrics | Seasons of Love (HD) | refused/too_few | 0/70 |  | 0 |

## GATE B follow-up output (raw, 2026-10-28)

HEAD `9c03f50`, scratch scripts (row 15). Real slices, pass 2 anchors under the code at `9c03f50` (`margin_real.py`; drift from `margin_verify.py`, same anchors). "Factor" is the best of the three factors. Seasons of Love asr: pass 1 too few anchors.

| Slice | Heard | Anchors | Cue span s | Factor | Factor spread | Free | Free spread | Gain s | Ratio | Drift s |
|---|---|---|---|---|---|---|---|---|---|---|
| be our guest | transcribe | 77 | 195 | 1.0427 | 1.048 | 1.0667 | 0.192 | +0.856 | 0.18 | 4.68 |
| be our guest | asr | 52 | 148 | 1.0427 | 0.954 | 1.0660 | 0.271 | +0.683 | 0.28 | 3.45 |
| belle | transcribe | 113 | 258 | 1.0427 | 1.713 | 1.0711 | 0.205 | +1.508 | 0.12 | 7.33 |
| belle | asr | 50 | 194 | 1.0427 | 1.643 | 1.0741 | 0.252 | +1.391 | 0.15 | 6.07 |
| hakuna matata | transcribe | 75 | 236 | 1.0000 | 0.155 | 1.0015 | 0.182 | -0.027 | 1.17 | 0.36 |
| hakuna matata | asr | 72 | 212 | 1.0000 | 0.142 | 1.0016 | 0.151 | -0.009 | 1.06 | 0.35 |
| mulan | transcribe | 49 | 228 | 0.9590 | 0.280 | 0.9611 | 0.314 | -0.034 | 1.12 | 0.47 |
| mulan | asr | 44 | 228 | 0.9590 | 0.240 | 0.9599 | 0.249 | -0.009 | 1.04 | 0.20 |
| pocahontas | transcribe | 40 | 180 | 1.0000 | 0.253 | 0.9981 | 0.190 | +0.063 | 0.75 | 0.34 |
| pocahontas | asr | 40 | 180 | 1.0000 | 0.081 | 1.0001 | 0.080 | +0.001 | 0.99 | 0.02 |
| seasons of love | transcribe | 26 | 125 | 0.9590 | 0.232 | 0.9558 | 0.155 | +0.077 | 0.67 | 0.40 |
| the next ten minutes | transcribe | 67 | | 1.0000 | 0.280 | | | | | 0.17 |

(The Next Ten Minutes row is from `margin_verify.py` only; `margin_real.py` stopped on the two-video name match before it.)

Simulation (`margin_sim.py` / `margin_eval.py`), clips >= 60 s. D = spread gain threshold s, G = drift threshold s; the rule switches when gain > D and drift > G. Columns: true-factor runs switched, true-factor runs with max error > 0.5 s, off-factor runs with max error > 0.5 s. Factor always: 0%, 0.1%, (off by length) 52.2% at 60 s, 93.5% at 100 s, 100% at 200 s.

| D | G | True switched | True err > 0.5 s | Off err > 0.5 s |
|---|---|---|---|---|
| 0 | 0 | 54.5% | 1.2% | 5.9% |
| 0 | 0.3 | 9.1% | 1.2% | 6.1% |
| 0 | 0.5 | 3.5% | 1.1% | 6.3% |
| 0 | 0.75 | 0.8% | 0.6% | 8.6% |
| 0.03 | 0 | 11.0% | 1.0% | 7.6% |
| 0.03 | 0.5 | 2.6% | 0.9% | 7.9% |
| 0.03 | 0.75 | 0.6% | 0.5% | 10.0% |
| 0.05 | 0 | 5.5% | 0.9% | 8.9% |
| 0.05 | 0.5 | 2.2% | 0.8% | 9.2% |
| 0.05 | 0.75 | 0.6% | 0.5% | 11.1% |
| 0.075 | 0 | 3.0% | 0.7% | 11.4% |
| 0.1 | 0 | 1.5% | 0.5% | 14.6% |
| 0.1 | 0.75 | 0.3% | 0.3% | 15.1% |
| 0.15 | 0 | 0.5% | 0.3% | 22.2% |

All lengths (40-400 s), single-form rules: true switched / off p95 max error s / off err > 0.5 s / off err > 0.75 s.

| Rule | True switched | Off p95 | Off > 0.5 s | Off > 0.75 s |
|---|---|---|---|---|
| factor always | 0.0% | 1.27 | 64.0% | 33.9% |
| no margin (lower spread) | 54.5% | 0.61 | 8.6% | 1.8% |
| gain > 0.05 | 7.4% | 0.65 | 11.4% | 2.6% |
| gain > 0.1 | 2.3% | 0.70 | 16.3% | 3.8% |
| gain > 0.15 | 0.8% | 0.77 | 22.3% | 5.3% |
| gain > 0.2 | 0.2% | 0.85 | 28.9% | 7.1% |
| ratio < 0.8 | 13.4% | 0.66 | 11.8% | 2.9% |
| ratio < 0.67 | 6.5% | 0.74 | 17.0% | 4.8% |
| ratio < 0.5 | 2.2% | 1.01 | 26.0% | 9.2% |
| speed distance > 0.5% | 17.0% | 0.51 | 5.4% | 1.7% |
| speed distance > 1.0% | 7.4% | 0.75 | 12.7% | 5.0% |
| drift > 0.5 & lower spread | 4.2% | 0.61 | 9.2% | 1.7% |
| drift > 0.75 & lower spread | 1.4% | 0.65 | 11.6% | 2.3% |

True-factor noise only, max spread gain / max drift by clip and noise sigma (outliers 0 / 5 / 10% with sigma 0.1 / 0.25 / 0.4): 40 s 0.103 / 0.235 / 0.222 gain, 0.40 / 2.84 / 3.46 drift; 60 s 0.046 / 0.198 / 0.285, 0.37 / 0.75 / 2.55; 100 s 0.050 / 0.129 / 0.170, 0.27 / 0.70 / 1.55; 200 s 0.018 / 0.055 / 0.098, 0.15 / 0.52 / 0.64; 400 s 0.013 / 0.029 / 0.051, 0.11 / 0.26 / 0.57.

Off-factor p95 max error s, by speed and clip, all noise levels: factor | no margin | gain > 0.1 | gain > 0.15 | gain > 0.2.

| Speed | 40 s | 60 s | 100 s | 200 s |
|---|---|---|---|---|
| 0.970 | 0.74 / 0.72 / 0.72 / 0.74 / 0.74 | 1.02 / 0.47 / 0.73 / 0.73 / 0.98 | 0.80 / 0.59 / 0.74 / 0.74 / 0.79 | 1.29 / 0.25 / 0.25 / 0.25 / 0.34 |
| 0.980 | 0.70 / 0.68 / 0.73 / 0.70 / 0.70 | 0.88 / 0.70 / 0.88 / 0.88 / 0.88 | 1.27 / 0.62 / 1.09 / 1.12 / 1.17 | |
| 0.990 | 0.73 / 0.66 / 0.73 / 0.73 / 0.73 | 1.08 / 0.47 / 0.68 / 0.71 / 0.71 | 0.69 / 0.56 / 0.60 / 0.69 / 0.69 | 1.21 / 0.39 / 0.39 / 0.99 / 1.05 |
| 1.010 | 0.72 / 0.62 / 0.68 / 0.69 / 0.69 | 0.90 / 0.53 / 0.65 / 0.71 / 0.71 | 0.70 / 0.54 / 0.69 / 0.69 / 0.69 | 1.16 / 0.32 / 0.32 / 0.36 / 1.03 |
| 1.020 | 0.69 / 0.65 / 0.69 / 0.69 / 0.69 | 0.85 / 0.66 / 0.85 / 0.85 / 0.85 | 1.31 / 0.41 / 0.44 / 1.03 / 1.13 | |
| 1.030 | 0.70 / 0.74 / 0.70 / 0.70 / 0.70 | 0.86 / 0.77 / 0.86 / 0.86 / 0.86 | 0.83 / 0.66 / 0.78 / 0.78 / 0.80 | 1.46 / 0.26 / 0.26 / 0.28 / 0.34 |
| 1.055 | 0.92 / 1.00 / 1.00 / 1.00 / 1.00 | 0.55 / 0.63 / 0.55 / 0.55 / 0.55 | 0.71 / 0.35 / 0.68 / 0.71 / 0.71 | 1.37 / 0.28 / 0.28 / 0.28 / 1.25 |
| 1.065 | 0.73 / 0.69 / 0.70 / 0.70 / 0.70 | 0.85 / 0.61 / 0.79 / 0.79 / 0.79 | 1.29 / 0.50 / 1.11 / 1.15 / 1.17 | |
| 1.070 | 0.79 / 0.60 / 0.63 / 0.63 / 0.69 | 1.07 / 0.83 / 0.93 / 0.95 / 0.95 | 1.52 / 0.44 / 0.44 / 0.49 / 0.79 | |

(Blank: every factor bailed in all runs, so the row 14 rule applies.)

Off-factor share left > 0.5 s off under drift > G and lower spread, by clip: G = 0.5: 40 s 16.4%, 60 s 10.4%, 100 s 5.6%, 200 s 0.3%; G = 0.75: 19.2%, 13.6%, 8.1%, 0.3%; G = 1.0: 24.6%, 21.8%, 21.1%, 0.3%. No margin: 15.3%, 9.5%, 5.4%, 0.3%. True-factor runs switched (of 2693): G = 0.5 112 (40 s 37, 60 s 42, 100 s 25, 200 s 6, 400 s 2), median error 0.12 -> 0.42 s, worst added 1.01 s; G = 0.75 37 (19 / 12 / 6 / 0 / 0), 0.17 -> 0.52 s; G = 1.0 15 (9 / 3 / 3 / 0 / 0), 0.18 -> 0.70 s.

Review cases (test helpers, 20 lines, exact heard times, clip 120 s, shift -1800), max cue error s: at `9c03f50` / candidate (G = 0.75).

| True speed | Fitted at 9c03f50 | Error | Fitted, candidate | Error |
|---|---|---|---|---|
| 1.0 | 1.0000 | 0.0 | 1.0000 | 0.0 |
| 1.0427 | 1.0427 | 0.001 | 1.0427 | 0.001 |
| 0.9590 | 0.9590 | 0.0 | 0.9590 | 0.0 |
| 1.02 | 1.0000 | 0.931 | 1.0200 | 0.001 |
| 1.065 | 1.0427 | 0.995 | 1.0650 | 0.0 |
| 1.07 | 1.0427 | 1.212 | 1.0700 | 0.001 |
| 1.15 | refused | | refused | |

Jittered true-factor test seeds (30 lines, speed 1.0, `random.Random(seed).gauss(0, 0.3)` per line), candidate / no margin: seed 0 1.0000 / 1.0000 (drift 0.06); 1 1.0000 / 1.0013 (0.19); 2 1.0000 / 1.0001 (0.02); 3 1.0000 / 1.0000 (0.33); 4 1.0000 / 0.9980 (0.28); 5 1.0000 / 1.0000 (0.28).

## GATE B #3 output (raw, 2026-10-29)

HEAD `0faf557`, scratch scripts (row 17). Real library cross (`cross_all.py`, `cross_sum.py`): runs that reached pass 2 (pass 1 had 4 or more anchors); the other 250 were too_few at pass 1. Columns per variant: status matched/total, speed and spread where a speed was picked. "Slice" is the pasted slice; the song it was run against is left out.

    HEAD {'too_few': 255, 'disagree': 20}
    NOREPICK {'too_few': 255, 'disagree': 20}
    NOFREE {'too_few': 255, 'disagree': 20}
    pass-1 anchors >= 4: 25 max a1 7
    pass-2 free speed picked (HEAD): 1
    HEAD pass-2 anchors max: 7
    

| Slice | Stream | Cues | P1 anchors | P1 speed | P1 bailed | P2 anchors | HEAD | NOREPICK | NOFREE |
|---|---|---|---|---|---|---|---|---|---|
| belle | asr | 122 | 6 | 0.9690 | wide_spread | 6 | disagree 6/122 @0.9690 mad 4.08 | disagree 6/122 @0.9690 mad 4.08 | disagree 6/122 @0.9590 mad 4.08 |
| belle | asr | 122 | 5 | 0.9590 | wide_spread | 4 | disagree 4/122 @0.9590 mad 4.80 | disagree 4/122 @0.9590 mad 4.80 | disagree 4/122 @0.9590 mad 4.80 |
| belle | asr | 122 | 4 | 0.9590 | wide_spread | 4 | disagree 4/122 @0.9590 mad 4.15 | disagree 4/122 @0.9590 mad 4.15 | disagree 4/122 @0.9590 mad 4.15 |
| belle | transcribe | 122 | 6 | 0.9590 | wide_spread | 6 | disagree 6/122 @0.9590 mad 15.30 | disagree 6/122 @0.9590 mad 15.30 | disagree 6/122 @0.9590 mad 15.30 |
| belle | transcribe | 122 | 5 | 0.9590 | wide_spread | 5 | disagree 5/122 @0.9590 mad 14.54 | disagree 5/122 @0.9590 mad 14.54 | disagree 5/122 @0.9590 mad 14.54 |
| belle | transcribe | 122 | 4 | 0.9590 | wide_spread | 4 | disagree 4/122 @1.0427 mad 14.52 | disagree 4/122 @0.9590 mad 16.87 | disagree 4/122 @1.0427 mad 14.52 |
| belle | transcribe | 122 | 6 | 0.9590 | wide_spread | 5 | disagree 5/122 @0.9590 mad 18.67 | disagree 5/122 @0.9590 mad 18.67 | disagree 5/122 @0.9590 mad 18.67 |
| belle | transcribe | 122 | 5 | 0.9590 | wide_spread | 3 | too_few 0/122 | too_few 0/122 | too_few 0/122 |
| can you feel the love tonight | asr | 48 | 4 | 1.0427 | wide_spread | 4 | disagree 4/48 @1.0427 mad 4.79 | disagree 4/48 @1.0427 mad 4.79 | disagree 4/48 @1.0427 mad 4.79 |
| can you feel the love tonight | asr | 48 | 4 | 1.0427 | wide_spread | 3 | too_few 0/48 | too_few 0/48 | too_few 0/48 |
| can you feel the love tonight | transcribe | 48 | 4 | 1.0427 | wide_spread | 4 | disagree 4/48 @1.0427 mad 4.79 | disagree 4/48 @1.0427 mad 4.79 | disagree 4/48 @1.0427 mad 4.79 |
| can you feel the love tonight | transcribe | 48 | 5 | 1.0427 | wide_spread | 5 | disagree 5/48 @1.0427 mad 1.07 | disagree 5/48 @1.0427 mad 1.07 | disagree 5/48 @1.0427 mad 1.07 |
| can you feel the love tonight | transcribe | 48 | 4 | 1.0427 | wide_spread | 3 | too_few 0/48 | too_few 0/48 | too_few 0/48 |
| can you feel the love tonight | transcribe | 48 | 7 | 1.0427 | wide_spread | 5 | disagree 5/48 @0.9590 mad 9.98 | disagree 5/48 @1.0427 mad 14.03 | disagree 5/48 @0.9590 mad 9.98 |
| can you feel the love tonight | transcribe | 48 | 4 | 1.0427 | wide_spread | 4 | disagree 4/48 @1.0427 mad 49.87 | disagree 4/48 @1.0427 mad 49.87 | disagree 4/48 @1.0427 mad 49.87 |
| hakuna matata | asr | 94 | 4 | 1.0000 | wide_spread | 4 | disagree 4/94 @1.0000 mad 2.82 | disagree 4/94 @1.0000 mad 2.82 | disagree 4/94 @1.0000 mad 2.82 |
| hakuna matata | asr | 94 | 4 | 1.0427 | wide_spread | 4 | disagree 4/94 @1.0427 mad 6.31 | disagree 4/94 @1.0427 mad 6.31 | disagree 4/94 @1.0427 mad 6.31 |
| hakuna matata | transcribe | 94 | 5 | 1.0427 | wide_spread | 4 | disagree 4/94 @1.0427 mad 4.80 | disagree 4/94 @1.0427 mad 4.80 | disagree 4/94 @1.0427 mad 4.80 |
| hakuna matata | transcribe | 94 | 7 | 0.9590 | wide_spread | 6 | disagree 6/94 @1.0427 mad 7.51 | disagree 6/94 @0.9590 mad 9.70 | disagree 6/94 @1.0427 mad 7.51 |
| hakuna matata | transcribe | 94 | 4 | 0.9590 | wide_spread | 3 | too_few 0/94 | too_few 0/94 | too_few 0/94 |
| hakuna matata | transcribe | 94 | 4 | 1.0427 | wide_spread | 4 | disagree 4/94 @1.0427 mad 26.87 | disagree 4/94 @1.0427 mad 26.87 | disagree 4/94 @1.0427 mad 26.87 |
| the next ten minutes | asr | 70 | 4 | 0.9590 | wide_spread | 7 | disagree 7/70 @0.9590 mad 11.43 | disagree 7/70 @0.9590 mad 11.43 | disagree 7/70 @0.9590 mad 11.43 |
| the next ten minutes | transcribe | 70 | 6 | 0.9590 | wide_spread | 5 | disagree 5/70 @0.9590 mad 21.41 | disagree 5/70 @0.9590 mad 21.41 | disagree 5/70 @0.9590 mad 21.41 |
| the next ten minutes | transcribe | 70 | 4 | 1.0427 | wide_spread | 3 | too_few 0/70 | too_few 0/70 | too_few 0/70 |
| the next ten minutes | transcribe | 70 | 4 | 1.0427 | wide_spread | 4 | disagree 4/70 @1.0427 mad 7.11 | disagree 4/70 @1.0427 mad 7.11 | disagree 4/70 @1.0427 mad 7.11 |

Synthetic cross (`synth_cross.py` seed 23 for k = 6, 10, 20, 40; `synth_cross_1216.py` seed 29 for k = 12, 16; 40 windows per song per k; `synth_sum.py`). Per-run tuple in the fit list: k, stream, pass-1 anchors, pass-2 anchors, pass-1 pick (speed, bail, spread), then per variant (status, matched, total, speed, spread).

```
control: | k | runs | P1 >= 4 anchors | HEAD fits | NOREPICK fits | NOFREE fits | HEAD disagree | HEAD P2 free picked |
| 6 | 480 | 405 | 367 | 366 | 367 | 35 | 8 |
| 10 | 480 | 425 | 391 | 391 | 389 | 32 | 40 |
| 20 | 440 | 401 | 382 | 381 | 380 | 17 | 90 |
| 40 | 400 | 400 | 397 | 397 | 361 | 3 | 157 |
wrong: | k | runs | P1 >= 4 anchors | HEAD fits | NOREPICK fits | NOFREE fits | HEAD disagree | HEAD P2 free picked |
| 6 | 30320 | 278 | 2 | 2 | 2 | 232 | 0 |
| 10 | 30320 | 786 | 3 | 0 | 3 | 624 | 0 |
| 20 | 27560 | 1524 | 0 | 0 | 0 | 1141 | 6 |
| 40 | 26200 | 2176 | 0 | 0 | 0 | 1699 | 88 |
wrong-song fits, any variant:
6 transcribe 4 4 (0.95904, 'wide_spread', 1.03) {'HEAD': ('fits', 4, 6, 0.959, 0.38), 'NOREPICK': ('fits', 4, 6, 0.959, 0.38), 'NOFREE': ('fits', 4, 6, 0.959, 0.38)}
6 asr 4 4 (0.95904, 'wide_spread', 1.11) {'HEAD': ('fits', 4, 6, 1.0, 0.493), 'NOREPICK': ('fits', 4, 6, 0.959, 0.63), 'NOFREE': ('fits', 4, 6, 1.0, 0.493)}
10 transcribe 4 4 (1.0427093760427095, 'wide_spread', 9.798) {'HEAD': ('fits', 4, 10, 0.959, 0.645), 'NOREPICK': ('disagree', 4, 10, 1.0427, 1.276), 'NOFREE': ('fits', 4, 10, 0.959, 0.645)}
10 transcribe 4 4 (1.0427093760427095, 'wide_spread', 10.171) {'HEAD': ('fits', 4, 10, 0.959, 0.375), 'NOREPICK': ('disagree', 4, 10, 1.0427, 0.982), 'NOFREE': ('fits', 4, 10, 0.959, 0.375)}
10 transcribe 4 4 (1.0427093760427095, 'wide_spread', 9.798) {'HEAD': ('fits', 4, 10, 0.959, 0.645), 'NOREPICK': ('disagree', 4, 10, 1.0427, 1.276), 'NOFREE': ('fits', 4, 10, 0.959, 0.645)}
wrong-song runs with pass-2 spread <= 0.75 (any status), HEAD:
{(40, 'too_few'): 98, (6, 'fits'): 2, (20, 'too_few'): 4, (10, 'fits'): 3}
variants differ (status): 52 | HEAD vs NOREPICK speed differs: 266
```

```
control: | k | runs | P1 >= 4 anchors | HEAD fits | NOREPICK fits | NOFREE fits | HEAD disagree | HEAD P2 free picked |
| 12 | 480 | 433 | 396 | 392 | 394 | 35 | 58 |
| 16 | 480 | 442 | 410 | 410 | 401 | 32 | 69 |
wrong: | k | runs | P1 >= 4 anchors | HEAD fits | NOREPICK fits | NOFREE fits | HEAD disagree | HEAD P2 free picked |
| 12 | 30320 | 908 | 1 | 1 | 1 | 741 | 4 |
| 16 | 28920 | 1161 | 4 | 2 | 2 | 925 | 2 |
wrong-song fits, any variant:
16 transcribe 4 4 (1.0427093760427095, 'wide_spread', 7.065) {'HEAD': ('fits', 4, 16, 1.0427, 0.115), 'NOREPICK': ('fits', 4, 16, 1.0427, 0.115), 'NOFREE': ('fits', 4, 16, 1.0427, 0.115)}
16 transcribe 4 4 (1.0427093760427095, 'wide_spread', 7.74) {'HEAD': ('fits', 4, 16, 1.0427, 0.44), 'NOREPICK': ('fits', 4, 16, 1.0427, 0.44), 'NOFREE': ('fits', 4, 16, 1.0427, 0.44)}
12 transcribe 5 4 (1.0427093760427095, 'wide_spread', 1.139) {'HEAD': ('fits', 4, 12, 1.0427, 0.683), 'NOREPICK': ('fits', 4, 12, 1.0427, 0.683), 'NOFREE': ('fits', 4, 12, 1.0427, 0.683)}
16 asr 5 4 (0.95904, 'wide_spread', 1.945) {'HEAD': ('fits', 4, 16, 0.9226, 0.511), 'NOREPICK': ('disagree', 4, 16, 0.959, 0.972), 'NOFREE': ('disagree', 4, 16, 0.959, 0.972)}
16 asr 5 4 (0.95904, 'wide_spread', 1.83) {'HEAD': ('fits', 4, 16, 0.934, 0.511), 'NOREPICK': ('disagree', 4, 16, 0.959, 0.824), 'NOFREE': ('disagree', 4, 16, 0.959, 0.824)}
wrong-song runs with pass-2 spread <= 0.75 (any status), HEAD:
{(16, 'fits'): 4, (12, 'fits'): 1}
variants differ (status): 4 | HEAD vs NOREPICK speed differs: 91
```


## Phase 3 whole-film timing output (raw, 2026-10-29)

HEAD `1a6f1da`, scratch `size_timing.py` (row 24), AMD Ryzen 9 4900H. Columns: song, streams with heard-word counts, scenario, cues (nominal N), characters of the pasted text, status/reason, matched/total, anchors, min and median seconds of 3 runs, then one wrapped run: seconds in `match_words_to_tokens` (calls), in `free_speed` (calls, most anchors in a call), and the rest. Exit 0, stderr empty, both runs. `singles` rows at 122 and 500 cues: the planted single-word cues alone are 467-792, so the film is that size (see the chars column).

    vocabulary: 1451 distinct heard words; top-20 cover 31% of all heard words
    
    song | streams (heard words) | scenario | cues | chars | status/reason | matched/total | anchors | min s | median s | match s | free_speed s (calls, anchors) | other s
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | wrong | 122 | 8885 | refused/too_few | 0/122 | 0 | 0.07 | 0.07 | 0.07 (1) | 0.00 (0, max 0) | 0.01
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | wrong | 500 | 35881 | refused/too_few | 0/500 | 0 | 0.27 | 0.28 | 0.27 (1) | 0.00 (0, max 0) | 0.02
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | wrong | 1000 | 72268 | refused/too_few | 0/1000 | 0 | 0.56 | 0.57 | 0.52 (1) | 0.00 (0, max 0) | 0.05
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | wrong | 1500 | 108688 | refused/too_few | 0/1500 | 0 | 0.86 | 0.86 | 0.78 (1) | 0.00 (0, max 0) | 0.07
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | wrong | 2000 | 146010 | refused/too_few | 0/2000 | 0 | 1.19 | 1.20 | 1.08 (1) | 0.00 (0, max 0) | 0.10
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | wrong | 3000 | 216692 | refused/too_few | 0/3000 | 0 | 1.71 | 1.71 | 1.54 (1) | 0.00 (0, max 0) | 0.14
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | right | 122 | 8180 | fits | 123/123 | 123 | 0.13 | 0.13 | 0.13 (2) | 0.00 (2, max 123) | 0.01
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | right | 500 | 35264 | fits | 123/123 | 123 | 0.53 | 0.53 | 0.50 (2) | 0.00 (2, max 123) | 0.03
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | right | 1000 | 71530 | fits | 123/123 | 123 | 1.09 | 1.10 | 1.04 (2) | 0.00 (2, max 123) | 0.05
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | right | 1500 | 107851 | fits | 123/123 | 123 | 1.65 | 1.65 | 1.57 (2) | 0.00 (2, max 123) | 0.08
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | right | 2000 | 145374 | fits | 123/123 | 123 | 2.21 | 2.23 | 2.10 (2) | 0.00 (2, max 123) | 0.10
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | right | 3000 | 215623 | fits | 123/123 | 123 | 3.25 | 3.29 | 3.09 (2) | 0.00 (2, max 123) | 0.15
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | repeat | 122 | 6358 | refused/too_few | 0/122 | 0 | 0.05 | 0.05 | 0.05 (1) | 0.00 (0, max 0) | 0.00
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | repeat | 500 | 26392 | refused/too_few | 0/500 | 0 | 0.20 | 0.20 | 0.19 (1) | 0.00 (0, max 0) | 0.02
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | repeat | 1000 | 52893 | refused/too_few | 0/1000 | 0 | 0.40 | 0.41 | 0.37 (1) | 0.00 (0, max 0) | 0.03
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | repeat | 1500 | 79893 | refused/too_few | 0/1500 | 0 | 0.61 | 0.61 | 0.56 (1) | 0.00 (0, max 0) | 0.05
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | repeat | 2000 | 106893 | refused/too_few | 0/2000 | 0 | 0.81 | 0.81 | 0.74 (1) | 0.00 (0, max 0) | 0.07
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | repeat | 3000 | 160893 | refused/too_few | 0/3000 | 0 | 1.21 | 1.23 | 1.11 (1) | 0.00 (0, max 0) | 0.10
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | common | 122 | 7432 | refused/too_few | 0/122 | 0 | 0.07 | 0.07 | 0.06 (1) | 0.00 (0, max 0) | 0.01
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | common | 500 | 30899 | refused/too_few | 0/500 | 0 | 0.28 | 0.28 | 0.26 (1) | 0.00 (0, max 0) | 0.02
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | common | 1000 | 62004 | refused/too_few | 0/1000 | 0 | 0.58 | 0.58 | 0.54 (1) | 0.00 (0, max 0) | 0.04
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | common | 1500 | 93772 | refused/too_few | 0/1500 | 0 | 0.85 | 0.85 | 0.79 (1) | 0.00 (0, max 0) | 0.06
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | common | 2000 | 125438 | refused/too_few | 0/2000 | 0 | 1.13 | 1.14 | 1.06 (1) | 0.00 (0, max 0) | 0.08
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | common | 3000 | 188359 | refused/too_few | 0/3000 | 0 | 1.71 | 1.73 | 1.60 (1) | 0.00 (0, max 0) | 0.13
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | wrong | 122 | 8885 | refused/too_few | 0/122 | 0 | 0.07 | 0.07 | 0.07 (2) | 0.00 (0, max 0) | 0.01
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | wrong | 500 | 35881 | refused/too_few | 0/500 | 0 | 0.29 | 0.30 | 0.26 (2) | 0.00 (0, max 0) | 0.02
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | wrong | 1000 | 72268 | refused/too_few | 0/1000 | 0 | 0.60 | 0.60 | 0.54 (2) | 0.00 (0, max 0) | 0.05
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | wrong | 1500 | 108688 | refused/too_few | 0/1500 | 0 | 0.89 | 0.90 | 0.82 (2) | 0.00 (0, max 0) | 0.07
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | wrong | 2000 | 146010 | refused/too_few | 0/2000 | 0 | 1.21 | 1.22 | 1.12 (2) | 0.00 (0, max 0) | 0.10
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | wrong | 3000 | 216692 | refused/too_few | 0/3000 | 0 | 1.81 | 1.82 | 1.65 (2) | 0.00 (0, max 0) | 0.15
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | right | 122 | 8507 | fits | 93/93 | 93 | 0.13 | 0.13 | 0.12 (4) | 0.00 (4, max 93) | 0.01
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | right | 500 | 35516 | fits | 93/93 | 93 | 0.56 | 0.56 | 0.53 (4) | 0.00 (4, max 93) | 0.03
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | right | 1000 | 71878 | fits | 93/93 | 93 | 1.16 | 1.16 | 1.10 (4) | 0.00 (4, max 93) | 0.05
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | right | 1500 | 107967 | fits | 93/93 | 93 | 1.73 | 1.73 | 1.64 (4) | 0.00 (4, max 93) | 0.08
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | right | 2000 | 145641 | fits | 93/93 | 93 | 2.34 | 2.39 | 2.25 (4) | 0.00 (4, max 93) | 0.11
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | right | 3000 | 214327 | fits | 93/93 | 93 | 3.45 | 3.46 | 3.29 (4) | 0.00 (4, max 93) | 0.16
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | repeat | 122 | 6358 | refused/too_few | 0/122 | 0 | 0.06 | 0.06 | 0.05 (2) | 0.00 (0, max 0) | 0.00
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | repeat | 500 | 26392 | refused/too_few | 0/500 | 0 | 0.23 | 0.23 | 0.21 (2) | 0.00 (0, max 0) | 0.02
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | repeat | 1000 | 52893 | refused/too_few | 0/1000 | 0 | 0.47 | 0.47 | 0.44 (2) | 0.00 (0, max 0) | 0.04
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | repeat | 1500 | 79893 | refused/too_few | 0/1500 | 0 | 0.70 | 0.71 | 0.66 (2) | 0.00 (0, max 0) | 0.05
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | repeat | 2000 | 106893 | refused/too_few | 0/2000 | 0 | 0.94 | 0.94 | 0.88 (2) | 0.00 (0, max 0) | 0.07
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | repeat | 3000 | 160893 | refused/too_few | 0/3000 | 0 | 1.40 | 1.41 | 1.29 (2) | 0.00 (0, max 0) | 0.12
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | common | 122 | 7432 | refused/too_few | 0/122 | 0 | 0.07 | 0.07 | 0.07 (2) | 0.00 (0, max 0) | 0.01
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | common | 500 | 30899 | refused/too_few | 0/500 | 0 | 0.30 | 0.30 | 0.28 (2) | 0.00 (0, max 0) | 0.02
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | common | 1000 | 62004 | refused/too_few | 0/1000 | 0 | 0.61 | 0.62 | 0.59 (2) | 0.00 (0, max 0) | 0.04
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | common | 1500 | 93772 | refused/too_few | 0/1500 | 0 | 0.92 | 0.92 | 0.88 (2) | 0.00 (0, max 0) | 0.07
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | common | 2000 | 125438 | refused/too_few | 0/2000 | 0 | 1.25 | 1.25 | 1.15 (2) | 0.00 (0, max 0) | 0.09
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | common | 3000 | 188359 | refused/too_few | 0/3000 | 0 | 1.84 | 1.84 | 1.69 (2) | 0.00 (0, max 0) | 0.15
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | wrong | 122 | 8885 | refused/too_few | 0/122 | 0 | 0.08 | 0.08 | 0.07 (2) | 0.00 (0, max 0) | 0.01
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | wrong | 500 | 35881 | refused/too_few | 0/500 | 0 | 0.30 | 0.30 | 0.28 (2) | 0.00 (0, max 0) | 0.02
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | wrong | 1000 | 72268 | refused/too_few | 0/1000 | 0 | 0.63 | 0.63 | 0.58 (2) | 0.00 (0, max 0) | 0.05
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | wrong | 1500 | 108688 | refused/too_few | 0/1500 | 0 | 0.95 | 0.96 | 0.88 (2) | 0.00 (0, max 0) | 0.07
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | wrong | 2000 | 146010 | refused/too_few | 0/2000 | 0 | 1.32 | 1.34 | 1.18 (2) | 0.00 (0, max 0) | 0.10
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | wrong | 3000 | 216692 | refused/too_few | 0/3000 | 0 | 1.91 | 1.92 | 1.76 (2) | 0.00 (0, max 0) | 0.16
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | right | 122 | 8666 | fits | 75/75 | 75 | 0.14 | 0.15 | 0.14 (4) | 0.00 (4, max 75) | 0.01
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | right | 500 | 35618 | fits | 75/75 | 75 | 0.59 | 0.60 | 0.57 (4) | 0.00 (4, max 75) | 0.03
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | right | 1000 | 71973 | fits | 75/75 | 75 | 1.22 | 1.23 | 1.19 (4) | 0.00 (4, max 75) | 0.05
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | right | 1500 | 108142 | fits | 75/75 | 75 | 1.85 | 1.89 | 1.81 (4) | 0.00 (4, max 75) | 0.08
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | right | 2000 | 145734 | fits | 75/75 | 75 | 2.53 | 2.53 | 2.44 (4) | 0.00 (4, max 75) | 0.11
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | right | 3000 | 215792 | fits | 75/75 | 75 | 3.78 | 3.79 | 3.72 (4) | 0.00 (4, max 75) | 0.18
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | repeat | 122 | 6358 | refused/too_few | 0/122 | 0 | 0.06 | 0.06 | 0.05 (2) | 0.00 (0, max 0) | 0.00
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | repeat | 500 | 26392 | refused/too_few | 0/500 | 0 | 0.23 | 0.23 | 0.21 (2) | 0.00 (0, max 0) | 0.02
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | repeat | 1000 | 52893 | refused/too_few | 0/1000 | 0 | 0.45 | 0.45 | 0.41 (2) | 0.00 (0, max 0) | 0.04
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | repeat | 1500 | 79893 | refused/too_few | 0/1500 | 0 | 0.68 | 0.68 | 0.62 (2) | 0.00 (0, max 0) | 0.05
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | repeat | 2000 | 106893 | refused/too_few | 0/2000 | 0 | 0.90 | 0.90 | 0.83 (2) | 0.00 (0, max 0) | 0.07
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | repeat | 3000 | 160893 | refused/too_few | 0/3000 | 0 | 1.36 | 1.38 | 1.32 (2) | 0.00 (0, max 0) | 0.13
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | common | 122 | 7432 | refused/too_few | 0/122 | 0 | 0.09 | 0.09 | 0.08 (2) | 0.00 (0, max 0) | 0.01
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | common | 500 | 30899 | refused/too_few | 0/500 | 0 | 0.33 | 0.33 | 0.31 (2) | 0.00 (0, max 0) | 0.02
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | common | 1000 | 62004 | refused/too_few | 0/1000 | 0 | 0.66 | 0.68 | 0.62 (2) | 0.00 (0, max 0) | 0.05
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | common | 1500 | 93772 | refused/too_few | 0/1500 | 0 | 0.97 | 0.97 | 0.90 (2) | 0.00 (0, max 0) | 0.07
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | common | 2000 | 125438 | refused/too_few | 0/2000 | 0 | 1.28 | 1.29 | 1.23 (2) | 0.00 (0, max 0) | 0.11
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | common | 3000 | 188359 | refused/too_few | 0/3000 | 0 | 1.96 | 1.99 | 1.84 (2) | 0.00 (0, max 0) | 0.14

    singles run (second invocation, same script):
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | singles | 122 | 31595 | fits | 792/792 | 792 | 0.24 | 0.24 | 0.12 (2) | 0.09 (2, max 792) | 0.02
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | singles | 500 | 31595 | fits | 792/792 | 792 | 0.23 | 0.24 | 0.12 (2) | 0.09 (2, max 792) | 0.02
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | singles | 1000 | 46613 | fits | 792/792 | 792 | 0.44 | 0.45 | 0.33 (2) | 0.09 (2, max 792) | 0.03
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | singles | 1500 | 83111 | fits | 792/792 | 792 | 0.98 | 0.98 | 0.84 (2) | 0.09 (2, max 792) | 0.08
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | singles | 2000 | 120013 | fits | 792/792 | 792 | 1.54 | 1.55 | 1.37 (2) | 0.09 (2, max 792) | 0.08
    Eminem - Lose Yourself---xFY | {'transcribe': 792} | singles | 3000 | 191831 | fits | 792/792 | 792 | 2.67 | 2.70 | 2.48 (2) | 0.09 (2, max 792) | 0.14
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | singles | 122 | 23484 | fits | 585/585 | 585 | 0.17 | 0.18 | 0.10 (4) | 0.05 (4, max 585) | 0.02
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | singles | 500 | 23484 | fits | 585/585 | 585 | 0.17 | 0.17 | 0.10 (4) | 0.05 (4, max 585) | 0.02
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | singles | 1000 | 52864 | fits | 585/585 | 585 | 0.63 | 0.64 | 0.54 (4) | 0.05 (4, max 585) | 0.04
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | singles | 1500 | 89426 | fits | 585/585 | 585 | 1.23 | 1.23 | 1.10 (4) | 0.05 (4, max 585) | 0.09
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | singles | 2000 | 126631 | fits | 585/585 | 585 | 1.86 | 1.86 | 1.70 (4) | 0.05 (4, max 585) | 0.12
    Beauty and the Beast (1991)  | {'transcribe': 592, 'asr': 264} | singles | 3000 | 198184 | fits | 585/585 | 585 | 3.02 | 3.04 | 2.81 (4) | 0.05 (4, max 585) | 0.17
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | singles | 122 | 18808 | fits | 467/467 | 467 | 0.14 | 0.14 | 0.08 (4) | 0.04 (4, max 467) | 0.02
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | singles | 500 | 20863 | fits | 467/467 | 467 | 0.18 | 0.18 | 0.11 (4) | 0.04 (4, max 467) | 0.02
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | singles | 1000 | 56774 | fits | 467/467 | 467 | 0.78 | 0.79 | 0.70 (4) | 0.05 (4, max 467) | 0.05
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | singles | 1500 | 93407 | fits | 467/467 | 467 | 1.43 | 1.44 | 1.35 (4) | 0.04 (4, max 467) | 0.08
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | singles | 2000 | 130279 | fits | 467/467 | 467 | 2.11 | 2.12 | 1.96 (4) | 0.04 (4, max 467) | 0.10
    정국 (Jung Kook) 'Seven (feat. | {'transcribe': 472, 'asr': 433} | singles | 3000 | 202017 | fits | 467/467 | 467 | 3.36 | 3.39 | 3.31 (4) | 0.04 (4, max 467) | 0.16

## Phase 3 whole-film real SRTs output (raw, 2026-10-29)

Scratch `full_film.py` at `c55cb77`, row 25. Per song: `slice` is the hand-trimmed
slice, `film` the whole film (with its one call's seconds); `kept` and `slice`
lines give each result's cue count (the script also printed the first and last
cue's text, which is left out here: subtitle text stays out of the repo).

```
## Beauty.And.The.Beast.1991.SE.iNTERNAL.DVDRip.XviD-SLeTDiVX.en.srt: 1639 cues, 99,074 chars
  Beauty and the Beast (1991) - Belle [UHD  streams={'transcribe': 592, 'asr': 264}
    slice fits                113/122  drop=0     shift=  -175.06 speed=1.0711 spread=0.205  anchors=113  src=transcribe
    film  fits                113/122  drop=1517  shift=  -175.06 speed=1.0711 spread=0.205  anchors=113  src=transcribe  1.28s
    film kept 122 cues
    slice     122 cues
  Beauty and the Beast (1991) - Be Our Gue  streams={'transcribe': 414, 'asr': 296}
    slice fits                 77/92   drop=0     shift= -2288.83 speed=1.0667 spread=0.192  anchors=77   src=transcribe
    film  fits                 77/92   drop=1547  shift= -2288.83 speed=1.0667 spread=0.192  anchors=77   src=transcribe  1.01s
    film kept 92 cues
    slice     92 cues

## Disney - Pocahontas [DVD DivX].srt: 942 cues, 70,049 chars
  Pocahontas - Colors of the Wind (Blu-ray  streams={'transcribe': 311, 'asr': 310}
    slice fits                 40/40   drop=0     shift= -2363.11 speed=1.0000 spread=0.253  anchors=40   src=transcribe
    film  fits                 40/41   drop=901   shift= -2363.11 speed=1.0000 spread=0.253  anchors=40   src=transcribe  0.79s
    film kept 41 cues
    slice     40 cues

## Mulan.1998.720p.BRrip.x264.GAZ.YIFY.srt: 1261 cues, 80,209 chars
  Mulan _ I'll Make a Man Out of You _ @di  streams={'transcribe': 312, 'asr': 281}
    slice fits                 49/50   drop=0     shift= -2139.46 speed=0.9590 spread=0.280  anchors=49   src=transcribe
    film  fits                 44/51   drop=951   shift= -2139.28 speed=0.9590 spread=0.240  anchors=44   src=asr  0.64s
    film kept 59 cues
    slice     56 cues

## Rent.REAL.DVDRip.XviD-LMG.srt: 1782 cues, 119,182 chars
  Seasons of Love (HD)  streams={'transcribe': 176, 'asr': 26}
    slice fits                 26/33   drop=0     shift=   -66.57 speed=0.9590 spread=0.232  anchors=26   src=transcribe
    film  fits                 23/33   drop=1749  shift=   -66.53 speed=0.9590 spread=0.200  anchors=23   src=transcribe  0.47s
    film kept 33 cues
    slice     33 cues

## The Lion King I - [1994].srt: 1677 cues, 102,871 chars
  The Lion King - Can You Feel The Love To  streams={}
    slice no_reference          0/0    drop=0     shift=     0.00 speed=1.0000 spread=       anchors=0    src=None
    film  no_reference          0/0    drop=0     shift=     0.00 speed=1.0000 spread=       anchors=0    src=None  0.01s
  The Lion King - Hakuna Matata Music Vide  streams={'transcribe': 352, 'asr': 339}
    slice fits                 75/94   drop=0     shift= -2683.96 speed=1.0000 spread=0.155  anchors=75   src=transcribe
    film  fits                 76/96   drop=1345  shift= -2683.96 speed=1.0000 spread=0.158  anchors=76   src=transcribe  0.90s
    film kept 103 cues
    slice     101 cues
```

## Hand-off prompt (executor)

> Execute `plans/movie-subtitle-slice.md` from Phase 0. Branch
> `movie_subtitles` off `dev`. Phase 1 is a mockup published as an Artifact;
> stop at GATE A for Ken. Phase 2 ends at GATE B: stop and hand the
> calibration table to Opus, don't choose thresholds. Real subtitle slices live
> in `~/pikaraoke-songs/movie_subs/` and must never be committed. Log every
> phase's raw results in the plan's Results log.
