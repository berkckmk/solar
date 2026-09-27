"""Render "Shared Clock": the same Earth time on all 8 planets.

Two cuts share one scene:

  short (default, 20 s / 600 frames) - 24 Earth hours, three planet zooms.
  long  (--long, 9:09 / 16 470 frames) - three acts on ONE continuous clock:
        0 -> 1 day -> 30 days -> 365 days. In every act the camera leaves the
        8-planet grid for each world in turn (zoom in, 12 s of detail, zoom out,
        back to the grid), so every planet is visited at 1, 30 and 365 days.
        Zoomed detail: real tilt angle between spin axis and orbit normal, an
        orbit inset (seen from the north) with the angle swept so far, plus the
        live counters. The grid in between shows all eight side by side on the
        same clock; bars rescale per act.

Every planet is driven by one Earth clock. Each one:
  - spins about its real, tilted axis (NASA obliquity; Venus upside down,
    Uranus on its side), at its real sidereal rate,
  - is lit from the Sun's direction in a Sun-fixed frame, so the day/night
    terminator sweeps across the surface exactly as fast as its local solar day
    (over a year the axis turns against the Sun: the seasons),
  - carries a red prime-meridian stripe and a pole rod so spin is readable even
    on featureless worlds,
  - shows live counters: spin degrees / turns, local days passed, orbital advance.
Where a planet would turn more than ~35° per frame (act III) the drawn spin is
rate-limited and its meridian stripe fades; the counters stay exact.

Sizes and distances are not to scale; the Sun is off-screen to the left.

Usage (inside Blender):
    blender --background --python render_shared_clock.py -- [--long] [--res 1920 1080]
        [--samples 16] [--days 1.0] [--lang en|tr] [--frames START END] [--still FRAME]
"""

from __future__ import annotations

import argparse
import math
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

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from science.planet_data import PLANETS, PLANET_ORDER, TRAIL_COLORS
from science.kepler import heliocentric_position
from science.rotation import rotation_state
from blender_build import (
    clear_scene, setup_render_settings, setup_world_starfield, build_planet_material,
    create_saturn_rings,
)
from render_io import output_dir, encode_frames

OUTPUT_DIR = output_dir()

FPS = 30
TOTAL_FRAMES = 600
CLOCK_START, CLOCK_END = 31, 570          # clock runs 00:00 → end between these frames

# ── Layout (world units; camera looks straight down −Z, screen up = +Y) ────
CELL_X = (-9.0, -3.0, 3.0, 9.0)
ROW_PLANET_Y = (2.95, -2.8)        # bottom-row bars stay clear of the footer line
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

# ── Long cut ──────────────────────────────────────────────────────────────
ACTS = (1.0, 30.0, 365.0)                 # clock end of each act (days)
BAR_SCALE = {1.0: (2.5, (1, 2)), 30.0: (80.0, (20, 40, 60)), 365.0: (900.0, (200, 400, 600, 800))}
LONG_ZOOM_WIDTH = 9.6                     # neighbours stay just outside the zoomed frame
LONG_ZOOM_DY = -0.8                       # room above the globe for the axis and tilt label
INSET_DX, INSET_DY, INSET_R = 3.3, -1.1, 0.95   # orbit inset, right of the globe, under the clock
MAX_SPIN_DEG_PER_FRAME = 35.0

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
        # long cut
        "day": "DAY",
        "act_title": {1.0: "1 EARTH DAY · 8 WORLDS", 30.0: "30 EARTH DAYS · 8 WORLDS",
                      365.0: "365 EARTH DAYS · 8 WORLDS"},
        "act_subtitle": {1.0: "Same 24 hours on every planet: how far does each one turn?",
                         30.0: "Same month on every planet: spins, local days and orbits",
                         365.0: "Same Earth year on every planet: spins, seasons and orbits"},
        "intro": ("8 WORLDS · ONE EARTH CLOCK", "Same Earth time on every planet: 1 day, 30 days, 365 days"),
        "chapter": {1.0: ("ACT I · 1 EARTH DAY", "24 hours: how far does each world turn?"),
                    30.0: ("ACT II · 30 EARTH DAYS", "The clock speeds up: one month"),
                    365.0: ("ACT III · 365 EARTH DAYS", "One Earth year: watch the axes turn against the Sun")},
        "outro": ("ONE EARTH YEAR", "Same clock, eight different days"),
        "orbit_view": "ORBIT (seen from north)",
        "laps": "laps",
        "slowed": "spin drawn slower than real",
        "foot_long": "Sun is to the left · red = prime meridian · white rod = spin axis · grey = orbit normal · not to scale · NASA/JPL data",
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
        # long cut
        "day": "GÜN",
        "act_title": {1.0: "1 DÜNYA GÜNÜ · 8 DÜNYA", 30.0: "30 DÜNYA GÜNÜ · 8 DÜNYA",
                      365.0: "365 DÜNYA GÜNÜ · 8 DÜNYA"},
        "act_subtitle": {1.0: "Her gezegende aynı 24 saat: hangisi ne kadar döner?",
                         30.0: "Her gezegende aynı ay: dönüşler, yerel günler, yörüngeler",
                         365.0: "Her gezegende aynı Dünya yılı: dönüşler, mevsimler, yörüngeler"},
        "intro": ("8 DÜNYA · TEK DÜNYA SAATİ", "Her gezegende aynı Dünya zamanı: 1 gün, 30 gün, 365 gün"),
        "chapter": {1.0: ("BÖLÜM I · 1 DÜNYA GÜNÜ", "24 saat: hangi gezegen ne kadar döner?"),
                    30.0: ("BÖLÜM II · 30 DÜNYA GÜNÜ", "Saat hızlanıyor: bir ay"),
                    365.0: ("BÖLÜM III · 365 DÜNYA GÜNÜ", "Bir Dünya yılı: eksenlerin Güneş'e göre dönüşünü izleyin")},
        "outro": ("BİR DÜNYA YILI", "Aynı saat, sekiz farklı gün"),
        "orbit_view": "YÖRÜNGE (kuzeyden)",
        "laps": "tur",
        "slowed": "dönüş gerçeğinden yavaş çizildi",
        "foot_long": "Güneş solda · kırmızı = başlangıç meridyeni · beyaz çubuk = dönme ekseni · gri = yörünge normali · ölçeksiz · NASA/JPL verisi",
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


def add_meridian_markers(mat: bpy.types.Material) -> bpy.types.Node:
    """Overlay a bold red prime meridian + three faint meridians on a planet material.

    Longitude is measured in object space, so the markers turn with the body.
    Returns the Value node scaling marker visibility (1 = full, 0 = hidden).
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

    amount = nodes.new('ShaderNodeValue')
    amount.name = "MeridianAmount"
    amount.outputs[0].default_value = 1.0
    faint_vis = nodes.new('ShaderNodeMath')
    faint_vis.operation = 'MULTIPLY'
    links.new(faint_amt.outputs[0], faint_vis.inputs[0])
    links.new(amount.outputs[0], faint_vis.inputs[1])
    bold_vis = nodes.new('ShaderNodeMath')
    bold_vis.operation = 'MULTIPLY'
    links.new(bold.outputs[0], bold_vis.inputs[0])
    links.new(amount.outputs[0], bold_vis.inputs[1])

    mix_faint = nodes.new('ShaderNodeMix')
    mix_faint.data_type = 'RGBA'
    links.new(faint_vis.outputs[0], mix_faint.inputs['Factor'])
    links.new(base_src, mix_faint.inputs[6])
    mix_faint.inputs[7].default_value = (0.95, 0.95, 0.95, 1.0)

    mix_bold = nodes.new('ShaderNodeMix')
    mix_bold.data_type = 'RGBA'
    links.new(bold_vis.outputs[0], mix_bold.inputs['Factor'])
    links.new(mix_faint.outputs[2], mix_bold.inputs[6])
    mix_bold.inputs[7].default_value = (0.95, 0.12, 0.06, 1.0)

    links.new(mix_bold.outputs[2], base_in)
    return amount


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


def set_alpha(obj, a: float):
    """Fade an emission-only object by its strength (base kept in obj["base_strength"])."""
    obj.hide_render = a < 0.01 or obj.get("empty", False)
    if obj.hide_render:
        return
    em = obj.active_material.node_tree.nodes.get("Emission")
    em.inputs['Strength'].default_value = obj["base_strength"] * a


def glow(obj, color: tuple, strength: float):
    obj.data.materials.append(emission_mat(f"Mat_{obj.name}", color, strength))
    obj["base_strength"] = strength
    return obj


def new_curve(name: str):
    cu = bpy.data.curves.new(name, type='CURVE')
    cu.dimensions = '3D'
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    obj = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(obj)
    return obj


def set_curve_points(obj, pts, bevel: float):
    """Replace a curve's single POLY spline (hidden when fewer than 2 points)."""
    cu = obj.data
    cu.splines.clear()
    obj["empty"] = len(pts) < 2
    obj.hide_render = obj["empty"]
    if obj["empty"]:
        return
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    flat = []
    for p in pts:
        flat.extend((p[0], p[1], p[2], 1.0))
    sp.points.foreach_set("co", flat)
    cu.bevel_depth = bevel


# ═══════════════════════════════════════════════════════════════════════
#  TIMELINES
# ═══════════════════════════════════════════════════════════════════════

def trapezoid(u: float, a: float = 0.06) -> float:
    """Clock easing: constant speed with short accelerate / decelerate ends."""
    u = min(1.0, max(0.0, u))
    v = 1.0 / (1.0 - a)
    if u < a:
        return 0.5 * v * u * u / a
    if u > 1.0 - a:
        return 1.0 - 0.5 * v * (1.0 - u) ** 2 / a
    return v * (u - 0.5 * a)


class ShortTimeline:
    """The original 20 s cut: `days_total` on one clock, three zooms."""
    long = False

    def __init__(self, days_total: float):
        self.days_total = days_total
        self.total = TOTAL_FRAMES
        self.keys = CAMERA_KEYS
        self.zoom_dy = -1.15

    def days(self, f: int) -> float:
        u = min(1.0, max(0.0, (f - CLOCK_START) / (CLOCK_END - CLOCK_START)))
        return u * self.days_total

    def act(self, f: int) -> float:
        return self.days_total

    def focus(self, f: int):
        return None, 0.0

    def card(self, f: int):
        return None, 0.0


class LongTimeline:
    """9-minute cut: intro, then per act (1 / 30 / 365 days) a chapter card, the grid,
    a zoom visit to every planet and a summary grid; the clock never resets."""
    long = True
    SEC = {"intro": 15, "chapter": 5, "grid": 8, "zin": 2.5, "hold": 12, "zout": 2.5,
           "gap": 2, "summary": 8, "outro": 15}

    def __init__(self):
        self.segs = []
        self._add("intro", 0.0)
        for act in ACTS:
            self._add("chapter", act)
            self._add("grid", act)
            for name in PLANET_ORDER:
                for kind in ("zin", "hold", "zout", "gap"):
                    self._add(kind, act, name)
            self._add("summary", act)
        self._add("outro", ACTS[-1])
        self.total = self.segs[-1]["f1"]
        self.zoom_dy = LONG_ZOOM_DY

        # Clock runs through each act from its first grid to the end of its summary.
        self.runs = {}
        prev = 0.0
        for act in ACTS:
            segs = [s for s in self.segs if s["act"] == act and s["kind"] not in ("chapter", "outro")]
            self.runs[act] = (segs[0]["f0"], segs[-1]["f1"], prev)
            prev = act

        self.keys = []
        for s in self.segs:
            a = (None, WIDE_WIDTH)
            b = (s["planet"], LONG_ZOOM_WIDTH)
            start, end = {"zin": (a, b), "hold": (b, b), "zout": (b, a)}.get(s["kind"], (a, a))
            self.keys += [(s["f0"], *start), (s["f1"], *end)]

    def _add(self, kind: str, act: float, planet: str | None = None):
        f0 = self.segs[-1]["f1"] + 1 if self.segs else 1
        n = int(round(self.SEC[kind] * FPS))
        self.segs.append({"kind": kind, "act": act, "planet": planet, "f0": f0, "f1": f0 + n - 1})

    def seg(self, f: int) -> dict:
        f = min(max(f, 1), self.total)
        return next(s for s in self.segs if s["f0"] <= f <= s["f1"])

    def act(self, f: int) -> float:
        return self.seg(f)["act"] or ACTS[0]

    def days(self, f: int) -> float:
        s = self.seg(f)
        if s["kind"] == "intro":
            return 0.0
        if s["kind"] == "outro":
            return ACTS[-1]
        f0, f1, start = self.runs[s["act"]]
        if f < f0:                                  # chapter card: clock waits
            return start
        return start + (s["act"] - start) * trapezoid((f - f0) / (f1 - f0))

    def focus(self, f: int):
        s = self.seg(f)
        if s["kind"] not in ("zin", "hold", "zout"):
            return None, 0.0
        width = camera_state(f, self.keys, self.zoom_dy)[2]
        return s["planet"], (WIDE_WIDTH - width) / (WIDE_WIDTH - LONG_ZOOM_WIDTH)

    def card(self, f: int):
        s = self.seg(f)
        t, dur = (f - s["f0"]) / FPS, (s["f1"] - s["f0"] + 1) / FPS
        if s["kind"] == "intro":
            return ("intro", None), min(1.0, max(0.0, (t - 1.5) / 1.5)) * min(1.0, max(0.0, (dur - 1.0 - t) / 1.5))
        if s["kind"] == "chapter":
            return ("chapter", s["act"]), min(1.0, t / 0.6) * min(1.0, max(0.0, (dur - t) / 0.6))
        if s["kind"] == "outro":
            return ("outro", None), min(1.0, max(0.0, (t - 2.0) / 1.5))
        return None, 0.0


def visual_spin_tables(tl) -> tuple[dict, dict]:
    """Drawn spin angle per planet per frame, rate-limited to MAX_SPIN_DEG_PER_FRAME
    (so fast rotators never strobe), plus meridian-stripe visibility (1 = true rate)."""
    spin = {n: [0.0] * (tl.total + 1) for n in PLANET_ORDER}
    stripe = {n: [1.0] * (tl.total + 1) for n in PLANET_ORDER}
    prev = tl.days(1)
    acc = {n: 360.0 * prev / abs(PLANETS[n].rotation_period_days) for n in PLANET_ORDER}
    for f in range(1, tl.total + 1):
        d = tl.days(f)
        for n in PLANET_ORDER:
            step = 360.0 * (d - prev) / abs(PLANETS[n].rotation_period_days)
            acc[n] += max(-MAX_SPIN_DEG_PER_FRAME, min(MAX_SPIN_DEG_PER_FRAME, step))
            spin[n][f] = acc[n]
            stripe[n][f] = min(1.0, max(0.0, (MAX_SPIN_DEG_PER_FRAME + 10.0 - abs(step)) / 10.0))
        prev = d
    return spin, stripe


# ═══════════════════════════════════════════════════════════════════════
#  SCENE
# ═══════════════════════════════════════════════════════════════════════

def build_scene(res: tuple[int, int], samples: int, lang: str, tl):
    S = STRINGS[lang]
    clear_scene()
    setup_render_settings(res, samples)
    setup_world_starfield()
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, tl.total

    # Sunlight from the left (travels +X) + faint camera fill so night sides stay legible
    sun_data = bpy.data.lights.new("Sunlight", type='SUN')
    sun_data.energy = 4.2
    sun_data.color = (1.0, 0.96, 0.90)
    sun_data.angle = math.radians(0.6)
    # The planets sit in rows along the light direction: with shadows on, each one
    # eclipses its right-hand neighbour (Venus, Earth, Mars, Saturn... went dark).
    sun_data.use_shadow = False
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
    hud["foot"] = make_text("HUD_Foot", S["foot_long"] if tl.long else S["foot"],
                            (0, -half_h * 0.91, -1), 0.0058, (0.55, 0.60, 0.68), 'CENTER', 1.2, cam)
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
    acts = ACTS if tl.long else (tl.days_total,)
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
        meridian = add_meridian_markers(mat)
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
        for t, st in zip(tx, (2.2, 1.5, 1.7, 1.3)):
            t["base_strength"] = st

        bar_x0 = cx - BAR_LEN / 2
        bar_y = base_y + TEXT_OFFSETS[4]
        bar_bg = make_rect(f"BarBg_{name}", bar_x0, bar_y, BAR_LEN, 0.07, (0.22, 0.23, 0.26), 1.0)
        fill_bar = make_rect(f"Bar_{name}", bar_x0, bar_y, 0.0001, 0.07, color, 2.4, z=0.001)
        bar_bg["base_strength"], fill_bar["base_strength"] = 1.0, 2.4
        ticks = {}
        for act in acts:
            bar_max, marks = BAR_SCALE.get(act, (BAR_MAX_DAYS, (1, 2)))
            ticks[act] = [make_rect(f"Tick{d}_{name}", bar_x0 + BAR_LEN * d / bar_max - 0.012, bar_y,
                                    0.024, 0.20, (0.75, 0.78, 0.85), 1.2, z=0.002) for d in marks]
            for t in ticks[act]:
                t["base_strength"] = 1.2

        rigs[name] = {"tilt": tilt_empty, "body": body, "cell": (cx, cy), "r": r,
                      "tilt_deg": p.axial_tilt_deg, "texts": tx, "bar": fill_bar,
                      "meridian": meridian, "ticks": ticks, "bar_bg": bar_bg}

    extra = build_long_extras(cam, half_w, half_h, S) if tl.long else None
    return cam, hud, clock_bar, clock_bar_w, rigs, extra


def build_long_extras(cam, half_w: float, half_h: float, S: dict) -> dict:
    """Zoom annotations (tilt arc, orbit normal, orbit inset) and chapter cards."""
    ex = {}
    bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2.0, vertices=16)
    ex["normal"] = glow(bpy.context.active_object, (0.55, 0.58, 0.64), 1.0)
    ex["normal"].name = "Zoom_OrbitNormal"
    ex["tilt_arc"] = glow(new_curve("Zoom_TiltArc"), (1.0, 0.84, 0.4), 2.2)
    ex["tilt_label"] = make_text("Zoom_TiltLabel", "", (0, 0, 0.3), 0.26, (1.0, 0.86, 0.45), 'CENTER', 2.2)
    ex["tilt_label"]["base_strength"] = 2.2

    ex["ellipse"] = glow(new_curve("Inset_Orbit"), (0.6, 0.64, 0.7), 1.0)
    ex["swept"] = glow(new_curve("Inset_Swept"), (1, 1, 1), 2.4)
    ex["ray0"] = glow(new_curve("Inset_Ray0"), (0.6, 0.64, 0.7), 1.0)
    ex["ray1"] = glow(new_curve("Inset_Ray1"), (1, 1, 1), 1.8)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=12)
    ex["sun"] = glow(bpy.context.active_object, (1.0, 0.85, 0.45), 3.0)
    ex["sun"].name = "Inset_Sun"
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=12)
    ex["dot"] = glow(bpy.context.active_object, (1, 1, 1), 2.6)
    ex["dot"].name = "Inset_Planet"
    ex["caption"] = make_text("Inset_Caption", S["orbit_view"], (0, 0, 0.3), 0.17,
                              (0.62, 0.68, 0.76), 'CENTER', 1.4)
    ex["caption"]["base_strength"] = 1.4
    ex["value"] = make_text("Inset_Value", "", (0, 0, 0.3), 0.22, (1, 1, 1), 'CENTER', 2.0)
    ex["value"]["base_strength"] = 2.0
    ex["zoom_objs"] = [ex[k] for k in ("normal", "tilt_arc", "tilt_label", "ellipse", "swept",
                                       "ray0", "ray1", "sun", "dot", "caption", "value")]

    ex["slowed"] = make_text("HUD_Slowed", S["slowed"], (-half_w * 0.94, -half_h * 0.82, -1), 0.0058,
                             (0.55, 0.60, 0.68), 'LEFT', 1.2, cam)
    ex["slowed"]["base_strength"] = 1.2

    # Chapter cards: darkening plane + two lines, all in front of the grid
    me = bpy.data.meshes.new("Card_Backdrop")
    bm = bmesh.new()
    w, h = half_w * 1.1, half_h * 0.42
    bm.faces.new([bm.verts.new(v) for v in ((-w, -h, 0), (w, -h, 0), (w, h, 0), (-w, h, 0))])
    bm.to_mesh(me)
    bm.free()
    back = bpy.data.objects.new("Card_Backdrop", me)
    bpy.context.collection.objects.link(back)
    back.parent = cam
    back.location = (0.0, 0.0, -1.002)
    mat = bpy.data.materials.new("Card_Backdrop_Mat")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    tr = nodes.new('ShaderNodeBsdfTransparent')
    em = nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    mix = nodes.new('ShaderNodeMixShader')
    links.new(tr.outputs[0], mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    out = nodes.new('ShaderNodeOutputMaterial')
    links.new(mix.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    me.materials.append(mat)
    ex["backdrop"], ex["backdrop_mix"] = back, mix
    ex["card"] = [make_text("Card_L0", "", (0, half_h * 0.08, -1), 0.020, (1.0, 0.95, 0.85), 'CENTER', 2.4, cam),
                  make_text("Card_L1", "", (0, -half_h * 0.12, -1), 0.0105, (0.75, 0.80, 0.88), 'CENTER', 1.8, cam)]
    for o, s in zip(ex["card"], (2.4, 1.8)):
        o["base_strength"] = s
    return ex


def camera_state(f: int, keys=CAMERA_KEYS, zoom_dy: float = -1.15) -> tuple[float, float, float]:
    """(center_x, center_y, visible_width) for frame f."""
    def target(key):
        _, planet, width = key
        if planet is None:
            return 0.0, 0.0, width
        cx, cy = cell_of(planet)
        return cx, cy + zoom_dy, width

    for a, b in zip(keys, keys[1:]):
        if a[0] <= f <= b[0]:
            u = smoothstep((f - a[0]) / max(1, b[0] - a[0]))
            ta, tb = target(a), target(b)
            return tuple(ta[i] + (tb[i] - ta[i]) * u for i in range(3))
    return target(keys[-1])


def update_frame(f: int, tl, lang: str, cam, hud, clock_bar, clock_bar_w, rigs, extra, spin_tab):
    S = STRINGS[lang]
    days = tl.days(f)
    act = tl.act(f)
    vis_spin, stripe = spin_tab

    # Camera
    cx, cy, width = camera_state(f, tl.keys, tl.zoom_dy)
    dist = width * LENS_MM / 36.0
    cam.location = (cx, cy, dist)
    cam.rotation_euler = (0.0, 0.0, 0.0)

    # Global clock
    if tl.long:
        hud["title"].data.body = S["act_title"][act]
        hud["subtitle"].data.body = S["act_subtitle"][act]
        hud["clock"].data.body = fmt_hours(days * 24.0) if act <= 1.0 else f"{S['day']} {days:.1f}"
        clock_bar.scale.x = max(1e-4, clock_bar_w * min(1.0, days / act))
    else:
        u = min(1.0, max(0.0, (f - CLOCK_START) / (CLOCK_END - CLOCK_START)))
        hud["clock"].data.body = fmt_hours(days * 24.0) if tl.days_total <= 1.0 else f"{days:.2f} d"
        clock_bar.scale.x = max(1e-4, clock_bar_w * u)

    bar_max = BAR_SCALE.get(act, (BAR_MAX_DAYS,))[0]
    states = {}
    for name, rig in rigs.items():
        rs = rotation_state(name, days)
        states[name] = rs
        rig["tilt"].matrix_world = attitude_matrix(rig["cell"], rs.orbit_deg, rig["tilt_deg"])
        # Spin about the tilted axis (tilt > 90° already encodes retrograde sense)
        rig["body"].rotation_euler = (0.0, 0.0, math.radians(vis_spin[name][f]))
        rig["meridian"].outputs[0].default_value = stripe[name][f]

        retro = f"  ({S['retro']})" if PLANETS[name].rotation_period_days < 0 else ""
        rig["texts"][1].data.body = (f"{S['spin']}  {abs(rs.spin_deg):,.1f}°  ·  "
                                     f"{rs.spin_turns:,.2f} {S['turns']}{retro}").replace(",", " ")
        rig["texts"][2].data.body = f"{S['local_days']}  {rs.local_days:,.3f}".replace(",", " ")
        sol = rs.solar_day_days
        sol_txt = (f"{sol * 24.0:.1f} {S['hours']}" if sol < 2.0
                   else f"{sol:.0f} {S['days']}")
        rig["texts"][3].data.body = f"{S['day_is']} {sol_txt}  ·  {S['orbit']} +{rs.orbit_deg:.3f}°"
        rig["bar"].scale.x = max(1e-4, BAR_LEN * min(rs.local_days, bar_max) / bar_max)
        for a, ticks in rig["ticks"].items():
            for t in ticks:
                t.hide_render = a != act

    if extra is not None:
        update_long_extras(f, tl, S, rigs, states, extra, stripe)


def update_long_extras(f: int, tl, S: dict, rigs: dict, states: dict, ex: dict, stripe: dict):
    # Chapter cards
    card, ca = tl.card(f)
    lines = ("", "")
    if card:
        kind, act = card
        lines = S["chapter"][act] if kind == "chapter" else S[kind]
    for o, txt in zip(ex["card"], lines):
        o.data.body = txt
        set_alpha(o, ca if txt else 0.0)
    ex["backdrop_mix"].inputs['Fac'].default_value = 0.9 * ca
    ex["backdrop"].hide_render = ca < 0.01

    # Zoom detail
    name, w = tl.focus(f)
    a = smoothstep((w - 0.45) / 0.55) if name else 0.0
    act = tl.act(f)
    for other, orig in rigs.items():                 # dim the neighbouring cells while zoomed
        dim = 1.0 if other == name else 1.0 - 0.95 * a
        for o in orig["texts"] + [orig["bar"], orig["bar_bg"]] + orig["ticks"].get(act, []):
            set_alpha(o, dim)
    if a < 0.01:
        for o in ex["zoom_objs"] + [ex["slowed"]]:
            o.hide_render = True
        return
    rig, rs = rigs[name], states[name]
    color = TRAIL_COLORS[name]
    r = rig["r"]
    M = rig["tilt"].matrix_world
    center = M.translation
    k = (M.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    n = Vector((0.0, math.cos(math.radians(VIEW_ELEVATION_DEG)), math.sin(math.radians(VIEW_ELEVATION_DEG))))

    ex["normal"].matrix_world = (Matrix.Translation(center) @ n.to_track_quat('Z', 'Y').to_matrix().to_4x4() @
                                 Matrix.Diagonal((0.012, 0.012, ROD_HALF * r * 1.05, 1.0)))
    tilt = rig["tilt_deg"]
    e2 = k - n * k.dot(n)
    e2 = e2.normalized() if e2.length > 1e-6 else n.orthogonal().normalized()
    th = math.radians(tilt)
    steps = max(6, int(tilt / 3.0))
    R = 1.42 * r
    set_curve_points(ex["tilt_arc"], [center + (n * math.cos(th * i / steps) + e2 * math.sin(th * i / steps)) * R
                                      for i in range(steps + 1)] if tilt >= 1.0 else [], 0.018)
    half = th * 0.5
    ex["tilt_label"].location = center + (n * math.cos(half) + e2 * math.sin(half)) * 1.65 * r + Vector((0, 0, 0.3))
    ex["tilt_label"].data.body = f"{tilt:.1f}°"

    # Orbit inset: true ellipse seen from ecliptic north, swept angle since day 0
    cx, cy = rig["cell"]
    oc = Vector((cx + INSET_DX, cy + INSET_DY, 0.2))
    p = PLANETS[name]
    Q = p.semi_major_axis_au * (1.0 + p.eccentricity)
    s = INSET_R / Q
    AU = 149_597_870.7

    def inset(t):
        st = heliocentric_position(p, t)
        return oc + Vector((st.x / AU * s, st.y / AU * s, 0.0))

    period = p.orbital_period_days
    set_curve_points(ex["ellipse"], [inset(period * i / 180.0) for i in range(181)], 0.008)
    days = tl.days(f)
    swept = rs.orbit_deg
    t0 = max(0.0, days - period)                       # at most the last full lap
    nseg = max(8, min(400, int(min(swept, 360.0) / 2.0)))
    set_curve_points(ex["swept"], [inset(t0 + (days - t0) * i / nseg) for i in range(nseg + 1)]
                     if days > 0 else [], 0.028)
    set_curve_points(ex["ray0"], [oc, inset(t0)], 0.006)
    set_curve_points(ex["ray1"], [oc, inset(days)], 0.008)
    ex["sun"].matrix_world = Matrix.Translation(oc) @ Matrix.Scale(0.075, 4)
    ex["dot"].matrix_world = Matrix.Translation(inset(days)) @ Matrix.Scale(0.07, 4)
    for key in ("swept", "ray1", "dot", "value"):
        ex[key].active_material.node_tree.nodes["Emission"].inputs['Color'].default_value = (*color, 1.0)
    ex["caption"].location = oc + Vector((0.0, INSET_R + 0.32, 0.0))
    ex["value"].location = oc + Vector((0.0, -INSET_R - 0.3, 0.0))
    laps = swept / 360.0
    ex["value"].data.body = (f"+{swept:.2f}°" if laps < 0.1 else f"+{swept:,.1f}°  ·  {laps:.2f} {S['laps']}"
                             ).replace(",", " ")

    for o in ex["zoom_objs"]:
        set_alpha(o, a)
    set_alpha(ex["slowed"], a if stripe[name][f] < 0.5 else 0.0)


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--long", action="store_true", help="9-minute three-act cut (1 / 30 / 365 days)")
    ap.add_argument("--res", nargs=2, type=int, default=(1920, 1080))
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--days", type=float, default=1.0, help="Clock span of the short cut")
    ap.add_argument("--lang", choices=sorted(STRINGS), default="en")
    ap.add_argument("--frames", nargs=2, type=int)
    ap.add_argument("--still", type=int, nargs="+", help="Render test frame(s) and exit")
    ap.add_argument("--name", default=None)
    args = ap.parse_args(argv)

    tl = LongTimeline() if args.long else ShortTimeline(args.days)
    name = args.name or ("solar_shared_clock_9min" if args.long else "solar_1_day_shared_clock_20s")
    frames_dir = OUTPUT_DIR / f"{name}_{args.lang}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    state = build_scene(tuple(args.res), args.samples, args.lang, tl)
    spin_tab = visual_spin_tables(tl)
    scene = bpy.context.scene

    if args.still:
        for f in args.still:
            update_frame(f, tl, args.lang, *state, spin_tab)
            out = OUTPUT_DIR / f"{name}_{args.lang}_still_{f:05d}.png"
            scene.render.filepath = str(out)
            bpy.ops.render.render(write_still=True)
            print(f"Still: {out}")
        return

    f0, f1 = args.frames if args.frames else (1, tl.total)
    for f in range(f0, f1 + 1):
        out = frames_dir / f"frame_{f:06d}.png"
        if out.exists() and out.stat().st_size > 0:
            continue
        scene.frame_set(f)
        update_frame(f, tl, args.lang, *state, spin_tab)
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        if f % 30 == 0:
            print(f"  frame {f}/{tl.total}")

    if len(list(frames_dir.glob("frame_*.png"))) < tl.total:
        print("Partial range rendered; skipping encode.")
        return

    mp4 = encode_frames(frames_dir, OUTPUT_DIR / "final" / f"{name}_{args.lang}.mp4", FPS, start_number=1)
    print(f"✅ {mp4}")


if __name__ == "__main__":
    main()
