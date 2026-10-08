"""Does a MaterialX node render the same with its inputs left unwritten?

Hydra forwards only the parameters Houdini authored, and Houdini authors only
the ones the user touched: an input left at its MaterialX default reaches the
delegate as nothing at all, and the Cycles node then keeps its own default -
which is not always the same number. `modulo` divides by 1 in MaterialX and
by 0.5 on an untouched math node; a `clamp` runs 0..1 in both. The surface
models have `mtlx_defaults.py` for this; here it is every value nodedef the
delegate renders.

Two grids, one quad per nodedef, rendered the way `mtlx_inputs.py` does: in
the first the probe has no input authored, in the second every input that has
a default in the nodedef is authored with it. A nodedef whose two quads differ
has an input whose Cycles default is not its MaterialX one - a pinned default
missing in the mapping.

    hython tools/mtlx_pinned.py [--list] [pattern]

Scenes and images go to tests/materialx/output/pinned/.
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
OUT = os.path.join(ROOT, "tests", "materialx", "output", "pinned")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

VALUE_TYPES = {"float", "integer", "boolean", "color3", "color4", "vector2", "vector3", "vector4"}
SAMPLES = 16
QUAD_PX = 64  # pixels per grid cell
TOL = 0.02


def block(nd, author):
    """The probe material: inputs authored at the nodedef's defaults, or none."""
    name = nd.getName()
    outputs = nd.getActiveOutputs()
    out = outputs[0]
    probe = ['uniform token info:id = "%s"' % name]
    if author:
        for inp in nd.getActiveInputs():
            t = inp.getType()
            if t in mtlx_inputs.CLOSURES or inp.getName() == "note":
                continue
            # No default means "read the geometry" (texcoord) or "nothing"
            # (a file): authoring a zero there would change the meaning.
            if not inp.getValueString():
                continue
            usd_t, literal = mtlx_inputs.usd_value(t, inp.getValueString())
            if usd_t is None:
                continue
            probe.append("%s inputs:%s = %s" % (usd_t, inp.getName(), literal))
    for o in outputs:
        probe.append("%s outputs:%s" % (mtlx_inputs.USD_OUT_TYPE.get(o.getType(), "token"), o.getName()))
    base = "/world/Materials/%s" % name
    lines = ["token outputs:mtlx:surface.connect = <%s/surf.outputs:out>" % base,
             'def Shader "surf" {',
             '    uniform token info:id = "ND_standard_surface_surfaceshader"',
             "    float inputs:specular = 0",
             "    color3f inputs:base_color.connect = <%s/probe.outputs:%s>" % (base, out.getName()),
             "    token outputs:out",
             "}",
             'def Shader "probe" {'] + ["    " + p for p in probe] + ["}"]
    return "\n".join("            " + l for l in lines)


def render(tag, blocks, cols):
    quads = []
    for i, (name, _) in enumerate(blocks):
        c, r = i % cols, i // cols
        quads.append(mtlx_inputs.QUAD % {"i": i, "name": name, "x0": c, "x1": c + 0.9,
                                         "y0": r, "y1": r + 0.9})
    materials = "\n".join('        def Material "%s"\n        {\n%s\n        }' % (name, b)
                          for name, b in blocks)
    # A USD orthographic aperture is in tenths of a scene unit: the view spans
    # the whole grid, one cell per QUAD_PX pixels.
    scene = mtlx_inputs.HEAD % {"res": cols * QUAD_PX, "aperture": cols * 10, "center": cols / 2.0,
                                "quads": "".join(quads), "materials": materials}
    scene = scene.replace("int cycles:samples = 1", "int cycles:samples = %d" % SAMPLES)
    scene_path = os.path.join(OUT, tag + ".usda")
    open(scene_path, "w", encoding="utf-8").write(scene)
    exr = os.path.join(OUT, tag + ".exr")
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                    "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                    "-s", "/Render/settings", "--output", exr, scene_path],
                   capture_output=True, text=True, env=env, cwd=OUT)
    buf = oiio.ImageBuf(exr)
    return None if buf.has_error else buf.get_pixels(oiio.FLOAT)


def cell_mean(img, i, cols):
    """Mean colour of the inner part of quad i; the image's y runs downward."""
    c, r = i % cols, i // cols
    rows = img.shape[0]
    x0 = int((c + 0.1) * QUAD_PX)
    x1 = int((c + 0.8) * QUAD_PX)
    y1 = rows - int((r + 0.1) * QUAD_PX)
    y0 = rows - int((r + 0.8) * QUAD_PX)
    return img[y0:y1, x0:x1, :3].reshape(-1, 3).mean(axis=0)


def main():
    want_list = "--list" in sys.argv
    pattern = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    nodedefs = [nd for nd in mtlx_inputs.routed_nodedefs()
                if nd.getActiveOutputs() and nd.getActiveOutputs()[0].getType() in VALUE_TYPES
                and (not pattern or pattern in nd.getName())]
    blocks_bare = [(nd.getName(), block(nd, False)) for nd in nodedefs]
    blocks_full = [(nd.getName(), block(nd, True)) for nd in nodedefs]
    cols = max(1, int(math.ceil(math.sqrt(len(nodedefs)))))

    bare = render("bare", blocks_bare, cols)
    full = render("authored", blocks_full, cols)
    if bare is None or full is None:
        print("NO IMAGE")
        sys.exit(1)

    differing = []
    for i, nd in enumerate(nodedefs):
        a, b = cell_mean(bare, i, cols), cell_mean(full, i, cols)
        if np.abs(a - b).max() > TOL:
            differing.append((nd.getName(), a, b))
    print("value nodedefs rendered : %d" % len(nodedefs))
    print("same bare and authored  : %d" % (len(nodedefs) - len(differing)))
    print("differ (a pinned default missing): %d" % len(differing))
    if want_list:
        for name, a, b in sorted(differing):
            print("   %-44s bare %.3f %.3f %.3f  authored %.3f %.3f %.3f"
                  % ((name,) + tuple(a) + tuple(b)))
    sys.exit(1 if differing else 0)


if __name__ == "__main__":
    main()
