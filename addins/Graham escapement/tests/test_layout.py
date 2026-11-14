import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen.constants import DEG
from gen.layout import angle_of, layout
from gen.params import default_params
from gen.validate import ValidationError


class LayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = layout(default_params())

    def near(self, want, got, name, tol=1e-4):
        self.assertAlmostEqual(want, got, delta=tol, msg=name)

    def near_pt(self, want, got, name):
        self.near(want[0], got[0], name + ".x")
        self.near(want[1], got[1], name + ".y")

    def test_axes_and_circle(self):
        g = self.g
        self.near(12 * DEG, g.pitch, "pitch")
        self.near(45 * DEG, g.half_span, "half span")
        self.near(56.5685, g.centre_distance, "d")
        self.near(40, g.tangent_radius, "rm")
        self.near(38.6, g.r_in, "r_in")
        self.near(41.4, g.r_out, "r_out")
        self.near_pt((0, 0), g.axis_o, "O")
        self.near_pt((0, 56.5685), g.axis_p, "P")
        self.near_pt((0, 70.5685), g.axis_s, "S")
        self.near_pt((0, -45.75), g.axis_g, "G")
        self.near_pt((-29.2569, 27.2770), g.il, "IL")
        self.near_pt((-27.2770, 29.2569), g.fl, "FL")
        self.near_pt((27.2770, 29.2569), g.ir, "IR")
        self.near_pt((29.2569, 27.2770), g.fr, "FR")

    def test_events_and_pallets(self):
        g = self.g
        self.near(-0.5 * DEG, g.psi_eu, "psi_eu")
        self.near(2 * DEG, g.psi_ef, "psi_ef")
        self.near(0.5 * DEG, g.psi_xu, "psi_xu")
        self.near(-2 * DEG, g.psi_xf, "psi_xf")
        self.near_pt((-29.5114, -29.0351), g.ce, "CE")
        self.near_pt((-26.3072, -28.2470), g.fe, "FE")
        self.near_pt((27.5143, -27.0726), g.cx, "CX")
        self.near_pt((28.2168, -30.2948), g.fx, "FX")
        self.near(-144.4661, g.top_e / DEG, "top_e")
        self.near(-35.5364, g.top_x / DEG, "top_x")
        self.near(5.2915, g.s0, "s0")

    def test_arms(self):
        g = self.g
        self.near_pt((-31.4116, -22.4337), g.ge, "GE")
        self.near_pt((-6.5102, -4.6495), g.he, "HE")
        self.near_pt((-33.6901, -24.0610), g.ke, "KE")
        self.near_pt((-37.1773, -19.1784), g.me, "ME")
        self.near_pt((-7.7932, 1.8073), g.ne, "NE")
        self.near_pt((31.4106, -22.4351), g.gx, "GX")
        self.near_pt((6.5100, -4.6498), g.hx, "HX")
        self.near_pt((33.6891, -24.0625), g.kx, "KX")
        self.near_pt((37.1764, -19.1800), g.mx, "MX")
        self.near_pt((7.7933, 1.8070), g.nx, "NX")

    def test_tooth_crutch_pendulum(self):
        g = self.g
        self.near_pt((0, 40), g.tooth_tip, "T")
        self.near_pt((-1.3272, 32.4729), g.tooth_l, "L")
        self.near_pt((-4.5118, 32.1853), g.tooth_b, "B")
        self.near_pt((2.5, -5.4544), g.crutch_ar, "A_R")
        self.near_pt((2.5, -41.8775), g.crutch_br, "B_R")
        self.near_pt((4, -9.1652), g.pend_er, "E_R")
        self.near_pt((4, -180 + 24.6779), g.pend_qr, "Q_R")

    def test_gears(self):
        g = self.g
        self.near(45.75, g.gear_centre, "centre")
        self.near(7.73, g.pinion_root, "pinion root")
        self.near(11.23, g.pinion_tip, "pinion tip")
        self.near(33.98, g.great_root, "great root")
        self.near(37.48, g.great_tip, "great tip")
        self.near(0.54, g.tip_to_root_a, "tip to root a")
        self.near(0.54, g.tip_to_root_b, "tip to root b")
        self.near(-90, g.pinion_phase / DEG, "pinion phase")
        self.near(93.75, g.great_phase / DEG, "great phase")
        self.near(0.99425, g.wheel_phase_e / DEG, "phi E")
        self.near(6.99425, g.wheel_phase_x / DEG, "phi X")
        self.near(1.98848, g.drop / DEG, "drop")
        self.assertAlmostEqual(g.pendulum_period, 0.851, delta=1e-3)

    def test_spring(self):
        g = self.g
        sd = g.spring
        self.assertEqual(sd.turns, 9)
        self.near(2.6, sd.pitch, "pitch")
        self.near(1.1, sd.gap, "gap")
        self.near(8.4, sd.first_inner_radius, "rho0")
        self.assertAlmostEqual(sd.active_length, 1142.3, delta=0.05)
        self.assertAlmostEqual(sd.eye_center_x, -31.250, delta=1e-3)
        self.assertAlmostEqual(sd.eye_center_y, -13.399, delta=1e-3)
        self.near(3.4, sd.eye_radius, "eye radius")
        self.near(3.8, sd.eye_hole_diameter, "hole")
        self.near(3.6, sd.bore_radius, "r_b")
        self.near(3.10, sd.bore_flat_distance, "f")
        self.near(0.55, sd.fillet_radius, "r_f")
        self.assertAlmostEqual(sd.taper_offset, 0.0692, delta=1e-4)
        self.near(1.3, sd.center_offset, "d")
        self.near(66.7916, g.spring_turn / DEG, "spring_turn")
        self.near(41.7639, g.carrier_offset / DEG, "carrier_offset")
        self.near_pt((0, -79.7515), g.spring_anchor, "Q")
        self.assertAlmostEqual(g.spring_rate, 3.10, delta=0.01)
        # The gallery rounds the full wind torque to 43.9; the formula gives 43.858.
        self.assertAlmostEqual(g.full_wind_torque, 43.9, delta=0.05)
        self.assertAlmostEqual(g.run_turns, 1.84, delta=0.01)
        self.assertAlmostEqual(g.full_wind_strain, 0.0093, delta=1e-4)

    def test_eye_lands_at_anchor(self):
        g = self.g
        sd = g.spring
        x, y = sd.eye_center_x, sd.eye_center_y
        c, s = math.cos(g.spring_turn), math.sin(g.spring_turn)
        px, py = c * x - s * y + g.axis_g[0], s * x + c * y + g.axis_g[1]
        self.assertAlmostEqual(px, g.spring_anchor[0], delta=1e-6)
        self.assertAlmostEqual(py, g.spring_anchor[1], delta=1e-6)

    def test_angle_of(self):
        self.near(137.0058, angle_of(self.g.il) / DEG, "angle IL")
        self.near(90, (angle_of(self.g.il) - angle_of(self.g.ir)) / DEG, "span")

    def test_invalid_params_raise(self):
        with self.assertRaises(ValidationError):
            layout(dataclasses.replace(default_params(), pendulum_length=100.0))


if __name__ == "__main__":
    unittest.main()
