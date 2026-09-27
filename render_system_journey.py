"""System Journey: the 9:25 film as one continuous, live camera flight (Format A, long).

Follows the 32-shot timeline in `project.json` (1 / 30 / 365 Earth-day acts), but
nothing is frozen: one shared Earth clock drives all eight planets on their real
Keplerian orbits and the camera flies between the whole system and each world.

Every focus shot (e.g. `earth_30`):
  IN    the camera zooms from the system view onto the planet while the clock
        rewinds to day 0 (all trails retract)
  RUN   the clock runs 0 → N days for every planet; the camera rides along with
        the focused one: growing trail, real spin axis vs. orbit normal with the
        tilt angle, prime-meridian marker, live counters (distance, orbit angle,
        speed, Sun distance, spin, local days)
  HOLD  final numbers
  OUT   the camera pulls back to the whole system: every planet sits where N days
        put it, swept-angle wedges and "clock hand" spokes plus a lap panel show
        how the worlds keep time with each other
Comparison shots run the clock for the whole system at once while the camera
dollies from the outer system into the inner one. Opening / chapters / outro
are wide titles.

Sizes are exaggerated per shot so each arc stays readable; distances and angles
are real (NASA/JPL elements, IAU pole directions).

Usage (inside Blender):
    blender --background --python render_system_journey.py -- [--lang en|tr]
        [--res 2560 1440] [--samples 16] [--frames START END] [--step N]
        [--still FRAME [FRAME ...]] [--list-shots]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    import bpy
    from mathutils import Matrix, Vector
except ImportError:
    print("This script must run inside Blender Python.")
    sys.exit(1)

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from science.planet_data import PLANETS, PLANET_ORDER, TRAIL_COLORS, AU_KM
from science.kepler import heliocentric_position
from science.rotation import orbital_advance_deg, rotation_state
from science.attitude import spin_axis, orbit_normal, obliquity_deg
from science.coordinates import planet_visual_radius, sun_visual_radius
from blender_build import (
    clear_scene, setup_render_settings, setup_world_starfield, create_sun,
    build_planet_material, create_saturn_rings,
)
from render_shared_clock import (
    STRINGS as CLOCK_STRINGS, make_text, make_rect, add_meridian_markers,
    glow, set_alpha, new_curve, set_curve_points,
)
from render_io import output_dir, encode_frames

FPS = 30
LENS_MM = 35.0
SENSOR_MM = 36.0
HALF_W = 0.5 * SENSOR_MM / LENS_MM          # half frame width at unit depth

IN_S, HOLD_S, OUT_S = 3.5, 1.5, 3.0         # focus-shot phases (RUN = the rest)
REWIND_S = 1.5                              # comparison / chapter rewind
WIDE_DIST = 2.6                             # camera distance per unit of framed radius
MIN_PLANET = 0.0017                         # min planet radius / camera distance (~7 px @1440p)
MIN_SUN = 0.0026
MAX_SPIN_DEG_PER_FRAME = 35.0               # faster surface spin is slowed for display
TRAIL_GRID = 720                            # trail samples per interval
TEST_FRAMES = 20 * FPS                      # --test clip length

STRINGS = {
    "en": {
        "names": CLOCK_STRINGS["en"]["names"],
        "act": {1: "1 EARTH DAY", 30: "30 EARTH DAYS", 365: "365 EARTH DAYS"},
        "time": "TIME", "day": "DAY",
        "distance": "DISTANCE", "orbit_angle": "ORBIT ANGLE", "of_orbit": "of orbit",
        "speed": "SPEED", "sun_dist": "SUN DISTANCE", "spin": "SPIN", "turns": "turns",
        "retro": "retrograde", "tilt": "AXIAL TILT", "local_days": "LOCAL DAYS",
        "million_km": "million km", "laps": "laps",
        "clock": "EARTH CLOCK", "harmony": "SAME CLOCK · EVERY ORBIT",
        "legend": "white rod = spin axis · green = north · grey = orbit normal · red = prime meridian",
        "slowed": "surface spin slowed for display",
        "foot": "Sizes not to scale · planets enlarged · real orbits & angles · NASA/JPL data",
        "opening": ("THE SOLAR SYSTEM", "THROUGH EARTH TIME", "1 DAY  ·  30 DAYS  ·  365 DAYS"),
        "chapter": {
            1: ("ACT I  ·  1 EARTH DAY", "24 HOURS", "How far does every world move in a single day?"),
            30: ("ACT II  ·  30 EARTH DAYS", "ONE MONTH", "Now the orbits start to open up."),
            365: ("ACT III  ·  365 EARTH DAYS", "ONE EARTH YEAR", "The full payoff: one lap of Earth."),
        },
        "outro": ("ONE EARTH YEAR LATER", "Every world keeps its own rhythm around the same Sun.",
                  "Solar System Time Journey"),
    },
    "tr": {
        "names": CLOCK_STRINGS["tr"]["names"],
        "act": {1: "1 DÜNYA GÜNÜ", 30: "30 DÜNYA GÜNÜ", 365: "365 DÜNYA GÜNÜ"},
        "time": "SÜRE", "day": "GÜN",
        "distance": "KAT EDİLEN YOL", "orbit_angle": "YÖRÜNGE AÇISI", "of_orbit": "yörünge",
        "speed": "HIZ", "sun_dist": "GÜNEŞE UZAKLIK", "spin": "DÖNÜŞ", "turns": "tur",
        "retro": "ters yön", "tilt": "EKSEN EĞİKLİĞİ", "local_days": "GEÇEN YEREL GÜN",
        "million_km": "milyon km", "laps": "tur",
        "clock": "DÜNYA SAATİ", "harmony": "AYNI SAAT · HER YÖRÜNGE",
        "legend": "beyaz çubuk = dönme ekseni · yeşil = kuzey · gri = yörünge normali · kırmızı = başlangıç meridyeni",
        "slowed": "yüzey dönüşü görüntüde yavaşlatıldı",
        "foot": "Boyutlar ölçeksiz · gezegenler büyütüldü · gerçek yörünge ve açılar · NASA/JPL verisi",
        "opening": ("GÜNEŞ SİSTEMİ", "DÜNYA ZAMANIYLA", "1 GÜN  ·  30 GÜN  ·  365 GÜN"),
        "chapter": {
            1: ("BÖLÜM I  ·  1 DÜNYA GÜNÜ", "24 SAAT", "Tek bir günde her gezegen ne kadar yol alır?"),
            30: ("BÖLÜM II  ·  30 DÜNYA GÜNÜ", "BİR AY", "Şimdi yörüngeler açılmaya başlıyor."),
            365: ("BÖLÜM III  ·  365 DÜNYA GÜNÜ", "BİR DÜNYA YILI", "Büyük final: Dünya'nın tam bir turu."),
        },
        "outro": ("BİR DÜNYA YILI SONRA", "Her gezegen aynı Güneş'in etrafında kendi ritmini tutar.",
                  "Güneş Sistemi Zaman Yolculuğu"),
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  SMALL MATH (tuples, double precision — mathutils is single precision)
# ═══════════════════════════════════════════════════════════════════════

def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def length(a): return math.sqrt(dot(a, a))
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def normalize(a):
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-15 else (0.0, 0.0, 1.0)


def lerp(a, b, u): return a + (b - a) * u
def vlerp(a, b, u): return (lerp(a[0], b[0], u), lerp(a[1], b[1], u), lerp(a[2], b[2], u))
def loglerp(a, b, u): return math.exp(lerp(math.log(a), math.log(b), u))
def clamp01(u): return min(1.0, max(0.0, u))


def smootherstep(u: float) -> float:
    u = clamp01(u)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def trapezoid(u: float, a: float = 0.08) -> float:
    """Clock easing: constant speed with short accelerate / decelerate ends."""
    u = clamp01(u)
    v = 1.0 / (1.0 - a)
    if u < a:
        return 0.5 * v * u * u / a
    if u > 1.0 - a:
        return 1.0 - 0.5 * v * (1.0 - u) ** 2 / a
    return v * (u - 0.5 * a)


def sph_dir(el_deg: float, az_deg: float):
    el, az = math.radians(el_deg), math.radians(az_deg)
    return (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))


def axis_basis(z, ref) -> Matrix:
    """Rotation whose local Z is `z`; local X lies along ref × z when defined."""
    x = cross(ref, z)
    if length(x) < 1e-6:
        x = cross((1.0, 0.0, 0.0), z)
    x = normalize(x)
    y = cross(z, x)
    return Matrix(((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2]))).to_4x4()


# ═══════════════════════════════════════════════════════════════════════
#  PHYSICS CACHE
# ═══════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=500_000)
def pos(name: str, t: float):
    """Heliocentric ecliptic position in AU (= Blender units before the floating origin)."""
    s = heliocentric_position(PLANETS[name], t)
    return (s.x / AU_KM, s.y / AU_KM, s.z / AU_KM)


@lru_cache(maxsize=None)
def cum_distance_table(name: str, days: float, n: int = 2000):
    """Cumulative path length (km) along the real trajectory over [0, days]."""
    p = PLANETS[name]
    table = [0.0]
    prev = heliocentric_position(p, 0.0)
    for i in range(1, n + 1):
        cur = heliocentric_position(p, days * i / n)
        table.append(table[-1] + math.dist((prev.x, prev.y, prev.z), (cur.x, cur.y, cur.z)))
        prev = cur
    return table


def distance_km(name: str, days: float, t: float) -> float:
    table = cum_distance_table(name, days)
    x = clamp01(t / days) * (len(table) - 1)
    i = min(int(x), len(table) - 2)
    return lerp(table[i], table[i + 1], x - i)


def speed_kms(name: str, t: float, h: float) -> float:
    a = heliocentric_position(PLANETS[name], t - h)
    b = heliocentric_position(PLANETS[name], t + h)
    return math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) / (2.0 * h * 86_400.0)


def aphelion(name: str) -> float:
    p = PLANETS[name]
    return p.semi_major_axis_au * (1.0 + p.eccentricity)


def guide_times(name: str, c: float, window_days: float, dense: bool) -> list[float]:
    """One full orbit centred on the current clock. For the focused planet the part
    near the camera is sampled finely so the guide hugs the trail in close-ups."""
    period = PLANETS[name].orbital_period_days
    base = round(c / period * 360.0) * period / 360.0          # snap -> cache-friendly times
    ts = [base - period / 2 + period * i / 360.0 for i in range(361)]
    if dense and window_days > 0:
        w = min(3.0 * window_days, period / 4)
        ts += [c - w + 2 * w * i / 400.0 for i in range(401)]
        ts.sort()
    return ts


def trail_times(c: float, grid_days: float) -> list[float]:
    if c <= 1e-9:
        return []
    dt = grid_days / TRAIL_GRID
    k = int(c / dt + 1e-9)
    ts = [i * dt for i in range(k + 1)]
    if c - ts[-1] > dt * 1e-3:
        ts.append(c)
    return ts


# ═══════════════════════════════════════════════════════════════════════
#  TIMELINE
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Shot:
    id: str
    kind: str
    f0: int
    f1: int                     # inclusive
    planet: str | None
    days: float                 # act interval (0 for opening)
    clock0: float = 0.0
    clock1: float = 0.0
    R0: float = 30.0            # wide framing radius (AU) + elevation at start / end
    el0: float = 34.0
    R1: float = 30.0
    el1: float = 34.0
    sh0: float = 0.0            # sideways framing shift (fraction of R), start / end
    sh1: float = 0.0

    @property
    def dur(self) -> float:
        return (self.f1 - self.f0 + 1) / FPS

    @property
    def run_s(self) -> float:
        if self.kind == "focus":
            return self.dur - IN_S - HOLD_S - OUT_S
        if self.kind == "comparison":
            return self.dur - 2.0 * REWIND_S
        return 0.0


def load_shots() -> list[Shot]:
    project = json.loads((PROJECT_DIR / "project.json").read_text(encoding="utf-8"))
    shots, f, act = [], 0, 0.0
    for item in project["timeline"]:
        n = int(round(item["seconds"] * FPS))
        act = float(item.get("earth_days", act))
        shots.append(Shot(item["id"], item["kind"], f, f + n - 1, item.get("planet"), act))
        f += n

    prev = None
    for s in shots:
        s.clock0 = prev.clock1 if prev else 0.0
        s.R0, s.el0, s.sh0 = (prev.R1, prev.el1, prev.sh1) if prev else (46.0, 40.0, 0.0)
        if s.kind == "opening":
            s.clock1, s.R1, s.el1 = 0.0, 30.0, 33.0
        elif s.kind == "chapter":
            s.clock1, s.R1, s.el1 = 0.0, 26.0, 31.0
        elif s.kind == "focus":
            s.clock1, s.R1, s.el1 = s.days, max(1.9, aphelion(s.planet) * 1.3), 30.0
            s.sh1 = 0.3
        elif s.kind == "comparison":
            s.clock1, s.R1, s.el1 = s.days, {1: 1.15, 30: 2.1}.get(int(s.days), 2.3), 40.0
            s.sh1 = 0.3
        else:  # outro
            s.clock1, s.R1, s.el1 = s.clock0, 48.0, 42.0
        prev = s
    return shots


def azimuth(f: int) -> float:
    """Slow global orbit of the camera, continuous across shots."""
    return -100.0 + 0.004 * f


# ═══════════════════════════════════════════════════════════════════════
#  CAMERA STATES
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Cam:
    target: tuple
    direction: tuple            # unit vector target → camera
    dist: float
    r_focus: float = 0.0        # display radius for the focused planet


def screen_right(direction):
    return normalize(cross(mul(direction, -1.0), (0.0, 0.0, 1.0)))


def wide_cam(R: float, el: float, f: int, shift: float = 0.0) -> Cam:
    """Sun-centred view framing radius R; `shift` > 0 slides the system left on screen."""
    d = sph_dir(el, azimuth(f))
    return Cam(mul(screen_right(d), shift * R), d, R * WIDE_DIST)


@lru_cache(maxsize=None)
def focus_geometry(name: str, days: float):
    """Arc length (AU), sweep (deg) and display radius targets for one focus interval."""
    p = PLANETS[name]
    arc = cum_distance_table(name, days)[-1] / AU_KM
    sweep = 360.0 * days / p.orbital_period_days
    L = min(arc, 2.0 * math.pi * p.semi_major_axis_au)
    r_nom = planet_visual_radius(p.mean_radius_km)
    return arc, sweep, L, r_nom


def focus_cam(name: str, days: float, c: float, f: int) -> Cam:
    """Follow cam for short arcs, orbit overview for long ones, blended by sweep angle."""
    _, sweep, L, r_nom = focus_geometry(name, days)
    P = pos(name, c)
    b = smootherstep((sweep - 30.0) / 90.0)

    # Follow: sunward 3/4 view so the lit face and the trail both read; planet leads on screen.
    ur = normalize((P[0], P[1], 0.0))
    uz = (0.0, 0.0, 1.0)
    ut = cross(uz, ur)
    r_f = min(0.11 * L, 3.0 * r_nom) * (0.6 if name == "saturn" else 1.0)
    D_f = max(1.6 * L, 9.0 * r_f)
    T_f = add(sub(P, mul(ut, 0.35 * L)), mul(uz, 0.12 * L))
    o_f = normalize(add(add(mul(ur, -0.55), mul(ut, 0.22)), mul(uz, 0.42)))
    if b <= 0.0:
        return Cam(T_f, o_f, D_f, r_f)

    # Overview: whole orbit from above, leaning toward the planet.
    Q = aphelion(name)
    D_o = 3.6 * Q
    o_o = sph_dir(48.0, azimuth(f))
    T_o = sub(mul(P, 0.1), mul(screen_right(o_o), 0.3 * Q))     # orbit right of the HUD
    r_o = max(r_nom, 0.045 * Q)
    return Cam(vlerp(T_f, T_o, b), normalize(vlerp(o_f, o_o, b)),
               loglerp(D_f, D_o, b), loglerp(r_f, r_o, b))


def blend_cam(W: Cam, F: Cam, u: float) -> tuple[Cam, float]:
    """Zoom from wide W to focus F (u: 0 → 1). Log-distance zoom; the target converges
    in proportion to distance so the planet never leaves the frame. Returns (cam, w)."""
    sd = smootherstep(u)
    D = loglerp(W.dist, F.dist, sd)
    frac = (D - F.dist) / (W.dist - F.dist) if abs(W.dist - F.dist) > 1e-12 else 0.0
    T = add(F.target, mul(sub(W.target, F.target), clamp01(frac)))
    d = normalize(vlerp(W.direction, F.direction, smootherstep((u - 0.3) / 0.7)))
    return Cam(T, d, D, F.r_focus), sd


# ═══════════════════════════════════════════════════════════════════════
#  PER-FRAME STATE
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class State:
    shot: Shot
    clock: float
    cam: Cam
    w: float                    # focus weight: 0 = system view, 1 = on the planet
    grid_days: float
    title_alpha: float = 0.0
    harmony_alpha: float = 0.0
    clock_alpha: float = 1.0


def rewind(c0: float, t: float, span: float) -> float:
    return c0 * (1.0 - smootherstep(t / span)) if span > 0 else 0.0


def fade(t: float, dur: float, t_in: float, t_out: float, ramp: float = 1.0) -> float:
    return clamp01((t - t_in) / ramp) * clamp01((dur - t_out - t) / ramp)


def evaluate(shots: list[Shot], f: int) -> State:
    shot = next(s for s in shots if s.f0 <= f <= s.f1)
    t = (f - shot.f0) / FPS
    dur = shot.dur
    grid = max(shot.days, shot.clock0, 1e-6)

    if shot.kind == "focus":
        N = shot.days
        run = shot.run_s
        if t < IN_S:
            c = rewind(shot.clock0, t, IN_S)
            cam, w = blend_cam(wide_cam(shot.R0, shot.el0, f, shot.sh0),
                               focus_cam(shot.planet, N, c, f), t / IN_S)
        elif t < IN_S + run:
            c = N * trapezoid((t - IN_S) / run)
            cam, w = focus_cam(shot.planet, N, c, f), 1.0
        elif t < dur - OUT_S:
            c = N
            cam, w = focus_cam(shot.planet, N, c, f), 1.0
        else:
            c = N
            u = 1.0 - (t - (dur - OUT_S)) / OUT_S
            cam, w = blend_cam(wide_cam(shot.R1, shot.el1, f, shot.sh1),
                               focus_cam(shot.planet, N, c, f), u)
        return State(shot, c, cam, w, grid, harmony_alpha=(1.0 - w) ** 2)

    u = smootherstep(t / dur)
    cam = wide_cam(loglerp(shot.R0, shot.R1, u), lerp(shot.el0, shot.el1, u), f,
                   lerp(shot.sh0, shot.sh1, u))
    if shot.kind == "comparison":
        c = (rewind(shot.clock0, t, REWIND_S) if t < REWIND_S
             else shot.days * trapezoid((t - REWIND_S) / shot.run_s))
        return State(shot, c, cam, 0.0, grid, harmony_alpha=fade(t, dur, 0.0, 0.0, 0.6))
    if shot.kind == "chapter":
        c = rewind(shot.clock0, t, 2.0)
        return State(shot, c, cam, 0.0, grid, title_alpha=fade(t, dur, 1.0, 1.0, 1.0))
    if shot.kind == "opening":
        return State(shot, 0.0, cam, 0.0, grid, title_alpha=fade(t, dur, 2.0, 1.5, 1.5),
                     clock_alpha=0.0)
    return State(shot, shot.clock0, cam, 0.0, grid, title_alpha=fade(t, dur, 2.0, 0.5, 1.5),
                 harmony_alpha=fade(t, dur, 0.0, dur * 0.5, 1.0))


def spin_display_factor(shot: Shot, name: str) -> float:
    """Scale factor on the drawn surface spin so it never strobes (counters stay true)."""
    fastest = 0.0
    if shot.run_s > 0:
        fastest = shot.days / (shot.run_s * FPS)
    rw = {"focus": IN_S, "comparison": REWIND_S, "chapter": 2.0}.get(shot.kind, 0.0)
    if rw:
        fastest = max(fastest, shot.clock0 / (rw * FPS) * 1.9)   # smootherstep peak speed
    deg = fastest * 360.0 / abs(PLANETS[name].rotation_period_days)
    return min(1.0, MAX_SPIN_DEG_PER_FRAME / deg) if deg > 0 else 1.0


# ═══════════════════════════════════════════════════════════════════════
#  MATERIALS
# ═══════════════════════════════════════════════════════════════════════

def sunlit_group() -> bpy.types.NodeTree:
    """Shared shading group: Lambert light from the Sun's current position (set per
    frame on the `SunPos` node), soft terminator, optional atmosphere rim. Engine-
    independent and correct for every planet at once, however far from the Sun."""
    ng = bpy.data.node_groups.get("SunLit")
    if ng:
        return ng
    ng = bpy.data.node_groups.new("SunLit", 'ShaderNodeTree')
    for name, kind in (("Color", 'NodeSocketColor'), ("Ambient", 'NodeSocketFloat'),
                       ("TwoSided", 'NodeSocketFloat'), ("RimColor", 'NodeSocketColor'),
                       ("RimStrength", 'NodeSocketFloat')):
        ng.interface.new_socket(name, in_out='INPUT', socket_type=kind)
    ng.interface.new_socket("Emission", in_out='OUTPUT', socket_type='NodeSocketColor')
    n, l = ng.nodes, ng.links
    gi, go = n.new('NodeGroupInput'), n.new('NodeGroupOutput')
    geo = n.new('ShaderNodeNewGeometry')
    sun = n.new('ShaderNodeCombineXYZ')
    sun.name = "SunPos"

    def vmath(op, a, b=None):
        node = n.new('ShaderNodeVectorMath')
        node.operation = op
        l.new(a, node.inputs[0])
        if b is not None:
            l.new(b, node.inputs[1])
        return node

    def fmath(op, a, b=None, bval=None):
        node = n.new('ShaderNodeMath')
        node.operation = op
        if isinstance(a, float):
            node.inputs[0].default_value = a
        else:
            l.new(a, node.inputs[0])
        if b is not None:
            l.new(b, node.inputs[1])
        elif bval is not None:
            node.inputs[1].default_value = bval
        return node

    to_sun = vmath('NORMALIZE', vmath('SUBTRACT', sun.outputs[0], geo.outputs['Position']).outputs[0])
    ndl = vmath('DOT_PRODUCT', geo.outputs['Normal'], to_sun.outputs[0]).outputs['Value']
    ndl_abs = fmath('ABSOLUTE', ndl).outputs[0]
    two = n.new('ShaderNodeMix')
    two.data_type = 'FLOAT'
    l.new(gi.outputs["TwoSided"], two.inputs['Factor'])
    l.new(ndl, two.inputs[2])
    l.new(ndl_abs, two.inputs[3])

    lit = n.new('ShaderNodeMapRange')
    lit.clamp = True
    lit.inputs['From Min'].default_value = -0.04
    lit.inputs['From Max'].default_value = 1.0
    l.new(two.outputs[0], lit.inputs['Value'])

    # light = ambient + (1 - ambient) * lit
    one_minus = fmath('SUBTRACT', 1.0, gi.outputs["Ambient"])
    light = fmath('MULTIPLY_ADD', lit.outputs[0], one_minus.outputs[0])
    l.new(gi.outputs["Ambient"], light.inputs[2])

    shaded = n.new('ShaderNodeMix')
    shaded.data_type = 'RGBA'
    shaded.blend_type = 'MULTIPLY'
    shaded.inputs['Factor'].default_value = 1.0
    l.new(gi.outputs["Color"], shaded.inputs[6])
    l.new(light.outputs[0], shaded.inputs[7])

    # Rim: facing^3, only where the Sun reaches (lit hemisphere + a little past it)
    lw = n.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    rim_pow = fmath('POWER', lw.outputs['Facing'], bval=3.0)
    rim_lit = n.new('ShaderNodeMapRange')
    rim_lit.clamp = True
    rim_lit.inputs['From Min'].default_value = -0.25
    rim_lit.inputs['From Max'].default_value = 0.3
    l.new(ndl, rim_lit.inputs['Value'])
    rim_amt = fmath('MULTIPLY', rim_pow.outputs[0], rim_lit.outputs[0])
    rim_amt2 = fmath('MULTIPLY', rim_amt.outputs[0], gi.outputs["RimStrength"])
    rim = n.new('ShaderNodeMix')
    rim.data_type = 'RGBA'
    rim.blend_type = 'ADD'
    l.new(rim_amt2.outputs[0], rim.inputs['Factor'])
    l.new(shaded.outputs[2], rim.inputs[6])
    l.new(gi.outputs["RimColor"], rim.inputs[7])
    l.new(rim.outputs[2], go.inputs["Emission"])
    return ng


# Texture frequency on the unit-radius globes (the procedural materials were tuned
# for tiny spheres; this keeps continents / belts at a believable size up close).
MAP_SCALE = {"mercury": 0.5, "venus": 0.4, "earth": 0.4, "mars": 1.0,
             "jupiter": 0.1, "saturn": 0.12, "uranus": 1.0, "neptune": 0.5}

RIM = {
    "earth": ((0.35, 0.68, 1.0), 0.9), "venus": ((1.0, 0.86, 0.6), 0.45),
    "uranus": ((0.6, 0.95, 1.0), 0.45), "neptune": ((0.4, 0.6, 1.0), 0.45),
    "jupiter": ((1.0, 0.9, 0.75), 0.2), "saturn": ((1.0, 0.9, 0.7), 0.2),
    "mars": ((1.0, 0.7, 0.5), 0.15), "mercury": ((1, 1, 1), 0.05),
}


def convert_to_sunlit(mat: bpy.types.Material, ambient: float, two_sided: bool = False,
                      rim=((1, 1, 1), 0.0), strength: float = 1.15):
    """Keep the procedural base colour (and alpha) of a Principled material, but shade
    it with the SunLit group through an Emission shader."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    out = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')

    grp = nodes.new('ShaderNodeGroup')
    grp.node_tree = sunlit_group()
    base_in = bsdf.inputs['Base Color']
    if base_in.is_linked:
        links.new(base_in.links[0].from_socket, grp.inputs["Color"])
    else:
        grp.inputs["Color"].default_value = base_in.default_value
    grp.inputs["Ambient"].default_value = ambient
    grp.inputs["TwoSided"].default_value = 1.0 if two_sided else 0.0
    grp.inputs["RimColor"].default_value = (*rim[0], 1.0)
    grp.inputs["RimStrength"].default_value = rim[1]

    em = nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = strength
    links.new(grp.outputs["Emission"], em.inputs['Color'])
    alpha_in = bsdf.inputs['Alpha']
    if alpha_in.is_linked:
        tr = nodes.new('ShaderNodeBsdfTransparent')
        mix = nodes.new('ShaderNodeMixShader')
        links.new(alpha_in.links[0].from_socket, mix.inputs['Fac'])
        links.new(tr.outputs[0], mix.inputs[1])
        links.new(em.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs['Surface'])
        mat.surface_render_method = 'BLENDED'
    else:
        links.new(em.outputs[0], out.inputs['Surface'])


def fade_mat(name: str, color: tuple, strength: float) -> tuple[bpy.types.Material, bpy.types.Node]:
    """Emission blended over the scene; returns the Mix node whose Fac is the opacity."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    em = nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color[:3], 1.0)
    em.inputs['Strength'].default_value = strength
    tr = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    mix.inputs['Fac'].default_value = 1.0
    links.new(tr.outputs[0], mix.inputs[1])
    links.new(em.outputs[0], mix.inputs[2])
    out = nodes.new('ShaderNodeOutputMaterial')
    links.new(mix.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    return mat, mix


# ═══════════════════════════════════════════════════════════════════════
#  SCENE OBJECTS
# ═══════════════════════════════════════════════════════════════════════

def new_empty(name: str, parent=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(o)
    o.parent = parent
    return o


def new_mesh_obj(name: str):
    me = bpy.data.meshes.new(name)
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    return o


def primitive(kind: str, name: str, **kw):
    getattr(bpy.ops.mesh, f"primitive_{kind}_add")(**kw)
    o = bpy.context.active_object
    o.name = name
    return o


class Scene:
    """All objects plus the per-frame update."""

    def __init__(self, res: tuple[int, int], samples: int, lang: str):
        self.S = STRINGS[lang]
        self.res = res
        self.half_h = HALF_W * res[1] / res[0]
        clear_scene()
        setup_render_settings(res, samples)
        setup_world_starfield()
        scene = bpy.context.scene
        # Shading is emission-based (SunLit), so show the colours as authored.
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'

        # Camera + screen-space HUD root (scaled toward the camera to stay in front)
        cam_data = bpy.data.cameras.new("JourneyCam")
        cam_data.lens = LENS_MM
        cam_data.sensor_fit = 'HORIZONTAL'
        cam_data.sensor_width = SENSOR_MM
        self.cam = bpy.data.objects.new("JourneyCam", cam_data)
        bpy.context.collection.objects.link(self.cam)
        scene.camera = self.cam
        self.hud_root = new_empty("HUD_Root", self.cam)

        # Sun (existing shader), scaled by an empty so it keeps a minimum size
        create_sun()
        self.sun = new_empty("SunFrame")
        for name in ("Sun", "Sun_Corona"):
            bpy.data.objects[name].parent = self.sun
        light = bpy.data.objects.get("SunLight")
        if light:
            bpy.data.objects.remove(light, do_unlink=True)
        self.sun_r0 = sun_visual_radius()

        self._build_planets()
        self._build_lines()
        self._build_annotations()
        self._build_hud()

    # ── planets ──────────────────────────────────────────────────────
    def _build_planets(self):
        self.rigs = {}
        for name in PLANET_ORDER:
            p = PLANETS[name]
            frame = new_empty(f"Frame_{name}")
            body = primitive("uv_sphere", f"Body_{name}", segments=96, ring_count=48, radius=1.0)
            bpy.ops.object.shade_smooth()
            body.parent = frame
            mat = build_planet_material(name)
            for node in mat.node_tree.nodes:
                if node.type == 'MAPPING':
                    node.inputs['Scale'].default_value = (MAP_SCALE[name],) * 3
            amount = add_meridian_markers(mat)
            amount.outputs[0].default_value = 0.0
            convert_to_sunlit(mat, ambient=0.035, rim=RIM[name])
            body.data.materials.append(mat)
            if name == "saturn":
                ring = create_saturn_rings(body, 1.0)
                ring.parent = frame
                ring.location = (0.0, 0.0, 0.0)
                ring.rotation_euler = (0.0, 0.0, 0.0)
                convert_to_sunlit(ring.active_material, ambient=0.2, two_sided=True, strength=1.0)
            k, n = spin_axis(name), orbit_normal(name)
            r_nom = planet_visual_radius(p.mean_radius_km)
            self.rigs[name] = {
                "frame": frame, "body": body, "meridian": amount, "k": k, "n": n,
                "basis": axis_basis(k, n), "r_nom": r_nom,
                "size": (r_nom / planet_visual_radius(6371.0)) ** 0.35,
            }

    # ── trails, guides, spokes, wedges ───────────────────────────────
    def _build_lines(self):
        self.trails, self.guides, self.spokes, self.wedges = {}, {}, {}, {}
        for name in PLANET_ORDER:
            color = TRAIL_COLORS[name]

            tr = new_curve(f"Trail_{name}")
            glow(tr, color, 2.4)
            self.trails[name] = tr

            gd = new_curve(f"Guide_{name}")
            gmat, gmix = fade_mat(f"GuideMat_{name}", color, 0.9)
            gd.data.materials.append(gmat)
            self.guides[name] = (gd, gmix)

            sp = new_curve(f"Spoke_{name}")
            glow(sp, color, 0.9)
            self.spokes[name] = sp

            wd = new_mesh_obj(f"Wedge_{name}")
            wmat, wmix = fade_mat(f"WedgeMat_{name}", color, 0.8)
            wd.data.materials.append(wmat)
            self.wedges[name] = (wd, wmix)

        self.sweep_arc = new_curve("SweepArc")
        glow(self.sweep_arc, (1, 1, 1), 2.0)
        self.sweep_label = make_text("SweepLabel", "", (0, 0, 0), 1.0, (1, 1, 1), 'CENTER', 2.0)
        self.sweep_label["base_strength"] = 2.0

    # ── focus annotations: spin axis, orbit normal, tilt arc ─────────
    def _build_annotations(self):
        self.rod = primitive("cylinder", "Anno_SpinAxis", vertices=24, radius=1.0, depth=2.0)
        glow(self.rod, (0.92, 0.94, 1.0), 1.4)
        self.cap = primitive("uv_sphere", "Anno_North", segments=24, ring_count=12, radius=1.0)
        glow(self.cap, (0.3, 1.0, 0.65), 3.0)
        self.normal = primitive("cylinder", "Anno_OrbitNormal", vertices=16, radius=1.0, depth=2.0)
        glow(self.normal, (0.55, 0.58, 0.64), 0.9)
        self.tilt_arc = new_curve("Anno_TiltArc")
        glow(self.tilt_arc, (1.0, 0.84, 0.4), 2.2)
        self.tilt_label = make_text("Anno_TiltLabel", "", (0, 0, 0), 1.0, (1.0, 0.86, 0.45), 'CENTER', 2.2)
        self.tilt_label["base_strength"] = 2.2
        self.annos = (self.rod, self.cap, self.normal, self.tilt_arc, self.tilt_label)

    # ── HUD (unit-depth coordinates, parented to the HUD root) ───────
    def _text(self, key, body, x, y, size, color, align='LEFT', strength=1.7):
        o = make_text(f"HUD_{key}", body, (x, y, -1.0), size * self.half_h, color, align, strength,
                      self.hud_root)
        o["base_strength"] = strength
        return o

    def _rect(self, key, x0, y, w, h, color, strength, z=-1.0):
        o = make_rect(f"HUD_{key}", x0, y, w, h, color, strength, z)
        o.parent = self.hud_root
        o["base_strength"] = strength
        return o

    def _build_hud(self):
        hw, hh = HALF_W, self.half_h
        S = self.S
        # Focus panel (left)
        x = -hw * 0.92
        self.f_header = self._text("FHeader", "", x, hh * 0.80, 0.060, (0.62, 0.72, 0.82))
        self.f_name = self._text("FName", "", x, hh * 0.66, 0.160, (1, 1, 1), strength=2.2)
        self.f_rows = [self._text(f"FRow{i}", "", x, hh * (0.50 - 0.092 * i), 0.062,
                                  (0.92, 0.94, 0.97) if i else (1.0, 0.86, 0.42))
                       for i in range(8)]
        self.f_legend = self._text("FLegend", S["legend"], hw * 0.94, -hh * 0.80, 0.042,
                                   (0.55, 0.60, 0.68), 'RIGHT', strength=1.2)
        self.f_slowed = self._text("FSlowed", S["slowed"], hw * 0.94, -hh * 0.72, 0.042,
                                   (0.55, 0.60, 0.68), 'RIGHT', strength=1.2)
        self.focus_hud = [self.f_header, self.f_name, *self.f_rows, self.f_legend]

        # Harmony panel (right): one row per planet
        hx = hw * 0.50
        self.h_title = self._text("HTitle", S["harmony"], hx, hh * 0.52, 0.055, (0.75, 0.80, 0.88))
        self.h_rows = []
        bar_w = hw * 0.20
        for i, name in enumerate(PLANET_ORDER):
            y = hh * (0.38 - 0.13 * i)
            color = TRAIL_COLORS[name]
            label = self._text(f"HName{i}", S["names"][name], hx, y, 0.055, color, strength=2.0)
            value = self._text(f"HVal{i}", "", hx + hw * 0.43, y, 0.050, (0.9, 0.92, 0.95), 'RIGHT')
            bg = self._rect(f"HBarBg{i}", hx, y - hh * 0.055, bar_w * 2.15, hh * 0.012,
                            (0.22, 0.23, 0.26), 1.0)
            fill = self._rect(f"HBar{i}", hx, y - hh * 0.055, 1e-4, hh * 0.012, color, 2.4, z=-0.9999)
            self.h_rows.append((name, label, value, bg, fill, bar_w * 2.15))

        # Clock (top right)
        self.c_label = self._text("ClockLbl", S["clock"], hw * 0.94, hh * 0.86, 0.055,
                                  (1.0, 0.82, 0.35), 'RIGHT')
        self.c_value = self._text("Clock", "", hw * 0.94, hh * 0.74, 0.150, (1.0, 0.86, 0.40),
                                  'RIGHT', 2.0)
        cbw = hw * 0.30
        self.c_bar_bg = self._rect("ClockBarBg", hw * 0.94 - cbw, hh * 0.63, cbw, hh * 0.010,
                                   (0.25, 0.25, 0.28), 1.0)
        self.c_bar = self._rect("ClockBar", hw * 0.94 - cbw, hh * 0.63, 1e-4, hh * 0.010,
                                (1.0, 0.82, 0.35), 2.0, z=-0.9999)
        self.c_bar_w = cbw

        # Title card + footer
        self.t_lines = [self._text("Title0", "", 0, hh * 0.22, 0.20, (1.0, 0.95, 0.85), 'CENTER', 2.4),
                        self._text("Title1", "", 0, hh * 0.04, 0.10, (0.75, 0.80, 0.88), 'CENTER', 2.0),
                        self._text("Title2", "", 0, -hh * 0.10, 0.066, (0.60, 0.65, 0.72), 'CENTER', 1.8)]
        self.foot = self._text("Foot", S["foot"], 0, -hh * 0.92, 0.040, (0.50, 0.55, 0.62), 'CENTER', 1.1)

    # ═══════════════════════════════════════════════════════════════
    #  PER FRAME
    # ═══════════════════════════════════════════════════════════════
    def update(self, st: State, f: int):
        shot, c, cam, w = st.shot, st.clock, st.cam, st.w
        focus = shot.planet if shot.kind == "focus" else None
        O = cam.target                                        # floating origin
        cam_world = add(cam.target, mul(cam.direction, cam.dist))

        def rel(p):
            return sub(p, O)

        # Camera
        cd = self.cam.data
        cd.clip_start = cam.dist * 0.06
        cd.clip_end = cam.dist * 4.0 + 160.0
        self.cam.location = mul(cam.direction, cam.dist)
        self.cam.rotation_euler = Vector(mul(cam.direction, -1.0)).to_track_quat('-Z', 'Y').to_euler()
        h = cd.clip_start * 3.0
        self.hud_root.scale = (h, h, h)

        # Sun
        sunlit_group().nodes["SunPos"].inputs[0].default_value = -O[0]
        sunlit_group().nodes["SunPos"].inputs[1].default_value = -O[1]
        sunlit_group().nodes["SunPos"].inputs[2].default_value = -O[2]
        view_R = cam.dist / WIDE_DIST
        r_sun = max(min(self.sun_r0, 0.06 * view_R), MIN_SUN * length(cam_world))
        self.r_sun = r_sun
        self.sun.matrix_world = Matrix.Translation(rel((0.0, 0.0, 0.0))) @ Matrix.Scale(r_sun / self.sun_r0, 4)

        # Planets
        positions = {}
        for name, rig in self.rigs.items():
            P = pos(name, c)
            positions[name] = P
            d_cam = length(sub(P, cam_world))
            r_base = loglerp(rig["r_nom"], cam.r_focus, w) if name == focus else rig["r_nom"]
            r = max(r_base, MIN_PLANET * rig["size"] * d_cam)
            rig["r"] = r
            rig["frame"].matrix_world = (Matrix.Translation(rel(P)) @ rig["basis"] @ Matrix.Scale(r, 4))
            p = PLANETS[name]
            factor = spin_display_factor(shot, name)
            spin = 360.0 * c / abs(p.rotation_period_days) * factor
            rig["body"].rotation_euler = (0.0, 0.0, math.radians(spin % 360.0))
            anno = smootherstep((w - 0.6) / 0.4) if name == focus else 0.0
            rig["meridian"].outputs[0].default_value = anno if factor >= 1.0 else 0.0
            rig["spin_factor"] = factor

        # Trails / guides / spokes / wedges
        wide = 1.0 - w
        for name in PLANET_ORDER:
            P = positions[name]
            d_cam = length(sub(P, cam_world))
            is_focus = name == focus
            times = trail_times(c, st.grid_days)
            pts = [rel(pos(name, t)) for t in times]
            set_curve_points(self.trails[name], pts, (0.0008 if is_focus else 0.0006) * d_cam)
            set_alpha(self.trails[name], 1.0 if (is_focus or focus is None) else 0.35 + 0.65 * wide)

            gd, gmix = self.guides[name]
            ga = 0.30 * wide + (0.40 * w if is_focus else 0.0)
            if ga >= 0.01:
                set_curve_points(gd, [rel(pos(name, t)) for t in guide_times(name, c, shot.days, is_focus)],
                                 0.00045 * d_cam)
            gmix.inputs['Fac'].default_value = ga
            gd.hide_render = ga < 0.01

            sp = self.spokes[name]
            sa = 0.30 * wide * (0.35 if focus and not is_focus else 1.0)
            d_near = min(d_cam, length(cam_world))
            set_curve_points(sp, [rel((0.0, 0.0, 0.0)), rel(P)], 0.0002 * d_near)
            set_alpha(sp, sa)

            wd, wmix = self.wedges[name]
            wa = wide * (0.30 if is_focus else (0.08 if focus else 0.16))
            wa *= min(1.0, max(0.08, ((cam.dist / WIDE_DIST) / PLANETS[name].semi_major_axis_au) ** 2))
            period = PLANETS[name].orbital_period_days
            lap = [p for t, p in zip(times, pts) if t >= c - period]
            if wa > 0.01 and len(lap) >= 2:
                me = wd.data
                me.clear_geometry()
                verts = [rel((0.0, 0.0, 0.0))] + lap
                me.from_pydata(verts, [], [(0, i, i + 1) for i in range(1, len(verts) - 1)])
                wmix.inputs['Fac'].default_value = wa
                wd.hide_render = False
            else:
                wd.hide_render = True

        self._update_sweep_label(focus, c, cam_world, wide, rel)
        self._update_annotations(focus, positions, cam_world, w, rel)
        self._update_hud(st, focus, c)

    def _update_sweep_label(self, focus, c, cam_world, wide, rel):
        a = smootherstep((wide - 0.3) / 0.5) if focus else 0.0
        if a < 0.01 or c <= 0:
            self.sweep_arc.hide_render = self.sweep_label.hide_render = True
            return
        p = PLANETS[focus]
        swept = orbital_advance_deg(p, 0.0, c)
        a0 = math.atan2(pos(focus, 0.0)[1], pos(focus, 0.0)[0])
        rad = max(0.30 * p.semi_major_axis_au, 1.8 * self.r_sun)
        n = max(8, int(min(abs(swept), 360.0) / 3.0))
        span = math.radians(min(swept, 360.0))
        pts = [rel((rad * math.cos(a0 + span * i / n), rad * math.sin(a0 + span * i / n), 0.0))
               for i in range(n + 1)]
        d_cam = length(sub((0.0, 0.0, 0.0), cam_world))
        set_curve_points(self.sweep_arc, pts, 0.0008 * d_cam)
        self.sweep_arc.active_material.node_tree.nodes["Emission"].inputs['Color'].default_value = \
            (*TRAIL_COLORS[focus], 1.0)
        set_alpha(self.sweep_arc, a)
        mid = a0 + span * 0.5
        lp = (rad * 1.35 * math.cos(mid), rad * 1.35 * math.sin(mid), 0.0)
        laps = swept / 360.0
        self.sweep_label.data.body = (f"+{swept:.1f}°" if laps < 1.0 else
                                      f"+{swept:.0f}°  ({laps:.2f} {self.S['laps']})")
        size = 0.028 * length(sub(lp, cam_world))
        self.sweep_label.matrix_world = (Matrix.Translation(rel(lp)) @
                                         self.cam.matrix_world.to_quaternion().to_matrix().to_4x4() @
                                         Matrix.Scale(size, 4))
        set_alpha(self.sweep_label, a)

    def _update_annotations(self, focus, positions, cam_world, w, rel):
        a = smootherstep((w - 0.6) / 0.4) if focus else 0.0
        if a < 0.01:
            for o in self.annos:
                o.hide_render = True
            return
        rig = self.rigs[focus]
        P, r, k, n = positions[focus], rig["r"], rig["k"], rig["n"]
        cp = rel(P)
        L_rod = 2.6 * r if focus == "saturn" else 1.45 * r
        self.rod.matrix_world = (Matrix.Translation(cp) @ axis_basis(k, n) @
                                 Matrix.Diagonal((0.012 * r, 0.012 * r, L_rod, 1.0)))
        self.cap.matrix_world = Matrix.Translation(add(cp, mul(k, L_rod))) @ Matrix.Scale(0.05 * r, 4)
        self.normal.matrix_world = (Matrix.Translation(cp) @ axis_basis(n, k) @
                                    Matrix.Diagonal((0.006 * r, 0.006 * r, 0.9 * L_rod, 1.0)))
        for o in (self.rod, self.cap, self.normal):
            set_alpha(o, a)

        tilt = obliquity_deg(focus)
        if tilt < 1.0:
            self.tilt_arc.hide_render = True
        else:
            e2 = sub(k, mul(n, dot(k, n)))
            e2 = normalize(e2) if length(e2) > 1e-6 else normalize(cross(n, (1.0, 0.0, 0.0)))
            R = 1.22 * r
            steps = max(6, int(tilt / 3.0))
            th = math.radians(tilt)
            pts = [add(cp, mul(add(mul(n, math.cos(th * i / steps)), mul(e2, math.sin(th * i / steps))), R))
                   for i in range(steps + 1)]
            set_curve_points(self.tilt_arc, pts, 0.008 * r)
            set_alpha(self.tilt_arc, a)
        half = math.radians(tilt) * 0.5
        e2 = sub(k, mul(n, dot(k, n)))
        e2 = normalize(e2) if length(e2) > 1e-6 else normalize(cross(n, (1.0, 0.0, 0.0)))
        lp = add(cp, mul(add(mul(n, math.cos(half)), mul(e2, math.sin(half))), 1.5 * r))
        self.tilt_label.data.body = f"{tilt:.1f}°"
        self.tilt_label.matrix_world = (Matrix.Translation(lp) @
                                        self.cam.matrix_world.to_quaternion().to_matrix().to_4x4() @
                                        Matrix.Scale(0.2 * r, 4))
        set_alpha(self.tilt_label, a)

    def _update_hud(self, st: State, focus, c):
        S, shot = self.S, st.shot
        act = int(shot.days) if shot.days else 1

        # Clock
        for o in (self.c_label, self.c_value, self.c_bar_bg, self.c_bar):
            set_alpha(o, st.clock_alpha)
        if act == 1:
            mins = int(c * 24.0 * 60.0 + 1e-6)
            self.c_value.data.body = f"{mins // 60:02d}:{mins % 60:02d}"
        else:
            self.c_value.data.body = f"{S['day']} {c:.1f}"
        self.c_bar.scale.x = max(1e-4, self.c_bar_w * clamp01(c / max(shot.days, 1e-9)))

        # Focus panel
        fa = smootherstep((st.w - 0.5) / 0.5) if focus else 0.0
        for o in self.focus_hud:
            set_alpha(o, fa)
        slowed = focus is not None and self.rigs[focus]["spin_factor"] < 1.0
        set_alpha(self.f_slowed, fa if slowed else 0.0)
        if fa > 0.01:
            p = PLANETS[focus]
            N = shot.days
            self.f_header.data.body = S["act"].get(act, "")
            self.f_name.data.body = S["names"][focus]
            self.f_name.active_material.node_tree.nodes["Emission"].inputs['Color'].default_value = \
                (*TRAIL_COLORS[focus], 1.0)
            if act == 1:
                mins = int(c * 24.0 * 60.0 + 1e-6)
                tm = f"{mins // 60:02d}:{mins % 60:02d} / 24:00"
                t_row = f"{S['time']}   {tm}"
            else:
                t_row = f"{S['day']}   {c:.1f} / {N:.0f}"
            km = distance_km(focus, N, c)
            dist = (f"{km:,.0f} km".replace(",", " ") if km < 1e7
                    else f"{km / 1e6:,.2f} {S['million_km']}")
            swept = orbital_advance_deg(p, 0.0, c) if c > 0 else 0.0
            laps = swept / 360.0
            orbit = (f"+{swept:.2f}°  ·  {100.0 * laps:.2f}% {S['of_orbit']}" if laps < 1.0
                     else f"+{swept:.0f}°  ·  {laps:.2f} {S['laps']}")
            v = speed_kms(focus, c, max(1e-4, N * 1e-4))
            sun_au = length(pos(focus, c))
            rs = rotation_state(focus, c)
            spin, local = abs(rs.spin_deg), rs.local_days
            retro = f"  ({S['retro']})" if p.rotation_period_days < 0 else ""
            rows = [
                t_row,
                f"{S['distance']}   {dist}",
                f"{S['orbit_angle']}   {orbit}",
                f"{S['speed']}   {v:.1f} km/s",
                f"{S['sun_dist']}   {sun_au:.3f} AU",
                f"{S['spin']}   {spin:,.1f}°  ·  {spin / 360.0:,.2f} {S['turns']}{retro}".replace(",", " "),
                f"{S['tilt']}   {obliquity_deg(focus):.1f}°",
                f"{S['local_days']}   {local:,.3f}".replace(",", " "),
            ]
            for o, txt in zip(self.f_rows, rows):
                o.data.body = txt

        # Harmony panel
        ha = st.harmony_alpha
        set_alpha(self.h_title, ha)
        for name, label, value, bg, fill, bw in self.h_rows:
            dim = 0.45 if (focus and name != focus) else 1.0
            for o in (label, value, bg, fill):
                set_alpha(o, ha * dim)
            if ha * dim > 0.01:
                swept = orbital_advance_deg(PLANETS[name], 0.0, c) if c > 0 else 0.0
                laps = swept / 360.0
                value.data.body = (f"+{swept:.2f}°" if laps < 0.1 else
                                   f"+{swept:.1f}°  ·  {laps:.2f} {S['laps']}")
                lap_progress = laps % 1.0 if (laps % 1.0 > 1e-6 or laps == 0.0) else 1.0
                fill.scale.x = max(1e-4, bw * lap_progress)

        # Titles
        ta = st.title_alpha
        lines = ("", "", "")
        if shot.kind == "opening":
            lines = S["opening"]
        elif shot.kind == "chapter":
            lines = S["chapter"].get(act, ("", "", ""))
        elif shot.kind == "outro":
            lines = S["outro"]
        for o, txt in zip(self.t_lines, lines):
            o.data.body = txt
            set_alpha(o, ta if txt else 0.0)


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="Continuous 9:25 system-journey render")
    ap.add_argument("--lang", choices=sorted(STRINGS), default="en")
    ap.add_argument("--res", nargs=2, type=int, default=(2560, 1440))
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--frames", nargs=2, type=int, metavar=("START", "END"))
    ap.add_argument("--step", type=int, default=1, help="Render every Nth frame (quick preview)")
    ap.add_argument("--still", nargs="+", type=int, help="Render these frames as stills and exit")
    ap.add_argument("--list-shots", action="store_true")
    ap.add_argument("--test", type=int, metavar="START",
                    help="Render a fresh 20 s clip from this frame into its own folder and encode it")
    args = ap.parse_args(argv)

    shots = load_shots()
    total = shots[-1].f1 + 1
    if args.list_shots:
        for s in shots:
            print(f"{s.id:15} {s.kind:10} {s.f0:6d}-{s.f1:6d}  {s.dur:5.1f}s  "
                  f"clock {s.clock0:g}->{s.clock1:g}  R {s.R0:.1f}->{s.R1:.1f}")
        print(f"total {total} frames = {total / FPS:.1f}s")
        return

    out = output_dir()
    scene = Scene(tuple(args.res), args.samples, args.lang)
    rscene = bpy.context.scene

    if args.still:
        still_dir = out / "journey_stills"
        still_dir.mkdir(parents=True, exist_ok=True)
        for f in args.still:
            st = evaluate(shots, f)
            scene.update(st, f)
            rscene.render.filepath = str(still_dir / f"journey_{args.lang}_{f:06d}_{st.shot.id}.png")
            bpy.ops.render.render(write_still=True)
        return

    if args.test is not None:
        f0 = max(0, min(args.test, total - TEST_FRAMES))
        f1 = f0 + TEST_FRAMES - 1
        frames_dir = out / f"test_journey_{args.lang}_{f0:06d}_frames"
        for old in frames_dir.glob("frame_*.png"):      # a test always reflects the current code
            old.unlink()
    else:
        frames_dir = out / f"journey_{args.lang}_frames"
        f0, f1 = args.frames if args.frames else (0, total - 1)
    frames_dir.mkdir(parents=True, exist_ok=True)
    for f in range(f0, f1 + 1, max(1, args.step)):
        path = frames_dir / f"frame_{f:06d}.png"
        if path.exists() and path.stat().st_size > 0:
            continue
        st = evaluate(shots, f)
        scene.update(st, f)
        rscene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if f % 30 == 0:
            print(f"  frame {f}/{total - 1}  {st.shot.id}  clock {st.clock:.3f} d")

    if args.test is not None:
        mp4 = encode_frames(frames_dir, out / "final" / f"test_journey_{args.lang}_{f0:06d}.mp4",
                            FPS, start_number=f0)
        print(f"✅ Test clip: {mp4}")
    elif args.step == 1 and len(list(frames_dir.glob("frame_*.png"))) >= total:
        mp4 = encode_frames(frames_dir, out / "final" /
                            f"solar_system_journey_{args.lang}_{args.res[1]}p.mp4", FPS)
        print(f"✅ {mp4}")
    else:
        print("Partial range rendered; encode skipped.")


if __name__ == "__main__":
    main()
