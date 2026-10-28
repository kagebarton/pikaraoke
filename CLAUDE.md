# CLAUDE.md

PiKaraoke: karaoke system for Raspberry Pi/Windows/macOS/Linux with YouTube search, queuing, pitch shifting.

**Core:** Code clarity over docs. Simplicity over flexibility. Single source of truth.

## Refactoring

Refactor iteratively when touching code:

- Extract classes for multiple responsibilities, functions for repeated logic or >50 lines
- Rename unclear names, delete dead code (never comment out)
- Delete old methods/tests when superseded

**Refactor when:** modifying hard-to-understand code, third similar pattern, function doing too much\
**Don't refactor:** unrelated code, working untouched code, speculative flexibility

## Code Style

- PEP 8, 4 spaces, meaningful names, type hints (modern syntax: `str | None`, Python 3.10+)
- Concise docstrings for public APIs—explain "why", not "how"
- No emoji

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
- **Simplicity** — simplest thing that works; no dead code, duplicate logic, speculative abstraction, or unrequested scope; reuse helpers; single source of truth
- **Robustness** — see Error Handling; plus no races/TOCTOU, safe edge/metachar inputs, cross-platform paths via `get_temp_directory()`

On commits that add or rewrite logic (skip pure delete/move/rename): if the change is simple enough to verify in one read-through, say the self-review above covers it; if it's complex — multi-file, new algorithm, core pipeline/concurrency — track it as pending for the next checkpoint.

## Design Proposals

When Ken proposes a larger feature (anything that would get a plan or span several commits — not tweaks or fixes), ask clarifying questions before writing a plan or code: scope, success criteria, tradeoffs not yet weighed, and anything in the code that contradicts the proposal. Push back when the proposal looks wrong. If nothing is genuinely open, say so in one line and list the assumptions instead of inventing questions.

## Checkpoints

At a commit with its plan-log row written, or a phase/GATE boundary (never mid-commit), say which of these apply, each with a ready-to-paste prompt (≤10 lines, paths and hashes rather than prose):

- **`/compact`** — flag it.
- **Review due** — the exact `/code-review` line: commit range, files in scope, and exactly 3 finder angles, one per Self-Review axis (not the tool's default spread). Never launch it unprompted; run it only when asked. `/code-review ultra` is user-triggered only, never launched for any reason.
- **Model handoff** (e.g. Sonnet handing a GATE read to Opus, Opus escalating to Fable) — branch + HEAD, the plan file and section, what's done (don't redo it), the next step, and where to stop.

## Communication

- Plain language. Lead with the consequence — what is decided, blocked, or the user's call. Keep a number only when the number *is* the finding. Explain a mechanism by what it does, not what it is called.
- Vocabulary from `plans/` (gate letters, phase and rung numbers, route and probe names) is shared language — use it directly. Code-level detail is out by default: no recomputed arithmetic, per-song tables, constant names, or metric decompositions. That lives in the plan's Results log; the user asks when he wants it.
- Chat tone only. Plan entries keep raw tables, full provenance, and no verdicts (`plans/PROGRAM.md`). Simplify the relay, never the record.

## Commits

- Group by feature, not file—each commit coherent and self-contained. Tests ride with the code they exercise.
- Before committing: compile/import-smoke the changed code and read `git diff --cached` against what you intended.

## Environment

Conda env `pik` (not uv). Run tests: `/home/ken/miniconda3/envs/pik/bin/python -m pytest`. Run pre-commit on the files you changed: `pre-commit run --config code_quality/.pre-commit-config.yaml --files <files>` (`--all-files` rewrites untouched upstream Python via pycln/isort). Tools: Black (100 char), isort, pycln, pylint, mdformat. Never commit to `master` directly.

## Plans

Store in `plans/` with descriptive kebab-case names (e.g., `subtitle-delay-cleanup.md`). Name the executing model at top, e.g. `Model: Claude Sonnet 5.5`.

## Pull Requests

Include test plan: minimal checklist for manual verification.

## Codebase Ownership

Forked from vicwomg/pikaraoke; last upstream sync 2026-03-22, no plan to merge from it again. Edit any file when that's the clean change. Keep large new subsystems in their own modules for size and clarity, not merge cost.

## Rules

- Don't add unrequested features, error handling for impossible states, or speculative abstractions
- Never commit debug prints or commented code
- Temp files: use `get_temp_directory()` from `get_platform.py`, never hardcode paths or `tempfile.gettempdir()`

## graphify

When `graphify-out/graph.json` exists (local, uncommitted, code-only), it is a call/import graph of the code. It is precise for named symbols and weak for prose questions, so use it alongside search, not before it:

- **Callers, callees, impact:** `graphify explain "<symbol>"` and `graphify affected "<symbol>"` — exact, including which tests cover a function. Prefer these to grepping for call sites.
- **`query`:** pass code-name words (`"transpose pitch semitones"`), never a sentence — it matches words against symbol names, so prose seeds on test helpers.
- **`path`:** name both ends as `file::symbol` and end on a function, not a class. A hop marked `uses [INFERRED]` means the real call chain is not in the graph (calls through a returned object or `self.<attr>` are not resolved) — search instead.
- **Use search for:** module-level constants (not in the graph), strings, and anything the graph misses.
- After changing code, run `graphify update .` (local, no API cost).
