"""Unit tests for pikaraoke.lib.lrclib_fill — gated LRCLIB fill (E1)."""

import numpy as np
import pytest

from pikaraoke.lib.lrclib_fill import (
    MAX_FILL_WORD_DUR_S,
    MIN_FILL_DUR_S,
    _collision,
    _eligibility,
    _energy_check,
    _fill_line,
    _theil_sen,
    apply_fills,
    plan_fills,
)
from pikaraoke.lib.onset_snap import MIN_REF_DB, SOFT_NEAR_DB

# ---------------------------------------------------------------------------
# _fill_line
# ---------------------------------------------------------------------------


class TestFillLine:
    def test_even_pacing(self):
        # 2 tokens over 1.0s (0.5s/word) -- under both caps, so uncapped.
        obj = _fill_line(3, "hello world", "hello world", 10.0, 11.0, "lrclib_fill")
        assert obj["line_id"] == 3
        assert obj["source"] == "lrclib_fill"
        assert obj["words"] == [
            {"word": "hello", "start": 10.0, "end": 10.5},
            {"word": "world", "start": 10.5, "end": 11.0},
        ]
        assert obj["start"] == 10.0
        assert obj["end"] == 11.0

    def test_multi_word_cap_uses_per_word_pace(self):
        # 2 tokens, wide span -> capped at MAX_FILL_WORD_DUR_S * 2 (1.4s),
        # which exceeds the MIN_FILL_DUR_S floor so the per-word math wins.
        obj = _fill_line(0, "hi there", "hi there", 0.0, 10.0, "lrclib_fill")
        assert obj["end"] == pytest.approx(MAX_FILL_WORD_DUR_S * 2)

    def test_single_word_cap_floors_at_min_fill_dur(self):
        # 1 token: the pure per-word cap would be MAX_FILL_WORD_DUR_S
        # (0.7s), but MIN_FILL_DUR_S (1.2s) raises the cap floor for a
        # low-token line so a capped single word stays readable.
        obj = _fill_line(0, "hi", "hi", 0.0, 10.0, "lrclib_fill")
        assert obj["end"] == pytest.approx(MIN_FILL_DUR_S)

    def test_t1_at_or_before_t0_floors_to_half_second(self):
        obj = _fill_line(0, "hi there", "hi there", 10.0, 10.0, "lrclib_fill")
        assert obj["start"] == 10.0
        assert obj["end"] == pytest.approx(10.5)

    def test_token_less_line_returns_none(self):
        assert _fill_line(0, "", "", 0.0, 1.0, "lrclib_fill") is None


# ---------------------------------------------------------------------------
# _theil_sen
# ---------------------------------------------------------------------------


class TestTheilSen:
    def test_recovers_known_slope_and_intercept(self):
        points = [(0.0, 1.0), (1.0, 3.0), (2.0, 5.0), (3.0, 7.0)]  # y = 2x + 1
        slope, intercept = _theil_sen(points)
        assert slope == pytest.approx(2.0)
        assert intercept == pytest.approx(1.0)

    def test_degenerate_x_returns_none(self):
        assert _theil_sen([(5.0, 1.0), (5.0, 2.0), (5.0, 3.0)]) is None


# ---------------------------------------------------------------------------
# _eligibility (GATE L2 adopted gate)
# ---------------------------------------------------------------------------


class TestEligibility:
    @staticmethod
    def _arm_a(bailed=None):
        return {"n_anchors_fit": 8, "bailed": bailed, "offset_s": 0.1, "mad_s": 0.1}

    @staticmethod
    def _slope(slope=1.0, bailed=None):
        d = {"n_anchors": 8, "bailed": bailed}
        if bailed is None:
            d.update(slope=slope, intercept=0.0, mad_s=0.1)
        return d

    def test_arm_a_bail_is_ineligible(self):
        eligible, reason = _eligibility(self._arm_a(bailed="wide_spread"), self._slope())
        assert (eligible, reason) == (False, "arm_a_bail")

    def test_slope_bail_is_ineligible(self):
        eligible, reason = _eligibility(self._arm_a(), self._slope(bailed="few_anchors"))
        assert (eligible, reason) == (False, "slope_bail")

    def test_slope_dev_above_threshold_is_ineligible(self):
        # Best Part Of Me's measured value (GATE L2).
        eligible, reason = _eligibility(self._arm_a(), self._slope(slope=1.021))
        assert (eligible, reason) == (False, "slope_dev")

    def test_slope_dev_within_threshold_is_eligible(self):
        # Domino's measured value (GATE L2 eyeballed-good worst case).
        eligible, reason = _eligibility(self._arm_a(), self._slope(slope=1.0051))
        assert eligible is True
        assert reason is None


# ---------------------------------------------------------------------------
# _collision
# ---------------------------------------------------------------------------


class TestCollision:
    def test_rejects_overlap_above_tolerance(self):
        assert _collision(10.0, 12.0, [(11.7, 13.0)]) is True  # 0.3s overlap > 0.2s tol

    def test_accepts_overlap_within_tolerance(self):
        assert _collision(10.0, 12.0, [(11.9, 13.0)]) is False  # 0.1s overlap <= 0.2s tol

    def test_no_placed_spans_never_collides(self):
        assert _collision(10.0, 12.0, []) is False


# ---------------------------------------------------------------------------
# _energy_check
# ---------------------------------------------------------------------------


class TestEnergyCheck:
    @staticmethod
    def _env(db_value, n=200):
        return np.full(n, db_value, dtype=np.float32)

    def test_pass_near_sung_level(self):
        env = self._env(-20.0)
        assert _energy_check(env, -20.0, 1.0, 2.0) == "PASS"

    def test_bail_below_soft_near_band(self):
        env = self._env(-20.0 - SOFT_NEAR_DB - 5.0)
        assert _energy_check(env, -20.0, 1.0, 2.0) == "bail"

    def test_void_on_none_env(self):
        assert _energy_check(None, -20.0, 1.0, 2.0) == "void"

    def test_void_on_none_ref(self):
        assert _energy_check(self._env(-20.0), None, 1.0, 2.0) == "void"

    def test_void_on_ref_below_min_ref_db(self):
        assert _energy_check(self._env(-20.0), MIN_REF_DB - 1.0, 1.0, 2.0) == "void"

    def test_void_on_empty_window_past_envelope_end(self):
        env = self._env(-20.0, n=10)
        assert _energy_check(env, -20.0, 100.0, 101.0) == "void"

    def test_void_on_empty_window_with_negative_t0(self):
        env = np.array([], dtype=np.float32)
        assert _energy_check(env, -20.0, -5.0, -4.0) == "void"

    def test_negative_t0_does_not_wrap_the_envelope(self):
        # Long envelope so an unclamped negative raw index would land on
        # real (wrong) data near the tail instead of raising or clamping.
        env = np.full(1000, -20.0, dtype=np.float32)
        env[800:840] = -100.0  # what an unclamped negative index would read
        # t0=-5.0s / HOP_S=0.025 -> raw index -200, a valid negative index
        # into this array without the max(0, ...) clamp.
        assert _energy_check(env, -20.0, -5.0, -4.0) == "PASS"


# ---------------------------------------------------------------------------
# apply_fills
# ---------------------------------------------------------------------------


class TestApplyFills:
    def test_splices_at_the_right_positions_and_preserves_order(self):
        line_objects = [
            {"line_id": 0, "words": [{"word": "a", "start": 0.0, "end": 0.5}]},
            {"line_id": 1, "words": []},
            {"line_id": 2, "words": [{"word": "c", "start": 2.0, "end": 2.5}]},
        ]
        fill = {
            "line_id": 1,
            "words": [{"word": "b", "start": 1.0, "end": 1.5}],
            "source": "lrclib_fill",
        }
        out = apply_fills(line_objects, [fill])
        assert [o["line_id"] for o in out] == [0, 1, 2]
        assert out[1] is fill
        assert out[0] is line_objects[0]
        assert out[2] is line_objects[2]

    def test_skips_a_lid_whose_words_became_non_empty(self):
        # Simulates a line the veto ran on between planning and splice --
        # not actually reachable for a fill candidate, but the guard must
        # hold regardless.
        line_objects = [{"line_id": 0, "words": [{"word": "a", "start": 0.0, "end": 0.5}]}]
        fill = {"line_id": 0, "words": [{"word": "b", "start": 1.0, "end": 1.5}]}
        out = apply_fills(line_objects, [fill])
        assert out[0] is line_objects[0]

    def test_leaves_non_candidates_untouched(self):
        line_objects = [{"line_id": 0, "words": []}]
        out = apply_fills(line_objects, [])
        assert out == line_objects


# ---------------------------------------------------------------------------
# plan_fills — orchestration
# ---------------------------------------------------------------------------


def _lrc(stamps_and_texts: list[tuple[float, str]]) -> str:
    lines = []
    for t, text in stamps_and_texts:
        m, s = divmod(t, 60.0)
        lines.append(f"[{int(m):02d}:{s:05.2f}]{text}")
    return "\n".join(lines)


def _anchor_lines(cue_start: float, placed_start: float):
    """One anchor line: 4 unique tokens, transcribe-corroborated, with a
    cue at ``cue_start`` and a matcher placement at ``placed_start``."""
    words = [
        "w" + str(cue_start) + "a",
        "w" + str(cue_start) + "b",
        "w" + str(cue_start) + "c",
        "w" + str(cue_start) + "d",
    ]
    text = " ".join(words)
    line_words = [
        {"word": w, "start": placed_start + i * 0.3, "end": placed_start + i * 0.3 + 0.25}
        for i, w in enumerate(words)
    ]
    return text, line_words


class TestPlanFillsHappyPath:
    """5 well-corroborated anchors (slope exactly 1.0, offset -1.0) plus one
    matcher-unplaced line whose cue lands, after the offset, clear of every
    placed span and inside a sung-energy region."""

    ANCHOR_CUES = [10.0, 20.0, 30.0, 40.0, 50.0]
    OFFSET = -1.0
    CANDIDATE_CUE = 60.0

    def _build(self):
        lyrics_lines = []
        align_lines = []
        line_objects = []
        transcribe_words = []
        lrc_stamps = []

        for i, cue in enumerate(self.ANCHOR_CUES):
            text, words = _anchor_lines(cue, cue + self.OFFSET)
            lyrics_lines.append(text)
            align_lines.append(text)
            line_objects.append(
                {
                    "line_id": i,
                    "words": words,
                    "start": words[0]["start"],
                    "end": words[-1]["end"],
                    "source": "align",
                }
            )
            transcribe_words.extend(words)
            lrc_stamps.append((cue, text))

        candidate_lid = len(self.ANCHOR_CUES)
        candidate_text = "uniform victor whiskey xray"
        lyrics_lines.append(candidate_text)
        align_lines.append(candidate_text)
        line_objects.append(
            {"line_id": candidate_lid, "words": [], "start": None, "end": None, "source": "absent"}
        )
        lrc_stamps.append((self.CANDIDATE_CUE, candidate_text))

        synced_text = _lrc(lrc_stamps)
        env = np.full(3000, -20.0, dtype=np.float32)  # constant sung level throughout
        return (
            line_objects,
            lyrics_lines,
            align_lines,
            transcribe_words,
            synced_text,
            env,
            candidate_lid,
        )

    def test_eligible_song_fills_the_unplaced_line(self):
        (
            line_objects,
            lyrics_lines,
            align_lines,
            transcribe_words,
            synced_text,
            env,
            candidate_lid,
        ) = self._build()
        fills, stats = plan_fills(
            line_objects,
            lyrics_lines,
            align_lines,
            transcribe_words,
            synced_text,
            env,
            margin_s=0.3,
            max_edit_ratio=0.75,
        )
        assert stats["eligible"] is True
        assert stats["reason"] is None
        assert stats["arm_a"]["bailed"] is None
        assert stats["slope_fit"]["slope"] == pytest.approx(1.0)
        assert stats["filled_lids"] == [candidate_lid]
        assert len(fills) == 1
        fill = fills[0]
        assert fill["line_id"] == candidate_lid
        assert fill["source"] == "lrclib_fill"
        expected_t0 = self.CANDIDATE_CUE + self.OFFSET
        assert fill["start"] == pytest.approx(expected_t0)

        spliced = apply_fills(line_objects, fills)
        assert spliced[candidate_lid]["words"] != []


class TestPlanFillsNegativeStart:
    """The candidate's cue sits early enough that cue + offset < 0 -- must be
    rejected before ``_fill_line``/``_collision``/``_energy_check`` ever
    run, with the rejection recorded rather than silently dropped. The
    candidate is positioned first (both positionally and chronologically)
    so the LRC's time-sort doesn't reorder cue_texts out of step with
    lyrics_lines -- map_lines_to_cues is an order-preserving alignment."""

    def test_negative_start_recorded_and_not_applied(self):
        offset = -1.0
        anchor_cues = [10.0, 20.0, 30.0, 40.0, 50.0]
        lyrics_lines = ["uniform victor whiskey xray"]
        align_lines = list(lyrics_lines)
        line_objects = [{"line_id": 0, "words": [], "start": None, "end": None, "source": "absent"}]
        transcribe_words: list[dict] = []
        lrc_stamps = [(0.5, lyrics_lines[0])]  # candidate cue, chronologically first

        for i, cue in enumerate(anchor_cues, start=1):
            text, words = _anchor_lines(cue, cue + offset)
            lyrics_lines.append(text)
            align_lines.append(text)
            line_objects.append(
                {
                    "line_id": i,
                    "words": words,
                    "start": words[0]["start"],
                    "end": words[-1]["end"],
                    "source": "align",
                }
            )
            transcribe_words.extend(words)
            lrc_stamps.append((cue, text))

        synced_text = _lrc(lrc_stamps)
        env = np.full(3000, -20.0, dtype=np.float32)

        fills, stats = plan_fills(
            line_objects,
            lyrics_lines,
            align_lines,
            transcribe_words,
            synced_text,
            env,
            margin_s=0.3,
            max_edit_ratio=0.75,
        )
        assert stats["eligible"] is True
        assert fills == []
        assert stats["filled_lids"] == []
        rejected = [f for f in stats["fills"] if f["lid"] == 0]
        assert len(rejected) == 1
        assert rejected[0]["reason"] == "negative_start"
        assert rejected[0]["applied"] is False


class TestPlanFillsNoMapping:
    def test_no_cue_mapping_returns_empty_with_reason(self):
        line_objects = [{"line_id": 0, "words": [], "start": None, "end": None, "source": "absent"}]
        fills, stats = plan_fills(
            line_objects,
            ["completely unrelated lyric text"],
            ["completely unrelated lyric text"],
            [],
            _lrc([(1.0, "nothing whatsoever alike")]),
            None,
            margin_s=0.3,
            max_edit_ratio=0.75,
        )
        assert fills == []
        assert stats == {
            "n_cues_mapped": 0,
            "arm_a": None,
            "slope_fit": None,
            "eligible": False,
            "reason": "no_mapping",
            "n_candidates": 0,
            "fills": [],
            "filled_lids": [],
        }
