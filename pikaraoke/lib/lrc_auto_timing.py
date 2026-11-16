"""The LRCLIB check of a first-time Genius download (plans/lrclib-fit-pick.md, Phase 4).

One search, every synced record fitted to the words the transcriber heard, the pick of
:mod:`lrc_auto_pick`. Network, no file writes: the stage that calls it decides what lands in
the library. It imports no pipeline module and not ``library_regen``, which imports the align
stage, so what both need about the automatic sheet lives here.
"""

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pikaraoke.lib import lrc_auto_pick, lrclib
from pikaraoke.lib.lrc_auto_pick import Entry
from pikaraoke.lib.srt_slice_fit import TRANSCRIBE, heard_streams

logger = logging.getLogger(__name__)

# The bundle's ``lyrics.origin`` of a song timed from the record this check picked, and the
# name of its sheet in ``lyrics/``.
ORIGIN = "lrclib_auto_srt"
SHEET_SUFFIX = ".lrclib-auto.srt"

PICKED, NO_PICK, NO_RECORDS, SEARCH_FAILED, ERROR = (
    "picked",
    "no_pick",
    "no_records",
    "search_failed",
    "error",
)


def sheet_path(song: Path) -> Path:
    """Where the picked record's sheet lives, whether or not it exists."""
    return song.parent / "lyrics" / f"{song.stem}{SHEET_SUFFIX}"


@dataclass(frozen=True)
class AutoCheck:
    """What the check found. ``entries`` are the search's synced records, fitted, the ones
    that pass first in pick order (:func:`lrc_auto_pick.evaluate`); none on a failed search."""

    outcome: str
    query: str = ""
    entries: tuple[Entry, ...] = ()

    @property
    def entry(self) -> Entry | None:
        """The record that times the song, or None."""
        return self.entries[0] if self.outcome == PICKED else None

    def record(self) -> dict:
        """The bundle's record of the check, counts over the synced records. No lyric text."""
        refused = Counter(e.refusal for e in self.entries)
        timings = {lrc_auto_pick.timing_key(e.record["syncedLyrics"]) for e in self.entries}
        pick = None
        if self.entry is not None:
            fit = self.entry.fit
            pick = {
                **lrclib.record_meta(self.entry.record),
                "timing_size": self.entry.timing_size,
                "mistimed": len(fit.mistimed),
                "unclaimed_run": fit.unclaimed_run,
                "shift_run": fit.shift_run,
                "shift_s": fit.shift_s,
            }
        return {
            "outcome": self.outcome,
            "query": self.query,
            "records": len(self.entries),
            "timings": len(timings),
            "passing": sum(e.passes for e in self.entries),
            "refusals": {r: refused[r] for r in lrc_auto_pick.REFUSALS if refused[r]},
            "pick": pick,
        }


def check(genius: dict, words: list[dict], clip_length: float) -> AutoCheck:
    """Search LRCLIB for the song and pick the record that passes the bar, if any.

    ``genius`` is the Genius identity the lyrics stage recorded (``title``, ``artist``);
    ``words`` are the de-reverb gate's transcribe words, as the bundle stores them. Never
    raises: an unreachable LRCLIB gives ``search_failed`` and any other failure ``error``,
    and the song goes to the joint matcher either way.
    """
    query = ""
    try:
        query = lrclib.query_text(genius["title"], genius["artist"])
        heard = heard_streams({"transcribe_words": words}, None).get(TRANSCRIBE, [])
        entries = lrc_auto_pick.evaluate(lrclib.search_query(query), heard, clip_length)
    except lrclib.LrclibUnavailable as e:
        logger.warning("%s", e)
        return AutoCheck(SEARCH_FAILED, query)
    except Exception:
        logger.exception("LRCLIB timing check failed for query %r", query)
        return AutoCheck(ERROR, query)
    if not entries:
        return AutoCheck(NO_RECORDS, query)
    return AutoCheck(PICKED if entries[0].passes else NO_PICK, query, tuple(entries))
