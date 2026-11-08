"""Point probes: points whose containment in a built body is known from the design."""

from __future__ import annotations

import dataclasses
import math

from . import gears, layout
from .dims import Dims
from .involute import gear_outline_polygon
from .fasteners import (
    HEAD_DIAMETER,
    HEAD_HEIGHT,
    NUT_ROOF,
    NUT_THICKNESS,
    SHANK_DIAMETER,
    nut_across_corners,
    nut_cavity_height,
)
from .params import FIT_CLEARANCE, KEY_COUNT, RING_MARGIN, Params, Vec3
from .phase import planet_orbit_angle, planet_tooth_angle, ring_tooth_angle
from .sections import bolt_angles, spoke_angle

INSIDE = "inside"
OUTSIDE = "outside"


@dataclasses.dataclass(frozen=True)
class Probe:
    label: str
    point: Vec3  # part-local coordinates
    expect: str  # "inside" | "outside"


@dataclasses.dataclass(frozen=True)
class MeshPoint:
    label: str
    target: str  # name of the body that must not contain the point
    point: Vec3  # assembled coordinates


def _polar(r: float, angle: float, z: float = 0.0) -> Vec3:
    return (r * math.cos(angle), r * math.sin(angle), z)


def _deg(angle: float) -> int:
    return int(round(math.degrees(angle)))


def _bolt_probes(d: Dims, z: float) -> list[Probe]:
    out = [Probe(f"bolt hole {i}", _polar(d.bolt_circle, a, z), OUTSIDE) for i, a in enumerate(bolt_angles())]
    out += [Probe(f"rim {i}", _polar(d.bolt_circle, i * math.pi / 2, z), INSIDE) for i in range(4)]
    return out


def _collar_probe(spec: layout.ShaftSpec, r: float, d: Dims) -> list[Probe]:
    if spec.collar is None:
        return []
    lo, hi = spec.collar
    return [Probe("collar", ((r + d.collar / 2) / 2, 0.0, (lo + hi) / 2), INSIDE)]


def part_probes(p: Params, d: Dims) -> dict[str, list[Probe]]:
    """Probes per part, in part-local coordinates. Keys are layout.PARTS (link_shaft only when stages > 1)."""
    t, tc, tv, g = p.gear_thickness, p.carrier_thickness, p.cover_thickness, p.stage_gap
    wb = d.bearing.width
    r = d.shaft / 2
    keyed = p.key_depth > 0
    # Shaft probes sit mid-groove (rg); bore probes sit mid-way between the bore tool's floor and its round (rt).
    rg = r - p.key_depth / 2 if keyed else r / 2
    rt = r + FIT_CLEARANCE - p.key_depth / 2
    thetas = [2 * math.pi * k / KEY_COUNT for k in range(KEY_COUNT)]
    sun_gd = gears.sun_gear(p)
    planet_gd = gears.planet_gear(p)
    ring_pitch = p.module * p.ring_teeth / 2
    theta_r = ring_tooth_angle(p)
    r_m = (d.lip / 2 + d.pocket / 2) / 2
    probes: dict[str, list[Probe]] = {}

    sun: list[Probe] = []
    if keyed:
        for th in thetas:
            sun.append(Probe(f"bore tooth {_deg(th)}", _polar(rt, th, t / 2), INSIDE))
            sun.append(Probe(f"bore {_deg(th)}", _polar(rt, th + math.pi / 3, t / 2), OUTSIDE))
    else:
        sun.append(Probe("bore", (0.0, 0.0, t / 2), OUTSIDE))
    sun.append(Probe("tooth zero", (sun_gd.pitch, 0.0, t / 2), INSIDE))
    sun.append(Probe("gap", _polar(sun_gd.pitch, math.pi / p.sun_teeth, t / 2), OUTSIDE))
    probes["sun"] = sun

    probes["planet"] = [
        Probe("lip bore", (0.0, 0.0, t / 2), OUTSIDE),
        Probe("pocket", (r_m, 0.0, t - wb / 2), OUTSIDE),
        Probe("lip", (r_m, 0.0, (t - wb) / 2), INSIDE),
        Probe("wall", ((d.pocket / 2 + d.planet_root) / 2, 0.0, t / 2), INSIDE),
        Probe("tooth zero", (planet_gd.pitch, 0.0, t / 2), INSIDE),
        Probe("gap", _polar(planet_gd.pitch, math.pi / p.planet_teeth, t / 2), OUTSIDE),
    ]

    zr = RING_MARGIN + d.ring_length / 2
    probes["ring"] = _bolt_probes(d, zr) + [
        Probe("tooth space", _polar(ring_pitch, theta_r, zr), OUTSIDE),
        Probe("tooth", _polar(ring_pitch, theta_r + math.pi / p.ring_teeth, zr), INSIDE),
        Probe("bore", (0.0, 0.0, zr), OUTSIDE),
    ]
    # Deviation from decad-gallery: the bolt-hole probes above stay; Fusion's point containment is exact for a
    # 2.4 mm hole (README deviations).
    # Nut cavities: closed hexagonal pockets, NUT_ROOF of material between the cavity and each end face.
    z_f = RING_MARGIN + NUT_ROOF + nut_cavity_height() / 2
    z_r = RING_MARGIN + d.ring_length - NUT_ROOF - nut_cavity_height() / 2
    bc = d.bolt_circle
    for i, a in enumerate(bolt_angles()):
        probes["ring"].append(Probe(f"front nut cavity {i}", _polar(bc + 1.65, a, z_f), OUTSIDE))
        probes["ring"].append(Probe(f"rear nut cavity {i}", _polar(bc + 1.65, a, z_r), OUTSIDE))
    a0 = bolt_angles()[0]
    probes["ring"].append(Probe("front nut roof", _polar(bc + 1.65, a0, RING_MARGIN + NUT_ROOF / 2), INSIDE))
    probes["ring"].append(Probe("rear nut roof", _polar(bc + 1.65, a0, RING_MARGIN + d.ring_length - NUT_ROOF / 2),
                                INSIDE))

    r_s = (d.cover_hub / 2 + d.rim_inner) / 2
    probes["cover"] = (
        [
            Probe("spoke", _polar(r_s, spoke_angle(0), tv / 2), INSIDE),
            Probe("window", _polar(r_s, spoke_angle(0) + math.pi / 3, tv / 2), OUTSIDE),
        ]
        + _bolt_probes(d, tv / 2)
        + [
            Probe("lip bore", (0.0, 0.0, tv / 2), OUTSIDE),
            Probe("boss pocket", (r_m, 0.0, tv + wb / 2), OUTSIDE),
            Probe("boss wall", ((d.pocket / 2 + d.cover_boss / 2) / 2, 0.0, tv + wb / 2), INSIDE),
        ]
    )
    for i, a in enumerate(bolt_angles()):
        probes["cover"].append(Probe(f"head pocket {i}", _polar(d.bolt_circle + 1.6, a, tv - HEAD_HEIGHT / 2), OUTSIDE))
        probes["cover"].append(Probe(f"under head {i}", _polar(d.bolt_circle + 1.6, a, (tv - HEAD_HEIGHT) / 2), INSIDE))

    probes["bolt"] = [
        Probe("head", (1.4, 0.0, 0.5), INSIDE),
        Probe("socket", (0.0, 0.0, 1.5), OUTSIDE),
        Probe("shank", (0.0, 0.0, -3.0), INSIDE),
        Probe("beside shank", (1.5, 0.0, -3.0), OUTSIDE),
    ]
    probes["nut"] = [Probe("body", (1.5, 0.0, 0.8), INSIDE), Probe("bore", (0.0, 0.0, 0.8), OUTSIDE)]

    bearing = [Probe("race", ((4.0 + 11.0) / 2, 0.0, wb / 2), INSIDE), Probe("bore", (0.0, 0.0, wb / 2), OUTSIDE)]
    probes["housing_bearing"] = list(bearing)
    probes["planet_bearing"] = list(bearing)

    n = p.planet_count
    e = d.orbit * math.cos(math.pi / n) + d.boss / 2
    hang = -(t + g) / 2
    carrier = [
        Probe("plate between pins", _polar((r + e) / 2, math.pi / n, tc / 2), INSIDE),
        Probe("plate near edge", _polar(e - 1.5, math.pi / n, tc / 2), INSIDE),
        Probe("beyond edge", _polar(e + 2.5, math.pi / n, tc / 2), OUTSIDE),
        Probe("pin boss", (d.orbit, 0.0, tc / 2), INSIDE),
        Probe("shaft hole", (0.0, 0.0, tc / 2), OUTSIDE),
        Probe("hole round side", (-(r - 1.5), 0.0, tc / 2), OUTSIDE),
    ]
    if keyed:
        carrier.append(Probe("hole tooth", (rt, 0.0, tc / 2), INSIDE))
    carrier += [
        Probe("pin", (d.orbit, 0.0, hang), INSIDE),
        Probe("beside pin", (d.orbit + d.pin / 2 + 2, 0.0, hang), OUTSIDE),
        Probe("above plate", (d.orbit, 0.0, tc + 0.5), OUTSIDE),
    ]
    probes["carrier"] = carrier

    spec = layout.input_shaft_spec(p, d)
    shaft: list[Probe] = []
    if keyed:
        for th in thetas:
            shaft.append(Probe(f"groove {_deg(th)}", _polar(rg, th, t / 2), OUTSIDE))
            shaft.append(Probe(f"round {_deg(th)}", _polar(rg, th + math.pi / 3, t / 2), INSIDE))
    shaft.append(Probe("under front bearing", (rg, 0.0, -(g + tv + wb / 2)), INSIDE))
    probes["input_shaft"] = shaft + _collar_probe(spec, r, d)

    link = layout.link_shaft_spec(p, d)
    if link is not None:
        lp: list[Probe] = []
        if keyed:
            for th in thetas:
                lp.append(Probe(f"groove {_deg(th)}", _polar(rg, th, tc / 2), OUTSIDE))
            for th in thetas:
                lp.append(Probe(f"sun groove {_deg(th)}", _polar(rg, th, (tc + g + link.top) / 2), OUTSIDE))
        if link.collar is not None:
            lo, hi = link.collar
            lp.append(Probe("collar over groove", (rg, 0.0, (lo + hi) / 2), INSIDE))
        probes["link_shaft"] = lp

    out = layout.output_shaft_spec(p, d)
    op: list[Probe] = []
    if keyed:
        for th in thetas:
            op.append(Probe(f"groove {_deg(th)}", _polar(rg, th, tc / 2), OUTSIDE))
    op.append(Probe("round under bearing", (rg, 0.0, out.top - p.output_shaft_length - wb / 2), INSIDE))
    probes["output_shaft"] = op + _collar_probe(out, r, d)
    return probes


def mesh_points(p: Params, d: Dims, dense: int = 20, extra_turn: float = 0.0) -> list[MeshPoint]:
    """Outline points of each gear that must lie outside the neighbouring bodies, in assembled coordinates."""
    sun_gd = gears.sun_gear(p)
    planet_gd = gears.planet_gear(p)
    ring_gd = gears.ring_tool(p)
    sun_poly = gear_outline_polygon(sun_gd, dense)
    ring_poly = gear_outline_polygon(ring_gd, dense, angle=ring_tooth_angle(p))
    out: list[MeshPoint] = []
    for k in range(p.stages):
        z = k * d.stage_pitch + p.gear_thickness / 2
        for i in range(p.planet_count):
            phi = planet_orbit_angle(p, i)
            center = (d.orbit * math.cos(phi), d.orbit * math.sin(phi))
            turn = planet_tooth_angle(p, i) + (extra_turn if i == 0 else 0.0)
            planet_poly = gear_outline_polygon(planet_gd, dense, angle=turn, center=center)
            tag = f"{k + 1}.{i + 1}"
            for j, q in enumerate(planet_poly):
                radius = math.hypot(q[0], q[1])
                if radius <= sun_gd.tip + 0.1:
                    out.append(MeshPoint(f"planet {tag} vs sun #{j}", layout.sun_name(k), (q[0], q[1], z)))
                if radius >= d.ring_tip - 0.1:
                    out.append(MeshPoint(f"planet {tag} vs ring #{j}", layout.RING_NAME, (q[0], q[1], z)))
            near = d.planet_tip + 0.1
            target = layout.planet_name(k, i)
            for j, q in enumerate(sun_poly):
                if math.hypot(q[0] - center[0], q[1] - center[1]) <= near:
                    out.append(MeshPoint(f"sun {k + 1} vs planet {tag} #{j}", target, (q[0], q[1], z)))
            for j, q in enumerate(ring_poly):
                if math.hypot(q[0] - center[0], q[1] - center[1]) <= near:
                    out.append(MeshPoint(f"ring vs planet {tag} #{j}", target, (q[0], q[1], z)))
    return out


def fastener_points(p: Params, d: Dims) -> list[MeshPoint]:
    """Bolt and nut surface points (assembled coordinates) that must lie outside the cover and ring they pass through.

    Stands in for the gallery's intersection-volume test TestFastenersFitTheirPockets.
    """
    out: list[MeshPoint] = []
    insts = layout.instances(p, d)
    floor = p.cover_thickness - HEAD_HEIGHT
    for inst in insts:
        if inst.part == "bolt":
            cover = layout.FRONT_COVER_NAME if inst.name.startswith("Front") else layout.REAR_COVER_NAME
            for k in range(8):
                th = k * math.pi / 4
                c, s = math.cos(th), math.sin(th)
                local = (
                    (f"{inst.name} head #{k}", (HEAD_DIAMETER / 2 * c, HEAD_DIAMETER / 2 * s, HEAD_HEIGHT / 2), cover),
                    (f"{inst.name} shank #{k}", (SHANK_DIAMETER / 2 * c, SHANK_DIAMETER / 2 * s, -floor / 2), cover),
                    (
                        f"{inst.name} roof #{k}",
                        (SHANK_DIAMETER / 2 * c, SHANK_DIAMETER / 2 * s, -floor - NUT_ROOF / 2),
                        layout.RING_NAME,
                    ),
                )
                for label, pt, target in local:
                    out.append(MeshPoint(label, target, inst.pose.apply(pt)))
        elif inst.part == "nut":
            for k in range(6):
                th = k * math.pi / 3
                pt = (nut_across_corners() / 2 * math.cos(th), nut_across_corners() / 2 * math.sin(th),
                      NUT_THICKNESS / 2)
                out.append(MeshPoint(f"{inst.name} corner #{k}", layout.RING_NAME, inst.pose.apply(pt)))
    return out
