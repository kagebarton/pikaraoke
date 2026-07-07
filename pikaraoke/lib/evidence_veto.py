"""Demote align placements no other source and no vocal energy support.

The joint matcher's align source can win a line purely on its own timing —
zero transcribe overlap, zero ytasr agreement — when the forced aligner
smears lyric tokens over a span the singer never sang (an instrumental
break, an outro, a repeat). Rendered as karaoke that reads as text sweeping
over silence.

This post-pass is the upstream fix that onset_snap's ``MIN_REF_DB`` floor
only names ("not singing anywhere in the claimed span; an upstream
misplacement problem"). A zero-corroboration align line whose claimed span
is near-silent in the vocal stem is demoted to a word-less placeholder (the
ASS/SRT generators skip it), keeping ``start``/``end`` for debug. It only
demotes: it never moves, restores, or re-times a line, and it never touches
a line any other source or any vocal energy corroborates.
"""

import logging

import numpy as np

from pikaraoke.lib.onset_snap import HOP_S, MIN_REF_DB

logger = logging.getLogger(__name__)


def veto_uncorroborated_lines(
    line_objects: list[dict],
    env: np.ndarray,
) -> tuple[list[dict], dict]:
    """Demote zero-evidence align lines whose claimed span is near-silent.

    A veto candidate has words, ``source == "align"``, and an ``evidence``
    dict with ``transcribe_match == 0`` and ``ytasr_agreement == 0.0``. By
    construction only align-won objects can be zero-zero, so the source
    check is documentation; a missing ``evidence`` key (interp/cue objects)
    is never a candidate. When the median :func:`onset_snap.rms_envelope_db`
    level over the line's ``[start, end]`` sits below
    :data:`onset_snap.MIN_REF_DB` — the exact level onset_snap already
    treats as "not singing anywhere in the claimed span" — the line is
    demoted to a copy with ``words=[]`` and ``source="veto"``.

    Returns ``(line_objects, stats)``. ``stats["lines"]`` records every
    zero-evidence line's ``median_db`` whether vetoed or kept, so the GATE
    can judge whether the -45 dB floor sits right.
    """
    out: list[dict] = []
    lines: list[dict] = []
    n_zero_evidence = 0
    n_vetoed = 0
    for obj in line_objects:
        evidence = obj.get("evidence")
        if (
            not (obj.get("words") or [])
            or obj.get("source") != "align"
            or evidence is None
            or evidence["transcribe_match"] != 0
            or evidence["ytasr_agreement"] != 0.0
        ):
            out.append(obj)
            continue

        n_zero_evidence += 1
        lo = max(int(obj["start"] / HOP_S), 0)
        hi = min(int(obj["end"] / HOP_S) + 1, len(env))
        span = env[lo:hi]
        # A line past the envelope end slices empty — not silence evidence,
        # so keep it and record it for the GATE with no level.
        if len(span) == 0:
            lines.append({"line_id": obj.get("line_id"), "median_db": None, "vetoed": False})
            out.append(obj)
            continue

        median_db = float(np.median(span))
        vetoed = median_db < MIN_REF_DB
        lines.append(
            {"line_id": obj.get("line_id"), "median_db": round(median_db, 1), "vetoed": vetoed}
        )
        if vetoed:
            n_vetoed += 1
            demoted = dict(obj)
            demoted["words"] = []
            demoted["source"] = "veto"
            out.append(demoted)
        else:
            out.append(obj)

    stats = {"n_zero_evidence": n_zero_evidence, "n_vetoed": n_vetoed, "lines": lines}
    if n_vetoed:
        logger.info(
            "evidence veto: %d/%d zero-evidence align lines demoted over silence",
            n_vetoed,
            n_zero_evidence,
        )
    return out, stats
