"""Point probes: points whose containment in a built body is known from the design."""

from __future__ import annotations

import dataclasses
import math

from . import gears, layout
from .bridge import BRIDGE_THICKNESS
from .dims import Dims
from .ears import ear_angle, ear_center_radius, ear_half_width
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
from .params import PRESS_FIT_CLEARANCE, RING_MARGIN, Params, Vec3
from .phase import planet_orbit_angle, planet_tooth_angle, ring_tooth_angle
from .sections import bolt_angles, carrier_hole_radius, pin_socket_radius, spoke_angle

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


def _bolt_probes(d: Dims, z: float) -> list[Probe]:
    out = [Probe(f"bolt hole {i}", _polar(d.bolt_circle, a, z), OUTSIDE) for i, a in enumerate(bolt_angles())]
    out += [Probe(f"rim {i}", _polar(d.bolt_circle, i * math.pi / 2, z), INSIDE) for i in range(4)]
    return out


def _collar_probe(spec: layout.ShaftSpec, r: float, d: Dims) -> list[Probe]:
    if spec.collar is None:
        return []
    lo, hi = spec.collar
    return [Probe("collar", ((r + d.collar / 2) / 2, 0.0, (lo + hi) / 2), INSIDE)]


def _thick_probes(p: Params, d: Dims, spec: layout.ShaftSpec) -> list[Probe]:
    """Probes in the D thick part of a link or output shaft: material on the round side, none past the flat."""
    assert spec.thick_top is not None
    z = spec.thick_top / 2
    rk = d.collar / 2 - p.flat_depth / 2 if p.flat_depth > 0 else d.collar / 2 - 0.25
    out = [Probe("thick", (-rk, 0.0, z), INSIDE), Probe("beside thick", (d.collar / 2 + 0.5, 0.0, z), OUTSIDE)]
    if p.flat_depth > 0:
        out.append(Probe("thick flat", (rk, 0.0, z), OUTSIDE))
    return out


def _ear_probes(p: Params, d: Dims, z: float) -> list[Probe]:
    """Ring probes for the mounting ears: the bore, the wall between bore and ring, the ear's tip and side, and the
    bare ring between two ears. None without ears."""
    if p.ear_count == 0:
        return []
    half = ear_half_width(p.ear_bore_diameter)
    centre = ear_center_radius(d.ring_outer, p.ear_bore_diameter)
    out: list[Probe] = []
    for i in range(p.ear_count):
        a = ear_angle(i, p.ear_count)
        out.append(Probe(f"ear {i} bore", _polar(centre, a, z), OUTSIDE))
        out.append(Probe(f"ear {i} wall", _polar((d.ring_outer + centre - p.ear_bore_diameter / 2) / 2, a, z), INSIDE))
        out.append(Probe(f"ear {i} tip", _polar(centre + half + 1.0, a, z), OUTSIDE))
        side = (centre * math.cos(a) - (half + 0.5) * math.sin(a), centre * math.sin(a) + (half + 0.5) * math.cos(a))
        out.append(Probe(f"ear {i} side", (side[0], side[1], z), OUTSIDE))
        # The bare ring between two ears, only when it lies a clear 1 mm beside the ears' sides.
        if p.ear_count == 1 or (d.ring_outer + 1.0) * math.sin(math.pi / p.ear_count) >= half + 1.0:
            out.append(Probe(f"between ears {i}", _polar(d.ring_outer + 1.0, a + math.pi / p.ear_count, z), OUTSIDE))
    return out


def part_probes(p: Params, d: Dims) -> dict[str, list[Probe]]:
    """Probes per part, in part-local coordinates. Keys are layout.PARTS (link_shaft only when stages > 1)."""
    t, tc, tv, g = p.gear_thickness, p.carrier_thickness, p.cover_thickness, p.stage_gap
    ws, wp = d.shaft_bearing.width, d.planet_bearing.width
    r = d.shaft / 2
    flat = p.flat_depth > 0
    # Shaft probes sit mid-flat (rg); bore probes sit mid-way between the bore tool's flat and its round (rt).
    rg = r - p.flat_depth / 2 if flat else r / 2
    rt = r + PRESS_FIT_CLEARANCE - p.flat_depth / 2
    sun_gd = gears.sun_gear(p)
    planet_gd = gears.planet_gear(p)
    ring_pitch = p.module * p.ring_teeth / 2
    theta_r = ring_tooth_angle(p)
    r_p = (d.planet_lip / 2 + d.planet_pocket / 2) / 2
    r_c = (d.cover_lip / 2 + d.cover_pocket / 2) / 2
    probes: dict[str, list[Probe]] = {}

    sun: list[Probe] = []
    if flat:
        sun.append(Probe("bore tooth", (rt, 0.0, t / 2), INSIDE))
        sun.append(Probe("bore round side", (-rt, 0.0, t / 2), OUTSIDE))
        sun.append(Probe("bore", (0.0, 0.0, t / 2), OUTSIDE))
    else:
        sun.append(Probe("bore", (0.0, 0.0, t / 2), OUTSIDE))
    sun.append(Probe("tooth zero", (sun_gd.pitch, 0.0, t / 2), INSIDE))
    sun.append(Probe("gap", _polar(sun_gd.pitch, math.pi / p.sun_teeth, t / 2), OUTSIDE))
    probes["sun"] = sun

    probes["planet"] = [
        Probe("lip bore", (0.0, 0.0, t / 2), OUTSIDE),
        Probe("pocket", (r_p, 0.0, t - wp / 2), OUTSIDE),
        Probe("lip", (r_p, 0.0, (t - wp) / 2), INSIDE),
        Probe("wall", ((d.planet_pocket / 2 + d.planet_root) / 2, 0.0, t / 2), INSIDE),
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
    # 2.6 mm hole (README deviations).
    # Nut cavities: closed hexagonal pockets, NUT_ROOF of material between the cavity and each end face.
    h = nut_cavity_height()
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
    # Sacrificial bridge layers (not in the gallery model): the bolt hole is filled for BRIDGE_THICKNESS directly above
    # each cavity's roof, so a point on the bolt circle in the middle of that span is material.
    layer_f = z_f + h / 2 + BRIDGE_THICKNESS / 2
    layer_r = z_r + h / 2 + BRIDGE_THICKNESS / 2
    if p.sacrificial_bridging:
        for i, a in enumerate(bolt_angles()):
            probes["ring"].append(Probe(f"front bridge layer {i}", _polar(bc, a, layer_f), INSIDE))
            probes["ring"].append(Probe(f"rear bridge layer {i}", _polar(bc, a, layer_r), INSIDE))
    probes["ring"] += _ear_probes(p, d, zr)

    r_s = (d.cover_hub / 2 + d.rim_inner) / 2
    probes["cover"] = (
        [
            Probe("spoke", _polar(r_s, spoke_angle(0), tv / 2), INSIDE),
            Probe("window", _polar(r_s, spoke_angle(0) + math.pi / 3, tv / 2), OUTSIDE),
        ]
        + _bolt_probes(d, tv / 2)
        + [
            Probe("lip bore", (0.0, 0.0, tv / 2), OUTSIDE),
            Probe("boss pocket", (r_c, 0.0, tv + ws / 2), OUTSIDE),
            Probe("boss wall", ((d.cover_pocket / 2 + d.cover_boss / 2) / 2, 0.0, tv + ws / 2), INSIDE),
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

    for part, spec_b in (("housing_bearing", d.shaft_bearing), ("planet_bearing", d.planet_bearing)):
        probes[part] = [
            Probe("race", ((spec_b.bore_diameter + spec_b.outer_diameter) / 4, 0.0, spec_b.width / 2), INSIDE),
            Probe("bore", (0.0, 0.0, spec_b.width / 2), OUTSIDE),
        ]

    n = p.planet_count
    e = d.orbit * math.cos(math.pi / n) + d.boss / 2
    rs = pin_socket_radius(d)
    rh = carrier_hole_radius(d)
    carrier = [
        Probe("plate between pins", _polar((r + e) / 2, math.pi / n, tc / 2), INSIDE),
        Probe("plate near edge", _polar(e - 1.5, math.pi / n, tc / 2), INSIDE),
        Probe("beyond edge", _polar(e + 2.5, math.pi / n, tc / 2), OUTSIDE),
        Probe("pin boss", (d.orbit + rs + 0.5, 0.0, tc / 2), INSIDE),
        Probe("pin socket low", (d.orbit, 0.0, tc / 4), OUTSIDE),
        Probe("pin socket high", (d.orbit, 0.0, 3 * tc / 4), OUTSIDE),
        Probe("shaft hole", (0.0, 0.0, tc / 2), OUTSIDE),
        Probe("hole round side", (-(r - 1.5), 0.0, tc / 2), OUTSIDE),
    ]
    if flat:
        carrier.append(Probe("hole tooth", (rh - p.flat_depth / 2, 0.0, tc / 2), INSIDE))
        # The socket's flat faces outward on planet 0's side: the plate keeps a tooth beyond it.
        carrier.append(Probe("socket tooth", (d.orbit + rs - p.flat_depth / 2, 0.0, tc / 4), INSIDE))
    carrier.append(Probe("above plate", (d.orbit, 0.0, tc + 0.5), OUTSIDE))
    probes["carrier"] = carrier

    # Carrier pin, in its own frame: a thin rod below, then the D thick part that passes through the plate's socket.
    spans = layout.pin_spans(p)
    rod_z = (spans.rod[0] + spans.thick[0]) / 2
    thick_z = (spans.thick[0] + spans.thick[1]) / 2
    rk = d.pin_collar / 2 - p.flat_depth / 2 if flat else d.pin_collar / 2 - 0.25
    pin: list[Probe] = [
        Probe("rod", (d.pin / 4, 0.0, rod_z), INSIDE),
        Probe("beside rod", (d.pin / 2 + 0.75, 0.0, rod_z), OUTSIDE),
        Probe("thick", (-rk, 0.0, thick_z), INSIDE),
        Probe("beside thick", (d.pin_collar / 2 + 0.5, 0.0, thick_z), OUTSIDE),
        Probe("above thick", (0.0, 0.0, spans.thick[1] + 0.2), OUTSIDE),
    ]
    if flat:
        pin.append(Probe("thick flat", (rk, 0.0, thick_z), OUTSIDE))
    probes["carrier_pin"] = pin

    spec = layout.input_shaft_spec(p, d)
    shaft: list[Probe] = []
    if flat:
        shaft.append(Probe("flat", (rg, 0.0, t / 2), OUTSIDE))
        shaft.append(Probe("round side", (-rg, 0.0, t / 2), INSIDE))
    shaft.append(Probe("under front bearing", (rg, 0.0, -(g + tv + ws / 2)), INSIDE))
    probes["input_shaft"] = shaft + _collar_probe(spec, r, d)

    link = layout.link_shaft_spec(p, d)
    if link is not None:
        lp = _thick_probes(p, d, link)
        if flat:
            lp.append(Probe("sun flat", (rg, 0.0, (tc + g + link.top) / 2), OUTSIDE))
        probes["link_shaft"] = lp

    out = layout.output_shaft_spec(p, d)
    op = _thick_probes(p, d, out)
    op.append(Probe("round under bearing", (rg, 0.0, out.top - p.output_shaft_length - ws / 2), INSIDE))
    probes["output_shaft"] = op
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
