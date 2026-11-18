import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import bodies, expected, probes
from gen.params import Params, default_params
from gen.validate import derive
from test_params import CASES

# Printed volumes from decad builds (instructions.md "Representative cases"): bracket and rail in mm^3.
DECAD = {
    "default": (27082.87, 7746.18), "min": (12344.22, 4614.89), "max": (36857.07, 9546.67),
    "forward": (24940.22, 9311.82), "narrow-tall": (29290.11, 4614.89), "short-steep": (20671.57, 4614.89),
}


class VolumeTest(unittest.TestCase):
    def test_printed_volumes_match_decad(self):
        for name, (p, *_rest) in CASES.items():
            with self.subTest(case=name):
                dm = derive(p)
                bracket, rail = DECAD[name]
                self.assertAlmostEqual(expected.body_volume(bodies.BRACKET_1, p, dm).value, bracket, delta=0.2)
                self.assertAlmostEqual(expected.body_volume(bodies.BRACKET_2, p, dm).value, bracket, delta=0.2)
                self.assertAlmostEqual(expected.body_volume(bodies.RAIL, p, dm).value, rail, delta=0.2)

    def test_total_printed_volume_of_the_default(self):
        p = default_params()
        dm = derive(p)
        total = 2 * expected.bracket_volume(dm) + expected.rail_volume(dm)
        self.assertAlmostEqual(total / 1000, 61.91, delta=0.01)

    def test_plaque_and_fasteners(self):
        p = default_params()
        dm = derive(p)
        self.assertAlmostEqual(expected.body_volume(bodies.PLAQUE, p, dm).value, 250 * 305 * 12.8)
        self.assertAlmostEqual(expected.body_volume(bodies.BOLT_1, p, dm).value, 38.9114, delta=0.05)  # M2 x 6
        self.assertAlmostEqual(expected.body_volume(bodies.NUT_2, p, dm).value, 16.1489, delta=0.05)

    def test_every_body_has_a_volume(self):
        p = default_params()
        dm = derive(p)
        for name in bodies.BODY_NAMES:
            self.assertGreater(expected.body_volume(name, p, dm).value, 0, name)


class BoundsTest(unittest.TestCase):
    def check(self, name, want, p=None, delta=1e-6):
        p = p or default_params()
        got = expected.body_bounds(name, p, derive(p))
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, delta=delta, msg=f"{name}: {got} != {want}")

    def test_default_printed_bodies(self):
        dm = derive(default_params())
        self.check(bodies.BRACKET_1, (0, 0, 0, 20, 112, dm.height))
        self.check(bodies.BRACKET_2, (180, 0, 0, 200, 112, dm.height))
        self.check(bodies.RAIL, (0, dm.rail_center - 5, 4.4, 200, dm.rail_center + 5, 8.4))

    def test_plaque_is_centred_on_the_span_and_rests_on_the_seat(self):
        p = default_params()
        dm = derive(p)
        b = expected.body_bounds(bodies.PLAQUE, p, dm)
        self.assertAlmostEqual(b[0], -25.0)  # x0 = (S - W) / 2
        self.assertAlmostEqual(b[3], 225.0)
        # The plaque's lowest point is the front-bottom corner, a thickness below the seat's z by (t/2) sin(theta).
        theta = math.radians(15)
        t = 12.8
        self.assertAlmostEqual(b[2], dm.seat[1] - (t / 2) * math.sin(theta) - 0.0, places=6)
        self.assertAlmostEqual(b[5], dm.seat[1] + (t / 2) * math.sin(theta) * 0 + 305 * math.cos(theta)
                               + (t / 2) * math.sin(theta), places=6)

    def test_plaque_axes_are_a_right_handed_frame(self):
        p = default_params()
        o, x, y, z = expected.plaque_axes(p, derive(p))
        cross = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
        for a, b in zip(cross, z):
            self.assertAlmostEqual(a, b)
        self.assertAlmostEqual(math.hypot(*y), 1.0)

    def test_fasteners_sit_on_their_sites(self):
        p = default_params()
        dm = derive(p)
        s = dm.sites[0]
        # M2 x 6: the head's top at z 8.4, the tip 8 below it at 0.4; the nut from z 0.2 to 1.8.
        b = expected.body_bounds(bodies.BOLT_1, p, dm)
        self.assertAlmostEqual(b[2], 0.4)
        self.assertAlmostEqual(b[5], 8.4)
        self.assertAlmostEqual((b[0] + b[3]) / 2, s.head[0])
        n = expected.body_bounds(bodies.NUT_1, p, dm)
        self.assertAlmostEqual(n[2], 0.2)
        self.assertAlmostEqual(n[5], 1.8)

    def test_every_body_has_ordered_bounds(self):
        for name, (p, *_rest) in CASES.items():
            dm = derive(p)
            for body in bodies.BODY_NAMES:
                b = expected.body_bounds(body, p, dm)
                self.assertTrue(all(b[i] < b[i + 3] for i in range(3)), (name, body, b))

    def test_every_case_fits_the_bed(self):
        for name, (p, *_rest) in CASES.items():
            dm = derive(p)
            for body in bodies.PRINTED:
                b = expected.body_bounds(body, p, dm)
                self.assertTrue(all(b[i + 3] - b[i] <= 246.0 + 1e-9 for i in range(3)), (name, body))


class BodiesTest(unittest.TestCase):
    def test_eight_bodies_in_five_containers(self):
        self.assertEqual(bodies.EXPECTED_BODY_COUNT, 8)
        want = bodies.expected_bodies()
        self.assertEqual(list(want), ["Brackets", "Rail", "Bolts", "Nuts", "Plaque"])
        self.assertEqual(want["Brackets"], ["Bracket 1", "Bracket 2"])
        self.assertEqual(want["Bolts"], ["Bolt 1", "Bolt 2"])

    def test_site_of_a_bolt_and_its_nut_agree(self):
        dm = derive(default_params())
        for bolt, nut in zip(bodies.BOLTS, bodies.NUTS):
            self.assertEqual(bodies.site_of(bolt, dm), bodies.site_of(nut, dm))

    def test_tree_check(self):
        found = [bodies.Found(c, tuple(n), ()) for c, n in bodies.expected_bodies().items()]
        top, results = bodies.check_tree(found, 0)
        self.assertTrue(top.ok and all(r.ok for r in results))
        found[0] = bodies.Found("Brackets (1)", ("Bracket 1",), ())
        top, results = bodies.check_tree(found, 0)
        self.assertFalse(results[0].ok)
        self.assertIn("missing Bracket 2", results[0].detail)


class ProbeTest(unittest.TestCase):
    def test_probes_exist_for_every_non_fastener_body(self):
        for name, (p, *_rest) in CASES.items():
            dm = derive(p)
            got = probes.part_probes(p, dm)
            self.assertEqual(sorted(got), sorted(bodies.PRINTED + (bodies.PLAQUE,)), name)
            for body, plist in got.items():
                self.assertEqual(len({q.label for q in plist}), len(plist), (name, body))
                self.assertTrue(all(q.expect in (probes.INSIDE, probes.OUTSIDE) for q in plist))
                self.assertEqual({q.expect for q in plist}, {probes.INSIDE, probes.OUTSIDE}, (name, body))

    def test_inside_probes_lie_in_the_bodys_bounds(self):
        for name, (p, *_rest) in CASES.items():
            dm = derive(p)
            for body, plist in probes.part_probes(p, dm).items():
                lo = expected.body_bounds(body, p, dm)
                for q in plist:
                    if q.expect == probes.INSIDE:
                        for i in range(3):
                            self.assertTrue(lo[i] < q.point[i] < lo[i + 3], (name, body, q.label, q.point, lo))

    def test_a_bracket_grid_follows_its_outline(self):
        p = default_params()
        dm = derive(p)
        grid = [q for q in probes.part_probes(p, dm)[bodies.BRACKET_2] if q.label.startswith("bracket 2")]
        self.assertTrue(40 <= len(grid) <= 70)
        self.assertTrue(all(abs(q.point[0] - 185.0) < 1e-9 for q in grid))  # 5 mm in from the side face at x 180
        self.assertTrue(any(q.expect == probes.INSIDE for q in grid))
        self.assertTrue(any(q.expect == probes.OUTSIDE for q in grid))

    def test_the_channel_probes(self):
        p = default_params()
        dm = derive(p)
        found = {q.label: q for q in probes.part_probes(p, dm)[bodies.BRACKET_1]}
        self.assertEqual(found["channel"].expect, probes.OUTSIDE)
        self.assertEqual(found["nut pocket"].expect, probes.OUTSIDE)
        self.assertEqual(found["nut pocket"].point, (10.0, dm.rail_center, 1.0))
        self.assertEqual(found["beside the channel"].expect, probes.INSIDE)


if __name__ == "__main__":
    unittest.main()
