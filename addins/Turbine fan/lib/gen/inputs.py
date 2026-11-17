"""Dialog input table. Not geometry, but stdlib-only so it stays unit-testable."""

from __future__ import annotations

import dataclasses

from .clutch.params import CLOCKWISE, DIRECTIONS, SHAFTS, Params as ClutchParams
from .constants import CLUTCH_MOUNT, RIGHT_HAND, SHAFT_MOUNT
from .params import Params, params_for_clutch

HANDS: tuple[str, ...] = ("Right hand", "Left hand")
MOUNTS: tuple[str, ...] = ("Shaft", "Clutch")


@dataclasses.dataclass(frozen=True)
class InputSpec:
    id: str
    label: str
    field: str  # the Params field it sets
    default: float | str  # mm; degrees for an angle; the item name for a choice
    kind: str = "length"  # "length" (mm) | "angle" (degrees) | "choice" | "bool" (check box; 0 or 1)
    choices: tuple[str, ...] = ()


# The gallery's Params605ZZ values are the defaults, in the gallery's field order. `Shaft bore diameter` is the D-flat
# shaft's diameter, which the hub's D bore is cut for.
INPUT_SPECS: tuple[InputSpec, ...] = (
    InputSpec("shaft_diameter", "Shaft bore diameter", "shaft_diameter", 5.0),
    InputSpec("flat_depth", "Flat depth", "flat_depth", 0.5),
    InputSpec("bore_clearance", "Bore clearance", "bore_clearance", 0.05),
    InputSpec("rotor_diameter", "Rotor diameter", "rotor_diameter", 192.0),  # DEFAULT_ROTOR_DIAMETER, 128 to 224
    InputSpec("blade_pitch", "Blade pitch", "blade_pitch", 25.0, "angle"),  # DEFAULT_BLADE_PITCH, in degrees
    InputSpec("hand", "Hand", "hand", HANDS[RIGHT_HAND], "choice", HANDS),
    InputSpec("mount", "Mount", "mount", MOUNTS[SHAFT_MOUNT], "choice", MOUNTS),
    # The clutch the clutch mount builds, as the one-way clutch's own inputs. Used only when Mount is Clutch, where the
    # shaft, hand and bore inputs above are replaced by the values the clutch gives (docs/turbinefan/deviations.md).
    InputSpec("clutch_shaft", "Clutch shaft", "clutch_shaft", SHAFTS[0].name, "choice", tuple(s.name for s in SHAFTS)),
    InputSpec("clutch_freewheel", "Clutch freewheel", "clutch_freewheel", CLOCKWISE, "choice", DIRECTIONS),
    InputSpec("clutch_bore_clearance", "Clutch bore clearance", "clutch_bore_clearance", 0.05),
    # Directive: an extra option, off by default, that adds the sacrificial bridge layers of the hub and, in the clutch
    # mount, of the clutch's back plate, cover and adapter ring (docs/sacrificial-bridging.md in decad-converter). The
    # blades, bolts and nuts get none. The box shows in both mounts. Not a gallery input.
    InputSpec("sacrificial_bridging", "Sacrificial bridging", "sacrificial_bridging", 0, "bool"),
)

# The inputs that set the clutch, not a Params field; and the ones the clutch mount ignores or replaces.
CLUTCH_IDS: tuple[str, ...] = ("clutch_shaft", "clutch_freewheel", "clutch_bore_clearance")
SHAFT_MOUNT_IDS: tuple[str, ...] = ("shaft_diameter", "flat_depth", "bore_clearance", "hand")


def params_from_values(values: dict[str, float | str]) -> Params:
    """Build Params from dialog values: lengths in mm, the pitch in radians, the hand and the mount as item names.

    # Deviation: a length read back from Fusion (centimeters times ten) is rounded to 1e-9 mm, so the dialog's own
    default never fails a range check, such as the 0.05 mm bore clearance minimum, by one ulp. The pitch is rounded
    the same way (docs/turbinefan/deviations.md)."""
    kwargs: dict[str, float | int] = {}
    clutch: dict[str, float | str] = {}
    for spec in INPUT_SPECS:
        v = values[spec.id]
        if spec.id in CLUTCH_IDS:
            clutch[spec.id] = str(v) if spec.kind == "choice" else round(float(v), 9)
        elif spec.kind == "choice":
            kwargs[spec.field] = spec.choices.index(str(v)) if str(v) in spec.choices else -1
        elif spec.kind == "bool":
            kwargs[spec.field] = bool(v)
        else:
            kwargs[spec.field] = round(float(v), 9)
    p = Params(**kwargs)  # pyright: ignore[reportArgumentType]
    if p.mount != CLUTCH_MOUNT:
        return p
    # Deviation: the clutch mount builds the clutch too, so the shaft, the hand and the bore come from the clutch
    # inputs, as the gallery's ParamsForClutch does (docs/turbinefan/deviations.md).
    c = ClutchParams(shaft=str(clutch["clutch_shaft"]), freewheel=str(clutch["clutch_freewheel"]),
                     bore_clearance=float(clutch["clutch_bore_clearance"]),
                     sacrificial_bridging=p.sacrificial_bridging)
    return params_for_clutch(c, p.blade_pitch, rotor_diameter=p.rotor_diameter)

