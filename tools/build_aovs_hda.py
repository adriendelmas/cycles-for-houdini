"""Build the Cycles AOVs LOP as an installable digital asset.

Blender picks a render's passes on the View Layer properties; in Solaris a pass
is a render var on a render product. This node lays Blender's page out as
check boxes - Data, Light, Cryptomatte, Shader AOVs, Light Groups - and writes
the render vars (src/hydra/resources/cycles_aovs.py does the work).

    CYCLES_SOURCE=<cycles worktree> hython tools/build_aovs_hda.py
"""

import os

import hou

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CYCLES = os.environ.get("CYCLES_SOURCE", os.path.join(ROOT, "external", "cycles-53"))
HDA = os.path.join(CYCLES, "src", "hydra", "resources", "otls", "hdcycles_aovs.hda")

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

    group.append(folder("Data", [
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
    ]))

    group.append(folder("Light", [
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

    group.append(folder("Cryptomatte", [
        toggle("cryptoobject", "Object"),
        toggle("cryptomaterial", "Material"),
        toggle("cryptoasset", "Asset"),
        hou.IntParmTemplate("cryptolevels", "Levels", 1, default_value=(6,), min=2, max=16,
                            help="Objects a pixel can tell apart; two per layer."),
    ]))

    shader = hou.FolderParmTemplate("shaderaovs", "Shader AOVs",
                                    folder_type=hou.folderType.MultiparmBlock)
    shader.addParmTemplate(hou.StringParmTemplate(
        "shaderaov#", "Name", 1, help="The name of an AOV Output node in the materials."))
    shader.addParmTemplate(hou.MenuParmTemplate(
        "shaderaovtype#", "Type", ("color", "value"), ("Color", "Value")))
    group.append(folder("Shader AOVs", [shader]))

    groups = hou.FolderParmTemplate("lightgroups", "Light Groups",
                                    folder_type=hou.folderType.MultiparmBlock)
    groups.addParmTemplate(hou.StringParmTemplate(
        "lightgroup#", "Name", 1,
        help="A light group, as set on lights and objects (cycles:object:lightgroup). "
             "Written as Combined_<name>."))
    group.append(folder("Light Groups", [groups]))
    return group


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

    os.makedirs(os.path.dirname(HDA), exist_ok=True)
    asset = subnet.createDigitalAsset(
        name=TYPE_NAME, hda_file_name=HDA, description=LABEL,
        min_num_inputs=1, max_num_inputs=1, ignore_external_references=True)
    definition = asset.type().definition()
    definition.setParmTemplateGroup(parameters())
    definition.save(HDA, asset, hou.HDAOptions())
    print("HDA written:", HDA)


main()
