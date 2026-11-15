"""Expected volumes and bounding boxes of each body, in the local frame (millimeters).

The bolt and nut volumes are ports of the m2bolt / m2nut gallery tests. The pin's and handle's volumes and the arm's
volume at the two bearing presets are the gallery model's own, read from a decad build at the revision in
`config.GALLERY_REVISION` (the gallery tests none of them). The arm's volume changes by 159.5 mm^3 for each mm of throw:
a 20 mm wide straight arm of 8 mm thickness, less the face chamfers' 0.5 mm^3 per mm.
"""

from __future__ import annotations

import math

from . import bodies
from .constants import (
    ARM_RADIUS,
    ARM_THICKNESS,
    HANDLE_FROM,
    HANDLE_PROFILE,
    HEAD_FROM,
    HEAD_LENGTH,
    HEAD_R,
    STUB_FROM,
)
from .fasteners import (
    DRILL_POINT_ANGLE,
    DRILL_POINT_BASE_RADIUS,
    HEAD_CHAMFER_ANGLE,
    HEAD_CHAMFER_WIDTH,
    HEAD_DIAMETER,
    HEAD_HEIGHT,
    NUT_ACROSS_FLATS,
    NUT_BEARING_DIAMETER,
    NUT_BORE_DIAMETER,
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
    nut_across_corners,
)
from .params import Dimensions, Params
from .report import Expect

# Arm volume of the gallery model at Throw 55 for the two presets: (shaft diameter, flat depth, clearance).
_ARM_REFERENCE: dict[tuple[float, float, float], float] = {
    (5.0, 0.5, 0.05): 11441.1239,
    (8.0, 0.75, 0.05): 11472.3045,
}
_ARM_REFERENCE_THROW = 55.0
_ARM_PER_MM_THROW = 159.5
_ARM_TOLERANCE = 3.0  # the gallery's mesh bound is up to 1.1 mm^3
_PIN_VOLUME = 4098.4072
_PIN_TOLERANCE = 3.0  # the gallery's mesh bound is 1.3 mm^3
_HANDLE_VOLUME = 4513.6335
_HANDLE_TOLERANCE = 1.0

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


def arm_volume(p: Params) -> float | None:
    """The gallery arm's volume, or None when p is not one of the two bearing presets (any throw)."""
    base = _ARM_REFERENCE.get((p.shaft_diameter, p.flat_depth, p.bore_clearance))
    if base is None:
        return None
    return base + _ARM_PER_MM_THROW * (p.throw - _ARM_REFERENCE_THROW)


def body_volume(name: str, p: Params, dm: Dimensions) -> Expect | None:
    """Expected volume of a body, or None when none is known."""
    if name == bodies.ARM:
        value = arm_volume(p)
        return None if value is None else Expect(value, _ARM_TOLERANCE)
    if name == bodies.PIN:
        return Expect(_PIN_VOLUME, _PIN_TOLERANCE)
    if name == bodies.HANDLE:
        return Expect(_HANDLE_VOLUME, _HANDLE_TOLERANCE)
    if bodies.is_bolt(name):
        value = _bolt_volume(bodies.site_of(name, dm).length)
        return Expect(value, 0.002 * value + 0.01)
    value = _nut_volume()
    return Expect(value, 0.002 * value + 0.01)


def _site_bounds(site: Site, t0: float, t1: float, along_corner: float, across: float) -> Bounds:
    """Bounds of a bolt or nut: t0..t1 along the site's direction, +-along_corner along its corner direction and
    +-across along the third axis. Site directions are axis-aligned."""
    lo: list[float] = []
    hi: list[float] = []
    for i in range(3):
        if abs(site.dir[i]) > 0.5:
            a, b = site.head[i] + site.dir[i] * t0, site.head[i] + site.dir[i] * t1
            lo.append(min(a, b))
            hi.append(max(a, b))
        else:
            half = along_corner if abs(site.corner[i]) > 0.5 else across
            lo.append(site.head[i] - half)
            hi.append(site.head[i] + half)
    return (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])


def body_bounds(name: str, p: Params, dm: Dimensions) -> Bounds:
    """Bounding box of a body in the local frame."""
    if name == bodies.ARM:
        return (-ARM_RADIUS, -dm.reach, 0.0, ARM_RADIUS, p.throw + ARM_RADIUS, ARM_THICKNESS)
    if name == bodies.PIN:
        top = HEAD_FROM + HEAD_LENGTH
        return (-HEAD_R, p.throw - HEAD_R, STUB_FROM, HEAD_R, p.throw + HEAD_R, top)
    if name == bodies.HANDLE:
        r = max(r for _, r in HANDLE_PROFILE)
        z0 = HANDLE_FROM + min(z for z, _ in HANDLE_PROFILE)
        z1 = HANDLE_FROM + max(z for z, _ in HANDLE_PROFILE)
        return (-r, p.throw - r, z0, r, p.throw + r, z1)
    site = bodies.site_of(name, dm)
    if bodies.is_bolt(name):
        return _site_bounds(site, 0.0, site.tip(), HEAD_DIAMETER / 2, HEAD_DIAMETER / 2)
    t0 = site.cavity + NUT_CLEARANCE
    return _site_bounds(site, t0, t0 + NUT_THICKNESS, nut_across_corners() / 2, NUT_ACROSS_FLATS / 2)
