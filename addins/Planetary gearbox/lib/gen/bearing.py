"""Own copy of decad-gallery models/ballbearing catalog.go at 45b5875 (the bearing catalog: 605ZZ and 608ZZ)."""

from __future__ import annotations

import dataclasses

# Radial clearance between a bearing's outer race and a bore that holds it fixed [catalog.go SeatClearance].
SEAT_CLEARANCE = 0.05
# Radial clearance between a shaft and a printed bore it is pressed into [catalog.go PressFitClearance].
PRESS_FIT_CLEARANCE = 0.05


@dataclasses.dataclass(frozen=True)
class Spec:
    """One purchased bearing of the catalog. Lengths mm."""

    name: str
    bore_diameter: float
    outer_diameter: float
    width: float
    # Outside diameter of the inner race's face; a shoulder or collar must be narrower. A repository assumption of the
    # gallery, not a catalogue value (the open question on 605ZZ 8.0 vs 6.8 mm is with the owner).
    inner_race_diameter: float

    def shaft_diameter(self) -> float:
        """Diameter of a shaft or pin through the bore: the bore itself, with no clearance."""
        return self.bore_diameter

    def seat_diameter(self) -> float:
        """Diameter of a bore or pocket that holds the outer race fixed."""
        return self.outer_diameter + 2 * SEAT_CLEARANCE

    def press_bore_diameter(self) -> float:
        """Diameter of a printed bore that a shaft_diameter shaft presses into."""
        return self.bore_diameter + 2 * PRESS_FIT_CLEARANCE


CATALOG: tuple[Spec, ...] = (
    Spec("605ZZ", 5.0, 14.0, 5.0, 8.0),
    Spec("608ZZ", 8.0, 22.0, 7.0, 12.0),
)


def catalog_names() -> tuple[str, ...]:
    """Catalog names, in catalog order."""
    return tuple(s.name for s in CATALOG)


def lookup(name: str) -> Spec | None:
    """The catalog bearing whose name equals `name` exactly (case-sensitive), or None."""
    for s in CATALOG:
        if s.name == name:
            return s
    return None


# Kept until the per-role dimensions replace it (see dims.py).
@dataclasses.dataclass(frozen=True)
class Bearing:
    bore_diameter: float
    outer_diameter: float
    width: float


def bearing_605zz() -> Bearing:
    return Bearing(5.0, 14.0, 5.0)
