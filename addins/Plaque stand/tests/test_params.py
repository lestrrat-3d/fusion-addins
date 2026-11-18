import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen.inputs import INPUT_SPECS, params_from_values
from gen.params import Params, default_params
from gen.validate import ValidationError, derive, validate

# instructions.md "Representative cases": (params, S, H_b, C_y, D, Height, TipFront, TipBack, TipSide).
CASES = {
    "default": (Params(250, 305, 12.8, 15, 10, 0.55), 200, 60, 24.303105, 112, 70.432523, 19.875977, 15.042312, 31.403024),
    "min": (Params(150, 120, 2, 10, 6, 0.55), 120, 30, 17.280750, 55, 38.349710, 18.644768, 18.572439, 40.766229),
    "max": (Params(400, 350, 15, 25, 20, 1.5), 246, 60, 29.192341, 160, 66.588125, 27.346216, 15.206476, 34.345575),
    "forward": (Params(300, 350, 2, 10, 10, 0.55), 240, 60, 23.828646, 109, 67.893943, 15.000000, 15.262544, 33.224387),
    "narrow-tall": (Params(150, 350, 15, 10, 6, 1.5), 120, 60, 31.809631, 124, 74.050264, 15.000000, 15.154925, 17.328331),
    "short-steep": (Params(150, 120, 15, 25, 20, 1.5), 120, 30, 29.192341, 81, 40.220496, 32.136555, 15.245825, 38.859428),
}


class DerivedTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(default_params(), Params(250.0, 305.0, 12.8, 15.0, 10.0, 0.55))

    def test_representative_cases(self):
        for name, (p, span, back, cy, depth, height, front, back_tip, side) in CASES.items():
            with self.subTest(case=name):
                dm = derive(p)
                self.assertAlmostEqual(dm.span, span, places=9)
                self.assertAlmostEqual(dm.back_height, back, places=9)
                self.assertAlmostEqual(dm.seat[0], cy, places=5)
                self.assertEqual(dm.depth, depth)
                self.assertAlmostEqual(dm.height, height, places=5)
                self.assertAlmostEqual(dm.tip_front, front, places=5)
                self.assertAlmostEqual(dm.tip_back, back_tip, places=5)
                self.assertAlmostEqual(dm.tip_side, side, places=5)

    def test_channel_and_sites(self):
        dm = derive(default_params())
        self.assertAlmostEqual(dm.channel_width, 10.8)
        self.assertAlmostEqual(dm.channel_back, dm.depth - 11)
        self.assertAlmostEqual(dm.channel_front, dm.depth - 21.8)
        self.assertEqual(dm.channel_floor, 4.0)
        self.assertAlmostEqual(dm.rail_center, dm.depth - 16.4)
        for s, x in zip(dm.sites, (10.0, dm.span - 10.0)):
            self.assertEqual((s.dir, s.corner, s.length), ((0.0, 0.0, -1.0), (1.0, 0.0, 0.0), 6.0))
            self.assertAlmostEqual(s.head[0], x)
            self.assertAlmostEqual(s.head[1], dm.rail_center)
            self.assertAlmostEqual(s.head[2], 8.4)
            self.assertAlmostEqual(s.cavity, 6.4)
            self.assertEqual(s.validate(), "")

    def test_slot(self):
        dm = derive(default_params())
        self.assertAlmostEqual(dm.slot_width, 12.8 + 1.1)
        self.assertAlmostEqual(dm.slot_radius, 6.95)
        self.assertAlmostEqual(dm.seat[1], 8 + 6.95)
        self.assertAlmostEqual(dm.back_wall, 57.0)
        self.assertAlmostEqual(dm.lip_wall, 7.5)
        self.assertAlmostEqual(math.hypot(*dm.axis), 1.0)
        self.assertAlmostEqual(dm.axis[0], math.sin(math.radians(15)))
        self.assertAlmostEqual(dm.normal[0], math.cos(math.radians(15)))

    def test_every_case_fits_the_bed(self):
        for name, (p, *_rest) in CASES.items():
            dm = derive(p)
            self.assertTrue(max(dm.span, dm.depth, dm.height) <= 246.0, name)


class ValidationTest(unittest.TestCase):
    def message(self, **changes):
        with self.assertRaises(ValidationError) as cm:
            validate(dataclasses.replace(default_params(), **changes))
        return str(cm.exception)

    def test_each_field_in_order(self):
        self.assertEqual(self.message(plaque_width=149.0), "PlaqueWidth must be from 150 to 400 mm, got 149")
        self.assertEqual(self.message(plaque_height=351.0), "PlaqueHeight must be from 120 to 350 mm, got 351")
        self.assertEqual(self.message(plaque_thickness=1.9), "PlaqueThickness must be from 2 to 15 mm, got 1.9")
        self.assertEqual(self.message(recline=9.0), "Recline must be from 10 to 25 degrees, got 9")
        self.assertEqual(self.message(lip_height=21.0), "LipHeight must be from 6 to 20 mm, got 21")
        self.assertEqual(self.message(slot_clearance=0.5), "SlotClearance must be from 0.55 to 1.5 mm, got 0.5")

    def test_limits_are_inclusive_and_nan_fails(self):
        for p in (Params(150, 120, 2, 10, 6, 0.55), Params(400, 350, 15, 25, 20, 1.5)):
            validate(p)
        self.assertIn("PlaqueWidth must be", self.message(plaque_width=math.nan))
        self.assertIn("SlotClearance must be", self.message(slot_clearance=math.inf))

    def test_first_failure_wins(self):
        self.assertIn("PlaqueWidth", self.message(plaque_width=1.0, recline=1.0))


class InputsTest(unittest.TestCase):
    def test_order_labels_and_defaults(self):
        self.assertEqual([(s.label, s.kind, s.default) for s in INPUT_SPECS], [
            ("Plaque width", "length", 250.0), ("Plaque height", "length", 305.0),
            ("Plaque thickness", "length", 12.8), ("Recline", "angle", 15.0), ("Lip height", "length", 10.0),
            ("Slot clearance", "length", 0.55)])

    def test_params_from_values_converts_the_angle_and_rounds(self):
        values = {s.id: s.default for s in INPUT_SPECS}
        values["recline"] = math.radians(15.0)  # Fusion hands back radians
        values["slot_clearance"] = 0.55000000000000004 * 1.0000000001
        p = params_from_values(values)
        self.assertEqual(p, default_params())

    def test_the_dialogs_defaults_pass_validation(self):
        values = {s.id: s.default for s in INPUT_SPECS}
        values["recline"] = math.radians(values["recline"])
        validate(params_from_values(values))


if __name__ == "__main__":
    unittest.main()
