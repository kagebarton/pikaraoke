"""Unit tests for scripts/replay_ytasr_third_source.py — recorded_summary's
E1 gated-fill exclusion (Deliverable 5, plans/lrclib-fill-production-wiring.md).
"""

import importlib.util
import sys
from pathlib import Path

# scripts/ is not a package — load the module straight from its file.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "replay_ytasr_third_source.py"
_spec = importlib.util.spec_from_file_location("replay_ytasr_third_source", _SCRIPT)
harness = importlib.util.module_from_spec(_spec)
sys.modules["replay_ytasr_third_source"] = harness
_spec.loader.exec_module(harness)


def _timing(line_id: int, start: float, end: float, n_words: int = 2) -> dict:
    return {"line_id": line_id, "start": start, "end": end, "n_words": n_words}


class TestRecordedSummaryExcludesFills:
    def test_no_joint_stats_key_is_unaffected(self):
        bundle = {"output_line_timings": [_timing(0, 0.0, 1.0)]}
        result = harness.recorded_summary(bundle)
        assert result["n_placed"] == 1
        assert result["n_excluded_fills"] == 0

    def test_joint_stats_without_lrclib_fill_key_is_unaffected(self):
        bundle = {
            "output_line_timings": [_timing(0, 0.0, 1.0)],
            "joint_stats": {"knobs": {}},
        }
        result = harness.recorded_summary(bundle)
        assert result["n_placed"] == 1
        assert result["n_excluded_fills"] == 0

    def test_filled_lines_are_excluded_from_every_stat(self):
        bundle = {
            "output_line_timings": [
                _timing(0, 0.0, 1.0),
                _timing(1, 1.0, 2.0),  # filled -- would otherwise overlap/crawl-count
                _timing(2, 5.0, 5.1, n_words=1),  # filled -- would otherwise be a crawl
            ],
            "joint_stats": {"lrclib_fill": {"filled_lids": [1, 2]}},
        }
        result = harness.recorded_summary(bundle)
        assert result["n_placed"] == 1
        assert result["n_excluded_fills"] == 2
        assert result["max_overlap"] == 0.0
        assert result["n_crawl"] == 0

    def test_zero_word_lines_still_dropped_independent_of_fills(self):
        bundle = {
            "output_line_timings": [_timing(0, 0.0, 1.0), _timing(1, 1.0, 2.0, n_words=0)],
            "joint_stats": {"lrclib_fill": {"filled_lids": []}},
        }
        result = harness.recorded_summary(bundle)
        assert result["n_placed"] == 1
        assert result["n_excluded_fills"] == 0
