"""Writes tests/houdini/lights_live.hip, the scene for checking light edits live.

The floor, boards and rect light of `bench_light_split.py`, plus a cylinder
light, in a LOP network: `scene` imports them, `edit` sets the rect light's
shadow colour and lobe multipliers and the cylinder's roll from the Python
it holds - a GUI check rewrites that code through tools/hou_remote.py and
watches the viewport follow, without restarting the render (K-87, K-89).

    hython tools/make_lights_live_hip.py
"""

import os
import sys

import hou

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bench_light_split as split  # noqa: E402

CYLINDER = """
    def CylinderLight "tube"
    {
        float inputs:radius = 0.1
        float inputs:length = 3
        float inputs:intensity = 3
        float3 xformOp:translate = (0, 3, 4.5)
        float3 xformOp:rotateXYZ = (-90, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
    }
}
"""

EDIT = """from pxr import Gf
stage = hou.pwd().editableStage()
light = stage.GetPrimAtPath('/world/light')
light.CreateAttribute('inputs:shadow:color', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.6, 0.2, 0))
light.CreateAttribute('inputs:specular', Sdf.ValueTypeNames.Float).Set(1.0)
light.CreateAttribute('inputs:diffuse', Sdf.ValueTypeNames.Float).Set(1.0)
tube = stage.GetPrimAtPath('/world/tube')
tube.GetAttribute('xformOp:rotateXYZ').Set(Gf.Vec3f(-90, 0, 0))
"""


def main():
    hou.hipFile.clear(suppress_save_prompt=True)
    scene_text = split.SCENE % dict(res=split.RES, quads=split.QUADS, inputs="")
    scene_text = scene_text.rstrip()[:-1] + CYLINDER
    scene = hou.node("/stage").createNode("pythonscript", "scene")
    scene.parm("python").set("hou.pwd().editableLayer().ImportFromString(%r)" % scene_text)
    edit = hou.node("/stage").createNode("pythonscript", "edit")
    edit.setFirstInput(scene)
    edit.parm("python").set("from pxr import Sdf\n" + EDIT)
    edit.setDisplayFlag(True)
    path = os.path.join(ROOT, "tests", "houdini", "lights_live.hip")
    hou.hipFile.save(path.replace(os.sep, "/"))
    print("written", path)


if __name__ == "__main__":
    main()
