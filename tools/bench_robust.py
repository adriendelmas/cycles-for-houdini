"""Does the delegate survive a malformed file?

Each `tests/scenes/bad_*.usda` carries one attribute USD could not parse - a
misspelt type name, so the value reaches Hydra as an empty array of the right
type. Karma renders such a file and ignores the attribute; the delegate read
past the end of the empty array and took husk down with it (K-57). Each scene
must render, with an image on disk and a husk exit code of 0.

    python tools/bench_robust.py

Images go to tests/scratch/robust/ (ignored).
"""

import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
OUT = os.path.join(ROOT, "tests", "scratch", "robust")


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    scenes = sorted(glob.glob(os.path.join(ROOT, "tests", "scenes", "bad_*.usda")))
    problems = []
    for scene in scenes:
        name = os.path.splitext(os.path.basename(scene))[0]
        exr = os.path.join(OUT, name + ".exr")
        if os.path.exists(exr):
            os.remove(exr)
        run = subprocess.run([os.path.join(HFS, "husk.exe"), "--renderer", "HdCyclesPlugin",
                              "--frame", "1", "--frame-count", "1", "--camera", "/world/camera",
                              "--res", "120", "90", "--output", exr, scene],
                             capture_output=True, text=True)
        log = (run.stdout or "") + (run.stderr or "")
        if "Fatal error" in log or run.returncode != 0 or not os.path.exists(exr):
            reason = "crashed" if "Fatal error" in log else "exit %d, no image" % run.returncode
            problems.append((name, reason))
            print("%-22s %s" % (name, reason.upper()))
        else:
            print("%-22s ok" % name)
    print("\n%d malformed scenes, %d problems" % (len(scenes), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
