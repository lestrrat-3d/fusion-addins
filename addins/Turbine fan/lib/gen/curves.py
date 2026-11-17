"""2D curve types for closed section loops, and sampling of a loop into a polygon."""

from __future__ import annotations

import dataclasses
import math
import typing

Point = tuple[float, float]


@dataclasses.dataclass(frozen=True)
class Line:
    start: Point
    end: Point


@dataclasses.dataclass(frozen=True)
class Arc:
    """Counterclockwise arc from start to end about center; |start - center| == |end - center|."""

    center: Point
    start: Point
    end: Point


Curve = typing.Union[Line, Arc]
Loop = typing.Sequence[Curve]


def endpoints(c: Curve) -> tuple[Point, Point]:
    return (c.start, c.end)


def loop_is_closed(loop: Loop) -> bool:
    """True when consecutive curves (and the last with the first) share an endpoint exactly."""
    if len(loop) < 2:
        return False
    for i, c in enumerate(loop):
        nxt = loop[(i + 1) % len(loop)]
        if not set(endpoints(c)) & set(endpoints(nxt)):
            return False
    return True


def _arc_points(a: Arc, max_step: float) -> list[Point]:
    """Points of a, start to end counterclockwise; the first is a.start and the last is a.end."""
    cx, cy = a.center
    r = math.hypot(a.start[0] - cx, a.start[1] - cy)
    a0 = math.atan2(a.start[1] - cy, a.start[0] - cx)
    a1 = math.atan2(a.end[1] - cy, a.end[0] - cx)
    sweep = (a1 - a0) % (2 * math.pi)
    n = max(1, math.ceil(sweep / max_step - 1e-9))
    pts = [a.start]
    for i in range(1, n):
        t = a0 + sweep * i / n
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    pts.append(a.end)
    return pts


def loop_polygon(loop: Loop, max_step: float = math.radians(0.5)) -> list[Point]:
    """Walk the loop into a polygon without a repeated closing point."""
    s0, e0 = endpoints(loop[0])
    shared = set(endpoints(loop[1])) if len(loop) > 1 else set()
    cur = e0 if (s0 in shared and e0 not in shared) else s0
    out: list[Point] = []
    for c in loop:
        a, b = endpoints(c)
        forward = cur == a
        pts = [a, b] if isinstance(c, Line) else _arc_points(c, max_step)
        if not forward:
            pts.reverse()
        out.extend(pts[:-1])
        cur = pts[-1]
    return out


def polygon_area(pts: list[Point]) -> float:
    """Signed shoelace area; counterclockwise is positive."""
    total = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        total += x0 * y1 - x1 * y0
    return total / 2
