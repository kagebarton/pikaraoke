"""Tests for the alignment-debug capture writer."""

import json

import numpy as np

from pikaraoke.lib.alignment_capture import write_bundle


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
