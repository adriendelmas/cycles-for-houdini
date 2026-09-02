"""Rend un materiau par noeud Cycles et rapporte ce qui cloche.

Trois choses sont surveillees, par ordre d'importance :

* un avertissement du delegate, qui trahit un socket que le VOP genere nomme
  autrement que Cycles - c'est le defaut que ce banc doit attraper ;
* une image absente, donc un rendu qui a echoue ;
* une image entierement noire, qui signale un materiau mort.
"""

import os
import subprocess
import sys

ROOT = r"E:\WORK\PERSONNAL STUFF\HOUDINI\hdCycles"
HFS = r"E:\Side Effects Software\Houdini22.0.368\bin"
BENCH = os.path.join(ROOT, "tests", "usd", "bench")
SCENES = os.path.join(BENCH, "scenes")
IMAGES = os.path.join(BENCH, "images")
for d in (SCENES, IMAGES):
    if not os.path.isdir(d):
        os.makedirs(d)

BASE = open(os.path.join(ROOT, "tests", "usd", "phase4b_mtlx.usda"), encoding="utf-8").read()

env = dict(os.environ)
env["PXR_PLUGINPATH_NAME"] = "E:/WORK/PERSONNAL STUFF/HOUDINI/hdCycles/install/houdini/dso/usd_plugins"
env["PATH"] = HFS + ";" + env["PATH"]


def scene_for(name):
    """La scene de test, avec le materiau du noeud empile en sous-couche."""
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

print("%-34s %-10s %s" % ("noeud", "etat", "detail"))
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
        state, detail = "PAS D'IMAGE", (log.strip().splitlines() or [""])[-1][:60]
    elif warns:
        state, detail = "AVERTI", warns[0][:70]
    else:
        peak = stats(exr)
        if peak is None:
            state, detail = "ILLISIBLE", ""
        elif peak <= 1e-6:
            state, detail = "NOIRE", ""
        else:
            state, detail = "ok", ""
    if state != "ok":
        problems.append((name, state, detail))
    print("%-34s %-10s %s" % (name, state, detail))

print("\n%d noeuds rendus, %d problemes" % (len(names), len(problems)))
for name, state, detail in problems:
    print("   %-32s %-12s %s" % (name, state, detail))
