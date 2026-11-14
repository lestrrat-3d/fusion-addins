"""Axial layout, instance poses and body names.

Own copy of decad-gallery models/planetarygearbox planetarygearbox.go (Named, build, buildHousing), place.go and the
shaft spans of carrier.go / cover.go, and fasteners.go (buildFasteners, fastener names) at c2cbb77.
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
from .params import (
    COLLAR_BEARING_GAP,
    COLLAR_CLEARANCE,
    END_FLAT_MARGIN,
    FIT_CLEARANCE,
    PIN_SHOULDER_CLEARANCE,
    PLANET_BEARING_LIFT,
    RING_MARGIN,
    STEP_OVERLAP,
    Params,
    Vec3,
)
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
    "carrier_pin",
    "carrier",
    "link_shaft",
    "output_shaft",
)

SPLIT_PARTS = ("carrier_pin", "input_shaft", "link_shaft", "output_shaft")


def split_names(name: str) -> tuple[str, str]:
    """Names of a split pin's or shaft's two halves: the half on the -X side of the plane through its axis that is
    parallel to the D flat (the plane's normal is the part's local +X), then the half on the +X side, which holds
    the flat."""
    return f"{name} Half 1", f"{name} Half 2"


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


def pin_name(k: int, i: int) -> str:
    return f"Carrier Pin {k + 1}.{i + 1}"


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
    flats: tuple[tuple[float, float], ...]
    # Top of the D thick part of a link or output shaft, from bottom; None for the input shaft, a plain rod.
    thick_top: float | None = None


@dataclasses.dataclass(frozen=True)
class Instance:
    name: str
    part: str
    pose: Pose


def _collar(lo: float, hi: float) -> tuple[float, float] | None:
    return (lo, hi) if hi > lo else None


def input_shaft_spec(p: Params, d: Dims) -> ShaftSpec:
    g, tv, wb = p.stage_gap, p.cover_thickness, d.shaft_bearing.width
    bottom = -(g + tv + wb + p.input_shaft_length)
    # [buildInputShaft] The collar starts COLLAR_BEARING_GAP above the front bearing's inner face. A second flat runs
    # along the end that reaches out of the cover, ending END_FLAT_MARGIN short of the boss.
    return ShaftSpec(
        bottom=bottom,
        top=p.gear_thickness,
        collar=_collar(-(g + tv) + COLLAR_BEARING_GAP, -COLLAR_CLEARANCE),
        flats=((0.0, p.gear_thickness + 1), (bottom - 1, bottom + p.input_shaft_length - END_FLAT_MARGIN)),
    )


def link_shaft_spec(p: Params, d: Dims) -> ShaftSpec | None:
    """[buildSteppedShaft] A D thick part pressed through the carrier, ending FIT_CLEARANCE short of the next sun, and
    a thin rod through that sun's bore with one flat over the sun."""
    if p.stages == 1:
        return None
    g, tc = p.stage_gap, p.carrier_thickness
    top = p.gear_thickness + tc + g
    return ShaftSpec(0.0, top, None, ((tc + g, top + 1),), thick_top=tc + g - FIT_CLEARANCE)


def output_shaft_spec(p: Params, d: Dims) -> ShaftSpec:
    g, tc, tv, wb = p.stage_gap, p.carrier_thickness, p.cover_thickness, d.shaft_bearing.width
    top = tc + g + tv + wb + p.output_shaft_length
    # [Build] A flat on the free end, starting END_FLAT_MARGIN clear of the rear boss.
    return ShaftSpec(
        bottom=0.0,
        top=top,
        collar=None,
        flats=((top - p.output_shaft_length + END_FLAT_MARGIN, top + 1),),
        thick_top=tc + g + tv - FIT_CLEARANCE,
    )


@dataclasses.dataclass(frozen=True)
class PinSpans:
    """Axial ranges of a carrier pin's rod and thick part, in the pin's own frame (z = 0 is the plate's lower face)."""

    rod: tuple[float, float]
    thick: tuple[float, float]


def pin_spans(p: Params) -> PinSpans:
    """[buildPin] The rod reaches STEP_OVERLAP into the thick part, so the union crosses faces. The thick part ends
    level with the plate's upper face."""
    hang = p.gear_thickness + p.stage_gap
    thick_bottom = -p.stage_gap + PLANET_BEARING_LIFT + PIN_SHOULDER_CLEARANCE
    return PinSpans(rod=(-hang, thick_bottom + STEP_OVERLAP), thick=(thick_bottom, p.carrier_thickness))


def part_local_z(p: Params, d: Dims, part: str) -> tuple[float, float]:
    """Axial range of the master body of part, in part-local coordinates."""
    if part == "bolt":
        return (-FASTENER_LENGTH, HEAD_HEIGHT)
    if part == "nut":
        return (0.0, NUT_THICKNESS)
    if part == "ring":
        return (RING_MARGIN, RING_MARGIN + d.ring_length)
    if part == "cover":
        return (0.0, p.cover_thickness + d.shaft_bearing.width)
    if part == "housing_bearing":
        return (0.0, d.shaft_bearing.width)
    if part == "planet_bearing":
        return (0.0, d.planet_bearing.width)
    if part in ("sun", "planet"):
        return (0.0, p.gear_thickness)
    if part == "carrier":
        return (0.0, p.carrier_thickness)
    if part == "carrier_pin":
        return (pin_spans(p).rod[0], pin_spans(p).thick[1])
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
    g, tv, t = p.stage_gap, p.cover_thickness, p.gear_thickness
    wbs, wbp = d.shaft_bearing.width, d.planet_bearing.width
    length = d.ring_length
    out = [
        Instance(RING_NAME, "ring", Pose(z=-RING_MARGIN - g)),
        Instance(FRONT_COVER_NAME, "cover", Pose(flip=True, z=-g)),
        Instance(REAR_COVER_NAME, "cover", Pose(z=length - g)),
        Instance(FRONT_BEARING_NAME, "housing_bearing", Pose(z=-(g + tv + wbs))),
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
            zb = z + t - wbp + PLANET_BEARING_LIFT
            out.append(Instance(bearing_name(k, i), "planet_bearing", Pose(0.0, x, y, zb)))
        zc = z + t + g
        for i in range(p.planet_count):
            phi = planet_orbit_angle(p, i)
            # The pin turns with its orbit angle, so its flat faces the same way as its socket.
            out.append(
                Instance(pin_name(k, i), "carrier_pin", Pose(phi, d.orbit * math.cos(phi), d.orbit * math.sin(phi), zc))
            )
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
    return 6 + 16 + p.stages * (3 + 3 * p.planet_count)  # 8 bolts + 8 nuts
