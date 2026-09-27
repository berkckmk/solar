"""Background music for every render (FFmpeg only; no bpy, no numpy).

The default score is assets/audio/music/solar_calm_10min.m4a (original, made by
tools/make_music.py). Set SOLAR_MUSIC=/path/to/track to use your own.

  - long videos (> 2 min) start the music at its beginning,
  - tests and 20 s samples start at a random point of the track (printed, so a
    take can be repeated with SOLAR_MUSIC_OFFSET=<seconds>),
  - a video longer than the track continues with a 6 s cross-fade into its start,
  - soft fade in / out, loudness measured (EBU R128) and set to one level.
"""

from __future__ import annotations

import os
import random
import re
import subprocess
from pathlib import Path

from render_io import ffmpeg_exe

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_MUSIC = PROJECT_DIR / "assets" / "audio" / "music" / "solar_calm_10min.m4a"
RATE = 44_100
LONG_VIDEO_S = 120.0
TARGET_LUFS = -17.0
PEAK_DBFS = -1.5
XFADE_S = 6.0


def music_path() -> Path | None:
    p = Path(os.environ.get("SOLAR_MUSIC", DEFAULT_MUSIC)).expanduser()
    return p if p.exists() else None


def media_duration(path: Path) -> float:
    err = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", err)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def loudness(path: Path):
    err = subprocess.run([ffmpeg_exe(), "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    return (float(i[-1]) if i else None), (float(p[-1]) if p else None)


def choose_offset(duration: float, track: float, offset="auto") -> float:
    """'auto': start of the track for long videos, a random point for short ones."""
    env = os.environ.get("SOLAR_MUSIC_OFFSET")
    if env is not None:
        return max(0.0, float(env)) % max(track, 1.0)
    if offset == "auto":
        offset = "start" if duration > LONG_VIDEO_S else "random"
    if offset == "start":
        return 0.0
    if offset == "random":
        room = track - duration - 1.0
        return round(random.uniform(0.0, room), 1) if room > 0 else 0.0
    return float(offset)


def build(out_wav: Path, duration: float, offset="auto", target_lufs: float = TARGET_LUFS,
          fade_in: float = 2.0, fade_out: float = 3.0, quiet: bool = False):
    """Write `duration` seconds of music to `out_wav` (stereo 44.1 kHz) at `target_lufs`.
    Returns (offset used, LUFS, peak) or None when no music file is available."""
    src = music_path()
    if src is None:
        return None
    ff = ffmpeg_exe()
    track = media_duration(src)
    off = choose_offset(duration, track, offset)
    first = min(duration, track - off)
    raw = out_wav.with_name(out_wav.stem + ".raw.wav")
    if first >= duration - 1e-3:                                   # one piece of the track
        graph = f"[0:a]atrim={off}:{off + duration},asetpts=PTS-STARTPTS[m]"
    else:                                                          # wrap round with a cross-fade
        rest = duration - first + XFADE_S
        graph = (f"[0:a]atrim={off}:{track},asetpts=PTS-STARTPTS[a];"
                 f"[1:a]atrim=0:{rest},asetpts=PTS-STARTPTS[b];"
                 f"[a][b]acrossfade=d={XFADE_S}:c1=qsin:c2=qsin[m]")
    graph += (f";[m]aformat=sample_rates={RATE}:channel_layouts=stereo,atrim=0:{duration},"
              f"afade=t=in:st=0:d={fade_in}:curve=qsin,"
              f"afade=t=out:st={max(0.0, duration - fade_out)}:d={fade_out}:curve=qsin[out]")
    inputs = ["-i", str(src)] + (["-i", str(src)] if first < duration - 1e-3 else [])
    subprocess.run([ff, "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[out]",
                    "-c:a", "pcm_s16le", str(raw)], check=True)
    lufs, peak = loudness(raw)
    gain = 0.0
    if lufs is not None:
        gain = target_lufs - lufs
        if peak is not None:
            gain = min(gain, PEAK_DBFS - peak)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(raw), "-af", f"volume={gain:.2f}dB",
                    "-c:a", "pcm_s16le", str(out_wav)], check=True)
    raw.unlink()
    if not quiet:
        m, s = divmod(off, 60)
        print(f"Music: {src.name} from {int(m)}:{s:04.1f} for {duration:.1f} s "
              f"(repeat with SOLAR_MUSIC_OFFSET={off:g})")
    return (off,) + loudness(out_wav)


def prepare(duration: float, next_to: Path, offset="auto") -> Path | None:
    """Build the music for a video next to its output file; None if no track is available.
    The caller muxes it in and may delete it afterwards."""
    out = Path(next_to).with_suffix(".music.wav")
    return out if build(out, duration, offset) else None
