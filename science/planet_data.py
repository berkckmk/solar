"""NASA/JPL planetary orbital elements and physical data.

Epoch: J2000.0 (2000-Jan-01 12:00:00 TDB, JD 2451545.0)

Sources:
  - NASA Planetary Fact Sheet: https://nssdc.gsfc.nasa.gov/planetary/factsheet/
  - JPL Solar System Dynamics: https://ssd.jpl.nasa.gov/planets/approx_pos.html
  - Standish (1992) "Keplerian Elements for Approximate Positions of the
    Major Planets", Solar System Dynamics Group, JPL.

All orbital elements are J2000 mean ecliptic and equinox.
Units: AU, degrees, Earth days, km, km/s, kg.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict

# ── physical constants ──────────────────────────────────────────────────
AU_KM = 149_597_870.7          # 1 AU in km  (IAU 2012)
EARTH_DAY_S = 86_400.0         # seconds per Earth day
G_M_SUN = 1.327_124_400_18e20  # GM_sun  m^3 s^-2  (DE440)
SOLAR_RADIUS_KM = 695_700.0    # IAU nominal

EPOCH_NAME = "J2000.0"
EPOCH_JD   = 2_451_545.0       # Julian Date


@dataclass(frozen=True)
class PlanetData:
    """Orbital elements at J2000.0 + physical properties."""

    name: str

    # ── orbital elements (J2000 ecliptic) ──
    semi_major_axis_au: float       # a
    eccentricity: float             # e
    inclination_deg: float          # i
    long_ascending_node_deg: float  # Ω
    arg_periapsis_deg: float        # ω
    mean_anomaly_deg: float         # M₀  at epoch
    orbital_period_days: float      # T  (sidereal, Earth days)

    # ── physical ──
    mass_kg: float
    mean_radius_km: float
    rotation_period_days: float     # sidereal; negative = retrograde
    mean_orbital_speed_kms: float   # km/s  (mean)
    axial_tilt_deg: float           # obliquity to orbit (NASA Fact Sheet); >90 = retrograde spin

    # ── derived (computed at load time) ──
    semi_major_axis_km: float = field(init=False)
    mean_motion_rad_per_day: float = field(init=False)

    def __post_init__(self):
        object.__setattr__(
            self, "semi_major_axis_km",
            self.semi_major_axis_au * AU_KM,
        )
        object.__setattr__(
            self, "mean_motion_rad_per_day",
            2.0 * math.pi / self.orbital_period_days,
        )


# ── JPL J2000 mean elements + NASA Fact Sheet physical data ─────────────
# Orbital elements: Standish (1992) / JPL SSD approx_pos table (3000 BC – 3000 AD)
# Physical data: NASA GSFC Planetary Fact Sheet (2024 revision)

PLANETS: Dict[str, PlanetData] = {}

def _register(name: str, **kw):
    p = PlanetData(name=name, **kw)
    PLANETS[name.lower()] = p

_register(
    "Mercury",
    semi_major_axis_au   = 0.387_098_93,
    eccentricity         = 0.205_630_69,
    inclination_deg      = 7.004_86,
    long_ascending_node_deg = 48.330_67,
    arg_periapsis_deg    = 29.124_78,
    mean_anomaly_deg     = 174.796_0,
    orbital_period_days  = 87.969_1,
    mass_kg              = 3.301_1e23,
    mean_radius_km       = 2_439.7,
    rotation_period_days = 58.646,
    mean_orbital_speed_kms = 47.36,
    axial_tilt_deg       = 0.034,
)

_register(
    "Venus",
    semi_major_axis_au   = 0.723_331_99,
    eccentricity         = 0.006_773_23,
    inclination_deg      = 3.394_71,
    long_ascending_node_deg = 76.680_69,
    arg_periapsis_deg    = 54.852_29,
    mean_anomaly_deg     = 50.416_0,
    orbital_period_days  = 224.700_8,
    mass_kg              = 4.867_5e24,
    mean_radius_km       = 6_051.8,
    rotation_period_days = -243.025,
    mean_orbital_speed_kms = 35.02,
    axial_tilt_deg       = 177.36,
)

_register(
    "Earth",
    semi_major_axis_au   = 1.000_000_11,
    eccentricity         = 0.016_710_22,
    inclination_deg      = 0.000_05,
    long_ascending_node_deg = -11.260_64,
    arg_periapsis_deg    = 102.947_19,
    mean_anomaly_deg     = 357.517_6,
    orbital_period_days  = 365.256_36,
    mass_kg              = 5.972_4e24,
    mean_radius_km       = 6_371.0,
    rotation_period_days = 0.997_27,
    mean_orbital_speed_kms = 29.78,
    axial_tilt_deg       = 23.44,
)

_register(
    "Mars",
    semi_major_axis_au   = 1.523_662_31,
    eccentricity         = 0.093_412_33,
    inclination_deg      = 1.850_61,
    long_ascending_node_deg = 49.578_54,
    arg_periapsis_deg    = 286.502_19,
    mean_anomaly_deg     = 19.387_0,
    orbital_period_days  = 686.979_6,
    mass_kg              = 6.417_1e23,
    mean_radius_km       = 3_389.5,
    rotation_period_days = 1.025_96,
    mean_orbital_speed_kms = 24.07,
    axial_tilt_deg       = 25.19,
)

_register(
    "Jupiter",
    semi_major_axis_au   = 5.202_603_91,
    eccentricity         = 0.048_497_64,
    inclination_deg      = 1.303_30,
    long_ascending_node_deg = 100.464_44,
    arg_periapsis_deg    = 273.867_68,
    mean_anomaly_deg     = 20.020_0,
    orbital_period_days  = 4_332.589,
    mass_kg              = 1.898_2e27,
    mean_radius_km       = 69_911.0,
    rotation_period_days = 0.413_54,
    mean_orbital_speed_kms = 13.07,
    axial_tilt_deg       = 3.13,
)

_register(
    "Saturn",
    semi_major_axis_au   = 9.554_909_56,
    eccentricity         = 0.055_508_62,
    inclination_deg      = 2.488_78,
    long_ascending_node_deg = 113.665_24,
    arg_periapsis_deg    = 339.392_64,
    mean_anomaly_deg     = 317.020_0,
    orbital_period_days  = 10_759.22,
    mass_kg              = 5.683_4e26,
    mean_radius_km       = 58_232.0,
    rotation_period_days = 0.444_01,
    mean_orbital_speed_kms = 9.68,
    axial_tilt_deg       = 26.73,
)

_register(
    "Uranus",
    semi_major_axis_au   = 19.218_446_12,
    eccentricity         = 0.046_295_11,
    inclination_deg      = 0.773_13,
    long_ascending_node_deg = 74.005_95,
    arg_periapsis_deg    = 96.998_57,
    mean_anomaly_deg     = 142.238_6,
    orbital_period_days  = 30_685.4,
    mass_kg              = 8.681_0e25,
    mean_radius_km       = 25_362.0,
    rotation_period_days = -0.718_33,
    mean_orbital_speed_kms = 6.80,
    axial_tilt_deg       = 97.77,
)

_register(
    "Neptune",
    semi_major_axis_au   = 30.110_386_86,
    eccentricity         = 0.008_990_48,
    inclination_deg      = 1.769_17,
    long_ascending_node_deg = 131.784_06,
    arg_periapsis_deg    = 276.336_42,
    mean_anomaly_deg     = 256.228_0,
    orbital_period_days  = 60_189.0,
    mass_kg              = 1.024_1e26,
    mean_radius_km       = 24_622.0,
    rotation_period_days = 0.671_25,
    mean_orbital_speed_kms = 5.43,
    axial_tilt_deg       = 28.32,
)

# Convenience ordered list matching project.json planet_order
PLANET_ORDER = [
    "mercury", "venus", "earth", "mars",
    "jupiter", "saturn", "uranus", "neptune",
]

# ── visual trail colours (R, G, B  0-1 linear) ──────────────────────────
TRAIL_COLORS = {
    "mercury":  (0.78, 0.80, 0.82),   # silver / cool white
    "venus":    (0.90, 0.82, 0.55),   # warm pale gold
    "earth":    (0.25, 0.60, 0.95),   # azure / cyan-blue
    "mars":     (0.85, 0.40, 0.15),   # rust orange
    "jupiter":  (0.88, 0.78, 0.50),   # cream / amber
    "saturn":   (0.85, 0.75, 0.45),   # pale gold
    "uranus":   (0.40, 0.82, 0.85),   # aqua / pale cyan
    "neptune":  (0.20, 0.35, 0.90),   # cobalt / deep electric blue
}
