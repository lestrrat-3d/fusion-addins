"""Own copy of decad-gallery models/spurgear involute math (involute.go, spurgear.go, variant.go) and the root
clearance variant of internal/gearroot, at e11a188, and the planetarygearbox ring tool radii (gears.go ringTool).
The spurgear refactor since the gearbox port (7302e55), including the re-emits 9037e391d, ef0539a3b (#242) and
e11a188db (#249), did not change the radii, flank, closing-radius or root fillet math. The closing-radius bisection
now tests `half(mid) > limit` where it tested `>=`; the two differ
only on an exact tie. `validate_spur` and the closing-radius error text are not the gallery's, and the build
does not call them."""

from __future__ import annotations

import dataclasses
import math

from .curves import Arc, Line, Loop, Spline, rotate
from .report import fmt_num

Point = tuple[float, float]

_ORIGIN: Point = (0.0, 0.0)
_ARC_STEP = math.radians(0.5)


@dataclasses.dataclass(frozen=True)
class GearDims:
    module: float
    teeth: int
    pitch: float
    base: float
    root: float
    tip: float
    fillet: float
    backlash: float


def spur_dims(module: float, teeth: int, pressure_angle: float, backlash: float) -> GearDims:
    pitch = module * teeth / 2
    base = pitch * math.cos(pressure_angle)
    root = (module * teeth - 2.5 * module) / 2
    tip = (module * teeth + 2 * module) / 2
    inv = math.tan(pressure_angle) - pressure_angle
    fillet = 0.9 * root * (math.pi / teeth - 2 * inv) / 2
    return GearDims(module, teeth, pitch, base, root, tip, fillet, backlash)


def external_gear_dims(
    module: float,
    teeth: int,
    pressure_angle: float,
    backlash: float,
    root_clearance: float,
    root_margin: float,
    tip_margin: float,
) -> GearDims:
    """Spur dims with root-to-tip clearance: root below the pitch circle by module + clearance + margin."""
    gd = spur_dims(module, teeth, pressure_angle, backlash)
    root = gd.pitch - module - root_clearance - root_margin
    tip = gd.pitch + module - tip_margin
    # The gallery's fillet_radius expression reads the root radius after the variant overwrote it.
    inv = math.tan(pressure_angle) - pressure_angle
    fillet = 0.9 * root * (math.pi / teeth - 2 * inv) / 2
    return dataclasses.replace(gd, root=root, tip=tip, fillet=fillet)


def ring_tool_dims(
    module: float, teeth: int, pressure_angle: float, backlash: float, root_clearance: float
) -> GearDims:
    """Spur dims with the ring's radii: the gear whose teeth are the ring's tooth spaces (no root fillet)."""
    gd = spur_dims(module, teeth, pressure_angle, backlash)
    return dataclasses.replace(gd, root=gd.pitch - module, tip=gd.pitch + module + root_clearance, fillet=0.0)


def validate_spur(
    module: float,
    teeth: int,
    pressure_angle: float,
    thickness: float,
    samples: int,
    bore_diameter: float,
    backlash: float,
) -> str | None:
    """Port of spurgear validate() for the inputs the add-in uses. Returns the first error message."""
    m, n, a = module, teeth, pressure_angle
    if m <= 0:
        return f"spurgear: module {fmt_num(m)} must be positive"
    if thickness <= 0:
        return f"spurgear: thickness {fmt_num(thickness)} must be positive"
    if n < 3:
        return f"spurgear: teeth {n} must be at least 3"
    if samples < 3:
        return f"spurgear: samples {samples} must be at least 3"
    if a <= 0 or a >= math.pi / 2:
        return f"spurgear: pressure angle {fmt_num(a)} must lie in (0, pi/2)"
    if bore_diameter < 0:
        return f"spurgear: bore diameter {fmt_num(bore_diameter)} must not be negative"
    j = backlash
    if math.isnan(j) or math.isinf(j):
        return f"spurgear: backlash {fmt_num(j)} is not finite"
    if abs(j) > m / 2:
        return f"spurgear: backlash {fmt_num(j)} exceeds half the module {fmt_num(m)}"
    rp = m * n / 2
    rb = rp * math.cos(a)
    rr = (m * n - 2.5 * m) / 2
    rt = (m * n + 2 * m) / 2
    if rr <= 0:
        return f"spurgear: root radius {fmt_num(rr)} must be positive"
    if rb <= 0:
        return f"spurgear: base radius {fmt_num(rb)} must be positive"
    if rt <= rb:
        return f"spurgear: tip radius {fmt_num(rt)} must exceed base radius {fmt_num(rb)}"
    if bore_diameter >= 2 * rr:
        return f"spurgear: bore diameter {fmt_num(bore_diameter)} must be below the root diameter {fmt_num(2 * rr)}"
    rf = 0.9 * rr * (math.pi / n - 2 * (math.tan(a) - a)) / 2
    if math.isnan(rf) or math.isinf(rf):
        return f"spurgear: root fillet radius {fmt_num(rf)} is not finite"
    return None


def is_embedded(gd: GearDims) -> bool:
    """True when the involute base circle lies inside the root circle (flanks begin inside the root)."""
    return gd.base < gd.root


def mirrored_involute(base: float, r: float) -> Point:
    t = math.tan(math.acos(base / r))
    return (base * (math.cos(t) + t * math.sin(t)), -(base * (math.sin(t) - t * math.cos(t))))


def flank_beta(gd: GearDims) -> float:
    delta = gd.backlash / (2 * gd.pitch)
    px, py = mirrored_involute(gd.base, gd.pitch)
    return math.pi / (2 * gd.teeth) - delta - math.atan2(py, px)


def closing_radius(gd: GearDims) -> float:
    """Radius of the arc that closes an embedded tooth [spurgear.go closingRadius].

    Raises ValueError when adjacent teeth overlap at the root circle."""
    beta = flank_beta(gd)

    def half(r: float) -> float:
        mx, my = mirrored_involute(gd.base, r)
        c, s = math.cos(beta), math.sin(beta)
        return math.atan2(mx * s + my * c, mx * c - my * s)

    limit = math.pi / gd.teeth
    if half(gd.base) < limit:
        return gd.base
    if half(gd.root) >= limit:
        raise ValueError(f"spurgear: adjacent teeth overlap at the root circle (radius {fmt_num(gd.root)})")
    lo, hi = gd.base, gd.root
    for _ in range(200):
        mid = (lo + hi) / 2
        if half(mid) > limit:
            lo = mid
        else:
            hi = mid
    rq = (lo + hi) / 2
    return (rq + gd.root) / 2


def flank_points_at(gd: GearDims, r: float, angle: float = 0.0) -> tuple[Point, Point]:
    """Return (left, right) flank points at radius r, turned by angle."""
    m = rotate(mirrored_involute(gd.base, r), flank_beta(gd))
    return (rotate(m, angle), rotate((m[0], -m[1]), angle))


def sample_flanks(
    gd: GearDims, start: float, samples: int, angle: float = 0.0
) -> tuple[list[Point], list[Point]]:
    """Sample the left and right flanks from radius start to the tip, each base to tip, turned by angle."""
    beta = flank_beta(gd)
    left: list[Point] = []
    right: list[Point] = []
    for i in range(samples):
        r = start + (gd.tip - start) * i / (samples - 1)
        m = rotate(mirrored_involute(gd.base, r), beta)
        left.append(rotate(m, angle))
        right.append(rotate((m[0], -m[1]), angle))
    return left, right


def root_contact(pt: Point, gd: GearDims) -> Point:
    """Scale pt onto the root circle, multiplying before dividing."""
    return (pt[0] * gd.root / gd.base, pt[1] * gd.root / gd.base)


def tooth_section(gd: GearDims, samples: int) -> Loop:
    """Closed section of tooth zero: six curves for an ordinary tooth, four for an embedded one."""
    if not is_embedded(gd):
        left, right = sample_flanks(gd, gd.base, samples)
        rr = root_contact(right[0], gd)
        lr = root_contact(left[0], gd)
        return [
            Line(rr, right[0]),
            Spline(tuple(right)),
            Arc(_ORIGIN, right[-1], left[-1]),
            Spline(tuple(left)),
            Line(left[0], lr),
            Arc(_ORIGIN, rr, lr),
        ]
    rc = closing_radius(gd)
    left, right = sample_flanks(gd, rc, samples)
    return [
        Spline(tuple(right)),
        Arc(_ORIGIN, right[-1], left[-1]),
        Spline(tuple(left)),
        Arc(_ORIGIN, right[0], left[0]),
    ]


def root_contacts(gd: GearDims, samples: int) -> list[Point]:
    """The 2N root contacts of an ordinary gear, right then left per tooth."""
    if is_embedded(gd):
        raise ValueError("embedded gear has no root contacts")
    left, right = sample_flanks(gd, gd.base, samples)
    out: list[Point] = []
    for k in range(gd.teeth):
        a = 2 * math.pi * k / gd.teeth
        out.append(rotate(root_contact(right[0], gd), a))
        out.append(rotate(root_contact(left[0], gd), a))
    return out


def _arc_between(radius: float, p0: Point, p1: Point) -> list[Point]:
    """Interior points of the counterclockwise arc of the given radius about the origin from p0 to p1."""
    a0 = math.atan2(p0[1], p0[0])
    sweep = (math.atan2(p1[1], p1[0]) - a0) % (2 * math.pi)
    if sweep > math.pi:
        return []
    n = math.ceil(sweep / _ARC_STEP - 1e-9)
    return [
        (radius * math.cos(a0 + sweep * i / n), radius * math.sin(a0 + sweep * i / n)) for i in range(1, n)
    ]


def gear_outline_polygon(
    gd: GearDims, dense: int, angle: float = 0.0, center: Point = (0.0, 0.0)
) -> list[Point]:
    """Unfilleted counterclockwise outline of the whole gear, for areas and mesh tests."""
    start = max(gd.base, gd.root)
    ordinary = not is_embedded(gd)
    teeth: list[tuple[list[Point], list[Point]]] = []
    for k in range(gd.teeth):
        left, right = sample_flanks(gd, start, dense, 2 * math.pi * k / gd.teeth + angle)
        if ordinary:
            left = [root_contact(left[0], gd)] + left
            right = [root_contact(right[0], gd)] + right
        teeth.append((left, right))
    out: list[Point] = []
    for k, (left, right) in enumerate(teeth):
        out.extend(right)
        out.extend(_arc_between(gd.tip, right[-1], left[-1]))
        out.extend(reversed(left))
        next_right = teeth[(k + 1) % gd.teeth][1]
        out.extend(_arc_between(gd.root, left[0], next_right[0]))
    return [(x + center[0], y + center[1]) for x, y in out]
