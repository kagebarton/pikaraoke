"""Unseen video titles: the first results of the frozen YouTube searches on branch
search_official_captions (tests/unit/data/youtube_search), minus videos in the library.

The builder was written while looking at the library's 206 titles; these it has not seen.
A result is kept when its title carries the searched song's title. usage: holdout.py <fixture dir> [-v]
"""
import json
import sys
from collections import Counter
from pathlib import Path

import builder
import gx
import run
from pikaraoke.lib.genius_lyrics import clean_genius_query

PER_SEARCH = 4
# search file -> (artist words accepted as the original act, or None when the search names none; title)
SONGS = {
    "adele_someone_like_you": ("Adele", "Someone Like You"), "someone_like_you": ("Adele", "Someone Like You"),
    "a_whole_new_world_aladdin": (None, "A Whole New World"),
    "backstreet_boys_i_want_it_that_way": ("Backstreet Boys", "I Want It That Way"),
    "backstreet_boys_shape_of_my_heart": ("Backstreet Boys", "Shape of My Heart"),
    "bad_guy": ("Billie Eilish", "bad guy"), "because_of_you": (None, "Because of You"),
    "bohemian_rhapsody": ("Queen", "Bohemian Rhapsody"), "queen_bohemian_rhapsody": ("Queen", "Bohemian Rhapsody"),
    "britney_spears_oops_i_did_it_again": ("Britney Spears", "Oops!...I Did It Again"),
    "bts_butter": ("BTS", "Butter"), "celine_dion_my_heart_will_go_on": ("Celine Dion", "My Heart Will Go On"),
    "circle_of_life_lion_king": (None, "Circle of Life"), "colbie_caillat_realize": ("Colbie Caillat", "Realize"),
    "dancing_queen": ("ABBA", "Dancing Queen"), "defying_gravity": (None, "Defying Gravity"),
    "dont_stop_believin": ("Journey", "Don't Stop Believin'"), "ed_sheeran_perfect": ("Ed Sheeran", "Perfect"),
    "eminem_lose_yourself": ("Eminem", "Lose Yourself"), "golden_kpop_demon_hunters": (None, "Golden"),
    "hallelujah": (None, "Hallelujah"), "hello": (None, "Hello"), "how_far_ill_go_moana": (None, "How Far I'll Go"),
    "john_legend_all_of_me": ("John Legend", "All of Me"), "jung_kook_seven": ("Jung Kook", "Seven"),
    "justin_timberlake_suit_and_tie": ("Justin Timberlake", "Suit & Tie"),
    "kelly_clarkson_because_of_you": ("Kelly Clarkson", "Because of You"), "let_it_go_frozen": (None, "Let It Go"),
    "let_it_go": (None, "Let It Go"), "mirrors": ("Justin Timberlake", "Mirrors"),
    "never_gonna_give_you_up": ("Rick Astley", "Never Gonna Give You Up"), "ne-yo_so_sick": ("Ne-Yo", "So Sick"),
    "part_of_your_world": (None, "Part of Your World"), "perfect": (None, "Perfect"),
    "rolling_in_the_deep": ("Adele", "Rolling in the Deep"), "seasons_of_love_rent": (None, "Seasons of Love"),
    "shallow_lady_gaga": ("Lady Gaga", "Shallow"), "speechless_aladdin": (None, "Speechless"),
    "tenacious_d_tribute": ("Tenacious D", "Tribute"), "tribute": ("Tenacious D", "Tribute"),
    "the_lonely_island_threw_it_on_the_ground": ("The Lonely Island", "Threw It on the Ground"),
    "the_philosopher_kings_cry": ("The Philosopher Kings", "Cry"), "vitamin_c_graduation": ("Vitamin C", "Graduation"),
    "youre_welcome_moana": (None, "You're Welcome"),
}
in_library = {r["id"] for r in gx.rows if r.get("id")}
videos, seen = [], set()
for path in sorted(Path(sys.argv[1]).glob("*.jsonl")):
    artist, title = SONGS[path.stem]
    kept = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        v = json.loads(line)
        if kept == PER_SEARCH or v["id"] in in_library or v["id"] in seen:
            continue
        if builder.squash(title) not in builder.squash(v["title"]):
            continue
        seen.add(v["id"])
        kept += 1
        videos.append({"yt_title": v["title"], "channel": v.get("channel"), "title": title, "alts": [], "artist": artist or "", "kind": "artist" if artist else "film", "genius": None})


def today(text):
    q = clean_genius_query(text)
    return gx.app_filter(gx.raw(q), q)[:8], 1, True


STRATEGIES = {
    "search page today": lambda v: today(v["yt_title"]),
    "prototype": lambda v: run.replay("proto", v["yt_title"], v["channel"], 3)[:3],
    "new builder": lambda v: run.replay("new", v["yt_title"], v["channel"], 3)[:3],
}
print(f"{len(videos)} unseen videos from {len(SONGS)} searches")
for name, play in STRATEGIES.items():
    tally, calls, notes = Counter(), 0, []
    for v in videos:
        ranked, n, sure = play(v)
        calls += n
        title_pos = next((i for i, h in enumerate(ranked, 1) if gx.correct(h, {**v, "kind": "film"})), None)
        full_pos = gx.position(ranked, v)
        tally["right title first"] += title_pos == 1
        tally["right title listed"] += title_pos is not None
        tally["no hits"] += not ranked
        if v["kind"] == "artist":
            tally["named act: songs"] += 1
            tally["named act: original act's page first"] += full_pos == 1
            if name != "search page today":
                tally["named act: preselected"] += sure
                tally["named act: preselected, not the original act"] += sure and full_pos != 1
        if title_pos != 1 or (v["kind"] == "artist" and full_pos != 1):
            notes.append(f"   {v['yt_title'][:62]!r} [{(v['channel'] or '')[:18]}] -> " + "; ".join(f"{h['title'][:24]} / {h['artist'][:22]}" for h in ranked[:2]))
    print(f"\n== {name}: {calls / len(videos):.2f} calls a video\n  " + ", ".join(f"{k} {v}" for k, v in tally.items()))
    if "-v" in sys.argv and name == "new builder":
        print("\n".join(notes))
    gx.save()
