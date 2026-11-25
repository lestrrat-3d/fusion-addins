"""Dialog input table. Not geometry, but stdlib-only so it stays unit-testable."""

from __future__ import annotations

import dataclasses

from .params import Params

DIGIT_MIN = 0
DIGIT_MAX = 9


@dataclasses.dataclass(frozen=True)
class InputSpec:
    id: str
    label: str
    field: str  # the Params field it sets
    default: int
    minimum: int
    maximum: int


# The gallery's inputs are `Digit` and `Placement` only; Placement is chosen by the two selections in the dialog.
INPUT_SPECS: tuple[InputSpec, ...] = (InputSpec("digit", "Digit", "digit", 2, DIGIT_MIN, DIGIT_MAX),)

# The check box after the spinner: the flags are tilted to show the digit. Off (the default) builds them straight, so
# they are in the orientation they print in.
TILT_ID = "tilt_flags"
TILT_LABEL = "Tilt flags to show the digit"
TILT_DEFAULT = False


def params_from_values(values: dict[str, int], tilt_flags: bool = TILT_DEFAULT) -> Params:
    """Build Params from the dialog's integer values and its check box."""
    return Params(tilt_flags=bool(tilt_flags), **{spec.field: int(values[spec.id]) for spec in INPUT_SPECS})
