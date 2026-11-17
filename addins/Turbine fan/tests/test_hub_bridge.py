"""Sacrificial bridge layers of the hub: where they sit, how many, and what they add to the volume and the probes."""

import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import bridge, expected, probes
from gen.constants import CLUTCH_MOUNT
from gen.fasteners import HOLE_RADIUS
from gen.params import default_params, params_for_clutch
from gen.clutch.params import Params as ClutchParams
from gen.validate import derive


def setup(**kw):
    p = dataclasses.replace(default_params(), **kw)
    return p, derive(p)


# (rotor diameter, hub length, blade bolt cavity): the hub's front face is at z = hub length.
SIZES = ((128.0, 20.0, 15.6), (192.0, 30.0, 24.6), (224.0, 35.0, 24.6))


class HubLayerTest(unittest.TestCase):
    def test_blade_pocket_layers_sit_above_each_head_pocket_roof(self):
        # Front face (z = hub length) down: the head pocket runs 2 mm back from it and the bolt hole continues above it
        # (toward z 0): z 17.7 to 18.0 at 128, 27.7 to 28.0 at 192, 32.7 to 33.0 at 224.
        for d, length, _ in SIZES:
            _, dm = setup(rotor_diameter=d)
            layers = bridge.blade_pocket_layers(dm)
            self.assertEqual(len(layers), 3)
            for layer, site in zip(layers, dm.blade_sites):
                lo, hi = layer.z_range()
                self.assertAlmostEqual(lo, length - 2.3, places=9)
                self.assertAlmostEqual(hi, length - 2.0, places=9)
                self.assertEqual(layer.center()[:2], (site.head[0], site.head[1]))

    def test_blade_slot_layers_sit_above_each_nut_slot_ceiling(self):
        # The nut slot's ceiling is its far face (hub length - cavity - 2): z 2.4 at 128, 3.4 at
        # 192 and 8.4 at 224. The bolt hole continues above it, to the back face.
        for d, length, cavity in SIZES:
            _, dm = setup(rotor_diameter=d)
            layers = bridge.blade_slot_layers(dm)
            self.assertEqual(len(layers), 3)
            ceiling = length - cavity - 2.0
            for layer in layers:
                lo, hi = layer.z_range()
                self.assertAlmostEqual(lo, ceiling - 0.3, places=9)
                self.assertAlmostEqual(hi, ceiling, places=9)
        _, dm = setup(rotor_diameter=192.0)
        self.assertAlmostEqual(bridge.blade_slot_layers(dm)[0].z_range()[1], 3.4, places=9)

    def test_adapter_slot_layers_sit_above_each_nut_slot_ceiling(self):
        # The adapter nut slot runs z 1.5 to 3.5 and the hole continues above its ceiling at z 1.5, to the back face.
        _, dm = setup()
        layers = bridge.adapter_slot_layers(dm)
        self.assertEqual(len(layers), 2)
        for layer, site in zip(layers, dm.adapter_sites):
            lo, hi = layer.z_range()
            self.assertAlmostEqual(lo, 1.2, places=9)
            self.assertAlmostEqual(hi, 1.5, places=9)
            self.assertEqual(layer.center()[:2], (site.head[0], site.head[1]))

    def test_every_layer_lies_in_a_hole_above_a_wider_part_in_the_material_range(self):
        for d, length, _ in SIZES:
            _, dm = setup(rotor_diameter=d)
            for layer in bridge.all_hub_layers(dm):
                lo, hi = layer.z_range()
                self.assertAlmostEqual(hi - lo, 0.3, places=9)
                self.assertTrue(0.0 < lo and hi < length)
                # The layer's centre line is at a bolt hole: the blade bolt circle (9.5 j) or the adapter bolts' (9.5).
                x, y, _ = layer.center()
                self.assertIn(round(math.hypot(x, y), 9), (round(dm.size.blade_bolt_at, 9), 9.5))

    def test_eight_layers_when_checked_none_otherwise(self):
        on, dm_on = setup(sacrificial_bridging=True)
        off, dm_off = setup()
        self.assertEqual(len(bridge.hub_layers(on, dm_on)), 8)
        self.assertEqual(bridge.hub_layers(off, dm_off), [])

    def test_layers_are_the_same_in_both_mounts(self):
        shaft, dm_shaft = setup(sacrificial_bridging=True)
        clutch = params_for_clutch(ClutchParams(sacrificial_bridging=True))
        self.assertEqual(clutch.mount, CLUTCH_MOUNT)
        dm_clutch = derive(clutch)
        self.assertEqual(len(bridge.hub_layers(shaft, dm_shaft)), len(bridge.hub_layers(clutch, dm_clutch)))

    def test_volume_adds_the_hole_sections(self):
        on, dm = setup(sacrificial_bridging=True)
        self.assertAlmostEqual(bridge.bridge_volume(on, dm), 8 * math.pi * HOLE_RADIUS**2 * 0.3, places=9)
        off, dm_off = setup()
        self.assertEqual(bridge.bridge_volume(off, dm_off), 0.0)


class HubExpectedTest(unittest.TestCase):
    def test_hub_volume_grows_by_the_layers_only_when_checked(self):
        off, dm_off = setup()
        on, dm_on = setup(sacrificial_bridging=True)
        v_off = expected.body_volume("Hub", off, dm_off)
        v_on = expected.body_volume("Hub", on, dm_on)
        self.assertEqual(v_off.value, 29974.6904)  # the default size, 192
        self.assertAlmostEqual(v_on.value - v_off.value, bridge.bridge_volume(on, dm_on), places=9)
        self.assertEqual(v_on.tol, v_off.tol)

    def test_bounds_and_the_blades_do_not_change(self):
        off, dm_off = setup()
        on, dm_on = setup(sacrificial_bridging=True)
        self.assertEqual(expected.body_bounds("Hub", on, dm_on), expected.body_bounds("Hub", off, dm_off))
        self.assertEqual(expected.body_volume("Blade 1", on, dm_on), expected.body_volume("Blade 1", off, dm_off))
        for name in ("Blade Bolt 1", "Blade Nut 1"):
            self.assertEqual(expected.body_volume(name, on, dm_on), expected.body_volume(name, off, dm_off))


class HubProbeTest(unittest.TestCase):
    def layer_probes(self, p, dm):
        return [q for q in probes.part_probes(p, dm)["Hub"] if q.label.startswith("hub bridge layer")]

    def test_checked_puts_each_layer_inside_the_material(self):
        p, dm = setup(sacrificial_bridging=True)
        found = self.layer_probes(p, dm)
        self.assertEqual(len(found), 8)
        self.assertTrue(all(q.expect == probes.INSIDE for q in found))
        self.assertEqual([q.point for q in found], [layer.center() for layer in bridge.all_hub_layers(dm)])

    def test_unchecked_leaves_each_hole_open(self):
        p, dm = setup()
        found = self.layer_probes(p, dm)
        self.assertEqual(len(found), 8)
        self.assertTrue(all(q.expect == probes.OUTSIDE for q in found))

    def test_no_other_body_gets_layer_probes(self):
        p, dm = setup(sacrificial_bridging=True)
        for name, plist in probes.part_probes(p, dm).items():
            if name != "Hub":
                self.assertFalse([q for q in plist if "bridge" in q.label], name)


if __name__ == "__main__":
    unittest.main()
