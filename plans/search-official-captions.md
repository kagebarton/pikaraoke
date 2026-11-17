# Search: lift the videos most likely to have captions, and stop lifting the wrong ones

Model: Claude Sonnet 5.5 (spec by Claude Fable 5.2, 2026-11-11; rules revised 2026-11-16 after
the held-out check, see Measurements; Part 2, the search page layout, spec by Claude Opus 5.5,
2026-11-17)

Branch `search_official_captions` off `dev` at `1016e20`, worktree
`.claude/worktrees/search_official_captions` (inside the main checkout, gitignored via
`.claude/`; `models/` is symlinked in). Work and run everything from the worktree. If `dev` has
moved, rebase onto it before commit 1.

Follows `plans/search-official-first.md` on tag `archive/search_official_first`, which built
`pikaraoke/lib/official_rank.py`. Read it with
`git show archive/search_official_first:plans/search-official-first.md` only if a rule's history
matters; everything needed is below.

## Goal

The search page lifts official uploads so the user is likely to pick a video with manual
captions (the best lyric timing source) that is the studio recording. An evaluation on 60
live searches (Measurements, below) found three faults in the current ranking:

- It lifts uploads that are not the record: live sessions, making-ofs, fan and re-upload
  channels, all badged "Official video" (17 of 60 searches).
- It misses label-channel uploads, which is where film songs (DisneyMusicVEVO) and K-pop (HYBE
  LABELS) live. For "bts butter" the official MV drops from #1 to #10.
- The query is sent to YouTube wrapped in quotes, so a missing apostrophe ("how far ill go
  moana") returns 30 uploads with no official one among them.

The first draft of the rules (2026-11-11) was tuned on the same 44 fixtures and 60 searches
that tested it. A check on 40 new searches (2026-11-16, Measurements) found it no better than
YouTube's own order there, and rules 1, 5, 6, 7, 9 and 12 were revised.

## Decisions (Ken, 2026-11-11)

1. Drop the quotes around the search query.
2. Alternate versions of the video lift ("2025 Version", "Millennium 20 Edition", "Clean
   Version"): about half have manual captions. The goal is to maximise the chance the user
   picks a video with manual captions.
3. No caption lookup at search time. It is slow, and users expect fast results. The ranking
   stays a guess from the title and channel.
4. Another act's version of the song lifts only from a label channel (DisneyMusicVEVO's second
   cast of a film song). Ken first asked for covers from any official channel; the prototype
   showed that also lifts every other song of the same name from its own act's channel ("hello"
   lifted Lionel Richie's, "let it go" lifted Keyshia Cole's, Def Leppard's and DJ Khaled's), and
   he ruled label channels only. The old plan's decision 2 (original artist only) otherwise
   stands: Pentatonix's own-channel "Bohemian Rhapsody" stays where YouTube put it.

Decisions (Ken, 2026-11-16, after the held-out check):

5. "I only want audio to be lifted when there's no official video, and no other videos with
   manual captions." The second half cannot be known without a caption lookup (decision 3), so
   the rule is the first half: audio is lifted only when no video is. Beside a lifted video it
   keeps YouTube's place and its "Official audio" badge.
6. A title that says "official" does not make a verified channel a label's. Only the
   channel's name does. (Ken agreed this for videos. The spec applies it to audio too, and
   drops the re-upload bar that went with it, see rule 7: neither changes a row in the 84
   searches.)

Still in force from the old plan: official lyric videos, live, remix, karaoke and the like are
not lifted unless the query asks for that version; the vote is taken over the first page only;
a query in a script the matching cannot read lifts nothing. "Video before audio" is superseded
by decision 5.

## What exists (checked 2026-11-11, `dev` at `1016e20`)

- `pikaraoke/lib/official_rank.py` (193 lines): `pick_artist(results, query) -> str | None`,
  `official_kind(result, query, artist) -> "video" | "audio" | None`,
  `official_first(results, query, artist) -> list[tuple[SearchResult, OfficialKind | None]]`.
- `pikaraoke/routes/search.py`: `/search` (line 121) and `/search/more` (line 158) call
  `pick_artist` over the first page and pass the artist to `_search_rows` (line 101), which
  calls `official_first`. `SearchRow.official` is the kind; `templates/search_result.html`
  prints "Official {{ row.official }}".
- `pikaraoke/lib/youtube_dl.py:249`: `yt_search = f'ytsearch{count}:"{query}"'`. The command is
  an argument list, not a shell string, so the quotes reach YouTube.
  `tests/unit/test_youtube_dl.py:473` asserts the quoted form.
- `tests/unit/test_official_rank.py`: tables `_LIFTED` (14 fixtures) and `_STAYS_PUT` (6 rows),
  plus synthetic-row tests. `tests/unit/test_search_render.py` has the route tests.
- yt-dlp reports one flag, `channel_is_verified`, for both YouTube's plain verified tick and
  its "Official Artist Channel" badge (`yt_dlp/extractor/youtube/_base.py`, badge map), so the
  app cannot see which channels YouTube itself calls official. "Official channel" below is
  therefore worked out from the channel's name and the title.

## Design

The reference is `plans/search-official-captions/proto_rank2.py`: a working prototype of every
rule below, checked against all 44 fixtures and the 40 held-out searches in
`plans/search-official-captions/holdout/`. Write the module cleanly; the prototype is there
to settle ambiguity and is not to be imported. It borrows the unchanged helpers from today's
module (`_words`, `_compact`, `_share_found`, `_has_letters_without_ascii`, `_is_art_track`,
`_is_trusted`, `_channel_artist`, `_title_artists`, `_marks`, the regexes), which stay.

### Search command (`youtube_dl.py`)

`ytsearch{count}:{query}`, no quotes.

### Ranking rules (`official_rank.py`)

1. **Who a title credits.** As today for "Artist - Song". New: a title with no separator but a
   quoted song credits the text before the opening quote, and each round-bracket alias in it.
   `BTS (방탄소년단) 'Butter' Official MV` credits `bts`; `정국 (Jung Kook) 'Seven (feat. Latto)'
   Official MV` credits `jungkook`. An opening quote is one of `' " ‘ “ 「 『` not preceded by a
   letter or digit, so the apostrophe in "Don't" is not one, and outside every bracket (a
   bracket the title never closes runs to its end): in `Under the Sea (From "The Little
   Mermaid")` the quote names the film, not the song, and the title credits no one. Square
   and `【】` brackets before the quote are dropped. A title with neither a separator nor such
   a quote credits its channel, as today.
2. **The originals.** Count credits over the trusted rows of the first page, as today. The
   originals are every name tied for the most credits, when that count is at least 2. A tie is
   no longer "nobody": a duet's two singers and the pair tie ("Mena Massoud, Naomi Scott"), and
   so do two casts of a film song. None for a query the matching cannot read.
3. **Whose upload a row is.** The names it credits (rule 1, plus the channel for an art
   track or a title naming no one). Exception: a row on a "- Topic" channel is its channel's
   alone, because a cover's art track is titled "Song - Film" or "Original Artist - Song".
4. **Tier.** "Original" when the row's names include an original; otherwise "other" (commit 3).
5. **Not the record.** Today's exclude list, counted per mark beyond the query's, plus: demo,
   rehearsal, making of, footnotes, perform(s), performance. Hyphens read as spaces, in the
   title and the query alike, so "Behind-the-Scenes" carries the mark "behind the".
6. **Is the song.** More than half the song words appear anywhere in the title, and at least
   one appears outside brackets. (Today the whole check ignores brackets, so "speechless
   aladdin" misses "Naomi Scott - Speechless (from Aladdin)".) And the query may say more
   than the title ("let it go frozen" for the art track "Let It Go"), or the title more than
   the query, but not both: a title that lacks a song word may carry, outside its brackets,
   no word that rule 9 calls unexplained. "Adele - Make You Feel My Love" is not "adele send
   my love". A misspelt song word therefore lifts nothing, video or audio (it leaves one word
   missing and one unexplained): YouTube's order, which is what today's module says a typo
   should get. For the original tier the song words are the query words not inside the name of
   an original this row credits. Not any original's: when the song's name ties the vote
   ("under the sea little mermaid" votes `underthesea` beside `samuelewright`), striking it
   leaves only the film's name, which Samuel E. Wright's title carries in brackets.
7. **Comes from the act.** One of:
   - an art track;
   - **own channel**: a trusted channel whose name equals one of the row's names. The channel
     name is today's `_channel_artist`, then with trailing `official`, `vevo`, `music`, `tv`,
     `video(s)` stripped ("EminemMusic", "PhilosopherKingsVEVO") and a leading "the" dropped
     from both sides. Equal, not contained: today's substring test passes the fan channel
     "ePro Team: Support for Eminem & Shady Records";
   - **label upload**: a verified channel whose name ends in "VEVO" or has the word Records,
     Recordings or Label(s). Nothing in the title makes a channel a label's (decision 6): the
     verified fan channel "Disney¡Fan!" titles its re-uploads "Official Music Video". This
     gives up RHINO's and Netflix's real uploads, none of which had captions. The 11-11
     draft also barred a label upload when the act's own channel had the video on the page.
     That bar existed for the by-title channels (7clouds' "Justin Timberlake - Suit & Tie
     (Official Video)"), which no longer pass at all; it decides no row in the 84 searches
     and is dropped.
8. **"Says official"** means: "official" followed, before the bracket closes, by "video",
   "audio" or "MV"; or "music video"; or "MV" / "M/V". A bare "official" does not count:
   "(Rosanna Pansino Official)".
9. **A video must say what it is.** Take the title, drop "feat./ft./featuring/with/from …" up
   to the bracket or segment end, and drop the query's words, words inside the row's names,
   the plain words (official music video audio hd hq 4k mv explicit clean only the a an of
   and) and the words of the record's own title: every word in the title of an art track on
   the first page that is the original's and the song (rules 3 to 6). "Adele - Send My Love
   (To Your New Lover)" on "Adele - Topic" explains the official video's "(To Your New
   Lover)". If anything is left, the title must say official (rule 8) or say version,
   edition, edit or remaster(ed). "(O2 Arena)", "(AOL Sessions)", "@ The Tonight Show" fail;
   "(2025 Version)", "(Official HD Video)", "(Edit)" pass. Skipped for audio (never captioned
   either way) and for a title carrying a mark, which got this far only because the query
   asked for it ("bohemian rhapsody live" still lifts "(Live Aid 1985)").
10. **Kind.** Audio for an art track or a title with the word "audio"; otherwise video.
11. **Other acts (commit 3).** A row whose names include no original lifts as a video when
    its channel is a label channel by name (rule 7: verified, ends in "VEVO" or has Records,
    Recordings or Label(s)) and is not the act's own channel ("NataliaKillsVEVO" is Natalia
    Kills' own); every query word appears in its title or channel name; and rules 5, 6 (with
    all query words) and 9 hold. Never its audio. A label channel's title that credits no one
    credits the channel (rule 1), so DisneyMusicVEVO's `We Don't Talk About Bruno (From
    "Encanto")` lifts here. Residue, four rows across the 44 fixtures and the 40 held-out
    searches: a label channel's different song of the same name (Spinnin' Records' "Martin
    Solveig & Dragonette - Hello" for "hello"; DisneyMusicVEVO's `Stronger (From "Under the
    Sea: A Descendants Short Story"/Official Video)` for "stronger"), and a concert or signed
    version titled as from the film (`(From "Encanto at the Hollywood Bowl")`, `(From "The
    Little Mermaid"/British Sign Language Version)`).
12. **Order (decision 5).** The originals' videos, other acts' videos, then the rest in
    YouTube's order. The originals' audio goes first only when no video is lifted, among the
    rows being ordered or on the first page; otherwise it stays where YouTube put it. Stable
    within each. Every row with a kind shows its badge, "Official video" / "Official audio",
    lifted or not.

### Module shape

```python
@dataclass(frozen=True)
class Acts:
    """What the first page says: the original artist's names, the words of the record's own
    title, and whether that page lifts any video."""
    originals: frozenset[str] = frozenset()
    record_words: frozenset[str] = frozenset()
    has_video: bool = False

def read_first_page(results: Sequence[SearchResult], query: str) -> Acts: ...
def official_kind(result: SearchResult, query: str, acts: Acts) -> OfficialKind | None: ...
def official_first(results, query, acts) -> list[tuple[SearchResult, OfficialKind | None]]: ...
```

`pick_artist` goes; `read_first_page` replaces it, and `Acts()` is "nothing known". It fills
the fields in order, each needing the one before: the vote, then `record_words` (rule 9, off
the originals' art tracks), then `has_video` (rule 12, for `/search/more`, whose rows are
ordered apart from the first page's). The tier is internal to the module (`official_first`
needs it to order; callers only see the kind). `official_first` returns the rows in display
order with their kinds, as today: a kind is a badge, not a promise that the row moved. The
prototype's `other` switch and its third "lifted" value are for printing commit 2's state
and the tables; the module has neither.
Keep helpers small: the prototype's `lift` is one long function for reading, and the module
should split it (who the row is, is it the song, does it come from the act, does it say what
it is). Delete what is superseded: `pick_artist`, `_OFFICIAL`, the substring channel test.

### Routes (`routes/search.py`)

Both routes call `read_first_page` over the first page (`results` on `/search`,
`results[:PAGE_SIZE]` on `/search/more`) and pass the `Acts` through `_search_rows` to
`official_first`. No template change.

### Not doing

- Any caption lookup at search time (decision 3).
- Reading YouTube's "Official Artist Channel" badge: yt-dlp merges it with the verified tick.
- Matching CJK or other non-Latin song names (the existing guard stays; nothing is lifted).
- Changing which uploads count as official audio beyond the new marks: "Band Ver." and
  "Extended Version" art tracks still get the audio badge.
- A caption-aware audio rule (the second half of decision 5).
- Known wrong lifts left as they are: a foreign-language cast that shares a credited singer
  with the original lifts as the original's (DisneyMusicAsiaVEVO's Thai "Into the Unknown"
  credits AURORA); a duet re-recording on the other singer's channel lifts ("Calum Scott,
  Whitney Houston - I Wanna Dance With Somebody", uncaptioned; barring it also bars Reba
  McEntire's and Lindsey Stirling's duets, both captioned); rule 11's residue.
- Known misses left as they are, each costing only YouTube's order: "for good wicked" and
  "popular wicked" (the vote picks the song's name or nothing), "colors of the wind" (the vote
  picks the film's name from karaoke channels), "soda pop kpop demon hunters", "toxic" (the
  vote picks BoyWithUke, whose song of that name fills the page).

## Fixtures

`tests/unit/data/youtube_search/` holds 44 files, and six held-out captures join them
(below). The 14 from 2026-11-08 are quoted-search captures. The 30 new ones are committed on
this branch as `8187552` (on their own, ahead of the tests that read them, because they cannot
be captured again; it lands on `dev` with the rest). They are real unquoted `ytsearch30`
captures from 2026-11-11, cut to the same fields (`id, url, title, channel, uploader,
channel_is_verified, duration, description[:40]`).
File stem = the query with `_` for spaces, as before.

Position = YouTube's, 1-based. "Other acts' videos" is empty after commit 2 and as listed
after commit 3; everything else is the same after both. The audio column is the rows badged
"Official audio". They are lifted, in the order listed, only where the videos columns are both
"none": defying gravity, dont stop believin, hallelujah, seasons of love rent. Everywhere else
they keep YouTube's place. No fixture lifts audio after commit 2 and loses it after commit 3.

### New fixtures (unquoted captures, 2026-11-11)

| query | originals | original's videos | other acts' videos (commit 3) | original's audio |
|---|---|---|---|---|
| bts butter | bts | `WMweEpGlu_U` (#1) | none | none |
| jung kook seven | jungkook | `QU9c0053UAU` (#1) | none | `Vs64cZbeY88` (#12), `zj0O6-YvLhg` (#15) |
| a whole new world aladdin | menamassoud, menamassoudnaomiscott, naomiscott | `eitDnP0_83k` (#2) | none | `atc8RAtl-Ms` (#9) |
| part of your world | jodibenson, thelittlemermaid | `SXKlJuO07eM` (#1) | `kf7Dss2gCe0` (#2) | `sg1Y6Vxl6Nk` (#5), `ZYcV5oXlccc` (#10), `totRu4FjI74` (#24) |
| speechless aladdin | naomiscott | `mw5VIEIvuMI` (#1) | none | `DwTogmKwYWo` (#4), `J8CVHdMvv30` (#25) |
| how far ill go moana | auliicravalho | `cPAbx5kgCJo` (#1) | `_nVJl4-o2XA` (#3), `IhZI-a1eiCg` (#14) | `keGr19WWwoA` (#24) |
| circle of life lion king | thelionking | none | `GibiNy4d4gc` (#1), `IwH9YvhPN7c` (#2) | none |
| youre welcome moana | dwaynejohnson, moana | `79DijItQXMM` (#1) | `0DLzyvT4eUo` (#10) | `khg-OuAtt5E` (#4) |
| backstreet boys shape of my heart | backstreetboys | `OT5msu-dap8` (#1) | none | none |
| john legend all of me | johnlegend | `450p7goxZqg` (#1), `xwsYvBYZcx4` (#5) | none | none |
| colbie caillat realize | colbiecaillat | `GlZxZ2n2zpw` (#1), `pwpHhN-vtRI` (#5), `u5Exxrl7frA` (#9) | none | none |
| kelly clarkson because of you | kellyclarkson | `Ra-Om7UMSJc` (#1), `o0oenkCT8EY` (#5) | none | `C-IgZrOsEag` (#4) |
| britney spears oops i did it again | britneyspears | `CduA0TULnow` (#1) | none | `OO0aTOIU_3w` (#5) |
| ne-yo so sick | neyo | `IxszlJppRQI` (#1), `ub3y1Baw0ak` (#27) | none | none |
| eminem lose yourself | eminem | `xFYQQPAOz7Y` (#1) | none | none |
| justin timberlake suit and tie | justintimberlake | `IsUsVbTj2AY` (#1), `7tWvTW16atE` (#7) | none | `cJzRZ0T5ewc` (#2), `0S0vamqBlek` (#5) |
| adele someone like you | adele | `hLQl3WQQoQ0` (#1) | none | `22c3_LoIfZQ` (#4) |
| tenacious d tribute | tenaciousd | `_lK4cX5xGiQ` (#1) | none | none |
| ed sheeran perfect | edsheeran | `2Vv-BfVoq4g` (#1) | none | `817P8W8-mGE` (#15) |
| backstreet boys i want it that way | backstreetboys | `4fndeDfaWCg` (#1), `VVB6FI8QTFg` (#4), `mAGGPgxl6qU` (#7), `GJhTjyc7A3Y` (#22) | none | `z6Wq59qrdB0` (#9), `-aKJE1lanQk` (#14) |
| because of you | kellyclarkson | `Ra-Om7UMSJc` (#1), `o0oenkCT8EY` (#5) | none | `C-IgZrOsEag` (#16) |
| perfect | edsheeran | `2Vv-BfVoq4g` (#2) | none | `817P8W8-mGE` (#21) |
| let it go | idinamenzel | `YVVTZgwYwVo` (#1) | none | `FnpJBkAMk44` (#4) |
| mirrors | justintimberlake | `uuZE_IRwLNI` (#1) | none | `U41KPUfOSFk` (#6) |
| tribute | none | none | none | none |
| the lonely island threw it on the ground | thelonelyisland | `gAYL5H46QnQ` (#1) | none | none |
| vitamin c graduation | vitaminc | none | none | none |
| the philosopher kings cry | thephilosopherkings | `EUW0eDhKoxw` (#1) | none | none |
| golden kpop demon hunters | huntrx | none | none | none |
| celine dion my heart will go on | celinedion | `9bFHsd3o1w0` (#1), `bf-HGyke89Y` (#8) | none | `mNsm2P0l_7Y` (#11), `cJnSrovvM74` (#19) |

### Existing fixtures (quoted captures, 2026-11-08)

| query | originals | original's videos | other acts' videos (commit 3) | original's audio |
|---|---|---|---|---|
| bad guy | billieeilish | `DyDfgMOUjCI` (#1) | none | `2pnXjQCegVc` (#6) |
| bohemian rhapsody | queen | `fJ9rUzIMcZQ` (#1) | none | `0TF3hFevWE8` (#9) |
| dancing queen | abba | `xFrGuyw1V8s` (#1) | none | `P5AqvKYYQEE` (#16) |
| defying gravity | cynthiaerivo | none | none | `HxkLt1GXVsw` (#9) |
| dont stop believin | journey | none | none | `_wXLKQCTuD0` (#20) |
| hallelujah | leonardcohen | none | none | `ttEMYvpoR-k` (#8) |
| hello | adele | `YQHsXMglC9A` (#1) | `LnET4RKXx5k` (#4) | `T1tl66trXTQ` (#16) |
| let it go frozen | idinamenzel | `YVVTZgwYwVo` (#1) | none | `FnpJBkAMk44` (#2) |
| never gonna give you up | rickastley | `dQw4w9WgXcQ` (#1), `LLFhKaqnWwk` (#3), `RrESvSRNpeo` (#7) | none | `3BFTio5296w` (#5) |
| queen bohemian rhapsody | queen | `fJ9rUzIMcZQ` (#1) | none | `0TF3hFevWE8` (#6) |
| rolling in the deep | adele | `rYEDA3JcQqw` (#1) | none | `bDtjO-R0QSo` (#5) |
| seasons of love rent | anthonyrapp | none | none | `1xGUTW3C3gE` (#5), `HLEPfySbfxQ` (#14) |
| shallow lady gaga | ladygaga | `bo_efYhYU2A` (#1) | none | `BpIf43m2ZQI` (#5) |
| someone like you | adele | `hLQl3WQQoQ0` (#1) | none | `22c3_LoIfZQ` (#17) |

For the 14 existing fixtures the originals' videos and audio are exactly today's `_LIFTED`
table, but its test is not: audio is now at the top in only the four fixtures with no video.

### Held-out fixtures (unquoted captures, 2026-11-16)

Six of the 40 searches in `plans/search-official-captions/holdout/`, each the capture that
exposed a fault in the 11-11 draft. Copy them into `tests/unit/data/youtube_search/` under
the same names.

| query | originals | original's videos | other acts' videos (commit 3) | original's audio |
|---|---|---|---|---|
| adele send my love | adele | `fk4BbF7B29w` (#1) | none | `Fq-AHPOshKc` (#5) |
| under the sea little mermaid | samuelewright, underthesea | `GC_mV1IpjWA` (#1) | `Wbv_huklr5E` (#2), `Uki_W4nYbr4` (#22) | `ChNJ_FMtSnk` (#3), `b32vFD5Acrc` (#12), `ZhFwcueYEKE` (#14) |
| we dont talk about bruno encanto | wedonttalkaboutbruno | none | `bvWRMAU6V-c` (#1), `-QOSz9G1GnY` (#5) | none |
| do you want to build a snowman | frozen | none | `1APv9t_LyOY` (#2) | none |
| justin timberlake sexyback | justintimberlake | `3gOHvDP_vCs` (#1), `-oqXwnXjgDE` (#13) | none | none |
| be our guest beauty and the beast | thebeast | none | none | none |

Audio keeps YouTube's place in all six. What each pins: "(To Your New Lover)" is the record's
own title (rule 9) and "Make You Feel My Love" is another song (rule 6); the song's name ties
the vote without hiding Samuel E. Wright's video (rule 6); `Song (From "Film")` credits no one
(rule 1); "Behind-the-Scenes" is a mark (rule 5); "(Edit)" is a version (rule 9); a fan
channel's "Official Music Video" is no label's (rule 7). `-QOSz9G1GnY` and `Uki_W4nYbr4` are
rule 11's residue, listed because the rules lift them, not because they should.

Must stay unlifted, after commit 2 and after commit 3 (new and held-out fixtures):

| query | id (#) | what | rule |
|---|---|---|---|
| bts butter | `HbkBVxU5K5A` (#4) | BANGTANTV, "'Butter' @ The 64th GRAMMY Awards" | 9 |
| bts butter | `5dWxvUcEUEY` (#21) | BANGTANTV, "(PERFORMANCE REHEARSAL VER)" | 5 |
| jung kook seven | `1QYBiNRu1ok` (#2) | BANGTANTV, "Official Performance Video" | 5 |
| backstreet boys shape of my heart | `v1Q5SsHIuBY` (#8) | own channel, "(O2 Arena)" | 9 |
| john legend all of me | `ftGQLvUwzjY` (#3) | own channel, "Vevo Go Shows: All Of Me" | 9 |
| colbie caillat realize | `jDt2u2eJk3Q` (#3) | own channel, "(AOL Sessions)" | 9 |
| kelly clarkson because of you | `P8dtX_t9mJc` (#7) | own channel, "(Walmart Soundcheck 2009)" | 9 |
| britney spears oops i did it again | `MHfCJT6hkZ4` (#9) | own channel, "The Making of … (Vevo Footnotes)" | 5 |
| ne-yo so sick | `XLtinWelxkE` (#8) | own channel, "The Making Of 'So Sick'" | 5 |
| eminem lose yourself | `jNYR1ioecJY` (#29) | fan channel "ePro Team: Support for Eminem…", full live set | 5, 7 |
| justin timberlake suit and tie | `8fWBQtknJdA` (#3) | 7clouds, "(Official Video)" | 7 |
| adele someone like you | `il-NdjTtUAI` (#25) | Casey Ford Alexander, "Adele - Someone Like You (Music Video)" | 7 |
| tenacious d tribute | `W4uqbxvOK2A` (#2) | own channel, "Tribute to "Tribute": … Fan Compilation" | 1 |
| tenacious d tribute | `qSf6JznfdkY` (#16) | own channel, "(1995 Demo Version - Official Audio)" | 5 |
| ed sheeran perfect | `eiDiKwbGfIY` (#3) | "Ed Sheeran and Andrea Bocelli" channel, Perfect Symphony | 7 |
| ed sheeran perfect | `fgcwFILyTVo` (#27) | own channel, "(Backstage Rehearsal)" | 5 |
| backstreet boys i want it that way | `nUhVJBCpPSM` (#28) | "SethDrums - Topic" cover art track | 3 |
| part of your world | `azpDUgf2RLc` (#27) | "Rosanna Pansino - Topic" cover art track | 3 |
| youre welcome moana | `5CQLqMebytM` (#6) | Disney¡Fan!, "MOANA - You're Welcome (HD) Music Video" | 7 |
| vitamin c graduation | `tz_NxOF7RB4` (#1) | RHINO, "[Official Music Video]" | 7 |
| golden kpop demon hunters | `hohuFW0zQUw` (#16) | Netflix Philippines, "‘Golden’ Music Video" | 7 |
| adele send my love | `0put0_a--Ng` (#12) | XL Recordings, "Adele - Make You Feel My Love (Official Video)" | 6 |
| adele send my love | `9IzKueQ2ZxY` (#10) | Adele's art track "Make You Feel My Love" | 6 |
| do you want to build a snowman | `-9ZWF8vxmzM` (#25) | Shine On Media, "Behind-the-Scenes Music Video" | 5, 7 |
| do you want to build a snowman | `KKP0Txebobg` (#14) | DisneyMusicVEVO, `(From "Frozen: The Broadway Musical"/Audio Only)` | 1, 11 |
| be our guest beauty and the beast | `Lt1Fck9DDp8` (#7) | Disney¡Fan!, "(Official Music Video(" | 7 |

Perfect Symphony, RHINO's Vitamin C video and Netflix's "Golden" are real official videos
on channels that are neither the act's own by name nor a label's by name. Accepted: none has
captions.

The old `_STAYS_PUT` table: all six rows hold after commit 2 and after commit 3, including
`ojRj2JK5oCI` (Pentatonix, own channel, "bohemian rhapsody") and `mHONNcZbwDY` (Lionel
Richie, own channel, "hello").

Page 2 (the four 60-row fixtures), `read_first_page` over rows 1-30, ranking rows 31-60:
nothing is lifted in any of the four, after commit 2 and after commit 3. The vote over all 60
rows gives `{oct2026}` for hallelujah and `{letitgo}` for let it go frozen, as the drift test
records.

## Commits

Each commit: `pre-commit run --config code_quality/.pre-commit-config.yaml --files <changed>`,
`/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit -q`, an import smoke, and a read
of `git diff --cached`. Do the CLAUDE.md self-review before each one. Fill this plan's Results
log row in a separate plan-only commit, so landing can drop it cleanly. This file,
`plans/search-official-captions/proto_rank2.py` and `captions.json` are already committed
(plan-only).

1. **`fix(search): the query goes to YouTube unquoted`.** `youtube_dl.py:249` and the
   assertion at `tests/unit/test_youtube_dl.py:473`. Nothing else.

   Then, on its own like `8187552`: **`test(official_rank): six held-out searches frozen as
   fixtures`**, the six files named under "Held-out fixtures", copied from `holdout/`.
2. **`feat(official_rank): label uploads and alternate videos lift, live sessions and
   re-uploads do not`.** Rules 1-10 and 12, the `Acts` API, both routes, and the tests:
   - `_LIFTED` grows by the 30 new rows and the 6 held-out rows (originals as a set, videos,
     audio); the 14 old rows keep their IDs. Its tests change with rule 12: every listed row
     carries its kind; the videos come first in the listed order; the audio comes first, in
     the listed order, only where no video is listed, and otherwise sits where YouTube put it;
     everything else keeps YouTube's order.
   - `_STAYS_PUT` grows by the table above.
   - Rewrite the tests that call `pick_artist`: a tie now names both; one trusted credit is
     still not enough; no trusted rows changes no order; the drift test compares sets.
   - Synthetic-row tests, one per rule that a fixture does not isolate: a quoted title
     credits the text before the quote and its bracket alias (rule 1); a channel named
     "Alpha Fans United" is not Alpha's (rule 7); "AlphaMusic" and "AlphaVEVO" are; a verified
     channel that is neither Alpha's nor a label's by name is not lifted for "Alpha - Some
     Song (Official Video)", with or without Alpha's own channel on the page, and "Beta
     Records" is (rule 7); a bare "(Someone Official)" does not say official (rule 8); "Song
     (from Film)" passes the song check for "song film" and "Other Song (from Film)" does not
     (rule 6); "bohemian rhapsody live" still lifts "(Live Aid 1985)" (rule 9's exemption;
     this existing case must keep passing).
   - One per revised rule, beside the held-out fixtures that pin them: `Some Song (From "Some
     Film")` credits its channel, and `Alpha 'Some Song' (From "Some Film")` still credits
     Alpha (rule 1); "Behind-the-Scenes" and "Making-Of" are marks (rule 5); for "alpha some
     long song", "Alpha - Other Long Song (Official Video)" is not the song, for "alpha some
     long song film" the art track "Some Long Song" still is (the query says more, the title
     nothing of its own), and the misspelt "alpha some long sogn" lifts nothing (rule 6); with
     two verified "Some Song - Film" rows tying `somesong` with `alpha` in the vote, "Alpha -
     Some Song (from Film) (Official Video)" on a VEVO channel still lifts for "some song
     film" (rule 6); "Alpha - Some Song (Its Subtitle)" on Alpha's channel lifts when Alpha's
     art track is titled so and not when it is titled "Some Song" (rule 9); "(Edit)" lifts
     (rule 9). All were run through the prototype on 2026-11-16.
   - Rule 12, on synthetic rows: audio beside a lifted video keeps its place and its kind;
     audio with no video is first; rows 31-60 with audio and no video are not reordered when
     the first page lifted a video (`Acts.has_video`).
   - "celebration kool and the gang" from open-issues: add the case with the channel
     "KoolandthegangShow" and report in the Results log what it does. Do not bend a rule to
     make it pass.
   - Render tests in `test_search_render.py` follow the API change.
3. **`feat(official_rank): a label channel's other cast of the song lifts after the
   original's`.** Rule 11, the "other acts' videos" column for all 50 fixtures (eight fixtures
   have rows), and synthetic tests: another act's video on a label channel lifts, after the
   original's videos and before its audio; the same video on that act's own channel does not,
   nor on its own "ActVEVO" channel; a query that names the original ("alpha some song") lifts
   no other act; another act's audio on a label channel is not lifted; a query the matching
   cannot read lifts nothing.
4. **`docs(plans): open issues follows the search ranking changes`.** In
   `plans/open-issues.md`, "Search results": remove or rewrite the entries this fixes ("A
   verified re-upload can be lifted" is fixed for channels that are not labels by name; "A
   band whose channel spells its name another way" per what commit 2 found), and add the "Not
   doing" misses and known wrong lifts above, rule 11's residue, the real official videos
   decision 6 gives up (RHINO, Netflix), and one new entry: YouTube sometimes answers a search
   with no channel on any row (3 of 40 captures on 2026-11-16, gone on a second fetch), and
   such a page gets no badges and no lifts. Point the section at this plan.

**Stop after commit 4** (and its Results row). Don't land, push or retire anything. Report a
Review-due checkpoint per CLAUDE.md for commits 1-4: multi-file, new algorithm, so it is due.
Part 2 (below) runs in a later session, after that review and its fixes. Ken's manual checks
run once, after Part 2.
If a fixture row disagrees with the tables above, stop and report it rather than editing the
table: the tables come from the prototype, so a mismatch means the module and the prototype
differ.

## Manual checks (Ken, in the real app)

Run from the worktree: `/home/ken/miniconda3/envs/pik/bin/python -m pikaraoke.app`. Only one
instance can run at a time; stop the main one first. Live results differ from the fixtures.

- [ ] "bts butter": the HYBE LABELS "Official MV" is first with the badge; no "@ show" card
      has a badge.
- [ ] "how far ill go moana": Disney's official video is first.
- [ ] "part of your world": both Disney uploads (Jodi Benson, Halle) are at the top.
- [ ] "speechless aladdin": Disney's official video has the badge.
- [ ] "backstreet boys shape of my heart": the official video is badged, "(O2 Arena)" is not.
- [ ] "justin timberlake suit and tie": no 7clouds card has a badge.
- [ ] "hello": Adele's video first; Lionel Richie's "Hello" has no badge.
- [ ] "circle of life lion king": both Disney uploads (Carmen Twillie and Lebo M., Elton John)
      are at the top.
- [ ] "queen bohemian rhapsody": no cover has a badge.
- [ ] "adele send my love": Adele's video is first with the badge; nothing titled "Make You
      Feel My Love" has a badge.
- [ ] "under the sea little mermaid": Samuel E. Wright's official video is first.
- [ ] "nsync bye bye bye" (or any search with an official video and an official audio): the
      "Official audio" card has its badge and is not pulled above unbadged videos.
- [ ] "dont stop believin" (no official video on the page): the "Official audio" card is first.
- [ ] Show more still appends about 30 cards with no duplicates.

These run after Part 2, whose library lift puts a card you already own above everything. Read
"X is first" above as "X is first after the cards already in your library".

## Part 2: search page layout

Starts after commit 4 and its review fixes. Same branch, same per-commit routine as Part 1
(pre-commit, unit tests, import smoke, `git diff --cached` read, CLAUDE.md self-review,
Results row in a separate plan-only commit).

Mockup (private to Ken): https://claude.ai/artifact/1Q8jEkXEy5v5ZZeBvP7mCA. Three phone
screens for the search "adele hello": today, after, and after with Advanced opened. It
carries decisions 7-13. Where this section and the mockup differ, this section wins.

### Decisions (Ken, 2026-11-17)

7. A card whose YouTube ID is already a library file goes above every other card, official
   ones included. Among themselves they keep the ranking's order. Show more lifts its own
   in-library cards to the top of the batch it appends.
8. The "Already in the library" box goes. A library song under another YouTube ID becomes a
   note on the card that matched it, "In library: <name>" with its own Queue button. That card
   keeps its own button, so its version can still be downloaded.
9. The help hint under the search box goes.
10. The library autofill dropdown goes: guests tap its options by accident. The search box is
    a plain text box.
11. One "Add to queue after download" checkbox, in Advanced, for search picks and direct URLs
    alike, ticked by default. An untick lasts until the browser tab closes (not an app
    restart, not a page change).
12. The in-library button reads "Queue" (was "Add to Queue").
13. "Select" reads "Add…": the dialog with the preview and the lyrics choice still opens
    first, and the ellipsis says so.

Spec choices (Opus, not ruled by Ken; reopen any of them by asking):

- S1. Each library copy is noted once, on the first card in display order that matches it and
  is not itself in the library, and at most `MAX_SIMILAR_SONGS` (3) copies are noted per page,
  as the box had. A copy titled like the song matches nearly every upload of it, so noting it
  on every match would repeat one line down the whole page.
- S2. Notes are on the first page only, as the box was. Show more's cards get the library lift
  (decision 7) but no notes. Noting them would need the second page to know which copies the
  first page already noted.
- S3. The search box also turns off the browser's own past-searches list
  (`autocomplete="off"`): it is the same accidental tap as decision 10.
- S4. The search page is the only user of the selectize files and of `/autocomplete`, so both
  are deleted. So is dead upstream code in the same script: thumbnail cycling for
  `#search_result_selector`, `#youtube-link` and `#youtube-thumb`, none of which is on the
  page. Its interval fires a no-op every 2 s for as long as the tab is open.

### What exists (checked 2026-11-17 on `dev` at `764df44`)

Line numbers are `dev`'s. The branch has no code of its own before commit 1, and Part 1 rebases
onto `dev` first, so they hold until Part 1's commits move `routes/search.py`.

- `routes/search.py`: `SearchRow(result, existing_path, official)` (line 75); `_library_copies`
  (line 84) returns up to `MAX_SIMILAR_SONGS` library paths that `similar_songs` matches to any
  result's title, deduplicated, leaving out a path whose YouTube ID is any result's own;
  `/search` passes it as `similar_songs`; `/search/more` computes none. `/autocomplete` (line
  164) and `AutocompleteQuery` (line 47) serve only the selectize dropdown.
- `templates/search_result.html`: the card macro; `existing_path` gives a green "Add to Queue"
  button (`search_result_items_enqueue`), else `{% trans %}Select{% endtrans %}`
  (`search_result_items_select`), which opens the preview dialog.
- `templates/search.html`:
  - Head: selectize `<link>`/`<script>` (lines 4-5) and their CSS (`.optgroup-header`,
    `.row`, `.col-icon`, `.col-text`, `.selectize-input`, lines 7-29); `.similar-song` CSS
    (line 98).
  - Script: the document-wide Enter handler (line 277), which clicks Search from anywhere,
    the direct-URL box included; selectize setup and its `#add-queue-link` enqueue (lines
    289-464); the dead thumbnail cycling (lines 468-499, `changeImage` at 1034); the checkbox
    cookie `add-to-queue-on-download`, written at line 530 and read by
    `restoreCheckboxStates` (line 1042); `.similar-song-enqueue` handler (line 627).
  - Two synced ticks: `downloadSong` (the direct-URL download) reads `#add-to-queue-direct`,
    `postDownload` (the dialog's download) reads `#add-to-queue-search`, and the change handler
    at line 529 keeps them equal. `58ccd63` moved `downloadSong` onto the direct box: the
    results' tick exists only while results are on screen, so a direct download from a page
    with no results was never queued.
  - Markup: `#queue-form` with the selectize `<select>`, Search (`#search-link`), "Add to
    queue" (`#add-queue-link`), hidden `.song_added_by` (lines 1056-1073); help hint
    `<article class="message">` (lines 1084-1105); `#advanced-settings` with the direct URL
    and `#add-to-queue-direct` (lines 1110-1138); hidden `#container_search_form` whose
    `#search_string` input the script fills and submits (lines 1143-1147); the "Already in the
    library" box (lines 1165-1175); `#add-to-queue-search` above the results (lines
    1176-1182).
  - sessionStorage already holds `pikaraoke_search_results` and `pikaraoke_search_term` (the
    restore on a return visit, line 398), and the lyrics picker sends the term to
    `/lyrics_search` as `typed` (line 785).
- `filename_from_path` is a Jinja global (`app.py:208`), so the imported card macro can use it,
  `/search/more` included. Translation catalogs were last regenerated 2026-06-10 (`5780dfce`).
- `tests/unit/test_search_render.py`: the "Already in the library" tests (lines 142-230) and the
  card tests (from line 233) assert on `similar-song-enqueue`, `search_result_items_enqueue`
  and `search_result_items_select`.

### Design

**Order and notes (`routes/search.py`).**

- `SearchRow` gains `library_copies: tuple[str, ...] = ()`, the library songs noted on this
  card.
- `_search_rows` (Part 1's signature): after `official_first`, a stable sort puts rows with an
  `existing_path` first. Both routes go through it, so Show more lifts within its batch. Badges
  don't change.
- `_library_copies` becomes the note step, on `/search` only. It takes the rows in display
  order and returns them with `library_copies` filled (`dataclasses.replace`). It walks the
  rows; it skips a row with an `existing_path`; for each other row it notes the
  `similar_songs(row.result.title, library)` paths that are not yet noted and whose YouTube ID
  is not any result's own; it stops once `MAX_SIMILAR_SONGS` paths are noted. The docstring
  gives S1's reason in a line. `/search` stops passing `similar_songs` to the template.

**Card (`search_result.html`).**

- When `row.library_copies` is set: one line per copy, "In library: <strong>{{
  filename_from_path(path) }}</strong>", with a small green button
  `{% trans %}Queue{% endtrans %}`, class `library-copy-enqueue`, `data-file-path` the copy.
  Light info tint, as the box had (Bulma `is-info is-light`), no left border. On a phone it
  runs full width under the title row (mockup). On desktop, where the card is a row, it stays
  in the text column, not a third column beside it.
- Buttons: in-library `{% trans %}Queue{% endtrans %}`; otherwise
  `{% trans %}Add…{% endtrans %}` (U+2026, one character). Class names stay. The catalogs are
  not regenerated; "Add…" shows in English until they are.

**Search box (`search.html`).**

- `#queue-form` and `#container_search_form` become one GET form to `search.search`: a text
  input `name="search_string"`, `autocomplete="off"` (S3), `enterkeyhint="search"`, its
  `value` the query from the server (`{{ search_string or '' }}`; replaces the URL-param
  JS at line 384); and the Search button as the submit. A submit handler keeps today's
  behaviour: a blank query does nothing; otherwise show `#searching_loader` with the term,
  disable the button, hide the old results.
- Enter submits through the form. Delete the document-wide Enter handler, which also stops
  Enter in the direct-URL box from running a search. The lyrics box has its own handler
  (line 856) and is unaffected.
- The return-visit restore (line 404) fills the new input from `pikaraoke_search_term`. Clear
  empties the input, removes both keys and the results, as today, minus the selectize call.
- Delete: the help hint; `#add-queue-link` and its handler; `.song_added_by` and its fill
  (line 524); the selectize includes, setup and CSS (check `.row` is used nowhere else on the
  page before removing it); `static/selectize-0.12.6.min.js`, `static/selectize.min.css`;
  `/autocomplete` and `AutocompleteQuery`; the dead thumbnail cycling and its `i` global (S4).

**Add-to-queue box (`search.html`).**

- One checkbox `#add-to-queue`, labelled `{% trans %}Add to queue after download{% endtrans %}`,
  `checked` in the markup, first in `#advanced-settings`, with a rule between it and the
  direct URL (mockup). Delete `#add-to-queue-search` and `#add-to-queue-direct`. Update the
  translator `MSG` comment.
- `downloadSong` and `postDownload` read `#add-to-queue`. `#advanced-settings` is hidden but
  always on the page, so both read a real tick whether or not results are showing (the case
  `58ccd63` fixed). Keep it that way: the box must not move into anything rendered only with
  results.
- sessionStorage key `pikaraoke_add_to_queue`: on change write `"true"` or `"false"`; on load
  untick only when it reads `"false"`. The inline script runs again on every SPA visit, so the
  load step covers moving between pages. Delete `restoreCheckboxStates` and the cookie write.
  Nothing reads the old cookie; it is left to expire.

### Not doing

- Notes on Show more's cards (S2).
- Searching the library by its own song names on this page. A library song YouTube doesn't
  return for that search, or one with no YouTube ID in its name, is queued from Browse.
- A label on in-library cards beyond the top place and the green Queue button.
- Regenerating the translation catalogs.
- The open issue "A restored search page can show a stuck card".

### Commits

5. **`feat(search): songs already in the library come first, and a library copy is noted on
   its card`.** `routes/search.py`, `search_result.html` (note line; its button already
   "Queue"), `search.html` (delete the box and `.similar-song` CSS; the handler becomes
   `.library-copy-enqueue`), tests. Rewrite the "Already in the library" tests for the note,
   through the route as today:
   - an in-library card the ranking put below an official video comes first; two in-library
     cards keep their ranking order; badges are unchanged;
   - `/search/more`: a second-page in-library card is first in the returned batch;
   - a copy is noted inside the `<li>` of the card it matched; a copy matching several cards
     is noted on the first only; a card that is itself in the library is skipped and the copy
     goes to the next match; at most three copies on the page; no note when nothing matches;
     no note for a copy whose ID is a result's own; Show more's cards carry none.
6. **`feat(search): the search box drops the library dropdown and the help hint`.**
   `search.html`, the two static files, `routes/search.py`. Tests: the bare page has a GET form
   to `/search` with a `search_string` text input marked `autocomplete="off"`, and no
   "selectize" anywhere; a results page fills the input with the query, a query with `"` and
   `<` escaped in the attribute; `/autocomplete` is gone (404).
   `test_the_saved_search_term_is_a_script_string_of_the_query` must keep passing.
7. **`feat(search): one "Add to queue after download" box in Advanced`.** `search.html`. Test:
   exactly one `id="add-to-queue"`, checked, inside `#advanced-settings`; neither old id is on
   the page. If the `ui-check` skill can drive it, also check: untick, SPA to Queue and back,
   still unticked; a download POST then sends `queue: false`; a fresh browser context starts
   ticked. Otherwise leave it to Ken's checks and say so in the Results row.
8. **`feat(search): result buttons read Queue and Add…`.** `search_result.html`; test
   assertions on button text follow.

**Stop after commit 8** (and its Results row). Don't land, push or retire anything. Report a
Review-due checkpoint for commits 5-8: multi-file and a script rewrite, so it is due.

### Manual checks, Part 2 (Ken, on a phone)

- [ ] A song you own by its exact video: that card is first, above the official one, with a
      green Queue button that queues it.
- [ ] A song you own under another upload: the first card matching it shows "In library:
      <name>" with Queue; no "Already in the library" box; that card's Add… opens the dialog.
- [ ] Typing in the search box opens no list (neither library songs nor past searches); Enter
      and Search both run it; Clear empties it.
- [ ] No help hint under the search box.
- [ ] Advanced: "Add to queue after download" is ticked, above the direct URL; nothing sits
      above the results.
- [ ] Untick it, go to Queue and back: still unticked; a song downloaded now is not queued.
      Close the tab and open the page again: ticked.
- [ ] A direct-URL download with the box ticked is queued, from a fresh Search page with no
      results showing.
- [ ] Show more: a card you own on the second page lands first in the appended batch.

## Measurements (2026-11-11)

60 searches built from the library (35 "artist title", 10 title only, 13 film and stage
songs, 2 non-Latin), fetched with the app's own command, 30 rows each, once quoted and once
unquoted. Manual captions: one `yt-dlp --skip-download --print "%(subtitles)j"` per video,
counted when any `en*` language is present; six answers cross-checked against the app's
`get_preview_info`, all agreeing. All lookups are in `plans/search-official-captions/
captions.json` (video ID to manual subtitle languages; `[]` is none). Which lifts are "not the
record" is a reading of titles; nothing was listened to.

Manual English captions by kind of result, quoted searches, current code:

| kind | with captions | of |
|---|---|---|
| lifted video, the real official video (by title) | 32 | 40 |
| lifted video, something else (live, making-of, re-upload, duet version) | 4 | 27 |
| lifted audio | 1 | 34 |
| the artist's own lyric video (not lifted) | 0 | 9 |
| other lyric video, YouTube top 5 | 1 | 51 |
| live / cover / karaoke, YouTube top 5 | 3 | 50 |
| unmarked and not lifted, YouTube top 5 | 20 | 106 |

Alternate videos on the artist's own channel: 4 of 8 captioned ("Millennium 20 Edition" x2,
"Clean Version", "25th Anniversary Alternate"; not "2025 Version", "Perfect Symphony", two
Tenpenny re-recordings). Alternate audio: 0 of 8.

Quoted against unquoted: same first result in 51 of 60; zero rows in common for "how far ill
go moana" and "ill make a man out of you"; current-code outcome "video lifted" 44 quoted, 47
unquoted.

Prototype (the 11-11 draft of the rules, other acts from label channels only) over the 60
unquoted searches plus the 14 old fixtures, captions by tier:

| tier | with captions | of |
|---|---|---|
| original's video | 48 | 66 |
| - own channel | 40 | 54 |
| - label upload | 8 | 12 |
| other act's video (label channel) | 7 | 8 |
| original's audio | 2 | 48 |

An earlier run that also lifted other acts from their own channels (Ken's first wording of
decision 4): 10 of those 23 own-channel videos had captions, and most were different songs
of the same name.

Top of the page, 60 unquoted searches:

| order | top card captioned | any of top 3 captioned | captioned cards in top 3 |
|---|---|---|---|
| YouTube's | 40 | 47 | 53 of 180 |
| current code | 43 | 45 | 62 of 180 |
| prototype (11-11 draft) | 46 | 48 | 66 of 180 |

Tried and dropped: record length against the art track's as a live-version test (official
videos run 0.78x to 1.6x the record); keeping marked rows (lyrics, karaoke) out of the vote
(loses the pick for "s club 7", "vitamin c graduation", "soda pop", and swaps "how far ill go
moana" to the 2026 cast).

### Held-out check (2026-11-16)

40 searches not used to write the 11-11 draft (20 "artist title", 7 title only, 11 film and
stage songs, 2 non-Latin), captured unquoted on 2026-11-16 with the app's command, in
`plans/search-official-captions/holdout/` with a README and their caption lookups
(`holdout/captions.json`, 232 IDs, same lookup as above). Five share 5 to 7 video IDs with
the tuning data (the README names them) and are counted apart. Three (`toxic`, `what is this
feeling wicked`, `周杰倫 晴天`) first came back with no channel on 28 to 30 rows; a second
fetch the same day returned the channels, and those captures are the ones kept.

"11-11 draft" is the prototype at `eae97c8`. "Revised" is the rules in this plan. The
revisions were written from the faults this set exposed, so the revised rows below are not a
held-out measurement; only the draft's rows are.

Top of the page:

| order | top card captioned | any of top 3 captioned | captioned cards in top 3 |
|---|---|---|---|
| **35 held-out** | | | |
| YouTube's | 14 | 19 | 22 of 105 |
| current code | 13 | 19 | 20 of 105 |
| 11-11 draft, after commit 2 | 13 | 17 | 18 of 105 |
| 11-11 draft, after commit 3 | 13 | 18 | 19 of 105 |
| revised, after commit 2 | 14 | 21 | 24 of 105 |
| revised, after commit 3 | 16 | 21 | 26 of 105 |
| **5 overlapping** | | | |
| YouTube's | 5 | 5 | 6 of 15 |
| current code, draft and revised (all the same) | 5 | 5 | 8 of 15 |
| **30 unquoted fixtures** (2026-11-11 captures) | | | |
| YouTube's | 24 | 27 | 33 of 90 |
| current code | 24 | 25 | 36 of 90 |
| 11-11 draft, after commit 2 | 26 | 27 | 35 of 90 |
| 11-11 draft, after commit 3 | 26 | 27 | 39 of 90 |
| revised, after commit 2 | 26 | 27 | 38 of 90 |
| revised, after commit 3 | 26 | 27 | 40 of 90 |
| **14 quoted fixtures** (2026-11-08 captures) | | | |
| YouTube's | 10 | 13 | 15 of 42 |
| current code, draft and revised (all the same) | 11 | 12 | 14 of 42 |

The fixture rows needed 67 more lookups (2026-11-16, appended to `captions.json`), because
the revised order leaves cards in the top 3 that the draft's order never showed.

Captions by tier, after commit 3:

| tier | 11-11 draft, held-out 35 | revised, held-out 35 | revised, overlap 5 | revised, 44 fixtures |
|---|---|---|---|---|
| original's video, own channel | 10 of 21 | 12 of 23 | 7 of 7 | 31 of 40 |
| original's video, label upload | 2 of 7 | 3 of 4 | none | 9 of 9 |
| other act's video (label channel) | 4 of 5 | 6 of 8 | none | 6 of 7 |
| original's audio, lifted | 0 of 17 | 0 of 2 | none | 1 of 5 |
| original's audio, badge only | n/a | 0 of 17 | 0 of 4 | 1 of 34 |

Current code on the 35: lifted video 12 of 37, lifted audio 0 of 20. Of the 11 uncaptioned
own-channel videos the revised rules lift on the 35, ten are the official video itself (Bruno
Mars x3, Jessie J x2, Westlife x2, Justin Timberlake, Queen, Kelly Clarkson) and one is the
Calum Scott duet.

What the draft did on the held-out set, and the revision each led to:

| search | row | what the draft did | rule |
|---|---|---|---|
| adele send my love | `fk4BbF7B29w` (#1, captioned), Adele's video "Send My Love (To Your New Lover)" | not lifted: the subtitle read as unexplained | 9: the art track's words |
| adele send my love | `0put0_a--Ng` (#12), XL Recordings "Make You Feel My Love (Official Video)" | lifted to #1: two of three song words | 6: not both |
| under the sea little mermaid | `GC_mV1IpjWA` (#1, captioned), Samuel E. Wright's official video | not lifted, the 2023 cast lifted above it: `underthesea` tied the vote and its words were struck | 6: only the row's own names |
| we dont talk about bruno encanto and three more film searches | `Song (From "Film")` titles | credited "Song (From"; that name joined the originals; the official video got no badge | 1: quote outside brackets |
| do you want to build a snowman | `-9ZWF8vxmzM` (#25), Shine On Media "Behind-the-Scenes Music Video" | lifted to #1 | 5: hyphens |
| be our guest beauty and the beast; when will my life begin tangled | `Lt1Fck9DDp8` (#7), `Q9I_8S_h7GI` (#10), Disney¡Fan! "Official Music Video" | lifted to #1; current code does too | 7: decision 6 |
| justin timberlake sexyback | `-oqXwnXjgDE` (#13, captioned), own channel "(Edit)" | not lifted | 9: edit |
| kelly clarkson breakaway and 17 more | the original's audio | lifted above every unlifted card; 0 of 17 captioned | 12: decision 5 |

Label uploads by title alone (the branch decision 6 removes), both sets: 0 of 6 captioned
(Disney¡Fan! x3, Shine On Media, RHINO, Netflix Philippines).

Tried and not taken: other acts only from a channel that also carries the original (removes
both different-song lifts of rule 11's residue, and takes the badge off four right rows:
both "circle of life" casts, the 2019 "hakuna matata", Circle of Stars); own channel only
when it is an original's (removes the Calum Scott duet and two captioned duets in the
fixtures).

## Results log

| commit | hash | tests | notes |
|---|---|---|---|
| 1 `fix(search): the query goes to YouTube unquoted` | `37ba443` | 3849 passed (`tests/unit`) | Rebased onto `dev` `764df44` first (five plan/test commits, no conflicts; the plan's `1016e20` base is now `764df44`). `youtube_dl.py:249` and the assertion at `test_youtube_dl.py:473` only. |
| `test(official_rank): six held-out searches frozen as fixtures` | `d249353` | no suite run on its own (data files only) | Six files copied unchanged from `holdout/`; each has 30 rows and parses with no row dropped. |
| 2 `feat(official_rank): label uploads and alternate videos lift, live sessions and re-uploads do not` | `ed3d12b` | 3996 passed (`tests/unit`) | Module vs prototype, `--no-other` state: full display order, every badge and the `Acts` fields (originals, record words, has-video) compared against a copy of `proto_rank2.py` bound to the pre-commit-2 module, on all 50 fixtures and all 40 held-out searches: 0 mismatches (check script not committed). Mutation check, not committed: 14 single-rule changes (rules 1, 2, 3, 5 and 8 once each; rule 6 three ways; rules 7, 9 and 12 twice each), each failed at least one test. `celebration kool and the gang`, built from synthetic rows (two verified rows titled `Kool & The Gang - Celebration (Official Video)` on `KoolandthegangShow`, one unverified filler): originals = {kool, thegang, koolandthegang}; the video is not lifted or badged and the order is unchanged, because the own-channel test needs equal names (`koolandthegangshow` is not `koolandthegang`). No rule bent; pinned as a known miss. The plan's synthetic line says `Other Song (from Film)` fails rule 6 for `song film`; in the prototype and the module it passes rule 6 (every song word is in the title), and as a video rule 9 stops it (`other` is unexplained), as an art track it is badged audio. The test pins the video case and a rule-6 case for song words only in brackets (`Alpha - Other Song (From Some Film)` for `some film`). `test_search_render.py`: the audio-and-video ordering test follows rule 12 (audio keeps its place); one new `/search/more` test for `Acts.has_video`. |
| 3 `feat(official_rank): a label channel's other cast of the song lifts after the original's` | `d02bce5` | 4008 passed (`tests/unit`) | Module vs prototype, other acts on: 0 mismatches over the same 90 searches. The eight fixtures with other acts' videos match the plan's column; the four 60-row fixtures lift nothing on page 2; every `_STAYS_PUT` row holds. Mutation check, not committed: eight rule-11 changes; one survived (the song check on the other-acts path had no test), a test was added and it is killed. The plan's commit-3 line says another act's video lifts "before its audio"; under decision 5 a lifted video of any tier keeps the original's audio in YouTube's place, so the test pins that. |
| 4 `docs(plans): open issues follows the search ranking changes` | `25a3f81` | n/a (docs; `tests/unit` last run at `d02bce5`) | The new "no channel on any row" entry already existed in the section ("YouTube sometimes drops the channel fields"), so it is updated in place (3 of 40 captures, no badges and no lifts) instead of duplicated. "A verified re-upload can be lifted" is struck with its closing commit, as the file's header asks, not deleted. |
| 5 `feat(search): songs already in the library come first, and a library copy is noted on its card` | | | |
| 6 `feat(search): the search box drops the library dropdown and the help hint` | | | |
| 7 `feat(search): one "Add to queue after download" box in Advanced` | | | |
| 8 `feat(search): result buttons read Queue and Add…` | | | |
| manual checks (Part 1 and Part 2) | | n/a | |
