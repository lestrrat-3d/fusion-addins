import math
import unittest

import _support  # noqa: F401
from gen import fasteners as f
from gen.curves import Line, loop_is_closed


class FastenersTest(unittest.TestCase):
    def test_spans(self):
        self.assertEqual(f.hole_span(), (21.0, 35.0))
        self.assertEqual(f.pocket_tool_span(), (32.0, 35.0))
        self.assertEqual(f.cavity_span(), (24.0, 26.0))
        self.assertEqual(f.bolt_tip_z(), 22.0)
        lo, hi = f.nut_span()
        self.assertAlmostEqual(lo, 24.2, places=12)
        self.assertAlmostEqual(hi, 25.8, places=12)

    def test_sizes(self):
        self.assertAlmostEqual(f.HOLE_RADIUS, 1.3, places=12)
        self.assertAlmostEqual(f.HEAD_POCKET_RADIUS, 2.2, places=12)
        self.assertAlmostEqual(f.NUT_CAVITY_RADIUS, 4 / math.sqrt(3) + 0.2, places=12)
        self.assertAlmostEqual(f.NUT_CAVITY_HEIGHT, 2.0, places=12)
        self.assertEqual(f.PILLARS, ((-50.0, 74.0), (50.0, 74.0), (-50.0, -88.0), (50.0, -88.0)))

    def test_bolt_section_closed(self):
        loop = f.bolt_section(10.0)
        self.assertTrue(all(isinstance(c, Line) for c in loop))
        self.assertTrue(loop_is_closed(loop))
        self.assertEqual(loop[0].start, (0.0, -10.0))

    def test_nut_and_hexagon(self):
        self.assertTrue(loop_is_closed(f.nut_chamfer_section(False)))
        self.assertTrue(loop_is_closed(f.nut_chamfer_section(True)))
        self.assertAlmostEqual(f.nut_across_corners(), 4.618802153517006, places=12)
        self.assertTrue(loop_is_closed(f.hexagon_loop(4.0)))


if __name__ == "__main__":
    unittest.main()
