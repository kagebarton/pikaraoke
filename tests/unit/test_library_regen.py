"""Unit tests for pikaraoke/lib/library_regen.py -- selection + planning.

Scan/staleness, lyric-plan resolution, the caption gate and fetch, the scoped
backup and wipe, and the lyric prep for a run.  Driving the pipeline is covered
by the stage tests; the CLI flow is in test_regen_alignment_bundles.py.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pikaraoke.lib import library_regen as lr
from pikaraoke.lib.alignment_capture import SCHEMA_VERSION
from pikaraoke.lib.youtube_dl import ASR_JSON3_SUFFIX
from pikaraoke.pipeline.config import PipelineConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_bundle(folder: Path, stem: str, bundle: dict) -> None:
    debug = folder / "alignment_debug"
    debug.mkdir(exist_ok=True)
    (debug / f"{stem}.json").write_text(json.dumps(bundle), encoding="utf-8")


def _touch_video(folder: Path, stem: str) -> Path:
    path = folder / f"{stem}.mp4"
    path.touch()
    return path


def _job(folder: Path, stem: str, bundle: dict | None) -> "lr.SongJob":
    return lr.SongJob(song_path=folder / f"{stem}.mp4", bundle=bundle, stale_reason="all")


def _make_srt(folder: Path, stem: str, n_words: int = 1) -> Path:
    subs = folder / "subtitles"
    subs.mkdir(exist_ok=True)
    words = " ".join(["la"] * n_words)
    srt = subs / f"{stem}.srt"
    srt.write_text(f"1\n00:00:01,000 --> 00:00:04,000\n{words}\n", encoding="utf-8")
    return srt


def _write_sheet(
    folder: Path,
    stem: str,
    text: str = "la la la\nsecond line\n",
    suffix: str = lr.CUSTOM_TEXT_SUFFIX,
) -> Path:
    sheet = folder / "lyrics" / f"{stem}{suffix}"
    sheet.parent.mkdir(exist_ok=True)
    sheet.write_text(text, encoding="utf-8")
    return sheet


MOVIE_SRT = "1\n00:00:01,000 --> 00:00:03,000\nla la la\n"


def _write_movie_sheet(folder: Path, stem: str, text: str = MOVIE_SRT) -> Path:
    return _write_sheet(folder, stem, text, lr.CUSTOM_SRT_SUFFIX)


def _is_srt_plan(plan) -> bool:
    """True for a seed plan that feeds a local SRT as the lyric source."""
    return plan.kind == "seed" and plan.seed.get("lyrics_origin") == "srt"


def _scoped_library(folder: Path) -> None:
    """A library for the ``--song`` scoping tests: ``Song``, ``Song.live``, ``Other``.

    ``Song.live`` is a real library video too, so it must win ownership of its
    own files over the shorter ``Song`` stem.
    """
    for stem in ("Song", "Song.live", "Other"):
        _touch_video(folder, stem)

    subs = folder / "subtitles"
    subs.mkdir()
    (subs / "Song.srt").write_text("song", encoding="utf-8")
    (subs / "Song.srt.generated").write_text("marker", encoding="utf-8")
    (subs / f"Song{ASR_JSON3_SUFFIX}").write_text("{}", encoding="utf-8")
    (subs / "Song.live.srt").write_text("live", encoding="utf-8")
    (subs / "Other.srt").write_text("other", encoding="utf-8")

    karaoke = folder / "karaoke"
    karaoke.mkdir()
    (karaoke / "Song.ass").write_text("song ass", encoding="utf-8")
    (karaoke / "Other.ass").write_text("other ass", encoding="utf-8")

    lyrics = folder / "lyrics"
    lyrics.mkdir()
    (lyrics / "Song.txt").write_text("stale reuse", encoding="utf-8")
    (lyrics / "Song.lrc").write_text("[00:01.00]hi\n", encoding="utf-8")
    (lyrics / "Other.txt").write_text("other reuse", encoding="utf-8")

    debug = folder / "alignment_debug"
    debug.mkdir()
    (debug / "Song.json").write_text("{}", encoding="utf-8")
    (debug / "Other.json").write_text("{}", encoding="utf-8")


# A stem with a real 11-char YouTube id, so extract_youtube_id picks it up.
YT_STEM = "Song---dQw4w9WgXcQ"


# ---------------------------------------------------------------------------
# scan_folder — staleness selection
# ---------------------------------------------------------------------------


class TestScanFolder:
    def _setup(self, folder: Path):
        _touch_video(folder, "current")
        _touch_video(folder, "stale")
        _touch_video(folder, "missing")
        _write_bundle(folder, "current", {"schema_version": SCHEMA_VERSION})
        _write_bundle(folder, "stale", {"schema_version": SCHEMA_VERSION - 1})

    def test_default_selects_missing_and_stale(self, tmp_path):
        self._setup(tmp_path)
        jobs = lr.scan_folder(tmp_path, include_all=False)
        by_stem = {j.song_path.stem: j.stale_reason for j in jobs}
        assert by_stem == {"missing": "missing", "stale": f"v{SCHEMA_VERSION - 1}"}

    def test_all_selects_everything(self, tmp_path):
        self._setup(tmp_path)
        jobs = lr.scan_folder(tmp_path, include_all=True)
        assert {j.song_path.stem for j in jobs} == {"current", "stale", "missing"}
        assert all(j.stale_reason == "all" for j in jobs)

    def test_corrupt_bundle_counts_as_missing(self, tmp_path):
        _touch_video(tmp_path, "broken")
        (tmp_path / "alignment_debug").mkdir()
        (tmp_path / "alignment_debug" / "broken.json").write_text("{not json", encoding="utf-8")
        jobs = lr.scan_folder(tmp_path, include_all=False)
        assert [j.stale_reason for j in jobs] == ["missing"]

    def test_ignores_non_video_files(self, tmp_path):
        (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
        jobs = lr.scan_folder(tmp_path, include_all=True)
        assert jobs == []


class TestScanFolderSelection:
    def test_selected_current_song_included_unselected_stale_excluded(self, tmp_path):
        _touch_video(tmp_path, "current")
        _touch_video(tmp_path, "stale")
        _write_bundle(tmp_path, "current", {"schema_version": SCHEMA_VERSION})
        _write_bundle(tmp_path, "stale", {"schema_version": SCHEMA_VERSION - 1})

        jobs = lr.scan_folder(tmp_path, include_all=False, songs=[tmp_path / "current.mp4"])

        assert [j.song_path.stem for j in jobs] == ["current"]
        assert jobs[0].stale_reason == "selected"


# ---------------------------------------------------------------------------
# resolve_plan (default) — reuse, else fetch/prompt
# ---------------------------------------------------------------------------


class TestResolvePlanDefault:
    def test_no_bundle_no_id_prompts(self, tmp_path):
        plan = lr.resolve_plan(_job(tmp_path, "plain", None), reset=False)
        assert plan.kind == "prompt"

    def test_no_bundle_with_id_fetches(self, tmp_path):
        plan = lr.resolve_plan(_job(tmp_path, YT_STEM, None), reset=False)
        assert plan.kind == "fetch"
        assert plan.fallback.kind == "prompt"

    def test_srt_origin_with_srt_on_disk_reuses(self, tmp_path):
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "s.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
        plan = lr.resolve_plan(_job(tmp_path, "s", {"lyrics": {"origin": "srt"}}), reset=False)
        assert plan.kind == "seed"
        assert plan.lyrics_path == subs / "s.srt"
        assert plan.seed == {"lyrics_origin": "srt"}

    def test_srt_origin_missing_srt_falls_through_to_fetch(self, tmp_path):
        plan = lr.resolve_plan(_job(tmp_path, YT_STEM, {"lyrics": {"origin": "srt"}}), reset=False)
        assert plan.kind == "fetch"

    def test_genius_with_ytasr_and_json3_on_disk_reuses(self, tmp_path):
        subs = tmp_path / "subtitles"
        subs.mkdir()
        asr_rel = f"subtitles/s{ASR_JSON3_SUFFIX}"
        (tmp_path / asr_rel).write_text("{}", encoding="utf-8")
        ytasr = {"asr_file": asr_rel, "n_words": 40, "wpm": 60.0}
        bundle = {
            "media_duration_s": 200.0,
            "lyrics": {
                "origin": "genius",
                "lines": ["hello", "world"],
                "ytasr": ytasr,
                "genius": {"id": 9, "title": "H", "artist": "W"},
            },
        }
        plan = lr.resolve_plan(_job(tmp_path, "s", bundle), reset=False)
        assert plan.kind == "seed"
        assert plan.lyrics_lines == ["hello", "world"]
        assert plan.seed["lyrics_origin"] == "genius"
        assert plan.seed["ytasr"] == ytasr
        assert plan.seed["genius"] == {"id": 9, "title": "H", "artist": "W"}
        assert plan.seed["media_duration_s"] == 200.0
        assert "ytasr" in plan.label

    def test_genius_with_ytasr_but_json3_missing_drops_source(self, tmp_path):
        bundle = {
            "lyrics": {
                "origin": "genius",
                "lines": ["hello"],
                "genius": {"id": 9, "title": "H", "artist": "W"},
                "ytasr": {"asr_file": f"subtitles/s{ASR_JSON3_SUFFIX}", "n_words": 40},
            },
        }
        plan = lr.resolve_plan(_job(tmp_path, "s", bundle), reset=False)
        assert plan.kind == "seed"
        assert "ytasr" not in plan.seed
        assert "missing" in plan.label

    def test_genius_with_identity_only_seeds_without_source(self, tmp_path):
        bundle = {
            "lyrics": {
                "origin": "genius",
                "lines": ["hello"],
                "genius": {"id": 9, "title": "H", "artist": "W"},
            },
        }
        plan = lr.resolve_plan(_job(tmp_path, "s", bundle), reset=False)
        assert plan.kind == "seed"
        assert "ytasr" not in plan.seed
        assert plan.seed["genius"] == {"id": 9, "title": "H", "artist": "W"}

    def test_genius_without_identity_falls_through(self, tmp_path):
        # Lines but no recorded identity -> not reusable; a song with a YouTube
        # id falls through to fetch (then a prompt fills in the provenance).
        bundle = {"lyrics": {"origin": "genius", "lines": ["hello"]}}
        plan = lr.resolve_plan(_job(tmp_path, YT_STEM, bundle), reset=False)
        assert plan.kind == "fetch"

    def test_non_srt_origin_with_srt_but_no_identity_never_reuses(self, tmp_path):
        # youtube_srt_present is contaminated by the pipeline's own generated
        # SRT, and there's no recorded identity -> the on-disk .srt is never
        # reused; the song falls through to fetch/prompt instead.
        _make_srt(tmp_path, "plain")
        bundle = {
            "lyrics": {"origin": "genius", "lines": ["hello"]},
            "ground_truth_refs": {"youtube_srt_present": True},
        }
        plan = lr.resolve_plan(_job(tmp_path, "plain", bundle), reset=False)
        assert plan.kind == "prompt"  # no YouTube id -> straight to prompt

    def test_unknown_origin_without_identity_falls_through(self, tmp_path):
        bundle = {"lyrics": {"origin": "unknown", "lines": ["a", "b"]}}
        plan = lr.resolve_plan(_job(tmp_path, "plain", bundle), reset=False)
        assert plan.kind == "prompt"

    def test_origin_without_lines_falls_through(self, tmp_path):
        bundle = {"lyrics": {"origin": "unknown"}}
        plan = lr.resolve_plan(_job(tmp_path, "plain", bundle), reset=False)
        assert plan.kind == "prompt"

    def test_falls_back_to_align_lines_when_no_lines(self, tmp_path):
        bundle = {
            "lyrics": {
                "origin": "genius",
                "align_lines": ["hello there"],
                "genius": {"id": 1, "title": "H", "artist": "W"},
            },
        }
        plan = lr.resolve_plan(_job(tmp_path, "s", bundle), reset=False)
        assert plan.kind == "seed"
        assert plan.lyrics_lines == ["hello there"]


# ---------------------------------------------------------------------------
# resolve_plan (reset) — ignore provenance, re-resolve from scratch
# ---------------------------------------------------------------------------


class TestResolvePlanReset:
    def test_reset_ignores_reusable_bundle(self, tmp_path):
        # A perfectly reusable genius+ytasr bundle is discarded in reset mode;
        # a song with a YouTube id is re-resolved via fetch.
        subs = tmp_path / "subtitles"
        subs.mkdir()
        asr_rel = f"subtitles/{YT_STEM}{ASR_JSON3_SUFFIX}"
        (tmp_path / asr_rel).write_text("{}", encoding="utf-8")
        bundle = {
            "lyrics": {
                "origin": "genius",
                "lines": ["hi"],
                "ytasr": {"asr_file": asr_rel, "n_words": 40},
                "genius": {"id": 9, "title": "H", "artist": "W"},
            },
        }
        plan = lr.resolve_plan(_job(tmp_path, YT_STEM, bundle), reset=True)
        assert plan.kind == "fetch"

    def test_reset_ignores_srt_origin(self, tmp_path):
        _make_srt(tmp_path, YT_STEM)
        plan = lr.resolve_plan(_job(tmp_path, YT_STEM, {"lyrics": {"origin": "srt"}}), reset=True)
        assert plan.kind == "fetch"

    def test_reset_no_id_prompts(self, tmp_path):
        plan = lr.resolve_plan(_job(tmp_path, "plain", {"lyrics": {"origin": "srt"}}), reset=True)
        assert plan.kind == "prompt"


class TestCustomSheetWinsEveryPlan:
    """A custom lyric sheet on disk is the song's pick, whatever the bundle says
    and whether or not the run is a reset."""

    GENIUS_BUNDLE = {
        "lyrics": {
            "origin": "genius",
            "lines": ["hi"],
            "genius": {"id": 9, "title": "H", "artist": "W"},
        },
    }

    @pytest.mark.parametrize("reset", [False, True])
    def test_resolve_plan_returns_the_custom_plan(self, tmp_path, reset):
        sheet = _write_sheet(tmp_path, YT_STEM)

        plan = lr.resolve_plan(_job(tmp_path, YT_STEM, self.GENIUS_BUNDLE), reset=reset)

        assert plan.kind == "seed"
        assert plan.lyrics_path == sheet
        assert plan.seed == {"lyrics_origin": "custom"}
        assert plan.custom_text is None  # the sheet is already on disk
        assert lr.is_custom_plan(plan)

    def test_reuse_plan_prefers_it_over_a_reusable_bundle(self, tmp_path):
        _write_sheet(tmp_path, YT_STEM)

        plan = lr.reuse_plan(_job(tmp_path, YT_STEM, self.GENIUS_BUNDLE))

        assert lr.is_custom_plan(plan)

    def test_reuse_plan_finds_it_with_no_bundle_at_all(self, tmp_path):
        _write_sheet(tmp_path, YT_STEM)

        assert lr.is_custom_plan(lr.reuse_plan(_job(tmp_path, YT_STEM, None)))

    def test_without_a_sheet_resolution_is_unchanged(self, tmp_path):
        assert lr.custom_plan(_job(tmp_path, YT_STEM, None)) is None
        assert lr.resolve_plan(_job(tmp_path, YT_STEM, None), reset=True).kind == "fetch"
        assert lr.reuse_plan(_job(tmp_path, YT_STEM, None)) is None

    def test_another_songs_sheet_is_not_this_songs(self, tmp_path):
        _write_sheet(tmp_path, "Song.live")

        assert lr.custom_plan(_job(tmp_path, "Song", None)) is None
        assert lr.custom_sheet_path(tmp_path / "Song.mp4") is None

    @pytest.mark.parametrize("reset", [False, True])
    def test_resolve_plan_returns_the_movie_plan_for_a_movie_sheet(self, tmp_path, reset):
        sheet = _write_movie_sheet(tmp_path, YT_STEM)

        plan = lr.resolve_plan(_job(tmp_path, YT_STEM, self.GENIUS_BUNDLE), reset=reset)

        assert plan.kind == "seed"
        assert plan.lyrics_path == sheet
        assert plan.seed == {"lyrics_origin": "movie_srt"}
        assert plan.custom_text is None  # the sheet is already on disk
        assert plan.label == "movie subtitles"
        assert lr.is_custom_plan(plan) and lr.is_movie_plan(plan)

    def test_reuse_plan_prefers_a_movie_sheet_over_a_reusable_bundle(self, tmp_path):
        _write_movie_sheet(tmp_path, YT_STEM)

        assert lr.is_movie_plan(lr.reuse_plan(_job(tmp_path, YT_STEM, self.GENIUS_BUNDLE)))

    def test_reuse_plan_finds_a_movie_sheet_with_no_bundle_at_all(self, tmp_path):
        _write_movie_sheet(tmp_path, YT_STEM)

        assert lr.is_movie_plan(lr.reuse_plan(_job(tmp_path, YT_STEM, None)))

    def test_a_typed_sheet_is_a_custom_plan_and_not_a_movie_plan(self, tmp_path):
        _write_sheet(tmp_path, YT_STEM)

        plan = lr.custom_plan(_job(tmp_path, YT_STEM, None))

        assert lr.is_custom_plan(plan) and not lr.is_movie_plan(plan)

    def test_the_sheet_path_is_whichever_kind_is_on_disk(self, tmp_path):
        song = tmp_path / f"{YT_STEM}.mp4"
        assert lr.custom_sheet_path(song) is None

        typed = _write_sheet(tmp_path, YT_STEM)
        assert lr.custom_sheet_path(song) == typed

        typed.unlink()
        movie = _write_movie_sheet(tmp_path, YT_STEM)
        assert lr.custom_sheet_path(song) == movie


# ---------------------------------------------------------------------------
# adopt_caption / fetch_caption — download + length gate + resolve-or-revert
# ---------------------------------------------------------------------------


def _gap_bundle(media_duration_s: float | None = None) -> dict:
    """A bundle with no reusable lyric source (so the default plan is fetch)."""
    bundle: dict = {"lyrics": {"origin": "unknown"}}
    if media_duration_s is not None:
        bundle["media_duration_s"] = media_duration_s
    return bundle


class TestAdoptCaption:
    def _fetch_job(self, tmp_path, bundle=None):
        job = _job(tmp_path, YT_STEM, bundle)
        job.plan = lr.resolve_plan(job, reset=False)
        assert job.plan.kind == "fetch"
        return job

    def test_sparse_caption_deleted_and_falls_back(self, tmp_path):
        job = self._fetch_job(tmp_path, _gap_bundle(media_duration_s=60.0))
        fallback = job.plan.fallback
        srt = _make_srt(tmp_path, f"{YT_STEM}.en", n_words=3)  # 3 wpm over 60s

        lr.adopt_caption(job, srt)

        assert job.plan is fallback
        assert not srt.exists()

    def test_dense_caption_already_at_stem_srt_kept_and_seeded(self, tmp_path):
        job = self._fetch_job(tmp_path, _gap_bundle(media_duration_s=60.0))
        # Already at the playback-matched name (what find_local_srt hands
        # add_songs' handoff after the download manager's own move) -- no
        # os.replace needed, and the file must survive untouched.
        srt = _make_srt(tmp_path, YT_STEM, n_words=60)  # 60 wpm over 60s

        lr.adopt_caption(job, srt)

        assert _is_srt_plan(job.plan)
        assert job.plan.lyrics_path == srt
        assert srt.exists()


class TestFetchCaption:
    def _fetch_job(self, tmp_path, bundle=None):
        job = _job(tmp_path, YT_STEM, bundle)
        job.plan = lr.resolve_plan(job, reset=False)
        assert job.plan.kind == "fetch"
        return job

    def _writer(self, srt_path: Path, n_words: int):
        def fake_dl(url, dest, stem):
            Path(dest).mkdir(parents=True, exist_ok=True)
            words = " ".join(["la"] * n_words)
            srt_path.write_text(f"1\n00:00:01,000 --> 00:00:04,000\n{words}\n", encoding="utf-8")
            return str(srt_path)

        return fake_dl

    def test_success_becomes_srt_plan(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lr, "probe_duration", lambda p: None)  # skip wpm gate
        job = self._fetch_job(tmp_path)
        srt = tmp_path / "subtitles" / f"{YT_STEM}.en.srt"
        monkeypatch.setattr(lr, "download_manual_en_subs", self._writer(srt, 60))
        lr.fetch_caption(job)
        assert _is_srt_plan(job.plan)
        # Promoted from yt-dlp's <stem>.en.srt to the playback-matched <stem>.srt.
        playback_srt = tmp_path / "subtitles" / f"{YT_STEM}.srt"
        assert job.plan.lyrics_path == playback_srt
        assert playback_srt.exists()
        assert not srt.exists()
        assert job.plan.label == "fetched srt (from video)"

    def test_no_caption_reverts_to_fallback(self, tmp_path, monkeypatch):
        job = self._fetch_job(tmp_path)
        fallback = job.plan.fallback
        monkeypatch.setattr(lr, "download_manual_en_subs", lambda url, dest, stem: None)
        lr.fetch_caption(job)
        assert job.plan is fallback
        assert job.plan.kind == "prompt"

    def test_a_download_that_fails_reverts_to_fallback(self, tmp_path, monkeypatch, caplog):
        job = self._fetch_job(tmp_path)
        fallback = job.plan.fallback

        def fail(url, dest, stem):
            raise lr.CaptionDownloadFailed("HTTP Error 403")

        monkeypatch.setattr(lr, "download_manual_en_subs", fail)
        lr.fetch_caption(job)
        assert job.plan is fallback
        assert "HTTP Error 403" in caplog.text

    def test_too_sparse_discarded_and_reverts(self, tmp_path, monkeypatch):
        job = self._fetch_job(tmp_path, _gap_bundle(media_duration_s=60.0))
        fallback = job.plan.fallback
        srt = tmp_path / "subtitles" / f"{YT_STEM}.en.srt"
        monkeypatch.setattr(lr, "download_manual_en_subs", self._writer(srt, 3))  # 3 wpm
        lr.fetch_caption(job)
        assert job.plan is fallback
        assert not srt.exists()

    def test_dense_caption_passes_gate(self, tmp_path, monkeypatch):
        job = self._fetch_job(tmp_path, _gap_bundle(media_duration_s=60.0))
        srt = tmp_path / "subtitles" / f"{YT_STEM}.en.srt"
        monkeypatch.setattr(lr, "download_manual_en_subs", self._writer(srt, 60))  # 60 wpm
        lr.fetch_caption(job)
        assert _is_srt_plan(job.plan)
        assert (tmp_path / "subtitles" / f"{YT_STEM}.srt").exists()
        assert not srt.exists()


class TestCheckCaption:
    """``check_caption`` measures a throwaway download and leaves nothing behind."""

    @pytest.fixture
    def scratch_root(self, tmp_path, monkeypatch):
        root = tmp_path / "pk_tmp"
        root.mkdir()
        monkeypatch.setattr(lr, "get_temp_directory", lambda: str(root))
        return root

    def _check(self, tmp_path, scratch_root, monkeypatch, n_words: int | str | None, duration=60.0):
        """Run ``check_caption`` with a download of ``n_words`` (None: no caption; "fail")."""

        def fake_dl(url, dest, stem):
            assert dest.startswith(str(scratch_root))
            if n_words == "fail":
                raise lr.CaptionDownloadFailed("timed out")
            if n_words is None:
                return None
            srt = Path(dest) / f"{stem}.en.srt"
            words = " ".join(["la"] * n_words)
            srt.write_text(f"1\n00:00:01,000 --> 00:00:04,000\n{words}\n", encoding="utf-8")
            return str(srt)

        monkeypatch.setattr(lr, "download_manual_en_subs", fake_dl)
        monkeypatch.setattr(lr, "probe_duration", lambda p: None)
        job = _job(tmp_path, YT_STEM, _gap_bundle(media_duration_s=duration))

        result = lr.check_caption(job)

        assert list(scratch_root.iterdir()) == []
        assert not (tmp_path / "subtitles").exists()
        return result

    def test_no_caption(self, tmp_path, scratch_root, monkeypatch):
        result = self._check(tmp_path, scratch_root, monkeypatch, n_words=None)
        assert result == lr.CaptionCheck(found=False, wpm=None, passed=False)
        assert result.failed is False

    def test_a_download_that_fails_is_a_check_that_could_not_run(
        self, tmp_path, scratch_root, monkeypatch
    ):
        result = self._check(tmp_path, scratch_root, monkeypatch, n_words="fail")
        assert result == lr.CaptionCheck(found=False, wpm=None, passed=False, failed=True)

    def test_sparse_caption_fails_the_gate(self, tmp_path, scratch_root, monkeypatch):
        result = self._check(tmp_path, scratch_root, monkeypatch, n_words=3)  # 3 wpm over 60s
        assert result == lr.CaptionCheck(found=True, wpm=3.0, passed=False)

    def test_dense_caption_passes_the_gate(self, tmp_path, scratch_root, monkeypatch):
        result = self._check(tmp_path, scratch_root, monkeypatch, n_words=60)  # 60 wpm
        assert result == lr.CaptionCheck(found=True, wpm=60.0, passed=True)

    def test_unmeasurable_caption_passes_the_gate(self, tmp_path, scratch_root, monkeypatch):
        result = self._check(tmp_path, scratch_root, monkeypatch, n_words=3, duration=None)
        assert result == lr.CaptionCheck(found=True, wpm=None, passed=True)

    def test_downloads_the_video_by_its_youtube_id(self, tmp_path, scratch_root, monkeypatch):
        urls = []
        monkeypatch.setattr(lr, "download_manual_en_subs", lambda url, dest, stem: urls.append(url))
        lr.check_caption(_job(tmp_path, YT_STEM, None))
        assert urls == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]


class TestCheckVideoCaption:
    """``check_video_caption`` measures against YouTube's length, before any download."""

    @pytest.fixture
    def downloaded(self, tmp_path, monkeypatch):
        """Fake a 60-word caption download; yields the URLs asked for."""
        root = tmp_path / "pk_tmp"
        root.mkdir()
        monkeypatch.setattr(lr, "get_temp_directory", lambda: str(root))
        urls = []

        def fake_dl(url, dest, stem):
            urls.append(url)
            srt = Path(dest) / f"{stem}.en.srt"
            words = " ".join(["la"] * 60)
            srt.write_text(f"1\n00:00:01,000 --> 00:00:04,000\n{words}\n", encoding="utf-8")
            return str(srt)

        monkeypatch.setattr(lr, "download_manual_en_subs", fake_dl)
        yield urls
        assert list(root.iterdir()) == []

    def test_a_caption_dense_for_the_video_length_passes(self, downloaded):
        result = lr.check_video_caption("dQw4w9WgXcQ", 60.0)

        assert result == lr.CaptionCheck(found=True, wpm=60.0, passed=True)
        assert downloaded == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]

    def test_the_same_caption_on_a_long_video_is_too_sparse(self, downloaded):
        result = lr.check_video_caption("dQw4w9WgXcQ", 600.0)  # 6 wpm

        assert result == lr.CaptionCheck(found=True, wpm=6.0, passed=False)

    def test_with_no_length_the_caption_cannot_be_measured_and_passes(self, downloaded):
        assert lr.check_video_caption("dQw4w9WgXcQ", None) == lr.CaptionCheck(
            found=True, wpm=None, passed=True
        )


@pytest.fixture(
    params=[
        "1\n00:00:01,000 --> 00:00:04,000\ncafé la la\n".encode("latin-1"),
        b"1\n999999999999999:00:01,000 --> 999999999999999:00:04,000\nla la\n",
        b"not an srt at all",
    ],
    ids=["not utf-8", "out-of-range timestamp", "not an srt"],
)
def unreadable_caption(request, tmp_path) -> Path:
    """A caption on disk that can't be read or parsed, at the playback-matched name."""
    subs = tmp_path / "subtitles"
    subs.mkdir()
    path = subs / f"{YT_STEM}.srt"
    path.write_bytes(request.param)
    return path


class TestSrtWordCount:
    def test_counts_the_cleaned_cue_words(self, tmp_path):
        assert lr._srt_word_count(_make_srt(tmp_path, YT_STEM, n_words=7)) == 7

    def test_a_caption_that_cannot_be_read_has_no_count(self, unreadable_caption, caplog):
        with caplog.at_level("WARNING", logger=lr.logger.name):
            assert lr._srt_word_count(unreadable_caption) is None

        assert "Cannot read SRT" in caplog.text

    def test_a_missing_caption_has_no_count(self, tmp_path):
        assert lr._srt_word_count(tmp_path / "gone.srt") is None


class TestGateOnDiskCaption:
    def _job_without_plan(self, tmp_path):
        return _job(tmp_path, YT_STEM, _gap_bundle(media_duration_s=60.0))

    def test_no_caption_on_disk_leaves_the_plan_alone(self, tmp_path):
        job = self._job_without_plan(tmp_path)

        assert lr.gate_on_disk_caption(job) is False
        assert job.plan is None

    def test_sparse_caption_is_deleted(self, tmp_path):
        job = self._job_without_plan(tmp_path)
        srt = _make_srt(tmp_path, YT_STEM, n_words=3)  # 3 wpm over 60s

        assert lr.gate_on_disk_caption(job) is False
        assert not srt.exists()
        assert job.plan.kind == "prompt"

    def test_dense_caption_is_kept_and_seeded(self, tmp_path):
        job = self._job_without_plan(tmp_path)
        srt = _make_srt(tmp_path, YT_STEM, n_words=60)  # 60 wpm

        assert lr.gate_on_disk_caption(job) is True
        assert srt.exists()
        assert _is_srt_plan(job.plan)
        assert job.plan.lyrics_path == srt

    def test_a_caption_that_cannot_be_read_passes_and_is_kept(self, tmp_path, unreadable_caption):
        # It can't be measured, and it may be the admin's own file.
        job = self._job_without_plan(tmp_path)

        assert lr.gate_on_disk_caption(job) is True
        assert unreadable_caption.exists()
        assert job.plan.lyrics_path == unreadable_caption


# ---------------------------------------------------------------------------
# backup_text_folders — scoped backup for --song
# ---------------------------------------------------------------------------


class TestBackupTextFoldersScoped:
    def test_copies_only_selected_songs_files(self, tmp_path):
        _scoped_library(tmp_path)

        backup = lr.backup_text_folders(tmp_path, stems=["Song"])

        assert backup is not None
        assert (backup / "subtitles" / "Song.srt").exists()
        assert (backup / "subtitles" / "Song.srt.generated").exists()
        assert (backup / "karaoke" / "Song.ass").exists()
        assert (backup / "alignment_debug" / "Song.json").exists()
        # The longer-stem sibling and the other song are never claimed.
        assert not (backup / "subtitles" / "Song.live.srt").exists()
        assert not (backup / "subtitles" / "Other.srt").exists()
        assert not (backup / "karaoke" / "Other.ass").exists()
        assert not (backup / "alignment_debug" / "Other.json").exists()

    def test_unscoped_backup_is_unchanged(self, tmp_path):
        _scoped_library(tmp_path)

        backup = lr.backup_text_folders(tmp_path)

        assert (backup / "subtitles" / "Song.live.srt").exists()
        assert (backup / "subtitles" / "Other.srt").exists()
        assert (backup / "karaoke" / "Other.ass").exists()


# ---------------------------------------------------------------------------
# clear_output_folders — reset wipes the regenerable outputs (after backup)
# ---------------------------------------------------------------------------


class TestClearOutputFolders:
    def test_removes_outputs_but_keeps_stems(self, tmp_path):
        for sub in ("subtitles", "karaoke", "lyrics"):
            (tmp_path / sub).mkdir()
            (tmp_path / sub / "x").write_text("x", encoding="utf-8")
        (tmp_path / "vocal").mkdir()
        (tmp_path / "vocal" / f"{YT_STEM}---vocal.m4a").write_text("a", encoding="utf-8")
        lr.clear_output_folders(tmp_path)
        assert not (tmp_path / "subtitles" / "x").exists()
        assert not (tmp_path / "karaoke").exists()
        # lyrics/ is now content-spared like subtitles/ (an .lrc is a
        # non-regenerable input, see TestClearOutputFolders below), not
        # wholesale-removed like karaoke/ -- the non-.lrc file inside it
        # still gets wiped.
        assert not (tmp_path / "lyrics" / "x").exists()
        assert (tmp_path / "vocal" / f"{YT_STEM}---vocal.m4a").exists()

    def test_preserves_asr_captions_wipes_the_rest(self, tmp_path):
        # ASR captions are non-regenerable download artifacts — they must
        # survive the reset wipe, unlike generated SRTs and re-fetched captions.
        subs = tmp_path / "subtitles"
        subs.mkdir()
        asr = subs / f"{YT_STEM}{ASR_JSON3_SUFFIX}"
        asr.write_text("{}", encoding="utf-8")
        (subs / f"{YT_STEM}.srt").write_text("generated", encoding="utf-8")
        (subs / f"{YT_STEM}.en.srt").write_text("caption", encoding="utf-8")
        lr.clear_output_folders(tmp_path)
        assert asr.exists()
        assert not (subs / f"{YT_STEM}.srt").exists()
        assert not (subs / f"{YT_STEM}.en.srt").exists()

    def test_preserves_lrc_variants_wipes_the_rest(self, tmp_path):
        # LRCLIB variants (E1 gated fill) are non-regenerable fetch-time
        # inputs -- they must survive the reset wipe like ASR captions do.
        lyrics = tmp_path / "lyrics"
        lyrics.mkdir()
        lrc = lyrics / f"{YT_STEM}.lrc"
        lrc.write_text("[00:01.00]hi\n", encoding="utf-8")
        (lyrics / f"{YT_STEM}.txt").write_text("stale reuse txt", encoding="utf-8")
        lr.clear_output_folders(tmp_path)
        assert lrc.exists()
        assert not (lyrics / f"{YT_STEM}.txt").exists()

    def test_preserves_custom_sheets_wipes_the_rest(self, tmp_path):
        # An admin's own lyric sheet is hand-made: a reset must not lose it.
        sheet = _write_sheet(tmp_path, YT_STEM)
        stale = sheet.with_name(f"{YT_STEM}.txt")
        stale.write_text("stale reuse txt", encoding="utf-8")

        lr.clear_output_folders(tmp_path)

        assert sheet.exists()
        assert not stale.exists()

    def test_preserves_movie_sheets_wipes_the_rest(self, tmp_path):
        sheet = _write_movie_sheet(tmp_path, YT_STEM)
        stale = sheet.with_name(f"{YT_STEM}.txt")
        stale.write_text("stale reuse txt", encoding="utf-8")

        lr.clear_output_folders(tmp_path)

        assert sheet.exists()
        assert not stale.exists()

    def test_missing_folders_is_noop(self, tmp_path):
        lr.clear_output_folders(tmp_path)  # does not raise


class TestClearOutputFoldersScoped:
    def test_removes_only_selected_songs_regenerable_files(self, tmp_path):
        _scoped_library(tmp_path)

        lr.clear_output_folders(tmp_path, stems=["Song"])

        # Selected song's regenerable output is gone.
        assert not (tmp_path / "subtitles" / "Song.srt").exists()
        assert not (tmp_path / "karaoke" / "Song.ass").exists()
        assert not (tmp_path / "lyrics" / "Song.txt").exists()
        # Non-regenerable inputs for the selected song survive.
        assert (tmp_path / "subtitles" / f"Song{ASR_JSON3_SUFFIX}").exists()
        assert (tmp_path / "lyrics" / "Song.lrc").exists()
        # The longer-stem sibling and every other song's files are untouched.
        assert (tmp_path / "subtitles" / "Song.live.srt").exists()
        assert (tmp_path / "subtitles" / "Other.srt").exists()
        assert (tmp_path / "karaoke" / "Other.ass").exists()
        assert (tmp_path / "lyrics" / "Other.txt").exists()
        # Never a whole-folder wipe: the folders themselves survive.
        assert (tmp_path / "karaoke").is_dir()

    def test_keeps_the_selected_songs_sheet_and_leaves_the_others(self, tmp_path):
        _scoped_library(tmp_path)
        mine = _write_sheet(tmp_path, "Song")
        sibling = _write_sheet(tmp_path, "Song.live")
        other = _write_sheet(tmp_path, "Other")

        lr.clear_output_folders(tmp_path, stems=["Song"])

        assert mine.exists() and sibling.exists() and other.exists()
        assert not (tmp_path / "lyrics" / "Song.txt").exists()

    def test_keeps_the_selected_songs_movie_sheet_and_leaves_the_others(self, tmp_path):
        _scoped_library(tmp_path)
        mine = _write_movie_sheet(tmp_path, "Song")
        sibling = _write_movie_sheet(tmp_path, "Song.live")
        other = _write_movie_sheet(tmp_path, "Other")

        lr.clear_output_folders(tmp_path, stems=["Song"])

        assert mine.exists() and sibling.exists() and other.exists()
        assert not (tmp_path / "lyrics" / "Song.txt").exists()


# ---------------------------------------------------------------------------
# _owner / _remove — the shared ownership rule and the delete helper
# ---------------------------------------------------------------------------


class TestOwner:
    STEMS = {"Song", "Song.live", "Other"}

    def test_entry_belongs_to_its_stem(self):
        assert lr._owner("Song.srt", self.STEMS) == "Song"
        assert lr._owner("Song.srt.generated", self.STEMS) == "Song"
        assert lr._owner("Song", self.STEMS) == "Song"

    def test_longest_claiming_stem_wins(self):
        assert lr._owner("Song.live.srt", self.STEMS) == "Song.live"
        assert lr._owner("Song.live", self.STEMS) == "Song.live"

    def test_a_prefix_without_a_dot_is_not_a_claim(self):
        assert lr._owner("Songs.srt", self.STEMS) is None

    def test_unclaimed_entry_has_no_owner(self):
        assert lr._owner("Unknown.srt", self.STEMS) is None


class TestOwnedByAny:
    def test_entry_of_a_selected_stem(self):
        assert lr._owned_by_any("Song.srt", ["Song"], {"Song", "Other"})

    def test_longer_stem_sibling_is_not_owned_by_the_shorter_selection(self):
        assert not lr._owned_by_any("Song.live.srt", ["Song"], {"Song", "Song.live"})

    def test_unclaimed_name_is_rejected_without_scanning_the_library(self, monkeypatch):
        def scan(name, all_stems):
            raise AssertionError("full ownership scan for a name no selected stem claims")

        monkeypatch.setattr(lr, "_owner", scan)

        assert not lr._owned_by_any("Unknown.srt", ["Song"], {"Song", "Other"})


class TestRemove:
    def test_removes_a_file_and_a_tree(self, tmp_path):
        file = tmp_path / "a.txt"
        file.write_text("x", encoding="utf-8")
        tree = tmp_path / "tree"
        (tree / "sub").mkdir(parents=True)
        (tree / "sub" / "b.txt").write_text("y", encoding="utf-8")

        lr._remove(file)
        lr._remove(tree)

        assert not file.exists()
        assert not tree.exists()

    def test_missing_path_is_a_noop(self, tmp_path):
        lr._remove(tmp_path / "nope")  # does not raise

    def test_file_that_cannot_be_removed_raises(self, tmp_path, monkeypatch):
        # A file that survives a reset could be mistaken for a current caption,
        # so unlike a tree it stops the reset instead of being warned about.
        file = tmp_path / "locked.srt"
        file.write_text("x", encoding="utf-8")
        real_unlink = Path.unlink

        def unlink(self, missing_ok=False):
            if self == file:
                raise PermissionError(13, "in use", str(self))
            real_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", unlink)

        with pytest.raises(OSError):
            lr._remove(file)

    def test_tree_that_cannot_be_removed_is_warned_about(self, tmp_path, monkeypatch, caplog):
        tree = tmp_path / "tree"
        tree.mkdir()

        def boom(path):
            raise OSError("locked")

        monkeypatch.setattr(lr.shutil, "rmtree", boom)

        lr._remove(tree)  # does not raise

        assert "Could not fully remove" in caplog.text
        assert "locked" in caplog.text


# ---------------------------------------------------------------------------
# prepare_lyrics — LRCLIB resolve for the no-YouTube-id Genius fallback
# ---------------------------------------------------------------------------


class TestPrepareLyricsNoIdSidecar:
    """A Genius pick on a song without a YouTube id bypasses
    LyricsFetchStage (and its LRCLIB leg), so prepare_lyrics resolves the
    variant itself — knob-gated and never fatal to the song's run."""

    def _run(self, tmp_path, monkeypatch, config, resolve_error=None):
        job = _job(tmp_path, "noid", None)
        job.plan = lr.Plan(kind="sidecar", genius_id=123, label="prompt -> genius")
        genius = MagicMock()
        genius.fetch_song.return_value = SimpleNamespace(title="H", artist="W", text="hello\nworld")
        ensure = MagicMock(return_value=None, side_effect=resolve_error)
        monkeypatch.setattr(lr.lrclib, "ensure_lrc", ensure)
        monkeypatch.setattr(lr, "probe_duration", MagicMock(return_value=200.0))
        lyrics_dir = tmp_path / "lyrics"
        lyrics_dir.mkdir(exist_ok=True)
        result = lr.prepare_lyrics(job, genius, lyrics_dir, config)
        return ensure, result, job

    def test_resolves_lrclib_variant(self, tmp_path, monkeypatch):
        ensure, (lyrics_path, stage), job = self._run(tmp_path, monkeypatch, PipelineConfig())

        ensure.assert_called_once_with(job.song_path, "H", "W", ["hello", "world"], 200.0)
        assert lyrics_path is not None
        assert stage is not None

    def test_knob_off_skips_resolve(self, tmp_path, monkeypatch):
        ensure, _, _ = self._run(tmp_path, monkeypatch, PipelineConfig(lrclib_fill=False))

        ensure.assert_not_called()

    def test_resolve_failure_is_not_fatal(self, tmp_path, monkeypatch):
        ensure, (lyrics_path, stage), _ = self._run(
            tmp_path, monkeypatch, PipelineConfig(), resolve_error=OSError("disk full")
        )

        ensure.assert_called_once()
        assert lyrics_path is not None
        assert stage is not None


# ---------------------------------------------------------------------------
# backfill_lrc — one song's LRCLIB variant for a genius reuse plan
# ---------------------------------------------------------------------------


class TestBackfillLrc:
    def _reuse_job(self, tmp_path):
        bundle = {
            "lyrics": {
                "origin": "genius",
                "lines": ["hello", "world"],
                "genius": {"id": 9, "title": "H", "artist": "W"},
            },
            "media_duration_s": 200.0,
        }
        job = _job(tmp_path, "s", bundle)
        job.plan = lr.resolve_plan(job, reset=False)
        return job

    def test_resolves_the_variant_from_the_recorded_identity(self, tmp_path, monkeypatch):
        job = self._reuse_job(tmp_path)
        ensure = MagicMock(return_value=None)
        monkeypatch.setattr(lr.lrclib, "ensure_lrc", ensure)

        lr.backfill_lrc(job, PipelineConfig())

        ensure.assert_called_once_with(job.song_path, "H", "W", ["hello", "world"], 200.0)

    def test_knob_off_skips_the_fetch(self, tmp_path, monkeypatch):
        job = self._reuse_job(tmp_path)
        ensure = MagicMock()
        monkeypatch.setattr(lr.lrclib, "ensure_lrc", ensure)

        lr.backfill_lrc(job, PipelineConfig(lrclib_fill=False))

        ensure.assert_not_called()

    def test_a_failure_is_logged_and_does_not_raise(self, tmp_path, monkeypatch, caplog):
        job = self._reuse_job(tmp_path)
        monkeypatch.setattr(lr.lrclib, "ensure_lrc", MagicMock(side_effect=OSError("disk full")))

        lr.backfill_lrc(job, PipelineConfig())

        assert "LRCLIB backfill failed" in caplog.text


# ---------------------------------------------------------------------------
# apply_lrclib_choice — lyrics/<stem>.lrc is the LRCLIB choice
# ---------------------------------------------------------------------------


class TestApplyLrclibChoice:
    GENIUS_BUNDLE = {
        "lyrics": {"origin": "genius", "genius": {"id": 9, "title": "H", "artist": "W"}}
    }
    RECORD = {"id": 42, "trackName": "T", "syncedLyrics": "[00:01.00]hello\n"}

    def _job_with_lrc(self, tmp_path, plan, bundle=None):
        job = _job(tmp_path, YT_STEM, bundle)
        job.plan = plan
        lrc = tmp_path / "lyrics" / f"{YT_STEM}.lrc"
        lrc.parent.mkdir(exist_ok=True)
        lrc.write_text("[lrclib_id:1]\n[00:01.00]old song\n", encoding="utf-8")
        return job, lrc

    def test_a_different_genius_id_drops_the_old_match(self, tmp_path):
        job, lrc = self._job_with_lrc(
            tmp_path, lr.Plan(kind="sidecar", genius_id=10), self.GENIUS_BUNDLE
        )

        lr.apply_lrclib_choice(job)

        assert not lrc.exists()

    def test_the_same_genius_id_keeps_the_match(self, tmp_path):
        job, lrc = self._job_with_lrc(
            tmp_path, lr.Plan(kind="sidecar", genius_id=9), self.GENIUS_BUNDLE
        )

        lr.apply_lrclib_choice(job)

        assert lrc.exists()

    def test_a_bundle_without_a_genius_id_drops_the_match(self, tmp_path):
        job, lrc = self._job_with_lrc(tmp_path, lr.Plan(kind="sidecar", genius_id=9), None)

        lr.apply_lrclib_choice(job)

        assert not lrc.exists()

    def test_a_chosen_record_replaces_the_file(self, tmp_path):
        job, lrc = self._job_with_lrc(tmp_path, lr.Plan(kind="sidecar", genius_id=9))
        job.plan.lrclib_record = self.RECORD

        lr.apply_lrclib_choice(job)

        assert "[lrclib_id:42]" in lrc.read_text(encoding="utf-8")

    def test_skip_writes_the_marker(self, tmp_path):
        job, lrc = self._job_with_lrc(tmp_path, lr.Plan(kind="sidecar", genius_id=9))
        job.plan.lrclib_skip = True

        lr.apply_lrclib_choice(job)

        assert lr.lrclib.is_skip_marker(lrc)

    def test_skip_wins_over_a_record_and_over_the_id_rule(self, tmp_path):
        job, lrc = self._job_with_lrc(
            tmp_path, lr.Plan(kind="sidecar", genius_id=10), self.GENIUS_BUNDLE
        )
        job.plan.lrclib_skip = True
        job.plan.lrclib_record = self.RECORD

        lr.apply_lrclib_choice(job)

        assert lr.lrclib.is_skip_marker(lrc)

    def test_seed_and_transcribe_plans_leave_the_file_alone(self, tmp_path):
        for plan in (
            lr.Plan(kind="seed", seed={"lyrics_origin": "genius"}),
            lr.Plan(kind="transcribe"),
        ):
            job, lrc = self._job_with_lrc(tmp_path, plan, self.GENIUS_BUNDLE)

            lr.apply_lrclib_choice(job)

            assert lrc.read_text(encoding="utf-8").startswith("[lrclib_id:1]")

    def test_prepare_lyrics_applies_the_choice_before_the_stage_can_reuse_the_file(
        self, tmp_path, monkeypatch
    ):
        job, lrc = self._job_with_lrc(
            tmp_path, lr.Plan(kind="sidecar", genius_id=10), self.GENIUS_BUNDLE
        )
        monkeypatch.setattr(lr, "write_choice", MagicMock())

        lr.prepare_lyrics(job, MagicMock(), tmp_path, PipelineConfig())

        assert not lrc.exists()


# ---------------------------------------------------------------------------
# prepare_regen_job / finish_regen_job -- the per-song work of a queued regen
# ---------------------------------------------------------------------------


class TestApplyCustomChoice:
    def _job_with(self, tmp_path, plan):
        job = _job(tmp_path, YT_STEM, None)
        job.plan = plan
        return job

    def test_a_custom_repair_writes_the_sheet(self, tmp_path):
        job = self._job_with(tmp_path, lr.custom_sheet_plan(tmp_path / f"{YT_STEM}.mp4", "a\nb\n"))

        lr.apply_custom_choice(job)

        assert lr.custom_sheet_path(job.song_path).read_text(encoding="utf-8") == "a\nb\n"

    def test_a_custom_repair_replaces_an_older_sheet(self, tmp_path):
        _write_sheet(tmp_path, YT_STEM, "old words\n")
        job = self._job_with(tmp_path, lr.custom_sheet_plan(tmp_path / f"{YT_STEM}.mp4", "new\n"))

        lr.apply_custom_choice(job)

        assert lr.custom_sheet_path(job.song_path).read_text(encoding="utf-8") == "new\n"

    def test_replaying_the_sheet_leaves_it_alone(self, tmp_path):
        sheet = _write_sheet(tmp_path, YT_STEM, "kept\n")
        job = self._job_with(tmp_path, lr.custom_plan(_job(tmp_path, YT_STEM, None)))

        lr.apply_custom_choice(job)

        assert sheet.read_text(encoding="utf-8") == "kept\n"

    @pytest.mark.parametrize(
        "plan",
        [
            lr.Plan(kind="seed", seed={"lyrics_origin": "srt"}, label="fetched srt"),
            lr.Plan(kind="sidecar", genius_id=5, label="genius pick"),
            lr.Plan(kind="transcribe"),
        ],
        ids=["caption", "genius", "transcribe"],
    )
    @pytest.mark.parametrize("write", [_write_sheet, _write_movie_sheet], ids=["typed", "movie"])
    def test_a_repair_to_another_source_deletes_either_kind_of_sheet(self, tmp_path, plan, write):
        sheet = write(tmp_path, YT_STEM)
        job = self._job_with(tmp_path, plan)
        job.replaces_custom = True

        lr.apply_custom_choice(job)

        assert not sheet.exists()

    def test_a_movie_repair_writes_the_srt_sheet(self, tmp_path):
        song = tmp_path / f"{YT_STEM}.mp4"
        job = self._job_with(tmp_path, lr.movie_sheet_plan(song, MOVIE_SRT))

        lr.apply_custom_choice(job)

        sheet = tmp_path / "lyrics" / f"{YT_STEM}.custom.srt"
        assert lr.custom_sheet_path(song) == sheet
        assert sheet.read_text(encoding="utf-8") == MOVIE_SRT

    def test_saving_a_movie_sheet_deletes_the_typed_one(self, tmp_path):
        typed = _write_sheet(tmp_path, YT_STEM)
        job = self._job_with(tmp_path, lr.movie_sheet_plan(tmp_path / f"{YT_STEM}.mp4", MOVIE_SRT))

        lr.apply_custom_choice(job)

        assert not typed.exists()
        assert lr.custom_sheet_path(job.song_path).suffix == ".srt"

    def test_saving_a_typed_sheet_deletes_the_movie_one(self, tmp_path):
        movie = _write_movie_sheet(tmp_path, YT_STEM)
        job = self._job_with(tmp_path, lr.custom_sheet_plan(tmp_path / f"{YT_STEM}.mp4", "new\n"))

        lr.apply_custom_choice(job)

        assert not movie.exists()
        assert lr.custom_sheet_path(job.song_path).read_text(encoding="utf-8") == "new\n"

    def test_saving_a_sheet_leaves_another_songs_sheets_alone(self, tmp_path):
        other = _write_movie_sheet(tmp_path, "Song.live")
        job = self._job_with(tmp_path, lr.custom_sheet_plan(tmp_path / "Song.mp4", "new\n"))

        lr.apply_custom_choice(job)

        assert other.exists()

    def test_replaying_the_movie_sheet_leaves_it_alone(self, tmp_path):
        sheet = _write_movie_sheet(tmp_path, YT_STEM, "kept\n")
        job = self._job_with(tmp_path, lr.custom_plan(_job(tmp_path, YT_STEM, None)))

        lr.apply_custom_choice(job)

        assert sheet.read_text(encoding="utf-8") == "kept\n"

    def test_any_other_plan_keeps_the_sheet(self, tmp_path):
        """A plan that missed the sheet (not a repair) must not cost the admin's lyrics."""
        sheet = _write_sheet(tmp_path, YT_STEM, "kept\n")

        lr.apply_custom_choice(self._job_with(tmp_path, lr.Plan(kind="transcribe")))

        assert sheet.read_text(encoding="utf-8") == "kept\n"

    def test_no_sheet_and_no_custom_plan_is_a_no_op(self, tmp_path):
        lr.apply_custom_choice(self._job_with(tmp_path, lr.Plan(kind="transcribe")))

        assert not (tmp_path / "lyrics").exists()


class TestPrepareLyricsCustom:
    """A custom sheet is read in place and gets the on-disk auto-caption as a 3rd
    source exactly when it passes the gate."""

    def _asr(self, tmp_path, n_words: int) -> Path:
        subs = tmp_path / "subtitles"
        subs.mkdir(exist_ok=True)
        segs = [
            {"utf8": "w0"} if i == 0 else {"utf8": f" w{i}", "tOffsetMs": i * 400}
            for i in range(n_words)
        ]
        asr = subs / f"{YT_STEM}{ASR_JSON3_SUFFIX}"
        asr.write_text(json.dumps({"events": [{"tStartMs": 0, "segs": segs}]}), encoding="utf-8")
        return asr

    def _prepare(self, tmp_path, monkeypatch, plan):
        monkeypatch.setattr(lr.ytasr, "probe_duration", MagicMock(return_value=60.0))
        job = _job(tmp_path, YT_STEM, None)
        job.plan = plan
        work = tmp_path / "work"
        work.mkdir(exist_ok=True)
        return job, lr.prepare_lyrics(job, MagicMock(), work, PipelineConfig())

    def test_the_sheet_is_the_lyrics_file_and_the_origin_is_custom(self, tmp_path, monkeypatch):
        sheet = _write_sheet(tmp_path, YT_STEM)

        _, (lyrics_path, stage) = self._prepare(
            tmp_path, monkeypatch, lr.custom_plan(_job(tmp_path, YT_STEM, None))
        )

        assert lyrics_path == sheet
        assert stage._seed["lyrics_origin"] == "custom"

    def test_a_typed_sheet_is_written_before_it_is_read(self, tmp_path, monkeypatch):
        plan = lr.custom_sheet_plan(tmp_path / f"{YT_STEM}.mp4", "typed line\n")

        _, (lyrics_path, _stage) = self._prepare(tmp_path, monkeypatch, plan)

        assert lyrics_path.read_text(encoding="utf-8") == "typed line\n"

    def test_the_seed_carries_a_caption_that_passes_the_gate(self, tmp_path, monkeypatch):
        _write_sheet(tmp_path, YT_STEM)
        self._asr(tmp_path, n_words=30)  # 30 words in 60 s: above the wpm floor
        plan = lr.custom_plan(_job(tmp_path, YT_STEM, None))

        _, (_path, stage) = self._prepare(tmp_path, monkeypatch, plan)

        assert stage._seed["ytasr"] == {
            "asr_file": f"subtitles/{YT_STEM}{ASR_JSON3_SUFFIX}",
            "n_words": 30,
            "wpm": 30.0,
        }
        assert stage._seed["media_duration_s"] == 60.0
        assert "ytasr" not in plan.seed  # the queued plan is not edited

    def test_the_seed_omits_a_caption_that_fails_the_gate(self, tmp_path, monkeypatch):
        _write_sheet(tmp_path, YT_STEM)
        self._asr(tmp_path, n_words=3)  # 3 words in 60 s: below the wpm floor

        _, (_path, stage) = self._prepare(
            tmp_path, monkeypatch, lr.custom_plan(_job(tmp_path, YT_STEM, None))
        )

        assert "ytasr" not in stage._seed
        assert stage._seed["media_duration_s"] == 60.0

    def test_the_seed_has_no_caption_when_none_is_on_disk(self, tmp_path, monkeypatch):
        _write_sheet(tmp_path, YT_STEM)

        _, (_path, stage) = self._prepare(
            tmp_path, monkeypatch, lr.custom_plan(_job(tmp_path, YT_STEM, None))
        )

        assert stage._seed == {"lyrics_origin": "custom"}

    def test_another_origins_seed_is_not_given_a_caption(self, tmp_path, monkeypatch):
        self._asr(tmp_path, n_words=30)
        plan = lr.Plan(kind="seed", lyrics_lines=["hi"], seed={"lyrics_origin": "genius"})

        _, (_path, stage) = self._prepare(tmp_path, monkeypatch, plan)

        assert stage._seed == {"lyrics_origin": "genius"}

    def test_the_movie_sheet_is_the_lyrics_file_and_the_origin_is_movie_srt(
        self, tmp_path, monkeypatch
    ):
        sheet = _write_movie_sheet(tmp_path, YT_STEM)

        _, (lyrics_path, stage) = self._prepare(
            tmp_path, monkeypatch, lr.custom_plan(_job(tmp_path, YT_STEM, None))
        )

        assert lyrics_path == sheet
        assert stage._seed["lyrics_origin"] == "movie_srt"

    def test_a_saved_movie_sheet_is_written_before_it_is_read(self, tmp_path, monkeypatch):
        plan = lr.movie_sheet_plan(tmp_path / f"{YT_STEM}.mp4", MOVIE_SRT)

        _, (lyrics_path, _stage) = self._prepare(tmp_path, monkeypatch, plan)

        assert lyrics_path.name == f"{YT_STEM}.custom.srt"
        assert lyrics_path.read_text(encoding="utf-8") == MOVIE_SRT

    def test_a_movie_sheet_is_not_given_a_caption_even_one_that_passes_the_gate(
        self, tmp_path, monkeypatch
    ):
        _write_movie_sheet(tmp_path, YT_STEM)
        self._asr(tmp_path, n_words=30)  # the cue route never reads the third source

        _, (_path, stage) = self._prepare(
            tmp_path, monkeypatch, lr.custom_plan(_job(tmp_path, YT_STEM, None))
        )

        assert stage._seed == {"lyrics_origin": "movie_srt"}


class TestPrepareRegenJob:
    GENIUS_BUNDLE = {
        "lyrics": {
            "origin": "genius",
            "lines": ["hello", "world"],
            "genius": {"id": 9, "title": "H", "artist": "W"},
        },
        "media_duration_s": 200.0,
    }

    def _regen(self, tmp_path, plan, *, reset=False, bundle=None):
        _touch_video(tmp_path, YT_STEM)
        job = _job(tmp_path, YT_STEM, bundle)
        job.plan = plan
        return lr.RegenJob(song=job, reset=reset, label="Repair")

    def _prepare(self, regen, tmp_path, genius=None):
        lyrics_dir = tmp_path / "work"
        lyrics_dir.mkdir(exist_ok=True)
        return lr.prepare_regen_job(regen, genius or MagicMock(), PipelineConfig(), lyrics_dir)

    def test_reset_wipes_outputs_but_keeps_captions_and_lrc(self, tmp_path):
        regen = self._regen(tmp_path, lr.Plan(kind="transcribe"), reset=True)
        subs = tmp_path / "subtitles"
        subs.mkdir()
        asr = subs / f"{YT_STEM}{ASR_JSON3_SUFFIX}"
        asr.write_text("{}", encoding="utf-8")
        (subs / f"{YT_STEM}.srt").write_text("old", encoding="utf-8")
        lyrics = tmp_path / "lyrics"
        lyrics.mkdir()
        lrc = lyrics / f"{YT_STEM}.lrc"
        lrc.write_text("[00:01.00]hi\n", encoding="utf-8")
        (lyrics / f"{YT_STEM}.txt").write_text("old", encoding="utf-8")

        self._prepare(regen, tmp_path)

        assert asr.exists() and lrc.exists()
        assert not (subs / f"{YT_STEM}.srt").exists()
        assert not (lyrics / f"{YT_STEM}.txt").exists()

    def test_a_reset_replays_the_custom_sheet_it_kept(self, tmp_path):
        sheet = _write_sheet(tmp_path, YT_STEM, "my own words\n")
        _touch_video(tmp_path, YT_STEM)
        job = _job(tmp_path, YT_STEM, None)
        job.plan = lr.resolve_plan(job, reset=True)
        regen = lr.RegenJob(song=job, reset=True, label="Reset")

        lyrics_path, stage = self._prepare(regen, tmp_path)

        assert lyrics_path == sheet
        assert sheet.read_text(encoding="utf-8") == "my own words\n"
        assert stage._seed["lyrics_origin"] == "custom"

    def test_a_reset_replays_the_movie_sheet_it_kept(self, tmp_path):
        sheet = _write_movie_sheet(tmp_path, YT_STEM)
        _touch_video(tmp_path, YT_STEM)
        job = _job(tmp_path, YT_STEM, None)
        job.plan = lr.resolve_plan(job, reset=True)
        regen = lr.RegenJob(song=job, reset=True, label="Reset")

        lyrics_path, stage = self._prepare(regen, tmp_path)

        assert lyrics_path == sheet
        assert sheet.read_text(encoding="utf-8") == MOVIE_SRT
        assert stage._seed["lyrics_origin"] == "movie_srt"

    def test_no_reset_leaves_the_outputs(self, tmp_path):
        regen = self._regen(tmp_path, lr.Plan(kind="transcribe"))
        subs = tmp_path / "subtitles"
        subs.mkdir()
        srt = subs / f"{YT_STEM}.srt"
        srt.write_text("old", encoding="utf-8")

        self._prepare(regen, tmp_path)

        assert srt.exists()

    def test_a_file_in_use_becomes_a_regen_error_and_nothing_else_runs(self, tmp_path, monkeypatch):
        regen = self._regen(tmp_path, lr.Plan(kind="sidecar", genius_id=1), reset=True)
        monkeypatch.setattr(
            lr, "clear_output_folders", MagicMock(side_effect=PermissionError("locked"))
        )
        write_choice = MagicMock()
        monkeypatch.setattr(lr, "write_choice", write_choice)

        with pytest.raises(lr.RegenError, match="in use.*Close the player and retry"):
            self._prepare(regen, tmp_path)

        write_choice.assert_not_called()

    def test_a_genius_pick_genius_does_not_return_fails_before_anything_changes(
        self, tmp_path, monkeypatch
    ):
        regen = self._regen(tmp_path, lr.Plan(kind="sidecar", genius_id=1), reset=True)
        karaoke = tmp_path / "karaoke"
        karaoke.mkdir()
        ass = karaoke / f"{YT_STEM}.ass"
        ass.write_text("old", encoding="utf-8")
        lyrics = tmp_path / "lyrics"
        lyrics.mkdir()
        lrc = lyrics / f"{YT_STEM}.lrc"
        lrc.write_text("[lrclib_id:5]\n[00:01.00]hi\n", encoding="utf-8")
        clear = MagicMock()
        monkeypatch.setattr(lr, "clear_output_folders", clear)
        write_choice = MagicMock()  # a regression must not write a real sidecar
        monkeypatch.setattr(lr, "write_choice", write_choice)
        genius = MagicMock()
        genius.fetch_song.side_effect = lr.GeniusUnavailable("503")

        with pytest.raises(lr.RegenError, match="Genius didn't return this song's lyrics, so"):
            self._prepare(regen, tmp_path, genius)

        genius.fetch_song.assert_called_once_with(1)
        clear.assert_not_called()
        write_choice.assert_not_called()
        assert ass.read_text(encoding="utf-8") == "old"
        assert lrc.read_text(encoding="utf-8") == "[lrclib_id:5]\n[00:01.00]hi\n"

    def test_a_genius_pick_genius_returns_prepares_as_before(self, tmp_path, monkeypatch):
        regen = self._regen(tmp_path, lr.Plan(kind="sidecar", genius_id=1), reset=True)
        write_choice = MagicMock()
        monkeypatch.setattr(lr, "write_choice", write_choice)
        genius = MagicMock()

        lyrics_path, stage = self._prepare(regen, tmp_path, genius)

        genius.fetch_song.assert_called_once_with(1)
        write_choice.assert_called_once_with("dQw4w9WgXcQ", {"genius_id": 1})
        assert lyrics_path is None
        assert isinstance(stage, lr.LyricsFetchStage)

    def test_a_plan_of_another_kind_does_not_ask_genius(self, tmp_path):
        genius = MagicMock()

        self._prepare(self._regen(tmp_path, lr.Plan(kind="transcribe")), tmp_path, genius)

        genius.fetch_song.assert_not_called()

    def test_a_fetch_plan_that_passes_goes_on_as_the_caption(self, tmp_path, monkeypatch):
        regen = self._regen(tmp_path, lr.fetch_or_prompt_plan(tmp_path / f"{YT_STEM}.mp4"))
        srt = _make_srt(tmp_path, YT_STEM, n_words=60)

        def fetch(job):
            job.plan = lr.Plan(kind="seed", lyrics_path=srt, seed={"lyrics_origin": "srt"})

        monkeypatch.setattr(lr, "fetch_caption", fetch)

        lyrics_path, stage = self._prepare(regen, tmp_path)

        assert lyrics_path == srt
        assert isinstance(stage, lr.SeedArtifactsStage)

    def test_a_fetch_plan_that_fails_the_gate_raises_a_regen_error(self, tmp_path, monkeypatch):
        regen = self._regen(tmp_path, lr.fetch_or_prompt_plan(tmp_path / f"{YT_STEM}.mp4"))

        def fetch(job):
            job.plan = job.plan.fallback

        monkeypatch.setattr(lr, "fetch_caption", fetch)
        prepare_lyrics = MagicMock()
        monkeypatch.setattr(lr, "prepare_lyrics", prepare_lyrics)

        with pytest.raises(
            lr.RegenError,
            match="No usable YouTube caption: none could be downloaded, or it is too short.*"
            "Try again later, or pick lyrics with Repair lyrics on Song Info",
        ):
            self._prepare(regen, tmp_path)

        prepare_lyrics.assert_not_called()

    def test_a_failed_fetch_leaves_the_job_ready_to_retry(self, tmp_path, monkeypatch):
        fetch_plan = lr.fetch_or_prompt_plan(tmp_path / f"{YT_STEM}.mp4")
        regen = self._regen(tmp_path, fetch_plan)
        monkeypatch.setattr(
            lr, "fetch_caption", lambda job: setattr(job, "plan", job.plan.fallback)
        )

        with pytest.raises(lr.RegenError):
            self._prepare(regen, tmp_path)

        assert regen.song.plan is fetch_plan

    def _real_fetch(self, tmp_path, monkeypatch):
        """The real ``fetch_caption`` over a stubbed download; returns the download mock."""
        monkeypatch.setattr(lr, "probe_duration", lambda p: None)  # skip the wpm gate
        srt = tmp_path / "subtitles" / f"{YT_STEM}.en.srt"

        def download(url, dest, stem):
            Path(dest).mkdir(parents=True, exist_ok=True)
            words = " ".join(["la"] * 60)
            srt.write_text(f"1\n00:00:01,000 --> 00:00:04,000\n{words}\n", encoding="utf-8")
            return str(srt)

        mock = MagicMock(side_effect=download)
        monkeypatch.setattr(lr, "download_manual_en_subs", mock)
        return mock

    def test_the_queued_job_keeps_its_fetch_plan_after_a_fetch(self, tmp_path, monkeypatch):
        fetch_plan = lr.fetch_or_prompt_plan(tmp_path / f"{YT_STEM}.mp4")
        regen = self._regen(tmp_path, fetch_plan, reset=True)
        self._real_fetch(tmp_path, monkeypatch)

        lyrics_path, _ = self._prepare(regen, tmp_path)

        assert lyrics_path == tmp_path / "subtitles" / f"{YT_STEM}.srt"
        assert regen.song.plan is fetch_plan

    def test_preparing_the_same_job_again_wipes_and_fetches_again(self, tmp_path, monkeypatch):
        fetch_plan = lr.fetch_or_prompt_plan(tmp_path / f"{YT_STEM}.mp4")
        regen = self._regen(tmp_path, fetch_plan, reset=True)
        download = self._real_fetch(tmp_path, monkeypatch)

        first, _ = self._prepare(regen, tmp_path)
        assert first.exists()
        # A retry: the reset wipe deletes the .srt the first run fetched.
        second, _ = self._prepare(regen, tmp_path)

        assert download.call_count == 2
        assert second.exists()

    def test_a_reused_genius_pick_backfills_the_lrc(self, tmp_path, monkeypatch):
        job = _job(tmp_path, YT_STEM, self.GENIUS_BUNDLE)
        plan = lr.reuse_plan(job)
        regen = self._regen(tmp_path, plan, bundle=self.GENIUS_BUNDLE)
        ensure = MagicMock(return_value=None)
        monkeypatch.setattr(lr.lrclib, "ensure_lrc", ensure)

        lyrics_path, stage = self._prepare(regen, tmp_path)

        ensure.assert_called_once_with(regen.song.song_path, "H", "W", ["hello", "world"], 200.0)
        assert lyrics_path.read_text(encoding="utf-8") == "hello\n\nworld"
        assert isinstance(stage, lr.SeedArtifactsStage)

    def test_a_reused_caption_does_not_backfill(self, tmp_path, monkeypatch):
        srt = _make_srt(tmp_path, YT_STEM, n_words=60)
        plan = lr.Plan(kind="seed", lyrics_path=srt, seed={"lyrics_origin": "srt"})
        regen = self._regen(tmp_path, plan)
        ensure = MagicMock()
        monkeypatch.setattr(lr.lrclib, "ensure_lrc", ensure)

        self._prepare(regen, tmp_path)

        ensure.assert_not_called()

    def test_the_lrclib_choice_is_applied(self, tmp_path, monkeypatch):
        plan = lr.Plan(kind="sidecar", genius_id=9, lrclib_skip=True)
        regen = self._regen(tmp_path, plan)
        monkeypatch.setattr(lr, "write_choice", MagicMock())

        self._prepare(regen, tmp_path)

        assert lr.lrclib.is_skip_marker(tmp_path / "lyrics" / f"{YT_STEM}.lrc")

    def test_a_transcribe_plan_has_no_lyrics_and_no_stage(self, tmp_path):
        regen = self._regen(tmp_path, lr.Plan(kind="transcribe"))

        assert self._prepare(regen, tmp_path) == (None, None)


class TestPutBackLyricFiles:
    def test_it_restores_a_skip_marker_the_run_deleted(self, tmp_path):
        song = tmp_path / f"{YT_STEM}.mp4"
        lrc = lr.lrclib.lrc_path(song)
        lr.lrclib.write_skip_marker(lrc)
        snapshot = lr.snapshot_lyric_files(song)
        lrc.unlink()

        lr.put_back_lyric_files(snapshot)

        assert lr.lrclib.is_skip_marker(lrc)

    def test_it_restores_a_sheet_the_run_deleted(self, tmp_path):
        song = _touch_video(tmp_path, YT_STEM)
        sheet = _write_sheet(tmp_path, YT_STEM, "my own words\n")
        snapshot = lr.snapshot_lyric_files(song)
        sheet.unlink()  # a repair to another source removed it

        lr.put_back_lyric_files(snapshot)

        assert sheet.read_text(encoding="utf-8") == "my own words\n"

    def test_it_restores_a_movie_sheet_a_typed_one_replaced(self, tmp_path):
        song = _touch_video(tmp_path, YT_STEM)
        movie = _write_movie_sheet(tmp_path, YT_STEM)
        snapshot = lr.snapshot_lyric_files(song)
        movie.unlink()  # saving a typed sheet removed it
        typed = _write_sheet(tmp_path, YT_STEM, "typed in the repair box\n")

        lr.put_back_lyric_files(snapshot)

        assert movie.read_text(encoding="utf-8") == MOVIE_SRT
        assert not typed.exists()

    def test_it_restores_a_sheet_the_run_overwrote(self, tmp_path):
        song = _touch_video(tmp_path, YT_STEM)
        sheet = _write_sheet(tmp_path, YT_STEM, "my own words\n")
        snapshot = lr.snapshot_lyric_files(song)
        sheet.write_text("typed in the repair box\n", encoding="utf-8")

        lr.put_back_lyric_files(snapshot)

        assert sheet.read_text(encoding="utf-8") == "my own words\n"

    def test_it_removes_a_sheet_that_did_not_exist_before(self, tmp_path):
        song = _touch_video(tmp_path, YT_STEM)
        snapshot = lr.snapshot_lyric_files(song)
        sheet = _write_sheet(tmp_path, YT_STEM)

        lr.put_back_lyric_files(snapshot)

        assert not sheet.exists()

    def test_a_failed_restore_is_logged_and_does_not_raise(self, tmp_path, monkeypatch, caplog):
        song = _touch_video(tmp_path, YT_STEM)
        snapshot = lr.snapshot_lyric_files(song)
        monkeypatch.setattr(
            lr.lrclib, "restore_file", MagicMock(side_effect=PermissionError("locked"))
        )

        lr.put_back_lyric_files(snapshot)

        assert "Could not put back" in caplog.text

    def test_one_file_that_cannot_be_restored_does_not_stop_the_other(self, tmp_path, monkeypatch):
        song = _touch_video(tmp_path, YT_STEM)
        sheet = _write_sheet(tmp_path, YT_STEM, "my own words\n")
        snapshot = lr.snapshot_lyric_files(song)
        sheet.write_text("changed\n", encoding="utf-8")
        real_restore = lr.lrclib.restore_file

        def restore(path, text):
            if path.suffix == ".lrc":
                raise PermissionError("locked")
            real_restore(path, text)

        monkeypatch.setattr(lr.lrclib, "restore_file", restore)

        lr.put_back_lyric_files(snapshot)

        assert sheet.read_text(encoding="utf-8") == "my own words\n"


class TestFinishRegenJob:
    """The run says whether it transcribed (``lyric_method``); only then is the
    old bundle stale, because a transcribe run writes no bundle."""

    def _song_with_bundle(self, tmp_path):
        song = _touch_video(tmp_path, YT_STEM)
        _write_bundle(tmp_path, YT_STEM, {"schema_version": 10})
        return song, tmp_path / "alignment_debug" / f"{YT_STEM}.json"

    def test_a_run_that_transcribed_removes_the_old_bundle(self, tmp_path):
        song, bundle = self._song_with_bundle(tmp_path)

        lr.finish_regen_job(song, "transcribe")

        assert not bundle.exists()

    def test_a_run_that_transcribed_without_a_bundle_is_fine(self, tmp_path):
        song, bundle = self._song_with_bundle(tmp_path)
        bundle.unlink()

        lr.finish_regen_job(song, "transcribe")  # does not raise

    def test_a_run_with_lyrics_or_no_report_leaves_the_bundle(self, tmp_path):
        song, bundle = self._song_with_bundle(tmp_path)

        for method in ("genius+joint", "srt+cue_align", None):
            lr.finish_regen_job(song, method)

            assert bundle.exists()
