# PiKaraoke

<img width="480" alt="PiKaraoke" src="../pikaraoke/static/images/placeholder.png" />

PiKaraoke is a cross-platform karaoke server that brings the "KTV" experience to your home. It turns your computer into a dedicated karaoke station with a full-screen player and an instant web interface. Guests join by scanning a QR code—no app downloads required—to browse your local library, manage the queue, and pull songs from YouTube.

This is a heavily modified fork of [vicwomg/pikaraoke](https://github.com/vicwomg/pikaraoke). Its headline addition is **automatic karaoke creation**: any downloaded song is run through a processing pipeline that separates out the lead vocals and generates time-synced lyric subtitles, so ordinary music videos become singable karaoke tracks without pre-made instrumentals. Processing kicks off automatically when a song is downloaded—no manual step—and you can watch each stage run on the [processing dashboard](#features).

## Features

- 🎤 **Automatic karaoke creation**: stem separation removes the lead vocal, and Whisper forced-alignment turns fetched lyrics into time-synced on-screen subtitles.
- 📝 **Lyrics from Genius or YouTube captions**: fetches and aligns lyrics from Genius.com or a video's YouTube captions.
- 📺 **Native full-screen player**: a libmpv window with QR code, now-playing / up-next / clock overlays—no browser tab required for playback.
- 📱 **Mobile remote**: search and queue songs from any smartphone—just scan and sing.
- 🌐 **YouTube & local media**: play your own files or download more from the web.
- 🎹 **Live pitch shifting**: adjust the key of any song on the fly (via Rubberband).
- 🎚️ **Live now-playing controls**: volume, subtitle delay, subtitle mode, and vocal volume (mix the lead vocal back in for a guide track) adjustable mid-song.
- 🔊 **Audio polish**: per-song loudness normalization, global A/V sync delay, and selectable audio output device.
- 🛠️ **Processing dashboard**: watch the pipeline run live, with a streaming terminal of each stage.
- 📂 **Backfill tool**: regenerate stems, subtitles, and loudness data for songs already in your library.
- 🔐 **Admin control**: manage the queue and settings behind a password-protected admin mode.

### Removed from the parent project

This fork drops several upstream features in favor of the libmpv player and processing pipeline:

- In-browser HLS playback and the browser-based splash screen (replaced by the native libmpv window)
- The random "performance scoring" / fireworks feature
- Background music and the screensaver
- CDG (.cdg) playback support
- The separate download-queue UI

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Lyrics setup](#lyrics-setup)
- [Backfilling an existing library](#backfilling-an-existing-library)
- [Developing PiKaraoke](#developing-pikaraoke)
- [Troubleshooting](#troubleshooting-and-guides)

## Requirements

- **OS**: developed and tested on **Ubuntu 24.04**. Other Linux distributions, macOS, and Windows may work but are untested.

- **GPU**: an NVIDIA GPU with CUDA is strongly recommended. Stem separation and Whisper alignment run on the GPU; on CPU they are extremely slow. The development host is a **6 GB RTX 2060**, so that is roughly the minimum proven configuration—more VRAM gives more headroom. On this host, processing runs at roughly **2× real time** (a 4-minute song is ready in about 2 minutes).

- **NVIDIA driver**: `torch` pulls in its own CUDA runtime on Linux, but you still need a recent enough NVIDIA driver on the host for it to work.

- **Python**: 3.10 or greater.

- **FFmpeg** built with `librubberband` (pitch shifting) and `libzmq` (the `azmq` filter, used to mix the lead vocal back in live on dual-stem karaoke tracks). Ubuntu 24.04's stock FFmpeg (6.1.1) includes both, so no extra setup is needed there. On a distro or build without the `azmq` filter, check `ffmpeg -filters | grep zmq` and install a build that has it.

- **libmpv 0.41 or newer.** The on-screen overlays use libmpv's `osd-overlay` command with ASS-formatted events, and Ubuntu 24.04's stock mpv (0.37) does **not** render them correctly. Install a newer libmpv from the [UbuntuHandbook mpv PPA](https://launchpad.net/~ubuntuhandbook1/+archive/ubuntu/mpv) (`ppa:ubuntuhandbook1/mpv`), which is the 0.41 build this project is developed against:

  ```sh
  sudo add-apt-repository ppa:ubuntuhandbook1/mpv
  sudo apt update && sudo apt install libmpv2
  ```

- **A JS runtime on your PATH** (used by yt-dlp). [Deno](https://deno.com/) is easiest for non-developers; [Node.js](https://nodejs.org/en/download/) also works.

On first run, the stem-separation and Whisper models are downloaded automatically (a few GB), so the first processed song takes longer.

## Installation

Clone the repository:

```sh
git clone https://github.com/kagebarton/pikaraoke.git
cd pikaraoke
```

### Option A: uv (recommended)

The repo ships a `uv.lock`, so [uv](https://github.com/astral-sh/uv) gives a reproducible install:

```sh
uv run pikaraoke
```

`uv run` resolves the locked dependencies and launches PiKaraoke in one step.

### Option B: pip / conda

Install into a virtual environment of your choice:

```sh
# venv
python -m venv .venv
source .venv/bin/activate

# or conda
# conda create -n pik python=3.10
# conda activate pik

pip install -e .
pikaraoke
```

## Usage

Launch the player from the command line:

```sh
pikaraoke
```

This opens the full-screen libmpv player window. Scan the QR code shown on screen to connect mobile remotes.

See `pikaraoke --help` for all options (port, download path, volume, overlay toggles, audio device, and more).

## Lyrics setup

The lyric pipeline can source lyrics from a video's YouTube captions automatically. To also use **Genius.com** as a lyrics source, set a Genius API token in the web interface preferences (the `genius_token` setting). Without a token, PiKaraoke falls back to YouTube captions.

## Backfilling an existing library

To generate stems, subtitles, and loudness data for songs already in your library, use the backfill script:

```sh
python scripts/backfill_artifacts.py --help
```

See [scripts/README.md](../scripts/README.md) for details.

## Developing PiKaraoke

Dependencies are managed with `uv`.

```sh
git clone https://github.com/kagebarton/pikaraoke.git
cd pikaraoke
uv run pikaraoke   # install deps and run from local code
```

Run the tests and linters before committing:

```sh
python -m pytest
pre-commit run --config code_quality/.pre-commit-config.yaml --all-files
```

[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-green.svg)](https://conventionalcommits.org)

## Troubleshooting and guides

For background on the original project, see the [upstream wiki](https://github.com/vicwomg/pikaraoke/wiki/), which still covers general setup, FAQs, and creative deployments. Note that upstream guides predate this fork's libmpv player and processing pipeline, so playback- and lyrics-specific sections may not apply.
</content>
</invoke>
