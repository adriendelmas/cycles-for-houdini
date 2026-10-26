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

Then the state across frames (`sequence`): a probe whose Wet State node is fed
1 - AO against a raycast-visible plane 0.5 behind it (contact 0.75: the rays
beyond the AO distance of 1 miss), the plane leaving on frame 4, eight frames
in one husk run. Wet rate 50 saturates the state on the first commit, dry
time 0.25 s dries it by exp(-1/6) per frame at 24 fps:

    frame 1  0.75   nothing committed yet, the contact shows
    frame 2  1.00   the commit of frame 1
    frame 3  1.00
    frame 4  1.00   the plane is gone, the state carries (contact 0)
    frame 5  0.85   drying
    frame 6  0.72
    frame 7  0.61
    frame 8  0.51

`twice` renders frame 2 two times in one run (--frame-inc 0): the same frame
must not advance the state, so both read 0.75 - a fresh frame 2 - and not
1.00. With --gpu the sequence runs on OptiX too and must agree with the CPU.

    hython tools/bench_wet.py [--gpu] [pattern]

Rendered by husk on the CPU plugin, and with --gpu on the GPU plugin under
CYCLES_DEVICE=OPTIX as well. Scenes and images go to tests/wet/output/.
"""

import math
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

# The sequence: contact 0.75 (AO (0.5 / 1)^2 = 0.25 behind the probe), wet
# rate 50 (saturates in one frame), dry time 0.25 s, 24 fps.
SEQ_DEPTH = 0.5
SEQ_CONTACT = 1.0 - SEQ_DEPTH * SEQ_DEPTH
SEQ_FRAMES = 8
SEQ_LEAVES = 4  # first frame without the plane
SEQ_DECAY = math.exp(-(1.0 / 24.0) / 0.25)
SEQ_TOLERANCE = 0.03


def sequence_expected():
    expected = []
    for frame in range(1, SEQ_FRAMES + 1):
        if frame == 1:
            expected.append(SEQ_CONTACT)
        elif frame < SEQ_LEAVES + 1:
            expected.append(1.0)
        else:
            expected.append(SEQ_DECAY ** (frame - SEQ_LEAVES))
    return expected


SCENE = """#usda 1.0
(
    defaultPrim = "world"
    metersPerUnit = 1
    upAxis = "Y"
    startTimeCode = 1
    endTimeCode = %(frames)d
    timeCodesPerSecond = 24
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

WET_MATERIAL = """        def Material "wet"
        {
            token outputs:cycles:surface.connect = </world/Materials/wet/e.outputs:emission>
            def Shader "e"
            {
                uniform token info:id = "cycles_emission"
                color3f inputs:color = (1, 1, 1)
                float inputs:strength.connect = </world/Materials/wet/state.outputs:wet>
                token outputs:emission
            }
            def Shader "state"
            {
                uniform token info:id = "cycles_wet_state"
                float inputs:contact.connect = </world/Materials/wet/inv.outputs:color>
                float inputs:wet_rate = 50
                float inputs:dry_time = 0.25
                float inputs:max_wet = 1
                float outputs:wet
            }
            def Shader "inv"
            {
                uniform token info:id = "cycles_invert"
                float inputs:fac = 1
                color3f inputs:color.connect = </world/Materials/wet/ao.outputs:color>
                color3f outputs:color
            }
            def Shader "ao"
            {
                uniform token info:id = "cycles_ambient_occlusion"
                color3f inputs:color = (1, 1, 1)
                int inputs:samples = 16
                float inputs:distance = 1
                int inputs:inside = 1
                int inputs:raycast_visibility = 1
                color3f outputs:color
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

# The plane behind the probe, there until it leaves for good.
LEAVING_QUAD = """    def Mesh "behind" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        rel material:binding = </world/Materials/wet>
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-2, -2, 0), (2, -2, 0), (2, 2, 0), (-2, 2, 0)]
        uniform token subdivisionScheme = "none"
        double3 xformOp:translate.timeSamples = { 1: (0, 0, 0), %(last)d: (0, 0, 0), %(leaves)d: (0, 0, -50), %(frames)d: (0, 0, -50) }
        uniform token[] xformOpOrder = ["xformOp:translate"]
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
    return SCENE % {"res": RES, "frames": 1, "materials": "\n".join(materials),
                    "body": "\n".join(body)}


def sequence_scene():
    body = [QUAD % {"name": "probe", "material": "wet", "h": PROBE / 2, "x": 0.0,
                    "z": SEQ_DEPTH, "primvars": ""},
            LEAVING_QUAD % {"last": SEQ_LEAVES - 1, "leaves": SEQ_LEAVES, "frames": SEQ_FRAMES}]
    return SCENE % {"res": RES, "frames": SEQ_FRAMES, "materials": WET_MATERIAL,
                    "body": "\n".join(body)}


def render(usda, exr, gpu, frames=("--frame", "1", "--frame-count", "1")):
    env = dict(os.environ)
    env["PATH"] = HFS + ";" + env["PATH"]
    env["MSYS_NO_PATHCONV"] = "1"
    renderer = "HdCyclesPlugin"
    if gpu:
        renderer = "HdCyclesPluginGPU"
        env["CYCLES_DEVICE"] = "OPTIX"
    run = subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", renderer,
                          "-s", "/Render/settings", *frames, "--output", exr, usda],
                         env=env, capture_output=True, text=True)
    if run.returncode != 0 or ("$" not in exr and not os.path.exists(exr)):
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

    if not patterns or any(p in "sequence twice" for p in patterns):
        usda = os.path.join(OUT, "sequence.usda")
        with open(usda, "w") as f:
            f.write(sequence_scene())
        expected = sequence_expected()
        means = {}
        for device in ["cpu"] + (["gpu"] if gpu else []):
            pattern = os.path.join(OUT, "sequence_%s_$F4.exr" % device)
            render(usda, pattern, device == "gpu", ("--frame", "1", "--frame-count", str(SEQ_FRAMES)))
            means[device] = []
            for frame in range(1, SEQ_FRAMES + 1):
                got = centre_mean(pattern.replace("$F4", "%04d" % frame))
                means[device].append(got)
                ok = abs(got - expected[frame - 1]) <= SEQ_TOLERANCE
                problems += not ok
                print("%-4s sequence frame %d wet %.3f expected %.3f %s" % (device, frame, got, expected[frame - 1],
                                                                        "ok" if ok else "PROBLEM"))
            # Frame 2 twice in one run: the second must not advance the state.
            pattern = os.path.join(OUT, "twice_%s_$N.exr" % device)
            render(usda, pattern, device == "gpu", ("--frame", "2", "--frame-count", "2", "--frame-inc", "0"))
            for n in (1, 2):
                got = centre_mean(pattern.replace("$N", str(n)))
                ok = abs(got - SEQ_CONTACT) <= SEQ_TOLERANCE
                problems += not ok
                print("%-4s twice render %d wet %.3f expected %.3f %s" % (device, n, got, SEQ_CONTACT, "ok" if ok else "PROBLEM"))
        if "gpu" in means:
            # The CPU's AO sees 0.8 % of its rays stopped by the probe's own
            # coplanar second triangle (its `free` case reads 0.992, OptiX
            # 0.999): a contact of 0.008 that the wet rate turns into +0.017
            # per frame while drying. Cycles' AO, not the state.
            worst = max(abs(a - b) for a, b in zip(means["cpu"], means["gpu"]))
            ok = worst <= 0.03
            problems += not ok
            print("cpu vs gpu over the sequence: largest gap %.3f %s" % (worst, "ok" if ok else "PROBLEM"))
    print("%d problem(s)" % problems)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
