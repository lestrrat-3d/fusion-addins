"""Meshing phase angles. Own copy of decad-gallery models/planetarygearbox phase.go."""

from __future__ import annotations

import math

from .params import Params


def planet_orbit_angle(p: Params, i: int) -> float:
    """Orbit angle of planet i about the gearbox axis."""
    return 2 * math.pi * i / p.planet_count


def planet_tooth_angle(p: Params, i: int) -> float:
    """Turn of planet i's tooth zero about its own axis."""
    zs, zp = float(p.sun_teeth), float(p.planet_teeth)
    return ((zs + zp) * planet_orbit_angle(p, i) + math.pi * (zp - 1)) / zp


def ring_tooth_angle(p: Params) -> float:
    """Turn of the ring's tooth-space tool about the axis, reduced to one tooth pitch."""
    pitch = 2 * math.pi / p.ring_teeth
    angle = math.fmod(math.pi * (p.planet_teeth - 1) / p.ring_teeth, pitch)
    if angle < 0:
        angle += pitch
    if angle < 1e-12 or pitch - angle < 1e-12:
        return 0.0
    return angle
