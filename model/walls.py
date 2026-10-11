"""Exterior wall assembly: double-stud wall, dense-pack cellulose.

Layers are listed outside to inside as (layer name, thickness in feet).
The two stud rows sit inside the cellulose layer; cellulose fills the
stud bays and the gap between the rows, so it is one continuous 8" blanket.
"""
from geometry import box, prism, wall

IN = 1 / 12

SHEATHING = 0.5 * IN       # 1/2" plywood / OSB, taped as the air barrier
OUTER_STUDS = 3.5 * IN     # 2x4 row, bearing (carries floor and roof)
GAP = 1.0 * IN             # thermal break between rows
INNER_STUDS = 3.5 * IN     # 2x4 row, non-bearing, carries services
DRYWALL = 0.5 * IN

CORE = OUTER_STUDS + GAP + INNER_STUDS          # 8" double-stud / cellulose depth
THICKNESS = SHEATHING + CORE + DRYWALL          # 9" overall (siding not modelled)

STUD_W = 1.5 * IN          # face width of a 2x stud
SPACING = 2.0              # 24" on centre
PLATE = 1.5 * IN

# offsets from the exterior face: (layer, start, end)
LAYERS = [
    ("Walls-Ext-Sheathing", 0.0, SHEATHING),
    ("Walls-Ext-Cellulose", SHEATHING, SHEATHING + CORE),
    ("Walls-Ext-Drywall", SHEATHING + CORE, THICKNESS),
]
ROWS = [
    ("outer", SHEATHING, SHEATHING + OUTER_STUDS),
    ("inner", SHEATHING + OUTER_STUDS + GAP, SHEATHING + CORE),
]

ASSEMBLY_TABLE = [
    # layer, thickness (in), approx R
    ("Siding on 3/4\" rainscreen battens (not modelled)", None, None),
    ("1/2\" plywood sheathing, taped seams (air barrier)", 0.5, 0.6),
    ("2x4 outer stud row, 24\" o.c., bearing", 3.5, None),
    ("1\" gap between rows (thermal break)", 1.0, None),
    ("2x4 inner stud row, 24\" o.c., services", 3.5, None),
    ("Dense-pack cellulose filling all 8\" (about R-3.6/in)", 8.0, 28.8),
    ("1/2\" drywall, latex paint (vapour retarder)", 0.5, 0.45),
]


class Side:
    """One exterior wall: which axis it runs along, where its outside face is,
    and which way is inward (+1 or -1)."""

    def __init__(self, name, axis, face, inward, length, openings):
        self.name, self.axis, self.face, self.inward = name, axis, face, inward
        self.length, self.openings = length, openings

    def across(self, o0, o1):
        a, b = self.face + self.inward * o0, self.face + self.inward * o1
        return min(a, b), max(a, b)

    def extent(self, o0, o1):
        """x-walls run through the corners; y-walls stop against them."""
        if self.axis == "x":
            return o0, self.length - o0
        return o1, self.length - o1


def build_walls(sides, z0, z1, storeys, gables=(), plate_z=None, ridge_z=None, depth=None):
    out = []
    band_for = {}
    for sd in sides:
        band_for[sd.name] = sd.across(0, THICKNESS)
        for layer, o0, o1 in LAYERS:
            a0, a1 = sd.extent(o0, o1)
            c0, c1 = sd.across(o0, o1)
            out += wall(f"{sd.name} {layer.split('-')[-1].lower()}", layer, sd.axis,
                        a0, a1, c0, c1, z0, z1, sd.openings,
                        infill=layer == "Walls-Ext-Cellulose", band=band_for[sd.name])
        out += framing(sd, storeys)
    for name, x_face, inward in gables:
        for layer, o0, o1 in LAYERS:
            x0 = min(x_face + inward * o0, x_face + inward * o1)
            out.append(prism(f"{name} {layer.split('-')[-1].lower()}", layer,
                             [(x0, 0, plate_z), (x0, depth, plate_z), (x0, depth / 2, ridge_z)],
                             (o1 - o0, 0, 0)))
    return out


def framing(sd, storeys):
    """Studs, plates, kings, cripples and headers for both rows of one wall.
    `storeys` is a list of (bottom, top) z for each platform-framed storey."""
    E = []
    eps = 0.002   # keep studs a hair inside the cellulose so faces don't coincide

    def blk(name, a0, a1, c0, c1, zz0, zz1):
        if a1 - a0 <= 1e-6 or zz1 - zz0 <= 1e-6:
            return
        if sd.axis == "x":
            E.append(box(name, "Walls-Ext-Framing", a0, c0 + eps, zz0, a1, c1 - eps, zz1))
        else:
            E.append(box(name, "Walls-Ext-Framing", c0 + eps, a0, zz0, c1 - eps, a1, zz1))

    for row, o0, o1 in ROWS:
        a_start, a_end = sd.extent(o0, o1)
        c0, c1 = sd.across(o0, o1)
        tag = f"{sd.name} {row}"
        for zb, zt in storeys:
            ops = [o for o in sd.openings if o.sill < zt and o.head > zb]
            s0, s1 = zb + PLATE, zt - 2 * PLATE     # stud bottom / top
            # plates (bottom plate is cut out at door openings)
            cursor = a_start
            for o in sorted(ops, key=lambda o: o.a):
                if o.sill <= zb + 0.01:
                    blk(f"{tag} bottom plate", cursor, o.a, c0, c1, zb, s0)
                    cursor = o.b
            blk(f"{tag} bottom plate", cursor, a_end, c0, c1, zb, s0)
            blk(f"{tag} double top plate", a_start, a_end, c0, c1, s1, zt)

            # common studs at 24" o.c., plus an end stud
            positions = [a_start + i * SPACING for i in range(int((a_end - a_start) / SPACING) + 1)]
            if a_end - STUD_W - positions[-1] > STUD_W:
                positions.append(a_end - STUD_W)
            for p in positions:
                p = min(p, a_end - STUD_W)
                hit = [o for o in ops if p + STUD_W > o.a - STUD_W and p < o.b + STUD_W]
                if not hit:
                    blk(f"{tag} stud", p, p + STUD_W, c0, c1, s0, s1)
                    continue
                o = hit[0]
                if p + STUD_W <= o.a or p >= o.b:
                    continue   # falls on a king stud
                hdr = min(o.head + 0.75, s1)
                if o.sill > s0:
                    blk(f"{tag} cripple", p, p + STUD_W, c0, c1, s0, o.sill - PLATE)
                blk(f"{tag} cripple", p, p + STUD_W, c0, c1, hdr, s1)

            for o in ops:
                blk(f"{tag} king stud", o.a - STUD_W, o.a, c0, c1, s0, s1)
                blk(f"{tag} king stud", o.b, o.b + STUD_W, c0, c1, s0, s1)
                if o.head < s1:
                    blk(f"{tag} header", o.a, o.b, c0, c1, o.head, min(o.head + 0.75, s1))
                if o.sill > s0:
                    blk(f"{tag} sill", o.a, o.b, c0, c1, o.sill - PLATE, o.sill)
        # rim board at each floor line, in the bearing (outer) row
        for (zb, zt), (nb, _) in zip(storeys, storeys[1:]):
            if row == "outer" and nb > zt:
                blk(f"{tag} rim board", a_start, a_end, c0, c1, zt, nb)
    return E
