"""Does the camera frame and blur what Karma's does?

Small white unlit squares on black, seen by one camera per case; the image's
weighted centroid of each square, its spread (the root mean square distance
of its light from the centroid) and its total light are compared with
Karma's. Cases: an off-axis perspective framing; the aperture offsets (lens
shift); depth of field (an f-stop and a focus distance, squares in and out
of focus); an orthographic camera; the camera's exposure; an image whose
aspect differs from the aperture's (USD's aperture conform policy); a crop
window (dataWindowNDC); a pixel aspect ratio of 2.

    hython tools/bench_camera.py [pattern]

Scenes and images go to tests/camera/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "camera", "output")
TOL_PX = 1.0       # centroid and spread, in pixels
TOL_REL = 0.05     # total light

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
        int2 resolution = %(res)s
        int cycles:samples = 128
        int karma:global:pixelsamples = 128
%(settings)s
    }
}
def Xform "world"
{
    def Camera "camera"
    {
%(camera)s
        float2 clippingRange = (0.1, 1000)
    }
%(squares)s
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

SQUARE = """    def Mesh "sq%(i)d" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/white>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(%(x0)g,%(y0)g,%(z)g), (%(x1)g,%(y0)g,%(z)g), (%(x1)g,%(y1)g,%(z)g), (%(x0)g,%(y1)g,%(z)g)]
        uniform token subdivisionScheme = "none"
    }
"""

PERSP = ["float focalLength = 35", "float horizontalAperture = 36", "float verticalAperture = 24"]

# (name, resolution, camera lines, squares as (x, y, z, size))
CASES = [
    ("framing", "(120, 80)", PERSP, [(0, 0, -10, 0.4), (2, 1, -10, 0.4), (-3, -1.5, -10, 0.4)]),
    ("lens_shift", "(120, 80)", PERSP + ["float horizontalApertureOffset = 5",
                                         "float verticalApertureOffset = 3"],
     [(0, 0, -10, 0.4), (2, 1, -10, 0.4)]),
    ("depth_of_field", "(120, 80)", PERSP + ["float fStop = 8", "float focusDistance = 5"],
     [(0, 0, -5, 0.2), (1.5, 0.5, -15, 0.6)]),
    ("orthographic", "(120, 80)", ['token projection = "orthographic"',
                                   "float horizontalAperture = 120",
                                   "float verticalAperture = 80"],
     [(0, 0, -10, 1), (3, 2, -10, 1)]),
    ("exposure", "(120, 80)", PERSP + ["float exposure = 1"], [(0, 0, -10, 1)]),
    ("aspect_wider", "(160, 80)", PERSP, [(0, 0, -10, 0.4), (3, 1.5, -10, 0.4)]),
    ("aspect_taller", "(80, 80)", PERSP, [(0, 0, -10, 0.4), (3, 1.5, -10, 0.4)]),
]

# Render settings beyond the resolution: a crop of the frame's middle, which
# is rendered as a data window inside the full display window, and pixels
# twice as wide as they are tall.
SETTINGS = {
    "crop": "        float4 dataWindowNDC = (0.25, 0.25, 0.75, 0.75)",
    "crop_corner": "        float4 dataWindowNDC = (0.5, 0.5, 1, 1)",
    "pixel_aspect": "        float pixelAspectRatio = 2",
}
CASES += [
    ("crop", "(120, 80)", PERSP, [(0, 0, -10, 0.4), (2, 1, -10, 0.4)]),
    ("crop_corner", "(120, 80)", PERSP, [(2, 1, -10, 0.4), (3, 2, -10, 0.4)]),
    ("pixel_aspect", "(120, 80)", PERSP, [(0, 0, -10, 0.4), (2, 1, -10, 0.4)]),
]


def scene_text(res, camera, squares, settings=""):
    sq = "".join(SQUARE % {"i": i, "x0": x - s / 2, "x1": x + s / 2, "y0": y - s / 2,
                           "y1": y + s / 2, "z": z} for i, (x, y, z, s) in enumerate(squares))
    return SCENE % {"res": res, "camera": "\n".join("        " + l for l in camera),
                    "squares": sq, "settings": settings}


def render(renderer, scene, exr):
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer, "--frame", "1",
                    "--frame-count", "1", "-s", "/Render/settings", "--output", exr, scene],
                   capture_output=True, text=True, env=env, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)[..., :3].mean(axis=2)


def blobs(img, count):
    """Centroid, spread and total of the `count` brightest blobs, found by
    splitting the lit pixels around seeds taken greedily far apart."""
    ys, xs = np.nonzero(img > 0.02 * img.max())
    w = img[ys, xs]
    pts = np.stack([xs + 0.5, ys + 0.5], axis=1)
    seeds = [pts[np.argmax(w)]]
    while len(seeds) < count:
        d = np.min([np.linalg.norm(pts - s, axis=1) for s in seeds], axis=0)
        seeds.append(pts[np.argmax(d * w)])
    owner = np.argmin([np.linalg.norm(pts - s, axis=1) for s in seeds], axis=0)
    out = []
    for k in range(count):
        m = owner == k
        c = (pts[m] * w[m, None]).sum(axis=0) / w[m].sum()
        spread = np.sqrt((((pts[m] - c) ** 2).sum(axis=1) * w[m]).sum() / w[m].sum())
        out.append((c, spread, w[m].sum()))
    return sorted(out, key=lambda b: (b[0][0], b[0][1]))


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    pattern = sys.argv[1] if len(sys.argv) > 1 else None
    problems, count = [], 0
    for name, res, camera, squares in CASES:
        if pattern and pattern not in name:
            continue
        count += 1
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(scene_text(res, camera, squares,
                                                             SETTINGS.get(name, "")))
        cyc = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append(name)
            print("%-15s NO IMAGE" % name)
            continue
        if cyc.shape != kar.shape:
            problems.append(name)
            print("%-15s SIZE cycles %s karma %s" % (name, cyc.shape, kar.shape))
            continue
        ok = True
        lines = []
        for (cc, cs, ct), (kc, ks, kt) in zip(blobs(cyc, len(squares)), blobs(kar, len(squares))):
            good = (np.abs(cc - kc).max() <= TOL_PX and abs(cs - ks) <= TOL_PX
                    and abs(ct - kt) <= TOL_REL * kt)
            ok &= good
            lines.append("      centroid cycles (%.1f, %.1f) karma (%.1f, %.1f)  spread %.2f / %.2f"
                         "  light %.1f / %.1f%s" % (cc[0], cc[1], kc[0], kc[1], cs, ks, ct, kt,
                                                    "" if good else "   <--"))
        print("%-15s %s" % (name, "ok" if ok else "DIFFERS"))
        print("\n".join(lines))
        if not ok:
            problems.append(name)
    print("\n%d cases, %d problems" % (count, len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
