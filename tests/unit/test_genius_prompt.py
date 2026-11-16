"""Tests for the shared command-line lyric-source prompt."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from pikaraoke.lib.genius import HITS_PER_QUERY, GeniusHit
from scripts import genius_prompt

SONG = Path("/songs/Artist - Song---dQw4w9WgXcQ.mp4")
START = "Artist Song"  # what the title reader starts the prompt with for SONG
# By the song's artist, with page views: a title-and-artist match, so the ladder stops and
# preselects it.
SURE = GeniusHit(id=7, title="Song", artist="Artist", primary_artist="Artist", views=1000)
# The right title by someone else: listed, but nothing is safe to preselect.
OTHER = GeniusHit(id=8, title="Song", artist="Somebody", primary_artist="Somebody", views=1000)
ELSEWHERE = GeniusHit(id=9, title="Song", artist="Elsewhere", primary_artist="Elsewhere", views=500)


def _ask(monkeypatch, answers, hits=(SURE,), prompts=None):
    """Run the prompt on ``answers``; returns its choice and the Genius calls as (query, limit).

    ``prompts``, when given, collects the text of every prompt asked.
    """
    replies = iter(answers)
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (prompts.append(prompt) if prompts is not None else None) or next(replies),
    )
    searches = []

    def search(query, limit=8):
        searches.append((query, limit))
        return list(hits)

    return genius_prompt.ask_lyrics_source(SONG, SimpleNamespace(search=search)), searches


@pytest.mark.parametrize(
    "answer,choice",
    [("s", ("srt",)), ("T", ("transcribe",)), ("k", ("skip",)), ("q", ("skip",))],
)
def test_a_shortcut_at_the_search_prompt_picks_without_searching(monkeypatch, answer, choice):
    assert _ask(monkeypatch, [answer]) == (choice, [])


def test_a_shortcut_at_the_choose_prompt_still_picks(monkeypatch):
    assert _ask(monkeypatch, ["", "s"]) == (("srt",), [(START, HITS_PER_QUERY)])


def test_a_numbered_hit_picks_genius(monkeypatch):
    assert _ask(monkeypatch, ["", "1"]) == (("genius", 7), [(START, HITS_PER_QUERY)])


def test_the_first_search_is_the_song_s_own_ladder_and_stops_on_a_sure_match(monkeypatch):
    _, searches = _ask(monkeypatch, ["", "1"])

    assert searches == [(START, HITS_PER_QUERY)]


def test_the_first_search_asks_at_most_two_queries_when_nothing_is_sure(monkeypatch):
    _, searches = _ask(monkeypatch, ["", "1"], hits=[OTHER])

    assert searches == [(START, HITS_PER_QUERY), ("Song", HITS_PER_QUERY)]


def test_a_new_query_at_choose_becomes_the_next_default_and_goes_as_typed(monkeypatch):
    choice, searches = _ask(monkeypatch, ["", "other song", "", "1"])

    assert choice == ("genius", 7)
    assert searches == [(START, HITS_PER_QUERY), ("other song", 8)]


def test_the_start_text_typed_again_is_the_song_s_own_search_again(monkeypatch):
    _, searches = _ask(monkeypatch, ["other song", "", START, "1"])

    assert searches == [("other song", 8), (START, HITS_PER_QUERY)]


def test_no_hits_returns_to_the_search_prompt(monkeypatch):
    choice, searches = _ask(monkeypatch, ["", "t"], hits=[])

    assert choice == ("transcribe",)
    assert searches == [(START, HITS_PER_QUERY), ("Song", HITS_PER_QUERY)]


def test_enter_at_choose_takes_the_marked_hit(monkeypatch, capsys):
    choice, _ = _ask(monkeypatch, ["", ""], hits=[SURE, OTHER])

    assert choice == ("genius", 7)
    out = capsys.readouterr().out
    assert "1) Song - Artist  <- Enter" in out
    assert "2) Song - Somebody\n" in out


def test_a_hit_shows_its_year_after_the_artist_and_before_the_mark(monkeypatch, capsys):
    dated_sure = GeniusHit(7, "Song", "Artist", primary_artist="Artist", year=1987, views=1000)
    dated_other = GeniusHit(8, "Song", "Somebody", primary_artist="Somebody", year=2001, views=1000)

    _ask(monkeypatch, ["", ""], hits=[dated_sure, dated_other, ELSEWHERE])

    out = capsys.readouterr().out
    assert "1) Song - Artist (1987)  <- Enter" in out
    assert "2) Song - Somebody (2001)\n" in out
    assert "3) Song - Elsewhere\n" in out  # Genius gave no year


def test_the_choose_prompt_says_enter_takes_the_marked_hit_only_when_there_is_one(monkeypatch):
    marked, unmarked = [], []

    _ask(monkeypatch, ["", "1"], hits=[SURE], prompts=marked)
    _ask(monkeypatch, ["", "1"], hits=[OTHER], prompts=unmarked)

    assert "Enter=1" in [p for p in marked if "choose" in p][0]
    assert "Enter=1" not in [p for p in unmarked if "choose" in p][0]


def test_with_nothing_marked_enter_at_choose_searches_again_as_before(monkeypatch):
    choice, searches = _ask(monkeypatch, ["", "", "", "2"], hits=[OTHER, ELSEWHERE])

    assert choice == ("genius", 9)
    assert searches == [(START, HITS_PER_QUERY), ("Song", HITS_PER_QUERY)] * 2


def test_a_typed_search_marks_nothing_so_enter_searches_again(monkeypatch, capsys):
    choice, searches = _ask(monkeypatch, ["other song", "", "", "1"], hits=[SURE])

    assert choice == ("genius", 7)
    assert searches == [("other song", 8)] * 2
    assert "<- Enter" not in capsys.readouterr().out
