"""Does an anisotropic metal stretch its highlight as Karma does?

A MaterialX conductor's roughness is two alphas, along the tangent (the first
UV set's) and the bitangent; Cycles' metallic BSDF takes one roughness and an
anisotropy (K-91). A plane with UVs along X, seen from (0, -3, 5), reflects a
small sphere light at (0, 3, 5) at its centre. The highlight's spread along
the image's x and y - intensity-weighted standard deviations - and its mean
are compared between Cycles and Karma, for an isotropic roughness, a
vector2 value both ways (alphas 7.5 apart: Cycles caps the ratio at 10) and a
roughness wired from `roughness_anisotropy`.

    hython tools/bench_aniso.py

Scenes and images go to tests/aniso/output/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio
from pxr import Gf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "aniso", "output")
RES = 160


def camera_matrix():
    view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(0, -3, 5), Gf.Vec3d(0, 0, 0), Gf.Vec3d(0, 0, 1))
    m = view.GetInverse()
    return "( %s )" % ", ".join("(%s)" % ", ".join("%.6f" % m[r][c] for c in range(4))
                                for r in range(4))


SCENE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Z"
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
        float focalLength = 35
        float horizontalAperture = 20
        float verticalAperture = 20
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = %(camera)s
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def SphereLight "light"
    {
        float inputs:radius = 0.15
        float inputs:intensity = 300
        float3 xformOp:translate = (0, 3, 5)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
    def Mesh "plane" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/M>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-4, -4, 0), (4, -4, 0), (4, 4, 0), (-4, 4, 0)]
        normal3f[] normals = [(0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1)] (interpolation = "vertex")
        texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (interpolation = "vertex")
        uniform token subdivisionScheme = "none"
    }
    def Scope "Materials"
    {
        def Material "M"
        {
            token outputs:mtlx:surface.connect = </world/Materials/M/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_surface"
                token inputs:bsdf.connect = </world/Materials/M/metal.outputs:out>
                token outputs:out
            }
            def Shader "metal"
            {
                uniform token info:id = "%(bsdf)s"
%(roughness)s
                token outputs:out
            }
%(extra)s
        }
    }
}
"""

CASES = [
    ("isotropic", '                float2 inputs:roughness = (0.1, 0.1)', ""),
    ("value_x", '                float2 inputs:roughness = (0.04, 0.3)', ""),
    ("value_y", '                float2 inputs:roughness = (0.3, 0.04)', ""),
    # A reflecting dielectric - a clear coat - is a principled in Cycles,
    # with the same anisotropy.
    ("dielectric", '                float2 inputs:roughness = (0.04, 0.3)', "",
     "ND_dielectric_bsdf"),
    ("wired", '                float2 inputs:roughness.connect = </world/Materials/M/ra.outputs:out>',
     """            def Shader "ra"
            {
                uniform token info:id = "ND_roughness_anisotropy"
                float inputs:roughness = 0.4
                float inputs:anisotropy = 0.8
                float2 outputs:out
            }"""),
]


def render(name, renderer, scene):
    exr = os.path.join(OUT, "%s_%s.exr" % (name, renderer))
    if os.path.exists(exr):
        os.remove(exr)
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer,
                    "--frame", "1", "--frame-count", "1", "--output", exr, scene],
                   capture_output=True, text=True, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)[:, :, :3].mean(axis=2)


def spread(img):
    """Mean, and the intensity-weighted standard deviations along x and y."""
    w = np.clip(img - np.median(img), 0, None)
    ys, xs = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    total = w.sum()
    mx, my = (w * xs).sum() / total, (w * ys).sum() / total
    sx = np.sqrt((w * (xs - mx) ** 2).sum() / total)
    sy = np.sqrt((w * (ys - my) ** 2).sum() / total)
    return img.mean(), sx, sy


def main():
    os.makedirs(OUT, exist_ok=True)
    problems = 0
    for case in CASES:
        name, roughness, extra = case[:3]
        bsdf = case[3] if len(case) > 3 else "ND_conductor_bsdf"
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(SCENE % dict(
            res=RES, camera=camera_matrix(), roughness=roughness, extra=extra, bsdf=bsdf))
        cyc = render(name, "HdCyclesPlugin", scene)
        kar = render(name, "BRAY_HdKarma", scene)
        if cyc is None or kar is None:
            print("%-10s NO IMAGE" % name)
            problems += 1
            continue
        (cm, cx, cy), (km, kx, ky) = spread(cyc), spread(kar)
        ratio_c, ratio_k = cx / cy, kx / ky
        ok = abs(ratio_c - ratio_k) <= 0.2 * ratio_k and abs(cm - km) <= 0.15 * km
        print("%-10s %s  x/y spread cycles %.2f karma %.2f, mean cycles %.4f karma %.4f"
              % (name, "ok     " if ok else "DIFFERS", ratio_c, ratio_k, cm, km))
        problems += 0 if ok else 1
    print("\n%d cases, %d problems" % (len(CASES), problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
