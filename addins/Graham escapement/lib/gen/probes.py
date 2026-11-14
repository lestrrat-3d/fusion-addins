"""Point probes and interaction points: points whose containment in a built body is known from the design.

Own copy of the gearbox add-in's probe structure, with the escapement's probe tables of the design doc. Part probes
are in part-local coordinates (origin on the part's axis, z in model z). Interaction points are in the component frame.
The `round` probes (labels containing "round", plus the root taper and the slot end) stand in for the gallery's
TestCorners: each is a point on the segment from a sharp corner to its round's centre that only the round makes
material.
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
from .constants import CARRIER_CORE_RADIUS, SLOT_END_RADIUS
from .sections import (
    KEYED_RING_D, DFamily, anchor_rounds, crutch_rounds, escape_window_rounds, pawl_rounds, pendulum_rounds,
    ratchet_rounds, window_rounds,
)

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
    label: str  # starts with its event: mesh, escapement, coupling, fit, collar or bore
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

    def rnd(label: str, r, z: float) -> Probe:
        x, y = r.probe()
        return _in(label, x, y, z)

    win_r, win_l = window_rounds(g, 1.0), window_rounds(g, -1.0)
    slot_c = pawl_g - SLOT_END_RADIUS / (CARRIER_CORE_RADIUS + SLOT_END_RADIUS)
    slot_ctr = _polar(CARRIER_CORE_RADIUS + SLOT_END_RADIUS, slot_c)[:2]
    along = (-math.sin(slot_c), math.cos(slot_c))
    gangs = (pawl_g, pawl_g + math.pi)
    e = dm.taper_offset
    rho0, d = dm.first_inner_radius, dm.center_offset
    phi = 225 * _DEG
    s_old = -e * math.cos(phi) + math.sqrt(rho0 * rho0 - e * e * math.sin(phi) ** 2)
    rm = (rho0 - e + s_old) / 2

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
        rnd("window round F", win_r[0], -3), rnd("window round H", win_r[1], -3),
        rnd("window round A", win_r[6], -3), rnd("window round A left", win_l[6], -3),
    ]
    probes["front_plate"] = [
        _in("spine", 0, 30, 31), _in("socket wall", 0, 75, 31), _in("above seat", 6, 0, 33.5),
        _in("below head pocket", -48.3, 74, 31),
        _out("window -", -40, 0, 31), _out("window +", 40, 0, 31), _out("seat", 6, 0, 30),
        _out("suspension socket", 0, sy, 32.5), _out("anchor socket", qx, qy, 29),
        _out("head pocket -", -50, 74, 33), _out("head pocket +", 50, 74, 33),
        rnd("window round F", win_r[0], 31), rnd("window round H", win_r[1], 31),
        rnd("window round A", win_r[6], 31), rnd("window round A left", win_l[6], 31),
    ]
    probes["escape_arbor"] = [
        _in("axis", 0, 0, 10), _in("under bearing", 2.25, 0, -2.5), _in("collar", 3.5, 0, 26),
        _in("body round", -2.7, 0, 10), _in("kept by flat", 2.45, 0, 10),
        _out("flat", 2.65, 0, 10), _out("beyond body", -2.9, 0, 10), _out("seat", -2.6, 0, -2.5),
    ]
    probes["pallet_arbor"] = [
        _in("under bearing", 2.25, 0, -2.5), _in("shoulder", 3.5, 0, 10), _in("body round", -2.7, 0, 24),
        _in("end unflattened", 2.25, 0, 30),
        _out("body flat", 2.65, 0, 24), _out("end flat", 2.25, 0, 36), _out("seat", -2.6, 0, -2.5),
        _out("past end", 0, 0, 38.5),
    ]
    probes["great_wheel_arbor"] = [
        _in("collar", 3.5, 0, 1.75), _in("drive before flat", 2.95, 0, 4.25), _in("drive kept by flat", 2.45, 0, 10),
        _in("body round", -2.7, 0, 22), _in("end", 2.25, 0, 30.5),
        _out("drive flat", 2.75, 0, 10), _out("body flat", 2.65, 0, 22), _out("end flat", 2.25, 0, 36),
        _out("beyond drive", -3.15, 0, 10),
    ]
    probes["suspension_pin"] = [
        _in("shank", 2.25, 0, 42), _in("shoulder", 3.5, 0, 37), _in("round side", -2.25, 0, 32.5),
        _out("rear flat", 2.25, 0, 32.5), _out("front flat", 2.25, 0, 46), _out("beyond shank", 2.6, 0, 42),
    ]
    probes["escape_wheel"] = [
        _in("tooth 0", -1.1, 37.0, 23.5), _in("spoke", 0, 20.5, 23.5), _in("D flat side", 2.75, 0, 10),
        _in("pinion tooth 0", 0, -11.0, 10), _in("under front counterbore", 3.5, 0, 23.5),
        _in("front wall", 3.9, 0, 24.2), _in("rear floor", 3.5, 0, 3.5), _in("rear wall", 3.9, 0, 2.4),
        Probe("window", _polar(20.5, 120 * _DEG, 23.5), OUTSIDE), _out("bore", -2.75, 0, 10),
        _out("bore at flat", 2.5, 0, 10), _out("front counterbore", 3.5, 0, 24.2),
        _out("rear counterbore", 3.5, 0, 2.4), _out("rim chamfer", 3.9, 0, 24.9), _out("no boss", 0, 3.5, 1.0),
        rnd("window round inner", escape_window_rounds(0)[0], 23.5),
        rnd("window round outer", escape_window_rounds(0)[1], 23.5),
    ]
    probes["anchor"] = [
        Probe("entry pallet", _polar(40.0, (ce_a + g.top_e) / 2, 23.5), INSIDE),
        Probe("exit pallet", _polar(40.0, (cx_a + g.top_x) / 2, 23.5), INSIDE),
        _in("hub", 0, 5, 23.5), _in("D flat side", 2.75, 0, 22.5), _in("under counterbore", 3.5, 0, 24.2),
        _in("counterbore wall", 3.9, 0, 25.0),
        _out("bore", -2.75, 0, 23.5), _out("between arms", 0, -20, 23.5), _out("counterbore", 3.5, 0, 25.0),
        _out("rim chamfer", 3.9, 0, 25.9), _out("no boss", 0, 3.2, 27),
        rnd("round G_E", anchor_rounds(g)[0], 23.5), rnd("round H_E", anchor_rounds(g)[1], 23.5),
        rnd("round H_X", anchor_rounds(g)[2], 23.5), rnd("round G_X", anchor_rounds(g)[3], 23.5),
    ]
    probes["crutch"] = [
        _in("arm", 0, -20, 36.8), _in("pin", 0, -45, 41.55), _in("floor", -3.5, 0, 37.8),
        _in("beyond counterbore flat", 3.5, 0, 36.5), _in("counterbore wall", -3.9, 0, 36.5),
        _in("socket flat side", 2.25, 0, 37.8),
        _out("beside arm", 4, -20, 36.8), _out("keyed counterbore", -3.5, 0, 36.5),
        _out("counterbore at its flat", 3.2, 0, 36.5), _out("socket", -2, 0, 37.8),
        rnd("arm round left", crutch_rounds(g)[0], 36.8), rnd("arm round right", crutch_rounds(g)[1], 36.8),
    ]
    lp = g.params.pendulum_length
    probes["pendulum"] = [
        _in("rod", 0, -100, 41.8), _in("bob", 0, -lp, 41.8), _in("below pocket", 6, 0, 39.30),
        _out("slot", 0, -59, 41.8), _out("lip", 0, 0, 39.30), _out("pocket", 6, 0, 42.05),
        rnd("rod round eye", pendulum_rounds(g)[3], 41.8), rnd("rod round bob", pendulum_rounds(g)[2], 41.8),
    ]
    probes["suspension_cap"] = [_in("wall", 3.0, 0, 46.05), _in("flat side", 2.25, 0, 46.05), _out("bore", -2.0, 0, 46.05)]
    probes["great_wheel"] = [
        _in("tooth 0", 37.0, 0, 3), Probe("land", _polar(12.5, 5 * _DEG, 7), INSIDE),
        Probe("under pocket", _polar(12.5, 27 * _DEG, 3), INSIDE), _in("bore wall", 3.6, 0, 4.25),
        _in("counterbore wall", 4.4, 0, 3.0),
        Probe("ratchet gap", _polar(12.5, 27 * _DEG, 7), OUTSIDE), _out("bore", 3.3, 0, 4.25),
        _out("counterbore", 3.9, 0, 2.5), _out("rim chamfer", 4.3, 0, 1.6),
        rnd("ratchet root round", ratchet_rounds()[0], 7), Probe("ratchet slope", _polar(12.5, 22 * _DEG, 7), OUTSIDE),
    ]
    probes["pawl_carrier"] = [
        _in("core", 6, 0, 7), Probe("pawl tooth", _polar(11.5, pawl_g - 114 * _DEG, 7), INSIDE),
        Probe("arm", _polar(9.75, pawl_g - 60 * _DEG, 7), INSIDE), _in("boss", 0, 3.5, 10),
        _in("D flat side", 2.75, 0, 7),
        Probe("slot", _polar(8.0, pawl_g - 60 * _DEG, 7), OUTSIDE), _out("bore", -3.0, 0, 7),
        _out("beside boss", 0, 4.5, 10.5),
        rnd("tooth root round", pawl_rounds(gangs)[0], 7), rnd("block back round", pawl_rounds(gangs)[1], 7),
        _in("slot end wall", slot_ctr[0] + 0.8 * along[0], slot_ctr[1] + 0.8 * along[1], 7.25),
        _out("slot end centre", slot_ctr[0], slot_ctr[1], 7.25),
        _out("slot end air", slot_ctr[0] + 0.7 * along[0], slot_ctr[1] + 0.7 * along[1], 7.25),
    ]
    probes["mainspring"] = [
        _in("strip", 0, r1 + t / 2, 3), _in("hub", 0, -4.5, 3),
        _in("flat side", 0, 3.0, 3),
        _out("gap", 0, r1 - gap / 2, 3), _out("bore", 0, 0, 3), _out("eye hole", dm.eye_center_x, dm.eye_center_y, 3),
        _out("bore arc", 0, -3.2, 3), _out("bore rim chamfer", 0, -3.5, 0.1),
        _in("root taper", d + e + rm * math.cos(phi), rm * math.sin(phi), 3),
    ]
    probes["spring_spacer"] = [
        _in("wall", 3.0, 0, 20), _in("D flat side", 2.75, 0, 20), _out("bore", -2.75, 0, 20),
        _out("bore at flat", 2.5, 0, 20),
    ]
    probes["spring_anchor_pin"] = [_in("pin", 0, 0, 20), _out("beside pin", 1.6, 0, 20)]
    probes["winding_knob"] = [
        _in("knob", 6, 0, 36.8), _in("floor", -3.5, 0, 37.8), _in("counterbore wall", -3.9, 0, 36.5),
        _out("keyed counterbore", -3.5, 0, 36.5), _out("socket", -2, 0, 37.8),
    ]
    probes["arbor_collar"] = [
        _in("wall", 3.2, 0, 1.5), _in("D flat side", 2.75, 0, 1.5), _out("bore", -2.75, 0, 1.5),
        _out("beyond", 3.8, 0, 1.5),
    ]
    probes["end_collar"] = [
        _in("arc side", -3.5, 0, 1.5), _in("between flats", 3.0, 0, 1.5), _in("bore flat side", 2.25, 0, 1.5),
        _out("bore", -2.0, 0, 1.5), _out("beyond chord", 3.4, 0, 1.5),
    ]
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
        x, y, z = crutch.apply((1.5 * math.cos(a), -45.0 + 1.5 * math.sin(a), 41.55))
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


def _ring(r: float, n: int = 16) -> list[tuple[float, float]]:
    return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _d_outline(d: DFamily) -> list[tuple[float, float]]:
    """12 points on the arc of the D family, end to end, and 3 on its chord (flat on +X)."""
    r, x = d
    a0 = math.acos(x / r)
    h = math.sqrt(r * r - x * x)
    arc = [(r * math.cos(a0 + (2 * math.pi - 2 * a0) * i / 11), r * math.sin(a0 + (2 * math.pi - 2 * a0) * i / 11))
           for i in range(12)]
    return arc + [(x, -h / 2), (x, 0.0), (x, h / 2)]


# (label, source body, outline, z in the source's own frame, target body) [collars.go, install and fit tests].
_COLLAR_ROWS: tuple[tuple[str, str, list[tuple[float, float]], float, str], ...] = (
    ("collar escape front", b.ESCAPE_ARBOR, _ring(3.7), 24.5, b.ESCAPE_WHEEL),
    ("collar escape rear", b.ESCAPE_REAR_COLLAR, _ring(3.7), 2.15, b.ESCAPE_WHEEL),
    ("collar pallet front", b.PALLET_FRONT_COLLAR, _ring(3.7), 0.75, b.ANCHOR),
    ("collar great wheel", b.GREAT_WHEEL_ARBOR, _ring(3.7), 2.5, b.GREAT_WHEEL),
    ("collar crutch", b.CRUTCH_COLLAR, _d_outline(KEYED_RING_D), 2.25, b.CRUTCH),
    ("collar knob", b.KNOB_COLLAR, _d_outline(KEYED_RING_D), 2.25, b.WINDING_KNOB),
)

_ARBOR_BODY = (2.8, 2.55)
_ARBOR_END = (2.5, 2.0)
_ARBOR_DRIVE = (3.05, 2.55)

_BORE_ROWS: tuple[tuple[str, str, list[tuple[float, float]], float, str], ...] = (
    ("bore escape wheel", b.ESCAPE_ARBOR, _d_outline(_ARBOR_BODY), 10.0, b.ESCAPE_WHEEL),
    ("bore escape rear collar", b.ESCAPE_ARBOR, _d_outline(_ARBOR_BODY), 1.75, b.ESCAPE_REAR_COLLAR),
    ("bore anchor", b.PALLET_ARBOR, _d_outline(_ARBOR_BODY), 24.0, b.ANCHOR),
    ("bore pallet front collar", b.PALLET_ARBOR, _d_outline(_ARBOR_BODY), 26.25, b.PALLET_FRONT_COLLAR),
    ("bore crutch collar", b.PALLET_ARBOR, _d_outline(_ARBOR_END), 36.0, b.CRUTCH_COLLAR),
    ("bore crutch", b.PALLET_ARBOR, _d_outline(_ARBOR_END), 37.8, b.CRUTCH),
    ("bore great wheel", b.GREAT_WHEEL_ARBOR, _ring(3.05), 4.25, b.GREAT_WHEEL),
    ("bore pawl carrier", b.GREAT_WHEEL_ARBOR, _d_outline(_ARBOR_DRIVE), 7.0, b.PAWL_CARRIER),
    ("bore mainspring", b.GREAT_WHEEL_ARBOR, _d_outline(_ARBOR_DRIVE), 14.25, b.MAINSPRING),
    ("bore spring spacer", b.GREAT_WHEEL_ARBOR, _d_outline(_ARBOR_BODY), 22.0, b.SPRING_SPACER),
    ("bore knob collar", b.GREAT_WHEEL_ARBOR, _d_outline(_ARBOR_END), 36.0, b.KNOB_COLLAR),
    ("bore knob", b.GREAT_WHEEL_ARBOR, _d_outline(_ARBOR_END), 37.8, b.WINDING_KNOB),
    ("bore suspension cap", b.SUSPENSION_PIN, _d_outline(_ARBOR_END), 46.05, b.SUSPENSION_CAP),
)


def _posed_rows(g: Geometry, s: State, rows) -> list[MeshPoint]:
    poses = body_poses(g, s)
    out: list[MeshPoint] = []
    for label, source, outline, z, target in rows:
        for k, (px, py) in enumerate(outline):
            out.append(MeshPoint(f"{label} #{k}", target, poses[source].apply((px, py, z))))
    return out


def collar_points(g: Geometry, s: State) -> list[MeshPoint]:
    """Collar and arbor surface points that must lie outside the part counterbored for them (event `collar`)."""
    return _posed_rows(g, s, _COLLAR_ROWS)


def bore_points(g: Geometry, s: State) -> list[MeshPoint]:
    """Arbor section points that must lie outside every part bored for them (event `bore`)."""
    return _posed_rows(g, s, _BORE_ROWS)
