# Held-out searches for `proto_rank2.py` (captured 2026-11-16)

Not used to write the 11-11 draft of the rules in `plans/search-official-captions.md`. The
rules were then revised from what these searches exposed (the plan's "Held-out check"), so
they are held out for the draft only.

- 40 `*.jsonl`: real `ytsearch30` captures, unquoted, in the fixture format (`id, url, title,
  channel, uploader, channel_is_verified, duration, description[:40]`), made with the app's own
  yt-dlp command minus the quotes. File stem = the query with `_` for spaces. Same format as
  `tests/unit/data/youtube_search/`, so `python plans/search-official-captions/proto_rank2.py
  plans/search-official-captions/holdout [--no-other]` runs on them.
- `captions.json` (232 IDs): video ID to manual subtitle languages (`[]` none, `null` yt-dlp
  could not read it), same lookup as the plan's Measurements. It covers only the IDs the
  analysis needs: YouTube's top 5, the top 5 of each ranking (current code, the 11-11 draft of
  the prototype and the revised one, each after commit 2 and after commit 3), and every row
  any of them lifts or badges. An ID missing from it was not looked up.
- `toxic`, `what_is_this_feeling_wicked` and `周杰倫_晴天` are second captures, made later the
  same day: the first came back with no channel on 28 to 30 rows.
- Six are also test fixtures (the plan's "Held-out fixtures"): `adele_send_my_love`,
  `under_the_sea_little_mermaid`, `we_dont_talk_about_bruno_encanto`,
  `do_you_want_to_build_a_snowman`, `justin_timberlake_sexyback`,
  `be_our_guest_beauty_and_the_beast`.

Mix: 20 "artist title", 7 title only, 11 film and stage songs, 2 non-Latin.

## Not fully held out

The 60 searches behind the plan's Measurements were not saved by query, so overlap is judged by
video IDs shared with `captions.json` (391 IDs) and the 44 fixtures. Five queries share 5 to 7
IDs, so they were most likely among the original 60: `nsync bye bye bye` (7), `lewis capaldi
someone you loved` (7), `backstreet boys larger than life` (6), `ed sheeran shape of you` (6),
`ed sheeran thinking out loud` (5). Report them apart from the other 35 (at most 4 shared IDs
each, from other searches by the same artist).
