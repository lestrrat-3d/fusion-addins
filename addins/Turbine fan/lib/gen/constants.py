"""Fixed dimensions of the turbine fan model.

Own copy of the constants of decad-gallery models/turbinefan (params.go, blade.go) and of the values it reads from
models/crankhandle and models/onewayclutch. Names are the Go names in UPPER_SNAKE_CASE. Lengths are mm, angles are
radians unless the name says degrees. The local frame has its origin on the shaft axis in the hub's back face, +Z along
the shaft away from the mechanism to the front face at z = Size.hub_length, and blade 1 along +Y.
"""

from __future__ import annotations

import math

BLADE_COUNT = 3

# The rotor size limits and the scale constants (size.go); the sizes themselves are Size fields (size.py).
BASE_ROTOR_DIAMETER = 128.0  # the size the blade station table is written for
DEFAULT_ROTOR_DIAMETER = 192.0
MIN_ROTOR_DIAMETER = 128.0
MAX_ROTOR_DIAMETER = 224.0
BASE_HUB_RADIUS = 14.0
# MAX_HUB_RADIUS keeps the hub rim HEAD_POCKET_RADIUS + 0.5 inside the 605ZZ clutch's ear circle (21.6), so the ear
# bolts' heads and a 1.5 mm hex key pass the hub to the adapter's ear pockets. One hub serves both mounts.
MAX_HUB_RADIUS = 18.9
BLADE_BOLT_TIP_FLOOR = 2.0  # the least height of a blade bolt's tip above the back face
FIRST_BLADE_ANGLE = math.pi / 2  # blade 1 along +Y; the set screw lies along -Y, midway between blades 2 and 3

SET_SCREW_Z = 4.0  # the set screw's line along the shaft
SET_SCREW_TRAVEL = 0.4  # gap under the head
COUNTERBORE_ROUND = 0.5
NUT_SLOT_ROUND = 0.5

# models/crankhandle
FIT_MARGIN = 0.05
REGULAR_FIT = 0.35 + FIT_MARGIN  # the stud in its socket
CHAMFER_SIZE = 0.5  # the hub's face chamfer
PRESS_WALL = 1.6  # the least wall round a press-fit bore
BORE_CLEARANCE_MIN = 0.05  # ballbearing.PressFitClearance
BORE_CLEARANCE_MAX = 0.5

# Blade and joint.
BLADE_SOCKET_FLOOR_ROUND = 0.5
STUD_CHAMFER = 0.3  # on the stud's inner end

REF_PITCH = math.radians(25)  # the pitch the sections are drawn at
DEFAULT_BLADE_PITCH = REF_PITCH
MIN_BLADE_PITCH = math.radians(10)
MAX_BLADE_PITCH = math.radians(40)
DESIGN_ATTACK = math.radians(5)
CAMBER_AT = 0.40  # chord fraction of the maximum camber
EDGE_THICK = 1.0  # trailing-edge thickness
SIDE_POINTS = 10  # fit points per surface, besides the leading edge

# models/onewayclutch, as the clutch mount reads them.
# ClutchTurn is pi: the fan hub's D-bore flat (at -Y in the fan frame) points the way the clutch's shaft flat does (+Y in
# the clutch frame). Every ear bolt lies midway between two blades, because the blades, ear bolts and face holes all
# repeat every 120 degrees.
CLUTCH_TURN = math.pi  # the fan frame's turn about Z from the clutch frame
CLUTCH_SEAM = 0.25
ADAPTER_THICKNESS = 6.0
FACE_CIRCLE = 9.5  # the adapter's face holes' circle
FACE_LENGTH = 10.0  # the adapter bolts' M2 length
FACE_NUT_DEPTH = 1.5
ADAPTER_TO = 26.0  # onewayclutch.AdapterTo: the adapter's front face, in the clutch frame
MOUNT_Z = ADAPTER_TO + CLUTCH_SEAM  # 26.25: the fan frame's origin in the clutch frame
EAR_ANGLES_DEGREES = (90.0, 210.0, 330.0)

# The two hands and the two mounts, as the dialog's integers.
RIGHT_HAND = 0
LEFT_HAND = 1
SHAFT_MOUNT = 0
CLUTCH_MOUNT = 1

TOP_RADIUS_LIMIT = 64.5  # every blade point lies within this radius of the shaft axis
