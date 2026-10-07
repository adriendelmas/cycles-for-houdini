"""The one node count the documentation quotes.

Three numbers come up and used to disagree - 163, 161, 97 - because each was
read from a different place. They are all derived here from the Sdr registry
the built delegate publishes, and from the same rules the VOP generator and
the bench apply:

    hython tools/count_nodes.py

Set CYCLES_INSTALL_DIR to pick the engine (`install` for 5.2, `install-53`).
"""

import os
import sys

from pxr import Sdr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

PREFIX = "cycles_"
# Terminals and outputs are not shaders a bench can probe; bench_export.py
# skips the same three.
NOT_PROBED = {"cycles_material", "cycles_output", "cycles_aov_output"}


def main():
    ids = sorted(str(i) for i in Sdr.Registry().GetShaderNodeIdentifiers()
                 if str(i).startswith(PREFIX))
    if not ids:
        sys.exit("no cycles_* node in the Sdr registry: is the package loaded?")
    converts = [i for i in ids if i.startswith(PREFIX + "convert_")]
    exposed = [i for i in ids if i not in converts]
    probed = [i for i in exposed if i not in NOT_PROBED]

    print("published to Sdr      : %d" % len(ids))
    print("  convert_* (hidden)  : %d" % len(converts))
    print("  exposed as VOPs     : %d" % len(exposed))
    print("  probed by the bench : %d  (exposed minus %s)" % (len(probed), ", ".join(sorted(NOT_PROBED))))


if __name__ == "__main__":
    main()
