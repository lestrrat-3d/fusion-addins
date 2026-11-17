"""Orchestration: creates the turbine fan component and its container components, then builds the bodies.

# Deviation: no parameter table and no sketch dimensions or constraints; plain numbers are used throughout
(docs/turbinefan/deviations.md, owner decision as for the planetary gearbox).
# Deviation: the gallery's NewDocument chain tolerance has no Fusion counterpart and is not used.
# Deviation: containers are sub-components of the top component at the identity transform, created before the first
body; each body is built in its container's component, because Fusion groups bodies only through components.
"""

from __future__ import annotations

import dataclasses
import time
import typing

import adsk.fusion

from ...lib.gen import bodies
from ...lib.gen.clutch.constants import COVER_TO
from ...lib.gen.constants import CLUTCH_MOUNT
from ...lib.gen.params import Dimensions, Frame, Params, frame_axes, mount_frame, point_at
from ...lib.gen.validate import derive
from . import checks, clutch_build, fusion, parts


class Log(typing.Protocol):
    enabled: bool

    def write(self, event: str, fields: list[tuple[str, object]]) -> None: ...


Built = tuple[str, adsk.fusion.BRepBody]  # (body name, body)


@dataclasses.dataclass
class BuildContext:
    comp: adsk.fusion.Component  # receives the current body's sketches and features
    top: adsk.fusion.Component  # the Turbine fan component
    p: Params
    dm: Dimensions
    log: Log
    placement_axes: tuple = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    part: str = ""
    container_comps: dict[str, adsk.fusion.Component] = dataclasses.field(default_factory=dict)


def build_fan(design: adsk.fusion.Design, p: Params, log: Log) -> None:
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise fusion.BuildError("switch the design to parametric (capture design history) and run again")
    started = time.time()
    dm = derive(p)
    # Directive: the selected point is the hub's front face in a shaft mount (docs/turbinefan/directives.md).
    placement = point_at(p.placement, dm.size.hub_length)
    if p.mount == CLUTCH_MOUNT:
        # Deviation: the clutch mount builds the one-way clutch with its adapter ring first, in its own top component,
        # because the gallery's Build leaves it to the caller, who builds it in a separate document. The selections
        # place the clutch, and the fan sits on it through MountFrame (docs/turbinefan/deviations.md).
        if p.clutch is None:
            raise fusion.BuildError("the clutch mount needs the clutch inputs")
        # Directive: in a clutch mount the selected point is where the clutch cover ends, its outer face, so the
        # clutch frame sits COVER_TO behind it (docs/turbinefan/directives.md).
        clutch_frame = point_at(p.placement, COVER_TO)
        # Directive: the one `Sacrificial bridging` box of the fan decides the clutch's layers too.
        clutch_p = dataclasses.replace(p.clutch, placement=clutch_frame, adapter=True,
                                       sacrificial_bridging=p.sacrificial_bridging)
        clutch_build.build_clutch(design, clutch_p, log)
        placement = mount_frame(clutch_frame)
    # The placement frame becomes the occurrence transform. Bodies stay in the component's own coordinates, so the
    # checks compare in the fan's local frame and need no conversion.
    # Deviation: placement by two selections instead of an r3.Frame (docs/turbinefan/deviations.md).
    occ = design.rootComponent.occurrences.addNewComponent(fusion.frame_matrix(placement))
    top = occ.component
    top.name = bodies.TOP_NAME
    ctx = BuildContext(comp=top, top=top, p=p, dm=dm, log=log, placement_axes=frame_axes(placement or Frame()))
    # [containers] One sub-component per container, made before any body.
    for name in bodies.CONTAINERS:
        ctx.container_comps[name] = fusion.new_component(top, name).component

    built: list[Built] = []

    ctx.part = bodies.HUB
    ctx.comp = ctx.container_comps[bodies.HUB_CONTAINER]
    hub = parts.build_hub(ctx)
    hub.name = bodies.HUB
    built.append((bodies.HUB, hub))

    ctx.part = "Blades"
    ctx.comp = ctx.container_comps[bodies.BLADES_CONTAINER]
    for name, blade in zip(bodies.BLADES, parts.build_blades(ctx)):
        blade.name = name
        built.append((name, blade))

    for name in bodies.bolts(p.mount) + bodies.nuts(p.mount):
        ctx.part = name
        ctx.comp = ctx.container_comps[bodies.container_of(name)]
        body = parts.build_fastener(ctx, name)
        body.name = name
        built.append((name, body))

    expected = bodies.expected_body_count(p.mount)
    count = top.bRepBodies.count + sum(c.bRepBodies.count for c in ctx.container_comps.values())
    if count != expected:
        raise fusion.BuildError(f"expected {expected} bodies, found {count}")
    for name, body in built:
        if not body.isSolid:
            raise fusion.BuildError(f"{name}: result is not a solid")
    checks.run_all(ctx, built, time.time() - started)
