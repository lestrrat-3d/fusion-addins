"""Face teeth of the click indexer: rings of ten sawtooth teeth whose ramps are helicoids about the shaft axis.

Own copy of decad-gallery models/sevensegment facetooth.go and the tooth specs of clicker.go, and of
clicker_motion.go's PressTurn. Angles are in the part's local frame (counterclockwise about +Z), heights are the local z.

# Deviation (docs/sevensegment/deviations.md, "Click indexer"): decad builds a ramp as a `Coil` cut. Fusion has
no coil feature an add-in can create, so a tooth is the intersection of two twisted prisms, each a sector swept along
the shaft axis with a twist. A horizontal slice of such a prism is the sector turned by the twist at that height, so
the prism's side wall is a helicoid, exactly the Coil's ramp. One prism's wall is the rising ramp and the other's the
falling ramp.
"""

from __future__ import annotations

import dataclasses
import math

from . import clicker_params as cp
from .curves import Arc, Line, Loop, Point

# The sector of each prism spans this many degrees at its start, more than a tooth's 36 so its far edge never clips.
SECTOR_SPAN = 40.0


@dataclasses.dataclass(frozen=True)
class FaceTeeth:
    """Ten teeth. Tooth k rises from its sharp valley at 36k (height 0) over `rise` degrees to its peak `h`, then falls
    over `fall` degrees to the next valley. `rise + fall` is 36."""

    name: str
    r0: float
    r1: float
    h: float
    rise: float
    fall: float
    tip: float = 0.05  # the peak is cut back by this much: the tip's land
    plate: float = 0.03  # height of the plate's top over the sharp valley under these teeth: the root land

    @property
    def top(self) -> float:
        """The tooth's height: the peak less the tip's land."""
        return self.h - self.tip

    @property
    def rise_twist(self) -> float:
        """The turn, degrees, of the rising ramp's edge over the tooth's height."""
        return self.rise * self.top / self.h

    @property
    def fall_twist(self) -> float:
        """The turn of the falling ramp's edge over the tooth's height (the edge turns back)."""
        return -self.fall * self.top / self.h


def rotor_inner_teeth() -> FaceTeeth:
    return FaceTeeth("rotor inner", cp.ROTOR_INNER_R0, cp.ROTOR_INNER_R1, cp.TOOTH_HEIGHT,
                     cp.CLICKER_STEP - cp.RAMP_ANGLE, cp.RAMP_ANGLE)


def rotor_outer_teeth() -> FaceTeeth:
    return FaceTeeth("rotor outer", cp.ROTOR_OUTER_R0, cp.ROTOR_OUTER_R1, cp.CROWN_HEIGHT, cp.CROWN_BACK,
                     cp.CLICKER_STEP - cp.CROWN_BACK)


def crown_teeth() -> FaceTeeth:
    return FaceTeeth("crown", cp.ROTOR_OUTER_R0, cp.HOUSING_TUBE_INNER + 0.3, cp.CROWN_HEIGHT, cp.CROWN_BACK,
                     cp.CLICKER_STEP - cp.CROWN_BACK)


def button_teeth() -> FaceTeeth:
    return FaceTeeth("button", cp.BUTTON_RECESS_R + 0.2, cp.BUTTON_RADIUS - 0.15, cp.TOOTH_HEIGHT,
                     cp.CLICKER_STEP - cp.RAMP_ANGLE, cp.RAMP_ANGLE)


# The shift of each ring: the turn of tooth 0 so its tips lie where the design puts them in forward angle (clicker.go).
ROTOR_INNER_SHIFT = -(cp.CLICKER_STEP - cp.RAMP_ANGLE)
ROTOR_OUTER_SHIFT = -cp.CROWN_BACK
CROWN_SHIFT = 0.0
BUTTON_SHIFT = cp.CLICKER_STEP - cp.RAMP_ANGLE


def rising_edge(ft: FaceTeeth, shift: float, z: float) -> float:
    """The angle of tooth 0's rising ramp at height z."""
    return shift + ft.rise * z / ft.h


def falling_edge(ft: FaceTeeth, shift: float, z: float) -> float:
    """The angle of tooth 0's falling ramp at height z."""
    return shift + cp.CLICKER_STEP - ft.fall * z / ft.h


def tooth_width(ft: FaceTeeth, z: float) -> float:
    """The angle a tooth spans at height z."""
    return falling_edge(ft, 0.0, z) - rising_edge(ft, 0.0, z)


def sector_loop(r0: float, r1: float, a0: float, a1: float) -> Loop:
    """The annular sector from radius r0 to r1 between the angles a0 and a1 (degrees, a1 - a0 under 360). Each arc is
    stored counterclockwise from a0 to a1, as `curves.Arc` requires."""

    def at(r: float, a: float) -> Point:
        return (round(r * math.cos(math.radians(a)), 9), round(r * math.sin(math.radians(a)), 9))

    o = (0.0, 0.0)
    return [Arc(o, at(r1, a0), at(r1, a1)), Line(at(r1, a1), at(r0, a1)), Arc(o, at(r0, a0), at(r0, a1)),
            Line(at(r0, a0), at(r1, a0))]


def sweeps(ft: FaceTeeth, shift: float) -> tuple[tuple[Loop, float], tuple[Loop, float]]:
    """The two prisms of tooth 0 as (start sector, twist in degrees over `ft.top`). The first holds the rising ramp:
    its start edge is at `shift` and turns by `rise_twist`. The second holds the falling ramp: its end edge is at
    `shift + 36` and turns back by `fall_twist`. Their intersection is the tooth."""
    rising = sector_loop(ft.r0, ft.r1, shift, shift + SECTOR_SPAN)
    falling = sector_loop(ft.r0, ft.r1, shift + cp.CLICKER_STEP - SECTOR_SPAN, shift + cp.CLICKER_STEP)
    return (rising, ft.rise_twist), (falling, ft.fall_twist)


def cap_angle(ft: FaceTeeth, shift: float, rising: bool) -> float:
    """The angle of the centre of a prism's top cap, from the cap's sector: used to check the twist's direction."""
    if rising:
        return shift + ft.rise_twist + SECTOR_SPAN / 2
    return shift + cp.CLICKER_STEP + ft.fall_twist - SECTOR_SPAN / 2


# PressTurn, from clicker_motion.go.
RAMP_RATE = cp.RAMP_ANGLE / cp.TOOTH_HEIGHT  # the rotor's turn per mm of button travel on the ramps


def press_turn() -> float:
    """The shaft's turn at the bottom of a press: the ramp's angle less what the lands take. Each land (the tip's, then
    the root's, or the tip's again when it is wider) costs the ramp's turn over its height."""
    inner, button = rotor_inner_teeth(), button_teeth()
    root = max(inner.tip, button.plate)
    return cp.RAMP_ANGLE - RAMP_RATE * (button.tip + root)
