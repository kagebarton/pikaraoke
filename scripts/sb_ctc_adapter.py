#!/usr/bin/env python
"""S-B: CTC (MMS_FA) slice_align adapter for the scaffold corpus probe.

Originally scratchpad-only per plans/timing-source-pillars.md ground rules;
committed with plans/joint-matcher-catchall-refit.md (Ken's call) as the
reference implementation for that plan's Phase 2a CTC arm — this is the
adapter the S-B corpus run (GATE S-2, CTC selected) actually ran.

Wraps the proven MMS_FA recipe (``phase1b_score_oracle``: the same
normalize/tokenize/align path the eyeball probe's 33/33-clean run validated)
behind the ``cue_align.align_song`` slice_align contract: ``(t0, t1, text,
label) -> absolute-time words | None``.

Reuses the per-song cached full-song emission (``phase1b_score_oracle
.EMISSION_DIR``) instead of a fresh per-slice GPU forward pass — one
whole-song forward pass, sliced by frame index many times per song (once per
section, plus any per-line realign rescue). Loaded via the harness's generic
``--slice-align-module`` hook (scripts/scaffold_align_song.py /
scaffold_align_corpus.py), which expects this file to expose
``make_slice_align`` with the same signature as
``cue_align_song._make_slice_align``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase1b_score_oracle import (  # noqa: E402
    SR,
    get_emission,
    load_model,
    normalize_word,
)

logger = logging.getLogger("sb_ctc_adapter")

_model_cache: dict[str, tuple] = {}


def _model():
    if "m" not in _model_cache:
        _model_cache["m"] = load_model()
    return _model_cache["m"]


def make_slice_align(vocal_wav: Path, tmp: Path, stem: str, worker):
    """Factory matching ``cue_align_song._make_slice_align``'s signature.

    ``worker``/``tmp`` are unused -- the CTC path never touches the
    WhisperWorker subprocess or writes slice files, only slices the cached
    emission tensor by frame index. ``vocal_wav`` is passed through to
    :func:`get_emission` for the cache-miss path.
    """
    model, tokenizer, aligner = _model()
    emission, ratio = get_emission(stem, vocal_wav, model, force=False)

    def slice_align(t0: float, t1: float, text: str, label: str) -> list[dict] | None:
        # Dual bookkeeping: keep each raw word alongside its normalized form
        # so an OOV word (normalizes to "") is dropped from the tokenizer
        # input but every surviving word still carries its real display text
        # forward to the returned word list.
        kept = [(raw, normalize_word(raw)) for raw in text.split()]
        kept = [(raw, norm) for raw, norm in kept if norm]
        if not kept:
            return None
        norm_words = [norm for _, norm in kept]

        frame_lo = max(0, int(t0 * SR / ratio))
        frame_hi = min(emission.size(0), int(t1 * SR / ratio) + 1)
        if frame_hi <= frame_lo:
            return None

        sub = emission[frame_lo:frame_hi].to("cuda")
        token_ids = tokenizer(norm_words)
        try:
            with torch.inference_mode():
                spans = aligner(sub, token_ids)
        except RuntimeError as e:
            logger.warning("%s: CTC align failed: %s; re-pacing from cue", label, e)
            return None

        words = []
        for (raw, _), word_spans in zip(kept, spans):
            words.append(
                {
                    "word": raw,
                    "start": t0 + word_spans[0].start * ratio / SR,
                    "end": t0 + word_spans[-1].end * ratio / SR,
                }
            )
        return words

    return slice_align
