import math
import unittest

import _support  # noqa: F401
from gen.constants import (
    ARM_THICKNESS,
    BORE_CLEARANCE_MAX,
    BORE_CLEARANCE_MIN,
    MIN_ARM_THICKNESS,
    SLOT_ANGLE,
)
from gen.inputs import INPUT_SPECS, params_from_values
from gen.params import (
    CLOCKWISE,
    COUNTER_CLOCKWISE,
    SHAFTS,
    Params,
    default_params,
    direction_sign,
    placement_frame,
)
from gen.validate import ValidationError, derive, validate


class DefaultsTest(unittest.TestCase):
    def test_default_params(self):
        p = default_params()
        self.assertEqual((p.shaft, p.freewheel, p.bore_clearance, p.placement, p.adapter),
                         ("605ZZ", CLOCKWISE, 0.05, None, False))

    def test_shaft_presets(self):
        self.assertEqual([(s.name, s.diameter, s.flat_depth) for s in SHAFTS],
                         [("605ZZ", 5.0, 0.5), ("608ZZ", 8.0, 0.75), ("608ZZ-gearbox", 8.0, 0.5)])

    def test_direction_sign(self):
        self.assertEqual((direction_sign(CLOCKWISE), direction_sign(COUNTER_CLOCKWISE), direction_sign("")),
                         (-1.0, 1.0, 0.0))


class DeriveTest(unittest.TestCase):
    def test_bore(self):
        dm = derive(default_params())
        self.assertAlmostEqual(dm.bore_radius, 2.55)
        self.assertAlmostEqual(dm.bore_flat, 2.05)
        # The 5 mm loop is 15.8 mm: under the 20 mm that takes the plates' chamfer.
        self.assertAlmostEqual(dm.bore_loop, 15.8, delta=0.1)
        self.assertLess(dm.bore_loop, 20.0)
        dm8 = derive(Params(shaft="608ZZ"))
        self.assertGreaterEqual(dm8.bore_loop, 20.0)
        self.assertAlmostEqual(dm8.bore_loop, 25.1, delta=0.2)

    def test_pawl_values_of_instructions(self):
        dm = derive(default_params())
        self.assertAlmostEqual(dm.ramp_angle, 145.940, places=3)
        self.assertAlmostEqual(dm.ramp_distance, 13.338, places=3)
        self.assertAlmostEqual(dm.flank_distance, 12.938, places=3)
        self.assertAlmostEqual(dm.apex[0], 0.400, places=3)
        self.assertAlmostEqual(dm.apex[1], 15.347, places=3)
        self.assertAlmostEqual(dm.tip_center[0], 0.8, places=3)
        self.assertAlmostEqual(dm.tip_center[1], 14.594, places=3)
        self.assertAlmostEqual(dm.head_reach, 15.015, places=3)
        self.assertAlmostEqual(dm.head_travel, 1.265, places=3)
        self.assertAlmostEqual(dm.flank_end[0], 5.078, places=3)
        self.assertAlmostEqual(dm.flank_end[1], 12.184, places=3)
        self.assertAlmostEqual(dm.lock_end[0], 0.4, places=3)
        # sqrt(ArmInner^2 - 0.4^2) with ArmInner = 10.1 + 1.6. The gallery's instructions.md still prints 11.993, the
        # value for the old 10.4 core (docs/onewayclutch/gallery-discrepancies.md).
        self.assertAlmostEqual(dm.lock_end[1], 11.693, places=3)

    def test_arm_is_the_enforced_minimum_and_strain_is_capped(self):
        # Gallery TestOneWayClutchPawls: arm >= MinArmThickness, strain 3 t delta / (2 L^2) <= 0.012 at full travel.
        dm = derive(default_params())
        arm = dm.arm_outer - dm.arm_inner
        self.assertGreaterEqual(arm, MIN_ARM_THICKNESS - 1e-9)
        self.assertAlmostEqual(arm, ARM_THICKNESS)
        self.assertEqual((dm.core_radius, dm.boss_radius), (10.1, 10.4))
        self.assertAlmostEqual(dm.slot_width - dm.head_travel, 0.335, places=3)
        flank_angle = math.degrees(math.atan2(dm.flank_end[0], dm.flank_end[1]))
        span = (90.0 - flank_angle) - SLOT_ANGLE
        length = math.radians(span) * (dm.arm_inner + dm.arm_outer) / 2
        strain = 3 * arm * dm.head_travel / (2 * length * length)
        self.assertLessEqual(strain, 0.012)
        self.assertAlmostEqual(strain, 0.0112, delta=0.0006)

    def test_sign_follows_the_direction(self):
        self.assertEqual(derive(default_params()).sign, -1.0)
        self.assertEqual(derive(Params(freewheel=COUNTER_CLOCKWISE)).sign, 1.0)

    def test_sites(self):
        dm = derive(default_params())
        for s in dm.sites:
            self.assertEqual((s.length, s.head[2], s.dir, s.cavity), (16.0, 18.5, (0.0, 0.0, -1.0), 16.5))
            self.assertAlmostEqual(math.hypot(s.head[0], s.head[1]), 7.15)
        for s in dm.mount_sites:
            self.assertEqual((s.length, s.head[2], s.dir, s.cavity), (25.0, 26.0, (0.0, 0.0, -1.0), 25.25))
            self.assertAlmostEqual(math.hypot(s.head[0], s.head[1]), 21.6)
        for s in dm.face_sites:
            self.assertEqual((s.length, s.head[2], s.dir, s.cavity), (10.0, 20.0, (0.0, 0.0, 1.0), 7.75))
            self.assertAlmostEqual(math.hypot(s.head[0], s.head[1]), 9.5)
        for s in dm.sites + dm.mount_sites + dm.face_sites:
            self.assertEqual(s.validate(), "")


class DerivedRadiiTest(unittest.TestCase):
    """instructions.md "Derived dimensions": the radii grow with the bore radius."""

    FIELDS = ("core_radius", "bolt_circle", "slot_width", "arm_inner", "arm_outer", "tooth_tip", "tooth_root",
              "ring_counter", "ring_outer", "ear_circle", "ear_reach", "plate_radius", "boss_radius", "adapter_inner",
              "adapter_radius", "hub_chamfer", "growth")
    ZZ605 = (10.1, 7.15, 1.6, 11.7, 13.2, 13.75, 16.1, 17.1, 19.1, 21.6, 25.7, 16.7, 10.4, 3.5, 25.7, 0.25, 0.0)
    ZZ608_LOW = (10.85, 7.90, 1.6275, 12.4775, 13.9775, 14.5275, 16.8775, 17.8775, 19.8775, 22.3775, 26.4775, 17.4775,
                 11.15, 5.0, 26.4775, 0.212, 0.7775)
    ZZ608_HIGH = (11.3, 8.35, 1.645, 12.945, 14.445, 14.995, 17.345, 18.345, 20.345, 22.845, 26.945, 17.945, 11.6,
                  5.0, 26.945, 0.190, 1.245)

    def check(self, p, want, places):
        dm = derive(p)
        for name, value in zip(self.FIELDS, want):
            with self.subTest(radius=name):
                self.assertAlmostEqual(getattr(dm, name), value, places=places)

    def test_605zz_keeps_the_base_size_at_any_clearance(self):
        for c in (0.05, 0.5):
            self.check(Params(bore_clearance=c), self.ZZ605, 9)

    def test_8mm_presets_grow(self):
        for shaft in ("608ZZ", "608ZZ-gearbox"):
            self.check(Params(shaft=shaft, bore_clearance=0.05), self.ZZ608_LOW, 3)
            self.check(Params(shaft=shaft, bore_clearance=0.5), self.ZZ608_HIGH, 3)

    def test_walls_round_the_bolts_hold_on_every_preset_and_clearance(self):
        from gen.fasteners import HEAD_POCKET_RADIUS, HOLE_RADIUS, NUT_CAVITY_RADIUS

        reach = max(HEAD_POCKET_RADIUS, NUT_CAVITY_RADIUS * math.sqrt(3) / 2)
        for shaft in ("605ZZ", "608ZZ", "608ZZ-gearbox"):
            for c in (0.05, 0.2, 0.35, 0.5):
                with self.subTest(shaft=shaft, c=c):
                    dm = derive(Params(shaft=shaft, bore_clearance=c))
                    self.assertGreaterEqual(dm.core_radius - dm.bolt_circle - HOLE_RADIUS, 1.65 - 1e-9)
                    self.assertGreaterEqual(dm.bolt_circle - reach - dm.bore_radius, 1.65 - 1e-9)
                    self.assertGreaterEqual(dm.slot_width - dm.head_travel, 0.33 - 1e-9)
                    self.assertAlmostEqual(dm.arm_outer - dm.arm_inner, ARM_THICKNESS)
                    self.assertAlmostEqual(dm.tooth_tip - dm.arm_outer, 0.55)
                    self.assertAlmostEqual(dm.hub_chamfer, min(0.25, dm.arm_outer - dm.flank_distance - 0.01))

    def test_head_stays_an_exact_offset_of_its_gap(self):
        # 0.40 from the ramp at every size: the flank is HEAD_GAP inside the ramp line.
        for p in (Params(), Params(shaft="608ZZ", bore_clearance=0.5)):
            dm = derive(p)
            self.assertAlmostEqual(dm.ramp_distance - dm.flank_distance, 0.40)

    def test_sites_follow_the_derived_circles(self):
        dm = derive(Params(shaft="608ZZ", bore_clearance=0.5))
        for s in dm.sites:
            self.assertAlmostEqual(math.hypot(s.head[0], s.head[1]), dm.bolt_circle)
        for s in dm.mount_sites:
            self.assertAlmostEqual(math.hypot(s.head[0], s.head[1]), dm.ear_circle)


class ValidateTest(unittest.TestCase):
    def fails(self, message, **changes):
        with self.assertRaises(ValidationError) as cm:
            validate(Params(**changes))
        self.assertEqual(str(cm.exception), message)

    def test_unknown_shaft(self):
        self.fails('unknown shaft preset "x"; want one of 605ZZ, 608ZZ, 608ZZ-gearbox', shaft="x")

    def test_freewheel(self):
        self.fails("Freewheel must be Clockwise or CounterClockwise", freewheel="")

    def test_bore_clearance_range(self):
        msg = "BoreClearance must be finite, from 0.05 to 0.5 mm"
        for c in (0.049, 0.51, math.nan, math.inf):
            with self.subTest(c=c):
                self.fails(msg, bore_clearance=c)
        self.assertEqual((BORE_CLEARANCE_MIN, BORE_CLEARANCE_MAX), (0.05, 0.5))

    def test_no_clearance_limit_below_the_range(self):
        # The core grows until the walls round the bolts hold, so every preset builds at every allowed clearance.
        for shaft in ("605ZZ", "608ZZ", "608ZZ-gearbox"):
            for c in (0.05, 0.327, 0.5):
                validate(Params(shaft=shaft, bore_clearance=c))

    def test_derived_radii_rules(self):
        from gen.validate import derive_radii

        with self.assertRaises(ValidationError) as cm:
            derive_radii(10.0, 19.0)  # a bore this large leaves no room for the hub's face chamfer
        self.assertEqual(str(cm.exception), "the head flank leaves no room for the hub's face chamfer")

    def test_placement(self):
        from gen.params import Frame

        self.fails("Placement must be a valid frame", placement=Frame(u=(0.0, 0.0, 0.0)))

    def test_first_failure_wins(self):
        self.fails('unknown shaft preset "x"; want one of 605ZZ, 608ZZ, 608ZZ-gearbox', shaft="x", freewheel="",
                   bore_clearance=9.0)


class InputsTest(unittest.TestCase):
    def test_order_labels_and_defaults(self):
        self.assertEqual([(s.label, s.kind, s.default) for s in INPUT_SPECS], [
            ("Shaft", "choice", "605ZZ"), ("Freewheel", "choice", "Clockwise"),
            ("Bore clearance", "length", 0.05), ("Adapter ring", "bool", 0),
            ("Sacrificial bridging", "bool", 0)])
        self.assertEqual(INPUT_SPECS[0].choices, ("605ZZ", "608ZZ", "608ZZ-gearbox"))
        self.assertEqual(INPUT_SPECS[1].choices, ("Clockwise", "CounterClockwise"))

    def test_params_from_values_rounds_lengths(self):
        p = params_from_values({"shaft": "608ZZ", "freewheel": "CounterClockwise",
                                "bore_clearance": 0.05000000000000001 * 1.0000000001, "adapter": 1.0,
                                "sacrificial_bridging": 0.0})
        self.assertEqual((p.shaft, p.freewheel, p.bore_clearance, p.adapter, p.sacrificial_bridging),
                         ("608ZZ", "CounterClockwise", 0.05, True, False))

    def test_sacrificial_bridging_is_off_by_default_and_follows_its_box(self):
        self.assertFalse(Params().sacrificial_bridging)
        values = {"shaft": "605ZZ", "freewheel": "Clockwise", "bore_clearance": 0.05, "adapter": 0.0,
                  "sacrificial_bridging": 1.0}
        self.assertTrue(params_from_values(values).sacrificial_bridging)


class PlacementTest(unittest.TestCase):
    def test_none_when_empty(self):
        self.assertIsNone(placement_frame(None, None))


if __name__ == "__main__":
    unittest.main()
