"""Own copy of decad-gallery models/ballbearing catalog entries 605ZZ and 608ZZ (catalog.go)."""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Bearing:
    name: str
    bore_diameter: float
    outer_diameter: float
    width: float
    # Outside diameter of the inner race's face; a shoulder or collar must be narrower [catalog.go InnerRaceDiameter].
    inner_race_diameter: float


BEARING_605ZZ = Bearing("605ZZ", 5.0, 14.0, 5.0, 8.0)
BEARING_608ZZ = Bearing("608ZZ", 8.0, 22.0, 7.0, 12.0)

# The bearing catalog in the gallery's order [ballbearing.Catalog].
CATALOG: tuple[Bearing, ...] = (BEARING_605ZZ, BEARING_608ZZ)


def lookup(name: str) -> Bearing | None:
    """The catalog bearing called name, or None when the catalog has none [ballbearing.Lookup]."""
    for b in CATALOG:
        if b.name == name:
            return b
    return None


def bearing_name_error(role: str, name: str) -> str | None:
    """The gallery's error for a bearing name outside the catalog [params.go bearingNameError], or None."""
    if lookup(name) is not None:
        return None
    names = ", ".join(b.name for b in CATALOG)
    return f'{role} bearing "{name}" is not in the bearing catalog; choose one of {names}'
