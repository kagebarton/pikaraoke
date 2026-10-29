"""Where a pasted stretch of movie subtitles sits in a clip, and whether it fits.

A clip cut from a movie has the movie's soundtrack but not its subtitle times.
The admin pastes the stretch of the movie's SRT that the clip covers;
:func:`fit_slice` finds the time map ``clip_t = speed * movie_t + shift`` that
puts the pasted cues over the words already heard in the clip, and rewrites the
cues with clip times. Pure: the heard words and the clip length come in as
arguments (:func:`heard_streams` shapes what is on disk), nothing is read or
written here.

The match runs twice. Pass 1 matches by order only, because movie times and
clip times are an hour apart and a time tiebreak would be noise. It gives a
first shift and picks the speed (a 25 fps subtitle file against a 23.976 fps
film drifts about 8 s over three minutes). Pass 2 re-matches with the cues'
expected times mapped through that fit, which hands a repeated chorus line to
the right instance.
"""

import json
import logging
from dataclasses import dataclass
from datetime import timedelta

import srt

from pikaraoke.lib.cue_align import _token_expected_times
from pikaraoke.lib.joint_match import _tokenise_lines
from pikaraoke.lib.srt_cues import cue_spans_from_srt, offset_mad_against_cues
from pikaraoke.lib.token_align import _normalize_token, match_words_to_tokens
from pikaraoke.lib.ytasr import parse_json3

logger = logging.getLogger(__name__)

FITS = "fits"
REFUSED = "refused"
NO_REFERENCE = "no_reference"
NOT_SRT = "not_srt"

# Why a refused check refused. TOO_FEW: not enough of the cues were found in the
# clip's words to fit anything. DISAGREE: enough were found, but they do not
# agree on one timing (a clip cut from several scenes, or subtitles for another
# release).
TOO_FEW = "too_few"
DISAGREE = "disagree"

# Heard-word streams, each tried on its own: the bundle's whisper transcribe and
# the on-disk YouTube auto-caption. Never merged: overlapping duplicates would
# confuse an in-order match.
TRANSCRIBE = "transcribe"
ASR = "asr"

# Speed factors tried: none, and the PAL speed-up (25 fps release of a 23.976
# fps film) with its reverse. Free-form speed is ruled out: with few anchors it
# fits noise.
SPEED_FACTORS = (1.0, 25 / 23.976, 23.976 / 25)

# A cue counts as found when at least this share of its tokens matched a heard
# word, so one stray "the" is not a hit.
FOUND_MIN_TOKEN_SHARE = 0.5

# Fits when the share of in-clip cues found reaches this. Provisional: the value
# is set from the calibration table (plans/movie-subtitle-slice.md, GATE B).
MIN_MATCHED_SHARE = 0.5


@dataclass(frozen=True)
class SliceFit:
    """The check's answer. Fields past ``status`` are 0/None when not known.

    ``matched`` and ``total`` count cleaned cues: once the time map is known,
    ``total`` is the cues that land inside the clip (``dropped`` more fall wholly
    outside); before that it is every cue pasted. ``shift_s`` and ``speed`` are
    the time map (``clip_t = speed * movie_t + shift_s``), the shift unreliable
    on a ``disagree`` refusal. ``srt`` is the corrected slice text.
    ``heard_source`` and ``spread_s`` (median absolute deviation of the anchors)
    are diagnostics for the calibration report.
    """

    status: str
    reason: str | None = None
    matched: int = 0
    total: int = 0
    shift_s: float = 0.0
    speed: float = 1.0
    dropped: int = 0
    srt: str | None = None
    heard_source: str | None = None
    spread_s: float | None = None
    anchors: int = 0


def heard_streams(bundle: dict | None, asr_json3: str | None) -> dict[str, list[dict]]:
    """The word streams on disk as ``{name: [{norm, start}]}``, empty ones left out.

    ``bundle`` is the song's alignment bundle (``transcribe_words`` in it);
    ``asr_json3`` is the text of its ``subtitles/<stem>.en.asr.json3``.
    """
    streams: dict[str, list[dict]] = {}
    transcribe = [
        {"norm": norm, "start": w["start"]}
        for w in (bundle or {}).get("transcribe_words") or []
        if (norm := _normalize_token(w["word"]))
    ]
    if transcribe:
        streams[TRANSCRIBE] = transcribe
    if asr_json3:
        try:
            asr_words, _ = parse_json3(asr_json3)
        except json.JSONDecodeError:
            logger.warning("Slice fit: the ASR caption is not valid json3, ignoring it")
            asr_words = []
        if asr_words:
            streams[ASR] = [{"norm": w["norm"], "start": w["start"]} for w in asr_words]
    return streams


def fit_slice(srt_text: str, streams: dict[str, list[dict]], video_length: float) -> SliceFit:
    """Check whether the pasted ``srt_text`` fits the clip, and correct it if so.

    Each stream in ``streams`` (see :func:`heard_streams`) is fitted on its own
    and the better result kept. ``video_length`` is the clip's length in seconds.
    """
    try:
        raw_cues = list(srt.parse(srt_text))
    except (OverflowError, srt.SRTParseError):
        return SliceFit(NOT_SRT)
    if not raw_cues:
        return SliceFit(NOT_SRT)
    streams = {name: words for name, words in streams.items() if words}
    if not streams:
        return SliceFit(NO_REFERENCE)

    texts, spans = cue_spans_from_srt(srt_text)
    if not texts:
        return SliceFit(REFUSED, reason=TOO_FEW)
    tokens = _CueTokens.of(texts)
    fits = [
        _fit_one_stream(name, words, tokens, spans, raw_cues, video_length)
        for name, words in streams.items()
    ]
    return max(fits, key=lambda f: (f.status == FITS, f.matched))


@dataclass(frozen=True)
class _CueTokens:
    """The cues' normalised tokens, per cue and flat (with the cue each came from)."""

    per_cue: list[list[str]]
    norms: list[str]
    cue_of: list[int]

    @classmethod
    def of(cls, texts: list[str]) -> "_CueTokens":
        per_cue = [[norm for norm, _ in toks] for toks in _tokenise_lines(texts)]
        return cls(
            per_cue,
            [norm for toks in per_cue for norm in toks],
            [k for k, toks in enumerate(per_cue) for _ in toks],
        )


def _fit_one_stream(
    name: str,
    words: list[dict],
    tokens: _CueTokens,
    spans: list[tuple[float, float]],
    raw_cues: list[srt.Subtitle],
    video_length: float,
) -> SliceFit:
    n_cues = len(spans)
    anchors, _ = _match_by_order(tokens, words)
    pass1 = _best_speed(anchors, spans)
    if pass1 is None:
        return SliceFit(REFUSED, reason=TOO_FEW, total=n_cues, heard_source=name)

    speed, shift = pass1
    anchors, found = _match_by_time(tokens, spans, speed, shift, words)
    stats = offset_mad_against_cues(anchors, _scaled(spans, speed))
    if stats["bailed"] == "few_anchors":
        return SliceFit(REFUSED, reason=TOO_FEW, total=n_cues, heard_source=name)
    shift = stats["offset_s"]
    common = {"heard_source": name, "spread_s": stats["mad_s"], "anchors": stats["n_anchors_fit"]}
    if stats["bailed"]:
        return SliceFit(
            REFUSED,
            reason=DISAGREE,
            matched=len(found),
            total=n_cues,
            shift_s=shift,
            speed=speed,
            **common,
        )

    inside = {
        k
        for k, (start, end) in enumerate(spans)
        if _clip_span(start, end, speed, shift, video_length) is not None
    }
    matched = len(found & inside)
    base = {
        "matched": matched,
        "total": len(inside),
        "shift_s": shift,
        "speed": speed,
        "dropped": n_cues - len(inside),
        **common,
    }
    if not inside or matched / len(inside) < MIN_MATCHED_SHARE:
        return SliceFit(REFUSED, reason=TOO_FEW, **base)
    return SliceFit(FITS, srt=_corrected_srt(raw_cues, speed, shift, video_length), **base)


def _match_by_order(tokens: _CueTokens, words: list[dict]) -> tuple[list[dict], set[int]]:
    """Pass 1: match the cues to the heard words by order alone.

    Both streams get rank pseudo-times (0..1). Movie times can't be used yet: at
    an hour's distance the matcher's time tiebreak would be noise.
    """
    n_tok, n_word = len(tokens.norms), len(words)
    assign = match_words_to_tokens(
        tokens.norms,
        [(i + 0.5) / n_tok for i in range(n_tok)],
        [w["norm"] for w in words],
        [(j + 0.5) / n_word for j in range(n_word)],
    )
    return _cue_anchors(assign, tokens, words)


def _match_by_time(
    tokens: _CueTokens,
    spans: list[tuple[float, float]],
    speed: float,
    shift: float,
    words: list[dict],
) -> tuple[list[dict], set[int]]:
    """Pass 2: match again with each token's expected clip time under ``(speed, shift)``.

    The time tiebreak hands a repeated line to the instance the pass 1 fit puts
    it in, which order alone can get wrong.
    """
    expected: list[float] = []
    for toks, (start, end) in zip(tokens.per_cue, spans):
        if toks:
            expected += _token_expected_times(len(toks), speed * start + shift, speed * end + shift)
    assign = match_words_to_tokens(
        tokens.norms, expected, [w["norm"] for w in words], [w["start"] for w in words]
    )
    return _cue_anchors(assign, tokens, words)


def _cue_anchors(
    assign: list[int | None], tokens: _CueTokens, words: list[dict]
) -> tuple[list[dict], set[int]]:
    """Per-cue anchors and the set of found cues from a token->word assignment.

    A found cue has at least :data:`FOUND_MIN_TOKEN_SHARE` of its tokens
    matched; its anchor is the start of its first matched word.
    """
    first: dict[int, int] = {}
    hits: dict[int, int] = {}
    for word_idx, cue in zip(assign, tokens.cue_of):
        if word_idx is None:
            continue
        first.setdefault(cue, word_idx)
        hits[cue] = hits.get(cue, 0) + 1
    found = {
        k for k, n in hits.items() if n >= max(1, FOUND_MIN_TOKEN_SHARE * len(tokens.per_cue[k]))
    }
    anchors = [{"lid": k, "start": words[first[k]]["start"]} for k in sorted(found)]
    return anchors, found


def _scaled(spans: list[tuple[float, float]], speed: float) -> dict[int, tuple[float, float]]:
    return {k: (speed * start, speed * end) for k, (start, end) in enumerate(spans)}


def _best_speed(
    anchors: list[dict], spans: list[tuple[float, float]]
) -> tuple[float, float] | None:
    """``(speed, shift)`` with the smallest spread, or None when no anchors to fit.

    Prefers a factor that did not bail; failing that, the least spread of those
    that bailed on spread, so pass 2 can still try to repair a first mismatch.
    Ties keep the earlier factor, so no speed change wins a tie.
    """
    best: tuple[tuple[int, float], float, float] | None = None
    for speed in SPEED_FACTORS:
        stats = offset_mad_against_cues(anchors, _scaled(spans, speed))
        if stats["bailed"] == "few_anchors":
            return None
        key = (stats["bailed"] is not None, stats["mad_s"])
        if best is None or key < best[0]:
            best = (key, speed, stats["offset_s"])
    return best[1], best[2]


def _corrected_srt(raw_cues: list[srt.Subtitle], speed: float, shift: float, length: float) -> str:
    """The pasted cues on clip times: dropped when wholly outside, clamped at the edges.

    Cue text is kept as pasted; the pipeline's load step is the one cleaner.
    """
    out: list[srt.Subtitle] = []
    for cue in raw_cues:
        span = _clip_span(cue.start.total_seconds(), cue.end.total_seconds(), speed, shift, length)
        if span is not None:
            out.append(
                srt.Subtitle(
                    index=0,
                    start=timedelta(seconds=span[0]),
                    end=timedelta(seconds=span[1]),
                    content=cue.content,
                )
            )
    return srt.compose(out)


def _clip_span(
    start: float, end: float, speed: float, shift: float, length: float
) -> tuple[float, float] | None:
    """A movie-time span on clip time, clamped to the clip; None when none of it is left.

    The one rule for both counting a cue as inside the clip and writing it out.
    """
    start, end = max(speed * start + shift, 0.0), min(speed * end + shift, length)
    return (start, end) if end > start else None
