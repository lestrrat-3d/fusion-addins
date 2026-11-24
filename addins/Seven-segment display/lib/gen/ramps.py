"""Cam ramps, the groove radius and the lift. Own copy of decad-gallery models/sevensegment params.go.

Angles are cam-local degrees, measured from +U toward +V of the cam frame. A follower at the top reads
psi = 90 + theta, and digit k rests at psi_k = 90 + 36 k.
"""

from __future__ import annotations

import dataclasses
import math

from .constants import OFF_RADIUS, ON_RADIUS, RAMP_END, RAMP_ROUND, RAMP_START
from .truth import lit

Pt = tuple[float, float]


@dataclasses.dataclass(frozen=True)
class Ramp:
    """One cam ramp: the step `from_digit` to (from_digit + 1) mod 10 changes the segment."""

    from_digit: int
    rising: bool
    start: float  # cam-local degrees, psi_from + RAMP_START, not wrapped
    end: float


@dataclasses.dataclass(frozen=True)
class RampGeometry:
    """A ramp's centreline: two arcs of RAMP_ROUND about c1 and c2 and the line t1 to t2, cam-local."""

    c1: Pt
    c2: Pt
    t1: Pt
    t2: Pt
    line_length: float


def polar(radius: float, deg: float) -> Pt:
    a = math.radians(deg)
    return (radius * math.cos(a), radius * math.sin(a))


def wrap360(a: float) -> float:
    return a - 360.0 * math.floor(a / 360.0)


def psi_of(k: int) -> float:
    """The cam-local angle of digit k: 90 + 36 k."""
    return 90.0 + 36.0 * k


def ramps_for(segment: int) -> tuple[Ramp, ...]:
    """Segment's ramps in increasing start, from the truth table."""
    out: list[Ramp] = []
    for k in range(10):
        a, b = lit(k, segment), lit((k + 1) % 10, segment)
        if a == b:
            continue
        start = psi_of(k) + RAMP_START
        out.append(Ramp(k, b, start, start + RAMP_END - RAMP_START))
    return tuple(out)


def _rising_geometry(a: float, b: float) -> tuple[RampGeometry, float, float]:
    """The rising ramp from polar angle a to b: arc 1 about OFF_RADIUS + RAMP_ROUND at a, arc 2 about
    ON_RADIUS - RAMP_ROUND at b, joined by their internal common tangent. Returns the geometry, the tangent normal's
    angle phi1 and arc 1's sweep."""
    c1 = polar(OFF_RADIUS + RAMP_ROUND, a)
    c2 = polar(ON_RADIUS - RAMP_ROUND, b)
    dv = (c2[0] - c1[0], c2[1] - c1[1])
    base = math.degrees(math.atan2(dv[1], dv[0]))
    off = math.degrees(math.acos(2 * RAMP_ROUND / math.hypot(*dv)))
    for phi1 in (base + off, base - off):
        n = polar(1.0, phi1)
        d = (n[1], -n[0])
        if dv[0] * d[0] + dv[1] * d[1] <= 0:
            continue
        sweep1 = wrap360((a + 180) - phi1)
        sweep2 = wrap360(b - (phi1 + 180))
        if sweep1 <= 0 or sweep1 > 180 or sweep2 <= 0 or sweep2 > 180:
            continue
        t1 = (c1[0] + RAMP_ROUND * n[0], c1[1] + RAMP_ROUND * n[1])
        t2 = (c2[0] - RAMP_ROUND * n[0], c2[1] - RAMP_ROUND * n[1])
        return RampGeometry(c1, c2, t1, t2, math.hypot(t2[0] - t1[0], t2[1] - t1[1])), phi1, sweep1
    raise ValueError(f"sevensegment: no ramp from {a} to {b} degrees")


def _reflect(v: Pt, m: float) -> Pt:
    """v mirrored about the line through the origin at polar angle m (degrees)."""
    s, c = math.sin(math.radians(2 * m)), math.cos(math.radians(2 * m))
    return (v[0] * c + v[1] * s, v[0] * s - v[1] * c)


def ramp_geometry(r: Ramp) -> RampGeometry:
    """The ramp's centreline arcs and line, cam-local. A falling ramp is the rising one mirrored about its window's
    mid-angle."""
    g, _, _ = _rising_geometry(r.start, r.end)
    if r.rising:
        return g
    m = (r.start + r.end) / 2
    return RampGeometry(_reflect(g.c2, m), _reflect(g.c1, m), _reflect(g.t2, m), _reflect(g.t1, m), g.line_length)


class _RisingPath:
    """A rising ramp's centreline as a function of a parameter t in [0, 3]: arc 1, the line, arc 2."""

    def __init__(self, a: float, b: float) -> None:
        self.g, self.phi1, self.sweep1 = _rising_geometry(a, b)
        self.a0 = a + 180
        self.sweep2 = wrap360(b - (self.phi1 + 180))
        self.start = a

    def at(self, t: float) -> tuple[Pt, Pt]:
        """The centreline point and its unit tangent."""
        g = self.g
        if t < 1:
            al = math.radians(self.a0 - self.sweep1 * t)
            s, c = math.sin(al), math.cos(al)
            return (g.c1[0] + RAMP_ROUND * c, g.c1[1] + RAMP_ROUND * s), (s, -c)
        if t < 2:
            d = (g.t2[0] - g.t1[0], g.t2[1] - g.t1[1])
            n = math.hypot(*d)
            return (g.t1[0] + d[0] * (t - 1), g.t1[1] + d[1] * (t - 1)), (d[0] / n, d[1] / n)
        al = math.radians(self.phi1 + 180 + self.sweep2 * (t - 2))
        s, c = math.sin(al), math.cos(al)
        return (g.c2[0] + RAMP_ROUND * c, g.c2[1] + RAMP_ROUND * s), (-s, c)

    def find(self, psi: float) -> float:
        """The parameter whose point lies at polar angle psi (degrees from the start)."""
        lo, hi = 0.0, 3.0
        for _ in range(60):
            mid = (lo + hi) / 2
            pt, _ = self.at(mid)
            if wrap360(math.degrees(math.atan2(pt[1], pt[0])) - self.start + 180) - 180 < psi:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def radius(self, psi: float) -> tuple[float, float]:
        """The centreline radius and the pressure angle (degrees) at polar angle psi."""
        pt, tan = self.at(self.find(psi - self.start))
        r = math.hypot(*pt)
        er = (pt[0] / r, pt[1] / r)
        radial = abs(tan[0] * er[0] + tan[1] * er[1])
        circ = abs(tan[0] * (-er[1]) + tan[1] * er[0])
        return r, math.degrees(math.atan2(radial, circ))


def groove(segment: int, psi: float) -> tuple[float, float]:
    """The groove's centreline radius and pressure angle (degrees) of segment at cam-local angle psi."""
    u = wrap360(psi - 90)
    shifted = u + 6.5
    k = int(math.floor(shifted / 36)) % 10
    rel = shifted - 36 * math.floor(shifted / 36)
    on = lit(k, segment)
    level = ON_RADIUS if on else OFF_RADIUS
    if rel < RAMP_START + 6.5:
        return level, 0.0
    nxt = lit((k + 1) % 10, segment)
    if nxt == on:
        return level, 0.0
    a = 90 + 36 * k + RAMP_START
    b = 90 + 36 * k + RAMP_END
    local = a + rel - (RAMP_START + 6.5)
    path = _RisingPath(a, b)
    if nxt:
        return path.radius(local)
    return path.radius(a + b - local)


def groove_radius(segment: int, psi: float) -> float:
    return groove(segment, psi)[0]


def pressure_angle(segment: int, psi: float) -> float:
    return groove(segment, psi)[1]


def lift(segment: int, theta: float) -> float:
    """The slider's lift at camshaft angle theta (degrees): groove_radius(segment, 90 + theta) - OFF_RADIUS."""
    return groove_radius(segment, 90 + theta) - OFF_RADIUS
