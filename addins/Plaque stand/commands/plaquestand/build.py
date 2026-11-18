"""Orchestration: creates the plaque stand component and its container components, then builds the bodies.

# Deviation: no parameter table and no sketch dimensions or constraints; plain numbers are used throughout
(docs/plaquestand/deviations.md, owner decision as for the planetary gearbox).
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
from ...lib.gen.params import Dimensions, Params
from ...lib.gen.validate import derive
from . import checks, fusion, parts


class Log(typing.Protocol):
    enabled: bool

    def write(self, event: str, fields: list[tuple[str, object]]) -> None: ...


Built = tuple[str, adsk.fusion.BRepBody]  # (body name, body)


@dataclasses.dataclass
class BuildContext:
    comp: adsk.fusion.Component  # receives the current body's sketches and features
    top: adsk.fusion.Component  # the Plaque stand component
    p: Params
    dm: Dimensions
    log: Log
    placement_axes: tuple = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))  # no placement
    part: str = ""
    container_comps: dict[str, adsk.fusion.Component] = dataclasses.field(default_factory=dict)


def build_stand(design: adsk.fusion.Design, p: Params, log: Log) -> None:
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise fusion.BuildError("switch the design to parametric (capture design history) and run again")
    started = time.time()
    dm = derive(p)
    # The gallery has no placement input, so the stand's component sits at the origin.
    occ = design.rootComponent.occurrences.addNewComponent(fusion.frame_matrix(None))
    top = occ.component
    top.name = bodies.TOP_NAME
    ctx = BuildContext(comp=top, top=top, p=p, dm=dm, log=log)
    # [containers] One sub-component per container, made before any body.
    for name in bodies.CONTAINERS:
        ctx.container_comps[name] = fusion.new_component(top, name).component

    built: list[Built] = []
    for name in bodies.BODY_NAMES:
        ctx.part = name
        ctx.comp = ctx.container_comps[bodies.BODY_CONTAINER[name]]
        body = parts.build_part(ctx, name)
        body.name = name
        built.append((name, body))

    count = top.bRepBodies.count + sum(c.bRepBodies.count for c in ctx.container_comps.values())
    if count != bodies.EXPECTED_BODY_COUNT:
        raise fusion.BuildError(f"expected {bodies.EXPECTED_BODY_COUNT} bodies, found {count}")
    for name, body in built:
        if not body.isSolid:
            raise fusion.BuildError(f"{name}: result is not a solid")
    checks.run_all(ctx, built, time.time() - started)
