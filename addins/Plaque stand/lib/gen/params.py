"""Plaque stand inputs and derived dimensions.

Own copy of decad-gallery models/plaquestand params.go (Params, Dimensions). The gallery has no placement input, so the
add-in has none: the stand is built at the origin of its own component.
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    DEFAULT_LIP_HEIGHT,
    DEFAULT_PLAQUE_HEIGHT,
    DEFAULT_PLAQUE_THICKNESS,
    DEFAULT_PLAQUE_WIDTH,
    DEFAULT_RECLINE,
    DEFAULT_SLOT_CLEARANCE,
)
from .fasteners import Site

Vec2 = tuple[float, float]  # (y, z) on the plane x = 0

Vec3 = tuple[float, float, float]


@dataclasses.dataclass(frozen=True)
class Frame:
    origin: Vec3 = (0.0, 0.0, 0.0)
    u: Vec3 = (1.0, 0.0, 0.0)
    v: Vec3 = (0.0, 1.0, 0.0)


def _norm(a: Vec3) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def frame_is_valid(f: Frame) -> bool:
    """Port of r3 NewFrame validity: finite numbers, nonzero u and v, not collinear."""
    nums = f.origin + f.u + f.v
    if not all(math.isfinite(n) for n in nums):
        return False
    nu, nv = _norm(f.u), _norm(f.v)
    if nu == 0 or nv == 0:
        return False
    return _norm(_cross(f.u, f.v)) > 1e-12 * nu * nv


def frame_axes(f: Frame) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    """Return (origin, x, y, z) of the orthonormalized frame. Raises ValueError when f is invalid."""
    if not frame_is_valid(f):
        raise ValueError("invalid placement frame")
    nu = _norm(f.u)
    x: Vec3 = (f.u[0] / nu, f.u[1] / nu, f.u[2] / nu)
    k = _dot(f.v, x)
    w: Vec3 = (f.v[0] - k * x[0], f.v[1] - k * x[1], f.v[2] - k * x[2])
    nw = _norm(w)
    y: Vec3 = (w[0] / nw, w[1] / nw, w[2] / nw)
    return (f.origin, x, y, _cross(x, y))



@dataclasses.dataclass(frozen=True)
class Params:
    """Stand inputs in mm and degrees. Field order and defaults are the gallery's DefaultParams."""

    plaque_width: float = DEFAULT_PLAQUE_WIDTH  # W, along X
    plaque_height: float = DEFAULT_PLAQUE_HEIGHT  # H, along the slot axis
    plaque_thickness: float = DEFAULT_PLAQUE_THICKNESS  # t
    recline: float = DEFAULT_RECLINE  # theta, degrees from vertical
    lip_height: float = DEFAULT_LIP_HEIGHT  # the lip top's height above the seat, along the slot axis
    slot_clearance: float = DEFAULT_SLOT_CLEARANCE  # c, per side


def default_params() -> Params:
    return Params()


@dataclasses.dataclass(frozen=True)
class Dimensions:
    """Values derived from Params, in mm and degrees, in the local frame [params.go Dimensions]. Every point is (y, z)
    on the plane x = 0."""

    span: float  # S: the rail's length and the distance between the brackets' outer faces
    channel_width: float  # w_c
    channel_height: float  # h_c
    channel_back: float  # y_cb
    channel_front: float  # y_cf
    channel_floor: float  # z_f
    rail_center: float  # y_ch
    sites: tuple[Site, Site]  # the two bolts, one per bracket
    back_height: float  # H_b
    slot_width: float  # s
    slot_radius: float  # R
    back_wall: float  # h_b: the straight back wall's length
    lip_wall: float  # h_l: the straight front wall's length
    axis: Vec2  # u: along the slot
    normal: Vec2  # n: normal to the slot, pointing back and down
    seat: Vec2  # C: the slot round's centre
    depth: float  # D: the stand's extent along Y
    height: float  # the stand's extent along Z
    play_angle: float  # alpha, degrees
    tip_front: float  # degrees
    tip_back: float
    tip_side: float
    q3y: float  # where the back rest's back line meets the base top
    q7y: float  # where the lip's front line meets the base top
    kf: float  # tangent length per unit root radius at the lip root
    kb: float  # and at the back-rest root
