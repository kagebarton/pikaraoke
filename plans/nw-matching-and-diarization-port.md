# Port NW matching and Genius header diarization from `mpv/genius_diarize`

Model: Claude Opus 4.7

## Context

The main pipeline pairs whisper-aligned words to lyric lines with a brittle
count-based slice ([`_match_words_to_lines`](../pikaraoke/pipeline/workers/whisper_worker.py#L116-L141)).
Any drift between the lyrics file's word count and what stable-ts emits — common
when contractions get split (`don't` → `do n't`), punctuation is stripped, or
whisper hallucinates in silent regions — cascades to every following line and
desyncs the entire song.

The `mpv/genius_diarize/` prototype already solved this with a Needleman-Wunsch
matcher and a Genius-header-driven speaker assignment pass that produces
multi-color karaoke ASS for songs like boy-band duets. The Genius header parser
itself is already ported ([`pikaraoke/lib/genius_lyrics.py`](../pikaraoke/lib/genius_lyrics.py)
and [`LyricAlignStage._load_lyrics`](../pikaraoke/pipeline/stages/lyric_align.py#L126-L161)
already produce a `lyrics_structure` artifact). What's missing is (a) the NW
matcher, (b) speaker assignment onto line_objects, and (c) per-speaker ASS
styling.

NW matching will run **in `LyricAlignStage` (parent side), not in the whisper
subprocess** — keeps the worker inference-only and gives diarization access to
`lyrics_structure` without extra IPC plumbing.

---

## Data Shapes

### Word dict (returned from worker, consumed by NW matcher)

**Today** ([`_extract_words`](../pikaraoke/pipeline/workers/whisper_worker.py#L94-L113)):
```python
{"word": str, "start": float, "end": float, "is_segment_first": bool}
```

**After port:**
```python
{
    "word": str,
    "start": float,
    "end": float,
    "is_segment_first": bool,        # initially set per whisper segment;
                                      # reset per lyric line after NW
    "speaker": None,                 # set by _assign_speakers_from_genius
    "dominant_speaker": None,        # set by _assign_speakers_from_genius
}
```

Words with `probability < min_whisper_word_probability` are dropped before this
dict is built (silent-region hallucination filter). In the prototype this
threshold was 0.0001 (see `word_extraction.py:62-99`).

### Line object (output of NW matcher; consumed by `_generate_ass`/`_generate_srt`)

**Today** (count-based, in worker):
```python
{"text": str, "words": list[word], "start": float, "end": float}
```

**After port** (built parent-side by `match_words_to_lines`):
```python
{
    "text": str,                      # karaoke display text
    "words": list[word],              # aligned whisper words (may be empty)
    "start": float,
    "end": float,
    "speaker": str | None,           # internal: diarization color key only
    "dominant_speaker": str | None,  # internal: diarization color key only
}
```

`speaker` and `dominant_speaker` are internal color keys for the ASS
generator only. They are never written as labels.

### Genius line (already exists, from `parse_genius_sections`)

```python
{
    "text": str,                      # display ("(I can't help) Falling…")
    "align_text": str,                # parens-stripped ("Falling…")
    "section": str,                   # "Verse 1"
    "speaker_label": str | None,      # "Brian" / "Kevin & AJ" / None=ensemble
    "dominant_speaker": str | None,   # "Brian" / "Kevin" / None=ensemble
    "is_ensemble": bool,
}
```

---

## 1. New module: `pikaraoke/lib/word_alignment.py`

Port from [`mpv/genius_diarize/word_extraction.py`](../mpv/genius_diarize/word_extraction.py)
the matching machinery, minus the prototype-specific I/O helpers
(`load_lyrics`, `load_genius_lyrics`, `extract_words`, `segments_to_line_objects`,
`match_words_to_lines_by_count` — none of these belong in the main project).

### Public API
```python
def match_words_to_lines(
    words: list[dict],
    lines: list[str],
    align_lines: list[str] | None = None,
) -> list[dict]:
    """Assign whisper words to lyric lines via Needleman-Wunsch.

    Args:
        words: flat whisper word list. Each dict must have at least
            `word`, `start`, `end`. Other fields pass through into the
            output line_objects unchanged.
        lines: display text per lyric line (used for line_obj["text"]).
        align_lines: parens-stripped tokens used for matching. If None,
            falls back to `lines`. When provided, must be 1:1 with `lines`.

    Returns:
        list[line_obj] of length len(lines). Lines with no aligned whisper
        words have words=[] and start/end interpolated from neighbors.
    """
```

### Private helpers (all ported as-is)

| Function | Source lines | Notes |
|---|---|---|
| `_normalize_token(t)` | L118-121 | NFKC + lowercase + strip non-word |
| `_levenshtein(a, b)` | L162-174 | edit distance, early exit on len-diff>1 |
| `_score(lyric_tok, whisper_tok)` | L124-159 | scoring matrix (see below) |
| `_needleman_wunsch(lyric_norms, whisper_norms)` | L419-431 | dispatcher |
| `_needleman_wunsch_unbanded(...)` | L233-304 | full O(m×n), free whisper prefix/suffix |
| `_needleman_wunsch_banded(...)` | L307-416 | Sakoe-Chiba band + taper + fallback |

### Scoring matrix (`_score`)

| Case | Score |
|---|---|
| Exact match, len ≥ 6 (anchor bonus) | +3 |
| Exact match, len < 6 | +2 |
| Contraction equivalence (incl. 1:N split) | +2 |
| Phonetic equivalence (`_PHONETIC_EQUIV`) | +1 |
| Levenshtein-1, both tokens ≥ 3 chars | +1 |
| Mismatch | 0 |

After NW, only pairs with `_score >= 1` are recorded (mismatches at score 0
are dropped → those lyric tokens fall through to neighbor-interpolation).

### Banding

- **Dispatch:** unbanded if `max(m, n) <= 500`, else banded.
- **Band width:** `max(50, max(m, n) // 4)`, with taper over the last
  `m // 4` rows so the free-suffix region stays reachable.
- **Fallback:** if banded score < `(m/3)*2 + (m*2/3)*GAP_LYRIC`, log a
  warning and re-run unbanded (band likely clipped the true path).

### Constants

```python
_GAP_LYRIC      = -2     # lyric token with no whisper match
_GAP_WHISPER    = -1     # whisper token with no lyric match
_MAX_MATCH      = 3      # anchor bonus ceiling
_BAND_MIN_LENGTH = 500
_MIN_WORD_PROBABILITY = 0.0001  # drop sub-threshold whisper words
_CONTRACTIONS   = {...}  # 30 entries, ported verbatim
_PHONETIC_EQUIV = {...}  # 13 frozensets, ported verbatim
```

The invariant `_MAX_MATCH <= -(_GAP_LYRIC + _GAP_WHISPER)` is asserted at
module-load (must hold so NW prefers matching over double-gapping).

### Design constraints worth knowing

Each of these is intentional in the prototype — listing them so reviewers don't
re-litigate them later:

- **Semi-global, not global.** The DP table seeds row 0 with zero (free whisper
  prefix) and the suffix traceback picks the best column on the last row
  (free whisper suffix). Whisper words before the first lyric token or after
  the last — typical of intros, outros, ad-libs, backing vox after the final
  line — are silently dropped instead of penalized. Lyric tokens never get
  the free treatment: every lyric line is required to land somewhere in the
  alignment.
- **Levenshtein-1 fuzzy is gated to tokens ≥ 3 chars on both sides.** A 1-char
  edit on a 2-char token (`do` ↔ `to`, `oh` ↔ `of`) is too easy to hit by
  coincidence and would cause false positives with short function words.
  Short-token matches must come through the exact-match branch (+2) or the
  contraction/phonetic branches; otherwise they score 0.
- **Contraction scoring is symmetric.** Both `_CONTRACTIONS.get(lyric_tok)` and
  `_CONTRACTIONS.get(whisper_tok)` are checked, and the 1:N split branch
  (`whisper_tok in l_exp.split()` and `lyric_tok in w_exp.split()`) covers
  both directions. So `lyric "don't"` ↔ `whisper "do"`, `lyric "do"` ↔
  `whisper "don't"`, and `lyric "do not"` ↔ `whisper "dont"` all score +2.
- **Empty `words` lists are valid.** A lyric line where no whisper word
  aligned (heavy hallucination on that line, or a line that's effectively
  silent) gets `words=[]` with `start`/`end` interpolated from neighbors.
  `_reset_segment_first_flags` and `_assign_speakers_from_genius` both
  iterate `line["words"]` and no-op on empty lists; `_generate_ass` skips
  events with no words; `_generate_srt` still emits the text with
  interpolated timing. No special-casing needed elsewhere.
- **`_PHONETIC_EQUIV` is not transitive.** Pairs are stored as `frozenset({a, b})`
  and matched as a set lookup. If `mm~mmm` and `mmm~mmmm` are both needed
  later, all pairwise frozensets must be added explicitly, or the structure
  refactored to a canonical-form dict. Documented in the source; flagging it
  here so future palette additions don't assume transitivity.

---

## 2. Worker IPC contract change: `pikaraoke/pipeline/workers/whisper_worker.py`

### `_extract_words` — drop sub-threshold, init speaker fields

```python
def _extract_words(result) -> list[dict]:
    """Flatten WhisperResult into [{word, start, end, is_segment_first,
    speaker, dominant_speaker}, ...].

    Drops words with probability < _MIN_WORD_PROBABILITY (silent-region
    hallucination filter). Without this, the matcher anchors lines to
    zero-duration phantom timestamps and collapses entire stanzas.
    Real low-confidence words sit at ~0.05+; phantoms are 1e-5 to 1e-3.
    """
    all_words = []
    dropped = 0
    for segment in result.segments:
        kept_in_segment = 0
        for word in segment.words:
            prob = getattr(word, "probability", None)
            if prob is not None and prob < _MIN_WORD_PROBABILITY:
                dropped += 1
                continue
            all_words.append({
                "word": word.word.strip(),
                "start": word.start,
                "end": word.end,
                "is_segment_first": kept_in_segment == 0,
                "speaker": None,
                "dominant_speaker": None,
            })
            kept_in_segment += 1
    if dropped:
        logger.info("Dropped %d low-probability whisper words (< %.4f)",
                    dropped, _MIN_WORD_PROBABILITY)
    return all_words
```

`_MIN_WORD_PROBABILITY` is imported from `pikaraoke.lib.word_alignment`
(single source of truth).

### `_match_words_to_lines` — **deleted**

The count-based helper (worker L116-141) is removed entirely. No callers remain
once the stage takes over matching.

### `_segments_to_line_objects` — init speaker fields

Same change as `_extract_words`: words get `speaker: None`, `dominant_speaker: None`
so transcription-mode line_objects have a uniform shape.

### `align_refine` — return shape change

| | Today | After |
|---|---|---|
| IPC call | `("align_refine", vocal_path, lyrics_text)` | unchanged |
| Worker payload on success | `("ok", list[line_obj])` | `("ok", list[word])` |
| Caller post-process | none | NW + speaker assignment in stage |

[`_do_align_refine`](../pikaraoke/pipeline/workers/whisper_worker.py#L687-L768)
now ends with:
```python
return _extract_words(refined)   # was: _match_words_to_lines(words, lyric_lines)
```

`transcribe_refine` is **unchanged** — no lyrics file → no NW → still returns
line_objects via `_segments_to_line_objects`.

### Public method docstring update

[`WhisperWorker.align_refine`](../pikaraoke/pipeline/workers/whisper_worker.py#L329-L349)
docstring:
```
Returns: list[dict] — flat word list (was: list[line_obj]).
The caller is responsible for matching words to lyric lines.
```

---

## 3. `LyricAlignStage` rewrite of post-worker path: `pikaraoke/pipeline/stages/lyric_align.py`

### New imports

```python
from pikaraoke.lib.genius_lyrics import parse_genius_sections, genius_singer_mode
from pikaraoke.lib.word_alignment import match_words_to_lines
```

### New flow inside `run()` alignment branch (replaces L72-80)

```python
words = _model_call(
    ctx, Phase.ALIGN,
    lambda: self._worker.align_refine(
        vocal_path=vocal_wav,
        lyrics_text=lyrics_text,
        cancel_event=ctx.cancel.event if ctx.cancel else None,
    ),
)

display_lines, align_lines = _split_lines(lyrics_text, lyrics_structure)
line_objects = match_words_to_lines(words, display_lines, align_lines)
_reset_segment_first_flags(line_objects)

if lyrics_structure and genius_singer_mode(lyrics_structure) == "multi":
    _assign_speakers_from_genius(line_objects, lyrics_structure)
```

The transcription branch is unchanged (worker still returns line_objects).

### New module-level helpers

```python
def _split_lines(
    lyrics_text: str,
    lyrics_structure: list[dict] | None,
) -> tuple[list[str], list[str]]:
    """Return (display_lines, align_lines) for match_words_to_lines.

    With Genius structure: display = gl["text"], align = gl["align_text"].
    Without:               both equal lyrics_text.split() (non-empty lines).
    """
    if lyrics_structure:
        display = [gl["text"] for gl in lyrics_structure]
        align = [gl["align_text"] for gl in lyrics_structure]
        return display, align
    flat = [ln for ln in lyrics_text.split("\n") if ln.strip()]
    return flat, flat


def _assign_speakers_from_genius(
    line_objects: list[dict],
    genius_lines: list[dict],
) -> None:
    """Copy speaker_label and dominant_speaker onto each line_obj and word.

    Best-effort zip — silently truncates to the shorter list. In practice
    line_objects and genius_lines come from the same parse_genius_sections
    call so they're 1:1; this is just a safety net.
    """
    for line_obj, gl in zip(line_objects, genius_lines):
        line_obj["speaker"] = gl["speaker_label"]
        line_obj["dominant_speaker"] = gl["dominant_speaker"]
        for word in line_obj["words"]:
            word["speaker"] = gl["speaker_label"]
            word["dominant_speaker"] = gl["dominant_speaker"]


def _reset_segment_first_flags(line_objects: list[dict]) -> None:
    """Make is_segment_first reflect lyric-line boundaries, not whisper segments.

    NW regroups whisper words to lyric lines, but is_segment_first was set
    in _extract_words against the whisper segment boundaries. After reset,
    only the first word of each line is flagged.
    """
    for line in line_objects:
        for i, w in enumerate(line["words"]):
            w["is_segment_first"] = (i == 0)
```

---

## 4. Speaker-colored ASS: `_generate_ass` overhaul

Port styling logic from [`mpv/genius_diarize/caption.py`](../mpv/genius_diarize/caption.py).
Keep the karaoke-timing math (event window, `\kf`, lead-in/out) byte-identical
to today's implementation.

**Constraints:**
- **No speaker labels** in ASS or SRT output. The `speaker` / `dominant_speaker`
  fields line up color in ASS only (via `Style` rows). They are never rendered
  as text.
- **No first-word nudge** (`first_word_nudge_cs`) — the nudge is not used.

### Decision logic

```
present, has_ensemble = _dominant_speaker_presence(line_objects)
single_speaker = (len(present) <= 1) and not has_ensemble
```

| Case | Styles emitted | Style assigned per line |
|---|---|---|
| `single_speaker` (no diarization, or all one singer) | `Style: Karaoke` | `Karaoke` |
| Multi + ensemble lines | `Style: Karaoke_<safe_name>` per name + `Style: Karaoke_ensemble` | by `dominant_speaker` |
| Multi, no ensemble | `Style: Karaoke_<safe_name>` per name | by `dominant_speaker` |

### New helpers (module-level in `lyric_align.py`)

```python
_UNSAFE_CHAR_RE = re.compile(r"[^\w]+")
_ENSEMBLE_STYLE = "Karaoke_ensemble"

def _safe_style_name(label: str) -> str:
    return _UNSAFE_CHAR_RE.sub("_", label).strip("_")

def _dominant_speaker_presence(line_objects) -> tuple[list[str], bool]:
    """Return (ordered_unique_speakers, has_ensemble) (Never rendered as text).

    These speaker keys are used only to assign color styles in ASS.
    They never appear as on-screen labels.

    ordered_unique_speakers: dominant_speaker values in first-appearance
    order, deduped, with None excluded.
    has_ensemble: True if any line_obj has speaker=None (not just
    dominant_speaker=None; ensemble lines have both fields None).
    """
```

### `_generate_ass` restructure

Split the current monolithic method ([`lyric_align.py:163-248`](../pikaraoke/pipeline/stages/lyric_align.py#L163-L248))
into:

```python
def _generate_ass(self, line_objects: list[dict]) -> str:
    present, has_ensemble = _dominant_speaker_presence(line_objects)
    single = (len(present) <= 1) and not has_ensemble
    return (
        self._ass_header(present, single, has_ensemble)
        + "\n".join(self._ass_events(line_objects, single))
        + "\n"
    )

def _ass_header(self, present, single, has_ensemble) -> str:
    # [Script Info] + [V4+ Styles] (1 or N) + [Events] format
    ...

def _ass_styles(self, present, single, has_ensemble) -> str:
    # single -> one "Style: Karaoke" row (current behavior)
    # multi  -> "Style: Karaoke_<safe>" per present speaker, color from
    #          cfg.speaker_colors[idx % len(cfg.speaker_colors)]
    #          + "Style: Karaoke_ensemble" with cfg.ensemble_color if has_ensemble
    ...

def _ass_events(self, line_objects, single) -> list[str]:
    # Per-line: pick style name, then identical karaoke-text generation.
    # Karaoke timing is the same as today (event window, \kf, lead-in/out).
    # Note: no first-word nudge is applied.
```

### Style picker (per line, inside `_ass_events`)

```python
if single:
    style = "Karaoke"
else:
    dominant = line_obj.get("dominant_speaker") or line_obj.get("speaker")
    style = _ENSEMBLE_STYLE if dominant is None else f"Karaoke_{_safe_style_name(dominant)}"
```

The Dialogue line then becomes:
```
Dialogue: 0,<start>,<end>,<style>,,0,0,0,,<karaoke_text>
```

Karaoke text generation (the `\kf{cs}word` builder, lead-in gap `\k{cs}`) is
byte-identical to today's loop — just hoisted into `_ass_events`.

---

## 5. Config: `pikaraoke/pipeline/config.py`

Add to `PipelineConfig` dataclass (copy palette from prototype's
`GeniusDiarizeConfig`):

```python
# Per-speaker karaoke colors. Index = first-appearance order.
# Format: &HAABBGGRR& (alpha + reversed RGB). Distinct from ensemble.
speaker_colors: tuple[str, ...] = (
    "&H00FFFF00&",  # cyan
    "&H00B469FF&",  # pink
    "&H0000FF00&",  # green
    "&H000080FF&",  # orange
    "&H00FA82FA&",  # lavender
    "&H000000FF&",  # red
)

# Color for ensemble lines (speaker_label is None -> all/unattributed).
ensemble_color: str = "&H0000D7FF&"  # goldenrod
```

`tuple` (not `list`) so the dataclass default is hashable / immutable.
If `len(present) > len(speaker_colors)`, indices wrap with `% len()`.

---

## 6. SRT: unchanged

[`_generate_srt`](../pikaraoke/pipeline/stages/lyric_align.py#L250-L265) and
[`_should_write_srt`](../pikaraoke/pipeline/stages/lyric_align.py#L267-L279)
already do the right thing: plain text, only when yt-dlp didn't already
provide an `.en.srt` / `.srt`. Diarization is **not** carried into SRT
(matches prototype rationale — header->line attribution is too imprecise to
claim authoritatively in plain-text caption form).

---

## 7. End-to-end call trace (after port)

Multi-singer Genius song, alignment mode:

```
LyricAlignStage.run(ctx)
├── lyrics_path = ctx.artifacts["lyrics_path"]  # genius .txt
├── _load_lyrics(lyrics_path)
│   ├── parse_genius_sections(raw)              # already exists
│   └── returns (lyrics_text, "txt", lyrics_structure)
├── ctx.artifacts["lyrics_structure"] = lyrics_structure
├── words = _worker.align_refine(vocal_wav, lyrics_text)
│   └── (subprocess) stable-ts align->refine->_extract_words
│       (drops prob<0.0001, returns flat list[word])
├── display, align = _split_lines(lyrics_text, lyrics_structure)
├── line_objects = match_words_to_lines(words, display, align)
│   ├── tokenize align lines -> lyric_norms with line_idx
│   ├── normalize whisper words -> whisper_norms
│   ├── alignment = _needleman_wunsch(lyric_norms, whisper_norms)
│   ├── filter pairs by _score >= 1
│   ├── group whisper words by lyric line (monotone)
│   └── interpolate timestamps for empty lines
├── _reset_segment_first_flags(line_objects)
├── genius_singer_mode(lyrics_structure) == "multi" -> True
├── _assign_speakers_from_genius(line_objects, lyrics_structure)
├── _generate_ass(line_objects)
│   ├── _dominant_speaker_presence -> (["Brian", "AJ"], has_ensemble=True)
│   ├── single_speaker = False
│   ├── _ass_header -> 3 styles (Karaoke_Brian, Karaoke_AJ, Karaoke_ensemble)
│   └── _ass_events -> per-line style picked from dominant_speaker
├── _generate_srt(line_objects)        # plain text, no labels
├── write tmp .ass / .srt -> move to karaoke/ and subtitles/
└── ctx.artifacts["ass_file"], ["srt_file"] set
```

---

## 8. Tests

### New: `tests/unit/test_word_alignment.py`

Port the relevant 60+ cases from
[`mpv/tests/test_word_extraction.py`](../mpv/tests/test_word_extraction.py).
Drop tests for prototype-only helpers (`load_genius_lyrics`,
`match_words_to_lines_by_count`).

Coverage targets:

```python
class TestNormalizeToken:           # NFKC, lowercase, non-word strip
class TestLevenshtein:              # exact, off-by-one, early exit
class TestScore:
    def test_exact_short_returns_2()
    def test_exact_long_returns_3_anchor()
    def test_contraction_equivalence_returns_2()
    def test_contraction_split_returns_2()
    def test_phonetic_equiv_returns_1()
    def test_fuzzy_lev1_returns_1()
    def test_below_min_length_no_fuzzy()
    def test_mismatch_returns_0()
class TestNeedlemanWunsch:
    def test_perfect_match()
    def test_free_whisper_prefix()
    def test_free_whisper_suffix()
    def test_lyric_gap_when_word_missing()
    def test_whisper_gap_for_hallucination()
class TestBanding:
    def test_short_dispatches_unbanded()
    def test_long_dispatches_banded()
    def test_banded_matches_unbanded_on_clean_input()
    def test_degenerate_band_falls_back_to_unbanded()
    def test_anchor_bonus_inside_band()
class TestMatchWordsToLines:
    def test_perfect_match_one_line()
    def test_punctuation_difference_still_matches()
    def test_hallucination_silently_dropped()
    def test_missing_word_interpolated_from_neighbors()
    def test_contraction_split_no_cascade()
    def test_align_lines_preferred_over_lines()
    def test_score_zero_pair_rejected()
    def test_anchor_tie_break()
    def test_empty_inputs_returns_empty_lines()
    def test_pass_through_extra_word_fields()  # speaker, dominant_speaker preserved
```

### Update: `tests/unit/test_lyric_align.py`

Add cases:
```python
def test_alignment_mode_calls_match_words_to_lines(monkeypatch, tmp_path):
    # Mock worker to return canned word list; assert NW path invoked.

def test_assign_speakers_populates_fields():
    # Build line_objects + genius_lines; call _assign_speakers_from_genius;
    # verify line_obj["speaker"], line_obj["dominant_speaker"], and per-word.

def test_assign_speakers_zips_silently_on_mismatch():
    # 3 line_objects, 2 genius_lines -> first 2 labeled, 3rd unlabeled, no exception.

def test_generate_ass_single_speaker_emits_one_style():
    # All lines speaker="Brian" -> only "Style: Karaoke" row.

def test_generate_ass_multi_speaker_emits_styles_per_speaker():
    # Mix of Brian/AJ -> "Style: Karaoke_Brian" and "Style: Karaoke_AJ" present.

def test_generate_ass_ensemble_emits_ensemble_style():
    # Includes a None-speaker line -> "Style: Karaoke_ensemble" present.

def test_generate_ass_safe_style_name_for_special_chars():
    # speaker="Kevin & AJ" -> style "Karaoke_Kevin_AJ" (collapsed underscores).

def test_reset_segment_first_flags_one_per_line():
    # 2 lines x 3 words; only word[0] of each has is_segment_first=True.

def test_split_lines_genius_uses_align_text():
    # lyrics_structure provided -> align_lines uses align_text.

def test_split_lines_no_structure_falls_back_to_text():
    # lyrics_structure=None -> align == display == text.split.

def test_generate_ass_no_speaker_labels():
    # Confirm no speaker labels appear inside any Dialogue event text.
```

### Update: `tests/unit/test_whisper_worker.py`

- **Delete** any tests of the removed `_match_words_to_lines`.
- **Update existing `align_refine` tests:** the worker payload contract changed
  from `("ok", list[line_obj])` to `("ok", list[word])`. Any test that sends a
  canned payload via `result_send.send(("ok", [{"text": "hello", "words": [], ...}]))`
  must be updated to send a flat word list instead, e.g.
  `("ok", [{"word": "hello", "start": 0.0, "end": 1.0, "is_segment_first": True, "speaker": None, "dominant_speaker": None}])`.
  Assertions on `result[0]["text"]` etc. must change to `result[0]["word"]`.
  Run `grep -n align_refine tests/unit/test_whisper_worker.py` to enumerate.
- **Add**:
  ```python
  def test_extract_words_drops_low_probability():
      # Fake WhisperResult with one prob=0.5, one prob=0.00005;
      # assert only the high-prob word survives.

  def test_extract_words_initializes_speaker_fields():
      # Every emitted dict has speaker=None, dominant_speaker=None.

  def test_segments_to_line_objects_initializes_speaker_fields():
      # Transcription-mode word dicts also carry speaker=None,
      # dominant_speaker=None so downstream code can rely on uniform shape.
  ```

### Test fixtures

Reuse existing patterns from `tests/unit/test_genius_lyrics.py`:
- raw `MagicMock()` for stable-ts result, with `.segments[i].words[j]`
  exposing `.word`, `.start`, `.end`, `.probability` attributes.
- No mocking of `parse_genius_sections` — call it on real Genius-format
  text fragments and let it produce real structure.

---

## Critical files

| Action | Path |
|---|---|
| New | [`pikaraoke/lib/word_alignment.py`](../pikaraoke/lib/word_alignment.py) |
| New | [`tests/unit/test_word_alignment.py`](../tests/unit/test_word_alignment.py) |
| Modified | [`pikaraoke/pipeline/workers/whisper_worker.py`](../pikaraoke/pipeline/workers/whisper_worker.py) — `_extract_words` filter, `_segments_to_line_objects` init, delete `_match_words_to_lines`, change `align_refine` return shape |
| Modified | [`pikaraoke/pipeline/stages/lyric_align.py`](../pikaraoke/pipeline/stages/lyric_align.py) — call NW, assign speakers, multi-style ASS |
| Modified | [`pikaraoke/pipeline/config.py`](../pikaraoke/pipeline/config.py) — `speaker_colors`, `ensemble_color` |
| Modified | [`tests/unit/test_lyric_align.py`](../tests/unit/test_lyric_align.py) |
| Modified | [`tests/unit/test_whisper_worker.py`](../tests/unit/test_whisper_worker.py) |

## Reused existing code

- [`pikaraoke.lib.genius_lyrics.parse_genius_sections`](../pikaraoke/lib/genius_lyrics.py#L95) — produces `align_text` per line
- [`pikaraoke.lib.genius_lyrics.genius_singer_mode`](../pikaraoke/lib/genius_lyrics.py#L180) — gates diarization
- [`LyricAlignStage._load_lyrics`](../pikaraoke/pipeline/stages/lyric_align.py#L126) — already returns `(text, format, structure)` and stores structure on ctx
- [`LyricAlignStage._should_write_srt`](../pikaraoke/pipeline/stages/lyric_align.py#L267) — filesystem-aware SRT gate

## Implementation order

1. Add `pikaraoke/lib/word_alignment.py`. Run `test_word_alignment.py` (port tests first or alongside) — must pass standalone.
2. Update `pikaraoke/pipeline/config.py` with `speaker_colors` / `ensemble_color`.
3. Modify `whisper_worker.py`: drop `_match_words_to_lines`, update `_extract_words` filter, update `_do_align_refine` return, update `_segments_to_line_objects` init.
4. Update `tests/unit/test_whisper_worker.py` to match (red -> green).
5. Modify `lyric_align.py`: import NW, add `_split_lines` / `_assign_speakers_from_genius` / `_reset_segment_first_flags` / ASS helpers, restructure `_generate_ass`.
6. Update `tests/unit/test_lyric_align.py` to cover new branches.
7. Run full suite + pre-commit.
8. Smoke-test a real song through the orchestrator (see verification).

Each step should leave the test suite green before the next starts.

## Verification

Test plan (manual, after the suite passes):

- [ ] `python -m pytest tests/unit/test_word_alignment.py tests/unit/test_lyric_align.py tests/unit/test_whisper_worker.py -v` passes
- [ ] `python -m pytest` (full suite) passes — no regressions in unrelated tests
- [ ] `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files` is clean
- [ ] Process a non-Genius song (plain `.txt` lyrics): ASS uses single `Karaoke` style, identical line/word timing to today, SRT identical to today
- [ ] Process a transcription-mode song (no lyrics): worker still returns line_objects, ASS unchanged
- [ ] Process a solo-Genius song (only `[Verse]` / `[Chorus]` headers, no `:` attribution): `genius_singer_mode == "solo"` -> ASS uses single `Karaoke` style, no regression
- [ ] Process a multi-singer Genius song (e.g., `[Verse 1: Brian]` / `[Chorus: All]` / `[Verse 2: AJ]`): ASS contains multiple `Style: Karaoke_<name>` rows + `Style: Karaoke_ensemble`; load in mpv and confirm distinct colors per singer and ensemble line
- [ ] Force a contraction edge case (lyrics with `don't`, `I'm`, `wanna`): line timing stays in sync — no cascading drift the count-based matcher had
- [ ] Cancel mid-alignment: orchestrator still receives `PipelineCancelled`; whisper subprocess survives and serves the next job (worker IPC change must not break cancellation path — payload type change shouldn't affect cancellation tags)
- [ ] Hallucination edge case: a song with a long instrumental break shouldn't have phantom words anchoring nearby lines to zero-duration timestamps (visible as "lines disappearing instantly" before the port)
