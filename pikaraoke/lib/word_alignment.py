"""Word alignment: two-pointer walk matcher with gap interpolation.

Ported from mpv/genius_align/word_extraction.py. stable-ts emits aligned
words in reference order, so a lockstep walk with bounded lookahead is
sufficient — no DP table, no fuzzy scoring.

Biases (vs. a naive symmetric walker):
  * Asymmetric lookahead — lyric_lookahead=3, whisper_lookahead=10 so
    the walker can absorb runs of extra/noisy whisper output without
    losing lyric anchors.
  * Confirmed re-sync — a candidate anchor at (i+di, j+dj) is rejected
    unless the next confirm_matches-1 pairs also match. Filters spurious
    single-word anchors on common tokens during a desync.
  * Whisper-skip budget — when no anchor exists in the lookahead window,
    advance only the whisper pointer (up to whisper_skip_budget steps)
    before reluctantly skipping the lyric token. Lyrics are source of
    truth; extra whisper output is noise to absorb.

Unmatched lyric tokens get placeholder timestamps interpolated linearly
between the surrounding matched words. Long unmatched runs and
degenerately fast runs are dropped instead of interpolated (assumed to
be lyrics absent from the audio — a skipped verse, a restructured
chorus). Matched runs that collapse onto a single timestamp (stable-ts
giving up and pinning every word to one instant) are demoted and
re-timed by interpolation across the bracketing anchors; since the words
matched 1:1 they're known present, so they're exempt from the long-run
drop and only the readability (min-slot) gate can still drop them.
"""

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_STRIP_NONWORD_RE = re.compile(r"[^\w]", re.UNICODE)

_CONTRACTIONS = {
    "im": "i am",
    "ive": "i have",
    "id": "i would",
    "ill": "i will",
    "youre": "you are",
    "youve": "you have",
    "youd": "you would",
    "youll": "you will",
    "hes": "he is",
    "shes": "she is",
    "its": "it is",
    "weve": "we have",
    "were": "we are",
    "theyre": "they are",
    "theyve": "they have",
    "dont": "do not",
    "doesnt": "does not",
    "didnt": "did not",
    "cant": "cannot",
    "wont": "will not",
    "isnt": "is not",
    "arent": "are not",
    "wasnt": "was not",
    "werent": "were not",
    "wanna": "want to",
    "gonna": "going to",
    "gotta": "got to",
    "aint": "are not",
}


def _normalize_token(token: str) -> str:
    """Lowercase, NFKC-normalize, strip non-word chars."""
    token = unicodedata.normalize("NFKC", token).lower()
    return _STRIP_NONWORD_RE.sub("", token)


def _match_simple(lyric_tok: str, whisper_tok: str) -> bool:
    """Cheap equivalence check: exact, contraction, or 1:N contraction split."""
    if lyric_tok == whisper_tok:
        return True
    l_exp = _CONTRACTIONS.get(lyric_tok)
    w_exp = _CONTRACTIONS.get(whisper_tok)
    if l_exp == whisper_tok or lyric_tok == w_exp:
        return True
    if l_exp and l_exp == w_exp:
        return True
    if l_exp and whisper_tok in l_exp.split():
        return True
    if w_exp and lyric_tok in w_exp.split():
        return True
    return False


# ---------------------------------------------------------------------------
# Walk alignment
# ---------------------------------------------------------------------------


def _walk_align(
    lyric_norms: list,
    whisper_norms: list,
    lyric_lookahead: int = 3,
    whisper_lookahead: int = 10,
    confirm_matches: int = 2,
    whisper_skip_budget: int = 10,
) -> list:
    """Two-pointer alignment biased toward preserving lyric anchors.

    Returns mapping[lyric_idx] = whisper_idx | None.

    On mismatch, scans an asymmetric (lyric_lookahead+1) x (whisper_lookahead+1)
    window for a re-sync point. A candidate is only accepted if the next
    confirm_matches-1 token pairs also match — this filters out spurious
    single-word anchors on common short tokens during a desync.

    When no confirmed re-sync exists in the window, advances only the
    whisper pointer (dropping noisy/extra whisper output) up to
    whisper_skip_budget steps before reluctantly skipping the current
    lyric token. Skipped lyric tokens stay None and get interpolated
    downstream.
    """
    m, n = len(lyric_norms), len(whisper_norms)
    mapping: list = [None] * m
    i = j = 0
    whisper_skips = 0
    while i < m and j < n:
        if _match_simple(lyric_norms[i], whisper_norms[j]):
            mapping[i] = j
            i += 1
            j += 1
            whisper_skips = 0
            continue
        best = None
        best_cost = lyric_lookahead + whisper_lookahead + 1
        max_di = min(lyric_lookahead + 1, m - i)
        max_dj = min(whisper_lookahead + 1, n - j)
        for di in range(max_di):
            for dj in range(max_dj):
                if di == 0 and dj == 0:
                    continue
                cost = di + dj
                if cost >= best_cost:
                    continue
                if not _match_simple(lyric_norms[i + di], whisper_norms[j + dj]):
                    continue
                # Confirm with the next (confirm_matches - 1) pairs. If we
                # run off either sequence before confirming, accept anyway
                # — end-of-sequence anchors can't be confirmed but are
                # usually still correct.
                confirmed = True
                for k in range(1, confirm_matches):
                    li, wi = i + di + k, j + dj + k
                    if li >= m or wi >= n:
                        break
                    if not _match_simple(lyric_norms[li], whisper_norms[wi]):
                        confirmed = False
                        break
                if confirmed:
                    best = (di, dj)
                    best_cost = cost
        if best is None:
            # Advance whisper pointer only: preserve the current lyric
            # token as an unmatched candidate. Cap consecutive whisper-only
            # advances so a truly missing lyric token doesn't stall the
            # walker forever.
            j += 1
            whisper_skips += 1
            if whisper_skips >= whisper_skip_budget:
                i += 1
                whisper_skips = 0
        else:
            di, dj = best
            i += di
            j += dj
            mapping[i] = j
            i += 1
            j += 1
            whisper_skips = 0
    return mapping


# ---------------------------------------------------------------------------
# Public API: match_words_to_lines
# ---------------------------------------------------------------------------


def _make_loss_span(
    token_start: int,
    token_end: int,
    lyric_tokens: list,
    t0: float,
    t1: float,
    from_collapse: bool,
    recovered: bool,
) -> dict:
    """Build one ``loss_spans`` entry for a contiguous failed-token run.

    ``token_end`` is half-open; ``line_start/line_end`` are the inclusive
    lyric-line range the run touches; ``t0/t1`` are the bracketing matched
    anchor times. ``kind`` records the failure origin (collapse-demoted vs
    unmatched) and ``recovered`` whether it ended up interpolated (present)
    rather than dropped (absent).
    """
    return {
        "token_start": token_start,
        "token_end": token_end,
        "line_start": lyric_tokens[token_start][1],
        "line_end": lyric_tokens[token_end - 1][1],
        "t0": t0,
        "t1": t1,
        "kind": "collapsed" if from_collapse else "dropped",
        "recovered": recovered,
    }


def match_words_to_lines(
    words: list,
    lines: list[str],
    align_lines: list[str] | None = None,
    lyric_lookahead: int = 3,
    whisper_lookahead: int = 10,
    confirm_matches: int = 2,
    whisper_skip_budget: int = 10,
    max_interp_run: int = 5,
    min_interp_slot: float = 0.1,
    max_collapsed_run: int = 8,
    collapse_window: float = 0.3,
) -> list[dict]:
    """Thin wrapper around :func:`match_words_to_lines_with_stats` that
    discards the stats dict. See that function for full documentation.
    """
    line_objects, _stats = match_words_to_lines_with_stats(
        words,
        lines,
        align_lines=align_lines,
        lyric_lookahead=lyric_lookahead,
        whisper_lookahead=whisper_lookahead,
        confirm_matches=confirm_matches,
        whisper_skip_budget=whisper_skip_budget,
        max_interp_run=max_interp_run,
        min_interp_slot=min_interp_slot,
        max_collapsed_run=max_collapsed_run,
        collapse_window=collapse_window,
    )
    return line_objects


def match_words_to_lines_with_stats(
    words: list,
    lines: list[str],
    align_lines: list[str] | None = None,
    lyric_lookahead: int = 3,
    whisper_lookahead: int = 10,
    confirm_matches: int = 2,
    whisper_skip_budget: int = 10,
    max_interp_run: int = 5,
    min_interp_slot: float = 0.1,
    max_collapsed_run: int = 8,
    collapse_window: float = 0.3,
) -> tuple[list[dict], dict]:
    """Assign whisper words to lyric lines via two-pointer walk matching.

    Each reference token is either paired with a whisper word (using that
    word's timing) or interpolated linearly between the surrounding
    matched anchors. Short unmatched runs are interpolated so the line
    stays gap-free; a run is dropped — rather than interpolated — when
    either it is longer than ``max_interp_run`` or its interpolation slot
    would fall below ``min_interp_slot``. Both signal lyrics absent from
    the audio: faking timing would just animate phantom words, and a
    near-zero slot crams them illegibly.

    Lines whose tokens are all dropped via the interp cap return with
    ``words=[]`` and ``start=None`` — the SRT/ASS generators skip these.
    Paren-only display lines (no normalizable tokens at all) still
    inherit timing from neighbors and render statically.

    Whisper words that match no lyric token (hallucinations, backing
    vocals) are silently dropped.

    Args:
        words: flat whisper word list from the worker.
        lines: display text per lyric line (may include inline parens).
        align_lines: paren-stripped text per lyric line for alignment.
            If None, falls back to lines.
        lyric_lookahead: max lyric tokens to skip when re-syncing.
        whisper_lookahead: max whisper words to skip when re-syncing —
            asymmetrically larger so the walker can absorb stretches of
            extra/noisy whisper output without losing lyric anchors.
        confirm_matches: required consecutive matches at a re-sync point
            before accepting it (filters spurious common-word anchors).
        whisper_skip_budget: max consecutive whisper-only advances before
            the walker reluctantly skips the current lyric token.
        max_interp_run: largest unmatched-token run that still gets
            linearly interpolated. Longer runs are dropped — assumed to
            be lyrics absent from the audio. Does NOT apply to collapse-
            demoted runs (see ``max_collapsed_run``): those matched 1:1
            and are known present, so they interpolate at any length,
            gated only by ``min_interp_slot``. Set very large to disable.
        min_interp_slot: minimum per-token interpolation slot, in seconds.
            If the bracketing anchors are too close to give each token at
            least this much time, the run is dropped instead of crammed.
            Set to 0.0 to disable.
        max_collapsed_run: longest run of *matched* tokens allowed to share
            essentially one timestamp. stable-ts force-places every word
            of an unalignable section at a single instant; the walker
            pairs those 1:1 so the interp caps never see them. A run
            longer than this many matched tokens inside ``collapse_window``
            seconds is demoted so it gets re-timed by interpolation across
            the bracketing anchors (exempt from ``max_interp_run`` since
            the words are known present). Set very large to disable.
        collapse_window: max span, in seconds, for a matched-token run to
            count as collapsed for the ``max_collapsed_run`` check.

    Returns:
        ``(line_objects, stats)``. ``stats`` is a dict capturing knob
        values and per-run telemetry (matched/dropped/collapsed/interp
        run lengths) used downstream by the alignment-capture writer to
        seed offline knob tuning. ``stats["loss_spans"]`` carries the
        collapsed/dropped runs as structured ``{token_start, token_end,
        line_start, line_end, t0, t1, kind, recovered}`` entries so the
        align stage can locate a concentrated failure (lines + audio
        window) without re-deriving it from the raw index lists.
    """
    knobs = {
        "lyric_lookahead": lyric_lookahead,
        "whisper_lookahead": whisper_lookahead,
        "confirm_matches": confirm_matches,
        "whisper_skip_budget": whisper_skip_budget,
        "max_interp_run": max_interp_run,
        "min_interp_slot": min_interp_slot,
        "max_collapsed_run": max_collapsed_run,
        "collapse_window": collapse_window,
    }
    if align_lines is None:
        align_lines = lines

    lyric_tokens: list = []  # [(norm_tok, line_idx, raw_tok)]
    for line_idx, aline in enumerate(align_lines):
        aline_split = aline.replace("—", " ").replace("--", " ")
        for tok in aline_split.split():
            norm = _normalize_token(tok)
            if norm:
                lyric_tokens.append((norm, line_idx, tok))

    n_lines = len(lines)
    if not lyric_tokens or not words:
        empty_stats = {
            "knobs": knobs,
            "n_words": len(words),
            "n_lines": n_lines,
            "n_tokens": len(lyric_tokens),
            "matched_count": 0,
            "whisper_consumed": 0,
            "collapsed_tokens": 0,
            "dropped_tokens": 0,
            "collapsed_run_lengths": [],
            "interp_run_lengths": [],
            "dropped_run_lengths": [],
            "collapsed_token_indices": [],
            "dropped_token_indices": [],
            "loss_spans": [],
            "mapping": [],
            "lines_with_words": 0,
            "empty_line_reasons": {},
            "early_return": True,
        }
        return (
            [{"text": d, "words": [], "start": 0.0, "end": 0.0} for d in lines],
            empty_stats,
        )

    whisper_norms = [_normalize_token(w["word"]) for w in words]
    lyric_norms = [lt[0] for lt in lyric_tokens]

    mapping = _walk_align(
        lyric_norms,
        whisper_norms,
        lyric_lookahead=lyric_lookahead,
        whisper_lookahead=whisper_lookahead,
        confirm_matches=confirm_matches,
        whisper_skip_budget=whisper_skip_budget,
    )

    n_tokens = len(lyric_tokens)
    token_words: list = [None] * n_tokens
    for k, (_, _, raw) in enumerate(lyric_tokens):
        w_idx = mapping[k]
        if w_idx is not None:
            wsrc = words[w_idx]
            token_words[k] = {
                "word": raw,
                "start": wsrc["start"],
                "end": wsrc["end"],
            }

    # Demote collapsed matched runs: when stable-ts can't locate a lyric
    # section it force-places every word at one timestamp. The walker
    # pairs those 1:1 so the interp caps never see them — find long runs
    # of matched tokens crammed into < collapse_window seconds and
    # demote them to None so the interp/drop logic below applies.
    collapsed_tokens = 0
    collapsed_run_lengths: list[int] = []
    collapsed_token_indices: list[list[int]] = []
    if max_collapsed_run < n_tokens:
        k = 0
        while k < n_tokens:
            if token_words[k] is None:
                k += 1
                continue
            run_end = k + 1
            while (
                run_end < n_tokens
                and token_words[run_end] is not None
                and token_words[run_end]["start"] - token_words[k]["start"] < collapse_window
            ):
                run_end += 1
            run_len = run_end - k
            if run_len > max_collapsed_run:
                for idx in range(k, run_end):
                    token_words[idx] = None
                collapsed_tokens += run_len
                collapsed_run_lengths.append(run_len)
                collapsed_token_indices.append(list(range(k, run_end)))
                k = run_end
            else:
                k += 1

    matched_count = sum(1 for tw in token_words if tw is not None)

    # Interpolate short unmatched runs; drop long runs entirely (token_words
    # stays None — those tokens won't appear in the karaoke output).
    # loss_spans records the collapsed/dropped runs (not the benign short
    # interp gaps) with their bracketing anchor times + line ranges, so the
    # align stage can map a concentrated failure to lines + an audio window
    # without re-deriving it.
    collapsed_indices_set = {idx for run in collapsed_token_indices for idx in run}
    dropped_tokens = 0
    interp_run_lengths: list[int] = []
    dropped_run_lengths: list[int] = []
    dropped_token_indices: list[list[int]] = []
    loss_spans: list[dict] = []
    k = 0
    while k < n_tokens:
        if token_words[k] is not None:
            k += 1
            continue
        run_end = k
        while run_end < n_tokens and token_words[run_end] is None:
            run_end += 1
        run_len = run_end - k
        # Collapse-demoted tokens matched whisper output 1:1 — they were
        # sung, only their timestamps collapsed onto one instant. The
        # max_interp_run cap targets lyrics *absent* from the audio, which
        # these are not, so interpolate them across the bracketing anchors
        # regardless of run length. The min_interp_slot gate below still
        # drops a run whose anchors are too close to place it legibly
        # (a collapse at the song's end, or with no real gap after it).
        from_collapse = any(idx in collapsed_indices_set for idx in range(k, run_end))
        prev_end = token_words[k - 1]["end"] if k > 0 else 0.0
        next_start = token_words[run_end]["start"] if run_end < n_tokens else prev_end
        if next_start < prev_end:
            next_start = prev_end
        if run_len > max_interp_run and not from_collapse:
            dropped_tokens += run_len
            dropped_run_lengths.append(run_len)
            dropped_token_indices.append(list(range(k, run_end)))
            loss_spans.append(
                _make_loss_span(k, run_end, lyric_tokens, prev_end, next_start, False, False)
            )
            k = run_end
            continue
        slot = (next_start - prev_end) / run_len if run_len > 0 else 0.0
        if run_len > 0 and slot < min_interp_slot:
            # Degenerate interpolation: bracketing anchors are too close
            # to fit these tokens at a readable pace. Almost always a
            # skipped section whose run was fragmented by spurious
            # common-word anchors — drop it rather than cram near-zero-
            # duration phantom words into a sliver of time.
            dropped_tokens += run_len
            dropped_run_lengths.append(run_len)
            dropped_token_indices.append(list(range(k, run_end)))
            loss_spans.append(
                _make_loss_span(
                    k, run_end, lyric_tokens, prev_end, next_start, from_collapse, False
                )
            )
            k = run_end
            continue
        if run_len > 0:
            interp_run_lengths.append(run_len)
            # A collapse-demoted run that interpolated cleanly is still a
            # failed span (present but linearly smeared) — record it. A
            # benign short gap between tight anchors is not a failure.
            if from_collapse:
                loss_spans.append(
                    _make_loss_span(k, run_end, lyric_tokens, prev_end, next_start, True, True)
                )
        for offset in range(run_len):
            s = prev_end + offset * slot
            e = prev_end + (offset + 1) * slot
            _, _, raw = lyric_tokens[k + offset]
            token_words[k + offset] = {
                "word": raw,
                "start": s,
                "end": e,
            }
        k = run_end

    logger.info(
        "Walk align: matched %d/%d reference tokens (%.1f%%); "
        "%d whisper words consumed; %d tokens demoted (collapsed run); "
        "%d tokens dropped (uninterpolatable)",
        matched_count,
        n_tokens,
        100.0 * matched_count / n_tokens if n_tokens else 0.0,
        sum(1 for v in mapping if v is not None),
        collapsed_tokens,
        dropped_tokens,
    )

    # Track which lines had any normalizable tokens at all, so we can
    # distinguish "paren-only display line" (inherit neighbor timing,
    # render statically) from "every token was dropped by the interp cap"
    # (suppress the line — audio doesn't contain it).
    lines_with_tokens: set = set()
    for _, line_idx, _ in lyric_tokens:
        lines_with_tokens.add(line_idx)

    line_word_lists: list = [[] for _ in range(n_lines)]
    for k, (_, line_idx, _) in enumerate(lyric_tokens):
        if token_words[k] is not None:
            line_word_lists[line_idx].append(token_words[k])

    line_objects: list = []
    for line_idx in range(n_lines):
        text = lines[line_idx]
        line_words = line_word_lists[line_idx]
        if line_words:
            line_objects.append(
                {
                    "text": text,
                    "words": line_words,
                    "start": line_words[0]["start"],
                    "end": line_words[-1]["end"],
                }
            )
        else:
            line_objects.append(
                {
                    "text": text,
                    "words": [],
                    "start": None,
                    "end": None,
                }
            )

    # Lines with no normalizable tokens (paren-only display lines) inherit
    # timing from neighbors. Lines whose tokens were all dropped via the
    # interp cap stay with start=None so the SRT/ASS generators skip them.
    for i, obj in enumerate(line_objects):
        if obj["start"] is not None or i in lines_with_tokens:
            continue
        prev_end = 0.0
        for j in range(i - 1, -1, -1):
            if line_objects[j]["end"] is not None:
                prev_end = line_objects[j]["end"]
                break
        next_start = prev_end
        for j in range(i + 1, len(line_objects)):
            if line_objects[j]["start"] is not None:
                next_start = line_objects[j]["start"]
                break
        obj["start"] = prev_end
        obj["end"] = next_start

    # Per-empty-line diagnosis. Distinguishes "line had no normalizable
    # tokens to start with" (paren-only / structural junk — a lyrics-
    # parser signal) from "every token was dropped by collapse-demote
    # or the interp cap" (a knob-tuning signal). Without this split the
    # aggregate lines_with_words count conflates both.
    empty_line_reasons: dict[int, str] = {}
    for line_idx, obj in enumerate(line_objects):
        if obj["words"]:
            continue
        if line_idx in lines_with_tokens:
            empty_line_reasons[line_idx] = "all_tokens_dropped"
        else:
            empty_line_reasons[line_idx] = "no_normalizable_tokens"

    stats = {
        "knobs": knobs,
        "n_words": len(words),
        "n_lines": n_lines,
        "n_tokens": n_tokens,
        "matched_count": matched_count,
        "whisper_consumed": sum(1 for v in mapping if v is not None),
        "collapsed_tokens": collapsed_tokens,
        "dropped_tokens": dropped_tokens,
        "collapsed_run_lengths": collapsed_run_lengths,
        "interp_run_lengths": interp_run_lengths,
        "dropped_run_lengths": dropped_run_lengths,
        "collapsed_token_indices": collapsed_token_indices,
        "dropped_token_indices": dropped_token_indices,
        "loss_spans": loss_spans,
        "mapping": list(mapping),
        "lines_with_words": sum(1 for o in line_objects if o["words"]),
        "empty_line_reasons": empty_line_reasons,
        "early_return": False,
    }
    return line_objects, stats
