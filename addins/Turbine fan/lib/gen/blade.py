"""The blade's sections: station table, blade angle and the fit points each section's spline passes through.

Own copy of decad-gallery models/turbinefan blade.go (stationsFor, sectionPoints); the blade angle is Size.beta. A blade is built in its own frame:
local Z is its radial line, local X the direction of motion and local Y downstream. Each section lies on the plane
Z = r with the sketch origin on the stacking line.
"""

from __future__ import annotations

import dataclasses
import math

from .constants import CAMBER_AT, EDGE_THICK, REF_PITCH, SIDE_POINTS
from .size import Size

Point = tuple[float, float]


@dataclasses.dataclass(frozen=True)
class Station:
    """One blade section: radius, chord, thickness ratio, maximum camber as a fraction of the chord, and the weight of
    the ellipse in the shape (1 is an ellipse or the round root, 0 is the airfoil)."""

    r: float
    chord: float
    ratio: float
    camber: float
    ellipse: float


def stations_for(size: Size) -> tuple[Station, ...]:
    """The section table for `size` [stationsFor]. The first two stations are the round root and scale by the hub scale;
    the others are the airfoil and scale by the blade scale. Thickness ratio, camber and ellipse weight do not change."""
    j, s = size.hub_scale, size.scale
    return (
        Station(size.root_radius, 8.0 * j, 1.00, 0.000, 1.00),
        Station(size.root_radius + 1.9 * j, 8.0 * j, 1.00, 0.000, 1.00),
        Station(19.0 * s, 11.5 * s, 0.60, 0.010, 0.60),
        Station(21.5 * s, 15.5 * s, 0.38, 0.025, 0.25),
        Station(25.0 * s, 17.8 * s, 0.26, 0.035, 0.00),
        Station(30.0 * s, 16.5 * s, 0.22, 0.040, 0.00),
        Station(38.0 * s, 14.5 * s, 0.19, 0.040, 0.00),
        Station(46.0 * s, 12.5 * s, 0.18, 0.040, 0.00),
        Station(55.0 * s, 10.5 * s, 0.17, 0.035, 0.00),
        Station(size.tip_radius, 8.0 * s, 0.22, 0.030, 0.00),
    )


def camber_line(x: float, m: float) -> float:
    if x < CAMBER_AT:
        return m / (CAMBER_AT * CAMBER_AT) * (2 * CAMBER_AT * x - x * x)
    return m / ((1 - CAMBER_AT) ** 2) * ((1 - 2 * CAMBER_AT) + 2 * CAMBER_AT * x - x * x)


def pivot_at(st: Station) -> float:
    """The chord fraction of the stacking point: 0.4 for an airfoil, 0.5 for the round root."""
    return CAMBER_AT + st.ellipse * (0.5 - CAMBER_AT)


def half_thickness(x: float, st: Station) -> float:
    """Half thickness at chord fraction x: the NACA 4-digit shape blended with an ellipse, plus a linear trailing-edge
    ramp."""
    thick = st.ratio * st.chord
    n = 0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x * x + 0.2843 * x**3 - 0.1036 * x**4
    naca = (thick / 2 - 0.3 * EDGE_THICK / 2) / 0.10002 * n + EDGE_THICK / 2 * x
    ellipse = thick * math.sqrt(x * (1 - x)) + EDGE_THICK / 2 * x
    return (1 - st.ellipse) * naca + st.ellipse * ellipse


def section_points(st: Station, angle: float) -> list[Point]:
    """Fit points from the trailing edge along the suction side, round the leading edge and back along the pressure
    side (2 * SIDE_POINTS + 1 of them), in the plane local to the stacking point and turned to the blade angle."""
    pivot = pivot_at(st)
    eta_pivot = st.chord * camber_line(pivot, st.camber)
    cos_b, sin_b = math.cos(angle), math.sin(angle)

    def local(x: float, eta: float) -> Point:
        du, dv = pivot * st.chord - x * st.chord, eta - eta_pivot
        return (du * cos_b - dv * sin_b, -du * sin_b - dv * cos_b)

    def fraction(k: int) -> float:
        return (1 - math.cos(math.pi * k / SIDE_POINTS)) / 2

    pts: list[Point] = []
    for k in range(SIDE_POINTS, 0, -1):
        x = fraction(k)
        pts.append(local(x, st.chord * camber_line(x, st.camber) + half_thickness(x, st)))
    pts.append(local(0.0, 0.0))
    for k in range(1, SIDE_POINTS + 1):
        x = fraction(k)
        pts.append(local(x, st.chord * camber_line(x, st.camber) - half_thickness(x, st)))
    return pts


def fit_points(st: Station, mirror: bool, size: Size) -> list[Point]:
    """The section's fit points as drawn: always at the REF_PITCH blade angle, with every X negated unless the blade
    is the mirrored (left-hand) one [bladeSection]."""
    pts = section_points(st, size.beta(st.r, REF_PITCH))
    if not mirror:
        pts = [(-x, y) for x, y in pts]
    return pts


def pitch_turn(pitch: float, mirror: bool) -> float:
    """The turn about the blade's radial line that takes the loft drawn at REF_PITCH to `pitch` [bladeBody]."""
    turn = pitch - REF_PITCH
    return -turn if mirror else turn


def rotate(p: Point, angle: float) -> Point:
    c, s = math.cos(angle), math.sin(angle)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def to_hub(x: float, y: float, z: float, size: Size) -> tuple[float, float, float]:
    """A blade-local point in the hub's frame: local Z becomes +Y, local Y becomes +Z and local X becomes -X, from the
    origin (0, 0, size.hub_mid)."""
    return (-x, z, y + size.hub_mid)


def blade_sample_points(pitch: float, mirror: bool, size: Size) -> list[tuple[float, float, float]]:
    """Points on blade 1 in the hub's frame: every section's fit points turned to `pitch`, and the stud's two end
    circles. The bounding box of these is the expected bounds, within the spline's overshoot."""
    turn = pitch_turn(pitch, mirror)
    out: list[tuple[float, float, float]] = []
    for st in stations_for(size):
        for q in fit_points(st, mirror, size):
            x, y = rotate(q, turn)
            out.append(to_hub(x, y, st.r, size))
    for z in (size.blade_stud_start, size.blade_stud_end):
        for i in range(72):
            a = 2 * math.pi * i / 72
            out.append(to_hub(size.blade_stud_radius * math.cos(a), size.blade_stud_radius * math.sin(a), z, size))
    return out
