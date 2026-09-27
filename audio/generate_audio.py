"""Synthesize calm, royalty-free deep-space tonal ambient drone.

Uses only Python standard library (wave, math, struct) with zero third-party dependencies.
Generates a warm 44.1kHz 16-bit stereo ambient bed for the documentary.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44100
DURATION_SEC = 30.0
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "audio" / "deep_space_ambience.wav"


def generate_deep_space_ambience(output_file: Path = OUTPUT_PATH, duration: float = DURATION_SEC):
    """Generate subtle, meditative cosmic ambient audio."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(SAMPLE_RATE * duration)

    # Harmonic components:
    # 55.0 Hz (A1 fundamental)
    # 82.4 Hz (E2 perfect fifth)
    # 110.0 Hz (A2 warm overtone)
    # Binaural detune: 0.15 Hz between left and right channels
    f_base = 55.0
    f_fifth = 82.4069
    f_octave = 110.0

    frames = bytearray()

    for i in range(num_samples):
        t = i / SAMPLE_RATE

        # Smooth envelope at start and end for seamless loop
        fade = 1.0
        if t < 2.0:
            fade = 0.5 * (1.0 - math.cos(math.pi * t / 2.0))
        elif t > (duration - 2.0):
            fade = 0.5 * (1.0 - math.cos(math.pi * (duration - t) / 2.0))

        # Slow LFO breathing modulation (0.08 Hz = ~12.5s cycle)
        lfo = 0.75 + 0.25 * math.sin(2.0 * math.pi * 0.08 * t)

        # Left channel
        s_left = (
            0.50 * math.sin(2.0 * math.pi * f_base * t) +
            0.30 * math.sin(2.0 * math.pi * f_fifth * t) +
            0.15 * math.sin(2.0 * math.pi * (f_octave - 0.1) * t)
        )

        # Right channel (subtle detune for stereo spaciousness)
        s_right = (
            0.50 * math.sin(2.0 * math.pi * (f_base + 0.15) * t) +
            0.30 * math.sin(2.0 * math.pi * (f_fifth - 0.12) * t) +
            0.15 * math.sin(2.0 * math.pi * (f_octave + 0.1) * t)
        )

        # Master volume scale (quiet, non-intrusive documentary background)
        vol = 0.18 * fade * lfo
        val_l = int(max(-32767, min(32767, s_left * vol * 32767)))
        val_r = int(max(-32767, min(32767, s_right * vol * 32767)))

        frames.extend(struct.pack('<hh', val_l, val_r))

    with wave.open(str(output_file), 'wb') as wav:
        wav.setnchannels(2)      # Stereo
        wav.setsampwidth(2)      # 16-bit
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(frames)

    print(f"✅ Deep-space ambient audio generated: {output_file} ({duration}s, 44.1kHz stereo)")


if __name__ == "__main__":
    generate_deep_space_ambience()
