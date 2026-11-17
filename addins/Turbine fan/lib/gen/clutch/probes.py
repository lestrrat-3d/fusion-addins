"""Point probes: points that must lie inside or outside a printed body, in the local frame (millimeters).

Fusion's point containment is exact, so a probe sits at least 0.3 mm from every surface. They stand in for the
gallery's section checks, which have no Fusion counterpart. The hub and the ring are probed on a grid at the middle of
their height, with the expectation read from the same pure sections the builders draw, so a mirrored, missing or
wrongly drawn curve shows. The plates and the adapter have a few hand-placed probes.
"""

from __future__ import annotations

import dataclasses
import functools
import math

from . import bodies, sections
from .bridge import layers_for
from .constants import (
    ADAPTER_FROM,
    BOLT_ANGLES,
    COVER_FROM,
    EAR_ANGLES,
    FACE_CIRCLE,
    HUB_FROM,
    HUB_HEIGHT,
    RING_FROM,
)
from ..curves import Loop, Point, loop_polygon
from ..fasteners import HOLE_RADIUS
from .params import Dimensions, Params, polar
from .validate import derive

INSIDE = "inside"
OUTSIDE = "outside"

_MARGIN = 0.3  # mm: least distance from a probe to any surface
_PROBE_LIMIT = 70  # probes per grid-probed body, thinned evenly


@dataclasses.dataclass(frozen=True)
class Probe:
    label: str
    point: tuple[float, float, float]
    expect: str  # INSIDE (in the material) or OUTSIDE (in a cavity or beyond the body)


def _circle_polygon(center: Point, radius: float, n: int = 144) -> list[Point]:
    return [(center[0] + radius * math.cos(2 * math.pi * i / n), center[1] + radius * math.sin(2 * math.pi * i / n))
            for i in range(n)]


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


def _hub(p: Params) -> list[Probe]:
    return list(_hub_grid(p.shaft, p.freewheel, p.bore_clearance))


@functools.lru_cache(maxsize=8)
def _hub_grid(shaft: str, freewheel: str, bore_clearance: float) -> tuple[Probe, ...]:
    """The hub's grid for a shaft preset, direction and bore clearance: the hub depends on nothing else."""
    dm = derive(Params(shaft=shaft, freewheel=freewheel, bore_clearance=bore_clearance))
    outer = sections.layout(sections.hub_outline(dm), dm.sign)
    holes = [_polygon(sections.bore_loop(dm))]
    holes += [_circle_polygon(c, HOLE_RADIUS) for c in sections.bolt_hole_centers(dm.bolt_circle, BOLT_ANGLES)]
    return tuple(grid_probes("hub", outer, holes, HUB_FROM + HUB_HEIGHT / 2, 1.2))


@functools.lru_cache(maxsize=8)
def _ring_grid(shaft: str, bore_clearance: float) -> tuple[Probe, ...]:
    """The ring's grid for a shaft preset and bore clearance: the radii grow with the bore, nothing else matters."""
    dm = derive(Params(shaft=shaft, bore_clearance=bore_clearance))
    outer = sections.ring_outline(dm)
    holes = [_polygon(sections.tooth_loop(dm))]
    holes += [_circle_polygon(c, HOLE_RADIUS) for c in sections.ear_centers(dm)]
    return tuple(grid_probes("ring", outer, holes, 9.25, 1.5))


def _ring(p: Params, dm: Dimensions) -> list[Probe]:
    # The tooth loop is mirrored for a clockwise freewheel; the grid above is for the counter-clockwise layout, so
    # a clockwise ring's grid is the same points with x mirrored.
    grid = list(_ring_grid(p.shaft, p.bore_clearance))
    if dm.sign < 0:
        grid = [dataclasses.replace(g, point=(-g.point[0], g.point[1], g.point[2])) for g in grid]
    out = grid
    out += [
        Probe("ring counterbore", (0.0, -(dm.ring_counter - 0.6), 1.0), OUTSIDE),
        Probe("ring wall at the counterbore", (0.0, -(dm.ring_counter + 0.9), 1.0), INSIDE),
    ]
    for a in EAR_ANGLES:
        bx, by = polar(dm.ear_circle, a)
        px, py = polar(dm.ear_circle + 1.7, a)
        out += [
            Probe(f"ear {a:g} bore", (bx, by, 5.0), OUTSIDE),
            Probe(f"ear {a:g} nut pocket", (px, py, RING_FROM + 0.75), OUTSIDE),
            Probe(f"ear {a:g} above the nut pocket", (px, py, 2.0), INSIDE),
        ]
    return out


def _plates(dm: Dimensions) -> tuple[list[Probe], list[Probe]]:
    rb, fb = dm.bore_radius, dm.bore_flat
    annulus = (dm.boss_radius + dm.tooth_root) / 2  # between the boss and the tooth root, in the recessed annulus
    back: list[Probe] = [
        Probe("back plate bore", (0.0, 0.0, 2.0), OUTSIDE),
        Probe("back plate bore flat, shaft side", (0.0, fb - 0.4, 2.0), OUTSIDE),
        Probe("back plate bore flat, plate side", (0.0, fb + 0.4, 2.0), INSIDE),
        Probe("back plate bore wall", (0.0, -(rb + 0.5), 2.0), INSIDE),
        Probe("back plate rim", (0.0, dm.plate_radius - 0.3, 2.0), INSIDE),
        Probe("back plate beyond the rim", (0.0, dm.plate_radius + 0.3, 2.0), OUTSIDE),
        Probe("back plate boss", (0.0, 9.0, 3.9), INSIDE),
        Probe("back plate annulus below the floor", (0.0, annulus, 3.3), INSIDE),
        Probe("back plate annulus", (0.0, annulus, 3.8), OUTSIDE),
    ]
    cover: list[Probe] = [
        Probe("cover bore", (0.0, 0.0, 16.5), OUTSIDE),
        Probe("cover bore flat, shaft side", (0.0, fb - 0.4, 16.5), OUTSIDE),
        Probe("cover bore flat, plate side", (0.0, fb + 0.4, 16.5), INSIDE),
        Probe("cover bore wall", (0.0, -(rb + 0.5), 16.5), INSIDE),
        Probe("cover rim", (0.0, dm.plate_radius - 0.3, 16.5), INSIDE),
        Probe("cover beyond the rim", (0.0, dm.plate_radius + 0.3, 16.5), OUTSIDE),
        Probe("cover boss", (0.0, 9.0, COVER_FROM + 0.1), INSIDE),
        Probe("cover annulus", (0.0, annulus, COVER_FROM + 0.2), OUTSIDE),
        Probe("cover above the annulus", (0.0, annulus, COVER_FROM + 0.7), INSIDE),
    ]
    for i, a in enumerate(BOLT_ANGLES):
        bx, by = polar(dm.bolt_circle, a)
        px, py = polar(dm.bolt_circle + 1.7, a)
        qx, qy = polar(dm.bolt_circle + 2.6, a)
        ox, oy = polar(dm.bolt_circle + 1.7, a)
        back += [
            Probe(f"back plate bolt {i + 1} hole", (bx, by, 3.0), OUTSIDE),
            Probe(f"back plate bolt {i + 1} nut pocket", (px, py, 1.0), OUTSIDE),
            Probe(f"back plate bolt {i + 1} nut pocket wall", (qx, qy, 1.0), INSIDE),
            Probe(f"back plate bolt {i + 1} above the nut pocket", (ox, oy, 2.8), INSIDE),
        ]
        cover += [
            Probe(f"cover bolt {i + 1} hole", (bx, by, 15.5), OUTSIDE),
            Probe(f"cover bolt {i + 1} head pocket", (px, py, 17.5), OUTSIDE),
            Probe(f"cover bolt {i + 1} head pocket wall", (qx, qy, 17.5), INSIDE),
            Probe(f"cover bolt {i + 1} under the head pocket", (ox, oy, 15.5), INSIDE),
        ]
    return back, cover


def _adapter(dm: Dimensions) -> list[Probe]:
    out = [Probe("adapter bore", (0.0, 0.0, 23.0), OUTSIDE), Probe("adapter wall", (0.0, -12.0, 23.0), INSIDE)]
    for a in EAR_ANGLES:
        ex, ey = polar(dm.ear_circle, a)
        px, py = polar(dm.ear_circle + 1.7, a)
        wx, wy = polar(dm.ear_circle + 2.7, a)
        fx, fy = polar(FACE_CIRCLE + 1.7, a)
        gx, gy = polar(FACE_CIRCLE + 2.7, a)
        out += [
            Probe(f"adapter ear {a:g} hole", (ex, ey, 23.0), OUTSIDE),
            Probe(f"adapter ear {a:g} head pocket", (px, py, 25.0), OUTSIDE),
            Probe(f"adapter ear {a:g} head pocket wall", (wx, wy, 25.0), INSIDE),
            Probe(f"adapter face {a:g} head pocket", (fx, fy, ADAPTER_FROM + 1.0), OUTSIDE),
            Probe(f"adapter face {a:g} head pocket wall", (gx, gy, ADAPTER_FROM + 1.0), INSIDE),
            Probe(f"adapter face {a:g} above the head pocket", (fx, fy, 23.0), INSIDE),
        ]
    for a in BOLT_ANGLES:
        hx, hy = polar(dm.bolt_circle, a)
        out.append(Probe(f"adapter access hole {a:g}", (hx, hy, 23.0), OUTSIDE))
    return out


def part_probes(p: Params, dm: Dimensions) -> dict[str, list[Probe]]:
    """Probes per printed body name."""
    back, cover = _plates(dm)
    out = {bodies.HUB: _hub(p), bodies.RING: _ring(p, dm), bodies.BACK_PLATE: back, bodies.COVER: cover}
    if p.adapter:
        out[bodies.ADAPTER] = _adapter(dm)
    # Sacrificial bridge layers (not in the gallery model): the bolt hole is filled for BRIDGE_THICKNESS directly above
    # each pocket's ceiling, so a probe on the hole's axis in the middle of the layer is in the material.
    for name, plist in out.items():
        for i, layer in enumerate(layers_for(name, p, dm)):
            plist.append(Probe(f"{name.lower()} bridge layer {i + 1}", layer.center(), INSIDE))
    return out
