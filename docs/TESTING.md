# Testing

What exists, what each bench actually proves, and what a real regression
suite needs. Numbers quoted in the README must come from a command on this
page.

## Running anything outside Houdini

All benches drive `husk.exe` and `hoiiotool.exe` from `$HFS/bin`. On this
machine three things are needed or the plugin is not found and the images are
wrong:

```bash
export HOUDINI_USER_PREF_DIR="C:/Users/Adrien/Documents/houdini22.0"   # the real pref dir, holds packages/cycles.json
export MSYS_NO_PATHCONV=1                                             # Git Bash: keep /Render/settings intact
export CYCLES_INSTALL_DIR=install-53                                  # which engine the benches target
```

Reference images are rendered at **120×90**; comparing at another resolution
fails every scene at once. If `hserver -l` shows `Connection Error`, restart
it with `hserver -S https://www.sidefx.com/license/sesinetd`.

To test a freshly built DLL while Houdini holds the installed one: set
`HOUDINI_PACKAGE_SKIP=1`, point `PXR_PLUGINPATH_NAME` at a temporary plugin
tree, and put the Houdini and install `bin` directories on `PATH` in POSIX
form (`/e/...`).

Writing a scene by hand: a `DistantLight` needs `inputs:normalize = 1` to
light anything. Unnormalized, USD reads its intensity as the radiance of the
sun disk, so the illuminance is intensity × the disk's solid angle - about
7e-5 at the default 0.53°. Karma and the delegate agree on both (measured
2026-10-07, white plane: 0.318 vs 0.317 normalized, 0.0019 vs 0.0019 at 5°);
Houdini's Distant Light LOP turns it on. `tests/scenes/smoke.usda` predates
this and its sun contributes nothing. Also give the stage `metersPerUnit = 1`:
without it a camera aperture is read in centimetres.

## The benches, and what each proves

| Command | Scope | Proves | Does **not** prove |
|---|---|---|---|
| `hython tools/bench_export.py` | 97 native Cycles VOPs | Each VOP exports through the real Solaris translator to USD | Values |
| `python tools/bench_render.py` | Same 97 scenes | No delegate warning, image present, not black; renders into `tests/nodes/5.3/output/` (ignored) | That the image is right |
| `hython tools/bench_diff.py [--accept node\|all]` | `output/` vs `references/` | Each node matches its committed reference (off by less than `1e-3` absolute or 1 % relative on 99.5 % of pixels); lists nodes inert against `_baseline.exr`; `cycles_set_normal` is reported, not counted (A19) | - |
| `hython tools/bench_mtlx.py [name]` | 36 MaterialX nodes (+3 textured with `CYCLES_BENCH_TEXTURE`), colours and closures | Rendered colour within 2 % of a value **computed from the MaterialX definition**, file named next to each formula | Anything the plane's mean cannot see: directions, volumes |
| `hython tools/bench_hair.py` | 4 pairs | MaterialX Chiang hair equals native principled hair, error < 1e-3 | - |
| `hython tools/mtlx_coverage.py [--list]` | MaterialX library vs the table | Which nodedefs route to *some* mapping (652/823) | Which translate correctly |
| `hython tools/mtlx_inputs.py [--list] [pattern]` | Every routed nodedef, all inputs authored, one husk run | Which nodedefs keep every input, output and node (543/652 on 2026-10-07); `--list` names what each one loses | Values |
| `hython tools/mtlx_defaults.py [pattern]` | standard_surface, OpenPBR, glTF, Disney, UsdPreviewSurface | A lit sphere renders the same with no input authored and with every input authored at its model's default (8x8 block means, so noise cannot pass for a difference); the sphere must be lit | Values of authored inputs |
| `hython tools/bench_curves.py [name]` | 5 hand-written BasisCurves | Each curve covers the plane where USD puts it and nowhere a misread curve would: Bézier, B-spline, periodic, pinned, `varying` widths | Shading; indexed curves (no USD attribute) |
| `hython tools/count_nodes.py` | Sdr registry | The node counts the docs quote: 163 published, 64 hidden, 99 VOPs, 97 probed | - |
| `scratchpad/audit_surface.py` (local) | 39 `standard_surface` inputs | Each input changes the image, references local and gitignored | Agreement with Karma beyond the four measured cases |

Taken together: the suite catches a node that stops rendering, a socket
rename, a dead parameter, a dropped input (`mtlx_inputs.py`), and - for the
eleven cases it carries - a wrong value. It does not yet catch a wrong closure
mix or a mistranslated OpenPBR input; those come with phases 2 and 4.

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

`bench_diff.py` compares `output/<name>.exr` to `references/<name>.exr` with
OpenImageIO in Python - a pixel fails beyond `1e-3` absolute *and* 1 % relative, 0.5 % of pixels may fail - and exits non-zero on a
regression. A reference moves only by `--accept <name>` (or `all`), which is a
reviewed commit. Still to do: the same layout for the MaterialX and hair
benches and for the `standard_surface` audit, whose references are local.

### 4. Agreement: Cycles against Karma

A handful of scenes rendered by both renderers from the same USD - lights,
`standard_surface`, OpenPBR, hair, a VDB - compared on mean luminance per
region with a tolerance that admits the two engines' real differences (a few
percent) and rejects a factor of two. This is the test that caught the ×4
distant light and the ×π dome; it should be a command, not a one-off.

## Measuring interactivity

`CYCLES_LOGGING=1 CYCLES_LOGGING_LEVEL=info CYCLES_LOG_FILE=<path>` before
starting Houdini. The log carries:

- `Affichage : ...` once per render pass creation - which driver and which Hgi;
- `Rendu relance : ...` at each session reset, with its cause;
- `Passe de rendu : N ms (verrou, veille COP, camera et AOV, relance, demarrage)`
  whenever the host thread spent more than 50 ms in `_Execute`;
- Cycles' own `Rendered N samples in T seconds` and memory lines.

(These lines are French today and will be renamed under K-53; grep for `ms`
and `Hgi` until then.)

A viewport that "feels slow" is one of three things, told apart by these
lines: the host thread blocked (`Passe de rendu` large), the session resetting
every frame (`Rendu relance` every frame with the same cause), or the sample
itself slow (`Rendered 1 samples in` large). Only the first two are the
delegate's.

## Checking a build

`cmake` returns 0 when the install step failed with Houdini open. After every
build:

```bash
ls -la install-53/houdini/dso/usd/hdCycles.dll          # timestamp
grep -c -a "a string from the new code" install-53/houdini/dso/usd/hdCycles.dll
```

Never run two builds concurrently; the second one links stale objects and the
DLL looks new while it is not.
