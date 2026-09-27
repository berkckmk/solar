"""Journey v2, 2D information layer (plain Python + Pillow; no Blender needed).

    python3 overlay_v2.py [--res 1920 1080] [--lang tr] [--debug]
        [--frames START END] [--stills SECONDS ...] [--name sample_mercury_30]

Writes transparent PNGs next to the 3D frames plus a layout QA report
(collisions between text, labels, the Sun and the selected planet, per frame).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

try:
    from PIL import Image  # noqa: F401
except ImportError:
    print("Pillow is missing. Install it once with:\n"
          f"  {sys.executable} -m pip install pillow")
    sys.exit(2)

from render_io import output_dir
from journey_v2.timeline import Sample, FPS
from journey_v2.overlay import Overlay


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", nargs=2, type=int, default=(1920, 1080))
    ap.add_argument("--lang", choices=("tr", "en"), default="tr")
    ap.add_argument("--debug", action="store_true", help="Draw layout boxes (development only)")
    ap.add_argument("--frames", nargs=2, type=int, metavar=("START", "END"))
    ap.add_argument("--stills", nargs="+", type=float, metavar="SECONDS")
    ap.add_argument("--name", default="sample_mercury_30")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = ap.parse_args(argv)

    sample = Sample(aspect=args.res[0] / args.res[1])
    ov = Overlay(sample, tuple(args.res), args.lang, args.debug)
    root = output_dir() / "v2" / args.name
    sub = f"overlay_{args.lang}" + ("_debug" if args.debug else "")
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    if args.stills:
        frames = sorted({min(sample.frames - 1, round(s * FPS)) for s in args.stills})
        sequential = False
    else:
        f0, f1 = args.frames if args.frames else (0, sample.frames - 1)
        frames = range(f0, f1 + 1)
        sequential = True

    issues = Counter()
    where = {}
    sun_track = []
    t0 = time.perf_counter()
    for f in frames:
        img, qa = ov.render(f, sequential=sequential)
        img.save(out / f"frame_{f:06d}.png", compress_level=1)
        for kind, what in qa["issues"]:
            issues[(kind, what)] += 1
            where.setdefault(f"{kind}:{what}", []).append(f)
        sun_track.append((f, qa["sun_uv"]))
    dt = (time.perf_counter() - t0) / max(1, len(frames))

    # Sun steadiness: it must not move at all while the camera holds, and move
    # smoothly (small change of step, no jumps) while the camera travels
    def px(a, b):
        return ((b[0] - a[0]) * args.res[0], (b[1] - a[1]) * args.res[1])

    def moving(f):
        return 0.0 < sample.focus_weight(f / FPS) < 1.0 or 0.0 < sample.focus_weight((f - 1) / FPS) < 1.0

    hold_step, move_step, jerk = 0.0, 0.0, 0.0
    for (fa, a), (fb, b), (fc, c) in zip(sun_track, sun_track[1:], sun_track[2:]):
        if not (fb == fa + 1 and fc == fb + 1):
            continue
        s1, s2 = px(a, b), px(b, c)
        step = abs(s2[0]) + abs(s2[1])
        if moving(fc):
            move_step = max(move_step, step)
            jerk = max(jerk, abs(s2[0] - s1[0]) + abs(s2[1] - s1[1]))
        else:
            hold_step = max(hold_step, step)
    report = {
        "frames": len(frames), "seconds_per_frame": round(dt, 3),
        "issues": {f"{k}:{w}": n for (k, w), n in issues.items()},
        "issue_frames": {k: [v[0], v[-1], len(v)] for k, v in where.items()},
        "sun_max_step_px_while_camera_holds": round(hold_step, 3),
        "sun_max_step_px_during_camera_moves": round(move_step, 2),
        "sun_max_step_change_px_during_camera_moves": round(jerk, 2),
    }
    (root / f"qa_{sub}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
