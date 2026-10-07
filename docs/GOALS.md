# Goals

## In one sentence

Render Solaris scenes with Blender's Cycles, inside Houdini 22, with the same
reliability a Houdini user expects from Karma - and without forking Cycles.

## Who it is for

- A Houdini user who knows Cycles from Blender and wants its look, its
  Principled BSDF, its hair and its volumes on Solaris scenes, in the viewport
  and through husk.
- The author's own pipeline: garments and yarns built in `md_seams`, rendered
  with a renderer whose hair and thick-curve model he trusts.
- Eventually, Blender upstream: the delegate lives in Cycles' own tree, and
  most of what is fixed here is a fix to that delegate, not to Houdini.

## What "working correctly" means

The project is done when all of the following hold, each verified by a test
named in [TESTING.md](TESTING.md):

1. **A scene that renders in Karma renders in Cycles** with the same geometry,
   the same lights at the same intensity, the same camera, the same
   subdivision, the same motion blur - polygons, subdivision surfaces,
   curves of every USD basis, points, instances, VDB volumes.
2. **A MaterialX material renders the same as its MaterialX reference.** Not
   "plausible": the same, within noise, for every nodedef the translation
   claims. A claimed nodedef has a test; an unclaimed one is reported in the
   log, never silently dropped.
3. **A native Cycles material behaves as in Blender**: every node the VOP
   library exposes does what its Blender counterpart does, with the same
   defaults.
4. **The viewport is interactive**: an edit shows within the time Cycles
   needs to trace one sample, and never freezes Houdini's UI thread for
   longer than a frame.
5. **husk renders are production renders**: AOVs, cryptomatte, transparent
   background, light linking, per-object visibility and holdouts, as a Karma
   ROP would give them.
6. **Nothing fails silently.** A dropped connection, an unknown node, an
   ignored setting, a device fallback - each writes one line to the log.

## Deliberate non-goals

- **No copy of Cycles in this repository.** Changes are a patch series
  against a pinned upstream commit, re-applied by `tools/bootstrap.py`.
  Anything that would require a permanent fork is out.
- **No Blender UI parity.** The Material Builder follows Blender's node
  categories and labels, but Houdini's parameter conventions win where they
  clash.
- **No MaterialX-to-OSL compiler, for now.** Translating MaterialX to Cycles
  nodes is the chosen path because it runs on CUDA and HIP; OSL would not.
  The option stays open for the nodes that cannot be expressed as a node
  graph (see [PLAN.md](PLAN.md), phase 7).
- **No second viewport renderer.** Previewing a Cycles material in Houdini's
  own GL/Vulkan viewport goes through `UsdPreviewSurface`, which can only
  approximate; the goal is "recognisable", not "identical".
- **Windows first.** The build is exercised on Windows 11 with MSVC. Nothing
  in the delegate is Windows-specific except the GL display driver; Linux
  and macOS are untested, not excluded.

## Constraints that shape every decision

- The delegate links against Houdini's own USD, Python and image libraries:
  it is tied to a Houdini series (22.0 today) and rebuilt for the next.
- The render device is fixed when the session is created; it is an
  installation preference, never a scene setting.
- Hydra forwards only *authored* parameters: every mapping must carry the
  MaterialX default for inputs the network never writes, or Cycles' default
  leaks through.
- `TF_WARN` is swallowed by husk. Anything the user must see goes through
  Cycles' logger.
