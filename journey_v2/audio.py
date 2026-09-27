"""Sound for the v2 sample (standard library + FFmpeg, runs on any Python).

Layers:
  - the calm score (soundtrack.py) as the bed, from a random point of the track
    (printed; repeat a take with SOLAR_MUSIC_OFFSET); if no score is installed,
    the old deep-space ambience, levelled, is used instead
  - a soft, low "breath" when the camera moves in / out: dark filtered noise
    (180-650 Hz), smooth envelope, well under the music; nothing in the harsh
    1-4 kHz band
  - one gentle chime when the experiment reaches its target time
  - a quiet, in-key glide (A4 -> A3) under the labelled rewind
No sounds on digit changes. Every layer is measured on its own (EBU R128) and
set to a fixed level under the bed, so the balance does not depend on the files.
"""

from __future__ import annotations

import math
import random
import re
import struct
import subprocess
import wave
from pathlib import Path

RATE = 44100
AMBIENCE = Path(__file__).resolve().parent.parent / "assets" / "audio" / "deep_space_ambience.wav"


def _read_wav(path: Path):
    with wave.open(str(path), "rb") as w:
        n, ch = w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    vals = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    if ch == 1:
        return [v / 32768 for v in vals], [v / 32768 for v in vals]
    return [v / 32768 for v in vals[0::2]], [v / 32768 for v in vals[1::2]]


def _bed(duration: float):
    """Ambience from the file's steady middle (its first/last 2 s are fades)."""
    L, R = _read_wav(AMBIENCE)
    lo, hi = int(2.5 * RATE), len(L) - int(2.5 * RATE)
    core_l, core_r = L[lo:hi], R[lo:hi]
    n = int(duration * RATE)
    xf = int(1.5 * RATE)
    out_l, out_r = [0.0] * n, [0.0] * n
    i = 0
    while i < n:                                   # cross-faded repeats, never a gap
        for k in range(len(core_l)):
            j = i + k
            if j >= n:
                break
            g = min(1.0, k / xf) if i > 0 else 1.0
            out_l[j] += core_l[k] * g
            out_r[j] += core_r[k] * g
        i += len(core_l) - xf
    _level(out_l, out_r)
    fade_in, fade_out = int(0.6 * RATE), int(0.8 * RATE)
    for j in range(n):
        g = min(1.0, j / fade_in, (n - 1 - j) / fade_out)
        out_l[j] *= g
        out_r[j] *= g
    return out_l, out_r


def _level(L, R, block_s=0.05, window_s=2.0, max_gain=2.0):
    """Slow automatic gain: removes the ambience's swells, keeps its texture."""
    blk = int(block_s * RATE)
    nb = max(1, len(L) // blk)
    rms = []
    for b in range(nb):
        seg = range(b * blk, min(len(L), (b + 1) * blk))
        rms.append(math.sqrt(sum(L[j] * L[j] + R[j] * R[j] for j in seg) / (2 * len(seg)) + 1e-12))
    half = int(window_s / block_s / 2)
    env = [sum(rms[max(0, b - half):b + half + 1]) / len(rms[max(0, b - half):b + half + 1]) for b in range(nb)]
    ref = sorted(env)[len(env) // 2]
    gains = [min(max_gain, max(1 / max_gain, ref / e)) for e in env]
    for j in range(len(L)):
        x = j / blk - 0.5
        b0 = min(nb - 1, max(0, int(math.floor(x))))
        b1 = min(nb - 1, b0 + 1)
        u = min(1.0, max(0.0, x - b0))
        g = gains[b0] * (1 - u) + gains[b1] * u
        L[j] *= g
        R[j] *= g


def _swell(dur: float, rising: bool, seed: int):
    """Soft 'breath': low-passed noise whose (low) cut-off drifts up or down, with a
    raised-sine envelope. Two independent noises keep it wide without panning."""
    rnd = random.Random(seed)
    n = int(dur * RATE)
    l, r = [0.0] * n, [0.0] * n
    st = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]                      # per channel: lp1, lp2, dc
    for j in range(n):
        u = j / n
        f = 180.0 + 470.0 * (u if rising else 1.0 - u) ** 1.5
        a = 1.0 - math.exp(-2.0 * math.pi * f / RATE)
        env = math.sin(math.pi * u) ** 2
        for c, out in ((0, l), (1, r)):
            x = rnd.uniform(-1.0, 1.0)
            s0 = st[c]
            s0[0] += a * (x - s0[0])
            s0[1] += a * (s0[0] - s0[1])
            s0[2] += 0.0071 * (s0[1] - s0[2])                     # remove rumble below ~50 Hz
            out[j] = (s0[1] - s0[2]) * env
    return l, r


def _chime(dur: float):
    n = int(dur * RATE)
    parts = ((659.25, 1.0, 1.1), (987.77, 0.45, 0.7), (1318.5, 0.25, 0.45))   # E5, B5, E6
    out = [0.0] * n
    for j in range(n):
        t = j / RATE
        att = min(1.0, t / 0.006)
        out[j] = att * sum(a * math.exp(-t / tau) * math.sin(2 * math.pi * f * t) for f, a, tau in parts)
    return out, out[:]


def _glide(dur: float, seed: int):
    """Descending sine A4 -> A3 with a soft second harmonic, raised-sine envelope."""
    n = int(dur * RATE)
    l, r = [0.0] * n, [0.0] * n
    ph = 0.0
    for j in range(n):
        u = j / n
        f = 440.0 * 2 ** (-u)
        ph += 2 * math.pi * f / RATE
        v = (math.sin(ph) + 0.15 * math.sin(2 * ph)) * math.sin(math.pi * u) ** 2
        l[j], r[j] = v, v
    return l, r


def _mix_into(dst_l, dst_r, src, t0: float, gain: float):
    s_l, s_r = src
    i0 = int(t0 * RATE)
    for k in range(len(s_l)):
        j = i0 + k
        if 0 <= j < len(dst_l):
            dst_l[j] += s_l[k] * gain
            dst_r[j] += s_r[k] * gain


def _write(path: Path, L, R, gain=1.0):
    frames = bytearray()
    for a, b in zip(L, R):
        frames += struct.pack("<hh", int(max(-1, min(1, a * gain)) * 32767),
                              int(max(-1, min(1, b * gain)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def _loudness(path: Path, ffmpeg: str):
    err = subprocess.run([ffmpeg, "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    return (float(i[-1]) if i else None), (float(p[-1]) if p else None)


# target levels (LUFS, each layer measured on its own over its own length)
BED_LUFS = -20.0             # the music
SWELL_LUFS = -33.0           # camera moves: 13 dB under the music
ACCENT_LUFS = -27.0          # target reached
REWIND_LUFS = -33.0


def _scaled(layer, path: Path, ffmpeg: str, target: float):
    """Return the layer scaled so that on its own it measures `target` LUFS."""
    tmp = path.with_name(path.stem + ".layer.wav")
    _write(tmp, *layer)
    lufs, _ = _loudness(tmp, ffmpeg)
    tmp.unlink()
    g = 10 ** ((target - lufs) / 20) if lufs is not None else 1.0
    return [x * g for x in layer[0]], [x * g for x in layer[1]]


def build(sample, path: Path, ffmpeg: str, master_lufs: float = -17.0, peak_limit: float = -1.5):
    """Write the sample's soundtrack and return its measured (LUFS, peak dBFS).
    The balance between layers is fixed above; the whole mix is then raised or
    lowered towards `master_lufs` without letting the peak pass `peak_limit`."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import soundtrack
    music = path.with_name(path.stem + ".music.wav")
    if soundtrack.build(music, sample.DUR, "auto", target_lufs=BED_LUFS):
        L, R = _read_wav(music)
        music.unlink()
    else:
        L, R = _scaled(_bed(sample.DUR), path, ffmpeg, BED_LUFS)
    for i, (kind, t0, dur) in enumerate(sample.audio_events()):
        if kind == "whoosh_in":
            _mix_into(L, R, _scaled(_swell(dur + 0.8, True, 11 + i), path, ffmpeg, SWELL_LUFS), t0 - 0.3, 1.0)
        elif kind == "whoosh_out":
            _mix_into(L, R, _scaled(_swell(dur + 0.8, False, 11 + i), path, ffmpeg, SWELL_LUFS), t0 - 0.2, 1.0)
        elif kind == "accent":
            _mix_into(L, R, _scaled(_chime(dur), path, ffmpeg, ACCENT_LUFS), t0, 1.0)
        elif kind == "rewind":
            _mix_into(L, R, _scaled(_glide(dur, 11 + i), path, ffmpeg, REWIND_LUFS), t0, 1.0)
    peak = max(max(abs(x) for x in L), max(abs(x) for x in R)) or 1.0
    _write(path, L, R)
    lufs, _ = _loudness(path, ffmpeg)
    gain_db = (master_lufs - lufs) if lufs is not None else 0.0
    gain_db = min(gain_db, peak_limit - 20 * math.log10(peak))
    _write(path, L, R, 10 ** (gain_db / 20))
    return _loudness(path, ffmpeg)
