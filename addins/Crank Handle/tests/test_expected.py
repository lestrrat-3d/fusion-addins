import dataclasses
import unittest

import _support  # noqa: F401
from gen import bodies, expected, probes
from gen.params import default_params, params_6082rs
from gen.report import within
from gen.validate import derive


class BoundsTest(unittest.TestCase):
    """Bounds of the gallery model's bodies, read from a decad build (605ZZ and 608-2RS)."""

    def check(self, p, name, want):
        got = expected.body_bounds(name, p, derive(p))
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, delta=0.01, msg=f"{name}: {got} != {want}")

    def test_605zz(self):
        p = default_params()
        self.check(p, bodies.ARM, (-10, -13.881, 0, 10, 65, 17))
        self.check(p, bodies.PIN, (-6.45, 48.55, 3.5, 6.45, 61.45, 58))
        self.check(p, bodies.HANDLE, (-9.3, 45.7, 8.4, 9.3, 64.3, 58.4))
        self.check(p, bodies.PIN_BOLT, (-1.9, 53.1, 0, 1.9, 56.9, 12))
        self.check(p, bodies.PIN_NUT, (-2.309, 53.0, 4.95, 2.309, 57.0, 6.55))
        self.check(p, bodies.CROSS_BOLT_1, (-1.9, 51.0, 15.1, 1.9, 59.0, 18.9))
        self.check(p, bodies.CLAMP_BOLT_1, (-8, -6.8, 2.1, 10, -3.0, 5.9))
        self.check(p, bodies.CLAMP_BOLT_2, (-8, -6.8, 10.1, 10, -3.0, 13.9))
        # The nuts' corners point along Z (clamp) and across the pin (cross), gallery #275.
        self.check(p, bodies.CLAMP_NUT_1, (-7.8, -6.9, 1.691, -6.2, -2.9, 6.309))
        self.check(p, bodies.CLAMP_NUT_2, (-7.8, -6.9, 9.691, -6.2, -2.9, 14.309))
        self.check(p, bodies.CROSS_NUT_1, (-2.309, 51.2, 15.0, 2.309, 52.8, 19.0))

    def test_608_2rs(self):
        p = params_6082rs()
        self.check(p, bodies.ARM, (-10, -15.381, 0, 10, 65, 17))
        self.check(p, bodies.CLAMP_BOLT_1, (-8, -8.3, 2.1, 10, -4.5, 5.9))
        self.check(p, bodies.CLAMP_BOLT_2, (-8, -8.3, 10.1, 10, -4.5, 13.9))
        self.check(p, bodies.CLAMP_NUT_1, (-7.8, -8.4, 1.691, -6.2, -4.4, 6.309))
        self.check(p, bodies.CLAMP_NUT_2, (-7.8, -8.4, 9.691, -6.2, -4.4, 14.309))

    def test_every_body_has_bounds_in_order(self):
        p = default_params()
        dm = derive(p)
        for name in bodies.BODY_NAMES:
            b = expected.body_bounds(name, p, dm)
            self.assertTrue(all(b[i] < b[i + 3] for i in range(3)), (name, b))


class VolumeTest(unittest.TestCase):
    def test_fixed_bodies(self):
        p = default_params()
        dm = derive(p)
        self.assertAlmostEqual(expected.body_volume(bodies.PIN, p, dm).value, 4098.4072)
        self.assertAlmostEqual(expected.body_volume(bodies.HANDLE, p, dm).value, 4513.6335)
        self.assertAlmostEqual(expected.body_volume(bodies.CLAMP_BOLT_2, p, dm).value, 70.317, delta=0.2)
        self.assertAlmostEqual(expected.body_volume(bodies.CROSS_NUT_2, p, dm).value, 16.1489, delta=0.05)

    def test_arm_presets_and_throw(self):
        # decad volumes of the arm: 605ZZ 16418.6639 and 608-2RS (double flat) 16471.1251 at throw 55 (65: 18013.6488 and
        # 18066.1040; 40: 14026.2243 and 14078.6409). The 605ZZ values at throw 80 are the throw 55 value plus 159.5 mm^3
        # per mm, to the gallery's 0.5.
        self.assertAlmostEqual(expected.arm_volume(default_params()), 16418.6639)
        self.assertAlmostEqual(expected.arm_volume(params_6082rs()), 16471.1251)
        for throw, want in ((40.0, 14026.2243), (65.0, 18013.6488)):
            got = expected.arm_volume(dataclasses.replace(default_params(), throw=throw))
            self.assertAlmostEqual(got, want, delta=0.5)

    def test_arm_volume_is_unknown_for_other_bores(self):
        p = dataclasses.replace(default_params(), shaft_diameter=6.0)
        self.assertIsNone(expected.arm_volume(p))
        self.assertIsNone(expected.body_volume(bodies.ARM, p, derive(p)))

    def test_tolerance(self):
        p = default_params()
        vol = expected.body_volume(bodies.ARM, p, derive(p))
        self.assertTrue(within(16418.0, vol))
        self.assertFalse(within(16428.0, vol))


class BodiesTest(unittest.TestCase):
    def test_thirteen_bodies_in_five_containers(self):
        self.assertEqual(len(bodies.BODY_NAMES), 13)
        self.assertEqual(len(set(bodies.BODY_NAMES)), 13)
        want = bodies.expected_bodies()
        self.assertEqual(list(want), ["Arm", "Pin", "Handle", "Bolts", "Nuts"])
        self.assertEqual(want["Bolts"], ["Pin Bolt", "Cross Bolt 1", "Cross Bolt 2", "Clamp Bolt 1", "Clamp Bolt 2"])
        self.assertEqual(want["Nuts"], ["Pin Nut", "Cross Nut 1", "Cross Nut 2", "Clamp Nut 1", "Clamp Nut 2"])

    def test_bolt_and_nut_of_a_site_agree(self):
        dm = derive(default_params())
        for bolt, nut in zip(bodies.BOLTS, bodies.NUTS):
            self.assertEqual(bodies.site_of(bolt, dm), bodies.site_of(nut, dm))

    def test_tree_check(self):
        found = [bodies.Found(c, tuple(n), ()) for c, n in bodies.expected_bodies().items()]
        top, results = bodies.check_tree(found, 0)
        self.assertTrue(top.ok)
        self.assertEqual([r.ok for r in results], [True] * 5)

    def test_tree_check_ignores_fusions_number_suffix(self):
        found = [bodies.Found(c + (" (1)" if c in ("Bolts", "Nuts") else ""), tuple(n), ())
                 for c, n in bodies.expected_bodies().items()]
        top, results = bodies.check_tree(found, 0)
        self.assertTrue(top.ok, top.detail)
        self.assertEqual([r.ok for r in results], [True] * 5)

    def test_tree_check_reports_problems(self):
        found = [bodies.Found(c, tuple(n), ()) for c, n in bodies.expected_bodies().items()]
        found[0] = bodies.Found("Arm", (), ())
        found[1] = bodies.Found("Pin", ("Pin", "Arm"), ("Sub",))
        found.append(bodies.Found("Extra", (), ()))
        top, results = bodies.check_tree(found, 2)
        self.assertFalse(top.ok)
        self.assertIn("2 bodies outside containers", top.detail)
        self.assertIn("extra container Extra", top.detail)
        self.assertFalse(results[0].ok)
        self.assertEqual(results[0].detail, "missing Arm")
        self.assertFalse(results[1].ok)
        self.assertIn("extra Arm", results[1].detail)
        self.assertIn("extra child Sub", results[1].detail)
        top, _ = bodies.check_tree([], 0)
        self.assertIn("missing container Arm, Bolts, Handle +2", top.detail)


class ProbeTest(unittest.TestCase):
    def test_probes_sit_in_the_bodies_bounds_or_just_outside(self):
        for name, p in (("605zz", default_params()), ("608-2rs", params_6082rs())):
            dm = derive(p)
            for part, plist in probes.part_probes(p, dm).items():
                self.assertGreaterEqual(len(plist), 5)
                lo = expected.body_bounds(part, p, dm)
                for probe in plist:
                    with self.subTest(case=name, part=part, probe=probe.label):
                        self.assertIn(probe.expect, (probes.INSIDE, probes.OUTSIDE))
                        if probe.expect == probes.INSIDE:
                            for i in range(3):
                                self.assertTrue(lo[i] < probe.point[i] < lo[i + 3], (probe.point, lo))

    def test_probes_are_labelled_once(self):
        p = default_params()
        for part, plist in probes.part_probes(p, derive(p)).items():
            labels = [x.label for x in plist]
            self.assertEqual(len(labels), len(set(labels)), part)


if __name__ == "__main__":
    unittest.main()
