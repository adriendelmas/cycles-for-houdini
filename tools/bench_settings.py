"""Do the render settings and the per-prim properties do what they say?

Each case renders a small scene through husk and checks a few pixels against
a value it knows: the film transparent behind a dome light, the exposure
doubling the image, motion blur switched off, a Houdini volume's `Cd` field
reaching a shader that asks for the standard `color`, an unbound prim's
`displayOpacity`.

    hython tools/bench_settings.py [pattern]

Scenes and images go to tests/settings/output/. The volume case writes its
own VDB with Houdini.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "settings", "output")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

RES = 64

STAGE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
    startTimeCode = 1
    endTimeCode = 2
)
def Xform "world"
{
    def Camera "camera"
    {
        float focalLength = 35
        float horizontalAperture = 36
        float verticalAperture = 36
        double shutter:open = -0.25
        double shutter:close = 0.25
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 5, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def DomeLight "sky"
    {
        float inputs:intensity = 1
    }
%(body)s
}
def Scope "Render"
{
    def RenderSettings "settings"
    {
        rel camera = </world/camera>
        int2 resolution = (%(res)d, %(res)d)
%(settings)s
    }
}
"""

SPHERE = """    def Sphere "ball"
    {
        double radius = 1
    }"""

# A sphere sweeping from x = -1 to 1 between frames 1 and 2.
MOVING = """    def Sphere "ball"
    {
        double radius = 0.5
        double3 xformOp:translate.timeSamples = { 1: (-1, 0, 0), 2: (1, 0, 0) }
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }"""

VOLUME = """    def Volume "vol" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/M>
        rel field:density = </world/vol/density>
        rel field:Cd = </world/vol/Cd>
        def OpenVDBAsset "density"
        {
            asset filePath = @./redbox.vdb@
            token fieldName = "density"
        }
        def OpenVDBAsset "Cd"
        {
            asset filePath = @./redbox.vdb@
            token fieldName = "Cd"
        }
    }
    def Material "M"
    {
        token outputs:cycles:volume.connect = </world/M/v.outputs:volume>
        def Shader "v"
        {
            uniform token info:id = "cycles_principled_volume"
            float inputs:density = 5
            string inputs:density_attribute = "density"
            string inputs:color_attribute = "color"
            token outputs:volume
        }
    }"""


TRANSPARENT = "        bool cycles:background:transparent = 1"


def sphere_with(lines):
    return SPHERE.replace("double radius = 1", "double radius = 1" + chr(10) + lines)


# A ground plane under a sphere, lit from above: the plane catches its shadow.
CATCHER = """    def Sphere "ball"
    {
        double radius = 0.5
        double3 xformOp:translate = (0, -0.5, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
    def Mesh "ground"
    {
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-3, -1, 3), (3, -1, 3), (3, -1, -3), (-3, -1, -3)]
        uniform token subdivisionScheme = "none"
        bool primvars:cycles:object:shadow_catcher = 1
    }
    def DistantLight "sun"
    {
        float inputs:intensity = 3
        bool inputs:normalize = 1
        float3 xformOp:rotateXYZ = (-120, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
    }"""


# Two spheres; the sun lights only the left one through its lightLink
# collection.
LINKED = """    def DistantLight "sun" (
        prepend apiSchemas = ["CollectionAPI:lightLink"]
    )
    {
        float inputs:intensity = 3
        bool inputs:normalize = 1
        uniform bool collection:lightLink:includeRoot = 0
        rel collection:lightLink:includes = </world/a>
    }
    def Sphere "a"
    {
        double radius = 0.8
        double3 xformOp:translate = (-1, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
    def Sphere "b"
    {
        double radius = 0.8
        double3 xformOp:translate = (1, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }"""

# The catcher scene without the catcher, and the sphere left out of the sun's
# shadow link: the ground under it stays lit.
UNSHADOWED = CATCHER.replace("        bool primvars:cycles:object:shadow_catcher = 1" + chr(10), "").replace(
    """    def DistantLight "sun"
    {""", """    def DistantLight "sun" (
        prepend apiSchemas = ["CollectionAPI:shadowLink"]
    )
    {
        rel collection:shadowLink:excludes = </world/ball>""")


def corner(img):
    return img[2, 2]


def centre(img):
    return img[RES // 2, RES // 2]


def trail(img):
    row = img[RES // 2, :, 3]
    covered = np.where(row > 0.02)[0]
    return covered[-1] - covered[0] + 1 if len(covered) else 0


def write_vdb():
    """A unit box of fog with a constant red `Cd` vector grid."""
    path = os.path.join(OUT, "redbox.vdb")
    if os.path.exists(path):
        return
    import hou
    geo = hou.node("/obj").createNode("geo")
    box = geo.createNode("box")
    fog = geo.createNode("vdbfrompolygons")
    fog.setInput(0, box)
    fog.parm("voxelsize").set(0.05)
    fog.parm("builddistance").set(False)
    fog.parm("buildfog").set(True)
    fog.parm("fogname").set("density")
    cd = geo.createNode("volume")
    cd.setInput(0, box)
    cd.parm("name").set("Cd")
    cd.parm("rank").set("vector")
    cd.parm("initialval1").set(1)
    cd.parm("initialval2").set(0)
    cd.parm("initialval3").set(0)
    cd.parm("divsize").set(0.05)
    vdb = geo.createNode("convertvdb")
    vdb.setInput(0, cd)
    vdb.parm("conversion").set("vdb")
    vec = geo.createNode("vdbvectormerge")
    vec.setInput(0, vdb)
    merge = geo.createNode("merge")
    merge.setInput(0, fog)
    merge.setInput(1, vec)
    out = geo.createNode("file")
    out.setInput(0, merge)
    out.parm("filemode").set(2)
    out.parm("file").set(path.replace("\\", "/"))
    out.cook(force=True)


# (name, body, settings lines, husk extra args, check(img) -> error string or None)
CASES = [
    ("dome_opaque", SPHERE, "", [],
     lambda img: None if corner(img)[3] > 0.99 and corner(img)[0] > 0.9 else
     "background %s, expected the dome, opaque" % corner(img).round(3)),
    ("film_transparent", SPHERE, "        bool cycles:background:transparent = 1", [],
     lambda img: None if corner(img)[3] < 0.01 and centre(img)[3] > 0.99 and centre(img)[0] > 0.5
     else "background %s, sphere %s: expected alpha 0 behind a lit sphere"
     % (corner(img).round(3), centre(img).round(3))),
    ("film_exposure", SPHERE, "        float cycles:film:exposure = 2", [],
     lambda img: None if abs(corner(img)[0] - 2.0) < 0.02 else
     "background %.3f, expected 2 (dome 1 times exposure 2)" % corner(img)[0]),
    ("motion_on", MOVING, TRANSPARENT, ["--frame", "1.5"],
     # The sphere is 12 px across; its trail over the shutter about 25.
     lambda img: None if trail(img) > 20 else "trail %d px, expected a blur" % trail(img)),
    ("motion_off", MOVING, TRANSPARENT, ["--frame", "1.5", "--disable-motionblur"],
     lambda img: None if trail(img) < 16 else "trail %d px, expected sharp" % trail(img)),
    ("hidden_camera", sphere_with("        bool primvars:cycles:object:visibility:camera = 0"), "", [],
     lambda img: None if centre(img)[0] > 0.95 else
     "centre %s, expected the dome through a camera-invisible sphere" % centre(img).round(3)),
    ("karma_visibility", sphere_with('        string primvars:karma:object:rendervisibility = "-primary"'),
     "", [],
     lambda img: None if centre(img)[0] > 0.95 else
     "centre %s, expected the dome: Karma's -primary" % centre(img).round(3)),
    ("holdout", sphere_with("        bool primvars:cycles:object:holdout = 1"), "", [],
     lambda img: None if centre(img)[3] < 0.01 and corner(img)[3] > 0.99 else
     "centre %s, corner %s: expected a hole in an opaque image"
     % (centre(img).round(3), corner(img).round(3))),
    # The plane is below the camera; the shadow it catches shows just in
    # front of the sphere's foot (row 45, alpha about 0.2: the approximate
    # catcher folds the dome light in), the rest of it must be clear.
    ("shadow_catcher", CATCHER, TRANSPARENT, [],
     lambda img: None if img[RES - 4, 4, 3] < 0.05 and img[45, RES // 2, 3] > 0.1 else
     "plane alpha %.3f away from the shadow, %.3f under it"
     % (img[RES - 4, 4, 3], img[45, RES // 2, 3])),
    ("light_link", LINKED, "", [],
     # The dome (1) lights both, 0.8 on a 0.8 albedo; the sun only the left.
     lambda img: None if img[32, 18, 0] > 1.2 and abs(img[32, 46, 0] - 0.8) < 0.05 else
     "linked sphere %.3f, unlinked %.3f: expected dome and sun, dome only (0.8)"
     % (img[32, 18, 0], img[32, 46, 0])),
    ("shadow_link", UNSHADOWED, "", [],
     lambda img: None if img[45, RES // 2, 0] > 0.9 * img[60, RES // 2, 0] else
     "ground %.3f under the sphere, %.3f away: the sphere is out of the shadow link"
     % (img[45, RES // 2, 0], img[60, RES // 2, 0])),
    # A sun with no diffuse contribution leaves a diffuse sphere to the dome.
    ("light_no_diffuse", SPHERE + """
    def DistantLight "sun"
    {
        float inputs:intensity = 3
        bool inputs:normalize = 1
        float inputs:diffuse = 0
    }""", "", [],
     lambda img: None if abs(centre(img)[0] - 0.8) < 0.05 else
     "sphere %.3f, expected the dome alone (0.8): the sun's diffuse is 0" % centre(img)[0]),
    # An unbound sphere, black, 30 % opaque: the dome through both of its
    # sides, 0.7 x 0.7 (it rendered opaque black before 0121).
    ("display_opacity", sphere_with("        color3f[] primvars:displayColor = [(0, 0, 0)]" + chr(10) +
                                    "        float[] primvars:displayOpacity = [0.3]"), "", [],
     lambda img: None if abs(centre(img)[0] - 0.49) < 0.05 else
     "sphere %.3f, expected the dome through two 30 %% opaque sides (0.49)" % centre(img)[0]),
    # An unbound card coloured per vertex, red at the bottom, blue at the
    # top: the default surface reads it (it showed the grey fallback before).
    ("display_color_vertex", """    def Mesh "card"
    {
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)]
        color3f[] primvars:displayColor = [(1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, 1)] (
            interpolation = "vertex"
        )
    }""", "", [],
     lambda img: None if img[40, RES // 2, 0] > 3 * img[40, RES // 2, 2] and
     img[24, RES // 2, 2] > 3 * img[24, RES // 2, 0] else
     "bottom %s, top %s: expected red below, blue above"
     % (img[40, RES // 2, :3].round(3), img[24, RES // 2, :3].round(3))),
    # A volume's own primvars: hidden from camera rays, the dome shows
    # through (volumes read no primvar before 0125).
    ("volume_hidden_camera", VOLUME.replace(
        "        rel field:density = </world/vol/density>",
        "        rel field:density = </world/vol/density>" + chr(10) +
        "        bool primvars:cycles:object:visibility:camera = 0"), "", [],
     lambda img: None if centre(img)[0] > 0.95 and abs(centre(img)[0] - centre(img)[1]) < 0.05 else
     "centre %s, expected the dome through a camera-invisible volume" % centre(img).round(3)),
    ("volume_cd", VOLUME, "", [],
     lambda img: None if centre(img)[0] > 2.0 * centre(img)[1] else
     "volume %s, expected red from the Cd field" % centre(img).round(3)),
]


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else ""
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    cases = [c for c in CASES if pattern in c[0]]
    problems = 0
    for name, body, settings, extra, check in cases:
        if body is VOLUME:
            write_vdb()
        scene = os.path.join(OUT, name + ".usda")
        open(scene, "w", encoding="utf-8").write(
            STAGE % {"body": body, "settings": settings, "res": RES})
        exr = os.path.join(OUT, name + ".exr")
        if os.path.exists(exr):
            os.remove(exr)
        subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                        "--settings", "/Render/settings", "--output", exr, "--frame-count", "1"]
                       + (extra if "--frame" in extra else ["--frame", "1"] + extra) + [scene],
                       capture_output=True, text=True, env=env, cwd=OUT)
        buf = oiio.ImageBuf(exr)
        if buf.has_error:
            print("%-18s NO IMAGE" % name)
            problems += 1
            continue
        error = check(buf.get_pixels(oiio.FLOAT))
        print("%-18s %-6s %s" % (name, "ok" if error is None else "WRONG", error or ""))
        problems += error is not None
    print("\n%d cases, %d problems" % (len(cases), problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
