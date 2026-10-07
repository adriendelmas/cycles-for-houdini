"""Ce que la traduction MaterialX couvre, et ce qu'elle laisse de cote.

Le denominateur est la bibliotheque MaterialX livree avec Houdini, lue par
MaterialX lui-meme ; le numerateur, la table de correspondances du delegate,
relue dans `material.cpp`. La regle de resolution est celle du delegate : le
prefixe le plus long qui colle l'emporte.

    hython tools/mtlx_coverage.py [--list]

Sans argument il rend les chiffres ; avec `--list`, la liste des categories
sans correspondance.
"""

import os
import re
import sys

import MaterialX as mx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "external", "cycles-53", "src", "hydra", "material.cpp")

# Les quatre familles arithmetiques ne sont pas dans la table : la recherche
# choisit le noeud scalaire ou vectoriel d'apres le suffixe du nodedef.
INLINE = ("ND_add_", "ND_subtract_", "ND_multiply_", "ND_divide_")

# Ce qui n'a pas a etre traduit : des materiaux, des lumieres, des noeuds
# d'organisation, et les conversions d'espace colorimetrique qu'OpenColorIO
# fait en amont du graphe.
NOT_SHADING = re.compile(
    r"^(Lama|Usd|surfacematerial|volumematerial|displacementmaterial|surface$|"
    r"volume$|light$|point_light|spot_light|directional_light|"
    r"arrayappend|osl_set_ci|.*_to_lin_rec709$|standard_surface_to_|open_pbr_surface_to_)"
)

PREFIX_RE = re.compile(r'\{"(ND_[A-Za-z0-9_]*)"')


def prefixes():
    text = open(SOURCE, encoding="utf-8", errors="replace").read()
    return sorted(set(PREFIX_RE.findall(text)), key=len, reverse=True)


def main():
    known = prefixes()

    def resolves(nodedef):
        if nodedef.startswith(INLINE):
            return True
        return any(nodedef.startswith(p) for p in known)

    doc = mx.createDocument()
    mx.loadLibraries(["libraries"], mx.getDefaultDataSearchPath(), doc)

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

    print("bibliotheque MaterialX : %d categories, %d nodedefs"
          % (len(categories), sum(len(n) for n in categories.values())))
    print("dont a traduire        : %d categories, %d nodedefs" % (len(shading), defs_total))
    print("couvertes              : %d completes, %d partielles, %d absentes"
          % (len(covered), len(partial), len(missing)))
    print("nodedefs               : %d/%d (%.0f %%)"
          % (defs_hit, defs_total, 100.0 * defs_hit / max(defs_total, 1)))

    if "--list" in sys.argv:
        for title, group in (("PARTIELLES", partial), ("ABSENTES", missing)):
            if not group:
                continue
            print("\n%s (%d) :" % (title, len(group)))
            for name in sorted(group):
                print("   %-28s %d nodedefs" % (name, len(group[name])))


if __name__ == "__main__":
    main()
