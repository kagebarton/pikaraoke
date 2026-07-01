#!/usr/bin/env python3
"""Compare today's shipped scheme against a YTASR-as-3rd-DP-source variant.

Today's non-SRT (Genius/txt-sourced) songs run a 2-source (align + transcribe)
joint DP, then patch the result with a post-hoc timing prior (YTASR or LRCLIB,
whichever is available — see ``pikaraoke.pipeline.stages.lyric_align``). This
script replays each non-SRT bundle two ways and scores both against a held-out
LRCLIB reference that is fetched for comparison only, never fed into either
scheme:

  * **old scheme** — exactly what shipped: 2-source DP + replayed windowed
    re-align + whichever prior the bundle recorded. Reuses
    ``replay_alignment_from_bundle.replay_bundle`` unchanged.
  * **new scheme** — YTASR words (parsed fresh from the bundle's own cached
    ``.en.asr.json3``, when one exists) fed into the joint DP as a 3rd
    candidate source, no prior applied at all. Songs with no usable YTASR
    track fall back to the plain 2-source DP — an expected, flagged outcome,
    not an error.

Scoring: for each scheme's output, ``windowed_realign.analyze_pass1`` finds
the lines it placed with genuine matcher-level (not prior-patched) confidence
— excluding prior-touched lines keeps the comparison non-circular for the
5 songs whose *old*-scheme prior source is LRCLIB itself — then
``srt_prior.offset_mad_against_cues`` reports the median offset and MAD of
those placements against the held-out LRCLIB reference.

Held-out LRCLIB is read from each song's cached ``.lrc`` when the bundle
already has one (reused, not re-fetched, so scoring calibrates against the
same variant the original prior did); otherwise fetched fresh via the LRCLIB
search API using the bundle's own Genius title/artist.

Run from the repo root::

    python scripts/replay_ytasr_third_source.py PATH [--beta 0.5,1,1.5,2,3] [--alpha ALPHA]

``PATH`` is a song-library folder (scans ``<PATH>/alignment_debug/*.json``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as ``python scripts/replay_ytasr_third_source.py`` from repo
# root; scripts/ itself is already on sys.path (Python prepends a run
# script's own directory), so the sibling harness imports directly by name.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import replay_alignment_from_bundle as old_harness  # noqa: E402

from pikaraoke.lib import lrclib, ytasr  # noqa: E402
from pikaraoke.lib.joint_match import (  # noqa: E402
    match_words_to_lines_joint_with_stats,
)
from pikaraoke.lib.srt_prior import offset_mad_against_cues  # noqa: E402
from pikaraoke.lib.windowed_realign import analyze_pass1  # noqa: E402

DEFAULT_BETA_GRID = (0.5, 1.0, 1.5, 2.0, 3.0)


def _resolve(song_root: Path, rel_path: str) -> Path:
    return song_root / rel_path


def _load_ytasr_words(bundle: dict, song_root: Path) -> list[dict] | None:
    """Parsed YTASR word stream, or ``None`` when this song has none.

    The lyrics-fetch stage only stashes a ``lyrics.ytasr`` block when the
    caption beat the quality gates (real ASR, dense enough — see
    ``ytasr.is_usable``), so its presence in the bundle already means the
    track is usable; no need to re-gate here.
    """
    ref = bundle["lyrics"].get("ytasr")
    if not ref:
        return None
    asr_path = _resolve(song_root, ref["asr_file"])
    words, _word_seg_frac = ytasr.parse_json3(asr_path.read_text(encoding="utf-8"))
    return words


def _load_lrclib_reference(bundle: dict, song_root: Path) -> dict[int, tuple[float, float]] | None:
    """Held-out LRCLIB cue spans for scoring only — never fed into a matcher.

    Reuses the cached ``.lrc`` when the bundle already has one (the same
    variant the original prior calibrated against); otherwise fetches fresh
    via the bundle's own Genius title/artist. Returns ``None`` when no
    variant is available to score against.
    """
    lines = bundle["lyrics"]["lines"]
    ref = bundle["lyrics"].get("lrclib")
    if ref:
        synced_text, _meta = lrclib.read_lrc(_resolve(song_root, ref["lrc_file"]))
        return lrclib.cue_spans_for_lines(synced_text, lines)

    genius = bundle["lyrics"].get("genius")
    if not genius:
        return None
    records = lrclib.search(genius["title"], genius["artist"])
    record = lrclib.select_candidate(records, lines, bundle.get("media_duration_s"))
    if record is None or not record.get("syncedLyrics"):
        return None
    return lrclib.cue_spans_for_lines(record["syncedLyrics"], lines)


def _selected_sources(line_objects: list[dict], n_lines: int) -> list[str]:
    """Per-line source list, matching apply_srt_prior's own inline pattern."""
    sources = ["absent"] * n_lines
    for obj in line_objects:
        sources[obj["line_id"]] = obj.get("source") or "absent"
    return sources


def _score_against_lrclib(
    line_objects: list[dict],
    transcribe_words: list[dict],
    align_lines: list[str],
    knobs: dict,
    lrclib_cues: dict[int, tuple[float, float]] | None,
) -> dict:
    """MAD of this scheme's own trusted anchors against the held-out LRCLIB cues."""
    if lrclib_cues is None:
        return {"bailed": "no_reference"}
    n_lines = len(align_lines)
    sources = _selected_sources(line_objects, n_lines)
    anchors, _suspects = analyze_pass1(
        align_lines,
        line_objects,
        {"selected_source": sources},
        transcribe_words,
        margin_s=knobs["margin_s"],
        max_edit_ratio=knobs["max_edit_ratio"],
    )
    return offset_mad_against_cues(anchors, lrclib_cues)


def _new_scheme_output(
    bundle: dict, ytasr_words: list[dict] | None, alpha: float, beta: float
) -> list[dict]:
    """3-source (or 2-source fallback) DP + replayed windowed re-align, no prior."""
    transcribe_words = bundle["transcribe_words"]
    lines = bundle["lyrics"]["lines"]
    align_lines = bundle["lyrics"]["align_lines"]
    knobs = bundle["joint_stats"]["knobs"]

    line_objects, _stats = match_words_to_lines_joint_with_stats(
        bundle["words"],
        transcribe_words,
        lines,
        align_lines,
        alpha=alpha,
        beta=beta,
        margin_s=knobs["margin_s"],
        max_edit_ratio=knobs["max_edit_ratio"],
        lookahead=knobs["lookahead"],
        anchor_fallback=knobs["anchor_fallback"],
        ytasr_words=ytasr_words,
    )
    return old_harness._replay_realign(bundle, line_objects, transcribe_words, lines, align_lines)


def _fmt_mad(mad: dict) -> str:
    if mad.get("bailed"):
        return f"bail:{mad['bailed']}"
    return f"{mad['mad_s']:.2f}s/{mad['n_anchors_fit']}a"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("path", type=Path, help="song-library folder (scans alignment_debug/*.json)")
    ap.add_argument(
        "--beta",
        type=str,
        default=",".join(str(b) for b in DEFAULT_BETA_GRID),
        help="comma-separated beta sweep grid",
    )
    ap.add_argument(
        "--alpha",
        type=float,
        default=None,
        help="override alpha (default: bundle's own recorded value)",
    )
    args = ap.parse_args()

    beta_grid = [float(b) for b in args.beta.split(",")]
    debug_dir = args.path / "alignment_debug" if args.path.name != "alignment_debug" else args.path
    bundle_paths = sorted(debug_dir.glob("*.json"))
    if not bundle_paths:
        print(f"No bundles found under {args.path}", file=sys.stderr)
        return 1

    print(
        f"{'song':46s} {'src':>4s} {'old_mad':>14s} {'new_mad(best_beta)':>20s} "
        f"{'beta':>5s} {'crawl':>11s} {'overlap':>13s}"
    )
    print("-" * 120)

    for bp in bundle_paths:
        bundle = json.loads(bp.read_text(encoding="utf-8"))
        if bundle.get("ground_truth_refs", {}).get("youtube_srt_present"):
            continue  # SRT-sourced songs are out of scope for this experiment.

        song_root = bp.parent.parent
        knobs = bundle["joint_stats"]["knobs"]
        alpha = args.alpha if args.alpha is not None else knobs["alpha"]
        transcribe_words = bundle["transcribe_words"]
        align_lines = bundle["lyrics"]["align_lines"]

        ytasr_words = _load_ytasr_words(bundle, song_root)
        lrclib_cues = _load_lrclib_reference(bundle, song_root)

        old_objs = old_harness.replay_bundle(bundle, realign=True)
        old_summary = old_harness.summarize(old_objs)
        old_mad = _score_against_lrclib(old_objs, transcribe_words, align_lines, knobs, lrclib_cues)

        sweep = beta_grid if ytasr_words else [0.0]  # beta is a no-op with no ytasr data
        per_beta = {}
        for beta in sweep:
            new_objs = _new_scheme_output(bundle, ytasr_words, alpha, beta)
            per_beta[beta] = {
                "summary": old_harness.summarize(new_objs),
                "mad": _score_against_lrclib(
                    new_objs, transcribe_words, align_lines, knobs, lrclib_cues
                ),
            }

        best_beta = min(
            per_beta,
            key=lambda b: (
                per_beta[b]["summary"]["n_crawl"],
                per_beta[b]["mad"].get("mad_s", float("inf")),
            ),
        )
        best = per_beta[best_beta]
        src_flag = "3src" if ytasr_words else "2src"
        beta_col = f"{best_beta:.1f}" if ytasr_words else "n/a"
        print(
            f"{bp.stem[:46]:46s} {src_flag:>4s} {_fmt_mad(old_mad):>14s} "
            f"{_fmt_mad(best['mad']):>20s} {beta_col:>5s} "
            f"{old_summary['n_crawl']:2d}->{best['summary']['n_crawl']:<2d}      "
            f"{old_summary['max_overlap']:5.1f}->{best['summary']['max_overlap']:<5.1f}s"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
