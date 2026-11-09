"""Ask the admin for a song's lyric source on the command line.

Shared by ``regen_alignment_bundles.py`` and ``backfill_artifacts.py``.
"""

from __future__ import annotations

from pathlib import Path

from pikaraoke.lib.genius import GeniusClient
from pikaraoke.lib.library_regen import default_query

HELP = "Choose a numbered hit, or [s]=local SRT, [t]=transcribe, [k]=skip song (at either prompt)."

# Answers that pick a source rather than search. Taken at the search prompt
# too, so a song that only needs ``s`` doesn't search Genius first.
_SHORTCUTS = {
    "s": ("srt",),
    "srt": ("srt",),
    "t": ("transcribe",),
    "transcribe": ("transcribe",),
    "k": ("skip",),
    "skip": ("skip",),
    "q": ("skip",),
}


def ask_lyrics_source(song: Path, genius: GeniusClient) -> tuple:
    """Search Genius until the admin picks a source.

    Returns ``("genius", id)``, ``("srt",)``, ``("transcribe",)`` or ``("skip",)``.
    """
    print(f"\n{song.name}")
    query = default_query(song)
    while True:
        ans = input(f"  search query [{query}] or s/t/k: ").strip()
        if ans.lower() in _SHORTCUTS:
            return _SHORTCUTS[ans.lower()]
        query = ans or query
        hits = genius.search(query, limit=8)
        if not hits:
            print("  (no Genius hits)")
            continue
        for i, h in enumerate(hits, 1):
            print(f"  {i}) {h.title} - {h.artist}")
        ans = input(f"  choose [1-{len(hits)}/s/t/k or new query]: ").strip()
        if ans.lower() in _SHORTCUTS:
            return _SHORTCUTS[ans.lower()]
        if ans.isdigit() and 1 <= int(ans) <= len(hits):
            return ("genius", hits[int(ans) - 1].id)
        if ans:
            query = ans  # any other answer is the next search's default
