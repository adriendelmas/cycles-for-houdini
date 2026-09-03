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
- **Copernicus COP textures read live**, without a round trip through disk.
- Motion blur on animated transforms **and on deforming geometry** — meshes,
  curves and point clouds alike, from time-sampled points or from a
  `velocities` field, so a simulation whose point count changes still blurs.
- Displacement, render settings surfaced in Solaris, and a long list of crash
  and correctness fixes to the delegate.

Rendering is CPU and CUDA/OptiX, chosen from **Render › Cycles Render Device**.
The device is fixed when the render session is built, so it cannot come from a
Render Settings node — and it describes the machine rather than the scene, so it
is a per-installation preference the `.hip` does not carry.

The GL display driver is on, which is what makes the viewport refresh as
promptly as Blender's. It misbehaved in Houdini's viewport in four distinct
ways; three were crashes, all fixed and documented in the patch series. The
fourth, wrong pixels, has never been confirmed fixed and only shows in the
viewport — `CYCLES_DISPLAY_DRIVER=0` falls back to the output driver.

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
| `tests/usd/` | 97 single-node scenes and their reference images |
| `docs/` | build notes, status, audits — **in French** |

The patch series is the interesting part: each patch is a self-contained fix with
a message explaining the bug it addresses. A dozen of them are plain bugs in the
upstream delegate and are candidates for contribution back to Blender.

## Testing

Every published node gets its own USD scene, is rendered, and is compared against
a reference to confirm it actually changes the image.

```
python tools/bench_export.py && python tools/bench_render.py && python tools/bench_diff.py
```

97 nodes, 0 failures on both engines. The full MaterialX scene renders
bit-identical between 5.2 and 5.3.

## Known gaps

- Karma's own material context (`kma:`) falls back to UsdPreviewSurface.
- An intermittent CUDA "illegal address" on some scene edits, under investigation.

## Licence

Apache 2.0, matching Cycles. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
