"""The alignment arms of the Chinese character-timing probe (plans/chinese-character-timing.md).

Each arm loads its model once (``load``), then ``align`` turns one song's vocal stem, confirmed
sheet and language label into one Timing per sheet unit, plus a dict of raw counts for the run
record. Optional packages (transformers, jieba, pypinyin, ToJyutping, opencc) come from
``uv run --with`` and are imported where used.
"""

from __future__ import annotations

import functools
import gc
import logging
import re

import numpy as np
import torch
import torchaudio
import torchaudio.functional as taf
from corpus import HAN_RE, WHISPER_PATH
from sheet import Sheet
from stable_whisper.whisper_compatibility import get_tokenizer
from track import Timing

SAMPLE_RATE = 16000
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
WINDOW_S = 30.0  # audio per model call for the CTC arms
CONTEXT_S = 2.0  # neighbouring audio shown to each call and then dropped
FALLBACK_S = 0.25  # width given to an untimed character at the edge of a song
HAN_RUN_RE = re.compile(f"{HAN_RE.pattern}+")


@functools.cache
def opencc_converter(config: str):
    from opencc import OpenCC

    return OpenCC(config)


def place_between(prev: Timing | None, nxt: Timing | None, n: int) -> list[Timing]:
    """Spread ``n`` untimed characters between the onsets of their timed neighbours."""
    if prev is None and nxt is None:
        raise ValueError("no character got a timing")
    if nxt is None:
        points, first = [prev.start + FALLBACK_S * m for m in range(n + 2)], 1
    elif prev is None:
        lo = max(0.0, nxt.start - FALLBACK_S * n)
        points, first = [lo + (nxt.start - lo) * m / n for m in range(n + 1)], 0
    else:
        points = [prev.start + (nxt.start - prev.start) * m / (n + 1) for m in range(n + 2)]
        first = 1
    return [Timing(points[first + k], points[first + k + 1], "interpolated") for k in range(n)]


def fill_untimed(spans: list[tuple[float, float, bool] | None]) -> list[Timing]:
    """``spans`` holds (start, end, shared) per unit, or None where the arm gave no timing."""
    out = [None if s is None else Timing(s[0], s[1], "shared" if s[2] else None) for s in spans]
    i = 0
    while i < len(out):
        if out[i] is not None:
            i += 1
            continue
        j = i
        while j < len(out) and out[j] is None:
            j += 1
        out[i:j] = place_between(out[i - 1] if i else None, out[j] if j < len(out) else None, j - i)
        i = j
    return out


class WhisperArm:
    """Arm W: stable-ts forced alignment of the sheet, in the song's own language."""

    arm = "W"
    model_id = WHISPER_PATH.name
    languages = ("zh", "yue")

    def load(self) -> None:
        import stable_whisper

        self.model = stable_whisper.load_model(str(WHISPER_PATH), device=DEVICE)

    def align(self, audio: np.ndarray, sheet: Sheet, lang: str) -> tuple[list[Timing], dict]:
        tokenizer = get_tokenizer(self.model, language=lang, task="transcribe")
        if lang == "yue":
            # stable-ts 2.19.1 splits words by character only for zh, ja, th, lo, my, so Cantonese
            # would come out one word per space-separated phrase; whisper's own tokenizer already
            # splits yue by character, and this label is all stable-ts reads to choose
            tokenizer.language_code = "zh"
        result = self.model.align(
            audio,
            "\n".join(sheet.lines),
            language=lang,
            tokenizer=tokenizer,
            original_split=True,
            verbose=None,
        )
        words = [(w.word, w.start, w.end) for w in result.all_words()]
        return whisper_timings(words, sheet), {"n_words": len(words)}

    def unload(self) -> None:
        del self.model


def whisper_timings(words: list[tuple[str, float, float]], sheet: Sheet) -> list[Timing]:
    """Map whisper's words (a token each, often several characters) back onto sheet units.

    A word that covers several units gives each an even share and marks it shared; a unit
    spread over several words (a Latin word split into tokens) takes their union.
    """
    stream: list[tuple[str, int | None]] = []  # every non-space sheet character, with its unit
    for i, u in enumerate(sheet.units):
        stream += [(c, None) for c in u.pre if not c.isspace()]
        stream += [(c, i) for c in u.text]
        if i + 1 == len(sheet.units) or sheet.units[i + 1].line != u.line:
            stream += [(c, None) for c in sheet.tails[u.line] if not c.isspace()]

    spans: list[tuple[float, float, bool] | None] = [None] * len(sheet.units)
    pos = 0
    for text, start, end in words:
        chars = "".join(text.split())
        chunk = stream[pos : pos + len(chars)]
        if "".join(c for c, _ in chunk) != chars:
            raise ValueError(f"whisper word {chars!r} does not continue the sheet at {pos}")
        pos += len(chars)
        owners = list(dict.fromkeys(i for _, i in chunk if i is not None))
        for k, i in enumerate(owners):
            s = start + (end - start) * k / len(owners)
            e = start + (end - start) * (k + 1) / len(owners)
            shared = len(owners) > 1
            if spans[i] is not None:
                old_s, old_e, old_shared = spans[i]
                s, e, shared = min(old_s, s), max(old_e, e), old_shared or shared
            spans[i] = (s, e, shared)
    if pos != len(stream):
        raise ValueError(f"whisper words stop at {pos} of {len(stream)} sheet characters")
    return fill_untimed(spans)


def chunked_emission(emit, audio: np.ndarray, frame_s: float) -> torch.Tensor:
    """Log-probabilities (frames, classes) for a whole song from fixed windows.

    Each window of WINDOW_S is shown CONTEXT_S of its neighbours, whose frames are dropped, so
    memory stays flat for a 5-minute song and window edges do not show in the result.
    """
    window, context = round(WINDOW_S * SAMPLE_RATE), round(CONTEXT_S * SAMPLE_RATE)
    per_window = round(WINDOW_S / frame_s)
    pieces = []
    for a in range(0, len(audio), window):
        lo, hi = max(0, a - context), min(len(audio), a + window + context)
        skip = round((a - lo) / SAMPLE_RATE / frame_s)
        pieces.append(emit(audio[lo:hi])[skip : skip + per_window])
    assert all(len(p) == per_window for p in pieces[:-1]), [len(p) for p in pieces]
    return torch.cat(pieces)


def ctc_unit_spans(
    emission: torch.Tensor, unit_tokens: list[list[int]], blank: int
) -> list[tuple[int, int] | None]:
    """CTC forced alignment; the (first frame, end frame) of each unit's tokens, None if it has none."""
    flat = [t for tokens in unit_tokens for t in tokens]
    targets = torch.tensor([flat], dtype=torch.int32)
    aligned, scores = taf.forced_align(emission[None], targets, blank=blank)
    token_spans = taf.merge_tokens(aligned[0], scores[0].exp(), blank=blank)
    assert len(token_spans) == len(flat)
    out, k = [], 0
    for tokens in unit_tokens:
        group = token_spans[k : k + len(tokens)]
        k += len(tokens)
        out.append((group[0].start, group[-1].end) if group else None)
    return out


class CtcArm:
    """Shared by the arms that align a sheet against a CTC model's per-frame output."""

    frame_s = 0.02
    blank = 0

    def emit(self, chunk: np.ndarray) -> torch.Tensor:
        raise NotImplementedError

    def unit_tokens(self, sheet: Sheet, lang: str) -> list[list[int]]:
        raise NotImplementedError

    def align(self, audio: np.ndarray, sheet: Sheet, lang: str) -> tuple[list[Timing], dict]:
        emission = chunked_emission(self.emit, audio, self.frame_s)
        spans = ctc_unit_spans(emission, self.unit_tokens(sheet, lang), self.blank)
        timed = [
            None if s is None else (s[0] * self.frame_s, s[1] * self.frame_s, False) for s in spans
        ]
        return fill_untimed(timed), {"frames": len(emission), "frame_s": self.frame_s}

    def unload(self) -> None:
        del self.model


class MmsArm(CtcArm):
    """Arm R: torchaudio MMS_FA on a romanization (pinyin or jyutping, tones stripped)."""

    arm = "R"
    model_id = "torchaudio MMS_FA"
    languages = ("zh", "yue")

    def load(self) -> None:
        bundle = torchaudio.pipelines.MMS_FA
        self.model = bundle.get_model(with_star=False).to(DEVICE).eval()
        self.dictionary = bundle.get_dict(star=None)  # model normalizes and log-softmaxes itself

    def emit(self, chunk: np.ndarray) -> torch.Tensor:
        with torch.inference_mode():
            emission, _ = self.model(torch.from_numpy(chunk)[None].to(DEVICE))
        return emission[0].float().cpu()

    def unit_tokens(self, sheet: Sheet, lang: str) -> list[list[int]]:
        letters = self.dictionary
        return [
            [letters[c] for c in syllable if c in letters] for syllable in romanize(sheet, lang)
        ]


def romanize(sheet: Sheet, lang: str) -> list[str]:
    """One lowercase letter string per unit: a Han character's syllable, or the Latin word itself."""
    out = []
    for n, line in enumerate(sheet.lines):
        syllables = iter(han_syllables(line, lang))
        for u in sheet.line_units(n):
            out.append(next(syllables) if u.kind == "han" else u.text.lower())
    return out


def han_syllables(line: str, lang: str) -> list[str]:
    """Toneless syllable per Han character of the line; "" where the romanizer has no reading."""
    if lang == "yue":
        import ToJyutping

        return [
            re.sub(r"\d", "", jyutping or "")
            for char, jyutping in ToJyutping.get_jyutping_list(line)
            if HAN_RE.fullmatch(char)
        ]
    import jieba
    from pypinyin import Style, lazy_pinyin

    jieba.setLogLevel(logging.WARNING)
    out = []
    for run in HAN_RUN_RE.findall(line):
        # segmenting Simplified text gives jieba (and pypinyin's phrase table) the best chance
        # at the multi-reading characters; t2s keeps the length, but fall back if it ever differs
        simplified = opencc_converter("t2s").convert(run)
        if len(simplified) != len(run):
            simplified = run
        for word in jieba.cut(simplified):
            readings = lazy_pinyin(word, style=Style.NORMAL)
            out += [r if r.isascii() and r.isalpha() else "" for r in readings]
    return out


class HfArm(CtcArm):
    """Arm H: a Hugging Face CTC model that outputs characters, aligned against the sheet's own."""

    def __init__(self, arm: str, model_id: str, languages: tuple[str, ...], frame_s: float):
        self.arm, self.model_id, self.languages, self.frame_s = arm, model_id, languages, frame_s

    def load(self) -> None:
        from transformers import AutoModelForCTC, AutoProcessor

        self.processor = AutoProcessor.from_pretrained(self.model_id)
        self.model = AutoModelForCTC.from_pretrained(self.model_id).to(DEVICE).eval()
        self.vocab = self.processor.tokenizer.get_vocab()
        self.blank = self.model.config.pad_token_id

    def emit(self, chunk: np.ndarray) -> torch.Tensor:
        features = self.processor(chunk, sampling_rate=SAMPLE_RATE, return_tensors="pt")
        key = "input_values" if "input_values" in features else "input_features"
        with torch.inference_mode():
            logits = self.model(features[key].to(DEVICE)).logits[0]
        return torch.log_softmax(logits.float(), dim=-1).cpu()

    def char_id(self, char: str) -> int | None:
        """The character's own token, else its case or Traditional/Simplified counterpart."""
        t2s, s2t = opencc_converter("t2s"), opencc_converter("s2t")
        variants = (char, char.upper(), char.lower(), t2s.convert(char), s2t.convert(char))
        return next((self.vocab[v] for v in variants if v in self.vocab), None)

    def unit_tokens(self, sheet: Sheet, lang: str) -> list[list[int]]:
        out = []
        for u in sheet.units:
            ids = [self.char_id(c) for c in u.text]
            out.append([] if None in ids else ids)
        return out

    def unload(self) -> None:
        del self.model, self.processor


def make_arm(name: str):
    if name == "W":
        return WhisperArm()
    if name == "R":
        return MmsArm()
    models = {
        "H": ("jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn", ("zh",), 0.02),
        "Hsk": ("scottykwok/wav2vec2-large-xlsr-cantonese", ("yue",), 0.02),
        "Hal": ("alvanlii/wav2vec2-BERT-cantonese", ("yue",), 0.04),
    }
    return HfArm(name, *models[name])


def free_memory() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
