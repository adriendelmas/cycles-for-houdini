"""Do USD curves render where USD says they are?

Cycles draws every curve as a Catmull-Rom spline through all of its keys, or as
a polyline. A USD Bezier curve does not pass through its inner control points,
a B-spline through none of them, a periodic curve closes on itself, a pinned one
reaches its end points, and `varying` widths sit on the
segment ends. Each case draws white emissive curves seen from above by an
orthographic camera, then checks a few points of the plane: covered where the
USD curve goes, empty where only a misread one would.

    hython tools/bench_curves.py [pattern]

Scenes and images go to tests/curves/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "curves", "output")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

RES = 200
# An orthographic camera 4 units wide, centred on (0, 1): 50 pixels per unit.
CENTER = (0.0, 1.0)
PIXELS_PER_UNIT = RES / 4.0

SCENE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
    startTimeCode = 1
    endTimeCode = 1
)

def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = 40
        float verticalAperture = 40
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (%(cx)g, %(cy)g, 10, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def DomeLight "black"
    {
        float inputs:intensity = 0
    }
    def BasisCurves "curves" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/glow>
%(curve)s
    }
    def Scope "Materials"
    {
        def Material "glow"
        {
            token outputs:cycles:surface.connect = </world/Materials/glow/e.outputs:emission>
            def Shader "e"
            {
                uniform token info:id = "cycles_emission"
                color3f inputs:color = (1, 1, 1)
                float inputs:strength = 1
                token outputs:emission
            }
        }
    }
}
"""


def pts(*points):
    return ", ".join("(%g, %g, 0)" % p for p in points)


# (name, curve body, [(x, y, should_be_covered)])
CASES = [
    # A Bezier arch: on-curve ends at y = 0, controls at y = 2. The curve peaks
    # at y = 1.5 (t = 0.5); read as Catmull-Rom through all four points it ran
    # through the controls at y = 2 instead.
    ("bezier", """        uniform token type = "cubic"
        uniform token basis = "bezier"
        int[] curveVertexCounts = [4]
        point3f[] points = [%s]
        float[] widths = [0.08] (interpolation = "constant")""" % pts((-1, 0), (-1, 2), (1, 2), (1, 0)),
     [(0.0, 1.5, True), (-1.0, 2.0, False), (1.0, 2.0, False), (0.0, 2.0, False)]),
    # A uniform B-spline through four points on a line passes through none of
    # the outer ones: it spans (P0 + 4 P1 + P2) / 6 to (P1 + 4 P2 + P3) / 6,
    # x = -0.5 to 0.5 here.
    ("bspline", """        uniform token type = "cubic"
        uniform token basis = "bspline"
        int[] curveVertexCounts = [4]
        point3f[] points = [%s]
        float[] widths = [0.08] (interpolation = "constant")""" % pts((-1.5, 1), (-0.5, 1), (0.5, 1), (1.5, 1)),
     [(0.0, 1.0, True), (-0.4, 1.0, True), (-0.7, 1.0, False), (0.7, 1.0, False)]),
    # A closed square, drawn as a periodic linear curve: the closing side, from
    # the last point back to the first, must be there.
    ("periodic", """        uniform token type = "linear"
        uniform token wrap = "periodic"
        int[] curveVertexCounts = [4]
        point3f[] points = [%s]
        float[] widths = [0.08] (interpolation = "constant")""" % pts((-1, 0), (1, 0), (1, 2), (-1, 2)),
     [(0.0, 0.0, True), (1.0, 1.0, True), (0.0, 2.0, True), (-1.0, 1.0, True), (0.0, 1.0, False)]),
    # A pinned B-spline starts and ends on its first and last points, where
    # an open one stops short of them. (Indexed curves have no USD attribute:
    # only Hydra producers hand topology indices over, so a file cannot test
    # them.)
    ("pinned", """        uniform token type = "cubic"
        uniform token basis = "bspline"
        uniform token wrap = "pinned"
        int[] curveVertexCounts = [4]
        point3f[] points = [%s]
        float[] widths = [0.08] (interpolation = "constant")""" % pts((-1.5, 1), (-0.5, 1), (0.5, 1), (1.5, 1)),
     [(0.0, 1.0, True), (-1.4, 1.0, True), (1.4, 1.0, True)]),
    # Varying widths on a cubic curve, one per segment end: thin at the left,
    # wide at the right. Varying widths were not read at all.
    ("varying_widths", """        uniform token type = "cubic"
        uniform token basis = "catmullRom"
        int[] curveVertexCounts = [5]
        point3f[] points = [%s]
        float[] widths = [0.02, 0.2, 0.6] (interpolation = "varying")""" % pts((-2, 1), (-1, 1), (0, 1), (1, 1), (2, 1)),
     [(0.9, 1.25, True), (-0.9, 1.25, False), (0.0, 1.0, True)]),
]


def covered(img, x, y):
    px = int(round(RES / 2 + (x - CENTER[0]) * PIXELS_PER_UNIT))
    py = int(round(RES / 2 - (y - CENTER[1]) * PIXELS_PER_UNIT))
    window = img[max(py - 1, 0):py + 2, max(px - 1, 0):px + 2, :3]
    return float(window.max()) > 0.5


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else ""
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    problems = []
    for name, curve, probes in CASES:
        if pattern not in name:
            continue
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(
            SCENE % {"cx": CENTER[0], "cy": CENTER[1], "curve": curve})
        exr = os.path.join(OUT, name + ".exr")
        if os.path.exists(exr):
            os.remove(exr)
        subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                        "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                        "--res", str(RES), str(RES), "--output", exr, scene],
                       capture_output=True, text=True, env=env, cwd=OUT)
        buf = oiio.ImageBuf(exr)
        if buf.has_error:
            problems.append((name, "NO IMAGE"))
            print("%-16s NO IMAGE" % name)
            continue
        img = buf.get_pixels(oiio.FLOAT)
        wrong = [(x, y, want) for x, y, want in probes if covered(img, x, y) != want]
        state = "ok" if not wrong else "WRONG"
        detail = "; ".join("(%g, %g) %s" % (x, y, "should be covered" if want else "should be empty")
                           for x, y, want in wrong)
        print("%-16s %-6s %s" % (name, state, detail))
        if wrong:
            problems.append((name, detail))
    print("\n%d cases, %d problems" % (len([c for c in CASES if pattern in c[0]]), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
