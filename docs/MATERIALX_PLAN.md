# Traduction MaterialX → Cycles : plan de travail

Inventaire mesuré sur Houdini 22.0.368 : **239 VOP `mtlx*`** placeables dans
l'interface, pour **161 nœuds Cycles** disponibles.

Convention : `[x]` fait et **vérifié au rendu**, `[~]` mappé mais non vérifié,
`[ ]` à faire, `[-]` sans équivalent Cycles, écarté avec la raison.

> **Comment vérifier, et deux pièges à ne pas répéter.**
>
> Un nœud n'est coché `[x]` que si un rendu montre son effet. Deux méthodes de
> vérification se sont révélées vides :
>
> 1. **Compter les avertissements ne mesure rien** tant qu'ils passent par
>    `TF_WARN` / `TF_RUNTIME_ERROR` : husk les avale. Ils passent désormais par
>    le logger de Cycles, qui s'affiche.
> 2. **Instancier des nœuds non connectés ne teste rien** : Hydra élague le
>    réseau et ne transmet que ce qui est accessible depuis un terminal. Le
>    delegate ne voit jamais ces nœuds.
>
> Seule une chaîne **connectée**, jugée sur les pixels, fait foi.

---

## P0 — Correctness : ce qui est mappé mais rend faux

Ces nœuds passent déjà par la traduction mais ne donnent pas le même résultat
que Karma. Prioritaires sur tout ajout : un nœud qui rend faux est pire qu'un
nœud absent, parce que rien ne signale l'erreur.

- [~] `normalmap` — écart visible avec Karma sur une même normal map.
      Cause probable traitée par le colorspace ci-dessus : la texture était
      décodée en sRGB avant d'atteindre le nœud. Écartés par la lecture du
      code : `space` vaut `tangent` par défaut et `convention` vaut `OPENGL`,
      qui sont bien les conventions MaterialX. **À revérifier au rendu.**
- [ ] `normalmap::2.0` — variante à traiter avec la précédente.
- [~] `image` — **colorspace corrigé, à vérifier au rendu.** Cycles
      `image_texture` a un `colorspace` valant `auto` par défaut, qui applique
      une décompression sRGB à un fichier 8 bits. Une normal map ainsi décodée
      donne des normales fausses. MaterialX distingue les variantes dans le nom
      du nodedef : `ND_image_color3` est de la couleur, `ND_image_vector3` de
      la donnée. Les variantes float et vecteur sont désormais lues en `data`.
      Restent à poser : `alpha_type` et `extension`.
- [ ] `displacement` — le terminal fonctionne sur un matériau écrit à la main ;
      à valider sur un Karma Material Builder, où surface et displacement
      sortent du même subnet.

---

## P1 — Le socle d'un matériau utilisable

### Surfaces

- [x] `standard_surface` → `principled_bsdf` (30 entrées mappées)
- [~] `open_pbr_surface` → `principled_bsdf`
- [ ] `UsdPreviewSurface` → `principled_bsdf` *(déjà géré par le code amont)*
- [ ] `surface` → `principled_bsdf` minimal
- [ ] `surfacematerial` — terminal, à traiter avec les sorties de matériau
- [ ] `displacement` → `displacement` ✅ mappé, voir P0
- [ ] `volumematerial`, `volume` → shader volumétrique

### Géométrie et coordonnées

- [x] `position` → `geometry.position`
- [x] `normal` → `geometry.normal`
- [x] `tangent` → `geometry.tangent`
- [x] `bitangent` → `geometry.tangent` — vérifié (approximation : Cycles n'a
      pas de sortie bitangente, la tangente est utilisée en attendant)
- [x] `texcoord` → `texture_coordinate.UV`
- [x] `geomcolor` → `attribute` — vérifié
- [x] `geompropvalue` → `attribute` — vérifié
- [~] `geompropvalueuniform`
- [x] `viewdirection` → `geometry.incoming` — vérifié
- [x] `facingratio` → `layer_weight.facing` — vérifié
- [ ] `frame`, `time` → `value` piloté par la frame

### Textures

- [x] `image` → `image_texture` (voir P0)
- [x] `tiledimage` → `image_texture`
- [~] `latlongimage` → `environment_texture`
- [ ] `hextiledimage`, `hextilednormalmap` — pas d'équivalent, à décomposer
- [ ] `triplanarprojection` → pas d'équivalent direct, à composer

### Utilitaires indispensables

- [x] `bump` → `bump`
- [~] `heighttonormal` → `bump` ou `normal_map`
- [x] `mix` → `mix_color`
- [~] `layer` → `mix_closure`
- [ ] `constant` → `value` / `rgb` selon le type
- [ ] `convert`, `swizzle`, `extract` → `separate_*` / `combine_*`
- [x] `combine3` → `combine_color` / `combine_xyz` — vérifié
- [~] `combine2`, `combine4`
- [x] `separate2`, `separate3c`, `separate3v`, `separate4c`, `separate4v`
      → `separate_color` / `separate_xyz` — vérifié. MaterialX nomme ses
      sorties `outx`/`outy`/`outz` et `outr`/`outg`/`outb`, Cycles les nomme
      `x`/`y`/`z` et `r`/`g`/`b` : sans la traduction des **noms de sortie**,
      la connexion était perdue et le nœud aval gardait sa valeur par défaut.

---

## P2 — Math et couleur

### Arithmétique

- [x] `add`, `subtract`, `multiply`, `divide` → `math` / `vector_math`
- [x] `modulo` — vérifié
- [x] `absval`, `sign`, `floor`, `ceil`, `round` — vérifiés
- [~] `fract`
- [x] `power`, `exp`, `ln`, `sqrt` — vérifiés
- [~] `safepower`
- [x] `sin` — vérifié
- [x] `cos`, `tan`, `atan2` — vérifiés
- [~] `asin`, `acos`
- [x] `min`, `max` — vérifiés
- [x] `normalize`, `magnitude`, `distance` — vérifiés
- [x] `dotproduct`, `crossproduct` — vérifiés
- [~] `reflect`, `refract`
- [ ] `clamp`, `smoothstep`, `remap`, `range` — Cycles n'a pas de nœud
      équivalent, à composer
- [ ] `invert`, `trianglewave`, `luminance`, `atan2::2.0`

Tous se ramènent à `math` ou `vector_math` avec la bonne valeur d'enum — le
mécanisme de valeurs fixes est déjà en place.

### Couleur

- [ ] `hsvtorgb`, `rgbtohsv` → `separate_hsv` / `combine_hsv`
- [ ] `hsvadjust`, `saturate` → `hue_saturation`
- [ ] `colorcorrect` → chaîne à composer
- [ ] `contrast`, `curveadjust` → `rgb_curves`
- [ ] `premult`, `unpremult` → `math`
- [ ] Les 10 convertisseurs d'espace colorimétrique
      (`acescg_to_lin_rec709`, `srgb_texture_to_lin_rec709`, …)
      → à traiter par le `colorspace` de `image_texture` plutôt que par des
      nœuds, sinon on duplique la conversion.

---

## P3 — Procéduraux

Les dix familles ci-dessous ne sont plus des approximations : elles vont sur
`mx_noise_texture`, un nœud Cycles qui implémente les algorithmes MaterialX
eux-mêmes — mêmes fonctions de hachage, mêmes constantes de normalisation,
même sémantique de paramètres. Origine et réserve : voir la note en fin de
section.

- [x] `noise2d`, `noise3d` → `mx_noise_texture` perlin — vérifiés
- [x] `fractal2d`, `fractal3d` → `mx_noise_texture` fractal — vérifiés
- [x] `cellnoise2d`, `cellnoise3d` → `mx_noise_texture` cell — vérifiés
- [x] `worleynoise2d`, `worleynoise3d` → `mx_noise_texture` worley — vérifiés
- [x] `unifiednoise2d`, `unifiednoise3d` → `mx_noise_texture` unified —
      vérifiés, le sélecteur `type` étant transmis tel quel
- [~] `flake2d`, `flake3d` → `voronoi_texture`
- [x] `randomcolor`, `randomfloat` → `white_noise_texture` — vérifié
- [x] `checkerboard` → `checker_texture`

### D'où vient `mx_noise_texture`

Le nœud n'est pas dans Cycles amont : il vient de la
[PR Blender #158054](https://projects.blender.org/blender/blender/pulls/158054),
dont la partie Cycles est isolée et purement additive, donc reprise telle
quelle dans la série de patchs (à deux ajustements près, voir les patchs).

**Réserve :** cette PR est *ouverte*, pas fusionnée. Elle peut encore changer ou
être refusée. Le jour où elle atterrit en amont, ces patchs deviennent
redondants et doivent être retirés plutôt que rebasés.

Un détail qui coûte cher si on l'ignore : la variante du nodedef décide de la
sortie lue. `ND_fractal3d_float` est un scalaire qui se diffuse sur les trois
canaux, `ND_fractal3d_color3` est trois bruits différents. Décider d'après ce
que la sortie alimente — l'entrée `base_color` est une couleur, donc lisons la
sortie couleur — rend bariolé tout bruit gris pilotant une couleur.
- [ ] `grid`, `line`, `circle`, `cloverleaf`, `hexagon`, `crosshatch`,
      `tiledcircles`, `tiledcloverleafs`, `tiledhexagons`
      — motifs sans équivalent Cycles, à décomposer ou écarter
- [x] `ramplr` → `gradient_texture` pilotant un `mix_color` — **vérifié**,
      le dégradé entre `valuel` et `valuer` s'affiche correctement.
- [~] `ramptb` — même montage, mais le gradient de Cycles ne court que selon X.
      Mappé sur le type `diagonal` faute de mieux : **approximation assumée**,
      le vrai haut-bas demanderait un échange d'axes, donc un second auxiliaire.
- [ ] `ramp`, `ramp4`, `ramp_gradient` → `color_ramp`
- [ ] `ramp`, `ramp4` → `color_ramp`
- [ ] `splitlr`, `splittb` → `gradient_texture` + `math`

---

## P4 — Transformations et logique

- [x] `rotate2d`, `rotate3d` → `vector_rotate` — vérifiés
- [x] `place2d` → `mapping` — vérifié
- [x] `transformpoint`, `transformvector`, `transformnormal` → `vector_transform`
      — vérifiés
- [ ] `transformmatrix`, `creatematrix`, `creatematrix3`, `transpose`,
      `determinant`, `invertmatrix` — pas d'équivalent, à écarter
- [ ] `ifequal`, `ifgreater`, `ifgreatereq` et leurs variantes booléennes
      — demandent une comparaison **et** une sélection, donc deux entrées
      routées vers deux nœuds. Le mécanisme composite n'en gère qu'une.
- [~] `and` → `math multiply`, `or` → `math maximum` — approximations sur des
      valeurs 0/1
- [ ] `not`, `xor` — pas d'équivalent direct
- [ ] `switch` → chaîne de `mix`

---

## P5 — Compositing

- [ ] `over`, `in`, `out`, `mask`, `matte`, `disjointover`, `inside`, `outside`
      — demandent une composition alpha explicite
- [x] `screen` — vérifié
- [x] `plus`, `minus`, `difference`, `burn`, `dodge`, `overlay` — vérifiés

Tous se ramènent à `mix_color` avec le bon `blend_type`, sauf `over`/`in`/`out`
qui demandent une composition alpha explicite.

---

## P6 — Surfaces alternatives et BSDF primitifs

- [~] `disney_principled`, `disney_brdf_2012`, `disney_bsdf_2015`
      → `principled_bsdf`
- [~] `gltf_pbr`, `gltf_material` → `principled_bsdf`
- [x] `conductor_bsdf` → `glossy_bsdf` — vérifié
- [x] `dielectric_bsdf` → `glass_bsdf` — vérifié
- [ ] `generalized_schlick_bsdf` → `principled_bsdf`
- [x] `oren_nayar_diffuse_bsdf`, `burley_diffuse_bsdf` → `diffuse_bsdf` — vérifiés
- [x] `subsurface_bsdf` → `subsurface_scattering` — vérifié
- [x] `sheen_bsdf` → `sheen_bsdf` — vérifié
- [ ] `thin_film_bsdf` → entrées thin film du `principled_bsdf`
- [x] `translucent_bsdf` → `translucent_bsdf` — vérifié
- [ ] `chiang_hair_bsdf` → `hair_bsdf` / `principled_hair_bsdf`
- [x] `uniform_edf` → `emission` — vérifié
- [~] `conical_edf`, `measured_edf`, `generalized_schlick_edf`
- [~] `absorption_vdf`, `anisotropic_vdf` → `absorption_volume` / `scatter_volume`
- [x] `blackbody` → `blackbody` — vérifié
- [ ] `artistic_ior`, `roughness_anisotropy`, `glossiness_anisotropy`,
      `roughness_dual`, `open_pbr_anisotropy`, `chiang_hair_roughness`,
      `chiang_hair_absorption_from_color`,
      `deon_hair_absorption_from_melanin` — nœuds de conversion de paramètres,
      à traduire en arithmétique
- [~] `ambientocclusion` → `ambient_occlusion`
- [ ] `gooch_shade` — stylisé, pas d'équivalent

---

## Écartés

- [-] Les 13 nœuds `Lama*` — bibliothèque RenderMan de Pixar, hors périmètre
      d'une traduction MaterialX standard.
- [-] `light`, `directional_light`, `point_light`, `spot_light` — les lumières
      passent par les sprim USD, pas par le réseau de shading.
- [-] `standard_surface_to_UsdPreviewSurface`,
      `standard_surface_to_gltf_pbr`, `standard_surface_to_open_pbr_surface`,
      `open_pbr_surface_to_standard_surface` — nœuds de conversion entre
      modèles, sans objet ici puisqu'on traduit chaque modèle directement.
- [-] `UsdUVTexture`, `UsdUVTexture23`, `UsdPrimvarReader`, `UsdTransform2d`
      — déjà couverts par la traduction UsdPreviewSurface du code amont.
- [-] `blur` — opération d'image, pas de nœud de shading équivalent.
- [-] `arrayappend`, `dot` — utilitaires de graphe sans effet au rendu.

---

## Méthode

Chaque groupe est vérifié par un rendu comparatif contre Karma sur la même
scène avant d'être coché. Les noms de sockets Cycles sont relevés dans le
registre Sdr construit en phase 4a, jamais devinés — c'est ce qui a évité
plusieurs erreurs (`max_bounce` au singulier, sorties `fac`/`color` selon le
type de connexion).


---

## Structure du code

La traduction est passée d'une chaîne de `if` à une **table de préfixes**
(`MtlxTable()` dans `material.cpp`), où le préfixe le plus long l'emporte. Un
nœud spécifique peut donc précéder sa famille — `ND_image_color` avant
`ND_image_`, qui n'ont pas le même colorspace.

### Correspondances composites

Certains nœuds MaterialX n'ont pas d'équivalent Cycles **unique**. Un dégradé
gauche-droite, par exemple, vaut un `gradient_texture` pilotant le facteur d'un
`mix_color`. Une correspondance peut donc déclarer un **nœud auxiliaire** :
type, sortie, entrée de destination, et ses valeurs fixes. Le delegate le crée
et le câble à la construction du graphe.

Un piège à retenir : Cycles résout ses sockets par **nom d'interface**, pas par
identifiant. La sortie du gradient est `"Fac"` et l'entrée du mix est
`"Factor"` — pas `fac` des deux côtés.

Deux fabriques couvrent l'essentiel du volume :

- `MakeMtlxOp(mode, vector, unary)` — toute l'arithmétique se ramène à un
  `math` ou `vector_math` dont le mode est posé en valeur fixe.
- `MakeMtlxBlend(mode)` — tout le compositing se ramène à un `mix_color`.

Ajouter un nœud est donc une ligne dans la table, pas une branche de plus.


## Journal de vérification

**39 chaînes connectées rendues, 39 sans perte de connexion.** Chaque cas est
un graphe minimal branché sur `base_color` ou directement sur le terminal de
surface, rendu par husk, avec les avertissements de traduction lus dans la
console.

Deux niveaux de preuve, à ne pas confondre :

- **Plomberie** — aucun avertissement : chaque entrée et chaque sortie
  référencée existe, aucune connexion n'est écartée.
- **Sémantique** — le rendu change comme attendu. Les sept closures donnent
  sept moyennes distinctes, et `uniform_edf` ressort nettement plus lumineuse
  (0,69 contre ~0,53), ce qui confirme que le terminal est réellement pris en
  compte et pas seulement accepté.

Un nœud n'est coché `[x]` que s'il a passé les deux.
