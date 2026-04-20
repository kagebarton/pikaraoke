# CLAUDE.md

PiKaraoke: karaoke system for Raspberry Pi/Windows/macOS/Linux with YouTube search, queuing, pitch shifting.

**Core:** Code clarity over docs. Simplicity over flexibility. Single source of truth.

## Project Structure

The mpv prototype is in the `mpv/` subfolder under the project root.

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
