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
    "terminal": ("surface", None, 0),
}

# Un paramètre ne peut pas porter le nom d'un type : le contexte VOP les
# réserve et l'actif refuse alors de s'instancier. Mesuré sur `vector`.
RESERVED = {"vector", "float", "color", "normal", "point", "matrix", "string",
            "int", "bsdf", "struct", "surface", "displacement", "light"}


# Catégories du menu, calquées sur celles de Blender pour que les nœuds se
# retrouvent là où on les cherche. L'ordre compte : la première règle qui
# correspond gagne.
CATEGORY_RULES = [
    ("Output", ("output", "aov_output", "displacement", "vector_displacement")),
    ("Shader", ("_bsdf", "emission", "background_shader", "holdout", "mix_closure",
                "add_closure", "subsurface_scattering", "_volume", "volume_coefficients",
                "ray_portal", "principled_hair")),
    ("Texture", ("_texture", "ies_light", "sky", "environment")),
    ("Color", ("brightness_contrast", "gamma", "hsv", "invert", "mix_color",
               "rgb_curves", "rgb_ramp", "wavelength", "blackbody")),
    ("Vector", ("bump", "mapping", "normal_map", "set_normal", "vector_curves",
                "vector_rotate", "vector_transform", "vector_math", "vector_map_range",
                "normal", "tangent")),
    ("Converter", ("combine_", "separate_", "convert_", "math", "clamp", "map_range",
                   "float_curve", "mix_float", "mix_vector", "mix", "rgb_to_bw",
                   "blackbody")),
    ("Input", ("attribute", "camera_info", "geometry", "light_path", "object_info",
               "particle_info", "point_info", "texture_coordinate", "uvmap", "value",
               "volume_info", "wireframe", "ambient_occlusion", "bevel", "fresnel",
               "layer_weight", "hair_info", "vertex_color", "raycast", "scene_time",
               "color", "curves_info")),
]


# Les `convert_*` sont insérés d'office par le compilateur de graphe de Cycles
# pour raccorder deux types ; Blender ne les montre pas et poser l'un d'eux à la
# main n'a pas de sens. Ils encombreraient le menu de soixante entrées.
def exposed(node_id):
    return not node_id.startswith(PREFIX + "convert_")


def category(node_id):
    """La sous-catégorie du menu tab pour un nœud."""
    name = node_id[len(PREFIX):]
    for label, patterns in CATEGORY_RULES:
        for pattern in patterns:
            if name.startswith(pattern) or name.endswith(pattern) or pattern == name:
                return label
    return "Other"


TOOLS_SHELF = """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
    <toolMenuContext name="network">
      <contextOpType>$HDA_TABLE_AND_NAME</contextOpType>
    </toolMenuContext>
    <toolSubmenu>Cycles/%s</toolSubmenu>
    <script scriptType="python"><![CDATA[import voptoolutils
voptoolutils.genericTool(kwargs, '$HDA_NAME')]]></script>
    <keywordList>
      <keyword>Cycles</keyword>
    </keywordList>
  </tool>
</shelfDocument>
"""


# Les noms internes de Cycles ne sont pas ceux que Blender affiche : un artiste
# cherche « Color Ramp », pas « Rgb Ramp ». Ces libellés suivent l'interface de
# Blender pour que les nœuds se retrouvent sous le nom qu'on leur connaît.
LABEL_OVERRIDES = {
    "rgb_ramp": "Color Ramp",
    "rgb_curves": "RGB Curves",
    "rgb_to_bw": "RGB to BW",
    "color": "RGB",
    "value": "Value",
    "mix_closure": "Mix Shader",
    "add_closure": "Add Shader",
    "mix_closure_weight": "Mix Shader Weight",
    "background_shader": "Background",
    "camera_info": "Camera Data",
    "invert": "Invert Color",
    "brightness_contrast": "Bright/Contrast",
    "hsv": "Hue/Saturation/Value",
    "ies_light": "IES Texture",
    "uvmap": "UV Map",
    "scene_time": "Scene Time",
    "aov_output": "AOV Output",
    "mx_noise_texture": "MaterialX Noise",
    "mx_hextiled_image_texture": "MaterialX Hextiled Image",
    "volume_coefficients": "Volume Coefficients",
    "point_info": "Point Info",
}

# Mots que le passage en capitales initiales abîmerait.
LABEL_WORDS = {"bsdf": "BSDF", "rgb": "RGB", "hsv": "HSV", "ies": "IES",
               "uv": "UV", "aov": "AOV", "id": "ID", "xyz": "XYZ",
               "bw": "BW", "ao": "AO"}


def node_label(name):
    """Le libellé affiche, aligne sur les noms de Blender."""
    if name in LABEL_OVERRIDES:
        return "Cycles " + LABEL_OVERRIDES[name]
    words = [LABEL_WORDS.get(w, w.title()) for w in name.split("_")]
    return "Cycles " + " ".join(words)


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


# Cycles porte sur chaque fermeture un poids de mélange interne. Blender ne
# l'expose jamais : c'est le nœud Mix Shader qui le pose. L'offrir ici ne ferait
# qu'égarer, et un graphe qui s'en servirait ne se rejouerait pas ailleurs.
INTERNAL_SOCKETS = {"surface_mix_weight"}


def usable(prop):
    """Cycles publie son bloc de placement en sockets pointés
    (`tex_mapping.translation`) : un point est illégal dans un nom de
    paramètre. Les sockets tableau et les sockets internes sont écartés."""
    return ("." not in prop.GetName() and prop.GetArraySize() == 0
            and prop.GetName() not in INTERNAL_SOCKETS)


def parm_type_of(prop, fallback):
    """Le widget que Houdini doit offrir pour cette entrée.

    Un nom de fichier mérite un sélecteur, sans quoi il faut coller un chemin à
    la main ; un booléen mérite une case à cocher, sans quoi rien ne dit que
    seuls zéro et un ont un sens. Les deux se lisent dans les métadonnées que
    le registre publie."""
    if prop.IsAssetIdentifier():
        # `image` plutôt que `file` : c'est le sélecteur d'image de Houdini,
        # celui qu'il emploie pour ses propres nœuds de texture.
        return "image"
    if str(prop.GetWidget()) == "checkBox":
        return "toggle"
    return fallback


# Blender range les entrees d'un nuanceur en sections repliables. Les sockets de
# Cycles n'en portent pas la trace, mais leur prefixe suffit a la retrouver.
PARM_FOLDERS = [
    ("diffuse", "Diffuse"), ("subsurface", "Subsurface"), ("specular", "Specular"),
    ("transmission", "Transmission"), ("coat", "Coat"), ("sheen", "Sheen"),
    ("emission", "Emission"), ("thin_film", "Thin Film"),
    ("tex_mapping", "Mapping"), ("distribution", None),
]


# Un préfixe partagé par au moins tant d'entrées mérite sa section, même sur un
# nœud dont Blender ne montre pas de découpage : c'est ce qui rend lisible un
# voronoi ou un sky, pas seulement le principled.
FOLDER_THRESHOLD = 3


def folder_of(socket, counts=None):
    """La section d'un socket, ou None s'il reste en tête du nœud."""
    for prefix, label in PARM_FOLDERS:
        if label and socket.startswith(prefix + "_"):
            return label
    if counts:
        head = socket.split("_", 1)[0]
        if "_" in socket and counts.get(head, 0) >= FOLDER_THRESHOLD:
            return head.replace("_", " ").title()
    return None


def folder_counts(names):
    """Combien d'entrées partagent chaque préfixe.

    Celles qu'une section nommée réclame déjà ne comptent pas : sans ça
    `thin_wall` se retrouvait groupé avec les deux `thin_film_*` sous un
    « Thin » que Blender ne montre pas, alors qu'il y est une case en tête."""
    counts = {}
    for name in names:
        if "_" not in name or folder_of(name) is not None:
            continue
        head = name.split("_", 1)[0]
        counts[head] = counts.get(head, 0) + 1
    return counts


def menu_block(prop, indent):
    """Une enumeration devient un menu deroulant.

    Sans ca l'operation d'un noeud math n'est qu'un entier a deviner, et le
    noeud parait inutilisable alors qu'il porte trente operations."""
    options = list(prop.GetOptions() or [])
    if not options:
        return []
    lines = [indent + "menu {"]
    for name, value in sorted(options, key=lambda o: int(str(o[1]))):
        lines.append('%s    "%s"  "%s"' % (indent, value, name))
    lines.append(indent + "}")
    return lines


def dialog_script(node_id, sdr_node):
    inputs = [n for n in sdr_node.GetShaderInputNames() if usable(sdr_node.GetShaderInput(n))]
    outputs = [n for n in sdr_node.GetShaderOutputNames() if usable(sdr_node.GetShaderOutput(n))]
    label = node_label(sdr_node.GetName())

    out = ["{", "    name\t%s" % node_id, "    script\t%s" % node_id,
           '    label\t"%s"' % escape(label), "",
           "    rendermask\t%s" % RENDER_CONTEXT,
           "    shadertype\t%s" % shader_type(sdr_node),
           "    externalshader\t1", ""]

    # Un connecteur seulement pour ce que Cycles accepte de lier. Le reste - un
    # nom de fichier, un espace colorimétrique, un mode de projection - doit
    # être connu quand la scène est construite : une texture se charge en
    # mémoire, elle ne s'évalue pas par échantillon, et Blender ne dessine pas
    # de socket dessus non plus. Offrir l'entrée quand même laisserait tirer un
    # fil qui ne fait rien, ce qui trompe plus que ça ne sert.
    for name in inputs:
        prop = sdr_node.GetShaderInput(name)
        if not prop.IsConnectable():
            continue
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

    def emit_parm(name, indent):
        prop = sdr_node.GetShaderInput(name)
        conn, ptype, comps = TYPES.get(str(prop.GetType()), ("float", "float", 1))
        if ptype is None:
            return []
        ptype = parm_type_of(prop, ptype)
        if ptype in ("image", "toggle"):
            comps = 1
        block = [indent + "parm {",
                 '%s    name    "%s"' % (indent, parm_name(name)),
                 '%s    label   "%s"' % (indent, escape(prop.GetLabel() or name)),
                 "%s    type    %s" % (indent, ptype)]
        if comps > 1 and ptype != "color":
            block.append("%s    size    %d" % (indent, comps))
        block.append("%s    default { %s }" % (indent, default_literal(prop, comps)))
        block += menu_block(prop, indent + "    ")
        # Le nom réel du socket Cycles, que le traducteur écrira en USD.
        if parm_name(name) != name:
            block.append('%s    parmtag { "sidefx::shader_parmname" "%s" }' % (indent, name))
        block.append(indent + "}")
        return block

    counts = folder_counts(inputs)
    grouped = {}
    order = []
    for name in inputs:
        label = folder_of(name, counts)
        if label not in grouped:
            grouped[label] = []
            if label is not None:
                order.append(label)
        grouped[label].append(name)

    # Houdini range dans un groupe « Other » toute entrée hors section dès qu'il
    # en existe une. Les principales vont donc dans une section « Base » placée
    # en tête, ce que fait aussi Houdini pour ses propres nœuds MaterialX.
    loose = grouped.pop(None, [])
    if loose and grouped:
        out.append("    groupcollapsible {")
        out.append('        name    "folder_base"')
        out.append('        label   "Base"')
        out.append('        parmtag { "group_default" "1" }')
        out.append("")
        for name in loose:
            out += emit_parm(name, "        ")
        out.append("    }")
    else:
        for name in loose:
            out += emit_parm(name, "    ")
    known = [l for _, l in PARM_FOLDERS if l]
    for label in known + [l for l in order if l not in known]:
        names = grouped.pop(label, None)
        if not names:
            continue
        out.append("    groupcollapsible {")
        out.append('        name    "folder_%s"' % label.lower().replace(" ", "_"))
        out.append('        label   "%s"' % label)
        out.append("")
        for name in names:
            out += emit_parm(name, "        ")
        out.append("    }")
    for label, names in grouped.items():
        for name in names:
            out += emit_parm(name, "    ")

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
    template.copyToHDAFile(LIBRARY, new_name=node_id,
                           new_menu_name=node_label(sdr_node.GetName()))
    hou.hda.installFile(LIBRARY)
    node_type = hou.nodeType(hou.vopNodeTypeCategory(), node_id)
    definition = node_type.definition()
    definition.addSection("DialogScript", dialog_script(node_id, sdr_node))
    # Sans ça le nœud hérite du menu du modèle et atterrit dans les catégories
    # MaterialX, mêlé aux nœuds d'un autre moteur.
    definition.addSection("Tools.shelf", TOOLS_SHELF % category(node_id))
    definition.save(LIBRARY)


MATERIAL_NAME = "cycles_material"

MATERIAL_DIALOG = """{
    name	cycles_material
    script	cycles_material
    label	"Cycles Material"

    rendermask	cycles
    shadertype	material
    externalshader	1

    input	surface	surface	"Surface"
    input	displacement	displacement	"Displacement"
    input	surface	volume	"Volume"
    output	material	out	"out"

    parm {
        name    "shader_rendercontextname"
        label   "shader_rendercontextname"
        type    string
        default { "cycles" }
        invisible
    }
}
"""


def build_material_node(template):
    """Le nœud qui termine un réseau Cycles en matériau.

    C'est `shadertype material` qui le distingue : sans lui, une bibliothèque de
    matériaux ne reconnaît rien à exporter. C'est le rôle que joue
    `mtlxsurfacematerial` du côté MaterialX."""
    template.copyToHDAFile(LIBRARY, new_name=MATERIAL_NAME, new_menu_name=MATERIAL_NAME)
    hou.hda.installFile(LIBRARY)
    definition = hou.nodeType(hou.vopNodeTypeCategory(), MATERIAL_NAME).definition()
    definition.addSection("DialogScript", MATERIAL_DIALOG)
    definition.addSection("Tools.shelf", TOOLS_SHELF % "Output")
    definition.save(LIBRARY)


# Le builder n'est PAS un type de nœud : c'est un `subnet` configuré, monté par
# un outil du menu tab — voir `install/houdini/scripts/python/cycles_builder.py`
# et `install/houdini/toolbar/CyclesTools.shelf`. C'est ainsi que Houdini
# fabrique le Karma Material Builder, et une première tentative sous forme
# d'actif ne produisait rien : la Material Library n'exporte un matériau que si
# le drapeau `setMaterialFlag` est posé sur l'instance.


def main():
    only_sample = "--sample" in sys.argv
    registry = Sdr.Registry()
    ids = sorted(str(i) for i in registry.GetShaderNodeIdentifiers()
                 if str(i).startswith(PREFIX))
    ids = [i for i in ids if exposed(i)]
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

    try:
        stage = hou.node("/stage")
        for child in stage.children():
            child.destroy()
        build_material_node(template)
        print("Cycles Material ecrit")
    except hou.Error as exc:
        print("builder: ECHEC %s" % str(exc).replace(chr(10), " ")[:70])

    print("%d noeuds ecrits, %d echecs" % (built, len(failed)))
    for node_id, why in failed[:10]:
        print("   %-34s %s" % (node_id, why))


if __name__ == "__main__":
    main()
