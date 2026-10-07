"""Do a PointInstancer's per-instance primvars reach each instance?

Three white squares instanced along x, each given its own `displayColor` and a
float `weight` on the instancer. The squares emit what a shader reads back -
through an attribute node, through Object Info's colour - and the centre of
each is compared with the value its instance carries. The nested case puts
that instancer inside a second one that adds its own `rowweight` per row: the
inner colour and the outer value must both arrive.

    hython tools/bench_instances.py [pattern]

Scenes and images go to tests/instances/output/.
"""

import os
import subprocess
import sys

import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "instances", "output")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

RES = 200
# An orthographic camera 5 units wide centred on the origin: 40 pixels per unit.
PIXELS_PER_UNIT = RES / 5.0

COLORS = [(0.9, 0.1, 0.1), (0.1, 0.9, 0.1), (0.1, 0.1, 0.9)]
WEIGHT = [0.25, 0.5, 1.0]
ROW_WEIGHT = [0.2, 0.7]
XS = [-1.5, 0.0, 1.5]
ROWS = [-1.0, 1.0]

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
        float horizontalAperture = 50
        float verticalAperture = 50
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 10, 1) )
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
                color3f inputs:color.connect = %(source)s
                float inputs:strength = 1
                token outputs:emission
            }
%(probe)s
        }
    }
%(body)s
}
"""

PROBES = {
    "attribute": ("</world/Materials/glow/a.outputs:color>", """            def Shader "a"
            {
                uniform token info:id = "cycles_attribute"
                string inputs:attribute = "displayColor"
                color3f outputs:color
            }"""),
    "weight": ("</world/Materials/glow/a.outputs:color>", """            def Shader "a"
            {
                uniform token info:id = "cycles_attribute"
                string inputs:attribute = "weight"
                color3f outputs:color
            }"""),
    "rowweight": ("</world/Materials/glow/a.outputs:color>", """            def Shader "a"
            {
                uniform token info:id = "cycles_attribute"
                string inputs:attribute = "rowweight"
                color3f outputs:color
            }"""),
    "object_color": ("</world/Materials/glow/o.outputs:color>", """            def Shader "o"
            {
                uniform token info:id = "cycles_object_info"
                color3f outputs:color
            }"""),
}

SQUARE = """def Mesh "square" (prepend apiSchemas = ["MaterialBindingAPI"])
{
    rel material:binding = </world/Materials/glow>
    int[] faceVertexCounts = [4]
    int[] faceVertexIndices = [0, 1, 2, 3]
    point3f[] points = [(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)]
    uniform token subdivisionScheme = "none"
}"""


def indent(text, n):
    return "\n".join(" " * n + line if line else line for line in text.splitlines())


def row_instancer(name, y):
    return """def PointInstancer "%s"
{
    rel prototypes = [</world/%s/protos/square>]
    int[] protoIndices = [0, 0, 0]
    point3f[] positions = [%s]
    color3f[] primvars:displayColor = [%s] (interpolation = "vertex")
    float[] primvars:weight = [%s] (interpolation = "vertex")
    def Scope "protos"
    {
%s
    }
}""" % (name, name, ", ".join("(%g, %g, 0)" % (x, y) for x in XS),
        ", ".join("(%g, %g, %g)" % c for c in COLORS),
        ", ".join("%g" % h for h in WEIGHT), indent(SQUARE, 8))


def flat_body():
    return indent(row_instancer("inst", 0.0), 4)


def nested_body():
    inner = row_instancer("row", 0.0).replace("rel prototypes = [</world/row/protos/square>]",
                                              "rel prototypes = [</world/outer/protos/row/protos/square>]")
    return indent("""def PointInstancer "outer"
{
    rel prototypes = [</world/outer/protos/row>]
    int[] protoIndices = [0, 0]
    point3f[] positions = [%s]
    float[] primvars:rowweight = [%s] (interpolation = "vertex")
    def Scope "protos"
    {
%s
    }
}""" % (", ".join("(0, %g, 0)" % y for y in ROWS), ", ".join("%g" % h for h in ROW_WEIGHT),
        indent(inner, 8)), 4)


def expect_flat(probe):
    out = []
    for x, c, h in zip(XS, COLORS, WEIGHT):
        out.append(((x, 0.0), c if probe != "weight" else (h, h, h)))
    return out


def expect_nested(probe):
    out = []
    for y, rw in zip(ROWS, ROW_WEIGHT):
        for x, c in zip(XS, COLORS):
            out.append(((x, y), c if probe != "rowweight" else (rw, rw, rw)))
    return out


# (name, probe, body, expected [((x, y), rgb)])
CASES = [
    ("attribute", "attribute", flat_body(), expect_flat("attribute")),
    ("object_color", "object_color", flat_body(), expect_flat("object_color")),
    ("weight", "weight", flat_body(), expect_flat("weight")),
    ("nested_color", "attribute", nested_body(), expect_nested("attribute")),
    ("nested_rowweight", "rowweight", nested_body(), expect_nested("rowweight")),
]


def sample(img, x, y):
    px = int(round(RES / 2 + x * PIXELS_PER_UNIT))
    py = int(round(RES / 2 - y * PIXELS_PER_UNIT))
    return img[py - 2:py + 3, px - 2:px + 3, :3].reshape(-1, 3).mean(axis=0)


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else ""
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    problems = []
    cases = [c for c in CASES if pattern in c[0]]
    for name, probe, body, expected in cases:
        source, shader = PROBES[probe]
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(
            SCENE % {"source": source, "probe": shader, "body": body})
        exr = os.path.join(OUT, name + ".exr")
        if os.path.exists(exr):
            os.remove(exr)
        subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                        "--camera", "/world/camera", "--res", str(RES), str(RES),
                        "--output", exr, scene],
                       capture_output=True, text=True, env=env, cwd=OUT)
        buf = oiio.ImageBuf(exr)
        if buf.has_error:
            problems.append(name)
            print("%-14s NO IMAGE" % name)
            continue
        img = buf.get_pixels(oiio.FLOAT)
        wrong = []
        for (x, y), want in expected:
            got = sample(img, x, y)
            if max(abs(g - w) for g, w in zip(got, want)) > 0.02:
                wrong.append("(%g, %g) %.2f %.2f %.2f, expected %.2f %.2f %.2f"
                             % ((x, y) + tuple(got) + tuple(want)))
        print("%-14s %-6s %s" % (name, "ok" if not wrong else "WRONG", "; ".join(wrong[:3])))
        if wrong:
            problems.append(name)
    print("\n%d cases, %d problems" % (len(cases), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
