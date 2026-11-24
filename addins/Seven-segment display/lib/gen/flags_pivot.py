"""Outlines of the printed pivot blocks and of their pockets in the cradle and the top plate.

Own copy of decad-gallery models/sevensegment pivot.go (pivotBlock, roundedPrism, pivotPocketTool, toSegment). A block
is built in its own frame: local x is s (across the rotor), local y is up and local z is u, at the +u end. The -u end
turns the block 180 degrees about local y before it goes onto the rotor's frame. Lengths are mm.
"""

from __future__ import annotations

from . import flags_common as fc
from . import frames
from .constants import CRADLE_THICK, PIVOT_PIN_RADIUS, PRESS_FIT, ROTOR_HALF_LENGTH, SEAM
from .curves import Loop, Point
from .truth import SEGMENTS

# PIVOT_PIN_RADIUS (constants.py): the pin; the rotor's end bore (JOURNAL_RADIUS) leaves 0.2, the Tight minimum
PIVOT_BLOCK_SIDE = 4.8  # the block's width, along s
PIVOT_BLOCK_HIGH = 2 * (CRADLE_THICK - 1.0 - PRESS_FIT)  # along z: 1.0 of cradle stays under its pocket (5.9)
PIVOT_BLOCK_FROM = ROTOR_HALF_LENGTH + 0.25  # the end wall: the block's rotor-side face (0.25 from the rotor's end)
PIVOT_BLOCK_LONG = 3.0
PIVOT_PIN_TIP = PIVOT_BLOCK_FROM - 1.875  # the pin stands 1.875 from the block's face
PIVOT_ROOT_LEG = 0.25  # the pin's 45 degree root cone, inside the end gap
PIVOT_TIP_LEG = 0.1  # the pin's tip chamfer
PIVOT_CORNER_R = 0.675  # the block's rounds
PIVOT_POCKET_R = PIVOT_CORNER_R + PRESS_FIT
PIVOT_POCKET_HALF = PIVOT_BLOCK_SIDE / 2 + PRESS_FIT  # the pocket's half width along s
PIVOT_POCKET_LOW = PIVOT_BLOCK_HIGH / 2 + PRESS_FIT  # the pocket's floor, below the axis: 1.0 of cradle under it
PIVOT_POCKET_HIGH = SEAM + PIVOT_BLOCK_HIGH / 2 + PRESS_FIT  # its roof, above the axis, over the seam

ENDS: tuple[float, float] = (-1.0, 1.0)  # the rotor's -u end then its +u end, as in Parts.PivotBlocks[seg][0..1]

_IDENTITY: fc.Axes = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
_TURN_ABOUT_UP: fc.Axes = ((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0))


def pin_meridian() -> list[Point]:
    """The pin as an (r, z) section, its 45 degree root cone starting inside the block (a cone that starts on the face
    is refused by decad)."""
    leg = PIVOT_ROOT_LEG + 0.1
    f, r = PIVOT_BLOCK_FROM, PIVOT_PIN_RADIUS
    return [(0.0, f + 0.1), (r + leg, f + 0.1), (r, f - PIVOT_ROOT_LEG), (r, PIVOT_PIN_TIP + PIVOT_TIP_LEG),
            (r - PIVOT_TIP_LEG, PIVOT_PIN_TIP), (0.0, PIVOT_PIN_TIP)]


def block_dims() -> tuple[float, float, float, float, float, float]:
    """The block's roundedPrism arguments: half, below, above, rad, u0, u1."""
    return (PIVOT_BLOCK_SIDE / 2, PIVOT_BLOCK_HIGH / 2, PIVOT_BLOCK_HIGH / 2, PIVOT_CORNER_R, PIVOT_BLOCK_FROM,
            PIVOT_BLOCK_FROM + PIVOT_BLOCK_LONG)


def pocket_dims() -> tuple[float, float, float, float, float, float]:
    """The pocket's roundedPrism arguments, from 1 mm inside the bore to 0.05 past the block's outer face."""
    return (PIVOT_POCKET_HALF, PIVOT_POCKET_LOW, PIVOT_POCKET_HIGH, PIVOT_POCKET_R, PIVOT_BLOCK_FROM - 1,
            PIVOT_BLOCK_FROM + PIVOT_BLOCK_LONG + PRESS_FIT)


def rounded_prism_sections(half: float, below: float, above: float, rad: float, u0: float, u1: float):
    """The two prisms whose intersection is a block or a pocket [roundedPrism]. Returns
    ((section outline, frame, start z, length), (plan outline, frame, start z, length)).

    The section prism (a rectangle across the rotor and z, its four long edges rounded) starts at u0; the plan prism (u
    by s, its corners rounded) starts 1 mm before it, so the near rounds lie outside the body and u0 is a plain face."""
    sec: Loop = fc.rect_loop(-half, half, -below, above, rad)
    plan: Loop = fc.rect_loop(u0 - 1, u1, -half, half, rad)
    plan_axes = fc.plane_axes((0.0, -below - 1, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))  # normal +Y
    return (sec, _IDENTITY, u0, u1 - u0 + 1), (plan, plan_axes, 0.0, below + above + 2)


def segment_axes(s: int, sgn: float) -> fc.Axes:
    """The frame that moves a body built at the +u end onto segment s's end sgn at turn 0 [toSegment]."""
    frame = fc.rotor_frame(s)
    return frame if sgn > 0 else frames.compose(frame, _TURN_ABOUT_UP)


def block_bounds(s: int, sgn: float) -> tuple[float, float, float, float, float, float]:
    """The expected bounding box of the block at segment s's end sgn in the model frame: the pin tip to the outer face
    along u, the block's width along s and its height about the axis (rounds and the pin cone stay inside it)."""
    half, below, above, _, _, u1 = block_dims()
    corners = [fc.plan(s, sgn * u, sv) for u in (PIVOT_PIN_TIP, u1) for sv in (-half, half)]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    return (min(xs), min(ys), fc.ROTOR_AXIS_Z - below, max(xs), max(ys), fc.ROTOR_AXIS_Z + above)


ALL_ENDS: tuple[tuple[int, float], ...] = tuple((s, sgn) for s in SEGMENTS for sgn in ENDS)
