"""Every 2D loop of the escapement parts, in part-local coordinates (origin on the part's axis).

Own copy of the section geometry of decad-gallery models/escapement (plates.go, escapewheel.go, anchor.go, pendulum.go,
drive.go, arbors.go) at 0067d30. Arcs are counterclockwise (curves.Arc); a clockwise piece of the gallery is the
counterclockwise arc from its other end. Pieces that meet share one point tuple, so loops close exactly.
"""

from __future__ import annotations

import math

from .constants import (
    FLAT_REACH, FLAT_X, HUB_RING, PLATE_BOTTOM, PLATE_CORNER, PLATE_LEFT, PLATE_RIGHT,
    PRESS_FLAT, PRESS_RADIUS, RATCHET_DISC, RATCHET_INNER, RATCHET_OUTER, RATCHET_TEETH, SLOT_HIGH,
    SLOT_LOW, SLOT_RADIUS, SPINE_HALF, SPOKE_HALF, WINDOW_BOTTOM, WINDOW_CORNER, WINDOW_INNER, WINDOW_OUTER,
    WINDOW_SIDE, WINDOW_TOP,
)
from .curves import Arc, Line, Loop, Point
from .layout import Geometry, polar

Pt = Point
_ORIGIN: Pt = (0.0, 0.0)
_DEG = math.pi / 180


def plate_outline(top: float) -> Loop:
    """Rounded rectangle x in [-58, 58], y in [-96, top], corner radius 10 [roundedRect]."""
    x0, x1, y0, y1, rc = PLATE_LEFT, PLATE_RIGHT, PLATE_BOTTOM, top, PLATE_CORNER
    c1, c2, c3, c4 = (x0 + rc, y0 + rc), (x1 - rc, y0 + rc), (x1 - rc, y1 - rc), (x0 + rc, y1 - rc)
    a1s, a1e = (x0, y0 + rc), (x0 + rc, y0)
    a2s, a2e = (x1 - rc, y0), (x1, y0 + rc)
    a3s, a3e = (x1, y1 - rc), (x1 - rc, y1)
    a4s, a4e = (x0 + rc, y1), (x0, y1 - rc)
    return [
        Arc(c1, a1s, a1e), Line(a1e, a2s),
        Arc(c2, a2s, a2e), Line(a2e, a3s),
        Arc(c3, a3s, a3e), Line(a3e, a4s),
        Arc(c4, a4s, a4e), Line(a4e, a1s),
    ]


def window_loop(g: Geometry, sx: float) -> Loop:
    """Window on side sx (+1 right, -1 left): 6 lines and 5 arcs [instructions "Window loop"]."""
    py, gy = g.axis_p[1], g.axis_g[1]
    h = math.sqrt(HUB_RING * HUB_RING - SPINE_HALF * SPINE_HALF)
    fx = math.sqrt(HUB_RING * HUB_RING - (WINDOW_TOP - py) ** 2)

    def pt(x: float, y: float) -> Pt:
        return (sx * x, y)

    cx = WINDOW_SIDE - WINDOW_CORNER  # 38
    cy0, cy1 = WINDOW_BOTTOM + WINDOW_CORNER, WINDOW_TOP - WINDOW_CORNER  # -76, 56
    a, b = pt(SPINE_HALF, WINDOW_BOTTOM), pt(cx, WINDOW_BOTTOM)
    c, d = pt(WINDOW_SIDE, cy0), pt(WINDOW_SIDE, cy1)
    e, f = pt(cx, WINDOW_TOP), pt(fx, WINDOW_TOP)
    hp, i = pt(SPINE_HALF, py - h), pt(SPINE_HALF, h)
    j, k = pt(SPINE_HALF, -h), pt(SPINE_HALF, gy + h)
    ll = pt(SPINE_HALF, gy - h)
    c1, c2 = pt(cx, cy0), pt(cx, cy1)
    hub_p, hub_o, hub_g = (0.0, py), _ORIGIN, (0.0, gy)

    def arc(centre: Pt, frm: Pt, to: Pt) -> Arc:
        # The gallery's piece runs clockwise on the right and counterclockwise on the left.
        return Arc(centre, to, frm) if sx > 0 else Arc(centre, frm, to)

    return [
        Line(a, b),
        arc(c1, c, b),
        Line(c, d),
        arc(c2, e, d),
        Line(e, f),
        arc(hub_p, f, hp),
        Line(hp, i),
        arc(hub_o, i, j),
        Line(j, k),
        arc(hub_g, k, ll),
        Line(ll, a),
    ]


def lip_centres(g: Geometry) -> list[Pt]:
    """Bearing axes O, P, G of the plates. G's x is snapped to 0 (layout leaves 3e-15 from polar)."""
    return [_ORIGIN, g.axis_p, (0.0, g.axis_g[1])]


MOUNT_HOLES: tuple[Pt, ...] = ((-40.0, 90.0), (40.0, 90.0))


def escape_windows() -> list[Loop]:
    """The six windows of the escape wheel: 2 arcs and 2 lines each [escapeDisc]."""
    out: list[Loop] = []
    d13, d28 = math.asin(SPOKE_HALF / WINDOW_INNER), math.asin(SPOKE_HALF / WINDOW_OUTER)
    for k in range(6):
        s1 = (90 + 60 * k) * _DEG
        s2 = s1 + 60 * _DEG
        a = polar(WINDOW_INNER, s1 + d13)
        b = polar(WINDOW_INNER, s2 - d13)
        c = polar(WINDOW_OUTER, s2 - d28)
        d = polar(WINDOW_OUTER, s1 + d28)
        out.append([Arc(_ORIGIN, a, b), Line(b, c), Arc(_ORIGIN, d, c), Line(d, a)])
    return out


def escape_tooth(g: Geometry) -> Loop:
    """Triangle T, L, B of tooth 0 [escapeTooth]."""
    t, ll, b = g.tooth_tip, g.tooth_l, g.tooth_b
    return [Line(t, ll), Line(ll, b), Line(b, t)]


def anchor_outline(g: Geometry) -> Loop:
    """The anchor's 14 pieces about the pallet arbor, relative to P [anchorOutline]."""
    o = _ORIGIN
    return [
        Line(g.ce, g.fe),
        Arc(o, g.ge, g.fe),
        Line(g.he, g.ge),
        Arc(o, g.he, g.hx),
        Line(g.hx, g.gx),
        Arc(o, g.cx, g.gx),
        Line(g.cx, g.fx),
        Arc(o, g.fx, g.kx),
        Line(g.kx, g.mx),
        Line(g.mx, g.nx),
        Arc(o, g.nx, g.ne),
        Line(g.ne, g.me),
        Line(g.me, g.ke),
        Arc(o, g.ke, g.ce),
    ]


CRUTCH_PIN: tuple[Pt, float] = ((0.0, -45.0), 1.5)


def crutch_outline(g: Geometry) -> Loop:
    """Hub, arm and round end of the crutch, relative to P [buildCrutch]."""
    e: Pt = (0.0, -45.0)
    return [
        Arc(_ORIGIN, g.crutch_ar, g.crutch_al),
        Line(g.crutch_al, g.crutch_bl),
        Arc(e, g.crutch_bl, g.crutch_br),
        Line(g.crutch_br, g.crutch_ar),
    ]


def pendulum_outline(g: Geometry) -> Loop:
    """Eye, rod and bob of the pendulum, relative to S [buildPendulum]."""
    bob: Pt = (0.0, -g.params.pendulum_length)
    return [
        Arc(_ORIGIN, g.pend_er, g.pend_el),
        Line(g.pend_el, g.pend_ql),
        Arc(bob, g.pend_ql, g.pend_qr),
        Line(g.pend_qr, g.pend_er),
    ]


def crutch_slot() -> Loop:
    """Stadium of the crutch slot, relative to S: arc centres (0, -61.25) and (0, -56.75), radius 1.75."""
    r = SLOT_RADIUS
    low, high = (0.0, SLOT_LOW), (0.0, SLOT_HIGH)
    a, b = (r, SLOT_LOW), (r, SLOT_HIGH)
    c, d = (-r, SLOT_HIGH), (-r, SLOT_LOW)
    return [Line(a, b), Arc(high, b, c), Line(c, d), Arc(low, d, a)]


def _segment_area(r: float, floor: float) -> float:
    """Area of the part of the disc of radius r beyond the line x = floor."""
    return r * r * math.acos(floor / r) - floor * math.sqrt(r * r - floor * floor)


def press_d() -> Loop:
    """D section about the axis: arc radius 2.55, chord at x = 2.05, flat on +X [dTool]."""
    r = PRESS_RADIUS
    f = PRESS_FLAT
    h = math.sqrt(r * r - f * f)
    upper, lower = (f, h), (f, -h)
    return [Arc(_ORIGIN, upper, lower), Line(lower, upper)]


def press_d_area() -> float:
    return math.pi * PRESS_RADIUS**2 - _segment_area(PRESS_RADIUS, PRESS_FLAT)


def ratchet_triangle() -> Loop:
    """Ratchet tooth: (11 at 0 deg), (13.5 at 30 deg), (11 at 30 deg) [ratchetToolBody]."""
    step = 2 * math.pi / RATCHET_TEETH
    a, c, d = polar(RATCHET_INNER, 0.0), polar(RATCHET_OUTER, step), polar(RATCHET_INNER, step)
    return [Line(a, c), Line(c, d), Line(d, a)]


def ratchet_alpha() -> float:
    """Angle where the triangle's long side crosses the disc radius 11.5."""
    step = 2 * math.pi / RATCHET_TEETH
    a, c = polar(RATCHET_INNER, 0.0), polar(RATCHET_OUTER, step)
    dx, dy = c[0] - a[0], c[1] - a[1]
    # |a + t d|^2 = R^2, the root in (0, 1).
    qa = dx * dx + dy * dy
    qb = 2 * (a[0] * dx + a[1] * dy)
    qc = a[0] ** 2 + a[1] ** 2 - RATCHET_DISC**2
    t = (-qb + math.sqrt(qb * qb - 4 * qa * qc)) / (2 * qa)
    return math.atan2(a[1] + t * dy, a[0] + t * dx)


def ratchet_tool_outline() -> Loop:
    """Outline of the union of the disc (r 11.5) and the 12 ratchet triangles.

    Per tooth k: an arc on r 11.5 from 30k deg to 30k deg + alpha, a line out to (13.5 at 30(k+1) deg) and a radial
    line in to (11.5 at 30(k+1) deg)."""
    n = RATCHET_TEETH
    step = 2 * math.pi / n
    alpha = ratchet_alpha()
    starts = [polar(RATCHET_DISC, step * k) for k in range(n)]
    out: Loop = []
    for k in range(n):
        x = polar(RATCHET_DISC, step * k + alpha)
        c = polar(RATCHET_OUTER, step * (k + 1))
        nxt = starts[(k + 1) % n]
        out += [Arc(_ORIGIN, starts[k], x), Line(x, c), Line(c, nxt)]
    return out


def pawl_loop(gang: float) -> Loop:
    """Pawl loop whose base angle is gang [pawlLoop]."""
    o = _ORIGIN

    def at(r: float, a: float) -> Pt:
        return (r * math.cos(a), r * math.sin(a))

    g = gang
    p1, p2, p3 = at(7.0, g + 10 * _DEG), at(7.0, g), at(9.0, g)
    p4, p5 = at(9.0, g - 120 * _DEG), at(10.5, g - 120 * _DEG)
    p6, p7 = at(12.5, g - 116 * _DEG), at(12.5, g - 112 * _DEG)
    p8, p9 = at(10.5, g - 112 * _DEG), at(10.5, g + 10 * _DEG)
    return [
        Arc(o, p2, p1), Line(p2, p3), Arc(o, p4, p3), Line(p4, p5), Line(p5, p6),
        Arc(o, p6, p7), Line(p7, p8), Arc(o, p8, p9), Line(p9, p1),
    ]


# (radius, z) polygons with a point on the axis at each end [arbors.go].
_MERIDIANS: dict[str, tuple[Pt, ...]] = {
    "escape_arbor": ((0, -5), (2.5, -5), (2.5, 25.05), (3.7, 25.05), (3.7, 27.75), (2.5, 27.75), (2.5, 33), (0, 33)),
    "pallet_arbor": ((0, -5), (2.5, -5), (2.5, 19.95), (3.7, 19.95), (3.7, 20.95), (2.5, 20.95), (2.5, 37.2),
                     (0, 37.2)),
    "great_wheel_arbor": ((0, -5), (2.5, -5), (2.5, 0.25), (3.7, 0.25), (3.7, 1.25), (2.5, 1.25), (2.5, 37.2),
                          (0, 37.2)),
    "suspension_pin": ((0, 31.05), (2.5, 31.05), (2.5, 34), (3.7, 34), (3.7, 38.75), (2.5, 38.75), (2.5, 45.70),
                       (0, 45.70)),
}
_MERIDIANS = {k: tuple((float(r), float(z)) for r, z in v) for k, v in _MERIDIANS.items()}

# z spans of the flat boxes cut from each arbor.
ARBOR_FLATS: dict[str, tuple[Pt, ...]] = {
    "escape_arbor": ((0.5, 25.0),),
    "pallet_arbor": ((21.0, 27.75), (34.25, 38.2)),
    "great_wheel_arbor": ((5.25, 27.75), (34.25, 38.2)),
    "suspension_pin": ((30.05, 33.95), (44.25, 46.70)),
}


def arbor_meridian(part: str) -> Loop:
    """Closed loop of lines in (r, z) of an arbor or the suspension pin. Raises KeyError for another part."""
    pts = _MERIDIANS[part]
    return [Line(pts[i - 1], pts[i]) for i in range(1, len(pts))] + [Line(pts[-1], pts[0])]


def flat_box() -> tuple[Pt, Pt]:
    """Corners of the flat box about the axis: x in [2.0, 3.5], y in [-3.5, 3.5]."""
    return ((FLAT_X, -FLAT_REACH), (FLAT_REACH, FLAT_REACH))
