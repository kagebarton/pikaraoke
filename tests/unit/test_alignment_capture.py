"""Tests for the alignment-debug capture writer."""

import json

import numpy as np

from pikaraoke.lib.alignment_capture import build_bundle, write_bundle


def test_write_bundle_coerces_numpy_scalars(tmp_path):
    """Word timings come off stable-ts as numpy, so derived stats carry
    np.bool_/np.float64. The writer must land native JSON, not crash."""
    song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
    bundle = {
        "schema_version": 7,
        "joint_stats": {
            "n_sections": np.int64(3),
            "offset_s": np.float64(0.42),
            "resectioned": np.bool_(True),
        },
        "output_line_timings": [{"start": np.float32(1.5), "end": np.float64(2.0)}],
        "words": np.array([0.1, 0.2]),
    }

    out = write_bundle(song_path, bundle)

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["joint_stats"]["resectioned"] is True
    assert loaded["joint_stats"]["n_sections"] == 3
    assert loaded["output_line_timings"][0]["start"] == 1.5
    assert loaded["words"] == [0.1, 0.2]


def test_build_bundle_keeps_cue_inputs_and_writes_numpy_words(tmp_path):
    """Cue-align runs keep the rescue's inputs; the raw aligner words carry numpy floats."""
    song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
    realigns = [
        {
            "line_id": 3,
            "w0": np.float64(5.25),
            "w1": 9.75,
            "words": [{"word": "a", "start": np.float64(6.0), "probability": np.float32(0.5)}],
        },
        {"line_id": 4, "w0": 10.0, "w1": 12.0, "words": None},
    ]
    kwargs = dict(
        song_stem="Song---dQw4w9WgXcQ",
        config_snapshot={},
        lyrics={},
        pipeline_decisions={},
        words=None,
        words_source=None,
        output_summary={},
        output_line_timings=[],
        ground_truth_refs={},
    )

    bundle = build_bundle(**kwargs, cue_inputs={"sections": [{"line_id": 0}], "realigns": realigns})
    loaded = json.loads(write_bundle(song_path, bundle).read_text(encoding="utf-8"))

    assert loaded["cue_inputs"]["sections"] == [{"line_id": 0}]
    assert loaded["cue_inputs"]["realigns"][0]["words"][0]["start"] == 6.0
    assert loaded["cue_inputs"]["realigns"][1]["words"] is None
    assert build_bundle(**kwargs)["cue_inputs"] is None
