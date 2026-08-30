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
