"""Token primitives for lyric matching: normalization + lockstep aligner.

Two layers the matchers share:

  * Normalization — ``_normalize_token`` (lowercase, NFKC, ASCII-fold,
    strip non-word chars) and ``fold_to_ascii`` (homoglyph + diacritic
    folding) so lyric text and whisper output compare on equal footing.
    ``_match_simple`` adds cheap contraction-aware equivalence.
  * ``_walk_align`` — a two-pointer lockstep aligner with bounded
    lookahead that pairs an ordered token sequence to a whisper word
    stream. Biased toward preserving lyric anchors: asymmetric lookahead
    absorbs runs of extra/noisy whisper output, a confirmed re-sync
    filters spurious single-word anchors, and a whisper-skip budget drops
    noise before reluctantly skipping a lyric token.
  * ``match_words_to_tokens`` — a monotone assignment DP (max matched
    words, then min time deviation) that maps an ordered token sequence
    to an ordered word stream on strict normalised equality. For word
    streams produced by forced alignment of the token text itself, where
    the only divergence is dropped words.

``candidate_match._build_line_object`` runs ``_walk_align`` inside a
selected window to assign per-word timings; the joint matcher
(``joint_match``) consumes the normalization helpers directly.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_STRIP_NONWORD_RE = re.compile(r"[^\w]", re.UNICODE)

# Cyrillic lookalikes of Latin letters. Lyric sites watermark fetched
# text with these ("wеre" with U+0435), which silently breaks token
# equality against whisper output.
_CONFUSABLES = str.maketrans("аеіоруѕсхј", "aeiopyscxj")


def fold_to_ascii(text: str) -> str:
    """Fold homoglyphs and diacritics to plain ASCII letters.

    Whisper writes accented words unaccented ("souffle" for "soufflé"),
    so both comparison sides are folded before matching. Expects
    lowercased input (the confusable table is lowercase-only).
    """
    text = unicodedata.normalize("NFKD", text.translate(_CONFUSABLES))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


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
    """Lowercase, NFKC-normalize, ASCII-fold, strip non-word chars."""
    token = fold_to_ascii(unicodedata.normalize("NFKC", token).lower())
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
# Monotone assignment DP
# ---------------------------------------------------------------------------


def match_words_to_tokens(
    token_norms: list[str],
    token_times: list[float],
    word_norms: list[str],
    word_times: list[float],
) -> list[int | None]:
    """Monotone token<-word assignment: max matches, then min time deviation.

    Both streams are ordered; a match requires equal normalised text (strict
    — on both call paths the word stream came from forced alignment of the
    same text, so contraction/homoglyph divergence cannot arise). Among the
    assignments with the most matches, prefer the one whose word times sit
    closest to the tokens' expected times. The tiebreak is what makes
    repeats safe: when a whole repeated line's words were dropped, plain
    greedy text matching would hand the twin line's words to the earlier
    line and shift every later repeat; time deviation picks the twin. It is
    a tiebreak, not a gate, so a constant offset (which shifts every
    deviation equally) cannot flip a correct assignment.

    Two callers: the cue split (``cue_align``, cue-expected token times vs
    word start times) and the joint matcher's align-range assignment
    (``joint_match._line_align_ranges``, index pseudo-times on both sides).

    Returns, per token, the index of its matched word (or None). Words that
    match no token (e.g. punctuation-only tokens the tokeniser dropped but
    the aligner emitted) are skipped instead of stalling the scan.
    """
    n_tok, n_word = len(token_norms), len(word_norms)
    assign: list[int | None] = [None] * n_tok
    if not n_tok or not n_word:
        return assign
    # dp over (tokens consumed, words consumed) -> (matches, -total_deviation),
    # maximised lexicographically. Rolling rows plus a per-cell choice record
    # (0 = skip token, 1 = skip word, 2 = match) for the backtrack.
    prev: list[tuple[int, float]] = [(0, 0.0)] * (n_word + 1)
    choices: list[bytes] = []
    for i in range(1, n_tok + 1):
        cur: list[tuple[int, float]] = [(0, 0.0)] * (n_word + 1)
        row = bytearray(n_word + 1)
        norm, expected = token_norms[i - 1], token_times[i - 1]
        for j in range(1, n_word + 1):
            best, choice = prev[j], 0
            if cur[j - 1] > best:
                best, choice = cur[j - 1], 1
            if norm == word_norms[j - 1]:
                matches, neg_dev = prev[j - 1]
                cand = (matches + 1, neg_dev - abs(word_times[j - 1] - expected))
                if cand > best:
                    best, choice = cand, 2
            cur[j] = best
            row[j] = choice
        choices.append(bytes(row))
        prev = cur
    i, j = n_tok, n_word
    while i > 0 and j > 0:
        choice = choices[i - 1][j]
        if choice == 2:
            assign[i - 1] = j - 1
            i -= 1
            j -= 1
        elif choice == 1:
            j -= 1
        else:
            i -= 1
    return assign
