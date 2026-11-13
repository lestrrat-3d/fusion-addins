"""Expected volumes and z ranges of each part, from the 2D sections and the edge finishing (millimeters).

The bolt and nut volumes are ports of the m2bolt / m2nut gallery tests (the gearbox add-in's copies, a800069). The other
formulas are the add-in's own: the gallery tests none of them.
"""

from __future__ import annotations

import math

from . import bodies, edgefinish, gears
from .constants import (
    ANCHOR_COUNTER_RADIUS, CARRIER_BOSS_RADIUS, COLLAR_LENGTH, COLLAR_RADIUS, GREAT_BORE, GREAT_COUNTER_RADIUS,
    LIP_RADIUS, MOUNT_RADIUS, SEAT_RADIUS, SPRING_SOCKET_R, WHEEL_COUNTER_RADIUS, WHEEL_HIGH, WHEEL_LOW,
)
from .curves import Line, loop_polygon
from .fasteners import (
    DRILL_POINT_ANGLE,
    DRILL_POINT_BASE_RADIUS,
    HEAD_CHAMFER_ANGLE,
    HEAD_CHAMFER_WIDTH,
    HEAD_DIAMETER,
    HEAD_HEIGHT,
    HOLE_RADIUS,
    NUT_ACROSS_FLATS,
    NUT_BEARING_DIAMETER,
    NUT_BORE_DIAMETER,
    NUT_CAVITY_RADIUS,
    NUT_CHAMFER_ANGLE,
    NUT_THICKNESS,
    PILOT_DEPTH,
    SHANK_DIAMETER,
    SOCKET_ACROSS_FLATS,
    SOCKET_DEPTH,
    TIP_CHAMFER,
    UNDERHEAD_RADIUS,
    HEAD_POCKET_RADIUS,
    nut_across_corners,
)
from .involute import GearDims, gear_outline_polygon
from .layout import Geometry
from .motion import state_at
from .polygon import polygon_area
from .pose import body_poses
from .report import Expect
from .sections import (
    ARBOR_FLATS,
    arbor_meridian,
    BODY_D,
    DRIVE_D,
    END_D,
    KEYED_COUNTER_D,
    KEYED_RING_D,
    anchor_outline,
    crutch_outline,
    crutch_slot,
    escape_windows,
    pawl_loop,
    pendulum_outline,
    plate_outline,
    d_area,
    ratchet_tool_outline,
    window_loop,
)
# Private on purpose: the segment area is a helper of the D section; expected.py reuses it for the arbor flats.
from .sections import _segment_area  # noqa: E402
from .spring import profile, spring_params

_DENSE = 60
_STEP = math.radians(0.1)
_CAVITY_HEIGHT = 2.0  # the nut cavity's z span [24, 26]
_PAWL_OVERLAP = 10 * math.pi / 180  # the pawl loop's r 7 arc, 10 degrees, lies in the core's r 7 to 7.5 strip


def _loop_area(loop) -> float:
    return abs(polygon_area(loop_polygon(loop, max_step=_STEP)))


def _gear_area(gd: GearDims) -> float:
    return polygon_area(gear_outline_polygon(gd, _DENSE))


def _fillet_allowance(gd: GearDims, thickness: float) -> float:
    """Corner-area estimate of the 2N root fillets, times the thickness."""
    return 2 * gd.teeth * gd.fillet**2 * (1 - math.pi / 4) * thickness


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


def _overlap(span: tuple[float, float], lo: float, hi: float) -> float:
    return max(0.0, min(span[1], hi) - max(span[0], lo))


def _arbor_volume(part: str) -> float:
    """Every constant-radius run of the meridian as a cylinder, less the flat boxes over it [arbors_internal_test.go]."""
    value = 0.0
    for seg in arbor_meridian(part):
        if not (isinstance(seg, Line) and seg.start[0] == seg.end[0] and seg.start[0] > 0.0):
            continue
        r = seg.start[0]
        z_a, z_b = min(seg.start[1], seg.end[1]), max(seg.start[1], seg.end[1])
        value += math.pi * r * r * (z_b - z_a)
        for flat_x, z0, z1 in ARBOR_FLATS[part]:
            if r > flat_x:
                value -= _segment_area(r, flat_x) * _overlap((z_a, z_b), z0, z1)
    return value


def _tooth_outside_area(g: Geometry) -> float:
    """Area of the escape tooth outside the disc r 33: triangle T, L', B' less the circular segment of its chord."""
    t, ll, b = g.tooth_tip, g.tooth_l, g.tooth_b
    r = 33.0

    def on_circle(q: tuple[float, float]) -> tuple[float, float]:
        dx, dy = q[0] - t[0], q[1] - t[1]
        qa = dx * dx + dy * dy
        qb = 2 * (t[0] * dx + t[1] * dy)
        qc = t[0] ** 2 + t[1] ** 2 - r * r
        s = (-qb - math.sqrt(qb * qb - 4 * qa * qc)) / (2 * qa)  # first crossing from the tip
        return (t[0] + s * dx, t[1] + s * dy)

    lp, bp = on_circle(ll), on_circle(b)
    tri = abs(polygon_area([t, lp, bp]))
    chord = math.hypot(lp[0] - bp[0], lp[1] - bp[1])
    half = math.asin(chord / (2 * r))
    segment = r * r * (half - math.sin(half) * math.cos(half))
    return tri - segment


def part_volume(g: Geometry, part: str) -> Expect:
    """Expected volume (mm^3) and tolerance of the master body of part, before its pose."""
    p = g.params
    d_end, d_body, d_drive = d_area(END_D), d_area(BODY_D), d_area(DRIVE_D)
    d_kc, d_kr = d_area(KEYED_COUNTER_D), d_area(KEYED_RING_D)
    c = edgefinish.chamfer_volume(g, part)
    pi = math.pi
    if part == "back_plate":
        win = _loop_area(window_loop(g, -1.0)) + _loop_area(window_loop(g, 1.0))
        plate = _loop_area(plate_outline(98.0))
        value = (plate - win - 3 * pi * LIP_RADIUS**2 - 2 * pi * MOUNT_RADIUS**2) * 6
        value += 4 * pi * 5.0**2 * 28.0
        value -= 3 * pi * (SEAT_RADIUS**2 - LIP_RADIUS**2) * 5
        value -= 4 * (pi * HOLE_RADIUS**2 * 5 + pi * NUT_CAVITY_RADIUS**2 * _CAVITY_HEIGHT)
        value -= c
        return Expect(value, 0.002 * value)
    if part == "front_plate":
        win = _loop_area(window_loop(g, -1.0)) + _loop_area(window_loop(g, 1.0))
        plate = _loop_area(plate_outline(82.0))
        value = (plate - win - 3 * pi * LIP_RADIUS**2) * 6
        value -= 3 * pi * (SEAT_RADIUS**2 - LIP_RADIUS**2) * 5
        value -= 4 * (pi * HOLE_RADIUS**2 * 4 + pi * HEAD_POCKET_RADIUS**2 * 2)
        value -= d_end * 3 + pi * SPRING_SOCKET_R**2 * 3
        value -= c
        return Expect(value, 0.002 * value)
    if part in ("escape_arbor", "pallet_arbor", "great_wheel_arbor", "suspension_pin"):
        value = _arbor_volume(part)
        return Expect(value, 0.002 * value)
    if part == "escape_wheel":
        pinion = gears.pinion_dims(p)
        windows = sum(_loop_area(w) for w in escape_windows())
        value = (pi * 33.0**2 - windows) * (WHEEL_HIGH - WHEEL_LOW)
        value += 30 * _tooth_outside_area(g) * (WHEEL_HIGH - WHEEL_LOW)
        value += _gear_area(pinion) * 20.5
        value -= pi * WHEEL_COUNTER_RADIUS**2 * (1.80 + 1.05) + d_body * 20.65 + c
        f = _fillet_allowance(pinion, 21.0)
        value += f
        return Expect(value, 0.5 * f + 0.002 * value)
    if part == "anchor":
        value = _loop_area(anchor_outline(g)) * 5 - pi * ANCHOR_COUNTER_RADIUS**2 * 1.30 - d_body * 3.70 - c
        return Expect(value, 0.002 * value)
    if part == "crutch":
        value = _loop_area(crutch_outline(g)) * 3 + pi * 1.5**2 * 6.0 - d_kc * 2.0 - d_end * 1.0
        return Expect(value, 0.002 * value)
    if part == "pendulum":
        value = (_loop_area(pendulum_outline(g)) - pi * LIP_RADIUS**2 - _loop_area(crutch_slot())) * 6
        value -= pi * (SEAT_RADIUS**2 - LIP_RADIUS**2) * 5 + c
        return Expect(value, 0.002 * value)
    if part == "suspension_cap":
        value = (pi * 3.7**2 - d_end) * 1.5
        return Expect(value, 0.002 * value)
    if part == "great_wheel":
        great = gears.great_dims(p)
        bore = pi * (GREAT_BORE / 2) ** 2
        f = _fillet_allowance(great, 7.0)
        value = (_gear_area(great) - bore) * 7 - (_loop_area(ratchet_tool_outline()) - bore) * 3.5 + f
        value -= pi * (GREAT_COUNTER_RADIUS**2 - (GREAT_BORE / 2) ** 2) * 2.0 + c
        return Expect(value, 0.5 * f + 0.002 * value)
    if part == "pawl_carrier":
        gang = math.pi / 2 - g.carrier_offset
        pawl = _loop_area(pawl_loop(gang)) - (7.5**2 - 7.0**2) / 2 * _PAWL_OVERLAP
        value = pi * 7.5**2 * 4 + 2 * pawl * 4 + pi * CARRIER_BOSS_RADIUS**2 * 1.75 - d_drive * 5.75
        return Expect(value, 0.002 * value)
    if part == "mainspring":
        outer, bore, eye = profile(spring_params(), g.spring)
        value = (_loop_area(outer) - _loop_area(bore) - pi * eye.radius**2) * 6 - c
        return Expect(value, 0.002 * value + 1.0)
    if part == "spring_spacer":
        value = (pi * 3.7**2 - d_body) * 10.25
        return Expect(value, 0.002 * value)
    if part == "spring_anchor_pin":
        value = pi * 1.5**2 * 20.7
        return Expect(value, 0.002 * value)
    if part == "winding_knob":
        value = pi * 9.0**2 * 3 - d_kc * 2.0 - d_end * 1.0
        return Expect(value, 0.002 * value)
    if part == "arbor_collar":
        value = (pi * COLLAR_RADIUS**2 - d_body) * COLLAR_LENGTH
        return Expect(value, 0.002 * value)
    if part == "end_collar":
        value = (d_kr - d_end) * COLLAR_LENGTH
        return Expect(value, 0.002 * value)
    if part == "bearing":
        value = pi * (7.0**2 - 2.5**2) * 5
        return Expect(value, 0.001 * value)
    if part == "bolt":
        value = _bolt_volume(10.0)
        return Expect(value, 0.002 * value + 0.01)
    if part == "nut":
        value = _nut_volume()
        return Expect(value, 0.002 * value + 0.01)
    raise KeyError(part)


# Part-local z range of each master body [Feature order].
_PART_Z: dict[str, tuple[float, float]] = {
    "back_plate": (-6.0, 28.0),
    "front_plate": (28.0, 34.0),
    "escape_arbor": (-5.0, 33.0),
    "pallet_arbor": (-5.0, 38.25),
    "great_wheel_arbor": (-5.0, 38.25),
    "suspension_pin": (31.05, 46.75),
    "escape_wheel": (1.5, 25.0),
    "anchor": (21.0, 26.0),
    "crutch": (35.30, 44.30),
    "pendulum": (38.80, 44.80),
    "suspension_cap": (45.30, 46.80),
    "great_wheel": (1.5, 8.5),
    "pawl_carrier": (5.25, 11.0),
    "mainspring": (0.0, 6.0),
    "spring_spacer": (17.5, 27.75),
    "spring_anchor_pin": (10.25, 30.95),
    "winding_knob": (35.30, 38.30),
    "arbor_collar": (0.0, 3.0),
    "end_collar": (0.0, 3.0),
    "bearing": (0.0, 5.0),
    "bolt": (-10.0, 2.0),
    "nut": (0.0, 1.6),
}


def part_z(part: str) -> tuple[float, float]:
    """z range of the master body in part-local coordinates. Raises KeyError for an unknown part."""
    return _PART_Z[part]


def assembled_z(g: Geometry) -> dict[str, tuple[float, float]]:
    """z range of every body after its pose, in the component's frame."""
    poses = body_poses(g, state_at(g, g.params.phase))
    out: dict[str, tuple[float, float]] = {}
    for name in bodies.BODY_NAMES:
        lo, hi = part_z(bodies.part_of(name))
        zs = [poses[name].apply((0.0, 0.0, z))[2] for z in (lo, hi)]
        out[name] = (min(zs), max(zs))
    return out
