# Genius Lyrics Integration Plan — Review of Issues & Recommendations

Reviewed against codebase at HEAD. Each issue is categorized by severity:
**🔴 Critical** — will cause runtime errors or data loss if shipped as-is.
**🟠 Significant** — will cause incorrect behaviour in real scenarios.
**🟡 Moderate** — design concern or missing piece that could bite later.
**🔵 Minor** — style, naming, or clarity improvements.

---

## 1. `lyricsgenius` is not declared as a dependency

**Severity: 🟡 Moderate**

`pyproject.toml` does not list `lyricsgenius` in `[project].dependencies`. It
happens to be installed in the dev environment (`pip list` shows 3.12.0), but
any clean install of pikaraoke will crash at import time with
`ModuleNotFoundError`.

**Recommendation:** Add `lyricsgenius>=3.0` to `pyproject.toml` dependencies,
OR gate the import behind a try/except and make `GeniusClient.enabled` return
`False` when the package is missing (graceful degradation). The second
approach avoids forcing a new transitive dependency on users who don't use
the Genius feature — the same pattern used by `audio-separator[gpu]` with its
optional extras bracket.

If gating: consider an optional-extra group:

```toml
[project.optional-dependencies]
genius = ["lyricsgenius>=3.0"]
```

and document that users need `pip install pikaraoke[genius]`.

---

## 2. `_convert_value` will corrupt the Genius API token

**Severity: 🔴 Critical**

`PreferenceManager._convert_value` auto-converts string values to `bool`,
`int`, or `float`. When the token is read from `config.ini`, the following
happens:

```python
# PreferenceManager._convert_value:
stripped = val.lstrip("-")
if stripped.isdigit():        # e.g. "123" → int(123) ← WRONG for a token
    return int(val)
if stripped.replace(".", "", 1).isdigit():  # e.g. "1.2" → float(1.2)
    return float(val)
```

The `DEFAULTS` entry is `""` (a string), so the *setter* path in `apply_all`
preserves string typing. But the *getter* path (`self.get(pref, default)`)
passes `default=""` to `get()`, and inside `get()` the code checks
`isinstance(default_value, str)` — only then does it return the raw string.
**This works only because the default is a string.** If anyone ever changes
the default to `None` (a natural "no value" sentinel), the token would be
auto-converted on read.

More importantly, `apply_all` itself calls `setattr` with the result of
`self.get(pref, default)`, which returns the correct string today. But the
`set()` method's auto-sync path also calls `_convert_value` on the value
passed by the user, which could mangle tokens that look numeric.

**Recommendation:** Add `genius_token` to the `set()` skip-list alongside
`volume`/`subtitle_delay`/`vocal_volume`, OR more robustly: add a
`STRING_ONLY` class-level set in `PreferenceManager` for keys that must never
be auto-converted:

```python
_STRING_ONLY_DEFAULTS = {"genius_token", "admin_password"}

def get(self, preference, default_value=None, section="USERPREFERENCES"):
    ...
    if preference in self._STRING_ONLY_DEFAULTS:
        return pref  # always return raw string
```

This also protects `admin_password` (which has the same latent bug — a
password of `"12345"` would become `int(12345)`).

---

## 3. Race between `/lyrics_select` write and pipeline read

**Severity: 🔵 Minor**

The plan says `/lyrics_select` writes the sidecar atomically (tmpfile + rename),
and `LyricsFetchStage` reads it. The timing window between "user clicks
Download" and "pipeline dequeues the song" can be **minutes** if the download
queue is long. During that window the user might:

1. Pick a Genius song for `yt_id=abc123`.
2. Click Download — the sidecar file is written.
3. Wait for the download queue.
4. Change their mind and pick a *different* Genius song for the same video.
5. The second `/lyrics_select` overwrites the first sidecar (last-write-wins,
   which is fine).

The plan's "last-write-wins" approach handles this correctly. No issue.

**Recommendation:** None needed.

---

## 4. `_extract_yt_id` regex is inconsistent with existing code

**Severity: 🟠 Significant**

The plan says `_extract_yt_id` should recognize two filename conventions:
`Title---<id>.mp4` and `Title [<id>].mp4`. But the existing
`metadata_parser.youtube_id_suffix()` already extracts YouTube IDs from both
conventions using the well-tested regex:

```python
re.search(r"(---[A-Za-z0-9_-]{11})$", stem)       # pikaraoke convention
re.search(r"(\s*\[[A-Za-z0-9_-]{11}\])$", stem)   # yt-dlp convention
```

And `DownloadManager` uses `get_youtube_id_from_url()` for its own extraction.
The plan doesn't reference either function — it proposes a new regex in a new
static method, introducing a third implementation of the same logic.

**Recommendation:** Reuse `metadata_parser.youtube_id_suffix()` (strip the
`---` prefix or `[`/`]` brackets to get the raw 11-char ID), or factor the
extraction into a shared utility that all three call sites use. Avoid
divergent regexes that drift apart over time.

---

## 5. `LyricsFetchStage` short-circuit for pre-populated `lyrics_path` is fragile

**Severity: 🟠 Significant**

The edge-case table says: *"Test passes `lyrics_path=` to
`run_one_async` — `LyricsFetchStage` should detect that artifact is already
set and short-circuit."* The plan's pseudocode for `LyricsFetchStage.run()`
does **not** include this check. The orchestrator sets
`ctx.artifacts["lyrics_path"] = lyrics_path` at line 212 *before* any stage
runs. So if `lyrics_path` is passed, `LyricsFetchStage` would overwrite it
with its own resolution (branch c — SRT fallback), discarding the test
override.

**Recommendation:** Add an explicit guard at the top of
`LyricsFetchStage.run()`:

```python
def run(self, ctx: StageContext) -> None:
    if "lyrics_path" in ctx.artifacts:
        logger.debug("lyrics_path pre-populated; skipping fetch stage")
        if "lyrics_origin" not in ctx.artifacts:
            ctx.artifacts["lyrics_origin"] = "override"
        return
    # ... rest of the stage logic
```

---

## 6. `lyricsgenius.Genius` initialization and thread safety

**Severity: 🟡 Moderate**

The plan says `GeniusClient` lazily initializes `lyricsgenius.Genius` and
that the same instance is shared between the Flask route (main thread) and
the pipeline (orchestrator thread). `lyricsgenius.Genius` is not documented
as thread-safe. The prototype creates it once at module level (single-threaded
Flask dev server), but the production app uses real threading.

The `search()` method calls `lyricsgenius.Genius.search()`, which modifies
internal request-session state. If two search requests arrive concurrently
(different Flask threads) while the pipeline thread calls `fetch_lyrics()`,
there could be shared-state corruption.

**Recommendation:** Either:
- Protect `GeniusClient.search` and `fetch_lyrics` with a `threading.Lock`
  (simple, prevents concurrent Genius API calls, which is also polite to
  their rate limits), or
- Create per-call `lyricsgenius.Genius` instances from the token (wasteful
  but safe).

A lock is the simpler approach and unlikely to be a bottleneck since Genius
API calls are inherently serial (one at a time per token).

---

## 7. `_load_lyrics` return type change breaks existing call sites silently

**Severity: 🟠 Significant**

The plan changes `_load_lyrics` from returning `tuple[str, str]` to
`tuple[str, str, list[dict] | None]`. The current call site in
`LyricAlignStage.run()` at line 63:

```python
lyrics_text, lyrics_format = self._load_lyrics(lyrics_path)
```

would crash with `ValueError: too many values to unpack` at runtime if the
change is deployed without updating this call site. The plan mentions this
change in the `LyricAlignStage` edit section, but the rollout plan doesn't
call out that this is a **hard breaking change** that requires both files to
land atomically in the same commit.

**Recommendation:** The rollout plan says "Land `LyricAlignStage` edits" as
step 3, but steps 1–2 (`lib/genius.py` and `LyricsFetchStage`) don't touch
`lyric_align.py`. If someone merges step 2 without step 3, nothing breaks
yet. But step 3 itself must change the return signature AND update the call
site in the same commit — this should be called out explicitly. Consider
making the new parameter optional with a default of `None` to maintain
backward compatibility during incremental rollout:

```python
def _load_lyrics(self, lyrics_path: Path, parse_structure: bool = False
                ) -> tuple[str, str, list[dict] | None]:
```

---

## 8. No `lyricsgenius` timeout configuration

**Severity: 🟡 Moderate**

The prototype hardcodes `timeout=10` in `lyricsgenius.Genius(_GENIUS_TOKEN,
timeout=10)`. The plan's `GeniusClient.__init__` signature only takes
`api_token`, with no timeout parameter. The `lyricsgenius` default timeout
is `None` (no timeout), which means a stalled Genius API call could block
the pipeline indefinitely.

**Recommendation:** Add a `timeout` parameter to `GeniusClient.__init__`
with a sensible default (e.g., 15 seconds), and pass it through to the
`lyricsgenius.Genius` constructor. This is especially important because the
plan explicitly states that the Genius HTTP call is not wrapped in a cancel
phase — a stuck call would block the entire pipeline.

---

## 9. Choice file temp directory lifecycle is underspecified

**Severity: 🟡 Moderate**

The plan uses `get_temp_directory()` for the choice sidecar path. On Linux,
`get_temp_directory()` typically returns `/tmp/pikaraoke/` (based on
`temp_dir` preference or system default). The plan notes that "choice files
linger in temp until reboot or manual sweep" — but `/tmp` on many Linux
systems is cleaned by `tmpfiles.d` only for files older than 10 days, not at
reboot. If the app runs continuously (a karaoke machine), stale choice files
could accumulate indefinitely.

**Recommendation:** Add cleanup logic — either:
- Delete the entire `lyric_choices/` directory on app startup (before any
  pipeline runs), or
- Add a timestamp to choice files and prune files older than, say, 24 hours
  during `ProcessingManager.start()`, or
- Since choice files are tiny (<1KB), document the accumulation as
  acceptable and leave it.

---

## 10. Prototype's `regex_tidy` usage is lossy for Genius search queries

**Severity: 🟡 Moderate**

The prototype's `/lyrics_search` route calls `regex_tidy()` on the query
before sending it to Genius. `regex_tidy` is designed for **cleaning
filenames**, not for preparing search queries — it strips parenthetical
content, bracketed content, noise words, and trailing dashes. This can
remove meaningful query terms:

- `"Bohemian Rhapsody (Official Video)"` → `"Bohemian Rhapsody"` ✓
- `"(I Can't Help) Falling In Love"` → `"Falling In Love"` ✗ — the
  parenthetical "(I Can't Help)" is part of the actual title
- `"Celine Dion - My Heart Will Go On (Love Theme from Titanic)"` →
  `"Celine Dion - My Heart Will Go On"` — loses "Titanic" context

The prototype's code at line 129:
```python
query = regex_tidy(request.args.get("q", "").strip()) or request.args.get("q", "").strip()
```
falls back to the raw query if `regex_tidy` produces an empty string, but
does not fall back if `regex_tidy` merely strips too much.

**Recommendation:** For Genius search, use a lighter cleaning function that
only removes YouTube-specific noise words (from `NOISE_WORDS`) but preserves
parenthetical content and bracketed content, since those are meaningful in
song titles. Something like:

```python
def clean_genius_query(query: str) -> str:
    """Light clean for Genius search — preserves title structure."""
    text = EMOJI_PATTERN.sub("", query)
    text = NOISE_PATTERN.sub("", text)
    return re.sub(r"\s+", " ", text).strip()
```

---

## 11. Template context: `genius_enabled` plumbing is unspecified

**Severity: 🟠 Significant**

The plan says the search template receives `genius_enabled` from the route,
and hides the lyric picker when `False`. But the current `search()` route
(in `pikaraoke/routes/search.py`) doesn't pass any `genius_enabled` variable
to `render_template()`. The plan doesn't specify where this variable comes
from.

The route currently gets the Karaoke instance via `get_karaoke_instance()`,
which returns `current_app.config["KARAOKE_INSTANCE"]`. The plan would need
to either:
- Add `k.genius_client.enabled` (or `k.genius_client` itself) to the render
  context, or
- Add a property/method on the `Karaoke` class that exposes the enabled
  state.

**Recommendation:** Add the plumbing explicitly in the plan. The simplest
approach:

```python
# In search route:
return render_template(
    "search.html",
    ...
    genius_enabled=k.genius_client.enabled if hasattr(k, 'genius_client') else False,
)
```

The `hasattr` guard prevents crashes when running without the Genius feature
initialized. Or make it a `Karaoke` property so routes don't need to know
about `GeniusClient` internals.

---

## 12. The `lyrics_select` route's yt_id validation is underspecified

**Severity: 🟡 Moderate**

The plan says `lyrics_select` should validate that `yt_id` is "the 11-char
YouTube ID". But it doesn't specify the validation regex. YouTube IDs use
the character set `[A-Za-z0-9_-]` (11 chars). The existing
`get_youtube_id_from_url` in `youtube_dl.py` uses a different extraction
pattern. Without an explicit regex, the validation could be too strict
(rejecting valid IDs with `-` or `_`) or too loose (accepting non-YouTube
11-char strings).

**Recommendation:** Define the validation regex explicitly in the plan:

```python
_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
```

and reuse it in both the route and `_extract_yt_id`.

---

## 13. `GeniusClient.fetch_lyrics` uses `search_song(song_id=id)` — fragile API

**Severity: 🟡 Moderate**

The plan correctly notes that `_genius.song(id)` only returns metadata, and
`search_song(song_id=id)` scrapes the page for lyrics. This is the same
approach as the prototype. However, `search_song(song_id=id)` is an
**undocumented usage** of `lyricsgenius` — the library's public API for
`search_song` expects title/artist strings, and `song_id` is a kwarg
shortcut that's maintained but not part of the stable contract.

If `lyricsgenius` changes how `search_song(song_id=...)` works (e.g.,
switching from page scraping to the API), the lyrics fetch would silently
start returning empty strings.

**Recommendation:** Wrap the `search_song` call with a check that the
returned `song.lyrics` is non-empty, and raise `GeniusUnavailable` if it's
empty — treating "lyrics present but empty" as a failure case, not a
success. The prototype doesn't check for this (it just writes whatever it
gets, including empty strings).

```python
def fetch_lyrics(self, genius_id: int) -> str:
    song = self._genius.search_song(song_id=genius_id)
    if not song or not song.lyrics:
        raise GeniusUnavailable(f"Genius returned no lyrics for id={genius_id}")
    return song.lyrics
```

---

## 14. `lyrics_origin` artifact is written but never consumed

**Severity: 🔵 Minor**

The plan introduces `ctx.artifacts["lyrics_origin"]` with values `"genius"`,
`"srt"`, or `"none"`, but no stage or downstream code reads it. It's purely
informational at this point.

**Recommendation:** This is fine as a forward-looking artifact (future
diarization work might consume it), but the plan should explicitly note it
as inert — otherwise reviewers will waste time looking for a consumer that
doesn't exist.

---

## 15. SRT conditional-write logic may surprise users on re-process

**Severity: 🟡 Moderate**

The plan says: "SRT write: only when `subtitles/<stem>.{en.,}srt` is absent."
This means if a song was originally downloaded with YouTube's auto-caption
SRT, and the user later re-processes it (e.g., after a pipeline upgrade),
the pipeline will **never** update the SRT, even if the pipeline's
transcription would be better than the original auto-captions.

The plan acknowledges this in "Out of scope" as "An admin 'regenerate SRT'
toggle." But the conditional-write logic is *inside* `LyricAlignStage` as a
filesystem check — there's no easy way for a future toggle to override it
without modifying the stage.

**Recommendation:** Instead of a pure filesystem check, make the SRT-write
decision based on a controllable artifact:

```python
# In LyricsFetchStage:
ctx.artifacts["srt_write_policy"] = "skip_if_exists"  # or "always" or "never"
```

Then `LyricAlignStage._should_write_srt` reads this policy instead of doing
its own filesystem check. This makes the "regenerate SRT" toggle trivial to
implement later (just set the policy to `"always"`).

---

## 16. No CSRF protection on `/lyrics_select` POST

**Severity: 🟡 Moderate**

The plan adds a POST route at `/lyrics_select` that writes a file to disk.
The existing `/download` route also accepts POST, so this may be consistent
with the app's current security posture. However, a cross-site request could
cause a malicious sidecar file to be written, which would then cause the
pipeline to fetch from an attacker-chosen Genius song ID.

**Recommendation:** This is low-impact (the attacker can only cause the
pipeline to fetch a Genius song, not arbitrary URLs), but worth noting for
consistency. If the app adds CSRF tokens in the future, include this route.

---

## 17. `GeniusClient` construction site in `karaoke.py` is ambiguous

**Severity: 🟠 Significant**

The plan says in the Config section:

```python
# karaoke.py, alongside other manager construction
self.genius_client = GeniusClient(
    api_token=self.preferences.get_or_default("genius_token") or None
)
```

But `self.preferences.apply_all()` is called at line 169 of `karaoke.py`,
**before** the ProcessingManager is constructed at line 271. The
`genius_token` attribute on `self` would be hydrated by `apply_all` at that
point. However, the plan also says `GeniusClient` should be passed to
`ProcessingManager`, which is constructed at line 271.

The ambiguity is: **where exactly** in `__init__` should `GeniusClient` be
constructed? If it's constructed after `apply_all` but before
`ProcessingManager`, the token is available. But the plan's pseudocode
suggests constructing it "alongside other manager construction" which is at
line 271+ — by which point `self.genius_token` is set. This works, but the
plan should be explicit about the ordering constraint.

**Recommendation:** Add a comment to the plan specifying the exact
insertion point:

```python
# After apply_all() at line 170, before ProcessingManager at line 271:
self.genius_client = GeniusClient(
    api_token=self.genius_token or None  # hydrated by apply_all
)
```

Note the subtle bug: `self.genius_token` will be `""` (empty string) when
not configured, and `"" or None` evaluates to `None` — which is correct. But
if `apply_all` stores `0` (due to the `_convert_value` bug in issue #2), then
`0 or None` evaluates to `None`, which also happens to be correct by
coincidence. Don't rely on this coincidence — fix issue #2 first.

---

## 18. `GeniusClient.enabled` as a `@property` is incorrect for the proposed API

**Severity: 🔵 Minor**

The plan defines `enabled` as a `@property`:

```python
@property
def enabled(self) -> bool:
    """True if a token was provided. UI hides the picker when False."""
```

But `enabled` only checks for token presence. It doesn't check whether
`lyricsgenius` is importable. If the package is not installed (issue #1),
calling `GeniusClient(None)` would succeed, but any `.search()` or
`.fetch_lyrics()` call would fail at the `import lyricsgenius` inside those
methods.

**Recommendation:** Make `enabled` check both conditions:

```python
@property
def enabled(self) -> bool:
    return self._api_token is not None and self._genius is not None
```

Where `self._genius` is `None` when either the token is absent or the import
failed.

---

## 19. Prototype vs. production template structure mismatch

**Severity: 🟠 Significant**

The prototype's `search.html` places the lyrics picker **inside the preview
modal** (lines 736–756 of the prototype template). The user must click a
search result's thumbnail to open the modal, and only then sees the lyrics
dropdown. But the production template doesn't have a "Select" button — it
has a "Download" button directly on each result row.

The plan says to port the picker from the prototype, but the prototype's
picker lives in a modal that the production template opens differently
(the production template already has a preview modal at line 765, but it
only contains the video player — no lyrics UI).

**Recommendation:** The plan should specify whether the lyrics picker will
be:
1. **Inside the existing preview modal** (prototype approach — requires
   user to click the thumbnail first, adding a step to the workflow)
2. **Inline per-result** (a dropdown directly on each search result row —
   more discoverable but more cluttered)

The plan mentions "per-result selectize dropdown" in the data flow, which
suggests option (2), but the prototype reference points to option (1). This
ambiguity could lead to significant rework during the port.

---

## 20. Choice file deletion on success prevents re-trying with a different selection

**Severity: 🟡 Moderate**

The plan says the choice file is deleted on pipeline success (branch a and
branch b). This means if the user downloads a song, the pipeline runs
successfully, and the user later wants to re-process with different lyrics
(e.g., they originally used SRT but now want to try Genius), the choice
file is gone and they must re-select from the search page.

The plan acknowledges this in the edge-case table: *"Same song
re-processed after success — Choice file deleted on first success. Re-runs
use SRT or transcribe — accepted limitation."*

**Recommendation:** This is acceptable for v1, but the plan should document
the user-facing workaround: to change lyrics source on an existing song,
the user must re-download it. This is a significant UX cost that may
surprise users. Consider persisting the choice in the database (not just
the temp sidecar) for future work.

---

## Summary

| # | Issue | Severity |
|---|-------|----------|
| 1 | `lyricsgenius` not declared as dependency | 🟡 Moderate |
| 2 | `_convert_value` will corrupt the Genius API token | 🔴 Critical |
| 3 | Race between `/lyrics_select` write and pipeline read | 🔵 Minor |
| 4 | `_extract_yt_id` regex diverges from existing code | 🟠 Significant |
| 5 | `LyricsFetchStage` doesn't short-circuit on pre-populated `lyrics_path` | 🟠 Significant |
| 6 | `lyricsgenius.Genius` thread safety | 🟡 Moderate |
| 7 | `_load_lyrics` return type change is a hard break | 🟠 Significant |
| 8 | No `lyricsgenius` timeout configuration | 🟡 Moderate |
| 9 | Choice file temp directory lifecycle | 🟡 Moderate |
| 10 | `regex_tidy` is too aggressive for Genius search queries | 🟡 Moderate |
| 11 | `genius_enabled` template context plumbing missing | 🟠 Significant |
| 12 | `yt_id` validation regex underspecified | 🟡 Moderate |
| 13 | `search_song(song_id=)` is an undocumented API usage | 🟡 Moderate |
| 14 | `lyrics_origin` artifact is inert | 🔵 Minor |
| 15 | SRT conditional-write logic has no override mechanism | 🟡 Moderate |
| 16 | No CSRF protection on `/lyrics_select` | 🟡 Moderate |
| 17 | `GeniusClient` construction site ordering is ambiguous | 🟠 Significant |
| 18 | `enabled` property doesn't check importability | 🔵 Minor |
| 19 | Prototype vs. production template structure mismatch | 🟠 Significant |
| 20 | Choice file deletion prevents re-trying with different selection | 🟡 Moderate |

**Critical issue to fix before implementation:** #2 (`_convert_value`
corrupting the token) — this is a latent bug that already affects
`admin_password` and will affect `genius_token` too.

**Most impactful design decision to resolve:** #19 (where the lyrics picker
lives in the UI) — this determines the shape of the template port and
should be settled before writing any HTML.
