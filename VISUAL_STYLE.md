# Art Direction & Visual Style Specification

**Project:** Solar System Through Earth Time  
**Primary Aesthetic Language:** LOOK-A Scientific Noir + LOOK-C Dark Cinematic Space  
**Aspect Ratio:** 16:9 widescreen  
**Target Quality:** 2560×1440 (QHD) @ 30 FPS  

---

## 1. Visual Directives

### 1.1 Deep Black Space & Starfield (BG-02)
- Pure black background void ($RGB = 0, 0, 0$).
- Two-tier procedural Voronoi starfield:
  - Sharp, pinprick primary stars (scale 350, high threshold).
  - Subtle micro-twinkling distant field (scale 700).
- No saturated, distracting nebulae; space feels vast, calm, and mathematically precise.

### 1.2 Multi-Layer Procedural Sun
- **Core:** Brilliant warm white-gold ($RGB = 1.0, 0.94, 0.75$), emission strength 3.2.
- **Surface:** Convective granulation cells via Voronoi distance mixed with Perlin noise.
- **Limb Darkening:** Facing-ratio Fresnel darkening to deep amber-orange ($RGB = 1.0, 0.60, 0.15$) at sphere silhouettes.
- **Corona:** Soft, non-clipping volumetric outer glow extending to $1.35\times$ solar radius.
- **Illumination:** Central warm light ($500\text{ W}$) providing accurate inverse-square physical falloff across planetary orbits.

### 1.3 Recognisable Planet Materials (Prompt §10)
Every world is instantly recognizable without textual identification:
- **Mercury:** Dark gray rocky terrain, micro-craters, zero atmosphere.
- **Venus:** Smooth, impenetrable cream/gold cloud canopy, soft golden Rayleigh limb.
- **Earth:** Royal blue oceans (specular 0.45, roughness 0.35), continental landmasses with biome coloration, and bright cyan-blue atmospheric rim ($450\text{ nm}$).
- **Mars:** Terracotta and rust-red oxidized deserts, dark basaltic maria, and crisp brilliant-white polar ice cap ($Z > 0.85$).
- **Jupiter:** Striated turbulent cloud belts (alternating ochre, amber, and cream), subtle Great Red Spot vortex.
- **Saturn:** Golden-ochre banded sphere with authentic $26.73^\circ$ tilted ring system featuring distinct A/B rings and the dark Cassini Division.
- **Uranus:** Pale, serene aquamarine/cyan with subtle methane absorption.
- **Neptune:** Deep, electric cobalt blue with soft cloud streaks.

### 1.4 Controlled Long-Exposure Orbital Trails (TRAIL-04)
- Thin, glowing, laser-precise motion ribbons ($0.0004\text{ BU}$ for closeups, $0.006\text{ BU}$ for panoramic).
- Planet-specific chromatic signatures:
  - Mercury: Silver / cool white (`#E0E5EA`)
  - Venus: Warm pale gold (`#F4E2A8`)
  - Earth: Azure cyan-blue (`#4FA8F5`)
  - Mars: Rust orange (`#E86A38`)
  - Jupiter: Amber cream (`#F0D095`)
  - Saturn: Pale gold (`#E8D49E`)
  - Uranus: Pale aquamarine (`#7FE5D9`)
  - Neptune: Cobalt electric blue (`#3B72EC`)
- Never an overpowering thick neon tube; trails flow smoothly behind the trailing hemisphere of each world.

### 1.5 Documentary Data Panel (UI-03 + UI-07)
- Screen-space camera-parented HUD positioned in safe title margins ($X=-0.27, Y=0.16$).
- Clean scientific typography with planet accent-colored headers.
- Monospace-aligned numeric data displays up to 4 key metrics (Distance, Speed, Orbit %, Sun Distance) without overlapping celestial bodies.
