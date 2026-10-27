"""Per-character timings for one song and arm, and their two outputs: JSON and a karaoke .ass.

The .ass writer is the probe's own (not the app's), and every arm goes through the same
rules so that Ken compares the arms and not the renderer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sheet import Sheet

ARM_NAMES = ("W", "R", "H", "Hsk", "Hal")  # whisper, romanized, Mandarin / two Cantonese char-CTC
PRE_ROLL_S = 1.5  # a line appears this long before its first character
POST_ROLL_S = 0.5  # and stays this long after its last one
LAST_SWEEP_MIN_S = 0.2  # CTC arms time a character as a spike, too short to see a sweep
PLAY_W, PLAY_H = 1920, 1080
MAX_FONT = 64
ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_W}
PlayResY: {PLAY_H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Microsoft JhengHei,{MAX_FONT},&H0000E5FF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,60,60,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""  # fmt: skip


@dataclass
class Timing:
    start: float
    end: float
    # "shared": split evenly with the other characters of one whisper token;
    # "interpolated": no target of its own in the model, placed between its neighbours
    note: str | None = None


def track_record(
    sheet: Sheet, timings: list[Timing], *, arm: str, model: str, lang: str, run: dict
) -> dict:
    assert len(timings) == len(sheet.units)
    return {
        "video_id": sheet.video_id,
        "arm": arm,
        "model": model,
        "lang": lang,
        "run": run,
        "units": [
            {
                "text": u.text,
                "line": u.line,
                "kind": u.kind,
                "start": round(t.start, 3),
                "end": round(t.end, 3),
                **({"note": t.note} if t.note else {}),
            }
            for u, t in zip(sheet.units, timings)
        ],
    }


def write_json(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


def ass_time(t: float) -> str:
    cs = max(0, round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def font_size(line: str) -> int:
    """Largest size (up to MAX_FONT) at which the line fits the frame on one row."""
    em = sum(1.0 if ord(c) > 0x2E80 else 0.3 if c == " " else 0.55 for c in line)
    return min(MAX_FONT, int((PLAY_W - 160) / max(em, 1)))


def write_ass(path: Path, sheet: Sheet, timings: list[Timing]) -> None:
    """One event per sheet line; each character sweeps from its start to the next one's.

    The last character of a line sweeps from its start to its own end (at least
    LAST_SWEEP_MIN_S). Starts are kept non-decreasing so a stray arm cannot run time backwards.
    """
    spans: list[list[tuple[str, float, float]]] = []  # per line: (display text, start, sweep end)
    prev_start = 0.0
    for n, line in enumerate(sheet.lines):
        idx = [i for i, u in enumerate(sheet.units) if u.line == n]
        starts = []
        for i in idx:
            prev_start = max(prev_start, timings[i].start)
            starts.append(prev_start)
        row = []
        for k, i in enumerate(idx):
            u = sheet.units[i]
            if k + 1 < len(idx):
                stop = starts[k + 1]
            else:
                stop = max(timings[i].end, starts[k] + LAST_SWEEP_MIN_S)
            text = u.pre + u.text + (sheet.tails[n] if k + 1 == len(idx) else "")
            row.append((text, starts[k], stop))
        spans.append(row)

    events = []
    prev_end = 0.0
    for n, row in enumerate(spans):
        first, last = row[0][1], row[-1][2]
        end = last + POST_ROLL_S
        if n + 1 < len(spans):
            end = min(end, spans[n + 1][0][1])
        start = max(first - PRE_ROLL_S, prev_end)
        base = round(start * 100)
        parts = [f"{{\\fs{font_size(sheet.lines[n])}}}{{\\k{max(0, round(first * 100) - base)}}}"]
        for text, s, stop in row:
            parts.append(f"{{\\kf{max(0, round(stop * 100) - round(s * 100))}}}{text}")
        end = max(end, start)
        events.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Karaoke,,0,0,0,,{''.join(parts)}"
        )
        prev_end = end
    path.write_text(ASS_HEADER + "\n".join(events) + "\n", encoding="utf-8")
