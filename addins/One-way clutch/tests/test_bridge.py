import math
import unittest

import _support  # noqa: F401
from gen import bodies, bridge, expected, probes
from gen.fasteners import HOLE_RADIUS
from gen.params import Params
from gen.validate import derive


def setup(**kw):
    p = Params(**kw)
    return p, derive(p)


class LayerTest(unittest.TestCase):
    def test_layer_is_one_printed_layer_reaching_into_the_wall(self):
        self.assertEqual(bridge.BRIDGE_THICKNESS, 0.3)
        self.assertAlmostEqual(bridge.layer_radius(), HOLE_RADIUS + 0.1, places=12)

    def test_back_plate_layers_sit_on_each_nut_pocket_roof(self):
        # Outer face (z 0) down: the hex pocket runs z 0 to 2.0 and the bolt hole continues above it.
        _, dm = setup()
        layers = bridge.back_plate_layers(dm)
        self.assertEqual(len(layers), 3)
        for layer, site in zip(layers, dm.sites):
            lo, hi = layer.z_range()
            self.assertAlmostEqual(lo, 2.0, places=9)
            self.assertAlmostEqual(hi, 2.3, places=9)
            self.assertEqual(layer.center()[:2], (site.head[0], site.head[1]))

    def test_cover_layers_sit_on_each_head_pocket_roof(self):
        # Outer face (z 18.5) down, so -Z is up: the head pocket runs z 16.5 to 18.5, the hole continues to 14.5.
        _, dm = setup()
        layers = bridge.cover_layers(dm)
        self.assertEqual(len(layers), 3)
        for layer in layers:
            lo, hi = layer.z_range()
            self.assertAlmostEqual(lo, 16.2, places=9)
            self.assertAlmostEqual(hi, 16.5, places=9)

    def test_adapter_layers_are_the_three_ear_head_pockets_only(self):
        # Front face (z 26) down: the ear head pockets run z 24 to 26 and the holes continue to 20. The face head
        # pockets open on the rear face (z 20), which is on top, so they have no roof.
        _, dm = setup(adapter=True)
        layers = bridge.adapter_layers(dm)
        self.assertEqual(len(layers), 3)
        for layer, site in zip(layers, dm.mount_sites):
            lo, hi = layer.z_range()
            self.assertAlmostEqual(lo, 23.7, places=9)
            self.assertAlmostEqual(hi, 24.0, places=9)
            self.assertEqual(layer.site, site)
        self.assertFalse({s for s in dm.face_sites} & {layer.site for layer in layers})

    def test_each_layer_ends_inside_its_body(self):
        p, dm = setup(adapter=True, sacrificial_bridging=True)
        for name in (bodies.BACK_PLATE, bodies.COVER, bodies.ADAPTER):
            lo, hi = expected.body_bounds(name, p, dm)[2], expected.body_bounds(name, p, dm)[5]
            for layer in bridge.layers_for(name, p, dm):
                self.assertGreaterEqual(layer.z_range()[0], lo)
                self.assertLessEqual(layer.z_range()[1], hi)

    def test_no_layers_unless_the_box_is_checked(self):
        p, dm = setup(adapter=True)
        for name in bodies.body_names(True):
            self.assertEqual(bridge.layers_for(name, p, dm), [])
            self.assertEqual(bridge.bridge_volume(name, p, dm), 0.0)

    def test_only_the_back_plate_the_cover_and_the_adapter_are_bridged(self):
        p, dm = setup(adapter=True, sacrificial_bridging=True)
        bridged = [n for n in bodies.body_names(True) if bridge.layers_for(n, p, dm)]
        self.assertEqual(set(bridged), {bodies.BACK_PLATE, bodies.COVER, bodies.ADAPTER})

    def test_adapter_has_no_layers_without_the_adapter(self):
        p, dm = setup(sacrificial_bridging=True)
        self.assertEqual(bridge.layers_for(bodies.ADAPTER, p, dm), [])


class VolumeAndProbeTest(unittest.TestCase):
    def test_volume_is_three_hole_sections_per_bridged_body(self):
        p, dm = setup(adapter=True, sacrificial_bridging=True)
        one = math.pi * HOLE_RADIUS**2 * 0.3
        for name in (bodies.BACK_PLATE, bodies.COVER, bodies.ADAPTER):
            self.assertAlmostEqual(bridge.bridge_volume(name, p, dm), 3 * one, places=9)
        self.assertEqual(bridge.bridge_volume(bodies.HUB, p, dm), 0.0)

    def test_expected_volume_adds_the_layers_only_when_checked(self):
        off, dm_off = setup(adapter=True)
        on, dm_on = setup(adapter=True, sacrificial_bridging=True)
        for name in (bodies.BACK_PLATE, bodies.COVER, bodies.ADAPTER):
            base = expected.body_volume(name, off, dm_off)
            more = expected.body_volume(name, on, dm_on)
            self.assertAlmostEqual(more.value - base.value, bridge.bridge_volume(name, on, dm_on), places=9)
            self.assertEqual(more.tol, base.tol)
        for name in (bodies.HUB, bodies.RING):
            self.assertEqual(expected.body_volume(name, on, dm_on), expected.body_volume(name, off, dm_off))

    def test_bounds_do_not_change(self):
        off, dm_off = setup(adapter=True)
        on, dm_on = setup(adapter=True, sacrificial_bridging=True)
        for name in bodies.body_names(True):
            self.assertEqual(expected.body_bounds(name, on, dm_on), expected.body_bounds(name, off, dm_off))

    def test_probes_cover_every_layer_when_enabled(self):
        p, dm = setup(adapter=True, sacrificial_bridging=True)
        found = probes.part_probes(p, dm)
        for name in (bodies.BACK_PLATE, bodies.COVER, bodies.ADAPTER):
            layers = [q for q in found[name] if "bridge layer" in q.label]
            self.assertEqual(len(layers), 3, name)
            self.assertTrue(all(q.expect == probes.INSIDE for q in layers))
        for name in (bodies.HUB, bodies.RING):
            self.assertEqual([q for q in found[name] if "bridge layer" in q.label], [])

    def test_no_bridge_probes_by_default(self):
        p, dm = setup(adapter=True)
        for plist in probes.part_probes(p, dm).values():
            self.assertEqual([q for q in plist if "bridge layer" in q.label], [])

    def test_layer_probes_stay_clear_of_the_other_probes(self):
        # A hole probe on the same axis must not sit inside a layer, or one of the two would be wrong.
        p, dm = setup(adapter=True, sacrificial_bridging=True)
        for name, plist in probes.part_probes(p, dm).items():
            for layer in bridge.layers_for(name, p, dm):
                lo, hi = layer.z_range()
                cx, cy, _ = layer.center()
                for q in plist:
                    if "bridge layer" in q.label:
                        continue
                    same_axis = math.hypot(q.point[0] - cx, q.point[1] - cy) < HOLE_RADIUS
                    self.assertFalse(same_axis and lo - 0.01 <= q.point[2] <= hi + 0.01, (name, q.label))


if __name__ == "__main__":
    unittest.main()
