# auralia_gyro_anim.py
# Blender Python script (tested for Blender 3.x+)
# Creates animated 3D logo with gyroscope-style orbiting neon rings
#
# Usage:
#   blender --background --factory-startup --python auralia_gyro_anim.py
#
# Output:
#   - MP4 video animation (5 seconds @ 60fps)
#   - GLB file for web/Three.js integration

import math
import os

import bpy
from mathutils import Euler

# ---------- USER PATHS (edit if needed) ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "dashboard")

INPUT_IMAGE_PATH = os.path.join(DASHBOARD_DIR, "AuraIA New Logo (1).jpg")
OUTPUT_VIDEO_PATH = os.path.join(DASHBOARD_DIR, "assets", "auralia_orbit.mp4")
OUTPUT_GLB_PATH = os.path.join(DASHBOARD_DIR, "assets", "auralia_scene.glb")

# Ensure output directory exists
os.makedirs(os.path.dirname(OUTPUT_VIDEO_PATH), exist_ok=True)

# ---------- ANIMATION / RENDER SETTINGS ----------
FPS = 60
DURATION_SECONDS = 5
FRAME_START = 1
FRAME_END = FRAME_START + DURATION_SECONDS * FPS - 1

bpy.context.scene.render.engine = "BLENDER_EEVEE"  # fast + bloom
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start = FRAME_START
scene.frame_end = FRAME_END

# EEVEE settings
scene.eevee.taa_render_samples = 64
scene.eevee.use_bloom = True
scene.eevee.bloom_threshold = 0.1
scene.eevee.bloom_knee = 0.5
scene.eevee.bloom_radius = 8.0
scene.eevee.bloom_intensity = 0.35

# Use FFmpeg + H.264 for MP4
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "HIGH"
scene.render.ffmpeg.ffmpeg_preset = "GOOD"
scene.render.ffmpeg.gopsize = FPS * 2
scene.render.filepath = OUTPUT_VIDEO_PATH
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100


# ---------- Utility: clear existing scene ----------
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # Remove orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


clear_scene()


# ---------- Load image (robust) ----------
def load_image(path):
    # Try with given path, then try adding common extensions
    candidates = [path, path + ".png", path + ".jpg", path + ".jpeg"]
    for p in candidates:
        if os.path.exists(p):
            print(f"Loading image from: {p}")
            return bpy.data.images.load(p)
    raise FileNotFoundError(f"Input image not found. Tried: {candidates}")


try:
    logo_img = load_image(INPUT_IMAGE_PATH)
except Exception as e:
    print("ERROR:", e)
    raise SystemExit(1)


# ---------- Create sphere with logo texture ----------
bpy.ops.mesh.primitive_uv_sphere_add(
    segments=64, ring_count=32, radius=1.0, location=(0, 0, 0)
)
sphere = bpy.context.active_object
sphere.name = "LogoSphere"

# Subsurf for smoothness
sub = sphere.modifiers.new("subd", type="SUBSURF")
sub.levels = 2
sub.render_levels = 2

# UV unwrap
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.uv.smart_project(angle_limit=66.0)
bpy.ops.object.mode_set(mode="OBJECT")

# Material using image (base color) + slight bump from luminance
mat_sphere = bpy.data.materials.new("LogoMat")
mat_sphere.use_nodes = True
nodes = mat_sphere.node_tree.nodes
links = mat_sphere.node_tree.links
nodes.clear()

# Nodes
node_tex = nodes.new(type="ShaderNodeTexImage")
node_tex.image = logo_img
node_tex.interpolation = "Smart"
node_tex.location = (-400, 200)

node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
node_bsdf.location = (0, 200)
node_bsdf.inputs["Specular"].default_value = 0.2
node_bsdf.inputs["Roughness"].default_value = 0.25

node_bump = nodes.new(type="ShaderNodeBump")
node_bump.location = (-200, 0)
node_bump.inputs["Strength"].default_value = 0.15
node_bump.inputs["Distance"].default_value = 0.1

node_out = nodes.new(type="ShaderNodeOutputMaterial")
node_out.location = (200, 200)

# Links
links.new(node_tex.outputs["Color"], node_bsdf.inputs["Base Color"])
links.new(node_tex.outputs["Color"], node_bump.inputs["Height"])
links.new(node_bump.outputs["Normal"], node_bsdf.inputs["Normal"])
links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])

sphere.data.materials.append(mat_sphere)


# ---------- Create neon ring material ----------
def create_ring_material(name="RingEmissive", color=(0.07, 0.85, 1.0, 1.0)):
    """Create a glowing neon ring material."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Emission + transparent mix so edges glow but center can fade
    node_em = nodes.new(type="ShaderNodeEmission")
    node_em.location = (0, 0)
    node_em.inputs["Strength"].default_value = 8.0

    node_col = nodes.new(type="ShaderNodeRGB")
    node_col.location = (-200, 0)
    node_col.outputs["Color"].default_value = color  # cyan-ish

    # Fresnel to make edges brighter
    node_fres = nodes.new(type="ShaderNodeFresnel")
    node_fres.location = (-200, -200)

    node_mix = nodes.new(type="ShaderNodeMixShader")
    node_mix.location = (200, 0)

    node_trans = nodes.new(type="ShaderNodeBsdfTransparent")
    node_trans.location = (0, -200)

    node_out = nodes.new(type="ShaderNodeOutputMaterial")
    node_out.location = (400, 0)

    links.new(node_col.outputs["Color"], node_em.inputs["Color"])
    links.new(node_em.outputs["Emission"], node_mix.inputs[2])
    links.new(node_trans.outputs["BSDF"], node_mix.inputs[1])
    links.new(node_fres.outputs["Fac"], node_mix.inputs["Fac"])
    links.new(node_mix.outputs["Shader"], node_out.inputs["Surface"])

    # Make it blend additively in viewport/render: enable blend mode for EEVEE
    mat.blend_method = "BLEND"
    mat.shadow_method = "NONE"
    return mat


# Create materials with different colors for variety
ring_colors = [
    (0.07, 0.85, 1.0, 1.0),  # Cyan (primary Aura color)
    (0.54, 0.17, 0.89, 1.0),  # Purple (accent)
    (0.0, 1.0, 1.0, 1.0),  # Bright cyan
    (0.58, 0.0, 0.83, 1.0),  # Violet
]

ring_materials = [
    create_ring_material(f"RingMat{i}", ring_colors[i])
    for i in range(len(ring_colors))
]


# ---------- Create multiple ring curves (beveled) and animate ----------
ring_count = 4
base_radius = 1.3
ring_objs = []
empty_objs = []

for i in range(ring_count):
    angle_offset = i * (math.pi * 2 / ring_count)

    # Create a curve circle
    curve_data = bpy.data.curves.new(f"RingCurve{i}", type="CURVE")
    curve_data.dimensions = "3D"
    spline = curve_data.splines.new("NURBS")
    spline.points.add(7)

    # Create an oval-like ring points
    for idx in range(8):
        theta = idx * (2 * math.pi / 8)
        x = base_radius * math.cos(theta)
        y = base_radius * math.sin(theta)
        z = 0.0
        spline.points[idx].co = (x, y, z, 1)
    spline.order_u = 4
    spline.use_cyclic_u = True

    curve_obj = bpy.data.objects.new(f"RingCurveObj{i}", curve_data)
    bpy.context.collection.objects.link(curve_obj)

    # Give it a bevel for thickness
    curve_data.bevel_depth = 0.015 + 0.004 * i  # slight variety
    curve_data.bevel_resolution = 6

    # Rotate initial tilt
    tilt_x = math.radians(10 + i * 8)  # slight tilt per ring
    tilt_y = math.radians((-1) ** i * (5 + i * 6))
    curve_obj.rotation_euler = (tilt_x, tilt_y, angle_offset)

    # Assign emission material (cycle through colors)
    if curve_obj.data.materials:
        curve_obj.data.materials[0] = ring_materials[i % len(ring_materials)]
    else:
        curve_obj.data.materials.append(
            ring_materials[i % len(ring_materials)]
        )

    ring_objs.append(curve_obj)

    # Create an empty at origin to be the orbital pivot for this ring
    empty = bpy.data.objects.new(f"RingPivot{i}", None)
    bpy.context.collection.objects.link(empty)
    empty.location = (0, 0, 0)

    # Parent the ring to its empty (so rotating the empty orbits the ring)
    curve_obj.parent = empty
    empty_objs.append(empty)


# ---------- Animation: orbit each empty (different speeds), and slowly tilt the ring locally ----------
def animate_orbits():
    """Animate the ring orbits and wobbles."""
    for i, empty in enumerate(empty_objs):
        # Different speeds: full rotations over duration (some do multiple spins)
        rotations = 1.0 + 0.5 * i  # 1, 1.5, 2.0, 2.5
        end_rot = rotations * 2 * math.pi
        empty.rotation_mode = "XYZ"
        empty.rotation_euler = (0, 0, 0)
        empty.keyframe_insert(data_path="rotation_euler", frame=FRAME_START)
        empty.rotation_euler[2] = end_rot
        empty.keyframe_insert(data_path="rotation_euler", frame=FRAME_END)

        # Make fcurve cyclic so loop is seamless
        if empty.animation_data and empty.animation_data.action:
            for fc in empty.animation_data.action.fcurves:
                for m in list(fc.modifiers):
                    fc.modifiers.remove(m)
                fc.modifiers.new(type="CYCLES")

    # Slight local oscillation on each ring to give gyroscope wobble
    for j, ring in enumerate(ring_objs):
        ring.rotation_mode = "XYZ"
        initial_rot = list(ring.rotation_euler)

        # Keyframe at start
        ring.keyframe_insert(data_path="rotation_euler", frame=FRAME_START)

        # Small wobble mid
        wobble_angle = math.radians(6 + j * 3)
        mid_frame = FRAME_START + (FRAME_END - FRAME_START) // 2
        ring.rotation_euler[0] = initial_rot[0] + wobble_angle
        ring.keyframe_insert(data_path="rotation_euler", frame=mid_frame)

        # Restore at end
        ring.rotation_euler[0] = initial_rot[0]
        ring.keyframe_insert(data_path="rotation_euler", frame=FRAME_END)

        # Add cyclic modifier for continuity
        if ring.animation_data and ring.animation_data.action:
            for fc in ring.animation_data.action.fcurves:
                fc.modifiers.new(type="CYCLES")


animate_orbits()


# ---------- Camera setup & animation ----------
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam
cam.location = (0, -4.0, 0.8)
cam.rotation_euler = Euler((math.radians(75), 0, 0), "XYZ")

# Camera slow orbit (subtle) around Z with slight dolly
cam_empty = bpy.data.objects.new("CamPivot", None)
bpy.context.collection.objects.link(cam_empty)
cam.parent = cam_empty

# Keyframe pivot rotation
cam_empty.rotation_mode = "XYZ"
cam_empty.rotation_euler = (0, 0, 0)
cam_empty.keyframe_insert(data_path="rotation_euler", frame=FRAME_START)
cam_empty.rotation_euler = (
    0,
    0,
    math.radians(18),
)  # small rotate over whole clip
cam_empty.keyframe_insert(data_path="rotation_euler", frame=FRAME_END)

# Camera slight in/out using location on parent
cam.keyframe_insert(data_path="location", frame=FRAME_START)
cam.location.y = -3.9
cam.keyframe_insert(data_path="location", frame=(FRAME_START + FRAME_END) // 2)
cam.location.y = -4.05
cam.keyframe_insert(data_path="location", frame=FRAME_END)


# ---------- Light setup ----------
# Add a subtle area light above-left
bpy.ops.object.light_add(type="AREA", radius=0.5, location=(-1.5, -1.5, 2.0))
area = bpy.context.active_object
area.name = "KeyLight"
area.data.energy = 200.0
area.data.size = 1.2

# Add a fill area light
bpy.ops.object.light_add(type="AREA", radius=0.5, location=(1.8, -1.8, -0.5))
fill = bpy.context.active_object
fill.name = "FillLight"
fill.data.energy = 40.0
fill.data.size = 1.8

# Add rim light for edge definition
bpy.ops.object.light_add(type="AREA", radius=0.3, location=(0, 2.0, 1.0))
rim = bpy.context.active_object
rim.name = "RimLight"
rim.data.energy = 80.0
rim.data.size = 0.8
rim.data.color = (0.5, 0.8, 1.0)  # Slight cyan tint


# ---------- Subtle volumetric/Haze (a simple cube with volume scatter) ----------
bpy.ops.mesh.primitive_cube_add(size=8, location=(0, 0, 0))
volcube = bpy.context.active_object
volcube.name = "VolumetricCube"

# Make it not render as solid (only volume)
mat_vol = bpy.data.materials.new(name="VolMat")
mat_vol.use_nodes = True
nodes = mat_vol.node_tree.nodes
links = mat_vol.node_tree.links
nodes.clear()

node_volume = nodes.new(type="ShaderNodeVolumeScatter")
node_volume.location = (0, 0)
node_volume.inputs["Density"].default_value = 0.005  # subtle

node_out = nodes.new(type="ShaderNodeOutputMaterial")
node_out.location = (200, 0)
links.new(node_volume.outputs["Volume"], node_out.inputs["Volume"])

volcube.data.materials.append(mat_vol)
volcube.display.show_shadows = False
volcube.hide_render = False


# ---------- Optional: slight glow behind sphere (emissive rim) ----------
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.05, location=(0, 0, 0))
glow = bpy.context.active_object
glow.name = "GlowShell"

mat_glow = bpy.data.materials.new("GlowMat")
mat_glow.use_nodes = True
nodes = mat_glow.node_tree.nodes
links = mat_glow.node_tree.links
nodes.clear()

n_em = nodes.new(type="ShaderNodeEmission")
n_em.location = (0, 0)
n_em.inputs["Strength"].default_value = 1.8

n_col = nodes.new(type="ShaderNodeRGB")
n_col.location = (-200, 0)
n_col.outputs["Color"].default_value = (
    0.0,
    0.35,
    0.9,
    1.0,
)  # Blue glow matching Aura brand

n_out = nodes.new(type="ShaderNodeOutputMaterial")
n_out.location = (200, 0)

links.new(n_col.outputs["Color"], n_em.inputs["Color"])
links.new(n_em.outputs["Emission"], n_out.inputs["Surface"])

mat_glow.blend_method = "BLEND"
mat_glow.shadow_method = "NONE"
glow.data.materials.append(mat_glow)
glow.show_transparent = True


# ---------- Render animation ----------
print("=" * 60)
print("Aura IA Gyroscope Animation Generator")
print("=" * 60)
print(f"Input image: {INPUT_IMAGE_PATH}")
print(f"Output video: {OUTPUT_VIDEO_PATH}")
print(f"Output GLB: {OUTPUT_GLB_PATH}")
print(
    f"Duration: {DURATION_SECONDS}s @ {FPS}fps ({FRAME_END - FRAME_START + 1} frames)"
)
print("=" * 60)
print("\nRendering animation...")

bpy.ops.render.render(animation=True)
print(f"\n✓ Video rendered to: {OUTPUT_VIDEO_PATH}")


# ---------- Export GLB at the last frame ----------
# Move to final frame to capture final pose
bpy.context.scene.frame_set(FRAME_END)

print("\nExporting GLB...")
bpy.ops.export_scene.gltf(
    filepath=OUTPUT_GLB_PATH,
    export_format="GLB",
    export_copyright="Aura IA",
    export_extras=True,
    export_yup=True,
    export_apply=True,
    export_texcoords=True,
    export_normals=True,
    export_materials="EXPORT",
    export_colors=True,
    export_cameras=True,
    export_lights=True,
)

print(f"✓ GLB exported to: {OUTPUT_GLB_PATH}")
print("\n" + "=" * 60)
print("Done! Files ready for dashboard integration.")
print("=" * 60)
print("=" * 60)
print("=" * 60)
