"""Own copy of decad-gallery models/ballbearing Params605ZZ (the bearing envelope: 5 x 14 x 5 mm)."""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Bearing:
    bore_diameter: float
    outer_diameter: float
    width: float


def bearing_605zz() -> Bearing:
    return Bearing(5.0, 14.0, 5.0)
