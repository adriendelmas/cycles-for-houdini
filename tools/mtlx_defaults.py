"""Do the surface shaders keep MaterialX's defaults for the inputs nobody writes?

Hydra forwards only *authored* parameters, and Houdini's material builders
author only what the user touched. Every input left alone therefore takes the
Cycles socket's default, not MaterialX's - and the two disagree more often than
not: `standard_surface` says a specular roughness of 0.2, the principled BSDF
0.5; a subsurface scale of 1 against 0.005.

The test that catches it whatever the input: render a lit sphere twice, once
with no input authored and once with every value input authored at its
MaterialX default. The images must match.

    hython tools/mtlx_defaults.py [nodedef-pattern]

Images and scenes go to tests/materialx/output/defaults/.
"""

import math
import os
import subprocess
import sys

import MaterialX as mx
import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "materialx", "output", "defaults")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

SURFACES = [
    "ND_standard_surface_surfaceshader",
    "ND_open_pbr_surface_surfaceshader",
    "ND_gltf_pbr_surfaceshader",
    "ND_disney_principled",
    "UsdPreviewSurface",
]

# UsdPreviewSurface is not a MaterialX nodedef: its defaults are the USD
# specification's (usdPreviewSurface spec, "Preview Surface" inputs).
PREVIEW_DEFAULTS = [
    ("color3f", "diffuseColor", "(0.18, 0.18, 0.18)"),
    ("color3f", "emissiveColor", "(0, 0, 0)"),
    ("int", "useSpecularWorkflow", "0"),
    ("float", "metallic", "0"),
    ("float", "roughness", "0.5"),
    ("float", "clearcoat", "0"),
    ("float", "clearcoatRoughness", "0.01"),
    ("float", "opacity", "1"),
    ("float", "ior", "1.5"),
]

# Same thresholds as bench_diff.py.
FAIL, FAIL_RELATIVE, FAIL_PERCENT = 1e-3, 1e-2, 0.5

DOC = mx.createDocument()
mx.loadLibraries(["libraries"], mx.getDefaultDataSearchPath(), DOC)


def sphere(rings=24, segments=48):
    points, normals, counts, indices = [], [], [], []
    for r in range(rings + 1):
        theta = math.pi * r / rings
        for s in range(segments):
            phi = 2 * math.pi * s / segments
            n = (math.sin(theta) * math.cos(phi), math.cos(theta), math.sin(theta) * math.sin(phi))
            points.append(n)
            normals.append(n)
    for r in range(rings):
        for s in range(segments):
            a = r * segments + s
            b = r * segments + (s + 1) % segments
            counts.append(4)
            # Counter-clockwise seen from outside, as USD's rightHanded wants:
            # the other order turns the faces inward against outward normals,
            # and the sphere renders black.
            indices += [a, b, b + segments, a + segments]
    fmt = lambda v: "(%.5f, %.5f, %.5f)" % v
    return (", ".join(map(str, counts)), ", ".join(map(str, indices)),
            ", ".join(map(fmt, points)), ", ".join(map(fmt, normals)))


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
        float focalLength = 50
        float horizontalAperture = 36
        float verticalAperture = 36
        float2 clippingRange = (0.1, 1000)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 4.5, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def RectLight "key"
    {
        float inputs:intensity = 20
        float inputs:width = 2
        float inputs:height = 2
        matrix4d xformOp:transform = ( (0.7071,0,-0.7071,0), (0,1,0,0), (0.7071,0,0.7071,0), (2.5, 1.5, 2.5, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def DomeLight "fill"
    {
        float inputs:intensity = 0.2
    }
    def Mesh "ball" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/M>
        int[] faceVertexCounts = [%(counts)s]
        int[] faceVertexIndices = [%(indices)s]
        point3f[] points = [%(points)s]
        normal3f[] normals = [%(normals)s] (interpolation = "vertex")
        uniform token subdivisionScheme = "none"
    }
    def Scope "Materials"
    {
        def Material "M"
        {
            token outputs:%(terminal)s.connect = </world/Materials/M/surf.outputs:%(out)s>
            def Shader "surf"
            {
                uniform token info:id = "%(nodedef)s"
%(inputs)s
                token outputs:%(out)s
            }
        }
    }
}
"""

USD_TYPES = {"float": "float", "color3": "color3f", "vector3": "float3", "vector2": "float2",
             "boolean": "bool", "integer": "int"}


def authored_defaults(nodedef):
    """Every value input of the nodedef, written at its MaterialX default."""
    lines = []
    for inp in nodedef.getActiveInputs():
        usd = USD_TYPES.get(inp.getType())
        text = inp.getValueString()
        if usd is None or not text:
            continue  # geometric inputs (normal, tangent) default to a geomprop
        if usd == "bool":
            literal = "true" if text.lower() == "true" else "false"
        elif usd in ("float", "int"):
            literal = text
        else:
            literal = "(%s)" % text
        lines.append("                %s inputs:%s = %s" % (usd, inp.getName(), literal))
    return "\n".join(lines)


def render(name, nodedef_name, inputs, geometry, env):
    counts, indices, points, normals = geometry
    scene = os.path.join(OUT, name + ".usda")
    open(scene, "w", encoding="utf-8").write(SCENE % {
        "counts": counts, "indices": indices, "points": points, "normals": normals,
        "nodedef": nodedef_name, "inputs": inputs,
        "terminal": "surface" if nodedef_name == "UsdPreviewSurface" else "mtlx:surface",
        "out": "surface" if nodedef_name == "UsdPreviewSurface" else "out"})
    exr = os.path.join(OUT, name + ".exr")
    if os.path.exists(exr):
        os.remove(exr)
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                    "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                    "--res", "96", "96", "--output", exr, scene],
                   capture_output=True, text=True, env=env, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)


BLOCK = 8


def blocks(img):
    """8x8 block means: path-tracing noise averages out, the shape of a
    highlight - which is what a wrong roughness changes - does not."""
    h, w = img.shape[0] // BLOCK, img.shape[1] // BLOCK
    return img[:h * BLOCK, :w * BLOCK, :3].reshape(h, BLOCK, w, BLOCK, 3).mean(axis=(1, 3))


def failing_percent(a, b):
    a, b = blocks(a), blocks(b)
    d = np.abs(a - b)
    scale = np.maximum(np.maximum(np.abs(a), np.abs(b)), 1e-6)
    return 100.0 * ((d > 2 * FAIL) & (d / scale > 2 * FAIL_RELATIVE)).any(axis=-1).mean()


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else ""
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    geometry = sphere()
    problems = 0
    for nodedef_name in SURFACES:
        if pattern not in nodedef_name:
            continue
        if nodedef_name == "UsdPreviewSurface":
            short = "preview_surface"
            defaults = chr(10).join("                %s inputs:%s = %s" % d for d in PREVIEW_DEFAULTS)
        else:
            short = nodedef_name[3:].replace("_surfaceshader", "")
            defaults = authored_defaults(DOC.getNodeDef(nodedef_name))
        bare = render(short + "_bare", nodedef_name, "", geometry, env)
        full = render(short + "_defaults", nodedef_name, defaults, geometry, env)
        if bare is None or full is None:
            print("%-22s NO IMAGE" % short)
            problems += 1
            continue
        percent = failing_percent(bare, full)
        state = "ok" if percent <= FAIL_PERCENT else "DIFFERS"
        if state != "ok":
            problems += 1
        # The sphere itself, not the background, must be lit: a black sphere
        # compares equal to a black sphere and proves nothing.
        lit = bare[36:60, 36:60, :3].mean()
        if lit < 0.02:
            state = "DARK"
            problems += 1
        print("%-22s %-8s %.2f%% of blocks differ, sphere %.4f vs %.4f"
              % (short, state, percent, lit, full[36:60, 36:60, :3].mean()))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
