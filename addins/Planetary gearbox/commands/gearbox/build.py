"""Orchestration: creates the gearbox component and its container components, then builds the parts.

Deviation from decad-gallery: no parameter table and no sketch dimensions; plain numbers are used throughout.
"""

from __future__ import annotations

import dataclasses
import time
import typing

import adsk.core
import adsk.fusion

from ...lib.gen import containers, layout
from ...lib.gen.dims import Dims, derive
from ...lib.gen.params import Params
from . import checks, fusion, parts

STAGE_PARTS = layout.PARTS  # all parts are built
PLACE_INSTANCES = True  # copy/move every master into its instance poses
APPLY_PLACEMENT = True  # the placement frame (from the dialog's point and axis) becomes the occurrence transform
PLACEMENT_VIA_TRANSFORM2 = False  # R7 fallback: create at the identity, then set occ.transform2 after building


class Log(typing.Protocol):
    enabled: bool

    def write(self, event: str, fields: list[tuple[str, object]]) -> None: ...


_BUILDERS = {
    "ring": parts.build_ring,
    "cover": parts.build_cover,
    "housing_bearing": parts.build_bearing,
    "input_shaft": parts.build_input_shaft,
    "bolt": parts.build_bolt,
    "nut": parts.build_nut,
    "sun": parts.build_sun,
    "planet": parts.build_planet,
    "planet_bearing": parts.build_bearing,
    "carrier_pin": parts.build_pin,
    "carrier": parts.build_carrier,
    "link_shaft": parts.build_link_shaft,
    "output_shaft": parts.build_output_shaft,
}
# The gallery places the fasteners inside buildFasteners, before the stage parts.
_HOUSING_PARTS = ("ring", "cover", "housing_bearing", "input_shaft", "bolt", "nut")


@dataclasses.dataclass
class BuildContext:
    occ: adsk.fusion.Occurrence
    comp: adsk.fusion.Component  # receives the current part's sketches and features
    box: adsk.fusion.Component  # the Planetary Gearbox component
    p: Params
    d: Dims
    log: Log
    part: str = ""
    fillet_radius: dict[str, float] = dataclasses.field(default_factory=dict)  # radius used when a ladder ran
    container_comps: dict[str, adsk.fusion.Component] = dataclasses.field(default_factory=dict)


def _place(ctx: BuildContext, part: str, master: adsk.fusion.BRepBody) -> list[tuple[str, str, adsk.fusion.BRepBody]]:
    """Copy the master into every instance pose but the last, then move the master into the last one."""
    insts = layout.instances_of(ctx.p, ctx.d, part)
    placed: list[tuple[str, str, adsk.fusion.BRepBody]] = []
    for inst in insts[:-1]:
        body = fusion.copy_body(ctx, master, f"{part} copy")
        fusion.move(ctx, body, inst.pose, f"{part} move")
        body.name = inst.name
        placed.append((part, inst.name, body))
    last = insts[-1]
    fusion.move(ctx, master, last.pose, f"{part} move")
    master.name = last.name
    placed.append((part, last.name, master))
    return placed


def build_gearbox(design: adsk.fusion.Design, p: Params, log: Log) -> None:
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise fusion.BuildError("switch the design to parametric (capture design history) and run again")
    started = time.time()
    d = derive(p)
    # The placement frame becomes the occurrence transform. Bodies stay in the component's own coordinates, so the
    # checks below compare in the gearbox's local frame and need no conversion.
    placed_frame = APPLY_PLACEMENT and p.placement is not None
    transform = fusion.frame_matrix(p.placement) if placed_frame and not PLACEMENT_VIA_TRANSFORM2 else (
        adsk.core.Matrix3D.create()
    )
    occ = design.rootComponent.occurrences.addNewComponent(transform)
    box = occ.component
    box.name = containers.GEARBOX_NAME
    ctx = BuildContext(occ=occ, comp=box, box=box, p=p, d=d, log=log)
    # [container.go moveBodies] One sub-component per gallery container, made before any part (README "Deviations").
    for name in containers.CONTAINER_NAMES:
        ctx.container_comps[name] = fusion.new_component(box, name).component

    built: list[tuple[str, str, adsk.fusion.BRepBody]] = []
    masters: list[tuple[str, adsk.fusion.BRepBody]] = []
    for part in layout.PARTS:
        if part not in STAGE_PARTS or (part == "link_shaft" and p.stages == 1):
            continue
        if part not in _BUILDERS:
            raise fusion.BuildError(f"{part}: builder is not implemented yet")
        ctx.part = part
        ctx.comp = ctx.container_comps[containers.container_of(part)]
        body = _BUILDERS[part](ctx)
        if not PLACE_INSTANCES:
            name = layout.master_name(p, d, part)
            body.name = name
            built.append((part, name, body))
        elif part in _HOUSING_PARTS:
            built += _place(ctx, part, body)
        else:
            masters.append((part, body))
    # Stage parts are placed after all of them are built [gallery build / buildHousing].
    for part, body in masters:
        ctx.part = part
        ctx.comp = ctx.container_comps[containers.container_of(part)]
        built += _place(ctx, part, body)

    if STAGE_PARTS == layout.PARTS and PLACE_INSTANCES:
        count = ctx.box.bRepBodies.count + sum(c.bRepBodies.count for c in ctx.container_comps.values())
        if count != layout.expected_body_count(p):
            raise fusion.BuildError(f"expected {layout.expected_body_count(p)} bodies, found {count}")
        for _, name, body in built:
            if not body.isSolid:
                raise fusion.BuildError(f"{name}: result is not a solid")
    checks.run_all(ctx, built, PLACE_INSTANCES, time.time() - started)
    if placed_frame and PLACEMENT_VIA_TRANSFORM2:
        occ.transform2 = fusion.frame_matrix(p.placement)
