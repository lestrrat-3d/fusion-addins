"""Derived dimensions. Own copy of decad-gallery models/planetarygearbox params.go derive() at 45b5875."""

from __future__ import annotations

import dataclasses
import json

from .bearing import Spec, lookup
from .fasteners import head_pocket_diameter
from .params import (
    ARM_MARGIN,
    BOLT_RIM_MARGIN,
    COLLAR_MARGIN,
    PRESS_FIT_CLEARANCE,
    GEAR_ROOT_MEASUREMENT_MARGIN,
    LIP_WIDTH,
    Params,
    gear_root_depth,
)


@dataclasses.dataclass(frozen=True)
class Dims:
    orbit: float
    planet_root: float
    planet_tip: float
    sun_root: float
    ring_tip: float
    ring_root: float
    ring_outer: float
    pin: float
    pin_collar: float
    planet_pocket: float
    planet_lip: float
    boss: float
    arm: float
    collar: float
    shaft: float
    shaft_bore: float
    cover_pocket: float
    cover_lip: float
    cover_boss: float
    cover_hub: float
    bolt_circle: float
    rim_inner: float
    stage_pitch: float
    ring_length: float
    planet_bearing: Spec
    shaft_bearing: Spec


def rim_inner_radius(bolt_circle: float) -> float:
    """Inner radius of a cover's rim [params.go rimInnerRadius]: the bolt circle radius less the head pocket radius
    and the material kept around the pocket."""
    return bolt_circle - head_pocket_diameter() / 2 - BOLT_RIM_MARGIN


def derive(p: Params) -> Dims:
    """Compute the derived dimensions of p. Does not validate p."""
    m = p.module
    # The gallery's derive uses a zero Spec for a name the catalog lacks; raising surfaces the bug sooner.
    pb, sb = lookup(p.planet_bearing), lookup(p.shaft_bearing)
    if pb is None:
        raise ValueError(f"unknown bearing {json.dumps(p.planet_bearing, ensure_ascii=False)}")
    if sb is None:
        raise ValueError(f"unknown bearing {json.dumps(p.shaft_bearing, ensure_ascii=False)}")
    ring_root = m * p.ring_teeth / 2 + gear_root_depth(m)
    ring_outer = ring_root + p.ring_wall
    bolt_circle = (ring_root + ring_outer) / 2
    stage_pitch = p.gear_thickness + p.carrier_thickness + 2 * p.stage_gap
    pin = pb.shaft_diameter()  # params.go: zero clearance in the bearing bore (96e8435)
    shaft = sb.shaft_diameter()
    cover_pocket = sb.outer_diameter + 2 * p.bearing_clearance
    cover_boss = cover_pocket + 2 * p.carrier_wall
    return Dims(
        orbit=m * (p.sun_teeth + p.planet_teeth) / 2,
        planet_root=m * p.planet_teeth / 2 - gear_root_depth(m) - GEAR_ROOT_MEASUREMENT_MARGIN,
        planet_tip=(m * p.planet_teeth + 2 * m) / 2 - GEAR_ROOT_MEASUREMENT_MARGIN,
        sun_root=m * p.sun_teeth / 2 - gear_root_depth(m),
        ring_tip=m * p.ring_teeth / 2 - m,
        ring_root=ring_root,
        ring_outer=ring_outer,
        pin=pin,
        pin_collar=pin + 2 * COLLAR_MARGIN,
        planet_pocket=pb.outer_diameter + 2 * p.bearing_clearance,
        planet_lip=pb.outer_diameter - 2 * LIP_WIDTH,
        boss=pin + 2 * p.carrier_wall,
        arm=pin + 2 * ARM_MARGIN,
        collar=shaft + 2 * COLLAR_MARGIN,
        shaft=shaft,
        shaft_bore=shaft + 2 * PRESS_FIT_CLEARANCE,
        cover_pocket=cover_pocket,
        cover_lip=sb.outer_diameter - 2 * LIP_WIDTH,
        cover_boss=cover_boss,
        cover_hub=cover_boss + 2 * p.carrier_wall,
        bolt_circle=bolt_circle,
        # [params.go rimInnerRadius] derive and table.go readDims both use it at a800069.
        rim_inner=rim_inner_radius(bolt_circle),
        stage_pitch=stage_pitch,
        ring_length=p.stages * stage_pitch + p.stage_gap,
        planet_bearing=pb,
        shaft_bearing=sb,
    )
