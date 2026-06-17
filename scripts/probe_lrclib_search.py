#!/usr/bin/env python3
"""Step-1 search-quality probe for plans/lrclib-timing-prior.md.

Measures, offline against the 24 hand-fetched files in ``<folder>/lrclib/``
(the ground truth), whether an automatic LRCLIB search can find a synced
variant whose *timing* matches the hand-vetted reference, and whether the
mapping-rate gate can pick that variant out of the result set.

For each ground-truth song it queries the LRCLIB API (``GET /api/search``)
with the canonical Genius title/artist captured by
``scripts/capture_lrclib_keys.py`` (SRT-sourced songs fall back to a
cleaned title query), then for every synced candidate computes two
numbers the production design hinges on:

  * **mapping rate** — ``map_lines_to_cues`` of the candidate's synced
    lines against our actual lyric sheet (bundle ``lyrics.lines``). This
    is the gate that *selects* a variant; the probe ranks by it.
  * **timing agreement vs the reference** — map the candidate to the
    hand-fetched file, fit offset+drift (LRCLIB clocks differ from the
    video master), and take the residual MAD. A candidate is a "timing
    match" if ``>= MATCH_MIN_LINES`` lines map with MAD ``<= MATCH_MAD_S``.

The hand-fetched reference is the best *video-matching* sync, which for an
edited video (an awards cut that drops verses, a movie clip with dialogue)
is sometimes a hard-won variant a real user wouldn't find — while
auto-search returns the common album version. So the report keeps the two
questions separate and classifies each song:

  * **HIT** — a returned variant matches the video reference's timing.
  * **SAFE-SKIP** — search found the right *song* (mapping rate clears the
    floor) but no variant matches this video's timing; the anchor-MAD gate
    bails at match time and the prior no-ops, so this is safe, not a miss.
  * **SEARCH-MISS** — no usable synced variant of the right song.

Duration is recorded as a *diagnostic only*, not a ranking key: several
corpus songs are movie clips whose video length (ffprobe) does not match
the soundtrack master (extra dialogue, intros), so duration-closeness
would mislead exactly the hard cases. The report quantifies how often a
duration rank would have agreed with the timing match anyway.

Run from the repo root (use the project's interpreter)::

    python scripts/probe_lrclib_search.py [--folder PATH] [--refresh] [--json OUT]
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

import requests

# Allow running as ``python scripts/probe_lrclib_search.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.alignment_eval import (  # noqa: E402
    _fit_offset_and_drift,
    map_lines_to_cues,
    parse_lrc_lines,
)
from scripts.capture_lrclib_keys import (  # noqa: E402
    KEYS_FILENAME,
    default_query,
    load_keys,
)

DEFAULT_FOLDER = "/home/ken/pikaraoke-songs"
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".webm", ".mov"}
USER_AGENT = "pikaraoke-lrclib-probe/0.1 (https://github.com/vicwomg/pikaraoke)"
SEARCH_URL = "https://lrclib.net/api/search"

# A candidate's sync is "equivalent" to the hand-vetted reference when this
# many lines map and the offset+drift residual spread stays tight. Mirrors
# the SRT prior's anchor-MAD vetting (>=4 anchors); MAD floor a touch under
# its 0.75 s since LRCLIB drift is fitted out here, not just offset.
MATCH_MIN_LINES = 4
MATCH_MAD_S = 0.5

# Mapping rate above which a returned variant is the right *song* (even if
# its timing doesn't match this particular video). Provisional; the lowest
# per-song matching variant maps ~38% (the Selfish 30/79 case). Separates
# "right song, wrong-for-this-video timing" (a safe gate bail) from "search
# returned the wrong song entirely".
RIGHT_SONG_FLOOR = 0.35


@dataclass
class Candidate:
    track: str
    artist: str
    album: str
    duration: float
    map_n: int  # sheet lines that mapped to this candidate
    map_den: int  # sheet lines total
    match_n: int  # lines mapped to the reference for timing
    mad_s: float  # residual MAD after offset+drift fit (vs reference)
    is_match: bool

    @property
    def map_rate(self) -> float:
        return self.map_n / self.map_den if self.map_den else 0.0


@dataclass
class SongProbe:
    song: str
    key_kind: str  # "genius" | "title"
    query: str
    video_dur: float | None
    n_candidates: int
    n_synced: int
    note: str = ""
    found: bool = False  # any synced candidate is a timing match
    gate_correct: bool = False  # top-mapping candidate is a timing match
    sel: Candidate | None = None  # the gate's pick (highest mapping rate)
    match_rates: list[float] = field(default_factory=list)  # map rate of matching cands
    nonmatch_rates: list[float] = field(default_factory=list)  # map rate of non-matching cands
    rank_by_dur: int | None = None  # rank of first match when synced sorted by |dur-video|


# ---------------------------------------------------------------------------
# Data resolution
# ---------------------------------------------------------------------------


def find_media(stem: str, folder: Path) -> Path | None:
    for ext in VIDEO_EXTS:
        cand = folder / f"{stem}{ext}"
        if cand.is_file():
            return cand
    return None


def ffprobe_duration(media: Path) -> float | None:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(media),
            ],
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        return float(out.strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def lyric_sheet(stem: str, debug_dir: Path) -> list[str] | None:
    """Our actual lyric sheet for the song: the bundle's ``lyrics.lines``."""
    cand = debug_dir / f"{stem}.json"
    if not cand.is_file():
        return None
    try:
        bundle = json.loads(cand.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    lines = bundle.get("lyrics", {}).get("lines")
    return lines or None


# ---------------------------------------------------------------------------
# LRCLIB search (cached)
# ---------------------------------------------------------------------------


def lrclib_search(params: dict, cache_dir: Path, refresh: bool) -> list[dict]:
    """``GET /api/search`` with the given params; cache the raw response.

    Cached by a hash of the params so re-runs are offline and don't
    re-hit the API. Returns [] on any network/parse failure.
    """
    key = hashlib.sha1(urllib.parse.urlencode(sorted(params.items())).encode()).hexdigest()[:16]
    cache_file = cache_dir / f"{key}.json"
    if cache_file.is_file() and not refresh:
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    try:
        resp = requests.get(
            SEARCH_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  ! search failed for {params}: {e}")
        return []
    time.sleep(0.3)  # be polite to the public API
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def timing_agreement(
    ref_texts: list[str], ref_starts: list[float], cand_texts: list[str], cand_starts: list[float]
) -> tuple[int, float]:
    """(lines matched, residual MAD) of a candidate's sync vs the reference.

    Maps reference lines to candidate lines by text, fits offset+drift on
    the matched deltas (LRCLIB clocks come from different masters), and
    returns the median absolute residual. A structural edit (inserted
    dialogue, dropped verse) leaves residuals that the robust fit won't
    absorb, so the MAD stays high — exactly the signal we want.
    """
    mapping = map_lines_to_cues(ref_texts, cand_texts)
    if len(mapping) < 2:
        return len(mapping), float("inf")
    ref_t = [ref_starts[r] for r in mapping]
    deltas = [cand_starts[c] - ref_starts[r] for r, c in mapping.items()]
    offset, drift = _fit_offset_and_drift(ref_t, deltas)
    residuals = [abs(d - (offset + drift * t)) for t, d in zip(ref_t, deltas)]
    return len(mapping), median(residuals)


def probe_song(
    stem: str,
    params: dict,
    key_kind: str,
    sheet: list[str] | None,
    ref_texts: list[str],
    ref_starts: list[float],
    video_dur: float | None,
    cache_dir: Path,
    refresh: bool,
) -> SongProbe:
    records = lrclib_search(params, cache_dir, refresh)
    synced = [r for r in records if r.get("syncedLyrics")]
    query = params.get("q") or f"{params.get('track_name','')} / {params.get('artist_name','')}"
    probe = SongProbe(
        song=stem,
        key_kind=key_kind,
        query=query,
        video_dur=video_dur,
        n_candidates=len(records),
        n_synced=len(synced),
    )
    if not synced:
        probe.note = "no synced candidates"
        return probe
    if sheet is None:
        probe.note = "no lyric sheet (bundle missing); recall/timing only"

    cands: list[Candidate] = []
    for r in synced:
        cand_texts, cand_starts = parse_lrc_lines(r["syncedLyrics"])
        if not cand_texts:
            continue
        if sheet is not None:
            map_n = len(map_lines_to_cues(sheet, cand_texts))
            map_den = len(sheet)
        else:
            map_n = map_den = 0
        match_n, mad = timing_agreement(ref_texts, ref_starts, cand_texts, cand_starts)
        cands.append(
            Candidate(
                track=r.get("trackName", ""),
                artist=r.get("artistName", ""),
                album=r.get("albumName", "") or "",
                duration=float(r.get("duration") or 0.0),
                map_n=map_n,
                map_den=map_den,
                match_n=match_n,
                mad_s=mad,
                is_match=(match_n >= MATCH_MIN_LINES and mad <= MATCH_MAD_S),
            )
        )
    if not cands:
        probe.note = "synced candidates unparseable"
        return probe

    probe.found = any(c.is_match for c in cands)
    # Rate distributions feed the gate-threshold measurement; a song with no
    # lyric sheet (map_den == 0) has no real rate, so keep it out of them.
    probe.match_rates = [c.map_rate for c in cands if c.is_match and c.map_den]
    probe.nonmatch_rates = [c.map_rate for c in cands if not c.is_match and c.map_den]
    # Gate's pick: highest mapping rate, tie-broken by tighter timing.
    probe.sel = max(cands, key=lambda c: (c.map_rate, -c.mad_s))
    probe.gate_correct = probe.sel.is_match
    if video_dur is not None:
        by_dur = sorted(cands, key=lambda c: abs(c.duration - video_dur))
        for i, c in enumerate(by_dur, 1):
            if c.is_match:
                probe.rank_by_dur = i
                break
    return probe


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(probes: list[SongProbe]) -> dict:
    header = (
        f"{'song':<46}{'key':>7}{'cand':>5}{'syn':>4}{'found':>6}"
        f"{'gate':>5}{'sel.map':>9}{'sel.mad':>8}{'durΔ':>7}{'rnk':>4}"
    )
    print(header)
    print("-" * len(header))
    for p in sorted(probes, key=lambda x: (x.key_kind, x.song)):
        if p.sel is not None:
            sel_map = f"{p.sel.map_n}/{p.sel.map_den}"
            sel_mad = "inf" if p.sel.mad_s == float("inf") else f"{p.sel.mad_s:.2f}s"
            dur_delta = (
                f"{p.sel.duration - p.video_dur:+.0f}s"
                if p.video_dur is not None
                else f"{p.sel.duration:.0f}s"
            )
        else:
            sel_map = sel_mad = dur_delta = "-"
        print(
            f"{p.song[:46]:<46}{p.key_kind[:7]:>7}{p.n_candidates:>5}{p.n_synced:>4}"
            f"{('Y' if p.found else 'n'):>6}{('Y' if p.gate_correct else 'n'):>5}"
            f"{sel_map:>9}{sel_mad:>8}{dur_delta:>7}{(p.rank_by_dur or '-'):>4}"
        )
        if p.note:
            print(f"{'':>46}  ({p.note})")

    print("-" * len(header))
    # The hand-fetched reference is the best *video-matching* sync (sometimes
    # a hard-won edit a real user wouldn't find); auto-search instead returns
    # the common album version. So split the two independent questions the
    # production design separates: did search find the right *song* (mapping
    # rate vs our sheet), and does a returned variant match *this video's*
    # timing (MAD vs the reference). Right-song / no-timing-match is a SAFE
    # skip: the anchor-MAD gate bails at match time and the prior no-ops.
    hits = [p for p in probes if p.found]
    safe_skip = [
        p
        for p in probes
        if not p.found and p.sel and p.sel.map_den and p.sel.map_rate >= RIGHT_SONG_FLOOR
    ]
    misses = [p for p in probes if not p.found and p not in safe_skip]
    print(f"songs probed: {len(probes)}")
    print(f"  HIT         (variant matches the video reference): {len(hits)}")
    print(f"  SAFE-SKIP   (right song, no video-timing match -> gate bails): {len(safe_skip)}")
    for p in safe_skip:
        print(f"                - {p.song[:48]}  map={p.sel.map_rate:.0%} mad={p.sel.mad_s:.1f}s")
    print(f"  SEARCH-MISS (no usable synced variant of the right song): {len(misses)}")
    for p in misses:
        why = p.note or (f"best map {p.sel.map_rate:.0%}" if p.sel else "no candidates")
        print(f"                - {p.song[:48]}  ({why})")

    correct_rates = sorted(r for p in probes for r in p.match_rates)
    junk_rates = sorted(r for p in probes for r in p.nonmatch_rates)
    if correct_rates:
        print(
            f"\nmapping-rate floor: MATCHING variants min={correct_rates[0]:.0%} "
            f"med={correct_rates[len(correct_rates)//2]:.0%}  |  same-song NON-matching "
            f"max={junk_rates[-1]:.0%} (n={len(junk_rates)})"
        )
        print(
            "  -> mapping rate finds the right song but not the right timing; "
            "anchor-MAD is the timing gate"
        )
    dur_rank1 = [p for p in hits if p.rank_by_dur == 1]
    if hits:
        print(
            f"duration diagnostic: video-closest synced cand IS the match for {len(dur_rank1)}/{len(hits)} hits"
        )
    return {
        "songs_probed": len(probes),
        "hit": len(hits),
        "safe_skip": len(safe_skip),
        "search_miss": len(misses),
        "search_miss_songs": [p.song for p in misses],
        "match_rate_min": correct_rates[0] if correct_rates else None,
        "junk_rate_max": junk_rates[-1] if junk_rates else None,
        "dur_rank1": f"{len(dur_rank1)}/{len(hits)}" if hits else "0/0",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--folder", default=DEFAULT_FOLDER, help="song library folder")
    p.add_argument("--refresh", action="store_true", help="re-hit the API, ignoring the cache")
    p.add_argument("--songs", default=None, help="substring filter on song stem")
    p.add_argument("--json", dest="json_out", default=None, help="write results JSON here")
    args = p.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    lrc_dir = folder / "lrclib"
    debug_dir = folder / "alignment_debug"
    if not lrc_dir.is_dir():
        print(f"No LRCLIB reference dir: {lrc_dir}", file=sys.stderr)
        return 2

    keys = load_keys(lrc_dir / KEYS_FILENAME)
    cache_dir = lrc_dir / "probe_cache"

    ground_truth = sorted(
        f.name for f in lrc_dir.iterdir() if f.is_file() and f.name != KEYS_FILENAME
    )
    probes: list[SongProbe] = []
    for stem in ground_truth:
        if args.songs and args.songs.lower() not in stem.lower():
            continue
        ref_texts, ref_starts = parse_lrc_lines((lrc_dir / stem).read_text(encoding="utf-8"))
        if not ref_texts:
            print(f"  ! reference has no synced lines, skipping: {stem[:50]}")
            continue
        if stem in keys:
            key_kind = "genius"
            params = {"track_name": keys[stem]["title"], "artist_name": keys[stem]["artist"]}
        else:
            key_kind = "title"
            params = {"q": default_query(stem)}
        media = find_media(stem, folder)
        video_dur = ffprobe_duration(media) if media else None
        probe = probe_song(
            stem,
            params,
            key_kind,
            lyric_sheet(stem, debug_dir),
            ref_texts,
            ref_starts,
            video_dur,
            cache_dir,
            args.refresh,
        )
        probes.append(probe)

    if not probes:
        print("no songs probed")
        return 1

    summary = print_report(probes)
    if args.json_out:
        payload = {
            "summary": summary,
            "songs": [
                {**dataclasses.asdict(p), "sel": dataclasses.asdict(p.sel) if p.sel else None}
                for p in probes
            ],
        }
        Path(args.json_out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
