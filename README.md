# Cycles for Houdini

Blender's [Cycles](https://projects.blender.org/blender/cycles) as a Hydra render
delegate for **Houdini 22 / Solaris**, with its shading nodes exposed natively in
Houdini and a **Cycles Material Builder** to wire them in.

> Not to be confused with [boberfly/hdcycles](https://github.com/boberfly/hdcycles),
> a separate and older Hydra delegate for Cycles. This project builds on the
> delegate that ships **inside Cycles itself**, under `src/hydra`, which already
> carries official Houdini support upstream.

## What it adds

Cycles' own delegate renders geometry, lights and cameras; the shading side is
where the work went.

- **163 Cycles shader nodes published to USD**, discovered from Cycles' node
  registry at runtime, so the node set always matches the linked Cycles version.
- **A Cycles Material Builder** — a dedicated LOP context holding every Cycles
  node in Blender's own categories, with Blender's parameter groupings, and
  without MaterialX or Karma nodes mixed in.
- **MaterialX to Cycles translation** inside the delegate, so a MaterialX network
  authored anywhere in a USD pipeline renders in Cycles. Includes MaterialX's
  procedural noise implemented exactly, as native SVM and OSL kernel nodes.
  Both follow Ben Houston's work — see [Credits](#credits). Nodes the table
  does not hold but the MaterialX library defines as nodegraphs - `switch`,
  `ramp4`, `hsvadjust`, `colorcorrect`, every `hmtlx*` node of Houdini - are
  expanded into their inner nodes at translation time, read from Houdini's
  own library.
- **Copernicus COP textures read live**, without a round trip through disk.
  This needs a live Houdini: under husk (a USD Render ROP, a farm) there is no
  node graph to cook, so put the **Flatten COP Textures** LOP
  (`hdcycles::flatten_op_textures`) before the render node - it cooks every
  referenced COP to an image file and rewrites the paths on its own layer.
- Motion blur on animated transforms **and on deforming geometry** — meshes,
  curves and point clouds alike, from time-sampled points or from a
  `velocities` field, so a simulation whose point count changes still blurs;
  **PointInstancer instances blur** too, and carry their per-instance primvars.
- **USD curves where USD puts them** — Bézier, B-spline, Catmull-Rom,
  periodic, pinned, `varying` widths — rendered as round tubes by default.
- **USD implicit surfaces** (Sphere, Cube, Cylinder, Cone, Capsule, Plane).
- **Render outputs the way a Karma Render Settings node writes them**: every
  Cycles pass by name, Karma's light-component names and light path
  expressions in Karma's convention, cryptomatte with its manifest, light
  groups, shader AOVs. Film transparency, exposure and pixel filter as render
  settings.
- **Per-object properties** from the Render Geometry Settings node: ray
  visibility, holdout, shadow catcher, caustics, light group, dicing rate -
  and Karma's own visibility and holdout properties read as well.
- **Light linking and shadow linking**, the diffuse/specular light
  multipliers (as on/off: Cycles cannot scale a lobe).
- Displacement, render settings surfaced in Solaris, and a long list of crash
  and correctness fixes to the delegate. Every claim here comes from a bench:
  see [docs/TESTING.md](docs/TESTING.md).

The viewport preview of a Cycles material (the GL shader Houdini draws before
a render) follows one texture per input: a mix of two textures, a procedural
or a ramp shows as the input's default value. It is a preview, not a link to
the Cycles nodes.

Rendering is CPU and CUDA/OptiX, chosen from **Render › Cycles Render Device**.
The device is fixed when the render session is built, so it cannot come from a
Render Settings node — and it describes the machine rather than the scene, so it
is a per-installation preference the `.hip` does not carry.

The GL display driver is on **when Houdini's viewport runs on OpenGL**: Cycles
then writes straight into a texture the host owns, which is what makes the
viewport refresh as promptly as Blender's. Under a Vulkan viewport, and under
husk, rendering goes through the output driver and the buffer is read back on
every refresh. The display driver misbehaved in Houdini's viewport in four
distinct ways; three were crashes, all fixed and documented in the patch
series. The fourth, wrong pixels, has never been confirmed fixed and only shows
in the viewport — `CYCLES_DISPLAY_DRIVER=0` falls back to the output driver.

## Cycles versions

Two engines can be installed side by side and switched with one word in the
Houdini package file.

| | Cycles | Base commit | Notes |
|---|---|---|---|
| `install` | 5.2 | `3b97e190` (`release/5.2`) | stable |
| `install-53` | 5.3 dev | `8424ed53` (`main`) | **default** — adds dispersion |

5.3 brings **dispersion** on the Principled BSDF: two sliders in the Transmission
section, an amount and an Abbe number, from which the per-wavelength IOR is
derived. The path only turns spectral when both weights are non-zero, so nothing
changes for materials that do not use it.

See [docs/CYCLES_53.md](docs/CYCLES_53.md) for the parallel install.

## Requirements

The delegate links against the USD, Python and image libraries Houdini ships,
so it is bound to a Houdini series rather than to a single build. Symbols carry
USD's versioned internal namespace (`pxrInternal_v0_26_5`), which means a
Houdini on a different USD will refuse to load it outright rather than
misbehave. Any Houdini 22.0 build should do; 22.5 and beyond will need a
rebuild, and so will the Python 3.11 flavour.

| | |
|---|---|
| Houdini | 22.0 series, built against **22.0.368** (USD 26.05, Python 3.13, MaterialX 1.39.5) |
| OS | Windows 11, MSVC 14.44 (VS2022 Build Tools) |
| GPU | CUDA 12.9 + OptiX SDK, or CPU only |
| Also | CMake 3.28+, git, git-lfs |

## Building

Cycles itself is not vendored here. The build clones it at the pinned commit,
applies the patch series, and installs into `install-53/`.

```
python tools/bootstrap.py --version 5.3
```

The VOP library is not shipped: it is generated from the Sdr registry the built
delegate publishes, so it always matches the Cycles you compiled. Generate it
once the install exists, with Houdini's Python:

```
hython tools/build_cycles_vops.py
```

Then point Houdini at the result by copying the generated package file:

```
copy install-53\houdini\packages\cycles.json %USERPROFILE%\Documents\houdini22.0\packages\
```

The package is generated at install time from `CMAKE_INSTALL_PREFIX`, so it
carries your own paths — there is nothing to edit by hand.

## Repository layout

| | |
|---|---|
| `patches/5.2/`, `patches/5.3/` | our changes to Cycles, one commit per subject |
| `tools/` | the Material Builder generator, the test benches, bootstrap |
| `tests/` | the node bench and its references, the MaterialX scenes, the feature scenes — see [tests/README.md](tests/README.md) |
| `docs/` | the project map — start at [docs/README.md](docs/README.md) |

The patch series is the interesting part: each patch is a self-contained fix with
a message explaining the bug it addresses. A dozen of them are plain bugs in the
upstream delegate and are candidates for contribution back to Blender.

## Documentation

| | |
|---|---|
| [docs/GOALS.md](docs/GOALS.md) | what "working correctly" means, and what is out of scope |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | the four layers, every file's role, the data path, the MaterialX mapping machinery |
| [docs/PROGRESS.md](docs/PROGRESS.md) | the feature matrix: works / partial / missing / wrong, with how each was verified |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | numbered defects with the file and line |
| [docs/PLAN.md](docs/PLAN.md) | the phases that take the project to its goals, each with its acceptance test |
| [docs/TESTING.md](docs/TESTING.md) | the benches, what each proves, and the regression suite to build |
| [docs/STATUS.md](docs/STATUS.md) | the dated journal of what was tried and measured (French) |

## Testing

Every published node gets its own USD scene, is rendered, and is checked for
warnings, for a non-black image, and for a difference against a baseline:

```
hython tools/bench_export.py && python tools/bench_render.py && hython tools/bench_diff.py
```

97 nodes pass that check against their committed reference images, and the
full MaterialX scene renders bit-identical between 5.2 and 5.3. A second
command renders seven materials with Cycles and with Karma from the same USD
and compares them region by region (`hython tools/bench_agree.py`, 21 checks,
floor within 1 %). What each bench does and does not prove is set out in
[docs/TESTING.md](docs/TESTING.md).

## Known gaps

The complete list, with line numbers, is [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).
The ones a user meets first:

- MaterialX: 796 of the library's 822 shading nodedefs are rendered - 666
  by the mapping table, 80 by expanding a nodegraph (the library's own, or
  one the delegate ships for nodes the library writes in GLSL only), 50 by
  rewriting (`extract`, `swizzle`, `transformmatrix`, a 1.38 thin film); of
  the 789 that route, 641 keep every input when rendered
  (`tools/mtlx_inputs.py`), and 67 are
  value-checked against the MaterialX definition (`tools/bench_mtlx.py`).
  Out: the matrix nodes other than a constant `transformmatrix`, the colour4
  compositing nodes (an image's own alpha does pass), `time`/`frame`,
  `thin_surface` - Cycles' node graph has no
  equivalent, and OSL is not an option against Houdini (its OpenImageIO is
  2.5, Cycles' OSL is built on 3.1; Houdini ships no usable OSL).
- Cycles has no light path expressions: Karma's usual LPEs are mapped to the
  Cycles pass holding the same light, any other one renders black and says so
  in the log.
- `shadow:color` and fractional diffuse/specular light multipliers are not
  supported by Cycles.
- Implicit surfaces carry no UVs.
- An intermittent CUDA "illegal address" on some scene edits, under investigation.

## Credits

The MaterialX translation is built on the map drawn by **Ben Houston**:

- **[blender-materialx-importer](https://github.com/bhouston/blender-materialx-importer)**
  (MIT) — a validated MaterialX importer for Blender, and the reference for
  which MaterialX nodes to carry over to Cycles and how. Its list of supported
  node categories was the first checklist of the coverage work, before
  `tools/mtlx_coverage.py` measured against the whole MaterialX library.
- **[Blender PR #158054](https://projects.blender.org/blender/blender/pulls/158054)**
  (Apache 2.0) — MaterialX-compatible noise shader nodes, validated pixel for
  pixel against the MaterialX reference renderer by his
  [material-fidelity](https://material-fidelity.ben3d.ca) suite. Its Cycles side
  — the exact noise and hex-tiled image nodes — is carried as patch `0025`.

Cycles itself, and the Hydra delegate this project extends, are the Blender
Foundation's and its contributors'.

## Licence

Apache 2.0, matching Cycles. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
