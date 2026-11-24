"""Outlines of the guide, cradle and top plates and their columns, pegs, tubes, bores and windows.

Own copy of decad-gallery models/sevensegment frame.go (slotLoop, guidePlate) and flagframe.go (cradlePlate,
flagTopPlate, columnGuidePlate, boreTool, rootedBox, rootedPost, mouthCone, windows).
"""

from __future__ import annotations

import math

from . import flags_common as fc
from . import flags_pivot as fv
from . import flags_rotor as fr
from .constants import (
    CRADLE_FROM,
    CRADLE_THICK,
    FACE_Z,
    FRONT_INNER_Y,
    GUIDE_FROM,
    GUIDE_THICK,
    GUIDE_TOP,
    LOOSE_FIT,
    PRESS_FIT,
    REAR_INNER_Y,
    RIB_INNER,
    ROTOR_AXIS_Z,
    SEAM,
    STEM_THICKNESS,
    TIGHT_FIT,
    TOP_FROM,
    TOP_THICK,
    PIN_LENGTH,
    WALL_HALF_WIDTH,
)
from .curves import Loop, Point
from .truth import SEG_A, SEG_B, SEG_C, SEG_D, SEG_G

# frame.go: the guide and top plates' y range lies between the walls' inner faces with a seam each side.
PLATE_FROM = FRONT_INNER_Y + SEAM  # -74.0
PLATE_TO = REAR_INNER_Y - SEAM  # 64.25
# GUIDE_FROM, GUIDE_THICK, CRADLE_FROM, CRADLE_THICK, TOP_FROM, TOP_THICK: constants.py
# flagframe.go. Both plates' thicknesses are whole layers.
TUBE_FROM = ROTOR_AXIS_Z - 7.8  # the tubes hang from the top plate to the sliders' heads
BLADE_HOLE_TOP = FACE_Z - 0.8  # the tube roof: 0.8 of top plate over the blade hole
COLUMN_FROM = GUIDE_TOP
COLUMN_TOP = CRADLE_FROM - 1.275  # the columns end this far under the cradle
PEG_RADIUS = 2.25
PEG_HOLE = PEG_RADIUS + PRESS_FIT  # registration hole radius
BORE_RADIUS = 8.094  # 7.644 rotor swept circle + 0.45 Regular-fit play
BORE_ROUND = 1.2
BORE_END = fv.PIVOT_BLOCK_FROM  # the bore's half length along the rotor axis: the end wall; the pivot pocket opens through it
# The bore's cone r + sqrt2 u = BORE_CONE stands 0.40 (the Regular fit) from the rotor's pyramid edge
# r + sqrt2 u = sqrt2 (ROTOR_HALF_WIDTH + ROTOR_SQUARE_HALF): the edge's constant is 8.244 + sqrt2 * 15.531, and the fit
# measured along r is BORE_CONE_FIT, of which the line keeps half beyond the edge's constant.
BORE_CONE_FIT = 0.4 * math.sqrt(3)  # the fit measured along r, sqrt3 times the distance normal to the cone
BORE_CONE = 8.244 + math.sqrt(2) * 15.531 - 0.5 * BORE_CONE_FIT
# How far the cone's line lies beyond the 5.496 + sqrt2 * 10.354 that the end wall's cone end was set from.
BORE_CONE_MOVE = 2.748 + math.sqrt(2) * 5.177 - 0.5 * BORE_CONE_FIT
PASSAGE_FROM = CRADLE_FROM - 1.0
PASSAGE_LENGTH = CRADLE_THICK + 2.4
PASSAGE_ROUND = 0.5
BLADE_HOLE_FROM = TUBE_FROM - 0.4
BLADE_HOLE_ROUND = 0.5
BLADE_ACROSS = 0.25
BLADE_ALONG = 0.35
TUBE_WALL = 0.8
WINDOW_HALF_WIDTH = fc.ROTOR_HALF_WIDTH - 0.8  # 0.8 inside the rotor's faces
WINDOW_CHAMFER = fc.ROTOR_HALF_WIDTH + fr.ROTOR_SQUARE_HALF - 1.1  # 1.1 inside its pyramid edges
WINDOW_END = 17.544
WINDOW_FROM = TOP_FROM - 0.85  # the plane the windows and the T holes are sketched on
WINDOW_LENGTH = FACE_Z + 0.75 - WINDOW_FROM
CONE_DEPTH = 0.8  # the mouth cone over a through hole

# The registration pegs: the first two stand on the guide plate's columns, the last two on the top plate.
COLUMN_PEGS: tuple[Point, Point] = ((18.0, -67.5), (-20.325, 58.5))
TOP_PEGS: tuple[Point, Point] = ((-18.0, -67.5), (21.75, 58.5))
# The columns' half widths (x, y), in the order of COLUMN_PEGS. The rear column keeps LooseFit from the rear top flange
# rib (x -24.6) and rotor a's pyramid never reaches it.
COLUMN_HALF: tuple[Point, Point] = (
    (3.75, 3.75), (RIB_INNER - 20.325 - LOOSE_FIT, 3.75))


def plate_rect() -> tuple[float, float, float, float]:
    return (-WALL_HALF_WIDTH, WALL_HALF_WIDTH, PLATE_FROM, PLATE_TO)


def slot_loop(y: float) -> Loop:
    """The guide slot of the station at y: the stem's section (10.5 by 5.4) with the Tight fit round it, x +-5.5 and y
    -2.95 to +2.95, with its 0.55 corner rounds, and the pin notch, the stem's narrow part with 0.1 each side and the
    pin's length with 0.4, x +-2.8 up to y + 6.1 with 0.5 rounds at its far corners [slotLoop]."""
    sx, sy = 5.25 + TIGHT_FIT, STEM_THICKNESS / 2 + TIGHT_FIT
    nx, ny = 2.8, STEM_THICKNESS / 2 + PIN_LENGTH + 0.4  # 2.8 is 2.7 + 0.1
    v = [(-sx, y - sy), (sx, y - sy), (sx, y + sy), (nx, y + sy), (nx, y + ny), (-nx, y + ny),
         (-nx, y + sy), (-sx, y + sy)]
    return fc.rounded_loop(v, {0: 0.55, 1: 0.55, 2: 0.55, 4: 0.5, 5: 0.5, 7: 0.55})


def cradle_passage(s: int, yi: float) -> tuple[float, float, float, float]:
    """The plan footprint of a slider and its tube plus LooseFit: x0, x1, y0, y1."""
    lf = LOOSE_FIT
    if s in (SEG_A, SEG_G, SEG_D):
        return (-(6.825 + lf), 6.825 + lf, yi - (13.275 + lf), yi + 5.775 + lf)
    if s in (SEG_B, SEG_C):
        return (-(5.25 + lf), 26.85 + lf, yi - (4.275 + lf), yi + 6.075 + lf)
    return (-(29.25 + lf), 5.25 + lf, yi - (4.275 + lf), yi + 6.075 + lf)


def blade_hole(s: int, yi: float) -> tuple[float, float, float, float]:
    """A segment's blade hole through the tube and the plate: the blade plus BLADE_ACROSS across it and BLADE_ALONG
    along it."""
    _, cy, _ = fc.segment_centre(s)
    a, b = BLADE_ACROSS, BLADE_ALONG
    half = STEM_THICKNESS / 2
    if s in (SEG_A, SEG_G, SEG_D):
        return (-5.25 - b, 5.25 + b, cy - 11.7 - a, cy - 10.05 + a)
    if s in (SEG_B, SEG_C):
        return (13.05 - a, 14.7 + a, yi - half - b, yi + 4.5 + b)
    return (-14.7 - a, -13.05 + a, yi - half - b, yi + 4.5 + b)


def tube_footprint(s: int, yi: float) -> tuple[float, float, float, float]:
    """A segment's tube plan x0, x1, y0, y1: it hangs from the top plate and guides the slider's blade."""
    h = blade_hole(s, yi)
    _, cy, _ = fc.segment_centre(s)
    w = TUBE_WALL
    if s in (SEG_A, SEG_G, SEG_D):
        return (h[0] - w, h[1] + w, h[2] - w, cy - 7.35)
    if s in (SEG_B, SEG_C):
        return (h[0] - w, 17.325, h[2] - w, h[3] + w)
    return (-17.325, h[1] + w, h[2] - w, h[3] + w)


def window_loop(s: int) -> Loop:
    """The window octagon of segment s in world XY: |s| <= 4.825, |s| + |u| <= 19.525 and |u| <= 17.544. The long sides
    stand 0.8 inside the rotor's faces and the chamfers 1.1 inside its pyramid edges."""
    hw = WINDOW_HALF_WIDTH
    u0, ue, se = WINDOW_CHAMFER - hw, WINDOW_END, WINDOW_CHAMFER - WINDOW_END
    w = [(u0, hw), (ue, se), (ue, -se), (u0, -hw), (-u0, -hw), (-ue, -se), (-ue, se), (-u0, hw)]
    return fc.poly_loop([fc.plan(s, q[0], q[1]) for q in w])


def bore_meridian() -> list[Point]:
    """A rotor bore's (r, u) section: the cylinder RB = 8.094, a round of 1.2 into the cone that follows the rotor's
    pyramid, and the end wall at u 18.625 to the axis. Symmetric in u [boreTool]. The pivot block's pocket opens through
    the end wall (flags_pivot.pocket_dims)."""
    rb, rd = BORE_RADIUS, BORE_ROUND
    rc = rb - rd
    uc = (BORE_CONE - (rb - rd) - math.sqrt(3) * rd) / math.sqrt(2)
    half = fc.quarter_round(rc, uc, rd, 0, math.degrees(math.atan(math.sqrt(2))), 8)
    # The cone ends on the end wall at r 2.461 plus the cone's move, less sqrt2 per mm of the wall's offset from u 12.5.
    half += [(2.461 + BORE_CONE_MOVE - math.sqrt(2) * (BORE_END - 12.5), BORE_END)]
    pts: list[Point] = [(0.0, -BORE_END)]
    for r, u in reversed(half):
        pts.append((r, -u))
    pts += half
    pts.append((0.0, BORE_END))
    return pts


def bore_axes(s: int, axis_z: float) -> fc.Axes:
    """The frame of a bore tool: its axis (local z) on the segment's rotor axis at height axis_z."""
    cx, cy, horizontal = fc.segment_centre(s)
    if horizontal:  # a rotation of 90 degrees about Y: local z to +X
        return ((cx, cy, axis_z), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))
    return ((cx, cy, axis_z), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))  # -90 degrees about X: z to +Y


def cone_meridian(z_top: float, rh: float = PEG_HOLE, depth: float = CONE_DEPTH) -> list[Point]:
    """The 45 degree mouth over a through hole of radius rh in the face at z_top: the gallery extrudes a circle of
    rh + depth + 0.1 at z_top + 0.1 down by depth + 0.2 with a 45 degree taper; this is that frustum as a section."""
    rad = rh + depth + 0.1
    z1 = z_top + 0.1
    z0 = z1 - (depth + 0.2)
    return [(0.0, z0), (rad - (depth + 0.2), z0), (rad, z1), (0.0, z1)]


def top_peg_meridian() -> list[Point]:
    """The top plate's peg, a (r, z) section about the peg axis; z 0 is the plate's underside."""
    r, z = PEG_RADIUS, -2.4
    return [(0.0, z), (r - 0.3, z), (r, z + 0.3), (r, -0.75), (r + 0.5, 0.0), (r + 0.5, 0.1), (0.0, 0.1)]


def column_peg_meridian() -> list[Point]:
    """The guide column's peg, a (r, z) section about the peg axis; z 0 is the column's top."""
    r, top = PEG_RADIUS, 3.9
    return [(0.0, -0.1), (r + 0.5, -0.1), (r + 0.5, 0.0), (r, 0.5), (r, top - 0.3), (r - 0.3, top), (0.0, top)]


def rooted_box_sections(x0: float, x1: float, y0: float, y1: float, zb: float, z_face: float, ov: float, c: float):
    """A box x [x0, x1], y [y0, y1] from zb up to the face z_face with a 45 degree root of leg c where it meets the face,
    as two prisms to intersect. Returns ((x-z polygon, y plane, length), (y-z polygon, x plane, length))."""
    px = [(x0, zb), (x1, zb), (x1, z_face - c), (x1 + c + ov, z_face + ov), (x0 - c - ov, z_face + ov),
          (x0, z_face - c)]
    py = [(y0, zb), (y1, zb), (y1, z_face - c), (y1 + c + ov, z_face + ov), (y0 - c - ov, z_face + ov),
          (y0, z_face - c)]
    return (px, y0 - c - 1, y1 - y0 + 2 * c + 2), (py, x0 - c - 1, x1 - x0 + 2 * c + 2)


def rooted_post_sections(x0: float, x1: float, y0: float, y1: float, z_face: float, z_top: float, ov: float, c: float):
    """The upward twin of the rooted box: a post standing on the face z_face up to z_top with a 45 degree root."""
    px = [(x0 - c - ov, z_face - ov), (x1 + c + ov, z_face - ov), (x1, z_face + c), (x1, z_top), (x0, z_top),
          (x0, z_face + c)]
    py = [(y0 - c - ov, z_face - ov), (y1 + c + ov, z_face - ov), (y1, z_face + c), (y1, z_top), (y0, z_top),
          (y0, z_face + c)]
    return (px, y0 - c - 1, y1 - y0 + 2 * c + 2), (py, x0 - c - 1, x1 - x0 + 2 * c + 2)

