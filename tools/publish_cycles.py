"""Publishes the Cycles branch and keeps the patch series in this repository equal to it.

The Cycles changes have one source: the branch `houdini` of the fork on projects.blender.org.
`patches/5.3/` is that branch exported, and `patches/5.3/BRANCH` names the commit it was exported from.

    python tools/publish_cycles.py --check     are the fork, the local branch and the patches the same?
    python tools/publish_cycles.py             push the branch to the fork, regenerate the patches, commit them here
    python tools/publish_cycles.py --push      the same, then push this repository as well

It refuses to run when the fork holds commits the local branch does not have (fetch and merge first:
the published branch is never rewritten), or when a commit message credits a tool as co-author."""
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLONE = os.path.join(ROOT, "external", "cycles-pr")
REMOTE, BRANCH, BASE = "fork", "houdini", "v5.3.0"
PATCHES = os.path.join(ROOT, "patches", "5.3")
STAMP = os.path.join(PATCHES, "BRANCH")


def git(where, *args, check=True):
    done = subprocess.run(["git", "-C", where] + list(args), capture_output=True, text=True, encoding="utf-8")
    if check and done.returncode:
        sys.exit("git %s failed:\n%s" % (" ".join(args), done.stderr.strip()))
    return done.stdout.strip()


def state():
    git(CLONE, "fetch", "-q", REMOTE, BRANCH)
    local = git(CLONE, "rev-parse", BRANCH)
    remote = git(CLONE, "rev-parse", "%s/%s" % (REMOTE, BRANCH))
    stamp = open(STAMP).read().split()[0] if os.path.exists(STAMP) else ""
    return local, remote, stamp


def main():
    local, remote, stamp = state()
    if "--check" in sys.argv:
        print("local branch  %s\nfork          %s\npatches from  %s" % (local, remote, stamp or "(unknown)"))
        sys.exit(0 if local == remote == stamp else "NOT in sync")

    if subprocess.run(["git", "-C", CLONE, "merge-base", "--is-ancestor", remote, local]).returncode:
        sys.exit("the fork has commits the local branch lacks: fetch and merge them first, never force")
    messages = git(CLONE, "log", "--format=%B", "%s..%s" % (BASE, BRANCH)).lower()
    if "co-authored-by: claude" in messages or "noreply@anthropic.com" in messages:
        sys.exit("a commit message credits a tool as co-author: only humans are authors (Blender's AI policy)")

    git(CLONE, "push", REMOTE, BRANCH)
    for old in glob.glob(os.path.join(PATCHES, "*.patch")):
        os.remove(old)
    git(CLONE, "format-patch", "--no-signature", "-q", "%s..%s" % (BASE, BRANCH), "-o", PATCHES)
    count = len(glob.glob(os.path.join(PATCHES, "*.patch")))
    with open(STAMP, "w", newline="\n") as out:
        out.write("%s\n%s/%s of https://projects.blender.org/starforge/cycles, %d patches on %s\n"
                  % (local, REMOTE, BRANCH, count, BASE))
    git(ROOT, "add", "-A", "--", "patches/5.3")
    if git(ROOT, "status", "--porcelain", "--", "patches/5.3"):
        git(ROOT, "commit", "-q", "-m", "patches: series exported from %s (%d patches)" % (local[:8], count), "--", "patches/5.3")
    if "--push" in sys.argv:
        git(ROOT, "push")
    print("published %s, %d patches" % (local[:8], count))


if __name__ == "__main__":
    main()
