"""The fan's bodies and their containers, and the check that stands in for decad VerifyContainers.

Own copy of the body and container layout of decad-gallery models/turbinefan turbinefan.go (Build).
"""

from __future__ import annotations

import dataclasses
import re

from .constants import BLADE_COUNT, CLUTCH_MOUNT
from .fasteners import Site
from .params import Dimensions

TOP_NAME = "Turbine fan"  # the add-in's top component; stands for the gallery document's root container

HUB_CONTAINER = "Hub"
BLADES_CONTAINER = "Blades"
BOLTS_CONTAINER = "Bolts"
NUTS_CONTAINER = "Nuts"
CONTAINERS: tuple[str, ...] = (HUB_CONTAINER, BLADES_CONTAINER, BOLTS_CONTAINER, NUTS_CONTAINER)

HUB = "Hub"
BLADES: tuple[str, ...] = tuple(f"Blade {k}" for k in range(1, BLADE_COUNT + 1))
BLADE_BOLTS: tuple[str, ...] = tuple(f"Blade Bolt {k}" for k in range(1, BLADE_COUNT + 1))
BLADE_NUTS: tuple[str, ...] = tuple(f"Blade Nut {k}" for k in range(1, BLADE_COUNT + 1))
SET_SCREW = "Set Screw"
SET_SCREW_NUT = "Set Screw Nut"
ADAPTER_BOLTS: tuple[str, ...] = ("Adapter Bolt 1", "Adapter Bolt 2")
ADAPTER_NUTS: tuple[str, ...] = ("Adapter Nut 1", "Adapter Nut 2")

PRINTED: tuple[str, ...] = (HUB,) + BLADES


def bolts(mount: int) -> tuple[str, ...]:
    """Bolt names in build order: the blade bolts, then the set screw (shaft mount) or the adapter bolts (clutch)."""
    return BLADE_BOLTS + (ADAPTER_BOLTS if mount == CLUTCH_MOUNT else (SET_SCREW,))


def nuts(mount: int) -> tuple[str, ...]:
    return BLADE_NUTS + (ADAPTER_NUTS if mount == CLUTCH_MOUNT else (SET_SCREW_NUT,))


def body_names(mount: int) -> tuple[str, ...]:
    """Every body in build order: the printed parts, then the bolts, then the nuts."""
    return PRINTED + bolts(mount) + nuts(mount)


def expected_body_count(mount: int) -> int:
    return len(body_names(mount))  # 12 for the shaft mount, 14 for the clutch mount


def container_of(name: str) -> str:
    if name == HUB:
        return HUB_CONTAINER
    if name in BLADES:
        return BLADES_CONTAINER
    if name in BLADE_BOLTS or name == SET_SCREW or name in ADAPTER_BOLTS:
        return BOLTS_CONTAINER
    return NUTS_CONTAINER


def is_bolt(name: str) -> bool:
    return name in BLADE_BOLTS or name == SET_SCREW or name in ADAPTER_BOLTS


def is_nut(name: str) -> bool:
    return name in BLADE_NUTS or name == SET_SCREW_NUT or name in ADAPTER_NUTS


def site_of(name: str, dm: Dimensions) -> Site:
    """The site of a bolt or a nut. Raises KeyError for a printed part."""
    sites: dict[str, Site] = {SET_SCREW: dm.set_screw_site, SET_SCREW_NUT: dm.set_screw_site}
    for k in range(BLADE_COUNT):
        sites[BLADE_BOLTS[k]] = sites[BLADE_NUTS[k]] = dm.blade_sites[k]
    for k in range(2):
        sites[ADAPTER_BOLTS[k]] = sites[ADAPTER_NUTS[k]] = dm.adapter_sites[k]
    return sites[name]


def expected_bodies(mount: int) -> dict[str, list[str]]:
    """Body names per container, in CONTAINERS order."""
    out: dict[str, list[str]] = {c: [] for c in CONTAINERS}
    for name in body_names(mount):
        out[container_of(name)].append(name)
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


def check_tree(found: list[Found], top_bodies: int, mount: int) -> tuple[ContainerResult, list[ContainerResult]]:
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

    want_bodies = expected_bodies(mount)
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
