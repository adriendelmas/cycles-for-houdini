"""Render one MaterialX node per case and check the colour that comes out.

The native-node bench (`bench_render.py`) only says "not black"; here the
value matters, because a translation can produce a plausible and wrong image:
a `contrast` on a colour that went through Cycles' scalar node came out grey,
and a check on the mean alone would have let it through.

Each case is a plane lit head-on, the probed node driving the base colour of a
`standard_surface` with no specular. The report gives the three RGB means
brought back to base-colour units; the expected colour is checked within the
case's tolerance (2 % unless stated).

**Expected values come from the MaterialX definitions, never from the
renderer.** Each one is computed below from the source expression or
nodegraph shipped in `$HFS/houdini/materialx/libraries`, with the file named.
A value derived from what the code happened to produce proves nothing - that
is how an HSV-based `saturate` passed for months.

    hython tools/bench_mtlx.py [pattern]

`CYCLES_BENCH_TEXTURE` adds the three textured cases, which need a file.
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
        %s
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

# The factor between a base colour and the rendered mean, measured on a case
# whose answer is known - a constant of one.
GAIN = 5.544

# ---------------------------------------------------------------------------
# Expected values, from the MaterialX library.
# ---------------------------------------------------------------------------

# ND_saturate_color3 / ND_luminance_color3 default `lumacoeffs` (ACEScg),
# stdlib/stdlib_defs.mtlx.
LUMA_ACESCG = (0.2722287, 0.6740818, 0.0536895)


def lerp(a, b, t):
    return tuple(x * (1.0 - t) + y * t for x, y in zip(a, b))


def mx_mix(bg, fg, mix):
    """stdlib/genglsl/stdlib_genglsl_impl.mtlx: `mix({{bg}}, {{fg}}, {{mix}})`."""
    return lerp(bg, fg, mix)


def mx_plus(bg, fg, mix):
    """`({{mix}}*({{bg}} + {{fg}})) + ((1.0-{{mix}})*{{bg}})`."""
    return tuple(mix * (b + f) + (1.0 - mix) * b for b, f in zip(bg, fg))


def mx_luminance(c, coeffs=LUMA_ACESCG):
    """NG_luminance: dot(in, lumacoeffs), spread to grey."""
    y = sum(x * w for x, w in zip(c, coeffs))
    return (y, y, y)


def mx_saturate(c, amount):
    """stdlib/stdlib_ng.mtlx NG_saturate_color3: mix(bg=luminance(in), fg=in, amount)."""
    return mx_mix(mx_luminance(c), c, amount)


def mx_contrast(c, amount, pivot):
    """`({{in}} - {{pivot}}) * {{amount}} + {{pivot}}`. The renderer clamps a
    negative base colour at zero, which is what the plane shows."""
    return tuple(max(0.0, (x - pivot) * amount + pivot) for x in c)


def rgb(c):
    return "(%g, %g, %g)" % c


# (name, body of the `probe` prim, expected colour or None, options)
# Options: `mesh` adds lines to the mesh prim; `tol` overrides the tolerance.
CASES = [
    ("dot", [
        'uniform token info:id = "ND_dot_color3"',
        "color3f inputs:in = (0.9, 0.2, 0.1)",
        "color3f outputs:out",
    ], (0.9, 0.2, 0.1), {}),
    ("convert", [
        'uniform token info:id = "ND_convert_float_color3"',
        "float inputs:in = 0.7",
        "color3f outputs:out",
    ], (0.7, 0.7, 0.7), {}),
    ("constant_color", [
        'uniform token info:id = "ND_constant_color3"',
        "color3f inputs:value = (0.1, 0.8, 0.3)",
        "color3f outputs:out",
    ], (0.1, 0.8, 0.3), {}),
    ("constant_float", [
        'uniform token info:id = "ND_constant_float"',
        "float inputs:value = 0.6",
        "float outputs:out",
    ], (0.6, 0.6, 0.6), {}),
    ("mix", [
        'uniform token info:id = "ND_mix_color3"',
        "color3f inputs:fg = (0.9, 0.2, 0.1)",
        "color3f inputs:bg = (0.1, 0.2, 0.9)",
        "float inputs:mix = 0.75",
        "color3f outputs:out",
    ], mx_mix((0.1, 0.2, 0.9), (0.9, 0.2, 0.1), 0.75), {}),
    ("plus", [
        'uniform token info:id = "ND_plus_color3"',
        "color3f inputs:fg = (0.4, 0.1, 0.0)",
        "color3f inputs:bg = (0.1, 0.2, 0.3)",
        "float inputs:mix = 0.5",
        "color3f outputs:out",
    ], mx_plus((0.1, 0.2, 0.3), (0.4, 0.1, 0.0), 0.5), {}),
    ("saturate", [
        'uniform token info:id = "ND_saturate_color3"',
        "color3f inputs:in = (0.9, 0.2, 0.1)",
        "float inputs:amount = 0.2",
        "color3f outputs:out",
    ], mx_saturate((0.9, 0.2, 0.1), 0.2), {}),
    ("contrast", [
        'uniform token info:id = "ND_contrast_color3"',
        "color3f inputs:in = (0.9, 0.2, 0.1)",
        "float inputs:amount = 2",
        "float inputs:pivot = 0.5",
        "color3f outputs:out",
    ], mx_contrast((0.9, 0.2, 0.1), 2.0, 0.5), {}),
    ("logical_not", [
        'uniform token info:id = "ND_logical_not"',
        "bool inputs:in = 0",
        "bool outputs:out",
    ], (1.0, 1.0, 1.0), {}),
    # `geomcolor` reads the mesh's vertex colour, here a constant written per
    # vertex the way Houdini exports Cd.
    ("geomcolor", [
        'uniform token info:id = "ND_geomcolor_color3"',
        "color3f outputs:out",
    ], (0.2, 0.6, 0.9), {
        "mesh": 'color3f[] primvars:displayColor = [(0.2,0.6,0.9), (0.2,0.6,0.9), '
                '(0.2,0.6,0.9), (0.2,0.6,0.9)] (interpolation = "vertex")',
    }),
    # nprlib NG_facingratio_float: |dot(V, N)|, 1 where the plane faces the
    # camera. The plane spans 4 units at 6 units from a perspective camera, so
    # the ratio falls to 0.905 at the corners; averaged over the plane and
    # weighted by the light's own falloff it sits near 0.96. The tolerance
    # admits that spread; the inverted mapping gave 0.04.
    ("facingratio", [
        'uniform token info:id = "ND_facingratio_float"',
        "float outputs:out",
    ], (0.96, 0.96, 0.96), {"tol": 0.04}),
]

TEXTURED = [
    ("image", "ND_image_color3"),
    ("hextiledimage", "ND_hextiledimage_color3"),
    ("gltf_image", "ND_gltf_image_color3_color3_1_0"),
]

env = dict(os.environ)
env["PATH"] = HFS + ";" + env["PATH"]
# The delegate reports dropped inputs and connections through Cycles' logger.
env.setdefault("CYCLES_LOGGING", "1")
env.setdefault("CYCLES_LOGGING_LEVEL", "warning")


def render(name, body, mesh_extra):
    scene = os.path.join(OUT, name + ".usda")
    open(scene, "w", encoding="utf-8").write(
        SCENE % (mesh_extra, "\n                ".join(body)))
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
            ], None, {}))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if only:
        cases = [c for c in cases if only in c[0]]

    print("%-18s %-9s %s" % ("node", "state", "detail"))
    problems = []
    for name, body, expected, options in cases:
        exr, warns, log = render(name, body, options.get("mesh", ""))
        tol = options.get("tol", 0.02)
        if not os.path.exists(exr):
            state = "NO IMAGE"
            detail = (log.strip().splitlines() or [""])[-1][:60]
        elif warns:
            state, detail = "WARNED", warns[0].split("WARNING:")[-1].strip()[:70]
        else:
            avg = averages(exr)
            if avg is None:
                state, detail = "UNREADABLE", ""
            else:
                got = tuple(round(v / GAIN, 3) for v in avg)
                detail = "RGB %.3f %.3f %.3f" % got
                if expected is None:
                    state = "ok" if max(avg) > 1e-6 else "BLACK"
                elif all(abs(g - e) <= tol for g, e in zip(got, expected)):
                    state = "ok"
                else:
                    state = "WRONG"
                    detail += "  expected %.3f %.3f %.3f" % tuple(expected)
        if state != "ok":
            problems.append((name, state, detail))
        print("%-18s %-9s %s" % (name, state, detail))

    print("\n%d nodes rendered, %d problems" % (len(cases), len(problems)))
    for name, state, detail in problems:
        print("   %-16s %-12s %s" % (name, state, detail))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
