# Genius.com Lyrics Integration

Model: Claude Opus 4.7

## Context

Today the alignment pipeline gets its lyrics from the YouTube auto-caption SRT
that yt-dlp downloads alongside the video. SRT is convenient but lossy:

- Auto-captions miss words, mangle proper nouns, and split lines awkwardly.
- They have no notion of structure (verse/chorus/bridge), which blocks any
  future singer-attribution / diarization work.
- Many videos have no captions at all, forcing transcription as the only
  fallback.

A working prototype at [mpv/search-prototype/](../mpv/search-prototype/) lets
the user pre-select a Genius.com lyric source from the YouTube search page
(per-result selectize dropdown), with three options: a specific Genius song, a
custom Genius search, or "raw transcription" to skip lyrics entirely.

This plan integrates that prototype into the production app. The lyrics file
is treated as **ephemeral pipeline scratch**, not a long-lived artifact —
selection persists, lyrics text does not.

______________________________________________________________________

## Scope

**In scope:**

- New routes: `/lyrics_search`, `/lyrics_select` in `pikaraoke/routes/search.py`.
- New module: `pikaraoke/lib/genius.py` — Genius API client + selection
  sidecar I/O.
- New module: `pikaraoke/lib/genius_lyrics.py` — Genius lyrics parser
  (`parse_genius_sections` full port) + `clean_genius_query()` query
  cleaner.
- New stage: `pikaraoke/pipeline/stages/lyrics_fetch.py` — runs first in the
  pipeline; resolves the lyrics source for the job.
- Edit: `pikaraoke/pipeline/stages/lyric_align.py` — strip Genius section
  headers before alignment; carry structure forward as `lyrics_structure`
  artifact; gate SRT writes on absence of an existing SRT.
- Edit: `pikaraoke/lib/processing_manager.py` — register the new stage; remove
  `_resolve_lyrics_path` (logic moves into the stage).
- Edit: `pikaraoke/lib/metadata_parser.py` — add `extract_youtube_id()`
  (canonical bare-ID extraction, Design Decision 6).
- Edit: `pikaraoke/templates/search.html` — port the selectize lyric-picker
  block from the prototype; rename Download → Select; move Download button
  into modal; refactor `openPreviewModal()` (Design Decision 1).
- Edit: `pikaraoke/lib/preference_manager.py` + `pikaraoke/karaoke.py` —
  `genius_token` as a hidden config entry, mirroring the
  `blocked_processing_words` pattern (commit 0bc73d27).

**Out of scope:**

- Singer-attribution / diarization downstream of `lyrics_structure`. The
  artifact is produced and ready, but no consumer is added by this plan.
- An admin "regenerate SRT" toggle (the new SRT-only-if-missing rule slightly
  reduces SRT freshness on re-runs; revisit if it's a problem).
- Migration of the prototype's `selectize` library if the production app
  already ships a different autocomplete widget — to be assessed during port.

______________________________________________________________________

## Design Decisions (review session → rulings)

These are the resolved ambiguities and rejected alternatives from the
pre-implementation review. Every ruling below supersedes anything in the
original component sections that contradicts it; the component sections
have been edited to reflect these decisions where applicable.

### 1. UI flow: "Download" button becomes "Select"; Download moves inside modal

**Finding:** The prototype has a "Select" button on each search result row
(line 722 of `search-prototype/templates/search.html`) that opens
`openPreviewModal()`. The production app has a "Download" button on each
row that calls `downloadSong()` directly — no modal involved. The plan
originally said "the existing per-result Download button is unchanged" and
placed the picker inside the modal, but that means a user who clicks
Download without opening the modal gets SRT fallback with no opportunity
to select Genius lyrics.

**Decision (matches prototype):** Rename the per-result "Download" button
to "Select". Both the Select button and the thumbnail open the preview
modal. The modal contains the lyrics picker **and** the Download button
that actually queues yt-dlp. This is exactly how the prototype works:
`openPreviewModal()` at line 549, Select button at line 722, Download
Lyrics button at line 754.

**Consequences:**
- The production `.img-wrapper` click handler (line 543) must be
  refactored into a reusable `openPreviewModal($li)` function (matching
  the prototype's line 549).
- The production `downloadSong()` function (line 468) must be callable
  from inside the modal — the Download button lives in the modal markup.
- The `openPreviewModal()` function must also call
  `resetLyricsSection()` + `runLyricsSearch(videoTitle)` (prototype
  lines 577–578).
- The production `is-loading` spinner on the modal (line 550) is
  preserved — the prototype dropped it but we keep it.

### 2. `GeniusClient` is always constructed — never `None`, no gating

**Finding:** The plan originally said `GeniusClient` is "constructed only
when a token is configured" and routes/template/stage check
`genius_client is None`. This requires `None` checks scattered across
routes, template `{% if genius_client %}` blocks, and the stage. It also
creates a split code path that's harder to test.

**Decision:** `GeniusClient(api_token="")` is always constructed,
regardless of whether a token is configured. An empty token produces a
client whose `search()` always returns `[]` and whose `fetch_lyrics()`
always raises `GeniusUnavailable`. Routes and the template never check
for `None` — they always call `search()` / render the picker. The picker
degrades gracefully: empty search results → "No lyrics results found"
message + custom search input. The pipeline stage always reads choice
files; if `fetch_lyrics()` fails (because the token is empty), it falls
through to SRT fallback.

**Consequences:**
- No `{% if genius_client %}` in any template.
- No `if genius_client is not None` in any route.
- No `if self._genius is not None` in `LyricsFetchStage`.
- `Karaoke.genius_client` is always a `GeniusClient` instance.
- `LyricsFetchStage.__init__` takes `GeniusClient` (not
  `GeniusClient | None`).
- `ProcessingManager.__init__` always receives a `GeniusClient`.

### 3. `lyricsgenius` is a hard dependency — no optional extra, no ImportError guard

**Finding:** The plan originally said "hard requirement, not an optional
extra." During review, the question was raised whether `lyricsgenius`
should be an optional extra (`pip install pikaraoke[genius]`) to avoid
pulling in `beautifulsoup4` + `requests-cache` for users who won't
configure a token.

**Decision (confirmed):** `lyricsgenius>=3.0` goes in
`pyproject.toml [project] dependencies` as a hard requirement. No
`try/except ImportError` guard. The import sits at module top level. The
~2MB of transitive deps is acceptable for a self-hosted karaoke app.
This is consistent with the project already bundling heavy deps like
`audio-separator`.

### 4. No `enabled` flag / `genius_enabled` property

**Finding:** The plan originally said "no derived boolean anywhere in the
code path" but then also said routes check `genius_client is not None`.
With Decision 2 (always-constructed client), this is moot.

**Decision (confirmed):** No `enabled` property on `GeniusClient`. No
`genius_enabled` variable anywhere. The empty-string token is the
configuration signal; the always-failing client is the runtime behavior.

### 5. Short-circuit guard uses `is not None`, not `in`

**Finding:** The orchestrator always sets
`ctx.artifacts["lyrics_path"] = lyrics_path` at line 212 *before any
stage runs*, even when `lyrics_path` is `None`. So
`"lyrics_path" in ctx.artifacts` is always `True`. The plan's pseudocode
had `if "lyrics_path" in ctx.artifacts:` which would short-circuit every
run.

**Decision:** The short-circuit guard in `LyricsFetchStage.run()` must
be:
```python
if ctx.artifacts.get("lyrics_path") is not None:
    ctx.artifacts.setdefault("lyrics_origin", "override")
    return
```
This only fires when a test explicitly passes a non-`None` `lyrics_path`
to `run_one_async`. On normal runs, `lyrics_path` is `None` and the
stage proceeds to its resolution logic.

### 6. `_extract_yt_id` delegates to new `extract_youtube_id()` in `metadata_parser.py`

**Finding:** The plan proposed a new static method
`LyricsFetchStage._extract_yt_id` with its own regex. But
`library_scanner._extract_youtube_id` (line 29–37) already does the same
job by calling `metadata_parser.youtube_id_suffix()` and stripping
delimiters. A third implementation would drift over time.

**Decision:** Add a public `extract_youtube_id(path: str) -> str | None`
function to `metadata_parser.py` that calls `youtube_id_suffix()` and
strips the delimiters (same logic as
`library_scanner._extract_youtube_id` lines 31–37). Make this the
canonical implementation. `LyricsFetchStage._extract_yt_id` delegates to
it. Optionally refactor `library_scanner._extract_youtube_id` to call it
too, but that's a cleanup commit, not a blocker.

### 7. Full `parse_genius_sections` port to `genius_lyrics.py` — not a minimal version

**Finding:** The plan said "Port `parse_genius_sections` into a new
helper module (or inline a minimal version)." The existing parser at
`/home/ken/whisper2srt/genius_diarize/genius.py` (204 lines) includes
section-number carry-forward, `split_groups()` for multi-speaker
attribution, `genius_singer_mode()` detection, and per-line `align_text`
vs `text` distinction. A "minimal version" would lose the carry-forward
and the `align_text` distinction, both of which matter for alignment
quality.

**Decision:** Port the full `parse_genius_sections` + `split_groups` +
supporting functions into `pikaraoke/lib/genius_lyrics.py`. The
`align_text` field (with inline parens stripped) is the text that
stable-ts aligns to; `text` (display, with parens preserved) is for
future display/consumers. This distinction matters for lines like
`"(I can't help) Falling in love"` — aligning to `"Falling in love"`
works better than aligning to the full string.

### 8. `clean_genius_query()` replaces `regex_tidy` for `/lyrics_search`

**Finding:** The prototype's `lyrics_search` route (line 129) uses
`regex_tidy(query)` to clean the search string. But `regex_tidy`
strips parenthetical content (line 590: `re.sub(r"\s*\([^)]*\)\s*$", "",
name)`), which loses meaningful title parts like
`"(I Can't Help) Falling In Love"` → `"Falling In Love"`. The prototype
falls back to the raw query only if `regex_tidy` produces empty string,
not if it merely strips too much.

**Decision:** Write a `clean_genius_query()` function in
`pikaraoke/lib/genius_lyrics.py` that does a light clean: strip emoji
and YouTube noise words (reuse `NOISE_WORDS`/`NOISE_PATTERN`/`EMOJI_PATTERN`
from `metadata_parser.py`), but **preserve parenthetical and bracketed
content**. The `/lyrics_search` route calls `clean_genius_query()` instead
of `regex_tidy()`.

### 9. `_load_lyrics` 2-tuple → 3-tuple change must be atomic

**Finding:** Changing `_load_lyrics` from `tuple[str, str]` to
`tuple[str, str, list[dict] | None]` crashes the existing call site at
`lyric_align.py:63` with `ValueError: too many values to unpack`. This
must land in a single commit that updates both the signature and the
call site.

**Decision:** The `_load_lyrics` return-type change and its sole call
site update land atomically in one commit as rollout step 3. Steps 1–2
don't touch `lyric_align.py`, so nothing breaks. No backward-compat shim
is needed.

### 10. No `_STRING_ONLY_KEYS` in PreferenceManager

**Finding:** `PreferenceManager._convert_value` auto-converts string
values to `int`/`float`. A Genius token like `"1234567890"` could become
`int(1234567890)`. The `get()` path is safe *today* because
`DEFAULTS["genius_token"] = ""` (a string) triggers the
`isinstance(default_value, str)` early return. The `set()` path is also
safe because `isinstance(default, str)` is `True`. This is a latent bug
(if the default sentinel or type changes) but not an active one.

**Decision (rejected):** Do **not** add `_STRING_ONLY_KEYS`. The
string-type default protects both `get()` and `set()` paths today. The
latent bug is real but not critical — a future refactor that changes the
default type would need to audit all consumers anyway. Adding
`_STRING_ONLY_KEYS` now is over-engineering for a hypothetical.

### 11. No `srt_write_policy` artifact

**Finding:** The plan's conditional SRT write (`_should_write_srt`) is
hardcoded with no escape hatch. If a YouTube SRT exists, the pipeline
never writes a new one — even on re-process. A `srt_write_policy`
artifact in `ctx.artifacts` would let a future "regenerate SRT" toggle
override this.

**Decision (rejected):** Do **not** introduce `srt_write_policy`. It's
over-engineering for a feature that's explicitly out of scope. The
filesystem check in `_should_write_srt` is sufficient. If a "regenerate
SRT" toggle is ever needed, the policy can be added then.

________________________________________________________________________

## Architecture

### Data flow

```
┌─ User on /search ────────────────────────────────────────────────────┐
│ 1. Types a query → YouTube results render (unchanged row layout). │
│ 2. Clicks Select (or thumbnail) on a result → preview modal opens. │
│    Modal contains: video player, Genius "Lyrics:" picker, and a    │
│    Download button. The picker is a selectize dropdown (Genius     │
│    hits + Custom + Raw), auto-seeded from the YouTube title.      │
│ 3. Picks an option in the modal.                                   │
│    ─ Genius song → POST /lyrics_select { yt_id, genius_id }       │
│    ─ Raw → POST /lyrics_select { yt_id, mode: "raw" }             │
│    ─ Nothing → no POST, default behavior (SRT fallback)           │
│ 4. Clicks Download inside the modal → /download POST (queues yt-dlp).│
└──────────────────────────────────────────────────────────────────────┘

┌─ /lyrics_select handler ─────────────────────────────────────────────┐
│  Writes <temp>/lyric_choices/<yt_id>.json. No Genius fetch yet.      │
└──────────────────────────────────────────────────────────────────────┘

┌─ Download (unchanged) ───────────────────────────────────────────────┐
│  yt-dlp downloads video + (when available) en.srt.                   │
│  DownloadManager moves srt → subtitles/<stem>.srt.                   │
│  Emits song_downloaded → ProcessingManager picks up the song.        │
└──────────────────────────────────────────────────────────────────────┘

┌─ Pipeline ───────────────────────────────────────────────────────────┐
│  PreparePtyStage                                                     │
│  LyricsFetchStage  ◀── NEW, runs first after pty                     │
│    Resolves source:                                                  │
│      a. If <temp>/lyric_choices/<yt_id>.json with genius_id:         │
│         fetch from Genius → ctx.tmp_dir/lyrics.txt                   │
│         set ctx.artifacts["lyrics_path"] = that path                 │
│      b. If choice file says mode=raw:                                │
│         leave ctx.artifacts["lyrics_path"] = None  (force transcribe)│
│      c. If no choice file:                                           │
│         look for subtitles/<stem>.en.srt or subtitles/<stem>.srt     │
│         set ctx.artifacts["lyrics_path"] = that path or None         │
│    Deletes the choice file on success.                               │
│    On Genius fetch failure: log warning, fall through to (c).        │
│  FFmpegExtractStage                                                  │
│  LoudnormAnalyzeStage                                                │
│  StemSeparationStage                                                 │
│  FFmpegTranscodeStage                                                │
│  LyricAlignStage                                                     │
│    - Reads lyrics_path; alignment if set, transcription if None.     │
│    - For .txt with Genius headers: strips headers for alignment,     │
│      stashes parsed structure in ctx.artifacts["lyrics_structure"].  │
│    - SRT write: only when subtitles/<stem>.{en.,}srt is absent.      │
│    - ASS write: always (unchanged).                                  │
└──────────────────────────────────────────────────────────────────────┘
```

### Durable artifacts after a job

| Artifact | Source | Notes |
| --- | --- | --- |
| `<stem>.mp4` (or original) | yt-dlp | unchanged |
| `subtitles/<stem>.srt` | yt-dlp (preferred) or pipeline (fallback) | YouTube SRT is preserved; pipeline only writes when it would otherwise be missing |
| `karaoke/<stem>.ass` | pipeline | always generated |

No long-lived lyrics file. No `pending_lyrics/` directory. Selection sidecar
lives only between user click and pipeline consumption.

### Selection sidecar format

Path: `<get_temp_directory()>/lyric_choices/<yt_id>.json`

```json
{
  "yt_id": "dQw4w9WgXcQ",
  "genius_id": 4848515,
  "yt_title": "Rick Astley - Never Gonna Give You Up (Official Video)"
}
```

or for raw:

```json
{
  "yt_id": "dQw4w9WgXcQ",
  "mode": "raw"
}
```

`yt_title` is informational only (logging / debug). The join key is `yt_id`,
extracted from the downloaded video filename via the existing
`get_youtube_id_from_url` / filename regex used by `DownloadManager`.

______________________________________________________________________

## Components

### `pikaraoke/lib/genius.py` (new)

```python
class GeniusUnavailable(Exception):
    """Raised when Genius is configured but a request fails."""

class GeniusClient:
    def __init__(self, api_token: str = "", timeout: float = 15.0) -> None:
        """Construct a client. An empty token produces a client whose
        search() always returns [] and whose fetch_lyrics() always raises
        GeniusUnavailable — the caller never needs to check for None.

        A `threading.Lock` guards `search` and `fetch_lyrics` because the
        same `lyricsgenius.Genius` instance is shared between Flask request
        threads and the pipeline orchestrator thread, and the underlying
        `requests.Session` is not thread-safe.

        When api_token is "", the Genius instance is not created (or is
        created with a dummy token that will fail); search() returns []
        immediately; fetch_lyrics() raises GeniusUnavailable immediately.
        """

    def search(self, query: str, limit: int = 8) -> list[GeniusHit]:
        """Search for songs. Returns [] on failure (UI degrades gracefully).

        Filters: type == "song"; drops translation/cover artists when
        the user query already matches "genius" / "translation" terms
        (logic ported from prototype app.py:lyrics_search).
        """

    def fetch_lyrics(self, genius_id: int) -> str:
        """Scrape lyrics for a specific song id. Raises GeniusUnavailable
        on any error or when the scraped page yields empty lyrics. Returns
        the raw text including section headers (e.g. '[Verse 1]',
        '[Chorus: Artist]').
        """


@dataclass(frozen=True)
class GeniusHit:
    id: int
    title: str
    artist: str


# ── Selection sidecar ──────────────────────────────────────────────────

CHOICES_SUBDIR = "lyric_choices"

def choices_dir() -> Path:
    """<get_temp_directory()>/lyric_choices/, created if missing."""

def write_choice(yt_id: str, payload: dict) -> Path:
    """Atomic write (tmpfile + rename) of choice JSON. Overwrites any
    existing choice for the same yt_id.
    """

def read_choice(yt_id: str) -> dict | None:
    """Returns the choice dict or None if absent / unparseable."""

def delete_choice(yt_id: str) -> None:
    """Idempotent removal."""
```

**Why a class for `GeniusClient`**: groups the `lyricsgenius.Genius` instance
with its lock and config. Always constructed (even with empty token) so
callers never need to check for `None`. Routes and the stage borrow the
same instance from the Karaoke instance (mirrors how `DownloadManager` /
`SongManager` are exposed). A single `threading.Lock` serializes all
Genius API calls — they're inherently rate-limited per token, so the lock
isn't a bottleneck and protects the shared `requests.Session`.

**No `enabled` flag, no `genius_enabled` variable**: the empty-string
token is the configuration signal; the always-failing client is the
runtime behavior. No `None` checks anywhere — see Design Decision 2.

**Dependency**: add `lyricsgenius>=3.0` to `pyproject.toml [project]
dependencies` (a hard requirement, not an optional extra). The import sits
at module top with the other imports — no `try/except ImportError` guard.

**Why the choice helpers are module-level functions**: they're stateless and
the call sites (route handler, stage) are in different processes/threads with
no shared object to inject. Atomic write avoids torn reads if the user clicks
Download immediately after picking.

**`fetch_lyrics` uses `search_song(song_id=id)`, not `song(id)`**: the API
endpoint returns metadata only; only the page-scraping path returns lyrics
text. This is the same approach as the prototype.

### `pikaraoke/routes/search.py` (edit)

Add two routes:

```python
@search_bp.route("/lyrics_search")
def lyrics_search():
    """GET ?q=<query> → JSON list of {id, title, artist}.

    Returns [] when Genius is disabled or the search fails. Always 200
    so the UI can render an empty state without error handling.
    """

@search_bp.route("/lyrics_select", methods=["POST"])
def lyrics_select():
    """POST { yt_id, genius_id?, mode?, yt_title? } → 204.

    Validates yt_id is the 11-char YouTube ID. One of {genius_id, mode}
    must be present. Writes the sidecar; does not fetch lyrics yet.

    Note: replaces the prototype's /lyrics_download route. The prototype
    fetched and saved lyrics text immediately; we only record the choice.
    """
```

`lyrics_search` uses `clean_genius_query()` from `genius_lyrics.py` to clean
the query (preserves parenthetical content, unlike `regex_tidy`). See
Design Decision 8.

The existing `search()` route passes `genius_client=k.genius_client` to its
`render_template` context. `genius_client` is always a `GeniusClient`
instance (never `None` — see Design Decision 2), so no `getattr` fallback
is needed.

`lyrics_select` validates `yt_id` against `re.compile(r"^[A-Za-z0-9_-]{11}$")`
(define once at module scope; same pattern enforced by YouTube). Malformed
ids → 400.

### `pikaraoke/templates/search.html` (edit)

**Picker placement**: inside the existing preview modal (`#modal-js-example`),
not inline per-result. The per-result "Download" button is renamed to
"Select" (Design Decision 1) — both the Select button and the thumbnail
open the modal. The modal now contains the lyrics picker **and** the
Download button that actually queues yt-dlp.

This matches the prototype's structure exactly:
- Prototype `openPreviewModal()` at line 549 — refactor the production
  `.img-wrapper` click handler (line 543) into this same function.
- Prototype Select button at line 722 — production "Download" button
  becomes "Select".
- Prototype Download button inside modal at line 754 — production
  Download button moves from the result row into the modal.
- Prototype `resetLyricsSection()` + `runLyricsSearch(videoTitle)` at
  lines 577–578 — production `openPreviewModal()` calls these too.

Port the lyric-picker UI from
[mpv/search-prototype/templates/search.html](../mpv/search-prototype/templates/search.html)
(roughly lines 420–545: `populateLyricsDropdown`, `runLyricsSearch`,
dropdown change handler, custom-search input; plus the modal markup at lines
730–760 which already targets the same element ids the JS expects).

Behavior changes from the prototype:

- The "Download Lyrics" button inside the modal is removed. Selection
  happens on dropdown change → POSTs to `/lyrics_select`. Persistence is
  implicit; no extra click.
- The Download button inside the modal (the one that actually queues
  yt-dlp) replaces the prototype's "Download Lyrics" button position.
- When the dropdown is on its initial empty state, no POST fires — that's
  "default behavior, fall through to SRT".
- No `{% if genius_client %}` gate — the picker is always visible (Design
  Decision 2). When the token is empty, `search()` returns `[]`, and the
  picker shows "No lyrics results found" + custom search input.
- The Genius search query is auto-seeded from the YouTube result's title
  on modal open (same as the prototype).
- The production `is-loading` spinner on the modal is preserved (the
  prototype dropped it; we keep it).

JS surface area:

```javascript
function recordLyricChoice(yt_id, payload) {
  // POST /lyrics_select with { yt_id, ...payload }; fire-and-forget
  // (button feedback is the dropdown state, not a server response).
}

// On dropdown change:
//   selected genius id  → recordLyricChoice(yt_id, { genius_id })
//   selected "__raw__"   → recordLyricChoice(yt_id, { mode: "raw" })
//   selected "__custom__" → no-op (waits for custom-search results)
```

### `pikaraoke/pipeline/stages/lyrics_fetch.py` (new)

```python
class LyricsFetchStage(BaseStage):
    """Resolve the lyrics source for the job and populate ctx.artifacts.

    Sets:
    - ctx.artifacts["lyrics_path"]: Path | None
    - ctx.artifacts["lyrics_origin"]: "genius" | "srt" | "none"

    Reads:
    - ctx.song_path (filename → yt_id)

    Networks:
    - Genius API when a Genius selection is present. Failures degrade
    to SRT/transcribe; never raise out of this stage.
    """

    name = "lyrics_fetch"

    def __init__(self, genius: GeniusClient) -> None:
        """`genius` is always a GeniusClient instance (Design Decision 2).
        When the token is empty, its methods degrade gracefully: search()
        returns [], fetch_lyrics() raises GeniusUnavailable.
        """
        self._genius = genius

    def run(self, ctx: StageContext) -> None:
        # Test-override short-circuit: orchestrator pre-populates
        # ctx.artifacts["lyrics_path"] when run_one_async is called with
        # an explicit lyrics_path kwarg. Respect it.
        # IMPORTANT: the orchestrator always sets
        # ctx.artifacts["lyrics_path"] = lyrics_path (even to None) at
        # line 212, so we must check "is not None", not "in" (Design
        # Decision 5).
        if ctx.artifacts.get("lyrics_path") is not None:
            ctx.artifacts.setdefault("lyrics_origin", "override")
            return

        yt_id = self._extract_yt_id(ctx.song_path)
        choice = read_choice(yt_id) if yt_id else None

        # Branch a: explicit Genius selection
        if choice and "genius_id" in choice:
            try:
                text = self._genius.fetch_lyrics(int(choice["genius_id"]))
                lyrics_path = ctx.tmp_dir / "lyrics.txt"
                lyrics_path.write_text(text, encoding="utf-8")
                ctx.artifacts["lyrics_path"] = lyrics_path
                ctx.artifacts["lyrics_origin"] = "genius"
                delete_choice(yt_id)
                return
            except GeniusUnavailable as e:
                logger.warning("Genius fetch failed for %s: %s — falling back", yt_id, e)
                # Do NOT delete the choice file — re-runs can retry.
                # Fall through.

        # Branch b: explicit raw selection
        if choice and choice.get("mode") == "raw":
            ctx.artifacts["lyrics_path"] = None
            ctx.artifacts["lyrics_origin"] = "none"
            delete_choice(yt_id)
            return

        # Branch c: SRT fallback (current behavior)
        srt_path = self._find_srt(ctx.song_path)
        ctx.artifacts["lyrics_path"] = srt_path
        ctx.artifacts["lyrics_origin"] = "srt" if srt_path else "none"

    @staticmethod
    def _extract_yt_id(song_path: Path) -> str | None:
        """Extract the 11-char YouTube ID from the filename.

        Delegates to `pikaraoke.lib.metadata_parser.extract_youtube_id`
        (Design Decision 6), which calls `youtube_id_suffix()` and strips
        delimiters to return the bare ID.
        Returns None for files without a recognisable ID (manually
        added library files).
        """

    @staticmethod
    def _find_srt(song_path: Path) -> Path | None:
        """Look for subtitles/<stem>.en.srt then subtitles/<stem>.srt.
        Logic moved verbatim from processing_manager._resolve_lyrics_path.
        """
```

**Cancellation**: the stage runs before any heavy work, so we don't bother
wrapping the Genius HTTP call in a `Phase` activity scope — a cancel during
this stage is checked by the orchestrator between stages, and a 2s HTTP call
that completes after the user cancelled is harmless. (If `lyricsgenius`
becomes a hot-spot for cancel latency we can revisit with a thread + poll.)

**No new `Phase`**: the stage doesn't need a dedicated cancel phase because
it has no model state to protect.

**Why this stage runs before FFmpegExtract, not after**: fail fast on Genius
problems. Extracting audio takes seconds we don't need to spend if we already
know we'll fail. This also keeps `ctx.tmp_dir/lyrics.txt` available for the
entire run, which simplifies LyricAlignStage.

### `pikaraoke/pipeline/stages/lyric_align.py` (edit)

Three changes:

**1. Genius header parsing in `_load_lyrics`:**

```python
def _load_lyrics(self, lyrics_path: Path) -> tuple[str, str, list[dict] | None]:
    """Returns (clean_text, format, structure).

    structure is a list of {line, section, attribution} dicts when the
    input is Genius-formatted .txt, else None.

    For Genius .txt:
      - Strip section header lines (lines matching r'^\\s*\\[.*\\]\\s*$').
      - Strip empty lines.
      - The remaining text is what stable-ts aligns to.
      - structure preserves header context for each surviving line.

    For non-Genius .txt and .srt: behaves as today; structure is None.
    """
```

Detection heuristic for "Genius-formatted": presence of any line matching the
section-header regex. The standard `_load_lyrics` `.srt` branch is unchanged.

Header parsing logic is already implemented in
[mpv/genius_diarize/genius.py:parse_genius_sections](../mpv/genius_diarize/genius.py).
Port the **full** `parse_genius_sections` + `split_groups` + supporting
functions into `pikaraoke/lib/genius_lyrics.py` (Design Decision 7) —
not a stripped-down version. The `align_text` field (with inline parens
stripped) is the text that stable-ts aligns to; `text` (display, with
parens preserved) is for future display/consumers. This distinction
matters for lines like `"(I can't help) Falling in love"`.

**File**: new `pikaraoke/lib/genius_lyrics.py` for the parser + query
cleaner (keeps API client and text parsing in separate modules). See
Design Decision 7 and 8.

**2. Carry structure forward:**

In `LyricAlignStage.run`, after `_load_lyrics`:

```python
lyrics_text, lyrics_format, lyrics_structure = self._load_lyrics(lyrics_path)
ctx.artifacts["lyrics_text"] = lyrics_text
ctx.artifacts["lyrics_format"] = lyrics_format
if lyrics_structure is not None:
    ctx.artifacts["lyrics_structure"] = lyrics_structure
```

**3. Conditional SRT write:**

Replace the current `write_srt = lyrics_format == "txt"` / `write_srt = True`
logic with a filesystem check, decoupled from input mode:

```python
def _should_write_srt(self, song_path: Path) -> bool:
    """Skip SRT generation when yt-dlp already provided one."""
    subs = song_path.parent / "subtitles"
    return not (
        (subs / f"{song_path.stem}.en.srt").exists()
        or (subs / f"{song_path.stem}.srt").exists()
    )
```

Replaces the two `write_srt = ...` assignments in `LyricAlignStage.run`. The
ASS write path is untouched.

### `pikaraoke/lib/processing_manager.py` (edit)

Two edits:

**1. Register the new stage in [processing_manager.py:212](../pikaraoke/lib/processing_manager.py#L212):**

```python
stages = [
    PreparePtyStage(self._pty_slave_fd),
    LyricsFetchStage(self._genius),         # NEW
    FFmpegExtractStage(self._config),
    LoudnormAnalyzeStage(self._config),
    StemSeparationStage(self._stem_worker),
    FFmpegTranscodeStage(self._config),
    LyricAlignStage(self._whisper_worker, self._config),
]
```

`self._genius` is a `GeniusClient` instance always passed in from
`ProcessingManager.__init__` (Design Decision 2 — never `None`).

**2. Remove `_resolve_lyrics_path` and its call site:**

```python
# Before:
lyrics_path = self._resolve_lyrics_path(song_path)
token = self._orchestrator.run_one_async(Path(song_path), lyrics_path)

# After:
token = self._orchestrator.run_one_async(Path(song_path))
```

The orchestrator's `run_one_async(song_path, lyrics_path=None)` signature
stays — `LyricsFetchStage` now owns the resolution. The `lyrics_path` kwarg
becomes a manual override path used only by tests; production flow always
relies on the stage.

### `pikaraoke/pipeline/orchestrator.py` (no changes required)

The `lyrics_path` kwarg on `run_one_async` is preserved as a back-door for
tests and for any caller that wants to bypass selection / SRT scanning. When
provided, `LyricsFetchStage` should respect it (see edge cases below).

### Config: Genius API token

Follow the hidden-config pattern from commit 0bc73d27 ("Reject karaoke videos
from processing"). The token is a config-file-only entry — no CLI flag, no UI
control, no env var — settable by editing `config.ini` under the standard
`[USERPREFERENCES]` section.

**`pikaraoke/lib/preference_manager.py`** — add to `DEFAULTS`:

```python
DEFAULTS = {
    ...
    "blocked_processing_words": "",
    "genius_token": "",   # NEW
}
```

Empty string means "disabled". `apply_all` will hydrate
`Karaoke.genius_token` from config when present, defaulting to `""`.

**`pikaraoke/karaoke.py`** — add the constructor kwarg so `apply_all` has a
hydration target (mirrors how `blocked_processing_words` was added):

```python
def __init__(
    self,
    ...
    blocked_processing_words: str | None = None,
    genius_token: str | None = None,   # NEW
    ...
):
```

**Construction site for `GeniusClient`**: same place that builds
`ProcessingManager` in `karaoke.py` (after `apply_all` hydrates
`self.genius_token`, around line 170; `ProcessingManager` built at line
271). `GeniusClient` is always constructed (Design Decision 2), even
when the token is empty. Pass into `ProcessingManager` and make
available to routes via the existing `current_app` /
`get_karaoke_instance` plumbing.

```python
# karaoke.py, alongside other manager construction (after apply_all)
self.genius_client = GeniusClient(api_token=self.genius_token or "")
self.processing_manager = ProcessingManager(
    events=self.events,
    preferences=self.preferences,
    song_manager=self.song_manager,
    genius_client=self.genius_client,  # always a GeniusClient instance
    temp_dir=self.temp_dir,
    log_level=self.log_level,
)
```

When the token is empty, `self.genius_client` is a `GeniusClient` whose
`search()` returns `[]` and whose `fetch_lyrics()` raises
`GeniusUnavailable`. Routes call `search()` unconditionally; the template
renders the picker unconditionally; `LyricsFetchStage` calls
`fetch_lyrics()` unconditionally. No `None` checks anywhere.

**Example config snippet** (for documentation, not a separate file):

```ini
[USERPREFERENCES]
# Genius.com API token; obtain at https://genius.com/api-clients
# When set, enables Genius lyric selection on the search page.
genius_token = abc123xyz...
```

**No CLI flag**, **no env var**, **no separate config.ini for Genius** —
everything goes through `PreferenceManager`, identical to how
`blocked_processing_words` is handled.

______________________________________________________________________

## Edge cases & failure modes

| Case | Behavior |
| --- | --- |
| User picks Genius song; pipeline runs; Genius returns 500 | Stage logs warning, leaves choice file in place, falls through to SRT (or transcribe). Re-run will retry the choice. |
| User picks raw; YouTube SRT exists | SRT is preserved (LyricAlignStage skips writing one — but the existing one is fine). LyricAlignStage runs in transcription mode; ASS is generated from transcribed words. |
| User picks raw; YouTube SRT does not exist | Pipeline runs in transcription mode; pipeline-generated SRT is written. Same as today's no-SRT path. |
| User picks Genius; YouTube SRT exists | Genius wins. ASS is built from Genius-aligned words. SRT is preserved (not overwritten). |
| User picks nothing; YouTube SRT exists | Same as today: alignment to SRT-derived text. |
| User picks nothing; YouTube SRT does not exist | Same as today: transcription mode; pipeline writes SRT. |
| User picks lyrics, then cancels download | Choice file lingers in temp until reboot or manual sweep. Tiny on-disk cost. |
| User picks lyrics, reboots, then triggers download | Choice file may be gone (depends on temp policy). Falls back to SRT. Acceptable. |
| Same song re-processed after success | Choice file deleted on first success. Re-runs use SRT or transcribe — accepted limitation. |
| Manually-added library file (no `---<yt_id>` in name) | `_extract_yt_id` returns None → no choice lookup → SRT fallback path. Same as today. |
| Genius token absent | `Karaoke.genius_client` is a `GeniusClient("")` whose `search()` returns `[]` and `fetch_lyrics()` raises `GeniusUnavailable`. Picker renders with "No lyrics results found". Pipeline stage tries Genius fetch on choice files, gets `GeniusUnavailable`, falls through to SRT. No `None` checks needed (Design Decision 2). |
| Test passes `lyrics_path=` to `run_one_async` | Orchestrator pre-populates `ctx.artifacts["lyrics_path"]` (existing behavior). `LyricsFetchStage.run` short-circuits on `ctx.artifacts.get("lyrics_path") is not None` (Design Decision 5) and sets `lyrics_origin="override"` if not already set. |
| Two users pick lyrics for same yt_id concurrently | Last write wins (atomic rename). Acceptable — there's no "user A's choice" vs "user B's choice" identity in the system. |
| Genius lyrics word-count mismatches the vocal stem (ad-libs, BGV, etc.) | Existing `_match_words_to_lines` is count-based and will desynchronize. **Known limitation**, not new — same risk exists with SRT today. Worth a follow-up plan; out of scope here. |

______________________________________________________________________

## Testing

Following the project's test conventions (mocked I/O/subprocess, real
`EventSystem` and `PreferenceManager`):

**`tests/lib/test_genius.py` (new):**
- `GeniusClient.search` with mocked `lyricsgenius` returns filtered hits.
- `GeniusClient.search` returns `[]` on `requests` failure.
- `GeniusClient.search` with empty token returns `[]` immediately (no
  network call).
- `GeniusClient.fetch_lyrics` raises `GeniusUnavailable` on failure.
- `GeniusClient.fetch_lyrics` with empty token raises
  `GeniusUnavailable` immediately (no network call).
- `Karaoke` always exposes `genius_client` as a `GeniusClient` instance
  (even with empty token) — covered in `tests/test_karaoke.py`.
- Sidecar I/O: write/read/delete round-trip; atomic-write durability under a
  simulated mid-write crash (write tmpfile, kill before rename, expect
  `read_choice` to return either old value or None — never partial).

**`tests/pipeline/stages/test_lyrics_fetch.py` (new):**
- Branch (a): Genius selection → `lyrics_path` set, choice file deleted.
- Branch (a) failure: Genius raises → `lyrics_path` falls back to SRT,
  choice file preserved.
- Branch (b): raw mode → `lyrics_path = None`, origin = "none".
- Branch (c): no choice + SRT exists → `lyrics_path` points at SRT.
- Branch (c): no choice + no SRT → `lyrics_path = None`, origin = "none".
- `_extract_yt_id` covers both filename conventions plus the "no ID" case.
- Honors a pre-populated `ctx.artifacts["lyrics_path"]` (test override).
  Must use `is not None` check, not `in` (Design Decision 5).

**`tests/pipeline/stages/test_lyric_align.py` (edit / extend):**
- Genius-formatted input: structure parsed, headers stripped, alignment
  word count matches surviving lines.
- Conditional SRT: existing `subtitles/<stem>.en.srt` → no SRT written.
- Conditional SRT: missing → SRT written.
- Existing alignment / transcription tests keep passing.

**`tests/routes/test_search.py` (edit):**
- `/lyrics_search?q=foo` returns JSON with hits when token is set,
  `[]` when token is empty (always 200, never gated on `None`).
- `/lyrics_select` writes the sidecar with valid `yt_id` and `genius_id`.
- `/lyrics_select` rejects malformed yt_id with 400.

**Manual test plan:**
- [ ] Search "rick astley never gonna give you up", verify Genius dropdown
      populates with hits.
- [ ] Pick a Genius song, click Download, wait for processing.
- [ ] Confirm `karaoke/<stem>.ass` reflects Genius lyrics (line breaks match
      the dropdown selection).
- [ ] Confirm `subtitles/<stem>.en.srt` (YouTube's) is preserved untouched.
- [ ] Confirm `<temp>/lyric_choices/<yt_id>.json` is gone after success.
- [ ] Pick "Raw Transcription" on a different video; verify ASS is
      transcription-derived; verify YouTube SRT is preserved if present.
- [ ] Pick a Genius song with a deliberately bad token; verify the pipeline
      falls back to SRT alignment and the choice file remains.
- [ ] Search a video with no captions; pick raw; verify pipeline-generated
      SRT lands in `subtitles/`.

______________________________________________________________________

## Rollout

1. Land `lib/genius.py` + sidecar tests (no behavior change). Also add
   `extract_youtube_id()` to `metadata_parser.py` (Design Decision 6).
2. Land `LyricsFetchStage` + tests; wire into `processing_manager.py`. At
   this point existing flows are unchanged because no choice files exist
   yet — branch (c) is the only branch reachable from the UI.
3. Land `LyricAlignStage` edits (header parsing, conditional SRT) +
   `lib/genius_lyrics.py` (full `parse_genius_sections` port, Design
   Decision 7; `clean_genius_query`, Design Decision 8). **The
   `_load_lyrics` 2-tuple → 3-tuple change and its sole call site must
   land atomically in one commit** (Design Decision 9). Run the full
   test suite — both `lib/genius.py` and `LyricsFetchStage` tests must
   pass first because some existing alignment tests will need to switch
   to the new `_load_lyrics` return signature.
4. Land config plumbing: `genius_token` in `PreferenceManager.DEFAULTS`,
   matching kwarg in `Karaoke.__init__`, `GeniusClient` always
   constructed in `karaoke.py` and passed to `ProcessingManager`
   (Design Decision 2).
5. Land routes + template port: Select button, `openPreviewModal()`
   refactor, Download button inside modal, lyrics picker always visible
   (Design Decisions 1 and 2). No `{% if genius_client %}` gate.
6. Verify on a real install with a real token before merging.

No data migration required — sidecars are temp-only and existing artifacts
are unaffected.
