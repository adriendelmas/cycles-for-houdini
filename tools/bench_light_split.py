"""Do a light's diffuse and specular multipliers and shadow colour render as in Karma?

Cycles scales a light as a whole; the delegate splits a light whose lobe
multipliers differ, or that has a shadow colour, into twins (K-87). Seen from
straight above: a floor whose left half is diffuse and right half a rough
metal, under a large rect light, with a board over each half casting a
shadow. Each case sets the light's multipliers or shadow colour; the floor
is sampled lit and in shadow on each half, in Cycles and in Karma.

    hython tools/bench_light_split.py [pattern]

Scenes and images go to tests/lights/output/split/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "lights", "output", "split")
RES = 120         # 10 pixels per unit over the 12-unit frame
TOL_REL = 0.10
TOL_ABS = 0.01

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
        int cycles:samples = 256
        int karma:global:pixelsamples = 256
    }
}
def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = 120
        float verticalAperture = 120
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,0,-1,0), (0,1,0,0), (0,10,0,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
%(quads)s
    def Scope "Materials"
    {
        def Material "diffuse"
        {
            token outputs:mtlx:surface.connect = </world/Materials/diffuse/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                color3f inputs:base_color = (0.8, 0.8, 0.8)
                float inputs:specular = 0
                token outputs:out
            }
        }
        def Material "metal"
        {
            token outputs:mtlx:surface.connect = </world/Materials/metal/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                color3f inputs:base_color = (0.8, 0.8, 0.8)
                float inputs:metalness = 1
                float inputs:specular_roughness = 0.4
                token outputs:out
            }
        }
        def Material "board"
        {
            token outputs:mtlx:surface.connect = </world/Materials/board/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                float inputs:base = 0
                float inputs:specular = 0
                token outputs:out
            }
        }
    }
    def RectLight "light"
    {
        float inputs:width = 12
        float inputs:height = 12
        float inputs:intensity = 1
%(inputs)s
        float3 xformOp:translate = (0, 4, 0)
        float3 xformOp:rotateXYZ = (-90, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
    }
}
"""

QUAD = """    def Mesh "%(name)s" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/%(material)s>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 3, 2, 1]
        point3f[] points = [(%(x0)s, %(y)s, %(z0)s), (%(x1)s, %(y)s, %(z0)s), (%(x1)s, %(y)s, %(z1)s), (%(x0)s, %(y)s, %(z1)s)]
        normal3f[] normals = [(0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0)] (interpolation = "vertex")
        uniform token subdivisionScheme = "none"
        bool doubleSided = 1
%(extra)s
    }"""


def quad(name, material, x0, x1, z0, z1, y, extra=""):
    return QUAD % dict(name=name, material=material, x0=x0, x1=x1, z0=z0, z1=z1, y=y,
                       extra=extra)


# Floor halves at x < 0 (diffuse) and x > 0 (metal); a board 3 units square
# one unit above each, at z = -3, hidden from the camera (Karma's visibility
# primvar, which the delegate reads too) so the floor under it shows: shadowed
# at z = -3, lit at z = 3.
HIDDEN = '        string primvars:karma:object:rendervisibility = "-primary"'
QUADS = "\n".join([
    quad("diffuse", "diffuse", -6, 0, -6, 6, 0),
    quad("metal", "metal", 0, 6, -6, 6, 0),
    quad("board_d", "board", -4.5, -1.5, -4.5, -1.5, 1, HIDDEN),
    quad("board_m", "board", 1.5, 4.5, -4.5, -1.5, 1, HIDDEN),
])

# Image samples (x, z) in scene units: lit and shadowed, on each half.
POINTS = {
    "diffuse lit": (-3, 3),
    "metal lit": (3, 3),
    "diffuse shadow": (-3, -3),
    "metal shadow": (3, -3),
}

CASES = [
    ("plain", []),
    ("diffuse_half", ["float inputs:diffuse = 0.5"]),
    ("specular_half", ["float inputs:specular = 0.5"]),
    ("both_half", ["float inputs:diffuse = 0.5", "float inputs:specular = 0.5"]),
    ("diffuse_off", ["float inputs:diffuse = 0"]),
    ("shadow_color", ['color3f inputs:shadow:color = (0.6, 0.2, 0)']),
    ("shadow_color_specular", ['color3f inputs:shadow:color = (0.6, 0.2, 0)',
                               "float inputs:specular = 0.3"]),
    ("shadow_off", ["bool inputs:shadow:enable = 0"]),
]


def render(name, renderer, scene):
    exr = os.path.join(OUT, "%s_%s.exr" % (name, renderer))
    if os.path.exists(exr):
        os.remove(exr)
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer,
                    "--frame", "1", "--frame-count", "1", "--output", exr, scene],
                   capture_output=True, text=True, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)[:, :, :3]


def sample(img, x, z):
    # The camera looks down -Y with +X right and -Z up the image.
    col = int(round((x + 6) * RES / 12.0))
    row = int(round((z + 6) * RES / 12.0))
    return img[row - 1:row + 2, col - 1:col + 2].reshape(-1, 3).mean(axis=0)


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else ""
    os.makedirs(OUT, exist_ok=True)
    problems = 0
    cases = [c for c in CASES if pattern in c[0]]
    for name, inputs in cases:
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(SCENE % dict(
            res=RES, quads=QUADS, inputs="\n".join("        " + i for i in inputs)))
        cyc = render(name, "HdCyclesPlugin", scene)
        kar = render(name, "BRAY_HdKarma", scene)
        if cyc is None or kar is None:
            print("%-22s NO IMAGE" % name)
            problems += 1
            continue
        bad = []
        for label, (x, z) in POINTS.items():
            c, k = sample(cyc, x, z), sample(kar, x, z)
            if np.any(np.abs(c - k) > np.maximum(TOL_ABS, TOL_REL * np.abs(k))):
                bad.append("%s %s vs %s" % (label, np.round(c, 3), np.round(k, 3)))
        print("%-22s %s" % (name, "ok" if not bad else "DIFFERS  " + "; ".join(bad)))
        problems += 1 if bad else 0
    print("\n%d cases, %d problems" % (len(cases), problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
