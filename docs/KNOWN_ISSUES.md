# Known issues

What is open today, and what Cycles cannot do the way Karma does. Issues that
were fixed, measured or closed keep their `K-` number in
[ISSUE_LOG.md](ISSUE_LOG.md), which the patch notes point at.

## Open

### Rendering

- **K-118 A smooth bump goes flat far from the origin.** Cycles takes a bump's
  slope by finite differences in float32: fifteen kilometres from the origin
  the offset point rounds back to the shading point and the slope is zero.
  Karma differentiates analytically and resists (it still loses 40 % at
  44 km). Recentre the scene near the origin; the same cures the pixelation
  of hex-tiled lookups.
- **K-114 The GL display driver is off by default.** Under a Karma Physical
  Sky it showed the sky and no geometry in Houdini's viewport; the output
  driver shows the scene. `CYCLES_DISPLAY_DRIVER=1` turns the display driver
  back on.
- **K-120 Stencil maps are ignored.** The Render Geometry Settings LOP's
  Stencil Map (`karma:object:stencilmap`) is not read; the object renders
  whole. The Cycles equivalent is a Transparent BSDF mixed in by the map.
- **K-125 A Cycles render of a stage carrying Karma's render settings can
  misbehave.** Reported, not reproduced. Deactivating Karma's `/Render` prim
  and using a Cycles Render Settings LOP avoids it.
- **K-121 Houdini crashed once on a layer reload under the Cycles GPU
  viewport.** Reported once, not reproduced; switching the viewport to
  Houdini VK before the reload avoids it.
- **K-86 A PointInstancer whose `protoIndices` name a missing prototype
  crashes USD.** Inside OpenUSD as Houdini 22.0.368 ships it; Karma crashes
  the same way. Not fixable in a delegate.
- **World volume.** A world volume that varies in space is bounded to 10 km
  around the origin; a homogeneous one is infinite, as in Blender, and hides
  the sky and the sun. A Karma Sky Atmosphere gets a default world volume
  from its coefficients, which costs render time and adds a haze on distant
  geometry that Karma does not show; Karma also dims and reddens the sun
  through its atmosphere, which Cycles does not.

### MaterialX

- **K-09 `layer` is an approximation.** Cycles has no layering closure:
  `top + base * (1 - F)`, right for a dielectric top (1.03-1.10 of Karma),
  approximate for any other.
- **K-62 `sheen_bsdf` in its default mode (`conty_kulla`) renders darker
  facing the camera.** Cycles' sheen is the `zeltner` model, which matches
  Karma within 7 %.
- **K-42 The viewport preview of a Cycles material follows one image per
  input.** A procedural or a ramp shows as the input's default value.

### Build and distribution

- **K-99 AMD, Intel and Apple GPUs are not built.** The delegate enumerates
  HIP, oneAPI and Metal devices; the build passes none of their options, and
  the kernel patches have only ever been compiled by `nvcc` and MSVC.
  Testing needs the hardware.
- **K-102 The distribution has not been installed on a second machine.**
- **K-101 `hdCycles.dll` embeds the source paths of its build**, through the
  log macros. Harmless.

## Limits of Cycles itself

What the delegate cannot fix, because Cycles has no counterpart or behaves
otherwise by design. Each is measured and kept on purpose; a file relying on
one renders differently from Karma, and that is expected.

- **Cylinder light**: Cycles has no cylinder light; it renders as an
  emissive tube mesh, 0.98-1.04 of Karma, without lobe multipliers, shadow
  colour or shadow switch (K-89).
- **Light filters, `occlusion`**: no Cycles equivalent. Light filters are
  dropped; UsdPreviewSurface's `occlusion` is ignored. `shadow:color` and the
  lobe multipliers are carried by splitting the light (K-87); on a dome only
  0 and 1.
- **Light path expressions**: Cycles has none. Karma's usual LPEs are mapped
  to the Cycles pass holding the same light; any other renders black and
  says so in the log.
- **MaterialX time, frame and matrix nodes**: no node in Cycles' graph
  carries a matrix or the current time; those nodedefs are left out.
- **Remaining differences with Karma on the MaterialX library**
  (`mtlx_karma.py`): 37 of 695 value nodes and 7 of 45 closures differ beyond
  the tolerance (K-61, K-64): engine-specific hex-tiled blending, noise and
  cellular functions, closures Karma itself approximates. Glass agrees in
  order of magnitude only: the two engines' rough refraction differ.
- **Bump at sub-pixel scale**: Cycles differentiates a bump's height over a
  tenth of a pixel, Karma over about a pixel. The slope is the same on relief
  larger than a few pixels; finer relief keeps more of its slope in Cycles.
- **Bump and normal map terminator**: Cycles darkens a bumped or
  normal-mapped surface towards its terminator; Karma does not - up to 8 % on
  strong tilts (K-73).
- **IES interpolation**: Cycles interpolates a profile cubically, Karma
  linearly; only coarse profiles show it (K-70).
- **Dome poles**: Cycles' environment map wraps vertically, so the half texel
  at each pole blends the first and last rows - invisible on a real HDRI
  (K-67).
- **Fallback shading of unbound prims**: Karma's is about twice as dark on
  the same `displayColor` (K-80).
