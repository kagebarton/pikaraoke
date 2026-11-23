# Search: lift the videos most likely to have captions, and stop lifting the wrong ones

Model: Claude Sonnet 5.5 (spec by Claude Fable 5.2, 2026-11-11; rules revised 2026-11-16 after
the held-out check, see Measurements; Part 2, the search page layout, spec by Claude Opus 5.5,
2026-11-17; commit 9 and Part 3's rulings from the phone pages' style review, Claude Opus 5.5,
2026-11-18; Part 2b scoped and specced by Claude Opus 5.5, 2026-11-23)

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
   Official MV` credits `jungkook`. An opening quote is one of `' " ‘ “` not preceded by a
   letter (accented too) or digit, so the apostrophe in "Don't" is not one, or `「 『`, which
   never are. It must close ("Don't Stop 'Til You Get Enough" quotes nothing) and sit outside
   every bracket (a round, square or `【` bracket the title never closes runs to its end): in
   `Under the Sea (From "The Little Mermaid")` the quote names the film, not the song, and the
   title credits no one. Square and `【】` brackets before the quote are dropped. A title with neither a separator nor such
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
   rehearsal, making of, footnotes, perform(s), performance, unplugged. Hyphens read as
   spaces, in the title and the query alike, so "Behind-the-Scenes" carries the mark "behind
   the".
6. **Is the song.** More than half the song words appear anywhere in the title, and at least
   one appears outside brackets. (Today the whole check ignores brackets, so "speechless
   aladdin" misses "Naomi Scott - Speechless (from Aladdin)".) And the query may say more
   than the title ("let it go frozen" for the art track "Let It Go"), or the title more than
   the query, but not both: a title that lacks a song word may carry, outside its brackets,
   no word that rule 9 calls unexplained, except that here the record's own title explains
   nothing (as in the prototype). "Adele - Make You Feel My Love" is not "adele send
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
     `video(s)`, `show` stripped ("EminemMusic", "PhilosopherKingsVEVO",
     "KoolandthegangShow") and a leading "the" dropped from both sides. Equal, not contained:
     today's substring test passes the fan channel "ePro Team: Support for Eminem & Shady
     Records". A channel whose name reads as nothing ("Official Music") is no one's;
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
carries decisions 7-13 (its "Add…" predates decision 13's amendment to "Queue…"). Where
this section and the mockup differ, this section wins.

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
13. "Select" reads "Queue…": the dialog with the preview and the lyrics choice still opens
    first, and the ellipsis says so. Amended by Ken 2026-11-17 (was "Add…") once the
    dialog's own button became "Queue" (`download_modal_speed`), so the card and the dialog
    name the same action.

### Decisions (Ken, 2026-11-18): one look

From the style review across the seven phone-page branches (`plans/open-issues.md` on `dev`,
"Phone pages: one look"; numbers are that list's, prefixed L). Visual reference: the canvas
https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL (private to Ken), boards "Search: results",
"Search: Advanced open" and "Reference palette". For colours and buttons it wins over this
Part's mockup; this file wins over both.

- **L11. The card's "Queue…" is green** (`is-success`), like every Queue: green means a tap
  that queues (L1). Commit 9.
- L12 and L13, the card restyle and the dark In library row, wait for Part 3 (below), after
  `queue_phone` lands.

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
  `{% trans %}Queue…{% endtrans %}` (U+2026, one character). Class names stay. The catalogs are
  not regenerated; "Queue…" shows in English until they are.

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
8. **`feat(search): result buttons read Queue, and Queue… where the dialog opens`.**
   `search_result.html`; test assertions on button text follow.

**Stop after commit 8** (and its Results row). Don't land, push or retire anything. Report a
Review-due checkpoint for commits 5-8: multi-file and a script rewrite, so it is due.

9. **`fix(search): the card's Queue… is green, like every Queue`** (L11, added 2026-11-18 after
   the stop above). `search_result.html`: `search_result_items_select` gains `is-success`; the
   card test that pins each kind of card's button class follows. Then its Results row and stop
   again. If the review of commits 5-8 has not run yet, its line takes in commit 9; if it has,
   commit 9 is one class and the self-review covers it.

### Manual checks, Part 2 (Ken, on a phone)

- [ ] A song you own by its exact video: that card is first, above the official one, with a
      green Queue button that queues it.
- [ ] A song you own under another upload: the first card matching it shows "In library:
      <name>" with Queue; no "Already in the library" box; that card's Queue… opens the dialog.
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
- [ ] Every Queue and Queue… on the page is green (L11).

## Part 2b: the video previews on its card (after the rebase onto `dev`)

Proposed by Ken 2026-11-23. Today every thumbnail, in-library cards included, opens the download
dialog (`search.html`, the `.img-wrapper` click calls `openPreviewModal`). Guests will want to
watch a video on the page before committing to anything, as the thumbnail's play icon suggests.
The play button on a thumbnail plays that video in its card instead, on every card. Queue (owned
card) and Queue… (the dialog) are unchanged.

Spec by Claude Opus 5.5, 2026-11-23 (Spec, below); Sonnet runs it, the rebase included. Canvas,
approved by Ken 2026-11-23: https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL#artboard-SearchPreview,
"Search: card preview (Part 2b)", four states of a card (loading, playing, paused, preview
unavailable). Where the board and P6-P8 or the Spec differ (the board's caption has a tap on the
thumbnail start it, its bar has a fullscreen button and is 40 px tall), P6-P8 and the Spec win.

### Order

1. Rebase this branch onto `dev` first. That is already Stage 2 item 2 of the landing order
   (`plans/open-issues.md` on `dev`): it points `queueAfterDownload()` at commit 7's
   `#add-to-queue` and keeps `is-flash` on the dialog's flashes. The preview needs the rebase
   because it reuses the dialog's lookup, which is on `dev` only (`download_modal_speed`,
   landed 2026-11-21). The branch is on origin and gh-ssh (both at `bf3c86d6`), so the rebase
   needs a force-push.
2. Then this Part's commits (10-12), with their Results rows, before the branch lands.
   Building it on `dev` instead was ruled out: this branch rewrites the same card markup and
   script, so the same lines would conflict twice.

### Decisions (Ken, 2026-11-23)

- **P1. The dialog keeps its own player.** Not chosen: a dialog with only the thumbnail as a
  still header, about lyrics alone (one player on the page, less dialog code, but no watching
  while picking lyrics).
- **P2. The card's preview starts muted**, as the dialog's does; the player's speaker control
  unmutes it. Not chosen: starting with sound (the dialog would have changed to match).

### Assumptions (Opus, 2026-11-23, not ruled; reopen any by asking)

- A1. One card plays at a time. Tapping another card's play button, or opening the dialog, ends
  it (the card goes back to its thumbnail).
- A2. One yt-dlp lookup per video per page visit, shared by the card and the dialog
  (`/caption_check` already returns the link beside the caption answer, so no server change).
  A video previewed on its card opens the dialog with its caption answer and link in hand, and
  the dialog's Play starts at once. Only an answer with a link is kept; anything else is asked
  again on the next tap or open, as each dialog open does today. A link that fails to play is
  forgotten too, so a retry looks again.
- A3. The thumbnail stays until the video plays, its play button breathing while the lookup
  runs (the dialog's Play does the same). With no link, or a video that cannot play, the play
  button becomes a "Preview unavailable" notice; a tap on it tries again.
- A4. An owned card's thumbnail no longer reaches the dialog, so the card half of "A search
  card you already own can be downloaded again" (`plans/open-issues.md`) is fixed. The stale
  restored page half (a song downloaded since still shows Queue…) stays open.
- A5. An unmute lasts the page visit, as the dialog's does: the page has one card `<video>` per
  visit, so the next card it plays in starts with sound. Leaving the page and coming back starts
  muted again.
- A6. The bar is 44 px tall, not the board's 40, so its buttons are full tap size.

### Decisions (Ken, 2026-11-23): the playing card

- **P3. Sized for phones.** The player fills the thumbnail's frame, the card's full width on a
  phone. Nothing is done for the 200 px thumbnail on a wide screen.
- **P4. A pause is a pause, not an end.** The player stays in the card, paused; its play button
  resumes it. Only A1 (another card's play button, or the dialog) ends it. First ruled with "a
  second tap pauses"; P6 sets what pauses.
- **P5. Badges stay during the preview, clear of the player's controls.** Part 3's L17 In
  library badge (top-left) stays, smaller while the player is in the card so it covers less
  of the video (Ken, same day): canvas draws it 8 px from the corner, 4 px corners, padding
  3/7/3/5 px, a 13 px folder icon, 12 px bold text; the thumbnail keeps L17's full size.
  Approved as drawn (Ken, 2026-11-23): smaller only while the player is in the card, and
  L19's Official badge shrinks with it. Part 2b builds before Part 3, so on the card today
  only the duration badge exists; the shrink applies to L17's and L19's badges once Part 3
  adds them. The duration badge goes while the player is in the
  card (playing or paused), since the player's own time shows the length (Ken, amended the
  same day; first ruled as moved above the control bar). Drawn on the canvas board above,
  which Ken asked for in place of a ruling on whether to draw one.

### Decisions (Ken, 2026-11-23, while the spec was written): what starts and stops it

- **P6. Only the play button starts a preview**, so a stray tap starts nothing (Ken: "to
  prevent accidental taps, and users forgetting to stop previews"). The rest of the thumbnail
  does nothing and stops looking tappable. While a preview plays, any tap outside its control
  bar pauses it, a tap on the video itself included. A tap elsewhere while it is still loading
  cancels the start. A scroll is not a tap. Ken proposed the rule; Opus's reading of it (the
  tap on the video, the cancel while loading, scrolling) was put to him with P7 and stood.
- **P7. A forgotten preview pauses itself** when its card scrolls entirely off the screen, or
  the page is hidden (phone locked, app or tab switched). Nothing resumes by itself. Not chosen:
  only on a hidden page (a guest could listen while browsing other results), taps only.
- **P8. No fullscreen button.** An iPhone can only fullscreen a video by handing it to its own
  native player, a second path with its own exit, and the preview already fills a phone's width
  (P3). The seek bar stays, so a guest can skip an intro. Not chosen: the board's fullscreen
  button.
- The sketch's open question, settled by Opus with P6 (no phone trial needed): **the page draws
  its own control bar**, as the board does, and the `<video>` has no native controls. Taps on
  the browser's native controls reach the page as taps on the `<video>`, so the page could not
  tell them from a tap elsewhere, and P6 would pause on every control tap. On Android the native
  time also hides while the video plays, and P5 drops the duration badge because the bar shows
  the length. L20 already gives the bar its fill.

### What exists (checked 2026-11-23 on a trial merge of `dev` `f48dc939` and this branch `3ce787f9`)

- The trial merge conflicts in `routes/search.py`, `search.html` and
  `tests/unit/test_search_render.py`. A trial rebase stops first at `ed3d12be` (commit 2) in the
  test file. Resolved by the rules in Step 1, the merged tree is `7eaf9276` (Black-formatted;
  4465 unit tests pass).
- The dialog's lookup: `askCaptionCheck(d)` asks `/caption_check?yt_id=`, answered
  `{found, passed, failed, stream_url}`; its `answered` sets `d.caption` and `d.link` and starts
  the video if Play waits; `isCurrent(d)` drops an answer for a dialog that has closed. Nothing
  is kept: each open asks again.
- The dialog's video: `#modal-video` (`controls playsinline muted preload="metadata"`), covered
  by `#modal-thumb-layer` until its `playing` event; `startVideo`, `warnPlayFailed`,
  `showPreviewUnavailable`; a Play tap before the link plays the empty video once (iOS).
- The card: `.img-wrapper` (its `data-url` read by nothing) holds `.img-frame`, which holds the
  `<img>` and `.duration-badge` (z-index 3). The play icon is two pseudo-elements on
  `.img-wrapper` (an 80 px circle and fontello `\e800`), not an element. The wrapper has
  `cursor: pointer` and hover rules, and `$("#search-results").on("click.search",
  ".img-wrapper", ...)` opens the dialog.
- `saveSearchResults()` saves `#container_search_result`'s `outerHTML` after a submitted search
  and after Show more; the restore parses the copy with jQuery `.html()`. Probed 2026-11-23 in
  the `ui-check` Chromium: a copy of a playing `<video>` made by `cloneNode` or `innerHTML`
  requests the video again; one parsed by `DOMParser` requests nothing.
- Each visit's `$(document).off(".search")` drops the last visit's document handlers.
- Catalogs (last regenerated 2026-06-10): "Pause" and "Play" are translated in all 15. "Play
  preview" and "Preview unavailable" (the dialog's, from `download_modal_speed`) are in none,
  so the sketch's "already a catalog string" was wrong; they are on the page already, so no new
  msgid.
- The fontello set has `icon-play`, `icon-pause`, `icon-volume-up` and `icon-volume-down`, and
  no muted speaker. `home.html` has its own `fmtTime(s)` (m:ss); nothing is shared.
- The `ui-check` Chromium plays VP9/Opus WebM (not H.264). A Playwright route that fulfils the
  whole file plays it but cannot seek (the video restarts); one that answers `Range` with 206
  seeks (the recipe below). Probed 2026-11-23.

### Spec

Per-commit routine as Part 1 (pre-commit on the changed files, `tests/unit`, import smoke, a read
of `git diff --cached`, the CLAUDE.md self-review), a Results row in a separate plan-only commit,
and **stop after each** (the rebase, 10, 11, 12) for Ken.

#### Step 1: the rebase (no commit of its own)

`git rebase dev` from the worktree. The rules hold at every stop, so each rewritten commit is
whole, not only the last; after each stop's resolution, run
`tests/unit/test_search_render.py -q` before `git rebase --continue`.

1. `routes/search.py`: both routes go. `dev` removed `/preview`, `PreviewQuery` and
   `get_preview_info` from the import; the branch removed `/autocomplete` and
   `AutocompleteQuery`. Keep the branch's `official_rank` import (`Acts`, `read_first_page`).
2. `search.html` head: keep `dev`'s `library-pages.js` `<script>`; drop the selectize `<link>`
   and `<script>`.
3. `search.html` script: drop the selectize block and `dev`'s document-wide Enter handler (the
   `keypress.search` one with the `_dialog` guard). The branch's GET form submits on Enter, and
   the dialog's typed search has its own handler. Drop the dead thumbnail cycling, as the branch
   does.
4. The Advanced box (rewritten commit 7, `67d6a23b`): keep the branch's `sessionStorage` load and
   its change handler on `#add-to-queue`, and put `dev`'s line into that handler with its
   comment: `if (_dialog && !_dialog.sent) syncQueue();`. **Drop `setUserCookie();`**: `dev`
   deleted that function (`bf96982b`, the join form), so the call would throw at load and stop
   the rest of the script. Drop `.song_added_by`, `restoreCheckboxStates()` and the cookie, as
   the branch does.
5. Also in rewritten commit 7: `postDownload` keeps `dev`'s `queue` parameter (`queue: queue`;
   the Queue tap takes the box's state when tapped), and `queueAfterDownload()` reads
   `#add-to-queue`. That line auto-merges still reading `#add-to-queue-search`, which commit 7
   deletes; commit 7's test fails until it changes.
6. Keep `is-flash` wherever `dev` has it (`61460808`).
7. `test_search_render.py`: keep both sides' tests. The branch's
   `test_the_official_video_comes_first_and_audio_beside_it_keeps_its_place_with_a_badge`
   replaces `dev`'s `test_the_artists_official_video_and_audio_come_first_with_a_badge`.
8. `plans/open-issues.md`, if it stops there (branch commits `25a3f817`, `ce409d83`): keep both
   sides; where both edit one entry, `dev`'s later text wins.

Then:

- `git diff 7eaf9276 HEAD -- pikaraoke tests` is empty. `7eaf9276` is an unreachable tree that git
  may prune after two weeks: if `git cat-file -t 7eaf9276` fails, skip this and say so. If `dev`
  has moved past `f48dc939`, explain each difference by a `dev` commit.
- Every branch commit is still there: `git log --oneline dev..HEAD` against
  `git log --oneline 764df440..3ce787f9` plus this spec's commit; none dropped as empty.
- The full `tests/unit` suite, pre-commit on the files the rebase resolved, an import smoke.
- One `ui-check` pass (the fake search of the commit 6 and 7 rows, a port nobody uses;
  `/caption_check`, `/lyrics_search`, `/lyrics_select` and `/download` answered by the script):
  no console errors but thumbnail 404s; a thumbnail still opens the dialog (until commit 11);
  Advanced unticked, the dialog's button reads "Add to library" and sends `queue: false`;
  ticking the box with the dialog open turns it back to "Queue" (rule 4's line); Enter in the
  search box searches; Enter in the dialog's lyric box runs the lyric search, not a page search.
- Results row "rebase onto `dev`" (plan-only commit), then stop. **The force-push waits for
  Ken's OK**: `git push --force-with-lease=search_official_captions:bf3c86d6 gh-ssh
  search_official_captions`, then `git fetch origin` (the same GitHub repository).

#### Commit 10: `feat(search): one caption lookup per video per visit, shared by every dialog open`

`search.html` only (A2).

- `lookupVideo(id)` gives a video's `/caption_check` answer as a promise. One map per visit, a
  `var` in the inline script, so the SPA's next visit starts empty. The first ask makes the
  entry, and every ask while it is in flight shares it. Once settled it stays only if the answer
  has a `stream_url`; otherwise (no link, or an error, answered `{failed: true}` as today) it is
  removed, so the next ask asks again.
- `forgetVideo(id)` removes an entry. The dialog video's `error` handler calls it when the video
  has a source.
- `askCaptionCheck(d)` asks `lookupVideo(d.id)`; its `answered` and the `isCurrent(d)` check
  stay. The flow comment's step 2 says the lookup is kept for the visit.
- No pytest: script only, and the Results row says so.
- `ui-check`, counting `/caption_check` requests per ID: open card A's dialog, close, open again:
  one request, and the second open shows the caption answer at once and Play starts the video
  with no request. Card B answered `stream_url: null`: two opens, two requests. Card C answered
  with a link that 404s: Play shows "Preview unavailable"; reopened, it asks again. Card D with
  its answer delayed 1.5 s on a fresh visit: open, close before the answer, open again: one
  request, and the second dialog gets its answer.

#### Commit 11: `feat(search): a thumbnail's play button previews its video in the card`

`search_result.html`, `search.html`, `tests/unit/test_search_render.py`. P2-P6, P8, A1, A3-A6.

**Card** (`search_result.html`).

- `.img-frame` gains `<button type="button" class="card-play" aria-label="{{ _('Play preview')
  }}">` with the play icon: a 56 px circle in `rgba(0, 0, 0, 0.6)` (L20) with a white triangle,
  centred, as the board draws it. It replaces the wrapper's `::before` and `::after` overlay.
- `.img-wrapper` loses `data-url`, `cursor: pointer` and its hover dimming and scaling; on
  desktop the hover belongs to the button (P6).

**Player** (`search.html`). One `#card-player` per page, after the results block and outside
`#container_search_result`, like the dialog and for the same reason (extend that template
comment to name both). It holds a `<video playsinline muted preload="metadata">` with no
`controls` attribute, and the bar:

- along the frame's bottom, 44 px tall (A6), `rgba(0, 0, 0, 0.6)`;
- from the left: play/pause (`<button type="button">`), the time in 12 px white, the seek
  (`<input type="range">`: a 3 px `#5e6d6f` track, white fill, an 11 px white knob), and the
  speaker (`<button type="button">`). No fullscreen (P8).
- Icons inline SVG from the board: two pause bars, the play triangle, the speaker with an X
  while muted, and for sound on the same speaker with two arcs. The `aria-label`s swap in the
  script from `TEXT`: Play/Pause, Unmute/Mute; the seek's is "Seek".

**States.** The previewing `<li>` carries `data-preview`; the script holds the one preview's
state in one object (the card, its ID, a sequence number), as `_dialog` does.

| `data-preview` | the frame shows | the play button | duration badge |
|---|---|---|---|
| (none) | the thumbnail | the play icon | shown |
| `loading` | the thumbnail; the player is in the frame but transparent and takes no taps (it stays rendered, as the dialog's video does under its thumbnail layer, so `play()` works) | breathing, the dialog's `breathe` (reduced motion: steady at half) | shown |
| `playing` | the player and its bar | hidden | hidden (P5) |
| `paused` | the player, paused, and its bar | shown over the video; resumes it | hidden |
| `unavailable` | the thumbnail; the player back in its home | becomes the "Preview unavailable" notice (the board's pill); a tap tries again | shown |

`playing` and `paused` follow the video's own `playing` and `pause` events, not the taps, so a
pause the browser makes (the end of the video, a page restored from the back-forward cache)
shows as paused. A video that ends is paused; its play button plays it again from the start.
Part 3 hangs P5's badge shrink on `li[data-preview="playing"]` and `li[data-preview="paused"]`.

**Rules.**

- Start: a click on a card's play button, the card idle or unavailable, ends any other preview
  (A1), moves the player into this card's `.img-frame`, sets `loading`, and asks
  `lookupVideo`. Inside the tap: with a kept link, set it and `play()`; without one, `play()`
  the empty video and pause it once it starts, as the dialog's Play does (iOS ties `play()` to
  the tap). When the answer arrives, dropped unless this preview is still the current one and
  the player is still on the page: a link is set, `load()`ed and `play()`ed; no link is
  `unavailable`. A refused `play()` (an autoplay block) goes back to idle, so the next tap, a
  fresh gesture, tries again. An `AbortError` is expected and not logged (`warnPlayFailed`).
- A click on the play button of the paused card resumes it; a click on the loading card's own
  play button does nothing. The bar's play/pause plays or pauses.
- A click on the playing video pauses it, bound on the `<video>` itself. On the video and not
  through the rule below, because the tap that pauses would otherwise be followed by a click,
  which on an iPhone can land on the play button that the pause has just shown, and resume it.
- A `pointerup` anywhere else on the page pauses a `playing` preview, or cancels a `loading`
  one (back to idle; its late answer is dropped). It ignores a `pointerup` inside
  `#card-player` and on the previewing card's own play button. `pointerup`, not `click`:
  Safari on an iPhone does not bubble a click on a plain element up to the document, and a
  scroll ends in `pointercancel`, not `pointerup`, so scrolling does not pause (P6). Primary
  pointer only. Bind it on `document` in the `.search` namespace, so the next visit's
  `.off(".search")` removes it.
- End (the card back to idle; the player back in its home, hidden, its `src` removed and the
  video `load()`ed so the stream stops downloading): another card's play button (A1),
  `openPreviewModal` (A1, first thing it does), and Clear (before it removes the results).
- A video `error` while it has a source: `forgetVideo(id)`, then `unavailable`.
- Mute: the speaker toggles `muted`; its icon and label follow `volumechange`. Nothing resets
  it between cards (A5).
- Time: `m:ss / m:ss` (where it is / how long), from the video; a length the video does not
  report as finite shows the time alone. A local formatter, the app's second after `home.html`'s
  `fmtTime`. The seek's max is the length at `loadedmetadata`; `input` sets `currentTime`;
  `timeupdate` moves the knob except while the guest drags it.

**Saved copy.** `saveSearchResults()` saves a copy parsed with `DOMParser`, with `#card-player`
removed and every `data-preview` dropped: a `cloneNode` or `innerHTML` copy would request the
video again (What exists). A restored page shows every card idle. A copy saved before this
commit restores without play buttons until the next search; accepted (once, per open tab).

**Dialog.** The `.img-wrapper` click handler goes, with its comment ("Both thumbnail and Select
button open the preview modal"); the Queue… binding stays. The flow comment's step 1 says
Queue… opens the dialog, and step 4 that the link may be in hand already from the card's
preview.

**Tests** (`test_search_render.py`, through the routes as today):

- every card, owned or not, from `/search` and from `/search/more`, has exactly one
  `<button type="button"` of class `card-play`, with an `aria-label`, inside its `.img-frame`;
  no card has `data-url`;
- `#card-player` is on the bare page and on a results page exactly once, not inside
  `#container_search_result` (`_ancestor_ids`); its `<video>` has `playsinline` and `muted`
  and no `controls`; the bar's buttons are `type="button"` with an `aria-label`, and the seek is
  `type="range"` with an `aria-label`.

**`ui-check`.** The fake search of the commit 6 and 7 rows, a port nobody uses, a
`p.devices["Pixel 7"]` context and `page.tap`. `/caption_check` answered by the script per ID:
for most, a link to `http://preview.test/clip.webm`; for one, `stream_url: null`; for one, a
link that 404s; one answer delayed 1.5 s. `/lyrics_search`, `/lyrics_select` and `/download`
answered too. The clip is a 10 s VP9/Opus WebM made in the scratchpad
(`ffmpeg -f lavfi -i testsrc=duration=10:size=640x360:rate=25 -f lavfi -i
sine=frequency=440:duration=10 -c:v libvpx-vp9 -b:v 200k -c:a libopus -shortest clip.webm`),
served by a route that answers `Range`:

```python
def serve_clip(route):
    m = re.match(r"bytes=(\d+)-(\d*)", route.request.headers.get("range", ""))
    if not m:
        return route.fulfill(body=DATA, content_type="video/webm", headers={"Accept-Ranges": "bytes"})
    start, end = int(m.group(1)), int(m.group(2) or len(DATA) - 1)
    route.fulfill(status=206, body=DATA[start : end + 1], content_type="video/webm",
                  headers={"Accept-Ranges": "bytes", "Content-Range": f"bytes {start}-{end}/{len(DATA)}"})
```

1. A tap on a thumbnail away from its play button: no dialog, no request, nothing changes.
2. Its play button: `loading` and the button breathing (the delayed answer), then playing in the
   card: `paused` false, `muted` true, the bar shown, the duration badge hidden, no dialog, one
   `/caption_check` request.
3. The speaker unmutes and mutes, its label following; the seek moves `currentTime`.
4. A tap on the middle of the playing video: paused, and still paused 1 s later; the play
   button shows, and a tap on it resumes. The bar's play/pause pauses and plays.
5. While it plays, a tap on the search box, then on the page heading, then on another card's
   title: each pauses it.
6. A vertical touch drag that scrolls the page (CDP `Input.dispatchTouchEvent`) while it plays:
   still playing.
7. The delayed answer: a play tap, then a tap elsewhere before the answer: idle, and still idle
   after the answer arrives (nothing plays, no player in the card).
8. Card A playing, then card B's play button: A idle (no player in its frame), B plays.
9. An owned card plays; its Queue calls `/enqueue` and pauses the preview.
10. A playing, then A's Queue…: the dialog opens, A is idle, and the dialog's Play starts at once
    with no second `/caption_check` request.
11. The no-link card: "Preview unavailable" in its play button's place; a tap on it asks again
    (a second request). The 404-link card: unavailable after the video's error; a tap asks again.
12. A playing, then Show more: A keeps playing; the saved copy in `sessionStorage` holds no
    `<video>` and no `data-preview`, and the clip was requested no more often than before; SPA to
    Queue and back: every card idle, and a restored card plays.
13. Clear while playing: the results go, no console error; a new search works.
14. A screenshot at 1100 px wide of a playing card (P3 does nothing for it; it must only not
    break).
15. No console errors but thumbnail 404s and the 404 link.

#### Commit 12: `feat(search): a preview pauses itself off screen or on a hidden page`

`search.html` only. P7.

- One `IntersectionObserver` per visit watches the previewing card's `.img-frame` from start to
  end. When none of it is on the screen, the preview pauses (`playing`) or is cancelled
  (`loading`), as a tap elsewhere does.
- `visibilitychange` to `hidden` does the same. Bound on `document` with
  `.on("visibilitychange.search")`, so the next visit's `.off(".search")` removes it.
- Nothing resumes by itself when the card or the page comes back.
- No pytest (script only).
- `ui-check`: playing, then a card ten below scrolled into view: paused; scrolled back, still
  paused. Scrolled so half the frame is off the screen: still playing. Loading (the delayed
  answer), scrolled off: idle once the answer arrives. A synthetic `visibilitychange` with
  `document.visibilityState` overridden to `hidden` (like the review row's synthetic
  `pageshow`): paused. Then SPA to Queue and back and the same event with no preview: no error
  (the last visit's handler is gone).

**Stop after commit 12** (and its Results row). Don't land, push or retire anything. Report a
Review-due checkpoint for commits 10-12: a new state machine in the page script, so it is due.

### Not doing, Part 2b

- Badges (L17, L19, L20) and their shrink (P5): Part 3, which finds the `data-preview` hook.
- Fullscreen (P8). Anything for the 200 px thumbnail on a wide screen (P3).
- The stale restored page half of the owned-card issue (A4), and `/download` refusing an ID it
  owns (that issue's option 3).
- Regenerating the catalogs: "Play preview", "Preview unavailable", "Mute", "Unmute" and "Seek"
  show in English until they are.
- A shared time formatter with `home.html`.

### At landing, Part 2b (not Sonnet's)

- `plans/open-issues.md`: commit 11 fixes the card half of "A search card you already own can
  be downloaded again"; the Landing order's Stage 2 item 2 loses its Part 2b sentence.

### Manual checks, Part 2b (Ken, on a phone)

- [ ] A tap on a thumbnail away from its play button does nothing.
- [ ] A not-yet-downloaded card's play button plays its video in the card, muted; the speaker
      unmutes it; no dialog opens. Same for a card you own.
- [ ] A tap on the playing video pauses it; its play button resumes it; the bar's button pauses
      and plays; the seek bar moves through the video.
- [ ] A tap anywhere else (the search box, another card's title, an owned card's Queue) pauses
      it. Scrolling doesn't, until the card is entirely off the screen; it is paused when you
      scroll back. Locking the phone pauses it.
- [ ] While it plays or is paused, the duration badge is gone (the bar shows the length).
- [ ] A second card's play button stops the first.
- [ ] Unmute one card, then play another: it plays with sound (A5).
- [ ] A card previewed first, then Queue…: the dialog opens, the card's video stops, and the
      dialog's Play starts the video at once.
- [ ] Show more, then go to Queue and back: no card comes back mid-preview.

## Part 3: search page restyle (after `queue_phone` lands)

Ruled by Ken 2026-11-18 (L12 and L13 in `plans/open-issues.md` on `dev`, "Phone pages: one
look"); no spec yet. Visual reference: the canvas
https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL, boards "Search: results" and "Search:
Advanced open", and the download dialog's three boards.

- **L12. The card restyle is its own pass**, after `queue_phone` lands its shared stylesheet
  (row, slot and button styles). It takes the download dialog's controls with it: the Search
  button, the list and the input, and no card behind the content (`download_modal_speed`'s
  dialog still has the Search page's Bulma look). Order: `queue_phone` lands, then this pass,
  which carries L13. Partly reverses decision 8's light tint. What it restyles, from the
  review: the amber (`is-warning`) Search button, white inputs, 4 px corners, 40 px buttons;
  the Official tag and the In library note in `is-info is-light`, the app's only light
  surfaces; a third blue `#6cb8ea` for the YouTube link and a grey `#a3b0b2` for the channel;
  titles 16 px regular, not 17 px bold.
- **L13. The In library note becomes a dark row** (option A): `#282f2f`, 6 px corners, the
  Browse folder icon, "In library" over the file name, a full-size green Queue. On a card with
  a library match, the card's own button reads "Download…" in neutral grey (L4, the fill
  `#434d4e` from L15), to steer guests to the copy they have; cards without a match keep the
  green "Queue…" (L11). The dialog's button still reads "Queue" when opened from "Download…"
  (`download_modal_speed`, L7).
- **In-library songs need a more obvious highlight** (Ken, 2026-11-19, after the Part 2
  phone checks). Two cases, and L13 covers only the second: (a) a card that is itself in the
  library (`row.existing_path`) is first on the page and its button is the green Queue, but
  nothing else sets it apart from a `Queue…` card, so with "backstreet boys drowning" the
  owned official video reads as just another result; (b) the "In library" note, which L13
  already turns into a dark row with the folder icon. Candidates for (a) were an In library
  tag beside the Official tag, the same dark row, or a tinted card.
  - **L17. Ruled (Ken, 2026-11-23):** (a) gets an "In library" badge on the thumbnail's
    top-left corner: `#282f2f` chip (fill superseded by L20), 6 px corners, padding 6/12/6/10 px, a green `#2ecc71`
    18 px folder icon (the Browse icon), 15 px bold white text. Its own button stays the
    green Queue, and the lift (decision 7) keeps it first. (b) keeps L13's dark row; the two
    share the dark fill and the folder icon, not the shape. The aim is a nudge seen while
    scrolling, not text to read: no "ready now" line. Not chosen: the dark row on (a) too
    (mocked as option 1), a tinted card (green tint already means "your own rows" on Queue),
    and a pinned "Already in your library" section (decision 8 removed that box). Canvas:
    the "Search: results" artboard, first card. Lands in the Part 3 restyle with L13.
- **L18. The card's "YouTube ↗" link goes** (Ken, 2026-11-23). Upstream's, never ruled here:
  the thumbnail already opens the dialog's preview, and on a phone the link leaves the app
  for the YouTube app. Canvas: both Search boards drawn without it. After Part 2b the
  thumbnail's play button plays the video in the card itself; the reason holds.
- **Canvas drawing choices for Part 3** (Opus, 2026-11-23, not ruled; the plan only lists
  what goes): Search button neutral grey (`#434d4e`, `#5e6d6f` border, bold white), beside a
  dark `#282f2f` input, both 44 px with 6 px corners; Official tag a filled `#434d4e` chip
  with a check icon, 12 px bold white, so it is louder than the channel and quieter than the
  L17 badge (Ken's order: In library first, official second); "Search results for…" becomes a
  13 px `#b5bfc0` label, the rule above it goes; the Advanced panel is a `#282f2f` inset with
  no shadow, its disabled Download in L16's look with 6 px corners, not a pill; the page sits
  in the v2 `#343c3d` card under the guest nav bar. Ken rejected a thumbnail badge for
  Official (it would dilute the In library badge); reversed by L19.
- **L19. Official moves onto the thumbnail** (Ken, 2026-11-23, approved on the canvas).
  Guests should pick in-library songs first and official videos second, so the Official
  badge sits in the In library badge's top-left corner, after it when a card has both, and
  the order reads left to right. Same size and shape as L17's badge. Its icon is one
  verified-style check emblem (a scalloped badge with a white check) in two fills, for
  consistency (Ken): the palette's icon grey `#8c9b9d` beside In library, so green stays
  the loudest; the palette's Info `#3298dc` when Official is the only badge (Ken asked for a
  palette blue; the other, `#375a7f`, is the "chosen" blue and too dark on a badge). That
  gives Info a second job beside the running job on Processing; both are states, never
  buttons, and the palette board says so. The channel line drops the Official tag. The
  badge reads "Official video" or "Official audio", as the tag does today.
- **L20. One fill for every thumbnail badge** (Ken, 2026-11-23, approved on the canvas): In
  library, Official and the duration all sit on black at 60% (`rgba(0,0,0,0.6)`), the play
  circle's, the player bar's and Preview unavailable's. It replaces L17's solid `#282f2f`
  chip and the duration's 80%. 60% is the lightest that keeps the white text at 4.5:1 or
  better on a pure white frame (about 5.7:1; 50% gives about 3.9:1); the icons, not the fill,
  tell the badges apart. L13's In library row under a card is not a thumbnail badge and
  keeps its `#282f2f`. Being see-through, a badge reads near black on a dark thumbnail and
  mid grey on a bright one; Ken saw both on the canvas and kept it (a solid fill would look
  the same everywhere but cover the video again).
- Canvas for L17-L20 and Part 2b, consolidated 2026-11-23: "Search: results" (an owned card;
  Official alone on a near-white thumbnail; a Download… card with its In library row),
  "Search: Advanced open", and "Search: card preview (Part 2b)" (an owned official video with
  both badges on a near-white thumbnail, through loading, playing and paused; then Official
  alone, preview unavailable). The palette board's Info swatch and the Processing note name
  the Official check.
- **An owned card's thumbnail opens the download dialog**, whose Queue downloads the video
  again. Open, in `plans/open-issues.md` on `dev` ("A search card you already own can be
  downloaded again"); its fix may land in Part 3. Superseded (2026-11-23): Part 2b's in-card
  preview takes every thumbnail off the dialog (A4).
- L1 (one green, one amber), L15 and L16 (disabled: no fill, a faded border, a `#8c9b9d`
  label, no opacity fade) come from `bulma-dark.css` on `singer_defaults` (its Phase 5), via
  `dev`. The canvas draws Advanced's disabled Download in L16's look.

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
| review `fix(official_rank): review fixes for odd titles and channels` | `a97f945` | 4019 passed (`tests/unit`) | `/code-review 23ad51e..25a3f81`, 15 findings. Fixed: 3 (`unplugged` mark), 5 (guest/film drop stops at the segment end), 6 and 9 (a quote must close; `「 『` open after any character; Unicode letter check), 8 (an empty channel name is no one's), 10 (any unclosed bracket, first test of it), 12 (`read_first_page` returns `Acts()` for an unreadable query), 13 (test for rule 12's local half; the mutation `video_lifted = acts.has_video` now fails it), 15's dead `quote.start() == 0` check (gone with the quote rewrite); plus the open issue "KoolandthegangShow" (trailing `show` stripped; its known-miss test flipped to a lift). 11: the module matches the prototype (rule 6 does not subtract record words), so rule 6's wording is corrected, not the code. Each fix, patched in memory and all together, compared on all 84 captured searches (50 fixtures plus the 34 held-out captures not among them, first 30 rows) against `25a3f81`'s module: display order and every badge unchanged. The new tests fail on `25a3f81`'s module except the unclosed round bracket (already handled, untested) and the plain-guest control. Logged in open issues, not fixed: 1, 2 and 7 (a different song of the same name: act-less titles on an act's VEVO channel, exact ties), 4 ("from"/"with" brackets). Dropped: 14 (the fixture tables pin the vote by design), 15's tier scheme (mirrors the two tiers). |
| 5 `feat(search): songs already in the library come first, and a library copy is noted on its card` | `2f9b36f` | 4024 passed (`tests/unit`) | `_library_copies` became `_note_library_copies(songs, rows)`; `_search_rows` ends in a stable sort on `existing_path is None`. The card gained a `.search_result_items_body` wrapper around the title row and the notes, so on desktop the note stays in the text column and on a phone it sits under the title row; `.search_result_items_meta` lost its `flex: 1` to the wrapper. Mutation check, not committed: 5 single changes (lift removed, in-library skip removed, already-noted check removed, own-ID check removed, cap removed), each failed at least one test; the first run of the lift mutation left the "ranking order among themselves" test green, so a non-library card was put ahead of the two library ones. Fixtures for the official video need the Topic audio row too (one video alone is not badged). Not seen in a browser: the note's spacing and tint are left to Ken's phone checks. |
| 6 `feat(search): the search box drops the library dropdown and the help hint` | `39ad7fb` | 4027 passed (`tests/unit`) | The form wraps the input and the Search button only; the Clear link and the Advanced tick sit outside it, because a named tick inside a GET form would add `show-advanced=on` to the search URL (the plan said "one GET form" without placing them). Search is a `<button type="submit">`; the blank-query check trims, so a whitespace query does nothing. Dropped as orphaned: `#search-field`, `#container_queue_form`, `#queue-form`, the dead autofocus on `#search_result_selector`, and the `.off(".search")` comment stays where it was (still before every namespaced bind). `json` and `current_app` imports left with `/autocomplete`. Driven in headless Chromium through `ui-check` (the worktree on port 5591, `get_search_results` faked: 30 or 60 rows, one library file carrying a result's ID, one under another ID), all passed: bare page has the input and no selectize; blank and whitespace Enter stay put; Enter in the direct-URL box runs no search; Enter and the Search button both load `?search_string=adele+hello`; the box keeps the query; the library card is first and one note sits on the first non-library card that matches; the note's Queue calls `/enqueue` for the copy's path; Queue and back through the SPA restores the box and the results; Show more appends; Clear empties the box, removes the results and both session keys; at submit the loader shows the term and the button is disabled and loading. No console errors except 25 thumbnail 404s (the fake IDs). `/autocomplete` answers 404. Not checked: the browser Back button onto a page left mid-search (the old script disabled the link the same way before its form submit). |
| 7 `feat(search): one "Add to queue after download" box in Advanced` | `67d6a23` | 4029 passed (`tests/unit`) | The test runs on the bare page and on a results page: one `id="add-to-queue"`, checked, after `#advanced-settings` and before the direct URL box, neither old id anywhere in the page (script included). The cookie `add-to-queue-on-download` is no longer read or written; `restoreCheckboxStates` and the two-box sync are gone. The translator comment says what the box does without the old "while it downloads". `ui-check` (same fake-search app as commit 6; `/download`, `/lyrics_select`, `/preview` and `/caption_check` answered by the script so nothing downloads or writes a sidecar), all passed: starts ticked and first in Advanced; a direct download from a page with no results sends `queue: true`; unticked, then SPA to Queue and back: still unticked; a direct download then sends `queue: false`; the unticked state survives a full-page search; the dialog's download (the captions button) sends `queue: false` unticked and `queue: true` after re-ticking, with the card's own URL and title; the session key reads `"false"` then `"true"`; a fresh browser context starts ticked. Not checked: a real phone's tab close (a new context stands in for it). |
| 8 `feat(search): result buttons read Queue, and Queue… where the dialog opens` | `b1f2bc4` | 4029 passed (`tests/unit`) | Both card buttons are `{% trans %}` strings now (the in-library one was a bare "Add to Queue"). The card test pins the button text and that each kind of card has only its own button class; the note test pins its `Queue` button. Mutation check, not committed: putting `Select` or `Add to Queue` back each fails a test. Screenshots through `ui-check` (fake search, 390 px and 1100 px wide), which also settle commit 5's "not seen in a browser": at 390 px the library card shows a green `Queue`, a `Queue…` card shows a dark button, and the note sits full width under the title row; at 1100 px the note stays inside the text column, not a third column. Advanced shows the tick first, a rule, then the direct URL. One thing Ken may not expect: the note's Bulma `is-info is-light` renders as a solid blue bar in this app's dark theme, as the old "Already in the library" box did; the plan's "light tint" is not what shows. Left as the box had it. |
| 9 `fix(search): the card's Queue… is green, like every Queue` | `09ae6dd` | 4029 passed (`tests/unit`) | `search_result_items_select` gains `is-success`. The card test now pins `is-success` on both buttons (it pinned the class on neither); mutation check, not committed: taking the class off the `Queue…` button fails it. Review of commits 5-8 has not run, so its line takes in this commit (range `2f9b36f0^..09ae6dd`). Not looked at in a browser. |
| review `fix(search): review fixes for the restore, the toast close and stray spaces` | `af48f5a` | 4032 passed (`tests/unit`) | `/code-review high 2f9b36f0^..09ae6dd`, 10 findings, run by Claude Opus 5.5. Fixed: 1 (a search with no results restored the previous search's cards and term: the script now gets the query as `searchString`, restores only when it is `null`, and forgets the saved cards on an empty search; already on `dev`), 2 (base.html's close button hid every `.notification`, the cards' notes included: now bound by `.base-notification .delete` and hides its own box; the old `#notification-close` bind only ever reached the first of two elements with that ID), 3 (a persisted `pageshow` undoes the submit's wait state; already on `dev`), 4 (the trimmed query is written back before the native submit), 5 (one `list(k.song_manager.songs)` for the lift and the notes; on a closer read the two reads could not disagree, since the notes skip lifted rows and any song carrying a result's ID, so this is a simplification, not a race fix), 6 (no `similar_songs` call once three are noted), 7 (`songs=` and `genius_client=` dropped from `render_template`; neither read by search.html or base.html), 8 (`.search_result_items_download` rule gone), 9 (`In library:` inside `{% trans %}` with a MSG comment; a new test pins the file name still escaped inside the translated line). Logged in open issues, not fixed: 10 (a restored page shows the library as of the last render), folded into "A restored search page can show a stuck card". `ui-check` through a fake-search wrapper (worktree on port 5737, `09ae6dd` exported on 5738; `get_search_results` patched to build 30 rows from the test library: one carrying a library file's ID, one titled like another, query `nothing` gives `[]`), each check run on both: library card first and one translated note (both pass); a search for `nothing at all` after `ingrid` shows no cards and keeps its own term, and an SPA revisit then restores nothing (fixed pass, `09ae6dd` fails all three); `"   ingrid  "` sends `search_string=ingrid` and the box reads `ingrid` (fixed pass, `09ae6dd` fails); SPA revisit restores 30 cards and the term, and Show more after two revisits appends once to 60 (both); `showNotification` then its close: the toast hides and the note stays (fixed pass, `09ae6dd` hides the note); wait state forced by a test-bound `preventDefault` submit, then a synthetic `PageTransitionEvent('pageshow', {persisted: true})`: button re-enabled, loader hidden, results shown (fixed pass, `09ae6dd` fails all three); no console errors but thumbnail 404s for the fake IDs. Not checked: a real back/forward-cache restore (headless Chromium did not use the cache for this page, so Back reloaded it), and not on a real phone. |
| manual checks (Part 1 and Part 2) | `5c4e410` (the code Ken ran) | n/a | Ken, 2026-11-19, on Windows with the branch fetched from the VM, on a phone: every step of the procedure passed except Part 2's "a song you own under another upload" (the note), which did not show for "backstreet boys drowning". Not a fault: the library's `Backstreet Boys - Drowning---GZXHBgjQjNM.mp4` is result 1 on that page (the official video), so it is the exact-ID case (first, green Queue), and the note skips any library song whose ID is on the page. Ken has not seen the note on a phone. Run through the route's code on the VM against live results, the note appears for ID-less library files: "the last five years (2014) the schmuel song" notes `The Last Five Years (2014) - The Schmuel Song.mp4` on the first card that matches (14 library songs searched by their own titles; ID-carrying ones show no note). Side finding, not new: the title matching is loose ("Jay Chou - Sunny Day (Audio)" noted against the library's `Jay Chou 周杰倫 - 龍捲風 (Tornado)`; "Britney Spears - The Making of 'Oops!...I Did It Again'" against `Oops!...I Did It Again`), as `song_match.py` says it leans toward showing. Ken also asked for a clearer in-library highlight: noted in Part 3. Part 1's list has 14 items; the procedure gave Ken eight searches first (bts butter, how far ill go moana, part of your world, circle of life lion king, queen bohemian rhapsody, hello, nsync bye bye bye, dont stop believin) and Show more came through Part 2's step. Ken then ran the other five (speechless aladdin, backstreet boys shape of my heart, justin timberlake suit and tie, adele send my love, under the sea little mermaid) the same day: all good. All 14 Part 1 items passed. |
| rebase onto `dev` (Part 2b, Step 1) | tip `c851e077` (was `592b2496`; `dev` `f87eb3b3`) | 4465 passed (`tests/unit`) | `git rebase dev` of 35 commits (the 34 of `764df440..3ce787f9` and the Part 2b spec). Stopped three times: `ed3d12be` (commit 2; `test_search_render.py`, rule 7: both sides kept, the branch's official-video test in place of `dev`'s), `39ad7fbe` (commit 6; `routes/search.py` rule 1, `search.html` head, selectize block, `dev`'s Enter handler, the dead thumbnail cycling and the cookie lines per rules 2-4), `67d6a23b` (commit 7; rules 4 and 5: `#add-to-queue`'s handler carries `dev`'s `syncQueue()` line, no `setUserCookie()`, `postDownload` keeps `queue: queue`, `queueAfterDownload()` reads `#add-to-queue`). `plans/open-issues.md` did not stop. `test_search_render.py` run at each stop (28, 36, 38 passed). `git diff 7eaf9276 HEAD -- pikaraoke tests`: first 12 lines, one stray blank line in `search.html` that my commit 6 resolution left; fixed in commit 6 itself (a fixup autosquashed into it; the rebase stopped again at the fixup and at commit 7 over the same hunk, both resolved by dropping that one blank line), then empty. `dev` has moved from the trial's `f48dc939` to `f87eb3b3` by one plan-only commit, so no difference needed explaining. Commit list: `git log --format=%s dev..HEAD` before and after, 35 and 35, the subjects identical in order; none dropped. Pre-commit on `routes/search.py`, `search.html`, `test_search_render.py`: all passed, nothing rewritten. Import smoke of `routes.search` and `official_rank`: ok. `ui-check` (this worktree on port 5683; `get_search_results` faked to 30 rows, 60 for Show more, one library file carrying `vid00000003`; `/caption_check`, `/lyrics_search`, `/lyrics_select`, `/download` answered by the script; a `Pixel 7` context, `page.tap`), all passed: 30 cards with the owned one first; a thumbnail opens the dialog; Queue reads "Queue" with the box ticked; Advanced unticked, the button reads "Add to library" and `/download` carries `queue: false`; ticking the box with the dialog open (by a `change` event, the dialog covers the box) turns it back to "Queue"; Enter in the dialog's lyric box asks `/lyrics_search?q=` and the URL stays; Enter in the search box loads `?search_string=queen`; no console errors (thumbnails answered by the script too, so no 404s). Harness note: `uihelpers.new_page` sets only the `user` cookie, which `dev`'s join form no longer accepts (`#singer-modal` covers the page and every tap waits); the script joins by `POST /singer` and sets `user` and `singer_token` itself. Not pushed: the force-push waits for Ken's OK. |
| 10 `feat(search): one caption lookup per video per visit, shared by every dialog open` | `570a0ad6` | 4465 passed (`tests/unit`) | No pytest of its own (script only, as the spec says); the suite was run for the regression. `search.html` only: `lookupVideo(id)` (one promise per video in `_lookups`, a `var` in the inline script so each SPA visit starts empty; removed once settled unless the answer has a `stream_url`), `forgetVideo(id)` (called from the dialog video's `error` handler, inside its existing source check), `askCaptionCheck(d)` now `lookupVideo(d.id).then(...)` with `isCurrent(d)` kept, and flow comment step 2 says the answer with a link is kept for the visit. Import smoke: the fake app rendered the page. Pre-commit on `search.html`: passed, nothing rewritten. `ui-check` (this worktree on port 5683, fake search of 30 rows, `Pixel 7` context, `page.tap`; `/caption_check` counted per ID; opened by the card's Queue… button, which is the dialog's one opener until commit 11), 13 checks all passed: card A (good link), open, close, open again: 1 request, the caption view shown within 500 ms of the second open, Play started the video (`paused` false, `currentTime` > 0) with no request; card B (`stream_url: null`), two opens: 2 requests; card C (link that 404s): Play showed "Preview unavailable", 1 request, reopened: 2 requests; card D (answer held until the script released it, fresh page load): open, close at 0.3 s, open again, released at 1.8 s: 1 request, the second dialog got its answer; SPA to Queue and back, a new search, card A: 1 -> 2 requests (a new visit starts empty). Console errors: only the 404 for the bad link. Self-review: the diff is one read-through (a promise map and one call site), so the self-review covers it; no checkpoint is pending for it alone. |
