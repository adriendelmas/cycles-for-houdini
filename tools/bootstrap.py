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

# One cubin per generation: Maxwell sm_50/52, Pascal sm_60/61, Volta sm_70,
# Turing sm_75, Ampere sm_86, Ada sm_89, Blackwell sm_120. At run time Cycles
# takes the cubin of the same major version with the highest minor that does
# not exceed the card's (sm_89 runs the sm_86 one), and otherwise JIT-compiles
# the compute_75 PTX through the driver, which covers sm_80, sm_90, sm_100 and
# later. sm_100/sm_120 need CUDA 12.8+; Cycles skips an architecture its
# toolkit cannot build.
CUDA_ARCH = "sm_50;sm_52;sm_60;sm_61;sm_70;sm_75;sm_86;sm_89;sm_120;compute_75"


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
    # Blender's precompiled libraries, as a submodule + git-lfs. Blender's
    # .gitmodules declares them `update = none` so that a plain checkout does
    # not pull gigabytes: asked for explicitly, or `git submodule update`
    # prints "Skipping submodule" and the configure step fails for want of
    # every dependency (seen on the clean-clone check of 2026-10-08).
    run(["git", "-c", "submodule.lib/windows_x64.update=checkout",
         "submodule", "update", "--init", "--progress", "lib/windows_x64"], cwd=src)


def apply_patches(src, version):
    series = os.path.join(ROOT, "patches", version)
    patches = sorted(
        os.path.join(series, f) for f in os.listdir(series) if f.endswith(".patch")
    )
    if not patches:
        sys.exit("no patch in " + series)
    print("%d patches to apply" % len(patches))
    # `git am` commits, so it needs an identity; a machine that has never
    # committed has none, and the run stopped at the first patch.
    identity = []
    if not subprocess.run(["git", "config", "user.email"], cwd=src,
                          capture_output=True).stdout.strip():
        identity = ["-c", "user.name=hdCycles bootstrap",
                    "-c", "user.email=bootstrap@hdcycles.local"]
    run(["git"] + identity + ["am"] + patches, cwd=src)


def configure(src, cfg, houdini, optix, arch, osl, split=True):
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
        # Cycles turns nvcc's split compile on only for one or two
        # architectures, to bound memory when several kernels build at once.
        # They build one after another here, and the flag cuts a kernel from
        # about 7.5 min to 1.5 min on a 128-thread machine. Always passed, empty
        # when off, so that a value cached by an earlier run cannot linger and
        # double up with the one Cycles adds itself.
        many = len([a for a in arch.split(";") if a]) > 2
        args += ["-DCUDA_NVCC_FLAGS=" + ("--split-compile=0" if split and many else "")]
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
    p.add_argument("--cuda-arch", default=CUDA_ARCH,
                   help="CUDA kernel architectures, ';'-separated (default: every NVIDIA "
                        "generation since Maxwell, plus a PTX fallback); "
                        "pass --cuda-arch= to build none")
    p.add_argument("--no-osl", action="store_true", help="build without OSL")
    p.add_argument("--no-split-compile", action="store_true",
                   help="do not pass nvcc --split-compile=0 when building more than two "
                        "CUDA architectures (slower, but lighter on memory)")
    p.add_argument("--jobs", type=int, default=os.cpu_count() or 1,
                   help="parallel jobs (default: the number of logical processors "
                        "of this machine)")
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
    build = configure(src, cfg, args.houdini, args.optix, args.cuda_arch, not args.no_osl,
                      not args.no_split_compile)
    if args.skip_build:
        return

    print("== build and install ==")
    cmd = ["cmake", "--build", build, "--config", "Release", "--target", "install"]
    if args.jobs > 0:
        cmd += ["--parallel", str(args.jobs)]
    run(cmd)

    print("\nDone. Next: generate the VOP library, then assemble the folder for Houdini:\n"
          "    hython tools/build_cycles_vops.py\n"
          "    python tools/make_dist.py --version %s" % args.version)


if __name__ == "__main__":
    main()
