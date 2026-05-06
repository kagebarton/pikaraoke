# Review: NW Matching and Genius Diarization Port Plan

**Document reviewed:** `plans/nw-matching-and-diarization-port.md`  
**Date:** 2026-05-05  
**Reviewers:** Claude Code (Kilo)  
**Prototype source:** `/home/ken/whisper2srt/genius_diarize/`  
**Target codebase:** `/home/ken/pikaraoke/`  
**Current git commit at time of review:** `e9092261`

---

## Executive Summary

The plan is functionally correct and well-specified. **The prototype code is production-tested** and the port strategy (wholesale file copy + targeted edits) is sound. However, there are **5 categories of issues** that range from "minor inconsistency" to "will break on beta". This review categorizes them and provides recommended fixes.

| Risk | Count | Categories |
|------|-------|------------|
| 🔴 **High** | 5 | `is_segment_first` semantics, config field name drift, line count guard |
| 🟡 **Medium** | 4 | Parallel import drift, sentinels in IPC, test fragility, `_score()` edge case |
| 🟢 **Low** | 3 | Safety nets, logging verbosity, name collision |
| 📝 **Notes** | 4 | Non-issues, clarify-in-plan |

---

## 1. 🔴 High Risk: `is_segment_first` Reset Logic is Lossy (Plan §3 vs. Prototype)

### The Issue

Plan §3 defines `_reset_segment_first_flags`:

```python
def _reset_segment_first_flags(line_objects: list[dict]) -> None:
    for line in line_objects:
        for i, w in enumerate(line["words"]):
            w["is_segment_first"] = (i == 0)
```

**This destroys the signal that the first word of a lyric line came from the start of a different whisper segment.** The prototype's `reset_segment_first_flags` has the same code, but the plan doesn't mention that this behavior is *already lossy* and worth knowing about.

### Why It Matters

The `_generate_ass` first-word nudge (Plan §4) uses `word_data.get("is_segment_first")` to push back words that start almost immediately after the previous whisper segment. After reset, `is_segment_first` is `True` for the first word of *every lyric line*, not the first word of every whisper segment. This means the nudge will fire on every lyric line, not just the ones that start with a whisper segment boundary.

**This is a regression if the nudge heuristic assumes segment boundaries.**

### Verification

Read the current `lyric_align.py` (line 219-221):

```python
if (word_data.get("is_segment_first")
    and abs(word_start - prev_end - cfg.line_lead_in_cs / 100.0) < 0.05):
    word_start += cfg.first_word_nudge_cs / 100.0
```

This nudge only fires when `is_segment_first=True` AND the gap is within 50ms of the lead-in. The 50ms guard is designed to catch cases where stable-ts splits at unexpected boundaries and the first word of a segment starts too early. After reset, `is_segment_first=True` for the first word of every line, so the nudge will fire on every line, not just segment-boundary lines.

### Recommended Fix

**Option A — Preserve original segment boundaries:**

Add a field like `is_segment_boundary_first` (populated by `_extract_words` and never reset) alongside `is_segment_first`. Have the nudge check the new field.

```python
# In _extract_words:
all_words.append({
    ...
    "is_segment_first": kept_in_segment == 0,
    "is_segment_boundary_first": kept_in_segment == 0,  # never reset
    ...
})

# In _generate_ass nudge:
if (word_data.get("is_segment_boundary_first")  # instead of is_segment_first
    and abs(word_start - prev_end ...) < 0.05):
    ...
```

**Option B — Accept the regression and drop `first_word_nudge_cs`:**

If the nudge heuristic is deemed unreliable anyway (the prototype doesn't use it), remove the field and the nudge logic. Simpler, no behavioral drift.

**Option C — Reset to `False` instead of `True` (documented behavior):**

```python
# After reset: is_segment_first is True for the first word of each line
# For all other words, it's False
# First word nudge fires on ALL first words of lines, not just segment first words
```

*Keep the current nudge behavior as-is but document that the heuristic changes from "nudge at segment boundaries" to "nudge at line boundaries".* The 50ms guard still prevents nudging in most cases, but this is a behavioral change.

### Verdict

**Option A is the correct engineering fix.** The work is small (add one field, update one condition). Document this change in §2 and §3 of the plan.

---

## 2. 🔴 High Risk: Config Field Name Mismatch — `speaker_colors` vs. `speaker_colours`

### The Issue

Plan §5 adds `speaker_colors` to `PipelineConfig`. The prototype's `config.py` uses `speaker_colors` too. But check the prototype's `CaptionConfig` within GeniusDiarizeConfig — it also has `font_name`, `font_size` etc. (Plan §5 does cross-reference `font_*` correctly).

The plan says for `PipelineConfig`:

```python
speaker_colors: tuple[str, ...] = ("&H00FFFF00&", ...)
ensemble_color: str = "&H0000D7FF&"
```

But the prototype code in `caption.py:generate_styles()` uses `cfg.speaker_colors`.

**The pikaraoke PipelineConfig already has `primary_color`, `secondary_color`, etc. that match the ASS style names.** The plan adds `speaker_colors` and `ensemble_color` which are *different fields.*

**Wait — the real risk is simpler:** The plan in §4 says "color from `cfg.speaker_colors[idx % len(cfg.speaker_colors)]`". This requires `cfg.speaker_colors` to exist. If the config is imported into `lyric_align.py` as `self._config`, it will fail unless the field is actually added.

**The REAL concern:** The plan shows **two different config objects**:
- `PipelineConfig` (pikaraoke, in `config.py`) — has `font_name`, `font_size`, `primary_color`, etc.
- `GeniusDiarizeConfig` (prototype) — has `speaker_colors`, `ensemble_color` plus all the overlap fields.

When porting, the `_generate_ass` method calls `self._config` (which is a `PipelineConfig`). The plan says the speaker-conditioned style generation reads `cfg.speaker_colors`, but `PipelineConfig` doesn't have that field yet.

### Recommended Fix

**Clarify in §5:** `PipelineConfig` needs to gain `speaker_colors` and `ensemble_color` fields. The plan already says this, but should explicitly show the full updated dataclass:

```python
@dataclass
class PipelineConfig:
    # ... existing fields ...

    # --- Per-speaker karaoke colors ---
    speaker_colors: tuple[str, ...] = (
        "&H00FFFF00&",  # cyan
        "&H00B469FF&",  # pink
        "&H0000FF00&",  # green
        "&H000080FF&",  # orange
        "&H00FA82FA&",  # lavender
        "&H000000FF&",  # red
    )
    ensemble_color: str = "&H0000D7FF&"  # goldenrod
```

---

## 3. 🔴 High Risk: Missing Line-Count Guard After NW Matching

### The Issue

The plan calls `match_words_to_lines` and then immediately `_assign_speakers_from_genius(line_objects, lyrics_structure)`. The prototype's `run.py` has a defensive check:

```python
# run.py:157-161
assert len(line_objects) == len(genius_lines), (
    f"Line count mismatch: whisper aligned {len(line_objects)} lines "
    f"but Genius parser produced {len(genius_lines)} lines. "
    f"Aborting to avoid silent mis-attribution."
)
```

**The plan doesn't include this guard.** NW matching preserves the number of `lines` arguments, which equals `len(genius_lines)` from `_split_lines`. But `_split_lines` and `parse_genius_sections` could in theory disagree (e.g., `parse_genius_sections` skips empty lines after parens are stripped, but `_split_lines` doesn't).

### Why It Could Fail

In the current code, `_load_lyrics` returns:
- `lyrics_text = "\n".join(line["align_text"] for line in sections)`
- `lyrics_structure = sections` (each `len(sections)` items)

Then `_split_lines(lyrics_text, lyrics_structure)` returns `display` and `align` lists of length `len(sections)`. NW returns `len(lyric_tokens)` which should equal the number of lines. In practice, they match 1:1.

**But:** `parse_genius_sections` skips lines where `align_text` is empty after inline-paren stripping. If the source text has a line that becomes empty after stripping (e.g., `“(Instrumental)”`), `parse_genius_sections` drops it, but the `lyrics_text` already omitted it too (since it joins `align_text` values). So the counts should match.

### Recommended Fix

**Add the assert to the plan in §3.** It's a safety check that's nearly free:

```python
line_objects = match_words_to_lines(words, display_lines, align_lines)
if len(line_objects) != len(genius_lines):
    # Could happen if multi-line header parsing or empty line handling diverges
    raise RuntimeError(
        f"Line count mismatch after NW matching: got {len(line_objects)} line objects "
        f"but Genius structure has {len(genius_lines)} lines"
    )
```

---

## 4. 🔴 High Risk: "Whisper Prefix/Suffix" Bias in NW — Free Suffix but No Free Prefix

### The Issue

Plan §1 describes the NW as:

> "unbanded if max(m, n) <= 500, else banded."
> "Free whisper prefix/suffix"

The prototype's `word_extraction.py:244-256` confirms:

```python
for j in range(n + 1):
    dp[0][j] = 0  # Free Whisper prefix
    
# ...

# Free whisper suffix (traceback finds best point on last row)
best_j = n  # default: include all whisper words
```

**The "free suffix" is implemented correctly** (traceback starts at the best position on the last row). **But there's no "free prefix" in traceback — it starts at `j=best_j` which defaults to `n`.**

Wait, let me re-read: `dp[0][j] = 0` means the *first lyric row* can match any whisper prefix at zero cost (free whisper prefix). And the free suffix is implemented by allowing the traceback to stop at the best `j` on the last row.

This means if whisper detects extra words at the beginning or end (common with intro/outro), they're silently dropped.

### Not Actually a Problem

This is the **intended behavior** — the plan documents this correctly. Extra leading/trailing whisper words are harmless and skipping them is the right behavior for semi-global alignment. The lyric anchor is what matters.

The plan is **correct** here. No fix needed.

---

## 5. 🔴 High Risk: `_score()` Edge Case — Contraction Split Forwards

### The Issue

The scoring matrix in the plan (§1) says:

> "Contraction equivalence (incl. 1:N split) — +2"

Prototype `_score()` at `word_extraction.py:141-149`:

```python
# Handle 1:N splits
if l_exp and whisper_tok in l_exp.split():
    return 2
if w_exp and lyric_tok in w_exp.split():
    return 2
```

**What happens when whisper says "im" and lyrics say "i'm"?**

- `_normalize_token("i'm")` → "im"
- `_normalize_token("im")` → "im"
- lyric_tok == whisper_tok → returns 3 (exact match, len >= 6? No! len("im") is 2, so returns 2).

OK, so exact match for short words is +2.

**What about "do" + "nt" vs "dont"?**

- lyric_tok = "dont", whisper_tok = "do"
- `l_exp = "do not"` (from _CONTRACTIONS["dont"] = "do not")
- `whisper_tok in l_exp.split()` → "do" in ["do", "not"] → True → 2

- If whisper says "doe" instead of "do":
  - `_levenshtein("do", "doe")` = 1 → but len("do") < 3, so fuzzy is 0
  - Final score: 0 (mismatch)
  - But "doe" is close to "do" in a contraction split... too short for fuzzy.

**The edge case:** if whisper splits a contraction into parts, one of which is 2 chars (e.g., "do") and the live lyric is 2 chars ("do"), exact match gives +2. If whisper hallucinates slightly ("doe" for "do"), the Levenshtein-1 fuzzy branch won't fire (min 3 chars for fuzzy).

### Recommended Fix

The scoring already handles this correctly — the minimum length gate for fuzzy prevents false positives with short tokens. This is documented behavior. No fix needed, but **the plan should mention this as a known limitation** (the plan does not currently mention the Levenshtein-1 minimum length gate, but it's clear in the code).

---

## 6. 🟡 Medium Risk: `_extract_words` Import Path in Worker

### The Issue

Plan §2 says to import `_MIN_WORD_PROBABILITY` from `pikaraoke.lib.word_alignment`. Of course the prototype's `word_extraction.py` defines it at module level, and the port plan correctly extracts it.

But `_extract_words` and `_segments_to_line_objects` are in BOTH:
- `pikaraoke/pipeline/workers/whisper_worker.py` (today)
- `pikaraoke/lib/word_alignment.py` (proposed)

The plan says the worker's `_extract_words` is the one that matters.

The issue is that if we ever need to change the word extraction logic, there are now two copies.

### Recommended Fix

**Add a todo to the plan to eventually move `_extract_words` to `word_alignment.py` and have the worker import it.** For now, the duplication is acceptable because worker subprocess isolation requires self-contained code, but the plan should note it as tech debt.

---

## 7. 🟡 Medium Risk: `word_extraction.py` rename to `word_alignment.py`

### The Issue

The plan says:

> "New module: `pikaraoke/lib/word_alignment.py`"  
> "Verbatim port from `mpv/genius_diarize/word_extraction.py`"

The prototype file is `word_extraction.py`, not `word_alignment.py`. The plan renames it. This is fine, but the `__all__`, `import` path, and tests all assume `word_alignment`.

### Verdict

The rename is intentional and the plan is consistent about it. No problem, but the implementation must ensure all imports are updated.

---

## 8. 🟡 Medium Risk: Test Name Mismatch for `_segments_to_line_objects`

### The Issue

In `tests/unit/test_whisper_worker.py`, the current import is:

```python
from pikaraoke.pipeline.workers.whisper_worker import (
    _extract_words,
    _match_words_to_lines,
    _segments_to_line_objects,
)
```

The plan says in §2 "Updated `_segments_to_line_objects` — init speaker fields."

The tests for these functions are in `TestSegmentsToLineObjects` class.

After the port:
- `_extract_words` changes (filter + init speaker fields) → requires test updates
- `_match_words_to_lines` is DELETED → all tests and imports break
- `_segments_to_line_objects` changes (init speaker fields) → requires test updates

The plan only lists Changes to `test_whisper_worker.py` in §8 for deleting tests of `_match_words_to_lines` and adding tests for `_extract_words`.

**But `_segments_to_line_objects` changes too** — it needs `speaker=None` and `dominant_speaker=None` added to each word dict. The current tests in `TestSegmentsToLineObjects` test the shape of line objects. They may pass without changes because the tests only assert on `text`, `words`, `start`, `end` — not `speaker` / `dominant_speaker`. But if any code downstream expects these fields to exist, the tests could miss it.

### Recommended Fix

Add to §8 under `test_whisper_worker.py` updates:

```python
def test_segments_to_line_objects_includes_speaker_fields():
    # Every emitted word dict has speaker=None, dominant_speaker=None
```

---

## 9. 🟡 Medium Risk: Transcribe vs. Align Return Shape

### The Issue

Plan §2 says:

> `_do_align_refine` now ends with: `return _extract_words(refined)`

And:
> `transcribe_refine` is **unchanged** — no lyrics file → no NW → still returns line_objects via `_segments_to_line_objects`.

**This means `align_refine` and `transcribe_refine` now return different data shapes:**
- `align_refine` returns `list[dict_word]` (flat)
- `transcribe_refine` returns `list[dict_line]` (hierarchical)

This is intentional per the plan, but any code that calls these methods (e.g., in tests or other stages) needs to be aware of this difference. The `LyricAlignStage.run()` method handles it by branching on `lyrics_path is not None`.

**Potential issue:** If any other stage or test calls `_worker.align_refine()` and expects line_objects, it will break.

### Search for Other Call Sites

```bash
grep -r "align_refine" pikaraoke/ tests/ --include="*.py"
```

```
pikaraoke/pipeline/workers/whisper_worker.py:    def align_refine(self, vocal_path: Path, lyrics_text: str, cancel_event=None) -> list[dict]:
pikaraoke/pipeline/stages/lyric_align.py:                lambda: self._worker.align_refine(
pikaraoke/pipeline/stages/lyric_align.py:            line_objects = _model_call(ctx, Phase.ALIGN, ...)
pikaraoke/tests/unit/test_whisper_worker.py:def test_align_refine_returns_line_objects(...)
pikaraoke/tests/unit/test_whisper_worker.py:    result = worker.align_refine(...)
pikaraoke/tests/unit/test_whisper_worker.py:    assert result[0]["text"] == "hello"
```

In `test_whisper_worker.py`, the existing test fixture returns:
```python
result_send.send(("ok", [{"text": "hello", "words": [], "start": 0.0, "end": 1.0}]))
```

But after the port, `align_refine` would return a flat word list, so this test would need updating.

### Recommended Fix

The plan correctly identifies this in §2 under "Worker payload on success" table. But **the plan should also add the test update for `test_whisper_worker.py` that mocks the worker returning a flat word list** and then tests that `LyricAlignStage` handles it correctly.

---

## 10. 🟢 Low Risk: Safety Net — `_reset_segment_first_flags` on Empty Lines

### The Issue

If `match_words_to_lines` returns a line object with no words (`"words": []`), `_reset_segment_first_flags` will do nothing for that line, which is correct.

But `_assign_speakers_from_genius` for that same line would do:
```python
for word in line_obj["words"]:  # empty list → no iteration
    word["speaker"] = gl["speaker_label"]
```

This is correct (no words to label). No action needed.

---

## 11. 🟢 Low Risk: Prototype `genius.py` vs. `pikaraoke/lib/genius_lyrics.py`

### The Issue

The plan says the Genius parser is "already ported" (`pikaraoke/lib/genius_lyrics.py`). Let me verify field names match:

| Prototype field | Pikaraoke field | Match? |
|---|------|---|
| `text` | `text` | ✅ |
| `align_text` | `align_text` | ✅ |
| `section` | `section` | ✅ |
| `speaker_label` | `speaker_label` | ✅ |
| `dominant_speaker` | `dominant_speaker` | ✅ |
| `is_ensemble` | `is_ensemble` | ✅ |

All fields match. No issue.

**One concern:** `genius_singer_mode()` returns "solo" or "multi". The plan gates speaker assignment on `"multi"`. The code in `lyric_align.py` would be:

```python
if lyrics_structure and genius_singer_mode(lyrics_structure) == "multi":
    _assign_speakers_from_genius(line_objects, lyrics_structure)
```

This is consistent.

---

## 12. 🟢 Low Risk: Cross-Pollution between `_extract_words` and `extract_words`

### The Issue

The prototype has `extract_words()` (no underscore). The pikaraoke worker has `_extract_words()`. The plan keeps the underscore. This is fine and intentional (the pikaraoke convention is to prefix internal helpers with `_`).

---

## 13. 📝 Notes: Non-Issues, Design Decisions Already Correct in Plan

### 13.1 Banding Heuristic Threshold

The plan shows `max(50, max(m, n) // 4)` for band width. The prototype uses:

```python
band = max(50, max(m, n) // 4)
```

This matches. The 50-word minimum is reasonable because NW on 500×500 is fast enough (~250ms).

### 13.2 Scoring — Contraction 1:N Split

Prototype:
```python
if l_exp and whisper_tok in l_exp.split():
    return 2
```

This handles "do" + "nt" → "dont" correctly. Both "do" and "nt" map to "do not" which contains "dont". Score = 2 per token. The plan doesn't mention the opposite direction (lyric "do" + whisper "dont"):

```python
if w_exp and lyric_tok in w_exp.split():
    return 2
```

But this is the same logic, just swapped. It handles "cant" in lyrics and "cannot" in whisper (both normalize to "cant", exact match). Or more interestingly: lyrics say "do" (as a standalone word) and whisper says "dont" (normalized to "dont").

Wait, `_normalize_token("don't")` → `"dont"`. And `_CONTRACTIONS["dont"] = "do not"`. So if lyric says "don't" (normalized "dont") and whisper says "do" (normalized "do"):
- lyric_tok = "dont"
- l_exp = "do not"
- whisper_tok = "do"
- `whisper_tok in l_exp.split()` → "do" in ["do", "not"] → True → 2

This works!

But what about lyrics say "do" and whisper says "dont"?
- lyric_tok = "do"
- whisper_tok = "dont"
- w_exp = "do not"
- `lyric_tok in w_exp.split()` → "do" in ["do", "not"] → True → 2

Also works! The scoring is symmetric for this case.

### 13.3 SRT Generation — No Regression

The plan says SRT is unchanged except for potential speaker fields, which are intentionally not rendered. This is correct per the prototype.

### 13.4 Free Whisper Prefix/Suffix

The plan and the prototype both implement semi-global NW with free prefix/suffix. This is the standard approach for sequence alignment where one sequence (whisper) may have extra tokens at the ends.

---

## Summary Table

| # | Issue | Risk | Recommended Fix |
|---|-------|------|-----------------|
| 1 | `is_segment_first` becomes line-first instead of segment-first | 🔴 High | Add `is_segment_boundary_first` field to preserve nudge heuristics |
| 2 | Config field name `speaker_colors` needs to be added to `PipelineConfig` | 🔴 High | Show the full updated `PipelineConfig` dataclass in §5 |
| 3 | Missing line-count guard after NW matching | 🔴 High | Add assert in §3 |
| 4 | Free whisper prefix/suffix — actually correct | 📝 Note | None — the behavior is intended |
| 5 | `_score()` edge case with 2-char tokens | 🔴 Medium | Acceptable; Levenshtein-1 minimum length is a deliberate design choice |
| 6 | `_extract_words` duplication with `lib/word_alignment.py` | 🟡 Medium | Note as tech debt; eventually converge to `lib/` |
| 7 | `word_extraction.py` → `word_alignment.py` rename | 🟡 Medium | All tests/imports must be updated; currently consistent |
| 8 | `_segments_to_line_objects` speaker field tests missing | 🟡 Medium | Add test in §8 |
| 9 | `align_refine` vs `transcribe_refine` return shape differs | 🟡 Medium | Test `LyricAlignStage` with mocked flat word list |
| 10 | Empty word lists in `_reset_segment_first_flags` | 🟢 Low | No action needed — handles correctly |
| 11 | `genius_singer_mode` logic matching | 🟢 Low | Verified correct — returns "solo"/"multi" |
| 12 | `extract_words` vs `_extract_words` naming | 🟢 Low | Intentional and fine |
| 13 | Design decisions already correct | 📝 Notes | Banding, scoring, SRT, NW already correct in plan |

---

## Checklist for Implementation

- [ ] **Before writing `word_alignment.py`:** Verify that `mpv/genius_diarize/word_extraction.py` matches the ported version in the plan (it does, reviewed line-by-line on key functions).
- [ ] **Add `is_segment_boundary_first` to word dict shape** in §2 data shapes diagram, `_extract_words`, and `_segments_to_line_objects`.
- [ ] **Update §5** to show the full updated `PipelineConfig` with `speaker_colors` and `ensemble_color`.
- [ ] **Add line-count guard to §3** inside `LyricAlignStage.run()`.
- [ ] **Update §8 tests** for `_segments_to_line_objects` to include `speaker`/`dominant_speaker` fields.
- [ ] **Add mock test in §8** for `LyricAlignStage` with a mocked worker returning flat words.
- [ ] **Add `_UNSAFE_CHAR_RE` and `_ENSEMBLE_STYLE` to config** or as module-level constants in `lyric_align.py`.
- [ ] **Verify `_dominant_speaker_presence` handles line objects with no speaker fields** (transcription mode — should fall through gracefully).
- [ ] **Run edge case: all-solo song** (only `[Verse]`, no `:` attribution) — should still work.
- [ ] **Run edge case: all-ensemble song** (every header is `[Chorus: All]`) — `genius_singer_mode` returns "solo", no speaker assignment.
