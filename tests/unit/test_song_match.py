"""Unit tests for pikaraoke/lib/song_match.py -- title-only duplicate matching.

The library is the real 33-song one the rules were tuned on; the part-frequency
rule only means something against a realistic set. Nothing touches the disk.
"""

import os

import pytest

from pikaraoke.lib.song_manager import SongManager
from pikaraoke.lib.song_match import (
    SongIndex,
    group_similar,
    parse_title,
    similar_songs,
)

LIBRARY_FILES = [
    "#OutOfOz - 'For Good' Performed by Kristin Chenoweth and Idina Menzel _ WICKED the Musical---TZ0pXUb5jVU.mp4",
    "'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM.mp4",
    "'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q.mp4",
    "'Popular' - Wicked 20th Anniversary Edition _ WICKED the Musical---22QYya-LGDY.mp4",
    "Ariana Grande, John Legend - Beauty and the Beast (From Beauty and the Beast - Official Video)---axySrE0Kg6k.mp4",
    "Backstreet Boys - Incomplete (Official HD Video)---WVe80iZtlYU.mp4",
    "Backstreet Boys - More Than That---1OwfYjemrYw.mp4",
    "Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjABn8.mp4",
    "Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw.mp4",
    "Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg.mp4",
    "Ed Sheeran - Happier (Official Music Video)---iWZmdoY1aTE.mp4",
    # Non-breaking spaces and a soft hyphen, as YouTube served them.
    "Ed\xa0Sheeran\xa0&\xa0Rudimental\xad\xa0- Bloodstream\xa0[Official\xa0Music\xa0Video\xad\xa0YTMAs]---Orq_75kFi8I.mp4",
    "HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA.mp4",
    "Idina Menzel - Let It Go (from Frozen) (Official Video)---YVVTZgwYwVo.mp4",
    "Jessie J - Domino (Official Video)---UJtB55MaoD0.mp4",
    "Jodi Benson - Part of Your World (From 'The Little Mermaid')---SXKlJuO07eM.mp4",
    "Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY.mp4",
    "Justin Timberlake - Like I Love You (Official Video)---FQ3slUz7Jo8.mp4",
    "Justin Timberlake - Mirrors (Official Video)---uuZE_IRwLNI.mp4",
    "Justin Timberlake - Rock Your Body (Official Video)---TSVHoHyErBQ.mp4",
    "Justin Timberlake - Selfish (Official Video)---je0roKRn3nY.mp4",
    "Mena Massoud, Naomi Scott - A Whole New World (from Aladdin) (Official Video)---eitDnP0_83k.mp4",
    "Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY.mp4",
    "NSYNC - Bye Bye Bye (Official Video)---Eo-KmOd3i7s.mp4",
    "NSYNC - Paradise.mp4",
    "Naomi Scott - Speechless (from Aladdin) (Official Video)---mw5VIEIvuMI.mp4",
    "Pocahontas - Colors of the Wind (Blu-ray 1080p HD)---9ThO76peOw0.mp4",
    "Seasons of Love (HD)---UvyHuse6buY.mp4",
    "The Lion King - Can You Feel The Love Tonight---25QyCxVkXwQ.mp4",
    "The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fwLxDUQBdEg.mp4",
    "The Next Ten Minutes Lyrics---0j8kL24ph8U.mp4",
    "Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ.mp4",
    "ZAYN, Zhavia Ward - A Whole New World (End Title) (From 'Aladdin')---rg_zwK_sSEY.mp4",
]
LIBRARY_PATHS = [os.path.join("/songs", name) for name in LIBRARY_FILES]

BOTH_WHOLE_NEW_WORLDS = {"Mena Massoud", "ZAYN"}
BOTH_FOR_GOODS = {"#OutOfOz", "Wicked - For Good"}


def library_path(fragment: str) -> str:
    """The one library path whose file name contains ``fragment``."""
    matches = [path for path in LIBRARY_PATHS if fragment in os.path.basename(path)]
    assert len(matches) == 1, f"{fragment!r} matches {len(matches)} library files"
    return matches[0]


def library_paths(fragments: set[str]) -> set[str]:
    return {library_path(fragment) for fragment in fragments}


@pytest.fixture(scope="module")
def library() -> SongIndex:
    return SongIndex.from_songs(LIBRARY_PATHS)


class TestSearchAgainstLibrary:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("Aladdin - A Whole New World (Lyrics)", BOTH_WHOLE_NEW_WORLDS),
            ("A Whole New World - Aladdin | Karaoke Version", BOTH_WHOLE_NEW_WORLDS),
            ("Justin Timberlake - Mirrors (Lyrics)", {"Timberlake - Mirrors"}),
            ("Belle - Beauty and the Beast (Lyrics)", {"1991) - Belle"}),
            ("Bloodstream - Ed Sheeran & Rudimental (Lyrics)", {"Bloodstream"}),
            ("Wicked - Defying Gravity (Lyric Video)", {"'Defying Gravity'"}),
            ("I'll Make a Man Out of You - Mulan", {"Mulan _"}),
        ],
    )
    def test_finds_the_library_copy(self, library, title, expected):
        assert set(similar_songs(title, library)) == library_paths(expected)

    @pytest.mark.parametrize(
        "title",
        [
            "Justin Timberlake - Can't Stop The Feeling",
            "Ed Sheeran - Shape of You",
            "Backstreet Boys - I Want It That Way",
            "The Lion King - Circle of Life",
        ],
    )
    def test_song_not_in_library_matches_nothing(self, library, title):
        assert similar_songs(title, library) == []


class TestSharedPartRules:
    def test_part_in_three_library_titles_is_an_artist_not_a_song(self, library):
        # The artist trails, so only the 3+ rule (4 Timberlake titles) keeps it from matching.
        assert similar_songs("Cry Me a River - Justin Timberlake", library) == []

    def test_part_leading_both_titles_is_an_artist_not_a_song(self, library):
        # Two Backstreet Boys titles: under the 3+ rule's threshold, so the lead rule decides.
        assert similar_songs("Backstreet Boys - I Want It That Way", library) == []

    def test_quote_inside_brackets_is_a_film_not_a_part(self, library):
        # "In Summer (From 'Frozen')" must not match a search that merely says Frozen.
        found = similar_songs("Frozen - Let It Go", library)
        assert found == [library_path("Idina Menzel - Let It Go")]

    def test_quoted_title_matches_on_the_quote_alone(self, library):
        defying = "'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical"
        # Popular shares the rest of the title, which is not the song name.
        assert similar_songs(defying, library) == [library_path("'Defying Gravity'")]

    def test_apostrophes_in_words_are_not_a_quote(self):
        journey = SongIndex.from_songs(["/songs/Journey - Don't Stop Believin'---abcdefghijk.mp4"])
        # Curly apostrophes in the search; a straight-quote misread of the library title
        # would keep only "t Stop Believin" and miss this.
        assert similar_songs("Don’t Stop Believin’ - Journey", journey) == [
            "/songs/Journey - Don't Stop Believin'---abcdefghijk.mp4"
        ]


class TestParseTitle:
    def test_brackets_and_separators(self):
        parsed = parse_title("Josh Gad - In Summer (From 'Frozen') [HD]")
        assert parsed.parts == {"josh gad", "in summer"}
        assert parsed.lead == "josh gad"

    def test_yt_dlp_underscore_separator(self):
        assert parse_title("Mulan _ Make a Man _ @disneykids").parts == {
            "mulan",
            "make man",
            "disneykids",
        }

    def test_quote_outside_brackets_replaces_the_other_parts(self):
        parsed = parse_title("'Popular' - Wicked 20th Anniversary Edition")
        assert parsed.parts == {"popular"}
        assert parsed.lead == ""

    def test_contraction_does_not_close_a_quote(self):
        # "'Til" opens like a quote; "I'm" must not close it.
        assert parse_title("Friends - 'Til I'm Done").parts == {"friends", "til im done"}

    def test_short_parts_are_dropped(self):
        assert parse_title("U2 - One").parts == frozenset()


class TestGroupSimilar:
    def test_library_pairs_are_found_and_defying_gravity_is_not_popular(self, library):
        names = [SongManager.filename_from_path(path, tidy=False) for path in LIBRARY_PATHS]
        groups = group_similar(names, SongIndex.from_songs([]))

        found = [{LIBRARY_PATHS[i] for i in group} for group in groups]
        assert sorted(found, key=sorted) == sorted(
            [library_paths(BOTH_WHOLE_NEW_WORLDS), library_paths(BOTH_FOR_GOODS)], key=sorted
        )

    def test_uploads_of_one_song_group_and_the_rest_are_omitted(self):
        titles = [
            "Shape of You - Ed Sheeran (Lyrics)",
            "Mirrors - Justin Timberlake",
            "Ed Sheeran - Shape of You [Official Video]",
        ]
        assert group_similar(titles, SongIndex.from_songs([])) == [[0, 2]]

    def test_a_chain_of_matches_is_one_group(self):
        titles = [
            "Alpha Beta Gamma | Delta Song",
            "Delta Song | Epsilon Tune",
            "Epsilon Tune | Zeta Thing",
        ]
        assert group_similar(titles, SongIndex.from_songs([])) == [[0, 1, 2]]

    def test_an_artist_heavy_in_the_playlist_does_not_glue_its_songs(self):
        titles = [
            "Mirrors - Justin Timberlake",
            "Selfish - Justin Timberlake",
            "Rock Your Body - Justin Timberlake",
        ]
        assert group_similar(titles, SongIndex.from_songs([])) == []

    def test_library_titles_count_toward_a_parts_frequency(self, library):
        # "Justin Timberlake" is already in 4 library titles, so two more cannot group on it.
        titles = ["Mirrors - Justin Timberlake", "Selfish - Justin Timberlake"]
        assert group_similar(titles, library) == []
        assert group_similar(titles, SongIndex.from_songs([])) == [[0, 1]]
