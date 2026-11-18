"""The stand's bodies and their containers, and the check that stands in for decad VerifyContainers.

Own copy of the body and container layout of decad-gallery models/plaquestand plaquestand.go (Build).
"""

from __future__ import annotations

import dataclasses
import re

from .fasteners import Site
from .params import Dimensions

TOP_NAME = "Plaque stand"  # the add-in's top component; stands for the gallery document's root container

BRACKETS_CONTAINER = "Brackets"
RAIL_CONTAINER = "Rail"
BOLTS_CONTAINER = "Bolts"
NUTS_CONTAINER = "Nuts"
PLAQUE_CONTAINER = "Plaque"
CONTAINERS: tuple[str, ...] = (
    BRACKETS_CONTAINER, RAIL_CONTAINER, BOLTS_CONTAINER, NUTS_CONTAINER, PLAQUE_CONTAINER,
)

BRACKET_1 = "Bracket 1"
BRACKET_2 = "Bracket 2"
RAIL = "Rail"
BOLT_1 = "Bolt 1"
BOLT_2 = "Bolt 2"
NUT_1 = "Nut 1"
NUT_2 = "Nut 2"
PLAQUE = "Plaque"

BRACKETS: tuple[str, ...] = (BRACKET_1, BRACKET_2)
BOLTS: tuple[str, ...] = (BOLT_1, BOLT_2)
NUTS: tuple[str, ...] = (NUT_1, NUT_2)
PRINTED: tuple[str, ...] = BRACKETS + (RAIL,)
BODY_NAMES: tuple[str, ...] = BRACKETS + (RAIL,) + BOLTS + NUTS + (PLAQUE,)
EXPECTED_BODY_COUNT = len(BODY_NAMES)  # 8

BODY_CONTAINER: dict[str, str] = {
    BRACKET_1: BRACKETS_CONTAINER, BRACKET_2: BRACKETS_CONTAINER, RAIL: RAIL_CONTAINER,
    BOLT_1: BOLTS_CONTAINER, BOLT_2: BOLTS_CONTAINER, NUT_1: NUTS_CONTAINER, NUT_2: NUTS_CONTAINER,
    PLAQUE: PLAQUE_CONTAINER,
}


def is_bolt(name: str) -> bool:
    return name in BOLTS


def is_nut(name: str) -> bool:
    return name in NUTS


def site_of(name: str, dm: Dimensions) -> Site:
    """The site of a bolt or a nut. Raises KeyError for any other body."""
    return {BOLT_1: dm.sites[0], BOLT_2: dm.sites[1], NUT_1: dm.sites[0], NUT_2: dm.sites[1]}[name]


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
