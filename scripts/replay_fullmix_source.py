#!/usr/bin/env python3
"""Sweep the full-mix transcribe as an extra joint-DP source (Experiment A).

Replays each non-SRT bundle several ways and scores them against a held-out
LRCLIB reference that is fetched for comparison only, never fed to a matcher:

  * **baseline** — the shipped 3-source route (align + transcribe + YTASR) +
    windowed re-align. Reuses ``replay_alignment_from_bundle.replay_bundle``.
  * **M2 (fourth source)** — the mix transcribe words (bundle field
    ``mix_transcribe_words``, captured under ``capture_mix_transcribe``) added as
    a genuine fourth candidate source with weight ``gamma``, swept over a grid
    with alpha/beta pinned at the shipped defaults. Runs whether or not the song
    has YTASR.
  * **M1 (ytasr-slot substitute)** — only for songs with *no* YTASR: the mix
    words are dropped into the existing YTASR slot (zero matcher change), beta
    swept. Measures the effect of a third source where one is currently absent.

Scoring: for each scheme's output, ``windowed_realign.analyze_pass1`` finds the
lines it placed with genuine matcher-level confidence — align/transcribe/ytasr
anchors only, so mix-won lines are excluded and the comparison stays
non-circular — then ``srt_cues.offset_mad_against_cues`` reports the MAD of those
placements against the held-out LRCLIB reference. Crawl-line count and max
inter-line overlap are the structural secondary metrics.

Held-out LRCLIB is read from the flat per-song cache ``<PATH>/lrclib/<stem>``
when present, else fetched fresh via the LRCLIB search API using the bundle's own
Genius title/artist (see scripts/_lrclib_ref.py). A song with no reference is
scored on the structural metrics alone (MAD shows ``bail:no_reference``).

``--write-ass`` renders each song's best combo to ``karaoke/<stem>.fullmix.ass``
for eyeballing, alongside the shipped ``<stem>.ass`` — never overwriting it.

Run from the repo root::

    python scripts/replay_fullmix_source.py PATH [--gamma 0.5,1,1.5,2,3]
        [--beta 0.5,1,1.5,2,3] [--mix-edit-ratio 0.34] [--write-ass]

``PATH`` is a song-library folder (scans ``<PATH>/alignment_debug/*.json``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# scripts/ is already on sys.path (Python prepends a run script's own dir), so
# the sibling base harness imports by name; add repo root for pikaraoke.*.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _lrclib_ref as lrclib  # noqa: E402
import replay_alignment_from_bundle as base  # noqa: E402

from pikaraoke.lib.joint_match import (  # noqa: E402
    match_words_to_lines_joint_with_stats,
)
from pikaraoke.lib.srt_cues import offset_mad_against_cues  # noqa: E402
from pikaraoke.lib.token_align import _normalize_token  # noqa: E402
from pikaraoke.lib.windowed_realign import analyze_pass1  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage  # noqa: E402

DEFAULT_GAMMA_GRID = (0.5, 1.0, 1.5, 2.0, 3.0)
DEFAULT_BETA_GRID = (0.5, 1.0, 1.5, 2.0, 3.0)
# Mix candidate generation defaults to ytasr's strict ratio — the mix ASR text
# is a mix candidate's only evidence for existing (see joint_match / ytasr).
DEFAULT_MIX_EDIT_RATIO = 0.34

ASS_TAG = "fullmix"


def _load_mix_words(bundle: dict) -> list[dict] | None:
    """The captured full-mix transcribe words, or ``None`` if absent."""
    mix = bundle.get("mix_transcribe_words")
    return mix or None


def _mix_as_ytasr(mix_words: list[dict]) -> list[dict]:
    """Mix words shaped for the YTASR slot (M1): add the ``norm`` key the
    matcher's ytasr path expects (plain whisper words don't carry one)."""
    return [{**w, "norm": _normalize_token(w["word"])} for w in mix_words]


def _load_lrclib_reference(
    bundle: dict, song_root: Path, stem: str
) -> dict[int, tuple[float, float]] | None:
    """Held-out LRCLIB cue spans for scoring only — never fed into a matcher.

    On this branch the bundle no longer records a ``.lrc`` (LRCLIB was dropped as
    a prior), so the tiers are: (1) a flat per-song cache at
    ``<song_root>/lrclib/<stem>`` (hand-provisioned outside this repo), else
    (2) a fresh live search keyed on the bundle's Genius title/artist. Returns
    ``None`` when neither yields a synced variant.
    """
    lines = bundle["lyrics"]["lines"]

    flat_cache = song_root / "lrclib" / stem
    if flat_cache.is_file():
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
    """Per-line source list for analyze_pass1's anchor classification."""
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
    """MAD of this scheme's own trusted anchors against the held-out LRCLIB cues.

    Anchors exclude mix-won lines (analyze_pass1 only trusts
    align/transcribe/ytasr), so the mix source is measured by how it moves the
    *other* lines, not by grading itself against the reference.
    """
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


def _scheme_output(
    bundle: dict,
    *,
    ytasr_words: list[dict] | None,
    mix_words: list[dict] | None,
    alpha: float,
    beta: float,
    gamma: float,
    mix_max_edit_ratio: float,
) -> tuple[list[dict], dict]:
    """Run one scheme's DP at the given knobs, then merge the captured re-align.

    The re-align spans replay at the bundle's recorded alpha (M2 pins alpha to
    that default), so ``base._replay_realign`` reproduces the shipped re-align
    over whichever pass-1 this scheme produced.
    """
    lines = bundle["lyrics"]["lines"]
    align_lines = bundle["lyrics"]["align_lines"]
    knobs = bundle["joint_stats"]["knobs"]
    transcribe_words = bundle["transcribe_words"]

    line_objects, stats = match_words_to_lines_joint_with_stats(
        bundle["words"],
        transcribe_words,
        lines,
        align_lines,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        margin_s=knobs["margin_s"],
        max_edit_ratio=knobs["max_edit_ratio"],
        mix_max_edit_ratio=mix_max_edit_ratio,
        lookahead=knobs["lookahead"],
        anchor_fallback=knobs["anchor_fallback"],
        ytasr_words=ytasr_words,
        mix_words=mix_words,
    )
    line_objects = base._replay_realign(bundle, line_objects, transcribe_words, lines, align_lines)
    return line_objects, stats


def _best_combo(combos: dict) -> tuple:
    """Pick the (label, knob) key with fewest crawl lines, then lowest MAD."""
    return min(
        combos,
        key=lambda k: (
            combos[k]["summary"]["n_crawl"],
            combos[k]["mad"].get("mad_s", float("inf")),
        ),
    )


def _fmt_mad(mad: dict) -> str:
    if mad.get("bailed"):
        return f"bail:{mad['bailed']}"
    return f"{mad['mad_s']:.2f}s/{mad['n_anchors_fit']}a"


def _write_ass_variant(bundle_stem: str, song_root: Path, line_objects: list[dict]) -> Path:
    """Render ``line_objects`` to ``karaoke/<stem>.fullmix.ass`` for eyeballing."""
    stage = LyricAlignStage(whisper_worker=None, config=PipelineConfig())
    ass = stage._generate_ass(line_objects)
    out = song_root / "karaoke" / f"{bundle_stem}.{ASS_TAG}.ass"
    out.parent.mkdir(exist_ok=True)
    out.write_text(ass, encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("path", type=Path, help="song-library folder (scans alignment_debug/*.json)")
    ap.add_argument(
        "--gamma",
        default=",".join(str(g) for g in DEFAULT_GAMMA_GRID),
        help="comma-separated gamma sweep grid (M2, mix as 4th source)",
    )
    ap.add_argument(
        "--beta",
        default=",".join(str(b) for b in DEFAULT_BETA_GRID),
        help="comma-separated beta sweep grid (M1, mix in the ytasr slot)",
    )
    ap.add_argument(
        "--mix-edit-ratio",
        type=float,
        default=DEFAULT_MIX_EDIT_RATIO,
        help="edit-distance gate for mix candidate generation (try 0.5 if starved)",
    )
    ap.add_argument(
        "--write-ass",
        action="store_true",
        help=f"write each song's best-combo karaoke/<stem>.{ASS_TAG}.ass for eyeballing",
    )
    args = ap.parse_args()

    gamma_grid = [float(g) for g in args.gamma.split(",")]
    beta_grid = [float(b) for b in args.beta.split(",")]
    debug_dir = args.path / "alignment_debug" if args.path.name != "alignment_debug" else args.path
    bundle_paths = sorted(debug_dir.glob("*.json"))
    if not bundle_paths:
        print(f"No bundles found under {args.path}", file=sys.stderr)
        return 1

    print(
        f"{'song':40s} {'flag':>4s} {'base_mad':>13s} {'M2_mad(gamma)':>18s} "
        f"{'M1_mad(beta)':>16s} {'crawl':>9s} {'overlap':>13s} {'mixwon':>6s}"
    )
    print("-" * 128)

    for bp in bundle_paths:
        bundle = json.loads(bp.read_text(encoding="utf-8"))
        # Skip by lyric source, not SRT presence: youtube_srt_present is true
        # for nearly every song (some SRT exists on disk); Experiment B owns
        # only the songs whose lyrics actually came from that SRT.
        if bundle.get("lyrics", {}).get("source_kind") == "srt":
            continue  # SRT-sourced songs are Experiment B, not A.

        song_root = bp.parent.parent
        knobs = bundle["joint_stats"]["knobs"]
        transcribe_words = bundle["transcribe_words"]
        align_lines = bundle["lyrics"]["align_lines"]
        alpha = knobs["alpha"]
        beta_shipped = knobs.get("beta", 2.0)

        ytasr_words = base.load_ytasr_words(bundle, song_root)
        mix_words = _load_mix_words(bundle)
        lrclib_cues = _load_lrclib_reference(bundle, song_root, bp.stem)

        base_objs = base.replay_bundle(bundle, realign=True, ytasr_words=ytasr_words)
        base_summary = base.summarize(base_objs)
        base_mad = _score_against_lrclib(
            base_objs, transcribe_words, align_lines, knobs, lrclib_cues
        )

        flag = ("y" if ytasr_words else "") + ("m" if mix_words else "") or "-"
        if not mix_words:
            print(
                f"{bp.stem[:40]:40s} {flag:>4s} {_fmt_mad(base_mad):>13s} "
                f"{'(no mix)':>18s} {'n/a':>16s} "
                f"{base_summary['n_crawl']:>9d} {base_summary['max_overlap']:>12.1f}s {'0':>6s}"
            )
            continue

        # M2: mix as a genuine fourth source, alpha/beta pinned to shipped.
        m2 = {}
        for gamma in gamma_grid:
            objs, stats = _scheme_output(
                bundle,
                ytasr_words=ytasr_words,
                mix_words=mix_words,
                alpha=alpha,
                beta=beta_shipped,
                gamma=gamma,
                mix_max_edit_ratio=args.mix_edit_ratio,
            )
            m2[gamma] = {
                "objs": objs,
                "stats": stats,
                "summary": base.summarize(objs),
                "mad": _score_against_lrclib(
                    objs, transcribe_words, align_lines, knobs, lrclib_cues
                ),
            }
        best_gamma = _best_combo(m2)
        best_m2 = m2[best_gamma]

        # M1: mix in the ytasr slot — only meaningful when the song has no ytasr.
        best_m1_col = "n/a"
        if not ytasr_words:
            mix_slot = _mix_as_ytasr(mix_words)
            m1 = {}
            for beta in beta_grid:
                objs, _stats = _scheme_output(
                    bundle,
                    ytasr_words=mix_slot,
                    mix_words=None,
                    alpha=alpha,
                    beta=beta,
                    gamma=0.0,
                    mix_max_edit_ratio=args.mix_edit_ratio,
                )
                m1[beta] = {
                    "summary": base.summarize(objs),
                    "mad": _score_against_lrclib(
                        objs, transcribe_words, align_lines, knobs, lrclib_cues
                    ),
                }
            best_beta = _best_combo(m1)
            best_m1_col = f"{_fmt_mad(m1[best_beta]['mad'])}({best_beta:.1f})"

        print(
            f"{bp.stem[:40]:40s} {flag:>4s} {_fmt_mad(base_mad):>13s} "
            f"{_fmt_mad(best_m2['mad']) + f'({best_gamma:.1f})':>18s} {best_m1_col:>16s} "
            f"{base_summary['n_crawl']:d}->{best_m2['summary']['n_crawl']:<d}    "
            f"{base_summary['max_overlap']:5.1f}->{best_m2['summary']['max_overlap']:<5.1f}s "
            f"{best_m2['stats']['mix_won']:>6d}"
        )

        if args.write_ass:
            out = _write_ass_variant(bp.stem, song_root, best_m2["objs"])
            print(f"  -> wrote {out} (gamma={best_gamma:.1f})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
