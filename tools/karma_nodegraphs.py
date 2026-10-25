"""Prints a Karma node's nodegraph as a readable node list.

Karma's own MaterialX nodes (`kma_*`) are defined in
`$HFS/houdini/karmaNodeGraphs.json`: a compact graph per node - a list of
[nodedef, name, connections, values] with inputs by index. This decodes one
or more of them with the inputs named, which is how the delegate's own
nodegraphs for the Karma Hextiled Triplanar were transcribed (K-106).

    python tools/karma_nodegraphs.py kma_hextiled_triplanar_color [more...]
    python tools/karma_nodegraphs.py --list

Nodes a Karma graph uses that are not in the MaterialX library (other
`kma_*`, GLSL-only ones) are listed after the graph with their inputs: those
need a nodegraph or a table entry of their own in the delegate.
"""

import glob
import io
import json
import os
import re
import sys

HFS = os.environ.get("HFS", "E:/Side Effects Software/Houdini22.0.368")
HOUDINI = HFS + "/houdini"


def library_inputs():
    """Input and output names of every ND_ nodedef in Houdini's library."""
    nd = {}
    for f in glob.glob(HOUDINI + "/materialx/libraries/**/*.mtlx", recursive=True):
        s = io.open(f, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r'<nodedef name="(ND_[^"]+)"(.*?)</nodedef>', s, re.S):
            ins = re.findall(r'<input name="([^"]+)"', m.group(2))
            outs = re.findall(r'<output name="([^"]+)"', m.group(2))
            nd[m.group(1)] = (ins, outs or ["out"])
    return nd


def main():
    data = json.load(io.open(HOUDINI + "/karmaNodeGraphs.json", encoding="utf-8"))
    defs = {e[0]: e for e in data[0]}
    graphs = {e[0]: e for e in data[1]}
    if "--list" in sys.argv or len(sys.argv) < 2:
        print("\n".join(sorted(graphs)))
        return
    nd = library_inputs()

    def names(tid):
        if tid in nd:
            return nd[tid]
        if tid in defs:
            return ([i[0] for i in defs[tid][1]], [o[0] for o in defs[tid][2]])
        return ([], ["out"])

    for g in sys.argv[1:]:
        if g not in graphs:
            print("no graph named", g)
            continue
        name, ngname, nodes, *rest = graphs[g]
        iface = [i[0] for i in defs[g][1]]
        print("==", name, ngname, "outputs:", json.dumps(rest)[:200])
        print("   inputs:", ", ".join("%s %s=%s" % (i[0], i[1], i[2]) for i in defs[g][1]))
        for idx, (tid, nname, conns, vals) in enumerate(nodes):
            ins, outs = names(tid)
            parts = []
            for ii, src, so in conns:
                iname = ins[ii] if ii < len(ins) else "#%d" % ii
                if src == -1:
                    parts.append("%s <- IFACE %s" % (iname, iface[so] if so < len(iface) else "#%d" % so))
                else:
                    souts = names(nodes[src][0])[1]
                    parts.append("%s <- %s.%s" % (iname, nodes[src][1], souts[so] if so < len(souts) else "#%d" % so))
            for ii, v in vals:
                parts.append("%s = %s" % (ins[ii] if ii < len(ins) else "#%d" % ii, v))
            print("%3d %-28s %-32s %s" % (idx, nname, tid, "; ".join(parts)))
        for t in sorted({n[0] for n in nodes if n[0] not in nd}):
            if t in defs:
                print("   not in the library:", t, [(i[0], i[1], i[2]) for i in defs[t][1]], [o[0] for o in defs[t][2]])
            else:
                print("   not in the library, no definition:", t)


if __name__ == "__main__":
    main()
