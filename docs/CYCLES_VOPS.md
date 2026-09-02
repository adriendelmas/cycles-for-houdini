# Nœuds Cycles dans Houdini — inventaire validé

Généré par `tools/build_cycles_vops.py` depuis le registre Sdr que le delegate
publie. La bibliothèque est écrite dans `install/houdini/otls/cycles_vops.hda`,
que le package `cycles.json` fait charger.

## Le compte

| | |
|---|---|
| Nœuds dans le registre Cycles | **163** |
| `convert_*` masqués | 64 |
| Exposés en VOP | **100** |
| **Manquants** | **0** |

Les `convert_*` sont insérés d'office par le compilateur de graphe de Cycles
pour raccorder deux types. Blender ne les montre pas, en poser un à la main n'a
pas de sens, et ils encombreraient le menu de soixante entrées.

Le seul nœud que nous ajoutons est `cycles_material`, le terminal qui fait d'un
réseau un matériau — l'équivalent de `mtlxsurfacematerial`.

## Ce que Blender a et que nous n'avons pas

Deux nœuds, tous deux **absents du registre de Cycles lui-même** dans cette
version : ils ne peuvent donc pas être générés.

- **Point Density** — texture volumétrique construite depuis des points.
- **OSL Script** — demande un compilateur OSL à l'exécution.

Tout le reste du menu de Blender est là : les 30 opérations du nœud `math`, les
19 modes de `mix_color`, les métriques et features de `voronoi_texture`, etc.
Ces opérations sont des **énumérations**, exposées en menus déroulants — un
seul nœud `math` porte les trente, exactement comme dans Blender.

## Le builder

`Cycles Material Builder`, dans le menu tab sous `Cycles`. Trois sorties comme
dans Blender : **surface, displacement, volume**.

Ce n'est pas un type de nœud mais un `subnet` configuré, monté par
`install/houdini/scripts/python/cycles_builder.py` et déclaré dans
`install/houdini/toolbar/CyclesTools.shelf`. C'est ainsi que Houdini fabrique
le Karma Material Builder.

Son menu tab est restreint par `tabmenumask` à `cycles_*` et aux utilitaires de
réseau. **Aucun nœud MaterialX ni Karma n'y entre** : un graphe qui les
mélangerait ne rendrait qu'ici, et pas à l'export vers Blender chez quelqu'un
qui n'a pas installé d'importateur.

## Organisation

Les catégories du menu suivent Blender : `Cycles/Shader` (24),
`Cycles/Input` (21), `Cycles/Texture` (15), `Cycles/Converter` (13),
`Cycles/Vector` (11), `Cycles/Color` (9), `Cycles/Output` (5).

Les libellés aussi : `rgb_ramp` s'affiche **Color Ramp**, `mix_closure`
**Mix Shader**, `camera_info` **Camera Data**. Chercher le nom de Blender doit
donner le nœud.

Les paramètres sont regroupés en sections repliables comme dans Blender — sur
le principled : Diffuse, Subsurface, Specular, Transmission, Coat, Sheen,
Emission, Thin Film, avec base color, metallic, roughness, IOR, alpha et normal
en tête. Les sockets de Cycles ne portent pas cette information ; elle est
retrouvée par leur préfixe.

## Ce qui est vérifié, et ce qui ne l'est pas

Vérifié au rendu : un matériau construit dans le builder, un `principled_bsdf`
dont la couleur vient d'un `noise_texture`, produit bien son motif à l'image.

Les 100 types s'instancient avec leurs paramètres, mais **seule cette paire a
été rendue**. Les autres reposent sur la même génération, pas sur une
vérification individuelle.

## Le banc d'essai

Un matériau par nœud, monté dans Houdini avec les vrais VOP, exporté puis
rendu. Passer par la chaîne complète est le seul moyen de tester les nœuds
générés plutôt que le seul delegate.

```
hython tools/bench_export.py     # un USD par nœud
python tools/bench_render.py     # un rendu par nœud
python tools/bench_diff.py       # ce qui ne change rien à l'image
```

Trois choses sont surveillées, par ordre d'importance : un avertissement du
delegate, qui trahirait un socket nommé autrement que dans Cycles ; une image
absente ; une image noire.

**Résultat : 97 nœuds rendus, 0 problème.** Comparés à une référence — le même
matériau sans rien de branché — **96 modifient l'image**. Le seul qui ne la
change pas est `principled_bsdf`, et c'est attendu : la référence en est un.

Le banc a d'abord signalé cinq nœuds inertes — `emission`, `holdout`,
`background_shader`, `subsurface_scattering`, `principled_bsdf`. C'était le
banc qui avait tort : il reconnaissait une fermeture à son nom de sortie, or
`emission` sort « emission » et `subsurface_scattering` sort « BSSRDF ». Ils
partaient donc sur la couleur de base, où une fermeture ne fait rien. La
détection se fait désormais sur le type Sdr.

## L'interface des nœuds

**Un connecteur seulement pour ce que Cycles accepte de brancher.** Le registre
dit d'un socket s'il est connectable, et cela recoupe exactement ce que Blender
montre : sur le principled, `distribution` et `subsurface_method` sont des menus
déroulants, pas des sockets. Les exposer en entrée aurait laissé construire des
graphes qui ne se rejoueraient nulle part ailleurs.

**`surface_mix_weight` est masqué.** C'est le poids de mélange interne que
Cycles porte sur chaque fermeture ; Blender ne l'expose jamais, c'est le nœud
Mix Shader qui le pose. L'offrir n'aurait fait qu'égarer.

**Un nom de fichier ouvre un sélecteur.** Le delegate marque désormais ces
sockets comme des chemins d'actif dans le registre, ce dont le générateur tire
un champ à parcourir plutôt qu'une chaîne à coller.

**Un booléen est une case à cocher.** Un booléen de Cycles arrive en USD sous
forme d'entier, et rien ne le distingue alors d'un compteur : le delegate le
signale maintenant dans les métadonnées, et l'interface n'offre plus un champ
libre là où seuls zéro et un ont un sens.

**Les sections sont repliables, pas des onglets.** Le mot-clé de Houdini est
`groupcollapsible` ; un simple `group` fabrique des onglets et rejette tout ce
qui reste hors dossier dans un onglet « Other ».
