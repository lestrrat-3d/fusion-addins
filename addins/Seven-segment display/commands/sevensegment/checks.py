"""Build checks: compare each built body with the pure expectations and log a few lines to Text Commands.

# Deviation: the gallery's geometry tests (section clearances, fits, corner and split checks, sketch constraints) have
no Fusion counterpart. These checks use the solid flag, the bounding box and the component tree
(docs/sevensegment/deviations.md).
"""

from __future__ import annotations

import typing

import adsk.fusion

from ...lib.gen import bodies, expected
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

_BOUNDS_TOL = 0.01  # mm


def run_all(ctx: BuildContext, built: list[tuple[str, adsk.fusion.BRepBody]], seconds: float) -> None:
    """Check each body (built = (name, body)) and log one summary line plus one line per failed check."""
    if not ctx.log.enabled:
        return
    log, dm = ctx.log, ctx.dm
    passed = failed = 0
    for name, body in built:
        solid, _, bbox = fusion.body_report(body)
        if not solid:
            log.write("body", [("name", name), ("solid", solid), ("result", "FAIL")])
        results = [solid]
        want = expected.body_bounds(name, dm)
        if want is not None:
            ok = all(abs(a - b) <= _BOUNDS_TOL for a, b in zip(bbox, want))
            if not ok:
                log.write("bounds", [("name", name), ("bounds", bbox), ("expected", want), ("result", "FAIL")])
            results.append(ok)
        passed += results.count(True)
        failed += results.count(False)

    ok, bad = _container_checks(ctx)
    passed += ok
    failed += bad
    log.write("summary", [("bodies", len(built)), ("expected", bodies.EXPECTED_BODY_COUNT), ("pass", passed),
                          ("fail", failed), ("seconds", seconds)])


def _container_checks(ctx: BuildContext) -> tuple[int, int]:
    """Read the component tree back from Fusion; one `containers` line for the top and one `container` line per
    container, only on failure. Returns (passed, failed) over the results.

    # Deviation: stands in for the gallery's VerifyContainers (docs/sevensegment/deviations.md)."""
    top_bodies, found = fusion.component_tree(ctx.top)
    top, results = bodies.check_tree(found, top_bodies)
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
