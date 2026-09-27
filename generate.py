"""Master CLI generator and pipeline coordinator for solar_system_time_journey.

Commands:
    python3 generate.py --stills       # Render 6 proof stills
    python3 generate.py --proof-clip   # Render 25s proof video
    python3 generate.py --validate     # Run astronomical validation checks
    python3 generate.py --final        # Run resumable 9:25 1440p final production render

Long versions (continuous clock, zoom into every planet and back out to the system):
    python3 generate.py --journey --lang tr             # Format A: 9:25 system journey, 2560x1440
    python3 generate.py --shared-clock-long --lang tr   # Format B: 9:09 eight-planet shared clock, 1920x1080
    Add --still 2400 7200 to render test frames only, --test 5850 for a 20 s test clip,
    --range START END for a range,
    python3 generate.py --journey-v2-sample --lang tr    # v2 layout: 20 s sample (Mercury, 30 days)
    --res W H / --samples N to override quality.
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


def run_blender_file(script_name: str, args: list[str]) -> int:
    """Run one of the render scripts inside Blender's background Python runtime."""
    cmd = [find_blender(), "--background", "--python", str(PROJECT_DIR / script_name), "--"] + args
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=True).returncode


def long_render_args(args) -> list[str]:
    out = ["--lang", args.lang]
    if args.res:
        out += ["--res", *map(str, args.res)]
    if args.samples:
        out += ["--samples", str(args.samples)]
    if args.still:
        out += ["--still", *map(str, args.still)]
    if args.range:
        out += ["--frames", *map(str, args.range)]
    if args.test is not None:
        out += ["--test", str(args.test)]
    return out


def _pillow_python() -> list[str] | None:
    """A Python that has Pillow: this one, else Blender's own interpreter."""
    if subprocess.run([sys.executable, "-c", "import PIL"], capture_output=True).returncode == 0:
        return [sys.executable]
    try:
        blender = find_blender()
    except RuntimeError:
        return None
    ok = subprocess.run([blender, "--background", "--python-exit-code", "1", "--python-expr", "import PIL"],
                        capture_output=True).returncode == 0
    return [blender, "--background", "--python"] if ok else None


def run_journey_v2_sample(args):
    """20 s v2 sample: 3D pass (Blender) + 2D layer (Pillow) + sound, composed by FFmpeg."""
    sys.path.insert(0, str(PROJECT_DIR))
    from render_io import output_dir, ffmpeg_exe
    from journey_v2.timeline import Sample
    from journey_v2 import audio

    res = tuple(args.res) if args.res else (1920, 1080)
    name = f"sample_mercury_30_{res[1]}p"
    root = output_dir() / "v2" / name
    py = _pillow_python()
    if py is None:
        print("Pillow is needed for the text layer. Install it once, then run again:\n"
              f"  {sys.executable} -m pip install --user pillow")
        sys.exit(2)

    if not args.skip_3d:
        run_blender_file("render_journey_v2.py", ["--res", str(res[0]), str(res[1]),
                                                  "--samples", str(args.samples or 16), "--name", name,
                                                  "--engine", args.engine])
    ov_args = ["--res", str(res[0]), str(res[1]), "--lang", args.lang, "--name", name]
    if args.debug:
        ov_args.append("--debug")
    if py[0] == sys.executable:
        subprocess.run(py + [str(PROJECT_DIR / "overlay_v2.py")] + ov_args, check=True)
    else:
        subprocess.run(py + [str(PROJECT_DIR / "overlay_v2.py"), "--"] + ov_args, check=True)

    wav = root / "audio.wav"
    lufs, peak = audio.build(Sample(aspect=res[0] / res[1]), wav, ffmpeg_exe())
    print(f"Audio: {lufs} LUFS, peak {peak} dBFS")

    sub = f"overlay_{args.lang}" + ("_debug" if args.debug else "")
    final = output_dir() / "final" / f"journey_v2_sample_{args.lang}_{res[1]}p{'_debug' if args.debug else ''}.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg_exe(), "-y", "-framerate", "30", "-i", str(root / "3d" / "frame_%06d.png"),
                    "-framerate", "30", "-i", str(root / sub / "frame_%06d.png"), "-i", str(wav),
                    "-filter_complex", "[0:v][1:v]overlay=format=auto,format=yuv420p[v]",
                    "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(final)],
                   check=True)
    print(f"✅ {final}")


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

    from soundtrack import prepare
    n_frames = len(list(frames_dir.glob("frame_*.png")))
    audio_file = prepare(n_frames / 30.0, master_mp4) or PROJECT_DIR / "assets" / "audio" / "deep_space_ambience.wav"
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
    if audio_file.name.endswith(".music.wav"):
        audio_file.unlink(missing_ok=True)
    print(f"\n✅ 9:25 Master Video Render Complete: {master_mp4}")


def run_day1_loop():
    """Run dedicated 20-second 1-Day Earth 24h diurnal & orbital loop render."""
    blender_bin = find_blender()
    script = PROJECT_DIR / "render_1_day_loop.py"
    subprocess.run([blender_bin, "--background", "--python", str(script)], check=True)


def run_day1_speedup():
    """Extract Act 1 (1 Earth Day) and speed it up to 20 seconds."""
    master_mp4 = OUTPUT_DIR / "final" / "solar_system_1_30_365_days_1440p.mp4"
    out_mp4 = OUTPUT_DIR / "final" / "solar_1_day_act_speedup_20s.mp4"
    if not master_mp4.exists():
        print(f"ERROR: Master video not found at {master_mp4}")
        return
    from soundtrack import prepare
    audio_wav = prepare(20.0, out_mp4) or PROJECT_DIR / "assets" / "audio" / "deep_space_ambience.wav"
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
    if audio_wav.name.endswith(".music.wav"):
        audio_wav.unlink(missing_ok=True)
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
    parser.add_argument("--journey", action="store_true",
                        help="Render the continuous 9:25 system journey (zoom in/out of every planet)")
    parser.add_argument("--shared-clock-long", action="store_true",
                        help="Render the 9-minute eight-planet shared clock (1 / 30 / 365 days)")
    parser.add_argument("--lang", choices=("en", "tr"), default="en", help="On-screen language")
    parser.add_argument("--res", nargs=2, type=int, metavar=("W", "H"), help="Override resolution")
    parser.add_argument("--samples", type=int, help="Override EEVEE samples")
    parser.add_argument("--still", nargs="+", type=int, metavar="FRAME", help="Render test frames only")
    parser.add_argument("--test", type=int, metavar="START",
                        help="Render a fresh 20 s test clip starting at this frame and encode it")
    parser.add_argument("--journey-v2-sample", action="store_true",
                        help="Render the 20 s v2 sample (new layout, 2D text layer, sound)")
    parser.add_argument("--skip-3d", action="store_true", help="v2: reuse rendered 3D frames")
    parser.add_argument("--debug", action="store_true", help="v2: draw layout boxes (development)")
    parser.add_argument("--engine", choices=("EEVEE", "CYCLES"), default="EEVEE",
                        help="v2 3D pass engine (CYCLES is faster on machines without a GPU)")
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
    elif args.journey_v2_sample:
        run_journey_v2_sample(args)
    elif args.journey:
        run_blender_file("render_system_journey.py", long_render_args(args))
    elif args.shared_clock_long:
        run_blender_file("render_shared_clock.py", ["--long"] + long_render_args(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

