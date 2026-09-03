"""Generate the Houdini render-property definitions for the Cycles delegate.

Houdini populates a renderer's tab in the Render Settings LOP from
`$HOUDINI_PATH/soho/parameters/<RendererName>_Global.ds`. This writes that file
from Cycles' own integrator socket declarations, so the exposed settings follow
the linked Cycles version rather than a hand-kept list that goes stale.

Run with hython - `hou.text.encode` produces the punycode parameter names
Houdini expects for attributes containing colons:

    hython tools/gen_render_properties.py
"""

import os
import re
import sys

import hou

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Quelle arborescence viser, suivant la meme convention que les autres outils :
# `install` pour la 5.2, `install-53` pour la 5.3.
INSTALL = os.environ.get("CYCLES_INSTALL_DIR", "install")
CYCLES = os.path.join(ROOT, "external", "cycles-53" if INSTALL.endswith("-53") else "cycles")
INTEGRATOR = os.path.join(CYCLES, "src", "scene", "integrator.cpp")
RESOURCES = os.path.join(CYCLES, "src", "hydra", "resources")
# Houdini cherche le fichier par nom de moteur : les deux entrees du menu, CPU
# et GPU, ont donc chacune le leur, au contenu identique.
OUTPUTS = [os.path.join(RESOURCES, "HdCyclesPlugin_Global.ds"),
           os.path.join(RESOURCES, "HdCyclesPluginGPU_Global.ds")]

# Cycles socket macro -> (Houdini parm type, USD value type)
NUMERIC = re.compile(r"^-?(\d+\.?\d*([eE][-+]?\d+)?|\.\d+)$")

TYPES = {
    "SOCKET_INT": ("integer", "int"),
    "SOCKET_UINT": ("integer", "int"),
    "SOCKET_FLOAT": ("float", "float"),
    "SOCKET_BOOLEAN": ("toggle", "bool"),
}

# Which tab each socket lands on, first match wins. Anything unmatched goes to
# Advanced rather than being dropped, so a new Cycles socket still shows up.
GROUPS = [
    ("Light Paths", ("min_bounce", "max_bounce", "max_diffuse", "max_glossy",
                     "max_transmission", "max_volume", "transparent_")),
    ("Ambient Occlusion", ("ao_",)),
    ("Volumes", ("volume_",)),
    ("Caustics", ("caustics_", "filter_glossy")),
    ("Denoising", ("denois", "use_denoise")),
    ("Guiding", ("guiding", "use_guiding")),
    ("Sampling", ("sampling_pattern", "seed", "sample_", "scrambling",
                  "adaptive", "light_sampling", "direct_light")),
]


def group_for(name):
    for label, prefixes in GROUPS:
        if any(p in name for p in prefixes):
            return label
    return "Advanced"


def parse_sockets():
    src = open(INTEGRATOR, encoding="utf-8", errors="replace").read()
    pattern = re.compile(
        r"(SOCKET_(?:INT|UINT|FLOAT|BOOLEAN))\(\s*(\w+)\s*,\s*\"([^\"]+)\"\s*,\s*([^,\)]+)")
    out = []
    for macro, name, label, default in pattern.findall(src):
        if macro not in TYPES:
            continue
        default = default.strip()
        if default in ("FLT_MAX",):
            default = "1e+30"
        default = default.rstrip("f")
        if macro == "SOCKET_BOOLEAN":
            default = "1" if default == "true" else "0"
        elif not NUMERIC.match(default):
            # A C++ constant or a bit-or of flags. Emitting it verbatim makes
            # Houdini complain about the default block; inventing a number
            # would be worse, so let Houdini use its own type default.
            default = None
        out.append((name, label, TYPES[macro][0], TYPES[macro][1], default))
    return out


def emit_parm(usd_name, label, parm_type, usd_type, default):
    """One property: a control parm driving whether it is authored, then the
    value parm itself. Mirrors how Houdini writes Karma's own definitions."""
    encoded = hou.text.encode(usd_name)
    control = hou.text.encode(usd_name + "_control")
    default_block = ("        default { %s }\n" % default) if default is not None else ""
    return f'''    parm {{
        name    "{control}"
        label   "{label}"
        type    string
        default {{ "none" }}
        menujoin {{
            [ "import loputils" ]
            [ "return loputils.createEditPropertiesControlMenu(kwargs, '{usd_type}')" ]
            language python
        }}
        parmtag {{ "sidefx::look" "icon" }}
    }}
    parm {{
        name    "{encoded}"
        label   "{label}"
        type    {parm_type}
        size    1
{default_block}        parmtag {{ "spare_category" "Cycles" }}
        parmtag {{ "usdvaluetype" "{usd_type}" }}
        disablewhen  R"({{ {control} == block }} {{ {control} == none }})"
    }}
'''


def main():
    sockets = parse_sockets()

    # Session-level settings the delegate reads directly, not integrator sockets.
    session = [
        ("cycles:samples", "Samples", "integer", "int", "1024"),
        ("cycles:sample_offset", "Sample Offset", "integer", "int", "0"),
        ("cycles:time_limit", "Time Limit", "float", "float", "0"),
        ("cycles:threads", "Threads", "integer", "int", "0"),
    ]

    grouped = {"Session": [emit_parm(*s) for s in session]}
    for name, label, parm_type, usd_type, default in sockets:
        grouped.setdefault(group_for(name), []).append(
            emit_parm("cycles:integrator:" + name, label, parm_type, usd_type, default))

    order = ["Session", "Sampling", "Light Paths", "Volumes", "Caustics",
             "Denoising", "Guiding", "Ambient Occlusion", "Advanced"]

    body = []
    for label in order:
        parms = grouped.get(label)
        if not parms:
            continue
        body.append(f'''    groupcollapsible {{
        name "cycles_{label.lower().replace(" ", "_")}"
        label "{label}"
        grouptag {{ "group_default" "1" }}
''')
        body.extend(parms)
        body.append("    }\n")

    text = f'''/// Generated by tools/gen_render_properties.py - do not edit by hand.
/// Render properties for the Cycles Hydra delegate.

#include "$HFS/houdini/soho/parameters/CommonMacros.ds"
{{
    name        "cycles"
    label       "Cycles"
    parmtag     {{ spare_opfilter        "!!SHOP/PROPERTIES!!" }}
    parmtag     {{ spare_classtags       "render" }}

    group {{
        name "cycles_global"
        label "Global"
{"".join(body)}    }}
}}
'''

    os.makedirs(RESOURCES, exist_ok=True)
    for out in OUTPUTS:
        open(out, "w", encoding="utf-8").write(text)
        print(out)
    total = sum(len(v) for v in grouped.values())
    print(f"{total} proprietes dans {len(grouped)} onglets")


main()
