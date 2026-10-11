"""Concept v1: print studio on the ground floor, ADU above.

This file is the single source of truth for the design. Change a number
here, run `python build.py`, and every output (Rhino file, 3D viewer,
plans) is regenerated.

Units: feet. x = east, y = north, z = up. Origin = SW corner of the
building, top of ground-floor slab.
"""
import walls
from geometry import Opening as O, box, cylinder_y, prism, wall

# ---------------------------------------------------------------------------
# Key parameters
# ---------------------------------------------------------------------------
LENGTH = 36.0            # east-west, exterior face to exterior face
DEPTH = 24.0             # north-south
EXT_WALL = walls.THICKNESS   # 9": 1/2" sheathing + 8" double-stud/cellulose + 1/2" drywall
INT_WALL = 0.375         # 4.5" interior partition

FLOOR2 = 12.0            # studio floor-to-floor (11' clear for the press, ducts)
FLOOR_THICK = 1.0        # upper floor structure
PLATE = FLOOR2 + 9.0     # top of upper walls (9' plate)
PITCH = 6 / 12           # roof slope
EAVE = 1.5               # eave overhang (north & south)
RAKE = 1.0               # rake overhang (east & west)
ROOF_THICK = 0.8
RIDGE = PLATE + PITCH * DEPTH / 2

STAIR_X0 = LENGTH - EXT_WALL - 3.625   # inside face of the stair partition
RISERS = 20
RISE = FLOOR2 / RISERS                 # 7.2"
TREAD = 10 / 12
STAIR_Y0 = 4.0                         # first riser
STAIR_Y1 = STAIR_Y0 + (RISERS - 1) * TREAD   # top riser = upper landing edge

LAYERS = {
    # name: (rgb, opacity)
    "Site":              ((0.62, 0.68, 0.56), 1.0),
    "Slab":              ((0.62, 0.62, 0.60), 1.0),
    "Walls-Ext-Sheathing": ((0.93, 0.92, 0.89), 1.0),
    "Walls-Ext-Cellulose": ((0.72, 0.70, 0.66), 1.0),
    "Walls-Ext-Framing":   ((0.86, 0.72, 0.50), 1.0),
    "Walls-Ext-Drywall":   ((0.98, 0.98, 0.97), 1.0),
    "Walls-Interior":    ((0.97, 0.97, 0.95), 1.0),
    "Floors":            ((0.78, 0.66, 0.50), 1.0),
    "Roof":              ((0.33, 0.35, 0.38), 1.0),
    "Glazing":           ((0.55, 0.75, 0.88), 0.35),
    "Doors":             ((0.55, 0.40, 0.28), 1.0),
    "Stair":             ((0.70, 0.56, 0.40), 1.0),
    "Studio-Equipment":  ((0.20, 0.32, 0.45), 1.0),
    "Studio-Zones":      ((0.95, 0.55, 0.20), 0.30),
    "ADU-Furniture":     ((0.62, 0.70, 0.62), 1.0),
    "ADU-Piano":         ((0.07, 0.07, 0.08), 1.0),
}

# interior faces of the exterior walls, and the studio side of the stair partition
_W, _N, _E = EXT_WALL, DEPTH - EXT_WALL, LENGTH - EXT_WALL
_SP = STAIR_X0 - INT_WALL

# ---------------------------------------------------------------------------
# Rooms (for labels and area take-offs). rect = (x0, y0, x1, y1)
# ---------------------------------------------------------------------------
ROOMS = [
    # level, name, rect, subtract-rects
    ("ground", "Print Studio", (_W, _W, _SP, _N),
     [(14.5, _W, 20.375, 7.375), (14.5, 16.0, 24.375, _N)]),
    ("ground", "Wet / Etch Room", (14.875, 16.375, 24.0, _N), []),
    ("ground", "WC", (14.875, _W, 20.0, 7.0), []),
    ("ground", "Entry + Stair", (STAIR_X0, _W, _E, _N), []),
    ("upper", "Living / Kitchen", (_W, _W, _SP, _N),
     [(14.5, _W, 21.0, 8.375), (21.0, _W, _SP, 11.875)]),
    ("upper", "Bedroom", (21.375, _W, _SP, 11.5), []),
    ("upper", "Bath", (14.875, _W, 21.0, 8.0), []),
    ("upper", "Landing", (STAIR_X0, STAIR_Y1, _E, _N), []),
]

LABEL_AT = {  # where to place a room label if not the rect centre
    "Print Studio": (6.5, 4.0),
    "Living / Kitchen": (12.0, 9.5),
    "Bedroom": (25.6, 8.65),
    "Entry + Stair": (33.7, 13.5),
}

LABEL_VERTICAL = {"Entry + Stair"}  # narrow rooms get a rotated label

ZONES = [  # translucent floor patches that show working clearances
    ("Press clearance", (2.5, 8.5, 14.5, 15.5)),
    ("Clean zone", (21.0, 7.5, 31.0, 17.5)),
    ("Dirty zone", (5.0, 18.0, 14.25, _N)),
]


def build():
    E = []
    L, D, W = LENGTH, DEPTH, EXT_WALL

    # --- site & slabs -------------------------------------------------------
    E.append(box("Ground", "Site", -22, -26, -0.55, L + 22, D + 18, -0.5))
    E.append(box("Apron (concrete, at big door)", "Slab", 3.5, -10, -0.5, 13.5, 0, -0.05))
    E.append(box("Path to ADU entry", "Slab", 31.5, -10, -0.5, 35.5, 0, -0.05))
    E.append(box("Ground floor slab (6\" reinforced, for press load)", "Slab",
                 0, 0, -0.5, L, D, 0, level="ground"))

    # --- exterior walls (run full height, openings on both floors) ----------
    u = FLOOR2  # upper floor datum
    south = [
        O(4.5, 12.5, 0, 8, "slider", name="Studio loading door (8' slider)"),
        O(22, 28, 3, 9, name="Studio south window"),
        O(32.0, 35.0, 0, 7, "door", "+b", name="ADU / stair entry door"),
        O(3, 10, u + 1.5, u + 8, name="Living south window"),
        O(16, 19, u + 5, u + 7, name="Bath window"),
        O(24, 29, u + 2.5, u + 7.5, name="Bedroom south window"),
    ]
    north = [
        O(1.5, 5.5, 3.5, 10.5, name="North light window 1"),
        O(7, 11, 3.5, 10.5, name="North light window 2"),
        O(17, 21, 4, 7.5, name="Wet room window"),
        O(26, 30, 3.5, 10.5, name="North light window 3"),
        O(2, 7, u + 2.5, u + 7.5, name="Living north window"),
        O(10, 14, u + 2.5, u + 7.5, name="Dining north window"),
        O(21, 27, u + 3.5, u + 7, name="Kitchen window"),
    ]
    west = [
        O(4, 8, 3, 10.5, name="Studio west window 1"),
        O(11, 15, 3, 10.5, name="Studio west window 2"),
        O(6, 18, u + 2, u + 8, name="Living west window wall"),
    ]
    east = [
        O(9, 13, 5, 9, name="Stair hall window"),
        O(9, 13, u + 2, u + 7, name="Stair hall upper window"),
    ]
    # double-stud walls: sheathing, cellulose and drywall layers, plus both stud rows
    sides = [
        walls.Side("South wall", "x", 0, +1, L, south),
        walls.Side("North wall", "x", D, -1, L, north),
        walls.Side("West wall", "y", 0, +1, D, west),
        walls.Side("East wall", "y", L, -1, D, east),
    ]
    storeys = [(0, FLOOR2 - FLOOR_THICK), (FLOOR2, PLATE)]
    E += walls.build_walls(sides, 0, PLATE, storeys,
                           gables=[("West gable", 0, +1), ("East gable", L, -1)],
                           plate_z=PLATE, ridge_z=RIDGE, depth=D)

    # --- upper floor (stair opening cut out) ---------------------------------
    z0, z1 = FLOOR2 - FLOOR_THICK, FLOOR2
    E.append(box("Upper floor", "Floors", W, W, z0, STAIR_X0, D - W, z1, level="upper"))
    E.append(box("Upper floor at landing", "Floors", STAIR_X0, STAIR_Y1, z0, L - W, D - W, z1,
                 level="upper"))

    # --- roof ------------------------------------------------------------------
    t = ROOF_THICK
    for nm, sgn in (("South roof", 1), ("North roof", -1)):
        y_eave = -EAVE if sgn > 0 else D + EAVE
        z_eave = PLATE - PITCH * EAVE
        poly = [(-RAKE, y_eave, z_eave), (-RAKE, D / 2, RIDGE),
                (-RAKE, D / 2, RIDGE + t), (-RAKE, y_eave, z_eave + t)]
        E.append(prism(nm, "Roof", poly, (L + 2 * RAKE, 0, 0)))

    # --- interior partitions: ground ------------------------------------------
    g = "ground"
    iw = INT_WALL
    E += wall("Stair hall partition (1-hr)", "Walls-Interior", "y", W, D - W,
              STAIR_X0 - iw, STAIR_X0, 0, FLOOR2 - FLOOR_THICK,
              [O(1.0, 3.75, 0, 7, "door", "-b", name="Studio door from stair hall")], g)
    E += wall("WC west wall", "Walls-Interior", "y", W, 7.375, 14.5, 14.5 + iw, 0, 11, level=g)
    E += wall("WC east wall", "Walls-Interior", "y", W, 7.375, 20.0, 20.0 + iw, 0, 11, level=g)
    E += wall("WC north wall", "Walls-Interior", "x", 14.5, 20.375, 7.0, 7.375, 0, 11,
              [O(16, 18.5, 0, 7, "door", "-a", name="WC door")], g)
    E += wall("Wet room south wall", "Walls-Interior", "x", 14.5, 24.375, 16.0, 16.375, 0, 11,
              [O(15.5, 18.5, 0, 7, "door", "+a", name="Wet room door (3')")], g)
    E += wall("Wet room west wall", "Walls-Interior", "y", 16.375, D - W, 14.5, 14.5 + iw, 0, 11,
              level=g)
    E += wall("Wet room east wall", "Walls-Interior", "y", 16.375, D - W, 24.0, 24.0 + iw, 0, 11,
              level=g)

    # --- interior partitions: upper -------------------------------------------
    up = "upper"
    E += wall("Stair enclosure wall (1-hr)", "Walls-Interior", "y", W, D - W,
              STAIR_X0 - iw, STAIR_X0, u, PLATE,
              [O(20.25, 23.0, u, u + 7, "door", "-a", name="ADU front door")], up)
    E += wall("Bedroom west wall", "Walls-Interior", "y", W, 11.875, 21.0, 21.0 + iw, u, PLATE,
              level=up)
    E += wall("Bedroom north wall", "Walls-Interior", "x", 21.0, STAIR_X0 - iw, 11.5, 11.875,
              u, PLATE, [O(22.0, 24.67, u, u + 7, "door", "-a", name="Bedroom door")], up)
    E += wall("Bath west wall", "Walls-Interior", "y", W, 8.375, 14.5, 14.5 + iw, u, PLATE,
              level=up)
    E += wall("Bath north wall", "Walls-Interior", "x", 14.5, 21.0, 8.0, 8.375, u, PLATE,
              [O(17.5, 20.0, u, u + 7, "door", "-a", name="Bath door")], up)

    # --- stair -------------------------------------------------------------------
    sx0, sx1 = STAIR_X0, L - W
    for i in range(RISERS - 1):
        y = STAIR_Y0 + i * TREAD
        E.append(box(f"Tread {i + 1}", "Stair", sx0, y, (i + 1) * RISE - 0.15,
                     sx1, y + TREAD + 0.08, (i + 1) * RISE, level=g if i < 6 else None))
    E.append(prism("Stair stringer", "Stair",
                   [(sx1 - 0.15, STAIR_Y0, 0), (sx1 - 0.15, STAIR_Y1, FLOOR2 - 0.6),
                    (sx1 - 0.15, STAIR_Y1, FLOOR2), (sx1 - 0.15, STAIR_Y0, RISE)],
                   (0.15, 0, 0)))
    E.append(box("Handrail", "Stair", sx0 + 0.05, STAIR_Y0, 3.0, sx0 + 0.2, STAIR_Y1, 3.15))

    # --- studio equipment -----------------------------------------------------------
    s = "Studio-Equipment"
    px, py0, py1 = 9.0, 10.75, 13.25           # press centre / bed edges
    E.append(box("Etching press stand", s, px - 3.5, py0 + 0.25, 0, px + 3.5, py1 - 0.25, 2.8,
                 level=g))
    E.append(box("Etching press bed (30\"x60\", 7' travel)", s, px - 3.5, py0, 2.95,
                 px + 3.5, py1, 3.1, level=g))
    for nm, y in (("Press side frame S", py0 - 0.4), ("Press side frame N", py1)):
        E.append(box(nm, s, px - 1.0, y, 0, px + 1.0, y + 0.4, 4.6, level=g))
    E.append(cylinder_y("Press top roller", s, px, 3.75, 0.55, py0, py1))
    E.append(cylinder_y("Press star wheel", s, px, 3.75, 1.6, py1 + 0.4, py1 + 0.55, sides=6))
    E.append(box("Inking table (glass slab top)", s, 6.0, 20.5, 0, 12.0, _N - 0.1, 3.0, level=g))
    E.append(box("Glass inking slab", "Glazing", 6.5, 20.75, 3.0, 11.5, _N - 0.35, 3.08, level=g))
    E.append(box("Paper prep / blotter table", s, _W + 0.1, 1.5, 0, _W + 3.1, 7.5, 3.0, level=g))
    E.append(box("Paper soaking tray", s, _W + 0.1, 8.0, 0, _W + 3.1, 11.0, 2.6, level=g))
    E.append(box("Deep sink (6' stainless)", s, 15.25, 21.0, 0, 21.25, _N - 0.1, 3.0, level=g))
    E.append(box("Fume hood base", s, 21.75, 20.5, 0, 23.9, _N - 0.1, 3.0, level=g))
    E.append(box("Fume hood (ducted)", s, 21.75, 20.5, 3.0, 23.9, _N - 0.1, 7.0, level=g))
    E.append(box("Fume hood exhaust duct", s, 22.5, 22.0, 7.0, 23.25, 22.75, 11.0))
    E.append(box("Drying rack", s, 25.0, 19.75, 0, 27.5, _N - 0.1, 5.0, level=g))
    E.append(box("Flat files 1", s, _SP - 3.75, 8.0, 0, _SP - 0.1, 12.5, 3.5, level=g))
    E.append(box("Flat files 2", s, _SP - 3.75, 12.5, 0, _SP - 0.1, 17.0, 3.5, level=g))
    E.append(box("Clean work table", s, 21.0, 8.5, 0, 27.0, 12.5, 3.0, level=g))
    E.append(box("WC toilet", s, 18.0, _W + 0.1, 0, 19.5, _W + 2.4, 1.4, level=g))
    E.append(box("WC hand sink", s, 15.0, 3.5, 2.4, 16.5, 5.0, 2.9, level=g))
    for nm, rect in ZONES:
        x0, y0, x1, y1 = rect
        E.append(box(nm, "Studio-Zones", x0, y0, 0.0, x1, y1, 0.02, level=g, zone=True))

    # --- ADU furniture ------------------------------------------------------------------
    f = "ADU-Furniture"
    E.append(box("Kitchen counter", f, 17.0, _N - 2.1, u, 27.75, _N, u + 3, level=up))
    E.append(box("Refrigerator", f, 28.0, _N - 2.5, u, 30.75, _N, u + 6.5, level=up))
    E.append(box("Kitchen island", f, 20.0, 16.5, u, 26.0, 19.0, u + 3, level=up))
    E.append(box("Dining table", f, 9.5, 16.5, u, 14.5, 19.5, u + 2.5, level=up))
    E.append(box("Sofa", f, 2.0, 1.0, u, 9.5, 4.0, u + 2.75, level=up))
    E.append(box("Coffee table", f, 4.0, 5.5, u, 8.0, 7.5, u + 1.5, level=up))
    E.append(box("Queen bed", f, _SP - 6.75, 2.5, u, _SP - 0.1, 7.5, u + 2, level=up))
    E.append(box("Closet", f, 26.5, 9.5, u, STAIR_X0 - iw, 11.5, u + 8, level=up))
    E.append(box("Bathtub / shower", f, 14.9, W, u, 19.9, 3.0, u + 1.75, level=up))
    E.append(box("Toilet", f, 19.4, 4.2, u, 20.95, 6.5, u + 1.4, level=up))
    E.append(box("Vanity", f, 14.9, 4.0, u, 16.7, 7.5, u + 2.8, level=up))
    E.append(box("Stacked washer/dryer", f, STAIR_X0 - iw - 2.5, 12.0, u,
                  STAIR_X0 - iw, 14.5, u + 6, level=up))

    # Steinway Model S baby grand: keyboard to the west, pianist facing east,
    # lid opening to the south toward the sofa; tail 3' clear of the dining table.
    E += steinway_s(kx=4.0, yn=15.2, z=u)
    return E


# Steinway Model S outline, in feet. u runs across the keyboard from the bass
# end (0) to the treble end; v runs from the front of the keys toward the tail.
# 4'-10" (148 cm) wide x 5'-1" (155 cm) long.
STEINWAY_S_WIDTH = 148 / 30.48
STEINWAY_S_LENGTH = 155 / 30.48
_KEYS = 0.55   # how far the keys stand proud of the case front
_S_OUTLINE = [
    (0.00, _KEYS), (0.00, 4.55),                      # straight bass-side spine
    (0.12, 4.82), (0.40, 5.00), (0.80, STEINWAY_S_LENGTH), (1.25, 5.05),  # rounded tail
    (1.62, 4.92), (1.95, 4.68), (2.30, 4.30),         # bentside, concave S-curve
    (2.75, 3.80), (3.30, 3.30), (3.90, 2.80),
    (4.40, 2.25), (4.72, 1.75), (STEINWAY_S_WIDTH, 1.30),
    (STEINWAY_S_WIDTH, _KEYS),                        # straight treble side
]


def steinway_s(kx, yn, z, layer="ADU-Piano"):
    """A Steinway Model S grand with the front of its keys at x = kx, its bass
    side at y = yn, standing on the floor at height z. The pianist faces +x,
    so the treble side (where the lid opens) is to the south."""
    def w(u, v, h):
        return (kx + v, yn - u, z + h)

    def outline(h):
        return [w(u, v, h) for u, v in _S_OUTLINE]

    W_ = STEINWAY_S_WIDTH
    out = [
        prism("Steinway Model S case (ebony)", layer, outline(1.95), (0, 0, 1.15)),
        prism("Steinway Model S lid (closed)", layer, outline(3.10), (0, 0, 0.07), plan=False),
        box("Steinway Model S keyboard (88 keys)", "ADU-Furniture",
            kx, yn - W_ + 0.42, z + 2.15, kx + _KEYS, yn - 0.42, z + 2.36),
        box("Steinway Model S key slip", layer, kx, yn - W_, z + 1.95, kx + _KEYS, yn, z + 2.15),
        box("Steinway Model S cheek (bass)", layer, kx, yn - 0.42, z + 2.15, kx + _KEYS, yn,
            z + 2.55),
        box("Steinway Model S cheek (treble)", layer, kx, yn - W_, z + 2.15, kx + _KEYS,
            yn - W_ + 0.42, z + 2.55),
        box("Steinway Model S music desk", layer, kx + 0.95, yn - 3.6, z + 3.17, kx + 1.05,
            yn - 1.25, z + 4.05),
        box("Steinway Model S pedal lyre", layer, kx + 0.75, yn - 2.75, z, kx + 0.95,
            yn - 2.1, z + 1.95),
    ]
    for nm, (u, v) in (("bass leg", (0.35, 0.85)), ("treble leg", (W_ - 0.35, 0.85)),
                       ("tail leg", (0.75, 4.6))):
        cx, cy, _ = w(u, v, 0)
        out.append(box(f"Steinway Model S {nm}", layer, cx - 0.17, cy - 0.17, z,
                       cx + 0.17, cy + 0.17, z + 1.95))
    out.append(box("Piano bench (30\" x 14\")", layer, kx - 1.75, yn - W_ / 2 - 1.25, z,
                   kx - 0.6, yn - W_ / 2 + 1.25, z + 1.6))
    return out


LEVELS = {
    "ground": {"title": "Ground floor: Print Studio", "floor": 0.0, "cut": 4.0},
    "upper": {"title": "Upper floor: ADU", "floor": FLOOR2, "cut": FLOOR2 + 4.0},
}


def room_area(rect, subtract):
    a = (rect[2] - rect[0]) * (rect[3] - rect[1])
    for r in subtract:
        a -= (r[2] - r[0]) * (r[3] - r[1])
    return a


def summary():
    gross = LENGTH * DEPTH
    stair_strip = (LENGTH - STAIR_X0 + INT_WALL) * DEPTH
    return {
        "footprint": f"{LENGTH:g}' x {DEPTH:g}'",
        "gross_per_floor": gross,
        "studio_gross": gross - stair_strip,
        "adu_gross": gross - stair_strip,
        "shared_stair_gross": stair_strip,
        "studio_clear_height": FLOOR2 - FLOOR_THICK,
        "adu_plate_height": PLATE - FLOOR2,
        "ridge_height": RIDGE + ROOF_THICK,
        "roof_pitch": f"{int(PITCH * 12)}:12",
    }
