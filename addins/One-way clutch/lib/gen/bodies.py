"""The clutch's bodies and their containers, and the check that stands in for decad VerifyContainers.

Own copy of the body and container layout of decad-gallery models/onewayclutch onewayclutch.go (Build) and adapter.go
(BuildAdapter).
"""

from __future__ import annotations

import dataclasses
import re

from .fasteners import Site
from .params import Dimensions

TOP_NAME = "One-way clutch"  # the add-in's top component; stands for the gallery document's root container

HUB_CONTAINER = "Hub"
RING_CONTAINER = "Ring"
PLATES_CONTAINER = "Plates"
BOLTS_CONTAINER = "Bolts"
NUTS_CONTAINER = "Nuts"
ADAPTER_CONTAINER = "Adapter"
CONTAINERS: tuple[str, ...] = (HUB_CONTAINER, RING_CONTAINER, PLATES_CONTAINER, BOLTS_CONTAINER, NUTS_CONTAINER)
ADAPTER_CONTAINERS: tuple[str, ...] = CONTAINERS + (ADAPTER_CONTAINER,)

HUB = "Hub"
RING = "Ring"
BACK_PLATE = "Back Plate"
COVER = "Cover"
ADAPTER = "Adapter"
BOLTS: tuple[str, ...] = ("Bolt 1", "Bolt 2", "Bolt 3")
NUTS: tuple[str, ...] = ("Nut 1", "Nut 2", "Nut 3")
MOUNT_BOLTS: tuple[str, ...] = ("Mount Bolt 1", "Mount Bolt 2", "Mount Bolt 3")
MOUNT_NUTS: tuple[str, ...] = ("Mount Nut 1", "Mount Nut 2", "Mount Nut 3")

PRINTED: tuple[str, ...] = (HUB, RING, BACK_PLATE, COVER)
BODY_NAMES: tuple[str, ...] = PRINTED + BOLTS + NUTS  # 10
ADAPTER_BODY_NAMES: tuple[str, ...] = (ADAPTER,) + MOUNT_BOLTS + MOUNT_NUTS  # 7

BODY_CONTAINER: dict[str, str] = {
    HUB: HUB_CONTAINER,
    RING: RING_CONTAINER,
    BACK_PLATE: PLATES_CONTAINER,
    COVER: PLATES_CONTAINER,
    ADAPTER: ADAPTER_CONTAINER,
    **{n: BOLTS_CONTAINER for n in BOLTS + MOUNT_BOLTS},
    **{n: NUTS_CONTAINER for n in NUTS + MOUNT_NUTS},
}


def body_names(adapter: bool) -> tuple[str, ...]:
    """The bodies of a build in build order: the clutch's ten, then the adapter's seven when `adapter`."""
    return BODY_NAMES + ADAPTER_BODY_NAMES if adapter else BODY_NAMES


def containers(adapter: bool) -> tuple[str, ...]:
    return ADAPTER_CONTAINERS if adapter else CONTAINERS


def expected_count(adapter: bool) -> int:
    return len(body_names(adapter))


def is_bolt(name: str) -> bool:
    return name in BOLTS or name in MOUNT_BOLTS


def is_nut(name: str) -> bool:
    return name in NUTS or name in MOUNT_NUTS


def site_of(name: str, dm: Dimensions) -> Site:
    """The site of a bolt or a nut. Raises KeyError for a printed part."""
    sites: dict[str, Site] = {}
    for i in range(3):
        sites[BOLTS[i]] = sites[NUTS[i]] = dm.sites[i]
        sites[MOUNT_BOLTS[i]] = sites[MOUNT_NUTS[i]] = dm.mount_sites[i]
    return sites[name]


def expected_bodies(adapter: bool) -> dict[str, list[str]]:
    """Body names per container, in container order."""
    out: dict[str, list[str]] = {c: [] for c in containers(adapter)}
    for name in body_names(adapter):
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


def check_tree(found: list[Found], top_bodies: int, adapter: bool) -> tuple[ContainerResult, list[ContainerResult]]:
    """The top-level result, then one result per container [VerifyContainers].

    Top: no body directly in the top component, and its children are exactly the container names, once each."""
    names = containers(adapter)
    found = [dataclasses.replace(f, name=base_name(f.name)) for f in found]
    have = [f.name for f in found]
    parts: list[str] = []
    if top_bodies > 0:
        parts.append(f"{top_bodies} bodies outside containers")
    missing = [n for n in names if n not in have]
    extra = [n for n in have if n not in names]
    duplicate = sorted({n for n in have if have.count(n) > 1})
    if missing:
        parts.append(_names("missing container", missing))
    if extra:
        parts.append(_names("extra container", extra))
    if duplicate:
        parts.append(_names("duplicate container", duplicate))
    top = ContainerResult("", top_bodies, 0, not parts, "; ".join(parts))

    want_bodies = expected_bodies(adapter)
    results: list[ContainerResult] = []
    for name in names:
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
