"""Joint alignment DP: align + transcribe + lyrics consumed in one matcher.

Two independent placements of the lyrics in time are always available:
forced alignment and a free transcribe pass. A third, optional placement
(YouTube auto-caption/YTASR words) can be supplied when present. Trusting
any single source everywhere is a degenerate answer to *which one do we
believe per line?* This matcher answers per-line by scoring every
available placement and letting an interval-scheduling DP pick.

Per lyric line we build up to three kinds of candidates:

* **align candidate.** One per line, at the time span forced alignment
  placed the line's tokens (read from ``align_words``). Has high
  ``align_agreement`` by construction. Its ``transcribe_match`` reflects
  how well transcribe corroborates align's placement — low for Hakuna-
  style dialogue mis-matches, high for clean lines.
* **transcribe candidates.** Found by fuzzy-matching the line's tokens
  against the transcribe word stream (the ``candidate_match.find_candidates``
  / ``find_anchor_candidates`` machinery). Each carries the matched-token
  count as ``transcribe_match`` and gets an ``align_agreement`` based on
  time overlap with align's predicted window for the same line.
* **ytasr candidates** (only when ``ytasr_words`` is supplied). Found by
  fuzzy-matching against the YTASR word stream the same way transcribe
  candidates are — YTASR has no 1:1 token guarantee with the lyric line
  the way align does, so it needs the same multi-candidate treatment as
  transcribe, not align's single-guaranteed-candidate treatment — but at
  the stricter ``ytasr.CANDIDATE_MAX_EDIT_RATIO``, since the ASR text is
  a ytasr candidate's only evidence for existing. Its ``ytasr_agreement``
  is its own graded match quality (matched-token fraction of the line);
  its ``transcribe_match`` and ``align_agreement`` are computed the same
  way align's are, against its own proposed window.

Each candidate's joint score is::

    score = transcribe_match + weight * (alpha * align_agreement + beta * ytasr_agreement)

where ``weight`` is the corroboration gate shared by both the alpha and
beta terms — it answers "does independent evidence support this specific
window," which is orthogonal to which source proposed the window. It
starts from transcribe's testimony (``_alpha_weight``: zero only when
transcribe heard substantial speech with no lexical overlap), but
transcribe is one fallible witness of three, so a zeroed gate can be
rescued 2-of-3 style by the other pair: when align and ytasr mutually
back the window, the bonus survives at the strength of that mutual
agreement (``_corroboration_weight``). When ``ytasr_words`` is not
supplied, ``ytasr_agreement`` is always 0, no rescue can fire, and the
formula reduces exactly to the two-source score.

The interval-scheduling DP (``_best_tiling_by_time``, a weighted
interval-scheduling pass over time intervals rather than token indices)
picks the maximum-score non-overlapping subset. Per-word timings come
from whichever source won each line — align's refined word timings when
the align candidate won (so clean-song precision is preserved exactly),
transcribe's or ytasr's word timestamps otherwise.

Lines with no selected candidate are interpolated between their bracketing
selected neighbours so the output is 1:1 with the lyric line list.
"""

import logging
from bisect import bisect_left

from pikaraoke.lib import ytasr
from pikaraoke.lib.candidate_match import (
    _build_line_object,
    find_anchor_candidates,
    find_candidates,
)
from pikaraoke.lib.token_align import _normalize_token

logger = logging.getLogger(__name__)

# Minimum width of an align candidate's selection window, in seconds. Forced
# alignment collapse (every lyric token of a run pinned to one timestamp)
# would otherwise produce zero-width candidates that the interval-scheduling
# DP can pick stacked together at the same instant. Padding to this minimum
# guarantees collapsed candidates conflict under non-overlap so the DP keeps
# at most one of them.
_MIN_ALIGN_WIDTH_S = 0.1


def match_words_to_lines_joint_with_stats(
    align_words: list[dict],
    transcribe_words: list[dict],
    lines: list[str],
    align_lines: list[str],
    *,
    alpha: float = 2.0,
    beta: float = 2.0,
    margin_s: float = 0.3,
    max_edit_ratio: float = 0.75,
    lookahead: int = 3,
    anchor_fallback: bool = True,
    ytasr_words: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    """Joint align + transcribe (+ optional ytasr) matcher.

    Args:
        align_words: refined whisper words from forced alignment. One entry
            per lyric token, in lyric order (the stable-ts align→refine
            output our worker emits).
        transcribe_words: whisper words from a free transcribe pass. Need
            not be refined; ``word_timestamps`` precision is sufficient.
        lines: display lyric lines (may contain inline parens, etc).
        align_lines: normalised lyric lines (paren-stripped upstream). Used
            for tokenisation; ``align_words`` is assumed to correspond
            1:1 with the flat token stream from ``align_lines``.
        alpha: weight on the align agreement term. Score formula is
            ``transcribe_match + weight * (alpha * align_agreement + beta *
            ytasr_agreement)``. Higher = trust align more (all-align on
            clean songs). Lower = trust transcribe more (all-transcribe on
            misaligned songs). The corpus-tuned default lives in
            ``PipelineConfig.joint_alpha``.
        beta: weight on the ytasr agreement term, symmetric to ``alpha``.
            Only has an effect when ``ytasr_words`` is supplied.
        margin_s: time slack on each side of a candidate's window when
            (a) deciding which transcribe words count as "inside" the
            window for ``transcribe_match`` computation, and (b) padding
            collapsed align candidates so the DP can reject them on
            non-overlap.
        max_edit_ratio: passed to ``find_candidates`` for the transcribe
            scan and to in-window corroboration scoring. Like ``alpha``,
            the corpus-tuned default lives in
            ``PipelineConfig.joint_max_edit_ratio``; signature defaults
            here mirror it. The ytasr candidate scan instead uses the
            stricter ``ytasr.CANDIDATE_MAX_EDIT_RATIO`` (see its comment).
        lookahead: passed to per-window per-word timing builder.
        anchor_fallback: if True, run ``find_anchor_candidates`` for lines
            that produced zero transcribe candidates in the main pass.
        ytasr_words: YouTube auto-caption words (same shape as
            ``transcribe_words``, plus a ``norm`` key — see
            ``ytasr.parse_json3``), or ``None`` to run the plain two-source
            matcher. When supplied, YTASR is treated as a third candidate
            source scored symmetrically to align/transcribe, not as a
            post-hoc timing prior.

    Returns:
        ``(line_objects, joint_stats)``. ``line_objects`` is one entry per
        lyric line (1:1, in lyric order). Each carries an explicit
        ``line_id`` back-reference into ``lines``. ``joint_stats`` records
        candidate counts, per-line selected source, and the knobs used —
        captured for offline tuning.
    """
    knobs = {
        "alpha": alpha,
        "beta": beta,
        "margin_s": margin_s,
        "max_edit_ratio": max_edit_ratio,
        "lookahead": lookahead,
        "anchor_fallback": anchor_fallback,
    }

    line_tokens = _tokenise_lines(align_lines)
    n_lines = len(lines)

    align_ranges = _line_align_ranges(line_tokens, align_words)

    transcribe_norms = [_normalize_token(w["word"]) for w in transcribe_words]
    line_norms = [[norm for norm, _raw in toks] for toks in line_tokens]

    main_cands = (
        find_candidates(transcribe_norms, line_norms, max_edit_ratio=max_edit_ratio)
        if transcribe_words
        else []
    )
    matched_main = {c[2] for c in main_cands}
    zero_cand_line_ids = sorted(
        lid for lid, toks in enumerate(line_norms) if toks and lid not in matched_main
    )
    anchor_cands: list = []
    if anchor_fallback and zero_cand_line_ids and transcribe_words:
        anchor_cands = find_anchor_candidates(transcribe_norms, line_norms, zero_cand_line_ids)

    ytasr_words = ytasr_words or []
    ytasr_cands: list = []
    ytasr_ranges: list[dict | None] = [None] * n_lines
    if ytasr_words:
        ytasr_norms = [w["norm"] for w in ytasr_words]
        # Full candidate list for the DP to arbitrate over (every hit kept),
        # at ytasr's own stricter ratio, NOT the transcribe knob: the ASR
        # text is a ytasr candidate's only evidence for existing (see
        # ytasr.CANDIDATE_MAX_EDIT_RATIO).
        ytasr_cands = find_candidates(
            ytasr_norms, line_norms, max_edit_ratio=ytasr.CANDIDATE_MAX_EDIT_RATIO
        )
        # Reference range for scoring *other* candidates' ytasr agreement:
        # the monotonic-filtered reduction (not best_candidate_per_line
        # directly) so a repeated chorus line can't have two different
        # line_ids collapse onto the same ytasr occurrence, which would
        # silently corrupt their agreement scores. Derived from the same
        # candidate list — no second scan of the ASR stream.
        for line_id, (t0, t1) in (
            ytasr.spans_from_candidates(ytasr_words, ytasr_cands) or {}
        ).items():
            ytasr_ranges[line_id] = {"t0": t0, "t1": t1}

    transcribe_candidates = _build_transcribe_candidates(
        main_cands + anchor_cands,
        transcribe_words,
        align_ranges,
        ytasr_ranges,
        alpha,
        beta,
    )

    align_candidates = _build_align_candidates(
        line_norms,
        align_ranges,
        transcribe_words,
        transcribe_norms,
        ytasr_ranges,
        margin_s,
        max_edit_ratio,
        alpha,
        beta,
    )

    ytasr_candidates = _build_ytasr_candidates(
        ytasr_cands,
        ytasr_words,
        line_norms,
        align_ranges,
        transcribe_words,
        transcribe_norms,
        margin_s,
        max_edit_ratio,
        alpha,
        beta,
    )

    # align first, then transcribe, then ytasr — ties (same score, same t1)
    # break in that order. Align's refined per-word timings are preferred
    # when sources agree; between transcribe and ytasr, transcribe is the
    # same-audio whisper-precision source, so it's preferred over ytasr's
    # lower-fidelity per-word split.
    all_candidates = align_candidates + transcribe_candidates + ytasr_candidates
    selected = _best_tiling_by_time(all_candidates)

    line_objects = _materialise_line_objects(
        selected,
        line_tokens,
        lines,
        align_words,
        transcribe_words,
        ytasr_words,
        align_ranges,
        lookahead,
    )

    line_objects = _interpolate_missing(line_objects, n_lines, align_words)

    selected_source = ["absent"] * n_lines
    for cand in selected:
        line_id = cand["line_id"]
        selected_source[line_id] = cand["source"]
    for obj in line_objects:
        if obj.get("source") == "interp" and selected_source[obj["line_id"]] == "absent":
            selected_source[obj["line_id"]] = "interp"

    align_won = sum(1 for s in selected_source if s == "align")
    transcribe_won = sum(1 for s in selected_source if s == "transcribe")
    ytasr_won = sum(1 for s in selected_source if s == "ytasr")
    interpolated = [i for i, s in enumerate(selected_source) if s == "interp"]
    absent = [i for i, s in enumerate(selected_source) if s == "absent"]

    stats = {
        "knobs": knobs,
        "n_lines": n_lines,
        "n_align_words": len(align_words),
        "n_transcribe_words": len(transcribe_words),
        "n_ytasr_words": len(ytasr_words),
        "n_main_candidates": len(main_cands),
        "n_anchor_candidates": len(anchor_cands),
        "n_align_candidates": len(align_candidates),
        "n_ytasr_candidates": len(ytasr_candidates),
        "n_selected": len(selected),
        "selected_source": selected_source,
        "align_won": align_won,
        "transcribe_won": transcribe_won,
        "ytasr_won": ytasr_won,
        "interpolated_line_ids": interpolated,
        "absent_line_ids": absent,
        "selected_score_sum": float(sum(c["score"] for c in selected)),
    }

    logger.info(
        "Joint match: %d/%d lines placed (align=%d transcribe=%d ytasr=%d "
        "interp=%d absent=%d) at alpha=%.2f beta=%.2f",
        n_lines - len(absent),
        n_lines,
        align_won,
        transcribe_won,
        ytasr_won,
        len(interpolated),
        len(absent),
        alpha,
        beta,
    )

    return line_objects, stats


def match_words_to_lines_joint(
    align_words: list[dict],
    transcribe_words: list[dict],
    lines: list[str],
    align_lines: list[str],
    *,
    alpha: float = 2.0,
    beta: float = 2.0,
    margin_s: float = 0.3,
    max_edit_ratio: float = 0.75,
    lookahead: int = 3,
    anchor_fallback: bool = True,
    ytasr_words: list[dict] | None = None,
) -> list[dict]:
    """Thin wrapper that drops the stats. See ``..._with_stats``."""
    line_objects, _ = match_words_to_lines_joint_with_stats(
        align_words,
        transcribe_words,
        lines,
        align_lines,
        alpha=alpha,
        beta=beta,
        margin_s=margin_s,
        max_edit_ratio=max_edit_ratio,
        lookahead=lookahead,
        anchor_fallback=anchor_fallback,
        ytasr_words=ytasr_words,
    )
    return line_objects


# ---------------------------------------------------------------------------
# Tokenisation + align-time ranges
# ---------------------------------------------------------------------------


def _tokenise_lines(align_lines: list[str]) -> list[list[tuple[str, str]]]:
    """Per-line list of ``(normalised, raw)`` tokens, dropping tokens that
    normalise to empty (punctuation, paren-stripped artefacts).

    The flat concatenation across lines is what ``align_words`` is assumed
    to correspond to 1:1 (forced alignment emits one word per lyric token).
    """
    out: list[list[tuple[str, str]]] = []
    for line in align_lines:
        toks: list[tuple[str, str]] = []
        for raw in line.split():
            norm = _normalize_token(raw)
            if norm:
                toks.append((norm, raw))
        out.append(toks)
    return out


def _line_align_ranges(
    line_tokens: list[list[tuple[str, str]]],
    align_words: list[dict],
) -> list[dict | None]:
    """Per-line align-time range and token-index slice into ``align_words``.

    Returns ``None`` for a line if the line has no tokens or if
    ``align_words`` runs out before the line's tokens are consumed (i.e.
    forced alignment dropped tokens — rare, but defended against).
    """
    out: list[dict | None] = []
    cursor = 0
    for toks in line_tokens:
        if not toks:
            out.append(None)
            continue
        n = len(toks)
        if cursor + n > len(align_words):
            out.append(None)
            continue
        slice_start = cursor
        slice_end = cursor + n
        t0 = align_words[slice_start]["start"]
        t1 = align_words[slice_end - 1]["end"]
        # Defend against tokens with start > end (rare; clamp).
        if t1 < t0:
            t1 = t0
        out.append(
            {
                "t0": t0,
                "t1": t1,
                "token_start": slice_start,
                "token_end": slice_end,
            }
        )
        cursor = slice_end
    return out


# ---------------------------------------------------------------------------
# Candidate construction
# ---------------------------------------------------------------------------


def _build_transcribe_candidates(
    tiling_cands: list,
    transcribe_words: list[dict],
    align_ranges: list[dict | None],
    ytasr_ranges: list[dict | None],
    alpha: float,
    beta: float,
) -> list[dict]:
    """Turn each tiling-style ``(start_idx, end_idx, line_id, score)`` into
    a joint candidate with its time interval and joint score.
    """
    out: list[dict] = []
    for start_idx, end_idx, line_id, t_score in tiling_cands:
        t0 = transcribe_words[start_idx]["start"]
        t1 = transcribe_words[end_idx - 1]["end"]
        a_agree = _range_agreement(t0, t1, align_ranges[line_id])
        y_agree = _range_agreement(t0, t1, ytasr_ranges[line_id])
        window_count = end_idx - start_idx
        # Transcribe candidates only exist because find_candidates accepted
        # them, so by construction at least one lyric token overlaps the
        # window. Pass True explicitly to keep the gate semantics consistent
        # with the align-candidate path.
        weight = _alpha_weight(t_score > 0, window_count)
        score = float(t_score) + weight * (alpha * a_agree + beta * y_agree)
        out.append(
            {
                "line_id": line_id,
                "source": "transcribe",
                "t0": t0,
                "t1": t1,
                "score": score,
                "transcribe_match": float(t_score),
                "align_agreement": a_agree,
                "ytasr_agreement": y_agree,
                "alpha_weight": weight,
                "transcribe_idx_start": start_idx,
                "transcribe_idx_end": end_idx,
            }
        )
    return out


_ALPHA_GATE_COUNT = 2


def _alpha_weight(any_overlap: bool, count: int) -> float:
    """Gate the alpha bonus by transcribe corroboration.

    ``any_overlap`` is True iff at least one normalised lyric token also
    appears anywhere in the transcribe slice. ``count`` is the slice's
    word count.

    Binary gate: a candidate's alpha bonus drops to zero **only** when
    transcribe heard substantial speech (``count >= _ALPHA_GATE_COUNT``)
    AND none of that speech overlaps lexically with the lyric line — i.e.
    align placed the lyric on confidently-wrong audio (Hakuna's dialogue
    interlude). Otherwise the bonus stays at 1.0 so:

      * silent / instrumental windows keep their align preference,
      * mistranscribed lyrics keep their align preference — even a single
        recognised word in the window (e.g. "I've" / "been" / "time" for a
        line whisper rendered as "I've been spinning out the time") is
        enough corroboration to trust align,
      * align-corroborated transcribe candidates score the same as the
        align candidate at the same position (clean-song ties → align
        wins, preserving refined per-word timings).

    Using lexical overlap (set intersection) rather than the strict
    edit-distance threshold ``find_candidates`` uses is the whole point:
    the gate's job is to catch "unrelated speech," not to enforce match
    quality — the score formula already encodes quality via
    ``transcribe_match``. The earlier ``matched == 0`` check inherited
    that threshold and false-fired on mistranscribed lyric lines.

    For align/ytasr candidates a 0.0 here is not the final word: it is
    composed by ``_corroboration_weight``, which can rescue the bonus
    2-of-3 when align and ytasr mutually back the window. Only for
    transcribe candidates (whose gate can never fire) is this the whole
    verdict.
    """
    if count >= _ALPHA_GATE_COUNT and not any_overlap:
        return 0.0
    return 1.0


def _corroboration_weight(any_overlap: bool, count: int, a_agree: float, y_agree: float) -> float:
    """2-of-3 corroboration gate on a candidate's agreement bonus.

    ``_alpha_weight`` judges a window by transcribe's testimony alone,
    which gives one fallible witness veto power over the other two:
    transcribe mishearing a clean line as unrelated words (hallucination
    over backing music, heavy dialect) would zero the bonus even when
    align and ytasr independently nominate the same window. When the
    transcribe gate fires, the bonus instead survives at
    ``min(a_agree, y_agree)`` — the strength of the align<->ytasr pair's
    mutual corroboration; *both* must back the window for the rescue to
    hold, so a source can never rescue itself. With no ytasr data every
    rescue is ``min(_, 0.0) == 0.0``, reducing exactly to the
    transcribe-only gate.
    """
    if _alpha_weight(any_overlap, count) == 1.0:
        return 1.0
    return min(a_agree, y_agree)


def _build_align_candidates(
    line_norms: list[list[str]],
    align_ranges: list[dict | None],
    transcribe_words: list[dict],
    transcribe_norms: list[str],
    ytasr_ranges: list[dict | None],
    margin_s: float,
    max_edit_ratio: float,
    alpha: float,
    beta: float,
) -> list[dict]:
    """One align candidate per line that has an align range, scored by the
    transcribe content inside that range.
    """
    out: list[dict] = []
    transcribe_starts = [w["start"] for w in transcribe_words]
    for line_id, ar in enumerate(align_ranges):
        if ar is None or not line_norms[line_id]:
            continue
        t0 = ar["t0"]
        t1 = ar["t1"]
        # Pad collapsed align candidates so the DP can reject stacks of them.
        if t1 - t0 < _MIN_ALIGN_WIDTH_S:
            pad = (_MIN_ALIGN_WIDTH_S - (t1 - t0)) / 2.0
            t0 = max(0.0, t0 - pad)
            t1 = t1 + pad
        t_match, any_overlap, count_in_window = _transcribe_match_and_count_in_window(
            line_norms[line_id],
            transcribe_norms,
            transcribe_starts,
            t0,
            t1,
            margin_s,
            max_edit_ratio,
        )
        y_agree = _range_agreement(t0, t1, ytasr_ranges[line_id])
        # a_agree is 1.0 by construction (this window *is* align's belief),
        # so the rescue reduces to ytasr's endorsement of it.
        weight = _corroboration_weight(any_overlap, count_in_window, 1.0, y_agree)
        score = float(t_match) + weight * (alpha * 1.0 + beta * y_agree)
        out.append(
            {
                "line_id": line_id,
                "source": "align",
                "t0": t0,
                "t1": t1,
                "score": score,
                "transcribe_match": float(t_match),
                "align_agreement": 1.0,
                "ytasr_agreement": y_agree,
                "alpha_weight": weight,
                "token_start": ar["token_start"],
                "token_end": ar["token_end"],
            }
        )
    return out


def _build_ytasr_candidates(
    tiling_cands: list,
    ytasr_words: list[dict],
    line_norms: list[list[str]],
    align_ranges: list[dict | None],
    transcribe_words: list[dict],
    transcribe_norms: list[str],
    margin_s: float,
    max_edit_ratio: float,
    alpha: float,
    beta: float,
) -> list[dict]:
    """Turn each ytasr ``find_candidates`` hit into a joint candidate.

    Mirrors ``_build_transcribe_candidates``'s shape (every fuzzy-matched
    hit is a competing DP candidate) rather than ``_build_align_candidates``'s
    one-guaranteed-candidate-per-line shape — ytasr has no 1:1 token
    guarantee with the lyric line the way align_words does. Its
    ``transcribe_match`` and ``align_agreement`` are computed fresh against
    this candidate's own window exactly as an align candidate's are, so all
    three sources are commensurable on the same axes. Its self-evidence
    (``ytasr_agreement``) is graded, not flat: the ``find_candidates`` score
    over the line's token count, i.e. the fraction of the line ASR actually
    heard here — a partial hit must not collect the full beta bonus the way
    an exact one does. (Align's flat ``align_agreement = 1.0`` is *not* the
    precedent: an align candidate's range is align's belief by definition,
    and its quality signal rides on ``transcribe_match``; a ytasr candidate's
    only evidence is this very lexical match.)
    """
    out: list[dict] = []
    transcribe_starts = [w["start"] for w in transcribe_words]
    for start_idx, end_idx, line_id, y_score in tiling_cands:
        t0 = ytasr_words[start_idx]["start"]
        t1 = ytasr_words[end_idx - 1]["end"]
        t_match, any_overlap, count_in_window = _transcribe_match_and_count_in_window(
            line_norms[line_id],
            transcribe_norms,
            transcribe_starts,
            t0,
            t1,
            margin_s,
            max_edit_ratio,
        )
        a_agree = _range_agreement(t0, t1, align_ranges[line_id])
        y_agree = y_score / len(line_norms[line_id])
        # The rescue pair here is align's endorsement of this window and
        # the solidity of ytasr's own lexical claim.
        weight = _corroboration_weight(any_overlap, count_in_window, a_agree, y_agree)
        score = float(t_match) + weight * (alpha * a_agree + beta * y_agree)
        out.append(
            {
                "line_id": line_id,
                "source": "ytasr",
                "t0": t0,
                "t1": t1,
                "score": score,
                "transcribe_match": float(t_match),
                "align_agreement": a_agree,
                "ytasr_agreement": y_agree,
                "alpha_weight": weight,
                "ytasr_idx_start": start_idx,
                "ytasr_idx_end": end_idx,
            }
        )
    return out


def _range_agreement(t0: float, t1: float, ref_range: dict | None) -> float:
    """Fraction of a reference range covered by a candidate window.

    A candidate landing exactly on the reference window gets 1.0. A
    candidate completely disjoint from the reference window gets 0.0
    (the Hakuna case). Direction-agnostic: used for a transcribe or ytasr
    candidate's agreement with align's window, and equally for align's or
    transcribe's agreement with a ytasr reference window.
    """
    if ref_range is None:
        return 0.0
    a0 = ref_range["t0"]
    a1 = ref_range["t1"]
    a_dur = a1 - a0
    if a_dur <= 0.0:
        # Collapsed reference range — any candidate overlapping the instant gets full credit.
        return 1.0 if t0 <= a0 <= t1 else 0.0
    overlap = min(t1, a1) - max(t0, a0)
    if overlap <= 0.0:
        return 0.0
    return min(1.0, overlap / a_dur)


def _transcribe_match_and_count_in_window(
    line_norms: list[str],
    transcribe_norms: list[str],
    transcribe_starts: list[float],
    t0: float,
    t1: float,
    margin_s: float,
    max_edit_ratio: float,
) -> tuple[int, bool, int]:
    """Return ``(matched_tokens, any_overlap, transcribe_word_count)``.

    ``matched_tokens`` is the ``find_candidates`` score at this slice —
    same scoring function transcribe candidates use, kept as the
    score-formula's ``transcribe_match`` term.

    ``any_overlap`` is True iff at least one normalised lyric token also
    appears anywhere in the slice. The alpha-weight gate uses this raw
    overlap (not ``matched_tokens``) so the gate fires only on truly
    unrelated speech, not on mistranscribed-but-still-lyric content that
    happens to exceed find_candidates' edit-distance threshold.
    """
    lo = t0 - margin_s
    hi = t1 + margin_s
    # Word indices whose start time is in [lo, hi). bisect_left so that a
    # word starting strictly before ``lo`` (even if its end is after ``lo``)
    # is excluded — overlap-include would otherwise inflate the count and
    # punish align scoring for a neighbour word brushing the window edge.
    left = bisect_left(transcribe_starts, lo)
    right = bisect_left(transcribe_starts, hi)
    window = transcribe_norms[left:right]
    count = len(window)
    if not window or not line_norms:
        return 0, False, count
    any_overlap = not set(line_norms).isdisjoint(window)
    cands = find_candidates(list(window), [line_norms], max_edit_ratio=max_edit_ratio)
    if not cands:
        return 0, any_overlap, count
    return int(max(c[3] for c in cands)), any_overlap, count


# ---------------------------------------------------------------------------
# DP: weighted interval scheduling on time intervals
# ---------------------------------------------------------------------------


def _best_tiling_by_time(candidates: list[dict]) -> list[dict]:
    """Pick the highest-scoring set of candidates that is both
    *non-overlapping in time* AND *monotonic by line_id*.

    Forced alignment guarantees lyric order, so the joint DP must respect
    it: line_id N's selection must end before line_id (N+k)'s selection
    starts. Without this constraint a chorus line whose transcribe
    candidate sits later in audio time than a subsequent lyric line's
    align candidate would steal the later position, leaving the
    subsequent line stuck on its (wrong-audio) align candidate —
    observed empirically on Hakuna Matata where the dialogue interlude
    creates that exact gap.

    Sorted by (line_id, t0) so each candidate's predecessors in the
    iteration order are exactly the candidates that could legally
    precede it in the chain. O(M²) — well within budget for our M.
    """
    if not candidates:
        return []
    cands = sorted(candidates, key=lambda c: (c["line_id"], c["t0"]))
    m = len(cands)
    dp = [c["score"] for c in cands]
    prev = [None] * m
    for i in range(m):
        ci = cands[i]
        for j in range(i):
            cj = cands[j]
            if cj["line_id"] >= ci["line_id"]:
                # Same line (can't double-count) or higher (sorted ascending,
                # impossible). At-most-one candidate per line in the chain.
                continue
            if cj["t1"] > ci["t0"]:
                continue
            candidate_score = dp[j] + ci["score"]
            if candidate_score > dp[i]:
                dp[i] = candidate_score
                prev[i] = j
    best_i = max(range(m), key=lambda i: dp[i])
    selected = []
    cur = best_i
    while cur is not None:
        selected.append(cands[cur])
        cur = prev[cur]
    selected.reverse()
    return selected


# ---------------------------------------------------------------------------
# Output materialisation
# ---------------------------------------------------------------------------


def _materialise_line_objects(
    selected: list[dict],
    line_tokens: list[list[tuple[str, str]]],
    lines: list[str],
    align_words: list[dict],
    transcribe_words: list[dict],
    ytasr_words: list[dict],
    align_ranges: list[dict | None],
    lookahead: int,
) -> list[dict]:
    """One line_object per selected candidate, per-word timed by its source.

    Returns a list (not yet 1:1 with lyric lines) — interpolation of
    missing lines happens in a separate step.
    """
    out: list[dict] = []
    for cand in selected:
        line_id = cand["line_id"]
        toks = line_tokens[line_id]
        if not toks:
            continue
        if cand["source"] == "align":
            obj = _align_line_object(
                line_id, lines[line_id], toks, align_words, align_ranges[line_id]
            )
        elif cand["source"] == "ytasr":
            start_idx = cand["ytasr_idx_start"]
            end_idx = cand["ytasr_idx_end"]
            win_words = ytasr_words[start_idx:end_idx]
            obj = _build_line_object(lines[line_id], line_id, toks, win_words, lookahead)
        else:
            start_idx = cand["transcribe_idx_start"]
            end_idx = cand["transcribe_idx_end"]
            win_words = transcribe_words[start_idx:end_idx]
            obj = _build_line_object(lines[line_id], line_id, toks, win_words, lookahead)
        obj["source"] = cand["source"]
        out.append(obj)
    return out


def _align_line_object(
    line_id: int,
    text: str,
    toks: list[tuple[str, str]],
    align_words: list[dict],
    align_range: dict | None,
) -> dict:
    """Build a line_object directly from align_words for this line."""
    if align_range is None:
        return {
            "text": text,
            "line_id": line_id,
            "words": [],
            "start": None,
            "end": None,
        }
    slice_start = align_range["token_start"]
    slice_end = align_range["token_end"]
    aw = align_words[slice_start:slice_end]
    words = []
    for (_, raw), w in zip(toks, aw):
        words.append({"word": raw, "start": w["start"], "end": w["end"]})
    return {
        "text": text,
        "line_id": line_id,
        "words": words,
        "start": words[0]["start"] if words else None,
        "end": words[-1]["end"] if words else None,
    }


def _interpolate_missing(
    line_objects: list[dict],
    n_lines: int,
    align_words: list[dict],
) -> list[dict]:
    """Pad out lines that had no selected candidate so the output stays
    1:1 with the lyric line list, sorted by ``line_id``.

    A missing line becomes a soft-drop placeholder: ``source: "interp"``,
    empty ``words`` (so the ASS/SRT generators skip it), empty ``text``,
    and a ``start``/``end`` span linearly bracketed by its nearest
    *placed* neighbours (``0.0`` / song end at the edges). It carries no
    per-word timings — the joint matcher renders only the lines it placed
    confidently from align or transcribe; the rest are dropped, the span
    recorded only for offline inspection.
    """
    by_id: dict[int, dict] = {o["line_id"]: o for o in line_objects}
    song_end = align_words[-1]["end"] if align_words else 0.0

    out: list[dict] = []
    for lid in range(n_lines):
        if lid in by_id:
            out.append(by_id[lid])
            continue
        # Find bracketing placed neighbours.
        prev_obj = None
        for j in range(lid - 1, -1, -1):
            if j in by_id and by_id[j].get("end") is not None:
                prev_obj = by_id[j]
                break
        next_obj = None
        for j in range(lid + 1, n_lines):
            if j in by_id and by_id[j].get("start") is not None:
                next_obj = by_id[j]
                break
        t0 = prev_obj["end"] if prev_obj is not None else 0.0
        t1 = next_obj["start"] if next_obj is not None else song_end
        if t1 < t0:
            t1 = t0
        out.append(
            {"line_id": lid, "text": "", "words": [], "start": t0, "end": t1, "source": "interp"}
        )

    out.sort(key=lambda o: o["line_id"])
    return out
