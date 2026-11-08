"""The glue checks (point checks, run_all, container checks), run against mocked Fusion bodies."""

import dataclasses
import importlib
import os
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS


class FakeLog:
    enabled = True

    def __init__(self):
        self.records = []

    def write(self, event, fields):
        self.records.append((event, dict(fields)))


class FakeBody:
    def __init__(self, containment, inside_at=()):
        self.containment = containment
        self.inside_at = set(inside_at)

    def pointContainment(self, pt):
        return self.containment[1] if pt in self.inside_at else self.containment[0]


class PointChecksTest(unittest.TestCase):
    def test_point_checks(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            checks = importlib.import_module("Planetary gearbox.commands.gearbox.checks")
            fusion = importlib.import_module("Planetary gearbox.commands.gearbox.fusion")
            probes_mod = importlib.import_module("Planetary gearbox.lib.planetarygearboxgen.probes")
            outside = adsk.fusion.PointContainment.PointOutsidePointContainment
            inside = adsk.fusion.PointContainment.PointInsidePointContainment
            # point() converts mm to cm and calls Point3D.create; make that return the (x, y, z) tuple itself.
            adsk.core.Point3D.create.side_effect = lambda x, y, z: (x, y, z)
            bad = fusion.point(1.0, 0.0, 0.0)
            with mock.patch.dict(checks._CONTAINMENT, {outside: probes_mod.OUTSIDE, inside: probes_mod.INSIDE}):
                a = FakeBody((outside, inside), [bad])
                b = FakeBody((outside, inside))
                points = [
                    probes_mod.MeshPoint("a0", "A", (1.0, 0.0, 0.0)),
                    probes_mod.MeshPoint("a1", "A", (2.0, 0.0, 0.0)),
                    probes_mod.MeshPoint("b0", "B", (3.0, 0.0, 0.0)),
                ]
                ctx = mock.MagicMock()
                ctx.log = FakeLog()
                self.assertEqual(checks._point_checks(ctx, {"A": a, "B": b}, points, "fit"), (1, 1))
                records = ctx.log.records
                self.assertIn(("fit summary", {"target": "A", "points": 2, "inside": 1, "result": "FAIL"}), records)
                # A passing target logs nothing; only failures are written.
                self.assertEqual([r for r in records if r[0] == "fit summary" and r[1]["target"] == "B"], [])
                self.assertEqual([r for r in records if r[0] == "fit"],
                                 [("fit", {"target": "A", "detail": "a0", "result": "FAIL"})])
                with self.assertRaises(fusion.BuildError) as cm:
                    checks._point_checks(ctx, {"A": a}, points, "fit")
                self.assertTrue(str(cm.exception).startswith("fit check: no body named"))

    def run_all(self, stages):
        """Run checks.run_all over fake bodies for every instance; returns the log records."""
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            checks = importlib.import_module("Planetary gearbox.commands.gearbox.checks")
            layout = importlib.import_module("Planetary gearbox.lib.planetarygearboxgen.layout")
            expected = importlib.import_module("Planetary gearbox.lib.planetarygearboxgen.expected")
            params = importlib.import_module("Planetary gearbox.lib.planetarygearboxgen.params")
            dims = importlib.import_module("Planetary gearbox.lib.planetarygearboxgen.dims")
            cmod = importlib.import_module("Planetary gearbox.lib.planetarygearboxgen.containers")
            p = params.default_params()
            p = dataclasses.replace(p, stages=stages)
            d = dims.derive(p)
            outside = adsk.fusion.PointContainment.PointOutsidePointContainment
            body = mock.MagicMock()
            body.pointContainment.return_value = outside
            bodies = [(i.part, i.name, body) for i in layout.instances(p, d)]
            ctx = mock.MagicMock()
            ctx.log = FakeLog()
            ctx.fillet_radius = {}
            ctx.p, ctx.d = p, d
            ctx.box.name = "Planetary Gearbox"
            tree = (0, [cmod.Found(n, tuple(b), 0) for n, b in cmod.expected_bodies(p, d).items()])
            with mock.patch.object(checks.fusion, "body_report") as report, \
                    mock.patch.object(checks.fusion, "component_tree", return_value=tree):
                def fake(b):
                    return True, 0.0, (0.0,) * 6

                report.side_effect = fake
                checks.run_all(ctx, bodies, True, 1.0)
            self.assertEqual(expected.assembled_z(p, d).keys(), {n for _, n, _ in bodies})
            self.cnames = list(cmod.CONTAINER_NAMES)
            return ctx.log.records

    def test_run_all_counts(self):
        for stages, bodies, total in ((1, 31, 111), (2, 40, 142)):
            with self.subTest(stages=stages):
                records = self.run_all(stages)
                summary = [f for e, f in records if e == "summary"]
                self.assertEqual(len(summary), 1)
                self.assertEqual(summary[0]["bodies"], bodies)
                self.assertEqual(summary[0]["expected"], bodies)
                self.assertEqual(summary[0]["pass"] + summary[0]["fail"], total)
                # Only failures and the summary are logged: no line reports a PASS, and the summary comes last.
                self.assertEqual(records[-1][0], "summary")
                self.assertFalse([e for e, f in records if f.get("result") == "PASS"])

    def test_container_checks_misplaced(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            checks = importlib.import_module("Planetary gearbox.commands.gearbox.checks")
            params = importlib.import_module("Planetary gearbox.lib.planetarygearboxgen.params")
            dims = importlib.import_module("Planetary gearbox.lib.planetarygearboxgen.dims")
            cmod = importlib.import_module("Planetary gearbox.lib.planetarygearboxgen.containers")
            p = params.default_params()
            d = dims.derive(p)
            want = {k: list(v) for k, v in cmod.expected_bodies(p, d).items()}
            want["Nuts"].remove("Rear Nut 4")
            want["Bolts"].append("Rear Nut 4")
            tree = (0, [cmod.Found(n, tuple(b), 0) for n, b in want.items()])
            ctx = mock.MagicMock()
            ctx.p, ctx.d = p, d
            ctx.log = FakeLog()
            ctx.box.name = "Planetary Gearbox"
            with mock.patch.object(checks.fusion, "component_tree", return_value=tree):
                self.assertEqual(checks._container_checks(ctx), (8, 2))
            self.assertIn(
                ("container", {"name": "Bolts", "bodies": 9, "expected": 8, "detail": "extra Rear Nut 4",
                               "result": "FAIL"}),
                ctx.log.records,
            )
            self.assertIn(
                ("container", {"name": "Nuts", "bodies": 7, "expected": 8, "detail": "missing Rear Nut 4",
                               "result": "FAIL"}),
                ctx.log.records,
            )


if __name__ == "__main__":
    unittest.main()
