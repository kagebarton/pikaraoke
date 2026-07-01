"""YouTube auto-caption (ASR) parsing + cue-span derivation for the timing prior.

Genius-origin (txt) songs reach the matcher with no per-line cue times. YouTube's
auto-generated captions are a free, *same-clock* timing source (unlike LRCLIB's
different master), carrying per-word timestamps in the ``json3`` caption format.
This module turns a downloaded ``json3`` track into the inputs the existing SRT
timing prior (``pikaraoke/lib/srt_prior.py``) consumes — paralleling ``lrclib``'s
role on the LRCLIB path: parse -> quality-gate -> derive cue spans.

Two failure modes are gated out before adoption (either falls back to LRCLIB):

  * **Manual-mirrored / line-level tracks.** A track *named* like an auto track
    can actually be the uploader's manual caption mirrored back, carrying no
    per-word timing. Real ASR emits per-word ``tOffsetMs`` segs; the word-seg
    fraction (segs with ``tOffsetMs`` over non-empty segs) separates them
    cleanly — 73-82% on real ASR vs 0% on manual-mirrored across the corpus.
  * **``[Music]`` degeneracy.** Music-video ASR often tags instrumental
    stretches ``[Music]`` / ``♪`` instead of transcribing. The bracket/note
    filter (reusing ``genius_lyrics.clean_srt_line``) strips those segments, and
    a words-per-minute floor rejects a caption left too sparse to time anything.

Cue spans are derived per line by fuzzy candidate search, NOT a single
whole-song walk-align: the latter collapses on long/repetitive songs (a corpus
song mapped 1/102 lines), while per-line ``find_candidates`` + greedy monotonic
selection recovered it to 31/102 at sub-second MAD.
"""

from __future__ import annotations

import json
import logging

from pikaraoke.lib.candidate_match import best_candidate_per_line, find_candidates
from pikaraoke.lib.genius_lyrics import clean_srt_line
from pikaraoke.lib.token_align import _normalize_token

logger = logging.getLogger(__name__)

# Below this fraction of word-level segs the track is manual-mirrored or
# line-level, not real ASR — reject it. Real ASR runs 73-82% across the corpus
# (the per-event first word carries no offset), manual-mirrored is a flat 0%.
WORD_SEG_MIN_FRAC = 0.5

# Real words-per-minute over media duration below this means the caption
# degenerated to ``[Music]``/sparse tags with too little timing to adopt. Shared
# value with the regen tool's caption gate.
MIN_CAPTION_WPM = 15.0

# The final word has no following word to bound it; hold it this long.
LAST_WORD_HOLD_S = 0.3

# Cap on a word's inferred duration. ``end`` is inferred as the next word's
# start, so the last word before an instrumental break would otherwise inherit
# the whole gap. Word ends feed the joint DP's 3rd-source path (candidate
# windows, agreement reference spans, per-word render timings), where a
# ballooned end spans the break: it blocks legal DP successors, dilutes
# ``_range_agreement`` for candidates covering only the sung part, and sweeps
# the rendered word across the gap. Generous enough for a held note.
MAX_WORD_DUR_S = 2.0

# Per-line fuzzy-match tolerance against ASR mis-hears. Looser than the matcher's
# default (0.25): ASR over backing music garbles more than whisper, and a wrong
# line mapping is caught downstream by the prior's anchor-MAD gate.
CANDIDATE_MAX_EDIT_RATIO = 0.34


def parse_json3(text: str) -> tuple[list[dict], float]:
    """Flatten a ``json3`` caption into a word stream + word-seg fraction.

    Returns ``(words, word_seg_frac)`` where ``words`` is a time-sorted list of
    ``{word, norm, start, end}`` (seconds) and ``word_seg_frac`` is the share of
    non-empty segs carrying ``tOffsetMs`` — the real-ASR discriminator
    (see module docstring), measured *before* the bracket/note filter so a
    degenerate ``[Music]`` track is judged on its raw timing, not survivors.

    Each word's ``start`` is ``(tStartMs + tOffsetMs)/1000``; ``end`` is the next
    word's start, capped at :data:`MAX_WORD_DUR_S` (the last word holds
    :data:`LAST_WORD_HOLD_S`). Segments empty
    after :func:`pikaraoke.lib.genius_lyrics.clean_srt_line` (``[Music]``, ``♪``,
    ``(applause)``) are dropped, and consecutive identical ``(norm, start)``
    tokens are de-duplicated (auto-caption roll-up artifact).
    """
    data = json.loads(text)
    raw: list[tuple[float, str]] = []
    n_segs = 0
    n_word_segs = 0
    for event in data.get("events", []):
        t_start = event.get("tStartMs", 0)
        for seg in event.get("segs") or []:
            utf8 = seg.get("utf8", "")
            if not utf8.strip():
                continue
            n_segs += 1
            if "tOffsetMs" in seg:
                n_word_segs += 1
            start = (t_start + seg.get("tOffsetMs", 0)) / 1000.0
            lexical = clean_srt_line(utf8)
            if lexical:
                raw.append((start, lexical))

    words: list[dict] = []
    for start, lexical in raw:
        for tok in lexical.split():
            norm = _normalize_token(tok)
            if not norm:
                continue
            if words and words[-1]["norm"] == norm and words[-1]["start"] == start:
                continue
            words.append({"word": tok, "norm": norm, "start": start})
    words.sort(key=lambda w: w["start"])
    for i, w in enumerate(words):
        nxt = words[i + 1]["start"] if i + 1 < len(words) else w["start"] + LAST_WORD_HOLD_S
        w["end"] = min(nxt, w["start"] + MAX_WORD_DUR_S)

    word_seg_frac = (n_word_segs / n_segs) if n_segs else 0.0
    return words, word_seg_frac


def is_usable(words: list[dict], word_seg_frac: float, media_dur: float | None) -> bool:
    """Whether the parsed caption is real word-level ASR dense enough to adopt.

    Two gates (either failure -> fall back to LRCLIB): the word-seg fraction must
    clear :data:`WORD_SEG_MIN_FRAC` (reject manual-mirrored/line-level), and the
    real words-per-minute over ``media_dur`` must clear :data:`MIN_CAPTION_WPM`
    (reject ``[Music]`` degeneracy). An unknown ``media_dur`` is rejected: the
    degeneracy gate can't run without it, so adopt nothing rather than risk a
    sparse caption unchecked (the prior must never degrade a song it can't vet).
    """
    if word_seg_frac < WORD_SEG_MIN_FRAC:
        return False
    if not media_dur or media_dur <= 0:
        return False
    return len(words) / (media_dur / 60.0) >= MIN_CAPTION_WPM


def cue_spans_for_lines(
    words: list[dict], align_lines: list[str]
) -> dict[int, tuple[float, float]] | None:
    """Map the ASR word stream onto lyric ``align_lines`` as per-line cue spans.

    The YTASR analog of :func:`pikaraoke.lib.lrclib.cue_spans_for_lines`. Runs a
    per-line fuzzy candidate search over the ASR tokens, keeps each line's
    best-scoring candidate, then takes a greedy monotonic subset (a kept line's
    start index never moves backward) so partial ASR coverage and repeated
    choruses never reorder. Each kept line's span is
    ``(words[start].start, words[end-1].end)``. Lines with no candidate get no
    cue — the prior leaves/fills them. Returns ``None`` when nothing maps.
    """
    asr_norms = [w["norm"] for w in words]
    line_toks = [
        [norm for norm in (_normalize_token(t) for t in line.split()) if norm]
        for line in align_lines
    ]
    candidates = find_candidates(asr_norms, line_toks, max_edit_ratio=CANDIDATE_MAX_EDIT_RATIO)
    best = best_candidate_per_line(candidates)

    spans: dict[int, tuple[float, float]] = {}
    last_start = -1
    for line_id in sorted(best):
        start, end, _ = best[line_id]
        if start < last_start:
            continue
        last_start = start
        spans[line_id] = (words[start]["start"], words[end - 1]["end"])
    return spans or None
