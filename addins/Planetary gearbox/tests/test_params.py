import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen.bearing import lookup
from gen.dims import derive, rim_inner_radius
from gen.kits import default_params_for
from gen.inputs import (
    INPUT_SPECS,
    SELECTOR_IDS,
    kit_input_values,
    params_from_values,
    status_html,
    status_rows,
)
from gen.params import (
    MIN_EDGE_CHAMFER,
    Frame,
    default_params,
    frame_axes,
    frame_is_valid,
    gear_root_clearance,
    gear_root_depth,
    placement_frame,
    ratio,
)

REFERENCE_DIMS = {
    "orbit": 21,
    "planet_root": 12.98,
    "planet_tip": 15.48,
    "sun_root": 5.0,
    "ring_tip": 34.5,
    "ring_root": 37.0,
    "ring_outer": 44.1,
    "pin": 5.0,
    "shaft": 5.0,
    "shaft_bore": 5.1,
    "planet_pocket": 14.1,
    "cover_pocket": 14.1,
    "planet_lip": 10,
    "cover_lip": 10,
    "pin_collar": 7.4,
    "collar": 7.4,
    "cover_boss": 20.1,
    "cover_hub": 26.1,
    "boss": 11.0,
    "arm": 7.0,
    "bolt_circle": 40.55,
    "rim_inner": 36.85,
    "stage_pitch": 13,
    "ring_length": 14,
}


def near(test, got, want, tol=1e-12):
    test.assertLessEqual(abs(got - want), tol, f"got {got!r} want {want!r}")


def near_vec(test, got, want, tol=1e-12):
    for g, w in zip(got, want):
        near(test, g, w, tol)


class ParamsTest(unittest.TestCase):
    def test_derive_default(self):
        d = derive(default_params())
        for name, want in REFERENCE_DIMS.items():
            with self.subTest(name=name):
                near(self, getattr(d, name), want)
        self.assertEqual(d.planet_bearing, lookup("605ZZ"))
        self.assertEqual(d.shaft_bearing, lookup("605ZZ"))

    def test_derive_kits(self):
        cols = ("pin", "pin_collar", "planet_pocket", "planet_lip", "shaft", "shaft_bore", "collar", "cover_pocket",
                "cover_lip", "cover_boss", "cover_hub", "boss", "arm", "ring_outer", "rim_inner")
        table = {
            "planet605-shaft605": (5, 7.4, 14.1, 10, 5, 5.1, 7.4, 14.1, 10, 20.1, 26.1, 11, 7, 44.1, 36.85),
            "planet605-shaft608": (5, 7.4, 14.1, 10, 8, 8.1, 10.4, 22.1, 18, 28.1, 34.1, 11, 7, 43.6, 36.35),
            "planet608-shaft605": (8, 10.4, 22.1, 18, 5, 5.1, 7.4, 14.1, 10, 20.1, 26.1, 14, 10, 44.1, 36.85),
            "planet608-shaft608": (8, 10.4, 22.1, 18, 8, 8.1, 10.4, 22.1, 18, 28.1, 34.1, 14, 10, 43.6, 36.35),
        }
        for kit, want in table.items():
            d = derive(default_params_for(kit))
            for name, w in zip(cols, want):
                with self.subTest(kit=kit, name=name):
                    near(self, getattr(d, name), w)
            p = default_params_for(kit)
            self.assertEqual(d.planet_bearing, lookup(p.planet_bearing))
            self.assertEqual(d.shaft_bearing, lookup(p.shaft_bearing))

    def test_derive_unknown_bearing(self):
        for field in ("planet_bearing", "shaft_bearing"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    derive(dataclasses.replace(default_params(), **{field: "609ZZ"}))

    def test_rim_inner_radius(self):
        self.assertAlmostEqual(rim_inner_radius(40.55), 36.85, places=12)

    def test_gear_root_clearance(self):
        for m, want in ((0.5, 0.5), (1, 0.5), (2, 0.5), (4, 1.0)):
            with self.subTest(module=m):
                near(self, gear_root_clearance(m), want)
        near(self, gear_root_depth(1.0), 1.5)

    def test_new_defaults(self):
        self.assertEqual(default_params().bolt_hole_diameter, 2.6)
        self.assertEqual(default_params().bearing_clearance, 0.05)
        self.assertEqual(default_params().edge_chamfer, 0.5)
        self.assertEqual(MIN_EDGE_CHAMFER, 0.5)

    def test_ring_length_two_stages(self):
        d = derive(dataclasses.replace(default_params(), stages=2))
        near(self, d.ring_length, 27)

    def test_ratio(self):
        near(self, ratio(default_params()), 1 + 71 / 13)
        near(self, ratio(dataclasses.replace(default_params(), stages=2)), (1 + 71 / 13) ** 2)

    def test_bearing(self):
        self.assertEqual(lookup("605ZZ").width, 5)
        self.assertEqual((lookup("605ZZ").bore_diameter, lookup("605ZZ").outer_diameter), (5, 14))

    def test_input_specs(self):
        ids = [s.id for s in INPUT_SPECS]
        self.assertEqual(len(ids), len(set(ids)))
        # Placement is chosen by selection in the dialog, so the table holds the 26 gallery inputs, the ears box, the
        # split box and the sacrificial bridging box.
        self.assertEqual(len(ids), 29)
        self.assertEqual(ids[ids.index("bearing_clearance") + 1 :][:3], ["planet_bearing", "shaft_bearing", "seat_chamfer"])
        specs = {s.id: s for s in INPUT_SPECS}
        for sel in SELECTOR_IDS:
            self.assertEqual((specs[sel].kind, specs[sel].default, specs[sel].choices), ("choice", "605ZZ", ("605ZZ", "608ZZ")))
        self.assertEqual(ids.index("edge_chamfer"), ids.index("seat_chamfer") + 1)
        fields = {f.name for f in dataclasses.fields(default_params())}
        self.assertEqual(set(ids) - fields, {"ears"})
        # The ears box comes right before the ear inputs that it enables, in the gallery's table order.
        self.assertEqual(ids[ids.index("output_shaft_length") + 1 :][:3], ["ears", "ear_count", "ear_bore_diameter"])
        for spec in INPUT_SPECS:
            self.assertEqual(spec.needs, "ears" if spec.id.startswith("ear_") else "", spec.id)

    def test_ears_default_on(self):
        p = default_params()
        self.assertEqual((p.ear_count, p.ear_bore_diameter), (3, 4.0))
        specs = {s.id: s for s in INPUT_SPECS}
        self.assertEqual((specs["ears"].kind, specs["ears"].default), ("bool", 1))

    def test_params_from_values_ears_off(self):
        values = {s.id: s.default for s in INPUT_SPECS}
        values["pressure_angle"] = 20 * math.pi / 180
        values["ears"] = 0
        p = params_from_values(values)
        self.assertEqual(p.ear_count, 0)
        self.assertEqual(p, dataclasses.replace(default_params(), ear_count=0))
        values["ears"] = 1
        values["ear_count"] = 2
        values["ear_bore_diameter"] = 6
        p = params_from_values(values)
        self.assertEqual((p.ear_count, p.ear_bore_diameter), (2, 6.0))

    def test_split_pins_shafts_off_by_default(self):
        specs = {s.id: s for s in INPUT_SPECS}
        self.assertEqual((specs["split_pins_shafts"].kind, specs["split_pins_shafts"].default), ("bool", 0))
        self.assertFalse(default_params().split_pins_shafts)
        values = {s.id: s.default for s in INPUT_SPECS}
        values["pressure_angle"] = 20 * math.pi / 180
        self.assertFalse(params_from_values(values).split_pins_shafts)
        values["split_pins_shafts"] = 1
        self.assertTrue(params_from_values(values).split_pins_shafts)

    def test_sacrificial_bridging_off_by_default(self):
        specs = {s.id: s for s in INPUT_SPECS}
        self.assertEqual((specs["sacrificial_bridging"].kind, specs["sacrificial_bridging"].default), ("bool", 0))
        self.assertFalse(default_params().sacrificial_bridging)
        values = {s.id: s.default for s in INPUT_SPECS}
        values["pressure_angle"] = 20 * math.pi / 180
        self.assertFalse(params_from_values(values).sacrificial_bridging)
        values["sacrificial_bridging"] = 1
        self.assertTrue(params_from_values(values).sacrificial_bridging)

    def test_params_from_values_selectors(self):
        values = {s.id: s.default for s in INPUT_SPECS}
        values["pressure_angle"] = 20 * math.pi / 180
        values["planet_bearing"] = "608ZZ"
        values["shaft_bearing"] = "605ZZ"
        p = params_from_values(values)
        self.assertEqual((p.planet_bearing, p.shaft_bearing), ("608ZZ", "605ZZ"))

    def test_kit_input_values(self):
        self.assertEqual(
            kit_input_values("608ZZ", "608ZZ"), {"sun_teeth": 14.0, "planet_teeth": 28.0, "ring_teeth": 70.0}
        )
        self.assertEqual(kit_input_values("605ZZ", ""), {})

    def test_status_html(self):
        self.assertEqual(status_html([]), "")
        self.assertEqual(status_html(["a"]), "<b>Error:</b> a")
        two = status_html(["a", "b"])
        self.assertEqual(two.count("<b>Error:</b>"), 2)
        self.assertEqual(two, "<b>Error:</b> a<br><b>Error:</b> b")
        self.assertEqual(status_html(["x < y"]), "<b>Error:</b> x &lt; y")

    def test_status_rows(self):
        self.assertEqual([status_rows(["m"] * n) for n in (0, 1, 2, 20)], [2, 2, 4, 12])

    def test_params_from_values_defaults(self):
        values = {s.id: s.default for s in INPUT_SPECS}
        values["pressure_angle"] = 20 * math.pi / 180
        self.assertEqual(params_from_values(values), default_params())

    def test_frame_validity(self):
        self.assertTrue(frame_is_valid(Frame()))
        self.assertTrue(frame_is_valid(Frame((10, -5, 7), (0, 1, 0), (0, 0, 1))))
        self.assertFalse(frame_is_valid(Frame((0, 0, 0), (0, 0, 0), (0, 0, 0))))
        self.assertFalse(frame_is_valid(Frame((0, 0, 0), (1, 0, 0), (2, 0, 0))))
        self.assertFalse(frame_is_valid(Frame((float("nan"), 0, 0))))
        self.assertTrue(frame_is_valid(Frame((0, 0, 0), (1, 0, 0), (1, 1, 0))))

    def test_frame_axes(self):
        _, x, y, z = frame_axes(Frame((10, -5, 7), (0, 1, 0), (0, 0, 1)))
        near_vec(self, z, (1, 0, 0))
        near_vec(self, x, (0, 1, 0))
        near_vec(self, y, (0, 0, 1))
        _, _, y2, _ = frame_axes(Frame((0, 0, 0), (1, 0, 0), (1, 1, 0)))
        near_vec(self, y2, (0, 1, 0))
        with self.assertRaises(ValueError):
            frame_axes(Frame((0, 0, 0), (1, 0, 0), (2, 0, 0)))

class PlacementFrameTest(unittest.TestCase):
    def test_none_when_both_empty(self):
        self.assertIsNone(placement_frame(None, None))

    def test_default_axis_is_identity(self):
        f = placement_frame((1.0, 2.0, 3.0), None)
        origin, x, y, z = frame_axes(f)
        self.assertEqual(origin, (1.0, 2.0, 3.0))
        self.assertEqual((x, y, z), ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))

    def test_origin_defaults_to_world_origin(self):
        origin, _, _, z = frame_axes(placement_frame(None, (0.0, 0.0, -2.0)))
        self.assertEqual(origin, (0.0, 0.0, 0.0))
        self.assertAlmostEqual(z[2], -1.0)

    def test_axis_becomes_z_and_axes_are_orthonormal(self):
        for axis in ((1, 0, 0), (0, 1, 0), (0, -1, 0), (1, 1, 1), (0.2, 5, -0.3), (0, 0, -1), (3, 0, 4)):
            with self.subTest(axis=axis):
                f = placement_frame((0.0, 0.0, 0.0), tuple(float(a) for a in axis))
                self.assertTrue(frame_is_valid(f))
                _, x, y, z = frame_axes(f)
                n = math.sqrt(sum(a * a for a in axis))
                for got, want in zip(z, axis):
                    self.assertAlmostEqual(got, want / n)
                for u, v in ((x, y), (x, z), (y, z)):
                    self.assertAlmostEqual(sum(a * b for a, b in zip(u, v)), 0.0)

    def test_degenerate_axis_rejected(self):
        for axis in ((0.0, 0.0, 0.0), (float("nan"), 0.0, 1.0), (0.0, float("inf"), 0.0)):
            with self.subTest(axis=axis):
                with self.assertRaisesRegex(ValueError, "placement axis"):
                    placement_frame((0.0, 0.0, 0.0), axis)

    def test_non_finite_origin_rejected(self):
        with self.assertRaisesRegex(ValueError, "placement origin"):
            placement_frame((float("nan"), 0.0, 0.0), None)



if __name__ == "__main__":
    unittest.main()
