"""Click indexer geometry without Fusion: sections, frames, the spring's helix, the tooth ramps and PressTurn."""

import math
import unittest

import _support  # noqa: F401

from gen import clicker_params as cp
from gen import clicker_teeth as ct
from gen import curves, frames, poses
from gen.constants import SHAFT_Z


def section_area_and_centroid_x(loop):
    """Area and x centroid of a polygon loop of lines (the sections have no arcs)."""
    pts = curves.loop_polygon(loop)
    area = curves.polygon_area(pts)
    cx = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cross
    return area, cx / (6 * area)


def revolved_volume(loop):
    area, cx = section_area_and_centroid_x(loop)
    return abs(2 * math.pi * area * cx)


class FramesTest(unittest.TestCase):
    def test_up_frame_runs_toward_minus_y(self):
        o, x, y, z = cp.fup_axes(-99.65)
        self.assertEqual(o, (0.0, -99.65, SHAFT_Z))
        self.assertEqual(frames.rotate(cp.fup_axes(0.0), (0, 0, 1)), (0.0, -1.0, 0.0))
        self.assertEqual((x, y, z), ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)))

    def test_down_frame_runs_toward_plus_y(self):
        _, x, y, z = cp.fdown_axes(-101.25)
        self.assertEqual((x, y, z), ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    def test_frames_are_right_handed(self):
        for axes in (cp.fup_axes(0.0), cp.fdown_axes(0.0), cp.hub_axes(72.0), cp.rotor_axes(36.0),
                     cp.spring_axes(108.0)):
            _, x, y, z = axes
            cross = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
            for a, b in zip(cross, z):
                self.assertAlmostEqual(a, b)

    def test_spinning_parts_follow_the_shaft_and_the_others_stay(self):
        self.assertEqual(cp.hub_axes(0.0), cp.fup_axes(-86.65))
        self.assertEqual(cp.rotor_axes(0.0), cp.fup_axes(-99.65))
        self.assertEqual(cp.housing_axes(), cp.fdown_axes(-101.25))
        self.assertEqual(cp.button_axes(), cp.fdown_axes(-115.65))
        turned = cp.rotor_axes(36.0)
        want = frames.compose(poses.turn_axes(36.0), cp.fup_axes(-99.65))
        self.assertEqual(turned, want)
        # The turn keeps the axis: the origin stays on x = 0, z = SHAFT_Z.
        self.assertAlmostEqual(turned[0][0], 0.0)
        self.assertAlmostEqual(turned[0][2], SHAFT_Z)

    def test_stack_heights_in_world_y(self):
        # Local z of each reference plane: hub rim -96.05, rotor tips -107.65, button tips -107.65, bezel -108.15.
        hub = cp.hub_axes(0.0)
        self.assertAlmostEqual(frames.apply(hub, (0, 0, cp.hub_top()))[1], -96.05)
        rotor = cp.rotor_axes(0.0)
        self.assertAlmostEqual(frames.apply(rotor, (0, 0, 8.0))[1], -107.65)
        self.assertAlmostEqual(frames.apply(rotor, (0, 0, 1.6))[1], -101.25)
        button = cp.button_axes()
        self.assertAlmostEqual(frames.apply(button, (0, 0, 8.0))[1], -107.65)
        self.assertAlmostEqual(frames.apply(button, (0, 0, -2.5))[1], -118.15)
        housing = cp.housing_axes()
        self.assertAlmostEqual(frames.apply(housing, (0, 0, cp.housing_z(-108.15)))[1], -108.15)
        # The crown's teeth reach the rotor plate's nominal top.
        self.assertAlmostEqual(frames.apply(housing, (0, 0, 1.6))[1], -99.65)


class SectionTest(unittest.TestCase):
    def test_every_section_is_a_closed_loop_of_positive_area(self):
        for loop in (cp.hub_meridian(), cp.rotor_meridian(0.03), cp.housing_meridian(0.03), cp.button_meridian(0.03)):
            self.assertTrue(curves.loop_is_closed(loop))
            self.assertGreater(abs(curves.polygon_area(curves.loop_polygon(loop))), 1.0)

    def test_hub_volume(self):
        want = math.pi * (10.5 ** 2 * 3.5 + (10.5 ** 2 - 9.0 ** 2) * (9.4 - 3.5))
        self.assertAlmostEqual(revolved_volume(cp.hub_meridian()), want, places=6)

    def test_rotor_extents(self):
        pts = curves.loop_polygon(cp.rotor_meridian(0.03))
        self.assertEqual(min(p[1] for p in pts), -7.0)
        self.assertEqual(max(p[1] for p in pts), 0.03)
        self.assertEqual(max(p[0] for p in pts), 14.2)
        self.assertEqual(min(p[0] for p in pts), 3.0)
        # The skirt's bore is wider than the spring (7.0 across) by the gallery's 0.55 a side.
        self.assertAlmostEqual(cp.ROTOR_SKIRT_INNER - cp.SPRING_OUTSIDE_DIAMETER / 2, 0.55)

    def test_housing_extents(self):
        pts = curves.loop_polygon(cp.housing_meridian(0.03))
        self.assertAlmostEqual(min(p[1] for p in pts), -6.9)
        self.assertAlmostEqual(max(p[1] for p in pts), 14.75)
        self.assertEqual(max(p[0] for p in pts), 24.8)
        self.assertEqual(min(p[0] for p in pts), 11.55)
        # The flange stays inside the walls (x +-24.9).
        self.assertLess(cp.HOUSING_FLANGE_R, 24.9)

    def test_housing_base_is_six_thick_against_the_wall(self):
        self.assertAlmostEqual(cp.housing_z(cp.HOUSING_BASE_Y) - cp.housing_z(cp.HOUSING_BASE_Y - 6.0), 6.0)
        self.assertEqual(cp.HOUSING_BASE_Y, -86.5)

    def test_button_extents(self):
        pts = curves.loop_polygon(cp.button_meridian(0.03))
        self.assertEqual(min(p[1] for p in pts), -2.5)
        self.assertAlmostEqual(min(p[1] for p in pts if p[0] == 0.0 and p[1] > -2.5), 0.03 - 1.4)
        self.assertEqual(max(p[0] for p in pts), 11.0)

    def test_hub_keys_and_slots_sit_in_each_others_gaps(self):
        # A hub key is 2.0 wide, the rotor's slot 2.4: 0.2 a side (Tight).
        self.assertAlmostEqual(cp.ROTOR_SLOT_WIDTH, 2.4)
        self.assertAlmostEqual(cp.ROTOR_SLOT_FLOOR, 7.85)
        self.assertLess(cp.ROTOR_SLOT_FLOOR, cp.HUB_KEY_INNER)
        z0, z1 = cp.hub_key_span()
        self.assertAlmostEqual(z0, 3.0)
        self.assertAlmostEqual(z1, 9.4)

    def test_radial_box_turns_about_the_axis(self):
        loop = cp.radial_box_loop(8.05, 9.5, 2.0, 120.0)
        self.assertTrue(curves.loop_is_closed(loop))
        pts = curves.loop_polygon(loop)
        c, s = math.cos(math.radians(120)), math.sin(math.radians(120))
        want = [(8.05, -1.0), (9.5, -1.0), (9.5, 1.0), (8.05, 1.0)]
        for (x, y), (u, v) in zip(pts, want):
            self.assertAlmostEqual(x, u * c - v * s, places=6)
            self.assertAlmostEqual(y, u * s + v * c, places=6)
        self.assertAlmostEqual(curves.polygon_area(pts), 1.45 * 2.0)

    def test_three_keys_are_120_apart(self):
        self.assertEqual([cp.key_angle(i) for i in range(3)], [0.0, 120.0, 240.0])

    def test_d_bore_is_the_long_arc_and_a_flat_on_the_plus_v_side(self):
        loop = cp.d_bore_loop(2.55, 2.05)
        self.assertTrue(curves.loop_is_closed(loop))
        arc, line = loop
        self.assertEqual(line.start[1], 2.05)
        self.assertEqual(line.end[1], 2.05)
        w = math.sqrt(2.55 ** 2 - 2.05 ** 2)
        self.assertAlmostEqual(arc.start[0], -w)
        self.assertAlmostEqual(arc.end[0], w)
        # Counterclockwise from the upper left corner through -V to the upper right corner.
        area = curves.polygon_area(curves.loop_polygon(loop))
        self.assertGreater(area, math.pi * 2.55 ** 2 / 2)
        # The flat is on the shaft's stub flat side: the stub flat is 2.0 from the axis, the bore's 2.05 clears it.
        self.assertGreater(cp.BORE_STUB_FLAT, 2.0)


class SpringTest(unittest.TestCase):
    def test_pitch_and_radius(self):
        self.assertAlmostEqual(cp.spring_pitch(8.0), (8.0 - 0.6) / 6.5)
        self.assertAlmostEqual(cp.spring_centre_radius(), 3.2)

    def test_sections_run_six_and_a_half_turns(self):
        secs = cp.spring_sections(8.0, 8)
        self.assertEqual(len(secs), 6.5 * 8 + 1)
        self.assertEqual(secs[0], (0.0, 0.0, 3.2))
        angle, z, r = secs[-1]
        self.assertAlmostEqual(angle, 2340.0)
        self.assertAlmostEqual(z, 8.0 - 0.6)
        self.assertEqual(r, 3.2)

    def test_spring_spans_the_installed_length(self):
        # The wire's lowest point is half a wire under the first centre, its highest half a wire over the last.
        secs = cp.spring_sections(8.0, 8)
        span = secs[-1][1] + cp.SPRING_WIRE_DIAMETER
        self.assertAlmostEqual(span, 8.0)
        # The frame puts the lowest point on the hub's top face (y -90.15) and the top at the rotor's plate (-98.15).
        axes = cp.spring_axes(0.0)
        self.assertAlmostEqual(frames.apply(axes, (0, 0, -0.3))[1], -90.15)
        self.assertAlmostEqual(frames.apply(axes, (0, 0, secs[-1][1] + 0.3))[1], -98.15)

    def test_turns_are_spaced_by_the_pitch_and_clear_each_other(self):
        pitch = cp.spring_pitch(8.0)
        self.assertGreater(pitch, cp.SPRING_WIRE_DIAMETER)
        # The solid height is 4.5; at 8.0 the coil is not solid.
        self.assertGreater(8.0, cp.SPRING_SOLID_HEIGHT)

    def test_spring_fits_the_skirt_bore(self):
        self.assertLess(cp.SPRING_OUTSIDE_DIAMETER / 2, cp.ROTOR_SKIRT_INNER)
        self.assertLess(cp.SPRING_OUTSIDE_DIAMETER / 2, cp.HUB_WALL_INNER)


class TeethTest(unittest.TestCase):
    def rings(self):
        return (ct.rotor_inner_teeth(), ct.rotor_outer_teeth(), ct.crown_teeth(), ct.button_teeth())

    def test_ring_specs_follow_the_table(self):
        inner, outer, crown, button = self.rings()
        self.assertEqual((inner.r0, inner.r1, inner.h, inner.rise, inner.fall), (3.2, 11.0, 8.0, 3.5, 32.5))
        self.assertAlmostEqual(button.r0, 3.4)
        self.assertAlmostEqual(button.r1, 10.85)
        self.assertEqual((button.h, button.rise, button.fall), (8.0, 3.5, 32.5))
        self.assertEqual((outer.r0, outer.r1, outer.h, outer.rise, outer.fall), (12.8, 14.0, 1.6, 30.0, 6.0))
        self.assertAlmostEqual(crown.r1, 14.85)
        self.assertEqual((crown.h, crown.rise, crown.fall), (1.6, 30.0, 6.0))
        for ft in self.rings():
            self.assertEqual(ft.tip, 0.05)
            self.assertEqual(ft.plate, 0.03)
            self.assertAlmostEqual(ft.rise + ft.fall, 36.0)

    def test_no_tooth_wall_lies_on_a_plate_wall(self):
        # steps.md "Face teeth" 6: the rotor's plate reaches past its teeth, its bore lies inside them, the button's
        # teeth end inside the head, the crown's run into the tube.
        inner, outer, crown, button = self.rings()
        self.assertGreater(cp.ROTOR_PLATE_RADIUS, outer.r1)
        self.assertLess(cp.ROTOR_BORE_RADIUS, inner.r0)
        self.assertLess(button.r1, cp.BUTTON_RADIUS)
        self.assertGreater(crown.r1, cp.HOUSING_TUBE_INNER)
        self.assertLess(button.r0, cp.BUTTON_RADIUS)
        self.assertGreater(button.r0, cp.BUTTON_RECESS_R)

    def test_rings_nest_without_overlap(self):
        inner, outer, crown, _ = self.rings()
        self.assertLess(inner.r1, outer.r0)
        self.assertEqual(crown.r0, outer.r0)

    def test_shifts(self):
        self.assertAlmostEqual(ct.ROTOR_INNER_SHIFT, -3.5)
        self.assertAlmostEqual(ct.ROTOR_OUTER_SHIFT, -30.0)
        self.assertAlmostEqual(ct.BUTTON_SHIFT, 3.5)
        self.assertEqual(ct.CROWN_SHIFT, 0.0)

    def test_tooth_walls_are_helicoids_between_the_valley_and_the_peak(self):
        for ft in self.rings():
            # At the valley plane a tooth spans the whole 36 degrees, at the peak it is a point.
            self.assertAlmostEqual(ct.tooth_width(ft, 0.0), 36.0)
            self.assertAlmostEqual(ct.tooth_width(ft, ft.h), 0.0)
            # Its two ramps meet at the peak at `rise` degrees.
            self.assertAlmostEqual(ct.rising_edge(ft, 0.0, ft.h), ft.rise)
            self.assertAlmostEqual(ct.falling_edge(ft, 0.0, ft.h), ft.rise)
            # The tip's land: the tooth is cut back by `tip`, leaving a flat of 36 * tip / h degrees.
            self.assertAlmostEqual(ct.tooth_width(ft, ft.top), 36.0 * ft.tip / ft.h)
            # The root land: where the plate's top cuts the teeth, the neighbours are 36 * plate / h degrees apart.
            self.assertAlmostEqual(36.0 - ct.tooth_width(ft, ft.plate), 36.0 * ft.plate / ft.h)

    def test_the_prisms_cover_one_tooth(self):
        for ft in self.rings():
            for shift in (0.0, -3.5, 30.0):
                (rise_loop, rise_twist), (fall_loop, fall_twist) = ct.sweeps(ft, shift)
                self.assertAlmostEqual(rise_twist, ft.rise * ft.top / ft.h)
                self.assertAlmostEqual(fall_twist, -ft.fall * ft.top / ft.h)
                self.assertGreater(rise_twist, 0.0)
                self.assertLess(fall_twist, 0.0)
                for z in (0.0, ft.top / 2, ft.top):
                    t = z / ft.top
                    # The rising prism's start edge and the falling prism's end edge turn with the twist and are the
                    # tooth's ramps at that height.
                    self.assertAlmostEqual(shift + rise_twist * t, ct.rising_edge(ft, shift, z))
                    self.assertAlmostEqual(shift + 36.0 + fall_twist * t, ct.falling_edge(ft, shift, z))
                    # The other edge of each prism lies beyond the tooth, so it never clips it.
                    self.assertGreaterEqual(shift + ct.SECTOR_SPAN + rise_twist * t,
                                            ct.falling_edge(ft, shift, z) - 1e-9)
                    self.assertLessEqual(shift + 36.0 - ct.SECTOR_SPAN + fall_twist * t,
                                         ct.rising_edge(ft, shift, z) + 1e-9)

    def test_a_sector_is_a_closed_loop_with_ccw_arcs(self):
        for a0, a1 in ((0.0, 40.0), (-3.5, 36.5), (-34.0, 6.0)):
            loop = ct.sector_loop(3.2, 11.0, a0, a1)
            self.assertTrue(curves.loop_is_closed(loop))
            arcs = [c for c in loop if isinstance(c, curves.Arc)]
            self.assertEqual(len(arcs), 2)
            area = abs(curves.polygon_area(curves.loop_polygon(loop)))
            want = math.radians(a1 - a0) / 2 * (11.0 ** 2 - 3.2 ** 2)
            self.assertAlmostEqual(area, want, delta=want * 1e-4)

    def test_cap_angle_is_the_sector_centre_after_the_twist(self):
        ft = ct.rotor_inner_teeth()
        self.assertAlmostEqual(ct.cap_angle(ft, -3.5, True), -3.5 + ft.rise_twist + 20.0)
        self.assertAlmostEqual(ct.cap_angle(ft, -3.5, False), -3.5 + 36.0 + ft.fall_twist - 20.0)

    def test_tooth_volume_is_the_wedge_between_the_ramps(self):
        # Numeric integral of the tooth's slices (a sector of the tooth's width at each height), against the closed form:
        # the slice's width falls linearly from 36 degrees at z = 0 to 36 * tip / h at z = top.
        for ft in self.rings():
            n = 2000
            vol = 0.0
            for i in range(n):
                z = ft.top * (i + 0.5) / n
                vol += math.radians(ct.tooth_width(ft, z)) / 2 * (ft.r1 ** 2 - ft.r0 ** 2) * ft.top / n
            w0, w1 = 36.0, 36.0 * ft.tip / ft.h
            want = math.radians(w0 + w1) / 2 * (ft.r1 ** 2 - ft.r0 ** 2) / 2 * ft.top
            self.assertAlmostEqual(vol, want, delta=want * 1e-6)


class PressTurnTest(unittest.TestCase):
    def test_press_turn_matches_the_gallery(self):
        # The ramp's 32.5 degrees over the 8.0 tooth height, less the tip (0.05) and the root land (0.05): 4.0625 a mm.
        self.assertAlmostEqual(ct.press_turn(), 32.09375, places=5)
        self.assertAlmostEqual(ct.press_turn() - 29.55, 2.54375, places=5)
        self.assertAlmostEqual(36.0 - ct.press_turn(), 3.90625, places=5)


if __name__ == "__main__":
    unittest.main()
