# PiKaraoke Project Context

## Project Overview

PiKaraoke is a cross-platform karaoke server/application that transforms computers (Raspberry Pi, Windows, macOS, Linux) into dedicated karaoke stations. It provides:

- **Web-based remote control**: Mobile-friendly interface for searching, queuing, and managing songs via QR code
- **Full-screen player**: Splash screen for TV/monitor display with professional KTV experience
- **YouTube integration**: Search and download karaoke videos via yt-dlp
- **Local media library**: Browse and play existing karaoke files
- **Live pitch shifting**: Adjust song key using FFmpeg with lib-rubberband
- **Admin controls**: Password-protected queue and settings management
- **Multi-language support**: 15+ languages via Flask-Babel

## Technology Stack

- **Language**: Python 3.10+
- **Web Framework**: Flask 3.1.x with flask-smorest (API), flask-socketio (real-time)
- **Async**: gevent for async operations
- **Media Processing**: ffmpeg-python, yt-dlp
- **Package Manager**: uv (primary), pip (alternative)
- **Build System**: hatchling

## Project Structure

```
pikaraoke/
├── pikaraoke/              # Main source package
│   ├── app.py              # Flask application entry point
│   ├── karaoke.py          # Core karaoke engine (614 lines)
│   ├── constants.py        # Language definitions
│   ├── version.py          # Version information
│   ├── lib/                # Core library modules (24 files)
│   │   ├── args.py         # CLI argument parsing
│   │   ├── browser.py      # Browser automation
│   │   ├── download_manager.py
│   │   ├── events.py       # Event system
│   │   ├── ffmpeg.py       # FFmpeg integration
│   │   ├── file_resolver.py
│   │   ├── get_platform.py # Platform detection utilities
│   │   ├── karaoke_database.py
│   │   ├── library_scanner.py
│   │   ├── metadata_parser.py
│   │   ├── playback_controller.py
│   │   ├── preference_manager.py
│   │   ├── processing_manager.py
│   │   ├── queue_manager.py
│   │   ├── song_manager.py
│   │   ├── stream_manager.py
│   │   └── youtube_dl.py   # YouTube search/download
│   ├── routes/             # Flask blueprints (API + UI)
│   ├── templates/          # Jinja2 templates
│   ├── static/             # CSS, JS, images
│   └── translations/       # i18n message catalogs
├── tests/
│   └── unit/               # pytest unit tests (30 test files)
├── build_scripts/          # Install scripts (shell, PowerShell)
├── code_quality/           # Pre-commit configuration
├── docs/                   # Documentation including README
└── audio-separator/        # Vocal separation models
```

## Building and Running

### Development Setup

**Important:** This project uses a **conda environment** named `avtest`, not uv for running tests.

```bash
# Install uv if not already installed
# Clone repo, then from project directory:

# Install dependencies and run
uv run pikaraoke

# Run tests (conda env 'avtest', NOT uv)
/home/ken/miniconda3/envs/avtest/bin/python -m pytest

# Run specific test file
/home/ken/miniconda3/envs/avtest/bin/python -m pytest tests/unit/test_file_resolver.py -v

# Run tests with verbose output and stop on first failure
/home/ken/miniconda3/envs/avtest/bin/python -m pytest -x -v

# Run pre-commit checks
pre-commit run --config code_quality/.pre-commit-config.yaml --all-files
```

### Production Installation

```bash
# Quick install (Linux/macOS)
curl -fsSL https://raw.githubusercontent.com/vicwomg/pikaraoke/master/build_scripts/install/install.sh | bash

# Quick install (Windows PowerShell)
irm https://raw.githubusercontent.com/vicwomg/pikaraoke/master/build_scripts/install/install.ps1 | iex

# Or via uv
uv tool install pikaraoke
```

### Docker

```bash
docker run -p 5555:5555 \
  -v ~/pikaraoke-songs:/app/pikaraoke-songs \
  -v ~/.pikaraoke:/home/pikaraoke/.pikaraoke \
  vicwomg/pikaraoke:latest \
  -u http://<YOUR_LAN_IP>:5555
```

## Development Conventions

### Code Style

- **PEP 8** compliant
- **4 spaces** for indentation
- **Type hints** required (Python 3.10+ syntax: `str | None`)
- **Line length**: 100 characters (Black)
- **No emoji** in code
- **Docstrings**: Concise, explain "why" not "how"

### Tooling

- **Format**: Black (100 char), isort
- **Lint**: pylint
- **Unused imports**: pycln
- **Markdown**: mdformat
- **Pre-commit**: Required before commits

### Testing Practices

- **Framework**: pytest with pytest-cov
- **Mock**: External I/O and subprocess operations
- **Real instances**: Use actual `EventSystem` and `PreferenceManager` (lightweight)
- **Coverage**: Excludes constants.py, app.py, current_app.py, args.py
- **Skip**: Trivial getters/setters

### Error Handling

- Catch specific exceptions, never bare `except:`
- Log errors, never swallow silently
- Use context managers for resources

### Filename Conventions

YouTube video filenames use 11-character video IDs:
- PiKaraoke format: `Title---dQw4w9WgXcQ.mp4` (triple dash separator)
- yt-dlp format: `Title [dQw4w9WgXcQ].mp4` (brackets)

Only support these two patterns.

### Commit Conventions

- **Standard**: Conventional Commits 1.0.0
- **Branch**: Never commit directly to master
- **Plan files**: Use kebab-case descriptive names (e.g., `subtitle-delay-cleanup.md`)

## Key Architecture Components

### Core Classes

- **`Karaoke`** (`karaoke.py`): Main engine coordinating songs, queue, playback
- **`SongManager`**: Local library management
- **`QueueManager`**: Song queue operations
- **`PlaybackController`**: Playback state and stream coordination
- **`PreferenceManager`**: User preferences (config.ini)
- **`EventSystem`**: Internal event pub/sub
- **`DownloadManager`**: YouTube download coordination

### Routes (Flask Blueprints)

**API Routes** (exposed in Swagger when enabled):
- `queue_bp`, `search_bp`, `files_bp`, `preferences_bp`
- `admin_bp`, `controller_bp`, `background_music_bp`
- `images_bp`, `nowplaying_bp`, `stream_bp`, `metadata_bp`

**Internal Routes** (UI only):
- `home_bp`, `info_bp`, `splash_bp`, `batch_song_renamer_bp`

### Preferences System

Configuration stored in `config.ini` with centralized `temp_dir` for all temporary files. Never hardcode temp paths or use `tempfile.gettempdir()` directly—use `get_temp_directory()` from `get_platform.py`.

## Environment Notes

**This project runs in a conda environment named `avtest` (not uv).**

```bash
# Run pytest
/home/ken/miniconda3/envs/avtest/bin/python -m pytest

# Run pre-commit directly (not via `uv run`)
pre-commit run --config code_quality/.pre-commit-config.yaml --all-files
```

## Upstream Fork Maintenance

This is a fork of upstream PiKaraoke. To minimize merge conflicts:

- **New functionality in new files** when possible
- **Minimal modifications** to upstream files—single hook calls or flags
- **Match upstream architecture**—follow existing patterns
- **Never restructure** upstream files for style alone

## PR Requirements

Pull requests must include a **test plan**: minimal checklist targeting only the changes made for quick manual verification.

## What NOT to Do

- Add unrequested features
- Add error handling for impossible states
- Create abstractions for single uses
- Write speculative "future-proofing" code
- Commit debug prints or commented code
- Modify upstream files when new module approach works
