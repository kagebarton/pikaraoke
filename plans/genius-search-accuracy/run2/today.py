"""Today's two starting queries, replayed on each song's YouTube title."""
import sys
from collections import Counter

import gx
from pikaraoke.lib.genius_lyrics import clean_genius_query
from pikaraoke.lib.metadata_parser import clean_search_query

CLEANERS = {"search page (clean_genius_query)": clean_genius_query, "library tools (clean_search_query)": lambda s: clean_search_query(s) or s}
verbose = "-v" in sys.argv
for src in ("yt_title",):
    for label, clean in CLEANERS.items():
        tally, notes = Counter(), []
        for r in gx.rows:
            if not r.get(src):
                continue
            q = clean(r[src])
            hits = gx.raw(q)
            shown = gx.app_filter(hits, q)[:8]
            pos = gx.position(shown, r)
            bucket = "first" if pos == 1 else "2-8" if pos else "not listed"
            tally[(r["kind"], bucket)] += 1
            if bucket != "first":
                notes.append(f"  [{r['kind']} {bucket}] {q!r} n={len(hits)} -> " + "; ".join(f"{h['title'][:24]} / {h['artist'][:22]}" for h in shown[:2]))
        print(f"\n== {src}, {label}")
        for kind in ("artist", "film"):
            print(f"  {kind}: first {tally[(kind, 'first')]}, 2-8 {tally[(kind, '2-8')]}, not listed {tally[(kind, 'not listed')]}")
        if verbose:
            print("\n".join(notes))
gx.save()
