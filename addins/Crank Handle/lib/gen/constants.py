"""Fixed dimensions of the crank handle model.

Own copy of the constants of decad-gallery models/crankhandle (params.go). Names are the Go names in UPPER_SNAKE_CASE.
Lengths are mm, angles are degrees where the name says so. The local frame has its origin on the shaft axis in the
arm's back face, +Z along the shaft away from the mechanism, the arm along +Y to the pin axis at (0, throw).
"""

from __future__ import annotations

FIT_MARGIN = 0.05
TIGHT_FIT = 0.2 + FIT_MARGIN  # the pin's stub in the arm's hexagonal pocket
REGULAR_FIT = 0.35 + FIT_MARGIN  # the handle on the pin's shank, and its gap to the arm

ARM_RADIUS = 10.0  # the arm is 20 wide: its sides run at x = +-ARM_RADIUS
ARM_THICKNESS = 8.0
HUB_LENGTH = 17.0  # the arm's back face to the boss top; the boss rises from the outer face under the bore
RAMP_ANGLE = 30.0  # degrees, the ramp from the boss top down to the outer face
BORE_FLOOR = 1.0  # the D bore is blind: 1 mm of arm closes it at the front face
PIN_HOLE_R = 1.3  # the pin bolt's clearance hole through the arm
STUB_FLATS = 7.03
POCKET_FLATS = STUB_FLATS + 2 * TIGHT_FIT
POCKET_FROM = 3.25  # the hexagonal pocket runs from here through the front face
POCKET_LENGTH = 5.75
STUB_FROM = 3.5
STUB_LENGTH = 5.8
SHANK_R = 5.15
SHANK_FROM = 8.25  # the root cone starts here at radius ROOT_R, inside the stub
ROOT_R = 3.5
SHANK_TO = 52.75
HEAD_R = 6.45
HEAD_FROM = 55.0  # the head cone runs from SHANK_TO up to here
HEAD_LENGTH = 3.0
HANDLE_FROM = 7.4  # the handle sketch's origin, 1 behind the handle's inner end
PIN_BOLT = 10.0
PIN_CAVITY = 4.75  # from the bolt head's top face to the nut cavity's near face
PRESS_WALL = 1.6
REGULAR_FIT = 0.40  # the least wall round a press-fit bore
CHAMFER_SIZE = 0.5  # the arm's face chamfer
CROSS_BOLT = 6.0
CROSS_FLAT = 4.0  # the pin's double flats' distance from the pin axis
CROSS_FLAT_HALF = 3.25  # half the flats' length along the pin
CROSS_CAVITY = 6.0
CONE_ANGLE = 30.0  # degrees, half angle of the pin's cones
CLAMP_BOLT = 16.0
CLAMP_HOLE_WALL = 1.05
CLAMP_SIDE_RUN = 3.6
CLAMP_CORNER_R = 4.5
CLAMP_END_R = 22.0
SLIT_WIDTH = 1.5
SLIT_IN_BORE = 1.0
NUT_POCKET_ROUND = 0.6
BORE_CLEARANCE_MIN = 0.05  # ballbearing.PressFitClearance
BORE_CLEARANCE_MAX = 0.5

# The clamp bolts' distances along the shaft from the arm's back face: 4 mm above it, and 4 mm below the bore's floor.
CLAMP_Z = (4.0, 12.0)

# The cross bolts' distances along the pin from the arm's back face.
CROSS_Z = (17.0, 49.0)

# The handle's meridian: (distance along the pin from HANDLE_FROM, radius).
HANDLE_PROFILE = (
    (1.5, 5.55), (45.24, 5.55), (47.84, 7.05), (50.5, 7.05), (51.0, 7.55), (51.0, 8.3), (49.8, 9.3),
    (44.0, 8.0), (37.0, 7.25), (23.0, 8.0), (9.0, 7.8), (2.2, 7.2), (1.0, 6.6), (1.0, 6.05),
)
