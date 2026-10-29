"""Tests for the movie-subtitle slice fit (lib/srt_slice_fit.py), on synthetic cues."""

import json
from datetime import timedelta

import srt

from pikaraoke.lib import srt_slice_fit
from pikaraoke.lib.srt_slice_fit import (
    ASR,
    DISAGREE,
    FITS,
    NO_REFERENCE,
    NOT_SRT,
    REFUSED,
    TOO_FEW,
    TRANSCRIBE,
    fit_slice,
    free_speed,
    heard_streams,
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
