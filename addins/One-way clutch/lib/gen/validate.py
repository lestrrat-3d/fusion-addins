"""Clutch input validation and the derived dimensions.

Own copy of decad-gallery models/onewayclutch params.go Validate and Derive.

Deviation: messages are the gallery's without the `onewayclutch: ` prefix, because the dialog shows them on its own
(docs/onewayclutch/deviations.md).
"""

from __future__ import annotations

import math

from .constants import (
    ADAPTER_SHAFT_GAP,
    ARM_THICKNESS,
    BASE_CORE_RADIUS,
    BOLT_WALL,
    BORE_CLEARANCE_MAX,
    BORE_CLEARANCE_MIN,
    BOSS_STEP,
    COUNTER_STEP,
    EAR_OFFSET,
    EAR_RADIUS,
    HEAD_GAP,
    HUB_CHAMFER_MARGIN,
    LOCK_ANGLE,
    LOOSE_FIT,
    MAX_HUB_CHAMFER,
    MIN_SLOT_MARGIN,
    MIN_SLOT_WIDTH,
    REGULAR_FIT,
    RING_WALL,
    TEETH,
    TIP_ROUND,
    TOOTH_DEPTH,
)
from .fasteners import HEAD_POCKET_RADIUS, HOLE_RADIUS, NUT_CAVITY_RADIUS, Site
from .params import (
    DIRECTIONS,
    SHAFTS,
    Dimensions,
    Params,
    Vec2,
    direction_sign,
    frame_is_valid,
    lookup_shaft,
    make_sites,
    polar,
)
from .report import fmt_num


class ValidationError(ValueError):
    pass


def derive_pawl(
    tooth_tip: float, tooth_root: float, arm_inner: float, arm_outer: float
) -> tuple[Vec2, Vec2, float, float, Vec2, Vec2, float, float, float, Vec2]:
    """Pawl 0's head from the seated tooth gap [params.go derivePawl]. Returns apex, tip_center, head_reach,
    head_travel, flank_end, lock_end, ramp_angle, flank_distance, ramp_distance, ramp_normal.

    The gap is bounded by the lock face at LOCK_ANGLE and the previous tooth's ramp, from P (tooth_tip one pitch before
    the lock face) to Q (tooth_root on the lock face)."""
    pitch = 360.0 / TEETH
    p = polar(tooth_tip, LOCK_ANGLE - pitch)
    q = polar(tooth_root, LOCK_ANGLE)
    ramp = (q[0] - p[0], q[1] - p[1])
    length = math.hypot(*ramp)
    ramp = (ramp[0] / length, ramp[1] / length)
    ramp_angle = math.degrees(math.atan2(ramp[1], ramp[0]))
    n = (ramp[1], -ramp[0])  # the ramp's unit normal pointing away from the axis
    if n[0] * p[0] + n[1] * p[1] < 0:
        n = (-n[0], -n[1])
    ramp_distance = n[0] * p[0] + n[1] * p[1]
    flank_distance = ramp_distance - HEAD_GAP
    x = HEAD_GAP  # the lock line is x = HEAD_GAP (for LOCK_ANGLE 90 degrees)
    apex = (x, (flank_distance - n[0] * x) / n[1])
    cx = x + TIP_ROUND
    tip_center = (cx, (flank_distance - TIP_ROUND - n[0] * cx) / n[1])
    head_reach = math.hypot(*tip_center) + TIP_ROUND
    head_travel = head_reach - tooth_tip
    lock_end = (x, math.sqrt(arm_inner * arm_inner - x * x))
    # H_f: the flank meets the circle arm_outer; take the root nearer the apex.
    foot = (n[0] * flank_distance, n[1] * flank_distance)
    half = math.sqrt(arm_outer * arm_outer - flank_distance * flank_distance)
    a = (foot[0] + ramp[0] * half, foot[1] + ramp[1] * half)
    b = (foot[0] - ramp[0] * half, foot[1] - ramp[1] * half)
    flank_end = a if math.dist(a, apex) < math.dist(b, apex) else b
    return apex, tip_center, head_reach, head_travel, flank_end, lock_end, ramp_angle, flank_distance, ramp_distance, n


# The least distance from a bolt's axis to the farthest point of its head pocket or nut cavity.
POCKET_REACH = max(HEAD_POCKET_RADIUS, NUT_CAVITY_RADIUS * math.sqrt(3) / 2)


def derive_radii(bore_radius: float, shaft_diameter: float) -> tuple[dict[str, float], tuple]:
    """The radii that grow with the bore radius [params.go deriveRadii], and the pawl values that depend on them.

    The core grows until every bolt hole keeps BOLT_WALL from the core and the bore keeps it from the bolt pockets,
    then the slot, arm, ring, plates and adapter follow. The slot is the least that keeps MIN_SLOT_MARGIN under a fully
    pressed head; the head travel depends on the tooth tip, which depends on the slot, so it iterates. Raises
    ValidationError when the slot does not converge or the head flank leaves no room for the hub's chamfer."""
    core = max(BASE_CORE_RADIUS, bore_radius + POCKET_REACH + HOLE_RADIUS + 2 * BOLT_WALL)
    bolt_circle = core - HOLE_RADIUS - BOLT_WALL
    s = MIN_SLOT_WIDTH
    converged = False
    for _ in range(100):
        arm_inner = core + s
        arm_outer = arm_inner + ARM_THICKNESS
        tip = arm_outer + LOOSE_FIT
        root = tip + TOOTH_DEPTH
        pawl = derive_pawl(tip, root, arm_inner, arm_outer)
        nxt = max(MIN_SLOT_WIDTH, pawl[3] + MIN_SLOT_MARGIN)
        if abs(nxt - s) <= 1e-12:
            converged = True
            break
        s = nxt
    if not converged:
        raise ValidationError("slot width did not converge")
    counter = root + COUNTER_STEP
    outer = counter + RING_WALL
    ear_circle = outer + EAR_OFFSET
    ear_reach = ear_circle + EAR_RADIUS
    flank_distance = pawl[7]
    hub_chamfer = min(MAX_HUB_CHAMFER, arm_outer - flank_distance - HUB_CHAMFER_MARGIN)
    if hub_chamfer <= 0:
        raise ValidationError("the head flank leaves no room for the hub's face chamfer")
    radii = dict(
        core_radius=core, bolt_circle=bolt_circle, slot_width=s, arm_inner=arm_inner, arm_outer=arm_outer,
        tooth_tip=tip, tooth_root=root, ring_counter=counter, ring_outer=outer, ear_circle=ear_circle,
        ear_reach=ear_reach, plate_radius=counter - REGULAR_FIT, boss_radius=core + BOSS_STEP,
        adapter_radius=ear_reach, adapter_inner=shaft_diameter / 2 + ADAPTER_SHAFT_GAP, hub_chamfer=hub_chamfer,
        growth=tip - (BASE_CORE_RADIUS + MIN_SLOT_WIDTH + ARM_THICKNESS + LOOSE_FIT),
    )
    return radii, pawl


def derive(p: Params) -> Dimensions:
    """Validate p and compute its dimensions. Raises ValidationError with the first failing rule's message."""
    shaft = lookup_shaft(p.shaft)
    if shaft is None:
        raise ValidationError(f'unknown shaft preset "{p.shaft}"; want one of {", ".join(s.name for s in SHAFTS)}')
    if p.freewheel not in DIRECTIONS:
        raise ValidationError("Freewheel must be Clockwise or CounterClockwise")
    c = p.bore_clearance
    if math.isnan(c) or math.isinf(c) or c < BORE_CLEARANCE_MIN or c > BORE_CLEARANCE_MAX:
        raise ValidationError(
            f"BoreClearance must be finite, from {fmt_num(BORE_CLEARANCE_MIN)} to {fmt_num(BORE_CLEARANCE_MAX)} mm"
        )
    rb = shaft.diameter / 2 + c
    fb = shaft.diameter / 2 - shaft.flat_depth + c
    radii, pawl = derive_radii(rb, shaft.diameter)
    half = math.sqrt(rb * rb - fb * fb)
    bore_loop = 2 * rb * (math.pi - math.acos(fb / rb)) + 2 * half
    if p.placement is not None and not frame_is_valid(p.placement):
        raise ValidationError("Placement must be a valid frame")
    sites, mounts, faces = make_sites(radii["bolt_circle"], radii["ear_circle"])
    for i, s in enumerate(sites):
        _require_site(s, f"bolt {i + 1}: ")
    for i, s in enumerate(mounts):
        _require_site(s, f"mount bolt {i + 1}: ")
    for i, s in enumerate(faces):
        _require_site(s, f"face bolt {i + 1}: ")
    apex, tip_center, reach, travel, flank_end, lock_end, ramp_angle, flank_distance, ramp_distance, n = pawl
    return Dimensions(
        shaft=shaft, sign=direction_sign(p.freewheel), bore_radius=rb, bore_flat=fb, bore_loop=bore_loop,
        sites=sites, mount_sites=mounts, face_sites=faces, apex=apex, tip_center=tip_center, head_reach=reach,
        head_travel=travel, flank_end=flank_end, lock_end=lock_end, ramp_angle=ramp_angle,
        flank_distance=flank_distance, ramp_distance=ramp_distance, ramp_normal=n, **radii,
    )


def _require_site(site: Site, prefix: str) -> None:
    msg = site.validate()
    if msg:
        raise ValidationError(prefix + msg)


def validate(p: Params) -> None:
    """Raise ValidationError with the first failing rule's message."""
    derive(p)
