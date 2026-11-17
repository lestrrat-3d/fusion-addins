import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import inputs
from gen.clutch.params import COUNTER_CLOCKWISE, Params as ClutchParams
from gen.constants import CLUTCH_MOUNT, LEFT_HAND, MOUNT_Z, RIGHT_HAND
from gen.params import (
    Frame,
    blade_angle,
    default_params,
    ear_bolt_angle,
    frame_axes,
    hand_for_freewheel,
    mount_frame,
    params_608zz,
    params_for_clutch,
    placement_frame,
    adapter_site,
    ear_bolt_angle,
    point_at,
)
from gen.validate import ValidationError, derive


class PointAtTest(unittest.TestCase):
    def test_world_frame_moves_back_along_z(self):
        self.assertEqual(point_at(None, 20.0).origin, (0.0, 0.0, -20.0))

    def test_moves_back_along_the_frame_axis(self):
        f = point_at(placement_frame((1.0, 2.0, 3.0), (0.0, 1.0, 0.0)), 18.5)
        for got, want in zip(f.origin, (1.0, -16.5, 3.0)):
            self.assertAlmostEqual(got, want)
        self.assertEqual(frame_axes(f)[3], frame_axes(placement_frame(None, (0.0, 1.0, 0.0)))[3])


class GalleryPlacementTest(unittest.TestCase):
    """The add-in's frames equal the gallery's (decad-gallery b98627c, params.go MountFrame and buildFrame)."""

    CLUTCH_ANCHOR_Z = 18.5 - MOUNT_Z  # onewayclutch.CoverTo - MountZ = -7.75

    @staticmethod
    def apply(f, v):
        o, x, y, z = frame_axes(f)
        return tuple(o[i] + x[i] * v[0] + y[i] * v[1] + z[i] * v[2] for i in range(3))

    @staticmethod
    def apply_dir(f, v):
        _, x, y, z = frame_axes(f)
        return tuple(x[i] * v[0] + y[i] * v[1] + z[i] * v[2] for i in range(3))

    def assert_frames_equal(self, got, want):
        for a, b in zip(frame_axes(got), frame_axes(want)):
            for p, q in zip(a, b):
                self.assertAlmostEqual(p, q, places=9)

    def test_clutch_mount_frame_equals_the_gallery_build_frame(self):
        for sel in (None, placement_frame((1.0, 2.0, 3.0), (0.0, 1.0, 0.0)),
                    placement_frame((-4.0, 5.0, 6.0), (1.0, 1.0, 1.0))):
            clutch = point_at(sel, 18.5)  # the clutch frame whose cover's outer face is the selected point
            # Gallery: MountFrame(clutch) is the placement point; buildFrame carries it back by ClutchAnchorZ.
            s, c = math.sin(math.pi), math.cos(math.pi)
            point = Frame(self.apply(clutch, (0.0, 0.0, 18.5)), self.apply_dir(clutch, (c, s, 0.0)),
                          self.apply_dir(clutch, (-s, c, 0.0)))
            want = Frame(self.apply(point, (0.0, 0.0, -self.CLUTCH_ANCHOR_Z)), point.u, point.v)
            self.assert_frames_equal(mount_frame(clutch), want)
            # The selected point is the gallery's placement point.
            ref = sel if sel is not None else Frame()
            for p, q in zip(point.origin, ref.origin):
                self.assertAlmostEqual(p, q, places=9)

    def test_shaft_mount_frame_equals_the_gallery_build_frame(self):
        for sel in (None, placement_frame((1.0, 2.0, 3.0), (0.0, 1.0, 0.0))):
            ref = sel if sel is not None else Frame()
            want = Frame(self.apply(ref, (0.0, 0.0, -20.0)), ref.u, ref.v)
            self.assert_frames_equal(point_at(sel, 20.0), want)

    def test_ear_bolts_and_adapter_sites_equal_the_gallery(self):
        self.assertEqual([round(math.degrees(ear_bolt_angle(k))) for k in (1, 2, 3)], [270, 30, 150])
        for k in (1, 2):  # the gallery's AdapterSites[k-1] uses EarBoltAngle(k+1)
            a = ear_bolt_angle(k + 1)
            self.assertAlmostEqual(adapter_site(k).head[0], 9.5 * math.cos(a), places=9)
            self.assertAlmostEqual(adapter_site(k).head[1], 9.5 * math.sin(a), places=9)
        # The bore flat (-Y in the fan frame) points where the clutch's shaft flat (+Y) does.
        v = self.apply_dir(mount_frame(None), (0.0, -1.0, 0.0))
        for got, want in zip(v, (0.0, 1.0, 0.0)):
            self.assertAlmostEqual(got, want, places=9)


class DerivedValuesTest(unittest.TestCase):
    """The gallery's "Presets and defaults" table."""

    def check(self, p, want):
        dm = derive(p)
        got = (dm.bore_radius, dm.bore_flat, dm.bore_flat_width, dm.bore_loop, dm.shaft_flat_width,
               dm.set_screw_tip, dm.set_screw_head, dm.counterbore_floor)
        for a, b, tol in zip(got, want, (1e-9, 1e-9, 5e-5, 2e-2, 5e-5, 1e-9, 1e-9, 1e-9)):
            self.assertAlmostEqual(a, b, delta=tol, msg=f"{got} != {want}")

    def at_128(self, **changes):
        return dataclasses.replace(default_params(), rotor_diameter=128.0, **changes)

    def test_605zz(self):
        # rho_h and rho_f: 9.95 and 7.55 at 128 (M2 x 6), 13.95 and 11.55 at 192 and 224 (M2 x 10).
        self.check(self.at_128(), (2.55, 2.05, 3.0332, 15.81, 3.0, 1.95, 9.95, 7.55))
        self.check(default_params(), (2.55, 2.05, 3.0332, 15.81, 3.0, 1.95, 13.95, 11.55))

    def test_608zz(self):
        self.check(dataclasses.replace(params_608zz(), rotor_diameter=128.0),
                   (4.05, 3.30, 4.6957, 25.12, 4.6637, 3.20, 11.20, 8.80))
        self.check(params_608zz(), (4.05, 3.30, 4.6957, 25.12, 4.6637, 3.20, 15.20, 12.80))

    def test_regular_bore(self):
        p = dataclasses.replace(default_params(), bore_clearance=0.35)
        # At 128 the gallery's table still prints 9.65 and 7.25 (M2 x 6), but its rule (the longest standard length whose
        # head stays inside the round face) picks M2 x 10 for this bore (tip 1.65, head 13.65 <= 13.87), as at 192.
        # The add-in follows the rule (docs/turbinefan/gallery-discrepancies.md).
        self.check(dataclasses.replace(p, rotor_diameter=128.0), (2.85, 2.35, 3.2249, 17.70, 3.0, 1.65, 13.65, 11.25))
        self.check(p, (2.85, 2.35, 3.2249, 17.70, 3.0, 1.65, 13.65, 11.25))

    def test_set_screw_length_follows_the_hub(self):
        # The longest standard length whose head stays inside the round face: M2 x 6 at 128, M2 x 10 at 192 and 224.
        for d, want in ((128.0, 6.0), (192.0, 10.0), (224.0, 10.0)):
            dm = derive(dataclasses.replace(default_params(), rotor_diameter=d))
            self.assertEqual((dm.set_screw_bolt, dm.set_screw_site.length), (want, want))
            reach = math.sqrt(dm.size.hub_radius**2 - 1.9**2)
            self.assertLessEqual(dm.set_screw_head, reach)

    def test_sites(self):
        dm = derive(self.at_128())
        s = dm.set_screw_site
        self.assertEqual((s.head, s.dir, s.corner, s.length), ((0.0, -9.95, 4.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), 6.0))
        self.assertAlmostEqual(s.cavity, 4.3)  # the slot spans f_b + 1.6 to f_b + 3.6
        self.assertAlmostEqual(s.tip(), 8.0)
        for k, b in enumerate(dm.blade_sites, start=1):
            a = blade_angle(k)
            self.assertAlmostEqual(b.head[0], 9.5 * math.cos(a))
            self.assertAlmostEqual(b.head[1], 9.5 * math.sin(a))
            self.assertEqual((b.head[2], b.dir, b.length, b.cavity), (20.0, (0.0, 0.0, -1.0), 16.0, 15.6))
        for a in dm.adapter_sites:
            self.assertEqual((a.head[2], a.dir, a.length, a.cavity), (-6.25, (0.0, 0.0, 1.0), 10.0, 7.75))
            self.assertAlmostEqual(a.tip(), 12.0)
            self.assertAlmostEqual(a.cavity_far(), 9.75)

    def test_sites_at_192(self):
        dm = derive(default_params())
        s = dm.set_screw_site
        self.assertEqual((s.head, s.length), ((0.0, -13.95, 4.0), 10.0))
        self.assertAlmostEqual(s.cavity, 8.3)
        self.assertAlmostEqual(s.tip(), 12.0)
        for k, b in enumerate(dm.blade_sites, start=1):
            a = blade_angle(k)
            self.assertAlmostEqual(b.head[0], 12.825 * math.cos(a))
            self.assertAlmostEqual(b.head[1], 12.825 * math.sin(a))
            self.assertEqual((b.head[2], b.dir, b.length), (30.0, (0.0, 0.0, -1.0), 25.0))
            self.assertAlmostEqual(b.cavity, 24.6)
            self.assertAlmostEqual(b.tip(), 27.0)  # 3 above the back face (z 30 - 27)

    def test_angles(self):
        self.assertEqual([round(math.degrees(blade_angle(k))) for k in (1, 2, 3)], [90, 210, 330])
        # Turned 180 degrees from the clutch, the ear bolts stay midway between the blades, in another order.
        self.assertEqual([round(math.degrees(ear_bolt_angle(k))) for k in (1, 2, 3)], [270, 30, 150])
        self.assertEqual(sorted(round(math.degrees(ear_bolt_angle(k))) for k in (1, 2, 3)), [30, 150, 270])


class ValidationTest(unittest.TestCase):
    def message(self, **changes):
        with self.assertRaises(ValidationError) as cm:
            derive(dataclasses.replace(default_params(), **changes))
        return str(cm.exception)

    def test_presets_and_clutch_mount_are_valid(self):
        derive(default_params())
        derive(params_608zz())
        derive(dataclasses.replace(default_params(), mount=CLUTCH_MOUNT, hand=LEFT_HAND))

    def test_positive_and_finite(self):
        for field, name in (("shaft_diameter", "ShaftDiameter"), ("flat_depth", "FlatDepth"),
                            ("bore_clearance", "BoreClearance"), ("blade_pitch", "BladePitch"),
                            ("rotor_diameter", "RotorDiameter")):
            for bad in (0.0, -1.0, math.nan, math.inf):
                self.assertEqual(self.message(**{field: bad}), f"{name} must be finite and positive")

    def test_flat_depth_limits(self):
        self.assertEqual(self.message(flat_depth=1.5), "FlatDepth must be at most a quarter of ShaftDiameter")
        # FlatDepth 0.2 fails the shaft's flat width, 0.25 passes it and fails the bore's flat width.
        self.assertIn("shaft's flat at least 2 mm wide", self.message(flat_depth=0.2))
        self.assertIn("bore's flat at least 2.8 mm wide", self.message(flat_depth=0.25))
        derive(dataclasses.replace(default_params(), flat_depth=0.42))

    def test_bore_clearance_range(self):
        want = "BoreClearance must be from 0.05 to 0.5 mm"
        self.assertEqual(self.message(bore_clearance=0.04), want)
        self.assertEqual(self.message(bore_clearance=0.51), want)

    def test_mount_hand_and_pitch(self):
        self.assertEqual(self.message(mount=2), "Mount must be ShaftMount or ClutchMount")
        self.assertEqual(self.message(hand=2), "Hand must be RightHand or LeftHand")
        self.assertEqual(self.message(blade_pitch=math.radians(9)), "BladePitch must lie from 10 to 40 degrees")
        self.assertEqual(self.message(blade_pitch=math.radians(41)), "BladePitch must lie from 10 to 40 degrees")
        derive(dataclasses.replace(default_params(), blade_pitch=math.radians(10)))
        derive(dataclasses.replace(default_params(), blade_pitch=math.radians(40)))

    def test_rotor_diameter_range(self):
        want = "RotorDiameter must lie in [128, 224] mm"
        self.assertEqual(self.message(rotor_diameter=127.9), want)
        self.assertEqual(self.message(rotor_diameter=224.1), want)
        derive(dataclasses.replace(default_params(), rotor_diameter=128.0))
        derive(dataclasses.replace(default_params(), rotor_diameter=224.0))

    def test_rotor_range_comes_before_the_shaft_rules(self):
        self.assertEqual(self.message(rotor_diameter=100.0, flat_depth=1.5),
                         "RotorDiameter must lie in [128, 224] mm")

    def test_shaft_diameter_limit(self):
        # r_b at most 4.1 at 128 (socket floors at 5.7) and 6.095 at 192 (7.695): the 8 mm shaft passes at the least
        # clearance and fails at 0.15 only at 128.
        derive(dataclasses.replace(params_608zz(), rotor_diameter=128.0))
        self.assertIn("less than a 1.6 mm wall to the blade sockets", self.message(
            shaft_diameter=8.0, flat_depth=0.75, bore_clearance=0.15, rotor_diameter=128.0))
        derive(dataclasses.replace(params_608zz(), bore_clearance=0.15))
        derive(dataclasses.replace(default_params(), shaft_diameter=12.0, flat_depth=1.0))  # r_b 6.05
        self.assertIn("less than a 1.6 mm wall to the blade sockets", self.message(shaft_diameter=12.2, flat_depth=1.0))

    def test_placement(self):
        self.assertIn("valid frame", self.message(placement=dataclasses.replace(placement_frame(None, (0, 0, 1)),
                                                                                 u=(0.0, 0.0, 0.0))))


class InputsTest(unittest.TestCase):
    def test_labels_and_order(self):
        self.assertEqual([s.label for s in inputs.INPUT_SPECS],
                         ["Shaft bore diameter", "Flat depth", "Bore clearance", "Rotor diameter", "Blade pitch", "Hand",
                          "Mount",
                          "Clutch shaft", "Clutch freewheel", "Clutch bore clearance", "Sacrificial bridging"])

    def test_bridging_box_is_a_fan_input_in_both_mounts_off_by_default(self):
        spec = next(s for s in inputs.INPUT_SPECS if s.id == "sacrificial_bridging")
        self.assertEqual((spec.kind, spec.default), ("bool", 0))
        self.assertNotIn("sacrificial_bridging", inputs.CLUTCH_IDS)
        self.assertNotIn("sacrificial_bridging", inputs.SHAFT_MOUNT_IDS)

    def test_bridging_values_build_the_fan_and_clutch_params(self):
        values = {s.id: s.default for s in inputs.INPUT_SPECS}
        values["blade_pitch"] = math.radians(values["blade_pitch"])
        values["mount"] = "Clutch"
        off = inputs.params_from_values(values)
        self.assertFalse(off.sacrificial_bridging)
        self.assertFalse(off.clutch.sacrificial_bridging)
        values["sacrificial_bridging"] = 1.0
        p = inputs.params_from_values(values)
        self.assertTrue(p.sacrificial_bridging)
        self.assertTrue(p.clutch.sacrificial_bridging)
        self.assertTrue(p.clutch.adapter)
        values["mount"] = "Shaft"
        shaft = inputs.params_from_values(values)
        self.assertIsNone(shaft.clutch)
        self.assertTrue(shaft.sacrificial_bridging)

    def test_defaults_give_default_params(self):
        values = {s.id: s.default for s in inputs.INPUT_SPECS}
        values["blade_pitch"] = math.radians(values["blade_pitch"])
        p = inputs.params_from_values(values)
        self.assertEqual((p.shaft_diameter, p.flat_depth, p.bore_clearance, p.hand, p.mount), (5.0, 0.5, 0.05, 0, 0))
        self.assertAlmostEqual(p.blade_pitch, math.radians(25), places=8)

    def test_choices(self):
        values = {s.id: s.default for s in inputs.INPUT_SPECS}
        values["blade_pitch"] = 0.5
        values.update(hand="Left hand")
        p = inputs.params_from_values(values)
        self.assertEqual((p.hand, p.mount, p.clutch), (LEFT_HAND, 0, None))
        values["hand"] = ""
        self.assertEqual(inputs.params_from_values(values).hand, -1)

    def test_shaft_mount_ignores_the_clutch_inputs(self):
        values = {s.id: s.default for s in inputs.INPUT_SPECS}
        values.update(clutch_shaft="608ZZ", clutch_freewheel=COUNTER_CLOCKWISE)
        p = inputs.params_from_values(values)
        self.assertEqual((p.shaft_diameter, p.hand, p.clutch), (5.0, RIGHT_HAND, None))

    def test_clutch_mount_takes_shaft_hand_and_bore_from_the_clutch(self):
        values = {s.id: s.default for s in inputs.INPUT_SPECS}
        values["blade_pitch"] = 0.5
        values.update(mount="Clutch", clutch_shaft="608ZZ", clutch_freewheel=COUNTER_CLOCKWISE,
                      clutch_bore_clearance=0.1, shaft_diameter=6.0, flat_depth=0.4, bore_clearance=0.3,
                      hand="Right hand")
        p = inputs.params_from_values(values)
        self.assertEqual((p.mount, p.shaft_diameter, p.flat_depth, p.bore_clearance, p.hand),
                         (CLUTCH_MOUNT, 8.0, 0.75, 0.05, LEFT_HAND))
        self.assertEqual(p.blade_pitch, 0.5)
        self.assertEqual((p.clutch.shaft, p.clutch.freewheel, p.clutch.bore_clearance, p.clutch.adapter),
                         ("608ZZ", COUNTER_CLOCKWISE, 0.1, True))
        derive(p)

    def test_clutch_bore_clearance_is_rounded_like_the_other_lengths(self):
        values = {s.id: s.default for s in inputs.INPUT_SPECS}
        values["blade_pitch"] = math.radians(25)
        values.update(mount="Clutch", clutch_bore_clearance=0.05000000000000001 * 1.0000000001)
        p = inputs.params_from_values(values)
        self.assertEqual(p.clutch.bore_clearance, 0.05)
        derive(p)

    def test_clutch_inputs_are_checked_by_the_clutch_rules(self):
        values = {s.id: s.default for s in inputs.INPUT_SPECS}
        values["blade_pitch"] = math.radians(25)
        values.update(mount="Clutch", clutch_shaft="nope")
        with self.assertRaises(ValidationError) as cm:
            derive(inputs.params_from_values(values))
        self.assertIn("unknown shaft preset", str(cm.exception))
        values.update(clutch_shaft="605ZZ", clutch_bore_clearance=0.9)
        with self.assertRaises(ValidationError) as cm:
            derive(inputs.params_from_values(values))
        self.assertTrue(str(cm.exception).startswith("clutch: BoreClearance"))


class ClutchMountTest(unittest.TestCase):
    def test_hand_follows_freewheel(self):
        self.assertEqual(hand_for_freewheel("Clockwise"), RIGHT_HAND)
        self.assertEqual(hand_for_freewheel(COUNTER_CLOCKWISE), LEFT_HAND)

    def test_params_for_clutch_matches_the_gallery(self):
        p = params_for_clutch(ClutchParams(shaft="608ZZ", freewheel=COUNTER_CLOCKWISE))
        self.assertEqual((p.shaft_diameter, p.flat_depth, p.bore_clearance, p.hand, p.mount),
                         (8.0, 0.75, 0.05, LEFT_HAND, CLUTCH_MOUNT))
        self.assertAlmostEqual(p.blade_pitch, math.radians(25))
        self.assertTrue(p.clutch.adapter)
        self.assertIsNone(p.clutch.placement)

    def test_mount_frame_without_a_clutch_frame(self):
        f = mount_frame(None)
        self.assertEqual(f.origin, (0.0, 0.0, MOUNT_Z))
        self.assertEqual(MOUNT_Z, 26.25)
        # Turned 180 degrees about Z: the fan's X and Y axes are the clutch's -X and -Y.
        self.assertAlmostEqual(f.u[0], -1.0)
        self.assertAlmostEqual(f.u[1], 0.0)
        self.assertAlmostEqual(f.v[0], 0.0)
        self.assertAlmostEqual(f.v[1], -1.0)

    def test_the_fan_flat_matches_the_clutch_flat(self):
        # The clutch's shaft flat faces +Y in the clutch frame (its bore flat is at y = +f_b); the fan's bore flat is at
        # y = -f_b in the fan frame. Seated on the clutch, both must point the same way.
        from gen.clutch.validate import derive as clutch_derive

        self.assertGreater(clutch_derive(ClutchParams()).bore_flat, 0.0)
        _, fan_x, fan_y, _ = frame_axes(mount_frame(None))
        flat = tuple(-c for c in fan_y)  # the fan's -Y in the clutch frame
        for got, want in zip(flat, (0.0, 1.0, 0.0)):
            self.assertAlmostEqual(got, want)

    def test_adapter_bolts_sit_on_clutch_face_holes_and_ear_bolts_between_blades(self):
        from gen.clutch.validate import derive as clutch_derive

        def to_clutch(pt):  # a fan-frame point in the clutch frame
            _, x, y, z = frame_axes(mount_frame(None))
            o = mount_frame(None).origin
            return tuple(o[i] + x[i] * pt[0] + y[i] * pt[1] + z[i] * pt[2] for i in range(3))

        faces = clutch_derive(ClutchParams()).face_sites
        for k, site in enumerate(derive(default_params()).adapter_sites, start=1):
            head = to_clutch(site.head)
            want = faces[k].head  # fan bolts 1 and 2 sit on face holes 2 and 3
            for i in range(3):
                self.assertAlmostEqual(head[i], want[i], places=9)
        # Every ear bolt lies midway between two blades.
        blades = sorted(math.degrees(blade_angle(k)) % 360 for k in (1, 2, 3))
        for k in (1, 2, 3):
            a = math.degrees(ear_bolt_angle(k)) % 360
            gaps = sorted(min(abs(a - b), 360 - abs(a - b)) for b in blades)
            self.assertAlmostEqual(gaps[0], 60.0)
            self.assertAlmostEqual(gaps[1], 60.0)
        # Each ear bolt lies on its clutch ear's angle: the fan angle plus the 180 degree turn is the ear's angle.
        for k, ear in enumerate((90.0, 210.0, 330.0), start=1):
            diff = (math.degrees(ear_bolt_angle(k)) + 180.0 - ear + 180.0) % 360.0 - 180.0
            self.assertAlmostEqual(diff, 0.0, places=6)

    def test_mount_frame_sits_on_the_clutch_frame(self):
        # A clutch turned so that its +Z is the world +X axis and placed at (10, 0, 0).
        c = placement_frame((10.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        f = mount_frame(c)
        o, x, y, z = frame_axes(f)
        self.assertAlmostEqual(o[0], 10.0 + MOUNT_Z)
        self.assertAlmostEqual(o[1], 0.0)
        self.assertAlmostEqual(o[2], 0.0)
        self.assertAlmostEqual(z[0], 1.0)  # both frames share +Z
        # The fan's X axis is the clutch's X axis turned 180 degrees about the shared Z.
        _, cx, cy, _ = frame_axes(c)
        for i in range(3):
            self.assertAlmostEqual(x[i], -cx[i])

    def test_mount_frame_rejects_an_invalid_frame(self):
        with self.assertRaises(ValueError):
            mount_frame(Frame(u=(0.0, 0.0, 0.0)))


class PlacementTest(unittest.TestCase):
    def test_none_and_z(self):
        self.assertIsNone(placement_frame(None, None))
        f = placement_frame((1.0, 2.0, 3.0), None)
        self.assertEqual(f.origin, (1.0, 2.0, 3.0))

    def test_zero_axis_rejected(self):
        with self.assertRaises(ValueError):
            placement_frame(None, (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
