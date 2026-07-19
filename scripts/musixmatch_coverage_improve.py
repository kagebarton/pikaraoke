#!/usr/bin/env python3
"""Reference-pick Musixmatch/NetEase coverage improvement over the corpus.

Sequel to ``plans/musixmatch-coverage-probe.md`` (part a), implementing
``plans/musixmatch-coverage-improvement.md`` (part a2). Part (a) found that
``syncedlyrics.search()`` silently picks one Musixmatch candidate by
title/artist *text similarity* against the query, which produced real
wrong-song hits even when a better-content candidate was sitting in the same
result list. This script bypasses that pick: it pulls Musixmatch's raw
``track.search`` candidates directly and scores each by how well its lyrics
map onto our sheet (``pikaraoke.lib.lrclib.map_lines_to_cues``) -- the same
reference-free selection ``lrclib.select_candidate`` already uses for
LRCLIB -- with a title-only query retry and a NetEase line-level fallback
for songs that still come up empty.

Scoped to the 26 corpus songs part (a) did *not* already resolve to a
confident word-level hit (``BASELINE`` below); the other 7 are skipped on
purpose (see the plan's "Baseline" section).

``--save-bodies`` (Phase 2a of ``plans/timing-source-pillars.md``) is a
second, independent mode: re-runs ``pikaraoke.lib.timing_fetch`` (the E0
production pillar -- this script no longer carries its own writer, just the
batch loop + politeness) over the 17 word-level-confident corpus songs and
persists each to the real production sidecar
(``lyrics/<stem>.timing.json`` beside the song), so Phase 2b's probe and the
future production path share one on-disk fixture set.

Run from the repo root::

    python scripts/musixmatch_coverage_improve.py
    python scripts/musixmatch_coverage_improve.py --save-bodies

``syncedlyrics`` is a runtime dependency (``pikaraoke/lib/timing_fetch.py``).
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import re
import sys
import time
from pathlib import Path

# Allow running as ``python scripts/musixmatch_coverage_improve.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import syncedlyrics  # noqa: E402
from syncedlyrics.providers import Musixmatch  # noqa: E402
from syncedlyrics.utils import format_time, get_cache_path  # noqa: E402

from pikaraoke.lib import timing_fetch  # noqa: E402
from pikaraoke.lib.lrclib import (  # noqa: E402
    clean_key,
    map_lines_to_cues,
    parse_lrc_lines,
)

logging.getLogger("syncedlyrics").setLevel(logging.WARNING)

WORD_TAG = re.compile(r"<\d+:\d{2}(?:\.\d+)?>")
SONGS_ROOT = Path("/home/ken/pikaraoke-songs")
BUNDLES_GLOB = "/home/ken/pikaraoke-songs/alignment_debug/*.json"
TOKEN_PATH = get_cache_path("syncedlyrics", False) / "musixmatch_token.json"
MEDIA_EXTS = (".mp4", ".webm", ".mkv")

# The 17 word-level-confident (>= WRONG_SONG_MAP_RATE) corpus songs, keyed by
# YouTube id (stable and glob-safe -- several of these filenames carry
# non-breaking spaces/soft hyphens that make literal-string matching
# fragile). Values: (label, recorded map_rate from the probe/improvement
# plans, control -- a known wrong-song fixture Phase 2b's gate test needs,
# exempt from the regression assert).
SAVE_BODIES_SONGS: dict[str, tuple[str, float, bool]] = {
    # Part (a)'s 7 already-confident rows (plans/musixmatch-coverage-probe.md).
    "22QYya-LGDY": ("Popular", 0.63, False),
    "otxTf5hZ0Yw": ("Belle", 0.86, False),
    "wGyh_53ecgg": ("Best Part of Me", 0.87, False),
    "Orq_75kFi8I": ("Bloodstream", 0.50, False),
    "9ThO76peOw0": ("Colors of the Wind", 0.95, False),
    "UJtB55MaoD0": ("Domino", 0.67, False),
    "TSVHoHyErBQ": ("Rock Your Body", 0.98, False),
    # Part (a2)'s 8 new word-level winners (plans/musixmatch-coverage-improvement.md).
    "fjOeJssZX_Q": ("Free", 0.805, False),
    "1OwfYjemrYw": ("More Than That", 0.923, False),
    "YVVTZgwYwVo": ("Let It Go", 0.702, False),
    "SXKlJuO07eM": ("Part of Your World", 0.704, False),
    "FQ3slUz7Jo8": ("Like I Love You", 0.869, False),
    "uuZE_IRwLNI": ("Mirrors", 0.883, False),
    "UvyHuse6buY": ("Seasons of Love", 0.912, False),
    "25QyCxVkXwQ": ("Can You Feel the Love Tonight", 0.875, False),
    # 2 negative controls (known wrong-song, both below the confidence bar).
    "WVe80iZtlYU": ("Incomplete", 0.296, True),
    "je0roKRn3nY": ("Selfish", 0.38, True),
}

# Pacing that survived a full 33-song part-(a) run and this plan's 4-song
# prototype without a persistent lockout -- see the plan's Robustness
# section before tightening any of these.
CALL_SLEEP_S = 2.5
SONG_SLEEP_S = 4.0
BACKOFF_SLEEP_S = 20.0

# Wrong-song cutoff, matching part (a): below this a hit isn't "covered".
WRONG_SONG_MAP_RATE = 0.5

# {filename: (segment, old_query, old_kind, old_map_rate)} -- part (a)'s
# per-song table for every row that did NOT already reach a confident (>=
# WRONG_SONG_MAP_RATE) word-level hit. Captured verbatim from
# plans/musixmatch-coverage-probe.md so this script doesn't depend on
# re-parsing markdown. The 7 skipped rows (already word >= 0.5): Popular,
# Belle, Best Part of Me, Bloodstream, Colors of the Wind, Domino, Rock Your
# Body.
BASELINE: dict[str, tuple[str, str, str, float]] = {
    "#OutOfOz - 'For Good' Performed by Kristin Chenoweth and Idina Menzel _ WICKED the Musical---TZ0pXUb5jVU.json": (
        "srt",
        "'For Good' Performed by Kristin Chenoweth and Idina Menzel _ WICKED the Musical #OutOfOz",
        "none",
        0.0,
    ),
    "'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM.json": (
        "genius/lrclib-miss",
        "Defying Gravity Kristin Chenoweth",
        "line",
        0.685,
    ),
    "'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q.json": (
        "genius/lrclib-hit",
        "Free RUMI",
        "none",
        0.0,
    ),
    "Ariana Grande, John Legend - Beauty and the Beast (From Beauty and the Beast - Official Video)---axySrE0Kg6k.json": (
        "srt",
        "Beauty and the Beast Ariana Grande, John Legend",
        "none",
        0.0,
    ),
    "Backstreet Boys - Incomplete (Official HD Video)---WVe80iZtlYU.json": (
        "srt",
        "Incomplete Backstreet Boys",
        "none",
        0.0,
    ),
    "Backstreet Boys - More Than That---1OwfYjemrYw.json": (
        "srt",
        "More Than That Backstreet Boys",
        "none",
        0.0,
    ),
    "Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjABn8.json": (
        "genius/lrclib-miss",
        "Be Our Guest Angela Lansbury",
        "line",
        0.688,
    ),
    "Ed Sheeran - Happier (Official Music Video)---iWZmdoY1aTE.json": (
        "srt",
        "Happier Ed Sheeran",
        "none",
        0.0,
    ),
    "HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA.json": (
        "genius/lrclib-hit",
        "What It Sounds Like HUNTR/X",
        "none",
        0.0,
    ),
    "Idina Menzel - Let It Go (from Frozen) (Official Video)---YVVTZgwYwVo.json": (
        "srt",
        "Let It Go Idina Menzel",
        "none",
        0.0,
    ),
    "Jodi Benson - Part of Your World (From 'The Little Mermaid')---SXKlJuO07eM.json": (
        "srt",
        "Part of Your World Jodi Benson",
        "word",
        0.407,
    ),
    "Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY.json": (
        "genius/lrclib-hit",
        "In Summer Josh Gad",
        "none",
        0.0,
    ),
    "Justin Timberlake - Like I Love You (Official Video)---FQ3slUz7Jo8.json": (
        "srt",
        "Like I Love You Justin Timberlake",
        "none",
        0.0,
    ),
    "Justin Timberlake - Mirrors (Official Video)---uuZE_IRwLNI.json": (
        "srt",
        "Mirrors Justin Timberlake",
        "none",
        0.0,
    ),
    "Justin Timberlake - Selfish (Official Video)---je0roKRn3nY.json": (
        "srt",
        "Selfish Justin Timberlake",
        "word",
        0.38,
    ),
    "Mena Massoud, Naomi Scott - A Whole New World (from Aladdin) (Official Video)---eitDnP0_83k.json": (
        "srt",
        "A Whole New World Mena Massoud, Naomi Scott",
        "none",
        0.0,
    ),
    "Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY.json": (
        "genius/lrclib-miss",
        "I’ll Make a Man Out of You Donny Osmond",
        "line",
        0.66,
    ),
    "NSYNC - Bye Bye Bye (Official Video)---Eo-KmOd3i7s.json": (
        "srt",
        "Bye Bye Bye NSYNC",
        "none",
        0.0,
    ),
    "NSYNC - Paradise.json": (
        "genius/lrclib-miss",
        "Paradise Justin Timberlake",
        "line",
        0.0,
    ),
    "Naomi Scott - Speechless (from Aladdin) (Official Video)---mw5VIEIvuMI.json": (
        "srt",
        "Speechless Naomi Scott",
        "none",
        0.0,
    ),
    "Seasons of Love (HD)---UvyHuse6buY.json": (
        "genius/lrclib-miss",
        "Seasons of Love Cast of the Motion Picture ‘Rent’",
        "word",
        0.088,
    ),
    "The Lion King - Can You Feel The Love Tonight---25QyCxVkXwQ.json": (
        "srt",
        "Can You Feel The Love Tonight The Lion King",
        "none",
        0.0,
    ),
    "The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fwLxDUQBdEg.json": (
        "genius/lrclib-miss",
        "Hakuna Matata Nathan Lane",
        "none",
        0.0,
    ),
    "The Next Ten Minutes Lyrics---0j8kL24ph8U.json": (
        "genius/lrclib-hit",
        "The Next Ten Minutes Anna Kendrick",
        "line",
        0.93,
    ),
    "Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ.json": (
        "genius/lrclib-miss",
        "The Girl in the Bubble Ariana Grande",
        "none",
        0.0,
    ),
    "ZAYN, Zhavia Ward - A Whole New World (End Title) (From 'Aladdin')---rg_zwK_sSEY.json": (
        "srt",
        "A Whole New World ZAYN, Zhavia Ward",
        "none",
        0.0,
    ),
}


def _mm_get(client: Musixmatch, action: str, params: list[tuple]) -> dict | None:
    """One Musixmatch call, with a single 401-triggered backoff+retry (fresh
    token). Any other non-200 (404 = no content for this track, etc.) is a
    clean miss, not a throttle -- return ``None`` immediately rather than
    wasting a retry on it."""
    response = client._get(action, list(params))  # pylint: disable=protected-access
    code = response.json().get("message", {}).get("header", {}).get("status_code")
    if code == 401:
        print(f"    [{action} -> 401, backing off {BACKOFF_SLEEP_S}s + fresh token]")
        time.sleep(BACKOFF_SLEEP_S)
        TOKEN_PATH.unlink(missing_ok=True)
        client.token = None
        response = client._get(action, list(params))  # pylint: disable=protected-access
        code = response.json().get("message", {}).get("header", {}).get("status_code")
    return response.json() if code == 200 else None


def _candidate_lyrics(client: Musixmatch, track_id: int) -> tuple[str, str | None]:
    """(kind, body) for one Musixmatch candidate: richsync first, else
    line-level subtitle."""
    data = _mm_get(client, "track.richsync.get", [("track_id", track_id)])
    if data and data["message"]["body"].get("richsync"):
        richsync = json.loads(data["message"]["body"]["richsync"]["richsync_body"])
        lrc_text = ""
        for entry in richsync:
            lrc_text += f"[{format_time(entry['ts'])}] "
            for word in entry["l"]:
                stamp = format_time(float(entry["ts"]) + float(word["o"]))
                lrc_text += f"<{stamp}> {word['c']} "
            lrc_text += "\n"
        return "word", lrc_text
    time.sleep(CALL_SLEEP_S)
    data = _mm_get(
        client, "track.subtitle.get", [("track_id", track_id), ("subtitle_format", "lrc")]
    )
    if data and data["message"]["body"]:
        return "line", data["message"]["body"]["subtitle"]["subtitle_body"]
    return "none", None


def _map_rate_for(body: str | None, sheet: list[str]) -> float:
    if not body:
        return 0.0
    clean = WORD_TAG.sub("", body)
    cue_texts, _ = parse_lrc_lines(clean)
    if not cue_texts or not sheet:
        return 0.0
    return len(map_lines_to_cues(sheet, cue_texts)) / len(sheet)


def _best_by_reference(
    client: Musixmatch, term: str, sheet: list[str], media_dur: float | None
) -> dict | None:
    """Best-scoring viable Musixmatch candidate for one query term, or
    ``None``. Skips instrumental/no-lyrics candidates without spending a
    lyrics-fetch call on them."""
    data = _mm_get(client, "track.search", [("q", term), ("page_size", "5"), ("page", "1")])
    if not data:
        return None
    best_key, best_row = None, None
    for entry in data["message"]["body"].get("track_list", []):
        track = entry["track"]
        if track.get("instrumental") or not (
            track.get("has_subtitles") or track.get("has_richsync")
        ):
            continue
        time.sleep(CALL_SLEEP_S)
        kind, body = _candidate_lyrics(client, track["track_id"])
        rate = _map_rate_for(body, sheet)
        length = track.get("track_length") or 0
        dur_key = -abs(length - media_dur) if media_dur else 0.0
        key = (rate, dur_key)
        row = {
            "track_id": track["track_id"],
            "track_name": track["track_name"],
            "artist_name": track["artist_name"],
            "kind": kind,
            "map_rate": round(rate, 3),
        }
        if best_key is None or key > best_key:
            best_key, best_row = key, row
    return best_row


def _reference_pick(
    client: Musixmatch, term_variants: list[str], sheet: list[str], media_dur: float | None
) -> dict | None:
    """Mechanisms 1+2: best candidate across every query variant tried
    (full title+artist, then title-only), tagged with which variant won."""
    overall = None
    for variant_index, term in enumerate(term_variants):
        time.sleep(CALL_SLEEP_S)
        row = _best_by_reference(client, term, sheet, media_dur)
        if row is None:
            continue
        row = {**row, "term": term, "variant": "full" if variant_index == 0 else "title-only"}
        if overall is None or row["map_rate"] > overall["map_rate"]:
            overall = row
    return overall


def _netease_fallback(term: str, sheet: list[str]) -> dict | None:
    """Mechanism 3: NetEase as a last resort. Verified this session
    (STEP 0, see the plan) that the installed ``syncedlyrics`` NetEase
    provider only ever returns line-level LRC -- it requests ``lv=1`` and
    never touches NetEase's word-level ``yrc`` field -- so this can only
    produce ``line`` or ``none``, never ``word``."""
    body = syncedlyrics.search(term, providers=["NetEase"], synced_only=True)
    if not body:
        return None
    rate = _map_rate_for(body, sheet)
    return {"kind": "line", "map_rate": round(rate, 3), "term": term, "variant": "netease"}


def _title_artist(bundle: dict) -> tuple[str, str]:
    """(title, artist) key: ``clean_key`` on the Genius title/artist for
    genius-origin bundles, else a filename-split fallback for srt-origin
    ones (part (a)'s derivation)."""
    lyrics = bundle["lyrics"]
    if lyrics.get("genius"):
        return clean_key(lyrics["genius"]["title"], lyrics["genius"]["artist"])
    stem = bundle["song_stem"].split("---")[0]
    artist_raw, sep, title_raw = stem.partition(" - ")
    return clean_key(title_raw, artist_raw) if sep else clean_key(stem, "")


def _term_variants(bundle: dict) -> list[str]:
    """[full "track artist", title-only] query variants -- kept separate so
    a title-only retry is possible."""
    track, artist = _title_artist(bundle)
    full = f"{track} {artist}".strip()
    return [full, track] if artist and track != full else [full]


def _classify(kind: str, rate: float) -> str:
    if kind == "none":
        return kind
    return f"{kind} (wrong-song?)" if rate < WRONG_SONG_MAP_RATE else kind


def process_song(client: Musixmatch, name: str, bundle: dict) -> dict:
    """Run the full per-song algorithm (Mechanism 1+2, then 3 if still
    empty/zero) and return one results-table row."""
    segment, old_query, old_kind, old_rate = BASELINE[name]
    sheet = bundle["lyrics"]["lines"]
    media_dur = bundle.get("media_duration_s")

    pick = _reference_pick(client, _term_variants(bundle), sheet, media_dur)
    source = pick["variant"] if pick else "none"

    if pick is None or pick["map_rate"] == 0.0:
        netease = _netease_fallback(old_query, sheet)
        if netease and (pick is None or netease["map_rate"] > pick["map_rate"]):
            pick, source = netease, "netease"

    new_kind = pick["kind"] if pick else "none"
    new_rate = pick["map_rate"] if pick else 0.0
    if pick is None:
        source = "unchanged"

    return {
        "song": name,
        "segment": segment,
        "old": _classify(old_kind, old_rate),
        "old_rate": old_rate,
        "new": _classify(new_kind, new_rate),
        "new_rate": new_rate,
        "source": source,
        "error": None,
    }


def _resolve_media(root: Path, stem: str) -> Path | None:
    for ext in MEDIA_EXTS:
        cand = root / f"{stem}{ext}"
        if cand.is_file():
            return cand
    return None


def save_bodies_main(songs_root: Path = SONGS_ROOT) -> int:
    """Phase 2a: persist the 17 word-level-confident songs' sidecars.

    Re-runs ``timing_fetch.reference_pick`` (via ``ensure_timing`` -- the
    disk-first/write path is identical to production, so this exercises the
    real pillar end to end) against each song's real media path, writing
    ``lyrics/<stem>.timing.json`` beside it -- the same file the pipeline
    would produce. Re-running this command is idempotent: an already-written
    sidecar (from a prior partial run) is reused, not re-fetched.

    Asserts the winner's ``map_rate`` has not regressed more than 0.05 below
    the recorded probe/improvement-plan value and that word-level songs
    stayed word-level (a control's low/no-confidence result is expected and
    exempt) -- either failure means the catalog shifted under us and stops
    the run rather than silently persisting a worse fixture set.
    """
    client = timing_fetch._get_client()  # pylint: disable=protected-access
    first_word_verified = False
    rows: list[dict] = []
    for i, (yt_id, (label, recorded_rate, control)) in enumerate(SAVE_BODIES_SONGS.items(), 1):
        matches = glob.glob(f"{songs_root}/alignment_debug/*---{yt_id}.json")
        if len(matches) != 1:
            print(f"WARNING: {label} ({yt_id}): expected 1 bundle, found {len(matches)} -- skip")
            continue
        bundle_path = Path(matches[0])
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        media = _resolve_media(songs_root, bundle_path.stem)
        if media is None:
            print(f"WARNING: {label} ({yt_id}): no media on disk -- skip")
            continue

        sidecar_path = media.parent / "lyrics" / f"{media.stem}.timing.json"
        already_fetched = sidecar_path.is_file()
        title, artist = _title_artist(bundle)
        sheet = bundle["lyrics"]["lines"]
        media_dur = bundle.get("media_duration_s")

        print(
            f"\n[{i}/{len(SAVE_BODIES_SONGS)}] {label} ({yt_id})"
            + (" [reused]" if already_fetched else "")
        )
        timing_fetch.ensure_timing(media, title, artist, sheet, media_dur)
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        new_rate, kind = sidecar["map_rate"], sidecar["kind"]

        if control:
            sidecar["control"] = True
            sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        else:
            if kind != "word":
                print(f"STOP: {label} ({yt_id}) kind downgraded word -> {kind!r} -- catalog shift?")
                return 1
            if new_rate < recorded_rate - 0.05:
                print(
                    f"STOP: {label} ({yt_id}) map_rate regressed: "
                    f"{new_rate:.3f} < {recorded_rate - 0.05:.3f} (recorded {recorded_rate})"
                )
                return 1

        delta = new_rate - recorded_rate
        print(
            f"    recorded={recorded_rate:.3f} new={new_rate:.3f} (delta {delta:+.3f}) "
            f"kind={kind} control={control} source={sidecar['source']}"
        )
        rows.append({"label": label, "yt_id": yt_id, "recorded": recorded_rate, "new": new_rate})

        if not first_word_verified and not already_fetched and kind == "word":
            entries = sidecar["body"] or []
            fields = sorted(entries[0]) if entries else []
            print(f"    first richsync body fields: {fields} (te present: {'te' in fields})")
            first_word_verified = True

        if not already_fetched:
            time.sleep(SONG_SLEEP_S)

    print("\n" + "=" * 80)
    print(f"{len(rows)}/{len(SAVE_BODIES_SONGS)} sidecars persisted, 0 STOPs")
    return 0


def main() -> int:
    client = Musixmatch(enhanced=False)  # one shared instance/token for the whole run
    bundle_by_name = {}
    for path in sorted(glob.glob(BUNDLES_GLOB)):
        name = Path(path).name
        if name in BASELINE:
            bundle_by_name[name] = json.loads(Path(path).read_text(encoding="utf-8"))

    missing = set(BASELINE) - set(bundle_by_name)
    if missing:
        print(f"WARNING: {len(missing)} baseline songs not found on disk: {sorted(missing)}")

    rows = []
    for i, (name, bundle) in enumerate(bundle_by_name.items(), 1):
        print(f"\n[{i}/{len(bundle_by_name)}] {name}")
        try:
            row = process_song(client, name, bundle)
        except Exception as e:  # noqa: BLE001 - harness, log and continue
            _, _, old_kind, old_rate = BASELINE[name]
            row = {
                "song": name,
                "segment": BASELINE[name][0],
                "old": _classify(old_kind, old_rate),
                "old_rate": old_rate,
                "new": "ERROR",
                "new_rate": 0.0,
                "source": "error",
                "error": str(e),
            }
        rows.append(row)
        print(
            f"    {row['old']} ({row['old_rate']}) -> {row['new']} ({row['new_rate']}) via {row['source']}"
        )
        time.sleep(SONG_SLEEP_S)

    print("\n" + "=" * 100)
    print(f"{'song':60s} {'old':>18s} {'new':>18s} {'source':>14s}")
    for row in rows:
        print(f"{row['song'][:60]:60s} {row['old']:>18s} {row['new']:>18s} {row['source']:>14s}")

    improved = sum(1 for r in rows if r["new_rate"] > r["old_rate"])
    regressed = sum(1 for r in rows if r["new_rate"] < r["old_rate"])
    print(
        f"\n{improved}/{len(rows)} improved, {regressed}/{len(rows)} regressed, "
        f"{len(rows) - improved - regressed}/{len(rows)} unchanged"
    )

    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--save-bodies",
        action="store_true",
        help="Phase 2a mode: persist the 17 word-level-confident songs' sidecars",
    )
    args = ap.parse_args()
    sys.exit(save_bodies_main() if args.save_bodies else main())
