import math
import unittest

import _support  # noqa: F401
from gen import sections
from gen.curves import Arc, Line, loop_is_closed, loop_polygon
from gen.layout import layout
from gen.params import default_params
from gen.polygon import polygon_area, point_in_polygon

G = layout(default_params())


def arcs(loop):
    return [c for c in loop if isinstance(c, Arc)]


def lines(loop):
    return [c for c in loop if isinstance(c, Line)]


def radius(a):
    return math.hypot(a.start[0] - a.center[0], a.start[1] - a.center[1])


def points(loop):
    out = set()
    for c in loop:
        out.add(c.start)
        out.add(c.end)
    return out


class SectionsTest(unittest.TestCase):
    def assertArcsConsistent(self, loop, radii=None, tol=1e-9):
        for a in arcs(loop):
            r_end = math.hypot(a.end[0] - a.center[0], a.end[1] - a.center[1])
            self.assertAlmostEqual(radius(a), r_end, delta=tol)
            if radii is not None:
                self.assertTrue(any(abs(radius(a) - r) < 1e-6 for r in radii), radius(a))

    def assertHas(self, loop, pt, tol=1e-3):
        best = min(math.hypot(q[0] - pt[0], q[1] - pt[1]) for q in points(loop))
        self.assertLess(best, tol, f"{pt} not on loop")

    def test_every_loop_is_closed(self):
        loops = [sections.plate_outline(98.0), sections.plate_outline(82.0), sections.window_loop(G, 1),
                 sections.window_loop(G, -1), sections.escape_tooth(G), sections.anchor_outline(G),
                 sections.crutch_outline(G), sections.pendulum_outline(G), sections.crutch_slot(),
                 sections.press_d(), sections.ratchet_triangle(), sections.ratchet_tool_outline(),
                 sections.pawl_layer((1.0, 1.0 + math.pi)), sections.pawl_layer((-2.0, -2.0 + math.pi))]
        loops += sections.escape_windows()
        loops += [sections.arbor_meridian(p) for p in sections.ARBOR_FLATS]
        for i, loop in enumerate(loops):
            self.assertTrue(loop_is_closed(loop), i)
            self.assertArcsConsistent(loop)
            self.assertGreater(abs(polygon_area(loop_polygon(loop))), 1.0, i)

    def test_plate_outline(self):
        loop = sections.plate_outline(98.0)
        self.assertEqual((len(arcs(loop)), len(lines(loop))), (4, 4))
        self.assertArcsConsistent(loop, [10.0])
        self.assertAlmostEqual(polygon_area(loop_polygon(loop)), 116 * 194 - (4 - math.pi) * 100, delta=0.05)
        self.assertAlmostEqual(polygon_area(loop_polygon(sections.plate_outline(82.0))),
                               116 * 178 - (4 - math.pi) * 100, delta=0.05)

    def test_window_points(self):
        py = G.axis_p[1]
        for sx in (1.0, -1.0):
            loop = sections.window_loop(G, sx)
            self.assertEqual((len(lines(loop)), len(arcs(loop))), (6, 12))
            self.assertArcsConsistent(loop, [6.0, 10.0, 1.0])
            rounds = sections.window_rounds(G, sx)
            self.assertEqual(len(rounds), 7)
            corners = [(sx * 8.3958, 62.0), (sx * 4.0, 47.4033), (sx * 4.0, 9.1652), (sx * 4.0, -9.1652),
                       (sx * 4.0, -36.5848), (sx * 4.0, -54.9152)]  # F, H, I, J, K, L
            for r, want in zip(rounds, corners):
                self.assertLess(math.hypot(r.corner[0] - want[0], r.corner[1] - want[1]), 1e-3 if want[1] == 62.0 else 1e-4)
                self.assertEqual(r.radius, 1.0)
                self.assertGreater(min(math.hypot(q[0] - r.corner[0], q[1] - r.corner[1]) for q in points(loop)), 0.1)
            self.assertAlmostEqual(rounds[6].corner[0], sx * 4.0, delta=1e-9)  # A
            self.assertAlmostEqual(rounds[6].corner[1], -82.0, delta=1e-9)
            self.assertAlmostEqual(rounds[6].centre[0], sx * 5.0, delta=1e-9)
            self.assertAlmostEqual(rounds[6].centre[1], -81.0, delta=1e-9)
            hubs = [G.axis_p, G.axis_p, (0.0, 0.0), (0.0, 0.0), (0.0, G.axis_g[1]), (0.0, G.axis_g[1])]
            for r, hub in zip(rounds[:6], hubs):
                if r is not rounds[0]:
                    self.assertAlmostEqual(r.centre[0], sx * 5.0, delta=1e-9)
                    self.assertAlmostEqual(math.hypot(r.centre[0] - hub[0], r.centre[1] - hub[1]), 11.0, delta=1e-9)
            self.assertAlmostEqual(rounds[0].centre[1], 61.0, delta=1e-9)
            self.assertAlmostEqual(math.hypot(rounds[0].centre[0], rounds[0].centre[1] - py), 11.0, delta=1e-9)
            poly = loop_polygon(loop)
            self.assertTrue(point_in_polygon(poly, (sx * 20.0, 0.0)))
            self.assertFalse(point_in_polygon(poly, (sx * 2.0, 0.0)))
            self.assertFalse(point_in_polygon(poly, (0.0, py)))  # inside the hub ring bulge
            self.assertFalse(point_in_polygon(poly, (sx * 8.0, py)))
            self.assertTrue(point_in_polygon(poly, (sx * 20.0, py)))

    def test_lip_centres(self):
        c = sections.lip_centres(G)
        self.assertEqual(c[0], (0.0, 0.0))
        self.assertAlmostEqual(c[1][1], 56.5685, delta=1e-4)
        self.assertEqual(c[2][0], 0.0)
        self.assertAlmostEqual(c[2][1], -45.75, delta=1e-9)
        self.assertEqual(sections.MOUNT_HOLES, ((-40.0, 90.0), (40.0, 90.0)))

    def test_escape_windows(self):
        wins = sections.escape_windows()
        self.assertEqual(len(wins), 6)
        for w in wins:
            self.assertEqual((len(arcs(w)), len(lines(w))), (6, 2))
            self.assertArcsConsistent(w, [13.0, 28.0, 1.0])
        # Window 0 spans 90 to 150 degrees; its centroid direction is 120 degrees.
        poly = loop_polygon(wins[0])
        self.assertTrue(point_in_polygon(poly, (20.5 * math.cos(math.radians(120)), 20.5 * math.sin(math.radians(120)))))
        self.assertFalse(point_in_polygon(poly, (20.5, 0.0)))
        rounds = sections.escape_window_rounds(0)
        self.assertEqual(len(rounds), 4)
        a, d = rounds[3], rounds[2]  # side 1 is the spoke at 90 degrees, so a and d sit at x = -3.5
        self.assertAlmostEqual(a.centre[0], -3.5, delta=1e-9)
        self.assertAlmostEqual(d.centre[0], -3.5, delta=1e-9)
        self.assertAlmostEqual(math.hypot(*a.centre), 14.0, delta=1e-9)
        self.assertAlmostEqual(math.hypot(*d.centre), 27.0, delta=1e-9)

    def test_tooth(self):
        loop = sections.escape_tooth(G)
        self.assertEqual(len(lines(loop)), 3)
        self.assertHas(loop, (0.0, 40.0))
        self.assertHas(loop, (-1.3272, 32.4729), 1e-4)
        self.assertHas(loop, (-4.5118, 32.1853), 1e-4)

    def test_anchor_outline(self):
        loop = sections.anchor_outline(G)
        self.assertEqual((len(lines(loop)), len(arcs(loop))), (8, 10))
        self.assertArcsConsistent(loop, [G.r_in, G.r_out, 8.0, 3.0, 1.0], tol=1e-9)
        for q in (G.ce, G.fe, G.cx, G.fx, G.me, G.mx):
            self.assertHas(loop, q, 1e-12)
        ge, he, hx, gx = sections.anchor_rounds(G)
        for r, q in zip((ge, he, hx, gx), (G.ge, G.he, G.hx, G.gx)):
            self.assertEqual(r.corner, q)
        for r in (he, hx):
            self.assertAlmostEqual(math.hypot(*r.centre), 11.0, delta=1e-9)
        for r in (ge, gx):
            self.assertAlmostEqual(math.hypot(*r.centre), G.r_in - 1.0, delta=1e-9)
        self.assertGreater(abs(polygon_area(loop_polygon(loop))), 100.0)

    def test_crutch_and_pendulum(self):
        crutch = sections.crutch_outline(G)
        self.assertArcsConsistent(crutch, [6.0, 4.0, 2.5])
        self.assertEqual((len(lines(crutch)), len(arcs(crutch))), (2, 4))
        for r, sx in zip(sections.crutch_rounds(G), (-1.0, 1.0)):
            self.assertAlmostEqual(r.centre[0], sx * 5.0, delta=1e-9)
            self.assertAlmostEqual(math.hypot(*r.centre), 8.5, delta=1e-9)
        self.assertEqual(sections.CRUTCH_PIN, ((0.0, -45.0), 1.5))
        self.assertTrue(point_in_polygon(loop_polygon(crutch), (0.0, -20.0)))
        self.assertTrue(point_in_polygon(loop_polygon(crutch), (0.0, -45.0)))
        self.assertFalse(point_in_polygon(loop_polygon(crutch), (4.0, -20.0)))
        pend = sections.pendulum_outline(G)
        self.assertArcsConsistent(pend, [10.0, 25.0, 4.0])
        self.assertEqual((len(lines(pend)), len(arcs(pend))), (2, 6))
        el, ql, qr, er = sections.pendulum_rounds(G)
        bob = (0.0, -G.params.pendulum_length)
        for r in (el, er):
            self.assertAlmostEqual(abs(r.centre[0]), 8.0, delta=1e-9)
            self.assertAlmostEqual(math.hypot(*r.centre), 14.0, delta=1e-9)
        for r in (ql, qr):
            self.assertAlmostEqual(abs(r.centre[0]), 8.0, delta=1e-9)
            self.assertAlmostEqual(math.hypot(r.centre[0] - bob[0], r.centre[1] - bob[1]), 29.0, delta=1e-9)
        self.assertTrue(point_in_polygon(loop_polygon(pend), (0.0, -G.params.pendulum_length)))
        slot = sections.crutch_slot()
        self.assertArcsConsistent(slot, [1.75])
        self.assertAlmostEqual(abs(polygon_area(loop_polygon(slot, math.radians(0.1)))),
                               4.5 * 3.5 + math.pi * 1.75**2, delta=1e-3)

    def test_press_d(self):
        d = sections.press_d()
        self.assertArcsConsistent(d, [2.05])
        self.assertAlmostEqual(abs(polygon_area(loop_polygon(d, math.radians(0.05)))), sections.press_d_area(),
                               delta=1e-3)
        self.assertLess(sections.press_d_area(), math.pi * 2.05**2)
        self.assertEqual(lines(d)[0].start[0], 1.55)

    def test_ratchet(self):
        tri = sections.ratchet_triangle()
        self.assertEqual((len(lines(tri)), len(arcs(tri))), (3, 1))
        self.assertArcsConsistent(tri, [0.5])
        self.assertHas(tri, (11.0, 0.0), 1e-12)
        r = arcs(tri)[0]
        # The round's touch point on the radial side (30 degrees) lies at radius 12.95.
        radial = [q for q in (r.start, r.end) if abs(math.atan2(q[1], q[0]) - math.pi / 6) < 1e-6][0]
        self.assertAlmostEqual(math.hypot(*radial), 12.95, delta=0.005)
        self.assertAlmostEqual(math.degrees(sections.ratchet_alpha()), 10.07, delta=0.01)
        tool = sections.ratchet_tool_outline()
        self.assertEqual((len(arcs(tool)), len(lines(tool))), (24, 24))
        self.assertArcsConsistent(tool, [11.5, 0.5])
        poly = loop_polygon(tool, math.radians(0.1))
        area = abs(polygon_area(poly))
        self.assertGreater(area, math.pi * 11.5**2)
        # The point at r 12.5, 25 deg is inside the tool outline; r 12.5, 5 deg is outside it.
        self.assertTrue(point_in_polygon(poly, (12.5 * math.cos(math.radians(25)), 12.5 * math.sin(math.radians(25)))))
        self.assertFalse(point_in_polygon(poly, (12.5 * math.cos(math.radians(5)), 12.5 * math.sin(math.radians(5)))))
        for deg, inside in ((20.45, False), (20.65, True)):
            a = math.radians(deg)
            self.assertEqual(point_in_polygon(poly, (12.5 * math.cos(a), 12.5 * math.sin(a))), inside, deg)

    def test_pawl_layer(self):
        g = 90 * math.pi / 180
        gangs = (g, g + math.pi)
        loop = sections.pawl_layer(gangs)
        self.assertEqual((len(lines(loop)), len(arcs(loop))), (8, 14))
        self.assertArcsConsistent(loop, [7.5, 0.75, 9.0, 12.5, 10.5, 0.5, 1.0])
        poly = loop_polygon(loop, math.radians(0.1))
        self.assertGreater(polygon_area(poly), 0.0)

        def at(r, a):
            return (r * math.cos(a), r * math.sin(a))
        self.assertTrue(point_in_polygon(poly, at(11.5, g - math.radians(114))))
        self.assertTrue(point_in_polygon(poly, at(9.75, g - math.radians(60))))
        self.assertTrue(point_in_polygon(poly, (0.0, 0.0)))
        self.assertFalse(point_in_polygon(poly, at(8.0, g - math.radians(60))))
        c = g - 0.75 / 8.25
        ctr = at(8.25, c)
        along = (-math.sin(c), math.cos(c))
        self.assertFalse(point_in_polygon(poly, (ctr[0] + 0.7 * along[0], ctr[1] + 0.7 * along[1])))
        self.assertTrue(point_in_polygon(poly, (ctr[0] + 0.8 * along[0], ctr[1] + 0.8 * along[1])))
        self.assertFalse(point_in_polygon(poly, ctr))
        rounds = sections.pawl_rounds(gangs)
        self.assertEqual(len(rounds), 4)
        self.assertAlmostEqual(math.hypot(*rounds[0].centre), 11.0, delta=1e-9)
        self.assertAlmostEqual(math.hypot(*rounds[1].centre), 8.5, delta=1e-9)
        slot_ends = [a for a in arcs(loop) if abs(radius(a) - 0.75) < 1e-9]
        self.assertEqual(len(slot_ends), 2)
        self.assertAlmostEqual(math.hypot(*slot_ends[0].center), 8.25, delta=1e-9)

    def test_d_families(self):
        fams = {
            "end": (sections.END_D, 12.283742), "rear peg": (sections.REAR_PEG_D, 19.395506),
            "body": (sections.BODY_D, 33.091726), "carrier": (sections.CARRIER_D, 34.064016),
            "keyed counter": (sections.KEYED_COUNTER_D, 43.269810), "keyed ring": (sections.KEYED_RING_D, 42.105848),
        }
        for name, (d, area) in fams.items():
            loop = sections.d_section(d)
            self.assertTrue(loop_is_closed(loop), name)
            self.assertArcsConsistent(loop, [d[0]])
            self.assertAlmostEqual(sections.d_area(d), area, places=6, msg=name)
            poly_area = abs(polygon_area(loop_polygon(loop, math.radians(0.05))))
            self.assertAlmostEqual(poly_area, sections.d_area(d), delta=1e-3, msg=name)
        self.assertEqual(sections.BODY_D[1], 2.60)
        self.assertEqual(sections.CARRIER_D[1], 2.85)
        for d in (sections.BODY_D, sections.CARRIER_D):
            self.assertGreater(d[1], 2.5)
        self.assertEqual(sections.REAR_PEG_D, (2.55, 2.05))

    def test_meridians(self):
        expect = {
            "escape_arbor": [(0, -5), (2.5, -5), (2.5, 0.25), (3.3, 0.25), (3.3, 24.0), (3.7, 24.0), (3.7, 27.75),
                             (2.5, 27.75), (2.5, 33), (0, 33)],
            "pallet_arbor": [(0, -5), (2.5, -5), (2.5, 0.25), (3.7, 0.25), (3.7, 20.95), (3.3, 20.95), (3.3, 27.75),
                             (2.5, 27.75), (2.5, 33.25), (2.0, 33.25), (2.0, 38.25), (0, 38.25)],
            "great_wheel_arbor": [(0, -5), (2.5, -5), (2.5, 0.25), (3.7, 0.25), (3.7, 3.25), (3.05, 3.25),
                                  (3.05, 5.20), (3.3, 5.20), (3.3, 27.75), (2.5, 27.75), (2.5, 33.25),
                                  (2.0, 33.25), (2.0, 38.25), (0, 38.25)],
            "suspension_pin": [(0, 31.05), (2.5, 31.05), (2.5, 34), (3.7, 34), (3.7, 39.80), (2.5, 39.80),
                               (2.5, 45.25), (2.0, 45.25), (2.0, 46.75), (0, 46.75)],
        }
        for part, pts in expect.items():
            loop = sections.arbor_meridian(part)
            self.assertEqual(len(loop), len(pts))
            self.assertEqual([c.start for c in loop], [tuple(map(float, p)) for p in pts])
        self.assertEqual(sections.ARBOR_FLATS["escape_arbor"], ((2.55, 0.20, 23.95),))
        self.assertEqual(sections.ARBOR_FLATS["pallet_arbor"], ((2.55, 21.0, 27.80), (1.5, 34.25, 39.25)))
        self.assertEqual(
            sections.ARBOR_FLATS["great_wheel_arbor"],
            ((2.80, 5.25, 17.55), (2.55, 17.45, 27.80), (1.5, 34.25, 39.25)),
        )
        self.assertEqual(sections.ARBOR_FLATS["suspension_pin"], ((2.0, 30.05, 33.95), (1.5, 45.30, 47.75)))
        with self.assertRaises(KeyError):
            sections.arbor_meridian("anchor")
        self.assertEqual(sections.flat_box(2.55), ((2.55, -3.5), (3.5, 3.5)))
        self.assertEqual(sections.flat_box(2.0), ((2.0, -3.5), (3.5, 3.5)))


if __name__ == "__main__":
    unittest.main()
