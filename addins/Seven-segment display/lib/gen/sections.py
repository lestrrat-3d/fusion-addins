"""Sections, outlines and hole positions of the shaft, the cams and the walls.

Own copy of decad-gallery models/sevensegment shaft.go, cams.go (cam, camBore, camMarks) and frame.go (wall, addRibs,
seatTool, wallMarks). Points are (u, v) in the sketch's own coordinates: a meridian's (r, z), a plate's (u, v).
"""

from __future__ import annotations

import math

from . import constants as k
from .curves import Arc, Line, Loop, Point
from .truth import SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G

Rect = tuple[float, float, float, float]  # u0, u1, v0, v1


def polygon_loop(pts: list[Point] | tuple[Point, ...]) -> Loop:
    """A closed loop of lines through the points, the last joined to the first."""
    return [Line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def rect_loop(u0: float, u1: float, v0: float, v1: float) -> Loop:
    return polygon_loop([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])


def quarter_round(cr: float, cz: float, rad: float, a0: float, a1: float, n: int) -> list[Point]:
    """n + 1 (r, z) points of the round of radius rad about (cr, cz) from angle a0 to a1 degrees."""
    out: list[Point] = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        out.append((cr + rad * math.cos(a), cz + rad * math.sin(a)))
    return out


def shaft_meridian() -> Loop:
    """The shaft's (r, z) section, z along the shaft axis (world Y), revolved a full turn about it."""
    return polygon_loop(k.SHAFT_MERIDIAN)


def shaft_flats() -> list[tuple[str, float, float, float, float]]:
    """The three flat tools (name, x0, x1, z0, z1) in the shaft frame: boxes y +-SHAFT_FLAT_HALF, x from x0 to x1,
    over z0 to z1."""
    return [
        ("cam flat", k.SHAFT_CAM_FLAT, k.SHAFT_FLAT_REACH, k.SHAFT_CAM_FLAT_FROM, k.SHAFT_CAM_FLAT_TO),
        ("cam back flat", -k.SHAFT_FLAT_REACH, -k.SHAFT_CAM_FLAT, k.SHAFT_CAM_FLAT_FROM, k.SHAFT_CAM_FLAT_TO),
        ("stub flat", k.SHAFT_STUB_FLAT, k.SHAFT_FLAT_REACH, k.SHAFT_STUB_FLAT_FROM, k.SHAFT_STUB_FLAT_TO),
    ]


def cam_meridian_points() -> list[Point]:
    """The cam's (r, z) vertices: disc z -5.7 to 0 with 0.5 rim chamfers, the hub root round, the hub to CAM_HUB_TOP."""
    pts: list[Point] = [
        (0.0, -k.CAM_THICKNESS), (k.CAM_RADIUS - k.CAM_CHAMFER, -k.CAM_THICKNESS),
        (k.CAM_RADIUS, -k.CAM_THICKNESS + k.CAM_CHAMFER), (k.CAM_RADIUS, -k.CAM_CHAMFER),
        (k.CAM_RADIUS - k.CAM_CHAMFER, 0.0), (k.HUB_RADIUS + k.CAM_ROUND, 0.0),
    ]
    pts += quarter_round(k.HUB_RADIUS + k.CAM_ROUND, k.CAM_ROUND, k.CAM_ROUND, -90.0, -180.0, k.ROUND_CHORDS)[1:]
    pts += [(k.HUB_RADIUS, k.CAM_HUB_TOP), (0.0, k.CAM_HUB_TOP)]
    return pts


def cam_meridian() -> Loop:
    return polygon_loop(cam_meridian_points())


def double_d_loop(rb: float, fb: float) -> Loop:
    """A double-D bore: two arcs of radius rb about the origin, closed by flats at v = +fb and v = -fb."""
    w = math.sqrt(rb * rb - fb * fb)
    q1, q2, q3, q4 = (-w, fb), (w, fb), (w, -fb), (-w, -fb)
    o = (0.0, 0.0)
    return [Arc(o, q3, q2), Line(q2, q1), Arc(o, q1, q4), Line(q4, q3)]


def cam_bore_loop() -> Loop:
    return double_d_loop(k.CAM_BORE_RADIUS, k.CAM_BORE_FLAT)


def cam_mark_count(segment: int) -> tuple[int, float]:
    """The look-alike hole count and circle radius: front cams d, e, c take 1, 2, 3 at radius 18; rear
    cams g, b, f, a take 1 to 4 at radius 12."""
    return {
        SEG_D: (1, 18.0), SEG_E: (2, 18.0), SEG_C: (3, 18.0), SEG_G: (1, 12.0), SEG_B: (2, 12.0), SEG_F: (3, 12.0),
    }.get(segment, (4, 12.0))


def cam_mark_centres(segment: int) -> list[Point]:
    """The look-alike holes' centres in the cam frame, 25 degrees apart from 270."""
    n, radius = cam_mark_count(segment)
    out: list[Point] = []
    for i in range(n):
        a = math.radians(k.CAM_MARK_FIRST + k.CAM_MARK_STEP * i)
        out.append((radius * math.cos(a), radius * math.sin(a)))
    return out


def wall_plate() -> Rect:
    """The wall plate in its frame: u +-WALL_HALF, v from WALL_BOTTOM_Z - SHAFT_Z to WALL_TOP_Z - SHAFT_Z."""
    return (-k.WALL_HALF, k.WALL_HALF, k.WALL_BOTTOM_Z - k.SHAFT_Z, k.WALL_TOP_Z - k.SHAFT_Z)


def rib_depth(front: bool, ledge: bool) -> float:
    if front and ledge:
        return k.FRONT_LEDGE_DEEP
    if ledge:
        return k.REAR_LEDGE_DEEP
    return k.RIB_DEPTH


def wall_ribs(front: bool) -> list[tuple[Rect, float]]:
    """The four ribs (rectangle on the inner face, depth against the wall's normal) in the gallery's order: the ledge
    ribs at -x then +x, then the top flange ribs."""
    out: list[tuple[Rect, float]] = []
    for ledge, from_z in ((True, k.LEDGE_FROM), (False, k.FLANGE_FROM)):
        v0 = from_z - k.SHAFT_Z
        for sgn in (-1.0, 1.0):
            u0, u1 = (k.RIB_INNER, k.WALL_HALF_WIDTH) if sgn > 0 else (-k.WALL_HALF_WIDTH, -k.RIB_INNER)
            out.append(((u0, u1, v0, v0 + k.RIB_HEIGHT), rib_depth(front, ledge)))
    return out


def wall_seat_loop() -> Loop:
    """The bearing seat and lip tool's (r, d) section, revolved about the shaft axis; d from the inner face."""
    return polygon_loop(k.SEAT_MERIDIAN)


def wall_mark_centres(front: bool) -> list[Point]:
    """The look-alike holes' (u, v) in the wall's frame: the front wall one, the rear wall two, on a circle of MARK_RADIUS (13.5) about
    the shaft axis from 270 degrees, 25 degrees apart, in front-view angles (u runs along -X on the rear wall)."""
    out: list[Point] = []
    for i in range(1 if front else 2):
        a = math.radians(k.CAM_MARK_FIRST + k.CAM_MARK_STEP * i)
        x, v = k.MARK_RADIUS * math.cos(a), k.MARK_RADIUS * math.sin(a)
        out.append((x if front else -x, v))
    return out


def wall_site_indices(front: bool) -> list[tuple[int, str]]:
    """The wall's fastener sites as (index into Dimensions.sites, kind): front wall T1, T2, G1, G2, H1, H2; rear wall
    T3, T4, G3, G4. Kind T and H cut a nut pocket and a hole, G a head pocket and a hole."""
    if front:
        return [(0, "T"), (1, "T"), (4, "G"), (5, "G"), (8, "H"), (9, "H")]
    return [(2, "T"), (3, "T"), (6, "G"), (7, "G")]
