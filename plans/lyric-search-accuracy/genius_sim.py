"""Prototype: retry ladder + re-rank for Genius, scored on the library (evaluation only)."""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import genius_probe as gp
from genius_variants import app_filter, correct, norm, parts
from pikaraoke.lib.genius_lyrics import clean_genius_query
from pikaraoke.lib.lrclib import normalize_line
from pikaraoke.lib.metadata_parser import EMOJI_PATTERN, youtube_id_suffix

VARIANT = re.compile(
    r"\b(parody|instrumental|karaoke|acapella|a cappella|remix|cover|commentary|translation|medley|"
    r"radio edit|live|demo|version|mix|edit|reprise|sped up|slowed|multilingual|suite|skit|snippet|mashup)\b",
    re.I,
)
STOP = {"the", "a", "an", "and", "of", "in", "to", "from", "feat", "ft", "with"}
JUNK = re.compile(
    r"\b(official|music|video|audio|lyrics?|lyric|visuali[sz]er|mv|m/v|hd|hq|uhd|4k|ultra|\d{3,4}p|"
    r"remaster(?:ed)?|blu-ray|karaoke|performance|choreography|movieclips|sing-along|sing along|"
    r"full|scene|clip|anniversary|edition|uncensored|explicit|ver\.?|version)\b",
    re.I,
)
BRACKET = re.compile(r"\([^()]*\)|\[[^\[\]]*\]|【[^】]*】|《[^》]*》")
QUOTED = re.compile(r"[\"“‘'《【]([^\"”’'》】]{2,})[\"”’'》】]")


def toks(s):
    return [t for t in normalize_line(s).split() if t not in STOP]


def tidy(s):
    return re.sub(r"\s+", " ", s).strip(" -–—|_.,")


def ladder(title: str) -> list[str]:
    """Candidate queries for a raw YouTube title, most specific first."""
    t = EMOJI_PATTERN.sub("", title).replace("\xad", "").replace("_", " | ")
    t = re.sub(r"[#@]\w+", " ", t)
    out = []
    quoted = QUOTED.search(t)
    # brackets: drop junk / "from X" ones, keep the rest
    def keep(m):
        inner = m.group(0)[1:-1]
        return " " if JUNK.search(inner) or re.match(r"\s*(from|feat|ft)\b", inner, re.I) or not inner.strip() else m.group(0)
    kept = tidy(JUNK.sub(" ", BRACKET.sub(keep, t).split("|")[0]))
    bare = tidy(JUNK.sub(" ", BRACKET.sub(" ", t).split("|")[0]))
    if quoted:
        rest = tidy(JUNK.sub(" ", BRACKET.sub(" ", t.replace(quoted.group(0), " ")).split("|")[0]))
        out += [f"{quoted.group(1)} {rest}", quoted.group(1)]
    out += [kept, bare]
    if " - " in bare:
        out.append(bare.split(" - ", 1)[1])
    seen, res = set(), []
    for q in out:
        q = tidy(q.replace(" - ", " "))
        if q and q.lower() not in seen:
            seen.add(q.lower())
            res.append(q)
    return res


def score(h, context_tokens):
    ht, ha = toks(BRACKET.sub(" ", h["title"])), toks(h["artist"])
    ctx = set(context_tokens)
    title_cov = sum(t in ctx for t in ht) / len(ht) if ht else 0
    artist_hit = sum(t in ctx for t in ha) / len(ha) if ha else 0
    variant = bool(VARIANT.search(h["title"])) and not VARIANT.search(" ".join(context_tokens))
    return (title_cov >= 1.0, round(artist_hit > 0), not variant, title_cov, (h["views"] or 0))


def run(queries, context, r, left, title, movie, max_calls=2):
    merged, seen, calls = [], set(), 0
    for q in queries:
        if calls >= max_calls:
            break
        hits = app_filter(gp.raw(q))
        calls += 1
        for h in hits:
            if h["id"] not in seen:
                seen.add(h["id"])
                merged.append(h)
        # stop early once a rung yields a full-title + artist match
        if any(score(h, context)[0] and score(h, context)[1] for h in hits):
            break
    ranked = sorted(merged, key=lambda h: score(h, context), reverse=True)[:8]
    rk = next((i for i, h in enumerate(ranked, 1) if correct(h, left, title, movie, r.get("genius"))), None)
    return rk, ranked, calls


mode = sys.argv[1]
tally, calls_total, misses = Counter(), 0, []
for r in gp.rows:
    left, title, movie = parts(r)
    if not title or left == title:
        continue
    if mode == "curated":
        queries = [f"{left} {title}", title]
        context = toks(f"{left} {title}")
    else:
        raw_title = r.get("old_title") or ""
        if not raw_title or not youtube_id_suffix(r["file"]):
            continue
        queries = ladder(raw_title)
        context = toks(raw_title)
    rk, ranked, calls = run(queries, context, r, left, title, movie, max_calls=int(sys.argv[2]) if len(sys.argv) > 2 else 2)
    calls_total += calls
    b = "first" if rk == 1 else "2-8" if rk else "miss"
    tally[("movie" if movie else "artist", b)] += 1
    if b != "first":
        misses.append((b, r["file"][:70], queries, [(h["title"], h["artist"][:40]) for h in ranked[:3]]))
print(mode, dict(sorted(tally.items())), "calls:", calls_total)
if "-v" in sys.argv:
    for m in misses:
        print(m)
if "-top" in sys.argv:
    for r in gp.rows:
        left, title, movie = parts(r)
        if not movie:
            continue
        rk, ranked, _ = run([f"{left} {title}", title], toks(f"{left} {title}"), r, left, title, movie)
        today = app_filter(gp.raw(f"{left} - {title}"))
        print(f"{left[:22]:22} | {title[:28]:28} | NEW: {ranked[0]['artist'][:45] if ranked else '-':45} | TODAY: {(today[0]['title'][:25] + ' / ' + today[0]['artist'][:30]) if today else '-'}")
