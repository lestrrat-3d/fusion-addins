"""Build checks: compare each built body with the pure expectations and log a few lines to Text Commands."""

from __future__ import annotations

import typing

import adsk.fusion

from ...lib.gen import containers, expected, layout, probes
from ...lib.gen.report import within
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

_Z_TOL = 1e-3  # mm
_X_TOL = 1e-2  # mm
_MAX_FAIL_LINES = 10

_CONTAINMENT = {
    adsk.fusion.PointContainment.PointInsidePointContainment: probes.INSIDE,
    adsk.fusion.PointContainment.PointOutsidePointContainment: probes.OUTSIDE,
    adsk.fusion.PointContainment.PointOnPointContainment: "on",
}


def _result(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def run_all(
    ctx: BuildContext,
    bodies: list[tuple[str, str, adsk.fusion.BRepBody]],
    placed: bool,
    seconds: float,
) -> None:
    """Check each body (bodies = (part, name, body)) and log one summary line plus one line per failed check."""
    if not ctx.log.enabled:
        return
    log = ctx.log
    p, d = ctx.p, ctx.d
    poses = {inst.name: inst.pose for inst in layout.instances(p, d)} if placed else {}
    z_ranges = expected.assembled_z(p, d) if placed else {}
    all_probes = probes.part_probes(p, d)
    passed = failed = 0
    for part, name, body in bodies:
        solid, volume, bbox = fusion.body_report(body)
        vol = expected.part_volume(p, d, part, ctx.fillet_radius.get(part))
        vol_ok = solid and within(volume, vol)
        if not vol_ok:
            log.write("body", [("name", name), ("solid", solid), ("volume_mm3", volume),
                               ("expected_mm3", vol.value), ("tol_mm3", vol.tol), ("result", "FAIL")])

        zmin, zmax, xmax = expected.part_local_bounds(p, d, part)
        if placed:
            zmin, zmax = z_ranges[name]
            xmax = None  # a turned instance has no fixed x extent
        fields: list[tuple[str, object]] = [("name", name), ("zmin", bbox[2]), ("zmax", bbox[5]),
                                            ("expected_z", (zmin, zmax))]
        bounds_ok = abs(bbox[2] - zmin) <= _Z_TOL and abs(bbox[5] - zmax) <= _Z_TOL
        if xmax is not None:
            fields += [("xmax", bbox[3]), ("expected_xmax", xmax)]
            bounds_ok = bounds_ok and abs(bbox[3] - xmax) <= _X_TOL
        if not bounds_ok:
            log.write("bounds", fields + [("result", "FAIL")])

        failures: list[str] = []
        plist = all_probes.get(part, [])
        for probe in plist:
            where = poses[name].apply(probe.point) if placed else probe.point
            got = _CONTAINMENT.get(body.pointContainment(fusion.point(*where)), "unknown")
            if got != probe.expect:
                failures.append(f"{probe.label}: got {got}, want {probe.expect}")
        if failures:
            log.write("probes", [("name", name), ("total", len(plist)), ("fail", len(failures)),
                                 ("result", "FAIL")])
        for line in failures[:_MAX_FAIL_LINES]:
            log.write("probe", [("name", name), ("detail", line), ("result", "FAIL")])

        passed += [vol_ok, bounds_ok, not failures].count(True)
        failed += [vol_ok, bounds_ok, not failures].count(False)
    if placed:
        by_name = {name: body for _, name, body in bodies}
        for event, points in (("mesh", probes.mesh_points(p, d)), ("fit", probes.fastener_points(p, d))):
            ok, bad = _point_checks(ctx, by_name, points, event)
            passed += ok
            failed += bad
        ok, bad = _container_checks(ctx)
        passed += ok
        failed += bad
    head: list[tuple[str, object]] = [("bodies", len(bodies))]
    if placed:
        head.append(("expected", layout.expected_body_count(p)))
    log.write("summary", head + [("pass", passed), ("fail", failed), ("seconds", seconds)])


def _container_checks(ctx: BuildContext) -> tuple[int, int]:
    """Read the component tree back from Fusion; one `containers` line and one `container` line per container.

    Stands in for the gallery's VerifyContainers + requireContainers. Returns (passed, failed) over the 10 results.
    """
    root_bodies, found = fusion.component_tree(ctx.box)
    root = containers.check_root(found, root_bodies)
    fields: list[tuple[str, object]] = [("component", ctx.box.name), ("bodies", root.bodies),
                                        ("containers", root.containers), ("expected", root.expected)]
    if root.detail:
        fields.append(("detail", root.detail))
    if not root.ok:
        ctx.log.write("containers", fields + [("result", "FAIL")])
    passed = int(root.ok)
    failed = int(not root.ok)
    for r in containers.check_containers(found, containers.expected_bodies(ctx.p, ctx.d)):
        fields = [("name", r.name), ("bodies", r.bodies), ("expected", r.expected)]
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
    """Points that must lie outside their target body. One `<event> summary` line per target body.

    event is `mesh` (gear outline points against the neighbouring gear) or `fit` (fastener points against the
    cover or ring they pass through).
    """
    totals: dict[str, int] = {}
    inside: dict[str, list[str]] = {}
    for mp in points:
        body = by_name.get(mp.target)
        if body is None:
            raise fusion.BuildError(f"{event} check: no body named {mp.target}")
        totals[mp.target] = totals.get(mp.target, 0) + 1
        got = _CONTAINMENT.get(body.pointContainment(fusion.point(*mp.point)), "unknown")
        if got == probes.INSIDE:
            inside.setdefault(mp.target, []).append(mp.label)
    passed = failed = 0
    shown = 0
    for target, total in totals.items():
        hits = inside.get(target, [])
        ok = not hits
        if not ok:
            ctx.log.write(f"{event} summary", [("target", target), ("points", total), ("inside", len(hits)),
                                               ("result", "FAIL")])
        for label in hits:
            if shown < _MAX_FAIL_LINES:
                ctx.log.write(event, [("target", target), ("detail", label), ("result", "FAIL")])
                shown += 1
        passed += ok
        failed += not ok
    return passed, failed
