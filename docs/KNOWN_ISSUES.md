# Known issues

Numbered so that PLAN.md and PROGRESS.md can point at them. Each entry names
the line that is wrong and how the claim was checked. "Confirmed" means read
in the code *and* checked against the MaterialX definition shipped with
Houdini 22.0.368 (`$HFS/houdini/materialx/libraries`) or against Cycles'
kernel; "probable" means read in the code only.

Paths are relative to `external/cycles-53/src/hydra/` unless stated.

## A. MaterialX translation - wrong results

### K-01 `mix` is inverted — confirmed — **fixed** (patch 0076, 2026-10-07)
`material.cpp:654` wired `fg → a`, `bg → b`, `mix → fac`. MaterialX:
`mix(bg, fg, mix)` (`stdlib_genglsl_impl.mtlx:604`), so `mix = 1` yields `fg`.
Cycles `mix_color`: `fac = 1` yields `b`. Fix: `fg → b`, `bg → a`. Bench case
`mix`: (0.300, 0.200, 0.700) before, (0.700, 0.200, 0.300) after, expected
(0.7, 0.2, 0.3).

### K-02 The seven compositing blends are inverted — confirmed — **fixed** (0076)
`material.cpp:734` (`MakeMtlxBlend`) used the same `fg → a`, `bg → b`.
MaterialX `plus`: `mix·(bg+fg) + (1−mix)·bg = bg + mix·fg`
(`stdlib_genglsl_impl.mtlx:546`). Cycles blend `add`: `a + fac·b`. Same fix
as K-01, for `plus`, `minus`, `difference`, `burn`, `dodge`, `screen`, `overlay`.
Bench case `plus` passes; the other six share the code and are not yet
value-tested.

### K-03 Closure mix/add/multiply go to colour and scalar nodes — confirmed — **fixed** (0078)
Routed by the nodedef's type suffix before the prefix table: `mix_closure`,
`add_closure`, a mix against nothing for `multiply`; vector nodes for the
displacementshader family. Bench cases `closure_mix`, `closure_add`,
`closure_scale`, `surface_mix` exact. Original note:
`material.cpp:1833` `{"ND_mix_", &MtlxMix}` also catches `ND_mix_bsdf`,
`ND_mix_edf`, `ND_mix_vdf`, `ND_mix_surfaceshader`, `ND_mix_displacementshader`
and sends them to `mix_color`. `ND_add_bsdf`/`ND_add_edf` take the `ND_add_`
branch (`material.cpp:1942`) onto the scalar `math`; `ND_multiply_bsdfC/F`,
`_edfC/F`, `_vdfC/F` onto `math`/`vector_math`. The closure connection is
dropped with a warning. Needed: `mix_closure` (with the K-01 orientation:
`fg → Closure2`), `add_closure`, and for multiply a `mix_closure` against
`transparent_bsdf` or a `surface_mix_weight` write.

### K-04 `ND_volume` is missing — confirmed — **fixed** (0078)
`volume(vdf, edf)` → `add_closure`; `mtlx_inputs.py` reports no missing node
any more. No value case yet: that needs a volume scene. Original note:
Not in `MtlxTable()`, and `tools/mtlx_coverage.py` excludes `volume$` from
the denominator. `absorption_vdf` and `anisotropic_vdf` are mapped but no
MaterialX volume network can reach the volume terminal. Same shape as the
`ND_surface` gap fixed on 2026-09-10: `volume(vdf, edf)` → `add_closure`.

### K-05 OpenPBR, Disney and glTF surfaces are aliased, not translated — confirmed — **fixed** (0080)
Three tables of their own, each input mapped or listed as dropped in the code:
OpenPBR on the standard_surface helpers with its names, units (thin film in
micrometres, subsurface radius/scale swapped) and defaults; glTF with the
specification's defaults (white, metallic 1, roughness 1) and sheen,
iridescence, dispersion and anisotropy rotation converted; Disney principled
with its tints as white-to-base mixes and the clearcoat gloss converted to a
roughness. `tools/mtlx_defaults.py` checks all three plus standard_surface and
UsdPreviewSurface. Original note:
`material.cpp:1710-1712` point `ND_open_pbr_surface`, `ND_disney_principled`,
`ND_gltf_pbr` at the `standard_surface` table. OpenPBR inputs
(`base_weight`, `base_metalness`, `specular_weight`, `specular_ior`,
`emission_luminance`, `geometry_opacity`, `geometry_normal`, `fuzz_*`,
`coat_darkening`...; `bxdf/open_pbr_surface.mtlx`) are not in that table and
fall to the "no input" warning. Metal, IOR, emission, opacity and normal are
lost. Each needs its own table; `gltf_pbr` and `disney_principled` likewise.

### K-06 `geomcolor` reads nothing — confirmed — **fixed** (0076 + 0075)
`material.cpp:1195` created an `attribute` node with no `attribute` value;
`AttributeNode::attributes()` requested an attribute named `""`. Fixed with
`attribute = displayColor`. That exposed K-19: with the name right the colour
was still garbage, because the mesh wrote float3 primvars at the wrong stride.
Bench case `geomcolor`: (0.200, 0.600, 0.900) exact after both fixes.

### K-07 Colour and vector variants of scalar operators collapse to grey — confirmed — **fixed** (0079)
`FindMtlxVectorTwin` gives every family a vector twin: `vector_math` where
it has the operation, separate → three `math` → combine for exp, ln, sqrt,
asin, acos, atan2, min(max()) for clamp, `vector_map_range` for remap, range
and smoothstep. Fifteen bench cases with coloured inputs; on the previous DLL
clamp, max and sqrt came out grey. Three scalar operators were wrong too and
are fixed in the same patch: `ln` (Cycles' logarithm takes its base on the
second input, 0.5 by default - it returned ln(x)/ln(0.5)), `modulo` (MaterialX
floors, Cycles truncated) and `atan2` (operands `iny`/`inx`, never mapped).
`invert` became `amount - in`, `luminance` takes ACEScg weights. Original note:
`isVector` (`material.cpp:1927`) is only consulted for add/sub/mul/div. Every
other family - `absval`, `sign`, `floor`, `ceil`, `round`, `fract`, `modulo`,
`min`, `max`, `power`, `sqrt`, `sin`..., `clamp`, `remap`, `range`,
`smoothstep` - maps to the scalar `math`, `clamp` or `map_range` in float
mode, and `convertToCycles<float>` averages the colour. `ND_clamp_color3`,
`ND_max_color3`, `ND_power_color3` render grey. `vector_math` has absolute,
floor, ceil, fraction, modulo, minimum, maximum, sine, cosine, tangent;
`clamp` and `map_range` have a vector data type. Power, sqrt, exp, ln need
three scalar helpers.

### K-08 `saturate` is not the MaterialX formula — confirmed — **fixed** (0076)
`material.cpp:1424` used `hsv.saturation`. MaterialX (`stdlib_ng.mtlx`,
`NG_saturate_color3`): `mix(luminance(in, lumacoeffs), in, amount)` with
ACEScg coefficients by default, not Rec.709. For `(0.9, 0.2, 0.1)` at 0.2:
MaterialX `(0.488, 0.348, 0.328)`, the old code `(0.90, 0.76, 0.74)`. The
bench's expected value had been derived from the implementation. Fixed with a
`vector_math` dot product (which also honours a connected `lumacoeffs`)
feeding `mix_color.a`; bench case `saturate` passes exactly.

### K-09 `layer` is a 50/50 mix — probable — **replaced by a documented approximation** (0078)
Now a `mix_closure` weighted by `layer_weight.Fresnel` (blend 0.333, IOR
1.5): right for a dielectric top over a base, approximate for any other top.
Renders a dielectric over red as (0.87, 0.20, 0.10). `layer_vdf` passes the
surface only. Original note:
`material.cpp:1197` maps `top`/`base` to `mix_closure` and never sets `fac`
(Cycles default 0.5). MaterialX vertical layering is `top + (1 − albedo(top))·base`.
A coat over a base loses half the base. Cycles has no exact node; the nearest
is `add_closure` for thin coats, or a `layer_weight`-driven mix. Document the
approximation chosen.

### K-10 `facingratio` is inverted — confirmed — **fixed** (0076)
`material.cpp:1204` returned `layer_weight.Facing`, which is 0 facing the
camera; MaterialX `facingratio` (nprlib, `NG_facingratio_float`) is
`|dot(V, N)|` with its defaults, 1 facing the camera. Fixed as
`abs(dot(Incoming, Normal))`; bench case `facingratio`: 0.034 before, 0.966
after on the bench plane (0.96 expected from the perspective spread).
`invert`, `faceforward` and connected `viewdirection`/`normal` are still not
carried and are reported.

### K-11 `viewdirection` points the wrong way — probable — **fixed** (0076)
`material.cpp:1210` returned `geometry.Incoming` (surface → camera). The
MaterialX HwViewDirection node emits `normalize(P − viewPosition)`, camera →
surface. Negated. No bench case: the plane's mean cannot see a direction.

### K-12 `heighttonormal` outputs a world normal — confirmed — **fixed** (0108)
`material.cpp:1149` maps it to `bump`, whose output is a shading normal.
MaterialX outputs a tangent-space normal *map* (`(0.5, 0.5, 1)` when flat)
meant for a following `normalmap`. The chain `heighttonormal → normalmap`
therefore breaks. Either detect the chain and collapse it, or build the
tangent map from `bump` − N through a `vector_transform` to tangent space.

Fixed 2026-10-08 by the second route, without a transform: heighttonormal is
a nodegraph the delegate ships - Cycles' bump of the height, its normal's dot
products with the UV tangent, the bitangent and the normal, encoded * 0.5 +
0.5. Flat gives (0.5, 0.5, 1), as Karma; `heighttonormal` into `normalmap`
renders identical to `bump` on a sine ripple, pixel for pixel - MaterialX
defines `bump` as exactly that chain. Approximation kept: the slope is the
bump's, in world units, where MaterialX's is in UV units (scale / 16 *
dh/du); the two agree only for one UV unit per world unit.

### K-13 `conductor_bsdf` loses its colour — confirmed — **fixed** (0078)
Now `metallic_bsdf` in `physical_conductor` mode with `ior` and `extinction`
carried, MaterialX's gold as default. Not yet value-tested against a
reference. Original note:
`material.cpp:1250` maps to `glossy_bsdf` and leaves `ior`/`extinction`
unmapped: every conductor is white. Cycles 4.3+ `metallic_bsdf` with
`fresnel_type = physical_conductor` takes exactly `ior` and `extinction`.

### K-14 Approximate closures without a note in the log — confirmed — **fixed** (0103, 0107)
`dielectric_bsdf`: `tint` and `scatter_mode` (R-only coats become glass with
transmission) unmapped. `subsurface_bsdf`: `anisotropy` unmapped.
`absorption_vdf.absorption` is a coefficient, Cycles `absorption_volume.color`
is a transmittance. `ambientocclusion.coneangle → distance` is not the same
quantity. All render *something*; none say they are approximate.

`dielectric_bsdf` follows its scatter mode since 0103 (K-58). The absorption
since 0107: Cycles absorbs (1 - colour) * density, so the colour is now
1 - absorption at density 1 - it was the coefficient itself, which inverted
it (0.2 absorbed as 0.8). `tools/bench_volume.py` measures the light through
a 2-unit cube against exp(-2 sigma): 0.670 / 0.368 / 0.135 for sigma 0.2 /
0.5 / 1, exact; also on a `leftHanded` cube, as Houdini writes meshes. Also
in 0107: `subsurface_bsdf` carries its `anisotropy`, and its scattering
length is right - Cycles scatters over radius * scale and its scale defaults
to 0.005, which the mapping left: the light spread 200 times too short (the
whole sphere 10 % too red against Karma, within 4 % after; `bench_agree.py`
checks the whole sphere for that case). The AO node takes `maxdistance` as
its distance, where it took the cone angle; the angle itself has no Cycles
counterpart and is dropped. K-14 is closed.

### K-60 `surface_unlit` rendered black — confirmed — **fixed** (0107)
Houdini's MtlX Surface Unlit (`ND_surface_unlit`) fell on the `ND_surface`
prefix, whose mapping has no `emission_color`: the colour was dropped with a
warning and the surface came out black. 0107 gives it its own mapping: a mix
by `opacity` between a transparent and the sum of an emission (colour times
`emission`) and a transparent tinted by `transmission_color * transmission`.
Found as the white wall of the volume bench, which checks it since.

### K-55 Unauthored surface inputs took Cycles' defaults — confirmed — **fixed** (0080)
Hydra forwards only authored inputs, and Houdini authors only what the user
touched, so every untouched input of a surface took the principled BSDF's
default rather than its own model's. `standard_surface`: specular roughness
0.5 instead of 0.2, subsurface scale 0.005 instead of 1, coat roughness 0.03
instead of 0.1, sheen roughness 0.5 instead of 0.3, thin film IOR 1.33 instead
of 1.5. `UsdPreviewSurface`: diffuse 0.8 instead of 0.18 - an untouched
preview surface rendered four times too bright. `tools/mtlx_defaults.py`
renders a sphere with no input written and with every input written at its
default; on the previous DLL all five surfaces differed (up to 40 % of the
image blocks), now none does. Defaults are pinned per table.

### K-56 UsdUVTexture channels were averaged — confirmed — **fixed** (0080)
`r`, `g` and `b` were all routed to the image's `color` output; plugged into
a scalar input, that colour was averaged. A roughness read from the green
channel of a packed occlusion/roughness/metal texture got the mean of all
three. Each channel now comes off a `separate_color` helper, and `rgb` passes
`rgb * scale + bias` first. Bench cases `uvtex_g`, `uvtex_b` returned the
whole colour on the previous DLL.

### K-15 `UsdPreviewSurface` gaps — confirmed — **mostly fixed** (0080)
Fixed: `scale`/`bias` (rgb only; their alpha components are not carried),
per-channel outputs (K-56), `UsdTransform2d` onto a `mapping` node (rotation
degrees to radians, 2D scale and translation widened; values only, a
connected rotation is linked unconverted), `sourceColorSpace` names, the
preview surface's own defaults (K-55). Still open: `fallback`,
`UsdPreviewSurface.displacement`, `occlusion`, `opacityThreshold`, and
`specularColor` is taken whatever `useSpecularWorkflow` says.
`UsdTransform2d` has no value case yet. Original note:
`UsdTransform2d` is a token (`material.cpp:69`) with no mapping in `findUsd`.
`UsdUVTexture.scale`/`bias`/`fallback` are unmapped, so the standard normal-map
encoding (`scale 2, bias −1`) renders wrong. `sourceColorSpace` was passed
verbatim (`material.cpp:2011`); `raw`, `sRGB` and `auto` now become `data`,
`__builtin_srgb` and the empty string (0076, not yet value-tested).
`displacement` on the preview surface finds no `Displacement` output on
`principled_bsdf`.

### K-16 `kma` is declared, never read — confirmed — **fixed** (0080)
`Sync` now reads `cycles`, then `mtlx`, then `kma`, then the universal
network. Bench case `kma_context`: grey (the preview fallback) on the previous
DLL, the network's colour now. This was STATUS A17's real cause - the journal
had put it on Houdini's side. Original note:
`render_delegate.cpp:410` lists `kma` in `GetMaterialRenderContexts`;
`material.cpp:2088-2094` reads `cycles`, then `mtlx`, then the universal
network. A Karma Material Builder's `kma` network is never consulted. Add it
after `mtlx` (the nodes are the same MaterialX nodedefs).

### K-17 Colour4 and alpha are dropped throughout — confirmed — partly fixed (0105)
`image_color4.out` becomes `color` (alpha lost), `separate4_color.outa` has
no socket, `combine4_*` drop the fourth input, `constant_vector4` averages.
Acceptable for most networks; should be logged once per material.

0105 fixes the common case: an image's alpha read through `separate4.outa`,
`extract` index 3 or a swizzle `a` - a cut-out driving opacity. When the
separated colour comes straight from an `image_color4`/`tiledimage_color4`,
the reader is wired to the image node's own alpha output
(`bench_mtlx.py` `alpha_*`). Alpha that has gone through any other colour4
node first is still lost, and with it the colour4 compositing nodes.

### K-18 `texcoord.index`, `normal.space`, `tangent.space` ignored — confirmed — **fixed** (0106), index as Karma
Only the first UV set; `normal`/`tangent` are world space while the nodedef
default is object space (differs once the object rotates). Noted in STATUS A11.

Measured against Karma on a sphere turned a quarter turn (`bench_agree.py`
`normal_*`, `position_world`, `tangent_object`): the default object-space
normal came out in world space (ratio 0.57 / 1.71 on the sphere), and a
world-space `position` came out in object space (1.93 / 0.61) - the table
had one lookup per node whatever its `space`. 0106 picks by `space`: object
normal from the texture coordinate node, world position from the geometry
node, object tangent through a vector transform. After: within 5-9 % of
Karma (the tangent within 30 % on its x: a sphere with no UVs has no
authored tangent, and each engine derives one its own way).
`texcoord.index`: Karma reads `st` for index 1 as for 0 - none of `st1`,
`uv1`, `st_1`, `map1` (measured 2026-10-08) - so the delegate already does
what Karma does; a second UV set is read in Houdini through `geompropvalue`
and the primvar's name, which the delegate handles.

### K-58 Hand-built BSDFs: roughness squared twice, dielectric always transmitting — confirmed — **fixed** (0103)
Found with `tools/bench_agree.py` on hand-built networks (`surface` over one
elementary BSDF). The roughness of MaterialX's `conductor_bsdf` and
`dielectric_bsdf` is already the GGX alpha (`mx_conductor_bsdf.glsl` uses it
as such; standard_surface squares its own roughness through
`roughness_anisotropy` before handing it over), and Cycles squares its
`roughness` socket again: a conductor at alpha 0.25 peaked 2.2 times above
Karma. And `dielectric_bsdf` landed on glass_bsdf whatever its
`scatter_mode`, whose default is "R" - reflection only, the coat of a layer
stack: a default dielectric sphere rendered 12 times brighter than Karma's,
the floor showing through. 0103 takes the square root back (a `math` helper)
and picks the dielectric's node by mode: "R" a principled with no diffuse and
no transmission, "T" a refraction_bsdf, "RT" the glass. After: conductor
highlight 0.96 of Karma's, dielectric 1.00, mean 0.89. Materials built from
standard_surface, OpenPBR or the other surface tables were never affected:
they map to the principled directly.

### K-59 Three table translations wrong, found by value cases — confirmed — **fixed** (0104)
Writing the value cases of the nodes added in 0104 turned up three defects of
the existing table, none caught before because no case exercised them:
- `mix` with a factor of its operands' type (`ND_mix_color3_color3` and the
  vector ones) landed on Cycles' mix_color, whose factor is a scalar: the
  colour factor was averaged. Now mix_vector_non_uniform, unclamped.
- `magnitude`, `distance`, `dotproduct` were read on vector_math's `vector`
  output, which is zero for those three - their result is on `value`. All
  three rendered black.
- `generalized_schlick_bsdf`, new in 0104, first wrote its colour to
  `base_color`; metallic_bsdf calls it `color`. Caught by the Karma bench.
`bench_mtlx.py` cases `mix_color_factor`, `scalar_*` failed on 0103 and pass.

### K-61 Twelve translations wrong, found by rendering the whole library against Karma — confirmed — **fixed** (0108)
`tools/mtlx_karma.py` renders one quad per value nodedef (695) with Cycles and
with Karma from the same file, the value shown unlit, and compares the quads.
First run: 563 the same, 36 apart by each engine's own noise, 96 apart. Fixed:
- `rotate2d` / `rotate3d`: `amount` is in degrees and MaterialX turns the
  other way (v' = v * M); read as radians, 0.37 degree turned 21;
- `tangent`: MaterialX's is dP/du of the first UV set, Cycles' geometry
  tangent is radial; now the tangent node in uv_map mode. `bitangent` was
  that same tangent; now N x T;
- a `convert` into or out of a vector2 left its free third component in the
  result (cos(0) = 1 showed in blue); now zeroed;
- `dotproduct`, `distance`, `magnitude`, `normalize` of vector2 counted that
  component: `tiledcircles` rendered black;
- `combine2` into colour4/vector4 from a colour and an alpha went through a
  channel combine: (r, alpha, 0); `combine2_vector4VV` likewise;
- `ifgreater`/`ifgreatereq`/`ifequal` with a boolean output gave nothing;
- `burn` and `dodge` went through Blender's blend modes, which clamp;
  MaterialX does not (nodegraphs the delegate ships, from the GLSL);
- `ramp_gradient` was routed to Cycles' gradient texture, another node; its
  library nodegraph now expands, and `ramp`, built on it, with it;
- with `--closures` (45 BSDF, EDF and surface nodedefs, lit by a white dome):
  every EDF shone ten times too bright - Cycles' emission node defaults its
  strength to 10 - and `generalized_schlick_edf` emitted on its own where it
  only tints the EDF on its `base`. 35 then 38 of 45 the same; `sheen_bsdf`
  remains apart (see K-62), the others are Karma's grey fallback for nodes it
  does not render (`layer` with nothing layered, `measured_edf`, the legacy
  Disney surfaces).
After: 599 the same. The 63 apart are explained: images pointing at a file
that does not exist (Cycles shows magenta, Karma the `default`), a
`geompropvalue` with no primvar, vector4 (K-17), Karma departing from the
library's GLSL (`dodge` gives 1 minus it, `blackbody` 11 times it, vector
`atan2` one channel, emission capped at 20), Houdini and Karma nodes Karma
alone implements. `heighttonormal` (K-12) is fixed in the same patch.

### K-62 `sheen_bsdf` in its default mode has no Cycles counterpart — measured — by design
MaterialX's sheen has two modes. `zeltner` is the model of Cycles' sheen
(`microfiber`), which the translation uses: on the agreement sphere, white,
roughness 0.3, Karma 0.231 against Cycles 0.215 (7 %), both near zero facing
the viewer. `conty_kulla` - the nodedef's default - sends much more light
back towards the viewer: 0.103 at the sphere's centre in Karma, against
0.002 for Cycles' microfiber and 0.003 for its Ashikhmin velvet; sphere mean
0.289. Cycles has no Conty-Kulla sheen, so a default-mode sheen renders
darker facing the camera, right at grazing angles. Measured 2026-10-08; the
`mode` input is reported unmapped when authored.

### K-63 Surface inputs that did nothing, measured input by input against Karma — confirmed — **fixed** (0109)
`tools/surface_audit.py` moves each input of a surface model off its default,
alone, on the agreement sphere, and compares its effect - the change in the
sphere's mean colour - between Cycles and Karma, the input's lobe switched on
where it needs it. First pass, 2026-10-08:
- OpenPBR, 37 inputs: `subsurface_color` had no effect at all (Cycles colours
  diffuse and subsurface with one base colour), and the coat did not darken
  the base: `coat_weight`, `coat_ior` and `coat_darkening` showed a fifth of
  Karma's effect, or none;
- standard_surface, 39 inputs: `coat_affect_color` had no effect;
- glTF, 25 inputs: `alpha` was applied whatever `alpha_mode`, so an OPAQUE
  material (the default) with an alpha below one rendered see-through.
0109 computes the principled's base colour before translation, from the
surface's own inputs, the way the model's nodegraph does (a helper node,
`FoldSurfaceBase` in mtlx_expand.cpp): OpenPBR's subsurface mix and coat
darkening, standard_surface's subsurface mix and coat gamma. glTF picks its
alpha by `alpha_mode` - ignored, cut at `alpha_cutoff`, or passed. After: all
of them within Karma's effect (OpenPBR coat_weight -0.086 against -0.070,
coat_darkening +0.062 against +0.055, subsurface_color and coat_affect_color
alike), and the three alpha modes render as Karma's.

What the audits leave apart, each a difference between the engines' models
rather than a translation: glass (Cycles shows the refracted floor 2.7 times
brighter, so every transmission input's effect is larger), sheen (K-62),
subsurface scattering (twice as marked in Cycles on a 1-unit sphere with a
1-unit mean free path), the diffuse roughness of standard_surface (Oren-Nayar
darkens, Cycles' principled diffuse brightens), the thin film's response, and
`thin_walled` (no Cycles counterpart). Karma itself does not apply several
glTF inputs (`specular`, `ior`, `sheen`, `thickness`...), so glTF is audited
from a grey dielectric and only where Karma reacts.

### K-64 Image nodes routed past their own nodegraphs — confirmed — **fixed** (0109)
`tools/mtlx_karma.py` now gives every `filename` input a texture with one
colour per corner and compares each quad by quarters, so that a texture read
mirrored or shifted shows. Five of the image family went wrong:
- `tiledimage`, the glTF images and `latlongimage` are, in the library,
  nodegraphs around an `image` - tiling and offset, glTF's texture
  transform, the direction to latitude-longitude. The table routed them
  straight to an image node and lost all of it; they expand now;
- `place2d`, which those nodegraphs and many Houdini networks use, went to
  Cycles' mapping node: no pivot, no SRT/TRS order, and the angle read as
  radians where MaterialX gives degrees. Its library nodegraph expands now;
- `image_float` gave the image's colour, averaged by a float socket; it reads
  the first channel, as MaterialX does.
After: 19 of 21 image nodedefs as Karma; `hextiledimage`'s random tiling is
each engine's own.

### K-65 UsdPreviewSurface ignored both its switches — confirmed — **fixed** (0110)
`tools/surface_audit.py UsdPreviewSurface`, 15 inputs against Karma:
- the specular workflow: with `useSpecularWorkflow = 1`, `specularColor` -
  the colour at normal incidence - had no effect, and in the metallic
  workflow, the default, where USD ignores it, it tinted the specular anyway:
  a file writing it black, as many exporters do, lost all reflection;
- `opacityThreshold`: no cut-out.
0110 picks one of four mappings by the two switches. Specular workflow: the
principled's dielectric gets the IOR whose F0 is the colour's largest
component, (1 + sqrt F0) / (1 - sqrt F0), and the colour over it as specular
tint; metallic is ignored. Threshold above zero: opacity at or above it is
opaque, below it transparent. After: `specularColor` red +0.232 against
Karma's +0.196, `opacityThreshold` +0.048 against +0.069. Kept: on the
weak channels of a strong specular colour Cycles takes away more diffuse
than Karma (its energy balance follows the untinted F0), and a partial
`opacity` darkens the sphere slightly in Karma where it lightens it in
Cycles.

### K-66 Texture colour spaces and wrap modes lost on the way — confirmed — **fixed** (0110)
`tools/bench_usdtex.py`, a four-corner texture on a quad through
`UsdUVTexture` and a MaterialX `image`, against Karma, under Houdini's OCIO
config:
- the colour space never arrived. UsdImaging moves `sourceColorSpace` and a
  MaterialX file input's `colorSpace` metadata out of the parameters, into
  the parameter's own colour-space field, which the delegate did not read; and
  the names it did map (`sRGB`, `raw`) were Cycles' builtins, which Houdini's
  config does not know - an sRGB PNG came out linear, 0.90 white where Karma
  decodes 0.79;
- with no colour space at all, the common case, Cycles' image node keeps the
  `scene_linear` its constructor gives it, where USD and MaterialX mean
  `auto` (an 8-bit file read as sRGB);
- `wrapS`/`wrapT` were passed as USD's tokens (`repeat`, `useMetadata`), which
  Cycles' extension enum does not have, so every texture clamped, and USD's
  default (`useMetadata`, black outside the image without metadata) did too.
0110 reads the colour-space field, resolves a name against the active OCIO
config (`ColorSpaceManager::resolve_texture_colorspace`: raw/data, the
config's own sRGB texture space under its usual names, any space the config
knows, linear), starts translated image nodes in `auto`, has `auto` pick the
config's sRGB texture space for a file tagged sRGB, and translates the wrap
tokens (`repeat` → `periodic`, `useMetadata` → `black`). 13 cases (UDIMs
included), all
within 0.011 of Karma.

## B. Geometry and scene

### K-19 float3 primvars copied at the wrong stride — confirmed — **fixed** (0075)
`util.cpp:266-277` (`ApplyPrimvars`) widened every `GfVec3f` to the padded
sixteen-byte `float3` before copying, while `Attribute::data_sizeof()` returns
`sizeof(packed_float3)`, twelve bytes, since Cycles moved its attributes to the
packed type. The copy ran at the wrong stride and four bytes per element past
the buffer. Every per-vertex colour or vector a shader read was garbage: a
constant `(0.2, 0.6, 0.9)` displayColor came back `(0.47, 0.38, 0.47)` through
the native `attribute` and `vertex_color` nodes alike. UVs (float2) and
normals (their own path) were unaffected, which is why it went unseen.
Upstream bug; a `GfVec3f` is exactly a `packed_float3`, so the array is now
copied as is. The 97-node references rendered before this fix are wrong for
every node that reads a vector primvar.

### K-20 Curve type, basis and wrap are ignored — confirmed — **fixed** (0081)
`curves.cpp:221-233` read `type`, `basis`, `wrap`, use them only to size the
topology, then hand every key to Cycles, which evaluates a Catmull-Rom through
all keys. Bézier control points are treated as on-curve points, `periodic`
curves are open, `curveIndices` (indexed curves) index the wrong points. Houdini
hair (linear or `catmullRom`, non-indexed) is fine; other DCCs' curves are not.
Fix: convert Bézier/B-spline to Catmull-Rom keys, close periodic curves,
expand indices.

Fixed 2026-10-07: every curve that is not an open, non-indexed polyline is
resampled into keys, each a weighted sum of up to four USD points (Bézier and
B-spline evaluated, open Catmull-Rom without its tangent points, periodic
closed, pinned reaching its ends), applied to points, motion samples, widths
and primvars. `tools/bench_curves.py` holds five cases. Indexed curves are
handled but untested: UsdGeomBasisCurves has no index attribute, only Hydra
producers hand topology indices over.

### K-21 `widths` with `varying` interpolation are ignored — confirmed — **fixed** (0081)
`curves.cpp:139` and `pointcloud.cpp:135` handle `constant` and `vertex` only.
USD cubic curves commonly author `varying` widths; the radius stays
uninitialised. `varying` on a cubic curve has one value per segment end:
resample to keys.

Fixed 2026-10-07: varying values are blended per key between the two nearest
segment ends; points read varying widths as per-point widths.

### K-22 Hair shape is fixed to ribbons — confirmed — **mostly fixed** (0081)
`session.cpp:62` passes a default-constructed `SceneParams`: `hair_shape = CURVE_RIBBON`,
`hair_subdivisions = 3`, `shadingsystem = SVM`, `texture_limit = 0`. None is
exposed. Thick 3D curves (`CURVE_THICK`) matter for yarns and for OptiX's
hardware curve intersection. Expose `cycles:hair_shape` and
`cycles:hair_subdivisions`; they are session-creation parameters like `device`,
so they need the same late-setting warning.

Fixed 2026-10-07 for the shape: in this Cycles the shape is per `Hair`
(`Hair::curve_shape`), not a session parameter, so `cycles:curve_shape`
(auto, thick, ribbon) changes live and reshapes the curves already synced.
`auto`, the default, renders linear curves as exact thick polylines and cubic
ones as round tubes; upstream rendered ribbons. Thick curves are open tubes:
seen exactly along their axis they show nothing. Still open:
`hair_subdivisions` and the other `SceneParams`.

### K-23 Instances never blur — confirmed — **fixed** (0082)
`instancer.cpp:58-60` read instance primvars at time 0. A PointInstancer with
animated positions renders sharp while its prototype blurs. Sample the
instance primvars at the three shutter times like `geometry.inl` does for the
prim transform.

Fixed 2026-10-07: the instancer reads its arrays and its own transform at any
shutter offset, parents included; each instance gets three motion steps.
Instances born or dying inside the shutter stay sharp. `tools/bench_motion.py`
measures the trail of a transform, deforming points, instance positions and
an instancer transform (6 cases).

### K-24 No light linking or shadow linking — confirmed — **fixed** (0089)
No code reads Hydra categories (`HdCategoriesSchema`, `lightLink`/`shadowLink`
collections). Cycles supports it since 4.0 (`Object::light_set_membership`,
`Light::light_set_membership`, `shadow_set_membership`).

Fixed 2026-10-08: Hydra's light linking scene index is registered for
Cycles; the session turns categories into light and shadow sets (one per
distinct combination of linked categories, at most 63). Measured in
`bench_settings.py` (`light_link`, `shadow_link`). Light filters and
per-instance categories are not handled.

### K-25 Five passes only — confirmed — **fixed** (0087, 0092, 0094)
`session.cpp:21` maps color, depth, normal, primId, instanceId and the Houdini
spellings `C`, `Cf`, `N`, `P`, `Pz`. No diffuse/glossy/transmission direct or
indirect, emission, AO, shadow catcher, mist, position, UV, motion vectors,
cryptomatte, denoising albedo/normal, light groups, or shader AOVs
(`aov_output` nodes exist but no RenderVar can select them). A RenderVar with
any other name logs "Unknown pass" and is dropped.

Fixed 2026-10-07. A render var resolves by its name (`C`, `Pz`, Cycles names,
Karma names), then by its `sourceName`/`sourceType` (raw names, Karma's
`ray:hit*`, Karma's light path expressions for its components, `st`), else
it is a shader AOV named after its source. Karma names and LPEs are
multiplied back by the colour pass (Cycles divides light passes by the
surface colour, Karma does not). One pass per Cycles type: two of a type
under different names stayed apart in the film and one read black.
`CryptoObject/Material/AssetNN` enable cryptomatte; objects and materials now
carry names to hash. `aov_output` has a pass-through `surface` → `closure`
so Hydra keeps it. The cryptomatte name, hash, conversion and manifest reach
the EXR header through the render stats husk copies there (0094). Still
missing: arbitrary LPEs (Cycles has no LPE engine: unknown ones are reported, black).
Light groups since 0092: `lightgroup:<name>` or Karma's `C.*<L.'tag'>`, lights
grouped by `cycles:lightgroup` or Karma's LPE tag.

### K-26 No transparent background with a dome light — confirmed — **fixed** (0086)
`session.cpp:137-150`: `background->set_transparent(true)` only when no
background light exists. With a dome light the alpha is opaque and there is no
setting to change it. Expose film transparency (`Background::transparent`,
`transparent_glass`, `transparent_roughness_threshold`) as render settings.

Fixed 2026-10-07: `cycles:film:<socket>` and `cycles:background:<socket>`
reach those nodes by name. Unset, the film is transparent when the dome is
not seen by the camera; the dome's ray visibility now reaches the background
(it went to the light's object, which camera rays never look at), and a dome
is camera-visible by default. `cycles:film:exposure` is a linear multiplier.

### K-27 Nothing is read per object — confirmed — **fixed** (0088)
`geometry.inl:231` sets `PATH_RAY_VISIBILITY_ALL` or 0. No per-prim ray
visibility, holdout, shadow catcher, light group, caustics caster/receiver,
shadow terminator offset, per-object dicing rate or `use_adaptive_subdivision`.
Karma reads `primvars:karma:object:*`; the equivalent `primvars:cycles:object:*`
does not exist.

Fixed 2026-10-08: `primvars:cycles:object:*` (ray visibility per type,
holdout, shadow catcher, caustics, light group, shadow terminator, dicing
rate) and Karma's `rendervisibility` expressions and `holdoutmode`; shown by
the Render Geometry Settings LOP through `HdCyclesPlugin_Geometry.ds`. The
approximate shadow catcher reports about 0.2 alpha where the plane loses half
its light under a dome. Left: changing the render settings' dicing rate
overwrites per-prim rates until those prims sync again; light groups have no
pass yet.

### K-28 Render tags and purposes are not honoured — **fixed** (0090)
`render_pass.cpp:99` ignores `renderTags`; rprims never check their tag. A
prim with `purpose = proxy` and its `render` sibling both render. To be
confirmed in Solaris with a proxy/render pair.


Checked 2026-10-08: under husk the proxy and guide prims were never rendered
(Hydra does not sync them). In the viewport an already built prim stayed when
its purpose was turned off; 0090 hides and shows prims as the render tags
change. Confirmed by the user in Houdini (`tests/houdini/purpose_toggle.hip`):
each purpose toggle shows and hides its object.

### K-29 `background = false` under husk — confirmed — **measured, not a cause**
`render_delegate.cpp:90` builds every session in interactive mode, batch
included: no tiling, progressive buffer updates, `use_auto_tile` inert.
Upstream does the same, but it is a candidate for the batch-speed gap against
Karma and must be measured (same scene, `background` true vs false).

Measured 2026-10-08, `smoke.usda` at 1920x1080, five alternating pairs:
13.6 s interactive, 13.2 s background, a spread of 1.5 s between runs, images
bit-identical. Not the batch-speed gap; the session stays interactive.

### K-30 Subdivision depends on a display hint — confirmed — **fixed** (0084)
`mesh.cpp:478-485` only subdivide when `refineLevel > 0`, and `mesh.cpp:704`
sets the maximum dicing level *to* `refineLevel`. That value is Hydra's
display complexity (`husk --complexity`, 0-3; Solaris display options), not a
property of the mesh. A `catmullClark` mesh should subdivide regardless, with
a render setting for the max level (Blender: 12) and the display hint left to
the viewport.

Fixed 2026-10-07: `catmullClark` always subdivides, capped by
`cycles:max_subdivisions` (12); bilinear still waits for the hint. husk's
default complexity already set a refine level, so batch renders looked right
before; the viewport at low complexity rendered the cage.

### K-31 Four seconds unexplained in the render pass — **closed** (2026-10-08, confirmed by the user)
The stopwatch reported `camera et AOV 4033.6 ms, verrou 0, relance 0.005`.
That bucket (`render_pass.cpp`, between `tPolled` and `tCamera`) holds only
AOV binding comparison, `set_full_width/height`, `ApplyCameraSettings`, the
dicing-camera copy and a pointer compare. None of it should take 4 s. Since
0076 the log line (`Render pass: ... (lock, COP poll, AOV bindings, camera,
dicing camera, reset, start)`) splits that stretch three ways.

Live reading, 2026-10-08, with 0099 in a Houdini driven through
`tools/hou_remote.py` on `test_hydra_solaris.hipnc` (Cycles GPU, 856×752 and
1590×752): scene edits, free-camera moves, a switch to the USD camera and
back, `Houdini GL` → `Cycles GPU`, six `Restart Render` (each rebuilds the
delegate: new `Display:` line, full resync), pause/unpause, a window resize,
a flipbook - about 45 session restarts in all. **Not one `Render pass` line**:
the host thread never spent 50 ms in `_Execute`. After a camera change the
restart line came 0.17 s later and the first sample 0.05 s after that. The
reading predates 0076-0099, which removed several per-edit costs (dicing
camera at identity, COP read twice, unconditional scene lock); whichever held
the 4 s, it is not there now. Open only until the user confirms by hand: with
`launch_cycles_log.cmd` the log lines carry seconds since start (0100), so a
slow start reads as the gap between `Render restarted` and `Rendered 1
samples`, with no stopwatch. Note for the next driver: a camera set from
Python (`setDefaultCamera`) reaches Hydra only when the viewport actually
repaints, one move in six here; the mouse does not have that problem.

Confirmed by the user the same morning, mouse in hand, on his scene through
`launch_cycles_log.cmd` ("it feels fast"): 871 session restarts in 22 minutes,
first sample a median 19 ms after the restart line (184 ms at worst, on a
camera switch), and still not one `Render pass` line. Closed; the timestamped
log stays, so a regression would read at once.

### K-32 The pass takes the scene lock unconditionally — by design, with a cost — **fixed** (0096), unmeasured live
`render_pass.cpp:125` (`scene->mutex.lock()`, patch 0014). While the render
thread holds the lock in `device_update`, Houdini's UI thread waits. The
try-lock it replaced dropped edits. A middle path: try-lock, and when it fails
mark the pass dirty so Hydra calls `_Execute` again next frame.


Fixed 2026-10-08: try-lock; a busy scene marks the pass unconverged so Hydra
executes it again next redraw (everything is recomputed from the pass state);
after 10 deferrals in a row it waits. To be felt in Houdini.

### K-33 Houdini volume field names — confirmed — **fixed** (0086)
`volume.cpp:55-70` recognise `density`, `color`, `flame`, `heat`,
`temperature`, `velocity`. Houdini writes `vel` and `Cd`. Only `density`
matches; the rest become named attributes a native shader can still read, but
`ATTR_STD_VOLUME_VELOCITY` (motion blur) is never set.

Fixed 2026-10-07: `vel`/`v` alias velocity, `Cd` aliases colour; a shader
asking for `Cd` by name still gets it. Measured: a red `Cd` grid read by a
principled volume under `color` renders red (grey before).

### K-34 Motion blur toggle only turns off — confirmed — **fixed** (0086)
`render_delegate.cpp:587-597`: `disableMotionBlur`/`instantaneousShutter`
true disables; false does nothing. In a live session the blur never comes back
until the delegate is recreated.

Fixed 2026-10-07: both flags tracked; blur is on when neither is set, and
prims synced without it or over another shutter are synced again. Batch
behaviour measured (`bench_settings.py`). In Houdini (2026-10-08, user,
`tests/houdini/motion_toggle.hip`) the blur came back, but turning it off made
the moving object vanish until the render was restarted: prims kept their
motion samples. Patch 0091 resyncs them on the way off too - to recheck.

### K-57 An attribute whose value failed to parse segfaulted the delegate — confirmed — **fixed** (0102)
`tests/scenes/bad_normals_type.usda`: a mesh whose `normals` is declared
`normal[]` - not a USD type name - keeps its literal as an
`Sdf.UnregisteredValue`, and Hydra hands the delegate an **empty**
`VtVec3fArray`: the type test passed, the size check was a `TF_VERIFY`, which
reports and carries on, and the loop read `normals[i]` past the end. husk
died with a segmentation fault; Karma renders the file and ignores the
attribute. The same pattern stood on the mesh's points and on a point cloud's
widths. Each now checks the count its interpolation needs before reading,
warns and skips the attribute (the points: the mesh). `tools/bench_robust.py`
renders three such files (`tests/scenes/bad_*.usda`): all three crashed with
0101, all three render with 0102. Curves were already guarded.

### K-67 Dome light texture lying on its side — confirmed — **fixed** (0111)
`tools/bench_dome.py`, a lat-long texture with one colour per quarter of the
horizon and a white top, on a dome seen by a camera in six directions,
against Karma. USD's dome follows OpenEXR's lat-long convention: top pole
+Y, longitude 0 towards +Z, pi/2 towards +X. The delegate handed the dome's
transform to Cycles' environment texture, whose map has its pole on +Z and
longitude 0 on +X: the sky stood on the horizon, Houdini's -Z view showed
the pole, and every direction differed from Karma. An HDRI lit the scene
from the wrong side too. A fixed axis permutation now follows the dome's
transform. `DomeLight_1`'s `poleAxis` (a Z-up stage) was ignored as well:
UsdImaging hands its rotation over as the light's `domeOffset`, now applied
under the transform. 11 directions, Y-up and Z-up, match Karma.
Kept: at the exact poles Cycles' map wraps vertically, blending the first
and last rows within half a texel - invisible on a real HDRI, visible on the
bench's 8-row texture, so the bench checks the poles at 75 degrees.

### K-68 Rect light texture mirrored — confirmed — **fixed** (0112)
`tools/bench_rect.py`, the four-corner texture on a 2 x 2 rect light seen
head-on from its emitting side, against Karma. USD puts the texture's min
corner at the light's (+X, +Y); Cycles' parametric u runs the other way
along X, and the delegate read the image with it as is: the texture came out
mirrored left to right, in the camera's view and in the light it casts. The
image is now read at (1 - u, v). Both cases (plain, turned a quarter about
the light's axis) match Karma within 0.003.

### K-69 Spot softness and emission focus off Karma — confirmed — **fixed** (0112)
`tools/bench_lights.py`, a white floor under one light per case, its
radiance under the light and 1 to 3 units aside, against Karma: sphere,
disk, rect, cylinder, distant, normalized or not, exposure and colour
temperature all agreed within 3 % (cylinder within 7 % at the far edge).
Two did not:
- `shaping:cone:softness` went to Cycles' spot `smooth` as is. USD smooths
  over the angle, from cutoff x (1 - softness) to the cutoff; Cycles over the
  cosine, over `smooth` of (1 - cos cutoff), a narrower penumbra: 28 % too
  bright inside it. The softness is now converted so both ramps start at the
  same angle (ratio 1.01). Softness without a cone angle took Cycles' 45
  degree default; it now takes USD's 90. Karma seems to ignore a softness
  without an angle (Houdini's Light LOP always writes one): there the
  delegate follows the USD formula, Karma does not.
- `shaping:focus` and `focusTint` were ignored, the light 3 times too bright
  3 units aside. The light shader now multiplies the emission by
  lerp(focusTint, 1, |direction . axis| ^ focus): within 3 %, tinted too.
`tools/bench_lights.py`: 15 cases, all within 10 % (most within 1 %).

### K-70 IES profiles blurred, scaled and never normalized — confirmed — **fixed** (0113)
`tools/bench_lights.py`, IES profiles on a small sphere light over the
floor, against Karma, which follows USD's formula (emission x the profile's
candela value; with `shaping:ies:normalize`, over the profile's mean
intensity):
- the profile was read along the texture coordinate's normal, which on a
  sphere light is the normal of the point sampled on the sphere - it sweeps
  the whole visible side, so the profile came out blurred, its peak halved;
- Cycles reads candela values times 4 pi / 177.83 (a radiometric
  conversion), 30 times below Karma with the blur;
- `normalize` and `angleScale` were ignored;
- the horizontal angle ran from the light's -Y where Karma's runs from -X.
The profile is now read along the emission direction in the light's frame
(the shading point's incoming direction through the light's baked axes, x
and y swapped), angleScale remaps the angle off the axis as USD says, and
the IES node's strength undoes Cycles' conversion, or divides by the
profile's mean (each patch's corners weighed by its solid angle over the
solid angle covered, as Karma does - `IESFile::mean_intensity`). Four cases
(plain, normalized, angle-scaled, asymmetric) within 5 % of Karma. Kept:
Cycles interpolates the profile cubically, Karma linearly - visible only on
coarse profiles (a 30 degree step: 20 % off the lobe), not on 5 degree ones.

### K-71 Camera exposure ignored — confirmed — **fixed** (0114)
`tools/bench_camera.py`, small white unlit squares seen by one camera per
case, their centroids, spread and total light against Karma: framing,
aperture offsets, depth of field, orthographic projection and images whose
aspect differs from the aperture's all agreed within a pixel. The camera's
`exposure` (USD's log2 scale, with ISO, time and f-stop folded by Hydra into
a linear exposure scale) did not reach the image: `exposure = 1` left it as
it was where Karma doubles it. The film's exposure is now the render
settings' (`cycles:film:exposure`) times the camera's scale, each side
keeping its own so neither overwrites the other; the free view counts 1.

### K-72 Subdivision tags lost: creases, corners, boundaries, holes — confirmed — **fixed** (0115)
`tools/bench_subdiv.py`, a Catmull-Clark cube and an open grid, white and
unlit, silhouettes compared pixel by pixel with Karma. Only the untagged
cube agreed:
- the subdivision tags were read from the prim's root, where Hydra does not
  put them (they live in the mesh's container): every crease and corner was
  lost, an all-creased cube came out as the rounded blob;
- read from the right place, the sharpness would have gone to Cycles as is,
  where Cycles multiplies its 0-1 weight by 10 for OpenSubdiv: now divided
  by 10;
- corners were only read when the mesh also had creases;
- `interpolateBoundary` and `faceVaryingLinearInterpolation` never reached
  Cycles' mesh, which has both;
- `holeIndices` were ignored on subdivided meshes (a TODO). Cycles' mesh now
  carries a hole per face, which the dicing skips while OpenSubdiv still
  shapes the neighbours with it, as USD's holes mean.
Also in Cycles itself: `Mesh::clear` kept the vertex creases, which piled up
on every topology rebuild. All seven cases within 0.2 % of Karma's pixels.

## C. Houdini side

### K-40 `op:` textures fail under husk — confirmed
`houdini_cop.cpp` needs `hou.node()` on a live session; husk has no node
graph, so the capture warns and the texture is missing. `flatten_op_textures`
exists; nothing runs it automatically when a USD Render ROP is used.

Documented 2026-10-08 in the README, under the COP feature: under husk, put
the Flatten COP Textures LOP (`hdcycles::flatten_op_textures`) before the render node. Not automated.

### K-41 COP pixel cache never evicts — confirmed — **fixed** (0096), unmeasured live
`houdini_cop.cpp` `Cache()` keeps every captured layer for the session: an 8K
RGBA half layer is 536 MB of host memory per COP, on top of Cycles' own copy.


Fixed 2026-10-08: entries no material uses leave the cache when their last
user is forgotten, and over a budget (`HDCYCLES_COP_CACHE_MB`, 4096 MB).

### K-42 The preview translator stops at one image — by design
`cycles.py` follows one relay chain per input. A `mix_color` of two textures,
a procedural, or a ramp show as the default value. Acceptable, but the README
should not imply the viewport is "linked" to the Cycles nodes.

Stated in the README since 2026-10-08.

## D. Repository and tests

### K-50 Benches overwrite their own references — confirmed — **fixed** (2680470)
`tools/bench_render.py` wrote to `tests/usd/bench-53/images/` (today `tests/nodes/5.3/references/`), the directory
git tracked as references, and `bench_diff.py` compared against `_baseline.exr`
only. Now `references/` is tracked, `output/` is ignored, and `bench_diff.py`
compares the two with a tolerance and moves a reference only on `--accept`.

### K-51 Coverage counts prefixes — confirmed — measured
`tools/mtlx_coverage.py` resolves a nodedef as "covered" when any table prefix
matches it. K-03, K-05 and K-07 are all counted as covered. The README's
"652/823" is a routing number. `tools/mtlx_inputs.py` (2026-10-07) renders
every routed nodedef with all its inputs authored and sorts the delegate's
warnings per nodedef. First measurement, after 0076:

| | |
|---|---|
| routed | 652 |
| clean - every input, output and node found | **511** after 0076, **528** after 0078 |
| inputs dropped | 124 (many are inputs with no Cycles counterpart: image `default`, `framerange`, `layer`; others are real, see K-05, K-14) |
| output not found | 15 after 0076 (the closure families, K-03), **0** after 0078 |
| node missing | 6 after 0076 (every VDF, through the missing `volume`, K-04), **0** after 0078 |

A third number, value-verified by rendering against the MaterialX
definition, is `bench_mtlx.py`'s case count: 16.

2026-10-08, after 0098 (nodegraph expansion, `tools/mtlx_rules.py` shared by
both tools): routed **775**, clean **636**, inputs dropped 139, outputs and
nodes missing 0; `bench_mtlx.py` 49 cases. The 31 families still out:
matrices (`transformmatrix`, `creatematrix`, `invertmatrix`, `transpose`,
`determinant`), the colour4 compositing nodes (`over`, `in`, `out`, `mask`,
`matte`, `premult`, `disjointover`...), `time`, `frame`, `curveadjust`,
`splitlr`/`splittb` of colour4 and vector4, `blur`, and the BSDF helpers
(`artistic_ior`, `roughness_*`, `thin_film_bsdf`, `generalized_schlick_bsdf`,
the Disney BSDFs, `thin_surface`).

2026-10-08 evening, after 0104: **789** of 822 rendered (80 expanded, 43
rewritten, 666 table), routed 782, clean **641**, `bench_mtlx.py` **64**
cases. Brought in: `artistic_ior`, `roughness_anisotropy`, `roughness_dual`
and through it `glossiness_anisotropy`, `inside`/`outside` of float and
colour3 - nodegraphs the delegate ships itself (`mtlx_nodegraphs.h`), each
transcribing the library's GLSL; `transformmatrix` of vector2/vector3 with a
constant matrix (dot products) and through it `hmtlxcomplementcolor`;
`generalized_schlick_bsdf` (Cycles' F82 metal); the legacy Disney surfaces
(on `disney_principled`). The 18 families still out: the other matrix nodes
(`creatematrix`, `invertmatrix`, `transpose`, `determinant`) and a connected
matrix, the colour4 compositing nodes (`over`, `in`, `out`, `mask`, `matte`,
`premult`, `unpremult`, `disjointover`, and the colour4 `inside`/`outside` -
they need the alpha K-17 drops), `time`, `frame`, `curveadjust`,
`thin_film_bsdf`, `thin_surface`, `hextilednormalmap`.

Later the same evening, after 0105: **796** of 822. `thin_film_bsdf` (1.38)
is folded onto the base BSDF of its `layer` - the 1.39 `thinfilm_*` inputs,
which render identical to it; `curveadjust` passes its input through, as its
only implementation in the library (MDL) does - no renderer implements the
knots. Still out: `time` and `frame` (nothing gives the delegate the current
frame, and a material is not re-synced per frame), the matrix nodes other
than a constant `transformmatrix`, the colour4 compositing nodes,
`thin_surface`, `hextilednormalmap`.

### K-52 Bench expected values derived from the code — confirmed — **fixed**
`tools/bench_mtlx.py` now computes every expected colour from the MaterialX
source expression or nodegraph, with the file named next to the formula, and
carries `mix`, `plus`, `saturate`, `geomcolor` and `facingratio` cases. Five of
them failed on the old DLL and pass on the new one.

### K-53 Code and log messages in French — confirmed — **fixed** (0097)
`material.cpp` (180 lines), `houdini_cop.cpp` (62), `render_pass.cpp` (47),
`mesh.cpp` (24) and others carry French comments; four `LOG_INFO` lines are
French (`Affichage :`, `Rendu relance :`, `Passe de rendu :`, in
`render_pass.cpp:64,241,283`). The project rule is English in code; the repo
is public and the patches are meant for upstream.

Fixed 2026-10-08: every comment and log line of `src/hydra` and every comment,
docstring and message of `tools/*.py` is English (`Display:`, `Render
restarted:`, `Render pass:`). A comment-stripping comparison against the
previous revision showed no code change. The journal (`docs/STATUS.md`) stays
French by design.

### K-54 README numbers disagree — confirmed — **fixed**
`hython tools/count_nodes.py` derives them all from the Sdr registry: 163
published, 64 `convert_*` hidden, 99 exposed as VOPs (plus the generated
`cycles_material` terminal makes the 100 of CYCLES_VOPS.md), 97 probed by the
bench (99 minus `cycles_output` and `cycles_aov_output`). STATUS.md's 161 was
the 5.2 count.
