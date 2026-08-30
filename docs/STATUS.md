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

### A2 — Chemin RenderSettings/RenderVar explicite → image noire (non résolu)

Avec `--settings /rendersettings` et une RenderVar écrite à la main, le rendu
sort noir (et sur 1 canal au lieu de 3), alors que la **même scène** rendue via
les défauts de husk (`--camera` + `--res`, sans RenderSettings) sort correcte.

Les erreurs de validation husk successives ont été corrigées une à une
(`driver:parameters:aov:husk:name`, `:format` = `"float"`, `sourceType` en
`token`, schémas `KarmaRenderVarAPI`/`HuskRenderVarAPI`), jusqu'à ne plus avoir
d'erreur — mais l'image reste noire.

Karma rend la **même** scène en noir également, ce qui indique que la RenderVar
faite main reste non conforme, plutôt qu'un défaut de hdCycles.

Prochaine étape : générer les RenderSettings depuis Houdini (hython + LOP
`karmarenderproperties`) plutôt que de les écrire à la main, et rejouer.
