# CLAUDE.md

PiKaraoke: karaoke server with YouTube search, queuing, pitch shifting, and automatic karaoke creation (stem separation + Whisper lyric alignment, CUDA GPU expected).

**Architecture:** songs play in a native libmpv window on the host (`lib/mpv_controller.py`, overlays in `lib/overlay_manager.py`). The Flask + Socket.IO pages are only the phone remote and admin UI. Upstream's browser player, splash page, HLS streaming, and gevent server were removed; don't restore or design around them. "Splash" in current code means the MPV idle screen; any other mention of a browser splash screen is stale.

**Core:** Code clarity over docs. Simplicity over flexibility. Single source of truth.

## Code Style

- Type hints in modern syntax (`str | None`, Python 3.10+); Black and pylint enforce the rest of PEP 8
- Concise docstrings for public APIs—explain "why", not "how"
- No emoji

## Refactoring

Refactor only code you're touching, when it's hard to follow, does too much (a class per responsibility, a function past ~50 lines), or a pattern reaches its third copy. Delete what the change supersedes, old methods and their tests included; never comment code out.

## Filenames

YouTube videos: exactly 11-char IDs only: `Title---dQw4w9WgXcQ.mp4` or `Title [dQw4w9WgXcQ].mp4`

## Error Handling

- Catch specific exceptions, never bare `except:`. Log errors, never swallow silently
- Use context managers for resources

## Testing

pytest with mocked external I/O/subprocess. Test business logic and integration, skip trivial getters/setters. Use real `EventSystem` and `PreferenceManager` instances.

## Self-Review

Before calling a change done, review your own diff on three axes:

- **Correctness** — does it do what it intended?
- **Simplicity** — simplest thing that works; no dead code, duplicate logic, speculative abstraction, unrequested scope, or handling for impossible states; reuse helpers; single source of truth
- **Robustness** — see Error Handling; plus no races/TOCTOU, safe edge/metachar inputs, no hardcoded paths; temp files via `get_temp_directory()` (`get_platform.py`), never `tempfile.gettempdir()`

On commits that add or rewrite logic (skip pure delete/move/rename): if the change is simple enough to verify in one read-through, say the self-review above covers it; if it's complex — multi-file, new algorithm, core pipeline/concurrency — track it as pending for the next checkpoint.

## Design Proposals

When Ken proposes a larger feature (anything that would get a plan or span several commits — not tweaks or fixes), ask clarifying questions before writing a plan or code: scope, success criteria, tradeoffs not yet weighed, and anything in the code that contradicts the proposal. Push back when the proposal looks wrong. If nothing is genuinely open, say so in one line and list the assumptions instead of inventing questions.

## Checkpoints

At a commit with its plan-log row written, or a phase/GATE boundary (never mid-commit), say which of these apply, each with a ready-to-paste prompt (≤10 lines, paths and hashes rather than prose):

- **`/compact`** — a `/compact Keep: ...` line naming branch + HEAD, the plan file and section, the next step and where to stop, open decisions with their options, and approaches ruled out this session. One fenced block of ≤5 lines with no blank lines, headings, or bullets; anything longer or broken up gets read as a regular message, not a command to paste.
- **Review due** — the exact `/code-review` line: commit range, files in scope, and exactly 3 finder angles, one per Self-Review axis (not the tool's default spread). Never launch it unprompted; run it only when asked. `/code-review ultra` is user-triggered only, never launched for any reason.
- **Model handoff** (e.g. Sonnet handing a GATE read to Opus, Opus escalating to Fable) — branch + HEAD, the plan file and section, what's done (don't redo it), the next step, and where to stop.

## Review Triage

End every code review with the surviving findings sorted into three groups, each with a one-line recommendation (fix now, fold into the next commit, or log in `plans/open-issues.md`):

- **Critical** — wrong output, data loss, crash, or race; fix before anything else lands.
- **Easy** — a few-line fix with no design question; fix now while the context is loaded.
- **Worthwhile** — real but larger, or touching a design decision; say what it costs and whether it is worth doing now or should wait.

For findings that fit none, decide whether each belongs in `plans/open-issues.md`: propose an entry for any that is real but not worth fixing now, and drop the rest (false alarms, style nits, accepted tradeoffs) with one line saying how many and why.

Then check `plans/open-issues.md` for entries in the files the review covered, skipping anything already ruled, out of scope, or recorded-not-fixed. List any that are now Easy, since those files are loaded and about to be re-tested, under a fourth group, **From open issues**, with the entry's heading. Say "none" if nothing qualifies.

## Communication

- Plain language. Lead with the consequence — what is decided, blocked, or the user's call. Keep a number only when the number *is* the finding. Explain a mechanism by what it does, not what it is called.
- Vocabulary from `plans/` (gate letters, phase numbers) is shared language — use it directly. Code-level detail is out by default: no recomputed arithmetic, per-song tables, constant names, or metric decompositions. That lives in the plan's Results log; the user asks when he wants it.
- Chat tone only. Plan entries keep raw tables, full provenance, and no verdicts. Simplify the relay, never the record.

## Commits

- Group by feature, not file—each commit coherent and self-contained. Tests ride with the code they exercise.
- Before committing: compile/import-smoke the changed code, strip debug prints, and read `git diff --cached` against what you intended.

## Branches and Archive Tags

- Features run on their own branch. Landing copies the code commits onto `dev` one by one, in order, with their messages: no merges, no squash, no plan-only commits, and `plans/<feature>.md` edits stripped from mixed commits. Among plans, `dev` carries only `plans/open-issues.md`.
- A finished branch is retired as an annotated tag, never deleted bare, because it is the only home of its plan docs: `git tag -a archive/<branch> <branch> -m "Archived <date>: <why>"`, push the tag, check `git ls-remote origin 'refs/tags/archive/*^{}'` matches, then delete the branch locally and on origin. Research branches that never landed retire the same way.
- The tag keeps the branch name, so an old `on <branch>` reference resolves as `archive/<branch>`. Repoint live references in `plans/open-issues.md` when retiring.
- Read old plans with `git show archive/<branch>:plans/<file>.md`; search all of them with `git grep <term> $(git tag -l 'archive/*') -- plans/`.

## Environment

Conda env `pik` (not uv). Run tests: `/home/ken/miniconda3/envs/pik/bin/python -m pytest`. Run pre-commit on the files you changed: `pre-commit run --config code_quality/.pre-commit-config.yaml --files <files>` (`--all-files` rewrites untouched upstream Python via pycln/isort). Tools: Black (100 char), isort, pycln, pylint, mdformat.

## Plans

Store in `plans/` with descriptive kebab-case names (e.g., `subtitle-delay-cleanup.md`). Name the executing model at top, e.g. `Model: Claude Sonnet 5.5`.

## Codebase Ownership

Forked from vicwomg/pikaraoke (last sync 2026-03-22), never merging from it again: edit any file when that's the clean change, and put large new subsystems in their own modules.

## graphify

When `graphify-out/graph.json` exists (local, uncommitted, code-only), it is a call/import graph of the code. It is precise for named symbols and weak for prose questions, so use it alongside search, not before it:

- **Callers, callees, impact:** `graphify explain "<symbol>"` and `graphify affected "<symbol>"` — exact, including which tests cover a function. Prefer these to grepping for call sites.
- **`query`:** pass code-name words (`"transpose pitch semitones"`), never a sentence — it matches words against symbol names, so prose seeds on test helpers.
- **`path`:** name both ends as `file::symbol` and end on a function, not a class. A hop marked `uses [INFERRED]` means the real call chain is not in the graph (calls through a returned object or `self.<attr>` are not resolved) — search instead.
- **Use search for:** module-level constants (not in the graph), strings, and anything the graph misses.
- After changing code, run `graphify update .` (local, no API cost).
