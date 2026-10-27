"""Writes a small example model: examples/bracket/ with two parts (bracket.stl, pipe.stl), units mm."""
import math, struct
from pathlib import Path


def write_stl(path, tris):
    with open(path, "wb") as f:
        f.write(b"sketch-to-prompt example".ljust(80, b" ")); f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            u = [b[i] - a[i] for i in range(3)]; v = [c[i] - a[i] for i in range(3)]
            n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            f.write(struct.pack("<12fH", *n, *a, *b, *c, 0))


def box(x0, y0, z0, x1, y1, z1):
    p = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    q = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return [t for a, b, c, d in q for t in ((p[a], p[b], p[c]), (p[a], p[c], p[d]))]


def tube(c, r_in, r_out, z0, z1, n=48):
    t = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        P = lambda r, a, z: (c[0] + r * math.cos(a), c[1] + r * math.sin(a), z)
        for r, s in ((r_out, 1), (r_in, -1)):
            q = (P(r, a0, z0), P(r, a1, z0), P(r, a1, z1), P(r, a0, z1))
            t += [(q[0], q[1], q[2]), (q[0], q[2], q[3])] if s > 0 else [(q[0], q[2], q[1]), (q[0], q[3], q[2])]
        for z, s in ((z0, -1), (z1, 1)):
            q = (P(r_in, a0, z), P(r_out, a0, z), P(r_out, a1, z), P(r_in, a1, z))
            t += [(q[0], q[1], q[2]), (q[0], q[2], q[3])] if s > 0 else [(q[0], q[2], q[1]), (q[0], q[3], q[2])]
    return t


o = Path(__file__).with_name("bracket"); o.mkdir(exist_ok=True)
write_stl(o / "bracket.stl", box(0, 0, 0, 120, 60, 10) + box(0, 0, 10, 10, 60, 90))
write_stl(o / "pipe.stl", tube((70, 30), 12, 16, 10, 70))
print("written", o)
