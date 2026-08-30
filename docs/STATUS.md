# État d'avancement

## Phase 0 — Build ✅

Cycles 5.2 (`3b97e190`) compile et s'installe contre **Houdini 22.0.368 / USD 26.05**.

- Configuration CMake : aucune erreur, aucun conflit TBB/OIIO/OpenVDB.
- Un correctif nécessaire : `patches/0001-FindUSDHoudini-add-hdsi.patch`.
- Sortie : `install/houdini/dso/usd/hdCycles.dll` (10 Mo) + `plugInfo.json`
  + package `cycles.json`.

Lancement :

    $env:PXR_PLUGINPATH_NAME = "<projet>/install/houdini/dso/usd_plugins"

`husk --list-renderers` affiche alors `HdCyclesPlugin (Cycles)`, **non marqué
"unsupported"**.

## Phase 1 — Delegate enregistré ✅

## Phase 2 — Première image ✅

![premier rendu](milestone-first-render.png)

Rendu par : `husk --renderer HdCyclesPlugin --camera /world/camera --res 480 270
--output geo.exr geo_only.usda`

Validé : mesh polygonaux, transforms, DomeLight (couleur + intensité),
displayColor, ombres de contact, path tracing sur 128 threads
(Threadripper 3995WX), échantillonnage adaptatif.

## Phase 3 — Lumières, instancing, subdivision ✅

![phase 3](milestone-phase3.png)

Validé sur `tests/usd/phase3.usda` :

- **Subdivision Catmull-Clark** — le cube de gauche est rendu comme une sphère
  lisse, le cube central (`subdivisionScheme = "none"`) reste dur.
- **PointInstancer** — les 5 instances sont rendues, avec la couleur du
  prototype (après correctif 0003).
- **RectLight, DiskLight, SphereLight** — les trois contribuent, avec leurs
  couleurs et leurs ombres douces respectives.
- **displayColor** par objet.

Méthode : chaque résultat est contre-vérifié en rendant la même scène avec
Karma. C'est ce qui a permis de distinguer un vrai bug du delegate (0003) d'une
scène de test mal écrite.

## Phase 4a — Nœuds Cycles natifs dans USD ✅

![phase 4a](milestone-phase4-sdr.png)

**161 nœuds Cycles** sont publiés dans le registre Sdr d'USD (patch 0004), avec
leurs types, valeurs par défaut et options d'enum lues du registre Cycles.

L'image ci-dessus est rendue depuis des matériaux authorés **en nœuds Cycles
natifs** dans un fichier USD : `cycles_principled_bsdf` en or métallique
(`metallic=1`, `roughness=0.12`) et en verre (`transmission_weight=1`,
`ior=1.45`).

Prérequis découvert : les meshes doivent porter le schéma appliqué
`MaterialBindingAPI`. Sans lui, `rel material:binding` est silencieusement
ignoré et la géométrie retombe sur `default_surface` — le rendu est correct
mais sans aucun matériau, ce qui est trompeur.

## Phase 4b — Traduction MaterialX ✅

![phase 4b](milestone-phase4b-materialx.png)

Les trois objets ci-dessus sont rendus depuis des matériaux **MaterialX**
`ND_standard_surface_surfaceshader` : métal (`metalness=1`,
`specular_roughness=0.14`), verre (`transmission=1`, `specular_IOR=1.45`) et
émission (`emission=2.5`).

Implémenté dans le patch 0006, en réutilisant la machinerie de mapping déjà
présente pour `UsdPreviewSurface` plutôt qu'en créant une seconde. Les noms de
sockets Cycles ont été relevés depuis le registre Sdr construit en phase 4a —
pas devinés.

La couche est volontairement un bloc auto-contenu dans `material.cpp` :
supprimable d'une pièce le jour où Cycles absorbera MaterialX, comme prévu au
départ. `src/mtlxCycles` n'a donc pas lieu d'être, la greffe sur l'existant
étant plus courte et plus cohérente.

Couvert : `standard_surface`, `image`, `normalmap`, `texcoord`. Les entrées
MaterialX sans équivalent Cycles (`base`, `transmission_color`,
`subsurface_color`, `transmission_extra_roughness`) sont délibérément non
mappées et ignorées — c'est documenté dans le code.

## Anomalies ouvertes

### A1 — Surfaces implicites non supportées (confirmé)

`kSupportedRPrimTypes` (`src/hydra/render_delegate.cpp:40`) ne liste que
`basisCurves`, `mesh`, `points`, `volume`. Un prim `Sphere` USD est
silencieusement absent du rendu ; un `Mesh` explicite au même endroit
s'affiche correctement.

Impact réel modéré (la géométrie venant des SOPs arrive en mesh), mais toute
scène USD tierce contenant Sphere/Cube/Cylinder/Cone/Capsule perdra ces prims
sans avertissement.

Piste : s'assurer que `UsdImagingImplicitSurfaceSceneIndex` est bien inséré
dans la pipeline husk d'Houdini 22, sinon déclarer les types et mailler
nous-mêmes.

### A2 — RenderVar Houdini → image noire ✅ RÉSOLU (patch 0002)

husk transmet `driver:parameters:aov:husk:name` comme nom d'AOV Hydra. La
convention Houdini pour la beauty étant `"C"`, le binding n'était pas mappé,
la liste de bindings restait vide, `IsConverged()` retournait vrai
immédiatement et husk écrivait une frame vierge — **sans le moindre
avertissement**.

Diagnostic obtenu par bissection : RenderSettings seuls → OK ; ajout du
RenderProduct + RenderVar → noir ; `husk:name = "color"` → OK.

### A3 — displayColor perdu sur les instances ✅ RÉSOLU (patch 0003)

Index `_instances[0]` codé en dur. Voir `patches/README.md`.

### A4 — Matériau à émission seule : invisible à la caméra

Un `Material` dont le terminal `outputs:cycles:surface` est connecté
directement à un nœud `cycles_emission` **émet bien de la lumière** (la lueur
colorée est visible sur les surfaces alentour) mais l'objet lui-même est
**totalement invisible aux rayons caméra**.

La même émission passée par les entrées `emission_color` / `emission_strength`
d'un `cycles_principled_bsdf` rend un objet lumineux visible, normalement.

Le défaut est donc spécifique au nœud `emission` employé seul comme terminal de
surface, et non à l'émission en général. Cause racine non déterminée — piste :
la construction du graphe côté `material.cpp`, la fermeture d'émission étant
visiblement prise en compte par l'arbre de lumières mais pas raccordée à la
sortie de surface.

Reproduction : `tests/usd/emit_test.usda` (invisible) contre
`tests/usd/pemit_test.usda` (correct).

### A5 — Crash sur matériau MaterialX ✅ RÉSOLU (patch 0005)

La simple présence d'un matériau MaterialX dans le stage provoquait un
segmentation fault, lié ou non à une géométrie. Karma rendait le même fichier
sans problème.

Cause racine : `Shader::tag_update()` déréférence `graph` sans vérification,
et un matériau dont la network est illisible n'atteint jamais `set_graph()`.
Corrigé en semant un graphe vide à la création du shader.

Localisé par instrumentation progressive (`fprintf` sur stderr — `TF_WARN` est
avalé par husk), en bissectant jusqu'à l'instruction.

Reproduction : `tests/usd/repro_mtlx_crash.usda`, 80 lignes.

Suite livrée en phase 4b : `mtlx` est désormais déclaré comme contexte de
rendu et les réseaux MaterialX sont traduits (patch 0006).


## Organisation des correctifs

Les modifications de Cycles vivent sur la branche `houdini-fixes` du clone, en
commits séparés par sujet, exportés dans `patches/` par `git format-patch`.
Réapplication après un pull amont : `git am ../../patches/*.patch`.

## Non-régression

Batterie rejouée après chaque build, toutes en exit 0 :

| Scène | Couvre |
|---|---|
| `phase4b_mtlx.usda` | MaterialX standard_surface (métal, verre, émission) |
| `phase4_materials.usda` | nœuds Cycles natifs via Sdr |
| `phase3.usda` | lumières, PointInstancer, subdivision |
| `repro_mtlx_crash.usda` | non-régression du crash A5 |

Méthode retenue tout du long : **contre-vérifier chaque résultat en rendant la
même scène avec Karma**. C'est ce qui a permis de distinguer les vrais bugs du
delegate de mes propres scènes de test mal écrites — et de rattraper au moins
une conclusion erronée.
