"""Do render vars reach the Cycles pass they name, with the value they should?

One husk render of two diffuse spheres under a normalized distant light, with
a render product holding every kind of render var the delegate resolves: the
beauty, a Cycles pass by its own name, a Karma light path expression, a Karma
component name, depth, a cryptomatte layer and a shader AOV written by an
`aov_output` node wired as a pass-through. The scene is diffuse only, so the
diffuse components in Karma's convention must equal the beauty, and in
Cycles' (light only, divided by the surface colour) the beauty over 0.8.

    hython tools/bench_aovs.py

Scene and image go to tests/aovs/output/.
"""

import os
import subprocess
import sys

import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "aovs", "output")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

# (prim name, dataType, sourceType, sourceName, husk name)
VARS = [
    ("beauty", "color4f", "raw", "color", "C"),
    ("cycles_dd", "color3f", "raw", "diffuse_direct", "dd"),
    ("lpe_diffuse", "color3f", "lpe", "C<RD>.*L", "combineddiffuse"),
    ("karma_dd", "color3f", "raw", "direct_diffuse", "direct_diffuse"),
    ("crypto", "color4f", "raw", "CryptoObject00", "CryptoObject00"),
    ("shader_aov", "color3f", "raw", "myaov", "myaov"),
    ("depth", "float", "raw", "depth", "Pz"),
]

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
        float focalLength = 35
        float horizontalAperture = 36
        float verticalAperture = 36
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 6, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def DistantLight "sun"
    {
        float inputs:intensity = 3
        bool inputs:normalize = 1
    }
    def Sphere "a" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/M>
        double radius = 0.8
        double3 xformOp:translate = (-1, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
    def Sphere "b" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/M>
        double radius = 0.8
        double3 xformOp:translate = (1, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
    def Material "M"
    {
        token outputs:cycles:surface.connect = </world/M/aov.outputs:closure>
        def Shader "d"
        {
            uniform token info:id = "cycles_diffuse_bsdf"
            color3f inputs:color = (0.8, 0.8, 0.8)
            token outputs:BSDF
        }
        def Shader "aov"
        {
            uniform token info:id = "cycles_aov_output"
            string inputs:name = "myaov"
            color3f inputs:color = (0.1, 0.2, 0.3)
            token inputs:surface.connect = </world/M/d.outputs:BSDF>
            token outputs:closure
        }
    }
}
def Scope "Render"
{
    def RenderSettings "settings"
    {
        rel camera = </world/camera>
        int2 resolution = (64, 64)
        rel products = </Render/product>
    }
    def RenderProduct "product"
    {
        token productType = "raster"
        token productName = "aovs.exr"
        rel orderedVars = [%(order)s]
    }
    def Scope "Vars"
    {
%(vars)s    }
}
"""

VAR = """        def RenderVar "%s" (
            prepend apiSchemas = ["HuskRenderVarAPI"]
        )
        {
            uniform token dataType = "%s"
            string driver:parameters:aov:husk:name = "%s"
            uniform string sourceName = "%s"
            uniform token sourceType = "%s"
        }
"""


def read_layers(path):
    layers = {}
    inp = oiio.ImageInput.open(path)
    if inp is None:
        return layers
    sub = 0
    while inp.seek_subimage(sub, 0):
        spec = inp.spec()
        layers[spec.get_string_attribute("name")] = inp.read_image(oiio.FLOAT)
        sub += 1
    inp.close()
    return layers


def main():
    scene = os.path.join(OUT, "aovs.usda")
    open(scene, "w", encoding="utf-8").write(SCENE % {
        "order": ", ".join("</Render/Vars/%s>" % v[0] for v in VARS),
        "vars": "".join(VAR % (n, dt, hn, sn, st) for n, dt, st, sn, hn in VARS)})
    exr = os.path.join(OUT, "aovs.exr")
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                    "--settings", "/Render/settings", scene],
                   capture_output=True, text=True, env=env, cwd=OUT)
    layers = read_layers(exr)
    if not layers:
        print("NO IMAGE")
        sys.exit(1)

    a, b, bg = (32, 18), (32, 46), (5, 5)

    def px(layer, at, c=0):
        return float(layers[layer][at[0], at[1], c]) if layer in layers else float("nan")

    beauty = px("C", a)
    checks = [
        ("beauty lit", beauty > 0.3, "C %.3f" % beauty),
        ("Cycles convention", abs(px("dd", a) - beauty / 0.8) < 0.01,
         "diffuse_direct %.4f, expected beauty / 0.8 = %.4f" % (px("dd", a), beauty / 0.8)),
        ("Karma LPE", abs(px("combineddiffuse", a) - beauty) < 0.005,
         "C<RD>.*L %.4f, expected the beauty %.4f" % (px("combineddiffuse", a), beauty)),
        ("Karma component", abs(px("direct_diffuse", a) - beauty) < 0.005,
         "direct_diffuse %.4f, expected the beauty %.4f" % (px("direct_diffuse", a), beauty)),
        ("cryptomatte ids", px("CryptoObject00", a) != px("CryptoObject00", b)
         and px("CryptoObject00", a, 1) > 0.99,
         "ids %g and %g, coverage %.2f" % (px("CryptoObject00", a), px("CryptoObject00", b),
                                          px("CryptoObject00", a, 1))),
        ("shader AOV", all(abs(px("myaov", a, c) - v) < 0.001 for c, v in enumerate((0.1, 0.2, 0.3))),
         "myaov %.3f %.3f %.3f" % tuple(px("myaov", a, c) for c in range(3))),
        ("depth", 4.5 < px("Pz", a) < 6.0 and px("Pz", bg) > 1e6,
         "Pz %.3f on the sphere, %g behind" % (px("Pz", a), px("Pz", bg))),
    ]
    problems = 0
    for name, ok, detail in checks:
        print("%-18s %-6s %s" % (name, "ok" if ok else "WRONG", detail))
        problems += not ok
    print("\n%d checks, %d problems" % (len(checks), problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
