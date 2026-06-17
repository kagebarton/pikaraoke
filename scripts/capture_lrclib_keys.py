#!/usr/bin/env python3
"""Capture canonical Genius artist/title for LRCLIB-reference songs.

Step 1 of ``plans/lrclib-timing-prior.md`` measures how well an automatic
LRCLIB search finds the right synced-lyric variant. To query the way
production would, each non-SRT corpus song needs a trustworthy search key:
the chosen ``GeniusHit``'s canonical title/artist, not a noisy video title
("... (Official Video)---uuZE_IRwLNI"). Production writes those keys to a
lyric-choice sidecar, but that sidecar lives in a temp dir and is absent
here, so this tool re-derives them interactively — mirroring the Genius
prompt in ``scripts/backfill_artifacts.py`` — and persists them beside the
ground-truth files at ``<folder>/lrclib/genius_keys.json`` for the probe.

Only songs with a hand-fetched ``<folder>/lrclib/<stem>`` file are
considered (the step-1 ground truth). SRT-sourced songs are skipped: the
probe keys those from a cleaned title parse, since they exist only for
step 2's testbed. Keys are saved after each song, so an interrupted walk
keeps its progress; re-running skips songs already captured unless
``--force``.

Run from the repo root::

    python scripts/capture_lrclib_keys.py [--folder PATH] [--force]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# Allow running as ``python scripts/capture_lrclib_keys.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.genius import GeniusClient, GeniusHit  # noqa: E402
from pikaraoke.lib.get_platform import get_default_dl_dir, get_platform  # noqa: E402
from pikaraoke.lib.metadata_parser import (  # noqa: E402
    clean_search_query,
    youtube_id_suffix,
)
from pikaraoke.lib.preference_manager import PreferenceManager  # noqa: E402

KEYS_FILENAME = "genius_keys.json"
_VIDEO_ID_RE = re.compile(r"---([\w-]{11})$")


def default_query(stem: str) -> str:
    """Strip the YouTube ID suffix and tidy the stem into a search query."""
    suffix = youtube_id_suffix(stem)
    title = stem[: -len(suffix)] if suffix else stem
    return clean_search_query(title) or title


def bundle_source_kind(stem: str, debug_dir: Path) -> str | None:
    """``lyrics.source_kind`` from the song's alignment-debug bundle, or None.

    Exact stem match first, then a video-ID glob for songs renamed since
    capture (mirrors the reference resolution in ``eval_alignment``).
    """
    cand = debug_dir / f"{stem}.json"
    if not cand.is_file():
        m = _VIDEO_ID_RE.search(stem)
        hits = sorted(debug_dir.glob(f"*{m.group(1)}*.json")) if m else []
        if not hits:
            return None
        cand = hits[0]
    try:
        bundle = json.loads(cand.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return bundle.get("lyrics", {}).get("source_kind")


def load_keys(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_keys(path: Path, keys: dict[str, dict]) -> None:
    """Atomic write (tmpfile + rename) of the keys sidecar."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.stem}-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(keys, f, ensure_ascii=False, indent=2, sort_keys=True)
        Path(tmp).rename(path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def prompt_one(stem: str, genius: GeniusClient) -> dict | None:
    """Interactively resolve one song's canonical Genius key.

    Returns ``{"title", "artist", "genius_id", "query"}`` for a chosen or
    manually entered key, or ``None`` to skip the song (the probe falls
    back to a title parse).
    """
    print(f"\n{stem}")
    query = default_query(stem)
    while True:
        hits: list[GeniusHit] = genius.search(query, limit=8)
        if hits:
            for i, h in enumerate(hits, 1):
                print(f"  {i}) {h.title} - {h.artist}")
            prompt = f"  choose [1-{len(hits)} / m=manual / k=skip / or new query]: "
        else:
            print(f"  (no Genius hits for {query!r})")
            prompt = "  choose [m=manual / k=skip / or new query]: "
        ans = input(prompt).strip()

        low = ans.lower()
        if low in ("k", "skip", "q", ""):
            return None
        if low in ("m", "manual"):
            artist = input("    artist: ").strip()
            title = input("    title: ").strip()
            if not (artist and title):
                print("    (need both artist and title; not saved)")
                continue
            return {"title": title, "artist": artist, "genius_id": None, "query": query}
        if low.isdigit() and hits and 1 <= int(low) <= len(hits):
            h = hits[int(low) - 1]
            return {"title": h.title, "artist": h.artist, "genius_id": h.id, "query": query}
        # Anything else is a new search query.
        query = ans


def main() -> int:
    default_folder = os.path.expanduser(get_default_dl_dir(get_platform()))
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--folder", default=default_folder, help=f"song library (default: {default_folder})"
    )
    p.add_argument("--force", action="store_true", help="re-prompt songs already in the sidecar")
    args = p.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    lrc_dir = folder / "lrclib"
    if not lrc_dir.is_dir():
        print(f"No LRCLIB reference dir: {lrc_dir}", file=sys.stderr)
        return 2
    debug_dir = folder / "alignment_debug"

    genius = GeniusClient(api_token=PreferenceManager().get("genius_token", ""))
    if not genius._token:
        print("No genius_token in preferences; searches return nothing. Use [m] or [k].\n")

    keys_path = lrc_dir / KEYS_FILENAME
    keys = load_keys(keys_path)

    ground_truth = sorted(
        f.name for f in lrc_dir.iterdir() if f.is_file() and f.name != KEYS_FILENAME
    )
    todo: list[str] = []
    skipped_srt: list[str] = []
    for stem in ground_truth:
        if bundle_source_kind(stem, debug_dir) == "srt":
            skipped_srt.append(stem)
        elif args.force or stem not in keys:
            todo.append(stem)

    print(f"LRCLIB ground-truth songs: {len(ground_truth)}")
    print(f"  SRT-sourced (probe uses title parse, skipped): {len(skipped_srt)}")
    print(f"  already captured: {sum(1 for s in ground_truth if s in keys and s not in todo)}")
    print(f"  to capture now: {len(todo)}")
    if not todo:
        print("\nNothing to capture.")
        return 0
    print("\nFor each song: pick the hit matching the recording, or re-type the query.")
    print("=" * 64)

    captured = 0
    for n, stem in enumerate(todo, 1):
        print(f"\n[{n}/{len(todo)}]", end="")
        choice = prompt_one(stem, genius)
        if choice is None:
            print("  -> skipped")
            continue
        keys[stem] = choice
        save_keys(keys_path, keys)  # persist after each so progress survives Ctrl-C
        captured += 1
        print(f"  -> saved: {choice['title']} - {choice['artist']}")

    print(f"\nDone. captured={captured} skipped={len(todo) - captured}")
    print(f"Keys: {keys_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
