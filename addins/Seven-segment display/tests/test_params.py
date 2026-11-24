import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen.inputs import INPUT_SPECS, params_from_values
from gen.params import Frame, default_params, placement_frame
from gen.validate import ValidationError, derive, validate


class ParamsTest(unittest.TestCase):
    def test_defaults(self):
        p = default_params()
        self.assertEqual((p.digit, p.placement), (2, None))

    def test_digit_range_message(self):
        for digit in (-1, 10, 99):
            with self.assertRaises(ValidationError) as cm:
                validate(dataclasses.replace(default_params(), digit=digit))
            self.assertEqual(str(cm.exception), f"sevensegment: digit {digit} out of range 0..9")

    def test_every_digit_is_valid(self):
        for digit in range(10):
            validate(dataclasses.replace(default_params(), digit=digit))

    def test_placement_message(self):
        bad = Frame(u=(1.0, 0.0, 0.0), v=(2.0, 0.0, 0.0))
        with self.assertRaises(ValidationError) as cm:
            validate(dataclasses.replace(default_params(), placement=bad))
        self.assertEqual(str(cm.exception), "sevensegment: invalid placement frame")

    def test_digit_is_checked_before_the_placement(self):
        bad = Frame(u=(0.0, 0.0, 0.0))
        with self.assertRaises(ValidationError) as cm:
            validate(dataclasses.replace(default_params(), digit=12, placement=bad))
        self.assertIn("digit 12", str(cm.exception))

    def test_valid_placement(self):
        validate(dataclasses.replace(default_params(), placement=placement_frame((1.0, 2.0, 3.0), (0.0, 0.0, 1.0))))

    def test_placement_from_selections(self):
        self.assertIsNone(placement_frame(None, None))
        with self.assertRaises(ValueError):
            placement_frame(None, (0.0, 0.0, 0.0))


class DeriveTest(unittest.TestCase):
    def test_theta(self):
        for digit in range(10):
            self.assertEqual(derive(dataclasses.replace(default_params(), digit=digit)).theta, 36.0 * digit)

    def test_ramps_do_not_depend_on_the_digit(self):
        a = derive(dataclasses.replace(default_params(), digit=0))
        b = derive(dataclasses.replace(default_params(), digit=9))
        self.assertEqual(a.ramps, b.ramps)
        self.assertEqual([len(r) for r in a.ramps], [6, 8, 4, 4, 2, 2, 4])

    def test_sites(self):
        dm = derive(default_params())
        self.assertEqual(len(dm.sites), 10)
        for s in dm.sites:
            self.assertEqual(s.validate(), "")
        want = [(-31.3, -66.75, 132.25), (31.3, -66.75, 132.25), (-31.3, 57.0, 132.25), (31.3, 57.0, 132.25),
                (-31.3, -51.3, 74.75), (31.3, -51.3, 74.75), (-31.3, 48.0, 74.75), (31.3, 48.0, 74.75),
                (-21.0, -92.5, 44.25), (21.0, -92.5, 44.25)]
        for s, w in zip(dm.sites, want):
            for got, exp in zip(s.head, w):
                self.assertAlmostEqual(got, exp, places=9)
        self.assertEqual([s.length for s in dm.sites], [16] * 4 + [10] * 4 + [16] * 2)
        self.assertEqual([s.cavity for s in dm.sites], [16.5] * 4 + [10.25] * 4 + [16.25] * 2)

    def test_each_bolt_tip_ends_at_its_nut_cavity(self):
        # Seams are modeled open: the tip ends 0.25 short of the face the cavity opens on (instructions.md).
        for s in derive(default_params()).sites:
            self.assertLessEqual(s.tip(), s.cavity_far() + 1e-9)

    def test_derive_validates(self):
        with self.assertRaises(ValidationError):
            derive(dataclasses.replace(default_params(), digit=10))

    def test_no_nan(self):
        for r in derive(default_params()).ramps:
            for ramp in r:
                self.assertFalse(math.isnan(ramp.start))


class InputsTest(unittest.TestCase):
    def test_one_digit_input(self):
        self.assertEqual([(s.id, s.label, s.default, s.minimum, s.maximum) for s in INPUT_SPECS],
                         [("digit", "Digit", 2, 0, 9)])

    def test_params_from_values(self):
        self.assertEqual(params_from_values({"digit": 7}), dataclasses.replace(default_params(), digit=7))


if __name__ == "__main__":
    unittest.main()
