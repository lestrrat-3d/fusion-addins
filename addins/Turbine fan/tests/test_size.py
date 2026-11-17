import math
import unittest

import _support  # noqa: F401
from gen.constants import MAX_HUB_RADIUS
from gen.fasteners import HEAD_POCKET_RADIUS
from gen.size import SizeError, size_for


class SizeTest(unittest.TestCase):
    """instructions.md "Size": the table at 128, 192 and 224."""

    FIELDS = ("scale", "hub_scale", "tip_radius", "hub_radius", "hub_length", "hub_mid", "root_radius", "ref_radius",
              "hold_radius", "blade_socket_start", "blade_stud_start", "blade_stud_radius", "blade_socket_radius",
              "blade_stud_end", "blade_bolt_at", "blade_bolt_length", "blade_bolt_cavity")
    TABLE = {
        128.0: (1, 1, 64, 14, 20, 10, 14.4, 48, 21.5, 5.7, 6.1, 3, 3.4, 16, 9.5, 16, 15.6),
        192.0: (1.5, 1.35, 96, 18.9, 30, 15, 19.3, 72, 32.25, 7.695, 8.095, 4.05, 4.45, 21.6, 12.825, 25, 24.6),
        224.0: (1.75, 1.35, 112, 18.9, 35, 17.5, 19.3, 84, 37.625, 7.695, 8.095, 4.05, 4.45, 21.6, 12.825, 25, 24.6),
    }

    def test_table(self):
        for d, want in self.TABLE.items():
            sz = size_for(d)
            self.assertEqual(sz.rotor_diameter, d)
            for name, value in zip(self.FIELDS, want):
                with self.subTest(d=d, field=name):
                    self.assertAlmostEqual(getattr(sz, name), value, places=9)

    def test_hub_radius_stops_at_the_clutch_cap(self):
        # The cap leaves the ear bolts of the 605ZZ clutch (ear circle 21.6) room for a head and a hex key.
        self.assertAlmostEqual(MAX_HUB_RADIUS, 21.6 - HEAD_POCKET_RADIUS - 0.5)
        self.assertEqual(size_for(224.0).hub_radius, MAX_HUB_RADIUS)
        self.assertLess(size_for(130.0).hub_radius, MAX_HUB_RADIUS)

    def test_blade_bolt_tip_stays_above_the_back_face(self):
        for d in (128.0, 150.0, 192.0, 224.0):
            sz = size_for(d)
            self.assertGreaterEqual(sz.hub_length - 2.0 - sz.blade_bolt_length, 2.0 - 1e-9)
        self.assertEqual(size_for(224.0).hub_length - 2.0 - 25.0, 8.0)  # the tip at z 8, as instructions.md says

    def test_range(self):
        for d in (127.9, 224.1, math.nan, math.inf, -math.inf):
            with self.subTest(d=d):
                with self.assertRaises(SizeError) as cm:
                    size_for(d)
                self.assertEqual(str(cm.exception), "RotorDiameter must lie in [128, 224] mm")
        size_for(128.0)
        size_for(224.0)

    def test_size_is_a_value(self):
        self.assertEqual(size_for(192.0), size_for(192.0))
        self.assertNotEqual(size_for(192.0), size_for(193.0))


if __name__ == "__main__":
    unittest.main()
