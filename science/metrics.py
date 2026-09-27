"""Compute all display metrics for 1 / 30 / 365 Earth-day intervals.

Precomputes and caches results so Blender never re-solves the physics.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

from .planet_data import PLANETS, PLANET_ORDER, AU_KM
from .kepler import heliocentric_position, orbital_arc_length

INTERVALS = [1, 30, 365]


@dataclass
class PlanetMetrics:
    """All display-ready metrics for one planet at one time interval."""

    planet: str
    earth_days: int

    # positions (heliocentric ecliptic km)
    start_x_km: float
    start_y_km: float
    start_z_km: float
    end_x_km: float
    end_y_km: float
    end_z_km: float

    # arc length along real trajectory
    distance_travelled_km: float
    distance_travelled_million_km: float

    # speeds
    avg_orbital_speed_kms: float
    end_instantaneous_speed_kms: float

    # orbit progress
    orbit_fraction: float      # fraction of one full orbit
    orbit_count: float         # total orbits (may be > 1)
    angle_progress_deg: float  # true anomaly change

    # Sun distance at end
    sun_distance_km: float
    sun_distance_au: float


def compute_planet_metrics(planet_name: str, earth_days: int,
                           n_arc_samples: int = 4000) -> PlanetMetrics:
    """Compute all metrics for a single planet at a given time interval."""
    p = PLANETS[planet_name]

    t0 = 0.0   # epoch
    t1 = float(earth_days)

    # Positions
    state0 = heliocentric_position(p, t0)
    state1 = heliocentric_position(p, t1)

    # Arc length (real Keplerian trajectory, dense sampling)
    arc_km = orbital_arc_length(p, t0, t1, n_samples=n_arc_samples)

    # Average speed
    elapsed_s = earth_days * 86_400.0
    avg_speed = arc_km / elapsed_s if elapsed_s > 0 else 0.0

    # Instantaneous speed at end (numerical derivative, ±0.01 day)
    dt_tiny = 0.01
    s_minus = heliocentric_position(p, t1 - dt_tiny)
    s_plus  = heliocentric_position(p, t1 + dt_tiny)
    dx = s_plus.x - s_minus.x
    dy = s_plus.y - s_minus.y
    dz = s_plus.z - s_minus.z
    dist_dt = math.sqrt(dx*dx + dy*dy + dz*dz)
    inst_speed = dist_dt / (2.0 * dt_tiny * 86_400.0)  # km/s

    # Orbit fraction and count
    orbit_count = earth_days / p.orbital_period_days
    orbit_fraction = orbit_count % 1.0

    # True anomaly progress
    angle_deg = math.degrees(state1.true_anomaly_rad - state0.true_anomaly_rad)
    # Adjust for multiple orbits
    full_orbits = int(orbit_count)
    if angle_deg < 0:
        angle_deg += 360.0
    angle_deg += full_orbits * 360.0

    return PlanetMetrics(
        planet=planet_name,
        earth_days=earth_days,
        start_x_km=state0.x,
        start_y_km=state0.y,
        start_z_km=state0.z,
        end_x_km=state1.x,
        end_y_km=state1.y,
        end_z_km=state1.z,
        distance_travelled_km=arc_km,
        distance_travelled_million_km=round(arc_km / 1e6, 3),
        avg_orbital_speed_kms=round(avg_speed, 3),
        end_instantaneous_speed_kms=round(inst_speed, 3),
        orbit_fraction=round(orbit_fraction, 6),
        orbit_count=round(orbit_count, 6),
        angle_progress_deg=round(angle_deg, 3),
        sun_distance_km=state1.radius_km,
        sun_distance_au=round(state1.radius_km / AU_KM, 6),
    )


def compute_all_metrics() -> Dict[int, List[PlanetMetrics]]:
    """Compute metrics for all planets at all time intervals."""
    results = {}
    for days in INTERVALS:
        results[days] = []
        for name in PLANET_ORDER:
            results[days].append(compute_planet_metrics(name, days))
    return results


def save_metrics_json(output_dir: Path) -> Path:
    """Compute + save metrics to data/metrics_precomputed.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    all_metrics = compute_all_metrics()

    data = {}
    for days, planet_list in all_metrics.items():
        data[str(days)] = [asdict(m) for m in planet_list]

    out_path = output_dir / "metrics_precomputed.json"
    out_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def save_metrics_csv(output_dir: Path) -> Path:
    """Compute + save metrics to data/metrics_1_30_365.csv."""
    output_dir.mkdir(parents=True, exist_ok=True)
    all_metrics = compute_all_metrics()

    lines = [
        "earth_days,planet,distance_km,distance_million_km,"
        "avg_speed_kms,inst_speed_kms,orbit_fraction,orbit_count,"
        "angle_deg,sun_dist_au"
    ]
    for days in INTERVALS:
        for m in all_metrics[days]:
            lines.append(
                f"{m.earth_days},{m.planet},"
                f"{m.distance_travelled_km:.1f},{m.distance_travelled_million_km:.3f},"
                f"{m.avg_orbital_speed_kms:.3f},{m.end_instantaneous_speed_kms:.3f},"
                f"{m.orbit_fraction:.6f},{m.orbit_count:.6f},"
                f"{m.angle_progress_deg:.3f},{m.sun_distance_au:.6f}"
            )

    out_path = output_dir / "metrics_1_30_365.csv"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
