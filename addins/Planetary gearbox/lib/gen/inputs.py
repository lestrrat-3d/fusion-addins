"""Dialog input table. Not geometry, but stdlib-only so it stays unit-testable."""

from __future__ import annotations

import dataclasses
import html

from .bearing import catalog_names
from .kits import default_params_for, kit_dependent_fields, kit_for
from .params import Params


@dataclasses.dataclass(frozen=True)
class InputSpec:
    id: str
    label: str
    # "length" (mm) | "angle" (deg shown) | "count" | "scalar" | "bool" (check box, 1 = checked) |
    # "choice" (a drop-down of `choices`; the value is the chosen name)
    kind: str
    default: float | str
    # Id of the "bool" input that enables this one. Its dialog input is disabled while that box is unchecked.
    needs: str = ""
    choices: tuple[str, ...] = ()


EARS_ID = "ears"
SPLIT_ID = "split_pins_shafts"
BRIDGING_ID = "sacrificial_bridging"
# The two bearing selectors; a change to either resets the kit-dependent inputs (kits.kit_dependent_fields).
SELECTOR_IDS = ("planet_bearing", "shaft_bearing")

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
    InputSpec("bolt_hole_diameter", "Bolt hole diameter", "length", 2.6),
    InputSpec("flat_depth", "Flat depth", "length", 0.5),
    InputSpec("input_shaft_length", "Input shaft length", "length", 12),
    InputSpec("bearing_clearance", "Bearing clearance", "length", 0.05),
    # Gallery PlanetBearing / ShaftBearing, placed in the gallery's table order (after BearingClearance); the drop-down
    # lists the catalog names.
    InputSpec("planet_bearing", "Planet bearing", "choice", "605ZZ", choices=catalog_names()),
    InputSpec("shaft_bearing", "Shaft bearing", "choice", "605ZZ", choices=catalog_names()),
    InputSpec("seat_chamfer", "Seat chamfer", "length", 0.5),
    InputSpec("edge_chamfer", "Edge chamfer", "length", 0.5),
    InputSpec("carrier_wall", "Carrier wall", "length", 3),
    InputSpec("ring_wall", "Ring wall", "length", 7.1),
    InputSpec("output_shaft_length", "Output shaft length", "length", 12),
    # Directive (docs/planetarygearbox/directives.md): the mounting ears are on by default and a check box turns them
    # off. The gallery has only EarCount (0 = no ears); an unchecked box gives 0, see params_from_values.
    InputSpec(EARS_ID, "Mounting ears", "bool", 1),
    InputSpec("ear_count", "Ear count", "count", 3, needs=EARS_ID),
    InputSpec("ear_bore_diameter", "Ear bore diameter", "length", 4, needs=EARS_ID),
    InputSpec("backlash", "Backlash", "length", 0.15),
    # Directive: an extra option, off by default, that splits every carrier pin and shaft in two. Not a gallery input.
    InputSpec(SPLIT_ID, "Split pins/shafts", "bool", 0),
    # Directive: an extra option, off by default, that adds the ring's sacrificial bridge layers (docs in
    # decad-converter: docs/sacrificial-bridging.md). The ring is the model's only body with bridgeable holes.
    InputSpec(BRIDGING_ID, "Sacrificial bridging", "bool", 0),
)


def params_from_values(values: dict[str, float | str]) -> Params:
    """Build Params from dialog values: lengths in mm, angle in rad, counts as int, scalars as float.

    A "bool" value is not a Params field. It switches off every input that needs it: with the ears box unchecked
    the ear count is 0, the gallery's way to leave the ring a plain cylinder."""
    kwargs: dict[str, float | int | str] = {}
    for spec in INPUT_SPECS:
        if spec.kind == "bool":
            continue
        v = values[spec.id]
        if spec.kind == "choice":
            kwargs[spec.id] = str(v)
        else:
            kwargs[spec.id] = int(v) if spec.kind == "count" else float(v)
    if not values[EARS_ID]:
        kwargs["ear_count"] = 0
    kwargs["split_pins_shafts"] = bool(values[SPLIT_ID])
    kwargs["sacrificial_bridging"] = bool(values[BRIDGING_ID])
    return Params(**kwargs)  # pyright: ignore[reportArgumentType]


def kit_input_values(planet_bearing: str, shaft_bearing: str) -> dict[str, float]:
    """The kit-dependent input values of the kit with these bearings, by input id (Params units); {} for no such kit."""
    kit = kit_for(planet_bearing, shaft_bearing)
    if kit is None:
        return {}
    p = default_params_for(kit.name)
    return {f: float(getattr(p, f)) for f in kit_dependent_fields()}


def status_html(messages: list[str]) -> str:
    """The status box text: one error line per message, "" for none."""
    return "<br>".join(f"<b>Error:</b> {html.escape(m)}" for m in messages)


def status_rows(messages: list[str]) -> int:
    """Rows of the status box: two per message, at least 2 and at most 12."""
    return max(2, min(12, 2 * len(messages)))
