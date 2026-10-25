"""Does Karma's Physical Sky render in Cycles as in Karma?

The Karma Physical Sky LOP writes a `KarmaSkyDomeLight` (a generic `light`
to Hydra, its parameters on a kma shader) or a `KarmaSkyAtmosphere` (its
coefficients as primvars), plus a distant light for the sun. The delegate puts
the dome on Cycles' Hosek-Wilkie sky - Karma's own model, which matches to the
fourth decimal - and the atmosphere on the multiple-scattering sky, lit by the
scene's sun, scaled by a measured constant (K-104). Built here through the LOP
itself, under hython, at three sun altitudes; the sky seen by a camera looking
up is compared patch by patch, Cycles against Karma.

The depth-of-field switches ride along (K-105): a camera at f/0.1 blurs, as
in Karma, and renders sharp once the render settings write
`disableDepthOfField = true` or `karma:global:enable_dof = false`.

    hython tools/bench_sky.py

Scenes and images go to tests/sky/output/.
"""

import os
import subprocess
import sys

import hou
import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ["HFS"], "bin")
OUT = os.path.join(ROOT, "tests", "sky", "output")

RES = (160, 100)
ALTITUDES = (10, 30, 60)
DOME_TOL = 1.03
ATMOSPHERE_TOL = 1.45

GEO = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "world"
{
    def Mesh "ground"
    {
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-20,0,-20), (20,0,-20), (20,0,20), (-20,0,20)]
        uniform token subdivisionScheme = "none"
    }
    def Sphere "ball"
    {
        double radius = 1
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 1, 0, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
}
"""

HIDE = """#usda 1.0
over "lights"
{
    over "%s" (active = false) {}
}
"""

CAMERA_DOWN = """#usda 1.0
over "cameras"
{
    over "cam"
    {
        float3 xformOp:rotateXYZ = (-20, 0, 0)
        double3 xformOp:translate = (0, 2, 6)
    }
}
def Scope "Render"
{
    def RenderSettings "dof"
    {
        rel camera = </cameras/cam>
    }
    def RenderSettings "usd_off"
    {
        bool disableDepthOfField = 1
        rel camera = </cameras/cam>
    }
    def RenderSettings "karma_off"
    {
        bool karma:global:enable_dof = 0
        rel camera = </cameras/cam>
    }
}
"""

SCENE = """#usda 1.0
(
    subLayers = [%s]
    metersPerUnit = 1
    upAxis = "Y"
)
"""


def write(name, text):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def rig(altitude):
    """The Physical Sky LOP in both modes and a camera looking up, from Houdini itself."""
    net = hou.node("/stage")
    for child in net.children():
        child.destroy()
    dome = net.createNode("karmaphysicalsky", "skydome")
    dome.parm("skymode").set(0)
    atmo = net.createNode("karmaphysicalsky", "skyatmo")
    atmo.parm("skymode").set(1)
    atmo.setInput(0, dome)
    for sky in (dome, atmo):
        sky.parm("solar_altitude").set(altitude)
        sky.parm("solar_azimuth").set(120)
    cam = net.createNode("camera", "cam")
    cam.setInput(0, atmo)
    cam.parmTuple("t").set((0, 2, 6))
    cam.parmTuple("r").set((25, 0, 0))
    cam.parm("fStop").set(0.1)
    cam.parm("focusDistance").set(100)
    path = os.path.join(OUT, "rig%d.usda" % altitude)
    cam.stage().Flatten().Export(path)
    return path


def render(renderer, scene, exr, settings=None):
    if os.path.exists(exr):
        os.remove(exr)
    cmd = [os.path.join(HFS, "husk.exe"), "--renderer", renderer, "--frame", "1",
           "--frame-count", "1", "--res", str(RES[0]), str(RES[1]), "--camera", "/cameras/cam",
           "--output", exr, scene]
    if settings:
        cmd[-1:-1] = ["--settings", settings]
    subprocess.run(cmd, capture_output=True, text=True, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)[:, :, :3]


def main():
    os.makedirs(OUT, exist_ok=True)
    write("geo.usda", GEO)
    write("no_atmo.usda", HIDE % "skyatmo")
    write("no_dome.usda", HIDE % "skydome")
    write("cam_down.usda", CAMERA_DOWN)
    w, h = RES
    patches = {"top": (2, 10, w // 3, 2 * w // 3), "left": (10, 30, 2, w // 4),
               "right": (10, 30, 3 * w // 4, w - 2), "low": (int(h * 0.75), int(h * 0.9), w // 3, 2 * w // 3)}
    problems = []
    for altitude in ALTITUDES:
        rig(altitude)
        for mode, hide, tol in (("dome", "no_atmo", DOME_TOL), ("atmo", "no_dome", ATMOSPHERE_TOL)):
            name = "%s%d" % (mode, altitude)
            scene = write(name + ".usda", SCENE % ("@%s.usda@, @rig%d.usda@, @geo.usda@" % (hide, altitude)))
            cycles = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
            karma = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
            if cycles is None or karma is None:
                problems.append(name)
                print("%-8s NO IMAGE (cycles %s, karma %s)" % (name, cycles is not None, karma is not None))
                continue
            worst = 1.0
            detail = []
            for patch, (y0, y1, x0, x1) in patches.items():
                c = cycles[y0:y1, x0:x1].mean(axis=(0, 1))
                k = karma[y0:y1, x0:x1].mean(axis=(0, 1))
                ratio = k / np.maximum(c, 1e-6)
                worst = max(worst, float(np.max(np.maximum(ratio, 1.0 / ratio))))
                detail.append("%s %.2f" % (patch, float(ratio.mean())))
            ok = worst <= tol
            print("%-8s karma/cycles %s  worst %.2f (tol %.2f)  %s" % (name, "  ".join(detail), worst, tol, "ok" if ok else "WRONG"))
            if not ok:
                problems.append(name)

    # Depth of field: the camera looks at the ball, f/0.1 focused at 100 m.
    scene = write("dof.usda", SCENE % "@cam_down.usda@, @no_atmo.usda@, @rig30.usda@, @geo.usda@")
    step = lambda px: float(np.abs(np.diff(px.mean(axis=2), axis=1)).max())  # noqa: E731
    blurred = render("HdCyclesPlugin", scene, os.path.join(OUT, "dof_on.exr"), "/Render/dof")
    karma = render("BRAY_HdKarma", scene, os.path.join(OUT, "dof_karma.exr"), "/Render/dof")
    for name in ("usd_off", "karma_off"):
        sharp = render("HdCyclesPlugin", scene, os.path.join(OUT, "dof_%s.exr" % name), "/Render/" + name)
        if blurred is None or sharp is None or karma is None:
            problems.append("dof " + name)
            print("dof      NO IMAGE")
            continue
        b, s, k = step(blurred), step(sharp), step(karma)
        ok = s > 2.0 * b and b < 1.5 * k
        print("dof      sharpest step blurred %.4f (karma %.4f), %s %.4f  %s" % (b, k, name, s, "ok" if ok else "WRONG"))
        if not ok:
            problems.append("dof " + name)

    print("\n%d cases, %d problems" % (len(ALTITUDES) * 2 + 2, len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
