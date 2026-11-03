"""Phase 0b: build the lyric-sheet worksheet page that a Chinese-reading friend fills in.

Per song, the candidate texts that phase0b_score.py ranks within SHORTLIST_F1_GAP of the best
against the whisper transcript become versions A, B, ... in file-name order (so no version looks
preferred). Every place the versions disagree becomes a spot: the wording each version has there
and a YouTube time taken from the transcript segment the place falls in. The page itself is
worksheet_template.html, which also warns when the wording a friend ticked is not in the sheet
text. Nothing here picks a text; the friend and Ken do.

Needs <PROBE_ROOT>/phase0/transcripts/<video_id>.json (phase0b_transcribe.py, GPU) for each song.
Saves, under --out: <tag>.html, <tag>_labels.json (which files make each version) and
<tag>_build.txt (candidate scores, cleaning counts and spot counts per song). Raw output only.

Run: PYTHONPATH=<opencc-python-reimplemented> python -P scripts/zh_probe/phase0b_worksheet.py
       --tag mandarin --songs 3,4,5,6,7,8 --out <dir>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from corpus import (  # noqa: E402
    LRC_STAMP_RE,
    PILOT,
    RAW_DIR,
    REST,
    Song,
    candidate_texts,
)
from phase0b_score import (  # noqa: E402
    CREDIT_RE,
    PHASE0_DIR,
    SAME_SOUND_VARIANTS,
    SHORTLIST_F1_GAP,
    T2S,
    labels,
    lcs_pairs,
    mmss,
    score_candidates,
    transcript_chars,
)

TEMPLATE = Path(__file__).parent / "worksheet_template.html"
CTX = 3  # normalized characters of context shown each side of a spot; also the merge distance
MAX_VERSIONS = 6
LEAD_IN_S = 3  # a play link starts this long before the transcript segment
MARK_MAX = 80  # a highlighted difference longer than this is shortened in the middle
HEADER_LINES = 4  # title and artist lines are looked for in this many leading lines
# Same ranges as the template's IS_HAN, so a wording is normalized the same way in both places.
HAN_RE = re.compile("[㐀-䶿一-鿿豈-﫿]")
ZERO_WIDTH_RE = re.compile("[​‌‍﻿]")
BRACKETED_RE = re.compile(r"^\s*[\[【][^\]】]*[\]】]\s*$")  # [ti:...] tags, [Verse], 【副歌】
INSTRUMENT_CREDIT_RE = re.compile(
    r"^\W*(吉他手?|[贝貝]斯|鼓|[键鍵][盘盤]|弦[乐樂]|和[声聲](?:编写|編寫)?|[统統][筹籌]|演唱|原唱|歌手|[专專][辑輯])" r"\s*[:：]"
)
NETEASE_CREDIT_RE = re.compile(r"^\s*[^\s:：]{1,12} : \S")  # "录音工程 : 杨瑞代"
SINGER_LABEL_RE = re.compile(r"^[A-Za-z]{1,10}\s*[:：]\s*(?=\S)")  # "Sa：站在大丸前"
COUNT_WORDS = "zero one two three four five six seven eight nine ten eleven twelve".split()
LANGUAGE = {"zh": "Mandarin", "yue": "Cantonese"}
# name on the page, artist line on the page
DISPLAY = {
    1: ("晴天", "周杰倫 Jay Chou"),
    2: ("龍捲風", "周杰倫 Jay Chou"),
    3: ("雙截棍", "周杰倫 Jay Chou"),
    4: ("千里之外", "周杰倫 Jay Chou & 費玉清"),
    5: ("月亮代表我的心", "鄧麗君 Teresa Teng"),
    6: ("遇見", "孫燕姿 Stefanie Sun"),
    7: ("十年", "陳奕迅 Eason Chan"),
    8: ("愛情轉移", "陳奕迅 Eason Chan"),
    9: ("明年今日", "陳奕迅 Eason Chan"),
    10: ("富士山下", "陳奕迅 Eason Chan"),
    11: ("海闊天空", "Beyond"),
    12: ("風繼續吹", "張國榮 Leslie Cheung"),
    13: ("少女的祈禱", "楊千嬅 Miriam Yeung"),
    14: ("容易受傷的女人 (粵語版)", "王菲 Faye Wong"),
    15: ("男兒當自強", "林子祥 George Lam"),
    16: ("下一站天后", "Twins"),
}


def fold(ch: str) -> str:
    """One Han character as Simplified, with the spelling variants that sound the same folded."""
    simplified = T2S.convert(ch)
    return (simplified if len(simplified) == 1 else ch).translate(SAME_SOUND_VARIANTS)


def normalize(text: str) -> tuple[str, list[int]]:
    """Han characters (folded) and Latin letters/digits (lowercase) of ``text``, and each one's
    index in ``text``. The template's ``norm`` does the same, so a wording matches whatever script,
    punctuation or line breaks the friend's text uses."""
    chars, index = [], []
    for i, ch in enumerate(text):
        if HAN_RE.match(ch):
            chars.append(fold(ch))
        elif ch.isascii() and ch.isalnum():
            chars.append(ch.lower())
        else:
            continue
        index.append(i)
    return "".join(chars), index


def header_names(song: Song) -> list[str]:
    """Normalized title and artist names, longest first, for spotting a title line."""
    names = {name for pair in song.keys for name in pair}
    names.update(song.title.replace("&", " ").split())
    return sorted({normalize(n)[0] for n in names} - {""}, key=len, reverse=True)


def is_header(line: str, names: list[str]) -> bool:
    rest = normalize(line)[0]
    for name in names:
        rest = rest.replace(name, "")
    return bool(normalize(line)[0]) and rest == ""


def clean_lyrics(song: Song, text: str, *, netease: bool) -> tuple[str, Counter]:
    """The lyric lines of a fetched text, and how many lines of each kind were dropped."""
    names = header_names(song)
    dropped: Counter = Counter()
    kept = []
    for raw in ZERO_WIDTH_RE.sub("", text).splitlines():
        line = raw.strip()
        if not line:
            continue
        if CREDIT_RE.match(line) or INSTRUMENT_CREDIT_RE.match(line):
            dropped["credit"] += 1
        elif netease and NETEASE_CREDIT_RE.match(line):
            dropped["netease_credit"] += 1
        elif BRACKETED_RE.match(line):
            dropped["tag_or_section"] += 1
        elif len(kept) < HEADER_LINES and is_header(line, names):
            dropped["title_or_artist"] += 1
        else:
            if SINGER_LABEL_RE.match(line) and HAN_RE.search(line):
                line = SINGER_LABEL_RE.sub("", line)
                dropped["singer_label_stripped"] += 1
            kept.append(line)
    return "\n".join(kept), dropped


def files_by_text(song: Song) -> dict[str, list[str]]:
    """candidate_texts key (first file of a text) -> every file carrying that same text."""
    folder = RAW_DIR / song.video_id
    paths = sorted(folder.glob("*.txt")) + sorted(folder.glob("netease_*.lrc"))
    groups: dict[str, list[str]] = {}
    first_of: dict[str, str] = {}
    for path in paths:
        if path.name == "sources.txt":
            continue
        key = re.sub(r"\s+", "", LRC_STAMP_RE.sub("", path.read_text(encoding="utf-8")))
        groups.setdefault(first_of.setdefault(key, path.name), []).append(path.name)
    return groups


def file_order(name: str) -> tuple[int, int]:
    source = ("genius", "lrclib", "netease").index(name.split("_")[0])
    return source, int(re.search(r"\d+", name)[0])


def pick_versions(song: Song, rows: list[dict], report: list[str]) -> list[dict]:
    """Near-best candidates as versions, labelled in file-name order; texts that are the same
    once cleaned (spaces aside) share a version. A Traditional and a Simplified copy stay apart,
    since the friend keeps the script of the version she starts from."""
    rows = [r for r in rows if r["text"] != "CONFIRMED" and r["n_han"] > 0]
    near = [r for r in rows if r["f1"] >= rows[0]["f1"] - SHORTLIST_F1_GAP][:MAX_VERSIONS]
    near.sort(key=lambda r: file_order(r["text"]))
    texts, files = candidate_texts(song), files_by_text(song)
    versions: dict[str, dict] = {}
    for r in near:
        text, dropped = clean_lyrics(
            song, texts[r["text"]], netease=r["text"].startswith("netease")
        )
        if not normalize(text)[0]:
            continue
        version = versions.setdefault(
            re.sub(r"\s+", "", text), {"text": text, "files": [], "scores": []}
        )
        version["files"] += files[r["text"]]
        version["scores"].append(r)
        report.append(f"  cleaned {r['text']}: dropped {dict(dropped) or 'nothing'}")
    out = []
    for letter, version in zip("ABCDEFGH", versions.values()):
        out.append({"label": letter, **version})
    return out


def project(ops: list, pos: int, *, end: bool) -> int:
    """The index in the other string that ``pos`` in the reference string lines up with. A region
    boundary always sits on an opcode edge, so only equal blocks and exact edges are needed."""
    for tag, i1, i2, j1, j2 in reversed(ops) if end else ops:
        if tag == "equal":
            if i1 <= pos <= i2:
                return j1 + pos - i1
        elif end and pos == i2:
            return j2
        elif not end and pos == i1:
            return j1
    raise ValueError(f"no opcode edge at {pos}")


def disagreement_regions(ref: str, others: dict[str, list]) -> list[tuple[int, int]]:
    """Spans of the reference where any version differs; spans within CTX of each other merge so
    that the context shown around a spot never holds another difference."""
    spans = sorted(
        (i1, i2) for ops in others.values() for tag, i1, i2, _, _ in ops if tag != "equal"
    )
    merged: list[list[int]] = []
    for a, b in spans:
        if merged and a - merged[-1][1] <= CTX:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def flat(text: str) -> str:
    """One line: line breaks become ' / ', runs of spaces collapse."""
    return re.sub(r" +", " ", re.sub(r"\s*\n\s*", " / ", text))


def occurrences_before(norm: str, needle: str, end: int) -> int:
    """How many times ``needle`` starts in ``norm`` before index ``end``."""
    count, pos = 0, norm.find(needle)
    while 0 <= pos < end:
        count += 1
        pos = norm.find(needle, pos + 1)
    return count


def snippet(text: str, index: list[int], norm: str, ja: int, jb: int) -> tuple[str, str, int]:
    """HTML of a version's own text around the normalized span [ja, jb), the difference marked
    (or an empty marker when this version has nothing there); the normalized context+wording the
    template looks for in the friend's text; and which occurrence of that string in the version
    this spot is, since a chorus repeats the same context."""
    c0, c1 = max(0, ja - CTX), min(len(norm), jb + CTX)

    def at(k: int) -> int:
        return index[k] if k < len(index) else len(text)

    before, mid, after = text[at(c0) : at(ja)], text[at(ja) : at(jb)], text[at(jb) : at(c1)]
    mid = flat(mid.strip())
    if len(mid) > MARK_MAX:
        mid = mid[: MARK_MAX // 2] + " … " + mid[-MARK_MAX // 2 :]
    mark = f'<mark class="diff">{escape(mid)}</mark>' if mid else '<mark class="gap"></mark>'
    html = escape(flat(before.lstrip())) + mark + escape(flat(after.rstrip()))
    chk = norm[c0:c1]
    return html, chk, occurrences_before(norm, chk, c0)


def is_spelling_only(groups: dict[str, list[str]], ref: str, a: int, b: int) -> bool:
    """No version has a Han character here and the difference touches a Latin letter on either
    side: a spelling of a sung syllable (Sol / So), which nobody can tell by ear. A syllable set
    between Chinese characters (yeah, oh no) is kept."""

    def latin(k: int) -> bool:
        return 0 <= k < len(ref) and ref[k].isascii() and ref[k].isalnum()

    return not any(HAN_RE.search(c) for c in groups) and (latin(a - 1) or latin(b))


def build_spots(versions: list[dict], ref_label: str, heard: str, segments: list[dict],
                segment_of: list[int]) -> list[dict]:  # fmt: skip
    norms = {v["label"]: normalize(v["text"]) for v in versions}
    texts = {v["label"]: v["text"] for v in versions}
    ref = norms[ref_label][0]
    ops = {
        label: SequenceMatcher(None, ref, norm, autojunk=False).get_opcodes()
        for label, (norm, _) in norms.items()
        if label != ref_label
    }
    han_before = [0]
    for ch in ref:
        han_before.append(han_before[-1] + bool(HAN_RE.match(ch)))
    anchors = lcs_pairs("".join(c for c in ref if HAN_RE.match(c)), heard)
    spots = []
    for a, b in disagreement_regions(ref, ops):
        groups: dict[str, list[str]] = {}
        spans = {}
        for label, (norm, _) in norms.items():
            if label == ref_label:
                spans[label] = (a, b)
            else:
                spans[label] = (project(ops[label], a, end=False), project(ops[label], b, end=True))
            ja, jb = spans[label]
            groups.setdefault(norm[ja:jb], []).append(label)
        if is_spelling_only(groups, ref, a, b):
            continue
        variants = []
        for members in sorted(groups.values()):
            first = members[0]
            html, chk, nth = snippet(texts[first], norms[first][1], norms[first][0], *spans[first])
            variants.append({"labels": members, "html": html, "chk": chk, "nth": nth})
        inside = [j for i, j in anchors if han_before[a] <= i < han_before[b]]
        before = [j for i, j in anchors if i < han_before[a]]
        pos = inside[0] if inside else (before[-1] if before else None)
        segment = segments[0] if pos is None else segments[segment_of[pos]]
        start, end = segment["start"], segment["end"]
        spots.append(
            {
                "at": mmss(start),
                "span": f"{mmss(start)}-{mmss(end)}",
                "t": max(0, int(start) - LEAD_IN_S),
                "variants": variants,
            }
        )
    return spots


def build_song(song: Song, report: list[str]) -> tuple[dict, dict[str, list[str]], set[str]]:
    record = json.loads(
        (PHASE0_DIR / "transcripts" / f"{song.video_id}.json").read_text(encoding="utf-8")
    )
    heard, segment_of = transcript_chars(record["segments"])
    rows, _ = score_candidates(song, heard)
    names = labels(song)
    report.append(f"\n#{song.num} {song.title} [{song.video_id}] transcript Han {len(heard)}")
    report.append(f"  {'f1':>5} {'recall':>6} {'prec':>5} {'han':>4}  text")
    for r in rows:
        report.append(
            f"  {r['f1']:5.3f} {r['recall']:6.3f} {r['precision']:5.3f} {r['n_han']:4d}  "
            f"{r['text']}  {names.get(r['text'], '')}"
        )
    versions = pick_versions(song, rows, report)
    best = max(versions, key=lambda v: max(s["f1"] for s in v["scores"]))
    spots = build_spots(versions, best["label"], heard, record["segments"], segment_of)
    name, artist = DISPLAY[song.num]
    report.append(
        f"  versions {len(versions)} (reference {best['label']}), spots {len(spots)}, "
        + "; ".join(
            f"{v['label']}={v['files'][0]} (+{len(v['files']) - 1} same text)" for v in versions
        )
    )
    data = {
        "id": song.video_id,
        "name": name,
        "artist": artist,
        "language": LANGUAGE[song.lang],
        "url": f"https://www.youtube.com/watch?v={song.video_id}",
        "versions": [{"label": v["label"], "text": v["text"]} for v in versions],
        "spots": spots,
    }
    chars = {ch for text in candidate_texts(song).values() for ch in text if HAN_RE.match(ch)}
    return data, {v["label"]: v["files"] for v in versions}, chars


def render_page(tag: str, songs: list[dict], chars: set[str]) -> str:
    languages = " and ".join(dict.fromkeys(s["language"] for s in songs))
    count_word = COUNT_WORDS[len(songs)]

    def dump(obj) -> str:  # "<" escaped so no string in the data can close the script tag
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")

    page = {
        "storeKey": f"lyric-sheet-check-{tag}-v2",
        "norm": {ch: fold(ch) for ch in sorted(chars) if fold(ch) != ch},
    }
    html = TEMPLATE.read_text(encoding="utf-8")
    for placeholder, value in (
        ("__TITLE__", f"{languages} Lyric Sheets"),
        (
            "__EYEBROW__",
            f"{count_word.capitalize()} {languages} songs to check against the recordings",
        ),
        ("__COUNT_WORD__", count_word),
        ("__SONGS__", dump(songs)),
        ("__PAGE__", dump(page)),
    ):
        html = html.replace(placeholder, value)
    return html


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--songs", required=True, help="song numbers, e.g. 3,4,5,6,7,8")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    wanted = args.songs.split(",")
    songs = [s for s in PILOT + REST if str(s.num) in wanted]
    missing = [
        s.video_id
        for s in songs
        if not (PHASE0_DIR / "transcripts" / f"{s.video_id}.json").exists()
    ]
    if missing:
        sys.exit(f"no transcript yet for {', '.join(missing)}: run phase0b_transcribe.py first")

    report: list[str] = []
    data, label_files, chars = [], {}, set()
    for song in songs:
        song_data, files, song_chars = build_song(song, report)
        data.append(song_data)
        label_files[song.video_id] = files
        chars |= song_chars
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.tag}.html").write_text(render_page(args.tag, data, chars), encoding="utf-8")
    (args.out / f"{args.tag}_labels.json").write_text(
        json.dumps(label_files, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (args.out / f"{args.tag}_build.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"\nwrote {args.tag}.html, {args.tag}_labels.json, {args.tag}_build.txt in {args.out}")


if __name__ == "__main__":
    main()
