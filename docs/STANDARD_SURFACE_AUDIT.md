# standard_surface — audit paramètre par paramètre

Chaque ligne est **mesurée au rendu**, pas lue dans la table de correspondance :
une scène de référence et une scène où le seul paramètre change. Si les deux
images sont identiques au pixel près, le paramètre ne fait rien.

Le script est `scratchpad/audit_surface.py` ; il rejoue les 39 entrées du
nodedef `ND_standard_surface_surfaceshader_100`, dont la 1.0.1 hérite.

## Honorés — 29

`base`, `base_color`, `diffuse_roughness`, `metalness`, `specular`,
`specular_color`, `specular_roughness`, `specular_IOR`, `specular_anisotropy`,
`transmission`, `transmission_color`, `transmission_dispersion`, `subsurface`,
`subsurface_color`, `subsurface_radius`, `subsurface_scale`,
`subsurface_anisotropy`, `sheen`, `sheen_color`, `sheen_roughness`, `coat`,
`coat_color`, `coat_roughness`, `coat_IOR`, `thin_film_thickness`,
`thin_film_IOR`, `emission`, `emission_color`, `opacity`, `thin_walled`.

Deux d'entre eux ne se voient que sous condition, ce qui avait d'abord fait
conclure à tort qu'ils étaient morts :

- `specular_rotation` demande une anisotropie non nulle ;
- `thin_walled` ne se manifeste que sous transmission.

`specular_rotation` reste **sans effet mesurable** même avec
`specular_anisotropy = 0.9` et `metalness = 1` (écart 3,8·10⁻⁷, soit le bruit).
Le socket existe et la valeur est écrite : la piste est du côté de la base
tangente que Cycles utilise pour orienter le lobe. Non résolu.

## Non honorés — 12, et pourquoi

### Sans équivalent dans le nœud Cycles

- `transmission_depth`, `transmission_scatter`,
  `transmission_scatter_anisotropy` — de l'absorption et de la diffusion
  **volumétriques** à l'intérieur du solide. Le `principled_bsdf` n'a rien de
  tel ; il faudrait attacher un shader de volume à l'objet.
- `transmission_dispersion` — pas de socket de dispersion.
- `coat_anisotropy`, `coat_rotation` — le vernis de Cycles est isotrope.
- `coat_affect_color`, `coat_affect_roughness` — pas d'équivalent.

### Mappables mais faux si mappés — laissés de côté sciemment

- `transmission_extra_roughness` — MaterialX ne l'ajoute qu'au lobe de
  transmission ; Cycles n'a qu'une rugosité pour tous les lobes. L'ajouter
  rendrait rugueux des matériaux non transparents qui ne l'ont pas demandé.

## Correspondances composites

Trois paramètres n'ont pas de socket direct et passent par un nœud auxiliaire :

| MaterialX | montage |
|---|---|
| `base` | `vector_math` multiply : `base_color × base` |
| `specular` | `math` multiply par 0,5 → Specular IOR Level |
| `transmission_color` | `mix_color` commandé par `light_path.is_transmission_ray` → Base Color |
| `subsurface_color` | `mix_color` à hauteur de `subsurface`, multiplié à la couleur de base |

**`transmission_color` et `subsurface_color` étaient dans la liste d'en dessous**
— écartés parce que les multiplier à `base_color` tachait aussi le diffus. Deux
montages lèvent l'objection, tous deux mesurés :

- la couleur de transmission ne touche que les rayons qui traversent, un
  `light_path` commandant le mélange. Témoin : un matériau opaque à qui l'on
  écrit un `transmission_color` vert rend **au pixel près** la même image ;
- la couleur de sous-surface teinte la couleur de base **à hauteur du poids de
  sous-surface** : nulle à 0, entière à 1, ce qui est exact aux deux bouts,
  puisque le `principled_bsdf` mélange diffus et sous-surfacique selon ce même
  poids et les colore tous deux par `base_color`.

L'autre route pour la sous-surface — multiplier le **rayon** par la couleur —
a été essayée et **inverse la teinte** : un `subsurface_color` rouge donne un
objet cyan, le rouge diffusant plus loin au lieu de ressortir. Mesuré :
référence neutre (2,01 / 2,01 / 2,01) → (2,01 / 3,01 / 3,17). Le montage retenu
donne (2,01 / 0,74 / 0,44), soit la teinte demandée.

⚠️ Le défaut MaterialX du rayon de diffusion, (1, 1, 1), est désormais posé
explicitement : celui de Cycles est (1, 0,2, 0,1), une peau, et un réseau qui
n'écrivait pas `subsurface_radius` en héritait sans l'avoir demandé.

Chaque auxiliaire porte les **défauts MaterialX** de ce qu'il pilote — un
`base` de 1, un `base_color` de 0,8 gris, un `specular` de 1. Sans ça, un
réseau qui n'écrit pas ces entrées se retrouverait piloté vers une valeur
arbitraire au lieu de garder celle de Cycles. Une première version du
`specular` faisait exactement cette erreur, attrapée par le cas « non
renseigné ».
