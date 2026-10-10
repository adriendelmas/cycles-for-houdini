"""Does each kind of light put on the floor what Karma puts there?

A white diffuse floor seen from straight above by an orthographic camera,
lit by one light per case, two units up, facing down. The floor's radiance
is sampled under the light and at 1, 2 and 3 units off to the side, so both
the level and the falloff are compared - a spot's cone shows at the side.
Cases: sphere (normalized and not), disk, rect, cylinder, distant; spots
(a shaping cone, hard, soft, softness alone), emission focus with and
without a tint, IES profiles (plain, normalized, angle-scaled, asymmetric),
a normalized disk and cylinder, a point (treatAsPoint), a colour with a
temperature, a textured rect light, exposure, colour temperature.

    hython tools/bench_lights.py [pattern]

Scenes and images go to tests/lights/output/.
"""

import math
import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "lights", "output")
RES = 80          # 10 pixels per unit over the 8-unit frame
TOL_REL = 0.10
TOL_ABS = 0.003
OFFSETS = (0, 1, 2, 3)

SCENE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
)
def Scope "Render"
{
    def RenderSettings "settings"
    {
        rel camera = </world/camera>
        int2 resolution = (%(res)d, %(res)d)
        int cycles:samples = 64
        int karma:global:pixelsamples = 64
    }
}
def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = 80
        float verticalAperture = 80
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,0,-1,0), (0,1,0,0), (0,10,0,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def Mesh "floor" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/floor>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 3, 2, 1]
        point3f[] points = [(-20, 0, -20), (20, 0, -20), (20, 0, 20), (-20, 0, 20)]
        normal3f[] normals = [(0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0)] (interpolation = "vertex")
        uniform token subdivisionScheme = "none"
    }
    def Scope "Materials"
    {
        def Material "floor"
        {
            token outputs:mtlx:surface.connect = </world/Materials/floor/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                color3f inputs:base_color = (0.8, 0.8, 0.8)
                float inputs:specular = 0
                token outputs:out
            }
        }
    }
    def %(light)s "light" %(schemas)s
    {
%(inputs)s
        float3 xformOp:translate = (0, 2, 0)
        float3 xformOp:rotateXYZ = %(rotate)s
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
    }
}
"""

SHAPING = '(prepend apiSchemas = ["ShapingAPI"])'

# Lights turned otherwise than facing the floor.
ROTATE = {"cylinder_rolled": "(90, 0, 0)"}

# (name, light type, api schemas, inputs)
CASES = [
    ("sphere", "SphereLight", "", ["float inputs:radius = 0.25", "float inputs:intensity = 10"]),
    ("sphere_normalized", "SphereLight", "", ["float inputs:radius = 0.25",
                                              "float inputs:intensity = 2",
                                              "bool inputs:normalize = 1"]),
    ("disk", "DiskLight", "", ["float inputs:radius = 0.5", "float inputs:intensity = 5"]),
    ("rect", "RectLight", "", ["float inputs:width = 1", "float inputs:height = 0.5",
                               "float inputs:intensity = 5"]),
    ("rect_normalized", "RectLight", "", ["float inputs:width = 1", "float inputs:height = 0.5",
                                          "float inputs:intensity = 2",
                                          "bool inputs:normalize = 1"]),
    ("cylinder", "CylinderLight", "", ["float inputs:radius = 0.1", "float inputs:length = 1",
                                       "float inputs:intensity = 5"]),
    ("distant", "DistantLight", "", ["float inputs:intensity = 1", "bool inputs:normalize = 1"]),
    ("spot", "SphereLight", SHAPING, ["float inputs:radius = 0.05", "float inputs:intensity = 200",
                                      "float inputs:shaping:cone:angle = 30",
                                      "float inputs:shaping:cone:softness = 0.2"]),
    ("spot_hard", "SphereLight", SHAPING, ["float inputs:radius = 0.05",
                                           "float inputs:intensity = 200",
                                           "float inputs:shaping:cone:angle = 40"]),
    ("focus", "RectLight", SHAPING, ["float inputs:width = 1", "float inputs:height = 1",
                                     "float inputs:intensity = 5",
                                     "float inputs:shaping:focus = 2"]),
    ("focus_tint", "RectLight", SHAPING, ["float inputs:width = 1", "float inputs:height = 1",
                                          "float inputs:intensity = 5",
                                          "float inputs:shaping:focus = 2",
                                          "color3f inputs:shaping:focusTint = (1, 0.2, 0)"]),
    ("focus_sphere", "SphereLight", SHAPING, ["float inputs:radius = 0.25",
                                              "float inputs:intensity = 10",
                                              "float inputs:shaping:focus = 3"]),
    # Softness alone: USD's default cone is 90 degrees.
    ("softness_only", "SphereLight", SHAPING, ["float inputs:radius = 0.05",
                                               "float inputs:intensity = 200",
                                               "float inputs:shaping:cone:softness = 0.5"]),
    # IES profiles (written by write_ies): read as candela values, over the
    # profile's mean with normalize, narrowed by angleScale; the asymmetric
    # one's lobe points away from the sampled side (Karma's horizontal angle
    # 0 is the light's -X), so a turned profile shows 3 times too bright.
    ("ies", "SphereLight", SHAPING, ["float inputs:radius = 0.05", "float inputs:intensity = 0.2",
                                     "asset inputs:shaping:ies:file = @profile.ies@"]),
    ("ies_normalize", "SphereLight", SHAPING, ["float inputs:radius = 0.05",
                                               "float inputs:intensity = 80",
                                               "asset inputs:shaping:ies:file = @profile.ies@",
                                               "bool inputs:shaping:ies:normalize = 1"]),
    ("ies_angle_scale", "SphereLight", SHAPING, ["float inputs:radius = 0.05",
                                                 "float inputs:intensity = 0.2",
                                                 "asset inputs:shaping:ies:file = @profile.ies@",
                                                 "float inputs:shaping:ies:angleScale = 1.5"]),
    ("ies_asymmetric", "SphereLight", SHAPING, ["float inputs:radius = 0.05",
                                                "float inputs:intensity = 1",
                                                "asset inputs:shaping:ies:file = @asym.ies@"]),
    ("disk_normalized", "DiskLight", "", ["float inputs:radius = 0.5", "float inputs:intensity = 2",
                                          "bool inputs:normalize = 1"]),
    ("cylinder_normalized", "CylinderLight", "", ["float inputs:radius = 0.1",
                                                  "float inputs:length = 1",
                                                  "float inputs:intensity = 5",
                                                  "bool inputs:normalize = 1"]),
    # Turned over: a tube lights all around its axis, where the rectangle
    # that stood in for it faced up and left the floor dark (K-89).
    ("cylinder_rolled", "CylinderLight", "", ["float inputs:radius = 0.1",
                                              "float inputs:length = 1",
                                              "float inputs:intensity = 5"]),
    ("treat_as_point", "SphereLight", "", ["float inputs:radius = 0.25", "float inputs:intensity = 10",
                                           "bool treatAsPoint = 1"]),
    ("color_and_temperature", "SphereLight", "", ["float inputs:radius = 0.25",
                                                  "float inputs:intensity = 10",
                                                  "color3f inputs:color = (0.2, 0.5, 1)",
                                                  "bool inputs:enableColorTemperature = 1",
                                                  "float inputs:colorTemperature = 3000"]),
    ("rect_textured", "RectLight", "", ["float inputs:width = 1", "float inputs:height = 1",
                                        "float inputs:intensity = 5",
                                        "asset inputs:texture:file = @corners.exr@"]),
    ("exposure", "SphereLight", "", ["float inputs:radius = 0.25", "float inputs:intensity = 5",
                                     "float inputs:exposure = 1"]),
    ("temperature", "SphereLight", "", ["float inputs:radius = 0.25",
                                        "float inputs:intensity = 10",
                                        "bool inputs:enableColorTemperature = 1",
                                        "float inputs:colorTemperature = 3000"]),
]


def write_corners():
    """The four-corner texture for the textured rect light."""
    px = np.zeros((8, 8, 3), dtype=np.float32)
    px[:4, :4] = (0.1, 0.2, 0.9)
    px[:4, 4:] = (0.9, 0.9, 0.9)
    px[4:, :4] = (0.9, 0.1, 0.1)
    px[4:, 4:] = (0.1, 0.8, 0.2)
    buf = oiio.ImageBuf(oiio.ImageSpec(8, 8, 3, oiio.FLOAT))
    buf.set_pixels(oiio.ROI(0, 8, 0, 8), px)
    buf.write(os.path.join(OUT, "corners.exr"))


def write_ies():
    """Two type C profiles at 5 degree steps down to 90: 1000 cos^2, the
    same on every horizontal angle, and with its 0 degree side 3 times
    brighter than the others (horizontal angles 0, 90, 180, 270, 360)."""
    v = list(range(0, 95, 5))
    base = [1000.0 * math.cos(math.radians(a)) ** 2 for a in v]
    for name, sides in (("profile.ies", [1.0]), ("asym.ies", [1.0, 0.3, 0.3, 0.3, 1.0])):
        h = [0] if len(sides) == 1 else [0, 90, 180, 270, 360]
        lines = ["IESNA:LM-63-2002", "TILT=NONE",
                 "1 -1 1 %d %d 1 1 0 0 0" % (len(v), len(h)), "1 1 100",
                 " ".join(str(a) for a in v), " ".join(str(a) for a in h)]
        lines += [" ".join("%.3f" % (b * f) for b in base) for f in sides]
        with open(os.path.join(OUT, name), "w", newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")


def render(renderer, scene, exr):
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer, "--frame", "1",
                    "--frame-count", "1", "-s", "/Render/settings", "--output", exr, scene],
                   capture_output=True, text=True, env=env, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    if buf.has_error:
        return None
    img = buf.get_pixels(oiio.FLOAT)[..., :3]
    c = RES // 2
    return np.array([img[c - 2:c + 3, c + 10 * x - 2:c + 10 * x + 3].reshape(-1, 3).mean(axis=0)
                     for x in OFFSETS])


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    write_ies()
    write_corners()
    pattern = sys.argv[1] if len(sys.argv) > 1 else None
    problems, count = [], 0
    for name, light, schemas, inputs in CASES:
        if pattern and pattern not in name:
            continue
        count += 1
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(SCENE % {
            "res": RES, "light": light, "schemas": schemas,
            "rotate": ROTATE.get(name, "(-90, 0, 0)"),
            "inputs": "\n".join("        " + l for l in inputs)})
        cyc = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append(name)
            print("%-18s NO IMAGE" % name)
            continue
        bad = np.abs(cyc - kar) > np.maximum(TOL_ABS, TOL_REL * np.abs(kar))
        print("%-18s %s" % (name, "ok" if not bad.any() else "DIFFERS"))
        for x, a, b in zip(OFFSETS, cyc, kar):
            ratio = a.mean() / max(b.mean(), 1e-6)
            print("      at %d  cycles %s  karma %s  ratio %.2f" % (x, np.round(a, 4), np.round(b, 4), ratio))
        if bad.any():
            problems.append(name)
    print("\n%d cases, %d problems" % (count, len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
