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
- [~] `bitangent` → `geometry` (pas de sortie directe, à composer)
- [x] `texcoord` → `texture_coordinate.UV`
- [~] `geomcolor` → `attribute` (Cd)
- [~] `geompropvalue`, `geompropvalueuniform` → `attribute`
- [~] `viewdirection` → `geometry.incoming`
- [~] `facingratio` → `layer_weight` ou `fresnel`
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
- [~] `combine2`, `combine3`, `combine4` → `combine_color` / `combine_xyz`
- [~] `separate2`, `separate3c`, `separate3v`, `separate4c`, `separate4v`
      → `separate_color` / `separate_xyz`

---

## P2 — Math et couleur

### Arithmétique

- [x] `add`, `subtract`, `multiply`, `divide` → `math` / `vector_math`
- [~] `modulo`, `absval`, `sign`, `floor`, `ceil`, `round`, `fract`
- [~] `power`, `safepower`, `exp`, `ln`, `sqrt`
- [~] `sin`, `cos`, `tan`, `asin`, `acos`, `atan2`
- [~] `min`, `max`
- [~] `normalize`, `magnitude`, `distance`
- [~] `dotproduct`, `crossproduct`, `reflect`, `refract`
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

- [x] `noise3d`, `fractal3d` → `noise_texture`
- [~] `noise2d`, `fractal2d` → `noise_texture` en 2D
- [~] `cellnoise2d`, `cellnoise3d` → `voronoi_texture`
- [x] `worleynoise2d`, `worleynoise3d` → `voronoi_texture.distance`
      (pas de sortie `fac` sur ce nœud, contrairement aux autres textures)
- [~] `unifiednoise2d`, `unifiednoise3d` → `noise_texture`
- [~] `flake2d`, `flake3d` → `voronoi_texture`
- [~] `randomcolor`, `randomfloat` → `white_noise_texture`
- [x] `checkerboard` → `checker_texture`
- [ ] `grid`, `line`, `circle`, `cloverleaf`, `hexagon`, `crosshatch`,
      `tiledcircles`, `tiledcloverleafs`, `tiledhexagons`
      — motifs sans équivalent Cycles, à décomposer ou écarter
- [~] `ramplr`, `ramptb`, `ramp_gradient` → `gradient_texture`
- [ ] `ramp`, `ramp4` → `color_ramp`
- [ ] `splitlr`, `splittb` → `gradient_texture` + `math`

---

## P4 — Transformations et logique

- [ ] `rotate2d`, `rotate3d` → `vector_rotate`
- [ ] `place2d` → `mapping`
- [ ] `transformpoint`, `transformvector`, `transformnormal` → `vector_transform`
- [ ] `transformmatrix`, `creatematrix`, `creatematrix3`, `transpose`,
      `determinant`, `invertmatrix` — pas d'équivalent, à écarter
- [ ] `ifequal`, `ifgreater`, `ifgreatereq` et leurs variantes booléennes
      → `math` en mode comparaison + `mix`
- [ ] `and`, `or`, `not`, `xor` → `math`
- [ ] `switch` → chaîne de `mix`

---

## P5 — Compositing

- [ ] `over`, `in`, `out`, `mask`, `matte`, `disjointover`, `inside`, `outside`
      — demandent une composition alpha explicite
- [~] `plus`, `minus`, `difference`, `burn`, `dodge`, `screen`, `overlay`

Tous se ramènent à `mix_color` avec le bon `blend_type`, sauf `over`/`in`/`out`
qui demandent une composition alpha explicite.

---

## P6 — Surfaces alternatives et BSDF primitifs

- [~] `disney_principled`, `disney_brdf_2012`, `disney_bsdf_2015`
      → `principled_bsdf`
- [~] `gltf_pbr`, `gltf_material` → `principled_bsdf`
- [~] `conductor_bsdf` → `glossy_bsdf` métallique
- [~] `dielectric_bsdf` → `glass_bsdf`
- [ ] `generalized_schlick_bsdf` → `principled_bsdf`
- [~] `oren_nayar_diffuse_bsdf`, `burley_diffuse_bsdf` → `diffuse_bsdf`
- [~] `subsurface_bsdf` → `subsurface_scattering`
- [~] `sheen_bsdf` → `sheen_bsdf`
- [ ] `thin_film_bsdf` → entrées thin film du `principled_bsdf`
- [~] `translucent_bsdf` → `translucent_bsdf`
- [ ] `chiang_hair_bsdf` → `hair_bsdf` / `principled_hair_bsdf`
- [~] `uniform_edf`, `conical_edf`, `measured_edf`, `generalized_schlick_edf`
      → `emission`
- [~] `absorption_vdf`, `anisotropic_vdf` → `absorption_volume` / `scatter_volume`
- [~] `blackbody` → `blackbody`
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

Deux fabriques couvrent l'essentiel du volume :

- `MakeMtlxOp(mode, vector, unary)` — toute l'arithmétique se ramène à un
  `math` ou `vector_math` dont le mode est posé en valeur fixe.
- `MakeMtlxBlend(mode)` — tout le compositing se ramène à un `mix_color`.

Ajouter un nœud est donc une ligne dans la table, pas une branche de plus.
