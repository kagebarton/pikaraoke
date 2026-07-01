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
    candidate source, plus the captured re-align spans re-matched at the
    swept alpha, no prior applied at all. Songs with no usable YTASR track
    fall back to the plain 2-source DP — an expected, flagged outcome, not
    an error.

Scoring: for each scheme's output, ``windowed_realign.analyze_pass1`` finds
the lines it placed with genuine matcher-level (not prior-patched) confidence
— excluding prior-touched lines keeps the comparison non-circular for the
5 songs whose *old*-scheme prior source is LRCLIB itself — then
``srt_prior.offset_mad_against_cues`` reports the median offset and MAD of
those placements against the held-out LRCLIB reference.

Held-out LRCLIB is read from each song's cached ``.lrc`` when the bundle
already has one (reused, not re-fetched, so scoring calibrates against the
same variant the original prior did — only true for the songs where LRCLIB
*was* the production prior); else a flat per-song cache at
``<PATH>/lrclib/<stem>`` when one exists (covers most of the ytasr-prior
songs, whose prior fetch short-circuits before ever trying LRCLIB, so they'd
otherwise always hit a live, non-reproducible fetch); otherwise fetched fresh
via the LRCLIB search API using the bundle's own Genius title/artist.

Run from the repo root::

    python scripts/replay_ytasr_third_source.py PATH [--beta 0.5,1,1.5,2,3] [--alpha 0.5,1,1.5,2,3] [--write-ass]

Both ``--beta`` and ``--alpha`` are swept as a grid; the best-scoring
``(alpha, beta)`` combination per song is reported (fewest crawl lines, then
lowest MAD, breaking ties). ``alpha`` still has an effect even for songs with
no usable YTASR track (it weights align agreement, independent of beta), so
it is swept for every song; ``beta`` is fixed at 0.0 (a no-op) for those.

``--write-ass`` renders each song's winning combo to
``karaoke/<stem>.ytasr3src.ass`` for visual inspection, alongside the
folder's existing ``.asralign``/``.jointalign`` variants — never overwriting
the shipped ``<stem>.ass``.

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
from pikaraoke.lib.windowed_realign import (  # noqa: E402
    analyze_pass1,
    merge_spans,
    replay_span,
)
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage  # noqa: E402

DEFAULT_BETA_GRID = (0.5, 1.0, 1.5, 2.0, 3.0)
DEFAULT_ALPHA_GRID = (0.5, 1.0, 1.5, 2.0, 3.0)

# Tag stamped on --write-ass output filenames, matching the karaoke/ folder's
# existing <stem>.asralign.ass / <stem>.jointalign.ass side-by-side convention.
ASS_TAG = "ytasr3src"


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

    Preference order: (1) the bundle's own cached ``.lrc`` — only present
    when LRCLIB was the production prior, so this is the same variant that
    prior calibrated against; (2) a flat per-song cache at
    ``<song_root>/lrclib/<stem>`` (pre-fetched outside this repo's pipeline;
    covers most ytasr-prior songs, which never populate (1) since the prior
    fetch short-circuits once ytasr succeeds); (3) a fresh live search.
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


def _replay_spans_at_alpha(bundle: dict, alpha: float) -> tuple[list, list] | None:
    """Captured re-align spans re-matched at the *swept* alpha.

    ``old_harness._replay_realign`` runs its sub-matches at the bundle's
    recorded alpha, which would overwrite the swept lines and make the
    sweep's own metrics partially insensitive to alpha. The sub-matches are
    2-source (beta never enters), so one replay per alpha serves the whole
    beta row. Returns ``(spans, results)`` for ``merge_spans``, or ``None``
    when the bundle recorded no spans.
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
            )
        )
    return spans, results


def _new_scheme_output(
    bundle: dict,
    ytasr_words: list[dict] | None,
    alpha: float,
    beta: float,
    realign: tuple[list, list] | None,
) -> tuple[list[dict], dict]:
    """3-source (or 2-source fallback) DP + windowed re-align merge, no prior.

    ``realign`` is this alpha's ``_replay_spans_at_alpha`` output. Returns
    ``(line_objects, joint_stats)`` — stats expose ``n_ytasr_candidates`` so
    the caller can tell a real 3-source run from one where the candidate
    scan matched nothing.
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
        line_objects = merge_spans(line_objects, spans, results, len(lines), bundle["words"])
    return line_objects, stats


def _fmt_mad(mad: dict) -> str:
    if mad.get("bailed"):
        return f"bail:{mad['bailed']}"
    return f"{mad['mad_s']:.2f}s/{mad['n_anchors_fit']}a"


def _write_ass_variant(
    bundle_path: Path, song_root: Path, line_objects: list[dict], tag: str
) -> Path:
    """Render ``line_objects`` to ``karaoke/<stem>.<tag>.ass`` for eyeballing.

    Reuses ``LyricAlignStage._generate_ass`` unchanged (same renderer
    production and ``replay_alignment_from_bundle --write`` use). Tagged
    alongside the shipped ``<stem>.ass``, matching the folder's existing
    ``.asralign``/``.jointalign`` side-by-side variants — never overwrites
    the shipped file itself, so nothing here needs backing up.
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
    args = ap.parse_args()

    beta_grid = [float(b) for b in args.beta.split(",")]
    alpha_grid = [float(a) for a in args.alpha.split(",")]
    debug_dir = args.path / "alignment_debug" if args.path.name != "alignment_debug" else args.path
    bundle_paths = sorted(debug_dir.glob("*.json"))
    if not bundle_paths:
        print(f"No bundles found under {args.path}", file=sys.stderr)
        return 1

    print(
        f"{'song':46s} {'src':>4s} {'old_mad':>14s} {'new_mad(best)':>20s} "
        f"{'alpha':>5s} {'beta':>5s} {'crawl':>11s} {'overlap':>13s}"
    )
    print("-" * 126)

    for bp in bundle_paths:
        bundle = json.loads(bp.read_text(encoding="utf-8"))
        if bundle.get("ground_truth_refs", {}).get("youtube_srt_present"):
            continue  # SRT-sourced songs are out of scope for this experiment.

        song_root = bp.parent.parent
        knobs = bundle["joint_stats"]["knobs"]
        transcribe_words = bundle["transcribe_words"]
        align_lines = bundle["lyrics"]["align_lines"]

        ytasr_words = _load_ytasr_words(bundle, song_root)
        lrclib_cues = _load_lrclib_reference(bundle, song_root, bp.stem)

        old_objs = old_harness.replay_bundle(bundle, realign=True)
        old_summary = old_harness.summarize(old_objs)
        old_mad = _score_against_lrclib(old_objs, transcribe_words, align_lines, knobs, lrclib_cues)

        beta_sweep = beta_grid if ytasr_words else [0.0]  # beta is a no-op with no ytasr data
        per_combo = {}
        for alpha in alpha_grid:
            realign = _replay_spans_at_alpha(bundle, alpha)
            for beta in beta_sweep:
                new_objs, new_stats = _new_scheme_output(bundle, ytasr_words, alpha, beta, realign)
                per_combo[(alpha, beta)] = {
                    "objs": new_objs,
                    "stats": new_stats,
                    "summary": old_harness.summarize(new_objs),
                    "mad": _score_against_lrclib(
                        new_objs, transcribe_words, align_lines, knobs, lrclib_cues
                    ),
                }
                if new_stats["n_ytasr_candidates"] == 0 and len(beta_sweep) > 1:
                    # ytasr passed its usability gate but the candidate scan
                    # matched nothing (candidate counts don't depend on
                    # alpha/beta): beta is a no-op for this song, stop
                    # sweeping it.
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
        print(
            f"{bp.stem[:46]:46s} {src_flag:>4s} {_fmt_mad(old_mad):>14s} "
            f"{_fmt_mad(best['mad']):>20s} {best_alpha:>5.1f} {beta_col:>5s} "
            f"{old_summary['n_crawl']:2d}->{best['summary']['n_crawl']:<2d}      "
            f"{old_summary['max_overlap']:5.1f}->{best['summary']['max_overlap']:<5.1f}s"
        )

        if args.write_ass:
            out = _write_ass_variant(bp, song_root, best["objs"], ASS_TAG)
            print(f"  -> wrote {out} (alpha={best_alpha:.1f}, beta={best_beta:.1f})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
