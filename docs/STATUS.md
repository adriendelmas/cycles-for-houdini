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

## Textures COP en `op:` - integre au delegate

Un chemin de texture peut nommer un noeud de compositing plutot qu'un fichier.
C'est desormais gere **dans hdCycles**, sans noeud a poser et sans rien
installer ailleurs dans Houdini.

### Ce qui a ete mesure avant de coder

Deux voies ont ete fermees par l'experience, pas par principe :

1. **Lire via le resolveur USD.** `ArAsset` pour un `op:` a une taille de 0 et
   `GetBuffer()` rend `None`. Ce n'est pas un flux d'octets.
2. **Lire via la couche image d'Houdini.** `hou.imageResolution` et
   `hou.loadImageDataFromFile` fonctionnent sur un vrai fichier (1920x1080,
   8,3 M de valeurs) et **echouent toutes les deux** sur un `op:`. Aucune API
   de lecture d'image d'Houdini n'expose les pixels d'un COP, quel que soit ce
   qu'on accepte de lier.

Seule la **cuisson du noeud** produit des pixels.

### Ou la cuisson a lieu, et pourquoi la

Pendant la **synchronisation du prim**, pas pendant le chargement de l'image.
Le chargement tourne sur les threads de travail de Cycles, et cuire un noeud
Houdini depuis l'un d'eux ferait tomber l'application - un crash de la meme
famille que ceux corriges plus haut, mais dependant du minutage.

Le delegate remplace donc le `op:` par le fichier cuit avant que Cycles ne voie
quoi que ce soit : **le chargeur natif reste inchange pour les chemins
ordinaires**, exactement le partage demande.

Resultats caches par chemin. Le suffixe de plan (`OUT_COLOR[1]`) est retire
pour retrouver le noeud, mais conserve dans la cle de cache pour que deux plans
d'un meme noeud ne se telescopent pas.

### Limites

- **Pas live.** Le COP est cuit quand le materiau se synchronise ; le modifier
  ensuite ne se repercute qu'a la prochaine synchronisation de ce materiau.
- **Rendu batch.** `husk` n'a pas de module `hou` et pas de session : l'appel
  est protege et sort un avertissement nommant le chemin fautif, sans lever ni
  planter. Pour une ferme de rendu, il faut aplatir en amont - c'est a ca que
  sert `tools/flatten_op_textures.py`, conserve pour cet usage.

## Copernicus : ce qu'il a fallu corriger, et les erreurs de methode

Trois passes ont ete necessaires, chacune parce que j'avais valide une partie
de la chaine en croyant l'avoir validee entiere.

### 1. Le mauvais systeme de compositing

Tous mes tests initiaux portaient sur `/img/...`, c'est-a-dire **COP2**. J'en ai
conclu qu'aucune API Houdini ne donne les pixels d'un COP - une conclusion
generale tiree d'un systeme qui n'etait pas celui utilise. Les noeuds
**Copernicus** (categorie `Cop`, dans un `copnet`) n'ont pas `saveImage`, qui
est une API COP2.

### 2. Un noeud de sortie inutile

Deuxieme correction : passer par un `rop_image`. Ca marchait, mais ca ajoutait
un noeud a la scene de l'utilisateur - alors que Karma lit un COP reference sans
rien poser du tout. `CopNode.layer()` donne un `hou.ImageLayer` avec un acces
**direct** aux pixels : `bufferResolution()` et `allBufferElements()`.

### 3. Les canaux

`hou.saveImageDataToFile` prend une sequence de flottants et n'accepte **que du
RGBA**. Elle rejette franchement un buffer a trois canaux :

    the color+alpha data sequence must contain width*height*4 elements

Mais un buffer a **un seul canal** passe : son nombre d'octets
(`w * h * 1 * 4`) egale par coincidence le nombre d'elements attendu
(`w * h * 4`). La fonction ecrit alors **chaque octet comme une valeur**. Un
noise en niveaux de gris ressortait en jaune sature et blanc crame - ce n'etait
pas l'image, c'etait sa representation binaire relue de travers.

Correction : construire explicitement les quatre canaux. Un canal replique en
RGB, trois canaux passes tels quels, alpha rempli de 1.

Le buffer est **entrelace**, verifie en lisant un `constant` a valeurs
distinctes par canal : `0.9, 0.2, 0.4, 0.9, 0.2, 0.4, ...`

### La lecon de methode

A chaque fois, le defaut etait de verifier qu'un fichier **apparaissait** plutot
que ce qu'il **contenait**. La verification qui a finalement tenu :

    source 0.35, un canal
    -> EXR : 0.350000 0.350000 0.350000 1.000000

Le script Python que le C++ assemble est aussi verifie a la compilation : une
erreur de syntaxe ne serait pas rattrapee par le `try` qu'il contient, puisque
celui-ci est a l'interieur.

### A11 — `position` MaterialX est en espace objet ✅ CORRIGÉ

`ND_position_vector3` a une entrée `space` qui vaut `object` par défaut. Elle
est traduite vers la sortie `Position` du nœud `geometry` de Cycles, qui est en
espace **monde**. Les deux coïncident pour un objet à l'origine et divergent
dès qu'il est déplacé.

Constaté en testant `clamp`/`remap` sur un objet translaté en x ≈ −3,2 : les
bornes attendues entre −1 et 1 tombaient hors plage et la sphère sortait noire.
Le graphe était pourtant correctement câblé — vérifié via `HD_CYCLES_DUMP_GRAPH`.

Sans effet sur les bruits procéduraux, qui ne dépendent pas de l'origine, mais
fausse tout ce qui compare une position à un seuil.

**Corrigé** en lisant la sortie `Object` du nœud `texture_coordinate` au lieu de
`geometry.Position`. Vérifié contre Karma sur le même USD, matériau purement
émissif pour ne pas dépendre de l'éclairage : les deux moteurs s'accordent à
0,002 près (bruit d'échantillonnage), contre une composante rouge négative
auparavant.

**Non corrigé, et volontairement :** `normal`, `tangent` et `bitangent`
déclarent le même défaut `space = "object"` et sortent du nœud `geometry`, en
espace monde. Pour une translation pure les deux coïncident ; seule une rotation
de l'objet les sépare. À traiter avec un `vector_transform` monde → objet le
jour où ça se voit.

**Écart mesuré mais non corrigé :** sur mes maillages de test, la normale rendue
par Cycles vaut exactement l'opposé de celle de Karma. La cause n'est pas une
convention d'axes mais l'enroulement de mes quads, dont la normale géométrique
pointe vers l'intérieur : Karma la rapporte telle quelle, Cycles la retourne
vers le rayon. Sur une géométrie correctement enroulée il n'y a pas d'écart.


### A12 — `specular` de standard_surface doublait le spéculaire ✅ CORRIGÉ

`specular` est un **poids** MaterialX dont la valeur neutre est 1. Il était
envoyé tel quel sur `specular_ior_level` de Cycles, dont le neutre est **0,5**.
Tout matériau où Houdini écrit ce paramètre — c'est-à-dire à peu près tous —
rendait donc un spéculaire deux fois trop fort.

Mesuré contre Karma, pic de la tache spéculaire sur une sphère :

| `specular`     | Karma | Cycles avant | Cycles après |
|----------------|-------|--------------|--------------|
| non renseigné  | 0,894 | 0,894        | 0,894        |
| = 1 (défaut)   | 0,894 | **1,372**    | 0,894        |
| = 0,5          | 0,629 | 0,894        | 0,658        |

Corrigé par un nœud `math` auxiliaire qui divise le poids par deux. Il porte
aussi le défaut MaterialX de 1, sans quoi un `specular` non écrit se retrouvait
piloté vers une valeur fausse au lieu de rester au défaut de Cycles — c'est ce
qu'une première version faisait, attrapé par le cas « non renseigné ».

L'écart résiduel à 0,5 tient à ce que le poids MaterialX est linéaire là où le
niveau de Cycles suit une courbe d'IOR : la direction et le neutre sont justes,
la courbe intermédiaire reste approchée.

### A13 — `base` et `default` d'image restent non honorés

`base` de standard_surface est un poids multipliant `base_color` ; il faudrait
un second nœud auxiliaire, or le mécanisme n'en gère qu'un par correspondance et
celui de `standard_surface` sert désormais au `specular`.

`default` du nœud image (la couleur rendue hors de l'image en mode `constant`)
n'a pas d'équivalent : Cycles ne sait renvoyer que du noir. La correspondance
qui l'envoyait vers `color` a été retirée — `color` est une **sortie** de
`image_texture`, la correspondance ne pouvait qu'échouer.

### A14 — `opacity` rendait tout matériau transparent ✅ CORRIGÉ

`opacity` est un `color3` MaterialX ; l'`alpha` de Cycles sur lequel il atterrit
est un flottant. USD ne définit aucun cast d'un `GfVec3f` vers un `float`, donc
la conversion tombait dans son avertissement et renvoyait **0**.

Conséquence : tout matériau écrivant une opacité — **blanche comprise**, ce que
les builders de matériaux de Houdini écrivent par défaut — devenait **totalement
transparent**. C'est très probablement ce qui se lisait comme « la transmission
rend comme de l'alpha, ça baisse juste l'opacité » : ce n'était pas la
transmission, c'était l'opacité qui annulait l'objet.

Vérifié : `opacity = (1,1,1)` rend désormais **exactement** comme une opacité non
renseignée (diff `PASS`), contre une sphère quasi invisible auparavant.

Corrigé dans `convertToCycles<float>`, qui réduit maintenant une couleur ou un
vecteur à la moyenne de ses composantes au lieu de renvoyer zéro. La correction
est générale : elle protège tout socket scalaire nourri par une couleur, pas
seulement `alpha`.

### A15 — normale et displacement : vérifiés fonctionnels

Signalés comme cassés, mais mesurés fonctionnels sur un réseau MaterialX USD
écrit à la main :

- **normalmap** : le relief est présent et son motif correspond à celui de
  Karma. Testé en `ND_image_color3` et `ND_image_vector3`, en EXR et en PNG 8
  bits — les deux variantes donnent la même image à 4·10⁻⁹ près, donc pas de
  décodage sRGB parasite.
- **displacement** : déformation géométrique réelle, silhouette identique à
  celle de Karma sur la même scène.

Deux causes restent plausibles côté utilisateur, dans cet ordre :

1. **La DLL n'est pas rechargée.** Houdini verrouille `hdCycles.dll` tant qu'il
   tourne ; l'installation échoue alors en `Permission denied` enfoui dans la
   sortie de MSBuild. Il faut fermer Houdini, réinstaller, puis rouvrir.
2. Une structure de réseau que je n'ai pas pu reproduire : le Karma Material
   Builder n'est pas instanciable en ligne de commande dans cette installation
   (ce n'est pas un type de nœud mais un outil d'étagère), et le
   `materialbuilder` VEX exporte ses terminaux sous le contexte `vex` et non
   `mtlx`. Pour trancher il faut l'USD exporté du matériau qui échoue.
