# Backing vocals in parentheses: show the sung ones on caption and LRC songs

Model: Claude Opus 5.5 runs Phase 0, judges both gates and writes the build spec.
Claude Sonnet 5.5 builds from that spec. (High-level spec by Claude Fable 5.2, 2026-11-11.)

**Status: GATE A ruled GO on the amended hybrid, 2026-11-14 ("GATE A ruling"). Build spec
written 2026-11-14 ("Build spec": Design, Commits). Next: Ken reads the spec and its four
choices; then Sonnet builds C0-C7. No code yet.**

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
   its time does not overlap another line's. Ruled 2026-11-14: "time" is cue time when the
   line is chosen; overlap on screen is judged at GATE B on the new timings.
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
- LRC stamps are on the LRC's own clock; the fitted `lyrics/*.lrclib.srt` is on the video's
  clock and keeps the record's text as pasted, parentheses included
  (`srt_slice_fit._corrected_srt`; corrected in Phase 0 step 1, which read every raw LRC
  parenthetical and its window straight from it).
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
- The keep-or-drop decision comes after the LRCLIB pick. Branch `lrclib_fit_pick`
  (`plans/lrclib-fit-pick.md`, "Phases 4-6") freezes `clean_cue_texts`, `clean_srt_line` and
  `lrc_to_srt`, because its bar was measured on cleaned lines: 12 of its 31 GATE Q picks have
  a line that is all parentheses, and Who You Are and Love Me Now were flagged for exactly
  those echoes. The pick keeps seeing today's cleaned lines; kept parentheticals join after it.
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

#### Design (Opus 5.5, 2026-11-14)

Code read on `b2f914be` (dev `1016e20` plus plan commits). Counts are from Phase 0's saved
outputs (Results row 10, `spec_counts.py`). The rule, its pad and its vocable set are the ones
ruled at GATE A; nothing here re-tunes them.

**Summary.** No cleaner and no sheet changes. On the cue route the first section pass runs on
today's lines, as now, and fits the display lead. A new pure step takes that lead, the
transcript the de-reverb gate already made and the sheet's parentheticals, and applies the
ruled rule. Nothing kept: the song finishes on today's path, call for call. Something kept:
the kept words join their lines, kept paren-only cues become lines, the song is re-sectioned,
only the sections whose window or text changed go back to the aligner, and the rescue runs
with the display lead today's lines give. A last pass, on every alignment route, puts the
parentheses back on the karaoke words. The aligner and the matchers see only words.

**D1. Where the decision is made: inside `cue_align.align_song`, after its first
`fit_offset`.** The cue route runs `LyricAlignStage.run` (sheet loaded by `_load_lyrics` →
`cue_spans_from_srt`) → `_run_cue_align` → `_dereverb_gate` (transcribe, maybe re-transcribe
dry) → `align_song`: section pass on the cue spans → `fit_offset` → a second pass on shifted
spans when the lead exceeds the 0.75 s pad → `repace_bad_lines` → back in the stage, edge snap
→ ASS. The rule needs the transcript, which exists before `align_song`, and the display lead,
which exists only after its first pass: `joint_stats.offset_s` is that first `fit_offset`,
rounded to 3 dp, and is what Phase 0 used. The cleaners have neither. The first pass is
today's pass on today's lines, so the rule sees the lead it was measured with. The LRCLIB pick
runs in `run` before the cue route (`lrclib_fit_pick` 4d), so the decision comes after it.

**D2. The pick and the cleaners are untouched.** `clean_cue_texts`, `clean_srt_line`,
`strip_srt_markup`, `cue_spans_from_srt`, `lrc_to_srt` and `fit_slice` keep their code and
their output for every caller (`ytasr.py` and `scripts/split_songs.py` included); their
existing tests pass unedited. The parentheticals are read by a second function from the same
sheet text (D4) and join inside `align_song` (D7).

**D3. Sheets.** None changes. `.lrclib.srt` stays `fit_slice`'s output, the record's text
with its parentheses; captions stay as downloaded. The keep is decided again on every run from
the raw sheet and that run's transcript, and is never written to a sheet. Edit words opens
`cue_spans_from_srt`'s cleaned lines, as today, and saves them, so an edited sheet holds no
paren group (`edited_srt` refuses any line its cleaning would change) and gets no backing
lines: Decision 4's "left alone" holds with no code, and a cleaned line still cleans to itself
because the cleaner is unchanged. Consequence: saving a word edit on a song that shows backing
lines drops them (choice 3). Movie sheets (`movie_srt`, `.custom.srt`) are not tested, since
Phase 0 measured captions and LRC only: the step runs for origins `srt` and `lrclib_srt`
(`backing_vocals.ORIGINS`; the stage cannot import `library_regen`, so a test ties the
constant to `LRC_ORIGIN`). An edited sheet records its source's origin but holds no group, so
it needs no check of its own.

**D4. Reading the parentheticals: `srt_cues.sheet_parens(srt_text) -> list[ParenCue]`.** As
Phase 0's `inventory.py` read them: per cue, every match of the pattern `clean_srt_line`
deletes, found after the markup strip (tags, `[brackets]`, note glyphs, quote and lookalike
folding); its text is the inner words, spaces collapsed; an empty group is skipped.
`ParenCue`: `index` (the cue's place in the sheet, every cue counted), `span`, `inline` (the
cue still has words once cleaned), `line` (inline: its line in `cue_spans_from_srt`'s list;
paren-only: the line it goes before, the line count after the last), and `groups`, each a
`ParenGroup(text, at)`. `at` is where the group sits in today's cleaned line: the cue's
markup-stripped text up to the group's `(`, cleaned the way `clean_cue_texts` cleans that cue
(the same file-level speaker-label and capitals decisions), counted in space-split tokens;
`None` when today's cleaned line does not begin with exactly those tokens. That catches a group
glued inside a word ("love(oh)you" cleans to "loveyou"). None of the 205 inline keeps is glued
to a letter; 4 have a comma right after the `)`, which is its own token today. In a file typed
in capitals a group's text is recased as its line is. `sheet_parens` lives in `srt_cues`
because it needs the cue cleaner's private per-file decisions. `genius_lyrics._strip_markup`
and `_PAREN_CONTENT_RE` become public (`strip_markup`, `PAREN_GROUP_RE`), a rename only, so
the pattern stays in one place.

**D5. The rule: `backing_vocals.judge(cues, line_spans, heard_words, offset) ->
list[Verdict]`**, in a new module `pikaraoke/lib/backing_vocals.py`. `none +vocables
+consist` as measured. `plans/backing-vocal-lines/heard.py` is the reference: its constants
(the step 2 vocable set, the vocable classes, the 0.5 s pad, the 0.5 share) are copied, not
re-derived. Per group:

1. Quote-opened (first character `"` after folding): dropped, `quote`, and never a source for
   step 4.
2. Heard: the window is the cue's span plus `offset`, padded 0.5 s each side; a transcript
   word is in it when their spans overlap (it ends after the window starts and starts before
   it ends). Transcript words and the group's text are split at spaces, hyphens and slashes and
   normalised (`_normalize_token`, empties dropped). The share is the fraction of the group's
   distinct words equal (`_match_simple`, or the same vocable class) to a word in the window:
   `heard` at 0.5 or more. Nothing is used up, so the line's own words count (`consume none`,
   the ruled variant).
3. `vocable` when every word is in the step 2 set.
4. `consistency` when the group's text key (Phase 0's label key) is kept by step 2 or 3
   elsewhere in the sheet.
5. After step 4, as measured (these never feed it): an inline group whose `at` is None is
   dropped, `unplaced`; a paren-only cue whose span overlaps by more than 0 s another line's
   cue span (one of today's lines, or a paren-only cue kept earlier in sheet order) is dropped,
   `overlap`. Decision 3's "heard" is read as "kept by the rule", which is how GATE A counted
   the 56.

Anything else is `not_heard`, including a group with no word once normalised (none in the
library; heard.py would divide by zero on one). A `Verdict` holds the cue index, group index,
kind, verdict and share. Inputs: the gate's transcribe words as the bundle stores them, cue
spans on the video clock, and the first pass's lead as the exact float (Phase 0 used the
bundle's 3-dp value; the parity step C2p feeds that). No setting: if GATE B drops an evidence
kind, that is a step deleted from `judge`.

**D6. The new lines: `backing_vocals.with_backing(display_lines, align_lines, spans, cues,
verdicts) -> Backed`**, holding display lines, align lines, spans and `old_line_ids` (each new
line's id in today's list, None for an added line).

- Today's lines keep their display and align text exactly, stray unbalanced parens included
  (`D_dOXTpwV5s` "(heeyyy]").
- An inline cue's kept groups go into its line at `at`, today's tokens untouched. Display: the
  group's first word gains `(`, its last `)`. Align: the same words bare. "Hey (hey!) you"
  gives display "Hey (hey!) you", align "Hey hey! you". Groups keep their order; a dropped one
  leaves no trace.
- A paren-only cue with a kept group becomes a new line before `line`, at its cue's span:
  display "(oh, oh)", align "oh, oh". Several kept groups in one cue join in order (one such
  cue in the library, with one group kept).

No paren this feature adds reaches the aligner or a matcher, so the question in "What exists"
(does a paren in the aligner's text change its output) does not arise.

**D7. Timing: `align_song` gains `parens: list[ParenCue] = ()` and `heard_words: list[dict] |
None = None`** (`cue_heard_rescue` gives `align_song` the gate's words under the same name).
With no parens, no heard words or nothing kept, every step and every aligner call is today's.
When something is kept:

1. Today's shipping pass is computed as now: the first pass, and the shifted pass when the
   lead exceeds the pad (none of the 34 songs does). The rescue's display lead is fitted on
   that pass, the value today's rescue fits, and pinned.
2. The song is re-sectioned on the new lines' spans (shifted as before when it re-sectioned)
   by the same gap rule: a new line is a cue like any other. Of the 56 paren-only lines kept,
   22 join one of today's sections, 2 make their own, 31 bridge a gap and merge two of today's
   sections, and 1 (`D_dOXTpwV5s`, a run captioned with no gap) moves where the 60 s cap splits
   its run. Step 5's baseline counted "mate of an added line" the same way.
3. A section whose window and text both equal one already aligned in this call reuses that
   align's words; the rest go to the aligner. One dict keyed by `(t0, t1, text)` over the
   section aligns. It saves the GPU on untouched sections and makes them identical by
   construction, not by aligner determinism.
4. `repace_bad_lines` gains `offset: float | None = None` (None fits it as today) and runs on
   the new lines with the pinned lead. Nothing else in the rescue changes. What else it reads
   (repeat runs, the next line's cue for the singing end, the previous line's end, guessed-word
   bounds) comes from the new lines, as for any line.
5. `align_song` returns a fourth item, the lines it timed, `(display_lines, align_lines)`: its
   inputs when nothing was kept. The stage records them as the bundle's `lyrics.lines` and
   `lyrics.align_lines`, so line ids agree with `output_line_timings` for
   `library_status._missing_words`, Song Info and Phase 2.

Recorded: `joint_stats.backing` whenever the sheet has a parenthetical and the step ran:
`groups` (per group: `cue`, `group`, `kind`, `verdict`, `share`, `line_id` in the new lines or
None, `tokens` as [first, end) of that line's align tokens), and when something was kept
`old_line_ids` and `aligned_sections` (the new-line `[lid_lo, lid_hi]` of each section step 3
sent to the aligner). `cue_inputs` describes the shipping pass (new spans, its sections) and
adds `rescue_offset` when the lead was pinned, so an offline replay of the rescue can pass it
back. No `SCHEMA_VERSION` bump: the keys are additive, and a bump would make every library
song stale, against Decision 4. The `alignment_capture` header lists the new keys. One info
log line: groups kept by evidence, dropped by reason, lines added.

What this guarantees at GATE B: an old line can move only if it gained words, sits in a
section that went back to the aligner, or is directly before or after a changed or added line
(the singing-end search, the start bound, the guessed-word bounds, the repeat runs and both
edge snaps look one line over). B2's three groups are then: gained words; near a change (the
other two); all other lines, which must be identical. "Near a change" is wider than the
plan's "section-mates" (choice 4): the ruling expects the line before a paren-only line to
move, and for 31 of the 56 that line is in another of today's sections.

**D8. A kept parenthetical the aligner cannot time is shown with the rescue's timing,** as any
lyric word is: a gainer's untimed echo words are guessed at its pace; a paren-only line left
short is re-aligned over its cue window, else paced across it. Nothing is dropped after
alignment in this build. B4 is computed from the bundle (`tokens` against
`cue_inputs.sections` and `realigns`, as `baseline.py` read old lines); if it fails, dropping
untimed parentheticals is the GATE B change. The risk to look for: a gainer whose echo words
the aligner drops can fall under the section split's half-the-tokens bar ("Baby (oh oh oh oh)"
with the "oh"s dropped is 1 of 5) and come back empty, which sends its lead words to the
rescue too. B2's gained-words group and B3 show it; the smallest fix to try then is counting a
gainer's coverage on its old words, a rescue change this build does not make.

**D9. Parens on screen: `backing_vocals.show_parens(line_objects, display_lines,
align_lines)`**, called by the stage in alignment mode after the snaps and the LRCLIB fills,
before the ASS is written (transcribe mode's words are the transcriber's own). On every route
a shown word's text is a raw token of its line's align text, in token order
(`split_section_to_lines`, the rescue, `_build_line_object`, `_align_line_object`,
`lrclib_fill`). A line whose display text equals its align text is left alone: every cue line
of today, which keeps B1 exact. Otherwise display tokens pair with align tokens in order, equal
or equal once `(` and `)` are removed; a display token that is only parens joins the next token
(the previous one at the line's end). Each word, in order, takes the display form of the next
align token equal to it. A line that does not pair, or a word that finds no token, keeps its
text. Only `word` changes, never a time, which is B6 by construction. Genius's `align_text` is
its display with the parens removed, so its lines pair; new cue lines pair by D6. Custom typed
sheets share Genius's parser and show their parens too (choice 2).

**For Phase 2.** There is no off switch, so "before" is the base commit and "after" the build
on it; name both. Evidence per group comes from `joint_stats.backing`; B2's groups from
`old_line_ids`, `aligned_sections` and line adjacency (D7); B3 from the rescue's stats mapped
through `old_line_ids`.

**Landing order.** Three open branches touch the same code; whichever lands second is
replayed onto the other.

- `lrclib_fit_pick` (Phase 4 not built) moves `_dereverb_gate` into `run` and adds origin
  `lrclib_auto_srt`, whose sheet is `fit_slice` output with the record's text as pasted. If it
  lands first: add its origin to `ORIGINS` (the same LRCLIB records were measured), and read
  the parentheticals from the sheet its pick writes.
- `cue_heard_rescue` (stopped at 3b2) passes the same `heard_words` to `align_song` and turns
  the rescue into a class that fits its lead when built; the pinned lead goes there. Its rules
  look for a line where the transcriber heard its words, and an echo's words are its lead's,
  so a new line could be aimed onto the lead's audio. If both are on Phase 2's base, report
  heard-aimed moves of new lines on their own.
- `onset_loud_start` changes the `snap_line_edges` call; `show_parens` runs after it. No other
  contact.

**Choices made here that Ken may overrule.**

1. A new line is a cue like any other, so the song is re-sectioned (D7.2). The alternative, a
   new line joins the nearer of today's sections and never merges two, moves fewer lines, but
   leaves a section edge where the echo is sung and differs from how step 5 counted mates.
2. Custom typed sheets show their parens (D9). The alternative is an origin check for
   `custom` in the display pass.
3. Saving a word edit drops a song's backing lines (D3). Keeping them needs Edit words to show
   the bundle's kept groups and an edited sheet that keeps them as typed: its own step,
   recorded in open issues (C6).
4. B2's middle group is "near a change" (D7), not "section-mates". As written, the line
   before a paren-only line in another of today's sections would fail "all other lines" by
   design. GATE B's text is left as Ken ruled it until he says.

#### Commits (Sonnet 5.5)

Executor rules: branch `backing_vocal_lines`, in its worktree. No library write; C2p's library
read is read-only, checked with `find ~/pikaraoke-songs -newer <stamp>`. Tests use made-up
lines and a stub aligner, as `test_cue_align.py` does; no lyric text from the library. Each
commit's tests ride with it; pre-commit on the files changed. STOP and report when an anchor
differs, C2p differs from Phase 0, an existing test needs more than a call-shape edit, a
cleaner's output changes, or anything here contradicts the code.

- [ ] **C0. Anchors** (no commit). Confirm these exist as D1-D9 use them:
  `srt_cues.clean_cue_texts`, `_clean_cue`, `is_all_caps`, `_recase_line`,
  `cue_spans_from_srt`; `genius_lyrics._strip_markup`, `_PAREN_CONTENT_RE`, `clean_srt_line`,
  `parse_lyric_lines`; `cue_align.align_song`, `segment_by_gaps`, `split_section_to_lines`,
  `repace_bad_lines`, `fit_offset`; `joint_match._tokenise_lines`;
  `token_align._normalize_token`, `_match_simple`; `LyricAlignStage.run`, `_load_lyrics`,
  `_run_cue_align`, `_write_debug_capture`; `library_regen.LRC_ORIGIN`, `MOVIE_ORIGIN`;
  `word_edit.edited_srt`. And that neither `lrclib_fit_pick` Phase 4 nor `cue_heard_rescue`
  is on `dev`; if one is, STOP ("Landing order").
- [ ] **C1. `feat(lyrics): read a cue sheet's parentheticals and where each sits in its
  line`.** D4: the two renames in `genius_lyrics` with their callers; `ParenGroup`,
  `ParenCue`, `sheet_parens` in `srt_cues`. Tests in `test_srt_cues.py`: a group at a line's
  end, start and middle; two groups in one cue; a paren-only cue (`inline` False, `line` the
  next line's id, the line count after the last line); a group on a cue's second line; a
  speaker label after a leading group ("(oh) MARA: hey": line "hey", `at` 0) and before one
  ("MARA: hey (hey)": `at` 1); a glued group (`at` None); a capitals file (group recased); an
  empty group skipped; an unbalanced "(x]" not a group; `[x]` inside a group stripped; a
  curly-quoted title card whose text starts with `"`; every inline cue's line equal to
  `cue_spans_from_srt`'s. Existing cleaner tests unedited. Then `docs(plans): backing-vocal-lines
  inventory.py follows the rename`, so the Phase 0 record still runs (plan-only, not landed).
- [ ] **C2. `feat(cue_align): which parentheticals were sung, by the GATE A rule`.** D5:
  `backing_vocals.py` with `ORIGINS`, the copied constants, `Verdict` and `judge`. Tests in a
  new `tests/unit/test_backing_vocals.py`, made-up words: a share of exactly 0.5 kept, under it
  dropped; a word ending exactly where the padded window starts is out; the lead shifts the
  window; a vocable heard as another of its class; a vocable-only group kept with an empty
  transcript; consistency keeps an unheard repeat of a heard text; a heard quote-opened group
  is dropped and keeps no repeat; an echo heard only on its line's own words is kept; overlap
  with one of today's lines and with an earlier kept paren-only cue; a later cue overlapping
  only a dropped one is kept; `unplaced`; `ORIGINS` holds `srt` and `library_regen.LRC_ORIGIN`
  and not `MOVIE_ORIGIN`.
- [ ] **C2p. Parity on the library, read-only.** New `plans/backing-vocal-lines/parity.py
  ~/pikaraoke-songs plans/backing-vocal-lines/out`: for every song in `songs.json` not
  skipped, read its sheet as the stage does (UTF-8), run `sheet_parens`, then `judge` with the
  bundle's `transcribe_words`, its `joint_stats.offset_s` (or 0.0) and the sheet's line spans.
  Against `out/heard.json`: the same 626 groups by (song, cue, group), none extra; kept exactly
  where `consume none +vocables +consist` kept, less any `unplaced` (each listed); 180 `heard`,
  60 `vocable`, 21 `consistency`; no `quote` or `overlap` among them. Any other difference is a
  STOP. Commit the script and a Results log row as `docs(plans): backing-vocal-lines parity of
  the built rule with Phase 0`.
- [ ] **C3. `feat(lyrics): karaoke words keep their parentheses`.** D9: `show_parens`, and
  the stage calls it in alignment mode before `_generate_ass`. On its own this changes the word
  text of Genius and custom songs with parens (Decision 2), never their timing. Tests: a
  Genius-shaped line ("(I can't help) Falling", words I, can't, help, Falling) shows "(I",
  "can't", "help)", "Falling" with every start and end unchanged; lone "(" and ")" tokens; a
  word the aligner dropped; "oh (oh)"; a line whose text equals its align text untouched, stray
  paren included; an interp line with no words; a line that does not pair. In
  `test_lyric_align.py`: the joint route's ASS carries "(I" at unchanged times; transcribe mode
  does not go through it.
- [ ] **C4. `feat(cue_align): kept backing vocals join the song's lines and are timed with
  them`.** D6, D7: `with_backing`; `align_song`'s two keywords, the section memo, the pinned
  lead, the fourth return item, `joint_stats.backing` and `cue_inputs.rescue_offset`;
  `repace_bad_lines(offset=...)`; the `alignment_capture` header. Tests in `test_cue_align.py`
  with a stub aligner that logs its calls: no parens, no heard words, or nothing kept give the
  same calls and output as a call without the keywords; an inline keep sends only its section
  back, with the echo words bare, and the other sections' line objects are identical; a
  paren-only keep in a short gap gives one merged section call and a new line with display
  "(oh, oh)" and bare words; one far from both gets its own section; the rescue's lead is
  today's when the new lines alone would move it (the stub realign of an unchanged rescued line
  gets today's window); a re-sectioned song; `old_line_ids`, `aligned_sections`, `tokens`, the
  returned lines. In `test_backing_vocals.py`: `with_backing` at a line's start, middle and
  end, two groups, a paren-only line before a line and after the last. Existing `align_song`
  tests: call shape only.
- [ ] **C5. `feat(pipeline): caption and LRC songs show the backing vocals they sing`.** D3,
  D7.5: in `run`, on the cue route with an origin in `ORIGINS`, `sheet_parens` of the sheet
  `_load_lyrics` read; `_run_cue_align` takes them, passes them and the gate's words to
  `align_song`, and hands back the timed lines, which the bundle records. `_load_lyrics` is
  unchanged. Tests in `test_lyric_align.py`, workers mocked as there: a caption sheet with a
  paren-only echo and an inline echo the mocked transcript hears gives a bundle whose
  `lyrics.lines` hold both, `output_line_timings` ids that match them, and ASS words "(oh,";
  the same sheet as `movie_srt`, and an edited caption sheet (cleaned lines), are timed as
  today; an `lrclib_srt` sheet takes the same path as the caption; the joint route gets no
  parens.
- [ ] **C6. `docs(plans): open issues for backing vocal lines`**, in `plans/open-issues.md`
  (this one lands). Under "Cue align windows": on "Repeated tokens get two assignment rules",
  that an echo line repeats its lead's words within one line, so the in-order guess can put an
  echo's timing on the lead's token, now a common case, watched at GATE B (B3, B4); on "Duet
  ending", that a paren-only line after the last caption becomes the song's last line and takes
  the uncapped tail window. New, under a heading for this feature: Edit words drops a song's
  backing lines on save (choice 3); Repair's LRCLIB list scores and counts "mapped N of M"
  against the lines the song shows (`current_lines`), backing lines now included.
- [ ] **C7. Finish.** Full suite; pre-commit on the changed files; self-review on the three
  axes; `graphify update .`; Results log row. **STOP: review due** (core pipeline, several
  files). Hand Ken the line; do not launch it: `/code-review <C1>~1..HEAD` on `srt_cues.py`,
  `genius_lyrics.py`, `backing_vocals.py`, `cue_align.py`, `lyric_align.py`,
  `alignment_capture.py` and their tests, three finders: correctness (nothing kept gives
  today's calls and output; a reused section is identical; `judge` is heard.py's rule),
  simplicity (one rule, one reader, no second cleaner, no handling for states that cannot
  occur), robustness (stray and glued parens, capitals files, window edges, re-sectioned songs,
  an empty transcript). Phase 2 follows the review.

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
  together that were not before. Amended 2026-11-14 ("GATE A ruling"): a kept paren-only
  line is checked against its neighbours on the after timings, not on today's.
- **B6, Genius:** every word's start and end identical before and after; only the word text
  differs.

**Listening list for Ken:** at most 10 spots, each with song, time, what changed and by how
much, drawn from B2's largest moves first, then a spread of new inline and new paren-only
lines. Written so he can check each in under a minute.

- **GO:** B1, B5, B6 pass outright, B2-B4 pass or every exception is on the list, and Ken
  accepts what he heard. Then Ken decides on the library regeneration.
- **NO-GO:** anything else. Report which check failed and the smallest change that would fix
  it; do not adjust thresholds to pass.

## Phase 0 record

Run by Opus 5.5 on 2026-11-14, CPU only, library read-only. Scripts in
`plans/backing-vocal-lines/`, output in its `out/`. From the worktree root, in order:

```
P="env PYTHONPATH=. /home/ken/miniconda3/envs/pik/bin/python"; D=plans/backing-vocal-lines; O=$D/out
$P $D/inventory.py ~/pikaraoke-songs $O   # step 1
$P $D/label_sheet.py $O                   # step 2's labelling view
$P $D/labels.py $O                        # step 2's labels, from the lists in labels.py
$P $D/heard.py ~/pikaraoke-songs $O       # steps 3-4, every variant
$P $D/report.py $O                        # A1 / A2 table
$P $D/gate.py ~/pikaraoke-songs $O "consume none" "consume none +consist" "consume none +vocables" "consume none +vocables +consist" "G" "words list v2"   # A3, A4, unsure
$P $D/baseline.py ~/pikaraoke-songs $O    # step 5
$P $D/spec_counts.py ~/pikaraoke-songs $O # build spec counts (Results row 10)
```

Only `out/baseline.json` and `out/songs.json` are committed; the rest of `out/` holds lyric
text (paren and cue texts) and stays local (`.gitignore`).

### Step 1: inventory

Scope: every bundle in `alignment_debug/` with `method_used` `cue_align`: 177 (the library has
grown since 2026-11-11; 234 bundles in all). Seven are `movie_srt` custom sheets
(`.custom.srt`), left out by Decision 4. No edited sheet (`-edited.srt`) exists. The other 170
sheets were found by YouTube ID, or by file name for the 41 songs without one (40 movie cuts
and NSYNC - Paradise). Every one cleans (`clean_cue_texts`, empty cues dropped) to exactly its
bundle's `lyrics.lines`.

A paren group is one `(...)` match after the cleaner's own markup strip (tags, `[brackets]`,
note glyphs), the same pattern `clean_srt_line` deletes. Inline: its cue still has words after
cleaning (a line today). Paren-only: its cue cleans to nothing (dropped today). Window: the
cue's own span on the video clock. Overlap: the window shares more than 0 s with a kept cue's.

| Source | Cue songs | With a paren | Paren groups | Inline (cues) | Paren-only (cues) | Songs with paren-only | Distinct texts |
|---|---|---|---|---|---|---|---|
| captions (`srt`) | 142 | 88 | 434 | 138 (137) | 296 (287) | 81 | 286 |
| LRC (`lrclib_srt`) | 28 | 18 | 192 | 172 (164) | 20 (20) | 7 | 109 |
| all | 170 | 106 | 626 | 310 (301) | 316 (307) | 88 | 391 |

Overlaps: no inline-paren cue overlaps another cue in either source. Two paren-only caption
cues overlap a line: `cPAbx5kgCJo` "(children laughing)" 75.40-77.23 s over line 21 by
1.83 s, and `GC_mV1IpjWA` "(singing)" 126.37-128.53 s over line 50 by 2.17 s. LRC cues end at
the next stamp, so none can overlap.

Not counted: one caption cue with an unbalanced bracket, `D_dOXTpwV5s` "(heeyyy]", which no
paren rule touches today.

### Step 2: labels

Written and committed before step 3 ran: no transcript, bundle word or audio was opened for
them. Each distinct text is labelled once, from the text, its cue and its song. Key: lower
case, every character but letters, digits and apostrophes made a space, spaces collapsed
("(Oh-oh-oh)" and "(oh, oh, oh)" are one key).

- `sung`: words a voice performs in the song at that point, sung or spoken: echoes, answers,
  ad-libs, a chant in another language ("Dies irae"), a spoken line inside the song ("Hang in
  there, Joan!").
- `direction`: anything else, which must never reach the screen: a sound or music, an action,
  a manner of voice ("falsetto", "hums", "vocalizing", "singing", "Bowie voice"), a
  non-verbal noise, and title cards ("\"My Love\"", "\"I Want It That Way\"", and "(Like You
  Used to Do)", the second half of a title card).
- `unsure`: the text cannot say. For Ken at GATE A.

Vocable-only, for the A2 split, fixed here too: every word of the text is one of oh, ohh, ooh,
ah, ahh, uh, mm, mmm, hmm, woo, whoa, la, na, da, ya, yeah, hey, eh, ay, aye, ha. Under this
rule "oh-I-oh-I" and "shamone" are worded.

| Source | sung | direction | unsure | groups |
|---|---|---|---|---|
| captions | 147 | 277 | 10 | 434 |
| LRC | 184 | 0 | 8 | 192 |

**unsure** (4): beep (Eminem - The Real Slim Shady, "so (beep) him": a bleeped word; the audio
may hold a beep, a reversed word or silence) · censored (Tenacious D - Tribute, "the best
(censored) song": the audio may sing the word) · heartbeat (BTS - Butter, "to my beat
(heartbeat)": reads as an echo but names a sound; the plan's own example) · skate (Silk Sonic -
Skate, "skate to me, baby (skate)": reads as an echo; the plan's own example).

**direction** (189): acoustic guitar playing · ad libs · aircraft engine rumbling · applauding
· backstreet boys scream · barking · basketball thudding · bass and drums · beat boxing · bell
rings · birds calling · birds chirping · birds screeching · birds squawking · bowie voice ·
brian screams in horror · brian startles agitatedly · bring it all back by s club 7 · bubbles
popping · camera clicks · car screeches · car screeching · cars humming · cars screeching ·
cars whirring · cd clicks · change clatters · chattering · cheerful music · cheering · children
laughing · chorus sings in foreign language · chuckling · chuffing and squawking · clears
throat · clock ticking · congas playing · creepy music · crowd chanting · crowd chattering ·
crowd cheering · crowd cheering and clapping · crowd yelling · demon cackles · distorted music
· doors creak open · dramatic music · dramatic pop music · dramatic whooshing · drums beating ·
dwayne laughing · electric guitar solo · electricity crackles · elephant trumpeting · energetic
guitar music · energetic rock music · falsetto · feet scraping · fireworks cracking · fist
pounds · flute playing · foot tapping · for good by kristin chenoweth and idina menzel · french
style laugh · genie in a bottle by christina aguilera · gentle bells · gentle guitar music ·
gentle music · gentle music and humming · gentle piano solo · gentle pop music · giggles ·
girls vocalizing · glass shattering · glass tinkling · groans · ground rumbling · grunts softly
· guitar · guitar playing · guitar strumming · haunting organ music · horses neighing · humming
continues · hums · i want it that way · instrumental interlude · intense music · intro beaming
· jack shouts · jack shushing · jack sings in vocalese · jc blowing · jemaine groaning
pleasurably · jemaine whispers · justin laughing · kyle huffs · laughing · laughs · like you
used to do · lisa singing in spanish · lively music · man singing in foreign language ·
melancholy piano music · mouthing · mouthing notes · music continues · music ends · music fades
· music stops · my love · normal voice · pandemonious banter · parrot squawking · passersby
talk indistinctly · passersby talking indistinctly · pencil tapping · phone clicks · phone
ringing · piano music · piano music continues · piano plays slow gentle melody · plane roaring
· pop music playing · purring · radio crackling · record halts · record scratch · record
scratching · relaxing music · relaxing music continues · rhythmic piano solo · roaring
trumpeting · saxophone playing · screen whooshing · seabirds calling · ship humming · shrieks ·
singer vocalizing · singing · singing through vocoder · siren wailing · slow music · slow quiet
electric guitar · slow quiet piano music · slow rock music · sneezes · snorting · snorts · soft
cymbal crash · soft music begins · soft pop music · soft rock music · solemn piano music · song
ends · soothing music · speaking in foreign language · sputtering springing · squawking ·
static buzzing · students running · synth strings and pop beat · synthesized voice · techno
music playing · tempo picks up · thunder crashes · thunder crashing · trumpets buzzing · upbeat
groovy music · upbeat instrumental music · upbeat music · upbeat music continues · upbeat music
playing · upbeat pop music · violin music · violin music continues · vocalizing · voices
distorting · warm rhythmic music · warm rhythmic music continues · waves lapping · whispering ·
whistling · whoosh · wild guitar music · wild guitar music continues · wind whirring ·
wonderboy by tenacious d · words typing and beeping

**sung** (198): a week · ah · ah ah · all alone · all because of you · always · always remember
· and i'm mark i'm mark · and i'm mark i'm mark i'm mark · are you sure · as we go on · baby ·
baby don't stop · baby i'm right here · best i ever had · between you and i · big latto · body
starts to rock · bummer · but i just don't know don't know girl · butter · can't believe it ·
can't love you like i do · come on · come over here baby · come whatever · crazy crazy crazy
crazy · da da da down oh watch me do it yeah ooh · darling oh · dies irae · do you ever wonder
· does he know what you feel · don't need control · don't worry · don't you dare · drip drip ·
erus · eternum · ever wonder why · everything is happening · favilla · gets you high · girl ·
girl i'm tryna give you this · gotta give you back · hang in there joan · help me please help
me please · hercules hercules · here we are · hey · hey girl · hey hey hey · hey ya hey yeah
hey yeah · house clean · how could she do this · how could she do this baby · how could she do
this to me · how it gets you so high baby · how much i loved you baby · huntr x girls to the
world · i · i can be in love but i just don't know don't know girl · i can't stop the feeling ·
i could be in love · i drive myself · i gotta know · i gotta see you baby · i just love your
brain · i know you hear your friends when they say you should · i like the way you look right
now · i need you baby · i wanna get to know ya · i wanna get to know you · i wanna rock your
body · i was wrong · i'd be your shining star yeah · i'll treat you good girl · i'm in love
with your body · i'm sorry · i'm waiting waiting waiting · i'ma leave the door open · i'ma
leave the door open hoping · i'ma tryna ride with you darling · if i had only told you · if you
· illa · in flamas · independent · it's a takedown · it's not goodbye · josé josé josé · just
how good you were to me · just think of me and you · la la la la · la la la la la · let ya body
know · let's bash · listen · listen 'cause i'm · look too good · made a mistake · make my heart
sing · makes me trust ya like i do · maledictus · mm · mmm you smell better than a barbecue ·
my arms around you · my girlfriend · my oh my · nah · never get enough · no no · no there ain't
nothin better than this · no there ain't nothing better than this · now · oh · oh da da da down
· oh da da da down ah · oh da da da down ooh · oh da da da down watch me do it yeah · oh da da
da down yeah yeah yeah yeah yeah · oh i oh i oh i oh i · oh no · oh oh · oh oh oh · oh oh oh oh
· oh oh oh oh oh · oh whoa · oh yeah yeah · oh yes we remember · one in a million ooh · one
things fo sho one things for sho · only one · ooh · ooh ooh ooh · ooh ooh ooh ooh ooh · our
destination · pool warm · purple haze · right here next to you right here next to you · rushing
on · same · say you are · seems hopeless but we know we gotta try · seven days a week ooh ·
shamone · she belong to everybody · she got she got · shut your trap · sip sip · slide your way
on over · smokin out the window of the benzo the benzo · smoking out the window · smooth like a
newborn · so sweet · so tight · stop stop stop · stunner · summer · tell me · tell me that
you're coming through · that girl yes she belong to everybody · that's why i love her · that's
why i love that girl · there ain't nothin better · there ain't nothing better · thing thing ·
this is me yeah · this moment yeah · too soon · toxic · tryna · uh · unless you like · vos
solve in · waiting · wanting you the way that i do · we could do somethin' · we remember · we
will still be friends forever · we're on our own · what you doing · what you smoke · when
you're body starts to rock · when your body starts to rock · where you at · whoa whoa · why ·
why you thinkin' about it mama · with you · woo woo · yeah · yeah she belong to everybody · you
already know · you can't stop · you confessed your love · you got plans · you're the best i
ever had

### Step 3: heard test

The base rule, written before any result:

1. Window: the cue's span moved by the song's fitted display lead (`joint_stats.offset_s`),
   padded 0.5 s each side. A transcript word (`transcribe_words`) is in it when its span
   overlaps.
2. Words: split at spaces, hyphens and slashes, normalised as the matcher does
   (`token_align._normalize_token`), equal or contraction-equal (`_match_simple`). Vocables
   match within a class: oh/ooh/woo/whoa, ah/uh/ha, mm/hmm, yeah/ya, hey/ay/eh, la/na/da.
3. Used-up words: the words of its own cue's line and of every line whose cue overlaps the
   window (one order-keeping match of those lines to the window's words) are taken out first,
   so an echo of its own line is not heard on the lead's words alone.
4. Kept when at least half of its distinct words are among the rest.

Variants, one knob at a time from the base unless named:

- `pad 0`, `pad 1.0`: the pad. `no offset`: the display lead not applied.
- `none`: no words used up, which is the plan's own wording ("its words in
  `transcribe_words` inside its window"; the scripts call it `consume none`). `consume own`:
  only its own line's words used up.
- `vocable exact`: vocables compared as plain words. `tokens>=0.5`: the share counted over
  its words in order, not distinct words. `types all`, `tokens all`: every word required.
- `pad 1.0 none`, `ceiling: none, pad 1.5`, `pad 3.0 none`, `pad 5.0 none`: no words used
  up, wider pads, to find where A1 breaks.
- `G`: words used up by one order-keeping match of the whole song's lines to the whole
  transcript, each line's word only within 1.0 s of its cue (`band`), so a neighbour line
  cannot take an echo's words from the far side of the window. `G ...`: its knobs; `G share>0`
  keeps on any one word.
- `+consist`: the plan's A2 consistency variant (a text kept once in a song is kept at every
  repeat there). `+vocables`: a vocable-only parenthetical (step 2's set) is kept without
  the transcript. Both added after the first table showed A2 short.
- `words list`, `words list v2`, `lyric echo`: step 4.

A1 is labelled directions kept (LRC has none labelled). A2 is labelled-sung kept.

| Rule | A1 captions | A1 LRC | A2 captions vocable | A2 captions worded | A2 LRC vocable | A2 LRC worded | A2 all sung |
|---|---|---|---|---|---|---|---|
| base | 0 | - | 4/22 (18%) | 50/125 (40%) | 6/50 (12%) | 35/134 (26%) | 95/331 (29%) |
| pad 0 | 0 | - | 4/22 (18%) | 55/125 (44%) | 7/50 (14%) | 50/134 (37%) | 116/331 (35%) |
| pad 1.0 | 0 | - | 4/22 (18%) | 51/125 (41%) | 7/50 (14%) | 44/134 (33%) | 106/331 (32%) |
| no offset | 0 | - | 4/22 (18%) | 50/125 (40%) | 6/50 (12%) | 34/134 (25%) | 94/331 (28%) |
| none | 0 | - | 4/22 (18%) | 83/125 (66%) | 8/50 (16%) | 78/134 (58%) | 173/331 (52%) |
| consume own | 0 | - | 4/22 (18%) | 64/125 (51%) | 8/50 (16%) | 54/134 (40%) | 130/331 (39%) |
| vocable exact | 0 | - | 4/22 (18%) | 50/125 (40%) | 5/50 (10%) | 35/134 (26%) | 94/331 (28%) |
| tokens>=0.5 | 0 | - | 3/22 (14%) | 47/125 (38%) | 5/50 (10%) | 32/134 (24%) | 87/331 (26%) |
| types all | 0 | - | 3/22 (14%) | 27/125 (22%) | 6/50 (12%) | 15/134 (11%) | 51/331 (15%) |
| tokens all | 0 | - | 2/22 (9%) | 25/125 (20%) | 4/50 (8%) | 12/134 (9%) | 43/331 (13%) |
| pad 1.0 none | 0 | - | 5/22 (23%) | 86/125 (69%) | 9/50 (18%) | 81/134 (60%) | 181/331 (55%) |
| ceiling: none, pad 1.5 | 0 | - | 5/22 (23%) | 88/125 (70%) | 9/50 (18%) | 82/134 (61%) | 184/331 (56%) |
| pad 3.0 none | 1 | - | 5/22 (23%) | 95/125 (76%) | 9/50 (18%) | 85/134 (63%) | 194/331 (59%) |
| pad 5.0 none | 1 | - | 5/22 (23%) | 97/125 (78%) | 10/50 (20%) | 86/134 (64%) | 198/331 (60%) |
| G | 0 | - | 4/22 (18%) | 52/125 (42%) | 6/50 (12%) | 45/134 (34%) | 107/331 (32%) |
| G pad 0 | 0 | - | 4/22 (18%) | 52/125 (42%) | 6/50 (12%) | 41/134 (31%) | 103/331 (31%) |
| G pad 1.0 | 0 | - | 4/22 (18%) | 52/125 (42%) | 7/50 (14%) | 47/134 (35%) | 110/331 (33%) |
| G band 0.5 | 0 | - | 4/22 (18%) | 55/125 (44%) | 6/50 (12%) | 47/134 (35%) | 112/331 (34%) |
| G band 2.0 | 0 | - | 4/22 (18%) | 51/125 (41%) | 6/50 (12%) | 46/134 (34%) | 107/331 (32%) |
| G no offset | 0 | - | 4/22 (18%) | 53/125 (42%) | 6/50 (12%) | 48/134 (36%) | 111/331 (34%) |
| G vocable exact | 0 | - | 4/22 (18%) | 52/125 (42%) | 5/50 (10%) | 45/134 (34%) | 106/331 (32%) |
| G tokens>=0.5 | 0 | - | 3/22 (14%) | 51/125 (41%) | 5/50 (10%) | 45/134 (34%) | 104/331 (31%) |
| G types all | 0 | - | 3/22 (14%) | 32/125 (26%) | 6/50 (12%) | 25/134 (19%) | 66/331 (20%) |
| G share>0 | 0 | - | 4/22 (18%) | 62/125 (50%) | 6/50 (12%) | 49/134 (37%) | 121/331 (37%) |
| words list | 19 | - | 22/22 (100%) | 125/125 (100%) | 50/50 (100%) | 134/134 (100%) | 331/331 (100%) |
| lyric echo | 33 | - | 22/22 (100%) | 118/125 (94%) | 50/50 (100%) | 123/134 (92%) | 313/331 (95%) |
| words list v2 | 1 | - | 22/22 (100%) | 125/125 (100%) | 50/50 (100%) | 134/134 (100%) | 331/331 (100%) |
| none +vocables | 0 | - | 22/22 (100%) | 83/125 (66%) | 50/50 (100%) | 78/134 (58%) | 233/331 (70%) |
| none +consist | 0 | - | 6/22 (27%) | 95/125 (76%) | 17/50 (34%) | 86/134 (64%) | 204/331 (62%) |
| none +vocables +consist | 0 | - | 22/22 (100%) | 95/125 (76%) | 50/50 (100%) | 86/134 (64%) | 253/331 (76%) |
| pad 1.0 none +vocables | 0 | - | 22/22 (100%) | 86/125 (69%) | 50/50 (100%) | 81/134 (60%) | 239/331 (72%) |
| pad 1.0 none +consist | 0 | - | 7/22 (32%) | 97/125 (78%) | 17/50 (34%) | 88/134 (66%) | 209/331 (63%) |
| pad 1.0 none +vocables +consist | 0 | - | 22/22 (100%) | 97/125 (78%) | 50/50 (100%) | 88/134 (66%) | 257/331 (78%) |
| ceiling: none, pad 1.5 +vocables | 0 | - | 22/22 (100%) | 88/125 (70%) | 50/50 (100%) | 82/134 (61%) | 242/331 (73%) |
| ceiling: none, pad 1.5 +consist | 0 | - | 7/22 (32%) | 98/125 (78%) | 17/50 (34%) | 89/134 (66%) | 211/331 (64%) |
| ceiling: none, pad 1.5 +vocables +consist | 0 | - | 22/22 (100%) | 98/125 (78%) | 50/50 (100%) | 89/134 (66%) | 259/331 (78%) |
| G +vocables | 0 | - | 22/22 (100%) | 52/125 (42%) | 50/50 (100%) | 45/134 (34%) | 169/331 (51%) |
| G +consist | 0 | - | 6/22 (27%) | 69/125 (55%) | 13/50 (26%) | 57/134 (43%) | 145/331 (44%) |
| G +vocables +consist | 0 | - | 22/22 (100%) | 69/125 (55%) | 50/50 (100%) | 57/134 (43%) | 198/331 (60%) |

Directions with any word in the window under `none`: one up to a 1.5 s pad ("upbeat pop
music", one word of three), two at 3.0 s. The first kept is "( Bowie voice )" at a 3.0 s pad,
whose cue goes on to sing "Bowie".

### Step 4: comparison rule

`words list`: a parenthetical is a direction when it opens with a quote mark (a title card)
or has a word from a list of sounds, music, instruments, voice actions and "continues /
ends / fades / begins / stops / halts". The list was written for this step from the kinds of
direction step 2 holds, so its A1 is in-sample. Kept as written: 19 directions ("Backstreet
Boys scream", "Brian startles agitatedly", "JC blowing", "Like You Used to Do", "ad libs",
"birds calling", "demon cackles", "doors creak open", "fireworks cracking", "fist pounds",
"gentle bells", "intro beaming", "record scratch", "record scratching", "seabirds calling",
"sputtering, springing", "students running", "voices distorting", "whistling").

`words list v2`, tightened once: a word added from each of those 18 (scream, startles,
blowing, libs, calling, cackles, creak, cracking, pounds, bells, beaming, scratch,
scratching, sputtering, springing, running, distorting, whistling). Kept: 1 direction,
"(Like You Used to Do)", the second half of a title card; its words are lyric words and the
only one that would catch it is "used". Not run further. No sung text dropped by either list.

`lyric echo` (extra, not the plan's rule): kept when vocable-only or when a word of it is in
the song's own lines. 33 directions kept, including all six quoted title cards.

### GATE A tables

A3, songs where one text is kept in one place and dropped in another:

| Rule | Song-texts split |
|---|---|
| `none` | 16: `1QYBiNRu1ok` "a week" 3/5, `6tpl9LtkRRw` "no there ain't nothing better than this" 2/3, `CEw-7cMnBDY` "skate" 7/8, `FQ3slUz7Jo8` "hey" 1/3, `JGwWNGJdvx8` "oh i oh i oh i oh i" 4/6, NSYNC - Paradise "i" 2/3, `TWZKw_MgUPI` "you can't stop" 1/2, `fGyTN5UjnL4` "now" 1/2, `fGyTN5UjnL4` "yeah" 1/2, `j5itLHDMJsE` "oh da da da down ooh" 1/2, `luotSpkyCVU` "oh oh oh" 5/12, `ru0K8uYEZWw` "i can't stop the feeling" 2/7, `saxnXiBKEaY` "come on" 1/2, `saxnXiBKEaY` "no no" 1/3, `wIyNAsmGrl0` "tell me that you're coming through" 3/6, `wIyNAsmGrl0` "woo woo" 1/2 |
| `none +vocables` | 12 (the above less the four vocable texts) |
| `G` | 15: against `none`, adds `6tpl9LtkRRw` "best i ever had" 2/5, `hj4e709GYf4` "let's bash" 4/10, `GG7fLOmlhYg` "i was wrong" 1/2, `CEw-7cMnBDY` "my oh my" 1/2; lacks NSYNC - Paradise "i", `fGyTN5UjnL4` "now" and "yeah", `j5itLHDMJsE` "oh da da da down ooh", `wIyNAsmGrl0` "woo woo" |
| any `+consist`, `words list v2` | 0 |

A4, paren-only cues kept. "Cue" counts those whose cue window overlaps another line's cue
(Decision 3 read as cue time). "Screen" counts those whose window, moved by the display lead,
overlaps the previous or next line's on-screen time today (`output_line_timings`).

| Rule | Paren-only kept | Overlap by cue | Overlap on screen |
|---|---|---|---|
| `none` | 46 | 0 | 40 |
| `none +consist` | 55 | 0 | 49 |
| `none +vocables` | 48 | 0 | 42 |
| `none +vocables +consist` | 56 | 0 | 50 |
| `G` | 34 | 0 | 29 |
| `words list v2` | 73 | 0 | 65 |

On-screen overlaps under `none +vocables +consist`: 0.0 to 3.8 s; 14 under 1 s, 33 from 1 to
3 s, 3 over 3 s.

Unsure rows, kept of total:

| Text (song) | Rows | `none` | `none +consist` | `none +vocables +consist` | `G` | `words list v2` |
|---|---|---|---|---|---|---|
| beep (`eJO5HU_7_1w`, inline) | 2 | 0 | 0 | 0 | 0 | 2 |
| censored (`_lK4cX5xGiQ`, inline) | 2 | 0 | 0 | 0 | 0 | 2 |
| heartbeat (`WMweEpGlu_U`, inline) | 6 | 0 | 0 | 0 | 0 | 6 |
| skate (`CEw-7cMnBDY`, LRC inline) | 8 | 7 | 8 | 8 | 7 | 8 |

What each candidate keeps, for Phase 2's song count:

| Rule | Groups kept (captions / LRC) | Inline / paren-only | Songs (captions / LRC) |
|---|---|---|---|
| `none` | 180 (87 / 93) | 134 / 46 | 31 (15 / 16) |
| `none +consist` | 212 (101 / 111) | 157 / 55 | 31 (15 / 16) |
| `none +vocables` | 240 (105 / 135) | 192 / 48 | 34 (17 / 17) |
| `none +vocables +consist` | 261 (117 / 144) | 205 / 56 | 34 (17 / 17) |
| `G` | 114 (56 / 58) | 80 / 34 | 24 (11 / 13) |
| `words list v2` | 350 (158 / 192) | 277 / 73 | 39 (21 / 18) |

### Step 5: baseline

Lines covered: every line with a `sung` or `unsure` inline parenthetical (it would gain
words), and every line in the same section as one of those or as a `sung` / `unsure`
paren-only cue (it would be added; its section found by inserting its span after its previous
line, on the bundle's own span clock, and re-sectioning with `segment_by_gaps`). That is a
superset of what every heard-test candidate keeps, since none keeps a labelled direction up
to a 1.5 s pad; `words list v2`'s one kept direction is not covered. Per line it holds the
section, the final start, end and word count
(`output_line_timings`), the final word times (read from the song's `.ass`, 0.01 s), the
section-align word times before any rescue (`cue_inputs.sections`), and the rescue and snap
status (re-aligned, re-paced, guessed words, crammed, widened, onset shift, end extends).
Timings and line ids only, no lyric text: `plans/backing-vocal-lines/out/baseline.json`,
committed.

| Songs (captions / LRC) | Lines covered (of those songs' lines) | Gain words | Mate of a gainer | Mate of an added line | Re-aligned | Re-paced | Guessed-word lines | Crammed | Widened | Onset-snapped | End-extended | Zero-length final words |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 38 (20 / 18) | 1364 (of 2501) | 267 | 1102 | 530 | 204 | 36 | 3 | 283 | 71 | 247 | 480 | 0 |

Checks: recomputed sections equal each bundle's `n_sections` in all 38; every `.ass` has one
line per shown bundle line, first word within 0.01 s of the bundle's line start, in all 38.

The commit: bundles record none. All 38 were written on the Windows GPU box between
2026-11-05T20:36Z and 2026-11-12. Dev's alignment code (`cue_align`, `onset_snap`,
`alignment_capture`, and the cleaners' behaviour) last changed at `2e5d389b`
(2026-11-05T19:42Z); the library regens are recorded at `7bb144d`; nothing on dev after it,
through `a7671d74`, changes alignment behaviour (a docstring, and `_is_all_caps` renamed
`is_all_caps`). If that box ran dev, every baseline bundle was written under alignment code
identical to `7bb144d`. Branch `cue_heard_rescue` (`a24348be`..`f2d305fc`, 2026-11-14, not
on dev) changes the rescue; if it lands first, a Phase 2 replay on the new base will differ
from this baseline on rescued lines, so Phase 2 names its base and diffs before/after on it.

### GATE A read (Opus 5.5, 2026-11-14)

As written, the gate reads **NO-GO**:

- The heard test passes A1 with room: no labelled direction kept in any variant up to a
  1.5 s pad. It fails A2. The plan's own wording (`none`) keeps 52% of sung, 62% with the
  consistency variant: short of 70, though above 40, so not "the wrong test" either. Versions
  that require the backing to be heard apart from the lead keep at most 39% (44% with the
  variant). No transcript-only rule with A1 0 keeps more than 23% of vocables or 61% of LRC
  worded ones (34% and 66% with the variant).
- The comparison rule fails A1: 19 directions as written, 1 after one tightening, and that
  one ("(Like You Used to Do)", a title card made of lyric words) no word list catches
  without listing a lyric word. Its A1 is in-sample besides.

Recommendation: **GO on a hybrid, put to Ken as a choice** (like the fallback; no build spec
until he rules). Worded parentheticals keep the heard test as the plan words it (`none`,
0.5 s pad, display lead applied); vocable-only parentheticals are kept on their text, since
no labelled direction is vocable-only; the consistency variant applies. Measured as
`none +vocables +consist`: A1 0; A2 76% (captions worded 76%, LRC worded 64%, vocables 100%);
A3 0. Without the consistency variant it is 70%, on the bar.

What Ken takes on with it:

- Part of what is kept has no audio evidence: the vocables (72 of 261 groups kept) and the
  repeats the consistency variant adds. B4 at GATE B tests whether the aligner can time them.
- "Heard" credits the lead's own words: "Let's bash (let's bash)" is kept whenever the lead
  was heard. That separates sung from direction, which is the gate's question; it does not
  show the echo itself is audible.
- The first direction to leak as the pad grows is one that names the singer ("Bowie voice"
  at 3.0 s). Quoted title cards had no word heard up to a 3.0 s pad (one did at 5.0 s); a
  build should still drop a quote-opened parenthetical outright, as the word list does.

For Ken to rule, whatever the outcome:

1. The four `unsure` texts: beep (Eminem - The Real Slim Shady), censored (Tenacious D -
   Tribute), heartbeat (BTS - Butter), skate (Silk Sonic - Skate). The heard test drops the
   first three every time and keeps skate 8 of 8.
2. What "overlap" means in Decision 3. By cue time it drops none of the 56 paren-only cues
   kept. By today's on-screen time it drops 50 of 56, and that half of the feature is close
   to empty. Keeping them by cue time puts two lines on screen together where there was one,
   which B5 forbids as written.
3. The hybrid, or NO-GO.

### GATE A second read (Fable 5.2, 2026-11-14)

Read-only, on `feb71bc4`: the tables above, plus counts taken from the saved `out/heard.json`,
`out/baseline.json` and the bundles' `output_line_timings`. Nothing re-run, no label changed.

**1. The hybrid: GO, as Ken amending the gate, not as the gate passing.** The first read's
"as written NO-GO" stands, and so does putting it to Ken as a choice.

- A1, the part meant to be rigid, is not bent: zero in every transcript variant up to three
  times the pad, and only one direction has any word in its window at all.
- What moves is A2, which is a worth-building bar ("set without data; Ken may move them"). A
  miss on A2 leaves a line exactly as it is today.
- Keeping vocables on text is a second change the gate did not register, but not a fitted
  one: the vocable set was fixed in step 2 before any result, and the plan asked for vocables
  apart because transcribers skip them. Open edge: "ha" is in the set, so a laugh written
  "(ha ha)" would be kept; no such text is in this library.
- The transcript is tested on worded parentheticals only: 161/259 (62%), 181/259 (70%) with
  the registered consistency variant; captions 76%, LRC 64%. The 76% headline includes 72
  vocable groups that pass by definition. "On the bar", not over it.
- `none` was chosen from 39 variants after the results. It is the plan's own wording and A1
  is zero for all of them, so the choice affects A2 only.

Not shown by GATE A, and so carried to GATE B:

- A1 on LRC. No LRC parenthetical is labelled a direction; the zero rests on captions alone
  (277 groups, 189 texts).
- That an echo can be heard. Under `none` the lead's words count for it.
- The 261 kept, by evidence:

| Evidence | Kept | Inline | Paren-only |
|---|---|---|---|
| heard (`none`) | 180 | 134 | 46 |
| vocable-only, kept on text, not heard | 60 | 58 | 2 |
| added by consistency | 21 | 13 | 8 |

Conditions on the GO: the rule is frozen as measured (no further pad or share tuning); a
quote-opened parenthetical is dropped outright; Phase 2 reports B2-B4 split by the three
evidence rows, so the 81 without audio evidence can be dropped at GATE B on their own.

**2. Decision 3: the on-screen count is not a fair measure of overlap.**
`output_line_timings` run from a line's first word start to its last word end, as aligned
today without the parenthetical's words. Of the 50 counted under
`none +vocables +consist`:

| | Count |
|---|---|
| overlap the previous line | 43 |
| ... previous line covers 80% or more of the paren-only window | 27 |
| ... previous line covers half or more | 37 |
| ... previous line has an end-extension record (`baseline.json`) | 41 |
| overlap the next line only | 7 |
| largest overlap under 0.5 s | 8 |

In most of them the previous line's words run across the whole slot: that audio had no words
of its own, so the line before was stretched over it. The count mostly measures the
parenthetical's absence, not two voices at once. Whether a kept line truly overlaps can only
be measured in Phase 2, on timings aligned with the line present. Read Decision 3 by cue time
at GATE A (drops 0 of 56) and judge on-screen overlap at GATE B. That has a cost there: those
previous lines' ends will move by seconds, so B2 will list them, and B5 must compare
after-timings, not before-timings.

If Ken holds to today's on-screen time: inline-only keeps 205 of 261 groups (79%) in 30 of
the 34 songs (captions 14, LRC 16; 11 songs hold 150 of them, 8 songs hold one each). Still
worth building, at the same scale as the whole feature (30 of 170 cue songs): inline is most
of what is kept and nearly all of the build spec's open points, and dropping paren-only
removes line insertion, section placement, Decision 3 and B5's two-lines check. Paren-only
could follow as its own step.

### GATE A ruling (Ken, 2026-11-14)

1. **GO on the amended hybrid**, with the second read's conditions: worded parentheticals on
   the heard test as the plan words it (`none`, 0.5 s pad, display lead applied),
   vocable-only kept on text, the consistency variant; the rule frozen as measured; a
   quote-opened parenthetical dropped outright; Phase 2 reports B2-B4 split by evidence
   (heard, vocable on text, added by consistency).
2. **Decision 3's overlap is cue time** when a paren-only line is chosen. On-screen overlap is
   judged at GATE B on timings aligned with the line present. B2 will list the previous
   lines whose ends move; B5 is amended above.
3. **The four `unsure` texts:**

| Text | Ken | Ruled | The hybrid does |
|---|---|---|---|
| beep | covers an explicit lyric | not shown | drops 2 of 2 |
| censored | covers an explicit lyric | not shown | drops 2 of 2 |
| heartbeat | not in the Genius lyrics for Butter | not shown (read as: not a sung line) | drops 6 of 6 |
| skate | a background chant, worth keeping where it is heard | sung | keeps 8 of 8 (7 heard, 1 by consistency) |

The rule already does what each ruling asks, so no label file or script output was changed;
`labels.json` still holds the four as `unsure`. With them counted, A1 stays 0.

## Results log

Raw tables, commands and commits only; no verdicts in this table.

| # | date | phase | what ran (command, commit) | raw result |
|---|---|---|---|---|
| 1 | 2026-11-14 | 0.1 | `inventory.py ~/pikaraoke-songs out` on `8701174c`, library read-only | 170 cue songs read (7 custom left out), all sheets match their bundles; 626 paren groups, 391 distinct texts. "Phase 0 record", "Step 1". |
| 2 | 2026-11-14 | 0.2 | `labels.py out` (labels written by hand from `out/label_sheet.txt`: text, cue, song; no transcript) | 391 keys: 198 sung, 189 direction, 4 unsure; groups: captions 147 / 277 / 10, LRC 184 / 0 / 8. "Phase 0 record", "Step 2". |
| 3 | 2026-11-14 | 0.3 | `heard.py ~/pikaraoke-songs out`, `report.py out`, `gate.py ~/pikaraoke-songs out <rules>` on `5818d634` (labels committed first) | 39 rule variants scored; A1 0 for every heard-test variant up to a 1.5 s pad, 1 at 3.0 and 5.0 s; A2 13-56% with the transcript alone up to 1.5 s (59-60% at 3.0-5.0 s), 44-64% with the consistency variant, 51-78% with vocables kept on text. "Phase 0 record", "Step 3", "GATE A tables". |
| 4 | 2026-11-14 | 0.4 | same run | `words list` A1 19, A2 100%; `words list v2` A1 1, A2 100%; `lyric echo` A1 33, A2 95%. "Step 4". |
| 5 | 2026-11-14 | 0.5 | `baseline.py ~/pikaraoke-songs out` | 38 songs, 1364 lines; sections and `.ass` words match every bundle; bundles captured 2026-11-05T20:36Z..2026-11-12, after dev's last alignment change `2e5d389b`; regens recorded at `7bb144d`. "Step 5". |
| 6 | 2026-11-14 | GATE A | Read by Opus 5.5 | As written NO-GO; recommended GO on the hybrid (`none +vocables +consist`: A1 0, A2 76%), for Ken to rule with the four `unsure` labels and Decision 3's "overlap". "GATE A read". |
| 7 | 2026-11-14 | 0 (record) | Scripts moved from the session scratch folder into `plans/backing-vocal-lines/` (dead imports dropped, Black, docstrings; `label_sheet.py` added for the step 2 view, which had been an inline snippet); the whole run above repeated from there on `a54f8e6f` | Every output byte-identical to rows 1-5's: `songs.json`, `inventory.json`, `label_sheet.txt`, `labels.json`, `heard.json`, `baseline.json`, the A1 / A2 table and the A3 / A4 / unsure output. |
| 8 | 2026-11-14 | GATE A | Second read by Fable 5.2 on `feb71bc4`, read-only: inline counts over `out/heard.json`, `out/baseline.json` and the bundles' `output_line_timings` (no script re-run, no label changed) | Worded sung kept 161/259 under `none`, 181/259 with `+consist`. Hybrid's 261 kept: heard 180 (134 inline / 46 paren-only), vocable on text 60 (58 / 2), consistency 21 (13 / 8); 34 songs, 30 with an inline keep. Of the 50 on-screen overlaps: 43 with the previous line (27 covering 80% or more of the window, 37 half or more, 41 end-extended), 7 next line only, 8 under 0.5 s. Recommended GO on the hybrid as an amended gate, Decision 3 read by cue time. "GATE A second read". |
| 9 | 2026-11-14 | GATE A | Ruled by Ken | GO on the amended hybrid with the second read's conditions; Decision 3 overlap by cue time, on-screen overlap judged at GATE B (B5 amended); beep, censored, heartbeat not shown, skate sung. No script re-run. "GATE A ruling". |
| 10 | 2026-11-14 | spec | `spec_counts.py ~/pikaraoke-songs out` on `b2f914be`, read-only over `out/heard.json`, `out/songs.json`, the sheets and the bundles | 261 kept by `none +vocables +consist`, 0 of them quote-opened. Cues mixing a kept and a dropped group: 4 (`FQ3slUz7Jo8` paren-only; `wIyNAsmGrl0` three inline). Inline keeps by position in the cue: end 181, start 18, middle 6; glued to a neighbour 4, all a comma after `)`. Kept paren-only cues 56; re-sectioned with each one: joins one section 22, own section 2, merges two 31, two more sections 1 (`D_dOXTpwV5s`, a run captioned with no gap, whose 60 s cap splits move); kept paren-only cues overlapping each other 0. Songs with a keep 34, re-sectioned 0. Evidence: heard 180, vocable 60, consistency 21. "Design". |
