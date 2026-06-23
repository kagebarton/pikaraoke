"""Genius.com API client and selection-sidecar I/O.

``GeniusClient`` wraps ``lyricsgenius.Genius`` with a ``threading.Lock``
so the same instance can be shared safely across Flask request threads and
the pipeline orchestrator thread (the underlying ``requests.Session`` is
not thread-safe).

An empty ``api_token`` produces a client whose :meth:`search` always
returns ``[]`` and whose :meth:`fetch_lyrics` always raises
:class:`GeniusUnavailable`.  Callers never need to check for ``None`` —
see Design Decision 2.

The sidecar helpers (``write_choice``, ``read_choice``, ``delete_choice``)
are module-level functions because they are stateless; the call sites
(route handler, pipeline stage) are in different threads with no shared
object to inject into.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import lyricsgenius

from pikaraoke.lib.get_platform import get_temp_directory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class GeniusUnavailable(Exception):
    """Raised when Genius is configured but a request fails."""


# ---------------------------------------------------------------------------
# Data class for search hits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeniusHit:
    id: int
    title: str
    artist: str


@dataclass(frozen=True)
class GeniusSong:
    """A fetched song: lyrics plus the canonical title/artist."""

    text: str
    title: str
    artist: str


# ---------------------------------------------------------------------------
# GeniusClient
# ---------------------------------------------------------------------------


class GeniusClient:
    """Thread-safe wrapper around ``lyricsgenius.Genius``.

    Always constructed — even with an empty token — so callers never need
    to check for ``None``.  An empty token produces a client whose
    ``search()`` returns ``[]`` and ``fetch_lyrics()`` raises
    ``GeniusUnavailable`` immediately (no network call).
    """

    def __init__(self, api_token: str = "", timeout: float = 15.0) -> None:
        self._token = api_token
        self._timeout = timeout
        self._lock = threading.Lock()

        # Suppress noisy lyricsgenius INFO logs (e.g. "Done.")
        logging.getLogger("lyricsgenius").setLevel(logging.WARNING)

        if api_token:
            self._genius = lyricsgenius.Genius(api_token, timeout=timeout)
            # Headers ([Verse], [Chorus: Brian], etc.) are stripped server-side
            # by the lyricsgenius lib so the aligner sees only sung text — no
            # bracketed metadata to confuse whisper alignment.
            self._genius.remove_section_headers = True
            self._genius.skip_non_songs = True
        else:
            self._genius = None  # type: ignore[assignment]

    # -- Search -------------------------------------------------------------

    def search(self, query: str, limit: int = 8) -> list[GeniusHit]:
        """Search Genius for songs.  Returns ``[]`` on any failure.

        Filters: type == "song"; drops translation/cover artists when the
        user query already matches the blocked term (logic ported from
        prototype ``app.py:lyrics_search``).
        """
        if not self._token or self._genius is None:
            return []

        with self._lock:
            try:
                data = self._genius.search(query, per_page=20, type_="song")
            except Exception as e:
                logger.warning("Genius search failed: %s", e)
                return []

        if not data:
            return []

        query_has_genius = "genius" in query.lower()
        blocked_term = "translation" if query_has_genius else "genius"

        hits: list[GeniusHit] = []
        try:
            for h in (data.get("sections") or [{}])[0].get("hits", []):
                if h.get("type") != "song":
                    continue
                result = h.get("result", {})
                artist_name = result.get("artist_names") or result.get("primary_artist", {}).get(
                    "name", ""
                )
                if blocked_term in artist_name.lower():
                    continue
                hits.append(
                    GeniusHit(
                        id=result["id"],
                        title=result["title"],
                        artist=artist_name,
                    )
                )
                if len(hits) >= limit:
                    break
        except (KeyError, AttributeError, TypeError) as e:
            # Honor the documented "[] on any failure" contract: a malformed
            # response shape (None section, null primary_artist, hit missing
            # id/title) must not escape as an unhandled exception to callers.
            logger.warning("Genius search response parse failed: %s", e)
            return []

        return hits

    # -- Fetch lyrics -------------------------------------------------------

    def fetch_song(self, genius_id: int) -> GeniusSong:
        """Scrape a specific song id: lyrics plus its canonical title/artist.

        Raises :class:`GeniusUnavailable` on any error or when the scraped
        page yields empty lyrics.  Lyrics have section headers removed (see
        ``remove_section_headers`` in ``__init__``); the canonical
        title/artist feed the LRCLIB structured search.
        """
        if not self._token or self._genius is None:
            raise GeniusUnavailable("Genius API token not configured")

        with self._lock:
            try:
                song = self._genius.search_song(song_id=genius_id)
            except Exception as e:
                raise GeniusUnavailable(f"Genius fetch failed for id {genius_id}: {e}") from e

        if not song or not song.lyrics:
            raise GeniusUnavailable(f"Genius returned empty lyrics for id {genius_id}")

        return GeniusSong(text=song.lyrics, title=song.title or "", artist=song.artist or "")

    def fetch_lyrics(self, genius_id: int) -> str:
        """Scrape lyrics for a specific song id (text only).

        Thin wrapper over :meth:`fetch_song` for callers that don't need the
        canonical key.
        """
        return self.fetch_song(genius_id).text


# ---------------------------------------------------------------------------
# Selection sidecar I/O
# ---------------------------------------------------------------------------

CHOICES_SUBDIR = "lyric_choices"


def choices_dir() -> Path:
    """Return ``<get_temp_directory()>/lyric_choices/``, creating it if missing."""
    d = Path(get_temp_directory()) / CHOICES_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_choice(yt_id: str, payload: dict) -> Path:
    """Atomic write (tmpfile + rename) of choice JSON.

    Overwrites any existing choice for the same *yt_id*.
    """
    target = choices_dir() / f"{yt_id}.json"
    payload.setdefault("yt_id", yt_id)

    # Atomic write: write to a temp file in the same directory, then rename.
    fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), prefix=f".{yt_id}-", suffix=".json")
    try:
        import os

        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        # rename is atomic on POSIX when source and dest are on the same filesystem
        Path(tmp_path).rename(target)
    except Exception:
        # Clean up the temp file on failure
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
        raise

    return target


def read_choice(yt_id: str) -> dict | None:
    """Return the choice dict, or ``None`` if absent / unparseable."""
    target = choices_dir() / f"{yt_id}.json"
    if not target.is_file():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read choice file %s: %s", target, e)
        return None


def delete_choice(yt_id: str) -> None:
    """Idempotent removal of the choice file."""
    target = choices_dir() / f"{yt_id}.json"
    try:
        target.unlink(missing_ok=True)
    except OSError:
        pass
