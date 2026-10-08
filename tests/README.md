# Tests

What each folder holds, and the command that uses it. Rendered output never
sits next to the scenes or the references: every folder that a script writes
into is listed in `.gitignore` and named `output/`, `scratch/` or `hair/`.

| Folder | Holds | Written by |
|---|---|---|
| `nodes/5.3/`, `nodes/5.2/` | One USD scene per native Cycles VOP (`cycles_*.usda`), `_baseline.usda`, and `references/` - the committed images | `tools/bench_export.py` writes the scenes once; `tools/bench_render.py` renders into `scenes/` and `output/` (ignored); `tools/bench_diff.py` compares `output/` to `references/` and moves a reference only on `--accept` |
| `materialx/scenes/` | Hand-written MaterialX verification scenes: the `v_*` series (one node or one input each), `phase4b_mtlx.usda` (the shared base scene of the node bench), `coverage.usda`, the builder exports | Read by `bench_render.py` (base scene) and by hand with husk |
| `materialx/standard_surface/` | The `au_*.usda` audit scenes, one per `standard_surface` input (see `docs/STANDARD_SURFACE_AUDIT.md`); their `.exr` references are local and ignored | `scratchpad/audit_surface.py` |
| `materialx/output/` (ignored) | `bench_mtlx.py` scenes and images, `mtlx_inputs.py`'s stage and log under `inputs/` | `tools/bench_mtlx.py`, `tools/mtlx_inputs.py` |
| `materialx/hair/` (ignored) | The four pairs of the hair bench | `tools/bench_hair.py` |
| `scenes/` | Feature and regression scenes: the phase scenes of the journal (`phase3.usda`, `phase6_aov.usda`, `phase12_velocity.usda`...), crash reproductions (`repro_mtlx_crash.usda`), lights, AOVs, settings, normals, COP textures | By hand with husk; the commands are in `docs/STATUS.md` next to each phase |
| `scenes/displacement/` | The dispersion and displacement comparison, with its images | - |
| `houdini/` | Scenes to check by hand in a live Houdini, what husk cannot show: `motion_toggle.hip` (motion blur turned off and back on, K-34), `purpose_toggle.hip` (display purposes toggled in the viewport, K-28). Each `.hip` sublayers its `.usda` and carries a sticky note with the steps | Open in Houdini, viewport on Cycles |
| `curves/output/`, `motion/output/`, `instances/output/`, `implicit/output/`, `settings/output/`, `aovs/output/` (ignored) | What the phase 5 and 6 benches write | `tools/bench_curves.py`, `bench_motion.py`, `bench_instances.py`, `bench_implicit.py`, `bench_settings.py`, `bench_aovs.py` |
| `notes/` | Text dumps kept from the early inventories (node and socket lists, case lists) | - |
| `scratch/` (ignored) | Anything rendered by hand while investigating | - |

The reference images are rendered at 120×90; comparing at another size fails
every scene at once. `docs/TESTING.md` says what each bench proves and how to
run them outside Houdini.
