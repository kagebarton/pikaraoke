"""Tests for the SRT timing prior (lib/srt_prior.py)."""

from pikaraoke.lib.srt_prior import apply_srt_prior, cue_spans_from_srt

KNOBS = dict(margin_s=0.3, max_edit_ratio=0.75)

# Four sheet-unique 4-token lines: each qualifies as a trusted anchor
# when placed and echoed by transcribe (the windowed re-align criteria).
ANCHOR_TEXTS = [
    "alpha bravo charlie delta",
    "echo foxtrot golf hotel",
    "india juliet kilo lima",
    "mike november oscar papa",
]


def _word(text: str, start: float, end: float) -> dict:
    return {"word": text, "start": start, "end": end}


def _placed_obj(lid: int, text: str, t0: float, source: str = "align") -> dict:
    words = [_word(tok, t0 + 0.5 * i, t0 + 0.5 * i + 0.4) for i, tok in enumerate(text.split())]
    return {
        "line_id": lid,
        "text": text,
        "words": words,
        "start": words[0]["start"],
        "end": words[-1]["end"],
        "source": source,
    }


def _interp_obj(lid: int, t0: float, t1: float) -> dict:
    return {"line_id": lid, "text": "", "words": [], "start": t0, "end": t1, "source": "interp"}


def _anchor_song(lead_s: float = 1.5):
    """Four anchor lines placed at 10/20/30/40 s, transcribe echoing
    each, cues leading the audio by ``lead_s``."""
    objs = [_placed_obj(i, text, 10.0 * (i + 1)) for i, text in enumerate(ANCHOR_TEXTS)]
    transcribe = [w for o in objs for w in o["words"]]
    cues = {i: (10.0 * (i + 1) - lead_s, 10.0 * (i + 1) - lead_s + 2.0) for i in range(4)}
    return list(ANCHOR_TEXTS), objs, transcribe, cues


class TestOffsetFit:
    def test_consistent_anchors_fit_offset_and_change_nothing(self):
        lines, objs, transcribe, cues = _anchor_song(lead_s=1.5)
        out, stats = apply_srt_prior(objs, transcribe, lines, lines, cues, **KNOBS)
        assert stats["bailed"] is None
        assert stats["offset_s"] == 1.5
        assert stats["mad_s"] == 0.0
        assert stats["n_anchors_fit"] == 4
        assert stats["n_snapped"] == 0 and stats["n_filled"] == 0
        assert out == objs

    def test_bails_on_few_anchors(self):
        lines, objs, transcribe, cues = _anchor_song()
        del cues[3]  # only 3 anchors carry cues
        out, stats = apply_srt_prior(objs, transcribe, lines, lines, cues, **KNOBS)
        assert stats["bailed"] == "few_anchors"
        assert stats["n_anchors_fit"] == 3
        assert out is objs

    def test_bails_on_wide_residual_spread(self):
        lines, objs, transcribe, cues = _anchor_song()
        # Per-anchor leads 0 / 0.9 / 1.8 / 3.6 s: MAD 0.9 > 0.75.
        for i, lead in enumerate((0.0, 0.9, 1.8, 3.6)):
            t0 = 10.0 * (i + 1)
            cues[i] = (t0 - lead, t0 - lead + 2.0)
        out, stats = apply_srt_prior(objs, transcribe, lines, lines, cues, **KNOBS)
        assert stats["bailed"] == "wide_spread"
        assert out is objs


class TestSnapRepair:
    def test_gross_disagreement_snaps_to_cue_plus_offset(self):
        lines, objs, transcribe, cues = _anchor_song(lead_s=1.5)
        # Uncorroborated placed line 28.5 s from where its cue says it
        # belongs (wrong chorus instance).
        lines.append("quebec romeo sierra tango")
        objs.append(_placed_obj(4, lines[4], 70.0))
        cues[4] = (40.0, 42.0)
        out, stats = apply_srt_prior(objs, transcribe, lines, lines, cues, **KNOBS)
        assert stats["snapped_line_ids"] == [4]
        snapped = out[4]
        assert snapped["start"] == 41.5
        assert snapped["source"] == "srt"
        # Word spacing is preserved — the line shifts, it isn't rebuilt.
        deltas = [w["start"] - snapped["start"] for w in snapped["words"]]
        assert deltas == [0.0, 0.5, 1.0, 1.5]
        # The original object is untouched (copies only).
        assert objs[4]["start"] == 70.0

    def test_small_disagreement_keeps_audio_placement(self):
        lines, objs, transcribe, cues = _anchor_song(lead_s=1.5)
        lines.append("quebec romeo sierra tango")
        objs.append(_placed_obj(4, lines[4], 50.0))
        cues[4] = (47.0, 49.0)  # target 48.5, off by 1.5 s < threshold
        out, stats = apply_srt_prior(objs, transcribe, lines, lines, cues, **KNOBS)
        assert stats["n_snapped"] == 0
        assert out[4] is objs[4]

    def test_line_without_cue_is_never_touched(self):
        lines, objs, transcribe, cues = _anchor_song(lead_s=1.5)
        lines.append("quebec romeo sierra tango")
        objs.append(_placed_obj(4, lines[4], 70.0))  # no cue entry
        out, stats = apply_srt_prior(objs, transcribe, lines, lines, cues, **KNOBS)
        assert stats["n_snapped"] == 0 and stats["n_filled"] == 0
        assert out[4] is objs[4]


class TestCoverageFill:
    def test_unplaced_line_gains_even_paced_words(self):
        lines, objs, transcribe, cues = _anchor_song(lead_s=1.5)
        lines.append("quebec romeo sierra tango")
        objs.append(_interp_obj(4, 41.9, 50.0))
        cues[4] = (50.0, 52.0)
        out, stats = apply_srt_prior(objs, transcribe, lines, lines, cues, **KNOBS)
        assert stats["filled_line_ids"] == [4]
        fill = out[4]
        assert fill["source"] == "srt"
        assert fill["text"] == "quebec romeo sierra tango"
        assert fill["start"] == 51.5 and fill["end"] == 53.5
        assert [w["word"] for w in fill["words"]] == ["quebec", "romeo", "sierra", "tango"]
        assert fill["words"][1]["start"] == 52.0  # even pace over the cue span
        assert fill["words"][3]["end"] == 53.5

    def test_negative_lead_fill_clamps_to_zero(self):
        # Captions lag the audio by 3 s (offset -3); an early cue would
        # land before t=0 without the clamp.
        lines, objs, transcribe, cues = _anchor_song(lead_s=-3.0)
        lines.append("quebec romeo sierra tango")
        objs.append(_interp_obj(4, 0.0, 5.0))
        cues[4] = (1.0, 2.5)
        out, stats = apply_srt_prior(objs, transcribe, lines, lines, cues, **KNOBS)
        assert stats["filled_line_ids"] == [4]
        assert out[4]["start"] == 0.0
        assert all(w["start"] >= 0.0 for w in out[4]["words"])

    def test_tokenless_line_stays_unfilled(self):
        lines, objs, transcribe, cues = _anchor_song(lead_s=1.5)
        lines.append("")
        objs.append(_interp_obj(4, 41.9, 50.0))
        cues[4] = (50.0, 52.0)
        out, stats = apply_srt_prior(objs, transcribe, lines, lines, cues, **KNOBS)
        assert stats["n_filled"] == 0
        assert out[4] is objs[4]


class TestCueSpansFromSrt:
    def test_cleanup_and_spans_stay_parallel(self):
        srt_text = (
            "1\n00:00:01,000 --> 00:00:02,000\n(gentle music)\n"
            "\n2\n00:00:02,500 --> 00:00:04,000\n<i>♪ Hello\nworld ♪</i>\n"
        )
        texts, spans = cue_spans_from_srt(srt_text)
        assert texts == ["Hello world"]
        assert spans == [(2.5, 4.0)]
