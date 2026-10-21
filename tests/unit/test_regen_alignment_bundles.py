"""Unit tests for scripts/regen_alignment_bundles.py -- the CLI flow.

The planning, caption gate, backup/wipe and lyric-prep core lives in
pikaraoke/lib/library_regen.py (test_library_regen.py).  Here: the report, the
``--song --reset`` wiring of ``main()``, the shared ``resolve_and_run`` setup and
the LRCLIB backfill batch.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from pikaraoke.lib import library_regen, lrclib
from pikaraoke.pipeline.config import PipelineConfig

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
        (backup,) = tmp_path.glob("regen_backup_*")
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

        hit = SimpleNamespace(id=10, title="New", artist="B")
        genius = SimpleNamespace(_token="tok", search=lambda query, limit: [hit])
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
        monkeypatch.setattr(regen, "build_stages", lambda *args: [])
        monkeypatch.setenv("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        monkeypatch.setattr(
            sys, "argv", ["regen", str(tmp_path), "--song", "dQw4w9WgXcQ", "--reset", "--yes"]
        )

        assert regen.main() == 0

        assert seen == {"lrc_exists": False}


# ---------------------------------------------------------------------------
# A transcribe run drops the old bundle
# ---------------------------------------------------------------------------


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
        monkeypatch.setattr(regen, "build_stages", lambda *args: [])
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
