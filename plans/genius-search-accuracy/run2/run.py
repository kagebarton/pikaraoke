"""Replay a query ladder and an order for the merged hits, scored against the answer key.

usage: run.py {proto|new|new-nochannel} {yt_title|name} [max_calls] [-v] [-film]
"""
import re
import sys
from collections import Counter

import builder
import gx
from pikaraoke.lib.lrclib import normalize_line
from pikaraoke.lib.metadata_parser import EMOJI_PATTERN

# --- the 2026-11-11 prototype, copied from ../genius_sim.py -------------------------------------
P_VARIANT = re.compile(
    r"\b(parody|instrumental|karaoke|acapella|a cappella|remix|cover|commentary|translation|medley|"
    r"radio edit|live|demo|version|mix|edit|reprise|sped up|slowed|multilingual|suite|skit|snippet|mashup)\b",
    re.I,
)
P_STOP = {"the", "a", "an", "and", "of", "in", "to", "from", "feat", "ft", "with"}
P_JUNK = re.compile(
    r"\b(official|music|video|audio|lyrics?|lyric|visuali[sz]er|mv|m/v|hd|hq|uhd|4k|ultra|\d{3,4}p|"
    r"remaster(?:ed)?|blu-ray|karaoke|performance|choreography|movieclips|sing-along|sing along|"
    r"full|scene|clip|anniversary|edition|uncensored|explicit|ver\.?|version)\b",
    re.I,
)
P_BRACKET = re.compile(r"\([^()]*\)|\[[^\[\]]*\]|【[^】]*】|《[^》]*》")
P_QUOTED = re.compile(r"[\"“‘'《【]([^\"”’'》】]{2,})[\"”’'》】]")


def p_toks(s):
    return [t for t in normalize_line(s).split() if t not in P_STOP]


def p_tidy(s):
    return re.sub(r"\s+", " ", s).strip(" -–—|_.,")


def p_ladder(title):
    t = EMOJI_PATTERN.sub("", title).replace("\xad", "").replace("_", " | ")
    t = re.sub(r"[#@]\w+", " ", t)
    out = []
    quoted = P_QUOTED.search(t)

    def keep(m):
        inner = m.group(0)[1:-1]
        return " " if P_JUNK.search(inner) or re.match(r"\s*(from|feat|ft)\b", inner, re.I) or not inner.strip() else m.group(0)

    kept = p_tidy(P_JUNK.sub(" ", P_BRACKET.sub(keep, t).split("|")[0]))
    bare = p_tidy(P_JUNK.sub(" ", P_BRACKET.sub(" ", t).split("|")[0]))
    if quoted:
        rest = p_tidy(P_JUNK.sub(" ", P_BRACKET.sub(" ", t.replace(quoted.group(0), " ")).split("|")[0]))
        out += [f"{quoted.group(1)} {rest}", quoted.group(1)]
    out += [kept, bare]
    if " - " in bare:
        out.append(bare.split(" - ", 1)[1])
    seen, res = set(), []
    for q in out:
        q = p_tidy(q.replace(" - ", " "))
        if q and q.lower() not in seen:
            seen.add(q.lower())
            res.append(q)
    return res


def p_score(h, ctx_tokens):
    ht, ha = p_toks(P_BRACKET.sub(" ", h["title"])), p_toks(h["artist"])
    ctx = set(ctx_tokens)
    title_cov = sum(t in ctx for t in ht) / len(ht) if ht else 0
    artist_hit = sum(t in ctx for t in ha) / len(ha) if ha else 0
    variant = bool(P_VARIANT.search(h["title"])) and not P_VARIANT.search(" ".join(ctx_tokens))
    return (title_cov >= 1.0, round(artist_hit > 0), not variant, title_cov, (h["views"] or 0))


# -------------------------------------------------------------------------------------------------


def replay(strategy: str, text: str, channel: str | None, max_calls: int):
    """(ranked hits, calls made, whether the first hit would be preselected, queries)."""
    if strategy == "proto":
        queries, ctx = p_ladder(text), p_toks(text)
        key = lambda h: p_score(h, ctx)
        sure = lambda h: bool(p_score(h, ctx)[0] and p_score(h, ctx)[1])
        keep = lambda hits: gx.app_filter(hits)
    else:
        builder.WHO_TIERS = strategy != "new-views"
        parsed = builder.parse(text, None if strategy == "new-nochannel" else channel)
        queries = builder.ladder(parsed)
        key = lambda h: builder.order_key(h, parsed)
        sure = lambda h: builder.confident(h, parsed)
        keep = lambda hits: [h for h in hits if builder.usable(h)]
    merged, seen, calls = [], set(), 0
    for q in queries[:max_calls]:
        hits = keep(gx.raw(q))
        calls += 1
        merged += [h for h in hits if h["id"] not in seen]
        seen.update(h["id"] for h in hits)
        if any(sure(h) for h in hits):
            break
    ranked = sorted(merged, key=key, reverse=True)[:8]
    return ranked, calls, bool(ranked) and sure(ranked[0]), queries[:max_calls]


if __name__ == "__main__":
    strategy, src = sys.argv[1], sys.argv[2]
    max_calls = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 3
    tally, pre, calls_total, notes, films = Counter(), Counter(), 0, [], []
    for r in gx.rows:
        if not r.get(src):
            continue
        ranked, calls, sure, queries = replay(strategy, r[src], r.get("channel") if src == "yt_title" else None, max_calls)
        calls_total += calls
        pos = gx.position(ranked, r)
        bucket = "first" if pos == 1 else "2-8" if pos else "not listed"
        tally[(r["kind"], bucket)] += 1
        pre[(r["kind"], "preselected" if sure else "left open", "right" if pos == 1 else "wrong")] += 1
        if bucket != "first" or (sure and pos != 1):
            notes.append(f"  [{r['kind']} {bucket}{' PRESELECTED' if sure else ''}] {r[src][:60]!r} q={queries} -> " + "; ".join(f"{h['title'][:26]} / {h['artist'][:24]}" for h in ranked[:2]))
        if r["kind"] == "film" or r.get("film"):
            h = ranked[0] if ranked else None
            films.append(f"  {'*' if sure else ' '}{pos or '-'} {(r.get('film') or '')[:20]:20} {r.get('year') or '':4} | {r['title'][:28]:28} | " + (f"{h['title'][:28]} / {h['artist'][:44]} ({h.get('year')}, {h.get('views') or 0})" if h else "-"))
        total = sum(1 for _ in gx.rows)
    n = sum(tally.values())
    print(f"== {strategy} on {src}, up to {max_calls} calls: {n} songs, {calls_total / n:.2f} calls a song")
    for kind in ("artist", "film"):
        print(f"  {kind}: first {tally[(kind, 'first')]}, 2-8 {tally[(kind, '2-8')]}, not listed {tally[(kind, 'not listed')]}"
              f" | preselected {pre[(kind, 'preselected', 'right')] + pre[(kind, 'preselected', 'wrong')]} (wrong {pre[(kind, 'preselected', 'wrong')]}),"
              f" left open {pre[(kind, 'left open', 'right')] + pre[(kind, 'left open', 'wrong')]} (first was right {pre[(kind, 'left open', 'right')]})")
    if "-v" in sys.argv:
        print("\n".join(notes))
    if "-film" in sys.argv:
        print("\n".join(films))
    gx.save()
