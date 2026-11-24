"""Shared numbers and 2D helpers of the flag mechanism: the rotors, the sliders and the plates.

Own copy of decad-gallery models/sevensegment params.go (flag constants, FlagAngle, raise), sliders.go (segmentCentre),
flagframe.go (plan) and the sketch helpers of sketches.go. Lengths are mm, angles degrees.
"""

from __future__ import annotations

import math

from . import frames, ramps
from .constants import (  # noqa: F401  (re-exported: the flag modules take these through fc)
    FACE_Z as FLAG_FACE_Z,
    JOURNAL_RADIUS,
    PIN_LENGTH,
    PIN_OFFSET,
    ROTOR_AXIS_Z,
    ROTOR_HALF_LENGTH,
    ROTOR_HALF_WIDTH,
    SEGMENT_SPAN,
)
from .curves import Arc, Line, Loop, Point
from .truth import SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G

Axes = frames.Axes
Vec3 = frames.Vec3


def segment_centre(s: int) -> tuple[float, float, bool]:
    """The segment's centre in the XY plane and whether its long axis is X [segmentCentre]."""
    h = SEGMENT_SPAN / 2
    return {
        SEG_A: (0.0, SEGMENT_SPAN, True), SEG_G: (0.0, 0.0, True), SEG_D: (0.0, -SEGMENT_SPAN, True),
        SEG_B: (h, h, False), SEG_C: (h, -h, False), SEG_E: (-h, -h, False), SEG_F: (-h, h, False),
    }[s]


def plan(s: int, u: float, sv: float) -> Point:
    """(u, s) about a segment's centre to world XY [plan]."""
    cx, cy, horizontal = segment_centre(s)
    if horizontal:
        return (cx + u, cy + sv)
    return (cx - sv, cy + u)


def raise_(s: int) -> float:
    """The unlit droop built into segment s's pin height: 0 for a, g, d, 0.20 for b, c and 0.25 for e, f [raise]."""
    if s in (SEG_B, SEG_C):
        return 0.20
    if s in (SEG_E, SEG_F):
        return 0.25
    return 0.0


def flag_angle(s: int, theta: float) -> float:
    """Segment s's modeled rotor angle in degrees at camshaft angle theta [FlagAngle]."""
    return math.degrees(math.atan2(ramps.lift(s, theta) - 2.625 + raise_(s), PIN_OFFSET))


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def plane_axes(origin: Vec3, u: Vec3, v: Vec3) -> Axes:
    """The frame of a sketch plane with U = u and V = v: x = u, y = v, z = u x v (the extrusion's +Z)."""
    return (origin, u, v, _cross(u, v))


def yz_axes(at: float) -> tuple[Axes, float]:
    """A profile drawn in (y, z) on the plane x = at, extruded toward +X [slFrame wIsY, Along]. Returns the frame and
    the start z; the extrusion runs from the start for its length."""
    return plane_axes((at, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), 0.0


def xz_axes(at: float, length: float) -> tuple[Axes, float]:
    """A profile drawn in (x, z) on the plane y = at, extruded toward +Y by `length` [slFrame, Against the normal -Y].
    The frame's +Z is world -Y, so the extrusion starts at local z = -length and ends at 0."""
    return plane_axes((0.0, at, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)), -length


def rotor_frame(s: int) -> Axes:
    """The rotor's frame at turn 0: origin on its axis at the middle, local x along s, local y up, local z along u
    [rotorFrame]. a, g, d have u = +X and s = +Y; b, c, e, f have u = +Y and s = -X."""
    cx, cy, horizontal = segment_centre(s)
    u: Vec3 = (1.0, 0.0, 0.0) if horizontal else (0.0, 1.0, 0.0)
    s_axis = _cross((0.0, 0.0, 1.0), u)
    return plane_axes((cx, cy, ROTOR_AXIS_Z), s_axis, (0.0, 0.0, 1.0))


def rotor_axes(s: int, angle: float) -> Axes:
    """The frame that moves a rotor built in its local frame onto the model: the rotor's frame, turned by `angle`
    about its axis (local z, which is the world axis the gallery turns about) [flag + sevensegment BuildParts]."""
    c, sn = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    turn: Axes = ((0.0, 0.0, 0.0), (c, sn, 0.0), (-sn, c, 0.0), (0.0, 0.0, 1.0))
    return frames.compose(rotor_frame(s), turn)


def poly_loop(pts: list[Point] | tuple[Point, ...]) -> Loop:
    return [Line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def rounded_loop(pts: list[Point], radii: dict[int, float]) -> Loop:
    """A closed polygon whose vertices listed in `radii` are rounded by that radius (a sketch fillet). The tangent
    points are shared exactly by the line and the arc they join."""
    n = len(pts)
    enter: list[Point] = list(pts)  # where the line arriving at vertex i ends
    leave: list[Point] = list(pts)  # where the line leaving vertex i starts
    arcs: dict[int, Arc] = {}
    for i, rad in radii.items():
        p0, p1, p2 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
        d1 = (p0[0] - p1[0], p0[1] - p1[1])
        d2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*d1), math.hypot(*d2)
        d1, d2 = (d1[0] / l1, d1[1] / l1), (d2[0] / l2, d2[1] / l2)
        half = math.acos(max(-1.0, min(1.0, d1[0] * d2[0] + d1[1] * d2[1]))) / 2
        t = rad / math.tan(half)
        if t >= min(l1, l2):
            raise ValueError(f"round {rad:g} at vertex {i} is longer than its edge")
        t1 = (p1[0] + d1[0] * t, p1[1] + d1[1] * t)
        t2 = (p1[0] + d2[0] * t, p1[1] + d2[1] * t)
        bis = (d1[0] + d2[0], d1[1] + d2[1])
        nb = math.hypot(*bis)
        dist = rad / math.sin(half)
        centre = (p1[0] + bis[0] / nb * dist, p1[1] + bis[1] / nb * dist)
        cross = (t1[0] - centre[0]) * (t2[1] - centre[1]) - (t1[1] - centre[1]) * (t2[0] - centre[0])
        arcs[i] = Arc(centre, t1, t2) if cross > 0 else Arc(centre, t2, t1)
        enter[i], leave[i] = t1, t2
    out: Loop = []
    for i in range(n):
        j = (i + 1) % n
        if i in arcs:
            out.append(arcs[i])
        out.append(Line(leave[i], enter[j]))
    return out


def rect_loop(x0: float, x1: float, y0: float, y1: float, rad: float = 0.0) -> Loop:
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return rounded_loop(pts, {i: rad for i in range(4)}) if rad > 0 else poly_loop(pts)


def stadium_loop(x0: float, x1: float, rad: float) -> Loop:
    """The pin pocket's outline: a stadium along x from centre x0 to centre x1 of radius rad, centred on y = 0."""
    a1, a2, b1, b2 = (x0, rad), (x0, -rad), (x1, -rad), (x1, rad)
    return [Arc((x0, 0.0), a1, a2), Line(a2, b1), Arc((x1, 0.0), b1, b2), Line(b2, a1)]


def quarter_round(cr: float, cz: float, rad: float, a0: float, a1: float, n: int) -> list[Point]:
    """n + 1 points of the round of radius rad about (cr, cz) from angle a0 to a1 degrees."""
    out: list[Point] = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        out.append((cr + rad * math.cos(a), cz + rad * math.sin(a)))
    return out
