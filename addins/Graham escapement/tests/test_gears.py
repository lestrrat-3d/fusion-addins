import unittest

import _support  # noqa: F401
from gen import gears
from gen.involute import is_embedded
from gen.params import default_params


class GearsTest(unittest.TestCase):
    def test_radii(self):
        p = default_params()
        pin, great = gears.pinion_dims(p), gears.great_dims(p)
        self.assertAlmostEqual(pin.root, 7.73, places=9)
        self.assertAlmostEqual(pin.tip, 11.23, places=9)
        self.assertAlmostEqual(great.root, 33.98, places=9)
        self.assertAlmostEqual(great.tip, 37.48, places=9)

    def test_tip_to_root(self):
        p = default_params()
        pin, great = gears.pinion_dims(p), gears.great_dims(p)
        centre = pin.pitch + great.pitch
        self.assertAlmostEqual(centre - pin.tip - great.root, 0.54, places=9)
        self.assertAlmostEqual(centre - great.tip - pin.root, 0.54, places=9)

    def test_ordinary_and_embedded(self):
        p = default_params()
        pin, great = gears.pinion_dims(p), gears.great_dims(p)
        self.assertFalse(is_embedded(pin))
        self.assertAlmostEqual(pin.base, 9.162, places=3)
        self.assertTrue(is_embedded(great))
        self.assertAlmostEqual(great.base, 33.829, places=3)
        self.assertEqual(gears.SAMPLES, 15)
        self.assertEqual(gears.ROOT_CLEARANCE, 0.5)


if __name__ == "__main__":
    unittest.main()
