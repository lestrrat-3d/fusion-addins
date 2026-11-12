"""2D sections of the carrier, cover and flat tool as closed loops of lines and arcs.

Own copy of decad-gallery models/planetarygearbox carrier.go and cover.go section geometry
(f22a29d: D-shaped bore tool, with PRESS_FIT_CLEARANCE since d8cf8d8).
"""

from __future__ import annotations

import math

from .curves import Arc, Circle, Line, Loop, Point, rotate
from .dims import Dims
from .params import COVER_SPOKES, PRESS_FIT_CLEARANCE, Params
from .phase import planet_orbit_angle

_ORIGIN: Point = (0.0, 0.0)


def _segment_area(r: float, floor: float) -> float:
    """Area of the part of the disc of radius r beyond the line x = floor (the circle segment of a flat)."""
    return r * r * math.acos(floor / r) - floor * math.sqrt(r * r - floor * floor)


def d_area(radius: float, depth: float) -> float:
    """Area of a disc of the given radius less the segment beyond a flat `depth` inside its +X rim."""
    if depth == 0:
        return math.pi * radius * radius
    return math.pi * radius * radius - _segment_area(radius, radius - depth)


def d_section(center_x: float, radius: float, depth: float) -> Loop | Circle:
    """A D section about (center_x, 0): a disc with a flat `depth` inside its +X rim (a circle when depth is 0).

    The loop is an arc about the center from the flat's upper end round to its lower end, and the line across the flat
    [extrudeDSection].
    """
    center: Point = (center_x, 0.0)
    if depth == 0:
        return Circle(center, radius)
    f = radius - depth
    h = math.sqrt(radius * radius - f * f)
    upper: Point = (center_x + f, h)
    lower: Point = (center_x + f, -h)
    return [Arc(center, upper, lower), Line(lower, upper)]


def flat_area(p: Params, d: Dims) -> float:
    """Area of the circle segment the flat cuts from the shaft section."""
    r = d.shaft / 2
    return _segment_area(r, r - p.flat_depth)


def _bore_radius(d: Dims) -> float:
    """Radius of the flat tool's round part: the shaft plus the fit clearance [extrudeFlatTool]."""
    return d.shaft / 2 + PRESS_FIT_CLEARANCE


def flat_tool_area(p: Params, d: Dims) -> float:
    return d_area(_bore_radius(d), p.flat_depth)


def flat_tool_section(p: Params, d: Dims) -> Loop | Circle:
    """The sun bore: a D section about the axis, PRESS_FIT_CLEARANCE outside the shaft's (a circle without a flat)."""
    return d_section(0.0, _bore_radius(d), p.flat_depth)


def socket_radius(d: Dims) -> float:
    """Radius of the D socket through the carrier plate, and of its centre hole: the thick part's radius plus the
    press-fit clearance."""
    return d.collar / 2 + PRESS_FIT_CLEARANCE


def socket_section(p: Params, d: Dims) -> Loop | Circle:
    """The tool for the socket of planet 0, at (orbit, 0); the other sockets are copies turned about the axis."""
    return d_section(d.orbit, socket_radius(d), p.flat_depth)


def socket_area(p: Params, d: Dims) -> float:
    return d_area(socket_radius(d), p.flat_depth)


def carrier_hole_section(p: Params, d: Dims) -> Loop | Circle:
    """The centre hole of the carrier, a D section about the axis that takes a link or output shaft's thick part."""
    return d_section(0.0, socket_radius(d), p.flat_depth)


def carrier_hole_area(p: Params, d: Dims) -> float:
    return d_area(socket_radius(d), p.flat_depth)


def thick_area(p: Params, d: Dims) -> float:
    return d_area(d.collar / 2, p.flat_depth)


def thick_section(p: Params, d: Dims) -> Loop | Circle:
    """The thick part of a carrier pin, a link shaft or the output shaft, about its own axis."""
    return d_section(0.0, d.collar / 2, p.flat_depth)


def flat_box(p: Params, d: Dims) -> tuple[Point, Point]:
    """Corners of the flat's box on the +X side of the shaft: Flat depth inside the edge to a millimeter beyond it,
    and a millimeter wider than the shaft on each side."""
    r = d.shaft / 2
    return ((r - p.flat_depth, -(r + 1)), (r + 1, r + 1))


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
