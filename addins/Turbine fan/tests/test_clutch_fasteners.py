import math
import unittest

import _support  # noqa: F401
from gen import fasteners
from gen.clutch import expected
from gen.curves import loop_is_closed
from gen.clutch.params import Params
from gen.clutch.validate import derive


class SiteTest(unittest.TestCase):
    def setUp(self):
        self.dm = derive(Params())

    def test_bolt_site_frames(self):
        s = self.dm.sites[0]  # at 30 degrees; its nut pocket's corner is at 60 degrees
        origin, x, y, z = s.axes(s.cavity)
        self.assertAlmostEqual(origin[2], 2.0)  # the cavity's near face, 0 to 2.0 below it
        self.assertEqual(z, (0.0, 0.0, -1.0))
        self.assertAlmostEqual(math.degrees(math.atan2(x[1], x[0])), 60.0)
        # Right-handed: x cross y = z.
        self.assertEqual(tuple(round(v, 9) for v in fasteners.cross(x, y)), (0.0, 0.0, -1.0))

    def test_bolt_and_nut_frames(self):
        s = self.dm.sites[2]  # at 270 degrees
        origin, x, y, z = s.bolt_axes()
        self.assertAlmostEqual(origin[2], 16.5)  # the head's underside, 2 below the cover's face
        self.assertEqual(z, (0.0, 0.0, 1.0))
        origin, x, y, z = s.nut_axes()
        self.assertAlmostEqual(origin[2], 1.8)  # 0.2 inside the cavity's near face at z 2.0
        self.assertEqual(z, (0.0, 0.0, -1.0))

    def test_tip_lands_in_the_back_plate(self):
        s = self.dm.sites[0]
        self.assertAlmostEqual(s.at(s.tip())[2], 0.5)  # seams open; flush (0.0) when the bolts are tightened

    def test_invalid_sites(self):
        s = self.dm.sites[0]
        import dataclasses

        self.assertIn("standard", dataclasses.replace(s, length=17.0).validate())
        self.assertIn("unit", dataclasses.replace(s, dir=(0.0, 0.0, 2.0)).validate())
        self.assertIn("perpendicular", dataclasses.replace(s, corner=(0.0, 0.0, 1.0)).validate())
        self.assertIn("Cavity", dataclasses.replace(s, cavity=1.0).validate())


class ShapesTest(unittest.TestCase):
    def test_hexagon_corners_on_the_circle(self):
        loop = fasteners.hexagon_by_radius(fasteners.NUT_CAVITY_RADIUS)
        self.assertTrue(loop_is_closed(loop))
        self.assertEqual(len(loop), 6)
        self.assertAlmostEqual(math.hypot(*loop[0].start), fasteners.NUT_CAVITY_RADIUS)
        self.assertEqual(loop[0].start[1], 0.0)  # the first corner is on the site's corner direction
        self.assertAlmostEqual(fasteners.NUT_CAVITY_RADIUS, 2.5094, places=3)  # the gallery's 2.51

    def test_sections_are_closed(self):
        self.assertTrue(loop_is_closed(fasteners.bolt_section(16.0)))
        self.assertTrue(loop_is_closed(fasteners.nut_chamfer_section(False)))
        self.assertTrue(loop_is_closed(fasteners.nut_chamfer_section(True)))

    def test_bolt_and_nut_volumes(self):
        self.assertAlmostEqual(expected._bolt_volume(16.0), 70.3, delta=0.5)
        self.assertAlmostEqual(expected._nut_volume(), 16.15, delta=0.5)


if __name__ == "__main__":
    unittest.main()
