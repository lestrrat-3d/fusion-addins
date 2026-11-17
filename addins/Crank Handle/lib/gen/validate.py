"""Crank handle input validation and the derived dimensions.

Own copy of decad-gallery models/crankhandle params.go Validate and Derive.

Deviation: messages are the gallery's without the `crankhandle: ` prefix, because the dialog shows them on its own
(docs/crankhandle/deviations.md).
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    ARM_RADIUS,
    ARM_THICKNESS,
    BORE_CLEARANCE_MAX,
    BORE_CLEARANCE_MIN,
    CLAMP_BOLT,
    CLAMP_END_R,
    CLAMP_HOLE_WALL,
    CLAMP_Z,
    CLAMP_SIDE_RUN,
    CROSS_BOLT,
    CROSS_CAVITY,
    CROSS_FLAT,
    CROSS_Z,
    HANDLE_PROFILE,
    HUB_LENGTH,
    PIN_BOLT,
    PIN_CAVITY,
    PRESS_WALL,
    RAMP_ANGLE,
    REGULAR_FIT,
)
from .fasteners import HEAD_POCKET_DEPTH, HOLE_RADIUS, NUT_CAVITY_HEIGHT, Site
from .params import Dimensions, Params, frame_is_valid
from .report import fmt_num

_TIP_TOLERANCE = 1e-9


class ValidationError(ValueError):
    pass


def derive(p: Params) -> Dimensions:
    """Validate p and compute its dimensions. Raises ValidationError with the first failing rule's message."""
    for name, value in (
        ("ShaftDiameter", p.shaft_diameter),
        ("FlatDepth", p.flat_depth),
        ("BoreClearance", p.bore_clearance),
        ("Throw", p.throw),
    ):
        if math.isnan(value) or math.isinf(value) or value <= 0:
            raise ValidationError(f"{name} must be finite and positive")
    if p.flat_depth > p.shaft_diameter / 4:
        raise ValidationError("FlatDepth must be at most a quarter of ShaftDiameter")
    if p.bore_clearance < BORE_CLEARANCE_MIN or p.bore_clearance > BORE_CLEARANCE_MAX:
        raise ValidationError(
            f"BoreClearance must be from {fmt_num(BORE_CLEARANCE_MIN)} to {fmt_num(BORE_CLEARANCE_MAX)} mm"
        )
    rb = p.shaft_diameter / 2 + p.bore_clearance
    fb = p.shaft_diameter / 2 - p.flat_depth + p.bore_clearance
    half = math.sqrt(rb * rb - fb * fb)
    bore_back = rb
    bore_loop = 2 * rb * (math.pi - math.acos(fb / rb)) + 2 * half
    if p.double_flat:
        bore_back = fb
        bore_loop = 2 * rb * (math.pi - 2 * math.acos(fb / rb)) + 4 * half
    ramp_foot = ARM_RADIUS + (HUB_LENGTH - ARM_THICKNESS) / math.tan(math.radians(RAMP_ANGLE))
    # A 1e-9 mm slack keeps the stated limit (a 16.7 mm shaft at the least clearance) valid despite rounding.
    if ARM_RADIUS - rb < PRESS_WALL - 1e-9:
        raise ValidationError(
            f"ShaftDiameter leaves less than a {PRESS_WALL:.1f} mm wall in the {fmt_num(2 * ARM_RADIUS)} mm arm"
        )
    handle_radius = max(r for _, r in HANDLE_PROFILE)
    min_throw = ramp_foot + handle_radius + REGULAR_FIT
    if p.throw < min_throw:
        # The handle and the pin pocket must clear the ramp.
        raise ValidationError(f"Throw must be at least {math.ceil(min_throw * 100) / 100:.2f} mm")
    if p.placement is not None and not frame_is_valid(p.placement):
        raise ValidationError("Placement must be a valid frame")

    site = Site(head=(0.0, p.throw, 0.0), dir=(0.0, 0.0, 1.0), corner=(1.0, 0.0, 0.0), length=PIN_BOLT,
                cavity=PIN_CAVITY)
    _require_site(site, "")
    clamp_y = -(rb + HOLE_RADIUS + CLAMP_HOLE_WALL)
    side_end = clamp_y - CLAMP_SIDE_RUN
    clamp_sites: list[Site] = []
    for i, z in enumerate(CLAMP_Z):
        cs = Site(head=(ARM_RADIUS, clamp_y, z), dir=(-1.0, 0.0, 0.0), corner=(0.0, 0.0, 1.0),
                  length=CLAMP_BOLT, cavity=HEAD_POCKET_DEPTH + CLAMP_BOLT - NUT_CAVITY_HEIGHT)
        _require_site(cs, f"clamp bolt {i + 1}: ")
        if abs(cs.tip() - cs.cavity_far()) > _TIP_TOLERANCE or cs.tip() >= 2 * ARM_RADIUS:
            raise ValidationError(
                f"clamp bolt {i + 1}: its tip must end at the nut cavity's far face, inside the -X side face")
        clamp_sites.append(cs)
    cross: list[Site] = []
    for i, z in enumerate(CROSS_Z):
        s = Site(head=(0.0, p.throw + CROSS_FLAT, z), dir=(0.0, -1.0, 0.0), corner=(1.0, 0.0, 0.0),
                 length=CROSS_BOLT, cavity=CROSS_CAVITY)
        _require_site(s, f"cross bolt {i + 1}: ")
        if abs(s.tip() - s.cavity_far()) > _TIP_TOLERANCE:
            raise ValidationError(f"cross bolt {i + 1}: its tip must end flush with the -Y flat")
        cross.append(s)
    dm = Dimensions(bore_radius=rb, bore_flat=fb, bore_back=bore_back, bore_loop=bore_loop, ramp_foot=ramp_foot,
                    site=site, cross_sites=(cross[0], cross[1]), clamp_y=clamp_y, side_end=side_end, reach=0.0,
                    clamp_sites=(clamp_sites[0], clamp_sites[1]))
    reach = CLAMP_END_R - dm.end_center()[1]
    return dataclasses.replace(dm, reach=reach)


def _require_site(site: Site, prefix: str) -> None:
    msg = site.validate()
    if msg:
        raise ValidationError(prefix + msg)


def validate(p: Params) -> None:
    """Raise ValidationError with the first failing rule's message."""
    derive(p)
