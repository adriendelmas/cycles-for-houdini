"""Flatten `op:` COP texture references so a third-party renderer can read them.

Houdini lets a texture path point straight at a COP with `op:/img/net/OUT`.
Its own renderers evaluate that through Houdini's image library, but a delegate
like Cycles only ever sees a string it cannot open - the USD asset resolver
accepts the path and hands back an asset of size zero, so the texture silently
goes missing.

This walks the stage, cooks every referenced COP to a real image file and
rewrites the paths to point at it.

Use it from a Python LOP placed before the render node:

    import flatten_op_textures
    flatten_op_textures.run(hou.pwd())

The rewrite happens on the LOP's own layer, so the original scene is untouched
and removing the node restores the `op:` paths.

Caveat: this is a snapshot. Editing the COP afterwards does not update a
running IPR - recook this node to pick the change up.
"""

import os
import tempfile

import hou
from pxr import Sdf, UsdShade


def _output_path(cop_path, frame, directory):
    """A stable filename per COP and frame, so repeated cooks reuse the file
    rather than filling the temp directory."""
    safe = cop_path.strip("/").replace("/", "_")
    return os.path.join(directory, "hdcycles_cop_%s.%04d.exr" % (safe, int(frame)))


def _flatten(cop_path, frame, directory, cache):
    """Cook one COP to an image file, once per run."""
    if cop_path in cache:
        return cache[cop_path]

    node = hou.node(cop_path)
    if node is None:
        hou.logging.log(hou.logging.LogEntry(
            "No COP at '%s', leaving the path alone" % cop_path,
            severity=hou.severityType.Warning))
        cache[cop_path] = None
        return None

    out = _output_path(cop_path, frame, directory)
    try:
        node.saveImage(out)
    except hou.Error as exc:
        hou.logging.log(hou.logging.LogEntry(
            "Could not cook '%s': %s" % (cop_path, exc),
            severity=hou.severityType.Warning))
        cache[cop_path] = None
        return None

    cache[cop_path] = out
    return out


def run(node, directory=None):
    """Rewrite every `op:` asset path on the stage of `node`.

    Returns the number of attributes rewritten.
    """
    stage = node.editableStage()
    frame = hou.frame()
    directory = directory or tempfile.gettempdir()
    cache = {}
    rewritten = 0

    for prim in stage.Traverse():
        shader = UsdShade.Shader(prim)
        if not shader:
            continue

        for shader_input in shader.GetInputs():
            attr = shader_input.GetAttr()
            if attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue

            value = attr.Get()
            if value is None:
                continue

            authored = value.path
            if not authored.startswith("op:"):
                continue

            flattened = _flatten(authored[len("op:"):], frame, directory, cache)
            if flattened:
                attr.Set(Sdf.AssetPath(flattened))
                rewritten += 1

    return rewritten
