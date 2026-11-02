"""SRT cue utilities: cleaned cue texts/spans + offset calibration.

Shared helpers for working with uploader-synced SRT cue times:

- :func:`cue_spans_from_srt` returns each cleaned cue's text and its
  ``(start, end)`` span, positionally identical to the lyric lines the
  matcher consumes — the SRT cue-align path's line->time input. Speaker
  labels, ``*`` song markers and dialogue dashes are stripped, and a caption
  file typed in capitals comes back in sentence case.
- :func:`clean_cue_texts` is the per-cue cleaning on its own, one text per cue
  in its own position, and :func:`cues_to_srt` writes cleaned lines back as an
  SRT, so a sheet's words can be edited without moving a line's time.
- :func:`offset_mad_against_cues` fits the robust median display lead of a
  set of audio placements against a cue reference, with a MAD bail-out when
  the anchors are too few or too spread to trust a single constant offset.
  Pure calibration math, used to score placements against a held-out cue
  reference offline (the alpha/beta tuning harness).
"""

import re
from datetime import timedelta
from statistics import median

import srt

from pikaraoke.lib.genius_lyrics import clean_srt_line, strip_srt_markup

# A caption file this share of capitals (or more) was typed in all caps and is
# recased. Decided per file, so one shouted line in a normally cased file stays
# as written. In the library the all-caps file is 100% capitals and every other
# file is under 10%.
_ALL_CAPS_MIN_SHARE = 0.9

# Marks movie and TV subtitles put in front of or between the spoken words. They
# are display noise on the karaoke screen, and a speaker label is also a token
# that would be timed as sung.
#
# Decoration that may sit in front of a speaker label: dialogue dash, song star. Tags and
# note glyphs are gone by then (:func:`_strip_subtitle_marks`).
_LEADING_DECORATION = r"[-*\s]*"
# "MULAN:" or "MEN: ..." at a cue line's start. Capitals only, so a lyric like
# "Listen: ..." survives. Group 2 is the label, which :func:`_drop_label` checks.
_SPEAKER_LABEL_RE = re.compile(
    rf"^({_LEADING_DECORATION})([A-Z][A-Z0-9.'&/+ -]{{1,29}}):(?=\s|$)\s*"
)
# A dialogue dash: at a line start (after any decoration but a dash, as in "* - What?";
# letting the prefix take dashes too backtracks quadratically), with any dashes after it
# ("- - What?"), after a sentence end
# ("- Hakuna matata. - What?"), or glued to the next speaker's first word ("Be a man
# -With all"). Many releases write it glued ("-What?"); none of the library's subtitles
# split a word across cues ("-derful"). A spaced dash mid-sentence ("wait - what") stays.
# The glued dash's spaces start at a run's start: a match tried inside a long run rescans it.
_DIALOGUE_DASH_RE = re.compile(r"^([*\s]*)-[-\s]*|(?<=[.!?])\s+-+\s*|(?<!\s)\s+-+(?=[^\s-])")
# A "*" standing alone as a song marker; a censored "f***" keeps its stars.
_SONG_STAR_RE = re.compile(r"(?<!\S)\*+(?!\S)")

_PRONOUN_I_RE = re.compile(r"\bi\b")
# Line start or a mid-line sentence end, then the first letter after any
# leading punctuation (so "'til" becomes "'Til").
_SENTENCE_START_RE = re.compile(r"(^|[.!?]\s+)(\W*)([^\W\d_])")

# Fewer trusted anchors than this and the offset median is not robust;
# bail out and change nothing.
PRIOR_MIN_ANCHORS = 4

# Median absolute deviation of anchor residuals above this means the
# captions have a variable lead (or the anchors are unreliable); a
# single constant offset would mis-calibrate, so bail out. The corpus-wide
# anchor-residual MAD is well under this on every song with accurate
# captions.
PRIOR_MAX_MAD_S = 0.75


def cue_spans_from_srt(srt_text: str) -> tuple[list[str], list[tuple[float, float]]]:
    """Cleaned cue texts and their ``(start, end)`` spans in seconds.

    Applies the same per-cue cleanup as the lyric-align stage's SRT
    load (clean + drop empty), so the returned texts are positionally
    identical to the lyric lines the matcher consumed — the spans are
    the timing that load step throws away. See :func:`clean_cue_texts` for
    what the cleanup strips and recases.
    """
    cues = list(srt.parse(srt_text))
    cleaned = clean_cue_texts([sub.content for sub in cues])
    kept = [(text, sub) for text, sub in zip(cleaned, cues) if text]
    return (
        [text for text, _ in kept],
        [(sub.start.total_seconds(), sub.end.total_seconds()) for _, sub in kept],
    )


def clean_cue_texts(contents: list[str]) -> list[str]:
    """Each cue's cleaned text in its own position, ``""`` for one that cleans to nothing.

    Subtitle marks that are not words (speaker labels, ``*`` song markers,
    dialogue dashes) are stripped first. A file typed in capitals is recased
    too: on the cue route the aligner's text is the karaoke's word text, so
    display case can't be fixed downstream. The capitals rule is decided over
    the whole list, and speaker labels are left alone in such a file, where
    every line would look like one.
    """
    all_caps = _is_all_caps([clean_srt_line(content) for content in contents])
    cleaned = [_clean_cue(content, labels=not all_caps) for content in contents]
    return [_recase_line(text) for text in cleaned] if all_caps else cleaned


def _clean_cue(content: str, labels: bool) -> str:
    """One cue's text with its marks and noise stripped, cleaned again until it stops changing.

    One pass can leave a mark that the next would strip: a second label ("MEN: MARA: hey")
    or a second dash ("- - hey") exposed by the first one's removal. Without the repeats a
    cleaned line would not clean to itself. No step lengthens a text, so the repeats end.
    """
    text = clean_srt_line(_strip_subtitle_marks(content, labels))
    while (again := clean_srt_line(_strip_subtitle_marks(text, labels))) != text:
        text = again
    return text


def cues_to_srt(lines: list[str], spans: list[tuple[float, float]]) -> str:
    """One cue per line at its span: the inverse of :func:`cue_spans_from_srt` on cleaned lines.

    Cues are numbered here and kept in the given order: ``srt.compose``'s own
    renumbering would drop a zero-length cue and sort the rest by start, so a
    line the page shows could vanish or move on save.
    """
    return srt.compose(
        (
            srt.Subtitle(
                index=index,
                start=timedelta(seconds=start),
                end=timedelta(seconds=end),
                content=line,
            )
            for index, (line, (start, end)) in enumerate(zip(lines, spans, strict=True), start=1)
        ),
        reindex=False,
    )


def _strip_subtitle_marks(content: str, labels: bool) -> str:
    """Raw cue content with speaker labels, song stars and dialogue dashes removed.

    Works per cue line, since a label or dash is only a mark at a line's start. Tags and
    stage directions go first, so a label behind them ("(softly) MARA: hey",
    "<i>MEN:</i> go") is at its line's start, on any line of the cue.
    """
    lines = []
    for line in strip_srt_markup(content).split("\n"):
        if labels:
            line = _SPEAKER_LABEL_RE.sub(_drop_label, line)
        line = _DIALOGUE_DASH_RE.sub(r"\1 ", line)
        lines.append(_SONG_STAR_RE.sub("", line))
    return "\n".join(lines)


def _drop_label(match: re.Match[str]) -> str:
    """A speaker label's match without the label, or kept whole when sentence case writes it
    as it stands.

    A file typed in capitals keeps its labels and is recased. Its "U2:" or "I I:" comes out
    unchanged, and the next cleaning, which no longer sees a file in capitals, must not take
    it for a label. "MULAN:", "R2-D2:" and "M.I.A.:" recase to something else and are labels.
    """
    label = match.group(2)
    return match.group(0) if _recase_line(label) == label else match.group(1)


def _is_all_caps(texts: list[str]) -> bool:
    """True when the file is typed in capitals.

    The share is taken over *every* letter, not only the cased ones. A
    caseless script has no lower case to dilute it, so counting only cased
    letters let a Mandarin caption's handful of Latin acronyms (DJ, KTV)
    read as a 100% capitalized file and get "recased" to lower case.
    """
    letters = [c for text in texts for c in text if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) >= _ALL_CAPS_MIN_SHARE


def _recase_line(text: str) -> str:
    """Sentence case for a line typed in capitals.

    Capitalizes "I" (and I'm, I'll...) and the first letter of the line and
    of any sentence inside it. Names can't be told apart from ordinary words
    and come out lowercase.
    """
    text = _PRONOUN_I_RE.sub("I", text.lower())
    return _SENTENCE_START_RE.sub(lambda m: m.group(1) + m.group(2) + m.group(3).upper(), text)


def offset_mad_against_cues(
    anchors: list[dict], cue_spans_by_line: dict[int, tuple[float, float]]
) -> dict:
    """Median offset + MAD of placed anchor starts vs cue starts.

    Pure calibration math, no mutation or logging. Scores a set of placements
    against an external cue reference (e.g. an offline held-out comparison in
    the tuning harness): the median display lead over anchor lines that have a
    cue, plus a MAD bail-out.

    Returns ``{"n_anchors_fit", "bailed", "offset_s", "mad_s"}``. ``bailed``
    is ``"few_anchors"`` when fewer than :data:`PRIOR_MIN_ANCHORS` anchors
    have a cue (``offset_s``/``mad_s`` absent), ``"wide_spread"`` when the
    residual MAD exceeds :data:`PRIOR_MAX_MAD_S` (present but unreliable),
    or ``None`` when the calibration is trustworthy.
    """
    residuals = [
        a["start"] - cue_spans_by_line[a["lid"]][0]
        for a in anchors
        if a["lid"] in cue_spans_by_line
    ]
    stats: dict = {"n_anchors_fit": len(residuals), "bailed": None}
    if len(residuals) < PRIOR_MIN_ANCHORS:
        stats["bailed"] = "few_anchors"
        return stats

    offset = median(residuals)
    mad = median(abs(r - offset) for r in residuals)
    stats["offset_s"] = round(offset, 3)
    stats["mad_s"] = round(mad, 3)
    if mad > PRIOR_MAX_MAD_S:
        stats["bailed"] = "wide_spread"
    return stats
