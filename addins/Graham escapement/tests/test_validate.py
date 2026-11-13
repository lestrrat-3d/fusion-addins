import dataclasses
import unittest

import _support  # noqa: F401
from gen.constants import DEG
from gen.params import Frame, default_params
from gen.validate import ValidationError, validate


def _msg(**kw) -> str:
    with unittest.TestCase().assertRaises(ValidationError) as cm:
        validate(dataclasses.replace(default_params(), **kw))
    return str(cm.exception)


class ValidateTest(unittest.TestCase):
    def test_default_valid(self):
        validate(default_params())

    def test_ranges(self):
        cases = {
            "pendulum_length": (120, 250),
            "lock_angle": (1.25 * DEG, 1.5 * DEG),
            "lift_angle": (2 * DEG, 3 * DEG),
            "backlash": (0.0, 0.3),
        }
        for field, (lo, hi) in cases.items():
            p = default_params()
            validate(dataclasses.replace(p, **{field: lo}))
            validate(dataclasses.replace(p, **{field: hi}))
            with self.assertRaises(ValidationError):
                validate(dataclasses.replace(p, **{field: lo - 0.01 * DEG - 0.01}))
            with self.assertRaises(ValidationError):
                validate(dataclasses.replace(p, **{field: hi + 0.01 * DEG + 0.01}))

    def test_nan_and_phase(self):
        self.assertEqual(_msg(pendulum_length=float("nan")), "PendulumLength must be finite, got NaN")
        self.assertEqual(_msg(amplitude=float("inf")), "Amplitude must be finite, got +Inf")
        self.assertIn("Phase 1 is outside its range [0, 1]", _msg(phase=1.0))
        self.assertIn("Phase -0.01 is outside its range [0, 1]", _msg(phase=-0.01))
        validate(dataclasses.replace(default_params(), phase=0.0))
        validate(dataclasses.replace(default_params(), phase=0.999))

    def test_amplitude_follows_lift_and_lock(self):
        p = default_params()
        lo = (p.lift_angle + p.lock_angle) / 2 + DEG
        validate(dataclasses.replace(p, amplitude=lo))
        validate(dataclasses.replace(p, amplitude=6 * DEG))
        self.assertIn("Amplitude", _msg(amplitude=lo - 0.01 * DEG))
        self.assertIn("Amplitude", _msg(amplitude=6 * DEG + 0.01 * DEG))
        # A larger lift and lock raise the lower bound.
        q = dataclasses.replace(p, lift_angle=3 * DEG, lock_angle=1.5 * DEG)
        self.assertIn("Amplitude", _msg(lift_angle=3 * DEG, lock_angle=1.5 * DEG, amplitude=3.2 * DEG))
        validate(dataclasses.replace(q, amplitude=3.25 * DEG))

    def test_exact_messages(self):
        self.assertEqual(_msg(pendulum_length=100.0), "PendulumLength 100 is outside its range [120, 250]")
        self.assertEqual(_msg(placement=Frame(u=(1.0, 0.0, 0.0), v=(2.0, 0.0, 0.0))), "Placement must be a valid frame")

    def test_field_order(self):
        self.assertIn("PendulumLength", _msg(pendulum_length=100.0, phase=2.0))
        self.assertIn("LockAngle", _msg(lock_angle=0.0, phase=2.0))


if __name__ == "__main__":
    unittest.main()
