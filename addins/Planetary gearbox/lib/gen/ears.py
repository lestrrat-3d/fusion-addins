"""The ring's mounting ears: dimensions, outline, areas and the input rules.

Own copy of decad-gallery models/planetarygearbox ears.go (earWall, earGap, earHalfWidth, earCenterRadius, earAngle,
addRingOutline) and Params.validateEars at 791aeb2. Deviation: the outline is a list of curves at computed
coordinates, not a constrained sketch (README "Deviations from decad-gallery" lives in the converter repo).
"""

from __future__ import annotations

import math

from .curves import Arc, Circle, Line, Loop, Point
from .dims import Dims
from .fasteners import POCKET_MARGIN, head_pocket_diameter, nut_pocket_flats
from .params import Params
from .report import fmt_num as n
from .sections import bolt_angles

EAR_WALL = 3.0  # material around an ear's bore [ears.go earWall]
EAR_GAP = 1.0  # smallest gap between neighbouring ears [ears.go earGap]

_ORIGIN: Point = (0.0, 0.0)


def ear_half_width(bore: float) -> float:
    """Half the width of an ear: the bore's radius plus the wall."""
    return bore / 2 + EAR_WALL


def ear_center_radius(ring_outer: float, bore: float) -> float:
    """Distance from the axis to the center of an ear's bore."""
    return ring_outer + ear_half_width(bore)


def ear_angle(i: int, count: int) -> float:
    """Angle of ear i of count: evenly spread, the first on +Y."""
    return math.pi / 2 + 2 * math.pi * i / count


def ear_bore_centers(p: Params, d: Dims) -> list[Point]:
    """Centers of the ear bores, in ear order."""
    radius = ear_center_radius(d.ring_outer, p.ear_bore_diameter)
    return [
        (radius * math.cos(ear_angle(i, p.ear_count)), radius * math.sin(ear_angle(i, p.ear_count)))
        for i in range(p.ear_count)
    ]


def _at(angle: float, along: float, side: float) -> Point:
    """The point `along` an ear's axis (at `angle`) and `side` to its counterclockwise side."""
    sin, cos = math.sin(angle), math.cos(angle)
    return (along * cos - side * sin, along * sin + side * cos)


def ring_outline(p: Params, d: Dims) -> Loop | Circle:
    """The ring blank's outer boundary: a circle without ears, else one closed loop.

    The loop runs, for each ear, a straight edge out to the half circle round the bore, the half circle, a straight
    edge back to the ring's outer circle, and then an arc of the outer circle to the next ear [ears.go addRingOutline].
    """
    if p.ear_count == 0:
        return Circle(_ORIGIN, d.ring_outer)
    half = ear_half_width(p.ear_bore_diameter)
    radius = ear_center_radius(d.ring_outer, p.ear_bore_diameter)
    root = math.sqrt(d.ring_outer * d.ring_outer - half * half)
    ears: list[tuple[Point, Point, Point, Point, Point]] = []
    for i in range(p.ear_count):
        angle = ear_angle(i, p.ear_count)
        # center, root_down, root_up, tip_down, tip_up
        ears.append((
            _at(angle, radius, 0.0),
            _at(angle, root, -half),
            _at(angle, root, half),
            _at(angle, radius, -half),
            _at(angle, radius, half),
        ))
    loop: list[Line | Arc] = []
    for i, (center, root_down, root_up, tip_down, tip_up) in enumerate(ears):
        next_root_down = ears[(i + 1) % len(ears)][1]
        loop.append(Line(root_down, tip_down))
        loop.append(Arc(center, tip_down, tip_up))
        loop.append(Line(tip_up, root_up))
        loop.append(Arc(_ORIGIN, root_up, next_root_down))
    return loop


def ring_blank_area(p: Params, d: Dims) -> float:
    """Area of the ring blank's outline less the ear bores (mm^2), before the bolt holes and the tooth spaces."""
    area = math.pi * d.ring_outer**2
    if p.ear_count == 0:
        return area
    half = ear_half_width(p.ear_bore_diameter)
    radius = ear_center_radius(d.ring_outer, p.ear_bore_diameter)
    wall = math.sqrt(d.ring_outer**2 - half * half)
    # One ear beyond the outer circle: its strip out to the bore's center, less the strip's part inside the circle,
    # plus the half circle round the bore.
    inside = half * wall + d.ring_outer**2 * math.asin(half / d.ring_outer)
    extra = 2 * half * radius - inside + math.pi * half * half / 2
    bores = math.pi * (p.ear_bore_diameter / 2) ** 2
    return area + p.ear_count * (extra - bores)


def loop_xmax(loop: Loop) -> float:
    """Largest x on a loop of lines and arcs: its vertices, and each arc's rightmost point when the arc reaches it."""
    best = -math.inf
    for c in loop:
        if isinstance(c, Line):
            best = max(best, c.start[0], c.end[0])
        elif isinstance(c, Arc):
            best = max(best, c.start[0], c.end[0])
            r = math.hypot(c.start[0] - c.center[0], c.start[1] - c.center[1])
            a0 = math.atan2(c.start[1] - c.center[1], c.start[0] - c.center[0])
            a1 = math.atan2(c.end[1] - c.center[1], c.end[0] - c.center[0])
            if (-a0) % (2 * math.pi) <= (a1 - a0) % (2 * math.pi):
                best = max(best, c.center[0] + r)
        else:
            raise ValueError("unsupported curve in the ring outline")
    return best


def ring_xmax(p: Params, d: Dims) -> float:
    """Largest x of the ring (mm): the outer radius, or the ears' reach."""
    outline = ring_outline(p, d)
    if isinstance(outline, Circle):
        return outline.radius
    return loop_xmax(outline)


def validate_ears(p: Params, d: Dims) -> str | None:
    """Message of the first failing ear rule, or None [params.go validateEars]. Takes only the numbers it needs."""
    if p.ear_count == 0:
        return None
    half = ear_half_width(p.ear_bore_diameter)
    radius = ear_center_radius(d.ring_outer, p.ear_bore_diameter)
    if p.ear_count > 1:
        # Neighbouring ears are closest at their half circles, whose centers are a chord apart.
        chord = 2 * radius * math.sin(math.pi / p.ear_count)
        if chord < 2 * half + EAR_GAP:
            return (
                f"neighbouring ear bores are {n(chord)} apart; the ears need {n(2 * half + EAR_GAP)} "
                f"for at least {n(EAR_GAP)} between them"
            )
    # A bolt site is clear of an ear when its pockets stay beyond the ear's side edge, or the ear lies on the far
    # side of the axis.
    reach = max(nut_pocket_flats(), head_pocket_diameter()) / 2 + POCKET_MARGIN
    for i in range(p.ear_count):
        for b in bolt_angles():
            delta = ear_angle(i, p.ear_count) - b
            if math.cos(delta) > 0 and d.bolt_circle * abs(math.sin(delta)) < half + reach:
                return f"ear {i + 1} lies over a bolt site: turn the ears off the bolt angles by using another ear count"
    return None
