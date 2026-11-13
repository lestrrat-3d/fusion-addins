import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen.curves import Arc, Circle, Line, loop_is_closed, loop_polygon
from gen.edgefinish import LONG_EDGE_RUN
from gen.polygon import polygon_area
from gen.spring import derive, fillet_corners, loop_length, profile, spring_params


class SpringTest(unittest.TestCase):
    def setUp(self):
        self.sp = spring_params()
        self.dm = derive(self.sp)

    def test_derive_values(self):
        dm = self.dm
        self.assertEqual(dm.turns, 9)
        self.assertAlmostEqual(dm.pitch, 2.6, places=9)
        self.assertAlmostEqual(dm.gap, 1.1, places=9)
        self.assertAlmostEqual(dm.first_inner_radius, 8.4, places=9)
        self.assertAlmostEqual(dm.active_length, 1142.3, delta=0.05)
        self.assertAlmostEqual(dm.eye_center_x, -31.25, places=3)
        self.assertAlmostEqual(dm.eye_center_y, -13.399, places=3)
        self.assertAlmostEqual(dm.eye_radius, 3.4, places=9)
        self.assertAlmostEqual(dm.eye_hole_diameter, 3.8, places=9)
        self.assertAlmostEqual(dm.bore_radius, 3.35, places=9)
        self.assertAlmostEqual(dm.bore_flat_distance, 2.85, places=9)
        self.assertAlmostEqual(dm.fillet_radius, 0.275, places=9)
        self.assertAlmostEqual(dm.center_offset, 1.3, places=9)

    def test_validation_errors(self):
        bad = dataclasses.replace(self.sp, thickness=1.0)
        with self.assertRaisesRegex(ValueError, "^spiralspring: Thickness must be at least 1.5 mm$"):
            derive(bad)
        bad = dataclasses.replace(self.sp, outer_diameter=14.0)
        with self.assertRaisesRegex(ValueError, "OuterDiameter leaves no room for one turn"):
            derive(bad)
        bad = dataclasses.replace(self.sp, turns=20)
        with self.assertRaisesRegex(ValueError, "Turns 20 needs a gap below MinGap; at most 9 turns fit"):
            derive(bad)

    def test_corners(self):
        c = fillet_corners(self.sp, self.dm)
        self.assertEqual(len(c), 5)
        self.assertEqual(c[0], (-6.0, 0.0))
        self.assertAlmostEqual(c[2][1], -3.0)

    def test_loops_closed(self):
        outer, bore, eye = profile(self.sp, self.dm)
        self.assertTrue(loop_is_closed(outer))
        self.assertTrue(loop_is_closed(bore))
        self.assertIsInstance(eye, Circle)
        # hub arc, root end, 18 outer arcs, tail, eye arc, tail, 18 inner arcs, spoke.
        self.assertEqual(len(outer), 1 + 1 + 18 + 1 + 1 + 1 + 18 + 1)
        arcs = [c for c in outer if isinstance(c, Arc)]
        self.assertEqual(len(arcs), 1 + 18 + 1 + 18)
        self.assertEqual(len([c for c in outer if isinstance(c, Line)]), 4)

    def test_arc_radii_consistent(self):
        outer, bore, _ = profile(self.sp, self.dm)
        for c in list(outer) + list(bore):
            if isinstance(c, Arc):
                r0 = math.hypot(c.start[0] - c.center[0], c.start[1] - c.center[1])
                r1 = math.hypot(c.end[0] - c.center[0], c.end[1] - c.center[1])
                self.assertAlmostEqual(r0, r1, places=9)

    def test_cap_loop_lengths(self):
        outer, bore, eye = profile(self.sp, self.dm)
        self.assertAlmostEqual(loop_length(bore), 20.862, delta=0.005)
        self.assertAlmostEqual(loop_length(eye), 11.938, delta=0.005)
        self.assertGreaterEqual(loop_length(bore), LONG_EDGE_RUN)
        self.assertLess(loop_length(eye), LONG_EDGE_RUN)
        self.assertGreater(loop_length(outer), LONG_EDGE_RUN)

    def test_profile_area(self):
        outer, bore, eye = profile(self.sp, self.dm)
        a_outer = polygon_area(loop_polygon(outer, max_step=math.radians(0.1)))
        a_bore = polygon_area(loop_polygon(bore, max_step=math.radians(0.1)))
        self.assertGreater(abs(a_outer), 0)
        self.assertGreater(abs(a_outer) - abs(a_bore) - math.pi * 1.9**2, 0)


if __name__ == "__main__":
    unittest.main()
