"""Would LRCLIB's exact-length lookup find what the capped search misses? (read-only)"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import lrclib_probe as lp
from pikaraoke.lib import lrclib

tally, disk_tally = Counter(), Counter()
for r in lp.rows:
    sheet, dur = r.get("lines") or [], r.get("dur")
    params = lp.queries(r)["field"]
    recs = lp.cache.get(json.dumps(params, sort_keys=True, ensure_ascii=False))
    if not isinstance(recs, list) or not dur:
        continue
    synced = [x for x in recs if x.get("syncedLyrics")]
    disk = r.get("lrc") or {}
    listed = any(x.get("id") == disk.get("id") for x in synced)
    if disk.get("id") is not None:
        d = disk.get("duration")
        disk_tally[
            ("listed" if listed else "not listed", "capped" if len(recs) >= 20 else "under cap",
             "disk within 5s" if d and abs(d - dur) <= 5 else "disk >5s off")
        ] += 1
    near = [x for x in synced if abs(float(x.get("duration") or 0) - dur) <= 2]
    if near:
        tally["search already lists a record within 2s"] += 1
        continue
    key = "GET " + json.dumps({**params, "duration": round(dur)}, sort_keys=True, ensure_ascii=False)
    if key not in lp.cache:
        try:
            resp = requests.get("https://lrclib.net/api/get", params={**params, "duration": round(dur)},
                                headers={"User-Agent": lrclib.USER_AGENT}, timeout=40)
            lp.cache[key] = resp.json() if resp.status_code == 200 else {"status": resp.status_code}
        except (requests.RequestException, ValueError) as e:
            lp.cache[key] = {"status": str(e)}
        with lp.cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "records": lp.cache[key]}, ensure_ascii=False) + chr(10))
        time.sleep(0.3)
    got = lp.cache[key]
    if got.get("syncedLyrics"):
        texts, _ = lrclib.parse_lrc_lines(got["syncedLyrics"])
        rate = len(lrclib.map_lines_to_cues(sheet, texts)) / len(sheet) if sheet and texts else 0
        tally["exact-length lookup finds a synced record the search hid" + (" (maps >=60%)" if rate >= 0.6 else " (maps <60%)")] += 1
    elif got.get("id"):
        tally["exact-length lookup finds an unsynced record only"] += 1
    else:
        tally["no record at the video's length"] += 1
print(dict(tally))
print("match on disk vs field search:", {" / ".join(k): v for k, v in disk_tally.items()})
