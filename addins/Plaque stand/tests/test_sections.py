import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import sections
from gen.curves import Arc, Line, loop_is_closed, loop_polygon, polygon_area
from gen.params import Params, default_params
from gen.validate import derive
from test_params import CASES

# instructions.md "Representative cases": Area and Length.
AREAS = {
    "default": (1361.179509, 394.964986), "min": (621.769165, 196.627946), "max": (1851.394079, 515.368145),
    "forward": (1253.769166, 372.627946), "narrow-tall": (1471.829062, 418.032811),
    "short-steep": (1039.394079, 297.368145),
}


def _tangent_at(s, at_end):
    """Unit tangent of segment s at its end or start, in the direction of the outline's traversal."""
    if not s.is_arc():
        dx, dy = s.end[0] - s.start[0], s.end[1] - s.start[1]
    else:
        pt = s.end if at_end else s.start
        dx, dy = -(pt[1] - s.center[1]), pt[0] - s.center[0]  # counter-clockwise about the centre
        if not s.convex:  # a concave arc is traversed clockwise
            dx, dy = -dx, -dy
    n = math.hypot(dx, dy)
    return dx / n, dy / n


class OutlineTest(unittest.TestCase):
    def test_area_and_length_of_every_case(self):
        for name, (p, *_rest) in CASES.items():
            with self.subTest(case=name):
                segs = sections.outline_segments(derive(p))
                area, length = AREAS[name]
                self.assertAlmostEqual(sections.area(segs), area, places=5)
                self.assertAlmostEqual(sections.length(segs), length, places=5)

    def test_26_segments_alternating_lines_and_arcs_with_shared_ends(self):
        for name, (p, *_rest) in CASES.items():
            with self.subTest(case=name):
                segs = sections.outline_segments(derive(p))
                self.assertEqual(len(segs), 26)
                self.assertEqual([s.is_arc() for s in segs], [i % 2 == 1 for i in range(26)])
                for i, s in enumerate(segs):
                    nxt = segs[(i + 1) % 26]
                    self.assertAlmostEqual(math.dist(s.end, nxt.start), 0.0, places=9, msg=f"segment {i}")

    def test_convex_less_concave_sweep_is_a_full_turn(self):
        for name, (p, *_rest) in CASES.items():
            segs = sections.outline_segments(derive(p))
            total = sum((1 if s.convex else -1) * s.sweep() for s in segs if s.is_arc())
            self.assertAlmostEqual(math.degrees(total), 360.0, delta=1e-4, msg=name)  # asin is only good to ~1e-7 near pi

    def test_every_join_is_tangent(self):
        for name, (p, *_rest) in CASES.items():
            segs = sections.outline_segments(derive(p))
            for i, c in enumerate(segs):
                a = _tangent_at(c, True)
                b = _tangent_at(segs[(i + 1) % len(segs)], False)
                self.assertAlmostEqual(a[0], b[0], places=6, msg=f"{name} join {i}")
                self.assertAlmostEqual(a[1], b[1], places=6, msg=f"{name} join {i}")

    def test_channel_is_segments_4_to_12(self):
        dm = derive(default_params())
        segs = sections.outline_segments(dm)
        self.assertEqual(segs[8].start[1], dm.channel_floor)  # the floor line, after the back floor round
        self.assertEqual(segs[8].start[1], segs[8].end[1])  # the floor is horizontal
        self.assertAlmostEqual(segs[6].start[0], dm.channel_back)
        self.assertAlmostEqual(segs[10].start[0], dm.channel_front)
        self.assertAlmostEqual(segs[6].end[0] - segs[10].end[0], dm.channel_width)

    def test_the_slot_round_is_centred_on_the_seat(self):
        dm = derive(default_params())
        segs = sections.outline_segments(dm)
        self.assertEqual(segs[17].center, dm.seat)
        self.assertAlmostEqual(segs[17].radius, dm.slot_radius)

    def test_loop_is_closed_and_counter_clockwise(self):
        for name, (p, *_rest) in CASES.items():
            loop = sections.outline_loop(derive(p))
            self.assertEqual(len(loop), 26)
            self.assertTrue(loop_is_closed(loop), name)
            poly = loop_polygon(loop, math.radians(0.1))
            self.assertAlmostEqual(polygon_area(poly), AREAS[name][0], delta=0.2, msg=name)

    def test_every_arc_has_equal_radii_at_both_ends(self):
        for name, (p, *_rest) in CASES.items():
            for c in sections.outline_loop(derive(p)):
                if isinstance(c, Arc):
                    self.assertAlmostEqual(math.dist(c.center, c.start), math.dist(c.center, c.end), places=9)

    def test_concave_arcs_swap_their_ends(self):
        loop = sections.outline_loop(derive(default_params()))
        segs = sections.outline_segments(derive(default_params()))
        for c, s in zip(loop, segs):
            if s.is_arc() and not s.convex:
                self.assertEqual(c.start, s.end)
                self.assertEqual(c.end, s.start)
            elif s.is_arc():
                self.assertEqual((c.start, c.end), (s.start, s.end))


class RailTest(unittest.TestCase):
    def test_section_is_a_rounded_rectangle(self):
        loop = sections.rail_loop()
        self.assertEqual([type(c) for c in loop], [Line, Arc] * 4)
        self.assertTrue(loop_is_closed(loop))
        poly = loop_polygon(loop, math.radians(0.1))
        self.assertAlmostEqual(polygon_area(poly), 10 * 4 - (4 - math.pi), delta=1e-3)
        xs, ys = [q[0] for q in poly], [q[1] for q in poly]
        self.assertEqual((min(xs), max(xs), min(ys), max(ys)), (-5.0, 5.0, -2.0, 2.0))


if __name__ == "__main__":
    unittest.main()
