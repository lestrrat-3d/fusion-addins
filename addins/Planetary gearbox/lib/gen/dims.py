"""Derived dimensions. Own copy of decad-gallery models/planetarygearbox params.go derive() (92c1f03)."""

from __future__ import annotations

import dataclasses

from .bearing import Bearing, bearing_605zz
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
    pocket: float
    lip: float
    boss: float
    arm: float
    collar: float
    shaft: float
    shaft_bore: float
    cover_boss: float
    cover_hub: float
    bolt_circle: float
    rim_inner: float
    stage_pitch: float
    ring_length: float
    bearing: Bearing


def rim_inner_radius(bolt_circle: float) -> float:
    """Inner radius of a cover's rim [params.go rimInnerRadius]: the bolt circle radius less the head pocket radius
    and the material kept around the pocket."""
    return bolt_circle - head_pocket_diameter() / 2 - BOLT_RIM_MARGIN


def derive(p: Params) -> Dims:
    """Compute the derived dimensions of p. Does not validate p."""
    m = p.module
    b = bearing_605zz()
    ring_root = m * p.ring_teeth / 2 + gear_root_depth(m)
    ring_outer = ring_root + p.ring_wall
    bolt_circle = (ring_root + ring_outer) / 2
    stage_pitch = p.gear_thickness + p.carrier_thickness + 2 * p.stage_gap
    pocket = b.outer_diameter + 2 * p.bearing_clearance
    cover_boss = pocket + 2 * p.carrier_wall
    pin = b.bore_diameter  # params.go: zero clearance in the bearing bore (96e8435)
    shaft = pin
    return Dims(
        orbit=m * (p.sun_teeth + p.planet_teeth) / 2,
        planet_root=m * p.planet_teeth / 2 - gear_root_depth(m) - GEAR_ROOT_MEASUREMENT_MARGIN,
        planet_tip=(m * p.planet_teeth + 2 * m) / 2 - GEAR_ROOT_MEASUREMENT_MARGIN,
        sun_root=m * p.sun_teeth / 2 - gear_root_depth(m),
        ring_tip=m * p.ring_teeth / 2 - m,
        ring_root=ring_root,
        ring_outer=ring_outer,
        pin=pin,
        pocket=pocket,
        lip=b.outer_diameter - 2 * LIP_WIDTH,
        boss=pin + 2 * p.carrier_wall,
        arm=pin + 2 * ARM_MARGIN,
        collar=shaft + 2 * COLLAR_MARGIN,
        shaft=shaft,
        shaft_bore=shaft + 2 * PRESS_FIT_CLEARANCE,
        cover_boss=cover_boss,
        cover_hub=cover_boss + 2 * p.carrier_wall,
        bolt_circle=bolt_circle,
        # [params.go rimInnerRadius] derive and table.go readDims both use it at a800069.
        rim_inner=rim_inner_radius(bolt_circle),
        stage_pitch=stage_pitch,
        ring_length=p.stages * stage_pitch + p.stage_gap,
        bearing=b,
    )
