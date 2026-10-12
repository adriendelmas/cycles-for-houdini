"""Compare the last bench run against the committed reference images.

Two checks, in this order:

* regression: output/<node>.exr must match references/<node>.exr within
  tolerance. A reference moves only through `--accept <node>` (or `--accept
  all`), which is a reviewed commit, never a side effect of rendering;
* inertness: a node whose image equals `_baseline.exr` changes nothing. Not
  necessarily broken - a constant equal to the default is invisible - but
  worth a look.

Runs under hython for Houdini's OpenImageIO and numpy: its `hoiiotool` has no
relative threshold, and an absolute one alone calls a half-float ulp on a
value of thirty a regression.

    hython tools/bench_diff.py [--accept node|all]
"""
import os
import shutil
import sys

import numpy as np
import OpenImageIO as oiio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.environ.get("CYCLES_INSTALL_DIR", "install-53")
VERSION = "5.3"
BENCH = os.path.join(ROOT, "tests", "nodes", VERSION)
OUTPUT = os.path.join(BENCH, "output")
REFERENCES = os.path.join(BENCH, "references")

# A pixel fails when it is off by more than FAIL *and* by more than
# FAIL_RELATIVE of its value; FAIL_PERCENT of the pixels may fail. The relative
# bound is what lets HDR values through: two builds of the same source render
# a 32.7 sky one half-float ulp apart (0.03), which the absolute bound alone
# called a regression. An inverted mix or a greyed colour is orders of
# magnitude above both.
FAIL = 1e-3
FAIL_RELATIVE = 1e-2
FAIL_PERCENT = 0.5

# References that are not references, with the issue that says why. They are
# rendered and reported, never counted.
KNOWN_UNSTABLE = {
    "cycles_set_normal": "A19: the scene gives no direction and the image holds infinities",
}


def pixels(path):
    buf = oiio.ImageBuf(path)
    if buf.has_error:
        return None
    return buf.get_pixels(oiio.FLOAT)


def failing_percent(a, b):
    """Percentage of pixels that differ beyond both thresholds. Non-finite
    values count as different unless both sides hold the same one."""
    if a is None or b is None or a.shape != b.shape:
        return 100.0
    finite = np.isfinite(a) & np.isfinite(b)
    d = np.abs(a - b)
    scale = np.maximum(np.maximum(np.abs(a), np.abs(b)), 1e-6)
    bad = finite & (d > FAIL) & (d / scale > FAIL_RELATIVE)
    bad |= ~finite & ~(a == b)
    return 100.0 * bad.any(axis=-1).mean()


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

    baseline = pixels(os.path.join(OUTPUT, "_baseline.exr")) \
        if os.path.exists(os.path.join(OUTPUT, "_baseline.exr")) else None
    regressions, missing, inert, unstable = [], [], [], []
    for name in names:
        out = pixels(os.path.join(OUTPUT, name + ".exr"))
        ref_path = os.path.join(REFERENCES, name + ".exr")
        if name in KNOWN_UNSTABLE:
            unstable.append(name)
        elif not os.path.exists(ref_path):
            missing.append(name)
        else:
            percent = failing_percent(pixels(ref_path), out)
            if percent > FAIL_PERCENT:
                regressions.append((name, percent))
        if baseline is not None and out is not None and out.shape == baseline.shape \
                and np.array_equal(np.nan_to_num(out), np.nan_to_num(baseline)):
            inert.append(name)

    print("%d nodes compared to their references" % len(names))
    print("%d regressions:" % len(regressions))
    for n, percent in regressions:
        print("    %-34s %.2f%% of pixels off" % (n, percent))
    if missing:
        print("%d without a reference (bench_diff.py --accept <node> once reviewed):" % len(missing))
        for n in missing:
            print("   ", n)
    print("%d with no visible effect against the baseline:" % len(inert))
    for n in inert:
        print("   ", n)
    for n in unstable:
        print("not compared: %s (%s)" % (n, KNOWN_UNSTABLE[n]))
    sys.exit(1 if regressions else 0)


if __name__ == "__main__":
    main()
