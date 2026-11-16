"""Ask the admin for a song's lyric source on the command line.

Shared by ``regen_alignment_bundles.py`` and ``backfill_artifacts.py``.
"""

from __future__ import annotations

from pathlib import Path

from pikaraoke.lib.genius import HITS_PER_QUERY, GeniusClient, GeniusHit
from pikaraoke.lib.genius_query import LIBRARY_CALLS, find_song, start_query
from pikaraoke.lib.library_regen import file_title

HELP = (
    "Choose a numbered hit, or [s]=local SRT, [t]=transcribe, [k]=skip song (at either prompt). "
    "A hit marked '<- Enter' is the safe pick: Enter takes it."
)

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


def _search(
    genius: GeniusClient, title: str, query: str, start: str
) -> tuple[list[GeniusHit], int | None]:
    """The hits for ``query``, and the one safe to take on Enter, if any.

    The text the prompt started with is the song's own search: the title's whole query
    ladder, which may preselect. Any other text goes to Genius as typed, with nothing
    preselected.
    """
    if query == start:
        found = find_song(
            lambda q: genius.search(q, limit=HITS_PER_QUERY), title, max_calls=LIBRARY_CALLS
        )
        return found.hits, found.preselect
    return genius.search(query), None


def ask_lyrics_source(song: Path, genius: GeniusClient) -> tuple:
    """Search Genius until the admin picks a source.

    Returns ``("genius", id)``, ``("srt",)``, ``("transcribe",)`` or ``("skip",)``.
    """
    print(f"\n{song.name}")
    title = file_title(song)
    start = start_query(title)
    query = start
    while True:
        ans = input(f"  search query [{query}] or s/t/k: ").strip()
        if ans.lower() in _SHORTCUTS:
            return _SHORTCUTS[ans.lower()]
        query = ans or query
        hits, preselect = _search(genius, title, query, start)
        if not hits:
            print("  (no Genius hits)")
            continue
        for i, h in enumerate(hits, 1):
            mark = "  <- Enter" if h.id == preselect else ""
            print(f"  {i}) {h.title} - {h.artist}{mark}")
        enter = "Enter=1, " if preselect is not None else ""
        ans = input(f"  choose [{enter}1-{len(hits)}/s/t/k or new query]: ").strip()
        if ans.lower() in _SHORTCUTS:
            return _SHORTCUTS[ans.lower()]
        if ans.isdigit() and 1 <= int(ans) <= len(hits):
            return ("genius", hits[int(ans) - 1].id)
        if ans:
            query = ans  # any other answer is the next search's default
        elif preselect is not None:
            return ("genius", preselect)
