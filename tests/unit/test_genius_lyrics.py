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

    def test_wrapped_bracket_attribution_dropped(self):
        """Genius splits a bracket attribution across physical lines, so
        neither bracket defence (both need a closing ']') fires and the
        fragments render as sung lyrics. Rejoining restores the header."""
        text = "Now I really wish that I knew how to swim!\n[SHANG & \nSOLDIERS\n]\nBe a man\n"
        result = parse_lyric_lines(text)
        assert [r["text"] for r in result] == [
            "Now I really wish that I knew how to swim!",
            "Be a man",
        ]

    def test_wrapped_paren_line_rejoined(self):
        """A paren wrap is a real lyric split mid-line, not dirt — it
        rejoins rather than dropping, and the leftover ')' line goes away."""
        text = "(\nBe a man\n) We must be swift as the coursing river\n"
        result = parse_lyric_lines(text)
        assert [r["text"] for r in result] == ["(Be a man) We must be swift as the coursing river"]
        assert result[0]["align_text"] == "Be a man We must be swift as the coursing river"

    def test_wrapped_paren_fragment_rejoined(self):
        """The wrap replaced nothing, so fragments concatenate with no
        separator: 'Between you and I (' + 'I' + ')' is one lyric line."""
        text = "Right here for this moment\nBetween you and I (\nI\n)\nEverything is happenin'\n"
        result = parse_lyric_lines(text)
        assert [r["text"] for r in result] == [
            "Right here for this moment",
            "Between you and I (I)",
            "Everything is happenin'",
        ]

    def test_stray_open_delimiter_leaves_its_neighbours_alone(self):
        """A delimiter that never closes is not a wrap: the join is
        discarded and every line is emitted as written."""
        text = "Ooh (yeah\nStill this stanza\n\nNext stanza\n"
        result = parse_lyric_lines(text)
        assert [r["text"] for r in result] == ["Ooh (yeah", "Still this stanza", "Next stanza"]

    def test_reparsing_a_parsed_sheet_is_a_no_op(self):
        """The regen tool feeds a stored sheet back through here, and a
        parsed sheet has no blank lines to bound a runaway join. One stray
        '(' used to swallow the rest of the song (NSYNC - Paradise)."""
        text = "Right here for this moment\nBetween you and I (\nI\n)\nEverything is happenin'\n"
        once = [r["text"] for r in parse_lyric_lines(text)]
        twice = [r["text"] for r in parse_lyric_lines("\n".join(once))]
        assert twice == once

    def test_reparsing_a_sheet_with_a_stray_delimiter_is_a_no_op(self):
        """The damaging case: the ')' fragment is already gone, so the
        '(' can never balance however far the join reaches."""
        stored = ["Between you and I (", "I", "Everything is happenin'", "And it's just what"]
        assert [r["text"] for r in parse_lyric_lines("\n".join(stored))] == stored

    def test_inline_html_and_notes_stripped(self):
        """Defensive: HTML tags / musical notes / stage-direction
        brackets shouldn't reach align or display."""
        text = "<i>♪ Hello [whispered] world ♪</i>\n"
        result = parse_lyric_lines(text)
        assert result[0]["text"] == "Hello world"
        assert result[0]["align_text"] == "Hello world"

    def test_empty_input(self):
        assert parse_lyric_lines("") == []

    def test_non_latin_lines_kept(self):
        """Review-fix: the letter check is Unicode-aware, so non-Latin
        (CJK / Cyrillic / accented) lyric lines aren't dropped."""
        text = "こんにちは世界\nПривет\nÉàü\n123\n"
        result = parse_lyric_lines(text)
        # the three letter-bearing lines survive; the digit-only line is dropped
        assert [r["text"] for r in result] == ["こんにちは世界", "Привет", "Éàü"]


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

    def test_normalizes_prime_used_as_apostrophe(self):
        assert normalize_lyric_line("I′M GOING UNDER") == "I'M GOING UNDER"

    def test_folds_cyrillic_watermark_letters(self):
        """Lyric-site watermark (U+0435 for "e"): the aligner reads this
        text, so the lookalike must not survive to reach whisper."""
        assert normalize_lyric_line("As it did when we wеre young") == (
            "As it did when we were young"
        )
        assert normalize_lyric_line("Givеs the real world a try") == "Gives the real world a try"

    def test_keeps_accents_of_non_english_lyrics(self):
        """Only lookalikes are folded here — a real accent is sung text."""
        assert normalize_lyric_line("Je t'aimerai à jamais") == "Je t'aimerai à jamais"

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

    def test_keeps_non_latin_lines(self):
        """Review-fix: Unicode-aware letter check keeps non-Latin lyrics
        instead of dropping them as letter-less."""
        assert clean_srt_line("こんにちは") == "こんにちは"
        assert clean_srt_line("Привет мир") == "Привет мир"


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
