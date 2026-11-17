"""Sacrificial bridge layers for printing (not in decad-gallery).

A pocket that opens on the print bed is wider than the bolt hole above it, so the first printed layer over the pocket
would hang in the air. The bridge layer fills the bolt hole for BRIDGE_THICKNESS directly above the pocket's roof, so
that layer is a full disc the slicer can bridge. The owner drills it out after printing. The rule is in decad-converter
docs/sacrificial-bridging.md, and the directive is in docs/turbinefan/directives.md (and docs/onewayclutch/directives.md).

Bodies and print orientation (the gallery's, from instructions.md "Printing"):

- Back plate: outer face (z = 0) down, so +Z is up. Each hex nut pocket opens on the bed and the 2.6 mm bolt hole
  continues above its ceiling at z = 2.0, so the layer is z 2.0 to 2.3.
- Cover: outer face (z = 18.5) down, so -Z is up. Each bolt head pocket opens on the bed and the bolt hole continues
  above its ceiling at z = 16.5, so the layer is z 16.2 to 16.5.
- Adapter ring: front face (z = 26.0) down, so -Z is up. Each of the three ear head pockets opens on the bed and the
  ear hole continues above its ceiling at z = 24.0, so the layer is z 23.7 to 24.0. The three face head pockets open on
  the rear face, which is on top, so they have a floor and no roof, and the access holes run straight through.

No hole is exempt. The hub, the ring, the bolts and the nuts get no layers.
"""

from __future__ import annotations

import dataclasses
import math

from . import bodies
from ..fasteners import HEAD_POCKET_DEPTH, HOLE_RADIUS, Site
from .params import Dimensions, Params

BRIDGE_THICKNESS = 0.3  # mm, one printed layer
BRIDGE_OVERLAP = 0.1  # mm, how far the layer's disc reaches into the hole wall so the join overlaps the body's volume


@dataclasses.dataclass(frozen=True)
class Layer:
    """One bridge layer in a bolt hole: the site whose line it sits on, and its near face's distance from the head's
    top face along the site's direction. It spans `start` to `start + BRIDGE_THICKNESS` along the direction."""

    site: Site
    start: float

    def z_range(self) -> tuple[float, float]:
        """(low, high) of the layer in the local frame; the sites of this model all run along Z."""
        a, b = self.site.at(self.start)[2], self.site.at(self.start + BRIDGE_THICKNESS)[2]
        return (min(a, b), max(a, b))

    def center(self) -> tuple[float, float, float]:
        """The middle of the layer on the hole's axis."""
        return self.site.at(self.start + BRIDGE_THICKNESS / 2)


def layer_radius() -> float:
    """Radius of the layer's disc: the bolt hole plus BRIDGE_OVERLAP of wall all round."""
    return HOLE_RADIUS + BRIDGE_OVERLAP


def back_plate_layers(dm: Dimensions) -> list[Layer]:
    """One layer per hex nut pocket, in the hole above the pocket's ceiling (the site's cavity near face)."""
    return [Layer(s, s.cavity - BRIDGE_THICKNESS) for s in dm.sites]


def cover_layers(dm: Dimensions) -> list[Layer]:
    """One layer per bolt head pocket, in the hole above the pocket's ceiling (the head pocket's floor)."""
    return [Layer(s, HEAD_POCKET_DEPTH) for s in dm.sites]


def adapter_layers(dm: Dimensions) -> list[Layer]:
    """One layer per ear head pocket (the mount sites), in the hole above the pocket's ceiling. The face sites' pockets
    open on the rear face, which is on top, so they get none."""
    return [Layer(s, HEAD_POCKET_DEPTH) for s in dm.mount_sites]


def layers_for(name: str, p: Params, dm: Dimensions) -> list[Layer]:
    """The layers of a body: none unless the `Sacrificial bridging` box is checked and the body is a bridged one."""
    if not p.sacrificial_bridging:
        return []
    if name == bodies.BACK_PLATE:
        return back_plate_layers(dm)
    if name == bodies.COVER:
        return cover_layers(dm)
    if name == bodies.ADAPTER and p.adapter:
        return adapter_layers(dm)
    return []


def bridge_volume(name: str, p: Params, dm: Dimensions) -> float:
    """Volume (mm^3) the body's layers add: each fills the bolt hole's section for BRIDGE_THICKNESS."""
    return len(layers_for(name, p, dm)) * math.pi * HOLE_RADIUS**2 * BRIDGE_THICKNESS
