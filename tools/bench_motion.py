"""Does everything that moves during the shutter blur by the right length?

A white emissive square, one unit wide, crosses an orthographic view from
x = -1 at frame 1 to x = 1 at frame 2. The camera's shutter is open from
-0.25 to 0.25 frames, so the square travels one unit while it is open and its
trail covers two units of the image; a sharp square covers one. Each case moves
the square a different way - its own transform, its points, a PointInstancer's
positions or the instancer's transform; or the camera moves instead - and the
trail is measured along the middle row.

    hython tools/bench_motion.py [pattern]

Scenes and images go to tests/motion/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ["HFS"], "bin")
OUT = os.path.join(ROOT, "tests", "motion", "output")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

RES = 200
# An orthographic camera 5 units wide centred on the origin: 40 pixels per unit.
PIXELS_PER_UNIT = RES / 5.0

SCENE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
    startTimeCode = 1
    endTimeCode = 2
    timeCodesPerSecond = 24
)

def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = 50
        float verticalAperture = 50
        float2 clippingRange = (0.1, 100)
        double shutter:open = -0.25
        double shutter:close = 0.25
        %(camera)s
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def DomeLight "black"
    {
        float inputs:intensity = 0
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
%(body)s
}
"""

SQUARE = """        rel material:binding = </world/Materials/glow>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        uniform token subdivisionScheme = "none"
"""

STILL_POINTS = "point3f[] points = [(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)]"
MOVING_XFORM = """matrix4d xformOp:transform.timeSamples = {
            1: ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (-1, 0, 0, 1) ),
            2: ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (1, 0, 0, 1) ),
        }
        uniform token[] xformOpOrder = ["xformOp:transform"]"""


def mesh(name, extra, points=STILL_POINTS):
    return """    def Mesh "%s" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
%s        %s
        %s
    }""" % (name, SQUARE, points, extra)


def instancer(positions, extra=""):
    return """    def PointInstancer "inst"
    {
        rel prototypes = [</world/inst/protos/square>]
        int[] protoIndices = [0]
        %s
        %s
        def Scope "protos"
        {
%s
        }
    }""" % (positions, extra, mesh("square", "").replace("\n    ", "\n            "))


STILL_CAMERA = "matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 10, 1) )"


def camera_keys(keys):
    return "matrix4d xformOp:transform.timeSamples = {%s}" % ", ".join(
        "%s: ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (%s, 0, 10, 1) )" % k for k in keys)


# Cases where the camera moves past a still square. Its keys sit outside the
# shutter, so sampling at the keys' own times (as the delegate once did) blurs
# too long; `camera_bounce` turns back mid-shutter (x 0.5, 1, 0.5 while open),
# which two samples cannot show.
CAMERAS = {
    "camera": camera_keys([(1, -1), (2, 1)]),
    "camera_bounce": camera_keys([(1, 0), (1.5, 1), (2, 0)]),
}

# (name, scene body, expected trail in units)
CASES = [
    ("still", mesh("square", ""), 1.0),
    ("transform", mesh("square", MOVING_XFORM), 2.0),
    ("points", mesh("square", "", """point3f[] points.timeSamples = {
            1: [(-1.5, -0.5, 0), (-0.5, -0.5, 0), (-0.5, 0.5, 0), (-1.5, 0.5, 0)],
            2: [(0.5, -0.5, 0), (1.5, -0.5, 0), (1.5, 0.5, 0), (0.5, 0.5, 0)],
        }"""), 2.0),
    ("instance_still", instancer("point3f[] positions = [(0, 0, 0)]"), 1.0),
    ("instance_positions", instancer("""point3f[] positions.timeSamples = {
            1: [(-1, 0, 0)],
            2: [(1, 0, 0)],
        }"""), 2.0),
    ("instancer_transform", instancer("point3f[] positions = [(0, 0, 0)]",
                                      MOVING_XFORM.replace("\n        ", "\n        ")), 2.0),
    ("camera", mesh("square", ""), 2.0),
    ("camera_bounce", mesh("square", ""), 1.5),
]


def trail(img):
    row = img[RES // 2, :, :3].max(axis=1)
    covered = np.where(row > 0.02)[0]
    if not len(covered):
        return 0.0
    return (covered[-1] - covered[0] + 1) / PIXELS_PER_UNIT


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else ""
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    problems = []
    cases = [c for c in CASES if pattern in c[0]]
    for name, body, expected in cases:
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(SCENE % {"body": body, "camera": CAMERAS.get(name, STILL_CAMERA)})
        exr = os.path.join(OUT, name + ".exr")
        if os.path.exists(exr):
            os.remove(exr)
        subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                        "--frame", "1.5", "--frame-count", "1", "--camera", "/world/camera",
                        "--res", str(RES), str(RES), "--output", exr, scene],
                       capture_output=True, text=True, env=env, cwd=OUT)
        buf = oiio.ImageBuf(exr)
        if buf.has_error:
            problems.append(name)
            print("%-20s NO IMAGE" % name)
            continue
        got = trail(buf.get_pixels(oiio.FLOAT))
        # Two pixels of slack on each side for the pixel filter.
        ok = abs(got - expected) <= 4.0 / PIXELS_PER_UNIT
        print("%-20s %-6s trail %.2f units, expected %.2f" % (name, "ok" if ok else "WRONG", got, expected))
        if not ok:
            problems.append(name)
    print("\n%d cases, %d problems" % (len(cases), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
