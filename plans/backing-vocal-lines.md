# Backing vocals in parentheses: show the sung ones on caption and LRC songs

Model: Claude Opus 5.5 runs Phase 0, judges both gates and writes the build spec.
Claude Sonnet 5.5 builds from that spec. (High-level spec by Claude Fable 5.2, 2026-11-11.)

**Status: Phase 0 done 2026-11-14 (Opus 5.5); stopped at GATE A for Ken's ruling ("GATE A
read").**

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

## Phase 0 record

Run by Opus 5.5 on 2026-11-14, CPU only, library read-only. Scripts and output in the session
scratch folder `/tmp/claude-1000/-home-ken-projects-pikaraoke/0ab1bdd0-e655-42ad-8e0b-05018e2c1d58/scratchpad/bvl/`,
run from the worktree with `PYTHONPATH=.`.

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
Timings and line ids only, no lyric text: `out/baseline.json` in the scratch folder.

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
