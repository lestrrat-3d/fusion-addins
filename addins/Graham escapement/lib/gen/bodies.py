"""Body names, part keys and build order.

Own copy of decad-gallery models/escapement build.go (body name constants, slots, buildAll order) at e11a188.
"""

from __future__ import annotations

BACK_PLATE = "Back Plate"
FRONT_PLATE = "Front Plate"
BACK_ESCAPE_BEARING = "Back Escape Bearing"
BACK_PALLET_BEARING = "Back Pallet Bearing"
BACK_GREAT_WHEEL_BEARING = "Back Great Wheel Bearing"
FRONT_ESCAPE_BEARING = "Front Escape Bearing"
FRONT_PALLET_BEARING = "Front Pallet Bearing"
FRONT_GREAT_WHEEL_BEARING = "Front Great Wheel Bearing"
PENDULUM_BEARING = "Pendulum Bearing"
ESCAPE_ARBOR = "Escape Arbor"
PALLET_ARBOR = "Pallet Arbor"
GREAT_WHEEL_ARBOR = "Great Wheel Arbor"
ESCAPE_WHEEL = "Escape Wheel"
ANCHOR = "Anchor"
CRUTCH = "Crutch"
PENDULUM = "Pendulum"
SUSPENSION_PIN = "Suspension Pin"
SUSPENSION_CAP = "Suspension Cap"
GREAT_WHEEL = "Great Wheel"
PAWL_CARRIER = "Pawl Carrier"
MAINSPRING = "Mainspring"
SPRING_SPACER = "Spring Spacer"
SPRING_ANCHOR_PIN = "Spring Anchor Pin"
WINDING_KNOB = "Winding Knob"
ESCAPE_REAR_COLLAR = "Escape Rear Collar"
PALLET_FRONT_COLLAR = "Pallet Front Collar"
CRUTCH_COLLAR = "Crutch Collar"
KNOB_COLLAR = "Knob Collar"

BEARING_NAMES: tuple[str, ...] = (
    BACK_ESCAPE_BEARING,
    BACK_PALLET_BEARING,
    BACK_GREAT_WHEEL_BEARING,
    FRONT_ESCAPE_BEARING,
    FRONT_PALLET_BEARING,
    FRONT_GREAT_WHEEL_BEARING,
    PENDULUM_BEARING,
)
COLLAR_NAMES: tuple[str, ...] = (ESCAPE_REAR_COLLAR, PALLET_FRONT_COLLAR, CRUTCH_COLLAR, KNOB_COLLAR)
BOLT_NAMES: tuple[str, ...] = tuple(f"Bolt {i}" for i in range(1, 5))
NUT_NAMES: tuple[str, ...] = tuple(f"Nut {i}" for i in range(1, 5))

# Bodies table order of instructions.md "Bodies and containers".
BODY_NAMES: tuple[str, ...] = (
    (BACK_PLATE, FRONT_PLATE)
    + BEARING_NAMES
    + (ESCAPE_ARBOR, PALLET_ARBOR, GREAT_WHEEL_ARBOR, ESCAPE_WHEEL, ANCHOR, CRUTCH, PENDULUM)
    + (SUSPENSION_PIN, SUSPENSION_CAP, GREAT_WHEEL, PAWL_CARRIER, MAINSPRING, SPRING_SPACER)
    + (SPRING_ANCHOR_PIN, WINDING_KNOB)
    + COLLAR_NAMES
    + BOLT_NAMES
    + NUT_NAMES
)
EXPECTED_BODY_COUNT = 36

# Build order of buildAll: one entry per part key.
PARTS: tuple[str, ...] = (
    "back_plate",
    "front_plate",
    "escape_arbor",
    "pallet_arbor",
    "great_wheel_arbor",
    "suspension_pin",
    "escape_wheel",
    "anchor",
    "crutch",
    "pendulum",
    "suspension_cap",
    "great_wheel",
    "pawl_carrier",
    "mainspring",
    "spring_spacer",
    "spring_anchor_pin",
    "winding_knob",
    "arbor_collar",
    "end_collar",
    "bearing",
    "bolt",
    "nut",
)

PART_BODIES: dict[str, tuple[str, ...]] = {
    "back_plate": (BACK_PLATE,),
    "front_plate": (FRONT_PLATE,),
    "escape_arbor": (ESCAPE_ARBOR,),
    "pallet_arbor": (PALLET_ARBOR,),
    "great_wheel_arbor": (GREAT_WHEEL_ARBOR,),
    "suspension_pin": (SUSPENSION_PIN,),
    "escape_wheel": (ESCAPE_WHEEL,),
    "anchor": (ANCHOR,),
    "crutch": (CRUTCH,),
    "pendulum": (PENDULUM,),
    "suspension_cap": (SUSPENSION_CAP,),
    "great_wheel": (GREAT_WHEEL,),
    "pawl_carrier": (PAWL_CARRIER,),
    "mainspring": (MAINSPRING,),
    "spring_spacer": (SPRING_SPACER,),
    "spring_anchor_pin": (SPRING_ANCHOR_PIN,),
    "winding_knob": (WINDING_KNOB,),
    "arbor_collar": (ESCAPE_REAR_COLLAR, PALLET_FRONT_COLLAR),
    "end_collar": (CRUTCH_COLLAR, KNOB_COLLAR),
    "bearing": BEARING_NAMES,
    "bolt": BOLT_NAMES,
    "nut": NUT_NAMES,
}

_PART_OF: dict[str, str] = {name: part for part, names in PART_BODIES.items() for name in names}


def part_of(body_name: str) -> str:
    """Part key of a body name. Raises KeyError for an unknown name."""
    return _PART_OF[body_name]
