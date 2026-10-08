"""Does a Karma Render Settings node render its AOVs through Cycles?

Builds a stage the way an artist would in Solaris - a sphere, a distant and a
dome light, a camera and Houdini's own Karma Render Settings LOP with its
light-component and data AOVs ticked - exports it and renders it with Cycles
under husk. The render vars are Karma's (`C<RD>.*L`, `ray:hitPz`, `CDA`...);
each must land on a Cycles pass with a sensible value. The scene is diffuse
only, so the diffuse components equal the beauty and the glossy ones are 0.

    hython tools/bench_karma_settings.py

Scene and image go to tests/karma_settings/output/.
"""

import os
import subprocess
import sys

import hou
import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "karma_settings", "output")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

AOVS = ("combineddiffuse", "directdiffuse", "indirectdiffuse", "combinedglossyreflection",
        "directglossyreflection", "combinedemission", "albedo", "hitP", "hitPz", "hituv", "hitN",
        "motionvectors")


def build(scene):
    stage = hou.node("/stage")
    sphere = stage.createNode("sphere")
    light = stage.createNode("distantlight")
    light.setInput(0, sphere)
    dome = stage.createNode("domelight")
    dome.setInput(0, light)
    cam = stage.createNode("camera")
    cam.setInput(0, dome)
    cam.parm("tz").set(6)
    settings = stage.createNode("karmarendersettings")
    settings.setInput(0, cam)
    settings.parm("camera").set("/cameras/camera1")
    for name in AOVS:
        settings.parm(name).set(1)
    settings.parm("picture").set("karma_aovs.exr")
    settings.stage().Export(scene)
    return [p for p in settings.stage().Traverse() if p.GetTypeName() == "RenderSettings"][0]


def read_layers(path):
    layers = {}
    inp = oiio.ImageInput.open(path)
    if inp is None:
        return layers
    sub = 0
    while inp.seek_subimage(sub, 0):
        layers[inp.spec().get_string_attribute("name")] = inp.read_image(oiio.FLOAT)
        sub += 1
    inp.close()
    return layers


def main():
    scene = os.path.join(OUT, "karma.usda").replace("\\", "/")
    settings = build(scene)
    exr = os.path.join(OUT, "karma_aovs.exr")
    if os.path.exists(exr):
        os.remove(exr)
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                    "--settings", str(settings.GetPath()), "--res", "128", "128",
                    "-o", exr, scene], capture_output=True, text=True, env=env, cwd=OUT)
    layers = read_layers(exr)
    if not layers:
        print("NO IMAGE")
        sys.exit(1)

    def at(name, c=0):
        return float(layers[name][64, 64, c]) if name in layers else float("nan")

    beauty = at("C")
    checks = [
        ("beauty", beauty > 0.3, "C %.3f" % beauty),
        ("combineddiffuse", abs(at("combineddiffuse") - beauty) < 0.01, "%.3f, expected the beauty" % at("combineddiffuse")),
        ("directdiffuse", abs(at("directdiffuse") - beauty) < 0.01, "%.3f, expected the beauty" % at("directdiffuse")),
        ("indirectdiffuse", abs(at("indirectdiffuse")) < 0.01, "%.3f, expected 0 (one convex object)" % at("indirectdiffuse")),
        ("glossy", abs(at("combinedglossyreflection")) < 0.01, "%.3f, expected 0 (diffuse only)" % at("combinedglossyreflection")),
        ("emission", "combinedemission" in layers and abs(at("combinedemission")) < 0.01,
         "%.3f, expected 0 and present" % at("combinedemission")),
        ("albedo", abs(at("albedo") - 0.8) < 0.02, "%.3f, expected 0.8" % at("albedo")),
        ("depth", abs(at("depth") - 5.0) < 0.05, "%.3f, expected 5" % at("depth")),
        ("P", abs(at("P", 2) - 1.0) < 0.02, "z %.3f, expected 1" % at("P", 2)),
        ("N", abs(at("N", 2) - 1.0) < 0.02, "z %.3f, expected 1" % at("N", 2)),
        ("all present", all(n in layers for n in ("UV", "motionvectors")),
         "layers %s" % sorted(layers)),
    ]
    problems = 0
    for name, ok, detail in checks:
        print("%-18s %-6s %s" % (name, "ok" if ok else "WRONG", detail))
        problems += not ok
    print("\n%d checks, %d problems" % (len(checks), problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
