"""Do USD's implicit surfaces render, at their size and along their axis?

Sphere, Cube, Cylinder, Cone, Capsule and Plane prims, white and emissive in a
row, seen from +Z by an orthographic camera. The silhouette of each is
computed here from its USD attributes and compared with the covered pixels:
a shape missing, scaled or lying along the wrong axis fails.

    hython tools/bench_implicit.py

Scene and image go to tests/implicit/output/.
"""

import math
import os
import subprocess
import sys

import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "implicit", "output")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

WIDTH, HEIGHT = 350, 100
PIXELS_PER_UNIT = WIDTH / 7.0


def disc(r):
    return lambda x, y: x * x + y * y <= r * r


def box(hw, hh):
    return lambda x, y: abs(x) <= hw and abs(y) <= hh


def capsule_y(r, h):
    def inside(x, y):
        ay = max(abs(y) - h / 2.0, 0.0)
        return x * x + ay * ay <= r * r
    return inside


# (type, attributes, silhouette seen along Z, centred on the prim)
SHAPES = [
    ("Sphere", "double radius = 0.4", disc(0.4)),
    ("Cube", "double size = 0.8", box(0.4, 0.4)),
    # Along Z, seen end on: a disc. Along X: a rectangle 0.8 long.
    ("Cylinder", 'double radius = 0.3\n        double height = 0.8\n        uniform token axis = "X"', box(0.4, 0.3)),
    ("Cone", 'double radius = 0.4\n        double height = 0.8\n        uniform token axis = "Z"', disc(0.4)),
    ("Capsule", 'double radius = 0.3\n        double height = 0.4\n        uniform token axis = "Y"', capsule_y(0.3, 0.4)),
    ("Plane", 'double width = 0.8\n        double length = 0.6\n        uniform token axis = "Z"', box(0.4, 0.3)),
]

HEAD = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = 70
        float verticalAperture = 20
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 10, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def DomeLight "black"
    {
        float inputs:intensity = 0
    }
    def Material "glow"
    {
        token outputs:cycles:surface.connect = </world/glow/e.outputs:emission>
        def Shader "e"
        {
            uniform token info:id = "cycles_emission"
            color3f inputs:color = (1, 1, 1)
            float inputs:strength = 1
            token outputs:emission
        }
    }
"""


def main():
    body = ""
    for i, (kind, attrs, _) in enumerate(SHAPES):
        body += """    def %s "p%d" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/glow>
        %s
        double3 xformOp:translate = (%g, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
""" % (kind, i, attrs, -2.5 + i)
    scene = os.path.join(OUT, "implicit.usda")
    open(scene, "w", encoding="utf-8").write(HEAD + body + "}\n")
    exr = os.path.join(OUT, "implicit.exr")
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                    "--camera", "/world/camera", "--res", str(WIDTH), str(HEIGHT),
                    "--output", exr, scene], capture_output=True, text=True, env=env, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    if buf.has_error:
        print("NO IMAGE")
        sys.exit(1)
    img = buf.get_pixels(oiio.FLOAT)

    problems = 0
    half = PIXELS_PER_UNIT / 2.0
    for i, (kind, _, inside) in enumerate(SHAPES):
        cx = WIDTH / 2.0 + (-2.5 + i) * PIXELS_PER_UNIT
        x0, x1 = int(cx - half), int(cx + half)
        got = int((img[:, x0:x1, :3].max(axis=2) > 0.5).sum())
        want = 0
        for py in range(HEIGHT):
            for px in range(x0, x1):
                x = (px + 0.5 - cx) / PIXELS_PER_UNIT
                y = (HEIGHT / 2.0 - py - 0.5) / PIXELS_PER_UNIT
                want += inside(x, y)
        ok = want > 0 and abs(got - want) <= 0.06 * want
        print("%-9s %-6s %4d px covered, %4d expected" % (kind, "ok" if ok else "WRONG", got, want))
        problems += not ok
    print("\n%d shapes, %d problems" % (len(SHAPES), problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
