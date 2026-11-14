"""Every 2D loop of the escapement parts, in part-local coordinates (origin on the part's axis).

Own copy of the section geometry of decad-gallery models/escapement (plates.go, escapewheel.go, anchor.go, pendulum.go,
drive.go, arbors.go, collars.go, builder.go dTool) at e11a188. Arcs are counterclockwise (curves.Arc); a clockwise
piece of the gallery is the counterclockwise arc from its other end. Pieces that meet share one point tuple, so loops
close exactly. The gallery's sketch rounds are tangent arcs computed by fillet.py: each rounded loop is its sharp
pieces plus a map of corner key to radius, and the public loop is fillet.round_loop of both.
"""

from __future__ import annotations

import math
from typing import Sequence

from . import fillet
from .constants import (
    ANCHOR_HUB_ROUND, ANCHOR_PALLET_ROUND, BLOCK_BACK_ROUND, BODY_PRESS_FLAT, BODY_PRESS_RADIUS, CARRIER_ARM_INNER,
    CARRIER_ARM_OUTER, CARRIER_CORE_RADIUS, COLLAR_RADIUS, CRUTCH_ARM_ROUND, DRIVE_PRESS_RADIUS, FLAT_REACH,
    HUB_RING, KEYED_COUNTER_FLAT, KEYED_COUNTER_RADIUS, KEYED_RING_FLAT, PENDULUM_ROD_ROUND, PLATE_BOTTOM,
    PLATE_CORNER, PLATE_LEFT, PLATE_RIGHT, PRESS_FLAT, PRESS_RADIUS, RATCHET_DISC, RATCHET_INNER, RATCHET_OUTER,
    RATCHET_ROUND, RATCHET_TEETH, SLOT_END_RADIUS, SLOT_HIGH, SLOT_LOW, SLOT_RADIUS, SPINE_HALF, SPOKE_HALF,
    TOOTH_ROOT_ROUND, WHEEL_WINDOW_ROUND, WINDOW_BOTTOM, WINDOW_CORNER, WINDOW_INNER, WINDOW_OUTER, WINDOW_ROUND,
    WINDOW_SIDE, WINDOW_TOP,
)
from .curves import Arc, Curve, Line, Loop, Point
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


def _window_pieces(g: Geometry, sx: float) -> tuple[list[Curve], dict[int, float]]:
    """Sharp window on side sx (+1 right, -1 left): 6 lines and 5 arcs, and the round of each inside corner.

    Keys: 4 F, 5 H, 6 I, 7 J, 8 K, 9 L, 10 A [instructions "Window loop"]."""
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

    pieces: list[Curve] = [
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
    return pieces, {key: WINDOW_ROUND for key in range(4, 11)}


def window_loop(g: Geometry, sx: float) -> Loop:
    """Window on side sx with its 1.0 rounds: 6 lines and 12 arcs."""
    return fillet.round_loop(*_window_pieces(g, sx))


def window_rounds(g: Geometry, sx: float) -> list[fillet.Round]:
    """The window's seven rounds in the order F, H, I, J, K, L, A."""
    return fillet.loop_rounds(*_window_pieces(g, sx))


def lip_centres(g: Geometry) -> list[Pt]:
    """Bearing axes O, P, G of the plates. G's x is snapped to 0 (layout leaves 3e-15 from polar)."""
    return [_ORIGIN, g.axis_p, (0.0, g.axis_g[1])]


MOUNT_HOLES: tuple[Pt, ...] = ((-40.0, 90.0), (40.0, 90.0))


def _escape_window_pieces(k: int) -> tuple[list[Curve], dict[int, float]]:
    """Sharp window k of the escape wheel: 2 arcs and 2 lines, and the round of each corner (0 b, 1 c, 2 d, 3 a)."""
    d13, d28 = math.asin(SPOKE_HALF / WINDOW_INNER), math.asin(SPOKE_HALF / WINDOW_OUTER)
    s1 = (90 + 60 * k) * _DEG
    s2 = s1 + 60 * _DEG
    a = polar(WINDOW_INNER, s1 + d13)
    b = polar(WINDOW_INNER, s2 - d13)
    c = polar(WINDOW_OUTER, s2 - d28)
    d = polar(WINDOW_OUTER, s1 + d28)
    pieces: list[Curve] = [Arc(_ORIGIN, a, b), Line(b, c), Arc(_ORIGIN, d, c), Line(d, a)]
    return pieces, {key: WHEEL_WINDOW_ROUND for key in range(4)}


def escape_windows() -> list[Loop]:
    """The six windows of the escape wheel with their 1.0 rounds: 2 lines and 6 arcs each [escapeDisc]."""
    return [fillet.round_loop(*_escape_window_pieces(k)) for k in range(6)]


def escape_window_rounds(k: int) -> list[fillet.Round]:
    """The four rounds of window k in the order b, c, d, a."""
    return fillet.loop_rounds(*_escape_window_pieces(k))


def escape_tooth(g: Geometry) -> Loop:
    """Triangle T, L, B of tooth 0 [escapeTooth]."""
    t, ll, b = g.tooth_tip, g.tooth_l, g.tooth_b
    return [Line(t, ll), Line(ll, b), Line(b, t)]


def _anchor_pieces(g: Geometry) -> tuple[list[Curve], dict[int, float]]:
    """The anchor's 14 sharp pieces about the pallet arbor, relative to P, and its four rounds [anchorOutline].

    Keys: 1 G_E and 4 G_X (pallet rounds), 2 H_E and 3 H_X (hub rounds)."""
    o = _ORIGIN
    pieces: list[Curve] = [
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
    return pieces, {1: ANCHOR_PALLET_ROUND, 4: ANCHOR_PALLET_ROUND, 2: ANCHOR_HUB_ROUND, 3: ANCHOR_HUB_ROUND}


def anchor_outline(g: Geometry) -> Loop:
    """The anchor with its four inside rounds: 8 lines and 10 arcs."""
    return fillet.round_loop(*_anchor_pieces(g))


def anchor_rounds(g: Geometry) -> list[fillet.Round]:
    """The anchor's rounds in the order G_E, H_E, H_X, G_X."""
    return fillet.loop_rounds(*_anchor_pieces(g))


CRUTCH_PIN: tuple[Pt, float] = ((0.0, -45.0), 1.5)


def _crutch_pieces(g: Geometry) -> tuple[list[Curve], dict[int, float]]:
    """Sharp hub, arm and round end of the crutch, relative to P, and the arm roots (0 A_L, 3 A_R) [buildCrutch]."""
    e: Pt = (0.0, -45.0)
    pieces: list[Curve] = [
        Arc(_ORIGIN, g.crutch_ar, g.crutch_al),
        Line(g.crutch_al, g.crutch_bl),
        Arc(e, g.crutch_bl, g.crutch_br),
        Line(g.crutch_br, g.crutch_ar),
    ]
    return pieces, {0: CRUTCH_ARM_ROUND, 3: CRUTCH_ARM_ROUND}


def crutch_outline(g: Geometry) -> Loop:
    """The crutch with both arm roots rounded 2.5: 2 lines and 4 arcs."""
    return fillet.round_loop(*_crutch_pieces(g))


def crutch_rounds(g: Geometry) -> list[fillet.Round]:
    """The crutch's rounds in the order A_L, A_R."""
    return fillet.loop_rounds(*_crutch_pieces(g))


def _pendulum_pieces(g: Geometry) -> tuple[list[Curve], dict[int, float]]:
    """Sharp eye, rod and bob of the pendulum, relative to S, and the rod corners (0 E_L, 1 Q_L, 2 Q_R, 3 E_R)
    [buildPendulum]."""
    bob: Pt = (0.0, -g.params.pendulum_length)
    pieces: list[Curve] = [
        Arc(_ORIGIN, g.pend_er, g.pend_el),
        Line(g.pend_el, g.pend_ql),
        Arc(bob, g.pend_ql, g.pend_qr),
        Line(g.pend_qr, g.pend_er),
    ]
    return pieces, {key: PENDULUM_ROD_ROUND for key in range(4)}


def pendulum_outline(g: Geometry) -> Loop:
    """The pendulum with its four rod corners rounded 4.0: 2 lines and 6 arcs."""
    return fillet.round_loop(*_pendulum_pieces(g))


def pendulum_rounds(g: Geometry) -> list[fillet.Round]:
    """The pendulum's rounds in the order E_L, Q_L, Q_R, E_R."""
    return fillet.loop_rounds(*_pendulum_pieces(g))


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


DFamily = tuple[float, float]  # (arc radius, chord x)

END_D: DFamily = (PRESS_RADIUS, PRESS_FLAT)
BODY_D: DFamily = (BODY_PRESS_RADIUS, BODY_PRESS_FLAT)
DRIVE_D: DFamily = (DRIVE_PRESS_RADIUS, BODY_PRESS_FLAT)
KEYED_COUNTER_D: DFamily = (KEYED_COUNTER_RADIUS, KEYED_COUNTER_FLAT)
KEYED_RING_D: DFamily = (COLLAR_RADIUS, KEYED_RING_FLAT)


def d_section(d: DFamily) -> Loop:
    """D section about the axis: arc of radius r about the origin, chord at x, flat on +X [dTool, dLoop]."""
    r, f = d
    h = math.sqrt(r * r - f * f)
    upper, lower = (f, h), (f, -h)
    return [Arc(_ORIGIN, upper, lower), Line(lower, upper)]


def d_area(d: DFamily) -> float:
    r, f = d
    return math.pi * r * r - _segment_area(r, f)


def press_d() -> Loop:
    """D section of the end press fit: arc radius 2.55, chord at x = 2.05."""
    return d_section(END_D)


def press_d_area() -> float:
    return d_area(END_D)


def _ratchet_triangle_pieces() -> tuple[list[Curve], dict[int, float]]:
    """Sharp ratchet tooth: (11 at 0 deg), (14 at 30 deg), (11 at 30 deg), and the root round at the outer vertex."""
    step = 2 * math.pi / RATCHET_TEETH
    a, c, d = polar(RATCHET_INNER, 0.0), polar(RATCHET_OUTER, step), polar(RATCHET_INNER, step)
    return [Line(a, c), Line(c, d), Line(d, a)], {0: RATCHET_ROUND}


def ratchet_triangle() -> Loop:
    """Ratchet tooth with its 0.5 root round: 3 lines and 1 arc [ratchetToolBody]."""
    return fillet.round_loop(*_ratchet_triangle_pieces())


def ratchet_rounds() -> list[fillet.Round]:
    """The tooth's one round."""
    return fillet.loop_rounds(*_ratchet_triangle_pieces())


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


def _ratchet_tool_pieces() -> tuple[list[Curve], dict[int, float]]:
    """Sharp outline of the union of the disc (r 11.5) and the 12 ratchet triangles, and the root round of each tooth.

    Per tooth k: an arc on r 11.5 from 30k deg to 30k deg + alpha, a line out to (14 at 30(k+1) deg) and a radial
    line in to (11.5 at 30(k+1) deg). The round of tooth k is key 3k + 1."""
    n = RATCHET_TEETH
    step = 2 * math.pi / n
    alpha = ratchet_alpha()
    starts = [polar(RATCHET_DISC, step * k) for k in range(n)]
    out: list[Curve] = []
    for k in range(n):
        x = polar(RATCHET_DISC, step * k + alpha)
        c = polar(RATCHET_OUTER, step * (k + 1))
        nxt = starts[(k + 1) % n]
        out += [Arc(_ORIGIN, starts[k], x), Line(x, c), Line(c, nxt)]
    return out, {3 * k + 1: RATCHET_ROUND for k in range(n)}


def ratchet_tool_outline() -> Loop:
    """The tool outline with a 0.5 root round on each tooth: 24 lines and 24 arcs."""
    return fillet.round_loop(*_ratchet_tool_pieces())


def _pawl_pieces(gangs: Sequence[float]) -> tuple[list[Curve], dict[int, float]]:
    """Sharp pawl layer: the core, both slots and both pawls as one loop of nine pieces per pawl [pawlLayer].

    For pawl j with base angle g: core arc, slot-end round, arm inner arc, two lines to the tip, tip arc, contact
    line, arm outer arc, back line. Keys 9j + 6 (contact to outer arc) is the tooth root, 9j + 8 (back to the next
    core arc) is the block back."""
    n = len(gangs)

    def at(r: float, a: float) -> Pt:
        return (r * math.cos(a), r * math.sin(a))

    slot = SLOT_END_RADIUS / (CARRIER_CORE_RADIUS + SLOT_END_RADIUS)
    corners = [at(CARRIER_CORE_RADIUS, g + 10 * _DEG) for g in gangs]
    pieces: list[Curve] = []
    rounds: dict[int, float] = {}
    for j, g in enumerate(gangs):
        c = g - slot
        prev = corners[(j + n - 1) % n]
        slot_start, slot_top = at(CARRIER_CORE_RADIUS, c), at(CARRIER_ARM_INNER, c)
        centre = at(CARRIER_CORE_RADIUS + SLOT_END_RADIUS, c)
        p4, p5 = at(CARRIER_ARM_INNER, g - 120 * _DEG), at(CARRIER_ARM_OUTER, g - 120 * _DEG)
        p6, p7 = at(12.5, g - 116 * _DEG), at(12.5, g - 112 * _DEG)
        p8, p9 = at(CARRIER_ARM_OUTER, g - 112 * _DEG), at(CARRIER_ARM_OUTER, g + 10 * _DEG)
        rounds[9 * j + 6] = TOOTH_ROOT_ROUND
        rounds[9 * j + 8] = BLOCK_BACK_ROUND
        pieces += [
            Arc(_ORIGIN, prev, slot_start), Arc(centre, slot_top, slot_start), Arc(_ORIGIN, p4, slot_top),
            Line(p4, p5), Line(p5, p6), Arc(_ORIGIN, p6, p7), Line(p7, p8), Arc(_ORIGIN, p8, p9),
            Line(p9, corners[j]),
        ]
    return pieces, rounds


def pawl_layer(gangs: Sequence[float]) -> Loop:
    """The pawl layer with its rounds: for two pawls 8 lines and 14 arcs."""
    return fillet.round_loop(*_pawl_pieces(gangs))


def pawl_rounds(gangs: Sequence[float]) -> list[fillet.Round]:
    """The layer's rounds in the order pawl 1 tooth root, pawl 1 block back, pawl 2 tooth root, ..."""
    return fillet.loop_rounds(*_pawl_pieces(gangs))


# (radius, z) polygons with a point on the axis at each end [arbors.go *ArborPoints, pinPoints].
_MERIDIANS: dict[str, tuple[Pt, ...]] = {
    "escape_arbor": ((0, -5), (2.5, -5), (2.5, 0.25), (2.8, 0.25), (2.8, 24.0), (3.7, 24.0), (3.7, 27.75),
                     (2.5, 27.75), (2.5, 33), (0, 33)),
    "pallet_arbor": ((0, -5), (2.5, -5), (2.5, 0.25), (3.7, 0.25), (3.7, 20.95), (2.8, 20.95), (2.8, 27.75),
                     (2.5, 27.75), (2.5, 38.25), (0, 38.25)),
    "great_wheel_arbor": ((0, -5), (2.5, -5), (2.5, 0.25), (3.7, 0.25), (3.7, 3.25), (3.05, 3.25), (3.05, 17.45),
                          (2.8, 17.45), (2.8, 27.75), (2.5, 27.75), (2.5, 38.25), (0, 38.25)),
    "suspension_pin": ((0, 31.05), (2.5, 31.05), (2.5, 34), (3.7, 34), (3.7, 39.80), (2.5, 39.80), (2.5, 46.75),
                       (0, 46.75)),
}
_MERIDIANS = {k: tuple((float(r), float(z)) for r, z in v) for k, v in _MERIDIANS.items()}

# Flat boxes cut from each arbor: (flat x, z0, z1) [arbors.go *Flats].
ARBOR_FLATS: dict[str, tuple[tuple[float, float, float], ...]] = {
    "escape_arbor": ((2.55, 0.20, 23.95),),
    "pallet_arbor": ((2.55, 21.0, 27.80), (2.0, 34.25, 39.25)),
    "great_wheel_arbor": ((2.55, 5.25, 27.80), (2.0, 34.25, 39.25)),
    "suspension_pin": ((2.0, 30.05, 33.95), (2.0, 45.30, 47.75)),
}


def arbor_meridian(part: str) -> Loop:
    """Closed loop of lines in (r, z) of an arbor or the suspension pin. Raises KeyError for another part."""
    pts = _MERIDIANS[part]
    return [Line(pts[i - 1], pts[i]) for i in range(1, len(pts))] + [Line(pts[-1], pts[0])]


def flat_box(flat_x: float) -> tuple[Pt, Pt]:
    """Corners of the flat box about the axis: x in [flat_x, 3.5], y in [-3.5, 3.5] [flatBox]."""
    return ((flat_x, -FLAT_REACH), (FLAT_REACH, FLAT_REACH))
