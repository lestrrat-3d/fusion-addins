"""Gear radii of the gearbox's sun, planet and ring tool.

Own copy of decad-gallery models/planetarygearbox gears.go (externalGearWithRootClearance, ringTool) at a800069.
"""

from __future__ import annotations

from .involute import GearDims, external_gear_dims, ring_tool_dims
from .params import GEAR_ROOT_MEASUREMENT_MARGIN, Params, gear_root_clearance


def sun_gear(p: Params) -> GearDims:
    return external_gear_dims(
        p.module, p.sun_teeth, p.pressure_angle, p.backlash, gear_root_clearance(p.module), 0.0,
        GEAR_ROOT_MEASUREMENT_MARGIN,
    )


def planet_gear(p: Params) -> GearDims:
    return external_gear_dims(
        p.module, p.planet_teeth, p.pressure_angle, p.backlash, gear_root_clearance(p.module),
        GEAR_ROOT_MEASUREMENT_MARGIN, GEAR_ROOT_MEASUREMENT_MARGIN,
    )


def ring_tool(p: Params) -> GearDims:
    return ring_tool_dims(p.module, p.ring_teeth, p.pressure_angle, -p.backlash, gear_root_clearance(p.module))
