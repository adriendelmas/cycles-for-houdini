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

## Non honorés — 10, et pourquoi

### Sans équivalent dans le nœud Cycles

- `transmission_depth`, `transmission_scatter`,
  `transmission_scatter_anisotropy` — de l'absorption et de la diffusion
  **volumétriques** à l'intérieur du solide. Le `principled_bsdf` n'a rien de
  tel ; il faudrait attacher un shader de volume à l'objet.
- `transmission_dispersion` — pas de socket de dispersion.
- `coat_anisotropy`, `coat_rotation` — le vernis de Cycles est isotrope.
- `coat_affect_color`, `coat_affect_roughness` — pas d'équivalent.

### Mappables mais faux si mappés — laissés de côté sciemment

- `subsurface_color` — le sous-surfacique de Cycles tire déjà sa couleur de
  `base_color`, donc l'entrée MaterialX ne dit rien de plus. Le seul moyen de
  l'honorer vraiment serait une fermeture de sous-surface séparée, mêlée au
  principled : le light path ne peut pas s'en charger, il n'a pas
  d'`is_subsurface_ray`.

## Correspondances composites

Quatre paramètres n'ont pas de socket direct et passent par un nœud auxiliaire :

| MaterialX | montage |
|---|---|
| `base` | `vector_math` multiply : `base_color × base` |
| `specular` | `math` multiply par 0,5 → Specular IOR Level |
| `transmission_color` | `glass_bsdf` mêlé au principled par le poids de transmission |
| `transmission_extra_roughness` | `math` add : rugosité spéculaire + supplément → rugosité du verre |

**`transmission_color` était dans la liste d'en dessous**
— écarté parce que le multiplier à `base_color` tachait aussi le diffus. Un
lobe de transmission séparé lève l'objection : chez MaterialX la transmission
**est** un lobe à part, avec sa couleur et sa rugosité, quand Cycles en fait un
étage du principled. Le montage suit MaterialX — principled sans transmission
d'un côté, `glass_bsdf` de l'autre, mêlés par le poids de transmission.

Mesuré, cube transmissif, `transmission_color` (1 / 0,1 / 0,1) :

| | valeur au centre |
|---|---|
| par un `light_path` (première version) | 0,519 / 0,265 / 0,265 |
| par le lobe de verre | 0,493 / **0,032** / 0,032 |

La première version ne teintait que les rayons **déjà** transmis, donc pas la
première traversée — celle qu'on voit. Témoin inchangé dans les deux cas : un
matériau opaque à qui l'on écrit un `transmission_color` rend au pixel près la
même image.

`transmission_extra_roughness` vient avec, puisque le verre a sa rugosité : elle
vaut la spéculaire plus le supplément.

⚠️ **Ce lobe perd la dispersion**, qui ne vit que sur le principled. Il n'est
donc monté que pour les matériaux qui écrivent l'une des deux entrées qu'il sert
— valeur posée ou fil branché. Un matériau qui n'y touche pas garde le
principled entier, et l'audit montre bien `transmission_dispersion` toujours
honoré à côté des deux nouveaux.

**`subsurface_color` reste écarté**, à la demande : le sous-surfacique de Cycles
tire déjà sa couleur de `base_color`. Il n'y a pas non plus de voie par le light
path — ce nœud n'a pas d'`is_subsurface_ray`, le sous-surfacique n'étant pas un
type de rayon mais une fermeture évaluée dans la même passe que le diffus.

⚠️ Le défaut MaterialX du rayon de diffusion, (1, 1, 1), est désormais posé
explicitement : celui de Cycles est (1, 0,2, 0,1), une peau, et un réseau qui
n'écrivait pas `subsurface_radius` en héritait sans l'avoir demandé.

Chaque auxiliaire porte les **défauts MaterialX** de ce qu'il pilote — un
`base` de 1, un `base_color` de 0,8 gris, un `specular` de 1. Sans ça, un
réseau qui n'écrit pas ces entrées se retrouverait piloté vers une valeur
arbitraire au lieu de garder celle de Cycles. Une première version du
`specular` faisait exactement cette erreur, attrapée par le cas « non
renseigné ».
