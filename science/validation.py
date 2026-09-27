"""Numerical validation of orbital solver and metrics.

Checks from SOURCE_PROMPT §27:
  - No NaN in any result
  - All orbit positions are finite
  - Earth ≈ 1 orbit / year
  - Mercury > 4 orbits / year
  - Venus > 1 orbit / year
  - Outer planets: partial orbit only in 365 days
  - All arc lengths are positive
  - Visual coordinates are valid (finite, non-zero for planets)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Allow running as script directly
_this_dir = Path(__file__).resolve().parent
_project_dir = _this_dir.parent
if str(_project_dir) not in sys.path:
    sys.path.insert(0, str(_project_dir))

try:
    from science.planet_data import PLANETS, PLANET_ORDER
    from science.kepler import heliocentric_position, orbital_arc_length
    from science.metrics import compute_all_metrics, INTERVALS
    from science.coordinates import ecliptic_km_to_blender
    from science.rotation import solar_day_days, shared_clock_table
    from science.attitude import obliquity_deg, prime_meridian, OBLIQUITY_J2000_DEG
except ImportError:
    from planet_data import PLANETS, PLANET_ORDER  # type: ignore
    from kepler import heliocentric_position, orbital_arc_length  # type: ignore
    from metrics import compute_all_metrics, INTERVALS  # type: ignore
    from coordinates import ecliptic_km_to_blender  # type: ignore
    from rotation import solar_day_days, shared_clock_table  # type: ignore
    from attitude import obliquity_deg, prime_meridian, OBLIQUITY_J2000_DEG  # type: ignore


def validate_all() -> list[str]:
    """Return list of validation errors (empty = all passed)."""
    errors: list[str] = []

    # ── 1. Basic Kepler solver sanity ────────────────────────────────
    for name in PLANET_ORDER:
        p = PLANETS[name]
        for t in [0, 1, 30, 365, 1000]:
            state = heliocentric_position(p, float(t))
            for attr in ("x", "y", "z", "radius_km"):
                val = getattr(state, attr)
                if math.isnan(val) or math.isinf(val):
                    errors.append(f"{name} t={t}: {attr} = {val}")

    # ── 2. Arc lengths positive ──────────────────────────────────────
    for name in PLANET_ORDER:
        p = PLANETS[name]
        for days in INTERVALS:
            arc = orbital_arc_length(p, 0, float(days), n_samples=1000)
            if arc <= 0 or math.isnan(arc):
                errors.append(f"{name} arc_length({days}d) = {arc}")

    # ── 3. Metrics plausibility ──────────────────────────────────────
    all_m = compute_all_metrics()

    for days, planet_list in all_m.items():
        for m in planet_list:
            # No NaN anywhere
            for field_name, val in m.__dict__.items():
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    errors.append(f"{m.planet} {days}d: {field_name} = {val}")

            # Positive distances
            if m.distance_travelled_km <= 0:
                errors.append(f"{m.planet} {days}d: distance_km = {m.distance_travelled_km}")

    # ── 4. Orbit count checks (365 days) ─────────────────────────────
    year_metrics = {m.planet: m for m in all_m[365]}

    # Earth: ~1 orbit
    earth_orbits = year_metrics["earth"].orbit_count
    if not (0.95 <= earth_orbits <= 1.05):
        errors.append(f"Earth 365d orbit_count = {earth_orbits}, expected ~1.0")

    # Mercury: > 4 orbits
    mercury_orbits = year_metrics["mercury"].orbit_count
    if mercury_orbits < 4.0:
        errors.append(f"Mercury 365d orbit_count = {mercury_orbits}, expected > 4")

    # Venus: > 1 orbit
    venus_orbits = year_metrics["venus"].orbit_count
    if venus_orbits < 1.0:
        errors.append(f"Venus 365d orbit_count = {venus_orbits}, expected > 1")

    # Outer planets: < 1 orbit
    for name in ("mars", "jupiter", "saturn", "uranus", "neptune"):
        oc = year_metrics[name].orbit_count
        if oc >= 1.0:
            errors.append(f"{name} 365d orbit_count = {oc}, expected < 1")

    # ── 5. Coordinate transform sanity ───────────────────────────────
    for name in PLANET_ORDER:
        p = PLANETS[name]
        state = heliocentric_position(p, 0.0)
        bx, by, bz = ecliptic_km_to_blender(state.x, state.y, state.z)
        for coord_name, val in [("bx", bx), ("by", by), ("bz", bz)]:
            if math.isnan(val) or math.isinf(val):
                errors.append(f"{name} blender coord {coord_name} = {val}")

    # ── 6. Speed sanity ──────────────────────────────────────────────
    for days in INTERVALS:
        for m in all_m[days]:
            p = PLANETS[m.planet]
            # avg speed should be within 50% of NASA mean orbital speed
            ratio = m.avg_orbital_speed_kms / p.mean_orbital_speed_kms
            if not (0.5 <= ratio <= 1.5):
                errors.append(
                    f"{m.planet} {days}d: avg_speed={m.avg_orbital_speed_kms:.2f} "
                    f"vs NASA mean={p.mean_orbital_speed_kms:.2f} "
                    f"(ratio={ratio:.2f})"
                )

    # ── 7. Axial rotation & solar day (NASA Fact Sheet "length of day") ──
    expected_solar_day_h = {
        "mercury": 4222.6, "venus": 2802.0, "earth": 24.0, "mars": 24.7,
        "jupiter": 9.9, "saturn": 10.7, "uranus": 17.2, "neptune": 16.1,
    }
    for name, exp_h in expected_solar_day_h.items():
        got_h = abs(solar_day_days(PLANETS[name])) * 24.0
        if abs(got_h - exp_h) / exp_h > 0.01:
            errors.append(f"{name} solar day = {got_h:.1f} h, expected ~{exp_h} h")

    for r in shared_clock_table(1.0):
        if math.isnan(r.spin_deg) or math.isnan(r.local_days):
            errors.append(f"{r.planet} rotation state NaN")
        if not (0.0 <= PLANETS[r.planet].axial_tilt_deg <= 180.0):
            errors.append(f"{r.planet} axial tilt out of range")

    # ── 8. Spin-axis vectors reproduce the fact-sheet obliquity ───────
    for name in PLANET_ORDER:
        got = obliquity_deg(name)
        exp = PLANETS[name].axial_tilt_deg
        if abs(got - exp) > 0.1:
            errors.append(f"{name} obliquity from IAU pole = {got:.2f}°, expected {exp}°")

    # ── 9. Earth at J2000.0: heliocentric longitude and local noon at Greenwich ──
    st = heliocentric_position(PLANETS["earth"], 0.0)
    lon = math.degrees(math.atan2(st.y, st.x)) % 360.0
    if abs(lon - 100.46) > 0.3:          # JPL: L = 100.464 deg, true longitude ~100.4
        errors.append(f"Earth longitude at J2000 = {lon:.2f}°, expected ~100.4°")
    e = math.radians(OBLIQUITY_J2000_DEG)

    def ra(v):
        return math.degrees(math.atan2(v[1] * math.cos(e) - v[2] * math.sin(e), v[0]))

    ha = (ra(prime_meridian("earth", 0.0)) - ra((-st.x, -st.y, -st.z)) + 180.0) % 360.0 - 180.0
    if abs(ha) > 2.0:                    # 12:00 TT on 1 Jan 2000: Sun on the Greenwich meridian (EoT ~ -1°)
        errors.append(f"Sun's hour angle at Greenwich, J2000 = {ha:+.2f}°, expected within ±2°")

    return errors


if __name__ == "__main__":
    print("Running orbital validation...")
    errs = validate_all()
    if errs:
        print(f"\n❌ {len(errs)} ERRORS:")
        for e in errs:
            print(f"  • {e}")
        sys.exit(1)
    else:
        print("✅ All validation checks passed.")
        sys.exit(0)
