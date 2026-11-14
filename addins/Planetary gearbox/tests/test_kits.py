import dataclasses
import unittest

import _support  # noqa: F401
from gen.bearing import CATALOG, Spec, catalog_names, lookup
from gen.kits import (
    Kit,
    default_params_for,
    kit_dependent_fields,
    kit_for,
    kit_teeth,
    supported_combinations,
)
from gen.params import default_params

KITS = (
    ("planet605-shaft605", "605ZZ", "605ZZ", (13, 29, 71)),
    ("planet605-shaft608", "605ZZ", "608ZZ", (14, 28, 70)),
    ("planet608-shaft605", "608ZZ", "605ZZ", (13, 29, 71)),
    ("planet608-shaft608", "608ZZ", "608ZZ", (14, 28, 70)),
)


class CatalogTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(catalog_names(), ("605ZZ", "608ZZ"))

    def test_specs(self):
        self.assertEqual(CATALOG[0], Spec("605ZZ", 5.0, 14.0, 5.0, 8.0))
        self.assertEqual(CATALOG[1], Spec("608ZZ", 8.0, 22.0, 7.0, 12.0))

    def test_lookup(self):
        self.assertEqual(lookup("605ZZ"), CATALOG[0])
        self.assertEqual(lookup("608ZZ"), CATALOG[1])
        self.assertIsNone(lookup("609ZZ"))
        self.assertIsNone(lookup("605zz"))

    def test_derived_diameters(self):
        s5, s8 = CATALOG
        self.assertEqual((s5.shaft_diameter(), s8.shaft_diameter()), (5.0, 8.0))
        self.assertAlmostEqual(s5.seat_diameter(), 14.1, places=12)
        self.assertAlmostEqual(s8.seat_diameter(), 22.1, places=12)
        self.assertAlmostEqual(s5.press_bore_diameter(), 5.1, places=12)
        self.assertAlmostEqual(s8.press_bore_diameter(), 8.1, places=12)


class KitsTest(unittest.TestCase):
    def test_supported_combinations(self):
        got = supported_combinations()
        self.assertEqual([k.name for k in got], [k[0] for k in KITS])
        self.assertEqual(got[0], Kit("planet605-shaft605", "605ZZ", "605ZZ"))

    def test_default_params_for(self):
        base = default_params()
        for name, pb, sb, teeth in KITS:
            with self.subTest(kit=name):
                p = default_params_for(name)
                self.assertEqual((p.planet_bearing, p.shaft_bearing), (pb, sb))
                self.assertEqual((p.sun_teeth, p.planet_teeth, p.ring_teeth), teeth)
                rest = dataclasses.replace(
                    p,
                    planet_bearing=base.planet_bearing,
                    shaft_bearing=base.shaft_bearing,
                    sun_teeth=base.sun_teeth,
                    planet_teeth=base.planet_teeth,
                    ring_teeth=base.ring_teeth,
                )
                self.assertEqual(rest, base)

    def test_default_kit_is_default_params(self):
        self.assertEqual(default_params_for("planet605-shaft605"), default_params())

    def test_unknown_kit(self):
        with self.assertRaises(ValueError) as cm:
            default_params_for("planet609-shaft605")
        self.assertEqual(
            str(cm.exception),
            'unknown kit "planet609-shaft605"; choose one of planet605-shaft605, planet605-shaft608, '
            "planet608-shaft605, planet608-shaft608",
        )

    def test_kit_for(self):
        for name, pb, sb, teeth in KITS:
            with self.subTest(kit=name):
                k = kit_for(pb, sb)
                self.assertEqual(k.name, name)
                self.assertEqual(kit_teeth(k), teeth)
        self.assertIsNone(kit_for("605ZZ", ""))

    def test_kit_dependent_fields(self):
        self.assertEqual(kit_dependent_fields(), ("sun_teeth", "planet_teeth", "ring_teeth"))


if __name__ == "__main__":
    unittest.main()
