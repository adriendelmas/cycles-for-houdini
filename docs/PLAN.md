# Plan

The order in which the project reaches the state [GOALS.md](GOALS.md)
describes. Each phase lists what it changes, the issues it closes
([KNOWN_ISSUES.md](KNOWN_ISSUES.md)), and the test that proves it - a phase
is not done until that test exists and passes.

The ordering rule: **make the measurements honest first, then fix what is
wrong, then add what is missing.** Fixing on top of a bench that cannot see
the bug reproduces the mistakes already in the journal.

## Phase 0 — Honest ground (1-2 days)

Nothing renders differently after this phase; everything that follows can be
trusted.

> **Status 2026-10-07: done**, except two items. Bench split (commit
> `2680470`); `bench_mtlx.py` computes its expected values from the MaterialX
> definitions and carries 11 cases; the three coverage numbers exist
> (`mtlx_coverage.py` 652 routed, `mtlx_inputs.py` 511 input-complete,
> `bench_mtlx.py` 11 value-verified); `count_nodes.py` settles the node count;
> the render-pass stopwatch is split (patch 0076). Open: the K-31 reading
> needs a live Houdini viewport, and README's numbers are updated in the same
> commit as this note.

| Task | Closes | Done when |
|---|---|---|
| Separate bench output from references: `tests/usd/bench-53/images/` becomes `tests/nodes/5.3/references/` (tracked) and `output/` (ignored); `bench_diff.py` compares output to reference per node with a tolerance | K-50 | `git status` clean after a bench run; a deliberate one-line regression in `material.cpp` is caught |
| Expected values in `bench_mtlx.py` computed from the MaterialX source expressions, not from the renderer; add `mix`, `plus`, `layer`, `saturate`, `facingratio`, `geomcolor` cases | K-52 | `saturate` case **fails** before phase 1 and passes after |
| `mtlx_coverage.py` reports three numbers: routed, input-complete (every nodedef input has a mapping or a documented omission), render-verified | K-51 | README quotes the third number |
| Re-measure the render pass with a timestamp per statement in the camera/AOV bucket | K-31 | The 4 s is attributed to a named call |
| One number for the node count, produced by a command | K-54 | README, STATUS, CYCLES_VOPS agree |
| Restate README claims (viewport refresh conditional on OpenGL Hgi, coverage, testing) | - | Every claim links to the command that reproduces it |

## Phase 1 — The inversions (half a day)

One-line fixes with outsized effect. Do them together and regenerate the
patch series once.

> **Status 2026-10-07: done** (patch 0076). All seven rows; `mix`, `plus`,
> `saturate`, `geomcolor` and `facingratio` pass the value bench exactly.
> Fixing `geomcolor` uncovered K-19 - float3 primvars copied at the wrong
> stride, an upstream bug that corrupted every per-vertex colour - fixed as
> patch 0075. Still to value-test: the six other blends, `viewdirection`, the
> colour-space names.

| Task | Closes |
|---|---|
| `mix`: `fg → b`, `bg → a` | K-01 |
| Compositing blends: same swap | K-02 |
| `facingratio`: `1 − Facing` | K-10 |
| `viewdirection`: negate | K-11 |
| `geomcolor`: `attribute = displayColor` | K-06 |
| `saturate`: `rgb_to_bw` + `mix_color` | K-08 |
| `UsdUVTexture.sourceColorSpace` names | K-15 (part) |

Done when: the phase-0 cases pass, and a Solaris scene with a
`mix(texA, texB, mask)` shows texA where the mask is white.

## Phase 2 — Closures and volumes (2-3 days)

> **Status 2026-10-07: done** (patch 0078), in an afternoon rather than days.
> Closure families dispatched by suffix, `volume` added, `layer` as a
> Fresnel-weighted mix, `conductor` on `metallic_bsdf`, output lookup by
> socket class when the name fails. `mtlx_inputs.py`: 528 clean, 0 output
> missing, 0 node missing. Left for later: a volume value case, a conductor
> reference, and the one-line "approximate" log for K-14.

| Task | Closes |
|---|---|
| Type dispatch in `FindMtlxMapping` on the nodedef suffix: `_bsdf`, `_edf`, `_vdf`, `_surfaceshader`, `_displacementshader`, `_volumeshader` route to closure mappings before the colour table | K-03 |
| `mix_*` closures → `mix_closure` (fg on Closure2), `add_*` → `add_closure`, `multiply_*C/F` → `mix_closure` against `transparent_bsdf` with `fac = weight` | K-03 |
| `ND_volume` → `add_closure(vdf, edf)`; `volume` family removed from the coverage exclusions | K-04 |
| `layer`: choose and document the approximation (`add_closure` for coats; log once) | K-09 |
| `conductor_bsdf` → `metallic_bsdf` physical conductor | K-13 |
| Log one "approximate" line per material for K-14 closures | K-14 |

Done when: a MaterialX material built in Houdini's USD MaterialX Builder with
`mix_bsdf(dielectric, oren_nayar, mask) → surface` renders both lobes; a
`volume(anisotropic_vdf)` on a VDB renders as the Karma reference within
tolerance; `bench_mtlx.py` has one case per closure family.

## Phase 3 — Types everywhere (2 days)

> **Status 2026-10-07: main row done** (patch 0079): vector twins for every
> math family, plus `ln`, `modulo`, `atan2` fixed in scalar form; 15 bench
> cases. Left: `heighttonormal` (K-12), `geompropvalue` vector outputs,
> colour4 alpha (K-17), `texcoord.index` and object-space normals (K-18).

| Task | Closes |
|---|---|
| Generalise the scalar/vector split: every `MakeMtlxOp` family gets a vector twin selected by `isVector`; `clamp`/`remap`/`smoothstep` switch `data_type`/`clamp_type` to vector; power/sqrt/exp/ln on colour via three scalar helpers on `separate_color` → `combine_color` | K-07 |
| `heighttonormal`: tangent-space normal map output | K-12 |
| `geompropvalue` colour/vector outputs | - |
| Colour4/alpha: `image_color4` → `color` + `alpha` pair, `separate4.outa` | K-17 |
| `texcoord.index` → `uvmap` node; `normal`/`tangent` object space via `vector_transform` | K-18 |

Done when: `bench_mtlx.py` runs every `_color3` and `_vector3` variant of
every mapped math family against its scalar twin on a grey input (must match)
and on a coloured input (must *not* be grey).

## Phase 4 — Surfaces beyond standard_surface (3 days)

> **Status 2026-10-07: done** (patch 0080), with one finding the plan had
> not foreseen: every surface model took Cycles' defaults for the inputs
> Houdini leaves unwritten (K-55) - an untouched UsdPreviewSurface rendered
> four times too bright. `tools/mtlx_defaults.py` now guards that for all
> five models. OpenPBR, glTF and Disney have their own tables;
> UsdUVTexture channels (K-56), scale/bias, UsdTransform2d and the `kma`
> context are handled. Left: `specular_rotation`, `coat_affect_*`, the
> preview surface's displacement, `fallback`.

| Task | Closes |
|---|---|
| `open_pbr_surface` table, built from `bxdf/open_pbr_surface.mtlx`, with MaterialX defaults pinned; coat darkening and fuzz as documented approximations | K-05 |
| `gltf_pbr` and `disney_principled` tables | K-05 |
| `UsdUVTexture` `scale`/`bias`/`fallback`, `UsdTransform2d` → `mapping`, `UsdPreviewSurface.displacement` | K-15 |
| Read the `kma` network after `mtlx` | K-16 |
| `standard_surface`: `coat_affect_color/roughness`, `specular_rotation` investigation (STANDARD_SURFACE_AUDIT) | - |

Done when: an OpenPBR audit like STANDARD_SURFACE_AUDIT.md shows every input
measured; a `UsdPreviewSurface` with a normal map matches Karma's; a Karma
Material Builder material renders its MaterialX network, not the preview
fallback.

## Phase 5 — Curves, points and instances (3 days)

This is the phase the author's own yarn work needs.

| Task | Closes |
|---|---|
| ✅ `widths` `varying` resampled to keys, for curves and points (0081) | K-21 |
| ✅ Bézier and B-spline → Catmull-Rom keys; periodic closed; `curveIndices` expanded (0081) | K-20 |
| ✅ `cycles:curve_shape` (per `Hair` in this Cycles, so live; 0081). `hair_subdivisions` still to do | K-22 |
| ✅ Instance primvars sampled across the shutter; per-instance `displayColor` and `instance`-interpolated primvars as object attributes (0082) | K-23 |
| ✅ Implicit surfaces: tessellated by our own scene index (Hydra's is too coarse) (0083) | A1 |

Done when: a `md_seams` yarn scene renders with round, thick curves and
matches Karma's silhouette; a Bézier curve from a hand-written USD passes
through its on-curve points; a PointInstancer with animated positions blurs
by the same length as its prototype.

**Status 2026-10-07: done** (patches 0081-0085), but for the `md_seams` yarn
scene, not rendered yet. Hand-written curves match Karma's silhouette
(`bench_curves.py --karma`: IoU 0.89-1.00); instances blur by their
prototype's length (`bench_motion.py`); K-30 was brought forward from phase 6
because round implicit surfaces needed it looked at.

## Phase 6 — Production output (4-5 days)

| Task | Closes |
|---|---|
| Pass table extended to every Cycles `PassType` with Houdini spellings; shader AOVs from `aov_output` names; cryptomatte object/material/asset with the film settings it needs | K-25 |
| ✅ Film settings: transparent background, transparent glass, exposure, pixel filter (0086) | K-26 |
| `primvars:cycles:object:*`: ray visibility, holdout, shadow catcher, light group, caustics, dicing rate, adaptive subdivision; read in `geometry.inl` | K-27 |
| Light linking and shadow linking from Hydra categories | K-24 |
| Render tags honoured; proxy/render purposes measured | K-28 |
| ✅ Subdivision independent of `refineLevel`; `cycles:max_subdivisions` setting (0084, done early with A1) | K-30 |
| `background = true` under husk, measured against Karma on three scenes | K-29 |
| ✅ Motion blur toggle symmetric (0086); `shadow:color`, light multipliers still to do | K-34 |
| ✅ Volume field aliases (`vel`, `Cd`) (0086) | K-33 |

Done when: a Karma ROP-style render settings node produces beauty, depth,
normal, diffuse/glossy/transmission, cryptomatte and two shader AOVs through
husk, with a transparent background under a dome light, with one object
hidden from camera rays and one light linked to one object.

## Phase 7 — Interactivity (open-ended, after phase 0's measurement)

| Task | Closes |
|---|---|
| Act on the phase-0 attribution of the 4 s | K-31 |
| Try-lock with a deferred re-execute instead of a blocking lock | K-32 |
| Vulkan Hgi: either a Vulkan interop display driver or a cheaper readback path; at least log which path is active at startup (already done) | - |
| COP cache eviction on material finalize; cap by bytes | K-41 |
| MaterialX-to-OSL for the nodes a node graph cannot express (`switch`, `swizzle`, `extract`, matrices), CPU and OptiX only, behind a setting | - |

Done when: a material edit on the user's reference scene shows in under one
sample time on CPU, and the UI thread never blocks longer than 100 ms in the
stopwatch log.

## Phase 8 — Repository hygiene (continuous, finish by phase 4)

| Task | Closes |
|---|---|
| Translate comments and log messages to English, file by file as each is touched; no new French in code from today | K-53 |
| `bootstrap.py` re-run on a clean clone in a temporary directory; record the time and the result in ENVIRONMENT.md | - |
| Automate `op:` flattening in a USD Render ROP pre-render script, or document the farm workflow in one place | K-40 |
| `preview translator` scope stated in the README | K-42 |

## What is explicitly deferred

- Linux and macOS builds.
- Point Density and OSL Script nodes (absent from Cycles' registry).
- MaterialX nodes with no Cycles equivalent: matrices, alpha compositing,
  `time`/`frame`, `blur`.
- A second look at the display driver's "wrong pixels" report: it has not
  reappeared since the three crash fixes; it is reopened only if seen again.

## How to use this plan

Take phases in order; inside a phase, tasks are independent unless a row says
otherwise. When a task lands: close its K-number here and in KNOWN_ISSUES.md,
flip the row in PROGRESS.md, regenerate the patch series, and add the
verification command to TESTING.md. A phase without its "done when" test is
not closed, however much code it contains.
