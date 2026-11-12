import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import layout
from gen.bridge import BRIDGE_THICKNESS, bridge_disc_diameter, nut_bridge_poses, nut_bridge_volume
from gen.dims import derive
from gen.fasteners import nut_cavity_height
from gen.params import default_params
from gen.probes import INSIDE, part_probes

P1 = default_params()
D1 = derive(P1)


class BridgeTest(unittest.TestCase):
    def test_layer_is_one_printed_layer(self):
        self.assertEqual(BRIDGE_THICKNESS, 0.3)

    def test_disc_reaches_into_the_hole_wall(self):
        self.assertAlmostEqual(bridge_disc_diameter(2.6), 2.8, places=12)

    def test_poses_sit_on_each_cavity_roof(self):
        cavities = layout.nut_cavity_poses(P1, D1)
        poses = nut_bridge_poses(P1, D1)
        self.assertEqual(len(poses), 8)
        for cavity, pose in zip(cavities, poses):
            self.assertAlmostEqual(pose.z, cavity.z + nut_cavity_height(), places=12)
            self.assertEqual((pose.x, pose.y, pose.angle, pose.flip), (cavity.x, cavity.y, cavity.angle, cavity.flip))
        # Cavities start at 2.0 and 12.0 and are 2.0 tall, so the roofs are at 4.0 and 14.0 in ring-local z.
        self.assertEqual([round(q.z, 9) for q in poses], [4.0] * 4 + [14.0] * 4)

    def test_layer_ends_inside_the_ring(self):
        lo, hi = layout.part_local_z(P1, D1, "ring")
        for pose in nut_bridge_poses(P1, D1):
            self.assertGreaterEqual(pose.z, lo)
            self.assertLessEqual(pose.z + BRIDGE_THICKNESS, hi)

    def test_volume_is_eight_hole_sections(self):
        expected = 8 * math.pi * 1.3**2 * 0.3
        self.assertAlmostEqual(nut_bridge_volume(P1), expected, places=9)

    def test_probes_cover_every_layer_when_enabled(self):
        p = dataclasses.replace(P1, sacrificial_bridging=True)
        layers = [pr for pr in part_probes(p, derive(p))["ring"] if "bridge layer" in pr.label]
        self.assertEqual(len(layers), 8)
        self.assertTrue(all(pr.expect == INSIDE for pr in layers))

    def test_no_bridge_probes_by_default(self):
        self.assertFalse(P1.sacrificial_bridging)
        self.assertEqual([pr for pr in part_probes(P1, D1)["ring"] if "bridge layer" in pr.label], [])


if __name__ == "__main__":
    unittest.main()
