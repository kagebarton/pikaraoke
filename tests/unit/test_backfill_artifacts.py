"""Unit tests for scripts/backfill_artifacts.py — selection scoping and lyric resolution.

``scan_folder``'s selection behavior, how a lyric choice resolves to a file plus
the origin the bundle records, and that ``run_jobs`` hands that origin to the
pipeline. Driving the pipeline itself is covered by the stage tests.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pikaraoke.lib.genius import GeniusSong, GeniusUnavailable
from pikaraoke.lib.library_regen import SeedArtifactsStage
from pikaraoke.lib.srt_provenance import mark_generated
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.load_vocal import LoadVocalFromM4aStage

# scripts/ is not a package — load the module straight from its file. It must
# be registered in sys.modules before exec so @dataclass can resolve its own
# module by __module__.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backfill_artifacts.py"
_spec = importlib.util.spec_from_file_location("backfill_artifacts", _SCRIPT)
backfill = importlib.util.module_from_spec(_spec)
sys.modules["backfill_artifacts"] = backfill
_spec.loader.exec_module(backfill)


def _touch_video(folder: Path, stem: str) -> Path:
    path = folder / f"{stem}.mp4"
    path.touch()
    return path


def _complete_song(folder: Path, stem: str) -> Path:
    """A song with every artifact present -- nothing missing."""
    path = _touch_video(folder, stem)
    for sub in ("vocal", "nonvocal", "karaoke", "subtitles"):
        (folder / sub).mkdir(exist_ok=True)
    (folder / "vocal" / f"{stem}---vocal.m4a").write_text("v", encoding="utf-8")
    (folder / "nonvocal" / f"{stem}---nonvocal.m4a").write_text("n", encoding="utf-8")
    (folder / "karaoke" / f"{stem}.ass").write_text("a", encoding="utf-8")
    (folder / "subtitles" / f"{stem}.srt").write_text("s", encoding="utf-8")
    return path


class TestScanFolderSelection:
    def test_selection_scopes_to_named_videos(self, tmp_path):
        a = _touch_video(tmp_path, "a")
        _touch_video(tmp_path, "b")  # unselected, also missing everything

        jobs = backfill.scan_folder(tmp_path, songs=[a])

        assert [j.song_path for j in jobs] == [a]

    def test_selected_song_with_nothing_missing_is_not_queued(self, tmp_path):
        complete = _complete_song(tmp_path, "complete")

        jobs = backfill.scan_folder(tmp_path, songs=[complete])

        assert jobs == []


def _job(song: Path, choice: tuple) -> "backfill.SongJob":
    return backfill.SongJob(song_path=song, missing={backfill.KARAOKE}, choice=choice)


def _write_caption(folder: Path, stem: str) -> Path:
    """An uploader caption: ``subtitles/<stem>.srt`` with no generated marker."""
    (folder / "subtitles").mkdir(exist_ok=True)
    path = folder / "subtitles" / f"{stem}.srt"
    path.write_text("1\n00:00:01,000 --> 00:00:02,000\ntext\n", encoding="utf-8")
    return path


class _FakeGenius:
    """Stands in for GeniusClient: serves one canned song, or is unavailable."""

    def __init__(self, song: GeniusSong | None = None) -> None:
        self._song = song

    def fetch_song(self, genius_id: int) -> GeniusSong:
        if self._song is None:
            raise GeniusUnavailable("no token")
        return self._song


class TestResolveLyrics:
    def test_srt_choice_uses_the_caption_and_records_srt(self, tmp_path):
        song = _touch_video(tmp_path, "song")
        caption = _write_caption(tmp_path, "song")

        path, seed = backfill.resolve_lyrics(_job(song, ("srt",)), None, tmp_path)

        assert path == caption
        assert seed == {"lyrics_origin": "srt"}

    def test_srt_choice_skips_a_generated_srt(self, tmp_path):
        song = _touch_video(tmp_path, "song")
        mark_generated(_write_caption(tmp_path, "song"))

        assert backfill.resolve_lyrics(_job(song, ("srt",)), None, tmp_path) == (None, {})

    def test_genius_choice_records_the_song_identity(self, tmp_path):
        song = _touch_video(tmp_path, "song")
        genius = _FakeGenius(GeniusSong(text="first\nsecond", title="Title", artist="Artist"))

        path, seed = backfill.resolve_lyrics(_job(song, ("genius", 42)), genius, tmp_path)

        assert path.read_text(encoding="utf-8") == "first\nsecond"
        assert seed == {
            "lyrics_origin": "genius",
            "genius": {"id": 42, "title": "Title", "artist": "Artist"},
        }

    def test_unavailable_genius_transcribes_and_claims_no_origin(self, tmp_path):
        song = _touch_video(tmp_path, "song")

        resolved = backfill.resolve_lyrics(_job(song, ("genius", 42)), _FakeGenius(), tmp_path)

        assert resolved == (None, {})

    def test_bundle_choice_keeps_the_origin_the_bundle_recorded(self, tmp_path):
        song = _touch_video(tmp_path, "song")
        genius_ref = {"id": 7, "title": "T", "artist": "A"}
        bundle = tmp_path / "bundle.json"
        lyrics = {"align_lines": ["a", "b"], "origin": "genius", "genius": genius_ref}
        bundle.write_text(json.dumps({"lyrics": lyrics}), encoding="utf-8")

        path, seed = backfill.resolve_lyrics(_job(song, ("bundle", bundle)), None, tmp_path)

        assert path.read_text(encoding="utf-8") == "a\n\nb"
        assert seed == {"lyrics_origin": "genius", "genius": genius_ref}

    def test_bundle_without_a_recorded_origin_seeds_nothing(self, tmp_path):
        song = _touch_video(tmp_path, "song")
        bundle = tmp_path / "bundle.json"
        bundle.write_text(json.dumps({"lyrics": {"align_lines": ["a"]}}), encoding="utf-8")

        path, seed = backfill.resolve_lyrics(_job(song, ("bundle", bundle)), None, tmp_path)

        assert path is not None
        assert seed == {}

    def test_raw_choice_transcribes(self, tmp_path):
        song = _touch_video(tmp_path, "song")

        assert backfill.resolve_lyrics(_job(song, ("raw",)), None, tmp_path) == (None, {})


class _FakeWorker:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class _RecordingOrchestrator:
    """Records what ``run_jobs`` hands the orchestrator instead of running a pipeline."""

    runs: list = []

    def __init__(self, stages, *args) -> None:
        self.stages = stages

    def run_one(self, song_path, lyrics_path) -> None:
        type(self).runs.append((self.stages, lyrics_path))


@pytest.fixture
def pipeline_runs(monkeypatch):
    """The ``(stages, lyrics_path)`` of each run, with the workers and orchestrator faked."""
    _RecordingOrchestrator.runs = []
    monkeypatch.setattr(backfill, "StemWorker", _FakeWorker)
    monkeypatch.setattr(backfill, "WhisperWorker", _FakeWorker)
    monkeypatch.setattr(backfill, "PipelineOrchestrator", _RecordingOrchestrator)
    return _RecordingOrchestrator.runs


def _song_with_stems(folder: Path, stem: str) -> Path:
    """A song whose stems exist, so only karaoke (and maybe subtitles) is missing."""
    song = _touch_video(folder, stem)
    for sub in ("vocal", "nonvocal"):
        (folder / sub).mkdir(exist_ok=True)
        (folder / sub / f"{stem}---{sub}.m4a").write_text("x", encoding="utf-8")
    return song


class TestRunJobsSeedsTheOrigin:
    def test_caption_run_seeds_srt_ahead_of_the_other_stages(self, tmp_path, pipeline_runs):
        _song_with_stems(tmp_path, "song")
        caption = _write_caption(tmp_path, "song")
        jobs = backfill.scan_folder(tmp_path)
        jobs[0].choice = ("srt",)
        config = PipelineConfig()
        config.intermediate_dir = str(tmp_path)

        counts = backfill.run_jobs(jobs, config, genius=None)

        stages, lyrics_path = pipeline_runs[0]
        ctx = SimpleNamespace(artifacts={})
        stages[0].run(ctx)
        assert counts == (1, 0)
        assert lyrics_path == caption
        assert isinstance(stages[0], SeedArtifactsStage)
        assert ctx.artifacts == {"lyrics_origin": "srt"}
        assert isinstance(stages[1], LoadVocalFromM4aStage)

    def test_transcribed_run_seeds_nothing(self, tmp_path, pipeline_runs):
        _song_with_stems(tmp_path, "song")
        jobs = backfill.scan_folder(tmp_path)
        jobs[0].choice = ("raw",)
        config = PipelineConfig()
        config.intermediate_dir = str(tmp_path)

        backfill.run_jobs(jobs, config, genius=None)

        stages, lyrics_path = pipeline_runs[0]
        assert lyrics_path is None
        assert not any(isinstance(s, SeedArtifactsStage) for s in stages)
