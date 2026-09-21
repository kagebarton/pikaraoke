"""Unit tests for scripts/voicing_release_study.py — the Phase 7a voicing
trace and its window rebuild (plans/edge-snap-coverage-accuracy.md).
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

# scripts/ is not a package, and the study imports its sibling harnesses.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_spec = importlib.util.spec_from_file_location(
    "voicing_release_study", _SCRIPTS / "voicing_release_study.py"
)
study = importlib.util.module_from_spec(_spec)
sys.modules["voicing_release_study"] = study
_spec.loader.exec_module(study)

CLAIMED_END = 1.0
BOUND = 2.0


def _track(hz: float = 220.0, dur: float = 3.0):
    """A steady voiced track at ``hz``, one frame per 25 ms hop."""
    times = np.round(np.arange(int(round(dur / 0.025))) * 0.025, 6)
    return times, np.full(len(times), hz), np.ones(len(times), dtype=bool)


def _from(times: np.ndarray, t: float) -> np.ndarray:
    return times >= t - 1e-9


def test_steady_contour_runs_to_bound():
    times, f0, voiced = _track()
    res = study.trace_voicing(times, f0, voiced, CLAIMED_END, BOUND)
    assert res == {"category": "no_break", "anchor_f0": 220.0}


def test_sustained_jump_breaks_at_the_jump():
    # Another voice a major third up takes over at 1.3 s.
    times, f0, voiced = _track()
    f0[_from(times, 1.3)] = 220.0 * 2 ** (4 / 12)
    res = study.trace_voicing(times, f0, voiced, CLAIMED_END, BOUND)
    assert res["category"] == "break"
    assert res["break_t"] == pytest.approx(1.3, abs=0.01)
    assert res["kind"] == "jump"


def test_sustained_unvoiced_breaks_as_unvoiced():
    times, f0, voiced = _track()
    voiced[_from(times, 1.4)] = False
    f0[~voiced] = np.nan
    res = study.trace_voicing(times, f0, voiced, CLAIMED_END, BOUND)
    assert res["category"] == "break"
    assert res["break_t"] == pytest.approx(1.4, abs=0.01)
    assert res["kind"] == "unvoiced"


def test_short_dropout_is_not_a_break():
    # 5 unvoiced frames (0.125 s) inside the held note, then the same pitch.
    times, f0, voiced = _track()
    gap = _from(times, 1.3) & ~_from(times, 1.425)
    voiced[gap] = False
    f0[gap] = np.nan
    res = study.trace_voicing(times, f0, voiced, CLAIMED_END, BOUND)
    assert res["category"] == "no_break"


def test_glide_is_followed():
    # One semitone per frame for 6 frames: a sung glide, not a voice swap.
    times, f0, voiced = _track()
    start = int(np.flatnonzero(_from(times, 1.3))[0])
    for k in range(1, len(times) - start):
        f0[start + k] = 220.0 * 2 ** (min(k, 6) / 12)
    res = study.trace_voicing(times, f0, voiced, CLAIMED_END, BOUND)
    assert res["category"] == "no_break"


def test_no_voiced_frame_near_claimed_end_is_no_anchor():
    times, f0, voiced = _track()
    voiced[_from(times, 0.85)] = False
    res = study.trace_voicing(times, f0, voiced, CLAIMED_END, BOUND)
    assert res == {"category": "no_anchor"}


def test_break_starting_at_bound_is_no_break():
    times, f0, voiced = _track()
    f0[_from(times, BOUND)] = 330.0
    res = study.trace_voicing(times, f0, voiced, CLAIMED_END, BOUND)
    assert res["category"] == "no_break"


def _bundle(line1_end: float, extends: list[dict]) -> dict:
    return {
        "output_line_timings": [
            {"line_id": 0, "start": 10.0, "end": line1_end, "n_words": 4},
            {"line_id": 1, "start": None, "end": None, "n_words": 0},
            {"line_id": 2, "start": 14.1, "end": 16.0, "n_words": 3},
        ],
        "joint_stats": {"edge_snap": {"end": {"extends": extends}}},
    }


def test_to_bound_window_rebuilt_past_a_wordless_line():
    bundle = _bundle(
        14.0,
        [
            {"line_id": 0, "extend_s": 1.25, "to_bound": True},
            {"line_id": 2, "extend_s": 0.4, "to_bound": False},
        ],
    )
    (win,) = study.to_bound_windows(bundle)
    assert win["line_id"] == 0
    assert win["bound"] == 14.0
    assert win["claimed_end"] == pytest.approx(12.75)
    assert win["bound_ok"] is True


def test_bound_mismatch_is_flagged():
    bundle = _bundle(13.9, [{"line_id": 0, "extend_s": 1.0, "to_bound": True}])
    (win,) = study.to_bound_windows(bundle)
    assert win["bound_ok"] is False


@pytest.mark.parametrize(
    "delta,label",
    [(-0.1, "(-0.15,0]"), (-0.15, "(-0.5,-0.15]"), (-0.7, "(-1,-0.5]"), (-2.0, "<=-2")],
)
def test_delta_bins(delta, label):
    assert study.delta_bin(delta) == label
