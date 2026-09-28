"""Unit tests for scripts/backfill_artifacts.py — selection scoping.

Only ``scan_folder``'s selection behavior is exercised here; driving the
pipeline is covered by the stage tests.
"""

import importlib.util
import sys
from pathlib import Path

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
