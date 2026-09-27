"""Output locations and FFmpeg encoding shared by the render scripts (no bpy needed)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
AUDIO_WAV = PROJECT_DIR / "assets" / "audio" / "deep_space_ambience.wav"


def output_dir() -> Path:
    """`<workspace>/output/solar_system_time_journey` inside the 3d-blender-youtube
    workspace (module lives in `projects/`), else `./output` next to this file."""
    if PROJECT_DIR.parent.name == "projects":
        return PROJECT_DIR.parent.parent / "output" / "solar_system_time_journey"
    return PROJECT_DIR / "output"


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # optional fallback
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError("ffmpeg not found. Install it (e.g. `brew install ffmpeg`).")


def encode_frames(frames_dir: Path, mp4: Path, fps: int = 30, start_number: int = 0,
                  audio: Path | None = AUDIO_WAV) -> Path:
    """Encode `frame_%06d.png` into an H.264 master, looping the ambient audio under it."""
    mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_exe(), "-y", "-framerate", str(fps), "-start_number", str(start_number),
           "-i", str(frames_dir / "frame_%06d.png")]
    if audio is not None and audio.exists():
        cmd += ["-stream_loop", "-1", "-i", str(audio), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    return mp4
