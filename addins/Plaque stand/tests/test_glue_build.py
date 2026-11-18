"""Runs the build order against a mocked Fusion: placement, naming, containers and the body-count rule.

The part builders are replaced by a fake that returns one body in the current container's component, so this file
checks the orchestration only."""

import dataclasses
import importlib
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import bodies
from gen.params import default_params

_ADDINS = _support.ADDINS
_PKG = "Plaque stand.commands.plaquestand"


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
        p = dataclasses.replace(default_params(), **changes)
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
            for name in (f"{_PKG}.build", f"{_PKG}.checks", f"{_PKG}.fusion", f"{_PKG}.parts"):
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            build = importlib.import_module(f"{_PKG}.build")
            design, top = make_design(adsk, world)
            self.top, self.fusion, self.world = top, fusion, world
            with mock.patch.object(build.parts, "build_part", build_part), \
                    mock.patch.object(fusion, "body_report", lambda b: (True, 100.0, ())), \
                    mock.patch.object(fusion, "frame_matrix", return_value="matrix") as frame, \
                    mock.patch.object(build.checks, "run_all") as run_all:
                self.frame = frame
                self.design = design
                build.build_stand(design, p, FakeLog())
            self.ctx = run_all.call_args.args[0]
            return world, run_all.call_args.args[1]

    def test_default_build_names_and_count(self):
        self.run_build()
        built = [c[1] for c in self.world.calls if c[0] == "build"]
        self.assertEqual(built, list(bodies.BODY_NAMES))
        self.assertEqual(len(self.world.alive), 8)
        self.assertEqual(sorted(b.name for b in self.world.alive), sorted(bodies.BODY_NAMES))
        self.assertTrue(all(b.isSolid for b in self.world.alive))

    def test_each_body_is_built_in_its_containers_component(self):
        self.run_build()
        comps = self.ctx.container_comps
        self.assertEqual(list(comps), list(bodies.CONTAINERS))
        for _, name, comp in [c for c in self.world.calls if c[0] == "build"]:
            self.assertIs(comp, comps[bodies.BODY_CONTAINER[name]], name)

    def test_the_top_component_is_named_and_sits_at_the_origin(self):
        self.run_build()
        self.assertEqual(self.top.name, "Plaque stand")
        self.frame.assert_called_once_with(None)  # the gallery has no placement input

    def test_invalid_params_rejected_before_any_component(self):
        with self.assertRaises(ValueError):
            self.run_build(plaque_width=100.0)
        self.design.rootComponent.occurrences.addNewComponent.assert_not_called()

    def test_non_parametric_rejected(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in (f"{_PKG}.build", f"{_PKG}.checks", f"{_PKG}.fusion", f"{_PKG}.parts"):
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            build = importlib.import_module(f"{_PKG}.build")
            design = mock.MagicMock()
            design.designType = "direct"
            with self.assertRaises(fusion.BuildError):
                build.build_stand(design, default_params(), FakeLog())
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in (f"{_PKG}.build", f"{_PKG}.fusion")])

    def test_not_solid_rejected(self):
        with self.assertRaises(Exception) as cm:
            self.run_build(solid=False)
        self.assertIn("not a solid", str(cm.exception))

    def test_stray_body_fails_count(self):
        with self.assertRaises(Exception) as cm:
            self.run_build(stray_part=bodies.RAIL)
        self.assertEqual(str(cm.exception), "expected 8 bodies, found 9")


if __name__ == "__main__":
    unittest.main()
