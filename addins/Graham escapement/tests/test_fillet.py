import math
import unittest

import _support  # noqa: F401
from gen import fillet
from gen.curves import Arc, Line, loop_is_closed, loop_polygon
from gen.polygon import polygon_area


def near(test, p, q, tol=1e-9):
    test.assertAlmostEqual(p[0], q[0], delta=tol)
    test.assertAlmostEqual(p[1], q[1], delta=tol)


class FilletTest(unittest.TestCase):
    def test_line_line(self):
        a, b = Line((0.0, 0.0), (5.0, 0.0)), Line((0.0, 0.0), (0.0, 5.0))
        ta, rnd, tb = fillet.round_corner(a, b, 1.0)
        near(self, rnd.center, (1.0, 1.0))
        near(self, ta.start, (1.0, 0.0))
        near(self, tb.start, (0.0, 1.0))
        near(self, rnd.start, (0.0, 1.0))
        near(self, rnd.end, (1.0, 0.0))
        self.assertIs(rnd.start, tb.start)
        self.assertIs(rnd.end, ta.start)
        self.assertEqual((ta.end, tb.end), (a.end, b.end))

    def test_line_arc(self):
        a = Line((10.0, 0.0), (20.0, 0.0))
        b = Arc((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))
        ta, rnd, tb = fillet.round_corner(a, b, 1.0)
        s = math.sqrt(120.0)
        near(self, rnd.center, (s, 1.0))
        near(self, ta.start, (s, 0.0))
        near(self, tb.start, (10 * s / 11, 10 / 11))
        self.assertEqual(tb.center, b.center)

    def test_arc_arc(self):
        a = Arc((0.0, 0.0), (4.0, -3.0), (4.0, 3.0))
        b = Arc((8.0, 0.0), (4.0, 3.0), (3.0, 0.0))
        ta, rnd, tb = fillet.round_corner(a, b, 0.5)
        h = math.sqrt(4.25)
        near(self, rnd.center, (4.0, h))
        near(self, ta.end, (4.0 * 5 / 4.5, h * 5 / 4.5))
        near(self, tb.start, (8.0 - 4.0 * 5 / 4.5, h * 5 / 4.5))

    def test_round_loop_square(self):
        sq = [Line((0.0, 0.0), (1.0, 0.0)), Line((1.0, 0.0), (1.0, 1.0)), Line((1.0, 1.0), (0.0, 1.0)),
              Line((0.0, 1.0), (0.0, 0.0))]
        loop = fillet.round_loop(sq, {0: 0.25, 1: 0.25, 2: 0.25, 3: 0.25})
        self.assertEqual(len(loop), 8)
        self.assertTrue(loop_is_closed(loop))
        area = abs(polygon_area(loop_polygon(loop, max_step=math.radians(0.05))))
        self.assertAlmostEqual(area, 1 - 4 * 0.0625 * (1 - math.pi / 4), delta=1e-6)
        recs = fillet.loop_rounds(sq, {3: 0.25, 1: 0.25})
        self.assertEqual([r.corner for r in recs], [(1.0, 1.0), (0.0, 0.0)])

    def test_errors(self):
        a, b = Line((0.0, 0.0), (5.0, 0.0)), Line((0.0, 0.0), (0.0, 5.0))
        with self.assertRaisesRegex(ValueError, "does not fit"):
            fillet.round_corner(a, b, 6.0)
        with self.assertRaisesRegex(ValueError, "share 2 ends"):
            fillet.round_corner(Line((0.0, 0.0), (1.0, 0.0)), Line((1.0, 0.0), (0.0, 0.0)), 0.1)
        with self.assertRaisesRegex(ValueError, "straight"):
            fillet.round_corner(Line((0.0, 0.0), (1.0, 0.0)), Line((0.0, 0.0), (-1.0, 0.0)), 0.1)
        with self.assertRaisesRegex(ValueError, "spline"):
            from gen.curves import Spline
            fillet.round_loop([Line((0.0, 0.0), (1.0, 0.0)), Spline(((1.0, 0.0), (2.0, 1.0), (0.0, 0.0)))], {})

    def test_probe(self):
        r = fillet.loop_rounds([Line((5.0, 0.0), (0.0, 0.0)), Line((0.0, 0.0), (0.0, 5.0)), Line((0.0, 5.0), (5.0, 0.0))],
                               {0: 1.0})[0]
        p = r.probe()
        d_corner = math.hypot(p[0] - r.corner[0], p[1] - r.corner[1])
        d_centre = math.hypot(p[0] - r.centre[0], p[1] - r.centre[1])
        self.assertLess(abs(d_corner - (d_centre - r.radius)), 1e-9)


if __name__ == "__main__":
    unittest.main()
