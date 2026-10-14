"""Does a tangent-space normal map tilt the surface the way Karma tilts it?

A quad facing the camera, its u along +X and v along +Y, a diffuse
standard_surface whose normal comes from a `normalmap` node fed a constant
tangent-space normal tilted towards +u, -u, +v or -v. A distant light grazes
the quad from +X, then from +Y: a tilt towards the light brightens it, away
darkens it. A flipped green channel, a mirrored tangent or a map ignored
shows as a brightness on the wrong side; each case's mean is compared with
Karma's. Also: the same through the `scale` input, and a mesh whose UVs run
backwards along X (a mirrored tangent).

    hython tools/bench_normalmap.py [pattern]

Scenes and images go to tests/normalmap/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ["HFS"], "bin")
OUT = os.path.join(ROOT, "tests", "normalmap", "output")
RES = 48
# Cycles darkens a bumped or normal-mapped surface towards its terminator on
# purpose (Conty Estevez et al.'s shadowing term, kernel/closure/bsdf.h),
# Karma does not: up to 8 % on these tilts. A wrong tilt is 2x or more.
TOL_REL = 0.10
TOL_ABS = 0.01

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
        int cycles:samples = 16
        int karma:global:pixelsamples = 16
    }
}
def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = 20
        float verticalAperture = 20
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,10,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def Mesh "quad" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/M>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-1,-1,0), (1,-1,0), (1,1,0), (-1,1,0)]
        normal3f[] normals = [(0,0,1), (0,0,1), (0,0,1), (0,0,1)] (interpolation = "vertex")
        texCoord2f[] primvars:st = %(st)s (interpolation = "vertex")
        uniform token subdivisionScheme = "none"
    }
    def DistantLight "sun"
    {
        float inputs:intensity = 1
        bool inputs:normalize = 1
        float inputs:angle = 1
        float3 xformOp:rotateXYZ = %(light)s
        uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
    }
    def Scope "Materials"
    {
        def Material "M"
        {
            token outputs:mtlx:surface.connect = </world/Materials/M/s.outputs:out>
            def Shader "s"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                color3f inputs:base_color = (0.8, 0.8, 0.8)
                float inputs:specular = 0
                vector3f inputs:normal.connect = </world/Materials/M/nm.outputs:out>
                token outputs:out
            }
            def Shader "nm"
            {
                uniform token info:id = "ND_normalmap_float"
                vector3f inputs:in = %(tilt)s
%(extra)s
                vector3f outputs:out
            }
        }
    }
}
"""

ST = "[(0,0), (1,0), (1,1), (0,1)]"
ST_MIRRORED = "[(1,0), (0,0), (0,1), (1,1)]"
# The light comes from +X (its -Z turned towards -X), then from +Y; both
# 60 degrees off the quad's normal.
FROM_X = "(0, 60, 0)"
FROM_Y = "(-60, 0, 0)"
TILTS = {"u+": "(0.85, 0.5, 0.85)", "u-": "(0.15, 0.5, 0.85)",
         "v+": "(0.5, 0.85, 0.85)", "v-": "(0.5, 0.15, 0.85)", "flat": "(0.5, 0.5, 1)"}

CASES = []
for light_name, light in (("from_x", FROM_X), ("from_y", FROM_Y)):
    for tilt in ("flat", "u+", "u-", "v+", "v-"):
        CASES.append(("%s_%s" % (light_name, tilt), ST, light, TILTS[tilt], ""))
CASES += [
    ("scale_half", ST, FROM_X, TILTS["u+"], "                float inputs:scale = 0.5"),
    ("mirrored_uv_u+", ST_MIRRORED, FROM_X, TILTS["u+"], ""),
]


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
    q = RES // 2
    return float(img[q - 3:q + 3, q - 3:q + 3].mean())


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    pattern = sys.argv[1] if len(sys.argv) > 1 else None
    problems, count = [], 0
    for name, st, light, tilt, extra in CASES:
        if pattern and pattern not in name:
            continue
        count += 1
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(SCENE % {
            "res": RES, "st": st, "light": light, "tilt": tilt, "extra": extra})
        cyc = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append(name)
            print("%-16s NO IMAGE" % name)
            continue
        ok = abs(cyc - kar) <= max(TOL_ABS, TOL_REL * kar)
        print("%-16s %s  cycles %.4f  karma %.4f" % (name, "ok     " if ok else "DIFFERS", cyc, kar))
        if not ok:
            problems.append(name)
    print("\n%d cases, %d problems" % (count, len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
