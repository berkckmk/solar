"""Keplerian orbit solver: eccentric anomaly, true anomaly, 3-D position.

Solves  M = E − e·sin(E)  via Newton-Raphson, then computes heliocentric
ecliptic position from the full set of J2000 orbital elements.

A separate physics→Blender coordinate transform is in `coordinates.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from .planet_data import PlanetData

DEG2RAD = math.pi / 180.0


@dataclass(frozen=True)
class OrbitalState:
    """Instantaneous orbital state in heliocentric ecliptic frame (km)."""
    x: float
    y: float
    z: float
    mean_anomaly_rad: float
    eccentric_anomaly_rad: float
    true_anomaly_rad: float
    radius_km: float

    @property
    def radius_au(self) -> float:
        from .planet_data import AU_KM
        return self.radius_km / AU_KM


def solve_kepler(M: float, e: float, tol: float = 1e-12, max_iter: int = 50) -> float:
    """Solve Kepler's equation  M = E − e·sin(E)  for E.

    Uses Newton-Raphson with a robust initial guess.
    Args:
        M: mean anomaly in radians
        e: eccentricity (0 ≤ e < 1)
    Returns:
        E: eccentric anomaly in radians
    """
    # Normalise M to [0, 2π)
    M = M % (2.0 * math.pi)

    # Initial guess (Markley-style starter for moderate e)
    E = M + e * math.sin(M) * (1.0 + e * math.cos(M))

    for _ in range(max_iter):
        sin_E = math.sin(E)
        cos_E = math.cos(E)
        f  = E - e * sin_E - M
        fp = 1.0 - e * cos_E        # dE
        dE = -f / fp
        E += dE
        if abs(dE) < tol:
            return E

    raise RuntimeError(f"Kepler solver did not converge: M={M:.6f}, e={e:.6f}")


def eccentric_to_true(E: float, e: float) -> float:
    """Convert eccentric anomaly E → true anomaly ν."""
    half_E = E / 2.0
    return 2.0 * math.atan2(
        math.sqrt(1.0 + e) * math.sin(half_E),
        math.sqrt(1.0 - e) * math.cos(half_E),
    )


def heliocentric_position(planet: PlanetData, days_since_epoch: float) -> OrbitalState:
    """Compute heliocentric ecliptic (x, y, z) in km at epoch + Δt days.

    Returns an OrbitalState with full angle information for downstream use.
    """
    # Mean anomaly at time t
    M0 = planet.mean_anomaly_deg * DEG2RAD
    n  = planet.mean_motion_rad_per_day
    M  = M0 + n * days_since_epoch

    e = planet.eccentricity

    # Solve Kepler
    E = solve_kepler(M, e)

    # True anomaly
    nu = eccentric_to_true(E, e)

    # Radius in AU then km
    a_km = planet.semi_major_axis_km
    r_km = a_km * (1.0 - e * math.cos(E))

    # Position in orbital plane (perifocal frame)
    x_pf = r_km * math.cos(nu)
    y_pf = r_km * math.sin(nu)

    # Rotate to ecliptic frame using Ω, ω, i
    omega = planet.arg_periapsis_deg * DEG2RAD       # ω
    Omega = planet.long_ascending_node_deg * DEG2RAD # Ω
    inc   = planet.inclination_deg * DEG2RAD         # i

    cos_w = math.cos(omega)
    sin_w = math.sin(omega)
    cos_O = math.cos(Omega)
    sin_O = math.sin(Omega)
    cos_i = math.cos(inc)
    sin_i = math.sin(inc)

    # Rotation matrix  R = R_z(-Ω) · R_x(-i) · R_z(-ω)
    x_ecl = (
        (cos_O * cos_w - sin_O * sin_w * cos_i) * x_pf
        + (-cos_O * sin_w - sin_O * cos_w * cos_i) * y_pf
    )
    y_ecl = (
        (sin_O * cos_w + cos_O * sin_w * cos_i) * x_pf
        + (-sin_O * sin_w + cos_O * cos_w * cos_i) * y_pf
    )
    z_ecl = (
        (sin_w * sin_i) * x_pf
        + (cos_w * sin_i) * y_pf
    )

    return OrbitalState(
        x=x_ecl,
        y=y_ecl,
        z=z_ecl,
        mean_anomaly_rad=M % (2.0 * math.pi),
        eccentric_anomaly_rad=E,
        true_anomaly_rad=nu % (2.0 * math.pi),
        radius_km=r_km,
    )


def orbital_arc_length(planet: PlanetData, t_start: float, t_end: float,
                        n_samples: int = 2000) -> float:
    """Compute arc length along the real Keplerian trajectory (km).

    Uses dense sampling of 3-D positions, summing chord lengths.
    For accuracy, n_samples should be ≥ 1000 per orbit.
    """
    dt = (t_end - t_start) / n_samples
    total = 0.0
    prev = heliocentric_position(planet, t_start)
    for i in range(1, n_samples + 1):
        t = t_start + i * dt
        cur = heliocentric_position(planet, t)
        dx = cur.x - prev.x
        dy = cur.y - prev.y
        dz = cur.z - prev.z
        total += math.sqrt(dx * dx + dy * dy + dz * dz)
        prev = cur
    return total
