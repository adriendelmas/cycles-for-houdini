"""Does a subdivided mesh keep the shape Karma gives it?

A Catmull-Clark cube, white and unlit on black, seen by an orthographic
camera from a three-quarter view: its silhouette is the subdivided limit
surface. Cases: no tags (a rounded blob); every edge creased infinitely
sharp (the cube itself) and half sharp; the corners made sharp; then an
open grid with its middle face a hole, and under each boundary rule. Then
a left-handed glass cube against the right-handed one, Cycles alone. Each image is compared with
Karma's, pixel by pixel: the fraction of pixels whose coverage differs by
more than half.

    hython tools/bench_subdiv.py [pattern]

Scenes and images go to tests/subdiv/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "subdiv", "output")
RES = 96
TOL = 0.01         # fraction of pixels allowed to differ

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
        float horizontalAperture = %(aperture)d
        float verticalAperture = %(aperture)d
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = %(view)s
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def Mesh "shape" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/white>
        uniform token subdivisionScheme = "catmullClark"
        uniform bool doubleSided = 1
%(mesh)s
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

# Looking at the cube from (1, 0.8, 1), and the grid from above at a slant.
VIEW_CUBE = ("( (0.7071,0,-0.7071,0), (-0.3313,0.8835,-0.3313,0), (0.6247,0.4685,0.6247,0), "
             "(6.247,4.685,6.247,1) )")
VIEW_GRID = "( (1,0,0,0), (0,0.5,-0.866,0), (0,0.866,0.5,0), (0,8.66,5,1) )"

CUBE = """        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 2, 3, 4, 7, 6, 5, 3, 2, 6, 7, 0, 4, 5, 1, 0, 3, 7, 4, 1, 5, 6, 2]
        point3f[] points = [(-1,-1,-1), (1,-1,-1), (1,-1,1), (-1,-1,1), (-1,1,-1), (1,1,-1), (1,1,1), (-1,1,1)]"""
EDGES = "[0,1, 1,2, 2,3, 3,0, 4,5, 5,6, 6,7, 7,4, 0,4, 1,5, 2,6, 3,7]"

# A 3 x 3 grid of quads, open on its four sides.
GRID_POINTS = ", ".join("(%d,0,%d)" % (x, z) for z in (-3, -1, 1, 3) for x in (-3, -1, 1, 3))
GRID_FACES = ", ".join("%d, %d, %d, %d" % (r * 4 + c, r * 4 + c + 4, r * 4 + c + 5, r * 4 + c + 1)
                       for r in range(3) for c in range(3))
GRID = """        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [%s]
        point3f[] points = [%s]""" % (GRID_FACES, GRID_POINTS)

CASES = [
    ("smooth", VIEW_CUBE, 30, CUBE),
    ("crease_sharp", VIEW_CUBE, 30, CUBE + """
        int[] creaseIndices = %s
        int[] creaseLengths = [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
        float[] creaseSharpnesses = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]""" % EDGES),
    ("crease_half", VIEW_CUBE, 30, CUBE + """
        int[] creaseIndices = %s
        int[] creaseLengths = [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
        float[] creaseSharpnesses = [1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5]""" % EDGES),
    ("corners", VIEW_CUBE, 30, CUBE + """
        int[] cornerIndices = [0, 1, 2, 3, 4, 5, 6, 7]
        float[] cornerSharpnesses = [10, 10, 10, 10, 10, 10, 10, 10]"""),
    ("hole", VIEW_GRID, 90, GRID + """
        int[] holeIndices = [4]"""),
    ("boundary_edge_only", VIEW_GRID, 90, GRID + """
        token interpolateBoundary = "edgeOnly\""""),
    ("boundary_edge_and_corner", VIEW_GRID, 90, GRID + """
        token interpolateBoundary = "edgeAndCorner\""""),
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
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)[..., :3].mean(axis=2)


# A left-handed cube: the same faces wound the other way. Hydra triangulates
# such a polygon mesh the right way round; a subdivided one went to Cycles
# inside out, which only refraction shows. Rendered as glass in front of a
# textured wall, by Cycles alone (glass differs between the engines anyway):
# it must match the right-handed cube.
CUBE_LEFT = CUBE.replace(
    "int[] faceVertexIndices = [0, 1, 2, 3, 4, 7, 6, 5, 3, 2, 6, 7, 0, 4, 5, 1, 0, 3, 7, 4, 1, 5, 6, 2]",
    "int[] faceVertexIndices = [3, 2, 1, 0, 5, 6, 7, 4, 7, 6, 2, 3, 1, 5, 4, 0, 4, 7, 3, 0, 2, 6, 5, 1]") + """
        uniform token orientation = "leftHanded\""""

GLASS = """            token outputs:mtlx:surface.connect = </world/Materials/white/g.outputs:out>
            def Shader "g"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                float inputs:base = 0
                float inputs:specular = 0
                float inputs:transmission = 1
                float inputs:specular_IOR = 1.5
                token outputs:out
            }
"""

WALL = """    def Mesh "wall" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/wallmat>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-6,-6,0), (6,-6,0), (6,6,0), (-6,6,0)]
        texCoord2f[] primvars:st = [(0,0), (4,0), (4,4), (0,4)] (interpolation = "vertex")
        matrix4d xformOp:transform = ( (0.7071,0,-0.7071,0), (-0.3313,0.8835,-0.3313,0), (0.6247,0.4685,0.6247,0), (-3.1,-2.3,-3.1,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
"""

WALL_MATERIAL = """        def Material "wallmat"
        {
            token outputs:mtlx:surface.connect = </world/Materials/wallmat/u.outputs:out>
            def Shader "u"
            {
                uniform token info:id = "ND_surface_unlit"
                color3f inputs:emission_color.connect = </world/Materials/wallmat/i.outputs:out>
                token outputs:out
            }
            def Shader "i"
            {
                uniform token info:id = "ND_image_color3"
                asset inputs:file = @corners.exr@
                string inputs:uaddressmode = "periodic"
                string inputs:vaddressmode = "periodic"
                color3f outputs:out
            }
        }
"""


def glass_scene(mesh):
    s = SCENE % {"res": 64, "view": VIEW_CUBE, "aperture": 30, "mesh": mesh}
    i = s.index("            token outputs:mtlx:surface.connect = </world/Materials/white/s.outputs:out>")
    j = s.index("        }\n    }\n}")
    s = s[:i] + GLASS + s[j:]
    s = s.replace('    def Scope "Materials"\n    {\n', WALL + '    def Scope "Materials"\n    {\n' + WALL_MATERIAL, 1)
    return s.replace("int cycles:samples = 16", "int cycles:samples = 64")


def left_handed_glass():
    px = np.zeros((8, 8, 3), dtype=np.float32)
    px[:4, :4], px[:4, 4:] = (0.1, 0.2, 0.9), (0.9, 0.9, 0.9)
    px[4:, :4], px[4:, 4:] = (0.9, 0.1, 0.1), (0.1, 0.8, 0.2)
    buf = oiio.ImageBuf(oiio.ImageSpec(8, 8, 3, oiio.FLOAT))
    buf.set_pixels(oiio.ROI(0, 8, 0, 8), px)
    buf.write(os.path.join(OUT, "corners.exr"))
    images = []
    for name, mesh in (("glass_right", CUBE), ("glass_left", CUBE_LEFT)):
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(glass_scene(mesh))
        images.append(render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr")))
    if images[0] is None or images[1] is None:
        print("%-26s NO IMAGE" % "left_handed_glass")
        return False
    differ = float(np.abs(images[0] - images[1]).mean())
    ok = differ <= 0.01
    print("%-26s %s  mean difference from the right-handed cube %.4f"
          % ("left_handed_glass", "ok     " if ok else "DIFFERS", differ))
    return ok


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    pattern = sys.argv[1] if len(sys.argv) > 1 else None
    problems, count = [], 0
    for name, view, aperture, mesh in CASES:
        if pattern and pattern not in name:
            continue
        count += 1
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(SCENE % {"res": RES, "view": view, "aperture": aperture,
                                                            "mesh": mesh})
        cyc = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append(name)
            print("%-26s NO IMAGE" % name)
            continue
        differ = float((np.abs(cyc - kar) > 0.5).mean())
        ok = differ <= TOL
        print("%-26s %s  coverage cycles %.3f karma %.3f  pixels differing %.3f"
              % (name, "ok     " if ok else "DIFFERS", cyc.mean(), kar.mean(), differ))
        if not ok:
            problems.append(name)
    if not pattern or pattern in "left_handed_glass":
        count += 1
        if not left_handed_glass():
            problems.append("left_handed_glass")
    print("\n%d cases, %d problems" % (count, len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
