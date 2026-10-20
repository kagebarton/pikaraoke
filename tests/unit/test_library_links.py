"""Unit tests for pikaraoke/lib/library_links.py -- classify, expand, library lookup.

Subprocess (yt-dlp) is mocked; nothing here touches the network.
"""

from pikaraoke.lib import library_links

VID_A = "dQw4w9WgXcQ"
VID_B = "abcdefghijk"


# ---------------------------------------------------------------------------
# Classify
# ---------------------------------------------------------------------------


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


class TestExpandPlaylist:
    def test_parses_ids_and_skips_blank_lines(self, monkeypatch):
        output = f"{VID_A}\n{VID_B}\n\nzzzzzzzzzzz\n"
        monkeypatch.setattr(
            library_links.subprocess,
            "check_output",
            lambda cmd, timeout=None: output.encode("utf-8"),
        )

        ids = library_links.expand_playlist("https://www.youtube.com/playlist?list=Y")

        assert ids == [VID_A, VID_B, "zzzzzzzzzzz"]


class TestLibraryFiles:
    def test_video_wins_over_an_mp3_sharing_its_id(self, tmp_path):
        video = tmp_path / f"Title---{VID_A}.mp4"
        video.touch()
        (tmp_path / f"Title---{VID_A}.mp3").touch()

        assert library_links.library_files(tmp_path) == {VID_A: video}
