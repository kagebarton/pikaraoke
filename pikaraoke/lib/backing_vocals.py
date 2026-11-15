"""Parentheses on karaoke lines: which of a caption or LRC sheet's groups were sung, and
showing the parentheses a line's display text carries.

Caption and LRC sheets put backing vocals in parentheses ("(oh, oh, oh)") beside stage
directions ("(upbeat music)"). The cue cleaners delete both; :func:`judge` tells them apart by
the transcript: a group is kept when the transcriber heard its words inside its cue's time
window. The rule, its pad and its vocable list are the ones measured and ruled at GATE A of
``plans/backing-vocal-lines.md`` (``none +vocables +consist``); the constants below are copied
from the measuring script, not re-derived.

Pure functions over the sheet's groups (:func:`pikaraoke.lib.srt_cues.sheet_parens`) and the
transcript, so the aligner never sees a parenthesis: :func:`with_backing` joins the kept words
to the song's lines bare, and :func:`show_parens` puts the parentheses back on the aligned words
afterwards, for Genius and custom lines too, whose display text keeps them.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from pikaraoke.lib.srt_cues import ParenCue, ParenGroup
from pikaraoke.lib.token_align import _match_simple, _normalize_token

# The bundle's ``lyrics.origin`` of the sheets the rule was measured on: a YouTube caption and
# an LRCLIB record. Movie and custom sheets were not measured. Spelled here because the
# align stage cannot import ``library_regen``; a test ties it to ``LRC_ORIGIN``.
ORIGINS = frozenset({"srt", "lrclib_srt"})

# Seconds added to each side of a cue's window, which is moved by the song's display lead.
WINDOW_PAD_S = 0.5
# The share of a group's distinct words the window must hold.
MIN_SHARE = 0.5

# A group made only of these is sung wherever the transcriber missed it: vocables sit under
# the lead and transcribers are least reliable on them.
VOCABLES = frozenset(
    "oh ohh ooh ah ahh uh mm mmm hmm woo whoa la na da ya yeah hey eh ay aye ha".split()
)

# Transcribers spell vocables loosely, so a heard word matches any member of its class.
_VOCABLE_CLASSES = {
    "O": "o oh ohh ohhh ooh oooh ooo oo woo wooh whoa woah wo ow",
    "A": "ah ahh aah ha hah uh uhh huh",
    "M": "mm mmm mmmm hmm hm mhm um",
    "Y": "yeah yea yeh ya yah ye yay",
    "H": "hey hei ay aye ayy eh ey",
    "L": "la na da du doo ba di dum",
}
_CLASS_OF = {word: name for name, words in _VOCABLE_CLASSES.items() for word in words.split()}

# Verdicts that show the group. The rest drop it: ``quote`` (a title card), ``not_heard``,
# ``unplaced`` (inline, no place in its line) and ``overlap`` (a paren-only cue over another
# line's time).
KEPT_VERDICTS = frozenset({"heard", "vocable", "consistency"})


@dataclass(frozen=True)
class Verdict:
    """One group's verdict. ``kind`` is ``"inline"`` or ``"paren_only"``; ``group`` indexes the
    cue's ``groups``; ``share`` is the heard share (0.0 when none was taken)."""

    cue: int
    group: int
    kind: str
    verdict: str
    share: float

    @property
    def kept(self) -> bool:
        return self.verdict in KEPT_VERDICTS


def judge(
    cues: Sequence[ParenCue],
    line_spans: Sequence[tuple[float, float]],
    heard_words: Sequence[dict],
    offset: float,
) -> list[Verdict]:
    """A verdict for every group of ``cues``, in sheet order.

    ``line_spans`` are today's lines' cue spans, ``heard_words`` the transcriber's words
    (``word``, ``start``, ``end``) on the audio clock and ``offset`` the display lead that
    moves a cue onto it. By evidence, first match wins:

    - ``quote``: opens with a quote mark, a title card ("Let It Go"). Never evidence for a repeat.
    - ``not_heard``: no word once normalised.
    - ``heard``: the window holds at least :data:`MIN_SHARE` of its distinct words. The line's
      own words count, and a vocable matches any of its class.
    - ``vocable``: every word is in :data:`VOCABLES`.
    - ``consistency``: the same text is ``heard`` or ``vocable`` elsewhere in the sheet.

    Then, as measured, and never evidence for a repeat: an inline group with no place in its line
    is ``unplaced``, and a paren-only cue over another line's cue time is ``overlap``, where
    "another line" is one of ``line_spans`` or a paren-only cue kept earlier in the sheet.
    """
    transcript = _transcript_tokens(heard_words)
    by_cue: list[list[Verdict]] = []
    for cue in cues:
        window = _window_tokens(transcript, cue.span, offset)
        kind = "inline" if cue.inline else "paren_only"
        by_cue.append(
            [
                Verdict(cue.index, g, kind, *_by_evidence(group.text, window))
                for g, group in enumerate(cue.groups)
            ]
        )
    heard_keys = {
        _text_key(group.text)
        for cue, verdicts in zip(cues, by_cue)
        for group, v in zip(cue.groups, verdicts)
        if v.verdict in ("heard", "vocable")
    }

    taken = list(line_spans)
    out: list[Verdict] = []
    for cue, verdicts in zip(cues, by_cue):
        verdicts = [
            replace(v, verdict="consistency")
            if v.verdict == "not_heard" and _text_key(group.text) in heard_keys
            else v
            for group, v in zip(cue.groups, verdicts)
        ]
        if cue.inline:
            verdicts = [
                replace(v, verdict="unplaced") if v.kept and cue.groups[v.group].at is None else v
                for v in verdicts
            ]
        elif any(v.kept for v in verdicts):
            if any(_overlap(cue.span, span) > 0 for span in taken):
                verdicts = [replace(v, verdict="overlap") if v.kept else v for v in verdicts]
            else:
                taken.append(cue.span)
        out.extend(verdicts)
    return out


@dataclass(frozen=True)
class GroupLine:
    """Where a kept group sits in the song's lines: its line, and its words as the
    ``[first, end)`` range of that line's align tokens."""

    line_id: int
    first: int
    end: int


@dataclass
class Backed:
    """A song's lines with the kept backing vocals in them.

    ``spans`` are the lines' cue spans, ``old_line_ids`` each line's id in today's list (None
    for an added line) and ``placed`` the line and tokens of each kept group, by ``(cue
    index, group index)``.
    """

    display_lines: list[str]
    align_lines: list[str]
    spans: list[tuple[float, float]]
    old_line_ids: list[int | None]
    placed: dict[tuple[int, int], GroupLine]

    def old_texts(
        self, display_lines: Sequence[str], align_lines: Sequence[str]
    ) -> tuple[list[str], list[str]]:
        """Today's lines (``display_lines``, ``align_lines``) with their kept words in and no
        added line: the lines the sections work on, before the renumbering."""
        display, align = list(display_lines), list(align_lines)
        for lid, new_display, new_align in zip(
            self.old_line_ids, self.display_lines, self.align_lines
        ):
            if lid is not None:
                display[lid], align[lid] = new_display, new_align
        return display, align


# A kept group: its cue's index, its place in that cue's groups, and the group.
_Kept = tuple[int, int, ParenGroup]


def with_backing(
    display_lines: Sequence[str],
    align_lines: Sequence[str],
    spans: Sequence[tuple[float, float]],
    cues: Sequence[ParenCue],
    verdicts: Sequence[Verdict],
) -> Backed:
    """Today's lines with the groups ``verdicts`` keep.

    An inline cue's kept groups go into its line at their place: the display line writes
    "Hey (hey!) you", the align line the same words bare, "Hey hey! you". A paren-only cue
    with a kept group becomes a line of its own before the line it precedes, at its cue's span:
    display "(oh, oh)", align "oh, oh". Today's tokens and every other line are untouched.
    """
    kept = {(v.cue, v.group) for v in verdicts if v.kept}
    inline: dict[int, list[_Kept]] = {}
    alone: dict[int, list[tuple[tuple[float, float], list[_Kept]]]] = {}
    for cue in cues:
        groups = [
            (cue.index, g, group) for g, group in enumerate(cue.groups) if (cue.index, g) in kept
        ]
        if not groups:
            continue
        if cue.inline:
            inline[cue.line] = groups
        else:
            alone.setdefault(cue.line, []).append((cue.span, groups))

    out = Backed([], [], [], [], {})
    for lid in range(len(display_lines) + 1):
        for span, groups in alone.get(lid, ()):
            _add_line(out, None, span, "", "", groups)
        if lid < len(display_lines):
            _add_line(
                out, lid, spans[lid], display_lines[lid], align_lines[lid], inline.get(lid, [])
            )
    return out


def _add_line(
    out: Backed,
    old_id: int | None,
    span: tuple[float, float],
    display: str,
    align: str,
    groups: list[_Kept],
) -> None:
    """Append a line to ``out``: ``display`` and ``align`` as they are, or with each of
    ``groups`` inserted at its place (a paren-only cue's groups all carry place 0, and follow
    one another)."""
    line_id = len(out.display_lines)
    if groups:
        display_tokens, align_tokens = display.split(), align.split()
        added = 0
        for cue_index, g, group in groups:
            words = group.text.split()
            at = group.at + added
            display_tokens[at:at] = _parenthesised(words)
            align_tokens[at:at] = words
            out.placed[(cue_index, g)] = GroupLine(line_id, at, at + len(words))
            added += len(words)
        display, align = " ".join(display_tokens), " ".join(align_tokens)
    out.display_lines.append(display)
    out.align_lines.append(align)
    out.spans.append(span)
    out.old_line_ids.append(old_id)


def _parenthesised(words: list[str]) -> list[str]:
    """``words`` with an opening parenthesis on the first and a closing one on the last."""
    return [
        ("(" if i == 0 else "") + word + (")" if i == len(words) - 1 else "")
        for i, word in enumerate(words)
    ]


def _by_evidence(text: str, window: list[str]) -> tuple[str, float]:
    """Verdict and heard share of one group against the words heard in its window."""
    if text.startswith('"'):
        return "quote", 0.0
    words = _tokens(text)
    if not words:
        return "not_heard", 0.0
    distinct = list(dict.fromkeys(words))
    share = sum(any(_same(w, heard) for heard in window) for w in distinct) / len(distinct)
    if share >= MIN_SHARE:
        return "heard", share
    if all(w in VOCABLES for w in words):
        return "vocable", share
    return "not_heard", share


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return min(a[1], b[1]) - max(a[0], b[0])


def _transcript_tokens(heard_words: Sequence[dict]) -> list[tuple[float, float, str]]:
    """Every normalised token of the transcript with its word's span."""
    return [
        (word["start"], word["end"], token)
        for word in heard_words
        for token in _tokens(word["word"])
    ]


def _window_tokens(
    transcript: list[tuple[float, float, str]], span: tuple[float, float], offset: float
) -> list[str]:
    """The transcript tokens whose word overlaps the cue's padded, shifted window."""
    w0 = span[0] + offset - WINDOW_PAD_S
    w1 = span[1] + offset + WINDOW_PAD_S
    return [token for start, end, token in transcript if end > w0 and start < w1]


def _tokens(text: str) -> list[str]:
    """Normalised words of ``text``, split at spaces, hyphens and slashes."""
    return [t for t in (_normalize_token(p) for p in re.split(r"[\s\-/]+", text)) if t]


def _same(word: str, heard: str) -> bool:
    if word in _CLASS_OF and _CLASS_OF[word] == _CLASS_OF.get(heard):
        return True
    return _match_simple(word, heard)


def _text_key(text: str) -> str:
    """A group's text as its repeats spell it: lower case, spacing and punctuation but
    apostrophes dropped."""
    return " ".join(re.sub(r"[^\w' ]+", " ", text.lower()).split())


def show_parens(
    line_objects: list[dict], display_lines: Sequence[str], align_lines: Sequence[str]
) -> list[dict]:
    """The line objects with each word's text as its display line writes it, parentheses
    included. Only ``word`` changes, never a time.

    The aligner and the matchers see a line's align text, which has no parentheses, so a word's
    text is one of its align tokens. A line whose display text equals its align text is left as
    it is. Otherwise the display tokens are paired with the align tokens in order, equal or
    equal once ``(`` and ``)`` are removed (a token of only parentheses sticks to its
    neighbour: ``(`` to the next token, ``)`` to the previous), and each word, in order, takes
    the display form of the next align token equal to it. A line that does not pair, and a word
    no token is left for, keep their text.
    """
    return [
        _show_line(obj, display_lines[obj["line_id"]], align_lines[obj["line_id"]])
        for obj in line_objects
    ]


def _show_line(obj: dict, display: str, align: str) -> dict:
    if not obj["words"] or display == align:
        return obj
    align_tokens = align.split()
    forms = _display_forms(display.split(), align_tokens)
    if forms is None:
        return obj
    words: list[dict] = []
    cursor = 0
    for word in obj["words"]:
        try:
            at = align_tokens.index(word["word"], cursor)
        except ValueError:
            words.append(word)
            continue
        words.append({**word, "word": forms[at]})
        cursor = at + 1
    return {**obj, "words": words}


def _display_forms(display: list[str], align: list[str]) -> list[str] | None:
    """The display tokens joined up so there is one per align token, None when they do not pair."""
    forms: list[str] = []
    opener = ""
    for token in display:
        if token.strip("()"):
            forms.append(opener + token)
            opener = ""
        elif forms and set(token) == {")"}:
            forms[-1] += token
        else:
            opener += token
    if opener and forms:
        forms[-1] += opener
    paired = len(forms) == len(align) and all(
        form.replace("(", "").replace(")", "") == token for form, token in zip(forms, align)
    )
    return forms if paired else None
