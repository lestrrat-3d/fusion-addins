import dataclasses
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

    def test_tool_frame_of_the_set_screw(self):
        # Corner +Z puts the nut's corners up and down and its flats on +-X; the screw runs along +Y.
        origin, x, y, z = self.dm.set_screw_site.axes()
        self.assertEqual((origin, x, z), ((0.0, -13.95, 4.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)))  # M2 x 10 at 192
        self.assertEqual(y, (1.0, 0.0, 0.0))

    def test_blade_bolt_frames(self):
        s = self.dm.blade_sites[0]
        origin, x, y, z = s.axes(s.cavity_far())
        # At 192 (M2 x 25, cavity 24.6): the slot's far face is z 30 - 26.6 = 3.4 below the head's top face.
        self.assertAlmostEqual(origin[2], 30.0 - 26.6)
        self.assertEqual(z, (0.0, 0.0, -1.0))
        self.assertAlmostEqual(x[1], 1.0)
        origin, x, y, z = s.nut_axes()
        self.assertAlmostEqual(origin[2], 30.0 - 24.6 - 0.2)  # the nut stands 0.2 inside the cavity's near face
        origin, x, y, z = s.bolt_axes()
        self.assertEqual((origin[2], z), (28.0, (0.0, 0.0, 1.0)))  # the head's underside, 2 below the face
        # At 128 (M2 x 16, cavity 15.6): the slot's far face is z 2.4.
        s = derive(dataclasses.replace(default_params(), rotor_diameter=128.0)).blade_sites[0]
        self.assertAlmostEqual(s.axes(s.cavity_far())[0][2], 20.0 - 17.6)

    def test_adapter_site_runs_into_the_hub(self):
        a = self.dm.adapter_sites[1]
        self.assertAlmostEqual(math.degrees(math.atan2(a.head[1], a.head[0])), 150.0)
        self.assertAlmostEqual(a.at(a.tip())[2], 5.75)  # the tip, inside the blind hole whose floor is z 6.75

    def test_invalid_sites(self):
        s = self.dm.set_screw_site
        for bad, text in (
            (dataclasses.replace(s, dir=(0.0, 2.0, 0.0)), "unit vectors"),
            (dataclasses.replace(s, corner=(0.0, 1.0, 0.0)), "perpendicular"),
            (dataclasses.replace(s, length=7.0), "standard M2 length"),
            (dataclasses.replace(s, cavity=1.0), "beyond the head pocket"),
        ):
            self.assertIn(text, bad.validate())
        self.assertEqual(s.validate(), "")


class ShapesTest(unittest.TestCase):
    def test_hexagon(self):
        loop = fasteners.hexagon_loop(4.0)
        self.assertEqual(len(loop), 6)
        self.assertTrue(loop_is_closed(loop))
        self.assertAlmostEqual(loop[0].start[0], 4.0 / math.sqrt(3))

    def test_nut_chamfer_sections_are_closed(self):
        for upper in (False, True):
            self.assertTrue(loop_is_closed(fasteners.nut_chamfer_section(upper)))

    def test_bolt_section(self):
        loop = fasteners.bolt_section(16.0)
        self.assertTrue(loop_is_closed(loop))
        self.assertEqual(min(c.start[1] for c in loop), -16.0)

    def test_bolt_volume_grows_with_length(self):
        dm = derive(default_params())
        self.assertGreater(expected._bolt_volume(16.0), expected._bolt_volume(10.0))


if __name__ == "__main__":
    unittest.main()
