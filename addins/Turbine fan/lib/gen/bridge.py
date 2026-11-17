"""Sacrificial bridge layers of the hub, for printing (not in decad-gallery).

The rule is in decad-converter docs/sacrificial-bridging.md and the directive is in docs/turbinefan/directives.md. The
clutch's own layers are in clutch/bridge.py. The layer is the same: a 0.3 mm disc that fills a bolt hole directly above
a wider pocket's roof, so the first printed layer over the pocket is whole. The owner drills it out after printing.

Body and print orientation (the gallery's, from instructions.md "Corners and roots": the hub prints front face down with
its axis vertical): the hub's front face (z = Size.hub_length: 30 at the default 192 mm, 20 at 128 mm) is on the bed, so -Z
is up. A hole has a roof when a wider part lies
below it and the hole continues above it, toward the back face.

Holes that get a layer (no exemptions):

- Each blade bolt's head pocket (radius 2.2, the 2 mm below the front face, open on the bed) has the 2.6 mm bolt hole
  above its ceiling at z = hub_length - 2, so the layer is 0.3 mm above that (z 27.7 to 28.0 at 192 mm, 17.7 to 18.0 at
  128 mm). Three layers.
- Each blade bolt's nut slot (open through the rim; z 3.4 to 5.4 at 192 mm, 2.4 to 4.4 at 128 mm) has the bolt hole above
  its ceiling at z = hub_length - cavity - 2 (3.4 at 192 mm, 2.4 at 128 mm), which runs on to the back face, so the
  layer is z 3.1 to 3.4 at 192 mm (2.1 to 2.4 at 128 mm). Three layers.
- Each adapter bolt's nut slot (z 1.5 to 3.5, open through the rim) has the adapter hole above its ceiling at
  z = 1.5, which runs on to the back face, so the layer is z 1.2 to 1.5. Two layers. The hub has these holes in both
  mounts, so they get layers in both.

Holes that get none, because no flat roof has a narrower hole above it in this orientation:

- The set screw's counterbore, hole and nut slot lie along the horizontal line y, so none has a roof. The nut slot opens
  on the back face, which is on top.
- The three blade sockets are horizontal cylinders. Their round ceilings have the blade bolt holes above them; the
  roof is curved, so no layer is built and the owner is asked (docs/turbinefan/directives.md).
- The D bore runs straight through; its lead-in chamfers are 45 degree slopes, not steps.

The blades, bolts and nuts get no layers.
"""

from __future__ import annotations

import math

from .clutch.bridge import BRIDGE_OVERLAP, BRIDGE_THICKNESS, Layer, layer_radius
from .fasteners import HEAD_POCKET_DEPTH, HOLE_RADIUS
from .params import Dimensions, Params

__all__ = [
    "BRIDGE_OVERLAP", "BRIDGE_THICKNESS", "Layer", "layer_radius", "blade_pocket_layers", "blade_slot_layers",
    "adapter_slot_layers", "all_hub_layers", "hub_layers", "bridge_volume",
]


def blade_pocket_layers(dm: Dimensions) -> list[Layer]:
    """One layer per blade bolt head pocket, in the hole above the pocket's ceiling (the pocket's depth, z 18)."""
    return [Layer(s, HEAD_POCKET_DEPTH) for s in dm.blade_sites]


def blade_slot_layers(dm: Dimensions) -> list[Layer]:
    """One layer per blade nut slot, in the hole above the slot's ceiling. The bolts run along -Z, so the slot's far
    face (cavity_far, z 2.4) is its ceiling and the layer starts there."""
    return [Layer(s, s.cavity_far()) for s in dm.blade_sites]


def adapter_slot_layers(dm: Dimensions) -> list[Layer]:
    """One layer per adapter nut slot, in the hole above the slot's ceiling. The bolts run along +Z, so the slot's near
    face (cavity, z 1.5) is its ceiling and the layer lies just before it."""
    return [Layer(s, s.cavity - BRIDGE_THICKNESS) for s in dm.adapter_sites]


def all_hub_layers(dm: Dimensions) -> list[Layer]:
    """Every layer the hub can have, whether or not the box is checked."""
    return blade_pocket_layers(dm) + blade_slot_layers(dm) + adapter_slot_layers(dm)


def hub_layers(p: Params, dm: Dimensions) -> list[Layer]:
    """The hub's layers: none unless the `Sacrificial bridging` box is checked."""
    return all_hub_layers(dm) if p.sacrificial_bridging else []


def bridge_volume(p: Params, dm: Dimensions) -> float:
    """Volume (mm^3) the hub's layers add: each fills the bolt hole's section for BRIDGE_THICKNESS."""
    return len(hub_layers(p, dm)) * math.pi * HOLE_RADIUS**2 * BRIDGE_THICKNESS
