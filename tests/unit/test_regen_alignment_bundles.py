"""Unit tests for scripts/regen_alignment_bundles.py — selection + planning.

Only the pure functions are exercised here (scan/staleness, lyric-plan
resolution and the caption-fetch step); driving the pipeline is covered by the
stage tests.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from pikaraoke.lib.alignment_capture import SCHEMA_VERSION
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
    (subs / f"Song{regen.ASR_JSON3_SUFFIX}").write_text("{}", encoding="utf-8")
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


class TestScanFolderSelection:
    def test_selected_current_song_included_unselected_stale_excluded(self, tmp_path):
        _touch_video(tmp_path, "current")
        _touch_video(tmp_path, "stale")
        _write_bundle(tmp_path, "current", {"schema_version": SCHEMA_VERSION})
        _write_bundle(tmp_path, "stale", {"schema_version": SCHEMA_VERSION - 1})

        jobs = regen.scan_folder(tmp_path, include_all=False, songs=[tmp_path / "current.mp4"])

        assert [j.song_path.stem for j in jobs] == ["current"]
        assert jobs[0].stale_reason == "selected"


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


class TestAdoptCaption:
    def _fetch_job(self, tmp_path, bundle=None):
        job = _job(tmp_path, YT_STEM, bundle)
        job.plan = regen.resolve_plan(job, reset=False)
        assert job.plan.kind == "fetch"
        return job

    def test_sparse_caption_deleted_and_falls_back(self, tmp_path):
        job = self._fetch_job(tmp_path, _gap_bundle(media_duration_s=60.0))
        fallback = job.plan.fallback
        srt = _make_srt(tmp_path, f"{YT_STEM}.en", n_words=3)  # 3 wpm over 60s

        regen.adopt_caption(job, srt)

        assert job.plan is fallback
        assert not srt.exists()

    def test_dense_caption_already_at_stem_srt_kept_and_seeded(self, tmp_path):
        job = self._fetch_job(tmp_path, _gap_bundle(media_duration_s=60.0))
        # Already at the playback-matched name (what _find_local_srt hands
        # add_songs' handoff after the download manager's own move) -- no
        # os.replace needed, and the file must survive untouched.
        srt = _make_srt(tmp_path, YT_STEM, n_words=60)  # 60 wpm over 60s

        regen.adopt_caption(job, srt)

        assert _is_srt_plan(job.plan)
        assert job.plan.lyrics_path == srt
        assert srt.exists()


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
# backup_text_folders — scoped backup for --song
# ---------------------------------------------------------------------------


class TestBackupTextFoldersScoped:
    def test_copies_only_selected_songs_files(self, tmp_path):
        _scoped_library(tmp_path)

        backup = regen.backup_text_folders(tmp_path, stems=["Song"])

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

        backup = regen.backup_text_folders(tmp_path)

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
        regen.clear_output_folders(tmp_path)
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
        asr = subs / f"{YT_STEM}{regen.ASR_JSON3_SUFFIX}"
        asr.write_text("{}", encoding="utf-8")
        (subs / f"{YT_STEM}.srt").write_text("generated", encoding="utf-8")
        (subs / f"{YT_STEM}.en.srt").write_text("caption", encoding="utf-8")
        regen.clear_output_folders(tmp_path)
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
        regen.clear_output_folders(tmp_path)
        assert lrc.exists()
        assert not (lyrics / f"{YT_STEM}.txt").exists()

    def test_missing_folders_is_noop(self, tmp_path):
        regen.clear_output_folders(tmp_path)  # does not raise


class TestClearOutputFoldersScoped:
    def test_removes_only_selected_songs_regenerable_files(self, tmp_path):
        _scoped_library(tmp_path)

        regen.clear_output_folders(tmp_path, stems=["Song"])

        # Selected song's regenerable output is gone.
        assert not (tmp_path / "subtitles" / "Song.srt").exists()
        assert not (tmp_path / "karaoke" / "Song.ass").exists()
        assert not (tmp_path / "lyrics" / "Song.txt").exists()
        # Non-regenerable inputs for the selected song survive.
        assert (tmp_path / "subtitles" / f"Song{regen.ASR_JSON3_SUFFIX}").exists()
        assert (tmp_path / "lyrics" / "Song.lrc").exists()
        # The longer-stem sibling and every other song's files are untouched.
        assert (tmp_path / "subtitles" / "Song.live.srt").exists()
        assert (tmp_path / "subtitles" / "Other.srt").exists()
        assert (tmp_path / "karaoke" / "Other.ass").exists()
        assert (tmp_path / "lyrics" / "Other.txt").exists()
        # Never a whole-folder wipe: the folders themselves survive.
        assert (tmp_path / "karaoke").is_dir()


# ---------------------------------------------------------------------------
# _owner / _remove — the shared ownership rule and the delete helper
# ---------------------------------------------------------------------------


class TestOwner:
    STEMS = {"Song", "Song.live", "Other"}

    def test_entry_belongs_to_its_stem(self):
        assert regen._owner("Song.srt", self.STEMS) == "Song"
        assert regen._owner("Song.srt.generated", self.STEMS) == "Song"
        assert regen._owner("Song", self.STEMS) == "Song"

    def test_longest_claiming_stem_wins(self):
        assert regen._owner("Song.live.srt", self.STEMS) == "Song.live"
        assert regen._owner("Song.live", self.STEMS) == "Song.live"

    def test_a_prefix_without_a_dot_is_not_a_claim(self):
        assert regen._owner("Songs.srt", self.STEMS) is None

    def test_unclaimed_entry_has_no_owner(self):
        assert regen._owner("Unknown.srt", self.STEMS) is None


class TestRemove:
    def test_removes_a_file_and_a_tree(self, tmp_path):
        file = tmp_path / "a.txt"
        file.write_text("x", encoding="utf-8")
        tree = tmp_path / "tree"
        (tree / "sub").mkdir(parents=True)
        (tree / "sub" / "b.txt").write_text("y", encoding="utf-8")

        regen._remove(file)
        regen._remove(tree)

        assert not file.exists()
        assert not tree.exists()

    def test_missing_path_is_a_noop(self, tmp_path):
        regen._remove(tmp_path / "nope")  # does not raise

    def test_tree_that_cannot_be_removed_is_warned_about(self, tmp_path, monkeypatch, caplog):
        tree = tmp_path / "tree"
        tree.mkdir()

        def boom(path):
            raise OSError("locked")

        monkeypatch.setattr(regen.shutil, "rmtree", boom)

        regen._remove(tree)  # does not raise

        assert "Could not fully remove" in caplog.text
        assert "locked" in caplog.text


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
        monkeypatch.setattr(regen.lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([job], PipelineConfig())

        mock.assert_called_once_with(job.song_path, "H", "W", ["hello", "world"], 200.0)

    def test_knob_off_skips_entirely(self, tmp_path, monkeypatch):
        job = self._reuse_job(tmp_path)
        mock = MagicMock()
        monkeypatch.setattr(regen.lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([job], PipelineConfig(lrclib_fill=False))

        mock.assert_not_called()

    def test_sidecar_plan_is_never_touched(self, tmp_path, monkeypatch):
        # A fresh Genius selection resolves via LyricsFetchStage when it
        # runs -- one call site per plan kind, no double-fetch here.
        job = _job(tmp_path, YT_STEM, None)
        job.plan = regen.Plan(kind="sidecar", genius_id=123, label="prompt -> genius")
        mock = MagicMock()
        monkeypatch.setattr(regen.lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([job], PipelineConfig())

        mock.assert_not_called()

    def test_srt_reuse_plan_is_never_touched(self, tmp_path, monkeypatch):
        _make_srt(tmp_path, "plain")
        job = _job(tmp_path, "plain", {"lyrics": {"origin": "srt"}})
        job.plan = regen.resolve_plan(job, reset=False)
        assert job.plan.seed.get("lyrics_origin") == "srt"
        mock = MagicMock()
        monkeypatch.setattr(regen.lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([job], PipelineConfig())

        mock.assert_not_called()

    def test_one_failing_song_does_not_abort_the_batch(self, tmp_path, monkeypatch):
        bad = self._reuse_job(tmp_path, stem="bad")
        good = self._reuse_job(tmp_path, stem="good")
        mock = MagicMock(side_effect=[OSError("disk full"), None])
        monkeypatch.setattr(regen.lrclib, "ensure_lrc", mock)

        regen.execute_lrclib_backfill([bad, good], PipelineConfig())

        assert mock.call_count == 2  # the OSError on "bad" didn't stop "good"


# ---------------------------------------------------------------------------
# _prepare_lyrics — LRCLIB resolve for the no-YouTube-id Genius fallback
# ---------------------------------------------------------------------------


class TestPrepareLyricsNoIdSidecar:
    """A Genius pick on a song without a YouTube id bypasses
    LyricsFetchStage (and its LRCLIB leg), so _prepare_lyrics resolves the
    variant itself — knob-gated and never fatal to the song's run."""

    def _run(self, tmp_path, monkeypatch, config, resolve_error=None):
        job = _job(tmp_path, "noid", None)
        job.plan = regen.Plan(kind="sidecar", genius_id=123, label="prompt -> genius")
        genius = MagicMock()
        genius.fetch_song.return_value = SimpleNamespace(title="H", artist="W", text="hello\nworld")
        ensure = MagicMock(return_value=None, side_effect=resolve_error)
        monkeypatch.setattr(regen.lrclib, "ensure_lrc", ensure)
        monkeypatch.setattr(regen, "probe_duration", MagicMock(return_value=200.0))
        lyrics_dir = tmp_path / "lyrics"
        lyrics_dir.mkdir(exist_ok=True)
        result = regen._prepare_lyrics(job, genius, lyrics_dir, config)
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
