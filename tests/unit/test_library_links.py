"""Unit tests for pikaraoke/lib/library_links.py -- classify, expand, library lookup.

Subprocess (yt-dlp) is mocked; nothing here touches the network.
"""

import json

import pytest

from pikaraoke.lib import library_links

VID_A = "dQw4w9WgXcQ"
VID_B = "abcdefghijk"


# ---------------------------------------------------------------------------
# Classify
# ---------------------------------------------------------------------------


class TestIsVideoId:
    @pytest.mark.parametrize("value", [VID_A, VID_B, "a-b_c-d_e-f", "___________"])
    def test_eleven_url_safe_characters_are_an_id(self, value):
        assert library_links.is_video_id(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "short",
            VID_A + "x",
            "has space!!",
            "ünicode-ünic",
            VID_A + "\n",  # fullmatch: a trailing newline is not part of an id
            None,
            5,
            ["dQw4w9WgXcQ"],
        ],
    )
    def test_anything_else_is_not(self, value):
        assert library_links.is_video_id(value) is False


class TestClassifyUrl:
    def test_video_watch_url(self):
        url = f"https://www.youtube.com/watch?v={VID_A}"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_video_with_list_param_gives_only_the_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&list=PLxxxx"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_short_url_with_tracking_param_gives_video(self):
        url = f"https://youtu.be/{VID_A}?si=abcXYZ"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_bare_playlist_url(self, caplog):
        url = "https://www.youtube.com/playlist?list=PLxxxx"
        assert library_links.classify_url(url) == ("playlist", url)
        assert not caplog.records

    def test_garbage_is_unrecognised(self):
        assert library_links.classify_url("not a url") is None

    # A real URL parser (urllib.parse), not a cut-at-? id helper: every shape
    # below carries a v= id and must give the video, regardless of what else
    # is on the query string or where v= falls in it.

    def test_search_result_param_gives_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&pp=abcXYZ"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_music_subdomain_gives_video(self):
        url = f"https://music.youtube.com/watch?v={VID_A}&si=abcXYZ"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_timestamp_param_gives_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&t=30s"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_param_before_v_gives_video(self):
        url = f"https://www.youtube.com/watch?feature=shared&v={VID_A}"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_param_between_v_and_list_gives_only_the_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&t=30s&list=Y"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_mix_link_gives_only_the_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&pp=abc&list=RDX&start_radio=1"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_list_before_v_gives_video(self):
        url = f"https://www.youtube.com/watch?list=Y&v={VID_A}"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_mobile_subdomain_gives_video(self):
        url = f"https://m.youtube.com/watch?v={VID_A}"
        assert library_links.classify_url(url) == ("video", VID_A)

    def test_non_youtube_host_with_v_param_is_unrecognised(self):
        url = f"https://notyoutube.com/watch?v={VID_A}"
        assert library_links.classify_url(url) is None


# ---------------------------------------------------------------------------
# Expand
# ---------------------------------------------------------------------------


def mock_yt_dlp(monkeypatch, output: str) -> list[list[str]]:
    """Make the yt-dlp call return ``output``; returns the commands it was given."""
    commands: list[list[str]] = []

    def fake_check_output(cmd, timeout=None):
        commands.append(cmd)
        return output.encode("utf-8")

    monkeypatch.setattr(library_links.subprocess, "check_output", fake_check_output)
    return commands


class TestReadPlaylist:
    def test_parses_the_title_ids_and_titles(self, monkeypatch):
        commands = mock_yt_dlp(
            monkeypatch,
            json.dumps(
                {
                    "title": "Karaoke Night",
                    "entries": [
                        {"id": VID_A, "title": "First Song"},
                        {"id": VID_B, "title": "Second Song"},
                    ],
                }
            ),
        )

        playlist = library_links.read_playlist("https://www.youtube.com/playlist?list=Y")

        assert playlist == library_links.Playlist(
            title="Karaoke Night",
            videos=[
                library_links.PlaylistVideo(id=VID_A, title="First Song"),
                library_links.PlaylistVideo(id=VID_B, title="Second Song"),
            ],
        )
        assert "--flat-playlist" in commands[0] and "-J" in commands[0]
        assert commands[0][-2:] == ["--", "https://www.youtube.com/playlist?list=Y"]

    def test_reads_each_videos_channel_and_length_when_given(self, monkeypatch):
        mock_yt_dlp(
            monkeypatch,
            json.dumps(
                {
                    "title": "Detailed",
                    "entries": [
                        {"id": VID_A, "title": "A", "channel": "Chan", "duration": 213.0},
                        {"id": VID_B, "title": "B", "uploader": "Uploader", "duration": "3:33"},
                        {"id": "ccccccccccc", "title": "C", "channel": None, "duration": None},
                    ],
                }
            ),
        )

        videos = library_links.read_playlist("https://www.youtube.com/playlist?list=Y").videos

        assert [(v.channel, v.duration) for v in videos] == [
            ("Chan", 213),
            ("Uploader", None),  # a length that isn't a number is no length
            ("", None),
        ]

    def test_a_link_that_looks_like_an_option_stays_a_url(self, monkeypatch):
        commands = mock_yt_dlp(monkeypatch, json.dumps({"title": "T", "entries": []}))

        library_links.read_playlist("--exec=x.youtube.com?list=1")

        assert commands[0][-2:] == ["--", "--exec=x.youtube.com?list=1"]

    def test_skips_entries_without_an_id(self, monkeypatch):
        mock_yt_dlp(
            monkeypatch,
            json.dumps(
                {
                    "title": "Mixed",
                    "entries": [
                        {"title": "Gone"},
                        None,
                        {"id": "", "title": "Blank"},
                        {"id": VID_A},
                    ],
                }
            ),
        )

        playlist = library_links.read_playlist("https://www.youtube.com/playlist?list=Y")

        assert playlist.videos == [library_links.PlaylistVideo(id=VID_A, title=VID_A)]

    def test_a_playlist_with_no_entries_is_empty(self, monkeypatch):
        mock_yt_dlp(monkeypatch, json.dumps({"title": "Empty"}))

        playlist = library_links.read_playlist("https://www.youtube.com/playlist?list=Y")

        assert playlist == library_links.Playlist(title="Empty", videos=[])

    def test_output_that_is_not_json_raises_value_error(self, monkeypatch):
        mock_yt_dlp(monkeypatch, "WARNING: not json")

        with pytest.raises(ValueError):
            library_links.read_playlist("https://www.youtube.com/playlist?list=Y")


class TestExpandPlaylist:
    def test_returns_the_ids_only(self, monkeypatch):
        mock_yt_dlp(
            monkeypatch,
            json.dumps(
                {
                    "title": "T",
                    "entries": [{"id": VID_A, "title": "A"}, {"title": "no id"}, {"id": VID_B}],
                }
            ),
        )

        ids = library_links.expand_playlist("https://www.youtube.com/playlist?list=Y")

        assert ids == [VID_A, VID_B]


class TestLibraryFiles:
    def test_video_wins_over_an_mp3_sharing_its_id(self, tmp_path):
        video = tmp_path / f"Title---{VID_A}.mp4"
        video.touch()
        (tmp_path / f"Title---{VID_A}.mp3").touch()

        assert library_links.library_files(tmp_path) == {VID_A: video}
