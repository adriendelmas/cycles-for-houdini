"""Compare the last bench run against the committed reference images.

Two checks, in this order:

* regression: output/<node>.exr must match references/<node>.exr within
  tolerance. A reference moves only through `--accept <node>` (or `--accept
  all`), which is a reviewed commit, never a side effect of rendering;
* inertness: a node whose image equals `_baseline.exr` changes nothing. Not
  necessarily broken - a constant equal to the default is invisible - but
  worth a look.

    python tools/bench_diff.py [--accept node|all]
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFS = os.path.join(os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368"), "bin")
INSTALL = os.environ.get("CYCLES_INSTALL_DIR", "install")
BENCH = os.path.join(ROOT, "tests", "usd", "bench" if INSTALL == "install" else "bench-53")
OUTPUT = os.path.join(BENCH, "output")
REFERENCES = os.path.join(BENCH, "references")
env = dict(os.environ)
env["PATH"] = HFS + ";" + env["PATH"]

# Path-tracing noise between two runs of the same build stays well below this;
# an inverted mix or a greyed colour is orders of magnitude above it.
FAIL = "1e-3"
FAIL_PERCENT = "0.5"


def diff(a, b, *extra):
    r = subprocess.run([os.path.join(HFS, "hoiiotool.exe"), *extra, "--diff", a, b],
                       capture_output=True, text=True, env=env)
    return "PASS" in (r.stdout or "")


def main():
    accept = None
    if "--accept" in sys.argv:
        accept = sys.argv[sys.argv.index("--accept") + 1]

    names = sorted(f[:-4] for f in os.listdir(OUTPUT)
                   if f.endswith(".exr") and f != "_baseline.exr")
    if accept:
        for name in names if accept == "all" else [accept]:
            shutil.copyfile(os.path.join(OUTPUT, name + ".exr"),
                            os.path.join(REFERENCES, name + ".exr"))
            print("accepted", name)
        return

    baseline = os.path.join(OUTPUT, "_baseline.exr")
    regressions, missing, inert = [], [], []
    for name in names:
        out = os.path.join(OUTPUT, name + ".exr")
        ref = os.path.join(REFERENCES, name + ".exr")
        if not os.path.exists(ref):
            missing.append(name)
        elif not diff(ref, out, "--fail", FAIL, "--failpercent", FAIL_PERCENT):
            regressions.append(name)
        if os.path.exists(baseline) and diff(baseline, out):
            inert.append(name)

    print("%d nodes compared to their references" % len(names))
    print("%d regressions:" % len(regressions))
    for n in regressions:
        print("   ", n)
    if missing:
        print("%d without a reference (bench_diff.py --accept <node> once reviewed):" % len(missing))
        for n in missing:
            print("   ", n)
    print("%d with no visible effect against the baseline:" % len(inert))
    for n in inert:
        print("   ", n)
    sys.exit(1 if regressions else 0)


if __name__ == "__main__":
    main()
