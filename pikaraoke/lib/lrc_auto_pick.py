"""Which LRCLIB record, if any, times a song: the bar and the pick of plans/lrclib-fit-pick.md.

Every synced record a search returns is fitted to the words the transcriber heard
(:func:`srt_slice_fit.fit_slice`). A record passes the bar when it fits, at the
clip's own speed, with at most one mistimed line and no long stretch of heard words
that no line claims. The pick is made among the passing records, so the order here
is part of the bar. Pure: the records, the heard words and the clip length come in
as arguments, so the probe that measured the bar and the pipeline that will use it
run this one code.
"""

import math
from collections import Counter
from dataclasses import dataclass

from pikaraoke.lib.srt_slice_fit import (
    FITS,
    TRANSCRIBE,
    SliceFit,
    fit_slice,
    lrc_to_srt,
)

# The bar's two limits, fixed before any measurement under plans/lrclib-fit-pick.md
# ("The bar and the pick"). One mistimed line is a repeat or a one-word line the heard
# words place elsewhere; every record of such a song carries it. A longer unclaimed
# run is singing the record skips or stops short of.
MAX_MISTIMED = 1
MAX_UNCLAIMED_RUN = 12

# Why a record fails the bar, the first condition it fails.
NO_FIT, SPEED, MISTIMED, UNCLAIMED = "no_fit", "speed", "mistimed", "unclaimed"
REFUSALS = (NO_FIT, SPEED, MISTIMED, UNCLAIMED)


@dataclass(frozen=True)
class Entry:
    """One synced record with its fit, why the bar refused it (None: it passes), and the
    number of the search's synced records that carry its timing."""

    record: dict
    fit: SliceFit
    refusal: str | None
    timing_size: int

    @property
    def passes(self) -> bool:
        return self.refusal is None


def refusal(fit: SliceFit) -> str | None:
    """The first bar condition ``fit`` fails; None when it passes."""
    if fit.status != FITS:
        return NO_FIT
    if fit.speed != 1.0:
        return SPEED
    if len(fit.mistimed) > MAX_MISTIMED:
        return MISTIMED
    if fit.unclaimed_run > MAX_UNCLAIMED_RUN:
        return UNCLAIMED
    return None


def timing_key(synced: str) -> str:
    """The synced text with each line stripped and empty lines dropped.

    Records with equal keys are one timing re-uploaded: LRCLIB holds many copies of the
    same file under different albums.
    """
    return "\n".join(line for raw in synced.splitlines() if (line := raw.strip()))


def evaluate(records: list[dict], words: list[dict], clip_length: float) -> list[Entry]:
    """Every record with synced text, fitted to ``words`` (:func:`srt_slice_fit.heard_streams`'
    transcribe stream) on a clip ``clip_length`` seconds long.

    The records that pass come first, in pick order; the rest follow in the search's order.
    """
    synced = [r for r in records if r.get("syncedLyrics")]
    keys = [timing_key(r["syncedLyrics"]) for r in synced]
    sizes = Counter(keys)
    entries = []
    for record, key in zip(synced, keys):
        fit = fit_slice(lrc_to_srt(record["syncedLyrics"]), {TRANSCRIBE: words}, clip_length)
        entries.append(Entry(record, fit, refusal(fit), sizes[key]))
    passing = sorted((e for e in entries if e.passes), key=_pick_order)
    return passing + [e for e in entries if not e.passes]


def pick(records: list[dict], words: list[dict], clip_length: float) -> Entry | None:
    """The record that times the song, or None when no record passes the bar."""
    entries = evaluate(records, words, clip_length)
    return entries[0] if entries and entries[0].passes else None


def _pick_order(entry: Entry) -> tuple:
    """Fewer mistimed lines, then the timing most records carry, then the plainest record:
    the shorter track name and album name (a missing one counts as empty), then the lower id."""
    record = entry.record
    record_id = record.get("id")
    return (
        len(entry.fit.mistimed),
        -entry.timing_size,
        len(record.get("trackName") or ""),
        len(record.get("albumName") or ""),
        record_id if isinstance(record_id, int) else math.inf,
    )
