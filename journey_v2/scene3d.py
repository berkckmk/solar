"""3D pass (Blender): stars, Sun, planets. No text or line art: those live in
the 2D layer so a wording change never forces a 3D re-render.

Camera and sizes come from journey_v2.timeline / camera, the same code the 2D
layer uses, so both passes line up to the pixel.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from science.planet_data import PLANETS, PLANET_ORDER
from science.attitude import spin_axis, orbit_normal
from blender_build import clear_scene, setup_render_settings, build_planet_material, create_saturn_rings
from planet_look import shape as planet_shape, meridian_offset_deg
from render_system_journey import (
    sunlit_group, convert_to_sunlit, MAP_SCALE, RIM, axis_basis,
)

from . import camera as C
from .timeline import FPS, pos

MAX_SPIN_DEG_PER_FRAME = 35.0
INSET_LENS_MM = 85.0          # close-up: long lens, little perspective distortion
INSET_FILL = 0.80             # planet (or ring) diameter / window diameter
INSET_SAMPLES = 64


def _new_mat(name: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat, mat.node_tree.nodes, mat.node_tree.links


def setup_stars(width_px: int):
    """Sparse, dim, round stars (about 1.3 px) so they sit behind the story and
    do not shimmer when the camera moves."""
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    n, l = world.node_tree.nodes, world.node_tree.links
    n.clear()
    scale = 120.0
    pixel_angle = 2.0 * math.atan(0.5 * C.SENSOR_MM / C.LENS_MM) / width_px
    d0 = 1.3 * pixel_angle * scale

    tc = n.new('ShaderNodeTexCoord')
    vor = n.new('ShaderNodeTexVoronoi')
    vor.voronoi_dimensions = '3D'
    vor.feature = 'F1'
    vor.inputs['Scale'].default_value = scale
    l.new(tc.outputs['Generated'], vor.inputs['Vector'])

    core = n.new('ShaderNodeMapRange')               # 1 at the feature point, 0 beyond d0
    core.interpolation_type = 'SMOOTHSTEP'
    core.inputs['From Min'].default_value = d0
    core.inputs['From Max'].default_value = 0.0
    l.new(vor.outputs['Distance'], core.inputs['Value'])

    sep = n.new('ShaderNodeSeparateColor')
    l.new(vor.outputs['Color'], sep.inputs['Color'])
    keep = n.new('ShaderNodeMath')                   # ~9 % of cells hold a star
    keep.operation = 'LESS_THAN'
    keep.inputs[1].default_value = 0.09
    l.new(sep.outputs[0], keep.inputs[0])
    bright = n.new('ShaderNodeMath')                 # mostly faint, a few brighter
    bright.operation = 'POWER'
    bright.inputs[1].default_value = 3.0
    l.new(sep.outputs[1], bright.inputs[0])

    m1 = n.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'
    l.new(core.outputs[0], m1.inputs[0]); l.new(keep.outputs[0], m1.inputs[1])
    m2 = n.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'
    l.new(m1.outputs[0], m2.inputs[0]); l.new(bright.outputs[0], m2.inputs[1])
    gain = n.new('ShaderNodeMath'); gain.operation = 'MULTIPLY_ADD'
    gain.inputs[1].default_value = 0.75
    gain.inputs[2].default_value = 0.0
    l.new(m2.outputs[0], gain.inputs[0])

    tint = n.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    tint.inputs[6].default_value = (0.78, 0.85, 1.0, 1.0)
    tint.inputs[7].default_value = (1.0, 0.92, 0.80, 1.0)
    l.new(sep.outputs[2], tint.inputs['Factor'])
    bg = n.new('ShaderNodeBackground')
    l.new(tint.outputs[2], bg.inputs['Color'])
    l.new(gain.outputs[0], bg.inputs['Strength'])
    out = n.new('ShaderNodeOutputWorld')
    l.new(bg.outputs[0], out.inputs['Surface'])


def build_sun():
    """Sun disc with gentle limb darkening + a soft additive halo billboard."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0)
    sun = bpy.context.active_object
    sun.name = "Sun"
    bpy.ops.object.shade_smooth()
    mat, n, l = _new_mat("SunDisc")
    lw = n.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    ramp = n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (1.0, 0.95, 0.82, 1.0)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (1.0, 0.62, 0.25, 1.0)
    l.new(lw.outputs['Facing'], ramp.inputs['Fac'])
    em = n.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 1.25
    l.new(ramp.outputs['Color'], em.inputs['Color'])
    out = n.new('ShaderNodeOutputMaterial')
    l.new(em.outputs[0], out.inputs['Surface'])
    sun.data.materials.append(mat)

    bpy.ops.mesh.primitive_plane_add(size=2.0)
    halo = bpy.context.active_object
    halo.name = "SunHalo"
    mat, n, l = _new_mat("SunHalo")
    tc = n.new('ShaderNodeTexCoord')
    length = n.new('ShaderNodeVectorMath')
    length.operation = 'LENGTH'
    l.new(tc.outputs['Object'], length.inputs[0])
    fall = n.new('ShaderNodeMapRange')               # 1 at the disc edge (1/3), 0 at the rim
    fall.clamp = True
    fall.inputs['From Min'].default_value = 1.0
    fall.inputs['From Max'].default_value = 1.0 / 3.0
    l.new(length.outputs['Value'], fall.inputs['Value'])
    soft = n.new('ShaderNodeMath')
    soft.operation = 'POWER'
    soft.inputs[1].default_value = 2.6
    l.new(fall.outputs[0], soft.inputs[0])
    strength = n.new('ShaderNodeMath')
    strength.operation = 'MULTIPLY'
    strength.inputs[1].default_value = 0.55
    l.new(soft.outputs[0], strength.inputs[0])
    em = n.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.78, 0.45, 1.0)
    l.new(strength.outputs[0], em.inputs['Strength'])
    tr = n.new('ShaderNodeBsdfTransparent')
    add = n.new('ShaderNodeAddShader')
    l.new(em.outputs[0], add.inputs[0])
    l.new(tr.outputs[0], add.inputs[1])
    out = n.new('ShaderNodeOutputMaterial')
    l.new(add.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    halo.data.materials.append(mat)
    return sun, halo


def build_planets():
    rigs = {}
    for name in PLANET_ORDER:
        frame = bpy.data.objects.new(f"Frame_{name}", None)
        bpy.context.collection.objects.link(frame)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0)
        body = bpy.context.active_object
        body.name = f"Body_{name}"
        bpy.ops.object.shade_smooth()
        body.parent = frame
        planet_shape(body, name)
        mat = build_planet_material(name)
        for node in mat.node_tree.nodes:
            if node.type == 'MAPPING':
                node.inputs['Scale'].default_value = (MAP_SCALE[name],) * 3
        convert_to_sunlit(mat, ambient=0.06, rim=RIM[name])
        body.data.materials.append(mat)
        if name == "saturn":
            ring = create_saturn_rings(body, 1.0)
            ring.parent = frame
            ring.location = (0.0, 0.0, 0.0)
            ring.rotation_euler = (0.0, 0.0, 0.0)
            convert_to_sunlit(ring.active_material, ambient=0.2, two_sided=True, strength=1.0)
        basis = axis_basis(spin_axis(name), orbit_normal(name))
        rigs[name] = {"frame": frame, "body": body, "parts": [body] + ([ring] if name == "saturn" else []),
                      "basis": basis, "m0": meridian_offset_deg(name, basis)}
    return rigs


class Scene3D:
    def __init__(self, sample, res: tuple[int, int], samples: int):
        self.sample, self.res = sample, res
        clear_scene()
        setup_render_settings(res, samples)
        sc = bpy.context.scene
        sc.view_settings.view_transform = 'Standard'
        sc.view_settings.look = 'None'
        for g in sunlit_group().nodes:             # Sun sits at the world origin here
            if g.name == "SunPos":
                g.inputs[0].default_value = g.inputs[1].default_value = g.inputs[2].default_value = 0.0
        setup_stars(res[0])
        cam_data = bpy.data.cameras.new("V2Cam")
        cam_data.lens = C.LENS_MM
        cam_data.sensor_fit = 'HORIZONTAL'
        cam_data.sensor_width = C.SENSOR_MM
        self.cam = bpy.data.objects.new("V2Cam", cam_data)
        bpy.context.collection.objects.link(self.cam)
        sc.camera = self.cam
        self.sun, self.halo = build_sun()
        self.rigs = build_planets()
        inset_data = bpy.data.cameras.new("InsetCam")
        inset_data.lens = INSET_LENS_MM
        inset_data.sensor_fit = 'HORIZONTAL'
        inset_data.sensor_width = C.SENSOR_MM
        self.inset_cam = bpy.data.objects.new("InsetCam", inset_data)
        bpy.context.collection.objects.link(self.inset_cam)
        for name, rig in self.rigs.items():        # planets outside the segment stay out of frame
            for obj in rig["parts"]:
                obj.hide_render = name not in sample.shown
        self.spin = self._visual_spin()

    def _visual_spin(self):
        """Drawn spin per frame, rate-limited so fast rotators never strobe."""
        s = self.sample
        table = {n: [0.0] * (s.frames + 1) for n in PLANET_ORDER}
        prev = s.days_at(0.0)
        acc = {n: 0.0 for n in PLANET_ORDER}
        for f in range(s.frames + 1):
            d = s.days_at(f / FPS)
            for n in PLANET_ORDER:
                step = 360.0 * (d - prev) / abs(PLANETS[n].rotation_period_days)
                acc[n] += max(-MAX_SPIN_DEG_PER_FRAME, min(MAX_SPIN_DEG_PER_FRAME, step))
                table[n][f] = acc[n]
            prev = d
        return table

    def update(self, f: int):
        s = self.sample
        t = f / FPS
        days = s.days_at(t)
        pose = s.pose(t)
        cd = self.cam.data
        cd.shift_x, cd.shift_y = pose.shift_x, pose.shift_y
        cd.clip_start = pose.dist * 0.01
        cd.clip_end = pose.dist * 20.0 + 50.0
        rot = Matrix(pose.matrix_rows()).to_4x4()
        self.cam.matrix_world = Matrix.Translation(pose.location) @ rot

        aspect = self.res[0] / self.res[1]

        def world_radius(px_frac, p):
            pr = C.project(pose, p)
            depth = pr[2] if pr else pose.dist
            return px_frac * depth / (C.K * aspect)

        r_sun = world_radius(s.sun_px(pose), (0.0, 0.0, 0.0))
        self.sun.matrix_world = Matrix.Scale(r_sun, 4)
        self.halo.matrix_world = rot @ Matrix.Scale(3.0 * r_sun, 4)

        for name, rig in self.rigs.items():
            p = pos(name, days)
            r = world_radius(s.planet_px(name, t), p)
            rig["frame"].matrix_world = Matrix.Translation(p) @ rig["basis"] @ Matrix.Scale(r, 4)
            spin = self.spin[name][min(f, s.frames)] + rig["m0"]
            rig["body"].rotation_euler = (0.0, 0.0, math.radians(spin % 360.0))

    def render_inset(self, f: int, path: str, px: int):
        """Close-up of the selected planet for the 2D layer's round window: same
        viewing direction as the main camera (so the lit phase matches), the
        planet's real axis, spin and lighting, transparent background."""
        s = self.sample
        rig = self.rigs[s.planet]
        centre = rig["frame"].matrix_world.translation.copy()
        extent = rig["frame"].matrix_world.to_scale()[0] * (2.35 if s.planet == "saturn" else 1.0)
        pose = s.pose(f / FPS)
        tan_half = 0.5 * C.SENSOR_MM / INSET_LENS_MM
        dist = extent / (INSET_FILL * tan_half)
        rot = Matrix(pose.matrix_rows()).to_4x4()
        back = Vector(pose.back)
        self.inset_cam.matrix_world = Matrix.Translation(centre + back * dist) @ rot
        self.inset_cam.data.clip_start = dist * 0.05
        self.inset_cam.data.clip_end = dist * 3.0

        sc = bpy.context.scene
        keep = (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.film_transparent)
        samples = (sc.cycles.samples, sc.eevee.taa_render_samples)
        hidden = [self.sun, self.halo] + [o for n, r in self.rigs.items() if n != s.planet for o in r["parts"]]
        was = [o.hide_render for o in hidden]
        try:
            for o in hidden:
                o.hide_render = True
            sc.camera = self.inset_cam
            sc.render.resolution_x = sc.render.resolution_y = px
            sc.render.film_transparent = True
            sc.cycles.samples = max(samples[0], INSET_SAMPLES)       # small image: clean it up cheaply
            sc.eevee.taa_render_samples = max(samples[1], INSET_SAMPLES)
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
        finally:
            for o, h in zip(hidden, was):
                o.hide_render = h
            sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.film_transparent = keep
            sc.cycles.samples, sc.eevee.taa_render_samples = samples

