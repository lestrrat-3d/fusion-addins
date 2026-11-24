"""Segments, the truth table and the stations. Own copy of decad-gallery models/sevensegment params.go."""

from __future__ import annotations

from .constants import SEGMENT_SPAN, STATION_PITCH

SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G = range(7)
SEGMENTS: tuple[int, ...] = (SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G)
SEGMENT_NAMES = "abcdefg"

# The segments by station index i: d, e, c, g, b, f, a.
STATION_ORDER: tuple[int, ...] = (SEG_D, SEG_E, SEG_C, SEG_G, SEG_B, SEG_F, SEG_A)

# Lit segments a..g of each digit. The box stands on its back wall with the button end up, so the model's segment a,
# at +Y, is the bottom of the digit as the viewer reads it: the roles of a and d, b and e, and c and f are swapped
# against the usual order, and each digit reads upright.
_X, _O = True, False
TRUTH: tuple[tuple[bool, ...], ...] = (
    (_X, _X, _X, _X, _X, _X, _O),
    (_O, _O, _O, _O, _X, _X, _O),
    (_X, _X, _O, _X, _X, _O, _X),
    (_X, _O, _O, _X, _X, _X, _X),
    (_O, _O, _X, _O, _X, _X, _X),
    (_X, _O, _X, _X, _O, _X, _X),
    (_X, _X, _X, _X, _O, _X, _X),
    (_O, _O, _O, _X, _X, _X, _O),
    (_X, _X, _X, _X, _X, _X, _X),
    (_X, _O, _X, _X, _X, _X, _X),
)


def segment_name(s: int) -> str:
    """"a" to "g"."""
    if s < SEG_A or s > SEG_G:
        return f"Segment({s})"
    return SEGMENT_NAMES[s]


def lit(digit: int, s: int) -> bool:
    """True when segment s is raised for digit. Raises ValueError with the gallery's message."""
    if digit < 0 or digit > 9:
        raise ValueError(f"sevensegment: digit {digit} out of range 0..9")
    if s < SEG_A or s > SEG_G:
        raise ValueError(f"sevensegment: segment {s} out of range")
    return TRUTH[digit][s]


def station(s: int) -> float:
    """The Y of segment s's slider centre plane: -SEGMENT_SPAN + STATION_PITCH i, i in the order d, e, c, g, b, f, a."""
    return -SEGMENT_SPAN + STATION_PITCH * STATION_ORDER.index(s)
