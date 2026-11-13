import math
import unittest

import _support  # noqa: F401
from gen import bodies, expected
from gen.layout import layout
from gen.params import default_params
from gen.sections import BODY_D, END_D, KEYED_COUNTER_D, KEYED_RING_D, d_area, _segment_area

G = layout(default_params())
D = d_area(END_D)
D_BODY = d_area(BODY_D)
D_KC = d_area(KEYED_COUNTER_D)
D_KR = d_area(KEYED_RING_D)


def vol(part):
    return expected.part_volume(G, part)


class VolumeTest(unittest.TestCase):
    def test_positive_with_tolerance(self):
        for part in bodies.PARTS:
            e = vol(part)
            self.assertGreater(e.value, 0.0, part)
            self.assertGreater(e.tol, 0.0, part)
            self.assertLess(e.tol, 0.01 * e.value + 1.0, part)

    def test_closed_forms(self):
        self.assertAlmostEqual(vol("bearing").value, math.pi * (49 - 6.25) * 5, places=6)
        self.assertAlmostEqual(vol("spring_anchor_pin").value, math.pi * 2.25 * 20.7, places=6)
        self.assertAlmostEqual(vol("winding_knob").value, 81 * math.pi * 3 - D_KC * 2.0 - D * 1.0, places=6)
        self.assertAlmostEqual(vol("spring_spacer").value, (13.69 * math.pi - D_BODY) * 10.25, places=6)
        self.assertAlmostEqual(vol("suspension_cap").value, (13.69 * math.pi - D) * 1.5, places=6)
        self.assertAlmostEqual(vol("arbor_collar").value, (13.69 * math.pi - D_BODY) * 3.0, places=6)
        self.assertAlmostEqual(vol("end_collar").value, (D_KR - D) * 3.0, places=6)
        self.assertAlmostEqual(vol("bearing").tol, 0.001 * vol("bearing").value, places=9)

    def test_value_table(self):
        want = {
            "escape_arbor": 943.1919, "pallet_arbor": 1360.2952, "great_wheel_arbor": 1085.0111,
            "suspension_pin": 439.3896, "escape_wheel": 11727.0011, "anchor": 3051.7426, "crutch": 958.4161,
            "great_wheel": 26352.6515, "pawl_carrier": 938.2497, "mainspring": 10420.8246,
            "spring_spacer": 183.3054, "winding_knob": 657.4719, "arbor_collar": 53.6504, "end_collar": 68.1310,
            "pendulum": 19498.9801, "suspension_cap": 35.4193, "back_plate": 73707.8421, "front_plate": 53951.2628,
            "spring_anchor_pin": 146.3197, "bearing": 671.5154, "bolt": 51.4814, "nut": 16.1483,
        }
        self.assertEqual(set(want), set(bodies.PARTS))
        for part, v in want.items():
            self.assertAlmostEqual(vol(part).value, v, delta=0.01, msg=part)

    def test_escape_arbor_flat(self):
        # The flat removes seg(2.8, 2.55) over the r 2.8 run [0.25, 24.0] cut at [0.20, 23.95]: 23.70 mm, 9.2212 mm^3.
        # It removes nothing from the r 2.5 runs (2.5 < 2.55).
        stair = math.pi * (2.5**2 * 5.25 + 2.8**2 * 23.75 + 3.7**2 * 3.75 + 2.5**2 * 5.25)
        flat = _segment_area(2.8, 2.55) * 23.70
        self.assertAlmostEqual(flat, 9.2212, places=3)
        self.assertAlmostEqual(vol("escape_arbor").value, stair - flat, places=6)

    def test_arbor_flat_runs(self):
        # The pin's rear flat [30.05, 33.95] meets the r 2.5 run [31.05, 34] for 2.9 mm, the front flat [45.30, 47.75]
        # the run [39.80, 46.75] for 1.45 mm; both flats sit at x = 2.0.
        stair = math.pi * (2.5**2 * 2.95 + 3.7**2 * 5.8 + 2.5**2 * 6.95)
        want = stair - _segment_area(2.5, 2.0) * (2.9 + 1.45)
        self.assertAlmostEqual(vol("suspension_pin").value, want, places=6)

    def test_chamfered_parts_lose_volume(self):
        from gen.edgefinish import chamfer_volume

        for part in ("back_plate", "front_plate", "escape_wheel", "anchor", "pendulum", "mainspring", "great_wheel"):
            self.assertGreater(chamfer_volume(G, part), 0.0)
        # Sanity: the pendulum's volume is its extrusion less the pocket and the chamfers.
        self.assertGreater(vol("pendulum").value, 10000.0)

    def test_fastener_tolerance(self):
        for part in ("bolt", "nut"):
            e = vol(part)
            self.assertAlmostEqual(e.tol, 0.002 * e.value + 0.01, places=9)
        self.assertAlmostEqual(vol("bolt").value, 51.48, delta=0.05)

    def test_gear_and_spring_tolerances(self):
        wheel, great, spring = vol("escape_wheel"), vol("great_wheel"), vol("mainspring")
        self.assertGreater(wheel.tol, 0.002 * wheel.value)
        self.assertGreater(great.tol, 0.002 * great.value)
        self.assertAlmostEqual(spring.tol, 0.002 * spring.value + 1.0, places=9)

    def test_unknown_part(self):
        with self.assertRaises(KeyError):
            vol("nope")


class ZRangeTest(unittest.TestCase):
    def test_assembled_z(self):
        want = {
            "Back Plate": (-6, 28), "Front Plate": (28, 34),
            "Back Escape Bearing": (-5, 0), "Back Pallet Bearing": (-5, 0), "Back Great Wheel Bearing": (-5, 0),
            "Front Escape Bearing": (28, 33), "Front Pallet Bearing": (28, 33),
            "Front Great Wheel Bearing": (28, 33), "Pendulum Bearing": (40.05, 45.05),
            "Escape Arbor": (-5, 33), "Pallet Arbor": (-5, 38.25), "Great Wheel Arbor": (-5, 38.25),
            "Escape Wheel": (1.5, 25), "Anchor": (21, 26), "Crutch": (35.30, 44.30),
            "Pendulum": (38.80, 44.80), "Suspension Pin": (31.05, 46.75), "Suspension Cap": (45.30, 46.80),
            "Great Wheel": (1.5, 8.5), "Pawl Carrier": (5.25, 11.0), "Mainspring": (11.25, 17.25),
            "Spring Spacer": (17.5, 27.75), "Spring Anchor Pin": (10.25, 30.95), "Winding Knob": (35.30, 38.30),
            "Escape Rear Collar": (0.25, 3.25), "Pallet Front Collar": (24.75, 27.75),
            "Crutch Collar": (34.25, 37.25), "Knob Collar": (34.25, 37.25),
        }
        for i in range(1, 5):
            want[f"Bolt {i}"] = (22, 34)
            want[f"Nut {i}"] = (24.2, 25.8)
        got = expected.assembled_z(G)
        self.assertEqual(set(got), set(bodies.BODY_NAMES))
        self.assertEqual(set(got), set(want))
        for name, (lo, hi) in want.items():
            self.assertAlmostEqual(got[name][0], lo, places=9, msg=name)
            self.assertAlmostEqual(got[name][1], hi, places=9, msg=name)

    def test_part_z(self):
        self.assertEqual(expected.part_z("mainspring"), (0.0, 6.0))
        self.assertEqual(expected.part_z("arbor_collar"), (0.0, 3.0))
        self.assertEqual(expected.part_z("end_collar"), (0.0, 3.0))
        with self.assertRaises(KeyError):
            expected.part_z("nope")


if __name__ == "__main__":
    unittest.main()
