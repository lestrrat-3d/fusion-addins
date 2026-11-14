import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen.bridge import nut_bridge_volume
from gen.dims import derive
from gen import layout
from gen.expected import assembled_z, part_local_bounds, part_volume
from gen.kits import default_params_for, supported_combinations
from gen.params import default_params

P1 = default_params()
D1 = derive(P1)
P2 = dataclasses.replace(P1, stages=2)
D2 = derive(P2)

# part -> reference volume (mm^3) and allowed distance from it.
REFERENCE = {
    "housing_bearing": (671.5154, 0.5),
    "planet_bearing": (671.5154, 0.5),
    "input_shaft": (625.9616, 0.5),
    "output_shaft": (609.2907, 0.5),
    "carrier": (3253.6953, 0.5),
    "carrier_pin": (313.0304, 0.5),
    "cover": (8885.4352, 1.0),
    "ring": (32122.5836, 0.5),
    "sun": (805.8648, 2.0),
    "planet": (4054.4277, 2.0),
    "bolt": (38.9151, 0.001),
    "nut": (16.1483, 0.001),
}

Z_K1 = {
    "Ring Gear": (-1, 13),
    "Front Cover": (-9, -1),
    "Rear Cover": (13, 21),
    "Front Bearing": (-9, -4),
    "Rear Bearing": (16, 21),
    "Input Shaft": (-21, 8),
    "Front Bolt 1": (-4, 4),
    "Rear Bolt 1": (8, 16),
    "Front Nut 1": (0.2, 1.8),
    "Rear Nut 1": (10.2, 11.8),
    "Sun Gear 1": (0, 8),
    "Planet Gear 1.1": (0, 8),
    "Planet Gear 1.2": (0, 8),
    "Planet Gear 1.3": (0, 8),
    "Planet Bearing 1.1": (3.25, 8.25),
    "Planet Bearing 1.2": (3.25, 8.25),
    "Planet Bearing 1.3": (3.25, 8.25),
    "Carrier 1": (9, 12),
    "Carrier Pin 1.1": (0, 12),
    "Output Shaft": (9, 33),
}

Z_K2 = {
    "Ring Gear": (-1, 26),
    "Front Bolt 1": (-4, 4),
    "Rear Bolt 1": (21, 29),
    "Rear Nut 1": (23.2, 24.8),
    "Planet Bearing 2.1": (16.25, 21.25),
    "Rear Cover": (26, 34),
    "Rear Bearing": (29, 34),
    "Sun Gear 2": (13, 21),
    "Carrier 2": (22, 25),
    "Carrier Pin 2.1": (13, 25),
    "Link Shaft 1": (9, 21),
    "Output Shaft": (22, 46),
}

# Closed-form references of the non-default kits (mm^3): bearings to 1e-3, shafts and pin to 0.5.
KIT_BEARING = {"605ZZ": 671.5154, "608ZZ": 2309.0706}
KIT_Z = {
    "planet608-shaft608": {
        "Front Cover": (-11, -1),
        "Rear Cover": (13, 23),
        "Front Bearing": (-11, -4),
        "Rear Bearing": (16, 23),
        "Input Shaft": (-23, 8),
        "Planet Bearing 1.1": (1.25, 8.25),
        "Carrier Pin 1.1": (0, 12),
        "Output Shaft": (9, 35),
    },
    "planet605-shaft608": {
        "Front Cover": (-11, -1),
        "Rear Cover": (13, 23),
        "Front Bearing": (-11, -4),
        "Rear Bearing": (16, 23),
        "Input Shaft": (-23, 8),
        "Planet Bearing 1.1": (3.25, 8.25),
        "Carrier Pin 1.1": (0, 12),
        "Output Shaft": (9, 35),
    },
}


class ExpectedTest(unittest.TestCase):
    def test_volumes(self):
        for part, (value, allowed) in REFERENCE.items():
            with self.subTest(part=part):
                got = part_volume(P1, D1, part)
                self.assertLessEqual(abs(got.value - value), allowed, f"volume {got.value}")
                self.assertGreater(got.tol, 0)

    def test_ring_volume_two_stages(self):
        got = part_volume(P2, D2, "ring")
        self.assertLessEqual(abs(got.value - 62241.1349), 0.5, f"volume {got.value}")

    def test_ring_volume_with_bridging(self):
        p = dataclasses.replace(P1, sacrificial_bridging=True)
        got = part_volume(p, derive(p), "ring")
        plain = part_volume(P1, D1, "ring")
        self.assertAlmostEqual(got.value - plain.value, nut_bridge_volume(P1), places=9)
        self.assertAlmostEqual(nut_bridge_volume(P1), 8 * math.pi * 1.3**2 * 0.3, places=9)

    def test_ring_volume_without_ears(self):
        p = dataclasses.replace(P1, ear_count=0)
        got = part_volume(p, derive(p), "ring")
        self.assertLessEqual(abs(got.value - 28873.4669), 0.5, f"volume {got.value}")
        self.assertEqual(part_local_bounds(p, derive(p), "ring")[2], 44.1)

    def test_planet_volume_with_fillet_fallback(self):
        p = default_params()
        d = derive(p)
        full = part_volume(p, d, "planet")
        skipped = part_volume(p, d, "planet", 0.0)
        reduced = part_volume(p, d, "planet", 0.38)
        self.assertLess(skipped.value, reduced.value)
        self.assertLess(reduced.value, full.value)
        self.assertLess(skipped.tol, full.tol)
        self.assertEqual(part_volume(p, d, "planet", None), full)

    def test_link_shaft_volume(self):
        got = part_volume(P2, D2, "link_shaft")
        self.assertLessEqual(abs(got.value - 310.3458), 0.5, f"volume {got.value}")
        with self.assertRaises(ValueError):
            part_volume(P1, D1, "link_shaft")

    def test_assembled_z(self):
        for p, d, table in ((P1, D1, Z_K1), (P2, D2, Z_K2)):
            got = assembled_z(p, d)
            for name, (lo, hi) in table.items():
                with self.subTest(name=name, stages=p.stages):
                    self.assertLess(abs(got[name][0] - lo), 1e-9)
                    self.assertLess(abs(got[name][1] - hi), 1e-9)

    def test_kit_volumes(self):
        for kit, pin, planet_bearing, shaft_bearing in (
            ("planet608-shaft608", 719.3335, "608ZZ", "608ZZ"),
            ("planet605-shaft608", 313.0304, "605ZZ", "608ZZ"),
        ):
            p = default_params_for(kit)
            d = derive(p)
            with self.subTest(kit=kit):
                self.assertLessEqual(
                    abs(part_volume(p, d, "housing_bearing").value - KIT_BEARING[shaft_bearing]), 1e-3
                )
                self.assertLessEqual(
                    abs(part_volume(p, d, "planet_bearing").value - KIT_BEARING[planet_bearing]), 1e-3
                )
                self.assertLessEqual(abs(part_volume(p, d, "input_shaft").value - 1646.0974), 0.5)
                self.assertLessEqual(abs(part_volume(p, d, "output_shaft").value - 1516.5132), 0.5)
                self.assertLessEqual(abs(part_volume(p, d, "carrier_pin").value - pin), 0.5)

    def test_kit_assembled_z(self):
        for kit, table in KIT_Z.items():
            p = default_params_for(kit)
            got = assembled_z(p, derive(p))
            for name, (lo, hi) in table.items():
                with self.subTest(kit=kit, name=name):
                    self.assertLess(abs(got[name][0] - lo), 1e-9)
                    self.assertLess(abs(got[name][1] - hi), 1e-9)

    def test_kit_volumes_positive(self):
        for k in supported_combinations():
            for stages in (1, 2):
                p = dataclasses.replace(default_params_for(k.name), stages=stages)
                d = derive(p)
                for part in layout.PARTS:
                    if part == "link_shaft" and stages == 1:
                        continue
                    with self.subTest(kit=k.name, stages=stages, part=part):
                        v = part_volume(p, d, part).value
                        self.assertTrue(math.isfinite(v))
                        self.assertGreater(v, 0)

    def test_local_bounds(self):
        want = {
            "sun": (0, 8, 7.48),
            "ring": (1, 15, 47.521847325815926),
            "carrier": (0, 3, 26.5),
            "carrier_pin": (-9, 3, 3.2),
            "input_shaft": (-21, 8, None),
            "bolt": (-6, 2, 1.9),
            "nut": (0, 1.6, 2.309401076758503),
        }
        for part, expect in want.items():
            with self.subTest(part=part):
                got = part_local_bounds(P1, D1, part)
                for g, w in zip(got, expect):
                    if w is None:
                        self.assertIsNone(g)
                    else:
                        self.assertAlmostEqual(g, w, places=9)


if __name__ == "__main__":
    unittest.main()
