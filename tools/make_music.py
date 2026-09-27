"""Generate the calm background score (original, royalty-free) used under every video.

    python3 tools/make_music.py            # -> assets/audio/music/solar_calm_10min.m4a
    (needs numpy and ffmpeg; the finished file is committed, so this is only for re-making it)

A slow ambient piece in A major, at home over the existing deep-space drone (A/E):
  - warm pad chords (detuned additive voices, 5 s swells, 12 s per chord),
  - a soft bass on the chord roots,
  - sparse felt-piano notes from the chord and the A-major pentatonic,
  - rare high shimmer, and a long, dark stereo reverb.
Sections change the harmony and the note density every ~48 s so ten minutes never
feel like a loop. No fades at the ends: the soundtrack builder adds them, and the
first and last chord are the same so repeats cross-fade cleanly. Seeded: every run
produces the same file.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from render_io import ffmpeg_exe  # noqa: E402

SR = 44_100
DUR = 600.0
CHORD_S = 12.0
OUT = ROOT / "assets" / "audio" / "music" / "solar_calm_10min.m4a"


def hz(note: str) -> float:
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1,
             "A": 0, "A#": 1, "B": 2}
    name, octave = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((names[name] + 12 * (octave - 4)) / 12)


CHORDS = {  # bass, pad voicing (smooth voice leading inside E3..G#4)
    "Amaj9": ("A2", ["E3", "G#3", "B3", "C#4", "E4"]),
    "F#m9":  ("F#2", ["E3", "A3", "C#4", "G#4"]),
    "Dmaj9": ("D3", ["F#3", "A3", "C#4", "E4"]),
    "E6sus": ("E3", ["F#3", "A3", "B3", "C#4"]),
    "Bm11":  ("B2", ["D3", "A3", "C#4", "E4"]),
    "C#m7":  ("C#3", ["E3", "G#3", "B3", "E4"]),
}
SECTIONS = {
    "A": ["Amaj9", "F#m9", "Dmaj9", "E6sus"],
    "B": ["Dmaj9", "Amaj9", "Bm11", "E6sus"],
    "C": ["F#m9", "Dmaj9", "Amaj9", "C#m7"],
}
FORM = "AABACBAACBAA"                 # 12 x 48 s = 576 s, then Amaj9 to the end
DENSITY = {"A": 0.22, "B": 0.32, "C": 0.16}      # felt-piano notes per second
PENTA = ["A4", "B4", "C#5", "E5", "F#5", "A5", "B5", "C#6", "E6"]


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def chord_timeline():
    seq = [c for sec in FORM for c in SECTIONS[sec]]
    secs = [sec for sec in FORM for _ in range(4)]
    n_end = int(np.ceil((DUR - len(seq) * CHORD_S) / CHORD_S))
    return seq + ["Amaj9"] * n_end, secs + ["A"] * n_end


def pad(out_l, out_r, rng):
    seq, _ = chord_timeline()
    t_all = np.arange(len(out_l)) / SR
    for i, name in enumerate(seq):
        bass, notes = CHORDS[name]
        t0, t1 = i * CHORD_S - 3.0, (i + 1) * CHORD_S + 4.0          # overlapping swells
        a, b = max(0, int(t0 * SR)), min(len(out_l), int(t1 * SR))
        t = t_all[a:b]
        env = smooth((t - t0) / 5.0) * smooth((t1 - t) / 6.0)
        breath = 0.85 + 0.15 * np.sin(2 * np.pi * 0.05 * t + i)
        for k, note in enumerate(notes):
            f0 = hz(note)
            pan = 0.5 + 0.35 * np.sin(k * 1.7 + i * 0.6)
            voice = np.zeros_like(t)
            for cents in (-7.0, 0.0, 7.0):
                f = f0 * 2 ** (cents / 1200)
                for n in range(1, 7):
                    amp = 1.0 / n ** 1.6 * (0.9 + 0.1 * np.sin(2 * np.pi * rng.uniform(0.03, 0.12) * t))
                    voice += amp * np.sin(2 * np.pi * f * n * t + rng.uniform(0, 2 * np.pi))
            voice *= env * breath * 0.030
            out_l[a:b] += voice * np.sqrt(1 - pan)
            out_r[a:b] += voice * np.sqrt(pan)
        fb = hz(bass)
        sub = (np.sin(2 * np.pi * fb * t) + 0.25 * np.sin(2 * np.pi * 2 * fb * t)) * env * 0.022
        out_l[a:b] += sub
        out_r[a:b] += sub


def felt_note(f, dur, vel):
    t = np.arange(int(dur * SR)) / SR
    att = smooth(t / 0.012)
    tone = (np.sin(2 * np.pi * f * t) * np.exp(-t / 1.9)
            + 0.35 * np.sin(2 * np.pi * 2.005 * f * t) * np.exp(-t / 0.9)
            + 0.14 * np.sin(2 * np.pi * 3.02 * f * t) * np.exp(-t / 0.45)
            + 0.05 * np.sin(2 * np.pi * 4.04 * f * t) * np.exp(-t / 0.3))
    return tone * att * vel


def piano(out_l, out_r, rng):
    seq, secs = chord_timeline()
    t = 2.0
    while t < DUR - 1.0:
        i = min(len(seq) - 1, int(t // CHORD_S))
        chord_notes = {n[:-1] for n in CHORDS[seq[i]][1]}
        pool = [p for p in PENTA if p[:-1] in chord_notes] or PENTA
        notes = [rng.choice(pool)]
        if rng.random() < 0.18:                                          # a small rising figure
            j = PENTA.index(notes[0])
            notes += PENTA[j + 1:j + 3]
        for k, note in enumerate(notes):
            s = felt_note(hz(note), 6.0, rng.uniform(0.35, 0.8) * 0.10)
            a = int((t + 0.42 * k) * SR)
            b = min(len(out_l), a + len(s))
            pan = rng.uniform(0.25, 0.75)
            out_l[a:b] += s[:b - a] * np.sqrt(1 - pan)
            out_r[a:b] += s[:b - a] * np.sqrt(pan)
        t += rng.exponential(1.0 / DENSITY[secs[i]]) + 1.2


def shimmer(out_l, out_r, rng):
    t = 10.0
    while t < DUR - 8.0:
        f = hz(rng.choice(["E6", "B5", "C#6", "A6"]))
        n = int(7.0 * SR)
        tt = np.arange(n) / SR
        s = np.sin(2 * np.pi * f * tt) * np.sin(np.pi * tt / 7.0) ** 2 * 0.016
        a = int(t * SR)
        out_l[a:a + n] += s * 0.7
        out_r[a:a + n] += s
        t += rng.uniform(18.0, 34.0)


def reverb(x, rng, t60=5.0, length=6.0):
    """FFT convolution with a dark, decaying stereo noise tail."""
    n = int(length * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-6.9 * t / t60)
    lp = np.zeros(n)                                                     # tail gets darker with time
    acc, k = 0.0, 0.5
    for i in range(n):
        acc += k * (ir[i] - acc)
        lp[i] = acc
        if i % 4410 == 0:
            k = max(0.06, 0.5 * np.exp(-t[i] / 1.8))
    ir = np.concatenate([np.zeros(int(0.025 * SR)), lp])
    ir /= np.sqrt(np.sum(ir ** 2))
    m = len(x) + len(ir) - 1
    size = 1 << (m - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x)]
    return y


def main():
    rng = np.random.default_rng(20260927)
    n = int(DUR * SR)
    L, R = np.zeros(n), np.zeros(n)
    pad(L, R, rng)
    piano(L, R, rng)
    shimmer(L, R, rng)
    wl, wr = reverb(L, np.random.default_rng(1)), reverb(R, np.random.default_rng(2))
    L, R = 0.72 * L + 0.55 * wl, 0.72 * R + 0.55 * wr
    peak = max(np.abs(L).max(), np.abs(R).max())
    g = 10 ** (-3.0 / 20) / peak                                          # peak -3 dBFS
    pcm = (np.stack([L, R], axis=1) * g * 32767).astype("<i2")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wav = OUT.with_suffix(".wav")
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(OUT)], check=True)
    wav.unlink()
    print(f"✅ {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {DUR / 60:.0f} min)")


if __name__ == "__main__":
    main()
