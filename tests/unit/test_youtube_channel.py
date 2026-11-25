"""Tests for the channel-name cleaner the search ranking and the Genius query share."""

import pytest

from pikaraoke.lib.youtube_channel import channel_words


@pytest.mark.parametrize(
    ("channel", "expected"),
    [
        ("Adele Official", "Adele"),
        ("Disney Music VEVO", "Disney"),
        ("Eminem Music Videos", "Eminem"),
        ("Journey - Topic", "Journey"),
        ("Sony Records", "Sony"),
        ("A-Lin官方專屬頻道", "A-Lin"),
        # Noise glued to the name is the caller's to read.
        ("BackstreetBoysVEVO", "BackstreetBoysVEVO"),
        # Only whole words go.
        ("Musical Moments", "Musical Moments"),
        ("Lionel Richie", "Lionel Richie"),
    ],
)
def test_channel_words_drops_only_the_noise(channel: str, expected: str):
    assert " ".join(channel_words(channel).split()) == expected
