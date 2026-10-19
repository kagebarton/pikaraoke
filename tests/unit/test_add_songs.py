"""Unit tests for scripts/add_songs.py — classify, expand, dedupe, handoff.

Subprocess (yt-dlp) is mocked throughout; nothing here downloads or runs
the pipeline.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

# scripts/ is not a package — load the module straight from its file. It must
# be registered in sys.modules before exec so @dataclass can resolve its own
# module by __module__.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "add_songs.py"
_spec = importlib.util.spec_from_file_location("add_songs", _SCRIPT)
add_songs = importlib.util.module_from_spec(_spec)
sys.modules["add_songs"] = add_songs
_spec.loader.exec_module(add_songs)


VID_A = "dQw4w9WgXcQ"
VID_B = "abcdefghijk"


# ---------------------------------------------------------------------------
# Classify
# ---------------------------------------------------------------------------


class TestClassifyUrl:
    def test_video_watch_url(self):
        url = f"https://www.youtube.com/watch?v={VID_A}"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_video_with_list_param_gives_only_the_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&list=PLxxxx"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_short_url_with_tracking_param_gives_video(self):
        url = f"https://youtu.be/{VID_A}?si=abcXYZ"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_bare_playlist_url(self, caplog):
        url = "https://www.youtube.com/playlist?list=PLxxxx"
        assert add_songs.classify_url(url) == ("playlist", url)
        # A playlist is not a parse failure: the app's id helper must not be
        # probed (it logs an ERROR for any URL it can't parse).
        assert not caplog.records

    def test_garbage_is_unrecognised(self):
        assert add_songs.classify_url("not a url") is None


# ---------------------------------------------------------------------------
# Expand
# ---------------------------------------------------------------------------


class TestExpandPlaylist:
    def test_parses_ids_and_skips_blank_lines(self, monkeypatch):
        output = f"{VID_A}\n{VID_B}\n\nzzzzzzzzzzz\n"
        monkeypatch.setattr(
            add_songs.subprocess, "check_output", lambda cmd: output.encode("utf-8")
        )

        ids = add_songs.expand_playlist("https://www.youtube.com/playlist?list=Y")

        assert ids == [VID_A, VID_B, "zzzzzzzzzzz"]


class TestResolveUrlsExpansionFailure:
    def test_called_process_error_is_reported_and_other_urls_continue(self, monkeypatch, capsys):
        def fake_expand(url):
            if "bad" in url:
                raise subprocess.CalledProcessError(1, "yt-dlp")
            return [VID_B]

        monkeypatch.setattr(add_songs, "expand_playlist", fake_expand)
        urls = [
            "https://www.youtube.com/playlist?list=bad",
            "https://www.youtube.com/playlist?list=good",
        ]

        entries = add_songs.resolve_urls(urls, existing_ids=set())

        assert [e.id for e in entries] == [VID_B]
        assert "failed to expand playlist" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------


class TestResolveUrlsDedupe:
    def test_id_already_in_library_is_marked_status(self):
        url = f"https://www.youtube.com/watch?v={VID_A}"

        entries = add_songs.resolve_urls([url], existing_ids={VID_A})

        assert entries == [add_songs.UrlEntry(id=VID_A, source=url, status="already in library")]

    def test_id_repeated_across_urls_appears_once(self):
        url1 = f"https://www.youtube.com/watch?v={VID_A}"
        url2 = f"https://youtu.be/{VID_A}"

        entries = add_songs.resolve_urls([url1, url2], existing_ids=set())

        assert len(entries) == 1
        assert entries[0].id == VID_A
        assert entries[0].status == "new"


# ---------------------------------------------------------------------------
# Handoff
# ---------------------------------------------------------------------------


class TestHandoff:
    def test_no_caption_on_disk_keeps_fetch_plan(self, tmp_path, monkeypatch):
        mock_run = MagicMock()
        monkeypatch.setattr(add_songs.rab, "resolve_and_run", mock_run)
        song_path = str(tmp_path / f"Title---{VID_A}.mp4")
        config = MagicMock()
        genius = MagicMock()

        jobs = add_songs.handoff([song_path], config, genius)

        assert len(jobs) == 1
        assert jobs[0].bundle is None
        assert jobs[0].plan.kind == "fetch"
        mock_run.assert_called_once_with(jobs, config, genius)

    def test_caption_on_disk_is_gated_instead_of_refetched(self, tmp_path, monkeypatch):
        mock_run = MagicMock()
        monkeypatch.setattr(add_songs.rab, "resolve_and_run", mock_run)
        monkeypatch.setattr(add_songs.rab, "probe_duration", lambda p: None)  # skip wpm gate
        song_path = tmp_path / f"Title---{VID_A}.mp4"
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / f"Title---{VID_A}.srt").write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nla\n", encoding="utf-8"
        )
        config = MagicMock()
        genius = MagicMock()

        jobs = add_songs.handoff([str(song_path)], config, genius)

        assert len(jobs) == 1
        assert jobs[0].plan.kind == "seed"
        assert jobs[0].plan.seed.get("lyrics_origin") == "srt"
        mock_run.assert_called_once_with(jobs, config, genius)
