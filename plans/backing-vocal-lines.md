# Backing vocals in parentheses: show the sung ones on caption and LRC songs

Model: Claude Opus 5.5 runs Phase 0, judges both gates and writes the build spec.
Claude Sonnet 5.5 builds from that spec. (High-level spec by Claude Fable 5.2, 2026-11-11.)
GATE B is read by Claude Fable 5.2 while it is available (to 2026-11-16), Opus 5.5 after
(Ken, 2026-11-15, "Rulings for Fable's window" under GATE B).

**Status: GATE A ruled GO on the amended hybrid, 2026-11-14 ("GATE A ruling"). Build spec
written 2026-11-14 ("Build spec": Design, Commits) and read by Fable 5.2 the same day ("Build
spec read") and ruled by Ken ("Build spec ruling"). Stage 1 built 2026-11-14: C0-C3 and C2p
on this branch (Results rows 13 and 14). The D7 amendment was written 2026-11-15 after GATE H
of `cue_heard_rescue` was ruled ("The D7 amendment", Results row 15), with two rulings by Ken
the same day: an added line is timed by the rescue's own one-line retry, and stage 2's base is
`dev` merged into this branch. GATE B's reader and Phase 2's size were ruled 2026-11-15 for
Fable's window (Results row 16). Stage 2 built 2026-11-15 (Sonnet 5.5): C0s, C4-C7 (Results
row 17). Reviewed 2026-11-15 and its findings fixed in `87d24ee2`, the rest logged in
`plans/open-issues.md` (Results row 19). Phase 2 ran 2026-11-15 on the full set (Results rows
18 and 20); its report is `out/phase2_report.md`, local. GATE B read by Fable 5.2 on
2026-11-15 after Ken's listen ("GATE B read", Results row 21): NO-GO as built, GO after one
change and two rulings. Ruled by Ken the same day ("GATE B ruling", Results row 22): all
three taken, the fix specced for Sonnet 5.5. Spot 1 heard again 2026-11-16 ("Spot 1 heard
again", Results row 23): the fix stands, one line logged. The fix was built as `705099db` and
the one song replayed 2026-11-16 (Results row 24). GATE B is GO, 2026-11-16 ("GATE B
call", Results row 25): line 91 sits on its cue. Next, on Ken's word: the landing on `dev`;
the library regen is the single full one after `onset_loud_start` has landed too. The
pipeline now calls `judge`: a caption or LRCLIB song shows the backing vocals the
transcriber heard, so a regenerated song changes; Genius and custom songs show their
parentheses (C3).**

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
2. **[Not built. Replaced 2026-11-15: "The D7 amendment", D7.2.]** The song is re-sectioned
   on the new lines' spans (shifted as before when it re-sectioned) by the same gap rule:
   a new line is a cue like any other. Of the 56 paren-only lines kept,
   22 join one of today's sections, 2 make their own, 31 bridge a gap and merge two of today's
   sections, and 1 (`D_dOXTpwV5s`, a run captioned with no gap) moves where the 60 s cap splits
   its run. Step 5's baseline counted "mate of an added line" the same way.
3. **[Not built. Replaced 2026-11-15: "The D7 amendment", D7.3.]** A section whose window and
   text both equal one already aligned in this call reuses that align's words;
   the rest go to the aligner. One dict keyed by `(t0, t1, text)` over the
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

**[Replaced 2026-11-15: "The D7 amendment", "What this guarantees at GATE B".]** What this
guarantees at GATE B: an old line can move only if it gained words, sits in a
section that went back to the aligner, or is directly before or after a changed or added line
(the singing-end search, the start bound, the guessed-word bounds, the repeat runs and both
edge snaps look one line over). B2's three groups are then: gained words; near a change (the
other two); all other lines, which must be identical. "Near a change" is wider than the
plan's "section-mates" (choice 4): the ruling expects the line before a paren-only line to
move, and for 31 of the 56 that line is in another of today's sections.

**D8. A kept parenthetical the aligner cannot time is shown with the rescue's timing,** as any
lyric word is (its counts, and how the landed rescue words it: "The D7 amendment", D8):
a gainer's untimed echo words are guessed at its pace; a paren-only line left
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
- **[Replaced 2026-11-15: "The D7 amendment", "Landing order".]** `cue_heard_rescue` (stopped
  at 3b2) passes the same `heard_words` to `align_song` and turns
  the rescue into a class that fits its lead when built; the pinned lead goes there. Its rules
  look for a line where the transcriber heard its words, and an echo's words are its lead's,
  so a new line could be aimed onto the lead's audio. If both are on Phase 2's base, report
  heard-aimed moves of new lines on their own.
- `onset_loud_start` changes the `snap_line_edges` call; `show_parens` runs after it. Its new
  onset exit moves a line with a loud start when the transcriber heard the line's first word
  within 0.25 s of a later rise. That touches this feature's lines in three ways (Fable 5.2,
  2026-11-15, read from the code, not measured):
  - A line that starts with a kept group whose next word is the same word ("(hey) Hey you")
    can have its start moved up against the lead's word, agreed by the lead's heard copy. An
    added line placed on top of its lead can move the same way. If that branch is on Phase 2's
    base, report on their own the heard-moved lines
    (`joint_stats.edge_snap.onset.heard_snaps`) that are added lines or lines whose kept group
    has `tokens` starting at 0.
  - An added line the transcriber never heard, with a loud claimed start (the lead's held
    note), is never moved by that exit. It is searched only when its start is quiet or its
    `source` is a doubted one (`cue_align_line`). The D7 amendment says which `source` an
    added line's own-window align carries, and why. **[Answered 2026-11-15: "The D7
    amendment", "The onset snap". There is no own-window align.]**
  - Its Phase 3 regen bumps the schema to 12, so every bundle is stale. If this branch is on
    the regen's base, that regen adds backing lines to every affected song, ahead of GATE B's
    regen decision (Decision 4), and its read has to split cue songs by a kept group in
    `joint_stats.backing`. As cut, `onset_loud_start` does not hold this branch.

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

- [x] **C0. Anchors** (no commit). Confirm these exist as D1-D9 use them:
  `srt_cues.clean_cue_texts`, `_clean_cue`, `is_all_caps`, `_recase_line`,
  `cue_spans_from_srt`; `genius_lyrics._strip_markup`, `_PAREN_CONTENT_RE`, `clean_srt_line`,
  `parse_lyric_lines`; `cue_align.align_song`, `segment_by_gaps`, `split_section_to_lines`,
  `repace_bad_lines`, `fit_offset`; `joint_match._tokenise_lines`;
  `token_align._normalize_token`, `_match_simple`; `LyricAlignStage.run`, `_load_lyrics`,
  `_run_cue_align`, `_write_debug_capture`; `library_regen.LRC_ORIGIN`, `MOVIE_ORIGIN`;
  `word_edit.edited_srt`. And that neither `lrclib_fit_pick` Phase 4 nor `cue_heard_rescue`
  is on `dev`; if one is, STOP ("Landing order").
- [x] **C1. `feat(lyrics): read a cue sheet's parentheticals and where each sits in its
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
- [x] **C2. `feat(cue_align): which parentheticals were sung, by the GATE A rule`.** D5:
  `backing_vocals.py` with `ORIGINS`, the copied constants, `Verdict` and `judge`. Tests in a
  new `tests/unit/test_backing_vocals.py`, made-up words: a share of exactly 0.5 kept, under it
  dropped; a word ending exactly where the padded window starts is out; the lead shifts the
  window; a vocable heard as another of its class; a vocable-only group kept with an empty
  transcript; consistency keeps an unheard repeat of a heard text; a heard quote-opened group
  is dropped and keeps no repeat; an echo heard only on its line's own words is kept; overlap
  with one of today's lines and with an earlier kept paren-only cue; a later cue overlapping
  only a dropped one is kept; `unplaced`; `ORIGINS` holds `srt` and `library_regen.LRC_ORIGIN`
  and not `MOVIE_ORIGIN`.
- [x] **C2p. Parity on the library, read-only.** New `plans/backing-vocal-lines/parity.py
  ~/pikaraoke-songs plans/backing-vocal-lines/out`: for every song in `songs.json` not
  skipped, read its sheet as the stage does (UTF-8), run `sheet_parens`, then `judge` with the
  bundle's `transcribe_words`, its `joint_stats.offset_s` (or 0.0) and the sheet's line spans.
  Against `out/heard.json`: the same 626 groups by (song, cue, group), none extra; kept exactly
  where `consume none +vocables +consist` kept, less any `unplaced` (each listed); 180 `heard`,
  60 `vocable`, 21 `consistency`; no `quote` or `overlap` among them. Any other difference is a
  STOP. Commit the script and a Results log row as `docs(plans): backing-vocal-lines parity of
  the built rule with Phase 0`.
- [x] **C3. `feat(lyrics): karaoke words keep their parentheses`.** D9: `show_parens`, and
  the stage calls it in alignment mode before `_generate_ass`. On its own this changes the word
  text of Genius and custom songs with parens (Decision 2), never their timing. Tests: a
  Genius-shaped line ("(I can't help) Falling", words I, can't, help, Falling) shows "(I",
  "can't", "help)", "Falling" with every start and end unchanged; lone "(" and ")" tokens; a
  word the aligner dropped; "oh (oh)"; a line whose text equals its align text untouched, stray
  paren included; an interp line with no words; a line that does not pair. In
  `test_lyric_align.py`: the joint route's ASS carries "(I" at unchanged times; transcribe mode
  does not go through it.
- [x] **C0s. Stage 2's base and its anchors** (a merge commit; no code of this plan's). Only
  after Phase 5 of `cue_heard_rescue` has landed on `dev`; if it has not, STOP. `git merge
  dev` in this worktree (Ken's ruling, "The D7 amendment"). Conflicts are expected only
  where both sides edited the same lines of `lyric_align.py` (stage 1's `show_parens` call,
  the rescue's `heard_words`), each resolved by keeping both; any other conflict is a STOP.
  Then the full suite, which must pass before C4. Confirm on the merged tree, as the
  amendment uses them: `cue_align._Rescue` (its `__init__` fits `self.offset` with
  `fit_offset`; `process`, `is_placed`, `confirmed`, `window`, `can_realign`, `heard_shift`,
  `heard_aimed_line`, `retry`, `realigned_line`, `start_bounded`), `repace_bad_lines(...,
  heard_words=)`, `align_song(..., heard_words=)` returning three items,
  `_guess_missing_words`, `_start_bound`, `_lead_in_bound`, `_line_from_realigned`,
  `_repace_line`, `_line_object`, `SOURCE_REALIGN`, `SOURCE_FILL`, `HEARD_SHIFT_S`;
  `heard_lines.heard_lines`, `runs_heard`, `confirms`; the stats keys
  `heard_kept_line_ids`, `heard_aimed_line_ids`, `heard_aimed_kept_line_ids`,
  `guard_lifted_line_ids`, `n_heard_lines`; `_run_cue_align` passes the gate's words as
  `heard_words`; the stage calls `snap_line_edges(...,
  doubted_sources=frozenset({SOURCE_REALIGN}))` before `show_parens`. And that none of
  these is there: `process_whole`, `whole_shift` (rule D), `gap_retry_line`, `free_stretch`
  (rule C), `heard_held_line_ids` (A2). One present means the base is not the ruled set:
  STOP. And that neither `lrclib_fit_pick` Phase 4 nor `onset_loud_start` is on `dev`; if
  one is, STOP ("Landing order").
- [x] **C4. `feat(cue_align): kept backing vocals join the song's lines and are timed with
  them`.** D6, and D7 as amended: `with_backing`; `align_song`'s `parens` keyword, the
  sections with a gaining line sent back, the renumbering, each added line handed to the
  rescue with no words, the pinned lead, the fourth return item, `joint_stats.backing` and
  `cue_inputs.rescue_offset`; `repace_bad_lines(offset=...)` through to `_Rescue`; the
  `alignment_capture` header; `SOURCE_REALIGN`'s comment (an added backing line's retry
  carries it too). No rescue rule changes. Tests in `test_cue_align.py` with a stub aligner
  that logs its calls:
  - no parens, `heard_words=None`, or nothing kept: the same calls and output as a call
    without the keyword, and the fourth item is the inputs;
  - an inline keep: one more section call, on its section's unchanged window with the echo
    words bare in the text; the other sections' line objects equal the first pass's;
  - a paren-only keep between two lines of one section: no section call beyond today's, and
    one one-line call for the new line, its bare words over its cue plus the lead padded by
    `pad_s`; the line's `text` is "(oh, oh)", its words bare, its source `cue_align_line`;
    the lines after it are renumbered with words and times unchanged;
  - a paren-only keep in the gap between two sections: both keep their windows and their
    line objects (no merge);
  - the aligner gives nothing for the added line: paced across its cue plus the lead,
    `cue_align_fill`;
  - its re-align starts before the previous line's last word: cut to start there;
  - an added line heard 2 s before its cue with its first word matched: the first one-line
    call is aimed there (rule B), and `heard_aimed_line_ids` carries its new id;
  - a one-word added line with the same word heard 2 s away: no heard-aimed call;
  - the rescue's lead is today's when the re-aligned gaining section alone would move it
    (the stub realign of an unchanged rescued line gets today's window);
  - a re-sectioned song: the added line's span is shifted with the others;
  - `old_line_ids`, `aligned_sections`, `tokens`, `cue_inputs.sections` (the added line
    with no words), `rescue_offset`, the returned lines.

  `repace_bad_lines`: a given `offset` is used and not fitted; None fits as today. In
  `test_backing_vocals.py`: `with_backing` at a line's start, middle and end, two groups, a
  paren-only line before a line and after the last. Existing `align_song` tests: call shape
  only.
- [x] **C5. `feat(pipeline): caption and LRC songs show the backing vocals they sing`.** D3,
  D7.5: in `run`, on the cue route with an origin in `ORIGINS`, `sheet_parens` of the sheet
  `_load_lyrics` read; `_run_cue_align` takes them, passes them to `align_song` beside the
  gate's words it already passes, and hands back the timed lines. The bundle records those
  lines and `show_parens` reads them, not the sheet's: with a keep the line ids differ.
  `_load_lyrics` is unchanged. Tests in `test_lyric_align.py`, workers mocked as there: a
  caption sheet with a paren-only echo and an inline echo the mocked transcript hears gives
  a bundle whose `lyrics.lines` hold both, `output_line_timings` ids that match them, and
  ASS words "(oh," on both the gaining line and the added one; the same sheet as
  `movie_srt`, and an edited caption sheet (cleaned lines), are timed as today; an
  `lrclib_srt` sheet takes the same path as the caption; the joint route gets no parens.
- [x] **C6. `docs(plans): open issues for backing vocal lines`**, in `plans/open-issues.md`
  (this one lands). Under "Cue align windows": on "Repeated tokens get two assignment rules",
  that an echo line repeats its lead's words within one line, so the in-order guess can put an
  echo's timing on the lead's token, now a common case, watched at GATE B (B3, B4); on "Duet
  ending", that a paren-only line after the last caption becomes the song's last line and takes
  the uncapped tail window. New, under a heading for this feature: Edit words drops a song's
  backing lines on save (choice 3); Repair's LRCLIB list scores and counts "mapped N of M"
  against the lines the song shows (`current_lines`), backing lines now included; Song Info
  counts an added line among the re-aligned or paced lines, and a paced one toward the 15%
  guessed share (`library_status._cue_fields`), so a song can read as poor from new lines
  alone; the rescue's rule B can aim an added line at another copy of its words, its lead's
  included ("The D7 amendment").
- [x] **C7. Finish.** Full suite; pre-commit on the changed files; self-review on the three
  axes; `graphify update .`; Results log row. **STOP: review due** (core pipeline, several
  files). Hand Ken the line; do not launch it: `/code-review <C1>~1..HEAD` on `srt_cues.py`,
  `genius_lyrics.py`, `backing_vocals.py`, `cue_align.py`, `lyric_align.py`,
  `alignment_capture.py` and their tests, three finders: correctness (nothing kept gives
  today's calls and output; a section with no gaining line is never re-made; no rescue rule
  changed; `judge` is heard.py's rule),
  simplicity (one rule, one reader, no second cleaner, no handling for states that cannot
  occur), robustness (stray and glued parens, capitals files, window edges, re-sectioned songs,
  an empty transcript). Phase 2 follows the review.

#### Build spec read (Fable 5.2, 2026-11-14)

A read of Design and Commits on `2dc30b7a`, not a rewrite: nothing above is edited. Checked
against `dev` `1016e20` (`cue_align.py`, `onset_snap.py`, `srt_cues.py`, `genius_lyrics.py`,
`word_edit.py`, the align stage), `cue_heard_rescue` at `81d0d0bc` (`cue_align.py`,
`heard_lines.py`, the stage) and `lrclib_fit_pick` at `e8bd6994` (its plan, "Phases 4-6").
Counts are from `read_counts.py` (Results row 11), read-only, no GPU. Each point is **keep**,
**change** (with the smallest edit) or **ask Ken**. Sonnet builds from Design and Commits as
amended by Ken's rulings on this list.

| # | Point | Verdict |
|---|---|---|
| 1 | D1, the keep step inside `align_song` after the first `fit_offset` | keep |
| 2 | D1 / D2, after the LRCLIB pick | keep |
| 3 | D3, no sheet changes | keep |
| 4 | D7.2, a paren-only line re-sections the song | ask Ken (choice 1, now three options) |
| 5 | D7.3, the section memo | keep |
| 6 | D7.4, the pinned rescue lead | keep |
| 7 | D7, "an old line can move only if..." and B2's zero | change, and ask Ken (choice 4) |
| 8 | Landing order, `cue_heard_rescue` | change; ask Ken on the build order |
| 9 | D8, coverage on old words | keep: not now |
| 10 | D4, `at` | keep, one case added |
| 11 | D5 against `heard.py` | keep, one order fixed |
| 12 | Choices 2 and 3 | keep |

**1. D1: keep.** The transcript exists before `align_song` and the lead only after its first
pass; no earlier place has both. `joint_stats.offset_s` is the first `fit_offset`, the value
Phase 0 used. On a song that did not re-section, the rescue's own fit is the same call on the
same inputs, so the lead D7.1 pins is that same number. `judge` and `with_backing` are pure, so
`align_song` stays drivable by a stub aligner.

**2. After the pick: keep.** `lrclib_fit_pick` 4d calls `_dereverb_gate` once in `run`, runs
the check on a song that would go joint, writes the picked sheet to `ctx.tmp_dir`, loads it
with `_load_lyrics` and runs the cue route. Its frozen list names `clean_cue_texts` and
`clean_srt_line`; D2 leaves both alone. The keep step sits inside the cue route, so it is after
the pick on any landing order. C5 reads the parentheticals from `lyrics_path`, which on a pick
is the tmp sheet: correct, and the "Landing order" note already says so.

**3. D3: keep.** The cleaner is unchanged, so `word_edit.edited_srt`'s check and "a cleaned
line cleans to itself" hold with no edit. One consequence to know, no change asked: on a song
with a keep the bundle's `lyrics.lines` are no longer the sheet's cleaned lines. Its readers
are Repair's custom-lyrics box (`LibraryTools.custom_start` prefills from them, so a typed
sheet started there carries the backing lines in parentheses, timed by the Genius parser),
`current_lines` (C6 covers it) and the history list. None compares them to the sheet.

**4. D7.2: ask Ken.** The 56 paren-only lines are where most of the avoidable re-timing comes
from. Old lines that go back to the aligner without gaining a word, over the 34 songs (2167
old lines, 202 gain words):

| Placement of a kept paren-only cue | Back to the aligner, not gaining | Beside a change only | All other lines |
|---|---|---|---|
| A, the spec: re-section, the new line is a cue | 1170 | 5 | 790 |
| B, choice 1's alternative: joins the nearer section, never merges | 944 | 14 | 1007 |
| C, new: aligned in a window of its own, today's sections stay | 809 | 48 | 1108 |

The 809 are section-mates of the 202 gaining lines and are the same under all three. A adds
361 old lines for 56 new ones (10 of them with no audio evidence). Seven songs carry most of
it (A / C): `68LBPvFhMx0` 53 / 2, `wGyh_53ecgg` 37 / 4, `6q0JnftlH-I` 36 / 0, `JGwWNGJdvx8`
63 / 13, `D_dOXTpwV5s` 59 / 23, `ru0K8uYEZWw` 72 / 30, `PodgxWsZw9s` 60 / 27.

- A is the least code and is what the route does with any sung cue. Re-aligning the line
  before with the echo's words present may be the better timing where the aligner put that
  line's last words on the echo. It is also the most old lines for Ken's ear to vouch for.
- C: today's sections are kept and renumbered; each added line is one aligner call over its
  cue span, padded as a section's is and clamped at the midpoints to its neighbours' cues. No
  old line is re-aligned for a paren-only line. The line before still gives up the slot: the
  end snap stops a line's last word at the next line's first word
  (`onset_snap.snap_line_ends`, `line_bound`), and 41 of the 43 previous-line overlaps in the
  second read have an end-extension record. Costs: about 20 lines more than A; the new line is
  timed without its lead's text beside it; the 7 next-line overlaps are not helped and go to
  B5. D7.3 then needs no dict (a section is re-aligned when it holds a gaining line) and the
  `D_dOXTpwV5s` cap-split case goes away.

Recommendation: C, because Decision 1 ranks old timing over new lines and C exposes 361 fewer
old lines for the same 56. A is right if Ken would rather the echo and its lead be timed
together and accepts the longer B2 list. B is between and has neither's argument.

**5. D7.3: keep.** Section windows are rounded to 3 dp, so the key is exact. It makes a reused
section identical inside one call. B1 and B2 compare two runs, so they also rest on the aligner
giving the same words twice for the same slice, which no step here checks; B1 is the first
place it would show. One-line re-aligns are outside the memo and are asked for again.

**6. D7.4: keep.** The pinned value is right (point 1). On `cue_heard_rescue` it goes in
`_Rescue.__init__` (`self.offset`), where it also puts the cue spans on the audio clock for the
heard-line match.

**7. "An old line can move only if...": change.** The three cases are not every way. Reading
the rescue:

- On `dev`: a re-aligned line's start bound is the previous line's *result* (`_start_bound`
  reads `previous["end"]`), and guessed words are bounded by the neighbours' results. So a
  change passes down a run of consecutive rescued lines: line 2 from a change can move when
  line 1 did. The repeat-run slack, the singing-end search and both snaps do stop one line
  over, as D7 says.
- On `cue_heard_rescue`, three more reach past the neighbour. `heard_lines` is one match of
  the transcriber's words to every token in the song, and an echo's words are its lead's, so
  new tokens can re-deal heard words among repeats some lines away, which flips rule A1, A2, B
  or D for a line nothing else touched. `runs_heard` is decided per run of identical lines: a
  run of four with its second line gaining words becomes three runs, and line 4 is judged
  differently. `free_stretch` reads the next line the first pass left clean and the last
  non-fill line, either of which can be several lines off.

Smallest edit: D7's paragraph says "is expected to move only if", and names the chain. B2
(Ken's text, choice 4): the middle group is "in a section that went back to the aligner, or
directly before or after a changed or added line"; "all other lines" is expected to show zero
moves, and each move there is listed with the rescue step that changed, not stopped on as a
bug. B1 stays the bug check. If Phase 2 shows more than a handful, the change to try is to run
the rescue on the touched lines only and copy today's result for the rest; not now, because
the rescue's stats and the offline replay would then need the copied lines' results too.

**8. Landing order, `cue_heard_rescue`: change.** Its status is stale: not stopped at 3b2 but
through 4c at `81d0d0bc`, waiting on Ken's listening and GATE H. The `heard_words` keyword and
the class are as the note says. The risk it names is real and a little wider:

- Rule B aims a bad or partial new line at where its words were heard, and rule D moves a
  complete, placed one. For an echo the transcriber did not hear on its own, the words heard
  are its lead's.
- A re-align the transcriber confirms is freed from the previous line's end (`start_bounded`),
  the one guard that would keep an echo off its lead.
- The other way round: an echo's tokens can take the lead's heard words, leaving the lead
  unheard and without rules A1 and A2.

Smallest edit: the note's last sentence becomes "report, for new lines, every heard-aimed and
whole-aimed keep, and for old lines every change in heard or confirmed status". Ask Ken on the
order: C1, C2, C2p and C3 do not touch the rescue; C4 and C5 do, and `cue_heard_rescue`
rewrote it (`cue_align.py`: 604 lines added, 149 removed against `dev`). Recommendation: build C1-C3 on `dev` now and hold C4
until GATE H is ruled, so C4 is written once on the rescue that ships.

**9. D8: keep, coverage on old words not now.** Worst case, the aligner times no echo word:

| Gaining lines | All | Echo heard | No audio evidence | Mixed |
|---|---|---|---|---|
| Timed by today's section align | 192 | 131 | 60 | 1 |
| ...under the bar if no echo word is timed | 30 | 27 | 3 | 0 |
| Empty after today's section align (rescued today) | 10 | | | |

The vocables are not where the bar bites: they sit on leads long enough to carry them, 3 lines
excepted. The 30 are lines whose echo is longer than the lead, 27 of them heard, and 13 of the
30 clear the bar on one echo word. For those lines a bar on old words alone would keep a
one-word lead and guess five echo words after it, which is not plainly better than the
re-align it replaces. It is also a rescue change, which "Not doing" rules out. Smallest edit:
D8 carries the count, and Phase 2 reports these 30 lines by id under B3. What the 60 vocable
groups risk is B4 (guessed, not timed), which the evidence split already shows.

**10. D4, `at`: keep.** Cleaning the text before the group, then checking today's line starts
with those tokens, catches the glued case and follows the cue cleaner's label and capitals
decisions. One case it gets wrong: text before the group with no letter in it ("1, 2 (hey)
go") cleans to nothing, so `at` is 0 and passes the check, and the echo lands before "1, 2".
Smallest edit: such a group's `at` is None (`unplaced`); one test in C1. None of the 205
inline keeps has it.

**11. D5 against `heard.py`: keep.** Line by line it is `consume none`: the window and its
overlap test, the split at spaces, hyphens and slashes, distinct words, the class match tried
before `_match_simple`, 0.5 inclusive, the vocable test on the step 2 set (not the classes),
consistency by song and label key, the bundle's `offset_s` or 0.0. The quote drop and the two
step 5 drops are additions the 261 do not meet. One order to fix: "no word once normalised" is
written last, but `all()` over no words is true, so step 3 would keep such a group as a
vocable. Smallest edit: that test comes first; one test in C2. None of the 626 groups has it.
Phase 0 read sheets as `utf-8-sig` and the stage reads `utf-8`; C2p will show any sheet where
that matters.

**12. The four choices.**

1. Point 4: A, B or C.
2. Custom typed sheets show their parens: keep. Same parser as Genius, same Decision 2; an
   origin check would be a difference nobody asked for.
3. Saving a word edit drops the backing lines: keep, with C6's entry. It is Decision 4 read
   plainly, and the alternative is its own feature.
4. Point 7: B2's middle group as worded there, and "all other lines" listed, not stopped on.

**For Ken to rule:** point 4 (A, B or C; recommended C), point 7 (B2's wording), point 8 (C1-C3
now and C4 after GATE H, or all on `dev` now). Points 10 and 11 are two one-line edits Sonnet
takes with the spec unless Ken objects.

#### Build spec ruling (Ken, 2026-11-14)

All three recommendations of the read ratified. Where this and Design or Commits disagree,
this wins.

1. **Point 4: option C.** A kept paren-only line is aligned in a window of its own and
   today's sections stay. Choice 1 is closed. D7.2 and D7.3 as written (re-section, the memo)
   are not built; they are rewritten for C in the D7 amendment below.
2. **Point 7: B2 amended** in "GATE B" above. D7's "an old line can move only if" reads "is
   expected to move only if". The rescue on touched lines only is not built; it is the change
   to try if Phase 2's "all other lines" list is long.
3. **Point 8: two stages.**
   - **Stage 1, now, on `dev`'s code:** C0, C1, C2, C2p, C3, then the full suite, pre-commit
     on the changed files, `graphify update .` and a Results log row. STOP there. The review
     waits for C7 and covers both stages.
   - **Stage 2, after GATE H of `cue_heard_rescue` is ruled:** the D7 amendment (Fable 5.2,
     Opus 5.5 if not available), then C4-C7 (Sonnet 5.5) on the rescue that ships.
4. **Points 10 and 11, taken into stage 1.** D4 / C1: a group with text before it that holds
   no letter has `at` None; one test ("1, 2 (hey) go"). D5 / C2: a group with no word once
   normalised is `not_heard` before the vocable test is tried; one test.
5. **Choices 2 and 3 stand** as the spec made them. D8 stands; Phase 2 reports the 30 lines of
   point 9 by id under B3.

**The D7 amendment (stage 2, before C4).** A plan edit, no code: D7.2 and D7.3 for option C
(today's sections kept and renumbered; one aligner call per added line over its cue span,
padded as a section's and clamped at the midpoints to its neighbours' cues; a section goes
back to the aligner only when it holds a gaining line), D7's guarantee paragraph, D8's count,
"Landing order" for where `cue_heard_rescue` then stands (point 8's reporting sentence), C4's
and C5's tests to match, and C0's anchors on the new base.

#### The D7 amendment (Fable 5.2, 2026-11-15)

The plan edit the ruling asks for. Where this and Design, Commits or the ruling above
disagree, this wins. Read on `de695678` (this branch, stage 1) against `cue_heard_rescue` at
`ac87c180`: `cue_align.py`, `heard_lines.py`, `onset_snap.py`, the align stage, and that
plan's "Rulings" and "Phase 5". Counts are from `amend_counts.py` (Results row 15),
read-only, no GPU. Design's D7.2, D7.3, guarantee paragraph, D8 and two "Landing order"
bullets are marked where they stand and replaced here. In "Commits", C0s is new, C4 and C5
are rewritten in place (stage 1's text of them is in `de695678`), C6 gains two entries and
C7's correctness finder follows D7.3.

**The base.** GATE H of `cue_heard_rescue` was ruled 2026-11-15. Landing: rule A1 (a line
the transcriber confirms counts as placed), the guard lift (a confirmed re-align is not cut
to the previous line's end), rule B (a retry aimed where the line was heard) and the
zero-length words. A2 is cut; D and C are left out. That set is in no tree yet: the branch
still holds all seven, and its Phase 5 removes three while landing. Everything below is
written for the landed set, and C4 cannot start until it is on `dev` (C0s).

**Two rulings (Ken, 2026-11-15, by question dialog).**

1. **An added line is timed by the rescue's own one-line retry**, not by a window built like
   a section's. This replaces one clause of the ruling above ("padded as a section's and
   clamped at the midpoints to its neighbours' cues"). The rest of option C stands: today's
   sections are kept, no old line is re-aligned for a paren-only line, and a section goes
   back to the aligner only when it holds a gaining line.
2. **Stage 2's base is a merge.** Once Phase 5 has landed, `dev` is merged into this branch.
   Stage 1's hashes stay as cited, and the merge commit never lands (landing copies code
   commits one by one).

Why ruling 1: the clamp leaves the window ruled on 2026-11-14 with no padding, because these
cues are captioned back to back with their neighbours. "The echo's start" is its cue start
plus the song's rescue lead.

| Of the 56 kept paren-only cues (18 songs) | Count |
|---|---|
| Cue touches the cue before / the cue after | 43 / 39 |
| Under 0.5 s to the cue before / after | 55 / 46 |
| A section-style pad clamped under 0.25 s, before / after | 55 / 46 |
| On raw cues, that window opens after the singing starts (the song's lead is larger than the pad) | 54 |
| Today's first pass ends the line before past the echo's start, by more than 0 / 0.25 / 0.5 / 1.0 s | 27 / 15 / 9 / 3 (of 55 with words) |
| Today's first pass starts the line after before the echo's end, by more than 0 / 0.25 / 0.5 / 1.0 s | 18 / 15 / 9 / 5 |
| Words in the line: 1 / 2 / 3 or more | 7 / 3 / 46 |
| Evidence: heard / vocable on text / consistency | 46 / 2 / 8 |
| Text equals a neighbouring line's / is the end of the line before | 6 / 9 |

The 18 songs' leads run from -0.713 to +0.198 s, median -0.296; 10 are over 0.25 s either
way. A section can align on raw cues because its edges sit in a gap with 0.75 s of pad; a
one-line window between touching cues has neither. The rescue's window is the one built and
measured for that case (`archive/cue_align_windows`): on the audio clock, 0.75 s each side,
out to where the singing stops, with the start held off the previous line. Point 4's "the
line before still gives up the slot" is also only part true: for 27 of 55 the line before
ends inside the echo's time before any snap runs, and the end snap only extends.

**D7, the header.** On the base `align_song` and `repace_bad_lines` already take
`heard_words`; C4 adds `parens: list[ParenCue] = ()` only. D7.1 and D7.5 stand as written.

**D7.2 for option C: an added line joins the lines with no words, and the rescue times it.**
Today's sections are the shipping pass's (D7.1): the same lines, the same windows. A kept
paren-only cue is in none of them and makes no aligner call of its own. `with_backing` (D6)
puts it in the song's lines at its cue's span (shifted as the others were when the song
re-sectioned), and it enters `repace_bad_lines` as a line object with no words, which is
what the section pass gives any line it could not time. The rescue then does what it does
for such a line ("How the rescue treats an added line" below), and the line comes out
re-aligned (`cue_align_line`) or paced across its cue (`cue_align_fill`), never dropped.

**D7.3 for option C: only a section with a gaining line goes back to the aligner.** One
call per such section: the shipping pass's window, the section's lines with the kept words
in (bare), split by `split_section_to_lines` on the new texts. Every other section keeps the
shipping pass's line objects, so they are identical because nothing re-made them, and there
is no memo dict. A `Section` is a run of consecutive line ids and an added line can sit
inside one, so the sections are worked in today's ids (a gaining line keeps its id) and the
line objects are renumbered to the new ids afterwards: `line_id` only, words and times
untouched.

**D7.4, where the pinned lead goes.** `repace_bad_lines(offset: float | None = None)` hands
it to `_Rescue.__init__`, which sets `self.offset` from it when given and fits it as today
when None. That one value then puts the cue spans on the audio clock for the windows, the
singing-end search and the heard-line match, as point 6 said. The pin is still needed under
C: a re-aligned gaining section can change which lines are clean enough to fit the lead on.

**Recorded** (replaces D7's list where they differ). `joint_stats.backing` as D7 has it.
`aligned_sections` is the new-id `[lid_lo, lid_hi]` of each of today's sections sent back;
an added line inside that range is not in the section, and `old_line_ids` (None) marks it.
`cue_inputs.sections` holds the lines the rescue was given, in new ids, each added line
with no words. `cue_inputs.realigns` records an added line's retries as it records any, so
its windows and the aligner's raw words need no new key. `cue_inputs.rescue_offset` is the
pinned lead as the exact float. The log line adds the sections sent back.

**How the rescue treats an added line** (read from `_Rescue.process` and what it calls).

- It has no words, so it is never placed, rule A1 has nothing to confirm, and it always
  reaches the retry.
- **Rule B comes first** when the whole-song match (`heard_lines`) hears the line (two or
  more words in the line, at least two and at least half of them matched), its first word
  is among the matched, any run of identical lines it sits in was heard in full, and the
  heard start is 1.5 s or more from its cue start plus the lead. The retry is aimed at the
  cue span moved to the heard start (window, singing-end search, aimed span, start bound),
  and kept only when it lies in the moved span and the transcriber confirms it. If not, the
  cue-aimed retry runs as if B had not.
  - The judge and this match are two different tests. The judge kept the line on what was
    heard in its own cue window (46), on its text (2) or on a repeat elsewhere (8), and
    lets the lead's words count. The match deals each heard word to one token over the
    whole song. So an echo's words can go to its lead, and the echo is then not heard and B
    never fires; or the echo's tokens can take a copy heard somewhere else, a spare repeat
    or its lead's words when the lead's tokens matched another copy.
  - A B keep therefore puts an added line 1.5 s or more from its cue, on audio the judge
    never tested, and for an echo that audio is most likely its lead's or a chorus repeat's.
    This is the shape of Bring It All Back 52 in GATE H's read, reached through B.
  - No exemption is built: ruling point 8 is "report", and "Not doing" leaves the rescue's
    rules as they are. If Phase 2 shows a B keep on an added line that lands on another
    line's words, the GATE B change is that an added line is never heard-aimed, since it was
    kept on the evidence of its own cue window.
- **The cue-aimed retry**: one align of the line's bare words over its cue span plus the
  lead, 0.75 s each side, out to where its singing stops. The first word is cut to start no
  earlier than 0.5 s before the cue plus lead and no earlier than the previous line's last
  word (unless that line is a fill), and the re-align is refused when under
  `INSTANT_WORD_DUR_S` of the first word is left. It is kept when at least half its words
  are timed and it lies inside its span. For the 27 lines whose line before already ends
  inside the echo (as today's first pass has it), the echo starts that much late, or is
  refused when its first word ends before the bound.
- **The guard lift** applies on either retry: a re-align the transcriber confirms as the
  aligner returned it is not cut to the previous line's end, only to the lead-in. Confirmed
  means within 1.0 s, and the lead-in is 0.75 s, so a first word dragged back onto the
  lead's held note still agrees. A heard echo can therefore start up to 0.5 s before its cue
  plus lead, under its lead's last word. GATE H ruled that as two lines sharing a held note;
  here it is an echo starting on its lead, and it shows at B5.
- **A one-word line (7 of 56) is never a heard line**: no rule B, no lift, the cue-aimed
  retry with the full start bound.
- **Else it is paced** across its cue plus lead (`cue_align_fill`). A kept re-align missing
  some words gets them guessed inside its window, between its neighbours' words.
- **Rule D is not on the base.** Nothing moves a complete, placed line, so the "whole-aimed"
  half of point 8's sentence is void. If D is ever revisited it has to be read against
  echoes first: its three wrong moves at GATE H were this kind.

What changes for lines that are not added:

- **A gaining line** is heard, confirmed and aimed on its new tokens. A long echo the
  transcriber missed can take it under half matched, so it stops being a heard line and
  loses A1, B and the lift; an echo the transcriber heard makes it easier to confirm. A
  line that starts with a kept group has its "first word heard" test on the echo's word.
  The 30 lines of point 9 are the ones most likely to reach the retry, and so rule B.
- **Any old line**, through the one match: new tokens can re-deal heard words among repeats
  some lines away, which flips A1, B or the lift for a line nothing else touched. A gaining
  line leaves a run of identical lines, and an added line can make one (6 of 56 have a
  neighbour's text): the neighbour's placed test then demands it sit inside its cue, and
  its confirmation needs the echo heard too.

**The onset snap: an added line is a doubted start, with no new code.** A re-aligned added
line carries `cue_align_line`, as every one-line re-align does, and the stage already
passes that source as doubted, so its first word is always searched for a later rise and
moved forward to it, never back. The doubt's stated reason (the window opens before the
caption, and a loud claimed start is usually the previous line's held note) is the echo's
case exactly: 43 of 56 cues touch the cue before, and the second read found the line before
end-extended across the echo for 41 of 43.

- Why it matters to old lines: `snap_line_ends` stops the previous line's last word 0.1 s
  before the next line's first word, and onsets run first. An echo start left on its lead's
  note cuts the lead's end extension off there. A doubted start can only move later, so the
  lead's last word gets the same room or more. Decision 1 ranks that over the new line.
- The cost falls on new lines only: the doubted search skips the "already on time" test, so
  a short first echo word followed by a pause can be snapped to the next word's rise.
- A paced added line (`cue_align_fill`) is not doubted, as no fill is: its start is its cue.
- Neither snap changes ("Not doing"). If the moved echo starts sound wrong at GATE B, the
  change to try is a source of its own for added lines, left out of the doubted set.

**What this guarantees at GATE B** (replaces D7's paragraph). An old line's first-pass words
are today's unless its section went back to the aligner. After that an old line is expected
to move only if:

1. it gained words;
2. it shares a section with a line that did;
3. it is directly before or after a gaining or added line. What looks one line over: the
   singing-end search (it reads the next line's cue, now perhaps an echo's), the start
   bound and the guessed-word bounds (the neighbours' results), the repeat-run slack and
   placed test (the neighbours' text), and both edge snaps. The line before an added line
   is the designed case: its last word may no longer extend across the echo;
4. it follows such a line down a run of consecutive rescued lines, each bounded by the
   result of the one before;
5. the heard match dealt its words differently, or its run of identical lines changed (the
   two bullets above). This can reach some lines away.

The pinned lead closes the one other path. Rules A2, D and C are not on the base, so the
free-stretch reach point 7 named is gone with C. B2's groups are as amended in "GATE B":
gained words (202 lines); in a section that went back, or directly before or after a
changed or added line (809 and 48); all other lines (1108 of the 2167), expected to show
zero moves, each move listed with the rescue step that changed. Cases 4 and 5 land in "all
other lines" and are why that list is read, not stopped on.

**D8, with its counts** (D8 stands; this adds the numbers and the base's wording).

- Gaining lines, from point 9 and the same under any placement: 192 of the 202 are timed by
  today's section align (echo heard 131, no audio evidence 60, mixed 1); 30 of those fall
  under the half-the-tokens bar if no echo word is timed (27 / 3 / 0; 13 clear it on one
  echo word, 12 on two, 5 need three or more); 10 are empty after today's section align
  and rescued today. A gaining line that comes back empty goes to the retry with its lead
  words: rule B first where it applies, the cue-aimed retry, then paced. Phase 2 reports
  the 30 by id under B3.
- Added lines: all 56 are timed by the retry or paced, as above. Expect the paced ones
  among the 9 whose line before ends more than 0.5 s into the echo and the 7 one-word
  lines. B4 counts a paced line's words as not measured, so the added lines are reported
  apart from the inline words; if B4 fails on them alone, the change is the plan's own:
  drop a paren-only line the retry could not time.
- Song Info counts an added line like any other: re-aligned, or paced, and a paced line is
  a guessed line toward the 15% "looks poor" share. That is true of the line, but it is a
  flag an old song can gain from new lines alone (C6).

**For Phase 2** (adds to Design's note). "Before" is `dev` with the rescue landed; "after"
is the build on it, so both hold rules A1 and B and the lift, and none of this is
conditional. Report:

- Every added line: how it ended (re-aligned at its cue, heard-aimed and kept, paced), its
  guessed words, each retry's window and raw words from `cue_inputs.realigns`, whether the
  guard lift freed it, whether its start was cut to the previous line's end, its overlap
  with each neighbour on the after timings (B5), and the onset snap's shift if it moved.
- Every heard-aimed try and keep on an added or gaining line, on its own, with the shift
  and what other line's words sit at the place it was aimed.
- Every old line whose membership changed in `heard_kept_line_ids`,
  `heard_aimed_line_ids`, `heard_aimed_kept_line_ids` or `guard_lifted_line_ids` (ids
  through `old_line_ids`), and every old line whose heard status changed. The bundle keeps
  only a count of heard lines, so the status is recomputed for both bundles with
  `heard_lines.heard_lines` and `runs_heard` from `lyrics.align_lines`, `cue_inputs.spans`
  plus the lead, and `transcribe_words`. Each is listed with its B2 group.
- The line before each added line: its last word's end before and after.
- B4 split into inline echo words and added-line words.
- Songs whose guessed-line share crosses 15% between before and after.

**Landing order** (replaces the `cue_heard_rescue` bullet; the other two stand).

- `cue_heard_rescue`: GATE H ruled 2026-11-15, Phase 5 (its landing) open. Stage 2 is built
  on what lands, by merging `dev` into this branch afterwards (C0s). If Phase 5 lands a
  different set than ruled, C0s stops and this amendment is re-read.
- `onset_loud_start`, the second sub-bullet's open sentence: an added line's `source` is
  the rescue's, `cue_align_line` or `cue_align_fill` ("The onset snap" above). A re-aligned
  added line is doubted and always searched; a paced one is searched only when its start is
  quiet. The first and third sub-bullets stand.

**Choices made here that Ken may overrule.**

1. An added line gets no source of its own and is doubted with every re-aligned line ("The
   onset snap").
2. Rule B is left able to aim an added line, and reported (point 8 as ruled). The
   alternative, never heard-aiming an added line, is a rescue change.
3. A paced added line is shown and counts toward Song Info's guessed lines (D8).

### Phase 2: replay (after the build, local GPU, output outside the library)

Replay before and after on the same commit base, writing bundles and `.ass` files to a
scratch folder, never into `~/pikaraoke-songs`. Songs: every cue song where the rule keeps at
least one parenthetical if the run time allows; otherwise at least 20, chosen by a stated
rule that covers captions and LRC, inline and paren-only, and the cue-align test songs that
are affected. Add the 8 songs of "The B6 sample" (Ken, 2026-11-15, under GATE B), for B6. Add
5 cue songs with no parentheticals as a control: their output must not change at all.

### GATE B: is it detrimental to timing? (Opus judges B1-B6, Ken's ear rules)

**Rulings for Fable's window (Ken, 2026-11-15).** Fable 5.2 is available until Monday night
2026-11-16, and this gate is the one the build order spends that window reaching.

- **Reader:** Fable 5.2 reads B1-B6 in place of Opus if the Phase 2 report is ready
  before Fable's window closes. After that, Opus 5.5 reads it as written. Ken's ear rules
  either way. His listen can follow the read after Fable's window has closed.
- **Phase 2's size:** "if the run time allows" means the replay, before and after, has
  finished by the morning of 2026-11-16. If every affected cue song would not finish by
  then, Phase 2 takes the floor: at least 20 songs by the stated rule, plus the B6 sample
  and the 5 controls (B1). The executor states the choice and the reason in the Results row.
- **The library regen** that a GO leads to is the single full regen from `dev` after
  `cue_heard_rescue`, `onset_loud_start` and this branch have all landed, not one of its
  own (`cue_heard_rescue` Phase 5 ruling, same day).
- **B6 is sampled** (Ken, 2026-11-15, after the executor prompt's size count: the 34 cue songs
  with a keep, 43 joint-route songs with a "(" in a lyric line and 5 controls, 82 songs and 164
  GPU runs). The plan's "every Genius-route song whose sheet has parens" is replaced by "The
  B6 sample" below, which sizes Phase 2 at 47 songs (94 runs), or 33 (66 runs) at the floor.
  The reason: this branch changes only a joint-route word's text (C3, `show_parens`), never
  a time, so what B6 needs is each shape of line `show_parens` has to pair, not every song.

**The B6 sample.** Drawn from the 43 live joint-route songs in `~/pikaraoke-songs/alignment_debug/`
whose bundle's `lyrics.lines` hold a "(" (42 Genius, 1 custom; the `backups/` and
`regen_backups/` folders are not songs). The rule: every line shape that occurs gets at least
two songs where two exist, plus the custom song (Decision 2 / choice 2), the one non-English
sheet, and the paren-heaviest. Shapes are read from the lyric lines: a group at the line's
trailing end, its start, its middle, the whole line, two or more groups, a group at both ends
(lead+trail), a group glued to a word, and an unbalanced paren. Bundle names, with what each
brings:

| Song (`alignment_debug/<name>.json`) | Origin | Audio | Shapes |
|---|---|---|---|
| `Bruno Mars, Anderson .Paak, Silk Sonic - After Last Night w_ Thundercat & Bootsy [Official Audio]----cy_tDQPXHk` | genius | 250 s | every shape; the only live unbalanced paren |
| `The Lonely Island - I'm On A Boat (Explicit Version) ft. T-Pain (Official Video)---avaSdC0QOUM` | genius | 184 s | glued, two or more, leading, whole line |
| `Bruno Mars - Grenade (Official Music Video)---SR6iYWJxHqs` | genius | 221 s | leading 9, trailing 9, middle 3 |
| `YOLO (feat. Adam Levine & Kendrick Lamar)---z5Otla5157c` | genius | 194 s | glued, middle 3, whole line |
| `Queen - Don't Stop Me Now (Official Video Remastered 4K)---HgzGwKwLmgM` | genius | 215 s | leading 8, two or more, lead+trail |
| `Justin Timberlake - SexyBack (Official HD Video) ft. Timbaland---3gOHvDP_vCs` | genius | 266 s | the most paren lines (71) |
| `Jay Chou 周杰倫 - 晴天 (Sunny Day)---DYptgVvkVLQ` | genius | 318 s | the non-English sheet, leading |
| `Ed Sheeran & Rudimental - Bloodstream---Orq_75kFi8I` | custom | 247 s | the custom sheet |

About 32 minutes of audio, run twice. A song in the sample that is gone from the library when
Phase 2 starts is replaced by the next song with its shape, named in the Results row.

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
  listening list. Amended 2026-11-14 ("Build spec ruling"): the middle group is lines in a
  section that went back to the aligner, or directly before or after a changed or added line.
  "All other lines" is expected to show zero moves; each move there is listed with the rescue
  step that changed, not stopped on as a bug. B1 stays the bug check.
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
  differs. Over the B6 sample (Ken, 2026-11-15).

**Listening list for Ken:** at most 10 spots, each with song, time, what changed and by how
much, drawn from B2's largest moves first, then a spread of new inline and new paren-only
lines. Written so he can check each in under a minute.

- **GO:** B1, B5, B6 pass outright, B2-B4 pass or every exception is on the list, and Ken
  accepts what he heard. Then Ken decides on the library regeneration.
- **NO-GO:** anything else. Report which check failed and the smallest change that would fix
  it; do not adjust thresholds to pass.

#### GATE B read (Fable 5.2, 2026-11-15)

Read on `21c28fb2` against Results row 20 (`out/phase2_report.md`, `out/phase2_details.json`)
and the before/after `.ass` files and bundles in `~/probes/backing_vocal_lines_phase2/`.
Counts beyond the report's are in Results row 21. Ken's listen came first and is recorded
here as given.

**Ken's listen (the report's 10 spots).**

| # | Spot | What it was | Ken |
|---|---|---|---|
| 1 | Takedown 2:43 | old line moved 6.9 s (middle) | too busy to hear the background clearly |
| 2 | Best Part Of Me 3:42 | old line moved 6.5 s (middle) | before overlapped and swallowed the last line as an earlier repeat; after times it properly |
| 3 | Leave the Door Open 2:17 | old line moved 5.9 s (gained) | after timed properly |
| 4 | Drive Myself Crazy 3:54 | old word's end 5.7 s earlier (middle) | before timed properly, after ends early |
| 5 | Smokin Out The Window 2:08 | heard-aimed gaining line | echo is there, timed roughly correctly |
| 6 | Can't Stop The Feeling 3:33 | heard-aimed added line | sung twice, after shows both at the same time; before preferable, cleaner |
| 7 | Because Of You 2:36 | heard-aimed gaining line | after timed correctly |
| 8 | Smokin Out The Window 0:21 | added line, re-aligned | there, timed correctly |
| 9 | Can't Stop The Feeling 1:32 | added line, paced | repeated faintly, timed correctly |
| 10 | Butter 2:38 | inline `(yeah)` | there, and in the line after as well (the after run shows it on both) |

**The checks.**

- **B1 passes.** 5 of 5 controls identical.
- **B6 passes.** 8 of 8 songs, every time equal, 286 text changes, all parentheses.
- **B2, all other lines: zero moves** in 1129 lines, so there is no move to read one by one.
  Cases 4 and 5 of "What this guarantees" did not occur outside the gained and middle
  groups: all 91 old lines whose rescue-list membership or heard status changed are gained
  (62) or middle (29).
- **B2, gained and middle: 565 old words in 331 lines moved over 0.3 s; the ear has 4 of
  them.** The transcript was used as a second referee, for starts only (it has no usable
  word ends): each line's old words against the words heard for that line in the before
  bundle's whole-song match, before and after. 262 of the 331 lines are comparable. After is
  nearer by over 0.3 s on 18, before is nearer on 9, 235 are the same within 0.3 s. On moves
  over 1 s, lines within 1.0 s of where they were heard: gained 39 of 45 before and after;
  middle 52 of 60 before, 57 after. Takedown (spot 1): the line moved from 6.6 s off its
  heard words to 1.0 s off.
- **The two kinds of move that are the design, not drift.** 65 old lines have a last word
  ending over 1 s earlier. 31 are the line before an added line (the echo takes the time the
  held word was stretched across; spot 8 is one) and 30 are a line whose own echo now takes
  that time. 4 have no echo to explain them: Drive Myself Crazy 63 (spot 4), Takedown 50
  (the re-placed line), I Just Might 47 and Leave the Door Open 55, each about 1.1 s.
- **Spot 4, why.** Two lines of that section gained an echo, so the section went back to the
  aligner (D7.3). It returned the last line's last word half a second later and 0.15 s long,
  and the end snap, which before had stretched that word 5.6 s to the note's release, did
  not fire. No echo is near it. This is what re-aligning a section costs its other lines;
  the same re-align is what fixed spots 1 and 2.
- **B3: increases, listed, explained by kind only.** 127 old lines carry an increase (86
  gained, 41 middle). 39 newly hold a guessed old word (21 gained, 18 middle; 29 of them
  with the lead words squeezed short), 9 no longer do: 241 to 271. Paced old lines fell 45
  to 39. No song crosses the 15% share.
- **B4 fails as written: 74.0% against 80%.** Inline echo words pass alone (82.3%). Added
  lines are 55.8%, because 23 of the 56 are paced and a paced word counts as not measured.
  Of those 23, 2 hit an aligner error, 18 had a retry that returned words and was refused
  because its first word fell inside the previous line's last word, and 3 had a retry that
  started in bounds and was not kept. A paced added line sits on its caption cue. Against the words heard in the cue window, a re-aligned added
  line is within 0.5 s on 22 of 26 and a paced one on 8 of 18, but an echo that repeats its
  lead pairs with the lead's words, so this undercounts (spot 9 scores 1.06 s and Ken heard
  it as correct).
- **B5, directions: passes.** 253 kept groups labelled sung, 8 unsure, all 8 `(skate)`,
  ruled sung at GATE A.
- **B5, two lines on screen: fails as worded.** 26 old pairs and 106 pairs with an added
  line overlap in display windows; the windows carry a 1 s pre-roll, and 1872 of 2133
  adjacent pairs overlapped before. In sung time: 26 old pairs overlap by 0.3 s more than
  before (three over 1.2 s: Because Of You 38/39, which is spot 7; Can't Stop The Feeling
  86/87, spot 6's side effect; Takedown 48/49), and 31 pairs with an added line overlap by
  over 0.3 s, 6 by over 1 s, 3 of those 6 from spot 6.
- **Spot 6 is the case the amendment named.** Added line 91 was kept on a repeat elsewhere
  (consistency; nothing heard in its own cue window, the transcript is empty from 3:25 to
  3:33). Rule B moved it 4.3 s onto the next copy, which added line 93 already holds. The
  old line before it then had its last word stretched 3.9 s across the gap and its first two
  words guessed. The two heard-aimed gaining lines (spots 5 and 7) were heard as right.

**Not heard yet, and the data says after is worse.**

- Leave the Door Open 3:46, old line 53 "for you". After: `(Tell me that you're coming
  through) for you`, the group kept on a repeat elsewhere and placed first, "for you" 1.6 s
  later than before. The transcript hears "for you" where before had it and no "tell me"
  there.
- Best Part Of Me 3:05, added line `(With you)`: the aligner errored on its retry, so it is
  paced across a 10.5 s cue. Heard at 3:05.9; "you)" lights at 3:11.7.

**Recommendation: NO-GO as built; GO after one change and two rulings.**

1. **Build the amendment's own change: an added line is never heard-aimed.** It removes spot
   6 and its side effect on the line before. Rule B tried exactly one added line in the 47
   songs, so only Can't Stop The Feeling changes; replay that one song and check line 91
   lands on its cue.
2. **Ruling on B4: keep paced added lines, and count B4 on inline words.** The plan's named
   remedy is to drop them, which removes 23 of 56 added lines, among them spot 9, heard as
   correct. A paced added line is on its caption cue, the timing this route already trusts.
   Dropping is the other option, and it is the one that passes B4 as written.
3. **Ruling on spot 4: accept it.** A held last word lost with no echo involved happens on
   3 lines in 34 songs, and there is no small fix: the alternative is to keep every
   non-gaining line's old words when its section is re-aligned, which also gives back spots
   1 and 2. Log it in `plans/open-issues.md` against the end snap.

The two unheard spots above are Ken's to listen to before he rules. If the first is worse,
the change to consider is not keeping a group on consistency alone when it leads its line
(1 such line found worse; 13 inline groups are kept on consistency).

#### GATE B ruling (Ken, 2026-11-15)

"I take the recommendations." All three, as the read words them:

1. **Build "an added line is never heard-aimed"**, replay `ru0K8uYEZWw` alone, check line 91
   sits on its cue ("The fix" below).
2. **B4: paced added lines are kept, and B4 is counted on inline words** (82.3%, passes).
3. **Spot 4 is accepted** and logged in `plans/open-issues.md` (done with this ruling).

**Ken's listen of the two spots the read left for him**, as given:

| Spot | Ken |
|---|---|
| Best Part Of Me 3:05, added line `(With you)`, paced across a 10.5 s cue | the line is actually "with you, yeah, oooooooo ooooooooo wooooaahhh"; after covers it correctly length-wise with "with you" |
| Leave the Door Open 3:46, old line 53 `(Tell me that you're coming through) for you` | the timing of "for you" is roughly correct, though "I'd have prefer 'tell me that you're coming through' to not split that line in" |

Neither is a NO-GO. The second is read here (Fable's reading, not Ken's words) as a
preference against that group joining the line, with no change asked for; it is logged in
`plans/open-issues.md` with the read's candidate change, and nothing is built for it.

**GATE B is GO once the replay below shows line 91 on its cue.** If it does not, stop and
report; do not adjust anything to make it pass. The library regen stays the single full
regen of "Rulings for Fable's window".

##### Spot 1 heard again (Ken, 2026-11-16)

Spot 1 was "too busy to hear the background clearly" at the listen. Ken went back to
Takedown from 2:35 and, as given: "'ima take it down' is quite early (it actually starts at
2:46), but ends on time. the other lines have early onsets but roughly right". Asked whether
that changes the fix.

**It does not: the fix and its check below stand as written.** The fix touches added lines
only and Takedown has none (4 kept groups, all inline). Read-only over the Phase 2 bundles,
logs and `.ass` files (Results row 23):

| Line (new id) | Cue | Heard | Before | After |
|---|---|---|---|---|
| 48 `It's a takedown` | 2:43.5 | "It's" 2:41.8-2:43.3, "a takedown" 2:43.3-2:44.1 | 2:41.3-2:44.3 | the same |
| 49 `I'ma take it down` + `(oh, da-da-da, down, ooh)` | 2:46.4 | 2:45.5-2:47.7 ("take" at 2:46.7) | 2:42.0-2:42.9 | lead 2:42.0-2:42.5, echo to 2:47.1 |
| 50 `It's a takedown` (spot 1) | 2:50.3 | "It's" 2:49.2-2:50.1, "a" 2:50.1 | 2:42.9-2:53.0 | "It's" 2:47.2, "a takedown" 2:50.1-2:51.2 |
| 51 `Take it down` | 2:53.4 | "it" 2:52.3-2:54.0, "down" 2:54.0-2:54.6 | "Take" 2:53.1, ends 2:54.9 | "Take" 2:51.2, ends 2:54.9 |

- **Line 49 is as early before as after**, so the branch did not move it: the first pass
  puts it 4.3 s before its cue on both sides, its words come back clean, and a clean line is
  trusted outside its cue span. The transcript hears it on its cue, under 1.5 s from the cue
  start, so rule B has nothing to look for. Before, the line gets no retry at all.
- **After, the line gets a retry and the retry is refused.** With the echo joined, the
  first pass returns "it" and "down" without a duration, so the line asks for a re-align.
  The cue-aimed retry returns the lead at 2:46.5-2:47.9 (probabilities 0.49, 0.99, 1.00,
  1.00) and the echo after it (0.15, 0.53, 0.02, 0.00), its last word ending at 2:51.0. The
  span check allows an end up to 2:50.8, so the whole retry is dropped and the first-pass
  line stays, with its two missing words guessed and the echo stretched by the end snap to
  2:47.1. That end is why the line "ends on time".
- **The echo was kept on consistency** (share 0.25: one of its four words matched in its
  own cue, under the heard test's bar), the same kind of keep as Leave the Door Open 3:46.
- **Reach, 47 songs:** 73 gaining lines had a retry refused; on 28 of them the retry ran
  past the cue's end bound. Where the two leads can be compared (53 lines), the first pass
  already had the lead within 1 s of the retry's on 45. Of the other 8, only this line has
  the retry's lead inside its cue span, confident, and seconds from what shipped (row 23
  lists the 8).
- **Spot 1 (line 50)** is heard as roughly right with an early first word, which agrees
  with the read (6.6 s off its heard words before, 1.0 s after). The read's credit to the
  section re-align stands on Ken's ear now, not on the transcript alone.
- **Line 51's early first word is new on the branch**: before, its retry was kept and
  "Take" started at 2:53.1; after, the first pass is kept and "Take" starts at 2:51.2. It is
  one of B2's listed middle moves (-1.83 s).

Ken (2026-11-16), to the recommendation to keep GATE B as ruled and log line 49: "add and
amend". Nothing is built for it. Logged in `plans/open-issues.md` with two candidate
changes; either alters what the rescue keeps and would need a replay of its own.

##### The fix: an added line is never heard-aimed (Sonnet 5.5 builds and replays)

Why: an added line was kept on the evidence of its own cue window, so nowhere else is a
place to look for it ("How the rescue treats an added line", the rule B bullets; spot 6).
Only rule B changes for it. Rule A1 and the guard lift are left as they are, and so are the
heard match and every non-added line.

**Code** (`pikaraoke/lib/cue_align.py`, one commit with its tests):

- `repace_bad_lines(..., added_lines: Collection[int] = ())`: the ids of the lines added to
  the song for a backing vocal. Passed to `_Rescue.__init__` as a keyword and held as a
  frozenset.
- `_Rescue.heard_shift` returns None for a line in it, before any other test. Nothing else
  in `_Rescue` reads it, so the line still gets the cue-aimed retry and then the fill.
- `align_song` passes the new ids whose `backed.old_line_ids` entry is None, and nothing
  when `backed` is None. If a small property on `Backed` reads better than a second
  comprehension beside `_log_backing`'s count, add it and use it in both.
- Docstrings: `repace_bad_lines` (the parameter and its why, in the rule B paragraph),
  `heard_shift`, `align_song`. `alignment_capture.py`'s `cue_inputs` note: an offline replay
  passes `added_lines` back too, read from `joint_stats.backing.old_line_ids` (null
  entries). Nothing new is recorded, so no schema change.

**Tests** (`tests/unit/test_cue_align.py`):

- `TestHeardAimedRetry`: the scenario of
  `test_a_line_with_no_words_heard_4_6_s_after_its_cue_is_kept_where_it_was_heard` with
  `added_lines=[4]`: the one align call is the cue-aimed slice, `heard_aimed_line_ids` is
  empty, the line is a fill.
- `TestAlignSongBacking`:
  `test_an_added_line_heard_two_seconds_before_its_cue_is_aimed_there_first` asserts the
  opposite of the ruling. Rewrite it in place (same heard words; the stub also sings the echo
  at its cue): the only one-line call is the cue window `(4.45, 6.55)`, the line is re-aligned
  at 5.25, `heard_aimed_line_ids` is empty.
- `test_a_one_word_added_line_is_never_aimed_where_its_word_was_heard` now passes for two
  reasons and tells nothing apart: delete it (the one-word rule is `heard_lines`' own, tested
  there). Check that before deleting; if `test_heard_lines.py` does not cover it, say so in
  the Results row and keep it.
- Mutation check: with the `heard_shift` test removed, both new tests fail.

Full suite, pre-commit on the changed files, `graphify update .`.

**Open issues** (`plans/open-issues.md`, "Backing vocal lines"): the entry "The rescue's rule
B can aim an added line at another copy of its words" is closed by this commit; delete it.

**Replay** (local GPU, one job, library read-only):

- Phase 2's outputs in `~/probes/backing_vocal_lines_phase2/{before,after}` are what GATE B
  was read on: do not write there. New scratch `~/probes/backing_vocal_lines_gateb_fix/`.
- The library's files for the song must be the ones Phase 2 staged:
  `find ~/pikaraoke-songs -newer ~/probes/backing_vocal_lines_phase2/logs/after_controls.started`
  lists nothing of this song. If it does, stop.
- Stage: `PYTHONPATH=. python plans/backing-vocal-lines/phase2_replay.py stage ~/pikaraoke-songs
  ~/probes/backing_vocal_lines_gateb_fix plans/backing-vocal-lines/out --key ru0K8uYEZWw --side after`.
- Run from this worktree's root on the fix commit, GPU idle first (`nvidia-smi`):
  `python -u plans/backing-vocal-lines/phase2_run.py ~/probes/backing_vocal_lines_gateb_fix/after
  --song=ru0K8uYEZWw --yes`, output to `~/probes/backing_vocal_lines_gateb_fix/logs/after_fix.log`.
  Never `--reset`.

**The check**, three sides: Phase 2 before, Phase 2 after, the fix. Line ids are the after
run's new ids; old ids through `joint_stats.backing.old_line_ids`. Word times from the
`.ass`, as in row 20.

- Line 91 (the added line cued over the transcript's empty stretch, 3:25-3:33; confirm it by
  text and `cue_inputs.spans[91]` first): not in `heard_aimed_line_ids`; its source
  (`cue_align_line` or `cue_align_fill`); its start and end against `cue_inputs.spans[91]`
  plus `cue_inputs.rescue_offset`. On its cue means it starts no earlier than 0.5 s before
  the cue start plus the lead and ends by the cue end plus the lead (or the window's
  `aim_end`, where a singing end widened it). Phase 2 after had it at 213.59-215.36.
- The old line before it (old id 86): its last word's end (209.59 before, 213.52 after) and
  whether its first two words are still guessed (the `PHASE2 guessed` note).
- Sung-time overlap of 91/93, 91/94 and 93/94 (1.40, 1.65 s and over 1 s at GATE B).
- Every line of the song whose word times differ between Phase 2 after and the fix, listed
  with source and rescue-list membership on both. Expected: line 91, the line before it, and
  any run of rescued lines directly after it. A difference anywhere else is listed, not
  explained away.
- The same count against Phase 2 before for old lines: the song's B2 "all other lines" stays
  at zero moves.
- The fix run's `heard_aimed_line_ids`, `heard_aimed_kept_line_ids`, `repaced_line_ids` and
  aligner failures against Phase 2 after's (it had line 40 fail on its retry).

Log it as a Results row (raw, no verdict), commit, and stop. Not in this step: a GO call,
a `/code-review`, the landing, a push, any regen.

##### GATE B call (Fable 5.2, 2026-11-16)

**GATE B is GO.** Ken's ruling made it GO once the replay shows line 91 on its cue, and it
does (Results row 24, checked again here with the committed script; row 25 for what this
call adds).

| Line 91, `(I can't stop the feeling)` | Phase 2 after | The fix |
|---|---|---|
| Cue on the audio clock | 209.78-211.14 | the same |
| Shown | 213.59-215.36 | 209.38-210.93 |
| Start against the cue start (allowed: up to 0.5 s before) | 3.81 s after | 0.40 s before |
| End against the cue end (allowed: by the cue end) | 4.22 s after | 0.21 s before |
| Looked for where heard | yes, kept | no |
| How timed | one-line retry, 1 word guessed | one-line retry, every word measured |

- **Nothing else moved.** 2 of the song's 119 lines differ from Phase 2 after: line 91, and
  the line before it (old 86), whose last word no longer stretches 3.9 s across the gap (it
  ends 0.34 s earlier than on `dev`). Every count of B2 against before is the same, and "all
  other lines" stays at zero moves. The other six added lines, the rescue lists and the one
  aligner failure (line 40) are as they were.
- **The other 46 songs stand on Phase 2.** Rule B tried exactly one added line in the 47
  (row 20), so the fix changes no other song's output.
- **What the GO rests on.** B1 and B6 pass outright. B2 and B3 have their exceptions listed
  (row 20's report). B4 is counted on inline words by ruling (82.3%). B5's directions check
  passes. B5's two-lines check fails as worded, and no ruling names it: it is taken here as
  accepted with "I take the recommendations", since the read laid it out and recommended GO
  past it. Ken's to correct if he reads it otherwise.

**Two things the read said about spot 6 that the replay does not bear out.**

- *"3 of those 6 [added-line overlaps over 1 s] from spot 6."* The fix removes two (91/93,
  91/94). 93/94 stays at 1.44 s, and line 91 on its cue now overlaps the next line, 92, by
  1.34 s (0.27 s at Phase 2). Both are the same thing: the next line's first word is placed
  about 1.5 s before its own cue and held to its second word, on `dev` as well, and the echo
  now shows in that time. Over the 47 songs that makes 5 added-line pairs over 1 s, not 3.
  It is the case the D7 amendment counted (the line after starts before the echo's end by
  over 1 s for 5 of 56). No old word moved for it. Logged in `plans/open-issues.md`.
- *"The old line before it then had ... its first two words guessed."* One word, and the fix
  leaves it guessed, so it was never line 91's doing. Fable's reading: the line before that
  one (89) gained an inline echo, kept because it repeats elsewhere, and the echo sits in
  the time "Got this" had; "Got" now starts 0.58 s later and is 0.1 s long. It is one of
  B3's listed increases, of the kind the read described.

**Still open, none of it holding the GO.**

- **Not heard:** the fix's output from 3:25 to 3:36. Ken heard spot 6 on the Phase 2 after
  only ("after shows both at the same time; before preferable, cleaner"). The two copies no
  longer share a time. Line 91 now shows at 3:29, where the caption has it and the transcript
  is empty (it has no word from 3:25 to 3:33, the lead lines included), so nothing but the
  caption says it is sung there. A listen is Ken's option before the landing; the ruling
  does not ask for one.
- **Logged at this gate, nothing built** (`plans/open-issues.md`, "Backing vocal lines"): a
  held last word lost when a section is re-aligned; a group kept on a repeat leading a line;
  the Takedown retry refused for its echo; and the overlap above.
- **Review:** `705099db` is a guard at the top of one method and the argument that carries
  the ids to it, read in one pass here, with the replay as its end-to-end check. The stage 2
  review (row 19) covered the rest. No review is due before the landing.
- **Next, on Ken's word:** the landing on `dev`, then the single full regen once
  `onset_loud_start` has landed too ("Rulings for Fable's window"). The probe folders
  `~/probes/backing_vocal_lines_phase2` and `~/probes/backing_vocal_lines_gateb_fix` and the
  worktree `.claude/worktrees/bvl_phase2_before` are still in place.

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
| 11 | 2026-11-14 | spec read | Read by Fable 5.2 on `2dc30b7a` against `dev` `1016e20`, `cue_heard_rescue` `81d0d0bc`, `lrclib_fit_pick` `e8bd6994`; `read_counts.py ~/pikaraoke-songs out`, read-only over `out/heard.json`, `out/songs.json` and the bundles (`find ~/pikaraoke-songs -newer <stamp>` empty) | 34 songs, 2167 old lines, 202 gain words, 56 lines added. Old lines back to the aligner without gaining / beside a change only / all other: A (re-section) 1170 / 5 / 790; B (nearer section) 944 / 14 / 1007; C (own window) 809 / 48 / 1108. Gaining lines timed by today's section align 192 (echo heard 131, no audio evidence 60, mixed 1); under the half-the-tokens bar if no echo word is timed 30 (27 / 3 / 0), needing 1 echo word 13, 2 words 12, 3 or more 5; empty after today's section align 10. Inline keeps with a letterless text before the group 0 of 205; groups with no word once normalised 0 of 626. "Build spec read". |
| 12 | 2026-11-14 | spec ruling | Ruled by Ken on `1a4ade25` | Point 4: option C (a kept paren-only line in a window of its own). Point 7: B2 amended. Point 8: C0-C3 and C2p now, C4-C7 after GATE H of `cue_heard_rescue` and a D7 amendment. Points 10 and 11 taken. No script re-run. "Build spec ruling". |
| 13 | 2026-11-14 | C2p | `parity.py ~/pikaraoke-songs plans/backing-vocal-lines/out` on `5a70cf34` (C1 `474fc0ff`, C2 `5a70cf34`), read-only: `find ~/pikaraoke-songs -newer <stamp>` empty after | 170 cue songs read as the stage reads them (UTF-8), 7 movie songs skipped. 626 of 626 groups matched by (song, cue, group) with equal label keys, none extra. Kept 261, per group the same as Phase 0's `consume none +vocables +consist`: heard 180, vocable 60, consistency 21. Built verdicts: not_heard 359, quote 6 (Phase 0 dropped the same 6), unplaced 0, overlap 0. Differences 0. "C2p".
| 14 | 2026-11-14 | stage 1 | C0 anchors; C1 `474fc0ff`, C2 `5a70cf34`, C2p `3eed4bc2`, C3 `2eac1ad4` on `25130fa1`; `python -m pytest`, `pre-commit` on the changed files, `graphify update .` | C0: every anchor exists; `dev` `3c8d1de5` is `1016e20` plus one plans-only commit; neither `cue_heard_rescue` nor `lrclib_fit_pick` is on `dev` or this branch, `align_song` has no `heard_words`. Tests added: `test_srt_cues.py::TestSheetParens` 19, `test_backing_vocals.py` 39 (new file), `test_lyric_align.py::TestShowParensWiring` 2; no existing test edited, no cleaner output changed. Full suite 3636 passed. Pre-commit passed on every changed file. Graph rebuilt: 8606 nodes, 21481 edges. Ruling point 4's two cases built: `at` None after text with no letter (C1), a group with no word is `not_heard` before the vocable test (C2). One reading differs from D9's wording: a lone `)` token mid-line sticks to the previous token ("( oh ) hey" shows "(oh)", "hey"), not the next. "Build spec ruling", "Commits".
| 15 | 2026-11-15 | D7 amendment | Written by Fable 5.2 on `de695678` against `cue_heard_rescue` `ac87c180` (GATE H ruled; the landed set is in no tree until its Phase 5); `amend_counts.py ~/pikaraoke-songs plans/backing-vocal-lines/out`, read-only over `out/heard.json`, `out/songs.json` and the bundles (`find ~/pikaraoke-songs -newer <stamp>` empty). Two points ruled by Ken by question dialog | 56 kept paren-only cues in 18 songs. Cue touches the cue before / after 43 / 39; under 0.5 s to it 55 / 46; a section-style pad clamped under 0.25 s 55 / 46; on raw cues that window opens after the singing starts 54. Today's first pass ends the line before past the echo's start (cue start plus the rescue lead) by more than 0 / 0.25 / 0.5 / 1.0 s: 27 / 15 / 9 / 3 of 55 with words; starts the line after before the echo's end: 18 / 15 / 9 / 5 of 56. Words in the line 1 / 2 / 3 or more: 7 / 3 / 46. Evidence heard / vocable / consistency 46 / 2 / 8. Text equals a neighbouring line's 6; is the end of the line before 9. Rescue leads of the 18 songs -0.713 to +0.198 s, median -0.296, 10 over 0.25 s either way. Ruled: an added line is timed by the rescue's own one-line retry (replacing the 2026-11-14 clause on a section-style window); stage 2's base is `dev` merged in after Phase 5 lands. No library write. "The D7 amendment". |
| 16 | 2026-11-15 | ruling | Ken, by question dialog in a planning session (Opus 5.5); no script run | Part of a cross-branch build order for Fable's window (to 2026-11-16): `cue_heard_rescue` Phase 5, then C0s and C4-C7, review, Phase 2, GATE B. Ruled: Fable reads GATE B while available, Opus after; Phase 2 takes the floor if the full set would not finish by the morning of 2026-11-16; the library regen after a GO is the one full regen after `cue_heard_rescue`, `onset_loud_start` and this branch land. GATE B, "Rulings for Fable's window". |
| 17 | 2026-11-15 | stage 2 | C0s: `git merge dev` (local `dev` `6c4e9991`) as `3636b1e0`. C4 `e528c92c`, C5 `ebd99489`, C6 `453bdfbc`, cleanup `4cfc1416` (C4's alias order, `Backed` not frozen; folds into C4 at landing if wanted). `python -m pytest`, `pre-commit` on the changed files, `graphify update .` | C0s: the merge was clean, no conflict in any file (`lyric_align.py` and `test_lyric_align.py` were the two both sides touched); full suite 3689 passed on the merged tree before C4. Every C0s anchor exists on the merged tree except `aimable`, which is not a `_Rescue` member on `dev` or anywhere in `cue_align.py`'s history and which no other part of the amendment uses; the list now reads `can_realign` (the `can_realign(win)` check before a retry). Absent, as required: `process_whole`, `whole_shift`, `gap_retry_line`, `free_stretch`, `heard_held_line_ids`. Neither `lrclib_fit_pick` Phase 4 nor `onset_loud_start` is on `dev`. C4-C5 changed 7 files, +906/-64 lines in `pikaraoke/` and `tests/`. Tests added: `test_backing_vocals.py::TestWithBacking` 10, `test_cue_align.py::TestAlignSongBacking` 11 and `TestRepaceBadLines::test_a_given_offset_is_used_and_not_fitted` 1, `test_lyric_align.py::TestBackingVocalsWiring` 5. Existing tests edited: 9 `align_song` call sites in `test_cue_align.py` (unpack four items), call shape only; no cleaner output changed. Full suite 3716 passed; pre-commit passed on every changed file. Mutation checks, each caught by at least one new test: rescue lead not pinned, added line's span not shifted on a re-sectioned song, every section sent back, stage ignoring the returned lines, no origin check, parens never read. Graph rebuilt: 8828 nodes, 22144 edges. Not run: any GPU run or library read (Phase 2). Built as the amendment reads, with these places where the spec left a free hand: `_Rescue` takes `offset` as a keyword defaulting to None; `joint_stats.backing` is recorded whenever the sheet has a group and a transcript (even a list with no words) was given, with `line_id` and `tokens` None for a dropped group; `align_song`'s first pass moved into `_first_pass` and its per-section align into `_align_section`, unchanged, so the section pass and the re-made sections share one path; the gaining sections are wrapped in the same `progress` as the first pass. "The D7 amendment", "Commits". |
| 18 | 2026-11-15 | ruling | Ken, in the session that wrote the Phase 2 executor prompt; counts read-only from the live bundles under `~/pikaraoke-songs/alignment_debug/` (backup folders excluded) and Results row 10; no script run | Phase 2 as written: 34 cue songs with a keep + 43 joint-route songs with a "(" in a lyric line (42 Genius, 1 custom) + 5 controls = 82 songs, 164 runs; floor 20 + 43 + 5 = 68 songs, 136 runs. 234 live bundles, 170 cue (`srt` 142, `lrclib_srt` 28), 7 `movie_srt`, 57 joint (54 Genius, 3 custom). Ruled: B6 is sampled to the 8 songs of "The B6 sample" (47 songs, 94 runs; floor 33 songs, 66 runs). "Rulings for Fable's window", "The B6 sample". |
| 19 | 2026-11-15 | stage 2 review | Opus 5.5: `/code-review dev..HEAD` on `c072a228`, files `srt_cues.py`, `genius_lyrics.py`, `backing_vocals.py`, `cue_align.py`, `lyric_align.py`, `alignment_capture.py` and their tests, 3 finders (correctness, simplicity, robustness). Library reach read-only with two session-scratch scripts (`finding_counts.py`: `sheet_parens`, `judge`, `with_backing` over `out/songs.json`; `word_per_token.py`: `output_line_timings[].n_words` against `_tokenise_lines(lyrics.align_lines)` in every live bundle), then `parity.py ~/pikaraoke-songs plans/backing-vocal-lines/out`; `find ~/pikaraoke-songs -newer <stamp>` empty. Fixes `87d24ee2`, open issues `a85fb179` | 11 findings: (1) a stray paren in the align text unpairs a line; (2) a "(" inside a group reaches the align text; (3) a failed re-align of a gaining section empties its untouched lines; (4) `_group_at` sends a group after a dash or star to None; (5) `tokens` count space-split tokens, not the line's words; (6) `_show_line` matches words to tokens by text, so a missing copy of a repeated word moves its form; (7) a capitals file capitalises a mid-line group; (8) `sheet_parens` re-parses the sheet; (9) `_group_at`'s letter check is a second cleaner; (10) `_show_line`'s ValueError fallback; (11) `ORIGINS` spells `"lrclib_srt"`. Reach among the 261 kept: (1) 0, (2) 0, (4) 0 unplaced, (5) 4 groups in 3 songs, (7) 19 groups in 2 songs (after the fix 3 capitals, one after a full stop and two "I"). Live bundles, per line, words against align tokens with a word: `cue_align` 10868 equal, joint 2791 equal and 262 none, 0 partial. Ken in chat: the rest to open issues; asked why not 6 and 10. Fixed: 1, 2, 3, 5, 6 and 10 (pair by position, warn and keep the text otherwise), 7. To `plans/open-issues.md`: 4 with 9, 8, 11 (`LRC_ORIGIN` sits with the other origin names in `library_regen`). Tests: `test_backing_vocals.py` 4 added, 2 removed (a dropped word, a word with no token left); `test_srt_cues.py` 1 rewritten (capitals), 1 added; `test_cue_align.py` 1 added. Mutation checks, each fix reverted alone: every one caught by its new test. Full suite 3720 passed; pre-commit passed on the changed files; `graphify update .`. `parity.py` after: 626 of 626 groups, kept 261 (heard 180, vocable 60, consistency 21), differences 0. |
| 20 | 2026-11-15 | 2 | Executor Sonnet 5.5. "Before" = `dev` `6c4e9991` in a detached worktree (`.claude/worktrees/bvl_phase2_before`); "after" = this branch at `aead83f3` (review fixes `87d24ee2`); `models/` linked into both. Scripts in `plans/backing-vocal-lines/`, committed with this row: `phase2_replay.py select` and `stage` (song list `out/phase2_songs.json`, kept), `phase2_run.py` (the driver's own `main()` with three observers on `_guess_missing_words`, `_Rescue.start_bounded` and `_Rescue.heard_aimed_line`, which log what the bundle does not keep: guessed tokens per line, why a retry's start moved, rule B's shifts), `phase2_report.py`. Replay: `scripts/regen_alignment_bundles.py <scratch>/before` (and `after`) `--song=<id>... --yes`, one GPU job at a time, scratch `~/probes/backing_vocal_lines_phase2/{before,after,logs}`, never `--reset`; library read-only (a stamp file, `find ~/pikaraoke-songs -newer <stamp>` empty after the controls, mid-run and at the end). Size: the full set, not the floor. Timed first on the 5 controls (after tree, 17:26-17:37, 11.3 min, 2.2 min a song), so the full 94 runs were expected in about 4 h; they ran 17:26-21:54 (controls first, then the 8 B6 songs and the 34 keep songs in chunks, each chunk before then after; the after side takes 1.0-1.4 times the before side). 47 songs: the 34 keep songs are row 10's (kept groups judged on the library bundles: 261, of them 205 inline and 56 paren-only; 129 min audio), the 8 B6 songs are "The B6 sample" (all 8 in the library, no substitute; 32 min, 7 Genius and 1 custom), the 5 controls are cue songs whose sheet holds no "(" (54 srt and 10 lrclib_srt candidates), per origin the ones nearest that origin's median audio length: `axySrE0Kg6k`, `orJSJGHjBLI`, `rg_zwK_sSEY` (srt), `9ThO76peOw0`, `gAYL5H46QnQ` (lrclib_srt); 18 min. The controls ran through the plain driver, everything else through `phase2_run.py`. Observers checked neutral: control `axySrE0Kg6k` rerun through `phase2_run.py` on a copy of the same inputs gave `.ass`, `.srt` and bundle identical to its plain run. Figures are the `Summary` block of `out/phase2_report.md` (local: it holds lyric text; the details are in `out/phase2_details.json`). Word times are read from the `.ass` (centiseconds, "moved" is over 0.011 s), since a cue song's bundle holds none. | **Inputs.** All 16 batches finished, no failed song. `.ass` dialogues match their bundle's lines on every keep-song run (34 x 2); the recomputed heard-line count equals `n_heard_lines` in all 68 of those bundles; every keep song has its guessed-token note in both logs; the `tokens` range of 260 of the 261 kept groups opens with "(" and closes with ")" in the `.ass` (the one that does not is the `show_parens` warning below). The replay transcribes again, so its keeps differ from the library judge's on 4 of 261 groups: not kept now, `TSVHoHyErBQ` cue 79 (inline) and `GG7fLOmlhYg` cue 33 (paren-only), both `not_heard`; kept now only, `FQ3slUz7Jo8` cues 71 and 73 (paren-only, heard). The after run keeps 261: 204 inline groups on 201 gaining lines (Phase 0: 205 on 202), 57 paren-only groups on 56 added lines; evidence heard 180, vocable 60, consistency 21; 83 sections sent back to the aligner. **B1** 5 of 5 controls identical: every output file byte-identical (2 files for three, 6 for two) and the bundle identical but `config.whisper.load_model.model_path`, which is each worktree's own `models/` link. **B2** (old words, 13138 in 2167 lines): gained 1010 words in 201 lines, moved at all 614, over 0.3 s 267 (in 144 lines); start |change| same 511, <=0.05 160, <=0.1 44, <=0.3 115, <=1 118, <=3 54, >3 8; end same 528, 189, 43, 75, 109, 58, 8; max(start,end) p50 0.03, p90 0.98, p99 3.46, max 5.87. Middle (in a section sent back, or directly before or after a gaining or added line) 5532 words in 837 lines, moved at all 1277, over 0.3 s 298 (in 187 lines); start same 4565, 454, 96, 204, 141, 54, 18; end same 4661, 502, 91, 108, 91, 60, 19; p50 0.00, p90 0.10, p99 1.84, max 6.87. All other lines 6596 words in 1129 lines, moved 0. Of the 565 words moved over 0.3 s, 13 (in 5 lines) sit on a line an aligner failure hit; each of the 565 is listed with the rescue steps that changed in the report. **B3** (old lines, before -> after): re-aligned 328 -> 340, paced 45 -> 39, lines with a guessed word 241 -> 306 (241 -> 271 counting only old words), guessed words 284 -> 331, zero-length words 0 -> 0. Increases listed per line, 213: re-aligned 49 (gained 26, middle 23), lines with a guessed word 73 (55, 18), with an old word guessed 39 (21, 18), guessed words 44 (25, 19), paced 8 (gained 8); 8 of them on a line an aligner failure hit. D8: 31 gaining lines have more new tokens than old (evidence heard 28, none 3, mixed 0; the plan counted 30, 27 / 3 / 0), by id in the report. **B4** new words: inline echo words 588, measured 484 (82.3%), guessed 66, paced 38; added-line words 269, measured 150 (55.8%), guessed 6, paced 113; all 857, measured 634 (74.0%). **B5** kept groups by Phase 0 label: sung 253, unsure 8, direction 0; old-line pairs whose display windows overlap after and did not before: 26; display-window overlaps involving an added line: 106; adjacent lines overlapping (the pre-roll): before 1872 of 2133 pairs, after 1859 of 2133 counting old lines only, 1951 of 2189 with the added lines. **B6** 8 songs: `output_line_timings` equal 8, bundle word times equal 8, `.ass` word times equal 8 (3138 words compared); text changed 286 words, all of them parentheses only; any other text change 0. **Added lines** 56 (18 songs): re-aligned 32, paced 23, heard-aimed and kept 1; guessed words in them 6; start cut to the previous line's end 13; guard lift freed 10; onset snap moved 4; the aligner failed on the retry of 2 (`wGyh_53ecgg` line 33, `ru0K8uYEZWw` line 40; both paced). The line before an added line: 55 have one with an old id; its last word's end moved for 44, earlier by over 0.3 s for 36, later by over 0.3 s for 1. **Heard-aimed tries on an added or gaining line** 5, kept 3: `GG7fLOmlhYg` gaining line 33 (shift -1.55 s, kept; line 34's words overlap the place by 0.35 s), `ru0K8uYEZWw` added line 91 (+4.28 s, kept; lines 92, 93, 94 overlap by 0.27, 1.40, 1.65 s; 93 is another added line), `fGyTN5UjnL4` gaining line 10 (-1.62 s, not kept), `atz_aZA3rf0` gaining line 39 (-1.61 s, kept; line 38 overlaps by 4.72 s) and line 40 (-1.62 s, not kept). Old lines whose membership of `heard_kept`, `heard_aimed`, `heard_aimed_kept` or `guard_lifted` changed, or whose heard status changed: 91 (gained 62, middle 29, other 0); 38 by list membership, 53 by heard status. Songs whose guessed-line share crosses 15%: 0. **Aligner failures** (every `slice-align failed` line, song and label): before 7: `axySrE0Kg6k` line 27, `W5kM5wAwRug` line 42, `wMOkm57vu0k` line 53, `wIyNAsmGrl0` line 35 (a padding-size error; the rest are "NoneType has no attribute language"), `tz_NxOF7RB4` lines 58, 59, 61; after 9: `axySrE0Kg6k` line 27, `W5kM5wAwRug` line 42, `wGyh_53ecgg` line 33, `ru0K8uYEZWw` line 40, `wIyNAsmGrl0` line 63, `tz_NxOF7RB4` lines 58, 59, 60, 61 (labels are the song's ids on each run). **`show_parens` warnings** in the after run: 1 (before: 0), `wIyNAsmGrl0` line 63, old line 56, an inline kept group (cue 63, vocable). The section align returned 3 of the line's 4 words, its one-line retry hit `slice-align failed` (same line, same log), and the line kept those 3 plus 1 guessed word; the third word reads `la-la` where its align token reads `la-la,`, so the words did not pair with the tokens and the group shows without parentheses. **Listening list** 10 spots in the report, from the 4 largest old-word moves (`j5itLHDMJsE`, `wGyh_53ecgg`, `wIyNAsmGrl0`, `PodgxWsZw9s`), the 3 heard-aimed keeps, an added line re-aligned and one paced, one inline line. Not done: any GO/NO-GO, a library regeneration, a push. |
| 21 | 2026-11-15 | GATE B | Read by Fable 5.2 on `21c28fb2`, after Ken's listen of the report's 10 spots (his notes are in "GATE B read"). Read-only over `out/phase2_details.json` and the before/after `.ass` files and bundles in `~/probes/backing_vocal_lines_phase2/`, with session-scratch scripts built on `phase2_report.py`'s `Side`: each side's on-screen words paired by text and order (`match_words_to_tokens`) with the words `heard_lines` gives the line in the before bundle (old words only on the after side), the median absolute start offset per line compared; last-word ends; sung-time overlaps from word times; added lines against transcript words within 1 s of their cue span plus the lead. No GPU, no library read, no build. | **Transcript referee**, old lines with a word moved over 0.3 s: 331, comparable 262 (gained 109, middle 153). After nearer by over 0.3 s / before nearer / within 0.3 s: gained, move 0.3-1.0 s (64 lines) 3 / 3 / 58; gained, over 1.0 s (45) 6 / 4 / 35; middle, 0.3-1.0 s (93) 1 / 1 / 91; middle, over 1.0 s (60) 8 / 1 / 51. Lines within 1.0 s of heard, before -> after: 60 -> 61, 39 -> 39, 90 -> 90, 52 -> 57. Before nearer (median offset before -> after): `CEw-7cMnBDY` 33 (0.12 -> 1.55) and 32 (0.32 -> 0.94), `wIyNAsmGrl0` 53 (0.05 -> 1.20), `NSYNC - Paradise` 49 (0.36 -> 1.00), `1QYBiNRu1ok` 41 (0.05 -> 0.57), `atz_aZA3rf0` 41 (0.36 -> 0.81), `GG7fLOmlhYg` 39 (0.07 -> 0.50) and 12 (2.37 -> 2.73), `D_dOXTpwV5s` 27 (0.04 -> 0.43). After nearer by over 1 s: `j5itLHDMJsE` 50 (6.56 -> 0.99), `wGyh_53ecgg` 37 (5.64 -> 0.32), `GG7fLOmlhYg` 45 (2.94 -> 0.14), `9tcaM06eGrY` 20 (1.96 -> 0.32), `hj4e709GYf4` 11 (1.21 -> 0.11), `CEw-7cMnBDY` 13 (1.17 -> 0.15). **Gaining lines by evidence** (201; comparable / after worse / after better by over 0.3 s): heard 131 lines, 107 / 5 / 8; vocable 56, 40 / 0 / 1; consistency 13, 9 / 2 / 0; mixed 1, 1 / 0 / 0. Kept group first in the line 18 lines, an old start moved over 1 s on 14; group later 183 lines, 34. **Last old word ending over 1 s earlier**: 65 lines; the next line is an added line 31, the line's own echo follows 30, neither 4: `PodgxWsZw9s` 63 (-5.74), `j5itLHDMJsE` 50 (-1.72), `luotSpkyCVU` 47 (-1.15), `wIyNAsmGrl0` 55 (-1.13). `PodgxWsZw9s` 63: section 54-67 sent back for gaining lines 60 and 61; first-pass last word 234.80-235.64 -> 235.34-235.49; end extension 5.585 s -> none. **Sung-time overlap**: old pairs overlapping by 0.3 s more than before 26 (`atz_aZA3rf0` 38/39 4.72, `ru0K8uYEZWw` 86/87 3.93, `j5itLHDMJsE` 48/49 2.32, the other 23 at most 1.11); pairs with an added line 52, over 0.3 s 31, over 1 s 6 (`ru0K8uYEZWw` 91/94, 93/94, 91/93; `6tpl9LtkRRw` 47/48; `PodgxWsZw9s` 38/39; `FQ3slUz7Jo8` 69/70). **Added lines against words heard in their cue window**: re-aligned 32, with a pair 26, median offset up to 0.5 s / 0.5-1 / over 1: 22 / 1 / 3; paced 23, with a pair 18: 8 / 3 / 7; an echo that repeats its lead pairs with the lead's words. `ru0K8uYEZWw` line 91: verdict consistency, share 0.0, no transcript word from 205 to 213.14 s; placed 213.59-215.36 with line 93 at 213.96-215.40; old line 86's last word end 209.59 -> 213.52. `wGyh_53ecgg` line 33: cue 10.47 s, words at 185.70 and 191.68, heard at 185.92 and 186.02. **B3**: old lines with an increase 127 (gained 86, middle 41); newly holding a guessed old word 39 (21, 18), 29 of them newly crammed; newly re-aligned 49 (26, 23); newly paced 8 (all gained). **B5**: the 8 kept groups labelled unsure are 8 `(skate)`. Recommended: NO-GO as built, GO after one change (an added line is never heard-aimed) and two rulings by Ken (paced added lines kept or dropped; `PodgxWsZw9s` 63 accepted or not), with two more spots for his ear. "GATE B read". |
| 22 | 2026-11-15 | GATE B ruling | Ken, in chat, on `502985d3`; no script run, no build. His listen of the read's two unheard spots, as given | Ruled: all three recommendations of "GATE B read" taken: (1) build "an added line is never heard-aimed" and replay `ru0K8uYEZWw` alone; (2) paced added lines kept, B4 counted on inline words (82.3%); (3) `PodgxWsZw9s` 63 accepted, logged in `plans/open-issues.md`. Listen: `wGyh_53ecgg` 3:05, added line `(With you)` paced over a 10.5 s cue: the line is "with you, yeah, oooooooo ooooooooo wooooaahhh", after covers it correctly length-wise with "with you". `wIyNAsmGrl0` 3:46, line 53: the timing of "for you" is roughly correct; Ken would have preferred "tell me that you're coming through" not put into that line. No change asked for the second; logged in `plans/open-issues.md`. Spec of the fix and the replay check written for Sonnet 5.5. "GATE B ruling". |
| 23 | 2026-11-16 | GATE B, spot 1 heard again | Ken, in chat, on `fd87a2b9` before it was amended: his listen of `j5itLHDMJsE` from 2:35, as given in "Spot 1 heard again". Read by Fable 5.2, read-only over `~/probes/backing_vocal_lines_phase2/{before,after}` (the song's bundles, `.ass`, `lyrics/*.lrclib.srt`) and `logs/{before,after}_K3.log`; no GPU, no build, no library read. One session-scratch script over every after bundle with `joint_stats.backing`: for each line holding a kept inline group, the last `cue_inputs.realigns` record of that line when the line is not in `realigned_line_ids`; where the record returns a word for every align token, its words outside the group's `tokens` range (the lead) against the same words of `cue_inputs.sections`, and its first start and last end against the cue span plus `rescue_offset`, 0.5 s either side (the span check's bounds for a window not widened; 6 of the lines are in `windows_widened_line_ids`, where the true end bound is later) | Ken: "'ima take it down' is quite early (it actually starts at 2:46), but ends on time. the other lines have early onsets but roughly right". **`j5itLHDMJsE`**, audio clock, offset -0.05. Cues: 48 163.47-166.35, 49 166.35-170.31, 50 170.31-173.38, 51 173.38-177.38. Transcript: `It's` 161.78-163.28, `a` 163.28-163.46, `takedown` 163.46-164.08; `I'ma` 165.54-166.74, `take` 166.74-167.00, `it` 167.00-167.20, `down` 167.20-167.68; `It's` 169.22-170.12, `a` 170.12-170.28, `day` 170.28-170.64; `Dig` 171.82-172.28, `it` 172.28-174.00, `down` 174.00-174.60. Line 49 first pass: before 161.99-162.93, 4 words timed, no retry record; after `I'ma` 161.99-162.17, `take` 162.17-162.45, `it` 162.45-162.47, `down` 162.47-162.47, echo 162.47-164.87, in `crammed_line_ids` and `guessed_word_line_ids` (tokens 2 and 3). After retry of 49: slice 165.55-171.01, `start_bounded` bound 165.80, start 166.478 not cut; `I'ma` 166.478-166.75 (p 0.49), `take` -166.99 (0.99), `it` -167.17 (1.00), `down` 167.34-167.85 (1.00), `oh,` 167.85-168.53 (0.15), `da-da-da,` 169.33-169.83 (0.53), `down,` 170.07-170.91 (0.02), `ooh` 170.91-170.99 (0.00); end bound 170.76; 49 not in `realigned_line_ids`. Shipped: before 161.99-162.93, after 161.99-167.14 (end extends on tokens 6 and 7, 0.796 and 2.271 s). Group on cue 49: `consistency`, share 0.25; cues 47, 48, 50: `not_heard`. Line 48 on both sides: heard-aimed, shift -1.64, kept, 161.28-164.31. Line 50: before 162.93-172.96; after `It's` 167.24, `a` 170.11, `takedown` 170.29-171.23. Line 51: before retry kept, `Take` 173.06; after first pass kept, `Take` 171.23, `it` 173.90, `down` 174.50. **Refused retries on gaining lines, 47 songs**: gaining lines 201, with a retry record 108, kept 35, refused 73. Of the 73: a word for every token 56, fewer 17. Of the 56: end past the end bound 28 (group evidence heard 17, consistency 6, vocable 5), start before the start bound 15, both 6, neither 19. Lead compared with the first pass's on 53: starts within 0.5 s 28, 0.5-1 s 17, over 1 s 8. The 8 (song, line, evidence; first-pass lead -> retry lead; shipped; lowest lead probability; which bound): `atz_aZA3rf0` 40 heard, 167.52 -> 162.31, shipped 163.06-167.27 (its cue), 0.08, both; `atz_aZA3rf0` 23 heard, 93.01 -> 88.24, 88.99-93.03 (its cue), 0.61, both; `j5itLHDMJsE` 49 consistency, 161.99 -> 166.48, 161.99-167.14, 0.49, end; `atz_aZA3rf0` 22 heard, 87.25 -> 84.02, 84.61-88.90 (its cue), 0.03, both; `CEw-7cMnBDY` 35 heard, 162.84 -> 161.38, 161.83-165.00, 0.00, neither; `hj4e709GYf4` 10 heard, 18.06 -> 16.63, 18.06-18.62, 0.77, start; `6tpl9LtkRRw` 88 heard, 232.00 -> 233.07, 232.00-236.78, 0.28, end; `NSYNC - Paradise` 43 vocable, 228.90 -> 229.93, 228.90-233.10, 0.03, end. Ken: "add and amend". Logged in `plans/open-issues.md`; the fix spec unchanged. "Spot 1 heard again". |
| 24 | 2026-11-16 | GATE B fix, replay of `ru0K8uYEZWw` | Sonnet 5.5. Fix built as `705099db` on `ef44346d` (the handoff named `fd87a2b9`; that commit was amended at 09:09 on 11-16 with the "Spot 1 heard again" text, so Results row 23 was taken and this is row 24): `repace_bad_lines(added_lines=)`, `_Rescue.heard_shift` returns None for an added line before any other test, `align_song` passes `Backed.added_line_ids` (new property, also used by `_log_backing`), the `alignment_capture` note, the open-issues entry deleted. Tests: `TestHeardAimedRetry::test_an_added_line_is_never_looked_for_where_it_was_heard` new; `TestAlignSongBacking::test_an_added_line_heard_two_seconds_before_its_cue_is_aimed_at_its_cue_only` rewritten in place (the stub also sings the echo at its cue); `test_a_one_word_added_line_is_never_aimed_where_its_word_was_heard` deleted, `tests/unit/test_heard_lines.py::test_a_one_word_line_is_never_heard` covers that rule. Mutation check: with the `heard_shift` guard removed both new tests fail, 138 others pass. Full suite 3720 passed; pre-commit on the changed files clean; `graphify update .` run. Replay: `find ~/pikaraoke-songs -newer ~/probes/backing_vocal_lines_phase2/logs/after_controls.started` listed nothing; GPU 6 MiB used, 0 % before; `PYTHONPATH=. python plans/backing-vocal-lines/phase2_replay.py stage ~/pikaraoke-songs ~/probes/backing_vocal_lines_gateb_fix plans/backing-vocal-lines/out --key ru0K8uYEZWw --side after`; from the worktree root at `705099db`, `python -u plans/backing-vocal-lines/phase2_run.py ~/probes/backing_vocal_lines_gateb_fix/after --song=ru0K8uYEZWw --yes`, log `~/probes/backing_vocal_lines_gateb_fix/logs/after_fix.log`, 5 min 25 s, succeeded=1 failed=0. Phase 2's folders were not written. Check: `plans/backing-vocal-lines/gateb_fix_check.py`, committed with this row, read-only over `Side`, `parse_logs` and `b2` of `phase2_report.py`; run `PYTHONPATH=.:plans/backing-vocal-lines python plans/backing-vocal-lines/gateb_fix_check.py`. Three sides: Phase 2 before, Phase 2 after, fix. Line ids are the after run's new ids | **Inputs.** Fix against Phase 2 after: `backing.old_line_ids`, groups and `aligned_sections`, `transcribe_words`, `lyrics`, `cue_inputs.spans`, `cue_inputs.sections` and `rescue_offset` (-0.24) all equal. Bundle differences outside `output_*` and `joint_stats`: `cue_inputs.realigns[33]` only (line 91's retry). **Line 91**, `(I can't stop the feeling)`, an added line; `cue_inputs.spans[91]` 210.024-211.384, `rescue_offset` -0.24, so the audio cue is 209.784-211.144. Transcript: no word from 205 to 213; `No,` 213.14-213.36; `I can't stop the feeling` 214.06-215.22 (line 93's cue is 214.202-215.614). Before: no such line. Phase 2 after / fix: in `heard_aimed_line_ids` yes (shift +4.28, kept) / no; source `cue_align_line` / `cue_align_line`; retry slice 213.31-216.17 / 209.03-211.89 (one retry each); words 213.59-215.36 / 209.38-210.93; start against cue start + lead +3.81 / -0.40 s; end against cue end + lead +4.22 / -0.21 s; guessed tokens 1 / 0; in `windows_unmeasured_line_ids` yes / no; widened no / no. Fix retry's raw words 209.39-210.93, `start_bounded` bound 209.284, raw start 209.386, kept uncut, not lifted. **Old line 86 (new 90) `Got this feeling in my body`:** last word `body` 208.93-209.59 before, 208.73-213.52 Phase 2 after, 208.73-209.25 fix. Guessed token indices before none, Phase 2 after [0], fix [0] (the first word only; not the first two). First words before `Got` 206.69-207.09, `this` 207.09-207.45, `feeling` 207.57-; Phase 2 after and fix both `Got` 207.27-207.37, `this` 207.37-207.47, `feeling` 207.47-207.97. Lists, both after runs: `guessed_word`, `crammed`, a section line. **Sung-time overlap** (first word start to last word end; positive is overlap), Phase 2 after / fix: 91/93 +1.40 / -3.03; 91/94 +1.65 / -2.78; 93/94 +1.44 / +1.44. Spans, before / Phase 2 after / fix: 89 205.06-206.69 / 205.01-207.37 / same; 90 206.69-209.59 / 207.27-213.52 / 207.27-209.25; 91 none / 213.59-215.36 / 209.38-210.93; 92 209.59-213.71 / 209.59-213.86 / same; 93 none / 213.96-215.40 / same; 94 213.71-218.92 / 213.71-217.90 / same; 95 none / 218.00-219.54 / same. **Lines whose word times differ, Phase 2 after against fix:** 2 of 119, and `output_line_timings` differs on those two only. Line 90 (old 86): one word, `body`'s end 213.52 -> 209.25 (4.27 s); lists the same on both. Line 91: 5 words, largest 4.43 s; lists `realigned`, `guessed_word`, `windows_unmeasured`, `heard_aimed`, `heard_aimed_kept` -> `realigned`. **B2 against Phase 2 before, old lines:** other 348 words in 76 lines, 0 moved; middle 194 words in 33 lines, 54 moved, 11 over 0.3 s in 6 lines; gained 7 words in 3 lines, 4 moved, 0 over 0.3 s; 0 lines with a different word count. Identical to Phase 2 after's counts, and the same 11 words are over 0.3 s on both; the one whose value changed is old 86 `body`'s end, +3.93 -> -0.34 against before. **Run lists, Phase 2 after -> fix:** `heard_aimed_line_ids` [91] -> []; `heard_aimed_kept_line_ids` [91] -> []; `repaced_line_ids` 0, 38, 40, 71, 80, 83, 86, 93, 95, 108 on both (before: 0, 69, 101); realigned 17 on both; guessed words 24 -> 23 (before 19). Aligner failures: line 40's retry, `Whisper worker error: 'NoneType' object has no attribute 'language'`, on both runs, nothing else. The song's 7 added lines (38, 40, 80, 86, 91, 93, 95): 91 `heard-aimed kept` -> `cue_align_line`; the other six `cue_align_fill` on both. "The fix". |
| 25 | 2026-11-16 | GATE B call | Fable 5.2 on `a73460c2`, read-only, no GPU, no build, no library read. `PYTHONPATH=.:plans/backing-vocal-lines python plans/backing-vocal-lines/gateb_fix_check.py` run again; two session-scratch scripts over `phase2_report.Side` on the three sides of `ru0K8uYEZWw` (Phase 2 before, Phase 2 after, fix): word times of new lines 86-96 from the `.ass`, `cue_inputs.sections` (first pass) and the end snap's `extends` for the same lines, the transcript from 200 to 222 s, and the sung-time overlap (first word start to last word end) of each added line with every line up to 4 ids away, listed over 0.3 s | **Check script:** output equal to row 24's; line 91 `on_cue` true, start -0.40 s against cue start + lead, end -0.21 s against cue end + lead (Phase 2 after: false, +3.81, +4.22). **Added-line overlaps over 0.3 s**, Phase 2 after: 38/39 0.34, 80/81 0.71, 86/85 0.30, 86/87 0.60, 91/93 1.40, 91/94 1.65, 93/94 1.44, 95/96 0.52. Fix: 38/39 0.34, 80/81 0.71, 86/85 0.30, 86/87 0.60, 91/92 1.34, 93/94 1.44, 95/96 0.52. **Line 92** (old 87) `Got this feeling in my body`, cue + lead 211.14-213.96: `Got` first pass 209.59-210.09 after and fix (before 209.59-210.13), end snap +1.40 s, shown 209.59-211.49 (before 209.59-211.44); `this` 211.59; no transcript word from 205 to 213.14; in no rescue list on any side. **Line 94** (old 88) `Wanna see you move your body`, cue + lead 215.37-218.00: `Wanna` first pass 213.71-214.39 (before 213.71-214.37), end snap +1.61 s, shown 213.71-216.00 (before 213.71-215.53); transcript `I` 215.22-215.86, `want` 215.86, `to` 215.86-216.00, `see` 216.00; in no rescue list. **Line 93** (added, `heard`, share 1.0, paced): 213.96-215.40, transcript `I can't stop the feeling` 214.06-215.22. **Line 89** (old 85) `Everybody sing (I can't stop the feeling)`: group `consistency`, share 0.0; before `Everybody` 205.06-206.21, `sing` 206.21-206.69; after and fix `Everybody` 205.01-206.01, `sing` 206.23-206.69, echo 206.69-207.37 (first pass: `(I` 206.69-206.97, `can't` -207.27, the last three with no duration at 207.27); `crammed` and `guessed_word` on both after runs. **Line 90** (old 86): first pass after and fix `Got` 207.27 with no duration, `this` 207.27-207.45 (before `Got` 206.69-207.09, `this` 207.09-207.45); shown as in row 24. **Added lines of the song**, verdicts near the spot: 86 and 91 `consistency` (share 0.0), 93 and 95 `heard` (1.0). Worktrees still present: `.claude/worktrees/bvl_phase2_before` (detached, `6c4e9991`). "GATE B call". |
