"""Dialog input table. Not geometry, but stdlib-only so it stays unit-testable."""

from __future__ import annotations

import dataclasses

from .params import Params


@dataclasses.dataclass(frozen=True)
class InputSpec:
    id: str
    label: str
    field: str  # the Params field it sets
    default: float  # mm; 0 or 1 for a check box
    kind: str = "length"  # "length" (mm) | "bool" (check box)


# The gallery's Params605ZZ values are the defaults. `Shaft bore diameter` is the D-flat shaft's diameter, which the
# arm's D bore is cut for; the owner chooses it (docs/crankhandle/directives.md).
INPUT_SPECS: tuple[InputSpec, ...] = (
    InputSpec("shaft_diameter", "Shaft bore diameter", "shaft_diameter", 5.0),
    InputSpec("flat_depth", "Flat depth", "flat_depth", 0.5),
    InputSpec("bore_clearance", "Bore clearance", "bore_clearance", 0.05),
    InputSpec("throw", "Throw", "throw", 55.0),
    # Directive: an extra option, off by default, that splits the pin in two. Not a gallery input.
    InputSpec("split_pin", "Split pin", "split_pin", 0, "bool"),
)


def params_from_values(values: dict[str, float]) -> Params:
    """Build Params from dialog values in mm.

    # Deviation: a length read back from Fusion (centimeters times ten) is rounded to 1e-9 mm, so the dialog's own
    default never fails a range check, such as the 0.05 mm bore clearance minimum, by one ulp."""
    kwargs: dict[str, float | bool] = {}
    for spec in INPUT_SPECS:
        v = float(values[spec.id])
        kwargs[spec.field] = bool(v) if spec.kind == "bool" else round(v, 9)
    return Params(**kwargs)  # pyright: ignore[reportArgumentType]
