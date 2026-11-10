"""Axial layout, instance poses and body names.

Own copy of decad-gallery models/planetarygearbox planetarygearbox.go (Named, build, buildHousing), place.go and the
shaft spans of carrier.go / cover.go, and fasteners.go (buildFasteners, fastener names) at a800069.
"""

from __future__ import annotations

import dataclasses
import math

from .dims import Dims
from .fasteners import (
    FASTENER_LENGTH,
    HEAD_HEIGHT,
    NUT_CLEARANCE,
    NUT_ROOF,
    NUT_THICKNESS,
    nut_angle,
    nut_cavity_height,
)
from .params import COLLAR_CLEARANCE, FIT_CLEARANCE, PLANET_BEARING_LIFT, RING_MARGIN, Params, Vec3
from .phase import planet_orbit_angle, planet_tooth_angle
from .sections import fastener_sites

RING_NAME = "Ring Gear"
FRONT_COVER_NAME = "Front Cover"
REAR_COVER_NAME = "Rear Cover"
FRONT_BEARING_NAME = "Front Bearing"
REAR_BEARING_NAME = "Rear Bearing"
INPUT_SHAFT_NAME = "Input Shaft"
OUTPUT_SHAFT_NAME = "Output Shaft"

# Gallery build order.
PARTS = (
    "ring",
    "cover",
    "housing_bearing",
    "input_shaft",
    "bolt",
    "nut",
    "sun",
    "planet",
    "planet_bearing",
    "carrier",
    "link_shaft",
    "output_shaft",
)


def sun_name(k: int) -> str:
    return f"Sun Gear {k + 1}"


def front_bolt_name(i: int) -> str:
    return f"Front Bolt {i + 1}"


def rear_bolt_name(i: int) -> str:
    return f"Rear Bolt {i + 1}"


def front_nut_name(i: int) -> str:
    return f"Front Nut {i + 1}"


def rear_nut_name(i: int) -> str:
    return f"Rear Nut {i + 1}"


def planet_name(k: int, i: int) -> str:
    return f"Planet Gear {k + 1}.{i + 1}"


def bearing_name(k: int, i: int) -> str:
    return f"Planet Bearing {k + 1}.{i + 1}"


def carrier_name(k: int) -> str:
    return f"Carrier {k + 1}"


def shaft_name(k: int, stages: int) -> str:
    return OUTPUT_SHAFT_NAME if k == stages - 1 else f"Link Shaft {k + 1}"


@dataclasses.dataclass(frozen=True)
class Pose:
    """Turn over about local X by pi (when flip), turn about local +Z by angle, then move by (x, y, z)."""

    angle: float = 0.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    flip: bool = False

    def _linear(self, pt: Vec3) -> Vec3:
        x, y, z = pt
        if self.flip:
            y, z = -y, -z
        s, c = math.sin(self.angle), math.cos(self.angle)
        return (x * c - y * s, x * s + y * c, z)

    def apply(self, pt: Vec3) -> Vec3:
        x, y, z = self._linear(pt)
        return (x + self.x, y + self.y, z + self.z)

    def unapply(self, pt: Vec3) -> Vec3:
        """Inverse of apply: subtract the move, turn by -angle, then flip when flip."""
        x, y, z = pt[0] - self.x, pt[1] - self.y, pt[2] - self.z
        s, c = math.sin(-self.angle), math.cos(-self.angle)
        x, y = x * c - y * s, x * s + y * c
        if self.flip:
            y, z = -y, -z
        return (x, y, z)

    def axes(self) -> tuple[Vec3, Vec3, Vec3, Vec3]:
        """Images of the origin and of the +X, +Y, +Z unit vectors."""
        return (
            self.apply((0.0, 0.0, 0.0)),
            self._linear((1.0, 0.0, 0.0)),
            self._linear((0.0, 1.0, 0.0)),
            self._linear((0.0, 0.0, 1.0)),
        )

    def is_identity(self) -> bool:
        return self.angle == 0 and self.x == 0 and self.y == 0 and self.z == 0 and not self.flip


@dataclasses.dataclass(frozen=True)
class ShaftSpec:
    bottom: float
    top: float
    collar: tuple[float, float] | None  # None when the collar is empty
    grooves: tuple[tuple[float, float], ...]


@dataclasses.dataclass(frozen=True)
class Instance:
    name: str
    part: str
    pose: Pose


def _collar(lo: float, hi: float) -> tuple[float, float] | None:
    return (lo, hi) if hi > lo else None


def input_shaft_spec(p: Params, d: Dims) -> ShaftSpec:
    g, tv, wb = p.stage_gap, p.cover_thickness, d.bearing.width
    return ShaftSpec(
        bottom=-(g + tv + wb + p.input_shaft_length),
        top=p.gear_thickness,
        collar=_collar(-(g + tv), -COLLAR_CLEARANCE),
        grooves=((0.0, p.gear_thickness + 1),),
    )


def link_shaft_spec(p: Params, d: Dims) -> ShaftSpec | None:
    if p.stages == 1:
        return None
    g, tc = p.stage_gap, p.carrier_thickness
    top = p.gear_thickness + tc + g
    if g > COLLAR_CLEARANCE:
        return ShaftSpec(
            0.0,
            top,
            (tc + COLLAR_CLEARANCE / 2, tc + g - COLLAR_CLEARANCE / 2),
            ((-1.0, tc), (tc + g, top + 1)),
        )
    return ShaftSpec(0.0, top, None, ((-1.0, top + 1),))


def output_shaft_spec(p: Params, d: Dims) -> ShaftSpec:
    g, tc, tv, wb = p.stage_gap, p.carrier_thickness, p.cover_thickness, d.bearing.width
    return ShaftSpec(
        bottom=0.0,
        top=tc + g + tv + wb + p.output_shaft_length,
        collar=_collar(tc + COLLAR_CLEARANCE, tc + g + tv - FIT_CLEARANCE),
        grooves=((-1.0, tc),),
    )


def part_local_z(p: Params, d: Dims, part: str) -> tuple[float, float]:
    """Axial range of the master body of part, in part-local coordinates."""
    wb = d.bearing.width
    if part == "bolt":
        return (-FASTENER_LENGTH, HEAD_HEIGHT)
    if part == "nut":
        return (0.0, NUT_THICKNESS)
    if part == "ring":
        return (RING_MARGIN, RING_MARGIN + d.ring_length)
    if part == "cover":
        return (0.0, p.cover_thickness + wb)
    if part in ("housing_bearing", "planet_bearing"):
        return (0.0, wb)
    if part in ("sun", "planet"):
        return (0.0, p.gear_thickness)
    if part == "carrier":
        return (-(p.gear_thickness + p.stage_gap), p.carrier_thickness)
    spec = {
        "input_shaft": input_shaft_spec,
        "link_shaft": link_shaft_spec,
        "output_shaft": output_shaft_spec,
    }[part](p, d)
    if spec is None:
        raise ValueError(f"{part} does not exist with {p.stages} stage(s)")
    return (spec.bottom, spec.top)


def instances(p: Params, d: Dims) -> list[Instance]:
    """Every body of the gearbox in the gallery's Named() order."""
    g, tv, wb, t = p.stage_gap, p.cover_thickness, d.bearing.width, p.gear_thickness
    length = d.ring_length
    out = [
        Instance(RING_NAME, "ring", Pose(z=-RING_MARGIN - g)),
        Instance(FRONT_COVER_NAME, "cover", Pose(flip=True, z=-g)),
        Instance(REAR_COVER_NAME, "cover", Pose(z=length - g)),
        Instance(FRONT_BEARING_NAME, "housing_bearing", Pose(z=-(g + tv + wb))),
        Instance(REAR_BEARING_NAME, "housing_bearing", Pose(z=length - g + tv)),
        Instance(INPUT_SHAFT_NAME, "input_shaft", Pose()),
    ]
    sites = fastener_sites(d)
    end = length - g
    # [buildFasteners] front bolts turn over about X so their heads face the front cover's outer face.
    for i, (x, y, a) in enumerate(sites):
        out.append(Instance(front_bolt_name(i), "bolt", Pose(flip=True, x=x, y=y, z=-(g + tv) + HEAD_HEIGHT)))
        out.append(
            Instance(front_nut_name(i), "nut", Pose(nut_angle(a), x, y, -g + NUT_ROOF + NUT_CLEARANCE))
        )
    for i, (x, y, a) in enumerate(sites):
        out.append(Instance(rear_bolt_name(i), "bolt", Pose(0.0, x, y, end + tv - HEAD_HEIGHT)))
        out.append(
            Instance(
                rear_nut_name(i),
                "nut",
                Pose(nut_angle(a), x, y, end - NUT_ROOF - NUT_CLEARANCE - NUT_THICKNESS),
            )
        )
    for k in range(p.stages):
        z = k * d.stage_pitch
        out.append(Instance(sun_name(k), "sun", Pose(z=z)))
        for i in range(p.planet_count):
            phi = planet_orbit_angle(p, i)
            x, y = d.orbit * math.cos(phi), d.orbit * math.sin(phi)
            out.append(Instance(planet_name(k, i), "planet", Pose(planet_tooth_angle(p, i), x, y, z)))
            zb = z + t - wb + PLANET_BEARING_LIFT
            out.append(Instance(bearing_name(k, i), "planet_bearing", Pose(0.0, x, y, zb)))
        zc = z + t + g
        out.append(Instance(carrier_name(k), "carrier", Pose(z=zc)))
        last = k == p.stages - 1
        out.append(Instance(shaft_name(k, p.stages), "output_shaft" if last else "link_shaft", Pose(z=zc)))
    return out


def instances_of(p: Params, d: Dims, part: str) -> list[Instance]:
    """Instances of part in placement order. The master body takes the last one."""
    return [i for i in instances(p, d) if i.part == part]


def master_name(p: Params, d: Dims, part: str) -> str:
    return instances_of(p, d, part)[-1].name


def nut_cavity_poses(p: Params, d: Dims) -> list[Pose]:
    """Ring-local poses of the nut cavity tool: front four, then rear four [cutNutPockets]."""
    out: list[Pose] = []
    for z in (RING_MARGIN + NUT_ROOF, RING_MARGIN + d.ring_length - NUT_ROOF - nut_cavity_height()):
        for x, y, _ in fastener_sites(d):
            out.append(Pose(0.0, x, y, z))
    return out


def head_pocket_poses(d: Dims) -> list[Pose]:
    """Cover-local poses of the head pocket tool, one per bolt site [cutHeadPockets]."""
    return [Pose(0.0, x, y, 0.0) for x, y, _ in fastener_sites(d)]


def expected_body_count(p: Params) -> int:
    return 6 + 16 + p.stages * (3 + 2 * p.planet_count)  # 8 bolts + 8 nuts
