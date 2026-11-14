"""Spiral spring dimensions and profile for the escapement's mainspring.

Own copy of decad-gallery models/spiralspring params.go (Derive, Validate) and profile.go (the sketch geometry) at
e11a188, and of models/escapement layout.go SpringParams. No sketch constraints: the profile is plain curves
(docs/escapement/deviations.md).
"""

from __future__ import annotations

import dataclasses
import math

from .curves import Arc, Circle, Line, Loop

Point = tuple[float, float]

THICKNESS_FLOOR = 1.5
GAP_FLOOR = 1.0
CLEARANCE_FLOOR = 0.2
MAX_TURNS = 40
TAPER_FRACTION = 0.075
TAPER_MARGIN = 0.05


@dataclasses.dataclass(frozen=True)
class SpringParams:
    outer_diameter: float
    hub_diameter: float
    thickness: float
    height: float
    min_gap: float
    arbor_diameter: float
    arbor_flat_depth: float
    bore_clearance: float
    anchor_pin_diameter: float
    anchor_clearance: float
    turns: int = 0


def spring_params() -> SpringParams:
    """The escapement's mainspring: layout.go SpringParams."""
    return SpringParams(64.0, 12.0, 1.5, 6.0, 1.0, 6.1, 0.5, 0.30, 3.0, 0.4, 0)


@dataclasses.dataclass(frozen=True)
class SpringDims:
    turns: int
    pitch: float
    gap: float
    center_offset: float
    hub_radius: float
    coil_radius: float
    first_inner_radius: float
    spoke_width: float
    bore_radius: float
    bore_flat_distance: float
    eye_center_x: float
    eye_center_y: float
    eye_radius: float
    eye_hole_diameter: float
    tail_length: float
    fillet_radius: float
    taper_offset: float
    active_length: float
    wind_strain: float


def _err(msg: str) -> ValueError:
    return ValueError("spiralspring: " + msg)


def derive(sp: SpringParams) -> SpringDims:
    """Validate sp and return its derived dimensions (spiralspring derive)."""
    fields = (
        ("OuterDiameter", sp.outer_diameter), ("HubDiameter", sp.hub_diameter), ("Thickness", sp.thickness),
        ("Height", sp.height), ("MinGap", sp.min_gap), ("ArborDiameter", sp.arbor_diameter),
        ("ArborFlatDepth", sp.arbor_flat_depth), ("BoreClearance", sp.bore_clearance),
        ("AnchorPinDiameter", sp.anchor_pin_diameter), ("AnchorClearance", sp.anchor_clearance),
    )
    for name, v in fields:
        if math.isnan(v) or math.isinf(v):
            raise _err(f"{name} must be finite")
    if sp.thickness < THICKNESS_FLOOR:
        raise _err(f"Thickness must be at least {THICKNESS_FLOOR:.1f} mm")
    if sp.min_gap < GAP_FLOOR:
        raise _err(f"MinGap must be at least {GAP_FLOOR:.1f} mm")
    if sp.height < 2 * sp.thickness:
        raise _err(f"Height must be at least 2*Thickness ({2 * sp.thickness:.2f} mm)")
    if sp.arbor_diameter <= 0:
        raise _err("ArborDiameter must be above 0")
    if sp.anchor_pin_diameter <= 0:
        raise _err("AnchorPinDiameter must be above 0")
    if sp.arbor_flat_depth < 0 or sp.arbor_flat_depth > sp.arbor_diameter / 4:
        raise _err(f"ArborFlatDepth must be between 0 and ArborDiameter/4 ({sp.arbor_diameter / 4:.3f} mm)")
    if sp.bore_clearance < CLEARANCE_FLOOR:
        raise _err(f"BoreClearance must be at least {CLEARANCE_FLOOR:.1f} mm")
    if sp.anchor_clearance < CLEARANCE_FLOOR:
        raise _err(f"AnchorClearance must be at least {CLEARANCE_FLOOR:.1f} mm")

    hub_r = sp.hub_diameter / 2
    coil_r = sp.outer_diameter / 2
    t = sp.thickness
    rb = sp.arbor_diameter / 2 + sp.bore_clearance
    f = 0.0
    if sp.arbor_flat_depth > 0:
        f = sp.arbor_diameter / 2 - sp.arbor_flat_depth + sp.bore_clearance
        if f >= rb:
            raise _err("ArborFlatDepth must exceed BoreClearance so the bore flat cuts the bore")
    if hub_r - rb < THICKNESS_FLOOR:
        raise _err(f"hub wall HubDiameter/2 - bore radius must be at least {THICKNESS_FLOOR:.1f} mm")
    if hub_r < 2.5 * t:
        raise _err(f"HubDiameter must be at least 5*Thickness ({5 * t:.2f} mm)")
    if sp.outer_diameter <= sp.hub_diameter:
        raise _err("OuterDiameter must exceed HubDiameter")
    if sp.turns < 0:
        raise _err("Turns must not be negative")
    n_max = int(math.floor((coil_r - hub_r) / (t + sp.min_gap) + 1e-9)) - 1
    if n_max < 1:
        raise _err("OuterDiameter leaves no room for one turn")
    if sp.turns > 0 and sp.turns > n_max:
        raise _err(f"Turns {sp.turns} needs a gap below MinGap; at most {n_max} turns fit")
    n = sp.turns if sp.turns > 0 else n_max
    if n > MAX_TURNS:
        raise _err(f"at most {MAX_TURNS} turns are supported, got {n}")

    pitch = (coil_r - hub_r) / (n + 1)
    g = pitch - t
    d = pitch / 2
    rho0 = hub_r + g + d
    rf = min(t / 2, g / 2)
    # The C4 fillet's contact on the spoke's underside lies at x4; e_room is the taper offset that leaves TAPER_MARGIN
    # of straight underside between the C3 and C4 fillets.
    a = 2 * t + rf
    x4 = -math.sqrt((hub_r + rf) ** 2 - a * a)
    q = TAPER_MARGIN + d - x4 + rho0 - rf
    e_room = rho0 - rf - (q * q + a * a) / (2 * q)
    if e_room <= 0:
        raise _err("HubDiameter and Gap leave no room for the root fillets")

    def rk(k: int) -> float:
        return rho0 + k * d

    hole = sp.anchor_pin_diameter + 2 * sp.anchor_clearance
    re = hole / 2 + t
    rho_prev = rk(2 * n - 2) + t
    lateral = rk(2 * n - 1) + t / 2 + d
    tail = max(2 * re, math.sqrt(max(0.0, (rho_prev + g + re) ** 2 - lateral * lateral)))
    nf = float(n)
    return SpringDims(
        turns=n,
        pitch=pitch,
        gap=g,
        center_offset=d,
        hub_radius=hub_r,
        coil_radius=coil_r,
        first_inner_radius=rho0,
        spoke_width=2 * t,
        bore_radius=rb,
        bore_flat_distance=f,
        eye_center_x=-(rk(2 * n - 1) + t / 2),
        eye_center_y=-tail,
        eye_radius=re,
        eye_hole_diameter=hole,
        tail_length=tail,
        fillet_radius=rf,
        taper_offset=min(TAPER_FRACTION * t, e_room),
        active_length=math.pi * (2 * nf * (rho0 + t / 2) + d * nf * (2 * nf - 1)),
        wind_strain=(t / 2) * (1 / (hub_r + t / 2) - 1 / (hub_r + g + t / 2)),
    )


@dataclasses.dataclass(frozen=True)
class _Points:
    c1: Point
    c2: Point
    c3: Point
    c4: Point
    pi: Point
    po: Point


def _points(sp: SpringParams, dm: SpringDims) -> _Points:
    t = sp.thickness
    r, g, d, w, rho0 = dm.hub_radius, dm.gap, dm.center_offset, dm.spoke_width, dm.first_inner_radius
    e = dm.taper_offset
    ex, ey = dm.eye_center_x, dm.eye_center_y
    yc = ey + math.sqrt(dm.eye_radius ** 2 - t * t / 4)
    return _Points(
        c1=(-r, 0.0),
        c2=(-(r + g + t), 0.0),
        c3=(d + e - math.sqrt((rho0 - e) ** 2 - w * w), -w),
        c4=(-math.sqrt(r * r - w * w), -w),
        pi=(ex + t / 2, yc),
        po=(ex - t / 2, yc),
    )


def profile(sp: SpringParams, dm: SpringDims) -> tuple[Loop, Loop, Circle]:
    """Return (outer loop, D bore loop, eye hole circle) in spring-local coordinates.

    Follows spiralspring steps "2. Sketch the profile". Every junction point is computed once and reused, so shared
    endpoints compare equal. Each Arc is counterclockwise, as CreateArc(c, a, b) is in the Go steps."""
    t = sp.thickness
    n = dm.turns
    d, rho0 = dm.center_offset, dm.first_inner_radius
    pts = _points(sp, dm)
    a: Point = (0.0, 0.0)
    b: Point = (d, 0.0)

    def rk(k: int) -> float:
        return rho0 + k * d

    e = dm.taper_offset
    inner: list[Arc] = []
    outer: list[Arc] = []
    j, o = pts.c3, pts.c2
    for k in range(2 * n):
        if k % 2 == 0:
            center = b
            jn: Point = (d + rk(k), 0.0)
            on: Point = (d + rk(k) + t, 0.0)
        else:
            center = a
            jn = (-rk(k), 0.0)
            on = (-(rk(k) + t), 0.0)
        # Half turn 0's inner edge is centred at (d + e, 0), so the strip thickens from t at J1 to t + 2e at the spoke.
        inner_center: Point = (d + e, 0.0) if k == 0 else center
        inner.append(Arc(inner_center, j, jn))
        outer.append(Arc(center, o, on))
        j, o = jn, on
    ex, ey = dm.eye_center_x, dm.eye_center_y
    hub = Arc(a, pts.c4, pts.c1)
    root_end = Line(pts.c1, pts.c2)
    tail_out = Line(o, pts.po)
    eye = Arc((ex, ey), pts.po, pts.pi)
    tail_in = Line(j, pts.pi)
    spoke = Line(pts.c3, pts.c4)
    outline: list[Arc | Line] = [hub, root_end, *outer, tail_out, eye, tail_in, *reversed(inner), spoke]

    rb, f = dm.bore_radius, dm.bore_flat_distance
    h = math.sqrt(rb * rb - f * f)
    q1: Point = (h, f)
    q2: Point = (-h, f)
    bore: list[Arc | Line] = [Arc(a, q2, q1), Line(q1, q2)]
    return outline, bore, Circle((ex, ey), dm.eye_hole_diameter / 2)


def fillet_corners(sp: SpringParams, dm: SpringDims) -> list[Point]:
    """The five concave corners the 3D fillet rounds: [C1, C3, C4, P_i, P_o]."""
    p = _points(sp, dm)
    return [p.c1, p.c3, p.c4, p.pi, p.po]


def loop_length(loop: Loop | Circle) -> float:
    """Exact perimeter of a loop of lines and arcs, or of a circle."""
    if isinstance(loop, Circle):
        return 2 * math.pi * loop.radius
    total = 0.0
    for c in loop:
        if isinstance(c, Line):
            total += math.hypot(c.end[0] - c.start[0], c.end[1] - c.start[1])
        elif isinstance(c, Arc):
            cx, cy = c.center
            r = math.hypot(c.start[0] - cx, c.start[1] - cy)
            a0 = math.atan2(c.start[1] - cy, c.start[0] - cx)
            a1 = math.atan2(c.end[1] - cy, c.end[0] - cx)
            total += r * ((a1 - a0) % (2 * math.pi))
        else:
            raise TypeError(f"unsupported curve {type(c).__name__}")
    return total
