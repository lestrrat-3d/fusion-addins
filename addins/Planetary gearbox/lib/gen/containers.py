"""Body containers of the gearbox and the check that stands in for decad VerifyContainers.

Own copy of decad-gallery models/planetarygearbox container.go (container names, moveBodies) and container_test.go
(requireContainers) at a800069.
"""

from __future__ import annotations

import dataclasses

from . import layout
from .dims import Dims
from .params import Params

GEARBOX_NAME = "Planetary Gearbox"  # the add-in's top component; stands for the gallery document's root container
HOUSING = "Housing"
COVER_BEARINGS = "Cover Bearings"
SUN_GEARS = "Sun Gears"
PLANET_GEARS = "Planet Gears"
PLANET_BEARINGS = "Planet Bearings"
CARRIERS = "Carriers"
SHAFTS = "Shafts"
BOLTS = "Bolts"
NUTS = "Nuts"
# Order of the first ChildNamed call per container in moveBodies.
CONTAINER_NAMES: tuple[str, ...] = (
    HOUSING,
    COVER_BEARINGS,
    BOLTS,
    NUTS,
    SHAFTS,
    SUN_GEARS,
    PLANET_GEARS,
    PLANET_BEARINGS,
    CARRIERS,
)
PART_CONTAINERS: dict[str, str] = {
    "ring": HOUSING,
    "cover": HOUSING,
    "housing_bearing": COVER_BEARINGS,
    "input_shaft": SHAFTS,
    "bolt": BOLTS,
    "nut": NUTS,
    "sun": SUN_GEARS,
    "planet": PLANET_GEARS,
    "planet_bearing": PLANET_BEARINGS,
    "carrier": CARRIERS,
    "link_shaft": SHAFTS,
    "output_shaft": SHAFTS,
}


def container_of(part: str) -> str:
    """Container name of a part. Raises KeyError for an unknown part."""
    return PART_CONTAINERS[part]


def expected_bodies(p: Params, d: Dims) -> dict[str, list[str]]:
    """Body names per container, keys in CONTAINER_NAMES order, bodies in layout order."""
    out: dict[str, list[str]] = {name: [] for name in CONTAINER_NAMES}
    for inst in layout.instances(p, d):
        out[PART_CONTAINERS[inst.part]].append(inst.name)
    return out


@dataclasses.dataclass(frozen=True)
class Found:
    """One child component of the top component, as read from Fusion."""

    name: str
    bodies: tuple[str, ...]  # body names directly in that component
    children: int  # number of occurrences inside that component


@dataclasses.dataclass(frozen=True)
class RootResult:
    bodies: int  # bodies directly in the top component
    containers: int  # number of child components found
    expected: int  # len(CONTAINER_NAMES)
    ok: bool
    detail: str  # "" when ok


@dataclasses.dataclass(frozen=True)
class ContainerResult:
    name: str
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


def check_root(found: list[Found], root_bodies: int) -> RootResult:
    """No body outside the containers; the child components are exactly the container names [VerifyContainers]."""
    names = [f.name for f in found]
    missing = [n for n in CONTAINER_NAMES if n not in names]
    extra = [n for n in names if n not in CONTAINER_NAMES]
    duplicate = sorted({n for n in names if names.count(n) > 1})
    parts: list[str] = []
    if root_bodies > 0:
        parts.append(f"{root_bodies} bodies outside containers")
    if missing:
        parts.append(_names("missing", missing))
    if extra:
        parts.append(_names("extra", extra))
    if duplicate:
        parts.append(_names("duplicate", duplicate))
    return RootResult(root_bodies, len(found), len(CONTAINER_NAMES), not parts, "; ".join(parts))


def check_containers(found: list[Found], expected: dict[str, list[str]]) -> list[ContainerResult]:
    """One result per container: its bodies are exactly the expected names [requireContainers]."""
    out: list[ContainerResult] = []
    for name, want in expected.items():
        hits = [f for f in found if f.name == name]
        if not hits:
            out.append(ContainerResult(name, 0, len(want), False, "no component"))
            continue
        if len(hits) > 1:
            out.append(
                ContainerResult(name, sum(len(h.bodies) for h in hits), len(want), False, f"{len(hits)} components")
            )
            continue
        f = hits[0]
        parts: list[str] = []
        if f.children > 0:
            parts.append(f"{f.children} child components")
        if len(set(f.bodies)) != len(f.bodies):
            parts.append("duplicate body names")
        missing = sorted(set(want) - set(f.bodies))
        if missing:
            parts.append(_names("missing", missing))
        extra = sorted(set(f.bodies) - set(want))
        if extra:
            parts.append(_names("extra", extra))
        out.append(ContainerResult(name, len(f.bodies), len(want), not parts, "; ".join(parts)))
    return out
