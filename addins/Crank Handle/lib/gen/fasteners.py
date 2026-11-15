"""M2 bolt and nut geometry, fastener sites and the tools cut for them.

Own copy of decad-gallery models/m2bolt (m2bolt.go), models/m2nut (m2nut.go) and internal/m2fastener (m2fastener.go).
Thread is not modeled, as in the gallery.

A `Site` is a bolt in the part's local frame: its head's top face is at `head`, the bolt runs along `dir`, and the
hexagons of its socket and nut have a corner along `corner`. A tool or fastener for a site is built at the origin with
its axis on +Z and moved by `site_axes` ("tool frame"): x = corner, y = dir x corner, z = dir.
"""

from __future__ import annotations

import dataclasses
import math

from .curves import Line, Loop, Point

Vec3 = tuple[float, float, float]

# m2bolt.go
SHANK_DIAMETER = 2.0
HEAD_DIAMETER = 3.8
HEAD_HEIGHT = 2.0
SOCKET_ACROSS_FLATS = 1.5
SOCKET_DEPTH = 1.0
HEAD_CHAMFER_WIDTH = 0.2
HEAD_CHAMFER_ANGLE = 30.0  # degrees
UNDERHEAD_RADIUS = 0.1
TIP_CHAMFER = 0.25
DRILL_POINT_ANGLE = 118.0  # degrees
DRILL_POINT_BASE_RADIUS = 0.7
PILOT_DEPTH = 0.1
SOCKET_CUTTER_RISE = 0.5
STANDARD_LENGTHS = (6.0, 10.0, 16.0, 18.0, 20.0, 25.0)
# m2nut.go
NUT_BORE_DIAMETER = 2.0
NUT_ACROSS_FLATS = 4.0
NUT_THICKNESS = 1.6
NUT_BEARING_DIAMETER = 3.48
NUT_CHAMFER_ANGLE = 30.0  # degrees
NUT_CHAMFER_MARGIN = 0.2
NUT_CHAMFER_REACH = 0.3
# m2fastener.go
HEAD_CLEARANCE = 0.3  # radial gap between a bolt head and its pocket, and between the shank and its hole
NUT_CLEARANCE = 0.2  # gap between a nut and its cavity: radial beyond the nut's corners, axial at each face
HOLE_RADIUS = SHANK_DIAMETER / 2 + HEAD_CLEARANCE
HEAD_POCKET_RADIUS = HEAD_DIAMETER / 2 + HEAD_CLEARANCE
HEAD_POCKET_DEPTH = HEAD_HEIGHT
NUT_CAVITY_RADIUS = NUT_ACROSS_FLATS / math.sqrt(3) + NUT_CLEARANCE
NUT_CAVITY_HEIGHT = NUT_THICKNESS + 2 * NUT_CLEARANCE
STOCK = 1.0  # a tool's reach past a face it opens
ROUND_RADIUS = 0.55
ROUND_CHORDS = 8
_UNIT_TOLERANCE = 1e-9


def _len(a: Vec3) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


@dataclasses.dataclass(frozen=True)
class Site:
    """One bolt: head position, direction, hexagon corner direction, nominal length, nut cavity's near face."""

    head: Vec3
    dir: Vec3
    corner: Vec3
    length: float
    cavity: float

    def validate(self) -> str:
        """The first problem as a message, or an empty string."""
        if abs(_len(self.dir) - 1) > _UNIT_TOLERANCE or abs(_len(self.corner) - 1) > _UNIT_TOLERANCE:
            return "fastener site: Dir and Corner must be unit vectors"
        if abs(_dot(self.dir, self.corner)) > _UNIT_TOLERANCE:
            return "fastener site: Corner must be perpendicular to Dir"
        if self.length not in STANDARD_LENGTHS:
            return f"fastener site: length {self.length:g} is not a standard M2 length"
        if not self.cavity > HEAD_POCKET_DEPTH:
            return f"fastener site: Cavity {self.cavity:g} must lie beyond the head pocket ({HEAD_POCKET_DEPTH:g})"
        return ""

    def at(self, t: float) -> Vec3:
        return (self.head[0] + self.dir[0] * t, self.head[1] + self.dir[1] * t, self.head[2] + self.dir[2] * t)

    def tip(self) -> float:
        """The bolt tip's distance from the head's top face."""
        return HEAD_POCKET_DEPTH + self.length

    def cavity_far(self) -> float:
        return self.cavity + NUT_CAVITY_HEIGHT

    def axes(self, t: float = 0.0) -> tuple[Vec3, Vec3, Vec3, Vec3]:
        """(origin, x, y, z) of the tool frame at distance t along the bolt: x = corner, z = dir, y = dir x corner."""
        return (self.at(t), self.corner, cross(self.dir, self.corner), self.dir)

    def bolt_axes(self) -> tuple[Vec3, Vec3, Vec3, Vec3]:
        """Frame of the bolt as built (head up along +Z, origin at the head's underside): z points back along -dir."""
        back: Vec3 = (-self.dir[0], -self.dir[1], -self.dir[2])
        return (self.at(HEAD_POCKET_DEPTH), self.corner, cross(back, self.corner), back)

    def nut_axes(self) -> tuple[Vec3, Vec3, Vec3, Vec3]:
        """Frame of the nut as built (z 0 to its thickness): NUT_CLEARANCE inside the cavity's near face."""
        return self.axes(self.cavity + NUT_CLEARANCE)


def hexagon_loop(flats: float, center: Point = (0.0, 0.0)) -> Loop:
    """Regular hexagon of the given across-flats size as six lines; corner 0 sits on +X."""
    return hexagon_by_radius(flats / math.sqrt(3), center)


def hexagon_by_radius(radius: float, center: Point = (0.0, 0.0)) -> Loop:
    """Regular hexagon with its corners on the circle of the given radius; corner 0 sits on +X."""
    corners: list[Point] = []
    for k in range(6):
        a = k * math.pi / 3
        corners.append((center[0] + radius * math.cos(a), center[1] + radius * math.sin(a)))
    return [Line(corners[k], corners[(k + 1) % 6]) for k in range(6)]


def bolt_section(length: float) -> Loop:
    """Half section of the bolt as (radius, height) lines; origin = centre of the head's underside, head along +v."""
    sh, hh = SHANK_DIAMETER / 2, HEAD_DIAMETER / 2
    socket_floor = HEAD_HEIGHT - SOCKET_DEPTH - PILOT_DEPTH
    pts: list[Point] = [
        (0.0, -length),
        (sh - TIP_CHAMFER, -length),
        (sh, -length + TIP_CHAMFER),
        (sh, 0.0),
        (hh, 0.0),
        (hh, HEAD_HEIGHT - HEAD_CHAMFER_WIDTH * math.tan(math.radians(HEAD_CHAMFER_ANGLE))),
        (hh - HEAD_CHAMFER_WIDTH, HEAD_HEIGHT),
        (DRILL_POINT_BASE_RADIUS, HEAD_HEIGHT),
        (DRILL_POINT_BASE_RADIUS, socket_floor),
        (0.0, socket_floor - DRILL_POINT_BASE_RADIUS / math.tan(math.radians(DRILL_POINT_ANGLE / 2))),
    ]
    return [Line(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]


def nut_across_corners() -> float:
    return NUT_ACROSS_FLATS / math.cos(math.pi / 6)


def nut_chamfer_section(upper: bool) -> Loop:
    """Triangle (radius, height) revolved to cut one chamfer of the nut."""
    slope = math.tan(math.radians(NUT_CHAMFER_ANGLE))
    outer = nut_across_corners() / 2 + NUT_CHAMFER_MARGIN
    br = NUT_BEARING_DIAMETER / 2
    sign, face = (-1.0, NUT_THICKNESS) if upper else (1.0, 0.0)
    start: Point = (br - NUT_CHAMFER_REACH / slope, face - sign * NUT_CHAMFER_REACH)
    foot: Point = (outer, start[1])
    corner: Point = (outer, face + sign * (outer - br) * slope)
    return [Line(start, foot), Line(foot, corner), Line(corner, start)]


def _quarter_round(t: float, r: float, start: float) -> list[tuple[float, float]]:
    """Chord points (t, r) of one ROUND_RADIUS quarter round [m2fastener.go quarterRound]."""
    out: list[tuple[float, float]] = []
    for i in range(ROUND_CHORDS + 1):
        f = i / ROUND_CHORDS
        a = math.pi / 2 * (1 - f) if start == 0 else math.pi - math.pi / 2 * f
        out.append((t + ROUND_RADIUS * math.cos(a), r + ROUND_RADIUS * math.sin(a)))
    return out


def rounded_hole_meridian(site: Site) -> list[tuple[float, float]]:
    """(t, r) vertices of the pin bolt's rounded hole tool [m2fastener.go RoundedHoleTool]."""
    end = site.tip() + STOCK
    pts = [(-STOCK, 0.0), (-STOCK, HOLE_RADIUS)]
    pts += _quarter_round(end - ROUND_RADIUS, HOLE_RADIUS - ROUND_RADIUS, 0)
    pts.append((end, 0.0))
    return pts


def rounded_cavity_meridian(site: Site) -> list[tuple[float, float]]:
    """(t, r) vertices of the pin bolt's rounded nut cavity tool [m2fastener.go RoundedCavityTool]."""
    near, far = site.cavity, site.cavity_far()
    pts = [(near, 0.0)]
    pts += _quarter_round(near + ROUND_RADIUS, NUT_CAVITY_RADIUS - ROUND_RADIUS, math.pi)
    pts += _quarter_round(far - ROUND_RADIUS, NUT_CAVITY_RADIUS - ROUND_RADIUS, 0)
    pts.append((far, 0.0))
    return pts


def meridian_loop(pts: list[tuple[float, float]]) -> Loop:
    """Closed loop of lines in (radius, t) sketch coordinates from (t, r) vertices."""
    q: list[Point] = [(r, t) for t, r in pts]
    return [Line(q[k], q[(k + 1) % len(q)]) for k in range(len(q))]
