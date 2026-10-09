"""Does a COP texture (`op:` path) reach the render through a USD Render ROP?

husk, which the USD Render ROP runs and which a farm runs, has no Houdini
session: an `op:/img/...` texture path cannot be read there, and Karma
renders it black, Cycles magenta. hdCycles adds an output processor to every
new USD Render ROP that cooks each referenced COP to a file beside the USD
it writes (K-40). This bench builds a throwaway scene in this hython - a red
constant COP, a quad whose emission reads it through `op:`, authored in a
LOP layer - and renders it through a fresh USD Render ROP with Karma and
with Cycles: both must show the COP's red, and the ROP must carry the
processor without anyone adding it.

    hython tools/bench_cop_rop.py

Run it with hdCycles' Houdini directory on HOUDINI_PATH (the package, or
HOUDINI_PATH="<install>/houdini;&"), so the creation hook and the processor
load. Images go to tests/cop/output/.
"""

import os
import sys

import hou
import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tests", "cop", "output")
RED = (0.9, 0.1, 0.1)

SCENE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = 20
        float verticalAperture = 20
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,10,1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def Mesh "quad" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/M>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-1,-1,0), (1,-1,0), (1,1,0), (-1,1,0)]
        texCoord2f[] primvars:st = [(0,0), (1,0), (1,1), (0,1)] (interpolation = "vertex")
    }
    def Scope "Materials"
    {
        def Material "M"
        {
            token outputs:surface.connect = </world/Materials/M/surf.outputs:surface>
            def Shader "surf"
            {
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0, 0, 0)
                color3f inputs:emissiveColor.connect = </world/Materials/M/tex.outputs:rgb>
                token outputs:surface
            }
            def Shader "st"
            {
                uniform token info:id = "UsdPrimvarReader_float2"
                string inputs:varname = "st"
                float2 outputs:result
            }
            def Shader "tex"
            {
                uniform token info:id = "UsdUVTexture"
                asset inputs:file = @op:/img/net/red@
                float2 inputs:st.connect = </world/Materials/M/st.outputs:result>
                float3 outputs:rgb
            }
        }
    }
}
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    hou.hipFile.clear(suppress_save_prompt=True)
    net = hou.node("/img").createNode("img", "net")
    cop = net.createNode("color", "red")
    for parm, value in zip(("colorr", "colorg", "colorb"), RED):
        cop.parm(parm).set(value)
    cop.setDisplayFlag(True)

    scene = hou.node("/stage").createNode("pythonscript", "scene")
    scene.parm("python").set("hou.pwd().editableLayer().ImportFromString(%r)" % SCENE)

    problems = 0
    for renderer in ("BRAY_HdKarma", "HdCyclesPlugin"):
        rop = hou.node("/stage").createNode("usdrender_rop", "render_" + renderer)
        rop.setFirstInput(scene)
        hooked = rop.parm("enableoutputprocessor_hdcycles_cookcoptextures") is not None
        rop.parm("renderer").set(renderer)
        exr = os.path.join(OUT, "%s.exr" % renderer)
        if os.path.exists(exr):
            os.remove(exr)
        rop.parm("outputimage").set(exr.replace(os.sep, "/"))
        rop.parm("override_res").set("specific")
        rop.parm("res_user1").set(32)
        rop.parm("res_user2").set(32)
        try:
            rop.render(verbose=False)
        except hou.OperationFailed:
            pass
        if not os.path.exists(exr):
            print("%-15s NO IMAGE (processor on the ROP: %s)" % (renderer, hooked))
            problems += 1
            continue
        centre = oiio.ImageBuf(exr).get_pixels(oiio.FLOAT)[16, 16, :3]
        # The quad sits in husk's default lighting, which brightens it alike
        # in both engines: the COP's red has to dominate, as it does nowhere
        # else (missing reads black in Karma, magenta in Cycles).
        ok = hooked and centre[0] > 0.5 and centre[0] > 3 * centre[1] and centre[0] > 3 * centre[2]
        print("%-15s %s  centre %s, processor on the ROP: %s"
              % (renderer, "ok     " if ok else "WRONG  ", np.round(centre, 3), hooked))
        problems += 0 if ok else 1
    print("\n2 renderers, %d problems" % problems)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
