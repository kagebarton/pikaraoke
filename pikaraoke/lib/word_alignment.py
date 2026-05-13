"""Word alignment: two-pointer walk matcher with gap interpolation.

Ported from mpv/genius_align/word_extraction.py. stable-ts emits aligned
words in reference order, so a lockstep walk with bounded lookahead is
sufficient — no DP table, no fuzzy scoring. Reference tokens that fail
to anchor get placeholder timestamps interpolated linearly between the
surrounding matched words, so every lyric token ends up in the karaoke
output.
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
    """Cheap equivalence check: exact, contraction, or 1:N contraction split.

    Strict-by-design: no Levenshtein, no phonetic table. The walk matcher
    relies on stable-ts emitting words in reference order, so we just need
    to recognize the cases where a single reference token corresponds to
    a different surface form in the whisper output.
    """
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


def _walk_align(lyric_norms: list, whisper_norms: list, lookahead: int = 3) -> list:
    """Two-pointer lockstep alignment with bounded lookahead.

    Returns mapping[lyric_idx] = whisper_idx | None. On mismatch, scans an
    (lookahead+1) x (lookahead+1) window for the nearest re-sync point and
    advances both pointers to it (skipped lyric tokens stay None; skipped
    whisper words are dropped). If no re-sync is found within the window,
    advances both pointers by one.
    """
    m, n = len(lyric_norms), len(whisper_norms)
    mapping: list = [None] * m
    i = j = 0
    while i < m and j < n:
        if _match_simple(lyric_norms[i], whisper_norms[j]):
            mapping[i] = j
            i += 1
            j += 1
            continue
        best = None
        best_cost = lookahead * 2 + 1
        for di in range(min(lookahead + 1, m - i)):
            for dj in range(min(lookahead + 1, n - j)):
                if di == 0 and dj == 0:
                    continue
                cost = di + dj
                if cost >= best_cost:
                    continue
                if _match_simple(lyric_norms[i + di], whisper_norms[j + dj]):
                    best = (di, dj)
                    best_cost = cost
        if best is None:
            i += 1
            j += 1
        else:
            di, dj = best
            i += di
            j += dj
            mapping[i] = j
            i += 1
            j += 1
    return mapping


# ---------------------------------------------------------------------------
# Public API: match_words_to_lines
# ---------------------------------------------------------------------------


def match_words_to_lines(
    words: list,
    lines: list[str],
    align_lines: list[str] | None = None,
    lookahead: int = 3,
) -> list[dict]:
    """Assign whisper words to lyric lines via two-pointer walk matching.

    For each reference token, either pair it with a whisper word (and use
    that word's timing) or synthesize a placeholder word with timestamps
    interpolated linearly between the surrounding matched anchors. Every
    reference token therefore ends up in the karaoke output, and the
    final per-line word lists are gap-free.

    Whisper words that match no lyric token (hallucinations, backing vox)
    are silently dropped. Lyric lines with no normalizable tokens
    (paren-only display lines) inherit timing from their neighbors.

    Args:
        words: flat whisper word list from the worker.
        lines: display text per lyric line (may include inline parens).
        align_lines: paren-stripped text per lyric line for alignment.
            If None, falls back to lines.
        lookahead: max (lyric, whisper) skip window when re-syncing.
    """
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
        return [{"text": d, "words": [], "start": 0.0, "end": 0.0} for d in lines]

    whisper_norms = [_normalize_token(w["word"]) for w in words]
    lyric_norms = [lt[0] for lt in lyric_tokens]

    mapping = _walk_align(lyric_norms, whisper_norms, lookahead)

    # Materialize a word dict for every anchored lyric token, copying timing
    # from the matched whisper word.
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
                "speaker": wsrc.get("speaker"),
                "dominant_speaker": wsrc.get("dominant_speaker"),
            }

    matched_count = sum(1 for tw in token_words if tw is not None)
    logger.info(
        "Walk align: matched %d/%d reference tokens (%.1f%%); %d whisper words consumed",
        matched_count,
        n_tokens,
        100.0 * matched_count / n_tokens if n_tokens else 0.0,
        sum(1 for v in mapping if v is not None),
    )

    # Interpolate runs of unmatched lyric tokens between anchored neighbors.
    k = 0
    while k < n_tokens:
        if token_words[k] is not None:
            k += 1
            continue
        run_end = k
        while run_end < n_tokens and token_words[run_end] is None:
            run_end += 1
        prev_end = token_words[k - 1]["end"] if k > 0 else 0.0
        next_start = token_words[run_end]["start"] if run_end < n_tokens else prev_end
        if next_start < prev_end:
            next_start = prev_end
        run_len = run_end - k
        slot = (next_start - prev_end) / run_len if run_len > 0 else 0.0
        for offset in range(run_len):
            s = prev_end + offset * slot
            e = prev_end + (offset + 1) * slot
            _, _, raw = lyric_tokens[k + offset]
            token_words[k + offset] = {
                "word": raw,
                "start": s,
                "end": e,
                "speaker": None,
                "dominant_speaker": None,
            }
        k = run_end

    line_word_lists: list = [[] for _ in range(n_lines)]
    for k, (_, line_idx, _) in enumerate(lyric_tokens):
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
    # timing from neighbors.
    for i, obj in enumerate(line_objects):
        if obj["start"] is None:
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
