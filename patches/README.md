# Correctifs apportes a Cycles

Cycles n'est pas recopie ici : il a son propre depot, et nos modifications y
vivent sur une branche a nous, en commits separes par sujet. Cette serie en est
l'export par `git format-patch`.

    patches/5.2/   38 correctifs, base 3b97e190 (branche release/5.2)
    patches/5.3/   80 correctifs, base 8424ed53 (branche main)

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
| `0025` | kernel/scene: MaterialX-exact procedural noise nodes — Cycles side of Blender PR #158054, by Ben Houston |
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
| `0054` | scene: le displacement s'ajoutait a lui-meme a chaque edition du materiau |
| `0055` | hydra: choisir l'espace colorimetrique d'une texture dans un menu |
| `0056` | hydra: aligner les lumieres sur Karma, et rendre les lumieres cylindriques |
| `0057` | hydra: la couleur de transmission et celle de sous-surface, enfin traduites |
| `0058` | hydra: une texture venue d'un COP sortait retournee |
| `0059` | hydra: les textures d'un COP passent par la memoire, plus par un fichier |
| `0060` | hydra: surveiller les COP, que personne ne signale comme changes |
| `0061` | hydra: un frein sur la veille des COP, et de quoi la couper |
| `0062` | hydra: une texture qui change, et une camera dont on sort |
| `0063` | hydra: la veille des COP repose l'image elle-meme |
| `0064` | hydra: une image branchee sur une entree scalaire, et la couleur de sous-surface retiree |
| `0065` | hydra: un lobe de transmission a lui, pour la couleur et la rugosite que MaterialX lui donne |
| `0066` | hydra: donner a Cycles la camera qui sert a decouper les subdivisions |
| `0067` | hydra: un shader d'apercu pour les materiaux Cycles, sinon le viewport reste gris |
| `0068` | hydra: le passe-plat MaterialX, deux entrees mortes, et six familles de plus |
| `0069` | hydra: ne plus retourner l'image d'un COP, les deux bouts la rangent deja pareil |
| `0070` | hydra: le taux de decoupage des subdivisions, dans les reglages de rendu |
| `0071` | hydra: de quoi mesurer un viewport qui traine, et un journal qui arrive quelque part |
| `0072` | hydra: une carte pleine qui se dit, et des COP qui ne pesent que leurs canaux |
| `0073` | hydra: les cheveux MaterialX, et le noeud surface qui coupait tout |
| `0074` | hydra: crediter Ben Houston a la tete de la traduction MaterialX |
| `0075` | hydra: les primvars float3 etaient copies au mauvais pas, et lus en vrac |
| `0076` | hydra: mix, les fondus, saturate, facingratio, viewdirection et geomcolor, exacts |
| `0077` | hydra: la declaration de ResolveUdimTiles manquait a la serie |
| `0078` | hydra: les fermetures MaterialX - mix, add, multiply, volume, layer, conductor |
| `0079` | hydra: les variantes couleur et vecteur des operateurs MaterialX, et trois operateurs scalaires faux |
| `0080` | hydra: OpenPBR, glTF et Disney traduits, les defauts de chaque surface, UsdUVTexture par canal, kma |
| `0081` | hydra: les courbes USD rendues ou USD les place, en tubes, et le reglage Curve Shape |
| `0082` | hydra: les instances floues, leurs primvars par instance, et les primvars constants scalaires |
| `0083` | hydra: les surfaces implicites USD rendues, en maillages fins |
| `0084` | hydra: un maillage Catmull-Clark subdivise sans attendre l'indice d'affichage |
| `0085` | hydra: huit cles par segment de courbe cubique, pour suivre la forme |
| `0086` | hydra: le flou qui revient, les champs de volume d'Houdini, et le film transparent |
| `0087` | hydra: les passes de rendu - lumieres, LPE de Karma, cryptomatte, AOV de shader |
| `0088` | hydra: les proprietes par objet - visibilite par rayon, holdout, shadow catcher |
| `0089` | hydra: le light linking et le shadow linking |
| `0090` | hydra: un prim dont le render tag n'est plus dessine disparait du rendu |
| `0091` | hydra: couper le flou de mouvement ne fait plus disparaitre les objets |
| `0092` | hydra: les light groups et leurs passes |
| `0093` | hydra: les multiplicateurs diffuse et specular des lumieres USD |
| `0094` | hydra: le manifeste de la cryptomatte dans les metadonnees de l'image |
| `0095` | hydra: l'emission combinee et les vecteurs de mouvement de Karma |
| `0096` | hydra: la passe ne bloque plus l'interface, et le cache des COP se vide |
| `0097` | hydra: commentaires et messages de journal en anglais |
| `0098` | hydra: les nodegraphs MaterialX deplies, extract et swizzle reecrits, vector2 converti |
| `0099` | hydra: les defauts MaterialX ecrits sur toute entree non ecrite |
| `0100` | hydra: le journal `CYCLES_LOG_FILE` horodate chaque ligne (secondes depuis la premiere) |
| `0101` | hydra: le lobe de verre de standard_surface choisi sur la transmission (cablee ou > 0), plus sur la presence de `transmission_color`, que 0099 ecrit partout |
| `0102` | hydra: les tailles des normales, des points et des largeurs verifiees avant lecture (K-57, plus de segfault sur un attribut illisible) |
| `0103` | hydra: rugosite des BSDF elementaires prise comme alpha (racine carree), dielectric_bsdf selon scatter_mode - R principled, T refraction, RT verre (K-58) |
| `0104` | hydra: nodegraphs livres par le delegue (artistic_ior, roughness_*, inside/outside), transformmatrix a matrice constante, generalized_schlick en F82, Disney legacy ; mix a facteur couleur, magnitude/distance/dotproduct corriges (K-59) |
| `0105` | hydra: thin_film_bsdf replie sur le BSDF de son layer, curveadjust en passe-plat, l'alpha d'une image lue par separate4/extract/swizzle (K-17) |
| `0106` | hydra: position, normale et tangente selon leur `space` - normale objet par defaut, position monde sur demande (K-18) |
| `0107` | hydra: absorption_vdf en coefficient (couleur = 1 - absorption), subsurface a l'echelle 1 et avec son anisotropie, AO par maxdistance (K-14) ; surface_unlit traduit (K-60) |
| `0108` | hydra: douze traductions corrigees par comparaison a Karma - rotate en degres, tangente UV, vector2 sans 3e composante, combine2 color4, comparaisons booleennes, burn/dodge sans bornes, ramp_gradient deplie (K-61) ; heighttonormal encode en espace tangent (K-12) ; emission a l'intensite 1, generalized_schlick_edf transmet sa base |
| `0109` | hydra: couleur de base des surfaces calculee avant traduction - sous-surface et assombrissement du vernis d'OpenPBR, sous-surface et gamma du vernis de standard_surface ; alpha glTF selon alpha_mode (K-63) ; tiledimage, images glTF, latlongimage et place2d depuis leurs nodegraphs, image_float sur son premier canal (K-64) |
| `0110` | hydra: UsdPreviewSurface selon useSpecularWorkflow (F0 = specularColor, ignore en workflow metallique) et opacityThreshold (detourage) (K-65) ; espace couleur des textures lu dans le champ Hydra et resolu dans la config OCIO active, images en `auto` par defaut, wrapS/wrapT traduits (K-66) |
| `0111` | hydra: texture du dome orientee selon la convention lat-long d'OpenEXR (pole +Y, longitude 0 vers +Z) et `poleAxis` de DomeLight_1 via `domeOffset` (K-67) |
| `0112` | hydra: texture des rect lights lue en (1 - u, v), coin min en (+X, +Y) comme le veut USD (K-68) ; douceur du cone des spots convertie de l'angle (USD) au cosinus (Cycles), cone de 90 degres par defaut, `shaping:focus` et `focusTint` dans le shader de la lumiere (K-69) |
| `0113` | hydra: profils IES lus selon la direction d'emission dans le repere de la lumiere, en candelas comme USD, `normalize` (moyenne du profil, `IESFile::mean_intensity`) et `angleScale` (K-70) |
| `0114` | hydra: exposition de la camera (echelle lineaire de Hydra) multipliee a celle des render settings sur le film (K-71) |
| `0115` | hydra + scene: tags de subdivision lus dans le conteneur du mesh (plis, coins), acuite USD / 10, coins sans plis, regles de bord et face-varying, trous non decoupes (`Mesh::subd_hole`), coins effaces par `Mesh::clear` (K-72) |
| `0116` | hydra: coordonnees de texture par sommet passees par coin (l'espace tangent mikktspace les lit par coin) - normal maps justes le long de v et sur des UV en miroir (K-73) |
| `0117` | hydra: largeur 1 par defaut (celle de Hydra) pour les points et courbes sans `widths` (K-74) ; `displacement` de UsdPreviewSurface par un noeud displacement de Cycles (K-75) |
| `0118` | hydra: maillages subdivises `leftHanded` (ceux de Houdini) retournes pour Cycles, coins de chaque face inverses et primvars par coin permutees (K-76) |
| `0119` | hydra: sous husk, cadrage reconstruit depuis `resolution`, `dataWindowNDC` et `pixelAspectRatio` - camera sur la fenetre d'affichage, tampon place par full_x/full_y, fenetre conformee a largeur x pixel aspect (K-77) |
| `0120` | hydra: `disableDepthOfField` des render settings respecte (et ouverture refermee a fStop 0), `aspectRatioConformPolicy` applique sous husk (K-78) |
| `0121` | hydra: `displayOpacity` constant des prims sans materiau -> alpha de l'objet, lue par la surface par defaut (melange transparent) (K-79) |
| `0122` | hydra: la surface par defaut lit `displayColor` comme attribut (par sommet, face, coin), gris 0,8 en repli par instance (K-80) |
| `0123` | hydra: flou de mouvement reactive en direct - chaque geometrie reechantillonne ses transformations sur l'obturateur sans passer par Hydra, dont le marquage ne resynchronisait rien dans le viewport de Houdini (K-81) ; topologie de maillage verifiee a la lecture, compteurs incoherents ecartes (plantage intermittent, K-82) |
| `0124` | hydra: UsdUVTexture dont le fichier est introuvable -> `fallback` (noir par defaut) au lieu du magenta de Cycles (K-83) |
| `0125` | hydra: nodegraphs pour la composition alpha (over, in, out, mask, matte, disjointover, premult, unpremult) et hextilednormalmap, alpha d'une constante color4 transmise a `outa` (K-84) ; volumes : primvars lues, `cycles:volume:step_size/object_space/velocity_scale` (K-85) |
| `0126` | hydra: processeur de sortie `hdcycles_cookcoptextures`, ajouté à chaque nouveau USD Render ROP, qui cuit les textures `op:` (COP) en EXR à côté de l'USD écrit, pour husk et les fermes (K-40) |
| `0127` | hydra: lumière répartie sur des jumelles pour les multiplicateurs `diffuse`/`specular` entre 0 et 1 et `shadow:color` ; une lumière sans ombre n'est plus touchée par les rayons BSDF (ombres à moitié noires avec `shadow:enable = 0`) (K-87) |
| `0128` | hydra: alpha d'une couleur calculée (jumeaux float des nœuds color4, K-17) ; `weight` des BSDF appliqué par un multiply (K-88) ; `geompropvalue` couleur et vecteur lus en entier |
| `0129` | hydra: lumière cylindre rendue par un tube maillé émissif (émission vers l'extérieur seulement, radiance dans le shader) au lieu d'un rectangle à une face (K-89) |
| `0130` | hydra: aperçu viewport d'un matériau Cycles à travers les mix (entrées `a`/`b`, côté favorisé par le facteur), `math`/`vector_math`, mix de constantes calculés ; commentaires du traducteur en anglais (K-42) |
| `0131` | hydra: `default` de `geompropvalue` posé en attribut d'objet, lu là où la géométrie n'a pas la primvar (K-90) |
| `0132` | hydra: rugosité anisotrope des métaux (conductor, generalized_schlick) convertie vers l'anisotropie et la rotation du metallic_bsdf, tangente UV (K-91) ; un `weight` branché masqué sur le nœud d'origine |
| `0133` | hydra: rugosité anisotrope d'un `dielectric_bsdf` réfléchissant (principled : `anisotropic`, `anisotropic_rotation`, tangente) (K-91) |

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
