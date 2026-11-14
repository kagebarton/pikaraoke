"""Phase 0 step 1: every parenthetical in the raw sheets of the library's cue songs.

Read-only over the library. From the worktree root:
    PYTHONPATH=. python plans/backing-vocal-lines/inventory.py ~/pikaraoke-songs plans/backing-vocal-lines/out
Writes inventory.json (one row per parenthetical) and songs.json (one row per cue song).
"""

import json
import re
import sys
from pathlib import Path

import srt

from pikaraoke.lib.genius_lyrics import _strip_markup
from pikaraoke.lib.srt_cues import clean_cue_texts

PAREN_RE = re.compile(r"\(([^)]*)\)")
ID_RE = re.compile(r"---([A-Za-z0-9_-]{11})$")
SHEET_SUFFIX = {"srt": ("subtitles", ".srt"), "lrclib_srt": ("lyrics", ".lrclib.srt")}


def song_key(stem: str) -> str:
    """The YouTube ID, or the stem for a movie song that has none."""
    match = ID_RE.search(stem)
    return match.group(1) if match else stem


def find_sheet(lib: Path, origin: str, stem: str, source_path: str) -> Path | None:
    folder, suffix = SHEET_SUFFIX[origin]
    key = song_key(stem)
    if key != stem:
        hits = [p for p in (lib / folder).iterdir() if p.name.endswith(f"---{key}{suffix}")]
    else:
        name = source_path.replace("\\", "/").rsplit("/", 1)[-1]
        hits = [p for p in (lib / folder).iterdir() if p.name == name]
    return hits[0] if len(hits) == 1 else None


def norm_key(text: str) -> str:
    """The label key: lower case, punctuation but apostrophes dropped, spaces collapsed."""
    text = text.lower().replace("’", "'")
    return " ".join(re.sub(r"[^\w' ]+", " ", text).split())


def main(lib: Path, out: Path) -> None:
    songs, rows = [], []
    for bundle_path in sorted((lib / "alignment_debug").glob("*.json")):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        lyrics = bundle["lyrics"]
        origin = lyrics.get("origin")
        if bundle["pipeline_decisions"].get("method_used") != "cue_align":
            continue
        stem = bundle["song_stem"]
        song = {"key": song_key(stem), "stem": stem, "origin": origin, "bundle": bundle_path.name}
        songs.append(song)
        if origin not in SHEET_SUFFIX:
            song["skipped"] = f"origin {origin} (custom sheet, Decision 4)"
            continue
        sheet = find_sheet(lib, origin, stem, lyrics["source_path"])
        if sheet is None:
            song["skipped"] = "sheet not found"
            continue
        cues = list(srt.parse(sheet.read_text(encoding="utf-8-sig")))
        cleaned = clean_cue_texts([c.content for c in cues])
        kept = [i for i, text in enumerate(cleaned) if text]
        song["sheet"] = str(sheet.relative_to(lib))
        song["lines_match_bundle"] = [cleaned[i] for i in kept] == lyrics["lines"]
        song["n_lines"] = len(kept)
        line_of = {cue: lid for lid, cue in enumerate(kept)}
        spans = [(c.start.total_seconds(), c.end.total_seconds()) for c in cues]
        for i, cue in enumerate(cues):
            markup = _strip_markup(cue.content)
            groups = PAREN_RE.findall(markup)
            if not groups:
                continue
            s0, s1 = spans[i]
            overlaps = [
                (line_of[j], round(min(s1, spans[j][1]) - max(s0, spans[j][0]), 3))
                for j in kept
                if j != i and min(s1, spans[j][1]) - max(s0, spans[j][0]) > 0
            ]
            paren_only = not cleaned[i]
            prev_line = max((line_of[j] for j in kept if j < i), default=None)
            next_line = min((line_of[j] for j in kept if j > i), default=None)
            for g, inner in enumerate(groups):
                text = " ".join(inner.split())
                if not text:
                    continue
                rows.append(
                    {
                        "song": song["key"],
                        "stem": stem,
                        "origin": origin,
                        "cue": i,
                        "group": g,
                        "text": text,
                        "label_key": norm_key(text),
                        "kind": "paren_only" if paren_only else "inline",
                        "line_id": None if paren_only else line_of[i],
                        "prev_line": prev_line,
                        "next_line": next_line,
                        "start": s0,
                        "end": s1,
                        "cue_text": " / ".join(cue.content.splitlines()),
                        "overlaps": overlaps,
                    }
                )
    out.mkdir(parents=True, exist_ok=True)
    (out / "songs.json").write_text(json.dumps(songs, indent=1, ensure_ascii=False))
    (out / "inventory.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]))
