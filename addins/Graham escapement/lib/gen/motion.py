"""Closed-form pose of the escapement at a phase of the pendulum period.

Own copy of decad-gallery models/escapement motion.go at e11a188. The wheel, anchor and pendulum angles are
clockwise-positive seen from +Z; the great wheel angle is counterclockwise.
"""

from __future__ import annotations

import dataclasses
import math

from .constants import CRUTCH_LENGTH, GREAT_TEETH, PINION_TEETH, SUSPENSION_OFFSET, TIP_RADIUS
from .layout import Geometry, add, layout, rot
from .params import Params

LOCKED_ENTRY = "entry"
LOCKED_EXIT = "exit"
LOCKED_NONE = ""


@dataclasses.dataclass(frozen=True)
class State:
    phase: float
    anchor_angle: float  # psi
    wheel_angle: float  # phi
    pendulum_angle: float  # beta
    great_wheel_angle: float  # phi * 13 / 48, counterclockwise
    locked: str


def pendulum_angle(psi: float) -> float:
    """The pendulum angle beta for anchor angle psi."""
    return math.atan2(CRUTCH_LENGTH * math.sin(psi), SUSPENSION_OFFSET + CRUTCH_LENGTH * math.cos(psi))


def _tip_on_pallet(g: Geometry, c: tuple[float, float], f: tuple[float, float], psi: float) -> float:
    """Math angle about O where the tip circle meets the impulse face from corner c to corner f at anchor angle psi."""
    a = add(g.axis_p, rot(c, -psi))
    b = add(g.axis_p, rot(f, -psi))
    dx, dy = b[0] - a[0], b[1] - a[1]
    qa = dx * dx + dy * dy
    qb = 2 * (a[0] * dx + a[1] * dy)
    qc = a[0] * a[0] + a[1] * a[1] - TIP_RADIUS * TIP_RADIUS
    disc = qb * qb - 4 * qa * qc
    if disc < 0:
        raise ValueError(f"the impulse face misses the tip circle at anchor angle {psi!r}")
    root = math.sqrt(disc)
    for s in ((-qb - root) / (2 * qa), (-qb + root) / (2 * qa)):
        if -1e-9 <= s <= 1 + 1e-9:
            return math.atan2(a[1] + dy * s, a[0] + dx * s)
    raise ValueError(f"the impulse face does not reach the tip circle at anchor angle {psi!r}")


def wheel_at(g: Geometry, psi: float, increasing: bool) -> tuple[float, str]:
    """Wheel angle and lock state at anchor angle psi on the swing that increases psi (increasing) or decreases it."""
    eps = 1e-12
    il_a = math.atan2(g.il[1], g.il[0])
    ir_a = math.atan2(g.ir[1], g.ir[0])
    if increasing:
        if psi < g.psi_eu:
            return g.wheel_phase_e, LOCKED_ENTRY
        if psi > g.psi_ef:
            return g.wheel_phase_x, LOCKED_EXIT
        q = _tip_on_pallet(g, g.ce, g.fe, psi)
        if abs(psi - g.psi_eu) < eps:
            return g.wheel_phase_e, LOCKED_ENTRY
        return g.wheel_phase_e + il_a - q, LOCKED_NONE
    if psi > g.psi_xu:
        return g.wheel_phase_x, LOCKED_EXIT
    if psi < g.psi_xf:
        return g.wheel_phase_e + g.pitch, LOCKED_ENTRY
    q = _tip_on_pallet(g, g.cx, g.fx, psi)
    if abs(psi - g.psi_xu) < eps:
        return g.wheel_phase_x, LOCKED_EXIT
    return g.wheel_phase_x + ir_a - q, LOCKED_NONE


def state_at(g: Geometry, t: float) -> State:
    """The state at phase t of the geometry's amplitude."""
    psi = -g.params.amplitude * math.cos(2 * math.pi * t)
    phi, locked = wheel_at(g, psi, t <= 0.5)
    return State(t, psi, phi, pendulum_angle(psi), phi * PINION_TEETH / GREAT_TEETH, locked)


def motion(p: Params) -> State:
    """The closed-form state at p.phase."""
    return state_at(layout(p), p.phase)
