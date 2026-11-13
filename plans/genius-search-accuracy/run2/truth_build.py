"""Answer key for the second computer's library: who and what each file is (read-only).

The library mixes 11-08 curated names with files still under their YouTube title, so the
song identity comes from a parse of the file name plus the hand overrides below.
"""
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from pikaraoke.lib import lrclib

LIB = Path("/home/ken/shared-drives/D:/Shared/pikaraoke-songs")
HERE = Path(__file__).parent
ID_RE = re.compile(r"---([A-Za-z0-9_-]{11})$")
BRACKET = re.compile(r"\s*[(\[][^)\]]*[)\]]")
FILM_LEFT = re.compile(r"^(.*?)\s*\((\d{4})\)$")
TLI = "The Lonely Island"
SILK = "Silk Sonic Bruno Mars Anderson Paak"
LATIN = re.compile(r"^[\x00-\x7f\u00c0-\u024f]+$")
# id or stem -> artist, title, optional film/year/alts. kind is "film" when film is set and artist is None.
OVERRIDE = {
    "b87dBaL4qI0": dict(artist="Ariana Grande", title="Almost Is Never Enough"),
    "-cy_tDQPXHk": dict(artist=SILK, q="Silk Sonic", title="After Last Night"),
    "GG7fLOmlhYg": dict(artist=SILK, q="Silk Sonic", title="Smokin Out the Window"),
    "wIyNAsmGrl0": dict(artist=SILK, q="Silk Sonic", title="Leave the Door Open"),
    "CEw-7cMnBDY": dict(artist=SILK, q="Silk Sonic", title="Skate"),
    "YRpvIiz9G8A": dict(film="Encanto", year=2021, title="We Don't Talk About Bruno"),
    "lQlIhraqL7o": dict(artist=TLI, title="I Just Had Sex"),
    "GI6CfKcMhjY": dict(artist=TLI, title="Jack Sparrow"),
    "z5Otla5157c": dict(artist=TLI, title="YOLO"),
    "avaSdC0QOUM": dict(artist=TLI, title="I'm on a Boat"),
    "vpMI8Qu5fsc": dict(artist="Ingrid Michaelson", title="Be OK"),
    "qMxX-QOV9tI": dict(artist="Jessie J", title="Price Tag"),
    "3gOHvDP_vCs": dict(artist="Justin Timberlake", title="SexyBack"),
    "Cbo2n2MzxxE": dict(artist="Michelle Branch", title="All You Wanted"),
    "Uxb6RFh3BCw": dict(artist="Michelle Branch", title="Are You Happy Now?"),
    "D_dOXTpwV5s": dict(film="Moana", year=None, title="Along the Way"),
    "tESZ92ugf7g": dict(film="Camp Rock 3", year=None, title="One Beat Away"),
    "jQ-Pqxl1BlI": dict(film="Camp Rock 3", year=None, title="Play My Music"),
    "fO4BmrVjqjM": dict(film="Camp Rock 2", year=2010, title="It's On"),
    "1YiAzyCzZzw": dict(film="Pocahontas", year=1995, title="Savages"),
    "pXNd2V88d60": dict(film="Rent", year=2005, title="Over the Moon"),
    "nVW9QOIeqQg": dict(film="Frozen 2", year=2019, title="Some Things Never Change"),
    "DcbEr7Cd_Cc": dict(film="Rent", year=2005, title="Take Me or Leave Me"),
    "zi5Z6rNU9Hw": dict(film="Tangled", year=2010, title="I've Got a Dream"),
    "0qj67KE5VXI": dict(film="High School Musical", year=2006, title="Breaking Free"),
    "RTWhvp_OD6s": dict(film="Moana", year=2016, title="Where You Are"),
    "jniq78mKKcM": dict(film="Wicked", year=2024, title="Dancing Through Life"),
    "amgPXKrFZVg": dict(film="Wicked", year=2024, title="What Is This Feeling?"),
    "68LBPvFhMx0": dict(artist="The Lonely Island Unauthorized Bash Brothers Experience", q=TLI, title="Jose & Mark"),
    "hj4e709GYf4": dict(artist="The Lonely Island Unauthorized Bash Brothers Experience", q=TLI, title="Let's Bash"),
    "PodgxWsZw9s": dict(artist="NSYNC", title="Thinking of You", alts=["I Drive Myself Crazy"]),
    "tt2k8PGm-TI": dict(artist="ZAYN", title="Dusk Till Dawn"),
    "cPKfUWDmNbo": dict(artist="Twins", title="下一站天后"),
    "ocDo3ySyHSI": dict(artist="Jay Chou 周杰倫 周杰伦", title="千里之外", alts=["Far Away", "Faraway"]),
    "OR-0wptI_u0": dict(artist="Jay Chou 周杰倫 周杰伦", title="雙截棍", alts=["双截棍", "Nunchucks"]),
    "DYptgVvkVLQ": dict(artist="Jay Chou 周杰倫 周杰伦", title="晴天", alts=["Sunny Day"]),
    "RPWDeLqsN0g": dict(artist="Jay Chou 周杰倫 周杰伦", title="龍捲風", alts=["龙卷风", "Tornado"]),
    "7qeShSmmsNg": dict(artist="Eason Chan 陳奕迅 陈奕迅", title="富士山下"),
    "RIq7Tz9nYD8": dict(artist="Eason Chan 陳奕迅 陈奕迅", title="愛情轉移", alts=["爱情转移"]),
    "JM9rx_hN1Ko": dict(artist="Eason Chan 陳奕迅 陈奕迅", title="十年", alts=["Ten Years"]),
    "8NJVNkzhJM4": dict(artist="Eason Chan 陳奕迅 陈奕迅", title="明年今日"),
    "IgvDMB5fR-8": dict(artist="Teresa Teng 鄧麗君 邓丽君", title="月亮代表我的心"),
    "U_EgeFUTbW4": dict(artist="George Lam 林子祥", title="男兒當自強", alts=["男儿当自强"]),
    "CvKvXNiXQZc": dict(artist="Miriam Yeung 楊千嬅 杨千嬅", title="少女的祈禱", alts=["少女的祈祷"]),
    "tDw_ULjZWA8": dict(artist="Faye Wong 王菲", title="容易受傷的女人", alts=["容易受伤的女人"]),
    "UmTB6E5mU5w": dict(artist="Leslie Cheung 張國榮 张国荣", title="風繼續吹", alts=["风继续吹"]),
    "qu_FSptjRic": dict(artist="Beyond", title="海闊天空", alts=["海阔天空"]),
    "m4nu_F_9dWU": dict(artist="Sun Yan-Zi Stefanie Sun 孫燕姿 孙燕姿", q="Sun Yan-Zi", title="遇見", alts=["遇见"]),
    "jeRu6h4XbUU": dict(artist="A-Lin Lin", q="A-Lin", title="幸福在歌唱", alts=["Happiness Is Singing"]),
    "WMweEpGlu_U": dict(artist="BTS 방탄소년단", title="Butter"),
}

def alnum(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


yt = json.loads((HERE / "yt_meta.json").read_text(encoding="utf-8"))
rows, kinds = [], Counter()
for song in sorted(LIB.glob("*.mp4")):
    m = ID_RE.search(song.stem)
    vid = m.group(1) if m else None
    name = ID_RE.sub("", song.stem)
    left, sep, right = name.partition(" - ")
    film = FILM_LEFT.match(left) if sep else None
    ident = {"artist": None, "film": None, "year": None, "alts": []}
    if film:
        ident.update(film=film.group(1), year=int(film.group(2)), title=BRACKET.sub("", right).strip())
    else:
        ident.update(artist=BRACKET.sub("", left).strip(), title=BRACKET.sub("", right or left).strip())
    over = OVERRIDE.get(vid) or OVERRIDE.get(name)
    if over:
        ident.update(artist=None, film=None, year=None)
        ident.update(over)
    if ident["title"] == "I'm a Part of That":
        ident["alts"] = ["A Part of That"]
    ident["kind"] = "film" if ident["artist"] is None else "artist"
    # What a search would send as the artist: the Latin-script name, with the other script as an alternate.
    words = (ident["artist"] or "").split()
    latin = [w for w in words if LATIN.match(w)]
    other = [w for w in words if not LATIN.match(w)]
    ident["artist_q"] = ident.pop("q", None) or " ".join(latin) or (other[0] if other else None)
    ident["artist_alt"] = other[0] if other and latin else None
    row = {"file": song.name, "name": name, "id": vid, **ident, "curated": vid is None or alnum(name) != alnum(yt[vid]["title"])}
    if vid:
        row["yt_title"], row["channel"] = yt[vid]["title"], yt[vid]["channel"]
    bundle_path = LIB / "alignment_debug" / f"{song.stem}.json"
    if bundle_path.is_file():
        b = json.loads(bundle_path.read_text(encoding="utf-8"))
        ly = b.get("lyrics") or {}
        row.update(origin=ly.get("origin"), genius=ly.get("genius"), lines=ly.get("lines") or [], dur=b.get("media_duration_s"))
    else:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(song)],
                             capture_output=True, text=True, check=False)
        row.update(origin=None, genius=None, lines=[], dur=float(out.stdout.strip()) if out.stdout.strip() else None)
    lrc = lrclib.read_song_lrc(song)
    row["lrc_state"], row["lrc"] = lrc.state, (lrc.meta if lrc.state == "match" else None)
    kinds[row["kind"]] += 1
    rows.append(row)
(HERE / "truth.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
names = [{k: v for k, v in r.items() if k != "lines"} for r in rows]
(HERE / "truth_names.json").write_text(json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(rows), dict(kinds), "with id:", sum(1 for r in rows if r["id"]), "genius picks:", sum(1 for r in rows if r["genius"]),
      "lrc on disk:", sum(1 for r in rows if r["lrc"]), "no dur:", sum(1 for r in rows if not r["dur"]))
