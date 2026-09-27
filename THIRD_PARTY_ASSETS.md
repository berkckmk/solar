# Third-Party Assets & Licensing Declaration

**Module:** `projects/solar_system_time_journey`  
**Compliance Requirement:** SOURCE_PROMPT §11 & §21 (Autonomous offline operation, open-source / public domain status)  

---

## 1. Asset Registry

| Asset Name | Category | Origin / Source | License Status | Local File Path | Offline Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Planetary Orbital Elements** | Scientific Data | NASA JPL Solar System Dynamics (Standish 1992, DE440) | Public Domain (U.S. Government Work) | `science/planet_data.py`, `data/metrics_precomputed.json` | Fully Offline |
| **Physical Planetary Parameters** | Scientific Data | NASA Goddard Space Flight Center (Planetary Fact Sheets 2024) | Public Domain (U.S. Government Work) | `science/planet_data.py` | Fully Offline |
| **Sun Shader & Corona** | Material Shader | Procedural node shader generated in Python | Original Work (MIT / Open License) | `blender_build.py` | Fully Offline |
| **Planet PBR Shaders (8 Worlds)** | Material Shader | Procedural node shaders generated in Python | Original Work (MIT / Open License) | `blender_build.py` | Fully Offline |
| **Saturn Ring System** | Geometry & Shader | Procedural mathematical disc with Cassini Division | Original Work (MIT / Open License) | `blender_build.py` | Fully Offline |
| **Cosmic Starfield** | World Shader | Procedural dual-frequency 3D Voronoi | Original Work (MIT / Open License) | `blender_build.py` | Fully Offline |
| **Deep Space Ambient Drone** | Audio | Synthesized harmonic sub-bass via mathematical wave formula | Original Work (CC0 Public Domain) | `assets/audio/deep_space_ambience.wav` | Fully Offline |

---

## 2. Trademarks & Brand Elements
- No NASA, JPL, ESA, or proprietary corporate logos, patches, or commercial typography are used anywhere in the video or codebase.
- The project is 100% self-contained and renders without requiring any active internet connection or external asset downloads.
