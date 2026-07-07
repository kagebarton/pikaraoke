"""Unit tests for the zero-evidence vocal-energy veto."""

import numpy as np

from pikaraoke.lib.evidence_veto import veto_uncorroborated_lines
from pikaraoke.lib.onset_snap import HOP_S, MIN_REF_DB

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SUNG_DB = -28.0  # comfortably above MIN_REF_DB (-45)
SILENT_DB = -60.0  # below MIN_REF_DB


def _env(total_s: float, segments: list[tuple[float, float, float]]) -> np.ndarray:
    """dB envelope: silent everywhere except the given (t0, t1, level) spans."""
    env = np.full(int(total_s / HOP_S), SILENT_DB)
    for t0, t1, level in segments:
        env[int(t0 / HOP_S) : int(t1 / HOP_S)] = level
    return env


def _align_line(start: float, end: float, tm=0, ya=0.0, line_id=0) -> dict:
    return {
        "text": "a line",
        "line_id": line_id,
        "words": [{"word": "a", "start": start, "end": end}],
        "start": start,
        "end": end,
        "source": "align",
        "evidence": {"transcribe_match": tm, "ytasr_agreement": ya},
    }


# ---------------------------------------------------------------------------
# Veto decisions
# ---------------------------------------------------------------------------


def test_zero_evidence_over_silence_is_vetoed():
    env = _env(5.0, [])  # all silent
    obj = _align_line(1.0, 2.0)

    out, stats = veto_uncorroborated_lines([obj], env)

    assert out[0]["words"] == []
    assert out[0]["source"] == "veto"
    assert out[0]["start"] == 1.0 and out[0]["end"] == 2.0
    assert stats["n_zero_evidence"] == 1
    assert stats["n_vetoed"] == 1
    # Never mutate in place — the original object is untouched.
    assert obj["words"] and obj["source"] == "align"


def test_zero_evidence_over_energy_is_kept():
    env = _env(5.0, [(1.0, 2.0, SUNG_DB)])
    obj = _align_line(1.0, 2.0)

    out, stats = veto_uncorroborated_lines([obj], env)

    assert out[0] is obj
    assert stats["n_zero_evidence"] == 1
    assert stats["n_vetoed"] == 0
    assert stats["lines"][0]["vetoed"] is False


def test_transcribe_corroborated_over_silence_is_kept():
    env = _env(5.0, [])
    obj = _align_line(1.0, 2.0, tm=3)

    out, stats = veto_uncorroborated_lines([obj], env)

    assert out[0] is obj
    assert stats["n_zero_evidence"] == 0
    assert stats["n_vetoed"] == 0


def test_ytasr_corroborated_over_silence_is_kept():
    env = _env(5.0, [])
    obj = _align_line(1.0, 2.0, ya=0.5)

    out, stats = veto_uncorroborated_lines([obj], env)

    assert out[0] is obj
    assert stats["n_zero_evidence"] == 0


def test_missing_evidence_key_is_kept():
    # Interp/cue objects carry no evidence key; never a candidate.
    env = _env(5.0, [])
    obj = _align_line(1.0, 2.0)
    del obj["evidence"]

    out, stats = veto_uncorroborated_lines([obj], env)

    assert out[0] is obj
    assert stats["n_zero_evidence"] == 0


def test_line_past_envelope_end_is_kept():
    # An empty slice is not silence evidence — the line lies past the stem.
    env = _env(2.0, [])  # frames cover up to 2.0s
    obj = _align_line(3.0, 4.0)

    out, stats = veto_uncorroborated_lines([obj], env)

    assert out[0] is obj
    assert stats["n_zero_evidence"] == 1
    assert stats["n_vetoed"] == 0
    assert stats["lines"][0]["median_db"] is None


def test_stats_record_every_zero_evidence_line():
    env = _env(5.0, [(3.0, 4.0, SUNG_DB)])
    silent = _align_line(1.0, 2.0, line_id=0)
    sung = _align_line(3.0, 4.0, line_id=1)

    _, stats = veto_uncorroborated_lines([silent, sung], env)

    assert stats["n_zero_evidence"] == 2
    assert stats["n_vetoed"] == 1
    by_id = {entry["line_id"]: entry for entry in stats["lines"]}
    assert by_id[0]["vetoed"] is True
    assert by_id[1]["vetoed"] is False
    assert by_id[0]["median_db"] < MIN_REF_DB
    assert by_id[1]["median_db"] >= MIN_REF_DB
