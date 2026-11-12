"""Sacrificial bridge layers for printing (not in decad-gallery).

A nut cavity is wider than the bolt hole above it, so the first printed layer over the cavity would hang in the air.
The bridge layer fills the bolt hole for BRIDGE_THICKNESS directly above the cavity roof, so that layer is a full disc
the slicer can bridge. The owner drills it out after printing. The rule is in decad-converter
docs/sacrificial-bridging.md, and the ring's directive is in docs/planetarygearbox/directives.md.
"""

from __future__ import annotations

import dataclasses
import math

from .dims import Dims
from .fasteners import nut_cavity_height
from .layout import Pose, nut_cavity_poses
from .params import Params

BRIDGE_THICKNESS = 0.3  # mm, one printed layer
BRIDGE_OVERLAP = 0.1  # mm, how far the layer's disc reaches into the hole wall so the join overlaps the ring volume


def bridge_disc_diameter(hole_diameter: float) -> float:
    """Diameter of the layer's disc: the bolt hole plus BRIDGE_OVERLAP of wall on each side."""
    return hole_diameter + 2 * BRIDGE_OVERLAP


NUT_BRIDGE_COUNT = 8  # one per nut cavity, front four and rear four


def nut_bridge_poses(p: Params, d: Dims) -> list[Pose]:
    """Ring-local poses of the layer tool, one per nut cavity, in nut_cavity_poses order.

    The tool starts at its own z = 0 and rises BRIDGE_THICKNESS, so each pose puts it on its cavity's roof.
    """
    return [dataclasses.replace(q, z=q.z + nut_cavity_height()) for q in nut_cavity_poses(p, d)]


def nut_bridge_volume(p: Params) -> float:
    """Volume (mm^3) the layers add to the ring: each fills the bolt hole's section for BRIDGE_THICKNESS."""
    return NUT_BRIDGE_COUNT * math.pi * (p.bolt_hole_diameter / 2) ** 2 * BRIDGE_THICKNESS
