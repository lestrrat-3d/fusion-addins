"""Fixed dimensions of the one-way clutch, in mm, in the local frame.

Own copy of the constants of decad-gallery models/onewayclutch params.go. A fit gap is its class minimum plus
FIT_MARGIN.
"""

from __future__ import annotations

FIT_MARGIN = 0.05
TIGHT_FIT = 0.2 + FIT_MARGIN  # 0.25: the hub to each plate boss
REGULAR_FIT = 0.35 + FIT_MARGIN  # 0.40: the head to its tooth gap
LOOSE_FIT = 0.5 + FIT_MARGIN  # 0.55: the arm to the tooth tips

PAWLS = 3  # pawls on the hub, 120 degrees apart
TEETH = 18  # internal teeth of the ring, 20 degrees apart

ROOT_ROUND = 0.8
RING_CHAMFER = 0.5

EARS = 3
EAR_RADIUS = 4.1
EAR_ROUND = 1.5
TOOTH_END_GAP = 0.85
EAR_ANGLES = (90.0, 210.0, 330.0)  # degrees; symmetric about x = 0, so the same in both directions

MIN_ARM_THICKNESS = 1.5  # least arm thickness that prints reliably
ARM_THICKNESS = 1.5

WEB_ANGLE = -20.0  # degrees: pawl 0's web back face
SLOT_ANGLE = -6.0  # degrees: pawl 0's slot end
LOCK_ANGLE = 90.0  # degrees: the ring lock face pawl 0 sits against
WEB_ROUND = 1.0
TIP_ROUND = 0.4
HEAD_GAP = REGULAR_FIT

HUB_HEIGHT = 10.0
SEAM = TIGHT_FIT

RECESS = REGULAR_FIT
BACK_PLATE_THICKNESS = 4.0
COVER_THICKNESS = 4.0
PLATE_CHAMFER = 0.5

BOLT_ANGLES = (30.0, 150.0, 270.0)  # degrees
BOLT_LENGTH = 16.0
PRESS_WALL = 1.6

# The rules that grow the radii with the shaft's bore radius (params.go; Dimensions holds the radii, validate.derive).
BASE_CORE_RADIUS = 10.1  # least hub core radius
WALL_MARGIN = FIT_MARGIN  # modeled margin over PRESS_WALL, so a section reads PRESS_WALL or more
BOLT_WALL = PRESS_WALL + WALL_MARGIN  # modeled wall each side of a bolt hole and pocket
MIN_SLOT_WIDTH = 1.6  # least slot under an arm
MIN_SLOT_MARGIN = 0.33  # least SlotWidth - HeadTravel
TOOTH_DEPTH = 2.35  # ToothRoot - ToothTip
COUNTER_STEP = 1.0  # RingCounter - ToothRoot (the 45 degree cone)
RING_WALL = 2.0  # RingOuter - RingCounter
EAR_OFFSET = 2.5  # EarCircle - RingOuter
BOSS_STEP = 0.3  # BossRadius - CoreRadius
MAX_HUB_CHAMFER = 0.25  # the hub's face chamfer, unless the head flank caps it lower
HUB_CHAMFER_MARGIN = 0.01  # least gap between the hub chamfer and its cap ArmOuter - FlankDistance
ADAPTER_SHAFT_GAP = 1.0  # radial gap from the shaft to the adapter bore

HUB_FROM = BACK_PLATE_THICKNESS + SEAM  # 4.25
COVER_FROM = HUB_FROM + HUB_HEIGHT + SEAM  # 14.5
COVER_TO = COVER_FROM + COVER_THICKNESS  # 18.5
END_STANDOFF = TOOTH_END_GAP + REGULAR_FIT  # 1.25
RING_FROM = -END_STANDOFF
RING_TO = COVER_TO + END_STANDOFF  # 19.75
RING_HEIGHT = RING_TO - RING_FROM  # 21
BAND_FROM = BACK_PLATE_THICKNESS - RECESS + TOOTH_END_GAP  # 4.45
BAND_TO = COVER_FROM + RECESS - TOOTH_END_GAP  # 14.05

ADAPTER_FROM = RING_TO + SEAM  # 20.0
ADAPTER_THICKNESS = 6.0
ADAPTER_TO = ADAPTER_FROM + ADAPTER_THICKNESS  # 26.0
MOUNT_LENGTH = 25.0
FACE_CIRCLE = 9.5
FACE_LENGTH = 10.0
FACE_NUT_DEPTH = 1.5

# Input rules (params.go Derive).
BORE_CLEARANCE_MIN = 0.05  # ballbearing.PressFitClearance
BORE_CLEARANCE_MAX = 0.5
# The chamfer rule of the plates' and the hub's D loop (instructions.md, "Surface edge finishing").
CHAMFER_LOOP_MIN = 20.0  # mm: a loop of this length or more takes the chamfer
