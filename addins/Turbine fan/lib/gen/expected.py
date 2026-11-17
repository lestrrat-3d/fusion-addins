"""Expected volumes and bounding boxes of each body, in the local frame (millimeters).

The bolt and nut volumes are ports of the m2bolt / m2nut gallery tests. The hub's volume at the two bearing presets and
the blades' volume, at the rotor sizes 128, 192 and 224, are the gallery model's own, read from a decad build at the revision in `config.GALLERY_REVISION`
(the gallery tests none of them). The hub's volume does not depend on the pitch, the hand or the mount. A blade's
volume does not depend on the pitch; the left-hand blade is the right-hand blade reflected and differs by 0.85 mm^3 at
128 mm (1.7 at 192 mm). Any other rotor size has no expected volume.
"""

from __future__ import annotations

import math

from . import bodies, blade
from .bridge import bridge_volume
from .constants import CLUTCH_MOUNT, LEFT_HAND
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
    cross,
    nut_across_corners,
)
from .params import Dimensions, Params, blade_angle
from .report import Expect
from .size import Size, size_for

# Hub volume of the gallery model for the two presets at the three tested rotor sizes: (shaft diameter, flat depth,
# clearance, rotor diameter).
_HUB_REFERENCE: dict[tuple[float, float, float, float], float] = {
    (5.0, 0.5, 0.05, 128.0): 10286.0083,
    (8.0, 0.75, 0.05, 128.0): 9703.7406,
    (5.0, 0.5, 0.05, 192.0): 29974.6904,
    (8.0, 0.75, 0.05, 192.0): 29095.0912,
    (5.0, 0.5, 0.05, 224.0): 35408.7061,
    (8.0, 0.75, 0.05, 224.0): 34380.4426,
}
_HUB_TOLERANCE = 5.0  # the gallery's mesh bound is up to 2.2 mm^3
# Blade volume of the gallery model at the three tested rotor sizes: (rotor diameter, left hand).
_BLADE_VOLUME: dict[tuple[float, bool], float] = {
    (128.0, False): 1945.9968, (128.0, True): 1945.1454,
    (192.0, False): 6362.3624, (192.0, True): 6360.6762,
    (224.0, False): 9914.7288, (224.0, True): 9912.1911,
}
# Fusion lofts through the same fit points with its own interpolation, so the blade's volume is held to 3 %.
_BLADE_RELATIVE_TOLERANCE = 0.03
_BLADE_BOUNDS_TOLERANCE = 0.3  # the spline's overshoot between fit points, measured at 0.12 at most
_EXACT_BOUNDS_TOLERANCE = 0.01

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


def hub_volume(p: Params) -> float | None:
    """The gallery hub's volume, or None when p is not one of the two bearing presets at a tested rotor size."""
    return _HUB_REFERENCE.get((p.shaft_diameter, p.flat_depth, p.bore_clearance, p.rotor_diameter))


def blade_volume(p: Params) -> float | None:
    """The gallery blade's volume, or None at an untested rotor size."""
    return _BLADE_VOLUME.get((p.rotor_diameter, p.hand == LEFT_HAND))


def body_volume(name: str, p: Params, dm: Dimensions) -> Expect | None:
    """Expected volume of a body, or None when none is known."""
    if name == bodies.HUB:
        value = hub_volume(p)
        # Directive: the sacrificial bridge layers (not in the gallery model) add their hole sections' volume when the
        # box is checked (docs/turbinefan/directives.md).
        return None if value is None else Expect(value + bridge_volume(p, dm), _HUB_TOLERANCE)
    if name in bodies.BLADES:
        value = blade_volume(p)
        return None if value is None else Expect(value, _BLADE_RELATIVE_TOLERANCE * value)
    if bodies.is_bolt(name):
        value = _bolt_volume(bodies.site_of(name, dm).length)
        return Expect(value, 0.002 * value + 0.01)
    value = _nut_volume()
    return Expect(value, 0.002 * value + 0.01)


def _extent(points: list[tuple[float, float, float]]) -> Bounds:
    lo = tuple(min(q[i] for q in points) for i in range(3))
    hi = tuple(max(q[i] for q in points) for i in range(3))
    return (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])


def dm_size(p: Params) -> Size:
    return size_for(p.rotor_diameter)


def blade_bounds(p: Params, k: int) -> Bounds:
    """Bounds of blade k (1 to 3): blade 1's section fit points turned about +Z by 120 degrees per blade."""
    turn = blade_angle(k) - blade_angle(1)
    pts = [(*blade.rotate((x, y), turn), z) for x, y, z in blade.blade_sample_points(p.blade_pitch, p.hand == LEFT_HAND, dm_size(p))]
    return _extent(pts)


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


def body_bounds(name: str, p: Params, dm: Dimensions) -> Bounds:
    """Bounding box of a body in the local frame."""
    if name == bodies.HUB:
        r = dm.size.hub_radius
        return (-r, -r, 0.0, r, r, dm.size.hub_length)
    if name in bodies.BLADES:
        return blade_bounds(p, bodies.BLADES.index(name) + 1)
    site = bodies.site_of(name, dm)
    if bodies.is_bolt(name):
        return _site_bounds(site, 0.0, site.tip(), _circle(HEAD_DIAMETER / 2))
    t0 = site.cavity + NUT_CLEARANCE
    return _site_bounds(site, t0, t0 + NUT_THICKNESS, _hexagon(nut_across_corners() / 2))


def bounds_tolerance(name: str, p: Params | None = None) -> float:
    """The spline's overshoot grows with the blade, which scales by rotor_diameter / 128 (0.12 mm at 128 at most)."""
    if name not in bodies.BLADES:
        return _EXACT_BOUNDS_TOLERANCE
    scale = 1.0 if p is None else max(1.0, p.rotor_diameter / 128.0)
    return _BLADE_BOUNDS_TOLERANCE * scale
