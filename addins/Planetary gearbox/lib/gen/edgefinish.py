"""Surface edge finishing of the ring, the covers and the carriers.

Own copy of decad-gallery models/planetarygearbox edgefinish.go (largeFaceArea, outerLoop, windowsAndRim,
radiusAbout) and the finishFaceEdges calls in gears.go buildRing, cover.go buildCover and carrier.go buildCarrier at
791aeb2. The gallery chamfers both ring faces in one call because decad cannot chamfer the ring twice; Fusion chamfers
each face in its own feature. The removed volumes are the add-in's own; the gallery tests none.
"""

from __future__ import annotations

import dataclasses
import math

from .curves import Arc, Circle, Line, Loop
from .dims import Dims
from .ears import ring_outline
from .params import COVER_SPOKES, RING_MARGIN, Params
from .sections import carrier_plate_outline

LARGE_FACE_AREA = 400.0  # mm^2 [edgefinish.go largeFaceArea]
LIP_RADIUS_TOL = 1e-3  # mm [cover.go buildCover lip rule]
OUTER = "outer"  # [edgefinish.go outerLoop]
WINDOWS_AND_RIM = "windows_and_rim"  # [edgefinish.go windowsAndRim]
LIP = "lip"  # [cover.go buildCover lip]


@dataclasses.dataclass(frozen=True)
class FinishPlane:
    z: float  # part-local height of the large flat face (mm)
    rule: str  # OUTER | WINDOWS_AND_RIM | LIP
    loops: int  # loops the rule keeps at the gallery's topology


def finish_planes(p: Params, d: Dims, part: str) -> list[FinishPlane]:
    """Planes to chamfer on a part, in the gallery's order of the finishFaceEdges calls."""
    if part == "ring":
        return [FinishPlane(RING_MARGIN, OUTER, 1), FinishPlane(RING_MARGIN + d.ring_length, OUTER, 1)]
    if part == "cover":
        return [
            FinishPlane(0.0, LIP, 2 + COVER_SPOKES),
            FinishPlane(p.cover_thickness, WINDOWS_AND_RIM, 1 + COVER_SPOKES),
        ]
    if part == "carrier":
        return [FinishPlane(0.0, OUTER, 1), FinishPlane(p.carrier_thickness, OUTER, 1)]
    return []


def is_large_face(area: float) -> bool:
    """True when a flat face of area (mm^2) is large enough to be finished."""
    return area >= LARGE_FACE_AREA


def keep_loop(rule: str, is_outer: bool, edge_count: int, start_radius: float, d: Dims) -> bool:
    """True when the rule keeps a loop: its outer flag, edge count and the start radius of its first edge."""
    if rule == OUTER:
        return is_outer
    if rule == WINDOWS_AND_RIM:
        return is_outer or edge_count > 1
    if rule == LIP:
        return is_outer or edge_count > 1 or (edge_count == 1 and abs(start_radius - d.lip / 2) < LIP_RADIUS_TOL)
    raise ValueError(f"unknown edge finishing rule {rule}")


def _rim(r: float, c: float, inside: bool) -> float:
    """Volume removed by a chamfer of setback c round a circle of radius r (Pappus).

    inside: the material is inside the circle (outer rim); otherwise it is outside (a hole)."""
    return c * c / 2 * 2 * math.pi * (r - c / 3 if inside else r + c / 3)


def _perimeter(loop: Loop) -> float:
    """Length of a loop of lines and arcs (mm)."""
    total = 0.0
    for c in loop:
        if isinstance(c, Line):
            total += math.hypot(c.end[0] - c.start[0], c.end[1] - c.start[1])
        elif isinstance(c, Arc):
            r = math.hypot(c.start[0] - c.center[0], c.start[1] - c.center[1])
            a0 = math.atan2(c.start[1] - c.center[1], c.start[0] - c.center[0])
            a1 = math.atan2(c.end[1] - c.center[1], c.end[0] - c.center[0])
            total += r * ((a1 - a0) % (2 * math.pi))
        else:
            raise ValueError("unsupported curve in a chamfered outline")
    return total


def window_chamfer_volume(d: Dims, c: float) -> float:
    """Volume removed by chamfering one cover window loop on one face (rim arc, hub arc, two spoke edges)."""
    h = d.arm / 2
    hub = d.cover_hub / 2
    rim = d.rim_inner
    hub_x = math.sqrt(hub * hub - h * h)
    rim_x = math.sqrt(rim * rim - h * h)
    length = rim_x - hub_x
    th_rim = 2 * math.pi / COVER_SPOKES - 2 * math.asin(h / rim)
    th_hub = 2 * math.pi / COVER_SPOKES - 2 * math.asin(h / hub)
    a_rim = math.acos(h / rim)
    a_hub = math.pi - math.acos(h / hub)
    # Rim arc: material outside it. Hub arc: material inside it. Corners add c^3/3 * cot(alpha / 2) each.
    edges = c * c / 2 * (2 * length + th_rim * (rim + c / 3) + th_hub * (hub - c / 3))
    corners = c**3 / 3 * (2 / math.tan(a_rim / 2) + 2 / math.tan(a_hub / 2))
    return edges + corners


def edge_chamfer_volume(p: Params, d: Dims, part: str) -> float:
    """Total volume (mm^3) the edge chamfers remove from a part."""
    c = p.edge_chamfer
    if part == "ring":
        outline = ring_outline(p, d)
        if isinstance(outline, Circle):
            return 2 * _rim(d.ring_outer, c, True)
        # The outline turns through 2 pi in all, so the smooth-edge rule c^2/2 (P - c/3 * 2 pi) holds. The six
        # corners where an ear meets the outer circle add under c^3 each, far below the check's tolerance.
        return 2 * c * c / 2 * (_perimeter(outline) - 2 * math.pi * c / 3)
    if part == "cover":
        return (
            2 * _rim(d.ring_outer, c, True)
            + _rim(d.lip / 2, c, False)
            + 2 * COVER_SPOKES * window_chamfer_volume(d, c)
        )
    if part == "carrier":
        # Two faces; the outline is convex and tangent-continuous, so its total turning is 2 pi.
        return c * c * (_perimeter(carrier_plate_outline(p, d)) - 2 * math.pi * c / 3)
    return 0.0
