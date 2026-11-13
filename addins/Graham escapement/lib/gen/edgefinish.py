"""Surface edge finishing of the plates, escape wheel, anchor, pendulum and mainspring.

Own copy of decad-gallery internal/edgefinish (MinChamfer, LargeFaceArea, LongEdgeRun, the Outer and Inner filters),
models/escapement plates.go plateKeep, pendulum.go rimKeep and the finish calls of the part builders at 0067d30. The
gallery chamfers both planes of a part in one call because decad cannot chamfer a body twice; Fusion chamfers each
plane in its own feature (docs/escapement/deviations.md). The removed volumes are the add-in's own; the gallery tests
none.
"""

from __future__ import annotations

import dataclasses
import math

from .constants import LIP_RADIUS, SEAT_RADIUS
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
INNER_MULTI = "inner_multi"  # [escapewheel.go: !IsOuter && len(e) > 1]
PLATE = "plate"  # [plateKeep]
RIM = "rim"  # [rimKeep]

_RIM_RADII = (SEAT_RADIUS, LIP_RADIUS)


@dataclasses.dataclass(frozen=True)
class FinishPlane:
    z: float  # part-local height of the large flat face (mm)
    rule: str  # OUTER | INNER_MULTI | PLATE | RIM
    loops: int  # loops the rule keeps at the gallery's topology


_PLANES: dict[str, tuple[FinishPlane, ...]] = {
    "back_plate": (FinishPlane(-6.0, PLATE, 6), FinishPlane(0.0, PLATE, 6)),
    "front_plate": (FinishPlane(28.0, PLATE, 6), FinishPlane(34.0, PLATE, 6)),
    "escape_wheel": (FinishPlane(22.0, INNER_MULTI, 6), FinishPlane(25.0, INNER_MULTI, 6)),
    "anchor": (FinishPlane(21.0, OUTER, 1), FinishPlane(26.0, OUTER, 1)),
    "pendulum": (FinishPlane(37.75, RIM, 2), FinishPlane(43.75, RIM, 2)),
    "mainspring": (FinishPlane(0.0, OUTER, 1), FinishPlane(6.0, OUTER, 1)),
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
) -> bool:
    """True when the rule keeps a loop.

    `circle` is (cx, cy, r) for a one-edge circular loop, else None. `start` is the first edge's start point.
    `centres` are the axes a circular loop must sit on (PLATE) or be measured about (RIM)."""
    if rule == OUTER:
        return is_outer
    if rule == INNER_MULTI:
        return not is_outer and edge_count > 1
    if rule == PLATE:
        if is_outer or edge_count > 4:
            return True
        if edge_count != 1 or circle is None:
            return False
        cx, cy, r = circle
        if not any(abs(r - want) <= CIRCLE_TOL for want in _RIM_RADII):
            return False
        return any(math.hypot(cx - c[0], cy - c[1]) < CIRCLE_TOL for c in centres)
    if rule == RIM:
        if is_outer:
            return True
        if edge_count != 1 or start is None:
            return False
        return any(
            abs(math.hypot(start[0] - c[0], start[1] - c[1]) - r) < CIRCLE_TOL for c in centres for r in _RIM_RADII
        )
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
        return [(w, False) for w in escape_windows()]
    if part == "anchor":
        return [(anchor_outline(g), True)]
    if part == "pendulum":
        r = SEAT_RADIUS if z == 43.75 else LIP_RADIUS
        return [(pendulum_outline(g), True), (Circle((0.0, 0.0), r), False)]
    if part == "mainspring":
        sp = spring_params()
        outer, _, _ = profile(sp, g.spring)
        return [(outer, True)]
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
