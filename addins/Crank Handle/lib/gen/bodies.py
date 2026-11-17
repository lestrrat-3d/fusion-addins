"""The crank's bodies and their containers, and the check that stands in for decad VerifyContainers.

Own copy of the body and container layout of decad-gallery models/crankhandle crankhandle.go (Build).
"""

from __future__ import annotations

import dataclasses
import re

from .params import Dimensions
from .fasteners import Site

TOP_NAME = "Crank Handle"  # the add-in's top component; stands for the gallery document's root container

# Container names, one per kind of body.
ARM_CONTAINER = "Arm"
PIN_CONTAINER = "Pin"
HANDLE_CONTAINER = "Handle"
BOLTS_CONTAINER = "Bolts"
NUTS_CONTAINER = "Nuts"
CONTAINERS: tuple[str, ...] = (ARM_CONTAINER, PIN_CONTAINER, HANDLE_CONTAINER, BOLTS_CONTAINER, NUTS_CONTAINER)

# Body names in build order: the printed parts, then each bolt and its nut's names in the same order.
ARM = "Arm"
PIN = "Pin"
HANDLE = "Handle"
PIN_BOLT = "Pin Bolt"
CROSS_BOLT_1 = "Cross Bolt 1"
CROSS_BOLT_2 = "Cross Bolt 2"
CLAMP_BOLT_1 = "Clamp Bolt 1"
CLAMP_BOLT_2 = "Clamp Bolt 2"
PIN_NUT = "Pin Nut"
CROSS_NUT_1 = "Cross Nut 1"
CROSS_NUT_2 = "Cross Nut 2"
CLAMP_NUT_1 = "Clamp Nut 1"
CLAMP_NUT_2 = "Clamp Nut 2"

# The pin's two printed halves when the `Split pin` option is on: the half on the -Y side of the plane through the
# pin's axis (toward the shaft, holding the cross bolts' nuts), then the half on the +Y side (the head pockets).
PIN_HALVES: tuple[str, str] = ("Pin Half 1", "Pin Half 2")

PRINTED: tuple[str, ...] = (ARM, PIN, HANDLE)
BOLTS: tuple[str, ...] = (PIN_BOLT, CROSS_BOLT_1, CROSS_BOLT_2, CLAMP_BOLT_1, CLAMP_BOLT_2)
NUTS: tuple[str, ...] = (PIN_NUT, CROSS_NUT_1, CROSS_NUT_2, CLAMP_NUT_1, CLAMP_NUT_2)
BODY_NAMES: tuple[str, ...] = PRINTED + BOLTS + NUTS
EXPECTED_BODY_COUNT = len(BODY_NAMES)  # 13

BODY_CONTAINER: dict[str, str] = {
    ARM: ARM_CONTAINER,
    PIN: PIN_CONTAINER,
    HANDLE: HANDLE_CONTAINER,
    **{n: BOLTS_CONTAINER for n in BOLTS},
    **{n: NUTS_CONTAINER for n in NUTS},
}


def is_bolt(name: str) -> bool:
    return name in BOLTS


def is_nut(name: str) -> bool:
    return name in NUTS


def site_of(name: str, dm: Dimensions) -> Site:
    """The site of a bolt or a nut. Raises KeyError for a printed part."""
    sites = {
        PIN_BOLT: dm.site, CROSS_BOLT_1: dm.cross_sites[0], CROSS_BOLT_2: dm.cross_sites[1],
        CLAMP_BOLT_1: dm.clamp_sites[0], CLAMP_BOLT_2: dm.clamp_sites[1],
        PIN_NUT: dm.site, CROSS_NUT_1: dm.cross_sites[0], CROSS_NUT_2: dm.cross_sites[1],
        CLAMP_NUT_1: dm.clamp_sites[0], CLAMP_NUT_2: dm.clamp_sites[1],
    }
    return sites[name]


def expected_bodies() -> dict[str, list[str]]:
    """Body names per container, in CONTAINERS order."""
    out: dict[str, list[str]] = {c: [] for c in CONTAINERS}
    for name in BODY_NAMES:
        out[BODY_CONTAINER[name]].append(name)
    return out


_NUMBERED = re.compile(r" \(\d+\)$")


def base_name(name: str) -> str:
    """A component name without the ` (n)` that Fusion appends when another component already has the name."""
    return _NUMBERED.sub("", name)


@dataclasses.dataclass(frozen=True)
class Found:
    """One descendant component of the top component, as read from Fusion."""

    name: str
    bodies: tuple[str, ...]  # body names directly in that component
    children: tuple[str, ...]  # names of the components directly inside it


@dataclasses.dataclass(frozen=True)
class ContainerResult:
    name: str  # "" for the top component
    bodies: int
    expected: int
    ok: bool
    detail: str  # "" when ok


def _names(label: str, names: list[str]) -> str:
    shown = sorted(names)[:3]
    text = label + " " + ", ".join(shown)
    if len(names) > 3:
        text += f" +{len(names) - 3}"
    return text


def check_tree(found: list[Found], top_bodies: int) -> tuple[ContainerResult, list[ContainerResult]]:
    """The top-level result, then one result per container [VerifyContainers].

    Top: no body directly in the top component, and its children are exactly the container names, once each."""
    found = [dataclasses.replace(f, name=base_name(f.name)) for f in found]
    have = [f.name for f in found]
    parts: list[str] = []
    if top_bodies > 0:
        parts.append(f"{top_bodies} bodies outside containers")
    missing = [n for n in CONTAINERS if n not in have]
    extra = [n for n in have if n not in CONTAINERS]
    duplicate = sorted({n for n in have if have.count(n) > 1})
    if missing:
        parts.append(_names("missing container", missing))
    if extra:
        parts.append(_names("extra container", extra))
    if duplicate:
        parts.append(_names("duplicate container", duplicate))
    top = ContainerResult("", top_bodies, 0, not parts, "; ".join(parts))

    want_bodies = expected_bodies()
    results: list[ContainerResult] = []
    for name in CONTAINERS:
        want = want_bodies[name]
        hits = [f for f in found if f.name == name]
        if not hits:
            results.append(ContainerResult(name, 0, len(want), False, "no component"))
            continue
        if len(hits) > 1:
            n = sum(len(h.bodies) for h in hits)
            results.append(ContainerResult(name, n, len(want), False, f"{len(hits)} components"))
            continue
        f = hits[0]
        problems: list[str] = []
        if len(set(f.bodies)) != len(f.bodies):
            problems.append("duplicate body names")
        missing_bodies = sorted(set(want) - set(f.bodies))
        if missing_bodies:
            problems.append(_names("missing", missing_bodies))
        extra_bodies = sorted(set(f.bodies) - set(want))
        if extra_bodies:
            problems.append(_names("extra", extra_bodies))
        if f.children:
            problems.append(_names("extra child", list(f.children)))
        results.append(ContainerResult(name, len(f.bodies), len(want), not problems, "; ".join(problems)))
    return top, results
