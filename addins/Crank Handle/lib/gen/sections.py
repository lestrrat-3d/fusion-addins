"""The 2D sections the crank's sketches draw, as pure loops (millimeters).

Own copy of the sketches of decad-gallery models/crankhandle sketches.go. Sections on the XY plane use model x and y.
A section that is revolved about the Z axis is in (radius, z) = sketch (u, v) and is built at the origin: the pin and
the handle are moved to the pin axis afterwards.
"""

from __future__ import annotations

import math

from .constants import (
    ARM_RADIUS,
    CLAMP_END_R,
    CONE_ANGLE,
    CROSS_FLAT,
    HANDLE_FROM,
    HANDLE_PROFILE,
    HEAD_FROM,
    HEAD_LENGTH,
    HEAD_R,
    ROOT_R,
    SHANK_FROM,
    SHANK_R,
    SHANK_TO,
    SLIT_IN_BORE,
    SLIT_WIDTH,
)
from .curves import Arc, Line, Loop, Point
from .params import Dimensions, Params

_FLAT_REACH = 3.0  # a flat tool's reach past the shank's surface
_FLAT_HALF_WIDTH = SHANK_R + 1


def arm_outline(p: Params, dm: Dimensions) -> Loop:
    """The arm's outline on the back face, counterclockwise: an arc of radius ARM_RADIUS about the pin axis, the two
    sides at x = +-ARM_RADIUS tangent to it down to y = side_end, a CLAMP_CORNER_R corner arc on each side and the
    CLAMP_END_R end arc tangent to both corners from inside. Every join is tangent. The pin hole is a separate circle."""
    top = (0.0, p.throw)
    r2 = (ARM_RADIUS, p.throw)
    l2 = (-ARM_RADIUS, p.throw)
    s_r = (ARM_RADIUS, dm.side_end)
    s_l = (-ARM_RADIUS, dm.side_end)
    c_r = dm.corner_center()
    c_l = (-c_r[0], c_r[1])
    c_b = dm.end_center()
    # The corner arc meets the end arc on the line through their centres, CLAMP_END_R from the end arc's centre.
    d = math.hypot(c_r[0] - c_b[0], c_r[1] - c_b[1])
    p_r = (c_b[0] + (c_r[0] - c_b[0]) * CLAMP_END_R / d, c_b[1] + (c_r[1] - c_b[1]) * CLAMP_END_R / d)
    p_l = (-p_r[0], p_r[1])
    return [
        Arc(top, r2, l2),
        Line(l2, s_l),
        Arc(c_l, s_l, p_l),
        Arc(c_b, p_l, p_r),
        Arc(c_r, p_r, s_r),
        Line(s_r, r2),
    ]


def slit_tool(dm: Dimensions) -> Loop:
    """The slit's cutter: x within +-SLIT_WIDTH/2 from 2 mm past the end arc up to SLIT_IN_BORE past the bore's wall,
    closed there by a half circle of radius SLIT_WIDTH/2."""
    half = SLIT_WIDTH / 2
    y0 = -dm.reach - 2
    y1 = -dm.bore_radius + SLIT_IN_BORE
    yc = y1 - half
    a, b, c, d = (half, y0), (half, yc), (-half, yc), (-half, y0)
    return [Line(a, b), Arc((0.0, yc), b, c), Line(c, d), Line(d, a)]


def bore_tool(dm: Dimensions) -> Loop:
    """The D bore's cutter: an arc of radius r_b about the axis the long way round through -Y, closed by its flat at
    y = f_b toward the pin."""
    rb, fb = dm.bore_radius, dm.bore_flat
    w = math.sqrt(rb * rb - fb * fb)
    q1, q2 = (-w, fb), (w, fb)
    return [Arc((0.0, 0.0), q1, q2), Line(q2, q1)]


def flat_box(throw: float, z: float, side: float) -> tuple[Point, Point, float, float]:
    """One of a cross bolt's double flats: everything beyond CROSS_FLAT from the pin axis on the side (+1 for +Y, -1
    for -Y), over the flat's length along the pin. Returns the rectangle's two corners on the XY plane, the start z and
    the length."""
    v0, v1 = CROSS_FLAT, CROSS_FLAT + _FLAT_REACH
    if side < 0:
        v0, v1 = -v1, -v0
    return ((-_FLAT_HALF_WIDTH, throw + v0), (_FLAT_HALF_WIDTH, throw + v1), z - 3.25, 6.5)


def _lines(pts: list[Point]) -> Loop:
    return [Line(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]


def pin_meridian() -> Loop:
    """The pin's turned part, (radius, z) about its own axis: a cone of half angle CONE_ANGLE from radius ROOT_R at
    SHANK_FROM out to the shank, the shank to SHANK_TO, a cone out to the head at HEAD_FROM, and the head."""
    slope = math.tan(math.radians(CONE_ANGLE))
    top = HEAD_FROM + HEAD_LENGTH
    return _lines([
        (0.0, SHANK_FROM), (ROOT_R, SHANK_FROM), (SHANK_R, SHANK_FROM + (SHANK_R - ROOT_R) / slope),
        (SHANK_R, SHANK_TO), (HEAD_R, HEAD_FROM), (HEAD_R, top), (0.0, top),
    ])


def handle_meridian() -> Loop:
    """The handle's meridian, (radius, z) about the pin axis, z measured from the arm's back face."""
    return _lines([(r, HANDLE_FROM + z) for z, r in HANDLE_PROFILE])
