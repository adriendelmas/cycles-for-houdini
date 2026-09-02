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
