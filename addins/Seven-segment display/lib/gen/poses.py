"""Frames of the bodies: each body is built in a local frame, with its axis on local +Z, then moved once onto its frame.

The camshaft group (shaft, cams) is turned by theta about the shaft axis, right-handed about +Y. The bearings, walls
and fasteners do not turn. Frames are (origin, x, y, z) tuples as in frames.py.
"""

from __future__ import annotations

import math

from . import frames
from .constants import FRONT_INNER_Y, REAR_INNER_Y, SHAFT_Z, STATION_FACE
from .fasteners import Site
from .truth import station

Axes = frames.Axes
Vec3 = frames.Vec3


def turn_axes(theta: float) -> Axes:
    """The right-hand turn by theta degrees about the shaft axis (x = 0, z = SHAFT_Z, along +Y)."""
    c, s = math.cos(math.radians(theta)), math.sin(math.radians(theta))
    x: Vec3 = (c, 0.0, -s)
    z: Vec3 = (s, 0.0, c)
    # origin = centre - R centre, with centre = (0, 0, SHAFT_Z)
    return ((-SHAFT_Z * s, 0.0, SHAFT_Z - SHAFT_Z * c), x, (0.0, 1.0, 0.0), z)


def shaft_axes(theta: float) -> Axes:
    """The shaft's frame: origin on the axis at y = 0, local z along world +Y, local x along world +Z (the flats'
    normal) and local y along world +X [camshaftFrame(0)]; then turned by theta."""
    return frames.compose(turn_axes(theta), ((0.0, 0.0, SHAFT_Z), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))


def cam_axes(segment: int, theta: float) -> Axes:
    """A cam's frame: origin on its groove face and the shaft axis, U = +X, V = +Z, so local +Z runs along world -Y
    [camFrame]; then turned by theta."""
    local = ((0.0, station(segment) + STATION_FACE, SHAFT_Z), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
    return frames.compose(turn_axes(theta), local)


def wall_axes(front: bool) -> Axes:
    """A wall's frame: origin on the shaft axis in its inner face, V = +Z and local +Z (the wall's thickness) pointing
    outward [wallFrame]: front U = +X, rear U = -X."""
    if front:
        return ((0.0, FRONT_INNER_Y, SHAFT_Z), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
    return ((0.0, REAR_INNER_Y, SHAFT_Z), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))


def bearing_axes(front: bool) -> Axes:
    """A bearing's frame: the lower cap's centre on the wall's inner face, extruding into the wall's seat. Front:
    U = +X, V = +Z (toward -Y). Rear: U = +Z, V = +X (toward +Y)."""
    if front:
        return ((0.0, FRONT_INNER_Y, SHAFT_Z), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
    return ((0.0, REAR_INNER_Y, SHAFT_Z), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def site_in(site: Site, axes: Axes) -> Site:
    """The site given in the frame `axes` (the site's head, direction and corner expressed in that frame)."""
    inv = frames.inverse(axes)
    return Site(head=frames.apply(inv, site.head), dir=frames.rotate(inv, site.dir),
                corner=frames.rotate(inv, site.corner), length=site.length, cavity=site.cavity)
