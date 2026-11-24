"""Fixed dimensions of the seven-segment display model.

Own copy of the constants of decad-gallery models/sevensegment (params.go, cams.go, shaft.go, frame.go). Names are the
Go names in UPPER_SNAKE_CASE. Lengths are mm, angles degrees. The model frame has its origin under the digit's centre,
+Z up, +Y toward the top of the digit (segment a) and -Y toward the button; the shaft axis is the line x = 0,
z = SHAFT_Z along +Y.
"""

from __future__ import annotations

# The gallery has no Scale constant any more: every shape is written in mm at the size of the earlier builds times 1.5,
# and fits, clearances, print limits, whole-layer plate thicknesses and purchased hardware are separate terms in mm
# (gallery params.go, instructions.md "Scale").

# Fits (mm).
SEAM = 0.25
PRESS_FIT = 0.05
TIGHT_FIT = 0.25
REGULAR_FIT = 0.40
LOOSE_FIT = 0.55

SEGMENT_SPAN = 49.5
TRAVEL = 4.5
SHAFT_Z = 44.25
STATION_PITCH = 16.5
CAM_RADIUS = 35.25
CAM_THICKNESS = 5.7
HUB_RADIUS = 7.5
OFF_RADIUS = 24.75
ON_RADIUS = 29.25
PIN_RADIUS = 2.25  # the slider's groove pin
GROOVE_WIDTH = 2 * PIN_RADIUS + 0.8  # the groove pin's diameter plus a 0.8 fit
GROOVE_DEPTH = 2.85
RAMP_START = 8.0  # degrees
RAMP_END = 29.5
RAMP_ROUND = 3.75
ENTRY_ANGLE = 18.0
PIN_LENGTH = 3.0  # 2.85 groove depth + 0.15 end gap
STEM_THICKNESS = 5.4
WALL_THICKNESS = 12.0
WALL_HALF_WIDTH = 35.1
CLICKER_STEP = 36.0

# The flag mechanism (params.go, flagframe.go).
CRADLE_FROM = 120.0
CRADLE_THICK = 4.0  # 20 layers: the seam plane carries the rotor axes; whole layers
TOP_FROM = CRADLE_FROM + CRADLE_THICK + SEAM
TOP_THICK = 8.0  # 40 layers; whole layers
FACE_Z = TOP_FROM + TOP_THICK  # the display face
ROTOR_AXIS_Z = CRADLE_FROM + CRADLE_THICK  # modeled height of every rotor axis: the seam plane
ROTOR_HALF_WIDTH = 5.625  # distance of a rotor face from its axis
ROTOR_HALF_LENGTH = 18.375
PIVOT_PIN_RADIUS = 0.7  # option B: diameter 1.4
JOURNAL_RADIUS = PIVOT_PIN_RADIUS + 0.2  # the rotor's end bore; the pivot pin turns in it with 0.2 to spare
PIN_OFFSET = 2.25  # distance of the slider pin line from the rotor axis, along the rotor's x
FLAG_PIN_RADIUS = 0.75  # the rotor pin
REAR_COLLAR_RADIUS = 5.7

# Cam (cams.go).
SHAFT_CAM_RADIUS = 4.8  # cam section
SHAFT_CAM_FLAT = 4.05  # cam section flat, from the axis
CAM_BORE_RADIUS = SHAFT_CAM_RADIUS + PRESS_FIT  # D bore
CAM_BORE_FLAT = SHAFT_CAM_FLAT + PRESS_FIT
CAM_HUB_TOP = STATION_PITCH - CAM_THICKNESS - 0.05  # hub end, local z: 0.05 short of the next cam's back face
CAM_ROUND = 0.5  # hub root round
CAM_CHAMFER = 0.5  # rim chamfer
CAM_MARK_RADIUS = 0.75  # look-alike hole radius
CAM_MARK_STEP = 25.0  # degrees between marks
CAM_MARK_FIRST = 270.0
CHANNEL_CAP = CAM_RADIUS + 1.0  # entry channel cap line, outside the rim so the channel opens through it
STATION_FACE = STEM_THICKNESS / 2 + LOOSE_FIT  # a cam's groove face lies this far in +Y from its station
ROUND_CHORDS = 8  # chords in the hub root round
INSCRIPTION_STROKE = 0.9
INSCRIPTION_WIDTH = 4.8
INSCRIPTION_HEIGHT = 6.9
INSCRIPTION_DEPTH = 0.5
INSCRIPTION_RADIUS = 21.0  # the letter's centre from the cam axis, straight up (local +Y)

# Walls (frame.go).
FRONT_INNER_Y = -74.25
REAR_INNER_Y = 64.5
FRONT_WALL_OUTER_Y = FRONT_INNER_Y - WALL_THICKNESS  # the click indexer's offsets start here: its size is fixed
GUIDE_FROM = 81.0  # the guide plate: z 81 to 87
GUIDE_THICK = 6.0
GUIDE_TOP = GUIDE_FROM + GUIDE_THICK
RIB_HEIGHT = 6.0
RIB_DEPTH = 15.0
LEDGE_FROM = GUIDE_FROM - SEAM - RIB_HEIGHT  # the guide plate stands on it over a seam
FLANGE_FROM = CRADLE_FROM - SEAM - RIB_HEIGHT  # the cradle plate stands on it over a seam
WALL_TOP_Z = FLANGE_FROM + RIB_HEIGHT + 1.5  # z of the wall's upper edge: ribs end 1.5 below it
WALL_HALF = WALL_HALF_WIDTH + 1.5
WALL_BOTTOM_Z = SHAFT_Z - CAM_RADIUS - 4.5  # 4.5 below the cams' rims
RIB_INNER = 24.6  # |x| where a rib starts, inside the nut pockets' flats
FRONT_LEDGE_DEEP = -47.9 - FRONT_INNER_Y  # -51.3 + 3.4: this far past the G1/G2 head pockets
REAR_LEDGE_DEEP = REAR_INNER_Y - 44.8  # 48.0 - 3.2: rear ledge ribs reach y 44.8, past the G3/G4 head pockets
RIB_ROUND = 0.5
WALL_CHAMFER = 0.5
MARK_RADIUS = 13.5  # look-alike hole circle on the walls: off the housing flange
# 608ZZ (models/ballbearing catalog): bore 8, outside diameter 22, width 7, inner ring face 12. The gallery pins these
# to the catalog by a test (params.go). A catalog has no bore chamfer; the 0.3 that the shaft's steps clear is an
# assumption.
BEARING_BORE_R = 4.0  # half the bore: the shaft's journals
BEARING_BORE = 2 * BEARING_BORE_R
BEARING_OUTER = 22.0
BEARING_WIDTH = 7.0
BEARING_SEAT_R = 11.05  # half the outside diameter plus the 0.05 seat fit
BEARING_RACE_R = 6.0  # half the inner ring's face: the least a collar facing the bearing may reach
BEARING_BORE_CHAMFER = 0.3  # assumed, not in the catalog

# (r, d), d from the wall's inner face along its thickness. The bearing's seat, lip and lead-ins belong to the purchased
# bearing and keep their size; the lip hole stands 0.5 outside the inner ring's face and ends at the outer face.
SEAT_MERIDIAN: tuple[tuple[float, float], ...] = (
    (0.0, -1.0), (BEARING_SEAT_R + 0.5, -1.0), (BEARING_SEAT_R + 0.5, 0.0), (BEARING_SEAT_R, 0.5),
    (BEARING_SEAT_R, BEARING_WIDTH), (BEARING_RACE_R + 0.5, BEARING_WIDTH),
    (BEARING_RACE_R + 0.5, WALL_THICKNESS - 0.5),
    (BEARING_RACE_R + 1.0, WALL_THICKNESS), (BEARING_RACE_R + 1.0, WALL_THICKNESS + 1.0), (0.0, WALL_THICKNESS + 1.0),
)

# Shaft (shaft.go).
SHAFT_JOURNAL = BEARING_BORE_R  # the journals: half the bearing's bore, fixed by the hardware
SHAFT_STUB_RADIUS = 2.5  # knob stub: the click indexer's size, as the spring fits round it
SHAFT_STUB_FLAT = 2.0
SHAFT_CAM_FROM = FRONT_INNER_Y + 0.25  # the cam section starts 0.25 inside the front wall
SHAFT_CAM_END = SEGMENT_SPAN + STATION_FACE + CAM_THICKNESS + LOOSE_FIT  # the last cam's back face and a Loose gap
SHAFT_REAR_FROM = REAR_INNER_Y - 0.25  # the rear collar ends 0.25 inside the rear wall
SHAFT_FRONT_END = FRONT_WALL_OUTER_Y - 14.7  # the knob end
SHAFT_STUB_STEP_FROM = FRONT_INNER_Y - BEARING_WIDTH - 0.25  # the stub's cone starts 0.25 outside the front bearing
SHAFT_STUB_STEP_TO = SHAFT_STUB_STEP_FROM - 2.6  # 30 degrees or less over the 1.5 step
SHAFT_CAM_FLAT_FROM = SHAFT_CAM_FROM - 1.0
SHAFT_CAM_FLAT_TO = SHAFT_CAM_END - 0.5
SHAFT_STUB_FLAT_FROM = SHAFT_FRONT_END - 1.0
SHAFT_STUB_FLAT_TO = FRONT_WALL_OUTER_Y - 0.35
SHAFT_FLAT_HALF = 6.0  # half the flat tool's width along the shaft's local y
SHAFT_FLAT_REACH = 12.0  # the flat tool's far side along x
# (r, z) with z = world Y. The journals are the bearings' size, 7 wide. The knob stub steps down to the click indexer's
# size inside the front wall's lip hole.
SHAFT_MERIDIAN: tuple[tuple[float, float], ...] = (
    (0.0, SHAFT_FRONT_END), (SHAFT_STUB_RADIUS - 0.3, SHAFT_FRONT_END), (SHAFT_STUB_RADIUS, SHAFT_FRONT_END + 0.3),
    (SHAFT_STUB_RADIUS, SHAFT_STUB_STEP_TO), (SHAFT_JOURNAL, SHAFT_STUB_STEP_FROM), (SHAFT_JOURNAL, SHAFT_CAM_FROM),
    (SHAFT_CAM_RADIUS, SHAFT_CAM_FROM), (SHAFT_CAM_RADIUS, SHAFT_CAM_END),
    (REAR_COLLAR_RADIUS, SHAFT_CAM_END + 1.5585), (REAR_COLLAR_RADIUS, SHAFT_REAR_FROM),
    (SHAFT_JOURNAL, SHAFT_REAR_FROM), (SHAFT_JOURNAL, REAR_INNER_Y + BEARING_WIDTH - 0.3),
    (SHAFT_JOURNAL - 0.3, REAR_INNER_Y + BEARING_WIDTH), (0.0, REAR_INNER_Y + BEARING_WIDTH),
)

FRAME_BOLT_X = WALL_HALF_WIDTH - 3.8  # |x| of the T and G bolts

# Housing base (clicker.go): the H bolts' heads sink in the housing's base, 6.0 thick, on the front wall's outer face.
HOUSING_BASE_Y = FRONT_WALL_OUTER_Y - 0.25
HOUSING_BASE_THICK = 6.0
