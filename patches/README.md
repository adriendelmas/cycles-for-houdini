# Correctifs apportes a Cycles

Cycles n'est pas recopie ici : il a son propre depot, et nos modifications y
vivent sur une branche a nous, en commits separes par sujet. Cette serie en est
l'export par `git format-patch`.

    patches/5.2/   38 correctifs, base 3b97e190 (branche release/5.2)
    patches/5.3/   53 correctifs, base 8424ed53 (branche main)

`tools/bootstrap.py` fait le chemin complet -- clone, `git am`, compilation.
A la main, sur un clone deja pose :

    cd external/cycles-53 && git am ../../patches/5.3/*.patch

Regenerer la serie apres une nouvelle modification :

    cd external/cycles-53 && git format-patch --no-signature -o ../../patches/5.3 8424ed53..HEAD

Les deux series different peu. Le passage a la 5.3 a rejoue 37 correctifs sur
38 : `hydra: never leave a Shader without a graph` n'a plus lieu d'etre, l'amont
ayant resolu le probleme de son cote. S'y ajoutent la dispersion, reprise de la
PR Blender 162041, et le retrait des sauvegardes d'HDA du suivi. **La
numerotation a donc glisse d'un cran** a partir du cinquieme : les notes plus
bas suivent celle de la 5.2.

La plupart de ces correctifs sont independants d'Houdini et de cette machine --
**autant de candidats a une contribution amont chez Blender**.

## Serie 5.3

| | |
|---|---|
| `0001` | cmake: add missing USD libraries for the Houdini build |
| `0002` | hydra: accept Houdini AOV naming conventions |
| `0003` | hydra: apply constant primvars to every instance |
| `0004` | hydra: publish Cycles shader nodes to the USD shader registry |
| `0005` | hydra: translate MaterialX networks to Cycles nodes |
| `0006` | hydra: give unbound volumes the default volume shader |
| `0007` | hydra: register the renderer with Houdini and warn on unknown integrator settings |
| `0008` | hydra: do not build an unusable GL context for the display driver |
| `0009` | hydra: motion blur for animated object transforms |
| `0010` | hydra: fix host crash from unbalanced display driver locking |
| `0011` | hydra: create the shared GL context before draw() can return early |
| `0012` | hydra: fix GL teardown crash, and stop using the display driver by default |
| `0013` | hydra: restart the render on scene edits, and translate more MaterialX nodes |
| `0014` | hydra: take the scene lock rather than trying it, and add a GPU renderer entry |
| `0015` | hydra: OptiX kernel install path, and Houdini render property definitions |
| `0016` | hydra: tag a light's object for update, and keep unresolvable asset paths |
| `0017` | hydra: material edits never reached the device, and displacement was bump-only |
| `0018` | hydra: read Houdini op: texture paths by cooking the COP during sync |
| `0019` | hydra: read Copernicus COP pixels live rather than through an output node |
| `0020` | hydra: build proper RGBA when writing a Copernicus COP layer |
| `0021` | hydra: read MaterialX data image variants without an sRGB decode |
| `0022` | hydra: translate the bulk of the MaterialX node library |
| `0023` | hydra: translate MaterialX separate node output names |
| `0024` | hydra: composite mappings, plus the transform and ramp nodes |
| `0025` | kernel/scene: MaterialX-exact procedural noise nodes |
| `0026` | hydra: spread a scalar across a vector socket |
| `0027` | hydra: translate MaterialX noise onto the MaterialX noise node |
| `0028` | hydra: eleven more MaterialX families, and a general composite mechanism |
| `0029` | hydra: MaterialX position is in object space |
| `0030` | hydra: standard_surface specular weight, and image wrapping |
| `0031` | hydra: a colour landing on a scalar socket, and several helpers per mapping |
| `0032` | hydra: MaterialX displacement has no midlevel |
| `0033` | hydra: do not write a parameter that carries no value |
| `0034` | hydra: shade a mesh flat unless its normals say otherwise, and refresh the UsdPreviewSurface names |
| `0035` | hydra: an empty string default crashed the Sdr parser |
| `0036` | interface des noeuds: connecteurs, selecteurs de fichier, cases a cocher |
| `0037` | cases a cocher, section Base, et un fil ignore ne l'est plus en silence |
| `0038` | dispersion sur le principled bsdf, reprise de la PR blender 162041 |
| `0039` | otls: ne plus suivre les sauvegardes automatiques d'Houdini |
| `0040` | hydra: une rampe d'Houdini remplit enfin la table que Cycles attend |
| `0041` | hydra: flou de deformation pour les points animes |
| `0042` | le Cycles Material Builder n'etait dans aucun depot |
| `0043` | hydra: flou par velocite, pour la geometrie dont le nombre de points varie |
| `0044` | hydra: les normales par coin, au lieu de facetter ce qui ne l'est pas |
| `0045` | hydra: rejeter une valeur d'enum hors registre plutot que de la transmettre telle quelle |
| `0046` | kernel: Random Walk (Legacy) manquait dans la table de saut des fermetures |
| `0047` | hydra: un seul terminal a trois entrees, plutot que trois connecteurs qui se contredisent |
| `0048` | hydra: la dispersion du MaterialX standard_surface, vers le principled bsdf qui la porte enfin |
| `0049` | hydra: presenter Cycles GPU avant Cycles CPU dans le menu des moteurs |
| `0050` | hydra: rendre le display driver et le choix du peripherique utilisables |
| `0051` | hydra: choisir le peripherique de rendu depuis le menu d'Houdini |
| `0052` | hydra: les terminaux dont la sortie ne s'appelle pas BSDF n'etaient jamais branches |
| `0053` | hydra: les reglages du materiau, dans un noeud plutot que nulle part |

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

## 0012 — Créer le contexte GL partagé avant les sorties anticipées de draw()

`draw()` renonce dans trois cas — binding d'AOV d'affichage absent, dimensions
qui ne correspondent pas, render buffer inutilisé — et `gl_context_create()`
était placé **après** les trois. Or le thread de rendu Cycles appelle
`update_begin()` dès le démarrage de la session : tant qu'un `draw()` n'était
pas allé jusqu'au bout, aucun contexte n'existait et chaque frame signalait
`PathTraceDisplay implementation could not begin update`.

`draw()` s'exécute sur le thread où l'hôte rend son contexte GL courant, seul
endroit où un contexte partageable peut être construit. Le faire depuis le
constructeur du display driver **ne fonctionne pas** : le render pass n'est pas
nécessairement construit sur ce thread — vérifié en pratique, l'erreur
persistait.

Sans le patch 0011, cette erreur menait au crash. Avec lui, elle n'était plus
que du bruit ; ce patch supprime le bruit.

## 0013 — Crash à la destruction, et display driver désactivé par défaut

Le destructeur appelait `glDeleteBuffers()` **sans contexte GL courant**. Il
s'exécute sur le thread où l'hôte détruit le delegate — changer de renderer
dans le viewport, par exemple — qui n'a pas de contexte à lui : l'appel partait
dans le vide et emportait l'application. `gl_context_dispose()` avait le même
défaut, en tentant de détruire un contexte potentiellement encore courant.

Correctif : rendre notre contexte courant le temps des suppressions, et le
délier avant destruction.

**Et le display driver est désormais désactivé par défaut.** Partager le
contexte GL de l'hôte pour blitter les tuiles dans une texture a produit
**quatre défauts distincts** dans le viewport d'Houdini :

1. verrouillage déséquilibré → crash (0011)
2. contexte créé trop tard → erreur à chaque frame (0012)
3. pixels erronés — le viewport affichait quelque chose ressemblant à une passe
   de profondeur plutôt qu'à la beauty
4. appels GL sans contexte à la destruction → crash (celui-ci)

Le chemin par l'output driver est celui qu'emploie déjà tout rendu batch, et il
est correct sur l'ensemble de la batterie de tests. Un rafraîchissement moins
efficace vaut mieux qu'un viewport qui affiche faux et qui tombe.

`CYCLES_DISPLAY_DRIVER=1` permet de le réactiver pour qui veut y travailler.
