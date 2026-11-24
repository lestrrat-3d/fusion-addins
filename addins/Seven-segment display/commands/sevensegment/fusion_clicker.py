"""Fusion calls of the click indexer that `fusion.py` does not have: a twisted sweep, an intersect, a circular pattern of
bodies, construction planes through the axis and a loft through circles.

None of these has been run in Fusion yet (no Fusion was available when they were written); they follow the reference
only. Each one checks its result and raises `BuildError` naming the step, and the twisted sweep checks the direction of
its twist (the reference does not give the sign).
"""

from __future__ import annotations

import contextlib
import math
import typing

import adsk.core
import adsk.fusion

from . import fusion
from .fusion import BuildError, cm, mm_from_cm, point

if typing.TYPE_CHECKING:
    from .build import BuildContext


@contextlib.contextmanager
def _step(what: str):
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


def axis_path(ctx: BuildContext, length: float, what: str) -> adsk.fusion.Path:
    """A sweep path: the line on the Z axis from z = 0 to z = length (mm), drawn on an XZ sketch."""
    sk = fusion.new_sketch_xz(ctx.comp, what)
    with _step(what):
        a = sk.modelToSketchSpace(point(0.0, 0.0, 0.0))
        b = sk.modelToSketchSpace(point(0.0, 0.0, length))
        line = sk.sketchCurves.sketchLines.addByTwoPoints(a, b)
        sk.isComputeDeferred = False
        path = ctx.comp.features.createPath(line)
        if path is None:
            raise BuildError(f"{what}: Fusion created no path")
        sk.isLightBulbOn = False
        return path


def _cap_angle(body: adsk.fusion.BRepBody, z: float, tol: float = 1e-3) -> float:
    """The angle, degrees, of the centroid of the body's planar face that faces +Z at height z (mm)."""
    for i in range(body.faces.count):
        face = body.faces.item(i)
        g = face.geometry
        if g is None or g.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
            continue
        plane = adsk.core.Plane.cast(g)
        if plane.normal.z < 0.999 or abs(mm_from_cm(plane.origin.z) - z) > tol:
            continue
        c = face.centroid
        return math.degrees(math.atan2(c.y, c.x))
    raise BuildError(f"no cap at z={z:g}")


def _angle_gap(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def twisted_prism(ctx: BuildContext, profile: adsk.fusion.Profile, path: adsk.fusion.Path, length: float,
                  twist: float, cap_angle: float, what: str) -> adsk.fusion.BRepBody:
    """Sweep `profile` (on the XY plane at z = 0) along the axis path, turning it by `twist` degrees (counterclockwise
    about +Z when positive) over the length. `cap_angle` is the angle the top cap's centroid must have; if the
    feature's cap lies there only with the opposite twist, the feature is rebuilt with that sign."""
    sweeps = ctx.comp.features.sweepFeatures
    with _step(what):
        for sign in (1.0, -1.0):
            inp = sweeps.createInput(profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            inp.twistAngle = adsk.core.ValueInput.createByString(f"{sign * twist:.9f} deg")
            feat = sweeps.add(inp)
            if feat is None or feat.bodies.count != 1:
                raise BuildError(f"{what}: sweep produced {0 if feat is None else feat.bodies.count} bodies")
            body = feat.bodies.item(0)
            got = _cap_angle(body, length)
            if _angle_gap(got, cap_angle) < 0.2 or abs(twist) < 0.4:
                profile.parentSketch.isLightBulbOn = False
                return body
            if sign < 0:
                raise BuildError(f"{what}: top cap at {got:.3f} degrees, expected {cap_angle:.3f} (twist {twist})")
            feat.deleteMe()
    raise BuildError(what)


def intersect(ctx: BuildContext, target: adsk.fusion.BRepBody, tool: adsk.fusion.BRepBody,
              what: str) -> adsk.fusion.BRepBody:
    with _step(what):
        inp = ctx.comp.features.combineFeatures.createInput(target, _collection([tool]))
        inp.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
        inp.isKeepToolBodies = False
        feat = ctx.comp.features.combineFeatures.add(inp)
        if feat is None or feat.bodies.count != 1:
            raise BuildError(f"{what}: intersect produced {0 if feat is None else feat.bodies.count} bodies")
        return feat.bodies.item(0)


def pattern(ctx: BuildContext, body: adsk.fusion.BRepBody, count: int, what: str) -> list[adsk.fusion.BRepBody]:
    """Circular pattern of body about the component Z axis; returns all `count` bodies, the input first."""
    with _step(what):
        inp = ctx.comp.features.circularPatternFeatures.createInput(_collection([body]), ctx.comp.zConstructionAxis)
        inp.quantity = adsk.core.ValueInput.createByReal(count)
        inp.totalAngle = adsk.core.ValueInput.createByString("360 deg")
        inp.isSymmetric = False
        feat = ctx.comp.features.circularPatternFeatures.add(inp)
        seen = _collection([body])
        out = [body]
        for i in range(feat.bodies.count):
            b = feat.bodies.item(i)
            if not seen.contains(b):
                seen.add(b)
                out.append(b)
        if len(out) != count:
            raise BuildError(f"{what}: pattern produced {len(out)} bodies, expected {count}")
        return out


def plane_through_axis(ctx: BuildContext, angle: float, what: str) -> adsk.fusion.ConstructionPlane | adsk.core.Base:
    """A plane that holds the Z axis, turned by `angle` degrees about Z from the XZ plane (angle in [0, 180)). It is the
    XZ plane itself for 0. A turn the wrong way is detected from the plane's normal and redone with the opposite sign."""
    if angle == 0.0:
        return ctx.comp.xZConstructionPlane
    with _step(what):
        planes = ctx.comp.constructionPlanes
        want = math.radians(angle)
        for sign in (1.0, -1.0):
            inp = planes.createInput()
            if not inp.setByAngle(ctx.comp.zConstructionAxis, adsk.core.ValueInput.createByReal(sign * want),
                                  ctx.comp.xZConstructionPlane):
                raise BuildError(f"{what}: Fusion rejected the construction plane")
            plane = planes.add(inp)
            n = plane.geometry.normal
            # The plane holds the radial direction (cos, sin, 0) of its angle when the normal is perpendicular to it.
            if abs(n.x * math.cos(want) + n.y * math.sin(want)) < 1e-6:
                plane.isLightBulbOn = False
                return plane
            plane.deleteMe()
        raise BuildError(f"{what}: no construction plane through the axis at {angle:g} degrees")


def circle_profile(ctx: BuildContext, plane: adsk.core.Base, centre: tuple[float, float, float], radius: float,
                   what: str) -> adsk.fusion.Profile:
    """A circle of `radius` mm about the model point `centre` (mm) in the sketch on `plane`, and its one profile."""
    with _step(what):
        sk = ctx.comp.sketches.add(plane)
        sk.name = what
        sk.isComputeDeferred = True
        c = sk.modelToSketchSpace(point(*centre))
        sk.sketchCurves.sketchCircles.addByCenterRadius(c, cm(radius))
    return fusion.profile_with_loops(sk, 1, what, only=True)


def loft(ctx: BuildContext, profiles: list[adsk.fusion.Profile], what: str) -> adsk.fusion.BRepBody:
    """A solid loft through the profiles in order, with free end conditions."""
    with _step(what):
        inp = ctx.comp.features.loftFeatures.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        for p in profiles:
            inp.loftSections.add(p)
        inp.isSolid = True
        inp.isClosed = False
        feat = ctx.comp.features.loftFeatures.add(inp)
        if feat is None or feat.bodies.count != 1:
            raise BuildError(f"{what}: loft produced {0 if feat is None else feat.bodies.count} bodies")
        for p in profiles:
            p.parentSketch.isLightBulbOn = False
        return feat.bodies.item(0)

