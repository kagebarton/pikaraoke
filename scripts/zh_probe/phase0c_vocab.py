"""Phase 0c, CPU half: vocabulary coverage (Arm H) and romanizer failures (Arm R).

Counts are per text, where a text is each distinct candidate sheet saved by
fetch_sheets.py, plus the confirmed sheet <PROBE_ROOT>/sheets/<id>.txt once Ken
has saved it. Raw numbers only: nothing here ranks a model or a source.

Run: uv run --with pypinyin --with jieba --with ToJyutping \
         --with opencc-python-reimplemented --with huggingface_hub \
         python scripts/zh_probe/phase0c_vocab.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
from opencc import OpenCC
from pypinyin import Style, lazy_pinyin
from ToJyutping import get_jyutping_list

sys.path.insert(0, str(Path(__file__).parent))

from corpus import PILOT, PROBE_ROOT, Song  # noqa: E402

OUT_DIR = PROBE_ROOT / "phase0"
RAW_DIR = OUT_DIR / "sheets_raw"
CONFIRMED_DIR = PROBE_ROOT / "sheets"

# Arm H candidates by language label.
H_MODELS = {
    "zh": ["jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn"],
    "yue": [
        "scottykwok/wav2vec2-large-xlsr-cantonese",
        "ctl/wav2vec2-large-xlsr-cantonese",
        "w11wo/wav2vec2-xls-r-300m-zh-HK-v2",
        "alvanlii/wav2vec2-BERT-cantonese",
    ],
}

HAN_RE = re.compile("[㐀-䶿一-鿿豈-﫿\U00020000-\U0002fa1f]")
PINYIN_FAIL = "<no-reading>"
LRC_STAMP_RE = re.compile(r"\[\d+:\d+(?:[.:]\d+)?\]")
T2S, S2T = OpenCC("t2s"), OpenCC("s2t")


def candidate_texts(song: Song) -> dict[str, str]:
    """Distinct texts for a song, keyed by the first file that carries each."""
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


def han_chars(text: str) -> list[str]:
    return HAN_RE.findall(text)


def load_vocab(repo: str) -> tuple[set[str], int]:
    path = hf_hub_download(repo, "vocab.json")
    vocab = json.loads(Path(path).read_text(encoding="utf-8"))
    return {tok for tok in vocab if len(tok) == 1}, len(vocab)


def model_files(repo: str) -> dict:
    info = HfApi().model_info(repo, files_metadata=True)
    weights = [s for s in info.siblings if s.rfilename.endswith((".safetensors", ".bin"))]
    card = info.card_data.to_dict() if info.card_data else {}
    return {
        "weights_mb": {s.rfilename: round((s.size or 0) / 1e6) for s in weights},
        "license": card.get("license"),
        "datasets": card.get("datasets"),
        "last_modified": str(info.last_modified)[:10],
    }


def coverage(chars: list[str], vocab: set[str]) -> dict:
    """In-vocabulary fraction raw and after a per-character OpenCC conversion."""
    n = len(chars)
    raw = sum(c in vocab for c in chars)
    t2s = [T2S.convert(c) for c in chars]
    s2t = [S2T.convert(c) for c in chars]
    best = max((chars, t2s, s2t), key=lambda cs: sum(c in vocab for c in cs))
    missing = Counter(orig for orig, c in zip(chars, best) if c not in vocab)
    return {
        "n_han": n,
        "raw": raw,
        "after_t2s": sum(c in vocab for c in t2s),
        "after_s2t": sum(c in vocab for c in s2t),
        "top_missing": missing.most_common(12),
    }


def romanizer_failures(song: Song, text: str) -> dict:
    """Han characters the song's romanizer could not give a reading for."""
    chars = han_chars(text)
    if song.lang == "zh":
        readings = lazy_pinyin("".join(chars), style=Style.NORMAL, errors=lambda c: [PINYIN_FAIL])
        failed = [c for c, r in zip(chars, readings) if r == PINYIN_FAIL]
        lib = "pypinyin"
    else:
        pairs = get_jyutping_list("".join(chars))
        failed = [c for c, r in pairs if not r]
        lib = "ToJyutping"
    return {"lib": lib, "n_han": len(chars), "n_failed": len(failed), "failed": sorted(set(failed))}


def main() -> None:
    api_info = {}
    vocabs = {}
    for repos in H_MODELS.values():
        for repo in repos:
            vocabs[repo] = load_vocab(repo)
            api_info[repo] = model_files(repo)
            print(
                f"model {repo}: vocab_size={vocabs[repo][1]} single_char_tokens={len(vocabs[repo][0])}"
            )
            print("   ", json.dumps(api_info[repo], ensure_ascii=False))

    result = {"models": api_info, "songs": {}}
    for song in PILOT:
        song_out = {}
        for name, text in candidate_texts(song).items():
            chars = han_chars(text)
            entry = {
                "romanizer": romanizer_failures(song, text),
                "vocab": {repo: coverage(chars, vocabs[repo][0]) for repo in H_MODELS[song.lang]},
            }
            song_out[name] = entry
            r = entry["romanizer"]
            print(f"\n#{song.num} {song.title} [{song.lang}] text={name}")
            print(f"  Arm R {r['lib']}: han={r['n_han']} failed={r['n_failed']} {r['failed']}")
            for repo, c in entry["vocab"].items():
                print(
                    f"  Arm H {repo}: han={c['n_han']} in_vocab raw={c['raw']} "
                    f"t2s={c['after_t2s']} s2t={c['after_s2t']} missing={c['top_missing']}"
                )
        result["songs"][song.video_id] = song_out
    (OUT_DIR / "phase0c_vocab.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
