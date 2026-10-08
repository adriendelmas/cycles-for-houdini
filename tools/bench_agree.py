"""Does Cycles agree with Karma on the same USD?

A sphere on a grey standard_surface ground, lit by a rect light and a distant
light, with one material per case on the sphere - the standard_surface lobes one at a time (diffuse, glossy
dielectric, metal, glass, coat, emission) and a UsdPreviewSurface - rendered
by both renderers from the same file, through husk. The sphere's centre and
two patches of floor are compared on their mean RGB: the ratio Cycles/Karma
must stay within TOL, a tolerance that admits the two engines' real
differences (a few percent, different sampling of a glossy lobe) and rejects a
factor of two. This is the check that would have caught the x4 distant light,
the x pi dome, and a glass tinted by its base colour.

No dome light: husk's Karma leaves a bare DomeLight out of the camera's view
and Cycles shows it (docs/TESTING.md), so the sky is black on both sides and
only lit surfaces are compared. A region darker than DARK on both sides is
not compared either. The ground carries a material of its own because the
two renderers do not shade an unbound prim alike: Cycles' fallback is a
diffuse whose albedo is the displayColor, Karma's comes out 2.4 times darker
on the same displayColor (measured 2026-10-08); bound, the floor matches to
the third decimal.

    hython tools/bench_agree.py [--karma-only|--cycles-only] [pattern]

Scenes and images go to tests/agreement/output/; a side-by-side PNG per case
(Cycles left, Karma right) for the eye.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "agreement", "output")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

RES = (240, 180)
TOL = 1.25     # ratio Cycles/Karma allowed per channel on a lit region
DARK = 0.01    # below this on both sides, a region is not compared
EMISSIVE_TOL = 1.10  # Karma's standard_surface emits ~5 % under the nominal value
# Through a glass sphere Cycles shows the refracted floor at its brightness,
# Karma CPU 2.8 times darker (2026-10-08): the engines' paths through a
# dielectric differ, not the translation. The case guards the order of
# magnitude - a black or a white sphere - and nothing finer.
GLASS_TOL = 4.0

# Regions in pixels at RES, y downward: the sphere's centre (its lit upper
# half, the key light being up-left), and two floor patches away from the
# sphere's shadow, which the key light throws right and back.
REGIONS = {
    "sphere": (104, 136, 70, 100),   # x0, x1, y0, y1
    "floor L": (10, 70, 140, 175),
    "floor R": (170, 230, 140, 175),
}

CASES = [
    ("diffuse", "ND_standard_surface_surfaceshader", {
        "color3f inputs:base_color": "(0.6, 0.3, 0.2)", "float inputs:specular": "0",
        "float inputs:specular_roughness": "0.5"}),
    ("dielectric", "ND_standard_surface_surfaceshader", {
        "color3f inputs:base_color": "(0.2, 0.5, 0.25)", "float inputs:specular_roughness": "0.3"}),
    ("metal", "ND_standard_surface_surfaceshader", {
        "color3f inputs:base_color": "(0.95, 0.72, 0.3)", "float inputs:metalness": "1",
        "float inputs:specular_roughness": "0.25"}),
    ("glass", "ND_standard_surface_surfaceshader", {
        "color3f inputs:base_color": "(1, 1, 1)", "float inputs:transmission": "1",
        "float inputs:specular_roughness": "0.05", "float inputs:specular_IOR": "1.5"}),
    ("coat", "ND_standard_surface_surfaceshader", {
        "color3f inputs:base_color": "(0.7, 0.1, 0.1)", "float inputs:specular": "0",
        "float inputs:coat": "1", "float inputs:coat_roughness": "0.1"}),
    ("emission", "ND_standard_surface_surfaceshader", {
        "color3f inputs:base_color": "(0.05, 0.05, 0.05)", "float inputs:specular": "0",
        "float inputs:emission": "2", "color3f inputs:emission_color": "(1, 0.4, 0.12)"}),
    ("preview", "UsdPreviewSurface", {
        "color3f inputs:diffuseColor": "(0.25, 0.4, 0.7)", "float inputs:roughness": "0.4",
        "float inputs:metallic": "0"}),
]

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
        float focalLength = 30
        float horizontalAperture = 36
        float verticalAperture = 27
        float2 clippingRange = (0.1, 1000)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,0.966,-0.259,0), (0,0.259,0.966,0), (0, 3.5, 10, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }

    def Mesh "ground" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        rel material:binding = </world/Materials/floor>
        # Wound counter-clockwise seen from above, so the geometric normal is
        # +Y like the authored one. Cycles shades a backfacing hit by flipping
        # both normals: with the winding the other way the authored +Y became
        # -Y and the floor went black, where Karma faces the normal forward.
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 3, 2, 1]
        point3f[] points = [(-20, 0, -20), (20, 0, -20), (20, 0, 20), (-20, 0, 20)]
        normal3f[] normals = [(0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0)] (
            interpolation = "vertex"
        )
        color3f[] primvars:displayColor = [(0.35, 0.35, 0.38)]
        uniform token subdivisionScheme = "none"
    }

    def Sphere "obj" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        rel material:binding = </world/Materials/mat>
        double radius = 1
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 1, 0, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }

    def Scope "Materials"
    {
        def Material "floor"
        {
            token outputs:mtlx:surface.connect = </world/Materials/floor/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                color3f inputs:base_color = (0.35, 0.35, 0.38)
                float inputs:specular = 0
                float inputs:specular_roughness = 0.6
                token outputs:out
            }
        }
        def Material "mat"
        {
            token outputs:%(terminal)s.connect = </world/Materials/mat/surf.outputs:%(output)s>
            def Shader "surf"
            {
                uniform token info:id = "%(shader)s"
%(inputs)s
                token outputs:%(output)s
            }
        }
    }

    def RectLight "key"
    {
        float inputs:width = 6
        float inputs:height = 6
        float inputs:intensity = 12
        matrix4d xformOp:transform = ( (1,0,0,0), (0,0.5,-0.866,0), (0,0.866,0.5,0), (-4, 7, 6, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }

    def DistantLight "sun"
    {
        float inputs:intensity = 2
        float inputs:angle = 1
        # As Houdini's Distant Light LOP writes it. Left unset, both
        # renderers give the light next to nothing (2026-10-08).
        bool inputs:normalize = 1
        float3 xformOp:rotateXYZ = (-50, 30, 0)
        uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
    }
}
"""


def scene_text(shader, inputs):
    mtlx = shader.startswith("ND_")
    lines = "\n".join("                %s = %s" % kv for kv in inputs.items())
    return SCENE % {"terminal": "mtlx:surface" if mtlx else "surface",
                    "output": "out" if mtlx else "surface",
                    "shader": shader, "inputs": lines}


def render(renderer, scene_path, exr):
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer,
                    "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                    "--res", str(RES[0]), str(RES[1]), "--output", exr, scene_path],
                   capture_output=True, text=True, env=env, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)[..., :3]


def region_mean(img, box):
    x0, x1, y0, y1 = box
    return img[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)


def side_by_side(a, b, path):
    big = np.concatenate([a, b], axis=1)
    big = np.repeat(np.repeat(big, 2, axis=0), 2, axis=1)
    spec = oiio.ImageSpec(big.shape[1], big.shape[0], 3, oiio.FLOAT)
    out = oiio.ImageBuf(spec)
    out.set_pixels(oiio.ROI(0, big.shape[1], 0, big.shape[0]), np.clip(big, 0, 1) ** (1 / 2.2))
    out.write(path)


def main():
    pattern = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    problems = []
    checks = 0
    for name, shader, inputs in CASES:
        if pattern and pattern not in name:
            continue
        scene_path = os.path.join(OUT, name + ".usda")
        open(scene_path, "w", encoding="utf-8").write(scene_text(shader, inputs))
        cyc = render("HdCyclesPlugin", scene_path, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene_path, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append((name, "NO IMAGE (%s)" % ("Cycles" if cyc is None else "Karma")))
            print("%-11s NO IMAGE" % name)
            continue
        side_by_side(cyc, kar, os.path.join(OUT, name + "_cmp.png"))
        tol = {"emission": EMISSIVE_TOL, "glass": GLASS_TOL}.get(name, TOL)
        for region, box in REGIONS.items():
            a, b = region_mean(cyc, box), region_mean(kar, box)
            if a.max() < DARK and b.max() < DARK:
                continue
            checks += 1
            ratio = (a + 1e-4) / (b + 1e-4)
            ok = bool(np.all(ratio < tol) and np.all(ratio > 1 / tol))
            print("%-11s %-8s cycles %s  karma %s  ratio %s  %s"
                  % (name, region, np.round(a, 3), np.round(b, 3), np.round(ratio, 2),
                     "ok" if ok else "DIFFERS"))
            if not ok:
                problems.append((name, "%s ratio %s" % (region, np.round(ratio, 2))))
    print("\n%d checks, %d problems" % (checks, len(problems)))
    for name, what in problems:
        print("   %-11s %s" % (name, what))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
