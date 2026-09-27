"""Axial rotation, solar-day and "shared clock" metrics.

Answers: while a given amount of Earth time passes, how far does each planet
spin on its own axis, how far does it advance along its orbit, and how many
of its *own* local (solar) days elapse?

Conventions:
  - `rotation_period_days` is the sidereal period (vs. the stars); negative
    means retrograde (Venus, Uranus), as in `planet_data.py`.
  - The solar day (Sun back to the same meridian) combines spin and orbital
    motion:  1/P_solar = 1/P_sidereal − 1/P_orbit  (signed).
  - Orbital advance uses the true Keplerian position, not the mean motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .planet_data import PLANETS, PLANET_ORDER, PlanetData
from .kepler import heliocentric_position


def solar_day_days(p: PlanetData) -> float:
    """Length of one local solar day in Earth days (signed; <0 = Sun rises in the west)."""
    return 1.0 / (1.0 / p.rotation_period_days - 1.0 / p.orbital_period_days)


def orbital_advance_deg(p: PlanetData, t0_days: float, t1_days: float) -> float:
    """Heliocentric longitude swept between two epochs (degrees, true Kepler motion)."""
    s0 = heliocentric_position(p, t0_days)
    s1 = heliocentric_position(p, t1_days)
    a0 = math.atan2(s0.y, s0.x)
    a1 = math.atan2(s1.y, s1.x)
    d = math.degrees(a1 - a0)
    # Unwrap using the mean motion as the expected sweep
    expected = 360.0 * (t1_days - t0_days) / p.orbital_period_days
    return d + 360.0 * round((expected - d) / 360.0)


@dataclass(frozen=True)
class RotationState:
    planet: str
    earth_days: float
    spin_deg: float           # sidereal spin (signed, vs. the stars)
    orbit_deg: float          # heliocentric longitude advance
    sun_relative_deg: float   # spin as seen from the Sun (what moves the terminator)
    local_days: float         # local solar days elapsed (always >= 0)
    solar_day_days: float     # |one local day| in Earth days

    @property
    def spin_turns(self) -> float:
        return abs(self.spin_deg) / 360.0


def rotation_state(name: str, earth_days: float, epoch_days: float = 0.0) -> RotationState:
    """Rotation metrics for one planet after `earth_days` of Earth time."""
    p = PLANETS[name]
    spin = 360.0 * earth_days / p.rotation_period_days
    orbit = orbital_advance_deg(p, epoch_days, epoch_days + earth_days)
    sol = solar_day_days(p)
    return RotationState(
        planet=name,
        earth_days=earth_days,
        spin_deg=spin,
        orbit_deg=orbit,
        sun_relative_deg=spin - orbit,
        local_days=abs(spin - orbit) / 360.0,
        solar_day_days=abs(sol),
    )


def shared_clock_table(earth_days: float = 1.0) -> list[RotationState]:
    """Rotation metrics for all 8 planets over the same span of Earth time."""
    return [rotation_state(n, earth_days) for n in PLANET_ORDER]


if __name__ == "__main__":
    print(f"{'planet':8} {'spin°':>9} {'turns':>6} {'orbit°':>8} {'local days':>10} {'solar day (d)':>13}")
    for r in shared_clock_table(1.0):
        print(f"{r.planet:8} {r.spin_deg:9.2f} {r.spin_turns:6.2f} {r.orbit_deg:8.4f} "
              f"{r.local_days:10.4f} {r.solar_day_days:13.3f}")
