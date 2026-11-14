import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen.params import KITS, Frame, default_params, default_params_for
from gen.validate import ValidationError, problems, validate

CASES = [
    ({"ring_teeth": 72}, "ring teeth"),
    ({"planet_count": 5}, "planet count"),
    ({"planet_count": 6}, "neighbouring planet centers"),
    ({"planet_count": 1}, "planet count"),
    ({"stages": 0}, "stages"),
    ({"module": 0}, "module"),
    ({"bolt_hole_diameter": 6}, "bolt holes"),
    ({"ring_wall": 3}, "bolt holes"),
    ({"carrier_wall": 12}, "no room for spokes"),
    ({"gear_thickness": 5.5}, "gear thickness"),
    ({"flat_depth": 3}, "flat depth"),
    ({"carrier_thickness": 1.9}, "carrier thickness"),
    ({"seat_chamfer": 2}, "seat chamfer"),
    ({"edge_chamfer": 0.49}, "edge chamfer"),
    ({"edge_chamfer": 1.01}, "edge chamfer"),
    ({"edge_chamfer": float("nan")}, "EdgeChamfer must be finite"),
    ({"bearing_clearance": -0.1}, "bearing clearance"),
    ({"placement": Frame((0, 0, 0), (0, 0, 0), (0, 0, 0))}, "placement"),
    ({"gear_thickness": float("nan")}, "finite"),
    ({"samples": 2}, "samples"),
    ({"backlash": -0.1}, "backlash"),
    ({"backlash": 0.6}, "backlash"),
    ({"pressure_angle": math.pi / 2}, "pressure angle"),
    ({"sun_teeth": 2}, "sun teeth"),
    ({"stage_gap": 0.5}, "stage gap"),
    ({"bearing_clearance": 0.04}, "bearing clearance"),
    ({"bolt_hole_diameter": 2.1}, "M2 bolt shank"),
    ({"bolt_hole_diameter": 2.3}, "clearance hole"),
    ({"bolt_hole_diameter": 1.5}, "shank"),
    ({"cover_thickness": 2.5}, "bolt head"),
    ({"ring_wall": 6}, "bolt head and nut pockets"),
    ({"module": 0.5}, "shaft bore"),
]


class ValidateTest(unittest.TestCase):
    def test_default_passes(self):
        validate(default_params())

    def test_valid_placement_passes(self):
        validate(dataclasses.replace(default_params(), placement=Frame((10, -5, 7), (0, 1, 0), (0, 0, 1))))

    def test_invalid_rows(self):
        for changes, want in CASES:
            with self.subTest(changes=changes):
                p = dataclasses.replace(default_params(), **changes)
                with self.assertRaises(ValidationError) as cm:
                    validate(p)
                self.assertIn(want, str(cm.exception))

    def test_exact_messages(self):
        with self.assertRaises(ValidationError) as cm:
            validate(dataclasses.replace(default_params(), ring_teeth=72))
        self.assertEqual(str(cm.exception), "ring teeth 72 must equal sun teeth + 2 * planet teeth = 71")
        with self.assertRaises(ValidationError) as cm:
            validate(dataclasses.replace(default_params(), gear_thickness=5.5))
        self.assertEqual(
            str(cm.exception),
            "gear thickness 5.5 leaves less than 1 for the lip behind a 5 wide bearing; "
            "a 605ZZ planet bearing needs GearThickness >= 6",
        )
        with self.assertRaises(ValidationError) as cm:
            validate(dataclasses.replace(default_params(), gear_thickness=float("nan")))
        self.assertEqual(str(cm.exception), "GearThickness must be finite, got NaN")

    def test_new_exact_messages(self):
        cases = [
            ({"planet_count": 6}, "neighbouring planet centers are 20.999999999999996 apart; tips need 31.46 for at "
             "least 0.5 clearance"),
            ({"module": 0.5}, "the 5.1 mm shaft bore leaves less than one module of wall under the sun root; "
             "SunTeeth must be at least 17 for the 5.1 mm shaft at module 0.5"),
            ({"flat_depth": 1.3}, "flat depth 1.3 is out of range"),
            ({"carrier_thickness": 1.9}, "carrier thickness 1.9 is out of range"),
            ({"flat_depth": -0.1}, "flat depth -0.1 is out of range"),
            ({"flat_depth": float("nan")}, "FlatDepth must be finite, got NaN"),
            ({"bolt_hole_diameter": 2.1}, "bolt hole diameter 2.1 is under the 2.6 clearance hole for the M2 bolt "
             "shank 2"),
            ({"bolt_hole_diameter": 1.5}, "bolt hole diameter 1.5 is under the 2.6 clearance hole for the M2 bolt "
             "shank 2"),
            ({"cover_thickness": 2.5}, "cover thickness 2.5 leaves less than 1 under a 2 tall bolt head"),
            ({"ring_wall": 6}, "bolt head and nut pockets of radius 2.5094010767585035 do not fit the ring wall 6 with 1 of "
             "material either side"),
            ({"stage_gap": 0.5}, "stage gap 0.5 is out of range"),
            ({"edge_chamfer": 0.4}, "edge chamfer 0.4 is out of range"),
            ({"edge_chamfer": float("inf")}, "EdgeChamfer must be finite, got +Inf"),
            ({"bearing_clearance": 0.04}, "bearing clearance 0.04 is out of range"),
            ({"bolt_hole_diameter": 3.4, "ring_wall": 13, "carrier_wall": 10.5},
             "carrier radius 34 does not leave more than 0.5 clearance from ring tip radius 34.5"),
        ]
        for changes, want in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError) as cm:
                    validate(dataclasses.replace(default_params(), **changes))
                self.assertEqual(str(cm.exception), want)

    def test_boundaries(self):
        base = default_params()
        validate(dataclasses.replace(base, edge_chamfer=0.5))
        validate(dataclasses.replace(base, carrier_thickness=2))
        validate(dataclasses.replace(base, edge_chamfer=1.0))
        validate(dataclasses.replace(base, bolt_hole_diameter=4))
        validate(dataclasses.replace(base, bolt_hole_diameter=2.6))
        with self.assertRaisesRegex(ValidationError, "clearance hole"):
            validate(dataclasses.replace(base, bolt_hole_diameter=2.59))
        with self.assertRaisesRegex(ValidationError, "bolt holes"):
            validate(dataclasses.replace(base, bolt_hole_diameter=4.11))
        cb = (1.0 * 29 / 2 - (1.0 + 0.5 + 0.02)) - 1.0 - 14.0 / 2
        validate(dataclasses.replace(base, bearing_clearance=cb))
        with self.assertRaisesRegex(ValidationError, "bearing pocket"):
            validate(dataclasses.replace(base, bearing_clearance=cb + 0.01))
        wide = dataclasses.replace(base, bolt_hole_diameter=3.4, ring_wall=13)
        validate(dataclasses.replace(wide, carrier_wall=10.49))
        with self.assertRaisesRegex(ValidationError, "carrier radius"):
            validate(dataclasses.replace(wide, carrier_wall=10.5))

    def test_press_fit_rules(self):
        base = default_params()
        validate(dataclasses.replace(base, flat_depth=1.19))
        validate(dataclasses.replace(base, carrier_wall=2.25))
        with self.assertRaisesRegex(ValidationError, "flat depth 1.2 must stay under the 1.2 collar margin"):
            validate(dataclasses.replace(base, flat_depth=1.2))
        with self.assertRaisesRegex(ValidationError, "carrier wall 2.2 leaves .* of plate around a pin socket, less than 1$"):
            validate(dataclasses.replace(base, carrier_wall=2.2))
        with self.assertRaisesRegex(ValidationError, "carrier wall 2.5 and edge chamfer 1 leave 0.25 of plate"):
            validate(dataclasses.replace(base, carrier_wall=2.5, edge_chamfer=1.0))

    def test_planet_count_divisibility_message(self):
        with self.assertRaises(ValidationError) as cm:
            validate(dataclasses.replace(default_params(), planet_count=5))
        self.assertEqual(
            str(cm.exception),
            "sun teeth + ring teeth = 84 must divide by planet count 5 so the planets mesh at equal angles",
        )

    def test_spur_limit_is_prefixed(self):
        # At 40 degrees the ring tool's adjacent flanks overlap at the root, which only the spur limits catch.
        p = dataclasses.replace(default_params(), pressure_angle=math.radians(40))
        with self.assertRaises(ValidationError) as cm:
            validate(p)
        self.assertEqual(
            str(cm.exception),
            (
                "ring tooth spaces: spurgear: tooth: spurgear: tooth section: "
                "spurgear: adjacent teeth overlap at the root circle (radius 34.5)"
            ),
        )


class KitValidateTest(unittest.TestCase):
    """The bearing kits and the gallery's bearing rules [problems_test.go, kits_test.go]."""

    def test_every_kit_validates(self):
        for kit in KITS:
            with self.subTest(kit=kit.name):
                self.assertEqual(problems(default_params_for(kit.name)), [])
                validate(default_params_for(kit.name))

    def test_unknown_bearing_names(self):
        for field, role in (("planet_bearing", "planet"), ("shaft_bearing", "shaft")):
            with self.subTest(field=field):
                want = f'{role} bearing "609ZZ" is not in the bearing catalog; choose one of 605ZZ, 608ZZ'
                self.assertEqual(problems(dataclasses.replace(default_params(), **{field: "609ZZ"})), [want])

    def test_608_shaft_with_default_teeth_names_the_kit(self):
        p = dataclasses.replace(default_params(), shaft_bearing="608ZZ")
        got = problems(p)
        self.assertEqual(got[0], (
            "the 8.1 mm shaft bore leaves less than one module of wall under the sun root; "
            "SunTeeth must be at least 14 for the 8.1 mm shaft at module 1; try 14/28/70"
        ))
        with self.assertRaises(ValidationError) as cm:
            validate(p)
        self.assertEqual(str(cm.exception), got[0])

    def test_608_planet_pocket_wall(self):
        p = dataclasses.replace(default_params(), planet_bearing="608ZZ", sun_teeth=13, planet_teeth=26, ring_teeth=65)
        self.assertIn("PlanetTeeth must be at least 28 for the 608ZZ planet bearing", problems(p)[0])

    def test_608_planet_lip(self):
        p = dataclasses.replace(default_params(), planet_bearing="608ZZ", gear_thickness=7.5)
        self.assertIn("a 608ZZ planet bearing needs GearThickness >= 8", problems(p)[0])

    def test_input_problems_stop_before_the_fit_checks(self):
        p = dataclasses.replace(default_params(), shaft_bearing="608ZZ", sun_teeth=14, planet_teeth=29, ring_teeth=72)
        got = problems(p)
        self.assertEqual(len(got), 1)
        self.assertIn("must divide by planet count", got[0])

    def test_planet_count_zero_does_not_raise(self):
        self.assertTrue(problems(dataclasses.replace(default_params(), planet_count=0)))

    def test_each_unknown_bearing_is_reported_once(self):
        p = dataclasses.replace(default_params(), planet_bearing="609ZZ", shaft_bearing="610ZZ")
        got = problems(p)
        self.assertEqual(len(got), 2)
        self.assertIn('planet bearing "609ZZ"', got[0])
        self.assertIn('shaft bearing "610ZZ"', got[1])

    def test_input_problems_come_alone(self):
        p = dataclasses.replace(default_params(), shaft_bearing="608ZZ", flat_depth=-1)
        self.assertEqual(problems(p), ["flat depth -1 is out of range"])


if __name__ == "__main__":
    unittest.main()
