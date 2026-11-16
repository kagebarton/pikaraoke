"""Freeze the fixtures for pikaraoke/lib/genius_query.py from the prototype and its cached answers.

usage: freeze.py <dir holding the 44 YouTube search fixtures>

Writes tests/unit/data/genius_search/{library.jsonl,unseen.jsonl,answers.json}. Makes no Genius
call: a query missing from genius_raw.json stops the run, and the cache file is never rewritten.

The 30 searches that only exist on branch search_official_captions are read from a temporary copy
(plans/genius-search-spec.md, "Fixtures and tests"); run it at the commit that froze the fixtures,
because holdout.py imports clean_genius_query, which a later phase deletes.
"""
import contextlib
import io
import json
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))  # this worktree's pikaraoke, not an editable install's

import builder  # noqa: E402
import gx  # noqa: E402
import run  # noqa: E402

OUT = REPO / "tests" / "unit" / "data" / "genius_search"
LIBRARY_ROWS, SEARCHES, UNSEEN_ROWS = 206, 44, 176  # what the spec's Results log row 1 counted
WITH_CHANNEL_CALLS, NO_CHANNEL_CALLS = 3, 2


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def cached_only(query: str) -> list[dict]:
    if query not in gx.cache:
        raise SystemExit(f"STOP: {query!r} is not in genius_raw.json (the freeze calls no Genius)")
    return gx.cache[query]


gx.raw = cached_only
gx.save = lambda: None


def unseen_videos(search_dir: Path) -> list[dict]:
    """The videos holdout.py selects (it replays three strategies as it imports)."""
    sys.argv = ["holdout.py", str(search_dir)]
    with contextlib.redirect_stdout(io.StringIO()):
        import holdout
    return [
        {"id": v["id"], "yt_title": v["yt_title"], "channel": v["channel"] or ""}
        for v in holdout.videos
    ]


def library_videos() -> list[dict]:
    meta = json.loads((HERE / "yt_meta.json").read_text(encoding="utf-8"))
    videos = []
    for r in gx.rows:
        if r.get("id"):
            title, channel = meta[r["id"]]["title"], meta[r["id"]]["channel"] or ""
            assert (title, channel) == (r["yt_title"], r["channel"] or ""), r["id"]
            videos.append({"id": r["id"], "yt_title": title, "channel": channel})
    return videos


def cut(hit: dict) -> dict:
    """A cached Genius hit as the app's GeniusHit reads it."""
    return {
        "id": hit["id"],
        "title": hit["title"],
        "artist": hit["artist"],
        "primary_artist": hit["primary"],
        "year": hit["year"],
        "views": hit["views"] or 0,
    }


def replayed(strategy: str, video: dict, calls: int, answers: dict) -> dict:
    ranked, made, sure, queries = run.replay(strategy, video["yt_title"], video["channel"], calls)
    asked = queries[:made]
    for q in asked:
        answers[q] = [cut(h) for h in gx.raw(q) if builder.usable(h)]
    return {
        "queries": asked,
        "hits": [h["id"] for h in ranked],
        "preselect": ranked[0]["id"] if sure else None,
    }


def row(video: dict, answers: dict, *, both_runs: bool) -> dict:
    parsed = asdict(builder.parse(video["yt_title"], video["channel"]))
    del parsed["raw"]  # it is the row's yt_title
    with_channel = replayed("new", video, WITH_CHANNEL_CALLS, answers)
    out = {**video, "parsed": parsed, "with_channel": with_channel}
    if both_runs:
        out["no_channel"] = replayed("new-nochannel", video, NO_CHANNEL_CALLS, answers)
    return out


def write_jsonl(name: str, rows: list[dict]) -> None:
    (OUT / name).write_text("".join(dump(r) + "\n" for r in rows), encoding="utf-8")


def main(search_dir: Path) -> None:
    assert len(list(search_dir.glob("*.jsonl"))) == SEARCHES, f"expected {SEARCHES} searches"
    answers: dict[str, list[dict]] = {}
    library = [row(v, answers, both_runs=True) for v in library_videos()]
    unseen = [row(v, answers, both_runs=False) for v in unseen_videos(search_dir)]
    assert (len(library), len(unseen)) == (LIBRARY_ROWS, UNSEEN_ROWS), (len(library), len(unseen))
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl("library.jsonl", library)
    write_jsonl("unseen.jsonl", unseen)
    lines = ",\n".join(f"{dump(q)}: {dump(hits)}" for q, hits in answers.items())  # a query a line
    (OUT / "answers.json").write_text("{\n" + lines + "\n}\n", encoding="utf-8")
    print(f"{len(library)} library, {len(unseen)} unseen rows, {len(answers)} queries, no Genius call")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
