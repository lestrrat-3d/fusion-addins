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


def params_from_values(values: dict[str, int]) -> Params:
    """Build Params from the dialog's integer values."""
    return Params(**{spec.field: int(values[spec.id]) for spec in INPUT_SPECS})
