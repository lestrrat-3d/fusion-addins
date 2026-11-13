"""Dialog input table. Not geometry, but stdlib-only so it stays unit-testable."""

from __future__ import annotations

import dataclasses
import math

from .constants import DEG
from .params import Params


@dataclasses.dataclass(frozen=True)
class InputSpec:
    id: str
    label: str
    kind: str  # "length" (mm) | "angle" (deg shown) | "scalar"
    default: float


# Deviation: angles are entered in degrees (Fusion's "deg" value input displays degrees) and are radians once read
# back, as in the gallery. See docs/escapement/deviations.md.
INPUT_SPECS: tuple[InputSpec, ...] = (
    InputSpec("pendulum_length", "Pendulum length", "length", 180),
    InputSpec("amplitude", "Amplitude", "angle", 5),
    InputSpec("lock_angle", "Lock angle", "angle", 1.5),
    InputSpec("lift_angle", "Lift angle", "angle", 2.5),
    InputSpec("phase", "Phase", "scalar", 0.25),
    InputSpec("backlash", "Backlash", "length", 0.15),
)


def params_from_values(values: dict[str, float]) -> Params:
    """Build Params from dialog values: lengths in mm, angles in rad, scalars as float.

    # Deviation: an angle v read back from Fusion is snapped to 1e-9 degrees and rebuilt as `<degrees> * DEG`, the same
    expression as the gallery's bounds, so the dialog's own default never fails its range check by one ulp."""
    kwargs: dict[str, float] = {}
    for spec in INPUT_SPECS:
        v = float(values[spec.id])
        if spec.kind == "angle":
            v = round(math.degrees(v), 9) * DEG
        kwargs[spec.id] = v
    return Params(**kwargs)
