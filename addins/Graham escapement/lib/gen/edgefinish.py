"""Surface edge finishing of the plates, escape wheel, anchor, pendulum and mainspring.

Own copy of decad-gallery internal/edgefinish (MinChamfer, LargeFaceArea, LongEdgeRun, the Outer and Inner filters),
models/escapement plates.go plateKeep, pendulum.go rimKeep, the escapewheel.go finish filter, the drive.go
buildGreatWheel filter, internal/edgefinish Long, models/spiralspring spiralspring.go `Outer || Long(Inner)` and the
finish calls of the part builders at 3a4f9d8. The
gallery chamfers both planes of a part in one call because decad cannot chamfer a body twice; Fusion chamfers each
plane in its own feature (docs/escapement/deviations.md). The removed volumes are the add-in's own; the gallery tests
none.
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    ANCHOR_COUNTER_RADIUS, GREAT_COUNTER_RADIUS, LIP_RADIUS, PENDULUM_HIGH, SEAT_RADIUS, WHEEL_COUNTER_RADIUS,
)
from .curves import Circle, Loop
from .layout import Geometry
from .sections import anchor_outline, escape_windows, lip_centres, pendulum_outline, plate_outline, window_loop
from .spring import loop_length, profile, spring_params

Pt = tuple[float, float]

CHAMFER = 0.5  # mm [edgefinish.go MinChamfer]
LARGE_FACE_AREA = 400.0  # mm^2 [edgefinish.go LargeFaceArea]
LONG_EDGE_RUN = 20.0  # mm [edgefinish.go LongEdgeRun]
CIRCLE_TOL = 0.01  # mm [plateKeep, rimKeep]

OUTER = "outer"  # [edgefinish.Outer]
PLATE = "plate"  # [plateKeep]
RIM = "rim"  # [rimKeep]
INNER_MULTI_OR_RIM = "inner_multi_or_rim"  # [escapewheel.go finish filter: inner with several edges, or a rim]
INNER_RIM = "inner_rim"  # [drive.go buildGreatWheel filter: inner rim only]
OUTER_OR_LONG_INNER = "outer_or_long_inner"  # [spiralspring.go: Outer || Long(Inner)]

_PLATE_RADII = (SEAT_RADIUS, LIP_RADIUS)


@dataclasses.dataclass(frozen=True)
class FinishPlane:
    z: float  # part-local height of the large flat face (mm)
    rule: str  # one of the rule names above
    loops: int  # loops the rule keeps at the gallery's topology
    radii: tuple[float, ...] = ()  # rim radii a one-edge circular loop is matched against


_PLANES: dict[str, tuple[FinishPlane, ...]] = {
    "back_plate": (FinishPlane(-6.0, PLATE, 6, _PLATE_RADII), FinishPlane(0.0, PLATE, 6, _PLATE_RADII)),
    "front_plate": (FinishPlane(28.0, PLATE, 6, _PLATE_RADII), FinishPlane(34.0, PLATE, 6, _PLATE_RADII)),
    "escape_wheel": (
        FinishPlane(22.0, INNER_MULTI_OR_RIM, 6, (WHEEL_COUNTER_RADIUS,)),
        FinishPlane(25.0, INNER_MULTI_OR_RIM, 7, (WHEEL_COUNTER_RADIUS,)),
    ),
    "anchor": (
        FinishPlane(21.0, RIM, 1, (ANCHOR_COUNTER_RADIUS,)),
        FinishPlane(26.0, RIM, 2, (ANCHOR_COUNTER_RADIUS,)),
    ),
    "pendulum": (
        FinishPlane(38.80, RIM, 2, _PLATE_RADII),
        FinishPlane(PENDULUM_HIGH, RIM, 2, _PLATE_RADII),
    ),
    "great_wheel": (FinishPlane(1.5, INNER_RIM, 1, (GREAT_COUNTER_RADIUS,)),),
    "mainspring": (FinishPlane(0.0, OUTER_OR_LONG_INNER, 2), FinishPlane(6.0, OUTER_OR_LONG_INNER, 2)),
}


def finish_planes(part: str) -> list[FinishPlane]:
    """Planes to chamfer on a part, in the gallery's order. Part-local z; empty for a part that is not finished."""
    return list(_PLANES.get(part, ()))


def keep_loop(
    rule: str,
    is_outer: bool,
    edge_count: int,
    circle: tuple[float, float, float] | None,
    start: Pt | None,
    centres: list[Pt],
    radii: tuple[float, ...] = (),
    length: float = 0.0,
) -> bool:
    """True when the rule keeps a loop.

    `circle` is (cx, cy, r) for a one-edge circular loop, else None. `start` is the first edge's start point.
    `centres` are the axes a circular loop must sit on (PLATE) or be measured about (rim rules). `radii` are the
    rim radii. `length` is the loop length in mm (OUTER_OR_LONG_INNER)."""
    on_rim = (
        edge_count == 1
        and start is not None
        and any(abs(math.hypot(start[0] - c[0], start[1] - c[1]) - r) < CIRCLE_TOL for c in centres for r in radii)
    )
    if rule == OUTER:
        return is_outer
    if rule == PLATE:
        if is_outer or edge_count > 4:
            return True
        if edge_count != 1 or circle is None:
            return False
        cx, cy, r = circle
        if not any(abs(r - want) <= CIRCLE_TOL for want in radii):
            return False
        return any(math.hypot(cx - c[0], cy - c[1]) < CIRCLE_TOL for c in centres)
    if rule == RIM:
        return is_outer or on_rim
    if rule == INNER_MULTI_OR_RIM:
        return not is_outer and (edge_count > 1 or on_rim)
    if rule == INNER_RIM:
        return not is_outer and on_rim
    if rule == OUTER_OR_LONG_INNER:
        return is_outer or length >= LONG_EDGE_RUN
    raise ValueError(f"unknown edge finishing rule {rule}")


def _rim(r: float, c: float, inside: bool) -> float:
    """Volume removed by a chamfer of setback c round a circle of radius r (Pappus).

    inside: the material is inside the circle (outer rim); otherwise it is outside (a hole)."""
    return c * c / 2 * 2 * math.pi * (r - c / 3 if inside else r + c / 3)


def _kept(g: Geometry, part: str, z: float) -> list[tuple[Loop | Circle, bool]]:
    """The loops of the plane at z that the rule keeps, each with True when its material is inside the loop."""
    if part in ("back_plate", "front_plate"):
        back = part == "back_plate"
        outline = plate_outline(98.0 if back else 82.0)
        out: list[tuple[Loop | Circle, bool]] = [(outline, True)]
        out += [(window_loop(g, sx), False) for sx in (-1.0, 1.0)]
        # The seat (r 7.05) opens on the inner face of both plates, the lip bore (r 5) on the outer face.
        inner_face = z == (0.0 if back else 28.0)
        r = SEAT_RADIUS if inner_face else LIP_RADIUS
        out += [(Circle(c, r), False) for c in lip_centres(g)]
        return out
    if part == "escape_wheel":
        out = [(w, False) for w in escape_windows()]
        if z == 25.0:
            out.append((Circle((0.0, 0.0), WHEEL_COUNTER_RADIUS), False))
        return out
    if part == "anchor":
        out = [(anchor_outline(g), True)]
        if z == 26.0:
            out.append((Circle((0.0, 0.0), ANCHOR_COUNTER_RADIUS), False))
        return out
    if part == "great_wheel":
        return [(Circle((0.0, 0.0), GREAT_COUNTER_RADIUS), False)]
    if part == "pendulum":
        r = SEAT_RADIUS if z == PENDULUM_HIGH else LIP_RADIUS
        return [(pendulum_outline(g), True), (Circle((0.0, 0.0), r), False)]
    if part == "mainspring":
        sp = spring_params()
        outer, bore, _ = profile(sp, g.spring)
        return [(outer, True), (bore, False)]
    return []


def chamfer_volume(g: Geometry, part: str) -> float:
    """Total volume (mm^3) the edge chamfers remove from a part.

    c^2/2 times the exact perimeter of every kept loop, summed over the planes, with Pappus for a full circle: inside
    the circle for an outer rim, outside it for a hole. The corners where a smooth outline turns add far less than
    the volume check's tolerance."""
    c = CHAMFER
    total = 0.0
    for plane in finish_planes(part):
        for loop, inside in _kept(g, part, plane.z):
            if isinstance(loop, Circle):
                total += _rim(loop.radius, c, inside)
            else:
                total += c * c / 2 * loop_length(loop)
    return total
