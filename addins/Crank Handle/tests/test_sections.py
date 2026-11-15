import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import sections
from gen.constants import ARM_RADIUS
from gen.curves import Arc, Line, loop_is_closed, loop_polygon, polygon_area
from gen.params import default_params, params_6082rs
from gen.validate import derive

CASES = {
    "605zz": default_params(),
    "608-2rs": params_6082rs(),
    "regular-bore": dataclasses.replace(default_params(), bore_clearance=0.35),
    "long-throw": dataclasses.replace(params_6082rs(), throw=80.0),
    "wide": dataclasses.replace(default_params(), shaft_diameter=16.0, flat_depth=1.0),
}


def _bbox(loop):
    pts = loop_polygon(loop, max_step=math.radians(0.05))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


class ArmOutlineTest(unittest.TestCase):
    def test_closed_counterclockwise_and_tangent(self):
        for name, p in CASES.items():
            with self.subTest(case=name):
                dm = derive(p)
                loop = sections.arm_outline(p, dm)
                self.assertTrue(loop_is_closed(loop))
                self.assertEqual(len(loop), 6)
                self.assertGreater(polygon_area(loop_polygon(loop)), 0)
                # Every arc's end points lie on its own radius: Fusion builds an arc from center and start.
                for c in loop:
                    if isinstance(c, Arc):
                        r0 = math.dist(c.center, c.start)
                        self.assertAlmostEqual(math.dist(c.center, c.end), r0, places=9)

    def test_bounds_follow_the_end_arc_and_the_pin(self):
        for name, p in CASES.items():
            with self.subTest(case=name):
                dm = derive(p)
                x0, y0, x1, y1 = _bbox(sections.arm_outline(p, dm))
                self.assertAlmostEqual(x0, -ARM_RADIUS, places=9)
                self.assertAlmostEqual(x1, ARM_RADIUS, places=9)
                self.assertAlmostEqual(y0, -dm.reach, delta=1e-3)
                self.assertAlmostEqual(y1, p.throw + ARM_RADIUS, delta=1e-3)

    def test_area_against_the_gallery_model(self):
        # Gallery arm at throw 55, 605ZZ: the outline's area is the straight part plus the end.
        p = default_params()
        area = polygon_area(loop_polygon(sections.arm_outline(p, derive(p)), max_step=math.radians(0.01)))
        longer = dataclasses.replace(p, throw=80.0)
        area_long = polygon_area(loop_polygon(sections.arm_outline(longer, derive(longer)), max_step=math.radians(0.01)))
        self.assertAlmostEqual(area_long - area, 2 * ARM_RADIUS * 25.0, places=3)

    def test_reach_matches_the_gallery_bounds(self):
        # instructions.md: R_e 13.89 and 15.39. decad's meshed arm bounds read 13.881 and 15.381, inside its 0.9 mm^3
        # mesh bound.
        self.assertAlmostEqual(derive(default_params()).reach, 13.89, delta=0.01)
        self.assertAlmostEqual(derive(params_6082rs()).reach, 15.39, delta=0.01)


class ToolSectionsTest(unittest.TestCase):
    def test_slit_runs_from_past_the_end_arc_into_the_bore(self):
        for name, p in CASES.items():
            with self.subTest(case=name):
                dm = derive(p)
                loop = sections.slit_tool(dm)
                self.assertTrue(loop_is_closed(loop))
                x0, y0, x1, y1 = _bbox(loop)
                self.assertAlmostEqual(x1 - x0, 1.0, places=9)
                self.assertAlmostEqual(y0, -dm.reach - 2, places=9)
                self.assertAlmostEqual(y1, -dm.bore_radius + 1.0, places=6)

    def test_bore_is_the_long_way_round_with_a_flat(self):
        for name, p in CASES.items():
            with self.subTest(case=name):
                dm = derive(p)
                loop = sections.bore_tool(dm)
                self.assertTrue(loop_is_closed(loop))
                self.assertIsInstance(loop[0], Arc)
                self.assertIsInstance(loop[1], Line)
                x0, y0, x1, y1 = _bbox(loop)
                self.assertAlmostEqual(y0, -dm.bore_radius, places=6)
                self.assertAlmostEqual(y1, dm.bore_flat, places=9)
                self.assertAlmostEqual(x1, dm.bore_radius, places=6)
                # Round plus flat: the D section's area of instructions.md.
                rb, fb = dm.bore_radius, dm.bore_flat
                half = math.acos(fb / rb)
                want = rb * rb * (math.pi - half) + fb * math.sqrt(rb * rb - fb * fb)
                self.assertAlmostEqual(polygon_area(loop_polygon(loop, max_step=math.radians(0.01))), want, places=3)

    def test_flat_boxes_straddle_the_pin(self):
        a, b, z0, length = sections.flat_box(55.0, 17.0, 1.0)
        self.assertEqual((a[1], b[1]), (59.0, 62.0))
        self.assertEqual((z0, length), (13.75, 6.5))
        a, b, _, _ = sections.flat_box(55.0, 49.0, -1.0)
        self.assertEqual((a[1], b[1]), (48.0, 51.0))
        self.assertEqual((a[0], b[0]), (-6.15, 6.15))


class MeridianTest(unittest.TestCase):
    def test_pin_meridian(self):
        loop = sections.pin_meridian()
        self.assertTrue(loop_is_closed(loop))
        pts = [c.start for c in loop]
        self.assertEqual(pts[0], (0.0, 8.25))
        self.assertAlmostEqual(pts[2][1], 8.25 + 1.65 / math.tan(math.radians(30)), places=9)  # z 11.11
        self.assertEqual(pts[-1], (0.0, 58.0))
        r_max = max(p[0] for p in pts)
        self.assertEqual(r_max, 6.45)

    def test_handle_meridian(self):
        loop = sections.handle_meridian()
        self.assertTrue(loop_is_closed(loop))
        x0, y0, x1, y1 = _bbox(loop)
        # (radius, z): the handle runs from z 8.4 to 58.4 and is 9.3 at its widest.
        self.assertEqual((x0, x1), (5.55, 9.3))
        self.assertAlmostEqual(y0, 8.4, places=9)
        self.assertAlmostEqual(y1, 58.4, places=9)


if __name__ == "__main__":
    unittest.main()
