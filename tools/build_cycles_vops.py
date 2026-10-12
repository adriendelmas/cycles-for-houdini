"""Builds the Cycles VOP node library for Houdini.

The delegate already publishes the Cycles nodes to the Sdr registry, which
makes them readable by USD - but not placeable in a Material Builder. For
that, Houdini expects real VOP node types.

No Python translator is needed. A shader VOP is described entirely by its
DialogScript: `rendermask` says which engine it belongs to, `externalshader`
that it is not compiled, and three reserved parameters tell Solaris' default
translator which USD prim to write. This is the shape of the MaterialX nodes
shipped with Houdini, taken from `MaterialX.hda`.

Run with hython - no license required, unlike husk:

    hython tools/build_cycles_vops.py [--sample]

The library is written into the **installed** tree, the only one that Houdini
loads through the `cycles.json` package.
"""

import os
import sys

import hou
from pxr import Sdr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Which installation to target: `install-53`, the Cycles 5.3 build. The library
# must be regenerated after every build: the Sdr registry it derives from is
# published by the built delegate, whose nodes change from one Cycles version to
# the next.
INSTALL = os.environ.get("CYCLES_INSTALL_DIR", "install-53")
OTLS = os.path.join(ROOT, INSTALL, "houdini", "otls")
LIBRARY = os.path.join(OTLS, "cycles_vops.hda")

RENDER_CONTEXT = "cycles"
PREFIX = "cycles_"

SAMPLE = ["cycles_principled_bsdf", "cycles_image_texture", "cycles_noise_texture",
          "cycles_math", "cycles_mix_color"]

# Sdr type -> (DialogScript connector, parameter type, number of components)
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

# A parameter cannot carry the name of a type: the VOP context reserves them
# and the asset then refuses to instantiate. Measured on `vector`.
RESERVED = {"vector", "float", "color", "normal", "point", "matrix", "string",
            "int", "bsdf", "struct", "surface", "displacement", "light"}


# Menu categories, modeled on Blender's so that the nodes are found where one
# looks for them. Order matters: the first rule that matches wins.
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


# The `convert_*` nodes are inserted automatically by Cycles' graph compiler to
# join two types; Blender does not show them and placing one by hand makes no
# sense. They would clutter the menu with sixty entries.
def exposed(node_id):
    return not node_id.startswith(PREFIX + "convert_")


def category(node_id):
    """The tab menu subcategory for a node."""
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


# Cycles' internal names are not the ones Blender displays: an artist looks for
# "Color Ramp", not "Rgb Ramp". These labels follow Blender's interface so that
# the nodes are found under the name people know them by.
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

# Words that title-casing would damage.
LABEL_WORDS = {"bsdf": "BSDF", "rgb": "RGB", "hsv": "HSV", "ies": "IES",
               "uv": "UV", "aov": "AOV", "id": "ID", "xyz": "XYZ",
               "bw": "BW", "ao": "AO"}


def node_label(name):
    """The displayed label, aligned with Blender's names."""
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


# Cycles has only one closure type: the same `SocketType::CLOSURE` serves a
# surface BSDF and a volume alike, and Sdr publishes both as `terminal`.
# Houdini, on the other hand, does distinguish the shader connectors -
# `surface`, `displacement`, `atmosphere` - and a `subnetconnector` refuses a
# wire whose connector does not carry exactly the expected name (verified:
# wiring a `vector` or `surface` output to a Displacement or Atmosphere
# `parmtype` connector raises "Input data type does not match output"). So we
# have to lie deliberately about those few nodes that only ever terminate a
# single kind of network - the generic mixers (`add_closure`, `mix_closure`,
# `subsurface_scattering`...) stay `surface`, because a volume network can
# legitimately use them too and nothing in the registry says which of the two
# uses is meant.
VOLUME_TERMINAL_NODES = {"absorption_volume", "scatter_volume", "volume_coefficients",
                         "principled_volume"}
DISPLACEMENT_TERMINAL_NODES = {"displacement", "vector_displacement"}

# Connector -> what the builder's `subnetconnector` expects opposite it (see
# resources/cycles_builder.py, PARMTYPE_DISPLACEMENT and PARMTYPE_ATMOSPHERE).
OUTPUT_KIND_OVERRIDES = {name: "displacement" for name in DISPLACEMENT_TERMINAL_NODES}
OUTPUT_KIND_OVERRIDES.update({name: "atmosphere" for name in VOLUME_TERMINAL_NODES})


def shader_type(node_id, sdr_node):
    """What the node produces, which decides its place in the menu."""
    name = node_id[len(PREFIX):]
    if name in DISPLACEMENT_TERMINAL_NODES:
        return "displacement"
    if name in VOLUME_TERMINAL_NODES:
        return "atmosphere"
    for out_name in sdr_node.GetShaderOutputNames():
        if str(sdr_node.GetShaderOutput(out_name).GetType()) == "terminal":
            return "surface"
    return "generic"


# Cycles carries an internal mix weight on each closure. Blender never exposes
# it: it is the Mix Shader node that sets it. Offering it here would only
# mislead, and a graph that used it could not be replayed elsewhere.
INTERNAL_SOCKETS = {"surface_mix_weight"}

# A ramp's alpha channel is derived, not set: Houdini's ramp does not carry
# one, and the delegate fills it with opaque so that the two arrays have the
# same size - otherwise Cycles refuses to compile the node.
DERIVED_SOCKETS = {"ramp_alpha"}

# The array types that a Houdini ramp can fill. `tiles`, an integer array, is
# not one of them: it is a list of UDIM tiles, not a curve.
RAMP_TYPES = {"color": "ramp_rgb", "vector": "ramp_rgb", "point": "ramp_rgb",
              "normal": "ramp_rgb", "float": "ramp_flt"}


def ramp_type_of(prop):
    """The ramp widget that suits this array socket, if any."""
    if prop.GetArraySize() == 0:
        return None
    return RAMP_TYPES.get(str(prop.GetType()))


def usable(prop):
    """Cycles publishes its placement block as dotted sockets
    (`tex_mapping.translation`): a dot is illegal in a parameter name.
    Internal and derived sockets are dropped, and an array only passes if a
    ramp can fill it."""
    if "." in prop.GetName():
        return False
    if prop.GetName() in INTERNAL_SOCKETS or prop.GetName() in DERIVED_SOCKETS:
        return False
    if prop.GetArraySize() != 0:
        return ramp_type_of(prop) is not None
    return True


def parm_type_of(prop, fallback):
    """The widget that Houdini should offer for this input.

    A file name deserves a chooser, otherwise a path has to be pasted by hand;
    a boolean deserves a checkbox, otherwise nothing says that only zero and
    one make sense. Both are read from the metadata that the registry
    publishes."""
    if prop.IsAssetIdentifier():
        # `image` rather than `file`: it is Houdini's image chooser, the one it
        # uses for its own texture nodes.
        return "image"
    if str(prop.GetWidget()) == "checkBox":
        return "toggle"
    return fallback


# The sections, taken from Blender's interface node by node. Guessing by
# prefix is not enough: Blender files `tangent` and `anisotropic` under
# Specular, of which their names carry no trace, and it leaves flat some nodes
# whose inputs nevertheless share a prefix - the sky, the bump, the principled
# volume. An automatic rule was therefore wrong on both sides.
# A pattern ending in `*` takes everything that starts that way.
NODE_FOLDERS = {
    "principled_bsdf": [
        ("Diffuse", ["diffuse_roughness"]),
        ("Subsurface", ["subsurface_*"]),
        ("Specular", ["specular_*", "anisotropic", "anisotropic_rotation", "tangent"]),
        ("Transmission", ["transmission_*"]),
        ("Coat", ["coat_*"]),
        ("Sheen", ["sheen_*"]),
        ("Emission", ["emission_*"]),
        ("Thin Film", ["thin_film_*"]),
    ],
    "glass_bsdf": [("Thin Film", ["thin_film_*"])],
    "metallic_bsdf": [("Thin Film", ["thin_film_*"])],
}


def folders_for(node_id):
    return NODE_FOLDERS.get(node_id[len(PREFIX):], [])


def folder_of(socket, folders):
    """A socket's section, or None if it stays at the top of the node."""
    for label, patterns in folders:
        for pattern in patterns:
            if pattern.endswith("*"):
                if socket.startswith(pattern[:-1]):
                    return label
            elif socket == pattern:
                return label
    return None


def menu_block(prop, indent):
    """An enumeration becomes a drop-down menu.

    Without it, a math node's operation is just an integer to guess, and the
    node looks unusable although it carries thirty operations."""
    options = list(prop.GetOptions() or [])
    if not options:
        return []
    lines = [indent + "menu {"]
    for name, value in sorted(options, key=lambda o: int(str(o[1]))):
        lines.append('%s    "%s"  "%s"' % (indent, value, name))
    lines.append(indent + "}")
    return lines


def colorspace_menu(socket, indent):
    """The color space menu, for a `colorspace` socket.

    The name is resolved in the active OCIO configuration, Houdini's: the list
    therefore cannot be frozen here, it is built when the menu is opened.
    `menureplace` makes it **editable by hand**, like MaterialX's File Color
    Space - an alias that the configuration knows without it being listed must
    remain enterable, and a value typed by hand must not be erased by the
    menu.
    """
    if socket != "colorspace":
        return []
    return [indent + "menureplace {",
            indent + '    [ "import cycles_colorspaces" ]',
            indent + '    [ "return cycles_colorspaces.menu()" ]',
            indent + "    language python",
            indent + "}"]


def dialog_script(node_id, sdr_node):
    inputs = [n for n in sdr_node.GetShaderInputNames() if usable(sdr_node.GetShaderInput(n))]
    outputs = [n for n in sdr_node.GetShaderOutputNames() if usable(sdr_node.GetShaderOutput(n))]
    label = node_label(sdr_node.GetName())

    out = ["{", "    name\t%s" % node_id, "    script\t%s" % node_id,
           '    label\t"%s"' % escape(label), "",
           "    rendermask\t%s" % RENDER_CONTEXT,
           "    shadertype\t%s" % shader_type(node_id, sdr_node),
           "    externalshader\t1", ""]

    # A connector only for what Cycles accepts to link. The rest - a file name,
    # a color space, a projection mode - must be known when the scene is built:
    # a texture is loaded into memory, it is not evaluated per sample, and
    # Blender draws no socket on it either. Offering the input anyway would let
    # people pull a wire that does nothing, which misleads more than it helps.
    for name in inputs:
        prop = sdr_node.GetShaderInput(name)
        if not prop.IsConnectable() or ramp_type_of(prop):
            continue
        conn = TYPES.get(str(prop.GetType()), ("float", "float", 1))[0]
        out.append('    input\t%s\t%s\t"%s"' % (conn, parm_name(name),
                                                escape(prop.GetLabel() or name)))
    kind_override = OUTPUT_KIND_OVERRIDES.get(node_id[len(PREFIX):])
    for name in outputs:
        prop = sdr_node.GetShaderOutput(name)
        conn = kind_override or TYPES.get(str(prop.GetType()), ("float", "float", 1))[0]
        # An output keeps its name as is: it is the one the delegate looks for
        # on the Cycles side, and the tag that restores the real name only
        # applies to parameters, which an output is not.
        out.append('    output\t%s\t%s\t"%s"' % (conn, name,
                                                 escape(prop.GetLabel() or name)))
    out.append("")

    def emit_parm(name, indent):
        prop = sdr_node.GetShaderInput(name)
        ramp = ramp_type_of(prop)
        if ramp:
            # Houdini splits the ramp into a key count, positions, values and a
            # basis; the delegate gathers them into the flat table that Cycles
            # expects.
            return [indent + "parm {",
                    '%s    name    "%s"' % (indent, name),
                    '%s    label   "%s"' % (indent, escape(prop.GetLabel() or name)),
                    "%s    type    %s" % (indent, ramp),
                    '%s    default { "2" }' % indent,
                    "%s    range   { 1! 10 }" % indent,
                    '%s    parmtag { "rampbasisdefault" "linear" }' % indent,
                    indent + "}"]
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
        block += colorspace_menu(name, indent + "    ")
        # The real name of the Cycles socket, which the translator will write
        # to USD.
        if parm_name(name) != name:
            block.append('%s    parmtag { "sidefx::shader_parmname" "%s" }' % (indent, name))
        block.append(indent + "}")
        return block

    folders = folders_for(node_id)
    grouped = {}
    for name in inputs:
        grouped.setdefault(folder_of(name, folders), []).append(name)

    # Houdini puts every input outside a section into an "Other" group as soon
    # as one section exists. The main ones therefore go into a "Base" section
    # placed first, which Houdini also does for its own MaterialX nodes.
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
    for label, _ in folders:
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

    # The three parameters read by Solaris' default translator.
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
    """The definition from which the base operator is inherited.

    An external shader is a leaf, not a network: built on a `subnet`, the
    asset exports as a NodeGraph and not as a Shader, and `genericshader`
    refuses to be converted into an asset. So we copy an external shader node
    already shipped with Houdini, keeping only its nature - everything else,
    interface included, is replaced by the generated DialogScript.
    """
    node_type = hou.nodeType(hou.vopNodeTypeCategory(), "mtlximage")
    if node_type is None or node_type.definition() is None:
        raise RuntimeError("template node mtlximage not found")
    return node_type.definition()


def build_one(node_id, sdr_node, template):
    template.copyToHDAFile(LIBRARY, new_name=node_id,
                           new_menu_name=node_label(sdr_node.GetName()))
    hou.hda.installFile(LIBRARY)
    node_type = hou.nodeType(hou.vopNodeTypeCategory(), node_id)
    definition = node_type.definition()
    definition.addSection("DialogScript", dialog_script(node_id, sdr_node))
    # Without this the node inherits the template's menu and lands in the
    # MaterialX categories, mixed in with another engine's nodes.
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
    input	atmosphere	volume	"Volume"
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
    """The node that ends a Cycles network as a material.

    It is `shadertype material` that sets it apart: without it, a material
    library recognizes nothing to export. It plays the role that
    `mtlxsurfacematerial` plays on the MaterialX side."""
    template.copyToHDAFile(LIBRARY, new_name=MATERIAL_NAME, new_menu_name=MATERIAL_NAME)
    hou.hda.installFile(LIBRARY)
    definition = hou.nodeType(hou.vopNodeTypeCategory(), MATERIAL_NAME).definition()
    definition.addSection("DialogScript", MATERIAL_DIALOG)
    definition.addSection("Tools.shelf", TOOLS_SHELF % "Output")
    definition.save(LIBRARY)


PROPERTIES_NAME = "cycles_material_properties"

# The settings carried by Cycles' `Shader` itself, and not by one of its nodes
# - the Settings panel of a Blender material. The names are those of the
# `Shader` sockets (`src/scene/shader.cpp`): the delegate looks them up in its
# NodeType, so a correct name here is enough, with no mapping table to keep up
# to date.
PROPERTIES = [
    ("displacement_method", "string", '"both"', "Displacement Method",
     [("bump", "Bump Only"), ("true", "Displacement Only"), ("both", "Displacement and Bump")]),
    ("emission_sampling_method", "string", '"auto"', "Emission Sampling",
     [("none", "None"), ("auto", "Auto"), ("front", "Front"), ("back", "Back"),
      ("front_back", "Front and Back")]),
    ("use_transparent_shadow", "toggle", '"1"', "Transparent Shadows", None),
    ("use_bump_map_correction", "toggle", '"1"', "Bump Map Correction", None),
    ("volume_sampling_method", "string", '"multiple_importance"', "Volume Sampling",
     [("distance", "Distance"), ("equiangular", "Equiangular"),
      ("multiple_importance", "Multiple Importance")]),
    ("volume_interpolation_method", "string", '"linear"', "Volume Interpolation",
     [("linear", "Linear"), ("cubic", "Cubic")]),
    ("volume_step_rate", "float", '"1"', "Volume Step Rate", None),
    ("pass_id", "integer", '"0"', "Pass ID", None),
]


def properties_parm(name, ptype, default, label, menu):
    """A setting, and the checkbox that decides whether it is exported.

    The convention is Houdini's for render properties, taken from
    `kma_material_properties`: a `__activate__<name>` parameter controls the
    export of `<name>`, and only what is activated lands in the USD. Without
    it every material would carry all eight settings, and the delegate's
    default - bump, or both as soon as a displacement is wired - could no
    longer be expressed.

    The names carry a colon, which is illegal in a Houdini parameter name:
    `hou.text.encode` produces the `xn__...` form that Houdini expects, and the
    USD translator gives back the real name, `cycles:<socket>`.
    """
    activate = hou.text.encode("__activate__cycles:" + name)
    value = hou.text.encode("cycles:" + name)
    lines = ["    parm {",
             '        name    "%s"' % activate,
             '        label   "Activate"',
             "        type    toggle",
             "        nolabel",
             '        default { "0" }',
             '        parmtag { "sidefx::shader_isparm" "0" }',
             "    }",
             "    parm {",
             '        name    "%s"' % value,
             '        label   "%s"' % label,
             "        type    %s" % ptype,
             "        default { %s }" % default,
             '        disablewhen "{ %s != 1 }"' % activate]
    if menu:
        lines.append("        menu {")
        for token, mlabel in menu:
            lines.append('            "%s"  "%s"' % (token, mlabel))
        lines.append("        }")
    lines.append("    }")
    return lines


def properties_dialog():
    head = ["{",
            "    name\t%s" % PROPERTIES_NAME,
            "    script\t%s" % PROPERTIES_NAME,
            '    label\t"Cycles Material Properties"',
            "",
            "    rendermask\t%s" % RENDER_CONTEXT,
            "    shadertype\tgeneric",
            "    externalshader\t1",
            "    output	properties	properties	Properties",
            "    signature	Float	default	{ properties }",
            "",
            "    outputoverrides\tdefault",
            "    {",
            "\t___begin\tauto",
            "\t\t\t(0)",
            "    }",
            "",
            "    parm {",
            '        name    "signature"',
            '        label   "Signature"',
            "        type    float",
            "        invisible",
            '        default { "0" }',
            "    }",
            # Without this parameter, `_propertiesShaderNodeSibling` (in
            # `husd/mtlxshadertranslator.py`) assumes Karma - it literally
            # writes `render_context = 'kma'` by default - and discards the
            # properties node because the targeted context, `cycles`, is not
            # in the list. The node was then placed, wired, activated, and
            # never reached the USD.
            "    parm {",
            '        name    "shader_propertiescontextname"',
            '        label   "shader_propertiescontextname"',
            "        type    string",
            '        default { "%s" }' % RENDER_CONTEXT,
            "        invisible",
            "    }"]
    body = []
    for prop in PROPERTIES:
        body += properties_parm(*prop)
    return "\n".join(head + body + ["}", ""])


def build_properties_node(template):
    """The node that carries the material's settings.

    Displacement method, volume sampling, transparent shadows: these settings
    are not node sockets, they describe the `Shader`. Houdini folds the
    parameters of a properties node into the terminal's Shader prim, prefixed
    with the engine - `inputs:cycles:displacement_method` - and the delegate
    reads them back from there. This is how Karma proceeds with its
    `karma:*`."""
    template.copyToHDAFile(LIBRARY, new_name=PROPERTIES_NAME,
                           new_menu_name="Cycles Material Properties")
    hou.hda.installFile(LIBRARY)
    definition = hou.nodeType(hou.vopNodeTypeCategory(), PROPERTIES_NAME).definition()
    definition.addSection("DialogScript", properties_dialog())
    definition.addSection("Tools.shelf", TOOLS_SHELF % "Output")
    definition.save(LIBRARY)


# The builder is NOT a node type: it is a configured `subnet`, assembled by a
# tab menu tool - see `install/houdini/scripts/python/cycles_builder.py` and
# `install/houdini/toolbar/CyclesTools.shelf`. This is how Houdini makes the
# Karma Material Builder, and a first attempt as an asset produced nothing:
# the Material Library only exports a material if the `setMaterialFlag` flag
# is set on the instance.


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
    print("library: %s" % LIBRARY)
    print("nodes to generate: %d" % len(ids))

    template = template_definition()

    built, failed = 0, []
    for node_id in ids:
        sdr_node = registry.GetShaderNodeByIdentifier(node_id)
        if sdr_node is None:
            failed.append((node_id, "not in registry"))
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
        print("Cycles Material written")
        build_properties_node(template)
        print("Cycles Material Properties written")
    except hou.Error as exc:
        print("builder: FAILED %s" % str(exc).replace(chr(10), " ")[:70])

    print("%d nodes written, %d failures" % (built, len(failed)))
    for node_id, why in failed[:10]:
        print("   %-34s %s" % (node_id, why))


if __name__ == "__main__":
    main()
