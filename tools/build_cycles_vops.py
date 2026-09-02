"""Construit la bibliothèque de nœuds VOP Cycles pour Houdini.

Le delegate publie déjà les nœuds Cycles au registre Sdr, ce qui les rend
lisibles par USD — mais pas posables dans un Material Builder. Houdini attend
pour cela de vrais types de nœuds VOP.

Aucun traducteur Python n'est nécessaire. Le traducteur par défaut de Solaris
sait écrire le prim USD à partir de trois paramètres réservés portés par le
nœud : le contexte de rendu, l'identifiant du nuanceur, et la façon de
l'interpréter. C'est le mécanisme documenté dans
`husdplugins/shadertranslators/default.py`, et celui que Houdini emploie pour
ses propres nœuds MaterialX.

À lancer avec hython — aucune licence n'est requise, contrairement à husk :

    hython tools/build_cycles_vops.py [--all]

Sans `--all`, seul un échantillon est généré : de quoi vérifier la chaîne de
bout en bout sans attendre les 163 nœuds.

ÉTAT : INCOMPLET. Les nœuds se génèrent et s'instancient, avec leurs
connecteurs d'entrée et de sortie. Il leur manque leurs **paramètres**, donc
ils ne servent pas encore à shader. Ce qui reste à faire, et ce qui a été
mesuré en chemin :

* Les `subnetconnector` ne promeuvent aucun paramètre dans ce flux sans
  interface — `parmTemplateGroup()` reste vide après leur création. Les
  paramètres doivent donc être posés explicitement sur le subnet, un par
  socket, avec leur valeur par défaut Cycles.
* Un paramètre ne peut pas s'appeler `vector` : le contexte VOP réserve les
  noms de types, et l'actif refuse alors de s'instancier. Mesuré : le même
  connecteur nommé `coords` passe. Il faut donc préfixer les noms et rendre le
  nom USD réel par l'étiquette `sidefx::shader_parmname`.
* Le masque de rendu n'est pas posé par `setExtraFileOption("RenderMask", …)`,
  qui est sans effet. À trouver ailleurs.
"""

import os
import sys

import hou
from pxr import Sdr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OTLS = os.path.join(ROOT, "external", "cycles", "src", "hydra", "resources", "otls")
LIBRARY = os.path.join(OTLS, "cycles_vops.hda")

RENDER_CONTEXT = "cycles"
PREFIX = "cycles_"

# Un échantillon représentatif : une surface, une texture, un procédural et
# deux utilitaires, ce qui exerce tous les types de sockets rencontrés.
SAMPLE = [
    "cycles_principled_bsdf",
    "cycles_image_texture",
    "cycles_noise_texture",
    "cycles_math",
    "cycles_mix_color",
]

# Type de socket Sdr -> jeton de connecteur VOP. Les jetons proviennent du menu
# de `subnetconnector` ; en inventer un fait échouer l'instanciation de l'actif.
CONNECTOR_TYPES = {
    "float": "float",
    "int": "int",
    "string": "string",
    "color": "color",
    "point": "point",
    "normal": "normal",
    "vector": "vector",
    "matrix": "float16",
    "terminal": "bsdf",
}


def connector_type(prop):
    return CONNECTOR_TYPES.get(str(prop.GetType()), "float")


def usable(prop):
    """Un socket que l'on peut exposer en connecteur VOP.

    Cycles publie son bloc de placement de texture en sockets pointés
    (`tex_mapping.translation`), or un point est illégal dans un nom de
    paramètre Houdini. Ces entrées sont écartées, comme les sockets tableau que
    la traduction ne gère de toute façon pas.
    """
    return "." not in prop.GetName() and prop.GetArraySize() == 0


def add_connector(subnet, prop, index, is_output):
    """Un subnetconnector est ce qui donne au VOP une entrée ou une sortie."""
    name = prop.GetName()
    node = subnet.createNode("subnetconnector",
                             ("out_" if is_output else "in_") + name)
    node.parm("parmname").set(name)
    node.parm("parmlabel").set(prop.GetLabel() or name)
    node.parm("parmtype").set(connector_type(prop))
    node.parm("connectorkind").set("output" if is_output else "input")
    node.setPosition(hou.Vector2(6.0 if is_output else 0.0, -index * 0.9))
    return node


def add_spare_strings(node, values):
    """Pose les paramètres réservés que lit le traducteur de Solaris."""
    group = node.parmTemplateGroup()
    for name, value in values:
        group.append(hou.StringParmTemplate(name, name, 1, default_value=(value,)))
    node.setParmTemplateGroup(group)


def apply_defaults(node, sdr_node):
    """Reporte les valeurs par défaut de Cycles sur les paramètres promus.

    Sans ça chaque entrée partirait à zéro, et un matériau fraîchement posé ne
    ressemblerait pas à ce que Cycles rend par défaut.
    """
    applied = 0
    for name in sdr_node.GetShaderInputNames():
        if not usable(sdr_node.GetShaderInput(name)):
            continue
        parm = node.parm(name) or node.parmTuple(name)
        if parm is None:
            continue
        value = sdr_node.GetShaderInput(name).GetDefaultValue()
        if value is None:
            continue
        try:
            if isinstance(parm, hou.ParmTuple):
                parm.set(tuple(value))
            else:
                parm.set(value)
            applied += 1
        except (hou.OperationFailed, TypeError, ValueError):
            pass
    return applied


def build_one(parent, node_id, sdr_node):
    subnet = parent.createNode("subnet", node_id)
    for child in subnet.children():
        child.destroy()

    inputs = [n for n in sdr_node.GetShaderInputNames() if usable(sdr_node.GetShaderInput(n))]
    outputs = [n for n in sdr_node.GetShaderOutputNames() if usable(sdr_node.GetShaderOutput(n))]
    for i, name in enumerate(inputs):
        add_connector(subnet, sdr_node.GetShaderInput(name), i, False)
    for i, name in enumerate(outputs):
        add_connector(subnet, sdr_node.GetShaderOutput(name), i, True)

    add_spare_strings(subnet, [
        ("shader_rendercontextname", RENDER_CONTEXT),
        ("shader_name", node_id),
        ("shader_namekind", "id"),
    ])
    defaults = apply_defaults(subnet, sdr_node)

    asset = subnet.createDigitalAsset(
        name=node_id,
        hda_file_name=LIBRARY,
        description="Cycles " + sdr_node.GetName().replace("_", " "),
        min_num_inputs=0,
        max_num_inputs=max(len(inputs), 1),
        ignore_external_references=True,
    )
    definition = asset.type().definition()
    definition.setExtraFileOption("RenderMask", RENDER_CONTEXT)
    return asset, "%d entrées, %d sorties, %d défauts" % (len(inputs), len(outputs), defaults)


def main():
    everything = "--all" in sys.argv
    registry = Sdr.Registry()
    ids = sorted(str(i) for i in registry.GetShaderNodeIdentifiers()
                 if str(i).startswith(PREFIX))
    if not everything:
        ids = [i for i in ids if i in SAMPLE]

    if not os.path.isdir(OTLS):
        os.makedirs(OTLS)
    print("bibliothèque : %s" % LIBRARY)
    print("nœuds à générer : %d%s" % (len(ids), "" if everything else " (échantillon)"))

    stage = hou.node("/stage")
    for child in stage.children():
        child.destroy()
    lib = stage.createNode("materiallibrary")

    built = 0
    for node_id in ids:
        sdr_node = registry.GetShaderNodeByIdentifier(node_id)
        if sdr_node is None:
            print("   %-34s absent du registre" % node_id)
            continue
        try:
            _, note = build_one(lib, node_id, sdr_node)
            built += 1
            print("   %-34s %s" % (node_id, note))
        except hou.Error as exc:
            print("   %-34s ECHEC: %s" % (node_id, str(exc).replace("\n", " ")[:70]))

    print("\n%d nœuds écrits dans %s" % (built, os.path.basename(LIBRARY)))


if __name__ == "__main__":
    main()
