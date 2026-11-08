"""Polygon area, containment and distance helpers for tests and probes."""

from __future__ import annotations

import math
from typing import Iterable

Point = tuple[float, float]


def polygon_area(pts: list[Point]) -> float:
    """Signed shoelace area; counterclockwise is positive."""
    total = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        total += x0 * y1 - x1 * y0
    return total / 2


def point_in_polygon(pts: list[Point], pt: Point) -> bool:
    """Even-odd ray test."""
    x, y = pt
    inside = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xc:
                inside = not inside
    return inside


def distance_to_polygon(pts: list[Point], pt: Point) -> float:
    """Distance from pt to the polygon's boundary."""
    x, y = pt
    best = math.inf
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        seg = dx * dx + dy * dy
        t = 0.0 if seg == 0 else max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / seg))
        best = min(best, math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)))
    return best


def count_inside(
    points: Iterable[Point], polygon: list[Point], tol: float, material_inside: bool = True
) -> int:
    """Count points on the material side of polygon by more than tol (the side is inside when material_inside)."""
    count = 0
    for pt in points:
        if point_in_polygon(polygon, pt) == material_inside and distance_to_polygon(polygon, pt) > tol:
            count += 1
    return count
