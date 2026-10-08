"""Does every MaterialX value node give what Karma gives?

One grid, one quad per value nodedef the delegate renders, rendered by Cycles
and by Karma from the same file. Each quad shows the node's output through a
`surface_unlit` - the value reaches the image as it is, with no light and no
noise in between - after a `convert` to colour3 for the other output types.
Inputs are authored: their default, or a witness value where the default is
zero, so that a node does something (a `multiply` by its zero default shows
nothing). Inputs read from the geometry (texcoord, position...) are left to
it, so textures vary over the quad and are compared on their mean.

With --closures, the BSDF, EDF and surface nodedefs instead: each quad a
`surface` over the BSDF or EDF (a surface shader is the terminal itself), lit
by the uniform white dome both engines agree on, and compared within 10 %.

A quad whose mean differs beyond TOL is listed. Not every difference is the
delegate's: noise and cellular functions are each engine's own, and are
reported apart. Everything else is a translation to look at.

    hython tools/mtlx_karma.py [--list] [--closures] [pattern]

Scenes and images go to tests/materialx/output/karma/.
"""

import math
import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mtlx_inputs  # noqa: E402  (loads the library, shares the routing rule)

ROOT = mtlx_inputs.ROOT
HFS = mtlx_inputs.HFS
OUT = os.path.join(ROOT, "tests", "materialx", "output", "karma")

VALUE_TYPES = {"float", "integer", "boolean", "color3", "color4", "vector2", "vector3", "vector4"}
QUAD_PX = 48
TOL_ABS = 0.02
TOL_REL = 0.05
# Each engine has its own noise and cellular functions: a difference there
# says nothing about the translation.
ENGINE_OWN = ("noise", "fractal", "cellnoise", "worley", "unifiednoise", "randomfloat",
              "randomcolor", "hash")
WITNESS = {"float": "0.37", "color3": "0.6, 0.3, 0.15", "color4": "0.6, 0.3, 0.15, 0.8",
           "vector2": "0.6, 0.3", "vector3": "0.6, 0.3, 0.15", "vector4": "0.6, 0.3, 0.15, 0.8"}


def is_zero(text):
    try:
        return all(float(p) == 0.0 for p in text.split(","))
    except ValueError:
        return False


def block(nd, library):
    """The material for one nodedef, or None when its output cannot be shown."""
    name = nd.getName()
    out = nd.getActiveOutputs()[0]
    out_type = out.getType()
    convert = None
    if out_type != "color3":
        convert = "ND_convert_%s_color3" % out_type
        if library.getNodeDef(convert) is None:
            return None
    probe = ['uniform token info:id = "%s"' % name]
    for inp in nd.getActiveInputs():
        t = inp.getType()
        if t in mtlx_inputs.CLOSURES or inp.getName() == "note":
            continue
        if inp.getDefaultGeomPropString() or not inp.getValueString():
            continue
        text = inp.getValueString()
        if t in WITNESS and is_zero(text) and not inp.getIsUniform():
            text = WITNESS[t]
        usd_t, literal = mtlx_inputs.usd_value(t, text)
        if usd_t is None:
            continue
        uniform = "uniform " if inp.getIsUniform() else ""
        probe.append("%s%s inputs:%s = %s" % (uniform, usd_t, inp.getName(), literal))
    for o in nd.getActiveOutputs():
        probe.append("%s outputs:%s" % (mtlx_inputs.USD_OUT_TYPE.get(o.getType(), "token"),
                                        o.getName()))
    base = "/world/Materials/%s" % name
    shown = "%s/probe.outputs:%s" % (base, out.getName())
    lines = ["token outputs:mtlx:surface.connect = <%s/surf.outputs:out>" % base,
             'def Shader "surf" {',
             '    uniform token info:id = "ND_surface_unlit"',
             "    color3f inputs:emission_color.connect = <%s>" % (
                 "%s/conv.outputs:out" % base if convert else shown),
             "    token outputs:out",
             "}",
             'def Shader "probe" {'] + ["    " + p for p in probe] + ["}"]
    if convert:
        lines += ['def Shader "conv" {',
                  '    uniform token info:id = "%s"' % convert,
                  "    %s inputs:in.connect = <%s>" % (
                      mtlx_inputs.USD_OUT_TYPE.get(out_type, "float"), shown),
                  "    color3f outputs:out",
                  "}"]
    return "\n".join("            " + l for l in lines)


CLOSURE_TYPES = {"BSDF", "EDF", "surfaceshader"}
CLOSURE_TOL_REL = 0.10


def closure_block(nd):
    """The material for one closure nodedef: under a `surface`, or the terminal."""
    name = nd.getName()
    out = nd.getActiveOutputs()[0]
    probe = ['uniform token info:id = "%s"' % name]
    for inp in nd.getActiveInputs():
        t = inp.getType()
        if t in mtlx_inputs.CLOSURES or inp.getName() == "note":
            continue
        if inp.getDefaultGeomPropString() or not inp.getValueString():
            continue
        usd_t, literal = mtlx_inputs.usd_value(t, inp.getValueString())
        if usd_t is None:
            continue
        uniform = "uniform " if inp.getIsUniform() else ""
        probe.append("%s%s inputs:%s = %s" % (uniform, usd_t, inp.getName(), literal))
    probe.append("token outputs:%s" % out.getName())
    base = "/world/Materials/%s" % name
    if out.getType() == "surfaceshader":
        lines = ["token outputs:mtlx:surface.connect = <%s/probe.outputs:%s>" % (base, out.getName())]
    else:
        socket = "bsdf" if out.getType() == "BSDF" else "edf"
        lines = ["token outputs:mtlx:surface.connect = <%s/surf.outputs:out>" % base,
                 'def Shader "surf" {',
                 '    uniform token info:id = "ND_surface"',
                 "    token inputs:%s.connect = <%s/probe.outputs:%s>" % (socket, base, out.getName()),
                 "    token outputs:out",
                 "}"]
    lines += ['def Shader "probe" {'] + ["    " + p for p in probe] + ["}"]
    return "\n".join("            " + l for l in lines)


def render(renderer, scene_path, exr):
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    run = subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer,
                          "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                          "-s", "/Render/settings", "--output", exr, scene_path],
                         capture_output=True, text=True, env=env, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    if buf.has_error:
        sys.stderr.write((run.stdout or "")[-2000:] + (run.stderr or "")[-2000:])
        return None
    return buf.get_pixels(oiio.FLOAT)


def cell_mean(img, i, cols):
    c, r = i % cols, i // cols
    rows = img.shape[0]
    x0, x1 = int((c + 0.15) * QUAD_PX), int((c + 0.75) * QUAD_PX)
    y1, y0 = rows - int((r + 0.15) * QUAD_PX), rows - int((r + 0.75) * QUAD_PX)
    return img[y0:y1, x0:x1, :3].reshape(-1, 3).mean(axis=0)


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    want_list = "--list" in sys.argv
    closures = "--closures" in sys.argv
    pattern = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    library = mtlx_inputs.DOC
    blocks = []
    for nd in mtlx_inputs.routed_nodedefs():
        outs = nd.getActiveOutputs()
        if not outs or outs[0].getType() not in (CLOSURE_TYPES if closures else VALUE_TYPES):
            continue
        if pattern and pattern not in nd.getName():
            continue
        b = closure_block(nd) if closures else block(nd, library)
        if b is not None:
            blocks.append((nd, b))
    cols = max(1, int(math.ceil(math.sqrt(len(blocks)))))
    quads = []
    for i, (nd, _) in enumerate(blocks):
        c, r = i % cols, i // cols
        quads.append(mtlx_inputs.QUAD % {"i": i, "name": nd.getName(), "x0": c, "x1": c + 0.9,
                                         "y0": r, "y1": r + 0.9})
    materials = "\n".join('        def Material "%s"\n        {\n%s\n        }' % (nd.getName(), b)
                          for nd, b in blocks)
    scene = mtlx_inputs.HEAD % {"res": cols * QUAD_PX, "aperture": cols * 10, "center": cols / 2.0,
                                "quads": "".join(quads), "materials": materials}
    if closures:
        # A lit BSDF needs samples; the dome is the light both agree on.
        scene = scene.replace("int cycles:samples = 1",
                              "int cycles:samples = 64\n        int karma:global:pixelsamples = 64")
    scene_path = os.path.join(OUT, "closures.usda" if closures else "grid.usda")
    open(scene_path, "w", encoding="utf-8").write(scene)

    cyc = render("HdCyclesPlugin", scene_path, os.path.join(OUT, "cycles.exr"))
    kar = render("BRAY_HdKarma", scene_path, os.path.join(OUT, "karma.exr"))
    if cyc is None or kar is None:
        print("NO IMAGE (%s)" % ("Cycles" if cyc is None else "Karma"))
        sys.exit(1)

    same, own, differ = [], [], []
    for i, (nd, _) in enumerate(blocks):
        a, b = cell_mean(cyc, i, cols), cell_mean(kar, i, cols)
        rel = CLOSURE_TOL_REL if closures else TOL_REL
        bad = np.abs(a - b) > np.maximum(TOL_ABS, rel * np.abs(b))
        if not bad.any():
            same.append(nd.getName())
        elif nd.getNodeString().startswith(ENGINE_OWN) or any(k in nd.getNodeString()
                                                                for k in ENGINE_OWN):
            own.append((nd.getName(), a, b))
        else:
            differ.append((nd.getName(), a, b))
    print("%s nodedefs compared : %d" % ("closure" if closures else "value", len(blocks)))
    print("same as Karma           : %d" % len(same))
    print("differ, engine's own    : %d (noise, cellular, random)" % len(own))
    print("differ                  : %d" % len(differ))
    if want_list:
        for name, a, b in sorted(differ):
            print("   %-40s cycles %7.3f %7.3f %7.3f  karma %7.3f %7.3f %7.3f"
                  % ((name,) + tuple(a) + tuple(b)))
    sys.exit(1 if differ else 0)


if __name__ == "__main__":
    main()
