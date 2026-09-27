"""Blender scene builder: Sun, planets, trails, stars, lighting, camera, UI, render.

This script executes inside Blender's Python environment.
It uses NASA/JPL planetary data, Keplerian orbital physics, and calibrated visual
scaling to create a premium cinematic documentary visualization.

Usage:
    blender --background --python projects/solar_system_time_journey/blender_build.py -- --proof-stills
    blender --background --python projects/solar_system_time_journey/blender_build.py -- --proof-clip
    blender --background --python projects/solar_system_time_journey/blender_build.py -- <job.json>
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ── Detect Blender environment ──────────────────────────────────────────
try:
    import bpy
    import bmesh
    import mathutils
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False
    print("ERROR: This script must run inside Blender's Python environment.")
    sys.exit(1)

# Project paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR
DATA_DIR = PROJECT_DIR / "data"
ASSETS_DIR = PROJECT_DIR / "assets"
OUTPUT_DIR = PROJECT_DIR.parent.parent / "output" / "solar_system_time_journey"

# Add project root to sys.path for science imports
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from science.planet_data import (
    PLANETS, PLANET_ORDER, TRAIL_COLORS, AU_KM, SOLAR_RADIUS_KM
)
from science.kepler import heliocentric_position, orbital_arc_length
from science.coordinates import (
    ecliptic_km_to_blender, planet_visual_radius, sun_visual_radius,
    VISUAL_SCALE_AU
)
from science.metrics import compute_all_metrics

# ═══════════════════════════════════════════════════════════════════════
#  CONFIGURATION & SPECS
# ═══════════════════════════════════════════════════════════════════════

PREVIEW_RES = (960, 540)
PROOF_RES   = (1280, 720)
FINAL_RES   = (2560, 1440)
FPS = 30

# The 6 Lookdev Proof Stills specified in SOURCE_PROMPT §28
PROOF_STILLS = [
    {"name": "01_solar_wide",      "camera": "CAM_SOLAR_WIDE",       "days": 0,   "focus": None},
    {"name": "02_mercury_follow",  "camera": "CAM_PLANET_FOLLOW",    "days": 30,  "focus": "mercury"},
    {"name": "03_earth_follow",    "camera": "CAM_PLANET_FOLLOW",    "days": 365, "focus": "earth"},
    {"name": "04_jupiter_follow",  "camera": "CAM_PLANET_FOLLOW",    "days": 365, "focus": "jupiter"},
    {"name": "05_saturn_follow",   "camera": "CAM_PLANET_FOLLOW",    "days": 365, "focus": "saturn"},
    {"name": "06_year_comparison", "camera": "CAM_YEAR_COMPARISON",  "days": 365, "focus": None},
]

# Proof clip shots: ~25s preview video (750 frames total at 30 fps)
PROOF_CLIP_SHOTS = [
    {"label": "01_wide_opening",    "camera": "CAM_SOLAR_WIDE",       "days": 0,   "focus": None,      "frames": 150},
    {"label": "02_earth_focus",     "camera": "CAM_PLANET_FOLLOW",    "days": 365, "focus": "earth",   "frames": 200},
    {"label": "03_jupiter_focus",   "camera": "CAM_PLANET_FOLLOW",    "days": 365, "focus": "jupiter", "frames": 200},
    {"label": "04_year_comparison", "camera": "CAM_YEAR_COMPARISON",  "days": 365, "focus": None,      "frames": 200},
]


# ═══════════════════════════════════════════════════════════════════════
#  SCENE CLEANUP & RENDER SETTINGS
# ═══════════════════════════════════════════════════════════════════════

def clear_scene():
    """Remove all objects and unlinked data blocks."""
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

    for block in list(bpy.data.meshes):
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in list(bpy.data.materials):
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in list(bpy.data.cameras):
        if block.users == 0:
            bpy.data.cameras.remove(block)
    for block in list(bpy.data.lights):
        if block.users == 0:
            bpy.data.lights.remove(block)
    for block in list(bpy.data.curves):
        if block.users == 0:
            bpy.data.curves.remove(block)


def setup_render_settings(resolution: tuple = PROOF_RES, samples: int = 48):
    """Configure Blender 5.2 EEVEE render settings and color management."""
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.film_transparent = False

    eevee = scene.eevee
    if hasattr(eevee, 'taa_render_samples'):
        eevee.taa_render_samples = samples

    # Color management: AgX
    scene.view_settings.view_transform = 'AgX'
    if 'AgX - Base Contrast' in [opt.identifier for opt in scene.view_settings.bl_rna.properties['look'].enum_items]:
        scene.view_settings.look = 'AgX - Base Contrast'


def setup_world_starfield():
    """Create a deep black space world with tiny sharp pinprick stars."""
    scene = bpy.context.scene
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-1000, 0)

    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-800, 0)
    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])

    # Layer 1: Tiny sharp pinprick stars (scale 350)
    voronoi_bright = nodes.new('ShaderNodeTexVoronoi')
    voronoi_bright.voronoi_dimensions = '3D'
    voronoi_bright.inputs['Scale'].default_value = 350.0
    voronoi_bright.location = (-600, 200)
    links.new(mapping.outputs['Vector'], voronoi_bright.inputs['Vector'])

    ramp_bright = nodes.new('ShaderNodeValToRGB')
    ramp_bright.color_ramp.elements[0].position = 0.985
    ramp_bright.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_bright.color_ramp.elements[1].position = 0.998
    ramp_bright.color_ramp.elements[1].color = (2.2, 2.2, 2.5, 1.0)
    ramp_bright.location = (-400, 200)
    links.new(voronoi_bright.outputs['Distance'], ramp_bright.inputs['Fac'])

    # Layer 2: Ultra-dense faint distant stars (scale 700)
    voronoi_faint = nodes.new('ShaderNodeTexVoronoi')
    voronoi_faint.voronoi_dimensions = '3D'
    voronoi_faint.inputs['Scale'].default_value = 700.0
    voronoi_faint.location = (-600, -150)
    links.new(mapping.outputs['Vector'], voronoi_faint.inputs['Vector'])

    ramp_faint = nodes.new('ShaderNodeValToRGB')
    ramp_faint.color_ramp.elements[0].position = 0.990
    ramp_faint.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_faint.color_ramp.elements[1].position = 0.999
    ramp_faint.color_ramp.elements[1].color = (0.9, 0.9, 1.0, 1.0)
    ramp_faint.location = (-400, -150)
    links.new(voronoi_faint.outputs['Distance'], ramp_faint.inputs['Fac'])

    # Add both star layers
    add_stars = nodes.new('ShaderNodeMix')
    add_stars.data_type = 'RGBA'
    add_stars.blend_type = 'ADD'
    add_stars.inputs['Factor'].default_value = 1.0
    add_stars.location = (-150, 50)
    links.new(ramp_bright.outputs['Color'], add_stars.inputs[6])
    links.new(ramp_faint.outputs['Color'], add_stars.inputs[7])

    bg = nodes.new('ShaderNodeBackground')
    bg.location = (100, 0)
    bg.inputs['Strength'].default_value = 1.0
    links.new(add_stars.outputs[2], bg.inputs['Color'])

    output = nodes.new('ShaderNodeOutputWorld')
    output.location = (300, 0)
    links.new(bg.outputs['Background'], output.inputs['Surface'])


# ═══════════════════════════════════════════════════════════════════════
#  PROCEDURAL SUN
# ═══════════════════════════════════════════════════════════════════════

def create_sun():
    """Create the Sun with procedural granulation, limb darkening, corona, and light."""
    radius = sun_visual_radius()  # 0.12 BU
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=radius, location=(0, 0, 0))
    sun = bpy.context.active_object
    sun.name = "Sun"
    bpy.ops.object.shade_smooth()

    mat = bpy.data.materials.new("Sun_Surface_Mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-1000, 0)

    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-800, 0)
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

    voronoi = nodes.new('ShaderNodeTexVoronoi')
    voronoi.voronoi_dimensions = '3D'
    voronoi.inputs['Scale'].default_value = 35.0
    voronoi.location = (-600, 150)
    links.new(mapping.outputs['Vector'], voronoi.inputs['Vector'])

    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 20.0
    noise.inputs['Detail'].default_value = 4.0
    noise.location = (-600, -100)
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

    mix_gran = nodes.new('ShaderNodeMix')
    mix_gran.data_type = 'FLOAT'
    mix_gran.inputs['Factor'].default_value = 0.35
    mix_gran.location = (-400, 50)
    links.new(voronoi.outputs['Distance'], mix_gran.inputs[2])
    links.new(noise.outputs['Fac'], mix_gran.inputs[3])

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[0].color = (1.0, 0.94, 0.75, 1.0)  # Core warm gold
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (1.0, 0.60, 0.15, 1.0)  # Amber edge
    ramp.location = (-200, 50)
    links.new(mix_gran.outputs[0], ramp.inputs['Fac'])

    fresnel = nodes.new('ShaderNodeFresnel')
    fresnel.inputs['IOR'].default_value = 1.15
    fresnel.location = (-200, -200)

    mix_limb = nodes.new('ShaderNodeMix')
    mix_limb.data_type = 'RGBA'
    mix_limb.blend_type = 'MULTIPLY'
    mix_limb.inputs['Factor'].default_value = 0.4
    mix_limb.location = (50, 0)
    links.new(ramp.outputs['Color'], mix_limb.inputs[6])
    links.new(fresnel.outputs['Fac'], mix_limb.inputs[7])

    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Strength'].default_value = 3.2
    emission.location = (250, 0)
    links.new(mix_limb.outputs[2], emission.inputs['Color'])

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (450, 0)
    links.new(emission.outputs['Emission'], output.inputs['Surface'])

    sun.data.materials.append(mat)

    # Solar Corona
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=radius * 1.35, location=(0, 0, 0))
    corona = bpy.context.active_object
    corona.name = "Sun_Corona"
    bpy.ops.object.shade_smooth()

    cmat = bpy.data.materials.new("Sun_Corona_Mat")
    cmat.use_nodes = True
    cnodes = cmat.node_tree.nodes
    clinks = cmat.node_tree.links
    cnodes.clear()

    cfresnel = cnodes.new('ShaderNodeFresnel')
    cfresnel.inputs['IOR'].default_value = 1.08
    cfresnel.location = (-300, 0)

    cemission = cnodes.new('ShaderNodeEmission')
    cemission.inputs['Color'].default_value = (1.0, 0.70, 0.25, 1.0)
    cemission.inputs['Strength'].default_value = 1.5
    cemission.location = (-100, 100)

    ctrans = cnodes.new('ShaderNodeBsdfTransparent')
    ctrans.location = (-100, -100)

    cmix = cnodes.new('ShaderNodeMixShader')
    cmix.location = (150, 0)
    clinks.new(cfresnel.outputs['Fac'], cmix.inputs['Fac'])
    clinks.new(ctrans.outputs['BSDF'], cmix.inputs[1])
    clinks.new(cemission.outputs['Emission'], cmix.inputs[2])

    coutput = cnodes.new('ShaderNodeOutputMaterial')
    coutput.location = (350, 0)
    clinks.new(cmix.outputs['Shader'], coutput.inputs['Surface'])
    corona.data.materials.append(cmat)

    # Central Point Light
    bpy.ops.object.light_add(type='POINT', radius=radius, location=(0, 0, 0))
    sun_light = bpy.context.active_object
    sun_light.name = "SunLight"
    sun_light.data.energy = 500.0
    sun_light.data.color = (1.0, 0.97, 0.92)

    return sun


# ═══════════════════════════════════════════════════════════════════════
#  PLANET MATERIALS (Identifiable without labels!)
# ═══════════════════════════════════════════════════════════════════════

def build_planet_material(name: str) -> bpy.types.Material:
    """Planet material: the real surface maps when they are installed (planet_look.py),
    otherwise rich procedural PBR materials tailored to each planet's appearance."""
    from planet_look import textured_material
    tex = textured_material(name)
    if tex is not None:
        return tex
    mat = bpy.data.materials.new(f"Planet_{name.capitalize()}_Mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-1000, 0)

    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-800, 0)
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (400, 0)

    if name == "mercury":
        # Gray rocky, cratered Voronoi surface
        voronoi = nodes.new('ShaderNodeTexVoronoi')
        voronoi.voronoi_dimensions = '3D'
        voronoi.inputs['Scale'].default_value = 55.0
        voronoi.location = (-600, 0)
        links.new(mapping.outputs['Vector'], voronoi.inputs['Vector'])

        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.2
        ramp.color_ramp.elements[0].color = (0.28, 0.27, 0.26, 1.0)
        ramp.color_ramp.elements[1].position = 0.8
        ramp.color_ramp.elements[1].color = (0.55, 0.53, 0.50, 1.0)
        ramp.location = (-350, 0)
        links.new(voronoi.outputs['Distance'], ramp.inputs['Fac'])

        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.85
        bsdf.inputs['Specular IOR Level'].default_value = 0.2
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    elif name == "venus":
        # Dense pale gold/cream cloud atmosphere
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 8.0
        noise.inputs['Detail'].default_value = 4.0
        noise.location = (-600, 0)
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.3
        ramp.color_ramp.elements[0].color = (0.86, 0.76, 0.52, 1.0)
        ramp.color_ramp.elements[1].position = 0.7
        ramp.color_ramp.elements[1].color = (0.95, 0.88, 0.68, 1.0)
        ramp.location = (-350, 0)
        links.new(noise.outputs['Fac'], ramp.inputs['Fac'])

        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.60
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    elif name == "earth":
        # Blue oceans + green/tan continents
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 6.0
        noise.inputs['Detail'].default_value = 8.0
        noise.inputs['Roughness'].default_value = 0.55
        noise.location = (-600, 0)
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.48
        ramp.color_ramp.elements[0].color = (0.04, 0.18, 0.52, 1.0)  # Deep ocean
        ramp.color_ramp.elements[1].position = 0.52
        ramp.color_ramp.elements[1].color = (0.18, 0.42, 0.22, 1.0)  # Land / vegetation
        elem2 = ramp.color_ramp.elements.new(0.65)
        elem2.color = (0.48, 0.40, 0.26, 1.0)  # Mountain / desert
        ramp.location = (-350, 0)
        links.new(noise.outputs['Fac'], ramp.inputs['Fac'])

        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.35
        bsdf.inputs['Specular IOR Level'].default_value = 0.45

        # Cyan atmospheric Fresnel rim
        fresnel = nodes.new('ShaderNodeFresnel')
        fresnel.inputs['IOR'].default_value = 1.08
        fresnel.location = (-100, -200)

        atmo = nodes.new('ShaderNodeEmission')
        atmo.inputs['Color'].default_value = (0.35, 0.68, 1.0, 1.0)
        atmo.inputs['Strength'].default_value = 0.7
        atmo.location = (100, -200)

        mix = nodes.new('ShaderNodeMixShader')
        mix.location = (250, 0)
        links.new(fresnel.outputs['Fac'], mix.inputs['Fac'])
        links.new(bsdf.outputs['BSDF'], mix.inputs[1])
        links.new(atmo.outputs['Emission'], mix.inputs[2])
        links.new(mix.outputs['Shader'], output.inputs['Surface'])

    elif name == "mars":
        # Rust red surface with dark maria and white polar ice
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 10.0
        noise.inputs['Detail'].default_value = 6.0
        noise.location = (-600, 0)
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[0].color = (0.42, 0.18, 0.09, 1.0)  # Dark volcanic basalt
        ramp.color_ramp.elements[1].position = 0.65
        ramp.color_ramp.elements[1].color = (0.78, 0.32, 0.12, 1.0)  # Rust red highlands
        ramp.location = (-350, 0)
        links.new(noise.outputs['Fac'], ramp.inputs['Fac'])

        # Polar cap via Separate XYZ
        sep_xyz = nodes.new('ShaderNodeSeparateXYZ')
        sep_xyz.location = (-600, -300)
        links.new(mapping.outputs['Vector'], sep_xyz.inputs['Vector'])

        ice_ramp = nodes.new('ShaderNodeValToRGB')
        ice_ramp.color_ramp.elements[0].position = 0.85
        ice_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
        ice_ramp.color_ramp.elements[1].position = 0.90
        ice_ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
        ice_ramp.location = (-350, -300)
        links.new(sep_xyz.outputs['Z'], ice_ramp.inputs['Fac'])

        mix_ice = nodes.new('ShaderNodeMix')
        mix_ice.data_type = 'RGBA'
        mix_ice.location = (-100, 0)
        links.new(ice_ramp.outputs['Color'], mix_ice.inputs['Factor'])
        links.new(ramp.outputs['Color'], mix_ice.inputs[6])
        mix_ice.inputs[7].default_value = (0.95, 0.98, 1.0, 1.0)  # Crisp polar ice

        links.new(mix_ice.outputs[2], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.82
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    elif name == "jupiter":
        # Striated atmospheric bands + Great Red Spot
        wave = nodes.new('ShaderNodeTexWave')
        wave.wave_type = 'BANDS'
        wave.bands_direction = 'Z'
        wave.inputs['Scale'].default_value = 16.0
        wave.inputs['Distortion'].default_value = 3.5
        wave.inputs['Detail'].default_value = 5.0
        wave.location = (-600, 100)
        links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.2
        ramp.color_ramp.elements[0].color = (0.68, 0.50, 0.32, 1.0)  # Dark belt
        ramp.color_ramp.elements[1].position = 0.8
        ramp.color_ramp.elements[1].color = (0.92, 0.82, 0.65, 1.0)  # Light zone
        ramp.location = (-350, 100)
        links.new(wave.outputs['Color'], ramp.inputs['Fac'])

        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.65
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    elif name == "saturn":
        # Golden-ochre delicate bands
        wave = nodes.new('ShaderNodeTexWave')
        wave.wave_type = 'BANDS'
        wave.bands_direction = 'Z'
        wave.inputs['Scale'].default_value = 12.0
        wave.inputs['Distortion'].default_value = 1.5
        wave.location = (-600, 0)
        links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.3
        ramp.color_ramp.elements[0].color = (0.78, 0.68, 0.44, 1.0)
        ramp.color_ramp.elements[1].position = 0.7
        ramp.color_ramp.elements[1].color = (0.88, 0.80, 0.60, 1.0)
        ramp.location = (-350, 0)
        links.new(wave.outputs['Color'], ramp.inputs['Fac'])

        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.70
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    elif name == "uranus":
        # Pale serene cyan
        bsdf.inputs['Base Color'].default_value = (0.55, 0.82, 0.85, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.50
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    elif name == "neptune":
        # Deep vivid cobalt blue
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 8.0
        noise.inputs['Detail'].default_value = 3.0
        noise.location = (-600, 0)
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.4
        ramp.color_ramp.elements[0].color = (0.10, 0.22, 0.68, 1.0)  # Cobalt
        ramp.color_ramp.elements[1].position = 0.6
        ramp.color_ramp.elements[1].color = (0.18, 0.36, 0.88, 1.0)  # Azure
        ramp.location = (-350, 0)
        links.new(noise.outputs['Fac'], ramp.inputs['Fac'])

        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.45
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    else:
        bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    return mat


def create_saturn_rings(saturn_obj, vis_r: float):
    """Create tilted, multi-banded rings for Saturn with Cassini Division."""
    inner_r = vis_r * 1.35
    outer_r = vis_r * 2.35

    # Create mesh disk at local (0, 0, 0) and parent to Saturn
    bpy.ops.mesh.primitive_cylinder_add(
        radius=outer_r, depth=0.0001, vertices=128, location=(0, 0, 0)
    )
    ring = bpy.context.active_object
    ring.name = "Saturn_Rings"
    ring.parent = saturn_obj
    ring.location = (0, 0, 0)
    ring.rotation_euler = (math.radians(26.73), 0.0, 0.0)

    # Material with radial distance shading and Cassini Division
    mat = bpy.data.materials.new("Saturn_Ring_System_Mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-800, 0)

    sep_xyz = nodes.new('ShaderNodeSeparateXYZ')
    sep_xyz.location = (-600, 0)
    links.new(tex_coord.outputs['Object'], sep_xyz.inputs['Vector'])

    math_x2 = nodes.new('ShaderNodeMath')
    math_x2.operation = 'MULTIPLY'
    math_x2.location = (-400, 100)
    links.new(sep_xyz.outputs['X'], math_x2.inputs[0])
    links.new(sep_xyz.outputs['X'], math_x2.inputs[1])

    math_y2 = nodes.new('ShaderNodeMath')
    math_y2.operation = 'MULTIPLY'
    math_y2.location = (-400, -100)
    links.new(sep_xyz.outputs['Y'], math_y2.inputs[0])
    links.new(sep_xyz.outputs['Y'], math_y2.inputs[1])

    math_sum = nodes.new('ShaderNodeMath')
    math_sum.operation = 'ADD'
    math_sum.location = (-200, 0)
    links.new(math_x2.outputs['Value'], math_sum.inputs[0])
    links.new(math_y2.outputs['Value'], math_sum.inputs[1])

    math_dist = nodes.new('ShaderNodeMath')
    math_dist.operation = 'SQRT'
    math_dist.location = (0, 0)
    links.new(math_sum.outputs['Value'], math_dist.inputs[0])

    map_range = nodes.new('ShaderNodeMapRange')
    map_range.inputs['From Min'].default_value = 0.0
    map_range.inputs['From Max'].default_value = outer_r
    map_range.inputs['To Min'].default_value = 0.0
    map_range.inputs['To Max'].default_value = 1.0
    map_range.clamp = True
    map_range.location = (200, 0)
    links.new(math_dist.outputs['Value'], map_range.inputs['Value'])

    inner_norm = inner_r / outer_r  # ~0.574

    # Alpha mask: inner hole (0), Ring B (0.9), Cassini Division (0.05), Ring A (0.75), outer edge (0)
    alpha_ramp = nodes.new('ShaderNodeValToRGB')
    alpha_ramp.color_ramp.elements[0].position = 0.0
    alpha_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    alpha_ramp.color_ramp.elements[1].position = inner_norm
    alpha_ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)

    e1 = alpha_ramp.color_ramp.elements.new(inner_norm + 0.01)
    e1.color = (0.9, 0.9, 0.9, 1.0)
    e2 = alpha_ramp.color_ramp.elements.new(0.72)
    e2.color = (0.9, 0.9, 0.9, 1.0)
    e3 = alpha_ramp.color_ramp.elements.new(0.74)
    e3.color = (0.05, 0.05, 0.05, 1.0)  # Cassini Division
    e4 = alpha_ramp.color_ramp.elements.new(0.77)
    e4.color = (0.8, 0.8, 0.8, 1.0)
    e5 = alpha_ramp.color_ramp.elements.new(0.97)
    e5.color = (0.75, 0.75, 0.75, 1.0)
    e6 = alpha_ramp.color_ramp.elements.new(0.99)
    e6.color = (0.0, 0.0, 0.0, 1.0)
    alpha_ramp.location = (450, -150)
    links.new(map_range.outputs['Result'], alpha_ramp.inputs['Fac'])

    # Color ramp for golden ring bands
    color_ramp = nodes.new('ShaderNodeValToRGB')
    color_ramp.color_ramp.elements[0].position = inner_norm
    color_ramp.color_ramp.elements[0].color = (0.75, 0.65, 0.48, 1.0)
    color_ramp.color_ramp.elements[1].position = 0.98
    color_ramp.color_ramp.elements[1].color = (0.88, 0.80, 0.62, 1.0)
    color_ramp.location = (450, 100)
    links.new(map_range.outputs['Result'], color_ramp.inputs['Fac'])

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.5
    bsdf.inputs['Emission Strength'].default_value = 0.35  # Self-luminescence so visible in space
    bsdf.location = (750, 0)
    links.new(color_ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(color_ramp.outputs['Color'], bsdf.inputs['Emission Color'])
    links.new(alpha_ramp.outputs['Color'], bsdf.inputs['Alpha'])

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (1000, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    from planet_look import ring_material       # the real ring profile, when installed
    ring.data.materials.append(ring_material(vis_r) or mat)
    return ring


def create_planets(days: float = 0.0):
    """Instantiate all 8 planets at their Keplerian coordinates for time t=days."""
    planet_objects = {}
    for name in PLANET_ORDER:
        p = PLANETS[name]
        state = heliocentric_position(p, days)
        bx, by, bz = ecliptic_km_to_blender(state.x, state.y, state.z)
        vis_r = planet_visual_radius(p.mean_radius_km)

        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=40 if name in ("jupiter", "saturn") else 32,
            ring_count=20,
            radius=vis_r,
            location=(bx, by, bz),
        )
        obj = bpy.context.active_object
        obj.name = f"Planet_{name.capitalize()}"
        bpy.ops.object.shade_smooth()

        mat = build_planet_material(name)
        obj.data.materials.append(mat)

        if name == "saturn":
            create_saturn_rings(obj, vis_r)

        planet_objects[name] = obj

    return planet_objects


# ═══════════════════════════════════════════════════════════════════════
#  ORBITAL TRAILS & SCIENTIFIC GUIDES
# ═══════════════════════════════════════════════════════════════════════

def create_orbital_trail(planet_name: str, days: float, is_focused: bool = False,
                         n_samples: int = 400):
    """Create a sleek, glowing orbital trail showing the arc traveled."""
    if days <= 0:
        return None

    p = PLANETS[planet_name]
    color = TRAIL_COLORS[planet_name]
    vis_r = planet_visual_radius(p.mean_radius_km)

    # Current position of planet
    end_state = heliocentric_position(p, days)
    end_bx, end_by, end_bz = ecliptic_km_to_blender(end_state.x, end_state.y, end_state.z)

    # Sample trajectory points from t=0 to t=days
    points = []
    for i in range(n_samples + 1):
        t = days * (i / n_samples)
        st = heliocentric_position(p, t)
        bx, by, bz = ecliptic_km_to_blender(st.x, st.y, st.z)

        # In focus mode, trim points that are inside or too close to the planet
        # so the trail gracefully flows behind the planet without skewering through it!
        if is_focused and i > n_samples * 0.90:
            d_to_planet = math.sqrt((bx - end_bx)**2 + (by - end_by)**2 + (bz - end_bz)**2)
            if d_to_planet < vis_r * 0.95:
                continue

        points.append((bx, by, bz))

    if len(points) < 2:
        return None

    curve_data = bpy.data.curves.new(f"Trail_{planet_name}", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 4
    # Thin, sleek bevel depth: hair-thin for focus, clean for wide
    curve_data.bevel_depth = 0.0004 if is_focused else 0.006

    spline = curve_data.splines.new('POLY')
    spline.points.add(len(points) - 1)
    for i, (x, y, z) in enumerate(points):
        spline.points[i].co = (x, y, z, 1.0)

    trail_obj = bpy.data.objects.new(f"Trail_{planet_name}", curve_data)
    bpy.context.collection.objects.link(trail_obj)

    # Glowing emissive material
    mat = bpy.data.materials.new(f"Trail_Mat_{planet_name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (*color, 1.0)
    emission.inputs['Strength'].default_value = 3.5 if is_focused else 2.2
    emission.location = (0, 0)

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (250, 0)
    links.new(emission.outputs['Emission'], output.inputs['Surface'])

    trail_obj.data.materials.append(mat)
    return trail_obj


def create_faint_orbit_guide(planet_name: str, n_points: int = 240):
    """Create a faint (5-8% opacity) scientific orbit ellipse guide (Prompt §8)."""
    p = PLANETS[planet_name]
    color = TRAIL_COLORS[planet_name]

    points = []
    period = p.orbital_period_days
    for i in range(n_points + 1):
        t = period * (i / n_points)
        st = heliocentric_position(p, t)
        bx, by, bz = ecliptic_km_to_blender(st.x, st.y, st.z)
        points.append((bx, by, bz))

    curve_data = bpy.data.curves.new(f"Guide_{planet_name}", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 2
    curve_data.bevel_depth = 0.0003  # hairline

    spline = curve_data.splines.new('POLY')
    spline.points.add(len(points) - 1)
    for i, (x, y, z) in enumerate(points):
        spline.points[i].co = (x, y, z, 1.0)

    guide_obj = bpy.data.objects.new(f"Guide_{planet_name}", curve_data)
    bpy.context.collection.objects.link(guide_obj)

    mat = bpy.data.materials.new(f"Guide_Mat_{planet_name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (*color, 1.0)
    emission.inputs['Strength'].default_value = 0.2
    emission.location = (0, 100)

    trans = nodes.new('ShaderNodeBsdfTransparent')
    trans.location = (0, -100)

    mix = nodes.new('ShaderNodeMixShader')
    mix.inputs['Fac'].default_value = 0.94  # 6% subtle opacity
    mix.location = (200, 0)
    links.new(emission.outputs['Emission'], mix.inputs[1])
    links.new(trans.outputs['BSDF'], mix.inputs[2])

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (400, 0)
    links.new(mix.outputs['Shader'], output.inputs['Surface'])

    guide_obj.data.materials.append(mat)
    return guide_obj


# ═══════════════════════════════════════════════════════════════════════
#  DOCUMENTARY UI OVERLAY (UI-03 + UI-07 Data Strip)
# ═══════════════════════════════════════════════════════════════════════

def create_documentary_ui(planet_name: str, days: int, cam_obj: bpy.types.Object):
    """Create screen-space parented documentary HUD text strip."""
    metrics_file = DATA_DIR / "metrics_precomputed.json"
    if not metrics_file.exists():
        return []

    all_metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
    metrics_list = all_metrics.get(str(days), [])
    planet_m = next((m for m in metrics_list if m["planet"] == planet_name), None)
    if not planet_m:
        return []

    accent_color = (*TRAIL_COLORS[planet_name], 1.0)

    # Position UI on screen: Left side within safe title margins at Z = -1.0
    base_x = -0.27
    base_y = 0.16
    z_dist = -1.0

    texts = []

    def make_screen_text(text: str, pos: tuple, size: float, color: tuple):
        bpy.ops.object.text_add(location=(0, 0, 0))
        t_obj = bpy.context.active_object
        t_obj.name = f"UI_{text[:15]}"
        t_obj.parent = cam_obj
        t_obj.location = pos
        t_obj.rotation_euler = (0, 0, 0)
        t_obj.data.body = text
        t_obj.data.size = size
        t_obj.data.align_x = 'LEFT'
        t_obj.data.align_y = 'TOP'

        mat = bpy.data.materials.new(f"UI_Mat_{text[:10]}")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        emission = nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = color
        emission.inputs['Strength'].default_value = 2.2
        output = nodes.new('ShaderNodeOutputMaterial')
        links.new(emission.outputs['Emission'], output.inputs['Surface'])

        t_obj.data.materials.append(mat)
        texts.append(t_obj)
        return t_obj

    # 1. Header / Timeframe
    header_str = f"{days} EARTH DAY{'S' if days > 1 else ''}"
    make_screen_text(header_str, (base_x, base_y, z_dist), 0.011, (0.70, 0.75, 0.80, 1.0))

    # 2. Planet Name in Accent Color
    name_str = planet_name.upper()
    make_screen_text(name_str, (base_x, base_y - 0.018, z_dist), 0.024, accent_color)

    # 3. Divider
    make_screen_text("───────────────", (base_x, base_y - 0.048, z_dist), 0.011, (0.45, 0.50, 0.55, 1.0))

    # 4. Metric Lines (Prompt §18 priority)
    lines = []
    if days == 1:
        lines = [
            f"DISTANCE   {planet_m['distance_travelled_km']:,.0f} km",
            f"SPEED      {planet_m['avg_orbital_speed_kms']:.1f} km/s",
            f"ORBIT      {planet_m['orbit_fraction']*100:.3f}%",
        ]
    elif days == 30:
        lines = [
            f"DISTANCE   {planet_m['distance_travelled_million_km']:.2f}M km",
            f"SPEED      {planet_m['avg_orbital_speed_kms']:.1f} km/s",
            f"ORBIT      {planet_m['orbit_fraction']*100:.1f}%",
        ]
    elif days == 365:
        lines = [
            f"ORBITS     {planet_m['orbit_count']:.2f}×",
            f"DISTANCE   {planet_m['distance_travelled_million_km']:.1f}M km",
            f"SUN DIST   {planet_m['sun_distance_au']:.2f} AU",
            f"SPEED      {planet_m['avg_orbital_speed_kms']:.1f} km/s",
        ]

    for idx, l in enumerate(lines):
        y_pos = base_y - 0.068 - (idx * 0.020)
        make_screen_text(l, (base_x, y_pos, z_dist), 0.012, (0.92, 0.94, 0.96, 1.0))

    return texts


# ═══════════════════════════════════════════════════════════════════════
#  CAMERA SYSTEM & CINEMATIC FRAMING
# ═══════════════════════════════════════════════════════════════════════

def setup_camera(preset: str, focus_planet: str | None = None, days: float = 0.0) -> bpy.types.Object:
    """Position camera according to art direction (panoramic vs cinematic follow)."""
    cam_data = bpy.data.cameras.new("MainCamera")
    cam_data.clip_start = 0.01
    cam_data.clip_end = 200.0

    cam_obj = bpy.data.objects.new("MainCamera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    if preset == "CAM_SOLAR_WIDE":
        # Elevated panoramic wide view showing entire system clearly
        cam_obj.location = (0.0, -18.0, 12.0)
        cam_data.lens = 19
        direction = mathutils.Vector((0, 0, 0)) - mathutils.Vector(cam_obj.location)
        cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    elif preset == "CAM_YEAR_COMPARISON":
        # Year comparison view framing all orbits
        cam_obj.location = (0.0, -15.0, 10.0)
        cam_data.lens = 20
        direction = mathutils.Vector((0, 0, 0)) - mathutils.Vector(cam_obj.location)
        cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    elif preset == "CAM_PLANET_FOLLOW" and focus_planet:
        p = PLANETS[focus_planet]
        st = heliocentric_position(p, days)
        bx, by, bz = ecliptic_km_to_blender(st.x, st.y, st.z)
        vis_r = planet_visual_radius(p.mean_radius_km)

        # Distance: 7.5 times visual radius for heroic rule-of-thirds composition
        dist = vis_r * 7.5

        p_vec = mathutils.Vector((bx, by, bz))
        r_dist = p_vec.length
        u_r = p_vec.normalized() if r_dist > 0.001 else mathutils.Vector((1, 0, 0))

        # Velocity direction
        u_tangent = mathutils.Vector((-u_r.y, u_r.x, 0)).normalized()
        u_up = mathutils.Vector((0, 0, 1))

        # Position camera behind and to the side of the planet
        cam_pos = p_vec - u_tangent * (dist * 1.1) + u_r * (dist * 0.7) + u_up * (dist * 0.45)
        cam_obj.location = cam_pos
        cam_data.lens = 50

        # Look target offset so planet sits gracefully on the right third of the frame
        look_target = p_vec - u_tangent * (dist * 0.25)
        direction = look_target - cam_pos
        cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

        # Calibrated soft key light (scales with distance squared for uniform lux)
        bpy.ops.object.light_add(type='POINT', radius=vis_r * 0.5, location=(
            bx - u_r.x * dist * 1.2,
            by - u_r.y * dist * 1.2,
            bz + dist * 0.6
        ))
        key_light = bpy.context.active_object
        key_light.name = f"KeyLight_{focus_planet}"
        key_light.data.energy = 220.0 * (dist ** 2)
        key_light.data.color = (1.0, 0.98, 0.94)

        # Cool soft ambient fill
        bpy.ops.object.light_add(type='POINT', radius=vis_r, location=(
            cam_pos.x, cam_pos.y, cam_pos.z + dist * 0.5
        ))
        fill_light = bpy.context.active_object
        fill_light.name = f"FillLight_{focus_planet}"
        fill_light.data.energy = 30.0 * (dist ** 2)
        fill_light.data.color = (0.7, 0.8, 1.0)

    else:
        cam_obj.location = (0.0, -10.0, 6.0)
        cam_data.lens = 28
        direction = mathutils.Vector((0, 0, 0)) - mathutils.Vector(cam_obj.location)
        cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    return cam_obj


# ═══════════════════════════════════════════════════════════════════════
#  SCENE BUILDER
# ═══════════════════════════════════════════════════════════════════════

def build_scene(camera_preset: str, days: float, focus_planet: str | None,
                show_trails: bool = True, show_guides: bool = False,
                show_data_panel: bool = True, resolution: tuple = PROOF_RES,
                samples: int = 48) -> bpy.types.Object:
    """Build complete solar system scene with all layers."""
    clear_scene()
    setup_render_settings(resolution, samples)
    setup_world_starfield()

    # Core celestial bodies
    create_sun()
    create_planets(days)

    # Camera
    cam = setup_camera(camera_preset, focus_planet, days)

    # Trails
    if show_trails and days > 0:
        if focus_planet:
            create_orbital_trail(focus_planet, days, is_focused=True)
            for other in PLANET_ORDER:
                if other != focus_planet and other in ("mercury", "venus", "earth", "mars"):
                    create_orbital_trail(other, days, is_focused=False)
        else:
            for name in PLANET_ORDER:
                create_orbital_trail(name, days, is_focused=False)

    # Orbit guide (only for focused planet)
    if show_guides and focus_planet:
        create_faint_orbit_guide(focus_planet)

    # Data panel (only in focus mode)
    if show_data_panel and focus_planet and days > 0:
        create_documentary_ui(focus_planet, int(days), cam)

    return cam


# ═══════════════════════════════════════════════════════════════════════
#  RENDER PIPELINE (Stills, Clips, Resumable Frames)
# ═══════════════════════════════════════════════════════════════════════

def render_still(output_path: str):
    """Render a single frame directly to disk."""
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)


def run_proof_stills():
    """Render the 6 mandatory lookdev proof stills."""
    out_dir = OUTPUT_DIR / "proof_stills"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n==================================================")
    print(f" RENDERING 6 LOOKDEV PROOF STILLS -> {out_dir}")
    print(f"==================================================")

    for still in PROOF_STILLS:
        print(f"\n[STILL] Rendering {still['name']} (day={still['days']}, focus={still['focus']})...")
        build_scene(
            camera_preset=still["camera"],
            days=float(still["days"]),
            focus_planet=still["focus"],
            show_trails=still["days"] > 0,
            show_guides=still["focus"] is not None,
            show_data_panel=still["focus"] is not None,
            resolution=PROOF_RES,
            samples=48,
        )
        dest = str(out_dir / f"{still['name']}.png")
        render_still(dest)
        print(f"  ✓ Saved: {dest}")

    print(f"\n✅ All 6 proof stills rendered successfully to {out_dir}")


def run_proof_clip():
    """Render 20-30s low-res preview video (preview_visual_proof.mp4) (Prompt §28)."""
    out_dir = OUTPUT_DIR / "proof_clip"
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n==================================================")
    print(f" RENDERING PROOF CLIP FRAMES -> {frames_dir}")
    print(f"==================================================")

    frame_idx = 0
    # Clean previous frames if any
    for existing_f in frames_dir.glob("frame_*.png"):
        existing_f.unlink()

    for shot in PROOF_CLIP_SHOTS:
        print(f"\n[SHOT] {shot['label']}: {shot['frames']} frames (day={shot['days']}, focus={shot['focus']})...")
        build_scene(
            camera_preset=shot["camera"],
            days=float(shot["days"]),
            focus_planet=shot["focus"],
            show_trails=shot["days"] > 0,
            show_guides=shot["focus"] is not None,
            show_data_panel=shot["focus"] is not None,
            resolution=PREVIEW_RES,
            samples=16,
        )

        cam_obj = bpy.context.scene.camera
        initial_loc = mathutils.Vector(cam_obj.location)
        initial_rot = mathutils.Euler(cam_obj.rotation_euler)
        n_f = shot["frames"]

        for f in range(n_f):
            t_frac = f / max(1, n_f - 1)
            # Smooth ease-in-out curve
            smooth_t = (1.0 - math.cos(t_frac * math.pi)) * 0.5

            if shot["camera"] == "CAM_SOLAR_WIDE":
                # Slow cinematic inward dolly
                cam_obj.location = initial_loc * (1.0 - smooth_t * 0.15)
            elif shot["camera"] == "CAM_YEAR_COMPARISON":
                # Subtle outward crane reveal
                cam_obj.location.y = initial_loc.y - smooth_t * 2.5
                cam_obj.location.z = initial_loc.z + smooth_t * 1.5
            else:
                # Gentle orbital parallax drift for planet follow
                drift_x = math.sin(smooth_t * math.pi) * 0.08
                drift_z = math.cos(smooth_t * math.pi) * 0.04
                cam_obj.location.x = initial_loc.x + drift_x
                cam_obj.location.z = initial_loc.z + drift_z

            frame_path = str(frames_dir / f"frame_{frame_idx:06d}.png")
            render_still(frame_path)
            frame_idx += 1

    print(f"\n✅ {frame_idx} frames rendered to {frames_dir}")

    # FFmpeg encode to MP4
    if shutil.which("ffmpeg"):
        mp4_path = out_dir / "preview_visual_proof.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", str(frames_dir / "frame_%06d.png"),
            "-c:v", "libx264",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(mp4_path),
        ]
        print(f"\nEncoding proof video with FFmpeg: {mp4_path}")
        subprocess.run(cmd, check=True)
        print(f"✅ Proof video ready: {mp4_path}")


# ═══════════════════════════════════════════════════════════════════════
#  FULL 9:25 PRODUCTION RENDER PIPELINE
# ═══════════════════════════════════════════════════════════════════════

def create_title_card(title: str, subtitle: str, detail: str, cam_obj: bpy.types.Object):
    """Create screen-space centered title card for opening, chapters, outro."""
    texts = []
    def make_centered_text(text: str, pos: tuple, size: float, color: tuple):
        bpy.ops.object.text_add(location=(0, 0, 0))
        t_obj = bpy.context.active_object
        t_obj.name = f"Card_{text[:12]}"
        t_obj.parent = cam_obj
        t_obj.location = pos
        t_obj.rotation_euler = (0, 0, 0)
        t_obj.data.body = text
        t_obj.data.size = size
        t_obj.data.align_x = 'CENTER'
        t_obj.data.align_y = 'CENTER'

        mat = bpy.data.materials.new(f"Card_Mat_{text[:8]}")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        emission = nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = color
        emission.inputs['Strength'].default_value = 2.5
        output = nodes.new('ShaderNodeOutputMaterial')
        links.new(emission.outputs['Emission'], output.inputs['Surface'])

        t_obj.data.materials.append(mat)
        texts.append(t_obj)
        return t_obj

    make_centered_text(title, (0.0, 0.13, -1.0), 0.024, (1.0, 0.95, 0.85, 1.0))
    make_centered_text(subtitle, (0.0, 0.08, -1.0), 0.015, (0.75, 0.80, 0.88, 1.0))
    if detail:
        make_centered_text(detail, (0.0, 0.038, -1.0), 0.011, (0.55, 0.60, 0.65, 1.0))
    return texts


def run_final_render(resolution: tuple = FINAL_RES, samples: int = 16,
                     start_frame_arg: int | None = None, end_frame_arg: int | None = None):
    """Execute the full 32-shot 9:25 production render with resumable PNG frames."""
    plan_path = OUTPUT_DIR / "plan.json"
    if not plan_path.exists():
        print(f"ERROR: Plan file not found at {plan_path}")
        return

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    shots = plan.get("shots", [])
    total_frames = plan.get("total_frames", 16950)

    frames_dir = OUTPUT_DIR / "final_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    final_dir = OUTPUT_DIR / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    print("==================================================")
    print(f" FULL 9:25 PRODUCTION RENDER (16,950 FRAMES)")
    print(f" Resolution: {resolution[0]}x{resolution[1]} @ {samples} samples")
    print(f" Frames Dir: {frames_dir}")
    if start_frame_arg or end_frame_arg:
        print(f" Range: {start_frame_arg or 1} to {end_frame_arg or total_frames}")
    print("==================================================")

    for s_idx, shot in enumerate(shots, 1):
        s_id = shot["id"]
        kind = shot["kind"]
        f_start = shot["frame_start"]
        f_end = shot["frame_end"]
        planet = shot.get("planet")
        earth_days = float(shot.get("earth_days", 0))

        if start_frame_arg is not None and f_end < start_frame_arg:
            continue
        if end_frame_arg is not None and f_start > end_frame_arg:
            continue

        actual_f_start = max(f_start, start_frame_arg) if start_frame_arg is not None else f_start
        actual_f_end = min(f_end, end_frame_arg) if end_frame_arg is not None else f_end

        # Check existing frames in this shot
        missing = [f for f in range(actual_f_start, actual_f_end + 1)
                   if not (frames_dir / f"frame_{f:06d}.png").exists()]
        if not missing:
            print(f"[{s_idx}/32] {s_id} ({actual_f_start}-{actual_f_end}): All frames already rendered. Skipping.")
            continue

        print(f"\n[{s_idx}/32] {s_id} ({actual_f_start}-{actual_f_end}, {len(missing)} frames to render): {kind} {planet or ''}...")

        # Determine camera preset
        if kind == "focus":
            cam_preset = "CAM_PLANET_FOLLOW"
            focus_target = planet
            show_hud = True
            show_guides = True
        elif kind == "comparison":
            cam_preset = "CAM_YEAR_COMPARISON"
            focus_target = None
            show_hud = False
            show_guides = False
        else:
            cam_preset = "CAM_SOLAR_WIDE"
            focus_target = None
            show_hud = False
            show_guides = False

        # Build scene for this shot
        cam_obj = build_scene(
            camera_preset=cam_preset,
            days=earth_days,
            focus_planet=focus_target,
            show_trails=earth_days > 0,
            show_guides=show_guides,
            show_data_panel=show_hud,
            resolution=resolution,
            samples=samples,
        )

        # Add title cards if applicable
        if kind == "opening":
            create_title_card("THE SOLAR SYSTEM", "THROUGH EARTH TIME", "1 DAY • 30 DAYS • 365 DAYS", cam_obj)
        elif kind == "chapter":
            c_titles = {
                1: ("ACT I • 1 EARTH DAY", "24 HOURS", "How much does the Solar System move in a single day?"),
                30: ("ACT II • 30 EARTH DAYS", "ONE MONTH", "Now how much orbital motion emerges?"),
                365: ("ACT III • 365 EARTH DAYS", "ONE EARTH YEAR", "The Full Payoff: How does the system look after one year?"),
            }
            t, s, d = c_titles.get(int(earth_days), (f"CHAPTER {int(earth_days)} DAYS", "", ""))
            create_title_card(t, s, d, cam_obj)
        elif kind == "outro":
            create_title_card("ONE EARTH YEAR LATER", "Every world moves to a different cosmic clock.", "Solar System Time Journey", cam_obj)

        initial_cam_loc = mathutils.Vector(cam_obj.location)

        for f in range(actual_f_start, actual_f_end + 1):
            frame_file = frames_dir / f"frame_{f:06d}.png"
            if frame_file.exists() and frame_file.stat().st_size > 0:
                continue

            # Gentle camera movement
            u = (f - f_start) / max(1, f_end - f_start)
            smooth_u = (1.0 - math.cos(u * math.pi)) * 0.5
            cam_obj.location.x = initial_cam_loc.x + math.sin(smooth_u * math.pi) * 0.04

            render_still(str(frame_file))

            if f % 100 == 0:
                print(f"    Frame {f}/{total_frames} ({(f/total_frames)*100:.1f}%) rendered.")

    print("\n✅ Frame sequence rendering completed or up-to-date!")

    # FFmpeg assembly
    master_mp4 = final_dir / "solar_system_1_30_365_days_1440p.mp4"
    from soundtrack import prepare
    audio_wav = (prepare(len(list(frames_dir.glob("frame_*.png"))) / FPS, master_mp4)
                 or ASSETS_DIR / "audio" / "deep_space_ambience.wav")

    if shutil.which("ffmpeg"):
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", str(frames_dir / "frame_%06d.png"),
        ]
        if audio_wav.exists():
            cmd.extend([
                "-stream_loop", "-1",
                "-i", str(audio_wav),
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
            ])
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(master_mp4),
        ])
        print(f"\nEncoding master video: {master_mp4}")
        subprocess.run(cmd, check=True)
        if audio_wav.name.endswith(".music.wav"):
            audio_wav.unlink(missing_ok=True)
        print(f"✅ Final 9:25 1440p Master Video Ready: {master_mp4}")


# ═══════════════════════════════════════════════════════════════════════
#  CLI DISPATCH
# ═══════════════════════════════════════════════════════════════════════

def main():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []

    if not args:
        print("Usage:")
        print("  blender --background --python blender_build.py -- --proof-stills")
        print("  blender --background --python blender_build.py -- --proof-clip")
        print("  blender --background --python blender_build.py -- --render-final")
        return

    if "--proof-stills" in args:
        run_proof_stills()
    elif "--proof-clip" in args:
        run_proof_clip()
    elif "--render-final" in args:
        if "--range" in args:
            r_idx = args.index("--range")
            s_f = int(args[r_idx + 1])
            e_f = int(args[r_idx + 2])
            run_final_render(start_frame_arg=s_f, end_frame_arg=e_f)
        else:
            run_final_render()
    else:
        print(f"Unknown arguments: {args}")


if __name__ == "__main__":
    main()

