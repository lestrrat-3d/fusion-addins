"""Point probes: points that must lie inside or outside a printed body, in the local frame (millimeters).

Fusion's point containment is exact, so a probe sits at least 0.3 mm from every surface. They stand in for the
gallery's section checks of the bore, the slit, the pockets and the pin's flats, which have no Fusion counterpart.
"""

from __future__ import annotations

import dataclasses
import math

from . import bodies
from .params import Dimensions, Params

INSIDE = "inside"
OUTSIDE = "outside"


@dataclasses.dataclass(frozen=True)
class Probe:
    label: str
    point: tuple[float, float, float]
    expect: str  # INSIDE (in the material) or OUTSIDE (in a cavity or beyond the body)


def _arm(p: Params, dm: Dimensions) -> list[Probe]:
    t, rb, fb, yc = p.throw, dm.bore_radius, dm.bore_flat, dm.clamp_y
    wall = (rb + 0.5) / math.sqrt(2)
    return [
        Probe("arm material beside the pin", (0.0, t + 8.0, 4.0), INSIDE),
        Probe("pin bolt head pocket", (0.0, t, 1.0), OUTSIDE),
        Probe("stub pocket", (3.5, t, 6.0), OUTSIDE),
        Probe("stub pocket wall", (5.5, t, 6.0), INSIDE),
        Probe("bore", (0.0, 0.0, 3.0), OUTSIDE),
        Probe("bore floor", (1.0, 0.0, 7.5), INSIDE),
        Probe("bore wall", (-wall, -wall, 3.0), INSIDE),
        Probe("bore flat, shaft side", (0.0, fb - 0.3, 3.0), OUTSIDE),
        Probe("bore flat, arm side", (0.0, fb + 0.3, 3.0), INSIDE),
        Probe("slit", (0.0, -(rb + 3.0), 1.0), OUTSIDE),
        Probe("slit wall", (0.8, -(rb + 3.0), 1.0), INSIDE),
        Probe("clamp bolt hole", (5.0, yc, 4.0), OUTSIDE),
        Probe("clamp head pocket", (9.0, yc + 1.8, 4.0), OUTSIDE),
        Probe("clamp head pocket wall", (7.0, yc + 1.8, 4.0), INSIDE),
        Probe("clamp nut pocket", (-9.0, yc + 1.5, 4.0), OUTSIDE),
        Probe("clamp nut pocket wall", (-7.0, yc + 1.5, 4.0), INSIDE),
        Probe("face chamfer", (9.95, 10.0, 0.05), OUTSIDE),
        Probe("face chamfer, inside", (9.5, 10.0, 1.0), INSIDE),
    ]


def _pin(p: Params) -> list[Probe]:
    t = p.throw
    return [
        Probe("stub", (3.0, t, 4.0), INSIDE),
        Probe("shank", (5.0, t, 30.0), INSIDE),
        Probe("beyond the shank", (5.4, t, 30.0), OUTSIDE),
        Probe("head", (6.0, t, 56.5), INSIDE),
        Probe("beyond the head", (6.7, t, 56.5), OUTSIDE),
        Probe("pin bolt hole", (0.0, t, 10.5), OUTSIDE),
        Probe("past the pin bolt hole", (0.0, t, 14.0), INSIDE),
        Probe("pin nut cavity", (2.0, t, 5.75), OUTSIDE),
        Probe("shank beside the flats", (0.0, t + 4.5, 30.0), INSIDE),
        Probe("flat 1", (0.0, t + 4.5, 17.0), OUTSIDE),
        Probe("flat 2", (0.0, t + 4.5, 49.0), OUTSIDE),
        Probe("cross bolt 1 head pocket", (1.0, t + 3.0, 17.5), OUTSIDE),
        Probe("cross bolt 1 nut pocket", (0.0, t - 3.0, 17.0), OUTSIDE),
        Probe("cross bolt 1 hole", (0.0, t, 17.0), OUTSIDE),
        Probe("cross bolt 1 hole wall", (3.0, t, 17.0), INSIDE),
        Probe("cross bolt 2 hole", (0.0, t, 49.0), OUTSIDE),
    ]


def _handle(p: Params) -> list[Probe]:
    t = p.throw
    return [
        Probe("handle bore", (0.0, t, 30.0), OUTSIDE),
        Probe("handle wall", (6.5, t, 30.0), INSIDE),
        Probe("beyond the handle", (8.5, t, 30.0), OUTSIDE),
        Probe("counterbore", (6.5, t, 56.4), OUTSIDE),
        Probe("counterbore wall", (8.0, t, 56.4), INSIDE),
    ]


def part_probes(p: Params, dm: Dimensions) -> dict[str, list[Probe]]:
    """Probes per printed body name."""
    return {bodies.ARM: _arm(p, dm), bodies.PIN: _pin(p), bodies.HANDLE: _handle(p)}
