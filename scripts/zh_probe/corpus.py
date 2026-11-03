"""Pilot corpus for the Chinese character-timing probe (plans/chinese-character-timing.md)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

# Both default to the Windows GPU box; the environment overrides let the CPU-only dev VM smoke-test
# the probe against a scratch library.
LIBRARY = Path(os.environ.get("ZH_PROBE_LIBRARY", "d:/shared/pikaraoke-songs"))
WHISPER_PATH = Path(
    os.environ.get("ZH_PROBE_WHISPER", "c:/temp/Github/pikaraoke/models/large-v3-turbo.pt")
)
PROBE_ROOT = LIBRARY / "zh_probe"
RAW_DIR = PROBE_ROOT / "phase0" / "sheets_raw"
CONFIRMED_DIR = PROBE_ROOT / "sheets"

HAN_RE = re.compile("[㐀-䶿一-鿿豈-﫿\U00020000-\U0002fa1f]")
LRC_STAMP_RE = re.compile(r"\[\d+:\d+(?:[.:]\d+)?\]")


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

# The other twelve corpus songs (plan "Corpus" table). Only Phase 0b's fetch uses them so far.
REST = (
    Song(
        3,
        "OR-0wptI_u0",
        "zh",
        "周杰倫 雙截棍",
        (("雙截棍", "周杰倫"), ("双截棍", "周杰伦"), ("Nunchucks", "Jay Chou")),
        ("周杰倫 雙截棍", "Jay Chou 雙截棍"),
        netease_ids=(186137,),
    ),
    Song(
        4,
        "ocDo3ySyHSI",
        "zh",
        "周杰倫 & 費玉清 千里之外",
        (("千里之外", "周杰倫"), ("千里之外", "周杰伦"), ("Thousand Miles", "Jay Chou")),
        ("周杰倫 千里之外", "Jay Chou 千里之外"),
        netease_ids=(185880,),
    ),
    Song(
        5,
        "IgvDMB5fR-8",
        "zh",
        "鄧麗君 月亮代表我的心",
        (
            ("月亮代表我的心", "鄧麗君"),
            ("月亮代表我的心", "邓丽君"),
            ("The Moon Represents My Heart", "Teresa Teng"),
        ),
        ("鄧麗君 月亮代表我的心", "Teresa Teng 月亮代表我的心"),
    ),
    Song(
        6,
        "m4nu_F_9dWU",
        "zh",
        "孫燕姿 遇見",
        (("遇見", "孫燕姿"), ("遇见", "孙燕姿"), ("Yu Jian", "Stefanie Sun")),
        ("孫燕姿 遇見", "Stefanie Sun 遇見"),
    ),
    Song(
        7,
        "JM9rx_hN1Ko",
        "zh",
        "陳奕迅 十年",
        (("十年", "陳奕迅"), ("十年", "陈奕迅"), ("Ten Years", "Eason Chan")),
        ("陳奕迅 十年", "Eason Chan 十年"),
    ),
    Song(
        8,
        "RIq7Tz9nYD8",
        "zh",
        "陳奕迅 愛情轉移",
        (("愛情轉移", "陳奕迅"), ("爱情转移", "陈奕迅"), ("Love Transfer", "Eason Chan")),
        ("陳奕迅 愛情轉移", "Eason Chan 愛情轉移"),
    ),
    Song(
        10,
        "7qeShSmmsNg",
        "yue",
        "陳奕迅 富士山下",
        (("富士山下", "陳奕迅"), ("富士山下", "陈奕迅"), ("Under Mount Fuji", "Eason Chan")),
        ("陳奕迅 富士山下", "Eason Chan 富士山下"),
    ),
    Song(
        12,
        "UmTB6E5mU5w",
        "yue",
        "張國榮 風繼續吹",
        (("風繼續吹", "張國榮"), ("风继续吹", "张国荣"), ("Wind Blows On", "Leslie Cheung")),
        ("張國榮 風繼續吹", "Leslie Cheung 風繼續吹"),
    ),
    Song(
        13,
        "CvKvXNiXQZc",
        "yue",
        "楊千嬅 少女的祈禱",
        (("少女的祈禱", "楊千嬅"), ("少女的祈祷", "杨千嬅"), ("Prayer", "Miriam Yeung")),
        ("楊千嬅 少女的祈禱", "Miriam Yeung 少女的祈禱"),
    ),
    Song(
        14,
        "tDw_ULjZWA8",
        "yue",
        "王菲 容易受傷的女人 (粵語版)",
        (("容易受傷的女人", "王菲"), ("容易受伤的女人", "王菲"), ("Vulnerable Woman", "Faye Wong")),
        ("王菲 容易受傷的女人", "Faye Wong 容易受傷的女人"),
    ),
    Song(
        15,
        "U_EgeFUTbW4",
        "yue",
        "林子祥 男兒當自強",
        (("男兒當自強", "林子祥"), ("男儿当自强", "林子祥"), ("男兒當自強", "George Lam")),
        ("林子祥 男兒當自強", "George Lam 男兒當自強"),
    ),
    Song(
        16,
        "cPKfUWDmNbo",
        "yue",
        "Twins 下一站天后",
        (("下一站天后", "Twins"), ("下一站天后", "TWINS"), ("Next Stop", "Twins")),
        ("Twins 下一站天后", "下一站天后"),
    ),
)


def find_in_library(video_id: str, subdir: str | None = None) -> list[Path]:
    """Files whose name carries the 11-char id, under the library or one of its subfolders."""
    base = LIBRARY / subdir if subdir else LIBRARY
    return sorted(p for p in base.glob(f"*{video_id}*") if p.is_file())


def han_chars(text: str) -> list[str]:
    return HAN_RE.findall(text)


def candidate_texts(song: Song) -> dict[str, str]:
    """Distinct texts for a song, keyed by the first file that carries each.

    Ken's confirmed sheet, once saved, comes first under the key ``CONFIRMED``.
    """
    texts: dict[str, tuple[str, str]] = {}
    folder = RAW_DIR / song.video_id
    for path in sorted(folder.glob("*.txt")) + sorted(folder.glob("netease_*.lrc")):
        if path.name == "sources.txt":
            continue
        text = LRC_STAMP_RE.sub("", path.read_text(encoding="utf-8"))
        texts.setdefault(re.sub(r"\s+", "", text), (path.name, text))
    confirmed = CONFIRMED_DIR / f"{song.video_id}.txt"
    out = {name: text for name, text in texts.values()}
    if confirmed.exists():
        out = {"CONFIRMED": confirmed.read_text(encoding="utf-8"), **out}
    return out
