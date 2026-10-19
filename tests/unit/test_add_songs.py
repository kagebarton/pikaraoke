"""Unit tests for scripts/add_songs.py — classify, expand, dedupe, handoff.

Subprocess (yt-dlp) is mocked throughout; nothing here downloads or runs
the pipeline.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
        assert not caplog.records

    def test_garbage_is_unrecognised(self):
        assert add_songs.classify_url("not a url") is None

    # A real URL parser (urllib.parse), not a cut-at-? id helper: every shape
    # below carries a v= id and must give the video, regardless of what else
    # is on the query string or where v= falls in it.

    def test_search_result_param_gives_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&pp=abcXYZ"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_music_subdomain_gives_video(self):
        url = f"https://music.youtube.com/watch?v={VID_A}&si=abcXYZ"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_timestamp_param_gives_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&t=30s"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_param_before_v_gives_video(self):
        url = f"https://www.youtube.com/watch?feature=shared&v={VID_A}"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_param_between_v_and_list_gives_only_the_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&t=30s&list=Y"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_mix_link_gives_only_the_video(self):
        url = f"https://www.youtube.com/watch?v={VID_A}&pp=abc&list=RDX&start_radio=1"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_list_before_v_gives_video(self):
        url = f"https://www.youtube.com/watch?list=Y&v={VID_A}"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_mobile_subdomain_gives_video(self):
        url = f"https://m.youtube.com/watch?v={VID_A}"
        assert add_songs.classify_url(url) == ("video", VID_A)

    def test_non_youtube_host_with_v_param_is_unrecognised(self):
        url = f"https://notyoutube.com/watch?v={VID_A}"
        assert add_songs.classify_url(url) is None


# ---------------------------------------------------------------------------
# Expand
# ---------------------------------------------------------------------------


class TestExpandPlaylist:
    def test_parses_ids_and_skips_blank_lines(self, monkeypatch):
        output = f"{VID_A}\n{VID_B}\n\nzzzzzzzzzzz\n"
        monkeypatch.setattr(
            add_songs.subprocess,
            "check_output",
            lambda cmd, timeout=None: output.encode("utf-8"),
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

        entries, unreadable = add_songs.resolve_urls(urls, library={})

        assert [e.id for e in entries] == [VID_B]
        assert unreadable == 1
        assert "failed to expand playlist" in capsys.readouterr().out

    def test_timeout_is_reported_and_other_urls_continue(self, monkeypatch, capsys):
        def fake_expand(url):
            if "slow" in url:
                raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=300)
            return [VID_B]

        monkeypatch.setattr(add_songs, "expand_playlist", fake_expand)
        urls = [
            "https://www.youtube.com/playlist?list=slow",
            "https://www.youtube.com/playlist?list=good",
        ]

        entries, unreadable = add_songs.resolve_urls(urls, library={})

        assert [e.id for e in entries] == [VID_B]
        assert unreadable == 1
        assert "timed out expanding playlist" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------


def _add_bundle(folder: Path, stem: str, text: str = "{}") -> None:
    (folder / "alignment_debug").mkdir(exist_ok=True)
    (folder / "alignment_debug" / f"{stem}.json").write_text(text, encoding="utf-8")


def _add_karaoke_file(folder: Path, stem: str) -> None:
    (folder / "karaoke").mkdir(exist_ok=True)
    (folder / "karaoke" / f"{stem}.ass").touch()


class TestResolveUrlsDedupe:
    def test_video_with_a_bundle_is_already_in_library(self, tmp_path):
        url = f"https://www.youtube.com/watch?v={VID_A}"
        video = tmp_path / f"Title---{VID_A}.mp4"
        video.touch()
        _add_bundle(tmp_path, video.stem)

        entries, unreadable = add_songs.resolve_urls([url], add_songs.library_files(tmp_path))

        assert entries == [add_songs.UrlEntry(id=VID_A, source=url, status="already in library")]
        assert unreadable == 0

    def test_video_without_a_bundle_is_in_library_not_processed(self, tmp_path):
        url = f"https://www.youtube.com/watch?v={VID_A}"
        (tmp_path / f"Title---{VID_A}.mp4").touch()

        entries, unreadable = add_songs.resolve_urls([url], add_songs.library_files(tmp_path))

        assert entries == [
            add_songs.UrlEntry(id=VID_A, source=url, status="in library, not processed")
        ]
        assert unreadable == 0

    def test_video_with_a_karaoke_file_and_no_bundle_is_already_in_library(self, tmp_path):
        # A song that ran with no lyrics (transcribed) gets a karaoke file but no bundle.
        url = f"https://www.youtube.com/watch?v={VID_A}"
        video = tmp_path / f"Title---{VID_A}.mp4"
        video.touch()
        _add_karaoke_file(tmp_path, video.stem)

        entries, _ = add_songs.resolve_urls([url], add_songs.library_files(tmp_path))

        assert [e.status for e in entries] == ["already in library"]

    def test_video_with_an_unreadable_bundle_and_no_karaoke_file_is_already_in_library(
        self, tmp_path
    ):
        url = f"https://www.youtube.com/watch?v={VID_A}"
        video = tmp_path / f"Title---{VID_A}.mp4"
        video.touch()
        _add_bundle(tmp_path, video.stem, text="not json")

        entries, _ = add_songs.resolve_urls([url], add_songs.library_files(tmp_path))

        assert [e.status for e in entries] == ["already in library"]

    def test_mp3_with_the_id_is_already_in_library(self, tmp_path):
        url = f"https://www.youtube.com/watch?v={VID_A}"
        (tmp_path / f"Title---{VID_A}.mp3").touch()

        entries, _ = add_songs.resolve_urls([url], add_songs.library_files(tmp_path))

        assert [e.status for e in entries] == ["already in library"]

    def test_video_wins_over_an_mp3_sharing_its_id(self, tmp_path):
        video = tmp_path / f"Title---{VID_A}.mp4"
        video.touch()
        (tmp_path / f"Title---{VID_A}.mp3").touch()

        assert add_songs.library_files(tmp_path) == {VID_A: video}

    def test_id_repeated_across_urls_appears_once(self):
        url1 = f"https://www.youtube.com/watch?v={VID_A}"
        url2 = f"https://youtu.be/{VID_A}"

        entries, unreadable = add_songs.resolve_urls([url1, url2], library={})

        assert len(entries) == 1
        assert entries[0].id == VID_A
        assert entries[0].status == "new"
        assert unreadable == 0

    def test_unrecognised_url_counts_as_unreadable(self):
        entries, unreadable = add_songs.resolve_urls(["not a url"], library={})

        assert entries == []
        assert unreadable == 1


class TestPrintReport:
    def test_status_column_is_sized_from_the_longest_status(self, capsys):
        entries = [add_songs.UrlEntry(VID_A, "src", "in library, not processed")]

        add_songs.print_report(entries)

        rule = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("-"))
        assert rule.endswith("  " + "-" * len("in library, not processed"))


# ---------------------------------------------------------------------------
# Handoff
# ---------------------------------------------------------------------------


class TestHandoff:
    def test_no_caption_on_disk_keeps_fetch_plan(self, tmp_path, monkeypatch):
        mock_run = MagicMock(return_value=0)
        monkeypatch.setattr(add_songs.rab, "resolve_and_run", mock_run)
        song_path = str(tmp_path / f"Title---{VID_A}.mp4")

        rc = add_songs.handoff([song_path])

        assert rc == 0
        jobs = mock_run.call_args.args[0]
        assert len(jobs) == 1
        assert jobs[0].bundle is None
        assert jobs[0].plan.kind == "fetch"
        mock_run.assert_called_once_with(jobs)

    def test_caption_on_disk_is_gated_instead_of_refetched(self, tmp_path, monkeypatch):
        mock_run = MagicMock(return_value=0)
        monkeypatch.setattr(add_songs.rab, "resolve_and_run", mock_run)
        monkeypatch.setattr(add_songs.rab, "probe_duration", lambda p: None)  # skip wpm gate
        song_path = tmp_path / f"Title---{VID_A}.mp4"
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / f"Title---{VID_A}.srt").write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nla\n", encoding="utf-8"
        )

        rc = add_songs.handoff([str(song_path)])

        assert rc == 0
        jobs = mock_run.call_args.args[0]
        assert len(jobs) == 1
        assert jobs[0].plan.kind == "seed"
        assert jobs[0].plan.seed.get("lyrics_origin") == "srt"

    def test_returns_the_pipeline_exit_code(self, tmp_path, monkeypatch):
        monkeypatch.setattr(add_songs.rab, "resolve_and_run", MagicMock(return_value=1))
        song_path = str(tmp_path / f"Title---{VID_A}.mp4")

        rc = add_songs.handoff([song_path])

        assert rc == 1


# ---------------------------------------------------------------------------
# main() -- exit code reflects link, download and pipeline failures
# ---------------------------------------------------------------------------


def _fake_download_manager_class(plan: dict, folder: Path):
    """A DownloadManager stand-in driven by a scripted ``id -> (rc, fires)`` map.

    Emits ``song_downloaded`` through the real ``EventSystem`` it's given
    (``events`` kwarg), so ``main()``'s event-driven success/failure counting
    runs for real; only the download itself (and the app DB/library it would
    otherwise touch) is faked. A plan value that is an exception is raised
    instead; an id missing from ``plan`` fails the test if it is downloaded.
    """

    class FakeDownloadManager:
        def __init__(self, *, events, **_kwargs):
            self._events = events

        def _execute_download(self, video_url, enqueue, user, title):
            vid = video_url.rsplit("v=", 1)[-1]
            assert vid in plan, f"unexpected download of {vid}"
            if isinstance(plan[vid], Exception):
                raise plan[vid]
            rc, fires = plan[vid]
            if fires:
                self._events.emit("song_downloaded", str(folder / f"Title---{vid}.mp4"))
            return rc

    return FakeDownloadManager


class TestMain:
    @pytest.fixture(autouse=True)
    def _isolated_from_the_machine(self, monkeypatch, tmp_path_factory):
        """Keep ``main()`` from leaking process state or touching the user's config."""
        # setup_process sets the allocator env var and configures logging.
        monkeypatch.setattr(add_songs.rab, "setup_process", lambda: None)
        # An absolute path skips the legacy ./config.ini migration. It stays out of
        # tmp_path, which is the test's library folder.
        config_path = str(tmp_path_factory.mktemp("prefs") / "config.ini")
        real_preferences = add_songs.PreferenceManager
        monkeypatch.setattr(add_songs, "PreferenceManager", lambda: real_preferences(config_path))

    def test_happy_path_download_and_pipeline_succeed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "add_songs.py",
                f"https://www.youtube.com/watch?v={VID_A}",
                "--folder",
                str(tmp_path),
                "--yes",
            ],
        )
        monkeypatch.setattr(
            add_songs, "DownloadManager", _fake_download_manager_class({VID_A: (0, True)}, tmp_path)
        )
        mock_handoff = MagicMock(return_value=0)
        monkeypatch.setattr(add_songs, "handoff", mock_handoff)

        assert add_songs.main() == 0
        mock_handoff.assert_called_once()

    def test_pipeline_failure_gives_exit_1(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "add_songs.py",
                f"https://www.youtube.com/watch?v={VID_A}",
                "--folder",
                str(tmp_path),
                "--yes",
            ],
        )
        monkeypatch.setattr(
            add_songs, "DownloadManager", _fake_download_manager_class({VID_A: (0, True)}, tmp_path)
        )
        monkeypatch.setattr(add_songs, "handoff", MagicMock(return_value=1))

        assert add_songs.main() == 1

    def test_download_with_no_event_counts_as_failed(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "add_songs.py",
                f"https://www.youtube.com/watch?v={VID_A}",
                "--folder",
                str(tmp_path),
                "--yes",
            ],
        )
        monkeypatch.setattr(
            add_songs,
            "DownloadManager",
            _fake_download_manager_class({VID_A: (0, False)}, tmp_path),
        )
        mock_handoff = MagicMock()
        monkeypatch.setattr(add_songs, "handoff", mock_handoff)

        assert add_songs.main() == 1
        mock_handoff.assert_not_called()
        assert "no file with that id is in the folder" in capsys.readouterr().out

    def test_exception_in_one_download_is_counted_failed_and_the_next_still_runs(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "add_songs.py",
                f"https://www.youtube.com/watch?v={VID_A}",
                f"https://www.youtube.com/watch?v={VID_B}",
                "--folder",
                str(tmp_path),
                "--yes",
            ],
        )
        monkeypatch.setattr(
            add_songs,
            "DownloadManager",
            _fake_download_manager_class({VID_A: RuntimeError("boom"), VID_B: (0, True)}, tmp_path),
        )
        mock_handoff = MagicMock(return_value=0)
        monkeypatch.setattr(add_songs, "handoff", mock_handoff)

        assert add_songs.main() == 1
        assert mock_handoff.call_args.args[0] == [str(tmp_path / f"Title---{VID_B}.mp4")]
        out = capsys.readouterr().out
        assert f"FAILED: {VID_A}" in out
        assert "Downloaded: 1 Failed: 1" in out

    def test_unprocessed_video_is_handed_off_without_a_download(
        self, tmp_path, monkeypatch, capsys
    ):
        video = tmp_path / f"Title---{VID_A}.mp4"
        video.touch()
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "add_songs.py",
                f"https://www.youtube.com/watch?v={VID_A}",
                "--folder",
                str(tmp_path),
                "--yes",
            ],
        )
        monkeypatch.setattr(
            add_songs, "DownloadManager", _fake_download_manager_class({}, tmp_path)
        )
        mock_handoff = MagicMock(return_value=0)
        monkeypatch.setattr(add_songs, "handoff", mock_handoff)

        assert add_songs.main() == 0
        assert mock_handoff.call_args.args[0] == [str(video)]
        assert "in library, not processed" in capsys.readouterr().out

    def test_unprocessed_videos_follow_the_new_downloads_in_the_handoff(
        self, tmp_path, monkeypatch
    ):
        video = tmp_path / f"Title---{VID_B}.mp4"
        video.touch()
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "add_songs.py",
                f"https://www.youtube.com/watch?v={VID_B}",
                f"https://www.youtube.com/watch?v={VID_A}",
                "--folder",
                str(tmp_path),
                "--yes",
            ],
        )
        monkeypatch.setattr(
            add_songs, "DownloadManager", _fake_download_manager_class({VID_A: (0, True)}, tmp_path)
        )
        mock_handoff = MagicMock(return_value=0)
        monkeypatch.setattr(add_songs, "handoff", mock_handoff)

        assert add_songs.main() == 0
        assert mock_handoff.call_args.args[0] == [
            str(tmp_path / f"Title---{VID_A}.mp4"),
            str(video),
        ]

    def test_processed_video_is_not_handed_off(self, tmp_path, monkeypatch, capsys):
        video = tmp_path / f"Title---{VID_A}.mp4"
        video.touch()
        _add_bundle(tmp_path, video.stem)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "add_songs.py",
                f"https://www.youtube.com/watch?v={VID_A}",
                "--folder",
                str(tmp_path),
                "--yes",
            ],
        )
        mock_handoff = MagicMock()
        monkeypatch.setattr(add_songs, "handoff", mock_handoff)

        assert add_songs.main() == 0
        mock_handoff.assert_not_called()
        assert "Nothing new to download." in capsys.readouterr().out

    def test_confirm_prompt_counts_downloads_and_unprocessed_songs(self, tmp_path, monkeypatch):
        (tmp_path / f"Title---{VID_B}.mp4").touch()
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "add_songs.py",
                f"https://www.youtube.com/watch?v={VID_A}",
                f"https://www.youtube.com/watch?v={VID_B}",
                "--folder",
                str(tmp_path),
            ],
        )
        prompts = []
        monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "n")

        assert add_songs.main() == 0
        assert prompts == ["Proceed with 1 download(s) and 1 unprocessed song(s)? [y/N] "]

    def test_one_unreadable_url_with_nothing_to_download_gives_exit_1(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["add_songs.py", "not a url", "--folder", str(tmp_path), "--yes"]
        )

        assert add_songs.main() == 1

    def test_dry_run_with_unreadable_url_gives_exit_1(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["add_songs.py", "not a url", "--folder", str(tmp_path), "--dry-run"]
        )

        assert add_songs.main() == 1
