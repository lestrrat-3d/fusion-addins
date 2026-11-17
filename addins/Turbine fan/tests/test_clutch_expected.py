import math
import unittest

import _support  # noqa: F401
from gen.clutch import bodies, expected, measure, sections
from gen.clutch.params import COUNTER_CLOCKWISE, Params, default_params
from gen.clutch.validate import derive


# Volumes read from decad builds of the gallery model at gallery a8114921f (Clockwise): (shaft, c) -> hub, ring, back
# plate, cover, adapter.
DECAD = {
    ("605ZZ", 0.05): (4126.7974, 9845.7350, 3023.2387, 3030.2212, 11767.6872),
    ("605ZZ", 0.5): (4049.2762, 9845.7350, 2992.2322, 2999.2147, 11767.6872),
    ("608ZZ", 0.05): (4410.8783, 10164.0897, 3218.2789, 3225.2634, 12288.4592),
    ("608ZZ", 0.5): (4658.1563, 10356.1345, 3368.1445, 3375.1302, 12758.5281),
    ("608ZZ-gearbox", 0.05): (4400.0908, 10164.0897, 3213.9492, 3220.9337, 12288.4592),
}


class RingTest(unittest.TestCase):
    def test_computed_ring_volume_matches_the_gallery(self):
        # instructions.md: the ring's volume is 9845.74 +- 5.43 mm^3. The sections the builders draw give the same.
        self.assertAlmostEqual(expected.ring_volume_computed(derive(default_params())), expected.RING_VOLUME, delta=1.0)

    def test_ring_expectation(self):
        e = expected.body_volume(bodies.RING, default_params(), derive(default_params()))
        self.assertEqual((e.value, e.tol), (9845.74, 5.43))

    def test_grown_ring_is_computed_and_matches_decad(self):
        for (shaft, c), vols in DECAD.items():
            with self.subTest(shaft=shaft, c=c):
                p = Params(shaft=shaft, bore_clearance=c)
                e = expected.body_volume(bodies.RING, p, derive(p))
                self.assertAlmostEqual(e.value, vols[1], delta=1.0)
                if shaft == "605ZZ":
                    self.assertEqual(e.value, expected.RING_VOLUME)


class HubTest(unittest.TestCase):
    def test_every_hub_is_chamfered(self):
        for kw in ({}, {"bore_clearance": 0.5}, {"shaft": "608ZZ"}, {"shaft": "608ZZ-gearbox"},
                   {"shaft": "608ZZ", "bore_clearance": 0.5}):
            with self.subTest(kw=kw):
                dm = derive(Params(**kw))
                self.assertTrue(expected.hub_is_chamfered(dm))
                self.assertGreater(expected.hub_face_area(dm), 400.0)

    def test_hub_volume_is_the_prism_less_the_chamfer_estimate(self):
        dm = derive(default_params())
        e = expected.hub_volume(dm)
        self.assertAlmostEqual(e.value, expected.hub_face_area(dm) * 10 - 0.25**2 * expected.hub_chamfer_length(dm))
        self.assertAlmostEqual(expected.hub_chamfer_length(dm), 192.0, delta=3.0)  # about 384 mm on both faces

    def test_the_8mm_d_loop_is_chamfered_whole(self):
        dm = derive(Params(shaft="608ZZ"))
        dm5 = derive(default_params())
        self.assertGreaterEqual(dm.bore_loop, 20.0)
        self.assertLess(dm5.bore_loop, 20.0)
        self.assertGreater(expected.hub_chamfer_length(dm), dm.bore_loop)

    def test_computed_printed_volumes_match_decad(self):
        for (shaft, c), vols in DECAD.items():
            with self.subTest(shaft=shaft, c=c):
                dm = derive(Params(shaft=shaft, bore_clearance=c))
                self.assertAlmostEqual(expected.hub_volume(dm).value, vols[0], delta=0.5)
                self.assertAlmostEqual(expected.back_plate_volume(dm).value, vols[2], delta=0.6)
                self.assertAlmostEqual(expected.cover_volume(dm).value, vols[3], delta=0.6)
                self.assertAlmostEqual(expected.adapter_volume(dm).value, vols[4], delta=0.6)


class PlatesTest(unittest.TestCase):
    def test_plates_differ_by_their_pockets_only(self):
        dm = derive(default_params())
        # The cover's head pockets (radius 2.2) remove less than the back plate's hexagons (corner radius 2.509).
        diff = expected.cover_volume(dm).value - expected.back_plate_volume(dm).value
        hexagon = measure.hexagon_area(4.0 / math.sqrt(3) + 0.2)
        circle = measure.circle_area(3.8 / 2 + 0.3)
        self.assertAlmostEqual(diff, 3 * (hexagon - circle) * 2.0, delta=0.01)

    def test_scan_volume_of_a_simple_polygon(self):
        # A rectangle r 1 to 2, z 0 to 1 turned about Z: pi (4 - 1) = 9.42.
        poly = ((1.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0))
        self.assertAlmostEqual(measure.revolved_volume(poly, 0.0, 1.0), 3 * math.pi, places=6)
        self.assertAlmostEqual(measure.revolved_volume(poly, 0.0, 0.5), 1.5 * math.pi, places=6)
        self.assertAlmostEqual(measure.revolved_volume(poly, 0.0, 1.0, r_max=1.5), math.pi * 1.25, places=6)

    def test_inner_tool_takes_the_annulus_only(self):
        removed = measure.revolved_volume(sections.back_plate_points(derive(default_params())), 0.0, 4.0, 16.7)
        # The recess under the boss face (r 9.5 to 16.7, 0.4 deep) plus the cone to the rim: about 260 mm^3.
        self.assertGreater(removed, 240.0)
        self.assertLess(removed, 280.0)


class BoundsTest(unittest.TestCase):
    def setUp(self):
        self.p = default_params()
        self.dm = derive(self.p)

    def test_printed_bounds(self):
        for got, want in ((expected.body_bounds(bodies.BACK_PLATE, self.p, self.dm), (-16.7, -16.7, 0.0, 16.7, 16.7, 4.0)),
                          (expected.body_bounds(bodies.COVER, self.p, self.dm), (-16.7, -16.7, 14.5, 16.7, 16.7, 18.5))):
            for a, b in zip(got, want):
                self.assertAlmostEqual(a, b, places=9)
        ring = expected.body_bounds(bodies.RING, self.p, self.dm)
        self.assertAlmostEqual(ring[0], -22.806, places=3)
        self.assertAlmostEqual(ring[3], 22.806, places=3)
        self.assertAlmostEqual(ring[1], -19.1, places=3)
        self.assertAlmostEqual(ring[4], 25.7, places=3)
        self.assertEqual((ring[2], ring[5]), (-1.25, 19.75))
        for a, b in zip(expected.body_bounds(bodies.ADAPTER, self.p, self.dm), (-25.7, -25.7, 20.0, 25.7, 25.7, 26.0)):
            self.assertAlmostEqual(a, b, places=9)

    def test_grown_bounds_match_decad(self):
        # Bounds read from decad builds at 608ZZ, c 0.05 and 0.5.
        for c, plate, ring, adapter in ((0.05, 17.4775, (-23.4789, -19.8761, 23.4789, 26.4761), 26.4775),
                                        (0.5, 17.945, (-23.8844, -20.3436, 23.8844, 26.9450), 26.945)):
            p = Params(shaft="608ZZ", bore_clearance=c)
            dm = derive(p)
            back = expected.body_bounds(bodies.BACK_PLATE, p, dm)
            self.assertAlmostEqual(back[3], plate, places=4)
            got = expected.body_bounds(bodies.RING, p, dm)
            for a, b in zip((got[0], got[1], got[3], got[4]), ring):
                self.assertAlmostEqual(a, b, delta=0.002)
            self.assertAlmostEqual(expected.body_bounds(bodies.ADAPTER, p, dm)[3], adapter, places=3)

    def test_hub_bounds_mirror_with_the_direction(self):
        cw = expected.body_bounds(bodies.HUB, self.p, self.dm)
        p2 = Params(freewheel=COUNTER_CLOCKWISE)
        ccw = expected.body_bounds(bodies.HUB, p2, derive(p2))
        self.assertAlmostEqual(cw[0], -ccw[3], places=3)
        self.assertAlmostEqual(cw[3], -ccw[0], places=3)
        self.assertEqual((cw[2], cw[5]), (4.25, 14.25))

    def test_bolts_and_nuts_sit_on_their_sites(self):
        for i, name in enumerate(bodies.BOLTS):
            lo = expected.body_bounds(name, self.p, self.dm)
            site = self.dm.sites[i]
            self.assertAlmostEqual(lo[2], 0.5)  # the tip ends 0.5 inside the back plate, seams open
            self.assertAlmostEqual(lo[5], 18.5)  # the head is flush with the cover
            self.assertAlmostEqual((lo[0] + lo[3]) / 2, site.head[0])
        for i, name in enumerate(bodies.NUTS):
            lo = expected.body_bounds(name, self.p, self.dm)
            self.assertAlmostEqual(lo[2], 0.2)  # the nut sits from z 0.2 to 1.8
            self.assertAlmostEqual(lo[5], 1.8)

    def test_mount_fasteners(self):
        p = Params(adapter=True)
        dm = derive(p)
        lo = expected.body_bounds("Mount Bolt 1", p, dm)
        self.assertAlmostEqual(lo[2], 26.0 - 27.0)  # tip z -1.0
        self.assertAlmostEqual(lo[5], 26.0)
        lo = expected.body_bounds("Mount Nut 1", p, dm)
        self.assertAlmostEqual(lo[2], -1.05)
        self.assertAlmostEqual(lo[5], 0.55)

    def test_every_body_has_a_volume_and_bounds(self):
        p = Params(adapter=True)
        dm = derive(p)
        for name in bodies.body_names(True):
            with self.subTest(body=name):
                self.assertGreater(expected.body_volume(name, p, dm).value, 0)
                lo = expected.body_bounds(name, p, dm)
                self.assertTrue(all(lo[i] < lo[i + 3] for i in range(3)))


if __name__ == "__main__":
    unittest.main()
