# Cycles 5.3 — installation parallèle

La 5.2 et la 5.3 cohabitent. Rien n'a été remplacé : la 5.2 est intacte,
arbre propre, installation en place. On passe de l'une à l'autre en changeant
**un mot** dans le package Houdini.

## Basculer

`C:\Users\Adrien\Documents\houdini22.0\packages\cycles.json`

```json
"CYCLES_BUILD": { "value": "install-53", "method": "replace" }
```

`install` pour la 5.2, `install-53` pour la 5.3. Puis relancer Houdini.

Le reste du package dérive de cette variable, donc il n'y a qu'un seul endroit
à toucher. La version 5.2 d'origine est sauvegardée en `cycles.json.bak-5.2`.

## Ce que la 5.3 apporte

**La dispersion.** Deux paramètres sur le principled, dans la section
Transmission comme dans Blender :

| socket | défaut |
|---|---|
| `transmission_dispersion_scale` | 0 |
| `transmission_dispersion_abbe_number` | 20 |

Elle ne s'active que si **les deux** sont non nuls : `PrincipledBsdfNode::has_dispersion()`
exige un poids de transmission et une échelle de dispersion tous deux positifs.
Un nombre d'Abbe **bas** disperse **fort** — c'est l'inverse de l'intuition, mais
c'est la définition du nombre d'Abbe en optique.

Vérifié au rendu (`tests/usd/disp/`) : à dispersion 0 les trois canaux sont
rigoureusement identiques ; à 1 ils se séparent, et l'écart croît du rouge vers
le bleu.

| | R | G | B |
|---|---|---|---|
| dispersion 0 — max | 9.109 | 9.109 | 9.109 |
| dispersion 1 — max | 7.832 | 7.168 | 3.348 |
| écart — moyenne | 0.00032 | 0.00041 | 0.00100 |

Les valeurs **négatives** dans l'image dispersée ne sont pas un défaut : le
rendu devient spectral, et une longueur d'onde pure tombe hors du gamut sRGB,
dont la matrice de conversion a des lobes négatifs.

## Comment elle a été fabriquée

Un `git worktree` sur la branche `houdini-fixes-53`, rebasée sur `origin/main`.

**37 des 38 commits rejoués.** Le patch 0004 a été abandonné : il empêchait un
plantage quand un `Shader` recevait un `tag_update` sans graphe, or l'amont ne
crée plus le Shader qu'au moment de lui donner son graphe. Le bug ne peut plus
exister.

La moitié du patch 0018 est morte de la même façon : `Shader::tag_update()`
appelle désormais `tag_modified()` lui-même. L'autre moitié — le displacement —
a été conservée mais **déplacée** dans `Sync`, derrière un membre
`_hasDisplacement`, parce que `BuildShaderGraph` s'exécute maintenant avant que
le Shader existe.

Sur deux conflits, les deux côtés ont été gardés plutôt qu'un choix :

* l'amont a ajouté un filtre `meets_driver_requirement` dans la sélection GPU —
  intégré à nos deux chemins de résolution automatique via un lambda `collect` ;
* l'amont distingue mieux deux cas dans un avertissement — distinction gardée,
  mais émise par `LOG_WARNING` et non `TF_WARN`, que husk avale.

La dispersion vient du PR Blender #162041. Sur ses 26 fichiers, 24 se sont
appliqués seuls ; les deux autres n'étaient que du décalage de lignes. La place
pour `SD_REQUIRES_WAVELENGTH` existe parce que l'amont a séparé
`ShaderDataFlag` de `ShaderRuntimeFlag`, ce qui a libéré des bits.

## Les bibliothèques précompilées

Elles sont téléchargées, non versionnées, et pèsent trop pour être dupliquées.
Sans elles la configuration échoue sur `Could NOT find PugiXML`. CMake les
cherche à un chemin **en dur**, `<source>/lib/windows_x64` — il n'existe aucune
variable pour les désigner ailleurs.

`external/cycles-53/lib/windows_x64` contient donc **57 jonctions**, une par
bibliothèque, vers celles de la 5.2.

Une jonction unique sur le dossier entier paraît plus simple, et c'est ce que
j'avais fait d'abord — mais `lib/windows_x64` est un **sous-module git**, et le
dossier de la 5.2 contient un fichier `.git` dont le `gitdir` est relatif. Vu à
travers la jonction, il pointait dans le vide et `git status` mourait sur
`not a git repository`. Descendre d'un niveau laisse ce fichier derrière.

## Les kernels GPU

Ils sont dans `install-53/houdini/lib/`, pas `install-53/lib/` — c'est un de nos
patchs qui les y met, parce que le delegate enracine Cycles dans l'arbre Houdini
et ne les trouverait pas ailleurs. Les `install/lib/*.zst` de la 5.2 sont des
reliquats d'un build antérieur à ce patch.

## Les fichiers côté Houdini

Trois fichiers ne sont pas produits par CMake et doivent exister dans **chaque**
installation :

* `houdini/otls/cycles_vops.hda` — **à régénérer** par installation, jamais à
  copier : elle dérive du registre Sdr publié par le delegate construit, dont
  les nœuds changent d'une version à l'autre (c'est ainsi que les deux sliders
  de dispersion apparaissent) ;
* `houdini/scripts/python/cycles_builder.py` et `houdini/toolbar/CyclesTools.shelf`
  — indépendants du moteur, copiés tels quels.

Les outils suivent la variable d'environnement `CYCLES_INSTALL_DIR` :

```bash
CYCLES_INSTALL_DIR=install-53 hython tools/build_cycles_vops.py
CYCLES_INSTALL_DIR=install-53 hython tools/bench_export.py
CYCLES_INSTALL_DIR=install-53 hython tools/bench_render.py
```

Les résultats du banc vont dans `tests/usd/bench-53/` pour ne pas écraser ceux
de la 5.2 et permettre la comparaison entre versions.
