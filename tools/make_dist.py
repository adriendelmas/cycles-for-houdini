"""Assembles the folder that is handed to users, from an install tree.

    python tools/make_dist.py --version 5.3 [--zip]

The result, in dist/CyclesForHoudini-<version>/:

    cycles.json              the Houdini package
    CyclesForHoudini/        the plugin (houdini/, licenses/, LICENSE, NOTICE)

Both are dropped together into a Houdini `packages` folder (for example
Documents/houdini22.0/packages). The package finds the plugin through
$HOUDINI_PACKAGE_PATH, so nothing in either holds a path of this machine.

The package file is taken from the template in the Cycles clone rather than
from the install tree, which may have been built before the template went
relative. The tool then scans what it copies and refuses to finish if a text
file still names a drive letter.
"""

import argparse
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

VERSIONS = {
    "5.3": {"dir": "cycles-53", "install": "install-53"},
}

PLUGIN_DIR = "CyclesForHoudini"
SKIP_DIRS = {"backup", "__pycache__", "packages"}
TEXT_EXT = {".json", ".py", ".ds", ".xml", ".shelf", ".txt", ".cmake"}
ABSOLUTE = re.compile(rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/][A-Za-z0-9_$ .-]")


def copy_tree(src, dst):
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(base, src)
        target = os.path.normpath(os.path.join(dst, rel))
        os.makedirs(target, exist_ok=True)
        for name in files:
            if name.endswith((".pyc", ".bak")) or ".old-" in name:
                continue
            shutil.copy2(os.path.join(base, name), os.path.join(target, name))


def scan(dist):
    bad = []
    for base, _, files in os.walk(dist):
        for name in files:
            if os.path.splitext(name)[1].lower() not in TEXT_EXT:
                continue
            path = os.path.join(base, name)
            with open(path, "rb") as f:
                if ABSOLUTE.search(f.read()):
                    bad.append(path)
    return bad


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", choices=sorted(VERSIONS), default="5.3")
    p.add_argument("--zip", action="store_true", help="also write dist/<name>.zip")
    args = p.parse_args()

    cfg = VERSIONS[args.version]
    install = os.path.join(ROOT, cfg["install"])
    houdini = os.path.join(install, "houdini")
    template = os.path.join(ROOT, "external", cfg["dir"], "src", "hydra",
                            "resources", "cycles.json.in")
    for path in (houdini, template):
        if not os.path.exists(path):
            sys.exit("not found: " + path)

    with open(template, "rb") as f:
        package = f.read()
    if b"@" in package or ABSOLUTE.search(package):
        sys.exit("the package template still holds a build path: " + template)

    name = "CyclesForHoudini-" + args.version
    dist = os.path.join(ROOT, "dist", name)
    if os.path.exists(dist):
        shutil.rmtree(dist)
    plugin = os.path.join(dist, PLUGIN_DIR)

    copy_tree(houdini, os.path.join(plugin, "houdini"))
    licence = os.path.join(install, "license")
    if os.path.isdir(licence):
        copy_tree(licence, os.path.join(plugin, "licenses"))
    for f in ("LICENSE", "NOTICE"):
        shutil.copy2(os.path.join(ROOT, f), os.path.join(plugin, f))
    with open(os.path.join(dist, "cycles.json"), "wb") as f:
        f.write(package)

    bad = scan(dist)
    if bad:
        print("text files that still name a drive letter:")
        for b in bad:
            print("  " + b)
        sys.exit(1)

    print("Done: " + dist)
    if args.zip:
        archive = shutil.make_archive(dist, "zip", root_dir=dist)
        print("Zip:  " + archive)


if __name__ == "__main__":
    main()
