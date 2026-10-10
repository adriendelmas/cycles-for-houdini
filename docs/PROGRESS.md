# Progress

The current state, feature by feature, as the code stands on 2026-10-07 -
established by reading the sources, not the earlier claims. Each line says
how it was verified; "code read" means nobody has rendered it yet.

Legend: ✅ works and verified · 🟡 partial or approximate · ❌ missing · 🐞 wrong (see [KNOWN_ISSUES.md](KNOWN_ISSUES.md))

## Geometry

| Feature | State | Verified by | Notes |
|---|---|---|---|
| Polygon meshes, triangulation, primvars | ✅ | 97-node bench, user scenes | |
| Per-vertex colours and vector primvars | ✅ | `geomcolor` bench case exact | Garbage until 2026-10-07 (K-19, patch 0075) |
| Face-varying (corner) normals | ✅ | bit-identical vs per-point normals | |
| Smooth/flat from authored normals | ✅ | measured | |
| Catmull-Clark subdivision, creases, corners, boundary rules | ✅ | `bench_subdiv.py` 7/7 vs Karma | Always for `catmullClark`, capped by `cycles:max_subdivisions` (K-30, 0084); the tags were never read before 0115 (K-72) |
| Adaptive dicing rate, dicing camera | ✅ | 10.3 M → expected triangle counts | Setting `cycles:dicing_rate`, clamped ≥ 0.1 |
| Holes on subdivided meshes | ✅ | `bench_subdiv.py` | Not diced, still shaping the neighbours (K-72, 0115) |
| Left-handed subdivided meshes | ✅ | `bench_subdiv.py`, `bench_usdtex.py` | Faces reversed for Cycles, corner primvars with them (K-76, 0118) |
| Geom subsets (per-face materials) | ✅ | upstream | Face sets only |
| Transform motion blur | ✅ | 179 px blur measured | 3 steps, evenly spaced |
| Deformation blur (sampled points) | ✅ | measured, mesh/curves/points | |
| Velocity / acceleration blur | ✅ | 242 px measured | fps from scene globals, fallback 24 |
| Corner normals under motion blur | 🟡 | upstream behaviour | Cycles drops them; smooth flag takes over |
| Curves: every USD basis and wrap | ✅ | `bench_curves.py` 5/5 | Bézier, B-spline, Catmull-Rom, periodic, pinned resampled to keys (K-20, 0081); indexed handled, untestable from a file |
| Curves: `widths` `varying` | ✅ | `bench_curves.py` | Blended per key (K-21, 0081) |
| Thick 3D curves | ✅ | rendered, end-on test | `cycles:curve_shape` auto/thick/ribbon, live; default auto = thick (K-22, 0081) |
| Points | ✅ | `bench_points.py` 5/5 vs Karma | `varying` widths read as per-point (0081); no widths: width 1 as Hydra and Karma (K-74, 0117) |
| Point instancer, nested instancers | ✅ | phase 3 | |
| Instance motion blur | ✅ | `bench_motion.py` 6/6 | Positions and instancer transform sampled over the shutter (K-23, 0082) |
| Per-instance primvars | ✅ | `bench_instances.py` 5/5 | `instance` primvars as object attributes, nested instancers, `displayColor` → Object Info colour (0082) |
| Constant scalar primvars (`float x = 0.5`) | ✅ | rendered | Read uninitialised memory before 0082; doubles and ints now converted |
| Implicit surfaces (Sphere, Cube...) | ✅ | `bench_implicit.py` 6/6 | Our scene index meshes them, 64 segments, smooth normals (A1, 0083) |
| OpenVDB volumes | ✅ | phase 5, `bench_settings.py` | `openvdbAsset` only; Houdini `vel`/`Cd` aliased (K-33, 0086) |
| Volume step size, object space, velocity scale per prim | ✅ | `bench_settings.py` | `primvars:cycles:volume:*`; volumes read their primvars since 0125 (K-85); no clipping in Cycles 5.3 |

## Lights and camera

| Feature | State | Verified by | Notes |
|---|---|---|---|
| Rect, disk, sphere, spot, distant, dome | ✅ | `bench_lights.py` 24/24 vs Karma | Units measured per type; spot softness converted from USD's angle to Cycles' cosine (K-69, 0112) |
| Agreement with Karma on materials | ✅ | `bench_agree.py` 21/21 | Diffuse, dielectric, metal, glass, coat, emission, preview surface: floor to 1 %, spheres to 25 %, glass loose (2026-10-08) |
| Cylinder light | 🟡 | 0.95 of Karma | Rectangle approximation, one-sided |
| IES profiles | ✅ | `bench_lights.py` | Read along the emission direction, in candelas, `normalize` and `angleScale` (K-70, 0113) - blurred and 30x off before |
| Colour temperature, emission focus and tint | ✅ | `bench_lights.py` | Focus in the light shader (K-69, 0112) |
| Dome and rect light textures | ✅ | `bench_dome.py`, `bench_rect.py` | Dome in USD's lat-long orientation and `poleAxis` (K-67, 0111); rect texture no longer mirrored (K-68, 0112) |
| `visibleInPrimaryRay`, `shadowEnable` | ✅ | upstream | |
| Light linking, shadow linking | ✅ | `bench_settings.py` | Hydra's light linking scene index → Cycles light and shadow sets (K-24, 0089); no light filters |
| `shadow:color`, `diffuse`/`specular` multipliers, `shadow:enable` | ✅ | `bench_light_split.py` 8/8 vs Karma | The light is split over twins (K-87, 0127); a dome keeps 0 or 1 |
| Light filters | ❌ | code read | No Cycles counterpart |
| Dome `textureFormat` | ⏸ | Karma, 2026-10-09 | Lat-long only. Not done on purpose: Karma itself reads `mirroredBall` and `angular` maps as lat-long (measured), so there is no reference for their orientation, which the HDRShop pages USD cites leave ambiguous |
| Camera: perspective, ortho, DoF, apertures, lens shift, aspect conform | ✅ | `bench_camera.py` 7/7 vs Karma | |
| Camera exposure | ✅ | `bench_camera.py` | Times the render settings' film exposure (K-71, 0114) |
| Crop (`dataWindowNDC`), pixel aspect | ✅ | `bench_camera.py` | Under husk, from its render settings (K-77, 0119) |
| `disableDepthOfField`, `aspectRatioConformPolicy` | ✅ | `bench_camera.py` | Policy from the render settings under husk (K-78, 0120) |
| Camera motion blur | ✅ | `bench_motion.py` camera cases, 2026-10-09 | Every sample the scene gives inside the shutter, not only two: a camera turning back mid-shutter blurs back and forth. Cycles spaces the steps evenly over the shutter, so keys spaced unevenly inside it shift where the blur is densest, not how far it reaches |
| Camera switch without manual restart | ✅ | phase 25 | |

## Rendering and output

| Feature | State | Verified by | Notes |
|---|---|---|---|
| CPU, CUDA, OptiX | ✅ | pixel-identical across the three | |
| Device menu (Render › Cycles Render Device) | ✅ | phase 19 | Per installation, not per scene |
| Render Settings tab (integrator sockets) | ✅ | 59 properties | Generated from the integrator |
| `samples`, `time_limit`, `sample_offset`, `dicing_rate` | ✅ | measured | |
| Shutter from settings, motion blur toggle | ✅ | `bench_settings.py` (batch) | Both flags, resync when blur returns (K-34, 0086); live toggle unmeasured |
| AOVs: color, depth, normal, primId, instanceId, P | ✅ | phase 6 | Houdini names `C`, `N`, `P`, `Pz` |
| Light passes, AO, mist, motion vectors, cryptomatte, shader AOVs | ✅ | `bench_aovs.py` 7/7 | Every Cycles pass by name, Karma names and LPEs in Karma's convention, cryptomatte layers, `aov_output` as a pass-through (K-25, 0087). cryptomatte manifest in the EXR header (0094), light groups (0092) |
| Transparent background | ✅ | `bench_settings.py` | `cycles:background:transparent`, or a dome hidden from camera rays (K-26, 0086) |
| Film exposure, pixel filter | ✅ | `bench_settings.py` (exposure) | Any film/background socket as `cycles:film:*`, `cycles:background:*` (0086) |
| Denoising (OIDN/OptiX) | ✅ | integrator sockets | |
| Per-object ray visibility, holdout, shadow catcher, light groups, caustics flags | ✅ | `bench_settings.py` | `primvars:cycles:object:*` and Karma's visibility/holdout (K-27, 0088); light group passes since 0092 |
| Render tags / purposes | ✅ | checked in Houdini | Honoured live (K-28, 0090) |
| Batch mode under husk | ✅ | measured | `background = true` brings nothing (K-29); crop, pixel aspect, conform policy read from husk's settings (K-77, K-78) |
| GL display driver | ✅ | user's viewport; agent's MCP session, 2026-10-09 | Houdini 22's own viewport is Vulkan ("Houdini VK", the default), but it ships only `hgiGL`: a delegate always gets an OpenGL Hgi and the display driver works under it (checked live, Cycles CPU in a Houdini VK viewport). The output driver remains for husk, which has no Hgi, and for a future Hgi that is not OpenGL |
| Viewport interactivity | ✅ | timestamped live log | K-31 closed 2026-10-08: 871 restarts by hand, first sample 19 ms median, no host-thread pass over 50 ms |

## Materials - native Cycles

| Feature | State | Verified by | Notes |
|---|---|---|---|
| 163 nodes published to Sdr, 100 VOPs | ✅ | CYCLES_VOPS.md | `convert_*` hidden |
| Material Builder, three terminals, properties node | ✅ | phase 15, 20 | |
| Ramps and curves (Houdini encoding → table) | ✅ | phase 10 | |
| UDIM (`<UDIM>`, `%(UDIM)d`) | ✅ | code and render | |
| Image reload on filename change | ✅ | phase 24 | |
| Copernicus `op:` textures, live | ✅ | phases 23-29 | Under husk, cooked to files by the USD Render ROP (K-40, 0126) |
| Material settings (`displacement_method`...) | ✅ | phase 20 | |
| Enum validation | ✅ | phase 14 | |
| 8-bit sRGB auto-detection under ACES | ✅ | `bench_usdtex.py` | `auto` picks the config's sRGB texture space (K-66, 0110) |
| Viewport preview from the Cycles graph | 🟡 | phase 27 | One image per input; no `mix`, no procedurals |

## Materials - UsdPreviewSurface

| Feature | State | Notes |
|---|---|---|
| Surface inputs | ✅ | |
| `UsdUVTexture` wrap, file | ✅ | `bench_usdtex.py` | `repeat`, `useMetadata` (black) translated (K-66, 0110) |
| `UsdUVTexture` per-channel outputs | ✅ | Were averaged (K-56); 4 bench cases |
| `UsdUVTexture` `scale`/`bias` | ✅ | rgb only (K-15) |
| `UsdUVTexture` `fallback` | ✅ | When the file cannot be found, as Karma (K-83, 0124); alpha stays 1 |
| `UsdTransform2d` | ✅ | `bench_usdtex.py`: rotation, translation, scale against Karma |
| `sourceColorSpace` | ✅ | Read from Hydra's colour-space field, resolved in the OCIO config (K-66, 0110) |
| Preview surface defaults | ✅ | Diffuse 0.18 pinned - was 0.8 (K-55) |
| `displacement` | ✅ | Cycles displacement node (K-75, 0117) |
| `opacityThreshold`, `useSpecularWorkflow` | ✅ | Four mapping variants (K-65, 0110) |
| `occlusion` | ❌ | No Cycles counterpart |

## Materials - MaterialX

Three numbers, measured 2026-10-09 (after 0125) (commands in [TESTING.md](TESTING.md)):
**805** of 822 nodedefs are rendered - 651 through the mapping table, 110 by
expanding a nodegraph (the library's, or one the delegate ships for nodes the
library writes in GLSL only), 44 by rewriting or folding (`mtlx_coverage.py`);
**666** of the 806 that route keep every input, output and node when rendered
with all inputs authored (`mtlx_inputs.py`); **80** are verified against a
value computed from the MaterialX definition (`bench_mtlx.py`), and the five
surface models keep their own defaults for unauthored inputs
(`mtlx_defaults.py`). Against Karma on the same file: 633 of 704 value nodes
and 38 of 45 closures alike (`mtlx_karma.py`, the rest explained in K-61 and
K-64), hand-built BSDF networks (`bench_agree.py`), and every input of the
surface models (`surface_audit.py`, K-63). On 2026-10-07 the numbers were
652, 543 and 36. This table says what renders right.

| Family | State | Notes |
|---|---|---|
| `standard_surface` | ✅ | 29 of 39 inputs measured; separate glass lobe when `transmission_color` is authored |
| `open_pbr_surface`, `disney_principled`, `gltf_pbr` | ✅ | Own tables since 2026-10-07 (K-05); defaults verified by `mtlx_defaults.py`; each lists its dropped inputs |
| Unauthored inputs of every surface | ✅ | MaterialX / USD defaults pinned (K-55) |
| `image`, `tiledimage`, `hextiledimage`, `gltf_image` | ✅ | `constant` wrap only exact for black |
| `normalmap`, `bump`, `displacement` | ✅ | `bench_normalmap.py`, `bench_displace.py`; per-vertex UVs broke the tangent space before 0116 (K-73) |
| `heighttonormal` | ✅ | Tangent-space map from the delegate's own nodegraph (K-12, 0108) |
| `texcoord`, `position`, `normal`, `tangent` | 🟡 | `position` object space ✅; `normal`/`tangent` world space; no UV set index |
| `geomcolor` | ✅ | Exact since 2026-10-07 (K-06, K-19); `index` not carried |
| `geompropvalue` | 🟡 | Scalar output only |
| MaterialX noises (perlin, fractal, cell, worley, unified) | ✅ | Exact kernel from PR 158054 |
| `checkerboard`, `randomcolor`, `ramplr` | ✅ / 🟡 | `ramptb` is the diagonal gradient |
| `mix` | ✅ | Exact since 2026-10-07 (K-01) |
| `plus`, `minus`, `difference`, `burn`, `dodge`, `screen`, `overlay` | ✅ | Orientation fixed (K-02); `plus` value-tested, the others not yet |
| `mix`/`add`/`multiply` of BSDF, EDF, VDF, surfaceshader | ✅ | Exact since 2026-10-07 (K-03); four bench cases |
| `mix`/`add`/`multiply`/`dot` of displacementshader | ✅ | Vector nodes; untested |
| `surface` | ✅ | Added 2026-09-10 |
| `volume` | ✅ | Added 2026-10-07 (K-04); no value case yet |
| `layer` | 🟡 | Fresnel-weighted mix, IOR 1.5: right for a dielectric top, approximate otherwise (K-09) |
| add/sub/mul/div, scalar and vector | ✅ | Split by type suffix |
| Other math on colour/vector (`absval`, `floor`, `min`, `max`, `power`, `clamp`, `remap`, `smoothstep`...) | ✅ | Vector twins since 2026-10-07 (K-07); 15 bench cases |
| `ln`, `modulo`, `atan2` (scalar) | ✅ | Were wrong: base 0.5, truncated modulo, operands unmapped (K-07) |
| `contrast` scalar and vector | ✅ | |
| `saturate` | ✅ | MaterialX nodegraph, ACEScg luma, exact since 2026-10-07 (K-08) |
| `invert`, `luminance` | ✅ | `amount - in`; ACEScg `lumacoeffs` |
| `rgbtohsv`, `hsvtorgb` | 🟡 | Untested |
| `ifgreater`, `ifgreatereq`, `ifequal` | ✅ | Per type |
| `logical_and/or/not` | ✅ | |
| `dot`, `convert` pass-through, `constant` | ✅ | |
| `rotate2d/3d`, `place2d`, `transform*` | 🟡 | `place2d` pivot/order unverified |
| `facingratio`, `viewdirection` | ✅ / 🟡 | `facingratio` exact for its defaults (K-10); `viewdirection` negated, untested (K-11) |
| `conductor_bsdf` | ✅ | `metallic_bsdf` physical conductor with `ior`/`extinction` (K-13); not value-tested |
| `dielectric_bsdf`, diffuse, sheen, translucent, subsurface | 🟡 | `tint` and thin film carried; `scatter_mode`, `weight`, anisotropy not |
| `absorption_vdf`, `anisotropic_vdf` | 🟡 | Reachable through `volume` since 2026-10-07; coefficient vs colour approximation |
| `uniform_edf` and the other EDFs | 🟡 | All become `emission` |
| Chiang hair BSDF, roughness, absorption nodes | ✅ | Exact vs native principled hair, 4 pairs < 1e-3 |
| `switch`, `swizzle`, `extract`, `ramp4`, `splitlr/tb` | ❌ | Need a mechanism the mapping lacks |
| Alpha compositing | ✅ | Own nodegraphs, 8 nodes same as Karma (K-84, 0125) |
| Matrices, `time`/`frame` | ❌ | No Cycles equivalent (section E of KNOWN_ISSUES) |
| `colorcorrect`, `hsvadjust`, `curveadjust`, triplanar, Houdini `hmtlx*`, 2D patterns, `blur`, `hextilednormalmap` | ✅ | Through their nodegraphs (`mtlx_coverage.py`); `hextilednormalmap` from the delegate's own (K-84) |

## Houdini integration

| Feature | State | Notes |
|---|---|---|
| Package, renderer registration, menu order | ✅ | GPU above CPU |
| Material Builder tab-menu mask | ✅ | `cycles_*` only |
| Material settings translator | ✅ | |
| Preview translator | 🟡 | See above |
| `op:` textures in husk / on a farm | ✅ | An output processor on every new USD Render ROP cooks them to files as it saves (K-40, 0126); `bench_cop_rop.py` |
| COP cache eviction | ✅ | On material finalize, capped by bytes (K-41, 0096) |
| Karma Material Builder (`kma`) | ✅ | Read after `mtlx` since 2026-10-07 (K-16) |

## Repository and process

| Item | State | Notes |
|---|---|---|
| Patch series regenerable from the worktree | ✅ | 74 patches |
| Bootstrap from a clean clone | ✅ | Re-run: 14 min 20 s (ENVIRONMENT.md) |
| Regression tests on images | ✅ | `references/` tracked, `output/` ignored, `bench_diff.py --accept` (K-50) |
| Code and messages in English | ✅ | Translated (K-53, 0097) |
| README numbers reproducible | ✅ | `count_nodes.py`: 163 / 64 / 99 / 97 (K-54) |
