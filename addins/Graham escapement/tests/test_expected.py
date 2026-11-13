import math
import unittest

import _support  # noqa: F401
from gen import bodies, expected
from gen.curves import Line
from gen.layout import layout
from gen.params import default_params
from gen.sections import arbor_meridian, press_d_area, _segment_area

G = layout(default_params())
D = press_d_area()


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
        self.assertAlmostEqual(vol("winding_knob").value, (81 * math.pi - D) * 3, places=6)
        self.assertAlmostEqual(vol("spring_spacer").value, (13.69 * math.pi - D) * 10.25, places=6)
        self.assertAlmostEqual(vol("suspension_cap").value, (13.69 * math.pi - D) * 1.5, places=6)
        self.assertAlmostEqual(vol("bearing").tol, 0.001 * vol("bearing").value, places=9)

    def test_escape_arbor(self):
        pts = [seg.start for seg in arbor_meridian("escape_arbor")]
        total = 0.0
        for k, a in enumerate(pts):
            b = pts[(k + 1) % len(pts)]
            total += (a[0] ** 2 + a[0] * b[0] + b[0] ** 2) * (b[1] - a[1])
        stair = abs(total) * math.pi / 3
        want = stair - _segment_area(2.5, 2.0) * 24.5
        self.assertAlmostEqual(vol("escape_arbor").value, want, places=6)

    def test_arbor_flat_runs(self):
        # The pin's rear flat [30.05, 33.95] meets the r 2.5 run [31.05, 34] for 2.9 mm, the front one for 1.45 mm.
        pin = vol("suspension_pin").value
        stair = 0.0
        pts = [seg.start for seg in arbor_meridian("suspension_pin")]
        for k, a in enumerate(pts):
            b = pts[(k + 1) % len(pts)]
            stair += (a[0] ** 2 + a[0] * b[0] + b[0] ** 2) * (b[1] - a[1])
        stair = abs(stair) * math.pi / 3
        self.assertAlmostEqual(pin, stair - _segment_area(2.5, 2.0) * (2.9 + 1.45), places=6)
        self.assertTrue(all(isinstance(s, Line) for s in arbor_meridian("pallet_arbor")))

    def test_chamfered_parts_lose_volume(self):
        from gen.edgefinish import chamfer_volume

        for part in ("back_plate", "front_plate", "escape_wheel", "anchor", "pendulum", "mainspring"):
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
            "Front Great Wheel Bearing": (28, 33), "Pendulum Bearing": (39, 44),
            "Escape Arbor": (-5, 33), "Pallet Arbor": (-5, 37.2), "Great Wheel Arbor": (-5, 37.2),
            "Escape Wheel": (0.25, 25), "Anchor": (21, 27.75), "Crutch": (34.25, 43.25),
            "Pendulum": (37.75, 43.75), "Suspension Pin": (31.05, 45.70), "Suspension Cap": (44.25, 45.75),
            "Great Wheel": (1.5, 8.5), "Pawl Carrier": (5.25, 11.0), "Mainspring": (11.25, 17.25),
            "Spring Spacer": (17.5, 27.75), "Spring Anchor Pin": (10.25, 30.95), "Winding Knob": (34.25, 37.25),
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
        with self.assertRaises(KeyError):
            expected.part_z("nope")


if __name__ == "__main__":
    unittest.main()
