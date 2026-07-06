"""Unit tests for scripts/regen_alignment_bundles.py — selection + planning.

Only the pure functions are exercised here (scan/staleness, lyric-plan
resolution and the caption-fetch step); driving the pipeline is covered by the
stage tests.
"""

import importlib.util
import json
import sys
from pathlib import Path

from pikaraoke.lib.alignment_capture import SCHEMA_VERSION

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


def _write_bundle(folder: Path, stem: str, bundle: dict) -> None:
    debug = folder / "alignment_debug"
    debug.mkdir(exist_ok=True)
    (debug / f"{stem}.json").write_text(json.dumps(bundle), encoding="utf-8")


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


def _is_srt_plan(plan) -> bool:
    """True for a seed plan that feeds a local SRT as the lyric source."""
    return plan.kind == "seed" and plan.seed.get("lyrics_origin") == "srt"


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
        jobs = regen.scan_folder(tmp_path, include_all=False)
        by_stem = {j.song_path.stem: j.stale_reason for j in jobs}
        assert by_stem == {"missing": "missing", "stale": f"v{SCHEMA_VERSION - 1}"}

    def test_all_selects_everything(self, tmp_path):
        self._setup(tmp_path)
        jobs = regen.scan_folder(tmp_path, include_all=True)
        assert {j.song_path.stem for j in jobs} == {"current", "stale", "missing"}
        assert all(j.stale_reason == "all" for j in jobs)

    def test_corrupt_bundle_counts_as_missing(self, tmp_path):
        _touch_video(tmp_path, "broken")
        (tmp_path / "alignment_debug").mkdir()
        (tmp_path / "alignment_debug" / "broken.json").write_text("{not json", encoding="utf-8")
        jobs = regen.scan_folder(tmp_path, include_all=False)
        assert [j.stale_reason for j in jobs] == ["missing"]

    def test_ignores_non_video_files(self, tmp_path):
        (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
        jobs = regen.scan_folder(tmp_path, include_all=True)
        assert jobs == []


# ---------------------------------------------------------------------------
# resolve_plan (default) — reuse, else fetch/prompt
# ---------------------------------------------------------------------------


class TestResolvePlanDefault:
    def test_no_bundle_no_id_prompts(self, tmp_path):
        plan = regen.resolve_plan(_job(tmp_path, "plain", None), reset=False)
        assert plan.kind == "prompt"

    def test_no_bundle_with_id_fetches(self, tmp_path):
        plan = regen.resolve_plan(_job(tmp_path, YT_STEM, None), reset=False)
        assert plan.kind == "fetch"
        assert plan.fallback.kind == "prompt"

    def test_srt_origin_with_srt_on_disk_reuses(self, tmp_path):
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "s.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
        plan = regen.resolve_plan(_job(tmp_path, "s", {"lyrics": {"origin": "srt"}}), reset=False)
        assert plan.kind == "seed"
        assert plan.lyrics_path == subs / "s.srt"
        assert plan.seed == {"lyrics_origin": "srt"}

    def test_srt_origin_missing_srt_falls_through_to_fetch(self, tmp_path):
        plan = regen.resolve_plan(
            _job(tmp_path, YT_STEM, {"lyrics": {"origin": "srt"}}), reset=False
        )
        assert plan.kind == "fetch"

    def test_genius_with_ytasr_and_json3_on_disk_reuses(self, tmp_path):
        subs = tmp_path / "subtitles"
        subs.mkdir()
        asr_rel = f"subtitles/s{regen.ASR_JSON3_SUFFIX}"
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
        plan = regen.resolve_plan(_job(tmp_path, "s", bundle), reset=False)
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
                "ytasr": {"asr_file": f"subtitles/s{regen.ASR_JSON3_SUFFIX}", "n_words": 40},
            },
        }
        plan = regen.resolve_plan(_job(tmp_path, "s", bundle), reset=False)
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
        plan = regen.resolve_plan(_job(tmp_path, "s", bundle), reset=False)
        assert plan.kind == "seed"
        assert "ytasr" not in plan.seed
        assert plan.seed["genius"] == {"id": 9, "title": "H", "artist": "W"}

    def test_genius_without_identity_falls_through(self, tmp_path):
        # Lines but no recorded identity -> not reusable; a song with a YouTube
        # id falls through to fetch (then a prompt fills in the provenance).
        bundle = {"lyrics": {"origin": "genius", "lines": ["hello"]}}
        plan = regen.resolve_plan(_job(tmp_path, YT_STEM, bundle), reset=False)
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
        plan = regen.resolve_plan(_job(tmp_path, "plain", bundle), reset=False)
        assert plan.kind == "prompt"  # no YouTube id -> straight to prompt

    def test_unknown_origin_without_identity_falls_through(self, tmp_path):
        bundle = {"lyrics": {"origin": "unknown", "lines": ["a", "b"]}}
        plan = regen.resolve_plan(_job(tmp_path, "plain", bundle), reset=False)
        assert plan.kind == "prompt"

    def test_origin_without_lines_falls_through(self, tmp_path):
        bundle = {"lyrics": {"origin": "unknown"}}
        plan = regen.resolve_plan(_job(tmp_path, "plain", bundle), reset=False)
        assert plan.kind == "prompt"

    def test_falls_back_to_align_lines_when_no_lines(self, tmp_path):
        bundle = {
            "lyrics": {
                "origin": "genius",
                "align_lines": ["hello there"],
                "genius": {"id": 1, "title": "H", "artist": "W"},
            },
        }
        plan = regen.resolve_plan(_job(tmp_path, "s", bundle), reset=False)
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
        asr_rel = f"subtitles/{YT_STEM}{regen.ASR_JSON3_SUFFIX}"
        (tmp_path / asr_rel).write_text("{}", encoding="utf-8")
        bundle = {
            "lyrics": {
                "origin": "genius",
                "lines": ["hi"],
                "ytasr": {"asr_file": asr_rel, "n_words": 40},
                "genius": {"id": 9, "title": "H", "artist": "W"},
            },
        }
        plan = regen.resolve_plan(_job(tmp_path, YT_STEM, bundle), reset=True)
        assert plan.kind == "fetch"

    def test_reset_ignores_srt_origin(self, tmp_path):
        _make_srt(tmp_path, YT_STEM)
        plan = regen.resolve_plan(
            _job(tmp_path, YT_STEM, {"lyrics": {"origin": "srt"}}), reset=True
        )
        assert plan.kind == "fetch"

    def test_reset_no_id_prompts(self, tmp_path):
        plan = regen.resolve_plan(
            _job(tmp_path, "plain", {"lyrics": {"origin": "srt"}}), reset=True
        )
        assert plan.kind == "prompt"


# ---------------------------------------------------------------------------
# execute_fetches — download + length gate + resolve-or-revert
# ---------------------------------------------------------------------------


def _gap_bundle(media_duration_s: float | None = None) -> dict:
    """A bundle with no reusable lyric source (so the default plan is fetch)."""
    bundle: dict = {"lyrics": {"origin": "unknown"}}
    if media_duration_s is not None:
        bundle["media_duration_s"] = media_duration_s
    return bundle


class TestExecuteFetches:
    def _fetch_job(self, tmp_path, bundle=None):
        job = _job(tmp_path, YT_STEM, bundle)
        job.plan = regen.resolve_plan(job, reset=False)
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
        monkeypatch.setattr(regen, "probe_duration", lambda p: None)  # skip wpm gate
        job = self._fetch_job(tmp_path)
        srt = tmp_path / "subtitles" / f"{YT_STEM}.en.srt"
        monkeypatch.setattr(regen, "download_manual_en_subs", self._writer(srt, 60))
        regen.execute_fetches([job])
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
        monkeypatch.setattr(regen, "download_manual_en_subs", lambda url, dest, stem: None)
        regen.execute_fetches([job])
        assert job.plan is fallback
        assert job.plan.kind == "prompt"

    def test_too_sparse_discarded_and_reverts(self, tmp_path, monkeypatch):
        job = self._fetch_job(tmp_path, _gap_bundle(media_duration_s=60.0))
        fallback = job.plan.fallback
        srt = tmp_path / "subtitles" / f"{YT_STEM}.en.srt"
        monkeypatch.setattr(regen, "download_manual_en_subs", self._writer(srt, 3))  # 3 wpm
        regen.execute_fetches([job])
        assert job.plan is fallback
        assert not srt.exists()

    def test_dense_caption_passes_gate(self, tmp_path, monkeypatch):
        job = self._fetch_job(tmp_path, _gap_bundle(media_duration_s=60.0))
        srt = tmp_path / "subtitles" / f"{YT_STEM}.en.srt"
        monkeypatch.setattr(regen, "download_manual_en_subs", self._writer(srt, 60))  # 60 wpm
        regen.execute_fetches([job])
        assert _is_srt_plan(job.plan)
        assert (tmp_path / "subtitles" / f"{YT_STEM}.srt").exists()
        assert not srt.exists()


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
        regen.clear_output_folders(tmp_path)
        assert not (tmp_path / "subtitles" / "x").exists()
        assert not (tmp_path / "karaoke").exists()
        assert not (tmp_path / "lyrics").exists()
        assert (tmp_path / "vocal" / f"{YT_STEM}---vocal.m4a").exists()

    def test_preserves_asr_captions_wipes_the_rest(self, tmp_path):
        # ASR captions are non-regenerable download artifacts — they must
        # survive the reset wipe, unlike generated SRTs and re-fetched captions.
        subs = tmp_path / "subtitles"
        subs.mkdir()
        asr = subs / f"{YT_STEM}{regen.ASR_JSON3_SUFFIX}"
        asr.write_text("{}", encoding="utf-8")
        (subs / f"{YT_STEM}.srt").write_text("generated", encoding="utf-8")
        (subs / f"{YT_STEM}.en.srt").write_text("caption", encoding="utf-8")
        regen.clear_output_folders(tmp_path)
        assert asr.exists()
        assert not (subs / f"{YT_STEM}.srt").exists()
        assert not (subs / f"{YT_STEM}.en.srt").exists()

    def test_missing_folders_is_noop(self, tmp_path):
        regen.clear_output_folders(tmp_path)  # does not raise
