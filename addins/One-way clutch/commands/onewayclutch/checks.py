"""Build checks: compare each built body with the pure expectations and log a few lines to Text Commands.

# Deviation: the gallery's geometry tests (section clearances, fits, corner and split checks, sketch constraints) have
no Fusion counterpart. These checks use volume, bounding box, point probes and the component tree
(docs/onewayclutch/deviations.md).
"""

from __future__ import annotations

import typing

import adsk.fusion

from ...lib.gen import bodies, expected, probes
from ...lib.gen.report import within
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

_BOUNDS_TOL = 0.01  # mm
_MAX_FAIL_LINES = 10

_CONTAINMENT = {
    adsk.fusion.PointContainment.PointInsidePointContainment: probes.INSIDE,
    adsk.fusion.PointContainment.PointOutsidePointContainment: probes.OUTSIDE,
    adsk.fusion.PointContainment.PointOnPointContainment: "on",
}


def run_all(ctx: BuildContext, built: list[tuple[str, adsk.fusion.BRepBody]], seconds: float) -> None:
    """Check each body (built = (name, body)) and log one summary line plus one line per failed check."""
    if not ctx.log.enabled:
        return
    log, p, dm = ctx.log, ctx.p, ctx.dm
    all_probes = probes.part_probes(p, dm)
    passed = failed = 0
    for name, body in built:
        solid, volume, bbox = fusion.body_report(body)
        vol = expected.body_volume(name, p, dm)
        vol_ok = solid and (vol is None or within(volume, vol))
        if not vol_ok:
            log.write("body", [("name", name), ("solid", solid), ("volume_mm3", volume),
                               ("expected_mm3", vol.value if vol else 0.0), ("tol_mm3", vol.tol if vol else 0.0),
                               ("result", "FAIL")])

        want = expected.body_bounds(name, p, dm)
        bounds_ok = all(abs(a - b) <= _BOUNDS_TOL for a, b in zip(bbox, want))
        if not bounds_ok:
            log.write("bounds", [("name", name), ("bounds", bbox), ("expected", want), ("result", "FAIL")])

        failures: list[str] = []
        plist = all_probes.get(name, [])
        for probe in plist:
            got = _CONTAINMENT.get(body.pointContainment(fusion.point(*probe.point)), "unknown")
            if got != probe.expect:
                failures.append(f"{probe.label}: got {got}, want {probe.expect}")
        if failures:
            log.write("probes", [("name", name), ("total", len(plist)), ("fail", len(failures)), ("result", "FAIL")])
        for line in failures[:_MAX_FAIL_LINES]:
            log.write("probe", [("name", name), ("detail", line), ("result", "FAIL")])

        results = [vol_ok, bounds_ok, not failures]
        passed += results.count(True)
        failed += results.count(False)

    ok, bad = _container_checks(ctx)
    passed += ok
    failed += bad
    log.write("summary", [("bodies", len(built)), ("expected", bodies.expected_count(p.adapter)), ("pass", passed),
                          ("fail", failed), ("seconds", seconds)])


def _container_checks(ctx: BuildContext) -> tuple[int, int]:
    """Read the component tree back from Fusion; one `containers` line for the top and one `container` line per
    container, only on failure. Returns (passed, failed) over the results.

    # Deviation: stands in for the gallery's VerifyContainers (docs/onewayclutch/deviations.md)."""
    top_bodies, found = fusion.component_tree(ctx.top)
    top, results = bodies.check_tree(found, top_bodies, ctx.p.adapter)
    passed = failed = 0
    if not top.ok:
        ctx.log.write("containers", [("component", ctx.top.name), ("bodies", top.bodies), ("detail", top.detail),
                                     ("result", "FAIL")])
    passed += top.ok
    failed += not top.ok
    for r in results:
        if not r.ok:
            ctx.log.write("container", [("name", r.name), ("bodies", r.bodies), ("expected", r.expected),
                                        ("detail", r.detail), ("result", "FAIL")])
        passed += r.ok
        failed += not r.ok
    return passed, failed
