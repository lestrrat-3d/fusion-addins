import math
import unittest

import _support  # noqa: F401
from gen import bodies
from gen.constants import BUILD_BACKOFF, DEG
from gen.curves import loop_polygon
from gen.layout import layout
from gen.motion import state_at
from gen.params import default_params
from gen.pose import Pose, body_poses
from gen.spring import profile, spring_params

P = default_params()
G = layout(P)
S = state_at(G, P.phase)
POSES = body_poses(G, S)


class PoseTest(unittest.TestCase):
    def test_apply_unapply(self):
        for pose in (Pose(), Pose(angle=0.7, x=1.0, y=-2.0, z=3.0), Pose(flip=True, angle=-0.3, x=4.0, y=5.0, z=6.0)):
            for pt in ((1.0, 2.0, 3.0), (-4.0, 0.5, 7.0)):
                back = pose.unapply(pose.apply(pt))
                for a, b in zip(back, pt):
                    self.assertAlmostEqual(a, b, places=12)
        self.assertTrue(Pose().is_identity())
        self.assertFalse(Pose(z=1.0).is_identity())
        o, x, y, z = Pose(angle=math.pi / 2, x=1.0).axes()
        self.assertAlmostEqual(x[1], 1.0)
        self.assertAlmostEqual(o[0], 1.0)
        self.assertAlmostEqual(Pose(flip=True).axes()[3][2], -1.0)

    def test_every_body_has_a_pose(self):
        self.assertEqual(set(POSES), set(bodies.BODY_NAMES))

    def test_fixed_bodies_translate_only(self):
        for name in (
            bodies.BACK_PLATE, bodies.FRONT_PLATE, bodies.SUSPENSION_PIN, bodies.SUSPENSION_CAP,
            bodies.SPRING_ANCHOR_PIN, bodies.BACK_ESCAPE_BEARING, bodies.FRONT_GREAT_WHEEL_BEARING,
        ):
            self.assertEqual(POSES[name].angle, 0.0, name)
            self.assertFalse(POSES[name].flip)
        self.assertTrue(POSES[bodies.BACK_PLATE].is_identity())
        self.assertEqual(POSES[bodies.BACK_PALLET_BEARING].z, -5.0)
        self.assertEqual(POSES[bodies.FRONT_PALLET_BEARING].z, 28.0)
        self.assertEqual(POSES[bodies.PENDULUM_BEARING].z, 40.05)

    def test_angles(self):
        wheel = S.wheel_angle - BUILD_BACKOFF
        self.assertAlmostEqual(POSES[bodies.ESCAPE_ARBOR].angle, -wheel)
        self.assertAlmostEqual(POSES[bodies.ESCAPE_WHEEL].angle, -wheel)
        self.assertAlmostEqual(POSES[bodies.ANCHOR].angle, -S.anchor_angle)
        self.assertAlmostEqual(POSES[bodies.PENDULUM].angle, -S.pendulum_angle)
        great = G.great_phase + wheel * 13 / 48
        self.assertAlmostEqual(POSES[bodies.GREAT_WHEEL].angle, great)
        arbor = great + 20.8 * DEG + G.carrier_offset
        for name in (bodies.GREAT_WHEEL_ARBOR, bodies.PAWL_CARRIER, bodies.SPRING_RETAINER, bodies.WINDING_KNOB):
            self.assertAlmostEqual(POSES[name].angle, arbor)
        self.assertEqual(POSES[bodies.MAINSPRING].z, 11.25)

    def test_collars(self):
        wheel = S.wheel_angle - BUILD_BACKOFF
        great = G.great_phase + wheel * 13 / 48
        arbor = great + 20.8 * DEG + G.carrier_offset
        cases = {
            bodies.CRUTCH_COLLAR: (-S.anchor_angle, G.axis_p[0], G.axis_p[1], 34.25),
            bodies.KNOB_COLLAR: (arbor, G.axis_g[0], G.axis_g[1], 34.25),
        }
        for name, want in cases.items():
            got = POSES[name]
            for have, exp in zip((got.angle, got.x, got.y, got.z), want):
                self.assertAlmostEqual(have, exp, places=12, msg=name)
            self.assertFalse(got.flip)
        self.assertEqual(POSES[bodies.KNOB_COLLAR].angle, POSES[bodies.WINDING_KNOB].angle)
        self.assertEqual(POSES[bodies.CRUTCH_COLLAR].angle, POSES[bodies.CRUTCH].angle)

    def test_fasteners(self):
        self.assertEqual((POSES["Bolt 1"].x, POSES["Bolt 1"].y, POSES["Bolt 1"].z), (-50.0, 74.0, 32.0))
        self.assertEqual((POSES["Bolt 4"].x, POSES["Bolt 4"].y), (50.0, -88.0))
        nut = POSES["Nut 3"]
        self.assertTrue(nut.flip)
        self.assertEqual((nut.x, nut.y, nut.z), (-50.0, -88.0, 25.8))
        self.assertAlmostEqual(nut.apply((0.0, 0.0, 1.6))[2], 24.2)

    def test_mainspring_eye_lands_at_anchor(self):
        dm = G.spring
        x, y, _ = POSES[bodies.MAINSPRING].apply((dm.eye_center_x, dm.eye_center_y, 0.0))
        self.assertAlmostEqual(x, G.spring_anchor[0], delta=1e-3)
        self.assertAlmostEqual(y, G.spring_anchor[1], delta=1e-3)
        self.assertAlmostEqual(G.spring_anchor[1], -79.7515, delta=1e-3)

    def test_mainspring_bounds(self):
        outer, _, _ = profile(spring_params(), G.spring)
        pts = [POSES[bodies.MAINSPRING].apply((px, py, 0.0)) for px, py in loop_polygon(outer)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.assertAlmostEqual(min(xs), -32.0, delta=0.01)
        self.assertAlmostEqual(max(xs), 31.21, delta=0.01)
        self.assertAlmostEqual(min(ys), -83.15, delta=0.01)
        self.assertAlmostEqual(max(ys), -13.75, delta=0.01)


if __name__ == "__main__":
    unittest.main()
