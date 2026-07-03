"""Fuzzy lyric-line candidate generation + per-word timing for the joint matcher.

The joint matcher (``joint_match``) needs, for each lyric line, every
plausible place that line could sit in the transcribe word stream. This
module supplies those candidates and turns a chosen token span back into
per-word karaoke timings.

  1. find_candidates — sliding-window fuzzy match of each line vs. the
     token stream. Windows range narrower AND wider than the line so the
     scan tolerates whisper dropping words as well as inserting filler.
     find_anchor_candidates is a relaxed fallback re-scan for lines that
     got zero candidates: it accepts a window on a contiguous anchor run
     alone, regardless of total edit distance.
  2. _build_line_object — once the matcher has selected a token span for a
     line, assign per-word start/end inside it (reusing ``_walk_align``)
     with linear interpolation across any unmatched runs.

Candidates are ``(start_idx, end_idx, line_id, score)`` tuples over token
indices; the matcher does its own interval scheduling over them.
"""

from pikaraoke.lib.token_align import _normalize_token, _walk_align


def _edit_distance(a: list, b: list) -> int:
    """Word-level Levenshtein distance between two token sequences."""
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        ai = a[i - 1]
        for j in range(1, n + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]


def _longest_contiguous_run(a: list, b: list) -> int:
    """Length of the longest run of consecutive equal elements common to
    sequences a and b — word-level longest common substring.
    """
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    best = 0
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        cur = [0] * (n + 1)
        ai = a[i - 1]
        for j in range(1, n + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def find_candidates(
    token_norms: list,
    lyric_lines: list,
    max_edit_ratio: float = 0.25,
    window_slack_lo: int = 2,
    window_slack_hi: int = 3,
) -> list:
    """Scan the token sequence for fuzzy occurrences of each lyric line.

    token_norms: list of normalized whisper word strings
    lyric_lines: list of lists of normalized lyric words
    Returns: list of (start_idx, end_idx, line_id, score) where score is
    the raw matched-token count ``n - dist`` (integer-valued float).

    Windows range from ``n - window_slack_lo`` to ``n + window_slack_hi``
    wide: narrower windows catch lines whisper only partially heard,
    wider windows absorb inserted filler. ``max_allowed`` is floored at 1
    so short lines (< 4 words) aren't given zero error tolerance.

    A candidate must also have at least ``min(2, n)`` tokens of genuine
    content overlap (``n - dist``). Without this floor, the narrow-window
    slack lets a 2-word line "match" a single token by pure deletion
    and the DP happily tiles those degenerate fragments.

    Score is the raw matched-token count, NOT a normalized ratio. The
    matcher's interval-scheduling DP maximizes the sum of selected scores,
    so raw counts make it maximize total lyric coverage. Normalization (the
    old ``(n-dist)/n``) gave every perfect short fragment a score of 1.0,
    letting a 2-token fragment beat a 6-token full line with one whisper
    error when they competed for overlapping windows. Edit-quality gating is
    already handled by ``max_edit_ratio``; the score shouldn't repeat it.
    """
    candidates = []
    T = len(token_norms)
    for line_id, line_words in enumerate(lyric_lines):
        n = len(line_words)
        if n == 0:
            continue
        max_allowed = max(1, int(n * max_edit_ratio))
        min_overlap = min(2, n)
        lo = max(1, n - window_slack_lo)
        hi = n + window_slack_hi
        for window_size in range(lo, hi + 1):
            if window_size > T:
                break
            for i in range(T - window_size + 1):
                window = token_norms[i : i + window_size]
                dist = _edit_distance(line_words, window)
                if dist <= max_allowed and (n - dist) >= min_overlap:
                    score = float(n - dist)
                    candidates.append((i, i + window_size, line_id, score))
    return candidates


def find_anchor_candidates(
    token_norms: list,
    lyric_lines: list,
    line_ids: list,
    min_run_floor: int = 3,
    window_slack_lo: int = 2,
    window_slack_hi: int = 3,
) -> list:
    """Relaxed fallback re-scan for specific lyric lines.

    Intended for lines that produced zero candidates in the main
    find_candidates pass — typically because whisper's transcription of
    that line is too garbled for the edit-ratio threshold. A window is
    accepted here on a *contiguous anchor run* alone: it must share a run
    of >= min_run consecutive words with the line, regardless of total
    edit distance. The anchor run is the confidence signal — a solid
    recognizable phrase is proof the line was sung here even if the
    surrounding words diverge.

    Score is the raw anchor-run length — the count of confidently-matched
    consecutive tokens — matching the main-pass scoring scheme so the
    DP can compare across passes on the same units. An N-token
    anchor run can never beat what main would have scored for the same
    line: main pass would have found ``n - dist`` with ``dist <= n - run``
    (the run contributes 0 to dist), so main's score is at least
    ``run``. Restricting the scan to ``line_ids`` keeps the pass bounded
    and means it never pollutes lines that already matched cleanly.
    """
    candidates = []
    T = len(token_norms)
    for line_id in line_ids:
        line_words = lyric_lines[line_id]
        n = len(line_words)
        min_run = max(min_run_floor, n // 3)
        if n < min_run:
            continue  # too short to anchor confidently
        lo = max(1, n - window_slack_lo)
        hi = n + window_slack_hi
        for window_size in range(lo, hi + 1):
            if window_size > T:
                break
            for i in range(T - window_size + 1):
                window = token_norms[i : i + window_size]
                run = _longest_contiguous_run(line_words, window)
                if run >= min_run:
                    candidates.append((i, i + window_size, line_id, float(run)))
    return candidates


def best_candidate_per_line(candidates: list) -> dict[int, tuple[int, int, float]]:
    """Reduce find_candidates-shaped tuples to one best-scoring hit per line.

    Keeps the highest ``(score, -start_idx)`` entry per ``line_id`` — ties
    broken toward the earliest start, so a repeated phrase resolves to its
    first occurrence. For callers that want every competing candidate (e.g.
    the joint DP), use the raw ``find_candidates`` output directly; this is
    for callers that need a single reference span per line instead.
    """
    best: dict[int, tuple[int, int, float]] = {}
    for start, end, line_id, score in candidates:
        cur = best.get(line_id)
        if cur is None or (score, -start) > (cur[2], -cur[0]):
            best[line_id] = (start, end, score)
    return best


def _build_line_object(
    text: str, line_id: int, line_toks: list, win_words: list, lookahead: int
) -> dict:
    """Assign per-word timing within a selected window.

    A candidate match only ties a whole lyric line to a token span — for
    karaoke each lyric word still needs its own start/end. Reuse
    ``_walk_align`` *within the window* to pair words, then linearly
    interpolate any unmatched runs across the surrounding anchors.
    """
    lyric_norms = [t[0] for t in line_toks]
    win_norms = [_normalize_token(w["word"]) for w in win_words]
    # Neutralize _walk_align's whole-song biases here: a selected tiling
    # window is already a tight fuzzy match, so there's no long stretch
    # of noise to absorb. confirm_matches=1 + whisper_skip_budget=1
    # reproduces the symmetric "advance both on no-resync" behavior.
    mapping = _walk_align(
        lyric_norms,
        win_norms,
        lyric_lookahead=lookahead,
        whisper_lookahead=lookahead,
        confirm_matches=1,
        whisper_skip_budget=1,
    )

    n = len(line_toks)
    tw: list = [None] * n
    for k, (_, raw) in enumerate(line_toks):
        wi = mapping[k]
        if wi is not None:
            src = win_words[wi]
            tw[k] = {
                "word": raw,
                "start": src["start"],
                "end": src["end"],
            }

    win_start = win_words[0]["start"]
    win_end = win_words[-1]["end"]
    k = 0
    while k < n:
        if tw[k] is not None:
            k += 1
            continue
        run_end = k
        while run_end < n and tw[run_end] is None:
            run_end += 1
        prev_end = tw[k - 1]["end"] if k > 0 else win_start
        next_start = tw[run_end]["start"] if run_end < n else win_end
        if next_start < prev_end:
            next_start = prev_end
        run_len = run_end - k
        slot = (next_start - prev_end) / run_len if run_len > 0 else 0.0
        for off in range(run_len):
            s = prev_end + off * slot
            e = prev_end + (off + 1) * slot
            _, raw = line_toks[k + off]
            tw[k + off] = {
                "word": raw,
                "start": s,
                "end": e,
            }
        k = run_end

    return {
        "text": text,
        "line_id": line_id,
        "words": tw,
        "start": tw[0]["start"],
        "end": tw[-1]["end"],
    }
