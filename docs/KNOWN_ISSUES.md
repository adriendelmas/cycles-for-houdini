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

### K-12 `heighttonormal` outputs a world normal — probable
`material.cpp:1149` maps it to `bump`, whose output is a shading normal.
MaterialX outputs a tangent-space normal *map* (`(0.5, 0.5, 1)` when flat)
meant for a following `normalmap`. The chain `heighttonormal → normalmap`
therefore breaks. Either detect the chain and collapse it, or build the
tangent map from `bump` − N through a `vector_transform` to tangent space.

### K-13 `conductor_bsdf` loses its colour — confirmed — **fixed** (0078)
Now `metallic_bsdf` in `physical_conductor` mode with `ior` and `extinction`
carried, MaterialX's gold as default. Not yet value-tested against a
reference. Original note:
`material.cpp:1250` maps to `glossy_bsdf` and leaves `ior`/`extinction`
unmapped: every conductor is white. Cycles 4.3+ `metallic_bsdf` with
`fresnel_type = physical_conductor` takes exactly `ior` and `extinction`.

### K-14 Approximate closures without a note in the log — probable
`dielectric_bsdf`: `tint` and `scatter_mode` (R-only coats become glass with
transmission) unmapped. `subsurface_bsdf`: `anisotropy` unmapped.
`absorption_vdf.absorption` is a coefficient, Cycles `absorption_volume.color`
is a transmittance. `ambientocclusion.coneangle → distance` is not the same
quantity. All render *something*; none say they are approximate.

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

### K-17 Colour4 and alpha are dropped throughout — probable
`image_color4.out` becomes `color` (alpha lost), `separate4_color.outa` has
no socket, `combine4_*` drop the fourth input, `constant_vector4` averages.
Acceptable for most networks; should be logged once per material.

### K-18 `texcoord.index`, `normal.space`, `tangent.space` ignored — probable
Only the first UV set; `normal`/`tangent` are world space while the nodedef
default is object space (differs once the object rotates). Noted in STATUS A11.

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

### K-24 No light linking or shadow linking — confirmed
No code reads Hydra categories (`HdCategoriesSchema`, `lightLink`/`shadowLink`
collections). Cycles supports it since 4.0 (`Object::light_set_membership`,
`Light::light_set_membership`, `shadow_set_membership`).

### K-25 Five passes only — confirmed
`session.cpp:21` maps color, depth, normal, primId, instanceId and the Houdini
spellings `C`, `Cf`, `N`, `P`, `Pz`. No diffuse/glossy/transmission direct or
indirect, emission, AO, shadow catcher, mist, position, UV, motion vectors,
cryptomatte, denoising albedo/normal, light groups, or shader AOVs
(`aov_output` nodes exist but no RenderVar can select them). A RenderVar with
any other name logs "Unknown pass" and is dropped.

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

### K-27 Nothing is read per object — confirmed
`geometry.inl:231` sets `PATH_RAY_VISIBILITY_ALL` or 0. No per-prim ray
visibility, holdout, shadow catcher, light group, caustics caster/receiver,
shadow terminator offset, per-object dicing rate or `use_adaptive_subdivision`.
Karma reads `primvars:karma:object:*`; the equivalent `primvars:cycles:object:*`
does not exist.

### K-28 Render tags and purposes are not honoured — probable
`render_pass.cpp:99` ignores `renderTags`; rprims never check their tag. A
prim with `purpose = proxy` and its `render` sibling both render. To be
confirmed in Solaris with a proxy/render pair.

### K-29 `background = false` under husk — confirmed
`render_delegate.cpp:90` builds every session in interactive mode, batch
included: no tiling, progressive buffer updates, `use_auto_tile` inert.
Upstream does the same, but it is a candidate for the batch-speed gap against
Karma and must be measured (same scene, `background` true vs false).

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

### K-31 Four seconds unexplained in the render pass — measured, unresolved
The stopwatch reported `camera et AOV 4033.6 ms, verrou 0, relance 0.005`.
That bucket (`render_pass.cpp`, between `tPolled` and `tCamera`) holds only
AOV binding comparison, `set_full_width/height`, `ApplyCameraSettings`, the
dicing-camera copy and a pointer compare. None of it should take 4 s. Since
0076 the log line (`Render pass: ... (lock, COP poll, AOV bindings, camera,
dicing camera, reset, start)`) splits that stretch three ways; the next
reading in a live Houdini session will name the call. Needs the user's
viewport scene; cannot be reproduced under husk.

### K-32 The pass takes the scene lock unconditionally — by design, with a cost
`render_pass.cpp:125` (`scene->mutex.lock()`, patch 0014). While the render
thread holds the lock in `device_update`, Houdini's UI thread waits. The
try-lock it replaced dropped edits. A middle path: try-lock, and when it fails
mark the pass dirty so Hydra calls `_Execute` again next frame.

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
behaviour measured (`bench_settings.py`); the live toggle needs Houdini.

## C. Houdini side

### K-40 `op:` textures fail under husk — confirmed
`houdini_cop.cpp` needs `hou.node()` on a live session; husk has no node
graph, so the capture warns and the texture is missing. `flatten_op_textures`
exists; nothing runs it automatically when a USD Render ROP is used.

### K-41 COP pixel cache never evicts — confirmed
`houdini_cop.cpp` `Cache()` keeps every captured layer for the session: an 8K
RGBA half layer is 536 MB of host memory per COP, on top of Cycles' own copy.

### K-42 The preview translator stops at one image — by design
`cycles.py` follows one relay chain per input. A `mix_color` of two textures,
a procedural, or a ramp show as the default value. Acceptable, but the README
should not imply the viewport is "linked" to the Cycles nodes.

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

### K-52 Bench expected values derived from the code — confirmed — **fixed**
`tools/bench_mtlx.py` now computes every expected colour from the MaterialX
source expression or nodegraph, with the file named next to the formula, and
carries `mix`, `plus`, `saturate`, `geomcolor` and `facingratio` cases. Five of
them failed on the old DLL and pass on the new one.

### K-53 Code and log messages in French — confirmed
`material.cpp` (180 lines), `houdini_cop.cpp` (62), `render_pass.cpp` (47),
`mesh.cpp` (24) and others carry French comments; four `LOG_INFO` lines are
French (`Affichage :`, `Rendu relance :`, `Passe de rendu :`, in
`render_pass.cpp:64,241,283`). The project rule is English in code; the repo
is public and the patches are meant for upstream.

### K-54 README numbers disagree — confirmed — **fixed**
`hython tools/count_nodes.py` derives them all from the Sdr registry: 163
published, 64 `convert_*` hidden, 99 exposed as VOPs (plus the generated
`cycles_material` terminal makes the 100 of CYCLES_VOPS.md), 97 probed by the
bench (99 minus `cycles_output` and `cycles_aov_output`). STATUS.md's 161 was
the 5.2 count.
