# Correctifs apportés à Cycles

Le clone Cycles (`external/cycles`) est gitignoré ici — il a son propre dépôt.
Nos modifications y vivent sur la branche **`houdini-fixes`**, en commits
séparés par sujet, et sont exportées ici par `git format-patch`.

Réappliquer après un pull amont :

    cd external/cycles && git am ../../patches/*.patch

Régénérer les patchs après une nouvelle modification :

    cd external/cycles && git format-patch -o ../../patches 3b97e190..HEAD

Base amont : `3b97e190` (branche `release/5.2`).

Les huit sont indépendants d'Houdini 22 et de cette machine — **tous sont des
candidats à une contribution amont chez Blender**.

---

## 0001 — cmake : librairies USD manquantes pour le build Houdini

`FindUSDHoudini.cmake` ne listait pas `hdsi`, dont `src/hydra/file_reader.cpp` a
besoin pour `HdSiExtComputationPrimvarPruningSceneIndex`. Résultat : `LNK2019`
au link de l'exécutable standalone, et donc échec de la cible `install` — alors
même que `hdCycles.dll` se construisait correctement. `sdr` est requis par le
plugin de registre de nœuds (0005). Houdini fournit les deux.

## 0002 — hydra : accepter les conventions de nommage d'AOV d'Houdini

husk transmet le `driver:parameters:aov:husk:name` d'un `UsdRenderVar` comme
**nom d'AOV Hydra**, et non un token `HdAovTokens` standard. Houdini nomme la
beauty `"C"` : un render var authoré normalement dans Solaris arrivait donc non
mappé, son binding était écarté, et le render pass se retrouvait **sans aucun
binding**. Or `IsConverged()` itère sur cette liste — vide, elle retourne vrai
immédiatement, et husk écrivait une frame vierge.

Symptôme : **image noire, sans erreur ni avertissement**, pour toute scène
Solaris normalement configurée.

## 0003 — hydra : appliquer les primvars constants à toutes les instances

Un `displayColor` d'interpolation constante décrit le prim entier, donc toutes
ses instances. L'index `_instances[0]` était codé en dur : avec un
`PointInstancer`, seule la première instance recevait la couleur du prototype,
les autres retombaient sur la couleur par défaut du shader.

## 0004 — hydra : ne jamais laisser un Shader sans graphe

**Crash de l'application hôte.** `Shader::tag_update()` lit `graph->output()`
sans vérification, mais `HdCyclesMaterial` n'assigne un graphe qu'une fois une
network de matériau lue avec succès. Un matériau dont la network est illisible
par le delegate — un matériau MaterialX, par exemple — partait dans la branche
d'erreur, et le shader fraîchement créé atteignait `tag_update()` avec un
`graph` nul.

Conséquence : la simple présence d'un tel matériau dans le stage faisait
segfaulter husk, que le matériau soit lié à une géométrie ou non.

## 0005 — hydra : publier les nœuds Cycles dans le registre de shaders USD

Couple discovery + parser Sdr qui énumère `NodeType::type_names()` **au
runtime** et publie chaque nœud `SHADER` sous l'identifiant `cycles_<nom>` —
celui que la traduction de matériaux du delegate accepte déjà. Lire le registre
au runtime plutôt que générer des définitions à l'avance garantit que le jeu de
nœuds exposé suit exactement la version de Cycles liée.

Enregistré dans la DLL `hdCycles` existante pour ne pas dupliquer les libs
statiques Cycles ni leur registre de nœuds dans le process.

Piège : un résultat de découverte publié avec un `SdrVersion()` vide est
parsable par identifiant mais **absent de l'énumération** du registre. Il faut
`SdrVersion(1, 0).GetAsDefault()`.

## 0006 — hydra : traduire les réseaux MaterialX en nœuds Cycles

Déclare `mtlx` comme contexte de rendu de matériau et remappe les identifiants
de nodedef MaterialX vers des nœuds Cycles natifs, via la même machinerie que
`UsdPreviewSurface`. Couvre `standard_surface`, `image`, `normalmap` et
`texcoord`. Les noms de sockets ont été vérifiés contre le registre de nœuds
Cycles, pas devinés.

Volontairement écrit en **un seul bloc auto-contenu**, supprimable d'une pièce
le jour où Cycles comprendra MaterialX nativement.

## 0007 — hydra : donner aux volumes non liés le shader volumétrique par défaut

Une géométrie sans matériau retombait sur `scene->default_surface` quel que
soit son type. Or un `Volume` a besoin d'un shader portant une fermeture
volumétrique : un volume non lié voyait sa grille **correctement chargée** — la
texture NanoVDB est allouée et apparaît dans les statistiques mémoire — mais
n'avait rien pour y diffuser, et rendait comme s'il n'existait pas.

Symptôme trompeur : tout indique que le VDB est lu, et pourtant l'image est
vide à cet endroit.

Correctif : choisir `default_volume` pour une géométrie de type `Volume`.

## 0008 — hydra : enregistrer le renderer auprès d'Houdini

Ajoute un `UsdRenderers.json` (label de menu, purpose par défaut, valeurs par
défaut de husk), installé à côté du package `cycles.json` déjà généré. Houdini
fusionne ce fichier le long du `HOUDINI_PATH`, que le package pointe sur
l'installation.

Ajoute aussi un avertissement quand un réglage `cycles:integrator:<socket>`
nomme un socket inexistant. L'ignorer en silence est un piège : un nom mal
orthographié est indiscernable d'un réglage sans effet. À noter, husk avale les
`TF_WARN` — l'avertissement remonte dans Solaris, pas en rendu batch.
