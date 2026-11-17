"""Runs the build order against a mocked Fusion: placement, naming, containers and the body-count rule.

The part builders are replaced by a fake that returns bodies in the current container's component, so this file checks
the orchestration only."""

import dataclasses
import importlib
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import bodies
from gen.clutch.params import Params as ClutchParams
from gen.clutch.constants import COVER_TO
from gen.constants import CLUTCH_MOUNT
from gen.params import default_params, mount_frame, params_for_clutch, placement_frame, point_at

_ADDINS = _support.ADDINS
_PKG = "Turbine fan.commands.turbinefan"
_MODULES = tuple(f"{_PKG}.{m}" for m in (
    "build", "checks", "fusion", "parts", "clutch_build", "clutch_checks", "clutch_parts"))


HUB_LENGTH = 30.0  # the default rotor, 192 mm: Size.hub_length

class FakeBody:
    def __init__(self, world, comp, part=""):
        self.comp = comp
        self.part = part
        self.name = ""
        self.isSolid = True
        world.alive.append(self)


class World:
    def __init__(self):
        self.alive = []
        self.calls = []


class FakeBodies:
    def __init__(self, items):
        self._items = list(items)

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class FakeOcc:
    def __init__(self, component):
        self.component = component


class FakeOccurrences:
    def __init__(self, world):
        self._world = world
        self._items = []

    def addNewComponent(self, transform):
        occ = FakeOcc(FakeComponent(self._world))
        occ.transform = transform
        self._items.append(occ)
        return occ

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class FakeComponent:
    def __init__(self, world, name=""):
        self._world = world
        self.name = name
        self.occurrences = FakeOccurrences(world)

    @property
    def bRepBodies(self):
        return FakeBodies([b for b in self._world.alive if b.comp is self])


class FakeLog:
    enabled = False

    def __init__(self):
        self.records = []

    def write(self, event, fields):
        self.records.append((event, dict(fields)))


def make_design(adsk, world):
    top = FakeComponent(world)
    design = mock.MagicMock()
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    design.rootComponent.occurrences.addNewComponent.return_value.component = top
    return design, top


class GlueBuildTest(unittest.TestCase):
    def run_build(self, stray_part=None, solid=True, clutch=None, **changes):
        p = dataclasses.replace(default_params(), **changes)
        if clutch is not None:
            p = dataclasses.replace(params_for_clutch(clutch), placement=changes.get("placement"),
                                    **{k: v for k, v in changes.items() if k == "sacrificial_bridging"})
        adsk = mock.MagicMock()
        world = World()

        def build_hub(ctx):
            world.calls.append(("build", "Hub", ctx.comp))
            return FakeBody(world, ctx.comp, "Hub")

        def build_blades(ctx):
            world.calls.append(("build", "Blades", ctx.comp))
            return [FakeBody(world, ctx.comp, f"Blade {k}") for k in (1, 2, 3)]

        def build_fastener(ctx, name):
            world.calls.append(("build", name, ctx.comp))
            if name == stray_part:
                FakeBody(world, ctx.comp, name)  # a leftover tool body
            body = FakeBody(world, ctx.comp, name)
            body.isSolid = solid
            return body

        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in _MODULES:
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            build = importlib.import_module(f"{_PKG}.build")
            design, top = make_design(adsk, world)
            self.top, self.fusion, self.world = top, fusion, world
            with mock.patch.object(build.parts, "build_hub", build_hub), \
                    mock.patch.object(build.parts, "build_blades", build_blades), \
                    mock.patch.object(build.parts, "build_fastener", build_fastener), \
                    mock.patch.object(fusion, "frame_matrix", return_value="matrix") as frame, \
                    mock.patch.object(build.clutch_build, "build_clutch") as build_clutch, \
                    mock.patch.object(build.checks, "run_all") as run_all:
                self.frame = frame
                self.build_clutch = build_clutch
                design_calls = design.rootComponent.occurrences.addNewComponent
                build_clutch.side_effect = lambda *a: world.calls.append(
                    ("clutch", design_calls.call_count))
                self.design = design
                build.build_fan(design, p, FakeLog())
            self.ctx = run_all.call_args.args[0]
            return world, run_all.call_args.args[1]

    def test_default_build_names_and_count(self):
        world, built = self.run_build()
        self.assertEqual([name for name, _ in built], list(bodies.body_names(0)))
        self.assertEqual(len(world.alive), 12)
        self.assertEqual(sorted(b.name for b in world.alive), sorted(bodies.body_names(0)))
        self.assertTrue(all(b.isSolid for b in world.alive))

    def test_clutch_mount_builds_adapter_bolts_and_nuts(self):
        world, built = self.run_build(clutch=ClutchParams())
        self.assertEqual([name for name, _ in built], list(bodies.body_names(CLUTCH_MOUNT)))
        self.assertEqual(len(world.alive), 14)
        names = [b.name for b in world.alive]
        self.assertIn("Adapter Bolt 2", names)
        self.assertNotIn("Set Screw", names)

    def test_bodies_built_in_their_container(self):
        world, _ = self.run_build()
        builds = [(n, comp) for _, n, comp in (c for c in world.calls if c[0] == "build")]
        self.assertEqual([n for n, _ in builds][:2], ["Hub", "Blades"])
        self.assertEqual([n for n, _ in builds][2:], list(bodies.bolts(0) + bodies.nuts(0)))
        self.assertIs(builds[0][1], self.ctx.container_comps["Hub"])
        self.assertIs(builds[1][1], self.ctx.container_comps["Blades"])
        for name, comp in builds[2:]:
            self.assertIs(comp, self.ctx.container_comps[bodies.container_of(name)])

    def test_containers(self):
        for mount, clutch in ((0, None), (CLUTCH_MOUNT, ClutchParams())):
            world, _ = self.run_build(clutch=clutch)
            top = self.top
            self.assertEqual(top.name, "Turbine fan")
            self.assertEqual(top.bRepBodies.count, 0)
            self.assertEqual(
                [top.occurrences.item(i).component.name for i in range(top.occurrences.count)], list(bodies.CONTAINERS)
            )
            count, found = self.fusion.component_tree(top)
            self.assertEqual(count, 0)
            got_top, results = bodies.check_tree(found, count, mount)
            self.assertTrue(got_top.ok, got_top.detail)
            self.assertTrue(all(r.ok for r in results), [(r.name, r.detail) for r in results if not r.ok])
            self.assertEqual(len(found), 4)

    def test_placement_transform(self):
        # The selected point is the hub's front face, so the fan frame sits HUB_LENGTH behind it.
        self.run_build()
        self.frame.assert_called_once_with(point_at(None, HUB_LENGTH))
        frame = placement_frame((1.0, 2.0, 3.0), (0.0, 0.0, 1.0))
        self.run_build(placement=frame)
        self.frame.assert_called_once_with(point_at(frame, HUB_LENGTH))
        self.design.rootComponent.occurrences.addNewComponent.assert_called_once_with("matrix")

    def test_shaft_mount_builds_no_clutch(self):
        self.run_build()
        self.build_clutch.assert_not_called()

    def test_clutch_mount_builds_the_clutch_first_and_places_the_fan_on_it(self):
        frame = placement_frame((1.0, 2.0, 3.0), (0.0, 1.0, 0.0))
        self.run_build(clutch=ClutchParams(shaft="608ZZ", freewheel="CounterClockwise", bore_clearance=0.1),
                       placement=frame)
        self.build_clutch.assert_called_once()
        design, clutch_p, _ = self.build_clutch.call_args.args
        self.assertIs(design, self.design)
        # The selections place the clutch; the clutch has its adapter; the fan sits on it through the mount frame.
        self.assertEqual((clutch_p.shaft, clutch_p.freewheel, clutch_p.bore_clearance, clutch_p.adapter),
                         ("608ZZ", "CounterClockwise", 0.1, True))
        # The selected point is where the clutch cover ends, so the clutch frame sits COVER_TO behind it.
        clutch_frame = point_at(frame, COVER_TO)
        self.assertEqual(clutch_p.placement, clutch_frame)
        self.frame.assert_called_once_with(mount_frame(clutch_frame))
        # The clutch is built before the fan's own component is made.
        self.assertEqual([c for c in self.world.calls if c[0] == "clutch"], [("clutch", 0)])
        self.design.rootComponent.occurrences.addNewComponent.assert_called_once_with("matrix")

    def test_the_fans_bridging_box_decides_the_clutch_layers(self):
        # Directive: one `Sacrificial bridging` box for the hub and the clutch parts.
        self.run_build(clutch=ClutchParams(sacrificial_bridging=False), sacrificial_bridging=True)
        self.assertTrue(self.build_clutch.call_args.args[1].sacrificial_bridging)
        self.run_build(clutch=ClutchParams(sacrificial_bridging=True), sacrificial_bridging=False)
        self.assertFalse(self.build_clutch.call_args.args[1].sacrificial_bridging)

    def test_clutch_mount_without_clutch_inputs_is_rejected(self):
        with self.assertRaises(Exception) as cm:
            self.run_build(mount=CLUTCH_MOUNT)
        self.assertIn("needs the clutch inputs", str(cm.exception))
        self.design.rootComponent.occurrences.addNewComponent.assert_not_called()

    def test_invalid_clutch_is_rejected_before_any_component(self):
        with self.assertRaises(ValueError):
            self.run_build(clutch=ClutchParams(bore_clearance=0.9))
        self.build_clutch.assert_not_called()

    def test_invalid_params_rejected_before_any_component(self):
        with self.assertRaises(ValueError):
            self.run_build(shaft_diameter=17.0)
        self.design.rootComponent.occurrences.addNewComponent.assert_not_called()

    def test_non_parametric_rejected(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in _MODULES:
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            build = importlib.import_module(f"{_PKG}.build")
            design = mock.MagicMock()
            design.designType = "direct"
            with self.assertRaises(fusion.BuildError) as cm:
                build.build_fan(design, default_params(), FakeLog())
            self.assertIn("parametric", str(cm.exception))
            design.rootComponent.occurrences.addNewComponent.assert_not_called()

    def test_not_solid_rejected(self):
        with self.assertRaises(Exception) as cm:
            self.run_build(solid=False)
        self.assertIn("not a solid", str(cm.exception))

    def test_stray_body_fails_count(self):
        with self.assertRaises(Exception) as cm:
            self.run_build(stray_part="Set Screw")
        self.assertEqual(str(cm.exception), "expected 12 bodies, found 13")


if __name__ == "__main__":
    unittest.main()
