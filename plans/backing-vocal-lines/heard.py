"""Phase 0 steps 3-4: the heard test and the transcript-free comparison rule, scored on the
step 2 labels.

    PYTHONPATH=. python plans/backing-vocal-lines/heard.py ~/pikaraoke-songs plans/backing-vocal-lines/out

Reads out/inventory.json, out/songs.json, out/labels.json (labels fixed before this ran).
Writes out/heard.json: per row, every variant's share and kept flag. report.py and gate.py
print the GATE A tables from it.
"""

import json
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import srt

from pikaraoke.lib.srt_cues import clean_cue_texts
from pikaraoke.lib.token_align import _match_simple, _normalize_token

# Step 2's vocable set (A2 split). Fixed in the plan before this ran.
VOCABLES = set("oh ohh ooh ah ahh uh mm mmm hmm woo whoa la na da ya yeah hey eh ay aye ha".split())

# Variant knob: transcribers spell vocables loosely, so a class matches any member.
VOCABLE_CLASSES = {
    "O": "o oh ohh ohhh ooh oooh ooo oo woo wooh whoa woah wo ow",
    "A": "ah ahh aah ha hah uh uhh huh",
    "M": "mm mmm mmmm hmm hm mhm um",
    "Y": "yeah yea yeh ya yah ye yay",
    "H": "hey hei ay aye ayy eh ey",
    "L": "la na da du doo ba di dum",
}
CLASS_OF = {w: c for c, ws in VOCABLE_CLASSES.items() for w in ws.split()}


@dataclass(frozen=True)
class Rule:
    name: str
    pad: float = 0.5  # seconds added to each side of the cue window
    offset: bool = True  # shift the cue window by the song's fitted display lead
    consume: str = "own+nb"  # none | own | own+nb: words other lines account for are used up
    vocable: str = "class"  # exact | class
    share: str = "types"  # types | tokens: what the threshold counts
    min_share: float = 0.5
    band: float = 1.0  # consume "global": how far from its cue a line's word may match


def tokens(text: str) -> list[str]:
    return [t for t in (_normalize_token(p) for p in re.split(r"[\s\-/]+", text)) if t]


def same(a: str, b: str, rule: Rule) -> bool:
    if rule.vocable == "class" and a in CLASS_OF and CLASS_OF.get(a) == CLASS_OF.get(b):
        return True
    return _match_simple(a, b)


def lcs_pairs(xs: list[str], ys: list[str], rule: Rule) -> list[tuple[int, int]]:
    """Index pairs of one longest common subsequence of xs and ys."""
    n, m = len(xs), len(ys)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = (
                dp[i + 1][j + 1] + 1
                if same(xs[i], ys[j], rule)
                else max(dp[i + 1][j], dp[i][j + 1])
            )
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        if same(xs[i], ys[j], rule) and dp[i][j] == dp[i + 1][j + 1] + 1:
            pairs.append((i, j))
            i, j = i + 1, j + 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


@dataclass
class Song:
    words: list[dict]  # transcribe_words, normalised token in "norm"
    offset: float
    spans: list[tuple[float, float]]  # every cue's span
    main: list[list[str]]  # every cue's tokens outside parentheses, cleaned ([] if dropped)


def load_song(lib: Path, song: dict) -> Song:
    bundle = json.loads((lib / "alignment_debug" / song["bundle"]).read_text())
    cues = list(srt.parse((lib / song["sheet"]).read_text(encoding="utf-8-sig")))
    cleaned = clean_cue_texts([c.content for c in cues])
    words = []
    for w in bundle["transcribe_words"]:
        for t in tokens(w["word"]):
            words.append({"norm": t, "start": w["start"], "end": w["end"]})
    return Song(
        words=words,
        offset=bundle["joint_stats"].get("offset_s") or 0.0,
        spans=[(c.start.total_seconds(), c.end.total_seconds()) for c in cues],
        main=[tokens(text) for text in cleaned],
    )


def chain(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The longest run of pairs increasing in both coordinates (sparse LCS)."""
    pairs = sorted(pairs, key=lambda p: (p[0], -p[1]))
    tails: list[int] = []  # index into pairs of the smallest tail j for each length
    back = [-1] * len(pairs)
    for k, (_, j) in enumerate(pairs):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if pairs[tails[mid]][1] < j:
                lo = mid + 1
            else:
                hi = mid
        back[k] = tails[lo - 1] if lo else -1
        if lo == len(tails):
            tails.append(k)
        else:
            tails[lo] = k
    out, k = [], tails[-1] if tails else -1
    while k >= 0:
        out.append(pairs[k])
        k = back[k]
    return out[::-1]


_LEAD_CACHE: dict[tuple, set[int]] = {}


def lead_words(song: Song, rule: Rule) -> set[int]:
    """Transcript words the song's own lines account for: one order-keeping match of every
    line's tokens to the whole transcript, a token only to words within ``band`` of its cue."""
    key = (id(song), rule.offset, rule.vocable, rule.band)
    if key in _LEAD_CACHE:
        return _LEAD_CACHE[key]
    shift = song.offset if rule.offset else 0.0
    mids = [(w["start"] + w["end"]) / 2 for w in song.words]
    pairs = []
    i = 0
    for k, (s0, s1) in enumerate(song.spans):
        lo, hi = s0 + shift - rule.band, s1 + shift + rule.band
        cand = [j for j, m in enumerate(mids) if lo <= m <= hi]
        for t in song.main[k]:
            pairs += [(i, j) for j in cand if same(t, song.words[j]["norm"], rule)]
            i += 1
    used = {j for _, j in chain(pairs)}
    _LEAD_CACHE[key] = used
    return used


def heard_share(row: dict, song: Song, rule: Rule) -> float:
    shift = song.offset if rule.offset else 0.0
    w0, w1 = row["start"] + shift - rule.pad, row["end"] + shift + rule.pad
    idx = [j for j, w in enumerate(song.words) if w["end"] > w0 and w["start"] < w1]
    window = [song.words[j]["norm"] for j in idx]
    if rule.consume == "global":
        lead = lead_words(song, rule)
        return _share(row, [song.words[j]["norm"] for j in idx if j not in lead], rule)
    if rule.consume == "none":
        others: list[str] = []
    elif rule.consume == "own":
        others = song.main[row["cue"]]
    else:
        others = [
            t
            for k, (s0, s1) in enumerate(song.spans)
            if k == row["cue"] or (s1 + shift > w0 and s0 + shift < w1)
            for t in song.main[k]
        ]
    used = {j for _, j in lcs_pairs(others, window, rule)}
    return _share(row, [t for j, t in enumerate(window) if j not in used], rule)


def _share(row: dict, rest: list[str], rule: Rule) -> float:
    """The share of the parenthetical found among the words no line accounts for."""
    paren = tokens(row["text"])
    if rule.share == "tokens":
        return len(lcs_pairs(paren, rest, rule)) / len(paren)
    types = list(dict.fromkeys(paren))
    return sum(any(same(t, r, rule) for r in rest) for t in types) / len(types)


# Step 4: the transcript-free comparison rule. A parenthetical reads like a direction when it
# is a quoted title or names a sound, music or an action. The list was written for this step
# from the kinds of direction the labels hold, so its A1 is in-sample.
DIRECTION_WORDS = set("""
    music musical instrumental interlude solo melody playing plays guitar piano drums bass
    violin flute saxophone congas organ cymbal synth strings beat tempo
    noise sound rumbling ringing rings clicks crackling crackles screeching screeches
    whooshing whoosh thudding tapping ticking humming hums whirring buzzing beeping roaring
    chirping squawking barking purring neighing trumpeting lapping popping shattering
    tinkling clatters scraping crashes crashing wailing typing
    laugh laughs laughing giggles chuckling groans groaning grunts sighs sneezes snorts
    snorting shrieks screams shouts shushing whispers whispering huffs clears throat
    vocalizing vocalese mouthing falsetto voice singing sings speaking chattering chanting
    cheering applauding clapping yelling banter indistinctly
    continues ends fades begins stops halts
    """.split())


def reads_like_direction(row: dict) -> bool:
    raw = row["text"].strip()
    if raw.startswith('"') or raw.startswith("“"):
        return True
    return any(t in DIRECTION_WORDS for t in tokens(raw))


def lyric_echo_kept(row: dict, song: Song) -> bool:
    """Extra transcript-free variant: kept when vocable-only or when a word of it is sung in
    the song's own lines."""
    paren = tokens(row["text"])
    if all(t in VOCABLES for t in paren):
        return True
    lyric = {t for line in song.main for t in line}
    return any(t in lyric for t in paren)


BASE = Rule("base")
VARIANTS = [
    BASE,
    replace(BASE, name="pad 0", pad=0.0),
    replace(BASE, name="pad 1.0", pad=1.0),
    replace(BASE, name="no offset", offset=False),
    replace(BASE, name="consume none", consume="none"),
    replace(BASE, name="consume own", consume="own"),
    replace(BASE, name="vocable exact", vocable="exact"),
    replace(BASE, name="tokens>=0.5", share="tokens"),
    replace(BASE, name="types all", min_share=1.0),
    replace(BASE, name="tokens all", share="tokens", min_share=1.0),
    replace(BASE, name="pad 1.0 none", consume="none", pad=1.0),
    replace(BASE, name="ceiling: none, pad 1.5", consume="none", pad=1.5),
    replace(BASE, name="pad 3.0 none", consume="none", pad=3.0),
    replace(BASE, name="pad 5.0 none", consume="none", pad=5.0),
]
GLOBAL = replace(BASE, name="G", consume="global")
VARIANTS += [
    GLOBAL,
    replace(GLOBAL, name="G pad 0", pad=0.0),
    replace(GLOBAL, name="G pad 1.0", pad=1.0),
    replace(GLOBAL, name="G band 0.5", band=0.5),
    replace(GLOBAL, name="G band 2.0", band=2.0),
    replace(GLOBAL, name="G no offset", offset=False),
    replace(GLOBAL, name="G vocable exact", vocable="exact"),
    replace(GLOBAL, name="G tokens>=0.5", share="tokens"),
    replace(GLOBAL, name="G types all", min_share=1.0),
    replace(GLOBAL, name="G share>0", min_share=0.01),
]


def is_vocable(row: dict) -> bool:
    return all(t in VOCABLES for t in tokens(row["text"]))


# The derived rules: a vocable-only parenthetical counts as heard (+vocables), and the plan's
# A2 consistency variant, a text kept once in a song is kept at every repeat there (+consist).
DERIVED_FROM = ["consume none", "pad 1.0 none", "ceiling: none, pad 1.5", "G"]


def consistent(rows: list[dict], name: str) -> None:
    kept_once = {(r["song"], r["label_key"]) for r in rows if r["kept"][name]}
    for row in rows:
        row["kept"][f"{name} +consist"] = (row["song"], row["label_key"]) in kept_once


# Step 4 tightened once (A1 rule: "tighten and re-measure"): v1 plus a word from each
# direction v1 let through. In-sample by construction.
DIRECTION_WORDS_V2 = DIRECTION_WORDS | set(
    """scream screams startles blowing libs calling cackles creak cracking pounds bells
    beaming scratch scratching sputtering springing running distorting whistling""".split()
)


def words_list_v2(row: dict) -> bool:
    raw = row["text"].strip()
    if raw.startswith('"') or raw.startswith("“"):
        return False
    return not any(t in DIRECTION_WORDS_V2 for t in tokens(raw))


def main(lib: Path, out: Path) -> None:
    rows = json.loads((out / "inventory.json").read_text())
    labels = json.loads((out / "labels.json").read_text())
    songs = {s["key"]: s for s in json.loads((out / "songs.json").read_text())}
    loaded = {key: load_song(lib, songs[key]) for key in {r["song"] for r in rows}}
    for row in rows:
        song = loaded[row["song"]]
        row["label"] = labels[row["label_key"]]
        row["vocable"] = is_vocable(row)
        row["shares"] = {v.name: round(heard_share(row, song, v), 3) for v in VARIANTS}
        row["kept"] = {v.name: row["shares"][v.name] >= v.min_share for v in VARIANTS}
        row["kept"]["words list"] = not reads_like_direction(row)
        row["kept"]["lyric echo"] = lyric_echo_kept(row, song)
        row["kept"]["words list v2"] = words_list_v2(row)
    for name in DERIVED_FROM:
        for row in rows:
            row["kept"][f"{name} +vocables"] = row["kept"][name] or row["vocable"]
        for suffix in ("", " +vocables"):
            consistent(rows, name + suffix)
    (out / "heard.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]))
