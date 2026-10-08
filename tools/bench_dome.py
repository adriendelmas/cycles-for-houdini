"""Does a dome light's texture face where Karma has it face?

A lat-long texture with one colour per quarter of the horizon (red, green,
blue, yellow, each centred on an axis whatever the convention's offset), a
white top and dark lower rows, on a USD dome light seen directly by a narrow
camera turned to the four horizon axes, and 75 degrees up and down. A
dome turned, mirrored or upside down shows a different colour in some
direction; each direction's mean is compared between Cycles and Karma.
Karma leaves a dome out of the camera's view unless told to render it.
The same on a Z-up stage with a DomeLight_1, whose pole follows the stage.

    hython tools/bench_dome.py

Scenes and images go to tests/dome/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "dome", "output")
RES = 32
TOL = 0.03

BANDS = [(0.9, 0.1, 0.1), (0.1, 0.8, 0.2), (0.1, 0.2, 0.9), (0.9, 0.8, 0.1)]

# Camera orientations as USD row matrices: the camera looks down its -Z.
DIRECTIONS = {
    "yaw_0": "(1,0,0,0), (0,1,0,0), (0,0,1,0)",
    "yaw_90": "(0,0,-1,0), (0,1,0,0), (1,0,0,0)",
    "yaw_180": "(-1,0,0,0), (0,1,0,0), (0,0,-1,0)",
    "yaw_270": "(0,0,1,0), (0,1,0,0), (-1,0,0,0)",
    # 75 degrees up and down, towards -Z: at the poles themselves Cycles
    # blends the first and last rows (its map wraps vertically too), which a
    # real HDRI's half-texel hides and this 8-row texture does not.
    "up_75": "(1,0,0,0), (0,0.258819,0.965926,0), (0,-0.965926,0.258819,0)",
    "down_75": "(1,0,0,0), (0,0.258819,-0.965926,0), (0,0.965926,0.258819,0)",
}

SCENE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "%(up)s"
)
def Xform "world"
{
    def Camera "camera"
    {
        float focalLength = 50
        float horizontalAperture = 10
        float verticalAperture = 10
        matrix4d xformOp:transform = ( %(rows)s, (0,0,0,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def %(dome)s "dome"
    {
        asset inputs:texture:file = @dome.exr@
        token inputs:texture:format = "latlong"
        bool karma:light:renderlightgeo = 1
    }
}
"""


def write_texture():
    """16 x 8: rows 0-1 white, 2-5 the band's colour, 6-7 a third of it.
    Each band is centred on a quarter of the width, so an axis falls in
    a band's middle wherever a convention starts its longitude."""
    px = np.zeros((8, 16, 3), dtype=np.float32)
    for x in range(16):
        colour = np.array(BANDS[((x + 2) // 4) % 4], dtype=np.float32)
        px[0:2, x] = 1.0
        px[2:6, x] = colour
        px[6:8, x] = colour * 0.3
    buf = oiio.ImageBuf(oiio.ImageSpec(16, 8, 3, oiio.FLOAT))
    buf.set_pixels(oiio.ROI(0, 16, 0, 8), px)
    buf.write(os.path.join(OUT, "dome.exr"))


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
    q = RES // 4
    return buf.get_pixels(oiio.FLOAT)[q:RES - q, q:RES - q, :3].reshape(-1, 3).mean(axis=0)


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    write_texture()
    problems = []
    cases = [(n, r, "Y", "DomeLight") for n, r in DIRECTIONS.items()]
    # DomeLight_1 on a Z-up stage: its pole follows the stage's up axis.
    # There the poles are on Z: yaw_0 and yaw_180 would look straight at
    # them, so the pole is checked at 75 degrees, like the Y-up one.
    cases += [("zup_" + n, r, "Z", "DomeLight_1") for n, r in DIRECTIONS.items()
              if n not in ("yaw_0", "yaw_180")]
    cases.append(("zup_towards_z_75", "(-1,0,0,0), (0,0.965926,-0.258819,0), "
                  "(0,-0.258819,-0.965926,0)", "Z", "DomeLight_1"))
    for name, rows, up, dome in cases:
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(SCENE % {"rows": rows, "up": up, "dome": dome})
        cyc = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append(name)
            print("%-12s NO IMAGE" % name)
            continue
        worst = float(np.abs(cyc - kar).max())
        ok = worst <= TOL
        print("%-12s %s  cycles %s  karma %s" % (name, "ok     " if ok else "DIFFERS",
                                                np.round(cyc, 3), np.round(kar, 3)))
        if not ok:
            problems.append(name)
    print("\n%d directions, %d problems" % (len(cases), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
