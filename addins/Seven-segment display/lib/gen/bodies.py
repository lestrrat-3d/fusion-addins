"""The display's bodies and containers, and the check that stands in for decad VerifyContainers.

Own copy of the body and container layout of decad-gallery models/sevensegment sevensegment.go (Build). The gallery
builds 75 bodies and so does the add-in; `EXPECTED_BODY_COUNT` is checked after a build.
"""

from __future__ import annotations

import dataclasses
import re

from .truth import SEGMENTS, segment_name

TOP_NAME = "Seven-segment display"  # the add-in's top component; stands for the gallery document's root container

FULL_BODY_COUNT = 75  # the gallery's Build comment: 75 bodies, the 14 pivot blocks among them

# Container names, one per kind of body.
FRAME = "Frame"
WALLS = "Walls"
PLATES = "Plates"
CAMSHAFT = "Camshaft"
SHAFT_CONTAINER = "Shaft"
CAMS = "Cams"
CLICKER = "Click Indexer"
HUB_CONTAINER = "Hub"
ROTOR_CONTAINER = "Rotor"
HOUSING_CONTAINER = "Housing"
BUTTON_CONTAINER = "Button"
SPRING_CONTAINER = "Spring"
SLIDERS = "Segment Sliders"
BEARINGS = "Bearings"
BOLTS = "Bolts"
NUTS = "Nuts"
FLAGS = "Flags"
FLAG_UNIT = "Flag"
YELLOW_FACE = "Yellow Face"
BLACK_BODY = "Black Body"
PIVOT_BLOCKS = "Pivot Blocks"

SITE_LABELS: tuple[str, ...] = ("T1", "T2", "T3", "T4", "G1", "G2", "G3", "G4", "H1", "H2")


@dataclasses.dataclass(frozen=True)
class Node:
    """A container: `key` is its path, `name` the component name, `children` its sub-containers."""

    key: str
    name: str
    children: tuple["Node", ...] = ()


def _flag_unit(i: int) -> Node:
    key = f"{FLAGS}/{FLAG_UNIT} {i + 1}"
    return Node(key, FLAG_UNIT, (Node(f"{key}/{YELLOW_FACE}", YELLOW_FACE), Node(f"{key}/{BLACK_BODY}", BLACK_BODY)))


# The container tree in creation order. Units `Frame`, `Camshaft`, `Click Indexer` and `Flags` hold their kinds; `Pivot Blocks` holds the 14 blocks.
TREE: tuple[Node, ...] = (
    Node(FRAME, FRAME, (Node(f"{FRAME}/{WALLS}", WALLS), Node(f"{FRAME}/{PLATES}", PLATES))),
    Node(CAMSHAFT, CAMSHAFT,
         (Node(f"{CAMSHAFT}/{SHAFT_CONTAINER}", SHAFT_CONTAINER), Node(f"{CAMSHAFT}/{CAMS}", CAMS))),
    Node(CLICKER, CLICKER, tuple(Node(f"{CLICKER}/{n}", n) for n in (
        HUB_CONTAINER, ROTOR_CONTAINER, HOUSING_CONTAINER, BUTTON_CONTAINER, SPRING_CONTAINER))),
    Node(SLIDERS, SLIDERS),
    Node(FLAGS, FLAGS, tuple(_flag_unit(i) for i in range(len(SEGMENTS)))),
    Node(PIVOT_BLOCKS, PIVOT_BLOCKS),
    Node(BEARINGS, BEARINGS),
    Node(BOLTS, BOLTS),
    Node(NUTS, NUTS),
)


def walk(nodes: tuple[Node, ...] = TREE):
    """Every node of the tree, parents before children."""
    for n in nodes:
        yield n
        yield from walk(n.children)


@dataclasses.dataclass(frozen=True)
class Spec:
    name: str
    container: str  # a Node key
    stage: int  # which builder group makes it: 1 frame and camshaft, 2 flags and plates, 3 click indexer


FRONT_WALL = "Front Wall"
REAR_WALL = "Rear Wall"
GUIDE_PLATE = "Guide Plate"
CRADLE_PLATE = "Cradle Plate"
TOP_PLATE = "Top Plate"
SHAFT = "Shaft"
HUB = "Hub"
ROTOR = "Rotor"
HOUSING = "Housing"
BUTTON = "Button"
SPRING = "Spring"
FRONT_BEARING = "Front Bearing"
REAR_BEARING = "Rear Bearing"


def cam_name(s: int) -> str:
    return f"Cam {segment_name(s).upper()}"


def slider_name(s: int) -> str:
    return f"Slider {segment_name(s).upper()}"


def yellow_name(s: int) -> str:
    return f"Yellow Face {segment_name(s).upper()}"


def black_name(s: int) -> str:
    return f"Black Body {segment_name(s).upper()}"


def pivot_name(s: int, sgn: float) -> str:
    """The pivot block at segment s's -u end (sgn -1) or +u end (sgn +1), as Parts.PivotBlocks[s][0 or 1]."""
    return f"Pivot Block {segment_name(s).upper()} {'+u' if sgn > 0 else '-u'}"


def bolt_name(label: str) -> str:
    return f"Bolt {label}"


def nut_name(label: str) -> str:
    return f"Nut {label}"


def _specs() -> tuple[Spec, ...]:
    out = [
        Spec(FRONT_WALL, f"{FRAME}/{WALLS}", 1), Spec(REAR_WALL, f"{FRAME}/{WALLS}", 1),
        Spec(GUIDE_PLATE, f"{FRAME}/{PLATES}", 2), Spec(CRADLE_PLATE, f"{FRAME}/{PLATES}", 2),
        Spec(TOP_PLATE, f"{FRAME}/{PLATES}", 2),
        Spec(SHAFT, f"{CAMSHAFT}/{SHAFT_CONTAINER}", 1),
        Spec(HUB, f"{CLICKER}/{HUB_CONTAINER}", 3), Spec(ROTOR, f"{CLICKER}/{ROTOR_CONTAINER}", 3),
        Spec(HOUSING, f"{CLICKER}/{HOUSING_CONTAINER}", 3), Spec(BUTTON, f"{CLICKER}/{BUTTON_CONTAINER}", 3),
        Spec(SPRING, f"{CLICKER}/{SPRING_CONTAINER}", 3),
    ]
    for s in SEGMENTS:
        out += [Spec(cam_name(s), f"{CAMSHAFT}/{CAMS}", 1), Spec(slider_name(s), SLIDERS, 2)]
    for s in SEGMENTS:
        unit = f"{FLAGS}/{FLAG_UNIT} {s + 1}"
        out += [Spec(yellow_name(s), f"{unit}/{YELLOW_FACE}", 2), Spec(black_name(s), f"{unit}/{BLACK_BODY}", 2)]
    for s in SEGMENTS:
        out += [Spec(pivot_name(s, -1), PIVOT_BLOCKS, 2), Spec(pivot_name(s, 1), PIVOT_BLOCKS, 2)]
    out += [Spec(FRONT_BEARING, BEARINGS, 1), Spec(REAR_BEARING, BEARINGS, 1)]
    for label in SITE_LABELS:
        out += [Spec(bolt_name(label), BOLTS, 1), Spec(nut_name(label), NUTS, 1)]
    return tuple(out)


PIVOT_ENDS: dict[str, tuple[int, float]] = {pivot_name(s, g): (s, g) for s in SEGMENTS for g in (-1.0, 1.0)}

# Every body of the gallery's model in build order.
ALL_SPECS: tuple[Spec, ...] = _specs()
BODY_CONTAINER: dict[str, str] = {s.name: s.container for s in ALL_SPECS}
BODY_STAGE: dict[str, int] = {s.name: s.stage for s in ALL_SPECS}
ALL_BODY_NAMES: tuple[str, ...] = tuple(s.name for s in ALL_SPECS)

# The bodies that are built, in build order.
BODY_NAMES: tuple[str, ...] = ALL_BODY_NAMES
EXPECTED_BODY_COUNT = FULL_BODY_COUNT

BOLTS_NAMES: tuple[str, ...] = tuple(bolt_name(label) for label in SITE_LABELS)
NUTS_NAMES: tuple[str, ...] = tuple(nut_name(label) for label in SITE_LABELS)


def is_bolt(name: str) -> bool:
    return name in BOLTS_NAMES


def is_nut(name: str) -> bool:
    return name in NUTS_NAMES


def site_index(name: str) -> int:
    """The index into Dimensions.sites of a bolt or a nut."""
    label = name.split(" ", 1)[1]
    return SITE_LABELS.index(label)


def expected_bodies() -> dict[str, list[str]]:
    """The built bodies per container key, in tree order."""
    out: dict[str, list[str]] = {n.key: [] for n in walk()}
    for name in BODY_NAMES:
        out[BODY_CONTAINER[name]].append(name)
    return out


_NUMBERED = re.compile(r" \(\d+\)$")


def base_name(name: str) -> str:
    """A component name without the ` (n)` that Fusion appends when another component already has the name."""
    return _NUMBERED.sub("", name)


@dataclasses.dataclass(frozen=True)
class Found:
    """One component below the top component, as read from Fusion."""

    name: str
    bodies: tuple[str, ...]  # body names directly in that component
    children: tuple["Found", ...]


@dataclasses.dataclass(frozen=True)
class ContainerResult:
    name: str  # the container's key; "" for the top component
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


def _match(nodes: tuple[Node, ...], found: tuple[Found, ...]) -> tuple[list[Found | None], list[str]]:
    """Pair each expected child with the next unused found child of the same base name, in order. Returns the pairs
    (None for a missing child) and the base names of the extra children."""
    used = [False] * len(found)
    pairs: list[Found | None] = []
    for node in nodes:
        hit = None
        for i, f in enumerate(found):
            if not used[i] and base_name(f.name) == node.name:
                used[i] = True
                hit = f
                break
        pairs.append(hit)
    extra = [base_name(f.name) for i, f in enumerate(found) if not used[i]]
    return pairs, extra


def check_tree(found: list[Found], top_bodies: int) -> tuple[ContainerResult, list[ContainerResult]]:
    """The top-level result, then one result per container in tree order [VerifyContainers].

    Top: no body directly in the top component, and its children are exactly the top containers, once each. Each
    container: exactly its built bodies, once each, and exactly its sub-containers."""
    want = expected_bodies()
    results: list[ContainerResult] = []

    def check_node(node: Node, f: Found | None) -> None:
        if f is None:
            results.append(ContainerResult(node.key, 0, len(want[node.key]), False, "no component"))
            for c in node.children:
                check_node(c, None)
            return
        problems: list[str] = []
        names = list(f.bodies)
        if len(set(names)) != len(names):
            problems.append("duplicate body names")
        missing = sorted(set(want[node.key]) - set(names))
        if missing:
            problems.append(_names("missing", missing))
        extra = sorted(set(names) - set(want[node.key]))
        if extra:
            problems.append(_names("extra", extra))
        pairs, extra_children = _match(node.children, f.children)
        if extra_children:
            problems.append(_names("extra child", extra_children))
        results.append(ContainerResult(node.key, len(names), len(want[node.key]), not problems, "; ".join(problems)))
        for c, pf in zip(node.children, pairs):
            check_node(c, pf)

    pairs, extra = _match(TREE, tuple(found))
    parts: list[str] = []
    if top_bodies > 0:
        parts.append(f"{top_bodies} bodies outside containers")
    missing = [n.name for n, p in zip(TREE, pairs) if p is None]
    if missing:
        parts.append(_names("missing container", missing))
    if extra:
        parts.append(_names("extra container", extra))
    top = ContainerResult("", top_bodies, 0, not parts, "; ".join(parts))
    for n, p in zip(TREE, pairs):
        check_node(n, p)
    return top, results
