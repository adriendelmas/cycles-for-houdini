# Progress

The current state, feature by feature, as the code stands on 2026-10-07 -
established by reading the sources, not the earlier claims. Each line says
how it was verified; "code read" means nobody has rendered it yet.

Legend: ✅ works and verified · 🟡 partial or approximate · ❌ missing · 🐞 wrong (see [KNOWN_ISSUES.md](KNOWN_ISSUES.md))

## Geometry

| Feature | State | Verified by | Notes |
|---|---|---|---|
| Polygon meshes, triangulation, primvars | ✅ | 97-node bench, user scenes | |
| Face-varying (corner) normals | ✅ | bit-identical vs per-point normals | |
| Smooth/flat from authored normals | ✅ | measured | |
| Catmull-Clark subdivision, creases, corners | 🟡 | measured | Only when Hydra's `refineLevel > 0`; the max dicing level *is* that display hint (K-30) |
| Adaptive dicing rate, dicing camera | ✅ | 10.3 M → expected triangle counts | Setting `cycles:dicing_rate`, clamped ≥ 0.1 |
| Holes, left-handed subdivided meshes | ❌ | code read | `// TODO: Handle hole indices` |
| Geom subsets (per-face materials) | ✅ | upstream | Face sets only |
| Transform motion blur | ✅ | 179 px blur measured | 3 steps, evenly spaced |
| Deformation blur (sampled points) | ✅ | measured, mesh/curves/points | |
| Velocity / acceleration blur | ✅ | 242 px measured | fps from scene globals, fallback 24 |
| Corner normals under motion blur | 🟡 | upstream behaviour | Cycles drops them; smooth flag takes over |
| Curves: Catmull-Rom through all keys | 🟡 | rendered | USD `type`/`basis`/`wrap` read and ignored (K-20); Bézier, periodic, indexed curves wrong |
| Curves: `widths` `varying` | ❌ | code read | Only `constant` and `vertex` (K-21) |
| Thick 3D curves (`hair_shape`) | ❌ | code read | `SceneParams` never set, ribbons only (K-22) |
| Points | ✅ | phase 5 | Same `widths` limit as curves |
| Point instancer, nested instancers | ✅ | phase 3 | |
| Instance motion blur | ❌ | code read | Instance primvars read at time 0 (K-23) |
| Per-instance primvars | ❌ | code read | Only constant `displayColor` reaches instances |
| Implicit surfaces (Sphere, Cube...) | ❌ | A1 | Not declared as supported rprims |
| OpenVDB volumes | ✅ | phase 5 | `openvdbAsset` only; `vel` not recognised as velocity (K-33) |
| Volume step size, clipping per prim | ❌ | code read | |

## Lights and camera

| Feature | State | Verified by | Notes |
|---|---|---|---|
| Rect, disk, sphere, spot, distant, dome | ✅ | within 1 % of Karma | Units measured per type |
| Cylinder light | 🟡 | 0.95 of Karma | Rectangle approximation, one-sided |
| IES, colour temperature, textures | ✅ | upstream | |
| `visibleInPrimaryRay`, `shadowEnable` | ✅ | upstream | |
| Light linking, shadow linking | ❌ | code read | No category reading (K-24) |
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
| Shutter from settings, motion blur toggle | 🟡 | measured | Toggle only turns off in a live session (K-34) |
| AOVs: color, depth, normal, primId, instanceId, P | ✅ | phase 6 | Houdini names `C`, `N`, `P`, `Pz` |
| Light passes, AO, mist, motion vectors, cryptomatte, shader AOVs | ❌ | code read | Five passes exist (K-25) |
| Transparent background | 🟡 | code read | Only when no dome light is present (K-26) |
| Film exposure, pixel filter | ❌ | code read | |
| Denoising (OIDN/OptiX) | ✅ | integrator sockets | |
| Per-object ray visibility, holdout, shadow catcher, light groups, caustics flags | ❌ | code read | Nothing read per prim beyond on/off (K-27) |
| Render tags / purposes | ❌ | code read | `proxy` and `render` both render (K-28) |
| Batch mode under husk | 🟡 | code read | `background = false` always (K-29) |
| GL display driver | 🟡 | user's viewport | Correct on OpenGL Hgi; falls back under Vulkan and husk |
| Viewport interactivity | 🟡 | stopwatch | 4 s unexplained in the camera/AOV bucket (K-31) |

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
| `UsdUVTexture` `scale`/`bias`, `fallback` | ❌ | Normal maps wrong (K-15) |
| `UsdTransform2d` | ❌ | Declared, never mapped (K-15) |
| `sourceColorSpace = raw` | 🐞 | Name unknown to Cycles (K-15) |
| `displacement`, `occlusion`, `opacityThreshold` | ❌ | |

## Materials - MaterialX

The coverage tool reports 652/823 nodedefs; that number counts prefix hits.
This table says what actually renders right.

| Family | State | Notes |
|---|---|---|
| `standard_surface` | ✅ | 29 of 39 inputs measured; separate glass lobe when `transmission_color` is authored |
| `open_pbr_surface`, `disney_principled`, `gltf_pbr` | 🐞 | Aliased to the standard_surface table; most inputs miss (K-05) |
| `image`, `tiledimage`, `hextiledimage`, `gltf_image` | ✅ | `constant` wrap only exact for black |
| `normalmap`, `bump`, `displacement` | ✅ | |
| `heighttonormal` | 🐞 | Outputs a world normal, not a tangent map (K-12) |
| `texcoord`, `position`, `normal`, `tangent` | 🟡 | `position` object space ✅; `normal`/`tangent` world space; no UV set index |
| `geomcolor` | 🐞 | No attribute name (K-06) |
| `geompropvalue` | 🟡 | Scalar output only |
| MaterialX noises (perlin, fractal, cell, worley, unified) | ✅ | Exact kernel from PR 158054 |
| `checkerboard`, `randomcolor`, `ramplr` | ✅ / 🟡 | `ramptb` is the diagonal gradient |
| `mix` | 🐞 | Inverted (K-01) |
| `plus`, `minus`, `difference`, `burn`, `dodge`, `screen`, `overlay` | 🐞 | Inverted (K-02) |
| `mix`/`add`/`multiply` of BSDF, EDF, VDF, surfaceshader | 🐞 | Sent to colour/scalar nodes (K-03) |
| `surface` | ✅ | Added 2026-09-10 |
| `volume` | ❌ | Missing; MaterialX volumes cannot reach the terminal (K-04) |
| `layer` | 🐞 | 50/50 mix (K-09) |
| add/sub/mul/div, scalar and vector | ✅ | Split by type suffix |
| Other math on colour/vector (`absval`, `floor`, `min`, `max`, `power`, `clamp`, `remap`, `smoothstep`...) | 🐞 | Scalar node, colour averaged to grey (K-07) |
| `contrast` scalar and vector | ✅ | |
| `saturate` | 🐞 | HSV scaling, not luma lerp (K-08) |
| `invert`, `luminance`, `rgbtohsv`, `hsvtorgb` | 🟡 | `amount` and `lumacoeffs` unmapped |
| `ifgreater`, `ifgreatereq`, `ifequal` | ✅ | Per type |
| `logical_and/or/not` | ✅ | |
| `dot`, `convert` pass-through, `constant` | ✅ | |
| `rotate2d/3d`, `place2d`, `transform*` | 🟡 | `place2d` pivot/order unverified |
| `facingratio`, `viewdirection` | 🐞 | Both inverted (K-10, K-11) |
| `conductor_bsdf` | 🐞 | `ior`/`extinction` unmapped: white glossy (K-13) |
| `dielectric_bsdf`, diffuse, sheen, translucent, subsurface | 🟡 | Approximate: `tint`, `scatter_mode`, anisotropy unmapped |
| `uniform_edf` and the other EDFs | 🟡 | All become `emission` |
| `absorption_vdf`, `anisotropic_vdf` | 🟡 | Unreachable without `volume` (K-04) |
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
| Karma Material Builder (`kma`) | ❌ | Context declared, never read (K-16) |

## Repository and process

| Item | State | Notes |
|---|---|---|
| Patch series regenerable from the worktree | ✅ | 74 patches |
| Bootstrap from a clean clone | 🟡 | Written, not re-run end to end since the 5.3 move |
| Regression tests on images | ❌ | Benches overwrite their own references (see [TESTING.md](TESTING.md)) |
| Code and messages in English | ❌ | French comments and log lines throughout (K-35) |
| README numbers reproducible | 🟡 | 163 / 161 / 97 disagree; coverage overstated |
