import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen.curves import Circle, loop_is_closed, loop_polygon
from gen.dims import derive
from gen.params import BOLT_RIM_MARGIN, default_params
from gen.polygon import point_in_polygon, polygon_area
from gen.sections import (
    bolt_hole_centers,
    carrier_plate_outline,
    cover_window_loops,
    fastener_sites,
    flat_area,
    flat_box,
    flat_tool_area,
    flat_tool_section,
)

P = default_params()
D = derive(P)


def polar(r, deg):
    a = math.radians(deg)
    return (r * math.cos(a), r * math.sin(a))


class SectionsTest(unittest.TestCase):
    def test_flat_tool(self):
        loop = flat_tool_section(P, D)
        assert not isinstance(loop, Circle)
        # An arc about the origin and the line across the flat, which sits at x = 2.55 - 0.5 = 2.05.
        self.assertEqual(len(loop), 2)
        self.assertTrue(loop_is_closed(loop))
        self.assertEqual(loop[0].start, (2.05, 1.51657508881031))
        self.assertEqual(loop[0].end, (2.05, -1.51657508881031))
        area = polygon_area(loop_polygon(loop))
        self.assertLess(abs(area - 19.39551), 1e-3)
        # pi 2.55^2 less the circle segment beyond x = 2.05: 6.5025 acos(2.05/2.55) - 2.05 * sqrt(2.3).
        self.assertLess(abs(flat_tool_area(P, D) - 19.395506), 1e-6)
        # The shaft's own segment beyond x = 2 on its 2.5 radius.
        self.assertLess(abs(flat_area(P, D) - 1.021882), 1e-6)
        self.assertEqual(flat_box(P, D), ((2.0, -3.5), (3.5, 3.5)))

    def test_flat_tool_round(self):
        p = dataclasses.replace(P, flat_depth=0.0)
        sec = flat_tool_section(p, derive(p))
        self.assertIsInstance(sec, Circle)
        self.assertLess(abs(flat_tool_area(p, derive(p)) - math.pi * 2.55 ** 2), 1e-9)

    def test_carrier_plate(self):
        loop = carrier_plate_outline(P, D)
        self.assertEqual(len(loop), 6)
        self.assertTrue(loop_is_closed(loop))
        poly = loop_polygon(loop)
        self.assertLess(abs(polygon_area(poly) - 1268.065), 1e-2)
        self.assertTrue(point_in_polygon(poly, polar(12, 60)))
        self.assertTrue(point_in_polygon(poly, polar(15, 60)))
        self.assertFalse(point_in_polygon(poly, polar(20, 60)))
        self.assertTrue(point_in_polygon(poly, (21.0, 0.0)))

    def test_cover_windows(self):
        loops = cover_window_loops(P, D)
        self.assertEqual(len(loops), 3)
        polys = []
        for loop in loops:
            self.assertEqual(len(loop), 4)
            self.assertTrue(loop_is_closed(loop))
            poly = loop_polygon(loop)
            self.assertLess(abs(polygon_area(poly) - 1076.339), 0.05)
            polys.append(poly)
        spoke = polar(28, 30)
        self.assertFalse(any(point_in_polygon(poly, spoke) for poly in polys))
        self.assertTrue(point_in_polygon(polys[0], polar(28, 90)))

    def test_window_reach(self):
        # Port of the gallery cover test: each window reaches the rim line.
        rim = D.ring_outer - P.ring_wall / 2 - (3.8 / 2 + 0.3) - 1.5
        loops = cover_window_loops(P, D)
        self.assertEqual(len(loops), 3)
        for loop in loops:
            reach = max(math.hypot(x, y) for x, y in loop_polygon(loop))
            self.assertLess(abs(reach - rim), 0.05)

    def test_bolt_holes(self):
        for x, y in bolt_hole_centers(D):
            r = math.hypot(x, y)
            self.assertLess(abs(r - 40.55), 1e-9)
            self.assertGreaterEqual(r - P.bolt_hole_diameter / 2, D.ring_root + BOLT_RIM_MARGIN)
            self.assertLessEqual(r + P.bolt_hole_diameter / 2, D.ring_outer - BOLT_RIM_MARGIN)

    def test_fastener_sites(self):
        sites = fastener_sites(D)
        self.assertEqual(len(sites), 4)
        for i, (x, y, a) in enumerate(sites):
            want = math.pi / 4 + i * math.pi / 2
            self.assertAlmostEqual(a, want, places=12)
            self.assertAlmostEqual(x, 40.55 * math.cos(want), places=12)
            self.assertAlmostEqual(y, 40.55 * math.sin(want), places=12)


if __name__ == "__main__":
    unittest.main()
