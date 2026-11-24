"""Unit tests for scripts/regen_alignment_bundles.py -- the CLI flow.

The planning, caption gate, backup/wipe and lyric-prep core lives in
pikaraoke/lib/library_regen.py (test_library_regen.py).  Here: the report, the
``--song --reset`` wiring of ``main()``, the shared ``resolve_and_run`` setup, the
LRCLIB backfill batch and the ``--lrclib-auto`` check.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib import library_regen, lrc_auto_timing, lrclib
from pikaraoke.lib.genius import GeniusHit
from pikaraoke.pipeline.config import PipelineConfig
from tests.unit.movie_slices import CLIP_S, heard_words, lrc_slice

# scripts/ is not a package — load the module straight from its file. It must
# be registered in sys.modules before exec so @dataclass can resolve its own
# module by __module__.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "regen_alignment_bundles.py"
_spec = importlib.util.spec_from_file_location("regen_alignment_bundles", _SCRIPT)
regen = importlib.util.module_from_spec(_spec)
sys.modules["regen_alignment_bundles"] = regen
_spec.loader.exec_module(regen)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _touch_video(folder: Path, stem: str) -> Path:
    path = folder / f"{stem}.mp4"
    path.touch()
    return path


def _job(folder: Path, stem: str, bundle: dict | None) -> "regen.SongJob":
    return regen.SongJob(song_path=folder / f"{stem}.mp4", bundle=bundle, stale_reason="all")


def _make_srt(folder: Path, stem: str, n_words: int = 1) -> Path:
    subs = folder / "subtitles"
    subs.mkdir(exist_ok=True)
    words = " ".join(["la"] * n_words)
    srt = subs / f"{stem}.srt"
    srt.write_text(f"1\n00:00:01,000 --> 00:00:04,000\n{words}\n", encoding="utf-8")
    return srt


# A stem with a real 11-char YouTube id, so extract_youtube_id picks it up.
YT_STEM = "Song---dQw4w9WgXcQ"


# ---------------------------------------------------------------------------
# print_report / main — --song --reset wiring
# ---------------------------------------------------------------------------


class TestPrintReportScope:
    def test_selected_with_reset_says_reset(self, tmp_path, capsys):
        regen.print_report([], tmp_path, reset=True, selected=True)

        assert "Selection: selected songs (reset)" in capsys.readouterr().out

    def test_selected_without_reset_does_not(self, tmp_path, capsys):
        regen.print_report([], tmp_path, reset=False, selected=True)

        out = capsys.readouterr().out
        assert "Selection: selected songs\n" in out
        assert "(reset)" not in out


class TestMainSongReset:
    """``--song <x> --reset`` backs up and wipes only the selected song's files.

    The helpers' scoping is tested above; this drives ``main()`` so the wiring
    between selection, backup and wipe is covered too. Siblings that must stay
    untouched: a longer-stem video (``Mr.live``), an ``.mp3`` whose stem also
    starts with ``Mr.`` (the app plays it, regen never processes it) and an
    unrelated video.
    """

    SELECTED = "Mr"
    UNTOUCHED = ("Mr.live", "Mr. Brightside---abcdefghijk", "Other")

    def _setup_library(self, tmp_path):
        _touch_video(tmp_path, "Mr")
        _touch_video(tmp_path, "Mr.live")
        _touch_video(tmp_path, "Other")
        (tmp_path / "Mr. Brightside---abcdefghijk.mp3").touch()
        for sub, ext in (
            ("subtitles", ".srt"),
            ("subtitles", ".srt.generated"),
            ("karaoke", ".ass"),
            ("lyrics", ".txt"),
            ("alignment_debug", ".json"),
        ):
            (tmp_path / sub).mkdir(exist_ok=True)
            for stem in (self.SELECTED, *self.UNTOUCHED):
                content = "{}" if ext == ".json" else stem
                (tmp_path / sub / f"{stem}{ext}").write_text(content, encoding="utf-8")

    def test_only_the_selected_songs_files_are_backed_up_and_wiped(
        self, tmp_path, monkeypatch, capsys
    ):
        self._setup_library(tmp_path)
        monkeypatch.setenv("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        monkeypatch.setattr(
            sys,
            "argv",
            ["regen", str(tmp_path), "--song", "Mr", "--reset", "--yes"],
        )
        mock_run = MagicMock(return_value=0)
        monkeypatch.setattr(regen, "resolve_and_run", mock_run)

        assert regen.main() == 0

        # Only the selected song is handed to the run path.
        jobs = mock_run.call_args.args[0]
        assert [j.song_path.name for j in jobs] == ["Mr.mp4"]

        # Backed up: the selected song's files, and nothing of the siblings'.
        (backup,) = tmp_path.glob("regen_backups/*")
        for sub, ext in (
            ("subtitles", ".srt"),
            ("subtitles", ".srt.generated"),
            ("karaoke", ".ass"),
            ("lyrics", ".txt"),
            ("alignment_debug", ".json"),
        ):
            assert (backup / sub / f"Mr{ext}").exists()
            for stem in self.UNTOUCHED:
                assert not (backup / sub / f"{stem}{ext}").exists()

        # Wiped: the selected song's regenerable outputs (never its bundle).
        for sub, ext in (
            ("subtitles", ".srt"),
            ("subtitles", ".srt.generated"),
            ("karaoke", ".ass"),
            ("lyrics", ".txt"),
        ):
            assert not (tmp_path / sub / f"Mr{ext}").exists()
        assert (tmp_path / "alignment_debug" / "Mr.json").exists()

        # Untouched: every sibling's files, in every folder.
        for sub, ext in (
            ("subtitles", ".srt"),
            ("subtitles", ".srt.generated"),
            ("karaoke", ".ass"),
            ("lyrics", ".txt"),
            ("alignment_debug", ".json"),
        ):
            for stem in self.UNTOUCHED:
                assert (tmp_path / sub / f"{stem}{ext}").exists()

        out = capsys.readouterr().out
        assert "Selection: selected songs (reset)" in out
        assert "for the selected songs" in out

    def test_a_reset_that_cannot_remove_a_file_stops_with_a_message(
        self, tmp_path, monkeypatch, capsys
    ):
        self._setup_library(tmp_path)
        monkeypatch.setenv("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        monkeypatch.setattr(
            sys,
            "argv",
            ["regen", str(tmp_path), "--song", "Mr", "--reset", "--yes"],
        )
        locked = tmp_path / "subtitles" / "Mr.srt"
        monkeypatch.setattr(
            regen,
            "clear_output_folders",
            MagicMock(side_effect=PermissionError(13, "in use", str(locked))),
        )
        mock_run = MagicMock(return_value=0)
        monkeypatch.setattr(regen, "resolve_and_run", mock_run)

        assert regen.main() == 1

        mock_run.assert_not_called()
        err = capsys.readouterr().err
        assert "Reset stopped" in err
        assert "in use" in err


class TestResolveAndRunSetup:
    """``resolve_and_run`` builds its own config and Genius client, so both CLIs share it."""

    def test_warns_when_no_genius_token(self, monkeypatch, capsys):
        monkeypatch.setattr(regen, "_make_genius", lambda: SimpleNamespace(_token=""))
        monkeypatch.setattr(regen, "execute_fetches", lambda jobs: None)
        monkeypatch.setattr(regen, "execute_lrclib_backfill", lambda jobs, config: None)
        monkeypatch.setattr(regen, "prompt_jobs", lambda jobs, genius: None)

        assert regen.resolve_and_run([]) == 0

        assert "no genius_token in preferences" in capsys.readouterr().out

    def test_hands_the_run_a_config_and_the_genius_client(self, tmp_path, monkeypatch):
        genius = SimpleNamespace(_token="tok")
        monkeypatch.setattr(regen, "_make_genius", lambda: genius)
        monkeypatch.setattr(regen, "get_temp_directory", lambda: str(tmp_path))
        monkeypatch.setattr(regen, "execute_fetches", lambda jobs: None)
        monkeypatch.setattr(regen, "execute_lrclib_backfill", lambda jobs, config: None)
        monkeypatch.setattr(regen, "prompt_jobs", lambda jobs, genius: None)
        job = _job(tmp_path, "s", None)
        job.plan = regen.Plan(kind="fetch", label="x")
        mock_run = MagicMock(return_value=(1, 0, 0))
        monkeypatch.setattr(regen, "run_jobs", mock_run)

        assert regen.resolve_and_run([job]) == 0

        _, config, passed_genius = mock_run.call_args.args
        assert config.intermediate_dir == str(tmp_path)
        assert passed_genius is genius


# ---------------------------------------------------------------------------
# execute_lrclib_backfill — LRCLIB variants for genius reuse plans (E1)
# ---------------------------------------------------------------------------


class TestExecuteLrclibBackfill:
    def _reuse_job(self, tmp_path, stem="s", lines=("hello", "world")):
        bundle = {
            "lyrics": {
                "origin": "genius",
                "lines": list(lines),
                "genius": {"id": 9, "title": "H", "artist": "W"},
            },
            "media_duration_s": 200.0,
        }
        job = _job(tmp_path, stem, bundle)
        job.plan = regen.resolve_plan(job, reset=False)
        assert job.plan.kind == "seed"
        assert job.plan.seed["lyrics_origin"] == "genius"
        return job

    def test_calls_ensure_lrc_for_a_genius_reuse_plan(self, tmp_path, monkeypatch):
        job = self._reuse_job(tmp_path)
        mock = MagicMock(return_value=None)
        monkeypatch.setattr(lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([job], PipelineConfig())

        mock.assert_called_once_with(job.song_path, "H", "W", ["hello", "world"], 200.0)

    def test_knob_off_skips_entirely(self, tmp_path, monkeypatch):
        job = self._reuse_job(tmp_path)
        mock = MagicMock()
        monkeypatch.setattr(lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([job], PipelineConfig(lrclib_fill=False))

        mock.assert_not_called()

    def test_sidecar_plan_is_never_touched(self, tmp_path, monkeypatch):
        # A fresh Genius selection resolves via LyricsFetchStage when it
        # runs -- one call site per plan kind, no double-fetch here.
        job = _job(tmp_path, YT_STEM, None)
        job.plan = regen.Plan(kind="sidecar", genius_id=123, label="prompt -> genius")
        mock = MagicMock()
        monkeypatch.setattr(lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([job], PipelineConfig())

        mock.assert_not_called()

    def test_srt_reuse_plan_is_never_touched(self, tmp_path, monkeypatch):
        _make_srt(tmp_path, "plain")
        job = _job(tmp_path, "plain", {"lyrics": {"origin": "srt"}})
        job.plan = regen.resolve_plan(job, reset=False)
        assert job.plan.seed.get("lyrics_origin") == "srt"
        mock = MagicMock()
        monkeypatch.setattr(lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([job], PipelineConfig())

        mock.assert_not_called()

    def test_one_failing_song_does_not_abort_the_batch(self, tmp_path, monkeypatch):
        bad = self._reuse_job(tmp_path, stem="bad")
        good = self._reuse_job(tmp_path, stem="good")
        mock = MagicMock(side_effect=[OSError("disk full"), None])
        monkeypatch.setattr(lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([bad, good], PipelineConfig())

        assert mock.call_count == 2  # the OSError on "bad" didn't stop "good"


# ---------------------------------------------------------------------------
# --song --reset with a different Genius pick
# ---------------------------------------------------------------------------


class TestResetWithNewGeniusPick:
    """``--song X --reset`` that picks another Genius song used to keep the old
    song's ``.lrc``: a reset keeps ``.lrc`` files and ``ensure_lrc`` reuses any
    file on disk, so the new song ran against the old song's LRCLIB timing."""

    def test_the_old_lrc_is_gone_when_the_pipeline_runs(self, tmp_path, monkeypatch):
        _touch_video(tmp_path, YT_STEM)
        (tmp_path / "alignment_debug").mkdir()
        bundle = {
            "lyrics": {"origin": "genius", "genius": {"id": 9, "title": "Old", "artist": "A"}}
        }
        (tmp_path / "alignment_debug" / f"{YT_STEM}.json").write_text(
            json.dumps(bundle), encoding="utf-8"
        )
        lrc = tmp_path / "lyrics" / f"{YT_STEM}.lrc"
        lrc.parent.mkdir()
        lrc.write_text("[lrclib_id:1]\n[00:01.00]old song\n", encoding="utf-8")
        temp_dir = tmp_path / "tmp"
        temp_dir.mkdir()

        hit = GeniusHit(id=10, title="New", artist="B")
        genius = SimpleNamespace(_token="tok", search=lambda query, limit=8: [hit])
        monkeypatch.setattr(regen, "_make_genius", lambda: genius)
        monkeypatch.setattr(regen, "get_temp_directory", lambda: str(temp_dir))
        monkeypatch.setattr(library_regen, "download_manual_en_subs", lambda url, dest, stem: None)
        monkeypatch.setattr(library_regen, "write_choice", MagicMock())
        answers = iter(["", "1"])  # the default query, then the first hit
        monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

        seen = {}

        class FakeOrchestrator:
            def __init__(self, *args):
                pass

            def run_one(self, song, lyrics_path):
                seen["lrc_exists"] = lrc.exists()
                return SimpleNamespace(artifacts={"lyric_method": "genius+joint"})

        monkeypatch.setattr(regen, "PipelineOrchestrator", FakeOrchestrator)
        monkeypatch.setattr(regen, "StemWorker", MagicMock())
        monkeypatch.setattr(regen, "WhisperWorker", MagicMock())
        monkeypatch.setattr(regen, "build_stages", lambda *args, **kwargs: [])
        monkeypatch.setenv("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        monkeypatch.setattr(
            sys, "argv", ["regen", str(tmp_path), "--song", "dQw4w9WgXcQ", "--reset", "--yes"]
        )

        assert regen.main() == 0

        assert seen == {"lrc_exists": False}


# ---------------------------------------------------------------------------
# A transcribe run drops the old bundle
# ---------------------------------------------------------------------------


class TestRunJobsArmsFirstDownloadsOnly:
    """A job from ``add_songs`` is a first download and arms the LRCLIB check; a scanned job
    never does."""

    def _armed(self, tmp_path, monkeypatch, *, first_download):
        _touch_video(tmp_path, "Song")
        job = _job(tmp_path, "Song", None)
        job.plan = regen.Plan(kind="transcribe")
        job.first_download = first_download
        build = MagicMock(return_value=[])
        monkeypatch.setattr(regen, "build_stages", build)
        monkeypatch.setattr(regen, "StemWorker", MagicMock())
        monkeypatch.setattr(regen, "WhisperWorker", MagicMock())
        monkeypatch.setattr(regen, "prepare_lyrics", lambda *args: (None, None))

        class FakeOrchestrator:
            def __init__(self, *args):
                pass

            def run_one(self, song, lyrics_path):
                return SimpleNamespace(artifacts={"lyric_method": "genius+joint"})

        monkeypatch.setattr(regen, "PipelineOrchestrator", FakeOrchestrator)
        config = PipelineConfig()
        config.intermediate_dir = str(tmp_path)

        assert regen.run_jobs([job], config, MagicMock()) == (1, 0, 0)

        return build.call_args.kwargs["auto_lrc_timing"]

    def test_a_first_download_arms_the_stage(self, tmp_path, monkeypatch):
        assert self._armed(tmp_path, monkeypatch, first_download=True) is True

    def test_a_scanned_job_does_not(self, tmp_path, monkeypatch):
        assert self._armed(tmp_path, monkeypatch, first_download=False) is False


class TestRunJobsFinishesEachSong:
    """A transcribe run writes no bundle, so the old one must go once the run
    succeeds (``finish_regen_job``, told by the run's ``lyric_method``); a failed
    run keeps it."""

    def _run(
        self, tmp_path, monkeypatch, run_error, lyric_method="transcribe", plan=None, prepare=None
    ):
        _touch_video(tmp_path, "Song")
        (tmp_path / "alignment_debug").mkdir()
        bundle = tmp_path / "alignment_debug" / "Song.json"
        bundle.write_text("{}", encoding="utf-8")
        job = _job(tmp_path, "Song", {})
        job.plan = plan or regen.Plan(kind="transcribe")

        class FakeOrchestrator:
            def __init__(self, *args):
                pass

            def run_one(self, song, lyrics_path):
                if run_error:
                    raise run_error
                return SimpleNamespace(artifacts={"lyric_method": lyric_method})

        monkeypatch.setattr(regen, "PipelineOrchestrator", FakeOrchestrator)
        monkeypatch.setattr(regen, "StemWorker", MagicMock())
        monkeypatch.setattr(regen, "WhisperWorker", MagicMock())
        monkeypatch.setattr(regen, "build_stages", lambda *args, **kwargs: [])
        monkeypatch.setattr(regen, "prepare_lyrics", prepare or (lambda *args: (None, None)))
        config = PipelineConfig()
        config.intermediate_dir = str(tmp_path)

        counts = regen.run_jobs([job], config, MagicMock())
        return counts, bundle

    def test_a_successful_transcribe_removes_the_old_bundle(self, tmp_path, monkeypatch):
        counts, bundle = self._run(tmp_path, monkeypatch, None)

        assert counts == (1, 0, 0)
        assert not bundle.exists()

    def test_a_genius_pick_that_ended_up_transcribing_removes_it_too(self, tmp_path, monkeypatch):
        plan = regen.Plan(kind="sidecar", genius_id=9)

        counts, bundle = self._run(tmp_path, monkeypatch, None, "transcribe", plan)

        assert counts == (1, 0, 0)
        assert not bundle.exists()

    def test_a_run_with_lyrics_keeps_the_old_bundle(self, tmp_path, monkeypatch):
        plan = regen.Plan(kind="sidecar", genius_id=9)

        counts, bundle = self._run(tmp_path, monkeypatch, None, "genius+joint", plan)

        assert counts == (1, 0, 0)
        assert bundle.exists()

    def test_a_failed_song_gets_its_lrc_back(self, tmp_path, monkeypatch):
        lrc = tmp_path / "lyrics" / "Song.lrc"
        lrc.parent.mkdir()
        lrc.write_text("[lrclib_id:1]\n[00:01.00]old\n", encoding="utf-8")

        def drop_for_the_new_song(job, genius, lyrics_dir, config):
            lrc.unlink()
            return None, None

        counts, _ = self._run(
            tmp_path, monkeypatch, RuntimeError("boom"), prepare=drop_for_the_new_song
        )

        assert counts == (0, 1, 0)
        assert lrc.read_text(encoding="utf-8") == "[lrclib_id:1]\n[00:01.00]old\n"

    def test_a_successful_song_keeps_its_new_lrc(self, tmp_path, monkeypatch):
        lrc = tmp_path / "lyrics" / "Song.lrc"
        lrc.parent.mkdir()
        lrc.write_text("[lrclib_id:1]\n", encoding="utf-8")

        def rewrite_for_the_new_pick(job, genius, lyrics_dir, config):
            lrc.write_text("[lrclib_id:2]\n", encoding="utf-8")
            return None, None

        counts, _ = self._run(tmp_path, monkeypatch, None, prepare=rewrite_for_the_new_pick)

        assert counts == (1, 0, 0)
        assert lrc.read_text(encoding="utf-8") == "[lrclib_id:2]\n"

    def test_a_failed_transcribe_keeps_the_old_bundle(self, tmp_path, monkeypatch):
        counts, bundle = self._run(tmp_path, monkeypatch, RuntimeError("boom"))

        assert counts == (0, 1, 0)
        assert bundle.exists()

    def test_a_song_that_fails_before_its_run_fails_alone(self, tmp_path, monkeypatch):
        """Preparing the lyrics is part of the song's try: the batch goes on, files put back."""
        sheet = tmp_path / "lyrics" / "Song.custom.txt"
        sheet.parent.mkdir()
        sheet.write_bytes("Café\n".encode("cp1252"))  # snapshotting it must not raise

        def drop_then_fail(job, genius, lyrics_dir, config):
            sheet.unlink()
            raise OSError("disk full")

        counts, _ = self._run(tmp_path, monkeypatch, None, prepare=drop_then_fail)

        assert counts == (0, 1, 0)
        assert sheet.read_bytes() == "Café\n".encode("cp1252")


# ---------------------------------------------------------------------------
# --lrclib-auto: the LRCLIB check of Genius songs on joint
# ---------------------------------------------------------------------------

GENIUS = {"id": 9, "title": "Some Song", "artist": "Some Artist"}
OTHER_GENIUS = {"id": 10, "title": "Other Song", "artist": "Other Artist"}
QUERY = "Some Song Some Artist"
OLD_LRC = "[ti:Old]\n[lrclib_id:1]\n[00:01.00] old\n"


def _record(record_id: int = 42, synced: str | None = None) -> dict:
    """A synced record of exactly the lines ``heard_words`` sings, so it passes the bar."""
    return {
        "id": record_id,
        "trackName": "Some Song",
        "artistName": "Some Artist",
        "albumName": "Album",
        "duration": CLIP_S,
        "syncedLyrics": synced if synced is not None else lrc_slice(),
    }


def _genius_song(folder: Path, stem: str = YT_STEM, genius: dict = GENIUS, **bundle) -> Path:
    """A video with the bundle of a song timed from Genius, and an old ``.lrc`` beside it."""
    video = _touch_video(folder, stem)
    fields = {
        "media_duration_s": CLIP_S,
        "transcribe_words": heard_words(),
        "lyrics": {"origin": "genius", "genius": genius, "lines": ["one", "two"]},
        **bundle,
    }
    path = library_regen.bundle_path(folder, stem)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(fields), encoding="utf-8")
    lrc = lrclib.lrc_path(video)
    lrc.parent.mkdir(exist_ok=True)
    lrc.write_text(OLD_LRC, encoding="utf-8")
    return video


def _planned(folder: Path, *videos: Path) -> list["regen.SongJob"]:
    """The jobs ``main()`` hands the mode: every video (or the named ones) with its plan."""
    jobs = library_regen.scan_folder(folder, True, songs=list(videos) or None)
    for job in jobs:
        job.plan = library_regen.resolve_plan(job, reset=False)
    return jobs


@pytest.fixture
def search():
    """Patch the LRCLIB search; the real check and bar run on its records."""
    with patch.object(lrclib, "search_query", return_value=[_record()]) as mock:
        yield mock


class TestLrclibAutoPlan:
    def test_a_passing_record_gives_the_plan_a_repair_to_it_would(self, tmp_path, search):
        video = _genius_song(tmp_path)

        (job,), _ = regen.check_lrclib_auto(_planned(tmp_path), named=False)

        plan = job.plan
        assert plan.kind == "seed"
        assert plan.lyrics_path == lrc_auto_timing.sheet_path(video)
        assert plan.seed == {"lyrics_origin": library_regen.LRC_AUTO_ORIGIN}
        assert plan.custom_text.startswith("1\n00:00:10,000 --> 00:00:15,000\n")
        assert plan.lrclib_record == _record()
        assert "42" in plan.label and "mistimed 0" in plan.label
        search.assert_called_once_with(QUERY)

    def test_no_record_passing_the_bar_stays_on_joint_and_counts_why(self, tmp_path, search):
        _genius_song(tmp_path)
        search.return_value = [_record(synced=lrc_slice(lines=range(3)))]

        (job,), _ = regen.check_lrclib_auto(_planned(tmp_path), named=False)

        assert job.plan.kind == "skip"
        assert job.plan.label == "stays on joint: no record passed (1 records; no_fit 1)"
        assert not (tmp_path / "lyrics" / f"{YT_STEM}.lrclib-auto.srt").exists()

    def test_no_synced_record_stays_on_joint(self, tmp_path, search):
        _genius_song(tmp_path)
        search.return_value = [{**_record(), "syncedLyrics": None}]

        (job,), _ = regen.check_lrclib_auto(_planned(tmp_path), named=False)

        assert job.plan.kind == "skip"
        assert job.plan.label == "stays on joint: no synced LRCLIB record"

    def test_an_unreachable_lrclib_stays_on_joint_and_says_to_rerun(self, tmp_path, search):
        _genius_song(tmp_path)
        search.side_effect = lrclib.LrclibUnavailable("LRCLIB search failed")

        (job,), unchecked = regen.check_lrclib_auto(_planned(tmp_path), named=False)

        assert job.plan.kind == "skip"
        assert job.plan.label == "stays on joint: LRCLIB could not be reached; rerun later"
        assert unchecked == 1
        assert lrclib.lrc_path(job.song_path).read_text(encoding="utf-8") == OLD_LRC

    def test_a_failed_check_stays_on_joint_and_points_at_the_log(self, tmp_path, search):
        _genius_song(tmp_path, genius={"title": "Some Song"})

        (job,), unchecked = regen.check_lrclib_auto(_planned(tmp_path), named=False)

        assert job.plan.kind == "skip"
        assert job.plan.label == "stays on joint: LRCLIB check failed (error); see the log"
        assert unchecked == 1
        search.assert_not_called()

    def test_a_song_without_a_stored_length_is_probed_once(self, tmp_path, search, monkeypatch):
        _genius_song(tmp_path, media_duration_s=None)
        probe = MagicMock(return_value=CLIP_S)
        monkeypatch.setattr(library_regen, "probe_duration", probe)

        (job,), _ = regen.check_lrclib_auto(_planned(tmp_path), named=False)

        assert job.plan.kind == "seed"
        probe.assert_called_once()

    def test_the_progress_goes_to_stderr_and_the_report_stays_clean(self, tmp_path, search, capsys):
        _genius_song(tmp_path)

        regen.check_lrclib_auto(_planned(tmp_path), named=False)

        captured = capsys.readouterr()
        assert captured.err == f"[1/1] {YT_STEM}.mp4\n"
        assert captured.out == ""


class TestLrclibAutoEligibility:
    """A song the check does not apply to is dropped before any search."""

    def _dropped(self, tmp_path, search, capsys, video: Path) -> str:
        assert regen.check_lrclib_auto(_planned(tmp_path, video), named=True) == ([], 0)
        search.assert_not_called()
        return capsys.readouterr().out

    def test_a_caption_song(self, tmp_path, search, capsys):
        video = _genius_song(tmp_path, lyrics={"origin": "srt"})
        _make_srt(tmp_path, YT_STEM)

        out = self._dropped(tmp_path, search, capsys, video)

        assert f"{YT_STEM}.mp4: not checked, it is not a Genius song on joint" in out

    def test_a_song_with_a_custom_sheet(self, tmp_path, search, capsys):
        video = _genius_song(tmp_path)
        (tmp_path / "lyrics" / f"{YT_STEM}.custom.txt").write_text("one\ntwo\n", encoding="utf-8")

        out = self._dropped(tmp_path, search, capsys, video)

        assert "it is not a Genius song on joint (custom sheet)" in out

    def test_a_song_already_timed_from_a_record(self, tmp_path, search, capsys):
        video = _genius_song(tmp_path)
        (tmp_path / "lyrics" / f"{YT_STEM}.lrclib-auto.srt").write_text("x", encoding="utf-8")

        out = self._dropped(tmp_path, search, capsys, video)

        assert "(LRCLIB timing (auto))" in out

    def test_a_skip_marker(self, tmp_path, search, capsys):
        video = _genius_song(tmp_path)
        lrclib.write_skip_marker(lrclib.lrc_path(video))

        out = self._dropped(tmp_path, search, capsys, video)

        assert "its .lrc is a no-match marker" in out

    def test_an_unreadable_lrc(self, tmp_path, search, capsys):
        video = _genius_song(tmp_path)
        lrclib.lrc_path(video).write_bytes("[ti:Café]\n".encode("cp1252"))

        out = self._dropped(tmp_path, search, capsys, video)

        assert "its .lrc can't be read" in out

    def test_a_bundle_without_transcribe_words(self, tmp_path, search, capsys):
        video = _genius_song(tmp_path, transcribe_words=[])

        out = self._dropped(tmp_path, search, capsys, video)

        assert "its bundle holds no transcribe words" in out

    def test_a_song_whose_length_is_unknown(self, tmp_path, search, capsys, monkeypatch):
        video = _genius_song(tmp_path, media_duration_s=None)
        monkeypatch.setattr(regen, "media_duration", lambda job: None)

        out = self._dropped(tmp_path, search, capsys, video)

        assert "its length is unknown" in out

    def test_a_song_without_a_bundle(self, tmp_path, search, capsys):
        video = _touch_video(tmp_path, YT_STEM)

        out = self._dropped(tmp_path, search, capsys, video)

        assert "it is not a Genius song on joint" in out

    def test_without_song_a_dropped_song_is_silent(self, tmp_path, search, capsys):
        _genius_song(tmp_path, lyrics={"origin": "srt"})

        assert regen.check_lrclib_auto(_planned(tmp_path), named=False) == ([], 0)

        assert capsys.readouterr().out == ""


class TestMainLrclibAuto:
    """``main()`` with the flag: the report, the dry run, the backup and the hand-off."""

    PICKED = "Some Song---aaaaaaaaaaa"
    STAYS = "Other Song---bbbbbbbbbbb"

    def _library(self, tmp_path):
        _genius_song(tmp_path, self.PICKED)
        _genius_song(tmp_path, self.STAYS, OTHER_GENIUS)

    def _main(self, monkeypatch, tmp_path, *args):
        monkeypatch.setenv("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        monkeypatch.setattr(sys, "argv", ["regen", str(tmp_path), "--lrclib-auto", *args])
        run = MagicMock(return_value=0)
        monkeypatch.setattr(regen, "resolve_and_run", run)
        return regen.main(), run

    @pytest.fixture(autouse=True)
    def only_the_first_song_has_a_record(self, search):
        search.side_effect = lambda query: [_record()] if query == QUERY else []

    def test_it_cannot_be_combined_with_reset(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["regen", str(tmp_path), "--lrclib-auto", "--reset"])

        with pytest.raises(SystemExit) as stop:
            regen.main()

        assert stop.value.code == 2
        assert "--lrclib-auto can't be combined with --reset" in capsys.readouterr().err

    def test_a_dry_run_searches_lists_the_songs_and_changes_nothing(
        self, tmp_path, monkeypatch, capsys, search
    ):
        self._library(tmp_path)
        before = sorted(p.name for p in tmp_path.rglob("*"))

        code, run = self._main(monkeypatch, tmp_path, "--dry-run")

        out = capsys.readouterr().out
        assert code == 0
        assert search.call_count == 2
        assert "Selection: Genius songs on joint, checked against LRCLIB\n" in out
        assert "Songs checked: 2; to re-time: 1; could not check: 0" in out
        assert "LRCLIB (auto) 42: Some Song · Some Artist" in out
        assert "stays on joint: no synced LRCLIB record" in out
        run.assert_not_called()
        assert sorted(p.name for p in tmp_path.rglob("*")) == before

    def test_a_real_run_backs_up_the_picked_songs_only_and_hands_over_every_checked_song(
        self, tmp_path, monkeypatch, capsys
    ):
        self._library(tmp_path)

        code, run = self._main(monkeypatch, tmp_path, "--yes")

        assert code == 0
        (backup,) = tmp_path.glob("regen_backups/*")
        assert (backup / "alignment_debug" / f"{self.PICKED}.json").is_file()
        assert (backup / "lyrics" / f"{self.PICKED}.lrc").is_file()
        assert not (backup / "alignment_debug" / f"{self.STAYS}.json").exists()
        assert not (backup / "lyrics" / f"{self.STAYS}.lrc").exists()
        (jobs,) = run.call_args.args
        assert {j.song_path.stem: j.plan.kind for j in jobs} == {
            self.PICKED: "seed",
            self.STAYS: "skip",
        }
        assert "for the re-timed songs" in capsys.readouterr().out

    def test_the_confirmation_counts_the_picked_songs_and_no_answers_abort(
        self, tmp_path, monkeypatch, capsys
    ):
        self._library(tmp_path)
        prompts = []
        monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "n")

        code, run = self._main(monkeypatch, tmp_path)

        assert code == 0
        assert prompts == ["Proceed with 1 song(s)? [y/N] "]
        assert "Aborted." in capsys.readouterr().out
        run.assert_not_called()
        assert not (tmp_path / "regen_backups").exists()

    def test_no_pick_means_nothing_to_re_time_and_no_backup(
        self, tmp_path, monkeypatch, capsys, search
    ):
        self._library(tmp_path)
        search.side_effect = None
        search.return_value = []

        code, run = self._main(monkeypatch, tmp_path, "--yes")

        assert code == 0
        assert "Nothing to re-time." in capsys.readouterr().out
        run.assert_not_called()
        assert not (tmp_path / "regen_backups").exists()

    def test_an_lrclib_outage_is_counted_and_exits_1(self, tmp_path, monkeypatch, capsys, search):
        self._library(tmp_path)
        search.side_effect = lrclib.LrclibUnavailable("LRCLIB search failed")

        code, run = self._main(monkeypatch, tmp_path, "--dry-run")

        out = capsys.readouterr().out
        assert code == 1
        assert "Songs checked: 2; to re-time: 0; could not check: 2" in out
        assert "Nothing to re-time." in out
        run.assert_not_called()

    def test_closed_input_at_the_prompt_aborts(self, tmp_path, monkeypatch, capsys):
        self._library(tmp_path)

        def closed(prompt):
            raise EOFError

        monkeypatch.setattr("builtins.input", closed)

        code, run = self._main(monkeypatch, tmp_path)

        assert code == 0
        assert "Aborted." in capsys.readouterr().out
        run.assert_not_called()

    def test_song_narrows_the_check_and_a_song_named_twice_is_checked_once(
        self, tmp_path, monkeypatch, capsys, search
    ):
        self._library(tmp_path)

        code, _ = self._main(
            monkeypatch, tmp_path, "--dry-run", "--song", "aaaaaaaaaaa", "--song", self.PICKED
        )

        out = capsys.readouterr().out
        assert code == 0
        search.assert_called_once_with(QUERY)
        assert "Selection: Genius songs on joint, checked against LRCLIB (selected songs)" in out
        assert self.STAYS not in out

    def test_a_song_named_that_the_check_drops_says_why(
        self, tmp_path, monkeypatch, capsys, search
    ):
        _genius_song(tmp_path, self.PICKED, lyrics={"origin": "srt"})
        _make_srt(tmp_path, self.PICKED)

        code, _ = self._main(monkeypatch, tmp_path, "--dry-run", "--song", self.PICKED)

        assert code == 0
        out = capsys.readouterr().out
        assert f"{self.PICKED}.mp4: not checked, it is not a Genius song on joint" in out
        assert "Nothing to re-time." in out
        search.assert_not_called()

    def test_a_cjk_song_name_goes_through_the_report(self, tmp_path, monkeypatch, capsys, search):
        stem = "歌手 - 歌曲---dQw4w9WgXcQ"
        _genius_song(tmp_path, stem)

        code, _ = self._main(monkeypatch, tmp_path, "--dry-run")

        assert code == 0
        assert f"{stem}.mp4" in capsys.readouterr().out


class TestLrclibAutoRun:
    """The picked plan through the real ``prepare_lyrics`` and ``run_jobs``."""

    def _job(self, tmp_path, search):
        _genius_song(tmp_path)
        (job,), _ = regen.check_lrclib_auto(_planned(tmp_path), named=False)
        return job

    def test_the_run_writes_the_sheet_and_the_record_and_keeps_the_genius_song(
        self, tmp_path, search
    ):
        job = self._job(tmp_path, search)
        lyrics_dir = tmp_path / "scratch"
        lyrics_dir.mkdir()

        lyrics_path, stage = regen.prepare_lyrics(job, MagicMock(), lyrics_dir, PipelineConfig())

        sheet = tmp_path / "lyrics" / f"{YT_STEM}.lrclib-auto.srt"
        assert lyrics_path == sheet
        assert sheet.read_text(encoding="utf-8") == job.plan.custom_text
        lrc = lrclib.lrc_path(job.song_path).read_text(encoding="utf-8")
        assert "[lrclib_id:42]" in lrc and "[lrclib_id:1]" not in lrc
        ctx = SimpleNamespace(artifacts={})
        stage.run(ctx)
        assert ctx.artifacts["lyrics_origin"] == library_regen.LRC_AUTO_ORIGIN
        assert ctx.artifacts["genius"] == GENIUS

    def test_a_song_that_fails_gets_its_old_lrc_back_and_no_auto_sheet(
        self, tmp_path, monkeypatch, search
    ):
        job = self._job(tmp_path, search)
        old = lrclib.lrc_path(job.song_path).read_bytes()

        started_from_the_sheet = []

        class FailingOrchestrator:
            def __init__(self, *args):
                pass

            def run_one(self, song, lyrics_path):
                started_from_the_sheet.append(lyrics_path.is_file())
                raise RuntimeError("boom")

        monkeypatch.setattr(regen, "PipelineOrchestrator", FailingOrchestrator)
        monkeypatch.setattr(regen, "StemWorker", MagicMock())
        monkeypatch.setattr(regen, "WhisperWorker", MagicMock())
        monkeypatch.setattr(regen, "build_stages", lambda *args, **kwargs: [])
        config = PipelineConfig()
        config.intermediate_dir = str(tmp_path)

        counts = regen.run_jobs([job], config, MagicMock())

        assert counts == (0, 1, 0)
        assert started_from_the_sheet == [True]
        assert lrclib.lrc_path(job.song_path).read_bytes() == old
        assert not (tmp_path / "lyrics" / f"{YT_STEM}.lrclib-auto.srt").exists()
