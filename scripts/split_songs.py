"""Cut a film's or TV show's songs into one clip and one clip-timed SRT each.

A show is described by a TOML file kept next to its source videos. The clips
("<prefix><title>.mp4/.srt") and a ``split_cache/`` folder are written beside it. The
edge rules, the config format and the workflow are in ``scripts/movie_split.md``.

``plan`` prints each song's edges without cutting, ``cut`` encodes the clips and writes
their SRTs, ``srt`` rewrites only the SRTs. Separating a stereo source's voice track needs
the GPU the running app holds, so stop the app first.
"""

import argparse
import logging
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from functools import cache, cached_property
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.srt_cues import is_all_caps  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402

LEAD, TAIL = 5.0, 5.0
INNER_LEAD = 0.5  # a joined part's start: just ahead of its first line
SEARCH = 60.0  # how far from the music's edge a camera cut or a pause is looked for
SCENE_THRESHOLD = 10  # ffmpeg scdet score; FOTC's hard cuts scored 15-19
# A camera cut further than this past the nearest clean moment costs too much dialogue (Ken,
# 11-08): the clip then opens or closes partway through a shot instead.
MAX_CUT_DETOUR = 15.0
VOICE_RATE, VOICE_FRAME = 8000, 0.05
# Quiet: every 50 ms frame within QUIET_AROUND of the cut is under the threshold, the higher of
# QUIET_SHARE up the window's range from floor (5th percentile) to speech (95th) and
# QUIET_DROP_DB under speech. The range rule is for a 5.1 centre channel, which never falls
# silent (room tone ~18 dB under speech); the drop rule is for a separated voice, whose floor is
# digital silence where nobody speaks but which still carries crowd murmur at a party.
QUIET_AROUND, QUIET_SHARE, QUIET_DROP_DB = 0.15, 0.3, 25.0
# Audio is encoded too: copied audio would start at the keyframe before the exact start,
# seconds ahead of the video. Mkv chapters would become a text track in the mp4.
ENCODE = [
    "-map_chapters", "-1", "-c:a", "aac", "-b:a", "192k", "-ac", "2",
    "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
    "-profile:v", "high", "-avoid_negative_ts", "make_zero", "-movflags", "+faststart",
]  # fmt: skip
HEIGHT = 720
MUSIC_TAG_RE = re.compile(r"music|guitar|strumming|piano|playing|beat|synth", re.I)
TAG_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
# Where recasing capitalizes: cue start, a sentence end, a new speaker's dash, a quote opened
# after a comma. Tags in between are skipped, so "( whispering ) what's" gets "What's" and the
# tag stays lowercase.
SENTENCE_START_RE = re.compile(
    r'(\A|[.!?]\s+|^\s*-\s*|,\s+")((?:[^\w(]|\([^)]*\))*?)([^\W\d_])', re.M
)
SRT_TIME_RE = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)")


@dataclass
class Part:
    first: int  # cue numbers in the source's SRT
    last: int
    music_from: float | None = None  # music start, when the SDH tag misses it or there is none
    music_to: float | None = None  # end of the music's fade, when it outlasts the last line
    start_by: float | None = None  # a setup scene Ken keeps: start at or before this


@dataclass
class Song:
    title: str
    parts: list[Part]
    episode: str = ""  # fills {episode} in the show's source pattern; "" for a film


@dataclass
class Cue:
    num: int
    start: float
    end: float
    text: str

    @property
    def spoken(self) -> bool:
        """Words anyone says or sings; a bare "( music playing )" tag is not."""
        return bool(re.search(r"[^\W\d_]", TAG_RE.sub("", self.text)))


@dataclass
class Edge:
    """One end of a clip part, and whether it landed on a camera cut."""

    time: float
    on_cut: bool


def label_re(labels: list[str]) -> re.Pattern | None:
    """Speaker labels at a line's start ("Both:", "Girls:"). The app strips only labels typed
    in capitals, so a mixed-case one would be shown and timed as a sung word."""
    if not labels:
        return None
    names = "|".join(re.escape(label) for label in labels)
    return re.compile(rf"^([-♪*\s]*)(?:{names}):\s*", re.I)


@dataclass
class Show:
    folder: Path
    prefix: str
    source: str  # glob under folder, with {episode}
    songs: list[Song]
    subtitles: str | None = None  # glob under folder, with {episode}; else the first stream
    names: list[str] = field(default_factory=list)  # proper names recasing can't tell apart
    labels: re.Pattern | None = None

    @classmethod
    def load(cls, path: Path) -> "Show":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls(
            folder=path.resolve().parent,
            prefix=data["prefix"],
            source=data["source"],
            subtitles=data.get("subtitles"),
            names=data.get("names", []),
            labels=label_re(data.get("labels", [])),
            songs=[
                Song(s["title"], [Part(**p) for p in s["parts"]], s.get("episode", ""))
                for s in data["songs"]
            ],
        )

    @property
    def cache(self) -> Path:
        return self.folder / "split_cache"

    def find(self, pattern: str, episode: str) -> Path:
        matches = sorted(self.folder.glob(pattern.format(episode=episode)))
        if len(matches) != 1:
            raise SystemExit(f"{pattern!r} for {episode!r} matches {len(matches)} files")
        return matches[0]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def run_bytes(cmd: list[str]) -> bytes:
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def parse_srt(text: str) -> list[Cue]:
    out = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "").lstrip("\ufeff").strip()):
        lines = block.split("\n")
        h1, m1, s1, f1, h2, m2, s2, f2 = map(int, SRT_TIME_RE.match(lines[1]).groups())
        start = h1 * 3600 + m1 * 60 + s1 + f1 / 1000
        end = h2 * 3600 + m2 * 60 + s2 + f2 / 1000
        out.append(Cue(int(lines[0]), start, end, "\n".join(lines[2:])))
    return out


def num(cues: list[Cue], n: int) -> Cue:
    return next(c for c in cues if c.num == n)


@cache
def separator(output_dir: Path):
    """The app's vocal model, loaded once."""
    from audio_separator.separator import Separator

    config = PipelineConfig()
    sep = Separator(
        model_file_dir=config.separator_model_dir, output_dir=str(output_dir),
        output_single_stem="Vocals", log_level=logging.WARNING,
    )  # fmt: skip
    sep.load_model(model_filename=config.separator_model_name)
    return sep


@dataclass
class Voice:
    """Per-50 ms voice level over a window, to tell whether anyone is talking at a moment."""

    t0: float
    db: np.ndarray

    @classmethod
    def from_file(cls, path: Path, t0: float) -> "Voice":
        pcm = run_bytes(
            ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(VOICE_RATE),
             "-f", "f32le", "-"]
        )  # fmt: skip
        a = np.frombuffer(pcm, np.float32)
        n = int(VOICE_FRAME * VOICE_RATE)
        frames = a[: len(a) // n * n].reshape(-1, n)
        return cls(t0, 20 * np.log10(np.sqrt(np.mean(frames**2, axis=1)) + 1e-9))

    def quiet(self, t: float) -> bool:
        lo = int((t - QUIET_AROUND - self.t0) / VOICE_FRAME)
        hi = int((t + QUIET_AROUND - self.t0) / VOICE_FRAME) + 1
        if lo < 0 or hi > len(self.db):
            return False
        floor, speech = np.percentile(self.db, 5), np.percentile(self.db, 95)
        threshold = max(floor + QUIET_SHARE * (speech - floor), speech - QUIET_DROP_DB)
        return bool(np.all(self.db[lo:hi] < threshold))

    def grid(self) -> list[float]:
        """Every frame's time: the off-cut candidates."""
        return [self.t0 + i * VOICE_FRAME for i in range(len(self.db))]


class Episode:
    """One source video (an episode, or the whole film) and what is measured from it."""

    def __init__(self, show: Show, code: str):
        self.show = show
        self.key = code or "film"  # cache file names
        self.src = show.find(show.source, code)
        self.srt = show.find(show.subtitles, code) if show.subtitles else None

    @cached_property
    def cues(self) -> list[Cue]:
        if self.srt:
            return parse_srt(self.srt.read_text(encoding="utf-8-sig"))
        cmd = ["ffmpeg", "-v", "error", "-i", str(self.src), "-map", "0:s:0", "-f", "srt", "-"]
        return parse_srt(run(cmd).stdout)

    @cached_property
    def all_caps(self) -> bool:
        """Captions typed in capitals, which the clip SRT recases."""
        return is_all_caps([TAG_RE.sub("", c.text) for c in self.cues])

    @cached_property
    def duration(self) -> float:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0"]
        return float(run([*cmd, str(self.src)]).stdout)

    @cached_property
    def has_centre(self) -> bool:
        """5.1 or wider: the centre channel carries the dialogue alone."""
        cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
               "stream=channels", "-of", "csv=p=0", str(self.src)]  # fmt: skip
        return int(run(cmd).stdout) >= 6

    def _cached(self, t0: float, t1: float, suffix: str) -> Path:
        self.show.cache.mkdir(exist_ok=True)
        return self.show.cache / f"{self.key}_{t0:.0f}_{t1:.0f}{suffix}"

    def shot_cuts(self, t0: float, t1: float) -> list[float]:
        """Times of the first frame of each new shot between ``t0`` and ``t1``."""
        t0, t1 = max(0.0, round(t0)), round(t1)
        path = self._cached(t0, t1, ".cuts")
        if not path.exists():
            log = run(
                ["ffmpeg", "-hide_banner", "-copyts", "-ss", str(t0), "-t", str(t1 - t0), "-i",
                 str(self.src), "-an", "-sn", "-vf",
                 f"scale=320:-2,scdet=threshold={SCENE_THRESHOLD}", "-f", "null", "-"]
            ).stderr  # fmt: skip
            path.write_text("\n".join(re.findall(r"lavfi\.scd\.time: ([\d.]+)", log)) + "\n")
        return [float(t) for t in path.read_text().split()]

    def voice(self, t0: float, t1: float) -> Voice:
        """The voice track of ``t0``..``t1`` (cached): the centre channel when there is one,
        else the app's vocal model separates it from the stereo mix."""
        t0, t1 = max(0.0, round(t0)), round(t1)
        path = self._cached(t0, t1, ".voice.wav")
        if not path.exists():
            seek = ["-ss", str(t0), "-t", str(t1 - t0), "-i", str(self.src), "-map", "0:a:0"]
            if self.has_centre:
                run(["ffmpeg", "-v", "error", "-y", *seek, "-af", "pan=mono|c0=FC", str(path)])
            else:
                mix = self._cached(t0, t1, ".wav")
                run(["ffmpeg", "-v", "error", "-y", *seek, "-ac", "2", "-ar", "44100", str(mix)])
                (out,) = separator(self.show.cache).separate(str(mix))
                (self.show.cache / Path(out).name).rename(path)
                mix.unlink()
        return Voice.from_file(path, t0)


def intro_tag(part: Part, cues: list[Cue]) -> Cue | None:
    """An SDH music tag between the previous spoken cue and the first sung line."""
    first = num(cues, part.first)
    tag = None
    for c in reversed([c for c in cues if c.start < first.start]):
        if c.spoken:
            break
        if MUSIC_TAG_RE.search(c.text):
            tag = c
    return tag


def music_start(part: Part, cues: list[Cue]) -> float:
    if part.music_from is not None:
        return part.music_from
    tag = intro_tag(part, cues)
    return tag.start - 1.0 if tag else num(cues, part.first).start


def clean(t: float, voice: Voice, cues: list[Cue]) -> bool:
    """Nobody is talking at ``t``: no caption is up, or the voice track is quiet (a pause
    inside a caption)."""
    no_caption = not any(c.spoken and c.start < t < c.end for c in cues)
    return no_caption or voice.quiet(t)


def pick(
    candidates: list[float], target: float, outward: int, voice: Voice, cues: list[Cue]
) -> float | None:
    """The clean candidate nearest ``target``, preferring the padding side of it: earlier for
    a start (``outward`` -1), later for an end (+1)."""
    ok = [t for t in candidates if clean(t, voice, cues)]
    padded = [t for t in ok if (t - target) * outward >= 0]
    return min(padded or ok, key=lambda t: abs(t - target)) if ok else None


def choose(
    cuts: list[float],
    window: list[float],
    target: float,
    outward: int,
    voice: Voice,
    cues: list[Cue],
    on_cut: bool,
) -> Edge:
    """On a clean camera cut if ``on_cut`` and one is within MAX_CUT_DETOUR of the nearest
    clean moment, on either side of it, else at that moment, partway through a shot."""
    moment = pick(window, target, outward, voice, cues)
    if moment is None:
        raise RuntimeError(f"no quiet moment near {target:.1f}")
    near = [t for t in cuts if abs(t - moment) <= MAX_CUT_DETOUR] if on_cut else []
    cut = pick(near, target, outward, voice, cues)
    return Edge(cut, True) if cut is not None else Edge(moment, False)


def lead_start(ep: Episode, part: Part, lead: float, on_cut: bool) -> Edge:
    first = num(ep.cues, part.first)
    latest = min(first.start, music_start(part, ep.cues))
    if part.start_by is not None:
        latest = min(latest, part.start_by)
    target = min(first.start - lead, latest)
    t0 = latest - SEARCH
    voice = ep.voice(t0, latest + 1)
    cuts = [t for t in ep.shot_cuts(t0, latest + 1) if t <= latest]
    window = [t for t in voice.grid() if t <= latest]
    return choose(cuts, window, target, -1, voice, ep.cues, on_cut)


def tail_end(ep: Episode, part: Part, tail: float, on_cut: bool) -> Edge:
    """``music_to`` may fall before the last line's caption ends: a joined part's music can
    stop under its last word."""
    last = num(ep.cues, part.last)
    earliest = part.music_to if part.music_to is not None else last.end
    nxt = next((c for c in ep.cues if c.spoken and c.start >= last.end - 0.01), None)
    cap = nxt.start if nxt else float("inf")
    target = max(earliest, min(last.end + tail, cap))
    # Capped by the next spoken line, the padding side is before that line, not after it.
    outward = -1 if cap <= last.end + tail else 1
    if ep.duration - earliest < 1:
        return Edge(ep.duration, True)
    t1 = min(earliest + SEARCH, ep.duration)
    voice = ep.voice(earliest - 1, t1)
    cuts = [t for t in ep.shot_cuts(earliest - 1, t1) if t >= earliest]
    window = [t for t in voice.grid() if t >= earliest]
    return choose(cuts, window, target, outward, voice, ep.cues, on_cut)


def edges(ep: Episode, song: Song) -> list[tuple[Edge, Edge]]:
    """Each part's start and end. A joined song's inner edges meet at the join, which is a cut
    anyway, so they skip the camera-cut rule and pad only a little."""
    out = []
    for i, part in enumerate(song.parts):
        first, last = i == 0, i == len(song.parts) - 1
        out.append(
            (
                lead_start(ep, part, LEAD if first else INNER_LEAD, first),
                tail_end(ep, part, TAIL if last else 0.0, last),
            )
        )
    return out


def recase(text: str, names: list[str]) -> str:
    """Sentence case for a caption typed in capitals: cue start, sentence starts, a new
    speaker's dash, "I", and ``names``."""
    text = re.sub(r"\bi\b", "I", text.lower())
    text = SENTENCE_START_RE.sub(lambda m: m.group(1) + m.group(2) + m.group(3).upper(), text)
    for name in names:
        text = re.sub(rf"\b{re.escape(name)}\b", name, text, flags=re.I)
    return text


def cue_text(text: str, labels: re.Pattern | None, names: list[str] | None) -> str:
    """A cue's text with speaker labels dropped (and a line left with no words by one),
    recased when ``names`` is given (the captions are typed in capitals)."""
    if labels:
        lines = []
        for line in text.split("\n"):
            bare = labels.sub(r"\1", line)
            if bare.strip() and (bare == line or re.search(r"\w", bare)):
                lines.append(bare)
        text = "\n".join(lines)
    return recase(text, names) if names is not None else text


def fmt(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def clip_srt(cues: list[Cue], spans: list[tuple[float, float]], text=lambda t: t) -> str:
    """The cues inside each span, shifted to the clip's timeline. A cut can fall inside a
    caption (in a pause between its sentences); a spoken cue counts as in the clip when its
    middle is, a tag when any of it is."""
    blocks, offset = [], 0.0
    for start, end in spans:
        for c in cues:
            inside = start <= (c.start + c.end) / 2 < end if c.spoken else c.end > start
            if inside and c.start < end:
                s, e = max(c.start, start) - start + offset, min(c.end, end) - start + offset
                blocks.append(f"{len(blocks) + 1}\n{fmt(s)} --> {fmt(e)}\n{text(c.text)}\n")
        offset += end - start
    return "\n".join(blocks)


def write_srt(show: Show, ep: Episode, song: Song, spans: list[tuple[float, float]]) -> None:
    names = show.names if ep.all_caps else None
    srt = clip_srt(ep.cues, spans, lambda t: cue_text(t, show.labels, names))
    (show.folder / f"{show.prefix}{song.title}.srt").write_text(srt, encoding="utf-8")


def cut(show: Show, ep: Episode, song: Song, spans: list[tuple[float, float]]) -> Path:
    """Encode the spans, joined, at exact frames (input seek is exact when re-encoding)."""
    out = show.folder / f"{show.prefix}{song.title}.mp4"
    src = str(ep.src)
    inputs = [arg for s, e in spans for arg in ("-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", src)]
    streams = "".join(f"[{i}:v][{i}:a]" for i in range(len(spans)))
    graph = f"{streams}concat=n={len(spans)}:v=1:a=1[joined][a];[joined]scale=-2:{HEIGHT}[v]"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]",
         "-map", "[a]", *ENCODE, str(out)],
        check=True,
    )  # fmt: skip
    write_srt(show, ep, song, spans)
    return out


def describe(cues: list[Cue], song: Song, parts: list[tuple[Edge, Edge]]) -> str:
    """One plan line: spans, lead and tail with the dialogue lines in them, and any outer
    edge that missed a camera cut."""
    first, last = num(cues, song.parts[0].first), num(cues, song.parts[-1].last)
    start, end = parts[0][0].time, parts[-1][1].time
    said_before = sum(c.spoken and start <= c.start < first.start for c in cues)
    said_after = sum(c.spoken and last.end <= c.start < end for c in cues)
    outer = (("start", parts[0][0]), ("end", parts[-1][1]))
    off_cut = [f"{side} {edge.time:.2f}" for side, edge in outer if not edge.on_cut]
    return (
        f"{song.episode or 'film'} {song.title}: "
        + " + ".join(f"{s.time:.2f}-{e.time:.2f}" for s, e in parts)
        + f" ({sum(e.time - s.time for s, e in parts):.0f}s)"
        f" lead {first.start - start:.1f}s ({said_before} lines)"
        f" tail {end - last.end:.1f}s ({said_after} lines)"
        + (f" NOT ON A CUT: {', '.join(off_cut)}" if off_cut else "")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("config", type=Path, help="the show's TOML file")
    parser.add_argument("action", choices=["plan", "cut", "srt"])
    parser.add_argument("song", nargs="?", default="", help="part of a song title")
    args = parser.parse_args()
    show = Show.load(args.config)
    episodes: dict[str, Episode] = {}
    for song in show.songs:
        if args.song.lower() not in song.title.lower():
            continue
        if song.episode not in episodes:
            episodes[song.episode] = Episode(show, song.episode)
        ep = episodes[song.episode]
        parts = edges(ep, song)
        spans = [(s.time, e.time) for s, e in parts]
        print(describe(ep.cues, song, parts), flush=True)
        if args.action == "cut":
            print(f"  -> {cut(show, ep, song, spans).name}", flush=True)
        elif args.action == "srt":
            write_srt(show, ep, song, spans)


if __name__ == "__main__":
    main()
