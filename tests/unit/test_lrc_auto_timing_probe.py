"""Unit tests for scripts/lrc_auto_timing_probe.py: the parts that need no library or network.

Every number is made up; no lyric text appears here.
"""

import math

import pytest

from pikaraoke.lib.srt_slice_fit import DISAGREE, FITS, REFUSED, TOO_FEW, SliceFit
from scripts.lrc_auto_timing_probe import (
    DIMS,
    GRID,
    HOLE,
    JOINT,
    KNOWN,
    REF,
    RIGHT,
    UNJUDGED,
    WRONG_TIMING,
    Candidate,
    SongResult,
    accepts,
    all_points,
    arm_b_key,
    caption_ok,
    classify,
    end_unheard,
    interior_unheard,
    margin_safe_points,
    need_vector,
    neighbours,
    run_sweep,
)

LOOSEST = tuple(len(GRID[d]) - 1 for d in DIMS)


def at(**steps: int) -> tuple[int, ...]:
    """A grid point from step indexes by dimension letter; every other dimension strictest."""
    return tuple(steps.get(d, 0) for d in DIMS)


def cand(
    *,
    status: str = FITS,
    speed: float = 1.0,
    matched: int = 9,
    total: int = 10,
    mistimed: tuple[int, ...] = (),
    unheard: tuple[int, ...] = (),
    dropped: int = 0,
    spread: float | None = 0.1,
    gap: int | None = 1,
    asr: SliceFit | None = None,
    lrclib_id: int = 1,
    cls: str = "",
    group: str = REF,
) -> Candidate:
    fit = SliceFit(
        status,
        matched=matched,
        total=total,
        speed=speed,
        mistimed=mistimed,
        unheard=unheard,
        dropped=dropped,
        spread_s=spread,
    )
    return Candidate(
        group=group,
        youtube_id="abc",
        title="a song",
        lrclib_id=lrclib_id,
        on_disk=False,
        duration=240,
        gap=gap,
        fit=fit,
        asr=asr,
        cls=cls,
    )


class TestEndUnheard:
    def test_none_when_both_ends_heard(self):
        assert end_unheard((), 10) == 0
        assert end_unheard((4, 5), 10) == 0

    def test_run_at_the_start(self):
        assert end_unheard((0, 1, 2), 10) == 3

    def test_run_at_the_end(self):
        assert end_unheard((8, 9), 10) == 2

    def test_longer_of_the_two_ends(self):
        assert end_unheard((0, 7, 8, 9), 10) == 3

    def test_a_gap_after_the_first_line_ends_the_start_run(self):
        assert end_unheard((0, 2, 3), 10) == 1

    def test_whole_song_unheard(self):
        assert end_unheard(tuple(range(5)), 5) == 5


class TestInteriorUnheard:
    def test_run_of_three_inside(self):
        assert interior_unheard((4, 5, 6), 10)

    def test_run_of_two_is_an_ad_lib(self):
        assert not interior_unheard((4, 5), 10)

    @pytest.mark.parametrize("unheard", [(0, 1, 2), (7, 8, 9)])
    def test_run_touching_an_end_is_not_interior(self, unheard):
        assert not interior_unheard(unheard, 10)

    def test_interior_run_beside_an_end_run(self):
        assert interior_unheard((0, 1, 2, 5, 6, 7), 10)

    def test_none(self):
        assert not interior_unheard((), 10)


def identity(n: int) -> dict[int, int]:
    return {i: i for i in range(n)}


def starts(n: int, offset: float = 0.0) -> list[float]:
    return [i * 10.0 + offset for i in range(n)]


class TestCaption:
    def test_a_clean_fit_is_a_usable_reference(self):
        assert caption_ok(SliceFit(FITS, shift_s=0.8))

    @pytest.mark.parametrize(
        "fit",
        [
            SliceFit(REFUSED, reason=TOO_FEW),
            SliceFit(FITS, speed=1.0427),
            SliceFit(FITS, shift_s=-1.6),
            SliceFit(FITS, mistimed=(3, 4)),
        ],
    )
    def test_anything_else_is_not(self, fit):
        assert not caption_ok(fit)

    def test_one_mistimed_line_is_a_repeat_not_a_run(self):
        assert caption_ok(SliceFit(FITS, mistimed=(3,)))


class TestClassify:
    def test_right(self):
        j = classify(identity(10), starts(10), starts(10), 0.0)
        assert j.cls == RIGHT
        assert j.median_d == 0.0

    def test_caption_shift_is_applied(self):
        j = classify(identity(10), starts(10, 5.0), starts(10), 5.0)
        assert j.cls == RIGHT

    def test_unjudged_with_too_few_mapped_lines(self):
        assert classify(identity(7), starts(7), starts(7), 0.0).cls == UNJUDGED

    def test_unjudged_with_too_small_a_share(self):
        j = classify(identity(9), starts(20), starts(20), 0.0)
        assert j.cls == UNJUDGED

    def test_wrong_timing_from_the_median_alone(self):
        j = classify(identity(10), starts(10, 2.0), starts(10), 0.0)
        assert j.cls == WRONG_TIMING
        assert j.off_runs == []

    def test_median_inside_the_limit_is_right(self):
        assert classify(identity(10), starts(10, 1.0), starts(10), 0.0).cls == RIGHT

    def test_wrong_timing_from_a_run_of_two_off_lines(self):
        lrc = starts(10)
        lrc[3] += 4.0
        lrc[4] += 4.0
        j = classify(identity(10), lrc, starts(10), 0.0)
        assert j.cls == WRONG_TIMING
        assert j.off_runs == [(3, 4)]

    def test_one_off_line_is_not_a_run(self):
        lrc = starts(10)
        lrc[3] += 4.0
        assert classify(identity(10), lrc, starts(10), 0.0).cls == RIGHT

    def test_unmapped_line_inside_an_off_run_does_not_end_it(self):
        lrc = starts(12)
        lrc[3] += 4.0
        lrc[5] += 4.0
        mapping = {i: i for i in range(12) if i != 4}
        assert classify(mapping, lrc, starts(12), 0.0).cls == WRONG_TIMING

    def test_mapped_line_between_two_off_lines_ends_the_run(self):
        lrc = starts(10)
        lrc[3] += 4.0
        lrc[5] += 4.0
        assert classify(identity(10), lrc, starts(10), 0.0).cls == RIGHT

    def test_hole_of_four_unmapped_lrc_lines_at_the_end(self):
        j = classify(identity(8), starts(12), starts(8), 0.0)
        assert j.cls == HOLE
        assert (j.lrc_hole, j.caption_hole) == (4, 0)

    def test_hole_of_four_unmapped_caption_cues_at_the_end(self):
        j = classify(identity(8), starts(8), starts(12), 0.0)
        assert j.cls == HOLE
        assert (j.lrc_hole, j.caption_hole) == (0, 4)

    def test_hole_of_three_is_not_one(self):
        assert classify(identity(8), starts(11), starts(8), 0.0).cls == RIGHT

    def test_wrong_timing_wins_over_a_hole(self):
        j = classify(identity(8), starts(12, 2.0), starts(8), 0.0)
        assert j.cls == WRONG_TIMING


class TestAccepts:
    def test_clean_candidate_needs_the_strictest_point(self):
        assert need_vector(cand()) == at()
        assert accepts(at(), cand())

    @pytest.mark.parametrize(
        "bad",
        [
            cand(status=REFUSED),
            cand(speed=25 / 23.976),
            cand(gap=None),
            cand(mistimed=(2, 6)),
            cand(matched=4),
            cand(gap=20),
            cand(unheard=(0, 1, 2, 3)),
        ],
    )
    def test_conjunct_that_no_grid_value_relaxes_refuses_everywhere(self, bad):
        assert need_vector(bad) is None
        assert not accepts(LOOSEST, bad)

    @pytest.mark.parametrize(
        "candidate, need",
        [
            (cand(mistimed=(3,)), at(M=1)),
            (cand(matched=7), at(R=2)),
            (cand(matched=5), at(R=4)),
            (cand(gap=-4), at(G=2)),
            (cand(gap=15), at(G=4)),
            (cand(unheard=(0, 1)), at(E=2)),
            (cand(unheard=(4, 5, 6)), at(I=1)),
            (cand(dropped=2), at(D=1)),
            (cand(spread=0.4), at(P=1)),
            (cand(spread=0.8), at(P=2)),
            (cand(spread=None), at(P=2)),
        ],
    )
    def test_each_dimension_turns_a_candidate_away_until_it_is_loose_enough(self, candidate, need):
        assert need_vector(candidate) == need
        assert accepts(need, candidate)
        for k, step in enumerate(need):
            if step:
                tighter = need[:k] + (step - 1,) + need[k + 1 :]
                assert not accepts(tighter, candidate)

    def test_looser_point_accepts_what_a_stricter_one_does(self):
        assert accepts(LOOSEST, cand(mistimed=(3,), matched=7, gap=-4, dropped=2))

    @pytest.mark.parametrize(
        "asr",
        [
            SliceFit(FITS, mistimed=(1, 2)),
            SliceFit(REFUSED, reason=DISAGREE),
        ],
    )
    def test_asr_disagreement_is_vetoed_only_while_the_veto_is_on(self, asr):
        c = cand(asr=asr)
        assert not accepts(at(V=0), c)
        assert accepts(at(V=1), c)

    @pytest.mark.parametrize(
        "asr", [None, SliceFit(REFUSED, reason=TOO_FEW), SliceFit(FITS, mistimed=(4,))]
    )
    def test_sparse_or_agreeing_asr_is_not_a_veto(self, asr):
        assert accepts(at(V=0), cand(asr=asr))


class TestMarginSafe:
    def test_all_clean(self):
        safe = margin_safe_points({p: True for p in all_points()})
        assert all(safe.values())

    def test_a_dirty_looser_neighbour_unsafes_the_point_but_not_the_point_beyond(self):
        clean = {p: True for p in all_points()}
        dirty = at(M=1)
        clean[dirty] = False
        safe = margin_safe_points(clean)
        assert not safe[dirty]
        assert not safe[at()]  # one step stricter in M
        assert safe[at(R=1)]  # its own looser neighbours are all clean
        assert dirty in set(neighbours(at()))
        assert at(M=1, R=1) not in set(neighbours(at()))

    def test_a_dirty_stricter_neighbour_does_not_matter(self):
        clean = {p: True for p in all_points()}
        clean[at()] = False
        assert margin_safe_points(clean)[at(M=1)]

    def test_loosest_point_has_no_neighbours(self):
        assert list(neighbours(LOOSEST)) == []
        clean = {p: False for p in all_points()}
        clean[LOOSEST] = True
        assert margin_safe_points(clean)[LOOSEST]

    def test_grid_has_3600_points(self):
        assert len(all_points()) == 3600


class TestArmB:
    def pick(self, *cands: Candidate) -> int:
        return min(cands, key=arm_b_key).lrclib_id

    def test_matched_share_beats_gap(self):
        assert (
            self.pick(cand(matched=9, gap=5, lrclib_id=1), cand(matched=8, gap=0, lrclib_id=2)) == 1
        )

    def test_smaller_absolute_gap_on_a_tie(self):
        assert self.pick(cand(gap=2, lrclib_id=1), cand(gap=-1, lrclib_id=2)) == 2

    def test_smaller_spread_on_a_further_tie(self):
        assert self.pick(cand(spread=0.2, lrclib_id=1), cand(spread=0.1, lrclib_id=2)) == 2

    def test_lowest_id_on_a_full_tie(self):
        assert self.pick(cand(lrclib_id=7), cand(lrclib_id=3), cand(lrclib_id=9)) == 3

    def test_missing_spread_ranks_after_a_known_one(self):
        assert arm_b_key(cand(spread=None)) > arm_b_key(cand(spread=5.0))
        assert math.isinf(arm_b_key(cand(spread=None))[2])


class TestSweep:
    def ref_song(self, wrong: Candidate) -> SongResult:
        return SongResult(
            REF,
            "abc",
            "a song",
            candidates=[cand(lrclib_id=1, cls=RIGHT), wrong],
            arm_a_id=wrong.lrclib_id,
            ref_ok=True,
        )

    def near_wrong(self) -> Candidate:
        """Wrong, and one step (in M) looser than the strictest point."""
        return cand(lrclib_id=2, cls=WRONG_TIMING, mistimed=(3,), spread=0.2)

    def test_a_wrong_acceptance_counts_once_the_bar_is_loose_enough(self):
        sweep = run_sweep([self.ref_song(self.near_wrong())])
        strict, loose = sweep[at()], sweep[at(M=1)]
        assert (strict["wrong"], strict["a_ref_any"], strict["b_ref"]) == (0, 0, 1)
        assert (loose["wrong"], loose["a_ref_any"], loose["a_ref"]) == (1, 1, 0)

    def test_arm_b_picks_the_better_fit_even_when_arm_a_picks_the_wrong_one(self):
        loose = run_sweep([self.ref_song(self.near_wrong())])[at(M=1)]
        assert (loose["b_ref"], loose["b_ref_any"]) == (1, 1)

    def test_margin_safe_needs_clean_neighbours(self):
        sweep = run_sweep([self.ref_song(self.near_wrong())])
        assert sweep[at()]["wrong"] == 0
        assert not sweep[at()]["margin_safe"]  # one step looser in M accepts the wrong one

    def test_a_wrong_acceptance_two_steps_away_is_outside_the_margin(self):
        far = cand(lrclib_id=2, cls=WRONG_TIMING, mistimed=(3,), matched=8)  # needs M=1 and R=1
        sweep = run_sweep([self.ref_song(far)])
        assert sweep[at(M=1, R=1)]["wrong"] == 1
        assert sweep[at()]["margin_safe"]
        assert not sweep[at(M=1)]["margin_safe"]

    def test_songs_without_a_usable_reference_are_not_counted_as_ref(self):
        song = self.ref_song(self.near_wrong())
        song.ref_ok = False
        counts = run_sweep([song])[LOOSEST]
        assert (counts["wrong"], counts["b_ref_any"]) == (0, 0)

    def test_known_acceptances_and_other_groups(self):
        known = SongResult(KNOWN, "k", "k", candidates=[cand(group=KNOWN)])
        joint = SongResult(JOINT, "j", "j", candidates=[cand(lrclib_id=5)], arm_a_id=5)
        counts = run_sweep([known, joint])[at()]
        assert (counts["known"], counts["a_joint"], counts["b_joint"]) == (1, 1, 1)
