"""Pinion and great-wheel radii of the escapement's gear train.

Own copy of decad-gallery models/escapement gears.go and internal/gearroot at 0067d30. Both gears share the root
clearance variant: root deepened by the gear-train clearance, root and tip both lowered by the 0.02 mm margin.
"""

from __future__ import annotations

from .constants import GEAR_ROOT_MARGIN, GEAR_TIP_MARGIN, GREAT_TEETH, MODULE, PINION_TEETH, PRESSURE_ANGLE
from .involute import GearDims, external_gear_dims
from .params import Params

ROOT_CLEARANCE = max(0.25 * MODULE, 0.5)
SAMPLES = 15


def _dims(p: Params, teeth: int) -> GearDims:
    return external_gear_dims(
        MODULE, teeth, PRESSURE_ANGLE, p.backlash, ROOT_CLEARANCE, GEAR_ROOT_MARGIN, GEAR_TIP_MARGIN
    )


def pinion_dims(p: Params) -> GearDims:
    return _dims(p, PINION_TEETH)


def great_dims(p: Params) -> GearDims:
    return _dims(p, GREAT_TEETH)
