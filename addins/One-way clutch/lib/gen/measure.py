"""Areas, lengths and volumes of the pure sections, used for the expected volumes and bounds (millimeters).

Numeric where a closed form is awkward: the volume of a revolved tool clipped to a body is a scan over z.
"""

from __future__ import annotations

import math

from .curves import Line, Loop, Point, loop_polygon, polygon_area

_SLICES = 4000


def loop_area(loop: Loop) -> float:
    """Unsigned area inside a closed loop."""
    return abs(polygon_area(loop_polygon(loop)))


def loop_length(loop: Loop) -> float:
    total = 0.0
    for c in loop:
        if isinstance(c, Line):
            total += math.dist(c.start, c.end)
        else:
            r = math.dist(c.center, c.start)
            a0 = math.atan2(c.start[1] - c.center[1], c.start[0] - c.center[0])
            a1 = math.atan2(c.end[1] - c.center[1], c.end[0] - c.center[0])
            total += r * ((a1 - a0) % (2 * math.pi))
    return total


def loop_bounds(loop: Loop) -> tuple[float, float, float, float]:
    """(min x, min y, max x, max y) of a loop, from its polygon at a 0.1 degree step."""
    pts = loop_polygon(loop, math.radians(0.1))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def circle_area(r: float) -> float:
    return math.pi * r * r


def hexagon_area(radius: float) -> float:
    """Area of the regular hexagon whose corners lie on the circle of `radius`."""
    return 3 * math.sqrt(3) / 2 * radius * radius


def chamfer_volume(length: float, size: float, turning: float) -> float:
    """Volume a chamfer of `size` takes along a convex-turning edge of `length` whose tangent turns by `turning` radians
    in all (2 pi round a closed outline). The cut's triangle has its centroid size / 3 inside the face (Pappus)."""
    return size * size / 2 * (length - size / 3 * turning)


def _intervals(poly: tuple[Point, ...], z: float) -> list[tuple[float, float]]:
    """The radius intervals the polygon of (r, z) vertices covers at height z."""
    hits: list[float] = []
    n = len(poly)
    for i in range(n):
        (r0, z0), (r1, z1) = poly[i], poly[(i + 1) % n]
        if z0 == z1:
            continue
        if min(z0, z1) <= z < max(z0, z1):
            hits.append(r0 + (r1 - r0) * (z - z0) / (z1 - z0))
    hits.sort()
    return [(hits[k], hits[k + 1]) for k in range(0, len(hits) - 1, 2)]


def revolved_volume(poly: tuple[Point, ...], z_lo: float, z_hi: float, r_max: float = math.inf) -> float:
    """Volume of the polygon of (radius, z) vertices turned about the Z axis, kept between z_lo and z_hi and inside the
    radius r_max."""
    total = 0.0
    dz = (z_hi - z_lo) / _SLICES
    for i in range(_SLICES):
        z = z_lo + (i + 0.5) * dz
        for a, b in _intervals(poly, z):
            b = min(b, r_max)
            if b > a:
                total += math.pi * (b * b - a * a) * dz
    return total


def revolved_profile_area_at(poly: tuple[Point, ...], z: float) -> float:
    """Annulus area the polygon covers at height z (the polygon turned about the Z axis)."""
    return sum(math.pi * (b * b - a * a) for a, b in _intervals(poly, z))


def outer_radius_at(poly: tuple[Point, ...], z: float) -> float:
    iv = _intervals(poly, z)
    return iv[-1][1] if iv else 0.0
