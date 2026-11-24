"""Log-line formatting, Go-style number printing and the line logger used by the build checks.

Not geometry, but stdlib-only and unit-testable, so it lives in the geometry package.
"""

from __future__ import annotations

import dataclasses
import decimal
import json
import math
import re
from collections.abc import Callable

_BARE = re.compile(r"[A-Za-z0-9_.:+-]+")


def fmt_num(v: float) -> str:
    """Format v like Go's %v for float64 (6 -> "6", 3.4 -> "3.4", 1e6 -> "1e+06")."""
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "+Inf" if v > 0 else "-Inf"
    if v == 0:
        return "0"
    d = decimal.Decimal(repr(float(v))).normalize()
    sign, digits, exp = d.as_tuple()
    assert isinstance(exp, int)
    x = len(digits) + exp - 1
    prefix = "-" if sign else ""
    if -4 <= x < 6:
        return prefix + format(abs(d), "f")
    ds = "".join(str(i) for i in digits)
    mantissa = ds[0] + ("." + ds[1:] if len(ds) > 1 else "")
    return f"{prefix}{mantissa}e{'+' if x >= 0 else '-'}{abs(x):02d}"


def _g(v: float) -> str:
    return "%.6g" % v


def fmt_field(v: object) -> str:
    """Format one log field value."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return _g(v)
    if isinstance(v, (tuple, list)):
        return "(" + ",".join(_g(float(i)) for i in v) + ")"  # pyright: ignore[reportUnknownArgumentType]
    s = str(v)
    if _BARE.fullmatch(s):
        return s
    return json.dumps(s)


def format_record(event: str, fields: list[tuple[str, object]]) -> str:
    """Return "event k=v k=v" with fields in the given order."""
    return " ".join([event] + [f"{k}={fmt_field(v)}" for k, v in fields])


@dataclasses.dataclass(frozen=True)
class Expect:
    value: float
    tol: float  # pass when |actual - value| <= tol


def within(actual: float, expect: Expect) -> bool:
    return abs(actual - expect.value) <= expect.tol


class SinkLog:
    """Formats records as log lines and passes each line to sink (in Fusion: a Text Commands writer)."""

    enabled = True

    def __init__(self, sink: Callable[[str], None]) -> None:
        self._sink = sink

    def write(self, event: str, fields: list[tuple[str, object]]) -> None:
        self._sink(format_record(event, fields))

    def close(self) -> None:
        pass


class NullLog:
    enabled = False

    def write(self, event: str, fields: list[tuple[str, object]]) -> None:
        pass

    def close(self) -> None:
        pass
