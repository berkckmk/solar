"""Master CLI generator and pipeline coordinator for solar_system_time_journey.

Commands:
    python3 generate.py --stills       # Render 6 proof stills
    python3 generate.py --proof-clip   # Render 25s proof video
    python3 generate.py --validate     # Run astronomical validation checks
    python3 generate.py --final        # Run resumable 9:25 1440p final production render
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent.parent
OUTPUT_DIR = ROOT_DIR / "output" / "solar_system_time_journey"
PLAN_FILE = OUTPUT_DIR / "plan.json"

BLENDER_CANDIDATES = [
    Path("/Applications/Blender.app/Contents/MacOS/Blender"),
    Path(shutil.which("blender") or "/dev/null"),
]


def find_blender() -> str:
    """Locate the Blender binary executable."""
    for b in BLENDER_CANDIDATES:
        if b.exists() and os.access(b, os.X_OK):
            return str(b)
    raise RuntimeError("Blender executable not found. Ensure Blender is installed.")


def run_blender_script(args: list[str]) -> int:
    """Invoke blender_build.py inside Blender's background Python runtime."""
    blender_bin = find_blender()
    script = PROJECT_DIR / "blender_build.py"
    cmd = [blender_bin, "--background", "--python", str(script), "--"] + args
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=True).returncode


def validate_science():
    """Run mathematical and astronomical validation checks."""
    validation_script = PROJECT_DIR / "science" / "validation.py"
    subprocess.run([sys.executable, str(validation_script)], check=True)


def run_final_pipeline(frame_range: tuple[int, int] | None = None):
    """Run resumable frame render pipeline and final FFmpeg assembly."""
    print("==================================================")
    print(" STARTING RESUMABLE 9:25 1440P FINAL PRODUCTION")
    print("==================================================")
    # Ensure plan is loaded
    if not PLAN_FILE.exists():
        # Generate plan using repository run.py
        subprocess.run([sys.executable, str(ROOT_DIR / "run.py"), "plan", "solar_system_time_journey"], check=True)

    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    total_frames = plan.get("total_frames", 16950)
    print(f"Target duration: {plan.get('total_seconds', 565.0)}s ({total_frames} frames @ 30 FPS)")

    frames_dir = OUTPUT_DIR / "final_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Check how many frames already exist
    existing_frames = len(list(frames_dir.glob("frame_*.png")))
    print(f"Existing frames in cache: {existing_frames} / {total_frames}")

    if existing_frames < total_frames or frame_range is not None:
        print("\nRendering missing frames in Blender...")
        blender_args = ["--render-final"]
        if frame_range is not None:
            blender_args.extend(["--range", str(frame_range[0]), str(frame_range[1])])
        run_blender_script(blender_args)
    else:
        print("\nAll frames already rendered in cache. Proceeding directly to encode.")

    # FFmpeg encode to final master MP4
    final_dir = OUTPUT_DIR / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    master_mp4 = final_dir / "solar_system_1_30_365_days_1440p.mp4"

    audio_file = PROJECT_DIR / "assets" / "audio" / "deep_space_ambience.wav"
    has_audio = audio_file.exists()

    cmd = [
        "ffmpeg", "-y",
        "-framerate", "30",
        "-i", str(frames_dir / "frame_%06d.png"),
    ]

    if has_audio:
        cmd.extend([
            "-stream_loop", "-1",
            "-i", str(audio_file),
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(master_mp4),
    ])

    print(f"\nEncoding 1440p master video: {master_mp4}")
    subprocess.run(cmd, check=True)
    print(f"\n✅ 9:25 Master Video Render Complete: {master_mp4}")


def run_day1_loop():
    """Run dedicated 20-second 1-Day Earth 24h diurnal & orbital loop render."""
    blender_bin = find_blender()
    script = PROJECT_DIR / "render_1_day_loop.py"
    subprocess.run([blender_bin, "--background", "--python", str(script)], check=True)


def run_day1_speedup():
    """Extract Act 1 (1 Earth Day) and speed it up to 20 seconds."""
    master_mp4 = OUTPUT_DIR / "final" / "solar_system_1_30_365_days_1440p.mp4"
    audio_wav = PROJECT_DIR / "assets" / "audio" / "deep_space_ambience.wav"
    out_mp4 = OUTPUT_DIR / "final" / "solar_1_day_act_speedup_20s.mp4"
    if not master_mp4.exists():
        print(f"ERROR: Master video not found at {master_mp4}")
        return
    cmd = [
        "ffmpeg", "-y",
        "-ss", "25.0", "-to", "183.0",
        "-i", str(master_mp4),
        "-i", str(audio_wav),
        "-filter_complex", "[0:v]setpts=20.0/158.0*PTS,fps=30[v]",
        "-map", "[v]", "-map", "1:a",
        "-t", "20.0",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)
    print(f"✅ Generated: {out_mp4}")


def main():
    parser = argparse.ArgumentParser(description="Solar System Time Journey CLI")
    parser.add_argument("--stills", action="store_true", help="Render 6 proof stills")
    parser.add_argument("--proof-clip", action="store_true", help="Render 25s proof video clip")
    parser.add_argument("--validate", action="store_true", help="Run astronomical validation checks")
    parser.add_argument("--final", action="store_true", help="Run 9:25 final production render")
    parser.add_argument("--range", nargs=2, type=int, metavar=("START", "END"), help="Optional frame range for render")
    parser.add_argument("--day1-loop", action="store_true", help="Render 20s 1-Day Earth 24h loop animation")
    parser.add_argument("--day1-speedup", action="store_true", help="Extract 20s 1-Day Act speedup from master")
    args = parser.parse_args()

    if args.validate:
        validate_science()
    elif args.stills:
        run_blender_script(["--proof-stills"])
    elif args.proof_clip:
        run_blender_script(["--proof-clip"])
    elif args.final:
        run_final_pipeline(frame_range=tuple(args.range) if args.range else None)
    elif args.day1_loop:
        run_day1_loop()
    elif args.day1_speedup:
        run_day1_speedup()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

