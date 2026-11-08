"""Prototype (reference only, not production code): lift the original artist's official video, then official audio.

Run: python -I proto_rank.py <rows> tests/unit/data/youtube_search/*.jsonl
"""

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

SEP = re.compile(r"\s+[-–—|]\s+|\s*[–—|]\s*")
BRACKET = re.compile(r"\([^)]*\)|\[[^\]]*\]|【[^】]*】")
COLLAB = re.compile(r"\s*(?:,|&|\bx\b|\bft\.?|\bfeat\.?|\bfeaturing\b|\bwith\b|\band\b)\s*", re.I)
CHANNEL_NOISE = re.compile(r"\b(official|vevo|music|videos?|records|topic|channel|tv)\b", re.I)
EXCLUDE = re.compile(
    r"\b(lyrics?|sing[- ]?along|live|concert|cover|karaoke|remix|instrumental|acoustic|"
    r"trailer|reaction|behind the|choreography|tutorial|lesson|sped up|slowed|8d|"
    r"multi[- ]language|scene|clip|a ?cappella|acapella)\b",
    re.I,
)
AUDIO = re.compile(r"\baudio\b", re.I)
OFFICIAL = re.compile(r"\bofficial\b|\bmusic video\b", re.I)


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", text.replace("'", "").replace("’", "")))


def compact(text: str) -> str:
    return norm(text).replace(" ", "")


def is_art_track(r: dict) -> bool:
    return (r.get("description") or "").startswith("Provided to YouTube by") or (
        r.get("channel") or ""
    ).endswith(" - Topic")


def channel_artist(r: dict) -> str:
    return compact(CHANNEL_NOISE.sub(" ", (r.get("channel") or "").removesuffix(" - Topic")))


def word_cover(words: list[str], text: str) -> float:
    have = set(norm(text).split())
    return sum(w in have for w in words) / len(words) if words else 0.0


def title_artists(r: dict, query_words: list[str]) -> set[str]:
    """Artists a title credits: the side of 'A - B' that is not the song."""
    segs = [s for s in SEP.split(BRACKET.sub(" ", r["title"])) if norm(s)]
    if len(segs) < 2:
        return set()
    # "Artist - Song" unless the left side alone is the whole query ("Song - Artist").
    a, b = segs[0], segs[1]
    artist_side = b if word_cover(query_words, a) == 1.0 and word_cover(query_words, b) < 1.0 else a
    return {compact(p) for p in COLLAB.split(artist_side) if compact(p)}


def trusted(r: dict) -> bool:
    return is_art_track(r) or bool(r.get("channel_is_verified"))


def credited(r: dict, query_words: list[str]) -> set[str]:
    artists = title_artists(r, query_words)
    if is_art_track(r) or not artists:
        artists = artists | {channel_artist(r)}
    return {a for a in artists if a}


def pick_artist(results: list[dict], query: str) -> str | None:
    words = norm(query).split()
    votes = Counter(a for r in results if trusted(r) for a in credited(r, words))
    if not votes:
        return None
    (top, n), *rest = votes.most_common(2) + [(None, 0)]
    runner = rest[0][1]
    return top if n >= 2 and n > runner else None


def song_matches(r: dict, query: str, artist: str) -> bool:
    words = [w for w in norm(query).split() if w not in artist and compact(w) not in artist]
    song_text = BRACKET.sub(" ", r["title"])
    return word_cover(words, song_text) > 0.5 if words else True


def kind(r: dict, query: str, artist: str | None) -> str | None:
    if not artist or EXCLUDE.search(r["title"]) or not song_matches(r, query, artist):
        return None
    words = norm(query).split()
    own_channel = trusted(r) and artist in channel_artist(r)
    credits = artist in credited(r, words)
    if not credits:
        return None
    art = is_art_track(r)
    label = r.get("channel_is_verified") and (OFFICIAL.search(r["title"]) or AUDIO.search(r["title"]))
    if not (art or own_channel or label):
        return None
    return "audio" if art or AUDIO.search(r["title"]) else "video"


def main(paths: list[str], n: int) -> None:
    for path in paths:
        rows = [json.loads(line) for line in open(path)][:n]
        query = Path(path).stem.replace("_", " ")
        artist = pick_artist(rows[:30], query)
        kinds = [kind(r, query, artist) for r in rows]
        print(f"===== {query!r} -> artist {artist!r}")
        for want in ("video", "audio"):
            for i, (r, k) in enumerate(zip(rows, kinds)):
                if k == want:
                    print(f"  {k:5} #{i:2} {r.get('channel', '')[:22]:22} | {r['title'][:70]}")


if __name__ == "__main__":
    main(sys.argv[2:], int(sys.argv[1]))
