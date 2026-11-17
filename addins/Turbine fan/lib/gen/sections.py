"""The 2D sections the fan's sketches draw, as pure loops (millimeters).

Own copy of the sketches of decad-gallery models/turbinefan sketches.go. Sections on the XY plane use model x and y.
A section that is revolved about the Z axis is in (radius, z) = sketch (u, v). Each tool is drawn at the origin with its
axis on +Z and moved onto its site afterwards (commands/turbinefan/parts.py).
"""

from __future__ import annotations

import math

from .constants import COUNTERBORE_ROUND
from .curves import Arc, Line, Loop, Point
from .fasteners import HEAD_POCKET_RADIUS, NUT_CAVITY_RADIUS, STOCK
from .params import Dimensions

COUNTERBORE_CHORDS = 8


def bore_loop(dm: Dimensions) -> Loop:
    """The D bore: an arc of radius r_b about the axis counterclockwise from (w_b/2, -f_b) over +Y to (-w_b/2, -f_b),
    closed by its flat."""
    w = dm.bore_flat_width / 2
    q_r: Point = (w, -dm.bore_flat)
    q_l: Point = (-w, -dm.bore_flat)
    return [Arc((0.0, 0.0), q_r, q_l), Line(q_l, q_r)]


def nut_slot_points(reach: float) -> list[Point]:
    """The corners A to E of the nut slot's outline in its own plane: a hexagon about the origin with its corners on the
    circle of radius NUT_CAVITY_RADIUS and one corner at -U, whose two sides toward +U run on as straight walls out to
    u = reach [nutSlotSketch]."""
    rad = NUT_CAVITY_RADIUS
    h = rad * math.sqrt(3) / 2
    return [(reach, -h), (-rad / 2, -h), (-rad, 0.0), (-rad / 2, h), (reach, h)]


def nut_slot_loop(reach: float) -> Loop:
    pts = nut_slot_points(reach)
    return [Line(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]


def nut_slot_round_corners() -> list[Point]:
    """The three hexagon corners B, C and D, whose edges along the extrusion are rounded by NUT_SLOT_ROUND."""
    return nut_slot_points(0.0)[1:4]


def counterbore_meridian(dm: Dimensions) -> list[tuple[float, float]]:
    """(t, r) vertices of the set screw's counterbore: from the floor (t = 0, at rho_f) a quarter round of radius
    COUNTERBORE_ROUND in eight chords up to the head pocket's radius, then straight out through the round face
    [counterboreTool]."""
    rr, rc = COUNTERBORE_ROUND, HEAD_POCKET_RADIUS
    pts: list[tuple[float, float]] = [(0.0, 0.0)]
    for i in range(COUNTERBORE_CHORDS + 1):
        t = math.pi - (math.pi / 2) * i / COUNTERBORE_CHORDS
        pts.append((rr + rr * math.cos(t), rc - rr + rr * math.sin(t)))
    out = dm.size.hub_radius + STOCK - dm.counterbore_floor
    pts.extend([(out, rc), (out, 0.0)])
    return pts
