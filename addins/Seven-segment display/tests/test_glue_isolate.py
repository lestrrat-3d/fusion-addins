"""The parts built in a design of their own and imported (isolate.py), against a mocked Fusion application: the order of
calls, the imported component's name, the fallback when nothing could be made, and the container check's view of an
imported part."""

import importlib
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS
_PKG = "Seven-segment display.commands.sevensegment"


class Comp:
    """A component with bodies and occurrences."""

    def __init__(self, name="", bodies=()):
        self.name = name
        self._bodies = list(bodies)
        self.occ = []

    @property
    def bRepBodies(self):
        return mock.MagicMock(count=len(self._bodies), item=lambda i: self._bodies[i])

    @property
    def occurrences(self):
        return mock.MagicMock(count=len(self.occ), item=lambda i: self.occ[i])


class Body:
    def __init__(self, name=""):
        self.name = name


class Occ:
    def __init__(self, component):
        self.component = component


class IsolateTest(unittest.TestCase):
    def setUp(self):
        self.adsk = mock.MagicMock()
        fakes = {"adsk": self.adsk, "adsk.core": self.adsk.core, "adsk.fusion": self.adsk.fusion}
        for patch in (mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path)):
            patch.start()
            self.addCleanup(patch.stop)
        names = [f"{_PKG}.isolate", f"{_PKG}.build", f"{_PKG}.fusion", f"{_PKG}.parts", f"{_PKG}.checks"]
        for n in names:
            sys.modules.pop(n, None)
        self.isolate = importlib.import_module(f"{_PKG}.isolate")
        self.build = importlib.import_module(f"{_PKG}.build")
        self.fusion = importlib.import_module(f"{_PKG}.fusion")
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in names])
        self.calls = []
        self.home = mock.MagicMock(name="home")
        self.scratch = mock.MagicMock(name="scratch")
        self.app = mock.MagicMock()
        self.app.activeDocument = self.home
        self.app.documents.add.side_effect = lambda *_: self.calls.append("new design") or self.scratch
        self.scratch.close.side_effect = lambda *_: self.calls.append("close")
        self.home.activate.side_effect = lambda: self.calls.append("activate home")
        self.adsk.core.Application.get.return_value = self.app
        self.design = mock.MagicMock()
        self.design.exportManager.execute.side_effect = lambda *_: self.calls.append("export") or True
        self.adsk.fusion.Design.cast.return_value = self.design
        self.comp = Comp("Frame")
        self.imported = Comp("Untitled", [Body("Top Plate")])

        def import_to(opts, target):
            self.calls.append("import")
            self.comp.occ.append(Occ(self.imported))
            return [object()]

        self.app.importManager.importToTarget2.side_effect = import_to
        self.ctx = self.build.BuildContext(comp=self.comp, top=self.comp, p=None, dm=None, log=mock.MagicMock())

    def builder(self, ctx, name):
        self.calls.append("build " + name)
        self.seen = ctx
        return Body(name)

    def export(self, names=("Top Plate",), build=None):
        return self.isolate.export_all(self.ctx, build or self.builder, names, "/tmp/x")

    def test_each_part_is_built_exported_and_closed_with_the_main_design_active_again(self):
        archives = self.export(("Top Plate", "Hub"))
        self.assertEqual(self.calls, ["new design", "build Top Plate", "export", "close", "activate home",
                                      "new design", "build Hub", "export", "close", "activate home"])
        self.assertEqual(archives, {"Top Plate": "/tmp/x/0.f3d", "Hub": "/tmp/x/1.f3d"})

    def test_a_part_is_built_in_the_new_designs_root_at_the_identity_with_nothing_shared(self):
        self.ctx.shared["x"] = 1
        self.export()
        self.assertIs(self.seen.comp, self.design.rootComponent)
        self.assertEqual(self.seen.placement_axes, self.isolate._IDENTITY)
        self.assertEqual(self.seen.shared, {})
        self.assertEqual(self.seen.part, "Top Plate")
        self.assertEqual(self.ctx.shared, {"x": 1})

    def test_a_failed_export_leaves_the_part_out_logs_it_and_returns_to_the_main_design(self):
        self.design.exportManager.execute.side_effect = lambda *_: False
        self.assertEqual(self.export(), {})
        self.assertEqual(self.calls[-2:], ["close", "activate home"])
        self.assertEqual(self.ctx.log.write.call_args.args[0], "isolate")

    def test_no_new_design_leaves_the_part_out_and_returns_to_the_main_design(self):
        self.app.documents.add.side_effect = RuntimeError("no")
        self.assertEqual(self.export(), {})
        self.assertEqual(self.calls, ["activate home"])

    def test_a_build_error_closes_the_scratch_design_and_is_not_swallowed(self):
        def failing(ctx, name):
            raise self.fusion.BuildError("boom")

        with self.assertRaises(self.fusion.BuildError):
            self.export(build=failing)
        self.assertEqual(self.calls, ["new design", "close", "activate home"])

    def test_import_names_the_component_and_returns_its_body(self):
        body = self.isolate.import_part(self.ctx, "Top Plate", "/tmp/x/0.f3d")
        self.assertEqual(self.calls, ["import"])
        self.assertEqual(body.name, "Top Plate")
        self.assertEqual(self.imported.name, "Top Plate part")

    def test_an_import_that_adds_nothing_is_unavailable(self):
        self.app.importManager.importToTarget2.side_effect = lambda *_: [object()]
        with self.assertRaises(self.isolate.Unavailable):
            self.isolate.import_part(self.ctx, "Top Plate", "/tmp/x/0.f3d")

    def test_a_failed_import_is_built_in_the_main_design_and_logged(self):
        with mock.patch.object(self.build.isolate, "import_part", side_effect=self.isolate.Unavailable("no")), \
                mock.patch.object(self.build.parts, "build_part", return_value="body") as part:
            self.assertEqual(self.build._build(self.ctx, "Top Plate", {"Top Plate": "p"}), "body")
        part.assert_called_once()
        self.assertEqual(self.ctx.log.write.call_args.args[0], "isolate")

    def test_a_part_without_an_archive_is_built_in_the_main_design(self):
        with mock.patch.object(self.build.isolate, "import_part") as imp, \
                mock.patch.object(self.build.parts, "build_part", return_value="body"):
            self.assertEqual(self.build._build(self.ctx, "Top Plate", {}), "body")
        imp.assert_not_called()

    def test_the_archives_are_made_before_the_build_and_the_design_is_taken_again(self):
        from gen.params import default_params

        old = mock.MagicMock(name="old design")
        old.designType = self.adsk.fusion.DesignTypes.ParametricDesignType
        fresh = mock.MagicMock(name="fresh design")
        self.adsk.fusion.Design.cast.return_value = fresh
        order = []
        with mock.patch.object(self.build.config, "ISOLATE_PARTS", True), \
                mock.patch.object(self.build.isolate, "export_all",
                                  side_effect=lambda *a: order.append("export") or {"Top Plate": "p"}) as export, \
                mock.patch.object(self.build, "_build_all",
                                  side_effect=lambda *a: order.append(("build", a[0], a[5]))):
            self.build.build_display(old, default_params(), self.ctx.log)
        self.assertEqual(order, ["export", ("build", fresh, {"Top Plate": "p"})])
        names = export.call_args.args[2]
        self.assertIn("Top Plate", names)
        # The first body of each kind that is copied is built in its own design too; the copies are not.
        for first in ("Yellow Face A", "Black Body A", "Black Body B", "Pivot Block A -u", "Nut T1", "Bolt T1",
                      "Bolt G1"):
            self.assertIn(first, names)
        for copy in ("Yellow Face B", "Black Body C", "Pivot Block A +u", "Nut T2", "Bolt T2", "Bolt G2"):
            self.assertNotIn(copy, names)

    def test_nothing_is_exported_when_isolation_is_off(self):
        from gen.params import default_params

        old = mock.MagicMock()
        old.designType = self.adsk.fusion.DesignTypes.ParametricDesignType
        with mock.patch.object(self.build.config, "ISOLATE_PARTS", False), \
                mock.patch.object(self.build.isolate, "export_all") as export, \
                mock.patch.object(self.build, "_build_all") as build_all:
            self.build.build_display(old, default_params(), self.ctx.log)
        export.assert_not_called()
        self.assertIs(build_all.call_args.args[0], old)

    def test_an_imported_first_body_becomes_the_prototype_its_copies_use(self):
        ctx = self.build.BuildContext(comp=self.comp, top=self.comp, p=None, dm=None, log=mock.MagicMock())
        from gen.params import default_params
        from gen.validate import derive

        ctx.dm = derive(default_params())
        with mock.patch.object(self.build.isolate, "import_part", return_value="imported body"):
            self.assertEqual(self.build._build(ctx, "Nut T1", {"Nut T1": "p"}), "imported body")
            self.assertEqual(self.build._build(ctx, "Bolt G1", {"Bolt G1": "p"}), "imported body")
        self.assertEqual(sorted(ctx.shared), ["bolt 10", "nut"])
        self.assertEqual(ctx.shared["nut"][0], "imported body")
        self.assertEqual(ctx.shared["nut"][1], ctx.dm.sites[0].nut_axes())
        self.assertEqual(ctx.shared["bolt 10"][1], ctx.dm.sites[4].bolt_axes())

    def test_the_kinds_that_are_copied_have_one_first_body_each(self):
        from gen.params import default_params
        from gen.validate import derive

        parts = importlib.import_module(f"{_PKG}.parts")
        ctx = self.build.BuildContext(comp=None, top=None, p=None, dm=derive(default_params()), log=mock.MagicMock())
        firsts = parts.first_of_each_kind(ctx)
        self.assertEqual(sorted(firsts), sorted(["Yellow Face A", "Black Body A", "Black Body B", "Pivot Block A -u",
                                                 "Nut T1", "Bolt T1", "Bolt G1"]))
        keys = {parts.shared_info(ctx, n)[0] for n in firsts}
        self.assertEqual(len(keys), 7)
        self.assertIsNone(parts.shared_info(ctx, "Top Plate"))
        self.assertEqual(parts.shared_info(ctx, "Bolt T2")[0], parts.shared_info(ctx, "Bolt T1")[0])
        self.assertNotEqual(parts.shared_info(ctx, "Bolt G1")[0], parts.shared_info(ctx, "Bolt T1")[0])

    def test_only_the_listed_parts_are_isolated(self):
        self.assertTrue(self.isolate.wants("Top Plate"))
        self.assertTrue(self.isolate.wants("Slider C"))
        self.assertFalse(self.isolate.wants("Yellow Face A"))
        self.assertFalse(self.isolate.wants("Bolt T1"))
        self.assertFalse(self.isolate.wants("Pivot Block A -u"))

    def test_an_imported_part_counts_as_a_body_of_its_container(self):
        container = Comp("Frame")
        container.occ.append(Occ(Comp("Top Plate part (1)", [Body("Top Plate")])))
        container.occ.append(Occ(Comp("Sub", [Body("x")])))
        top = Comp("Display")
        top.occ.append(Occ(container))
        bodies_directly, found = self.fusion.component_tree(top)
        self.assertEqual(bodies_directly, 0)
        self.assertEqual(found[0].bodies, ("Top Plate",))
        self.assertEqual([k.name for k in found[0].children], ["Sub"])
        self.assertEqual(self.fusion.count_bodies(top), 2)


if __name__ == "__main__":
    unittest.main()
