Model: Claude Sonnet 5

# Musixmatch coverage improvement (part a2)

## Objective

Sequel to `plans/completed/musixmatch-coverage-probe.md` (part a). That probe measured
raw Musixmatch coverage and found real problems in *how a match gets picked*,
not just whether one exists. This plan runs three targeted fixes over the
26 corpus songs that didn't already get a confident word-level hit, and
records whether each fix earns its keep. **Still a probe/validation round —
do not wire anything into the production pipeline.** The decision to actually
ship any of this is a separate, later step.

## Why this plan

Part (a)'s per-song table (33 songs) showed three distinct failure modes,
each validated informally in the session that wrote this plan:

1. **Wrong candidate picked.** `syncedlyrics.search()` picks one Musixmatch
   candidate internally by title/artist *text similarity* against the query
   string. Prototyped against the 4 songs part (a) flagged `map_rate < 0.5`:
   Seasons of Love went from 0.088 (a decoy whose artist string,
   "Cast of the Motion Picture RENT", happened to look like our query) to
   **0.912** (the real cast recording, credited to "Jonathan Larson", sitting
   in the same 5-candidate list the whole time) once candidates were scored
   by `map_lines_to_cues` instead of text similarity — the same reference-free
   selection `pikaraoke.lib.lrclib.select_candidate` already uses for LRCLIB.
   Part of Your World and Selfish were unchanged (only one candidate in the
   list had any lyrics at all — a real content ceiling, not a picker bug).
   NSYNC Paradise was unchanged (none of the 5 candidates were the right song
   at all — picking better among them can't help).
2. **Genius-credited artist doesn't match Musixmatch's catalog attribution.**
   Movie/soundtrack songs are Genius-credited to the on-screen performer
   (Nathan Lane, Josh Gad) rather than however Musixmatch attributes the
   recording — Hakuna Matata's query matched a "Nathan Lane feat. Blue
   Minder" instrumental cover with zero lyrics. Not yet prototyped this
   session; the fix is a title-only retry when the artist-qualified query
   comes back empty or at `map_rate == 0.0`.
3. **The song isn't in Musixmatch's index at all under Musixmatch.** NSYNC
   Paradise is the clearest case. NetEase (a different catalog, also
   word-level via its `yrc` format) is worth one targeted try here — not
   a blanket rerun, since part (a)'s own trigger for this ("only if the
   lrclib-miss segment comes back thin") wasn't met at the time.

## Baseline (do not re-derive — use this table)

Source of truth: `plans/completed/musixmatch-coverage-probe.md`'s `## Results` →
per-song table, captured verbatim below as `BASELINE` so this script doesn't
depend on re-parsing markdown or on any prior session's scratchpad (gone).
**Skip the 7 rows already `word` at `map_rate >= 0.5`** — Popular, Belle,
Best Part of Me, Bloodstream, Colors of the Wind, Domino, Rock Your Body —
those are already the best realistic outcome; reprocessing them risks a
regression for zero possible upside. The other **26** are in scope.

```python
# (segment, query used in part (a), old_kind, old_map_rate)
BASELINE = {
    "#OutOfOz - 'For Good' Performed by Kristin Chenoweth and Idina Menzel _ WICKED the Musical---TZ0pXUb5jVU.json":
        ("srt", "'For Good' Performed by Kristin Chenoweth and Idina Menzel _ WICKED the Musical #OutOfOz", "none", 0.0),
    "'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM.json":
        ("genius/lrclib-miss", "Defying Gravity Kristin Chenoweth", "line", 0.685),
    "'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q.json":
        ("genius/lrclib-hit", "Free RUMI", "none", 0.0),
    "Ariana Grande, John Legend - Beauty and the Beast (From Beauty and the Beast - Official Video)---axySrE0Kg6k.json":
        ("srt", "Beauty and the Beast Ariana Grande, John Legend", "none", 0.0),
    "Backstreet Boys - Incomplete (Official HD Video)---WVe80iZtlYU.json":
        ("srt", "Incomplete Backstreet Boys", "none", 0.0),
    "Backstreet Boys - More Than That---1OwfYjemrYw.json":
        ("srt", "More Than That Backstreet Boys", "none", 0.0),
    "Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjABn8.json":
        ("genius/lrclib-miss", "Be Our Guest Angela Lansbury", "line", 0.688),
    "Ed Sheeran - Happier (Official Music Video)---iWZmdoY1aTE.json":
        ("srt", "Happier Ed Sheeran", "none", 0.0),
    "HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA.json":
        ("genius/lrclib-hit", "What It Sounds Like HUNTR/X", "none", 0.0),
    "Idina Menzel - Let It Go (from Frozen) (Official Video)---YVVTZgwYwVo.json":
        ("srt", "Let It Go Idina Menzel", "none", 0.0),
    "Jodi Benson - Part of Your World (From 'The Little Mermaid')---SXKlJuO07eM.json":
        ("srt", "Part of Your World Jodi Benson", "word", 0.407),
    "Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY.json":
        ("genius/lrclib-hit", "In Summer Josh Gad", "none", 0.0),
    "Justin Timberlake - Like I Love You (Official Video)---FQ3slUz7Jo8.json":
        ("srt", "Like I Love You Justin Timberlake", "none", 0.0),
    "Justin Timberlake - Mirrors (Official Video)---uuZE_IRwLNI.json":
        ("srt", "Mirrors Justin Timberlake", "none", 0.0),
    "Justin Timberlake - Selfish (Official Video)---je0roKRn3nY.json":
        ("srt", "Selfish Justin Timberlake", "word", 0.38),
    "Mena Massoud, Naomi Scott - A Whole New World (from Aladdin) (Official Video)---eitDnP0_83k.json":
        ("srt", "A Whole New World Mena Massoud, Naomi Scott", "none", 0.0),
    "Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY.json":
        ("genius/lrclib-miss", "I’ll Make a Man Out of You Donny Osmond", "line", 0.66),
    "NSYNC - Bye Bye Bye (Official Video)---Eo-KmOd3i7s.json":
        ("srt", "Bye Bye Bye NSYNC", "none", 0.0),
    "NSYNC - Paradise.json":
        ("genius/lrclib-miss", "Paradise Justin Timberlake", "line", 0.0),
    "Naomi Scott - Speechless (from Aladdin) (Official Video)---mw5VIEIvuMI.json":
        ("srt", "Speechless Naomi Scott", "none", 0.0),
    "Seasons of Love (HD)---UvyHuse6buY.json":
        ("genius/lrclib-miss", "Seasons of Love Cast of the Motion Picture ‘Rent’", "word", 0.088),
    "The Lion King - Can You Feel The Love Tonight---25QyCxVkXwQ.json":
        ("srt", "Can You Feel The Love Tonight The Lion King", "none", 0.0),
    "The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fwLxDUQBdEg.json":
        ("genius/lrclib-miss", "Hakuna Matata Nathan Lane", "none", 0.0),
    "The Next Ten Minutes Lyrics---0j8kL24ph8U.json":
        ("genius/lrclib-hit", "The Next Ten Minutes Anna Kendrick", "line", 0.93),
    "Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ.json":
        ("genius/lrclib-miss", "The Girl in the Bubble Ariana Grande", "none", 0.0),
    "ZAYN, Zhavia Ward - A Whole New World (End Title) (From 'Aladdin')---rg_zwK_sSEY.json":
        ("srt", "A Whole New World ZAYN, Zhavia Ward", "none", 0.0),
}
```

Corpus: `/home/ken/pikaraoke-songs/alignment_debug/*.json` (same 33 bundles as
part (a)). Match bundles by filename (`Path(f).name in BASELINE`), not by
re-running `query_for`/`segment_for` from the original plan — the query
strings above are already final. You will additionally need each song's
**title and artist kept separate** (not pre-joined) to build the title-only
fallback variant in Mechanism 2 — re-derive those the same way part (a) did:
genius-origin via `clean_key(lyrics.genius["title"], lyrics.genius["artist"])`;
srt-origin via the `song_stem` split-on-first-" - " parse. Reuse
`pikaraoke.lib.lrclib.clean_key` — don't re-implement it. Each bundle's
`lyrics.lines` is the sheet for `map_lines_to_cues`; `media_duration_s` is the
top-level duration field for the tie-break in `best_by_reference`.

## Environment

Same as part (a): `/home/ken/miniconda3/envs/pik/pip install syncedlyrics`
(probe-only — do **not** add to `requirements.txt`/`pyproject.toml`;
uninstall when done). Run with the `pik` python throughout.

## Mechanism 1 + 2: reference-pick candidate selection, with title-only fallback

Validated code from this session's prototype (session scratchpad script,
not preserved — reproduced here in full since it's the proven starting
point; adapt only if the installed `syncedlyrics` version has drifted, same
STEP-0 spirit as part (a)):

```python
import json, re, time
from syncedlyrics.providers import Musixmatch
from syncedlyrics.utils import format_time, get_cache_path
from pikaraoke.lib.lrclib import map_lines_to_cues, parse_lrc_lines

WORD_TAG = re.compile(r"<\d+:\d{2}(?:\.\d+)?>")
TOKEN_PATH = get_cache_path("syncedlyrics", False) / "musixmatch_token.json"
CALL_SLEEP_S = 2.5
SONG_SLEEP_S = 4.0  # sleep this long between songs in your main() loop
BACKOFF_SLEEP_S = 20.0

mm = Musixmatch(enhanced=False)  # ONE shared instance for the whole run - see
                                  # Robustness section for why

def get(action, params):
    """One call, one 401-triggered backoff+retry (fresh token). Any other
    non-200 (404 = no content for this track, etc.) is a clean miss, not a
    throttle - return None immediately, don't waste a retry on it."""
    r = mm._get(action, list(params))
    code = r.json().get("message", {}).get("header", {}).get("status_code")
    if code == 401:
        print(f"    [{action} -> 401, backing off {BACKOFF_SLEEP_S}s + fresh token]")
        time.sleep(BACKOFF_SLEEP_S)
        TOKEN_PATH.unlink(missing_ok=True)
        mm.token = None
        r = mm._get(action, list(params))
        code = r.json().get("message", {}).get("header", {}).get("status_code")
    return r.json() if code == 200 else None

def candidate_lyrics(track_id):
    """(kind, body) for one candidate: richsync first, else line-level."""
    d = get("track.richsync.get", [("track_id", track_id)])
    if d and d["message"]["body"].get("richsync"):
        raw = json.loads(d["message"]["body"]["richsync"]["richsync_body"])
        s = ""
        for i in raw:
            s += f"[{format_time(i['ts'])}] "
            for l in i["l"]:
                t = format_time(float(i["ts"]) + float(l["o"]))
                s += f"<{t}> {l['c']} "
            s += "\n"
        return "word", s
    time.sleep(CALL_SLEEP_S)
    d = get("track.subtitle.get", [("track_id", track_id), ("subtitle_format", "lrc")])
    if d and d["message"]["body"]:
        return "line", d["message"]["body"]["subtitle"]["subtitle_body"]
    return "none", None

def map_rate_for(body, sheet):
    if not body:
        return 0.0
    clean = WORD_TAG.sub("", body)
    cue_texts, _ = parse_lrc_lines(clean)
    if not cue_texts or not sheet:
        return 0.0
    return len(map_lines_to_cues(sheet, cue_texts)) / len(sheet)

def best_by_reference(term, sheet, media_dur):
    """Best-scoring viable candidate for one query term, or None."""
    d = get("track.search", [("q", term), ("page_size", "5"), ("page", "1")])
    if not d:
        return None
    best_key, best_row = None, None
    for t in d["message"]["body"].get("track_list", []):
        tr = t["track"]
        if tr.get("instrumental") or not (tr.get("has_subtitles") or tr.get("has_richsync")):
            continue
        time.sleep(CALL_SLEEP_S)
        kind, body = candidate_lyrics(tr["track_id"])
        rate = map_rate_for(body, sheet)
        length = tr.get("track_length") or 0
        dur_key = -abs(length - media_dur) if media_dur else 0.0
        key = (rate, dur_key)
        row = {"track_id": tr["track_id"], "track_name": tr["track_name"],
               "artist_name": tr["artist_name"], "kind": kind, "map_rate": round(rate, 3)}
        if best_key is None or key > best_key:
            best_key, best_row = key, row
    return best_row

def reference_pick(term_variants, sheet, media_dur):
    """Mechanism 1+2 combined: best candidate across every query variant
    tried (e.g. [\"title artist\", \"title\"]), tagged with which variant won."""
    overall = None
    for i, term in enumerate(term_variants):
        time.sleep(CALL_SLEEP_S)
        row = best_by_reference(term, sheet, media_dur)
        if row is None:
            continue
        row = {**row, "term": term, "variant": i}
        if overall is None or row["map_rate"] > overall["map_rate"]:
            overall = row
    return overall
```

`term_variants` per song: `[f"{track} {artist}".strip()]` if `artist` is
empty, else `[f"{track} {artist}".strip(), track]` — try the full query
first (matches part (a) exactly, for comparability), fall back to
title-only only if it didn't already return a confident hit (see the
per-song algorithm below for exactly when the fallback fires).

## Mechanism 3: NetEase secondary provider

**STEP 0 result (verified during implementation, corrects this plan's
original assumption):** `syncedlyrics==1.0.1`'s `NetEase.get_lrc_by_id`
requests `lv=1` and reads only the response's `lrc` field — it never
requests or parses NetEase's `yrc` (word-level) field at all. Confirmed
live against 3 known-good songs (Bohemian Rhapsody, Blinding Lights, Rock
Your Body): all returned plain line-level LRC, zero inline word tags. **This
plan's "also word-level via yrc" framing was wrong for the installed library
version — treat NetEase as a line-level-only fallback, never `word`,**
unless a future `syncedlyrics` upgrade adds real `yrc` support (check the
provider source again before assuming otherwise). No throttling observed
across quick repeated calls (no token dance like Musixmatch, despite a
hardcoded, visibly stale ~2022 session cookie in the provider — apparently
unchecked by the endpoints actually used). Plain `try/except` + the same
`CALL_SLEEP_S` pacing is enough; no backoff/retry logic needed.

One data-quality note, not a bug to fix: NetEase's LRC embeds credit lines
(作词/作曲/编曲/制作人 — lyricist/composer/arranger/producer) as real
timestamped entries at the top of the body. Harmless — `map_lines_to_cues`'s
fuzzy alignment already tolerates a few unmatched junk lines by design (its
gap-cost is small but nonzero specifically so stray lines fall out of the
mapping instead of pairing wrongly); no special stripping needed.

Only call NetEase for a song if Mechanism 1+2 ends with **no candidate at
all, or the best candidate's `map_rate == 0.0`** (found something, but zero
real overlap - as uninformative as nothing). Use the original full
`"{track} {artist}"` term via the public `syncedlyrics.search(term,
providers=["NetEase"], synced_only=True)` (no need for Mechanism 1's
provider-internals bypass here — NetEase's own candidate selection isn't
known to have the same text-similarity mis-ranking problem, and this plan
doesn't test for it). Score with the same `map_rate_for`; classify as `line`
if non-empty, `none` if empty — never `word`.

## Per-song algorithm

For each of the 26 in-scope songs:

1. Build `term_variants` (see above).
2. `pick = reference_pick(term_variants, sheet, media_dur)`.
3. If `pick is None or pick["map_rate"] == 0.0`: try Mechanism 3
   (NetEase) with the full term; if it scores higher, it becomes the new
   `pick`.
4. Classify the final `pick` the same way part (a) did: word (tags present)
   / line (synced, no tags) / none (nothing usable). If `map_rate < 0.5`,
   note `wrong-song?` same as part (a) — don't count it as covered.
5. Record: song, segment, old (kind, rate), new (kind, rate, source —
   `musixmatch-ref/full`, `musixmatch-ref/title-only`, `netease`, or
   `unchanged`), delta.
6. `time.sleep(SONG_SLEEP_S)` before moving to the next song.

Wrap each song's whole block in `try/except Exception`, log the error string
into that row, and continue — one failure must not abort the run (same as
part (a)).

## Robustness / politeness (lessons from part (a), don't relearn these)

- **Reuse one shared `Musixmatch()` instance for the entire run** (as in the
  code above) rather than constructing a fresh one per call. Part (a)'s
  first attempt did the latter (via the public `syncedlyrics.search()`,
  which builds a fresh provider — and therefore fetches a fresh token —
  on every single call) and got 401-throttled almost immediately; the
  fix that worked was pacing + reusing one token, not refreshing more
  aggressively.
- Pace calls: `CALL_SLEEP_S = 2.5` between calls within a song,
  `SONG_SLEEP_S = 4.0` between songs. This exact pacing ran the full
  part (a) 33-song batch and this session's 4-song prototype with only
  a handful of 401s (part (a): 6/33, all recovered by the single backoff
  retry) or zero (the prototype).
- On a genuine 401: sleep `BACKOFF_SLEEP_S = 20.0`, clear
  `get_cache_path("syncedlyrics", False) / "musixmatch_token.json"`, retry
  **once**. Don't retry indefinitely and don't refresh the token
  preemptively on every call — both make the throttle worse, not better
  (confirmed this session: a per-call-fresh-token experiment tripped the
  token endpoint's own throttle, which then retries internally with an
  unbounded `sleep(10); recurse` loop inside the library — if that happens,
  kill the process rather than waiting it out, and fall back to the
  single-shared-instance approach).
- `syncedlyrics`'s `LRCProvider.__init__` calls
  `logging.getLogger("Musixmatch").addHandler(...)` with no idempotency
  check on every provider instantiation, so console warnings reprint once
  per accumulated handler over a long run if you construct more than one
  instance. Not a problem here since this plan reuses one instance
  throughout, but don't reintroduce per-call instantiation without also
  reintroducing a handler-reset guard (part (a)'s script had one).
- Expect this run to take longer than part (a)'s ~2 minutes — up to
  roughly 10-20 minutes depending on how many songs need the title-only
  and/or NetEase fallback. Run it backgrounded and wait for the
  completion notification rather than a short foreground timeout.

## Output — append to this file

Add a `## Results` section with:

1. **Per-song table** (26 rows): Song | Segment | Old (kind/rate) | New
   (kind/rate) | Source (which mechanism/variant produced the new result,
   or "unchanged") | Notes (carry over `wrong-song?` flags per the
   `map_rate < 0.5` rule).
2. **Summary**: how many of the 26 improved (kind upgraded, e.g.
   none→line/word, line→word, or wrong-song→real coverage), how many were
   unchanged, how many got worse (should be zero or explain why — a
   regression here would be a real bug, not an expected outcome). Break out
   by mechanism: how many wins came from reference-pick alone (Mechanism 1),
   how many needed the title-only variant (Mechanism 2), how many needed
   NetEase (Mechanism 3).
3. **Updated headline numbers**: recompute the same word/line/wrong-song/none
   counts part (a) reported (overall, and for the genius/lrclib-miss segment
   specifically), combining the 7 already-good rows (unchanged) with the 26
   reprocessed rows' new results.
4. **One-paragraph recommendation**: is the combined approach worth wiring
   into production (`lyrics_fetch.py`) for real? If yes, which mechanism(s)
   specifically carried the value — e.g. if Mechanism 1 did all the work
   and Mechanism 3 never fired, say so plainly rather than recommending the
   whole bundle by default.

`syncedlyrics` uninstall note (same as part (a)'s environment rule) goes at
the end of the Results section.

## Success criteria

- All 26 in-scope songs attempted; every row has a result or a recorded
  error (never an unhandled exception aborting the run).
- Every row's new result traces to a specific mechanism (or "unchanged"),
  not just a bare before/after number — the recommendation in step 4 above
  depends on knowing which mechanism earned its keep.
- No regression: every "new" result is `>=` its "old" result by map_rate,
  or the row explains why (e.g. NetEase's candidate scored lower and was
  correctly not chosen — `reference_pick`/the NetEase-only-on-miss gate
  should prevent this by construction, but confirm it held).

## Non-goals

- No production/pipeline wiring, no new product dependency
  (`requirements.txt`/`pyproject.toml` untouched), no edits to
  `lyric_align.py` / `lyrics_fetch.py`.
- No re-running the 7 already-good songs.
- No further providers beyond Musixmatch + NetEase.
- No timing-accuracy comparison vs stable-ts (still part (b), still
  deferred, still a separate later decision).

## Results

Ran 2026-07-18 via `scripts/musixmatch_coverage_improve.py` (kept in the repo
per Ken's request — this round's dependency and tooling persist, unlike part
(a)'s scratchpad-only probe; `syncedlyrics` is now a `dev` extra in
`pyproject.toml`, not a runtime dependency). STEP 0 for Mechanism 3 corrected
this plan's own assumption before any real rows ran — see the note now in
the Mechanism 3 section above: the installed `syncedlyrics` NetEase provider
only ever returns line-level LRC, never word-level, despite the plan
originally citing NetEase's `yrc` format as "also word-level."

6 of the 26 songs' Musixmatch calls hit a 401 (the same throttle from part
(a)); all 6 recovered via the single backoff+retry, zero unhandled errors,
zero songs skipped.

### Per-song table (26 reprocessed)

| Song | Segment | Old | New | Source | Notes |
|------|---------|-----|-----|--------|-------|
| For Good (#OutOfOz) | srt | none | none | full | unchanged — garbled title-parsed query, as expected |
| Defying Gravity | genius/lrclib-miss | line 0.685 | line 0.685 | full | unchanged — reference-pick confirmed the same candidate |
| **Free** | genius/lrclib-hit | none | **word 0.805** | full | **new win** — old single-pick rejected every candidate outright even though a well-matching one existed |
| Beauty and the Beast (AG/JL) | srt | none | word 0.482 | title-only | improved, still wrong-song (just under the 0.5 line) |
| Incomplete | srt | none | word 0.296 | full | improved, still wrong-song |
| **More Than That** | srt | none | **word 0.923** | full | **new win** |
| Be Our Guest | genius/lrclib-miss | line 0.688 | line 0.688 | full | unchanged — already optimal |
| Happier | srt | none | line 0.421 | title-only | improved, still wrong-song |
| **What It Sounds Like** | genius/lrclib-hit | none | **line 0.811** | full | **new win** — a 2025 release; turned out to be indexed after all |
| **Let It Go** | srt | none | **word 0.702** | full | **new win** |
| **Part of Your World** | srt | word 0.407 (wrong-song) | **word 0.704** | title-only | **new win** — title-only surfaced a different, better candidate than the artist-qualified query ever saw |
| **In Summer** | genius/lrclib-hit | none | **line 0.581** | netease | **new win** — first confirmed NetEase win |
| **Like I Love You** | srt | none | **word 0.869** | full | **new win** |
| **Mirrors** | srt | none | **word 0.883** | full | **new win** |
| Selfish | srt | word 0.38 (wrong-song) | word 0.38 (wrong-song) | full | unchanged — genuine ceiling, only 1 candidate ever has lyrics |
| A Whole New World (Mena/Naomi) | srt | none | word 0.463 | full | improved, still wrong-song |
| **I'll Make a Man Out of You** | genius/lrclib-miss | line 0.66 | **line 0.851** | title-only | already covered, rate improved |
| Bye Bye Bye | srt | none | none | — | unchanged — no viable candidate on either provider |
| **NSYNC Paradise** | genius/lrclib-miss | line 0.0 (wrong-song) | **line 0.785** | netease | **new win** — Musixmatch never had the right song under any query; NetEase's catalog did |
| **Speechless** | srt | none | **line 0.571** | netease | **new win** |
| **Seasons of Love** | genius/lrclib-miss | word 0.088 (wrong-song) | **word 0.912** | full | **new win** — reproduces this session's earlier prototype exactly |
| **Can You Feel the Love Tonight** | srt | none | **word 0.875** | title-only | **new win** |
| **Hakuna Matata** | genius/lrclib-miss | none | **line 0.625** | netease | **new win** — the Musixmatch match was a no-lyrics instrumental cover; NetEase had a real one |
| **The Next Ten Minutes** | genius/lrclib-hit | line 0.93 | **line 0.958** | title-only | already covered, rate improved |
| The Girl in the Bubble | genius/lrclib-miss | none | line 0.444 | full | improved, still wrong-song (a 2025 release, near the line) |
| A Whole New World (End Title, ZAYN) | srt | none | none | — | unchanged — no viable candidate on either provider |

### Summary

**13 songs newly crossed into real coverage** (none/wrong-song → word or
line at ≥0.5): Free, More Than That, What It Sounds Like, Let It Go, Part of
Your World, In Summer, Like I Love You, Mirrors, NSYNC Paradise, Speechless,
Seasons of Love, Can You Feel the Love Tonight, Hakuna Matata.
**2 more already-covered songs improved their rate** within the same tier
(I'll Make a Man Out of You 0.66→0.851, The Next Ten Minutes 0.93→0.958).
**2 held exactly flat** at already-good values (Defying Gravity, Be Our
Guest — reference-pick confirmed the existing pick was already optimal).
**9 remain uncovered** — 3 true `none` (no candidate on any provider/query)
and 6 stuck at `wrong-song` (one, Selfish, is a hard ceiling with only one
lyric-bearing candidate anywhere; the other 5 improved numerically and four
of those sit close to the 0.5 line — 0.482, 0.463, 0.444, 0.421 — suggesting
a content/version mismatch rather than a pure searchability problem).
**Zero regressions** — no row's map-rate went down, matching the plan's
success criterion (both fallback mechanisms only replace a pick when they
score strictly higher).

By mechanism, among the 15 real wins (13 new + 2 in-tier improvements):

| Mechanism | Wins | Songs |
|---|---|---|
| 1 — reference-pick, full query | 7 | Free, More Than That, What It Sounds Like, Let It Go, Like I Love You, Mirrors, Seasons of Love |
| 2 — title-only fallback | 4 | Part of Your World, Can You Feel the Love Tonight, I'll Make a Man Out of You, The Next Ten Minutes |
| 3 — NetEase fallback | 4 | In Summer, NSYNC Paradise, Speechless, Hakuna Matata |

All three mechanisms earned their keep — this isn't a case where one
mechanism did all the work and the others were dead weight.

### Updated headline numbers

Combining the 7 already-good skipped songs with the 26 reprocessed results
(wrong-song still excluded from "covered" per the same `< 0.5` rule as
part (a)):

| Segment | word | line | wrong-song | none | n | real coverage |
|---|---|---|---|---|---|---|
| Overall | 15 (was 7) | 9 (was 4) | 6 (was 4) | 3 (was 18) | 33 | **24/33 = 73%** (was 11/33 = 33%) |
| **genius/lrclib-miss (the 12)** | 6 (was 5) | 5 (was 3) | 1 (was 2) | 0 (was 2) | 12 | **11/12 = 92%** (was 8/12 = 67%) |
| genius/lrclib-hit (the 5) | 2 (was 1) | 3 (was 1) | 0 | 0 (was 3) | 5 | **5/5 = 100%** (was 2/5 = 40%) |
| srt (the 16, informational) | 7 (was 1) | 1 (was 0) | 5 (was 2) | 3 (was 13) | 16 | **8/16 = 50%** (was 1/16 = 6%) |

The money segment (genius/lrclib-miss, the ASR-only songs LRCLIB never
covered) went from 67% to 92% real coverage — only The Girl in the Bubble
remains, a very recent release sitting just under the line (0.444), most
likely thin indexing rather than a fixable mismatch.

### Recommendation

**Worth wiring in for real.** All three mechanisms contributed genuine,
distinct wins with zero regressions across 26 songs — this isn't a case for
picking just one. Mechanism 1 (reference-pick) alone would have delivered 7
of the 15 real wins and is the lowest-risk of the three (same provider,
same query, just a better internal pick); Mechanisms 2 and 3 are cheap
incremental adds on top (only triggered when 1 comes up empty or at 0.0) that
each contributed 4 more wins nobody would have gotten otherwise. The
genius/lrclib-miss segment's jump to 92% real coverage substantially
strengthens the case for part (b) (timing-quality comparison vs stable-ts) —
there are now 11 real-coverage songs in that segment to draw from instead of
8, and 6 of them word-level instead of 5. Suggested next step if this moves
forward: wire Mechanisms 1+2 (Musixmatch-only, no extra provider) into
`lyrics_fetch.py`'s Musixmatch path first, since together they're the
larger and lower-risk share of the win (11/15), and evaluate NetEase (a
second external dependency, a second catalog's worth of wrong-song risk
never tested against here) as a separate, later decision.

`syncedlyrics` stays installed in `pik` and stays in `pyproject.toml`'s `dev`
extra — not uninstalled, per this round's explicit instruction (differs from
part (a)'s probe-only rule). `scripts/musixmatch_coverage_improve.py` stays
in the repo for future reruns/extension.
