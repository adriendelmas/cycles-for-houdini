"""Exports one material per Cycles VOP node, built inside Houdini.

The point is to go through the real chain - VOP, Solaris translator, USD -
and not through hand-written USD, otherwise it is not the generated nodes
that get tested but only the delegate.
"""

import os
import sys

import hou
from pxr import Sdr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Which installation to target (Cycles 5.3, installed in `install-53`).
INSTALL = os.environ.get("CYCLES_INSTALL_DIR", "install-53")
sys.path.insert(0, os.path.join(ROOT, INSTALL, "houdini", "scripts", "python"))
hou.hda.installFile(os.path.join(ROOT, INSTALL, "houdini", "otls", "cycles_vops.hda"))
import cycles_builder  # noqa: E402

VERSION = "5.3"
OUT = os.path.join(ROOT, "tests", "nodes", VERSION)
if not os.path.isdir(OUT):
    os.makedirs(OUT)

# The terminal node and the graph output are not tested like a shader.
SKIP = {"cycles_material", "cycles_output", "cycles_aov_output"}

cat = hou.vopNodeTypeCategory()
names = sorted(n for n in cat.nodeTypes()
               if n.startswith("cycles_") and n not in SKIP)

report = []
for typename in names:
    stage = hou.node("/stage")
    for c in stage.children():
        c.destroy()
    lib = stage.createNode("materiallibrary")
    lib.parm("matpathprefix").set("/world/Materials/")
    sub = lib.createNode("subnet", "cyclesmat")
    cycles_builder.setup(sub)
    surface = sub.node("surface")

    try:
        node = sub.createNode(typename, "probe")
    except hou.Error as exc:
        report.append((typename, "CREATION", str(exc).replace(chr(10), " ")[:50]))
        continue

    outs = node.outputNames()
    note = ""
    if not outs:
        note = "no output"
    else:
        # A closure replaces the surface; everything else feeds its color.
        # The Sdr type decides, not the output name: `emission` outputs
        # "emission" and subsurface_scattering outputs "BSSRDF", both of them
        # closures that a name-driven test would send to the base color,
        # where they do nothing.
        sdr_node = Sdr.Registry().GetShaderNodeByIdentifier(typename)
        closure = False
        if sdr_node is not None:
            for out_name in sdr_node.GetShaderOutputNames():
                if str(sdr_node.GetShaderOutput(out_name).GetType()) == "terminal":
                    closure = True
                    break
        try:
            if closure:
                terminal = sub.node("outputs")
                terminal.setInput(0, node, 0)
                surface.destroy()
                note = "closure -> surface"
            else:
                surface.setInput(surface.inputNames().index("base_color"), node, 0)
                note = "%s -> base_color" % outs[0]
        except (hou.Error, ValueError) as exc:
            note = "WIRING: %s" % str(exc).replace(chr(10), " ")[:40]

    lib.setDisplayFlag(True)
    path = os.path.join(OUT, typename + ".usda")
    try:
        lib.stage().Export(path)
    except Exception as exc:
        report.append((typename, "EXPORT", str(exc)[:50]))
        continue

    text = open(path, encoding="utf-8").read()
    has_id = 'info:id = "%s"' % typename in text
    # A closure node can now end as a surface, a displacement or a volume
    # depending on what it really is (see OUTPUT_KIND_OVERRIDES in
    # build_cycles_vops.py) - it does not matter which, as long as the
    # material exports a real terminal.
    has_mat = any(("outputs:cycles:%s" % role) in text
                 for role in ("surface", "displacement", "volume"))
    report.append((typename, "ok" if (has_id and has_mat) else "INCOMPLETE",
                   "%s%s%s" % (note,
                               "" if has_id else " | no info:id",
                               "" if has_mat else " | no terminal")))

print("%-34s %-10s %s" % ("node", "state", "detail"))
bad = 0
for name, state, detail in report:
    if state != "ok":
        bad += 1
    print("%-34s %-10s %s" % (name, state, detail))
print("\n%d exported, %d problems" % (len(report), bad))
