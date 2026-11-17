import math
import unittest

import _support  # noqa: F401
from gen.clutch import bodies, probes, sections
from gen.curves import loop_polygon
from gen.clutch.params import Params
from gen.clutch.validate import derive


def parts(**kw):
    p = Params(**kw)
    return probes.part_probes(p, derive(p))


class ProbeTest(unittest.TestCase):
    def test_bodies_with_probes(self):
        self.assertEqual(sorted(parts()), sorted([bodies.HUB, bodies.RING, bodies.BACK_PLATE, bodies.COVER]))
        self.assertIn(bodies.ADAPTER, parts(adapter=True))

    def test_each_body_has_inside_and_outside_probes(self):
        for name, plist in parts(adapter=True).items():
            with self.subTest(body=name):
                self.assertEqual({p.expect for p in plist}, {probes.INSIDE, probes.OUTSIDE})

    def test_hub_probes_are_at_mid_height_and_clear_of_the_outline(self):
        p = Params()
        dm = derive(p)
        outline = loop_polygon(sections.layout(sections.hub_outline(dm), dm.sign))
        plist = probes.part_probes(p, dm)[bodies.HUB]
        self.assertTrue(all(abs(q.point[2] - 9.25) < 1e-9 for q in plist))
        for q in plist:
            self.assertGreaterEqual(probes._edge_distance(q.point[:2], outline), 0.29, q.label)
        # A point inside the outline and outside every hole is material.
        for q in plist:
            if q.expect == probes.INSIDE:
                self.assertTrue(probes._inside(q.point[:2], outline), q.label)

    def test_the_clockwise_ring_grid_is_the_counter_clockwise_shape_mirrored(self):
        cw = parts()
        ring_cw = [q for q in cw[bodies.RING] if q.label.startswith("ring (")]
        dm = derive(Params())
        outline = loop_polygon(sections.ring_outline(dm))
        tooth_ccw = loop_polygon(sections.tooth_loop(dm))
        for q in ring_cw:
            mirrored = (-q.point[0], q.point[1])
            solid = probes._inside(mirrored, outline) and not probes._inside(mirrored, tooth_ccw)
            solid = solid and all(math.dist(mirrored, c) > 1.3 for c in sections.ear_centers(dm))
            self.assertEqual(q.expect == probes.INSIDE, solid, q.label)

    def test_ring_pocket_probes_sit_inside_the_hexagon_and_clear_of_the_bore(self):
        # Each ear's pocket probe is 1.7 mm out from the bore on the pocket's flat normal: inside the hexagon
        # (apothem 2.174) and 0.4 from the 1.3 mm bore.
        found = [q for q in parts()[bodies.RING] if q.label.endswith("nut pocket") and "above" not in q.label]
        self.assertEqual(len(found), 3)
        centres = sections.ear_centers(derive(Params()))
        for q in found:
            d = min(math.dist(q.point[:2], c) for c in centres)
            self.assertAlmostEqual(d, 1.7, places=9)
            self.assertEqual((q.expect, q.point[2]), (probes.OUTSIDE, -0.5))

    def test_grown_presets_probes_stay_in_bounds(self):
        # Every INSIDE probe lies inside its body's bounds, and the plates' rim probes follow the grown radius.
        from gen.clutch import expected

        for kw in ({"shaft": "608ZZ"}, {"shaft": "608ZZ", "bore_clearance": 0.5}, {"shaft": "608ZZ-gearbox"}):
            p = Params(adapter=True, **kw)
            dm = derive(p)
            for name, plist in probes.part_probes(p, dm).items():
                lo = expected.body_bounds(name, p, dm)
                for q in plist:
                    if q.expect == probes.INSIDE:
                        with self.subTest(kw=kw, body=name, probe=q.label):
                            for i in range(3):
                                self.assertTrue(lo[i] < q.point[i] < lo[i + 3], (q.point, lo))
            back = {q.label: q for q in probes.part_probes(p, dm)[bodies.BACK_PLATE]}
            self.assertAlmostEqual(back["back plate rim"].point[1], dm.plate_radius - 0.3)
            self.assertAlmostEqual(back["back plate beyond the rim"].point[1], dm.plate_radius + 0.3)

    def test_ring_probes_follow_the_grown_counterbore(self):
        p = Params(shaft="608ZZ", bore_clearance=0.5)
        dm = derive(p)
        ring = {q.label: q for q in probes.part_probes(p, dm)[bodies.RING]}
        self.assertAlmostEqual(ring["ring counterbore"].point[1], -(dm.ring_counter - 0.6))
        self.assertAlmostEqual(ring["ring wall at the counterbore"].point[1], -(dm.ring_counter + 0.9))
        self.assertLess(dm.ring_counter + 0.9, dm.ring_outer)

    def test_plate_probes_stay_inside_the_plate_height(self):
        plist = parts()
        for q in plist[bodies.BACK_PLATE]:
            self.assertTrue(0.0 < q.point[2] < 4.0, q.label)
        for q in plist[bodies.COVER]:
            self.assertTrue(14.5 < q.point[2] < 18.5, q.label)

    def test_adapter_probes_stay_inside_the_adapter_height(self):
        for q in parts(adapter=True)[bodies.ADAPTER]:
            self.assertTrue(20.0 < q.point[2] < 26.0, q.label)


if __name__ == "__main__":
    unittest.main()
