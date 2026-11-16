"""Freeze GATE G's videos as fixtures for pikaraoke/lib/genius_query.py.

usage: freeze.py            (from anywhere; run in env `pik`, at the commit that froze the fixtures)

Writes tests/unit/data/genius_search/{gate_g.jsonl,gate_g_answers.json}: each of the gate's videos
read through `find_song` as the search page reads it (three calls, the channel, the typed search),
with the code as it stands. The videos and the answers are the gate's own caches, `youtube.json` and
`genius.json` (the uncommitted full YouTube cache when it is there: the same videos and titles).

Makes no YouTube or Genius call: a query missing from genius.json stops the run, and neither cache
is rewritten. Not in the fixtures: 16.3 and 30.4, whose titles hold a lyric line (the Executor rules
of plans/genius-search-spec.md: no lyric text).
"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))  # this worktree's pikaraoke, not an editable install's
sys.path.insert(0, str(HERE))  # this folder's collect.py, not the older one a level up

import collect  # noqa: E402

OUT = collect.FIXTURES
VIDEOS, ROWS = 120, 118  # what the gate kept, and what is frozen of it
LYRIC_TITLES = {"pW6N42hSHrY": "16.3", "WUxgIPYDQHE": "30.4"}  # by ID, with the number it checks


def no_youtube(*_args, **_kwargs):
    raise SystemExit("STOP: a YouTube search was needed (the freeze makes no YouTube call)")


collect.get_search_results = no_youtube


class OfflineGenius(collect.CachedGenius):
    def search(self, query):
        if query not in self.answers:
            raise SystemExit(f"STOP: {query!r} is not in genius.json (the freeze makes no call)")
        return super().search(query)


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def row(video: dict, term: str, genius: OfflineGenius) -> dict:
    read = collect.read_video(genius, video, term)
    parsed = asdict(read["parsed"])
    del parsed["raw"]  # it is the row's yt_title
    found = read["with_typed"]
    return {
        "id": video["id"],
        "yt_title": video["title"],
        "channel": video["channel"],
        "typed": term,
        "parsed": parsed,
        "search_page": {
            "queries": read["queries"],
            "hits": [h.id for h in found.hits],
            "preselect": found.preselect,
        },
    }


def main() -> None:
    kept = collect.select(collect.load_youtube())
    genius = OfflineGenius()
    rows: list[dict] = []
    seen = 0
    for number, term, _carries, _kind in collect.SEARCHES:
        for place, video in enumerate(kept[number], 1):
            seen += 1
            if video["id"] in LYRIC_TITLES:
                assert LYRIC_TITLES[video["id"]] == f"{number}.{place}", video["id"]
                continue
            rows.append(row(video, term, genius))
    assert (seen, len(rows)) == (VIDEOS, ROWS), (seen, len(rows))
    assert genius.calls_this_run == 0
    asked = dict.fromkeys(q for r in rows for q in r["search_page"]["queries"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gate_g.jsonl").write_text("".join(dump(r) + "\n" for r in rows), encoding="utf-8")
    lines = ",\n".join(f"{dump(q)}: {dump(genius.answers[q])}" for q in asked)  # a query a line
    (OUT / "gate_g_answers.json").write_text("{\n" + lines + "\n}\n", encoding="utf-8")
    print(f"{len(rows)} rows, {len(asked)} queries, no YouTube or Genius call")


if __name__ == "__main__":
    main()
