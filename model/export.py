"""Writers: Rhino .3dm, glTF .glb, OBJ, STL, viewer JSON and SVG plans."""
from __future__ import annotations

import json
import math

import numpy as np

FT = 0.3048  # metres per foot (glTF is metric)


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb)


# ---------------------------------------------------------------------------
# Rhino
# ---------------------------------------------------------------------------
def write_3dm(elements, layers, path):
    import rhino3dm as r

    model = r.File3dm()
    model.Settings.ModelUnitSystem = r.UnitSystem.Feet
    index = {}
    for name, (rgb, alpha) in layers.items():
        lyr = r.Layer()
        lyr.Name = name
        lyr.Color = tuple(int(c * 255) for c in rgb) + (255,)
        index[name] = model.Layers.Add(lyr)

    for e in elements:
        attr = r.ObjectAttributes()
        attr.Name = e.name
        attr.LayerIndex = index[e.layer]
        # every element is a planar profile swept along a vector
        pts = [r.Point3d(*map(float, p)) for p in e.polygon]
        pts.append(pts[0])
        vec = np.array(e.vector, dtype=float)
        geo = r.Extrusion.Create(r.PolylineCurve(pts), float(np.linalg.norm(vec)), True)
        # Extrusion.Create sweeps along the profile's own normal, which may face
        # backwards; if so the solid sits one vector-length behind, so move it.
        sweep = np.array([geo.PathEnd.X - geo.PathStart.X, geo.PathEnd.Y - geo.PathStart.Y,
                          geo.PathEnd.Z - geo.PathStart.Z])
        if np.dot(sweep, vec) < 0:
            geo.Translate(r.Vector3d(*map(float, vec)))
        model.Objects.Add(geo, attr)   # native Rhino extrusion (a closed solid)
    model.Write(str(path), 7)


# ---------------------------------------------------------------------------
# Mesh formats via trimesh
# ---------------------------------------------------------------------------
def _scene(elements, layers, metres=True):
    import trimesh

    scale = FT if metres else 1.0
    scene = trimesh.Scene()
    for e in elements:
        v, f = e.mesh()
        # glTF / most viewers are Y-up: map (x, y, z) -> (x, z, -y)
        v = np.column_stack([v[:, 0], v[:, 2], -v[:, 1]]) * scale
        rgb, alpha = layers[e.layer]
        mat = trimesh.visual.material.PBRMaterial(
            name=e.layer,
            baseColorFactor=[*rgb, alpha],
            alphaMode="BLEND" if alpha < 1 else "OPAQUE",
            metallicFactor=0.0, roughnessFactor=0.85, doubleSided=True)
        m = trimesh.Trimesh(v, f, process=False,
                            visual=trimesh.visual.TextureVisuals(material=mat))
        scene.add_geometry(m, node_name=f"{e.layer} / {e.name}", geom_name=e.name)
    return scene


def write_meshes(elements, layers, outdir):
    import trimesh

    scene = _scene(elements, layers)
    scene.export(outdir / "building.glb")
    obj = scene.export(file_type="obj", mtl_name="building.mtl", include_texture=True)
    if isinstance(obj, dict):  # trimesh returns {filename: bytes} when mtl is included
        for fname, data in obj.items():
            (outdir / ("building.obj" if fname.endswith(".obj") else fname)).write_bytes(
                data if isinstance(data, bytes) else data.encode())
    else:
        (outdir / "building.obj").write_text(obj)
    # STL: solids only (no site, glass or zone overlays). GitHub previews STL in 3D.
    solid = [e for e in elements if e.layer not in ("Site", "Glazing", "Studio-Zones")]
    meshes = []
    for e in solid:
        v, f = e.mesh()
        meshes.append(trimesh.Trimesh(v, f, process=False))
    trimesh.util.concatenate(meshes).export(outdir / "building.stl")


# ---------------------------------------------------------------------------
# Viewer data
# ---------------------------------------------------------------------------
def viewer_data(elements, layers, rooms, levels, label_at, summary):
    objs = []
    for e in elements:
        v, f = e.mesh()
        objs.append({
            "n": e.name, "l": e.layer,
            "v": [round(float(x), 3) for x in v.flatten()],
            "f": [int(i) for i in f.flatten()],
        })
    from design import room_area  # noqa: E402  (local import keeps this module generic)
    room_list = []
    for level, name, rect, sub in rooms:
        cx, cy = label_at.get(name, ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2))
        room_list.append({"level": level, "name": name,
                          "area": round(room_area(rect, sub)),
                          "x": cx, "y": cy, "z": levels[level]["floor"]})
    return {
        "layers": {k: {"color": _hex(c), "opacity": a} for k, (c, a) in layers.items()},
        "objects": objs,
        "rooms": room_list,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Plans (SVG). Walls and anything crossing the cut plane are poched; things
# below the cut are drawn in outline.
# ---------------------------------------------------------------------------
PLAN_CSS = """
.plan { font-family: var(--plan-font, 'IBM Plex Sans', Helvetica, Arial, sans-serif); }
.cut { fill: var(--plan-cut, #2a2b2e); stroke: none; }
.insul { fill: var(--plan-insul, #d9d3c7); stroke: none; }
.stud { fill: var(--plan-stud, #b98d4f); stroke: var(--plan-cut, #2a2b2e); stroke-width: .015; }
.cut-int { fill: var(--plan-cut-int, #55575c); stroke: none; }
.glass { fill: var(--plan-glass, #8fc0dd); stroke: var(--plan-cut, #2a2b2e); stroke-width: .03; }
.below { fill: none; stroke: var(--plan-line, #5d6066); stroke-width: .06; }
.equip { fill: var(--plan-equip, rgba(51,82,115,.12)); stroke: var(--plan-equip-line, #335273); stroke-width: .07; }
.zone { fill: var(--plan-zone, rgba(232,140,51,.14)); stroke: var(--plan-zone-line, #d9822b); stroke-width: .06; stroke-dasharray: .4 .25; }
.mullion { stroke: var(--plan-cut, #2a2b2e); stroke-width: .05; }
.swing { fill: none; stroke: var(--plan-line, #5d6066); stroke-width: .045; }
.leaf { stroke: var(--plan-cut, #2a2b2e); stroke-width: .1; }
.room { fill: var(--plan-text, #1d1e20); font-size: .95px; font-weight: 600; text-anchor: middle; }
.area { fill: var(--plan-muted, #6b6e74); font-size: .7px; text-anchor: middle; }
.zlabel { fill: var(--plan-zone-line, #b5661d); font-size: .6px; font-style: italic; }
.elabel { fill: var(--plan-equip-line, #335273); font-size: .5px; text-anchor: middle; }
.dim { stroke: var(--plan-muted, #6b6e74); stroke-width: .04; fill: none; }
.dimt { fill: var(--plan-muted, #6b6e74); font-size: .7px; text-anchor: middle; }
.title { fill: var(--plan-text, #1d1e20); font-size: 1.3px; font-weight: 600; }
.sub { fill: var(--plan-muted, #6b6e74); font-size: .7px; }
.north { fill: var(--plan-text, #1d1e20); }
"""

EQUIP_LABELS = {
    "Etching press bed (30\"x60\", 7' travel)": "Etching press",
    "Inking table (glass slab top)": "Inking table",
    "Paper prep / blotter table": "Paper prep",
    "Paper soaking tray": "Soak tray",
    "Deep sink (6' stainless)": "Deep sink",
    "Fume hood base": "Fume hood",
    "Drying rack": "Drying rack",
    "Flat files 1": "Flat files",
    "Flat files 2": "Flat files",
    "Clean work table": "Clean table",
    "Kitchen counter": "Kitchen",
    "Refrigerator": "Fridge",
    "Kitchen island": "Island",
    "Dining table": "Dining",
    "Sofa": "Sofa",
    "Steinway Model S case (ebony)": "Steinway S",
    "Piano bench (30\" x 14\")": "Bench",
    "Queen bed": "Queen bed",
    "Closet": "Closet",
    "Bathtub / shower": "Tub / shower",
    "Stacked washer/dryer": "W/D",
}


def _fmt_ft(v):
    ft = int(v)
    inch = round((v - ft) * 12)
    if inch == 12:
        ft, inch = ft + 1, 0
    return f"{ft}'-{inch}\""


def plan_svg(elements, rooms, levels, label_at, level, length, depth, inline=False,
             vertical=()):
    lv = levels[level]
    f, c = lv["floor"], lv["cut"]
    pad_l, pad_t, pad_r, pad_b = 4.0, 5.0, 4.0, 5.5
    W, H = length + pad_l + pad_r, depth + pad_t + pad_b
    Y = lambda y: depth - y + pad_t    # noqa: E731  svg y grows downward; north is up
    X = lambda x: x + pad_l            # noqa: E731

    def rect(lo, hi, cls, title=None):
        t = f"<title>{title}</title>" if title else ""
        return (f'<rect class="{cls}" x="{X(lo[0]):.3f}" y="{Y(hi[1]):.3f}" '
                f'width="{hi[0] - lo[0]:.3f}" height="{hi[1] - lo[1]:.3f}">{t}</rect>')

    below, cut, overlay, labels = [], [], [], []
    for e in elements:
        lo, hi = e.bbox()
        if e.layer in ("Site", "Roof", "Floors", "Slab"):
            continue
        crosses = lo[2] < c < hi[2]
        if e.layer == "Studio-Zones":
            if level == "ground":
                below.append(rect(lo, hi, "zone", e.name))
                labels.append(f'<text class="zlabel" x="{X(lo[0]) + .25:.2f}" '
                              f'y="{Y(hi[1]) + .75:.2f}">{e.name}</text>')
            continue
        if e.layer == "Stair":
            if e.name.startswith("Tread") and (level == "upper" or hi[2] <= c + 0.7):
                below.append(rect(lo, hi, "below"))
            continue
        if e.layer == "Glazing" and crosses:
            if e.meta.get("window"):  # draw across the full wall thickness, with a centre line
                c0, c1 = e.meta["wall"]
                if e.meta["axis"] == "x":
                    lo, hi = (lo[0], c0, lo[2]), (hi[0], c1, hi[2])
                else:
                    lo, hi = (c0, lo[1], lo[2]), (c1, hi[1], hi[2])
                overlay.append(rect(lo, hi, "glass", e.name))
                mx0, my0 = (lo[0], (c0 + c1) / 2) if e.meta["axis"] == "x" else ((c0 + c1) / 2, lo[1])
                mx1, my1 = (hi[0], (c0 + c1) / 2) if e.meta["axis"] == "x" else ((c0 + c1) / 2, hi[1])
                overlay.append(f'<line class="mullion" x1="{X(mx0):.2f}" y1="{Y(my0):.2f}" '
                               f'x2="{X(mx1):.2f}" y2="{Y(my1):.2f}"/>')
            else:
                overlay.append(rect(lo, hi, "glass", e.name))
            continue
        if e.layer == "Doors" and crosses:
            continue  # drawn as swings below
        if e.layer.startswith("Walls") and crosses:
            cls = {"Walls-Ext-Cellulose": "insul", "Walls-Ext-Framing": "stud",
                   "Walls-Interior": "cut-int"}.get(e.layer, "cut")
            cut.append(rect(lo, hi, cls))
            continue
        if e.layer in ("Studio-Equipment", "ADU-Furniture", "ADU-Piano") and lo[2] >= f - 0.1 and lo[2] < c:
            if e.meta.get("plan") is False:
                continue
            if e.kind == "prism" and abs(e.vector[0]) + abs(e.vector[1]) < 1e-9:
                # vertical extrusion: draw its true outline (e.g. the piano's curved case)
                pts = " ".join(f"{X(x):.3f},{Y(y):.3f}" for x, y, _ in e.polygon)
                below.append(f'<polygon class="equip" points="{pts}"><title>{e.name}</title></polygon>')
            else:
                below.append(rect(lo, hi, "equip", e.name))
            if e.name in EQUIP_LABELS:
                labels.append(f'<text class="elabel" x="{X((lo[0] + hi[0]) / 2):.2f}" '
                              f'y="{Y((lo[1] + hi[1]) / 2) + .18:.2f}">{EQUIP_LABELS[e.name]}</text>')

    # door swings
    for e in elements:
        d = e.meta.get("door")
        lo, hi = e.bbox()
        if not d or not (lo[2] < c < hi[2]):
            continue
        axis, mid, swing = e.meta["axis"], e.meta["wall_mid"], e.meta.get("swing", "")
        a, b = (lo[0], hi[0]) if axis == "x" else (lo[1], hi[1])
        if d == "slider" or not swing:
            # sliding door: two overlapping panels
            for k, off in ((0, -.15), (1, .15)):
                p0, p1 = a + k * (b - a) / 2 - .1 * k, a + (k + 1) * (b - a) / 2 + .1 * (1 - k)
                if axis == "x":
                    overlay.append(f'<line class="leaf" x1="{X(p0):.2f}" y1="{Y(mid + off):.2f}" '
                                   f'x2="{X(p1):.2f}" y2="{Y(mid + off):.2f}"/>')
                else:
                    overlay.append(f'<line class="leaf" x1="{X(mid + off):.2f}" y1="{Y(p0):.2f}" '
                                   f'x2="{X(mid + off):.2f}" y2="{Y(p1):.2f}"/>')
            continue
        side = 1 if swing[0] == "+" else -1
        hinge, free = (a, b) if swing[1] == "a" else (b, a)
        w = abs(b - a)
        if axis == "x":
            hx, hy = hinge, mid
            lx, ly = hinge, mid + side * w
            fx, fy = free, mid
        else:
            hx, hy = mid, hinge
            lx, ly = mid + side * w, hinge
            fx, fy = mid, free
        overlay.append(f'<line class="leaf" x1="{X(hx):.2f}" y1="{Y(hy):.2f}" '
                       f'x2="{X(lx):.2f}" y2="{Y(ly):.2f}"/>')
        # arc from leaf tip to the free jamb, centred on the hinge
        cross = (lx - hx) * (fy - hy) - (ly - hy) * (fx - hx)
        sweep = 1 if cross < 0 else 0  # svg y is flipped
        overlay.append(f'<path class="swing" d="M{X(lx):.2f},{Y(ly):.2f} A{w:.2f},{w:.2f} 0 0 '
                       f'{sweep} {X(fx):.2f},{Y(fy):.2f}"/>')

    from design import room_area
    for lvl, name, r, sub in rooms:
        if lvl != level:
            continue
        cx, cy = label_at.get(name, ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2))
        rot = f' transform="rotate(-90 {X(cx):.2f} {Y(cy):.2f})"' if name in vertical else ""
        labels.append(f'<g{rot}><text class="room" x="{X(cx):.2f}" y="{Y(cy):.2f}">{name}</text>'
                      f'<text class="area" x="{X(cx):.2f}" y="{Y(cy) + .9:.2f}">'
                      f'{room_area(r, sub):.0f} sf</text></g>')

    # dimensions, title, north arrow, scale bar
    dims = []
    yb = Y(0) + 2.2
    dims.append(f'<path class="dim" d="M{X(0)},{yb} H{X(length)} M{X(0)},{yb - .4} V{yb + .4} '
                f'M{X(length)},{yb - .4} V{yb + .4}"/>')
    dims.append(f'<text class="dimt" x="{X(length / 2)}" y="{yb - .3}">{_fmt_ft(length)}</text>')
    xr = X(length) + 2.0
    dims.append(f'<path class="dim" d="M{xr},{Y(0)} V{Y(depth)} M{xr - .4},{Y(0)} H{xr + .4} '
                f'M{xr - .4},{Y(depth)} H{xr + .4}"/>')
    dims.append(f'<text class="dimt" transform="translate({xr - .35},{Y(depth / 2)}) rotate(-90)">'
                f'{_fmt_ft(depth)}</text>')
    sb_y = Y(0) + 4.2
    for i in range(4):
        dims.append(f'<rect x="{X(i * 2.5)}" y="{sb_y}" width="2.5" height=".35" '
                    f'class="{"cut" if i % 2 == 0 else "below"}"/>')
    dims.append(f'<text class="sub" x="{X(10.6)}" y="{sb_y + .4}">10 ft</text>')
    nx, ny = X(length) + 2.0, pad_t - 3.0
    dims.append(f'<path class="north" d="M{nx},{ny - 1} L{nx + .55},{ny + .6} L{nx},{ny + .25} '
                f'L{nx - .55},{ny + .6} Z"/><text class="sub" x="{nx}" y="{ny + 1.5}" '
                f'text-anchor="middle">N</text>')
    dims.append(f'<text class="title" x="{X(0)}" y="{pad_t - 2.6}">{lv["title"]}</text>')
    dims.append(f'<text class="sub" x="{X(0)}" y="{pad_t - 1.5}">Plan cut at '
                f'{c - f:g} ft above floor. Concept v1, not for construction.</text>')

    style = "" if inline else f"<style>{PLAN_CSS}</style>"
    bg = "" if inline else f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fbfbf9"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="plan" viewBox="0 0 {W:.2f} {H:.2f}" '
            f'role="img" aria-label="{lv["title"]}">{style}{bg}'
            + "".join(below) + "".join(cut) + "".join(overlay) + "".join(labels) + "".join(dims)
            + "</svg>")


def write_json(data, path):
    path.write_text(json.dumps(data, separators=(",", ":")))
