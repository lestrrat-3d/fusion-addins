"""Tangent rounds of loop corners.

Own copy of the effect of the gallery's `sketch.CreateFillet` as used in models/escapement at e11a188: the corner
between two lines or arcs is replaced by an arc of radius r tangent to both. The pieces are trimmed back to the
touch points, and the round shares those points with them, so a loop stays closed.

# Deviation: the gallery's sketch fillets are tangent arcs computed here and drawn as plain sketch arcs
# (docs/escapement/deviations.md).
"""

from __future__ import annotations

import dataclasses
import math
import typing

from .curves import Arc, Curve, Line, Loop, Point, Spline, endpoints

_EPS = 1e-9


@dataclasses.dataclass(frozen=True)
class Round:
    corner: Point  # the sharp corner the round replaces
    centre: Point
    radius: float

    def probe(self) -> Point:
        """Point halfway from the corner to the round's arc, on the segment corner -> centre."""
        dx, dy = self.centre[0] - self.corner[0], self.centre[1] - self.corner[1]
        f = 0.5 * (1 - self.radius / math.hypot(dx, dy))
        return (self.corner[0] + f * dx, self.corner[1] + f * dy)


def _sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def _add(a: Point, b: Point) -> Point:
    return (a[0] + b[0], a[1] + b[1])


def _mul(a: Point, k: float) -> Point:
    return (a[0] * k, a[1] * k)


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _unit(a: Point) -> Point:
    n = math.hypot(a[0], a[1])
    return (a[0] / n, a[1] / n)


def _tangent(piece: typing.Union[Line, Arc], v: Point) -> Point:
    """Unit tangent of piece at its end v, pointing into the piece."""
    if isinstance(piece, Line):
        other = piece.end if piece.start == v else piece.start
        return _unit(_sub(other, v))
    u = _unit(_sub(v, piece.center))
    t = (-u[1], u[0])
    return t if piece.start == v else _mul(t, -1.0)


# An offset is ("line", point, direction) or ("circle", centre, radius).
def _offset(piece: typing.Union[Line, Arc], v: Point, t: Point, n: Point, r: float):
    if isinstance(piece, Line):
        return ("line", _add(v, _mul(n, r)), t)
    big = math.hypot(piece.start[0] - piece.center[0], piece.start[1] - piece.center[1])
    rho = big - r if _dot(n, _sub(piece.center, v)) > 0 else big + r
    if rho <= _EPS:
        raise ValueError(f"round: radius {r} exceeds arc radius {big}")
    return ("circle", piece.center, rho)


def _intersect(a, b) -> list[Point]:
    if a[0] == "circle" and b[0] == "line":
        a, b = b, a
    if a[0] == "line" and b[0] == "line":
        d = _cross(a[2], b[2])
        if abs(d) < _EPS:
            return []
        s = _cross(_sub(b[1], a[1]), b[2]) / d
        return [_add(a[1], _mul(a[2], s))]
    if a[0] == "line":
        _, p, t = a
        _, c, rho = b
        w = _sub(p, c)
        h = _dot(t, w)
        disc = h * h - (_dot(w, w) - rho * rho)
        if disc < 0:
            return []
        root = math.sqrt(disc)
        return [_add(p, _mul(t, -h + root)), _add(p, _mul(t, -h - root))]
    _, c1, r1 = a
    _, c2, r2 = b
    d = math.hypot(c2[0] - c1[0], c2[1] - c1[1])
    if d < _EPS:
        return []
    x = (d * d + r1 * r1 - r2 * r2) / (2 * d)
    h2 = r1 * r1 - x * x
    if h2 < 0:
        return []
    h = math.sqrt(h2)
    ex = _unit(_sub(c2, c1))
    ey = (-ex[1], ex[0])
    mid = _add(c1, _mul(ex, x))
    return [_add(mid, _mul(ey, h)), _add(mid, _mul(ey, -h))]


def _touch(piece: typing.Union[Line, Arc], p: Point, r: float) -> Point:
    """The point where the round about p meets piece; ValueError when it lies off the piece."""
    fit = f"round: radius {r} does not fit"
    if isinstance(piece, Line):
        d = _sub(piece.end, piece.start)
        s = _dot(_sub(p, piece.start), d) / _dot(d, d)
        if s < -_EPS or s > 1 + _EPS:
            raise ValueError(fit)
        return _add(piece.start, _mul(d, s))
    c = piece.center
    big = math.hypot(piece.start[0] - c[0], piece.start[1] - c[1])
    q = _add(c, _mul(_unit(_sub(p, c)), big))
    a0 = math.atan2(piece.start[1] - c[1], piece.start[0] - c[0])
    sweep = (math.atan2(piece.end[1] - c[1], piece.end[0] - c[0]) - a0) % (2 * math.pi)
    off = (math.atan2(q[1] - c[1], q[0] - c[0]) - a0) % (2 * math.pi)
    if off > sweep + _EPS and off < 2 * math.pi - _EPS:
        raise ValueError(fit)
    return q


def _replace(piece: typing.Union[Line, Arc], v: Point, q: Point) -> typing.Union[Line, Arc]:
    if isinstance(piece, Line):
        return Line(q, piece.end) if piece.start == v else Line(piece.start, q)
    return Arc(piece.center, q, piece.end) if piece.start == v else Arc(piece.center, piece.start, q)


def _round_corner(a, b, r: float):
    """Return (a trimmed, round, b trimmed, Round record)."""
    shared = set(endpoints(a)) & set(endpoints(b))
    if len(shared) != 1:
        raise ValueError(f"round: pieces share {len(shared)} ends, expected 1")
    (v,) = shared
    ta, tb = _tangent(a, v), _tangent(b, v)
    if abs(_cross(ta, tb)) < _EPS:
        raise ValueError("round: corner is straight")
    k = _dot(ta, tb)
    na = _unit(_sub(tb, _mul(ta, k)))
    nb = _unit(_sub(ta, _mul(tb, k)))
    cands = _intersect(_offset(a, v, ta, na, r), _offset(b, v, tb, nb, r))
    if not cands:
        raise ValueError("round: no centre")
    p = min(cands, key=lambda c: math.hypot(c[0] - v[0], c[1] - v[1]))
    qa, qb = _touch(a, p, r), _touch(b, p, r)
    rnd = Arc(p, qa, qb) if _cross(_sub(qa, p), _sub(qb, p)) > 0 else Arc(p, qb, qa)
    return _replace(a, v, qa), rnd, _replace(b, v, qb), Round(v, p, r)


def round_corner(a: typing.Union[Line, Arc], b: typing.Union[Line, Arc], r: float):
    """Round the one corner a and b share with radius r.

    Returns (a trimmed at the corner, the round, b trimmed at the corner)."""
    ta, rnd, tb, _ = _round_corner(a, b, r)
    return ta, rnd, tb


def _round_all(loop: Loop, rounds: typing.Mapping[int, float]) -> tuple[list[Curve], list[Round]]:
    for c in loop:
        if isinstance(c, Spline):
            raise ValueError("round: a loop with a spline cannot be rounded")
    pieces: list = list(loop)
    n = len(pieces)
    made: dict[int, Arc] = {}
    records: list[Round] = []
    for i in sorted(rounds):
        j = (i + 1) % n
        pieces[i], made[i], pieces[j], rec = _round_corner(pieces[i], pieces[j], rounds[i])
        records.append(rec)
    out: list[Curve] = []
    for i, c in enumerate(pieces):
        out.append(c)
        if i in made:
            out.append(made[i])
    return out, records


def round_loop(loop: Loop, rounds: typing.Mapping[int, float]) -> list[Curve]:
    """Loop with the corner between loop[i] and loop[(i + 1) % n] rounded with radius rounds[i], for each key i."""
    return _round_all(loop, rounds)[0]


def loop_rounds(loop: Loop, rounds: typing.Mapping[int, float]) -> list[Round]:
    """The Round of each key of rounds, in ascending key order."""
    return _round_all(loop, rounds)[1]
