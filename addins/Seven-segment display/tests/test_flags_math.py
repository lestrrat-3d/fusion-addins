"""The pure geometry of the flag mechanism : rotors, sliders and plates."""

import itertools
import math
import unittest

import _support  # noqa: F401

from gen import flags_common as fc
from gen import frames
from gen import flags_pivot as fv
from gen import flags_plates as fp
from gen import flags_rotor as fr
from gen import flags_slider as fs
from gen.curves import Arc, Line, loop_is_closed, loop_polygon, polygon_area
from gen.truth import SEGMENTS, lit, station


def _segments_cross(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return orient(a, b, c) * orient(a, b, d) < -1e-12 and orient(c, d, a) * orient(c, d, b) < -1e-12


def _simple(pts):
    """True when no two non-adjacent sides of the polygon cross."""
    n = len(pts)
    for i, j in itertools.combinations(range(n), 2):
        if j == i + 1 or (i == 0 and j == n - 1):
            continue
        if _segments_cross(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n]):
            return False
    return True


class CommonTest(unittest.TestCase):
    def test_rounded_loop_is_closed_and_removes_the_corner_area(self):
        loop = fc.rect_loop(0.0, 10.0, 0.0, 6.0, 1.0)
        self.assertTrue(loop_is_closed(loop))
        self.assertEqual(sum(isinstance(c, Arc) for c in loop), 4)
        area = polygon_area(loop_polygon(loop))
        self.assertAlmostEqual(area, 60.0 - 4 * (1.0 - math.pi / 4), places=3)

    def test_rounded_arcs_run_counterclockwise_and_join_their_lines(self):
        loop = fc.rounded_loop([(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (2.0, 4.0), (2.0, 2.0), (0.0, 2.0)], {4: 0.5, 0: 0.5})
        self.assertTrue(loop_is_closed(loop))
        for c in loop:
            if isinstance(c, Arc):
                a0 = math.atan2(c.start[1] - c.center[1], c.start[0] - c.center[0])
                a1 = math.atan2(c.end[1] - c.center[1], c.end[0] - c.center[0])
                self.assertLess((a1 - a0) % (2 * math.pi), math.pi)

    def test_round_longer_than_an_edge_is_refused(self):
        with self.assertRaises(ValueError):
            fc.rect_loop(0.0, 1.0, 0.0, 1.0, 2.0)

    def test_stadium(self):
        loop = fc.stadium_loop(1.0, 2.7, 0.7)
        self.assertTrue(loop_is_closed(loop))
        self.assertAlmostEqual(polygon_area(loop_polygon(loop)), 1.7 * 1.4 + math.pi * 0.49, places=3)

    def test_plan_maps_u_and_s(self):
        self.assertEqual(fc.plan(0, 2.0, 1.0), (2.0, 50.5))  # a: horizontal at y 49.5
        self.assertEqual(fc.plan(1, 2.0, 1.0), (23.75, 26.75))  # b: vertical at x 24.75, s = -x

    def test_flag_angle_at_unlit_and_lit_poses(self):
        for s in SEGMENTS:
            for digit in range(10):
                want = math.degrees(math.atan2((4.5 if lit(digit, s) else 0.0) - 2.625 + fc.raise_(s), 2.25))
                self.assertAlmostEqual(fc.flag_angle(s, 36.0 * digit), want, places=6, msg=(s, digit))

    def test_rotor_frames_are_right_handed_with_z_along_the_axis(self):
        for s in SEGMENTS:
            o, x, y, z = fc.rotor_axes(s, 0.0)
            cx, cy, horizontal = fc.segment_centre(s)
            self.assertEqual(o, (cx, cy, 124.0))
            self.assertEqual(z, (1.0, 0.0, 0.0) if horizontal else (0.0, 1.0, 0.0))
            self.assertEqual(y, (0.0, 0.0, 1.0))
            cross = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
            self.assertEqual(cross, z)

    def test_the_turn_is_about_the_rotor_axis(self):
        for s in SEGMENTS:
            _, _, _, z0 = fc.rotor_axes(s, 0.0)
            _, _, _, z1 = fc.rotor_axes(s, 37.0)
            for a, b in zip(z0, z1):
                self.assertAlmostEqual(a, b)


class RotorTest(unittest.TestCase):
    def test_outlines_are_simple_polygons(self):
        for name, pts in (("tipA", fr.tip_prism_a()), ("tipB", fr.tip_prism_b()), ("p1", fr.slab_p1()),
                          ("p2", fr.slab_p2())):
            self.assertTrue(_simple(pts), name)
        for s in SEGMENTS:
            for n in fr.notches(s):
                self.assertTrue(_simple(fr.notch_profile(n[0], n[1])), (s, n))

    def test_section_is_the_rounded_diamond(self):
        loop = fr.section_loop()
        self.assertTrue(loop_is_closed(loop))
        k = fc.ROTOR_HALF_WIDTH * math.sqrt(2)
        self.assertAlmostEqual(polygon_area(loop_polygon(loop)), 2 * k * k - 4 * 0.75 ** 2 * (1 - math.pi / 4), places=3)

    def test_notch_counts_per_type(self):
        self.assertEqual({s: len(fr.notches(s)) for s in SEGMENTS}, {0: 1, 1: 2, 2: 2, 3: 1, 4: 2, 5: 2, 6: 1})

    def test_pockets_lie_beyond_their_notches(self):
        for s in SEGMENTS:
            for n in fr.notches(s):
                loop, z0, length = fr.pocket(n)
                self.assertAlmostEqual(z0, n[1] - 0.9)
                self.assertAlmostEqual(z0 + length, n[2])
                self.assertTrue(loop_is_closed(loop))

    def test_pivot_bore_meridian_is_mirrored_and_simple(self):
        up, down = fr.pivot_bore_meridian(1.0), fr.pivot_bore_meridian(-1.0)
        self.assertEqual(sorted((r, -z) for r, z in down), sorted(up))
        self.assertTrue(_simple(up) and _simple(down))
        self.assertEqual(up[0], (0.0, 16.2))
        self.assertAlmostEqual(max(r for r, _ in up), fr.PIVOT_MOUTH_R + 0.2)
        # The wall of radius 0.9 runs from the floor round (u 16.95) to the countersink, which starts at 17.88 and meets
        # radius 1.395 at the end face 18.375.
        self.assertIn((0.9, 16.95), [(round(r, 9), round(z, 9)) for r, z in up])
        self.assertIn((0.9, round(18.375 - 0.495, 9)), [(round(r, 9), round(z, 9)) for r, z in up])
        self.assertAlmostEqual(min(z for _, z in up), 16.2)

    def test_pivot_roof_is_a_convex_gable_over_the_bore(self):
        pts, z0, length = fr.pivot_roof()
        self.assertTrue(_simple(pts))
        self.assertEqual((z0, round(z0 + length, 9)), (16.2, 18.575))
        t = 0.9 / math.sqrt(2)
        self.assertAlmostEqual(pts[1][0], t)
        self.assertAlmostEqual(pts[1][1], t)
        # The lower corner is on the axis; the gable is cut flat 1.00 from it, 0.5456 wide.
        self.assertEqual(pts[0], (0.0, 0.0))
        self.assertAlmostEqual(pts[2][1], 1.00)
        self.assertAlmostEqual(pts[2][0] - pts[3][0], 2 * (0.9 * math.sqrt(2) - 1.00))
        self.assertAlmostEqual(pts[2][0] - pts[3][0], 0.5456, places=3)
        lo, hi = fr.pivot_roof_axes(1.0), fr.pivot_roof_axes(-1.0)
        self.assertEqual((lo[0][2], hi[0][2]), (16.2, -18.575))
        self.assertAlmostEqual(lo[3][2], 1.0)

    def test_pivot_roof_cut_is_the_roof_turned_in_its_plane(self):
        pts, _, length = fr.pivot_roof()
        for sgn in (1.0, -1.0):
            xy, z0, cut_length = fr.pivot_roof_cut(sgn)
            self.assertEqual((z0, cut_length), (fr.pivot_roof_axes(sgn)[0][2], length))
            self.assertEqual(xy[0], (0.0, 0.0))
            # A turn keeps every side's length. The point (0, 1) of the roof frame (V, up in print) is the XY
            # direction (-1, -1)/sqrt 2.
            for i in range(len(pts)):
                j = (i + 1) % len(pts)
                self.assertAlmostEqual(math.dist(xy[i], xy[j]), math.dist(pts[i], pts[j]))
            top = xy[2]
            self.assertAlmostEqual(top[0], pts[2][0] * -math.sqrt(0.5) + pts[2][1] * -math.sqrt(0.5))
            self.assertAlmostEqual(top[1], pts[2][0] * math.sqrt(0.5) + pts[2][1] * -math.sqrt(0.5))

    def test_mouth_chamfer_applies_to_no_notch_at_this_size(self):
        # The gallery's test stays u0 > -15 and u0 + 15 < 0.8. Type B's first notch (u0 -14.1) ends 0.9 from the tip
        # slant, so none of the seven rotors takes the mouth chamfer; a notch at u0 -14.5 would.
        self.assertEqual([[fr.mouth_applies(n[0]) for n in fr.notches(s)] for s in SEGMENTS],
                         [[False], [False, False], [False, False], [False], [False, False], [False, False], [False]])
        self.assertTrue(fr.mouth_applies(-14.5))
        # The cutter's sections stay defined for a notch that takes it: the plane u - b = kk with kk = -14.1 - 0.7 + 5.625.
        (p1, ax1, z1, len1), (p3, ax3, z3, len3) = fr.mouth_prism_sections(-14.1)
        self.assertAlmostEqual(p1[0][1], -6.75 - 9.175)
        self.assertEqual((p1[0][0], p1[1]), (-6.75, (-6.75, -13.1)))
        self.assertAlmostEqual(p1[2][0], -13.1 + 9.175)
        self.assertTrue(_simple(p1) and _simple(p3))
        self.assertAlmostEqual(len1, 4.825 + 1.0)
        self.assertEqual((z3, len3), (-22.5, 45.0))
        for ax in (ax1, ax3):
            n = ax[3]
            self.assertAlmostEqual(sum(c * c for c in n), 1.0)


class PivotTest(unittest.TestCase):
    def test_pin_meridian_is_simple_and_ends_at_the_tip(self):
        pts = fv.pin_meridian()
        self.assertTrue(_simple(pts))
        self.assertEqual(pts[0], (0.0, 18.725))
        self.assertAlmostEqual(min(z for _, z in pts), 16.75)
        self.assertAlmostEqual(max(r for r, _ in pts), 1.05)
        self.assertAlmostEqual(fc.JOURNAL_RADIUS - fv.PIVOT_PIN_RADIUS, 0.2)  # the bore leaves the Tight minimum

    def test_block_and_pocket_dimensions(self):
        for got, want in zip(fv.block_dims(), (2.4, 2.95, 2.95, 0.675, 18.625, 21.625)):
            self.assertAlmostEqual(got, want)
        half, low, high, rad, u0, u1 = fv.pocket_dims()
        self.assertAlmostEqual(half, 2.45)
        self.assertAlmostEqual(high, 3.25)
        self.assertAlmostEqual(rad, 0.725)
        self.assertAlmostEqual(low, 3.0)
        self.assertAlmostEqual(u0, 17.625)
        self.assertAlmostEqual(u1, 21.675)
        # 0.05 of press on each face of the block, and 1.0 of cradle under the pocket (axis 124.0, cradle from 120.0).
        self.assertAlmostEqual(half - 2.4, 0.05)
        self.assertAlmostEqual(fc.ROTOR_AXIS_Z - low - 120.0, 1.0)

    def test_rounded_prism_sections_start_the_plan_prism_one_before(self):
        (sec, sa, z1, len1), (plan, pa, z2, len2) = fv.rounded_prism_sections(*fv.block_dims())
        self.assertAlmostEqual(z1, 18.625)
        self.assertAlmostEqual(len1, 4.0)
        self.assertEqual(z2, 0.0)
        self.assertAlmostEqual(len2, 7.9)
        self.assertTrue(loop_is_closed(sec) and loop_is_closed(plan))
        self.assertEqual(pa[3], (0.0, 1.0, 0.0))
        self.assertEqual(pa[0], (0.0, -3.95, 0.0))
        xs = [p[0] for p in loop_polygon(plan)]
        self.assertAlmostEqual(min(xs), 17.625)
        self.assertAlmostEqual(max(xs), 21.625)

    def test_segment_axes_put_the_block_at_each_end(self):
        for s in SEGMENTS:
            for sgn in fv.ENDS:
                ax = fv.segment_axes(s, sgn)
                tip = frames.apply(ax, (0.0, 0.0, fv.PIVOT_PIN_TIP))
                centre = fc.segment_centre(s)
                u = fc.rotor_frame(s)[3]
                self.assertAlmostEqual(tip[2], fc.ROTOR_AXIS_Z)
                along = (tip[0] - centre[0]) * u[0] + (tip[1] - centre[1]) * u[1]
                self.assertAlmostEqual(along, sgn * fv.PIVOT_PIN_TIP)

    def test_block_bounds(self):
        box = fv.block_bounds(6, 1.0)  # segment g, the +u end: u along +X
        self.assertEqual(tuple(round(v, 9) for v in box), (16.75, -2.4, 121.05, 21.625, 2.4, 126.95))
        box = fv.block_bounds(1, -1.0)  # segment b: u along +Y, s along -X, at (24.75, 24.75)
        self.assertEqual(tuple(round(v, 9) for v in box), (22.35, 3.125, 121.05, 27.15, 8.0, 126.95))


class SliderTest(unittest.TestCase):
    def test_every_slider_outline_is_closed_and_simple(self):
        for s in SEGMENTS:
            loop = fs.agd_loop() if fs.is_agd(s) else fs.bf_loop(s)
            self.assertTrue(loop_is_closed(loop), s)
            self.assertTrue(_simple(loop_polygon(loop)), s)
            self.assertGreater(polygon_area(loop_polygon(loop)), 0.0)
            self.assertGreater(max(p[1] for p in loop_polygon(loop)), 125.0)  # the blade's gable

    def test_tongue_hull_is_closed_and_simple(self):
        for s in SEGMENTS:
            t = fs.tongue_for(s)
            loop = fs.tongue_outline(t.sl, t.sr, t.sc, t.zp)
            self.assertTrue(loop_is_closed(loop), s)
            poly = loop_polygon(loop)
            self.assertTrue(_simple(poly), s)
            self.assertGreater(polygon_area(poly), 0.0)
            self.assertTrue(any(isinstance(c, Arc) for c in loop))
            self.assertTrue(_simple(fs.tongue_cutter(t.ue, t.zp)), s)

    def test_tongue_stations(self):
        self.assertEqual(fs.tongue_for(0).sc, station(0) + 2.25)
        self.assertEqual((fs.tongue_for(1).sl, fs.tongue_for(1).sc), (22.5, 22.5))
        self.assertEqual((fs.tongue_for(4).sl, fs.tongue_for(4).sc), (-27.0, -27.0))
        self.assertAlmostEqual(fs.tongue_for(1).zp, 121.575)
        self.assertAlmostEqual(fs.tongue_for(4).zp, 121.625)
        self.assertAlmostEqual(fs.tongue_for(0).hull_length, -2.85 + 5.6 + 5.25)

    def test_pins(self):
        self.assertTrue(_simple(fs.flag_pin_meridian()))
        self.assertAlmostEqual(max(z for _, z in fs.flag_pin_meridian()), 5.5)
        self.assertTrue(_simple(fs.groove_pin_meridian()))
        self.assertAlmostEqual(max(s for _, s in fs.groove_pin_meridian()), 3.0)

    def test_blade_gable_sits_in_the_top_plate_blade_hole(self):
        for s in SEGMENTS:
            if fs.is_agd(s):
                continue
            bl, br = fs.blade_x(s)
            h = fp.blade_hole(s, station(s))
            self.assertLess(h[0], bl)
            self.assertGreater(h[1], br)


class PlateTest(unittest.TestCase):
    def test_slots_are_closed_and_inside_the_plate(self):
        x0, x1, y0, y1 = fp.plate_rect()
        for s in SEGMENTS:
            loop = fp.slot_loop(station(s))
            self.assertTrue(loop_is_closed(loop))
            poly = loop_polygon(loop)
            self.assertTrue(all(x0 < x < x1 and y0 < y < y1 for x, y in poly), s)
            self.assertEqual(sum(isinstance(c, Arc) for c in loop), 6)

    def test_passages_hold_the_blade_holes_and_tubes_hold_them_too(self):
        for s in SEGMENTS:
            yi = station(s)
            p, h, t = fp.cradle_passage(s, yi), fp.blade_hole(s, yi), fp.tube_footprint(s, yi)
            self.assertTrue(p[0] < h[0] and h[1] < p[1] and p[2] < h[2] and h[3] < p[3], s)
            self.assertTrue(t[0] < h[0] and h[1] < t[1] and t[2] < h[2], s)
            self.assertLess(t[0], t[1])
            self.assertLess(t[2], t[3])

    def test_windows_are_octagons_clear_of_each_other(self):
        boxes = []
        for s in SEGMENTS:
            loop = fp.window_loop(s)
            self.assertEqual(len(loop), 8)
            self.assertTrue(loop_is_closed(loop))
            poly = loop_polygon(loop)
            self.assertTrue(_simple(poly))
            boxes.append((min(p[0] for p in poly), max(p[0] for p in poly), min(p[1] for p in poly),
                          max(p[1] for p in poly)))
        for a, b in itertools.combinations(boxes, 2):
            if a[1] > b[0] and b[1] > a[0] and a[3] > b[2] and b[3] > a[2]:
                self.fail(f"windows overlap in plan: {a} {b}")

    def test_bore_meridian(self):
        pts = fp.bore_meridian()
        self.assertEqual(pts[0], (0.0, -18.625))
        self.assertEqual(pts[-1], (0.0, 18.625))
        move = 2.748 + math.sqrt(2) * 5.177 - 0.5 * 0.4 * math.sqrt(3)
        self.assertAlmostEqual(pts[-2][0], 2.461 + move - math.sqrt(2) * (18.625 - 12.5))
        self.assertEqual(pts[-2][1], 18.625)
        self.assertTrue(all(r >= 0 for r, _ in pts))
        self.assertAlmostEqual(max(r for r, _ in pts), fp.BORE_RADIUS)
        self.assertTrue(_simple(pts))

    def test_bore_frames_put_z_on_the_rotor_axis(self):
        for s in SEGMENTS:
            o, _, _, z = fp.bore_axes(s, 124.0)
            self.assertEqual(z, fc.rotor_frame(s)[3])
            self.assertEqual(o, fc.rotor_frame(s)[0])

    def test_cone_meets_the_hole_at_the_far_side_of_the_plate(self):
        pts = fp.cone_meridian(124.0)
        self.assertAlmostEqual(pts[1][0], 2.2)
        self.assertAlmostEqual(pts[2][0], 3.2)
        # 45 degrees: the radius grows as fast as z. At z 124.0 it is hole + depth; at z 123.2 it is the hole.
        slope = (pts[2][0] - pts[1][0]) / (pts[2][1] - pts[1][1])
        self.assertAlmostEqual(slope, 1.0)

    def test_rooted_sections_are_simple(self):
        for sec in (fp.rooted_box_sections(0, 5, 0, 4, 77.4, 82.85, 0.1, 0.5),
                    fp.rooted_post_sections(0, 5, 0, 4, 58.0, 79.15, 0.1, 0.5)):
            for pts, _, length in sec:
                self.assertTrue(_simple(pts))
                self.assertGreater(length, 0)

    def test_plate_levels(self):
        self.assertAlmostEqual(fp.TOP_FROM, 124.25)
        self.assertAlmostEqual(fp.TOP_FROM + fp.TOP_THICK, fc.FLAG_FACE_Z + 0.0, places=6)
        self.assertAlmostEqual(fp.PLATE_FROM, -74.0)
        self.assertAlmostEqual(fp.PLATE_TO, 64.25)


if __name__ == "__main__":
    unittest.main()
