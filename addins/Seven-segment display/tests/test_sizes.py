"""The model's sizes: gallery 9c9d5ab sizes every shape at 1.5 times the earlier builds, with no `Scale` constant.

The earlier builds (gallery 4dca996) wrote each shape as `Scale * base` with `Scale = 1.0`. The numbers below are those
base values. A shape is now written in mm at 1.5 times its base (params.go, instructions.md "Scale"); fits, clearances,
print limits, whole-layer plate thicknesses and purchased hardware are separate terms and keep their size in mm. The
tables here come from the gallery's steps.md and params.go, not from the add-in's code.
"""

import math
import unittest

import _support  # noqa: F401
from gen import clicker_params as cp
from gen import constants as k
from gen import flags_pivot as fv
from gen import flags_plates as fp
from gen import flags_rotor as fr
from gen import flags_slider as fs
from gen.params import default_params
from gen.truth import SEGMENTS, station
from gen.validate import derive

# (name, the earlier base value): each is now 1.5 times it.
RESIZED = {
    "SEGMENT_SPAN": 33.0, "TRAVEL": 3.0, "SHAFT_Z": 29.5, "STATION_PITCH": 11.0, "CAM_RADIUS": 23.5,
    "CAM_THICKNESS": 3.8, "HUB_RADIUS": 5.0, "OFF_RADIUS": 16.5, "ON_RADIUS": 19.5, "GROOVE_DEPTH": 1.9,
    "RAMP_ROUND": 2.5, "PIN_RADIUS": 1.5, "STEM_THICKNESS": 3.6, "WALL_THICKNESS": 8.0, "WALL_HALF_WIDTH": 23.4,
    "CRADLE_FROM": 80.0, "ROTOR_HALF_WIDTH": 3.75, "ROTOR_HALF_LENGTH": 12.25, "PIN_OFFSET": 1.5,
    "FLAG_PIN_RADIUS": 0.5, "REAR_COLLAR_RADIUS": 3.8, "SHAFT_CAM_RADIUS": 3.2, "SHAFT_CAM_FLAT": 2.7,
    "INSCRIPTION_WIDTH": 3.2, "INSCRIPTION_HEIGHT": 4.6, "INSCRIPTION_RADIUS": 14.0, "FRONT_INNER_Y": -49.5,
    "REAR_INNER_Y": 43.0, "GUIDE_FROM": 54.0, "GUIDE_THICK": 4.0, "RIB_HEIGHT": 4.0, "RIB_DEPTH": 10.0,
    "RIB_INNER": 16.4, "SHAFT_FLAT_HALF": 4.0, "SHAFT_FLAT_REACH": 8.0,
}

# Values that the gallery's steps.md "Exported constants" and tables give outright.
GIVEN = {
    "SEGMENT_SPAN": 49.5, "TRAVEL": 4.5, "FACE_Z": 132.25, "SHAFT_Z": 44.25, "STATION_PITCH": 16.5,
    "CAM_RADIUS": 35.25, "CAM_THICKNESS": 5.7, "HUB_RADIUS": 7.5, "OFF_RADIUS": 24.75, "ON_RADIUS": 29.25,
    "GROOVE_WIDTH": 5.3, "GROOVE_DEPTH": 2.85, "RAMP_ROUND": 3.75, "PIN_RADIUS": 2.25, "PIN_LENGTH": 3.0,
    "STEM_THICKNESS": 5.4, "WALL_THICKNESS": 12.0, "WALL_HALF_WIDTH": 35.1, "REAR_COLLAR_RADIUS": 5.7,
    "ROTOR_AXIS_Z": 124.0, "ROTOR_HALF_WIDTH": 5.625, "ROTOR_HALF_LENGTH": 18.375, "JOURNAL_RADIUS": 0.9,
    "PIN_OFFSET": 2.25, "WALL_TOP_Z": 121.25, "WALL_BOTTOM_Z": 4.5, "RIB_INNER": 24.6, "LEDGE_FROM": 74.75,
    "FLANGE_FROM": 113.75, "TOP_FROM": 124.25, "FRONT_LEDGE_DEEP": 26.35, "REAR_LEDGE_DEEP": 19.7,
    "CAM_BORE_RADIUS": 4.85, "CAM_BORE_FLAT": 4.1, "CAM_HUB_TOP": 10.75, "STATION_FACE": 3.25,
    "SHAFT_CAM_FLAT_FROM": -75.0, "SHAFT_CAM_FLAT_TO": 58.5, "SHAFT_STUB_FLAT_FROM": -101.95,
    "SHAFT_STUB_FLAT_TO": -86.6, "FRONT_WALL_OUTER_Y": -86.25, "HOUSING_BASE_Y": -86.5, "HOUSING_BASE_THICK": 6.0,
    "MARK_RADIUS": 13.5,  # not 15: the marks stay off the housing's flange
}

# The shaft's section from steps.md: (r, y) from the knob end to the rear end.
SHAFT = (
    (0.0, -100.95), (2.2, -100.95), (2.5, -100.65), (2.5, -84.1), (4.0, -81.5), (4.0, -74.0), (4.8, -74.0),
    (4.8, 59.0), (5.7, 60.5585), (5.7, 64.25), (4.0, 64.25), (4.0, 71.2), (3.7, 71.5), (0.0, 71.5),
)
SEAT = ((0.0, -1.0), (11.55, -1.0), (11.55, 0.0), (11.05, 0.5), (11.05, 7.0), (6.5, 7.0), (6.5, 11.5), (7.0, 12.0),
        (7.0, 13.0), (0.0, 13.0))


def _close(test, got, want, msg=None):
    test.assertEqual(len(got), len(want), msg)
    for g, w in zip(got, want):
        if isinstance(w, (tuple, list)):
            _close(test, g, w, msg)
        else:
            test.assertAlmostEqual(g, w, places=9, msg=msg)


class ResizedTest(unittest.TestCase):
    def test_there_is_no_scale_constant(self):
        self.assertFalse(hasattr(k, "SCALE"))

    def test_every_shape_is_1_5_times_its_earlier_size(self):
        for name, base in RESIZED.items():
            self.assertAlmostEqual(getattr(k, name), 1.5 * base, places=9, msg=name)

    def test_the_gallery_numbers(self):
        for name, want in GIVEN.items():
            self.assertAlmostEqual(getattr(k, name), want, places=9, msg=name)
        _close(self, k.SHAFT_MERIDIAN, SHAFT)
        _close(self, k.SEAT_MERIDIAN, SEAT)

    def test_fits_and_hardware_keep_their_size(self):
        for name, want in (("SEAM", 0.25), ("PRESS_FIT", 0.05), ("TIGHT_FIT", 0.25), ("REGULAR_FIT", 0.40),
                           ("LOOSE_FIT", 0.55), ("CRADLE_THICK", 4.0), ("TOP_THICK", 8.0), ("CAM_CHAMFER", 0.5),
                           ("RIB_ROUND", 0.5), ("WALL_CHAMFER", 0.5), ("CAM_MARK_RADIUS", 0.75),
                           ("BEARING_BORE", 8.0), ("BEARING_OUTER", 22.0), ("BEARING_WIDTH", 7.0),
                           ("SHAFT_JOURNAL", 4.0), ("SHAFT_STUB_RADIUS", 2.5)):
            self.assertEqual(getattr(k, name), want, name)

    def test_a_size_plus_a_fit_moves_the_size_and_keeps_the_fit(self):
        self.assertAlmostEqual(k.GROOVE_WIDTH - 2 * k.PIN_RADIUS, 0.8)  # the pin's diameter plus a 0.8 fit
        self.assertAlmostEqual(k.PIN_LENGTH - k.GROOVE_DEPTH, 0.15)  # the groove depth plus a 0.15 end gap
        self.assertAlmostEqual(k.CAM_BORE_RADIUS - k.SHAFT_CAM_RADIUS, 0.05)
        self.assertAlmostEqual(k.STATION_FACE - k.STEM_THICKNESS / 2, 0.55)
        self.assertAlmostEqual(k.JOURNAL_RADIUS - k.PIVOT_PIN_RADIUS, 0.2)
        self.assertAlmostEqual(fp.PEG_HOLE - fp.PEG_RADIUS, 0.05)
        self.assertAlmostEqual(fp.BORE_RADIUS - (4.875 * math.sqrt(2) + 0.75), 0.45, delta=0.001)  # swept 7.644 + 0.45
        # The guide slot is the stem's section plus the Tight fit; the cradle passage is the slider plus a Loose fit.
        xs = [abs(q.start[0]) for q in fp.slot_loop(0.0) if hasattr(q, "start")]
        self.assertAlmostEqual(max(xs), 5.25 + 0.25)
        passage = fp.cradle_passage(0, 0.0)
        self.assertAlmostEqual(passage[1], 6.825 + 0.55)
        self.assertAlmostEqual(passage[3], 5.775 + 0.55)
        # The rear column keeps a Loose fit from the rear top flange rib.
        self.assertAlmostEqual(k.RIB_INNER - (-fp.COLUMN_PEGS[1][0] + fp.COLUMN_HALF[1][0]), 0.55)

    def test_whole_layer_plates(self):
        self.assertAlmostEqual(k.CRADLE_THICK / 0.2, 20.0)
        self.assertAlmostEqual(k.TOP_THICK / 0.2, 40.0)
        self.assertAlmostEqual(k.TOP_FROM, k.CRADLE_FROM + k.CRADLE_THICK + 0.25)
        self.assertAlmostEqual(k.FACE_Z, k.TOP_FROM + k.TOP_THICK)
        self.assertAlmostEqual(k.ROTOR_AXIS_Z, k.CRADLE_FROM + k.CRADLE_THICK)
        self.assertAlmostEqual(fp.WINDOW_LENGTH, k.FACE_Z + 0.75 - fp.WINDOW_FROM)

    def test_the_bearing_is_a_608zz(self):
        self.assertEqual((k.BEARING_BORE, k.BEARING_OUTER, k.BEARING_WIDTH), (8.0, 22.0, 7.0))
        self.assertEqual((k.BEARING_SEAT_R, k.BEARING_RACE_R), (11.05, 6.0))
        self.assertEqual(k.SHAFT_JOURNAL, k.BEARING_BORE / 2)
        # The collar and the cam section stay inside the inner ring's face (0.3 and 1.2), the seat ends at the outer face.
        self.assertAlmostEqual(k.BEARING_RACE_R - k.REAR_COLLAR_RADIUS, 0.3)
        self.assertAlmostEqual(k.BEARING_RACE_R - k.SHAFT_CAM_RADIUS, 1.2)
        self.assertAlmostEqual(k.SEAT_MERIDIAN[7][1], k.WALL_THICKNESS)
        self.assertAlmostEqual(k.SEAT_MERIDIAN[-1][1], k.WALL_THICKNESS + 1.0)

    def test_the_shaft_follows_the_walls_and_the_bearings(self):
        self.assertAlmostEqual(k.SHAFT_CAM_FROM, k.FRONT_INNER_Y + 0.25)
        self.assertAlmostEqual(k.SHAFT_REAR_FROM, k.REAR_INNER_Y - 0.25)
        self.assertAlmostEqual(k.SHAFT_FRONT_END, k.FRONT_WALL_OUTER_Y - 14.7)
        self.assertAlmostEqual(k.SHAFT_STUB_STEP_FROM, k.FRONT_INNER_Y - k.BEARING_WIDTH - 0.25)
        step = math.degrees(math.atan2(k.SHAFT_JOURNAL - k.SHAFT_STUB_RADIUS, 2.6))
        self.assertAlmostEqual(step, 29.98, places=2)  # "a cone over the 1.5 step at 30 degrees or less"

    def test_stations_follow_the_pitch(self):
        self.assertEqual([station(s) for s in (3, 4, 2, 6, 1, 5, 0)], [-49.5, -33.0, -16.5, 0.0, 16.5, 33.0, 49.5])

    def test_the_click_indexer_keeps_its_size_and_moves_with_the_front_wall(self):
        # Every Y is an offset from the front wall's outer face: the earlier build's offsets from -57.5, unchanged except
        # for the housing's base (6.0 thick), the bezel, the button and its keys, which follow the 8.0 tall teeth.
        outer = k.FRONT_WALL_OUTER_Y
        for name, off in (("HUB_BASE_Y", -0.4), ("HUB_RIM_Y", -9.8), ("ROTOR_PLATE_Y", -13.4),
                          ("HOUSING_BEZEL_Y", -21.9), ("HOUSING_CROWN_Y", -15.0), ("BUTTON_UNDERSIDE_Y", -29.4)):
            self.assertAlmostEqual(getattr(cp, name) - outer, off, places=9, msg=name)
        self.assertAlmostEqual(cp.HOUSING_BASE_Y - outer, -0.25)
        self.assertEqual((cp.HUB_RADIUS, cp.SPRING_FREE_LENGTH, cp.ROTOR_PLATE_RADIUS), (10.5, 14.0, 14.2))
        self.assertEqual((cp.TOOTH_HEIGHT, cp.BUTTON_STROKE, cp.BUTTON_KEY_DROP), (8.0, 10.0, 7.8))
        # The button's underside is one tooth height above the rotor's teeth tips at rest.
        self.assertAlmostEqual(cp.ROTOR_PLATE_Y - cp.TOOTH_HEIGHT, cp.BUTTON_UNDERSIDE_Y + cp.TOOTH_HEIGHT)
        # The head ends flush with the bezel after the full stroke: it stands 31.9 above the wall at rest.
        self.assertAlmostEqual(outer - (cp.BUTTON_UNDERSIDE_Y - 2.5), 31.9)
        self.assertAlmostEqual(outer - (cp.BUTTON_UNDERSIDE_Y - 2.5) - cp.BUTTON_STROKE, outer - cp.HOUSING_BEZEL_Y)


class SizedPartsTest(unittest.TestCase):
    def test_flag_sizes(self):
        self.assertAlmostEqual(fs.SLIDER_STEM_FROM, fs.SLIDER_PIN_Z - 5.25)
        self.assertAlmostEqual(fs.SLIDER_PIN_Z, 69.0)
        self.assertAlmostEqual(fs.SLIDER_STEM_FROM, 63.75)
        self.assertAlmostEqual(fs.PIN_AXIS_Z, 121.375)
        self.assertAlmostEqual(fs.SLIDER_HEAD_TOP, 109.3)
        self.assertAlmostEqual(fs.BLADE_RIDGE_Z, 125.425)
        self.assertAlmostEqual(fs.BLADE_SHOULDER_Z, 124.525)
        self.assertAlmostEqual(fs.TONGUE_HULL_R - fs.FLAG_PIN_RADIUS, 0.1)
        self.assertAlmostEqual(fr.NOTCH_FLOOR, k.ROTOR_HALF_WIDTH - 0.8)  # the 0.8 shell is a print limit
        self.assertAlmostEqual(fr.SLOT_RADIUS - fs.FLAG_PIN_RADIUS, 0.2)
        self.assertAlmostEqual(fv.PIVOT_BLOCK_FROM - k.ROTOR_HALF_LENGTH, 0.25)
        self.assertAlmostEqual(fv.PIVOT_POCKET_HALF - fv.PIVOT_BLOCK_SIDE / 2, 0.05)
        # The block is as high as the cradle leaves it: 1.0 of cradle under the pocket, 0.05 of press.
        self.assertAlmostEqual(fv.PIVOT_BLOCK_HIGH, 5.9)

    def test_rotor_numbers(self):
        _close(self, fr.notches(0), [(-8.4, -0.3, 4.2)])
        _close(self, fr.notches(1), [(-14.1, -6.0, -1.5), (2.4, 10.5, 15.0)])
        for name, want in (("NOTCH_FLOOR", 4.825), ("YELLOW_HALF_WIDTH", 4.825), ("YELLOW_TIP_K", 19.825),
                           ("YELLOW_TIP_END", 17.4), ("ROTOR_SQUARE_HALF", 15.0), ("ROTOR_TIP_B", 18.525),
                           ("ROTOR_FLAT", -3.45), ("SLOT_START", 1.5), ("SLOT_END", 4.05), ("SLOT_RADIUS", 0.95),
                           ("PIVOT_BORE_FLOOR", 16.2), ("PIVOT_MOUTH_R", 1.395)):
            self.assertAlmostEqual(getattr(fr, name), want, places=9, msg=name)

    def test_plate_numbers(self):
        for name, want in (("TUBE_FROM", 116.2), ("BLADE_HOLE_TOP", 131.45), ("COLUMN_FROM", 87.0),
                           ("COLUMN_TOP", 118.725), ("PEG_HOLE", 2.3), ("BORE_RADIUS", 8.094), ("BORE_ROUND", 1.2),
                           ("BORE_END", 18.625), ("PASSAGE_FROM", 119.0), ("PASSAGE_LENGTH", 6.4),
                           ("BLADE_HOLE_FROM", 115.8), ("WINDOW_HALF_WIDTH", 4.825), ("WINDOW_CHAMFER", 19.525),
                           ("WINDOW_END", 17.544), ("WINDOW_FROM", 123.4)):
            self.assertAlmostEqual(getattr(fp, name), want, places=9, msg=name)
        _close(self, fp.COLUMN_PEGS, ((18.0, -67.5), (-20.325, 58.5)))
        _close(self, fp.TOP_PEGS, ((-18.0, -67.5), (21.75, 58.5)))
        _close(self, fp.COLUMN_HALF, ((3.75, 3.75), (3.725, 3.75)))
        yi = 5.0
        _close(self, fp.cradle_passage(0, yi), (-7.375, 7.375, yi - 13.825, yi + 6.325))
        _close(self, fp.cradle_passage(1, yi), (-5.8, 27.4, yi - 4.825, yi + 6.625))
        _close(self, fp.cradle_passage(4, yi), (-29.8, 5.8, yi - 4.825, yi + 6.625))
        _close(self, fp.blade_hole(1, yi), (13.05 - 0.25, 14.7 + 0.25, yi - 2.7 - 0.35, yi + 4.5 + 0.35))
        _close(self, fp.top_peg_meridian(), ((0.0, -2.4), (1.95, -2.4), (2.25, -2.1), (2.25, -0.75), (2.75, 0.0),
                                             (2.75, 0.1), (0.0, 0.1)))
        _close(self, fp.column_peg_meridian(), ((0.0, -0.1), (2.75, -0.1), (2.75, 0.0), (2.25, 0.5), (2.25, 3.6),
                                                (1.95, 3.9), (0.0, 3.9)))

    def test_guide_slot(self):
        pts = [c.start for c in fp.slot_loop(0.0) if hasattr(c, "start")]
        xs = sorted({round(abs(p[0]), 6) for p in pts})
        ys = sorted({round(p[1], 6) for p in pts})
        self.assertEqual(max(xs), 5.5)
        self.assertEqual((min(ys), max(ys)), (-2.95, 6.1))

    def test_slider_numbers(self):
        # Root r 1.05 and feet 1.2 (not 1.2 and 1.35): the gallery's kernel refuses the stem chamfer beside a root of
        # about 1.15 or more. The numbers are the gallery's.
        self.assertAlmostEqual(fs.TONGUE_ROOT_R, 1.05)
        self.assertAlmostEqual(fs.TONGUE_FOOT, 1.2)
        t = fs.tongue_for(0)
        loop = fs.tongue_outline(t.sl, t.sr, t.sc, t.zp)
        zh, zc = fs.SLIDER_HEAD_TOP, fs.SLIDER_HEAD_TOP + 1.05 - fs.TONGUE_ROOT_DIP
        first = loop[0].start
        self.assertAlmostEqual(first[0], t.sr + 1.2)
        self.assertAlmostEqual(first[1], zh - 1.2)
        ends = [p for c in loop for p in (c.start, c.end)]
        self.assertTrue(any(abs(p[0] - t.sr) < 1e-9 and abs(p[1] - zc) < 1e-9 for p in ends))  # the root's top end
        self.assertAlmostEqual(min(p[1] for p in ends), zh - 1.2)
        cutter = fs.tongue_cutter(t.ue, t.zp)
        self.assertAlmostEqual(cutter[-1][0], t.ue + 5.8)  # the pin's 5.4 plus 0.4
        self.assertAlmostEqual(cutter[-3][0], t.ue + 1.2)
        self.assertAlmostEqual(cutter[0][1], t.zp + 2.25)
        self.assertAlmostEqual(t.hull_length, t.ue + 5.6 - t.ua)

    def test_derived_sites_and_ramps(self):
        dm = derive(default_params())
        self.assertEqual(len(dm.sites), 10)
        self.assertEqual(station(3), -49.5)  # d is the first station
        self.assertEqual(station(6), 0.0)  # g is the middle one


class StemChamferTest(unittest.TestCase):
    """The 0.5 chamfers of the stem's two large faces: the long runs of their outer loops (gallery finishSlider)."""

    def test_chamfer_is_the_wall_chamfer(self):
        self.assertEqual(fs.STEM_CHAMFER, 0.5)

    def test_a_g_d_take_the_four_vertical_stem_edges(self):
        yi_h = k.STEM_THICKNESS / 2
        for s in (0, 3, 6):
            runs = fs.stem_chamfer_runs(s)
            self.assertEqual([len(r) for r in runs], [1, 1, 1, 1])
            seen = set()
            for (e,) in runs:
                self.assertIsNone(e.center)
                self.assertEqual(e.a[0], e.b[0])
                self.assertEqual(e.a[1], e.b[1])
                self.assertAlmostEqual(abs(e.a[0]), 5.25)
                self.assertAlmostEqual(abs(e.a[1] - station(s)), yi_h)
                self.assertAlmostEqual(e.a[2], fs.SLIDER_STEM_FROM)
                self.assertGreaterEqual(e.length, fs.LONG_EDGE_RUN)
                seen.add((e.a[0], e.a[1]))
            self.assertEqual(len(seen), 4)
            tops = sorted(round(e.b[2] - fs.SLIDER_HEAD_TOP, 6) for (e,) in runs)
            self.assertEqual(tops, [-3.0, -3.0, -2.475, -2.475])

    def test_b_to_f_take_the_long_runs_below_the_head_top_on_both_faces(self):
        h = k.STEM_THICKNESS / 2
        for s, want in ((1, [62.6, 45.55]), (2, [62.6, 45.55]), (4, [45.55, 65.0]), (5, [45.55, 65.0])):
            runs = fs.stem_chamfer_runs(s)
            self.assertEqual(len(runs), 4)
            for face_y in (station(s) - h, station(s) + h):
                lengths = sorted(round(sum(e.length for e in r), 2) for r in runs if r[0].a[1] == face_y)
                self.assertEqual(lengths, sorted(want), (s, face_y))
            for r in runs:
                self.assertGreaterEqual(sum(e.length for e in r), fs.LONG_EDGE_RUN)
                for e in r:
                    self.assertLessEqual(max(e.a[2], e.b[2]), fs.SLIDER_HEAD_TOP + 1e-6)  # nothing in the blade

    def test_a_run_is_a_chain_of_tangent_edges(self):
        for s in (1, 4):
            for run in fs.stem_chamfer_runs(s):
                for e, nxt in zip(run, run[1:]):
                    self.assertTrue({e.a, e.b} & {nxt.a, nxt.b})
                if len(run) == 3:  # the stem side, the round and the arm's underside
                    self.assertEqual([e.center is None for e in run], [True, False, True])

    def test_loop_runs_split_a_loop_at_its_corners(self):
        from gen import flags_common as fc

        square = fc.rect_loop(0.0, 10.0, 0.0, 10.0)
        self.assertEqual([len(r) for r in fs.loop_runs(square)], [1, 1, 1, 1])
        rounded = fc.rect_loop(0.0, 10.0, 0.0, 10.0, 1.0)
        # Lines meet the arcs of their rounds tangentially, so a loop with no corner is one run.
        self.assertEqual([len(r) for r in fs.loop_runs(rounded)], [8])
        self.assertEqual([len(r) for r in fs.loop_runs(fc.stadium_loop(0.0, 5.0, 1.0))], [4])


if __name__ == "__main__":
    unittest.main()
