"""Clone Cycles au commit epingle, applique nos correctifs, compile, installe.

Cycles n'est pas recopie dans ce depot : nos modifications y vivent sous forme
de serie de correctifs, dans patches/. Cet outil refait le chemin complet, du
clone a l'installation Houdini prete a poser dans un package.

    python tools/bootstrap.py --version 5.3

Le clone est un depot git a part entiere, sur une branche a nous : une fois
pose, on y travaille normalement, et `git format-patch` regenere la serie.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Chaque version vise un commit precis de l'amont. Une serie de correctifs ne
# s'applique proprement que sur la base pour laquelle elle a ete exportee.
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
    """Clone treeless puis detache sur le commit epingle.

    Treeless plutot que shallow : l'historique reste navigable et `git am` a de
    quoi travailler, sans rapatrier chaque revision de chaque fichier.
    """
    run(["git", "clone", "--filter=tree:0", UPSTREAM, src])
    run(["git", "checkout", "-b", cfg["branch"], cfg["commit"]], cwd=src)
    # Bibliotheques precompilees de Blender, en submodule + git-lfs.
    run(["git", "submodule", "update", "--init", "lib/windows_x64"], cwd=src)


def apply_patches(src, version):
    series = os.path.join(ROOT, "patches", version)
    patches = sorted(
        os.path.join(series, f) for f in os.listdir(series) if f.endswith(".patch")
    )
    if not patches:
        sys.exit("aucun correctif dans " + series)
    print("%d correctifs a appliquer" % len(patches))
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
                   help="racine d'installation Houdini (defaut : $HFS)")
    p.add_argument("--optix", default=os.environ.get("OPTIX_ROOT_DIR", ""),
                   help="racine du SDK OptiX ; vide pour compiler sans OptiX")
    p.add_argument("--cuda-arch", default="sm_86",
                   help="architecture des noyaux CUDA, p.ex. sm_86 ; vide pour ne pas en compiler")
    p.add_argument("--no-osl", action="store_true", help="compiler sans OSL")
    p.add_argument("--jobs", type=int, default=0, help="taches paralleles (defaut : auto)")
    p.add_argument("--skip-build", action="store_true", help="s'arreter apres la configuration")
    args = p.parse_args()

    if not args.houdini:
        sys.exit("indiquez --houdini, ou definissez HFS. Cette version vise Houdini 22.0.368.")
    if not os.path.isdir(args.houdini):
        sys.exit("introuvable : " + args.houdini)
    for tool in ("git", "cmake"):
        if shutil.which(tool) is None:
            sys.exit(tool + " est absent du PATH")

    cfg = VERSIONS[args.version]
    src = os.path.join(ROOT, "external", cfg["dir"])

    if os.path.exists(src):
        print("%s existe deja : ni clone ni correctifs, on passe a la compilation." % src)
    else:
        print("== clone de Cycles au commit %s ==" % cfg["commit"][:8])
        clone(src, cfg)
        print("== application de la serie %s ==" % args.version)
        apply_patches(src, args.version)

    print("== configuration ==")
    build = configure(src, cfg, args.houdini, args.optix, args.cuda_arch, not args.no_osl)
    if args.skip_build:
        return

    print("== compilation et installation ==")
    cmd = ["cmake", "--build", build, "--config", "Release", "--target", "install"]
    if args.jobs:
        cmd += ["--parallel", str(args.jobs)]
    run(cmd)

    pkg = os.path.join(ROOT, cfg["install"], "houdini", "packages", "cycles.json")
    print("\nTermine. Copiez le package dans vos paquets Houdini :\n    %s" % pkg)


if __name__ == "__main__":
    main()
