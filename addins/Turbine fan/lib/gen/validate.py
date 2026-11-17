"""Turbine fan input validation and the derived dimensions.

Own copy of decad-gallery models/turbinefan params.go Validate and Derive.

Deviation: messages are the gallery's without the `turbinefan: ` prefix, because the dialog shows them on its own
(docs/turbinefan/deviations.md).
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    BORE_CLEARANCE_MAX,
    BORE_CLEARANCE_MIN,
    CLUTCH_MOUNT,
    LEFT_HAND,
    MAX_BLADE_PITCH,
    MIN_BLADE_PITCH,
    PRESS_WALL,
    RIGHT_HAND,
    SET_SCREW_TRAVEL,
    SET_SCREW_Z,
    SHAFT_MOUNT,
)
from .fasteners import (
    STANDARD_LENGTHS,
    HEAD_DIAMETER,
    HEAD_POCKET_DEPTH,
    HEAD_POCKET_RADIUS,
    HOLE_RADIUS,
    NUT_CAVITY_HEIGHT,
    SHANK_DIAMETER,
    Site,
)
from .clutch import validate as clutch_validate
from .params import Dimensions, Params, adapter_site, blade_site, frame_is_valid
from .report import fmt_num
from .size import SizeError, size_for

_SLACK = 1e-9


class ValidationError(ValueError):
    pass


def _require_site(site: Site, prefix: str) -> None:
    msg = site.validate()
    if msg:
        raise ValidationError(prefix + msg)


def derive(p: Params) -> Dimensions:
    """Validate p and compute its dimensions. Raises ValidationError with the first failing rule's message."""
    for name, value in (
        ("ShaftDiameter", p.shaft_diameter),
        ("FlatDepth", p.flat_depth),
        ("BoreClearance", p.bore_clearance),
        ("BladePitch", p.blade_pitch),
        ("RotorDiameter", p.rotor_diameter),
    ):
        if math.isnan(value) or math.isinf(value) or value <= 0:
            raise ValidationError(f"{name} must be finite and positive")
    try:
        size = size_for(p.rotor_diameter)
    except SizeError as e:
        raise ValidationError(str(e)) from e
    if p.flat_depth > p.shaft_diameter / 4:
        raise ValidationError("FlatDepth must be at most a quarter of ShaftDiameter")
    if p.bore_clearance < BORE_CLEARANCE_MIN or p.bore_clearance > BORE_CLEARANCE_MAX:
        raise ValidationError(
            f"BoreClearance must be from {fmt_num(BORE_CLEARANCE_MIN)} to {fmt_num(BORE_CLEARANCE_MAX)} mm"
        )
    if p.mount not in (SHAFT_MOUNT, CLUTCH_MOUNT):
        raise ValidationError("Mount must be ShaftMount or ClutchMount")
    rb = p.shaft_diameter / 2 + p.bore_clearance
    fb = p.shaft_diameter / 2 - p.flat_depth + p.bore_clearance
    bore_flat_width = 2 * math.sqrt(rb * rb - fb * fb)
    bore_loop = 2 * rb * (math.pi - math.acos(fb / rb)) + bore_flat_width
    shaft_flat_width = 2 * math.sqrt(p.flat_depth * (p.shaft_diameter - p.flat_depth))
    if size.blade_socket_start - rb < PRESS_WALL - _SLACK:
        raise ValidationError(f"ShaftDiameter leaves less than a {PRESS_WALL:.1f} mm wall to the blade sockets")
    if shaft_flat_width < SHANK_DIAMETER - _SLACK:
        raise ValidationError("FlatDepth must leave the shaft's flat at least 2 mm wide for the set screw's tip")
    if bore_flat_width < 2 * (HOLE_RADIUS + 0.1) - _SLACK:
        raise ValidationError("FlatDepth must leave the bore's flat at least 2.8 mm wide for the set screw's hole")
    if p.blade_pitch < MIN_BLADE_PITCH - _SLACK or p.blade_pitch > MAX_BLADE_PITCH + _SLACK:
        raise ValidationError("BladePitch must lie from 10 to 40 degrees")
    if p.hand not in (RIGHT_HAND, LEFT_HAND):
        raise ValidationError("Hand must be RightHand or LeftHand")
    if p.placement is not None and not frame_is_valid(p.placement):
        raise ValidationError("Placement must be a valid frame")
    if p.clutch is not None:
        # The clutch is built with the fan's placement and always with its adapter; its own rules apply as they are.
        try:
            clutch_validate.validate(dataclasses.replace(p.clutch, placement=None, adapter=True))
        except clutch_validate.ValidationError as e:
            raise ValidationError(f"clutch: {e}") from e

    tip = p.shaft_diameter / 2 - p.flat_depth - p.bore_clearance
    # The head must stay inside the round face: rho_h <= sqrt(HubRadius^2 - (HeadDiameter/2)^2).
    reach = math.sqrt(size.hub_radius * size.hub_radius - HEAD_DIAMETER * HEAD_DIAMETER / 4)
    set_screw_bolt = 0.0
    for length in STANDARD_LENGTHS:
        if tip + HEAD_POCKET_DEPTH + length <= reach:
            set_screw_bolt = float(length)
    if set_screw_bolt == 0.0:
        raise ValidationError("set screw: no standard length keeps its head inside the round face")
    head = tip + HEAD_POCKET_DEPTH + set_screw_bolt
    floor = head - HEAD_POCKET_DEPTH - SET_SCREW_TRAVEL
    screw = Site(head=(0.0, -head, SET_SCREW_Z), dir=(0.0, 1.0, 0.0), corner=(0.0, 0.0, 1.0), length=set_screw_bolt,
                 cavity=head - fb - PRESS_WALL - NUT_CAVITY_HEIGHT)
    _require_site(screw, "set screw: ")
    if screw.cavity - HEAD_POCKET_DEPTH - SET_SCREW_TRAVEL < 1 - _SLACK:
        raise ValidationError("set screw: less than 1 mm between its counterbore and its nut slot")
    if SET_SCREW_Z - HEAD_POCKET_RADIUS < 1:
        raise ValidationError("set screw: less than 1 mm between its counterbore and the back face")
    adapters = (adapter_site(1), adapter_site(2))
    for i, site in enumerate(adapters):
        _require_site(site, f"adapter bolt {i + 1}: ")
    blades = (blade_site(1, size), blade_site(2, size), blade_site(3, size))
    for i, site in enumerate(blades):
        _require_site(site, f"blade bolt {i + 1}: ")
    return Dimensions(
        size=size, set_screw_bolt=set_screw_bolt, bore_radius=rb, bore_flat=fb, bore_flat_width=bore_flat_width, bore_loop=bore_loop,
        shaft_flat_width=shaft_flat_width, set_screw_tip=tip, set_screw_head=head, counterbore_floor=floor,
        set_screw_site=screw, blade_sites=blades, adapter_sites=adapters,
    )


def validate(p: Params) -> None:
    """Raise ValidationError with the first failing rule's message."""
    derive(p)
