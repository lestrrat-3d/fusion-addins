"""Expected bounding boxes of the built bodies, in the model frame (the component's own coordinates).

The add-in's own expectations from the gallery's dimensions: the gallery tests bodies by mesh, not by bounding box.
`body_bounds` returns None for a body with no cheap expectation.
Every box is (min x, min y, min z, max x, max y, max z) in mm.
"""

from __future__ import annotations

from . import constants as k
from . import clicker_params as cp
from . import fasteners
from . import flags_pivot
from .params import Dimensions
from .truth import SEGMENTS, station

Box = tuple[float, float, float, float, float, float]

_CAM_NAMES = {f"Cam {c.upper()}": s for s, c in zip(SEGMENTS, "abcdefg")}


def _fastener_box(site: fasteners.Site, t0: float, t1: float, across: float, corner_half: float) -> Box:
    """The box of a part along the site's axis: from t0 to t1 along `dir`, half `across` on the dir x corner axis and
    half `corner_half` on the corner axis. Every site's dir and corner run along a coordinate axis."""
    ends = [site.at(t0), site.at(t1)]
    side = fasteners.cross(site.dir, site.corner)
    lo = [min(e[i] for e in ends) for i in range(3)]
    hi = [max(e[i] for e in ends) for i in range(3)]
    for i in range(3):
        half = abs(site.corner[i]) * corner_half + abs(side[i]) * across
        lo[i] -= half
        hi[i] += half
    return (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])


def bolt_bounds(site: fasteners.Site) -> Box:
    """The bolt: head top at t = 0, head 2.0 high of radius 1.9, shank to the tip at HEAD_POCKET_DEPTH + length."""
    return _fastener_box(site, 0.0, fasteners.HEAD_POCKET_DEPTH + site.length, fasteners.HEAD_DIAMETER / 2,
                         fasteners.HEAD_DIAMETER / 2)


def nut_bounds(site: fasteners.Site) -> Box:
    """The nut: NUT_THICKNESS thick, NUT_CLEARANCE inside the cavity's near face, corners along the site's corner."""
    t0 = site.cavity + fasteners.NUT_CLEARANCE
    return _fastener_box(site, t0, t0 + fasteners.NUT_THICKNESS, fasteners.NUT_ACROSS_FLATS / 2,
                         fasteners.nut_across_corners() / 2)


def body_bounds(name: str, dm: Dimensions) -> Box | None:
    """The expected bounding box of the body `name`, or None for a body with no expectation."""
    from . import bodies

    # A wall's box runs from its outer face to the far end of its deepest ribs, the ledge ribs.
    if name == bodies.FRONT_WALL:
        return (-k.WALL_HALF, k.FRONT_INNER_Y - k.WALL_THICKNESS, k.WALL_BOTTOM_Z, k.WALL_HALF,
                k.FRONT_INNER_Y + k.FRONT_LEDGE_DEEP, k.WALL_TOP_Z)
    if name == bodies.REAR_WALL:
        return (-k.WALL_HALF, k.REAR_INNER_Y - k.REAR_LEDGE_DEEP, k.WALL_BOTTOM_Z, k.WALL_HALF,
                k.REAR_INNER_Y + k.WALL_THICKNESS, k.WALL_TOP_Z)
    if name == bodies.SHAFT:
        # The collar's radius 5.7 is the widest section, whatever the turn.
        r = max(r for r, _ in k.SHAFT_MERIDIAN)
        ys = [z for _, z in k.SHAFT_MERIDIAN]
        return (-r, min(ys), k.SHAFT_Z - r, r, max(ys), k.SHAFT_Z + r)
    if name in _CAM_NAMES:
        face = station(_CAM_NAMES[name]) + k.STATION_FACE
        return (-k.CAM_RADIUS, face - k.CAM_HUB_TOP, k.SHAFT_Z - k.CAM_RADIUS, k.CAM_RADIUS, face + k.CAM_THICKNESS,
                k.SHAFT_Z + k.CAM_RADIUS)
    if name in (bodies.FRONT_BEARING, bodies.REAR_BEARING):
        r = k.BEARING_OUTER / 2
        if name == bodies.FRONT_BEARING:
            y0, y1 = k.FRONT_INNER_Y - k.BEARING_WIDTH, k.FRONT_INNER_Y
        else:
            y0, y1 = k.REAR_INNER_Y, k.REAR_INNER_Y + k.BEARING_WIDTH
        return (-r, y0, k.SHAFT_Z - r, r, y1, k.SHAFT_Z + r)
    if bodies.is_bolt(name):
        return bolt_bounds(dm.sites[bodies.site_index(name)])
    if bodies.is_nut(name):
        return nut_bounds(dm.sites[bodies.site_index(name)])
    if name == bodies.HUB:
        # clicker_test.go / rotors: the hub spans its rim y to its base y, diameter 2 x 21 about the shaft axis.
        r = cp.HUB_RADIUS
        return (-r, cp.HUB_RIM_Y, k.SHAFT_Z - r, r, cp.HUB_BASE_Y, k.SHAFT_Z + r)
    if name in bodies.PIVOT_ENDS:
        return flags_pivot.block_bounds(*bodies.PIVOT_ENDS[name])
    # No expectation for the flags, sliders, plates, rotor, housing, spring and button (the pivot blocks have one, from their size): the gallery gives no cheap box
    # for them (its tests probe meshes and clearances), so only the solid flag and the container check apply.
    return None


