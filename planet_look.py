"""Real planet surfaces for every renderer (runs inside Blender).

Surface maps: Solar System Scope (https://www.solarsystemscope.com/textures/),
CC BY 4.0, made from NASA mission data. `assets/textures/` ships 4K copies
(`4k_*`, resized from the originals); `tools/download_textures.py` fetches the
8K originals. Missing maps fall back to the procedural look in blender_build.py.

What each planet gets, besides its colour map:
  - relief from the map itself (bump), so craters and volcanoes catch the
    light near the day/night line (Mercury, Mars),
  - Earth: night-side city lights, clouds, sun glint on the oceans,
  - Venus: its cloud deck (the surface is never visible),
  - gas giants and Venus: limb darkening; real oblateness (Saturn ~10 %),
  - Saturn: the real ring profile (C, B, Cassini Division, A) at the right radii,
  - the IAU prime meridian: at J2000 each map is turned the way the real planet
    was, so Greenwich has local noon at 12:00 TT on 1 January 2000.

Maps are sampled with the sphere's own UV layout, which is equirectangular with
longitude 0 on local +X and north on local +Z (the same frame the meridian
markers use). Venus and Uranus spin about the IAU south pole, so their maps
are turned 180 degrees about local X to keep north up and east eastward.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import bpy

from science.planet_data import PLANETS
from science.attitude import prime_meridian

TEX_DIR = Path(__file__).resolve().parent / "assets" / "textures"

# role -> file stem (Solar System Scope names, without the "8k_" / "4k_" / "2k_" prefix)
MAPS = {
    "mercury": {"color": "mercury"},
    "venus":   {"color": "venus_atmosphere"},
    "earth":   {"color": "earth_daymap", "night": "earth_nightmap", "clouds": "earth_clouds",
                "spec": "earth_specular_map"},
    "mars":    {"color": "mars"},
    "jupiter": {"color": "jupiter"},
    "saturn":  {"color": "saturn", "ring": "saturn_ring_alpha"},
    "uranus":  {"color": "uranus"},
    "neptune": {"color": "neptune"},
}

BUMP = {"mercury": 0.20, "mars": 0.15}                          # relief strength from the map
LIMB = {"venus": 0.30, "jupiter": 0.35, "saturn": 0.35, "uranus": 0.30, "neptune": 0.30}
FLATTENING = {"earth": 0.00335, "mars": 0.00589, "jupiter": 0.06487, "saturn": 0.09796,
              "uranus": 0.02293, "neptune": 0.01708}           # (a - c) / a, NASA fact sheets
NIGHT_STRENGTH = 1.6
SPEC_STRENGTH = 0.55

# Saturn ring map: texture u = 0..1 spans these radii (in Saturn radii); fitted so the
# C-ring edge (1.24), the Cassini Division (1.99) and the A-ring edge (2.27) land right.
RING_U0_RADIUS = 1.171
RING_U1_RADIUS = 2.309
RING_GAIN = 2.4


def _preference() -> tuple[str, ...]:
    """Resolution order; SOLAR_TEX=2k/4k/8k caps memory use (default: best available),
    SOLAR_TEX=off uses the procedural look."""
    want = os.environ.get("SOLAR_TEX", "8k").lower()
    if want in ("off", "none", "0"):
        return ()
    order = {"8k": ("8k", "4k", "2k"), "4k": ("4k", "2k", "8k"), "2k": ("2k", "4k", "8k")}
    return order.get(want, order["8k"])


def texture_path(stem: str) -> Path | None:
    for res in _preference():
        for ext in (".jpg", ".png", ".tif"):
            p = TEX_DIR / f"{res}_{stem}{ext}"
            if p.exists() and p.stat().st_size > 0:
                return p
    return None


def has_textures(name: str) -> bool:
    return texture_path(MAPS[name]["color"]) is not None


def _image(nodes, path: Path, color: bool, name: str):
    img = bpy.data.images.load(str(path), check_existing=True)
    img.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    node = nodes.new('ShaderNodeTexImage')
    node.name = name
    node.image = img
    node.interpolation = 'Cubic' if color else 'Linear'
    node.extension = 'REPEAT'
    return node


def textured_material(name: str) -> bpy.types.Material | None:
    """Principled-based material from the real maps (so convert_to_sunlit and the
    meridian markers work unchanged), or None when the colour map is missing."""
    maps = {role: texture_path(stem) for role, stem in MAPS[name].items() if role != "ring"}
    if maps.get("color") is None:
        return None
    mat = bpy.data.materials.new(f"Planet_{name.capitalize()}_Tex")
    mat.use_nodes = True
    n, l = mat.node_tree.nodes, mat.node_tree.links
    n.clear()
    out = n.new('ShaderNodeOutputMaterial')
    bsdf = n.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.8
    l.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tc = n.new('ShaderNodeTexCoord')
    uv = tc.outputs['UV']
    if PLANETS[name].rotation_period_days < 0:          # spin axis = IAU south: turn the map over
        flip = n.new('ShaderNodeVectorMath')
        flip.operation = 'SUBTRACT'
        flip.inputs[0].default_value = (1.0, 1.0, 0.0)
        l.new(uv, flip.inputs[1])
        uv = flip.outputs[0]

    color = _image(n, maps["color"], True, "ColorTex")
    l.new(uv, color.inputs['Vector'])
    base = color.outputs['Color']

    cloud_cover = None
    if maps.get("clouds"):
        clouds = _image(n, maps["clouds"], False, "CloudTex")
        l.new(uv, clouds.inputs['Vector'])
        cover = n.new('ShaderNodeMath')                 # thin haze is left out, bright decks stay
        cover.operation = 'POWER'
        cover.inputs[1].default_value = 1.4
        l.new(clouds.outputs['Color'], cover.inputs[0])
        cloud_cover = cover.outputs[0]
        mix = n.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        l.new(cloud_cover, mix.inputs['Factor'])
        l.new(base, mix.inputs[6])
        mix.inputs[7].default_value = (0.96, 0.97, 1.0, 1.0)
        base = mix.outputs[2]
    l.new(base, bsdf.inputs['Base Color'])

    if name in BUMP:                                    # relief from the map's brightness
        bump = n.new('ShaderNodeBump')
        bump.name = "PlanetBump"
        bump.inputs['Strength'].default_value = BUMP[name]
        bump.inputs['Distance'].default_value = 0.02
        l.new(color.outputs['Color'], bump.inputs['Height'])
        l.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    if maps.get("night"):
        night = _image(n, maps["night"], True, "NightTex")
        l.new(uv, night.inputs['Vector'])
        k = n.new('ShaderNodeMix')                      # clouds hide the city lights
        k.name = "NightOut"
        k.data_type = 'RGBA'
        k.blend_type = 'MULTIPLY'
        k.inputs['Factor'].default_value = 1.0
        l.new(night.outputs['Color'], k.inputs[6])
        if cloud_cover is not None:
            keep = n.new('ShaderNodeMath')
            keep.operation = 'MULTIPLY_ADD'             # 1 - 0.85 * cover
            keep.inputs[1].default_value = -0.85
            keep.inputs[2].default_value = 1.0
            l.new(cloud_cover, keep.inputs[0])
            scale = n.new('ShaderNodeMath')
            scale.operation = 'MULTIPLY'
            scale.inputs[1].default_value = NIGHT_STRENGTH
            l.new(keep.outputs[0], scale.inputs[0])
            l.new(scale.outputs[0], k.inputs[7])
        else:
            k.inputs[7].default_value = (NIGHT_STRENGTH,) * 3 + (1.0,)

    if maps.get("spec"):
        spec = _image(n, maps["spec"], False, "SpecTex")
        l.new(uv, spec.inputs['Vector'])
        m = n.new('ShaderNodeMath')
        m.operation = 'MULTIPLY'
        m.inputs[1].default_value = SPEC_STRENGTH
        l.new(spec.outputs['Color'], m.inputs[0])
        if cloud_cover is not None:                     # no glint through clouds
            clear = n.new('ShaderNodeMath')
            clear.operation = 'SUBTRACT'
            clear.inputs[0].default_value = 1.0
            l.new(cloud_cover, clear.inputs[1])
            m2 = n.new('ShaderNodeMath')
            m2.operation = 'MULTIPLY'
            l.new(m.outputs[0], m2.inputs[0])
            l.new(clear.outputs[0], m2.inputs[1])
            m = m2
        m.name = "SpecOut"

    mat["limb_dark"] = LIMB.get(name, 0.0)
    mat["textured"] = True
    return mat


def wire_detail(mat: bpy.types.Material, group_node) -> None:
    """Connect the optional detail of a textured material into a SunLit group node."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bump = nodes.get("PlanetBump")
    if bump is not None:
        links.new(bump.outputs['Normal'], group_node.inputs["Normal"])
        group_node.inputs["UseNormal"].default_value = 1.0
    night = nodes.get("NightOut")
    if night is not None:
        links.new(night.outputs[2], group_node.inputs["Night"])
    spec = nodes.get("SpecOut")
    if spec is not None:
        links.new(spec.outputs[0], group_node.inputs["Spec"])
    group_node.inputs["LimbDark"].default_value = float(mat.get("limb_dark", 0.0))


def ring_material(vis_r: float) -> bpy.types.Material | None:
    """Saturn's rings from the real radial profile (colour + opacity), for a disc
    whose object-space radius is in the same units as `vis_r` (Saturn's radius)."""
    path = texture_path(MAPS["saturn"]["ring"])
    if path is None:
        return None
    mat = bpy.data.materials.new("Saturn_Ring_Tex")
    mat.use_nodes = True
    n, l = mat.node_tree.nodes, mat.node_tree.links
    n.clear()
    tc = n.new('ShaderNodeTexCoord')
    length = n.new('ShaderNodeVectorMath')
    length.operation = 'LENGTH'
    l.new(tc.outputs['Object'], length.inputs[0])
    u = n.new('ShaderNodeMapRange')                     # radius -> texture u (unclamped)
    u.clamp = False
    u.inputs['From Min'].default_value = RING_U0_RADIUS * vis_r
    u.inputs['From Max'].default_value = RING_U1_RADIUS * vis_r
    l.new(length.outputs['Value'], u.inputs['Value'])
    vec = n.new('ShaderNodeCombineXYZ')
    vec.inputs['Y'].default_value = 0.5
    l.new(u.outputs[0], vec.inputs['X'])
    tex = n.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(path), check_existing=True)
    tex.interpolation = 'Linear'
    tex.extension = 'CLIP'                              # outside 0..1: fully transparent
    l.new(vec.outputs[0], tex.inputs['Vector'])
    gain = n.new('ShaderNodeMix')                       # the map's colour is dim; B ring ~ planet albedo
    gain.data_type = 'RGBA'
    gain.blend_type = 'MULTIPLY'
    gain.clamp_result = True
    gain.inputs['Factor'].default_value = 1.0
    l.new(tex.outputs['Color'], gain.inputs[6])
    gain.inputs[7].default_value = (RING_GAIN, RING_GAIN, RING_GAIN, 1.0)
    bsdf = n.new('ShaderNodeBsdfPrincipled')
    l.new(gain.outputs[2], bsdf.inputs['Base Color'])
    l.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    out = n.new('ShaderNodeOutputMaterial')
    l.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    return mat


def shape(body, name: str) -> None:
    """Real oblateness: squash along the spin axis (the body's local Z)."""
    body.scale = (1.0, 1.0, 1.0 - FLATTENING.get(name, 0.0))


def meridian_offset_deg(name: str, basis) -> float:
    """Spin angle (about local Z) that puts the map's longitude 0 on the IAU prime
    meridian at J2000, for a body whose parent frame has rotation `basis` (columns =
    local X, Y, Z in the same ecliptic frame the planet positions use)."""
    m = prime_meridian(name, 0.0)
    x = sum(basis[i][0] * m[i] for i in range(3))
    y = sum(basis[i][1] * m[i] for i in range(3))
    return math.degrees(math.atan2(y, x))
