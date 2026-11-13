"""Orchestration: creates the escapement component and its container components, then builds the parts.

# Deviation: no parameter table and no sketch dimensions or constraints; plain numbers are used throughout
(docs/escapement/deviations.md, owner decision as for the planetary gearbox).
# Deviation: the gallery's NewDocument chain tolerance has no Fusion counterpart and is not used.
# Deviation: containers are nested sub-components of the top component at the identity transform, created before the
first part; each part is built in its container's component, because Fusion groups bodies only through components.
"""

from __future__ import annotations

import dataclasses
import time
import typing

import adsk.core
import adsk.fusion

from ...lib.gen import bodies, containers
from ...lib.gen.layout import Geometry, layout
from ...lib.gen.motion import State, state_at
from ...lib.gen.params import Params
from ...lib.gen.pose import body_poses
from . import checks, fusion, parts


class Log(typing.Protocol):
    enabled: bool

    def write(self, event: str, fields: list[tuple[str, object]]) -> None: ...


Built = tuple[str, str, adsk.fusion.BRepBody]  # (part, body name, body)


@dataclasses.dataclass
class BuildContext:
    occ: adsk.fusion.Occurrence
    comp: adsk.fusion.Component  # receives the current part's sketches and features
    top: adsk.fusion.Component  # the Graham Escapement component
    p: Params
    g: Geometry
    s: State
    log: Log
    part: str = ""
    container_comps: dict[tuple[str, ...], adsk.fusion.Component] = dataclasses.field(default_factory=dict)


def _place(ctx: BuildContext, part: str, master: adsk.fusion.BRepBody, poses) -> list[Built]:
    """Name and move the part's bodies. Several bodies: copy the master into every pose but the last, then move the
    master into the last one."""
    names = bodies.PART_BODIES[part]
    placed: list[Built] = []
    for name in names[:-1]:
        body = fusion.copy_body(ctx, master, f"{part} copy")
        fusion.move(ctx, body, poses[name], f"{part} move")
        body.name = name
        placed.append((part, name, body))
    last = names[-1]
    fusion.move(ctx, master, poses[last], f"{part} move")
    master.name = last
    placed.append((part, last, master))
    return placed


def build_escapement(design: adsk.fusion.Design, p: Params, log: Log) -> None:
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise fusion.BuildError("switch the design to parametric (capture design history) and run again")
    started = time.time()
    g = layout(p)
    s = state_at(g, p.phase)
    poses = body_poses(g, s)
    # The placement frame becomes the occurrence transform. Bodies stay in the component's own coordinates, so the
    # checks compare in the escapement's local frame and need no conversion.
    # Deviation: placement by two selections instead of an r3.Frame (docs/escapement/deviations.md).
    occ = design.rootComponent.occurrences.addNewComponent(fusion.frame_matrix(p.placement))
    top = occ.component
    top.name = containers.TOP_NAME
    ctx = BuildContext(occ=occ, comp=top, top=top, p=p, g=g, s=s, log=log)
    # [containers.go moveBodies] One sub-component per container path, parents first, made before any part.
    for path in containers.CONTAINER_PATHS:
        parent = ctx.container_comps[path[:-1]] if len(path) > 1 else top
        ctx.container_comps[path] = fusion.new_component(parent, path[-1]).component

    built: list[Built] = []
    for part in bodies.PARTS:
        ctx.part = part
        ctx.comp = ctx.container_comps[containers.container_of_part(part)]
        master = getattr(parts, f"build_{part}")(ctx)
        built += _place(ctx, part, master, poses)

    count = top.bRepBodies.count + sum(c.bRepBodies.count for c in ctx.container_comps.values())
    if count != bodies.EXPECTED_BODY_COUNT:
        raise fusion.BuildError(f"expected {bodies.EXPECTED_BODY_COUNT} bodies, found {count}")
    for _, name, body in built:
        if not body.isSolid:
            raise fusion.BuildError(f"{name}: result is not a solid")
    order = {name: i for i, name in enumerate(bodies.BODY_NAMES)}
    built.sort(key=lambda b: order[b[1]])
    checks.run_all(ctx, built, time.time() - started)
