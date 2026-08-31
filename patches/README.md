# Correctifs apportés à Cycles

Le clone Cycles (`external/cycles`) est gitignoré ici — il a son propre dépôt.
Nos modifications y vivent sur la branche **`houdini-fixes`**, en commits
séparés par sujet, et sont exportées ici par `git format-patch`.

Réappliquer après un pull amont :

    cd external/cycles && git am ../../patches/*.patch

Régénérer les patchs après une nouvelle modification :

    cd external/cycles && git format-patch -o ../../patches 3b97e190..HEAD

Base amont : `3b97e190` (branche `release/5.2`).

Les onze sont indépendants d'Houdini 22 et de cette machine — **tous sont des
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

## 0009 — hydra : ne pas fabriquer un contexte GL inutilisable

`gl_context_create()` lit deux fois le contexte GL courant du thread appelant :
via `wglGetCurrentDC()` pour le format de pixel, et pour `wglShareLists()`.
Sans contexte courant, il produisait un contexte ni correctement formaté ni
partagé avec celui de l'hôte, qui échouait à la première utilisation.

Symptôme observé dans le viewport Solaris :
`PathTraceDisplay implementation could not begin update`, suivi d'un crash.

Correctif : renoncer s'il n'y a pas de contexte courant, et détruire le
contexte si le partage échoue — `gl_context_enable()` signale alors proprement
l'échec.

Ajoute aussi un réglage d'environnement **`CYCLES_DISPLAY_DRIVER=0`** pour
désactiver complètement le display driver. Les hôtes diffèrent sur le moment et
le thread où un contexte GL est courant ; le rendu passe alors par l'output
driver, plus lent à rafraîchir mais sans aucune exigence GL.

## 0010 — hydra : motion blur des transforms d'objet animées

Seule la caméra était échantillonnée sur l'obturateur ; la géométrie lisait une
transform unique au temps zéro, donc tout ce qui bougeait rendait net.

Trois points à ne pas rater :

1. **L'obturateur est lu depuis les réglages de rendu**, pas depuis le prim
   caméra — ça évite de dépendre de l'ordre de synchronisation entre sprims et
   rprims, qui n'est pas garanti.
2. **Les échantillons doivent être régulièrement espacés.** `Object::motion_time()`
   répartit les étapes linéairement sur [-1, 1] ; utiliser les temps
   d'échantillonnage que remonte USD, qui sont irréguliers, flouterait le long
   d'une trajectoire déformée.
3. **`Integrator::motion_blur` doit être activé.** `Scene::need_motion()` ne
   renvoie `MOTION_BLUR` que dans ce cas — sans lui, les transforms de motion
   sont posées mais purement ignorées.

La transform statique est prise sur l'échantillon médian pour que le flou soit
centré sur l'obturateur.

Limite connue : c'est le flou de **transformation**. Le flou de déformation
(points animés, ou attributs `velocities` / `accelerations` façon Karma) reste
à faire — voir A8.

## 0011 — Crash de l'hôte : verrouillage déséquilibré du display driver

**C'est la cause du crash observé dans le viewport Solaris.**

`gl_context_enable()` verrouille `mutex_` quand il réussit, mais retourne
`false` **sans le verrouiller** quand aucun contexte GL utilisable n'existe.
Deux appelants ignoraient cette valeur de retour — `flush()` et
`graphics_interop_activate()` — et `gl_context_disable()` faisait
`mutex_.unlock()` inconditionnellement.

Déverrouiller un mutex que le thread ne possède pas est un **comportement
indéfini**, et fait tomber l'application.

Le point clé du diagnostic : ce chemin n'est atteint que lorsque le contexte
manque, c'est-à-dire exactement quand le driver signale
`PathTraceDisplay implementation could not begin update`. Le message d'erreur
et le segfault qui le suivait n'étaient pas deux problèmes, mais **un seul**.

Correctif en trois points :

1. Suivre la possession du verrou pour que `gl_context_disable()` ne libère que
   ce qui a effectivement été pris — robuste quelle que soit la discipline des
   appelants.
2. `flush()` renonce au lieu d'émettre des appels GL sans contexte.
3. Créer le contexte partagé **dans le constructeur** plutôt qu'au premier
   `draw()` : `draw()` a plusieurs sorties anticipées, le thread de rendu
   pouvait donc atteindre `update_begin()` avant qu'aucun contexte n'existe.
