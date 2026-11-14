import dataclasses
import unittest

import _support  # noqa: F401
from gen.kits import default_params_for, supported_combinations
from gen.params import default_params
from gen.validate import (
    ValidationError,
    _centre_hole_problem,
    _collar_lip_problem,
    _collar_race_problem,
    _pin_race_problem,
    problems,
    validate,
)


def with_(base, **changes):
    return dataclasses.replace(base, **changes)


class ProblemsTest(unittest.TestCase):
    def test_default_and_kits_are_clean(self):
        self.assertEqual(problems(default_params()), [])
        for k in supported_combinations():
            with self.subTest(kit=k.name):
                self.assertEqual(problems(default_params_for(k.name)), [])

    def test_shaft_608_at_605_teeth(self):
        p = with_(default_params(), shaft_bearing="608ZZ")
        self.assertEqual(
            problems(p)[0],
            "the 8.1 mm shaft bore leaves less than one module of wall under the sun root; "
            "SunTeeth must be at least 14 for the 8.1 mm shaft at module 1; try 14/28/70",
        )

    def test_planet_608_at_too_few_teeth(self):
        p = with_(default_params(), planet_bearing="608ZZ", planet_teeth=26, ring_teeth=65)
        self.assertIn("PlanetTeeth must be at least 28 for the 608ZZ planet bearing at module 1; try 13/29/71",
                      problems(p)[0])

    def test_planet_608_gear_thickness(self):
        p = with_(default_params(), planet_bearing="608ZZ", gear_thickness=7.5)
        self.assertIn("a 608ZZ planet bearing needs GearThickness >= 8", problems(p)[0])

    def test_divisibility_alone(self):
        p = with_(default_params_for("planet605-shaft608"), sun_teeth=14, planet_teeth=29, ring_teeth=72)
        got = problems(p)
        self.assertEqual(len(got), 1)
        self.assertIn("must divide by planet count", got[0])

    def test_planet_count_zero(self):
        got = problems(with_(default_params(), planet_count=0))
        self.assertTrue(got)

    def test_unknown_names(self):
        got = problems(with_(default_params(), planet_bearing="609ZZ", shaft_bearing="610ZZ"))
        self.assertEqual(len(got), 2)
        self.assertIn('planet bearing "609ZZ" is not in the bearing catalog; choose one of 605ZZ, 608ZZ', got[0])
        self.assertIn('shaft bearing "610ZZ"', got[1])

    def test_module_half_has_no_suggestion(self):
        p = with_(default_params(), shaft_bearing="608ZZ", module=0.5)
        first = problems(p)[0]
        self.assertTrue(first.endswith("SunTeeth must be at least 23 for the 8.1 mm shaft at module 0.5"), first)
        self.assertNotIn("; try", first)

    def test_two_independent_faults(self):
        got = problems(with_(default_params(), cover_thickness=2.5, flat_depth=1.2))
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0].startswith("cover thickness 2.5 leaves less than 1"), got[0])
        self.assertTrue(got[1].startswith("flat depth 1.2 must stay under the 1.2 collar margin"), got[1])

    def test_bearing_fit_rules(self):
        self.assertEqual(
            _collar_race_problem(7.4, 7.4, "605ZZ"),
            "the 7.4 mm shaft collar is not narrower than the 7.4 mm inner race of the 605ZZ shaft bearing",
        )
        self.assertEqual(_collar_race_problem(7.4, 8, "605ZZ"), "")
        self.assertEqual(
            _pin_race_problem(10.4, 10.4, "608ZZ"),
            "the 10.4 mm pin thick part is not narrower than the 10.4 mm inner race of the 608ZZ planet bearing",
        )
        self.assertEqual(_pin_race_problem(7.4, 8, "605ZZ"), "")
        self.assertEqual(
            _collar_lip_problem(7.4, 7.8),
            "the 7.4 mm shaft collar does not pass the 7.8 mm cover lip bore with 0.25 on each side",
        )
        self.assertEqual(_collar_lip_problem(7.4, 10), "")
        self.assertEqual(
            _centre_hole_problem(10, 10.4, 10.4),
            "the carrier's centre hole and pin sockets leave -0.5 of plate between them, less than 1",
        )
        self.assertEqual(_centre_hole_problem(21, 7.4, 7.4), "")

    def test_validate_raises_first_problem(self):
        cases = [
            with_(default_params(), shaft_bearing="608ZZ"),
            with_(default_params(), planet_bearing="609ZZ", shaft_bearing="610ZZ"),
            with_(default_params(), cover_thickness=2.5, flat_depth=1.2),
            with_(default_params(), planet_count=0),
        ]
        for p in cases:
            with self.subTest(p=(p.planet_bearing, p.shaft_bearing, p.planet_count)):
                with self.assertRaises(ValidationError) as cm:
                    validate(p)
                self.assertEqual(str(cm.exception), problems(p)[0])


if __name__ == "__main__":
    unittest.main()
