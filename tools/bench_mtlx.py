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

import math
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "materialx", "output")
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
%s
        }
    }
}
"""

# How the probe reaches the surface terminal, by the kind of value it produces.
# A colour drives the base colour of a specular-free standard_surface; a BSDF
# goes through `surface`; a surfaceshader is the terminal itself.
TERMINALS = {
    "color": """            token outputs:mtlx:surface.connect = </world/Materials/M/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                float inputs:specular = 0
                color3f inputs:base_color.connect = </world/Materials/M/probe.outputs:out>
                token outputs:out
            }""",
    "bsdf": """            token outputs:mtlx:surface.connect = </world/Materials/M/surf.outputs:out>
            def Shader "surf"
            {
                uniform token info:id = "ND_surface"
                token inputs:bsdf.connect = </world/Materials/M/probe.outputs:out>
                token outputs:out
            }""",
    "surface": """            token outputs:mtlx:surface.connect = </world/Materials/M/probe.outputs:out>""",
}


def shader(name, lines):
    body = "\n".join("                " + l for l in lines)
    return '            def Shader "%s"\n            {\n%s\n            }' % (name, body)


# A Lambert lobe, the same the colour template's standard_surface reduces to
# at specular zero, so the closure cases share its gain.
def diffuse(name, color):
    return shader(name, ['uniform token info:id = "ND_oren_nayar_diffuse_bsdf"',
                         "color3f inputs:color = %s" % rgb(color),
                         "float inputs:roughness = 0",
                         "token outputs:out"])


def matte(name, color):
    return shader(name, ['uniform token info:id = "ND_standard_surface_surfaceshader"',
                         "float inputs:specular = 0",
                         "color3f inputs:base_color = %s" % rgb(color),
                         "token outputs:out"])

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
    return "(%g, %g, %g)" % tuple(c)


def add3(a, b):
    return tuple(x + y for x, y in zip(a, b))


def scale3(a, s):
    return tuple(x * s for x in a)


RED, BLUE = (0.9, 0.2, 0.1), (0.1, 0.2, 0.9)

FLAT_TEXEL = (0.2, 0.9, 0.4, 0.6)


def uvtex(extra, output):
    return (['uniform token info:id = "UsdUVTexture"',
             "asset inputs:file = @flat.exr@",
             'token inputs:sourceColorSpace = "raw"'] + extra + [output])


def write_flat_texture():
    """A 4x4 texture of one texel value, raw float, beside the scenes."""
    import OpenImageIO as oiio
    spec = oiio.ImageSpec(4, 4, 4, oiio.FLOAT)
    buf = oiio.ImageBuf(spec)
    oiio.ImageBufAlgo.fill(buf, list(FLAT_TEXEL))
    buf.write(os.path.join(OUT, "flat.exr"))

# (name, body of the `probe` prim, expected colour or None, options)
# Options: `mesh` adds lines to the mesh prim; `tol` overrides the tolerance;
# `terminal` picks how the probe reaches the surface (see TERMINALS); `extra`
# adds shader prims the probe connects to.
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
    # Closures. pbrlib `mix` is mix(bg, fg, mix) like the colour one; `add`
    # sums; `multiply` scales by a weight. Two Lambert lobes give a mean that
    # is the same function of their colours.
    ("closure_mix", [
        'uniform token info:id = "ND_mix_bsdf"',
        "token inputs:fg.connect = </world/Materials/M/d1.outputs:out>",
        "token inputs:bg.connect = </world/Materials/M/d2.outputs:out>",
        "float inputs:mix = 0.75",
        "token outputs:out",
    ], mx_mix(BLUE, RED, 0.75), {"terminal": "bsdf",
                                  "extra": [diffuse("d1", RED), diffuse("d2", BLUE)]}),
    ("closure_add", [
        'uniform token info:id = "ND_add_bsdf"',
        "token inputs:in1.connect = </world/Materials/M/d1.outputs:out>",
        "token inputs:in2.connect = </world/Materials/M/d2.outputs:out>",
        "token outputs:out",
    ], add3((0.3, 0.1, 0.0), (0.1, 0.2, 0.3)), {
        "terminal": "bsdf",
        "extra": [diffuse("d1", (0.3, 0.1, 0.0)), diffuse("d2", (0.1, 0.2, 0.3))]}),
    ("closure_scale", [
        'uniform token info:id = "ND_multiply_bsdfF"',
        "token inputs:in1.connect = </world/Materials/M/d1.outputs:out>",
        "float inputs:in2 = 0.5",
        "token outputs:out",
    ], scale3((0.8, 0.4, 0.2), 0.5), {"terminal": "bsdf",
                                       "extra": [diffuse("d1", (0.8, 0.4, 0.2))]}),
    ("surface_mix", [
        'uniform token info:id = "ND_mix_surfaceshader"',
        "token inputs:fg.connect = </world/Materials/M/s1.outputs:out>",
        "token inputs:bg.connect = </world/Materials/M/s2.outputs:out>",
        "float inputs:mix = 0.25",
        "token outputs:out",
    ], mx_mix(BLUE, RED, 0.25), {"terminal": "surface",
                                  "extra": [matte("s1", RED), matte("s2", BLUE)]}),
    # Colour and vector variants of the scalar operators (phase 3). Each input
    # is coloured, so a translation that collapses to grey cannot pass.
    # Formulas from stdlib_genglsl_impl.mtlx / stdlib_ng.mtlx.
] + [
    (name, ['uniform token info:id = "%s"' % nodedef] + inputs + [out], expected, {})
    for name, nodedef, inputs, out, expected in [
        ("clamp_color3", "ND_clamp_color3",
         ["color3f inputs:in = (1.4, 0.5, 0.05)", "color3f inputs:low = (0.1, 0.1, 0.1)",
          "color3f inputs:high = (0.8, 0.8, 0.8)"], "color3f outputs:out",
         tuple(min(max(x, 0.1), 0.8) for x in (1.4, 0.5, 0.05))),
        ("max_color3", "ND_max_color3",
         ["color3f inputs:in1 = (0.9, 0.2, 0.1)", "color3f inputs:in2 = (0.3, 0.6, 0.2)"],
         "color3f outputs:out", (0.9, 0.6, 0.2)),
        ("power_color3", "ND_power_color3",
         ["color3f inputs:in1 = (0.5, 0.25, 0.81)", "color3f inputs:in2 = (2, 2, 0.5)"],
         "color3f outputs:out", (0.25, 0.0625, 0.9)),
        ("sqrt_color3", "ND_sqrt_color3",
         ["color3f inputs:in = (0.25, 0.49, 0.04)"], "color3f outputs:out", (0.5, 0.7, 0.2)),
        ("exp_color3", "ND_exp_color3",
         ["color3f inputs:in = (-1, -2, -0.5)"], "color3f outputs:out",
         tuple(math.exp(x) for x in (-1, -2, -0.5))),
        ("ln_float", "ND_ln_float",
         ["float inputs:in = 2"], "float outputs:out", (math.log(2),) * 3),
        ("modulo_float", "ND_modulo_float",
         ["float inputs:in1 = -0.25", "float inputs:in2 = 1"], "float outputs:out",
         (0.75, 0.75, 0.75)),
        ("modulo_color3", "ND_modulo_color3",
         ["color3f inputs:in1 = (-0.25, 1.3, 0.5)", "color3f inputs:in2 = (1, 1, 1)"],
         "color3f outputs:out", (0.75, 0.3, 0.5)),
        ("invert_color3", "ND_invert_color3",
         ["color3f inputs:in = (0.2, 0.5, 0.7)", "color3f inputs:amount = (1, 1, 1)"],
         "color3f outputs:out", (0.8, 0.5, 0.3)),
        ("invert_float", "ND_invert_float",
         ["float inputs:in = 0.2", "float inputs:amount = 0.9"], "float outputs:out",
         (0.7, 0.7, 0.7)),
        ("remap_color3", "ND_remap_color3",
         ["color3f inputs:in = (0.5, 0.25, 0.75)", "color3f inputs:outlow = (0.2, 0.2, 0.2)",
          "color3f inputs:outhigh = (0.6, 0.6, 0.6)"], "color3f outputs:out",
         tuple(0.2 + 0.4 * x for x in (0.5, 0.25, 0.75))),
        ("smoothstep_color3", "ND_smoothstep_color3",
         ["color3f inputs:in = (0.5, 0.25, 0.75)"], "color3f outputs:out",
         tuple(3 * x * x - 2 * x * x * x for x in (0.5, 0.25, 0.75))),
        ("luminance_color3", "ND_luminance_color3",
         ["color3f inputs:in = (0.9, 0.2, 0.1)"], "color3f outputs:out",
         mx_luminance((0.9, 0.2, 0.1))),
        ("atan2_float", "ND_atan2_float",
         ["float inputs:iny = 1", "float inputs:inx = 2"], "float outputs:out",
         (math.atan2(1, 2),) * 3),
        ("atan2_vector3", "ND_atan2_vector3",
         ["float3 inputs:iny = (1, 0.5, 0.2)", "float3 inputs:inx = (2, 1, 1)"],
         "float3 outputs:out",
         tuple(math.atan2(y, x) for y, x in ((1, 2), (0.5, 1), (0.2, 1)))),
    ]
] + [
    # UsdUVTexture (phase 4): one flat texel (0.2, 0.9, 0.4), alpha 0.6, read
    # raw. Each output is its channel, and rgb * scale + bias is applied on the
    # way out (UsdPreviewSurface spec). The channels used to arrive averaged.
    ("uvtex_rgb", uvtex(["float4 inputs:scale = (0.5, 1, 2, 1)",
                         "float4 inputs:bias = (0.1, 0, 0, 0)"], "float3 outputs:rgb"),
     (0.2 * 0.5 + 0.1, 0.9, 0.4 * 2), {"probe_out": "rgb"}),
    ("uvtex_g", uvtex([], "float outputs:g"), (0.9, 0.9, 0.9), {"probe_out": "g"}),
    ("uvtex_b", uvtex([], "float outputs:b"), (0.4, 0.4, 0.4), {"probe_out": "b"}),
    ("uvtex_a", uvtex([], "float outputs:a"), (0.6, 0.6, 0.6), {"probe_out": "a"}),
    # A Karma Material Builder writes the same MaterialX nodes under the `kma`
    # render context; the delegate must read that network, not the
    # UsdPreviewSurface fallback Houdini writes beside it.
    ("kma_context", [
        'uniform token info:id = "ND_constant_color3"',
        "color3f inputs:value = (0.3, 0.7, 0.2)",
        "color3f outputs:out",
    ], (0.3, 0.7, 0.2), {"context": "kma"}),
    # `layer` has no exact Cycles form (a Fresnel-weighted mix stands in); the
    # case only asks that a dielectric over a diffuse renders, and not black.
    ("layer", [
        'uniform token info:id = "ND_layer_bsdf"',
        "token inputs:top.connect = </world/Materials/M/coat.outputs:out>",
        "token inputs:base.connect = </world/Materials/M/d1.outputs:out>",
        "token outputs:out",
    ], None, {"terminal": "bsdf",
              "extra": [diffuse("d1", RED),
                        shader("coat", ['uniform token info:id = "ND_dielectric_bsdf"',
                                        "float inputs:ior = 1.5",
                                        "token outputs:out"])]}),
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


def render(name, body, options):
    terminal = TERMINALS[options.get("terminal", "color")].replace(
        "probe.outputs:out", "probe.outputs:" + options.get("probe_out", "out")).replace(
        "outputs:mtlx:surface", "outputs:%s:surface" % options.get("context", "mtlx"))
    material = [terminal, shader("probe", body)]
    material += options.get("extra", [])
    scene = os.path.join(OUT, name + ".usda")
    open(scene, "w", encoding="utf-8").write(
        SCENE % (options.get("mesh", ""), "\n".join(material)))
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
    write_flat_texture()
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
        exr, warns, log = render(name, body, options)
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
