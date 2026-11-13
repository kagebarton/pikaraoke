"""Shared pieces for the run-2 Genius replay: cached search, the answer key, the right-hit test."""
import configparser
import json
import re
import time
import unicodedata
from pathlib import Path

import lyricsgenius

HERE = Path(__file__).parent
rows = json.loads((HERE / "truth.json").read_text(encoding="utf-8"))
cache_path = HERE / "genius_raw.json"
cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
_client = None
calls_made = 0
BRACKET = re.compile(r"\([^()]*\)|\[[^\[\]]*\]|【[^】]*】|《[^》]*》")
STOP = {"the", "a", "an", "and", "of", "in", "to", "from", "feat", "ft", "with", "cast", "x"}


def client():
    global _client
    if _client is None:
        cfg = configparser.ConfigParser()
        cfg.read(Path.home() / ".pikaraoke" / "config.ini")
        token = next(cfg[s]["genius_token"] for s in cfg.sections() if "genius_token" in cfg[s])
        _client = lyricsgenius.Genius(token, timeout=15)
    return _client


def raw(query: str) -> list[dict]:
    """Genius's 20 hits for a query, as the app would receive them, cached by query."""
    global calls_made
    if query not in cache:
        for attempt in range(4):
            try:
                data = client().search(query, per_page=20, type_="song")
                break
            except Exception:  # scratch probe: retry any transient drop
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))
        hits = (data.get("sections") or [{}])[0].get("hits", [])
        cache[query] = [
            {
                "type": h.get("type"),
                "id": h["result"]["id"],
                "title": h["result"]["title"],
                "artist": h["result"].get("artist_names") or h["result"]["primary_artist"]["name"],
                "primary": h["result"]["primary_artist"]["name"],
                "state": h["result"].get("lyrics_state"),
                "instrumental": h["result"].get("instrumental"),
                "views": (h["result"].get("stats") or {}).get("pageviews"),
                "year": (h["result"].get("release_date_components") or {}).get("year"),
            }
            for h in hits
        ]
        calls_made += 1
        if calls_made % 20 == 0:
            save()
        time.sleep(0.35)
    return cache[query]


def save():
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def fold(s: str) -> str:
    """Lowercase, accents and apostrophes dropped, punctuation to spaces; CJK and Hangul kept."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"['’‘`´]", "", s)
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def title_key(s: str) -> str:
    return fold(BRACKET.sub(" ", s))


def words(s: str) -> set[str]:
    return {t for t in fold(s).split() if t not in STOP and len(t) > 1}


def app_filter(hits: list[dict], query: str = "") -> list[dict]:
    """Today's filter in genius.py: songs only, Genius's own accounts dropped except Romanizations."""
    blocked = "translation" if "genius" in query.lower() else "genius"
    return [h for h in hits if h["type"] == "song" and (blocked not in h["artist"].lower() or "romaniz" in h["artist"].lower())]


def correct(h: dict, r: dict) -> bool:
    """The recorded pick, or the right title and (for artist-named songs) a shared artist word."""
    if r.get("genius") and h["id"] == r["genius"].get("id"):
        return True
    wanted = {title_key(t) for t in [r["title"], *r.get("alts", [])]} - {""}
    got = title_key(h["title"])
    hit = got in wanted or any(not w.isascii() and w.replace(" ", "") in fold(h["title"]).replace(" ", "") for w in wanted)
    if not hit:
        return False
    return r["kind"] == "film" or bool(words(r["artist"]) & words(h["artist"]))


def position(ranked: list[dict], r: dict) -> int | None:
    return next((i for i, h in enumerate(ranked, 1) if correct(h, r)), None)
