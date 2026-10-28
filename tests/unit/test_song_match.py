"""Unit tests for pikaraoke/lib/song_match.py -- title-only duplicate matching.

The library is the real 33-song one the rules were tuned on; the part-frequency
rule only means something against a realistic set. Nothing touches the disk.
"""

import os

import pytest

from pikaraoke.lib.song_manager import SongManager
from pikaraoke.lib.song_match import (
    SimilarGroup,
    SongIndex,
    parse_title,
    similar_groups,
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


def found(title: str, *library_titles: str) -> list[str]:
    """Which of ``library_titles`` (display names, saved with an ID) look like ``title``."""
    names = {f"/songs/{name}---{i:011d}.mp4": name for i, name in enumerate(library_titles)}
    return [names[path] for path in similar_songs(title, SongIndex.from_songs(names))]


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
            ("Disney - A Whole New World | Karaoke", BOTH_WHOLE_NEW_WORLDS),
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


class TestSharedLead:
    """A part leading both titles is an artist only when each title goes on to something else."""

    @pytest.mark.parametrize(
        ("title", "library_titles", "expected"),
        [
            pytest.param(
                "Bohemian Rhapsody (Official Video)",
                ["Bohemian Rhapsody"],
                ["Bohemian Rhapsody"],
                id="no-separator",
            ),
            pytest.param(
                "Shape of You | Karaoke",
                ["Shape of You - Ed Sheeran"],
                ["Shape of You - Ed Sheeran"],
                id="noise-segment",
            ),
            pytest.param(
                "Mirrors - Justin Timberlake [HD]",
                [
                    "Justin Timberlake - Mirrors",
                    "Justin Timberlake - Selfish",
                    "Justin Timberlake - Like I Love You",
                    "Mirrors - Justin Timberlake (Lyrics)",
                ],
                ["Justin Timberlake - Mirrors", "Mirrors - Justin Timberlake (Lyrics)"],
                id="common-artist",
            ),
            pytest.param(
                "Snow Patrol - Run (Official Video)",
                ["Snow Patrol - Run"],
                ["Snow Patrol - Run"],
                id="short-song-name-same-song",
            ),
            pytest.param(
                "Snow Patrol - Run",
                ["Snow Patrol - Chasing Cars"],
                [],
                id="short-song-name-other-song",
            ),
            pytest.param(
                "Backstreet Boys - Larger Than Life",
                ["Backstreet Boys - Incomplete"],
                [],
                id="two-songs-one-artist",
            ),
        ],
    )
    def test_shared_lead(self, title, library_titles, expected):
        assert found(title, *library_titles) == expected


class TestQuotes:
    @pytest.mark.parametrize(
        ("title", "library_title"),
        [
            pytest.param(
                "Guns N' Roses \"Sweet Child O' Mine\" (Official)",
                "Guns N' Roses - Sweet Child O' Mine",
                id="double-quote-around-an-apostrophe",
            ),
            pytest.param(
                "Bobby Day 'Rockin' Robin'",
                "Bobby Day - Rockin' Robin",
                id="single-quote-around-an-apostrophe",
            ),
            pytest.param(
                "Kiss 'Rock 'n' Roll All Nite'",
                "KISS - Rock 'n' Roll All Nite",
                id="n-is-not-a-quote",
            ),
        ],
    )
    def test_quote_runs_to_the_last_matching_closer(self, title, library_title):
        assert found(title, library_title) == [library_title]

    def test_a_quote_closes_only_with_its_own_kind_of_mark(self):
        # The apostrophe of "'Til" has no closer; it must not pair with the double quote's.
        assert parse_title('\'Til Tuesday "Voices Carry"').parts == {"voices carry"}

    def test_curly_quotes_pair_with_each_other(self):
        assert parse_title("“Rockin’ Robin” - Bobby Day").parts == {"rockin robin"}

    def test_quote_shorter_than_a_part_is_parsed_by_segments(self):
        # 'Run' would be the only part, and too short to match anything: the title would
        # otherwise lose "snow patrol" and match nothing.
        assert parse_title("'Run' - Snow Patrol").parts == {"snow patrol"}

    def test_quotes_are_found_per_segment_not_across_a_separator(self):
        # Matched over the whole title, the greedy quote would run from the first mark to the
        # last and swallow the " - " between them.
        assert parse_title("'Defying Gravity' - Wicked 'Popular'").parts == {
            "defying gravity",
            "popular",
        }


class TestSeparators:
    @pytest.mark.parametrize("separator", ["｜", "－", "："], ids=["bar", "hyphen", "colon"])
    def test_fullwidth_separator_splits_like_its_ascii_form(self, separator):
        title = f"Perfect {separator} Ed Sheeran"
        assert found(title, "Ed Sheeran - Perfect") == ["Ed Sheeran - Perfect"]


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


def title_groups(titles: list[str], library: SongIndex) -> list[list[int]]:
    return [group.titles for group in similar_groups(titles, library)]


class TestSimilarGroups:
    def test_library_pairs_are_found_and_defying_gravity_is_not_popular(self):
        names = [SongManager.filename_from_path(path, tidy=False) for path in LIBRARY_PATHS]
        groups = similar_groups(names, SongIndex.from_songs([]))

        found = [{LIBRARY_PATHS[i] for i in group.titles} for group in groups]
        assert sorted(found, key=sorted) == sorted(
            [library_paths(BOTH_WHOLE_NEW_WORLDS), library_paths(BOTH_FOR_GOODS)], key=sorted
        )
        assert sorted(group.part for group in groups) == ["for good", "whole new world"]

    def test_uploads_of_one_song_group_and_the_rest_are_omitted(self):
        titles = [
            "Shape of You - Ed Sheeran (Lyrics)",
            "Mirrors - Justin Timberlake",
            "Ed Sheeran - Shape of You [Official Video]",
        ]
        assert title_groups(titles, SongIndex.from_songs([])) == [[0, 2]]

    def test_a_chain_of_matches_is_one_group(self):
        titles = [
            "Alpha Beta Gamma | Delta Song",
            "Delta Song | Epsilon Tune",
            "Epsilon Tune | Zeta Thing",
        ]
        assert title_groups(titles, SongIndex.from_songs([])) == [[0, 1, 2]]

    def test_an_artist_heavy_in_the_playlist_does_not_glue_its_songs(self):
        titles = [
            "Mirrors - Justin Timberlake",
            "Selfish - Justin Timberlake",
            "Rock Your Body - Justin Timberlake",
        ]
        assert title_groups(titles, SongIndex.from_songs([])) == []

    def test_library_titles_count_toward_a_parts_frequency(self, library):
        # "Justin Timberlake" is already in 4 library titles, so two more cannot group on it:
        # each only meets its own library song.
        titles = ["Mirrors - Justin Timberlake", "Selfish - Justin Timberlake"]
        assert title_groups(titles, library) == [[0], [1]]
        assert title_groups(titles, SongIndex.from_songs([])) == [[0, 1]]

    def test_three_uploads_of_one_song_are_one_group(self):
        # "shape of you" sits beside one other part in all three titles, so it is not an artist.
        titles = [
            "Shape of You - Ed Sheeran",
            "Ed Sheeran - Shape of You (Lyrics)",
            "Shape of You | Karaoke",
        ]

        [group] = similar_groups(titles, SongIndex.from_songs([]))

        assert (group.titles, group.part) == ([0, 1, 2], "shape of you")

    def test_a_title_holding_the_part_alone_does_not_make_it_common(self):
        # Two different partners are fine; the bare third title adds no partner.
        titles = [
            "Shape of You - Ed Sheeran",
            "Sing King - Shape of You",
            "Shape of You (Official)",
        ]
        assert title_groups(titles, SongIndex.from_songs([])) == [[0, 1, 2]]

    def test_uploads_that_only_meet_through_a_library_copy_group_with_it(self):
        # Both lead with the song name and differ after it, so they do not match each other;
        # the library copy (artist first) matches each.
        titles = ["Shape of You - Ed Sheeran", "Shape of You - Sing King"]
        library = SongIndex.from_songs(["/songs/Ed Sheeran - Shape of You---00000000000.mp4"])

        assert title_groups(titles, SongIndex.from_songs([])) == []
        assert similar_groups(titles, library) == [
            SimilarGroup(
                titles=[0, 1],
                songs=["/songs/Ed Sheeran - Shape of You---00000000000.mp4"],
                part="shape of you",
            )
        ]

    def test_a_partner_in_both_library_and_playlist_counts_once(self):
        # The library and the playlist both hold "shape of you" beside "sing king": two partners
        # in all (with "pop hits"), not three, so the song stays rare and all three titles group.
        library = SongIndex.from_songs(["/songs/Shape of You - Sing King---00000000000.mp4"])
        titles = ["Shape of You - Pop Hits", "Shape of You", "Shape of You | Sing King"]

        assert title_groups(titles, library) == [[0, 1, 2]]

    def test_a_pair_sharing_artist_and_song_is_headed_by_both(self):
        titles = ["Mirrors - Justin Timberlake", "Justin Timberlake - Mirrors [HD]"]

        [group] = similar_groups(titles, SongIndex.from_songs([]))

        assert group.part == "justin timberlake / mirrors"

    def test_a_title_groups_with_the_library_songs_it_looks_like(self, library):
        titles = ["Aladdin - A Whole New World (Lyrics)", "Ed Sheeran - Shape of You"]

        assert similar_groups(titles, library) == [
            SimilarGroup(
                titles=[0],
                songs=[library_path("Mena Massoud"), library_path("ZAYN")],
                part="whole new world",
            )
        ]

    def test_two_uploads_of_a_library_song_group_with_it(self, library):
        # "mirrors" sits beside "justin timberlake" in all three titles, so it stays rare
        # and the two uploads match each other as well as the library copy.
        titles = ["Mirrors - Justin Timberlake (Lyrics)", "Justin Timberlake - Mirrors [HD]"]

        assert similar_groups(titles, library) == [
            SimilarGroup(
                titles=[0, 1], songs=[library_path("Timberlake - Mirrors")], part="mirrors"
            )
        ]
