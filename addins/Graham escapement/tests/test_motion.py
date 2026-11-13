import dataclasses
import unittest

import _support  # noqa: F401
from gen.constants import DEG
from gen.layout import layout
from gen.motion import motion, pendulum_angle, state_at, wheel_at
from gen.params import default_params

N = 4000


class MotionTest(unittest.TestCase):
    def _check(self, p):
        g = layout(p)
        prev = state_at(g, 0.0)
        first = prev
        jumps = 0
        for i in range(1, N + 1):
            s = state_at(g, i / N)
            self.assertGreaterEqual(s.wheel_angle, prev.wheel_angle - 1e-12, f"phase {s.phase}")
            if s.locked != "" and s.locked == prev.locked:
                self.assertAlmostEqual(prev.wheel_angle, s.wheel_angle, delta=1e-12)
            d = s.wheel_angle - prev.wheel_angle
            if d > g.drop / 2 and prev.locked == "" and s.locked != "":
                self.assertAlmostEqual(g.drop, d, delta=0.2 * DEG)
                jumps += 1
            self.assertAlmostEqual(pendulum_angle(s.anchor_angle), s.pendulum_angle, delta=1e-12)
            self.assertAlmostEqual(s.wheel_angle * 13.0 / 48.0, s.great_wheel_angle, delta=1e-12)
            prev = s
        self.assertAlmostEqual(g.pitch, prev.wheel_angle - first.wheel_angle, delta=1e-9)
        self.assertEqual(jumps, 2)
        for psi, increasing, to in (
            (g.psi_ef, True, g.wheel_phase_x),
            (g.psi_xf, False, g.wheel_phase_e + g.pitch),
        ):
            before, _ = wheel_at(g, psi - 1e-12 if increasing else psi + 1e-12, increasing)
            self.assertAlmostEqual(g.drop, to - before, delta=1e-6)

    def test_default(self):
        self._check(default_params())

    def test_wide(self):
        self._check(dataclasses.replace(default_params(), lock_angle=1.25 * DEG, lift_angle=3 * DEG,
                                        amplitude=6 * DEG))

    def test_pendulum_angle_at_default(self):
        s = motion(dataclasses.replace(default_params(), phase=0.5))
        self.assertAlmostEqual(s.pendulum_angle, 3.814 * DEG, delta=1e-3 * DEG)


if __name__ == "__main__":
    unittest.main()
