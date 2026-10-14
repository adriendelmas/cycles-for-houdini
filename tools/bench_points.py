"""Do USD points render as large as Karma renders them?

White unlit points on black, seen from above by an orthographic camera; each
image's covered pixels are compared with Karma's (intersection over union).
Cases: one width for all, a width per point, no width at all (Hydra's
fallback, 1), the points under a scaled transform; linear curves without
widths.

    hython tools/bench_points.py [pattern]

Scenes and images go to tests/points/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ["HFS"], "bin")
OUT = os.path.join(ROOT, "tests", "points", "output")
RES = 96
MIN_IOU = 0.9

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
        float horizontalAperture = 100
        float verticalAperture = 100
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,0,-1,0), (0,1,0,0), (0,10,0,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def %(prim)s "pts" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/white>
        point3f[] points = [(-3,0,-3), (0,0,-3), (3,0,-3), (-3,0,0), (0,0,0), (3,0,0), (-3,0,3), (0,0,3), (3,0,3)]
%(extra)s
    }
    def Scope "Materials"
    {
        def Material "white"
        {
            token outputs:mtlx:surface.connect = </world/Materials/white/s.outputs:out>
            def Shader "s"
            {
                uniform token info:id = "ND_surface_unlit"
                color3f inputs:emission_color = (1, 1, 1)
                token outputs:out
            }
        }
    }
}
"""

CASES = [
    ("constant_width", 'Points', '        float[] widths = [1.2] (interpolation = "constant")'),
    ("per_point_width", 'Points', '        float[] widths = [0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0] '
                        '(interpolation = "vertex")'),
    ("no_width", 'Points', ""),
    # Linear curves through the same points, three of three, no widths.
    ("curves_no_width", 'BasisCurves', '        uniform token type = "linear"\n'
                                       '        int[] curveVertexCounts = [3, 3, 3]'),
    ("scaled", 'Points', '        float[] widths = [0.6] (interpolation = "constant")\n'
               '        float3 xformOp:scale = (1.5, 1.5, 1.5)\n'
               '        uniform token[] xformOpOrder = ["xformOp:scale"]'),
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
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)[..., :3].mean(axis=2) > 0.5


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    pattern = sys.argv[1] if len(sys.argv) > 1 else None
    problems, count = [], 0
    for name, prim, extra in CASES:
        if pattern and pattern not in name:
            continue
        count += 1
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(SCENE % {"res": RES, "prim": prim, "extra": extra})
        cyc = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append(name)
            print("%-16s NO IMAGE" % name)
            continue
        union = (cyc | kar).sum()
        iou = (cyc & kar).sum() / union if union else 1.0
        ok = iou >= MIN_IOU
        print("%-16s %s  covered cycles %d karma %d  IoU %.2f"
              % (name, "ok     " if ok else "DIFFERS", cyc.sum(), kar.sum(), iou))
        if not ok:
            problems.append(name)
    print("\n%d cases, %d problems" % (count, len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
