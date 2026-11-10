"""M2 bolt and nut geometry and the gearbox's fastener pocket sizes.

Own copy of decad-gallery models/m2bolt (m2bolt.go), models/m2nut (m2nut.go) and models/planetarygearbox
fasteners.go at a800069. Thread is not modeled, as in the gallery.
"""

from __future__ import annotations

import math

from .curves import Line, Loop, Point, rotate

# m2bolt.go
SHANK_DIAMETER = 2.0
HEAD_DIAMETER = 3.8
HEAD_HEIGHT = 2.0
SOCKET_ACROSS_FLATS = 1.5
SOCKET_DEPTH = 1.0
HEAD_CHAMFER_WIDTH = 0.2
HEAD_CHAMFER_ANGLE = 30.0  # degrees
UNDERHEAD_RADIUS = 0.1
TIP_CHAMFER = 0.25
DRILL_POINT_ANGLE = 118.0  # degrees
DRILL_POINT_BASE_RADIUS = 0.7
PILOT_DEPTH = 0.1
SOCKET_CUTTER_RISE = 0.5
# m2nut.go
NUT_BORE_DIAMETER = 2.0
NUT_ACROSS_FLATS = 4.0
NUT_THICKNESS = 1.6
NUT_BEARING_DIAMETER = 3.48
NUT_CHAMFER_ANGLE = 30.0  # degrees
NUT_CHAMFER_MARGIN = 0.2
NUT_CHAMFER_REACH = 0.3
# fasteners.go
HEAD_CLEARANCE = 0.3  # radial gap between a bolt head and its pocket, and between the shank and its hole
NUT_CLEARANCE = 0.2  # gap between a nut and its cavity: radial beyond the nut's corners, axial at each face
MIN_BOLT_HOLE_DIAMETER = SHANK_DIAMETER + 2 * HEAD_CLEARANCE  # fasteners.go minBoltHoleDiameter
COVER_FLOOR = 1.0
POCKET_MARGIN = 1.0
FASTENER_LENGTH = 6.0
FASTENER_STOCK = 1.0
NUT_ROOF = 1.0


def nut_across_corners() -> float:
    return NUT_ACROSS_FLATS / math.cos(math.pi / 6)


def head_pocket_diameter() -> float:
    return HEAD_DIAMETER + 2 * HEAD_CLEARANCE


def nut_pocket_diameter() -> float:
    """Diameter of the round nut cavity: the circle through the nut's corners plus NUT_CLEARANCE radially."""
    return 2 * (NUT_ACROSS_FLATS / math.sqrt(3) + NUT_CLEARANCE)


def nut_cavity_height() -> float:
    return NUT_THICKNESS + 2 * NUT_CLEARANCE


def nut_angle(angle: float) -> float:
    """Turns a nut (corners on X) so its flats face the bolt radius."""
    return angle - math.pi / 2


# Deviation from decad-gallery: hexagons are six lines from this pure function, not SketchLines.addScribedPolygon,
# so the corner positions stay in tested code (README deviations).
def hexagon_loop(flats: float, center: Point = (0.0, 0.0), angle: float = 0.0) -> Loop:
    """Regular hexagon of the given across-flats size as six lines; corner 0 sits on +X at angle 0."""
    corners: list[Point] = []
    for k in range(6):
        q = rotate((flats / math.sqrt(3), 0.0), angle + k * math.pi / 3)
        corners.append((center[0] + q[0], center[1] + q[1]))
    return [Line(corners[k], corners[(k + 1) % 6]) for k in range(6)]


def bolt_section(length: float) -> Loop:
    """Half section of the bolt as (radius, height) lines; origin = centre of the head's underside, head along +v."""
    sh, hh = SHANK_DIAMETER / 2, HEAD_DIAMETER / 2
    socket_floor = HEAD_HEIGHT - SOCKET_DEPTH - PILOT_DEPTH
    pts: list[Point] = [
        (0.0, -length),
        (sh - TIP_CHAMFER, -length),
        (sh, -length + TIP_CHAMFER),
        (sh, 0.0),
        (hh, 0.0),
        (hh, HEAD_HEIGHT - HEAD_CHAMFER_WIDTH * math.tan(math.radians(HEAD_CHAMFER_ANGLE))),
        (hh - HEAD_CHAMFER_WIDTH, HEAD_HEIGHT),
        (DRILL_POINT_BASE_RADIUS, HEAD_HEIGHT),
        (DRILL_POINT_BASE_RADIUS, socket_floor),
        (0.0, socket_floor - DRILL_POINT_BASE_RADIUS / math.tan(math.radians(DRILL_POINT_ANGLE / 2))),
    ]
    return [Line(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]


def nut_chamfer_section(upper: bool) -> Loop:
    """Triangle (radius, height) revolved to cut one chamfer of the nut."""
    slope = math.tan(math.radians(NUT_CHAMFER_ANGLE))
    outer = nut_across_corners() / 2 + NUT_CHAMFER_MARGIN
    br = NUT_BEARING_DIAMETER / 2
    sign, face = (-1.0, NUT_THICKNESS) if upper else (1.0, 0.0)
    start: Point = (br - NUT_CHAMFER_REACH / slope, face - sign * NUT_CHAMFER_REACH)
    foot: Point = (outer, start[1])
    corner: Point = (outer, face + sign * (outer - br) * slope)
    return [Line(start, foot), Line(foot, corner), Line(corner, start)]
