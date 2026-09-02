"""Chaque noeud branche doit changer l'image par rapport a la reference.

Un noeud qui n'y change rien n'est pas forcement casse - une valeur constante
egale au defaut ne se voit pas - mais il merite d'etre regarde de pres."""
import os, subprocess
ROOT = r"E:\WORK\PERSONNAL STUFF\HOUDINI\hdCycles"
HFS = r"E:\Side Effects Software\Houdini22.0.368\bin"
IMG = os.path.join(ROOT, "tests", "usd", "bench", "images")
base = os.path.join(IMG, "_baseline.exr")
env = dict(os.environ); env["PATH"] = HFS + ";" + env["PATH"]

inert = []
total = 0
for f in sorted(os.listdir(IMG)):
    if not f.endswith(".exr") or f == "_baseline.exr":
        continue
    total += 1
    r = subprocess.run([os.path.join(HFS, "hoiiotool.exe"), "--diff", base,
                        os.path.join(IMG, f)], capture_output=True, text=True, env=env)
    if "PASS" in (r.stdout or ""):
        inert.append(f[len("cycles_"):-4])
print("%d noeuds compares a la reference" % total)
print("%d sans effet visible:" % len(inert))
for n in inert:
    print("   ", n)
