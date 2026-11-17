import collections
import math
import unittest

import _support  # noqa: F401
from gen import measure, sections
from gen.constants import EAR_RADIUS, TEETH
from gen.curves import Arc, Line, loop_polygon
from gen.params import COUNTER_CLOCKWISE, Params, default_params
from gen.validate import derive


def assert_closed(case, loop):
    """Every endpoint is shared by exactly two curves, and each arc's ends lie on one circle about its centre."""
    ends = collections.Counter()
    for c in loop:
        ends[c.start] += 1
        ends[c.end] += 1
        if isinstance(c, Arc):
            case.assertAlmostEqual(math.dist(c.center, c.start), math.dist(c.center, c.end), places=9)
    case.assertEqual(set(ends.values()), {2})


class LoopsTest(unittest.TestCase):
    def setUp(self):
        self.dm = derive(default_params())

    def test_every_loop_is_closed(self):
        for name, loop in (
            ("hub", sections.hub_outline(self.dm)), ("hub mirrored", sections.layout(sections.hub_outline(self.dm), -1)),
            ("ring", sections.ring_outline(self.dm)), ("tooth", sections.tooth_loop(self.dm)),
            ("tooth mirrored", sections.layout(sections.tooth_loop(self.dm), -1)), ("bore", sections.bore_loop(self.dm)),
            ("ring back", sections.ring_back_tool(self.dm)), ("ring front", sections.ring_front_tool(self.dm)),
            ("back plate tool", sections.back_plate_tool(self.dm)), ("cover tool", sections.cover_tool(self.dm)),
        ):
            with self.subTest(loop=name):
                assert_closed(self, loop)

    def test_curve_counts(self):
        self.assertEqual(len(sections.hub_outline(self.dm)), 27)  # 9 curves per pawl
        self.assertEqual(len(sections.ring_outline(self.dm)), 18)  # 6 per ear
        self.assertEqual(len(sections.tooth_loop(self.dm)), 3 * TEETH)  # round, lock face and ramp per tooth

    def test_mirror_swaps_arc_ends_and_keeps_the_area(self):
        outline = sections.hub_outline(self.dm)
        mirrored = sections.mirror_loop(outline)
        self.assertEqual(sections.layout(outline, 1), list(outline))
        self.assertAlmostEqual(measure.loop_area(outline), measure.loop_area(mirrored), places=9)
        for a, b in zip(outline, mirrored):
            if isinstance(a, Arc):
                self.assertEqual((b.center, b.start, b.end), ((-a.center[0], a.center[1]), (-a.end[0], a.end[1]),
                                                              (-a.start[0], a.start[1])))
            else:
                self.assertEqual((b.start, b.end), ((-a.start[0], a.start[1]), (-a.end[0], a.end[1])))
        # An arc stays counter-clockwise after the mirror: its polygon area keeps the sign flipped only by the walk.
        self.assertAlmostEqual(abs(sum(1 for _ in mirrored)), len(outline))


class RingTest(unittest.TestCase):
    def setUp(self):
        self.dm = derive(default_params())

    def test_ring_extent_is_the_gallerys(self):
        x0, y0, x1, y1 = measure.loop_bounds(sections.ring_outline(self.dm))
        self.assertAlmostEqual(x0, -22.806, places=3)
        self.assertAlmostEqual(x1, 22.806, places=3)
        self.assertAlmostEqual(y0, -19.1, places=3)
        self.assertAlmostEqual(y1, 25.7, places=3)

    def test_grown_ring_extent_matches_the_decad_bounds(self):
        # Bounds read from decad builds of the gallery model at 608ZZ, c 0.05 and 0.5.
        for c, want in ((0.05, (-23.4789, -19.8761, 23.4789, 26.4761)), (0.5, (-23.8844, -20.3436, 23.8844, 26.9450))):
            dm = derive(Params(shaft="608ZZ", bore_clearance=c))
            got = measure.loop_bounds(sections.ring_outline(dm))
            for a, b in zip(got, want):
                self.assertAlmostEqual(a, b, delta=0.002)

    def test_ear_end_rounds_and_sides(self):
        for dm in (self.dm, derive(Params(shaft="608ZZ", bore_clearance=0.5))):
            for c in sections.ear_centers(dm):
                self.assertAlmostEqual(math.hypot(*c), dm.ear_circle)
            arcs = [c for c in sections.ring_outline(dm) if isinstance(c, Arc) and math.dist(c.center, (0.0, 0.0)) > 20]
            ends = [a for a in arcs if abs(math.dist(a.center, a.start) - EAR_RADIUS) < 1e-9]
            self.assertEqual(len(ends), 3)
            for a in ends:  # a half circle
                sweep = math.atan2(a.end[1] - a.center[1], a.end[0] - a.center[0]) - math.atan2(
                    a.start[1] - a.center[1], a.start[0] - a.center[0])
                self.assertAlmostEqual(abs(sweep) % (2 * math.pi), math.pi, places=9)

    def test_fillets_have_the_ear_round(self):
        rounds = [c for c in sections.ring_outline(self.dm)
                  if isinstance(c, Arc) and abs(math.dist(c.center, c.start) - 1.5) < 1e-9]
        self.assertEqual(len(rounds), 6)

    def test_tooth_loop_radii_and_pitch(self):
        for dm in (self.dm, derive(Params(shaft="608ZZ", bore_clearance=0.5))):
            loop = sections.tooth_loop(dm)
            locks = [c for c in loop if isinstance(c, Line) and abs(math.hypot(*c.end) - dm.tooth_tip) < 1e-9]
            self.assertEqual(len(locks), TEETH)
            for c in locks:  # a lock face lies on a radial line
                self.assertAlmostEqual(c.start[0] * c.end[1] - c.start[1] * c.end[0], 0.0, places=9)
            angles = sorted(math.degrees(math.atan2(c.end[1], c.end[0])) % 360 for c in locks)
            for a, b in zip(angles, angles[1:] + [angles[0] + 360]):
                self.assertAlmostEqual(b - a, 20.0, places=6)
            radii = [math.hypot(*p) for p in loop_polygon(loop)]
            self.assertAlmostEqual(min(radii), dm.tooth_tip, places=6)
            self.assertLess(max(radii), dm.tooth_root)

    def test_ramp_line_is_the_derived_one(self):
        for dm in (self.dm, derive(Params(shaft="608ZZ", bore_clearance=0.5))):
            ramps = [c for c in sections.tooth_loop(dm) if isinstance(c, Line)
                     and abs(math.hypot(*c.start) - dm.tooth_tip) < 1e-9
                     and abs(math.hypot(*c.start) - math.hypot(*c.end)) > 0.5]
            self.assertEqual(len(ramps), TEETH)
            for r in ramps:
                dx, dy = r.end[0] - r.start[0], r.end[1] - r.start[1]
                dist = abs(r.start[0] * dy - r.start[1] * dx) / math.hypot(dx, dy)
                self.assertAlmostEqual(dist, dm.ramp_distance, places=9)


class HubTest(unittest.TestCase):
    def face_area(self, **kw):
        dm = derive(Params(**kw))
        return (measure.loop_area(sections.hub_outline(dm)) - measure.loop_area(sections.bore_loop(dm))
                - 3 * measure.circle_area(1.3))

    def test_face_areas_of_instructions(self):
        # instructions.md, "Surface edge finishing": the 605ZZ face runs 413.9 to 406.1 over c 0.05 to 0.5, and the grown
        # 8 mm faces 441.0 (608ZZ-gearbox, c 0.05) to 466.7 (608ZZ, c 0.5). Every hub's faces are over 400 mm^2.
        self.assertAlmostEqual(self.face_area(), 413.9, delta=0.1)
        self.assertAlmostEqual(self.face_area(bore_clearance=0.5), 406.1, delta=0.1)
        self.assertAlmostEqual(self.face_area(shaft="608ZZ-gearbox"), 441.0, delta=0.1)
        self.assertAlmostEqual(self.face_area(shaft="608ZZ", bore_clearance=0.5), 466.7, delta=0.1)

    def test_head_tip_and_arm_radii(self):
        dm = derive(default_params())
        radii = [math.hypot(*p) for p in loop_polygon(sections.hub_outline(dm))]
        self.assertAlmostEqual(max(radii), dm.head_reach, places=3)
        self.assertAlmostEqual(min(radii), dm.core_radius, places=2)

    def test_pawls_are_120_degrees_apart(self):
        dm = derive(default_params())
        outline = sections.hub_outline(dm)
        flank_ends = sorted(math.degrees(math.atan2(c.end[1], c.end[0])) % 360 for c in outline
                            if isinstance(c, Arc) and c.center == (0.0, 0.0) and abs(math.hypot(*c.start) - dm.arm_outer) < 1e-9)
        self.assertEqual(len(flank_ends), 3)
        for a, b in zip(flank_ends, flank_ends[1:] + [flank_ends[0] + 360]):
            self.assertAlmostEqual(b - a, 120.0, places=6)

    def test_mirrored_hub_has_the_head_on_the_other_side(self):
        dm = derive(Params(freewheel=COUNTER_CLOCKWISE))
        ccw = sections.layout(sections.hub_outline(dm), dm.sign)
        cw = sections.layout(sections.hub_outline(dm), -dm.sign)
        top_ccw = max(loop_polygon(ccw), key=lambda p: p[1])
        top_cw = max(loop_polygon(cw), key=lambda p: p[1])
        self.assertGreater(top_ccw[0], 0)  # the head's tip leans toward +x in the counter-clockwise layout
        self.assertAlmostEqual(top_cw[0], -top_ccw[0], places=6)


class FitTest(unittest.TestCase):
    def test_heads_sit_0_40_from_the_ring_in_both_directions(self):
        # instructions.md fit R5: each head to its tooth gap, seated, modeled at 0.40 (REGULAR_FIT). The same gap is
        # the least distance between the hub's outline and the ring's tooth loop, which a wrong mirror would break.
        step = math.radians(1.0)
        for freewheel, shaft in (("Clockwise", "605ZZ"), ("CounterClockwise", "605ZZ"), ("Clockwise", "608ZZ")):
            with self.subTest(freewheel=freewheel, shaft=shaft):
                dm = derive(Params(freewheel=freewheel, shaft=shaft))
                hub = loop_polygon(sections.layout(sections.hub_outline(dm), dm.sign), step)
                tooth = loop_polygon(sections.layout(sections.tooth_loop(dm), dm.sign), step)
                best = math.inf
                for p in hub:
                    for i, a in enumerate(tooth):
                        b = tooth[(i + 1) % len(tooth)]
                        dx, dy = b[0] - a[0], b[1] - a[1]
                        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
                        best = min(best, math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy))
                self.assertAlmostEqual(best, 0.40, delta=0.005)


class BoreTest(unittest.TestCase):
    def test_d_bore(self):
        dm = derive(default_params())
        arc, flat = sections.bore_loop(dm)
        self.assertEqual(arc.center, (0.0, 0.0))
        self.assertAlmostEqual(flat.start[1], dm.bore_flat)
        self.assertAlmostEqual(flat.end[1], dm.bore_flat)
        self.assertAlmostEqual(math.hypot(*arc.start), dm.bore_radius)
        self.assertAlmostEqual(measure.loop_length(sections.bore_loop(dm)), dm.bore_loop, places=9)


class MeridianTest(unittest.TestCase):
    def test_tools_on_the_605zz_are_the_gallerys_literals(self):
        dm = derive(default_params())
        self.assertEqual([c.start for c in sections.ring_back_tool(dm)],
                         [(12.25, -2.25), (18.6, -2.25), (17.1, -0.75), (17.1, 3.45), (16.1, 4.45), (12.25, 4.45)])
        self.assertEqual([c.start for c in sections.ring_front_tool(dm)],
                         [(12.25, 20.75), (18.6, 20.75), (17.1, 19.25), (17.1, 15.05), (16.1, 14.05), (12.25, 14.05)])
        for got, want in zip(sections.back_plate_points(dm),
                             ((9.5, 5.0), (9.5, 3.4), (10.3, 3.6), (16.1, 3.6), (17.7, 2.0), (17.7, 5.0))):
            self.assertAlmostEqual(got[0], want[0], places=9)
            self.assertAlmostEqual(got[1], want[1], places=9)
        for got, want in zip(sections.cover_points(dm),
                             ((9.5, 13.5), (9.5, 15.1), (10.3, 14.9), (16.1, 14.9), (17.7, 16.5), (17.7, 13.5))):
            self.assertAlmostEqual(got[0], want[0], places=9)
            self.assertAlmostEqual(got[1], want[1], places=9)

    def test_ring_front_is_the_back_mirrored_in_the_hub_mid_plane(self):
        for p in (default_params(), Params(shaft="608ZZ", bore_clearance=0.5)):
            dm = derive(p)
            for (r0, z0), (r1, z1) in zip(sections.ring_back_points(dm), sections.ring_front_points(dm)):
                self.assertAlmostEqual(r0, r1, places=9)
                self.assertAlmostEqual(18.5 - z0, z1, places=9)

    def test_cover_tool_is_the_back_plate_tool_mirrored(self):
        for p in (default_params(), Params(shaft="608ZZ", bore_clearance=0.5)):
            dm = derive(p)
            for (r0, z0), (r1, z1) in zip(sections.back_plate_points(dm), sections.cover_points(dm)):
                self.assertAlmostEqual(r0, r1, places=9)
                self.assertAlmostEqual(18.5 - z0, z1, places=9)


if __name__ == "__main__":
    unittest.main()
