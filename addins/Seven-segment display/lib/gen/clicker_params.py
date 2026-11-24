"""Dimensions, sections and frames of the click indexer: hub, rotor, housing, button and spring.

Own copy of decad-gallery models/sevensegment clicker.go. Lengths are mm, angles degrees. The box stands on its back
wall, so model -Y points up and the indexer's parts stack along -Y from the front wall. Every part is built in a local
frame whose Z is the shaft axis (`fup_axes`: local +Z = world -Y; `fdown_axes`: local +Z = world +Y), so a part's local
z is its height above its reference plane.
"""

from __future__ import annotations

import math

from . import frames, poses
from .constants import FRONT_WALL_OUTER_Y, HOUSING_BASE_THICK, HOUSING_BASE_Y, SHAFT_Z  # noqa: F401
from .curves import Arc, Line, Loop, Point
from .sections import polygon_loop

# The click indexer is bought hardware (its spring) and a size set by the hand, so its size is fixed: every Y is an
# offset from the front wall's outer face (FRONT_WALL_OUTER_Y, -86.25).
# Keyed hub: pressed on the stub's D flat. A cup whose wall carries the keys of the rotor's skirt.
HUB_BASE_Y = FRONT_WALL_OUTER_Y - 0.4
HUB_BASE_LENGTH = 3.5
HUB_RIM_Y = FRONT_WALL_OUTER_Y - 9.8  # the rotor's lower stop, 0.1 short of its plate at the full 2.0 drop
HUB_RADIUS = 10.5
HUB_WALL_INNER = 9.0
HUB_KEY_INNER = 8.05
HUB_KEY_WIDTH = 2.0
HUB_KEY_COUNT = 3
HUB_SPRING_FLOOR = HUB_BASE_Y - HUB_BASE_LENGTH  # y of the base's top face, where the spring stands
BORE_STUB_RADIUS = 2.55  # the hub's D bore (shaft.go boreStubRadius, boreStubFlat)
BORE_STUB_FLAT = 2.05

# Rotor: skirt keyed in the hub, a plate with the inner teeth that meet the button and the outer teeth that lock in the
# fixed crown. Local z is the height above the plate's nominal top face at ROTOR_PLATE_Y.
ROTOR_PLATE_Y = FRONT_WALL_OUTER_Y - 13.4
ROTOR_PLATE_THICK = 1.5
ROTOR_PLATE_RADIUS = 14.2
ROTOR_BORE_RADIUS = 3.0
ROTOR_SKIRT_INNER = 4.05  # spring outside radius 3.5 plus 0.55, over the Tight 0.2 (a lower limit)
ROTOR_SKIRT_OUTER = 8.45
ROTOR_SKIRT_LENGTH = 5.5
ROTOR_SLOT_FLOOR = 7.85  # radius of a skirt slot's floor
ROTOR_SLOT_WIDTH = HUB_KEY_WIDTH + 2 * 0.2
ROTOR_INNER_R0 = 3.2
ROTOR_INNER_R1 = 11.0
ROTOR_OUTER_R0 = 12.8
ROTOR_OUTER_R1 = 14.0

# Housing: base on the front wall, tube and a bezel, a fixed crown ring that holds the rotor's outer teeth.
# HOUSING_BASE_Y and HOUSING_BASE_THICK: constants.py
HOUSING_BEZEL_Y = FRONT_WALL_OUTER_Y - 21.9  # 21.9 above the wall: the button's head ends flush with it
HOUSING_TUBE_INNER = 14.55
HOUSING_TUBE_OUTER = 16.55
HOUSING_FLANGE_R = 24.8  # base flange: inside the walls (x +-35.1); 1.1 round the H head pockets after the chamfer
HOUSING_CROWN_R0 = 11.55
HOUSING_CROWN_Y = FRONT_WALL_OUTER_Y - 15.0  # underside of the ring, above the crown's teeth
HOUSING_SLOT_OUTER = 12.7
HOUSING_SLOT_WIDTH = 3.0

# Button: head, ten teeth under it, three keys that slide in the housing's slots.
BUTTON_UNDERSIDE_Y = FRONT_WALL_OUTER_Y - 29.4  # 8.0 (TOOTH_HEIGHT) above the rotor teeth tips at rest
BUTTON_HEAD_THICK = 2.5
BUTTON_RADIUS = 11.0
BUTTON_RECESS_R = 3.2
BUTTON_RECESS_DEEP = 1.4
BUTTON_KEY_INNER = 11.4
BUTTON_KEY_OUTER = 12.2
BUTTON_KEY_WIDTH = 2.0
BUTTON_KEY_DROP = 7.8  # a key hangs this far below the head's underside

CHAMFER = 0.5  # "Surface edge finishing": the equal-setback chamfer of a large face's rim

CLICKER_STEPS = 10
CLICKER_STEP = 36.0
RAMP_ANGLE = 32.5
TOOTH_HEIGHT = 8.0
CROWN_HEIGHT = 1.6
CROWN_BACK = 30.0
ROTOR_TRAVEL = 2.0
BUTTON_STROKE = 10.0
SPRING_REST_LENGTH = 8.0

# The purchased spring, KSSC K series 1087 (models/compressionspring KSSC1087).
SPRING_OUTSIDE_DIAMETER = 7.0
SPRING_WIRE_DIAMETER = 0.60
SPRING_FREE_LENGTH = 14.0
SPRING_TOTAL_TURNS = 6.5
SPRING_SOLID_HEIGHT = 4.5

_ORIGIN: Point = (0.0, 0.0)


def fup_axes(y0: float) -> frames.Axes:
    """[fUp, frontFrame] Frame at world Y y0 on the shaft axis: U = +X, V = +Z, N = -Y. Local +Z is world -Y (up)."""
    return ((0.0, y0, SHAFT_Z), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))


def fdown_axes(y0: float) -> frames.Axes:
    """[fDown] Frame at world Y y0 on the shaft axis: U = +Z, V = +X, N = +Y. Local +Z is world +Y (toward the wall)."""
    return ((0.0, y0, SHAFT_Z), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def hub_axes(theta: float) -> frames.Axes:
    """The hub's frame, turned with the shaft by theta."""
    return frames.compose(poses.turn_axes(theta), fup_axes(HUB_BASE_Y))


def rotor_axes(theta: float) -> frames.Axes:
    return frames.compose(poses.turn_axes(theta), fup_axes(ROTOR_PLATE_Y))


def spring_axes(theta: float) -> frames.Axes:
    """The spring's frame: local z = 0 is the first wire centre, half a wire above the hub's top face."""
    return frames.compose(poses.turn_axes(theta), fup_axes(HUB_SPRING_FLOOR - SPRING_WIRE_DIAMETER / 2))


def housing_axes() -> frames.Axes:
    """The housing's frame (it does not turn): local z = 0 is the crown ring's underside, valley plane of its teeth."""
    return fdown_axes(HOUSING_CROWN_Y)


def button_axes() -> frames.Axes:
    """The button's frame (it does not turn): local z = 0 is the head's underside."""
    return fdown_axes(BUTTON_UNDERSIDE_Y)


def hub_top() -> float:
    """Height of the hub's rim over its base's underside."""
    return HUB_BASE_Y - HUB_RIM_Y


def hub_meridian() -> Loop:
    """The hub's (r, z) section: the base with the cup wall on it, solid to the axis (the D bore is cut later)."""
    top = hub_top()
    return polygon_loop([(0.0, 0.0), (HUB_RADIUS, 0.0), (HUB_RADIUS, top), (HUB_WALL_INNER, top),
                         (HUB_WALL_INNER, HUB_BASE_LENGTH), (0.0, HUB_BASE_LENGTH)])


def hub_key_span() -> tuple[float, float]:
    """The hub keys' local z from and to: from 0.5 inside the base's top face to the rim."""
    return (HUB_BASE_LENGTH - 0.5, hub_top())


def key_angle(k: int, count: int = HUB_KEY_COUNT) -> float:
    """The angle of key or slot k about the shaft axis, degrees."""
    return 360.0 / count * k


def radial_box_loop(r0: float, r1: float, w: float, angle: float) -> Loop:
    """The rectangle from radius r0 to r1 on the +X axis, w wide, turned counterclockwise by angle degrees about the
    origin [localBox]. The corners are rotated here, so no turn feature is needed."""
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    corners = [(r0, -w / 2), (r1, -w / 2), (r1, w / 2), (r0, w / 2)]
    pts = [(round(x * c - y * s, 9), round(x * s + y * c, 9)) for x, y in corners]
    return polygon_loop(pts)


def d_bore_loop(rb: float, fb: float) -> Loop:
    """[dBoreLoop] An arc of radius rb the long way round through -V, closed by its flat at v = +fb. In the part's
    frame V is world +Z, the side the shaft's stub flat is on at digit 0."""
    w = math.sqrt(rb * rb - fb * fb)
    q1, q2 = (-w, fb), (w, fb)
    return [Arc(_ORIGIN, q1, q2), Line(q2, q1)]


def rotor_skirt_top() -> float:
    return -ROTOR_PLATE_THICK


def rotor_meridian(root: float) -> Loop:
    """The rotor's (r, z) section: bore, skirt and plate, the plate's top one root land (`root`) over the nominal top."""
    top = rotor_skirt_top()
    bottom = top - ROTOR_SKIRT_LENGTH
    return polygon_loop([
        (ROTOR_BORE_RADIUS, top), (ROTOR_SKIRT_INNER, top), (ROTOR_SKIRT_INNER, bottom),
        (ROTOR_SKIRT_OUTER, bottom), (ROTOR_SKIRT_OUTER, top), (ROTOR_PLATE_RADIUS, top),
        (ROTOR_PLATE_RADIUS, root), (ROTOR_BORE_RADIUS, root),
    ])


def rotor_slot_span() -> tuple[float, float]:
    """The skirt slots' local z from and to."""
    top = rotor_skirt_top()
    return (top - ROTOR_SKIRT_LENGTH - 0.5, top)


def housing_z(y: float) -> float:
    """Height of world Y y toward the wall above the crown's valley plane."""
    return y - HOUSING_CROWN_Y


def housing_meridian(root: float) -> Loop:
    """The housing's (r, z) section with the 0.5 chamfers of the bezel's two rims and the flange's outer rim on both
    faces; the crown ring's underside lies one root land (`root`) over its valley plane."""
    c = CHAMFER
    z_bez = housing_z(HOUSING_BEZEL_Y)
    z_top = housing_z(HOUSING_BASE_Y - HOUSING_BASE_THICK)
    z_bot = housing_z(HOUSING_BASE_Y)
    return polygon_loop([
        (HOUSING_CROWN_R0 + c, z_bez), (HOUSING_TUBE_OUTER - c, z_bez), (HOUSING_TUBE_OUTER, z_bez + c),
        (HOUSING_TUBE_OUTER, z_top), (HOUSING_FLANGE_R - c, z_top), (HOUSING_FLANGE_R, z_top + c),
        (HOUSING_FLANGE_R, z_bot - c), (HOUSING_FLANGE_R - c, z_bot), (HOUSING_TUBE_INNER, z_bot),
        (HOUSING_TUBE_INNER, root), (HOUSING_CROWN_R0, root), (HOUSING_CROWN_R0, z_bez + c),
    ])


def housing_slot_span() -> tuple[float, float]:
    """The housing slots' local z from and to."""
    return (housing_z(HOUSING_BEZEL_Y) - 1.0, 1.0)


def button_meridian(root: float) -> Loop:
    """The button's (r, z) section: the head from z = -2.5, its recess, the head's underside one root land over z = 0."""
    return polygon_loop([
        (0.0, -BUTTON_HEAD_THICK), (BUTTON_RADIUS, -BUTTON_HEAD_THICK), (BUTTON_RADIUS, root),
        (BUTTON_RECESS_R, root), (BUTTON_RECESS_R, root - BUTTON_RECESS_DEEP), (0.0, root - BUTTON_RECESS_DEEP),
    ])


def button_key_boxes() -> list[tuple[float, float, float, float]]:
    """Each key's two boxes (r0, r1, z0, z1): a flange on the head's side and a lug hanging under the head."""
    return [
        (10.0, BUTTON_KEY_OUTER, -BUTTON_HEAD_THICK + 0.3, 0.0),
        (BUTTON_KEY_INNER, BUTTON_KEY_OUTER, -0.3, BUTTON_KEY_DROP),
    ]


def spring_pitch(length: float) -> float:
    """[compressionspring.Build] The pitch at the installed length: (length - wire) / total turns."""
    return (length - SPRING_WIRE_DIAMETER) / SPRING_TOTAL_TURNS


def spring_centre_radius() -> float:
    """The radius of the wire's centreline: (outside diameter - wire) / 2."""
    return (SPRING_OUTSIDE_DIAMETER - SPRING_WIRE_DIAMETER) / 2


def spring_sections(length: float, per_turn: int = 8) -> list[tuple[float, float, float]]:
    """The wire's section centres as (angle, z, radius): the angle in degrees counterclockwise about +Z from 0 to
    360 * turns in steps of 360 / per_turn, z the height over the first centre (pitch * angle / 360), radius the
    centreline's."""
    pitch = spring_pitch(length)
    count = round(SPRING_TOTAL_TURNS * per_turn)
    step = 360.0 / per_turn
    return [(step * i, pitch * step * i / 360.0, spring_centre_radius()) for i in range(count + 1)]
