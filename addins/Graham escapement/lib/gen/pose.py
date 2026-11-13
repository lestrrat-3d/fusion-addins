"""Part poses of the escapement.

Own copy of the gearbox add-in's Pose, and of decad-gallery models/escapement build.go (poses, poseAll),
drive.go buildMainspring (spring pose) and internal/m2fastener PlaceBolt, PlaceNut at 3a4f9d8.

Every part is built about its own axis at the component origin, then moved once by its Pose: a turn about local +Z
by `angle` (after a flip about local X when `flip`), then a move by (x, y, z). The result equals the gallery's
"build in the model frame, then turn about the part's axis".
"""

from __future__ import annotations

import dataclasses
import math

from . import bodies as b
from .constants import BACK_BEARING_Z, BUILD_BACKOFF, DRUM_OFFSET, ESCAPE_REAR_COLLAR_LOW, FRONT_BEARING_Z, GREAT_TEETH
from .constants import OUTSIDE_COLLAR_LOW, PALLET_FRONT_COLLAR_LOW, PENDULUM_BEARING_Z, PINION_TEETH, SPRING_Z
from .fasteners import PILLARS
from .layout import Geometry
from .motion import State
from .params import Vec3


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


BOLT_Z = 32.0  # head underside of a bolt [PlaceBolt: frame origin At(2.0), head up]
NUT_Z = 25.8  # a flipped nut's local z[0, 1.6] covers model z[25.8, 24.2] [PlaceNut: frame origin At(8.2), V = -Y]


def body_poses(g: Geometry, s: State) -> dict[str, Pose]:
    """The Pose of every body name at state s, from a part built about its own axis at the origin."""
    wheel = s.wheel_angle - BUILD_BACKOFF
    great = g.great_phase + wheel * PINION_TEETH / GREAT_TEETH
    arbor = great + DRUM_OFFSET + g.carrier_offset
    o, p, sx, gg, q = g.axis_o, g.axis_p, g.axis_s, g.axis_g, g.spring_anchor
    psi, beta = s.anchor_angle, s.pendulum_angle
    out: dict[str, Pose] = {
        b.BACK_PLATE: Pose(),
        b.FRONT_PLATE: Pose(),
        b.BACK_ESCAPE_BEARING: Pose(x=o[0], y=o[1], z=BACK_BEARING_Z),
        b.BACK_PALLET_BEARING: Pose(x=p[0], y=p[1], z=BACK_BEARING_Z),
        b.BACK_GREAT_WHEEL_BEARING: Pose(x=gg[0], y=gg[1], z=BACK_BEARING_Z),
        b.FRONT_ESCAPE_BEARING: Pose(x=o[0], y=o[1], z=FRONT_BEARING_Z),
        b.FRONT_PALLET_BEARING: Pose(x=p[0], y=p[1], z=FRONT_BEARING_Z),
        b.FRONT_GREAT_WHEEL_BEARING: Pose(x=gg[0], y=gg[1], z=FRONT_BEARING_Z),
        b.PENDULUM_BEARING: Pose(angle=-beta, x=sx[0], y=sx[1], z=PENDULUM_BEARING_Z),
        b.ESCAPE_ARBOR: Pose(angle=-wheel),
        b.ESCAPE_WHEEL: Pose(angle=-wheel),
        b.PALLET_ARBOR: Pose(angle=-psi, x=p[0], y=p[1]),
        b.ANCHOR: Pose(angle=-psi, x=p[0], y=p[1]),
        b.CRUTCH: Pose(angle=-psi, x=p[0], y=p[1]),
        b.PENDULUM: Pose(angle=-beta, x=sx[0], y=sx[1]),
        b.SUSPENSION_PIN: Pose(x=sx[0], y=sx[1]),
        b.SUSPENSION_CAP: Pose(x=sx[0], y=sx[1]),
        b.GREAT_WHEEL: Pose(angle=great, x=gg[0], y=gg[1]),
        b.GREAT_WHEEL_ARBOR: Pose(angle=arbor, x=gg[0], y=gg[1]),
        b.PAWL_CARRIER: Pose(angle=arbor, x=gg[0], y=gg[1]),
        b.SPRING_SPACER: Pose(angle=arbor, x=gg[0], y=gg[1]),
        b.WINDING_KNOB: Pose(angle=arbor, x=gg[0], y=gg[1]),
        b.MAINSPRING: Pose(angle=g.spring_turn, x=gg[0], y=gg[1], z=SPRING_Z),
        b.SPRING_ANCHOR_PIN: Pose(x=q[0], y=q[1]),
        b.ESCAPE_REAR_COLLAR: Pose(angle=-wheel, z=ESCAPE_REAR_COLLAR_LOW),
        b.PALLET_FRONT_COLLAR: Pose(angle=-psi, x=p[0], y=p[1], z=PALLET_FRONT_COLLAR_LOW),
        b.CRUTCH_COLLAR: Pose(angle=-psi, x=p[0], y=p[1], z=OUTSIDE_COLLAR_LOW),
        b.KNOB_COLLAR: Pose(angle=arbor, x=gg[0], y=gg[1], z=OUTSIDE_COLLAR_LOW),
    }
    for name, (px, py) in zip(b.BOLT_NAMES, PILLARS):
        out[name] = Pose(x=px, y=py, z=BOLT_Z)
    for name, (px, py) in zip(b.NUT_NAMES, PILLARS):
        out[name] = Pose(flip=True, x=px, y=py, z=NUT_Z)
    return out
