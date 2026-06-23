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
