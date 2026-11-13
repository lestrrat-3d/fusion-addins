import math
import unittest

import _support  # noqa: F401
from gen.curves import Arc, loop_is_closed
from gen.involute import (
    closing_radius,
    external_gear_dims,
    flank_beta,
    flank_points_at,
    gear_outline_polygon,
    is_embedded,
    ring_tool_dims,
    root_contacts,
    spur_dims,
    tooth_section,
    validate_spur,
)
from gen.polygon import polygon_area

A = 20 * math.pi / 180
J = 0.05


def arc_ends_equidistant(test, loop):
    for c in loop:
        if isinstance(c, Arc):
            r0 = math.hypot(c.start[0] - c.center[0], c.start[1] - c.center[1])
            r1 = math.hypot(c.end[0] - c.center[0], c.end[1] - c.center[1])
            test.assertLess(abs(r0 - r1), 1e-12)


class InvoluteTest(unittest.TestCase):
    def test_reference_gears(self):
        # (gear, base, root, tip, fillet, beta)
        rows = [
            (spur_dims(1, 13, A, J), 6.108002, 5.25, 7.5, 0.500501, 0.131888717),
            (spur_dims(1, 29, A, J), 13.625543, 13.25, 15.5, 0.468188, 0.067345637),
            (external_gear_dims(1, 13, A, J, 0.5, 0.0, 0.02), 6.108002, 5.0, 7.48, 0.476667, 0.131888717),
            (external_gear_dims(1, 29, A, J, 0.5, 0.02, 0.02), 13.625543, 12.98, 15.48, 0.458647, 0.067345637),
            (ring_tool_dims(1, 71, A, -J, 0.5), 33.359088, 34.5, 37.0, 0.0, 0.037732501),
        ]
        for gd, base, root, tip, fillet, beta in rows:
            with self.subTest(teeth=gd.teeth):
                self.assertLess(abs(gd.base - base), 1e-6)
                self.assertLess(abs(gd.root - root), 1e-6)
                self.assertLess(abs(gd.tip - tip), 1e-6)
                self.assertLess(abs(gd.fillet - fillet), 1e-6)
                self.assertLess(abs(flank_beta(gd) - beta), 1e-6)

    def test_flank_at_pitch(self):
        for j in (0.0, 0.2):
            gd = spur_dims(1, 17, A, j)
            left, right = flank_points_at(gd, gd.pitch)
            want = math.pi / (2 * 17) - j / (2 * gd.pitch)
            self.assertLess(abs(math.atan2(left[1], left[0]) - want), 1e-12)
            self.assertLess(abs(math.atan2(right[1], right[0]) + want), 1e-12)

    def test_sections(self):
        for teeth in (13, 29):
            with self.subTest(teeth=teeth):
                gd = spur_dims(1, teeth, A, J)
                self.assertFalse(is_embedded(gd))
                loop = tooth_section(gd, 15)
                self.assertEqual(len(loop), 6)
                self.assertTrue(loop_is_closed(loop))
                arc_ends_equidistant(self, loop)

    def test_ring_tool_embedded(self):
        gd = ring_tool_dims(1, 71, A, -J, 0.5)
        self.assertTrue(is_embedded(gd))
        self.assertLess(abs(closing_radius(gd) - gd.base), 1e-9)
        loop = tooth_section(gd, 15)
        self.assertEqual(len(loop), 4)
        self.assertTrue(loop_is_closed(loop))
        arc_ends_equidistant(self, loop)
        with self.assertRaises(ValueError):
            root_contacts(gd, 15)

    def test_root_contacts(self):
        gd = spur_dims(1, 13, A, J)
        pts = root_contacts(gd, 15)
        self.assertEqual(len(pts), 26)
        for x, y in pts:
            self.assertLess(abs(math.hypot(x, y) - gd.root), 1e-12)

    def test_outline_areas(self):
        for gd, want in (
            (spur_dims(1, 13, A, J), 125.922),
            (spur_dims(1, 29, A, J), 647.869),
            (ring_tool_dims(1, 71, A, -J, 0.5), 3986.826),
            (spur_dims(1, 13, A, 0.2), 121.618),
            (external_gear_dims(1, 13, A, J, 0.5, 0.0, 0.02), 122.117),
            (external_gear_dims(1, 29, A, J, 0.5, 0.02, 0.02), 639.052),
            (external_gear_dims(1, 13, A, 0.2, 0.5, 0.0, 0.02), 117.474),
        ):
            with self.subTest(teeth=gd.teeth, backlash=gd.backlash):
                area = polygon_area(gear_outline_polygon(gd, 60))
                self.assertLess(abs(area - want), 0.05, f"area {area}")
        a05 = polygon_area(gear_outline_polygon(spur_dims(1, 13, A, J), 60))
        a20 = polygon_area(gear_outline_polygon(spur_dims(1, 13, A, 0.2), 60))
        self.assertGreater(a05 - a20, 1)

    def test_outline_center_and_angle(self):
        gd = spur_dims(1, 13, A, J)
        base = polygon_area(gear_outline_polygon(gd, 20))
        moved = polygon_area(gear_outline_polygon(gd, 20, angle=0.3, center=(5.0, -2.0)))
        self.assertLess(abs(base - moved), 1e-9)

    def test_validate_spur_messages(self):
        cases = (
            ((0, 13, A, 8, 15, 0.0, J), "spurgear: module 0 must be positive"),
            ((1, 2, A, 8, 15, 0.0, J), "spurgear: teeth 2 must be at least 3"),
            ((1, 13, A, 8, 15, 0.0, 0.6), "spurgear: backlash 0.6 exceeds half the module 1"),
            ((1, 13, A, 8, 15, 0.0, float("nan")), "spurgear: backlash NaN is not finite"),
            (
                (1, 13, math.pi / 2, 8, 15, 0.0, J),
                "spurgear: pressure angle 1.5707963267948966 must lie in (0, pi/2)",
            ),
            (
                (1, 13, A, 8, 15, 10.5, J),
                "spurgear: bore diameter 10.5 must be below the root diameter 10.5",
            ),
            ((1, 13, A, 8, 15, 0.0, J), None),
        )
        for args, want in cases:
            with self.subTest(args=args):
                self.assertEqual(validate_spur(*args), want)

    def test_closing_radius_error(self):
        gd = ring_tool_dims(1, 71, math.radians(40), -J, 0.5)
        with self.assertRaises(ValueError) as cm:
            closing_radius(gd)
        self.assertEqual(str(cm.exception), "spurgear: adjacent teeth overlap at the root circle (radius 34.5)")


if __name__ == "__main__":
    unittest.main()
