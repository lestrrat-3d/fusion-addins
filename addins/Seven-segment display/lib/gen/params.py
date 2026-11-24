"""Seven-segment display inputs, derived dimensions and the placement frame.

Own copy of decad-gallery models/sevensegment params.go (Params, Validate, Derive, Dimensions, sites) and of the
placement rules of the other add-ins (a point and an axis instead of an r3.Frame).
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    FACE_Z,
    FLANGE_FROM,
    FRAME_BOLT_X,
    FRONT_INNER_Y,
    GUIDE_TOP,
    HOUSING_BASE_THICK,
    HOUSING_BASE_Y,
    LEDGE_FROM,
    SHAFT_Z,
)
from .fasteners import NUT_CAVITY_HEIGHT, Site
from .ramps import Ramp

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
    in the dialog (docs/sevensegment/deviations.md). U is a stable unit vector perpendicular to the axis (Y x axis, or
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
    """Seven-segment display inputs. Field order and defaults are the gallery's DefaultParams."""

    digit: int = 2  # the digit shown, 0..9: sets the camshaft angle 36 * digit and every slider's height
    placement: Frame | None = None  # None keeps the model's world frame


def default_params() -> Params:
    return Params()


@dataclasses.dataclass(frozen=True)
class Dimensions:
    """Values derived from Params [params.go Dimensions]."""

    digit: int
    theta: float  # camshaft angle, degrees
    ramps: tuple[tuple[Ramp, ...], ...]  # indexed by segment, in increasing start
    sites: tuple[Site, ...]  # T1..T4, G1..G4, H1, H2 in the model frame, before the placement


def flag_sites() -> tuple[Site, ...]:
    """The four T bolts of the flag mechanism: heads on the display face, M2 x 16, clamping the top plate and the
    cradle to the top flange ribs [frame flagframe.go flagSites]. Order: -x front, +x front, -x rear, +x rear."""
    out = []
    y0, y1 = -66.75, 57.0
    for x, y in ((-FRAME_BOLT_X, y0), (FRAME_BOLT_X, y0), (-FRAME_BOLT_X, y1), (FRAME_BOLT_X, y1)):
        out.append(Site(head=(x, y, FACE_Z), dir=(0.0, 0.0, -1.0), corner=(0.0, 1.0, 0.0),
                        length=16.0, cavity=FACE_Z - FLANGE_FROM - NUT_CAVITY_HEIGHT))
    return tuple(out)


def sites() -> tuple[Site, ...]:
    """T1..T4, G1..G4, H1, H2."""
    out = list(flag_sites())
    # G3/G4 at y 32 stand between the discs of cams f and a, so no cam lies under their heads.
    gy = (-51.3, -51.3, 48.0, 48.0)
    xs = (-FRAME_BOLT_X, FRAME_BOLT_X, -FRAME_BOLT_X, FRAME_BOLT_X)
    for x, y in zip(xs, gy):
        out.append(Site(head=(x, y, LEDGE_FROM), dir=(0.0, 0.0, 1.0), corner=(0.0, 1.0, 0.0),
                        length=10.0, cavity=GUIDE_TOP - LEDGE_FROM - NUT_CAVITY_HEIGHT))
    # H1, H2 hold the click indexer's housing on the front wall: the head sinks in the housing's base, the nut sits in
    # a hex pocket open to the wall's inner face. The click indexer keeps its size, so its bolts do.
    for x in (-21.0, 21.0):
        out.append(Site(head=(x, HOUSING_BASE_Y - HOUSING_BASE_THICK, SHAFT_Z), dir=(0.0, 1.0, 0.0),
                        corner=(0.0, 0.0, 1.0), length=16.0,
                        cavity=FRONT_INNER_Y - (HOUSING_BASE_Y - HOUSING_BASE_THICK) - NUT_CAVITY_HEIGHT))
    return tuple(out)
