import math
import unittest

import _support  # noqa: F401
from gen import bodies, edgefinish
from gen.edgefinish import (
    CHAMFER,
    INNER_MULTI,
    OUTER,
    PLATE,
    RIM,
    chamfer_volume,
    finish_planes,
    keep_loop,
)
from gen.layout import layout
from gen.params import default_params
from gen.sections import lip_centres, pendulum_outline, plate_outline
from gen.spring import loop_length

G = layout(default_params())
CENTRES = lip_centres(G)


class FinishPlanesTest(unittest.TestCase):
    def test_constants(self):
        self.assertEqual((CHAMFER, edgefinish.LARGE_FACE_AREA, edgefinish.LONG_EDGE_RUN), (0.5, 400.0, 20.0))
        self.assertEqual(edgefinish.CIRCLE_TOL, 0.01)

    def test_table(self):
        table = {
            "back_plate": [(-6.0, PLATE, 6), (0.0, PLATE, 6)],
            "front_plate": [(28.0, PLATE, 6), (34.0, PLATE, 6)],
            "escape_wheel": [(22.0, INNER_MULTI, 6), (25.0, INNER_MULTI, 6)],
            "anchor": [(21.0, OUTER, 1), (26.0, OUTER, 1)],
            "pendulum": [(37.75, RIM, 2), (43.75, RIM, 2)],
            "mainspring": [(0.0, OUTER, 1), (6.0, OUTER, 1)],
        }
        for part, want in table.items():
            got = [(f.z, f.rule, f.loops) for f in finish_planes(part)]
            self.assertEqual(got, want, part)
        for part in bodies.PARTS:
            if part not in table:
                self.assertEqual(finish_planes(part), [], part)


class KeepLoopTest(unittest.TestCase):
    def test_outer(self):
        self.assertTrue(keep_loop(OUTER, True, 9, None, None, []))
        self.assertFalse(keep_loop(OUTER, False, 4, None, None, []))

    def test_inner_multi(self):
        self.assertTrue(keep_loop(INNER_MULTI, False, 4, None, None, []))
        self.assertFalse(keep_loop(INNER_MULTI, False, 1, (0.0, 0.0, 2.55), None, []))
        self.assertFalse(keep_loop(INNER_MULTI, True, 4, None, None, []))

    def test_plate(self):
        keep = lambda *a: keep_loop(PLATE, *a, CENTRES)  # noqa: E731
        self.assertTrue(keep(True, 12, None, None))
        self.assertTrue(keep(False, 6, None, None))
        self.assertFalse(keep(False, 4, None, None))  # a 2-edge D socket or a 4-edge slot
        self.assertFalse(keep(False, 2, None, None))
        px, py = G.axis_p
        self.assertTrue(keep(False, 1, (px, py, 7.05), None))
        self.assertTrue(keep(False, 1, (0.0, 0.0, 5.005), None))
        self.assertFalse(keep(False, 1, (0.0, 0.0, 2.25), None))  # mount hole
        self.assertFalse(keep(False, 1, (50.0, 74.0, 5.0), None))  # pillar footprint, off every axis
        self.assertFalse(keep(False, 1, (0.0, 0.0, 7.2), None))
        self.assertFalse(keep(False, 1, None, (0.0, 5.0)))

    def test_rim(self):
        keep = lambda *a: keep_loop(RIM, *a, [(0.0, 0.0)])  # noqa: E731
        self.assertTrue(keep(True, 8, None, None))
        self.assertTrue(keep(False, 1, None, (7.05, 0.0)))
        self.assertTrue(keep(False, 1, None, (0.0, -5.004)))
        self.assertFalse(keep(False, 1, None, (6.0, 0.0)))
        self.assertFalse(keep(False, 4, None, (7.05, 0.0)))  # the slot has several edges
        self.assertFalse(keep(False, 1, None, None))

    def test_unknown_rule(self):
        with self.assertRaises(ValueError):
            keep_loop("nope", True, 1, None, None, [])


class ChamferVolumeTest(unittest.TestCase):
    def test_parts_without_planes(self):
        for part in ("crutch", "great_wheel", "bearing", "bolt"):
            self.assertEqual(chamfer_volume(G, part), 0.0)

    def test_pendulum(self):
        c = CHAMFER
        rim = lambda r, inside: c * c / 2 * 2 * math.pi * (r - c / 3 if inside else r + c / 3)  # noqa: E731
        want = 2 * c * c / 2 * loop_length(pendulum_outline(G)) + rim(5.0, False) + rim(7.05, False)
        self.assertAlmostEqual(chamfer_volume(G, "pendulum"), want, places=6)

    def test_back_plate_is_dominated_by_the_outline(self):
        c = CHAMFER
        outline = 2 * c * c / 2 * loop_length(plate_outline(98.0))
        v = chamfer_volume(G, "back_plate")
        self.assertGreater(v, outline)
        self.assertLess(v, 3 * outline)

    def test_positive(self):
        for part in ("front_plate", "escape_wheel", "anchor", "mainspring"):
            self.assertGreater(chamfer_volume(G, part), 0.0, part)


if __name__ == "__main__":
    unittest.main()
