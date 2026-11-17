import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import bodies, bridge, expected, probes
from gen.params import default_params, params_6082rs
from gen.validate import derive


class BridgeTest(unittest.TestCase):
    def test_only_the_arm_has_a_layer(self):
        p = default_params()
        self.assertEqual(len(bridge.bridges_of(bodies.ARM, p)), 1)
        for name in bodies.BODY_NAMES:
            if name != bodies.ARM:
                self.assertEqual(bridge.bridges_of(name, p), [], name)

    def test_layer_fills_the_pin_hole_above_the_head_pocket(self):
        p = dataclasses.replace(default_params(), throw=60.0)
        (b,) = bridge.arm_bridges(p)
        self.assertEqual(b.center, (0.0, 60.0))
        self.assertEqual((b.radius, b.z0, b.thickness), (1.3, 2.0, 0.3))
        self.assertAlmostEqual(b.disc_radius(), 1.4)
        self.assertAlmostEqual(b.volume(), math.pi * 1.69 * 0.3)

    def test_layer_ends_below_the_stub_pocket(self):
        (b,) = bridge.arm_bridges(default_params())
        self.assertLess(b.z0 + b.thickness, 3.25)  # the hexagonal pocket's floor

    def test_expected_volume_adds_the_layer_only_when_on(self):
        for p in (default_params(), params_6082rs()):
            on = dataclasses.replace(p, sacrificial_bridging=True)
            off = expected.body_volume(bodies.ARM, p, derive(p)).value
            added = expected.body_volume(bodies.ARM, on, derive(on)).value - off
            self.assertAlmostEqual(added, math.pi * 1.3**2 * 0.3, places=9)
            self.assertEqual(bridge.extra_volume(bodies.PIN, on), 0.0)

    def test_probe_follows_the_option(self):
        for on in (False, True):
            p = dataclasses.replace(default_params(), sacrificial_bridging=on)
            arm = {q.label: q for q in probes.part_probes(p, derive(p))[bodies.ARM]}
            self.assertEqual(arm["bridge layer"].expect, probes.INSIDE if on else probes.OUTSIDE)
            self.assertEqual(arm["pin hole above the bridge"].expect, probes.OUTSIDE)
            self.assertEqual(arm["bridge layer"].point, (0.0, 55.0, 2.15))


if __name__ == "__main__":
    unittest.main()
