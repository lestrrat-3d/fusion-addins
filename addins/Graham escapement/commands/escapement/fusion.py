"""Thin wrappers over Fusion features, unit conversion, edge finders and matrices.

Pure code works in millimeters; Fusion works in centimeters. `cm` is the only place that converts.
"""

from __future__ import annotations

import contextlib
import typing

import adsk.core
import adsk.fusion

from ...lib.gen.containers import Found
from ...lib.gen.curves import Arc, Line, Loop, Point, Spline
from ...lib.gen.params import Frame, frame_axes
from ...lib.gen.pose import Pose

if typing.TYPE_CHECKING:
    from .build import BuildContext


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
    """Read back the sub-components of comp, depth first in occurrence order.

    Returns (bodies directly in comp, one Found per descendant component with its path below comp)."""
    with _step("container check"):
        found: list[Found] = []

        def walk(parent: adsk.fusion.Component, prefix: tuple[str, ...]) -> None:
            for i in range(parent.occurrences.count):
                sub = parent.occurrences.item(i).component
                path = prefix + (sub.name,)
                bodies = sub.bRepBodies
                names = tuple(bodies.item(j).name for j in range(bodies.count))
                kids = tuple(sub.occurrences.item(j).component.name for j in range(sub.occurrences.count))
                found.append(Found(path, names, kids))
                walk(sub, path)

        walk(comp, ())
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
            elif isinstance(c, Spline):
                # Deviation: Fusion interpolates the fit points with its own spline (docs/escapement/deviations.md).
                fit = [sp(c.points[0])] + [to_sketch(q) for q in c.points[1:-1]] + [sp(c.points[-1])]
                curves.sketchFittedSplines.add(_collection(fit))


def draw_loop(sk: adsk.fusion.Sketch, loop: Loop) -> None:
    """Draw a closed loop on the XY sketch plane; (0, 0) reuses the sketch origin.

    """
    # Deviation: no dimensions or geometric constraints; curves sit at computed coordinates
    # (docs/escapement/deviations.md).
    _draw_loop(sk, loop, lambda q: point(q[0], q[1]), sk.originPoint)


def draw_loop_xz(sk: adsk.fusion.Sketch, loop: Loop) -> None:
    """Draw a closed loop of lines whose (u, v) are model (x, z) on an XZ sketch."""
    if any(not isinstance(c, Line) for c in loop):
        raise BuildError(f"sketch {sk.name}: draw_loop_xz takes lines only")
    # The XZ sketch's own axes differ from model X/Z; modelToSketchSpace converts.
    _draw_loop(sk, loop, lambda q: sk.modelToSketchSpace(point(q[0], 0.0, q[1])), None)


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


def cut(
    ctx: BuildContext, target: adsk.fusion.BRepBody, tools: list[adsk.fusion.BRepBody], what: str
) -> adsk.fusion.BRepBody:
    return _combine(ctx, adsk.fusion.FeatureOperations.CutFeatureOperation, target, tools, what)


def pattern(ctx: BuildContext, body: adsk.fusion.BRepBody, count: int, what: str) -> list[adsk.fusion.BRepBody]:
    """Circular pattern of body about the component Z axis; returns all `count` bodies, input first."""
    with _step(what):
        inp = ctx.comp.features.circularPatternFeatures.createInput(_collection([body]), ctx.comp.zConstructionAxis)
        inp.quantity = adsk.core.ValueInput.createByReal(count)
        inp.totalAngle = adsk.core.ValueInput.createByString("360 deg")
        inp.isSymmetric = False
        feat = ctx.comp.features.circularPatternFeatures.add(inp)
        result = _collection([body])
        bodies = [body]
        for i in range(feat.bodies.count):
            b = feat.bodies.item(i)
            if not result.contains(b):
                result.add(b)
                bodies.append(b)
        if len(bodies) != count:
            raise BuildError(f"{what}: pattern produced {len(bodies)} bodies, expected {count}")
        return bodies


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


def copy_body(ctx: BuildContext, body: adsk.fusion.BRepBody, what: str) -> adsk.fusion.BRepBody:
    with _step(what):
        feat = ctx.comp.features.copyPasteBodies.add(body)
        if feat is None or feat.bodies.count < 1:
            raise BuildError(f"{what}: copy produced no body")
        return feat.bodies.item(0)


def pose_matrix(pose: Pose) -> adsk.core.Matrix3D:
    origin, x, y, z = pose.axes()
    return _matrix(origin, x, y, z)


def frame_matrix(frame: Frame | None) -> adsk.core.Matrix3D:
    origin, x, y, z = frame_axes(frame or Frame())
    return _matrix(origin, x, y, z)


def _matrix(
    origin: tuple[float, float, float],
    x: tuple[float, float, float],
    y: tuple[float, float, float],
    z: tuple[float, float, float],
) -> adsk.core.Matrix3D:
    m = adsk.core.Matrix3D.create()
    m.setWithCoordinateSystem(
        point(origin[0], origin[1], origin[2]),
        adsk.core.Vector3D.create(*x),
        adsk.core.Vector3D.create(*y),
        adsk.core.Vector3D.create(*z),
    )
    return m


def move(ctx: BuildContext, body: adsk.fusion.BRepBody, pose: Pose, what: str) -> None:
    """Free move of body by pose; skipped for the identity pose."""
    if pose.is_identity():
        return
    with _step(what):
        inp = ctx.comp.features.moveFeatures.createInput2(_collection([body]))
        if not inp.defineAsFreeMove(pose_matrix(pose)):
            raise BuildError(f"{what}: Fusion rejected the move transform")
        ctx.comp.features.moveFeatures.add(inp)


def _xy_close(a: adsk.core.Point3D, b: tuple[float, float], tol: float) -> bool:
    return abs(mm_from_cm(a.x) - b[0]) <= tol and abs(mm_from_cm(a.y) - b[1]) <= tol


def _is_axial_line(edge: adsk.fusion.BRepEdge, tol: float) -> bool:
    # A degenerate edge (for example the seam point of a revolved body) has no curve geometry.
    if edge.geometry is None or edge.geometry.curveType != adsk.core.Curve3DTypes.Line3DCurveType:
        return False
    g = adsk.core.Line3D.cast(edge.geometry)
    return abs(g.startPoint.x - g.endPoint.x) <= cm(tol) and abs(g.startPoint.y - g.endPoint.y) <= cm(tol)


def axial_edges_at(
    body: adsk.fusion.BRepBody, points: list[Point], tol: float = 1e-3
) -> list[adsk.fusion.BRepEdge]:
    """Straight edges parallel to Z whose xy lies within tol (mm) of one of points."""
    found: list[adsk.fusion.BRepEdge] = []
    for i in range(body.edges.count):
        edge = body.edges.item(i)
        if not _is_axial_line(edge, tol):
            continue
        start = adsk.core.Line3D.cast(edge.geometry).startPoint
        if any(_xy_close(start, pt, tol) for pt in points):
            found.append(edge)
    return found


def concave_axial_edges(body: adsk.fusion.BRepBody, tol: float = 1e-3) -> list[adsk.fusion.BRepEdge]:
    edges = body.concaveEdges
    return [edges.item(i) for i in range(edges.count) if _is_axial_line(edges.item(i), tol)]


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
            _xy_close(c, (0.0, 0.0), tol)
            and abs(mm_from_cm(c.z) - z) <= tol
            and abs(mm_from_cm(g.radius) - radius) <= tol
        ):
            found.append(edge)
    return found


FaceLoop = tuple[bool, list[adsk.fusion.BRepEdge], tuple[float, float, float] | None, Point | None, float]


def flat_face_loops(
    body: adsk.fusion.BRepBody, z: float, min_area: float, what: str, tol: float = 1e-3
) -> list[FaceLoop]:
    """Loops of the planar faces of body that face along Z at height z (mm) with at least min_area (mm^2).

    Each loop is (is_outer, edges, circle, start, length). `length` is the loop length in mm, the sum of
    `BRepEdge.length` (cm) over the loop's edges, 0.0 with no edge. `circle` is (cx, cy, r) in mm when the loop has
    one edge whose geometry is a Circle3D or an Arc3D, else None. `start` is the (x, y) in mm of the first edge's
    start vertex, None when the loop has no edge or no start vertex [edgefinish.go finishFaceEdges]. An edge without
    curve geometry (a degenerate edge) is skipped (knowledge/revolve-and-edges.md)."""
    out: list[FaceLoop] = []
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
            # 1e-3 mm, not the gallery's 1e-6: Fusion stores cm; the nearest other flat face is 0.5 mm away.
            if abs(mm_from_cm(plane.origin.z) - z) > tol:
                continue
            if face.area * 100.0 < min_area:  # cm^2 -> mm^2
                continue
            for j in range(face.loops.count):
                loop = face.loops.item(j)
                edges = [loop.edges.item(k) for k in range(loop.edges.count)]
                edges = [e for e in edges if e.geometry is not None]
                circle = None
                if len(edges) == 1 and edges[0].geometry.curveType in (
                    adsk.core.Curve3DTypes.Circle3DCurveType,
                    adsk.core.Curve3DTypes.Arc3DCurveType,
                ):
                    cg = adsk.core.Circle3D.cast(edges[0].geometry) or adsk.core.Arc3D.cast(edges[0].geometry)
                    circle = (mm_from_cm(cg.center.x), mm_from_cm(cg.center.y), mm_from_cm(cg.radius))
                start = None
                if edges and edges[0].startVertex is not None:
                    q = edges[0].startVertex.geometry
                    start = (mm_from_cm(q.x), mm_from_cm(q.y))
                length = sum((mm_from_cm(e.length) for e in edges), 0.0)
                out.append((loop.isOuter, edges, circle, start, length))
    return out


def body_report(body: adsk.fusion.BRepBody) -> tuple[bool, float, tuple[float, ...]]:
    """isSolid, volume in mm^3, bounding box (min xyz, max xyz) in mm."""
    box = body.preciseBoundingBox
    lo, hi = box.minPoint, box.maxPoint
    bbox = tuple(mm_from_cm(v) for v in (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z))
    return body.isSolid, body.volume * 1000.0, bbox
