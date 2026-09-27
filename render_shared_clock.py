"""Render "Shared Clock": the same 24 Earth hours on all 8 planets (20 s, 600 frames).

Every planet is shown side by side at the same apparent size and driven by one
Earth clock (00:00 → 24:00). Each one:
  - spins about its real, tilted axis (NASA obliquity; Venus upside down,
    Uranus on its side), at its real sidereal rate,
  - is lit from the Sun's direction in a Sun-fixed frame, so the day/night
    terminator sweeps across the surface exactly as fast as its local solar day,
  - carries a red prime-meridian stripe and a pole rod so spin is readable even
    on featureless worlds,
  - shows live counters: spin degrees / turns, local days passed, orbital advance.

Sizes and distances are not to scale; the Sun is off-screen to the left.

Usage (inside Blender):
    blender --background --python render_shared_clock.py -- [--res 1920 1080]
        [--samples 16] [--days 1.0] [--lang en|tr] [--frames START END] [--still FRAME]
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

try:
    import bpy
    import bmesh
    import mathutils
    from mathutils import Matrix, Vector
except ImportError:
    print("This script must run inside Blender Python.")
    sys.exit(1)

PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent.parent
OUTPUT_DIR = ROOT_DIR / "output" / "solar_system_time_journey"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from science.planet_data import PLANETS, PLANET_ORDER, TRAIL_COLORS
from science.rotation import rotation_state
from blender_build import (
    clear_scene, setup_render_settings, setup_world_starfield, build_planet_material,
    create_saturn_rings,
)

FPS = 30
TOTAL_FRAMES = 600
CLOCK_START, CLOCK_END = 31, 570          # clock runs 00:00 → end between these frames

# ── Layout (world units; camera looks straight down −Z, screen up = +Y) ────
CELL_X = (-9.0, -3.0, 3.0, 9.0)
ROW_PLANET_Y = (2.7, -3.05)
TEXT_OFFSETS = (-1.75, -2.15, -2.5, -2.82, -3.15)   # name, line1, line2, line3, bar (from planet y)
PLANET_R = 1.0
SATURN_R = 0.72
ROD_HALF = 1.28
BAR_LEN = 4.6
BAR_MAX_DAYS = 2.5
VIEW_ELEVATION_DEG = 18.0    # orbit normal leans toward camera so poles/rings read in 3/4 view
LENS_MM = 85.0
WIDE_WIDTH = 24.0
ZOOM_WIDTH = 9.0

# Camera beats: (frame, planet-or-None, width). Smoothstep between consecutive keys.
CAMERA_KEYS = [
    (1, None, WIDE_WIDTH),
    (150, None, WIDE_WIDTH),
    (190, "jupiter", ZOOM_WIDTH),
    (250, "jupiter", ZOOM_WIDTH),
    (290, "venus", ZOOM_WIDTH),
    (340, "venus", ZOOM_WIDTH),
    (380, "uranus", ZOOM_WIDTH),
    (430, "uranus", ZOOM_WIDTH),
    (480, None, WIDE_WIDTH),
    (600, None, WIDE_WIDTH),
]

STRINGS = {
    "en": {
        "title": "1 EARTH DAY · 8 WORLDS",
        "subtitle": "Same 24 hours on every planet: how far does each one turn?",
        "clock": "EARTH TIME",
        "spin": "SPIN",
        "turns": "turns",
        "retro": "retrograde",
        "local_days": "LOCAL DAYS PASSED",
        "day_is": "1 local day =",
        "hours": "h",
        "days": "Earth days",
        "orbit": "orbit",
        "foot": "Sun is to the left · red line = prime meridian · rod = spin axis · sizes & distances not to scale · NASA/JPL data",
        "names": {n: n.upper() for n in PLANET_ORDER},
    },
    "tr": {
        "title": "1 DÜNYA GÜNÜ · 8 DÜNYA",
        "subtitle": "Her gezegende aynı 24 saat: hangisi ne kadar döner?",
        "clock": "DÜNYA SAATİ",
        "spin": "DÖNÜŞ",
        "turns": "tur",
        "retro": "ters yön",
        "local_days": "GEÇEN YEREL GÜN",
        "day_is": "1 yerel gün =",
        "hours": "sa",
        "days": "Dünya günü",
        "orbit": "yörünge",
        "foot": "Güneş solda · kırmızı çizgi = başlangıç meridyeni · çubuk = dönme ekseni · boyut ve mesafeler ölçeksiz · NASA/JPL verisi",
        "names": {"mercury": "MERKÜR", "venus": "VENÜS", "earth": "DÜNYA", "mars": "MARS",
                  "jupiter": "JÜPİTER", "saturn": "SATÜRN", "uranus": "URANÜS", "neptune": "NEPTÜN"},
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════

def smoothstep(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3.0 - 2.0 * u)


def cell_of(name: str) -> tuple[float, float]:
    i = PLANET_ORDER.index(name)
    return CELL_X[i % 4], ROW_PLANET_Y[i // 4]


def emission_mat(name: str, color: tuple, strength: float = 1.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    em = nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color[:3], 1.0)
    em.inputs['Strength'].default_value = strength
    out = nodes.new('ShaderNodeOutputMaterial')
    links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def make_text(name: str, body: str, loc: tuple, size: float, color: tuple,
              align: str = 'CENTER', strength: float = 1.6, parent=None) -> bpy.types.Object:
    curve = bpy.data.curves.new(name, type='FONT')
    curve.body = body
    curve.size = size
    curve.align_x = align
    curve.align_y = 'CENTER'
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    obj.location = loc
    obj.data.materials.append(emission_mat(f"Mat_{name}", color, strength))
    return obj


def make_rect(name: str, x0: float, y: float, width: float, height: float,
              color: tuple, strength: float, z: float = 0.0) -> bpy.types.Object:
    """Flat rectangle whose origin is its LEFT edge, so scale.x grows it rightward."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    h = height / 2.0
    verts = [bm.verts.new(v) for v in ((0, -h, 0), (1, -h, 0), (1, h, 0), (0, h, 0))]
    bm.faces.new(verts)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (x0, y, z)
    obj.scale = (width, 1.0, 1.0)
    obj.data.materials.append(emission_mat(f"Mat_{name}", color, strength))
    return obj


def add_meridian_markers(mat: bpy.types.Material):
    """Overlay a bold red prime meridian + three faint meridians on a planet material.

    Longitude is measured in object space, so the markers turn with the body.
    """
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    base_in = bsdf.inputs['Base Color']
    if base_in.is_linked:
        base_src = base_in.links[0].from_socket
    else:
        rgb = nodes.new('ShaderNodeRGB')
        rgb.outputs[0].default_value = base_in.default_value
        base_src = rgb.outputs[0]

    tc = nodes.new('ShaderNodeTexCoord')
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(tc.outputs['Object'], sep.inputs['Vector'])
    lon = nodes.new('ShaderNodeMath')
    lon.operation = 'ARCTAN2'
    links.new(sep.outputs['Y'], lon.inputs[0])
    links.new(sep.outputs['X'], lon.inputs[1])

    # Bold prime meridian: |lon| < w
    absn = nodes.new('ShaderNodeMath')
    absn.operation = 'ABSOLUTE'
    links.new(lon.outputs[0], absn.inputs[0])
    bold = nodes.new('ShaderNodeMath')
    bold.operation = 'LESS_THAN'
    bold.inputs[1].default_value = 0.075
    links.new(absn.outputs[0], bold.inputs[0])

    # Faint meridians every 90°: cos(4·lon) > threshold
    mul = nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 4.0
    links.new(lon.outputs[0], mul.inputs[0])
    cos = nodes.new('ShaderNodeMath')
    cos.operation = 'COSINE'
    links.new(mul.outputs[0], cos.inputs[0])
    faint = nodes.new('ShaderNodeMath')
    faint.operation = 'GREATER_THAN'
    faint.inputs[1].default_value = 0.992
    links.new(cos.outputs[0], faint.inputs[0])
    faint_amt = nodes.new('ShaderNodeMath')
    faint_amt.operation = 'MULTIPLY'
    faint_amt.inputs[1].default_value = 0.45
    links.new(faint.outputs[0], faint_amt.inputs[0])

    mix_faint = nodes.new('ShaderNodeMix')
    mix_faint.data_type = 'RGBA'
    links.new(faint_amt.outputs[0], mix_faint.inputs['Factor'])
    links.new(base_src, mix_faint.inputs[6])
    mix_faint.inputs[7].default_value = (0.95, 0.95, 0.95, 1.0)

    mix_bold = nodes.new('ShaderNodeMix')
    mix_bold.data_type = 'RGBA'
    links.new(bold.outputs[0], mix_bold.inputs['Factor'])
    links.new(mix_faint.outputs[2], mix_bold.inputs[6])
    mix_bold.inputs[7].default_value = (0.95, 0.12, 0.06, 1.0)

    links.new(mix_bold.outputs[2], base_in)


def attitude_matrix(cell: tuple[float, float], orbit_deg: float, tilt_deg: float) -> Matrix:
    """World matrix of a planet's tilt frame (local Z = spin axis / angular momentum).

    Physics frame is Sun-fixed: orbit normal = +z, Sun toward −x. Its rotation by
    −orbit_deg about the normal turns sidereal spin into Sun-relative spin, so the
    terminator moves at the local solar-day rate. The axis leans in the screen plane,
    away from the Sun. Physics→world: x→X, y→−Z (into screen), z→Y (screen up),
    then tipped toward the camera by VIEW_ELEVATION_DEG.
    """
    to_world = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).to_4x4()
    view = Matrix.Rotation(math.radians(VIEW_ELEVATION_DEG), 4, 'X')
    orbit = Matrix.Rotation(math.radians(-orbit_deg), 4, 'Z')
    tilt = Matrix.Rotation(math.radians(tilt_deg), 4, 'Y')
    return Matrix.Translation((cell[0], cell[1], 0.0)) @ view @ to_world @ orbit @ tilt


def fmt_hours(h: float) -> str:
    hh = int(h)
    mm = int(round((h - hh) * 60.0))
    if mm == 60:
        hh, mm = hh + 1, 0
    return f"{hh:02d}:{mm:02d}"


# ═══════════════════════════════════════════════════════════════════════
#  SCENE
# ═══════════════════════════════════════════════════════════════════════

def build_scene(res: tuple[int, int], samples: int, lang: str):
    S = STRINGS[lang]
    clear_scene()
    setup_render_settings(res, samples)
    setup_world_starfield()
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, TOTAL_FRAMES

    # Sunlight from the left (travels +X) + faint camera fill so night sides stay legible
    sun_data = bpy.data.lights.new("Sunlight", type='SUN')
    sun_data.energy = 4.2
    sun_data.color = (1.0, 0.96, 0.90)
    sun_data.angle = math.radians(0.6)
    sun = bpy.data.objects.new("Sunlight", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (0.0, math.radians(-90.0), 0.0)

    fill_data = bpy.data.lights.new("NightFill", type='SUN')
    fill_data.energy = 0.10
    fill_data.color = (0.55, 0.65, 1.0)
    fill = bpy.data.objects.new("NightFill", fill_data)
    bpy.context.collection.objects.link(fill)

    # Camera
    cam_data = bpy.data.cameras.new("SharedClockCam")
    cam_data.lens = LENS_MM
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.01
    cam_data.clip_end = 500.0
    cam = bpy.data.objects.new("SharedClockCam", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    # Screen-space HUD (parented to camera at local z = −1)
    half_w = 0.5 * 36.0 / LENS_MM
    half_h = half_w * res[1] / res[0]
    mx = half_w * 0.94
    hud = {}
    hud["title"] = make_text("HUD_Title", S["title"], (-mx, half_h * 0.86, -1), 0.0135,
                             (1, 1, 1), 'LEFT', 1.8, cam)
    hud["subtitle"] = make_text("HUD_Subtitle", S["subtitle"], (-mx, half_h * 0.76, -1), 0.0075,
                                (0.72, 0.78, 0.86), 'LEFT', 1.4, cam)
    hud["clock_lbl"] = make_text("HUD_ClockLbl", S["clock"], (mx, half_h * 0.88, -1), 0.0072,
                                 (1.0, 0.82, 0.35), 'RIGHT', 1.6, cam)
    hud["clock"] = make_text("HUD_Clock", "00:00", (mx, half_h * 0.76, -1), 0.020,
                             (1.0, 0.86, 0.40), 'RIGHT', 2.0, cam)
    hud["foot"] = make_text("HUD_Foot", S["foot"], (0, -half_h * 0.91, -1), 0.0058,
                            (0.55, 0.60, 0.68), 'CENTER', 1.2, cam)
    bar_w = half_w * 0.34
    for o in (make_rect("HUD_ClockBarBg", mx - bar_w, half_h * 0.68, bar_w, 0.0016,
                        (0.25, 0.25, 0.28), 1.0),
              make_rect("HUD_ClockBar", mx - bar_w, half_h * 0.68, bar_w, 0.0016,
                        (1.0, 0.82, 0.35), 2.0)):
        o.parent = cam
        o.location.z = -1.0 + 0.0001 * (o.name == "HUD_ClockBar")
    clock_bar = bpy.data.objects["HUD_ClockBar"]
    clock_bar_w = bar_w

    # Planets
    rigs = {}
    for name in PLANET_ORDER:
        p = PLANETS[name]
        cx, cy = cell_of(name)
        r = SATURN_R if name == "saturn" else PLANET_R

        tilt_empty = bpy.data.objects.new(f"Tilt_{name}", None)
        bpy.context.collection.objects.link(tilt_empty)

        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=r)
        body = bpy.context.active_object
        body.name = f"Body_{name}"
        bpy.ops.object.shade_smooth()
        mat = build_planet_material(name)
        add_meridian_markers(mat)
        body.data.materials.append(mat)
        body.parent = tilt_empty

        # Spin-axis rod + north (angular-momentum) cap
        bpy.ops.mesh.primitive_cylinder_add(radius=0.022, depth=2 * ROD_HALF * r, vertices=16)
        rod = bpy.context.active_object
        rod.name = f"Axis_{name}"
        rod.data.materials.append(emission_mat(f"AxisMat_{name}", (0.85, 0.88, 0.95), 0.9))
        rod.parent = tilt_empty
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, location=(0, 0, ROD_HALF * r))
        cap = bpy.context.active_object
        cap.name = f"NorthCap_{name}"
        cap.data.materials.append(emission_mat(f"CapMat_{name}", (0.30, 1.0, 0.65), 2.5))
        cap.parent = tilt_empty

        if name == "saturn":
            ring = create_saturn_rings(body, r)
            ring.parent = tilt_empty          # rings share the equator plane, don't spin with the body
            ring.rotation_euler = (0.0, 0.0, 0.0)

        color = TRAIL_COLORS[name]
        base_y = cy
        tx = [make_text(f"T{i}_{name}", "", (cx, base_y + off, 0.0), sz, col, 'CENTER', st)
              for i, (off, sz, col, st) in enumerate((
                  (TEXT_OFFSETS[0], 0.36, color, 2.2),
                  (TEXT_OFFSETS[1], 0.22, (0.92, 0.94, 0.97), 1.5),
                  (TEXT_OFFSETS[2], 0.22, (1.0, 0.84, 0.40), 1.7),
                  (TEXT_OFFSETS[3], 0.17, (0.60, 0.65, 0.72), 1.3),
              ))]
        tx[0].data.body = S["names"][name]

        bar_x0 = cx - BAR_LEN / 2
        bar_y = base_y + TEXT_OFFSETS[4]
        make_rect(f"BarBg_{name}", bar_x0, bar_y, BAR_LEN, 0.07, (0.22, 0.23, 0.26), 1.0)
        fill_bar = make_rect(f"Bar_{name}", bar_x0, bar_y, 0.0001, 0.07, color, 2.4, z=0.001)
        for d in (1, 2):
            make_rect(f"Tick{d}_{name}", bar_x0 + BAR_LEN * d / BAR_MAX_DAYS - 0.012, bar_y,
                      0.024, 0.20, (0.75, 0.78, 0.85), 1.2, z=0.002)

        rigs[name] = {"tilt": tilt_empty, "body": body, "cell": (cx, cy),
                      "tilt_deg": p.axial_tilt_deg, "texts": tx, "bar": fill_bar}

    return cam, hud, clock_bar, clock_bar_w, rigs


def camera_state(f: int) -> tuple[float, float, float]:
    """(center_x, center_y, visible_width) for frame f."""
    def target(key):
        _, planet, width = key
        if planet is None:
            return 0.0, 0.0, width
        cx, cy = cell_of(planet)
        return cx, cy - 1.15, width

    for a, b in zip(CAMERA_KEYS, CAMERA_KEYS[1:]):
        if a[0] <= f <= b[0]:
            u = smoothstep((f - a[0]) / max(1, b[0] - a[0]))
            ta, tb = target(a), target(b)
            return tuple(ta[i] + (tb[i] - ta[i]) * u for i in range(3))
    return target(CAMERA_KEYS[-1])


def update_frame(f: int, days_total: float, lang: str, cam, hud, clock_bar, clock_bar_w, rigs):
    S = STRINGS[lang]
    u = min(1.0, max(0.0, (f - CLOCK_START) / (CLOCK_END - CLOCK_START)))
    days = u * days_total

    # Camera
    cx, cy, width = camera_state(f)
    dist = width * LENS_MM / 36.0
    cam.location = (cx, cy, dist)
    cam.rotation_euler = (0.0, 0.0, 0.0)

    # Global clock
    hud["clock"].data.body = fmt_hours(days * 24.0) if days_total <= 1.0 else f"{days:.2f} d"
    clock_bar.scale.x = max(1e-4, clock_bar_w * u)

    for name, rig in rigs.items():
        rs = rotation_state(name, days)
        rig["tilt"].matrix_world = attitude_matrix(rig["cell"], rs.orbit_deg, rig["tilt_deg"])
        # Spin about the tilted axis (tilt > 90° already encodes retrograde sense)
        rig["body"].rotation_euler = (0.0, 0.0, math.radians(abs(rs.spin_deg)))

        retro = f"  ({S['retro']})" if PLANETS[name].rotation_period_days < 0 else ""
        rig["texts"][1].data.body = (f"{S['spin']}  {abs(rs.spin_deg):.1f}°  ·  "
                                     f"{rs.spin_turns:.2f} {S['turns']}{retro}")
        rig["texts"][2].data.body = f"{S['local_days']}  {rs.local_days:.3f}"
        sol = rs.solar_day_days
        sol_txt = (f"{sol * 24.0:.1f} {S['hours']}" if sol < 2.0
                   else f"{sol:.0f} {S['days']}")
        rig["texts"][3].data.body = f"{S['day_is']} {sol_txt}  ·  {S['orbit']} +{rs.orbit_deg:.3f}°"
        rig["bar"].scale.x = max(1e-4, BAR_LEN * min(rs.local_days, BAR_MAX_DAYS) / BAR_MAX_DAYS)


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", nargs=2, type=int, default=(1920, 1080))
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--days", type=float, default=1.0)
    ap.add_argument("--lang", choices=sorted(STRINGS), default="en")
    ap.add_argument("--frames", nargs=2, type=int)
    ap.add_argument("--still", type=int, help="Render a single test frame and exit")
    ap.add_argument("--name", default="solar_1_day_shared_clock_20s")
    args = ap.parse_args(argv)

    frames_dir = OUTPUT_DIR / f"{args.name}_{args.lang}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    state = build_scene(tuple(args.res), args.samples, args.lang)
    scene = bpy.context.scene

    if args.still:
        update_frame(args.still, args.days, args.lang, *state)
        out = OUTPUT_DIR / f"{args.name}_{args.lang}_still_{args.still:04d}.png"
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        print(f"Still: {out}")
        return

    f0, f1 = args.frames if args.frames else (1, TOTAL_FRAMES)
    for f in range(f0, f1 + 1):
        out = frames_dir / f"frame_{f:06d}.png"
        if out.exists() and out.stat().st_size > 0:
            continue
        scene.frame_set(f)
        update_frame(f, args.days, args.lang, *state)
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        if f % 30 == 0:
            print(f"  frame {f}/{TOTAL_FRAMES}")

    if len(list(frames_dir.glob("frame_*.png"))) < TOTAL_FRAMES:
        print("Partial range rendered; skipping encode.")
        return

    final_dir = OUTPUT_DIR / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    mp4 = final_dir / f"{args.name}_{args.lang}.mp4"
    audio = PROJECT_DIR / "assets" / "audio" / "deep_space_ambience.wav"
    cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(frames_dir / "frame_%06d.png")]
    if audio.exists():
        cmd += ["-stream_loop", "-1", "-i", str(audio), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    print(f"✅ {mp4}")


if __name__ == "__main__":
    main()
