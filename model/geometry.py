"""Geometry primitives for the building model.

Everything is built from two primitives so that every exporter (Rhino .3dm,
glTF, OBJ/STL, the web viewer and the plan drawings) can understand it:

* box    - an axis-aligned block (walls, slabs, furniture)
* prism  - a flat convex polygon swept along a vector (roof planes, gables,
           rollers)

Units are feet. x runs east, y runs north, z is up. Origin is the
south-west corner of the building at top of ground-floor slab.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Element:
    name: str
    layer: str
    kind: str                       # "box" or "prism"
    polygon: list                   # base polygon, list of (x, y, z)
    vector: tuple                   # sweep vector
    meta: dict = field(default_factory=dict)

    # ---- mesh -----------------------------------------------------------
    def mesh(self):
        base = np.array(self.polygon, dtype=float)
        top = base + np.array(self.vector, dtype=float)
        n = len(base)
        verts = np.vstack([base, top])
        normal = _newell(base)
        # orient so faces point outward
        flip = np.dot(normal, self.vector) > 0
        faces = []
        for a, b, c in _triangulate(base, normal):   # works for concave outlines too
            faces.append((a, c, b) if flip else (a, b, c))
            faces.append((n + a, n + b, n + c) if flip else (n + a, n + c, n + b))
        for i in range(n):
            j = (i + 1) % n
            quad = (i, j, n + j, n + i)
            if not flip:
                quad = quad[::-1]
            faces.append((quad[0], quad[1], quad[2]))
            faces.append((quad[0], quad[2], quad[3]))
        return verts, np.array(faces, dtype=int)

    def bbox(self):
        v, _ = self.mesh()
        return v.min(axis=0), v.max(axis=0)


def _newell(pts):
    """Polygon normal (Newell's method; robust for concave polygons)."""
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        (x0, y0, z0), (x1, y1, z1) = pts[i], pts[(i + 1) % len(pts)]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return np.array([nx, ny, nz])


def _triangulate(pts, normal):
    """Ear-clipping triangulation of a simple planar polygon. Triangles keep
    the polygon's winding."""
    drop = int(np.argmax(np.abs(normal)))
    keep = [i for i in range(3) if i != drop]
    p2 = pts[:, keep]
    area = sum(p2[i - 1][0] * p2[i][1] - p2[i][0] * p2[i - 1][1] for i in range(len(p2)))
    if area < 0:                  # make the 2D projection counter-clockwise
        p2 = p2[:, ::-1]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    idx = list(range(len(pts)))
    tris = []
    while len(idx) > 3:
        for k in range(len(idx)):
            i, j, m = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            if cross(p2[i], p2[j], p2[m]) <= 1e-12:
                continue  # reflex corner
            if any(cross(p2[i], p2[j], p2[q]) >= 0 and cross(p2[j], p2[m], p2[q]) >= 0
                   and cross(p2[m], p2[i], p2[q]) >= 0 for q in idx if q not in (i, j, m)):
                continue  # another vertex inside this ear
            tris.append((i, j, m))
            idx.pop(k)
            break
        else:
            raise ValueError("polygon could not be triangulated (self-intersecting?)")
    tris.append(tuple(idx))
    return tris


def box(name, layer, x0, y0, z0, x1, y1, z1, **meta):
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    return Element(name, layer, "box",
                   [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                   (0.0, 0.0, z1 - z0), meta)


def prism(name, layer, polygon, vector, **meta):
    return Element(name, layer, "prism", [tuple(map(float, p)) for p in polygon],
                   tuple(map(float, vector)), meta)


def cylinder_y(name, layer, cx, cz, r, y0, y1, sides=20, **meta):
    """Cylinder whose axis runs north-south (along y)."""
    pts = [(cx + r * math.cos(2 * math.pi * i / sides), y0,
            cz + r * math.sin(2 * math.pi * i / sides)) for i in range(sides)]
    return prism(name, layer, pts, (0, y1 - y0, 0), **meta)


# ---- walls with openings ---------------------------------------------------

@dataclass
class Opening:
    a: float            # start along the wall (absolute x or y)
    b: float            # end along the wall
    sill: float         # absolute z
    head: float         # absolute z
    kind: str = "window"   # window | door | glass-door | slider | open
    swing: str = ""        # doors only: "<side><hinge>", side +/- (toward
                           # increasing/decreasing perpendicular coordinate),
                           # hinge a/b, e.g. "+a"
    name: str = ""


def wall(name, layer, axis, along0, along1, across0, across1, z0, z1,
         openings=(), level=None, infill=True, band=None):
    """A straight wall. axis='x' runs east-west, axis='y' runs north-south.

    Returns the wall pieces plus, if `infill`, glazing / door leaves for each
    opening. `band` is the full (across0, across1) of a multi-layer wall, so
    infill can be centred in the whole assembly rather than in one layer.
    """
    band = band or (across0, across1)
    def blk(nm, lyr, a0, a1, c0, c1, zz0, zz1, **meta):
        if a1 - a0 < 1e-6 or zz1 - zz0 < 1e-6:
            return None
        if axis == "x":
            return box(nm, lyr, a0, c0, zz0, a1, c1, zz1, **meta)
        return box(nm, lyr, c0, a0, zz0, c1, a1, zz1, **meta)

    out = []
    ops = sorted(openings, key=lambda o: o.a)
    cursor = along0
    mid = (band[0] + band[1]) / 2
    for i, o in enumerate(ops):
        out.append(blk(f"{name} pier {i}", layer, cursor, o.a, across0, across1, z0, z1))
        out.append(blk(f"{name} below {o.name or i}", layer, o.a, o.b, across0, across1, z0, o.sill))
        out.append(blk(f"{name} above {o.name or i}", layer, o.a, o.b, across0, across1, o.head, z1))
        t = 0.06
        if not infill:
            pass
        elif o.kind == "window":
            out.append(blk(o.name or f"{name} window {i}", "Glazing",
                           o.a, o.b, mid - t / 2, mid + t / 2, o.sill, o.head,
                           window=True, axis=axis, wall=band))
        elif o.kind in ("glass-door", "slider"):
            out.append(blk(o.name or f"{name} door {i}", "Glazing",
                           o.a, o.b, mid - t / 2, mid + t / 2, o.sill, o.head,
                           door=o.kind, swing=o.swing, axis=axis, wall_mid=mid))
        elif o.kind == "door":
            out.append(blk(o.name or f"{name} door {i}", "Doors",
                           o.a, o.b, mid - 0.075, mid + 0.075, o.sill, o.head,
                           door="door", swing=o.swing, axis=axis, wall_mid=mid))
        cursor = o.b
    out.append(blk(f"{name} pier end", layer, cursor, along1, across0, across1, z0, z1))
    out = [e for e in out if e is not None]
    for e in out:
        e.meta.setdefault("level", level)
    return out
