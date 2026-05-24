"""Unit tests for pikaraoke.lib.genius_lyrics — parse_lyric_lines,
normalize_lyric_line, clean_srt_line, clean_genius_query."""

from pikaraoke.lib.genius_lyrics import (
    clean_genius_query,
    clean_srt_line,
    normalize_lyric_line,
    parse_lyric_lines,
)

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

    def test_inline_paren_contents_kept_in_align_text(self):
        """Bracket chars are removed from align_text, but enclosed words
        stay — paren contents in Genius lyrics are usually sung backing
        vocals, so the matcher needs those tokens."""
        text = "(I can't help) Falling in love\n"
        result = parse_lyric_lines(text)
        assert result[0]["text"] == "(I can't help) Falling in love"
        assert result[0]["align_text"] == "I can't help Falling in love"

    def test_paren_only_line_kept_with_contents(self):
        """A line that's purely parenthetical keeps its contents as a
        real align line (e.g. an adlib '(Oh)' is still sung)."""
        text = "(Oh)\nReal lyric\n"
        result = parse_lyric_lines(text)
        assert len(result) == 2
        assert result[0]["text"] == "(Oh)"
        assert result[0]["align_text"] == "Oh"
        assert result[1]["text"] == "Real lyric"

    def test_bracket_only_lines_skipped(self):
        """Stray bracket headers that slip past Genius's strip are dropped."""
        text = "[Verse 1]\nHello\n[Chorus]\nWorld\n"
        result = parse_lyric_lines(text)
        assert [r["text"] for r in result] == ["Hello", "World"]

    def test_punctuation_only_lines_dropped(self):
        """Stray '(', ')', ']', or '\\'' fragments left behind by sloppy
        sources would otherwise become empty matcher lines."""
        text = "Hello\n(\n)\n]\n'\nWorld\n"
        result = parse_lyric_lines(text)
        assert [r["text"] for r in result] == ["Hello", "World"]

    def test_inline_html_and_notes_stripped(self):
        """Defensive: HTML tags / musical notes / stage-direction
        brackets shouldn't reach align or display."""
        text = "<i>♪ Hello [whispered] world ♪</i>\n"
        result = parse_lyric_lines(text)
        assert result[0]["text"] == "Hello world"
        assert result[0]["align_text"] == "Hello world"

    def test_empty_input(self):
        assert parse_lyric_lines("") == []


# ---------------------------------------------------------------------------
# normalize_lyric_line
# ---------------------------------------------------------------------------


class TestNormalizeLyricLine:
    """Source-agnostic cleanups (HTML, notes, brackets, curly quotes)."""

    def test_strips_html_tags(self):
        assert normalize_lyric_line("<i>Hello</i> <b>world</b>") == "Hello world"

    def test_strips_musical_notes(self):
        assert normalize_lyric_line("♪ Hello world ♪") == "Hello world"
        assert normalize_lyric_line("♫ Sing ♬") == "Sing"

    def test_strips_bracketed_stage_directions(self):
        assert normalize_lyric_line("[whispered] hello world") == "hello world"
        assert normalize_lyric_line("hello [together] world") == "hello world"

    def test_collapses_srt_line_wrap(self):
        assert normalize_lyric_line("All the voices\nin my mind") == "All the voices in my mind"

    def test_normalizes_curly_quotes(self):
        assert normalize_lyric_line("I don’t know") == "I don't know"
        assert normalize_lyric_line("“hello”") == '"hello"'

    def test_preserves_parens(self):
        """Parens are source-dependent: Genius parens are sung backing
        vocals (kept). clean_srt_line strips them separately."""
        assert normalize_lyric_line("(Backing) Lead vocal") == "(Backing) Lead vocal"


# ---------------------------------------------------------------------------
# clean_srt_line
# ---------------------------------------------------------------------------


class TestCleanSrtLine:
    """SRT-route cleanup: normalize + strip paren stage directions."""

    def test_strips_paren_stage_directions(self):
        assert clean_srt_line("(aircraft engine rumbling)") == ""
        assert clean_srt_line("Hello (laughs) world") == "Hello world"

    def test_strips_html_tags_and_notes(self):
        assert clean_srt_line("<i>♪ Hello world ♪</i>") == "Hello world"

    def test_strips_bracketed_then_paren_stage_direction(self):
        """[together] header + paren ad-lib should both vanish; lead
        lyric kept."""
        assert clean_srt_line("[together]\n♪ Beauty and the beast ♪") == "Beauty and the beast"

    def test_drops_punct_only_lines(self):
        assert clean_srt_line("(") == ""
        assert clean_srt_line(")") == ""
        assert clean_srt_line("♪♪♪") == ""

    def test_collapses_2line_wrap(self):
        assert clean_srt_line("Hello\nworld") == "Hello world"


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
