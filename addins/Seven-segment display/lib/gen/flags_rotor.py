"""Outlines of the flag rotor: the tips, the rounded section, the yellow slab, the notches, the pin pockets, the pivot
bores and the flat. Own copy of decad-gallery models/sevensegment rotors.go.

The rotor is built in its local frame: local x is the rotor's x (the face normal at turn 0), local y is up and local z
is the axis u. The prisms are drawn in a plane through the axis that holds the diagonal A = (x + y) / sqrt 2 or
B = (-x + y) / sqrt 2 as its first coordinate and u as its second.
"""

from __future__ import annotations

import math

from . import flags_common as fc
from .constants import FLAG_PIN_RADIUS
from .curves import Loop, Point
from .truth import SEG_A, SEG_D, SEG_G

SQRT2 = math.sqrt(2.0)
AXIS_A = (1 / SQRT2, 1 / SQRT2, 0.0)
AXIS_B = (-1 / SQRT2, 1 / SQRT2, 0.0)
AXIS_Z = (0.0, 0.0, 1.0)

# The shells under the faces and the yellow's inset (0.8), the chamfer legs (0.5, 0.7, 0.8) and the pin pocket's play
# (0.20) are print limits and fits: they keep their size in mm.
ROTOR_EDGE_ROUND = 0.75  # long edges; swept radius 4.875 * sqrt 2 + 0.75 = 7.644
ROTOR_SQUARE_HALF = 15.0  # the section is square for |u| <= 15
ROTOR_TIP_B = 18.525  # prism B's end points, so the pyramid edges stay sharp
ROTOR_FLAT = -3.45  # the black body keeps y >= -3.45
NOTCH_FLOOR = fc.ROTOR_HALF_WIDTH - 0.8  # shells under both faces are 0.8
NOTCH_END = 0.5  # notch end chamfer leg
NOTCH_APEX = 0.8  # apex chamfer leg
SLOT_START = 1.5
SLOT_END = 4.05
SLOT_RADIUS = FLAG_PIN_RADIUS + 0.2  # the pin pocket's radius: the pin's 0.75 plus 0.20
POCKET_FLOOR_ROUND = 0.9  # the pin pocket's floor round
NOTCH_MOUTH = 0.7  # the mouth chamfer of a notch end within 0.8 of the tip slant, on hidden face 315
YELLOW_HALF_WIDTH = fc.ROTOR_HALF_WIDTH - 0.8
YELLOW_TIP_K = fc.ROTOR_HALF_WIDTH + ROTOR_SQUARE_HALF - 0.8  # chamfer |b| + |u| <= K runs 0.8 inside the pyramid edges
YELLOW_TIP_INNER = YELLOW_TIP_K  # the yellow's inner face a >= K - |u| runs 0.8 under the facet
YELLOW_TIP_END = 17.4  # the yellow ends at |u| = 17.4, clear of the pivot bore's mouth
PRISM_LENGTH = 21.0  # every symmetric prism: z from -10.5 to +10.5
SECTION_FROM = -19.5
SECTION_LENGTH = 39.0
FLAT_FROM = -21.0
FLAT_LENGTH = 42.0
_PRISM_HALF_WIDTH = 10.5  # the apex box and the flat under the bottom: x and y from -10.5 to 10.5
_SLAB_EDGE = 9.0  # the slab P1's and the notch slant's far edge


def notches(s: int) -> list[tuple[float, float, float]]:
    """A rotor type's notches as (u0, u1, pocket end) in the rotor's local u. Type A (segments a, g, d) has one notch;
    type B (b, c, e, f) has two, the first used by b and e and the second by c and f [rotorNotches]."""
    if s in (SEG_A, SEG_G, SEG_D):
        return [(-8.4, -0.3, 4.2)]
    return [(-14.1, -6.0, -1.5), (2.4, 10.5, 15.0)]


def plane_a():
    """The frame of the prism plane A: x = axis A, y = local z (u); the extrusion runs along A x Z."""
    return fc.plane_axes((0.0, 0.0, 0.0), AXIS_A, AXIS_Z)


def plane_b():
    return fc.plane_axes((0.0, 0.0, 0.0), AXIS_B, AXIS_Z)


def octagon(c: float, cend: float, uend: float) -> list[Point]:
    """A prism outline in the plane of a diagonal and u: slanted edges at 45 degrees through (5.625, +-15), overshoot to
    c, and end points (+-cend, +-uend)."""
    u0 = ROTOR_SQUARE_HALF - (c - fc.ROTOR_HALF_WIDTH)
    return [(c, -u0), (c, u0), (cend, uend), (-cend, uend), (-c, u0), (-c, -u0), (-cend, -uend), (cend, -uend)]


def tip_prism_a() -> list[Point]:
    return octagon(6.375, 2.25, fc.ROTOR_HALF_LENGTH)


def tip_prism_b() -> list[Point]:
    return octagon(6.375, 2.1, ROTOR_TIP_B)


def section_loop() -> Loop:
    """The rounded square section: four lines at 5.625 from the axis at 45 degrees, filleted ROTOR_EDGE_ROUND."""
    k = fc.ROTOR_HALF_WIDTH * SQRT2
    return fc.rounded_loop([(k, 0.0), (0.0, k), (-k, 0.0), (0.0, -k)], {i: ROTOR_EDGE_ROUND for i in range(4)})


def slab_p1() -> list[Point]:
    """P1 in (a, u): the slab floor, the inner face under the facet, and the end at |u| = YELLOW_TIP_END."""
    e, k = YELLOW_TIP_END, YELLOW_TIP_INNER - YELLOW_TIP_END
    f = NOTCH_FLOOR
    return [(f, -(YELLOW_TIP_INNER - f)), (f, YELLOW_TIP_INNER - f), (k, e), (_SLAB_EDGE, e), (_SLAB_EDGE, -e), (k, -e)]


def slab_p2() -> list[Point]:
    """P2 in (b, u): the slab's width and the chamfer |b| + |u| <= YELLOW_TIP_K, an octagon."""
    w = YELLOW_HALF_WIDTH
    cu, cb = YELLOW_TIP_K - YELLOW_HALF_WIDTH, YELLOW_TIP_K - YELLOW_TIP_END - 0.5
    kk = YELLOW_TIP_K
    return [(w, -cu), (w, cu), (cb, kk - cb), (-cb, kk - cb), (-w, cu), (-w, -cu), (-cb, -(kk - cb)), (cb, -(kk - cb))]


def flat_rect() -> tuple[float, float, float, float]:
    """The flat under the bottom: x -10.5 to 10.5, y -10.5 to ROTOR_FLAT, over the whole length."""
    return (-_PRISM_HALF_WIDTH, _PRISM_HALF_WIDTH, -_PRISM_HALF_WIDTH, ROTOR_FLAT)


def notch_profile(u0: float, u1: float) -> list[Point]:
    """The two slanted profiles of a notch [u0, u1] in (a, u) and (b, u); both prisms use it."""
    f, e = NOTCH_FLOOR, NOTCH_END
    return [(f, u0 + e), (f, u1 - e), (f - e, u1), (-_SLAB_EDGE, u1), (-_SLAB_EDGE, u0), (f - e, u0)]


def apex_top() -> float:
    """The apex box's top y: (2 * floor - apex) / sqrt 2."""
    return (2 * NOTCH_FLOOR - NOTCH_APEX) / SQRT2


def apex_box(u0: float, u1: float) -> tuple[tuple[float, float, float, float], float, float]:
    """The apex box: its rectangle (x0, x1, y0, y1) and the z it starts at and its length, in the rotor frame."""
    return (-_PRISM_HALF_WIDTH, _PRISM_HALF_WIDTH, -_PRISM_HALF_WIDTH, apex_top()), u0 - 1.0, u1 - u0 + 2.0


def pocket(n: tuple[float, float, float]) -> tuple[Loop, float, float]:
    """A pin pocket of a notch: the stadium outline, its start z and its length [pocketTool]."""
    u1, end = n[1], n[2]
    return fc.stadium_loop(SLOT_START, SLOT_END, SLOT_RADIUS), u1 - 0.9, end - u1 + 0.9


PIVOT_BORE_FLOOR = 16.2
PIVOT_FLOOR_ROUND = 0.75
PIVOT_ROOF_TOP = 1.00
PIVOT_MOUTH_R = 1.395


def pivot_bore_meridian(sgn: float) -> list[Point]:
    """One rotor end's revolved bore as an (r, z) section: the floor at u 16.2, a 0.75 round at the floor, the wall of
    radius JOURNAL_RADIUS and the 45 degree countersink to PIVOT_MOUTH_R at the end face, run on past it [pivotBoreTool]."""
    rr, r = PIVOT_FLOOR_ROUND, fc.JOURNAL_RADIUS
    end = fc.ROTOR_HALF_LENGTH
    mouth = end - (PIVOT_MOUTH_R - r)  # where the countersink starts
    pts: list[Point] = [(0.0, PIVOT_BORE_FLOOR), (r - rr, PIVOT_BORE_FLOOR)]
    pts += fc.quarter_round(r - rr, PIVOT_BORE_FLOOR + rr, rr, -90, 0, 6)[1:]
    pts += [(r, mouth), (PIVOT_MOUTH_R + 0.2, end + 0.2), (0.0, end + 0.2)]
    if sgn < 0:
        pts = [(q[0], -q[1]) for q in pts][::-1]
    return pts


def pivot_roof() -> tuple[list[Point], float, float]:
    """One end's teardrop roof: the pentagon (in the frame U = (-1, 1)/sqrt 2, V = (-1, -1)/sqrt 2, V being up in print), the
    start z of the prism for the +u end and its length. For the -u end the start is -(end + 0.2) [pivotRoofTool]."""
    r = fc.JOURNAL_RADIUS
    t = r / SQRT2
    h = r * SQRT2 - PIVOT_ROOF_TOP
    pts: list[Point] = [(0.0, 0.0), (t, t), (h, PIVOT_ROOF_TOP), (-h, PIVOT_ROOF_TOP), (-t, t)]
    end = fc.ROTOR_HALF_LENGTH + 0.2
    return pts, PIVOT_BORE_FLOOR, end - PIVOT_BORE_FLOOR


def pivot_roof_axes(sgn: float) -> fc.Axes:
    """The sketch frame of the roof prism at the end sgn: normal +Z, so the prism runs along +u from its origin."""
    z0 = PIVOT_BORE_FLOOR if sgn > 0 else -(fc.ROTOR_HALF_LENGTH + 0.2)
    return fc.plane_axes((0.0, 0.0, z0), (-1 / SQRT2, 1 / SQRT2, 0.0), (-1 / SQRT2, -1 / SQRT2, 0.0))


def pivot_roof_cut(sgn: float) -> tuple[list[Point], float, float]:
    """The roof prism of the end sgn in the rotor's own frame, ready to cut without a move: the pentagon as (x, y)
    points, the start z and the length. Its sketch frame has normal +Z (`pivot_roof_axes`), so only the pentagon is turned
    in the XY plane."""
    pts, _, length = pivot_roof()
    origin, ex, ey, _ = pivot_roof_axes(sgn)
    xy = [(u * ex[0] + v * ey[0], u * ex[1] + v * ey[1]) for u, v in pts]
    return xy, origin[2], length


def mouth_applies(u0: float) -> bool:
    """A notch whose u0 end lies within 0.8 of the tip slant gets the mouth chamfer [notchTool]."""
    return u0 > -ROTOR_SQUARE_HALF and u0 + ROTOR_SQUARE_HALF < 0.8


def mouth_prism_sections(u0: float):
    """The two prisms of a notch's mouth chamfer cutter [mouthTool], each as (outline, frame, start z, length). P1 is a
    triangle in (b, u) extruded along A; P3 is a wedge in (A, t) with t the 45 degree direction toward (-B, +z), extruded
    30 long about its plane. The tool is P1 x P3."""
    kk = u0 - NOTCH_MOUTH + fc.ROTOR_HALF_WIDTH  # the chamfer plane u - b = kk
    a_lo, top = -1.0, u0 + 1.0
    q = -6.75
    p1 = [(q, q + kk), (q, top), (top - kk, top)]
    ax1 = fc.plane_axes((AXIS_A[0] * a_lo, AXIS_A[1] * a_lo, 0.0), AXIS_B, AXIS_Z)
    k = 1 / SQRT2
    tdir = (AXIS_B[0] * -k, AXIS_B[1] * -k, k)
    w = fc.ROTOR_HALF_WIDTH
    o = (AXIS_B[0] * -w, AXIS_B[1] * -w, -w + kk)
    af = NOTCH_FLOOR - NOTCH_END
    p3 = [(a_lo - 1, -1.0), (af - 1, -1.0), (af + 2, 2.0), (a_lo - 1, 2.0)]
    ax3 = fc.plane_axes(o, AXIS_A, tdir)
    return (p1, ax1, 0.0, NOTCH_FLOOR - a_lo), (p3, ax3, -22.5, 45.0)
