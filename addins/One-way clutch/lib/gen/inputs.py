"""Dialog input table. Not geometry, but stdlib-only so it stays unit-testable."""

from __future__ import annotations

import dataclasses

from .params import CLOCKWISE, DIRECTIONS, SHAFTS, Params


@dataclasses.dataclass(frozen=True)
class InputSpec:
    id: str
    label: str
    field: str  # the Params field it sets
    default: float | str  # mm for a length; 0 or 1 for a check box; the chosen name for a drop-down
    kind: str = "length"  # "length" (mm) | "bool" (check box) | "choice" (a drop-down of `choices`)
    choices: tuple[str, ...] = ()


# The gallery's DefaultParams are the defaults. Shaft and Freewheel are the gallery's named inputs, so they are
# drop-downs listing the names the gallery accepts; a name cannot be mistyped.
INPUT_SPECS: tuple[InputSpec, ...] = (
    InputSpec("shaft", "Shaft", "shaft", SHAFTS[0].name, "choice", tuple(s.name for s in SHAFTS)),
    InputSpec("freewheel", "Freewheel", "freewheel", CLOCKWISE, "choice", DIRECTIONS),
    InputSpec("bore_clearance", "Bore clearance", "bore_clearance", 0.05),
    # An extra option, off by default, that also builds the gallery's BuildAdapter parts. Not a gallery input.
    InputSpec("adapter", "Adapter ring", "adapter", 0, "bool"),
    # Directive: an extra option, off by default, that adds the sacrificial bridge layers of the back plate, the cover
    # and the adapter ring (docs/sacrificial-bridging.md in decad-converter). Not a gallery input.
    InputSpec("sacrificial_bridging", "Sacrificial bridging", "sacrificial_bridging", 0, "bool"),
)


def params_from_values(values: dict[str, float | str]) -> Params:
    """Build Params from dialog values in mm.

    # Deviation: a length read back from Fusion (centimeters times ten) is rounded to 1e-9 mm, so the dialog's own
    default never fails a range check, such as the 0.05 mm bore clearance minimum, by one ulp."""
    kwargs: dict[str, float | bool | str] = {}
    for spec in INPUT_SPECS:
        v = values[spec.id]
        if spec.kind == "choice":
            kwargs[spec.field] = str(v)
        elif spec.kind == "bool":
            kwargs[spec.field] = bool(float(v))
        else:
            kwargs[spec.field] = round(float(v), 9)
    return Params(**kwargs)  # pyright: ignore[reportArgumentType]
