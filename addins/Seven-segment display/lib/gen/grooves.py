"""A cam's groove outline and its inscription, as closed loops of lines and arcs in cam-local coordinates.

Own copy of decad-gallery models/sevensegment cams.go (grooveTool, channel, letterLoops). The gallery draws the groove
as a fully constrained sketch; here each wall is one closed loop at computed coordinates
(docs/sevensegment/deviations.md).

The groove profile is the outer wall (dwell arcs, ramp arcs and lines, the entry channel) with the inner wall as its
hole. Every arc is counterclockwise from its start to its end, and consecutive curves share their end points exactly.
"""

from __future__ import annotations

import math

from . import constants as k
from .curves import Arc, Line, Loop
from .params import Dimensions
from .ramps import Pt, Ramp, polar, ramp_geometry, wrap360
from .truth import SEGMENT_NAMES, SEGMENTS


def _sub(a: Pt, b: Pt) -> Pt:
    return (a[0] - b[0], a[1] - b[1])


def _add_scaled(a: Pt, n: Pt, s: float) -> Pt:
    return (a[0] + n[0] * s, a[1] + n[1] * s)


def _short_arc(center: Pt, a: Pt, b: Pt) -> Arc:
    """The arc about center between a and b, whichever way round is the short one (at most 180 degrees)."""
    u, v = _sub(a, center), _sub(b, center)
    if u[0] * v[1] - u[1] * v[0] >= 0:
        return Arc(center, a, b)
    return Arc(center, b, a)


def sorted_ramps(ramps: tuple[Ramp, ...]) -> list[Ramp]:
    return sorted(ramps, key=lambda r: wrap360(r.start))


def channel_inside(a: float, b: float, half: float) -> bool:
    """True when the entry channel, centred at ENTRY_ANGLE, lies inside the dwell from angle a to b (degrees)."""
    lo = wrap360(k.ENTRY_ANGLE - half - a) + a
    hi = lo + 2 * half
    end = a + wrap360(b - a)
    return hi <= end


def channel_half_angle() -> float:
    """Half the angle the entry channel's mouth spans on the ON dwell's outer wall, degrees."""
    half = k.GROOVE_WIDTH / 2
    return math.degrees(math.asin(half / (k.ON_RADIUS + half)))


def _channel(frm: Pt, to: Pt, rd: float) -> list[Arc | Line]:
    """The outer wall's ON dwell arc frm -> to split by the entry channel: an arc to the channel's near side, the side
    line out to the cap line, the cap line, the far side line back and the arc on to `to`."""
    if abs(rd - (k.ON_RADIUS + k.GROOVE_WIDTH / 2)) > 1e-9:
        raise ValueError(f"entry channel dwell at radius {rd:g}, want the ON wall")
    u = polar(1.0, k.ENTRY_ANGLE)
    n = (-u[1], u[0])
    hw = k.GROOVE_WIDTH / 2
    along = math.sqrt(rd * rd - hw * hw)

    def at(l: float, lat: float) -> Pt:
        return (u[0] * l + n[0] * lat, u[1] * l + n[1] * lat)

    pl, pr = at(along, -hw), at(along, hw)
    cl, cr = at(k.CHANNEL_CAP, -hw), at(k.CHANNEL_CAP, hw)
    o: Pt = (0.0, 0.0)
    return [Arc(o, frm, pl), Line(pl, cl), Line(cl, cr), Line(cr, pr), Arc(o, pr, to)]


def _outward(c: Pt, t: Pt) -> Pt:
    """The unit vector from the arc centre c through its tangent point t, flipped to point away from the origin."""
    n = (( t[0] - c[0]) / k.RAMP_ROUND, (t[1] - c[1]) / k.RAMP_ROUND)
    if n[0] * t[0] + n[1] * t[1] < 0:
        n = (-n[0], -n[1])
    return n


def groove_loops(segment: int, dm: Dimensions) -> tuple[Loop, Loop]:
    """(outer wall loop, inner wall loop) of segment's groove. The outer loop includes the entry channel."""
    ramps = sorted_ramps(dm.ramps[segment])
    half = k.GROOVE_WIDTH / 2
    chan = channel_half_angle()
    out: list[Loop] = []
    for sigma in (1.0, -1.0):  # outer wall, inner wall
        curves: list[Arc | Line] = []
        walls: list[tuple[Pt, Pt, Pt, Pt]] = []
        for ra in ramps:
            g = ramp_geometry(ra)
            before, after = (k.OFF_RADIUS, k.ON_RADIUS) if ra.rising else (k.ON_RADIUS, k.OFF_RADIUS)
            n1, n2 = _outward(g.c1, g.t1), _outward(g.c2, g.t2)
            j1 = polar(before + sigma * half, ra.start)
            t1 = _add_scaled(g.t1, n1, sigma * half)
            t2 = _add_scaled(g.t2, n2, sigma * half)
            j2 = polar(after + sigma * half, ra.end)
            walls.append((j1, t1, t2, j2))
        for i, ra in enumerate(ramps):
            g = ramp_geometry(ra)
            j1, t1, t2, j2 = walls[i]
            nx = (i + 1) % len(ramps)
            curves += [_short_arc(g.c1, j1, t1), Line(t1, t2), _short_arc(g.c2, t2, j2)]
            after = k.ON_RADIUS if ra.rising else k.OFF_RADIUS
            rd = after + sigma * half
            frm, to = j2, walls[nx][0]
            if sigma > 0 and channel_inside(ra.end, ramps[nx].start, chan):
                curves += _channel(frm, to, rd)
            else:
                curves.append(Arc((0.0, 0.0), frm, to))
        out.append(curves)
    return out[0], out[1]


# Cam inscription: the segment's letter, engraved into the back face, drawn in the seven-segment style from
# rectangular strokes.
LETTER_SEGMENTS = {
    0: "abcefg",  # A
    1: "cdefg",  # b
    2: "adef",  # C
    3: "bcdeg",  # d
    4: "adefg",  # E
    5: "aefg",  # F
    6: "acdef",  # G
}

# A segment's cells on the 3 by 5 lattice: first and last column, first and last row (inclusive).
_COVER = {
    "a": (0, 2, 4, 4), "g": (0, 2, 2, 2), "d": (0, 2, 0, 0),
    "f": (0, 0, 2, 4), "e": (0, 0, 0, 2), "b": (2, 2, 2, 4), "c": (2, 2, 0, 2),
}


def letter_loops(segment: int) -> list[list[Pt]]:
    """The closed rectilinear loops of segment's letter in sketch coordinates about the letter's centre (u across,
    v up): the outer outline, then any counter. The letter is the union of its strokes on a lattice of
    x in {0, stroke, width - stroke, width} and y in {0, stroke, mid - stroke/2, mid + stroke/2, height - stroke,
    height}."""
    w, h, s = k.INSCRIPTION_WIDTH, k.INSCRIPTION_HEIGHT, k.INSCRIPTION_STROKE
    xs = (0.0, s, w - s, w)
    ys = (0.0, s, h / 2 - s / 2, h / 2 + s / 2, h - s, h)
    filled = [[False] * 5 for _ in range(3)]
    for c in LETTER_SEGMENTS[segment]:
        c0, c1, r0, r1 = _COVER[c]
        for i in range(c0, c1 + 1):
            for j in range(r0, r1 + 1):
                filled[i][j] = True

    def inside(i: int, j: int) -> bool:
        return 0 <= i < 3 and 0 <= j < 5 and filled[i][j]

    # Directed boundary edges with the material on the left, between lattice points (i, j).
    nxt: dict[tuple[int, int], tuple[int, int]] = {}
    for i in range(3):
        for j in range(5):
            if not filled[i][j]:
                continue
            if not inside(i, j - 1):
                nxt[(i, j)] = (i + 1, j)
            if not inside(i + 1, j):
                nxt[(i + 1, j)] = (i + 1, j + 1)
            if not inside(i, j + 1):
                nxt[(i + 1, j + 1)] = (i, j + 1)
            if not inside(i - 1, j):
                nxt[(i, j + 1)] = (i, j)
    loops: list[list[Pt]] = []
    for start in sorted(nxt):
        if start not in nxt:
            continue
        path: list[tuple[int, int]] = []
        p = start
        while p in nxt:
            q = nxt.pop(p)
            path.append(p)
            p = q
            if p == start:
                break
        corners: list[Pt] = []
        for n, p in enumerate(path):
            a, b = path[n - 1], path[(n + 1) % len(path)]
            if (a[0] == p[0] and b[0] == p[0]) or (a[1] == p[1] and b[1] == p[1]):
                continue
            corners.append((xs[p[0]] - w / 2, ys[p[1]] - h / 2))
        loops.append(corners)
    # The outer outline first: the loop with the largest area.
    def area(c: list[Pt]) -> float:
        return abs(sum(c[i][0] * c[(i + 1) % len(c)][1] - c[(i + 1) % len(c)][0] * c[i][1] for i in range(len(c))) / 2)

    return sorted(loops, key=area, reverse=True)


def letter_curves(segment: int) -> list[Loop]:
    """The letter's loops as lines in cam-local coordinates on the back face. The gallery's sketch frame looks at the
    face from outside (U along local -X, V along +Y), so the letter reads correctly from the back: local x = -u and
    local y = v + INSCRIPTION_RADIUS."""
    out: list[Loop] = []
    for loop in letter_loops(segment):
        pts = [(-u, v + k.INSCRIPTION_RADIUS) for u, v in loop]
        out.append([Line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))])
    return out


def letter_name(segment: int) -> str:
    """The letter's display segments, a to g."""
    return LETTER_SEGMENTS[segment]


assert len(LETTER_SEGMENTS) == len(SEGMENTS) and set("".join(LETTER_SEGMENTS.values())) <= set(SEGMENT_NAMES)
