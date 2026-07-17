#!/usr/bin/env python3
"""Offline alpha/beta sweep of the non-SRT joint matcher, scored vs held-out LRCLIB.

The non-SRT (Genius/txt-sourced) songs run the shipped 3-source joint DP
(align + transcribe + YTASR) followed by windowed re-align — see
``pikaraoke.pipeline.stages.lyric_align``. This harness replays each non-SRT
bundle through that same matcher straight from its captured word streams (no
whisper, no GPU), sweeps ``alpha``/``beta``, and scores each combination
against a held-out LRCLIB reference that is fetched for comparison only and
never fed into the matcher.

It is the tuning + baseline harness for the joint path: run it at a fixed
``alpha``/``beta`` to snapshot a per-song MAD / overlap / placed baseline that
later matcher changes diff against, or sweep the grid to retune the knobs.

What replays exactly vs. approximately:

  * **Joint match** replays exactly — it consumes only captured inputs
    (``words`` / ``transcribe_words`` / parsed YTASR) at the swept knobs.
  * **Windowed re-align** replays from each span's captured refined
    ``align_words`` via ``replay_span`` + ``merge_spans``, re-matched at the
    swept ``alpha``/``beta`` with YTASR threaded in as a third span-replay
    source. Span boundaries and the suspect set were chosen from the
    original pass-1, so they do not move here.
  * **Edge snap** is *not* replayed — it needs the vocal stem audio this
    offline harness deliberately never touches. The bundle's recorded
    ``output_line_timings`` (post-snap) is shown as a sanity column only; the
    measured baseline is this harness's snap-free replay, so pre/post-change
    diffs stay apples-to-apples.

Scoring: for each combination, ``windowed_realign.analyze_pass1`` finds the
lines placed with genuine matcher-level confidence, then
``srt_cues.offset_mad_against_cues`` reports the median offset and MAD of those
placements against the held-out LRCLIB reference.

Held-out LRCLIB is read from each song's cached ``.lrc`` when the bundle has
one; else a flat per-song cache at ``<PATH>/lrclib/<stem>`` when one exists;
otherwise fetched fresh via the LRCLIB search API using the bundle's own
Genius title/artist. Songs with no reference by any tier are scored ``bailed``.

Run from the repo root::

    python scripts/replay_ytasr_third_source.py PATH [--alpha 2.0] [--beta 2.0] [--write-ass]

``--alpha`` / ``--beta`` are comma-separated grids swept as a product; the
best-scoring ``(alpha, beta)`` per song is reported (fewest crawl lines, then
lowest MAD). For a fixed-point baseline pass a single value to each. ``alpha``
weights align agreement independent of YTASR, so it is swept for every song;
``beta`` is a no-op (fixed at 0.0) for songs with no usable YTASR track.

``--write-ass`` renders each song's winning combo to
``karaoke/<stem>.ytasr3src.ass`` for visual inspection, never overwriting the
shipped ``<stem>.ass``.

The ``coverage`` column reports the winning combo's ``placed/n_lines``,
flagged with ``!`` below ``--min-coverage`` (default 0.85) — MAD/overlap are
scored over placed anchors only, so a song can sit at a low-coverage
placement count without either metric ever showing it.

``PATH`` is a song-library folder (scans ``<PATH>/alignment_debug/*.json``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as ``python scripts/replay_ytasr_third_source.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib import lrclib, ytasr  # noqa: E402
from pikaraoke.lib.joint_match import (  # noqa: E402
    match_words_to_lines_joint_with_stats,
)
from pikaraoke.lib.srt_cues import offset_mad_against_cues  # noqa: E402
from pikaraoke.lib.windowed_realign import (  # noqa: E402
    analyze_pass1,
    merge_spans,
    replay_span,
    selected_sources,
)
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage  # noqa: E402

DEFAULT_BETA_GRID = (0.5, 1.0, 1.5, 2.0, 3.0)
DEFAULT_ALPHA_GRID = (0.5, 1.0, 1.5, 2.0, 3.0)

# A placed line sweeping slower than this many seconds per lyric word reads as a
# crawl (a mis-placement artifact). Matches the diagnosis band: corpus crawls
# are >=1.9 s/word, legit lines <=1.3 s/word.
CRAWL_S_PER_WORD = 1.5

# Tag stamped on --write-ass output filenames, matching the karaoke/ folder's
# existing <stem>.asralign.ass / <stem>.jointalign.ass side-by-side convention.
ASS_TAG = "ytasr3src"


def summarize(line_objects: list[dict]) -> dict:
    """Crawl/overlap/placed metrics for a set of placed line objects."""
    placed = sorted((o for o in line_objects if o.get("words")), key=lambda o: o["start"])
    overlaps = [placed[i]["end"] - placed[i + 1]["start"] for i in range(len(placed) - 1)]
    crawls = [o for o in placed if (o["end"] - o["start"]) / len(o["words"]) > CRAWL_S_PER_WORD]
    return {
        "n_placed": len(placed),
        "max_overlap": max(overlaps, default=0.0),
        "n_crawl": len(crawls),
    }


def recorded_summary(bundle: dict) -> dict:
    """Crawl/overlap/placed metrics from the bundle's recorded final timings.

    This is the shipped (post-edge-snap) output the pipeline actually wrote —
    a sanity reference the snap-free replay is compared against, not the
    baseline itself. Lines the E1 gated-fill hook filled from LRCLIB
    (``joint_stats.lrclib_fill.filled_lids``) are excluded before computing
    any of these stats: they come FROM LRCLIB, so folding them into a
    placement count sat alongside a LRCLIB-scored replay would be circular.
    """
    filled_lids = set(
        (bundle.get("joint_stats") or {}).get("lrclib_fill", {}).get("filled_lids") or []
    )
    olt = [
        e
        for e in bundle["output_line_timings"]
        if e["n_words"] > 0 and e["line_id"] not in filled_lids
    ]
    olt.sort(key=lambda e: e["start"])
    overlaps = [olt[i]["end"] - olt[i + 1]["start"] for i in range(len(olt) - 1)]
    crawls = [e for e in olt if (e["end"] - e["start"]) / e["n_words"] > CRAWL_S_PER_WORD]
    return {
        "n_placed": len(olt),
        "max_overlap": max(overlaps, default=0.0),
        "n_crawl": len(crawls),
        "n_excluded_fills": len(filled_lids),
    }


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


def _load_lrclib_reference(
    bundle: dict, song_root: Path, stem: str
) -> dict[int, tuple[float, float]] | None:
    """Held-out LRCLIB cue spans for scoring only — never fed into a matcher.

    Preference order: (1) the bundle's own cached ``.lrc``; (2) a flat
    per-song cache at ``<song_root>/lrclib/<stem>``; (3) a fresh live search.
    Returns ``None`` when no variant is available by any of the three.
    """
    lines = bundle["lyrics"]["lines"]
    ref = bundle["lyrics"].get("lrclib")
    if ref:
        synced_text, _meta = lrclib.read_lrc(_resolve(song_root, ref["lrc_file"]))
        return lrclib.cue_spans_for_lines(synced_text, lines)

    flat_cache = song_root / "lrclib" / stem
    if flat_cache.is_file():
        # Hand-provisioned files carry no encoding guarantee the way the
        # pipeline-written tier (1) does — fall through to a live fetch
        # rather than kill the whole corpus run on one bad file.
        try:
            synced_text, _meta = lrclib.read_lrc(flat_cache)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"  ! unreadable flat LRCLIB cache {flat_cache}: {exc}", file=sys.stderr)
        else:
            return lrclib.cue_spans_for_lines(synced_text, lines)

    genius = bundle["lyrics"].get("genius")
    if not genius:
        return None
    records = lrclib.search(genius["title"], genius["artist"])
    record = lrclib.select_candidate(records, lines, bundle.get("media_duration_s"))
    if record is None or not record.get("syncedLyrics"):
        return None
    return lrclib.cue_spans_for_lines(record["syncedLyrics"], lines)


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
    sources = selected_sources(line_objects, n_lines)
    anchors, _suspects, _ratios = analyze_pass1(
        align_lines,
        line_objects,
        {"selected_source": sources},
        transcribe_words,
        margin_s=knobs["margin_s"],
        max_edit_ratio=knobs["max_edit_ratio"],
    )
    return offset_mad_against_cues(anchors, lrclib_cues)


def _replay_spans(
    bundle: dict, ytasr_words: list[dict] | None, alpha: float, beta: float
) -> tuple[list, list] | None:
    """Captured re-align spans re-matched at the *swept* alpha/beta.

    Now a 3-source sub-match (ytasr threaded in), so a replay must be redone
    per ``(alpha, beta)`` pair — the old "one replay per alpha serves the
    whole beta row" caching is dead now that beta reaches the sub-match.
    Replays are CPU-cheap; nothing replaces the caching. Returns
    ``(spans, results)`` for ``merge_spans``, or ``None`` when the bundle
    recorded no spans.
    """
    spans = (bundle["joint_stats"].get("windowed_realign") or {}).get("spans")
    if not spans:
        return None
    knobs = bundle["joint_stats"]["knobs"]
    results = []
    for span in spans:
        span_words = span.get("align_words")
        if span_words is None:
            results.append(None)
            continue
        results.append(
            replay_span(
                span,
                span_words,
                bundle["transcribe_words"],
                bundle["lyrics"]["lines"],
                bundle["lyrics"]["align_lines"],
                alpha=alpha,
                margin_s=knobs["margin_s"],
                max_edit_ratio=knobs["max_edit_ratio"],
                beta=beta,
                ytasr_words=ytasr_words,
            )
        )
    return spans, results


def _replay_output(
    bundle: dict,
    ytasr_words: list[dict] | None,
    alpha: float,
    beta: float,
    realign: tuple[list, list] | None,
) -> tuple[list[dict], dict]:
    """3-source (or 2-source fallback) DP + windowed re-align merge.

    ``realign`` is this ``(alpha, beta)``'s ``_replay_spans`` output. Returns
    ``(line_objects, joint_stats)`` — stats expose ``n_ytasr_candidates`` so
    the caller can tell a real 3-source run from one where the candidate scan
    matched nothing. Mirrors the stage: pass-1 corroboration ratios (from
    ``analyze_pass1``) protect well-corroborated interior lines in the merge.
    """
    transcribe_words = bundle["transcribe_words"]
    lines = bundle["lyrics"]["lines"]
    align_lines = bundle["lyrics"]["align_lines"]
    knobs = bundle["joint_stats"]["knobs"]

    line_objects, stats = match_words_to_lines_joint_with_stats(
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
    if realign is not None:
        spans, results = realign
        _anchors, _suspects, ratios = analyze_pass1(
            align_lines,
            line_objects,
            stats,
            transcribe_words,
            margin_s=knobs["margin_s"],
            max_edit_ratio=knobs["max_edit_ratio"],
        )
        line_objects = merge_spans(
            line_objects, spans, results, len(lines), bundle["words"], pass1_ratios=ratios
        )
    return line_objects, stats


def _fmt_mad(mad: dict) -> str:
    if mad.get("bailed"):
        return f"bail:{mad['bailed']}"
    return f"{mad['mad_s']:.2f}s/{mad['n_anchors_fit']}a"


def _write_ass_variant(
    bundle_path: Path, song_root: Path, line_objects: list[dict], tag: str
) -> Path:
    """Render ``line_objects`` to ``karaoke/<stem>.<tag>.ass`` for eyeballing.

    Reuses ``LyricAlignStage._generate_ass`` unchanged. Tagged alongside the
    shipped ``<stem>.ass`` — never overwrites it, so nothing needs backing up.
    """
    stage = LyricAlignStage(whisper_worker=None, config=PipelineConfig())
    ass = stage._generate_ass(line_objects)
    out = song_root / "karaoke" / f"{bundle_path.stem}.{tag}.ass"
    out.parent.mkdir(exist_ok=True)
    out.write_text(ass, encoding="utf-8")
    return out


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
        type=str,
        default=",".join(str(a) for a in DEFAULT_ALPHA_GRID),
        help="comma-separated alpha sweep grid",
    )
    ap.add_argument(
        "--write-ass",
        action="store_true",
        help=f"write each song's best-combo karaoke/<stem>.{ASS_TAG}.ass for eyeballing",
    )
    ap.add_argument(
        "--min-coverage",
        type=float,
        default=0.85,
        help="flag (with '!') songs whose best-combo placed/n_lines falls below this",
    )
    args = ap.parse_args()

    beta_grid = [float(b) for b in args.beta.split(",")]
    alpha_grid = [float(a) for a in args.alpha.split(",")]
    debug_dir = args.path / "alignment_debug" if args.path.name != "alignment_debug" else args.path
    bundle_paths = sorted(debug_dir.glob("*.json"))
    if not bundle_paths:
        print(f"No bundles found under {args.path}", file=sys.stderr)
        return 1

    print(
        f"{'song':46s} {'src':>4s} {'mad(best)':>16s} {'alpha':>5s} {'beta':>5s} "
        f"{'crawl(rec>new)':>14s} {'overlap(rec>new)':>18s} {'placed(rec>new)':>16s} "
        f"{'coverage':>10s}"
    )
    print("-" * 142)

    for bp in bundle_paths:
        bundle = json.loads(bp.read_text(encoding="utf-8"))
        if bundle.get("ground_truth_refs", {}).get("youtube_srt_present"):
            continue  # SRT-sourced songs run the cue path, out of scope here.

        song_root = bp.parent.parent
        knobs = bundle["joint_stats"]["knobs"]
        transcribe_words = bundle["transcribe_words"]
        align_lines = bundle["lyrics"]["align_lines"]
        n_lines = len(bundle["lyrics"]["lines"])

        ytasr_words = _load_ytasr_words(bundle, song_root)
        lrclib_cues = _load_lrclib_reference(bundle, song_root, bp.stem)
        rec = recorded_summary(bundle)

        beta_sweep = beta_grid if ytasr_words else [0.0]  # beta is a no-op with no ytasr data
        per_combo = {}
        for alpha in alpha_grid:
            for beta in beta_sweep:
                realign = _replay_spans(bundle, ytasr_words, alpha, beta)
                objs, stats = _replay_output(bundle, ytasr_words, alpha, beta, realign)
                per_combo[(alpha, beta)] = {
                    "objs": objs,
                    "stats": stats,
                    "summary": summarize(objs),
                    "mad": _score_against_lrclib(
                        objs, transcribe_words, align_lines, knobs, lrclib_cues
                    ),
                }
                if stats["n_ytasr_candidates"] == 0 and len(beta_sweep) > 1:
                    # ytasr passed its usability gate but the candidate scan
                    # matched nothing (candidate counts don't depend on
                    # alpha/beta): beta is a no-op for this song, stop sweeping.
                    beta_sweep = [beta]
                    break

        best_alpha, best_beta = min(
            per_combo,
            key=lambda c: (
                per_combo[c]["summary"]["n_crawl"],
                per_combo[c]["mad"].get("mad_s", float("inf")),
            ),
        )
        best = per_combo[(best_alpha, best_beta)]
        if not ytasr_words:
            src_flag, beta_col = "2src", "n/a"
        elif best["stats"]["n_ytasr_candidates"] == 0:
            # A gate-passing ASR track whose text matched no line: the output
            # is effectively 2-source, so don't attribute a winning beta.
            src_flag, beta_col = "asr0", "n/a"
        else:
            src_flag, beta_col = "3src", f"{best_beta:.1f}"
        coverage = best["summary"]["n_placed"] / n_lines if n_lines else 1.0
        coverage_flag = "!" if coverage < args.min_coverage else ""
        coverage_col = f"{best['summary']['n_placed']}/{n_lines}{coverage_flag}"
        # E1 gated fills are excluded from `rec` (see recorded_summary); note
        # it on the row so a dropped fill count is visible, not silent.
        fill_note = f" fills_excluded={rec['n_excluded_fills']}" if rec["n_excluded_fills"] else ""
        print(
            f"{bp.stem[:46]:46s} {src_flag:>4s} {_fmt_mad(best['mad']):>16s} "
            f"{best_alpha:>5.1f} {beta_col:>5s} "
            f"{rec['n_crawl']:6d}->{best['summary']['n_crawl']:<6d} "
            f"{rec['max_overlap']:8.1f}->{best['summary']['max_overlap']:<8.1f} "
            f"{rec['n_placed']:6d}->{best['summary']['n_placed']:<6d} "
            f"{coverage_col:>10s}{fill_note}"
        )

        if args.write_ass:
            out = _write_ass_variant(bp, song_root, best["objs"], ASS_TAG)
            print(f"  -> wrote {out} (alpha={best_alpha:.1f}, beta={best_beta:.1f})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
