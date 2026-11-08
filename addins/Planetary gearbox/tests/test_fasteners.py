import math
import unittest

import _support  # noqa: F401
from planetarygearboxgen.curves import Line, loop_is_closed, loop_polygon
from planetarygearboxgen.fasteners import (
    MIN_BOLT_HOLE_DIAMETER,
    bolt_section,
    head_pocket_diameter,
    hexagon_loop,
    nut_across_corners,
    nut_angle,
    nut_cavity_height,
    nut_chamfer_section,
    nut_pocket_flats,
)
from planetarygearboxgen.polygon import polygon_area

BOLT_VERTICES = [
    (0.0, -6.0),
    (0.75, -6.0),
    (1.0, -5.75),
    (1.0, 0.0),
    (1.9, 0.0),
    (1.9, 1.8845299461620748),
    (1.7, 2.0),
    (0.7, 2.0),
    (0.7, 0.9),
    (0.0, 0.4793975666807078),
]
LOWER = [(1.2203847577293367, -0.3), (2.509401076758503, -0.3), (2.509401076758503, 0.44421391878130967)]
UPPER = [(1.2203847577293367, 1.9), (2.509401076758503, 1.9), (2.509401076758503, 1.1557860812186904)]


class FastenersTest(unittest.TestCase):
    def near_pts(self, loop, want):
        self.assertEqual(len(loop), len(want))
        self.assertTrue(all(isinstance(c, Line) for c in loop))
        self.assertTrue(loop_is_closed(loop))
        for c, (u, v) in zip(loop, want):
            self.assertAlmostEqual(c.start[0], u, places=12)
            self.assertAlmostEqual(c.start[1], v, places=12)

    def test_min_bolt_hole(self):
        self.assertEqual(MIN_BOLT_HOLE_DIAMETER, 2.4)

    def test_sizes(self):
        self.assertAlmostEqual(head_pocket_diameter(), 4.0, places=12)
        self.assertAlmostEqual(nut_pocket_flats(), 4.2, places=12)
        self.assertAlmostEqual(nut_cavity_height(), 1.8, places=12)
        self.assertAlmostEqual(nut_across_corners(), 4.618802153517006, places=12)

    def test_nut_angle(self):
        self.assertEqual(nut_angle(math.pi / 4), -math.pi / 4)

    def test_hexagon(self):
        loop = hexagon_loop(4.2)
        self.assertEqual(len(loop), 6)
        self.assertTrue(all(isinstance(c, Line) for c in loop))
        self.assertTrue(loop_is_closed(loop))
        self.assertAlmostEqual(loop[0].start[0], 2.4248711305964283, places=12)
        self.assertEqual(loop[0].start[1], 0.0)
        self.assertAlmostEqual(polygon_area(loop_polygon(loop)), 15.276688122757497, delta=1e-9)
        moved = hexagon_loop(4.2, (1.0, 2.0), math.pi / 2)
        self.assertAlmostEqual(moved[0].start[0], 1.0, places=9)
        self.assertAlmostEqual(moved[0].start[1], 4.4248711305964283, places=9)

    def test_bolt_section(self):
        self.near_pts(bolt_section(6.0), BOLT_VERTICES)

    def test_nut_chamfer_sections(self):
        self.near_pts(nut_chamfer_section(False), LOWER)
        self.near_pts(nut_chamfer_section(True), UPPER)


if __name__ == "__main__":
    unittest.main()
