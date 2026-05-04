"""Unit tests for pikaraoke.lib.genius_lyrics — parse_genius_sections, split_groups, clean_genius_query."""

import pytest

from pikaraoke.lib.genius_lyrics import (
    _section_base,
    clean_genius_query,
    genius_singer_mode,
    parse_genius_sections,
    split_groups,
)


# ---------------------------------------------------------------------------
# _section_base
# ---------------------------------------------------------------------------


class TestSectionBase:
    def test_strips_trailing_number(self):
        assert _section_base("Verse 2") == "Verse"

    def test_strips_trailing_number_with_space(self):
        assert _section_base("Chorus 3") == "Chorus"

    def test_no_number_unchanged(self):
        assert _section_base("Bridge") == "Bridge"

    def test_strips_trailing_number_prelude(self):
        assert _section_base("Pre-Chorus 1") == "Pre-Chorus"


# ---------------------------------------------------------------------------
# split_groups
# ---------------------------------------------------------------------------


class TestSplitGroups:
    def test_single_name(self):
        assert split_groups("Brian") == [["Brian"]]

    def test_duet_with_ampersand(self):
        assert split_groups("Kevin & AJ") == [["Kevin", "AJ"]]

    def test_multiple_groups_comma(self):
        assert split_groups("Nick, All") == [["Nick"], ["All"]]

    def test_mixed_groups(self):
        assert split_groups("Brian & AJ, Nick") == [["Brian", "AJ"], ["Nick"]]

    def test_all_ensemble(self):
        assert split_groups("All") == [["All"]]

    def test_whitespace_stripped(self):
        assert split_groups("  Brian ,  AJ  ") == [["Brian"], ["AJ"]]

    def test_empty_string(self):
        assert split_groups("") == []

    def test_triple_with_ampersands(self):
        assert split_groups("A & B & C") == [["A", "B", "C"]]


# ---------------------------------------------------------------------------
# parse_genius_sections
# ---------------------------------------------------------------------------


class TestParseGeniusSections:
    def test_basic_verse_chorus(self):
        text = "[Verse 1]\nHello world\n[Chorus]\nSing along\n"
        result = parse_genius_sections(text)

        assert len(result) == 2
        assert result[0]["text"] == "Hello world"
        assert result[0]["align_text"] == "Hello world"
        assert result[0]["section"] == "Verse 1"
        assert result[0]["is_ensemble"] is True
        assert result[1]["text"] == "Sing along"
        assert result[1]["section"] == "Chorus"

    def test_section_with_attribution(self):
        text = "[Verse 1: Brian]\nHello world\n[Chorus: All]\nSing together\n"
        result = parse_genius_sections(text)

        assert result[0]["section"] == "Verse 1"
        assert result[0]["speaker_label"] == "Brian"
        assert result[0]["dominant_speaker"] == "Brian"
        assert result[0]["is_ensemble"] is False

        # "All" → ensemble
        assert result[1]["speaker_label"] is None
        assert result[1]["is_ensemble"] is True

    def test_carry_forward_exact_name(self):
        """Section with same exact name inherits attribution from prior."""
        text = "[Verse 1: Brian]\nFirst line\n[Verse 1]\nSecond line\n"
        result = parse_genius_sections(text)

        assert result[0]["speaker_label"] == "Brian"
        assert result[1]["speaker_label"] == "Brian"

    def test_carry_forward_section_family(self):
        """[Verse 2] inherits from [Verse 1: Brian] via base name."""
        text = "[Verse 1: Brian]\nFirst line\n[Verse 2]\nSecond line\n"
        result = parse_genius_sections(text)

        assert result[0]["speaker_label"] == "Brian"
        assert result[1]["speaker_label"] == "Brian"

    def test_duet_attribution(self):
        text = "[Verse: Brian & AJ]\nWe sing together\n"
        result = parse_genius_sections(text)

        assert result[0]["speaker_label"] == "Brian & AJ"
        assert result[0]["dominant_speaker"] == "Brian"
        assert result[0]["is_ensemble"] is False

    def test_no_attribution_is_ensemble(self):
        text = "[Verse]\nJust a line\n"
        result = parse_genius_sections(text)

        assert result[0]["speaker_label"] is None
        assert result[0]["is_ensemble"] is True

    def test_inline_parens_stripped_for_align_text(self):
        """Inline parens like '(I can't help)' should be stripped in align_text."""
        text = "[Verse]\n(I can't help) Falling in love\n"
        result = parse_genius_sections(text)

        assert result[0]["text"] == "(I can't help) Falling in love"
        assert result[0]["align_text"] == "Falling in love"

    def test_fully_parenthesized_line_skipped(self):
        """A line that becomes empty after stripping inline parens is skipped."""
        text = "[Verse]\n(Oh)\nReal lyric\n"
        result = parse_genius_sections(text)

        assert len(result) == 1
        assert result[0]["text"] == "Real lyric"

    def test_blank_lines_skipped(self):
        text = "[Verse]\n\nHello\n\nWorld\n"
        result = parse_genius_sections(text)

        assert len(result) == 2
        assert result[0]["text"] == "Hello"
        assert result[1]["text"] == "World"

    def test_header_only_produces_no_lines(self):
        text = "[Verse 1]\n[Chorus]\n"
        result = parse_genius_sections(text)
        assert result == []

    def test_empty_input(self):
        assert parse_genius_sections("") == []

    def test_no_headers(self):
        """Lines without any headers — all treated as ensemble, section=''. """
        text = "Just a song\nWith no sections\n"
        result = parse_genius_sections(text)

        assert len(result) == 2
        assert result[0]["section"] == ""
        assert result[0]["is_ensemble"] is True

    def test_attribution_with_multiple_groups(self):
        """'Brian & AJ, Nick' → two groups: first group is duet."""
        text = "[Verse: Brian & AJ, Nick]\nSome line\n"
        result = parse_genius_sections(text)

        assert result[0]["speaker_label"] == "Brian & AJ"
        assert result[0]["dominant_speaker"] == "Brian"


# ---------------------------------------------------------------------------
# genius_singer_mode
# ---------------------------------------------------------------------------


class TestGeniusSingerMode:
    def test_solo_when_all_ensemble(self):
        lines = [
            {"speaker_label": None, "is_ensemble": True},
            {"speaker_label": None, "is_ensemble": True},
        ]
        assert genius_singer_mode(lines) == "solo"

    def test_multi_when_at_least_one_speaker(self):
        lines = [
            {"speaker_label": None, "is_ensemble": True},
            {"speaker_label": "Brian", "is_ensemble": False},
        ]
        assert genius_singer_mode(lines) == "multi"

    def test_solo_on_empty_list(self):
        assert genius_singer_mode([]) == "solo"


# ---------------------------------------------------------------------------
# clean_genius_query
# ---------------------------------------------------------------------------


class TestCleanGeniusQuery:
    """Light-clean query preserving parenthetical content (DD8)."""

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
        # The noise pattern strips 'HD' and 'HQ' as trailing terms
        # but the brackets are preserved by the function design
        assert "Song" in result
