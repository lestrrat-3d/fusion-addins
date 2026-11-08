import dataclasses
import math
import unittest

import _support  # noqa: F401
from planetarygearboxgen.dims import derive
from planetarygearboxgen import gears
from planetarygearboxgen.involute import gear_outline_polygon
from planetarygearboxgen.params import default_params
from planetarygearboxgen.phase import planet_orbit_angle, planet_tooth_angle, ring_tooth_angle
from planetarygearboxgen.polygon import count_inside

DENSE = 20
TOL = 0.02


def penetrations(p, extra_turn=0.0):
    """Return (sun_in_planet, planet_in_sun, ring_in_planet, planet_in_ring) summed over the planets."""
    d = derive(p)
    sun_gd = gears.sun_gear(p)
    planet_gd = gears.planet_gear(p)
    ring_gd = gears.ring_tool(p)
    sun = gear_outline_polygon(sun_gd, DENSE)
    ring = gear_outline_polygon(ring_gd, DENSE, angle=ring_tooth_angle(p))
    totals = [0, 0, 0, 0]
    for i in range(p.planet_count):
        phi = planet_orbit_angle(p, i)
        center = (d.orbit * math.cos(phi), d.orbit * math.sin(phi))
        turn = planet_tooth_angle(p, i) + (extra_turn if i == 0 else 0.0)
        planet = gear_outline_polygon(planet_gd, DENSE, angle=turn, center=center)
        # Only points inside the radius windows where the gears can touch are tested.
        near_sun = [q for q in planet if math.hypot(*q) <= sun_gd.tip + 0.1]
        near_ring = [q for q in planet if math.hypot(*q) >= d.ring_tip - 0.1]
        sun_near = [q for q in sun if math.hypot(q[0] - center[0], q[1] - center[1]) <= d.planet_tip + 0.1]
        ring_near = [q for q in ring if math.hypot(q[0] - center[0], q[1] - center[1]) <= d.planet_tip + 0.1]
        totals[0] += count_inside(sun_near, planet, TOL)
        totals[1] += count_inside(near_sun, sun, TOL)
        totals[2] += count_inside(ring_near, planet, TOL)
        # Ring material is outside the tool polygon.
        totals[3] += count_inside(near_ring, ring, TOL, material_inside=False)
    return tuple(totals)


class PhaseTest(unittest.TestCase):
    def test_ring_tooth_angle_default(self):
        self.assertEqual(ring_tooth_angle(default_params()), 0.0)

    def test_ring_tooth_angle_offset(self):
        p = dataclasses.replace(default_params(), sun_teeth=14, planet_teeth=30, ring_teeth=74)
        self.assertLess(abs(ring_tooth_angle(p) - math.pi / 74), 1e-12)

    def test_orbit_angles(self):
        p = default_params()
        for i in range(3):
            self.assertLess(abs(planet_orbit_angle(p, i) - 2 * math.pi * i / 3), 1e-12)

    def test_planets_mesh(self):
        for backlash in (0.05, 0.2):
            with self.subTest(backlash=backlash):
                got = penetrations(dataclasses.replace(default_params(), backlash=backlash))
                self.assertEqual(got, (0, 0, 0, 0), f"penetration counts {got}")

    def test_wrong_phase_is_detected(self):
        got = penetrations(default_params(), extra_turn=math.pi / 29)
        self.assertGreater(got[0] + got[1], 0, f"sun penetration counts {got}")
        self.assertGreater(got[2] + got[3], 0, f"ring penetration counts {got}")


if __name__ == "__main__":
    unittest.main()
