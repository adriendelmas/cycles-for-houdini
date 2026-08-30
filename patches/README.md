# Patches appliqués à `external/cycles`

Le clone Cycles est gitignoré (il a son propre dépôt), donc nos modifications
sont conservées ici sous forme de patchs, à réappliquer après un `git pull`
amont :

    cd external/cycles && git apply ../../patches/*.patch

## 0001 — FindUSDHoudini : ajouter `hdsi`

`src/hydra/file_reader.cpp` référence
`HdSiExtComputationPrimvarPruningSceneIndex::New`, qui vit dans la librairie
USD `hdsi`. `FindUSDHoudini.cmake` ne listait pas `hdsi` dans `USD_LIBRARIES`,
d'où un `LNK2019` au link de `cycles.exe` (l'app standalone) — et donc un échec
de la cible `install`, alors même que `hdCycles.dll` se construisait bien.

Houdini 22 fournit pourtant `libpxr_hdsi.lib` dans `custom/houdini/dsolib/`.
Correctif : ajouter `hdsi` à la liste.

**Candidat à une contribution amont** — le bug touche toute build Houdini, pas
seulement la 22.

## 0002 — Hydra : accepter les noms d'AOV Houdini

husk transmet la valeur de `driver:parameters:aov:husk:name` d'un `UsdRenderVar`
comme **nom d'AOV Hydra**, au lieu d'un token `HdAovTokens` standard. La
convention Houdini pour la beauty étant `"C"`, un RenderVar authoré normalement
dans Solaris arrive non mappé dans `kAovToPass` (`src/hydra/session.cpp`).

Le binding est alors ignoré, ce qui laisse le render pass **sans aucun binding** —
et `HdCyclesRenderPass::IsConverged()` itérant sur une liste vide retourne `true`
immédiatement. husk écrit donc une frame vierge : **image noire, sans erreur ni
avertissement**.

Correctif : ajouter les orthographes Houdini comme alias (`C`, `Cf`, `N`, `P`,
`Pz`).

**Candidat à une contribution amont** — sans ça, hdCycles est inutilisable avec
des render settings Houdini standards, ce qui est le cas d'usage principal.

## 0003 — Hydra : primvar constant perdu sur les instances

`mesh.cpp`, `curves.cpp` et `pointcloud.cpp` appliquaient un `displayColor`
d'interpolation *constant* avec un index codé en dur :

    _instances[0]->set_color(...);

Un primvar constant décrit le prim entier, donc toutes ses instances. Avec un
`PointInstancer`, seule la première instance recevait la couleur du prototype ;
toutes les autres retombaient sur la couleur par défaut du shader.

Vérifié : sur une scène à 5 instances, hdCycles en colorait 1 et laissait 4
blanches, là où Karma les rend correctement toutes les 5. Après correctif, les
deux moteurs concordent.

**Candidat à une contribution amont.**
