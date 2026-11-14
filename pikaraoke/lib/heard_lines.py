"""Where the transcriber heard each lyric line, and whether a placed line agrees.

The cue route times lines from their caption cues; the transcriber (the de-reverb
gate's whisper pass) hears the same audio without them. Where the two disagree on a
line, the cue rescue (:func:`cue_align.repace_bad_lines`) used to side with the cue.
This module is the other reference: one whole-song match of the heard words to the
sheet's tokens (:func:`heard_lines`) and a test of whether a line object sits on the
words heard for it (:func:`confirms`). Pure, and it must not import ``cue_align``,
which imports it.
"""

from dataclasses import dataclass

from pikaraoke.lib.joint_match import _tokenise_lines
from pikaraoke.lib.token_align import (
    INSTANT_WORD_DUR_S,
    MIN_LINE_COVERAGE,
    _normalize_token,
    _token_expected_times,
    match_words_to_tokens,
)

# A line is heard, and a placement confirmed, on at least this many words. One matching
# word is too easy to find by chance in a song full of "the" and "oh".
HEARD_MIN_WORDS = 2

# A placed word and the word heard for it agree when their starts are this close. Looser
# than the transcriber's own jitter on a clean sung word, tight enough that a line placed
# on the wrong repeat (seconds off) never agrees.
HEARD_AGREE_S = 1.0


@dataclass(frozen=True)
class HeardLine:
    """The heard words matched to one line, in order, and whether its first token is one."""

    words: tuple[dict, ...]
    first: bool

    @property
    def start(self) -> float:
        return self.words[0]["start"]


def heard_lines(
    align_lines: list[str],
    spans: list[tuple[float, float]],
    heard_words: list[dict] | None,
) -> list[HeardLine | None]:
    """The heard line for each of ``align_lines``, or None where it was not heard.

    ``spans`` are the lines' cue spans on the audio clock (offset already applied); they
    only pace each token's expected time, which decides between twins when a word repeats
    (:func:`token_align.match_words_to_tokens`). A line is heard when it has at least two
    tokens and at least :data:`HEARD_MIN_WORDS` of them, and :data:`MIN_LINE_COVERAGE` of
    them, matched. A line with one token is never heard: a single matching word proves
    nothing. A line without a span (``spans`` shorter than ``align_lines``) is not heard.
    """
    line_toks = _tokenise_lines(align_lines)
    heard: list[HeardLine | None] = [None] * len(line_toks)
    if not heard_words:
        return heard
    token_norms: list[str] = []
    token_times: list[float] = []
    for toks, (c0, c1) in zip(line_toks, spans):
        token_norms.extend(norm for norm, _raw in toks)
        token_times.extend(_token_expected_times(len(toks), c0, c1))
    assign = match_words_to_tokens(
        token_norms,
        token_times,
        [_normalize_token(w["word"]) for w in heard_words],
        [w["start"] for w in heard_words],
    )
    k = 0
    for lid, (toks, _span) in enumerate(zip(line_toks, spans)):
        hits = assign[k : k + len(toks)]
        k += len(toks)
        words = tuple(heard_words[wi] for wi in hits if wi is not None)
        if (
            len(toks) >= 2
            and len(words) >= HEARD_MIN_WORDS
            and len(words) >= MIN_LINE_COVERAGE * len(toks)
        ):
            heard[lid] = HeardLine(words, first=hits[0] is not None)
    return heard


def runs_heard(line_toks: list[list[tuple[str, str]]], heard: list[HeardLine | None]) -> list[bool]:
    """Per line: not in a run of identical lines, or every line of its run was heard.

    A run is the maximal stretch of adjacent lines with equal normalised text. Heard words
    cannot say which line of a run they belong to unless the transcriber heard them all,
    so a placement in a run is confirmed only when the whole run is.
    """
    norms = [" ".join(norm for norm, _raw in toks) for toks in line_toks]
    flags = [True] * len(norms)
    lo = 0
    while lo < len(norms):
        hi = lo + 1
        while hi < len(norms) and norms[hi] == norms[lo]:
            hi += 1
        if norms[lo] and hi - lo > 1:
            flags[lo:hi] = [all(h is not None for h in heard[lo:hi])] * (hi - lo)
        lo = hi
    return flags


def pair_offsets(obj: dict, n_tokens: int, heard: HeardLine | None) -> list[float] | None:
    """How far after its placed word each word heard for ``obj``'s line starts (negative:
    before), one per pair, or None when the line was not heard or too few words pair.

    The line's timed words (at least :data:`INSTANT_WORD_DUR_S` long) are paired in order
    with its heard words by equal normalised text. A zero-length word is a failed
    alignment, so it pairs with nothing and neither confirms nor contradicts. Too few is
    under :data:`HEARD_MIN_WORDS` pairs or under :data:`MIN_LINE_COVERAGE` of the
    ``n_tokens`` tokens.
    """
    if heard is None:
        return None
    timed = [w for w in obj["words"] if w["end"] - w["start"] >= INSTANT_WORD_DUR_S]
    assign = match_words_to_tokens(
        [_normalize_token(w["word"]) for w in timed],
        [w["start"] for w in timed],
        [_normalize_token(w["word"]) for w in heard.words],
        [w["start"] for w in heard.words],
    )
    offsets = [
        heard.words[wi]["start"] - w["start"] for w, wi in zip(timed, assign) if wi is not None
    ]
    if len(offsets) < HEARD_MIN_WORDS or len(offsets) < MIN_LINE_COVERAGE * n_tokens:
        return None
    return offsets


def confirms(obj: dict, n_tokens: int, heard: HeardLine | None, run_heard: bool) -> bool:
    """Whether line object ``obj`` sits on the words heard for its line.

    It is confirmed when the line is heard, its run was heard (``run_heard``), enough of
    its words pair with the heard words (:func:`pair_offsets`) and every pair's starts are
    within :data:`HEARD_AGREE_S`.
    """
    if not run_heard:
        return False
    offsets = pair_offsets(obj, n_tokens, heard)
    return offsets is not None and all(abs(off) <= HEARD_AGREE_S for off in offsets)
