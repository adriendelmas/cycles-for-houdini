"""Build the Cycles AOVs LOP as an installable digital asset.

Blender picks a render's passes on the View Layer properties; in Solaris a pass
is a render var on a render product. This node lays Blender's page out as
check boxes - Data, Light, Cryptomatte, Shader AOVs, Light Groups - and writes
the render vars (src/hydra/resources/cycles_aovs.py does the work).

    CYCLES_SOURCE=<cycles worktree> hython tools/build_aovs_hda.py
"""

import os
import shutil
import tempfile

import hou

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CYCLES = os.environ.get("CYCLES_SOURCE", os.path.join(ROOT, "external", "cycles-53"))
HDA = os.path.join(CYCLES, "src", "hydra", "resources", "otls", "hdcycles_aovs.hda")

ICON = os.path.join(CYCLES, "src", "hydra", "resources", "icons", "blender_icon_128x128.png")

TYPE_NAME = "hdcycles::cycles_aovs::1.0"
LABEL = "Cycles AOVs"

SCRIPT = '''import cycles_aovs

cycles_aovs.run(hou.pwd())
'''


def toggle(name, label, default=False, help=None):
    return hou.ToggleParmTemplate(name, label, default_value=default, help=help)


def folder(label, parms):
    f = hou.FolderParmTemplate("folder_" + label.lower().replace(" ", ""), label,
                               folder_type=hou.folderType.Simple)
    for p in parms:
        f.addParmTemplate(p)
    return f


def aov_folders():
    """The pass folders, shared with the Cycles Render Settings LOP
    (tools/build_render_settings_hda.py)."""
    folders = [folder("Data", [
        toggle("z", "Z"),
        toggle("mist", "Mist"),
        toggle("position", "Position"),
        toggle("normal", "Normal"),
        toggle("vector", "Vector"),
        toggle("uv", "UV"),
        toggle("roughness", "Roughness"),
        toggle("denoisingdata", "Denoising Data",
               help="Denoising Albedo and Denoising Normal, as Blender writes them."),
        toggle("objectindex", "Object Index",
               help="The Hydra prim id + 1. Hydra numbers prims as it loads them, so the "
                    "values change from one render to the next: use Cryptomatte for mattes."),
        toggle("materialindex", "Material Index"),
        toggle("samplecount", "Debug Sample Count"),
    ])]

    folders.append(folder("Light", [
        hou.LabelParmTemplate("difflabel", "Diffuse", column_labels=("Diffuse",)),
        toggle("diffusedirect", "Direct"),
        toggle("diffuseindirect", "Indirect"),
        toggle("diffusecolor", "Color"),
        hou.LabelParmTemplate("glosslabel", "Glossy", column_labels=("Glossy",)),
        toggle("glossydirect", "Direct"),
        toggle("glossyindirect", "Indirect"),
        toggle("glossycolor", "Color"),
        hou.LabelParmTemplate("translabel", "Transmission", column_labels=("Transmission",)),
        toggle("transmissiondirect", "Direct"),
        toggle("transmissionindirect", "Indirect"),
        toggle("transmissioncolor", "Color"),
        hou.LabelParmTemplate("vollabel", "Volume", column_labels=("Volume",)),
        toggle("volumedirect", "Direct"),
        toggle("volumeindirect", "Indirect"),
        hou.LabelParmTemplate("otherlabel", "Other", column_labels=("Other",)),
        toggle("emission", "Emission",
               help="Emission seen straight from the camera, Gaussian splats included."),
        toggle("environment", "Environment"),
        toggle("ao", "Ambient Occlusion"),
        toggle("shadowcatcher", "Shadow Catcher"),
    ]))

    folders.append(folder("Cryptomatte", [
        toggle("cryptoobject", "Object"),
        toggle("cryptomaterial", "Material"),
        toggle("cryptoasset", "Asset"),
        hou.IntParmTemplate("cryptolevels", "Levels", 1, default_value=(6,), min=2, max=16,
                            help="Objects a pixel can tell apart; two per layer."),
    ]))

    shader = hou.FolderParmTemplate("shaderaovs", "Shader AOVs",
                                    folder_type=hou.folderType.MultiparmBlock)
    shader.addParmTemplate(hou.ToggleParmTemplate(
        "shaderaovenable#", "", default_value=True, join_with_next=True,
        help="Write this AOV."))
    shader.addParmTemplate(hou.StringParmTemplate(
        "shaderaov#", "Name", 1, join_with_next=True,
        help="The name of an AOV Output node in the materials."))
    shader.addParmTemplate(hou.MenuParmTemplate(
        "shaderaovtype#", "Type", ("color", "value"), ("Color", "Value")))
    folders.append(folder("Shader AOVs", [
        button("autofillshaderaovs", "Auto Fill", "autofill_shader_aovs",
               "Adds every AOV Output node name found in the input's materials."),
        shader]))

    groups = hou.FolderParmTemplate("lightgroups", "Light Groups",
                                    folder_type=hou.folderType.MultiparmBlock)
    groups.addParmTemplate(hou.ToggleParmTemplate(
        "lightgroupenable#", "", default_value=True, join_with_next=True,
        help="Write this light group."))
    groups.addParmTemplate(hou.StringParmTemplate(
        "lightgroup#", "Name", 1,
        help="A light group, as set on objects (Render Geometry Settings, Cycles tab, or the "
             "LPE Tag LOP's geometry tag) and on lights (their LPE Tag). Written as "
             "Combined_<name>."))
    folders.append(folder("Light Groups", [
        button("autofilllightgroups", "Auto Fill", "autofill_light_groups",
               "Adds every light group and LPE tag set on the input's prims and lights."),
        groups]))
    return folders


def button(name, label, function, help):
    return hou.ButtonParmTemplate(
        name, label, help=help,
        script_callback="import cycles_aovs; cycles_aovs.%s(kwargs['node'])" % function,
        script_callback_language=hou.scriptLanguage.Python)


def parameters():
    group = hou.ParmTemplateGroup()
    group.append(hou.StringParmTemplate(
        "products", "Render Products", 1,
        help="The render products to add the AOVs to, separated by spaces. Empty: every "
             "product of the stage's render settings."))
    group.append(hou.StringParmTemplate(
        "location", "Render Vars Location", 1,
        help="Where the render var prims are created. Empty: a Vars scope next to the first "
             "render product."))
    for f in aov_folders():
        group.append(f)
    return group


TOOL = """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
    <toolMenuContext name="viewer">
      <contextNetType>LOP</contextNetType>
    </toolMenuContext>
    <toolMenuContext name="network">
      <contextOpType>$HDA_TABLE_AND_NAME</contextOpType>
    </toolMenuContext>
    <toolSubmenu>Rendering/Cycles</toolSubmenu>
    <script scriptType="python"><![CDATA[import loptoolutils

loptoolutils.genericTool(kwargs, '$HDA_NAME')]]></script>
  </tool>
</shelfDocument>
"""


def finish_definition(definition, parms):
    """Parameters, the Blender icon and a Rendering/Cycles entry in the tab menu."""
    definition.setParmTemplateGroup(parms)
    with open(ICON, "rb") as f:
        definition.addSection("IconImage.png", f.read())
    definition.setIcon("opdef:.?IconImage.png")
    definition.addSection("Tools.shelf", TOOL)


def save_asset(asset, path):
    """Saves through a scratch file: saving over an existing library makes Houdini
    keep a backup folder next to it, here in the source tree."""
    scratch = tempfile.mkdtemp(prefix="hda_")
    tmp = os.path.join(scratch, os.path.basename(path))
    asset.type().definition().save(tmp, asset, hou.HDAOptions())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copyfile(tmp, path)
    shutil.rmtree(scratch, ignore_errors=True)
    print("HDA written:", path)


def main():
    stage = hou.node("/stage")
    subnet = stage.createNode("subnet", "cycles_aovs_tmp")
    script = subnet.createNode("pythonscript", "author_render_vars")
    script.parm("python").set(SCRIPT)
    script.setFirstInput(subnet.indirectInputs()[0])
    script.setDisplayFlag(True)
    # A LOP subnet comes with an output node wired to its input: route it through the script.
    for child in subnet.children():
        if child.type().name() == "output":
            child.setFirstInput(script)

    scratch = tempfile.mkdtemp(prefix="hda_")
    asset = subnet.createDigitalAsset(
        name=TYPE_NAME, hda_file_name=os.path.join(scratch, "build.hda"), description=LABEL,
        min_num_inputs=1, max_num_inputs=1, ignore_external_references=True)
    finish_definition(asset.type().definition(), parameters())
    save_asset(asset, HDA)


if __name__ == "__main__":
    main()
