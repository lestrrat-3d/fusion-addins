"""Point probes and interaction points: points whose containment in a built body is known from the design.

Own copy of the gearbox add-in's probe structure, with the escapement's probe tables of the design doc. Part probes
are in part-local coordinates (origin on the part's axis, z in model z). Interaction points are in the component frame.
"""

from __future__ import annotations

import dataclasses
import math

from . import bodies as b
from .fasteners import PILLARS
from .gears import great_dims, pinion_dims
from .involute import gear_outline_polygon
from .layout import Geometry, angle_of
from .motion import State
from .params import Vec3
from .pose import body_poses

INSIDE = "inside"
OUTSIDE = "outside"

_DEG = math.pi / 180
_WHEEL_R = 33.0  # the escape wheel's disc radius


@dataclasses.dataclass(frozen=True)
class Probe:
    label: str
    point: Vec3  # part-local coordinates
    expect: str  # "inside" | "outside"


@dataclasses.dataclass(frozen=True)
class MeshPoint:
    label: str  # starts with its event: mesh, escapement, coupling or fit
    target: str  # name of the body that must not contain the point
    point: Vec3  # component-frame coordinates


def _polar(r: float, a: float, z: float = 0.0) -> Vec3:
    return (r * math.cos(a), r * math.sin(a), z)


def _in(label: str, x: float, y: float, z: float) -> Probe:
    return Probe(label, (x, y, z), INSIDE)


def _out(label: str, x: float, y: float, z: float) -> Probe:
    return Probe(label, (x, y, z), OUTSIDE)


def part_probes(g: Geometry) -> dict[str, list[Probe]]:
    """Probes per part key of bodies.PARTS, in part-local coordinates."""
    sy = g.axis_s[1]
    qx, qy = g.spring_anchor
    pawl_g = 90 * _DEG - g.carrier_offset
    dm = g.spring
    r1 = dm.first_inner_radius + dm.center_offset
    t, gap = 1.5, dm.gap
    ce_a = angle_of(g.ce)
    cx_a = angle_of(g.cx)
    probes: dict[str, list[Probe]] = {}

    probes["back_plate"] = [
        _in("spine", 0, 30, -3), _in("hub ring -", -8.5, 0, -3), _in("hub ring +", 8.5, 0, -3),
        _in("rim -74", -47, 74, -3), _in("rim +74", 47, 74, -3), _in("rim -88", -47, -88, -3),
        _in("rim +88", 47, -88, -3), _in("pillar -74", -50, 74, 14), _in("pillar +74", 50, 74, 14),
        _in("seat floor", 6, 0, -5.5),
        _out("window -40", -40, 0, -3), _out("window +40", 40, 0, -3), _out("window -20", -20, 0, -3),
        _out("window +20", 20, 0, -3), _out("window -g", -30, g.axis_g[1], -3), _out("window +g", 30, g.axis_g[1], -3),
        _out("lip", 0, 0, -3), _out("mount -", -40, 90, -3), _out("mount +", 40, 90, -3), _out("seat", 6, 0, -2),
        _out("cavity -74", -50, 74, 25), _out("cavity +74", 50, 74, 25), _out("cavity +88", 50, -88, 25),
        _out("hole", -50, 74, 22.5),
    ]
    probes["front_plate"] = [
        _in("spine", 0, 30, 31), _in("socket wall", 0, 75, 31), _in("above seat", 6, 0, 33.5),
        _in("below head pocket", -48.3, 74, 31),
        _out("window -", -40, 0, 31), _out("window +", 40, 0, 31), _out("seat", 6, 0, 30),
        _out("suspension socket", 0, sy, 32.5), _out("anchor socket", qx, qy, 29),
        _out("head pocket -", -50, 74, 33), _out("head pocket +", 50, 74, 33),
    ]
    probes["escape_arbor"] = [
        _in("axis", 0, 0, 10), _in("under bearing", 2.25, 0, -2.5), _in("collar", 3.5, 0, 26),
        _out("flat", 2.25, 0, 10),
    ]
    probes["pallet_arbor"] = [
        _in("under bearing", 2.25, 0, -2.5), _in("collar", 3.5, 0, 20.45), _in("between flats", 2.25, 0, 30),
        _out("flat 1", 2.25, 0, 24), _out("flat 2", 2.25, 0, 36),
    ]
    probes["great_wheel_arbor"] = [
        _in("collar", 3.5, 0, 0.75), _in("between flats", 2.25, 0, 30.5),
        _out("flat 1", 2.25, 0, 15), _out("flat 2", 2.25, 0, 36),
    ]
    probes["suspension_pin"] = [
        _in("shank", 2.25, 0, 40), _in("shoulder", 3.5, 0, 36), _in("round side", -2.25, 0, 32.5),
        _out("rear flat", 2.25, 0, 32.5), _out("front flat", 2.25, 0, 45),
    ]
    probes["escape_wheel"] = [
        _in("tooth 0", -1.1, 37.0, 23.5), _in("spoke", 0, 20.5, 23.5), _in("D flat", 2.25, 0, 10),
        _in("pinion tooth 0", 0, -11.0, 10), _in("boss", 0, 3.5, 1.0),
        Probe("window", _polar(20.5, 120 * _DEG, 23.5), OUTSIDE), _out("bore", -2.3, 0, 10),
        _out("beside boss", 0, 5, 1.0),
    ]
    probes["anchor"] = [
        Probe("entry pallet", _polar(40.0, (ce_a + g.top_e) / 2, 23.5), INSIDE),
        Probe("exit pallet", _polar(40.0, (cx_a + g.top_x) / 2, 23.5), INSIDE),
        _in("hub", 0, 5, 23.5), _in("boss", 0, 3.2, 27),
        _out("bore", -2, 0, 23.5), _out("between arms", 0, -20, 23.5), _out("beside boss", 0, 5, 27),
    ]
    probes["crutch"] = [
        _in("arm", 0, -20, 35.75), _in("pin", 0, -45, 40), _in("D flat", 2.25, 0, 35.75),
        _out("beside arm", 4, -20, 35.75), _out("bore", -2, 0, 35.75),
    ]
    lp = g.params.pendulum_length
    probes["pendulum"] = [
        _in("rod", 0, -100, 40.75), _in("bob", 0, -lp, 40.75), _in("below pocket", 6, 0, 38.25),
        _out("slot", 0, -59, 40.75), _out("lip", 0, 0, 38.25), _out("pocket", 6, 0, 41),
    ]
    probes["suspension_cap"] = [_in("wall", 3.0, 0, 45), _in("flat side", 2.25, 0, 45), _out("bore", -2.0, 0, 45)]
    probes["great_wheel"] = [
        _in("tooth 0", 37.0, 0, 3), Probe("land", _polar(12.5, 5 * _DEG, 7), INSIDE),
        Probe("under pocket", _polar(12.5, 27 * _DEG, 3), INSIDE),
        Probe("ratchet gap", _polar(12.5, 27 * _DEG, 7), OUTSIDE), _out("bore", 2.6, 0, 3),
    ]
    probes["pawl_carrier"] = [
        _in("core", 6, 0, 7), Probe("pawl tooth", _polar(11.5, pawl_g - 114 * _DEG, 7), INSIDE),
        Probe("arm", _polar(9.75, pawl_g - 60 * _DEG, 7), INSIDE), _in("boss", 0, 3.2, 10),
        Probe("slot", _polar(8.0, pawl_g - 60 * _DEG, 7), OUTSIDE), _out("bore", -2, 0, 7),
        _out("beside boss", 0, 5, 10.5),
    ]
    probes["mainspring"] = [
        _in("strip", 0, r1 + t / 2, 3), _in("hub", 0, -4.5, 3),
        _out("gap", 0, r1 - gap / 2, 3), _out("bore", 0, 0, 3), _out("eye hole", dm.eye_center_x, dm.eye_center_y, 3),
    ]
    probes["spring_spacer"] = [_in("wall", 3.0, 0, 20), _out("bore", -2, 0, 20)]
    probes["spring_anchor_pin"] = [_in("pin", 0, 0, 20), _out("beside pin", 1.6, 0, 20)]
    probes["winding_knob"] = [_in("knob", 6, 0, 35.75), _out("bore", -2, 0, 35.75)]
    probes["bearing"] = [_in("race", 4.75, 0, 2.5), _out("bore", 0, 0, 2.5)]
    probes["bolt"] = [
        _in("head", 1.4, 0, 0.5), _out("socket", 0, 0, 1.5), _in("shank", 0, 0, -3.0),
        _out("beside shank", 1.5, 0, -3.0),
    ]
    probes["nut"] = [_in("body", 1.5, 0, 0.8), _out("bore", 0, 0, 0.8)]
    return probes


def _clip_to_wheel(tip: tuple[float, float], other: tuple[float, float]) -> tuple[float, float]:
    """The point on the segment tip -> other at radius 33 (the segment starts outside the disc, ends inside)."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        x = tip[0] + (other[0] - tip[0]) * mid
        y = tip[1] + (other[1] - tip[1]) * mid
        if math.hypot(x, y) > _WHEEL_R:
            lo = mid
        else:
            hi = mid
    t = (lo + hi) / 2
    return (tip[0] + (other[0] - tip[0]) * t, tip[1] + (other[1] - tip[1]) * t)


def interaction_points(g: Geometry, s: State, dense: int = 20) -> list[MeshPoint]:
    """Points of one body that must lie outside another body at the pose of state s, in the component frame."""
    poses = body_poses(g, s)
    out: list[MeshPoint] = []

    # mesh: the pinion and great wheel outlines near the mesh point (0, -11) must not enter the other wheel.
    wheel, great = poses[b.ESCAPE_WHEEL], poses[b.GREAT_WHEEL]
    near = (0.0, -11.0)

    def keep(pt: tuple[float, float]) -> bool:
        return math.hypot(pt[0] - near[0], pt[1] - near[1]) <= 15.0

    pinion_poly = gear_outline_polygon(pinion_dims(g.params), dense, angle=g.pinion_phase)
    for j, q in enumerate(pinion_poly):
        x, y, z = wheel.apply((q[0], q[1], 5.0))
        if keep((x, y)):
            out.append(MeshPoint(f"mesh pinion vs great wheel #{j}", b.GREAT_WHEEL, (x, y, z)))
    great_poly = gear_outline_polygon(great_dims(g.params), dense)
    for j, q in enumerate(great_poly):
        x, y, z = great.apply((q[0], q[1], 5.0))
        if keep((x, y)):
            out.append(MeshPoint(f"mesh great wheel vs pinion #{j}", b.ESCAPE_WHEEL, (x, y, z)))

    # escapement: 5 points per exposed tooth edge, T -> L' and T -> B' (L', B' on the disc), against the anchor.
    tip = g.tooth_tip
    for e, (name, far) in enumerate((("T-L", g.tooth_l), ("T-B", g.tooth_b))):
        end = _clip_to_wheel(tip, far)
        for k in range(5):
            f = (k + 0.5) / 5
            base = (tip[0] + (end[0] - tip[0]) * f, tip[1] + (end[1] - tip[1]) * f)
            for tooth in range(30):
                a = 2 * math.pi * tooth / 30
                c, sn = math.cos(a), math.sin(a)
                px, py = base[0] * c - base[1] * sn, base[0] * sn + base[1] * c
                x, y, z = wheel.apply((px, py, 23.5))
                out.append(MeshPoint(f"escapement tooth {tooth} {name} #{k}", b.ANCHOR, (x, y, z)))

    # coupling: the crutch pin circle against the pendulum.
    crutch = poses[b.CRUTCH]
    for k in range(16):
        a = 2 * math.pi * k / 16
        x, y, z = crutch.apply((1.5 * math.cos(a), -45.0 + 1.5 * math.sin(a), 40.5))
        out.append(MeshPoint(f"coupling pin #{k}", b.PENDULUM, (x, y, z)))
    return out


def fastener_points(g: Geometry) -> list[MeshPoint]:
    """Bolt and nut surface points that must lie outside the plates they pass through (event `fit`)."""
    out: list[MeshPoint] = []
    for i, (px, py) in enumerate(PILLARS, start=1):
        for k in range(8):
            a = k * math.pi / 4
            c, sn = math.cos(a), math.sin(a)
            for z, target in ((23.0, b.BACK_PLATE), (30.0, b.FRONT_PLATE), (33.0, b.FRONT_PLATE)):
                out.append(MeshPoint(f"fit bolt {i} shank z{z:g} #{k}", target, (px + c, py + sn, z)))
            out.append(MeshPoint(f"fit bolt {i} head #{k}", b.FRONT_PLATE, (px + 1.85 * c, py + 1.85 * sn, 33.0)))
        for k in range(6):
            a = k * math.pi / 3
            out.append(
                MeshPoint(f"fit nut {i} corner #{k}", b.BACK_PLATE, (px + 2.3 * math.cos(a), py + 2.3 * math.sin(a), 25.0))
            )
    return out
