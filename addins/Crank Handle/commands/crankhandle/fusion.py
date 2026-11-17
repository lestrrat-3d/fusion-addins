"""Thin wrappers over Fusion features, unit conversion, edge finders and matrices.

Pure code works in millimeters; Fusion works in centimeters. `cm` is the only place that converts.
"""

from __future__ import annotations

import contextlib
import math
import typing

import adsk.core
import adsk.fusion

from ...lib.gen.bodies import Found
from ...lib.gen.curves import Arc, Line, Loop, Point
from ...lib.gen import frames
from ...lib.gen.params import Frame, Vec3, frame_axes

if typing.TYPE_CHECKING:
    from .build import BuildContext

Axes = tuple[Vec3, Vec3, Vec3, Vec3]  # (origin, x, y, z)
_IDENTITY_AXES: Axes = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


class BuildError(RuntimeError):
    """A Fusion call returned nothing or a count differed from the design."""


def cm(mm: float) -> float:
    return mm / 10.0


def mm_from_cm(v: float) -> float:
    return v * 10.0


def point(x: float, y: float, z: float = 0.0) -> adsk.core.Point3D:
    """Point3D in centimeters from millimeters."""
    return adsk.core.Point3D.create(cm(x), cm(y), cm(z))


@contextlib.contextmanager
def _step(what: str):
    """Re-raise Fusion API errors as BuildError naming the step."""
    try:
        yield
    except BuildError:
        raise
    except Exception as e:
        raise BuildError(f"{what}: {e}") from e


def _collection(items: typing.Iterable[typing.Any]) -> adsk.core.ObjectCollection:
    coll = adsk.core.ObjectCollection.create()
    for item in items:
        coll.add(item)
    return coll


def new_component(parent: adsk.fusion.Component, name: str) -> adsk.fusion.Occurrence:
    """Sub-component of parent at the identity transform, named `name` [container.go ChildNamed]."""
    with _step(f"component {name}"):
        occ = parent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        if occ is None:
            raise BuildError(f"component {name}: Fusion returned no occurrence")
        occ.component.name = name
        return occ


def component_tree(comp: adsk.fusion.Component) -> tuple[int, list[Found]]:
    """Read back the sub-components of comp in occurrence order.

    Returns (bodies directly in comp, one Found per direct sub-component)."""
    with _step("container check"):
        found: list[Found] = []
        for i in range(comp.occurrences.count):
            sub = comp.occurrences.item(i).component
            bodies = sub.bRepBodies
            names = tuple(bodies.item(j).name for j in range(bodies.count))
            kids = tuple(sub.occurrences.item(j).component.name for j in range(sub.occurrences.count))
            found.append(Found(sub.name, names, kids))
        return comp.bRepBodies.count, found


def new_sketch(comp: adsk.fusion.Component, name: str) -> adsk.fusion.Sketch:
    with _step(f"sketch {name}"):
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = name
        sk.isComputeDeferred = True
        return sk


def new_sketch_xz(comp: adsk.fusion.Component, name: str) -> adsk.fusion.Sketch:
    """Sketch on the XZ plane, for sections that are revolved about the Z axis."""
    with _step(f"sketch {name}"):
        sk = comp.sketches.add(comp.xZConstructionPlane)
        sk.name = name
        sk.isComputeDeferred = True
        return sk


def new_sketch_yz(comp: adsk.fusion.Component, name: str) -> adsk.fusion.Sketch:
    """Sketch on the YZ plane, for the relief tool's side profile."""
    with _step(f"sketch {name}"):
        sk = comp.sketches.add(comp.yZConstructionPlane)
        sk.name = name
        sk.isComputeDeferred = True
        return sk


def _draw_loop(
    sk: adsk.fusion.Sketch,
    loop: Loop,
    to_sketch: typing.Callable[[Point], adsk.core.Point3D],
    origin_point: adsk.fusion.SketchPoint | None,
) -> None:
    """Draw a closed loop with one SketchPoint per distinct Point so the curves share their ends."""
    origin: Point = (0.0, 0.0)
    points: dict[Point, adsk.fusion.SketchPoint] = {}

    def sp(pt: Point) -> adsk.fusion.SketchPoint:
        if pt not in points:
            if origin_point is not None and pt == origin:
                points[pt] = origin_point
            else:
                points[pt] = sk.sketchPoints.add(to_sketch(pt))
        return points[pt]

    curves = sk.sketchCurves
    with _step(f"sketch {sk.name} draw_loop ({len(loop)} curves)"):
        for c in loop:
            if isinstance(c, Line):
                curves.sketchLines.addByTwoPoints(sp(c.start), sp(c.end))
            elif isinstance(c, Arc):
                curves.sketchArcs.addByCenterStartEnd(sp(c.center), sp(c.start), sp(c.end))


def draw_loop(sk: adsk.fusion.Sketch, loop: Loop) -> None:
    """Draw a closed loop on the XY sketch plane; (0, 0) reuses the sketch origin."""
    # Deviation: no dimensions or geometric constraints; curves sit at computed coordinates
    # (docs/crankhandle/deviations.md).
    _draw_loop(sk, loop, lambda q: point(q[0], q[1]), sk.originPoint)


def draw_loop_xz(sk: adsk.fusion.Sketch, loop: Loop) -> None:
    """Draw a closed loop of lines whose (u, v) are model (x, z) on an XZ sketch."""
    if any(not isinstance(c, Line) for c in loop):
        raise BuildError(f"sketch {sk.name}: draw_loop_xz takes lines only")
    # The XZ sketch's own axes differ from model X/Z; modelToSketchSpace converts.
    _draw_loop(sk, loop, lambda q: sk.modelToSketchSpace(point(q[0], 0.0, q[1])), None)


def draw_loop_yz(sk: adsk.fusion.Sketch, loop: Loop) -> None:
    """Draw a closed loop of lines whose (u, v) are model (y, z) on a YZ sketch."""
    if any(not isinstance(c, Line) for c in loop):
        raise BuildError(f"sketch {sk.name}: draw_loop_yz takes lines only")
    # The YZ sketch's own axes differ from model Y/Z; modelToSketchSpace converts.
    _draw_loop(sk, loop, lambda q: sk.modelToSketchSpace(point(0.0, q[0], q[1])), None)


def draw_circle(sk: adsk.fusion.Sketch, center: Point, radius: float) -> None:
    with _step(f"sketch {sk.name} draw_circle"):
        sk.sketchCurves.sketchCircles.addByCenterRadius(point(center[0], center[1]), cm(radius))


def draw_rectangle(sk: adsk.fusion.Sketch, a: Point, b: Point) -> None:
    with _step(f"sketch {sk.name} draw_rectangle"):
        sk.sketchCurves.sketchLines.addTwoPointRectangle(point(a[0], a[1]), point(b[0], b[1]))


def profile_with_loops(sk: adsk.fusion.Sketch, loops: int, what: str, only: bool = False) -> adsk.fusion.Profile:
    """The single profile with `loops` loops. `only` also requires it to be the sketch's only profile."""
    sk.isComputeDeferred = False
    profiles = sk.profiles
    found = [profiles.item(i) for i in range(profiles.count) if profiles.item(i).profileLoops.count == loops]
    if len(found) != 1 or (only and profiles.count != 1):
        counts = [profiles.item(i).profileLoops.count for i in range(profiles.count)]
        raise BuildError(
            f"{what}: expected one profile with {loops} loops (only={only}), sketch has loop counts {counts}"
        )
    return found[0]


def extrude(
    ctx: BuildContext, profile: adsk.fusion.Profile, z: float, length: float, what: str
) -> adsk.fusion.BRepBody:
    """Extrude profile into a new body from z (mm) along +Z for length (mm)."""
    with _step(what):
        inp = ctx.comp.features.extrudeFeatures.createInput(
            profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        if z != 0:
            inp.startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(cm(z)))
        inp.setOneSideExtent(
            adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(cm(length))),
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
        )
        feat = ctx.comp.features.extrudeFeatures.add(inp)
        if feat is None or feat.bodies.count != 1:
            raise BuildError(f"{what}: extrude produced {0 if feat is None else feat.bodies.count} bodies, expected 1")
        return feat.bodies.item(0)


def extrude_symmetric(
    ctx: BuildContext, profile: adsk.fusion.Profile, length: float, what: str
) -> adsk.fusion.BRepBody:
    """Extrude profile into a new body, `length` (mm) in all, half on each side of its sketch plane."""
    with _step(what):
        inp = ctx.comp.features.extrudeFeatures.createInput(
            profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        inp.setSymmetricExtent(adsk.core.ValueInput.createByReal(cm(length)), True)
        feat = ctx.comp.features.extrudeFeatures.add(inp)
        if feat is None or feat.bodies.count != 1:
            raise BuildError(f"{what}: extrude produced {0 if feat is None else feat.bodies.count} bodies, expected 1")
        return feat.bodies.item(0)


def revolve(ctx: BuildContext, profile: adsk.fusion.Profile, what: str) -> adsk.fusion.BRepBody:
    """Full turn of profile about the component Z axis into a new body."""
    with _step(what):
        inp = ctx.comp.features.revolveFeatures.createInput(
            profile, ctx.comp.zConstructionAxis, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        if not inp.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg")):
            raise BuildError(f"{what}: Fusion rejected the revolve angle")
        feat = ctx.comp.features.revolveFeatures.add(inp)
        count = 0 if feat is None else feat.bodies.count
        if count != 1:
            raise BuildError(f"{what}: revolve produced {count} bodies, expected 1")
        return feat.bodies.item(0)


def _combine(
    ctx: BuildContext,
    operation: int,
    target: adsk.fusion.BRepBody,
    tools: list[adsk.fusion.BRepBody],
    what: str,
) -> adsk.fusion.BRepBody:
    with _step(what):
        inp = ctx.comp.features.combineFeatures.createInput(target, _collection(tools))
        inp.operation = operation
        inp.isKeepToolBodies = False
        feat = ctx.comp.features.combineFeatures.add(inp)
        if feat is None or feat.bodies.count != 1:
            raise BuildError(f"{what}: combine produced {0 if feat is None else feat.bodies.count} bodies, expected 1")
        return feat.bodies.item(0)


def join(
    ctx: BuildContext, target: adsk.fusion.BRepBody, tools: list[adsk.fusion.BRepBody], what: str
) -> adsk.fusion.BRepBody:
    return _combine(ctx, adsk.fusion.FeatureOperations.JoinFeatureOperation, target, tools, what)


def _bounds_mm(body: adsk.fusion.BRepBody) -> tuple[float, ...]:
    box = body.preciseBoundingBox
    lo, hi = box.minPoint, box.maxPoint
    return tuple(round(mm_from_cm(v), 3) for v in (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z))


def cut(
    ctx: BuildContext, target: adsk.fusion.BRepBody, tools: list[adsk.fusion.BRepBody], what: str
) -> adsk.fusion.BRepBody:
    """Cut tools from target. A cut that removes no material is logged as a `cut` FAIL line with the tool's bounds,
    because Fusion accepts such a cut without an error."""
    before = target.volume
    bounds = [_bounds_mm(t) for t in tools]
    result = _combine(ctx, adsk.fusion.FeatureOperations.CutFeatureOperation, target, tools, what)
    removed = (before - result.volume) * 1000.0  # cm^3 -> mm^3
    if removed < 1e-3:
        ctx.log.write("cut", [("step", what), ("removed_mm3", removed), ("tool_bounds", bounds[0]),
                              ("target_bounds", _bounds_mm(result)), ("result", "FAIL")])
    return result


def fillet(ctx: BuildContext, edges: list[adsk.fusion.BRepEdge], radius: float, what: str) -> None:
    with _step(what):
        inp = ctx.comp.features.filletFeatures.createInput()
        inp.isRollingBallCorner = True
        inp.edgeSetInputs.addConstantRadiusEdgeSet(
            _collection(edges), adsk.core.ValueInput.createByReal(cm(radius)), False
        )
        ctx.comp.features.filletFeatures.add(inp)


def chamfer(
    ctx: BuildContext,
    edges: list[adsk.fusion.BRepEdge],
    distance: float,
    what: str,
    tangent_chain: bool = True,
) -> None:
    """Equal-distance chamfer of exactly `edges` when tangent_chain is False, else also their tangent chains."""
    with _step(what):
        inp = ctx.comp.features.chamferFeatures.createInput2()
        if not inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            _collection(edges), adsk.core.ValueInput.createByReal(cm(distance)), tangent_chain
        ):
            raise BuildError(f"{what}: Fusion rejected the chamfer edge set")
        feat = ctx.comp.features.chamferFeatures.add(inp)
        if feat is None:
            raise BuildError(f"{what}: Fusion created no chamfer")


def frame_matrix(frame: Frame | None) -> adsk.core.Matrix3D:
    origin, x, y, z = frame_axes(frame or Frame())
    return _matrix((origin, x, y, z))


def _matrix(axes: Axes) -> adsk.core.Matrix3D:
    origin, x, y, z = axes
    m = adsk.core.Matrix3D.create()
    m.setWithCoordinateSystem(
        point(origin[0], origin[1], origin[2]),
        adsk.core.Vector3D.create(*x),
        adsk.core.Vector3D.create(*y),
        adsk.core.Vector3D.create(*z),
    )
    return m


def move(
    ctx: BuildContext, body: adsk.fusion.BRepBody, axes: Axes, what: str
) -> adsk.fusion.BRepBody:
    """Free move of body from the origin frame onto `axes` (origin, x, y, z) of its component; skipped for the
    identity.

    Fusion applies the transform in the top-level frame, so it is conjugated by the top component's placement
    (frames.conjugate). Returns the moved body as the move feature reports it, so later features use that reference."""
    if axes == _IDENTITY_AXES:
        return body
    with _step(what):
        inp = ctx.comp.features.moveFeatures.createInput2(_collection([body]))
        if not inp.defineAsFreeMove(_matrix(frames.conjugate(axes, ctx.placement_axes))):
            raise BuildError(f"{what}: Fusion rejected the move transform")
        feat = ctx.comp.features.moveFeatures.add(inp)
        if feat is not None and feat.bodies.count == 1:
            return feat.bodies.item(0)
        return body


def _plane_at_y(comp: adsk.fusion.Component, y: float, what: str, made: list) -> adsk.fusion.ConstructionPlane:
    """The plane y = `y` (mm) of the component, a copy of the XZ plane offset along its normal.

    A parametric design takes no setByPlane (knowledge/sketch-and-features.md), so the XZ plane is offset. Its normal
    runs along +Y or -Y, so the offset is read from its geometry and the result is read back and checked. Every plane
    it adds goes into `made`."""
    base = comp.xZConstructionPlane
    g = base.geometry
    if abs(abs(g.normal.y) - 1.0) > 1e-6:
        raise BuildError(f"{what}: the XZ plane's normal is not along Y")
    dist = (cm(y) - g.origin.y) * g.normal.y
    if abs(dist) < 1e-9:
        return base
    inp = comp.constructionPlanes.createInput()
    if not inp.setByOffset(base, adsk.core.ValueInput.createByReal(dist)):
        raise BuildError(f"{what}: Fusion rejected the offset construction plane")
    plane = comp.constructionPlanes.add(inp)
    made.append(plane)
    off = abs(plane.geometry.origin.y - cm(y))
    if off > 1e-6 or abs(abs(plane.geometry.normal.y) - 1.0) > 1e-6:
        raise BuildError(f"{what}: split plane is {mm_from_cm(off):.4f} mm off y = {y:g}")
    return plane


def split_body(
    ctx: BuildContext, body: adsk.fusion.BRepBody, y: float, what: str
) -> tuple[adsk.fusion.BRepBody, adsk.fusion.BRepBody]:
    """Cut a body in two along the plane y = `y` (mm) of its component, which holds the pin's axis.

    Returns the half on the -Y side, then the half on the +Y side."""
    made: list = []
    with _step(what):
        tool = _plane_at_y(ctx.comp, y, what, made)
        inp = ctx.comp.features.splitBodyFeatures.createInput(body, tool, True)
        feat = ctx.comp.features.splitBodyFeatures.add(inp)
        count = 0 if feat is None else feat.bodies.count
        if count != 2:
            raise BuildError(f"{what}: split produced {count} bodies, expected 2")
        for plane in made:
            plane.isLightBulbOn = False  # the plane is a tool only; hide it once used

        def side(b: adsk.fusion.BRepBody) -> float:
            box = b.boundingBox
            return (box.minPoint.y + box.maxPoint.y) / 2

        halves = sorted([feat.bodies.item(0), feat.bodies.item(1)], key=side)
        return halves[0], halves[1]


def circular_edges_at(
    body: adsk.fusion.BRepBody, radius: float, z: float, tol: float = 1e-3
) -> list[adsk.fusion.BRepEdge]:
    """Circle or arc edges centered on the Z axis at height z (mm) with the given radius (mm)."""
    found: list[adsk.fusion.BRepEdge] = []
    for i in range(body.edges.count):
        edge = body.edges.item(i)
        g = edge.geometry
        # A degenerate edge (for example a revolve's seam point) has no curve geometry.
        if g is None or g.curveType not in (
            adsk.core.Curve3DTypes.Circle3DCurveType,
            adsk.core.Curve3DTypes.Arc3DCurveType,
        ):
            continue
        g = adsk.core.Circle3D.cast(g) or adsk.core.Arc3D.cast(g)
        c = g.center
        if (
            abs(mm_from_cm(c.x)) <= tol
            and abs(mm_from_cm(c.y)) <= tol
            and abs(mm_from_cm(c.z) - z) <= tol
            and abs(mm_from_cm(g.radius) - radius) <= tol
        ):
            found.append(edge)
    return found


def face_loops(
    body: adsk.fusion.BRepBody, z: float, min_area: float, what: str, tol: float = 1e-3
) -> list[tuple[bool, list[adsk.fusion.BRepEdge]]]:
    """Loops of the planar faces of body that face along Z at height z (mm) with at least min_area (mm^2).

    Each loop is (is_outer, edges). An edge without curve geometry (a degenerate edge) is skipped
    (knowledge/revolve-and-edges.md)."""
    out: list[tuple[bool, list[adsk.fusion.BRepEdge]]] = []
    with _step(f"{what} faces"):
        for i in range(body.faces.count):
            face = body.faces.item(i)
            g = face.geometry
            if g is None or g.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
                continue
            plane = adsk.core.Plane.cast(g)
            nrm = plane.normal
            if abs(nrm.z) < (1 - 1e-9) * nrm.length:
                continue
            if abs(mm_from_cm(plane.origin.z) - z) > tol:
                continue
            if face.area * 100.0 < min_area:  # cm^2 -> mm^2
                continue
            for j in range(face.loops.count):
                loop = face.loops.item(j)
                edges = [loop.edges.item(k) for k in range(loop.edges.count)]
                out.append((loop.isOuter, [e for e in edges if e.geometry is not None]))
    return out


def bore_rim_edges(
    body: adsk.fusion.BRepBody, bore_radius: float, what: str, want_lines: int = 1, tol: float = 1e-3
) -> list:
    """The edges of the D bore's rim in the back face: every edge with both end points at z = 0 and within
    `bore_radius` (mm) of the Z axis. The slit's walls leave the rim, so their far end points fall outside. The slit
    leaves two arcs and the flat, or with a double flat two arcs and three lines, because it splits the -Y flat. Any
    other count is an error."""
    found: list[adsk.fusion.BRepEdge] = []
    arcs = lines = 0
    for i in range(body.edges.count):
        edge = body.edges.item(i)
        g = edge.geometry
        if g is None or edge.startVertex is None or edge.endVertex is None:
            continue
        ends = [edge.startVertex.geometry, edge.endVertex.geometry]
        if any(abs(mm_from_cm(q.z)) > tol or math.hypot(mm_from_cm(q.x), mm_from_cm(q.y)) > bore_radius + tol
               for q in ends):
            continue
        if g.curveType == adsk.core.Curve3DTypes.Arc3DCurveType:
            arcs += 1
        elif g.curveType == adsk.core.Curve3DTypes.Line3DCurveType:
            lines += 1
        else:
            raise BuildError(f"{what}: unexpected edge type {g.curveType}")
        found.append(edge)
    if arcs != 2 or lines != want_lines:
        raise BuildError(f"{what}: found {arcs} arcs and {lines} lines, expected 2 and {want_lines}")
    return found


def outer_face_edges(
    body: adsk.fusion.BRepBody,
    outer_z: float,
    top_z: float,
    top_y: float,
    ramp_foot: float,
    pin_y: float,
    pin_hole_r: float,
    what: str,
    tol: float = 1e-3,
) -> tuple[list[adsk.fusion.BRepEdge], list[adsk.fusion.BRepEdge]]:
    """The edges the arm's outer face chamfer takes, after the relief cut, as (outline, ramp top).

    The outline is every edge with both end points at z = `outer_z` (mm) and at y >= `ramp_foot`, less the ramp's foot
    (both end points at y = `ramp_foot`) and the pin hole's rim (both end points within `pin_hole_r` of (0, `pin_y`)).
    It holds two lines and an arc. The ramp top is the one line with both end points at z = `top_z` and y = `top_y`.
    Any other count is an error."""
    outline: list[adsk.fusion.BRepEdge] = []
    tops: list[adsk.fusion.BRepEdge] = []
    lines = arcs = 0
    for i in range(body.edges.count):
        edge = body.edges.item(i)
        g = edge.geometry
        if g is None or edge.startVertex is None or edge.endVertex is None:
            continue
        ends = [(mm_from_cm(q.x), mm_from_cm(q.y), mm_from_cm(q.z)) for q in
                (edge.startVertex.geometry, edge.endVertex.geometry)]
        is_line = g.curveType == adsk.core.Curve3DTypes.Line3DCurveType
        if all(abs(z - outer_z) <= tol for _, _, z in ends):
            if any(y < ramp_foot - tol for _, y, _ in ends) or all(abs(y - ramp_foot) <= tol for _, y, _ in ends):
                continue
            if all(math.hypot(x, y - pin_y) <= pin_hole_r + tol for x, y, _ in ends):
                continue
            if is_line:
                lines += 1
            elif g.curveType == adsk.core.Curve3DTypes.Arc3DCurveType:
                arcs += 1
            else:
                raise BuildError(f"{what}: unexpected outline edge type {g.curveType}")
            outline.append(edge)
        elif all(abs(z - top_z) <= tol and abs(y - top_y) <= tol for _, y, z in ends):
            if not is_line:
                raise BuildError(f"{what}: the ramp's top edge is not a line")
            tops.append(edge)
    if lines != 2 or arcs != 1 or len(tops) != 1:
        raise BuildError(
            f"{what}: found {lines} side lines, {arcs} arcs and {len(tops)} ramp top lines, expected 2, 1 and 1"
        )
    return outline, tops


def body_report(body: adsk.fusion.BRepBody) -> tuple[bool, float, tuple[float, ...]]:
    """isSolid, volume in mm^3, bounding box (min xyz, max xyz) in mm."""
    box = body.preciseBoundingBox
    lo, hi = box.minPoint, box.maxPoint
    bbox = tuple(mm_from_cm(v) for v in (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z))
    return body.isSolid, body.volume * 1000.0, bbox
