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

Run `/code-review` on commits that add or rewrite logic; skip pure delete/move/rename.

## Commits

- Group by feature, not file—each commit coherent and self-contained. Tests ride with the code they exercise.
- Before committing: compile/import-smoke the changed code and read `git diff --cached` against what you intended.

## Environment

Conda env `pik` (not uv). Run tests: `/home/ken/miniconda3/envs/pik/bin/python -m pytest`. Run pre-commit: `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`. Tools: Black (100 char), isort, pycln, pylint, mdformat. Never commit to `master` directly.

Exclude `plans/` and `static/` from pre-commit: these contain working docs and generated assets that don't need linting.

## Plans

Store in `plans/` with descriptive kebab-case names (e.g., `subtitle-delay-cleanup.md`). Include model at top: `Model: Claude Sonnet 4.6`.

## Pull Requests

Include test plan: minimal checklist for manual verification.

## Fork Maintenance

Avoid modifying upstream files. New features go in new files. If upstream must change, make smallest possible change (hook, import, or flag). Match upstream architecture. Don't restructure upstream for style alone.

## Rules

- Don't add unrequested features, error handling for impossible states, or speculative abstractions
- Never commit debug prints or commented code
- Temp files: use `get_temp_directory()` from `get_platform.py`, never hardcode paths or `tempfile.gettempdir()`
