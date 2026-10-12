# Conventions

## Language

- **Code, comments, log messages, HDA help, parameter labels: English.** The
  repository is public and the patches are meant to go upstream. Existing
  French comments are translated as the file they live in is touched
  (K-53); no new French goes into code from 2026-10-07.
- **Commit messages: French**, lower-case, no trailing period, one subject
  per commit - as the history reads today.
- **Documentation: English for the files in the map** (`docs/README.md`);
  the historical journal `STATUS.md` and the older reference docs stay
  French.
- Chat with the author is in French.

## The patch series is the source of truth

- `external/cycles-53` is a git worktree on `houdini-fixes-53`, based on
  upstream `8424ed53`. It is **not** tracked by this repository.
- Every change to Cycles or the delegate is a commit on that branch, one
  subject per commit, with a message that states the bug and how it was
  measured. Then:

  ```bash
  cd external/cycles-53 && git format-patch --no-signature -o ../../patches/5.3 8424ed53..HEAD
  ```

  and the regenerated `patches/5.3/*.patch` are committed here together with
  the docs they affect.
- `patches/README.md` gets one table row per patch; longer notes go below the
  table only when the patch message is not enough.
- Never edit a `.patch` file by hand.
- Prefer the smallest change that fixes the stated bug. Anything that would
  need a permanent divergence from upstream is discussed in STATUS.md before
  it is written.

## One Cycles version, and what is handed to users

- `external/cycles-53` (5.3, `houdini-fixes-53`) is the only maintained engine.
  A Cycles 5.2 build existed; it was incomplete (38 patches against 142) and
  was retired on 2026-10-12 (K-103). Its patches and bench data are
  git-ignored and stay on the author's machine; do not bring them back, and do
  not port anything to it. To regenerate one patch without rewriting the
  others: `git format-patch --no-signature -1 --start-number N -o
  ../../patches/5.3` from `external/cycles-53`.
- `tools/bootstrap.py` and `tools/make_dist.py` have a `VERSIONS` table with
  one entry. A second Cycles version would be a second entry and its own
  `patches/<v>/`, `install-<v>` and `tests/nodes/<v>/`.
- Generated files are never edited: `build/**/cycles.json`,
  `install*/houdini/packages/cycles.json`, anything under `install*/`. The source
  of the package is `src/hydra/resources/cycles.json.in` in the clone, shipped as
  a patch; `make_dist.py` reads that template, not the generated copy.
- What users receive is `dist/CyclesForHoudini-<version>/` (git-ignored), built
  by `python tools/make_dist.py --version 5.3 [--zip]`: `cycles.json` plus a
  `CyclesForHoudini/` folder, both dropped into a `packages` folder. Nothing in
  it may name a path of the machine that built it; the tool scans text files
  and refuses otherwise. Backups (`otls/backup`), `.pyc` files and
  `hdCycles.dll.old-*` stay out.
- A user-facing claim about a GPU (which vendor, which generation) is written
  only with the hardware that ran it named, as in K-98: compiled is not run.

## Building and verifying

- `cmake --build ... --target install` with Houdini open fails on the locked
  DLL and leaves the old one in place. Close Houdini, or test the new DLL
  from a temporary plugin tree (TESTING.md).
- One build at a time.
- After a build: DLL timestamp, then `grep -c -a` for a string from the new
  code.
- After a change to `material.cpp`: `bench_mtlx.py` and `bench_hair.py`.
  After a change to anything else in the delegate: `bench_render.py` and
  `bench_diff.py`. The numbers go in the commit message.

## Testing discipline

- A bug gets a failing test before its fix, when a test can express it.
- Expected values come from the specification (MaterialX source, Cycles
  kernel, Karma on the same USD), never from the implementation under test.
- Reference images move only through an explicit, reviewed commit.
- A claim in README.md is a number produced by a command named in TESTING.md.

## Logging

- Anything the user must see goes through Cycles' logger (`LOG_WARNING`,
  `LOG_INFO`), not `TF_WARN` or `TF_RUNTIME_ERROR` - husk swallows the latter.
- A dropped connection, an unknown node, an ignored parameter, an
  approximation: one line each, naming the prim path.
- Per-frame lines are gated (the render pass logs only above 50 ms).

## Documentation discipline

- `PROGRESS.md` is updated in the same commit as the feature.
- `KNOWN_ISSUES.md` entries carry a file and line and a verification level
  (confirmed / probable / measured).
- `STATUS.md` is append-only and dated: what was tried, what was measured,
  what was decided and why. Mistakes stay in it - they are the record that
  stops them being repeated.
- Numbers in docs are reproducible or marked as estimates.

## Working with the author

- Chain tasks: when one is done and checked, go on to the next in the plan
  with a short note; ask questions along the way with a stated default.
- Never save or overwrite his `.hip` scenes; never delete his files - set
  them aside and tell him.
- Agents only for isolating noise, for fully independent repetitive work, or
  for plain writing on a light model; code and fixes stay in the main thread.
