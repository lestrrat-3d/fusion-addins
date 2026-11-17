"""Runs the build order against a mocked Fusion: placement, naming, containers and the body-count rule.

The part builders are replaced by a fake that returns one body in the current container's component, so this file
checks the orchestration only."""

import dataclasses
import importlib
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

from gen.clutch import bodies
from gen.clutch.params import Params, placement_frame

_ADDINS = _support.ADDINS
_PKG = "Turbine fan.commands.turbinefan"


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
    def run_build(self, stray_part=None, solid=True, **changes):
        p = dataclasses.replace(Params(), **changes)
        adsk = mock.MagicMock()
        world = World()

        def build_part(ctx, name):
            world.calls.append(("build", name, ctx.comp))
            if name == stray_part:
                FakeBody(world, ctx.comp, name)  # a leftover tool body
            body = FakeBody(world, ctx.comp, name)
            body.isSolid = solid
            return body

        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in (f"{_PKG}.clutch_build", f"{_PKG}.clutch_checks", f"{_PKG}.fusion", f"{_PKG}.clutch_parts"):
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            build = importlib.import_module(f"{_PKG}.clutch_build")
            design, top = make_design(adsk, world)
            self.top, self.fusion, self.world = top, fusion, world
            with mock.patch.object(build.parts, "build_part", build_part), \
                    mock.patch.object(fusion, "frame_matrix", return_value="matrix") as frame, \
                    mock.patch.object(build.checks, "run_all") as run_all:
                self.frame = frame
                self.design = design
                build.build_clutch(design, p, FakeLog())
            self.ctx = run_all.call_args.args[0]
            return world, run_all.call_args.args[1]

    def test_default_build_names_and_count(self):
        world, built = self.run_build()
        self.assertEqual([name for name, _ in built], list(bodies.BODY_NAMES))
        self.assertEqual(len(world.alive), 10)
        self.assertEqual(sorted(b.name for b in world.alive), sorted(bodies.BODY_NAMES))
        self.assertTrue(all(b.isSolid for b in world.alive))

    def test_adapter_adds_seven_bodies_in_a_sixth_container(self):
        world, built = self.run_build(adapter=True)
        self.assertEqual([name for name, _ in built], list(bodies.body_names(True)))
        self.assertEqual(len(world.alive), 17)
        self.assertEqual(
            [self.top.occurrences.item(i).component.name for i in range(self.top.occurrences.count)],
            list(bodies.ADAPTER_CONTAINERS),
        )

    def test_bodies_built_in_order_in_their_container(self):
        world, _ = self.run_build(adapter=True)
        builds = [c for c in world.calls if c[0] == "build"]
        self.assertEqual([c[1] for c in builds], list(bodies.body_names(True)))
        for _, name, comp in builds:
            self.assertIs(comp, self.ctx.container_comps[bodies.BODY_CONTAINER[name]])

    def test_containers(self):
        world, _ = self.run_build()
        top = self.top
        self.assertEqual(top.name, "One-way clutch")
        self.assertEqual(top.bRepBodies.count, 0)
        self.assertEqual(
            [top.occurrences.item(i).component.name for i in range(top.occurrences.count)], list(bodies.CONTAINERS)
        )
        count, found = self.fusion.component_tree(top)
        self.assertEqual(count, 0)
        got_top, results = bodies.check_tree(found, count, False)
        self.assertTrue(got_top.ok, got_top.detail)
        self.assertTrue(all(r.ok for r in results), [(r.name, r.detail) for r in results if not r.ok])
        self.assertEqual(len(found), 5)

    def test_placement_transform(self):
        self.run_build()
        self.frame.assert_called_once_with(None)
        frame = placement_frame((1.0, 2.0, 3.0), (0.0, 0.0, 1.0))
        self.run_build(placement=frame)
        self.frame.assert_called_once_with(frame)
        self.design.rootComponent.occurrences.addNewComponent.assert_called_once_with("matrix")

    def test_invalid_params_rejected_before_any_component(self):
        with self.assertRaises(ValueError):
            self.run_build(shaft="608ZZ", bore_clearance=0.6)
        self.design.rootComponent.occurrences.addNewComponent.assert_not_called()

    def test_non_parametric_rejected(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in (f"{_PKG}.clutch_build", f"{_PKG}.clutch_checks", f"{_PKG}.fusion", f"{_PKG}.clutch_parts"):
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            build = importlib.import_module(f"{_PKG}.clutch_build")
            design = mock.MagicMock()
            design.designType = "direct"
            with self.assertRaises(fusion.BuildError) as cm:
                build.build_clutch(design, Params(), FakeLog())
            self.assertIn("parametric", str(cm.exception))
            design.rootComponent.occurrences.addNewComponent.assert_not_called()

    def test_not_solid_rejected(self):
        with self.assertRaises(Exception) as cm:
            self.run_build(solid=False)
        self.assertIn("not a solid", str(cm.exception))

    def test_stray_body_fails_count(self):
        with self.assertRaises(Exception) as cm:
            self.run_build(stray_part="Ring")
        self.assertEqual(str(cm.exception), "expected 10 bodies, found 11")


if __name__ == "__main__":
    unittest.main()
