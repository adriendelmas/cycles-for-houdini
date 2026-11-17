# Patches applied to Cycles

Cycles is not copied here: it has its own repository, and the changes live on a
branch of it, as commits separated by topic. This series is that branch exported
through `git format-patch`.

    patches/5.3/   181 patches, base v5.3.0 (b3f62626)

The branch is [`houdini`](https://projects.blender.org/starforge/cycles/src/branch/houdini)
of the fork on projects.blender.org: pull requests on the Cycles side go there.
`patches/5.3/BRANCH` names the commit the series was exported from, and
`tools/publish_cycles.py` is the only thing that writes the series
(`--check` tells whether the fork and the series are the same).

`tools/bootstrap.py` does the whole path - clone, `git am`, build. By hand, on a
clone of Cycles checked out at `v5.3.0`:

    git am <this repository>/patches/5.3/*.patch

Each patch carries, in its commit message, the bug it fixes or the feature it
adds and how it was checked. The `K-` numbers some of them quote are entries of
[`../docs/ISSUE_LOG.md`](../docs/ISSUE_LOG.md). Many of the fixes are to the Hydra
delegate itself and independent of Houdini: candidates for a contribution
upstream.

## Series

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
| `0025` | kernel/scene: MaterialX-exact procedural noise nodes |
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
| `0037` | checkboxes, Base section, and an ignored wire is no longer silent |
| `0038` | otls: stop tracking Houdini's automatic backups |
| `0039` | hydra: a Houdini ramp finally fills the table Cycles expects |
| `0040` | hydra: deformation blur for animated points |
| `0041` | the Cycles Material Builder was in no repository |
| `0042` | hydra: velocity blur, for geometry whose point count varies |
| `0043` | hydra: per-corner normals, instead of faceting what is not faceted |
| `0044` | hydra: reject enum values outside the registry instead of passing them on |
| `0045` | kernel: Random Walk (Legacy) was missing from the closure skip table |
| `0046` | hydra: one three-input terminal, instead of three contradicting connectors |
| `0047` | hydra: standard_surface dispersion now reaches the principled bsdf |
| `0048` | hydra: list Cycles GPU before Cycles CPU in the engine menu |
| `0049` | hydra: make the display driver and device choice usable |
| `0050` | hydra: pick the render device from Houdini's menu |
| `0051` | hydra: terminals whose output is not named BSDF were never connected |
| `0052` | hydra: material settings in a node instead of nowhere |
| `0053` | scene: displacement was added to itself on every material edit |
| `0054` | hydra: pick a texture's color space from a menu |
| `0055` | hydra: match lights to Karma, and render cylinder lights |
| `0056` | hydra: transmission and subsurface colors, finally translated |
| `0057` | hydra: a texture coming from a COP came out flipped |
| `0058` | hydra: COP textures go through memory, no longer through a file |
| `0059` | hydra: watch COPs, which nobody reports as changed |
| `0060` | hydra: a brake on the COP watch, and a way to turn it off |
| `0061` | hydra: a texture that changes, and a camera one leaves |
| `0062` | hydra: the COP watch puts the image back itself |
| `0063` | hydra: an image on a scalar input, and subsurface color removed |
| `0064` | hydra: a transmission lobe of its own, for MaterialX color and roughness |
| `0065` | hydra: give Cycles the camera used to dice subdivisions |
| `0066` | hydra: a preview shader for Cycles materials, or the viewport stays gray |
| `0067` | hydra: the MaterialX passthrough, two dead entries, and six more families |
| `0068` | hydra: stop flipping COP images, both ends already store them alike |
| `0069` | hydra: subdivision dicing rate in the render settings |
| `0070` | hydra: tools to measure a laggy viewport, and a log that goes somewhere |
| `0071` | hydra: a full card says so, and COPs only weigh their channels |
| `0072` | hydra: MaterialX hair, and the surface node that cut everything |
| `0073` | hydra: credit Ben Houston at the top of the MaterialX translation |
| `0074` | hydra: float3 primvars were copied at the wrong stride, and read as garbage |
| `0075` | hydra: mix, fades, saturate, facingratio, viewdirection, geomcolor: exact |
| `0076` | hydra: the ResolveUdimTiles declaration was missing from the series |
| `0077` | hydra: MaterialX closures - mix, add, multiply, volume, layer, conductor |
| `0078` | hydra: color/vector MaterialX operators, and three wrong scalar ones |
| `0079` | hydra: OpenPBR, glTF, Disney, surface defaults, UsdUVTexture channels, kma |
| `0080` | hydra: USD curves where USD places them, as tubes, and Curve Shape |
| `0081` | hydra: blurred instances, per-instance and scalar constant primvars |
| `0082` | hydra: USD implicit surfaces rendered, as fine meshes |
| `0083` | hydra: subdivide Catmull-Clark meshes without waiting for a display level |
| `0084` | hydra: eight keys per cubic curve segment, to follow the shape |
| `0085` | hydra: motion blur back, Houdini volume fields, and the transparent film |
| `0086` | hydra: render passes - lights, Karma LPEs, cryptomatte, shader AOVs |
| `0087` | hydra: per-object properties - ray visibility, holdout, shadow catcher |
| `0088` | hydra: light linking and shadow linking |
| `0089` | hydra: a prim whose render tag is no longer drawn disappears from the render |
| `0090` | hydra: turning motion blur off no longer makes objects vanish |
| `0091` | hydra: light groups and their passes |
| `0092` | hydra: diffuse and specular multipliers on USD lights |
| `0093` | hydra: the cryptomatte manifest in the image metadata |
| `0094` | hydra: Karma's combined emission and motion vectors |
| `0095` | hydra: the pass no longer blocks the UI, and the COP cache empties |
| `0096` | hydra: comments and log messages in English |
| `0097` | hydra: unfolded MaterialX nodegraphs, extract and swizzle, vector2 |
| `0098` | hydra: write MaterialX defaults on every unwritten input |
| `0099` | hydra: the CYCLES_LOG_FILE log timestamps every line |
| `0100` | hydra: pick the glass lobe on transmission, not on transmission_color |
| `0101` | hydra: check sizes before reading, no segfault on an unreadable attribute |
| `0102` | hydra: basic BSDF roughness as alpha, dielectric_bsdf by scatter_mode |
| `0103` | hydra: shipped nodegraphs, constant transformmatrix, F82, legacy Disney |
| `0104` | hydra: thin film into its BSDF, curveadjust passthrough, image alpha |
| `0105` | hydra: position, normal and tangent according to their space |
| `0106` | hydra: absorbing volumes, subsurface at the right scale, unlit surface |
| `0107` | hydra: translations fixed by comparing with Karma across the whole library |
| `0108` | hydra: surface base color before translation, glTF alpha, nodegraph images |
| `0109` | hydra: UsdPreviewSurface switches, texture colour spaces and wrap modes |
| `0110` | hydra: dome light texture in USD's lat-long orientation |
| `0111` | hydra: rect light texture, spot cone softness and emission focus as USD says |
| `0112` | hydra: IES profiles read along the emission direction, in USD's units |
| `0113` | hydra: the camera's exposure reaches the film |
| `0114` | hydra, scene: subdivision creases, corners, boundary rules and holes |
| `0115` | hydra: per-vertex texture coordinates go to Cycles per corner |
| `0116` | hydra: fallback widths for points and curves, UsdPreviewSurface displacement |
| `0117` | hydra: left-handed subdivided meshes the right way round |
| `0118` | hydra: crop windows and pixel aspect under husk |
| `0119` | hydra: disableDepthOfField and the aperture conform policy |
| `0120` | hydra: displayOpacity on prims without a material |
| `0121` | hydra: per-vertex displayColor on prims without a material |
| `0122` | hydra: motion blur turned back on in a live viewport |
| `0123` | hydra: UsdUVTexture fallback for a file that cannot be found |
| `0124` | hydra: alpha compositing nodes, hextilednormalmap, volume primvars |
| `0125` | hydra: cook op: COP textures to files as a USD Render ROP saves |
| `0126` | hydra: split lights for lobe multipliers, shadow colour and shadowless lights |
| `0127` | hydra: computed colour4 alpha, BSDF weight, geompropvalue colours |
| `0128` | hydra: render cylinder lights as an emissive tube |
| `0129` | hydra: viewport preview through mixes; translator comments in English |
| `0130` | hydra: geompropvalue default for a missing primvar |
| `0131` | hydra: anisotropic roughness on conductor and generalized Schlick |
| `0132` | hydra: anisotropic roughness on a reflecting dielectric_bsdf |
| `0133` | hydra: anisotropic_vdf scattering and absorption coefficients |
| `0134` | hydra: layer as top plus attenuated base, at the coat's IOR |
| `0135` | hydra: fixes from a full review of the delegate |
| `0136` | hydra: read custom MaterialX node libraries from HOUDINI_PATH |
| `0137` | hydra: leave a nodegraph's value defaults to CompleteMaterialXDefaults |
| `0138` | hydra: Karma's ST Derivatives as a zero derivative |
| `0139` | hydra: nodes inside a nested nodegraph keep their path |
| `0140` | hydra: the last French comments and docstrings in English |
| `0141` | hydra: the Houdini package finds the plugin next to itself, not at the build prefix |
| `0142` | hydra: CYCLES_DUMP_PRIMS=1 logs each prim the scene index adds |
| `0143` | hydra: Karma Physical Sky, and karma:global:enable_dof |
| `0144` | hydra: Karma's Hextiled Triplanar as the delegate's own nodegraphs |
| `0145` | hydra: the orthographic window is scaled by metersPerUnit |
| `0146` | util + hydra: 8-bit sRGB textures decoded without an OCIO config; image `default` consumed |
| `0147` | hydra + scene: a mix of many standard_surface blended by its inputs; SVM stack diagnostics |
| `0148` | hydra + util: textures inside a usdz archive; material:binding:full resolved |
| `0149` | hydra: an instance's transform composed as scale, orientation, position, then the instancer's |
| `0150` | hydra: display driver off by default again, the view logged |
| `0151` | hydra: tie a single surface's accumulated layers for the SVM compiler |
| `0152` | hydra: tie a single surface's layers from two accumulations on |
| `0153` | hydra: randomfloat and randomcolor from the library's nodegraphs |
| `0154` | hydra: a bumped chain's layer ties depend on the base colour's accumulation |
| `0155` | hydra: a MaterialX bump's scale is the Cycles bump node's distance |
| `0156` | hydra: authored normals are turned to the side their faces wind towards |
| `0157` | hydra: objects visible to raycast rays again after the 5.3 visibility split |
| `0158` | cmake: a standalone build gets Embree again |
| `0159` | rebase fixes: missing-image colour in hextile, device memory in the host warning |
| `0160` | hydra + kernel: Gaussian splats from USD, composited without noise |
| `0161` | hydra: a camera with a near clip of 0 renders instead of staying black |
| `0162` | hydra: one tile at any resolution - 4K renders no longer hang or fail |
| `0163` | gsplat: ellipsoid bounds, composite marker that works on OptiX |
| `0164` | gsplat: composited splats in a TLAS of their own, S^-1 R^T precomputed |
| `0165` | integrator: Light Optimize, the render sampled as if the lights were brighter |
| `0166` | film: a light group pass no longer takes the place of the beauty with the denoiser |
| `0167` | hydra: Cycles AOVs LOP, Blender's View Layer passes as render vars |
| `0168` | hydra: Cycles AOVs LOP, Object Index help says the ids change between renders |
| `0169` | hydra: light groups from Karma's LPE tags on objects and C.*[<L.'tag'>O] |
| `0170` | hydra: Cycles Render Settings LOP, Cycles (Setup) tool, AOV Auto Fill |
| `0171` | gsplat: composited splat emission goes to the splats' light group |
| `0172` | hydra: Cycles LOPs show their icon - embedded section named IconImage.png |
| `0173` | hydra: the viewport shows render settings' vars, not depth (K-129) |
| `0174` | gsplat: SplatEmit and BeautyNoSplatEmit, the splats' direct emission apart |
| `0175` | hydra: the splats' direct emission pass gets the film exposure |
| `0176` | gsplat: each light group gets its own splats' share of a segment |
| `0177` | hydra: cycles:denoise_aovs, OIDN on the render vars listed |
| `0178` | hydra: menus for Denoise AOVs and light group names |
| `0179` | hydra: world shader from a material bound to the dome (K-119) |
| `0180` | hydra: Cycles Render Settings HDA rebuilt on the 5.3.0 settings |
| `0181` | hydra: the atmosphere's world volume as Volume Scatter and Volume Absorption nodes |
| `0182` | integrator: Light Optimize removed, it is not a Cycles feature (undoes `0165`) |
