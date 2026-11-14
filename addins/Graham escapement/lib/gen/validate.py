"""Escapement input validation.

Own copy of decad-gallery models/escapement params.go Validate at 45b5875.

Deviation: messages are the gallery's without the `escapement: ` prefix, because the dialog shows them on its own
(docs/escapement/deviations.md).
"""

from __future__ import annotations

import math

from .constants import DEG
from .params import Params, frame_is_valid
from .report import fmt_num


class ValidationError(ValueError):
    pass


def validate(p: Params) -> None:
    """Raise ValidationError with the first failing rule's message."""
    # (name, value, lo, hi, hi_is_open); angle bounds use the same `<degrees> * DEG` expression as the Go code.
    fields = (
        ("PendulumLength", p.pendulum_length, 120.0, 250.0, False),
        ("LockAngle", p.lock_angle, 1.25 * DEG, 1.5 * DEG, False),
        ("LiftAngle", p.lift_angle, 2 * DEG, 3 * DEG, False),
        ("Phase", p.phase, 0.0, 1.0, True),
        ("Backlash", p.backlash, 0.0, 0.3, False),
    )
    for name, v, lo, hi, open_hi in fields:
        if math.isnan(v) or math.isinf(v):
            raise ValidationError(f"{name} must be finite, got {fmt_num(v)}")
        if v < lo or v > hi or (open_hi and v >= hi):
            raise ValidationError(f"{name} {fmt_num(v)} is outside its range [{fmt_num(lo)}, {fmt_num(hi)}]")
    if math.isnan(p.amplitude) or math.isinf(p.amplitude):
        raise ValidationError(f"Amplitude must be finite, got {fmt_num(p.amplitude)}")
    lo = (p.lift_angle + p.lock_angle) / 2 + DEG
    hi = 6 * DEG
    # A small slack keeps the exact range ends valid despite rounding.
    if p.amplitude < lo - 1e-12 or p.amplitude > hi + 1e-12:
        raise ValidationError(f"Amplitude {fmt_num(p.amplitude)} is outside its range [{fmt_num(lo)}, {fmt_num(hi)}]")
    if p.placement is not None and not frame_is_valid(p.placement):
        raise ValidationError("Placement must be a valid frame")
