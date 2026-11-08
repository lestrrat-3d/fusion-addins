"""2D sections of the carrier, cover and key tool as closed loops of lines and arcs.

Own copy of decad-gallery models/planetarygearbox carrier.go and cover.go section geometry
(a800069: bore key tool with FIT_CLEARANCE).
"""

from __future__ import annotations

import math

from .curves import Arc, Circle, Line, Loop, Point, rotate
from .dims import Dims
from .params import COVER_SPOKES, FIT_CLEARANCE, KEY_COUNT, Params
from .phase import planet_orbit_angle

_ORIGIN: Point = (0.0, 0.0)


def _segment_area(r: float, h: float, floor: float) -> float:
    """Part of the disc of radius r inside |y| < h with x > floor."""
    w = math.sqrt(r * r - h * h)
    return 2 * (h * w / 2 + r * r / 2 * math.asin(h / r) - floor * h)


def groove_area(p: Params, d: Dims) -> float:
    """Area of one keyway groove cut from the shaft section."""
    r = d.shaft / 2
    return _segment_area(r, p.key_width / 2, r - p.key_depth)


def _bore_radius(d: Dims) -> float:
    """Radius of the key tool's round part: the shaft plus the fit clearance [extrudeKeyTool]."""
    return d.shaft / 2 + FIT_CLEARANCE


def _bore_half_width(p: Params) -> float:
    return (p.key_width - 2 * FIT_CLEARANCE) / 2


def key_tool_area(p: Params, d: Dims) -> float:
    if p.key_depth == 0:
        return math.pi * (d.shaft_bore / 2) ** 2
    rb = _bore_radius(d)
    return math.pi * rb * rb - KEY_COUNT * _segment_area(rb, _bore_half_width(p), rb - p.key_depth)


def key_tool_section(p: Params, d: Dims) -> Loop | Circle:
    """The bore's round section less the three keyway grooves, as one loop (a circle without grooves)."""
    if p.key_depth == 0:
        return Circle(_ORIGIN, d.shaft_bore / 2)
    r = _bore_radius(d)
    h = _bore_half_width(p)
    floor = r - p.key_depth
    w = math.sqrt(r * r - h * h)
    upper: list[Point] = []
    fup: list[Point] = []
    flo: list[Point] = []
    lower: list[Point] = []
    for k in range(KEY_COUNT):
        theta = 2 * math.pi * k / KEY_COUNT
        upper.append(rotate((w, h), theta))
        fup.append(rotate((floor, h), theta))
        flo.append(rotate((floor, -h), theta))
        lower.append(rotate((w, -h), theta))
    loop: Loop = []
    for k in range(KEY_COUNT):
        loop.append(Line(lower[k], flo[k]))
        loop.append(Line(flo[k], fup[k]))
        loop.append(Line(fup[k], upper[k]))
        loop.append(Arc(_ORIGIN, upper[k], lower[(k + 1) % KEY_COUNT]))
    return loop


def key_box(p: Params, d: Dims) -> tuple[Point, Point]:
    """Corners of the keyway groove's box on the +X side of the shaft."""
    r = d.shaft / 2
    h = p.key_width / 2
    return ((r - p.key_depth, -h), (r + 1, h))


def pin_centers(p: Params, d: Dims) -> list[Point]:
    out: list[Point] = []
    for k in range(p.planet_count):
        phi = planet_orbit_angle(p, k)
        out.append((d.orbit * math.cos(phi), d.orbit * math.sin(phi)))
    return out


def carrier_plate_outline(p: Params, d: Dims) -> Loop:
    """Convex hull of the pin bosses: a line between each pair of neighbours and an arc round each boss."""
    n = p.planet_count
    rb = d.boss / 2
    centers = pin_centers(p, d)
    start: list[Point] = []
    end: list[Point] = []
    for k in range(n):
        nu = planet_orbit_angle(p, k) + math.pi / n
        dx, dy = rb * math.cos(nu), rb * math.sin(nu)
        start.append((centers[k][0] + dx, centers[k][1] + dy))
        nxt = centers[(k + 1) % n]
        end.append((nxt[0] + dx, nxt[1] + dy))
    loop: Loop = []
    for k in range(n):
        nk = (k + 1) % n
        loop.append(Line(start[k], end[k]))
        loop.append(Arc(centers[nk], end[k], start[nk]))
    return loop


def bolt_angles() -> list[float]:
    return [math.pi / 4 + i * math.pi / 2 for i in range(4)]


def fastener_sites(d: Dims) -> list[tuple[float, float, float]]:
    """(x, y, angle) of the four bolt sites on the bolt circle."""
    return [(d.bolt_circle * math.cos(a), d.bolt_circle * math.sin(a), a) for a in bolt_angles()]


def bolt_hole_centers(d: Dims) -> list[Point]:
    return [(d.bolt_circle * math.cos(a), d.bolt_circle * math.sin(a)) for a in bolt_angles()]


def spoke_angle(k: int) -> float:
    return math.pi / 6 + 2 * math.pi * k / COVER_SPOKES


def cover_window_loops(p: Params, d: Dims) -> list[Loop]:
    """The three windows between the cover's spokes, each a hub arc, a rim arc and two spoke edges."""
    h = d.arm / 2
    hub_r = d.cover_hub / 2
    rim_r = d.rim_inner
    hub_x = math.sqrt(hub_r * hub_r - h * h)
    rim_x = math.sqrt(rim_r * rim_r - h * h)

    def at(k: int, x: float, y: float) -> Point:
        return rotate((x, y), spoke_angle(k))

    loops: list[Loop] = []
    for k in range(COVER_SPOKES):
        nk = (k + 1) % COVER_SPOKES
        a = at(k, hub_x, h)
        b = at(k, rim_x, h)
        c = at(nk, rim_x, -h)
        dd = at(nk, hub_x, -h)
        loops.append([Line(a, b), Arc(_ORIGIN, b, c), Line(c, dd), Arc(_ORIGIN, a, dd)])
    return loops
