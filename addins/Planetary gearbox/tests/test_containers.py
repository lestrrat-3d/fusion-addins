import dataclasses
import unittest

import _support  # noqa: F401
from gen import layout
from gen.containers import (
    CONTAINER_NAMES,
    GEARBOX_NAME,
    PART_CONTAINERS,
    ContainerResult,
    Found,
    RootResult,
    check_containers,
    check_root,
    container_of,
    expected_bodies,
)
from gen.dims import derive
from gen.params import default_params

P1 = default_params()
D1 = derive(P1)
P2 = dataclasses.replace(P1, stages=2)
D2 = derive(P2)

FRONT_BOLTS = [f"Front Bolt {i}" for i in range(1, 5)]
REAR_BOLTS = [f"Rear Bolt {i}" for i in range(1, 5)]
K1 = {
    "Housing": ["Ring Gear", "Front Cover", "Rear Cover"],
    "Cover Bearings": ["Front Bearing", "Rear Bearing"],
    "Bolts": FRONT_BOLTS + REAR_BOLTS,
    "Nuts": [f"Front Nut {i}" for i in range(1, 5)] + [f"Rear Nut {i}" for i in range(1, 5)],
    "Shafts": ["Input Shaft", "Output Shaft"],
    "Sun Gears": ["Sun Gear 1"],
    "Planet Gears": ["Planet Gear 1.1", "Planet Gear 1.2", "Planet Gear 1.3"],
    "Planet Bearings": ["Planet Bearing 1.1", "Planet Bearing 1.2", "Planet Bearing 1.3"],
    "Carrier Pins": ["Carrier Pin 1.1", "Carrier Pin 1.2", "Carrier Pin 1.3"],
    "Carriers": ["Carrier 1"],
}


def found_from(expected):
    return [Found(n, tuple(b), 0) for n, b in expected.items()]


def moved_nut():
    want = {k: list(v) for k, v in K1.items()}
    want["Nuts"].remove("Rear Nut 4")
    want["Bolts"].append("Rear Nut 4")
    return want


class ContainersTest(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(
            CONTAINER_NAMES,
            (
                "Housing",
                "Cover Bearings",
                "Bolts",
                "Nuts",
                "Shafts",
                "Sun Gears",
                "Planet Gears",
                "Planet Bearings",
                "Carrier Pins",
                "Carriers",
            ),
        )
        self.assertEqual(set(PART_CONTAINERS), set(layout.PARTS))
        self.assertEqual(GEARBOX_NAME, "Planetary Gearbox")
        self.assertEqual(container_of("link_shaft"), "Shafts")
        with self.assertRaises(KeyError):
            container_of("nope")

    def test_expected_bodies(self):
        got = expected_bodies(P1, D1)
        self.assertEqual(list(got), list(CONTAINER_NAMES))
        self.assertEqual(got, K1)
        got2 = expected_bodies(P2, D2)
        self.assertEqual([len(v) for v in got2.values()], [3, 2, 8, 8, 3, 2, 6, 6, 6, 2])
        self.assertEqual(got2["Shafts"], ["Input Shaft", "Link Shaft 1", "Output Shaft"])
        for p, got_ in ((P1, got), (P2, got2)):
            self.assertEqual(sum(len(v) for v in got_.values()), layout.expected_body_count(p))

    def test_all_good(self):
        found = found_from(K1)
        self.assertEqual(check_root(found, 0), RootResult(0, 10, 10, True, ""))
        results = check_containers(found, K1)
        self.assertEqual(len(results), 10)
        for r in results:
            self.assertTrue(r.ok)
            self.assertEqual(r.detail, "")

    def test_misplaced_body(self):
        results = {r.name: r for r in check_containers(found_from(moved_nut()), K1)}
        self.assertEqual(results["Bolts"], ContainerResult("Bolts", 9, 8, False, "extra Rear Nut 4"))
        self.assertEqual(results["Nuts"], ContainerResult("Nuts", 7, 8, False, "missing Rear Nut 4"))
        self.assertEqual(sum(r.ok for r in results.values()), 8)

    def test_body_in_root(self):
        self.assertEqual(check_root(found_from(K1), 1).detail, "1 bodies outside containers")

    def test_missing_component(self):
        found = [f for f in found_from(K1) if f.name != "Carriers"]
        self.assertEqual(check_root(found, 0).detail, "missing Carriers")
        results = {r.name: r for r in check_containers(found, K1)}
        self.assertEqual(results["Carriers"], ContainerResult("Carriers", 0, 1, False, "no component"))

    def test_duplicate_component(self):
        found = found_from(K1) + [Found("Housing", tuple(K1["Housing"]), 0)]
        self.assertEqual(check_root(found, 0).detail, "duplicate Housing")
        results = {r.name: r for r in check_containers(found, K1)}
        self.assertEqual(results["Housing"].detail, "2 components")
        self.assertEqual(results["Housing"].bodies, 6)

    def test_extra_component(self):
        found = found_from(K1) + [Found("Group 1", (), 0)]
        self.assertEqual(check_root(found, 0).detail, "extra Group 1")

    def test_child_components(self):
        found = [Found(f.name, f.bodies, 1 if f.name == "Bolts" else 0) for f in found_from(K1)]
        results = {r.name: r for r in check_containers(found, K1)}
        self.assertEqual(results["Bolts"].detail, "1 child components")

    def test_empty_container(self):
        found = [Found(f.name, () if f.name == "Bolts" else f.bodies, 0) for f in found_from(K1)]
        results = {r.name: r for r in check_containers(found, K1)}
        self.assertEqual(results["Bolts"].detail, "missing Front Bolt 1, Front Bolt 2, Front Bolt 3 +5")


if __name__ == "__main__":
    unittest.main()
