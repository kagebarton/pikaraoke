"""Word alignment: Needleman-Wunsch word-to-line matching for lyrics.

Ported from mpv/genius_diarize/word_extraction.py. This module contains
only the NW matcher and related helpers; whisper-specific extraction
lives in the worker.
"""

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Gap penalties for NW alignment
_GAP_LYRIC = -2  # penalty for lyric word with no whisper match
_GAP_WHISPER = -1  # penalty for whisper token with no lyric match

# Maximum value _score() can return. Used by _needleman_wunsch to size the
# sentinel and to guard the gap-cost invariant.
_MAX_MATCH = 3

# Invariant: a single match must never exceed the cost of gapping both sides
# of a token. Otherwise NW becomes indifferent between matching a token and
# gapping both sides of it.
assert _MAX_MATCH <= -(
    _GAP_LYRIC + _GAP_WHISPER
), "Single match score must not exceed gap-pair cost"

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_STRIP_NONWORD_RE = re.compile(r"[^\w]", re.UNICODE)

# Contraction expansions for normalization (both directions checked at match time)
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

# Phonetic equivalence pairs (vowel-elongation and a few spelling variants)
# that the Levenshtein-1 fuzzy gate (len >= 3) excludes.
_PHONETIC_EQUIV = {
    frozenset({"mm", "mmm"}),
    frozenset({"uh", "uhh"}),
    frozenset({"oo", "ooh"}),
    frozenset({"hm", "hmm"}),
    frozenset({"wo", "woo"}),
    frozenset({"oh", "ooh"}),
    frozenset({"ah", "aah"}),
    frozenset({"ha", "hah"}),
    frozenset({"ay", "ayy"}),
    frozenset({"la", "laa"}),
    frozenset({"da", "daa"}),
    frozenset({"woah", "whoa"}),
}

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _normalize_token(token: str) -> str:
    """Lowercase, NFKC-normalize, strip non-word chars."""
    token = unicodedata.normalize("NFKC", token).lower()
    return _STRIP_NONWORD_RE.sub("", token)


def _levenshtein(a: str, b: str) -> int:
    """Standard edit distance (no substitution weighting needed here)."""
    if abs(len(a) - len(b)) > 1:
        return 2  # early exit — can't be ≤1
    m, n = len(a), len(b)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[n]


def _score(lyric_tok: str, whisper_tok: str) -> int:
    """Alignment score for a lyric/whisper token pair.

    +3 exact match, len >= 6 (anchor bonus — long words pin alignment)
    +2 exact match, len < 6
    +2 contraction equivalence (1:1 or 1:N split)
    +1 phonetic equivalence (_PHONETIC_EQUIV — vowel elongation, spelling variants)
    +1 one-edit-distance match (tokens >=3 chars) — handles minor typos
    0 mismatch
    """
    if lyric_tok == whisper_tok:
        return 3 if len(lyric_tok) >= 6 else 2
    l_exp = _CONTRACTIONS.get(lyric_tok)
    w_exp = _CONTRACTIONS.get(whisper_tok)
    if (l_exp == whisper_tok) or (lyric_tok == w_exp) or (l_exp and l_exp == w_exp):
        return 2
    if l_exp and whisper_tok in l_exp.split():
        return 2
    if w_exp and lyric_tok in w_exp.split():
        return 2
    pair = frozenset({lyric_tok, whisper_tok})
    if pair in _PHONETIC_EQUIV:
        return 1
    if len(lyric_tok) >= 3 and len(whisper_tok) >= 3:
        if _levenshtein(lyric_tok, whisper_tok) <= 1:
            return 1
    return 0


# ---------------------------------------------------------------------------
# NW alignment
# ---------------------------------------------------------------------------

_BAND_MIN_LENGTH = 500  # only band sequences longer than this


def _needleman_wunsch_unbanded(lyric_norms: list, whisper_norms: list) -> list:
    """Unbanded (full O(m*n)) Semi-Global NW alignment.

    Returns list of (lyric_idx | None, whisper_idx | None) pairs.
    None on either side means a gap on that sequence.
    Handles asymmetric penalties and free whisper prefix/suffix.
    """
    m, n = len(lyric_norms), len(whisper_norms)

    score_cache: dict = {}

    def _cached_score(a: str, b: str) -> int:
        key = (a, b)
        if key not in score_cache:
            score_cache[key] = _score(a, b)
        return score_cache[key]

    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i * _GAP_LYRIC
    for j in range(n + 1):
        dp[0][j] = 0  # Free Whisper prefix

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            match = dp[i - 1][j - 1] + _cached_score(lyric_norms[i - 1], whisper_norms[j - 1])
            delete = dp[i - 1][j] + _GAP_LYRIC
            insert = dp[i][j - 1] + _GAP_WHISPER
            dp[i][j] = max(match, delete, insert)

    # Find best Whisper suffix point (free suffix)
    best_j = n
    max_score = dp[m][n]
    for j_opt in range(n):
        if dp[m][j_opt] > max_score:
            max_score = dp[m][j_opt]
            best_j = j_opt

    # Traceback
    alignment = []
    i, j = m, best_j
    for j_skip in range(n, best_j, -1):
        alignment.append((None, j_skip - 1))

    while i > 0 or j > 0:
        if i > 0 and j > 0:
            s = _cached_score(lyric_norms[i - 1], whisper_norms[j - 1])
            if dp[i][j] == dp[i - 1][j - 1] + s:
                alignment.append((i - 1, j - 1))
                i -= 1
                j -= 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + _GAP_LYRIC:
            alignment.append((i - 1, None))
            i -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + _GAP_WHISPER:
            alignment.append((None, j - 1))
            j -= 1
        elif j > 0 and i == 0:
            alignment.append((None, j - 1))
            j -= 1
        else:
            break

    alignment.reverse()
    return alignment


def _needleman_wunsch_banded(lyric_norms: list, whisper_norms: list) -> list:
    """Banded (Sakoe-Chiba) Semi-Global NW alignment with taper and fallback."""
    m, n = len(lyric_norms), len(whisper_norms)

    score_cache: dict = {}

    def _cached_score(a: str, b: str) -> int:
        key = (a, b)
        if key not in score_cache:
            score_cache[key] = _score(a, b)
        return score_cache[key]

    band = max(50, max(m, n) // 4)
    taper_rows = min(band, m // 4)

    neg_inf = -(m + n + 1) * _MAX_MATCH * 2
    assert (
        neg_inf + _MAX_MATCH * max(m, n) < 0
    ), "Sentinel insufficient for current scoring constants"

    dp = [[neg_inf] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i * _GAP_LYRIC
    for j in range(n + 1):
        dp[0][j] = 0  # Free Whisper prefix

    for i in range(1, m + 1):
        j_exp = round(i * n / m)
        rows_from_end = m - i
        if taper_rows > 0 and rows_from_end < taper_rows:
            extra = (taper_rows - rows_from_end) * (n - band) // taper_rows
            eff_band = band + max(0, extra)
        else:
            eff_band = band
        j_lo = max(1, j_exp - eff_band)
        j_hi = min(n, j_exp + eff_band)
        for j in range(j_lo, j_hi + 1):
            match_s = dp[i - 1][j - 1] + _cached_score(lyric_norms[i - 1], whisper_norms[j - 1])
            delete_s = dp[i - 1][j] + _GAP_LYRIC
            insert_s = dp[i][j - 1] + _GAP_WHISPER
            dp[i][j] = max(match_s, delete_s, insert_s)

    # Find best Whisper suffix point (free suffix)
    best_j = n
    max_score = dp[m][n]
    for j_opt in range(n):
        if dp[m][j_opt] > max_score:
            max_score = dp[m][j_opt]
            best_j = j_opt

    # Degenerate-result fallback
    expected_floor = (m / 3) * 2 + (m * 2 / 3) * _GAP_LYRIC
    if dp[m][best_j] < expected_floor:
        logger.warning(
            "Banded NW score %d below expected floor %d; re-running unbanded",
            dp[m][best_j],
            int(expected_floor),
        )
        return _needleman_wunsch_unbanded(lyric_norms, whisper_norms)

    # Traceback
    alignment = []
    i, j = m, best_j
    for j_skip in range(n, best_j, -1):
        alignment.append((None, j_skip - 1))

    while i > 0 or j > 0:
        if i > 0 and j > 0:
            s = _cached_score(lyric_norms[i - 1], whisper_norms[j - 1])
            if dp[i][j] == dp[i - 1][j - 1] + s:
                alignment.append((i - 1, j - 1))
                i -= 1
                j -= 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + _GAP_LYRIC:
            alignment.append((i - 1, None))
            i -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + _GAP_WHISPER:
            alignment.append((None, j - 1))
            j -= 1
        elif j > 0 and i == 0:
            alignment.append((None, j - 1))
            j -= 1
        else:
            break

    alignment.reverse()
    return alignment


def _needleman_wunsch(lyric_norms: list, whisper_norms: list) -> list:
    """Semi-Global sequence alignment dispatcher.

    Returns list of (lyric_idx | None, whisper_idx | None) pairs.
    None on either side means a gap on that sequence.

    For short sequences (max(m,n) <= _BAND_MIN_LENGTH), uses full O(m*n)
    unbanded NW. For longer sequences, uses Sakoe-Chiba banded NW with
    taper and degenerate-result fallback to unbanded.
    """
    if max(len(lyric_norms), len(whisper_norms)) <= _BAND_MIN_LENGTH:
        return _needleman_wunsch_unbanded(lyric_norms, whisper_norms)
    return _needleman_wunsch_banded(lyric_norms, whisper_norms)


# ---------------------------------------------------------------------------
# Public API: match_words_to_lines
# ---------------------------------------------------------------------------


def match_words_to_lines(
    words: list, lines: list[str], align_lines: list[str] | None = None
) -> list[dict]:
    """Assign whisper words to lyric lines via Needleman-Wunsch alignment.

    Replaces the count-based approach. Each lyric token is globally
    aligned to a whisper token using a scoring function (+2 exact, +1
    fuzzy/contraction, 0 mismatch, -1 gap). This tolerates contraction
    splitting, punctuation differences, and limited whisper hallucinations
    without cascading the error across all subsequent lines.

    Whisper words that match no lyric token (hallucinations, backing vox)
    are silently dropped. Lyric lines where no whisper words aligned get
    an empty words list and inherit the previous line's end time — the
    ASS generator skips them; SRT still emits the text.

    Args:
        words: flat whisper word list from _extract_words().
        lines: display text per lyric line (may include inline parens).
        align_lines: paren-stripped text per lyric line for alignment.
            If None, falls back to lines.
    """
    if align_lines is None:
        align_lines = lines

    # Build flat lyric token list tagged with line index
    lyric_tokens = []  # [(norm_tok, line_idx)]
    for line_idx, aline in enumerate(align_lines):
        aline_split = aline.replace("—", " ").replace("--", " ")
        for tok in aline_split.split():
            norm = _normalize_token(tok)
            if norm:
                lyric_tokens.append((norm, line_idx))

    if not lyric_tokens or not words:
        return [{"text": d, "words": [], "start": 0.0, "end": 0.0} for d in lines]

    whisper_norms = [_normalize_token(w["word"]) for w in words]
    lyric_norms = [lt[0] for lt in lyric_tokens]

    alignment = _needleman_wunsch(lyric_norms, whisper_norms)

    lyric_to_whisper = [None] * len(lyric_tokens)
    for l_idx, w_idx in alignment:
        if l_idx is not None and w_idx is not None:
            if _score(lyric_norms[l_idx], whisper_norms[w_idx]) >= 1:
                lyric_to_whisper[l_idx] = w_idx

    # Group whisper word indices by lyric line (monotone → already ordered)
    n_lines = len(lines)
    line_whisper_indices: list[list[int]] = [[] for _ in range(n_lines)]
    prev_line_last_widx = -1
    for ltok_idx, (_, line_idx) in enumerate(lyric_tokens):
        w_idx = lyric_to_whisper[ltok_idx]
        if w_idx is not None:
            line_whisper_indices[line_idx].append(w_idx)
            if w_idx < prev_line_last_widx and line_idx > 0:
                logger.warning(
                    "Non-monotonic whisper index: line %d got w_idx %d "
                    "but previous line ended at w_idx %d — possible line-boundary leakage",
                    line_idx,
                    w_idx,
                    prev_line_last_widx,
                )
            prev_line_last_widx = max(prev_line_last_widx, w_idx)

    # Build one line_obj per lyric line
    line_objects = []
    for line_idx in range(n_lines):
        display_text = lines[line_idx]
        w_indices = line_whisper_indices[line_idx]

        if not w_indices:
            line_objects.append(
                {
                    "text": display_text,
                    "words": [],
                    "start": None,
                    "end": None,
                }
            )
        else:
            seen: set = set()
            unique: list = []
            for idx in w_indices:
                if idx not in seen:
                    seen.add(idx)
                    unique.append(idx)
            line_words = [words[i] for i in unique]
            line_objects.append(
                {
                    "text": display_text,
                    "words": line_words,
                    "start": line_words[0]["start"],
                    "end": line_words[-1]["end"],
                }
            )

    # Interpolate missing lines
    for i, obj in enumerate(line_objects):
        if obj["start"] is None:
            logger.warning(
                "No aligned whisper words for line: %r. Interpolating timestamps.", obj["text"]
            )

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

    return line_objects
