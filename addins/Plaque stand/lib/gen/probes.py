"""Point probes: points that must lie inside or outside a body, in the local frame (millimeters).

Fusion's point containment is exact, so a probe sits at least 0.3 mm from every surface (the grid skips points closer
than that to an outline). They stand in for the gallery's section checks of the profile, the channel, the pockets and
the plaque's pose, which have no Fusion counterpart. A bracket is probed on a grid across its profile, 5 mm in from
its side face, with the expectation read from the same pure outline the builder draws, so a misdrawn curve shows. The
rail, the nut pockets and the bolt holes have a few hand-placed probes.
"""

from __future__ import annotations

import dataclasses
import math

from . import bodies, expected, sections
from .constants import BASE_THICKNESS, BRACKET_WIDTH, JOINT_FIT, RAIL_HEIGHT, RAIL_WIDTH
from .curves import Loop, Point, loop_polygon
from .fasteners import HEAD_POCKET_RADIUS, HOLE_RADIUS
from .params import Dimensions, Params

INSIDE = "inside"
OUTSIDE = "outside"

_MARGIN = 0.3  # mm: least distance from a probe to any surface
_PROBE_LIMIT = 70  # probes per grid-probed body, thinned evenly
_GRID_STEP = 3.0


@dataclasses.dataclass(frozen=True)
class Probe:
    label: str
    point: tuple[float, float, float]
    expect: str  # INSIDE (in the material) or OUTSIDE (in a cavity or beyond the body)


def _polygon(loop: Loop) -> list[Point]:
    """The loop as a polygon with 2 degree chords: at most 0.004 mm inside an arc of 25 mm, under the 0.3 mm margin."""
    return loop_polygon(loop, math.radians(2.0))


def _inside(pt: Point, poly: list[Point]) -> bool:
    x, y = pt
    hit = False
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def _edge_distance(pt: Point, poly: list[Point]) -> float:
    best = math.inf
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((pt[0] - x0) * dx + (pt[1] - y0) * dy) / length2))
        best = min(best, math.hypot(pt[0] - (x0 + t * dx), pt[1] - (y0 + t * dy)))
    return best


def grid_probes(label: str, outer: Loop, holes: list[list[Point]], z: float, step: float) -> list[Probe]:
    """Probes on a grid at height z: INSIDE where the point is in `outer` and in none of `holes`, else OUTSIDE.

    A grid point closer than _MARGIN to any outline is skipped. The grid reaches 1 mm past the outline. At most
    _PROBE_LIMIT probes are kept, evenly spread."""
    poly = _polygon(outer)
    rings = [poly] + holes
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    found: list[Probe] = []
    nx = int((max(xs) - min(xs) + 2.0) / step) + 1
    ny = int((max(ys) - min(ys) + 2.0) / step) + 1
    for i in range(nx):
        for j in range(ny):
            pt = (min(xs) - 1.0 + i * step, min(ys) - 1.0 + j * step)
            if any(_edge_distance(pt, r) < _MARGIN for r in rings):
                continue
            solid = _inside(pt, poly) and not any(_inside(pt, h) for h in holes)
            found.append(Probe(f"{label} ({pt[0]:.1f}, {pt[1]:.1f})", (pt[0], pt[1], z), INSIDE if solid else OUTSIDE))
    if len(found) > _PROBE_LIMIT:
        keep = [found[int(k * len(found) / _PROBE_LIMIT)] for k in range(_PROBE_LIMIT)]
        found = keep
    return found


def _bracket(name: str, dm: Dimensions) -> list[Probe]:
    x0 = 0.0 if name == bodies.BRACKET_1 else dm.span - BRACKET_WIDTH
    mid = x0 + BRACKET_WIDTH / 2
    y, tb = dm.rail_center, BASE_THICKNESS
    # The grid is the profile at 5 mm from the side face, clear of the bolt's hole and pocket (the pocket's corners
    # reach 2.51 from the mid-plane) and of the side chamfer.
    out = [Probe(q.label, (x0 + 5.0, q.point[0], q.point[1]), q.expect)
           for q in grid_probes(name.lower(), sections.outline_loop(dm), [], 0.0, _GRID_STEP)]
    hole_z = (tb - dm.channel_height + 2.0) / 2  # between the pocket's far face (z 2) and the channel floor (z 4)
    out += [
        Probe("nut pocket", (mid, y, 1.0), OUTSIDE),
        Probe("nut pocket wall", (mid, y + 2.6, 1.0), INSIDE),
        Probe("bolt hole", (mid, y, hole_z), OUTSIDE),
        Probe("bolt hole wall", (mid + 1.9, y, hole_z), INSIDE),
        Probe("under the nut pocket", (mid, y, -0.01), OUTSIDE),
        Probe("channel", (mid, y, tb - 1.0), OUTSIDE),
        Probe("beside the channel", (mid, dm.channel_back + 1.5, tb - 1.0), INSIDE),
    ]
    return out


def _rail(dm: Dimensions) -> list[Probe]:
    y = dm.rail_center
    z0 = BASE_THICKNESS - RAIL_HEIGHT + JOINT_FIT  # the rail's bottom, 4.4
    top = z0 + RAIL_HEIGHT
    xs = [s.head[0] for s in dm.sites]
    out = [
        Probe("rail body", (dm.span / 2, y, z0 + RAIL_HEIGHT / 2), INSIDE),
        Probe("below the rail", (dm.span / 2, y, z0 - 0.4), OUTSIDE),
        Probe("above the rail", (dm.span / 2, y, top + 0.4), OUTSIDE),
        Probe("beside the rail", (dm.span / 2, y + RAIL_WIDTH / 2 + 0.4, z0 + RAIL_HEIGHT / 2), OUTSIDE),
    ]
    for k, x in enumerate(xs, start=1):
        out += [
            Probe(f"head pocket {k}", (x, y, top - 1.0), OUTSIDE),
            Probe(f"head pocket {k} wall", (x + HEAD_POCKET_RADIUS + 0.6, y, top - 1.0), INSIDE),
            Probe(f"bolt hole {k}", (x, y, z0 + 1.0), OUTSIDE),
            Probe(f"bolt hole {k} wall", (x + HOLE_RADIUS + 0.6, y, z0 + 1.0), INSIDE),
        ]
    return out


def _plaque(p: Params, dm: Dimensions) -> list[Probe]:
    o, x, y, z = expected.plaque_axes(p, dm)

    def at(a: float, b: float, c: float) -> tuple[float, float, float]:
        return (o[0] + a * x[0] + b * y[0] + c * z[0], o[1] + a * x[1] + b * y[1] + c * z[1],
                o[2] + a * x[2] + b * y[2] + c * z[2])

    w, t, h = p.plaque_width, p.plaque_thickness, p.plaque_height
    return [
        Probe("plaque centre", at(w / 2, t / 2, h / 2), INSIDE),
        Probe("plaque near the bottom edge", at(w / 2, t / 2, 1.0), INSIDE),
        Probe("in front of the plaque", at(w / 2, -0.5, h / 2), OUTSIDE),
        Probe("behind the plaque", at(w / 2, t + 0.5, h / 2), OUTSIDE),
        Probe("beyond its top", at(w / 2, t / 2, h + 0.5), OUTSIDE),
        Probe("beside the plaque", at(-0.5, t / 2, h / 2), OUTSIDE),
    ]


def part_probes(p: Params, dm: Dimensions) -> dict[str, list[Probe]]:
    """Probes per body name (the printed bodies and the plaque)."""
    out = {name: _bracket(name, dm) for name in bodies.BRACKETS}
    out[bodies.RAIL] = _rail(dm)
    out[bodies.PLAQUE] = _plaque(p, dm)
    return out
