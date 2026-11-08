"""Own copy of decad-gallery models/ballbearing Params608ZZ (the bearing envelope)."""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Bearing:
    bore_diameter: float
    outer_diameter: float
    width: float


def bearing_608zz() -> Bearing:
    return Bearing(8.0, 22.0, 7.0)
