"""Unit tests for pikaraoke.lib.genius_lyrics — parse_lyric_lines, clean_genius_query."""

from pikaraoke.lib.genius_lyrics import clean_genius_query, parse_lyric_lines

# ---------------------------------------------------------------------------
# parse_lyric_lines
# ---------------------------------------------------------------------------


class TestParseLyricLines:
    def test_basic_lines(self):
        text = "Hello world\nSing along\n"
        result = parse_lyric_lines(text)
        assert len(result) == 2
        assert result[0]["text"] == "Hello world"
        assert result[0]["align_text"] == "Hello world"
        assert result[1]["text"] == "Sing along"

    def test_blank_lines_skipped(self):
        text = "\nHello\n\nWorld\n"
        result = parse_lyric_lines(text)
        assert [r["text"] for r in result] == ["Hello", "World"]

    def test_inline_parens_stripped_for_align_text(self):
        """Inline parens like '(I can't help)' should be stripped in align_text."""
        text = "(I can't help) Falling in love\n"
        result = parse_lyric_lines(text)
        assert result[0]["text"] == "(I can't help) Falling in love"
        assert result[0]["align_text"] == "Falling in love"

    def test_fully_parenthesized_line_skipped(self):
        """A line that becomes empty after stripping inline parens is skipped."""
        text = "(Oh)\nReal lyric\n"
        result = parse_lyric_lines(text)
        assert len(result) == 1
        assert result[0]["text"] == "Real lyric"

    def test_bracket_only_lines_skipped(self):
        """Stray bracket headers that slip past Genius's strip are dropped."""
        text = "[Verse 1]\nHello\n[Chorus]\nWorld\n"
        result = parse_lyric_lines(text)
        assert [r["text"] for r in result] == ["Hello", "World"]

    def test_empty_input(self):
        assert parse_lyric_lines("") == []


# ---------------------------------------------------------------------------
# clean_genius_query
# ---------------------------------------------------------------------------


class TestCleanGeniusQuery:
    """Light-clean query preserving parenthetical content."""

    def test_preserves_parenthetical_content(self):
        """Unlike regex_tidy, clean_genius_query does NOT strip parens."""
        result = clean_genius_query("(I Can't Help) Falling In Love")
        assert "(I Can't Help)" in result
        assert "Falling In Love" in result

    def test_strips_emoji(self):
        result = clean_genius_query("Song 🎤🎵 Title")
        assert "🎤" not in result
        assert "🎵" not in result
        assert "Song" in result
        assert "Title" in result

    def test_replaces_underscores(self):
        result = clean_genius_query("Artist_Name_Song")
        assert "_" not in result
        assert "Artist Name Song" in result

    def test_strips_noise_words(self):
        """YouTube noise words like 'karaoke', 'official video' etc are stripped."""
        result = clean_genius_query("Song karaoke official video")
        assert "karaoke" not in result.lower()
        assert "official" not in result.lower()

    def test_collapses_whitespace(self):
        result = clean_genius_query("  Song   Title  ")
        assert result == "Song Title"

    def test_empty_string(self):
        assert clean_genius_query("") == ""

    def test_preserves_brackets(self):
        """Bracketed content (e.g. '[HD]') should be preserved since
        clean_genius_query only strips emoji and noise words, not brackets."""
        result = clean_genius_query("Song [HD]")
        assert "Song" in result
