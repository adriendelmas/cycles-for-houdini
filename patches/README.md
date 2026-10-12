# Patches applied to Cycles

Cycles is not copied here: it has its own repository, and our changes live
there on a branch of ours, as commits separated by topic. This series is its
export through `git format-patch`.

    patches/5.2/   39 patches, base 3b97e190 (branch release/5.2)
    patches/5.3/   142 patches, base 8424ed53 (branch main)

`tools/bootstrap.py` does the whole path -- clone, `git am`, build. By hand, on
a clone that is already in place:

    cd external/cycles-53 && git am ../../patches/5.3/*.patch

Regenerate the series after a new change:

    cd external/cycles-53 && git format-patch --no-signature -o ../../patches/5.3 8424ed53..HEAD

The two series differ little. The move to 5.3 replayed 37 patches out of 38:
`hydra: never leave a Shader without a graph` is no longer needed, upstream
having solved the problem on its side. To that are added dispersion, taken from
Blender PR 162041, and the removal of HDA backups from tracking. **The
numbering has therefore shifted by one** from the fifth on: the notes below
follow that of 5.2.

Most of these patches are independent of Houdini and of this machine --
**so many candidates for an upstream contribution to Blender**.

## Series 5.3

| | |
|---|---|
| `0001` | cmake: add missing USD libraries for the Houdini build |
| `0002` | hydra: accept Houdini AOV naming conventions |
| `0003` | hydra: apply constant primvars to every instance |
| `0004` | hydra: publish Cycles shader nodes to the USD shader registry |
| `0005` | hydra: translate MaterialX networks to Cycles nodes |
| `0006` | hydra: give unbound volumes the default volume shader |
| `0007` | hydra: register the renderer with Houdini and warn on unknown integrator settings |
| `0008` | hydra: do not build an unusable GL context for the display driver |
| `0009` | hydra: motion blur for animated object transforms |
| `0010` | hydra: fix host crash from unbalanced display driver locking |
| `0011` | hydra: create the shared GL context before draw() can return early |
| `0012` | hydra: fix GL teardown crash, and stop using the display driver by default |
| `0013` | hydra: restart the render on scene edits, and translate more MaterialX nodes |
| `0014` | hydra: take the scene lock rather than trying it, and add a GPU renderer entry |
| `0015` | hydra: OptiX kernel install path, and Houdini render property definitions |
| `0016` | hydra: tag a light's object for update, and keep unresolvable asset paths |
| `0017` | hydra: material edits never reached the device, and displacement was bump-only |
| `0018` | hydra: read Houdini op: texture paths by cooking the COP during sync |
| `0019` | hydra: read Copernicus COP pixels live rather than through an output node |
| `0020` | hydra: build proper RGBA when writing a Copernicus COP layer |
| `0021` | hydra: read MaterialX data image variants without an sRGB decode |
| `0022` | hydra: translate the bulk of the MaterialX node library |
| `0023` | hydra: translate MaterialX separate node output names |
| `0024` | hydra: composite mappings, plus the transform and ramp nodes |
| `0025` | kernel/scene: MaterialX-exact procedural noise nodes — Cycles side of Blender PR #158054, by Ben Houston |
| `0026` | hydra: spread a scalar across a vector socket |
| `0027` | hydra: translate MaterialX noise onto the MaterialX noise node |
| `0028` | hydra: eleven more MaterialX families, and a general composite mechanism |
| `0029` | hydra: MaterialX position is in object space |
| `0030` | hydra: standard_surface specular weight, and image wrapping |
| `0031` | hydra: a colour landing on a scalar socket, and several helpers per mapping |
| `0032` | hydra: MaterialX displacement has no midlevel |
| `0033` | hydra: do not write a parameter that carries no value |
| `0034` | hydra: shade a mesh flat unless its normals say otherwise, and refresh the UsdPreviewSurface names |
| `0035` | hydra: an empty string default crashed the Sdr parser |
| `0036` | node interface: connectors, file pickers, checkboxes |
| `0037` | checkboxes, Base section, and an ignored wire is no longer ignored silently |
| `0038` | dispersion on the principled bsdf, taken from Blender PR 162041 |
| `0039` | otls: stop tracking Houdini's automatic backups |
| `0040` | hydra: a Houdini ramp finally fills the table that Cycles expects |
| `0041` | hydra: deformation blur for animated points |
| `0042` | the Cycles Material Builder was in no repository |
| `0043` | hydra: velocity blur, for geometry whose point count varies |
| `0044` | hydra: per-corner normals, instead of faceting what is not faceted |
| `0045` | hydra: reject an enum value that is not in the registry rather than passing it through as is |
| `0046` | kernel: Random Walk (Legacy) was missing from the closure jump table |
| `0047` | hydra: a single terminal with three inputs, rather than three connectors that contradict each other |
| `0048` | hydra: the dispersion of MaterialX standard_surface, to the principled bsdf that finally carries it |
| `0049` | hydra: list Cycles GPU before Cycles CPU in the engine menu |
| `0050` | hydra: make the display driver and the device choice usable |
| `0051` | hydra: choose the render device from Houdini's menu |
| `0052` | hydra: terminals whose output is not named BSDF were never connected |
| `0053` | hydra: the material settings, in a node rather than nowhere |
| `0054` | scene: displacement was adding itself to itself on every material edit |
| `0055` | hydra: choose a texture's color space from a menu |
| `0056` | hydra: align the lights with Karma, and render cylinder lights |
| `0057` | hydra: the transmission color and the subsurface color, finally translated |
| `0058` | hydra: a texture coming from a COP came out flipped |
| `0059` | hydra: COP textures go through memory, no longer through a file |
| `0060` | hydra: watch the COPs, which nobody reports as changed |
| `0061` | hydra: a brake on COP watching, and a way to switch it off |
| `0062` | hydra: a texture that changes, and leaving a camera |
| `0063` | hydra: COP watching puts the image itself back |
| `0064` | hydra: an image wired into a scalar input, and the subsurface color removed |
| `0065` | hydra: a transmission lobe of its own, for the color and roughness that MaterialX gives it |
| `0066` | hydra: give Cycles the camera that is used to split subdivisions |
| `0067` | hydra: a preview shader for Cycles materials, otherwise the viewport stays gray |
| `0068` | hydra: the MaterialX pass-through, two dead inputs, and six more families |
| `0069` | hydra: stop flipping a COP's image, both ends already store it the same way |
| `0070` | hydra: the subdivision split rate, in the render settings |
| `0071` | hydra: a way to measure a viewport that lags, and a log that goes somewhere |
| `0072` | hydra: a full graphics card that says so, and COPs that weigh only their channels |
| `0073` | hydra: MaterialX hair, and the surface node that cut everything |
| `0074` | hydra: credit Ben Houston at the head of the MaterialX translation |
| `0075` | hydra: float3 primvars were copied at the wrong stride, and read in bulk |
| `0076` | hydra: mix, the dissolves, saturate, facingratio, viewdirection and geomcolor, made exact |
| `0077` | hydra: the ResolveUdimTiles declaration was missing from the series |
| `0078` | hydra: the MaterialX closures - mix, add, multiply, volume, layer, conductor |
| `0079` | hydra: the color and vector variants of the MaterialX operators, and three wrong scalar operators |
| `0080` | hydra: OpenPBR, glTF and Disney translated, the defaults of each surface, UsdUVTexture per channel, kma |
| `0081` | hydra: USD curves rendered where USD puts them, as tubes, and the Curve Shape setting |
| `0082` | hydra: blurred instances, their per-instance primvars, and scalar constant primvars |
| `0083` | hydra: USD implicit surfaces rendered, as fine meshes |
| `0084` | hydra: a Catmull-Clark mesh subdivided without waiting for the display hint |
| `0085` | hydra: eight keys per cubic curve segment, to follow the shape |
| `0086` | hydra: the blur that comes back, Houdini's volume fields, and the transparent film |
| `0087` | hydra: render passes - lights, Karma LPEs, cryptomatte, shader AOVs |
| `0088` | hydra: per-object properties - per-ray visibility, holdout, shadow catcher |
| `0089` | hydra: light linking and shadow linking |
| `0090` | hydra: a prim whose render tag is no longer drawn disappears from the render |
| `0091` | hydra: turning off motion blur no longer makes objects disappear |
| `0092` | hydra: light groups and their passes |
| `0093` | hydra: the diffuse and specular multipliers of USD lights |
| `0094` | hydra: the cryptomatte manifest in the image metadata |
| `0095` | hydra: combined emission and Karma's motion vectors |
| `0096` | hydra: the pass no longer blocks the interface, and the COP cache empties |
| `0097` | hydra: comments and log messages in English |
| `0098` | hydra: flattened MaterialX nodegraphs, extract and swizzle rewritten, vector2 converted |
| `0099` | hydra: the MaterialX defaults written on every input that was not written |
| `0100` | hydra: the `CYCLES_LOG_FILE` log timestamps every line (seconds since the first) |
| `0101` | hydra: the glass lobe of standard_surface chosen on the transmission (wired or > 0), no longer on the presence of `transmission_color`, which 0099 writes everywhere |
| `0102` | hydra: sizes of normals, points and widths checked before reading (K-57, no more segfault on an unreadable attribute) |
| `0103` | hydra: roughness of elementary BSDFs taken as alpha (square root), dielectric_bsdf according to scatter_mode - R principled, T refraction, RT glass (K-58) |
| `0104` | hydra: nodegraphs shipped by the delegate (artistic_ior, roughness_*, inside/outside), transformmatrix with a constant matrix, generalized_schlick as F82, legacy Disney; mix with a color factor, magnitude/distance/dotproduct fixed (K-59) |
| `0105` | hydra: thin_film_bsdf folded back onto the BSDF of its layer, curveadjust as a pass-through, the alpha of an image read by separate4/extract/swizzle (K-17) |
| `0106` | hydra: position, normal and tangent according to their `space` - object normal by default, world position on request (K-18) |
| `0107` | hydra: absorption_vdf as a coefficient (color = 1 - absorption), subsurface at scale 1 and with its anisotropy, AO by maxdistance (K-14); surface_unlit translated (K-60) |
| `0108` | hydra: twelve translations fixed by comparison with Karma - rotate in degrees, UV tangent, vector2 without a 3rd component, combine2 color4, boolean comparisons, burn/dodge without bounds, ramp_gradient flattened (K-61); heighttonormal encoded in tangent space (K-12); emission at intensity 1, generalized_schlick_edf passes its base through |
| `0109` | hydra: base color of the surfaces computed before translation - subsurface and coat darkening of OpenPBR, subsurface and coat gamma of standard_surface; glTF alpha according to alpha_mode (K-63); tiledimage, glTF images, latlongimage and place2d from their nodegraphs, image_float on its first channel (K-64) |
| `0110` | hydra: UsdPreviewSurface according to useSpecularWorkflow (F0 = specularColor, ignored in the metallic workflow) and opacityThreshold (cutout) (K-65); texture color space read from the Hydra field and resolved in the active OCIO config, images in `auto` by default, wrapS/wrapT translated (K-66) |
| `0111` | hydra: dome texture oriented according to the OpenEXR lat-long convention (pole +Y, longitude 0 toward +Z) and `poleAxis` of DomeLight_1 through `domeOffset` (K-67) |
| `0112` | hydra: rect light texture read at (1 - u, v), min corner at (+X, +Y) as USD requires (K-68); spot cone softness converted from the angle (USD) to the cosine (Cycles), 90-degree cone by default, `shaping:focus` and `focusTint` in the light's shader (K-69) |
| `0113` | hydra: IES profiles read according to the emission direction in the light's frame, in candelas like USD, `normalize` (mean of the profile, `IESFile::mean_intensity`) and `angleScale` (K-70) |
| `0114` | hydra: camera exposure (Hydra's linear scale) multiplied with that of the render settings on the film (K-71) |
| `0115` | hydra + scene: subdivision tags read from the mesh's container (creases, corners), USD sharpness / 10, corners without creases, boundary and face-varying rules, holes not subdivided (`Mesh::subd_hole`), corners cleared by `Mesh::clear` (K-72) |
| `0116` | hydra: per-vertex texture coordinates passed per corner (the mikktspace tangent space reads them per corner) - correct normal maps along v and on mirrored UVs (K-73) |
| `0117` | hydra: default width 1 (Hydra's) for points and curves without `widths` (K-74); `displacement` of UsdPreviewSurface through a Cycles displacement node (K-75) |
| `0118` | hydra: `leftHanded` subdivided meshes (Houdini's) flipped for Cycles, corners of each face reversed and per-corner primvars permuted (K-76) |
| `0119` | hydra: under husk, framing rebuilt from `resolution`, `dataWindowNDC` and `pixelAspectRatio` - camera on the display window, buffer placed by full_x/full_y, window conformed to width x pixel aspect (K-77) |
| `0120` | hydra: `disableDepthOfField` of the render settings honored (and aperture closed at fStop 0), `aspectRatioConformPolicy` applied under husk (K-78) |
| `0121` | hydra: constant `displayOpacity` of prims without a material -> object alpha, read by the default surface (transparent mix) (K-79) |
| `0122` | hydra: the default surface reads `displayColor` as an attribute (per vertex, face, corner), 0.8 gray as the per-instance fallback (K-80) |
| `0123` | hydra: motion blur re-enabled live - each geometry resamples its transforms over the shutter without going through Hydra, whose marking resynced nothing in Houdini's viewport (K-81); mesh topology checked on read, inconsistent counts discarded (intermittent crash, K-82) |
| `0124` | hydra: UsdUVTexture whose file cannot be found -> `fallback` (black by default) instead of Cycles' magenta (K-83) |
| `0125` | hydra: nodegraphs for alpha compositing (over, in, out, mask, matte, disjointover, premult, unpremult) and hextilednormalmap, alpha of a constant color4 passed to `outa` (K-84); volumes: primvars read, `cycles:volume:step_size/object_space/velocity_scale` (K-85) |
| `0126` | hydra: output processor `hdcycles_cookcoptextures`, added to every new USD Render ROP, which bakes the `op:` (COP) textures to EXR next to the written USD, for husk and render farms (K-40) |
| `0127` | hydra: light split into twin lights for the `diffuse`/`specular` multipliers between 0 and 1 and `shadow:color`; a light without shadow is no longer hit by BSDF rays (half-black shadows with `shadow:enable = 0`) (K-87) |
| `0128` | hydra: alpha of a computed color (float twins of the color4 nodes, K-17); BSDF `weight` applied by a multiply (K-88); color and vector `geompropvalue` read in full |
| `0129` | hydra: cylinder light rendered by an emissive mesh tube (emission outward only, radiance in the shader) instead of a single-sided rectangle (K-89) |
| `0130` | hydra: viewport preview of a Cycles material through the mixes (`a`/`b` inputs, side favored by the factor), `math`/`vector_math`, mixes of constants computed; translator comments in English (K-42) |
| `0131` | hydra: `default` of `geompropvalue` set as an object attribute, read where the geometry does not have the primvar (K-90) |
| `0132` | hydra: anisotropic roughness of metals (conductor, generalized_schlick) converted to the anisotropy and rotation of the metallic_bsdf, UV tangent (K-91); a wired `weight` hidden on the original node |
| `0133` | hydra: anisotropic roughness of a reflective `dielectric_bsdf` (principled: `anisotropic`, `anisotropic_rotation`, tangent) (K-91) |
| `0134` | hydra: `anisotropic_vdf`: `scattering` as the color of the scatter_volume (density 1), `absorption` as an added absorption_vdf; the old translation read a nonexistent `albedo` (K-92) |
| `0135` | hydra: `layer` = top + base*(1-F) instead of a mix that counted the Fresnel of the top twice; F at the IOR of the top dielectric (K-09) |
| `0136` | hydra: full review of the delegate - alpha of a constant color lost on a Hydra node (K-93), wired OpenPBR `base_weight` counted twice (K-94), three malformed meshes that crashed husk: primvar too long, crease of length 0, out-of-bounds subset (K-95), read of a freed Python dictionary in the COP capture (K-96); the IOR of a weighted coat reaches its `layer` |
| `0137` | hydra: MaterialX libraries of a package also read (`materialx/` on HOUDINI_PATH, and `CYCLES_MATERIALX_SEARCH_PATH`): a studio nodedef defined as a nodegraph (MtlX Text) expands as it does under Karma |
| `0138` | hydra: the expansion of a nodegraph leaves the default values to CompleteMaterialXDefaults, which writes only the translated inputs (no more `frameoffset` / `frameendaction` in the log, two lines per frame and per render) |
| `0139` | hydra: `kma_stderiv` (Karma's ST Derivatives) translated as a zero derivative: the node is no longer lost with a warning, the shader falls back on its own width |
| `0140` | hydra: a node in a NodeGraph (Houdini material subnetwork), named "G/a" by Hydra, keeps its path; all of them fell onto the empty path and merged, so the network rendered a constant |
| `0141` | hydra: the last French comments and docstrings in English (Python resources, Render menu, four comment blocks in Cycles); no code change |
| `0142` | hydra: the Houdini package (`cycles.json`) finds the plugin through `$HOUDINI_PACKAGE_PATH` instead of the build prefix: no absolute path in the generated file (5.2: `0039`) |

---

## 0001 - cmake: missing USD libraries for the Houdini build

`FindUSDHoudini.cmake` did not list `hdsi`, which `src/hydra/file_reader.cpp`
needs for `HdSiExtComputationPrimvarPruningSceneIndex`. Result: `LNK2019` when
linking the standalone executable, and so a failure of the `install` target --
even though `hdCycles.dll` built correctly. `sdr` is required by the node
registry plugin (0005). Houdini provides both.

## 0002 - hydra: accept Houdini's AOV naming conventions

husk passes the `driver:parameters:aov:husk:name` of a `UsdRenderVar` as the
**Hydra AOV name**, not as a standard `HdAovTokens` token. Houdini names the
beauty `"C"`: a render var authored normally in Solaris therefore arrived
unmapped, its binding was discarded, and the render pass ended up with **no
binding at all**. But `IsConverged()` iterates over that list -- empty, it
returns true immediately, and husk wrote a blank frame.

Symptom: **black image, with no error or warning**, for any normally configured
Solaris scene.

## 0003 - hydra: apply constant primvars to all instances

A constant-interpolation `displayColor` describes the whole prim, and so all of
its instances. The `_instances[0]` index was hard-coded: with a
`PointInstancer`, only the first instance received the prototype's color, and
the others fell back to the shader's default color.

## 0004 - hydra: never leave a Shader without a graph

**Host application crash.** `Shader::tag_update()` reads `graph->output()`
without checking, but `HdCyclesMaterial` only assigns a graph once a material
network has been read successfully. A material whose network is unreadable by
the delegate -- a MaterialX material, for example -- went down the error branch,
and the freshly created shader reached `tag_update()` with a null `graph`.

Consequence: the mere presence of such a material in the stage made husk
segfault, whether or not the material was bound to any geometry.

## 0005 - hydra: publish the Cycles nodes in the USD shader registry

A discovery + Sdr parser pair that enumerates `NodeType::type_names()` **at
runtime** and publishes every `SHADER` node under the identifier
`cycles_<name>` -- the one that the delegate's material translation already
accepts. Reading the registry at runtime rather than generating definitions in
advance guarantees that the set of exposed nodes follows exactly the linked
Cycles version.

Registered in the existing `hdCycles` DLL so as not to duplicate the static
Cycles libs or their node registry in the process.

Pitfall: a discovery result published with an empty `SdrVersion()` can be parsed
by identifier but is **absent from the registry's enumeration**. It needs
`SdrVersion(1, 0).GetAsDefault()`.

## 0006 - hydra: translate MaterialX networks to Cycles nodes

Declares `mtlx` as a material render context and remaps the MaterialX nodedef
identifiers to native Cycles nodes, through the same machinery as
`UsdPreviewSurface`. Covers `standard_surface`, `image`, `normalmap` and
`texcoord`. The socket names were checked against the Cycles node registry, not
guessed.

Deliberately written as **one self-contained block**, removable in one piece the
day Cycles understands MaterialX natively.

## 0007 - hydra: give unbound volumes the default volume shader

A geometry without a material fell back on `scene->default_surface` whatever its
type. But a `Volume` needs a shader carrying a volumetric closure: an unbound
volume had its grid **loaded correctly** -- the NanoVDB texture is allocated and
shows up in the memory statistics -- but had nothing to scatter with, and
rendered as if it did not exist.

Misleading symptom: everything indicates the VDB is read, and yet the image is
empty at that spot.

Fix: pick `default_volume` for a `Volume` geometry.

## 0008 - hydra: register the renderer with Houdini

Adds a `UsdRenderers.json` (menu label, default purpose, husk defaults),
installed next to the already generated `cycles.json` package. Houdini merges
this file along the `HOUDINI_PATH`, whether the package points at the
installation.

Also adds a warning when a `cycles:integrator:<socket>` setting names a
nonexistent socket. Ignoring it silently is a trap: a misspelled name is
indistinguishable from a setting that has no effect. Note that husk swallows
`TF_WARN` -- the warning shows up in Solaris, not in batch rendering.

## 0009 - hydra: do not build an unusable GL context

`gl_context_create()` reads the calling thread's current GL context twice: via
`wglGetCurrentDC()` for the pixel format, and for `wglShareLists()`. With no
current context, it produced a context that was neither correctly formatted nor
shared with the host's, and that failed on first use.

Symptom observed in the Solaris viewport:
`PathTraceDisplay implementation could not begin update`, followed by a crash.

Fix: give up if there is no current context, and destroy the context if sharing
fails -- `gl_context_enable()` then reports the failure cleanly.

Also adds an environment setting **`CYCLES_DISPLAY_DRIVER=0`** to disable the
display driver completely. Hosts differ on when and on which thread a GL context
is current; rendering then goes through the output driver, slower to refresh but
with no GL requirement at all.

## 0010 - hydra: motion blur of animated object transforms

Only the camera was sampled over the shutter; geometry read a single transform
at time zero, so everything that moved rendered sharp.

Three points not to miss:

1. **The shutter is read from the render settings**, not from the camera prim --
   this avoids depending on the sync order between sprims and rprims, which is
   not guaranteed.
2. **The samples must be evenly spaced.** `Object::motion_time()` spreads the
   steps linearly over [-1, 1]; using the sampling times that USD reports, which
   are irregular, would blur along a distorted trajectory.
3. **`Integrator::motion_blur` must be enabled.** `Scene::need_motion()` only
   returns `MOTION_BLUR` in that case -- without it, the motion transforms are
   set but simply ignored.

The static transform is taken from the middle sample so that the blur is
centered on the shutter.

Known limit: this is **transformation** blur. Deformation blur (animated
points, or Karma-style `velocities` / `accelerations` attributes) remains to be
done -- see A8.

## 0011 - Host crash: unbalanced display driver locking

**This is the cause of the crash observed in the Solaris viewport.**

`gl_context_enable()` locks `mutex_` when it succeeds, but returns `false`
**without locking it** when no usable GL context exists. Two callers ignored
that return value -- `flush()` and `graphics_interop_activate()` -- and
`gl_context_disable()` called `mutex_.unlock()` unconditionally.

Unlocking a mutex that the thread does not own is **undefined behavior**, and
brings the application down.

The key point of the diagnosis: this path is only reached when the context is
missing, that is, exactly when the driver reports
`PathTraceDisplay implementation could not begin update`. The error message and
the segfault that followed it were not two problems, but **one**.

Fix in three points:

1. Track lock ownership so that `gl_context_disable()` releases only what was
   actually taken -- robust whatever the callers' discipline.
2. `flush()` gives up instead of issuing GL calls without a context.
3. Create the shared context **in the constructor** rather than at the first
   `draw()`: `draw()` has several early exits, so the render thread could reach
   `update_begin()` before any context existed.

## 0012 - Create the shared GL context before the early exits of draw()

`draw()` gives up in three cases -- missing display AOV binding, mismatched
dimensions, unused render buffer -- and `gl_context_create()` was placed
**after** all three. But the Cycles render thread calls `update_begin()` as soon
as the session starts: until a `draw()` had gone all the way through, no context
existed and every frame reported
`PathTraceDisplay implementation could not begin update`.

`draw()` runs on the thread where the host makes its GL context current, the
only place where a shareable context can be built. Doing it from the display
driver's constructor **does not work**: the render pass is not necessarily built
on that thread -- verified in practice, the error persisted.

Without patch 0011, this error led to the crash. With it, it was only noise;
this patch removes the noise.

## 0013 - Crash on teardown, and display driver disabled by default

The destructor called `glDeleteBuffers()` **without a current GL context**. It
runs on the thread where the host destroys the delegate -- switching renderer in
the viewport, for example -- which has no context of its own: the call went off
into the void and took the application down with it. `gl_context_dispose()` had
the same flaw, trying to destroy a context that was potentially still current.

Fix: make our context current for the duration of the deletions, and unbind it
before destroying it.

**And the display driver is now disabled by default.** Sharing the host's GL
context to blit the tiles into a texture produced **four distinct defects** in
Houdini's viewport:

1. unbalanced locking -> crash (0011)
2. context created too late -> error on every frame (0012)
3. wrong pixels -- the viewport displayed something resembling a depth pass
   rather than the beauty
4. GL calls without a context on teardown -> crash (this one)

The output driver path is the one that every batch render already uses, and it
is correct across the whole test battery. A less efficient refresh is better
than a viewport that displays wrong and crashes.

`CYCLES_DISPLAY_DRIVER=1` re-enables it for anyone who wants to work on it.
