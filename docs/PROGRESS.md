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
| Catmull-Clark subdivision, creases, corners | ✅ | measured | Always for `catmullClark`, capped by `cycles:max_subdivisions` (K-30, 0084) |
| Adaptive dicing rate, dicing camera | ✅ | 10.3 M → expected triangle counts | Setting `cycles:dicing_rate`, clamped ≥ 0.1 |
| Holes, left-handed subdivided meshes | ❌ | code read | `// TODO: Handle hole indices` |
| Geom subsets (per-face materials) | ✅ | upstream | Face sets only |
| Transform motion blur | ✅ | 179 px blur measured | 3 steps, evenly spaced |
| Deformation blur (sampled points) | ✅ | measured, mesh/curves/points | |
| Velocity / acceleration blur | ✅ | 242 px measured | fps from scene globals, fallback 24 |
| Corner normals under motion blur | 🟡 | upstream behaviour | Cycles drops them; smooth flag takes over |
| Curves: every USD basis and wrap | ✅ | `bench_curves.py` 5/5 | Bézier, B-spline, Catmull-Rom, periodic, pinned resampled to keys (K-20, 0081); indexed handled, untestable from a file |
| Curves: `widths` `varying` | ✅ | `bench_curves.py` | Blended per key (K-21, 0081) |
| Thick 3D curves | ✅ | rendered, end-on test | `cycles:curve_shape` auto/thick/ribbon, live; default auto = thick (K-22, 0081) |
| Points | ✅ | phase 5 | `varying` widths read as per-point (0081) |
| Point instancer, nested instancers | ✅ | phase 3 | |
| Instance motion blur | ✅ | `bench_motion.py` 6/6 | Positions and instancer transform sampled over the shutter (K-23, 0082) |
| Per-instance primvars | ✅ | `bench_instances.py` 5/5 | `instance` primvars as object attributes, nested instancers, `displayColor` → Object Info colour (0082) |
| Constant scalar primvars (`float x = 0.5`) | ✅ | rendered | Read uninitialised memory before 0082; doubles and ints now converted |
| Implicit surfaces (Sphere, Cube...) | ✅ | `bench_implicit.py` 6/6 | Our scene index meshes them, 64 segments, smooth normals (A1, 0083) |
| OpenVDB volumes | ✅ | phase 5, `bench_settings.py` | `openvdbAsset` only; Houdini `vel`/`Cd` aliased (K-33, 0086) |
| Volume step size, clipping per prim | ❌ | code read | |

## Lights and camera

| Feature | State | Verified by | Notes |
|---|---|---|---|
| Rect, disk, sphere, spot, distant, dome | ✅ | within 1 % of Karma | Units measured per type |
| Agreement with Karma on materials | ✅ | `bench_agree.py` 21/21 | Diffuse, dielectric, metal, glass, coat, emission, preview surface: floor to 1 %, spheres to 25 %, glass loose (2026-10-08) |
| Cylinder light | 🟡 | 0.95 of Karma | Rectangle approximation, one-sided |
| IES, colour temperature, textures | ✅ | upstream | |
| `visibleInPrimaryRay`, `shadowEnable` | ✅ | upstream | |
| Light linking, shadow linking | ✅ | `bench_settings.py` | Hydra's light linking scene index → Cycles light and shadow sets (K-24, 0089); no light filters |
| `shadow:color`, `diffuse`/`specular` multipliers, light filters | ❌ | code read | |
| Dome `textureFormat` | ❌ | code read | Lat-long assumed |
| Camera: perspective, ortho, DoF, apertures | ✅ | phase 2 | |
| Camera motion blur | 🟡 | upstream | Two samples: linear only |
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
| Render tags / purposes | ❌ | code read | `proxy` and `render` both render (K-28) |
| Batch mode under husk | 🟡 | code read | `background = false` always (K-29) |
| GL display driver | 🟡 | user's viewport | Correct on OpenGL Hgi; falls back under Vulkan and husk |
| Viewport interactivity | ✅ | timestamped live log | K-31 closed 2026-10-08: 871 restarts by hand, first sample 19 ms median, no host-thread pass over 50 ms |

## Materials - native Cycles

| Feature | State | Verified by | Notes |
|---|---|---|---|
| 163 nodes published to Sdr, 100 VOPs | ✅ | CYCLES_VOPS.md | `convert_*` hidden |
| Material Builder, three terminals, properties node | ✅ | phase 15, 20 | |
| Ramps and curves (Houdini encoding → table) | ✅ | phase 10 | |
| UDIM (`<UDIM>`, `%(UDIM)d`) | ✅ | code and render | |
| Image reload on filename change | ✅ | phase 24 | |
| Copernicus `op:` textures, live | ✅ | phases 23-29 | In Houdini only; husk needs flattening |
| Material settings (`displacement_method`...) | ✅ | phase 20 | |
| Enum validation | ✅ | phase 14 | |
| 8-bit sRGB auto-detection under ACES | 🟡 | A21 | Falls back to linear; menu as workaround |
| Viewport preview from the Cycles graph | 🟡 | phase 27 | One image per input; no `mix`, no procedurals |

## Materials - UsdPreviewSurface

| Feature | State | Notes |
|---|---|---|
| Surface inputs | ✅ | |
| `UsdUVTexture` wrap, file | ✅ | |
| `UsdUVTexture` per-channel outputs | ✅ | Were averaged (K-56); 4 bench cases |
| `UsdUVTexture` `scale`/`bias` | ✅ | rgb only (K-15) |
| `UsdUVTexture` `fallback` | ❌ | |
| `UsdTransform2d` | 🟡 | Mapped to `mapping` (K-15); untested |
| `sourceColorSpace` | ✅ | `raw`/`sRGB`/`auto` spelled for Cycles |
| Preview surface defaults | ✅ | Diffuse 0.18 pinned - was 0.8 (K-55) |
| `displacement`, `occlusion`, `opacityThreshold` | ❌ | |

## Materials - MaterialX

Three numbers, measured 2026-10-08 (commands in [TESTING.md](TESTING.md)):
**762** of 822 nodedefs are rendered - 651 through the mapping table, 71 by
expanding the nodegraph the library defines them with, 40 by rewriting
(`mtlx_coverage.py`); **636** of the 775 that route keep every input, output
and node when rendered with all inputs authored (`mtlx_inputs.py`); **49** are
verified against a value computed from the MaterialX definition
(`bench_mtlx.py`), and the five surface models keep their own defaults for
unauthored inputs (`mtlx_defaults.py`). On 2026-10-07 the numbers were 652,
543 and 36. This table says what renders right.

| Family | State | Notes |
|---|---|---|
| `standard_surface` | ✅ | 29 of 39 inputs measured; separate glass lobe when `transmission_color` is authored |
| `open_pbr_surface`, `disney_principled`, `gltf_pbr` | ✅ | Own tables since 2026-10-07 (K-05); defaults verified by `mtlx_defaults.py`; each lists its dropped inputs |
| Unauthored inputs of every surface | ✅ | MaterialX / USD defaults pinned (K-55) |
| `image`, `tiledimage`, `hextiledimage`, `gltf_image` | ✅ | `constant` wrap only exact for black |
| `normalmap`, `bump`, `displacement` | ✅ | |
| `heighttonormal` | 🐞 | Outputs a world normal, not a tangent map (K-12) |
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
| Matrices, alpha compositing, `time`/`frame` | ❌ | No Cycles equivalent |
| `colorcorrect`, `hsvadjust`, `curveadjust`, triplanar, Houdini `hmtlx*`, 2D patterns, `blur` | ❌ | Feasible, not done |

## Houdini integration

| Feature | State | Notes |
|---|---|---|
| Package, renderer registration, menu order | ✅ | GPU above CPU |
| Material Builder tab-menu mask | ✅ | `cycles_*` only |
| Material settings translator | ✅ | |
| Preview translator | 🟡 | See above |
| `op:` textures in husk / on a farm | ❌ | `flatten_op_textures` exists, nothing automates it |
| COP cache eviction | ❌ | Pixels kept for the session |
| Karma Material Builder (`kma`) | ✅ | Read after `mtlx` since 2026-10-07 (K-16) |

## Repository and process

| Item | State | Notes |
|---|---|---|
| Patch series regenerable from the worktree | ✅ | 74 patches |
| Bootstrap from a clean clone | 🟡 | Written, not re-run end to end since the 5.3 move |
| Regression tests on images | ✅ | `references/` tracked, `output/` ignored, `bench_diff.py --accept` (K-50) |
| Code and messages in English | 🟡 | New code in English since 2026-10-07; French comments remain in older code (K-53) |
| README numbers reproducible | ✅ | `count_nodes.py`: 163 / 64 / 99 / 97 (K-54) |
