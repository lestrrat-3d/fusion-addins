"""Plaque stand input validation and the derived dimensions.

Own copy of decad-gallery models/plaquestand params.go Validate and Derive.

Deviation: messages are the gallery's without the `plaquestand: ` prefix, because the dialog shows them on its own
(docs/plaquestand/deviations.md).
"""

from __future__ import annotations

import math

from .constants import (
    BACK_HEIGHT_RATIO,
    BACK_THICKNESS,
    BASE_THICKNESS,
    BOLT_LENGTH,
    BRACKET_WIDTH,
    CHAMFER_SIZE,
    CHANNEL_LAND,
    CHANNEL_MOUTH_ROUND,
    CORNER_RADIUS,
    FRONT_FLAT,
    JOINT_FIT,
    LIP_THICKNESS,
    MAX_BACK_HEIGHT,
    MAX_EXTENT,
    MAX_LIP_HEIGHT,
    MAX_PLAQUE_HEIGHT,
    MAX_PLAQUE_THICKNESS,
    MAX_PLAQUE_WIDTH,
    MAX_RECLINE,
    MAX_SLOT_CLEARANCE,
    MAX_SPAN,
    MIN_BACK_HEIGHT,
    MIN_LIP_HEIGHT,
    MIN_PLAQUE_HEIGHT,
    MIN_PLAQUE_THICKNESS,
    MIN_PLAQUE_WIDTH,
    MIN_RECLINE,
    MIN_SLOT_CLEARANCE,
    MIN_SPAN,
    MIN_TIP_ANGLE,
    RAIL_HEIGHT,
    RAIL_WIDTH,
    REAR_LAND,
    ROOT_RADIUS,
    SPAN_RATIO,
)
from .fasteners import Site
from .params import Dimensions, Params
from .report import fmt_num


class ValidationError(ValueError):
    pass


def _outside(v: float, lo: float, hi: float) -> bool:
    return not (lo <= v <= hi)  # also rejects NaN


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)


def _field(name: str, v: float, lo: float, hi: float, unit: str) -> None:
    if _outside(v, lo, hi):
        raise ValidationError(f"{name} must be from {fmt_num(lo)} to {fmt_num(hi)} {unit}, got {fmt_num(v)}")


def derive(p: Params) -> Dimensions:
    """Validate p and compute its dimensions. Raises ValidationError with the first failing rule's message."""
    _field("PlaqueWidth", p.plaque_width, MIN_PLAQUE_WIDTH, MAX_PLAQUE_WIDTH, "mm")
    _field("PlaqueHeight", p.plaque_height, MIN_PLAQUE_HEIGHT, MAX_PLAQUE_HEIGHT, "mm")
    _field("PlaqueThickness", p.plaque_thickness, MIN_PLAQUE_THICKNESS, MAX_PLAQUE_THICKNESS, "mm")
    _field("Recline", p.recline, MIN_RECLINE, MAX_RECLINE, "degrees")
    _field("LipHeight", p.lip_height, MIN_LIP_HEIGHT, MAX_LIP_HEIGHT, "mm")
    _field("SlotClearance", p.slot_clearance, MIN_SLOT_CLEARANCE, MAX_SLOT_CLEARANCE, "mm")

    W, H, t, c = p.plaque_width, p.plaque_height, p.plaque_thickness, p.slot_clearance
    theta = math.radians(p.recline)
    sT, cT = math.sin(theta), math.cos(theta)
    tb, lt, bt, rr, rc, e = BASE_THICKNESS, LIP_THICKNESS, BACK_THICKNESS, ROOT_RADIUS, CORNER_RADIUS, CHAMFER_SIZE
    tan_phi = math.tan(math.radians(MIN_TIP_ANGLE))

    span = _clamp(SPAN_RATIO * W, MIN_SPAN, MAX_SPAN)
    back_height = _clamp(BACK_HEIGHT_RATIO * H, MIN_BACK_HEIGHT, MAX_BACK_HEIGHT)
    slot_width = t + 2 * c
    R = slot_width / 2
    back_wall = back_height - bt / 2
    lip_wall = p.lip_height - lt / 2
    axis = (sT, cT)
    normal = (cT, -sT)
    cz = tb + R
    alpha = math.atan(2 * c / back_wall)
    kf = 1 / math.tan(math.radians(45) + theta / 2)
    kb = 1 / math.tan(math.radians(45) - theta / 2)
    l7 = -(R + (R + lt) * sT) / cT
    l3 = (-R + (R + bt) * sT) / cT
    theta_f, theta_b = theta - alpha, theta + alpha

    cy_geom = rc + FRONT_FLAT + (R + lt) * cT - l7 * sT + rr * kf
    cy_stab = rc + (cz + (H / 2) * math.cos(theta_f)) * tan_phi - (H / 2) * math.sin(theta_f)
    cy = max(cy_geom, cy_stab)

    q7y = cy - (R + lt) * cT + l7 * sT
    q3y = cy + (R + bt) * cT + l3 * sT
    gfy, gfz = cy + (H / 2) * math.sin(theta_f), cz + (H / 2) * math.cos(theta_f)
    gby, gbz = cy + (H / 2) * math.sin(theta_b), cz + (H / 2) * math.cos(theta_b)
    wc = RAIL_WIDTH + 2 * JOINT_FIT
    d_geom = q3y + rr * kb + CHANNEL_LAND + 2 * CHANNEL_MOUTH_ROUND + wc + REAR_LAND + rc
    d_stab = rc + gby + gbz * tan_phi
    depth = math.ceil(max(d_geom, d_stab))

    tip_front = math.degrees(math.atan((gfy - rc) / gfz))
    tip_back = math.degrees(math.atan((depth - rc - gby) / gbz))
    tip_side = math.degrees(math.atan((span / 2 - e) / gfz))

    c4 = (cy + normal[0] * (R + bt / 2) + axis[0] * back_wall, cz + normal[1] * (R + bt / 2) + axis[1] * back_wall)
    c6 = (cy - normal[0] * (R + lt / 2) + axis[0] * lip_wall, cz - normal[1] * (R + lt / 2) + axis[1] * lip_wall)
    height = max(c4[1] + bt / 2, c6[1] + lt / 2)

    if tip_side < MIN_TIP_ANGLE:
        raise ValidationError(f"side tip angle {tip_side:.2f} degrees is under {fmt_num(MIN_TIP_ANGLE)}")
    if span > MAX_EXTENT:
        raise ValidationError(f"rail length {span:.1f} mm exceeds the {fmt_num(MAX_EXTENT)} mm print limit")
    if depth > MAX_EXTENT:
        raise ValidationError(f"stand depth extent {depth:.1f} mm exceeds the {fmt_num(MAX_EXTENT)} mm print limit")
    if height > MAX_EXTENT:
        raise ValidationError(f"stand height extent {height:.1f} mm exceeds the {fmt_num(MAX_EXTENT)} mm print limit")

    channel_back = depth - rc - REAR_LAND - CHANNEL_MOUTH_ROUND
    channel_front = channel_back - wc
    channel_floor = tb - RAIL_HEIGHT
    rail_center = (channel_back + channel_front) / 2
    sites = []
    for k in range(2):
        x = BRACKET_WIDTH / 2 if k == 0 else span - BRACKET_WIDTH / 2
        site = Site(head=(x, rail_center, tb + JOINT_FIT), dir=(0.0, 0.0, -1.0), corner=(1.0, 0.0, 0.0),
                    length=BOLT_LENGTH, cavity=6 + JOINT_FIT)
        msg = site.validate()
        if msg:
            raise ValidationError(f"bolt {k + 1}: {msg}")
        sites.append(site)
    return Dimensions(
        span=span, channel_width=wc, channel_height=RAIL_HEIGHT, channel_back=channel_back,
        channel_front=channel_front, channel_floor=channel_floor, rail_center=rail_center,
        sites=(sites[0], sites[1]), back_height=back_height, slot_width=slot_width, slot_radius=R,
        back_wall=back_wall, lip_wall=lip_wall, axis=axis, normal=normal, seat=(cy, cz), depth=depth,
        height=height, play_angle=math.degrees(alpha), tip_front=tip_front, tip_back=tip_back, tip_side=tip_side,
        q3y=q3y, q7y=q7y, kf=kf, kb=kb,
    )


def validate(p: Params) -> None:
    """Raise ValidationError with the first failing rule's message."""
    derive(p)
