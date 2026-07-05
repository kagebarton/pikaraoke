"""Snap line-edge word timings to the vocal stem's energy envelope.

Whisper's word onsets after an instrumental gap are its least reliable
timestamps: cross-attention smears the first word's start back into the
gap, and VAD/silence suppression can't correct it because a separated
vocal stem carries reverb tails and bleed there rather than silence.
Rendered as karaoke, that reads as "first word sweeps early, line
recovers at word 2" (the ASS writer re-anchors at every inter-word gap).

This post-pass repairs it at one point for every timing source. For each
line's first word it searches ``[word1.start, word2.start]`` in the
stem's RMS envelope for the first sustained rise that lands near the
line's own sung level, then shifts the word start forward to it. A
reverb tail decays monotonically, so it cannot fake a rise — the exact
failure mode that defeats an absolute silence threshold. Shifts are
forward-only and bounded by word 2, so an on-time line is never made
worse.
"""

import logging
import subprocess
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Envelope resolution: 50 ms RMS windows every 25 ms at 16 kHz mono.
ENVELOPE_SR = 16000
HOP_S = 0.025
WIN_S = 0.050

# A rise is EDGE_FRAMES of mean level jumping by at least STEP_DB.
STEP_DB = 10.0
EDGE_FRAMES = 3

# The post-rise level must land within this of the line's median sung
# level, so a mid-gap artifact bump can't register as the voice.
NEAR_SUNG_DB = 8.0

# Soft-onset tier: a rise landing this far below the sung level still
# counts if it then SUSTAINS near that level — a quietly sung pickup
# word ("I'm doing...") holds its energy, while a breath bump or reverb
# tail dies within a couple frames. Without this tier the detector
# skips soft pickups and locks onto the louder continuation, turning an
# early word 1 into a late one.
SOFT_NEAR_DB = 16.0
SUSTAIN_S = 0.4
SUSTAIN_NEAR_DB = 12.0

# Snap slightly before the detected rise frame so the sweep catches the
# true attack.
SNAP_MARGIN_S = 0.05

# Shifts below this are within whisper's normal jitter; leave them.
MIN_SHIFT_S = 0.15

# Never shrink word 1 below this, and skip search windows narrower.
MIN_WORD_DUR_S = 0.1

# Line-end snap: a line-final word has released once the level stays
# below the sung reference (by SUSTAIN_NEAR_DB) for this long. Shorter
# than SUSTAIN_S — it only confirms the fall is a release rather than a
# tremolo dip, not that a word is being sung.
RELEASE_SUSTAIN_S = 0.2

# Extended ends stop this short of the next line's first word.
NEXT_LINE_GAP_S = 0.1

# Lines whose sung reference sits below this are not singing anywhere in
# their claimed span (misplaced over near-silence). With the reference at
# the noise floor every relative check degenerates — "near sung level"
# becomes trivially true — so leave those lines alone. Steady bleed above
# the floor defeats the relative checks the same way, but no envelope
# floor can catch it; such lines are an upstream misplacement problem.
MIN_REF_DB = -45.0


def rms_envelope_db(audio_path: str | Path) -> np.ndarray:
    """dB RMS envelope of ``audio_path`` (any ffmpeg-readable format).

    3-frame median smoothed; one value per :data:`HOP_S`. Raises
    ``subprocess.CalledProcessError`` if ffmpeg cannot decode the file.
    """
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(audio_path),
        "-ac",
        "1",
        "-ar",
        str(ENVELOPE_SR),
        "-f",
        "s16le",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    win = int(WIN_S * ENVELOPE_SR)
    hop = int(HOP_S * ENVELOPE_SR)
    if len(pcm) < win:
        return np.full(1, -120.0, dtype=np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(pcm, win)[::hop]
    rms = np.sqrt((frames**2).mean(axis=1))
    db = 20.0 * np.log10(np.maximum(rms, 1e-6))
    if len(db) >= 3:
        db[1:-1] = np.median(np.stack([db[:-2], db[1:-1], db[2:]]), axis=0)
    return db


def _decode_env(vocal_path: str | Path, label: str) -> np.ndarray | None:
    """Decode ``vocal_path``'s RMS envelope, or None if ffmpeg can't read it.

    Shared decode-or-bail for the three snap entry points; a None return
    is each caller's cue to leave the timings unchanged. ``label`` names
    the pass in the warning.
    """
    try:
        return rms_envelope_db(vocal_path)
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("%s: cannot decode %s (%s); skipped", label, vocal_path, exc)
        return None


def _sung_level_ref(env: np.ndarray, words: list[dict]) -> float | None:
    """Median envelope level over the spans of words 2..n, or None if empty.

    Word 1's own span is excluded on purpose: when it was stretched across
    a preceding gap, including it drags the reference down until reverb
    tails pass for singing. Both snaps gate on this same reference, so a
    change here must hold for both.
    """
    span_idx = np.concatenate(
        [np.arange(int(w["start"] / HOP_S), int(w["end"] / HOP_S) + 1) for w in words[1:]]
    )
    span_idx = span_idx[(span_idx >= 0) & (span_idx < len(env))]
    if len(span_idx) == 0:
        return None
    return float(np.median(env[span_idx]))


def _detect_rise(env: np.ndarray, t0: float, t1: float, ref_db: float) -> float | None:
    """Time of the first qualifying energy rise in ``[t0, t1]``, else None.

    A rise qualifies either by landing near the sung level outright, or
    by landing softly (:data:`SOFT_NEAR_DB`) and then sustaining near
    that level for :data:`SUSTAIN_S`. Either way the voice must then
    hold through to ``t1`` (word 2's start): word 1's true onset begins
    the voiced run that word 2 continues, while a bump in a noisy reverb
    tail collapses back into the gap.
    """
    a = max(EDGE_FRAMES, int(t0 / HOP_S))
    b = min(len(env) - EDGE_FRAMES, int(t1 / HOP_S))
    sustain_frames = int(SUSTAIN_S / HOP_S)
    for i in range(a, b):
        pre = env[i - EDGE_FRAMES : i].mean()
        post = env[i : i + EDGE_FRAMES].mean()
        if post - pre < STEP_DB:
            continue
        if post < ref_db - NEAR_SUNG_DB and not (
            post >= ref_db - SOFT_NEAR_DB
            and env[i : i + sustain_frames].mean() >= ref_db - SUSTAIN_NEAR_DB
        ):
            continue
        # A rise within the sustain window of word 2 is already
        # continuous with it; the median over that sliver would only
        # measure the attack itself.
        if b - i < sustain_frames or float(np.median(env[i:b])) >= ref_db - SUSTAIN_NEAR_DB:
            return i * HOP_S
    return None


def snap_line_onsets(
    line_objects: list[dict], vocal_path: str | Path, env: np.ndarray | None = None
) -> tuple[list[dict], dict]:
    """Snap each line's first word to the detected vocal onset.

    Returns ``(line_objects, stats)``. Lines are replaced by copies only
    when moved; on decode failure the input is returned unchanged and
    ``stats["bailed"]`` names the reason. ``env`` reuses a precomputed
    :func:`rms_envelope_db` envelope instead of decoding ``vocal_path``.
    """
    if env is None:
        env = _decode_env(vocal_path, "onset snap")
        if env is None:
            return line_objects, {"bailed": "decode_failed"}

    snaps: list[dict] = []
    out: list[dict] = []
    for obj in line_objects:
        words = obj.get("words") or []
        if len(words) < 2:
            out.append(obj)
            continue
        w1s, w1e = words[0]["start"], words[0]["end"]
        w2s = words[1]["start"]
        if w2s - w1s < MIN_WORD_DUR_S:
            out.append(obj)
            continue

        ref = _sung_level_ref(env, words)
        if ref is None:
            out.append(obj)
            continue

        # An on-time word 1 is near sung level at its claimed start AND
        # across its claimed span; skip those, or an on-time word followed
        # by an intra-line pause would get snapped to the NEXT word's
        # onset (back-to-back lines leave no quiet before word 1 for the
        # rise detector). The span check keeps a loud reverb tail at the
        # start from passing as on time — a tail collapses over the span,
        # sustained singing holds.
        # Clamp into the envelope like _detect_rise: a first word at/after
        # the stem's end (the envelope omits the final window) would slice
        # empty and warn.
        a = min(max(int(w1s / HOP_S), 0), max(len(env) - EDGE_FRAMES, 0))
        span1 = env[a : max(int(w1e / HOP_S), a + 1)]
        if (
            env[a : a + EDGE_FRAMES].mean() >= ref - NEAR_SUNG_DB
            and float(np.median(span1)) >= ref - SUSTAIN_NEAR_DB
        ):
            out.append(obj)
            continue

        onset = _detect_rise(env, w1s, w2s, ref)
        if onset is None:
            out.append(obj)
            continue

        new_start = min(max(onset - SNAP_MARGIN_S, w1s), w2s - MIN_WORD_DUR_S)
        if new_start - w1s < MIN_SHIFT_S:
            out.append(obj)
            continue

        # Whisper's word ends are bounded by the next word's attention, so
        # keep the end when it still lies past the snapped start; otherwise
        # the whole span sat in the gap — carry the duration forward.
        if w1e >= new_start + MIN_WORD_DUR_S:
            new_end = w1e
        else:
            new_end = min(max(new_start + (w1e - w1s), new_start + MIN_WORD_DUR_S), w2s)

        new_obj = dict(obj)
        new_obj["words"] = [{**words[0], "start": new_start, "end": new_end}] + words[1:]
        new_obj["start"] = new_start
        out.append(new_obj)
        snaps.append({"line_id": obj.get("line_id"), "shift_s": round(new_start - w1s, 3)})

    stats = {"n_lines": len(line_objects), "n_snapped": len(snaps), "snaps": snaps}
    if snaps:
        logger.info(
            "onset snap: %d/%d line starts moved forward (max %+.2fs)",
            len(snaps),
            len(line_objects),
            max(s["shift_s"] for s in snaps),
        )
    return out, stats


def snap_line_ends(
    line_objects: list[dict], vocal_path: str | Path, env: np.ndarray | None = None
) -> tuple[list[dict], dict]:
    """Extend each line's clipped last word to the vocal release.

    Mirror of :func:`snap_line_onsets` for line ends: whisper truncates a
    held line-final word because nothing anchors its end once the phonetic
    content stops, so the karaoke fill finishes while the note still
    sounds. For each line whose last word is still near the line's sung
    level at its claimed end (evidence of clipping), the end is pushed
    forward to the first sustained fall below that level. Gated this way
    the detector never models a hold duration — it traces the voiced run
    the word is already inside until the run ends. Extensions are
    forward-only and bounded by the next line's first word, so a
    correctly ended line is never made worse.

    Returns ``(line_objects, stats)`` with the same copy, bail, and
    ``env`` reuse semantics as :func:`snap_line_onsets`.
    """
    if env is None:
        env = _decode_env(vocal_path, "end snap")
        if env is None:
            return line_objects, {"bailed": "decode_failed"}

    release_frames = int(RELEASE_SUSTAIN_S / HOP_S)
    extends: list[dict] = []
    n_fired = n_low_ref = 0
    out: list[dict] = []
    for idx, obj in enumerate(line_objects):
        words = obj.get("words") or []
        if len(words) < 2:
            out.append(obj)
            continue
        w_end = words[-1]["end"]

        bound = len(env) * HOP_S
        for nxt in line_objects[idx + 1 :]:
            nxt_words = nxt.get("words") or []
            if nxt_words:
                bound = nxt_words[0]["start"] - NEXT_LINE_GAP_S
                break
        if bound - w_end < MIN_SHIFT_S:
            out.append(obj)
            continue

        # The last word's claimed span is genuinely sung either way — a
        # clipped span is a subset of the true one — so the shared
        # words-2..n reference applies unchanged.
        ref = _sung_level_ref(env, words)
        if ref is None:
            out.append(obj)
            continue
        if ref < MIN_REF_DB:
            n_low_ref += 1
            out.append(obj)
            continue

        # Clip evidence: the voice must still be near sung level at the
        # claimed end. If it has already fallen away the end is plausibly
        # right, so a correctly ended staccato word is never touched.
        e = min(max(int(w_end / HOP_S), 0), max(len(env) - EDGE_FRAMES, 0))
        if env[e : e + EDGE_FRAMES].mean() < ref - NEAR_SUNG_DB:
            out.append(obj)
            continue
        n_fired += 1

        # Trace the voiced run to its release: the first point where the
        # level stays below the sung reference for RELEASE_SUSTAIN_S. A
        # tremolo dip recovers within a couple frames and does not
        # qualify. Only full-length windows count — near the bound or the
        # envelope end a truncated window would let a single quiet frame
        # (or the next line's audio) pass for a sustained fall. No release
        # before the bound means the voice runs into the next line (a
        # melisma): extend to the bound.
        b = min(int(bound / HOP_S), len(env))
        new_end = bound
        for i in range(e, b - release_frames + 1):
            if env[i : i + release_frames].mean() < ref - SUSTAIN_NEAR_DB:
                new_end = i * HOP_S
                break
        if new_end - w_end < MIN_SHIFT_S:
            out.append(obj)
            continue

        new_obj = dict(obj)
        new_obj["words"] = words[:-1] + [{**words[-1], "end": new_end}]
        new_obj["end"] = new_end
        out.append(new_obj)
        extends.append(
            {
                "line_id": obj.get("line_id"),
                "extend_s": round(new_end - w_end, 3),
                # No release found before the bound — the harmony/melisma
                # blind-spot suspects.
                "to_bound": new_end == bound,
            }
        )

    stats = {
        "n_lines": len(line_objects),
        "n_low_ref": n_low_ref,
        "n_fired": n_fired,
        "n_extended": len(extends),
        "extends": extends,
    }
    if extends:
        logger.info(
            "end snap: %d/%d line ends extended (max %+.2fs)",
            len(extends),
            len(line_objects),
            max(s["extend_s"] for s in extends),
        )
    return out, stats


def snap_line_edges(line_objects: list[dict], vocal_path: str | Path) -> tuple[list[dict], dict]:
    """Run the onset and end snaps sharing a single envelope decode.

    Onsets first: a snapped-forward line start widens the room the
    previous line's end may legitimately extend into.
    """
    env = _decode_env(vocal_path, "edge snap")
    if env is None:
        return line_objects, {"bailed": "decode_failed"}
    out, onset_stats = snap_line_onsets(line_objects, vocal_path, env)
    out, end_stats = snap_line_ends(out, vocal_path, env)
    return out, {"onset": onset_stats, "end": end_stats}
