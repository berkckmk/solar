"""Physics (ecliptic km) ↔ Blender visual coordinate transform.

Blender convention used here:
  Blender X  =  ecliptic X
  Blender Y  =  ecliptic Y
  Blender Z  =  ecliptic Z   (up = north ecliptic pole)

Scale: 1 Blender unit (BU) = 1.0 AU.
The Sun sits at the Blender origin (0, 0, 0).
"""

from __future__ import annotations

from .planet_data import AU_KM

# 1 Blender unit (BU) = 1.0 AU.
# Neptune at ~30.1 AU sits at ~30.1 BU from origin.
VISUAL_SCALE_AU = 1.0


def ecliptic_km_to_blender(x_km: float, y_km: float, z_km: float) -> tuple[float, float, float]:
    """Convert heliocentric ecliptic km → Blender units."""
    s = 1.0 / (AU_KM * VISUAL_SCALE_AU)
    return (x_km * s, y_km * s, z_km * s)


def planet_visual_radius(mean_radius_km: float) -> float:
    """Exaggerated visual radius in Blender units.
    
    Uses a soft sub-linear exponent (0.55) so rocky planets remain clearly visible
    while gas giants stay impressively larger without overwhelming their orbits.
    Earth (6,371 km) -> 0.024 BU
    Jupiter (69,911 km) -> ~0.090 BU
    Mercury (2,440 km) -> ~0.014 BU
    """
    return 0.024 * (mean_radius_km / 6371.0) ** 0.55


def sun_visual_radius() -> float:
    """Exaggerated visual Sun radius in Blender units.
    
    Chosen to be 0.12 BU.
    Mercury's perihelion is ~0.307 BU, providing ~0.187 BU of clear space
    between the solar limb and Mercury's closest approach.
    """
    return 0.12
