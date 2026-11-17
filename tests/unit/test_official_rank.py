"""Tests for lifting an original act's official uploads to the top of a search.

The fixtures are real ``ytsearch`` captures (``tests/unit/data/youtube_search``): 14 from
2026-11-08, 30 from 2026-11-11 and six held-out searches from 2026-11-16, frozen because
YouTube's live results differ from day to day. Each is loaded through ``_parse_search_line``, so
these tests also cover parsing a real yt-dlp row. The expected tables were read off the
captures, ranking their first page.
"""

from pathlib import Path

import pytest

from pikaraoke.lib.official_rank import (
    Acts,
    official_first,
    official_kind,
    read_first_page,
)
from pikaraoke.lib.youtube_dl import SearchResult, _parse_search_line

_FIXTURES = Path(__file__).parent / "data" / "youtube_search"

# The first page of every capture: the rows the app ranks and votes over.
_FIRST_PAGE = 30

# query, the originals the vote picks, official videos in lifted order, official audio in
# YouTube's order (it is lifted only when no video is)
_LIFTED = [
    ("bad guy", ("billieeilish",), ["DyDfgMOUjCI"], ["2pnXjQCegVc"]),
    ("bohemian rhapsody", ("queen",), ["fJ9rUzIMcZQ"], ["0TF3hFevWE8"]),
    ("dancing queen", ("abba",), ["xFrGuyw1V8s"], ["P5AqvKYYQEE"]),
    ("defying gravity", ("cynthiaerivo",), [], ["HxkLt1GXVsw"]),
    ("dont stop believin", ("journey",), [], ["_wXLKQCTuD0"]),
    ("hallelujah", ("leonardcohen",), [], ["ttEMYvpoR-k"]),
    ("hello", ("adele",), ["YQHsXMglC9A"], ["T1tl66trXTQ"]),
    ("let it go frozen", ("idinamenzel",), ["YVVTZgwYwVo"], ["FnpJBkAMk44"]),
    (
        "never gonna give you up",
        ("rickastley",),
        ["dQw4w9WgXcQ", "LLFhKaqnWwk", "RrESvSRNpeo"],
        ["3BFTio5296w"],
    ),
    ("queen bohemian rhapsody", ("queen",), ["fJ9rUzIMcZQ"], ["0TF3hFevWE8"]),
    ("rolling in the deep", ("adele",), ["rYEDA3JcQqw"], ["bDtjO-R0QSo"]),
    ("seasons of love rent", ("anthonyrapp",), [], ["1xGUTW3C3gE", "HLEPfySbfxQ"]),
    ("shallow lady gaga", ("ladygaga",), ["bo_efYhYU2A"], ["BpIf43m2ZQI"]),
    ("someone like you", ("adele",), ["hLQl3WQQoQ0"], ["22c3_LoIfZQ"]),
    ("bts butter", ("bts",), ["WMweEpGlu_U"], []),
    ("jung kook seven", ("jungkook",), ["QU9c0053UAU"], ["Vs64cZbeY88", "zj0O6-YvLhg"]),
    (
        "a whole new world aladdin",
        ("menamassoud", "menamassoudnaomiscott", "naomiscott"),
        ["eitDnP0_83k"],
        ["atc8RAtl-Ms"],
    ),
    (
        "part of your world",
        ("jodibenson", "thelittlemermaid"),
        ["SXKlJuO07eM"],
        ["sg1Y6Vxl6Nk", "ZYcV5oXlccc", "totRu4FjI74"],
    ),
    ("speechless aladdin", ("naomiscott",), ["mw5VIEIvuMI"], ["DwTogmKwYWo", "J8CVHdMvv30"]),
    ("how far ill go moana", ("auliicravalho",), ["cPAbx5kgCJo"], ["keGr19WWwoA"]),
    ("circle of life lion king", ("thelionking",), [], []),
    ("youre welcome moana", ("dwaynejohnson", "moana"), ["79DijItQXMM"], ["khg-OuAtt5E"]),
    ("backstreet boys shape of my heart", ("backstreetboys",), ["OT5msu-dap8"], []),
    ("john legend all of me", ("johnlegend",), ["450p7goxZqg", "xwsYvBYZcx4"], []),
    (
        "colbie caillat realize",
        ("colbiecaillat",),
        ["GlZxZ2n2zpw", "pwpHhN-vtRI", "u5Exxrl7frA"],
        [],
    ),
    (
        "kelly clarkson because of you",
        ("kellyclarkson",),
        ["Ra-Om7UMSJc", "o0oenkCT8EY"],
        ["C-IgZrOsEag"],
    ),
    ("britney spears oops i did it again", ("britneyspears",), ["CduA0TULnow"], ["OO0aTOIU_3w"]),
    ("ne-yo so sick", ("neyo",), ["IxszlJppRQI", "ub3y1Baw0ak"], []),
    ("eminem lose yourself", ("eminem",), ["xFYQQPAOz7Y"], []),
    (
        "justin timberlake suit and tie",
        ("justintimberlake",),
        ["IsUsVbTj2AY", "7tWvTW16atE"],
        ["cJzRZ0T5ewc", "0S0vamqBlek"],
    ),
    ("adele someone like you", ("adele",), ["hLQl3WQQoQ0"], ["22c3_LoIfZQ"]),
    ("tenacious d tribute", ("tenaciousd",), ["_lK4cX5xGiQ"], []),
    ("ed sheeran perfect", ("edsheeran",), ["2Vv-BfVoq4g"], ["817P8W8-mGE"]),
    (
        "backstreet boys i want it that way",
        ("backstreetboys",),
        ["4fndeDfaWCg", "VVB6FI8QTFg", "mAGGPgxl6qU", "GJhTjyc7A3Y"],
        ["z6Wq59qrdB0", "-aKJE1lanQk"],
    ),
    ("because of you", ("kellyclarkson",), ["Ra-Om7UMSJc", "o0oenkCT8EY"], ["C-IgZrOsEag"]),
    ("perfect", ("edsheeran",), ["2Vv-BfVoq4g"], ["817P8W8-mGE"]),
    ("let it go", ("idinamenzel",), ["YVVTZgwYwVo"], ["FnpJBkAMk44"]),
    ("mirrors", ("justintimberlake",), ["uuZE_IRwLNI"], ["U41KPUfOSFk"]),
    ("tribute", (), [], []),
    ("the lonely island threw it on the ground", ("thelonelyisland",), ["gAYL5H46QnQ"], []),
    ("vitamin c graduation", ("vitaminc",), [], []),
    ("the philosopher kings cry", ("thephilosopherkings",), ["EUW0eDhKoxw"], []),
    ("golden kpop demon hunters", ("huntrx",), [], []),
    (
        "celine dion my heart will go on",
        ("celinedion",),
        ["9bFHsd3o1w0", "bf-HGyke89Y"],
        ["mNsm2P0l_7Y", "cJnSrovvM74"],
    ),
    ("adele send my love", ("adele",), ["fk4BbF7B29w"], ["Fq-AHPOshKc"]),
    (
        "under the sea little mermaid",
        ("samuelewright", "underthesea"),
        ["GC_mV1IpjWA"],
        ["ChNJ_FMtSnk", "b32vFD5Acrc", "ZhFwcueYEKE"],
    ),
    ("we dont talk about bruno encanto", ("wedonttalkaboutbruno",), [], []),
    ("do you want to build a snowman", ("frozen",), [], []),
    ("justin timberlake sexyback", ("justintimberlake",), ["3gOHvDP_vCs", "-oqXwnXjgDE"], []),
    ("be our guest beauty and the beast", ("thebeast",), [], []),
]

# query, id of a row that looks official but must stay where YouTube put it, without a badge
_STAYS_PUT = [
    pytest.param("bohemian rhapsody", "ojRj2JK5oCI", id="cover-artists-own-video"),
    pytest.param("queen bohemian rhapsody", "LlPcnOjSByU", id="unverified-reupload"),
    pytest.param("queen bohemian rhapsody", "rY0WxgSXdEE", id="another-song"),
    pytest.param("hello", "mHONNcZbwDY", id="another-artist-same-title"),
    pytest.param("dancing queen", "-sVB91NTa4A", id="official-lyric-video"),
    pytest.param("rolling in the deep", "tW626Q6CFcI", id="acapella-on-page-2"),
    pytest.param("bts butter", "HbkBVxU5K5A", id="show-performance"),
    pytest.param("bts butter", "5dWxvUcEUEY", id="performance-rehearsal"),
    pytest.param("jung kook seven", "1QYBiNRu1ok", id="official-performance-video"),
    pytest.param("backstreet boys shape of my heart", "v1Q5SsHIuBY", id="arena-concert"),
    pytest.param("john legend all of me", "ftGQLvUwzjY", id="vevo-go-shows"),
    pytest.param("colbie caillat realize", "jDt2u2eJk3Q", id="aol-sessions"),
    pytest.param("kelly clarkson because of you", "P8dtX_t9mJc", id="soundcheck"),
    pytest.param("britney spears oops i did it again", "MHfCJT6hkZ4", id="vevo-footnotes"),
    pytest.param("ne-yo so sick", "XLtinWelxkE", id="making-of"),
    pytest.param("eminem lose yourself", "jNYR1ioecJY", id="fan-channel-live-set"),
    pytest.param("justin timberlake suit and tie", "8fWBQtknJdA", id="reupload-by-title"),
    pytest.param("adele someone like you", "il-NdjTtUAI", id="cover-music-video"),
    pytest.param("tenacious d tribute", "W4uqbxvOK2A", id="fan-compilation"),
    pytest.param("tenacious d tribute", "qSf6JznfdkY", id="demo-version"),
    pytest.param("ed sheeran perfect", "eiDiKwbGfIY", id="perfect-symphony"),
    pytest.param("ed sheeran perfect", "fgcwFILyTVo", id="backstage-rehearsal"),
    pytest.param("backstreet boys i want it that way", "nUhVJBCpPSM", id="cover-art-track"),
    pytest.param("part of your world", "azpDUgf2RLc", id="cover-art-track-of-a-film-song"),
    pytest.param("youre welcome moana", "5CQLqMebytM", id="fan-channel-music-video"),
    pytest.param("vitamin c graduation", "tz_NxOF7RB4", id="label-only-by-title"),
    pytest.param("golden kpop demon hunters", "hohuFW0zQUw", id="regional-channel-music-video"),
    pytest.param("adele send my love", "0put0_a--Ng", id="another-song-on-a-label"),
    pytest.param("adele send my love", "9IzKueQ2ZxY", id="another-song-as-art-track"),
    pytest.param("do you want to build a snowman", "-9ZWF8vxmzM", id="behind-the-scenes"),
    pytest.param("do you want to build a snowman", "KKP0Txebobg", id="stage-cast-audio-only"),
    pytest.param("be our guest beauty and the beast", "Lt1Fck9DDp8", id="fan-channel-typo-title"),
]

_SIXTY_ROW_FIXTURES = ["bohemian rhapsody", "hallelujah", "let it go frozen", "rolling in the deep"]


def _load(query: str) -> list[SearchResult]:
    path = _FIXTURES / f"{query.replace(' ', '_')}.jsonl"
    results = [_parse_search_line(line) for line in path.read_text().splitlines()]
    assert None not in results, f"{path.name} has a row the parser drops"
    return results


def _ids(ranked) -> list[str]:
    return [result.id for result, _ in ranked]


def _row(
    title: str, channel: str = "A Channel", verified: bool = True, description: str = ""
) -> SearchResult:
    return SearchResult(
        title=title,
        url="https://youtu.be/aaaaaaaaaaa",
        id="aaaaaaaaaaa",
        channel=channel,
        duration="3:00",
        channel_verified=verified,
        description=description,
    )


def _art(title: str, act: str = "Alpha") -> SearchResult:
    """A label-distributed art track, which YouTube files on the act's "- Topic" channel."""
    return _row(title, channel=f"{act} - Topic", verified=False)


def _unrelated(title: str = "Unrelated upload") -> SearchResult:
    return _row(title, verified=False)


def _kind(row: SearchResult, query: str = "some song", vote: tuple = ()):
    """The kind ``row`` gets on a page of itself and the rows that vote for Alpha (two art tracks
    unless ``vote`` says otherwise)."""
    page = [row, *(vote or (_art("Some Song"), _art("Some Song")))]
    return official_kind(row, query, read_first_page(page, query))


def _originals(rows: list[SearchResult], query: str = "some song") -> frozenset[str]:
    return read_first_page(rows, query).originals


def _titles(ranked) -> list[str]:
    return [result.title for result, _ in ranked]


# Fixtures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query, originals, videos, audio", _LIFTED, ids=[query for query, *_ in _LIFTED]
)
def test_lifts_the_originals_official_videos_and_badges_every_official_upload(
    query, originals, videos, audio
):
    results = _load(query)[:_FIRST_PAGE]
    acts = read_first_page(results, query)

    ranked = official_first(results, query, acts)

    assert acts.originals == frozenset(originals)
    assert acts.has_video == bool(videos)
    lifted = videos or audio  # audio is lifted only where no video is
    assert _ids(ranked)[: len(lifted)] == lifted
    assert {result.id: kind for result, kind in ranked if kind} == {
        **dict.fromkeys(videos, "video"),
        **dict.fromkeys(audio, "audio"),
    }


@pytest.mark.parametrize(
    "query, originals, videos, audio", _LIFTED, ids=[query for query, *_ in _LIFTED]
)
def test_everything_not_lifted_keeps_youtubes_order(query, originals, videos, audio):
    results = _load(query)[:_FIRST_PAGE]
    lifted = videos or audio

    ranked = official_first(results, query, read_first_page(results, query))

    assert _ids(ranked)[len(lifted) :] == [r.id for r in results if r.id not in lifted]


@pytest.mark.parametrize("query, video_id", _STAYS_PUT)
def test_an_upload_that_is_not_the_acts_record_is_not_badged(query, video_id):
    results = _load(query)
    acts = read_first_page(results[:_FIRST_PAGE], query)
    assert acts.originals  # else None would pass vacuously
    row = next(r for r in results if r.id == video_id)

    assert official_kind(row, query, acts) is None


@pytest.mark.parametrize("query", _SIXTY_ROW_FIXTURES)
def test_a_second_page_is_ranked_by_the_first_pages_vote_and_lifts_nothing(query):
    results = _load(query)
    assert len(results) == 2 * _FIRST_PAGE
    second_page = results[_FIRST_PAGE:]

    acts = read_first_page(results[:_FIRST_PAGE], query)

    assert acts.originals
    assert official_first(second_page, query, acts) == [(r, None) for r in second_page]


@pytest.mark.parametrize(
    "query, first_page_originals, all_rows_originals",
    [
        ("hallelujah", {"leonardcohen"}, {"oct2026"}),
        ("let it go frozen", {"idinamenzel"}, {"letitgo"}),
    ],
)
def test_the_vote_over_sixty_rows_drifts_so_it_is_taken_over_the_first_page(
    query, first_page_originals, all_rows_originals
):
    results = _load(query)

    assert read_first_page(results[:_FIRST_PAGE], query).originals == first_page_originals
    assert read_first_page(results, query).originals == all_rows_originals


# The vote (rules 1 and 2)
# ---------------------------------------------------------------------------


def test_a_tie_names_every_act_that_shares_the_most_credits():
    rows = [
        _row("Alpha - Some Song"),
        _row("Alpha - Some Song"),
        _row("Beta - Some Song"),
        _row("Beta - Some Song"),
    ]

    assert _originals(rows) == {"alpha", "beta"}


def test_one_trusted_credit_is_not_enough():
    assert _originals([_row("Alpha - Some Song")]) == frozenset()


def test_no_trusted_rows_names_no_one_and_changes_no_order():
    rows = [_row(f"Alpha - Some Song {i}", verified=False) for i in range(5)]
    acts = read_first_page(rows, "some song")

    assert acts == Acts()
    assert official_first(rows, "some song", acts) == [(r, None) for r in rows]


@pytest.mark.parametrize(
    "titles, originals",
    [
        pytest.param(
            ["Some Song - Alpha", "Some Song - Alpha"],
            {"alpha"},
            id="song-first-title-credits-right",
        ),
        pytest.param(
            ["Alpha ft. Beta - Some Song", "Alpha - Some Song", "Alpha & Beta - Some Song"],
            {"alpha"},
            id="collaborators-are-credited-separately",
        ),
        pytest.param(
            ["Featherstone - Some Song", "Featherstone - Some Song"],
            {"featherstone"},
            id="feat-inside-a-word-is-not-a-split",
        ),
        pytest.param(
            ["Alpha - Some Song (Official Video)", "Alpha - Some Song [HD]"],
            {"alpha"},
            id="bracketed-text-is-ignored",
        ),
    ],
)
def test_the_vote_reads_the_act_out_of_a_title(titles, originals):
    assert _originals([_row(title) for title in titles]) == originals


@pytest.mark.parametrize(
    "title, credited",
    [
        pytest.param("Alpha (Beta) 'Some Song' Official MV", {"alpha", "beta"}, id="bracket-alias"),
        pytest.param("[MV] Alpha 'Some Song'", {"alpha"}, id="square-bracket-before-the-quote"),
        pytest.param("Alpha “Some Song” Official", {"alpha"}, id="curly-quotes"),
        pytest.param("Alpha 'Some Song' (From \"Some Film\")", {"alpha"}, id="film-is-bracketed"),
        pytest.param('Some Song (From "Some Film")', {"gamma"}, id="film-quote-credits-no-one"),
        pytest.param("Don't Stop Me Now", {"gamma"}, id="apostrophe-is-no-quote"),
        pytest.param("'Some Song' Official MV", {"gamma"}, id="nothing-before-the-quote"),
    ],
)
def test_a_title_with_a_quoted_song_credits_the_text_before_the_quote(title, credited):
    assert _originals([_row(title, channel="Gamma")] * 2) == credited


@pytest.mark.parametrize(
    "query, band, song, originals",
    [
        pytest.param(
            "the sound of silence",
            "Simon & Garfunkel",
            "The Sound of Silence",
            {"simonandgarfunkel"},
            id="ampersand",
        ),
        pytest.param(
            "september earth wind and fire",
            "Earth, Wind & Fire",
            "September",
            {"earthwindandfire"},
            id="and-in-the-query-is-the-titles-ampersand",
        ),
        pytest.param(
            "lil nas x old town road", "Lil Nas X", "Old Town Road", {"lilnasx"}, id="x-in-the-name"
        ),
    ],
)
def test_a_band_named_like_a_collaboration_is_credited_whole(query, band, song, originals):
    rows = [
        _row(f"{band} - {song} (Official Video)", channel=band),
        _row(f"{band} - {song} (Official Audio)", channel=band),
        _row(song, channel=f"{band} - Topic", verified=False),
    ]
    acts = read_first_page(rows, query)

    assert acts.originals == originals
    assert [kind for _, kind in official_first(rows, query, acts)] == ["video", "audio", "audio"]


def test_the_song_with_a_tied_name_does_not_hide_the_other_originals_video():
    """ "Some Song - Film" art tracks tie the song's own name with Alpha in the vote; Alpha's video
    must still pass the song check, which strikes only the names the row itself credits."""
    page = [
        _row("Some Song - Film", channel="Gamma"),
        _row("Some Song - Film", channel="Gamma"),
        _row("Alpha - Some Song (from Film) (Official Video)", channel="AlphaVEVO"),
        _row("Alpha - Some Song (from Film) (Official Video)", channel="AlphaVEVO"),
    ]
    acts = read_first_page(page, "some song film")

    assert acts.originals == {"somesong", "alpha"}
    assert official_kind(page[2], "some song film", acts) == "video"


# Which row is the song (rule 6)
# ---------------------------------------------------------------------------


def test_a_song_word_inside_a_bracket_only_does_not_make_the_song():
    """ "Another One Bites the Dust (from Bohemian Rhapsody)" is not "bohemian rhapsody"."""
    title = "Alpha - Other Song (From Some Film)"

    assert _kind(_row(title, channel="Alpha"), "some film") is None
    assert _kind(_art(title), "some film") is None


def test_a_film_in_brackets_is_part_of_the_song_search():
    assert _kind(_row("Song (from Film)", channel="Alpha"), "song film") == "video"


def test_a_title_with_a_word_of_its_own_is_another_song_when_it_lacks_a_song_word():
    """ "Make You Feel My Love" is not "send my love": two of three words match, one is its own."""
    query = "alpha send my love"

    assert _kind(_row("Alpha - Make You Feel My Love (Official Video)", "Alpha"), query) is None
    assert _kind(_art("Make You Feel My Love"), query) is None
    assert _kind(_row("Alpha - Send My Love (Official Video)", "Alpha"), query) == "video"


def test_the_query_may_say_more_than_the_title_but_a_misspelt_word_lifts_nothing():
    art_track = _art("Some Long Song")
    video = _row("Alpha - Some Long Song (Official Video)", channel="Alpha")

    assert _kind(art_track, "alpha some long song film") == "audio"
    assert (
        _kind(_row("Alpha - Other Long Song (Official Video)", "Alpha"), "alpha some long song")
        is None
    )
    assert _kind(art_track, "alpha some long sogn") is None
    assert _kind(video, "alpha some long sogn") is None


# Whose upload, and from where (rules 3 and 7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "channel, kind",
    [
        pytest.param("Alpha", "video", id="own-channel"),
        pytest.param("AlphaMusic", "video", id="music-suffix"),
        pytest.param("AlphaVEVO", "video", id="vevo-suffix"),
        pytest.param("Alpha Fans United", None, id="fan-channel-is-not-the-acts"),
        pytest.param("Gamma Channel", None, id="verified-channel-of-someone-else"),
        pytest.param("Beta Records", "video", id="label-by-name"),
    ],
)
def test_a_video_must_come_from_the_act_or_a_label_by_name(channel, kind):
    row = _row("Alpha - Some Song (Official Video)", channel=channel)

    assert _kind(row) == kind


def test_a_verified_channel_is_no_label_however_the_title_reads_with_or_without_the_acts_own():
    reupload = _row("Alpha - Some Song (Official Music Video)", channel="Gamma Channel")
    own = _row("Alpha - Some Song (Official Video)", channel="Alpha")

    assert _kind(reupload) is None
    assert _kind(reupload, vote=(own, _art("Some Song"))) is None


def test_the_act_is_found_with_or_without_a_leading_the():
    row = _row("The Alpha - Some Song (Official Video)", channel="Alpha")
    vote = (_art("Some Song", "The Alpha"), _art("Some Song", "The Alpha"))

    assert _kind(row, vote=vote) == "video"


def test_an_unverified_channel_is_not_the_acts_own():
    assert _kind(_row("Alpha - Some Song (Official Video)", "Alpha", verified=False)) is None


def test_a_cover_art_track_is_its_channels_alone_whoever_its_title_credits():
    """Alpha's cover of a song, titled "Original Artist - Song", is Alpha's, not the original's."""
    cover = _art("Beta - Some Song", act="Alpha")
    vote = (_row("Beta - Some Song (Official Video)", channel="Beta"),) * 2

    acts = read_first_page([cover, *vote], "some song")

    assert acts.originals == {"beta"}
    assert official_kind(cover, "some song", acts) is None


def test_a_band_whose_channel_adds_a_word_to_its_name_is_not_found():
    """Known miss (open issues, "celebration kool and the gang"): the channel
    "KoolandthegangShow" is not the band's name, so the vote now finds the band, split and whole,
    but the video is still not recognised as the band's own."""
    query = "celebration kool and the gang"
    video = _row("Kool & The Gang - Celebration (Official Video)", channel="KoolandthegangShow")
    page = [_unrelated(), video, video]

    acts = read_first_page(page, query)

    assert acts.originals == {"kool", "thegang", "koolandthegang"}
    assert official_first(page, query, acts) == [(r, None) for r in page]


# Does it say what it is (rules 5, 8, 9)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bracket, kind",
    [
        pytest.param("(Official Video)", "video", id="official-video"),
        pytest.param("(Official HD Video)", "video", id="official-hd-video"),
        pytest.param("[Official MV]", "video", id="official-mv"),
        pytest.param("(Music Video)", "video", id="music-video"),
        pytest.param("[M/V]", "video", id="mv"),
        pytest.param("(2025 Version)", "video", id="version"),
        pytest.param("(Millennium 20 Edition)", "video", id="edition"),
        pytest.param("(Edit)", "video", id="edit"),
        pytest.param("(Someone Official)", None, id="a-bare-official-says-nothing"),
        pytest.param("(O2 Arena)", None, id="venue"),
        pytest.param("@ The Tonight Show", None, id="show"),
    ],
)
def test_a_video_with_more_than_act_and_song_must_say_what_it_is(bracket, kind):
    row = _row(f"Alpha - Some Song {bracket}", channel="Alpha")

    assert _kind(row) == kind


def test_a_bare_title_needs_no_explanation():
    assert _kind(_row("Alpha - Some Song", channel="Alpha")) == "video"


@pytest.mark.parametrize(
    "bracket", ["(Behind-the-Scenes)", "(The Making-Of)", "(Demo)", "(Performance)"]
)
def test_marks_hide_hyphens_and_the_new_words_exclude_a_row(bracket):
    row = _row(f"Alpha - Some Song {bracket} (Official Video)", channel="Alpha")

    assert _kind(row) is None


def test_the_records_own_title_explains_its_subtitle():
    row = _row("Alpha - Some Song (Its Subtitle)", channel="Alpha")
    titled_so = (_art("Alpha - Some Song (Its Subtitle)"), _art("Some Song"))
    titled_plain = (_art("Some Song"), _art("Some Song"))

    assert _kind(row, vote=titled_so) == "video"
    assert _kind(row, vote=titled_plain) is None


def test_audio_is_spared_the_what_is_it_test():
    audio = _row("Alpha - Some Song (O2 Arena Audio)", channel="Alpha")

    assert _kind(audio) == "audio"


@pytest.mark.parametrize(
    "query, title, channel, kind",
    [
        pytest.param(
            "live your life",
            "T.I. - Live Your Life ft. Rihanna (Official Video)",
            "T.I.",
            "video",
            id="mark-in-the-song-name",
        ),
        pytest.param(
            "live and let die",
            "Paul McCartney & Wings - Live And Let Die (Live)",
            "Paul McCartney",
            None,
            id="a-mark-beyond-the-song-name-still-excludes",
        ),
        pytest.param(
            "bohemian rhapsody live",
            "Queen - Bohemian Rhapsody (Live Aid 1985)",
            "Queen Official",
            "video",
            id="the-version-the-query-asks-for",
        ),
    ],
)
def test_only_marks_beyond_the_querys_exclude_a_row(query, title, channel, kind):
    row = _row(title, channel=channel)
    vote = (_row(title, channel=channel),) * 2

    assert _kind(row, query, vote=vote) == kind


# Order (rule 12)
# ---------------------------------------------------------------------------


def _page_with_audio_and_a_video() -> list[SearchResult]:
    return [
        _unrelated(),
        _art("Some Song"),
        _row("Alpha - Some Song (Official Video)", channel="Alpha"),
        _art("Some Song (Second)"),
    ]


def test_audio_beside_a_lifted_video_keeps_its_place_and_its_badge():
    rows = _page_with_audio_and_a_video()

    ranked = official_first(rows, "some song", read_first_page(rows, "some song"))

    assert _titles(ranked) == [
        "Alpha - Some Song (Official Video)",
        "Unrelated upload",
        "Some Song",
        "Some Song (Second)",
    ]
    assert [kind for _, kind in ranked] == ["video", None, "audio", "audio"]


def test_audio_with_no_video_is_first_in_youtubes_order():
    rows = [_unrelated(), _art("Some Song"), _art("Some Song (Second)")]

    ranked = official_first(rows, "some song", read_first_page(rows, "some song"))

    assert _titles(ranked) == ["Some Song", "Some Song (Second)", "Unrelated upload"]
    assert [kind for _, kind in ranked] == ["audio", "audio", None]


def test_a_second_page_with_audio_and_no_video_keeps_its_order_when_page_one_lifted_a_video():
    with_video = [_row("Alpha - Some Song (Official Video)", channel="Alpha"), _art("Some Song")]
    no_video = [_art("Some Song"), _art("Some Song")]
    second_page = [_unrelated(), _art("Some Song (Second)")]

    after_a_video = read_first_page(with_video + no_video, "some song")
    after_none = read_first_page(no_video, "some song")

    assert after_a_video.has_video and not after_none.has_video
    kept = official_first(second_page, "some song", after_a_video)
    assert _titles(kept) == ["Unrelated upload", "Some Song (Second)"]
    assert [kind for _, kind in kept] == [None, "audio"]
    lifted = official_first(second_page, "some song", after_none)
    assert _titles(lifted) == ["Some Song (Second)", "Unrelated upload"]


@pytest.mark.parametrize("query", ["夜に駆ける", "yoasobi 夜に駆ける"])
def test_a_query_the_song_check_cannot_read_lifts_nothing(query):
    rows = [
        _row("YOASOBI「夜に駆ける」Official Music Video", channel="YOASOBI"),
        _row("YOASOBI「アイドル」Official Music Video", channel="YOASOBI"),
        _row("YOASOBI - Idol (Official Music Video)", channel="YOASOBI"),
    ]

    acts = read_first_page(rows, query)

    assert not acts.has_video
    assert official_first(rows, query, acts) == [(r, None) for r in rows]


def test_accented_latin_is_still_read():
    rows = [_row("Beyoncé - Halo"), _row("Beyoncé - Halo (Official Video)")]

    assert _originals(rows, "beyoncé halo") == {"beyonce"}
