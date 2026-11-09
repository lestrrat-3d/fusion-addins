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
    groove_area,
    key_tool_area,
    key_tool_section,
)

P = default_params()
D = derive(P)


def polar(r, deg):
    a = math.radians(deg)
    return (r * math.cos(a), r * math.sin(a))


class SectionsTest(unittest.TestCase):
    def test_key_tool(self):
        loop = key_tool_section(P, D)
        assert not isinstance(loop, Circle)
        self.assertEqual(len(loop), 12)
        self.assertTrue(loop_is_closed(loop))
        area = polygon_area(loop_polygon(loop))
        self.assertLess(abs(area - 14.8561), 1e-3)
        self.assertLess(abs(key_tool_area(P, D) - 14.85606), 1e-4)
        self.assertLess(abs(groove_area(P, D) - 2.047119), 1e-6)

    def test_key_tool_round(self):
        p = dataclasses.replace(P, key_depth=0.0)
        sec = key_tool_section(p, derive(p))
        self.assertIsInstance(sec, Circle)
        self.assertLess(abs(key_tool_area(p, derive(p)) - math.pi * 6.25), 1e-9)

    def test_carrier_plate(self):
        loop = carrier_plate_outline(P, D)
        self.assertEqual(len(loop), 6)
        self.assertTrue(loop_is_closed(loop))
        poly = loop_polygon(loop)
        self.assertLess(abs(polygon_area(poly) - 1232.342), 1e-2)
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
            self.assertLess(abs(polygon_area(poly) - 1099.0225), 0.05)
            polys.append(poly)
        spoke = polar(28, 30)
        self.assertFalse(any(point_in_polygon(poly, spoke) for poly in polys))
        self.assertTrue(point_in_polygon(polys[0], polar(28, 90)))

    def test_window_reach(self):
        # Port of the gallery cover test: each window reaches the rim line.
        rim = D.ring_outer - P.ring_wall / 2 - (3.8 / 2 + 0.1) - 1.5
        loops = cover_window_loops(P, D)
        self.assertEqual(len(loops), 3)
        for loop in loops:
            reach = max(math.hypot(x, y) for x, y in loop_polygon(loop))
            self.assertLess(abs(reach - rim), 0.05)

    def test_bolt_holes(self):
        for x, y in bolt_hole_centers(D):
            r = math.hypot(x, y)
            self.assertLess(abs(r - 40.5), 1e-9)
            self.assertGreaterEqual(r - P.bolt_hole_diameter / 2, D.ring_root + BOLT_RIM_MARGIN)
            self.assertLessEqual(r + P.bolt_hole_diameter / 2, D.ring_outer - BOLT_RIM_MARGIN)

    def test_fastener_sites(self):
        sites = fastener_sites(D)
        self.assertEqual(len(sites), 4)
        for i, (x, y, a) in enumerate(sites):
            want = math.pi / 4 + i * math.pi / 2
            self.assertAlmostEqual(a, want, places=12)
            self.assertAlmostEqual(x, 40.5 * math.cos(want), places=12)
            self.assertAlmostEqual(y, 40.5 * math.sin(want), places=12)


if __name__ == "__main__":
    unittest.main()
