"""Does the USD texture chain read a texture where Karma reads it?

A quad facing the camera, a UsdPreviewSurface whose emission is a
UsdUVTexture - read through a UsdPrimvarReader of `st`, optionally through a
UsdTransform2d - and whose diffuse is black, so the image shows the texture as
it is. The texture has one colour per corner (blue top-left, white top-right,
red bottom-left, green bottom-right), so a flipped, mirrored or shifted read
shows in the quad's quarters, compared between Cycles and Karma.

Cases: the plain read; a 2x tiling with repeat wrap; a quarter-turn
rotation; a translation; scale and bias on the texture; an 8-bit PNG read
as sRGB, as raw and with no colour space (auto); the same PNG through a
MaterialX image, with and without a colour space; two UDIM tiles; a
left-handed subdivided grid with UVs per corner and per vertex.

    hython tools/bench_usdtex.py

Scenes and images go to tests/usdtex/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "usdtex", "output")
RES = 96
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
        float horizontalAperture = 20
        float verticalAperture = 20
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0.5, 0.5, 10, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def Mesh "quad" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/M>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-0.5,-0.5,0), (1.5,-0.5,0), (1.5,1.5,0), (-0.5,1.5,0)]
        texCoord2f[] primvars:st = [(0,0), (1,0), (1,1), (0,1)] (interpolation = "faceVarying")
        uniform token subdivisionScheme = "none"
    }
    def Scope "Materials"
    {
        def Material "M"
        {
            token outputs:surface.connect = </world/Materials/M/surf.outputs:surface>
            def Shader "surf"
            {
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0, 0, 0)
                float inputs:roughness = 1
                color3f inputs:emissiveColor.connect = </world/Materials/M/tex.outputs:rgb>
                token outputs:surface
            }
            def Shader "st"
            {
                uniform token info:id = "UsdPrimvarReader_float2"
                string inputs:varname = "st"
                float2 outputs:result
            }
%(transform)s
            def Shader "tex"
            {
                uniform token info:id = "UsdUVTexture"
                asset inputs:file = @%(file)s@
                float2 inputs:st.connect = </world/Materials/M/%(stsource)s>
%(texinputs)s
                float3 outputs:rgb
            }
        }
    }
}
"""

TRANSFORM = """            def Shader "xf"
            {
                uniform token info:id = "UsdTransform2d"
                float2 inputs:in.connect = </world/Materials/M/st.outputs:result>
%s
                float2 outputs:result
            }"""

CASES = [
    ("plain", "corners.exr", None, []),
    ("tiled_repeat", "corners.exr", ["float2 inputs:scale = (2, 2)"],
     ['token inputs:wrapS = "repeat"', 'token inputs:wrapT = "repeat"']),
    ("rotate_90", "corners.exr", ["float inputs:rotation = 90"],
     ['token inputs:wrapS = "repeat"', 'token inputs:wrapT = "repeat"']),
    ("translate", "corners.exr", ["float2 inputs:translation = (0.5, 0)"],
     ['token inputs:wrapS = "repeat"', 'token inputs:wrapT = "repeat"']),
    # No wrap authored: USD's default is useMetadata, and with no metadata in
    # the file, black outside the image.
    ("outside_default", "corners.exr", ["float2 inputs:translation = (0.5, 0)"], []),
    ("scale_bias", "corners.exr", None,
     ["float4 inputs:scale = (0.5, 0.5, 0.5, 1)", "float4 inputs:bias = (0.25, 0, 0.1, 0)"]),
    ("png_srgb", "corners.png", None, ['token inputs:sourceColorSpace = "sRGB"']),
    ("png_raw", "corners.png", None, ['token inputs:sourceColorSpace = "raw"']),
    # Nothing authored: USD's auto, an 8 bit file read as sRGB.
    ("png_auto", "corners.png", None, []),
    # A MaterialX image instead, its colour space as metadata on the file
    # input, as Houdini writes it - and with none, auto, the common case.
    ("mtlx_png_srgb", "corners.png", "MTLX", ' (\n                    colorSpace = "srgb_texture"\n                )'),
    ("mtlx_png_auto", "corners.png", "MTLX", ""),
    # Two UDIM tiles, one colour each, the quad's u running over both; the
    # second spelling is the one Houdini writes.
    ("udim", "tile.<UDIM>.exr", ["float2 inputs:scale = (2, 1)"], []),
    ("udim_houdini", "tile.%(UDIM)d.exr", ["float2 inputs:scale = (2, 1)"], []),
    # A left-handed subdivided grid, UVs per corner and per vertex.
    ("left_subd_corner_uv", "corners.exr", "LEFT", "faceVarying"),
    ("left_subd_vertex_uv", "corners.exr", "LEFT", "vertex"),
]

SCENE_MTLX_MATERIAL = '''            token outputs:mtlx:surface.connect = </world/Materials/M/unlit.outputs:out>
            def Shader "unlit"
            {
                uniform token info:id = "ND_surface_unlit"
                color3f inputs:emission_color.connect = </world/Materials/M/img.outputs:out>
                token outputs:out
            }
            def Shader "img"
            {
                uniform token info:id = "ND_image_color3"
                asset inputs:file = @%s@%s
                color3f outputs:out
            }'''


def mtlx_scene(file, colorspace):
    text = SCENE % {"file": file, "transform": "", "stsource": "st.outputs:result",
                    "texinputs": ""}
    start = text.index("            token outputs:surface.connect")
    end = text.index('            def Shader "st"')
    return text[:start] + SCENE_MTLX_MATERIAL % (file, colorspace) + "\n" + text[end:]


def left_handed_scene(interpolation):
    """The plain case on a 2 x 2 grid wound clockwise (`leftHanded`, as
    Houdini writes meshes) and subdivided: Cycles gets each face reversed,
    and the corner UVs must follow."""
    points = [(x - 0.5, y - 0.5) for y in range(3) for x in range(3)]
    faces = [(0, 3, 4, 1), (1, 4, 5, 2), (3, 6, 7, 4), (4, 7, 8, 5)]
    indices = [i for f in faces for i in f]
    per_vertex = [(x / 2.0, y / 2.0) for y in range(3) for x in range(3)]
    st = [per_vertex[i] for i in indices] if interpolation == "faceVarying" else per_vertex
    mesh = "\n".join([
        "        int[] faceVertexCounts = [4, 4, 4, 4]",
        "        int[] faceVertexIndices = [%s]" % ", ".join(str(i) for i in indices),
        "        point3f[] points = [%s]" % ", ".join("(%g,%g,0)" % p for p in points),
        '        texCoord2f[] primvars:st = [%s] (interpolation = "%s")'
        % (", ".join("(%g,%g)" % p for p in st), interpolation),
        '        uniform token orientation = "leftHanded"',
        '        uniform token subdivisionScheme = "catmullClark"',
        '        uniform token faceVaryingLinearInterpolation = "all"'])
    text = SCENE % {"file": "corners.exr", "transform": "", "stsource": "st.outputs:result",
                    "texinputs": ""}
    start = text.index("        int[] faceVertexCounts")
    end = text.index('        uniform token subdivisionScheme = "none"')
    return text[:start] + mesh + text[end + len('        uniform token subdivisionScheme = "none"'):]


def write_textures():
    px = np.zeros((8, 8, 3), dtype=np.float32)
    for (r, c), colour in CORNERS.items():
        px[r * 4:(r + 1) * 4, c * 4:(c + 1) * 4] = colour
    for name, fmt in (("corners.exr", oiio.FLOAT), ("corners.png", oiio.UINT8)):
        spec = oiio.ImageSpec(8, 8, 3, fmt)
        buf = oiio.ImageBuf(spec)
        buf.set_pixels(oiio.ROI(0, 8, 0, 8), px)
        buf.write(os.path.join(OUT, name))
    for tile, colour in ((1001, CORNERS[(1, 0)]), (1002, CORNERS[(1, 1)])):
        buf = oiio.ImageBuf(oiio.ImageSpec(8, 8, 3, oiio.FLOAT))
        oiio.ImageBufAlgo.fill(buf, colour)
        buf.write(os.path.join(OUT, "tile.%d.exr" % tile))


def render(renderer, scene, exr):
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    # The colour spaces need OpenColorIO, which HOUDINI_PACKAGE_SKIP turns off:
    # Houdini's own config, for both renderers.
    if not env.get("OCIO"):
        env["OCIO"] = os.path.join(os.path.dirname(HFS), "packages", "ocio",
                                   "houdini-config-v3.0.0_aces-v2.0_ocio-v2.5.ocio")
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer, "--frame", "1",
                    "--frame-count", "1", "--camera", "/world/camera", "--res", str(RES), str(RES),
                    "--output", exr, scene], capture_output=True, text=True, env=env, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)[..., :3]


def quarters(img):
    """Mean colour of the quad's four quarters, sampled away from their
    borders: the quad fills the middle half of the image."""
    q = RES // 4
    out = []
    for r in range(2):
        for c in range(2):
            y0, x0 = q + r * q, q + c * q
            out.append(img[y0 + q // 4:y0 + 3 * q // 4, x0 + q // 4:x0 + 3 * q // 4].reshape(-1, 3).mean(axis=0))
    return np.array(out)


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    write_textures()
    problems = []
    for name, file, xform, texinputs in CASES:
        scene = os.path.join(OUT, name + ".usda")
        if xform == "MTLX":
            open(scene, "w", encoding="utf-8").write(mtlx_scene(file, texinputs))
        elif xform == "LEFT":
            open(scene, "w", encoding="utf-8").write(left_handed_scene(texinputs))
        else:
            transform = TRANSFORM % "\n".join("                " + l for l in xform) if xform else ""
            open(scene, "w", encoding="utf-8").write(SCENE % {
                "file": file, "transform": transform,
                "stsource": "xf.outputs:result" if xform else "st.outputs:result",
                "texinputs": "\n".join("                " + l for l in texinputs)})
        cyc = render("HdCyclesPlugin", scene, os.path.join(OUT, name + "_cycles.exr"))
        kar = render("BRAY_HdKarma", scene, os.path.join(OUT, name + "_karma.exr"))
        if cyc is None or kar is None:
            problems.append(name)
            print("%-13s NO IMAGE" % name)
            continue
        a, b = quarters(cyc), quarters(kar)
        worst = float(np.abs(a - b).max())
        ok = worst <= TOL
        print("%-13s %s  worst quarter difference %.3f" % (name, "ok   " if ok else "DIFFERS", worst))
        if not ok:
            for i in range(4):
                print("      quarter %d  cycles %s  karma %s" % (i, np.round(a[i], 3), np.round(b[i], 3)))
            problems.append(name)
    print("\n%d cases, %d problems" % (len(CASES), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
