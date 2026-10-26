# Wet map in the shader - implementation plan

A time-accumulated wet map computed by the renderer itself, GPU-native, with no
bake: a surface remembers the water it touched on earlier frames and dries over
time. Written 2026-10-26 from a reading of `external/cycles-53` (Cycles 5.3,
`houdini-fixes-53`) and of the delegate; nothing here has been compiled or
rendered yet. Every file and line below was read, every claim marked
*unverified* was not.

Two pieces, independent, in this order:

- **A. Target-set ray tracing** - the AO node (and later a distance output)
  traces against a chosen set of objects only ("the water"), on CPU and GPU.
- **B. Persistent per-object state** - a shader node that reads a value left
  by the previous frame and writes one for the next, with the accumulation
  rule (`wet rate`, `dry time`, `max`) as linkable inputs.

## 0. Scope

**V1 does:** one wet value per Cycles object (one PointInstancer instance is
one object), updated once per frame from what the camera sees of it, kept in
memory across the frames of one husk run or one viewport session, optionally
written to and read from disk per frame. A shader adds the per-pixel detail
(noise, orientation, height) itself from that value.

**V1 does not:** store state per texel or per vertex; update objects the
camera does not see; transfer water between objects; render frames out of
order or in parallel on a farm without the per-frame state files. These are
the limits of the design, not of the implementation - say so in the docs.

## 0b. Partition: this is an addition, not hdCycles

Everything that belongs to the wet map is recognizable by name, lives in its
own files where a file can be its own, and is documented in this file and in
one section of PROGRESS.md - so that it can be read, reviewed, disabled or
removed as one piece, and so that nobody mistakes it for upstream Cycles.

| Layer | Rule | Names |
|---|---|---|
| Commits / patches | Subject prefixed `wetmap:`; one block "Wet map (addition)" in `patches/README.md`, after the fixes | `0153-wetmap-...` onwards |
| Kernel | Own headers; the only shared edits are the dispatch line in `svm.h`, the node type line in `node_types_template.h`, the arrays in `data_arrays.h`, the flag in `svm/types.h`, the bit in `types.h`, each with a `/* wetmap */` comment | `kernel/svm/wet_state.h`, `NODE_WET_STATE`, `SVMNodeWetState`, `wet_prev`, `wet_accum`, `wet_count` |
| Scene / session | Own manager, own node class file; shared edits limited to the registration lines | `scene/wet_state.{h,cpp}` (`WetStateManager`, `WetStateNode`), `Scene::wet_manager`, sockets `wet_*` on the integrator |
| Delegate | Own file for the frame commit and the keys; `render_pass.cpp` gets one call | `hydra/wet_state.{h,cpp}` (`HdCyclesWetState`), `Object::wet_key` |
| Houdini | Node `cycles_wet_state` ("Wet State", `Cycles/Input`); settings under one `Wet Map` tab of the Render Settings; the geometry toggle in the Visibility group | `cycles:integrator:wet_*`, `cycles:object:trace_target` |
| Tests | Own folder and bench | `tests/wet/`, `tools/bench_wet.py` |
| Docs | This plan, then `docs/WETMAP.md` for users; a "Wet map (addition)" section in PROGRESS.md and KNOWN_ISSUES.md; nothing of it in the generic sections | - |

The one deliberate exception: the **trace-target bit** (piece A) is a generic
Cycles feature - a visibility bit and an AO option - useful without any wet
map. It keeps a generic name (`trace_target`), but it is still committed with
the `wetmap:` prefix and listed in the same block, because it exists for this
project.

Not done, by choice: a `WITH_WETMAP` compile switch. It would scatter `#ifdef`s
through the kernel, which must also reach the CUDA and OptiX kernel builds;
the names and files above give the same legibility without that cost.

## 1. What exists and is reused

| Need | Already in Cycles | Where |
|---|---|---|
| A ray-visibility bit set per object, honoured by every BVH | `PathRayVisibilityFlag`, 7 bits used, `uint8_t` in the integrator state | `kernel/types.h:151-178` |
| A shader node that traces rays, with an OptiX direct callable | `svm_ao` / `__direct_callable__svm_node_ao`, flags byte | `kernel/svm/ao.h`, `device/optix/device_impl.cpp:690` |
| A device buffer the kernel writes and the host reads back | `KERNEL_DATA_ARRAY_WRITABLE(uint8_t, image_texture_tile_access_state)`, `mem_or_from_device`, `copy_from_device` | `kernel/data_arrays.h:95`, `scene/image.cpp:584`, `scene/image.cpp:785` |
| Float atomics on every device | `atomic_add_and_fetch_float` | `util/atomic.h` |
| A node that writes only on primary camera hits | `svm_node_aov_check`, `svm_node_aov_value` | `kernel/svm/aov.h:14-61` |
| Per-object properties from Houdini's Render Geometry Settings | `cycles:object:*` primvars → `Object` | `hydra/object_properties.cpp`, `tools/gen_render_properties.py:214` |
| Render settings generated from integrator sockets | `SOCKET_*` in `integrator.cpp` → `<Renderer>_Global.ds` | `tools/gen_render_properties.py` |
| Nodes published to USD and to Houdini VOPs automatically | Sdr registry walk, `build_cycles_vops.py` | `hydra/sdr_cycles.cpp:215` |
| The frame's time and fps from the stage | `HdSceneGlobalsSchema::GetTimeCodesPerSecond`; `GetCurrentFrame` exists in Houdini's USD | `hydra/geometry.inl:104`, `$HFS/toolkit/include/pxr/imaging/hd/sceneGlobalsSchema.h:133` |
| husk renders a frame range in one process, one delegate | measured for the displacement fix | `docs/STATUS.md:1382` |
| The end of a completed render, on the session thread | `PathTrace::write_tile_buffer` → `output_driver_->write_render_tile` | `integrator/path_trace.cpp:857-886` |

## 2. Design

### A. Target-set tracing

> **Revised 2026-10-26 (S1).** The first draft of this section, read from the
> 5.2 tree, wanted a new visibility bit 7. In 5.3 that bit exists already:
> `PATH_RAY_VISIBILITY_RAYCAST` (`kernel/types.h:169`), the bit the new
> **Raycast node** traces with (`kernel/svm/raycast.h:79`), and
> `PATH_RAY_VISIBILITY_ALL` is `0xFF`: the eight bits the OptiX hardware mask
> holds are all taken. No new bit, then - the raycast bit *is* the target set.

- An object is a target when it keeps its **raycast visibility**; every other
  object has it turned off. Objects carry the bit by default (it is in
  `ALL`), so the delegate exposes it like the other ray types:
  `cycles:object:visibility:raycast` (`object_properties.cpp`, the `rays`
  table) and a "Raycast Rays" toggle in the Visibility group of the Render
  Geometry Settings (`gen_render_properties.py`). In Solaris one Render
  Geometry Settings LOP on `* - /water` turns it off everywhere but the water.
- `AmbientOcclusionNode`: `SOCKET_BOOLEAN(raycast_visibility, "Raycast Visibility", false)`
  → flag `NODE_AO_RAYCAST_VISIBILITY = (1 << 3)` (`kernel/svm/types.h`). In
  `svm_ao` the non-local branch traces with `PATH_RAY_VISIBILITY_RAYCAST`
  instead of `SHADOW_OPAQUE` when the flag is set; the OSL path carries the
  flag through the `swidth` texture option (`services_shared.h`,
  `node_ambient_occlusion.osl`). No kernel structure, no new OptiX program
  group, no change to any mask.
- The **Raycast node itself** is the native alternative for a wet line: one
  ray along `-N` (or straight down) with a length, `Hit Distance` out,
  already limited to raycast-visible objects. The AO form gives a cone, the
  raycast form a direction; both read the same per-object toggle.
- Later (not V1): a `Distance` output on the AO node (min hit distance
  normalized), which a wet line wants more than an occlusion ratio.

### B. Persistent state

**Kernel.** New node `NODE_WET_STATE` (appended to
`kernel/svm/node_types_template.h`), struct `SVMNodeWetState` in
`node_types.h` with `SVMInputFloat contact, wet_rate, dry_time, max_wet;
SVMStackOffset out_wet;` (+ padding, both `static_assert`s). Handler
`kernel/svm/wet_state.h`, dispatched from `svm.h` **outside** the
`#ifdef __SHADER_RAYTRACE__` block. It:

1. reads `wet_prev[sd->object]` and writes `out_wet = max(wet_prev × 1, …)` -
   the output is simply `wet_prev` blended with the current contact for
   immediate feedback: `out = clamp(max(wet_prev, contact), 0, max_wet)`;
2. on primary camera hits only (the `svm_node_aov_check` idiom:
   `render_buffer != nullptr`, `PATH_RAY_TRANSPARENT_BACKGROUND`, not
   `SINGLE_PASS_DONE`, not `PATH_RAY_SHADOW_CATCHER_PASS`), and only while
   `INTEGRATOR_STATE(state, path, sample) < kernel_data.integrator.wet_accum_samples`,
   atomically adds `contact`, `wet_rate`, `dry_time`, `max_wet` into
   `wet_accum[5 * object + k]` and `1` into a `uint` count.

Four writable arrays in `data_arrays.h`: `KERNEL_DATA_ARRAY(float, wet_prev)`,
`KERNEL_DATA_ARRAY_WRITABLE(float, wet_accum)`,
`KERNEL_DATA_ARRAY_WRITABLE(uint, wet_count)`. Guards: `sd->object != OBJECT_NONE`,
a surface shader evaluation (displacement and volume evaluations pass through
the same `svm_eval_nodes`).

**Scene.** `scene/wet_state.{h,cpp}`: `WetStateManager`, owned by `Scene`
like `bake_manager`:

- `device_update(device, dscene, scene)` after `object_manager->device_update`
  (`scene/scene.cpp:296`): size the three vectors to `scene->objects.size()`,
  fill `wet_prev[i]` from a host map keyed by the object's **stable key**
  (§3), `copy_to_device_if_modified`, zero the accumulators
  (`zero_to_device`).
- `need_update()` added to `Scene::need_data_update` (`scene.cpp:488`) so an
  updated `wet_prev` reaches the device without touching the BVH or shaders.
- `read_back(device)`: `copy_from_device` of `wet_accum` and `wet_count` into
  host vectors; `completed` flag.
- `commit(dt)`: for every object with `count > 0`:
  `mean_k = accum_k / count`; then
  `wet = clamp(wet_prev × exp(-dt / dry_time) + wet_rate × dt × contact, 0, max_wet)`;
  objects with `count == 0` (unseen) keep `wet_prev` unchanged. Result goes
  back into the host map under the stable key.
- `save(path)`, `load(path)`: the map, as a flat binary file (key length, key
  bytes, float) - or JSON if a dependency is already linked; check before
  adding one.
- `tag_reset()`: forces a device update on the next `Scene::device_update`
  (accumulators must be zeroed on every session reset, see pitfall 16).

**Session.** `Session::reset` (`session/session.cpp:585`) calls
`scene->wet_manager->tag_reset()`. In `PathTrace::write_tile_buffer`
(`path_trace.cpp:857`), before the output driver callback, when
`render_scheduler_.done()` and not cancelled: `wet_manager->read_back(device)`
and mark `completed`. That runs on the session thread, which owns the device,
exactly as the tile pixels are read there.

**Integrator sockets** (`scene/integrator.cpp`, near `ao_*` at line 79):
`SOCKET_INT(wet_accum_samples, "Wet Accumulation Samples", 16)`,
`SOCKET_STRING(wet_state_dir, "Wet State Directory", "")`,
`SOCKET_BOOLEAN(wet_reset_on_jump, …, true)`. `wet_accum_samples` goes to
`kernel_data.integrator` through `kernel/data_template.h:187` and
`integrator.cpp:236`. They appear in the Render Settings tab after
`gen_render_properties.py` (string sockets: verify the delegate's
`cycles:integrator:<socket>` path accepts strings - pitfall 43).

**Delegate.** The commit happens **on the host, when the frame changes**, not
in the render-end callback (pitfall 16, 17):

- `HdCyclesRenderPass::_Execute` (`render_pass.cpp`, before the reset block
  at line 314) reads `currentFrame` and `timeCodesPerSecond` from
  `HdSceneGlobalsSchema::GetFromSceneIndex(GetRenderIndex()->GetTerminalSceneIndex())`
  - the same source as `geometry.inl:104`.
- `HdCyclesSession` keeps `_wetFrame` (the frame the current accumulation
  belongs to) and `_wetFrameValid`. When `currentFrame != _wetFrame`:
  - if the manager has a completed read-back for `_wetFrame`:
    `commit((currentFrame - _wetFrame) / fps)`, then `save(dir/wet_<frame>.bin)`
    if a directory is set;
  - if `|currentFrame - _wetFrame| != 1` and `wet_reset_on_jump`: try
    `load(dir/wet_<currentFrame-1>.bin)`, else clear the map and
    `LOG_WARNING` once ("wet state restarted at frame N: no state for N-1");
  - `_wetFrame = currentFrame`.
- Stable key for each object: set at `InitializeInstance`
  (`geometry.inl:337`) as a string `"<prim path>#<instance index>"` on the
  Cycles `Object` (new `ustring wet_key` socket, or reuse `asset_name` +
  `instanceId` attribute - see §3). Lights get none.

### Houdini layer

- `tools/gen_render_properties.py` `GEOMETRY`: `("Visibility", … ("primvars:cycles:object:trace_target", "Trace Target", "toggle", "bool", "0"))`.
- `hython tools/build_cycles_vops.py` regenerates `cycles_vops.hda`: the AO
  node gains its toggle, `cycles_wet_state` appears under `Cycles/Input`
  (category and label come from the generator's prefix tables - give the new
  node the label "Wet State").
- `tools/count_nodes.py`, `docs/CYCLES_VOPS.md`, `README.md` counts change
  (163 → 164 nodes, 100 → 101 VOPs, one more bench scene and reference).
- The node is a native Cycles VOP: it renders inside a **Cycles Material
  Builder** only. The MEGALIB materials are MaterialX; to drive them a
  MaterialX nodedef (`ND_cycles_wet_state_float`, shipped in the package) and
  one `MtlxTable()` row in `material.cpp` are needed. Phase E.

## 3. Object identity across frames

Cycles object indices are reassigned at every `ObjectManager::device_update`
(the order of `scene->objects`, which changes when prims appear or vanish),
and a Hydra prim rebuilt on a topology change gets new `Object*`
(`geometry.inl:292-334`). The device slot is the index, the persistent key
is not.

- Key = prim path + instance index, as a string; `random_id`
  (`geometry.inl:354`) is a 32-bit hash of the same and can collide - do not
  use it as the key.
- A PointInstancer whose point order changes between frames moves the keys
  with it. V1 accepts this; the fix is to key on the instancer's authored
  `ids` primvar when present (`instancer.cpp:105` reads `instanceIndices`, not
  `ids`). Say so in KNOWN_ISSUES.
- Nested instancers are flattened to one `Object` per leaf instance - one
  slot each, as wanted.

## 4. Order of work

Each step is one commit on `houdini-fixes-53`, one patch (`0153` onwards),
one row in `patches/README.md`, PROGRESS.md in the same commit.

| Step | What | Done when |
|---|---|---|
| **S0 Spike** - **done 2026-10-26** (patch 0153) | `currentFrame` **arrives under husk**: `--frame 1 --frame-count 3` ran one delegate through frames 1, 2, 3 with `timeCodesPerSecond` 24 (`dt` 0.0417 s), one `Render restarted: scene` per frame. `write_render_tile` **does fire on cancel** - read, not run: `render_scheduler.cpp:259` sets `tile.write` for a cancelled render that has samples (pitfall 16 stands). The build has `WITH_CYCLES_OSL=ON` (pitfall 11 stands: the `.osl` stub is mandatory) and ten CUDA architectures (pitfall 30). Not done: the viewport reading of `currentFrame` (needs a GUI session; the code handles its absence), the kernel rebuild timing (S1 measures it). Seen on the way: `install-53/houdini/lib/` holds OptiX `.ptx` of Oct 25 next to CUDA `.cubin` of Oct 14 - check both dates after S1 (pitfall 29) | - |
| **S1 Target set** - **done 2026-10-26** (patch 0154) | §2.A as revised: `raycast_visibility` on the AO node (flag `NODE_AO_RAYCAST_VISIBILITY`, OSL through `swidth`), `cycles:object:visibility:raycast` and its "Raycast Rays" toggle; `gen_render_properties.py`, `build_cycles_vops.py` rerun (the AO VOP carries the toggle). **Measured**: `bench_wet.py --gpu` 10/10 - the raycast-visible plane occludes (AO 0.011 against the 0.01 the geometry predicts), the raycast-hidden one does not (0.996 / 0.999), the control occludes (0.011), the all-hidden plane does not occlude on OptiX either (0.999: pitfall 3 does not bite), CPU and OptiX agree. Full rebuild with the ten CUDA architectures and OptiX: **26 min** (07:47-08:13), every kernel dated after it. First OptiX render after a kernel change: 137 s of pipeline compile, once (pitfall 32) | - |
| **S2 State node, in memory** - **done 2026-10-26** (patch 0155) | §2.B as planned, two details settled while building: the read-back lives in `Session::run_main_render_loop` where the loop finds no work left and no cancel (`RenderScheduler::done()` is protected, and the cancel path writes a tile too); the shader output is `min(max(prev, contact), max_wet)`, so a still frame shows its contact. **Measured** (`bench_wet.py --gpu`): the 8-frame sequence within 0.03 of the formula on both devices (OptiX 0.749, 1, 1, 1, 0.847, 0.718, 0.608, 0.516 for 0.75, 1, 1, 1, 0.846, 0.717, 0.607, 0.513), frame 2 twice reads 0.75 twice, CPU and OptiX within 0.03 - the CPU's AO alone stops 0.8 % of its rays on the probe's own coplanar triangle (`free` 0.992 vs 0.999). Full rebuild of the kernels: about 20 min this time (the host-only target had already built them) | - |
| **S3 State on disk** | `wet_state_dir`, `save`/`load`, jump handling | case 7 |
| **S4 Houdini finish** | labels, docs (`PROGRESS`, `KNOWN_ISSUES`, `TESTING`, `CYCLES_VOPS`, counts), `make_dist.py` check | docs and README numbers agree with `count_nodes.py` |
| **S5 MaterialX bridge** (optional) | nodedef + table row so a MaterialX material can read the wet value | a `standard_surface` with `base_color` driven by the nodedef renders the same as the native graph |

## 5. Pitfalls - the hours-losers, in advance

Kernel and visibility

1. **Read the tree you build.** Pitfalls 1-3 of the first draft were written
   from `external/cycles` (5.2); 5.3 had taken bit 7 for the Raycast node in
   the meantime. Every line number in this plan is now from `cycles-53`;
   anything added later must be read there too.
2. **The raycast bit is in `ALL`**: every object is a target until its
   `visibility:raycast` is turned off. The default is "everything occludes",
   which is the old AO behaviour, so the flag changes nothing until the user
   authors the toggle; the docs must say that the water is selected by
   turning the others *off*.
3. **OptiX turns a zero mask into 0xFF** (`device_impl.cpp:1801`): an object
   hidden from every ray type becomes hittable by *every* mask, the raycast
   one included, on OptiX only. Test it (case 5); if it bites, give such
   objects `0x7F` there instead of `0xFF`, or skip them in the kernel by
   object flag.
4. The `|= 4` on ribbons and point clouds (`device_impl.cpp:1811`) touches bit
   2, not ours - harmless, noted so nobody hunts it.
5. HIP-RT builds its own masks (`kernel/device/hiprt/bvh.h`), Metal has its
   own path: **unverified**; the machine is NVIDIA. Say "OptiX and CPU" in the
   docs until measured.
6. OptiX refuses a **zero ray mask** - the wet trace always passes bit 7, fine;
   but a `trace_target_only` AO in a scene with no target object returns
   "unoccluded" everywhere, which is correct and must be the documented
   behaviour, not a bug report.
7. The AO node already demands `KERNEL_FEATURE_NODE_RAYTRACE`
   (`shader_nodes.h:898`); the state node must **not**, or every material
   using it drags the slower raytrace kernel in.
8. The AO dispatch sits under `#ifdef __SHADER_RAYTRACE__` (`svm.h:580`); the
   state node goes **outside** it or it vanishes from the ordinary kernel.
9. `SVMNode*` structs need both `static_assert`s and explicit `_pad` to a
   multiple of 4 bytes (`node_types.h:1278`); linkable inputs are
   `SVMInputFloat` (constant or stack offset, `compiler.input_float`), outputs
   `SVMStackOffset` checked with `stack_valid`.
10. Append the node type at the **end** of `node_types_template.h`; the enum
    is shared by host and kernel, both rebuilt, but an insertion renumbers
    every later node in anyone's cached kernel.
11. **OSL.** `bootstrap.py` has a `WITH_CYCLES_OSL` switch (line 94). If the
    build is ON, every node's `compile(OSLCompiler&)` names a `.osl` that
    must exist in `kernel/osl/shaders/` or the oso build step fails: ship a
    `node_wet_state.osl` that returns 0 (OSL = CPU only, no accumulation).
    Check the switch before S2.
12. **Which evaluations write.** `svm_eval_nodes` also runs for displacement,
    shadow, volume and background shading, with other `state` types. Copy the
    AOV idiom exactly (`aov.h:14`): `render_buffer != nullptr`,
    `PATH_RAY_TRANSPARENT_BACKGROUND` set, `PATH_RAY_SINGLE_PASS_DONE` clear;
    add `!(path_flag & PATH_RAY_SHADOW_CATCHER_PASS)` (shadow catchers shade
    twice) and `sd->object != OBJECT_NONE` (background).
13. **Float32 sums.** A sum near 1e7 has an ulp of 1: adding 0.5 rounds to 0
    or 1 and the mean drifts. Cap the writers with `wet_accum_samples`
    (default 16 samples per pixel: coverage is the same on every sample, the
    contact barely changes) and count in a `uint`. With 4K × 16 samples the
    worst slot sees ~1.3e8 adds only if one object fills the frame - still
    fine for a mean in [0, 1]; document the setting.
14. Float atomics are order-dependent: two renders differ in the last
    bits. Tests compare with tolerances, never bit-exact.
15. **Multi-device** (CPU+GPU, two GPUs): each sub-device holds its own copy;
    `mem_or_from_device` is an OR, not a sum. V1: read back from one device
    and `LOG_WARNING` once under `MultiDevice`; a `mem_add_from_device` is
    the proper fix.

Threads and time

16. **`write_render_tile` fires on cancel too** (`render_scheduler.cpp:428`
    sets `tile.write` when cancelling). Read back only when
    `render_scheduler_.done()`; and never **commit** there: commit on the
    host when the frame changes. Zero the accumulators on every
    `Session::reset` (`tag_reset`), or a cancelled viewport pass leaks samples
    into the next.
17. **The viewport re-renders the same frame endlessly** (`Render restarted:`
    in the log). Without the `currentFrame != _wetFrame` guard the state
    advances on every camera move. With it, scrubbing is a sequence of
    commits, each from the last completed render of the frame left behind;
    a frame left before any render completed carries the state unchanged and
    logs once.
18. `_Execute` runs on the host thread under `scene->mutex` while the render
    thread may be mid-sample (patch 0014): **no device read there**. Device
    reads live in `PathTrace` on the session thread; the host commit only
    touches host vectors.
19. `currentFrame` may be absent (older scene indices, the free viewport):
    fall back to "no time, no commit" and `LOG_INFO` once, so the node still
    renders the current contact.
20. `dt` = frame delta / `timeCodesPerSecond`, default 24 when the stage has
    none (`geometry.h:68`). A backwards or non-unit jump is a sequence
    break: load `wet_<frame-1>.bin` or restart, never apply a negative `dt`.

16b. **A manager's `need_update()` is a render restart.** `Scene::need_data_update`
    feeds `need_reset`, which `_Execute` reads on every render pass: a flag
    raised by `Session::reset` itself (the first `tag_reset` did) is true on
    every pass until the render thread's `device_update` clears it - on a
    scene whose update takes seconds (442 000 instances), every Hydra redraw
    restarted the session again, cancelling the update in progress, and the
    GPU viewport died with "illegal address in CUDA" (2026-10-26, 0155,
    Adrien's gauge scene; fixed in 0156). A reset-time action that needs no
    scene data runs on the session thread when the delayed reset is applied
    (`Session::update_scene`, `zero_device`), never through `need_update`.

Scene and identity

21. Object indices move between frames (§3): key by string, fill `wet_prev`
    by key at every `device_update`.
22. `random_id` (`geometry.inl:354`) is a 32-bit hash: not a key.
23. `keep_nodes` (`geometry.inl:299`) keeps `Object*` across a Finalize; the
    key by string makes this irrelevant, but the slot count still changes.
24. Our `need_update()` goes into `need_data_update` (`scene.cpp:488`) and
    **nowhere else**: a per-frame `wet_prev` upload must not tag objects,
    geometry or shaders, or the BVH rebuilds every frame.
25. `Scene::reset()` (`scene.cpp:503`) runs on every session reset: it must
    not clear the host map, only the device accumulators.
26. `sd->object` is the device object index, the same `instanceId` OptiX
    carries (`device_impl.cpp:1791`): size the arrays to
    `scene->objects.size()`, lights included (they get a slot and never
    write).
27. The water's property is read from the **prototype's** constant primvars
    and applied to each instance (`object_properties.cpp` via
    `geometry.inl`): an instanced water surface works, but every instance of
    that prototype is a target.
28. A submerged object: rays from inside the water hit its back face, so
    "contact" is 1 under the surface as well - wanted, but the AO sign is the
    opposite of intuition (occluded = wet): invert in the shader, document.

Build and install

29. **Stale kernels.** The GPU kernels live in `install-53/houdini/lib/`
    (`docs/CYCLES_53.md`); a new DLL next to old `.ptx`/`.cubin` renders the
    old behaviour with no error. After every build: timestamps of the DLL
    **and** of `kernel_optix_shader_raytrace.ptx` / the cubins, then `grep -c -a`
    a new string in the DLL.
30. `bootstrap.py` compiles ten CUDA architectures (`STATUS.md:2616`): for
    iteration, configure with `CYCLES_CUDA_BINARIES_ARCH=sm_86` only and
    restore the list for the distribution.
31. Houdini locks `hdCycles.dll`; cmake returns 0 on a failed install
    (`CONVENTIONS.md`). Close Houdini or test from a temporary plugin tree
    (`TESTING.md`). One build at a time.
32. The OptiX module cache is keyed by content: no manual purge, but the
    first render after a kernel change takes the compile time - do not read
    it as a regression.

Registry, VOPs and benches

33. The new socket and node reach the Sdr automatically (`sdr_cycles.cpp:215`
    publishes every `SHADER` node) and the VOP library only after
    `hython tools/build_cycles_vops.py` - **per installation, never copied**
    (`CYCLES_53.md`). The toggle is a boolean: the generator makes a checkbox
    from the metadata the delegate sets (`CYCLES_VOPS.md`).
34. `bench_export.py` writes one scene per node: the new node needs its
    scene, its reference accepted with `bench_diff.py --accept cycles_wet_state`
    in a reviewed commit, and `count_nodes.py`'s numbers updated in the three
    places that quote them.
35. The AO node's reference image must not move: the new flag defaults to
    off. `bench_diff.py` is the check.
36. `gen_render_properties.py` must be rerun for the Global tab (new
    integrator sockets) and writes the Geometry tab from its `GEOMETRY` list:
    both `.ds` files are generated, never edited (`CONVENTIONS.md`).
37. A `SOCKET_STRING` on the integrator through `cycles:integrator:<socket>`:
    the settings path was measured on numbers (`STATUS.md` phase 9), strings
    **unverified** - the spike checks it, else the directory becomes a
    `cycles:wet_state_dir` render setting read by the delegate directly.
38. Houdini's `$F` in the directory path would resolve to the *current* frame
    at export: the delegate composes `wet_<frame>.bin` itself from a plain
    directory.

Pipeline

39. Frames must be rendered **in order, in one process** (or chunked on a
    farm, chunks in order, with the state files): a documented limit, with the
    husk line that respects it (`husk --frame-count N`).
40. Karma renders none of this: a scene sharing materials between the two
    renderers differs by design.
41. Logging: `LOG_WARNING` / `LOG_INFO`, never `TF_WARN` (husk swallows it);
    one line per cause, per-frame lines gated.

## 6. The bench: `tools/bench_wet.py`

One USD scene, written by the script as the other benches do
(`bench_instances.py` is the model): an orthographic camera looking down, a
water plane (`cycles:object:trace_target = 1`) whose height is animated over
frames 1-6 (up for 1-3, down for 4-6), three unlit cubes at three heights, a
fourth cube hidden from every ray type next to the water, a wall that is not a
target. Each cube's emission is `wet` × white so the image reads the state.
Rendered with husk `--frame-count 6` on CPU and on OptiX, 120×90, into
`tests/wet/output/`.

| Case | Checks | Pitfall |
|---|---|---|
| 1 | AO with `trace_target_only` on a cube beside the wall, far from the water: unoccluded (1 ± 0.02) | 1, 6 |
| 2 | Same cube touching the water: occluded on the wet side | A |
| 3 | Cube wetted on frame 3, water gone on 4-6: emission follows `exp(-dt/dry_time)` within 5 % per frame | B, 20 |
| 4 | Frame 3 rendered twice in one run (two products of the same frame): identical within 1e-3 - no double advance | 17 |
| 5 | The hidden cube does not occlude the wet trace on OptiX | 3 |
| 6 | CPU and OptiX agree within 2 % on every frame | 14, 15 |
| 7 | Frames 1-3 with a state directory, then frame 4 alone: equals frame 4 of the continuous run within 1e-3 | 37, 38, 20 |

Case 7 is the one that proves the feature is usable on a farm; cases 4 and 5
are the ones that would otherwise cost the hours.

## 7. Open questions, with the default taken

| Question | Default |
|---|---|
| Linked `wet_rate` / `dry_time` averaged over the pixels seen, or read on the host as constants? | Averaged in the kernel (three more atomics per write); the constant case is not special-cased in V1 |
| First frame of a sequence: `wet_prev` = 0 or the current contact? | 0; the output already blends the current contact in |
| Unseen objects: decay anyway, or freeze? | Freeze (`count == 0` keeps `wet_prev`): a decay without a contact measurement would dry an object that may be under water |
| One slot per object, or per object × material? | Per object; a second material on the same object shares the value |
| State file format | Flat binary, no new dependency |
