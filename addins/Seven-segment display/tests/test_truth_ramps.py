"""Truth table, stations, ramp windows, ramp geometry and the lift function: the numbers of the gallery's
instructions.md and params_test.go, with no geometry."""

import math
import unittest

import _support  # noqa: F401
from gen import ramps, truth
from gen.constants import OFF_RADIUS, ON_RADIUS

A, B, C, D, E, F, G = truth.SEGMENTS

# The usual table (a b c d e f g), before the roles of a/d, b/e and c/f are swapped for the upright digit.
USUAL = [
    "1111110", "0110000", "1101101", "1111001", "0110011", "1011011", "1011111", "1110000", "1111111", "1111011",
]


class TruthTest(unittest.TestCase):
    def test_roles_are_swapped_against_the_usual_order(self):
        swap = {A: D, B: E, C: F, D: A, E: B, F: C, G: G}
        for digit, row in enumerate(USUAL):
            for s in truth.SEGMENTS:
                self.assertEqual(truth.lit(digit, swap[s]), row[s] == "1", f"digit {digit} segment {s}")

    def test_lit_counts(self):
        self.assertEqual([sum(truth.lit(d, s) for s in truth.SEGMENTS) for d in range(10)],
                         [6, 2, 5, 5, 4, 5, 6, 3, 7, 6])

    def test_out_of_range(self):
        with self.assertRaises(ValueError) as cm:
            truth.lit(10, A)
        self.assertEqual(str(cm.exception), "sevensegment: digit 10 out of range 0..9")
        with self.assertRaises(ValueError):
            truth.lit(0, 7)

    def test_stations(self):
        self.assertEqual([truth.station(s) for s in (D, E, C, G, B, F, A)], [-49.5, -33, -16.5, 0, 16.5, 33, 49.5])

    def test_names(self):
        self.assertEqual([truth.segment_name(s) for s in truth.SEGMENTS], list("abcdefg"))


class RampTest(unittest.TestCase):
    def test_window_per_step(self):
        # [psi_k + 8, psi_k + 29.5] mod 360, from the table of instructions.md.
        want = [(98, 119.5), (134, 155.5), (170, 191.5), (206, 227.5), (242, 263.5), (278, 299.5), (314, 335.5),
                (350, 11.5), (26, 47.5), (62, 83.5)]
        for k, (a, b) in enumerate(want):
            self.assertAlmostEqual(ramps.wrap360(ramps.psi_of(k) + 8.0), a)
            self.assertAlmostEqual(ramps.wrap360(ramps.psi_of(k) + 29.5), b)

    def test_ramp_counts(self):
        # The instructions' table counts the cams as the usual segments; the model's roles are swapped.
        counts = {A: 6, B: 8, C: 4, D: 4, E: 2, F: 2, G: 4}
        for s, n in counts.items():
            self.assertEqual(len(ramps.ramps_for(s)), n, s)
        self.assertEqual(sum(counts.values()), 30)

    def test_ramps_in_increasing_start_and_direction(self):
        for s in truth.SEGMENTS:
            starts = [r.start for r in ramps.ramps_for(s)]
            self.assertEqual(starts, sorted(starts))
            for r in ramps.ramps_for(s):
                self.assertEqual(r.rising, truth.lit((r.from_digit + 1) % 10, s))
                self.assertEqual(r.end - r.start, 21.5)

    def test_rising_geometry_at_8_degrees(self):
        g = ramps.ramp_geometry(ramps.Ramp(0, True, 8.0, 29.5))
        # Every size of the model is 1.5 times the earlier build's and the angles are the same, so each length here is
        # the earlier build's (c1 18.8151, 2.6443; c2 14.7960, 8.3712; ...) times 1.5.
        self.assertAlmostEqual(g.c1[0], 28.2227, places=3)
        self.assertAlmostEqual(g.c1[1], 3.9665, places=3)
        self.assertAlmostEqual(g.c2[0], 22.1940, places=3)
        self.assertAlmostEqual(g.c2[1], 12.5568, places=3)
        self.assertAlmostEqual(g.t1[0], 24.5361, places=3)
        self.assertAlmostEqual(g.t1[1], 4.6533, places=3)
        self.assertAlmostEqual(g.t2[0], 25.8807, places=3)
        self.assertAlmostEqual(g.t2[1], 11.8700, places=3)
        self.assertAlmostEqual(math.hypot(*g.t1), 24.9735, places=3)
        self.assertAlmostEqual(math.degrees(math.atan2(g.t1[1], g.t1[0])), 10.739, places=3)
        self.assertAlmostEqual(math.hypot(*g.t2), 28.473, places=3)
        self.assertAlmostEqual(math.degrees(math.atan2(g.t2[1], g.t2[0])), 24.638, places=3)
        self.assertAlmostEqual(g.line_length, 7.3409, places=3)

    def test_falling_geometry_is_the_mirror(self):
        g = ramps.ramp_geometry(ramps.Ramp(0, False, 8.0, 29.5))
        self.assertAlmostEqual(math.hypot(*g.c1), 25.5, places=9)
        self.assertAlmostEqual(math.hypot(*g.c2), 28.5, places=9)
        self.assertAlmostEqual(math.hypot(*g.t1), 28.473, places=3)
        self.assertAlmostEqual(math.degrees(math.atan2(g.t1[1], g.t1[0])), 8 + 4.862, places=3)
        self.assertAlmostEqual(math.hypot(*g.t2), 24.9735, places=3)
        self.assertAlmostEqual(math.degrees(math.atan2(g.t2[1], g.t2[0])), 8 + 18.761, places=3)

    def test_every_ramp_has_tangent_points_inside_its_window(self):
        for s in truth.SEGMENTS:
            for r in ramps.ramps_for(s):
                g = ramps.ramp_geometry(r)
                for t in (g.t1, g.t2):
                    ang = ramps.wrap360(math.degrees(math.atan2(t[1], t[0])) - r.start)
                    self.assertTrue(0 < ang < 21.5)

    def test_rising_lift_table(self):
        # Segment e at digit 1 -> 2 is not rising; use a segment that rises from 0 to 1: none do. Use c: 4->5 rises.
        table = {8: 0.0, 9: 0.0285, 10: 0.117, 12: 0.4455, 14: 0.8325, 16: 1.263, 18: 1.7415, 20: 2.271, 22: 2.856,
                 24: 3.5025, 26: 4.1145, 28: 4.431, 29: 4.4925, 29.5: 4.5}
        s = next(s for s in truth.SEGMENTS if any(r.rising and r.from_digit == 1 for r in ramps.ramps_for(s)))
        for off, lift in table.items():
            psi = ramps.psi_of(1) + off
            self.assertAlmostEqual(ramps.groove_radius(s, psi) - OFF_RADIUS, lift, delta=0.0025, msg=str(off))

    def test_falling_radius_is_the_rising_radius_at_the_mirrored_angle(self):
        s = next(s for s in truth.SEGMENTS if any(not r.rising and r.from_digit == 0 for r in ramps.ramps_for(s)))
        a, b = ramps.psi_of(0) + 8, ramps.psi_of(0) + 29.5
        path = ramps._RisingPath(a, b)
        for off in (9.0, 14.0, 20.0, 27.0):
            psi = ramps.psi_of(0) + off
            self.assertAlmostEqual(ramps.groove_radius(s, psi), path.radius(a + b - psi)[0], places=9)

    def test_dwell_and_rest_lifts(self):
        for s in truth.SEGMENTS:
            for digit in range(10):
                want = 4.5 if truth.lit(digit, s) else 0.0
                self.assertAlmostEqual(ramps.lift(s, 36 * digit), want, places=9, msg=f"{s} digit {digit}")

    def test_lift_stays_in_range(self):
        for s in truth.SEGMENTS:
            for i in range(720):
                self.assertTrue(-1e-9 <= ramps.lift(s, i * 0.5) <= 4.5 + 1e-9)

    def test_max_pressure_angle(self):
        worst = max(ramps.pressure_angle(s, 90 + 0.1 * i) for s in truth.SEGMENTS for i in range(3600))
        self.assertAlmostEqual(worst, 35.2, delta=0.1)

    def test_active_zone_of_the_lift(self):
        # Lift differs from its dwell by more than 0.075 only for psi - psi_k in [9.61, 27.93].
        s = next(s for s in truth.SEGMENTS if any(r.rising and r.from_digit == 1 for r in ramps.ramps_for(s)))
        moving = [off / 100 for off in range(800, 2951)
                  if abs(ramps.groove_radius(s, ramps.psi_of(1) + off / 100) - OFF_RADIUS) > 0.075
                  and abs(ramps.groove_radius(s, ramps.psi_of(1) + off / 100) - ON_RADIUS) > 0.075]
        self.assertAlmostEqual(min(moving), 9.61, delta=0.02)
        self.assertAlmostEqual(max(moving), 27.93, delta=0.02)


if __name__ == "__main__":
    unittest.main()
