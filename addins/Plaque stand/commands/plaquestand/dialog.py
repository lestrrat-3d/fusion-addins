"""The command dialog: adds the inputs from INPUT_SPECS, reads them back as Params, shows validation status.

# Deviation: input errors are checked here, before building, because Fusion validates command inputs before execute;
messages are the gallery's without the `plaquestand: ` prefix (docs/plaquestand/deviations.md)."""

from __future__ import annotations

import html

import adsk.core

from ...lib.gen.inputs import INPUT_SPECS, params_from_values
from ...lib.gen.params import Params
from ...lib.gen.validate import ValidationError, validate

STATUS_ID = "status"
BUILD_ID = "build"

_MM_PER_CM = 10.0


def add_inputs(inputs: adsk.core.CommandInputs, build_label: str) -> None:
    """Add one input per INPUT_SPECS entry in order, then the read-only text boxes."""
    for spec in INPUT_SPECS:
        if spec.kind == "angle":
            inputs.addValueInput(spec.id, spec.label, "deg", adsk.core.ValueInput.createByString(f"{spec.default} deg"))
        else:
            inputs.addValueInput(spec.id, spec.label, "mm", adsk.core.ValueInput.createByString(f"{spec.default} mm"))
    inputs.addTextBoxCommandInput(STATUS_ID, "", "", 2, True)
    inputs.addTextBoxCommandInput(BUILD_ID, "", build_label, 1, True)


def read_params(inputs: adsk.core.CommandInputs) -> tuple[Params | None, str]:
    """Return (params, "") when the inputs pass the gallery's rules, else (None, first failing message)."""
    values: dict[str, float] = {}
    for spec in INPUT_SPECS:
        vin = adsk.core.ValueCommandInput.cast(inputs.itemById(spec.id))
        if not vin.isValidExpression:
            return None, f"{spec.label}: invalid value"
        # Value inputs return database units: centimeters for lengths, radians for angles.
        values[spec.id] = vin.value if spec.kind == "angle" else vin.value * _MM_PER_CM
    p = params_from_values(values)
    try:
        validate(p)
    except ValidationError as e:
        return None, str(e)
    return p, ""


def show_status(inputs: adsk.core.CommandInputs, p: Params | None, err: str) -> None:
    status = adsk.core.TextBoxCommandInput.cast(inputs.itemById(STATUS_ID))
    status.formattedText = f"<b>Error:</b> {html.escape(err)}" if err else ""
