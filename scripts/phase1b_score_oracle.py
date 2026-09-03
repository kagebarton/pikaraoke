#!/usr/bin/env python
"""Phase 1b emission score oracle probe (GATE O) — MMS_FA recipe module.

Originally scratchpad-only per plans/timing-source-pillars.md ground rules;
committed with plans/joint-matcher-catchall-refit.md (Ken's call) because its
model/emission/align recipe is the reference implementation for that plan's
Phase 2a CTC arm and the eventual pikaraoke/lib/ctc_align.py port. The GATE O
scoring passes (mean/min word-z tables) are retained for provenance.

Recomputes MMS_FA emissions per song (the eyeball probe's chunked recipe —
compute once, slice many), runs the forced aligner over the bundle's
align_lines, and writes a per-song per-line score table. Emissions and score
tables cache under ``<temp>/ctc_probe/`` (see ``CACHE_ROOT``); to reuse a
previous session's emission cache, copy its ``emissions/*.pt`` files there.

Usage:
    python scripts/phase1b_score_oracle.py                     # full corpus
    python scripts/phase1b_score_oracle.py --only "In Summer"  # smoke test
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio

# Sibling import: the repo's editable install already puts ``pikaraoke`` on
# the path; only ``scripts`` needs adding so ``cue_align_song`` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cue_align_song import _ffmpeg, find_vocal  # noqa: E402

from pikaraoke.lib.get_platform import get_temp_directory  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("phase1b")

SONGS_ROOT = Path("/home/ken/pikaraoke-songs")  # --songs-root overrides
DEBUG_DIR = SONGS_ROOT / "alignment_debug"
CACHE_ROOT = Path(get_temp_directory()) / "ctc_probe"
EMISSION_DIR = CACHE_ROOT / "emissions"
SCORES_DIR = CACHE_ROOT / "line_scores"

CHUNK_S = 20.0
SR = 16000
CHARSET = set("abcdefghijklmnopqrstuvwxyz'")


def normalize_word(word: str) -> str:
    """Lowercase, ASCII-fold apostrophes, drop anything outside the MMS_FA
    charset (letters + apostrophe -- confirmed via bundle.get_tokenizer()
    .dictionary). Returns "" for a word with nothing left (pure
    punctuation/symbols), matching the eyeball probe's OOV handling."""
    w = word.lower().replace("’", "'")
    return "".join(c for c in w if c in CHARSET)


def load_model():
    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model().to("cuda").eval()
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()
    return model, tokenizer, aligner


def compute_emission(model, wav: torch.Tensor) -> torch.Tensor:
    """Chunked ~20s forward passes, concatenated along the time dim.
    Chunk-boundary edge effects are negligible per the eyeball probe's
    precedent (its 33/33 clean run used this same recipe)."""
    chunk_samples = int(CHUNK_S * SR)
    chunks = []
    with torch.inference_mode():
        for start in range(0, wav.size(1), chunk_samples):
            piece = wav[:, start : start + chunk_samples].to("cuda")
            emission, _ = model(piece)
            chunks.append(emission.cpu())
    return torch.cat(chunks, dim=1).squeeze(0)


def set_songs_root(root: Path) -> None:
    """Repoint the corpus at another box's library (see ``--songs-root``)."""
    global SONGS_ROOT, DEBUG_DIR
    SONGS_ROOT = root
    DEBUG_DIR = root / "alignment_debug"


def all_bundles() -> list[Path]:
    """All corpus bundles -- Phase 1b scores the whole corpus, not just
    the genius-origin subset (labels + well-behaved songs span both SRT-
    and Genius-origin songs)."""
    return sorted(DEBUG_DIR.glob("*.json"))


def find_media(stem: str) -> Path | None:
    for ext in (".mp4", ".webm", ".mkv"):
        cand = SONGS_ROOT / f"{stem}{ext}"
        if cand.is_file():
            return cand
    return None


def get_emission(stem: str, vocal: Path, model, force: bool) -> tuple[torch.Tensor, float] | None:
    """Emission tensor + frames-to-seconds ratio, cached to ``EMISSION_DIR``
    as {"emission": Tensor[T,V], "ratio": float}. ``ratio = num_wave_samples /
    emission.size(0)`` per the eyeball probe's recipe -- computed once from
    the wav actually fed to the model, not re-derived from chunk math."""
    cache_path = EMISSION_DIR / f"{stem}.pt"
    if cache_path.is_file() and not force:
        cached = torch.load(cache_path)
        return cached["emission"], cached["ratio"]

    tmp = Path(get_temp_directory())
    wav_path = tmp / f"{stem}__phase1b.wav"
    try:
        _ffmpeg(["-i", str(vocal), "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(wav_path)])
        # soundfile, not torchaudio.load: this torchaudio build's default
        # backend requires torchcodec, which isn't installed in this env.
        data, file_sr = sf.read(str(wav_path), dtype="float32")
        if file_sr != SR:
            raise ValueError(f"unexpected sample rate {file_sr}")
        wav = torch.from_numpy(np.atleast_2d(data))
        num_samples = wav.size(1)
        emission = compute_emission(model, wav)
    finally:
        wav_path.unlink(missing_ok=True)

    ratio = num_samples / emission.size(0)
    EMISSION_DIR.mkdir(parents=True, exist_ok=True)
    torch.save({"emission": emission, "ratio": ratio}, cache_path)
    return emission, ratio


def align_words(model, tokenizer, aligner, bundle_path: Path, force: bool) -> dict | None:
    """Shared recipe: cached emission -> normalize/tokenize align_lines ->
    full-song forced alignment -> flat per-word (line_id, norm, score,
    start_s, end_s). Reused by the primary mean/min-word-z pass and the
    rescue-stat pass (S-decode/S-shift/S-tx), which both need per-word
    timings/tokens, not just the line-level summary."""
    stem = bundle_path.stem
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    align_lines: list[str] = bundle["lyrics"]["align_lines"]

    media = find_media(stem)
    vocal = find_vocal(media) if media else None
    if vocal is None:
        logger.warning("skip %s: no media/vocal", stem[:50])
        return None

    emission, ratio = get_emission(stem, vocal, model, force)
    logger.info("%s: emission %s (ratio=%.5f)", stem[:50], tuple(emission.shape), ratio)

    # Per-word normalize + tokenize, tracking which words survive (non-empty
    # normalized form) so the flat aligned-word list slices back into lines.
    words_per_line: list[int] = []
    flat_words: list[str] = []
    word_line_id: list[int] = []
    skipped = 0
    for line_id, line in enumerate(align_lines):
        n_kept = 0
        for w in line.split():
            norm = normalize_word(w)
            if not norm:
                skipped += 1
                continue
            flat_words.append(norm)
            word_line_id.append(line_id)
            n_kept += 1
        words_per_line.append(n_kept)

    if not flat_words:
        logger.warning("%s: no alignable words after normalization", stem[:50])
        return None

    token_ids = tokenizer(flat_words)
    with torch.inference_mode():
        token_spans = aligner(emission.to("cuda"), token_ids)

    # Per-word: mean token score over that word's tokens, and start/end secs.
    word_scores: list[float] = []
    word_starts: list[float] = []
    word_ends: list[float] = []
    for spans in token_spans:
        scores = [s.score for s in spans]
        word_scores.append(sum(scores) / len(scores))
        word_starts.append(spans[0].start * ratio / SR)
        word_ends.append(spans[-1].end * ratio / SR)

    return {
        "stem": stem,
        "align_lines": align_lines,
        "words_per_line": words_per_line,
        "flat_words": flat_words,
        "word_line_id": word_line_id,
        "word_scores": word_scores,
        "word_starts": word_starts,
        "word_ends": word_ends,
        "skipped": skipped,
        "emission": emission,
        "ratio": ratio,
    }


def run_song(model, tokenizer, aligner, bundle_path: Path, force: bool) -> dict | None:
    aligned = align_words(model, tokenizer, aligner, bundle_path, force)
    if aligned is None:
        return None
    stem = aligned["stem"]
    align_lines = aligned["align_lines"]
    word_line_id = aligned["word_line_id"]
    word_scores = aligned["word_scores"]
    word_starts = aligned["word_starts"]
    skipped = aligned["skipped"]

    # Group into lines.
    line_word_scores: list[list[float]] = [[] for _ in align_lines]
    line_first_start: list[float | None] = [None] * len(align_lines)
    for wi, lid in enumerate(word_line_id):
        line_word_scores[lid].append(word_scores[wi])
        if line_first_start[lid] is None:
            line_first_start[lid] = word_starts[wi]

    mean_raw = [sum(s) / len(s) if s else None for s in line_word_scores]
    min_raw = [min(s) if s else None for s in line_word_scores]

    def zscore(vals: list[float | None]) -> list[float | None]:
        defined = [v for v in vals if v is not None]
        if len(defined) < 2:
            return [None for _ in vals]
        mean = sum(defined) / len(defined)
        var = sum((v - mean) ** 2 for v in defined) / len(defined)
        sd = var**0.5
        if sd == 0:
            return [0.0 if v is not None else None for v in vals]
        return [(v - mean) / sd if v is not None else None for v in vals]

    mean_z = zscore(mean_raw)
    min_z = zscore(min_raw)

    out = {
        "stem": stem,
        "n_lines": len(align_lines),
        "n_words_total": sum(len(line.split()) for line in align_lines),
        "n_words_skipped": skipped,
        "n_words_aligned": len(aligned["flat_words"]),
        "lines": [
            {
                "line_id": i,
                "text": align_lines[i],
                "n_words": aligned["words_per_line"][i],
                "mean_word_raw": mean_raw[i],
                "min_word_raw": min_raw[i],
                "mean_word_z": mean_z[i],
                "min_word_z": min_z[i],
                "start": line_first_start[i],
            }
            for i in range(len(align_lines))
        ],
    }
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    (SCORES_DIR / f"{stem}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="substring filter on bundle filename")
    ap.add_argument("--force", action="store_true", help="recompute emissions even if cached")
    ap.add_argument(
        "--songs-root",
        type=Path,
        default=SONGS_ROOT,
        help="song library root (default: the Linux box's)",
    )
    args = ap.parse_args(argv)

    set_songs_root(args.songs_root)
    bundles = all_bundles()
    if args.only:
        bundles = [b for b in bundles if args.only.lower() in b.stem.lower()]
    if not bundles:
        ap.error("no matching bundles")

    model, tokenizer, aligner = load_model()
    ok, failed = 0, []
    for bp in bundles:
        try:
            result = run_song(model, tokenizer, aligner, bp, force=args.force)
            if result is not None:
                ok += 1
            else:
                failed.append(bp.stem[:50])
        except Exception:
            logger.exception("failed: %s", bp.stem[:50])
            failed.append(bp.stem[:50])
    logger.info("done: %d/%d ok", ok, len(bundles))
    if failed:
        logger.warning("failed/skipped: %s", failed)


if __name__ == "__main__":
    main()
