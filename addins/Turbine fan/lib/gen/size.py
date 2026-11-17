"""The fan's sizes, which follow the rotor diameter.

Own copy of decad-gallery models/turbinefan size.go (Size, SizeFor, Size.Beta). Lengths are mm.

The blade scale is s = rotor_diameter / 128. Every airfoil section, the hub length, the pitch reference radius and the
hold radius scale by s. The hub radius is 14 s, capped at MAX_HUB_RADIUS, and the round blade root, the stud, the socket
and the blade bolt circle scale by the hub scale j = hub_radius / 14.
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    BASE_HUB_RADIUS,
    BASE_ROTOR_DIAMETER,
    BLADE_BOLT_TIP_FLOOR,
    DESIGN_ATTACK,
    MAX_HUB_RADIUS,
    MAX_ROTOR_DIAMETER,
    MIN_ROTOR_DIAMETER,
    REF_PITCH,
    REGULAR_FIT,
)
from .fasteners import HEAD_POCKET_DEPTH, STANDARD_LENGTHS
from .report import fmt_num


class SizeError(ValueError):
    """The rotor diameter has no valid size; the message is the gallery's without the `turbinefan: ` prefix."""


@dataclasses.dataclass(frozen=True)
class Size:
    rotor_diameter: float
    scale: float  # s: rotor_diameter / BASE_ROTOR_DIAMETER
    hub_scale: float  # j: hub_radius / BASE_HUB_RADIUS
    tip_radius: float  # rotor_diameter / 2
    root_radius: float  # hub_radius + REGULAR_FIT: the blade's root station
    ref_radius: float  # 48 s: the pitch is the blade angle here, 75 % of the tip radius
    hold_radius: float  # 21.5 s: inboard of this the blade angle stays constant
    hub_radius: float  # min(14 s, MAX_HUB_RADIUS)
    hub_length: float  # 20 s
    hub_mid: float  # hub_length / 2: the sockets' and blade bolts' plane
    blade_stud_radius: float  # 3 j
    blade_stud_start: float  # blade_socket_start + REGULAR_FIT
    blade_stud_end: float  # 16 j
    blade_socket_radius: float  # blade_stud_radius + REGULAR_FIT
    blade_socket_start: float  # 5.7 j
    blade_bolt_at: float  # 9.5 j: the blade bolt's distance from the fan axis
    blade_bolt_length: float  # the longest standard length that keeps its tip BLADE_BOLT_TIP_FLOOR above the back face
    blade_bolt_cavity: float  # blade_bolt_length - 0.4

    def beta(self, r: float, pitch: float) -> float:
        """The blade angle at radius r, from the plane of rotation, for a blade angle of `pitch` at ref_radius."""
        return (DESIGN_ATTACK + math.atan(math.tan(REF_PITCH - DESIGN_ATTACK) * self.ref_radius
                                          / max(r, self.hold_radius)) + (pitch - REF_PITCH))


def size_for(rotor_diameter: float) -> Size:
    """The sizes of a rotor of the given diameter [SizeFor]. Raises SizeError for a diameter that is not finite or lies
    outside [MIN_ROTOR_DIAMETER, MAX_ROTOR_DIAMETER], when no standard blade bolt length fits, and when the blade nut
    slot leaves less than 1 mm of hub above the socket."""
    if (math.isnan(rotor_diameter) or math.isinf(rotor_diameter)
            or rotor_diameter < MIN_ROTOR_DIAMETER or rotor_diameter > MAX_ROTOR_DIAMETER):
        raise SizeError(
            f"RotorDiameter must lie in [{fmt_num(MIN_ROTOR_DIAMETER)}, {fmt_num(MAX_ROTOR_DIAMETER)}] mm")
    s = rotor_diameter / BASE_ROTOR_DIAMETER
    hub_radius = min(BASE_HUB_RADIUS * s, MAX_HUB_RADIUS)
    j = hub_radius / BASE_HUB_RADIUS  # computed this way, so the cap is exact
    hub_length = 20 * s
    bolt = 0.0
    for length in STANDARD_LENGTHS:
        if hub_length - HEAD_POCKET_DEPTH - length >= BLADE_BOLT_TIP_FLOOR - 1e-9:
            bolt = length
    if bolt == 0.0:
        raise SizeError("no standard blade bolt length fits the hub")
    stud_radius = 3 * j
    socket_start = 5.7 * j
    sz = Size(
        rotor_diameter=rotor_diameter, scale=s, hub_scale=j, tip_radius=rotor_diameter / 2,
        root_radius=hub_radius + REGULAR_FIT, ref_radius=48 * s, hold_radius=21.5 * s, hub_radius=hub_radius,
        hub_length=hub_length, hub_mid=hub_length / 2, blade_stud_radius=stud_radius,
        blade_stud_start=socket_start + REGULAR_FIT, blade_stud_end=16 * j,
        blade_socket_radius=stud_radius + REGULAR_FIT, blade_socket_start=socket_start, blade_bolt_at=9.5 * j,
        blade_bolt_length=bolt, blade_bolt_cavity=bolt - 0.4,
    )
    if sz.hub_length - sz.blade_bolt_cavity > sz.hub_mid - sz.blade_socket_radius - 1:
        raise SizeError("blade nut slot leaves less than 1 mm of hub above the socket")
    return sz
