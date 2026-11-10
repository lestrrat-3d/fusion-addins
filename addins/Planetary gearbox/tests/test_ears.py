import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import ears
from gen.curves import Arc, Circle, Line, loop_is_closed, loop_polygon
from gen.dims import derive
from gen.params import default_params
from gen.polygon import polygon_area
from gen.validate import ValidationError, validate

P1 = default_params()
D1 = derive(P1)


def with_ears(**changes):
    p = dataclasses.replace(P1, **changes)
    return p, derive(p)


class EarGeometryTest(unittest.TestCase):
    def test_dimensions(self):
        self.assertEqual(ears.ear_half_width(4), 5)
        self.assertEqual(ears.ear_center_radius(44.1, 4), 49.1)
        self.assertAlmostEqual(ears.ear_angle(0, 3), math.pi / 2, places=12)
        self.assertAlmostEqual(ears.ear_angle(1, 3), math.radians(210), places=12)
        self.assertAlmostEqual(ears.ear_angle(2, 3), math.radians(330), places=12)

    def test_bore_centers(self):
        got = ears.ear_bore_centers(P1, D1)
        self.assertEqual(len(got), 3)
        for (x, y), deg in zip(got, (90, 210, 330)):
            self.assertAlmostEqual(x, 49.1 * math.cos(math.radians(deg)), places=9)
            self.assertAlmostEqual(y, 49.1 * math.sin(math.radians(deg)), places=9)
        p, d = with_ears(ear_count=0)
        self.assertEqual(ears.ear_bore_centers(p, d), [])

    def test_outline_without_ears_is_the_circle(self):
        p, d = with_ears(ear_count=0)
        self.assertEqual(ears.ring_outline(p, d), Circle((0.0, 0.0), 44.1))
        self.assertEqual(ears.ring_xmax(p, d), 44.1)
        self.assertAlmostEqual(ears.ring_blank_area(p, d), math.pi * 44.1**2, places=9)

    def test_outline_is_one_closed_loop(self):
        for count in (1, 2, 3, 4, 6):
            with self.subTest(count=count):
                p, d = with_ears(ear_count=count)
                loop = ears.ring_outline(p, d)
                self.assertEqual(len(loop), 4 * count)
                self.assertTrue(loop_is_closed(loop))
                # Consecutive curves share exact endpoints, so the sketch draws one loop of shared points.
                for i, c in enumerate(loop):
                    nxt = loop[(i + 1) % len(loop)]
                    self.assertIn(c.end, (nxt.start, nxt.end), (i, c))
                kinds = [type(c) for c in loop[:4]]
                self.assertEqual(kinds, [Line, Arc, Line, Arc])

    def test_ear_edges_have_the_gallery_shape(self):
        loop = ears.ring_outline(P1, D1)
        half, centre = 5.0, 49.1
        root = math.sqrt(44.1**2 - half**2)
        # The first ear is on +Y: its straight edges run parallel to Y, half a width either side of it.
        down, end, up, outer = loop[:4]
        self.assertAlmostEqual(down.start[0], half, places=9)
        self.assertAlmostEqual(down.start[1], root, places=9)
        self.assertAlmostEqual(down.end[1], centre, places=9)
        self.assertEqual(end.center, (math.cos(math.pi / 2) * centre, centre))
        self.assertAlmostEqual(up.end[0], -half, places=9)
        self.assertEqual(outer.center, (0.0, 0.0))
        for c in loop:
            if isinstance(c, Arc):
                r = math.dist(c.start, c.center)
                self.assertAlmostEqual(math.dist(c.end, c.center), r, places=9)
                self.assertTrue(abs(r - 44.1) < 1e-9 or abs(r - half) < 1e-9, r)

    def test_area_matches_the_sampled_outline(self):
        for changes in ({}, {"ear_count": 1}, {"ear_count": 2, "ear_bore_diameter": 6.0}, {"ear_count": 6}):
            with self.subTest(changes=changes):
                p, d = with_ears(**changes)
                poly = loop_polygon(ears.ring_outline(p, d), math.radians(0.01))
                bores = p.ear_count * math.pi * (p.ear_bore_diameter / 2) ** 2
                self.assertAlmostEqual(polygon_area(poly) - bores, ears.ring_blank_area(p, d), delta=1e-2)

    def test_area_matches_the_gallery_section(self):
        # ears_test.go: section = strip + half circle - bore, per ear, beyond the outer circle.
        p, d = with_ears(ear_count=2, ear_bore_diameter=6.0)
        half = 6.0 / 2 + 3
        wall = math.sqrt(44.1**2 - half**2)
        strip = 2 * half * (44.1 + half) - (half * wall + 44.1**2 * math.asin(half / 44.1))
        want = math.pi * 44.1**2 + 2 * (strip + math.pi * half * half / 2 - math.pi * 6.0**2 / 4)
        self.assertAlmostEqual(ears.ring_blank_area(p, d), want, places=9)

    def test_xmax_matches_the_sampled_outline(self):
        for changes in ({}, {"ear_count": 1}, {"ear_count": 2, "ear_bore_diameter": 6.0}, {"ear_count": 6}):
            with self.subTest(changes=changes):
                p, d = with_ears(**changes)
                poly = loop_polygon(ears.ring_outline(p, d), math.radians(0.01))
                self.assertAlmostEqual(ears.ring_xmax(p, d), max(x for x, _ in poly), delta=1e-4)
        # Two ears on the Y axis reach no further along X than the outer wall.
        p, d = with_ears(ear_count=2, ear_bore_diameter=6.0)
        self.assertAlmostEqual(ears.ring_xmax(p, d), 44.1, places=9)
        p, d = with_ears()
        self.assertAlmostEqual(ears.ring_xmax(p, d), 49.1 * math.cos(math.radians(30)) + 5, places=9)


class EarValidationTest(unittest.TestCase):
    def test_default_and_no_ears_are_valid(self):
        validate(P1)
        validate(dataclasses.replace(P1, ear_count=0))
        # A bore diameter of 0 only matters while there are ears.
        validate(dataclasses.replace(P1, ear_count=0, ear_bore_diameter=0.0))

    def test_rules(self):
        cases = (
            ({"ear_count": -1}, "ear count -1 is out of range"),
            ({"ear_bore_diameter": 0.0}, "ear bore diameter 0 is out of range"),
            ({"ear_bore_diameter": -4.0}, "ear bore diameter -4 is out of range"),
            ({"ear_count": 0, "ear_bore_diameter": -4.0}, "ear bore diameter -4 is out of range"),
            ({"ear_bore_diameter": float("inf")}, "EarBoreDiameter must be finite, got +Inf"),
            ({"ear_count": 8}, "ear 2 lies over a bolt site: turn the ears off the bolt angles by using another ear "
                               "count"),
            ({"ear_count": 20, "ear_bore_diameter": 20.0}, "neighbouring ear bores are "),
        )
        for changes, want in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError) as cm:
                    validate(dataclasses.replace(P1, **changes))
                self.assertTrue(str(cm.exception).startswith(want), str(cm.exception))


if __name__ == "__main__":
    unittest.main()
