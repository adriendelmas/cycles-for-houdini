"""Run Python inside the Houdini session that has the HoudiniMCP server on.

The houdini-mcp plugin (Documents/houdini22.0/scripts/python/houdinimcp)
listens on 127.0.0.1:9876 once its shelf tool "MCP Start/Stop" has been
clicked - or at once in a Houdini started by tests/houdini/launch_cycles_log.cmd,
which runs the server on scene load. Its protocol is a 4-byte big-endian
length followed by UTF-8 JSON;
`execute_code` runs a string on Houdini's main thread and returns what it
printed. This is the piece that lets a bench drive the real viewport - the
Hydra render pass, the display driver, Solaris' scene index - which husk
never exercises.

    python tools/hou_remote.py ping
    python tools/hou_remote.py -c "import hou; print(hou.hipFile.path())"
    python tools/hou_remote.py script.py [--timeout SECONDS] [--port N]

The script runs with `hou` in its namespace and its stdout comes back here.
The Houdini side is single-client, newest wins: a connection left open by
someone else is dropped when this one arrives.
"""

import argparse
import json
import os
import socket
import struct
import sys

# HDCYCLES_MCP_PORT moves both ends off 9876, when another session's Houdini
# holds it (tests/houdini/autostart/scripts/456.py reads it too).
HOST, PORT = "127.0.0.1", int(os.environ.get("HDCYCLES_MCP_PORT", "9876"))


def call(command, params=None, timeout=300.0, port=None):
    sock = socket.create_connection((HOST, port or PORT), timeout=timeout)
    try:
        payload = json.dumps({"type": command, "params": params or {}}).encode("utf-8")
        sock.sendall(struct.pack(">I", len(payload)) + payload)
        header = b""
        while len(header) < 4:
            chunk = sock.recv(4 - len(header))
            if not chunk:
                raise ConnectionError("Houdini closed the connection")
            header += chunk
        (length,) = struct.unpack(">I", header)
        body = b""
        while len(body) < length:
            chunk = sock.recv(min(65536, length - len(body)))
            if not chunk:
                raise ConnectionError("Houdini closed the connection mid-reply")
            body += chunk
        return json.loads(body.decode("utf-8"))
    finally:
        sock.close()


def run_code(code, timeout=300.0, port=None):
    """Returns (stdout, stderr); raises on a Houdini-side error."""
    reply = call("execute_code", {"code": code}, timeout, port)
    if reply.get("status") != "success":
        raise RuntimeError(reply.get("message", "unknown error"))
    result = reply.get("result", {})
    return result.get("stdout", ""), result.get("stderr", "")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("script", nargs="?", help="a Python file to run in Houdini, or 'ping'")
    p.add_argument("-c", dest="code", help="Python code to run in Houdini")
    p.add_argument("--timeout", type=float, default=300.0)
    p.add_argument("--port", type=int, default=PORT,
                   help="the plugin's port; tests/headless_host.py of houdinimcp uses 19878")
    args = p.parse_args()

    if args.script == "ping":
        print(call("ping", timeout=args.timeout, port=args.port))
        return
    code = args.code if args.code else open(args.script, encoding="utf-8").read()
    try:
        out, err = run_code(code, args.timeout, args.port)
    except ConnectionRefusedError:
        sys.exit("Houdini is not listening on %s:%d - click the MCP shelf tool first."
                 % (HOST, args.port))
    sys.stdout.write(out)
    if err:
        sys.stderr.write(err)


if __name__ == "__main__":
    main()
