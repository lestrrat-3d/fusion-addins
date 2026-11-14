"""Escapement inputs, defaults and placement frame.

Own copy of decad-gallery models/escapement params.go (Params, DefaultParams) at 45b5875, and of the gearbox add-in's
validity and axes rules of r3 NewFrame and its two-selection placement.
"""

from __future__ import annotations

import dataclasses
import math

from .constants import DEG

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
    in the dialog (docs/escapement/deviations.md). U is a stable unit vector perpendicular to the axis (Y x axis, or
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
    """Escapement inputs. Field order and defaults are the gallery's DefaultParams. Lengths mm, angles rad."""

    pendulum_length: float = 180.0
    amplitude: float = 5 * DEG
    lock_angle: float = 1.5 * DEG
    lift_angle: float = 2.5 * DEG
    phase: float = 0.25
    backlash: float = 0.15
    placement: Frame | None = None


def default_params() -> Params:
    return Params()
