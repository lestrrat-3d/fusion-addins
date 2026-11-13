"""M2 bolt and nut geometry and the escapement's fastener sites and tool spans.

Own copy of decad-gallery models/m2bolt (m2bolt.go) and models/m2nut (m2nut.go), unchanged since the gearbox port, and
of internal/m2fastener plus models/escapement plates.go `sites` at 3a4f9d8. Thread is not modeled, as in the gallery.
Spans are model z (low, high) with the shank toward -Z from a head top at z 34.
"""

from __future__ import annotations

import math

from .constants import BOLT_LENGTH, HEAD_TOP, NUT_CAVITY_AT
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
# m2fastener.go and plates.go
HEAD_CLEARANCE = 0.3  # radial gap between a bolt head and its pocket, and between the shank and its hole
NUT_CLEARANCE = 0.2  # gap between a nut and its cavity: radial beyond the nut's corners, axial at each face
HOLE_RADIUS = SHANK_DIAMETER / 2 + HEAD_CLEARANCE
HEAD_POCKET_RADIUS = HEAD_DIAMETER / 2 + HEAD_CLEARANCE
HEAD_POCKET_DEPTH = HEAD_HEIGHT
NUT_CAVITY_RADIUS = NUT_ACROSS_FLATS / math.sqrt(3) + NUT_CLEARANCE
NUT_CAVITY_HEIGHT = NUT_THICKNESS + 2 * NUT_CLEARANCE
STOCK = 1.0  # a tool's reach past a face it opens
PILLARS: tuple[Point, ...] = ((-50.0, 74.0), (50.0, 74.0), (-50.0, -88.0), (50.0, -88.0))

Span = tuple[float, float]


def hole_span() -> Span:
    """Clearance hole tool: from STOCK above the head top to STOCK past the bolt tip."""
    return (HEAD_TOP - (HEAD_POCKET_DEPTH + BOLT_LENGTH) - STOCK, HEAD_TOP + STOCK)


def pocket_tool_span() -> Span:
    return (HEAD_TOP - HEAD_POCKET_DEPTH, HEAD_TOP + STOCK)


def cavity_span() -> Span:
    return (HEAD_TOP - NUT_CAVITY_AT - NUT_CAVITY_HEIGHT, HEAD_TOP - NUT_CAVITY_AT)


def bolt_tip_z() -> float:
    return HEAD_TOP - HEAD_POCKET_DEPTH - BOLT_LENGTH


def nut_span() -> Span:
    """Nut z range: NUT_CLEARANCE inside each face of the cavity."""
    top = HEAD_TOP - NUT_CAVITY_AT - NUT_CLEARANCE
    return (top - NUT_THICKNESS, top)


def nut_across_corners() -> float:
    return NUT_ACROSS_FLATS / math.cos(math.pi / 6)


# Deviation: hexagons are six lines from this pure function, not SketchLines.addScribedPolygon,
# so the corner positions stay in tested code (docs/escapement/deviations.md).
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
