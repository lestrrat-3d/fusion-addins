import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import bodies, expected, probes
from gen.constants import CLUTCH_MOUNT, LEFT_HAND
from gen.params import default_params, params_608zz
from gen.validate import derive


P128 = dataclasses.replace(default_params(), rotor_diameter=128.0)


class BoundsTest(unittest.TestCase):
    def check(self, p, name, want, delta=0.01):
        got = expected.body_bounds(name, p, derive(p))
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, delta=delta, msg=f"{name}: {got} != {want}")

    def test_hub(self):
        self.check(P128, bodies.HUB, (-14, -14, 0, 14, 14, 20))
        self.check(default_params(), bodies.HUB, (-18.9, -18.9, 0, 18.9, 18.9, 30))
        self.check(dataclasses.replace(default_params(), rotor_diameter=224.0), bodies.HUB, (-18.9, -18.9, 0, 18.9, 18.9, 35))

    def test_blades_against_the_gallery_at_192(self):
        # decad bounds of blade 1 at the default size and pitch, within the spline's overshoot (0.45 at 192).
        p = default_params()
        self.check(p, "Blade 1", (-12.1881, 8.095, 7.5149, 9.1793, 96.0, 26.3859), 0.45)
        left = dataclasses.replace(p, hand=LEFT_HAND)
        self.check(left, "Blade 1", (-9.1793, 8.095, 7.5149, 12.1881, 96.0, 26.3859), 0.45)

    def test_blades_against_the_gallery(self):
        # decad bounds of blades 1 to 3 at 128 and the default pitch, within the spline's overshoot.
        p = P128
        self.check(p, "Blade 1", (-8.2298, 6.1, 5.0203, 6.1102, 64.0, 17.7183), 0.3)
        self.check(p, "Blade 2", (-56.9730, -35.9775, 5.0203, -3.9328, -0.6019, 17.7183), 0.3)
        self.check(p, "Blade 3", (3.9328, -34.6801, 5.0203, 57.7221, -0.6019, 17.7183), 0.3)

    def test_left_hand_blade_is_mirrored(self):
        p = dataclasses.replace(P128, hand=LEFT_HAND)
        self.check(p, "Blade 1", (-6.1102, 6.1, 5.0203, 8.2298, 64.0, 17.7183), 0.3)

    def test_fasteners_at_192(self):
        p = default_params()
        self.check(p, "Set Screw", (-1.9, -13.95, 2.1, 1.9, -1.95, 5.9))  # M2 x 10
        self.check(p, "Set Screw Nut", (-2.0, -5.45, 1.691, 2.0, -3.85, 6.309), 0.001)
        self.check(p, "Blade Bolt 1", (-1.9, 12.825 - 1.9, 3.0, 1.9, 12.825 + 1.9, 30.0))  # M2 x 25, tip at z 3
        # the blade nut spans r 10.515 to 15.135 along its radial line at z 3.6 to 5.2
        self.check(p, "Blade Nut 1", (-2.0, 12.825 - 2.309, 3.6, 2.0, 12.825 + 2.309, 5.2), 0.001)

    def test_fasteners(self):
        p = P128
        self.check(p, "Set Screw", (-1.9, -9.95, 2.1, 1.9, -1.95, 5.9))
        self.check(p, "Set Screw Nut", (-2.0, -5.45, 1.691, 2.0, -3.85, 6.309), 0.001)
        self.check(p, "Blade Bolt 1", (-1.9, 7.6, 2.0, 1.9, 11.4, 20.0))
        # the blade nut spans r 7.19 to 11.81 along its radial line at z 2.6 to 4.2
        self.check(p, "Blade Nut 1", (-2.0, 7.191, 2.6, 2.0, 11.809, 4.2), 0.001)
        p = dataclasses.replace(p, mount=CLUTCH_MOUNT)
        self.check(default_params(), "Adapter Bolt 1", (8.227 - 1.9, 4.75 - 1.9, -6.25, 8.227 + 1.9, 4.75 + 1.9, 5.75), 0.001)
        self.check(p, "Adapter Bolt 1", (8.227 - 1.9, 4.75 - 1.9, -6.25, 8.227 + 1.9, 4.75 + 1.9, 5.75), 0.001)

    def test_every_body_has_ordered_bounds(self):
        for mount in (0, CLUTCH_MOUNT):
            p = dataclasses.replace(default_params(), mount=mount)
            dm = derive(p)
            for name in bodies.body_names(mount):
                b = expected.body_bounds(name, p, dm)
                self.assertTrue(all(b[i] < b[i + 3] for i in range(3)), (name, b))

    def test_tolerances(self):
        self.assertEqual(expected.bounds_tolerance("Hub"), 0.01)
        self.assertEqual(expected.bounds_tolerance("Blade 2"), 0.3)
        self.assertEqual(expected.bounds_tolerance("Blade 2", P128), 0.3)
        self.assertAlmostEqual(expected.bounds_tolerance("Blade 2", default_params()), 0.45)  # grows with the blade


class VolumeTest(unittest.TestCase):
    def test_hub_presets(self):
        # Volumes read from decad builds: both presets at 128, 192 (the default) and 224.
        for d, want605, want608 in ((128.0, 10286.0083, 9703.7406), (192.0, 29974.6904, 29095.0912),
                                    (224.0, 35408.7061, 34380.4426)):
            for p, want in ((default_params(), want605), (params_608zz(), want608)):
                p = dataclasses.replace(p, rotor_diameter=d)
                self.assertAlmostEqual(expected.body_volume(bodies.HUB, p, derive(p)).value, want)
        p = dataclasses.replace(default_params(), bore_clearance=0.35)
        self.assertIsNone(expected.body_volume(bodies.HUB, p, derive(p)))
        p = dataclasses.replace(default_params(), rotor_diameter=150.0)  # an untested size has no expected volume
        self.assertIsNone(expected.body_volume(bodies.HUB, p, derive(p)))
        self.assertIsNone(expected.body_volume("Blade 1", p, derive(p)))

    def test_blades_ignore_the_pitch(self):
        p = default_params()
        q = dataclasses.replace(p, blade_pitch=math.radians(40))
        self.assertEqual(expected.body_volume("Blade 1", p, derive(p)), expected.body_volume("Blade 1", q, derive(q)))
        left = dataclasses.replace(p, hand=LEFT_HAND)
        self.assertAlmostEqual(expected.body_volume("Blade 1", p, derive(p)).value, 6362.3624)
        self.assertAlmostEqual(expected.body_volume("Blade 1", left, derive(left)).value, 6360.6762)
        p128 = dataclasses.replace(P128, hand=LEFT_HAND)
        self.assertAlmostEqual(expected.body_volume("Blade 1", p128, derive(p128)).value, 1945.1454)

    def test_bolt_and_nut(self):
        dm = derive(P128)
        self.assertAlmostEqual(expected.body_volume("Blade Bolt 1", P128, dm).value, 70.33, delta=0.1)  # M2 x 16
        self.assertAlmostEqual(expected.body_volume("Set Screw Nut", P128, dm).value, 16.1489, delta=0.05)
        p = default_params()
        # M2 x 25 is 9 mm longer than M2 x 16: 9 pi mm^3 of shank.
        self.assertAlmostEqual(expected.body_volume("Blade Bolt 1", p, derive(p)).value, 70.33 + 9 * math.pi, delta=0.2)


class BodiesTest(unittest.TestCase):
    def test_counts_and_order(self):
        self.assertEqual(bodies.expected_body_count(0), 12)
        self.assertEqual(bodies.expected_body_count(CLUTCH_MOUNT), 14)
        names = bodies.body_names(0)
        self.assertEqual(names[:4], ("Hub", "Blade 1", "Blade 2", "Blade 3"))
        self.assertIn("Set Screw", names)
        self.assertNotIn("Adapter Bolt 1", names)
        clutch = bodies.body_names(CLUTCH_MOUNT)
        self.assertIn("Adapter Nut 2", clutch)
        self.assertNotIn("Set Screw", clutch)
        self.assertEqual(len(set(clutch)), 14)

    def test_containers(self):
        want = bodies.expected_bodies(CLUTCH_MOUNT)
        self.assertEqual(want["Bolts"], ["Blade Bolt 1", "Blade Bolt 2", "Blade Bolt 3", "Adapter Bolt 1", "Adapter Bolt 2"])
        self.assertEqual(len(want["Nuts"]), 5)
        self.assertEqual((want["Hub"], len(want["Blades"])), (["Hub"], 3))

    def test_check_tree(self):
        for mount in (0, CLUTCH_MOUNT):
            found = [bodies.Found(c, tuple(n), ()) for c, n in bodies.expected_bodies(mount).items()]
            top, results = bodies.check_tree(found, 0, mount)
            self.assertTrue(top.ok and all(r.ok for r in results))
        # a clutch tree is wrong for the shaft mount
        found = [bodies.Found(c, tuple(n), ()) for c, n in bodies.expected_bodies(CLUTCH_MOUNT).items()]
        _, results = bodies.check_tree(found, 0, 0)
        self.assertFalse(all(r.ok for r in results))

    def test_check_tree_reports_problems(self):
        found = [bodies.Found("Hub (1)", ("Hub",), ()), bodies.Found("Blades", ("Blade 1",), ("x",)),
                 bodies.Found("Extra", (), ())]
        top, results = bodies.check_tree(found, 2, 0)
        self.assertFalse(top.ok)
        self.assertIn("2 bodies outside containers", top.detail)
        self.assertTrue(results[0].ok)  # a ` (n)` suffix is ignored
        self.assertIn("missing Blade 2", results[1].detail)
        self.assertIn("extra child x", results[1].detail)
        self.assertEqual(results[2].detail, "no component")


class ProbeTest(unittest.TestCase):
    def test_probes_exist_for_every_printed_body(self):
        for p in (default_params(), params_608zz()):
            got = probes.part_probes(p, derive(p))
            self.assertEqual(sorted(got), sorted(bodies.PRINTED))
            for name, plist in got.items():
                self.assertEqual(len({q.label for q in plist}), len(plist), name)
                self.assertTrue(all(q.expect in (probes.INSIDE, probes.OUTSIDE) for q in plist))

    def test_hub_probes_stay_inside_the_hub_envelope(self):
        for p, radius, length in ((P128, 14.0, 20.0), (default_params(), 18.9, 30.0),
                                  (dataclasses.replace(default_params(), rotor_diameter=224.0), 18.9, 35.0)):
            for q in probes.part_probes(p, derive(p))[bodies.HUB]:
                x, y, z = q.point
                self.assertLess(math.hypot(x, y), radius + 1e-9, q.label)
                self.assertTrue(0.0 <= z <= length, q.label)

    def test_blade_probes_turn_with_the_blade(self):
        p = default_params()
        got = probes.part_probes(p, derive(p))
        one = {q.label: q.point for q in got["Blade 1"]}
        two = {q.label: q.point for q in got["Blade 2"]}
        for label, (x, y, z) in one.items():
            tx, ty, tz = two[label]
            self.assertAlmostEqual(math.hypot(x, y), math.hypot(tx, ty))
            self.assertEqual(z, tz)
        self.assertAlmostEqual(math.degrees(math.atan2(two["blade at r 30 s"][1], two["blade at r 30 s"][0])) % 360.0, 210.0)


if __name__ == "__main__":
    unittest.main()
