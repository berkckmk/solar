"""Camera pose, framing and projection shared by the 3D and 2D passes (pure Python).

The camera always looks at a target point from a fixed direction (elevation,
azimuth). Where that target lands on screen is set with the lens shift, not by
turning the camera, so the Sun can sit at the centre of the *animation area*
(not of the whole frame) without any perspective tilt. Distance is solved so a
set of 3D points (whole orbits, over the whole shot) fits a screen rectangle.

`project()` uses exactly Blender's perspective + shift model (horizontal sensor
fit); the 2D layer therefore lines up with the rendered planets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

LENS_MM = 35.0
SENSOR_MM = 36.0
K = LENS_MM / SENSOR_MM            # image width units per unit of x/depth

Vec = tuple[float, float, float]


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def direction(el_deg: float, az_deg: float) -> Vec:
    """Unit vector from the target towards the camera."""
    el, az = math.radians(el_deg), math.radians(az_deg)
    return (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))


@dataclass(frozen=True)
class Pose:
    target: Vec
    back: Vec              # unit, target -> camera (camera local +Z)
    right: Vec             # camera local +X
    up: Vec                # camera local +Y
    dist: float
    shift_x: float
    shift_y: float
    aspect: float          # width / height

    @property
    def location(self) -> Vec:
        return _add(self.target, _mul(self.back, self.dist))

    def matrix_rows(self):
        """3x3 rotation (columns = camera axes) as row tuples, for Blender."""
        r, u, b = self.right, self.up, self.back
        return ((r[0], u[0], b[0]), (r[1], u[1], b[1]), (r[2], u[2], b[2]))


def make_pose(target: Vec, back: Vec, dist: float, screen_uv, aspect: float) -> Pose:
    fwd = _mul(back, -1.0)
    right = _cross(fwd, (0.0, 0.0, 1.0))
    if _dot(right, right) < 1e-12:
        right = (1.0, 0.0, 0.0)
    right = _norm(right)
    up = _cross(right, fwd)
    u, v = screen_uv
    return Pose(target, back, right, up, dist, 0.5 - u, (v - 0.5) / aspect, aspect)


def project(pose: Pose, p: Vec):
    """World point -> (u, v, depth): u 0..1 left→right, v 0..1 top→bottom."""
    rel = _sub(p, pose.location)
    x, y, z = _dot(rel, pose.right), _dot(rel, pose.up), _dot(rel, pose.back)
    depth = -z
    if depth <= 1e-9:
        return None
    u = 0.5 + K * x / depth - pose.shift_x
    v = 0.5 - K * pose.aspect * y / depth + pose.shift_y * pose.aspect
    return u, v, depth


def world_per_pixel(pose: Pose, depth: float, width_px: int) -> float:
    """Size in world units of one pixel at the given depth."""
    return depth / (K * width_px)


def fit_distance(points, target: Vec, back: Vec, rect, aspect: float) -> float:
    """Smallest distance at which every point projects inside `rect`
    (target placed at the rectangle centre)."""
    uc, vc = 0.5 * (rect[0] + rect[2]), 0.5 * (rect[1] + rect[3])

    def fits(d):
        pose = make_pose(target, back, d, (uc, vc), aspect)
        for p in points:
            pr = project(pose, p)
            if pr is None:
                return False
            u, v, _ = pr
            if not (rect[0] <= u <= rect[2] and rect[1] <= v <= rect[3]):
                return False
        return True

    lo, hi = 1e-4, 1e5
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        lo, hi = (lo, mid) if fits(mid) else (mid, hi)
    return hi


def bbox_center(points) -> Vec:
    xs, ys, zs = zip(*points)
    return (0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys)), 0.5 * (min(zs) + max(zs)))


@dataclass(frozen=True)
class View:
    """A static camera framing: target placed at `screen`, seen from `back`."""
    target: Vec
    back: Vec
    dist: float
    screen: tuple[float, float]


def smootherstep(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def blend(a: View, b: View, s: float, aspect: float) -> Pose:
    """Camera between two views (s: 0 = a, 1 = b), eased; its own time curve,
    independent of the simulation clock. Log-distance zoom; target and screen
    anchor converge in step with the distance, so nothing swings out of frame."""
    s = smootherstep(s)
    if abs(math.log(a.dist / b.dist)) < 0.05:
        frac = 1.0 - s
        dist = a.dist + (b.dist - a.dist) * s
    else:
        dist = math.exp(math.log(a.dist) + (math.log(b.dist) - math.log(a.dist)) * s)
        frac = (dist - b.dist) / (a.dist - b.dist)
    target = _add(b.target, _mul(_sub(a.target, b.target), frac))
    screen = (b.screen[0] + (a.screen[0] - b.screen[0]) * frac,
              b.screen[1] + (a.screen[1] - b.screen[1]) * frac)
    back = _norm(_add(_mul(a.back, 1.0 - s), _mul(b.back, s)))
    return make_pose(target, back, dist, screen, aspect)


def still(view: View, aspect: float) -> Pose:
    return make_pose(view.target, view.back, view.dist, view.screen, aspect)
