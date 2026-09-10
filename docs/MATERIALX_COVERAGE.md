# MaterialX — ce qui est traduit, ce qui ne l'est pas

Mesuré le 2026-09-09 avec `hython tools/mtlx_coverage.py --list`, contre la
bibliothèque MaterialX 1.39.5 livrée avec Houdini 22.0.368.

| | |
|---|---|
| bibliothèque | 245 catégories, 898 nodedefs |
| dont à traduire | 205 catégories, 823 nodedefs |
| **couvert** | **136 catégories, 652 nodedefs — 79 %** |

Les 40 catégories écartées du dénominateur ne sont pas des nœuds de shading :
les matériaux et les lumières, que Hydra transmet par ses propres primitives,
les nœuds Lama et UsdPreviewSurface qui ont leur propre chemin, et les
conversions d'espace colorimétrique, qu'OpenColorIO fait en amont du graphe.

Le compte se refait tout seul : le script relit la table de correspondances
dans `material.cpp` et applique la règle du delegate — le préfixe le plus long
qui colle l'emporte.

## Ce qui a été ajouté le 2026-09-09

De 549 à 647 nodedefs. Deux corrections et six familles.

**Deux entrées ne pouvaient rien attraper.** `and` et `or` étaient inscrits
sous `ND_and_` et `ND_or_` ; MaterialX les nomme `ND_logical_and` et
`ND_logical_or`. Aucun graphe n'a jamais pu les atteindre. `not` s'y ajoute.

**Le passe-plat manquait.** MaterialX pose un `dot` pour router un fil et un
`convert` pour changer de type — deux choses que Cycles fait sur le lien
lui-même. Sans correspondance, la chaîne se coupait là : un graphe venu d'un
autre logiciel, où l'un et l'autre abondent, y perdait ses textures. Un mélange
à facteur nul rend son entrée telle quelle ; sur une fermeture, où un mélange
de couleurs détruirait tout, c'est une somme à un seul terme.

| catégorie | nœud Cycles | vérifié |
|---|---|---|
| `dot` | `mix_color` (fac 0) | (0,9 0,2 0,1) → (0,9 0,2 0,1) |
| `convert` | idem | float 0,7 → (0,7 0,7 0,7) |
| `constant` | `value` ou `color` selon le type | (0,1 0,8 0,3) → identique |
| `saturate` | `hsv` | (0,9 0,2 0,1) à 0,2 → (0,900 0,760 0,740) |
| `contrast` | `math`/`vector_math` en multiplication accumulée | ×2 pivot 0,5 → (1,3 −0,1 −0,3) |
| `hextiledimage` | `mx_hextiled_image_texture` | moyenne 0,500, celle du fichier |
| `gltf_image`, `gltf_colorimage` | `image_texture` | idem |
| `logical_and/or/not` | `math` | 1 − 0 = 1 |

Un cas de `convert` n'est pas un passe-plat : `convert_<type>_surfaceshader`
fait une surface qui **émet** la couleur donnée. Traité comme les autres, il
laissait le terminal sans fermeture — signalé (`Cycles node 'mix_color' has no
output 'BSDF'`), mais perdu. Il devient un nœud `emission`. Le suffixe ne se
lisant pas par préfixe, ce cas-là est traité dans la recherche elle-même.

Trois pièges rencontrés en chemin, tous mesurés :

* `contrast` sur une **couleur** passait d'abord par le nœud `math`, qui est
  scalaire : la couleur y était réduite à sa moyenne et ressortait grise. Il en
  faut deux versions, scalaire et vectorielle, comme pour les quatre familles
  arithmétiques.
* `length` a été inscrit puis retiré : ce nom n'existe pas dans MaterialX 1.39,
  c'est `magnitude`. Un préfixe qui n'attrape rien est exactement le défaut
  qu'on venait de corriger sur `and` et `or`.

`ND_hextiledimage_` mérite une note : le nœud Cycles correspondant vient de la
**PR Blender 158054** de Ben Houston, déjà intégrée ici pour les bruits
MaterialX. Il existait donc dans le moteur sans que rien ne l'atteigne depuis
un réseau MaterialX.

## Ce qui manque, et pourquoi

**Impossible en l'état — Cycles n'a pas de type matrice** (11 nodedefs) :
`creatematrix`, `determinant`, `invertmatrix`, `transformmatrix`, `transpose`.

**Impossible — Cycles n'a pas de canal alpha sur une couleur** :
`premult`, `unpremult`, `disjointover`, `over`, `in`, `out`, `mask`, `matte`.

**Impossible — pas de notion de temps dans le graphe** : `time`, `frame`.

**Demande un mécanisme qu'on n'a pas encore** — une sortie choisie par la
valeur d'un paramètre, ou une entrée variadique :

| | |
|---|---|
| `switch` (16 nodedefs) | dix entrées, une sélection par index |
| `swizzle` (35 nodedefs) | déprécié en 1.39, remplacé par `extract`/`combine` |
| `extract` (7) | la sortie dépend de l'index demandé |
| `ramp4`, `splitlr`, `splittb` (18) | rampes et coupures à quatre coins |

**Faisable, pas encore fait** — par ordre d'utilité décroissante :

| | |
|---|---|
| `colorcorrect`, `hsvadjust`, `curveadjust` | réglages colorimétriques |
| `triplanarprojection` (6) | Cycles projette en boîte, mais sur **une** image |
| `hmtlx*` (10) | les nœuds MaterialX propres à Houdini : damier, cercles, biais, gain, ratio de face |
| `huniformramp`, `hcatmullrom`, `huniformcubic`, `ramp` | les rampes de Houdini |
| `circle`, `grid`, `line`, `hexagon`, `cloverleaf`, `crosshatch`, `tiled*` | les motifs procéduraux 2D |
| `blur` (6) | un flou de voisinage, que Cycles ne sait pas faire sur un graphe |
| `gltf_normalmap`, `gltf_anisotropy_image`, `gltf_iridescence_thickness` | le reste de la famille glTF |
| `artistic_ior`, `open_pbr_anisotropy`, `roughness_anisotropy`, `roughness_dual`, `glossiness_anisotropy` | conversions de paramètres |
| `generalized_schlick_bsdf`, `thin_film_bsdf`, `thin_surface`, `surface_unlit`, `gooch_shade`, `disney_*` | des fermetures sans équivalent direct |

**Un nœud sans correspondance est annoncé**, pas ignoré : le delegate écrit
`MaterialX: no Cycles node for '<nodedef>'` dans le journal, par le logger de
Cycles et non par `TF_WARN`, qu'husk avale.

## Le banc

`tools/bench_mtlx.py` rend un matériau par nœud testé et vérifie la valeur qui
en sort, pas seulement que l'image ne soit pas noire — c'est ce qui a attrapé
le `contrast` gris.

## Les cheveux, ajoutés le 2026-09-10

`chiang_hair_bsdf`, `chiang_hair_roughness`, `chiang_hair_absorption_from_color`,
`deon_hair_absorption_from_melanin`, et `surface` qui en fait un shader. Exacts,
comparés au principled hair natif de Cycles par `tools/bench_hair.py` — voir la
phase 33 de `STATUS.md`. Seules les teintes par lobe (`tint_R`, `tint_TT`,
`tint_TRT`) restent sans équivalent chez Cycles.
