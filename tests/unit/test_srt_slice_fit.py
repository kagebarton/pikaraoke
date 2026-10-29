"""Tests for the movie-subtitle slice fit (lib/srt_slice_fit.py), on synthetic cues."""

import json
from datetime import timedelta

import srt

from pikaraoke.lib import srt_slice_fit
from pikaraoke.lib.lrclib import LRC_LAST_LINE_HOLD_S
from pikaraoke.lib.srt_cues import cue_spans_from_srt
from pikaraoke.lib.srt_slice_fit import (
    ASR,
    DISAGREE,
    FITS,
    FLAG_TOLERANCE_S,
    MAX_CUES,
    MIN_FLAGGED_RUN,
    NO_REFERENCE,
    NOT_SRT,
    REFUSED,
    TOO_FEW,
    TOO_LONG,
    TRANSCRIBE,
    fit_slice,
    flagged_runs,
    free_speed,
    heard_streams,
    lrc_to_srt,
)

LINE_GAP_S = 5.0
LINE_DUR_S = 3.5
WORDS_PER_LINE = 5

# Heard line starts off by about 0.3 s, as a transcription of a sung clip is; fixed
# so the tests keep what they check on every Python.
JITTER_S = [0.01, 0.14, -0.14, 0.11, 0.28, 0.12, 0.47, -0.27, 0.02, -0.21]
JITTER_S += [-0.24, -0.06, 0.07, 0.13, 0.15, 0.67, 0.26, -0.48, 0.06, -0.19]
JITTER_S += [-0.15, 0.39, -0.07, -0.59, 0.09, -0.09, -0.35, -0.28, -0.19, -0.01]


def _word(i: int) -> str:
    """A distinct pseudo-word per index, so the order match is unambiguous."""
    return f"w{chr(97 + i // 26)}{chr(97 + i % 26)}x"


def _line(k: int) -> str:
    return " ".join(_word(k * WORDS_PER_LINE + i) for i in range(WORDS_PER_LINE))


def _clip_start(k: int) -> float:
    return 10.0 + LINE_GAP_S * k


def _heard(lines: dict[int, str], clip_start=_clip_start) -> list[dict]:
    """Heard words for the given lines, sung evenly across each line's clip span."""
    out = []
    for k, text in lines.items():
        for i, tok in enumerate(text.split()):
            out.append({"norm": tok, "start": clip_start(k) + i * 0.6})
    return sorted(out, key=lambda w: w["start"])


def _movie_srt(
    lines: dict[int, str], shift: float = 0.0, speed: float = 1.0, clip_start=_clip_start
) -> str:
    """The lines as movie subtitles whose fit back to the clip is ``(speed, shift)``."""
    subs = [
        srt.Subtitle(
            index=n,
            start=timedelta(seconds=(clip_start(k) - shift) / speed),
            end=timedelta(seconds=(clip_start(k) + LINE_DUR_S - shift) / speed),
            content=text,
        )
        for n, (k, text) in enumerate(lines.items(), start=1)
    ]
    return srt.compose(subs)


def _song(n: int = 30) -> dict[int, str]:
    return {k: _line(k) for k in range(n)}


def _starts(srt_text: str) -> list[float]:
    return [c.start.total_seconds() for c in srt.parse(srt_text)]


class TestFit:
    def test_plain_shift_fits_and_corrects_the_cue_times(self):
        song = _song()
        result = fit_slice(_movie_srt(song, shift=-2500.0), {TRANSCRIBE: _heard(song)}, 300.0)
        assert result.status == FITS
        assert abs(result.shift_s + 2500.0) < 0.05
        assert result.speed == 1.0
        assert (result.matched, result.total, result.dropped) == (30, 30, 0)
        assert _starts(result.srt) == [round(_clip_start(k), 3) for k in range(30)]

    def test_pal_speed_fits_in_both_directions(self):
        song = _song()
        for speed in srt_slice_fit.SPEED_FACTORS[1:]:
            result = fit_slice(
                _movie_srt(song, shift=-1800.0, speed=speed), {TRANSCRIBE: _heard(song)}, 300.0
            )
            assert result.status == FITS
            assert result.speed == speed
            assert abs(result.shift_s + 1800.0) < 0.05
            assert max(abs(a - _clip_start(k)) for k, a in enumerate(_starts(result.srt))) < 0.01

    def test_the_move_is_the_first_lines_not_the_shift_under_a_speed(self):
        song = _song()
        movie = _movie_srt(song, shift=-1800.0, speed=25 / 23.976)
        result = fit_slice(movie, {TRANSCRIBE: _heard(song)}, 300.0)
        assert result.status == FITS
        moved = _starts(result.srt)[0] - _starts(movie)[0]
        assert abs(result.move_s - moved) < 0.05
        assert abs(result.move_s - result.shift_s) > 60

    def test_a_speed_no_factor_covers_is_fitted_free(self):
        song = _song()
        result = fit_slice(
            _movie_srt(song, shift=-1800.0, speed=1.07), {TRANSCRIBE: _heard(song)}, 300.0
        )
        assert result.status == FITS
        assert abs(result.speed - 1.07) < 0.001
        assert max(abs(a - _clip_start(k)) for k, a in enumerate(_starts(result.srt))) < 0.05

    def test_a_short_clip_fits_at_its_own_speed_when_a_factor_barely_passes(self):
        song = _song(20)
        for speed in (1.02, 1.065, 1.07):
            result = fit_slice(
                _movie_srt(song, shift=-1800.0, speed=speed), {TRANSCRIBE: _heard(song)}, 120.0
            )
            assert result.status == FITS
            assert abs(result.speed - speed) < 0.001
            assert max(abs(a - _clip_start(k)) for k, a in enumerate(_starts(result.srt))) < 0.002

    def test_noisy_heard_times_keep_the_factor_over_a_barely_different_free_speed(self):
        song = _song(30)
        heard = _heard(song, clip_start=lambda k: _clip_start(k) + JITTER_S[k])
        result = fit_slice(_movie_srt(song, shift=-1800.0), {TRANSCRIBE: heard}, 300.0)
        assert result.status == FITS
        assert result.speed == 1.0

    def test_a_free_speed_too_far_from_one_is_refused(self):
        song = _song()
        result = fit_slice(
            _movie_srt(song, shift=-1800.0, speed=1.15), {TRANSCRIBE: _heard(song)}, 300.0
        )
        assert (result.status, result.reason) == (REFUSED, DISAGREE)

    def test_clip_cut_from_two_scenes_is_refused_as_disagreeing(self):
        song = _song()
        movie = srt.compose(
            [
                srt.Subtitle(
                    index=k + 1,
                    start=timedelta(seconds=_clip_start(k) + (900.0 if k < 15 else 2400.0)),
                    end=timedelta(
                        seconds=_clip_start(k) + LINE_DUR_S + (900.0 if k < 15 else 2400.0)
                    ),
                    content=text,
                )
                for k, text in song.items()
            ]
        )
        result = fit_slice(movie, {TRANSCRIBE: _heard(song)}, 300.0)
        assert (result.status, result.reason) == (REFUSED, DISAGREE)
        assert result.srt is None

    def test_cues_past_both_ends_are_dropped_and_the_edge_ones_clamped(self):
        def clip_start(k: int) -> float:
            return -12.0 + LINE_GAP_S * k

        lines = {k: _line(k) for k in range(30)}
        length = 100.0
        inside = {k: t for k, t in lines.items() if 0 <= clip_start(k) <= length}
        result = fit_slice(
            _movie_srt(lines, shift=-600.0, clip_start=clip_start),
            {TRANSCRIBE: _heard(inside, clip_start)},
            length,
        )
        assert result.status == FITS
        # k=0..1 end before 0 (-12 -> -8.5, -7 -> -3.5); k=2 (-2 -> 1.5) straddles the start.
        # k=23 (103) onwards starts past the end; k=22 (98 -> 101.5) straddles it.
        assert result.dropped == 2 + 7
        cues = list(srt.parse(result.srt))
        assert cues[0].start == timedelta(0)
        assert cues[-1].end == timedelta(seconds=length)
        assert [c.index for c in cues] == list(range(1, len(cues) + 1))

    def test_a_zero_length_cue_is_dropped_from_both_the_count_and_the_sheet(self):
        song = _song()
        cues = list(srt.parse(_movie_srt(song, shift=-600.0)))
        cues[5].end = cues[5].start
        # compose would renumber and so drop the zero-length cue before the fit sees it
        result = fit_slice(srt.compose(cues, reindex=False), {TRANSCRIBE: _heard(song)}, 300.0)
        assert result.status == FITS
        assert (result.total, result.dropped) == (29, 1)
        assert len(list(srt.parse(result.srt))) == result.total

    def test_dialogue_with_no_heard_match_does_not_sink_a_fit(self):
        song = _song()
        dialogue = {k: _line(100 + k) for k in range(0, 30, 5)}  # 6 unheard cues among 30
        movie = {k: song[k] if k not in dialogue else dialogue[k] for k in song}
        result = fit_slice(_movie_srt(movie, shift=-2500.0), {TRANSCRIBE: _heard(song)}, 300.0)
        assert result.status == FITS
        assert result.matched == 24 and result.total == 30

    def test_recheck_of_a_corrected_slice_fits_at_zero_shift_and_speed_one(self):
        song = _song()
        first = fit_slice(
            _movie_srt(song, shift=-1800.0, speed=srt_slice_fit.SPEED_FACTORS[1]),
            {TRANSCRIBE: _heard(song)},
            300.0,
        )
        again = fit_slice(first.srt, {TRANSCRIBE: _heard(song)}, 300.0)
        assert again.status == FITS
        assert again.speed == 1.0
        assert abs(again.shift_s) < 0.01
        assert (again.matched, again.total, again.dropped) == (30, 30, 0)

    def test_text_the_clip_does_not_contain_is_refused_as_too_few(self):
        song = _song()
        elsewhere = {k: _line(200 + k) for k in range(30)}
        result = fit_slice(_movie_srt(elsewhere), {TRANSCRIBE: _heard(song)}, 300.0)
        assert (result.status, result.reason) == (REFUSED, TOO_FEW)
        assert result.total == 30

    def test_the_stream_that_matches_more_is_kept(self):
        song = _song()
        sparse = _heard({k: song[k] for k in range(0, 30, 6)})
        result = fit_slice(
            _movie_srt(song, shift=-100.0), {TRANSCRIBE: sparse, ASR: _heard(song)}, 300.0
        )
        assert result.status == FITS
        assert result.heard_source == ASR


class TestNothingToFit:
    def test_no_heard_words_means_no_reference(self):
        assert fit_slice(_movie_srt(_song()), {}, 300.0).status == NO_REFERENCE

    def test_text_that_is_not_srt(self):
        streams = {TRANSCRIBE: _heard(_song())}
        for text in ("these are not subtitles at all", "", "\n \n"):
            assert fit_slice(text, streams, 300.0).status == NOT_SRT

    def test_out_of_range_timestamp_is_not_srt(self):
        text = "1\n99999999999999:00:00,000 --> 99999999999999:00:01,000\nhey\n"
        assert fit_slice(text, {TRANSCRIBE: _heard(_song())}, 300.0).status == NOT_SRT

    def test_windows_line_endings_parse(self):
        song = _song()
        text = _movie_srt(song, shift=-100.0).replace("\n", "\r\n")
        assert fit_slice(text, {TRANSCRIBE: _heard(song)}, 300.0).status == FITS


class TestTooLong:
    def test_more_cues_than_the_limit_are_not_fitted(self):
        cue = "{n}\n00:00:01,000 --> 00:00:02,000\nla\n\n"
        text = "".join(cue.format(n=n) for n in range(1, MAX_CUES + 2))

        fit = fit_slice(text, {TRANSCRIBE: _heard(_song())}, 300.0)

        assert (fit.status, fit.total) == (TOO_LONG, MAX_CUES + 1)


class TestHeardStreams:
    def test_bundle_words_become_normalised_stream(self):
        bundle = {
            "transcribe_words": [{"word": "Hello,", "start": 1.0}, {"word": "...", "start": 2}]
        }
        assert heard_streams(bundle, None) == {TRANSCRIBE: [{"norm": "hello", "start": 1.0}]}

    def test_asr_caption_becomes_stream_and_bad_json_is_ignored(self):
        caption = json.dumps(
            {"events": [{"tStartMs": 1000, "segs": [{"utf8": "Hello", "tOffsetMs": 0}]}]}
        )
        assert heard_streams(None, caption) == {ASR: [{"norm": "hello", "start": 1.0}]}
        assert heard_streams(None, "not json") == {}

    def test_an_auto_caption_of_another_shape_is_ignored(self):
        for caption in ("[]", '{"events": [{"segs": ["Hello"]}]}', '{"events": [7]}'):
            assert heard_streams(None, caption) == {}

    def test_nothing_on_disk_is_no_streams(self):
        assert heard_streams(None, None) == {}
        assert heard_streams({"transcribe_words": None}, "") == {}


class TestRepeatedLine:
    def test_timed_pass_gives_a_repeated_chorus_to_the_instance_it_sits_in(self):
        chorus = "wavx wbvx wcvx wdvx"
        texts = [chorus, "wexx wfxx wgxx", chorus]
        spans = [(0.0, 3.0), (5.0, 8.0), (10.0, 13.0)]
        tokens = srt_slice_fit._CueTokens.of(texts)
        # Only the second chorus was heard; the movie clock runs 100 s ahead of the clip.
        heard = [{"norm": tok, "start": 110.0 + i * 0.6} for i, tok in enumerate(chorus.split())]
        anchors, found = srt_slice_fit._match_by_time(tokens, spans, 1.0, 100.0, heard)
        assert found == {2}
        assert anchors == [{"lid": 2, "start": 110.0}]


class TestFreeSpeed:
    def test_none_without_a_pair_of_anchors_far_enough_apart(self):
        spans = [(5.0 * k, 5.0 * k + 3.0) for k in range(5)]  # starts 0-20 s: 20 s is not enough
        anchors = [{"lid": k, "start": 100.0 + 1.07 * spans[k][0]} for k in range(5)]
        assert free_speed(anchors, spans) is None

    def test_cue_starts_out_of_file_order_still_give_the_slope(self):
        spans = [(100.0, 103.0), (60.0, 63.0), (20.0, 23.0)]
        anchors = [{"lid": k, "start": 5.0 + 1.07 * spans[k][0]} for k in range(3)]
        assert abs(free_speed(anchors, spans) - 1.07) < 1e-9


class TestPassTwoPick:
    def test_pass_two_picks_its_own_speed_and_shift_when_pass_one_saw_too_little(self, monkeypatch):
        song = _song(20)
        order_match = srt_slice_fit._match_by_order

        def first_five_cues(tokens, words):
            anchors, _ = order_match(tokens, words)
            return anchors[:5], {a["lid"] for a in anchors[:5]}

        picks = []
        best_speed = srt_slice_fit._best_speed

        def recording(*args):
            picks.append(best_speed(*args))
            return picks[-1]

        monkeypatch.setattr(srt_slice_fit, "_match_by_order", first_five_cues)
        monkeypatch.setattr(srt_slice_fit, "_best_speed", recording)
        text = _movie_srt(song, shift=-1800.0, speed=1.07)
        result = fit_slice(text, {TRANSCRIBE: _heard(song)}, 120.0)

        pass1, pass2 = picks
        assert pass1.speed == srt_slice_fit.SPEED_FACTORS[1]
        assert abs(pass2.speed - 1.07) < 0.001
        assert abs(pass2.stats["offset_s"] - pass1.stats["offset_s"]) > 1.0
        assert result.status == FITS
        assert result.speed == pass2.speed
        assert result.shift_s == pass2.stats["offset_s"]


class TestBestSpeed:
    def test_a_free_speed_with_less_spread_replaces_a_bailed_factor_however_little_it_drifts(self):
        spans = [(5.0 * k, 5.0 * k + 3.0) for k in range(12)]
        jitter = [0.5, 0.0, -1.4, -0.5, 0.9, 1.6, -0.3, -2.7, 2.8, 0.7, -3.2, 0.8]
        anchors = [{"lid": k, "start": 100.0 + 1.01 * spans[k][0] + jitter[k]} for k in range(12)]
        factor = srt_slice_fit._fit_at(anchors, spans, 1.0)
        assert factor.stats["bailed"] == "wide_spread"

        best = srt_slice_fit._best_speed(anchors, spans)
        assert best.stats["bailed"] is None
        assert srt_slice_fit._drift_s(anchors, factor.speed, best.speed) < 0.75

    def test_a_wrong_line_anchor_far_down_the_paste_does_not_stretch_the_drift(self):
        spans = [(5.0 * k, 5.0 * k + 3.0) for k in range(20)] + [(700.0, 703.0)]
        anchors = [{"lid": k, "start": 100.0 + spans[k][0] + JITTER_S[k]} for k in range(20)]
        anchors.append({"lid": 20, "start": 180.0})  # a line repeated past the clip
        free = srt_slice_fit.free_speed(anchors, spans)
        factor = srt_slice_fit._fit_at(anchors, spans, 1.0)
        assert srt_slice_fit._fit_at(anchors, spans, free).rank < factor.rank
        drift = srt_slice_fit._drift_s(anchors, factor.speed, free)
        assert drift < srt_slice_fit.MIN_FREE_SPEED_DRIFT_S
        assert srt_slice_fit._best_speed(anchors, spans).speed == 1.0


def _stamp(seconds: float) -> str:
    return f"[{int(seconds) // 60:02d}:{seconds % 60:05.2f}]"


def _lrc(lines: dict[int, str], clip_start=_clip_start) -> str:
    """The lines as an LRC on the clip's own clock, as LRCLIB stamps them."""
    return "".join(f"{_stamp(clip_start(k))} {text}\n" for k, text in lines.items())


def _fit_lrc(lrc: str, heard: list[dict], length: float = 300.0):
    return fit_slice(lrc_to_srt(lrc), {TRANSCRIBE: heard}, length)


class TestLrcToSrt:
    def test_each_line_ends_where_the_next_starts_and_the_last_holds(self):
        lrc = "[ti:A Title]\n[00:10.00] first\n[00:15.50] second\n[01:01.00] third\n"

        cues = list(srt.parse(lrc_to_srt(lrc)))

        assert [cue.content for cue in cues] == ["first", "second", "third"]
        assert [(c.start.total_seconds(), c.end.total_seconds()) for c in cues] == [
            (10.0, 15.5),
            (15.5, 61.0),
            (61.0, 61.0 + LRC_LAST_LINE_HOLD_S),
        ]

    def test_an_lrc_with_no_timed_line_is_empty_and_fit_slice_refuses_it(self):
        assert lrc_to_srt("") == ""
        assert lrc_to_srt("[ti:A Title]\nwords with no stamp\n") == ""
        assert fit_slice(lrc_to_srt(""), {TRANSCRIBE: _heard(_song())}, 300.0).status == NOT_SRT


class TestFlaggedLines:
    def test_an_lrc_on_the_clips_own_clock_fits_with_nothing_flagged(self):
        song = _song()

        result = _fit_lrc(_lrc(song), _heard(song))

        assert result.status == FITS
        assert abs(result.shift_s) < 0.05
        assert result.speed == 1.0
        assert (result.matched, result.total) == (30, 30)
        assert result.flagged == ()

    def test_a_cut_verse_still_fits_and_its_lines_are_one_flagged_run(self):
        """Six lines mid-song that the heard words never sing: the spread check passes them."""
        song = _song()
        sung = {k: text for k, text in song.items() if not 12 <= k < 18}

        result = _fit_lrc(_lrc(song), _heard(sung))

        assert result.status == FITS
        assert result.spread_s == 0
        assert result.flagged == (12, 13, 14, 15, 16, 17)
        assert flagged_runs(result.flagged, MIN_FLAGGED_RUN) == [(12, 17)]

    def test_single_unheard_lines_scattered_make_no_run(self):
        song = _song()
        sung = {k: text for k, text in song.items() if k not in (3, 9, 15, 21)}

        result = _fit_lrc(_lrc(song), _heard(sung))

        assert result.status == FITS
        assert result.flagged == (3, 9, 15, 21)
        assert flagged_runs(result.flagged, MIN_FLAGGED_RUN) == []

    def test_a_line_heard_far_from_its_time_is_flagged_and_one_near_it_is_not(self):
        song = _song()
        late = FLAG_TOLERANCE_S + 1.0
        near = FLAG_TOLERANCE_S / 2

        def start(k: int) -> float:
            return _clip_start(k) + {7: late, 8: near}.get(k, 0.0)

        result = _fit_lrc(_lrc(song), _heard(song, clip_start=start))

        assert result.status == FITS
        assert result.flagged == (7,)

    def test_flagged_lines_number_the_lines_the_pipeline_loads_not_the_cues(self):
        """A music-note cue cleans to nothing, so it is no line and shifts none of the numbers."""
        song = _song(12)
        lrc = _lrc(song) + f"{_stamp(_clip_start(5) + 2)} \u266a\n"
        sung = {k: text for k, text in song.items() if k != 8}

        result = _fit_lrc(lrc, _heard(sung))

        assert result.status == FITS
        texts, _ = cue_spans_from_srt(result.srt)
        assert len(texts) == 12
        assert result.flagged == (8,)
        assert texts[8] == song[8]

    def test_cues_outside_the_clip_are_not_numbered(self):
        """The corrected sheet drops lines past the clip's end; the flags count what is left."""
        song = _song()
        sung = {k: text for k, text in song.items() if k != 2}

        result = _fit_lrc(_lrc(song), _heard(sung), length=_clip_start(20) + 1)

        assert result.status == FITS
        assert result.dropped == 9
        assert result.flagged == (2,)
        assert len(cue_spans_from_srt(result.srt)[0]) == result.total == 21

    def test_lines_that_end_before_the_clip_begins_are_not_numbered(self):
        """A video that starts mid-song: the LRC's earlier lines fall off the front of the clip."""
        song = _song()
        lead = 20.0  # the LRC's clock runs this far ahead of the clip's
        before = {k: _line(40 + k + 3) for k in (-3, -2, -1)}  # sung at clip times -5, 0, 5
        lrc = _lrc({**before, **song}, clip_start=lambda k: _clip_start(k) + lead)
        sung = {k: text for k, text in song.items() if k != 5}

        result = _fit_lrc(lrc, _heard(sung))

        assert result.status == FITS
        assert abs(result.shift_s + lead) < 0.05
        assert result.dropped == 1  # the line wholly before the clip
        texts, _ = cue_spans_from_srt(result.srt)
        assert len(texts) == result.total == 32
        # The two before lines that overlap the clip's start and the unheard line 5.
        assert result.flagged == (0, 1, 7)
        assert texts[7] == song[5]

    def test_a_refused_fit_flags_nothing(self):
        song = _song()

        result = _fit_lrc(_lrc(song), _heard({0: "completely unrelated words here ok"}))

        assert result.status == REFUSED
        assert result.flagged == ()

    def test_the_two_streams_are_flagged_on_their_own(self):
        song = _song()
        sung = {k: text for k, text in song.items() if not 4 <= k < 8}

        full = fit_slice(lrc_to_srt(_lrc(song)), {TRANSCRIBE: _heard(song)}, 300.0)
        gap = fit_slice(lrc_to_srt(_lrc(song)), {ASR: _heard(sung)}, 300.0)

        assert (full.flagged, gap.flagged) == ((), (4, 5, 6, 7))

    @staticmethod
    def _video_repeating(song, first: int, last: int) -> list[dict]:
        """Heard words of a video that sings lines ``first..last`` twice; the LRC has them once."""
        order = [*range(last + 1), *range(first, last + 1), *range(last + 1, len(song))]
        words = []
        for slot, k in enumerate(order):
            start = _clip_start(slot)
            words += [
                {"norm": tok, "start": start + i * 0.6} for i, tok in enumerate(song[k].split())
            ]
        return words

    def test_what_the_flags_do_for_an_extra_repeat(self):
        """A record for GATE A, not a requirement: the spread check passes every one of these.

        The flags mark whichever side of the repeat holds the minority of lines, since
        the median timing follows the majority. A repeat late in the song flags the
        lines after it; a repeat in the middle flags the lines before it.
        """
        song = _song()
        recorded = {}
        for first, last in ((24, 27), (14, 17), (4, 7)):
            result = _fit_lrc(_lrc(song), self._video_repeating(song, first, last))
            assert result.status == FITS
            recorded[(first, last)] = (result.shift_s, result.flagged)

        assert recorded == {
            (24, 27): (0.0, (28, 29)),
            (14, 17): (20.0, tuple(range(14))),
            (4, 7): (20.0, (0, 1, 2, 3)),
        }


class TestFlaggedRuns:
    def test_runs_at_least_min_run_long_are_reported_first_to_last(self):
        assert flagged_runs((2, 3, 4, 9, 10, 11, 12), 3) == [(2, 4), (9, 12)]

    def test_a_shorter_run_is_left_out(self):
        assert flagged_runs((2, 3, 9, 10, 11), 3) == [(9, 11)]

    def test_a_run_exactly_min_run_long_counts(self):
        assert flagged_runs((5, 6, 7), 3) == [(5, 7)]

    def test_a_run_at_the_start_and_one_at_the_end(self):
        assert flagged_runs((0, 1, 2, 7, 8, 9), 3) == [(0, 2), (7, 9)]

    def test_lines_that_skip_a_number_are_not_one_run(self):
        assert flagged_runs((1, 2, 4, 5), 3) == []

    def test_a_min_run_of_one_reports_every_line(self):
        assert flagged_runs((1, 4, 5), 1) == [(1, 1), (4, 5)]

    def test_nothing_flagged_has_no_runs(self):
        assert flagged_runs((), 3) == []
