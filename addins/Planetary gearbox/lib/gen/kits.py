"""Bearing kits. Own copy of decad-gallery models/planetarygearbox kits.go at 45b5875."""

from __future__ import annotations

import dataclasses
import json

from .params import Params, default_params


@dataclasses.dataclass(frozen=True)
class Kit:
    """One supported pair of bearings, by catalog name."""

    name: str
    planet_bearing: str
    shaft_bearing: str


# (kit, sun, planet, ring) at module 1 and three planets, the default first, in the gallery's order.
_KITS: tuple[tuple[Kit, int, int, int], ...] = (
    (Kit("planet605-shaft605", "605ZZ", "605ZZ"), 13, 29, 71),
    (Kit("planet605-shaft608", "605ZZ", "608ZZ"), 14, 28, 70),
    (Kit("planet608-shaft605", "608ZZ", "605ZZ"), 13, 29, 71),
    (Kit("planet608-shaft608", "608ZZ", "608ZZ"), 14, 28, 70),
)


def supported_combinations() -> tuple[Kit, ...]:
    """Every kit default_params_for accepts, the default kit first."""
    return tuple(k for k, _, _, _ in _KITS)


def default_params_for(kit: str) -> Params:
    """default_params() with the kit's bearings and its tooth set. Raises ValueError for an unknown kit name."""
    for k, sun, planet, ring in _KITS:
        if k.name == kit:
            return dataclasses.replace(
                default_params(),
                planet_bearing=k.planet_bearing,
                shaft_bearing=k.shaft_bearing,
                sun_teeth=sun,
                planet_teeth=planet,
                ring_teeth=ring,
            )
    names = ", ".join(k.name for k, _, _, _ in _KITS)
    raise ValueError(f"unknown kit {json.dumps(kit, ensure_ascii=False)}; choose one of {names}")


def kit_for(planet_bearing: str, shaft_bearing: str) -> Kit | None:
    """The kit with these two bearings, or None."""
    for k, _, _, _ in _KITS:
        if k.planet_bearing == planet_bearing and k.shaft_bearing == shaft_bearing:
            return k
    return None


def kit_teeth(kit: Kit) -> tuple[int, int, int]:
    """The kit's (sun, planet, ring) tooth set at module 1."""
    for k, sun, planet, ring in _KITS:
        if k == kit:
            return (sun, planet, ring)
    raise ValueError(f"unknown kit {json.dumps(kit.name)}")


def kit_dependent_fields() -> tuple[str, ...]:
    """Params fields whose value differs between any two kits, minus the two bearing selectors, in field order."""
    results = [default_params_for(k.name) for k in supported_combinations()]
    out = []
    for f in dataclasses.fields(Params):
        if f.name in ("planet_bearing", "shaft_bearing"):
            continue
        if len({getattr(p, f.name) for p in results}) > 1:
            out.append(f.name)
    return tuple(out)
