# CLAUDE.md

Guidance for Claude Code when working on PiKaraoke.

## Project Overview

PiKaraoke is a karaoke system for Raspberry Pi, Windows, macOS, and Linux. Web interface for YouTube song search, queuing, and playback with pitch shifting and streaming.

## Core Principles

**Single-owner maintainability:** Code clarity over documentation. Simplicity over flexibility. One source of truth.

## Refactoring

**Refactor iteratively as you work.** When touching code:

- Extract classes when a module has multiple responsibilities (like `Browser` was extracted from utilities)
- Extract functions when logic is repeated or a function exceeds ~50 lines
- Rename unclear variables/functions immediately
- Delete dead code - never comment it out. When new code supersedes existing methods, remove the old methods and their tests in the same commit
- Update related code consistently (no half-migrations)

**When to refactor:**

- Code you're modifying is hard to understand
- You're adding a third similar pattern (rule of three)
- A function/class is doing too many things

**When NOT to refactor:**

- Unrelated code "while you're in the area"
- Working code that you're not modifying
- To add flexibility you don't need yet

## Code Style

- PEP 8, 4 spaces, meaningful names
- Type hints required: modern syntax (`str | None`) — Python 3.10+ is the minimum, no `from __future__ import annotations` needed
- Concise docstrings for public APIs - explain "why", not "how"
- No emoji or unicode emoji substitutes

## Filename Conventions

YouTube video filenames use exactly 11-character IDs:

- PiKaraoke format: `Title---dQw4w9WgXcQ.mp4` (triple dash)
- yt-dlp format: `Title [dQw4w9WgXcQ].mp4` (brackets)

Only support these two patterns.

## Error Handling

- Catch specific exceptions, never bare `except:`
- Log errors, never swallow silently
- Use context managers for resources

## Testing

- pytest with mocked external I/O and subprocess operations only
- Test business logic and integration points
- Skip trivial getters/setters
- Use real `EventSystem` and `PreferenceManager` instances (they're lightweight)

## Environment

This project runs in a **conda environment** named `pik` (not uv). Use `/home/ken/miniconda3/envs/pik/bin/python -m pytest` to run tests and `pre-commit` directly (not via `uv run`).

## Code Quality

```bash
# Run pre-commit checks
pre-commit run --config code_quality/.pre-commit-config.yaml --all-files
```

Tools: Black (100 char), isort, pycln, pylint, mdformat.

Never commit to `master` directly.

## Plans

Store all plan files in the `plans/` folder in the root of the project.

Name plan files with a short, descriptive kebab-case filename that reflects the task
(e.g., `subtitle-delay-cleanup.md`, `auth-refactor.md`), not the auto-generated random
name Claude Code assigns by default.

Include a line at the top of each plan specifying which Claude model created it:

```
Model: Claude Sonnet 4.6
```

or `Claude Opus 4.6` / `Claude Haiku 4.5` as appropriate.

## Pull Requests

PRs must include a test plan: a minimal checklist targeting only the changes made, enabling quick manual verification.

## Fork Maintenance

This is a fork of upstream PiKaraoke. Minimize merge conflicts when pulling upstream changes:

- **New functionality goes in new files** — avoid modifying upstream source files when the feature can live in a separate module that upstream files import or call into
- **When upstream files must be modified**, make the smallest possible change: a single hook call, import, or flag rather than inline logic
- **Match upstream architecture** — new code should look like it belongs; follow the same patterns, naming, and file organization already in place
- **Never restructure upstream files** for style or preference alone — only refactor what you're functionally changing

## What NOT to Do

- Add unrequested features
- Add error handling for impossible states
- Create abstractions for single uses
- Write speculative "future-proofing" code
- Commit debug prints or commented code

## Temporary Files

All non-persistent files (intermediate processing artifacts, logs, HLS segments,
download temp files) must use the centralized `temp_dir` preference from config.ini.
Never hardcode temp paths or use `tempfile.gettempdir()` directly. Use
`get_temp_directory()` from `get_platform.py` to resolve the configured path.
