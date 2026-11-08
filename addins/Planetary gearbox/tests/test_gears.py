import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import gears
from gen.involute import external_gear_dims, ring_tool_dims
from gen.params import default_params, gear_root_clearance

A = 20 * math.pi / 180
J = 0.15
FIELDS = ("module", "teeth", "pitch", "base", "root", "tip", "fillet", "backlash")


class GearsTest(unittest.TestCase):
    def assert_same(self, got, want):
        for f in FIELDS:
            self.assertEqual(getattr(got, f), getattr(want, f), f)

    def test_default_gears(self):
        p = default_params()
        self.assert_same(gears.sun_gear(p), external_gear_dims(1, 13, A, J, 0.5, 0.0, 0.02))
        self.assert_same(gears.planet_gear(p), external_gear_dims(1, 29, A, J, 0.5, 0.02, 0.02))
        self.assert_same(gears.ring_tool(p), ring_tool_dims(1, 71, A, -J, 0.5))

    def test_tip_root_clearance(self):
        # Port of gallery TestGearTipRootClearance (radii only). The ring tool's tip is the ring's root circle and
        # its root is the ring's tip circle.
        for m in (0.5, 1, 2, 4):
            with self.subTest(module=m):
                p = dataclasses.replace(default_params(), module=m)
                c = gear_root_clearance(m)
                sun, planet, ring = gears.sun_gear(p), gears.planet_gear(p), gears.ring_tool(p)
                orbit = m * 42 / 2
                self.assertGreaterEqual(orbit - sun.root - planet.tip, c - 1e-12)
                self.assertGreaterEqual(orbit - planet.root - sun.tip, c - 1e-12)
                self.assertGreaterEqual(ring.tip - orbit - planet.tip, c - 1e-12)
                self.assertGreaterEqual(ring.root - orbit - planet.root, c - 1e-12)
                self.assertGreaterEqual(2 * orbit * math.sin(math.pi / 3) - 2 * planet.tip, 0.5 - 1e-12)

    def test_default_margins(self):
        p = default_params()
        sun, planet, ring = gears.sun_gear(p), gears.planet_gear(p), gears.ring_tool(p)
        self.assertAlmostEqual(21 - sun.root - planet.tip, 0.52, places=9)
        self.assertAlmostEqual(21 - planet.root - sun.tip, 0.54, places=9)
        self.assertAlmostEqual(ring.tip - 21 - planet.tip, 0.52, places=9)
        self.assertAlmostEqual(ring.root - 21 - planet.root, 0.52, places=9)


if __name__ == "__main__":
    unittest.main()
