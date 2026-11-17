import math
import unittest

import _support  # noqa: F401
from gen import expected, fasteners
from gen.curves import loop_is_closed
from gen.params import default_params
from gen.validate import derive


class SiteTest(unittest.TestCase):
    def setUp(self):
        self.dm = derive(default_params())

    def test_tool_frame_of_the_pin_bolt(self):
        origin, x, y, z = self.dm.site.axes()
        self.assertEqual((origin, x, y, z), ((0.0, 55.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))

    def test_tool_frame_of_the_clamp_bolt(self):
        # [m2fastener Site.Across] U = Corner, V = Dir x Corner, so the sketch extrudes along Dir.
        # The clamp nut's hexagon has a corner up and one down (gallery #275): Corner is +Z.
        site = self.dm.clamp_sites[1]
        origin, x, y, z = site.axes(site.cavity)
        self.assertEqual(x, (0.0, 0.0, 1.0))
        self.assertEqual(y, (0.0, 1.0, 0.0))
        self.assertEqual(z, (-1.0, 0.0, 0.0))
        self.assertAlmostEqual(origin[0], -6.0, places=12)  # the nut pocket's floor, 16 from the head
        self.assertAlmostEqual(origin[2], 12.0, places=12)  # the second clamp bolt

    def test_bolt_and_nut_frames(self):
        s = self.dm.cross_sites[0]
        origin, x, y, z = s.bolt_axes()
        self.assertEqual(origin, (0.0, 57.0, 17.0))  # the head's underside, 2 below the flat
        self.assertEqual(z, (0.0, 1.0, 0.0))  # the head looks back along -dir
        self.assertEqual(x, (1.0, 0.0, 0.0))  # the cross nuts' corners point across the pin (gallery #275)
        self.assertEqual(y, (0.0, 0.0, -1.0))
        origin, x, y, z = s.nut_axes()
        self.assertAlmostEqual(origin[1], 59.0 - 6.2, places=12)
        self.assertEqual(z, (0.0, -1.0, 0.0))

    def test_invalid_sites(self):
        s = self.dm.site
        self.assertIn("unit", fasteners.Site(s.head, (0.0, 0.0, 2.0), s.corner, 10.0, 4.75).validate())
        self.assertIn("perpendicular", fasteners.Site(s.head, s.dir, s.dir, 10.0, 4.75).validate())
        self.assertIn("standard", fasteners.Site(s.head, s.dir, s.corner, 11.0, 4.75).validate())
        self.assertIn("Cavity", fasteners.Site(s.head, s.dir, s.corner, 10.0, 2.0).validate())


class ShapeTest(unittest.TestCase):
    def test_nut_cavity_hexagon(self):
        loop = fasteners.hexagon_by_radius(fasteners.NUT_CAVITY_RADIUS)
        self.assertTrue(loop_is_closed(loop))
        self.assertAlmostEqual(loop[0].start[0], 4.0 / math.sqrt(3) + 0.2, places=12)
        self.assertEqual(loop[0].start[1], 0.0)
        # Flats at 2.17 from the axis: 0.17 clear of the nut's flats at 2.0.
        flat = fasteners.NUT_CAVITY_RADIUS * math.sqrt(3) / 2
        self.assertAlmostEqual(flat, 2.1735, places=3)

    def test_hexagon_by_flats(self):
        loop = fasteners.hexagon_loop(7.03, (0.0, 55.0))
        self.assertAlmostEqual(loop[0].start[0], 7.03 / math.sqrt(3), places=12)
        self.assertAlmostEqual(loop[0].start[1], 55.0, places=12)

    def test_rounded_hole_meridian(self):
        pts = fasteners.rounded_hole_meridian(derive(default_params()).site)
        self.assertEqual(pts[0], (-1.0, 0.0))
        self.assertEqual(pts[1], (-1.0, 1.3))
        self.assertEqual(len(pts), 2 + 9 + 1)
        self.assertEqual(pts[-1], (13.0, 0.0))  # tip at 12 plus the tool's 1 mm of stock
        self.assertTrue(loop_is_closed(fasteners.meridian_loop(pts)))
        # (radius, t) after the swap: the loop's first point is on the axis.
        self.assertEqual(fasteners.meridian_loop(pts)[0].start, (0.0, -1.0))

    def test_rounded_cavity_meridian(self):
        site = derive(default_params()).site
        pts = fasteners.rounded_cavity_meridian(site)
        self.assertEqual(pts[0], (4.75, 0.0))
        self.assertEqual(pts[-1], (6.75, 0.0))
        self.assertEqual(len(pts), 1 + 9 + 9 + 1)
        self.assertAlmostEqual(max(r for _, r in pts), fasteners.NUT_CAVITY_RADIUS, places=12)
        self.assertTrue(loop_is_closed(fasteners.meridian_loop(pts)))

    def test_bolt_and_nut_sections_are_closed(self):
        self.assertTrue(loop_is_closed(fasteners.bolt_section(10.0)))
        self.assertTrue(loop_is_closed(fasteners.nut_chamfer_section(False)))
        self.assertTrue(loop_is_closed(fasteners.nut_chamfer_section(True)))


class VolumeTest(unittest.TestCase):
    """The ported volume formulas against the gallery model's own bolts and nut (decad volumes)."""

    def test_bolts(self):
        for length, want in ((6.0, 38.9114), (10.0, 51.4751), (18.0, 76.6004)):
            with self.subTest(length=length):
                self.assertAlmostEqual(expected._bolt_volume(length), want, delta=0.002 * want + 0.01)

    def test_nut(self):
        self.assertAlmostEqual(expected._nut_volume(), 16.1489, delta=0.05)


if __name__ == "__main__":
    unittest.main()
