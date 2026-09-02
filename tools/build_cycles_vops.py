"""Construit la bibliothèque de nœuds VOP Cycles pour Houdini.

Le delegate publie déjà les nœuds Cycles au registre Sdr, ce qui les rend
lisibles par USD — mais pas posables dans un Material Builder. Houdini attend
pour cela de vrais types de nœuds VOP.

Aucun traducteur Python n'est nécessaire. Un VOP de nuanceur se décrit
entièrement par son DialogScript : `rendermask` dit à quel moteur il
appartient, `externalshader` qu'il ne se compile pas, et trois paramètres
réservés disent au traducteur par défaut de Solaris quel prim USD écrire. C'est
la forme des nœuds MaterialX livrés par Houdini, relevée dans `MaterialX.hda`.

À lancer avec hython — aucune licence requise, contrairement à husk :

    hython tools/build_cycles_vops.py [--sample]

La bibliothèque est écrite dans l'arborescence **installée**, la seule que
Houdini charge via le package `cycles.json`.
"""

import os
import sys

import hou
from pxr import Sdr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OTLS = os.path.join(ROOT, "install", "houdini", "otls")
LIBRARY = os.path.join(OTLS, "cycles_vops.hda")

RENDER_CONTEXT = "cycles"
PREFIX = "cycles_"

SAMPLE = ["cycles_principled_bsdf", "cycles_image_texture", "cycles_noise_texture",
          "cycles_math", "cycles_mix_color"]

# Type Sdr -> (connecteur DialogScript, type de paramètre, nb de composantes)
TYPES = {
    "float": ("float", "float", 1),
    "int": ("int", "int", 1),
    "string": ("ustring", "string", 1),
    "color": ("color", "color", 3),
    "point": ("point", "vector", 3),
    "normal": ("normal", "vector", 3),
    "vector": ("vector", "vector", 3),
    "matrix": ("matrix", "float", 16),
    "terminal": ("bsdf", None, 0),
}

# Un paramètre ne peut pas porter le nom d'un type : le contexte VOP les
# réserve et l'actif refuse alors de s'instancier. Mesuré sur `vector`.
RESERVED = {"vector", "float", "color", "normal", "point", "matrix", "string",
            "int", "bsdf", "struct", "surface", "displacement", "light"}


def parm_name(socket):
    return "cy_" + socket if socket in RESERVED else socket


def escape(text):
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def default_literal(prop, components):
    value = prop.GetDefaultValue()
    kind = str(prop.GetType())
    if value is None:
        return '""' if kind == "string" else " ".join(["0"] * max(components, 1))
    if components > 1:
        try:
            return " ".join("%g" % float(v) for v in list(value)[:components])
        except TypeError:
            return " ".join(["%g" % float(value)] * components)
    if kind == "string":
        return '"%s"' % escape(value)
    if kind == "int":
        return "%d" % int(value)
    return "%g" % float(value)


def shader_type(sdr_node):
    """Ce que le nœud produit, ce qui décide de sa place dans le menu."""
    for name in sdr_node.GetShaderOutputNames():
        if str(sdr_node.GetShaderOutput(name).GetType()) == "terminal":
            return "surface"
    return "generic"


def usable(prop):
    """Cycles publie son bloc de placement en sockets pointés
    (`tex_mapping.translation`) : un point est illégal dans un nom de
    paramètre. Les sockets tableau sont écartés de même."""
    return "." not in prop.GetName() and prop.GetArraySize() == 0


def dialog_script(node_id, sdr_node):
    inputs = [n for n in sdr_node.GetShaderInputNames() if usable(sdr_node.GetShaderInput(n))]
    outputs = [n for n in sdr_node.GetShaderOutputNames() if usable(sdr_node.GetShaderOutput(n))]
    label = "Cycles " + sdr_node.GetName().replace("_", " ").title()

    out = ["{", "    name\t%s" % node_id, "    script\t%s" % node_id,
           '    label\t"%s"' % escape(label), "",
           "    rendermask\t%s" % RENDER_CONTEXT,
           "    shadertype\t%s" % shader_type(sdr_node),
           "    externalshader\t1", ""]

    for name in inputs:
        prop = sdr_node.GetShaderInput(name)
        conn = TYPES.get(str(prop.GetType()), ("float", "float", 1))[0]
        out.append('    input\t%s\t%s\t"%s"' % (conn, parm_name(name),
                                                escape(prop.GetLabel() or name)))
    for name in outputs:
        prop = sdr_node.GetShaderOutput(name)
        conn = TYPES.get(str(prop.GetType()), ("float", "float", 1))[0]
        # Une sortie garde son nom tel quel : c'est celui que le delegate
        # cherche côté Cycles, et l'étiquette qui rétablit le nom réel ne vaut
        # que pour les paramètres, qu'une sortie n'est pas.
        out.append('    output\t%s\t%s\t"%s"' % (conn, name,
                                                 escape(prop.GetLabel() or name)))
    out.append("")

    for name in inputs:
        prop = sdr_node.GetShaderInput(name)
        conn, ptype, comps = TYPES.get(str(prop.GetType()), ("float", "float", 1))
        if ptype is None:
            continue
        out.append("    parm {")
        out.append('        name    "%s"' % parm_name(name))
        out.append('        label   "%s"' % escape(prop.GetLabel() or name))
        out.append("        type    %s" % ptype)
        if comps > 1 and ptype != "color":
            out.append("        size    %d" % comps)
        out.append("        default { %s }" % default_literal(prop, comps))
        # Le nom réel du socket Cycles, que le traducteur écrira en USD.
        if parm_name(name) != name:
            out.append('        parmtag { "sidefx::shader_parmname" "%s" }' % name)
        out.append("    }")

    # Les trois paramètres que lit le traducteur par défaut de Solaris.
    for pname, value in (("shader_rendercontextname", RENDER_CONTEXT),
                         ("shader_name", node_id),
                         ("shader_namekind", "id")):
        out.append("    parm {")
        out.append('        name    "%s"' % pname)
        out.append('        label   "%s"' % pname)
        out.append("        type    string")
        out.append('        default { "%s" }' % value)
        out.append("        invisible")
        out.append("    }")

    out.append("}")
    return "\n".join(out) + "\n"


def template_definition():
    """La définition dont on hérite l'opérateur de base.

    Un nuanceur externe est une feuille, pas un réseau : bâti sur un `subnet`,
    l'actif s'exporte en NodeGraph et non en Shader, et `genericshader` refuse
    d'être converti en actif. On copie donc un nœud de nuanceur externe déjà
    livré par Houdini, dont on ne garde que la nature — tout le reste, interface
    comprise, est remplacé par le DialogScript généré.
    """
    node_type = hou.nodeType(hou.vopNodeTypeCategory(), "mtlximage")
    if node_type is None or node_type.definition() is None:
        raise RuntimeError("nœud modèle mtlximage introuvable")
    return node_type.definition()


def build_one(node_id, sdr_node, template):
    template.copyToHDAFile(LIBRARY, new_name=node_id, new_menu_name=node_id)
    hou.hda.installFile(LIBRARY)
    node_type = hou.nodeType(hou.vopNodeTypeCategory(), node_id)
    definition = node_type.definition()
    definition.addSection("DialogScript", dialog_script(node_id, sdr_node))
    definition.save(LIBRARY)


def main():
    only_sample = "--sample" in sys.argv
    registry = Sdr.Registry()
    ids = sorted(str(i) for i in registry.GetShaderNodeIdentifiers()
                 if str(i).startswith(PREFIX))
    if only_sample:
        ids = [i for i in ids if i in SAMPLE]

    if not os.path.isdir(OTLS):
        os.makedirs(OTLS)
    if os.path.exists(LIBRARY):
        os.remove(LIBRARY)
    print("bibliotheque : %s" % LIBRARY)
    print("noeuds a generer : %d" % len(ids))

    template = template_definition()

    built, failed = 0, []
    for node_id in ids:
        sdr_node = registry.GetShaderNodeByIdentifier(node_id)
        if sdr_node is None:
            failed.append((node_id, "absent du registre"))
            continue
        try:
            build_one(node_id, sdr_node, template)
            built += 1
        except hou.Error as exc:
            failed.append((node_id, str(exc).replace("\n", " ")[:60]))

    print("%d noeuds ecrits, %d echecs" % (built, len(failed)))
    for node_id, why in failed[:10]:
        print("   %-34s %s" % (node_id, why))


if __name__ == "__main__":
    main()
