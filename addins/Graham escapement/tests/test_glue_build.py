"""Runs the build order against a mocked Fusion: placement, naming, containers and the body-count rule.

The part builders are replaced by fakes that return one body in the current container's component, so this file
checks the orchestration only."""

import dataclasses
import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import bodies, containers
from gen.params import default_params, placement_frame

_ADDINS = _support.ADDINS
_PKG = "Graham escapement.commands.escapement"


class FakeBody:
    def __init__(self, world, comp, part=""):
        self.comp = comp
        self.part = part
        self.name = ""
        self.isSolid = True
        self.moved = 0
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
        p = dataclasses.replace(default_params(), **changes)
        adsk = mock.MagicMock()
        world = World()

        def builder(part):
            def build(ctx):
                world.calls.append(("build", part, ctx.comp))
                if part == stray_part:
                    FakeBody(world, ctx.comp, part)  # a leftover tool body
                body = FakeBody(world, ctx.comp, part)
                body.isSolid = solid
                return body

            return build

        fake_parts = types.ModuleType(f"{_PKG}.parts")
        for part in bodies.PARTS:
            setattr(fake_parts, f"build_{part}", builder(part))
        fakes = {
            "adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion, f"{_PKG}.parts": fake_parts,
        }
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in (f"{_PKG}.build", f"{_PKG}.checks", f"{_PKG}.fusion"):
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            build = importlib.import_module(f"{_PKG}.build")
            design, top = make_design(adsk, world)
            self.top, self.fusion, self.adsk, self.world = top, fusion, adsk, world

            def copy_body(ctx, body, what):
                world.calls.append(("copy", what))
                return FakeBody(world, ctx.comp, ctx.part)

            def move(ctx, body, pose, what):
                if not pose.is_identity():
                    world.calls.append(("move", what))
                    body.moved += 1

            with mock.patch.object(fusion, "copy_body", copy_body), mock.patch.object(fusion, "move", move), \
                    mock.patch.object(fusion, "frame_matrix", return_value="matrix") as frame, \
                    mock.patch.object(build.checks, "run_all") as run_all:
                self.frame = frame
                self.design = design
                build.build_escapement(design, p, FakeLog())
            self.ctx = run_all.call_args.args[0]
            self.seconds = run_all.call_args.args[2]
            return world, run_all.call_args.args[1]

    def test_default_build_names_and_count(self):
        world, built = self.run_build()
        self.assertEqual([name for _, name, _ in built], list(bodies.BODY_NAMES))
        self.assertEqual(world.alive.__len__(), 36)
        self.assertEqual(sorted(b.name for b in world.alive), sorted(bodies.BODY_NAMES))
        self.assertTrue(all(b.isSolid for b in world.alive))
        copies = [c for c in world.calls if c[0] == "copy"]
        self.assertEqual(len(copies), 6 + 3 + 3 + 1 + 1)

    def test_collar_kinds_are_copied_once(self):
        world, built = self.run_build()
        by_name = {name: body for _, name, body in built}
        for part in ("arbor_collar", "end_collar"):
            first, last = bodies.PART_BODIES[part]
            self.assertEqual(world.calls.count(("copy", f"{part} copy")), 1, part)
            self.assertEqual((by_name[first].part, by_name[last].part), (part, part))
            self.assertEqual(by_name[first].moved, 1)
            self.assertEqual(by_name[last].moved, 1)
        collars = self.ctx.container_comps[("Collars",)]
        self.assertEqual(sorted(b.name for b in world.alive if b.comp is collars), sorted(bodies.COLLAR_NAMES))

    def test_parts_built_in_order_in_their_container(self):
        world, _ = self.run_build()
        builds = [c for c in world.calls if c[0] == "build"]
        self.assertEqual([c[1] for c in builds], list(bodies.PARTS))
        for _, part, comp in builds:
            self.assertIs(comp, self.ctx.container_comps[containers.container_of_part(part)])

    def test_containers(self):
        world, _ = self.run_build()
        top = self.top
        self.assertEqual(top.name, "Graham Escapement")
        self.assertEqual(top.bRepBodies.count, 0)
        self.assertEqual(
            [top.occurrences.item(i).component.name for i in range(top.occurrences.count)], list(containers.TOP_LEVEL)
        )
        self.assertEqual(len(self.ctx.container_comps), 20)
        for path, comp in self.ctx.container_comps.items():
            self.assertEqual(comp.name, path[-1])
        want = containers.expected_bodies()
        by_body = {b.name: self.ctx.container_comps and b.comp for b in world.alive}
        for path, names in want.items():
            for name in names:
                self.assertIs(by_body[name], self.ctx.container_comps[path])
        count, found = self.fusion.component_tree(top)
        self.assertEqual(count, 0)
        got_top, results = containers.check_tree(found, count)
        self.assertTrue(got_top.ok, got_top.detail)
        self.assertTrue(all(r.ok for r in results), [(r.path, r.detail) for r in results if not r.ok])
        self.assertEqual(len(found), 20)

    def test_placement_transform(self):
        self.run_build()
        self.frame.assert_called_once_with(None)
        frame = placement_frame((1.0, 2.0, 3.0), (0.0, 0.0, 1.0))
        self.run_build(placement=frame)
        self.frame.assert_called_once_with(frame)
        self.design.rootComponent.occurrences.addNewComponent.assert_called_once_with("matrix")

    def test_non_parametric_rejected(self):
        p = default_params()
        adsk = mock.MagicMock()
        fake_parts = types.ModuleType(f"{_PKG}.parts")
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion, f"{_PKG}.parts": fake_parts}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in (f"{_PKG}.build", f"{_PKG}.checks", f"{_PKG}.fusion"):
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            build = importlib.import_module(f"{_PKG}.build")
            design = mock.MagicMock()
            design.designType = "direct"
            with self.assertRaises(fusion.BuildError) as cm:
                build.build_escapement(design, p, FakeLog())
            self.assertIn("parametric", str(cm.exception))
            design.rootComponent.occurrences.addNewComponent.assert_not_called()

    def test_not_solid_rejected(self):
        with self.assertRaises(Exception) as cm:
            self.run_build(solid=False)
        self.assertIn("not a solid", str(cm.exception))

    def test_stray_body_fails_count(self):
        with self.assertRaises(Exception) as cm:
            self.run_build(stray_part="front_plate")
        self.assertEqual(str(cm.exception), "expected 36 bodies, found 37")


if __name__ == "__main__":
    unittest.main()
