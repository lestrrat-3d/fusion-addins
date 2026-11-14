"""Build checks: compare each built body with the pure expectations and log a few lines to Text Commands.

# Deviation: the gallery's geometry tests (action simulation, meshgap fits, section clearances, TestSketches,
TestExploded, TestArborCollars, TestInstallability, TestCorners, TestSpringRoot, TestPressFitWalls) have no Fusion
counterpart. These checks use volume, z range, point probes and interaction points; the `collar` and `bore` points
stand in for TestArborCollars and TestInstallability, the `body step` probes for the body-step checks of
TestArborCollars, and the `round` probes for the corner check. A unit test checks the press-fit wall arithmetic
(docs/escapement/deviations.md).
"""

from __future__ import annotations

import typing

import adsk.fusion

from ...lib.gen import bodies as body_names
from ...lib.gen import containers, expected, probes
from ...lib.gen.pose import body_poses
from ...lib.gen.report import within
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

_Z_TOL = 1e-3  # mm
_MAX_FAIL_LINES = 10
_EVENTS = ("mesh", "escapement", "coupling", "fit", "collar", "bore")

_CONTAINMENT = {
    adsk.fusion.PointContainment.PointInsidePointContainment: probes.INSIDE,
    adsk.fusion.PointContainment.PointOutsidePointContainment: probes.OUTSIDE,
    adsk.fusion.PointContainment.PointOnPointContainment: "on",
}


def run_all(ctx: BuildContext, bodies: list[tuple[str, str, adsk.fusion.BRepBody]], seconds: float) -> None:
    """Check each body (bodies = (part, name, body)) and log one summary line plus one line per failed check."""
    if not ctx.log.enabled:
        return
    log = ctx.log
    g = ctx.g
    poses = body_poses(g, ctx.s)
    z_ranges = expected.assembled_z(g)
    all_probes = probes.part_probes(g)
    passed = failed = 0
    for part, name, body in bodies:
        solid, volume, bbox = fusion.body_report(body)
        vol = expected.part_volume(g, part)
        vol_ok = solid and within(volume, vol)
        if not vol_ok:
            log.write("body", [("name", name), ("solid", solid), ("volume_mm3", volume),
                               ("expected_mm3", vol.value), ("tol_mm3", vol.tol), ("result", "FAIL")])

        zmin, zmax = z_ranges[name]
        bounds_ok = abs(bbox[2] - zmin) <= _Z_TOL and abs(bbox[5] - zmax) <= _Z_TOL
        if not bounds_ok:
            log.write("bounds", [("name", name), ("zmin", bbox[2]), ("zmax", bbox[5]), ("expected_z", (zmin, zmax)),
                                 ("result", "FAIL")])

        failures: list[str] = []
        plist = all_probes.get(part, [])
        for probe in plist:
            where = poses[name].apply(probe.point)
            got = _CONTAINMENT.get(body.pointContainment(fusion.point(*where)), "unknown")
            if got != probe.expect:
                failures.append(f"{probe.label}: got {got}, want {probe.expect}")
        if failures:
            log.write("probes", [("name", name), ("total", len(plist)), ("fail", len(failures)),
                                 ("result", "FAIL")])
        for line in failures[:_MAX_FAIL_LINES]:
            log.write("probe", [("name", name), ("detail", line), ("result", "FAIL")])

        results = [vol_ok, bounds_ok, not failures]
        passed += results.count(True)
        failed += results.count(False)

    by_name = {name: body for _, name, body in bodies}
    points = (
        probes.interaction_points(g, ctx.s) + probes.fastener_points(g) + probes.collar_points(g, ctx.s)
        + probes.bore_points(g, ctx.s)
    )
    for event in _EVENTS:
        ok, bad = _point_checks(ctx, by_name, [mp for mp in points if mp.label.split()[0] == event], event)
        passed += ok
        failed += bad
    ok, bad = _container_checks(ctx)
    passed += ok
    failed += bad
    log.write("summary", [("bodies", len(bodies)), ("expected", body_names.EXPECTED_BODY_COUNT), ("pass", passed),
                          ("fail", failed), ("seconds", seconds)])


def _path_text(path: tuple[str, ...]) -> str:
    return "/".join(path)


def _container_checks(ctx: BuildContext) -> tuple[int, int]:
    """Read the component tree back from Fusion; one `containers` line for the top and one `container` line per path.

    # Deviation: stands in for the gallery's VerifyContainers + requireContainers (docs/escapement/deviations.md).
    Returns (passed, failed) over the 21 results. Only failures log a line."""
    top_bodies, found = fusion.component_tree(ctx.top)
    top, results = containers.check_tree(found, top_bodies)
    fields: list[tuple[str, object]] = [("component", ctx.top.name), ("bodies", top.bodies)]
    if top.detail:
        fields.append(("detail", top.detail))
    if not top.ok:
        ctx.log.write("containers", fields + [("result", "FAIL")])
    passed = int(top.ok)
    failed = int(not top.ok)
    for r in results:
        fields = [("path", _path_text(r.path)), ("bodies", r.bodies), ("expected", r.expected)]
        if r.detail:
            fields.append(("detail", r.detail))
        if not r.ok:
            ctx.log.write("container", fields + [("result", "FAIL")])
        passed += r.ok
        failed += not r.ok
    return passed, failed


def _point_checks(
    ctx: BuildContext, by_name: dict[str, adsk.fusion.BRepBody], points: list[probes.MeshPoint], event: str
) -> tuple[int, int]:
    """Points that must lie outside their target body: one check per event, `<event> summary` line on failure.

    A point inside its target adds an `<event>` line, at most 10 per event. Returns (passed, failed)."""
    total = 0
    inside: list[str] = []
    for mp in points:
        body = by_name.get(mp.target)
        if body is None:
            raise fusion.BuildError(f"{event} check: no body named {mp.target}")
        total += 1
        got = _CONTAINMENT.get(body.pointContainment(fusion.point(*mp.point)), "unknown")
        if got == probes.INSIDE:
            inside.append(f"{mp.target}: {mp.label}")
    if not inside:
        return 1, 0
    ctx.log.write(f"{event} summary", [("points", total), ("inside", len(inside)), ("result", "FAIL")])
    for detail in inside[:_MAX_FAIL_LINES]:
        ctx.log.write(event, [("detail", detail), ("result", "FAIL")])
    return 0, 1
