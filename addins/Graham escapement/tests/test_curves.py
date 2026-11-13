import math
import unittest

import _support  # noqa: F401
from gen.curves import Arc, Line, loop_is_closed, loop_polygon, rotate
from gen.polygon import count_inside, distance_to_polygon, point_in_polygon, polygon_area

SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


class CurvesTest(unittest.TestCase):
    def test_square_area(self):
        self.assertAlmostEqual(polygon_area(SQUARE), 1.0)
        self.assertAlmostEqual(polygon_area(SQUARE[::-1]), -1.0)

    def test_point_in_polygon(self):
        self.assertTrue(point_in_polygon(SQUARE, (0.5, 0.5)))
        self.assertFalse(point_in_polygon(SQUARE, (1.5, 0.5)))

    def test_distance(self):
        self.assertAlmostEqual(distance_to_polygon(SQUARE, (0.5, 0.5)), 0.5)
        self.assertAlmostEqual(distance_to_polygon(SQUARE, (2.0, 0.5)), 1.0)

    def test_half_disc(self):
        loop = [Line((-1.0, 0.0), (1.0, 0.0)), Arc((0.0, 0.0), (1.0, 0.0), (-1.0, 0.0))]
        self.assertTrue(loop_is_closed(loop))
        self.assertLess(abs(polygon_area(loop_polygon(loop)) - math.pi / 2), 1e-4)

    def test_half_disc_reversed_arc_order(self):
        # The same disc with the curves listed in the other order walks the same polygon area.
        loop = [Arc((0.0, 0.0), (1.0, 0.0), (-1.0, 0.0)), Line((-1.0, 0.0), (1.0, 0.0))]
        self.assertLess(abs(abs(polygon_area(loop_polygon(loop))) - math.pi / 2), 1e-4)

    def test_open_loop(self):
        loop = [Line((0.0, 0.0), (1.0, 0.0)), Line((1.0, 0.0), (1.0, 1.0)), Line((0.5, 0.5), (0.0, 0.0))]
        self.assertFalse(loop_is_closed(loop))
        self.assertFalse(loop_is_closed([Line((0.0, 0.0), (1.0, 0.0))]))

    def test_count_inside(self):
        pts = [(0.5, 0.5), (0.99, 0.5), (2.0, 2.0), (3.0, 3.0)]
        self.assertEqual(count_inside(pts, SQUARE, 0.02), 1)
        self.assertEqual(count_inside(pts, SQUARE, 0.02, material_inside=False), 2)

    def test_rotate(self):
        x, y = rotate((1.0, 0.0), math.pi / 2)
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 1.0)


if __name__ == "__main__":
    unittest.main()
