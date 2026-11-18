"""GATE N judge (Opus, 2026-11-18): marks and tallies over Phase 0's saved artifacts.

Read-only over set_g.json / set_l.json; reruns nothing in probe.py. Also checks what (b) shows
on the names Browse actually reads: the current file names, with no channel.

Run: PYTHONPATH=. /home/ken/miniconda3/envs/pik/bin/python plans/browse-phone-phase0/judge.py
     (--write fills set_g.md's judge column from the marks below)
"""

import json
import sys
from pathlib import Path

import probe

from pikaraoke.lib import genius_query as gq
from pikaraoke.lib.song_manager import sanitize_filename

P0 = Path(__file__).parent

# Set G marks, per row (a, b, Genius preselect):
# R = right: top line is the singer, or the film/show/cast (Ken's own file-name convention);
#     bottom line starts with the song. Leftover YouTube text ("(Official Video)") is allowed.
# W = wrong: names a different song, or the song and the singer are in the wrong lines, or a
#     line holds no name (a year, "FULL SCREEN", a channel, a game, a tour), or one line showing
#     only the singer.
# 1 = one line, and it names the song.   - = no Genius preselect.
R, W, ONE, NA = "R", "W", "1", "-"
marks: dict[int, tuple[str, str, str]] = {}
notes: dict[int, str] = {}


def m(rows, a, b, g, note=""):
    for i in rows if isinstance(rows, (list, range)) else [rows]:
        marks[i] = (a, b, g)
        if note:
            notes[i] = note


m(1, ONE, ONE, NA)
m([2, 3, 4], R, R, R)
m(5, R, ONE, NA)
m(6, R, R, NA)
m(7, ONE, R, NA)
m(8, ONE, ONE, NA)
m(9, ONE, R, NA)
m(10, R, R, R)
m(11, ONE, ONE, NA)
m(12, ONE, ONE, R)
m(13, ONE, R, NA)
m(14, ONE, ONE, R)
m(15, R, R, R)
m(16, R, R, NA)
m(17, ONE, ONE, NA)
m(18, ONE, ONE, R)
m(19, R, R, R)
m(20, R, W, W, "b: singer as the song; Genius: a different song (ABBA's 'Mamma Mia'), known wrong")
m(21, ONE, R, W, "Genius: the Reprise, a different track, known wrong")
m(22, ONE, ONE, NA)
m([23, 25, 26, 27, 28], R, R, NA)
m(24, ONE, R, NA)
m(29, ONE, W, NA, "b: song and film swapped")
m([30, 31], W, W, NA, "a, b: song and film swapped")
m(32, ONE, ONE, NA)
m(33, R, ONE, NA)
m(34, ONE, ONE, NA)
m(35, ONE, ONE, R)
m(36, ONE, W, NA, "b: song and film swapped")
m(37, R, R, NA)
m([38, 40], R, R, R)
m(39, W, W, NA, "a, b: song on top, channel as the song")
m([41, 42, 44], W, W, NA, "a, b: song and film swapped")
m(43, ONE, W, NA, "b: a video game as the singer")
m(45, W, ONE, NA, "a: song on top, 'Audio)' as the song")
m(46, ONE, R, R)
m([47, 48], W, W, NA, "a, b: song and show swapped")
m(49, ONE, R, R)
m(50, ONE, ONE, NA)
m(51, R, R, R)
m(52, W, R, NA, "a: song on top")
m([53, 54, 56], ONE, ONE, NA)
m(55, ONE, R, NA)
m(57, ONE, R, NA)
m(58, W, W, NA, "a, b: song and show swapped")
m(59, R, R, NA)
m(60, ONE, ONE, NA)
m(range(61, 66), R, R, R)
m(66, ONE, ONE, R)
m(67, R, W, NA, "b: 'FULL SCREEN' as the song")
m(range(68, 73), R, R, R)
m(73, W, W, R, "a, b: song and singer swapped; Genius fixes it")
m(74, R, W, NA, "b: '1983' as the song")
m(75, ONE, ONE, R)
m(range(76, 82), R, R, R)
m(82, ONE, R, R)
m(83, R, R, NA)
m(range(84, 88), R, R, R)
m(88, ONE, R, R)
m(range(89, 95), R, R, R)
m(95, R, R, NA)
m(96, ONE, R, R)
m(97, R, R, R)
m(98, ONE, ONE, NA)
m([99, 100], ONE, R, R)
m(101, R, R, NA)
m(102, ONE, W, NA, "b: one line showing only the singer")
m(103, ONE, ONE, NA)
m(104, W, W, R, "a, b: a concert tour as the singer")
m([105, 107], ONE, ONE, R)
m(106, ONE, W, NA, "b: one line showing only the singer")
m(range(108, 111), R, R, R)
m(111, W, W, R, "a, b: song on top; Genius names the original band (Radiohead) for this cover")
m([112, 114], ONE, ONE, R)
m(113, R, R, R)
m(115, R, ONE, NA)
m(116, R, W, NA, "b: one line showing only the singer")
m(117, R, R, R)
m(118, W, W, NA, "a, b: song and singer swapped")

# Set L, wrong rows as read (row numbers of set_l.md). Every Genius label c1 or c2 would show
# was read and is right, so Genius adds none.
WRONG_L = {
    "a": {
        1: "song + video tag on top, film blurb as the song",
        82: "swapped",
        160: "swapped (Ken's file name is swapped too)",
        170: "song on top, 'Uncensored Version' as the song",
        186: "song and show swapped",
        188: "song and show swapped",
    },
    "b": {82: "swapped", 125: "song and film swapped", 191: "song and show swapped"},
}


def parse_label(name: str, use_film: bool = False) -> probe.Label:
    p = gq.parse(name)
    top = p.artist or (p.film if use_film else "")
    return (top, p.title) if top and p.title else ("", p.title or name)


def tally_g(g: list) -> None:
    assert sorted(marks) == list(range(1, len(g) + 1)), "every row marked once"
    tally: dict[str, dict[str, int]] = {}
    shown_wrong: dict[str, list[int]] = {"c1": [], "c2": []}
    for i, r in enumerate(g, 1):
        a, b, gm = marks[i]
        assert (gm == NA) == (r["genius"] is None), f"row {i}: genius mark vs preselect"
        rows = {"a": a, "b": b}
        for c in ("c1", "c2"):
            rows[f"{c}+a"] = gm if r[c] else a
            rows[f"{c}+b"] = gm if r[c] else b
            if r[c] and gm == W:
                shown_wrong[c].append(i)
        rows["a, b where a is one line"] = b if a == ONE else a
        for src, mark in rows.items():
            tally.setdefault(src, {R: 0, W: 0, ONE: 0})[mark] += 1
    print("SET G | source | right | wrong | one line |")
    for src, t in tally.items():
        print(f"| {src} | {t[R]} | {t[W]} | {t[ONE]} |")
    print("Genius-wrong labels shown (row):", shown_wrong)


def tally_l(rows: list) -> None:
    print("\nSET L | source | wrong | one line |")
    for src, key in (("a", "a"), ("b", "b"), ("c1+a", "c1_fb_a"), ("c1+b", "c1_fb_b"),
                     ("c2+a", "c2_fb_a"), ("c2+b", "c2_fb_b")):
        c, fb = (src[:2], src[-1]) if "+" in src else (None, src)
        wrong = sum(1 for i, r in enumerate(rows, 1) if i in WRONG_L[fb] and not (c and r[c]))
        print(f"| {src} | {wrong} | {sum(1 for r in rows if r[key][0] == '')} |")


def b_on_file_names(g: list) -> None:
    files = sorted(f for f in probe.SONGS.iterdir() if f.suffix == ".mp4")
    names = [probe.truth_name(f.name) for f in files]
    one = {"a": 0, "b": 0, "b, film as top line": 0, "a, b where a is one line": 0}
    for name in names:
        a = probe.split_name(name)
        labels = {
            "a": a,
            "b": parse_label(name),
            "b, film as top line": parse_label(name, use_film=True),
            "a, b where a is one line": a if a[0] else parse_label(name),
        }
        for src, label in labels.items():
            one[src] += label[0] == ""
    print(f"\nLIBRARY, current file names ({len(names)}), one-line rows:", one)
    print("SET G, (b) on the download-time file name with no channel, where it differs:")
    for i, r in enumerate(g, 1):
        label = parse_label(sanitize_filename(r["raw"]))
        if probe.fold_label(label) != probe.fold_label(tuple(r["b"])):
            print(f"  {i}: probe {probe.show(tuple(r['b']))}  |  no channel {probe.show(label)}")


def write_marks() -> None:
    lines = (P0 / "set_g.md").read_text().splitlines()
    for n, line in enumerate(lines):
        cell = line.split("|")[1].strip() if line.startswith("| ") else ""
        if cell.isdigit():
            i = int(cell)
            mark = "/".join(marks[i]) + (f": {notes[i]}" if i in notes else "")
            lines[n] = line.rsplit("|", 2)[0] + f"| {mark} |"
    (P0 / "set_g.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    g = json.loads((P0 / "set_g.json").read_text())
    tally_g(g)
    tally_l(json.loads((P0 / "set_l.json").read_text()))
    b_on_file_names(g)
    if "--write" in sys.argv:
        write_marks()
        print("\nwrote set_g.md judge column")
