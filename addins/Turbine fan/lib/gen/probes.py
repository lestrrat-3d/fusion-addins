"""Point probes: points that must lie inside or outside a printed body, in the local frame (millimeters).

Fusion's point containment is exact, so a probe sits at least 0.25 mm from every surface. They stand in for the
gallery's section checks of the bore, the pockets, the slots and the blades' stud, which have no Fusion counterpart.
"""

from __future__ import annotations

import dataclasses
import math

from . import bodies
from .blade import rotate
from .bridge import all_hub_layers
from .constants import BLADE_COUNT, FACE_CIRCLE
from .params import Dimensions, Params, adapter_site, blade_angle

INSIDE = "inside"
OUTSIDE = "outside"


@dataclasses.dataclass(frozen=True)
class Probe:
    label: str
    point: tuple[float, float, float]
    expect: str  # INSIDE (in the material) or OUTSIDE (in a cavity or beyond the body)


def _polar(r: float, angle: float, z: float, tangent: float = 0.0) -> tuple[float, float, float]:
    """The point r along the radial line at `angle` and `tangent` along its counterclockwise tangent."""
    c, s = math.cos(angle), math.sin(angle)
    return (r * c - tangent * s, r * s + tangent * c, z)


def _hub(p: Params, dm: Dimensions) -> list[Probe]:
    rb, fb, rho_f = dm.bore_radius, dm.bore_flat, dm.counterbore_floor
    sz = dm.size
    wall = (rb + 0.5) / math.sqrt(2)
    slot_far = fb + 1.6 + 2.0  # the set screw slot's outer face, as a distance below the axis
    hole_y = -(slot_far + (rho_f - slot_far) / 2)
    mid = sz.hub_mid  # the sockets' and blade bolts' plane
    slot_z = sz.hub_length - sz.blade_bolt_cavity - 1  # the middle of the blade nut slots (z 2.4 to 4.4 at 128)
    slot_r = sz.blade_bolt_at + 2.5  # along a blade's line, inside the slot and out toward the rim
    probes = [
        Probe("material between the blades", (0.0, -9.0, mid), INSIDE),
        Probe("bore", (0.0, 0.0, mid), OUTSIDE),
        Probe("bore, back half", (0.0, 0.0, 3.0), OUTSIDE),
        Probe("bore wall", (wall, wall, mid), INSIDE),
        Probe("bore flat, shaft side", (0.0, -fb + 0.3, mid), OUTSIDE),
        Probe("bore flat, hub side", (0.0, -fb - 0.3, mid), INSIDE),
        Probe("socket 1", (0.0, sz.blade_socket_start + 0.3, mid), OUTSIDE),
        Probe("socket 1 wall", (sz.blade_socket_radius + 0.5, sz.blade_socket_start + 0.3, mid), INSIDE),
        Probe("blade bolt 1 hole", (0.0, sz.blade_bolt_at, sz.hub_length - 4.0), OUTSIDE),
        Probe("blade bolt 1 hole wall", (1.8, sz.blade_bolt_at, sz.hub_length - 4.0), INSIDE),
        Probe("blade bolt 1 head pocket", (0.0, sz.blade_bolt_at, sz.hub_length - 1.0), OUTSIDE),
        Probe("blade bolt 1 head pocket wall", (2.7, sz.blade_bolt_at, sz.hub_length - 1.0), INSIDE),
        Probe("blade nut slot 1", (0.0, slot_r, slot_z), OUTSIDE),
        Probe("blade nut slot 1 wall", (2.7, sz.blade_bolt_at + 0.5, slot_z), INSIDE),
        Probe("blade nut slot 1 roof", (2.0, sz.blade_bolt_at + 1.5, slot_z + 1.5), INSIDE),
        Probe("counterbore", (0.0, -(rho_f + 1.0), 4.0), OUTSIDE),
        Probe("counterbore wall", (2.7, -(rho_f + 1.0), 4.0), INSIDE),
        Probe("set screw hole", (0.0, hole_y, 4.0), OUTSIDE),
        Probe("set screw hole wall", (1.9, hole_y, 4.0), INSIDE),
        Probe("set screw nut slot", (0.0, -(fb + 2.6), 3.0), OUTSIDE),
        Probe("set screw nut slot wall", (2.7, -(fb + 2.6), 3.0), INSIDE),
        Probe("face chamfer", (sz.hub_radius - 0.01, 0.0, 0.01), OUTSIDE),
        Probe("face chamfer, inside", (sz.hub_radius - 0.5, 0.0, 1.0), INSIDE),
        Probe("front face chamfer", (sz.hub_radius - 0.01, 0.0, sz.hub_length - 0.01), OUTSIDE),
    ]
    for k in range(1, BLADE_COUNT):  # the other two sockets and blade nut slots are copies turned about the axis
        a = blade_angle(k + 1)
        probes.append(Probe(f"socket {k + 1}", _polar(sz.blade_socket_start + 0.3, a, mid), OUTSIDE))
        probes.append(Probe(f"blade nut slot {k + 1}", _polar(slot_r, a, slot_z), OUTSIDE))
        probes.append(Probe(f"blade nut slot {k + 1} wall", _polar(sz.blade_bolt_at + 0.5, a, slot_z, 2.7), INSIDE))
    for k in (1, 2):
        # The adapter bolts lie on the clutch's face circle, which does not follow the rotor size.
        a = math.atan2(adapter_site(k).corner[1], adapter_site(k).corner[0])
        probes.append(Probe(f"adapter bolt {k} hole", _polar(FACE_CIRCLE, a, 5.5), OUTSIDE))
        probes.append(Probe(f"adapter bolt {k} hole, past its end", _polar(FACE_CIRCLE, a, 7.75), INSIDE))
        probes.append(Probe(f"adapter nut slot {k}", _polar(11.0, a, 2.5), OUTSIDE))
        probes.append(Probe(f"adapter nut slot {k} wall", _polar(11.0, a, 2.5, 2.7), INSIDE))
    # Directive: sacrificial bridge layers (not in the gallery model). Each fills a bolt hole for BRIDGE_THICKNESS
    # directly above a pocket's or slot's ceiling when the box is checked and leaves the hole open when it is not
    # (docs/turbinefan/directives.md).
    for i, layer in enumerate(all_hub_layers(dm), start=1):
        probes.append(Probe(f"hub bridge layer {i}", layer.center(), INSIDE if p.sacrificial_bridging else OUTSIDE))
    return probes


def _blade(k: int, dm: Dimensions) -> list[Probe]:
    """Probes on blade k (1 to 3): blade 1's, turned about the axis."""
    turn = blade_angle(k) - blade_angle(1)
    sz = dm.size
    mid, s = sz.hub_mid, sz.scale
    stud_y = (sz.blade_stud_start + sz.blade_stud_end) / 2 + 1.0  # inside the stud, clear of the bolt hole

    def at(x: float, y: float, z: float) -> tuple[float, float, float]:
        rx, ry = rotate((x, y), turn)
        return (rx, ry, z)

    return [
        Probe("stud", at(0.67 * sz.blade_stud_radius, stud_y, mid), INSIDE),
        Probe("stud bolt hole", at(0.0, sz.blade_bolt_at, mid), OUTSIDE),
        Probe("stud bolt hole wall", at(1.8, sz.blade_bolt_at, mid), INSIDE),
        Probe("beside the stud", at(0.0, stud_y, mid + sz.blade_stud_radius + 0.5), OUTSIDE),
        Probe("before the stud", at(0.0, sz.blade_stud_start - 0.4, mid), OUTSIDE),
        Probe("stud's inner end", at(0.0, sz.blade_stud_start + 0.4, mid), INSIDE),
        Probe("blade at r 20 s", at(0.0, 20.0 * s, mid), INSIDE),
        Probe("blade at r 30 s", at(0.0, 30.0 * s, mid), INSIDE),
        Probe("blade at r 50 s", at(0.0, 50.0 * s, mid), INSIDE),
        Probe("below the blade", at(0.0, 20.0 * s, 2.0), OUTSIDE),
        Probe("beyond the tip", at(0.0, sz.tip_radius + 2.0, mid), OUTSIDE),
    ]


def part_probes(p: Params, dm: Dimensions) -> dict[str, list[Probe]]:
    """Probes per printed body name."""
    out = {bodies.HUB: _hub(p, dm)}
    for k, name in enumerate(bodies.BLADES, start=1):
        out[name] = _blade(k, dm)
    return out
