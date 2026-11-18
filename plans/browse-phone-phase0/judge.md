# GATE N judge read (Opus, 2026-11-18)

Read-only over Phase 0's saved artifacts (`set_g.json`, `set_l.json`); `probe.py` was not rerun.
Marks, Set L wrong rows and every number below come from `judge.py` (run line in its docstring).
Set G per-row marks are in `set_g.md`'s judge column.

Rule for a wrong label: names a different song, or the song and the singer are in the wrong
lines, or a line holds no name (a year, "FULL SCREEN", a channel, a game, a tour), or a one-line
row that shows only the singer. A film, show or cast as the top line is right (Ken's own
convention in the library). Leftover YouTube text such as "(Official Video)" is not wrong.

## Set G (118 raw YouTube titles, 63 with a preselect)

| source | right | wrong | one line |
|---|---|---|---|
| a | 60 | 15 | 43 |
| b | 68 | 22 | 28 |
| c1+a | 68 | 15 | 35 |
| c1+b | 69 | 21 | 28 |
| c2+a | 61 | 14 | 43 |
| c2+b | 69 | 21 | 28 |
| a, b where a is one line | 74 | 20 | 24 |

Genius labels that are wrong and would show: c1 rows 20 (`ed1RIhS7lDA`, "Meryl Streep / Mamma
Mia") and 21 (`mSfH2AuhXfw`, "You Will Be Found (Reprise)"), the two known wrong preselects; c2
none. How c1 lets them through: the title check strips the brackets, so "(Reprise)" is not
compared; a film named in the title ("Mamma Mia!") satisfies the song-title check; a cast name
whose words all appear in the title counts as credited.

Genius fixes a/b rows only twice: row 73 (swapped, fixed by c1 and c2) and row 111 (swapped,
fixed by c1, but Genius names Radiohead for a Postmodern Jukebox cover; marked right, same song).

c1 over its fallback: one-line rows a 43 -> 35 (7 right, 1 wrong: row 21), b 28 -> 28.
c2 over its fallback: one-line rows a 43 -> 43, b 28 -> 28.

## Set L (205 of 249 library files with a raw title, 57 with a Genius match)

| source | wrong | one line |
|---|---|---|
| a | 6 | 41 |
| b | 3 | 25 |
| c1+a | 5 | 39 |
| c1+b | 3 | 25 |
| c2+a | 6 | 39 |
| c2+b | 3 | 25 |

Wrong rows (set_l.md numbering): a 1, 82, 160, 170, 186, 188; b 82, 125, 191. All 42 Genius
labels c1 would show (24 for c2) name the right song and singer; differences from the file name
are cosmetic (a duet's second singer dropped, "A-Lin (TWN)", curly quotes). c1 fixes a's row 1 and
turns a's one-line rows 80 and 85 into two lines; c2 the same two one-line rows; neither changes b.

The file count (249) and the Genius count (57) differ from the plan's 248 and 54; not chased.

## What (b) shows on the names Browse reads (not in Phase 0)

Browse renders from the file name and has no channel. Phase 0 ran (b) on the raw title with the
channel, which Browse does not have unless it is stored at download.

Library, current hand-made file names (249), one-line rows:

| source | one line |
|---|---|
| a | 17 |
| b | 85 |
| b, film as the top line when the parse finds no artist | 7 |
| a, b where a is one line | 9 |

(b) as `parse()` returns it files every film-named song ("Frozen (2013) - Let It Go", all of Rent,
The Last Five Years, Flight of the Conchords, KPop Demon Hunters) as one line, because the film is
read as a film, not an artist. Even with the film as the top line, (b) drops what Ken added to the
names: the year, "(Sing-Along)", "(Titanic, 1997)", the English title after a Chinese one, and
"(feat. ...)". "a, b where a is one line" leaves Ken's names as they are; of the 17 rows (a) can't
split, 7 get two right lines, 1 gets a swapped one ("Wicked _ What Is This Feeling"), 9 stay one
line.

Set G, (b) on the download-time file name with no channel, differs on 6 rows: 52 and 88 become
swapped, 91 loses "Jay-Z / Numb" ("Linkin Park / Encore"), 92 gains "M-V" in the top line, 5 and
115 keep "(1-10)".

## The GATE N rule, read

- c1 shows wrong labels, both known wrong preselects among them. It fails the first test.
- c2 shows no wrong Genius label, but saves no one-line rows over (b) in either set, and two of
  205 over (a) in Set L, none in Set G. It fails "clearly fewer one-line rows".
- So (c) does not earn Phase 2 under either check. Ken picks between (a) and (b).
