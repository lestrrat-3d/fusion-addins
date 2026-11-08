"""Expected volumes and axial bounds of each part, from the 2D sections and the edge finishing (millimeters).

The bolt and nut volumes are ports of the m2bolt / m2nut gallery tests (a800069)."""

from __future__ import annotations

import dataclasses
import math

from . import edgefinish, layout
from .curves import loop_polygon
from .dims import Dims
from .ears import ring_blank_area, ring_xmax
from . import gears
from .involute import GearDims, gear_outline_polygon
from .fasteners import (
    DRILL_POINT_ANGLE,
    DRILL_POINT_BASE_RADIUS,
    FASTENER_LENGTH,
    HEAD_CHAMFER_ANGLE,
    HEAD_CHAMFER_WIDTH,
    HEAD_DIAMETER,
    HEAD_HEIGHT,
    NUT_ACROSS_FLATS,
    NUT_BEARING_DIAMETER,
    NUT_BORE_DIAMETER,
    NUT_CHAMFER_ANGLE,
    NUT_THICKNESS,
    PILOT_DEPTH,
    SHANK_DIAMETER,
    SOCKET_ACROSS_FLATS,
    SOCKET_DEPTH,
    TIP_CHAMFER,
    UNDERHEAD_RADIUS,
    head_pocket_diameter,
    nut_across_corners,
    nut_cavity_height,
    nut_pocket_flats,
)
from .params import PIN_COLLAR_CLEARANCE, PIN_COLLAR_THICKNESS, PLANET_BEARING_LIFT, Params
from .polygon import polygon_area
from .report import Expect
from .sections import carrier_plate_outline, cover_window_loops, groove_area, key_tool_area

_DENSE = 60


def _area(gd: GearDims) -> float:
    return polygon_area(gear_outline_polygon(gd, _DENSE))


def _fillet_allowance(gd: GearDims, thickness: float) -> float:
    """Corner-area estimate of the 2N root fillets, times the thickness."""
    return 2 * gd.teeth * gd.fillet**2 * (1 - math.pi / 4) * thickness


def _chamfer(p: Params, radius: float) -> float:
    """Volume removed by the seat chamfer on a circular rim of the given radius."""
    sc = p.seat_chamfer
    if sc == 0:
        return 0.0
    return sc * sc / 2 * 2 * math.pi * (radius + sc / 3)


def _gear_gd(p: Params, part: str) -> GearDims:
    return gears.sun_gear(p) if part == "sun" else gears.planet_gear(p)


def _bolt_volume(length: float) -> float:
    """Port of m2bolt_test.go expectedVolume: Pappus on the blank section, plus the underhead fillet, less the
    hex socket and the drill-point pilot."""
    sh, hh = SHANK_DIAMETER / 2, HEAD_DIAMETER / 2
    # Blank section (radius, height): tip centre, tip chamfer, shank, head, head chamfer, head top.
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
    # Each of the six flats cuts a circular segment off the circle.
    half = math.acos(apothem / rho)
    segment = rho * rho * (half - math.sin(half) * math.cos(half))
    return math.pi * rho * rho - 6 * segment


def _nut_volume() -> float:
    """Port of m2nut_test.go expectedVolume: the hexagonal prism, less the bore and the two chamfers.

    The gallery integrates with 20000 midpoint steps; 2000 differ by less than 1e-7.
    """
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


def _overlap(span: tuple[float, float], lo: float, hi: float) -> float:
    return max(0.0, min(span[1], hi) - max(span[0], lo))


def part_volume(p: Params, d: Dims, part: str, fillet_radius: float | None = None) -> Expect:
    """Expected volume (mm^3) and tolerance of the master body of part.

    fillet_radius replaces the gear's root fillet radius (0 = no fillet) when a fallback was taken.
    """
    t, tv, wb = p.gear_thickness, p.cover_thickness, d.bearing.width
    if part in ("sun", "planet"):
        gd = _gear_gd(p, part)
        if fillet_radius is not None:
            gd = dataclasses.replace(gd, fillet=fillet_radius)
        f = _fillet_allowance(gd, t)
        if part == "sun":
            bore = key_tool_area(p, d)
            value = (_area(gd) - bore) * t + f
        else:
            value = (
                (_area(gd) - math.pi * d.lip**2 / 4) * t
                - math.pi / 4 * (d.pocket**2 - d.lip**2) * wb
                - _chamfer(p, d.pocket / 2)
                + f
            )
        return Expect(value, 0.5 * f + 0.002 * value)
    if part == "ring":
        tool = _area(gears.ring_tool(p))
        bolts = 4 * math.pi * (p.bolt_hole_diameter / 2) ** 2
        cavities = 8 * (math.sqrt(3) / 2 * nut_pocket_flats() ** 2 - math.pi * (p.bolt_hole_diameter / 2) ** 2)
        value = (ring_blank_area(p, d) - bolts - tool) * d.ring_length - cavities * nut_cavity_height()
        value -= edgefinish.edge_chamfer_volume(p, d, part)
        return Expect(value, 0.002 * value)
    if part == "cover":
        bolts = 4 * math.pi * (p.bolt_hole_diameter / 2) ** 2
        windows = sum(polygon_area(loop_polygon(w)) for w in cover_window_loops(p, d))
        frame = (math.pi * d.ring_outer**2 - math.pi * d.lip**2 / 4 - bolts - windows) * tv
        boss = math.pi / 4 * (d.cover_boss**2 - d.pocket**2) * wb
        pockets = 4 * math.pi * ((head_pocket_diameter() / 2) ** 2 - (p.bolt_hole_diameter / 2) ** 2) * HEAD_HEIGHT
        value = frame - pockets + boss - _chamfer(p, d.pocket / 2)
        value -= edgefinish.edge_chamfer_volume(p, d, part)
        return Expect(value, 0.002 * value)
    if part in ("housing_bearing", "planet_bearing"):
        value = math.pi / 4 * (22.0**2 - 8.0**2) * 7.0
        return Expect(value, 0.001 * value)
    if part == "carrier":
        hull = polygon_area(loop_polygon(carrier_plate_outline(p, d)))
        n = p.planet_count
        g = p.stage_gap
        collar_len = g - PLANET_BEARING_LIFT - PIN_COLLAR_CLEARANCE
        has_collar = g >= PLANET_BEARING_LIFT + PIN_COLLAR_CLEARANCE + PIN_COLLAR_THICKNESS
        value = (
            (hull - key_tool_area(p, d)) * p.carrier_thickness
            + n * math.pi * d.pin**2 / 4 * (t + g)
            + (n * math.pi / 4 * (d.collar**2 - d.pin**2) * collar_len if has_collar else 0.0)
        )
        value -= edgefinish.edge_chamfer_volume(p, d, part)
        return Expect(value, 0.002 * value)
    if part == "bolt":
        value = _bolt_volume(FASTENER_LENGTH)
        return Expect(value, 0.002 * value + 0.01)
    if part == "nut":
        value = _nut_volume()
        return Expect(value, 0.002 * value + 0.01)
    spec = {
        "input_shaft": layout.input_shaft_spec,
        "link_shaft": layout.link_shaft_spec,
        "output_shaft": layout.output_shaft_spec,
    }[part](p, d)
    if spec is None:
        raise ValueError(f"{part} does not exist with {p.stages} stage(s)")
    r = d.shaft / 2
    value = math.pi * r * r * (spec.top - spec.bottom)
    if spec.collar is not None:
        lo, hi = spec.collar
        value += math.pi * (d.collar**2 / 4 - r * r) * (hi - lo)
    if p.key_depth > 0:
        cut = sum(_overlap((spec.bottom, spec.top), lo, hi) for lo, hi in spec.grooves)
        value -= 3 * groove_area(p, d) * cut
    return Expect(value, 0.002 * value)


def part_local_bounds(p: Params, d: Dims, part: str) -> tuple[float, float, float | None]:
    """(zmin, zmax, xmax or None) of the master body of part, in part-local coordinates."""
    zmin, zmax = layout.part_local_z(p, d, part)
    if part == "sun":
        xmax: float | None = _gear_gd(p, "sun").tip
    elif part == "planet":
        xmax = _gear_gd(p, "planet").tip
    elif part == "bolt":
        xmax = HEAD_DIAMETER / 2
    elif part == "nut":
        xmax = nut_across_corners() / 2
    elif part == "ring":
        xmax = ring_xmax(p, d)
    elif part == "cover":
        xmax = d.ring_outer
    elif part in ("housing_bearing", "planet_bearing"):
        xmax = 11.0
    elif part == "carrier":
        xmax = d.orbit + d.boss / 2
    else:
        xmax = None
    return (zmin, zmax, xmax)


def assembled_z(p: Params, d: Dims) -> dict[str, tuple[float, float]]:
    """Axial range of every instance after its pose."""
    out: dict[str, tuple[float, float]] = {}
    for inst in layout.instances(p, d):
        lo, hi = layout.part_local_z(p, d, inst.part)
        zs = [inst.pose.apply((0.0, 0.0, z))[2] for z in (lo, hi)]
        out[inst.name] = (min(zs), max(zs))
    return out
