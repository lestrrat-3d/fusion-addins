"""Runs the build checks against fake bodies: every check passes for the expected values and a wrong one logs a line."""

import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import bodies, expected, probes
from gen.constants import CLUTCH_MOUNT
from gen.params import default_params
from gen.validate import derive

import dataclasses

_ADDINS = _support.ADDINS
_PKG = "Turbine fan.commands.turbinefan"


class FakeLog:
    enabled = True

    def __init__(self):
        self.records = []

    def write(self, event, fields):
        self.records.append((event, dict(fields)))


class ChecksTest(unittest.TestCase):
    def setUp(self):
        self.adsk = mock.MagicMock()
        pc = self.adsk.fusion.PointContainment
        pc.PointInsidePointContainment, pc.PointOutsidePointContainment, pc.PointOnPointContainment = "in", "out", "on"
        fakes = {"adsk": self.adsk, "adsk.core": self.adsk.core, "adsk.fusion": self.adsk.fusion}
        patch = mock.patch.dict(sys.modules, fakes)
        patch.start()
        self.addCleanup(patch.stop)
        path = mock.patch.object(sys, "path", [_ADDINS] + sys.path)
        path.start()
        self.addCleanup(path.stop)
        for name in (f"{_PKG}.checks", f"{_PKG}.fusion", f"{_PKG}.build"):
            sys.modules.pop(name, None)
        self.fusion = importlib.import_module(f"{_PKG}.fusion")
        self.checks = importlib.import_module(f"{_PKG}.checks")
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in (f"{_PKG}.checks", f"{_PKG}.fusion")])
        self.p = default_params()
        self.dm = derive(self.p)

    def fake_body(self, name, volume=None, bounds=None, flip=None):
        want = probes.part_probes(self.p, self.dm).get(name, [])
        answers = {pr.point: ("in" if pr.expect == probes.INSIDE else "out") for pr in want}
        if flip is not None:
            answers[want[flip].point] = "out" if answers[want[flip].point] == "in" else "in"
        body = types.SimpleNamespace(name=name)
        body.pointContainment = lambda pt: answers[pt]
        vol = expected.body_volume(name, self.p, self.dm)
        body.report = (True, volume if volume is not None else (vol.value if vol else 100.0),
                       bounds if bounds is not None else expected.body_bounds(name, self.p, self.dm))
        return body

    def run_checks(self, tree_ok=True, **per_body):
        log = FakeLog()
        ctx = types.SimpleNamespace(log=log, p=self.p, dm=self.dm, top=types.SimpleNamespace(name="Turbine fan"))
        built = [(n, self.fake_body(n, **per_body.get(n, {}))) for n in bodies.body_names(self.p.mount)]
        found = [bodies.Found(c, tuple(n), ()) for c, n in bodies.expected_bodies(self.p.mount).items()]
        if not tree_ok:
            found.pop()
        by_body = {id(b): b for _, b in built}
        with mock.patch.object(self.fusion, "body_report", lambda b: by_body[id(b)].report), \
                mock.patch.object(self.fusion, "point", lambda x, y, z: (x, y, z)), \
                mock.patch.object(self.fusion, "component_tree", lambda top: (0, found)):
            self.checks.run_all(ctx, built, 1.5)
        return log.records

    def test_a_correct_build_logs_only_the_summary(self):
        records = self.run_checks()
        self.assertEqual([r[0] for r in records], ["summary"])
        summary = records[0][1]
        self.assertEqual((summary["bodies"], summary["expected"], summary["fail"]), (12, 12, 0))
        # 12 bodies x (volume, bounds, probes) plus the top and the four containers.
        self.assertEqual(summary["pass"], 36 + 5)

    def test_a_correct_clutch_build(self):
        self.p = dataclasses.replace(self.p, mount=CLUTCH_MOUNT)
        self.dm = derive(self.p)
        summary = self.run_checks()[-1][1]
        self.assertEqual((summary["bodies"], summary["expected"], summary["fail"], summary["pass"]), (14, 14, 0, 42 + 5))

    def test_wrong_volume_bounds_and_probe(self):
        records = self.run_checks(**{
            "Blade 2": {"volume": 1500.0},
            "Hub": {"bounds": (-14.0, -14.0, 0.0, 14.0, 14.0, 21.0), "flip": 1},
            "Blade Bolt 1": {"bounds": (0.0, 0.0, 0.0, 1.0, 1.0, 1.0)},
        })
        events = [(r[0], r[1].get("name")) for r in records]
        self.assertIn(("body", "Blade 2"), events)
        self.assertIn(("bounds", "Hub"), events)
        self.assertIn(("probes", "Hub"), events)
        self.assertIn(("bounds", "Blade Bolt 1"), events)
        probe = [r for r in records if r[0] == "probe"][0][1]
        self.assertIn("bore", probe["detail"])
        self.assertEqual(records[-1][1]["fail"], 4)

    def test_a_blade_bound_within_the_spline_tolerance_passes(self):
        want = expected.body_bounds("Blade 1", self.p, self.dm)
        shifted = tuple(v + 0.2 for v in want)
        self.assertEqual(self.run_checks(**{"Blade 1": {"bounds": shifted}})[-1][1]["fail"], 0)
        off = tuple(v + 0.5 for v in want)  # the spline tolerance is 0.45 at the default 192 mm size
        self.assertEqual(self.run_checks(**{"Blade 1": {"bounds": off}})[-1][1]["fail"], 1)

    def test_a_hub_that_is_not_a_preset_skips_the_volume(self):
        self.p = dataclasses.replace(self.p, bore_clearance=0.35)
        self.dm = derive(self.p)
        self.assertEqual(self.run_checks()[-1][1]["fail"], 0)

    def test_missing_container_is_reported(self):
        records = self.run_checks(tree_ok=False)
        self.assertIn("container", [r[0] for r in records])
        self.assertEqual(records[-1][1]["fail"], 2)  # the top and the missing container

    def test_disabled_log_skips_the_checks(self):
        log = FakeLog()
        log.enabled = False
        ctx = types.SimpleNamespace(log=log)
        self.checks.run_all(ctx, [], 0.0)
        self.assertEqual(log.records, [])


if __name__ == "__main__":
    unittest.main()
