"""Phase 0 of plans/browse-phone.md: where a Browse row's artist and song come from.

Offline. For every video it writes what each name source would put on a row:

  a   the raw title, as the file is named at download, split at the first " - "
  b   genius_query.parse() on the raw title and channel (artist from the parse, title as its song)
  c   the Genius match's names, only when they agree with the raw title; else a or b shows
        c1  agree = the match's primary artist is named in the title (genius_query._credited) and
            every word of the match's title is in the title
        c2  c1, and every content word of the title (junk words dropped) is also in the match's
            artist or title: no unexplained words are left over

Set G: gate_g.jsonl, the Genius match is the frozen preselect (63 of 118 have one).
Set L: library.jsonl joined by video id to the library on the share; truth is the current file
name; the Genius match is the bundle's ``lyrics.genius`` (alignment_debug/*.json).

Run: /home/ken/miniconda3/envs/pik/bin/python plans/browse-phone-phase0/probe.py
"""

import json
import re
from pathlib import Path

from pikaraoke.lib import genius_query as gq
from pikaraoke.lib.genius import GeniusHit
from pikaraoke.lib.song_manager import sanitize_filename

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tests/unit/data/genius_search"
SONGS = Path("/home/ken/shared-drives/D:/Shared/pikaraoke-songs")
OUT = Path(__file__).parent

Label = tuple[str, str]  # (top line, bottom line); top is "" for a one-line row


def split_name(name: str) -> Label:
    """Split at the first " - "; no usable split gives a one-line row."""
    artist, sep, song = name.partition(" - ")
    artist, song = artist.strip(), song.strip()
    if not sep or not artist or not song:
        return "", name.strip()
    return artist, song


def label_b(raw: str, channel: str) -> Label:
    parsed = gq.parse(raw, channel)
    if parsed.artist and parsed.title:
        return parsed.artist, parsed.title
    return "", parsed.title or raw


def _words(s: str) -> set[str]:
    return gq._word_set(s)


def agree_c1(name: str, g_title: str, g_artist: str) -> bool:
    hit = GeniusHit(id=0, title=g_title, artist=g_artist, primary_artist=g_artist)
    title_ok = bool(_words(g_title)) and (
        _words(g_title) <= _words(name)
        or gq._squash(gq._bare(g_title)) in gq._squash(name)
        or gq._squash(g_title) in gq._squash(name)
    )
    return title_ok and gq._credited(hit, name)


def agree_c2(name: str, g_title: str, g_artist_line: str, g_artist: str) -> bool:
    if not agree_c1(name, g_title, g_artist):
        return False
    content = _words(gq.JUNK.sub(" ", gq._flat(name)))
    return not (content - _words(g_title) - _words(g_artist_line) - _words(g_artist))


def fold_label(label: Label) -> Label:
    return gq._fold(label[0]), gq._fold(label[1])


def show(label: Label) -> str:
    top, bottom = label
    text = f"{top} / {bottom}" if top else f"(1 line) {bottom}"
    return text.replace("|", "\\|")


def row_labels(raw: str, channel: str, genius: dict | None) -> dict:
    """Every source's label for one video. ``genius`` has title, artist, artist_line."""
    name = sanitize_filename(raw)
    a, b = split_name(name), label_b(raw, channel)
    out: dict = {"a": a, "b": b, "genius": None, "c1": None, "c2": None}
    if genius:
        g: Label = (genius["artist"], genius["title"])
        out["genius"] = g
        out["c1"] = agree_c1(name, genius["title"], genius["artist"])
        out["c2"] = agree_c2(name, genius["title"], genius["artist_line"], genius["artist"])
        for key in ("c1", "c2"):
            out[f"{key}_fb_a"] = g if out[key] else a
            out[f"{key}_fb_b"] = g if out[key] else b
    else:
        for key in ("c1", "c2"):
            out[f"{key}_fb_a"], out[f"{key}_fb_b"] = a, b
    return out


def flag(value: bool | None) -> str:
    return "-" if value is None else ("Y" if value else "N")


def run_g() -> None:
    rows = [json.loads(line) for line in (DATA / "gate_g.jsonl").read_text().splitlines()]
    hits = {}
    for hit_list in json.loads((DATA / "gate_g_answers.json").read_text()).values():
        for h in hit_list:
            hits[h["id"]] = h
    records, lines = [], []
    for r in rows:
        pre = r["search_page"]["preselect"]
        h = hits[pre] if pre else None
        genius = (
            {
                "title": h["title"],
                "artist": h.get("primary_artist") or h["artist"],
                "artist_line": h["artist"],
            }
            if h
            else None
        )
        labels = row_labels(r["yt_title"], r["channel"], genius)
        records.append({"id": r["id"], "raw": r["yt_title"], "channel": r["channel"], **labels})
        lines.append(
            f"| {len(lines) + 1} | `{r['id']}` | {r['yt_title'].replace('|', chr(92) + '|')} | "
            f"{r['channel']} | {show(labels['a'])} | {show(labels['b'])} | "
            f"{show(labels['genius']) if genius else '-'} | {flag(labels['c1'])} | "
            f"{flag(labels['c2'])} | |"
        )
    header = (
        "| # | id | raw YouTube title | channel | a: file-name split | b: title parser | "
        "genius preselect (artist / title) | c1 | c2 | judge (right/wrong/one-line) |\n"
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    (OUT / "set_g.md").write_text(
        "# Set G: 118 raw YouTube titles\n\n"
        "c1 and c2: Y = the Genius names would show, N = they disagree with the title so a or b "
        "shows, - = no preselect. Definitions are in `probe.py`.\n\n"
        + header
        + "\n"
        + "\n".join(lines)
        + "\n"
    )
    (OUT / "set_g.json").write_text(json.dumps(records, ensure_ascii=False, indent=1))


def video_id(name: str) -> str | None:
    m = re.search(r"---([\w-]{11})\.mp4$", name) or re.search(r"\[([\w-]{11})\]\.mp4$", name)
    return m.group(1) if m else None


def truth_name(file: str) -> str:
    stem = file[: -len(".mp4")]
    return re.sub(r"(---[\w-]{11}|\s\[[\w-]{11}\])$", "", stem)


def bundle_genius(vid: str | None) -> dict | None:
    if not vid:
        return None
    for path in (SONGS / "alignment_debug").glob(f"*{vid}*.json"):
        genius = json.loads(path.read_text()).get("lyrics", {}).get("genius")
        if genius:
            return {
                "title": genius["title"],
                "artist": genius["artist"],
                "artist_line": genius["artist"],
            }
    return None


def run_l() -> None:
    raw_by_id = {
        r["id"]: r
        for r in map(json.loads, (DATA / "library.jsonl").read_text().splitlines())
    }
    files = sorted(f for f in SONGS.iterdir() if f.suffix == ".mp4")
    records, lines, no_raw = [], [], []
    for f in files:
        vid = video_id(f.name)
        truth = split_name(truth_name(f.name))
        r = raw_by_id.get(vid) if vid else None
        genius = bundle_genius(vid)
        if not r:
            no_raw.append((truth_name(f.name), genius))
            continue
        labels = row_labels(r["yt_title"], r["channel"], genius)
        same = {
            k: fold_label(labels[k]) == fold_label(truth)
            for k in ("a", "b", "c1_fb_a", "c2_fb_a")
        }
        same["genius"] = fold_label(labels["genius"]) == fold_label(truth) if genius else None
        records.append(
            {
                "id": vid,
                "raw": r["yt_title"],
                "channel": r["channel"],
                "truth": truth,
                **labels,
                "same_as_truth": same,
            }
        )
        marks = "/".join(
            flag(same[k]) for k in ("a", "b", "genius", "c1_fb_a", "c2_fb_a")
        )
        lines.append(
            f"| {len(lines) + 1} | `{vid}` | {r['yt_title'].replace('|', chr(92) + '|')} | "
            f"{show(truth)} | {show(labels['a'])} | {show(labels['b'])} | "
            f"{show(labels['genius']) if genius else '-'} | {flag(labels['c1'])} | "
            f"{flag(labels['c2'])} | {marks} |"
        )
    header = (
        "| # | id | raw YouTube title | truth (current file name) | a | b | "
        "genius (bundle) | c1 | c2 | same as truth: a/b/genius/c1/c2 |\n"
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    tail = [
        f"- {name}" + (f"  (genius: {show((g['artist'], g['title']))})" if g else "")
        for name, g in no_raw
    ]
    (OUT / "set_l.md").write_text(
        f"# Set L: the library, {len(files)} files\n\n"
        f"{len(records)} have a raw YouTube title (library.jsonl, joined by video id) and are "
        "compared below. Truth is the hand-made file name split at its first \" - \". "
        "\"Same as truth\" is a folded-text comparison of both lines (Y/N, - = no Genius "
        "match); c1 and c2 are scored with the file-name split (a) as their fallback. "
        "Not a verdict: the judge reads the rows.\n\n"
        + header
        + "\n"
        + "\n".join(lines)
        + f"\n\n## Files with no raw title ({len(no_raw)}), not compared\n\n"
        + "\n".join(tail)
        + "\n"
    )
    (OUT / "set_l.json").write_text(json.dumps(records, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    run_g()
    run_l()
