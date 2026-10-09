"""Does a displaced surface move where Karma moves it?

A Catmull-Clark plane four units by one, white and unlit, seen from 30
degrees above by an orthographic camera; its displacement moves it up the
image. The top and bottom rows the surface covers, column by column, are
compared with Karma's. Cases: no displacement; a MaterialX `displacement`
whose amount grows along u (a ramp); a UsdPreviewSurface's `displacement`
input, a constant height.

    hython tools/bench_displace.py

Scenes and images go to tests/displace/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "displace", "output")
COLUMNS = (24, 36, 48, 60, 72)
TOL_ROWS = 1

HEAD = """#usda 1.0
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
        int2 resolution = (96, 96)
        int cycles:samples = 8
        int karma:global:pixelsamples = 8
    }
}
def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = 60
        float verticalAperture = 60
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,0.866,-0.5,0), (0,0.5,0.866,0), (0,5,8.66,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def Mesh "plane" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/M>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 3, 2, 1]
        point3f[] points = [(-2,0,-0.5), (2,0,-0.5), (2,0,0.5), (-2,0,0.5)]
        texCoord2f[] primvars:st = [(0,0), (1,0), (1,1), (0,1)] (interpolation = "vertex")
        uniform token subdivisionScheme = "catmullClark"
        uniform token interpolateBoundary = "edgeAndCorner"
    }
    def Scope "Materials"
    {
        def Material "M"
        {
"""

TAIL = """        }
    }
}
"""

MATERIALS = {
    "flat": """            token outputs:mtlx:surface.connect = </world/Materials/M/s.outputs:out>
            def Shader "s"
            {
                uniform token info:id = "ND_surface_unlit"
                color3f inputs:emission_color = (1, 1, 1)
                token outputs:out
            }
            def Shader "tc"
            {
                uniform token info:id = "ND_texcoord_vector2"
                float2 outputs:out
            }
            def Shader "sep"
            {
                uniform token info:id = "ND_separate2_vector2"
                float2 inputs:in.connect = </world/Materials/M/tc.outputs:out>
                float outputs:outx
            }
            def Shader "d"
            {
                uniform token info:id = "ND_displacement_float"
                float inputs:displacement.connect = </world/Materials/M/sep.outputs:outx>
                float inputs:scale = 2
                token outputs:out
            }
""",
    "mtlx_ramp": """            token outputs:mtlx:surface.connect = </world/Materials/M/s.outputs:out>
            token outputs:mtlx:displacement.connect = </world/Materials/M/d.outputs:out>
            def Shader "s"
            {
                uniform token info:id = "ND_surface_unlit"
                color3f inputs:emission_color = (1, 1, 1)
                token outputs:out
            }
            def Shader "tc"
            {
                uniform token info:id = "ND_texcoord_vector2"
                float2 outputs:out
            }
            def Shader "sep"
            {
                uniform token info:id = "ND_separate2_vector2"
                float2 inputs:in.connect = </world/Materials/M/tc.outputs:out>
                float outputs:outx
            }
            def Shader "d"
            {
                uniform token info:id = "ND_displacement_float"
                float inputs:displacement.connect = </world/Materials/M/sep.outputs:outx>
                float inputs:scale = 2
                token outputs:out
            }
""",
    "preview_constant": """            token outputs:surface.connect = </world/Materials/M/p.outputs:surface>
            token outputs:displacement.connect = </world/Materials/M/p.outputs:displacement>
            def Shader "p"
            {
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:emissiveColor = (1, 1, 1)
                color3f inputs:diffuseColor = (0, 0, 0)
                float inputs:displacement = 0.8
                token outputs:surface
                token outputs:displacement
            }
""",
}


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
    covered = buf.get_pixels(oiio.FLOAT)[..., :3].mean(axis=2) > 0.1
    rows = []
    for c in COLUMNS:
        hit = np.nonzero(covered[:, c])[0]
        rows.append((int(hit[0]), int(hit[-1])) if hit.size else (-1, -1))
    return rows


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    problems = []
    for name, material in MATERIALS.items():
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(HEAD + material + TAIL)
        cyc = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append(name)
            print("%-17s NO IMAGE" % name)
            continue
        ok = all(abs(a - b) <= TOL_ROWS for ca, ka in zip(cyc, kar) for a, b in zip(ca, ka))
        print("%-17s %s  rows cycles %s  karma %s" % (name, "ok     " if ok else "DIFFERS", cyc, kar))
        if not ok:
            problems.append(name)
    print("\n%d cases, %d problems" % (len(MATERIALS), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
