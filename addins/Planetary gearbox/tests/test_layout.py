import dataclasses
import math
import unittest

import _support  # noqa: F401
from planetarygearboxgen import layout
from planetarygearboxgen.dims import derive
from planetarygearboxgen.params import default_params

P1 = default_params()
D1 = derive(P1)
P2 = dataclasses.replace(P1, stages=2)
D2 = derive(P2)

NAMES_K1 = [
    "Ring Gear",
    "Front Cover",
    "Rear Cover",
    "Front Bearing",
    "Rear Bearing",
    "Input Shaft",
    "Front Bolt 1",
    "Front Nut 1",
    "Front Bolt 2",
    "Front Nut 2",
    "Front Bolt 3",
    "Front Nut 3",
    "Front Bolt 4",
    "Front Nut 4",
    "Rear Bolt 1",
    "Rear Nut 1",
    "Rear Bolt 2",
    "Rear Nut 2",
    "Rear Bolt 3",
    "Rear Nut 3",
    "Rear Bolt 4",
    "Rear Nut 4",
    "Sun Gear 1",
    "Planet Gear 1.1",
    "Planet Bearing 1.1",
    "Planet Gear 1.2",
    "Planet Bearing 1.2",
    "Planet Gear 1.3",
    "Planet Bearing 1.3",
    "Carrier 1",
    "Output Shaft",
]


def near_vec(test, got, want, tol=1e-12):
    for g, w in zip(got, want):
        test.assertLess(abs(g - w), tol, f"{got} vs {want}")


class LayoutTest(unittest.TestCase):
    def test_names_k1(self):
        self.assertEqual([i.name for i in layout.instances(P1, D1)], NAMES_K1)
        self.assertEqual(layout.expected_body_count(P1), 31)

    def test_names_k2(self):
        names = [i.name for i in layout.instances(P2, D2)]
        self.assertEqual(len(names), 40)
        self.assertIn("Link Shaft 1", names)
        self.assertEqual(names[-2:], ["Carrier 2", "Output Shaft"])
        self.assertEqual(layout.expected_body_count(P2), 40)

    def test_parts_are_known(self):
        for inst in layout.instances(P2, D2):
            self.assertIn(inst.part, layout.PARTS)

    def test_shaft_specs(self):
        s = layout.input_shaft_spec(P1, D1)
        self.assertEqual((s.bottom, s.top, s.collar, s.grooves), (-23, 8, (-4, -0.5), ((0, 9),)))
        s = layout.output_shaft_spec(P1, D1)
        self.assertEqual((s.bottom, s.top, s.collar, s.grooves), (0, 26, (3.5, 6.75), ((-1, 3),)))
        self.assertIsNone(layout.link_shaft_spec(P1, D1))
        s = layout.link_shaft_spec(P2, D2)
        assert s is not None
        self.assertEqual((s.bottom, s.top, s.collar, s.grooves), (0, 12, (3.25, 3.75), ((-1, 3), (4, 13))))

    def test_link_spec_thin_gap(self):
        p = dataclasses.replace(P2, stage_gap=0.5)
        s = layout.link_shaft_spec(p, derive(p))
        assert s is not None
        self.assertIsNone(s.collar)
        self.assertEqual(s.grooves, ((-1, 12.5),))

    def test_pose(self):
        self.assertEqual(layout.Pose(flip=True, z=-1).apply((1, 2, 3)), (1, -2, -4))
        near_vec(self, layout.Pose(angle=math.pi / 2).apply((1, 0, 0)), (0, 1, 0))
        self.assertTrue(layout.Pose().is_identity())
        self.assertFalse(layout.Pose(flip=True).is_identity())
        o, x, y, z = layout.Pose(flip=True, z=-1).axes()
        self.assertEqual((o, x, y, z), ((0, 0, -1), (1, 0, 0), (0, -1, 0), (0, 0, -1)))

    def test_masters(self):
        self.assertEqual(layout.master_name(P1, D1, "cover"), "Rear Cover")
        self.assertEqual(layout.master_name(P1, D1, "planet"), "Planet Gear 1.3")
        suns = layout.instances_of(P2, D2, "sun")
        self.assertEqual([s.pose.z for s in suns], [0, 13])

    def test_fastener_masters_and_local_z(self):
        self.assertEqual(layout.master_name(P1, D1, "bolt"), "Rear Bolt 4")
        self.assertEqual(layout.master_name(P1, D1, "nut"), "Rear Nut 4")
        self.assertEqual(layout.part_local_z(P1, D1, "bolt"), (-6, 2))
        self.assertEqual(layout.part_local_z(P1, D1, "nut"), (0, 1.6))

    def test_parts_tuple(self):
        self.assertEqual(
            layout.PARTS,
            ("ring", "cover", "housing_bearing", "input_shaft", "bolt", "nut", "sun", "planet", "planet_bearing",
             "carrier", "link_shaft", "output_shaft"),
        )

    def poses(self, p, d):
        return {i.name: i.pose for i in layout.instances(p, d)}

    def check_pose(self, pose, angle, x, y, z, flip=False):
        for got, want in ((pose.angle, angle), (pose.x, x), (pose.y, y), (pose.z, z)):
            self.assertLess(abs(got - want), 1e-12, f"{pose}")
        self.assertEqual(pose.flip, flip)

    def test_fastener_poses(self):
        poses = self.poses(P1, D1)
        c = 40.5 * math.cos(math.pi / 4)
        self.check_pose(poses["Front Bolt 1"], 0, c, c, -2, flip=True)
        self.check_pose(poses["Rear Bolt 1"], 0, c, c, 14)
        self.check_pose(poses["Front Nut 1"], -math.pi / 4, c, c, 0.1)
        self.check_pose(poses["Rear Nut 4"], 5 * math.pi / 4, c, -c, 10.3)
        self.assertLess(abs(poses["Planet Bearing 1.1"].z - 1.25), 1e-12)

    def test_nut_cavity_and_head_pocket_poses(self):
        cav = layout.nut_cavity_poses(P1, D1)
        self.assertEqual(len(cav), 8)
        self.assertEqual([round(q.z, 9) for q in cav], [2.0] * 4 + [12.2] * 4)
        for i, q in enumerate(cav):
            a = math.pi / 4 + (i % 4) * math.pi / 2
            self.assertLess(abs(q.x - 40.5 * math.cos(a)), 1e-12)
            self.assertLess(abs(q.y - 40.5 * math.sin(a)), 1e-12)
            self.assertLess(abs(q.angle - (math.pi / 4 + (i % 4) * math.pi / 2 - math.pi / 2)), 1e-12)
        heads = layout.head_pocket_poses(D1)
        self.assertEqual(len(heads), 4)
        self.assertTrue(all(h.z == 0 and h.angle == 0 and not h.flip for h in heads))

    def test_unapply(self):
        pose = layout.Pose(angle=0.3, x=1, y=2, z=3, flip=True)
        q = (0.5, -1.0, 2.0)
        near_vec(self, pose.unapply(pose.apply(q)), q)

    def test_part_local_z(self):
        self.assertEqual(layout.part_local_z(P1, D1, "ring"), (1, 15))
        self.assertEqual(layout.part_local_z(P1, D1, "carrier"), (-9, 3))
        with self.assertRaises(ValueError):
            layout.part_local_z(P1, D1, "link_shaft")


if __name__ == "__main__":
    unittest.main()
