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

## 1b. Long Versions: Continuous Clock, Zoom Into Every Planet

Two ~9-minute landscape cuts where time never freezes: one shared Earth clock drives all
eight planets on their real Kepler orbits, and the camera keeps leaving the whole system
to visit each world, then pulls back out so you see how they move against each other.

```bash
python3 projects/solar_system_time_journey/generate.py --journey --lang tr            # Format A
python3 projects/solar_system_time_journey/generate.py --shared-clock-long --lang tr  # Format B
# or double-click render_long_versions_macos.command (Turkish; pass `en` for English)
```

| | Format A: System Journey | Format B: Shared Clock (long) |
|---|---|---|
| Script | `render_system_journey.py` | `render_shared_clock.py --long` |
| Length | 9:25, 16,950 frames, 2560x1440 | 9:09, 16,470 frames, 1920x1080 |
| Structure | `project.json` timeline: 3 acts x 8 focus shots + comparisons | intro, then 3 acts (clock 0 -> 1 -> 30 -> 365 days), each: grid, 8 planet zooms, summary |
| Zoomed in | camera rides with the planet; growing trail; real spin axis vs. orbit normal with the tilt angle; prime meridian; distance, orbit angle, speed, Sun distance, spin, local days | real tilt arc; orbit inset (seen from north) with the angle swept so far; spin, local days, day length |
| Pulled back | whole system at the same moment: swept-angle wedges, Sun-planet "clock hands", lap panel for all 8 | the 8-planet grid on the same clock; bars rescale per act |
| Output | `output/.../final/solar_system_journey_<lang>_1440p.mp4` | `output/.../final/solar_shared_clock_9min_<lang>.mp4` |

Useful flags (both): `--still 2400 7200` renders test frames only (into `output/.../journey_stills/`
or next to the frames), `--test START` renders a fresh 20 s clip from that frame into its own folder
and encodes it to `output/.../final/test_*.mp4` (e.g. `--journey --test 5850`,
`--shared-clock-long --test 10981`), `--range START END` renders a slice, `--res W H` / `--samples N`
override quality.
Renders are resumable: existing PNG frames are skipped, and the MP4 is encoded once all frames exist.

Science behind the new detail: `science/attitude.py` gives each planet's real spin-axis direction
(IAU pole RA/Dec -> J2000 ecliptic); `science/validation.py` checks it reproduces the NASA obliquities.
Surface spin faster than ~35° per frame (act III) is drawn rate-limited with the meridian stripe hidden;
all on-screen numbers stay exact.

## 1c. Journey v2 (20 s sample: Mercury, 30 Earth days)

The new edit direction, first as one 20 s sample: question -> Mercury's orbit lights up and the
camera settles -> one Earth clock runs the counter, the motion and every number -> readable result
-> back to the whole system with time held, the result flies into its table row -> "same 30 days:
Venus" with a labelled return to the start.

```bash
python3 -m pip install --user pillow          # once: the text layer is drawn with Pillow
python3 projects/solar_system_time_journey/generate.py --journey-v2-sample --lang tr
# faster preview: --res 1280 720 --samples 8 ; no GPU: add --engine CYCLES
# text/layout change only: add --skip-3d (reuses the 3D frames) ; layout boxes: --debug
```

Two passes share one timeline (`journey_v2/timeline.py`) and one camera model (`journey_v2/camera.py`):
`render_journey_v2.py` (Blender) draws only stars, Sun and planets; `overlay_v2.py` (plain Python)
draws text, orbits, paths, arcs, labels and the table as transparent PNGs; FFmpeg lays one over the
other and adds `journey_v2/audio.py`'s soundtrack. A wording change never needs a 3D re-render.
`overlay_v2.py` also writes `qa_overlay_<lang>.json`: text/label/planet/Sun collisions and safe-area
breaks per frame, and how far the Sun moves on screen (0 px whenever the camera holds).
While the camera is on the planet, a round "close-up" window shows it large (rendered by the 3D pass
from the same viewing direction: real map, axis, spin and day/night), with the live spin counter.
Output: `output/.../final/journey_v2_sample_<lang>_<H>p.mp4`.

## 1d. Planet surfaces and music (all formats)

**Planets** use real surface maps (Solar System Scope, CC BY 4.0, from NASA data; see
`assets/textures/CREDITS.md`) through `planet_look.py`: relief near the day/night line, Earth's city
lights, clouds and ocean glint, Venus' cloud deck, limb darkening, real oblateness, Saturn's real ring
profile, and each map turned to the IAU prime meridian (Greenwich has local noon at J2000.0).
The repository ships 4K maps. Optional 8K originals and memory control:

```bash
python3 projects/solar_system_time_journey/tools/download_textures.py     # 8K originals, ~60 MB (git-ignored)
SOLAR_TEX=4k python3 ...    # cap map size (8k > 4k > 2k is picked by default); SOLAR_TEX=off: old procedural look
```

**Music**: every video gets the calm, original score `assets/audio/music/solar_calm_10min.m4a`
(made by `tools/make_music.py`) through `soundtrack.py`, at -17 LUFS. Videos longer than 2 minutes
start it from the top (longer than 10 minutes: it continues with a cross-fade); tests and 20 s samples
start at a random point, printed so a take can be repeated:

```bash
SOLAR_MUSIC_OFFSET=190.4 python3 ...        # same music start as a previous test
SOLAR_MUSIC=~/Music/my_track.mp3 python3 ... # use your own track instead
```

The v2 sample adds only soft cues under the music: a low "breath" on camera moves, one quiet chime
when the clock reaches its target, and an in-key glide under the labelled rewind.

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
