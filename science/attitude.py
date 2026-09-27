"""Spin-axis and orbit-plane directions in the J2000 ecliptic frame.

Answers "which way does each planet's axis point?" so a renderer can show the
real tilt (obliquity) against the real orbit plane, not just a tilt number.

Sources:
  - IAU WGCCRE 2009 report (Archinal et al. 2011): north-pole RA/Dec at J2000
    (Neptune's precession term evaluated at the epoch).
  - Orbit normals from the JPL mean elements in `planet_data.py`.

Conventions:
  - IAU "north pole" is the pole on the north side of the invariable plane.
    Venus and Uranus spin retrograde about it, so their angular-momentum
    ("spin") axis is the IAU south pole. `spin_axis()` returns the angular-
    momentum direction; the planet turns counter-clockwise about it.
  - The angle between `spin_axis()` and `orbit_normal()` is the obliquity and
    matches `PlanetData.axial_tilt_deg` (checked in `validation.py`).
"""

from __future__ import annotations

import math

from .planet_data import PLANETS

Vec3 = tuple[float, float, float]

OBLIQUITY_J2000_DEG = 23.4392911   # Earth's obliquity: equatorial -> ecliptic

_N_NEPTUNE = math.radians(357.85)  # Neptune pole precession angle at J2000

# IAU north pole (RA, Dec) in degrees, J2000 equatorial frame.
IAU_NORTH_POLE_RADEC: dict[str, tuple[float, float]] = {
    "mercury": (281.0103, 61.4155),
    "venus":   (272.76, 67.16),
    "earth":   (0.0, 90.0),
    "mars":    (317.68143, 52.88650),
    "jupiter": (268.056595, 64.495303),
    "saturn":  (40.589, 83.537),
    "uranus":  (257.311, -15.175),
    "neptune": (299.36 + 0.70 * math.sin(_N_NEPTUNE), 43.46 - 0.51 * math.cos(_N_NEPTUNE)),
}


def _equatorial_to_ecliptic(v: Vec3) -> Vec3:
    e = math.radians(OBLIQUITY_J2000_DEG)
    x, y, z = v
    return (x, y * math.cos(e) + z * math.sin(e), -y * math.sin(e) + z * math.cos(e))


def iau_north_pole(name: str) -> Vec3:
    """Unit vector of the IAU north pole in the J2000 ecliptic frame."""
    ra, dec = (math.radians(a) for a in IAU_NORTH_POLE_RADEC[name])
    return _equatorial_to_ecliptic(
        (math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)))


def spin_axis(name: str) -> Vec3:
    """Unit angular-momentum vector of the planet's rotation (ecliptic frame)."""
    k = iau_north_pole(name)
    if PLANETS[name].rotation_period_days < 0:
        k = (-k[0], -k[1], -k[2])
    return k


def orbit_normal(name: str) -> Vec3:
    """Unit orbital angular-momentum vector (ecliptic frame)."""
    p = PLANETS[name]
    i = math.radians(p.inclination_deg)
    node = math.radians(p.long_ascending_node_deg)
    return (math.sin(i) * math.sin(node), -math.sin(i) * math.cos(node), math.cos(i))


# IAU WGCCRE 2009 prime-meridian angle W = W0 + rate * d (degrees, d = days from
# J2000), measured eastward along the planet's equator from its node Q on the
# ICRF equator. Small periodic terms (Mercury's libration) are left out.
IAU_PRIME_MERIDIAN: dict[str, tuple[float, float]] = {
    "mercury": (329.5469, 6.1385025),
    "venus":   (160.20, -1.4813688),
    "earth":   (190.147, 360.9856235),
    "mars":    (176.630, 350.89198226),
    "jupiter": (284.95, 870.5360000),          # System III
    "saturn":  (38.90, 810.7939024),
    "uranus":  (203.81, -501.1600928),
    "neptune": (253.18 - 0.48 * math.sin(_N_NEPTUNE), 536.3128492),
}


def prime_meridian(name: str, days: float) -> Vec3:
    """Unit vector (ecliptic frame) from the planet's centre through its prime
    meridian on the equator, `days` after J2000 (IAU definition)."""
    ra, dec = (math.radians(a) for a in IAU_NORTH_POLE_RADEC[name])
    p = iau_north_pole(name)
    q = _equatorial_to_ecliptic((-math.sin(ra), math.cos(ra), 0.0))      # node Q, RA = alpha0 + 90 deg
    pq = (p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0])
    w0, rate = IAU_PRIME_MERIDIAN[name]
    w = math.radians(w0 + rate * days)
    return tuple(math.cos(w) * q[i] + math.sin(w) * pq[i] for i in range(3))


def obliquity_deg(name: str) -> float:
    """Angle between spin axis and orbit normal, from the vectors above."""
    k, n = spin_axis(name), orbit_normal(name)
    d = max(-1.0, min(1.0, k[0] * n[0] + k[1] * n[1] + k[2] * n[2]))
    return math.degrees(math.acos(d))


if __name__ == "__main__":
    for name in PLANETS:
        print(f"{name:8} obliquity {obliquity_deg(name):7.2f}°  "
              f"(fact sheet {PLANETS[name].axial_tilt_deg:.2f}°)")
