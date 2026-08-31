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

## Phase 5 — Curves, points, volumes ✅

![phase 5](milestone-phase5.png)

Validé sur `tests/usd/phase5.usda` :

- **BasisCurves** — 60 courbes cubiques bspline, largeurs dégressives par
  vertex, rendues comme des cheveux natifs Cycles.
- **Points** — 900 points, largeurs variables.
- **Volume OpenVDB** — le `cloud.vdb` livré avec Houdini, chargé via un prim
  `OpenVDBAsset`, avec auto-ombrage et ombre portée.

Le volume ne s'affichait pas au premier essai. Les logs montraient pourtant la
texture NanoVDB allouée (3,45 Mo) — mais aussi `Use Volume False` et
`0 volume octree(s)`. Cause : un volume sans matériau recevait le shader de
surface par défaut. Corrigé par le patch 0007.

## Phase 6 — AOVs ✅ / motion blur ⚠️

### AOVs : validés

`tests/usd/phase6_aov.usda` produit quatre RenderProducts distincts, tous
corrects et non triviaux :

| AOV | Canaux | Contrôle |
|---|---|---|
| `C` (color) | 4 (RGBA) | max 11,86 — le cube émissif |
| `Pz` (depth) | 1 | max 1e10 sur le fond, la profondeur « infinie » standard |
| `N` (normal) | 3 | valeurs bornées à ±1, normales normalisées |
| `primId` | 1 | max 4 pour 5 prims, identifiants 0..4 |

Les alias de nommage Houdini (`C`, `Pz`, `N`) passent par le patch 0002.

### Motion blur d'objet : absent

![motion blur](gap-motionblur.png)

Voir l'anomalie A7 ci-dessous.

## Phase 9 — Réglages de rendu et packaging ✅

### Réglages exposés

Le delegate accepte, depuis un prim `RenderSettings` USD :

| Clé | Effet |
|---|---|
| `cycles:samples` | nombre d'échantillons |
| `cycles:device` | CPU / CUDA / OPTIX… |
| `cycles:threads` | threads CPU |
| `cycles:time_limit` | limite de temps |
| `cycles:sample_offset` | décalage d'échantillons |
| `cycles:integrator:<socket>` | **tout** socket de l'intégrateur |

Vérifié : `cycles:samples = 24` rend bien 24 échantillons contre 1024 par
défaut ; `cycles:integrator:max_bounce` à 0 contre 12 change la luminance
moyenne comme attendu (perte de l'illumination indirecte).

⚠️ Les noms de sockets sont ceux de Cycles, pas ceux de l'UI Blender :
c'est **`max_bounce`** au singulier, pas `max_bounces`. Un nom erroné était
ignoré sans un mot — le patch 0008 ajoute un avertissement.

La liste complète des sockets disponibles se lit dans
`external/cycles/src/scene/integrator.cpp`.

### Packaging

`install/houdini/` contient désormais :

- `packages/cycles.json` — package Houdini (généré par le build amont)
- `UsdRenderers.json` — label de menu et défauts husk (patch 0008)
- `dso/usd/hdCycles.dll` + `dso/usd_plugins/hdCycles/` — le delegate et son manifeste

Installation : copier `install/houdini/packages/cycles.json` dans
`%USERPROFILE%/Documents/houdini22.0/packages/`.

**Reste à vérifier par toi** : l'effet de `UsdRenderers.json` sur le menu de
renderers de Solaris ne se constate que dans l'interface.

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

### A7 — Motion blur d'objet ✅ RÉSOLU (patch 0010)

![motion blur](milestone-motionblur.png)

Résolu. Détail dans `patches/README.md`. Ce qui suit décrit l'état initial.

<details>
<summary>Diagnostic d'origine</summary>


Seule la **caméra** a du motion blur : `camera.cpp` échantillonne sa transform
sur l'obturateur et appelle `cam->set_motion()`. Pour la géométrie,
`geometry.inl` ne lit qu'un seul échantillon :

    _geomTransform = matrixDs->GetTypedValue(0.0f);

Vérifié sur `tests/usd/phase6_mblur.usda` : un cube animé de x=-2,5 à x=+2,5
sur l'obturateur est rendu **parfaitement net** par Cycles, à sa position
d'ouverture, là où Karma l'étale sur toute sa trajectoire.

Ce qu'il faut pour le corriger, et pourquoi ce n'est pas un petit patch :

1. Faire remonter l'intervalle d'obturateur de la caméra jusqu'à la
   synchronisation des rprim — ni `HdCyclesSession` ni `HdCyclesCamera` ne
   l'exposent aujourd'hui.
2. Gérer l'ordre de synchronisation : rien ne garantit que la caméra soit
   synchronisée avant la géométrie, donc l'application du flou doit être
   différée ou rejouée.
3. Poser `Object::set_motion()`, `Geometry::set_use_motion_blur()` et
   `set_motion_steps()` de façon cohérente.
4. Le flou de déformation (points animés sur mesh et courbes) est un chantier
   distinct de celui du flou de transformation.

Un flou subtilement faux serait pire que pas de flou du tout, donc cette
fonctionnalité mérite son propre créneau plutôt qu'un ajout en fin de phase.

</details>

### A8 — Flou de déformation et attributs de vélocité

Le patch 0010 couvre le flou de **transformation** d'objet. Restent à faire :

- le flou de **déformation** : points animés sur mesh et courbes, via les
  attributs de motion Cycles (`ATTR_STD_MOTION_VERTEX_POSITION`) ;
- le flou par **attributs `velocities` / `accelerations`**, comme le fait Karma.
  Cycles n'a pas de notion native de vélocité : il faut synthétiser les
  positions aux étapes de motion (`P + v·dt`, plus `½·a·dt²` si l'accélération
  est présente) et remplir l'attribut de motion.

C'est en réalité le chemin le plus **simple** des deux, puisqu'il ne demande
aucun échantillon temporel supplémentaire au scene delegate : la vélocité
arrive comme un primvar ordinaire à un seul instant. C'est aussi le plus utile
en pratique, les simulations Houdini transportant `v` presque toujours.

### A9 — Crash du viewport Solaris ✅ CAUSE TROUVÉE (patch 0011)

Verrouillage déséquilibré dans le display driver : `gl_context_disable()`
déverrouillait `mutex_` même quand `gl_context_enable()` avait échoué **sans
l'avoir verrouillé**. Déverrouiller un mutex non possédé est un comportement
indéfini, et fait tomber Houdini.

Ce chemin n'est atteint que quand le contexte GL manque — donc exactement quand
le driver signale `could not begin update`. Le message d'erreur et le segfault
étaient **le même défaut**, pas deux.

Ma première tentative (patch 0009) durcissait la création du contexte : utile,
mais elle traitait la cause de l'erreur, pas celle du crash. Le crash a
persisté, ce qui a permis de chercher au bon endroit.

Détail dans `patches/README.md`. **Reste à confirmer en interface.**

Le message `could not begin update` qui l'accompagnait est traité séparément
par le patch 0012 : le contexte GL n'était créé qu'après les sorties anticipées
de `draw()`.

### Piège d'installation

Windows verrouille `hdCycles.dll` tant qu'Houdini tourne. L'étape `install`
échoue alors avec un `Permission denied` **noyé dans une erreur MSB3073
générique**, et l'ancienne DLL reste en place — on teste donc sans le savoir
une version périmée.

Toujours vérifier l'horodatage après installation :

    ls -la install/houdini/dso/usd/hdCycles.dll

### A10 — Display driver GPU inutilisable dans le viewport Houdini

Quatre défauts distincts trouvés dans `display_driver.cpp`, tous corrigés
(patchs 0009, 0011, 0012, 0013), mais le blit lui-même produisait encore des
pixels erronés — un rendu ressemblant à une passe de profondeur.

**Décision : désactivé par défaut** (patch 0013). Le rendu interactif passe par
l'output driver, le même chemin que tout rendu batch, correct sur l'ensemble de
la batterie. Réactivable par `CYCLES_DISPLAY_DRIVER=1`.

Reste à comprendre, pour qui voudra le réactiver : pourquoi le contenu blitté
est incorrect. Piste — `GetDefaultAovDescriptor` force `HdFormatFloat16Vec4`
quand le display driver est actif, et le driver l'exige
(`TF_VERIFY(renderBuffer->GetFormat() == HdFormatFloat16Vec4)`) ; une
inadéquation de format avec ce qu'attend le viewport d'Houdini expliquerait
l'aspect « profondeur ».

## GPU (phase 8) — partiellement livré

**Cycles GPU** est une entrée de menu distincte de **Cycles CPU**, et rend sur
la RTX 3090 via CUDA. Sortie vérifiée **identique au pixel près** au rendu CPU.

Trois obstacles levés :

1. `nvcc fatal : Cannot find compiler 'cl.exe' in PATH` — Cycles compilait les
   kernels à l'exécution, ce qui exige nvcc *et* le compilateur hôte MSVC dans
   le PATH. Résolu en précompilant les kernels (`WITH_CYCLES_CUDA_BINARIES=ON`,
   `CYCLES_CUDA_BINARIES_ARCH=sm_86`).
2. Activer les binaires CUDA activait aussi la cible OptiX, qui échouait faute
   de SDK. Il faut `-DWITH_CYCLES_DEVICE_OPTIX=OFF`.
3. Les kernels s'installaient dans `install/lib`, hors de la racine Houdini sur
   laquelle le delegate enracine Cycles — donc jamais trouvés à l'exécution.

### OptiX

**Le SDK etait installe depuis le debut**, sous
`C:/ProgramData/NVIDIA Corporation/OptiX SDK 9.1.0`. CMake ne fouille pas
`ProgramData` : il ne manquait qu'un `-DOPTIX_ROOT_DIR`. Version 9.1.0 acceptee
(minimum requis 8.0.0). Rien a mettre a jour.

A propos de `Hardware Ray-Tracing: Off` affiche meme sous OptiX :
`use_hardware_raytracing` n'est renseigne que par le device **HIP** (AMD
RDNA2+, ou HIP-RT est optionnel). Le device OptiX ne le met jamais a vrai,
parce que l'acceleration materielle y est **intrinseque a l'API**. Le message
est cosmetique, pas un symptome.

### Mesures

Temps de rendu pur (hors demarrage du process), 1280x640, 1024 samples fixes,
echantillonnage adaptatif desactive, sur `phase5.usda` :

| Device | Temps | Rapport |
|---|---|---|
| CPU - Threadripper 3995WX, 128 threads | 29,8 s | reference |
| CUDA - RTX 3090 | 12,1 s | **2,5x** |
| OptiX - RTX 3090 | 12,0 s | 2,5x |

Sorties identiques sur les trois devices.

OptiX n'apporte rien **sur cette scene-la**, et c'est attendu : elle est
dominee par un volume et des courbes, or les coeurs RT accelerent
l'intersection rayon-triangle. L'ecart apparaitrait sur de la geometrie
polygonale dense.

Piege de mesure : au chronometre du process, sur une scene legere, OptiX
ressortait *plus lent* (5,7 s contre 4,5 s) - uniquement a cause de son surcout
d'initialisation, chargement des modules PTX et construction des structures
d'acceleration. Il faut mesurer le rendu seul.

## Noeud de reglages de rendu (livre)

Les reglages Cycles apparaissent dans l'onglet du **Render Settings LOP**, au
meme endroit que ceux de Karma - pas dans un noeud separe. Houdini peuple cet
onglet depuis `$HOUDINI_PATH/soho/parameters/<Renderer>_Global.ds`.

**59 proprietes en 9 onglets** : Session, Sampling, Light Paths, Volumes,
Caustics, Denoising, Guiding, Ambient Occlusion, Advanced.

Le fichier est **genere** depuis les declarations `SOCKET_*` de
`integrator.cpp` par `tools/gen_render_properties.py`, pas tenu a la main : a
relancer apres une mise a jour de Cycles pour que les nouveaux reglages
apparaissent d'eux-memes.

Les noms de parametres sont encodes par `hou.text.encode()`, dont j'ai verifie
qu'elle reproduit exactement l'encodage punycode d'Houdini
(`karma:global:imagemode` -> `xn__karmaglobalimagemode_m8ag`), plutot que de
reimplementer cette transformation a l'aveugle.

Chaque propriete porte son parm de controle set/block/none, donc rien n'est
ecrit dans l'USD tant que l'utilisateur n'y touche pas.


Ligne de configuration :

    cmake -B build -DHOUDINI_ROOT=... -DWITH_CYCLES_HYDRA_RENDER_DELEGATE=ON       -DWITH_CYCLES_CUDA_BINARIES=ON -DCYCLES_CUDA_BINARIES_ARCH=sm_86       -DWITH_CYCLES_DEVICE_OPTIX=OFF

## Textures COP en `op:` (livre, cote Houdini)

Houdini permet de pointer une texture directement sur un COP :
`op:/img/net/OUT`. Ses propres renderers evaluent ca via sa bibliotheque
d'imagerie ; un delegate tiers, lui, ne voit qu'une chaine qu'il ne sait pas
ouvrir.

**Ce qui a ete ecarte, et pourquoi.** Le resolveur d'assets d'Houdini accepte
le chemin et rend un `ArAsset` - mais de **taille 0**, avec `GetBuffer()` a
`None`. Un `op:` n'est pas un flux d'octets. J'avais commence a concevoir un
`ImageLoader` Cycles lisant via `ArAsset` : ce test a deux lignes a evite
d'ecrire le chargeur pour rien.

**Ce qui a ete ecarte aussi.** Lier `libIMG` d'Houdini dans le delegate et
appeler `IMG_File::open("op:...")`. Plausible - le delegate tourne dans le
process d'Houdini - mais invérifiable sans ecrire un programme HDK, et surtout
ca lierait un composant Cycles amont a l'ABI d'Houdini, qui casse a chaque
version.

**Ce qui est livre.** `tools/flatten_op_textures.py` : une pre-passe qui
parcourt le stage, cuit chaque COP reference vers un fichier image et reecrit
les chemins. A poser dans un Python LOP avant le noeud de rendu :

    import flatten_op_textures
    flatten_op_textures.run(hou.pwd())

La reecriture se fait sur la couche du LOP, donc la scene d'origine est
intacte et retirer le noeud restaure les `op:`.

Verifie de bout en bout : COP -> aplatissement -> EXR de 35 Ko -> materiau
MaterialX `ND_image_color3` -> `image_texture` Cycles -> rendu correct.

**Limite : ce n'est pas live.** Le COP est aplati au moment ou le LOP cuit ;
le modifier ensuite ne se repercute pas dans un IPR en cours sans recuire ce
noeud.

Corrige au passage : `node_util.cpp` faisait `GetResolvedPath()` sans repli, la
ou les volumes et les lumieres retombent sur `GetAssetPath()`. Toute texture non
resolue devenait une chaine vide - donc absente en silence, sans indication du
chemin fautif.

## Mises a jour de materiaux et displacement

### Les editions de materiau ne repassaient jamais

`Shader::set_graph()` **ne marque pas le shader comme modifie**. Or `Sync`
faisait :

    else { PopulateShaderGraph(network); }      // pas de tag_modified
    ...
    if (_shader->is_modified()) { _shader->tag_update(lock.scene); }

Le graphe reconstruit laissait donc `is_modified()` faux, `tag_update()`
n'etait jamais appele, le shader manager jamais notifie, et la scene ne se
declarait pas a mettre a jour. Un materiau s'affichait correctement au premier
rendu puis ignorait toute modification.

La branche voisine, celle qui ne met a jour que les parametres, appelait bien
`tag_modified()` : **l'asymetrie etait le bug**.

### Displacement

![displacement](milestone-displacement.png)

Deux manques cumules :

1. Le delegate ne posait **jamais** `displacement_method`. Il restait sur le
   defaut de Cycles, `DISPLACE_BUMP` - donc un terminal de displacement
   branche ne faisait que perturber les normales, et `set_graph()` ne calculait
   meme pas le hash de displacement.
2. Les noeuds `ND_displacement_float` / `_vector3` de MaterialX n'avaient pas
   d'equivalent mappe, alors que Cycles a `displacement` et
   `vector_displacement`.

Corrige : la methode passe a `DISPLACE_BOTH` quand le reseau pilote
effectivement un displacement, et les deux noeuds MaterialX sont mappes.

### Fichier de proprietes de rendu

Deux avertissements dans la console d'Houdini venaient de mon fichier genere :

- `Warning(830): Too many defaults specified` - deux sockets ont pour defaut une
  constante C++ (`MAX_SAMPLES`, un `|` de drapeaux) que la regex capturait
  verbatim. On n'emet plus de bloc `default` quand il n'est pas numerique,
  plutot que d'inventer une valeur.
- `Duplicate folder name (global` - le groupe s'appelait `global`, comme celui
  de Karma. Renomme en `cycles_global`.

### Textures COP

L'erreur `Image file op:/... does not exist` est desormais **visible** grace au
repli sur le chemin authore : avant, le chemin devenait une chaine vide et la
texture disparaissait sans un mot. Pour que ces textures fonctionnent, utiliser
`tools/flatten_op_textures.py`.
