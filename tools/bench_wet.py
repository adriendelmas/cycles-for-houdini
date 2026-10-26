"""Wet map (addition, docs/WETMAP_PLAN.md): what the renderer measures against
a chosen set of objects, and - later - what it keeps from one frame to the next.

Five unlit probe quads face an orthographic camera, one scene each so that
no probe sees another, each glowing with the AO its material computes
*inside* (rays traced away from the camera, towards whatever lies behind the
probe at distance 0.1, AO distance 1: a wide plane there leaves
(0.1 / 1)^2 = 0.01 of the cosine-weighted rays unoccluded, the ones beyond
the AO distance):

    water      a plane behind it that keeps its raycast visibility (the target)
    wall       a plane behind it with raycast visibility off, AO set to
               raycast visibility: must not occlude (case 1)
    wall_ctl   the same wall, AO left on every object: must occlude - the
               control that says case 1 means something
    hidden     a plane hidden from every ray type: must not occlude (case 5,
               the OptiX zero-mask fallback)
    free       nothing behind it

    hython tools/bench_wet.py [--gpu] [pattern]

Rendered by husk on the CPU plugin, and with --gpu on the GPU plugin under
CYCLES_DEVICE=OPTIX as well. Scenes and images go to tests/wet/output/.
"""

import os
import subprocess
import sys

import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ["HFS"], "bin")
OUT = os.path.join(ROOT, "tests", "wet", "output")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

RES = 120
PROBE = 0.8
DEPTH = 0.1
BLOCK = 8
OCCLUDED = DEPTH * DEPTH  # AO distance 1

# name, what lies behind (None, or the primvars of the backing plane), AO on raycast visibility only, expected AO
PROBES = [
    ("water", "", True, OCCLUDED),
    ("wall", "bool primvars:cycles:object:visibility:raycast = 0", True, 1.0),
    ("wall_ctl", "bool primvars:cycles:object:visibility:raycast = 0", False, OCCLUDED),
    ("hidden", "\n".join("bool primvars:cycles:object:visibility:%s = 0" % ray for ray in
                         ("camera", "diffuse", "glossy", "transmission", "shadow", "volume_scatter", "raycast")),
     True, 1.0),
    ("free", None, True, 1.0),
]
TOLERANCE = 0.05

SCENE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
)

def Scope "Render"
{
    def RenderSettings "settings"
    {
        rel camera = </world/camera>
        int2 resolution = (%(res)d, %(res)d)
        int cycles:samples = 16
    }
}

def Xform "world"
{
    def Camera "camera"
    {
        token projection = "orthographic"
        float horizontalAperture = 50
        float verticalAperture = 50
        float2 clippingRange = (0.1, 100)
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (0, 0, 10, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }
    def DomeLight "black"
    {
        float inputs:intensity = 0
    }
    def Scope "Materials"
    {
%(materials)s
    }
%(body)s
}
"""

MATERIAL = """        def Material "glow_%(name)s"
        {
            token outputs:cycles:surface.connect = </world/Materials/glow_%(name)s/e.outputs:emission>
            def Shader "e"
            {
                uniform token info:id = "cycles_emission"
                color3f inputs:color = (1, 1, 1)
                float inputs:strength.connect = </world/Materials/glow_%(name)s/ao.outputs:ao>
                token outputs:emission
            }
            def Shader "ao"
            {
                uniform token info:id = "cycles_ambient_occlusion"
                int inputs:samples = 16
                float inputs:distance = 1
                int inputs:inside = 1
                int inputs:raycast_visibility = %(raycast)d
                float outputs:ao
            }
        }"""

QUAD = """    def Mesh "%(name)s" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/%(material)s>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-%(h)g, -%(h)g, 0), (%(h)g, -%(h)g, 0), (%(h)g, %(h)g, 0), (-%(h)g, %(h)g, 0)]
        uniform token subdivisionScheme = "none"
        matrix4d xformOp:transform = ( (1,0,0,0), (0,1,0,0), (0,0,1,0), (%(x)g, 0, %(z)g, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]
%(primvars)s
    }"""


def indent(text, n):
    return "\n".join(" " * n + line if line else line for line in text.splitlines())


def scene(name, backing, raycast):
    materials = [MATERIAL % {"name": name, "raycast": int(raycast)}]
    body = [QUAD % {"name": "probe", "material": "glow_" + name, "h": PROBE / 2,
                    "x": 0.0, "z": DEPTH, "primvars": ""}]
    if backing is not None:
        # Wide enough that every ray within the AO distance meets it.
        body.append(QUAD % {"name": "behind", "material": "glow_" + name, "h": 2.0,
                            "x": 0.0, "z": 0.0, "primvars": indent(backing, 8)})
    return SCENE % {"res": RES, "materials": "\n".join(materials), "body": "\n".join(body)}


def render(usda, exr, gpu):
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    env["MSYS_NO_PATHCONV"] = "1"
    renderer = "HdCyclesPlugin"
    if gpu:
        renderer = "HdCyclesPluginGPU"
        env["CYCLES_DEVICE"] = "OPTIX"
    run = subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer,
                          "-s", "/Render/settings", "--frame", "1", "--frame-count", "1",
                          "--output", exr, usda], env=env, capture_output=True, text=True)
    if run.returncode != 0 or not os.path.exists(exr):
        print(run.stdout[-2000:])
        print(run.stderr[-2000:])
        raise SystemExit("husk failed on " + usda)


def centre_mean(exr):
    image = oiio.ImageBuf(exr)
    px = RES // 2
    py = RES // 2
    total = 0.0
    for j in range(py - BLOCK // 2, py + BLOCK // 2):
        for i in range(px - BLOCK // 2, px + BLOCK // 2):
            total += image.getpixel(i, j)[0]
    return total / (BLOCK * BLOCK)


def main():
    gpu = "--gpu" in sys.argv
    patterns = [a for a in sys.argv[1:] if not a.startswith("--")]
    problems = 0
    for name, backing, raycast, expected in PROBES:
        if patterns and not any(p in name for p in patterns):
            continue
        usda = os.path.join(OUT, name + ".usda")
        with open(usda, "w") as f:
            f.write(scene(name, backing, raycast))
        for device in ["cpu"] + (["gpu"] if gpu else []):
            exr = os.path.join(OUT, "%s_%s.exr" % (name, device))
            render(usda, exr, device == "gpu")
            got = centre_mean(exr)
            ok = abs(got - expected) <= TOLERANCE
            problems += not ok
            print("%-4s %-9s AO %.3f expected %.2f %s" % (device, name, got, expected, "ok" if ok else "PROBLEM"))
    print("%d problem(s)" % problems)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
