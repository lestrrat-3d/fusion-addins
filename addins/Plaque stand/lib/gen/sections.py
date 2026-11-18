"""The 2D sections the plaque stand's sketches draw, as pure loops (millimeters).

Own copy of decad-gallery models/plaquestand outline.go (buildOutline) and sketches.go (railSketch). The bracket's
profile is a loop in (y, z); the add-in draws it on the XY plane as (x, y) = (y, z) and turns the extrusion onto the X
axis afterwards (commands/plaquestand/parts.py). Each curve is placed at computed coordinates with no constraints
(docs/plaquestand/deviations.md).
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    BACK_THICKNESS,
    BASE_THICKNESS,
    CHANNEL_MOUTH_ROUND,
    CORNER_RADIUS,
    JOINT_FIT,
    LIP_THICKNESS,
    RAIL_HEIGHT,
    RAIL_ROUND,
    RAIL_WIDTH,
    ROOT_RADIUS,
)
from .curves import Arc, Line, Loop, Point
from .params import Dimensions


@dataclasses.dataclass(frozen=True)
class Segment:
    """One line or arc of the profile, in traversal order. An arc has a centre and a radius; convex is set for an arc
    along which the outline turns counter-clockwise."""

    start: Point
    end: Point
    center: Point = (0.0, 0.0)
    radius: float = 0.0
    convex: bool = False

    def is_arc(self) -> bool:
        return self.radius > 0

    def sweep(self) -> float:
        """An arc's angle in radians: 2 asin(min(1, chord / (2 radius))); 0 for a line."""
        if not self.is_arc():
            return 0.0
        chord = math.hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])
        return 2 * math.asin(min(1.0, chord / (2 * self.radius)))


def outline_segments(dm: Dimensions) -> list[Segment]:
    """The 26 segments of a bracket's profile, in the order of instructions.md "Outline" [buildOutline]."""
    tb, lt, bt, rr, rc = BASE_THICKNESS, LIP_THICKNESS, BACK_THICKNESS, ROOT_RADIUS, CORNER_RADIUS
    D, R = dm.depth, dm.slot_radius
    rm = CHANNEL_MOUTH_ROUND
    rf = RAIL_ROUND + JOINT_FIT
    ycb, ycf, zf = dm.channel_back, dm.channel_front, dm.channel_floor
    seat, n, u = dm.seat, dm.normal, dm.axis

    def at(a: float, b: float) -> Point:
        """P(a, b) = C + a n + b u."""
        return (seat[0] + a * n[0] + b * u[0], seat[1] + a * n[1] + b * u[1])

    def line(a: Point, b: Point) -> Segment:
        return Segment(a, b)

    def arc(a: Point, b: Point, c: Point, r: float, convex: bool) -> Segment:
        return Segment(a, b, c, r, convex)

    back_foot = (dm.q3y + rr * dm.kb, tb)
    back_tan = (dm.q3y + rr * dm.kb * u[0], tb + rr * dm.kb * u[1])
    lip_tan = (dm.q7y + rr * dm.kf * u[0], tb + rr * dm.kf * u[1])
    lip_foot = (dm.q7y - rr * dm.kf, tb)
    hb, hl = dm.back_wall, dm.lip_wall
    return [
        line((rc, 0), (D - rc, 0)),
        arc((D - rc, 0), (D, rc), (D - rc, rc), rc, True),
        line((D, rc), (D, tb - rc)),
        arc((D, tb - rc), (D - rc, tb), (D - rc, tb - rc), rc, True),
        line((D - rc, tb), (ycb + rm, tb)),
        arc((ycb + rm, tb), (ycb, tb - rm), (ycb + rm, tb - rm), rm, True),
        line((ycb, tb - rm), (ycb, zf + rf)),
        arc((ycb, zf + rf), (ycb - rf, zf), (ycb - rf, zf + rf), rf, False),
        line((ycb - rf, zf), (ycf + rf, zf)),
        arc((ycf + rf, zf), (ycf, zf + rf), (ycf + rf, zf + rf), rf, False),
        line((ycf, zf + rf), (ycf, tb - rm)),
        arc((ycf, tb - rm), (ycf - rm, tb), (ycf - rm, tb - rm), rm, True),
        line((ycf - rm, tb), back_foot),
        arc(back_foot, back_tan, (dm.q3y + rr * dm.kb, tb + rr), rr, False),
        line(back_tan, at(R + bt, hb)),
        arc(at(R + bt, hb), at(R, hb), at(R + bt / 2, hb), bt / 2, True),
        line(at(R, hb), at(R, 0)),
        arc(at(R, 0), at(-R, 0), seat, R, False),
        line(at(-R, 0), at(-R, hl)),
        arc(at(-R, hl), at(-R - lt, hl), at(-R - lt / 2, hl), lt / 2, True),
        line(at(-R - lt, hl), lip_tan),
        arc(lip_tan, lip_foot, (dm.q7y - rr * dm.kf, tb + rr), rr, False),
        line(lip_foot, (rc, tb)),
        arc((rc, tb), (0, tb - rc), (rc, tb - rc), rc, True),
        line((0, tb - rc), (0, rc)),
        arc((0, rc), (rc, 0), (rc, rc), rc, True),
    ]


def area(segments: list[Segment]) -> float:
    """The outline's area in mm^2 [Outline.Area]: the shoelace sum over every chord, plus (r^2/2)(phi - sin phi) for each
    convex arc and minus it for each concave arc."""
    total = 0.0
    for s in segments:
        total += (s.start[0] * s.end[1] - s.end[0] * s.start[1]) / 2
        if not s.is_arc():
            continue
        phi = s.sweep()
        seg = s.radius * s.radius / 2 * (phi - math.sin(phi))
        total += seg if s.convex else -seg
    return total


def length(segments: list[Segment]) -> float:
    """The outline's length in mm [Outline.Length]."""
    total = 0.0
    for s in segments:
        total += s.radius * s.sweep() if s.is_arc() else math.hypot(s.end[0] - s.start[0], s.end[1] - s.start[1])
    return total


def outline_loop(dm: Dimensions) -> Loop:
    """The profile as drawable curves: every arc counter-clockwise (a concave arc swaps its ends), and each curve's
    end equal to the next curve's start in the traversal, so the points are shared exactly."""
    segs = outline_segments(dm)
    starts = [s.start for s in segs]
    n = len(segs)
    loop: list[Line | Arc] = []
    for i, s in enumerate(segs):
        end = starts[(i + 1) % n]
        if not s.is_arc():
            loop.append(Line(s.start, end))
        elif s.convex:
            loop.append(Arc(s.center, s.start, end))
        else:
            loop.append(Arc(s.center, end, s.start))
    return loop


def rail_loop() -> Loop:
    """The rail's section, a rounded rectangle RAIL_WIDTH x RAIL_HEIGHT with corner rounds RAIL_ROUND, about the origin:
    the bottom line, then counter-clockwise an arc, the right line, an arc, the top line, an arc, the left line and an
    arc [railSketch]. x is across the rail (world Y) and y is its height (world Z)."""
    hw, hh, r = RAIL_WIDTH / 2, RAIL_HEIGHT / 2, RAIL_ROUND
    return [
        Line((-hw + r, -hh), (hw - r, -hh)),
        Arc((hw - r, -hh + r), (hw - r, -hh), (hw, -hh + r)),
        Line((hw, -hh + r), (hw, hh - r)),
        Arc((hw - r, hh - r), (hw, hh - r), (hw - r, hh)),
        Line((hw - r, hh), (-hw + r, hh)),
        Arc((-hw + r, hh - r), (-hw + r, hh), (-hw, hh - r)),
        Line((-hw, hh - r), (-hw, -hh + r)),
        Arc((-hw + r, -hh + r), (-hw, -hh + r), (-hw + r, -hh)),
    ]
