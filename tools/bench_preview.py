"""Does the viewport preview of a Cycles material show its colour and textures?

Houdini's viewport renders a Cycles material through the UsdPreviewSurface
the delegate's preview translator writes beside it (`cycles.py`, K-42). This
bench builds Cycles VOP networks in this hython - the real chain: VOPs,
Solaris' translators, USD - and reads the preview back: which texture its
diffuse colour reads, or which colour it holds.

    hython tools/bench_preview.py

Run it with hdCycles' Houdini directory first on HOUDINI_PATH (the package,
or HOUDINI_PATH="<install>/houdini;&" with a Windows path), so the
translator loads.
"""

import os
import sys

import hou

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.environ.get("CYCLES_INSTALL_DIR", "install-53")
sys.path.insert(0, os.path.join(ROOT, INSTALL, "houdini", "scripts", "python"))
hou.hda.installFile(os.path.join(ROOT, INSTALL, "houdini", "otls", "cycles_vops.hda"))
import cycles_builder  # noqa: E402


def image(sub, name, path):
    node = sub.createNode("cycles_image_texture", name)
    node.parm("filename").set(path)
    return node


def color(node, parm, rgb):
    for i, c in enumerate("rgb"):
        node.parm(parm + c).set(rgb[i])


def case_image(sub):
    return image(sub, "img", "C:/tex/a.png"), ("texture", "C:/tex/a.png")


def case_gamma(sub):
    gam = sub.createNode("cycles_gamma", "gam")
    gam.setInput(0, image(sub, "img", "C:/tex/a.png"), 0)
    return gam, ("texture", "C:/tex/a.png")


def case_mix_b(sub):
    # An image on `b`, the side a factor of 0.5 or more favours.
    mix = sub.createNode("cycles_mix_color", "mix")
    mix.setInput(2, image(sub, "img", "C:/tex/b.png"), 0)
    return mix, ("texture", "C:/tex/b.png")


def case_mix_a(sub):
    mix = sub.createNode("cycles_mix_color", "mix")
    mix.setInput(1, image(sub, "img", "C:/tex/a.png"), 0)
    return mix, ("texture", "C:/tex/a.png")


def case_mix_two_images(sub):
    # Two images: the preview holds one, the one the factor favours.
    mix = sub.createNode("cycles_mix_color", "mix")
    mix.parm("fac").set(0.2)
    mix.setInput(1, image(sub, "img_a", "C:/tex/a.png"), 0)
    mix.setInput(2, image(sub, "img_b", "C:/tex/b.png"), 0)
    return mix, ("texture", "C:/tex/a.png")


def case_mix_constants(sub):
    mix = sub.createNode("cycles_mix_color", "mix")
    mix.parm("fac").set(0.25)
    color(mix, "a", (1.0, 0.0, 0.0))
    color(mix, "b", (0.0, 0.0, 1.0))
    return mix, ("value", (0.75, 0.0, 0.25))


CASES = [
    ("image", case_image),
    ("gamma", case_gamma),
    ("mix_b", case_mix_b),
    ("mix_a", case_mix_a),
    ("mix_two_images", case_mix_two_images),
    ("mix_constants", case_mix_constants),
]


def preview_diffuse(stage):
    """The preview's diffuseColor: ("texture", file), ("value", rgb) or None."""
    from pxr import UsdShade
    for prim in stage.Traverse():
        shader = UsdShade.Shader(prim)
        if not shader or shader.GetShaderId() != "UsdPreviewSurface":
            continue
        inp = shader.GetInput("diffuseColor")
        if not inp:
            return None
        if inp.HasConnectedSource():
            source = inp.GetConnectedSources()[0][0].source
            tex = UsdShade.Shader(source.GetPrim())
            file_input = tex.GetInput("file")
            value = file_input.Get() if file_input else None
            return ("texture", value.path if value is not None else None)
        value = inp.Get()
        return ("value", tuple(round(float(c), 3) for c in value)) if value is not None else None
    return None


def main():
    problems = 0
    for name, build in CASES:
        stage_net = hou.node("/stage")
        for child in stage_net.children():
            child.destroy()
        lib = stage_net.createNode("materiallibrary")
        lib.parm("matpathprefix").set("/world/Materials/")
        sub = lib.createNode("subnet", "mat")
        cycles_builder.setup(sub)
        surface = sub.node("surface")
        node, expected = build(sub)
        surface.setInput(surface.inputNames().index("base_color"), node, 0)
        lib.setDisplayFlag(True)
        got = preview_diffuse(lib.stage())
        if expected[0] == "value" and got and got[0] == "value":
            ok = all(abs(a - b) < 1e-3 for a, b in zip(got[1], expected[1]))
        else:
            ok = got == expected
        print("%-16s %s  got %s, expected %s" % (name, "ok     " if ok else "WRONG  ", got, expected))
        problems += 0 if ok else 1
    print("\n%d cases, %d problems" % (len(CASES), problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
