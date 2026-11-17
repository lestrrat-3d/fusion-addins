"""The command dialog: adds the inputs from INPUT_SPECS, reads them back as Params, shows validation status.

# Deviation: input errors are checked here, before building, because Fusion validates command inputs before execute;
messages are the gallery's without the `turbinefan: ` prefix (docs/turbinefan/deviations.md)."""

from __future__ import annotations

import html

import dataclasses

import adsk.core
import adsk.fusion

from ...lib.gen.constants import CLUTCH_MOUNT
from ...lib.gen.inputs import CLUTCH_IDS, INPUT_SPECS, MOUNTS, SHAFT_MOUNT_IDS, params_from_values
from ...lib.gen.params import Params, Vec3, placement_frame
from ...lib.gen.validate import ValidationError, validate

STATUS_ID = "status"
BUILD_ID = "build"
ORIGIN_ID = "placement_origin"
AXIS_ID = "placement_axis"
FLIP_ID = "placement_flip"
# The placement selections in dialog order. Once one has a selection, the next one takes focus.
PLACEMENT_IDS = (ORIGIN_ID, AXIS_ID)

_MM_PER_CM = 10.0


def add_inputs(inputs: adsk.core.CommandInputs, build_label: str) -> None:
    """Add the placement selections, then one input per INPUT_SPECS entry in order, then the read-only text boxes.

    The placement selections come first, as in the other add-ins."""
    # Deviation: placement is chosen in the model (a point and an axis) instead of typing the gallery's frame values
    # (docs/turbinefan/deviations.md). Both empty = world origin, axis +Z.
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
    # Directive: a check box turns the build to the opposite direction along the axis (docs/turbinefan/directives.md).
    inputs.addBoolValueInput(FLIP_ID, "Flip direction", True, "", False)
    for spec in INPUT_SPECS:
        if spec.kind == "bool":
            inputs.addBoolValueInput(spec.id, spec.label, True, "", bool(spec.default))
        elif spec.kind == "choice":
            dd = inputs.addDropDownCommandInput(spec.id, spec.label, adsk.core.DropDownStyles.TextListDropDownStyle)
            for name in spec.choices:
                dd.listItems.add(name, name == spec.default, "")
        elif spec.kind == "angle":
            inputs.addValueInput(spec.id, spec.label, "deg", adsk.core.ValueInput.createByString(f"{spec.default} deg"))
        else:
            inputs.addValueInput(spec.id, spec.label, "mm", adsk.core.ValueInput.createByString(f"{spec.default} mm"))
    inputs.addTextBoxCommandInput(STATUS_ID, "", "", 2, True)
    inputs.addTextBoxCommandInput(BUILD_ID, "", build_label, 1, True)
    update_mount_inputs(inputs)


def update_mount_inputs(inputs: adsk.core.CommandInputs) -> None:
    """Show the inputs the chosen mount uses and hide the others.

    # Deviation: the clutch mount builds the clutch too, so it takes the clutch's shaft, freewheel and bore clearance
    instead of the fan's shaft, hand and bore inputs (docs/turbinefan/deviations.md)."""
    clutch = _selected_name(inputs, "mount") == MOUNTS[CLUTCH_MOUNT]
    for input_id, visible in [(i, not clutch) for i in SHAFT_MOUNT_IDS] + [(i, clutch) for i in CLUTCH_IDS]:
        item = inputs.itemById(input_id)
        if item is not None:
            item.isVisible = visible


def advance_placement_focus(inputs: adsk.core.CommandInputs, changed: adsk.core.CommandInput | None) -> None:
    """A placement selection that gets a selection hands the focus to
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
    flip = adsk.core.BoolValueCommandInput.cast(inputs.itemById(FLIP_ID))
    if flip is not None and flip.value:
        # No axis selected means +Z, so the flip builds towards -Z.
        x, y, z = axis if axis is not None else (0.0, 0.0, 1.0)
        axis = (-x, -y, -z)
    return placement_frame(origin, axis)


def _selected_name(inputs: adsk.core.CommandInputs, input_id: str) -> str:
    """Name of the selected item of a drop-down input, "" when it has none."""
    dd = adsk.core.DropDownCommandInput.cast(inputs.itemById(input_id))
    item = dd.selectedItem if dd is not None else None
    return item.name if item is not None else ""


def read_params(inputs: adsk.core.CommandInputs) -> tuple[Params | None, str]:
    """Return (params, "") when the inputs pass the gallery's rules, else (None, first failing message)."""
    values: dict[str, float | str] = {}
    for spec in INPUT_SPECS:
        if spec.kind == "bool":
            values[spec.id] = float(adsk.core.BoolValueCommandInput.cast(inputs.itemById(spec.id)).value)
            continue
        if spec.kind == "choice":
            values[spec.id] = _selected_name(inputs, spec.id)
            continue
        vin =adsk.core.ValueCommandInput.cast(inputs.itemById(spec.id))
        if not vin.isValidExpression:
            return None, f"{spec.label}: invalid value"
        # Value inputs return database units: centimeters for lengths, radians for angles.
        values[spec.id] = vin.value if spec.kind == "angle" else vin.value * _MM_PER_CM
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
