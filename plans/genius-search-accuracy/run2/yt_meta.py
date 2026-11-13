"""YouTube title and channel for every library file with an ID, via public oEmbed (cached)."""
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

LIB = Path("/home/ken/shared-drives/D:/Shared/pikaraoke-songs")
OUT = Path(__file__).parent / "yt_meta.json"
ID_RE = re.compile(r"---([A-Za-z0-9_-]{11})\.mp4$")
meta = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
for p in sorted(LIB.glob("*.mp4")):
    m = ID_RE.search(p.name)
    if not m or m.group(1) in meta:
        continue
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={m.group(1)}&format=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            d = json.loads(resp.read().decode("utf-8"))
        meta[m.group(1)] = {"title": d["title"], "channel": d.get("author_name")}
    except (urllib.error.URLError, ValueError) as e:
        print("FAILED", m.group(1), e)
    time.sleep(0.2)
OUT.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(meta), "ids")
