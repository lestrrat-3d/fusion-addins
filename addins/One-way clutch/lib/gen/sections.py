"""The 2D sections the clutch's sketches draw, as pure loops (millimeters).

Own copy of the sketches of decad-gallery models/onewayclutch sketches.go. Sections on the XY plane use model x and y.
A section revolved about the Z axis is a meridian in (radius, z) = sketch (u, v).

Every hub and ring section is built in the counter-clockwise layout and mirrored by `mirror_loop` when the freewheel
direction is clockwise: each point (x, y) maps to (sign * x, y) and each arc's start and end swap.
Deviation: no sketch dimensions or geometric constraints; every curve is placed at computed coordinates, so each
tangent point and fillet is computed here (docs/onewayclutch/deviations.md).
"""

from __future__ import annotations

import math

from .constants import (
    BACK_PLATE_THICKNESS,
    BAND_FROM,
    BAND_TO,
    COVER_FROM,
    EAR_ANGLES,
    EAR_RADIUS,
    EAR_ROUND,
    HEAD_GAP,
    LOCK_ANGLE,
    PAWLS,
    RECESS,
    RING_CHAMFER,
    RING_FROM,
    RING_TO,
    ROOT_ROUND,
    SLOT_ANGLE,
    TEETH,
    TIP_ROUND,
    WEB_ANGLE,
    WEB_ROUND,
)
from .curves import Arc, Line, Loop, Point
from .params import Dimensions, polar

ORIGIN: Point = (0.0, 0.0)


def rotate(p: Point, deg: float) -> Point:
    """p turned by deg degrees about the origin. A turn of 0 returns p itself."""
    if deg == 0:
        return p
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def _m(p: Point) -> Point:
    return (-p[0], p[1])


def mirror_loop(loop: Loop) -> Loop:
    """The loop mirrored in the plane x = 0. An arc keeps its counter-clockwise sense by swapping its ends."""
    out: list[Line | Arc] = []
    for c in loop:
        if isinstance(c, Line):
            out.append(Line(_m(c.start), _m(c.end)))
        else:
            out.append(Arc(_m(c.center), _m(c.end), _m(c.start)))
    return out


def layout(loop: Loop, sign: float) -> Loop:
    """The loop of the counter-clockwise layout for the direction's sign (+1 as drawn, -1 mirrored)."""
    return list(loop) if sign > 0 else mirror_loop(loop)


def minor_arc(center: Point, p: Point, q: Point) -> Arc:
    """The counter-clockwise arc about center between p and q that sweeps at most 180 degrees."""
    cross = (p[0] - center[0]) * (q[1] - center[1]) - (p[1] - center[1]) * (q[0] - center[0])
    return Arc(center, p, q) if cross >= 0 else Arc(center, q, p)


def fillet(a: Point, corner: Point, b: Point, radius: float) -> tuple[Point, Point, Point]:
    """Round the corner between the lines corner-a and corner-b with a circle of `radius` inside their angle.

    Returns (tangent point on corner-a, tangent point on corner-b, centre)."""
    ua = (a[0] - corner[0], a[1] - corner[1])
    ub = (b[0] - corner[0], b[1] - corner[1])
    la, lb = math.hypot(*ua), math.hypot(*ub)
    ua = (ua[0] / la, ua[1] / la)
    ub = (ub[0] / lb, ub[1] / lb)
    cos_t = ua[0] * ub[0] + ua[1] * ub[1]
    theta = math.acos(max(-1.0, min(1.0, cos_t)))  # the angle between the two lines at the corner
    d = radius / math.tan(theta / 2)
    ta = (corner[0] + ua[0] * d, corner[1] + ua[1] * d)
    tb = (corner[0] + ub[0] * d, corner[1] + ub[1] * d)
    bis = (ua[0] + ub[0], ua[1] + ub[1])
    lbis = math.hypot(*bis)
    h = radius / math.sin(theta / 2)
    center = (corner[0] + bis[0] / lbis * h, corner[1] + bis[1] / lbis * h)
    return ta, tb, center


# --- Plates and the D bore -------------------------------------------------------------------------------------------


def bore_loop(dm: Dimensions) -> Loop:
    """The D bore: an arc of r_b about the axis the long way round through -Y, closed by its flat at y = f_b."""
    rb, fb = dm.bore_radius, dm.bore_flat
    w = math.sqrt(rb * rb - fb * fb)
    q1, q2 = (-w, fb), (w, fb)
    return [Arc(ORIGIN, q1, q2), Line(q2, q1)]


def bolt_hole_centers(radius: float, angles: tuple[float, ...]) -> list[Point]:
    return [polar(radius, a) for a in angles]


def meridian(pts: tuple[tuple[float, float], ...]) -> Loop:
    """A closed loop of lines through the (radius, z) vertices."""
    return [Line(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]


Pts = tuple[tuple[float, float], ...]


def ring_back_points(dm: Dimensions) -> Pts:
    """The vertices (r, z) of the ring's back counterbore tool, a closed meridian: the plate's rim in a counterbore, a 45
    degree lead-in at the ring's end face and a 45 degree cone that holds the ring axially
    [Dimensions.RingBackTool]."""
    tip, root, counter = dm.tooth_tip, dm.tooth_root, dm.ring_counter
    return (
        (tip - 1.5, RING_FROM - 1), (counter + 1.5, RING_FROM - 1), (counter, RING_FROM + RING_CHAMFER),
        (counter, BAND_FROM - (counter - root)), (root, BAND_FROM), (tip - 1.5, BAND_FROM),
    )


def ring_front_points(dm: Dimensions) -> Pts:
    """The front counterbore tool's vertices: the back one mirrored in the hub's mid-plane [Dimensions.RingFrontTool]."""
    tip, root, counter = dm.tooth_tip, dm.tooth_root, dm.ring_counter
    return (
        (tip - 1.5, RING_TO + 1), (counter + 1.5, RING_TO + 1), (counter, RING_TO - RING_CHAMFER),
        (counter, BAND_TO + (counter - root)), (root, BAND_TO), (tip - 1.5, BAND_TO),
    )


def back_plate_points(dm: Dimensions) -> Pts:
    """The back plate's inner-face tool's vertices: the boss, its bevel, the recessed annulus and the 45 degree cone to
    the rim [Dimensions.BackPlateInner]."""
    b, p, t, z = dm.boss_radius, dm.plate_radius, dm.tooth_root, BACK_PLATE_THICKNESS
    return (
        (b - 0.9, z + 1), (b - 0.9, z - 0.6), (b - 0.1, z - RECESS), (t, z - RECESS),
        (p + 1, z - RECESS - (p + 1 - t)), (p + 1, z + 1),
    )


def cover_points(dm: Dimensions) -> Pts:
    """The cover's inner-face tool's vertices [Dimensions.CoverInner]."""
    b, p, t, z = dm.boss_radius, dm.plate_radius, dm.tooth_root, COVER_FROM
    return (
        (b - 0.9, z - 1), (b - 0.9, z + 0.6), (b - 0.1, z + RECESS), (t, z + RECESS),
        (p + 1, z + RECESS + (p + 1 - t)), (p + 1, z - 1),
    )


def ring_back_tool(dm: Dimensions) -> Loop:
    return meridian(ring_back_points(dm))


def ring_front_tool(dm: Dimensions) -> Loop:
    return meridian(ring_front_points(dm))


def back_plate_tool(dm: Dimensions) -> Loop:
    return meridian(back_plate_points(dm))


def cover_tool(dm: Dimensions) -> Loop:
    return meridian(cover_points(dm))


# --- Ring ------------------------------------------------------------------------------------------------------------


def ear_centers(dm: Dimensions) -> list[Point]:
    return [polar(dm.ear_circle, a) for a in EAR_ANGLES]


def ring_outline(dm: Dimensions) -> Loop:
    """The ring's outer loop: the outside arc of dm.ring_outer with three ears. Each ear has parallel sides 2 *
    EAR_RADIUS apart, tangent to a full end round of EAR_RADIUS about dm.ear_circle, and meets the outside in a round
    of EAR_ROUND. Built for an ear on +Y, then turned onto each ear angle."""
    outer, circle = dm.ring_outer, dm.ear_circle
    # Fillet centre, in the ear's frame (axis +Y, +X on the clockwise side of the ear).
    fy = math.sqrt((outer + EAR_ROUND) ** 2 - (EAR_RADIUS + EAR_ROUND) ** 2)
    fc = (EAR_RADIUS + EAR_ROUND, fy)
    scale = outer / math.hypot(*fc)
    t_out_r = (fc[0] * scale, fc[1] * scale)  # on the outside circle, clockwise side
    t_side_r = (EAR_RADIUS, fy)  # on the side line
    end_r = (EAR_RADIUS, circle)
    end_l = (-EAR_RADIUS, circle)
    ear: dict[str, Point] = {
        "out_r": t_out_r, "side_r": t_side_r, "end_r": end_r, "end_l": end_l,
        "side_l": (-t_side_r[0], t_side_r[1]), "out_l": (-t_out_r[0], t_out_r[1]),
        "fc_r": fc, "fc_l": (-fc[0], fc[1]), "end_c": (0.0, circle),
    }
    turned = [{k: rotate(v, a - 90.0) for k, v in ear.items()} for a in EAR_ANGLES]
    loop: list[Line | Arc] = []
    n = len(turned)
    for i, e in enumerate(turned):
        nxt = turned[(i + 1) % n]
        loop.append(minor_arc(e["fc_r"], e["out_r"], e["side_r"]))  # fillet, clockwise side
        loop.append(Line(e["side_r"], e["end_r"]))
        loop.append(Arc(e["end_c"], e["end_r"], e["end_l"]))  # the end round, a half circle over the ear's tip
        loop.append(Line(e["end_l"], e["side_l"]))
        loop.append(minor_arc(e["fc_l"], e["side_l"], e["out_l"]))  # fillet, counter-clockwise side
        loop.append(Arc(ORIGIN, e["out_l"], nxt["out_r"]))  # the outside between this ear and the next
    return loop


def tooth_loop(dm: Dimensions) -> Loop:
    """The ring's 18-tooth void as one closed loop, counter-clockwise layout [toothLoop].

    Lock face j lies on the radial axis at phi_j = LOCK_ANGLE + 20 j, from Q_j = dm.tooth_root at phi_j in to P_j =
    dm.tooth_tip at phi_j; the ramp of tooth j runs from P_j to Q_(j+1). Each Q_j is rounded by ROOT_ROUND."""
    pitch = 360.0 / TEETH
    phi = [LOCK_ANGLE + pitch * (j % TEETH) for j in range(TEETH)]
    p = [polar(dm.tooth_tip, a) for a in phi]
    q = [polar(dm.tooth_root, a) for a in phi]
    ramp_end: list[Point] = []  # tangent point of the round at Q_j on the ramp j-1
    lock_start: list[Point] = []  # tangent point of the round at Q_j on the lock face j
    centers: list[Point] = []
    for j in range(TEETH):
        ta, tb, c = fillet(p[(j - 1) % TEETH], q[j], p[j], ROOT_ROUND)
        ramp_end.append(ta)
        lock_start.append(tb)
        centers.append(c)
    loop: list[Line | Arc] = []
    for j in range(TEETH):
        loop.append(minor_arc(centers[j], ramp_end[j], lock_start[j]))
        loop.append(Line(lock_start[j], p[j]))
        loop.append(Line(p[j], ramp_end[(j + 1) % TEETH]))
    return loop


# --- Hub -------------------------------------------------------------------------------------------------------------


def hub_outline(dm: Dimensions) -> Loop:
    """The hub's outer loop in the counter-clockwise layout: three pawls, pawl k turned by 120 k degrees."""
    core, inner, outer = dm.core_radius, dm.arm_inner, dm.arm_outer
    rn = core + WEB_ROUND
    off = math.degrees(math.asin(WEB_ROUND / rn))
    core_tangent = polar(core, WEB_ANGLE - off)  # where the web root round meets the core arc
    web_center = polar(rn, WEB_ANGLE - off)
    web_tangent = polar(math.sqrt(rn * rn - WEB_ROUND * WEB_ROUND), WEB_ANGLE)
    web_end = polar(outer, WEB_ANGLE)
    n = dm.ramp_normal
    flank_tangent = (dm.tip_center[0] + TIP_ROUND * n[0], dm.tip_center[1] + TIP_ROUND * n[1])
    lock_tangent = (HEAD_GAP + 0.0, dm.tip_center[1])
    arm_in = polar(inner, SLOT_ANGLE)
    slot_center = polar(inner - dm.slot_width / 2, SLOT_ANGLE)
    slot_core = polar(core, SLOT_ANGLE)

    def turn(pt: Point, k: int) -> Point:
        return rotate(pt, 360.0 / PAWLS * (k % PAWLS))

    loop: list[Line | Arc] = []
    for k in range(PAWLS):
        loop.append(minor_arc(turn(web_center, k), turn(core_tangent, k), turn(web_tangent, k)))
        loop.append(Line(turn(web_tangent, k), turn(web_end, k)))
        loop.append(Arc(ORIGIN, turn(web_end, k), turn(dm.flank_end, k)))
        loop.append(Line(turn(dm.flank_end, k), turn(flank_tangent, k)))
        loop.append(minor_arc(turn(dm.tip_center, k), turn(flank_tangent, k), turn(lock_tangent, k)))
        loop.append(Line(turn(lock_tangent, k), turn(dm.lock_end, k)))
        loop.append(Arc(ORIGIN, turn(arm_in, k), turn(dm.lock_end, k)))
        loop.append(Arc(turn(slot_center, k), turn(slot_core, k), turn(arm_in, k)))
        loop.append(Arc(ORIGIN, turn(slot_core, k), turn(core_tangent, k + 1)))
    return loop
