# Documentation map

Start here. Each file answers one question; none repeats another.

| Question | File |
|---|---|
| What is this project for, and for whom? | [GOALS.md](GOALS.md) |
| How is it built, and where does each piece live? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| What works today, what is partial, what is missing? | [PROGRESS.md](PROGRESS.md) |
| What is known to be wrong, with the line that is wrong? | [KNOWN_ISSUES.md](KNOWN_ISSUES.md) |
| In what order do we fix it, and how do we know it is fixed? | [PLAN.md](PLAN.md) |
| How do we test, and what do the benches really prove? | [TESTING.md](TESTING.md) |
| Rules of the repository: language, patches, commits, builds | [CONVENTIONS.md](CONVENTIONS.md) |

## Reference and history

These predate the map above and stay as written. They are in French.

| File | What it holds |
|---|---|
| [STATUS.md](STATUS.md) | The chronological journal, phase 0 to 33: what was tried, measured and decided, in order. It is the record, not the current state - read PROGRESS.md for that. |
| [MATERIALX_COVERAGE.md](MATERIALX_COVERAGE.md) | The MaterialX coverage count and what it leaves out. Its headline number counts prefix matches, not correct translations - see TESTING.md. |
| [MATERIALX_PLAN.md](MATERIALX_PLAN.md) | The node-by-node checklist of the MaterialX work, with verification notes. |
| [STANDARD_SURFACE_AUDIT.md](STANDARD_SURFACE_AUDIT.md) | `standard_surface` input by input, measured at render time. |
| [CYCLES_53.md](CYCLES_53.md) | Running Cycles 5.2 and 5.3 side by side. |
| [CYCLES_VOPS.md](CYCLES_VOPS.md) | Inventory of the generated VOP library. |
| [ENVIRONMENT.md](ENVIRONMENT.md) | The build machine: toolchain and library versions. |

The patch series has its own notes in [`../patches/README.md`](../patches/README.md), one entry per patch, with the bug each one fixes. The test tree is described in [`../tests/README.md`](../tests/README.md): which folder holds scenes, which holds references, and which a script writes into.

Images of the journal live in `images/`; nothing rendered by a test goes in `docs/`.

## Keeping this in step

- A feature lands: update PROGRESS.md the same day, and close its line in PLAN.md.
- A bug is found: it goes in KNOWN_ISSUES.md with the file and line, before any fix.
- A decision is taken (an approach rejected, a trade-off accepted): STATUS.md, dated, as before.
- A number quoted in README.md must be reproducible by a command named in TESTING.md.
