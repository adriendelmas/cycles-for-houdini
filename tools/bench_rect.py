"""Does a rect light's texture read the way Karma reads it?

A 2 x 2 rect light carrying the four-corner texture (blue top-left, white
top-right, red bottom-left, green bottom-right), seen head-on from its
emitting side by an orthographic camera, visible to camera rays in both
renderers. USD puts the texture's min corner at the light's (+X, +Y); a
mirrored or flipped read shows in the quarters, compared with Karma's. Then
the same light turned a quarter about its axis, so a transform is followed
too.

    hython tools/bench_rect.py

Scenes and images go to tests/rect/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "rect", "output")
RES = 64
TOL = 0.03

CORNERS = {(0, 0): (0.1, 0.2, 0.9), (0, 1): (0.9, 0.9, 0.9),
           (1, 0): (0.9, 0.1, 0.1), (1, 1): (0.1, 0.8, 0.2)}  # (row, col), row 0 at the top

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
        token projection = "orthographic"
        float horizontalAperture = 40
        float verticalAperture = 40
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (-1,0,0,0), (0,1,0,0), (0,0,-1,0), (0,0,-5,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def RectLight "rect"
    {
        float inputs:width = 2
        float inputs:height = 2
        asset inputs:texture:file = @corners.exr@
        bool visibleInPrimaryRay = 1
        bool karma:light:renderlightgeo = 1
        matrix4d xformOp:transform = ( %(rows)s, (0,0,0,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
}
"""

CASES = [
    ("plain", "(1,0,0,0), (0,1,0,0), (0,0,1,0)"),
    ("turned_90", "(0,1,0,0), (-1,0,0,0), (0,0,1,0)"),
]


def write_texture():
    px = np.zeros((8, 8, 3), dtype=np.float32)
    for (r, c), colour in CORNERS.items():
        px[r * 4:(r + 1) * 4, c * 4:(c + 1) * 4] = colour
    buf = oiio.ImageBuf(oiio.ImageSpec(8, 8, 3, oiio.FLOAT))
    buf.set_pixels(oiio.ROI(0, 8, 0, 8), px)
    buf.write(os.path.join(OUT, "corners.exr"))


def render(renderer, scene, exr):
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer, "--frame", "1",
                    "--frame-count", "1", "--camera", "/world/camera", "--res", str(RES), str(RES),
                    "--output", exr, scene], capture_output=True, text=True, env=env, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    if buf.has_error:
        return None
    img = buf.get_pixels(oiio.FLOAT)[..., :3]
    # The aperture is in tenths of a unit: the 2-unit light fills the middle
    # half of the frame. Each quarter is sampled away from its borders.
    a, b, m = RES // 4 + 2, 3 * RES // 4 - 2, RES // 2
    return np.array([img[ya:yb, xa:xb].reshape(-1, 3).mean(axis=0)
                     for ya, yb in ((a, m - 2), (m + 2, b)) for xa, xb in ((a, m - 2), (m + 2, b))])


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    write_texture()
    problems = []
    for name, rows in CASES:
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(SCENE % {"rows": rows})
        cyc = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append(name)
            print("%-10s NO IMAGE" % name)
            continue
        worst = float(np.abs(cyc - kar).max())
        ok = worst <= TOL
        print("%-10s %s  worst quarter difference %.3f" % (name, "ok     " if ok else "DIFFERS", worst))
        if not ok:
            for i in range(4):
                print("      quarter %d  cycles %s  karma %s" % (i, np.round(cyc[i], 3),
                                                              np.round(kar[i], 3)))
            problems.append(name)
    print("\n%d cases, %d problems" % (len(CASES), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
