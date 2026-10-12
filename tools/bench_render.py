"""Renders one material per Cycles node and reports what is wrong.

Three things are watched, in order of importance:

* a delegate warning, which betrays a socket that the generated VOP names
  differently from Cycles - this is the defect this bench has to catch;
* a missing image, hence a render that failed;
* an entirely black image, which signals a dead material.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
# Which installation to target (Cycles 5.3, installed in `install-53`).
INSTALL = os.environ.get("CYCLES_INSTALL_DIR", "install-53")
VERSION = "5.3"
BENCH = os.path.join(ROOT, "tests", "nodes", VERSION)
SCENES = os.path.join(BENCH, "scenes")
# What the run produces; the committed references live next door in
# references/ and move only through bench_diff.py --accept.
IMAGES = os.path.join(BENCH, "output")
for d in (SCENES, IMAGES):
    if not os.path.isdir(d):
        os.makedirs(d)

BASE = open(os.path.join(ROOT, "tests", "materialx", "scenes", "phase4b_mtlx.usda"),
            encoding="utf-8").read()

env = dict(os.environ)
# A PXR_PLUGINPATH_NAME already in the environment wins: that is how a freshly
# built DLL is tested from a temporary tree while Houdini holds the installed one.
env.setdefault("PXR_PLUGINPATH_NAME", os.path.join(ROOT, INSTALL, "houdini", "dso", "usd_plugins"))
env["PATH"] = HFS + ";" + env["PATH"]


def scene_for(name):
    """The test scene, with the node's material stacked as a sublayer."""
    text = BASE.replace("rel material:binding = </world/Materials/mxMetal>",
                        "rel material:binding = </world/Materials/cyclesmat>")
    lines = text.splitlines()
    end = next(i for i, l in enumerate(lines) if l.strip() == ")")
    lines.insert(end, '    subLayers = [\n        @../%s.usda@\n    ]' % name)
    path = os.path.join(SCENES, name + ".usda")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    return path


def stats(path):
    out = subprocess.run([os.path.join(HFS, "hoiiotool.exe"), "--stats", path],
                         capture_output=True, text=True, env=env).stdout or ""
    maxima = [l for l in out.splitlines() if "Stats Max" in l]
    if not maxima:
        return None
    return max(float(v) for v in maxima[0].split(":")[1].split()[:3])


names = sorted(f[:-5] for f in os.listdir(BENCH) if f.endswith(".usda"))
only = sys.argv[1] if len(sys.argv) > 1 else None
if only:
    names = [n for n in names if only in n]

print("%-34s %-10s %s" % ("node", "state", "detail"))
problems = []
for name in names:
    usd = scene_for(name)
    exr = os.path.join(IMAGES, name + ".exr")
    if os.path.exists(exr):
        os.remove(exr)
    run = subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                          "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                          "--res", "120", "90", "--output", exr, usd],
                         capture_output=True, text=True, env=env, cwd=SCENES)
    log = (run.stdout or "") + (run.stderr or "")
    warns = [l.split("WARNING:")[-1].strip() for l in log.splitlines()
             if "WARNING" in l and ("Cycles node" in l or "MaterialX" in l)]

    if not os.path.exists(exr):
        state, detail = "NO IMAGE", (log.strip().splitlines() or [""])[-1][:60]
    elif warns:
        state, detail = "WARNED", warns[0][:70]
    else:
        peak = stats(exr)
        if peak is None:
            state, detail = "UNREADABLE", ""
        elif peak <= 1e-6:
            state, detail = "BLACK", ""
        else:
            state, detail = "ok", ""
    if state != "ok":
        problems.append((name, state, detail))
    print("%-34s %-10s %s" % (name, state, detail))

print("\n%d nodes rendered, %d problems" % (len(names), len(problems)))
for name, state, detail in problems:
    print("   %-32s %-12s %s" % (name, state, detail))
