import dataclasses
import unittest

import _support  # noqa: F401
from gen.dims import derive
from gen.expected import assembled_z, part_local_bounds, part_volume
from gen.params import default_params

P1 = default_params()
D1 = derive(P1)
P2 = dataclasses.replace(P1, stages=2)
D2 = derive(P2)

# part -> reference volume (mm^3) and allowed distance from it.
REFERENCE = {
    "housing_bearing": (671.5154, 0.5),
    "planet_bearing": (671.5154, 0.5),
    "input_shaft": (642.8541, 0.5),
    "output_shaft": (620.5314, 0.5),
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
