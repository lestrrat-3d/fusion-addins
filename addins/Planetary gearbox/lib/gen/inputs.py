"""Dialog input table. Not geometry, but stdlib-only so it stays unit-testable."""

from __future__ import annotations

import dataclasses

from .params import Params


@dataclasses.dataclass(frozen=True)
class InputSpec:
    id: str
    label: str
    kind: str  # "length" (mm) | "angle" (deg shown) | "count" | "scalar"
    default: float


# Deviation: the pressure angle is entered in degrees (Fusion's "deg" value input displays degrees) and is
# radians once read back, as in the gallery. See README "Deviations from decad-gallery".
INPUT_SPECS: tuple[InputSpec, ...] = (
    InputSpec("module", "Module", "length", 1),
    InputSpec("pressure_angle", "Pressure angle", "angle", 20),
    InputSpec("sun_teeth", "Sun teeth", "count", 13),
    InputSpec("planet_teeth", "Planet teeth", "count", 29),
    InputSpec("ring_teeth", "Ring teeth", "count", 71),
    InputSpec("planet_count", "Planets per stage", "count", 3),
    InputSpec("stages", "Stages", "count", 1),
    InputSpec("samples", "Flank samples", "count", 15),
    InputSpec("gear_thickness", "Gear thickness", "length", 8),
    InputSpec("carrier_thickness", "Carrier thickness", "length", 3),
    InputSpec("stage_gap", "Stage gap", "length", 1),
    InputSpec("cover_thickness", "Cover thickness", "length", 3),
    InputSpec("bolt_hole_diameter", "Bolt hole diameter", "length", 2.4),
    InputSpec("key_depth", "Key depth", "length", 1.1),
    InputSpec("key_width", "Key width", "length", 2),
    InputSpec("input_shaft_length", "Input shaft length", "length", 12),
    InputSpec("bearing_clearance", "Bearing clearance", "length", 0.25),
    InputSpec("seat_chamfer", "Seat chamfer", "length", 0.5),
    InputSpec("edge_chamfer", "Edge chamfer", "length", 0.5),
    InputSpec("carrier_wall", "Carrier wall", "length", 3),
    InputSpec("ring_wall", "Ring wall", "length", 7),
    InputSpec("output_shaft_length", "Output shaft length", "length", 12),
    InputSpec("backlash", "Backlash", "length", 0.15),
)


def params_from_values(values: dict[str, float]) -> Params:
    """Build Params from dialog values: lengths in mm, angle in rad, counts as int, scalars as float."""
    kwargs: dict[str, float | int] = {}
    for spec in INPUT_SPECS:
        v = values[spec.id]
        kwargs[spec.id] = int(v) if spec.kind == "count" else float(v)
    return Params(**kwargs)  # pyright: ignore[reportArgumentType]
