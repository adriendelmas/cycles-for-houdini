"""English headers for the patch series.

The Cycles worktree's history was written in French for a long time, and
`git format-patch` copies each commit message into its patch. Rather than
rewrite that history, this replaces the subject and body of every patch whose
commit is listed in `patch_messages.json` (short hash to English message) and
renames the file after the new subject. Run it after regenerating the series:

    cd external/cycles-53 && git format-patch --no-signature -o ../../patches/5.3 8424ed53..HEAD
    python tools/patch_messages.py

Patches of commits not in the table are left as they are.
"""

import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(ROOT, "tools", "patch_messages.json")
SERIES = os.path.join(ROOT, "patches", "5.3")


def slug(subject):
    """What format-patch makes of a subject: non-alphanumerics to dashes, 52 chars."""
    text = re.sub(r"[^A-Za-z0-9]+", "-", subject).strip("-")
    return text[:52].rstrip("-")


def rewrite(path, message):
    data = io.open(path, "rb").read().decode("utf-8")
    subject_at = data.index("\nSubject: ") + 1
    body_end = data.index("\n---\n", subject_at) + 1
    header = data[:subject_at]
    tag = re.match(r"Subject: (\[PATCH[^\]]*\] )", data[subject_at:]).group(1)
    lines = message.rstrip("\n").split("\n")
    subject, body = lines[0], "\n".join(lines[1:])
    # format-patch wraps a long subject onto a continuation line.
    first = "Subject: " + tag + subject
    if len(first) > 78:
        cut = first.rfind(" ", 0, 78)
        first = first[:cut] + "\n" + first[cut:]
    new = header + first + "\n" + body + "\n" + data[body_end:]
    number = os.path.basename(path)[:4]
    target = os.path.join(os.path.dirname(path), "%s-%s.patch" % (number, slug(subject)))
    io.open(target, "wb").write(new.encode("utf-8"))
    if target != path:
        os.remove(path)
    return target


def main():
    table = json.load(io.open(TABLE, encoding="utf-8"))
    done = 0
    for path in sorted(glob.glob(os.path.join(SERIES, "*.patch"))):
        head = io.open(path, "rb").read(80).decode("utf-8", "replace")
        commit = head.split()[1] if head.startswith("From ") else ""
        for short, message in table.items():
            if commit.startswith(short):
                rewrite(path, message)
                done += 1
                break
    print("%d patch headers in English" % done)
    return 0


if __name__ == "__main__":
    sys.exit(main())
