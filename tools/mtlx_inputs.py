"""Which MaterialX nodedefs translate without losing an input.

`mtlx_coverage.py` says which nodedefs *route* to a mapping. That is a
necessary condition, not a sufficient one: a nodedef whose prefix matches a
table entry still loses every input the mapping does not name. This tool
measures that second number by rendering.

One USD stage, one material per routed nodedef, every input of the nodedef
authored at its default so that Hydra forwards it, the node wired to a terminal
the way its output type requires. husk renders the lot once, and the
delegate's own warnings - which name the node path - are sorted per nodedef.

    hython tools/mtlx_inputs.py [--list] [pattern]

Reports, for the routed nodedefs: clean (no warning), inputs dropped, output
not found, node missing. `--list` prints the dropped inputs per nodedef.
The stage and the log stay in tests/materialx/output/inputs/ for inspection.
"""

import math
import os
import re
import subprocess
import sys

import MaterialX as mx

from mtlx_rules import Resolver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
SOURCE = os.path.join(ROOT, "external", "cycles-53", "src", "hydra", "material.cpp")
OUT = os.path.join(ROOT, "tests", "materialx", "output", "inputs")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

# Same routing rules as mtlx_coverage.py and the delegate.
INLINE = ("ND_add_", "ND_subtract_", "ND_multiply_", "ND_divide_")
NOT_SHADING = re.compile(
    r"^(Lama|Usd|surfacematerial|volumematerial|displacementmaterial|"
    r"light$|point_light|spot_light|directional_light|"
    r"arrayappend|osl_set_ci|.*_to_lin_rec709$|standard_surface_to_|open_pbr_surface_to_)"
)
PREFIX_RE = re.compile(r'\{"(ND_[A-Za-z0-9_]*)"')

# MaterialX type -> (USD type, formatter).
CLOSURES = {"BSDF", "EDF", "VDF", "surfaceshader", "displacementshader",
            "volumeshader", "lightshader", "material"}


def fmt_floats(text, n):
    parts = [p.strip() for p in text.split(",")] if text else []
    vals = []
    for i in range(n):
        try:
            vals.append(float(parts[i]))
        except (IndexError, ValueError):
            vals.append(0.0)
    return "(" + ", ".join("%g" % v for v in vals) + ")"


def usd_value(mx_type, text):
    """The USD attribute type and literal for a MaterialX input."""
    if mx_type == "float":
        try:
            return "float", "%g" % float(text)
        except ValueError:
            return "float", "0"
    if mx_type == "integer":
        try:
            return "int", "%d" % int(float(text))
        except ValueError:
            return "int", "0"
    if mx_type == "boolean":
        return "bool", "true" if text.strip().lower() in ("true", "1") else "false"
    if mx_type == "string":
        return "string", '"%s"' % text.replace('"', '\\"')
    if mx_type == "filename":
        return "asset", "@%s@" % (text or "missing.png")
    if mx_type == "color3":
        return "color3f", fmt_floats(text, 3)
    if mx_type == "color4":
        return "color4f", fmt_floats(text, 4)
    if mx_type == "vector2":
        return "float2", fmt_floats(text, 2)
    if mx_type == "vector3":
        return "float3", fmt_floats(text, 3)
    if mx_type == "vector4":
        return "float4", fmt_floats(text, 4)
    if mx_type == "matrix33":
        return "matrix3d", "( (1,0,0), (0,1,0), (0,0,1) )"
    if mx_type == "matrix44":
        return "matrix4d", "( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1) )"
    return None, None


USD_OUT_TYPE = {"float": "float", "integer": "int", "boolean": "bool", "string": "string",
                "filename": "asset", "color3": "color3f", "color4": "color4f",
                "vector2": "float2", "vector3": "float3", "vector4": "float4",
                "matrix33": "matrix3d", "matrix44": "matrix4d"}


def prefixes():
    text = open(SOURCE, encoding="utf-8", errors="replace").read()
    return sorted(set(PREFIX_RE.findall(text)), key=len, reverse=True)


# Kept alive for the whole run: a nodedef is a view into its document, and
# MaterialX refuses to answer for an element whose document has gone.
DOC = mx.createDocument()


def routed_nodedefs():
    doc = DOC
    mx.loadLibraries(["libraries"], mx.getDefaultDataSearchPath(), doc)
    resolver = Resolver(doc)
    out = []
    for nd in doc.getNodeDefs():
        if NOT_SHADING.match(nd.getNodeString()):
            continue
        if resolver.resolves(nd.getName()):
            out.append(nd)
    return out


def material_block(nd):
    """The Material prim for one nodedef, or None when it cannot be wired."""
    name = nd.getName()
    outputs = nd.getActiveOutputs()
    if not outputs:
        return None
    out_name = outputs[0].getName()
    out_type = outputs[0].getType()

    lines = []
    probe = ['uniform token info:id = "%s"' % name]
    for inp in nd.getActiveInputs():
        t = inp.getType()
        # `note` is a free-text annotation on the pass-through nodes, not a
        # shading input; nothing is expected to carry it.
        if t in CLOSURES or inp.getName() == "note":
            continue
        usd_t, literal = usd_value(t, inp.getValueString())
        if usd_t is None:
            continue
        probe.append("%s inputs:%s = %s" % (usd_t, inp.getName(), literal))
    for o in outputs:
        probe.append("%s outputs:%s" % (USD_OUT_TYPE.get(o.getType(), "token"), o.getName()))

    base = "/world/Materials/%s" % name
    probe_out = "<%s/probe.outputs:%s>" % (base, out_name)

    if out_type == "surfaceshader":
        lines.append("token outputs:mtlx:surface.connect = %s" % probe_out)
    elif out_type == "displacementshader":
        lines.append("token outputs:mtlx:displacement.connect = %s" % probe_out)
    elif out_type == "volumeshader":
        lines.append("token outputs:mtlx:volume.connect = %s" % probe_out)
    elif out_type in ("BSDF", "EDF"):
        lines.append("token outputs:mtlx:surface.connect = <%s/surf.outputs:out>" % base)
        lines.append('def Shader "surf" {')
        lines.append('    uniform token info:id = "ND_surface"')
        lines.append("    token inputs:%s.connect = %s" % (out_type.lower(), probe_out))
        lines.append("    token outputs:out")
        lines.append("}")
    elif out_type == "VDF":
        lines.append("token outputs:mtlx:volume.connect = <%s/vol.outputs:out>" % base)
        lines.append('def Shader "vol" {')
        lines.append('    uniform token info:id = "ND_volume"')
        lines.append("    token inputs:vdf.connect = %s" % probe_out)
        lines.append("    token outputs:out")
        lines.append("}")
    elif out_type in CLOSURES:
        return None
    else:
        lines.append("token outputs:mtlx:surface.connect = <%s/surf.outputs:out>" % base)
        lines.append('def Shader "surf" {')
        lines.append('    uniform token info:id = "ND_standard_surface_surfaceshader"')
        lines.append("    float inputs:specular = 0")
        lines.append("    color3f inputs:base_color.connect = %s" % probe_out)
        lines.append("    token outputs:out")
        lines.append("}")

    lines.append('def Shader "probe" {')
    lines += ["    " + p for p in probe]
    lines.append("}")
    return "\n".join("            " + l for l in lines)


HEAD = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
    startTimeCode = 1
    endTimeCode = 1
)

def Scope "Render"
{
    def RenderSettings "settings"
    {
        rel camera = </world/camera>
        int2 resolution = (%(res)d, %(res)d)
        int cycles:samples = 1
    }
}

def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = %(aperture)g
        float verticalAperture = %(aperture)g
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (%(center)g, %(center)g, 10, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def DomeLight "dome"
    {
        float inputs:intensity = 1
    }
%(quads)s
    def Scope "Materials"
    {
%(materials)s
    }
}
"""

QUAD = """    def Mesh "q%(i)d" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/%(name)s>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(%(x0)g,%(y0)g,0), (%(x1)g,%(y0)g,0), (%(x1)g,%(y1)g,0), (%(x0)g,%(y1)g,0)]
        texCoord2f[] primvars:st = [(0,0), (1,0), (1,1), (0,1)] (interpolation = "faceVarying")
        color3f[] primvars:displayColor = [(0.5,0.5,0.5)] (interpolation = "constant")
        uniform token subdivisionScheme = "none"
    }
"""

WARNING_KINDS = [
    ("missing", "no Cycles node for"),
    ("output", "has no output"),
    ("input", "no input '"),
    ("input", "which '"),  # "maps to Cycles input 'x', which 'node' does not have"
    ("connection", "does not take a connection"),
    ("connection", "connection dropped"),
]
INPUT_RE = re.compile(r"input '([^']+)'")


def main():
    want_list = "--list" in sys.argv
    pattern = next((a for a in sys.argv[1:] if not a.startswith("--")), None)

    nodedefs = routed_nodedefs()
    if pattern:
        nodedefs = [nd for nd in nodedefs if pattern in nd.getName()]
    blocks = []
    skipped = []
    for nd in nodedefs:
        block = material_block(nd)
        if block is None:
            skipped.append(nd.getName())
        else:
            blocks.append((nd.getName(), block))

    n = len(blocks)
    cols = max(1, int(math.ceil(math.sqrt(n))))
    quads = []
    for i, (name, _) in enumerate(blocks):
        c, r = i % cols, i // cols
        quads.append(QUAD % {"i": i, "name": name, "x0": c, "x1": c + 0.9, "y0": r, "y1": r + 0.9})
    materials = "\n".join('        def Material "%s"\n        {\n%s\n        }' % (name, block)
                          for name, block in blocks)
    # The aperture is in tenths of a unit; only the log is read, so the framing
    # never mattered here, but mtlx_pinned.py reads the pixels of this grid.
    scene = HEAD % {"res": 256, "aperture": (cols + 1) * 10, "center": cols / 2.0,
                    "quads": "".join(quads), "materials": materials}
    scene_path = os.path.join(OUT, "inputs.usda")
    open(scene_path, "w", encoding="utf-8").write(scene)

    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    env["CYCLES_LOGGING"] = "1"
    env["CYCLES_LOGGING_LEVEL"] = "warning"
    exr = os.path.join(OUT, "inputs.exr")
    run = subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                          "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                          "-s", "/Render/settings", "--output", exr, scene_path],
                         capture_output=True, text=True, env=env, cwd=OUT)
    log = (run.stdout or "") + (run.stderr or "")
    open(os.path.join(OUT, "inputs.log"), "w", encoding="utf-8").write(log)

    per = {name: {"missing": set(), "output": set(), "input": set(), "connection": set()}
           for name, _ in blocks}
    for line in log.splitlines():
        m = re.search(r"/world/Materials/([A-Za-z0-9_]+)/", line)
        if not m or m.group(1) not in per:
            continue
        for kind, needle in WARNING_KINDS:
            if needle in line:
                detail = INPUT_RE.search(line)
                per[m.group(1)][kind].add(detail.group(1) if detail else line.strip()[-60:])
                break

    clean = [n for n, w in per.items() if not any(w.values())]
    missing = [n for n, w in per.items() if w["missing"]]
    lost_out = [n for n, w in per.items() if w["output"] and not w["missing"]]
    lost_in = [n for n, w in per.items() if (w["input"] or w["connection"])
               and not w["missing"] and not w["output"]]

    print("routed nodedefs        : %d (+%d not wirable: material/light outputs)" % (n, len(skipped)))
    print("clean, every input kept: %d" % len(clean))
    print("inputs dropped         : %d" % len(lost_in))
    print("output not found       : %d" % len(lost_out))
    print("node missing           : %d" % len(missing))
    if not os.path.exists(exr):
        print("\nNO IMAGE - last log lines:")
        print("\n".join(log.strip().splitlines()[-5:]))
    if want_list:
        for title, names in (("INPUTS DROPPED", lost_in), ("OUTPUT NOT FOUND", lost_out),
                             ("NODE MISSING", missing)):
            if not names:
                continue
            print("\n%s (%d):" % (title, len(names)))
            for name in sorted(names):
                w = per[name]
                detail = ", ".join(sorted(w["input"] | w["connection"] | w["output"]))
                print("   %-44s %s" % (name, detail[:90]))


if __name__ == "__main__":
    main()
