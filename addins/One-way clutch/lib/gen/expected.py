"""Expected volumes and bounding boxes of each body, in the local frame (millimeters).

The bolt and nut volumes are ports of the m2bolt / m2nut gallery tests. A printed body's volume is computed from the
same sections the builders draw: the extruded profile's area times its height, less the chamfers and cuts. The ring's
volume is the gallery's own (9845.74 +- 5.43 mm^3 in instructions.md); the other printed parts have none in the
gallery, so each is computed here and carries a tolerance for the chamfer and numeric error.
"""

from __future__ import annotations

import math

from . import bodies, measure, sections
from .bridge import bridge_volume
from .constants import (
    ADAPTER_FROM,
    ADAPTER_THICKNESS,
    ADAPTER_TO,
    BACK_PLATE_THICKNESS,
    CHAMFER_LOOP_MIN,
    COVER_FROM,
    COVER_TO,
    HUB_FROM,
    HUB_HEIGHT,
    PLATE_CHAMFER,
    RING_CHAMFER,
    RING_FROM,
    RING_HEIGHT,
    RING_TO,
)
from .fasteners import (
    DRILL_POINT_ANGLE,
    DRILL_POINT_BASE_RADIUS,
    HEAD_CHAMFER_ANGLE,
    HEAD_CHAMFER_WIDTH,
    HEAD_DIAMETER,
    HEAD_HEIGHT,
    HEAD_POCKET_RADIUS,
    HOLE_RADIUS,
    NUT_ACROSS_FLATS,
    NUT_BEARING_DIAMETER,
    NUT_BORE_DIAMETER,
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
    HEAD_POCKET_DEPTH,
    Site,
    nut_across_corners,
)
from .params import Dimensions, Params
from .report import Expect

RING_VOLUME = 9845.74  # instructions.md "Ring": volume 9845.74 +- 5.43 mm^3 (the 605ZZ ring; it does not depend on c)
_RING_TOLERANCE = 5.43
_PLATE_TOLERANCE = 2.5  # numeric error of the scan and of the chamfer along the D loop's corners
_HUB_TOLERANCE = 3.0
_ADAPTER_TOLERANCE = 3.0

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


# --- Printed bodies --------------------------------------------------------------------------------------------------


def hub_face_area(dm: Dimensions) -> float:
    """Net area of one hub face: the outline less the D bore and the three bolt holes."""
    return (measure.loop_area(sections.hub_outline(dm)) - measure.loop_area(sections.bore_loop(dm))
            - 3 * measure.circle_area(HOLE_RADIUS))


def hub_is_chamfered(dm: Dimensions) -> bool:
    """Every hub's faces are over 400 mm^2, so each takes the chamfer (`HubChamfer`), as the gallery's hub() does."""
    return True


def hub_chamfer_length(dm: Dimensions) -> float:
    """Length of the runs one hub face's chamfer follows: each pawl's outline less its head run (flank, tip round and
    lock face, which stay sharp), and the whole D loop when it is CHAMFER_LOOP_MIN or more."""
    outline = sections.hub_outline(dm)
    per_pawl = len(outline) // 3
    head = sum(measure.loop_length([outline[k * per_pawl + i]]) for k in range(3) for i in (3, 4, 5))
    total = measure.loop_length(outline) - head
    if dm.bore_loop >= CHAMFER_LOOP_MIN:
        total += dm.bore_loop
    return total


def hub_volume(dm: Dimensions) -> Expect:
    """The prism, less an estimate of the chamfer: the triangle of `HubChamfer` along both faces' runs. The estimate
    ignores the corners where a run ends, so the tolerance holds a chamfer that ends short or runs past."""
    prism = hub_face_area(dm) * HUB_HEIGHT
    estimate = 2 * 0.5 * dm.hub_chamfer**2 * hub_chamfer_length(dm)
    return Expect(prism - estimate, _HUB_TOLERANCE)


def ring_volume_computed(dm: Dimensions) -> float:
    """The ring from its sections, to compare with the gallery's RING_VOLUME."""
    outline, tooth = sections.ring_outline(dm), sections.tooth_loop(dm)
    void = measure.loop_area(tooth)
    prism = (measure.loop_area(outline) - void - 3 * measure.circle_area(HOLE_RADIUS)) * RING_HEIGHT
    chamfer = 2 * measure.chamfer_volume(measure.loop_length(outline), RING_CHAMFER, 2 * math.pi)
    cuts = 0.0
    for tool in (sections.ring_back_points(dm), sections.ring_front_points(dm)):
        lo, hi = max(RING_FROM, min(z for _, z in tool)), min(RING_TO, max(z for _, z in tool))
        n = 4000
        dz = (hi - lo) / n
        for i in range(n):
            z = lo + (i + 0.5) * dz
            # The tool's outer radius at z is at least the tooth root, so it takes the whole annulus less the void.
            b = measure.outer_radius_at(tool, z)
            if b > 0:
                cuts += (math.pi * b * b - void) * dz
    pocket = (measure.hexagon_area(NUT_CAVITY_RADIUS) - measure.circle_area(HOLE_RADIUS)) * 2.0
    return prism - chamfer - cuts - 3 * pocket


def _plate_volume(dm: Dimensions, tool: tuple[tuple[float, float], ...], z0: float, pocket_area: float) -> float:
    prism = (measure.circle_area(dm.plate_radius) - measure.loop_area(sections.bore_loop(dm))
             - 3 * measure.circle_area(HOLE_RADIUS)) * BACK_PLATE_THICKNESS
    length = 2 * math.pi * dm.plate_radius
    turning = 2 * math.pi
    if dm.bore_loop >= CHAMFER_LOOP_MIN:
        length += dm.bore_loop
        turning += 0.0  # the D loop's own chamfer: a hole's rim turns the other way, so its centroid term is small
    chamfer = measure.chamfer_volume(length, PLATE_CHAMFER, turning)
    cut = measure.revolved_volume(tool, z0, z0 + BACK_PLATE_THICKNESS, dm.plate_radius)
    pockets = 3 * (pocket_area - measure.circle_area(HOLE_RADIUS)) * 2.0
    return prism - chamfer - cut - pockets


def back_plate_volume(dm: Dimensions) -> Expect:
    value = _plate_volume(dm, sections.back_plate_points(dm), 0.0, measure.hexagon_area(NUT_CAVITY_RADIUS))
    return Expect(value, _PLATE_TOLERANCE)


def cover_volume(dm: Dimensions) -> Expect:
    value = _plate_volume(dm, sections.cover_points(dm), COVER_FROM, measure.circle_area(HEAD_POCKET_RADIUS))
    return Expect(value, _PLATE_TOLERANCE)


def adapter_volume(dm: Dimensions) -> Expect:
    holes = 1 * measure.circle_area(dm.adapter_inner) + 9 * measure.circle_area(HOLE_RADIUS)
    prism = (measure.circle_area(dm.adapter_radius) - holes) * ADAPTER_THICKNESS
    chamfer = 2 * (measure.chamfer_volume(2 * math.pi * dm.adapter_radius, PLATE_CHAMFER, 2 * math.pi)
                   + measure.chamfer_volume(2 * math.pi * dm.adapter_inner, PLATE_CHAMFER, 0.0))
    pockets = 6 * (measure.circle_area(HEAD_POCKET_RADIUS) - measure.circle_area(HOLE_RADIUS)) * HEAD_POCKET_DEPTH
    return Expect(prism - chamfer - pockets, _ADAPTER_TOLERANCE)


def body_volume(name: str, p: Params, dm: Dimensions) -> Expect | None:
    """Expected volume of a body."""
    if name == bodies.HUB:
        return hub_volume(dm)
    if name == bodies.RING:
        if dm.growth == 0.0:
            # The 605ZZ ring is the gallery's (it does not depend on BoreClearance).
            return Expect(RING_VOLUME, _RING_TOLERANCE)
        # A grown ring has no gallery volume: it is computed from the sections.
        return Expect(ring_volume_computed(dm), _RING_TOLERANCE)
    # Sacrificial bridge layers (not in the gallery model) add their hole sections' volume when the box is checked.
    if name == bodies.BACK_PLATE:
        v = back_plate_volume(dm)
        return Expect(v.value + bridge_volume(name, p, dm), v.tol)
    if name == bodies.COVER:
        v = cover_volume(dm)
        return Expect(v.value + bridge_volume(name, p, dm), v.tol)
    if name == bodies.ADAPTER:
        v = adapter_volume(dm)
        return Expect(v.value + bridge_volume(name, p, dm), v.tol)
    if bodies.is_bolt(name):
        value = _bolt_volume(bodies.site_of(name, dm).length)
        return Expect(value, 0.002 * value + 0.01)
    value = _nut_volume()
    return Expect(value, 0.002 * value + 0.01)


# --- Bounds ----------------------------------------------------------------------------------------------------------


def _fastener_bounds(site: Site, t0: float, t1: float, radius: float, corner_angles: bool) -> Bounds:
    """Bounds of a bolt or a nut on a site whose direction is along Z. A bolt is round about the site's line
    (radius = half the head); a nut's hexagon has a corner along the site's corner direction."""
    zs = sorted((site.head[2] + site.dir[2] * t0, site.head[2] + site.dir[2] * t1))
    if not corner_angles:
        xs = (site.head[0] - radius, site.head[0] + radius)
        ys = (site.head[1] - radius, site.head[1] + radius)
    else:
        base = math.atan2(site.corner[1], site.corner[0])
        pts = [(site.head[0] + radius * math.cos(base + k * math.pi / 3),
                site.head[1] + radius * math.sin(base + k * math.pi / 3)) for k in range(6)]
        xs = (min(p[0] for p in pts), max(p[0] for p in pts))
        ys = (min(p[1] for p in pts), max(p[1] for p in pts))
    return (xs[0], ys[0], zs[0], xs[1], ys[1], zs[1])


def body_bounds(name: str, p: Params, dm: Dimensions) -> Bounds:
    """Bounding box of a body in the local frame."""
    if name == bodies.HUB:
        x0, y0, x1, y1 = measure.loop_bounds(sections.layout(sections.hub_outline(dm), dm.sign))
        return (x0, y0, HUB_FROM, x1, y1, HUB_FROM + HUB_HEIGHT)
    if name == bodies.RING:
        x0, y0, x1, y1 = measure.loop_bounds(sections.ring_outline(dm))
        return (x0, y0, RING_FROM, x1, y1, RING_TO)
    if name == bodies.BACK_PLATE:
        return (-dm.plate_radius, -dm.plate_radius, 0.0, dm.plate_radius, dm.plate_radius, BACK_PLATE_THICKNESS)
    if name == bodies.COVER:
        return (-dm.plate_radius, -dm.plate_radius, COVER_FROM, dm.plate_radius, dm.plate_radius, COVER_TO)
    if name == bodies.ADAPTER:
        return (-dm.adapter_radius, -dm.adapter_radius, ADAPTER_FROM, dm.adapter_radius, dm.adapter_radius, ADAPTER_TO)
    site = bodies.site_of(name, dm)
    if bodies.is_bolt(name):
        return _fastener_bounds(site, 0.0, site.tip(), HEAD_DIAMETER / 2, False)
    t0 = site.cavity + NUT_CLEARANCE
    return _fastener_bounds(site, t0, t0 + NUT_THICKNESS, nut_across_corners() / 2, True)
