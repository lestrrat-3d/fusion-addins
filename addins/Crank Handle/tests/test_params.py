import dataclasses
import unittest

import _support  # noqa: F401
from gen.inputs import INPUT_SPECS, params_from_values
from gen.params import Frame, default_params, params_6082rs, placement_frame
from gen.validate import ValidationError, derive, validate


class DerivedTest(unittest.TestCase):
    """The derived values of instructions.md "Presets and defaults"."""

    def test_605zz(self):
        dm = derive(default_params())
        self.assertAlmostEqual(dm.bore_radius, 2.55, places=12)
        self.assertAlmostEqual(dm.bore_flat, 2.05, places=12)
        self.assertAlmostEqual(dm.bore_loop, 15.8, delta=0.05)
        self.assertAlmostEqual(dm.clamp_y, -4.90, places=12)
        self.assertAlmostEqual(dm.side_end, -8.50, places=12)
        self.assertAlmostEqual(dm.reach, 13.89, delta=0.01)

    def test_6082rs(self):
        dm = derive(params_6082rs())
        self.assertAlmostEqual(dm.bore_radius, 4.05, places=12)
        self.assertAlmostEqual(dm.bore_flat, 3.30, places=12)
        self.assertAlmostEqual(dm.bore_loop, 25.13, delta=0.01)
        self.assertAlmostEqual(dm.clamp_y, -6.40, places=12)
        self.assertAlmostEqual(dm.side_end, -10.0, places=12)
        self.assertAlmostEqual(dm.reach, 15.39, delta=0.01)

    def test_sites(self):
        dm = derive(default_params())
        self.assertEqual(dm.site.head, (0.0, 55.0, 0.0))
        self.assertEqual([s.head for s in dm.cross_sites], [(0.0, 59.0, 17.0), (0.0, 59.0, 49.0)])
        self.assertEqual(dm.clamp_site.head[0::2], (10.0, 4.0))
        self.assertAlmostEqual(dm.clamp_site.head[1], -4.9, places=12)
        for site in (dm.site, dm.clamp_site) + dm.cross_sites:
            self.assertEqual(site.validate(), "")
        # The clamp and cross bolts' tips end flush with the face their nut pocket opens to.
        for site in (dm.clamp_site,) + dm.cross_sites:
            self.assertAlmostEqual(site.tip(), site.cavity_far(), places=9)

    def test_throw_moves_the_pin_sites(self):
        dm = derive(dataclasses.replace(default_params(), throw=80.0))
        self.assertEqual(dm.site.head[1], 80.0)
        self.assertEqual(dm.cross_sites[0].head[1], 84.0)


class ValidationTest(unittest.TestCase):
    def fails(self, message, **changes):
        with self.assertRaises(ValidationError) as cm:
            validate(dataclasses.replace(default_params(), **changes))
        self.assertEqual(str(cm.exception), message)

    def test_default_is_valid(self):
        validate(default_params())
        validate(params_6082rs())

    def test_positive_finite(self):
        self.fails("ShaftDiameter must be finite and positive", shaft_diameter=0.0)
        self.fails("FlatDepth must be finite and positive", flat_depth=float("nan"))
        self.fails("BoreClearance must be finite and positive", bore_clearance=-0.1)
        self.fails("Throw must be finite and positive", throw=float("inf"))

    def test_flat_depth(self):
        validate(dataclasses.replace(default_params(), flat_depth=1.25))
        self.fails("FlatDepth must be at most a quarter of ShaftDiameter", flat_depth=1.26)

    def test_bore_clearance_range(self):
        validate(dataclasses.replace(default_params(), bore_clearance=0.5))
        self.fails("BoreClearance must be from 0.05 to 0.5 mm", bore_clearance=0.04)
        self.fails("BoreClearance must be from 0.05 to 0.5 mm", bore_clearance=0.51)

    def test_largest_shaft(self):
        validate(dataclasses.replace(default_params(), shaft_diameter=16.7, flat_depth=0.5))
        self.fails("ShaftDiameter leaves less than a 1.6 mm wall in the 20 mm arm", shaft_diameter=16.8)

    def test_throw(self):
        validate(dataclasses.replace(default_params(), throw=20.0))
        self.fails("Throw must be at least 20 mm", throw=19.9)

    def test_placement(self):
        self.fails("Placement must be a valid frame", placement=Frame(u=(1.0, 0.0, 0.0), v=(2.0, 0.0, 0.0)))

    def test_order_of_rules(self):
        # The first failing rule is reported: finiteness before the flat, the flat before the clearance.
        self.fails("ShaftDiameter must be finite and positive", shaft_diameter=-1.0, flat_depth=9.0)
        self.fails("FlatDepth must be at most a quarter of ShaftDiameter", flat_depth=9.0, bore_clearance=9.0)


class InputsTest(unittest.TestCase):
    def test_defaults_are_the_605zz_preset(self):
        values = {s.id: s.default for s in INPUT_SPECS}
        self.assertEqual(params_from_values(values), default_params())

    def test_bore_diameter_is_an_input(self):
        spec = INPUT_SPECS[0]
        self.assertEqual((spec.id, spec.label, spec.default), ("shaft_diameter", "Shaft bore diameter", 5.0))
        values = {s.id: s.default for s in INPUT_SPECS} | {"shaft_diameter": 8.0, "flat_depth": 0.75}
        self.assertEqual(params_from_values(values), params_6082rs())

    def test_split_pin_is_an_option_off_by_default(self):
        spec = INPUT_SPECS[-1]
        self.assertEqual((spec.id, spec.label, spec.kind, spec.default), ("split_pin", "Split pin", "bool", 0))
        self.assertFalse(default_params().split_pin)
        values = {s.id: s.default for s in INPUT_SPECS}
        self.assertFalse(params_from_values(values).split_pin)
        values["split_pin"] = 1.0
        self.assertTrue(params_from_values(values).split_pin)
        self.assertEqual(params_from_values(values), dataclasses.replace(default_params(), split_pin=True))

    def test_rounding_keeps_the_minimum_clearance_valid(self):
        # Fusion hands back centimeters; 0.005 cm * 10 can land an ulp under 0.05.
        values = {s.id: s.default for s in INPUT_SPECS} | {"bore_clearance": 0.05 - 1e-17}
        validate(params_from_values(values))
        values["bore_clearance"] = 0.0049999999999999 * 10
        validate(params_from_values(values))


class PlacementTest(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(placement_frame(None, None))

    def test_axis_is_z(self):
        f = placement_frame((1.0, 2.0, 3.0), (0.0, 0.0, 2.0))
        self.assertEqual(f.origin, (1.0, 2.0, 3.0))
        self.assertEqual(f.u, (1.0, 0.0, 0.0))

    def test_zero_axis(self):
        with self.assertRaises(ValueError):
            placement_frame(None, (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
