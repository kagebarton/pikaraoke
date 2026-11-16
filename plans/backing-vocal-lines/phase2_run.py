"""Run ``scripts/regen_alignment_bundles.py`` with three observers on the cue rescue.

From the root of the tree under test (the "before" worktree or this one), unbuffered so the
driver's per-song header lands in the log in order with the logger's lines::

    python -u <this file> <scratch folder> --song=<id> ... --yes

It is the driver's own ``main()``; nothing is replaced. Each observer calls the original with the
same arguments, returns what it returned, and logs one ``PHASE2 <kind> <json>`` line, because the
bundle keeps no per-line count of guessed words and no record of why a retry's start moved:

- ``guessed``: from ``_guess_missing_words``, once per song: ``words`` is ``{line_id: words
  guessed}`` and ``tokens`` ``{line_id: indices of the tokens that had no timed word}``.
- ``start_bounded``: per retry, the start bound, the aligner's first word start, the start kept
  (None: refused) and whether the transcriber's confirmation lifted the bound.
- ``heard_aimed``: per rule B call, the shift and whether the retry was kept.

Line ids are the rescue's own: the song's new ids on the "after" tree.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from pikaraoke.lib import cue_align  # noqa: E402
from scripts import regen_alignment_bundles as driver  # noqa: E402

log = logging.getLogger("phase2")


def note(kind: str, **fields) -> None:
    log.info("PHASE2 %s %s", kind, json.dumps(fields))


_guess_missing_words = cue_align._guess_missing_words
_timed_slots = cue_align._timed_slots
_start_bounded = cue_align._Rescue.start_bounded
_heard_aimed_line = cue_align._Rescue.heard_aimed_line


# The tokens without a timed word, by the identity of the line's word list that was tested.
_missing: dict[int, tuple[list, list[int]]] = {}


def timed_slots(words, toks):
    slots = _timed_slots(words, toks)
    _missing[id(words)] = (words, [k for k, slot in enumerate(slots) if slot is None])
    return slots


def guess_missing_words(out, windows, line_toks, max_word_dur):
    _missing.clear()
    owner = {id(obj["words"]): obj["line_id"] for obj in out}
    guessed = _guess_missing_words(out, windows, line_toks, max_word_dur)
    tokens = {owner[i]: missing for i, (_, missing) in _missing.items() if owner.get(i) in guessed}
    note("guessed", words=guessed, tokens=tokens)
    return guessed


def start_bounded(self, raw, out, shift):
    fixed, lifted = _start_bounded(self, raw, out, shift)
    lid = raw["line_id"]
    note(
        "start_bounded",
        line_id=lid,
        shift=shift,
        bound=cue_align._start_bound(out, self.cue_spans, lid, self.offset, shift),
        raw_start=raw["words"][0]["start"] if raw["words"] else None,
        start=fixed["words"][0]["start"] if fixed else None,
        lifted=lifted,
    )
    return fixed, lifted


def heard_aimed_line(self, obj, out, placed, shift):
    fixed = _heard_aimed_line(self, obj, out, placed, shift)
    note("heard_aimed", line_id=obj["line_id"], shift=shift, kept=fixed is not None)
    return fixed


cue_align._guess_missing_words = guess_missing_words
cue_align._timed_slots = timed_slots
cue_align._Rescue.start_bounded = start_bounded
cue_align._Rescue.heard_aimed_line = heard_aimed_line

if __name__ == "__main__":
    sys.exit(driver.main())
