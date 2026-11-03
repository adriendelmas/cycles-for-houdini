"""Build the Cycles Render Settings LOP, Karma Render Settings' counterpart.

One node writes everything a Cycles render needs: the render settings prim
(camera, resolution, every Cycles setting of the Render Settings LOP's Cycles
tab), its render product (the output picture) with the beauty, and Blender's
View Layer passes, as the Cycles AOVs LOP does. Inside: Houdini's Render
Settings and Render Product LOPs, whose parameters are channel references to
the asset's, and a Python LOP running cycles_aovs.run() for the render vars.

The Cycles settings are always authored (no per-parameter "Set or Create"
menu), as Karma Render Settings does: the values shown are what renders.

    CYCLES_SOURCE=<cycles worktree> hython tools/build_render_settings_hda.py
"""

import os
import tempfile

import hou

from build_aovs_hda import (CYCLES, MENU_SCRIPT, SCRIPT, aov_folders, finish_definition,
                            save_asset)

HDA = os.path.join(CYCLES, "src", "hydra", "resources", "otls",
                   "hdcycles_render_settings.hda")
TYPE_NAME = "hdcycles::cycles_render_settings::1.0"
LABEL = "Cycles Render Settings"

# Not Karma's /Render/rendersettings: a Cycles render after Karma's settings
# misbehaves (docs/KNOWN_ISSUES.md, K-125), so the two can live side by side.
SETTINGS_PATH = "/Render/CyclesRenderSettings"
PRODUCT_PATH = "/Render/Products/CyclesBeauty"
PICTURE = "$HIP/render/$HIPNAME.$OS.$F4.exr"


def _strip_controls(template, controls):
    """A copy of a Cycles folder without the "Set or Create" menus, whose
    names go to `controls`."""
    folder = template.clone()
    kept = []
    for child in template.parmTemplates():
        if child.type() == hou.parmTemplateType.Folder:
            kept.append(_strip_controls(child, controls))
        elif "_control" in child.name():
            controls.append(child.name())
        else:
            child = child.clone()
            child.setConditional(hou.parmCondType.DisableWhen, "")
            kept.append(child)
    folder.setParmTemplates(kept)
    return folder


def _value_names(template, out):
    for child in template.parmTemplates():
        if child.type() == hou.parmTemplateType.Folder:
            _value_names(child, out)
        elif child.type() not in (hou.parmTemplateType.Label, hou.parmTemplateType.Separator):
            out.append(child.name())
    return out


def _tabs(label, folders):
    tab = hou.FolderParmTemplate(
        "tab_" + label.lower().replace(" ", ""), label, folder_type=hou.folderType.Tabs)
    for f in folders:
        tab.addParmTemplate(f)
    return tab


def parameters(settings, controls):
    group = hou.ParmTemplateGroup()
    rs = settings.parmTemplateGroup()

    group.append(hou.StringParmTemplate(
        "primpath", "Render Settings Path", 1, default_value=(SETTINGS_PATH,),
        help="The render settings prim. The Render Pass (Cycles (Setup)) and the viewport's "
             "render settings menu point at it."))
    group.append(hou.StringParmTemplate(
        "productpath", "Render Product Path", 1, default_value=(PRODUCT_PATH,),
        help="The render product: the output picture, its beauty and its AOVs."))
    group.append(hou.StringParmTemplate(
        "picture", "Output Picture", 1, default_value=(PICTURE,),
        string_type=hou.stringParmType.FileReference,
        file_type=hou.fileType.Image,
        help="The image file husk writes. One EXR holds the beauty and every AOV."))
    for name in ("camera", "resolution", "resolutionMenu"):
        group.append(rs.find(name))
    group.append(hou.SeparatorParmTemplate("sep_rendering"))

    cycles_global = rs.findFolder(("Cycles", "Global"))
    rendering = [_strip_controls(f, controls) for f in cycles_global.parmTemplates()
                 if f.type() == hou.parmTemplateType.Folder]
    # Collapsible sections open on the Rendering tab, as on Karma's node.
    group.append(_tabs("Rendering", rendering))

    aovs = [hou.StringParmTemplate(
        "denoiseaovs", "Denoise AOVs", 1,
        item_generator_script=MENU_SCRIPT % ("denoise_menu", "denoise_menu"),
        item_generator_script_language=hou.scriptLanguage.Python,
        menu_type=hou.menuType.StringToggle,
        help="Render var names, separated by spaces, that OIDN denoises at the end of the "
             "render, guided by albedo and normal (cycles:denoise_aovs) - as the AOVs list of "
             "Karma's denoiser. The beauty is left to Cycles' own denoiser (Rendering > "
             "Denoising). Denoising helps passes whose noise comes from bounces; a pass made "
             "mostly of fine, direct splat emission loses detail."),
            hou.StringParmTemplate(
        "location", "Render Vars Location", 1,
        help="Where the render var prims are created. Empty: a Vars scope next to the "
             "render product.")]
    aovs += aov_folders()
    group.append(_tabs("AOVs", aovs))
    return group


def main():
    stage = hou.node("/stage")
    subnet = stage.createNode("subnet", "cycles_render_settings_tmp")
    settings = subnet.createNode("rendersettings", "settings")
    settings.setFirstInput(subnet.indirectInputs()[0])
    product = subnet.createNode("renderproduct", "product")
    product.setFirstInput(settings)
    passes = subnet.createNode("pythonscript", "render_vars")
    passes.parm("python").set(SCRIPT)
    passes.setFirstInput(product)
    passes.setDisplayFlag(True)
    for child in subnet.children():
        if child.type().name() == "output":
            child.setFirstInput(passes)

    controls = []
    group = parameters(settings, controls)

    scratch = tempfile.mkdtemp(prefix="hda_")
    asset = subnet.createDigitalAsset(
        name=TYPE_NAME, hda_file_name=os.path.join(scratch, "build.hda"), description=LABEL,
        min_num_inputs=1, max_num_inputs=1, ignore_external_references=True)
    definition = asset.type().definition()
    finish_definition(definition, group)

    # Inside, every parameter reads the asset's.
    asset.allowEditingOfContents()
    settings = asset.node("settings")
    product = asset.node("product")
    settings.parm("primpath").setExpression('chs("../primpath")', hou.exprLanguage.Hscript)
    for name in ("products", "camera", "resolution"):
        settings.parm(name + "_control").set("set")
    settings.parm("products").set(asset.parm("productpath"))
    settings.parm("camera").set(asset.parm("camera"))
    # The asset's resolution is the one rendered: no height derived from the camera.
    settings.parm("res_mode").set("manual")
    settings.parmTuple("resolution").lock((False, False))
    settings.parmTuple("resolution").set(asset.parmTuple("resolution"))
    for name in controls:
        settings.parm(name).set("set")
    names = []
    for f in group.entries():
        if f.type() == hou.parmTemplateType.Folder and f.label() == "Rendering":
            _value_names(f, names)
    linked = 0
    for name in names:
        inner = settings.parmTuple(name)
        outer = asset.parmTuple(name)
        if inner is None or outer is None:
            print("not linked:", name)
            continue
        for a, b in zip(inner, outer):
            a.set(b)
        linked += 1
    print("Cycles settings linked:", linked, "controls set:", len(controls))

    product.parm("primpath").setExpression('chs("../productpath")', hou.exprLanguage.Hscript)
    product.parm("productName_control").set("set")
    product.parm("productName").setExpression('chs("../picture")', hou.exprLanguage.Hscript)

    definition.updateFromNode(asset)
    save_asset(asset, HDA)


main()
