# Search: lift the videos most likely to have captions, and stop lifting the wrong ones

Model: Claude Sonnet 5.5 (spec by Claude Fable 5.2, 2026-11-11)

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

Still in force from the old plan: video before audio; official lyric videos, live, remix,
karaoke and the like are not lifted unless the query asks for that version; the vote is taken
over the first page only; a query in a script the matching cannot read lifts nothing.

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
rule below, checked against all 44 fixtures. Write the module cleanly; the prototype is there
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
   letter or digit, so the apostrophe in "Don't" is not one. Square and `【】` brackets before
   the quote are dropped. A title with neither a separator nor a quote credits its channel, as
   today.
2. **The originals.** Count credits over the trusted rows of the first page, as today. The
   originals are every name tied for the most credits, when that count is at least 2. A tie is
   no longer "nobody": a duet's two singers and the pair tie ("Mena Massoud, Naomi Scott"), and
   so do two casts of a film song. None for a query the matching cannot read.
3. **Whose upload a row is.** The names it credits (rule 1, plus the channel for an art
   track or a title naming no one). Exception: a row on a "- Topic" channel is its channel's
   alone, because a cover's art track is titled "Song - Film" or "Original Artist - Song".
4. **Tier.** "Original" when the row's names include an original; otherwise "other" (commit 3).
5. **Not the record.** Today's exclude list, counted per mark beyond the query's, plus: demo,
   rehearsal, making of, footnotes, perform(s), performance.
6. **Is the song.** More than half the song words appear anywhere in the title, and at least
   one appears outside brackets. For the original tier the song words are the query words not
   inside an original's name, as today. (Today the whole check ignores brackets, so
   "speechless aladdin" misses "Naomi Scott - Speechless (from Aladdin)".)
7. **Comes from the act.** One of:
   - an art track;
   - **own channel**: a trusted channel whose name equals one of the row's names. The channel
     name is today's `_channel_artist`, then with trailing `official`, `vevo`, `music`, `tv`,
     `video(s)` stripped ("EminemMusic", "PhilosopherKingsVEVO") and a leading "the" dropped
     from both sides. Equal, not contained: today's substring test passes the fan channel
     "ePro Team: Support for Eminem & Shady Records";
   - **label upload**: a verified channel whose name ends in "VEVO" or has the word Records,
     Recordings or Label(s); or, for the original tier only, any verified channel whose title
     says official or audio (RHINO, Netflix). Never when one of the row's names has its own
     channel's video on the first page: then the row is a re-upload (7clouds' "Justin
     Timberlake - Suit & Tie (Official Video)").
8. **"Says official"** means: "official" followed, before the bracket closes, by "video",
   "audio" or "MV"; or "music video"; or "MV" / "M/V". A bare "official" does not count:
   "(Rosanna Pansino Official)".
9. **A video must say what it is.** Take the title, drop "feat./ft./featuring/with/from …" up
   to the bracket or segment end, and drop the query's words, words inside the row's names and
   the plain words (official music video audio hd hq 4k mv explicit clean only the a an of
   and). If anything is left, the title must say official (rule 8) or say version, edition or
   remaster(ed). "(O2 Arena)", "(AOL Sessions)", "@ The Tonight Show" fail; "(2025 Version)",
   "(Official HD Video)" pass. Skipped for audio (the fallback, never captioned either way) and
   for a title carrying a mark, which got this far only because the query asked for it
   ("bohemian rhapsody live" still lifts "(Live Aid 1985)").
10. **Kind.** Audio for an art track or a title with the word "audio"; otherwise video.
11. **Other acts (commit 3).** A row whose names include no original lifts as a video when
    its channel is a label channel by name (rule 7: verified, ends in "VEVO" or has Records,
    Recordings or Label(s)) and is not the act's own channel ("NataliaKillsVEVO" is Natalia
    Kills' own); every query word appears in its title or channel name; and rules 5, 6 (with
    all query words), the re-upload bar of rule 7, and 9 hold. Never its audio. Residue: a
    label channel's different song of the same name still lifts (Spinnin' Records' "Martin
    Solveig & Dragonette - Hello" for "hello"); one row across the 44 fixtures.
12. **Order.** The originals' videos, other acts' videos, the originals' audio, the rest.
    Stable within each. The badge stays "Official video" / "Official audio".

### Module shape

```python
@dataclass(frozen=True)
class Acts:
    """What the first page says: the original artist's names, and the acts whose own
    channel has a video of the song on that page."""
    originals: frozenset[str] = frozenset()
    own_channel: frozenset[str] = frozenset()

def read_first_page(results: Sequence[SearchResult], query: str) -> Acts: ...
def official_kind(result: SearchResult, query: str, acts: Acts) -> OfficialKind | None: ...
def official_first(results, query, acts) -> list[tuple[SearchResult, OfficialKind | None]]: ...
```

`pick_artist` goes; `read_first_page` replaces it, and `Acts()` is "nothing known". The tier
is internal to the module (`official_first` needs it to order; callers only see the kind).
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
- Changing audio lifts beyond the new marks: "Band Ver." and "Extended Version" art tracks
  still lift as audio, below every video.
- Known misses left as they are, each costing only YouTube's order: "for good wicked" and
  "popular wicked" (the vote picks the song's name or nothing), "colors of the wind" (the vote
  picks the film's name from karaoke channels), "soda pop kpop demon hunters".

## Fixtures

`tests/unit/data/youtube_search/` holds 44 files. The 14 from 2026-11-08 are quoted-search
captures. The 30 new ones are committed on this branch as `8187552` (on their own, ahead of the
tests that read them, because they cannot be captured again; it lands on `dev` with the rest).
They are real unquoted `ytsearch30` captures from 2026-11-11, cut to the same
fields (`id, url, title, channel, uploader, channel_is_verified, duration, description[:40]`).
File stem = the query with `_` for spaces, as before.

Position = YouTube's, 1-based. "Other acts' videos" is empty after commit 2 and as listed
after commit 3; everything else is the same after both.

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
| youre welcome moana | dwaynejohnson, moana | `79DijItQXMM` (#1), `5CQLqMebytM` (#6) | `0DLzyvT4eUo` (#10) | `khg-OuAtt5E` (#4) |
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
| vitamin c graduation | vitaminc | `tz_NxOF7RB4` (#1) | none | none |
| the philosopher kings cry | thephilosopherkings | `EUW0eDhKoxw` (#1) | none | none |
| golden kpop demon hunters | huntrx | `hohuFW0zQUw` (#16) | none | none |
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
table, so that table passes unchanged after commit 2.

Must stay unlifted, after commit 2 and after commit 3 (new fixtures):

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
| justin timberlake suit and tie | `8fWBQtknJdA` (#3) | 7clouds, "(Official Video)" | 7, re-upload |
| adele someone like you | `il-NdjTtUAI` (#25) | Casey Ford Alexander, "Adele - Someone Like You (Music Video)" | 7, re-upload |
| tenacious d tribute | `W4uqbxvOK2A` (#2) | own channel, "Tribute to "Tribute": … Fan Compilation" | 1 |
| tenacious d tribute | `qSf6JznfdkY` (#16) | own channel, "(1995 Demo Version - Official Audio)" | 5 |
| ed sheeran perfect | `eiDiKwbGfIY` (#3) | "Ed Sheeran and Andrea Bocelli" channel, Perfect Symphony | 7, re-upload |
| ed sheeran perfect | `fgcwFILyTVo` (#27) | own channel, "(Backstage Rehearsal)" | 5 |
| backstreet boys i want it that way | `nUhVJBCpPSM` (#28) | "SethDrums - Topic" cover art track | 3 |
| part of your world | `azpDUgf2RLc` (#27) | "Rosanna Pansino - Topic" cover art track | 3 |

Perfect Symphony is a real official video; it is lost to the re-upload rule because its
channel is a joint one. Accepted: it has no captions.

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
2. **`feat(official_rank): label uploads and alternate videos lift, live sessions and
   re-uploads do not`.** Rules 1-10 and 12, the `Acts` API, both routes, and the tests:
   - `_LIFTED` grows by the 30 new rows (originals as a set, videos, audio); the 14 old rows
     keep their IDs.
   - `_STAYS_PUT` grows by the table above.
   - Rewrite the tests that call `pick_artist`: a tie now names both; one trusted credit is
     still not enough; no trusted rows changes no order; the drift test compares sets.
   - Synthetic-row tests, one per rule that a fixture does not isolate: a quoted title
     credits the text before the quote and its bracket alias (rule 1); a channel named
     "Alpha Fans United" is not Alpha's (rule 7); "AlphaMusic" and "AlphaVEVO" are; a verified
     re-upload titled "(Official Video)" is not lifted when Alpha's own channel has the video
     and is lifted when it does not (rule 7); a bare "(Someone Official)" does not say official
     (rule 8); "Song (from Film)" passes the song check for "song film" and "Other Song (from
     Film)" does not (rule 6); "bohemian rhapsody live" still lifts "(Live Aid 1985)" (rule 9's
     exemption; this existing case must keep passing).
   - "celebration kool and the gang" from open-issues: add the case with the channel
     "KoolandthegangShow" and report in the Results log what it does. Do not bend a rule to
     make it pass.
   - Render tests in `test_search_render.py` follow the API change.
3. **`feat(official_rank): a label channel's other cast of the song lifts after the
   original's`.** Rule 11, the "other acts' videos" column for all 44 fixtures (five fixtures
   have rows), and synthetic tests: another act's video on a label channel lifts, after the
   original's videos and before its audio; the same video on that act's own channel does not,
   nor on its own "ActVEVO" channel; a query that names the original ("alpha some song") lifts
   no other act; another act's audio on a label channel is not lifted; a query the matching
   cannot read lifts nothing.
4. **`docs(plans): open issues follows the search ranking changes`.** In
   `plans/open-issues.md`, "Search results": remove or rewrite the entries this fixes ("A
   verified re-upload can be lifted" becomes the residue: a re-upload still lifts when the
   act's own channel is not on the first page; "A band whose channel spells its name another
   way" per what commit 2 found), and add the "Not doing" misses above. Point the section at
   this plan.

**Stop after commit 4** (and its Results row). Don't land, push or retire anything. Report a
Review-due checkpoint per CLAUDE.md for commits 1-4: multi-file, new algorithm, so it is due.
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
- [ ] Show more still appends about 30 cards with no duplicates.

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

Prototype (final rules, other acts from label channels only) over the 60 unquoted searches
plus the 14 old fixtures, captions by tier:

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
| prototype (final rules) | 46 | 48 | 66 of 180 |

Tried and dropped: record length against the art track's as a live-version test (official
videos run 0.78x to 1.6x the record); keeping marked rows (lyrics, karaoke) out of the vote
(loses the pick for "s club 7", "vitamin c graduation", "soda pop", and swaps "how far ill go
moana" to the 2026 cast).

## Results log

| commit | hash | tests | notes |
|---|---|---|---|
| 1 `fix(search): the query goes to YouTube unquoted` | | | |
| 2 `feat(official_rank): label uploads and alternate videos lift, live sessions and re-uploads do not` | | | |
| 3 `feat(official_rank): a label channel's other cast of the song lifts after the original's` | | | |
| 4 `docs(plans): open issues follows the search ranking changes` | | | |
| manual checks | | n/a | |
