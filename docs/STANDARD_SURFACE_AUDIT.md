# standard_surface — audit paramètre par paramètre

Chaque ligne est **mesurée au rendu**, pas lue dans la table de correspondance :
une scène de référence et une scène où le seul paramètre change. Si les deux
images sont identiques au pixel près, le paramètre ne fait rien.

Le script est `scratchpad/audit_surface.py` ; il rejoue les 39 entrées du
nodedef `ND_standard_surface_surfaceshader_100`, dont la 1.0.1 hérite.

## Honorés — 27

`base`, `base_color`, `diffuse_roughness`, `metalness`, `specular`,
`specular_color`, `specular_roughness`, `specular_IOR`, `specular_anisotropy`,
`transmission`, `subsurface`, `subsurface_radius`, `subsurface_scale`,
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

- `transmission_color`, `subsurface_color` — Cycles teinte la transmission et
  le sous-surfacique par `base_color`. Les y multiplier tacherait aussi le
  diffus, donc rendrait faux tout matériau où la transmission n'est pas à 1.
- `transmission_extra_roughness` — MaterialX ne l'ajoute qu'au lobe de
  transmission ; Cycles n'a qu'une rugosité pour tous les lobes. L'ajouter
  rendrait rugueux des matériaux non transparents qui ne l'ont pas demandé.

## Correspondances composites

Trois paramètres n'ont pas de socket direct et passent par un nœud auxiliaire :

| MaterialX | montage |
|---|---|
| `base` | `vector_math` multiply : `base_color × base` → Base Color |
| `specular` | `math` multiply par 0,5 → Specular IOR Level |

Chaque auxiliaire porte les **défauts MaterialX** de ce qu'il pilote — un
`base` de 1, un `base_color` de 0,8 gris, un `specular` de 1. Sans ça, un
réseau qui n'écrit pas ces entrées se retrouverait piloté vers une valeur
arbitraire au lieu de garder celle de Cycles. Une première version du
`specular` faisait exactement cette erreur, attrapée par le cas « non
renseigné ».
