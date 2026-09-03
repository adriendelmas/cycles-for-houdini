"""Exporte un materiau par noeud VOP Cycles, monte dans Houdini.

Le but est de passer par la vraie chaine - VOP, traducteur de Solaris, USD -
et pas par de l'USD ecrit a la main, sans quoi on ne teste pas les noeuds
generes mais seulement le delegate.
"""

import os
import sys

import hou
from pxr import Sdr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Quelle installation viser : `install` pour la 5.2, `install-53` pour la 5.3.
INSTALL = os.environ.get("CYCLES_INSTALL_DIR", "install")
sys.path.insert(0, os.path.join(ROOT, INSTALL, "houdini", "scripts", "python"))
hou.hda.installFile(os.path.join(ROOT, INSTALL, "houdini", "otls", "cycles_vops.hda"))
import cycles_builder  # noqa: E402

OUT = os.path.join(ROOT, "tests", "usd", "bench" if INSTALL == "install" else "bench-53")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

# Le noeud terminal et la sortie du graphe ne se testent pas comme un shader.
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
        note = "aucune sortie"
    else:
        # Une fermeture remplace la surface; tout le reste nourrit sa couleur.
        # Le type Sdr tranche, pas le nom de la sortie: `emission` sort
        # "emission" et subsurface_scattering sort "BSSRDF", tous deux des
        # fermetures qu'un test guide par le nom envoie sur la couleur de base,
        # ou elles ne font rien.
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
                note = "ferme -> surface"
            else:
                surface.setInput(surface.inputNames().index("base_color"), node, 0)
                note = "%s -> base_color" % outs[0]
        except (hou.Error, ValueError) as exc:
            note = "BRANCHEMENT: %s" % str(exc).replace(chr(10), " ")[:40]

    lib.setDisplayFlag(True)
    path = os.path.join(OUT, typename + ".usda")
    try:
        lib.stage().Export(path)
    except Exception as exc:
        report.append((typename, "EXPORT", str(exc)[:50]))
        continue

    text = open(path, encoding="utf-8").read()
    has_id = 'info:id = "%s"' % typename in text
    # Un noeud de fermeture peut desormais terminer en surface, en
    # displacement ou en volume selon ce qu'il est reellement (voir
    # OUTPUT_KIND_OVERRIDES dans build_cycles_vops.py) - peu importe lequel,
    # tant que le materiau exporte un vrai terminal.
    has_mat = any(("outputs:cycles:%s" % role) in text
                 for role in ("surface", "displacement", "volume"))
    report.append((typename, "ok" if (has_id and has_mat) else "INCOMPLET",
                   "%s%s%s" % (note,
                               "" if has_id else " | pas d'info:id",
                               "" if has_mat else " | pas de terminal")))

print("%-34s %-10s %s" % ("noeud", "etat", "detail"))
bad = 0
for name, state, detail in report:
    if state != "ok":
        bad += 1
    print("%-34s %-10s %s" % (name, state, detail))
print("\n%d exportes, %d problemes" % (len(report), bad))
