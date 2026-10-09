"""Run a step in the agent's own Houdini session, then capture its window.

The window of the Houdini started by tests/houdini/launch_cycles_log.cmd is
grabbed with PrintWindow, which works while it sits behind other windows
(the viewport's flipbook does not: it returned the same stale image for
every state, 2026-10-09). It refuses to run in a session whose scene is not
under hdCycles/tests, so it can never drive Adrien's own Houdini.

    python tools/gui_capture.py NAME ["python step run in Houdini first"] [--wait S]

The step runs through tools/hou_remote.py, then the script waits (default 10
s, pumping Houdini's event loop) so the render settles before the grab.
Images go to tests/scratch/gui/NAME.png.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "tests", "scratch", "gui")

GRAB = r"""
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class Grab {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  public struct RECT { public int L, T, R, B; }
  public static IntPtr Find(uint target) { IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint pid; GetWindowThreadProcessId(h, out pid); var sb = new StringBuilder(512);
      GetWindowText(h, sb, 512); if (pid == target && sb.ToString().Contains("Houdini FX")) found = h; return true; }, IntPtr.Zero);
    return found; } }
"@
$h = [Grab]::Find([uint32]$env:GRAB_PID)
if ($h -eq [IntPtr]::Zero) { Write-Error "no Houdini window of the test session"; exit 1 }
$r = New-Object Grab+RECT; [Grab]::GetWindowRect($h, [ref]$r) | Out-Null
$bmp = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
$g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
[Grab]::PrintWindow($h, $dc, 2) | Out-Null
$g.ReleaseHdc($dc); $bmp.Save($env:GRAB_OUT)
"""


def main():
    args = [a for a in sys.argv[1:]]
    wait = 10.0
    if "--wait" in args:
        i = args.index("--wait")
        wait = float(args[i + 1])
        del args[i:i + 2]
    name = args[0]
    step = args[1] if len(args) > 1 else ""
    # Never drive Adrien's own Houdini: only a session on a test scene.
    guard = ("assert 'hdCycles/tests' in hou.hipFile.path(), "
             "'not the agent test session: ' + hou.hipFile.path()\n")
    code = (guard + step + "\nimport time\n_t = time.time()\n"
            "hou.ui.waitUntil(lambda: time.time() > _t + %g)\n" % wait)
    subprocess.run([sys.executable, os.path.join(HERE, "hou_remote.py"), "-c", code], check=True)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".png")
    # The window of the very process that ran the step: two sessions on the
    # same scene once had the same title, and the wrong one was grabbed.
    pid = subprocess.run([sys.executable, os.path.join(HERE, "hou_remote.py"), "-c",
                          "import os; print(os.getpid())"],
                         check=True, capture_output=True, text=True).stdout.strip().splitlines()[-1]
    env = dict(os.environ, GRAB_OUT=path, GRAB_PID=pid)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", GRAB],
                   check=True, env=env)
    print(path)


if __name__ == "__main__":
    main()
