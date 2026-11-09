"""Tests for the shared command-line lyric-source prompt."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import genius_prompt

SONG = Path("/songs/Artist - Song---dQw4w9WgXcQ.mp4")
HITS = [SimpleNamespace(id=7, title="Song", artist="Artist")]


def _ask(monkeypatch, answers, hits=HITS):
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt: next(replies))
    searches = []

    def search(query, limit):
        searches.append(query)
        return hits

    return genius_prompt.ask_lyrics_source(SONG, SimpleNamespace(search=search)), searches


@pytest.mark.parametrize(
    "answer,choice",
    [("s", ("srt",)), ("T", ("transcribe",)), ("k", ("skip",)), ("q", ("skip",))],
)
def test_a_shortcut_at_the_search_prompt_picks_without_searching(monkeypatch, answer, choice):
    assert _ask(monkeypatch, [answer]) == (choice, [])


def test_a_shortcut_at_the_choose_prompt_still_picks(monkeypatch):
    assert _ask(monkeypatch, ["", "s"]) == (("srt",), ["Artist - Song"])


def test_a_numbered_hit_picks_genius(monkeypatch):
    assert _ask(monkeypatch, ["", "1"]) == (("genius", 7), ["Artist - Song"])


def test_a_new_query_at_choose_becomes_the_next_default(monkeypatch):
    choice, searches = _ask(monkeypatch, ["", "other song", "", "1"])
    assert choice == ("genius", 7)
    assert searches == ["Artist - Song", "other song"]


def test_no_hits_returns_to_the_search_prompt(monkeypatch):
    assert _ask(monkeypatch, ["", "t"], hits=[]) == (("transcribe",), ["Artist - Song"])
