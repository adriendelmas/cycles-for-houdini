# Gaussian splats in Cycles for Houdini — study (2026-11-03)

Asked by the user through the ARTIFACTORY session: render the EGO "data strings"
(procedural, purely emissive 3D Gaussian splats, 0.5–4 M per frame, animated with
a changing topology, opacity ≈ 0.01, HDR linear radiance, anisotropic scale) with
Cycles, building on the native splat support of Cycles 5.3. Nothing is
implemented; this note holds what was verified and the plan. Roadmap: K-123.

## What Cycles 5.3 does (verified in the source, not from the notes)

Merged into `blender/cycles` main on 2026-09-15 (`6553806b41` "GSplat: Initial
rendering support for Cycles", then `ac33303bc1`, `ea07233644`), also on
`release/5.3`. Our base `8424ed53` is 2026-08-30: 92 upstream commits older.

- A `PointCloud` with `render_as = gaussian_splats`; primitive `PRIMITIVE_GSPLAT`,
  same position/radius layout as points, custom primitive for Embree and OptiX.
  Attributes: `ATTR_STD_GSPLAT_SCALE` (float3, **sigma per axis**, no log),
  `ATTR_STD_GSPLAT_ROTATION` (`Quaternion {w, x, y, z}`),
  `ATTR_STD_GSPLAT_RADIANCE_BASE` (float4: SH DC coefficient, **raw opacity** in
  `.w`, no sigmoid), optional packed SH rest (8-bit quantised, degree ≤ 3).
- Intersection (`kernel/geom/gsplat_intersect.h`): bounding sphere, then the
  point of maximum response along the ray, `t = -dot(o_g, d_g) / dot(d_g, d_g)`;
  response `α·exp(-e/2)`; **stochastic acceptance**: the hit is kept when a hash
  of the hit point is below the response, otherwise the ray goes on. No
  polyhedron clipping, no sorting, no state.
- Bounding radius (`scene/pointcloud.cpp update_gsplat_radii`):
  `r = max(|σ|)·sqrt(2·ln(α / 0.01))`, and **`r = 0` when α < 0.01**: a splat
  of opacity below 0.01 is never hit; at α = 0.02 the sphere stops at 1.18 σ,
  at 0.05 at 1.79 σ. Worse than Karma XPU's 2.8 σ polyhedron for our opacities.
- Radiance (`kernel/geom/gsplat.h gsplat_radiance`): `rgb = srgb_to_linear(C0·base
  + SH(dir) + 0.5)`, so `radiance:base` is a trained sRGB SH coefficient, not a
  colour. The default shader is `Attribute("radiance") → Emission(1)`. Any other
  attribute of the point cloud can feed an Emission node instead.
- Normal: axis of the smallest scale, rotated (for the Diffuse relighting).
- Light sampling (`scene/light.cpp`, `light_tree.cpp`): only mesh triangles and
  lights are emitters. Splats, points, curves and volumes light the scene only
  when a bounce ray hits them; there is no `treat_as_lightsource` equivalent.
- Shadow rays: `shadow_all.h` has a TODO "accumulate throughput instead of
  recording intersection": splats cast binary stochastic shadows.
- The Blender importer applies `exp` to scales and the sigmoid to opacity at
  import; the kernel takes decoded values.
- Hydra: the upstream delegate has no splat support (`hydra/pointcloud.cpp`
  unchanged).

## What Houdini gives a Hydra delegate (measured, probe files below)

SOP points with `Cd`, `GS_Alpha`, `orient`, `scale` through a SOP Import LOP
become a `ParticleField3DGaussianSplat` prim (usdVol schema, OpenUSD 25.11):
`positions`, `scales` (raw sigma), `orientations` (quatf, printed `(w, x, y, z)`:
Houdini's `orient` xyzw → `w` last → Cycles `make_quaternion(w, x, y, z)`),
`opacities` (raw `GS_Alpha`), `primvars:displayColor` (= `Cd`, **HDR kept, no
conversion**, 4 2 0.5 stayed 4 2 0.5), `radiance:sphericalHarmonicsCoefficients`
only when `GS_SPH_*` exist. Hydra adds it as an rprim of type **`particleField`**
(`HdPrimTypeTokens->particleField`, `UsdImagingParticleFieldAdapter`, a gprim
adapter). Our delegate does not list that type, so Hydra skips the prim silently
(husk on the probe: Karma "Rprim Added", hdCycles nothing).

## Why the stock 5.3 path cannot render the data strings as they are

Stochastic acceptance with probability p = α·g ≤ 0.01 returns the full radiance
L in 1 sample out of 100 and 0 otherwise: unbiased, but the relative noise per
sample is `sqrt((1-p)/p)` ≈ 10. For 5 % noise on a string that needs ~40 000
spp; 20 % needs 2 500. Karma XPU's noise-free mode composites analytically. The
Blender notes' "not fully correct in low-opacity, high-radiance areas" is the
sRGB mapping, which we bypass, not this variance. Plus the radius cut above.

## Plan (not scheduled; estimates for the user)

1. **Rebase the fork onto `release/5.3`** (2–3 days, CPU + OptiX rebuild,
   re-run the probes of TESTING.md). Dry cherry-pick of the three gsplat commits
   onto `houdini-fixes-53`: conflicts in 6 files (`bvh/embree.cpp`,
   `svm/attribute.h`, `kernel/types.h` KernelObject union, `scene/attribute.cpp`,
   `scene/scene.cpp` feature log, SH header missing) and ~15 prerequisite
   upstream commits (quaternion attribute `40f4daeb`, SH attribute `efd699e1`,
   KernelObject split `01e9fa19`, 64-bit features `6e93c3a7`, Embree
   `prim_offset` `9f963954`, `float3x3`, OptiX hit kind enum, attribute name
   mapping `591700a7`). 54 of the files our 162 patches touch moved upstream
   since our base, so a rebase is the same work as the cherry-picks and leaves a
   clean base. Blender 5.3 ships 2026-11-10.
2. **Delegate** (1 day): register `particleField`; a `HdCyclesGSplat` rprim
   (or `HdCyclesPoints` with a flag) that reads `positions`, `scales`,
   `orientations`, `opacities` into the GSPLAT attributes (`radiance_base.xyz`
   = 0, `.w` = opacity), keeps `displayColor` and the other primvars as
   attributes, sets `render_as = gaussian_splats`, and binds, when no material
   is bound, `Attribute("displayColor") → Emission(strength)` — this skips the
   sRGB/SH mapping and keeps the HDR linear radiance. First thing to do in
   `Sync`: dump the data-source names of the prim, the layout of the gprim data
   source was not verified (no Python binding for UsdImaging in Houdini).
   Patch on our side: bounding radius `k·max(σ)` with k = 3 (one line in
   `update_gsplat_radii`), so low opacities are not culled.
3. **Gate test, one frame** (half a day): one real data string exported from the
   ARTIFACTORY scene (SOP Import, one frame, one string), rendered with husk,
   Cycles CPU 64 and 256 spp vs Karma XPU: mean luminance of the string's
   region (bias) and the std between two seeds (noise). Expected: right mean,
   noise ≈ 10/sqrt(spp). The user decides on step 4 from that number.
4. **Additive emissive path** (kernel, ~1 week CPU + 3–5 days OptiX): for
   point clouds flagged emissive-additive, the closest-hit traversal collects
   the splats along the ray up to the first surface (the `shadow_all.h`
   machinery: fixed-size hit buffer, loop by advancing `tmin`), sorts by `t`,
   adds `Σ T_i·α_i·g_i·L_i` to the path's emission and multiplies the throughput
   by `Π(1 - α_i·g_i)`. Noise-free like Karma; bounce rays from the walls get
   the integrated emission too, so the strings light the scene smoothly, though
   still only through bounces.
5. **Lighting the scene** (SOP side, no code): an emissive tube along each
   curve, visible to diffuse/glossy/shadow rays only (`karma:object:
   rendervisibility`, already parsed), radiance per area = Σ α·L·σxσyσz over the
   segment / tube area; the splats camera-only. The light tree then samples the
   tubes directly. Without it, the walls are lit only by bounce rays hitting the
   splats, which with the stochastic path is noise times noise.

## Alternative available today, no kernel work

Rasterise the strings into a VDB (density + emission colour) per frame and
render it as a Cycles volume with an emissive volume shader: volume emission is
integrated along the ray by the ray marcher (no acceptance noise), bounce rays
through it light the walls smoothly, CPU and GPU work now. Cost: a VDB per frame
whose voxel must resolve the smallest sigma (to measure on one string:
sigma_min vs extent), and no NEE either (same tube proxy helps).

## Volume and animation

4 M splats ≈ 72 B each (P+radius, scale, rotation, radiance_base, Cd) ≈ 300 MB,
BVH rebuilt per frame like points (seconds). Motion blur with a changing
topology is impossible, as in Karma.

## Files

Probes `E:/claude_temp/hdCycles/gsplat/probe/` (`sopimport_probe.py`,
`splat_sopimport.usda`, `cam.usda`, husk logs), upstream material
`E:/claude_temp/hdCycles/gsplat/` (`pr163103.diff`, `pr163102.diff`, `main_*.h`).
The three gsplat commits are fetched in the worktree (`git fetch origin main`).
Sources: Blender 5.3 release notes (rendering), code.blender.org
"Splatting the Gaussians into Blender" (2026-10), PR blender/blender#163103 and
#163102, `blender/cycles` main.

## Speed: what a faster renderer buys (added 2026-11-03, ARTIFACTORY figures)

Goal stated by the user: render time, with the hunch that Cycles could be up to
4x faster than Karma XPU on this case (not verified; nothing measured yet).
Timings given for a 4K frame, 48 spp, OIDN on 3 AOVs, RTX 3090, one husk per
frame: render 16-78 s + "rest" (SOP baking, USD export, husk start) 14-37 s,
total 39-114 s, 397 s for the seven frames.

| Case | Total now | Total with 4x render | Gain |
|---|---|---|---|
| Render 4x faster, rest unchanged | 397 s | 205 s | 1.9x (1.5x-2.4x per frame) |
| Render 4x faster, rest halved | 397 s | 135 s | 2.9x |

- The rest cannot be removed by the renderer alone. Measured on the 3-splat
  probe (husk, 64x48, 1 spp, CPU): process start plus a trivial render takes
  4-10 s with both hdCycles and Karma, so the delegate start is not slower than
  Karma's, and about 5-10 s of the rest is husk start whatever the renderer.
- Cuts that belong to the pipeline, same for any renderer: write the splats
  alone as a binary per-frame layer over a static stage (no rewrite of the
  rest of the stage); render several frames per husk process on a time-sampled
  stage (husk frame-range options to be checked) so start-up and kernel load
  are paid once. The BVH of the splats is rebuilt every frame anyway.
- At 48 spp the stochastic Cycles path is far too noisy at opacity 0.01 even
  with OIDN (hit probability 1 %, ~0.5 hit per pixel per frame), so any speed
  claim only holds for the additive path (plan step 4). Karma XPU's own noise-free
  mode is the bar to beat.
- Cheapest test of the 4x hunch before any rebase: bake one real string to a
  VDB (density + emission) and render that frame with hdCycles (CPU or OptiX)
  and with Karma XPU, same 4K/48 spp/OIDN. It needs no kernel work and tells
  whether Cycles is faster on this scene at all. It stays an approximation of
  the splats, so it measures the engine, not the final image.
- The gate test of plan step 3 must record time to a given denoised error, not
  only spp: the same number of samples costs different times in the two engines.

## Implementation (2026-11-03, branch `gsplat-53`)

Done in autonomy at the user's request ("the whole fix, for speed"), on the
fork rebased onto `release/5.3` (see `docs/CYCLES_53.md`).

**Delegate.** `particleField` is a supported rprim type; it creates an
`HdCyclesPoints` in splat mode (`hydra/pointcloud.cpp`, `PopulateSplats`),
which reads the primvars usdVolImaging publishes - `positions`, `scales`,
`orientations`, `opacities` (float or half), `displayColor`,
`radiance:sphericalHarmonicsCoefficients`/`Degree` - into the GSPLAT
attributes, `render_as = gaussian_splats`. GfQuatf (real, imaginary) becomes
Cycles' `Quaternion {w, x, y, z}`. Unbound splats fall back to Cycles'
`default_gsplat` shader. Any primvar change rebuilds the splats (they have no
`points`).

**Two modes**, `cycles:gsplat:mode` (constant token or string):

- `composite` - the default when the prim has no spherical harmonics (the
  EGO strings). The base radiance holds the linear `displayColor`, unshaded.
  Splats are never hit: after each closest-hit query the integrator traces
  the segment up to the hit (`integrator_intersect_gsplat_composite`), sums
  `response x radiance`, the responses and `log(1 - response)` of every splat
  crossed, and adds `radiance_sum x (1 - T) / response_sum` to the path as
  emission, then multiplies the throughput by `T`. Weighted-average
  order-independent blending: exact for one colour, close for faint splats;
  dense opaque splats need the other mode. No noise from acceptance; walls are
  lit by the bounce rays that cross the haze (no light sampling, no shadows).
  Bounding sphere down to a response of 1e-4 (3 sigma at opacity 0.01)
  instead of upstream's 0.01, which dropped every splat below 0.01.
- `stochastic` - upstream's hit test, the default for trained splats (with
  harmonics); the order 0 coefficient feeds `default_gsplat`, a colour
  without harmonics is converted back to that coefficient (Rec.709 assumed).
  Higher harmonics bands are not read yet.

**Kernel.** A ray marker `PATH_RAY_VISIBILITY_GSPLAT_COMPOSITE` (bit 14) and
an object flag `SD_OBJECT_GSPLAT_COMPOSITE`; `kernel_data.bvh.
have_gsplat_composite` skips the query when no such splats exist.
- Embree (CPU): composited splat geometries and their instances carry only the
  marker as mask, so other rays skip them; the composite query is an
  `rtcOccluded1` with its own user-geometry callback, which accumulates and
  never reports a hit.
- OptiX: composited splat instances are left out of the scene's TLAS and put in
  a TLAS of their own (`device_bvh_gsplat`, in KernelData's padding), so other
  rays never meet them. The composite traversal (`optixTraverse` on that TLAS,
  no closest hit) is recognised in `__intersection__point` by a marker in the
  payload (`p2`, and its complement in `p3`): `optixTraverse` does not carry
  Cycles' ray flags. The path visibility travels in `p5`, the accumulator
  through `p0/p1`.
- Each splat's `S^-1 R^T` is computed once per update (`gsplat_inverse`, three
  float4 rows per point, `PointCloud::pack_gsplat_inverse`), so a ray-splat
  test is three dot products and one fetch of the base radiance. The bounds
  are the ellipsoid's box at the 1e-4 response cut.
- The CUDA (non-OptiX), HIP and Metal BVHs do not draw composited splats.

**Speed (4K, 128 spp, RTX 3090, OptiX, synthetic 4 M splat frame).** No
splats 55 s; splats before the separate TLAS and the precomputed matrix
138 s, after 131 s, image identical. What costs is the number of splats a ray
crosses (384 on average per camera ray there), not the tracing. On the EGO
frame in the viewport the user measured 128 spp off camera in 25 s. Levers left
to the scene: a lower global max bounce (the splats are crossed again by every
bounce ray), fewer, larger splats. The 1e-4 cut is kept: 1e-3 is faster but
changes the look (user's choice).

**Light Optimize** (Render Settings > Light Optimize, `use_light_optimize`,
`light_optimize_factor`, default 10): adaptive sampling judges noise as if the
lights were `factor` times brighter (`KernelFilm.adaptive_exposure`), and the
clamps are divided by it, the user's Blender habit of x10 lights / x0.1 film
without touching the scene. It only acts past the adaptive minimum samples, so
it does little at 128 spp.

**Passes.** Composited emission seen straight from the camera goes to the
Emission pass (Emit, Karma's `CO`); seen through a surface it goes to that
surface's light passes (DiffDir/DiffInd, GlossDir/GlossInd...), as any Cycles
emission. It goes to the splats' light group (`Combined_<group>`, light group
from `primvars:cycles:object:lightgroup` or Karma's `primvars:karma:object:lpetag`):
fixed 2026-11-03, before that the group pass stayed black. A segment's emission
goes to the group of its strongest splat. Cycles has no pass for emission seen
indirectly only (Karma's `C.+O`): with the splats as the only emitters it is
`Combined_<group> - Emit`. Two render vars naming the same light group write
only the first.

**SplatEmit / BeautyNoSplatEmit** (2026-11-03, for EGO's comp): render var
sources `gsplat_emission` (the splats' emission seen straight from the camera,
nothing else) and `combined_without_gsplat_emission` (the beauty without it, one
layer). With them, the kernel writes the splats' direct emission to its own pass
instead of the beauty; the denoiser works on the rest; the delegate adds the pass
back to the beauty it reads. So the beauty keeps the splats' detail undenoised,
BeautyNoSplatEmit is denoised, and C = BeautyNoSplatEmit + SplatEmit. The
viewport's `color` display (no render settings) is not affected. Film exposure
other than 1 is not applied to the pass (untested). See K-128 for the light group fix found on the way.
