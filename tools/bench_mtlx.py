"""Rend un materiau MaterialX par noeud teste et verifie ce qui en sort.

Le banc des noeuds Cycles (`bench_render.py`) ne dit que « pas noir » ; ici la
valeur compte, parce qu'une traduction peut aboutir a une image plausible et
fausse : un `contrast` sur une couleur qui passe par le noeud scalaire de
Cycles en ressort gris, et une verification par la seule moyenne l'aurait
laisse passer.

Chaque cas est un plan eclaire de face, le noeud teste branche sur la couleur
de base d'un `standard_surface` sans speculaire. Le rapport donne les trois
moyennes RVB ramenees a la couleur de base ; l'attendu, quand il est connu, est
verifie a 2 % pres.

    hython tools/bench_mtlx.py [motif]

`CYCLES_BENCH_TEXTURE` ajoute les trois cas a texture, qui demandent un fichier.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "usd", "bench-mtlx")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

TEX = os.environ.get("CYCLES_BENCH_TEXTURE", "")

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
        float verticalAperture = 24
        float2 clippingRange = (0.1, 1000)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 6, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def RectLight "key"
    {
        float inputs:intensity = 40
        float inputs:width = 8
        float inputs:height = 8
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 6, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def Mesh "obj" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/M>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-2,-2,0), (2,-2,0), (2,2,0), (-2,2,0)]
        texCoord2f[] primvars:st = [(0,0), (1,0), (1,1), (0,1)] (
            interpolation = "faceVarying"
        )
        uniform token subdivisionScheme = "none"
    }
    def Scope "Materials"
    {
        def Material "M"
        {
            token outputs:mtlx:surface.connect = </world/Materials/M/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                float inputs:specular = 0
                color3f inputs:base_color.connect = </world/Materials/M/probe.outputs:out>
                token outputs:out
            }
            def Shader "probe"
            {
                %s
            }
        }
    }
}
"""

# Le facteur entre une couleur de base et la moyenne rendue, releve sur un cas
# dont la reponse est connue - une constante a un.
GAIN = 5.544

# (nom, corps du prim `probe`, couleur attendue ou None)
CASES = [
    ("dot", [
        'uniform token info:id = "ND_dot_color3"',
        "color3f inputs:in = (0.9, 0.2, 0.1)",
        "color3f outputs:out",
    ], (0.9, 0.2, 0.1)),
    ("convert", [
        'uniform token info:id = "ND_convert_float_color3"',
        "float inputs:in = 0.7",
        "color3f outputs:out",
    ], (0.7, 0.7, 0.7)),
    ("constant_color", [
        'uniform token info:id = "ND_constant_color3"',
        "color3f inputs:value = (0.1, 0.8, 0.3)",
        "color3f outputs:out",
    ], (0.1, 0.8, 0.3)),
    ("constant_float", [
        'uniform token info:id = "ND_constant_float"',
        "float inputs:value = 0.6",
        "float outputs:out",
    ], (0.6, 0.6, 0.6)),
    ("saturate", [
        'uniform token info:id = "ND_saturate_color3"',
        "color3f inputs:in = (0.9, 0.2, 0.1)",
        "float inputs:amount = 0.2",
        "color3f outputs:out",
    ], (0.900, 0.760, 0.740)),
    ("contrast", [
        'uniform token info:id = "ND_contrast_color3"',
        "color3f inputs:in = (0.9, 0.2, 0.1)",
        "float inputs:amount = 2",
        "float inputs:pivot = 0.5",
        "color3f outputs:out",
    ], (1.3, 0.0, 0.0)),
    ("logical_not", [
        'uniform token info:id = "ND_logical_not"',
        "bool inputs:in = 0",
        "bool outputs:out",
    ], (1.0, 1.0, 1.0)),
]

TEXTURED = [
    ("image", "ND_image_color3"),
    ("hextiledimage", "ND_hextiledimage_color3"),
    ("gltf_image", "ND_gltf_image_color3_color3_1_0"),
]

env = dict(os.environ)
env["PATH"] = HFS + ";" + env["PATH"]


def render(name, body):
    scene = os.path.join(OUT, name + ".usda")
    open(scene, "w", encoding="utf-8").write(SCENE % ("\n                ".join(body)))
    exr = os.path.join(OUT, name + ".exr")
    if os.path.exists(exr):
        os.remove(exr)
    run = subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                          "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                          "--res", "120", "90", "--output", exr, scene],
                         capture_output=True, text=True, env=env, cwd=OUT)
    log = (run.stdout or "") + (run.stderr or "")
    warns = [l.strip() for l in log.splitlines()
             if "MaterialX" in l and ("no Cycles node" in l or "no input" in l
                                      or "has no output" in l)]
    return exr, warns, log


def averages(exr):
    out = subprocess.run([os.path.join(HFS, "hoiiotool.exe"), "--stats", exr],
                         capture_output=True, text=True, env=env).stdout or ""
    line = [l for l in out.splitlines() if "Stats Avg" in l]
    if not line:
        return None
    return [float(v) for v in line[0].split(":")[1].split()[:3]]


def main():
    cases = list(CASES)
    if TEX:
        for name, nodedef in TEXTURED:
            cases.append((name, [
                'uniform token info:id = "%s"' % nodedef,
                "asset inputs:file = @%s@" % TEX,
                "color3f outputs:out",
            ], None))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if only:
        cases = [c for c in cases if only in c[0]]

    print("%-18s %-9s %s" % ("noeud", "etat", "detail"))
    problems = []
    for name, body, expected in cases:
        exr, warns, log = render(name, body)
        if not os.path.exists(exr):
            state = "PAS D'IMAGE"
            detail = (log.strip().splitlines() or [""])[-1][:60]
        elif warns:
            state, detail = "AVERTI", warns[0].split("WARNING:")[-1].strip()[:70]
        else:
            avg = averages(exr)
            if avg is None:
                state, detail = "ILLISIBLE", ""
            else:
                got = tuple(round(v / GAIN, 3) for v in avg)
                detail = "RVB %.3f %.3f %.3f" % got
                if expected is None:
                    state = "ok" if max(avg) > 1e-6 else "NOIRE"
                elif all(abs(g - e) <= 0.02 for g, e in zip(got, expected)):
                    state = "ok"
                else:
                    state = "FAUX"
                    detail += "  attendu %.3f %.3f %.3f" % expected
        if state != "ok":
            problems.append((name, state, detail))
        print("%-18s %-9s %s" % (name, state, detail))

    print("\n%d noeuds rendus, %d problemes" % (len(cases), len(problems)))
    for name, state, detail in problems:
        print("   %-16s %-12s %s" % (name, state, detail))


if __name__ == "__main__":
    main()
