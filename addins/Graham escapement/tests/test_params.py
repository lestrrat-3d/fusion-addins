import math
import unittest

import _support  # noqa: F401
from gen.constants import DEG
from gen.inputs import INPUT_SPECS, params_from_values
from gen.params import Frame, Params, default_params, frame_axes, frame_is_valid, placement_frame
from gen.validate import validate


class ParamsTest(unittest.TestCase):
    def test_defaults(self):
        p = default_params()
        self.assertEqual(p.pendulum_length, 180.0)
        self.assertEqual(p.amplitude, 5 * DEG)
        self.assertEqual(p.lock_angle, 1.5 * DEG)
        self.assertEqual(p.lift_angle, 2.5 * DEG)
        self.assertEqual(p.phase, 0.25)
        self.assertEqual(p.backlash, 0.15)
        self.assertIsNone(p.placement)
        validate(p)

    def test_input_specs(self):
        got = [(s.id, s.kind, s.default) for s in INPUT_SPECS]
        want = [
            ("pendulum_length", "length", 180),
            ("amplitude", "angle", 5),
            ("lock_angle", "angle", 1.5),
            ("lift_angle", "angle", 2.5),
            ("phase", "scalar", 0.25),
            ("backlash", "length", 0.15),
        ]
        self.assertEqual(got, want)
        self.assertEqual([s.label for s in INPUT_SPECS][:2], ["Pendulum length", "Amplitude"])

    def test_params_from_default_values_is_default(self):
        values = {s.id: (math.radians(s.default) if s.kind == "angle" else s.default) for s in INPUT_SPECS}
        self.assertEqual(params_from_values(values), default_params())

    def test_angle_snap(self):
        for deg_value, field in ((1.5, "lock_angle"), (3.0, "lift_angle"), (6.0, "amplitude")):
            for rad in (math.radians(deg_value), deg_value * math.pi / 180, deg_value * (math.pi / 180)):
                values = {s.id: (math.radians(s.default) if s.kind == "angle" else s.default) for s in INPUT_SPECS}
                values[field] = rad
                p = params_from_values(values)
                self.assertEqual(getattr(p, field), deg_value * DEG)
                validate(p)

    def test_placement_identity_and_axis(self):
        self.assertIsNone(placement_frame(None, None))
        f = placement_frame((1.0, 2.0, 3.0), (0.0, 0.0, 1.0))
        self.assertTrue(frame_is_valid(f))
        o, x, y, z = frame_axes(f)
        self.assertEqual(o, (1.0, 2.0, 3.0))
        self.assertAlmostEqual(z[2], 1.0)
        self.assertFalse(frame_is_valid(Frame(u=(1.0, 0.0, 0.0), v=(2.0, 0.0, 0.0))))
        with self.assertRaises(ValueError):
            placement_frame(None, (0.0, 0.0, 0.0))
        self.assertIsInstance(default_params(), Params)


if __name__ == "__main__":
    unittest.main()
