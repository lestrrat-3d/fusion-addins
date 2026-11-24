"""Orchestration: creates the display component and its container components, then builds the bodies.

# Deviation: no parameter table and no sketch dimensions or constraints; plain numbers are used throughout
(docs/sevensegment/deviations.md, owner decision as for the planetary gearbox).
# Deviation: the gallery's NewDocument chain tolerance has no Fusion counterpart and is not used.
# Deviation: containers are sub-components of the top component (or of their parent container) at the identity
transform, created before the first body; each body is built in its container's component, because Fusion groups
bodies only through components.
# Every body of `bodies.ALL_SPECS` is built, and the count is checked against `bodies.EXPECTED_BODY_COUNT` (the
gallery's 61).
"""

from __future__ import annotations

import dataclasses
import shutil
import tempfile
import time
import typing

import adsk.core
import adsk.fusion

from ... import config
from ...lib.gen import bodies
from ...lib.gen.params import Dimensions, Frame, Params, frame_axes
from ...lib.gen.validate import derive
from . import checks, fusion, isolate, parts


class Log(typing.Protocol):
    enabled: bool

    def write(self, event: str, fields: list[tuple[str, object]]) -> None: ...


Built = tuple[str, adsk.fusion.BRepBody]  # (body name, body)


@dataclasses.dataclass
class BuildContext:
    comp: adsk.fusion.Component  # receives the current body's sketches and features
    top: adsk.fusion.Component  # the Seven-segment display component
    p: Params
    dm: Dimensions
    log: Log
    placement_axes: tuple = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    part: str = ""
    container_comps: dict[str, adsk.fusion.Component] = dataclasses.field(default_factory=dict)
    # Prototype bodies kept for copying: key -> (body, the frame it was moved onto). See parts_flags._shared.
    shared: dict[str, tuple[adsk.fusion.BRepBody, tuple]] = dataclasses.field(default_factory=dict)


def _make_containers(ctx: BuildContext) -> None:
    """[containers] The whole container tree, made before any body: one sub-component per container, each inside its
    parent's component."""

    def make(parent: adsk.fusion.Component, nodes: tuple[bodies.Node, ...]) -> None:
        for node in nodes:
            comp = fusion.new_component(parent, node.name).component
            ctx.container_comps[node.key] = comp
            make(comp, node.children)

    make(ctx.top, bodies.TREE)


def _build(ctx: BuildContext, name: str, archives: dict[str, str]) -> adsk.fusion.BRepBody:
    """Build the body `name`: imported from its archive when it has one (a large part built in a design of its own),
    otherwise, or when the import fails, in the current container's component."""
    if name in archives:
        try:
            body = isolate.import_part(ctx, name, archives[name])
            info = parts.shared_info(ctx, name)
            if info is not None:
                ctx.shared.setdefault(info[0], (body, info[1]))  # the later bodies of this kind are copies of it
            return body
        except isolate.Unavailable as e:
            ctx.log.write("isolate", [("part", name), ("error", str(e)), ("result", "FALLBACK")])
    return parts.build_part(ctx, name)


def prepare_archives(p: Params, log: Log) -> tuple[dict[str, str], str]:
    """Phase one of an isolated build: the large parts, each built in a design of its own and exported (commands/
    sevensegment/isolate.py). Returns the archive paths by body name and the folder that holds them; the caller removes
    the folder. Run it outside a command: it opens and closes documents, which a command's undo step cannot hold."""
    started = time.time()
    folder = tempfile.mkdtemp(prefix="sevensegment_")
    try:
        first = BuildContext(comp=None, top=None, p=p, dm=derive(p), log=log)  # type: ignore[arg-type]
        names = [n for n in bodies.ALL_BODY_NAMES if isolate.wants(n)]
        names += parts.first_of_each_kind(first)  # the prototypes that the other bodies of a kind copy
        archives = isolate.export_all(first, parts.build_part, names, folder)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    log.write("timing", [("part", "isolated parts"), ("seconds", time.time() - started), ("archives", len(archives))])
    return archives, folder


def build_display(design: adsk.fusion.Design, p: Params, log: Log, archives: dict[str, str] | None = None) -> None:
    """Build the display in `design`. `archives` are the exported parts of `prepare_archives`; None makes them here when
    config asks for it, which switches documents, so the design is taken again afterwards."""
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise fusion.BuildError("switch the design to parametric (capture design history) and run again")
    started = time.time()
    dm = derive(p)
    folder = ""
    try:
        if archives is None and config.ISOLATE_PARTS:
            archives, folder = prepare_archives(p, log)
            design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
        _build_all(design, p, dm, log, started, archives or {})
    finally:
        if folder:
            shutil.rmtree(folder, ignore_errors=True)


def _build_all(design: adsk.fusion.Design, p: Params, dm: Dimensions, log: Log, started: float,
               archives: dict[str, str]) -> None:
    # The placement frame becomes the occurrence transform. Bodies stay in the component's own coordinates, so the
    # checks compare in the display's local frame and need no conversion.
    # Deviation: placement by two selections instead of an r3.Frame (docs/sevensegment/deviations.md).
    occ = design.rootComponent.occurrences.addNewComponent(fusion.frame_matrix(p.placement))
    top = occ.component
    top.name = bodies.TOP_NAME
    ctx = BuildContext(comp=top, top=top, p=p, dm=dm, log=log, placement_axes=frame_axes(p.placement or Frame()))
    _make_containers(ctx)

    built: list[Built] = []
    timeline = design.timeline
    log.write("timing", [("part", "containers"), ("seconds", time.time() - started), ("timeline", int(timeline.count))])
    for spec in bodies.ALL_SPECS:
        ctx.part = spec.name
        ctx.comp = ctx.container_comps[spec.container]
        part_started, items = time.time(), int(timeline.count)
        body = _build(ctx, spec.name, archives)
        body.name = spec.name
        built.append((spec.name, body))
        # One line per part, so a run shows where the time goes: the part's seconds and its timeline items.
        log.write("timing", [("part", spec.name), ("seconds", time.time() - part_started),
                             ("items", int(timeline.count) - items), ("timeline", int(timeline.count))])

    count = fusion.count_bodies(top)
    if count != bodies.EXPECTED_BODY_COUNT:
        raise fusion.BuildError(f"expected {bodies.EXPECTED_BODY_COUNT} bodies, found {count}")
    for name, body in built:
        if not body.isSolid:
            raise fusion.BuildError(f"{name}: result is not a solid")
    built_at = time.time()
    checks.run_all(ctx, built, built_at - started)
    log.write("timing", [("part", "checks"), ("seconds", time.time() - built_at),
                         ("timeline", int(timeline.count))])
