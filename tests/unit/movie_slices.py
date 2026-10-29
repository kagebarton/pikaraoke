"""A synthetic movie slice and the words heard over it, for the movie-subtitles tests.

12 lines of five distinct pseudo-words, sung in a 200 s clip from 10 s on, 5 s apart; the
movie's own times are an hour later. No film text. ``lrc_slice`` is the same lines as an
LRCLIB match, which times a clip directly.
"""

import json
from datetime import timedelta

import srt

SLICE_LINES = 12
CLIP_S = 200.0
MOVIE_OFFSET_S = 3600.0


def slice_line(k: int) -> list[str]:
    return [f"w{chr(97 + (k * 5 + i) // 26)}{chr(97 + (k * 5 + i) % 26)}x" for i in range(5)]


def slice_clip_start(k: int) -> float:
    return 10.0 + 5.0 * k


def heard_words(lines=range(SLICE_LINES)) -> list[dict]:
    """The bundle's transcribe words for the given slice lines."""
    return [
        {
            "word": word,
            "start": slice_clip_start(k) + 0.6 * i,
            "end": slice_clip_start(k) + 0.6 * i + 0.5,
        }
        for k in lines
        for i, word in enumerate(slice_line(k))
    ]


def movie_slice(offset=lambda k: MOVIE_OFFSET_S, lines=range(SLICE_LINES)) -> str:
    """The lines as movie subtitles; ``offset(k)`` is how far line ``k`` sits after the clip."""
    return srt.compose(
        [
            srt.Subtitle(
                index=n,
                start=timedelta(seconds=slice_clip_start(k) + offset(k)),
                end=timedelta(seconds=slice_clip_start(k) + offset(k) + 3.5),
                content=" ".join(slice_line(k)),
            )
            for n, k in enumerate(lines, start=1)
        ]
    )


def lrc_slice(offset=lambda k: 0.0, lines=range(SLICE_LINES)) -> str:
    """The lines as an LRC (starts only); ``offset(k)`` is how far line ``k`` sits after the clip's."""
    rows = []
    for k in lines:
        start = slice_clip_start(k) + offset(k)
        rows.append(f"[{int(start // 60):02d}:{start % 60:05.2f}] {' '.join(slice_line(k))}")
    return "\n".join(rows) + "\n"


def clip_starts(srt_text: str) -> list[float]:
    return [round(cue.start.total_seconds(), 2) for cue in srt.parse(srt_text)]


def asr_json3(lines=range(SLICE_LINES)) -> str:
    """The same words as a YouTube auto-caption on disk."""
    events = [
        {
            "tStartMs": int(slice_clip_start(k) * 1000),
            "segs": [
                {"utf8": word} if i == 0 else {"utf8": f" {word}", "tOffsetMs": i * 600}
                for i, word in enumerate(slice_line(k))
            ],
        }
        for k in lines
    ]
    return json.dumps({"events": events})
