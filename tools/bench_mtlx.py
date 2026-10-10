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
             'token inputs:sourceColorSpace = "raw"',
             # USD's default wrap, useMetadata, is black without metadata: the
             # border texels would blend with it. These cases test channels.
             'token inputs:wrapS = "repeat"', 'token inputs:wrapT = "repeat"'] + extra + [output])


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
    # `geompropvalue` of a colour or a vector reads the primvar whole; it gave
    # its average as a float.
    ("geompropvalue_color3", [
        'uniform token info:id = "ND_geompropvalue_color3"',
        'string inputs:geomprop = "tint"',
        "color3f outputs:out",
    ], (0.2, 0.6, 0.9), {
        "mesh": 'color3f[] primvars:tint = [(0.2,0.6,0.9), (0.2,0.6,0.9), '
                '(0.2,0.6,0.9), (0.2,0.6,0.9)] (interpolation = "vertex")',
    }),
    ("geompropvalue_vector3", [
        'uniform token info:id = "ND_geompropvalue_vector3"',
        'string inputs:geomprop = "dir"',
        "float3 outputs:out",
    ], (0.7, 0.1, 0.4), {
        "mesh": 'float3[] primvars:dir = [(0.7,0.1,0.4), (0.7,0.1,0.4), '
                '(0.7,0.1,0.4), (0.7,0.1,0.4)] (interpolation = "vertex")',
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
    # A BSDF's own `weight` scales it (K-88): it was dropped, the lobe whole.
    ("closure_weight", [
        'uniform token info:id = "ND_oren_nayar_diffuse_bsdf"',
        "color3f inputs:color = (0.8, 0.4, 0.2)",
        "float inputs:roughness = 0",
        "float inputs:weight = 0.5",
        "token outputs:out",
    ], scale3((0.8, 0.4, 0.2), 0.5), {"terminal": "bsdf"}),
    ("closure_weight_wired", [
        'uniform token info:id = "ND_oren_nayar_diffuse_bsdf"',
        "color3f inputs:color = (0.8, 0.4, 0.2)",
        "float inputs:roughness = 0",
        "float inputs:weight.connect = </world/Materials/M/w.outputs:out>",
        "token outputs:out",
    ], scale3((0.8, 0.4, 0.2), 0.25), {"terminal": "bsdf", "extra": [shader("w", [
        'uniform token info:id = "ND_constant_float"', "float inputs:value = 0.25",
        "float outputs:out"])]}),
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

# Nodes the table does not hold: the delegate expands them from their
# MaterialX nodegraph (mtlx_expand.cpp), or rewrites them by hand (extract,
# swizzle). Formulas read from the nodegraphs in stdlib_ng.mtlx.


def mx_hsvadjust(c, amount):
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*c)
    return colorsys.hsv_to_rgb((h + amount[0]) % 1.0, s * amount[1], v * amount[2])


def mx_trianglewave(x):
    m = abs(x) % 1.0
    return 0.5 - abs(m - 0.5)


CASES += [
    # switch: ifgreater chain, in(which + 1).
    ("exp_switch_color3", [
        'uniform token info:id = "ND_switch_color3"',
        "color3f inputs:in1 = (0.9, 0.1, 0.1)",
        "color3f inputs:in2 = (0.1, 0.9, 0.1)",
        "color3f inputs:in3 = (0.1, 0.2, 0.8)",
        "color3f inputs:in4 = (0.5, 0.5, 0.5)",
        "float inputs:which = 2",
        "color3f outputs:out",
    ], (0.1, 0.2, 0.8), {}),
    ("exp_switch_float", [
        'uniform token info:id = "ND_switch_float"',
        "float inputs:in1 = 0.1",
        "float inputs:in2 = 0.9",
        "float inputs:in3 = 0.4",
        "float inputs:which = 1",
        "float outputs:out",
    ], (0.9, 0.9, 0.9), {}),
    ("exp_extract", [
        'uniform token info:id = "ND_extract_color3"',
        "color3f inputs:in = (0.9, 0.2, 0.1)",
        "int inputs:index = 1",
        "float outputs:out",
    ], (0.2, 0.2, 0.2), {}),
    ("exp_swizzle_bgr", [
        'uniform token info:id = "ND_swizzle_color3_color3"',
        "color3f inputs:in = (0.9, 0.2, 0.1)",
        'string inputs:channels = "bgr"',
        "color3f outputs:out",
    ], (0.1, 0.2, 0.9), {}),
    ("exp_swizzle_float", [
        'uniform token info:id = "ND_swizzle_float_color3"',
        "float inputs:in = 0.4",
        'string inputs:channels = "rrr"',
        "color3f outputs:out",
    ], (0.4, 0.4, 0.4), {}),
    ("exp_hsvadjust", [
        'uniform token info:id = "ND_hsvadjust_color3"',
        "color3f inputs:in = (0.9, 0.2, 0.1)",
        "float3 inputs:amount = (0.1, 0.5, 0.8)",
        "color3f outputs:out",
    ], mx_hsvadjust((0.9, 0.2, 0.1), (0.1, 0.5, 0.8)), {}),
    ("exp_trianglewave", [
        'uniform token info:id = "ND_trianglewave_float"',
        "float inputs:in = 0.65",
        "float outputs:out",
    ], (mx_trianglewave(0.65),) * 3, {}),
    # ramp4 is bilinear in the plane's st; the plane faces the camera, so the
    # mean over it is the mean of the four corners.
    ("exp_ramp4", [
        'uniform token info:id = "ND_ramp4_color3"',
        "color3f inputs:valuetl = (1, 0, 0)",
        "color3f inputs:valuetr = (0, 1, 0)",
        "color3f inputs:valuebl = (0, 0, 1)",
        "color3f inputs:valuebr = (1, 1, 0)",
        "color3f outputs:out",
    ], (0.5, 0.5, 0.25), {"tol": 0.03}),
]


def texcoord(name):
    return shader(name, ['uniform token info:id = "ND_texcoord_vector2"', "float2 outputs:out"])


CASES += [
    # The plane's st runs 0..1 both ways: the mean of either component is 0.5.
    ("dbg_texcoord_x", [
        'uniform token info:id = "ND_extract_vector2"',
        "float2 inputs:in.connect = </world/Materials/M/tc.outputs:out>",
        "int inputs:index = 0",
        "float outputs:out",
    ], (0.5, 0.5, 0.5), {"extra": [texcoord("tc")], "tol": 0.03}),
    ("dbg_clamp_texcoord_y", [
        'uniform token info:id = "ND_extract_vector2"',
        "float2 inputs:in.connect = </world/Materials/M/cl.outputs:out>",
        "int inputs:index = 1",
        "float outputs:out",
    ], (0.5, 0.5, 0.5), {"extra": [texcoord("tc"), shader("cl", [
        'uniform token info:id = "ND_clamp_vector2"',
        "float2 inputs:in.connect = </world/Materials/M/tc.outputs:out>",
        "float2 inputs:low = (0, 0)", "float2 inputs:high = (1, 1)", "float2 outputs:out"])],
        "tol": 0.03}),
    # splitlr / splittb: a sharp step at `center` along s, or along 1 - t;
    # with center 0.25, three quarters of the plane show the second value.
    ("exp_splitlr", [
        'uniform token info:id = "ND_splitlr_color3"',
        "color3f inputs:valuel = (1, 0, 0)",
        "color3f inputs:valuer = (0, 0, 1)",
        "float inputs:center = 0.25",
        "color3f outputs:out",
    ], (0.25, 0.0, 0.75), {"tol": 0.03}),
    ("exp_splittb", [
        'uniform token info:id = "ND_splittb_color3"',
        "color3f inputs:valuet = (1, 0, 0)",
        "color3f inputs:valueb = (0, 0, 1)",
        "float inputs:center = 0.25",
        "color3f outputs:out",
    ], (0.25, 0.0, 0.75), {"tol": 0.03}),
    # A connected texcoord replaces the helper's: a constant (0.9, 0.5) is past
    # the centre, so the right value shows everywhere.
    ("exp_splitlr_texcoord", [
        'uniform token info:id = "ND_splitlr_color3"',
        "color3f inputs:valuel = (1, 0, 0)",
        "color3f inputs:valuer = (0, 0, 1)",
        "float inputs:center = 0.25",
        "float2 inputs:texcoord.connect = </world/Materials/M/c2.outputs:out>",
        "color3f outputs:out",
    ], (0.0, 0.0, 1.0), {"extra": [shader("c2", [
        'uniform token info:id = "ND_constant_vector2"', "float2 inputs:value = (0.9, 0.5)",
        "float2 outputs:out"])]}),
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


# The delegate's own nodegraphs (mtlx_nodegraphs.h), for nodedefs the library
# implements in GLSL/OSL only. Expected values transcribe the library's GLSL,
# file named on each function.


def mx_roughness_anisotropy(roughness, anisotropy):
    # pbrlib/genglsl/mx_roughness_anisotropy.glsl
    rsq = min(max(roughness * roughness, 1e-8), 1.0)
    if anisotropy > 0.0:
        aspect = math.sqrt(1.0 - min(max(anisotropy, 0.0), 0.98))
        return (min(rsq / aspect, 1.0), rsq * aspect)
    return (rsq, rsq)


def mx_roughness_dual(x, y):
    # pbrlib/genglsl/mx_roughness_dual.glsl
    if y < 0.0:
        y = x
    return (min(max(x * x, 1e-8), 1.0), min(max(y * y, 1e-8), 1.0))


def mx_artistic_ior(reflectivity, edge_color):
    # pbrlib/genglsl/mx_artistic_ior.glsl
    ior, ext = [], []
    for r, e in zip(reflectivity, edge_color):
        r = min(max(r, 0.0), 0.99)
        rs = math.sqrt(r)
        n_min = (1.0 - r) / (1.0 + r)
        n_max = (1.0 + rs) / (1.0 - rs)
        n = n_max * (1.0 - e) + n_min * e
        k2 = max(((n + 1.0) ** 2 * r - (n - 1.0) ** 2) / (1.0 - r), 0.0)
        ior.append(n)
        ext.append(math.sqrt(k2))
    return tuple(ior), tuple(ext)



def mx_complement(rgb):
    # houdini/hmtlxcomplementcolor.mtlx: rec709 to XYZ, to xyY, mirrored
    # through the D65 white point (x, y) -> (2wx - x, 2wy - y), back.
    to_xyz = ((0.412391, 0.212639, 0.0193308), (0.357584, 0.715169, 0.119195),
              (0.180481, 0.0721923, 0.950532))
    to_rgb = ((3.24097, -0.969244, 0.0556301), (-1.53738, 1.87597, -0.203977),
              (-0.498611, 0.0415551, 1.05697))
    X, Y, Z = (sum(rgb[j] * to_xyz[j][i] for j in range(3)) for i in range(3))
    s = X + Y + Z
    x, y = X / s, Y / s
    x2, y2 = 2 * 0.3127 - x, 2 * 0.329 - y
    X2, Z2 = x2 * Y / y2, (1 - x2 - y2) * Y / y2
    xyz = (X2, Y, Z2)
    return tuple(sum(xyz[j] * to_rgb[j][i] for j in range(3)) for i in range(3))


IMAGE4 = shader("img", ['uniform token info:id = "ND_image_color4"',
                        "asset inputs:file = @flat.exr@", "color4f outputs:out"])


PLACE2D = ['uniform token info:id = "ND_place2d_vector2"',
           "float2 inputs:texcoord = (0.6, 0.3)", "float2 inputs:pivot = (0.4, 0.5)",
           "float2 inputs:scale = (2, 1.5)", "float inputs:rotate = 30",
           "float2 inputs:offset = (0.1, -0.05)", "float2 outputs:out"]


def mx_place2d(uv, pivot, scale, degrees, offset, order):
    # stdlib_ng NG_place2d_vector2: SRT (0) scales, rotates, then offsets;
    # TRS (1) offsets, rotates, then scales - both about the pivot.
    p = (uv[0] - pivot[0], uv[1] - pivot[1])
    if order == 0:
        p = mx_rotate2d((p[0] / scale[0], p[1] / scale[1]), degrees)
        p = (p[0] - offset[0], p[1] - offset[1])
    else:
        p = mx_rotate2d((p[0] - offset[0], p[1] - offset[1]), degrees)
        p = (p[0] / scale[0], p[1] / scale[1])
    return (p[0] + pivot[0], p[1] + pivot[1])


def mx_rotate2d(v, degrees):
    # stdlib/genglsl/mx_rotate_vector2.glsl
    a = math.radians(degrees)
    s, c = math.sin(a), math.cos(a)
    return (c * v[0] + s * v[1], -s * v[0] + c * v[1])


def mx_rotate3d(v, degrees, axis):
    # stdlib/genglsl/mx_rotate_vector3.glsl: v c + cross(v, axis) s + axis (axis . v)(1 - c)
    n = math.sqrt(sum(x * x for x in axis))
    k = [x / n for x in axis]
    a = math.radians(degrees)
    s, c = math.sin(a), math.cos(a)
    cross = (v[1] * k[2] - v[2] * k[1], v[2] * k[0] - v[0] * k[2], v[0] * k[1] - v[1] * k[0])
    d = sum(v[i] * k[i] for i in range(3))
    return tuple(v[i] * c + cross[i] * s + k[i] * d * (1 - c) for i in range(3))

def read_component(node, index):
    """A probe reading one component of a vector2 output of `node`."""
    return [
        'uniform token info:id = "ND_extract_vector2"',
        "float2 inputs:in.connect = </world/Materials/M/%s.outputs:out>" % node,
        "int inputs:index = %d" % index,
        "float outputs:out",
    ]


ANISO = shader("ra", ['uniform token info:id = "ND_roughness_anisotropy"',
                      "float inputs:roughness = 0.6", "float inputs:anisotropy = 0.5",
                      "float2 outputs:out"])
DUAL = shader("rd", ['uniform token info:id = "ND_roughness_dual"',
                     "float2 inputs:roughness = (0.7, -1)", "float2 outputs:out"])
GLOSS = shader("ga", ['uniform token info:id = "ND_glossiness_anisotropy"',
                      "float inputs:glossiness = 0.4", "float inputs:anisotropy = 0.3",
                      "float2 outputs:out"])
ARTISTIC = shader("ai", ['uniform token info:id = "ND_artistic_ior"',
                         "color3f inputs:reflectivity = (0.3, 0.5, 0.2)",
                         "color3f inputs:edge_color = (0.5, 0.8, 0.2)",
                         "color3f outputs:ior", "color3f outputs:extinction"])
_ior, _ext = mx_artistic_ior((0.3, 0.5, 0.2), (0.5, 0.8, 0.2))

CASES += [
    ("own_roughness_anisotropy_x", read_component("ra", 0),
     (mx_roughness_anisotropy(0.6, 0.5)[0],) * 3, {"extra": [ANISO]}),
    ("own_roughness_anisotropy_y", read_component("ra", 1),
     (mx_roughness_anisotropy(0.6, 0.5)[1],) * 3, {"extra": [ANISO]}),
    ("own_roughness_dual_y", read_component("rd", 1),
     (mx_roughness_dual(0.7, -1.0)[1],) * 3, {"extra": [DUAL]}),
    # glossiness_anisotropy is the library's own nodegraph, 1 - glossiness
    # into roughness_anisotropy: it expands once the latter does.
    ("own_glossiness_anisotropy_x", read_component("ga", 0),
     (mx_roughness_anisotropy(0.6, 0.3)[0],) * 3, {"extra": [GLOSS]}),
    # ior runs past 1: scaled by a quarter to stay in base-colour range.
    ("own_artistic_ior", [
        'uniform token info:id = "ND_multiply_color3FA"',
        "color3f inputs:in1.connect = </world/Materials/M/ai.outputs:ior>",
        "float inputs:in2 = 0.25",
        "color3f outputs:out",
    ], tuple(0.25 * v for v in _ior), {"extra": [ARTISTIC]}),
    ("own_artistic_extinction", [
        'uniform token info:id = "ND_multiply_color3FA"',
        "color3f inputs:in1.connect = </world/Materials/M/ai.outputs:extinction>",
        "float inputs:in2 = 0.25",
        "color3f outputs:out",
    ], tuple(0.25 * v for v in _ext), {"extra": [ARTISTIC]}),
    # inside / outside: in * mask, in * (1 - mask) (stdlib_genglsl_impl.mtlx).
    # A colour-valued mix factor mixes per channel (mix(bg, fg, mix)); it was
    # averaged onto a scalar factor before 0104.
    ("mix_color_factor", [
        'uniform token info:id = "ND_mix_color3_color3"',
        "color3f inputs:fg = (0.9, 0.2, 0.1)",
        "color3f inputs:bg = (0.1, 0.2, 0.9)",
        "color3f inputs:mix = (0.25, 0.5, 1.0)",
        "color3f outputs:out",
    ], (0.3, 0.2, 0.1), {}),
    # Scalar results of vector maths: |v|, |a - b|, a . b.
    ("scalar_magnitude", [
        'uniform token info:id = "ND_magnitude_vector3"',
        "float3 inputs:in = (0.3, 0.4, 0)",
        "float outputs:out",
    ], (0.5, 0.5, 0.5), {}),
    ("scalar_distance", [
        'uniform token info:id = "ND_distance_vector3"',
        "float3 inputs:in1 = (0.1, 0.2, 0.3)",
        "float3 inputs:in2 = (0.1, 0.5, 0.7)",
        "float outputs:out",
    ], (0.5, 0.5, 0.5), {}),
    ("scalar_dotproduct", [
        'uniform token info:id = "ND_dotproduct_vector3"',
        "float3 inputs:in1 = (0.2, 0.5, 0.1)",
        "float3 inputs:in2 = (1, 0.5, 2)",
        "float outputs:out",
    ], (0.65, 0.65, 0.65), {}),
    # transformmatrix with a constant matrix: out[i] = sum_j in[j] * M[j][i]
    # (row vector on the left; stdlib/genglsl/lib/mx_math.glsl).
    ("rw_transformmatrix_vector3", [
        'uniform token info:id = "ND_transformmatrix_vector3"',
        "float3 inputs:in = (0.2, 0.5, 0.1)",
        "matrix3d inputs:mat = ( (1, 0, 0.5), (0, 0.5, 0), (0.5, 0, 1) )",
        "float3 outputs:out",
    ], (0.2 + 0.05, 0.25, 0.1 + 0.1), {}),
    ("rw_transformmatrix_vector3M4", [
        'uniform token info:id = "ND_transformmatrix_vector3M4"',
        "float3 inputs:in = (0.2, 0.5, 0.1)",
        "matrix4d inputs:mat = ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0.3, 0.1, 0.4, 1) )",
        "float3 outputs:out",
    ], (0.5, 0.6, 0.5), {}),
    # hmtlxcomplementcolor: the colour opposite through the D65 white point in
    # xyY, through two transformmatrix (houdini/hmtlxcomplementcolor.mtlx).
    ("own_complementcolor", [
        'uniform token info:id = "ND_hmtlxcomplementcolor_vector3"',
        "float3 inputs:in = (0.6, 0.3, 0.2)",
        "float3 outputs:out",
    ], mx_complement((0.6, 0.3, 0.2)), {}),
    # curveadjust: rolled back in 1.39.2, implemented nowhere but in MDL,
    # which returns the input unchanged (mdl/materialx/stdlib_1_6.mdl).
    ("legacy_curveadjust", [
        'uniform token info:id = "ND_curveadjust_color3"',
        "color3f inputs:in = (0.3, 0.6, 0.2)",
        "color3f outputs:out",
    ], (0.3, 0.6, 0.2), {}),
    # The alpha of a colour4 image reaches a scalar input: through extract
    # (rewritten into a separate) and through separate4.outa, both routed to
    # the image node's alpha (K-17, 0105). flat.exr's texel alpha is 0.6.
    ("alpha_extract", [
        'uniform token info:id = "ND_extract_color4"',
        "color4f inputs:in.connect = </world/Materials/M/img.outputs:out>",
        "int inputs:index = 3",
        "float outputs:out",
    ], (0.6, 0.6, 0.6), {"extra": [IMAGE4]}),
    ("alpha_separate4", [
        'uniform token info:id = "ND_multiply_float"',
        "float inputs:in1.connect = </world/Materials/M/sep.outputs:outa>",
        "float inputs:in2 = 1",
        "float outputs:out",
    ], (0.6, 0.6, 0.6), {"extra": [IMAGE4, shader("sep", [
        'uniform token info:id = "ND_separate4_color4"',
        "color4f inputs:in.connect = </world/Materials/M/img.outputs:out>",
        "float outputs:outr", "float outputs:outg", "float outputs:outb", "float outputs:outa"])]}),
    # The alpha of a computed colour4: each colour4 node on the way gets a
    # float twin (K-17). The image's alpha is 0.6.
    ("alpha_mix", [
        'uniform token info:id = "ND_multiply_float"',
        "float inputs:in1.connect = </world/Materials/M/sep.outputs:outa>",
        "float inputs:in2 = 1",
        "float outputs:out",
    ], (0.3, 0.3, 0.3), {"extra": [IMAGE4, shader("mix", [
        'uniform token info:id = "ND_mix_color4"',
        "color4f inputs:fg.connect = </world/Materials/M/img.outputs:out>",
        "color4f inputs:bg = (0, 0, 0, 0.2)",
        "float inputs:mix = 0.25",
        "color4f outputs:out"]), shader("sep", [
        'uniform token info:id = "ND_separate4_color4"',
        "color4f inputs:in.connect = </world/Materials/M/mix.outputs:out>",
        "float outputs:outr", "float outputs:outg", "float outputs:outb", "float outputs:outa"])]}),
    ("alpha_multiply_by_float", [
        'uniform token info:id = "ND_multiply_float"',
        "float inputs:in1.connect = </world/Materials/M/sep.outputs:outa>",
        "float inputs:in2 = 1",
        "float outputs:out",
    ], (0.3, 0.3, 0.3), {"extra": [IMAGE4, shader("mul", [
        'uniform token info:id = "ND_multiply_color4FA"',
        "color4f inputs:in1.connect = </world/Materials/M/img.outputs:out>",
        "float inputs:in2 = 0.5",
        "color4f outputs:out"]), shader("sep", [
        'uniform token info:id = "ND_separate4_color4"',
        "color4f inputs:in.connect = </world/Materials/M/mul.outputs:out>",
        "float outputs:outr", "float outputs:outg", "float outputs:outb", "float outputs:outa"])]}),
    ("alpha_add_values", [
        'uniform token info:id = "ND_multiply_float"',
        "float inputs:in1.connect = </world/Materials/M/sep.outputs:outa>",
        "float inputs:in2 = 1",
        "float outputs:out",
    ], (0.35, 0.35, 0.35), {"extra": [shader("add", [
        'uniform token info:id = "ND_add_color4"',
        "color4f inputs:in1 = (0.5, 0.5, 0.5, 0.1)",
        "color4f inputs:in2 = (0.5, 0.5, 0.5, 0.25)",
        "color4f outputs:out"]), shader("sep", [
        'uniform token info:id = "ND_separate4_color4"',
        "color4f inputs:in.connect = </world/Materials/M/add.outputs:out>",
        "float outputs:outr", "float outputs:outg", "float outputs:outb", "float outputs:outa"])]}),
    # rotate2d / rotate3d: degrees, and v' = v * M (mx_rotate_vector2/3.glsl).
    ("rotate2d_x", [
        'uniform token info:id = "ND_extract_vector2"',
        "float2 inputs:in.connect = </world/Materials/M/rot.outputs:out>",
        "int inputs:index = 0",
        "float outputs:out",
    ], (mx_rotate2d((0.5, 0.2), 30)[0],) * 3, {"extra": [shader("rot", [
        'uniform token info:id = "ND_rotate2d_vector2"',
        "float2 inputs:in = (0.5, 0.2)", "float inputs:amount = 30", "float2 outputs:out"])]}),
    ("rotate2d_y", [
        'uniform token info:id = "ND_extract_vector2"',
        "float2 inputs:in.connect = </world/Materials/M/rot.outputs:out>",
        "int inputs:index = 1",
        "float outputs:out",
    ], (mx_rotate2d((0.2, 0.5), 30)[1],) * 3, {"extra": [shader("rot", [
        'uniform token info:id = "ND_rotate2d_vector2"',
        "float2 inputs:in = (0.2, 0.5)", "float inputs:amount = 30", "float2 outputs:out"])]}),
    # place2d, both operation orders, with a pivot (stdlib_ng NG_place2d_vector2).
    ("place2d_srt", [
        'uniform token info:id = "ND_extract_vector2"',
        "float2 inputs:in.connect = </world/Materials/M/pl.outputs:out>",
        "int inputs:index = 0",
        "float outputs:out",
    ], (mx_place2d((0.6, 0.3), (0.4, 0.5), (2, 1.5), 30, (0.1, -0.05), 0)[0],) * 3,
        {"extra": [shader("pl", PLACE2D + ["int inputs:operationorder = 0"])]}),
    ("place2d_trs", [
        'uniform token info:id = "ND_extract_vector2"',
        "float2 inputs:in.connect = </world/Materials/M/pl.outputs:out>",
        "int inputs:index = 1",
        "float outputs:out",
    ], (mx_place2d((0.6, 0.3), (0.4, 0.5), (2, 1.5), 30, (0.1, -0.05), 1)[1],) * 3,
        {"extra": [shader("pl", PLACE2D + ["int inputs:operationorder = 1"])]}),
    ("rotate3d", [
        'uniform token info:id = "ND_rotate3d_vector3"',
        "float3 inputs:in = (0.2, 0.5, 0.1)", "float inputs:amount = 30",
        "float3 inputs:axis = (0, 1, 0)",
        "float3 outputs:out",
    ], mx_rotate3d((0.2, 0.5, 0.1), 30, (0, 1, 0)), {}),
    # Found by tools/mtlx_karma.py (2026-10-08), expected values from the
    # library's GLSL. dodge is not clamped: 0.6 / (1 - 0.6) = 1.5.
    ("ka_dodge_color3", [
        'uniform token info:id = "ND_dodge_color3"',
        "color3f inputs:fg = (0.6, 0.3, 0.15)", "color3f inputs:bg = (0.6, 0.3, 0.15)",
        "float inputs:mix = 1",
        "color3f outputs:out",
    ], (1.5, 0.3 / 0.7, 0.15 / 0.85), {}),
    ("ka_burn_float", [
        'uniform token info:id = "ND_burn_float"',
        "float inputs:fg = 0.8", "float inputs:bg = 0.6", "float inputs:mix = 1",
        "float outputs:out",
    ], (0.5, 0.5, 0.5), {}),
    ("ka_ifgreater_boolean", ['uniform token info:id = "ND_convert_boolean_color3"', 'bool inputs:in.connect = </world/Materials/M/cmp.outputs:out>', 'color3f outputs:out'], (1.0, 1.0, 1.0), {"extra": [shader("cmp", [
        'uniform token info:id = "ND_ifgreater_boolean"',
        "float inputs:value1 = 0.7", "float inputs:value2 = 0.3", "bool outputs:out"])]}),
    ("ka_ifgreatereq_boolean_false", ['uniform token info:id = "ND_convert_boolean_color3"', 'bool inputs:in.connect = </world/Materials/M/cmp.outputs:out>', 'color3f outputs:out'], (0.0, 0.0, 0.0), {"extra": [shader("cmp", [
        'uniform token info:id = "ND_ifgreatereq_boolean"',
        "float inputs:value1 = 0.2", "float inputs:value2 = 0.3", "bool outputs:out"])]}),
    ("ka_combine2_color4CF", ['uniform token info:id = "ND_convert_color4_color3"', 'color4f inputs:in.connect = </world/Materials/M/cmb.outputs:out>', 'color3f outputs:out'], (0.6, 0.3, 0.15), {"extra": [shader("cmb", [
        'uniform token info:id = "ND_combine2_color4CF"',
        "color3f inputs:in1 = (0.6, 0.3, 0.15)", "float inputs:in2 = 0.8", "color4f outputs:out"])]}),
    ("ka_convert_vector2", ['uniform token info:id = "ND_convert_vector2_color3"', 'float2 inputs:in.connect = </world/Materials/M/cs.outputs:out>', 'color3f outputs:out'], (math.cos(0.5), math.cos(0.2), 0.0), {"extra": [shader("cs", [
        'uniform token info:id = "ND_cos_vector2"',
        "float2 inputs:in = (0.5, 0.2)", "float2 outputs:out"])]}),
    # A vector2 reduced: subtract(v, 0.3) leaves the free third component at
    # -0.3, which the dot product must not count: 0.2^2 + 0.5^2 = 0.29.
    ("ka_dotproduct_vector2", [
        'uniform token info:id = "ND_dotproduct_vector2"',
        "float2 inputs:in1.connect = </world/Materials/M/sub.outputs:out>",
        "float2 inputs:in2.connect = </world/Materials/M/sub.outputs:out>",
        "float outputs:out",
    ], (0.29, 0.29, 0.29), {"extra": [shader("sub", [
        'uniform token info:id = "ND_subtract_vector2FA"',
        "float2 inputs:in1 = (0.5, 0.8)", "float inputs:in2 = 0.3", "float2 outputs:out"])]}),
    # heighttonormal returns an encoded tangent-space normal: flat is
    # (0.5, 0.5, 1) (K-12; it returned the world normal, (0, 0, 1)).
    ("ka_heighttonormal_flat", [
        'uniform token info:id = "ND_heighttonormal_vector3"',
        "float inputs:in = 0.4",
        "float3 outputs:out",
    ], (0.5, 0.5, 1.0), {}),
    # The plane's U runs along +X, its V along +Y: tangent (1, 0, 0),
    # bitangent (0, 1, 0) - the radial tangent pointed elsewhere.
    ("ka_tangent", [
        'uniform token info:id = "ND_tangent_vector3"',
        'uniform string inputs:space = "world"',
        "float3 outputs:out",
    ], (1.0, 0.0, 0.0), {}),
    ("ka_bitangent", [
        'uniform token info:id = "ND_bitangent_vector3"',
        'uniform string inputs:space = "world"',
        "float3 outputs:out",
    ], (0.0, 1.0, 0.0), {}),
    ("own_inside_color3", [
        'uniform token info:id = "ND_inside_color3"',
        "color3f inputs:in = (0.9, 0.5, 0.2)", "float inputs:mask = 0.4",
        "color3f outputs:out",
    ], (0.36, 0.2, 0.08), {}),
    ("own_outside_float", [
        'uniform token info:id = "ND_outside_float"',
        "float inputs:in = 0.8", "float inputs:mask = 0.25",
        "float outputs:out",
    ], (0.6, 0.6, 0.6), {}),
]

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
