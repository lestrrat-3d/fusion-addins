"""Fixed dimensions of the plaque stand, in mm and degrees.

Own copy of the constants of decad-gallery models/plaquestand params.go. Names are the Go names in UPPER_SNAKE_CASE.
The local frame has its origin at the front-bottom corner of bracket 1's outer face: +X runs along the span, +Y from the
front to the back, +Z up, and the base's bottom face is z = 0.
"""

from __future__ import annotations

# Default plaque dimensions: the measured size of the owner's plaque.
DEFAULT_PLAQUE_WIDTH = 250.0
DEFAULT_PLAQUE_HEIGHT = 305.0
DEFAULT_PLAQUE_THICKNESS = 12.8
DEFAULT_RECLINE = 15.0
DEFAULT_LIP_HEIGHT = 10.0

# Fit constants (docs/model-pipeline.md "Part clearances").
LOOSE_FIT = 0.5
FIT_MARGIN = 0.05
DEFAULT_SLOT_CLEARANCE = LOOSE_FIT + FIT_MARGIN

# Limits on the parameters.
MIN_PLAQUE_WIDTH, MAX_PLAQUE_WIDTH = 150.0, 400.0
MIN_PLAQUE_HEIGHT, MAX_PLAQUE_HEIGHT = 120.0, 350.0
MIN_PLAQUE_THICKNESS, MAX_PLAQUE_THICKNESS = 2.0, 15.0
MIN_RECLINE, MAX_RECLINE = 10.0, 25.0
MIN_LIP_HEIGHT, MAX_LIP_HEIGHT = 6.0, 20.0
MIN_SLOT_CLEARANCE, MAX_SLOT_CLEARANCE = LOOSE_FIT + FIT_MARGIN, 1.5

BASE_THICKNESS = 8.0  # T_b
LIP_THICKNESS = 5.0  # L_t
BACK_THICKNESS = 6.0  # B_t
ROOT_RADIUS = 4.0  # r_r
CORNER_RADIUS = 2.0  # r_c
FRONT_FLAT = 5.0  # F

BRACKET_WIDTH = 20.0  # w_b
SPAN_RATIO = 0.8
MIN_SPAN = 120.0

BED_SIZE = 256.0
BED_MARGIN = 5.0
MAX_SPAN = BED_SIZE - 2 * BED_MARGIN
MAX_EXTENT = BED_SIZE - 2 * BED_MARGIN

RAIL_WIDTH = 10.0  # w_r
RAIL_HEIGHT = 4.0  # h_r
RAIL_ROUND = 1.0  # r_q
REGULAR_FIT = 0.35
JOINT_FIT = REGULAR_FIT + FIT_MARGIN  # j: the rail-to-channel gap
CHANNEL_MOUTH_ROUND = 1.0  # r_m
CHANNEL_LAND = 2.0
REAR_LAND = 8.0
BOLT_LENGTH = 6.0
NUT_POCKET_ROUND = 0.6
BACK_HEIGHT_RATIO = 0.2
MIN_BACK_HEIGHT = 30.0
MAX_BACK_HEIGHT = 60.0

MIN_TIP_ANGLE = 15.0  # phi
CHAMFER_SIZE = 0.5  # e
