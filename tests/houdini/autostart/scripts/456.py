"""Starts the houdini-mcp server when the scene is loaded.

A Houdini launched by tests/houdini/launch_cycles_log.cmd can then be driven
by tools/hou_remote.py at once, with no click on the MCP shelf tool. Houdini
runs only the first scripts/456.py it finds, so the launcher puts this folder
first on HOUDINI_SCRIPT_PATH and the other 456.py files (SideFX Labs' for
one) are run from here, so nothing of the usual startup is lost.
"""
import os

import hou


def _start_mcp():
    try:
        import houdinimcp
        # Another port when another session's Houdini holds the default.
        houdinimcp.start_server(port=int(os.environ.get("HDCYCLES_MCP_PORT", "9876")))
    except Exception as exc:  # the plugin is optional, never block the load
        print("houdinimcp not started:", exc)


_start_mcp()
_here = os.path.normcase(os.path.abspath(__file__))
try:
    for _other in hou.findFiles("scripts/456.py"):
        if os.path.normcase(os.path.abspath(_other)) != _here:
            exec(compile(open(_other, encoding="utf-8").read(), _other, "exec"),
                 {"__file__": _other, "__name__": "__main__"})
except hou.OperationFailed:
    pass
