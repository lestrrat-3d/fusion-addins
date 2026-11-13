"""Body containers of the escapement and the check that stands in for decad VerifyContainers.

Own copy of decad-gallery models/escapement containers.go (container names, moveBodies) at 0067d30, and of the
gearbox add-in's container check, extended to nested containers.
"""

from __future__ import annotations

import dataclasses

from . import bodies as b

Path = tuple[str, ...]

TOP_NAME = "Graham Escapement"  # the add-in's top component; stands for the gallery document's root container

# Creation order: a parent comes before its children.
CONTAINER_PATHS: tuple[Path, ...] = (
    ("Frame",),
    ("Bearings",),
    ("Arbors",),
    ("Escapement",),
    ("Escapement", "Escape Wheel"),
    ("Escapement", "Anchor"),
    ("Pendulum Assembly",),
    ("Pendulum Assembly", "Crutch"),
    ("Pendulum Assembly", "Pendulum"),
    ("Pendulum Assembly", "Suspension"),
    ("Drive",),
    ("Drive", "Great Wheel"),
    ("Drive", "Pawl Carrier"),
    ("Drive", "Mainspring"),
    ("Drive", "Spring Spacer"),
    ("Drive", "Spring Anchor"),
    ("Drive", "Winding Knob"),
    ("Bolts",),
    ("Nuts",),
)
TOP_LEVEL: tuple[str, ...] = ("Frame", "Bearings", "Arbors", "Escapement", "Pendulum Assembly", "Drive", "Bolts", "Nuts")

# Path of each part's bodies [moveBodies].
PART_CONTAINERS: dict[str, Path] = {
    "back_plate": ("Frame",),
    "front_plate": ("Frame",),
    "bearing": ("Bearings",),
    "escape_arbor": ("Arbors",),
    "pallet_arbor": ("Arbors",),
    "great_wheel_arbor": ("Arbors",),
    "escape_wheel": ("Escapement", "Escape Wheel"),
    "anchor": ("Escapement", "Anchor"),
    "crutch": ("Pendulum Assembly", "Crutch"),
    "pendulum": ("Pendulum Assembly", "Pendulum"),
    "suspension_pin": ("Pendulum Assembly", "Suspension"),
    "suspension_cap": ("Pendulum Assembly", "Suspension"),
    "great_wheel": ("Drive", "Great Wheel"),
    "pawl_carrier": ("Drive", "Pawl Carrier"),
    "mainspring": ("Drive", "Mainspring"),
    "spring_spacer": ("Drive", "Spring Spacer"),
    "spring_anchor_pin": ("Drive", "Spring Anchor"),
    "winding_knob": ("Drive", "Winding Knob"),
    "bolt": ("Bolts",),
    "nut": ("Nuts",),
}
BODY_CONTAINER: dict[str, Path] = {name: PART_CONTAINERS[b.part_of(name)] for name in b.BODY_NAMES}


def container_of_part(part: str) -> Path:
    """Container path of a part. Raises KeyError for an unknown part."""
    return PART_CONTAINERS[part]


def expected_bodies() -> dict[Path, list[str]]:
    """Body names per container path, in CONTAINER_PATHS order; a group node has an empty list."""
    out: dict[Path, list[str]] = {path: [] for path in CONTAINER_PATHS}
    for name in b.BODY_NAMES:
        out[BODY_CONTAINER[name]].append(name)
    return out


def expected_children(path: Path) -> list[str]:
    """Names of the child containers of `path`; the empty path is the top component."""
    return [p[-1] for p in CONTAINER_PATHS if p[:-1] == path]


@dataclasses.dataclass(frozen=True)
class Found:
    """One descendant component of the top component, as read from Fusion."""

    path: Path
    bodies: tuple[str, ...]  # body names directly in that component
    children: tuple[str, ...]  # names of the components directly inside it


@dataclasses.dataclass(frozen=True)
class ContainerResult:
    path: Path
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


def _child_problems(have: list[str], want: list[str], label: str) -> list[str]:
    parts: list[str] = []
    missing = [n for n in want if n not in have]
    extra = [n for n in have if n not in want]
    duplicate = sorted({n for n in have if have.count(n) > 1})
    if missing:
        parts.append(_names(f"missing {label}", missing))
    if extra:
        parts.append(_names(f"extra {label}", extra))
    if duplicate:
        parts.append(_names(f"duplicate {label}", duplicate))
    return parts


def check_tree(found: list[Found], top_bodies: int) -> tuple[ContainerResult, list[ContainerResult]]:
    """The top-level result, then one result per path in CONTAINER_PATHS [VerifyContainers, requireContainers].

    Top: no body directly in the top component, and its children are exactly the top-level names, once each."""
    top_children = [f.path[0] for f in found if len(f.path) == 1]
    parts: list[str] = []
    if top_bodies > 0:
        parts.append(f"{top_bodies} bodies outside containers")
    parts += _child_problems(top_children, list(TOP_LEVEL), "container")
    top = ContainerResult((), top_bodies, 0, not parts, "; ".join(parts))

    want_bodies = expected_bodies()
    results: list[ContainerResult] = []
    for path in CONTAINER_PATHS:
        want = want_bodies[path]
        hits = [f for f in found if f.path == path]
        if not hits:
            results.append(ContainerResult(path, 0, len(want), False, "no component"))
            continue
        if len(hits) > 1:
            n = sum(len(h.bodies) for h in hits)
            results.append(ContainerResult(path, n, len(want), False, f"{len(hits)} components"))
            continue
        f = hits[0]
        problems: list[str] = []
        if len(set(f.bodies)) != len(f.bodies):
            problems.append("duplicate body names")
        missing = sorted(set(want) - set(f.bodies))
        if missing:
            problems.append(_names("missing", missing))
        extra = sorted(set(f.bodies) - set(want))
        if extra:
            problems.append(_names("extra", extra))
        problems += _child_problems(list(f.children), expected_children(path), "child")
        results.append(ContainerResult(path, len(f.bodies), len(want), not problems, "; ".join(problems)))
    return top, results
