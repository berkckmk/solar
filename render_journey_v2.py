"""Journey v2, 3D pass (run inside Blender). Renders stars, Sun and planets only;
the 2D information layer is drawn by overlay_v2.py from the same timeline.

    blender --background --python render_journey_v2.py -- [--res 1920 1080]
        [--samples 16] [--frames START END] [--stills SECONDS ...] [--name sample_mercury_30]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import bpy

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from render_io import output_dir
from journey_v2.timeline import Sample, FPS
from journey_v2.scene3d import Scene3D


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", nargs=2, type=int, default=(1920, 1080))
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--frames", nargs=2, type=int, metavar=("START", "END"))
    ap.add_argument("--stills", nargs="+", type=float, metavar="SECONDS")
    ap.add_argument("--name", default="sample_mercury_30")
    ap.add_argument("--engine", choices=("EEVEE", "CYCLES"), default="EEVEE",
                    help="CYCLES is faster on machines without a GPU (the scene is emission-only)")
    args = ap.parse_args(argv)

    sample = Sample(aspect=args.res[0] / args.res[1])
    root = output_dir() / "v2" / args.name
    frames_dir = root / "3d"
    frames_dir.mkdir(parents=True, exist_ok=True)
    scene = Scene3D(sample, tuple(args.res), args.samples)
    rs = bpy.context.scene
    if args.engine == "CYCLES":
        rs.render.engine = 'CYCLES'
        rs.cycles.samples = args.samples
        rs.cycles.use_denoising = False
        rs.cycles.max_bounces = 0
        rs.render.film_transparent = False

    if args.stills:
        todo = sorted({min(sample.frames - 1, round(s * FPS)) for s in args.stills})
    else:
        f0, f1 = args.frames if args.frames else (0, sample.frames - 1)
        todo = range(f0, f1 + 1)

    timings = []
    for f in todo:
        path = frames_dir / f"frame_{f:06d}.png"
        if path.exists() and path.stat().st_size > 0 and not args.stills:
            continue
        t0 = time.perf_counter()
        scene.update(f)
        rs.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        timings.append((f, time.perf_counter() - t0))
        if f % 30 == 0:
            print(f"  3d frame {f}/{sample.frames - 1}  {timings[-1][1]:.2f}s")

    if timings:
        log = root / "render_times_3d.json"
        prev = json.loads(log.read_text()) if log.exists() else {}
        prev.update({str(f): round(dt, 3) for f, dt in timings})
        log.write_text(json.dumps(prev, indent=1))
        avg = sum(dt for _, dt in timings) / len(timings)
        print(f"3D: {len(timings)} frames, {avg:.2f} s/frame at {args.res[0]}x{args.res[1]}, "
              f"{args.samples} samples")


if __name__ == "__main__":
    main()
