"""Outlines of the flag sliders: the three types (a, g, d; b, c; e, f), the blade extension, the rooted tongue and the
groove pin. Own copy of decad-gallery models/sevensegment sliders.go.

Heights are model z in mm, at the unlit build pose; a lit slider is moved up by TRAVEL as a whole.
"""

from __future__ import annotations

import dataclasses
import math

from . import flags_common as fc
from .constants import FLAG_PIN_RADIUS, OFF_RADIUS, PIN_RADIUS, SHAFT_Z, STEM_THICKNESS, WALL_CHAMFER
from .curves import Arc, Curve, Line, Loop, Point
from .truth import SEG_E, SEG_F, SEG_A, SEG_D, SEG_G, station

SLIDER_PIN_Z = SHAFT_Z + OFF_RADIUS  # z of the groove pin's axis at the unlit pose: on the groove's off radius
SLIDER_STEM_FROM = SLIDER_PIN_Z - 5.25  # z where the stem starts
SLIDER_PIN_R = PIN_RADIUS
SLIDER_PIN_ROUND = 0.5
SLIDER_PIN_CHAMFER = 0.3
PIN_AXIS_Z = fc.ROTOR_AXIS_Z - 2.625  # the rotor pin's axis at the unlit build pose of a, g and d
SLIDER_HEAD_TOP = PIN_AXIS_Z - 12.075  # head or arm top at the build pose (unlit)
TONGUE_ROOT_DIP = 0.03  # how far the tongue's root rounds bottom out inside the head
TONGUE_HULL_R = FLAG_PIN_RADIUS + 0.1  # radius of the hull round about the pin axis
FLAG_PIN_LENGTH = 5.4
FLAG_PIN_TIP_CHAMFER = 0.2
BLADE_RIDGE_Z = SLIDER_HEAD_TOP + 16.125  # top of the blade's gable
BLADE_SHOULDER_Z = SLIDER_HEAD_TOP + 15.225
BLADE_EXT_OVERLAP = 0.1
BLADE_EXT_LENGTH = 1.8  # the blade extension beyond the arm, before its overlap
STEM_CHAMFER = WALL_CHAMFER  # the 0.5 "Surface edge finishing" chamfer of the stem's two large faces
TONGUE_END_GAP = 1.95  # the end cutter's lower line lies this far below the head top
PIN_STATION_AGD = 2.25  # the rotor pin's distance from the stem along s, a, g, d
PIN_STATION_BC = 22.5  # along x, b and c
PIN_STATION_EF = 27.0  # along x, e and f
TONGUE_WIDTH = 2.1  # the tongue strip's width along s
TONGUE_TOP_GAP = 1.8  # the tongue's top edge lies this far below the pin axis
# Root r 1.05 and feet 1.2, not 1.2 and 1.35: the gallery's kernel refuses the stem's 0.5 chamfer next to a root round of
# about 1.15 or more (sliders.go). The numbers are the gallery's, so they stay.
TONGUE_ROOT_R = 1.05  # the tongue's root rounds
TONGUE_FOOT = 1.2  # the feet where they meet the head
SLIDER_HALF_WIDE = 5.25  # half the stem's width along the rotor axis of a, g and d, and along x of b to f
STEM_HALF_AGD = SLIDER_HALF_WIDE  # the a, g, d stem's extent along x (extruded x -5.25 to 5.25)
BF_THICK = STEM_THICKNESS  # the b-f profile's extent along y
AGD_THICK = 2 * SLIDER_HALF_WIDE


def is_agd(s: int) -> bool:
    return s in (SEG_A, SEG_G, SEG_D)


def is_ef(s: int) -> bool:
    return s in (SEG_E, SEG_F)


def agd_polygon() -> tuple[list[Point], dict[int, float]]:
    """The a, g, d main profile in (w, z), w relative to the slider's station, and its rounds."""
    zh, sh, rz = SLIDER_HEAD_TOP, BLADE_SHOULDER_Z, BLADE_RIDGE_Z
    h = STEM_THICKNESS / 2
    v = [(-h, SLIDER_STEM_FROM), (h, SLIDER_STEM_FROM), (h, zh - 2.475), (3.6, zh - 1.575), (3.6, zh),
         (-10.05, zh), (-10.05, sh), (-10.875, rz), (-11.7, sh), (-11.7, zh), (-12.9, zh),
         (-12.9, zh - 3.0), (-h, zh - 3.0)]
    return v, {5: 0.9, 9: 0.9, 12: 1.5}


def agd_loop() -> Loop:
    v, radii = agd_polygon()
    return fc.rounded_loop(v, radii)


def blade_x(s: int) -> tuple[float, float]:
    """The b-f blade's x range (bL, bR): the blade is 1.65 thick."""
    return (-14.7, -13.05) if is_ef(s) else (13.05, 14.7)


def bf_polygon(s: int) -> tuple[list[Point], dict[int, float]]:
    """The b-f main profile (stem, arm, head and blade) in (x, z), and its rounds. The arm points to +x for b and c and
    to -x for e and f."""
    zh, za = SLIDER_HEAD_TOP, SLIDER_HEAD_TOP - 3.75
    sh, rz = BLADE_SHOULDER_Z, BLADE_RIDGE_Z
    bl, br = blade_x(s)
    mid = (bl + br) / 2
    h = SLIDER_HALF_WIDE
    if not is_ef(s):
        v = [(-h, SLIDER_STEM_FROM), (h, SLIDER_STEM_FROM), (h, za), (26.85, za), (26.85, zh), (br, zh), (br, sh),
             (mid, rz), (bl, sh), (bl, zh), (-h, zh)]
        return v, {2: 1.875, 5: 0.9, 9: 0.9}
    v = [(-h, SLIDER_STEM_FROM), (h, SLIDER_STEM_FROM), (h, zh), (br, zh), (br, sh), (mid, rz), (bl, sh),
         (bl, zh), (-29.25, zh), (-29.25, za), (-h, za)]
    return v, {3: 0.9, 7: 0.9, 10: 1.875}


def bf_loop(s: int) -> Loop:
    v, radii = bf_polygon(s)
    return fc.rounded_loop(v, radii)


# The stem's 0.5 chamfers (gallery sliders.go finishSlider: edgefinish.ChamferRuns on the stem's two large faces, every
# run of their outer loops of LongEdgeRun or more). Edges are straight or circular, in model mm.
LONG_EDGE_RUN = 20.0  # gallery edgefinish.LongEdgeRun: the arc length from which a boundary run is long
_TANGENT_COS = 1 - 5e-7  # gallery edgefinish tangentCos: below this two edge directions at a joint are a corner


@dataclasses.dataclass(frozen=True)
class StemEdge:
    """One edge of a stem face's outer loop: a line from a to b, or the arc about `center` between a and b."""

    a: tuple[float, float, float]
    b: tuple[float, float, float]
    center: tuple[float, float, float] | None = None  # None: a line

    @property
    def length(self) -> float:
        if self.center is None:
            return math.dist(self.a, self.b)
        r = math.dist(self.a, self.center)
        v0 = (self.a[0] - self.center[0], self.a[1] - self.center[1], self.a[2] - self.center[2])
        v1 = (self.b[0] - self.center[0], self.b[1] - self.center[1], self.b[2] - self.center[2])
        cos = sum(p * q for p, q in zip(v0, v1)) / (r * r)
        return r * math.acos(max(-1.0, min(1.0, cos)))


def _tangent(c: Curve, at: Point) -> Point:
    """The unit tangent of curve c at its end point `at`, as an undirected direction."""
    if isinstance(c, Line):
        dx, dy = c.end[0] - c.start[0], c.end[1] - c.start[1]
    else:
        dx, dy = -(at[1] - c.center[1]), at[0] - c.center[0]
    n = math.hypot(dx, dy)
    return (dx / n, dy / n)


def _curve_length(c: Curve) -> float:
    if isinstance(c, Line):
        return math.dist(c.start, c.end)
    r = math.dist(c.center, c.start)
    a0 = math.atan2(c.start[1] - c.center[1], c.start[0] - c.center[0])
    a1 = math.atan2(c.end[1] - c.center[1], c.end[0] - c.center[0])
    return r * ((a1 - a0) % (2 * math.pi))


def loop_runs(loop: Loop) -> list[list[Curve]]:
    """[edgefinish.Runs] The loop's curves, in loop order, split at its corners into tangent-continuous runs."""
    n = len(loop)
    breaks = []
    for i, c in enumerate(loop):
        nxt = loop[(i + 1) % n]
        joint = next(p for p in (c.start, c.end) if p in (nxt.start, nxt.end))
        d1, d2 = _tangent(c, joint), _tangent(nxt, joint)
        breaks.append(abs(d1[0] * d2[0] + d1[1] * d2[1]) < _TANGENT_COS)  # a corner after curve i
    if not any(breaks):
        return [list(loop)]
    start = (breaks.index(True) + 1) % n  # the first curve after a corner
    runs: list[list[Curve]] = []
    cur: list[Curve] = []
    for k in range(n):
        i = (start + k) % n
        cur.append(loop[i])
        if breaks[i]:
            runs.append(cur)
            cur = []
    return runs


def _stem_edge(c: Curve, face_y: float) -> StemEdge:
    """A profile curve in (x, z) on the plane y = face_y as a model edge."""
    a, b = (c.start[0], face_y, c.start[1]), (c.end[0], face_y, c.end[1])
    if isinstance(c, Line):
        return StemEdge(a, b)
    return StemEdge(a, b, (c.center[0], face_y, c.center[1]))


def stem_chamfer_runs(s: int) -> list[list[StemEdge]]:
    """The runs of the stem's two large faces that take the 0.5 chamfer, on the slider's profile prism at station(s).

    b to f: the prism's two faces at y = station -+ 1/2 stem are the profile; a run is long from LONG_EDGE_RUN. A run that
    reaches above the head top is left out: the blade extension (+y face) and the tongue (-y face) are joined there.
    a, g, d: the faces are the stem's sides; their only long runs are the stem's vertical edges at x = +-5.25."""
    yi, h = station(s), STEM_THICKNESS / 2
    out: list[list[StemEdge]] = []
    if is_agd(s):
        # The profile's edges at w = -h and w = +h run from the foot to the first corner: zh - 3.0 and zh - 2.475.
        for w, top in ((-h, SLIDER_HEAD_TOP - 3.0), (h, SLIDER_HEAD_TOP - 2.475)):
            for x in (-SLIDER_HALF_WIDE, SLIDER_HALF_WIDE):
                out.append([StemEdge((x, yi + w, SLIDER_STEM_FROM), (x, yi + w, top))])
        return out
    loop = bf_loop(s)
    for face_y in (yi - h, yi + h):
        for run in loop_runs(loop):
            if sum(_curve_length(c) for c in run) < LONG_EDGE_RUN:
                continue
            if any(max(c.start[1], c.end[1]) > SLIDER_HEAD_TOP + 1e-6 for c in run):
                continue
            out.append([_stem_edge(c, face_y) for c in run])
    return out


def blade_extension(s: int) -> list[Point]:
    """The b-f blade extension beyond the arm, in (x, z)."""
    bl, br = blade_x(s)
    return [(bl, SLIDER_HEAD_TOP), (br, SLIDER_HEAD_TOP), (br, BLADE_SHOULDER_Z), ((bl + br) / 2, BLADE_RIDGE_Z),
            (bl, BLADE_SHOULDER_Z)]


def tangent_point(p: Point, c: Point, rad: float, side: float) -> Point:
    """The point where a line from p touches the circle (c, rad); side +1 or -1 picks the tangent."""
    dx, dy = p[0] - c[0], p[1] - c[1]
    d = math.hypot(dx, dy)
    a = math.atan2(dy, dx) + side * math.acos(rad / d)
    return (c[0] + rad * math.cos(a), c[1] + rad * math.sin(a))


def tongue_outline(sl: float, sr: float, sc: float, zp: float) -> Loop:
    """The tongue's hull in (s, z): feet at the head, 8-chord root rounds of r TONGUE_ROOT_R (1.05) that bottom out inside
    the head, the strip sides up to the pin, and two hull lines tangent to the circle TONGUE_HULL_R about the pin axis."""
    zt = zp - TONGUE_TOP_GAP
    zh = SLIDER_HEAD_TOP
    rr, ft = TONGUE_ROOT_R, TONGUE_FOOT
    zc = zh + rr - TONGUE_ROOT_DIP
    right: list[Point] = [(sr + ft, zh - ft), (sr + ft, zc - rr)]
    right += fc.quarter_round(sr + rr, zc, rr, 270, 180, 8)
    right.append((sr, zt))
    left = fc.quarter_round(sl - rr, zc, rr, 0, -90, 8)
    left = [(sl, zt)] + left + [(sl - ft, zc - rr), (sl - ft, zh - ft)]
    c = (sc, zp)
    tr1 = tangent_point((sr, zt), c, TONGUE_HULL_R, 1)
    tr2 = tangent_point((sr, zt), c, TONGUE_HULL_R, -1)
    t_r = tr2 if tr2[0] > tr1[0] else tr1
    tl1 = tangent_point((sl, zt), c, TONGUE_HULL_R, 1)
    tl2 = tangent_point((sl, zt), c, TONGUE_HULL_R, -1)
    t_l = tl2 if tl2[0] < tl1[0] else tl1
    out: Loop = []
    for a, b in zip(right, right[1:]):
        out.append(Line(a, b))
    out.append(Line(right[-1], t_r))
    out.append(Arc(c, t_r, t_l))  # counterclockwise over the top of the pin axis
    out.append(Line(t_l, left[0]))
    for a, b in zip(left, left[1:]):
        out.append(Line(a, b))
    out.append(Line(left[-1], right[0]))
    return out


def tongue_cutter(ue: float, zp: float) -> list[Point]:
    """The tongue's end cutter in (u, z)."""
    ztop = zp + 2.25
    rr, ft = TONGUE_ROOT_R, TONGUE_FOOT
    zc_e = SLIDER_HEAD_TOP + rr - TONGUE_ROOT_DIP
    far = ue + FLAG_PIN_LENGTH + 0.4
    cv: list[Point] = [(ue, ztop)]
    cv += fc.quarter_round(ue + rr, zc_e, rr, 180, 270, 8)
    cv += [(ue + ft, zc_e - rr), (ue + ft, SLIDER_HEAD_TOP - TONGUE_END_GAP),
           (far, SLIDER_HEAD_TOP - TONGUE_END_GAP), (far, ztop)]
    return cv


def flag_pin_meridian() -> list[Point]:
    """The rotor pin's (r, z) section: diameter 1.5, 5.5 long from the plane u = ue - 0.1, tip chamfer 0.2."""
    r, length, c = FLAG_PIN_RADIUS, FLAG_PIN_LENGTH + 0.1, FLAG_PIN_TIP_CHAMFER
    return [(0.0, 0.0), (r, 0.0), (r, length - c), (r - c, length), (0.0, length)]


def groove_pin_meridian() -> list[Point]:
    """The groove pin's (r, s) section, s along +Y from the stem's +Y face: it starts 0.5 inside the stem."""
    rd, top = SLIDER_PIN_ROUND, SLIDER_PIN_R + SLIDER_PIN_ROUND
    v: list[Point] = [(0.0, -rd), (top, -rd)]  # (r, s)
    for s, r in fc.quarter_round(rd, top, rd, 180, 270, 8):
        v.append((r, s))
    v += [(SLIDER_PIN_R, fc.PIN_LENGTH - SLIDER_PIN_CHAMFER), (SLIDER_PIN_R - SLIDER_PIN_CHAMFER, fc.PIN_LENGTH),
          (0.0, fc.PIN_LENGTH)]
    return v


@dataclasses.dataclass(frozen=True)
class Tongue:
    """The arguments of the gallery's rootedTongue."""

    u_is_x: bool
    ua: float  # the print face
    ue: float  # the pin face
    sl: float
    sr: float
    sc: float
    zp: float

    @property
    def hull_length(self) -> float:
        return self.ue + (FLAG_PIN_LENGTH + 0.2) - self.ua

    @property
    def cutter_length(self) -> float:
        return self.sr - self.sl + 4.5

    @property
    def cutter_at(self) -> float:
        return self.sl - 2.25

    @property
    def pin_at(self) -> float:
        return self.ue - 0.1


def tongue_for(s: int) -> Tongue:
    yi = station(s)
    if is_agd(s):
        return Tongue(True, -SLIDER_HALF_WIDE, -2.85, yi + PIN_STATION_AGD - TONGUE_WIDTH, yi + PIN_STATION_AGD,
                      yi + PIN_STATION_AGD, PIN_AXIS_Z)
    zp = PIN_AXIS_Z + fc.raise_(s)
    if is_ef(s):
        sl = -PIN_STATION_EF
        return Tongue(False, yi - STEM_THICKNESS / 2, yi - 0.3, sl, sl + TONGUE_WIDTH, sl, zp)
    return Tongue(False, yi - STEM_THICKNESS / 2, yi - 0.3, PIN_STATION_BC, PIN_STATION_BC + TONGUE_WIDTH, PIN_STATION_BC, zp)
