"""Sacrificial bridge layers for printing (not in decad-gallery).

The pin bolt's head pocket in the arm is wider than the hole above it, so the first printed layer over the pocket would
hang in the air. The bridge layer fills that hole for BRIDGE_THICKNESS directly above the pocket's roof, so the layer
is a full disc the slicer can bridge. The owner drills it out after printing. The rule is in decad-converter
docs/sacrificial-bridging.md, and the crank's directive is in docs/crankhandle/directives.md.

Only the arm has a hole with a roof. Printed with +Z up, the arm's other cavities are open to the top, run
horizontally or are closed by their own floor. The pin prints as two halves on their cut faces, and none of its holes
has a narrower hole above a wider part in that orientation, so it gets no layer.
"""

from __future__ import annotations

import dataclasses
import math

from . import bodies
from .constants import PIN_HOLE_R
from .fasteners import HEAD_POCKET_DEPTH
from .params import Params

BRIDGE_THICKNESS = 0.3  # mm, one printed layer
BRIDGE_OVERLAP = 0.1  # mm, how far the layer's disc reaches into the hole wall so the join overlaps the arm's volume


@dataclasses.dataclass(frozen=True)
class Bridge:
    label: str
    center: tuple[float, float]  # on the XY plane
    radius: float  # the hole's radius; the layer fills the whole hole
    z0: float  # the roof of the wider part below, where the layer starts
    thickness: float = BRIDGE_THICKNESS

    def disc_radius(self) -> float:
        """Radius of the layer's disc: the hole plus BRIDGE_OVERLAP of wall all round."""
        return self.radius + BRIDGE_OVERLAP

    def volume(self) -> float:
        """Volume (mm^3) the layer adds to the body: the hole's section for `thickness`."""
        return math.pi * self.radius**2 * self.thickness


def arm_bridges(p: Params) -> list[Bridge]:
    """The arm prints on its back face, +Z up. The pin bolt's head pocket (radius 2.2, from the back face to
    HEAD_POCKET_DEPTH) has the 1.3 mm pin hole above its roof."""
    return [Bridge("pin bolt hole over its head pocket", (0.0, p.throw), PIN_HOLE_R, HEAD_POCKET_DEPTH)]


def bridges_of(name: str, p: Params) -> list[Bridge]:
    """The layers of a body, empty for a body that is not bridged or has no hole with a roof."""
    return arm_bridges(p) if name == bodies.ARM else []


def extra_volume(name: str, p: Params) -> float:
    """Volume (mm^3) the layers add to a body when `Sacrificial bridging` is on."""
    return sum(b.volume() for b in bridges_of(name, p)) if p.sacrificial_bridging else 0.0
