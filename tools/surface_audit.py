"""Does each input of a surface model do in Cycles what it does in Karma?

For one surface nodedef (open_pbr_surface by default), every value input is
moved off its default, alone, on the agreement bench's sphere
(bench_agree.py), and rendered by Cycles and by Karma. What is compared is
the input's *effect*: the sphere's mean colour with the input moved, minus
the mean with everything at its default - per engine. An input whose effect
Karma shows and Cycles does not is dead in the translation; one whose effect
goes the other way, or is off by more than twice, is translated wrong.

An input that only shows when its lobe is on - a coat colour without coat,
a transmission colour without transmission - is measured with that lobe on,
in the default render too: the effect stays the input's own.

    hython tools/surface_audit.py [nodedef] [pattern]

Scenes and images go to tests/agreement/output/audit/.
"""

import os
import subprocess
import sys

import numpy as np
import OpenImageIO as oiio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_agree  # noqa: E402  (the scene, the renderer call)
import mtlx_rules  # noqa: E402

OUT = os.path.join(bench_agree.OUT, "audit")
BOX = bench_agree.PEAK_BOX
THRESH = 0.006     # an effect smaller than this on the sphere's mean is none
DEAD = 0.25        # Cycles' effect below this fraction of Karma's: dead
FACTOR = 2.0       # effects further apart than this: wrong

# Inputs whose effect needs another one set first, beyond the generic rule
# (an input `x_y` needs `x` or `x_weight` when that one defaults to zero).
NEEDS = {
    "specular_rotation": {"specular_anisotropy": "0.8"},
    "specular_roughness_anisotropy": {},
    "thin_film_IOR": {"thin_film_thickness": "500"},
    "geometry_thin_walled": {"transmission_weight": "1"},
    "thin_walled": {"transmission": "1"},
    "emission_color": {"emission": "1", "emission_luminance": "1"},
}


# A starting point per model, where its default is a poor one to measure
# from: glTF's is a white, fully rough metal, on which a thin film or a
# specular tint has next to nothing to act.
BASE = {
    "ND_gltf_pbr_surfaceshader": {"metallic": "0", "roughness": "0.3",
                                  "base_color": "(0.6, 0.6, 0.6)"},
}


def moved(inp):
    """A value off the input's default, as a USD literal, or None to skip."""
    t = inp.getType()
    name = inp.getName().lower()
    text = inp.getValueString()
    if t == "boolean":
        return "true" if text.strip().lower() not in ("true", "1") else "false"
    if t in ("float", "integer"):
        try:
            v = float(text)
        except ValueError:
            return None
        if "ior" in name:
            new = 2.2
        elif "thickness" in name:
            new = 700.0 if v < 50 else v * 0.5
        elif v == 0.0:
            new = 0.8
        elif v == 1.0:
            new = 0.3
        else:
            new = v * 2.0
        return "%d" % int(new) if t == "integer" else "%g" % new
    if t in ("color3", "vector3"):
        return "(0.9, 0.3, 0.1)" if "radius" not in name else "(1, 0.2, 0.05)"
    return None


def enablers(nd, inp):
    """Inputs to set for this one to show, with their values."""
    name = inp.getName()
    if name in NEEDS:
        return {k: v for k, v in NEEDS[name].items() if nd.getActiveInput(k) is not None}
    family = name.split("_")[0]
    for cand in (family, family + "_weight"):
        other = nd.getActiveInput(cand)
        if other is None or cand == name or other.getType() != "float":
            continue
        try:
            if float(other.getValueString()) == 0.0:
                return {cand: "1"}
        except ValueError:
            pass
    return {}


def render_both(nd_name, inputs, tag):
    scene = os.path.join(OUT, tag + ".usda")
    open(scene, "w", encoding="utf-8").write(bench_agree.scene_text(nd_name, inputs))
    means = []
    for renderer, suffix in (("HdCyclesPlugin", "cycles"), ("BRAY_HdKarma", "karma")):
        img = bench_agree.render(renderer, scene, os.path.join(OUT, "%s_%s.exr" % (tag, suffix)))
        if img is None:
            return None
        x0, x1, y0, y1 = BOX
        means.append(img[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0))
    return means


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    nd_name = args[0] if args else "ND_open_pbr_surface_surfaceshader"
    pattern = args[1] if len(args) > 1 else None
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    bench_agree.OUT = OUT  # renders run from there
    library = mtlx_rules.load_library()  # kept: a nodedef does not hold its document
    nd = library.getNodeDef(nd_name)
    if nd is None:
        sys.exit("no nodedef %s" % nd_name)
    uniform = {"float": "float", "integer": "int", "boolean": "bool",
               "color3": "color3f", "vector3": "float3"}
    baselines = {}
    rows = []
    for inp in nd.getActiveInputs():
        t = inp.getType()
        if t not in uniform or inp.getDefaultGeomPropString():
            continue
        if pattern and pattern not in inp.getName():
            continue
        value = moved(inp)
        if value is None:
            continue
        need = {k: v for k, v in BASE.get(nd_name, {}).items() if k != inp.getName()}
        need.update(enablers(nd, inp))
        key = tuple(sorted(need.items()))
        base_inputs = {"%s inputs:%s" % (uniform[nd.getActiveInput(k).getType()], k): v
                       for k, v in need.items()}
        if key not in baselines:
            baselines[key] = render_both(nd_name, base_inputs, "base_%d" % len(baselines))
        test_inputs = dict(base_inputs)
        prefix = "uniform " if inp.getIsUniform() else ""
        test_inputs["%s%s inputs:%s" % (prefix, uniform[t], inp.getName())] = value
        result = render_both(nd_name, test_inputs, inp.getName())
        base = baselines[key]
        if result is None or base is None:
            rows.append((inp.getName(), "NO IMAGE", None, None))
            continue
        d_cyc, d_kar = result[0] - base[0], result[1] - base[1]
        big_c, big_k = np.abs(d_cyc).max(), np.abs(d_kar).max()
        if big_k < THRESH and big_c < THRESH:
            verdict = "no effect in either"
        elif big_k >= THRESH and big_c < DEAD * big_k:
            verdict = "DEAD in Cycles"
        elif big_c >= THRESH and big_k < DEAD * big_c:
            verdict = "Cycles only"
        else:
            idx = np.abs(d_kar) >= THRESH
            ratio = d_cyc[idx] / d_kar[idx]
            if np.any(ratio <= 0):
                verdict = "OPPOSITE"
            elif np.any(ratio > FACTOR) or np.any(ratio < 1 / FACTOR):
                verdict = "OFF %.1fx" % float(np.median(ratio))
            else:
                verdict = "ok"
        rows.append((inp.getName(), verdict, d_cyc, d_kar))
        print("%-38s %-20s cycles %s  karma %s" % (inp.getName(), verdict, np.round(d_cyc, 3),
                                                    np.round(d_kar, 3)), flush=True)
    counts = {}
    for _, verdict, _, _ in rows:
        key = verdict.split()[0]
        counts[key] = counts.get(key, 0) + 1
    print("\n%s: %d inputs - %s" % (nd_name, len(rows),
                                    ", ".join("%s %d" % kv for kv in sorted(counts.items()))))


if __name__ == "__main__":
    main()
