# Gaussian splats

3D Gaussian splats render in Cycles for Houdini, on CPU (Embree) and on OptiX,
on top of the splat primitive Cycles 5.3 introduced. Two things are added to
it: the Hydra side, which upstream's delegate does not have, and a
**composite** mode for faint emissive splats, which upstream's stochastic hit
test cannot render without heavy noise.

## What reaches the delegate

SOP points with `Cd`, `GS_Alpha`, `orient` and `scale` through a SOP Import
LOP become a `ParticleField3DGaussianSplat` prim, which Hydra hands over as an
rprim of type `particleField`. The delegate reads `positions`, `scales` (sigma
per axis), `orientations`, `opacities`, `displayColor` (linear, HDR kept) and,
when present, `radiance:sphericalHarmonicsCoefficients`. Any primvar change
rebuilds the splats.

## Two modes

`cycles:gsplat:mode`, a constant primvar (token or string):

- **`composite`** - the default when the prim has no spherical harmonics. The
  splats are purely emissive and never hit: after each closest-hit query the
  integrator traces the segment up to the hit, accumulates every splat it
  crosses, adds their emission to the path and attenuates what lies behind.
  The blend is a weighted average, independent of order: exact for one
  colour, close for faint splats; dense opaque splats need the other mode.
  There is no acceptance noise. Splats light the scene through the bounce
  rays that cross them; they are not sampled as lights and cast no shadows.
  A splat is bounded down to a response of 1e-4 (3 sigma at opacity 0.01),
  where upstream drops every splat below an opacity of 0.01.
- **`stochastic`** - Cycles' own hit test, the default for trained splats
  (with harmonics). The order 0 coefficient feeds Cycles' default splat
  shader; a colour without harmonics is converted back to that coefficient
  (Rec.709 assumed). Higher harmonics bands are not read yet.

## Why a composite mode

Upstream keeps a hit with a probability equal to the splat's response. At an
opacity of 0.01 that returns the full radiance in one sample out of a hundred
and nothing otherwise: unbiased, but the relative noise per sample is about
10, so 5 % noise needs some 40 000 samples per pixel. Compositing along the
ray removes that noise altogether.

## Devices

- CPU: composited splats carry a ray mask of their own, so other rays skip
  them; the composite query is an occlusion query that accumulates and never
  reports a hit.
- OptiX: composited splats live in a TLAS of their own, traversed without a
  closest hit.
- CUDA without OptiX, HIP and Metal do not draw composited splats.

What costs render time is the number of splats a ray crosses, not the
tracing: a lower global max bounce helps (every bounce ray crosses the splats
again), and so do fewer, larger splats.

## Passes

- Composited emission seen straight from the camera goes to the Emission
  pass; seen through a surface it goes to that surface's light passes, as any
  Cycles emission.
- It goes to the splats' **light group** (`primvars:cycles:object:lightgroup`,
  or Karma's `primvars:karma:object:lpetag`). Each group gets its own splats'
  share of a segment, up to 8 groups per segment.
- **`gsplat_emission`** (the splats' emission seen straight from the camera)
  and **`combined_without_gsplat_emission`** (the beauty without it) are
  render var sources, offered by the Cycles AOVs LOP as SplatEmit and
  BeautyNoSplatEmit. With them the denoiser works on everything but the
  splats' direct emission, which keeps its detail; the beauty is the sum of
  the two.
- **Denoise AOVs** (`cycles:denoise_aovs`, Cycles Render Settings > AOVs):
  render vars OIDN denoises at the end of the render, guided by albedo and
  normal. It helps passes whose noise comes from bounces, such as a light
  group lit through the splats; it softens passes made of fine direct splat
  emission, which are clean already.

## Light Optimize

Render Settings > Light Optimize (`use_light_optimize`,
`light_optimize_factor`, default 10): adaptive sampling judges noise as if the
lights were `factor` times brighter, and the clamps are divided by it - the
habit of rendering with lights ten times brighter and a film ten times darker,
without touching the scene. It only acts past the adaptive minimum samples.

## Limits

- Motion blur on splats whose count changes between frames is impossible, as
  in Karma.
- About 72 bytes per splat; the splats' BVH is rebuilt on every change.
