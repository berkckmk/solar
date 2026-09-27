"""20 s sample: one planet's experiment inside the shared-clock story (pure Python).

Beats (seconds):
  0-2    question over the whole (inner) system, clock at day 0
  2-4    the selected orbit lights up, camera moves in, name label, then the panel
  4-12   the shared clock runs 0 -> N days; path, start marker, live results
  12-15  clock holds at N; result sentence built from the computed values
  15-18  camera back to the system, clock still N; result flies into its table row
  18-20  next planet highlighted, "same N days", labelled rewind to day 0

One simulation clock (`days`) feeds positions, spin, counters and table. The
camera has its own easing curve and never touches the clock.
"""

from __future__ import annotations

import math
from functools import lru_cache

from science.planet_data import PLANETS, PLANET_ORDER, AU_KM
from science.kepler import heliocentric_position
from science.rotation import orbital_advance_deg, rotation_state, solar_day_days

from . import camera as C
from . import layout as L

FPS = 30
EL, AZ = 62.0, -90.0          # one viewing direction for the whole sample: no idle rotation


# ── physics (AU, days) ──────────────────────────────────────────────────
@lru_cache(maxsize=400_000)
def pos(name: str, t: float):
    s = heliocentric_position(PLANETS[name], t)
    return (s.x / AU_KM, s.y / AU_KM, s.z / AU_KM)


@lru_cache(maxsize=None)
def orbit_points(name: str, n: int = 360):
    period = PLANETS[name].orbital_period_days
    return tuple(pos(name, period * i / n) for i in range(n + 1))


@lru_cache(maxsize=None)
def _cum_km(name: str, days: float, n: int = 3000):
    p = PLANETS[name]
    out, prev = [0.0], heliocentric_position(p, 0.0)
    for i in range(1, n + 1):
        cur = heliocentric_position(p, days * i / n)
        out.append(out[-1] + math.dist((prev.x, prev.y, prev.z), (cur.x, cur.y, cur.z)))
        prev = cur
    return tuple(out)


def metrics(name: str, days_total: float, c: float) -> dict:
    """Every number shown on screen for one planet at simulation time c."""
    p = PLANETS[name]
    table = _cum_km(name, days_total)
    x = min(1.0, max(0.0, c / days_total)) * (len(table) - 1)
    i = min(int(x), len(table) - 2)
    km = table[i] + (table[i + 1] - table[i]) * (x - i)
    h = max(1e-4, days_total * 1e-4)
    a, b = heliocentric_position(p, c - h), heliocentric_position(p, c + h)
    speed = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) / (2 * h * 86_400.0)
    swept = orbital_advance_deg(p, 0.0, c) if c > 0 else 0.0
    rs = rotation_state(name, c)
    return {
        "km": km, "swept_deg": swept, "lap_by_angle": swept / 360.0,
        "period_fraction": c / p.orbital_period_days, "speed": speed,
        "sun_au": math.sqrt(sum(v * v for v in pos(name, c))),
        "spin_deg": abs(rs.spin_deg), "spin_turns": rs.spin_turns,
        "solar_days": rs.local_days, "solar_day_len": abs(solar_day_days(p)),
    }


# ── easing ──────────────────────────────────────────────────────────────
def ramp(t: float, t0: float, t1: float) -> float:
    return C.smootherstep((t - t0) / (t1 - t0))


def trapezoid(u: float, a: float = 0.075) -> float:
    u = min(1.0, max(0.0, u))
    v = 1.0 / (1.0 - a)
    if u < a:
        return 0.5 * v * u * u / a
    if u > 1.0 - a:
        return 1.0 - 0.5 * v * (1.0 - u) ** 2 / a
    return v * (u - 0.5 * a)


# ── the sample ──────────────────────────────────────────────────────────
class Sample:
    DUR = 20.0
    RUN = (4.0, 12.0)
    CAM_IN = (2.25, 3.85)
    CAM_OUT = (15.0, 17.2)
    REWIND = (18.7, 19.7)

    def __init__(self, planet: str = "mercury", next_planet: str = "venus", days: float = 30.0,
                 aspect: float = 16 / 9, context=("mercury", "venus", "earth", "mars")):
        self.planet, self.next_planet, self.days, self.aspect = planet, next_planet, days, aspect
        self.frames = int(round(self.DUR * FPS))
        self.context = context
        # the only planets drawn (3D and 2D): the selected one and its context
        self.shown = tuple(dict.fromkeys((planet,) + tuple(context)))
        back = C.direction(EL, AZ)

        m_v = L.PX["planet"] + 0.03
        pts = [p for n in context for p in orbit_points(n)]
        rect = L.inset(L.GENERAL_AREA, m_v / aspect, m_v)
        self.general = C.View((0.0, 0.0, 0.0), back,
                              C.fit_distance(pts, (0.0, 0.0, 0.0), back, rect, aspect),
                              L.center(L.GENERAL_AREA))

        m_v = L.PX["focus_planet"] + L.LABEL_MARGIN
        fp = orbit_points(planet)
        tgt = C.bbox_center(fp)
        rect = L.inset(L.FOCUS_AREA, m_v / aspect, m_v)
        self.focus = C.View(tgt, back, C.fit_distance(fp, tgt, back, rect, aspect),
                            L.center(L.FOCUS_AREA))

        # Kepler note: only when the speed visibly changes during the run
        v0 = metrics(planet, days, 0.0)["speed"]
        v1 = metrics(planet, days, days)["speed"]
        self.kepler_t = None
        if abs(v1 - v0) / v0 > 0.08:
            target = v0 + 0.35 * (v1 - v0)
            for i in range(1, 400):
                t = self.RUN[0] + (self.RUN[1] - self.RUN[0]) * i / 400
                if (metrics(planet, days, self.days_at(t))["speed"] - target) * (v1 - v0) >= 0:
                    self.kepler_t = t
                    break

        # the comparison table returns only once every drawn planet has left its column
        col = L.TABLE_COL
        self.table_in = self.CAM_OUT[0]
        for f in range(int(self.CAM_OUT[0] * FPS), int(self.CAM_OUT[1] * FPS) + 1):
            t = f / FPS
            pose = self.pose(t)
            for name in self.shown:
                uv = C.project(pose, pos(name, self.days_at(t)))
                r = self.planet_px(name, t) + 0.012
                if uv and uv[0] + r / aspect > col[0] and uv[0] - r / aspect < col[2] \
                        and uv[1] + r > col[1] and uv[1] - r < col[3]:
                    self.table_in = t + 1.0 / FPS

    # simulation clock
    def days_at(self, t: float) -> float:
        if t < self.RUN[0]:
            return 0.0
        if t < self.RUN[1]:
            return self.days * trapezoid((t - self.RUN[0]) / (self.RUN[1] - self.RUN[0]))
        if t < self.REWIND[0]:
            return self.days
        if t < self.REWIND[1]:
            return self.days * (1.0 - ramp(t, *self.REWIND))
        return 0.0

    # camera (own time curve)
    def focus_weight(self, t: float) -> float:
        if t < self.CAM_IN[0] or t >= self.CAM_OUT[1]:
            return 0.0
        if t < self.CAM_IN[1]:
            return C.smootherstep((t - self.CAM_IN[0]) / (self.CAM_IN[1] - self.CAM_IN[0]))
        if t < self.CAM_OUT[0]:
            return 1.0
        return 1.0 - C.smootherstep((t - self.CAM_OUT[0]) / (self.CAM_OUT[1] - self.CAM_OUT[0]))

    def pose(self, t: float) -> C.Pose:
        if t < self.CAM_IN[0] or t >= self.CAM_OUT[1]:
            return C.still(self.general, self.aspect)
        if t < self.CAM_IN[1]:
            return C.blend(self.general, self.focus,
                           (t - self.CAM_IN[0]) / (self.CAM_IN[1] - self.CAM_IN[0]), self.aspect)
        if t < self.CAM_OUT[0]:
            return C.still(self.focus, self.aspect)
        return C.blend(self.focus, self.general,
                       (t - self.CAM_OUT[0]) / (self.CAM_OUT[1] - self.CAM_OUT[0]), self.aspect)

    # on-screen sizes (fraction of frame height)
    def planet_px(self, name: str, t: float) -> float:
        base = L.PX["planet"]
        if name == self.planet:
            sel = ramp(t, 2.0, 2.5) * (1.0 - ramp(t, 18.0, 18.4))
            big = base + (0.009 - base) * sel
            return big + (L.PX["focus_planet"] - big) * self.focus_weight(t)
        if name == self.next_planet:
            return base + (0.009 - base) * ramp(t, 18.0, 18.4)
        return base

    def sun_px(self, pose: C.Pose) -> float:
        return L.PX["sun"] * (self.general.dist / pose.dist) ** 0.25

    # what the 2D layer shows
    def ui(self, t: float) -> dict:
        fw = self.focus_weight(t)
        fly0 = self.table_in - 1.0          # the result leaves the info column here
        out = {
            "question": ramp(t, 0.15, 0.5) * (1.0 - ramp(t, 1.8, 2.2)),
            "clock": ramp(t, 0.0, 0.3),
            "select": ramp(t, 2.0, 2.5) * (1.0 - ramp(t, 18.0, 18.4)),
            "pulse": math.exp(-((t - 2.45) / 0.3) ** 2),
            "name_label": ramp(t, 2.5, 2.9),
            "panel": ramp(t, 3.6, 4.1) * (1.0 - ramp(t, fly0, fly0 + 0.5)),
            "legend": ramp(t, 4.2, 4.7) * (1.0 - ramp(t, 11.4, 11.9)),
            "path": ramp(t, 4.0, 4.3) * (1.0 - ramp(t, *self.REWIND)),
            "start_marker": ramp(t, 4.0, 4.4) * (1.0 - ramp(t, 18.6, 18.9)),
            "angle_arc": ramp(t, 4.4, 4.9) * (1.0 - ramp(t, 18.6, 18.9)),
            "kepler": 0.0,
            "result": ramp(t, 12.15, 12.6) * (1.0 - ramp(t, fly0, fly0 + 0.4)),
            "extra": ramp(t, 12.9, 13.3) * (1.0 - ramp(t, fly0, fly0 + 0.4)),
            # the result flies from the info column into its row as the table returns
            "fly": ramp(t, fly0, self.table_in + 0.45),
            # the table leaves before the camera flies in and returns once no planet
            # is inside its column (see table_in)
            "table": (ramp(t, 0.2, 0.7) * (1.0 - ramp(t, self.CAM_IN[0] - 0.25, self.CAM_IN[0] + 0.25))
                      if t < self.RUN[1] else ramp(t, self.table_in, self.table_in + 0.35)),
            "row_done": ramp(t, self.table_in + 0.3, self.table_in + 0.5),
            "next": ramp(t, 18.0, 18.4),
            "rewind": ramp(t, 18.55, 18.75) * (1.0 - ramp(t, 19.75, 19.95)),
            "scale_note": ramp(t, 0.3, 0.8),
            "focus": fw,
        }
        if self.kepler_t is not None:
            out["kepler"] = ramp(t, self.kepler_t, self.kepler_t + 0.4) * (1.0 - ramp(t, 11.6, 12.0))
            out["sun_dist"] = ramp(t, self.kepler_t, self.kepler_t + 0.4) * (1.0 - ramp(t, fly0, fly0 + 0.4))
        else:
            out["sun_dist"] = 0.0
        return out

    def audio_events(self):
        return [("whoosh_in", self.CAM_IN[0], self.CAM_IN[1] - self.CAM_IN[0]),
                ("accent", self.RUN[1], 1.6),
                ("whoosh_out", self.CAM_OUT[0], self.CAM_OUT[1] - self.CAM_OUT[0]),
                ("rewind", self.REWIND[0], self.REWIND[1] - self.REWIND[0])]


def planets_in_order():
    return PLANET_ORDER
