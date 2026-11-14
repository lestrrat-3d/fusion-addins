"""The command dialog: adds the inputs from INPUT_SPECS, reads them back as Params, shows validation status."""

from __future__ import annotations

import html

import dataclasses

import adsk.core
import adsk.fusion

from ...lib.gen.inputs import INPUT_SPECS, params_from_values
from ...lib.gen.params import Params, Vec3, default_params, kit_for, placement_frame, ratio
from ...lib.gen.validate import ValidationError, validate

RATIO_ID = "ratio"
STATUS_ID = "status"
BUILD_ID = "build"
ORIGIN_ID = "placement_origin"
AXIS_ID = "placement_axis"
# The placement selections in dialog order. Once one has a selection, the next one takes focus.
PLACEMENT_IDS = (ORIGIN_ID, AXIS_ID)

_MM_PER_CM = 10.0


def _ratio_text(p: Params) -> str:
    return f"{ratio(p):.4f} : 1"


def add_inputs(inputs: adsk.core.CommandInputs, build_label: str) -> None:
    """Add the placement selections, then one input per INPUT_SPECS entry in order, then the read-only text boxes.

    Directive (docs/planetarygearbox/directives.md): the placement selections come first."""
    # Deviation from decad-gallery: placement is chosen in the model (a point and an axis) instead of typing the
    # gallery's frame values. Both empty = world origin, axis +Z.
    origin = inputs.addSelectionInput(ORIGIN_ID, "Origin point", "Select a construction point, sketch point or vertex")
    for flt in (
        adsk.core.SelectionCommandInput.ConstructionPoints,
        adsk.core.SelectionCommandInput.SketchPoints,
        adsk.core.SelectionCommandInput.Vertices,
    ):
        origin.addSelectionFilter(flt)
    origin.setSelectionLimits(0, 1)
    origin.hasFocus = True
    axis = inputs.addSelectionInput(AXIS_ID, "Axis direction", "Select a construction axis, linear edge or planar face")
    for flt in (
        adsk.core.SelectionCommandInput.ConstructionLines,
        adsk.core.SelectionCommandInput.LinearEdges,
        adsk.core.SelectionCommandInput.PlanarFaces,
    ):
        axis.addSelectionFilter(flt)
    axis.setSelectionLimits(0, 1)
    for spec in INPUT_SPECS:
        if spec.kind == "length":
            inputs.addValueInput(spec.id, spec.label, "mm", adsk.core.ValueInput.createByString(f"{spec.default} mm"))
        elif spec.kind == "angle":
            inputs.addValueInput(spec.id, spec.label, "deg", adsk.core.ValueInput.createByString(f"{spec.default} deg"))
        elif spec.kind == "count":
            inputs.addIntegerSpinnerCommandInput(spec.id, spec.label, 0, 9999, 1, int(spec.default))
        elif spec.kind == "bool":
            inputs.addBoolValueInput(spec.id, spec.label, True, "", bool(spec.default))
        elif spec.kind == "choice":
            drop = inputs.addDropDownCommandInput(spec.id, spec.label, adsk.core.DropDownStyles.TextListDropDownStyle)
            for i, name in enumerate(spec.choices):
                drop.listItems.add(name, i == int(spec.default))
        else:
            inputs.addValueInput(spec.id, spec.label, "", adsk.core.ValueInput.createByReal(spec.default))
    sync_dependent_inputs(inputs)
    inputs.addTextBoxCommandInput(RATIO_ID, "Reduction", _ratio_text(default_params()), 1, True)
    inputs.addTextBoxCommandInput(STATUS_ID, "", "", 2, True)
    inputs.addTextBoxCommandInput(BUILD_ID, "", build_label, 1, True)


def sync_dependent_inputs(inputs: adsk.core.CommandInputs) -> None:
    """Directive (docs/planetarygearbox/directives.md): an input that needs a check box is disabled while the box is
    unchecked. With the ears box unchecked the ear count and the ear bore diameter cannot be edited."""
    for spec in INPUT_SPECS:
        if not spec.needs:
            continue
        box = adsk.core.BoolValueCommandInput.cast(inputs.itemById(spec.needs))
        dependent = inputs.itemById(spec.id)
        if box is not None and dependent is not None:
            dependent.isEnabled = box.value


BEARING_IDS = ("planet_bearing", "shaft_bearing")


def apply_kit_teeth(inputs: adsk.core.CommandInputs, changed: adsk.core.CommandInput | None) -> None:
    """Deviation (docs/planetarygearbox/deviations.md, Bearing kits): choosing a bearing sets the sun, planet and ring
    teeth to the gallery kit for the two bearings, so the pair passes the fit checks. The teeth stay editable."""
    if changed is None or changed.id not in BEARING_IDS:
        return
    names = [adsk.core.DropDownCommandInput.cast(inputs.itemById(i)).selectedItem.name for i in BEARING_IDS]
    kit = kit_for(names[0], names[1])
    if kit is None:
        return
    for input_id, teeth in (("sun_teeth", kit.sun_teeth), ("planet_teeth", kit.planet_teeth),
                            ("ring_teeth", kit.ring_teeth)):
        adsk.core.IntegerSpinnerCommandInput.cast(inputs.itemById(input_id)).value = teeth


def advance_placement_focus(inputs: adsk.core.CommandInputs, changed: adsk.core.CommandInput | None) -> None:
    """Directive (docs/planetarygearbox/directives.md): a placement selection that gets a selection hands the focus to
    the next placement selection. The last one, and any other input, leave the focus alone."""
    if changed is None or changed.id not in PLACEMENT_IDS:
        return
    sel = adsk.core.SelectionCommandInput.cast(changed)
    if sel is None or sel.selectionCount == 0:
        return
    index = PLACEMENT_IDS.index(changed.id) + 1
    if index >= len(PLACEMENT_IDS):
        return
    following = adsk.core.SelectionCommandInput.cast(inputs.itemById(PLACEMENT_IDS[index]))
    if following is not None:
        following.hasFocus = True


def _selected(inputs: adsk.core.CommandInputs, input_id: str):
    sel = adsk.core.SelectionCommandInput.cast(inputs.itemById(input_id))
    return sel.selection(0).entity if sel is not None and sel.selectionCount > 0 else None


def _mm(pt: adsk.core.Point3D) -> Vec3:
    return (pt.x * _MM_PER_CM, pt.y * _MM_PER_CM, pt.z * _MM_PER_CM)


def origin_from_entity(entity) -> Vec3:
    """World position (mm) of a construction point, sketch point or vertex. Raises ValueError otherwise."""
    cp = adsk.fusion.ConstructionPoint.cast(entity)
    if cp is not None:
        return _mm(cp.geometry)
    sp = adsk.fusion.SketchPoint.cast(entity)
    if sp is not None:
        return _mm(sp.worldGeometry)
    vx = adsk.fusion.BRepVertex.cast(entity)
    if vx is not None:
        return _mm(vx.geometry)
    raise ValueError("origin point: select a construction point, sketch point or vertex")


def axis_from_entity(entity) -> Vec3:
    """Direction (unit not required) of a construction axis, linear edge or planar face normal."""
    ca = adsk.fusion.ConstructionAxis.cast(entity)
    if ca is not None:
        d = ca.geometry.direction
        return (d.x, d.y, d.z)
    edge = adsk.fusion.BRepEdge.cast(entity)
    if edge is not None:
        line = adsk.core.Line3D.cast(edge.geometry)
        if line is None:
            raise ValueError("axis direction: the selected edge is not a straight line")
        a, b = line.startPoint, line.endPoint
        return (b.x - a.x, b.y - a.y, b.z - a.z)
    face = adsk.fusion.BRepFace.cast(entity)
    if face is not None:
        plane = adsk.core.Plane.cast(face.geometry)
        if plane is None:
            raise ValueError("axis direction: the selected face is not planar")
        n = plane.normal
        return (n.x, n.y, n.z)
    raise ValueError("axis direction: select a construction axis, linear edge or planar face")


def read_placement(inputs: adsk.core.CommandInputs):
    """The placement Frame from the two selection inputs (None when both are empty). Raises ValueError."""
    ent_o, ent_a = _selected(inputs, ORIGIN_ID), _selected(inputs, AXIS_ID)
    origin = origin_from_entity(ent_o) if ent_o is not None else None
    axis = axis_from_entity(ent_a) if ent_a is not None else None
    return placement_frame(origin, axis)


def read_params(inputs: adsk.core.CommandInputs) -> tuple[Params | None, str]:
    """Return (params, "") when the inputs pass the gallery's rules, else (None, first failing message)."""
    values: dict[str, float] = {}
    for spec in INPUT_SPECS:
        inp = inputs.itemById(spec.id)
        if spec.needs and not values[spec.needs]:
            # Disabled by its check box: the value does not count, and params_from_values ignores it or zeroes it.
            values[spec.id] = spec.default
            continue
        if spec.kind == "count":
            values[spec.id] = float(adsk.core.IntegerSpinnerCommandInput.cast(inp).value)
            continue
        if spec.kind == "bool":
            values[spec.id] = float(adsk.core.BoolValueCommandInput.cast(inp).value)
            continue
        if spec.kind == "choice":
            values[spec.id] = float(adsk.core.DropDownCommandInput.cast(inp).selectedItem.index)
            continue
        vin = adsk.core.ValueCommandInput.cast(inp)
        if not vin.isValidExpression:
            return None, f"{spec.label}: invalid value"
        # Value inputs return database units: centimeters for lengths, radians for angles.
        values[spec.id] = vin.value * _MM_PER_CM if spec.kind == "length" else vin.value
    p = params_from_values(values)
    try:
        p = dataclasses.replace(p, placement=read_placement(inputs))
    except ValueError as e:
        return None, str(e)
    try:
        validate(p)
    except ValidationError as e:
        return None, str(e)
    return p, ""


def show_status(inputs: adsk.core.CommandInputs, p: Params | None, err: str) -> None:
    status = adsk.core.TextBoxCommandInput.cast(inputs.itemById(STATUS_ID))
    status.formattedText = f"<b>Error:</b> {html.escape(err)}" if err else ""
    if p is not None:
        adsk.core.TextBoxCommandInput.cast(inputs.itemById(RATIO_ID)).formattedText = _ratio_text(p)
