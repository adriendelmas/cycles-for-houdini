"""MaterialX hair bench: each translation against a known result.

    python tools/bench_hair.py [renderer]

The renderer defaults to `HdCyclesPlugin` (CPU), for deterministic images.

Each pair must render the same image if the translation is exact:

  mx_abs   / cy_native : the MaterialX Chiang BSDF against Cycles' native
                         principled hair, at equal absorption and roughness;
  mx_mel   / mx_abs    : d'Eon's melanin against the absorption it should
                         produce, computed by hand;
  mx_color / cy_direct : absorption from a color against Cycles' native
                         color parametrization;
  mx_rval  / mx_abs    : a roughness written as a value (variance) against
                         the same one passed through chiang_hair_roughness
                         (beta).
"""

import math
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tests", "materialx", "hair")
os.makedirs(OUT, exist_ok=True)
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")

# Expected absorption for melanin 0.5 / redness 0.5 and the default colors.
m = -math.log(max(1.0 - 0.5, 1e-4))
eu = [-math.log(c) for c in (0.657704, 0.498077, 0.254107)]
ph = [-math.log(c) for c in (0.829444, 0.67032, 0.349938)]
ABS = [m * 0.5 * a + m * 0.5 * b for a, b in zip(eu, ph)]
ABS_TXT = "(%.6f, %.6f, %.6f)" % tuple(ABS)

# The same roughness beta = 0.3, expressed as variance/scale the way MaterialX
# hands it to the BSDF.
b = 0.3
V = (0.726 * b + 0.812 * b * b + 3.7 * b ** 20) ** 2
S = 0.265 * b + 1.194 * b * b + 5.372 * b ** 22


def strands():
    counts, points, widths = [], [], []
    nx, nz, seg = 40, 6, 10
    for i in range(nx):
        for k in range(nz):
            x0 = -1.6 + 3.2 * (i + 0.5) / nx
            z0 = -0.3 + 0.6 * (k + 0.5) / nz
            counts.append(seg)
            for j in range(seg):
                t = j / (seg - 1)
                y = 1.6 - 3.2 * t
                x = x0 + 0.08 * math.sin(6.0 * t + i * 0.7)
                points.append("(%.4f, %.4f, %.4f)" % (x, y, z0))
    return counts, points


HEAD = """#usda 1.0
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
        float verticalAperture = 36
        float2 clippingRange = (0.1, 1000)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 6, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def RectLight "key"
    {
        float inputs:intensity = 30
        float inputs:width = 6
        float inputs:height = 6
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (2, 2, 6, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def RectLight "back"
    {
        float inputs:intensity = 30
        float inputs:width = 6
        float inputs:height = 6
        matrix4d xformOp:transform = ( (-1,0,0,0), (0,1,0,0), (0,0,-1,0), (0, 1, -6, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def BasisCurves "hair" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/M>
        uniform token type = "linear"
        int[] curveVertexCounts = [%s]
        point3f[] points = [%s]
        float[] widths = [0.012] (interpolation = "constant")
    }
    def Scope "Materials"
    {
        def Material "M"
        {
%s
        }
    }
}
"""

ROUGH = """            def Shader "rough"
            {
                uniform token info:id = "ND_chiang_hair_roughness"
                float inputs:longitudinal = 0.3
                float inputs:azimuthal = 0.3
                float2 outputs:roughness_R
                float2 outputs:roughness_TT
                float2 outputs:roughness_TRT
            }"""


def mx_material(absorption_lines, extra_nodes, roughness_lines=None):
    if roughness_lines is None:
        roughness_lines = """                float2 inputs:roughness_R.connect = </world/Materials/M/rough.outputs:roughness_R>
                float2 inputs:roughness_TT.connect = </world/Materials/M/rough.outputs:roughness_TT>
                float2 inputs:roughness_TRT.connect = </world/Materials/M/rough.outputs:roughness_TRT>"""
        extra_nodes = ROUGH + "\n" + extra_nodes
    return """            token outputs:mtlx:surface.connect = </world/Materials/M/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_surface"
                token inputs:bsdf.connect = </world/Materials/M/hair.outputs:out>
                token outputs:out
            }
            def Shader "hair"
            {
                uniform token info:id = "ND_chiang_hair_bsdf"
%s
%s
                token outputs:out
            }
%s""" % (absorption_lines, roughness_lines, extra_nodes)


def cy_material(param_lines):
    return """            token outputs:cycles:surface.connect = </world/Materials/M/hair.outputs:BSDF>
            def Shader "hair"
            {
                uniform token info:id = "cycles_principled_hair_bsdf"
                token inputs:model = "Chiang"
                float inputs:roughness = 0.3
                float inputs:radial_roughness = 0.3
                float inputs:offset = 0
                float inputs:ior = 1.55
%s
                token outputs:BSDF
            }""" % param_lines


VARIANTS = {
    "mx_abs": mx_material(
        "                float3 inputs:absorption_coefficient = %s" % ABS_TXT, ""),
    "mx_mel": mx_material(
        "                float3 inputs:absorption_coefficient.connect = "
        "</world/Materials/M/mel.outputs:absorption>",
        """            def Shader "mel"
            {
                uniform token info:id = "ND_deon_hair_absorption_from_melanin"
                float inputs:melanin_concentration = 0.5
                float inputs:melanin_redness = 0.5
                float3 outputs:absorption
            }"""),
    "mx_color": mx_material(
        "                float3 inputs:absorption_coefficient.connect = "
        "</world/Materials/M/col.outputs:absorption>",
        """            def Shader "col"
            {
                uniform token info:id = "ND_chiang_hair_absorption_from_color"
                color3f inputs:color = (0.6, 0.3, 0.1)
                float inputs:azimuthal_roughness = 0.3
                float3 outputs:absorption
            }"""),
    "mx_rval": mx_material(
        "                float3 inputs:absorption_coefficient = %s" % ABS_TXT, "",
        "                float2 inputs:roughness_R = (%.6f, %.6f)" % (V, S)),
    "cy_native": cy_material(
        "                token inputs:parametrization = \"Absorption coefficient\"\n"
        "                float3 inputs:absorption_coefficient = %s" % ABS_TXT),
    "cy_direct": cy_material(
        "                token inputs:parametrization = \"Direct coloring\"\n"
        "                color3f inputs:color = (0.6, 0.3, 0.1)"),
}

PAIRS = [("mx_abs", "cy_native"), ("mx_mel", "mx_abs"), ("mx_color", "cy_direct"),
         ("mx_rval", "mx_abs")]


def main():
    counts, points = strands()
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    print("expected absorption (melanin) :", ABS_TXT)
    print("roughness as variance :","(%.6f, %.6f)" % (V, S))
    renderer = sys.argv[1] if len(sys.argv) > 1 else "HdCyclesPlugin"
    for name, material in VARIANTS.items():
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(
            HEAD % (", ".join(map(str, counts)), ", ".join(points), material))
        exr = os.path.join(OUT, name + ".exr")
        if os.path.exists(exr):
            os.remove(exr)
        run = subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer,
                              "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                              "--res", "240", "240", "--output", exr, scene],
                             capture_output=True, text=True, env=env, cwd=OUT)
        log = (run.stdout or "") + (run.stderr or "")
        warns = [l.split("WARNING:")[-1].strip() for l in log.splitlines() if "WARNING" in l]
        stats = subprocess.run([os.path.join(HFS, "hoiiotool.exe"), "--stats", exr],
                               capture_output=True, text=True, env=env).stdout or ""
        avg = [l for l in stats.splitlines() if "Stats Avg" in l]
        print("%-10s %s" % (name, avg[0].split(":")[1].strip()[:44] if avg else "NO IMAGE"))
        for w in warns[:3]:
            print("           ! " + w[:110])
    print()
    # A black image against a black image passes `--diff` just as well as two
    # correct images: each render must first contain something.
    problems = 0
    for a, bname in PAIRS:
        r = subprocess.run([os.path.join(HFS, "hoiiotool.exe"), "--diff",
                            os.path.join(OUT, a + ".exr"), os.path.join(OUT, bname + ".exr")],
                           capture_output=True, text=True, env=env).stdout or ""
        mean = [l for l in r.splitlines() if "Mean error" in l]
        error = float(mean[0].split("=")[1]) if mean else (0.0 if "PASS" in r else 1.0)
        lit = all(peak(os.path.join(OUT, n + ".exr"), env) > 1e-3 for n in (a, bname))
        ok = lit and error < 1e-3
        problems += 0 if ok else 1
        print("%-9s vs %-10s : %-6s mean error %.2e%s" % (
            a, bname, "ok" if ok else "WRONG", error, "" if lit else "  (black image)"))
    print("\n%d pairs, %d problems" % (len(PAIRS), problems))


def peak(exr, env):
    out = subprocess.run([os.path.join(HFS, "hoiiotool.exe"), "--stats", exr],
                         capture_output=True, text=True, env=env).stdout or ""
    line = [l for l in out.splitlines() if "Stats Avg" in l]
    return max(float(v) for v in line[0].split(":")[1].split()[:3]) if line else 0.0


if __name__ == "__main__":
    main()
