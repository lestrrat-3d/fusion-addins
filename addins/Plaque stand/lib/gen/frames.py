"""Rigid frames as (origin, x, y, z) tuples, and the change of frame a move feature needs.

Fusion applies a move feature's transform in the top-level (assembly) frame, not in the frame of the component that
holds the body. A body in a component whose occurrence has the transform W, moved by the transform M of the component
frame, must be given W M W^-1: Fusion then applies W^-1 (W M W^-1) W = M to the body's own coordinates. For a move
that only translates, W M W^-1 and M agree when W is a pure translation, which is why those moves came out right while
rotated moves came out displaced by (R - I) times W's translation.
"""

from __future__ import annotations

Vec3 = tuple[float, float, float]
Axes = tuple[Vec3, Vec3, Vec3, Vec3]  # (origin, x, y, z); the columns of the rotation are x, y and z


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _rotate(a: Axes, v: Vec3) -> Vec3:
    """a's rotation applied to v."""
    _, x, y, z = a
    return (
        x[0] * v[0] + y[0] * v[1] + z[0] * v[2],
        x[1] * v[0] + y[1] * v[1] + z[1] * v[2],
        x[2] * v[0] + y[2] * v[1] + z[2] * v[2],
    )


def apply(a: Axes, p: Vec3) -> Vec3:
    """The point p moved by the frame a: origin + R p."""
    r = _rotate(a, p)
    o = a[0]
    return (o[0] + r[0], o[1] + r[1], o[2] + r[2])


def compose(a: Axes, b: Axes) -> Axes:
    """The frame that applies b first, then a."""
    return (apply(a, b[0]), _rotate(a, b[1]), _rotate(a, b[2]), _rotate(a, b[3]))


def inverse(a: Axes) -> Axes:
    o, x, y, z = a
    inv_x: Vec3 = (x[0], y[0], z[0])
    inv_y: Vec3 = (x[1], y[1], z[1])
    inv_z: Vec3 = (x[2], y[2], z[2])
    return ((-_dot(x, o), -_dot(y, o), -_dot(z, o)), inv_x, inv_y, inv_z)


def conjugate(move: Axes, occurrence: Axes) -> Axes:
    """The transform to give Fusion's move feature so that a body of a component placed by `occurrence` is moved by
    `move` in the component's own frame: W M W^-1."""
    return compose(compose(occurrence, move), inverse(occurrence))
