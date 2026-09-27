"""Render a continuous 20-second 1-Day Earth 24-hour diurnal & orbital loop in Blender.

Duration: 20.0 seconds (600 frames @ 30 FPS)
Time scale: 0.0 to 1.0 Earth Day (24.0 hours)
Visuals:
- Earth completes exactly 1 full 360-degree axial rotation (seamless 24h diurnal loop)
- Earth travels its true Keplerian 1-day orbital arc (2.57M km)
- Dynamic growing orbital trail emerges behind Earth
- Inner planets (Mercury, Venus, Mars) orbit concurrently according to Kepler's laws
- Real-time animated documentary HUD with 24-hour clock & live kilometer counter
- 16:9 Landscape (Yatay) 1440p / 1080p
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import bpy
    import mathutils
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False
    print("This script must run inside Blender Python.")
    sys.exit(1)

PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent.parent
OUTPUT_DIR = ROOT_DIR / "output" / "solar_system_time_journey"
FRAMES_DIR = OUTPUT_DIR / "day1_loop_frames"
FINAL_DIR = OUTPUT_DIR / "final"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from science.planet_data import PLANETS, PLANET_ORDER, TRAIL_COLORS
from science.kepler import heliocentric_position
from science.coordinates import ecliptic_km_to_blender, planet_visual_radius
from blender_build import (
    clear_scene, setup_render_settings, setup_world_starfield,
    create_sun, build_planet_material
)

TOTAL_FRAMES = 600  # 20 seconds @ 30 FPS
RESOLUTION = (1920, 1080)
SAMPLES = 16
FPS = 30


def build_animated_1day_scene(f0: int = 1, f1: int = TOTAL_FRAMES, still: int | None = None):
    """Build the single scene with keyframed animation and render specified frames."""
    clear_scene()
    setup_render_settings(RESOLUTION, SAMPLES)
    setup_world_starfield()

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = TOTAL_FRAMES
    scene.render.fps = FPS

    # 1. Sun at center
    create_sun()

    # 2. Celestial bodies
    earth_data = PLANETS["earth"]
    earth_vis_r = planet_visual_radius(earth_data.mean_radius_km)

    # Earth Object
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=earth_vis_r, location=(0, 0, 0))
    earth_obj = bpy.context.active_object
    earth_obj.name = "Earth_Hero"
    bpy.ops.object.shade_smooth()
    earth_mat = build_planet_material("earth")
    earth_obj.data.materials.append(earth_mat)

    # Axial tilt 23.44 degrees
    tilt_rad = math.radians(23.44)

    # Sun Light source
    bpy.ops.object.light_add(type='POINT', radius=0.08, location=(0, 0, 0))
    sun_light = bpy.context.active_object
    sun_light.name = "Central_Sun_Light"
    sun_light.data.energy = 500.0
    sun_light.data.color = (1.0, 0.96, 0.90)

    # Other planets for context in background (Mercury, Venus, Mars)
    other_objs = {}
    for name in ("mercury", "venus", "mars"):
        p = PLANETS[name]
        vis_r = planet_visual_radius(p.mean_radius_km)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, radius=vis_r, location=(0, 0, 0))
        o = bpy.context.active_object
        o.name = f"Bg_{name.capitalize()}"
        bpy.ops.object.shade_smooth()
        o.data.materials.append(build_planet_material(name))
        other_objs[name] = o

    # Camera setup
    cam_data = bpy.data.cameras.new("LoopCamera")
    cam_data.clip_start = 0.01
    cam_data.clip_end = 200.0
    cam_data.lens = 45
    cam_obj = bpy.data.objects.new("LoopCamera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Key light on Earth
    bpy.ops.object.light_add(type='POINT', radius=earth_vis_r * 0.6, location=(0, 0, 0))
    key_light = bpy.context.active_object
    key_light.name = "Earth_Key_Light"
    key_light.data.energy = 60.0
    key_light.data.color = (1.0, 0.98, 0.95)

    # Fill light
    bpy.ops.object.light_add(type='POINT', radius=earth_vis_r * 1.2, location=(0, 0, 0))
    fill_light = bpy.context.active_object
    fill_light.name = "Earth_Fill_Light"
    fill_light.data.energy = 10.0
    fill_light.data.color = (0.6, 0.75, 1.0)

    # Screen-space HUD text objects parented to camera
    def make_hud_text(name: str, pos: tuple, size: float, color: tuple):
        bpy.ops.object.text_add(location=(0, 0, 0))
        t = bpy.context.active_object
        t.name = name
        t.parent = cam_obj
        t.location = pos
        t.rotation_euler = (0, 0, 0)
        t.data.size = size
        t.data.align_x = 'LEFT'
        t.data.align_y = 'TOP'

        mat = bpy.data.materials.new(f"Mat_{name}")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        em = nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = color
        em.inputs['Strength'].default_value = 2.4
        out = nodes.new('ShaderNodeOutputMaterial')
        links.new(em.outputs['Emission'], out.inputs['Surface'])
        t.data.materials.append(mat)
        return t

    base_x = -0.27
    base_y = 0.16
    z_dist = -1.0
    hud_title = make_hud_text("HUD_Title", (base_x, base_y, z_dist), 0.011, (0.0, 0.90, 1.0, 1.0))
    hud_title.data.body = "1 EARTH DAY • 24-HOUR DIURNAL & ORBITAL CYCLE"

    hud_planet = make_hud_text("HUD_Planet", (base_x, base_y - 0.020, z_dist), 0.020, (1.0, 1.0, 1.0, 1.0))
    hud_planet.data.body = "EARTH"

    hud_clock = make_hud_text("HUD_Clock", (base_x, base_y - 0.065, z_dist), 0.013, (1.0, 0.85, 0.3, 1.0))
    hud_dist = make_hud_text("HUD_Dist", (base_x, base_y - 0.088, z_dist), 0.012, (0.90, 0.93, 0.96, 1.0))
    hud_rot = make_hud_text("HUD_Rot", (base_x, base_y - 0.110, z_dist), 0.012, (0.75, 0.80, 0.85, 1.0))
    hud_speed = make_hud_text("HUD_Speed", (base_x, base_y - 0.132, z_dist), 0.012, (0.60, 0.65, 0.70, 1.0))
    hud_speed.data.body = "ORBITAL SPEED   29.8 km/s"

    # Faint Earth orbit guide
    n_guide = 300
    guide_pts = []
    for i in range(n_guide + 1):
        st = heliocentric_position(earth_data, earth_data.orbital_period_days * (i / n_guide))
        gx, gy, gz = ecliptic_km_to_blender(st.x, st.y, st.z)
        guide_pts.append((gx, gy, gz))

    c_guide = bpy.data.curves.new("Earth_Guide_Curve", type='CURVE')
    c_guide.dimensions = '3D'
    c_guide.bevel_depth = 0.0003
    sp_g = c_guide.splines.new('POLY')
    sp_g.points.add(len(guide_pts) - 1)
    for i, (gx, gy, gz) in enumerate(guide_pts):
        sp_g.points[i].co = (gx, gy, gz, 1.0)
    g_obj = bpy.data.objects.new("Earth_Guide_Obj", c_guide)
    bpy.context.collection.objects.link(g_obj)

    g_mat = bpy.data.materials.new("Earth_Guide_Mat")
    g_mat.use_nodes = True
    g_nodes = g_mat.node_tree.nodes
    g_nodes.clear()
    g_em = g_nodes.new('ShaderNodeEmission')
    g_em.inputs['Color'].default_value = (0.2, 0.6, 0.9, 1.0)
    g_em.inputs['Strength'].default_value = 0.25
    g_out = g_nodes.new('ShaderNodeOutputMaterial')
    g_mat.node_tree.links.new(g_em.outputs['Emission'], g_out.inputs['Surface'])
    g_obj.data.materials.append(g_mat)

    # Dynamic trail curve object
    trail_curve = bpy.data.curves.new("Dynamic_Trail_Curve", type='CURVE')
    trail_curve.dimensions = '3D'
    trail_curve.bevel_depth = 0.0004
    trail_spline = trail_curve.splines.new('POLY')
    # Pre-allocate 120 points
    trail_spline.points.add(119)
    trail_obj = bpy.data.objects.new("Dynamic_Trail_Obj", trail_curve)
    bpy.context.collection.objects.link(trail_obj)

    t_mat = bpy.data.materials.new("Dynamic_Trail_Mat")
    t_mat.use_nodes = True
    t_nodes = t_mat.node_tree.nodes
    t_nodes.clear()
    t_em = t_nodes.new('ShaderNodeEmission')
    t_em.inputs['Color'].default_value = (*TRAIL_COLORS["earth"], 1.0)
    t_em.inputs['Strength'].default_value = 3.5
    t_out = t_nodes.new('ShaderNodeOutputMaterial')
    t_mat.node_tree.links.new(t_em.outputs['Emission'], t_out.inputs['Surface'])
    trail_obj.data.materials.append(t_mat)

    dist = earth_vis_r * 7.5

    def update_frame(f: int):
        t_day = (f - 1) / (TOTAL_FRAMES - 1) if TOTAL_FRAMES > 1 else 0.0
        sim_hours = t_day * 24.0

        # Earth position
        st_e = heliocentric_position(earth_data, t_day)
        ex, ey, ez = ecliptic_km_to_blender(st_e.x, st_e.y, st_e.z)
        earth_obj.location = (ex, ey, ez)

        # Earth 360-degree axial rotation (diurnal cycle)
        earth_rot_z = t_day * 2.0 * math.pi
        earth_obj.rotation_euler = (tilt_rad, 0.0, earth_rot_z)

        # Other planets
        for name, o in other_objs.items():
            p_data = PLANETS[name]
            st_p = heliocentric_position(p_data, t_day)
            px, py, pz = ecliptic_km_to_blender(st_p.x, st_p.y, st_p.z)
            o.location = (px, py, pz)

        # Camera tracking with cinematic subtle drift
        e_vec = mathutils.Vector((ex, ey, ez))
        u_r = e_vec.normalized()
        u_tangent = mathutils.Vector((-u_r.y, u_r.x, 0)).normalized()
        u_up = mathutils.Vector((0, 0, 1))

        # Gentle parallax curve
        drift_angle = (f / TOTAL_FRAMES) * math.pi * 0.4
        cam_pos = e_vec - u_tangent * (dist * 1.1 + math.sin(drift_angle) * 0.01) + u_r * (dist * 0.7) + u_up * (dist * 0.45)
        cam_obj.location = cam_pos

        look_target = e_vec - u_tangent * (dist * 0.25)
        direction = look_target - cam_pos
        cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

        # Update lights
        key_light.location = (ex - u_r.x * dist * 1.2, ey - u_r.y * dist * 1.2, ez + dist * 0.6)
        fill_light.location = (cam_pos.x, cam_pos.y, cam_pos.z + dist * 0.5)

        # Update HUD texts
        hh = int(sim_hours)
        mm = int((sim_hours - hh) * 60)
        ss = int((((sim_hours - hh) * 60) - mm) * 60)
        hud_clock.data.body = f"TIME ELAPSED    {hh:02d}:{mm:02d}:{ss:02d} / 24:00:00"

        cur_km = t_day * 2570000.0
        hud_dist.data.body = f"ORBITAL DIST    {cur_km:,.0f} km".replace(",", " ")

        cur_deg = t_day * 360.0
        hud_rot.data.body = f"AXIAL ROTATION  {cur_deg:5.1f}° / 360.0°"

        # Update dynamic trail
        n_pts = len(trail_spline.points)
        for i in range(n_pts):
            sample_t = t_day * (i / (n_pts - 1)) if t_day > 0 else 0.0
            st_tr = heliocentric_position(earth_data, sample_t)
            tx, ty, tz = ecliptic_km_to_blender(st_tr.x, st_tr.y, st_tr.z)
            trail_spline.points[i].co = (tx, ty, tz, 1.0)

        return hh, mm, ss, cur_km

    if still is not None:
        hh, mm, ss, cur_km = update_frame(still)
        out = OUTPUT_DIR / f"solar_1_day_earth_loop_still_{still:04d}.png"
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        print(f"Still rendered: {out}")
        return

    print(f"\nStarting animation render ({f0} to {f1} of {TOTAL_FRAMES} frames)...")
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    for f in range(f0, f1 + 1):
        frame_file = FRAMES_DIR / f"frame_{f:06d}.png"
        if frame_file.exists() and frame_file.stat().st_size > 0:
            continue

        hh, mm, ss, cur_km = update_frame(f)

        # Render frame
        scene.render.filepath = str(frame_file)
        bpy.ops.render.render(write_still=True)

        if f % 30 == 0 or f == 1:
            print(f"  Frame {f:3d}/600 ({f/600*100:5.1f}%) | Time: {hh:02d}:{mm:02d}:{ss:02d} | Dist: {cur_km:,.0f} km")

    existing_count = len(list(FRAMES_DIR.glob("frame_*.png")))
    if existing_count < TOTAL_FRAMES:
        print(f"Partial range rendered ({existing_count}/{TOTAL_FRAMES} frames); skipping final MP4 encode.")
        return

    print("\n✅ All 600 frames rendered!")

    # FFmpeg assembly
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    master_mp4 = FINAL_DIR / "solar_1_day_earth_24h_loop_20s.mp4"
    audio_wav = PROJECT_DIR / "assets" / "audio" / "deep_space_ambience.wav"

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(FRAMES_DIR / "frame_%06d.png"),
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
        "-t", "20.0",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(master_mp4),
    ])

    print(f"\nEncoding 20s 1-Day Loop Video: {master_mp4}")
    subprocess.run(cmd, check=True)
    print(f"✅ Master 20s 1-Day Loop Video Complete: {master_mp4}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Render 1-Day Earth 24h diurnal & orbital loop")
    parser.add_argument("--frames", nargs=2, type=int, help="Start and end frame range (1-indexed)")
    parser.add_argument("--still", type=int, help="Render a single frame still")
    args = parser.parse_args(argv)

    f0, f1 = args.frames if args.frames else (1, TOTAL_FRAMES)
    build_animated_1day_scene(f0=f0, f1=f1, still=args.still)


if __name__ == "__main__":
    main()
