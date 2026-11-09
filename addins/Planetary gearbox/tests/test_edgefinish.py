import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import edgefinish, layout
from gen.curves import loop_polygon
from gen.dims import derive
from gen.edgefinish import (
    LIP,
    OUTER,
    WINDOWS_AND_RIM,
    FinishPlane,
    edge_chamfer_volume,
    finish_planes,
    is_large_face,
    keep_loop,
    window_chamfer_volume,
)
from gen.params import default_params
from gen.sections import carrier_plate_outline, cover_window_loops

P1 = default_params()
D1 = derive(P1)
P2 = dataclasses.replace(P1, stages=2)
D2 = derive(P2)
P1_WIDE = dataclasses.replace(P1, edge_chamfer=1.0)
D1_WIDE = derive(P1_WIDE)

# part -> (volume at c = 0.5, volume at c = 1.0)
VOLUMES = {
    "ring": (81.0455, 323.1348),
    "cover": (179.0232, 719.4680),
    "carrier": (35.2647, 140.0115),
}


def offset_removed(poly, c):
    """Removed volume of a 45 deg chamfer around a hole polygon: P c^2/2 + c^3/3 sum tan(phi/2), mitered."""
    n = len(poly)
    ccw = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) > 0
    per = sum(math.dist(poly[i], poly[(i + 1) % n]) for i in range(n))
    k = 0.0
    for i in range(n):
        a, b, q = poly[i - 1], poly[i], poly[(i + 1) % n]
        phi = (math.atan2(q[1] - b[1], q[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0]) + math.pi) % (
            2 * math.pi) - math.pi
        k += math.tan((phi if ccw else -phi) / 2)
    return per * c * c / 2 + k * c**3 / 3


class EdgeFinishTest(unittest.TestCase):
    def test_large_face(self):
        self.assertEqual(edgefinish.LARGE_FACE_AREA, 400)
        self.assertFalse(is_large_face(399.999))
        self.assertTrue(is_large_face(400.0))

    def test_finish_planes(self):
        self.assertEqual(finish_planes(P1, D1, "ring"), [FinishPlane(1.0, OUTER, 1), FinishPlane(15.0, OUTER, 1)])
        self.assertEqual(finish_planes(P2, D2, "ring"), [FinishPlane(1.0, OUTER, 1), FinishPlane(28.0, OUTER, 1)])
        self.assertEqual(
            finish_planes(P1, D1, "cover"), [FinishPlane(0.0, LIP, 5), FinishPlane(3.0, WINDOWS_AND_RIM, 4)]
        )
        self.assertEqual(
            finish_planes(P1, D1, "carrier"), [FinishPlane(0.0, OUTER, 1), FinishPlane(3.0, OUTER, 1)]
        )
        for name in layout.PARTS:
            if name not in ("ring", "cover", "carrier"):
                with self.subTest(part=name):
                    self.assertEqual(finish_planes(P1, D1, name), [])

    def test_keep_loop(self):
        cases = (
            (OUTER, True, 1, 44.0, True),
            (OUTER, False, 1, 5.0, False),
            (OUTER, False, 4, 17.9, False),
            (OUTER, True, 6, 27.75, True),
            (WINDOWS_AND_RIM, True, 1, 44.0, True),
            (WINDOWS_AND_RIM, False, 4, 17.9, True),
            (WINDOWS_AND_RIM, False, 1, 38.5, False),
            (WINDOWS_AND_RIM, False, 1, 14.25, False),
            (LIP, True, 1, 44.0, True),
            (LIP, False, 4, 17.9, True),
            (LIP, False, 1, 5.0, True),
            (LIP, False, 1, 5.0009, True),
            (LIP, False, 1, 5.002, False),
            (LIP, False, 1, 39.3, False),
            (LIP, False, 0, -1.0, False),
        )
        for rule, outer, count, radius, want in cases:
            with self.subTest(rule=rule, outer=outer, count=count, radius=radius):
                self.assertIs(keep_loop(rule, outer, count, radius, D1), want)
        with self.assertRaises(ValueError):
            keep_loop("x", True, 1, 0.0, D1)

    def test_edge_chamfer_volume(self):
        for part, (small, wide) in VOLUMES.items():
            with self.subTest(part=part):
                self.assertAlmostEqual(edge_chamfer_volume(P1, D1, part), small, delta=1e-3)
                self.assertAlmostEqual(edge_chamfer_volume(P1_WIDE, D1_WIDE, part), wide, delta=1e-3)
                self.assertAlmostEqual(edge_chamfer_volume(P2, D2, part), small, delta=1e-3)
        for name in layout.PARTS:
            if name not in VOLUMES:
                with self.subTest(part=name):
                    self.assertEqual(edge_chamfer_volume(P1, D1, name), 0.0)

    def test_edge_chamfer_volume_ring_without_ears(self):
        for c, want in ((0.5, 68.8532), (1.0, 274.3658)):
            with self.subTest(chamfer=c):
                p = dataclasses.replace(P1, ear_count=0, edge_chamfer=c)
                self.assertAlmostEqual(edge_chamfer_volume(p, derive(p), "ring"), want, delta=1e-3)

    def test_window_chamfer_volume(self):
        self.assertAlmostEqual(window_chamfer_volume(D1, 0.5), 17.6851, delta=1e-3)
        self.assertAlmostEqual(window_chamfer_volume(D1_WIDE, 1.0), 71.3912, delta=1e-3)
        poly = loop_polygon(cover_window_loops(P1, D1)[0], math.radians(0.05))
        self.assertAlmostEqual(window_chamfer_volume(D1, 0.5), offset_removed(poly, 0.5), delta=1e-4)

    def test_lip_rim(self):
        self.assertAlmostEqual(edgefinish._rim(5.0, 0.5, False), 4.0579, delta=1e-3)
        self.assertAlmostEqual(edgefinish._rim(5.0, 1.0, False), 16.7552, delta=1e-3)

    def test_carrier_perimeter(self):
        self.assertAlmostEqual(edgefinish._perimeter(carrier_plate_outline(P1, D1)), 142.1059, delta=1e-3)


if __name__ == "__main__":
    unittest.main()
