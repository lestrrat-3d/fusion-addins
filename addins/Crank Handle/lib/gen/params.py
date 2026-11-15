"""Crank handle inputs, derived dimensions and the placement frame.

Own copy of decad-gallery models/crankhandle params.go (Params, Dimensions) and of the placement rules of the other
add-ins (a point and an axis instead of an r3.Frame).
"""

from __future__ import annotations

import dataclasses
import math

from .constants import ARM_RADIUS, CLAMP_CORNER_R, CLAMP_END_R
from .curves import Point
from .fasteners import Site

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


def placement_frame(origin: Vec3 | None, axis: Vec3 | None) -> Frame | None:
    """Frame whose origin is `origin` (world origin when None) and whose Z axis is `axis` (+Z when None).

    # Deviation: the gallery takes an r3.Frame (origin, u, v); the add-in takes a point and an axis direction chosen
    in the dialog (docs/crankhandle/deviations.md). U is a stable unit vector perpendicular to the axis (Y x axis, or
    Z x axis when the axis is nearly along Y) and V = axis x U, so frame_axes gives back z = axis and +Z gives the
    identity frame. Returns None when both are None. Raises ValueError with a dialog message when the axis is zero
    or not finite.
    """
    if origin is None and axis is None:
        return None
    o = origin if origin is not None else (0.0, 0.0, 0.0)
    a = axis if axis is not None else (0.0, 0.0, 1.0)
    if not all(math.isfinite(n) for n in o):
        raise ValueError("placement origin must be a finite point")
    if not all(math.isfinite(n) for n in a) or _norm(a) < 1e-9:
        raise ValueError("placement axis must be a nonzero direction")
    n = _norm(a)
    z: Vec3 = (a[0] / n, a[1] / n, a[2] / n)
    ref: Vec3 = (0.0, 1.0, 0.0) if abs(z[1]) < 0.9 else (0.0, 0.0, 1.0)
    u = _cross(ref, z)
    nu = _norm(u)
    u = (u[0] / nu, u[1] / nu, u[2] / nu)
    return Frame(o, u, _cross(z, u))


@dataclasses.dataclass(frozen=True)
class Params:
    """Crank inputs in mm. Field order and defaults are the gallery's Params605ZZ."""

    shaft_diameter: float = 5.0  # ballbearing.Params605ZZ().BoreDiameter
    flat_depth: float = 0.5
    bore_clearance: float = 0.05  # ballbearing.PressFitClearance
    throw: float = 55.0
    placement: Frame | None = None
    # Add-in option, off by default, not a gallery input: cut the pin in two along the plane through its axis
    # (docs/crankhandle/directives.md).
    split_pin: bool = False


def default_params() -> Params:
    return Params()


def params_605zz() -> Params:
    return Params()


def params_6082rs() -> Params:
    """The hand-crank siren's crank: the 8 mm shaft of a 608-2RS bearing with a 0.75 mm flat."""
    return Params(shaft_diameter=8.0, flat_depth=0.75)


@dataclasses.dataclass(frozen=True)
class Dimensions:
    """Values derived from Params, in the local frame [params.go Dimensions]."""

    bore_radius: float  # r_b
    bore_flat: float  # f_b: distance from the axis to the bore's flat, on the +Y side
    bore_loop: float  # length of the bore's outline in the back face
    site: Site  # the pin bolt
    cross_sites: tuple[Site, Site]  # the two cross bolts that clamp the pin's halves
    clamp_y: float  # the clamp bolt's axis
    side_end: float  # where the arm's sides stop being straight
    reach: float  # how far the end arc runs behind the shaft axis
    clamp_site: Site  # the clamp bolt

    def corner_center(self) -> Point:
        """Centre of the right corner arc; the left one is its mirror in x = 0."""
        return (ARM_RADIUS - CLAMP_CORNER_R, self.side_end)

    def end_center(self) -> Point:
        """Centre of the end arc, which touches both corner arcs from inside."""
        dx = ARM_RADIUS - CLAMP_CORNER_R
        return (0.0, self.side_end + math.sqrt((CLAMP_END_R - CLAMP_CORNER_R) ** 2 - dx * dx))
