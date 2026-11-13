# Backing vocals in parentheses: show the sung ones on caption and LRC songs

Model: Claude Opus 5.5 runs Phase 0, judges both gates and writes the build spec.
Claude Sonnet 5.5 builds from that spec. (High-level spec by Claude Fable 5.2, 2026-11-11.)

Branch `backing_vocal_lines` off `dev` at `1016e20`, worktree
`.claude/worktrees/backing_vocal_lines`. Work and run everything from the worktree. Whisper
needs `models/` symlinked in from the main checkout before any GPU run, and only one app or
replay instance may run at a time.

## Goal

Lyric sources put backing vocals and call-and-response in parentheses: "(oh, oh, oh)",
"(I'ma leave the door open)". On caption-timed and LRCLIB-timed songs the cleaner deletes
everything inside parentheses, so those words are never aligned and never shown. Ken wants
them on screen, **provided adding them does not make the existing lines' timing worse**. Cue
timing is already good; protecting it outranks showing more backing lines.

The same parentheses also hold stage directions, "(upbeat music)", "(crowd chanting)", which
must stay off the screen. The feature therefore needs a test that tells sung from not sung.
The proposed test: keep a parenthetical only if the transcriber heard its words inside that
cue's time window.

## Decisions (Ken, 2026-11-11)

1. Show sung backing lines, if that is not detrimental to cue-align timing.
2. They keep their parentheses on screen. Genius songs change to match: today they show the
   words bare.
3. A cue that is nothing but a parenthetical becomes its own line only when it was heard and
   its time does not overlap another line's.
4. New and regenerated songs only. Edited and custom sheets are left alone. A regeneration of
   the affected library songs is decided at GATE B, and Ken runs it.

## What exists (checked 2026-11-11, `dev` at `1016e20`)

- `pikaraoke/lib/genius_lyrics.py`: `clean_srt_line` / `strip_srt_markup` delete paren
  contents. `parse_lyric_lines` (Genius and pasted sheets) keeps the words in `align_text`
  and removes only the paren characters.
- `pikaraoke/lib/srt_cues.py`: `clean_cue_texts` / `cue_spans_from_srt` are the caption
  loader, and LRC goes through the same cleaning (`srt_slice_fit.lrc_to_srt`, which also
  merges same-stamp duet lines into one cue). `word_edit.py` relies on a cleaned line
  cleaning to itself.
- `clean_srt_line` has other callers that are not lyric sheets: `ytasr.py` (filters YouTube
  auto-captions) and `scripts/split_songs.py` (capitals detection). They must keep dropping
  parentheticals.
- On the cue route one cue is one line, and the cleaned text is both the aligner's input and
  the screen text (`lyric_align._load_lyrics` returns the same list twice). `generate_ass`
  renders each word from the raw half of `joint_match._tokenise_lines` tokens;
  `token_align._normalize_token` strips non-word characters, so a raw token can carry a
  paren while its normalised form does not. Not checked: whether a paren in the text handed
  to the forced aligner changes its word output.
- `pikaraoke/lib/cue_align.py`: lines are grouped into sections at silent gaps and each
  section is force-aligned as one text, so a changed line can move its section-mates. Lines
  the align leaves short go to a rescue (re-align, then paced or guessed words), counted in
  the bundle under `joint_stats.repace`.
- The only evidence for dropping caption parens is commit `acf36e01` (2026-05-24): 12 caption
  files, all parens stage directions. LRC was routed through the same cleaner later with no
  audit. No with/without timing comparison exists in `plans/` or any `archive/*` tag.

Library tally (`~/pikaraoke-songs`, read-only, excluding `backups/` and `regen_backups/`,
which hold old copies and inflate every count if globbed):

| Source | Files | With paren text | Paren groups |
|---|---|---|---|
| `subtitles/*.srt` | 154 | 78 | 446 (212 cues inline, 241 cues paren-only, the latter in 65 files) |
| `lyrics/*.lrc` | 36 | 25 | 233 |

- Captions are a mix of directions and sung lines. LRC is almost all sung, with a little
  junk such as "(official video)".
- All 134 bundles in `alignment_debug/` have a `transcribe_words` key (one bundle opened:
  word, start, end, probability). Cue songs also record `cue_inputs` (spans, sections,
  realigns), `lyrics.source_path` and `lyrics.origin`. Bundle lines are already cleaned, so
  the parentheticals must be read from the raw `.srt` / `.lrc`.
- LRC stamps are on the LRC's own clock; the fitted `lyrics/*.lrclib.srt` (12 files) is on
  the video's clock but already cleaned. Placing a raw LRC parenthetical on the video clock
  needs the fit, or its neighbours' fitted times.
- The library was mass-renamed on 2026-11-08: match songs by YouTube ID, not by stem.
- YouTube auto-captions exist for only 6 of the 78 songs, so they cannot be the test.

## Phases

### Phase 0: measure (Opus, CPU only, nothing shipped, library read-only)

1. **Inventory.** Every parenthetical in the raw caption and LRC files of songs that have a
   cue bundle: song (YouTube ID), source, text, inline or paren-only, its window on the
   video clock, and whether that window overlaps another cue's.
2. **Label before testing.** Label every distinct parenthetical text `sung`, `direction` or
   `unsure`, from the text and its context alone, and write the labels into this plan before
   step 3 runs, so the results cannot bend them. `unsure` is for text that could be either
   ("(heartbeat)", "(go)", "(skate)", "(censored)"); those go to Ken at GATE A.
3. **Heard test.** For each parenthetical, were its words in `transcribe_words` inside its
   window? The matching rule (how much padding, what share of the words, how vocables such as
   "oh" / "ooh" / "woo" are compared) is Opus's to design; record the rule and every
   variant tried.
4. **Comparison rule.** Score one transcript-free rule on the same labels: a parenthetical is
   a direction if it reads like one (names a sound or action: "music", "laughs", "crowd
   cheering"). It is the fallback if the heard test fails the gate.
5. **Baseline.** For every line that would gain words and every line sharing a section with
   a line that would change or be added, record today's word timings and rescue status from
   the bundle. Phase 2 diffs against this.

### GATE A: is there a test good enough to build on? (Opus judges, Ken rules)

Judge on the `sung` and `direction` labels only; `unsure` rows are reported separately with
what each rule did to them. Report captions and LRC separately, and within `sung` report
vocable-only parentheticals apart from worded ones, since transcribers are least reliable on
vocables.

- **A1, directions kept: must be zero.** A stage direction shown as a lyric is the worst
  outcome this feature can produce. If any labelled direction passes, tighten the rule and
  re-measure. A rule that cannot reach zero fails.
- **A2, sung kept.** Backing vocals sit under the lead, so the transcriber may miss many.
  - 70% or more of labelled-sung kept: pass.
  - 40% to 70%: try one consistency variant (a text heard once in a song keeps its repeats in
    that song) and re-measure A1 and A2. Pass if it reaches 70% with A1 still zero.
  - Under 40% after the variant: the transcript is the wrong test.
- **A3, consistency.** Count songs where the same parenthetical text is kept in one place and
  dropped in another. Not a pass/fail number: list them, because a chorus echo shown once and
  missing the next time is what Ken would notice.
- **A4, paren-only lines.** Of the heard paren-only cues, how many overlap another line and
  are dropped by Decision 3. If nearly all are, say so: that half of the feature is then
  close to empty.

Outcomes:

- **GO:** A1 and A2 pass on the heard test. Opus writes the build spec.
- **GO on the fallback:** the heard test fails A2 but the comparison rule passes both A1 and
  A2. Put this to Ken as a choice, since it is a different design (a word list to maintain,
  no audio evidence), and do not write the build spec until he rules.
- **NO-GO:** neither passes. Report the numbers and stop.

The 70 and 40 are starting points set without data; Ken may move them when he sees the
tables. In every outcome, stop at GATE A and report: the four tables, the `unsure` list for
Ken's labels, and the recommendation.

### Build spec (Opus writes after a GO; Sonnet builds)

Opus adds a Design and a Commits section to this plan. It must settle:

- Where the keep-or-drop decision is made. The cleaners are pure text functions with no
  transcript; the transcript exists only inside the align stage. Check the stage order on the
  cue route before choosing.
- What a saved sheet contains (`.lrclib.srt`, the caption sheet Edit words opens), given
  Decision 4 and that a cleaned line must still clean to itself.
- One rule for captions and LRC, in one place. The non-sheet callers of `clean_srt_line`
  keep today's behaviour.
- Parens on screen with paren-free matching, on both routes. On the Genius route only the
  word text may change; its timing must not.
- Paren-only cues as lines: the overlap rule of Decision 3, and where a new line sits
  relative to sections.
- What happens to a kept parenthetical the aligner cannot time (see B3).
- Tests per CLAUDE.md, and the open-issues entries this touches ("Cue align windows").

Not doing: any test on Genius parens (they all stay), `[bracket]` directions, note glyphs or
speaker labels, changes to the rescue or onset snap, the stem separator, rebuilding edited
or custom sheets, any library write before GATE B.

### Phase 2: replay (after the build, local GPU, output outside the library)

Replay before and after on the same commit base, writing bundles and `.ass` files to a
scratch folder, never into `~/pikaraoke-songs`. Songs: every cue song where the rule keeps at
least one parenthetical if the run time allows; otherwise at least 20, chosen by a stated
rule that covers captions and LRC, inline and paren-only, and the cue-align test songs that
are affected. Add every Genius-route song whose sheet has parens, for B6. Add 5 cue songs
with no parentheticals as a control: their output must not change at all.

### GATE B: is it detrimental to timing? (Opus judges B1-B6, Ken's ear rules)

"Old words" are the words on screen before the change; "new words" are the kept
parentheticals. There is no independent timing truth on cue songs, and the 2026-11-10 onset
probe showed the transcriber cannot referee a moved line start, so the numbers find what
moved and Ken decides whether a move is worse.

- **B1, control:** the 5 control songs are identical before and after. Any difference is a
  bug; stop.
- **B2, old words moved:** per old word, the change in start and in end. Report the count
  moved more than 0.3 s (the threshold the onset probe used) and the full distribution,
  split into lines that gained words, section-mates of a changed line, and all other lines.
  "All other lines" must show zero moves. Every old word moved more than 0.3 s goes on the
  listening list.
- **B3, rescue counts on old lines:** re-aligned lines, paced lines, guessed words and
  zero-length words, before and after, old lines only. Any increase fails unless each added
  case is explained and listed for Ken.
- **B4, new words timed:** share of new words with measured timing (not guessed, not
  zero-length). Under 80% means the aligner is not finding what the test said was sung: fail,
  and go back to the rule or to dropping untimed parentheticals.
- **B5, screen:** no labelled direction appears in any output; no two lines are on screen
  together that were not before.
- **B6, Genius:** every word's start and end identical before and after; only the word text
  differs.

**Listening list for Ken:** at most 10 spots, each with song, time, what changed and by how
much, drawn from B2's largest moves first, then a spread of new inline and new paren-only
lines. Written so he can check each in under a minute.

- **GO:** B1, B5, B6 pass outright, B2-B4 pass or every exception is on the list, and Ken
  accepts what he heard. Then Ken decides on the library regeneration.
- **NO-GO:** anything else. Report which check failed and the smallest change that would fix
  it; do not adjust thresholds to pass.

## Results log

Raw tables, commands and commits only; no verdicts in this table.

| # | date | phase | what ran (command, commit) | raw result |
|---|---|---|---|---|
