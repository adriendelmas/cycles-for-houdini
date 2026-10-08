"""Does an absorbing volume transmit what Beer-Lambert says?

A 2-unit cube holding only a volume, in front of a white `surface_unlit`
wall, seen head-on: the light crossing it is exp(-2 sigma_a). Karma renders
no volume on a mesh that has no surface, so the reference is the law itself.
Cases:

- `mtlx_absorption`: MaterialX `absorption_vdf`, whose `absorption` is the
  coefficient sigma_a (it was taken as Cycles' colour, inverted, before 0107);
- `native_absorption`: Cycles' own absorption volume, colour 0.5 at density 1,
  sigma_a = (1 - colour) * density = 0.5;
- `lefthanded`: the MaterialX case on a cube written as Houdini writes meshes,
  `orientation = "leftHanded"` - a winding read the wrong way doubles the path
  through the volume.

The wall's white also checks `surface_unlit`, black before 0107.

    hython tools/bench_volume.py

Scenes and images go to tests/volume/output/.
"""

import math
import os
import subprocess
import sys

import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "volume", "output")

SIGMA = (0.2, 0.5, 1.0)
TOL = 0.02

OUTWARD = "0, 1, 2, 3,  4, 7, 6, 5,  3, 2, 6, 7,  0, 4, 5, 1,  0, 3, 7, 4,  1, 5, 6, 2"
INWARD = "0, 3, 2, 1,  4, 5, 6, 7,  3, 7, 6, 2,  0, 1, 5, 4,  0, 4, 7, 3,  1, 2, 6, 5"

MTLX_VOLUME = """            token outputs:mtlx:volume.connect = </world/Materials/M/vol.outputs:out>
            def Shader "vol"
            {
                uniform token info:id = "ND_volume"
                token inputs:vdf.connect = </world/Materials/M/abs.outputs:out>
                token outputs:out
            }
            def Shader "abs"
            {
                uniform token info:id = "ND_absorption_vdf"
                vector3f inputs:absorption = (%g, %g, %g)
                token outputs:out
            }""" % SIGMA

NATIVE_VOLUME = """            token outputs:cycles:volume.connect = </world/Materials/M/abs.outputs:volume>
            def Shader "abs"
            {
                uniform token info:id = "cycles_absorption_volume"
                color3f inputs:color = (0.5, 0.5, 0.5)
                float inputs:density = 1
                token outputs:volume
            }"""

SCENE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "world"
{
    def Camera "camera"
    {
        float focalLength = 50
        float horizontalAperture = 36
        float verticalAperture = 24
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 10, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def Mesh "wall" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/W>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-20,-20,-5), (20,-20,-5), (20,20,-5), (-20,20,-5)]
        uniform token subdivisionScheme = "none"
    }
    def Mesh "box" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/M>
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [%(indices)s]
        point3f[] points = [(-1,-1,-1), (1,-1,-1), (1,-1,1), (-1,-1,1), (-1,1,-1), (1,1,-1), (1,1,1), (-1,1,1)]
        uniform token orientation = "%(orientation)s"
        uniform token subdivisionScheme = "none"
    }
    def Scope "Materials"
    {
        def Material "W"
        {
            token outputs:mtlx:surface.connect = </world/Materials/W/s.outputs:out>
            def Shader "s"
            {
                uniform token info:id = "ND_surface_unlit"
                color3f inputs:emission_color = (1, 1, 1)
                token outputs:out
            }
        }
        def Material "M"
        {
%(volume)s
        }
    }
}
"""

CASES = [
    ("mtlx_absorption", MTLX_VOLUME, OUTWARD, "rightHanded", tuple(math.exp(-2 * s) for s in SIGMA)),
    ("native_absorption", NATIVE_VOLUME, OUTWARD, "rightHanded", (math.exp(-1.0),) * 3),
    ("lefthanded", MTLX_VOLUME, INWARD, "leftHanded", tuple(math.exp(-2 * s) for s in SIGMA)),
]


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    problems = []
    for name, volume, indices, orientation, expected in CASES:
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(
            SCENE % {"volume": volume, "indices": indices, "orientation": orientation})
        exr = os.path.join(OUT, name + ".exr")
        if os.path.exists(exr):
            os.remove(exr)
        subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                        "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                        "--res", "120", "80", "--output", exr, scene],
                       capture_output=True, text=True, env=env, cwd=OUT)
        buf = oiio.ImageBuf(exr)
        if buf.has_error:
            problems.append(name)
            print("%-18s NO IMAGE" % name)
            continue
        px = buf.get_pixels(oiio.FLOAT)
        centre = px[34:46, 54:66, :3].reshape(-1, 3).mean(axis=0)
        wall = px[2:8, 2:8, :3].reshape(-1, 3).mean(axis=0)
        ratio = [c / max(w, 1e-6) for c, w in zip(centre, wall)]
        ok = all(abs(r - e) <= TOL for r, e in zip(ratio, expected)) and min(wall) > 0.95
        print("%-18s wall %.3f  transmitted %s  expected %s  %s"
              % (name, min(wall), " ".join("%.3f" % r for r in ratio),
                 " ".join("%.3f" % e for e in expected), "ok" if ok else "WRONG"))
        if not ok:
            problems.append(name)
    print("\n%d cases, %d problems" % (len(CASES), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
