Model: Claude Opus 5.5 (author, 2026-10-30). Executor: Claude Sonnet 5.5. Opus reads
GATE N1; GATE N2, GATE N3 and Phase 6 go to Ken.

# Genius lyrics on LRCLIB times (Repair)

## Goal

For a mixed-language song (the KPop Demon Hunters songs), Genius has a romanized
page and LRCLIB writes the Korean in Hangul. Ken wants a Repair option that keeps
the Genius text and takes each line's time from an LRCLIB match that has passed the
LRCLIB timing check.

This builds on the `lyric_source_lists` plan, which landed on `dev` on 2026-10-30
(`1a5d059..c99e632`) and is retired as tag `archive/lyric_source_lists`. Read its plan
with `git show archive/lyric_source_lists:plans/lyric-source-lists.md`. Its LRCLIB
timing repair fits an LRC to the clip (`srt_slice_fit.fit_slice`, with mistimed and
unheard flags), and saves the fitted LRC lines as a `.lrclib.srt` sheet on the cue
route. This plan swaps in a Genius page's lines for the LRC's text and keeps the
LRC's fitted times.

Base: `dev` at `daf183a` (pushed). The branch was cut at `4e8cb26` and reset to
`daf183a` on 2026-10-30, before any work, so it carries this plan and nothing else.

History: as an automatic default this was withdrawn (S-1, 2026-09-08). An LRC can be
timed to another edit of the song, and nothing checked it. On Repair, the LRCLIB fit
check now does that, and the admin reads the result before confirming.

## Rulings (Ken, 2026-10-30)

1. **Pairing Genius lines with LRC lines.** First by text, with
   `lrclib.map_lines_to_cues` (fuzzy, order-keeping). Then, in each stretch
   between two text-paired lines, by position, but only when both sides have the
   same number of lines. A stretch with unequal counts is refused, and the card
   lists its lines. Ken's own doubt: "I have a feeling line splits will be
   different between genius and lrclib."
2. **The card shows the stretches paired by position**: each Genius line beside its
   LRC line and that line's time. Text-paired lines are not listed.
3. **Where the Genius sheet comes from**: a lyrics choice on the LRCLIB timing card,
   "the LRC's own" or "a Genius page", reusing the Genius card's search and pick.
   One step.
4. **Test song: Your Idol** (KPop Demon Hunters).
5. **A plan of its own, with testing first.** Ken: it "could use some testing first".

## What the library shows today (2026-10-30, read only)

Counted on `/home/ken/shared-drives/D:/Shared/pikaraoke-songs`, with no lyric text
printed. "Latin" means Latin letters only, which can be English or romanized Korean.

| Song | Timed by now | Sheet now | Bundle sheet lines (Hangul / mixed / Latin) | LRC lines (Hangul / mixed / Latin) | Bundle lines that text-pair with the LRC |
|---|---|---|---|---|---|
| Your Idol | cue align | `.lrclib.srt` (the LRC's own) | 59 (1 / 7 / 51) | 59 (1 / 7 / 51) | 51 |
| Takedown | cue align | `.lrclib.srt` (the LRC's own) | 52 (3 / 1 / 48) | 52 (3 / 1 / 48) | 35 |
| Golden | joint | Genius | 51 (3 / 5 / 43) | 46 (3 / 2 / 41) | 35 |
| Soda Pop | joint | Genius | 64 (11 / 2 / 51) | 59 (9 / 2 / 48) | 46 |
| Seven | joint | Genius | 79 (0 / 0 / 79) | 77 (0 / 0 / 77) | 56 |

Rechecked at `daf183a`, after `8dabf55` changed how `lrc_to_srt` merges lines: none of
the five LRCs stamps two lines at one start, so the LRC line counts above are also the
counts after the merge (read only, counts only).

What this changes from the hand-off that started this plan:

- **Your Idol and Takedown are already LRCLIB-timed.** Ken repaired both with the
  LRC's own text (Your Idol at 2026-10-30 00:12 UTC). Their bundles no longer hold a
  Genius sheet, so Phase 1 fetches one. It also means Your Idol already has a
  version for Ken to compare against by ear.
- **The LRCs are not all Hangul.** In Your Idol's LRC, 8 of 59 lines hold Hangul,
  and 7 of those mix it with English words. The Genius pages Ken has in mind mostly
  differ from the LRC in those few lines.
- **Your Idol's unheard stretches are not the Korean parts.** Lines 0-9 are the
  intro chant, in English with Latin words in brackets. Lines 28-35 are mostly
  English, and only line 31 is Hangul alone. The transcriber missed them for other
  reasons (a choir, a fast rap). They stay a fair test, but not of Korean.
- **Hangul never pairs by text.** `lrclib.normalize_line` keeps only `a-z0-9`
  after folding to ASCII, so a Hangul-only line becomes empty, and a mixed line
  keeps only its English words. Text pairing therefore anchors on the English
  lines, and the Hangul lines are reached only by position. That is the shape
  ruling 1 assumes.
- **Seven has no Hangul on either side.** It is the control for Ken's line-split
  doubt: any stretch refused there is a line split, not a script difference.
- **Soda Pop's LRC fit is refused today** (`disagree`, GATE A report), so it can't be
  offered. It still counts for pairing.

## Conflicts and risks

- **Decision 1 of the parent plan** (in the tag: "the LRC's own lyrics are the sheet") stands
  because the flags check the LRC's lines, not the sheet. With Genius text, a wrong
  pair gives a correct time with the wrong words, and no flag shows it. Ruling 2 is
  the answer for position pairs. Text pairs go unlisted because they already say
  nearly the same thing (similarity of at least 0.85 after normalising).
- **A refused stretch refuses the whole option.** Cue align needs a time for every
  sheet line, so a Genius line that can't be paired leaves nothing to save. This is
  how this plan reads ruling 1. If Phase 1 shows refusals are common, the fallback
  is Ken's call at GATE N1 (options listed there).
- **Word timing inside romanized lines.** Line times come from the LRC, so they will
  be right. But cue align passes each line's text to the stable-ts aligner, which is
  set to English (`pipeline/config.py`, `language = "en"`). Words in a romanized line
  may land loosely. A line the aligner can't cover falls back to evenly paced words
  across its window (`cue_align.repace_bad_lines`). Today's Your Idol hands the same
  aligner Hangul in those lines, so it's an A/B, not a new risk alone. Ken's ear
  decides at GATE N2, and that needs a GPU run on Windows.
- **The cue route cleans the sheet again.** The saved sheet is an SRT, so loading it
  runs `srt_cues.cue_spans_from_srt` over the Genius text. That strips speaker labels
  and `*` marks, recases a file typed in capitals, and drops lines that clean to
  nothing. Phase 1 counts how many Genius lines change or drop on that reload.
- **Duet lines.** `lrc_to_srt` merges LRC lines stamped at the same start into one
  cue, and `cue_spans_from_srt` joins that cue's lines with a space, so one LRC line
  can stand for two Genius lines. That makes a stretch with unequal counts, which
  gets refused. Since `8dabf55` the merge keeps both singers' lines for every stamp
  (before it, a stamp such as 01:08.04 lost the first singer's line), so a duet now
  shows up here as it is. Phase 1 shows how often it happens.

## Open questions

None for the GATEs beyond their own questions. Rulings 1-5 cover the shape, and the
rest below are the author's defaults. Raise any that look wrong.

One open point, for Phase 4 to settle (not a stop): **the new kind is its own repair
source.** `REPAIR_SOURCES` is `("caption", "genius", *SHEETS, "transcribe")` and
`repair` sets `replaces_custom = source not in SHEETS`, so a `lrclib_genius` entry in
`SHEETS` is a repair source of that name without further code. The Design below still
says `repair(source="lrclib", genius_id=...)`. The two ways:

- **`source="lrclib_genius"`**, carrying `genius_id` and `lrclib_id`. Follows the table:
  source and kind are one name, and `repair` gains one branch beside `lrclib`. The
  page sends this source when "a Genius page" is picked. The author leans here.
- **`source="lrclib"` with `genius_id`**, `repair` choosing the kind from the id. Source
  and saved kind then differ, and `replaces_custom`, the route's source check and the
  page's `preselect` each need a second look.

Phase 4 picks one and records why in the Results log.

## Defaults (author's; not ruled)

- **Pairing is library code from the start.** `pikaraoke/lib/lrc_pairing.py`
  holds the pairing and the sheet build, with unit tests. The Phase 1 probe calls
  them. That way the GATE measures the function the feature ships, not a copy in a
  script.
- **The LRC side of the pairing is the fitted lines**, as the cue route would load
  them: `cue_spans_from_srt(fit.srt)`, which gives each line's text and clip-time
  span. The flags (`fit.mistimed`, `fit.unheard`) index `fit.lines`. These two lists
  should match line for line. If they ever don't, stop (row 7 of the parent plan, in
  the tag, says how they can drift). A span ends at the next stamp, a blank one
  included, so a line before an instrumental break ends at the break; the last line
  holds `LRC_LAST_LINE_HOLD_S`. `timed_sheet_srt` takes the spans as they are.
- **The stretches at either end** (before the first text pair, after the last) follow
  the same rule as the ones between pairs. A Genius intro that the clip doesn't sing
  is an unequal stretch, so it's refused.
- **Viable** = the LRC check is viable as it is today, AND no stretch is refused.
  The length override (`LrcTimingCheck.overridable` and `repair(..., allow_gap)`,
  `8767f65`) still applies to the gap. A refused stretch can never be overridden. Note
  that `_fit_lrc_timing` sets `overridable=fits and not viable`: with a refused
  stretch that is true, so the formula must also require no refused stretch (Design,
  Phase 4).
- **Its own sheet kind**, not the `.lrclib.srt` one. The handoff suggested the same
  kind with its own origin label. But the origin is read off the sheet's suffix on
  every replay: `library_regen.custom_plan` finds the sheet on disk, `sheet_kind` names
  its kind, and `sheet_plan(song, kind)` takes the origin from `SHEETS[kind]`. With a
  shared suffix, the first Regenerate, bulk run or Reset would relabel the song
  "LRCLIB timing". So a new entry in `library_regen.SHEETS`:
  - suffix `.lrclib-genius.srt`. It must not end in another sheet's suffix:
    `sheet_kind` matches the table's suffixes with `endswith`, first hit, so
    `.genius.lrclib.srt` would read as an LRC sheet;
  - origin `lrclib_genius_srt` (a constant beside `LRC_ORIGIN`), kind `lrclib_genius`,
    label "LRCLIB timing, Genius lyrics" (the plan's label, as the others);
  - `SHEETS` is the one place: backups (the `"lyrics"` suffix tuple), Reset
    (`custom_plan`), the one-sheet rule (`_sheet_files`), `sheet_plan` and the History
    `_pick` rule (`song_info._pick` tests the table's origins) read it, so none of
    them changes. The repair source is the open point above.
- **Once saved, the Genius page is never fetched again.** The sheet holds the text
  and the times, as the LRC sheet does. The Genius id is not stored.
- **The LRCLIB search on the card scores against the Genius sheet** once a Genius
  page is picked (`LibraryTools.genius_sheet_lines`, already used by step 2's
  search). Until then it scores against the song's current lines, as today.

## Design (sketch; Phase 4 settles it after GATE N3)

### `pikaraoke/lib/lrc_pairing.py` (Phase 1)

```python
@dataclass(frozen=True)
class Stretch:
    sheet: tuple[int, int]  # half-open range of Genius line indexes
    lrc: tuple[int, int]    # half-open range of LRC line indexes

@dataclass(frozen=True)
class Pairing:
    by_text: dict[int, int]          # Genius line -> LRC line
    by_position: tuple[Stretch, ...] # equal counts, paired in order
    refused: tuple[Stretch, ...]     # unequal counts

def pair_lines(sheet: list[str], lrc_lines: list[str]) -> Pairing: ...
def timed_sheet_srt(sheet: list[str], spans: list[tuple[float, float]], pairing: Pairing) -> str: ...
```

- `pair_lines`: `map_lines_to_cues(sheet, lrc_lines)` for the text pairs. Then walk
  the gaps between consecutive pairs, plus the two ends. A gap that is empty on
  both sides is nothing. Equal counts go to `by_position`; unequal counts
  (including one side empty) go to `refused`.
- `timed_sheet_srt`: one SRT cue per Genius line, at its paired LRC line's span.
  Raises `ValueError` when `pairing.refused` is not empty, since a line with no time
  is no sheet.
- Tests (invented lines only): all lines pair by text; a stretch of Hangul-only LRC
  lines between two English pairs, with equal counts; the same with unequal counts;
  a stretch at the start and at the end; one side empty; a duet LRC line merged with
  `\n` against two Genius lines; a repeated chorus where text pairing must keep
  each instance in its own place; `timed_sheet_srt` round-trips through
  `cue_spans_from_srt` to the same lines and spans.

### Check, plan, repair (`library_tools.py`, `library_regen.py`, Phase 4)

- `check_lrc_timing(song_path, lrclib_id, genius_id=None)`. With a `genius_id`, fetch
  the sheet (`genius_sheet_lines`) and pair it against the fit's lines. The pairing
  goes into `_fit_lrc_timing(job, record, sheet=None)`, the one function the check and
  the repair both call, so the repair redoes it on the server. The check gains
  `pairing: Pairing | None`. `viable` also needs `pairing.refused` to be empty, and
  `overridable` too: today `overridable=fits and not viable` would be true for a
  refused stretch, which `allow_gap` must not open.
- The repair re-runs the check on the server (as `_lrc_repair_plan` does today: one
  `_lrc_record`, one `_fit_lrc_timing`). It refuses with `LrcTimingRefused` and, when
  viable (or overridable with `allow_gap`, nothing refused), queues
  `sheet_plan(song, "lrclib_genius", timed_sheet_srt(...))`. `sheet_plan` already takes
  the kind, so there is no new plan wrapper. A record given by id becomes the song's
  `.lrc`, as for `lrclib`. Which `source` name reaches `repair` is the open point under
  Open questions.
- `GeniusUnavailable` during the check becomes a `RegenError` with the Genius card's
  wording (`_genius_plan`'s "Genius didn't return that song's lyrics. Try again.").

### Route and page (`routes/song_info.py`, `song_repair.html`, Phase 5)

- `POST /song_info/lrc_fit` takes an optional `genius_id`. The LRC card gains a
  "position-paired" list (each pair: Genius line, LRC line, `m:ss`) and a "can't
  pair" list (each refused stretch: its Genius lines and its LRC lines, with times).
- The LRCLIB timing section gains the lyrics choice (ruling 3). Picking "a Genius
  page" opens the Genius card's search box and list (`searchGenius`,
  `geniusOption`). A new pick clears the answer, as a new LRC pick does.
- Labels. `SHEETS` carries the suffix, origin and plan label, and `song_info._pick`
  reads it, but these sites still test one origin or kind by name, and a missing branch
  mislabels silently. Find them with `grep -rn "LRC_ORIGIN\|\"lrclib\"" pikaraoke`;
  rows 15-16 of the parent plan (in the tag) say why each exists:
  - `routes/song_info.py`: `_source_name`, `_route_text`, `_lrclib_tile` and the
    `lrclib_row` test, and `_versions` (History; an origin with no branch there reads
    "YouTube captions");
  - `routes/library.py`: `_now_text` (`LibraryTools._now` hands it the kind, so a missing
    branch reads "Now: no recorded lyric source") and the `("caption", "movie", "lrc")`
    "Cue align" subline;
  - `lib/library_status.py`: the `lrclib=` match read off the `.lrc` header (a cue run
    records none), the `SONG_LISTS["lrc"]` rule (Phase 6 expects the song on the LRCLIB
    list) and the `SongStatus.sheet_kind` comment;
  - `templates/processing.html`: the tools-tab "LRCLIB · cue align" row counts that list.
  Each gets a route or status test; the Phase 5 commit lists any site found beyond these.

## Phases

### Phase 0: branch and baseline

- [x] `git worktree add ../pik-genius-lrc -b genius_lrc_timing 4e8cb26` (the author,
      2026-10-30). The plan file is untracked. Never switch branches in
      `/home/ken/pikaraoke`: another session works there.
- [x] Reset to the landed base (the executor, 2026-10-30): `git log 4e8cb26..HEAD` was
      empty and only this plan untracked, then `git reset --hard daf183a`. This plan
      updated for the landing in its own `docs(plans)` commit (Results row 2).
- [x] Full suite in the worktree (`python -P -m pytest -q`; `-P` so the main
      checkout doesn't shadow the worktree). Log the pass count as the baseline.
      Baseline: 2998 passed at `61d00cf` (Results row 3).

### Phase 1: pairing, then the probe -> GATE N1 (Opus reads, Ken rules)

- [ ] Write `pikaraoke/lib/lrc_pairing.py` and `tests/unit/test_lrc_pairing.py` to
      the Design section. Commit: `feat(lyrics): pair a lyric sheet's lines with an
      LRC's, by text then by position`.
- [ ] Find the Genius pages. For Your Idol, Golden, Takedown and Soda Pop, run
      `GeniusClient.search("<title> romanized")`, using the token from the
      preferences, as `scripts/regen_alignment_bundles.py` builds its client. Take the
      hit whose artist is Genius Romanizations, and log each id, title and artist in
      the Results log. Seven uses its bundle's Genius sheet (no romanized page
      needed). If a song has no romanized hit, or more than one, stop and ask Ken.
- [ ] Write `scripts/genius_lrc_pairing_report.py`, modelled on
      `scripts/lrc_timing_report.py`. Read only. It prints indexes, counts and times,
      never lyric text. It reads each song's LRC through `lrclib.read_song_lrc` and the
      status's `lrc_match`, as that script does since `5e20312`, and fits it with
      `fit_slice(lrc_to_srt(...))` as `_fit_lrc_timing` does.
  - Arguments: `--folder` (default `get_default_dl_dir`; on the VM pass the D: path
    above) and `--song "<name part>=<genius id>"`, repeatable. With no id after
    `=`, the bundle's own Genius sheet is used.
  - **Table 1**, one row per named song: the LRC fit's status on its best stream,
    and whether pairing ran on the fitted lines or (fit refused) on all the LRC's
    lines; Genius lines; LRC lines; text-paired lines; position-paired lines and
    their stretch count; refused stretches, each as `genius a-b / lrc c-d`; and the
    viable verdict under the Defaults. Also the Genius lines changed or dropped
    when `timed_sheet_srt`'s output is reloaded with `cue_spans_from_srt`, and
    whether `fit.lines` and `cue_spans_from_srt(fit.srt)` match.
  - **Table 2**, the same columns for every Genius-origin song with a usable LRC,
    using its bundle's Genius sheet. No network. This answers Ken's line-split doubt
    across the library, not only for five songs.
  - `--write-sheet DIR`: for each viable song, write the built sheet to `DIR` as
    `<stem>.lrclib-genius.srt`. Also write a list of the line indexes and clip
    times where its text differs from the LRC's own sheet, as the places to listen.
    `DIR` must not be the library folder; the script refuses it.
- [ ] Run it for the five songs, plus Table 2. Paste the raw output into a "GATE N1
      report output" section at the end of this plan, and add one Results row. The
      report carries no text, so it may be committed.
- [ ] Commit the script: `feat(scripts): report how a Genius sheet pairs with an
      LRC's lines`. Plan updates go in their own `docs(plans)` commits.
- [ ] **GATE N1: stop.** No verdict on the executor side. Ask Ken to `/model` to
      Opus for the read. The question for Ken: does pairing cover Your Idol with
      nothing refused, and how often do line splits refuse a stretch elsewhere,
      Seven included? If refusals are common, Ken picks the fallback, for example:
  - keep refusing (the option works only on songs whose splits agree);
  - in a refused stretch, use the LRC's own lines there (mixed text, all lines
    timed);
  - spread the stretch's Genius lines evenly over the LRC stretch's time span
    (all Genius text, rougher line times, and the card says so).

  A fallback changes `pair_lines` or `timed_sheet_srt` and their tests before
  Phase 2.

### Phase 2: Your Idol by ear -> GATE N2 (Ken)

No feature code. The saved sheet is a plain file the cue route already reads, so
the existing Regenerate can time it.

- [ ] Run the probe with `--write-sheet` into `D:\Shared\genius_lrc_probe\`
      (`/home/ken/shared-drives/D:/Shared/genius_lrc_probe/` here).
- [ ] Copy Your Idol's current `lyrics/<stem>.lrclib.srt`, its `.ass` and its
      bundle into that folder, so Ken can compare and put them back.
- [ ] Put the built sheet in place as `lyrics/<stem>.lrclib.srt`, overwriting the
      LRC's own (the copy is in the probe folder). Use the existing suffix: the new
      kind doesn't exist yet, and Regenerate replays `.lrclib.srt` on the cue route.
- [ ] Hand Ken one PowerShell block for Windows: fetch the branch from remote `vm`,
      start the app with `uv run`, open Your Idol's Song Info, press Regenerate
      (not Reset). Then listen, mostly at the lines the probe listed. Memory
      `project_gpu_runs_via_windows` has the remote and the D: rules.
- [ ] Log Ken's read in the Results log. Then put the old sheet, `.ass` and bundle
      back, unless Ken wants to keep the Genius version.
- [ ] **GATE N2: Ken's ear.** Are the romanized lines' words timed well enough
      next to today's version? If not, the choices are: build anyway (line times
      right, words rough), or stop the plan here. The aligner's language is out of
      scope.

### Phase 3: mockup -> GATE N3 (Ken)

- [ ] Build an HTML mockup of the LRCLIB timing card with the lyrics choice,
      styled from `song_repair.html`'s `rp-*` CSS, and publish it as an Artifact. The
      parent plan's mockup is the reference (Results row 12 of
      `archive/lyric_source_lists:plans/lyric-source-lists.md`, which has its link).
      Use invented lyrics only. States:
  - lyrics choice on "the LRC's own" (today's card, unchanged);
  - "a Genius page" picked, search open, a hit picked;
  - fits and viable: all lines paired by text (no list);
  - fits and viable, with position-paired stretches listed;
  - a refused stretch (not viable), with its lines listed;
  - a flagged run beside Genius lyrics. Ruling needed: are the flag's lines shown
    in the LRC's text (what was checked) or the paired Genius text?
  - length too far off, with the "Use this match anyway" box (`8767f65`), and Genius
    lyrics;
  - Genius unavailable;
  - the source when it is current (the saved sheet holds no Genius id, so the
    choice can't show which page).
- [ ] **GATE N3: Ken ratifies the mockup.** Log his changes. No page code before
      this.

### Phase 4: server side

- [ ] The new `SHEETS` entry (Defaults), the Check, plan, repair section, and the
      repair-source open point (Open questions): pick one, log why.
- [ ] Tests: `test_library_regen.py` (the plan shape; saving it removes the other
      kinds and the other kinds remove it; Reset and bulk runs replay it with its own
      origin; the backup claims it; `sheet_kind` tells it from `.lrclib.srt`).
      `test_library_tools.py` (a viable check with Genius lyrics; a refused stretch
      is not viable and can't be overridden; the repair re-runs both the fit and the
      pairing on the server; Genius unavailable; the saved sheet's text is
      Genius's and its times are the fitted LRC's).
- [ ] Commit: `feat(repair): LRCLIB timing can keep a Genius page's lyrics`.

### Phase 5: page and labels

- [ ] Build the ratified mockup, the route change and the labels (the sites listed
      under Route and page).
- [ ] Route tests: `genius_id` validated as `lrclib_id` is; the card's paired and
      refused lists; Repair sends `genius_id`; admin only.
- [ ] Commit: `feat(repair): the LRCLIB timing card offers a Genius page's lyrics`.
- [ ] Checkpoint: review due (Checkpoints below).

### Phase 6: end to end -> Ken's checks (Windows, GPU)

- [ ] Your Idol: Repair, LRCLIB timing, "a Genius page", pick the romanized page,
      Check fit, Regenerate. Confirm Song Info reads cue align and names the new
      source, the song shows in the LRCLIB list, and get Ken's read of the karaoke.
- [ ] A song with a refused stretch from the GATE N1 report: the card lists it and
      Regenerate stays off.
- [ ] Reset Your Idol: the sheet survives, is replayed and keeps its label.
- [ ] Repair Your Idol back to "the LRC's own": the Genius sheet is removed.
- [ ] `plans/open-issues.md`, in one `docs(plans)` commit: record this option under
      the LRCLIB-timing entry, with this branch's commits.

## Rules for the executor

- Plain-language chat. Raw tables go in the Results log (CLAUDE.md, Communication).
- Never commit lyric text, Genius or LRC. Tests use invented lines. Probe output
  carries indexes, counts and times only. The built sheets in the probe folder hold
  real text and stay off git.
- Work in `/home/ken/pik-genius-lrc` only. Run Python with `-P`.
- Tests: `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest`. Pre-commit on
  changed files only:
  `pre-commit run --config code_quality/.pre-commit-config.yaml --files <files>`.
- Import-smoke the changed modules and read `git diff --cached` before each commit.
  Plan edits go in their own `docs(plans)` commits.
- After code changes: `graphify update .`.
- Stop at each GATE, and after each phase's relay so Ken can `/compact`. If a step
  contradicts the code, stop and say so.

## Checkpoints

- GATE N1: hand to Opus with the branch, HEAD and this file's "GATE N1 report
  output" section. The read says what the counts show, without choosing the
  fallback; that is Ken's call.
- After Phase 5: review due.
  `/code-review high <Phase 1 first commit>^..HEAD`, files in
  `pikaraoke/lib/{lrc_pairing,library_regen,library_tools,library_status}.py`,
  `pikaraoke/routes/{song_info,library}.py`,
  `pikaraoke/templates/{song_repair,processing}.html`. Three finder angles:
  1. **Correctness**: does every saved Genius line carry its paired LRC line's
     fitted time, and does the repair redo the pairing on the server?
  2. **Simplicity**: one pairing function, `sheet_plan` with no new wrapper, the Genius search
     reused rather than copied.
  3. **Robustness**: Genius unavailable mid-check, a duet line, a suffix that
     `sheet_kind` could misread, a song that's busy.

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
| 1 | 2026-10-30 | 0 | `git worktree add ../pik-genius-lrc -b genius_lrc_timing 4e8cb26`; read-only script counts on the five songs (table in "What the library shows today") | Branch at `4e8cb26`. Your Idol and Takedown are already LRCLIB-timed with the LRC's own text. Hangul normalises to nothing for text pairing. |
| 2 | 2026-10-30 | 0 | Executor (Sonnet 5.5): `git log 4e8cb26..HEAD` empty and only this plan untracked, then `git reset --hard daf183a` (dev, pushed). Plan updated for the landing. Read only: LRC line counts for the five songs before and after the duet merge. | Branch now at `daf183a`. Parent plan read from `archive/lyric_source_lists`. Changes from the dev commits `7ab4252`, `8dabf55`, `ffd021d`/`eca03ce`, `8767f65`: sheet kinds are one `SHEETS` table (the Defaults bullet and the label list rewritten to it); `check_lrc_timing` and `_fit_lrc_timing` signatures as they are now; the length override has landed (Viable default, Phase 3 state); `overridable=fits and not viable` would be true for a refused stretch, so the formula needs the pairing too (Design, Defaults); the new kind is its own repair source (open point for Phase 4, not a stop); the label sites listed from the code. The five LRCs have no lines stamped at one start (raw sung stamps = lines after the merge: 59 / 52 / 46 / 59 / 77), so the library table needed no change. Phase 3's wait-and-rebase step and the Rebase risk dropped. |
| 3 | 2026-10-30 | 0 | `/home/ken/miniconda3/envs/pik/bin/python -P -m pytest -q -p no:cacheprovider` in the worktree at `61d00cf` (code identical to `daf183a`; the commit adds only this plan) | **2998 passed**, 0 failed, 58.8 s. This is the baseline. Checked that the run used the worktree's code: a plugin printing `pikaraoke.__file__` after `tests/unit/test_lrclib.py` gave `/home/ken/pik-genius-lrc/pikaraoke/__init__.py`. **Trap for scripts:** a bare `python -P -c "import pikaraoke"` in the worktree gives `/home/ken/pikaraoke/pikaraoke` (the env's editable install points at the main checkout), and only pytest's own path setup reaches the worktree. A script run from the worktree must put its own repo root first on `sys.path`, as `scripts/lrc_timing_report.py` does (`sys.path.insert(0, parents[1])`); Phase 1's script copies that line. |
