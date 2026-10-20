"""Phase 0b aid: how closely each lyric candidate matches the whisper transcript of the stem.

For each pilot song, every distinct candidate text (and Ken's CONFIRMED sheet once
saved) is compared with the transcript from phase0b_transcribe.py. Both sides are
reduced to Han characters and converted to Simplified one character at a time, with
著/着 and 妳/你 folded, so spelling alone does not count against a candidate. Credit lines
(词：, 曲：, ...) are dropped from the candidate first. The overlap is the longest
common subsequence, so a section whisper missed lowers recall but does not shift
the rest. ``diff`` is how many characters a candidate differs from the best-scoring
one by. phase0b_diffs.txt lists, for the near-best candidates, each place they differ
from the best one, which variant the transcript contains, and the transcript segment
(start-end in the song) to listen to; a difference several candidates share is one
line. Raw numbers only: whisper mishears sung Chinese (homophones, Mandarin spellings
for Cantonese), so this narrows candidates and picks none.

Run: uv run --with opencc-python-reimplemented python scripts/zh_probe/phase0b_score.py
"""

from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

from opencc import OpenCC

sys.path.insert(0, str(Path(__file__).parent))

from corpus import PILOT, PROBE_ROOT, RAW_DIR, Song, candidate_texts, han_chars  # noqa: E402

PHASE0_DIR = PROBE_ROOT / "phase0"
T2S = OpenCC("t2s")
# OpenCC leaves these spelling variants alone; folding them keeps a candidate from
# being scored down for a spelling choice that sounds the same.
SAME_SOUND_VARIANTS = str.maketrans({"著": "着", "妳": "你"})
SHORTLIST_F1_GAP = 0.05  # candidates this close to the best get their differences listed
CONTEXT = 2  # characters of the best text kept around each difference
HUNK_SHOWN = 20
CREDIT_RE = re.compile(
    r"^\W*(作?[词詞曲]|编曲|編曲|填词|填詞|监制|監製|制作人?|製作人?|混音|录音|錄音|母带|母帶|"
    r"配唱|和声|和聲|企划|企劃|发行|發行|出品|OP|SP|Lyrics?|Music|Composer|Lyricist|Arranger|"
    r"Producer|Written by|Composed by)\s*[:：]",
    re.IGNORECASE,
)


def simplified(text: str) -> str:
    return "".join(T2S.convert(c) for c in han_chars(text)).translate(SAME_SOUND_VARIANTS)


def strip_credits(text: str) -> tuple[str, int]:
    kept = [line for line in text.splitlines() if not CREDIT_RE.match(line)]
    return "\n".join(kept), len(text.splitlines()) - len(kept)


def lcs_pairs(a: str, b: str) -> list[tuple[int, int]]:
    """Index pairs (in a, in b) of one longest common subsequence."""
    table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, ca in enumerate(a):
        for j, cb in enumerate(b):
            table[i + 1][j + 1] = (
                table[i][j] + 1 if ca == cb else max(table[i][j + 1], table[i + 1][j])
            )
    pairs, i, j = [], len(a), len(b)
    while i and j:
        if a[i - 1] == b[j - 1]:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif table[i - 1][j] >= table[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return pairs[::-1]


def transcript_chars(segments: list[dict]) -> tuple[str, list[int]]:
    """Simplified Han characters of the transcript, and the segment index each came from."""
    chars, segment_of = "", []
    for k, segment in enumerate(segments):
        piece = simplified(segment["text"])
        chars += piece
        segment_of += [k] * len(piece)
    return chars, segment_of


def mmss(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def diff_hunks(ref: str, other: str) -> tuple[int, list[dict]]:
    """Characters ``other`` differs from ``ref`` by, and each place they differ."""
    n_diff, hunks = 0, []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, ref, other, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        n_diff += max(i2 - i1, j2 - j1)
        hunks.append(
            {
                "i1": i1,
                "i2": i2,
                "before": ref[max(0, i1 - CONTEXT) : i1],
                "best": ref[i1:i2],
                "this": other[j1:j2],
                "after": ref[i2 : i2 + CONTEXT],
            }
        )
    return n_diff, hunks


def hunk_position(hunk: dict, anchors: list[tuple[int, int]]) -> int | None:
    """Transcript character index of a difference: the best text's own characters if
    whisper matched any, else the last matched character before the insertion point."""
    inside = [j for i, j in anchors if hunk["i1"] <= i < hunk["i2"]]
    before = [j for i, j in anchors if i < hunk["i1"]]
    return inside[0] if inside else (before[-1] if before else None)


def heard_near(hunk: dict, segment: int, heard: str, segment_of: list[int]) -> tuple[bool, bool]:
    """Whether each variant, with its context, is in the transcript within one segment
    either side of ``segment``. A phrase sung several times would otherwise match from
    a different place in the song."""
    nearby = "".join(c for c, k in zip(heard, segment_of) if abs(k - segment) <= 1)
    return (
        hunk["before"] + hunk["best"] + hunk["after"] in nearby,
        hunk["before"] + hunk["this"] + hunk["after"] in nearby,
    )


def labels(song: Song) -> dict[str, str]:
    """Candidate file name -> 'source id title / artist / album duration' from index.json."""
    rows = json.loads((RAW_DIR / song.video_id / "index.json").read_text(encoding="utf-8"))
    out = {}
    for row in rows:
        title = row.get("title") or row.get("trackName") or ""
        artist = row.get("artist") or row.get("artistName") or ""
        extra = " ".join(str(row[k]) for k in ("albumName", "duration") if row.get(k))
        label = f"{row['source']} {row.get('id', '')} {title} / {artist} {extra}".strip()
        for key in ("file", "synced_file"):
            if row.get(key):
                out[row[key]] = label
    return out


def score_candidates(song: Song, heard: str) -> tuple[list[dict], dict[str, str]]:
    """Score rows (best first) and each candidate's Simplified Han string."""
    names = labels(song)
    rows, simp = [], {}
    for name, text in candidate_texts(song).items():
        body, n_credit = strip_credits(text)
        chars = simp[name] = simplified(body)
        common = len(lcs_pairs(heard, chars))
        recall = common / len(heard) if heard else 0.0
        precision = common / len(chars) if chars else 0.0
        f1 = 2 * recall * precision / (recall + precision) if common else 0.0
        rows.append(
            {
                "text": name,
                "label": names.get(name, ""),
                "n_han": len(chars),
                "credit_lines_dropped": n_credit,
                "lcs": common,
                "recall": round(recall, 3),
                "precision": round(precision, 3),
                "f1": round(f1, 3),
            }
        )
    rows.sort(key=lambda r: r["f1"], reverse=True)
    return rows, simp


def diff_section(
    song: Song,
    rows: list[dict],
    simp: dict[str, str],
    record: dict,
    heard: str,
    segment_of: list[int],
) -> list[str]:
    """Differences of the near-best candidates from the best one, with where to listen."""
    best = rows[0]
    anchors = lcs_pairs(simp[best["text"]], heard)
    shortlist, merged = [], {}
    best["diff_chars_vs_best"] = 0
    for r in rows[1:]:
        r["diff_chars_vs_best"], hunks = diff_hunks(simp[best["text"]], simp[r["text"]])
        if r["f1"] < best["f1"] - SHORTLIST_F1_GAP:
            continue
        shortlist.append(f"{r['text']} ({r['diff_chars_vs_best']})")
        for h in hunks:
            key = (h["i1"], h["i2"], h["this"])
            merged.setdefault(key, {"hunk": h, "in": []})["in"].append(r["text"])
    lines = [
        f"\n#{song.num} {song.title} [{song.video_id}] reference={best['text']}",
        f" near-best, chars differing from reference: {', '.join(shortlist) or 'none'}",
    ]
    for entry in sorted(merged.values(), key=lambda e: e["hunk"]["i1"]):
        h = entry["hunk"]
        pos = hunk_position(h, anchors)
        where, near = "(not matched in transcript)", "n/a"
        if pos is not None:
            segment = segment_of[pos]
            span = record["segments"][segment]
            where = f"{mmss(span['start'])}-{mmss(span['end'])}"
            in_best, in_this = heard_near(h, segment, heard, segment_of)
            near = f"reference={in_best} other={in_this}"
        lines.append(
            f"  {where:>26}  {h['before']}[{h['best'][:HUNK_SHOWN]} | {h['this'][:HUNK_SHOWN]}]"
            f"{h['after']}   whisper wrote nearby: {near}   other in: {', '.join(entry['in'])}"
        )
    return lines


def main() -> None:
    result, diff_report = {}, []
    for song in PILOT:
        record = json.loads(
            (PHASE0_DIR / "transcripts" / f"{song.video_id}.json").read_text(encoding="utf-8")
        )
        heard, segment_of = transcript_chars(record["segments"])
        rows, simp = score_candidates(song, heard)
        diff_report.extend(diff_section(song, rows, simp, record, heard, segment_of))
        result[song.video_id] = {"transcript_han": len(heard), "candidates": rows}
        print(f"\n#{song.num} {song.title} [{song.video_id}] transcript_han={len(heard)}")
        print(
            f"  {'f1':>5} {'recall':>6} {'prec':>5} {'lcs':>4} {'han':>4} {'cred':>4} "
            f"{'diff':>4}  text"
        )
        for r in rows:
            print(
                f"  {r['f1']:5.3f} {r['recall']:6.3f} {r['precision']:5.3f} {r['lcs']:4d} "
                f"{r['n_han']:4d} {r['credit_lines_dropped']:4d} {r['diff_chars_vs_best']:4d}  "
                f"{r['text']}  {r['label']}"
            )
    (PHASE0_DIR / "phase0b_score.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (PHASE0_DIR / "phase0b_diffs.txt").write_text("\n".join(diff_report), encoding="utf-8")


if __name__ == "__main__":
    main()
