"""Seven-segment display input validation and the derived dimensions.

Own copy of decad-gallery models/sevensegment params.go Validate and Derive. The messages are the gallery's, with the
`sevensegment: ` prefix.
"""

from __future__ import annotations

from .params import Dimensions, Params, frame_is_valid, sites
from .ramps import ramps_for
from .truth import SEGMENTS


class ValidationError(ValueError):
    pass


def validate(p: Params) -> None:
    """Raise ValidationError with the first failing rule's message: digit, then placement."""
    if p.digit < 0 or p.digit > 9:
        raise ValidationError(f"sevensegment: digit {p.digit} out of range 0..9")
    if p.placement is not None and not frame_is_valid(p.placement):
        raise ValidationError("sevensegment: invalid placement frame")


def derive(p: Params) -> Dimensions:
    """Validate p, then compute the ramps and the fastener sites."""
    validate(p)
    all_sites = sites()
    for i, s in enumerate(all_sites):
        msg = s.validate()
        if msg:
            raise ValidationError(f"sevensegment: site {i + 1}: {msg}")
    return Dimensions(digit=p.digit, theta=36.0 * p.digit, ramps=tuple(ramps_for(s) for s in SEGMENTS), sites=all_sites)
