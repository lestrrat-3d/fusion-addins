import math
import unittest

import _support  # noqa: F401
from gen import blade
from gen.constants import REF_PITCH
from gen.size import size_for


class StationsTest(unittest.TestCase):
    def setUp(self):
        self.sz128 = size_for(128.0)
        self.sz192 = size_for(192.0)

    def test_table_at_128_is_the_gallerys(self):
        stations = blade.stations_for(self.sz128)
        self.assertEqual(len(stations), 10)
        self.assertEqual([round(s.r, 9) for s in stations], [14.4, 16.3, 19.0, 21.5, 25.0, 30.0, 38.0, 46.0, 55.0, 64.0])
        self.assertEqual([s.chord for s in stations], [8.0, 8.0, 11.5, 15.5, 17.8, 16.5, 14.5, 12.5, 10.5, 8.0])

    def test_table_scales_by_the_blade_scale_and_the_hub_scale(self):
        sz = self.sz192
        base = blade.stations_for(self.sz128)
        big = blade.stations_for(sz)
        # The round root (stations 1 and 2) scales by the hub scale j = 1.35, the airfoil (3 to 10) by s = 1.5.
        self.assertAlmostEqual(big[0].r, 19.3)  # RootRadius = 18.9 + 0.4
        self.assertAlmostEqual(big[0].chord, 8.0 * 1.35)
        self.assertAlmostEqual(big[1].r, 19.3 + 1.9 * 1.35)
        for a, b in zip(base[2:], big[2:]):
            self.assertAlmostEqual(b.r, 1.5 * a.r)
            self.assertAlmostEqual(b.chord, 1.5 * a.chord)
            self.assertEqual((a.ratio, a.camber, a.ellipse), (b.ratio, b.camber, b.ellipse))
        self.assertAlmostEqual(big[-1].r, 96.0)  # the tip radius

    def test_fit_points(self):
        for st in blade.stations_for(self.sz192):
            pts = blade.fit_points(st, False, self.sz192)
            self.assertEqual(len(pts), 21)
            # the leading edge is the middle fit point, and the section is drawn flipped unless mirrored
            self.assertEqual(blade.fit_points(st, True, self.sz192)[10], (-pts[10][0], pts[10][1]))

    def test_beta(self):
        # constant inboard of the hold radius (21.5 s), and the pitch is the angle at the reference radius (48 s)
        for sz in (self.sz128, self.sz192):
            self.assertAlmostEqual(sz.beta(sz.root_radius, REF_PITCH), sz.beta(sz.hold_radius, REF_PITCH))
            self.assertAlmostEqual(sz.beta(sz.ref_radius, REF_PITCH), math.radians(25))
            self.assertAlmostEqual(sz.beta(sz.ref_radius, math.radians(40)), math.radians(40))

    def test_an_enlarged_airfoil_section_has_the_angle_of_the_128_section(self):
        # 192's section at 1.5 r is 128's at r enlarged, so beta agrees there.
        for r in (25.0, 38.0, 55.0):
            self.assertAlmostEqual(self.sz192.beta(1.5 * r, REF_PITCH), self.sz128.beta(r, REF_PITCH))

    def test_pitch_turn(self):
        self.assertAlmostEqual(blade.pitch_turn(math.radians(40), False), math.radians(15))
        self.assertAlmostEqual(blade.pitch_turn(math.radians(40), True), -math.radians(15))
        self.assertEqual(blade.pitch_turn(REF_PITCH, False), 0.0)

    def test_to_hub(self):
        self.assertEqual(blade.to_hub(1.0, 2.0, 30.0, self.sz128), (-1.0, 30.0, 12.0))
        self.assertEqual(blade.to_hub(1.0, 2.0, 30.0, self.sz192), (-1.0, 30.0, 17.0))


class BoundsTest(unittest.TestCase):
    """Bounds of blade 1 in the hub frame, read from decad builds at the gallery revision, within the spline's
    overshoot between fit points (0.3 mm at 128, 1.5 times that at 192)."""

    def check(self, size, pitch, mirror, want, delta=0.3):
        pts = blade.blade_sample_points(math.radians(pitch), mirror, size)
        got = [min(q[i] for q in pts) for i in range(3)] + [max(q[i] for q in pts) for i in range(3)]
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, delta=delta, msg=f"{got} != {want}")

    def test_default_at_128(self):
        self.check(size_for(128.0), 25, False, (-8.2298, 6.1, 5.0203, 6.1102, 64.0, 17.7183))

    def test_flat_and_steep_at_128(self):
        self.check(size_for(128.0), 10, False, (-9.7093, 6.1, 5.8490, 6.8034, 64.0, 15.5478))
        self.check(size_for(128.0), 40, False, (-6.2319, 6.1, 4.1652, 5.1053, 64.0, 19.3878))

    def test_left_hand_at_128(self):
        self.check(size_for(128.0), 25, True, (-6.1102, 6.1, 5.0203, 8.2298, 64.0, 17.7183))

    def test_default_at_192(self):
        sz = size_for(192.0)
        self.check(sz, 25, False, (-12.1881, 8.095, 7.5149, 9.1793, 96.0, 26.3859), delta=0.45)
        self.check(sz, 25, True, (-9.1793, 8.095, 7.5149, 12.1881, 96.0, 26.3859), delta=0.45)

    def test_default_at_224(self):
        self.check(size_for(224.0), 25, False, (-14.1691, 8.095, 8.7622, 10.7138, 112.0, 30.7206), delta=0.5)

    def test_envelope_z_ranges_of_instructions(self):
        # instructions.md, "Blade facts": z 7.51 to 26.39 at 192 and the default pitch, 6.24 to 28.94 at 40 degrees and
        # 8.76 to 23.10 at 10 degrees; every vertex lies in the hub's length.
        sz = size_for(192.0)
        for pitch, lo, hi in ((25, 7.51, 26.39), (40, 6.24, 28.94), (10, 8.76, 23.10)):
            pts = blade.blade_sample_points(math.radians(pitch), False, sz)
            self.assertAlmostEqual(min(q[2] for q in pts), lo, delta=0.45)
            self.assertAlmostEqual(max(q[2] for q in pts), hi, delta=0.45)
            self.assertTrue(all(0.0 <= q[2] <= sz.hub_length for q in pts))
            self.assertTrue(all(math.hypot(q[0], q[1]) <= sz.tip_radius + 0.5 for q in pts))


if __name__ == "__main__":
    unittest.main()
