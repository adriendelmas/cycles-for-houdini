"""Which MaterialX nodedefs the delegate renders, by the delegate's own rules.

Shared by `mtlx_coverage.py` and `mtlx_inputs.py`, so that both count the
same thing. A nodedef is translated when:

- its name starts with a prefix of the mapping table in `material.cpp` (the
  longest prefix wins there; here any match counts), or is one of the four
  arithmetic families the lookup picks apart by type suffix;
- or the delegate expands it (`mtlx_expand.cpp`): `extract` and `swizzle` are
  rewritten by hand, and any nodedef the library implements as a nodegraph is
  replaced by that nodegraph's nodes - translated if every one of them is.
"""

import os
import re

import MaterialX as mx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "external", "cycles-53", "src", "hydra", "material.cpp")

INLINE = ("ND_add_", "ND_subtract_", "ND_multiply_", "ND_divide_")
PREFIX_RE = re.compile(r'\{"(ND_[A-Za-z0-9_]*)"')
SEPARABLE = {"color3", "color4", "vector2", "vector3", "vector4"}


def prefixes():
    text = open(SOURCE, encoding="utf-8", errors="replace").read()
    return sorted(set(PREFIX_RE.findall(text)), key=len, reverse=True)


def load_library():
    """The library Houdini ships, as the delegate reads it."""
    doc = mx.createDocument()
    mx.loadLibraries(["libraries"], mx.getDefaultDataSearchPath(), doc)
    return doc


class Resolver:
    """resolves(name) -> True when the delegate renders that nodedef;
    how(name) -> 'table', 'expanded', 'rewritten' or ''."""

    def __init__(self, doc, known=None):
        self.doc = doc
        self.known = known if known is not None else prefixes()
        self._cache = {}

    def in_table(self, name):
        return name.startswith(INLINE) or any(name.startswith(p) for p in self.known)

    def how(self, name):
        if name in self._cache:
            return self._cache[name]
        self._cache[name] = ""  # guards against a nodegraph that refers to itself
        result = ""
        if self.in_table(name):
            result = "table"
        else:
            nd = self.doc.getNodeDef(name)
            if nd is not None:
                category = nd.getNodeString()
                if category == "extract":
                    in_ = nd.getActiveInput("in")
                    result = "rewritten" if in_ is not None and in_.getType() in SEPARABLE else ""
                elif category == "swizzle":
                    result = "rewritten"
                else:
                    for impl in self.doc.getMatchingImplementations(name):
                        if not impl.isA(mx.NodeGraph):
                            continue
                        inner = [n.getNodeDef() for n in impl.getNodes()]
                        if inner and all(d is not None and self.how(d.getName()) for d in inner):
                            result = "expanded"
                        break
        self._cache[name] = result
        return result

    def resolves(self, name):
        return bool(self.how(name))
