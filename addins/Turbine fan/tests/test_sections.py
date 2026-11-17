import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import fasteners, sections
from gen.curves import Arc, Line, loop_is_closed
from gen.params import default_params, params_608zz
from gen.validate import derive


class SectionsTest(unittest.TestCase):
    def test_bore_loop_is_the_d(self):
        for p, loop_len in ((default_params(), 15.81), (params_608zz(), 25.13)):
            dm = derive(p)
            loop = sections.bore_loop(dm)
            self.assertTrue(loop_is_closed(loop))
            arc, flat = loop
            self.assertIsInstance(arc, Arc)
            self.assertIsInstance(flat, Line)
            self.assertAlmostEqual(arc.start[1], -dm.bore_flat)
            self.assertAlmostEqual(arc.start[0], dm.bore_flat_width / 2)
            self.assertEqual(arc.end, flat.start)
            self.assertAlmostEqual(math.hypot(*arc.start), dm.bore_radius)
            # counter-clockwise from the right end of the flat over +Y: sweep = 2 pi - 2 asin(w/2 / r)... = L_b - w_b
            sweep = (math.atan2(arc.end[1], arc.end[0]) - math.atan2(arc.start[1], arc.start[0])) % (2 * math.pi)
            self.assertAlmostEqual(sweep * dm.bore_radius + dm.bore_flat_width, loop_len, delta=0.02)

    def test_nut_slot_outline(self):
        rad = fasteners.NUT_CAVITY_RADIUS
        pts = sections.nut_slot_points(5.5)
        self.assertEqual(len(pts), 5)
        self.assertAlmostEqual(rad, 2.51, delta=0.001)
        h = rad * math.sqrt(3) / 2
        self.assertAlmostEqual(h, 2.1737, delta=0.001)  # the walls stand 2.1737 from the bolt line
        self.assertEqual(pts[0], (5.5, -h))
        self.assertEqual(pts[2], (-rad, 0.0))
        self.assertTrue(loop_is_closed(sections.nut_slot_loop(5.5)))
        self.assertEqual(sections.nut_slot_round_corners(), pts[1:4])
        # the corner C sits 2.51 behind the bolt line: r 6.99 for a bolt at 9.5
        self.assertAlmostEqual(9.5 - rad, 6.99, delta=0.001)

    def test_counterbore_meridian(self):
        for p, floor in ((dataclasses.replace(default_params(), rotor_diameter=128.0), 7.55),
                         (dataclasses.replace(params_608zz(), rotor_diameter=128.0), 8.8),
                         (default_params(), 11.55), (params_608zz(), 12.8)):
            dm = derive(p)
            pts = sections.counterbore_meridian(dm)
            self.assertEqual(len(pts), 1 + 9 + 2)
            self.assertEqual(pts[0], (0.0, 0.0))
            self.assertAlmostEqual(dm.counterbore_floor, floor)
            self.assertAlmostEqual(pts[1][0], 0.0)  # the round starts on the floor at radius 1.7
            self.assertAlmostEqual(pts[1][1], 1.7)
            self.assertAlmostEqual(pts[9][0], 0.5)  # and ends 0.5 up at the pocket's radius
            self.assertAlmostEqual(pts[9][1], 2.2)
            self.assertAlmostEqual(pts[-1][0], dm.size.hub_radius + 1 - floor)
            self.assertEqual(pts[-1][1], 0.0)
            # the head (radius 1.9) floats 0.4 above the floor, where the round is at radius 2.19
            self.assertAlmostEqual(pts[2][0], 0.5 - 0.5 * math.cos(math.pi / 16), delta=1e-9)
            loop = fasteners.meridian_loop(pts)
            self.assertTrue(loop_is_closed(loop))


if __name__ == "__main__":
    unittest.main()
