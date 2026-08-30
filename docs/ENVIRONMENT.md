# Environnement de build — hdCycles pour Houdini

Relevé effectué le 2026-08-30 sur la machine de dev.

## Cible

| Composant | Version | Chemin |
|---|---|---|
| Houdini | 22.0.368 | `E:\Side Effects Software\Houdini22.0.368` |
| USD (pxr) | 26.05 | `$HFS/toolkit/include/pxr` |
| MaterialX | 1.39.5 | bundled Houdini |
| oneTBB | 2022.1 (iface 12150) | bundled Houdini |
| OpenImageIO | 2.5.18 | bundled Houdini |
| OpenVDB | 13.0.0 | bundled Houdini |
| Python | 3.10 / 3.11 / 3.13 | `$HFS/python3xx` |

Note : OSL n'est pas exposé dans le toolkit Houdini (Karma passe par
MaterialX/VEX). Cycles embarquera donc son propre OSL, ou on construit
d'abord sans OSL — le backend SVM suffit.

## Toolchain

| Outil | Version | Chemin |
|---|---|---|
| MSVC | 14.44.35207 (VS2022 BuildTools) | `D:\VS\BuildTools` |
| Windows SDK | 10.0.22621.0 | |
| CMake | 4.4.0 | |
| CUDA | 12.9 | |
| GPU | RTX 3090 (driver 591.86) | |
| git-lfs | 3.7.1 | |

Manquants pour la phase GPU : **OptiX SDK** (à télécharger chez NVIDIA), **Ninja** (optionnel).

Attention : CMake 4.x refuse `cmake_minimum_required(VERSION < 3.5)`. Prévoir
une CMake 3.3x de secours si une dépendance ancienne bloque.

## Source

- Cycles `release/5.2`, commit `3b97e190` (2026-07-13), clone treeless dans `external/cycles`.
- Libs précompilées Blender : `lib/windows_x64` (submodule + git-lfs).

## Ce qui existe déjà en amont

`external/cycles/src/hydra/` est un render delegate Hydra complet **avec support
Houdini officiel** (`FindUSDHoudini.cmake`, `HOUDINI_ROOT`, install vers
`houdini/dso/usd_plugins`, génération du package `cycles.json`).
Couvre : mesh, curves, pointcloud, volume, instancer, lights, caméra,
render passes, display driver (IPR).

Côté shading il consomme déjà les identifiants `cycles_*` / `cycles:`
(`src/hydra/material.cpp:442`) et mappe `UsdPreviewSurface`.

## Ce qu'il reste à écrire (notre valeur ajoutée)

1. **`src/sdrCycles`** — plugin Sdr (discovery + parser) publiant les nœuds
   Cycles dans le registre USD, généré depuis `NodeType::type_names()`.
   Modèle de référence : `$HFS/houdini/dso/usd_plugins/sdrKarmaDiscovery`.
2. **`src/mtlxCycles`** — traduction MaterialX -> graphe de nœuds Cycles.
   Absent en amont. Module isolé, supprimable si Cycles absorbe MaterialX.
3. Validation et correctifs contre Houdini 22 / USD 26.05 (l'amont vise 21).
