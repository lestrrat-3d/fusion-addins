"""Expected volumes and bounding boxes of each body, in the local frame (millimeters).

The bolt and nut volumes are ports of the m2bolt / m2nut gallery tests. The brackets' and the rail's volumes are computed
from the sections the builders draw (the gallery's own, read from decad builds, are in tests/test_expected.py and agree
to a few mm^3). The plaque is a box.
"""

from __future__ import annotations

import math

from . import bodies, sections
from .constants import (
    BASE_THICKNESS,
    BRACKET_WIDTH,
    CHAMFER_SIZE,
    JOINT_FIT,
    NUT_POCKET_ROUND,
    RAIL_HEIGHT,
    RAIL_ROUND,
    RAIL_WIDTH,
)
from .fasteners import (
    DRILL_POINT_ANGLE,
    DRILL_POINT_BASE_RADIUS,
    HEAD_CHAMFER_ANGLE,
    HEAD_CHAMFER_WIDTH,
    HEAD_DIAMETER,
    HEAD_HEIGHT,
    HEAD_POCKET_DEPTH,
    HEAD_POCKET_RADIUS,
    HOLE_RADIUS,
    NUT_ACROSS_FLATS,
    NUT_BEARING_DIAMETER,
    NUT_BORE_DIAMETER,
    NUT_CAVITY_HEIGHT,
    NUT_CAVITY_RADIUS,
    NUT_CHAMFER_ANGLE,
    NUT_CLEARANCE,
    NUT_THICKNESS,
    PILOT_DEPTH,
    SHANK_DIAMETER,
    SOCKET_ACROSS_FLATS,
    SOCKET_DEPTH,
    TIP_CHAMFER,
    UNDERHEAD_RADIUS,
    Site,
    cross,
    nut_across_corners,
)
from .params import Dimensions, Params
from .report import Expect

_BRACKET_TOLERANCE = 2.0  # the chamfer and the pocket's round are closed forms; the gallery's mesh bound is ~1 mm^3
_RAIL_TOLERANCE = 0.5
_PLAQUE_TOLERANCE = 1.0

Bounds = tuple[float, float, float, float, float, float]  # min x, y, z, max x, y, z


def _bolt_volume(length: float) -> float:
    """Port of m2bolt_test.go expectedVolume: Pappus on the blank section, plus the underhead fillet, less the
    hex socket and the drill-point pilot."""
    sh, hh = SHANK_DIAMETER / 2, HEAD_DIAMETER / 2
    pts = [
        (0.0, -length),
        (sh - TIP_CHAMFER, -length),
        (sh, -length + TIP_CHAMFER),
        (sh, 0.0),
        (hh, 0.0),
        (hh, HEAD_HEIGHT - HEAD_CHAMFER_WIDTH * math.tan(math.radians(HEAD_CHAMFER_ANGLE))),
        (hh - HEAD_CHAMFER_WIDTH, HEAD_HEIGHT),
        (0.0, HEAD_HEIGHT),
    ]
    total = 0.0
    for k, a in enumerate(pts):
        b = pts[(k + 1) % len(pts)]
        total += (a[0] ** 2 + a[0] * b[0] + b[0] ** 2) * (b[1] - a[1])
    blank = abs(total) * math.pi / 3
    r = UNDERHEAD_RADIUS
    fillet = 2 * math.pi * (sh + 0.78 * r) * r * r * (1 - math.pi / 4)
    socket = math.sqrt(3) / 2 * SOCKET_ACROSS_FLATS**2 * SOCKET_DEPTH
    base = DRILL_POINT_BASE_RADIUS
    pilot = math.pi * base**2 * PILOT_DEPTH
    cone = math.pi * base**2 * (base / math.tan(math.radians(DRILL_POINT_ANGLE / 2))) / 3
    return blank + fillet - socket - pilot - cone


def _clipped_hex_area(rho: float) -> float:
    """Area of the nut's hexagon inside the circle of radius rho about its centre [m2nut_test.go clippedHexArea]."""
    apothem = NUT_ACROSS_FLATS / 2
    if rho <= apothem:
        return math.pi * rho * rho
    if rho >= nut_across_corners() / 2:
        return math.sqrt(3) / 2 * NUT_ACROSS_FLATS**2
    half = math.acos(apothem / rho)
    segment = rho * rho * (half - math.sin(half) * math.cos(half))
    return math.pi * rho * rho - 6 * segment


def _nut_volume() -> float:
    """Port of m2nut_test.go expectedVolume: the hexagonal prism, less the bore and the two chamfers."""
    hex_area = math.sqrt(3) / 2 * NUT_ACROSS_FLATS**2
    bore = math.pi * NUT_BORE_DIAMETER**2 / 4 * NUT_THICKNESS
    slope = math.tan(math.radians(NUT_CHAMFER_ANGLE))
    bearing_r = NUT_BEARING_DIAMETER / 2
    depth = (nut_across_corners() / 2 - bearing_r) * slope
    steps = 2000
    chamfer = 0.0
    for i in range(steps):
        z = (i + 0.5) / steps * depth
        chamfer += (hex_area - _clipped_hex_area(bearing_r + z / slope)) * depth / steps
    return hex_area * NUT_THICKNESS - bore - 2 * chamfer


def _extent(points: list[tuple[float, float, float]]) -> Bounds:
    lo = tuple(min(q[i] for q in points) for i in range(3))
    hi = tuple(max(q[i] for q in points) for i in range(3))
    return (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])


def _site_bounds(site: Site, t0: float, t1: float, perpendicular: list[tuple[float, float]]) -> Bounds:
    """Bounds of a bolt or nut: t0..t1 along the site's direction (axis-aligned), and the (corner, third) offsets of its
    outline's vertices across it, where third = dir x corner."""
    third = cross(site.dir, site.corner)
    pts: list[tuple[float, float, float]] = []
    for t in (t0, t1):
        for a, b in perpendicular:
            pts.append(tuple(site.head[i] + site.dir[i] * t + site.corner[i] * a + third[i] * b for i in range(3)))
    return _extent(pts)  # pyright: ignore[reportArgumentType]


def _circle(radius: float) -> list[tuple[float, float]]:
    """Points on a circle, 720 of them, so its bounding box along any pair of axes is right to 1e-4 mm."""
    return [(radius * math.cos(math.pi * j / 360), radius * math.sin(math.pi * j / 360)) for j in range(720)]


def _hexagon(radius: float) -> list[tuple[float, float]]:
    return [(radius * math.cos(math.pi * j / 3), radius * math.sin(math.pi * j / 3)) for j in range(6)]



def _chamfer_volume(length: float, size: float, turning: float) -> float:
    """Volume a chamfer of `size` takes along an edge of `length` whose tangent turns by `turning` radians in all (2 pi
    round a closed outline): the cut's triangle has its centroid size / 3 inside the face (Pappus)."""
    return size * size / 2 * (length - size / 3 * turning)


def _hex_area(radius: float) -> float:
    return 3 * math.sqrt(3) / 2 * radius * radius


def bracket_volume(dm: Dimensions) -> float:
    """A bracket: the profile's area times its width, less the chamfer round both side faces' outlines, the nut pocket
    (its floor outline rounded by NUT_POCKET_ROUND) and the bolt hole through the channel floor.

    The pocket is the hexagon of corner radius NUT_CAVITY_RADIUS from the bottom face to the cavity's far face, less the
    round, which takes (1 - pi/4) r^2 along the floor outline's length (a hexagon's perimeter, six corners that each
    turn 60 degrees, so the round takes about the same share as a closed outline)."""
    segs = sections.outline_segments(dm)
    prism = sections.area(segs) * BRACKET_WIDTH
    chamfer = 2 * _chamfer_volume(sections.length(segs), CHAMFER_SIZE, 2 * math.pi)
    pocket_floor = BASE_THICKNESS - dm.channel_height  # the channel floor, z 4
    cavity_top = NUT_CAVITY_HEIGHT  # the pocket's far face, z 2
    hex_perimeter = 6 * NUT_CAVITY_RADIUS
    pocket = _hex_area(NUT_CAVITY_RADIUS) * cavity_top - (1 - math.pi / 4) * NUT_POCKET_ROUND**2 * hex_perimeter
    hole = math.pi * HOLE_RADIUS**2 * (pocket_floor - cavity_top)  # from the pocket to the channel floor
    return prism - chamfer - pocket - hole


def rail_volume(dm: Dimensions) -> float:
    """The rail: its section's area times the span, less each head pocket (z 6.4 to 8.4) and the hole under it, down to
    the rail's bottom."""
    r = RAIL_ROUND
    section = RAIL_WIDTH * RAIL_HEIGHT - (4 - math.pi) * r * r
    pocket = math.pi * HEAD_POCKET_RADIUS**2 * HEAD_POCKET_DEPTH
    hole = math.pi * HOLE_RADIUS**2 * (RAIL_HEIGHT - HEAD_POCKET_DEPTH)
    return section * dm.span - 2 * (pocket + hole)


def plaque_volume(p: Params) -> float:
    return p.plaque_width * p.plaque_height * p.plaque_thickness


def body_volume(name: str, p: Params, dm: Dimensions) -> Expect | None:
    """Expected volume of a body."""
    if name in bodies.BRACKETS:
        return Expect(bracket_volume(dm), _BRACKET_TOLERANCE)
    if name == bodies.RAIL:
        return Expect(rail_volume(dm), _RAIL_TOLERANCE)
    if name == bodies.PLAQUE:
        return Expect(plaque_volume(p), _PLAQUE_TOLERANCE)
    if bodies.is_bolt(name):
        value = _bolt_volume(bodies.site_of(name, dm).length)
        return Expect(value, 0.002 * value + 0.01)
    value = _nut_volume()
    return Expect(value, 0.002 * value + 0.01)


def plaque_axes(p: Params, dm: Dimensions) -> tuple[tuple[float, float, float], ...]:
    """Frame (origin, x, y, z) of the plaque's box as built: x along the span, y = n (the slot's normal), z = u (along
    the slot), the origin on the front-bottom corner (the box's x from 0 to W, y from 0 to t, z from 0 to H)."""
    x0 = (dm.span - p.plaque_width) / 2
    cy, cz = dm.seat
    n, u = dm.normal, dm.axis
    half = p.plaque_thickness / 2
    return ((x0, cy - half * n[0], cz - half * n[1]), (1.0, 0.0, 0.0), (0.0, n[0], n[1]), (0.0, u[0], u[1]))


def _plaque_bounds(p: Params, dm: Dimensions) -> Bounds:
    o, x, y, z = plaque_axes(p, dm)
    pts = []
    for a in (0.0, p.plaque_width):
        for b in (0.0, p.plaque_thickness):
            for c in (0.0, p.plaque_height):
                pts.append(tuple(o[i] + a * x[i] + b * y[i] + c * z[i] for i in range(3)))
    return (min(q[0] for q in pts), min(q[1] for q in pts), min(q[2] for q in pts),
            max(q[0] for q in pts), max(q[1] for q in pts), max(q[2] for q in pts))


def body_bounds(name: str, p: Params, dm: Dimensions) -> Bounds:
    """Bounding box of a body in the local frame."""
    if name in bodies.BRACKETS:
        x0 = 0.0 if name == bodies.BRACKET_1 else dm.span - BRACKET_WIDTH
        return (x0, 0.0, 0.0, x0 + BRACKET_WIDTH, dm.depth, dm.height)
    if name == bodies.RAIL:
        hw, z0 = RAIL_WIDTH / 2, BASE_THICKNESS - RAIL_HEIGHT + JOINT_FIT
        return (0.0, dm.rail_center - hw, z0, dm.span, dm.rail_center + hw, z0 + RAIL_HEIGHT)
    if name == bodies.PLAQUE:
        return _plaque_bounds(p, dm)
    site = bodies.site_of(name, dm)
    if bodies.is_bolt(name):
        return _site_bounds(site, 0.0, site.tip(), _circle(HEAD_DIAMETER / 2))
    t0 = site.cavity + NUT_CLEARANCE
    return _site_bounds(site, t0, t0 + NUT_THICKNESS, _hexagon(nut_across_corners() / 2))
