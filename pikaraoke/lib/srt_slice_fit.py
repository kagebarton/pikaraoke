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
first shift and speed (a 25 fps subtitle file against a 23.976 fps film drifts
about 8 s over three minutes). Pass 2 re-matches with the cues' expected times
mapped through that fit, which hands a repeated chorus line to the right
instance, and fits the speed and shift again from its own matches.

An LRCLIB match's synced lyrics fit the same way (:func:`lrc_to_srt` makes them
subtitles), and a fit also marks the lines heard far from their fitted time and
the lines nothing was heard for.
"""

import itertools
import logging
from dataclasses import dataclass
from datetime import timedelta
from statistics import median
from typing import NamedTuple

import srt

from pikaraoke.lib import lrclib
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
TOO_LONG = "too_long"

# The most cues the fit takes on. A whole film's SRT runs 900-1,800 cues and fits
# as well as the song's own stretch does. The match costs about a millisecond a
# cue on a desktop CPU, on both the preview and the Repair POST
# (plans/movie-subtitle-slice.md, Results rows 24-25).
MAX_CUES = 3000

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

# Speed factors tried first: none, and the PAL speed-up (25 fps release of a
# 23.976 fps film) with its reverse. A free speed is fitted to the anchors too,
# because real clips run at other speeds (two Beauty and the Beast clips at about
# 1.07). It replaces the best factor when it has less spread and, if that factor
# passed, also moves the cues by more than MIN_FREE_SPEED_DRIFT_S; the spread
# limit vets it as it vets a factor. Measured rates: plans/movie-subtitle-slice.md,
# Results rows 14-15.
SPEED_FACTORS = (1.0, 25 / 23.976, 23.976 / 25)

# A free speed further than this from 1 is not believed.
MAX_FREE_SPEED_CHANGE = 0.1

# Anchors this close in cue time give a noisy slope, so their pair is skipped.
MIN_SLOPE_SEPARATION_S = 20.0

# A free speed with less spread replaces a passing factor only when it moves the
# cues by more than this many seconds across the stretch the anchors were heard
# over. A free speed is only as precise as that stretch, so over it noise in the
# heard times fakes a gap about the size of the jitter, and a smaller gap would
# swap a right factor for a wrong speed. Measured over the whole clip instead,
# noise from a short cluster of anchors would look like a real drift.
MIN_FREE_SPEED_DRIFT_S = 0.75

# A cue counts as found when at least this share of its tokens matched a heard
# word, so one stray "the" is not a hit.
FOUND_MIN_TOKEN_SHARE = 0.5

# Fits when the share of in-clip cues found reaches this. Calibrated on eight real
# slices (plans/movie-subtitle-slice.md, GATE B): right-song fits found 41-100%,
# the sparse ASR stream being the low end; wrong-song runs at most 6%. A
# low share with a tight spread is still a right fit: the cues nobody heard keep
# the subtitles' own (shifted) times.
MIN_MATCHED_SHARE = 0.25

# A fitted line is mistimed when the heard words put its start more than this many
# seconds from where the fit puts it. Set at GATE A of plans/lyric-source-lists.md
# on the 17 joint songs: the two LRCs timed to another edit had lines 14-23 s off;
# on the rest no line was off by more than 9 s, and nearly all by 4 s or less.
FLAG_TOLERANCE_S = 5.0

# The fewest mistimed lines that make a flagged run, the warning shown before an
# LRC times a song. A cut verse or an extra repeat moves every line on one side of
# it; a single mistimed line is a repeated phrase matched to its other instance.
MIN_FLAGGED_RUN = 2

# The shortest stretch of unheard lines worth a note. Nothing was heard there, so
# the fit could not check those lines; a single unheard line is an ad-lib, a
# chant or a line in another language the transcriber skipped.
MIN_UNHEARD_RUN = 3


@dataclass(frozen=True)
class SliceFit:
    """The check's answer. Fields past ``status`` are 0/None when not known.

    ``matched`` and ``total`` count cleaned cues: once the time map is known,
    ``total`` is the cues that land inside the clip (``dropped`` more fall wholly
    outside); before that it is every cue pasted (on ``too_long``, as parsed).
    ``shift_s`` and ``speed`` are the time map (``clip_t = speed * movie_t +
    shift_s``), the shift unreliable on a ``disagree`` refusal. ``move_s`` is how
    far the first cue inside the clip moves, which a speed change sets apart from
    ``shift_s``. ``srt`` is the corrected slice text. ``heard_source`` and
    ``spread_s`` (median absolute deviation of the anchors) are diagnostics for
    the calibration report. ``lines``, ``mistimed`` and ``unheard`` are set on
    ``fits`` only. ``lines`` are the cleaned lines inside the clip (cues cleaned to
    nothing are not lines), each as ``(text, clip-time start)``; ``mistimed`` and
    ``unheard`` are indexes into them: the lines heard more than ``FLAG_TOLERANCE_S``
    from their fitted start, and those nothing was heard for. The flags carry their
    own lines because cleaning ``srt`` again can number them differently: whether a
    file is typed in capitals, which decides speaker labels, is judged over the cues
    it holds.
    """

    status: str
    reason: str | None = None
    matched: int = 0
    total: int = 0
    shift_s: float = 0.0
    speed: float = 1.0
    move_s: float = 0.0
    dropped: int = 0
    srt: str | None = None
    heard_source: str | None = None
    spread_s: float | None = None
    anchors: int = 0
    lines: tuple[tuple[str, float], ...] = ()
    mistimed: tuple[int, ...] = ()
    unheard: tuple[int, ...] = ()


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
        except (ValueError, AttributeError, TypeError) as e:
            logger.warning("Slice fit: the ASR caption is not readable json3 (%s), ignoring it", e)
            asr_words = []
        if asr_words:
            streams[ASR] = [{"norm": w["norm"], "start": w["start"]} for w in asr_words]
    return streams


def lrc_to_srt(lrc_text: str) -> str:
    """The synced lines of an LRC as SRT text, so :func:`fit_slice` takes them as subtitles.

    LRC stamps only starts: each line ends at the next start, and the last holds
    ``LRC_LAST_LINE_HOLD_S``. Lines stamped at the same start (a duet's two singers)
    share one cue, as a two-line subtitle does; a cue of no length would be dropped.
    An LRC with no timed line gives ``""``, which ``fit_slice`` refuses as ``not_srt``.
    """
    texts, spans = lrclib.cue_spans_from_lrc(lrc_text)
    cues: list[srt.Subtitle] = []
    for text, (start, end) in zip(texts, spans):
        if cues and cues[-1].start.total_seconds() == start:
            cues[-1].content += "\n" + text
            cues[-1].end = timedelta(seconds=end)
        else:
            cues.append(
                srt.Subtitle(
                    index=0,
                    start=timedelta(seconds=start),
                    end=timedelta(seconds=end),
                    content=text,
                )
            )
    return srt.compose(cues)


def flagged_runs(
    mistimed: tuple[int, ...], unheard: tuple[int, ...], min_run: int
) -> list[tuple[int, int]]:
    """The runs of at least ``min_run`` mistimed lines, as ``(first, last)`` mistimed line.

    Only a line heard near its fitted time ends a run: an unheard line between two
    mistimed ones says nothing either way, so the run goes on past it.
    """
    runs: list[tuple[int, int]] = []
    current: list[int] = []

    def close() -> None:
        if len(current) >= min_run:
            runs.append((current[0], current[-1]))
        current.clear()

    skipped = set(unheard)
    for line in range(max(mistimed, default=-1) + 1):
        if line in mistimed:
            current.append(line)
        elif line not in skipped:
            close()
    close()
    return runs


def unheard_runs(unheard: tuple[int, ...], min_run: int) -> list[tuple[int, int]]:
    """The runs of consecutive ``unheard`` lines at least ``min_run`` long, as ``(first, last)``."""
    runs = []
    for _, group in itertools.groupby(enumerate(unheard), key=lambda pair: pair[1] - pair[0]):
        lines = [line for _, line in group]
        if len(lines) >= min_run:
            runs.append((lines[0], lines[-1]))
    return runs


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
    if len(raw_cues) > MAX_CUES:
        return SliceFit(TOO_LONG, total=len(raw_cues))
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
    """The cues' cleaned texts, and their normalised tokens per cue and flat (with the cue each
    came from)."""

    texts: list[str]
    per_cue: list[list[str]]
    norms: list[str]
    cue_of: list[int]

    @classmethod
    def of(cls, texts: list[str]) -> "_CueTokens":
        per_cue = [[norm for norm, _ in toks] for toks in _tokenise_lines(texts)]
        return cls(
            texts,
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

    speed, stats = pass1
    anchors, found = _match_by_time(tokens, spans, speed, stats["offset_s"], words)
    pass2 = _best_speed(anchors, spans)
    if pass2 is None:
        return SliceFit(REFUSED, reason=TOO_FEW, total=n_cues, heard_source=name)
    speed, stats = pass2
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
    first = min((spans[k][0] for k in inside), default=0.0)
    base = {
        "matched": matched,
        "total": len(inside),
        "shift_s": shift,
        "speed": speed,
        "move_s": (speed - 1) * first + shift,
        "dropped": n_cues - len(inside),
        **common,
    }
    if not inside or matched / len(inside) < MIN_MATCHED_SHARE:
        return SliceFit(REFUSED, reason=TOO_FEW, **base)
    in_clip = sorted(inside)
    return SliceFit(
        FITS,
        srt=_corrected_srt(raw_cues, speed, shift, video_length),
        lines=tuple(
            (tokens.texts[k], _clip_span(*spans[k], speed, shift, video_length)[0]) for k in in_clip
        ),
        **_flagged_lines(in_clip, anchors, spans, speed, shift),
        **base,
    )


def _flagged_lines(
    in_clip: list[int],
    anchors: list[dict],
    spans: list[tuple[float, float]],
    speed: float,
    shift: float,
) -> dict[str, tuple[int, ...]]:
    """The ``in_clip`` cues (indexes into ``spans``) the heard words do not bear out.

    Returns :class:`SliceFit`'s ``mistimed`` (the anchor sits more than
    FLAG_TOLERANCE_S from the start the fit gives the cue) and ``unheard`` (no
    anchor), numbering the cues by their place in ``in_clip``, as ``lines`` is.
    """
    heard = {anchor["lid"]: anchor["start"] for anchor in anchors}
    mistimed = tuple(
        line
        for line, k in enumerate(in_clip)
        if k in heard and abs(heard[k] - (speed * spans[k][0] + shift)) > FLAG_TOLERANCE_S
    )
    unheard = tuple(line for line, k in enumerate(in_clip) if k not in heard)
    return {"mistimed": mistimed, "unheard": unheard}


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


class _SpeedFit(NamedTuple):
    """A speed and the offset stats of the anchors under it."""

    speed: float
    stats: dict

    @property
    def rank(self) -> tuple[bool, float]:
        """Lower is better: a fit within the spread limit, then the least spread."""
        return self.stats["bailed"] is not None, self.stats["mad_s"]


def _fit_at(anchors: list[dict], spans: list[tuple[float, float]], speed: float) -> _SpeedFit:
    return _SpeedFit(speed, offset_mad_against_cues(anchors, _scaled(spans, speed)))


def _best_speed(anchors: list[dict], spans: list[tuple[float, float]]) -> _SpeedFit | None:
    """The speed to fit at and its offset stats; None when too few anchors.

    Prefers a factor that did not bail, then the least spread of those that
    bailed on spread, so pass 2 can still try to repair a first mismatch. Ties
    keep the earlier factor, so no speed change wins a tie. A free speed takes
    over from a factor that bailed whenever it has less spread, and from one that
    passed only when it also moves the cues by more than MIN_FREE_SPEED_DRIFT_S.
    """
    factors = [_fit_at(anchors, spans, speed) for speed in SPEED_FACTORS]
    if factors[0].stats["bailed"] == "few_anchors":
        return None
    best = min(factors, key=lambda fit: fit.rank)
    free = free_speed(anchors, spans)
    if free is None or abs(free - 1) > MAX_FREE_SPEED_CHANGE:
        return best
    candidate = _fit_at(anchors, spans, free)
    if candidate.rank < best.rank and (
        best.stats["bailed"] or _drift_s(anchors, best.speed, free) > MIN_FREE_SPEED_DRIFT_S
    ):
        return candidate
    return best


def _drift_s(anchors: list[dict], a: float, b: float) -> float:
    """Seconds the speeds ``a`` and ``b`` move the cues apart across the heard anchors.

    The extent is taken over heard times, which all lie in the clip, so an anchor
    on a wrong line far down the paste cannot stretch it.
    """
    heard = [anchor["start"] for anchor in anchors]
    return abs(a - b) * (max(heard) - min(heard))


def free_speed(anchors: list[dict], spans: list[tuple[float, float]]) -> float | None:
    """Theil-Sen slope of anchor time against cue start; None with no pair far enough apart.

    The median of pairwise slopes shrugs off the few anchors a match gives the
    wrong line, where a least-squares slope would be dragged by them.
    """
    points = [(spans[a["lid"]][0], a["start"]) for a in anchors]
    slopes = [
        (h2 - h1) / (t2 - t1)
        for (t1, h1), (t2, h2) in itertools.combinations(points, 2)
        if abs(t2 - t1) > MIN_SLOPE_SEPARATION_S
    ]
    return median(slopes) if slopes else None


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
