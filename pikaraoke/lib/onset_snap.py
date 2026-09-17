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

# Single-word lines have no words 2..n to reference. A high percentile of
# the word's own claimed span works instead: smeared gap frames are LOW
# outliers, so with >= ~20% of the span genuinely sung the percentile lands
# at the sung level; a span lying wholly in a gap yields a floor-level
# reference that MIN_REF_DB rejects. Validated at 35/36 usable on corpus.
SINGLE_WORD_REF_PCT = 80.0


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


def decode_env_db(vocal_path: str | Path, label: str) -> np.ndarray | None:
    """Decode ``vocal_path``'s RMS envelope, or None if ffmpeg can't read it.

    Shared decode-or-bail for the snap entry points and the evidence veto;
    a None return is each caller's cue to leave the timings unchanged.
    ``label`` names the pass in the warning.
    """
    try:
        return rms_envelope_db(vocal_path)
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("%s: cannot decode %s (%s); skipped", label, vocal_path, exc)
        return None


def _sung_level_ref(env: np.ndarray, words: list[dict], end: bool = False) -> float | None:
    """Sung-level reference for the line, or None if its span is empty.

    For 2+ words: the median envelope level over the spans of words 2..n,
    plus word 1's own span when ``end`` is true and word 1 is longer than
    :data:`MIN_WORD_DUR_S`. Word 1 is excluded by default: when its start
    was stretched across a preceding gap, including it drags the reference
    down until reverb tails pass for singing. The end path runs after
    onsets have already repaired that start, so a substantial word 1 is
    safe to include there — and on a line that is mostly one long held
    note plus short trailing words, leaving it out misstates the sung
    level.

    For a single word: the :data:`SINGLE_WORD_REF_PCT` percentile over its
    own claimed span, since there are no words 2..n. Smeared gap frames are
    low outliers, so with enough of the span genuinely sung the percentile
    still lands at the sung level. Independent of ``end``.
    """
    if len(words) == 1:
        w = words[0]
        span_idx = np.arange(int(w["start"] / HOP_S), int(w["end"] / HOP_S) + 1)
        span_idx = span_idx[(span_idx >= 0) & (span_idx < len(env))]
        if len(span_idx) == 0:
            return None
        return float(np.percentile(env[span_idx], SINGLE_WORD_REF_PCT))
    ref_words = words[1:]
    if end and words[0]["end"] - words[0]["start"] > MIN_WORD_DUR_S:
        ref_words = [words[0]] + ref_words
    span_idx = np.concatenate(
        [np.arange(int(w["start"] / HOP_S), int(w["end"] / HOP_S) + 1) for w in ref_words]
    )
    span_idx = span_idx[(span_idx >= 0) & (span_idx < len(env))]
    if len(span_idx) == 0:
        return None
    return float(np.median(env[span_idx]))


def _detect_rise(env: np.ndarray, t0: float, t1: float, ref_db: float) -> float | None:
    """Time of the first qualifying energy rise in ``[t0, t1]``, else None.

    A rise qualifies either by landing near the sung level outright, or
    by landing softly (:data:`SOFT_NEAR_DB`) and then sustaining near
    that level for :data:`SUSTAIN_S`. Either way the voice must then hold
    through to ``t1`` (word 2's start, or word 1's own claimed end on a
    one-word line): word 1's true onset begins a voiced run that
    continues at least that far, while a bump in a noisy reverb tail
    collapses back into the gap.
    """
    a = max(EDGE_FRAMES, int(t0 / HOP_S))
    b_bound = int(t1 / HOP_S)
    b_env = len(env) - EDGE_FRAMES
    b = min(b_bound, b_env)
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
        # A rise within the sustain window of the bound is already
        # continuous with it; the median over that sliver would only
        # measure the attack itself.
        if b - i < sustain_frames:
            # Continuity with the bound is trustworthy; the envelope
            # running out is not — onsets near the stem end are unreliable.
            if b_bound <= b_env:
                return i * HOP_S
            continue
        if float(np.median(env[i:b])) >= ref_db - SUSTAIN_NEAR_DB:
            return i * HOP_S
    return None


def snap_line_onsets(
    line_objects: list[dict], vocal_path: str | Path, env: np.ndarray | None = None
) -> tuple[list[dict], dict]:
    """Snap each line's first word to the detected vocal onset.

    A single-word line is searched up to its own claimed end rather than
    word 2's start (see ``bound`` below), so :func:`_detect_rise`'s
    continuity check demands the voice hold all the way to that claimed
    end. For a held note this is correct: whisper clips the end early, so
    the claimed end sits inside the true run. A staccato word with a
    wildly long claimed span won't snap — the safe direction, since the
    line is merely left untouched rather than moved to a false onset.

    Returns ``(line_objects, stats)``. Lines are replaced by copies only
    when moved; on decode failure the input is returned unchanged and
    ``stats["bailed"]`` names the reason. ``env`` reuses a precomputed
    :func:`rms_envelope_db` envelope instead of decoding ``vocal_path``.
    """
    if env is None:
        env = decode_env_db(vocal_path, "onset snap")
        if env is None:
            return line_objects, {"bailed": "decode_failed"}

    snaps: list[dict] = []
    n_low_ref = 0
    n_fired = n_no_rise = n_below_min_shift = n_undetectable = n_single_word = 0
    out: list[dict] = []
    for obj in line_objects:
        words = obj.get("words") or []
        if not words:
            out.append(obj)
            continue
        if len(words) == 1:
            n_single_word += 1
        w1s, w1e = words[0]["start"], words[0]["end"]
        bound = words[1]["start"] if len(words) >= 2 else words[0]["end"]
        if bound - w1s < MIN_WORD_DUR_S:
            out.append(obj)
            continue

        ref = _sung_level_ref(env, words)
        if ref is None:
            out.append(obj)
            continue
        if ref < MIN_REF_DB:
            n_low_ref += 1
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

        n_fired += 1
        lo = min(int(w1s / HOP_S), len(env) - 1)
        hi = min(max(int(bound / HOP_S), lo + 1), len(env))
        p20 = float(np.percentile(env[lo:hi], 20))
        if ref - p20 < STEP_DB:
            n_undetectable += 1

        onset = _detect_rise(env, w1s, bound, ref)
        if onset is None:
            n_no_rise += 1
            out.append(obj)
            continue

        new_start = min(max(onset - SNAP_MARGIN_S, w1s), bound - MIN_WORD_DUR_S)
        if new_start - w1s < MIN_SHIFT_S:
            n_below_min_shift += 1
            out.append(obj)
            continue

        # Whisper's word ends are bounded by the next word's attention, so
        # keep the end when it still lies past the snapped start; otherwise
        # the whole span sat in the gap — carry the duration forward.
        if w1e >= new_start + MIN_WORD_DUR_S:
            new_end = w1e
        else:
            new_end = min(max(new_start + (w1e - w1s), new_start + MIN_WORD_DUR_S), bound)

        new_obj = dict(obj)
        new_obj["words"] = [{**words[0], "start": new_start, "end": new_end}] + words[1:]
        new_obj["start"] = new_start
        out.append(new_obj)
        snaps.append({"line_id": obj.get("line_id"), "shift_s": round(new_start - w1s, 3)})

    # Invariant: n_fired == n_snapped + n_no_rise + n_below_min_shift.
    stats = {
        "n_lines": len(line_objects),
        "n_snapped": len(snaps),
        "n_low_ref": n_low_ref,
        "n_fired": n_fired,
        "n_no_rise": n_no_rise,
        "n_below_min_shift": n_below_min_shift,
        "n_undetectable": n_undetectable,
        "n_single_word": n_single_word,
        "snaps": snaps,
    }
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

    A single-word line's reference comes from its own claimed span (see
    :func:`_sung_level_ref`). Because onsets run first, that span is
    already the snapped, cleaner one by the time this reference is taken.

    Returns ``(line_objects, stats)`` with the same copy, bail, and
    ``env`` reuse semantics as :func:`snap_line_onsets`.
    """
    if env is None:
        env = decode_env_db(vocal_path, "end snap")
        if env is None:
            return line_objects, {"bailed": "decode_failed"}

    release_frames = int(RELEASE_SUSTAIN_S / HOP_S)
    extends: list[dict] = []
    n_fired = n_low_ref = n_below_min_shift = n_single_word = 0
    out: list[dict] = []
    for idx, obj in enumerate(line_objects):
        words = obj.get("words") or []
        if not words:
            out.append(obj)
            continue
        if len(words) == 1:
            n_single_word += 1
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

        # end=True: onsets already ran, so a substantial word 1 no longer
        # needs excluding to protect the reference from onset smear, and
        # including it fixes lines that are mostly one held note plus
        # short trailing words. The last word's own claimed span is
        # genuinely sung either way — a clipped span is a subset of the
        # true one — so referencing it is fair regardless.
        ref = _sung_level_ref(env, words, end=True)
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
            n_below_min_shift += 1
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

    # Invariant: n_fired == n_extended + n_below_min_shift.
    stats = {
        "n_lines": len(line_objects),
        "n_low_ref": n_low_ref,
        "n_fired": n_fired,
        "n_below_min_shift": n_below_min_shift,
        "n_extended": len(extends),
        "n_single_word": n_single_word,
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


def snap_line_edges(
    line_objects: list[dict], vocal_path: str | Path, env: np.ndarray | None = None
) -> tuple[list[dict], dict]:
    """Run the onset and end snaps sharing a single envelope decode.

    Onsets first: a snapped-forward line start widens the room the
    previous line's end may legitimately extend into. ``env`` reuses a
    precomputed :func:`rms_envelope_db` envelope instead of decoding
    ``vocal_path`` (the stage shares it with the evidence veto).
    """
    if env is None:
        env = decode_env_db(vocal_path, "edge snap")
        if env is None:
            return line_objects, {"bailed": "decode_failed"}
    out, onset_stats = snap_line_onsets(line_objects, vocal_path, env)
    out, end_stats = snap_line_ends(out, vocal_path, env)
    return out, {"onset": onset_stats, "end": end_stats}
