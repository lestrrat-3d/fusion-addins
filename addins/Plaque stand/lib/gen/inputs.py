"""Dialog input table. Not geometry, but stdlib-only so it stays unit-testable."""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    DEFAULT_LIP_HEIGHT,
    DEFAULT_PLAQUE_HEIGHT,
    DEFAULT_PLAQUE_THICKNESS,
    DEFAULT_PLAQUE_WIDTH,
    DEFAULT_RECLINE,
    DEFAULT_SLOT_CLEARANCE,
)
from .params import Params


@dataclasses.dataclass(frozen=True)
class InputSpec:
    id: str
    label: str
    field: str  # the Params field it sets
    default: float  # mm; degrees for an angle
    kind: str = "length"  # "length" (mm) | "angle" (degrees)


# The gallery's DefaultParams are the defaults, in the gallery's field order.
INPUT_SPECS: tuple[InputSpec, ...] = (
    InputSpec("plaque_width", "Plaque width", "plaque_width", DEFAULT_PLAQUE_WIDTH),
    InputSpec("plaque_height", "Plaque height", "plaque_height", DEFAULT_PLAQUE_HEIGHT),
    InputSpec("plaque_thickness", "Plaque thickness", "plaque_thickness", DEFAULT_PLAQUE_THICKNESS),
    InputSpec("recline", "Recline", "recline", DEFAULT_RECLINE, "angle"),
    InputSpec("lip_height", "Lip height", "lip_height", DEFAULT_LIP_HEIGHT),
    InputSpec("slot_clearance", "Slot clearance", "slot_clearance", DEFAULT_SLOT_CLEARANCE),
)


def params_from_values(values: dict[str, float]) -> Params:
    """Build Params from dialog values: lengths in mm, the recline in radians (Fusion's unit for an angle).

    # Deviation: a length read back from Fusion (centimeters times ten) is rounded to 1e-9 mm, so the dialog's own
    default never fails a range check, such as the 0.55 mm clearance minimum, by one ulp. The recline is converted to
    degrees and rounded the same way (docs/plaquestand/deviations.md)."""
    kwargs: dict[str, float] = {}
    for spec in INPUT_SPECS:
        v = float(values[spec.id])
        kwargs[spec.field] = round(math.degrees(v), 9) if spec.kind == "angle" else round(v, 9)
    return Params(**kwargs)
