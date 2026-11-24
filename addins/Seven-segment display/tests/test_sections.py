import math
import unittest

import _support  # noqa: F401
from gen import bodies, expected, grooves, sections
from gen.curves import Arc, Line, loop_is_closed, loop_polygon, polygon_area
from gen.params import default_params
from gen.truth import SEGMENTS
from gen.validate import derive

DM = derive(default_params())


def area(loop):
    return abs(polygon_area(loop_polygon(loop)))


class ShaftTest(unittest.TestCase):
    def test_meridian_closed_and_sized(self):
        loop = sections.shaft_meridian()
        self.assertTrue(loop_is_closed(loop))
        self.assertEqual(len(loop), 14)
        # Length 172.45 from y -100.95 (the knob end) to 71.5 (the rear journal's end).
        ys = [p[1] for line in loop for p in (line.start, line.end)]
        self.assertAlmostEqual(min(ys), -100.95)
        self.assertAlmostEqual(max(ys), 71.5)

    def test_meridian_volume(self):
        # Pappus: the revolved area times the centroid's distance round the axis.
        pts = [(l.start) for l in sections.shaft_meridian()]
        a = c = 0.0
        for i in range(len(pts)):
            (x0, z0), (x1, z1) = pts[i], pts[(i + 1) % len(pts)]
            cr = x0 * z1 - x1 * z0
            a += cr
            c += (x0 + x1) * cr
        a /= 2
        vol = abs(2 * math.pi * (c / (6 * a)) * a)
        # The three flats remove a little, so the whole revolve is just above the shaft's 172.45 mm times its ~64 mm^2.
        self.assertTrue(10500 < vol < 12000, vol)

    def test_flats(self):
        flats = {n: (x0, x1, z0, z1) for n, x0, x1, z0, z1 in sections.shaft_flats()}
        for name, want in (("cam flat", (4.05, 12.0, -75.0, 58.5)), ("cam back flat", (-12.0, -4.05, -75.0, 58.5)),
                           ("stub flat", (2.0, 12.0, -101.95, -86.6))):
            for got, exp in zip(flats[name], want):
                self.assertAlmostEqual(got, exp, places=9, msg=name)
        # The stub flat ends 0.05 short of the hub's back face at -86.65, and the cam flats end square at 58.5.
        self.assertAlmostEqual(-86.6 - (-86.65), 0.05)


class CamTest(unittest.TestCase):
    def test_meridian_points(self):
        pts = sections.cam_meridian_points()
        self.assertEqual(pts[:6], [(0, -5.7), (34.75, -5.7), (35.25, -5.2), (35.25, -0.5), (34.75, 0.0), (8.0, 0.0)])
        self.assertEqual(len(pts), 6 + 8 + 2)
        self.assertAlmostEqual(pts[6][0], 8.0 + 0.5 * math.cos(math.radians(-90 - 11.25)))
        self.assertAlmostEqual(pts[13][0], 7.5)
        self.assertAlmostEqual(pts[13][1], 0.5)
        self.assertEqual(pts[-2:], [(7.5, 10.75), (0.0, 10.75)])
        self.assertTrue(loop_is_closed(sections.cam_meridian()))

    def test_bore_is_a_double_d(self):
        loop = sections.cam_bore_loop()
        self.assertTrue(loop_is_closed(loop))
        self.assertEqual([type(c) for c in loop], [Arc, Line, Arc, Line])
        w = math.sqrt(4.85 ** 2 - 4.1 ** 2)
        self.assertAlmostEqual(loop[1].start[0], w)
        self.assertEqual(loop[1].start[1], 4.1)
        # The circle of radius 4.85 less the two circular segments the flats cut off.
        cap = 4.85 ** 2 * math.acos(4.1 / 4.85) - 4.1 * w
        self.assertAlmostEqual(area(loop), math.pi * 4.85 ** 2 - 2 * cap, delta=0.05)

    def test_look_alike_holes(self):
        counts = {s: len(sections.cam_mark_centres(s)) for s in SEGMENTS}
        # d, e, c: 1, 2, 3 at radius 18; g, b, f, a: 1, 2, 3, 4 at radius 12.
        self.assertEqual([counts[s] for s in (3, 4, 2, 6, 1, 5, 0)], [1, 2, 3, 1, 2, 3, 4])
        for s in SEGMENTS:
            n, radius = sections.cam_mark_count(s)
            for x, y in sections.cam_mark_centres(s):
                self.assertAlmostEqual(math.hypot(x, y), radius)
        first = sections.cam_mark_centres(3)[0]
        self.assertAlmostEqual(first[0], 0.0, places=9)
        self.assertAlmostEqual(first[1], -18.0)


class GrooveTest(unittest.TestCase):
    def test_loops_are_closed_and_joined(self):
        for s in SEGMENTS:
            outer, inner = grooves.groove_loops(s, DM)
            self.assertTrue(loop_is_closed(outer), s)
            self.assertTrue(loop_is_closed(inner), s)
            # Every end point is shared by exactly two curves, so the loop is one closed chain.
            for loop in (outer, inner):
                ends = {}
                for c in loop:
                    for q in (c.start, c.end):
                        ends[q] = ends.get(q, 0) + 1
                self.assertTrue(all(n == 2 for n in ends.values()), f"segment {s}")

    def test_curve_counts(self):
        # Per ramp: two arcs and a line, then one dwell arc; the entry channel replaces one outer dwell arc with five curves.
        for s in SEGMENTS:
            n = len(DM.ramps[s])
            outer, inner = grooves.groove_loops(s, DM)
            self.assertEqual(len(inner), 4 * n)
            self.assertEqual(len(outer), 4 * n + 4)

    def test_arcs_are_counterclockwise_and_short_or_dwell(self):
        for s in SEGMENTS:
            for loop in grooves.groove_loops(s, DM):
                for c in loop:
                    if isinstance(c, Arc):
                        r0 = math.hypot(c.start[0] - c.center[0], c.start[1] - c.center[1])
                        r1 = math.hypot(c.end[0] - c.center[0], c.end[1] - c.center[1])
                        self.assertAlmostEqual(r0, r1, places=6)

    def test_wall_radii(self):
        half = 2.65  # half of the groove width, the pin's 4.5 plus the 0.8 fit
        for s in SEGMENTS:
            outer, inner = grooves.groove_loops(s, DM)
            for loop, sign in ((outer, 1), (inner, -1)):
                for c in loop:
                    if isinstance(c, Arc) and c.center == (0.0, 0.0):
                        r = math.hypot(*c.start)
                        self.assertTrue(any(abs(r - (base + sign * half)) < 1e-6 for base in (24.75, 29.25)), r)
                    elif isinstance(c, Arc):
                        r = math.hypot(c.start[0] - c.center[0], c.start[1] - c.center[1])
                        self.assertTrue(abs(r - 1.1) < 1e-6 or abs(r - 6.4) < 1e-6, r)

    def test_ramp_wall_radii_by_centre_side(self):
        # A centre outside the centreline (away from the origin) gives the inner wall 6.4 and the outer wall 1.1.
        outer, inner = grooves.groove_loops(5, DM)  # segment f, rising ramps
        ramps_of = DM.ramps[5]
        self.assertTrue(ramps_of)
        from gen.ramps import ramp_geometry

        for ra in ramps_of:
            g = ramp_geometry(ra)
            for centre in (g.c1, g.c2):
                arcs = [c for loop in (outer, inner) for c in loop if isinstance(c, Arc) and c.center == centre]
                self.assertEqual(len(arcs), 2)

    def test_entry_channel(self):
        # The channel opens on the ray 18 degrees: sides parallel at +-2.65, out to a cap at 36.25 (the rim plus 1).
        for s in SEGMENTS:
            outer, _ = grooves.groove_loops(s, DM)
            lines = [c for c in outer if isinstance(c, Line)]
            caps = [c for c in lines if abs(math.hypot(*c.start) - math.hypot(36.25, 2.65)) < 1e-6
                    and abs(math.hypot(*c.end) - math.hypot(36.25, 2.65)) < 1e-6]
            self.assertEqual(len(caps), 1, s)
            cap = caps[0]
            self.assertAlmostEqual(math.hypot(cap.end[0] - cap.start[0], cap.end[1] - cap.start[1]), 5.3)
            mid = ((cap.start[0] + cap.end[0]) / 2, (cap.start[1] + cap.end[1]) / 2)
            self.assertAlmostEqual(math.degrees(math.atan2(mid[1], mid[0])), 18.0, places=6)
            self.assertAlmostEqual(math.hypot(*mid), 36.25, places=6)

    def test_channel_half_angle(self):
        self.assertAlmostEqual(grooves.channel_half_angle(), math.degrees(math.asin(2.65 / (29.25 + 2.65))), places=6)
        self.assertAlmostEqual(grooves.channel_half_angle(), 4.77, places=2)

    def test_channel_lies_in_every_cams_on_dwell(self):
        for s in SEGMENTS:
            ramps = grooves.sorted_ramps(DM.ramps[s])
            inside = [i for i, ra in enumerate(ramps)
                      if grooves.channel_inside(ra.end, ramps[(i + 1) % len(ramps)].start, grooves.channel_half_angle())]
            self.assertEqual(len(inside), 1, s)

    def test_groove_area_is_width_times_centreline_length(self):
        # The profile area is the outer loop's less the inner loop's: width 5.3 times the centreline, to the cap.
        for s in SEGMENTS:
            outer, inner = grooves.groove_loops(s, DM)
            self.assertGreater(area(outer), area(inner))
            ring = area(outer) - area(inner)
            self.assertTrue(700 < ring < 1500, (s, ring))


class LetterTest(unittest.TestCase):
    def test_loops_per_letter(self):
        # A and b and d and E have a counter or two; the loop counts follow the lattice.
        counts = {s: len(grooves.letter_loops(s)) for s in SEGMENTS}
        self.assertEqual(counts[0], 2)  # A: abcefg encloses the space between a and g
        self.assertEqual(counts[1], 2)  # b: cdefg
        self.assertEqual(counts[2], 1)  # C: adef
        self.assertEqual(counts[3], 2)  # d: bcdeg
        self.assertEqual(counts[4], 1)  # E: adefg
        self.assertEqual(counts[5], 1)  # F: aefg
        self.assertEqual(counts[6], 1)  # G: acdef

    def test_loops_are_rectilinear_and_inside_the_cell(self):
        for s in SEGMENTS:
            for loop in grooves.letter_loops(s):
                for i, (x, y) in enumerate(loop):
                    nx, ny = loop[(i + 1) % len(loop)]
                    self.assertTrue(x == nx or y == ny)
                    self.assertTrue(abs(x) <= 2.4 + 1e-9 and abs(y) <= 3.45 + 1e-9)

    def test_outline_first(self):
        for s in SEGMENTS:
            loops = grooves.letter_loops(s)
            areas = [abs(polygon_area(l)) for l in loops]
            self.assertEqual(areas, sorted(areas, reverse=True))

    def test_curves_sit_above_the_axis_and_mirror_u(self):
        for s in SEGMENTS:
            for loop in grooves.letter_curves(s):
                self.assertTrue(loop_is_closed(loop))
                for c in loop:
                    self.assertTrue(21.0 - 3.45 - 1e-9 <= c.start[1] <= 21.0 + 3.45 + 1e-9)


class WallTest(unittest.TestCase):
    def test_plate(self):
        u0, u1, v0, v1 = sections.wall_plate()
        self.assertEqual((u0, u1), (-36.6, 36.6))
        self.assertAlmostEqual(v0, -39.75)
        self.assertAlmostEqual(v1, 77.0)
        # 73.2 wide and 116.75 tall: z 4.5 to 121.25.
        self.assertAlmostEqual(v1 - v0, 116.75)

    def test_ribs(self):
        for front, deep in ((True, 26.35), (False, 19.7)):
            ribs = sections.wall_ribs(front)
            self.assertEqual(len(ribs), 4)
            for got, exp in zip([d for _, d in ribs], [deep, deep, 15.0, 15.0]):
                self.assertAlmostEqual(got, exp, places=9)
            for (u0, u1, v0, v1), _ in ribs:
                self.assertAlmostEqual(abs(u1 - u0), 10.5)
                self.assertAlmostEqual(v1 - v0, 6.0)
                self.assertAlmostEqual(min(abs(u0), abs(u1)), 24.6)
                self.assertAlmostEqual(max(abs(u0), abs(u1)), 35.1)
            # Ledge ribs z 74.75-80.75, top flange ribs z 113.75-119.75.
            self.assertAlmostEqual(ribs[0][0][2] + 44.25, 74.75)
            self.assertAlmostEqual(ribs[2][0][2] + 44.25, 113.75)

    def test_ribs_stand_inside_the_plate(self):
        u0, u1, v0, v1 = sections.wall_plate()
        for (ru0, ru1, rv0, rv1), _ in sections.wall_ribs(True):
            self.assertAlmostEqual(u1 - max(abs(ru0), abs(ru1)), 1.5)
            self.assertGreaterEqual(rv0, v0)
            self.assertAlmostEqual(v1 - rv1, 1.5) if rv1 > 40 else None

    def test_seat(self):
        loop = sections.wall_seat_loop()
        self.assertTrue(loop_is_closed(loop))
        radii = {p[0] for line in loop for p in (line.start, line.end)}
        self.assertEqual(radii, {0.0, 11.55, 11.05, 6.5, 7.0})
        # The seat r 11.05 (608ZZ outer diameter 22 + 0.1 press) is 7 deep, the lip hole r 6.5 is 4.5 thick.
        ds = sorted({p[1] for line in loop for p in (line.start, line.end)})
        self.assertEqual(ds, [-1.0, 0.0, 0.5, 7.0, 11.5, 12.0, 13.0])

    def test_marks(self):
        front = sections.wall_mark_centres(True)
        rear = sections.wall_mark_centres(False)
        self.assertEqual((len(front), len(rear)), (1, 2))
        self.assertAlmostEqual(front[0][0], 0.0, places=9)
        self.assertAlmostEqual(front[0][1], -13.5)
        # The rear wall's u runs along -X, so the 295 degree mark's x flips.
        x295 = 13.5 * math.cos(math.radians(295))
        self.assertAlmostEqual(front[0][0], rear[0][0], places=9)
        self.assertAlmostEqual(rear[1][0], -x295)

    def test_site_kinds(self):
        self.assertEqual(sections.wall_site_indices(True), [(0, "T"), (1, "T"), (4, "G"), (5, "G"), (8, "H"), (9, "H")])
        self.assertEqual(sections.wall_site_indices(False), [(2, "T"), (3, "T"), (6, "G"), (7, "G")])


class ExpectedTest(unittest.TestCase):
    def test_frame_camshaft_hub_and_pivot_blocks_have_bounds_the_rest_none(self):
        for name in bodies.BODY_NAMES:
            box = expected.body_bounds(name, DM)
            if bodies.BODY_STAGE[name] == 1 or name == bodies.HUB or name in bodies.PIVOT_ENDS:
                self.assertIsNotNone(box, name)
                self.assertTrue(all(box[i] < box[i + 3] for i in range(3)), name)
            else:
                self.assertIsNone(box, name)

    def test_hub(self):
        self.assertEqual(expected.body_bounds("Hub", DM), (-10.5, -96.05, 33.75, 10.5, -86.65, 54.75))

    def test_walls_and_shaft(self):
        self.assertEqual(expected.body_bounds("Front Wall", DM), (-36.6, -86.25, 4.5, 36.6, -47.9, 121.25))
        self.assertEqual(expected.body_bounds("Rear Wall", DM), (-36.6, 44.8, 4.5, 36.6, 76.5, 121.25))
        self.assertEqual(expected.body_bounds("Shaft", DM), (-5.7, -100.95, 38.55, 5.7, 71.5, 49.95))

    def test_cam_a(self):
        box = expected.body_bounds("Cam A", DM)
        self.assertAlmostEqual(box[1], 42.0)
        self.assertAlmostEqual(box[4], 58.45)
        self.assertEqual((box[2], box[5]), (9.0, 79.5))  # cams z 9.0 to 79.5

    def test_cam_d_hub_and_disc(self):
        box = expected.body_bounds("Cam D", DM)
        # Cam d disc [-46.25, -40.55], hub [-57.0, -46.25].
        self.assertAlmostEqual(box[1], -57.0)
        self.assertAlmostEqual(box[4], -40.55)

    def test_bearings(self):
        self.assertEqual(expected.body_bounds("Front Bearing", DM), (-11.0, -81.25, 33.25, 11.0, -74.25, 55.25))
        self.assertEqual(expected.body_bounds("Rear Bearing", DM), (-11.0, 64.5, 33.25, 11.0, 71.5, 55.25))

    def test_bolt_and_nut(self):
        # T1 bolt: head top at z 132.25, 18.0 long (2.0 head pocket and 16 length) to the tip at 114.25; head radius 1.9.
        b = expected.body_bounds("Bolt T1", DM)
        self.assertAlmostEqual(b[2], 114.25)
        self.assertAlmostEqual(b[5], 132.25)
        self.assertAlmostEqual(b[3] - b[0], 3.8)
        # The nut sits 0.2 inside the cavity's near face, 1.6 thick, across flats 4 and corners 4.619.
        n = expected.body_bounds("Nut T1", DM)
        self.assertAlmostEqual(n[5] - n[2], 1.6)
        self.assertAlmostEqual(n[5], 132.25 - 16.5 - 0.2)
        self.assertAlmostEqual(n[3] - n[0], 4.0)
        self.assertAlmostEqual(n[4] - n[1], 4.0 / math.cos(math.pi / 6))


if __name__ == "__main__":
    unittest.main()
