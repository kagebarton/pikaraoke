"""Tests for the LRCLIB bar and pick (lib/lrc_auto_pick.py).

Most tests patch the fit, so each says exactly what the bar saw; the last class runs the
real fit on small made-up songs to show the numbers reach the bar.
"""

import pytest

from pikaraoke.lib import lrc_auto_pick
from pikaraoke.lib.lrc_auto_pick import (
    MAX_MISTIMED,
    MAX_SHIFT_RUN,
    MAX_UNCLAIMED_RUN,
    MISTIMED,
    NO_FIT,
    SHIFTED,
    SPEED,
    UNCLAIMED,
    evaluate,
    pick,
    refusal,
    timing_key,
)
from pikaraoke.lib.srt_slice_fit import FITS, REFUSED, SliceFit

CLEAN = SliceFit(FITS)


def _fit(mistimed: int = 0, unclaimed_run: int = 0, shift_run: int = 0, **fields) -> SliceFit:
    """A fit with that many mistimed lines, and ``shift_run`` neighbouring lines heard 2 s off."""
    return SliceFit(
        FITS,
        mistimed=tuple(range(mistimed)),
        unclaimed_run=unclaimed_run,
        offsets=(2.0,) * shift_run,
        **fields,
    )


def _record(record_id: int, text: str = "a\nb", track: str = "Song", album: str = "Album") -> dict:
    return {"id": record_id, "syncedLyrics": text, "trackName": track, "albumName": album}


@pytest.fixture
def fits(monkeypatch):
    """Patch the fit: a record's synced text (stripped) names the fit it gets, from the dict
    this returns. Records of one timing share a fit, as the real fit of equal text is equal."""
    by_text: dict[str, SliceFit] = {}
    monkeypatch.setattr(lrc_auto_pick, "lrc_to_srt", lambda synced: synced)
    monkeypatch.setattr(
        lrc_auto_pick, "fit_slice", lambda srt_text, streams, length: by_text[srt_text.strip()]
    )
    return by_text


class TestRefusal:
    def test_a_clean_fit_passes(self):
        assert refusal(CLEAN) is None

    def test_a_fit_that_did_not_fit_is_refused_whatever_else_it_says(self):
        assert refusal(SliceFit(REFUSED, speed=1.07, unclaimed_run=99)) == NO_FIT

    def test_a_speed_change_is_refused(self):
        assert refusal(_fit(speed=25 / 23.976)) == SPEED

    def test_more_than_the_allowed_mistimed_lines_is_refused(self):
        assert refusal(_fit(mistimed=MAX_MISTIMED)) is None
        assert refusal(_fit(mistimed=MAX_MISTIMED + 1)) == MISTIMED

    def test_a_longer_unclaimed_run_than_allowed_is_refused(self):
        assert refusal(_fit(unclaimed_run=MAX_UNCLAIMED_RUN)) is None
        assert refusal(_fit(unclaimed_run=MAX_UNCLAIMED_RUN + 1)) == UNCLAIMED

    def test_a_longer_shift_run_than_allowed_is_refused(self):
        assert refusal(_fit(shift_run=MAX_SHIFT_RUN)) is None
        assert refusal(_fit(shift_run=MAX_SHIFT_RUN + 1)) == SHIFTED

    def test_the_first_failed_condition_is_the_one_named(self):
        fit = _fit(mistimed=5, unclaimed_run=50, shift_run=9, speed=1.07)
        assert refusal(fit) == SPEED
        assert refusal(_fit(mistimed=5, unclaimed_run=50, shift_run=9)) == MISTIMED
        assert refusal(_fit(unclaimed_run=50, shift_run=9)) == UNCLAIMED
        assert refusal(_fit(shift_run=9)) == SHIFTED


class TestTimingKey:
    def test_a_reupload_with_other_spacing_is_the_same_timing(self):
        assert timing_key("[00:10.00] a \n\n  [00:12.00] b\n") == timing_key(
            "[00:10.00] a\n[00:12.00] b"
        )

    def test_a_different_stamp_is_a_different_timing(self):
        assert timing_key("[00:10.00] a") != timing_key("[00:10.50] a")


class TestPick:
    def test_a_clean_record_beats_a_one_flag_record_from_a_larger_timing(self, fits):
        fits.update({"flag": _fit(mistimed=1), "clean": CLEAN})
        records = [_record(1, "flag"), _record(2, "flag"), _record(3, "flag"), _record(9, "clean")]

        chosen = pick(records, [], 100.0)

        assert chosen.record["id"] == 9
        assert chosen.timing_size == 1

    def test_the_timing_most_records_carry_wins_among_clean_ones(self, fits):
        fits.update({"common": CLEAN, "rare": CLEAN})
        records = [_record(1, "rare"), _record(5, "common"), _record(6, "common")]

        chosen = pick(records, [], 100.0)

        assert (chosen.record["id"], chosen.timing_size) == (5, 2)

    def test_every_entry_reports_the_size_of_its_timing_the_refused_included(self, fits):
        fits.update({"copy": SliceFit(REFUSED), "solo": CLEAN})
        records = [_record(1, "copy"), _record(2, "copy "), _record(3, "solo")]

        sizes = {e.record["id"]: e.timing_size for e in evaluate(records, [], 100.0)}

        assert sizes == {1: 2, 2: 2, 3: 1}

    def test_equal_timing_falls_to_the_shorter_track_name(self, fits):
        fits["t"] = CLEAN
        records = [_record(1, "t", track="Song (Live)"), _record(2, "t", track="Song")]

        assert pick(records, [], 100.0).record["id"] == 2

    def test_then_the_shorter_album_name(self, fits):
        fits["t"] = CLEAN
        records = [_record(1, "t", album="Greatest Hits"), _record(2, "t", album="Hits")]

        assert pick(records, [], 100.0).record["id"] == 2

    def test_a_record_with_no_album_counts_as_the_shortest(self, fits):
        fits["t"] = CLEAN
        records = [
            _record(1, "t", album="Hits"),
            {"id": 2, "syncedLyrics": "t", "trackName": "Song"},
        ]

        assert pick(records, [], 100.0).record["id"] == 2

    def test_then_the_lower_id(self, fits):
        fits["t"] = CLEAN
        records = [_record(30, "t"), _record(7, "t"), _record(12, "t")]

        assert pick(records, [], 100.0).record["id"] == 7

    def test_fewer_mistimed_lines_come_before_everything_else(self, fits):
        fits.update({"flag": _fit(mistimed=1), "clean": CLEAN})
        records = [_record(1, "flag", track="A"), _record(2, "clean", track="A much longer name")]

        assert pick(records, [], 100.0).record["id"] == 2

    def test_records_without_synced_text_are_ignored(self, fits):
        fits["t"] = CLEAN
        records = [
            {"id": 1, "syncedLyrics": None, "trackName": "S"},
            {"id": 2, "syncedLyrics": "", "trackName": "S"},
            {"id": 3, "plainLyrics": "words", "trackName": "S"},
            _record(4, "t"),
        ]

        assert [e.record["id"] for e in evaluate(records, [], 100.0)] == [4]

    def test_a_shifted_record_is_not_picked_over_a_clean_one_from_a_smaller_timing(self, fits):
        fits.update({"shifted": _fit(shift_run=MAX_SHIFT_RUN + 1), "clean": CLEAN})
        records = [_record(1, "shifted"), _record(2, "shifted"), _record(9, "clean")]

        assert pick(records, [], 100.0).record["id"] == 9

    def test_no_pick_when_every_passing_record_carries_the_shift(self, fits):
        fits.update({"a": _fit(shift_run=5), "b": _fit(shift_run=3)})

        records = [_record(1, "a"), _record(2, "b")]

        assert pick(records, [], 100.0) is None
        assert [e.refusal for e in evaluate(records, [], 100.0)] == [SHIFTED, SHIFTED]

    def test_no_pick_when_none_pass(self, fits):
        fits.update({"a": _fit(unclaimed_run=40), "b": SliceFit(REFUSED)})

        assert pick([_record(1, "a"), _record(2, "b")], [], 100.0) is None

    def test_no_pick_without_records(self, fits):
        assert pick([], [], 100.0) is None

    def test_evaluate_puts_the_passing_first_and_keeps_every_refusal(self, fits):
        fits.update({"bad": _fit(unclaimed_run=40), "good": CLEAN, "none": SliceFit(REFUSED)})
        records = [_record(1, "bad"), _record(2, "none"), _record(3, "good")]

        entries = evaluate(records, [], 100.0)

        assert [(e.record["id"], e.refusal) for e in entries] == [
            (3, None),
            (1, UNCLAIMED),
            (2, NO_FIT),
        ]


# ---- the real fit, on made-up songs -----------------------------------------------------


def _word(i: int) -> str:
    return f"w{chr(97 + i // 26)}{chr(97 + i % 26)}x"


def _sung(lines: int) -> list[dict]:
    """The words of ``lines`` five-word lines sung 5 s apart from 10 s, as the transcriber hears them."""
    return [
        {"norm": _word(k * 5 + i), "start": 10.0 + 5.0 * k + 0.6 * i}
        for k in range(lines)
        for i in range(5)
    ]


def _lrc(lines: int, moved: dict[int, float] | None = None) -> str:
    """The record's lines on the singing's clock, those in ``moved`` stamped that many seconds late."""

    def stamp(k: int) -> str:
        seconds = 10.0 + 5.0 * k + (moved or {}).get(k, 0.0)
        return f"[{int(seconds) // 60:02d}:{seconds % 60:05.2f}]"

    return "".join(
        f"{stamp(k)} {' '.join(_word(k * 5 + i) for i in range(5))}\n" for k in range(lines)
    )


class TestRealFit:
    def test_a_record_that_covers_the_singing_passes(self):
        chosen = pick([_record(1, _lrc(30))], _sung(30), 300.0)

        assert chosen is not None
        assert chosen.fit.unclaimed_run == 0

    def test_a_record_that_stops_early_is_refused_for_what_it_leaves_unclaimed(self):
        entries = evaluate([_record(1, _lrc(10))], _sung(30), 300.0)

        assert entries[0].refusal == UNCLAIMED
        assert entries[0].fit.unclaimed_run == 100

    def test_the_complete_record_is_picked_over_the_short_one_from_a_larger_timing(self):
        short, whole = _lrc(10), _lrc(30)
        records = [_record(1, short), _record(2, short), _record(3, short), _record(4, whole)]

        chosen = pick(records, _sung(30), 300.0)

        assert chosen.record["id"] == 4

    def test_a_stretch_stamped_a_few_seconds_off_is_refused_as_shifted(self):
        late = {k: 3.0 for k in range(14, 17)}

        entries = evaluate([_record(1, _lrc(30, late))], _sung(30), 300.0)

        assert (entries[0].fit.mistimed, entries[0].fit.shift_run) == ((), 3)
        assert entries[0].refusal == SHIFTED

    def test_a_stretch_of_the_allowed_length_passes(self):
        late = {k: 3.0 for k in range(14, 16)}

        chosen = pick([_record(1, _lrc(30, late))], _sung(30), 300.0)

        assert chosen is not None
        assert chosen.fit.shift_run == MAX_SHIFT_RUN
