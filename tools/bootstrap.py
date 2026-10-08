"""Clones Cycles at the pinned commit, applies our patches, builds, installs.

Cycles is not copied into this repository: our changes live there as a patch
series, in patches/. This tool redoes the whole path, from the clone to the
Houdini install ready to be dropped into a package.

    python tools/bootstrap.py --version 5.3

The clone is a full git repository, on a branch of our own: once in place, you
work in it normally, and `git format-patch` regenerates the series.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Each version targets a specific upstream commit. A patch series only applies
# cleanly on the base it was exported against.
VERSIONS = {
    "5.2": {
        "dir": "cycles",
        "install": "install",
        "branch": "houdini-fixes",
        "commit": "3b97e190c5ff1a2ed2160d879ad5bf95bea7b8ba",
    },
    "5.3": {
        "dir": "cycles-53",
        "install": "install-53",
        "branch": "houdini-fixes-53",
        "commit": "8424ed531b0d0b56667418d4a8d09452957b7904",
    },
}

UPSTREAM = "https://projects.blender.org/blender/cycles.git"


def run(cmd, cwd=None, env=None):
    print("  $ " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def clone(src, cfg):
    """Treeless clone, then checkout of the pinned commit.

    Treeless rather than shallow: the history stays browsable and `git am` has
    enough to work with, without fetching every revision of every file.
    """
    run(["git", "clone", "--filter=tree:0", UPSTREAM, src])
    run(["git", "checkout", "-b", cfg["branch"], cfg["commit"]], cwd=src)
    # Blender's precompiled libraries, as a submodule + git-lfs.
    run(["git", "submodule", "update", "--init", "lib/windows_x64"], cwd=src)


def apply_patches(src, version):
    series = os.path.join(ROOT, "patches", version)
    patches = sorted(
        os.path.join(series, f) for f in os.listdir(series) if f.endswith(".patch")
    )
    if not patches:
        sys.exit("no patch in " + series)
    print("%d patches to apply" % len(patches))
    run(["git", "am"] + patches, cwd=src)


def configure(src, cfg, houdini, optix, arch, osl):
    build = os.path.join(src, "build")
    args = [
        "cmake",
        "-S", src,
        "-B", build,
        "-DCMAKE_INSTALL_PREFIX=" + os.path.join(ROOT, cfg["install"]).replace("\\", "/"),
        "-DHOUDINI_ROOT=" + houdini.replace("\\", "/"),
        "-DWITH_CYCLES_HYDRA_RENDER_DELEGATE=ON",
        "-DWITH_CYCLES_OSL=" + ("ON" if osl else "OFF"),
    ]
    if arch:
        args += ["-DWITH_CYCLES_CUDA_BINARIES=ON", "-DCYCLES_CUDA_BINARIES_ARCH=" + arch]
    else:
        args += ["-DWITH_CYCLES_CUDA_BINARIES=OFF"]
    if optix:
        args += ["-DWITH_CYCLES_DEVICE_OPTIX=ON", "-DOPTIX_ROOT_DIR=" + optix.replace("\\", "/")]
    else:
        args += ["-DWITH_CYCLES_DEVICE_OPTIX=OFF"]
    run(args)
    return build


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", choices=sorted(VERSIONS), default="5.3")
    p.add_argument("--houdini", default=os.environ.get("HFS", ""),
                   help="Houdini install root (default: $HFS)")
    p.add_argument("--optix", default=os.environ.get("OPTIX_ROOT_DIR", ""),
                   help="OptiX SDK root; empty to build without OptiX")
    p.add_argument("--cuda-arch", default="sm_86",
                   help="CUDA kernel architecture, e.g. sm_86; empty to build none")
    p.add_argument("--no-osl", action="store_true", help="build without OSL")
    p.add_argument("--jobs", type=int, default=0, help="parallel jobs (default: auto)")
    p.add_argument("--skip-build", action="store_true", help="stop after configuration")
    args = p.parse_args()

    if not args.houdini:
        sys.exit("pass --houdini, or set HFS. This version targets Houdini 22.0.368.")
    if not os.path.isdir(args.houdini):
        sys.exit("not found: " + args.houdini)
    for tool in ("git", "cmake"):
        if shutil.which(tool) is None:
            sys.exit(tool + " is missing from PATH")

    cfg = VERSIONS[args.version]
    src = os.path.join(ROOT, "external", cfg["dir"])

    if os.path.exists(src):
        print("%s already exists: no clone, no patches, going straight to the build." % src)
    else:
        print("== cloning Cycles at commit %s ==" % cfg["commit"][:8])
        clone(src, cfg)
        print("== applying series %s ==" % args.version)
        apply_patches(src, args.version)

    print("== configuration ==")
    build = configure(src, cfg, args.houdini, args.optix, args.cuda_arch, not args.no_osl)
    if args.skip_build:
        return

    print("== build and install ==")
    cmd = ["cmake", "--build", build, "--config", "Release", "--target", "install"]
    if args.jobs:
        cmd += ["--parallel", str(args.jobs)]
    run(cmd)

    pkg = os.path.join(ROOT, cfg["install"], "houdini", "packages", "cycles.json")
    print("\nDone. Copy the package into your Houdini packages:\n    %s" % pkg)


if __name__ == "__main__":
    main()
