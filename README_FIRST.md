# Solar System Time Journey — Developer & Production Guide

**Module:** `projects/solar_system_time_journey`  
**Parent Workspace:** `3d-blender-youtube`  
**Video Concept:** *"How far does each planet travel in 1, 30, and 365 Earth days?"*  
**Duration:** 9:25 (565.0s, 16,950 frames @ 30 FPS, 16:9, 2560×1440 QHD)  

---

## 1. Quick Start Commands

All commands can be executed from the repository root:

```bash
# 1. Run astronomical Kepler science validation
python3 projects/solar_system_time_journey/generate.py --validate

# 2. Render the 6 Lookdev Proof Stills (EEVEE, 1280x720)
python3 projects/solar_system_time_journey/generate.py --stills

# 3. Render the 25-second Low-Res Proof Video (960x540 MP4)
python3 projects/solar_system_time_journey/generate.py --proof-clip

# 4. Or double-click the macOS command scripts:
./projects/solar_system_time_journey/render_preview_macos.command
./projects/solar_system_time_journey/render_final_macos.command
```

---

## 2. Deliverables & Output Locations

| Output | Path | Description |
|---|---|---|
| **Proof Stills (6x)** | `output/solar_system_time_journey/proof_stills/` | Full lookdev frames: Wide, Mercury, Earth, Jupiter, Saturn, Comparison. |
| **Proof Video** | `output/solar_system_time_journey/proof_clip/preview_visual_proof.mp4` | 25s continuous preview clip with animated cameras and HUD. |
| **Ambient Audio** | `projects/solar_system_time_journey/assets/audio/deep_space_ambience.wav` | 44.1kHz stereo ambient drone synthesized without copyright. |
| **Precomputed Data** | `projects/solar_system_time_journey/data/metrics_precomputed.json` | Instant Kepler solver cache for all 8 planets across 1/30/365 days. |
| **Final Video** | `output/solar_system_time_journey/final/solar_system_1_30_365_days_1440p.mp4` | Master 9:25 1440p production deliverable. |

---

## 3. Architecture & Documentation

- [`SCIENCE_NOTES.md`](SCIENCE_NOTES.md): NASA JPL sources, J2000 epoch, Keplerian equations, and numerical validation tables.
- [`VISUAL_STYLE.md`](VISUAL_STYLE.md): Shader formulas, lighting ratios, planet color palettes, and HUD design system.
- [`STORYBOARD.md`](STORYBOARD.md): Complete 32-shot timeline breakdown from 0:00 to 9:25.
- [`THIRD_PARTY_ASSETS.md`](THIRD_PARTY_ASSETS.md): Asset declarations and 100% offline license compliance.
- [`blender_build.py`](blender_build.py): Core Blender Python scene generator and render script.
