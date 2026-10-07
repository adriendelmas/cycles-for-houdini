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

## The benches, and what each proves

| Command | Scope | Proves | Does **not** prove |
|---|---|---|---|
| `hython tools/bench_export.py` | 97 native Cycles VOPs | Each VOP exports through the real Solaris translator to USD | Values |
| `python tools/bench_render.py` | Same 97 scenes | No delegate warning, image present, not black | That the image is right. **Overwrites** `tests/usd/bench-53/images/*.exr`, the directory git tracks (K-50) |
| `python tools/bench_diff.py` | Same images | Each node changes the image against `_baseline.exr` | Direction or magnitude of the change |
| `hython tools/bench_mtlx.py [name]` | 7 MaterialX nodes (+3 textured with `CYCLES_BENCH_TEXTURE`) | Rendered colour within 2 % of an expected value | That the expected value is MaterialX's: `saturate`'s was derived from the code (K-52) |
| `hython tools/bench_hair.py` | 4 pairs | MaterialX Chiang hair equals native principled hair, error < 1e-3 | - |
| `hython tools/mtlx_coverage.py [--list]` | MaterialX library vs the table | Which nodedefs route to *some* mapping | Which translate correctly (K-51) |
| `scratchpad/audit_surface.py` (local) | 39 `standard_surface` inputs | Each input changes the image, references local and gitignored | Agreement with Karma beyond the four measured cases |

Taken together: today's suite catches a node that stops rendering, a socket
rename, and a dead parameter. It does not catch an inverted mix, a greyed
colour, or a mistranslated OpenPBR input - which is exactly what
KNOWN_ISSUES.md is full of.

## What a real suite looks like

Phase 0 of [PLAN.md](PLAN.md). Four layers, cheapest first.

### 1. Unit: the mapping table

A `hython` script that, for every MaterialX nodedef the table claims, lists the
nodedef's inputs (from `MaterialX.loadLibraries`) and checks each has either a
mapping entry or a documented omission. No render. Output: the
"input-complete" number for the README.

### 2. Value: one plane, one node, one expected colour

`bench_mtlx.py` generalised: the probe drives `base_color` of a specular-free
surface under a flat light, and the rendered mean divided by the measured gain
(5.544) must match an expected colour to 2 %. Expected colours come from the
MaterialX `genglsl` source expressions evaluated in Python - never from the
renderer. Every `_float`, `_color3`, `_vector3` variant of a family is a
separate case; colour cases use a non-grey input so a collapse to grey fails.

### 3. Image: references under version control, outputs outside it

```
tests/usd/bench-53/
    scenes/        generated
    references/    tracked - rendered once, reviewed, committed on purpose
    output/        ignored - what the last run produced
```

`bench_diff.py` compares `output/<name>.exr` to `references/<name>.exr` with
`hoiiotool --fail 1e-3 --failpercent 0.5 --diff` and lists the failures. A
reference moves only by an explicit `--accept <name>`, which is a reviewed
commit. The same layout for the MaterialX and hair benches and for the
`standard_surface` audit, whose references stop being local.

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
