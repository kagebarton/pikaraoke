Model: Claude Sonnet 5

# Musixmatch coverage probe (part a)

## Objective

Measure how much of the corpus Musixmatch covers via the `syncedlyrics`
package, and — critically — how much of it comes back as **word-level
(richsync)** vs **line-level only**. This is a *coverage/hit-rate* probe only.

**In scope (part a):** for each corpus song, does Musixmatch return synced
lyrics; is it line-level or word-level; and does the returned text actually
correspond to our lyric sheet (a wrong-song match is not coverage).

**Out of scope (part b, deferred):** comparing Musixmatch word timings against
the current stable-ts output for accuracy. Do **not** attempt any timing-quality
comparison here. Do **not** wire anything into the production pipeline.

## Why this probe

Musixmatch is the largest synced-lyric corpus in existence and the only large
source of human-authored **word-level** timing (its "richsync" format) reachable
for free. `syncedlyrics` wraps the app's token flow that exposes richsync. The
decision this informs: is Musixmatch a worthwhile third/fourth timing source —
especially for the songs where **LRCLIB found nothing** (the 10 ASR-only songs +
`NSYNC - Paradise`), which is exactly where a word-level source would help most.

Coverage is the gate. If Musixmatch richsync doesn't cover the LRCLIB-miss
segment, part (b) is moot. If it does, part (b) becomes worth running.

## Corpus

`/home/ken/pikaraoke-songs/alignment_debug/*.json` — **33 bundles**. Segment
them (derive programmatically, don't transcribe by hand):

- **17 genius-origin** — `lyrics.origin == "genius"`, clean `lyrics.genius`
  `{title, artist}`. Split further by LRCLIB status from
  [song-metadata-survey.md](song-metadata-survey.md):
  - **5 LRCLIB-hit**: Free, What It Sounds Like, Domino, In Summer,
    The Next Ten Minutes.
  - **12 LRCLIB-miss**: the other 12 genius bundles (the survey's 10 ASR songs +
    `NSYNC - Paradise` + `Seasons of Love`). **This is the money segment.**
- **16 srt-origin** — `lyrics.origin == "srt"`, **no** `lyrics.genius`. These
  already have gold manual SRT timing, so Musixmatch coverage here is
  informational. Metadata must be parsed from the filename (best-effort, lower
  confidence — flag it).

Every bundle, both origins, carries `lyrics.lines` (the lyric sheet) — use it for
the text-map check on all 33.

## Environment

- Install into the `pik` conda env: `/home/ken/miniconda3/envs/pik/bin/pip install syncedlyrics`.
- This is a **probe-only** dependency: do **not** add it to `requirements.txt`
  or `pyproject.toml`. (Fork maintenance: new product deps only when something
  ships.) Note in the results whether it needs uninstalling after.
- The probe imports repo helpers, so run it with the `pik` python.

## Query construction

Reuse `pikaraoke.lib.lrclib.clean_key` so the search key is derived the same way
LRCLIB's is (strips feature credits and trailing parentheticals):

- **genius-origin:** `title, artist = lyrics.genius["title"], lyrics.genius["artist"]`,
  then `clean_key(title, artist)`, query string `f"{track} {artist}"`.
- **srt-origin:** parse the bundle's `song_stem` (or filename): take the part
  before `---` (drops the YouTube id), split on the first ` - ` into
  `artist - title`; if there's no ` - `, use the whole cleaned string as the
  query. Run the artist/title through `clean_key` too. Mark these rows
  `metadata=title-parsed` so low-confidence keys are visible in the results.

## STEP 0 — verify the installed `syncedlyrics` API before writing the probe

`syncedlyrics` moves fast; do not trust a remembered signature. Inspect the
installed version first:

```
/home/ken/miniconda3/envs/pik/bin/python -c "import syncedlyrics, inspect; print(syncedlyrics.__version__); print(inspect.signature(syncedlyrics.search))"
```

Confirm three things and adapt the reference script to match:

1. The provider argument (expected `providers=["Musixmatch"]`) and the exact
   provider name string.
2. The word-level flag (expected `enhanced=True`, which returns **enhanced LRC**
   with inline `<mm:ss.xx>` word tags where richsync exists).
3. The synced-only behavior (older versions used `synced_only`, newer use
   `plain_only`) — we want synced results, never plain text.

If the API differs from the reference below, the *classification logic* (word
tags = richsync) is stable regardless of how the string is fetched; keep that and
adjust only the call.

## Classification

For each song, make two calls (small corpus, cost is fine — it disambiguates
"has line-level but no richsync" cleanly):

- `word_lrc = search(term, providers=["Musixmatch"], enhanced=True)`
- `line_lrc = search(term, providers=["Musixmatch"])`

Classify:

- **none** — both `None`.
- **word (richsync)** — `word_lrc` contains inline word tags:
  `re.search(r"<\d+:\d{2}(?:\.\d+)?>", word_lrc)`.
- **line only** — synced result exists but no inline word tags.

## Text-map check (reject wrong-song matches)

A returned LRC for the wrong recording is not coverage. Reuse the LRCLIB
selection methodology:

```
from pikaraoke.lib.lrclib import map_lines_to_cues, parse_lrc_lines
```

- Strip inline word tags before parsing so line text is clean:
  `clean = re.sub(r"<\d+:\d{2}(?:\.\d+)?>", "", lrc)`.
- `cue_texts, _ = parse_lrc_lines(clean)`.
- `map_rate = len(map_lines_to_cues(sheet, cue_texts)) / len(sheet)` where
  `sheet = bundle["lyrics"]["lines"]`.
- Prefer the richsync text for the map check when present, else the line-level
  text. Treat `map_rate < 0.5` as a **wrong-song / unusable** hit (report it, but
  don't count it as covered in the headline number).

## Robustness / politeness

- `time.sleep(1.5)` between songs (Musixmatch token flow rate-limits; 33 songs is
  ~1–2 min).
- Wrap each song in `try/except Exception`; record the error string in that row
  and continue — one failure must not abort the run.
- Quiet `syncedlyrics`'s logger (`logging.getLogger("syncedlyrics").setLevel(WARNING)`).

## Reference probe script

Write it to your scratchpad (temp — it does not belong in the repo). Adapt the
`search(...)` call per STEP 0. Skeleton:

```python
import glob, json, logging, re, time
from pathlib import Path
import syncedlyrics
from pikaraoke.lib.lrclib import clean_key, map_lines_to_cues, parse_lrc_lines

logging.getLogger("syncedlyrics").setLevel(logging.WARNING)
WORD_TAG = re.compile(r"<\d+:\d{2}(?:\.\d+)?>")
BUNDLES = "/home/ken/pikaraoke-songs/alignment_debug/*.json"

def query_for(d):
    ly = d["lyrics"]
    if ly.get("genius"):
        track, artist = clean_key(ly["genius"]["title"], ly["genius"]["artist"])
        return f"{track} {artist}", "genius"
    stem = d["song_stem"].split("---")[0]
    artist, _, title = stem.partition(" - ")
    track, artist = clean_key(title or artist, artist if title else "")
    return f"{track} {artist}".strip(), "title-parsed"

def mm(term, enhanced):
    try:
        return syncedlyrics.search(term, providers=["Musixmatch"], enhanced=enhanced)
    except Exception as e:                     # noqa: BLE001 - probe, log and continue
        return f"ERR:{e}"

rows = []
for f in sorted(glob.glob(BUNDLES)):
    d = json.load(open(f))
    sheet = d["lyrics"]["lines"]
    term, meta = query_for(d)
    word_lrc, line_lrc = mm(term, True), mm(term, False)
    body = word_lrc if (isinstance(word_lrc, str) and not word_lrc.startswith("ERR")) else line_lrc
    kind = "none"
    if isinstance(word_lrc, str) and WORD_TAG.search(word_lrc):
        kind = "word"
    elif isinstance(line_lrc, str) and line_lrc and not line_lrc.startswith("ERR"):
        kind = "line"
    map_rate = 0.0
    if isinstance(body, str) and body and not body.startswith("ERR"):
        cue_texts, _ = parse_lrc_lines(WORD_TAG.sub("", body))
        map_rate = len(map_lines_to_cues(sheet, cue_texts)) / len(sheet) if sheet else 0.0
    rows.append((Path(f).name, d["lyrics"]["origin"], meta, term, kind, round(map_rate, 2)))
    time.sleep(1.5)

for r in rows:
    print(r)
```

Extend the printing into the markdown table + summary below.

## Output — record in this file

Append a `## Results` section to this plan with:

1. **Per-song table**, sorted by segment:

   | Song | Segment | Metadata | Query | MM result | map-rate | Notes |
   |------|---------|----------|-------|-----------|----------|-------|

   `MM result` ∈ {word, line, none}. Flag any hit with `map-rate < 0.5` as
   `wrong-song?` in Notes. Segment ∈ {srt, genius/lrclib-hit, genius/lrclib-miss}.

2. **Summary counts** — the headline numbers:
   - Overall: word / line / none out of 33 (excluding map-rate<0.5 from covered).
   - **genius/lrclib-miss segment (the 12): word / line / none.** This is the
     verdict driver — does Musixmatch richsync cover what LRCLIB missed?
   - genius/lrclib-hit segment (the 5): does Musixmatch add word-level where
     LRCLIB only gave line-level?
   - srt segment (the 16): informational.

3. **One-paragraph verdict** on whether part (b) (timing-quality comparison) is
   worth running — i.e., is there a meaningful word-level-covered set that
   overlaps the songs where we currently lack good timing (the LRCLIB-miss /
   ASR-only songs).

## Success criteria

- All 33 bundles attempted; every row has a result or a recorded error.
- Word/line/none classification and map-rate present per song.
- Summary counts + the lrclib-miss breakdown + a go/no-go note for part (b).

## Non-goals (do not do these here)

- No timing-accuracy comparison vs stable-ts (that is part b).
- No production/pipeline wiring, no new product dependency, no edits to
  `lyric_align.py` / `lyrics_fetch.py` / `requirements.txt`.
- No NetEase / other providers unless the lrclib-miss segment comes back thin on
  Musixmatch — in which case a **single optional** extra column
  (`providers=["NetEase"]`, whose `yrc` format is also word-level) is a cheap
  add. Mark it clearly as a secondary probe, keep Musixmatch primary.

## Results

Ran 2026-07-18 against `syncedlyrics==1.0.1`. STEP 0 findings: `providers=["Musixmatch"]`
matches (case-insensitive on the provider class name); `enhanced=True` is
confirmed word-level (falls back silently to line-level LRC when a track has
no richsync, which is exactly the "has line but no richsync" case the
two-call design disambiguates); this version has **both** `plain_only` and
`synced_only` — used `synced_only=True` on every call so a plain-text-only
hit can never be misread as "line" coverage.

Operational note not anticipated by the plan: Musixmatch's token flow throttles
hard after a handful of requests in quick succession — the first attempt at
`time.sleep(1.5)` between songs got 401s on nearly every call from song 3
onward (a throttle, not real token expiry: the cached token still looked
unexpired locally). Fetching a fresh token per call made it worse by tripping
the token endpoint's own throttle too. Fix: paced calls further apart
(2.5s between the two calls in a song, 4s between songs) and added a
one-shot backoff (20s sleep + token-cache clear + retry) triggered only when
a logging hook on the `Musixmatch` logger actually observed a 401 — 6 of the
33 songs needed that retry, all succeeded on the second attempt, zero
unhandled errors. `syncedlyrics` also has an unrelated logging bug worth
flagging for anyone reusing this script: every provider instantiation
(one per `search()` call) calls `logging.getLogger("Musixmatch").addHandler(...)`
with no idempotency check, so console warnings reprint once per accumulated
handler — a growing-duplicate spam that has nothing to do with the actual
request count. Worked around by resetting that logger's handler list before
each call.

### Per-song table

| Song | Segment | Metadata | Query | MM result | map-rate | Notes |
|------|---------|----------|-------|-----------|----------|-------|
| Defying Gravity — Kristin Chenoweth | genius/lrclib-miss | genius | Defying Gravity Kristin Chenoweth | line | 0.69 | |
| Popular — Kristin Chenoweth | genius/lrclib-miss | genius | Popular Kristin Chenoweth | word | 0.63 | |
| Be Our Guest — Angela Lansbury | genius/lrclib-miss | genius | Be Our Guest Angela Lansbury | line | 0.69 | |
| Belle — Paige O'Hara | genius/lrclib-miss | genius | Belle Paige O'Hara | word | 0.86 | |
| Best Part of Me — Ed Sheeran | genius/lrclib-miss | genius | Best Part of Me Ed Sheeran | word | 0.87 | |
| Bloodstream — Ed Sheeran | genius/lrclib-miss | genius | Bloodstream Ed Sheeran | word | 0.50 | 74-line sheet, boundary case but a real match (checked) |
| I'll Make a Man Out of You — Donny Osmond | genius/lrclib-miss | genius | I'll Make a Man Out of You Donny Osmond | line | 0.66 | |
| Paradise — Justin Timberlake (NSYNC) | genius/lrclib-miss | genius | Paradise Justin Timberlake | line | 0.00 | wrong-song? |
| Colors of the Wind — Judy Kuhn | genius/lrclib-miss | genius | Colors of the Wind Judy Kuhn | word | 0.95 | |
| Seasons of Love — Cast of "Rent" | genius/lrclib-miss | genius | Seasons of Love Cast of the Motion Picture 'Rent' | word | 0.09 | wrong-song? |
| Hakuna Matata — Nathan Lane | genius/lrclib-miss | genius | Hakuna Matata Nathan Lane | none | 0.00 | matched track is a no-lyrics instrumental cover |
| The Girl in the Bubble — Ariana Grande | genius/lrclib-miss | genius | The Girl in the Bubble Ariana Grande | none | 0.00 | |
| Free — Rumi (HUNTR/X) | genius/lrclib-hit | genius | Free RUMI | none | 0.00 | |
| What It Sounds Like — HUNTR/X | genius/lrclib-hit | genius | What It Sounds Like HUNTR/X | none | 0.00 | |
| Domino — Jessie J | genius/lrclib-hit | genius | Domino Jessie J | word | 0.67 | upgrade over LRCLIB's line-level |
| In Summer — Josh Gad | genius/lrclib-hit | genius | In Summer Josh Gad | none | 0.00 | |
| The Next Ten Minutes — Anna Kendrick | genius/lrclib-hit | genius | The Next Ten Minutes Anna Kendrick | line | 0.93 | no upgrade (LRCLIB already line-level) |
| For Good — Kristin Chenoweth & Idina Menzel (#OutOfOz) | srt | title-parsed | 'For Good' Performed by... #OutOfOz | none | 0.00 | messy filename, not "Artist - Title"; garbled query |
| Beauty and the Beast — Ariana Grande, John Legend | srt | title-parsed | Beauty and the Beast Ariana Grande, John Legend | none | 0.00 | |
| Incomplete — Backstreet Boys | srt | title-parsed | Incomplete Backstreet Boys | none | 0.00 | |
| More Than That — Backstreet Boys | srt | title-parsed | More Than That Backstreet Boys | none | 0.00 | |
| Happier — Ed Sheeran | srt | title-parsed | Happier Ed Sheeran | none | 0.00 | |
| Let It Go — Idina Menzel | srt | title-parsed | Let It Go Idina Menzel | none | 0.00 | |
| Part of Your World — Jodi Benson | srt | title-parsed | Part of Your World Jodi Benson | word | 0.41 | wrong-song? |
| Like I Love You — Justin Timberlake | srt | title-parsed | Like I Love You Justin Timberlake | none | 0.00 | |
| Mirrors — Justin Timberlake | srt | title-parsed | Mirrors Justin Timberlake | none | 0.00 | |
| Rock Your Body — Justin Timberlake | srt | title-parsed | Rock Your Body Justin Timberlake | word | 0.98 | |
| Selfish — Justin Timberlake | srt | title-parsed | Selfish Justin Timberlake | word | 0.38 | wrong-song? |
| A Whole New World — Mena Massoud, Naomi Scott | srt | title-parsed | A Whole New World Mena Massoud, Naomi Scott | none | 0.00 | |
| Bye Bye Bye — NSYNC | srt | title-parsed | Bye Bye Bye NSYNC | none | 0.00 | |
| Speechless — Naomi Scott | srt | title-parsed | Speechless Naomi Scott | none | 0.00 | |
| Can You Feel the Love Tonight — The Lion King | srt | title-parsed | Can You Feel The Love Tonight The Lion King | none | 0.00 | |
| A Whole New World (End Title) — ZAYN, Zhavia Ward | srt | title-parsed | A Whole New World ZAYN, Zhavia Ward | none | 0.00 | |

All 33 bundles attempted, zero unrecovered errors (the 6 that hit a 401 all
succeeded on the built-in retry).

### Summary counts

Word/line/none, with map-rate<0.5 hits broken out as **wrong-song** and
excluded from the covered counts per the plan's rule:

| Segment | word | line | wrong-song (excluded) | none | n |
|---|---|---|---|---|---|
| Overall | 7 | 4 | 4 | 18 | 33 |
| **genius/lrclib-miss (the 12)** | **5** | **3** | 2 | 2 | 12 |
| genius/lrclib-hit (the 5) | 1 | 1 | 0 | 3 | 5 |
| srt (the 16, informational) | 1 | 0 | 2 | 13 | 16 |

NetEase secondary probe not run — the lrclib-miss segment came back
well-covered (8/12 real hits, 5/12 word-level), not thin, so the plan's
trigger condition for that optional column wasn't met.

### Verdict

**Go for part (b), scoped to the genius/lrclib-miss segment.** 8 of the 12
LRCLIB-miss songs return real, right-song Musixmatch coverage (map-rate
0.5–0.95), and 5 of those are word-level richsync — Popular, Belle, Best Part
of Me, Bloodstream, and Colors of the Wind — which is exactly the ASR-only
cohort where a word-level ground truth is currently unavailable and would be
most useful as a timing-quality reference against stable-ts. Of the original
10 ASR-only songs, only Hakuna Matata (matched track is a no-lyrics
instrumental cover on Musixmatch's side) and The Girl in the Bubble come back
with nothing; the other two lrclib-miss misses (NSYNC Paradise, Seasons of
Love) are wrong-song collisions with a more-famous same-titled track, not
real absence, and are excluded rather than counted against coverage. The
lrclib-hit segment is a minor secondary finding — Musixmatch upgrades exactly
one of five (Domino) from LRCLIB's line-level to word-level, not enough on
its own to change the E1 LRCLIB-fill picture. Recommended scope for part (b):
run the timing-quality comparison against the 5 confirmed word-level
lrclib-miss songs first; treat the 3 line-level ones (Defying Gravity, Be Our
Guest, I'll Make a Man Out of You) as lower-priority secondary candidates.

`syncedlyrics` was installed probe-only into `pik` and was **not** added to
`requirements.txt`/`pyproject.toml`; uninstalled after this probe per the
plan's environment note.
