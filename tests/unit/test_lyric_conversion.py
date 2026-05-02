"""Characterization tests for whisper/lyric-align conversion helpers.

These tests capture the current behaviour of _extract_words,
_match_words_to_lines, and _segments_to_line_objects so that we have a
regression baseline when these functions move from LyricAlignStage into
the whisper worker subprocess.

The functions now live in whisper_worker.py as module-level functions.
The tests use mock WhisperResult-shaped objects (not real stable-ts
outputs) so they run without a GPU or stable_whisper install.
"""

from unittest.mock import MagicMock

import pytest

from pikaraoke.pipeline.workers.whisper_worker import (
    _extract_words,
    _match_words_to_lines,
    _segments_to_line_objects,
)


# ---------------------------------------------------------------------------
# Fixtures that mimic stable-ts WhisperResult structure
# ---------------------------------------------------------------------------


def _make_word(word: str, start: float, end: float):
    """Create a mock word object matching stable-ts WhisperResult word shape."""
    w = MagicMock()
    w.word = word
    w.start = start
    w.end = end
    # Ensure str() gives the word text for debugging
    w.__str__ = lambda self: f"Word({word})"
    return w


def _make_segment(text: str, words: list):
    """Create a mock segment object matching stable-ts segment shape."""
    seg = MagicMock()
    seg.text = text
    seg.words = words
    return seg


def _make_result(segments: list):
    """Create a mock WhisperResult with the given segments."""
    result = MagicMock()
    result.segments = segments
    return result


# ---------------------------------------------------------------------------
# _extract_words tests
# ---------------------------------------------------------------------------


class TestExtractWords:
    """Tests for _extract_words (now in whisper_worker module)."""

    def test_single_segment_single_word(self):
        result = _make_result(
            [_make_segment("Hello", [_make_word(" Hello ", 0.0, 0.5)])]
        )
        words = _extract_words(result)
        assert len(words) == 1
        assert words[0] == {
            "word": "Hello",
            "start": 0.0,
            "end": 0.5,
            "is_segment_first": True,
        }

    def test_single_segment_multiple_words(self):
        result = _make_result(
            [
                _make_segment(
                    "Hello world",
                    [
                        _make_word(" Hello ", 0.0, 0.5),
                        _make_word(" world", 0.5, 1.0),
                    ],
                )
            ]
        )
        words = _extract_words(result)
        assert len(words) == 2
        assert words[0]["is_segment_first"] is True
        assert words[1]["is_segment_first"] is False

    def test_multiple_segments(self):
        result = _make_result(
            [
                _make_segment(
                    "Hello",
                    [_make_word(" Hello ", 0.0, 0.5)],
                ),
                _make_segment(
                    "World",
                    [_make_word(" World ", 1.0, 1.5)],
                ),
            ]
        )
        words = _extract_words(result)
        assert len(words) == 2
        assert words[0]["is_segment_first"] is True
        assert words[1]["is_segment_first"] is True  # first word of second segment

    def test_empty_result(self):
        result = _make_result([])
        words = _extract_words(result)
        assert words == []

    def test_whitespace_stripped(self):
        result = _make_result(
            [_make_segment(" Hello ", [_make_word(" Hello ", 0.0, 0.5)])]
        )
        words = _extract_words(result)
        assert words[0]["word"] == "Hello"

    def test_preserves_float_timestamps(self):
        result = _make_result(
            [_make_segment("Hi", [_make_word(" Hi ", 1.234, 5.678)])]
        )
        words = _extract_words(result)
        assert words[0]["start"] == 1.234
        assert words[0]["end"] == 5.678


# ---------------------------------------------------------------------------
# _match_words_to_lines tests
# ---------------------------------------------------------------------------


class TestMatchWordsToLines:
    """Tests for _match_words_to_lines (now in whisper_worker module)."""

    def test_one_line_one_word(self):
        words = [{"word": "Hello", "start": 0.0, "end": 0.5, "is_segment_first": True}]
        lines = ["Hello"]
        result = _match_words_to_lines(words, lines)
        assert len(result) == 1
        assert result[0]["text"] == "Hello"
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 0.5
        assert len(result[0]["words"]) == 1

    def test_two_lines(self):
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5, "is_segment_first": True},
            {"word": "world", "start": 0.5, "end": 1.0, "is_segment_first": False},
        ]
        lines = ["Hello", "world"]
        result = _match_words_to_lines(words, lines)
        assert len(result) == 2
        assert result[0]["text"] == "Hello"
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 0.5
        assert result[1]["text"] == "world"
        assert result[1]["start"] == 0.5
        assert result[1]["end"] == 1.0

    def test_multi_word_line(self):
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5, "is_segment_first": True},
            {"word": "beautiful", "start": 0.5, "end": 1.0, "is_segment_first": False},
            {"word": "world", "start": 1.0, "end": 1.5, "is_segment_first": False},
        ]
        lines = ["Hello beautiful world"]
        result = _match_words_to_lines(words, lines)
        assert len(result) == 1
        assert result[0]["text"] == "Hello beautiful world"
        assert len(result[0]["words"]) == 3
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 1.5

    def test_mixed_line_lengths(self):
        words = [
            {"word": "I", "start": 0.0, "end": 0.2, "is_segment_first": True},
            {"word": "sing", "start": 0.2, "end": 0.5, "is_segment_first": False},
            {"word": "a", "start": 0.5, "end": 0.6, "is_segment_first": True},
            {"word": "song", "start": 0.6, "end": 1.0, "is_segment_first": False},
        ]
        lines = ["I sing", "a song"]
        result = _match_words_to_lines(words, lines)
        assert len(result) == 2
        assert result[0]["text"] == "I sing"
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 0.5
        assert result[1]["text"] == "a song"
        assert result[1]["start"] == 0.5
        assert result[1]["end"] == 1.0

    def test_empty_lines_skipped(self):
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5, "is_segment_first": True},
        ]
        lines = ["", "Hello", ""]
        result = _match_words_to_lines(words, lines)
        assert len(result) == 1
        assert result[0]["text"] == "Hello"

    def test_no_words_for_line_skips(self):
        """A line with zero words (e.g. all words already consumed) is skipped."""
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5, "is_segment_first": True},
        ]
        lines = ["Hello", "orphan line"]
        result = _match_words_to_lines(words, lines)
        assert len(result) == 1
        assert result[0]["text"] == "Hello"


# ---------------------------------------------------------------------------
# _segments_to_line_objects tests
# ---------------------------------------------------------------------------


class TestSegmentsToLineObjects:
    """Tests for _segments_to_line_objects (now in whisper_worker module)."""

    def test_single_segment(self):
        result = _make_result(
            [
                _make_segment(
                    "Hello world",
                    [
                        _make_word(" Hello ", 0.0, 0.5),
                        _make_word(" world", 0.5, 1.0),
                    ],
                )
            ]
        )
        line_objects = _segments_to_line_objects(result)
        assert len(line_objects) == 1
        assert line_objects[0]["text"] == "Hello world"
        assert line_objects[0]["start"] == 0.0
        assert line_objects[0]["end"] == 1.0
        assert len(line_objects[0]["words"]) == 2
        assert line_objects[0]["words"][0]["is_segment_first"] is True
        assert line_objects[0]["words"][1]["is_segment_first"] is False

    def test_multiple_segments(self):
        result = _make_result(
            [
                _make_segment(
                    "Hello",
                    [_make_word(" Hello ", 0.0, 0.5)],
                ),
                _make_segment(
                    "World",
                    [_make_word(" World ", 1.0, 1.5)],
                ),
            ]
        )
        line_objects = _segments_to_line_objects(result)
        assert len(line_objects) == 2
        assert line_objects[0]["text"] == "Hello"
        assert line_objects[1]["text"] == "World"
        # is_segment_first is True for the first word of each segment
        assert line_objects[0]["words"][0]["is_segment_first"] is True
        assert line_objects[1]["words"][0]["is_segment_first"] is True

    def test_segment_with_no_words_skipped(self):
        result = _make_result(
            [
                _make_segment("Hello", [_make_word(" Hello ", 0.0, 0.5)]),
                _make_segment("NoWords", []),  # empty words list
                _make_segment("World", [_make_word(" World ", 1.0, 1.5)]),
            ]
        )
        line_objects = _segments_to_line_objects(result)
        assert len(line_objects) == 2
        assert line_objects[0]["text"] == "Hello"
        assert line_objects[1]["text"] == "World"

    def test_empty_result(self):
        result = _make_result([])
        line_objects = _segments_to_line_objects(result)
        assert line_objects == []

    def test_text_stripped(self):
        result = _make_result(
            [
                _make_segment(
                    " Hello world ",
                    [
                        _make_word(" Hello ", 0.0, 0.5),
                        _make_word(" world ", 0.5, 1.0),
                    ],
                )
            ]
        )
        line_objects = _segments_to_line_objects(result)
        assert line_objects[0]["text"] == "Hello world"

    def test_word_text_stripped(self):
        result = _make_result(
            [
                _make_segment(
                    "Hello",
                    [_make_word(" Hello ", 0.0, 0.5)],
                )
            ]
        )
        line_objects = _segments_to_line_objects(result)
        assert line_objects[0]["words"][0]["word"] == "Hello"


# ---------------------------------------------------------------------------
# LineObject contract: JSON-serializability check
# ---------------------------------------------------------------------------


class TestLineObjectContract:
    """Verify that line_objects produced by the conversion helpers are
    JSON-serializable (all values are str/int/float/bool/list/dict).
    This is the IPC contract: these objects cross the subprocess boundary.
    """

    def test_extract_words_produces_json_serializable_output(self):
        import json

        result = _make_result(
            [
                _make_segment(
                    "Hello world",
                    [
                        _make_word(" Hello ", 0.0, 0.5),
                        _make_word(" world", 0.5, 1.0),
                    ],
                )
            ]
        )
        words = _extract_words(result)
        # Must not raise
        serialized = json.dumps(words)
        deserialized = json.loads(serialized)
        assert deserialized == words

    def test_segments_to_line_objects_produces_json_serializable_output(self):
        import json

        result = _make_result(
            [
                _make_segment(
                    "Hello world",
                    [
                        _make_word(" Hello ", 0.0, 0.5),
                        _make_word(" world", 0.5, 1.0),
                    ],
                )
            ]
        )
        line_objects = _segments_to_line_objects(result)
        serialized = json.dumps(line_objects)
        deserialized = json.loads(serialized)
        assert deserialized == line_objects

    def test_match_words_to_lines_produces_json_serializable_output(self):
        import json

        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5, "is_segment_first": True},
            {"word": "world", "start": 0.5, "end": 1.0, "is_segment_first": False},
        ]
        lines = ["Hello", "world"]
        line_objects = _match_words_to_lines(words, lines)
        serialized = json.dumps(line_objects)
        deserialized = json.loads(serialized)
        assert deserialized == line_objects
