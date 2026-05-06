# Clarifications: NW Matching & Diarization Port

Post-review, post-feedback list of what's still open before implementation.
Anything struck through is resolved and removed. Anything remaining is an
actual open question.

---

## ~~1. `_MIN_WORD_PROBABILITY` location~~

**Status: RESOLVED.** Stays in `word_alignment.py` as the canonical value.
`whisper_worker.py` still reads it via a module-level import in step 1; the
plan already lists `min_whisper_word_probability` in `PipelineConfig` so the
caller can override if needed. The clarifications file proposed moving it to
config; the feedback correctly noted that a logic-specific default in the module
is fine, and the override lives in config anyway.

---

## ~~2. `is_segment_first` nudge guard dead code / semantic shift~~

**Status: RESOLVED.** The review proposed adding `is_segment_boundary_first` to
preserve the old nudge behavior. That was rejected as over-engineering. Instead,
the plan was updated to document the semantic shift: after
`_reset_segment_first_flags`, `is_segment_first` always means "first word of the
lyric line" and the nudge becomes deterministic. The old guard (checking
`abs(word_start - prev_end - lead_in) < 0.05`) becomes almost-always-true and
can be removed; if `first_word_nudge_cs > 0`, every line now gets the nudge.
This is the intended prototype behavior.

---

## 3. Missing line-count guard

**Status: RESOLVED BY DESIGN (no change).** The prototype asserts
`len(line_objects) == len(genius_lines)`. The plan uses a zip that silently
truncates. The feedback from the user (via AskUserQuestion earlier) explicitly
chose "best-effort zip and continue silently" over "hard-fail the alignment
stage". The clarifications file argued for a guard; the feedback confirms the
current silen-zip behavior is deliberate. No change.

---

## 4. Empty `words` lists — default `start`/`end`

**Status: RESOLVED.** The plan already specifies `start`/`end` are interpolated
from neighbors for empty lines, which is the same as the prototype's behavior.
No additional clarification needed.

---

## 5. `_extract_words` vs `_segments_to_line_objects` duplication

**Status: RESOLVED.** These stay in `whisper_worker.py`. `word_alignment.py` only
contains the NW matching machinery (`match_words_to_lines`, `_needleman_wunsch`,
scoring, etc.). There is no duplication.

---

## 6. Test gap: `_segments_to_line_objects` speaker field init

**Status: ADDED to plan §8.** Test case `test_segments_to_line_objects_initializes_speaker_fields`
now covers this.

---

## 7. Test gap: align_refine return shape update

**Status: ADDED to plan §8.** Explicit note added: existing tests that send
line_object payloads via `result_send.send(...)` must be updated to send a flat
word list, and assertions changed from `result[0]["text"]` to `result[0]["word"]`.
Run `grep -n align_refine tests/unit/test_whisper_worker.py` to enumerate.

---

## ~~8. Speaker colors as `tuple` vs `list`~~

**Status: RESOLVED.** Already specified as `tuple[str, ...]` in the plan. No
issue.

---

## ~~9. Style name spacing — collapse multiple underscores~~

**Status: RESOLVED.** The plan now uses `_UNSAFE_CHAR_RE = re.compile(r"[^\w]+")`
and `_safe_style_name(label)` that collapses multiple underscores (e.g.
`Kevin & AJ` -> `Karaoke_Kevin_AJ` rather than `Karaoke_Kevin___AJ`).

---

## ~~10. Color overflow (more speakers than colors)~~

**Status: RESOLVED.** Plan says to wrap with modulo and log a warning. Silent
wrapping is not acceptable.

---

## 11. Cancellation path safety

**Status: NO CHANGE NEEDED.** The plan notes cancellation is tag-based
(`("ok" / "cancelled" / "error")`) and the payload shape change doesn't affect
that. The orchestrator reads `result[0]` (the tag), not `result[1]`, so changing
`list[line_obj]` to `list[word]` in the success case is safe.

---

## 12. Interpolation for large unaligned gaps

**Status: RESOLVED BY PROTOTYPE.** The prototype `match_words_to_lines` already
does simple neighbor interpolation: `prev_end = line_objects[j]["end"]` and
`next_start = line_objects[k]["start"]` for the nearest lines with words. The
plan inherits this verbatim. No change needed.

---

## 13. `is_segment_first` docstring update

**Status: DONE in plan.** The docstring for `_reset_segment_first_flags` now
documents the semantic shift directly. No special-casing needed elsewhere.

---

## Summary of remaining open questions

None. Every item from both the original clarifications file and the review
feedback has been either resolved in the plan or explicitly dismissed with a
design rationale.

If you believe any of the above should remain open, or if new questions
arise during implementation, the correct next step is to re-open with a single
specific issue and a concrete proposed change.
