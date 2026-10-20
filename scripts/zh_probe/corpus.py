"""Pilot corpus for the Chinese character-timing probe (plans/chinese-character-timing.md)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

LIBRARY = Path("d:/shared/pikaraoke-songs")
PROBE_ROOT = LIBRARY / "zh_probe"


@dataclass(frozen=True)
class Song:
    num: int
    video_id: str
    lang: str  # "zh" Mandarin, "yue" Cantonese
    title: str
    # (track, artist) pairs tried against LRCLIB and NetEase; Traditional and
    # Simplified spellings both, since each service indexes one or the other.
    keys: tuple[tuple[str, str], ...]
    genius_queries: tuple[str, ...]
    # NetEase track ids looked up by hand: its search hides some official
    # catalogues (Jay Chou) but the lyric endpoint still serves them by id.
    netease_ids: tuple[int, ...] = ()


PILOT = (
    Song(
        1,
        "DYptgVvkVLQ",
        "zh",
        "周杰倫 晴天",
        (("晴天", "周杰倫"), ("晴天", "周杰伦"), ("Sunny Day", "Jay Chou")),
        ("周杰倫 晴天", "Jay Chou 晴天"),
        netease_ids=(186016,),
    ),
    Song(
        2,
        "RPWDeLqsN0g",
        "zh",
        "周杰倫 龍捲風",
        (("龍捲風", "周杰倫"), ("龙卷风", "周杰伦"), ("Tornado", "Jay Chou")),
        ("周杰倫 龍捲風", "Jay Chou 龍捲風"),
        netease_ids=(186160,),
    ),
    Song(
        9,
        "8NJVNkzhJM4",
        "yue",
        "陳奕迅 明年今日",
        (("明年今日", "陳奕迅"), ("明年今日", "陈奕迅"), ("Ming Nin Gam Yat", "Eason Chan")),
        ("陳奕迅 明年今日", "Eason Chan 明年今日"),
    ),
    Song(
        11,
        "qu_FSptjRic",
        "yue",
        "Beyond 海闊天空",
        (("海闊天空", "Beyond"), ("海阔天空", "Beyond"), ("海闊天空", "BEYOND")),
        ("Beyond 海闊天空", "Beyond 海阔天空"),
    ),
)


def find_in_library(video_id: str, subdir: str | None = None) -> list[Path]:
    """Files whose name carries the 11-char id, under the library or one of its subfolders."""
    base = LIBRARY / subdir if subdir else LIBRARY
    return sorted(p for p in base.glob(f"*{video_id}*") if p.is_file())
