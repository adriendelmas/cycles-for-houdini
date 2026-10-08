"""What the MaterialX translation covers, and what it leaves aside.

The denominator is the MaterialX library shipped with Houdini, read by
MaterialX itself; the numerator is the delegate's mapping table, re-read from
`material.cpp`. The resolution rule is the delegate's: the longest matching
prefix wins.

    hython tools/mtlx_coverage.py [--list]

Without arguments it gives the figures; with `--list`, the list of categories
without a match.
"""

import os
import re
import sys

import MaterialX as mx

from mtlx_rules import Resolver, load_library, prefixes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "external", "cycles-53", "src", "hydra", "material.cpp")

# The four arithmetic families are not in the table: the lookup picks the
# scalar or vector node from the nodedef's suffix.
INLINE = ("ND_add_", "ND_subtract_", "ND_multiply_", "ND_divide_")

# What does not need translating: materials, lights, organizational nodes, and
# the color space conversions that OpenColorIO does upstream of the graph.
NOT_SHADING = re.compile(
    r"^(cycles_|Lama|Usd|surfacematerial|volumematerial|displacementmaterial|surface$|"
    r"volume$|light$|point_light|spot_light|directional_light|"
    r"arrayappend|osl_set_ci|.*_to_lin_rec709$|standard_surface_to_|open_pbr_surface_to_)"
)

PREFIX_RE = re.compile(r'\{"(ND_[A-Za-z0-9_]*)"')


def prefixes():
    text = open(SOURCE, encoding="utf-8", errors="replace").read()
    return sorted(set(PREFIX_RE.findall(text)), key=len, reverse=True)


def main():
    doc = load_library()
    resolver = Resolver(doc)
    resolves = resolver.resolves

    categories = {}
    for nodedef in doc.getNodeDefs():
        categories.setdefault(nodedef.getNodeString(), []).append(nodedef.getName())

    shading = {c: n for c, n in categories.items() if not NOT_SHADING.match(c)}
    covered = {c: n for c, n in shading.items() if all(resolves(d) for d in n)}
    partial = {c: n for c, n in shading.items()
               if c not in covered and any(resolves(d) for d in n)}
    missing = {c: n for c, n in shading.items() if c not in covered and c not in partial}

    defs_total = sum(len(n) for n in shading.values())
    defs_hit = sum(1 for n in shading.values() for d in n if resolves(d))

    print("MaterialX library      : %d categories, %d nodedefs"
          % (len(categories), sum(len(n) for n in categories.values())))
    print("of which to translate  : %d categories, %d nodedefs" % (len(shading), defs_total))
    print("covered                : %d complete, %d partial, %d missing"
          % (len(covered), len(partial), len(missing)))
    print("nodedefs               : %d/%d (%.0f %%)"
          % (defs_hit, defs_total, 100.0 * defs_hit / max(defs_total, 1)))
    by_how = {}
    for n in shading.values():
        for d in n:
            how = resolver.how(d)
            if how:
                by_how[how] = by_how.get(how, 0) + 1
    print("of which               : " + ", ".join("%d %s" % (c, h) for h, c in sorted(by_how.items())))

    if "--list" in sys.argv:
        for title, group in (("PARTIAL", partial), ("MISSING", missing)):
            if not group:
                continue
            print("\n%s (%d) :" % (title, len(group)))
            for name in sorted(group):
                print("   %-28s %d nodedefs" % (name, len(group[name])))


if __name__ == "__main__":
    main()
