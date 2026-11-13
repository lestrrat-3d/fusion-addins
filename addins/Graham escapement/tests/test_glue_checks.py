"""The glue checks (point checks, run_all, container checks), run against mocked Fusion bodies."""

import importlib
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS
_PKG = "Graham escapement.commands.escapement"


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


def load():
    adsk = mock.MagicMock()
    fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
    return adsk, fakes


class PointChecksTest(unittest.TestCase):
    def test_point_checks(self):
        adsk, fakes = load()
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            checks = importlib.import_module(f"{_PKG}.checks")
            fusion = importlib.import_module(f"{_PKG}.fusion")
            probes_mod = importlib.import_module("Graham escapement.lib.gen.probes")
            outside = adsk.fusion.PointContainment.PointOutsidePointContainment
            inside = adsk.fusion.PointContainment.PointInsidePointContainment
            adsk.core.Point3D.create.side_effect = lambda x, y, z: (x, y, z)
            bad = fusion.point(1.0, 0.0, 0.0)
            with mock.patch.dict(checks._CONTAINMENT, {outside: probes_mod.OUTSIDE, inside: probes_mod.INSIDE}):
                a = FakeBody((outside, inside), [bad])
                b = FakeBody((outside, inside))
                points = [
                    probes_mod.MeshPoint("fit a0", "A", (1.0, 0.0, 0.0)),
                    probes_mod.MeshPoint("fit a1", "A", (2.0, 0.0, 0.0)),
                    probes_mod.MeshPoint("fit b0", "B", (3.0, 0.0, 0.0)),
                ]
                ctx = mock.MagicMock()
                ctx.log = FakeLog()
                self.assertEqual(checks._point_checks(ctx, {"A": a, "B": b}, points, "fit"), (0, 1))
                self.assertEqual(
                    ctx.log.records,
                    [
                        ("fit summary", {"points": 3, "inside": 1, "result": "FAIL"}),
                        ("fit", {"detail": "A: fit a0", "result": "FAIL"}),
                    ],
                )
                ctx.log.records.clear()
                self.assertEqual(checks._point_checks(ctx, {"A": b, "B": b}, points, "fit"), (1, 0))
                self.assertEqual(ctx.log.records, [])
                with self.assertRaises(fusion.BuildError) as cm:
                    checks._point_checks(ctx, {"A": a}, points, "fit")
                self.assertTrue(str(cm.exception).startswith("fit check: no body named"))

    def test_collar_point_inside_target_logs_lines(self):
        adsk, fakes = load()
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            checks = importlib.import_module(f"{_PKG}.checks")
            probes_mod = importlib.import_module("Graham escapement.lib.gen.probes")
            inside = adsk.fusion.PointContainment.PointInsidePointContainment
            body = mock.MagicMock()
            body.pointContainment.return_value = inside
            points = [probes_mod.MeshPoint("collar crutch #0", "Crutch", (1.0, 0.0, 0.0))]
            ctx = mock.MagicMock()
            ctx.log = FakeLog()
            with mock.patch.dict(checks._CONTAINMENT, {inside: probes_mod.INSIDE}):
                self.assertEqual(checks._point_checks(ctx, {"Crutch": body}, points, "collar"), (0, 1))
            self.assertEqual(
                ctx.log.records,
                [
                    ("collar summary", {"points": 1, "inside": 1, "result": "FAIL"}),
                    ("collar", {"detail": "Crutch: collar crutch #0", "result": "FAIL"}),
                ],
            )
            self.assertEqual(checks._EVENTS[-2:], ("collar", "bore"))

    def test_fail_lines_are_capped(self):
        adsk, fakes = load()
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            checks = importlib.import_module(f"{_PKG}.checks")
            probes_mod = importlib.import_module("Graham escapement.lib.gen.probes")
            inside = adsk.fusion.PointContainment.PointInsidePointContainment
            body = mock.MagicMock()
            body.pointContainment.return_value = inside
            points = [probes_mod.MeshPoint(f"mesh p{i}", "A", (float(i), 0.0, 0.0)) for i in range(25)]
            ctx = mock.MagicMock()
            ctx.log = FakeLog()
            with mock.patch.dict(checks._CONTAINMENT, {inside: probes_mod.INSIDE}):
                self.assertEqual(checks._point_checks(ctx, {"A": body}, points, "mesh"), (0, 1))
            self.assertEqual(len([r for r in ctx.log.records if r[0] == "mesh"]), 10)
            self.assertEqual(ctx.log.records[0], ("mesh summary", {"points": 25, "inside": 25, "result": "FAIL"}))


def _run_all(adsk, body_for=None):
    checks = importlib.import_module(f"{_PKG}.checks")
    bodies_mod = importlib.import_module("Graham escapement.lib.gen.bodies")
    layout = importlib.import_module("Graham escapement.lib.gen.layout")
    motion = importlib.import_module("Graham escapement.lib.gen.motion")
    params = importlib.import_module("Graham escapement.lib.gen.params")
    cmod = importlib.import_module("Graham escapement.lib.gen.containers")
    expected = importlib.import_module("Graham escapement.lib.gen.expected")
    g = layout.layout(params.default_params())
    s = motion.state_at(g, g.params.phase)
    outside = adsk.fusion.PointContainment.PointOutsidePointContainment
    body = mock.MagicMock()
    body.pointContainment.return_value = outside
    bodies = [(bodies_mod.part_of(n), n, body) for n in bodies_mod.BODY_NAMES]
    ctx = mock.MagicMock()
    ctx.log = FakeLog()
    ctx.g, ctx.s = g, s
    ctx.top.name = "Graham Escapement"
    tree = (0, [cmod.Found(path, tuple(names), tuple(cmod.expected_children(path)))
                for path, names in cmod.expected_bodies().items()])
    with mock.patch.object(checks.fusion, "body_report", return_value=(True, 0.0, (0.0,) * 6)), \
            mock.patch.object(checks.fusion, "component_tree", return_value=tree):
        checks.run_all(ctx, bodies, 1.0)
    assert expected.assembled_z(g).keys() == {n for _, n, _ in bodies}
    return ctx.log.records


class RunAllTest(unittest.TestCase):
    def test_run_all_counts(self):
        adsk, fakes = load()
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            probes_mod = importlib.import_module("Graham escapement.lib.gen.probes")
            checks = importlib.import_module(f"{_PKG}.checks")
            outside = adsk.fusion.PointContainment.PointOutsidePointContainment
            with mock.patch.dict(checks._CONTAINMENT, {outside: probes_mod.OUTSIDE}):
                records = _run_all(adsk)
            summary = [f for e, f in records if e == "summary"]
            self.assertEqual(len(summary), 1)
            self.assertEqual(summary[0]["bodies"], 36)
            self.assertEqual(summary[0]["expected"], 36)
            # 3 checks per body, 6 point events, 1 top and 20 container results.
            self.assertEqual(summary[0]["pass"] + summary[0]["fail"], 3 * 36 + 6 + 21)
            self.assertEqual(records[-1][0], "summary")
            self.assertFalse([e for e, f in records if f.get("result") == "PASS"])

    def test_disabled_log_skips_everything(self):
        adsk, fakes = load()
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            checks = importlib.import_module(f"{_PKG}.checks")
            ctx = mock.MagicMock()
            ctx.log.enabled = False
            checks.run_all(ctx, [], 1.0)
            ctx.log.write.assert_not_called()


class ContainerChecksTest(unittest.TestCase):
    def test_nested_failure_lines(self):
        adsk, fakes = load()
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            checks = importlib.import_module(f"{_PKG}.checks")
            cmod = importlib.import_module("Graham escapement.lib.gen.containers")
            want = {k: list(v) for k, v in cmod.expected_bodies().items()}
            want[("Nuts",)].remove("Nut 4")
            want[("Drive", "Mainspring")].append("Nut 4")
            tree = (0, [cmod.Found(p, tuple(b), tuple(cmod.expected_children(p))) for p, b in want.items()])
            ctx = mock.MagicMock()
            ctx.log = FakeLog()
            ctx.top.name = "Graham Escapement"
            with mock.patch.object(checks.fusion, "component_tree", return_value=tree):
                self.assertEqual(checks._container_checks(ctx), (19, 2))
            self.assertIn(
                ("container", {"path": "Drive/Mainspring", "bodies": 2, "expected": 1, "detail": "extra Nut 4",
                               "result": "FAIL"}),
                ctx.log.records,
            )
            self.assertIn(
                ("container", {"path": "Nuts", "bodies": 3, "expected": 4, "detail": "missing Nut 4",
                               "result": "FAIL"}),
                ctx.log.records,
            )
            self.assertEqual([e for e, _ in ctx.log.records], ["container", "container"])

    def test_top_failure_line(self):
        adsk, fakes = load()
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            checks = importlib.import_module(f"{_PKG}.checks")
            cmod = importlib.import_module("Graham escapement.lib.gen.containers")
            tree = (2, [cmod.Found(p, tuple(b), tuple(cmod.expected_children(p)))
                        for p, b in cmod.expected_bodies().items()])
            ctx = mock.MagicMock()
            ctx.log = FakeLog()
            ctx.top.name = "Graham Escapement"
            with mock.patch.object(checks.fusion, "component_tree", return_value=tree):
                self.assertEqual(checks._container_checks(ctx), (20, 1))
            self.assertEqual(ctx.log.records[0][0], "containers")
            self.assertIn("2 bodies outside containers", ctx.log.records[0][1]["detail"])


if __name__ == "__main__":
    unittest.main()
