# Testing

What exists, what each bench actually proves, and what a real regression
suite needs. Numbers quoted in the README must come from a command on this
page.

## Running anything outside Houdini

All benches drive `husk.exe` and `hoiiotool.exe` from `$HFS/bin`. On this
machine three things are needed or the plugin is not found and the images are
wrong:

```bash
export HOUDINI_USER_PREF_DIR="C:/Users/<you>/Documents/houdini22.0"   # the real pref dir, holds packages/cycles.json
export MSYS_NO_PATHCONV=1                                             # Git Bash: keep /Render/settings intact
export CYCLES_INSTALL_DIR=install-53                                  # which engine the benches target
export HFS="C:/Program Files/Side Effects Software/Houdini 22.0.368"  # only for the benches run with plain python; hython sets it
```

Reference images are rendered at **120×90**; comparing at another resolution
fails every scene at once. If `hserver -l` shows `Connection Error`, restart
it with `hserver -S https://www.sidefx.com/license/sesinetd`.

To read the delegate's log from a live Houdini, start it with
`tests/houdini/launch_cycles_log.cmd [scene.hip]`: the log lands in
`tests/scratch/cycles_viewport.log`, each line stamped with the seconds since
the first one. The launcher also starts the houdini-mcp server on scene load
(`tests/houdini/autostart/scripts/456.py`, put first on `HOUDINI_SCRIPT_PATH`),
so `python tools/hou_remote.py -c "<python>"` (or a script file) runs code in
that session at once and prints what it printed - the way to drive the
viewport, the display driver and Solaris' scene index from a bench. Two
things learnt driving it (2026-10-08): `hou.ui.waitUntil` is the pause that
lets the viewport redraw between steps, and a camera set from Python
(`setDefaultCamera` + `triggerUpdate`) reaches Hydra only when the viewport
repaints, which it did one move in six; `frameAll`, `home`, `setCamera` and
scene edits went through every time.

To test a freshly built DLL while Houdini holds the installed one: set
`HOUDINI_PACKAGE_SKIP=1`, point `PXR_PLUGINPATH_NAME` at a temporary plugin
tree, and put the Houdini and install `bin` directories on `PATH` in POSIX
form (`/e/...`). `HOUDINI_PACKAGE_SKIP` also drops Houdini's OCIO config,
and without one Cycles stores an 8-bit sRGB texture encoded instead of
decoded - three times too bright - while Karma complains it has no working
space: set `OCIO` to `$HFS/packages/ocio/houdini-config-*.ocio` for any
measurement with textures (`bench_usdtex.py` does it itself). A bench run
under hython loads the packages, so husk then takes the **installed** DLL,
not the one on `PXR_PLUGINPATH_NAME`: install before measuring.

Writing a scene by hand: a `DistantLight` needs `inputs:normalize = 1` to
light anything. Unnormalized, USD reads its intensity as the radiance of the
sun disk, so the illuminance is intensity × the disk's solid angle - about
7e-5 at the default 0.53°. Karma and the delegate agree on both (measured
2026-10-07, white plane: 0.318 vs 0.317 normalized, 0.0019 vs 0.0019 at 5°);
Houdini's Distant Light LOP turns it on. `tests/scenes/smoke.usda` predates
this and its sun contributes nothing. Also give the stage `metersPerUnit = 1`:
without it a camera aperture is read in centimetres. Do not name a primvar
after a Cycles standard attribute (`heat`, `density`, `color`, `temperature`,
`flame`...): an attribute node asks for the standard one instead.

## The benches, and what each proves

| Command | Scope | Proves | Does **not** prove |
|---|---|---|---|
| `hython tools/bench_export.py` | 97 native Cycles VOPs | Each VOP exports through the real Solaris translator to USD | Values |
| `python tools/bench_render.py` | Same 97 scenes | No delegate warning, image present, not black; renders into `tests/nodes/5.3/output/` (ignored) | That the image is right |
| `hython tools/bench_diff.py [--accept node\|all]` | `output/` vs `references/` | Each node matches its committed reference (off by less than `1e-3` absolute or 1 % relative on 99.5 % of pixels); lists nodes inert against `_baseline.exr`; `cycles_set_normal` is reported, not counted (A19) | - |
| `hython tools/bench_mtlx.py [name]` | 93 cases: MaterialX nodes (+5 textured with `CYCLES_BENCH_TEXTURE`, Karma's hextiled triplanar among them), colours, closures, and the nodes expanded from their nodegraph (`exp_*`) | Rendered colour within 2 % of a value **computed from the MaterialX definition**, file named next to each formula | Anything the plane's mean cannot see: directions, volumes |
| `hython tools/bench_hair.py` | 4 pairs | MaterialX Chiang hair equals native principled hair, error < 1e-3 | - |
| `hython tools/mtlx_karma.py [--list] [--closures] [pattern]` | Every value nodedef (695), one unlit quad each - or with `--closures` the 45 BSDF, EDF and surface nodedefs under a white dome - rendered by Cycles and by Karma from the same file | Which nodes give Karma's value - 625 values and 38 closures on 2026-10-08, images read from a four-corner texture and compared by quarters; the rest are listed and explained in K-61, K-64 | Nodes whose value is each engine's own (noise); the shape of a lobe |
| `hython tools/surface_audit.py [nodedef] [pattern]` | Every value input of a surface model (OpenPBR by default; standard_surface, glTF, `UsdPreviewSurface`), moved off its default alone on the agreement sphere | The input's effect on the sphere has Karma's sign and is within a factor of two of it; which inputs neither engine shows at that setting | Lobe shapes; the models' own differences (K-63 lists them) |
| `hython tools/bench_volume.py` | A cube of medium in front of a white `surface_unlit` wall, no other light: MaterialX `absorption_vdf` and `anisotropic_vdf` (absorbing, scattering), native, and a `leftHanded` cube | Absorption transmits exp(-2 sigma) within 0.02 - Karma renders no volume on a mesh without a surface, so the law is the reference; a scattering `anisotropic_vdf` as Cycles' own scatter volume with the same coefficient (K-92) | Scattering against another engine |
| `hython tools/bench_usdtex.py` | A four-corner texture on a quad: `UsdUVTexture` plain, tiled, rotated, translated, outside the image, scale/bias, an 8-bit PNG as sRGB, raw and auto; a MaterialX `image` with and without a colour space; two UDIM tiles, `<UDIM>` and Houdini's `%(UDIM)d`; a left-handed subdivided grid with UVs per corner and per vertex; a missing file with and without `fallback` | Each quarter within 0.03 of Karma, under Houdini's OCIO config (K-66) | `useMetadata` with metadata in the file |
| `HOUDINI_PATH="<install>/houdini;&" hython tools/bench_cop_rop.py` (a Windows path: `$(pwd -W)` under Git Bash) | A red constant COP read through `op:` by a LOP-authored quad, rendered through fresh USD Render ROPs | The ROP gets the COP output processor on creation, and Karma and Cycles both render the COP's red (K-40) | `op:` paths in sublayered files on disk |
| `HOUDINI_PATH="<install>/houdini;&" hython tools/bench_preview.py` | Cycles VOP networks built in hython - an image, through a gamma, on either side of a mix, two images mixed, two colours mixed - on a principled's base colour | The viewport preview's diffuse colour reads the right texture or holds the computed colour (K-42) | What the viewport draws of it |
| `hython tools/bench_dome.py` | A lat-long texture, one colour per quarter of the horizon and a white top, on a dome seen by a narrow camera along the horizon axes and 75 degrees up and down; the same on a Z-up stage with `DomeLight_1` | Each direction within 0.03 of Karma (K-67) | The exact poles (Cycles wraps its map vertically there), lighting from the dome |
| `hython tools/bench_rect.py` | The four-corner texture on a 2 x 2 rect light seen head-on, plain and turned a quarter | Each quarter within 0.03 of Karma (K-68) | Brightness of other light shapes |
| `hython tools/bench_lights.py [pattern]` | A white floor under one light per case, seen from above: sphere, disk, rect, cylinder, distant, normalized or not; spots hard, soft and softness alone; emission focus with and without tint; IES profiles plain, normalized, angle-scaled and asymmetric; a normalized disk and cylinder, a point, a colour with a temperature, a textured rect light; exposure; colour temperature (24 cases) | Floor radiance under the light and 1, 2, 3 units aside within 10 % (or 0.003) of Karma (K-69, K-70) | Coarse IES profiles (Cycles interpolates cubically, Karma linearly), light textures (bench_rect), portals |
| `hython tools/bench_light_split.py [name]` | A diffuse and a metal floor half under a large rect light, a board over each casting a shadow: lobe multipliers 0.5, 0, both, a shadow colour with and without a specular multiplier, shadows off | Lit and shadowed floor within 10 % of Karma on each half (K-87) | A light seen by the camera; domes |
| `hython tools/bench_aniso.py` | A metal plane reflecting a small light: isotropic roughness, two alphas both ways, a reflecting dielectric, a roughness wired from `roughness_anisotropy` | The highlight's x/y spread within 20 % and its mean within 15 % of Karma (K-91) | Alphas more than 10 apart (Cycles' cap) |
| `hython tools/bench_camera.py [pattern]` | Small white unlit squares, one camera per case: off-axis framing, aperture offsets, depth of field, orthographic (on a stage in metres and one in centimetres), camera exposure, image aspect wider and taller than the aperture, a crop (`dataWindowNDC`, centred and in a corner), a pixel aspect of 2, the four other conform policies, `disableDepthOfField` | Each square's centroid and spread within a pixel and its total light within 5 % of Karma (K-71, K-77, K-78) | Motion blur of the camera, stereo |
| `hython tools/bench_sky.py` | Houdini's Karma Physical Sky LOP built under hython, dome and atmosphere modes, the sun at 10, 30 and 60 degrees, a camera looking up over a ground and a ball; the same camera at f/0.1 on the ball with each depth-of-field switch | Four patches of the sky within 3 % of Karma for the dome, within 45 % for the atmosphere; the ball blurred as in Karma and sharp under either switch (K-104, K-105) | The sun's disc, the ground lit by the sky, aerial perspective |
| `hython tools/bench_subdiv.py [pattern]` | A Catmull-Clark cube (no tags, all edges creased sharp and at 1.5, sharp corners) and an open grid (a hole, each boundary rule), white unlit silhouettes; a left-handed glass cube against the right-handed one | At most 1 % of the pixels differ from Karma (K-72); the glass cubes within 0.01 of each other (K-76) | Face-varying interpolation of UVs, Loop and bilinear schemes |
| `hython tools/bench_normalmap.py [pattern]` | A quad with a constant tangent-space normal map tilted along +-u and +-v, lit from +X then +Y; the map's `scale`; UVs mirrored along X | Centre brightness within 10 % of Karma (Cycles' bump terminator term takes up to 8 %) (K-73) | Normal maps from textures, object-space maps, `bump` |
| `hython tools/bench_points.py [pattern]` | White unlit points seen from above: constant width, a width per point, no width, under a scaled transform; linear curves without widths | Covered pixels overlap Karma's (IoU at least 0.9) (K-74) | Point shapes other than spheres, motion |
| `hython tools/bench_displace.py` | A Catmull-Clark plane seen from 30 degrees above: flat, a MaterialX displacement ramp along u, a UsdPreviewSurface constant displacement | The rows its silhouette covers, per column, within one of Karma's (K-75) | Vector displacement, displacement on bump-only materials |
| `python tools/bench_robust.py` | `tests/scenes/bad_*.usda`, 19 malformed files: unparsable attributes (mesh normals, points, point widths), NaN points, indices out of range (plain and subdivided), counts that do not add up (meshes, curves), degenerate faces, short face-varying and per-vertex primvars, primvars longer than the geometry (constant and per-vertex), crease lengths of 0 and 1, a GeomSubset past the faces, an instancer with more indices than positions, a cyclic material graph, missing textures and IES files, an IES file with no angles | husk renders every file three times, exit 0, image on disk - no crash on a malformed file, even an intermittent one (K-57, K-82) | That the image is right |
| `hython tools/bench_agree.py [pattern]` | 7 surface materials and 5 hand-built BSDF networks (two `layer` coats among them) × 3 regions, plus the highlight's 99th percentile on the glossy ones, Cycles against Karma on the same USD | Floor within 1 %, spheres within 25 % (glass: order of magnitude), highlights within 35 % of Karma; normal, position and tangent lookups by space on a turned sphere, the whole subsurface sphere within 6 % - 67 checks | Fine shading differences: the tolerance admits the engines' own |
| `hython tools/mtlx_coverage.py [--list]` | MaterialX library vs the table | Which nodedefs the delegate renders - by the table, by nodegraph expansion or by rewriting (796/822, `tools/mtlx_rules.py` holds the rule) | Which translate correctly |
| `hython tools/mtlx_inputs.py [--list] [pattern]` | Every routed nodedef, all inputs authored, one husk run | Which nodedefs keep every input, output and node (543/652 on 2026-10-07); `--list` names what each one loses | Values |
| `hython tools/mtlx_defaults.py [pattern]` | standard_surface, OpenPBR, glTF, Disney, UsdPreviewSurface | A lit sphere renders the same with no input authored and with every input authored at its model's default (8x8 block means, so noise cannot pass for a difference); the sphere must be lit | Values of authored inputs |
| `hython tools/bench_curves.py [--karma] [name]` | 5 hand-written BasisCurves | Each curve covers the plane where USD puts it and nowhere a misread curve would: Bézier, B-spline, periodic, pinned, `varying` widths; with `--karma`, its silhouette overlaps Karma's (IoU ≥ 0.85) | Shading; indexed curves (no USD attribute) |
| `hython tools/bench_motion.py [name]` | 8 ways to move a square | The blur trail is as long as the shutter says: own transform, points, PointInstancer positions, instancer transform, a moving camera and one turning back mid-shutter; still ones stay sharp | Deformation by velocity |
| `hython tools/bench_instances.py [name]` | 3 instanced squares, flat and nested | Each instance's `displayColor` and float primvar reach an attribute node and Object Info; an outer instancer's primvar reaches nested instances | - |
| `hython tools/bench_implicit.py` | Sphere, Cube, Cylinder, Cone, Capsule, Plane | Each renders with the silhouette its attributes give, along its axis (6 % tolerance; 0.4 % measured) | Shading |
| `hython tools/bench_settings.py [name]` | Render settings and per-prim properties, one small scene each | Dome opaque by default, film transparent on request, exposure, motion blur on and off, camera-invisible prims (Cycles and Karma spellings), holdout, shadow catcher, light and shadow linking, a light's diffuse multiplier at 0, Houdini `Cd` volume field read as colour, an unbound prim's `displayOpacity` and per-vertex `displayColor` (K-79, K-80), a volume hidden from the camera by its own primvar (K-85) | The live motion-blur toggle (needs a Hydra session) |
| `hython tools/bench_aovs.py` | One product, nine render vars, the EXR header | Beauty, a Cycles pass in Cycles' convention, a Karma LPE and a Karma component in Karma's (equal to the beauty on a diffuse scene), distinct cryptomatte ids, a shader AOV through `aov_output`, two light groups adding up to the beauty, depth, a cryptomatte manifest whose hashes are the pixels' ids | - |
| `hython tools/bench_karma_settings.py` | Houdini's Karma Render Settings LOP, twelve AOVs ticked | Each of Karma's render vars (LPEs, `ray:hit*`, `CDA`) lands on a Cycles pass with the value the diffuse scene implies | Light components other than diffuse on a scene that has them |
| `hython tools/mtlx_pinned.py [--list] [pattern]` | Every value nodedef, two grids | A nodedef renders the same with its inputs unwritten and with them written at their MaterialX defaults (677/677 since 0099; 57 differed before) | Values |
| `hython tools/count_nodes.py` | Sdr registry | The node counts the docs quote: 163 published, 64 hidden, 99 VOPs, 97 probed | - |
| `python tools/karma_nodegraphs.py <kma_node> \| --list` | `$HFS/houdini/karmaNodeGraphs.json` | A Karma node's own nodegraph as a readable list, inputs named; the nodes it uses that are not in the library, which a delegate nodegraph has to replace (K-106) | - |
| `scratchpad/audit_surface.py` (local) | 39 `standard_surface` inputs | Each input changes the image, references local and gitignored | Agreement with Karma beyond the four measured cases |

Taken together: the suite catches a node that stops rendering, a socket
rename, a dead parameter, a dropped input (`mtlx_inputs.py`), a wrong value
on the 49 MaterialX cases, a wrong closure mix, a surface model's default,
a wrong pass, a prim rendered where its settings hide it, a curve or an
instance drawn in the wrong place. What it cannot see is the live viewport:
`tests/houdini/` holds the scenes to check there.

**Checks in the Houdini GUI are done by the agent, not handed to Adrien**
(his rule, 2026-10-09: everything to test in the interface is checkable
through the MCP). Start a session with `tests/houdini/launch_cycles_log.cmd
<scene>` (it starts the houdini-mcp server), drive it with
`python tools/hou_remote.py`, read `tests/scratch/cycles_viewport.log`, grab
the viewport or the render buffer from Python, and close the session when
done - never his own Houdini, never save his `.hip` files. A patch that
touches the viewport, live edits (moving a light, toggling a setting while
rendering) or the display driver is not finished until this check ran.
`python tools/gui_capture.py NAME "<python step>"` runs a step in that
session and grabs its window with PrintWindow, which works while the window
sits behind others; Houdini's flipbook does not (it returned one stale image
for every state). The tool checks the scene is under `hdCycles/tests` and
grabs the window of the very process the MCP server runs in, so it can never
drive or capture Adrien's own Houdini. Measure the region you need from the
PNG (`tests/scratch/gui/`); a window resized between two steps makes the
first grab after it stale. When another session's Houdini already holds the
MCP port 9876, set `HDCYCLES_MCP_PORT` (9877...) before starting the session:
the launcher's startup script and `hou_remote.py` both read it.
`tests/houdini/lights_live.hip` (written by `tools/make_lights_live_hip.py`)
is the scene for live light edits: its `edit` LOP sets the shadow colour,
lobe multipliers and the cylinder's roll.

Testing a freshly built DLL while Houdini holds the installed one: every
bench honours a `PXR_PLUGINPATH_NAME` already in the environment, so the
temporary-tree recipe above applies to all of them.

## The four layers of the suite

Cheapest first. Layers 1 and 3 exist since 2026-10-07; layer 2 exists and
grows with every phase; layer 4 is still a one-off.

### 1. Inputs: `mtlx_inputs.py`

One stage, one material per routed nodedef, every input authored at its
default so that Hydra forwards it, wired to a terminal the way its output type
requires (surfaces directly, BSDF/EDF through `surface`, VDF through `volume`,
values into `standard_surface.base_color`). One husk render at one sample;
the delegate's warnings carry the material path and are sorted per nodedef.
The stage and the log stay in `tests/materialx/output/inputs/`.

### 2. Value: `bench_mtlx.py`

The probe drives `base_color` of a specular-free surface under a flat light,
and the rendered mean divided by the measured gain (5.544) must match an
expected colour to 2 %. Expected colours come from the MaterialX source
expressions and nodegraphs evaluated in Python, each with its file named -
never from the renderer. Colour cases use a non-grey input so a collapse to
grey fails. A case may add lines to the mesh (`geomcolor` writes a vertex
colour) or widen its tolerance (`facingratio`, 0.04 for the perspective
spread). To add: every `_color3`/`_vector3` variant of each math family
(phase 3), the six other blends, the closures through a second template.

### 3. Image: `bench_render.py` + `bench_diff.py`

```
tests/nodes/5.3/
    scenes/        generated
    references/    tracked - rendered once, reviewed, committed on purpose
    output/        ignored - what the last run produced
```

The 97 node references were re-accepted on 2026-10-08 after patch 0099: the
shared stage's glass cube (`mxGlass`, `standard_surface` with `transmission
1` and no `transmission_color` authored) had been rendered teal, Cycles
tinting the transmission with `base_color` where MaterialX says the default
`transmission_color` - white - applies. With the default now written the cube
is clear, as Karma renders it (cube region r/b ratio 0.89 against Karma's
0.90, 0.51 before). Every node image changed by that cube alone; `--accept
all` after the side-by-side check against Karma, not before.

`bench_diff.py` compares `output/<name>.exr` to `references/<name>.exr` with
OpenImageIO in Python - a pixel fails beyond `1e-3` absolute *and* 1 % relative, 0.5 % of pixels may fail - and exits non-zero on a
regression. A reference moves only by `--accept <name>` (or `all`), which is a
reviewed commit. Still to do: the same layout for the MaterialX and hair
benches and for the `standard_surface` audit, whose references are local.

### 4. Agreement: Cycles against Karma

`hython tools/bench_agree.py [pattern]`: a sphere on a grey standard_surface
floor, a rect light and a distant light, one material per case on the sphere
- diffuse, glossy dielectric, metal, glass, coat, emission, UsdPreviewSurface -
rendered by both renderers from the same file through husk at 240×180. The
sphere's centre and two floor patches are compared on their mean RGB; the
ratio Cycles/Karma must stay within 1.25 (1.10 for emission, 4 for glass).
21 checks, 0 problems on 2026-10-08; the floor agrees to the third decimal,
the sphere within 5-20 % (Cycles bounces more indirect light), emission 5 %
over Karma. A side-by-side PNG per case lands in `tests/agreement/output/`.

What writing it taught, each worth knowing before trusting a comparison:

- an **unbound prim** is not shaded alike: Cycles' fallback is a diffuse with
  the displayColor as albedo, Karma's comes out 2.4 times darker on the same
  displayColor - bind a material before comparing;
- a **distant light without `normalize = 1`** gives next to nothing in both
  renderers; Houdini's LOP writes it, a hand-written file must too;
- a ground wound clockwise with an authored upward normal is **black in
  Cycles** (a backfacing hit flips both normals) and lit in Karma, which faces
  the normal forward; Houdini writes consistent windings;
- **through a glass sphere** Karma CPU shows the refracted floor 2.7 times
  darker than Cycles; the two engines' paths through a dielectric differ,
  hence the loose tolerance on that one case;
- a bare **dome light** is left out of the camera's view by husk's Karma
  (alpha 0) and shown by Cycles (alpha 1); the bench has no dome for that
  reason. Seen on `tests/materialx/scenes/phase4b_mtlx.usda`, where the glass
  cube is milky in Cycles and clear with a dark top in Karma - the sky through
  the glass.

## Measuring interactivity

`CYCLES_LOGGING=1 CYCLES_LOGGING_LEVEL=info CYCLES_LOG_FILE=<path>` before
starting Houdini. With `CYCLES_DUMP_PRIMS=1` as well, the log lists every
prim the scene index adds, its type and its data source six levels deep: how
Houdini delivers a LOP to Hydra (the sky of K-104 was found that way). The
log carries:

- `Display: ...` once per render pass creation - which driver and which Hgi;
- `Render restarted: ...` at each session reset, with its cause (scene,
  camera, settings, camera-switch);
- `Render pass: N ms on the host thread (lock, COP poll, AOV bindings, camera,
  dicing camera, reset, start)` whenever the host thread spent more than 50 ms
  in `_Execute`;
- Cycles' own `Rendered N samples in T seconds` and memory lines.

Every line starts with `[seconds]` since the first one, so a viewport that
"takes long to start" reads as the gap between `Render restarted` and the
first `Rendered 1 samples`, and a frozen UI as a `Render pass` line - no
stopwatch needed. The live reading of 2026-10-08 (K-31) saw 0.17 s to the
restart, 0.05 s more to the first sample, and no `Render pass` line at all.

A viewport that "feels slow" is one of three things, told apart by these
lines: the host thread blocked (`Render pass` large), the session resetting
every frame (`Render restarted` every frame with the same cause), or the sample
itself slow (`Rendered 1 samples in` large). Only the first two are the
delegate's.

## Checking a distribution

`tools/make_dist.py` already refuses to finish if a text file still names a
drive letter. It cannot judge a binary: `hdCycles.dll` carries its build's
source paths in `__FILE__` strings (K-101), harmless. To check that the folder
loads from somewhere other than where it was built, without touching the real
Houdini preferences, copy `cycles.json` and `CyclesForHoudini/` into a scratch
`packages` folder and point Houdini at it:

```bash
export HOUDINI_USER_PREF_DIR="/tmp/scratch/houdini__HVER__"   # keep __HVER__
mkdir -p /tmp/scratch/houdini22.0/packages
cp -r dist/CyclesForHoudini-5.3/* /tmp/scratch/houdini22.0/packages/
hython check.py
```

where `check.py` prints `hou.getenv("CYCLES_ROOT")` (it must be inside the
scratch folder), the loaded HDAs containing `cycles`
(`hou.hda.loadedFiles()`: `cycles_vops.hda`, `hdcycles_flatten_op_textures.hda`)
and `[p for p in UsdImagingGL.Engine.GetRendererPlugins() if "Cycles" in p]`
(`HdCyclesPlugin`, `HdCyclesPluginGPU`). Done on 2026-10-12 for the 5.3 zip.
This proves the package and the plugin registration, not a render and not a
clean machine (K-102).

Two traps met while doing it: `HOUDINI_USER_PREF_DIR` must contain `__HVER__`
or Houdini refuses it; and piping `hython` into `Select-Object -First N` in
PowerShell kills it with exit code 1 when the pipe closes, which looks like a
failure and is not (redirect to a file instead).

To time the CUDA kernels alone, run the `nvcc` command of one cubin from
`build/src/kernel/device/cuda/cycles_kernel_cuda.vcxproj` with and without
`--split-compile=0` (K-100); it writes to the output path you give and needs the
MSVC environment (`vcvars64.bat`).

## Checking a build

`cmake` returns 0 when the install step failed with Houdini open. After every
build:

```bash
ls -la install-53/houdini/dso/usd/hdCycles.dll          # timestamp
grep -c -a "a string from the new code" install-53/houdini/dso/usd/hdCycles.dll
```

Never run two builds concurrently; the second one links stale objects and the
DLL looks new while it is not.
