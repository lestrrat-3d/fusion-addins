import math
import unittest

import _support  # noqa: F401
from gen import frames, poses
from gen.params import default_params
from gen.validate import derive


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class TurnTest(unittest.TestCase):
    def test_turn_is_a_right_hand_rotation_about_the_shaft_axis(self):
        t = poses.turn_axes(90.0)
        # A point above the axis (+Z) goes to +X for a right-hand turn about +Y: x' = x cos + z sin.
        self.assertTrue(close(frames.apply(t, (0.0, 5.0, 46.25)), (2.0, 5.0, 44.25)))
        # A point on the axis stays.
        self.assertTrue(close(frames.apply(t, (0.0, -10.0, 44.25)), (0.0, -10.0, 44.25)))

    def test_zero_turn_is_the_identity(self):
        t = poses.turn_axes(0.0)
        self.assertTrue(close(t[0], (0.0, 0.0, 0.0)))
        self.assertEqual((t[1], t[2], t[3]), ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))

    def test_cam_angle_goes_to_psi_minus_theta(self):
        # Material at cam-local angle psi sits at psi - theta after the turn (instructions.md "Coordinates").
        for theta in (36.0, 108.0, 200.0):
            ax = poses.cam_axes(0, theta)
            for psi in (10.0, 90.0, 250.0):
                local = (math.cos(math.radians(psi)), math.sin(math.radians(psi)), 0.0)
                world = frames.apply(ax, local)
                # World point relative to the shaft axis, read in the front view: u = +X, v = +Z.
                got = math.degrees(math.atan2(world[2] - 44.25, world[0])) % 360
                self.assertAlmostEqual(got, (psi - theta) % 360, places=6)

    def test_follower_at_the_top_reads_digit(self):
        for digit in range(10):
            theta = 36.0 * digit
            ax = poses.cam_axes(0, theta)
            # The cam-local angle 90 + theta is the digit's rest and lies under the follower at the top (+Z).
            psi = 90.0 + theta
            local = (math.cos(math.radians(psi)), math.sin(math.radians(psi)), 0.0)
            world = frames.apply(ax, local)
            self.assertAlmostEqual(world[0], 0.0, places=9)
            self.assertGreater(world[2], 44.25)

    def test_frames_are_right_handed(self):
        axes = [poses.wall_axes(True), poses.wall_axes(False), poses.bearing_axes(True), poses.bearing_axes(False),
                poses.shaft_axes(72.0)] + [poses.cam_axes(s, 72.0) for s in range(7)]
        for _, x, y, z in axes:
            cx = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
            self.assertTrue(close(cx, z))


class FrameOriginsTest(unittest.TestCase):
    def test_wall_and_bearing_frames(self):
        self.assertEqual(poses.wall_axes(True)[0], (0.0, -74.25, 44.25))
        self.assertEqual(poses.wall_axes(True)[3], (0.0, -1.0, 0.0))
        self.assertEqual(poses.wall_axes(False)[0], (0.0, 64.5, 44.25))
        self.assertEqual(poses.wall_axes(False)[1], (-1.0, 0.0, 0.0))
        self.assertEqual(poses.wall_axes(False)[3], (0.0, 1.0, 0.0))
        # The front bearing runs -Y from the front wall's inner face, the rear one +Y.
        self.assertEqual(poses.bearing_axes(True)[3], (0.0, -1.0, 0.0))
        self.assertEqual(poses.bearing_axes(False)[3], (0.0, 1.0, 0.0))

    def test_cam_origins_are_the_groove_faces(self):
        # Cam a: station 49.5, groove face 52.75.
        self.assertTrue(close(poses.cam_axes(0, 0.0)[0], (0.0, 52.75, 44.25)))
        self.assertTrue(close(poses.cam_axes(3, 0.0)[0], (0.0, -46.25, 44.25)))  # cam d, station -49.5

    def test_shaft_frame_maps_local_z_to_world_y(self):
        ax = poses.shaft_axes(0.0)
        self.assertTrue(close(frames.apply(ax, (0.0, 0.0, 10.0)), (0.0, 10.0, 44.25)))
        self.assertTrue(close(frames.apply(ax, (1.0, 0.0, 0.0)), (0.0, 0.0, 45.25)))  # local +x is world +Z


class SiteInTest(unittest.TestCase):
    def test_round_trip_through_a_wall_frame(self):
        dm = derive(default_params())
        for front in (True, False):
            ax = poses.wall_axes(front)
            for s in dm.sites:
                local = poses.site_in(s, ax)
                self.assertTrue(close(frames.apply(ax, local.head), s.head))
                self.assertTrue(close(frames.rotate(ax, local.dir), s.dir))
                self.assertTrue(close(frames.rotate(ax, local.corner), s.corner))

    def test_front_wall_g_bolt_in_the_wall_frame(self):
        # G1 head at (-31.3, -51.3, 74.75): 22.95 behind the inner face (the ribs stand on the inner face, local z < 0),
        # u = -31.3, v = 74.75 - 44.25 = 30.5, pointing along local +v.
        dm = derive(default_params())
        local = poses.site_in(dm.sites[4], poses.wall_axes(True))
        self.assertTrue(close(local.head, (-31.3, 30.5, -22.95)))
        self.assertTrue(close(local.dir, (0.0, 1.0, 0.0)))

    def test_rear_wall_u_runs_along_minus_x(self):
        dm = derive(default_params())
        local = poses.site_in(dm.sites[3], poses.wall_axes(False))  # T4 at x +31.3
        self.assertAlmostEqual(local.head[0], -31.3)


if __name__ == "__main__":
    unittest.main()
