# Architecture

## The four layers

```
 Houdini / Solaris / husk
 ───────────────────────────────────────────────────────────────────────
 4. Houdini-side resources        VOP library, Material Builder, render
    (Python, .ds, .xml, .hda)      properties, preview translator, device menu
 ───────────────────────────────────────────────────────────────────────
 3. hdCycles.dll                  HdRenderDelegate + Sdr plugin, in one DLL
    src/hydra/plugin.cpp
    src/hydra/sdr_cycles.cpp
 ───────────────────────────────────────────────────────────────────────
 2. cycles_hydra (static)         the delegate proper: prims, materials,
    src/hydra/*.cpp               render pass, drivers, COP reader
 ───────────────────────────────────────────────────────────────────────
 1. Cycles                        scene, kernels, devices - upstream, plus
    external/cycles-53            74 patches (patches/5.3)
```

Layers 2 and 3 are upstream code (Blender ships this delegate under
`src/hydra`) carrying our patches. Layer 4 is entirely ours and lives in
`src/hydra/resources/`. Everything below `external/` is a git worktree on the
branch `houdini-fixes-53`; the repository tracks the *patches*, not the tree.

## Where each file is, and what it does

### Layer 1 - Cycles patches that are not in `src/hydra`

| Patch | Files | What |
|---|---|---|
| 0025 | `kernel/svm/mx_noise.h`, `mx_hextile.h`, `scene/shader_nodes.cpp` | MaterialX-exact noise and hex-tiled image nodes (Ben Houston, Blender PR 158054) |
| 0038 | `kernel/closure/bsdf_microfacet.h`, `scene/shader_nodes.cpp` | Dispersion on the Principled BSDF (Blender PR 162041) |
| 0046 | `kernel/svm/closure.h` | Random Walk (Legacy) missing from the closure skip table |
| 0054 | `scene/mesh_displace.cpp`, `scene/mesh.cpp` | Displacement made idempotent across material edits |
| 0072 | `device/device.cpp` | One-time warning when memory falls back to the host |

Everything else is in the delegate.

### Layer 2 - the delegate

| File | Role | Our changes |
|---|---|---|
| `render_delegate.cpp/.h` | Prim factory, render settings, device choice, material contexts | GPU resolution order, `dicing_rate`, late-setting warnings, `kma` context, display-driver switch |
| `session.cpp/.h` | Owns the Cycles `Session`, AOV→pass map, default background | Houdini AOV names (`C`, `N`, `P`, `Pz`), shutter and dicing-rate state |
| `render_pass.cpp` | Runs once per host frame: lock, COP poll, AOVs, camera, reset, draw | Blocking lock, dicing camera, camera-switch detection, stopwatch log |
| `geometry.inl/.h` | Shared Sync for mesh/curves/points/volume: material, transform, instances, motion blur | Transform motion blur, shutter from settings, fps from scene globals |
| `mesh.cpp` | Topology, points, normals, primvars, subdivision, creases | Corner normals, smooth flag from normals, deformation blur, dicing rate, undisplaced reset |
| `curves.cpp`, `pointcloud.cpp` | Hair and points | Deformation and velocity blur |
| `instancer.cpp` | Instance transforms, nested instancers | Quaternion array types |
| `light.cpp` | USD lights → Cycles lights | Intensity units measured against Karma, cylinder lights, object tagging |
| `camera.cpp` | USD camera → Cycles camera, DoF, shutter samples | - |
| `material.cpp` | **The largest file.** Material networks → shader graphs: native Cycles nodes, `UsdPreviewSurface`, and the MaterialX table | Everything MaterialX, ramps, UDIM, shader settings, image handle refresh, COP binding, terminal lookup |
| `node_util.cpp` | VtValue ↔ Cycles socket conversion | Scalar↔vector spreading, enum validation, `op:` paths kept |
| `util.cpp` | Primvar helpers, motion sampling | Velocity/acceleration sampling, motion position writer |
| `houdini_cop.cpp` | Reads Copernicus layers through `hou`, caches pixels, polls for changes | New file |
| `display_driver.cpp` | GL interop: Cycles writes into a texture the host owns | Context creation order, lock ownership, teardown with a current context |
| `output_driver.cpp`, `render_buffer.cpp` | The non-GL path: copy pass pixels into Hydra buffers | - |
| `field.cpp`, `volume.cpp` | OpenVDB grids as Cycles volumes | Default volume shader for unbound volumes |
| `file_reader.cpp` | Standalone `cycles` executable reading USD; unused by Houdini | - |

### Layer 3 - the plugin DLL

| File | Role |
|---|---|
| `plugin.cpp` | Registers `HdCyclesPlugin` (CPU) and `HdCyclesPluginGPU`; seeds the device from the variant and `CYCLES_DEVICE`; `CYCLES_LOGGING`, `CYCLES_LOG_FILE` |
| `sdr_cycles.cpp` | Enumerates Cycles' node registry at runtime and publishes every `SHADER` node to USD's Sdr as `cycles_<name>`, with types, defaults, enum options, connectability and widget hints |
| `plugInfo.json` | USD plugin manifest, paths filled by CMake |

### Layer 4 - Houdini resources (`src/hydra/resources/`)

| File | Installed to | Role |
|---|---|---|
| `cycles.json.in` | `houdini/packages/` | The Houdini package: `HOUDINI_PATH` and `PATH` to `$HOUDINI_PACKAGE_PATH/CyclesForHoudini/houdini` (layout built by `tools/make_dist.py`) |
| `UsdRenderers.json` | `houdini/` | Menu labels "Cycles CPU" / "Cycles GPU", husk defaults |
| `HdCyclesPlugin*_Global.ds` | `houdini/soho/parameters/` | Render Settings tab, **generated** by `tools/gen_render_properties.py` from the integrator's sockets |
| `cycles_builder.py`, `CyclesTools.shelf` | `scripts/python/`, `toolbar/` | The Cycles Material Builder: a configured subnet with a three-input `suboutput` and a tab-menu mask |
| `husdplugins/shadertranslators/cycles.py` | `houdini/husdplugins/shadertranslators/` | Two translators: material *settings* (`cycles:<socket>` on the terminal shader) and the `UsdPreviewSurface` *preview* derived from the Cycles graph |
| `cycles_device.py`, `MainMenuCommon.xml`, `pythonrc.py` | `scripts/python/`, `houdini/`, `scripts/` | Render › Cycles Render Device menu, persisted in `$HOUDINI_USER_PREF_DIR/cycles_device.pref` |
| `cycles_colorspaces.py` | `scripts/python/` | Colour-space menu for image nodes, from the live OCIO config |
| `flatten_op_textures.py`, `otls/hdcycles_flatten_op_textures.hda` | `python3.Xlibs/`, `otls/` | Bakes `op:` textures to files for farm renders |

Not shipped, generated on the user's machine: `install-53/houdini/otls/cycles_vops.hda`
by `tools/build_cycles_vops.py`, so the VOP set always matches the compiled Cycles.

## The data path, end to end

```
USD stage ── UsdImaging scene index ── Hydra render index
                                             │ Sync() per prim
                                             ▼
   HdCyclesMesh / Curves / Points / Volume / Light / Camera / Material
                                             │ SceneLock
                                             ▼
                      ccl::Scene (geometry, objects, lights, shaders)
                                             │ HdCyclesRenderPass::_Execute
                                             ▼
                 ccl::Session ── device_update ── path trace ── drivers
                                                                 │
                       GL display driver (texture) ◄─────────────┤
                       output driver (Hydra render buffers) ◄────┘
```

Three things to know about this path:

1. **Materials are synced before geometry asks for them.** `HdCyclesGeometry::Sync`
   looks the material up in the render index; if the material failed to
   translate, the geometry gets `default_surface` (grey) or `default_volume`.
2. **`_Execute` runs on the host thread** and takes `scene->mutex` for real
   (patch 0014). Whatever the render thread is doing under that lock - a
   device update, a BVH build - freezes Houdini's UI for that long. The
   stopwatch in `render_pass.cpp` logs the split when a pass exceeds 50 ms.
3. **Only authored parameters arrive.** A MaterialX network that never writes
   `transmission_dispersion` sends nothing for it, so every mapping pins the
   MaterialX default through `setFixedValues` where Cycles' default differs.

## The MaterialX translation, in one page

Everything is in `material.cpp`, in a block meant to be removable the day
Cycles reads MaterialX itself.

- **Lookup**: `FindMtlxMapping(nodedef)` - four arithmetic families are split
  scalar/vector by the nodedef's type suffix; `convert_*_surfaceshader` is
  special-cased; everything else is **longest matching prefix** in
  `MtlxTable()`.
- **A mapping** (`UsdToCyclesMapping`) names the Cycles node type, a map from
  MaterialX input/output names to Cycles socket names, fixed values applied at
  creation, and *helpers*: auxiliary Cycles nodes created alongside, wired by
  socket name, addressable as `"helper:socket"`. A helper can also sit *after*
  the main node (`takesMainOutput`), which is how `standard_surface` grows a
  separate glass lobe.
- **Multi-targets**: a MaterialX input may drive several sockets, `"a;b"`,
  for values and for connections alike.
- **Value rewrites**: a subclass can transform a value in `parameterName()`
  (wrap modes, Chiang roughness → beta).
- **Two outputs for one `out`**: `MtlxFacOrColor` picks `fac` or `color` from
  what the connection feeds; the MaterialX noise picks it from the nodedef
  variant (`_float` vs `_color3`), which is the right way - see KNOWN_ISSUES
  for where the connection-based choice still misleads.

The limits of this design, which [PLAN.md](PLAN.md) works around rather than
rewrites: one Cycles node per mapping plus helpers (no general subgraph), no
per-nodedef type dispatch outside the four arithmetic families, and a
coverage tool that measures prefixes, not correctness.

## Build and install

```
python tools/bootstrap.py --version 5.3        # clone, git am, cmake, build, install
hython tools/build_cycles_vops.py              # VOP library from the Sdr registry
hython tools/gen_render_properties.py          # Render Settings tab (after a Cycles update)
```

Incremental, once configured:

```
cd external/cycles-53 && cmake --build build --config Release --target install --parallel
```

Houdini locks `hdCycles.dll`: with Houdini open the install step fails with
`Permission denied` buried in an MSB3073 error, and the previous DLL stays.
Check the DLL's timestamp, or grep it for a string from the new code. Never run
two builds at once: the second links stale objects.

Regenerate the patch series after any commit on the worktree:

```
cd external/cycles-53 && git format-patch --no-signature -o ../../patches/5.3 8424ed53..HEAD
```

## Environment variables

| Variable | Effect |
|---|---|
| `CYCLES_DEVICE` | `CPU`, `GPU`, `OPTIX`, `CUDA`, `HIP`, `ONEAPI`, `METAL`; read when the delegate is created |
| `CYCLES_DISPLAY_DRIVER` | `0` forces the output driver even under OpenGL |
| `CYCLES_COP_WATCH` | `0` stops polling Copernicus nodes for changes |
| `CYCLES_LOGGING`, `CYCLES_LOGGING_LEVEL` | Cycles' own logger (`info`, `warning`, ...) |
| `CYCLES_LOG_FILE` | Write that log to a file - Houdini has no console on Windows |
| `CYCLES_DUMP_PRIMS` | `1` logs each prim the scene index adds, with its data source (needs the logger at `info`) |
| `HD_CYCLES_DUMP_GRAPH` | Directory; one `.dot` per translated material |
