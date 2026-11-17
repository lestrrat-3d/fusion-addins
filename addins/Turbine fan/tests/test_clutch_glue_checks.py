"""Runs the build checks against fake bodies: every check passes for the expected values and a wrong one logs a line."""

import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen.clutch import bodies, expected, probes
from gen.clutch.params import Params
from gen.clutch.validate import derive

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
        for name in (f"{_PKG}.clutch_checks", f"{_PKG}.fusion", f"{_PKG}.clutch_build"):
            sys.modules.pop(name, None)
        self.fusion = importlib.import_module(f"{_PKG}.fusion")
        self.checks = importlib.import_module(f"{_PKG}.clutch_checks")
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in (f"{_PKG}.clutch_checks", f"{_PKG}.fusion")])
        self.p = Params()
        self.dm = derive(self.p)

    def fake_body(self, name, volume=None, bounds=None, flip=None):
        want = probes.part_probes(self.p, self.dm).get(name, [])
        answers = {pr.point: ("in" if pr.expect == probes.INSIDE else "out") for pr in want}
        if flip:
            answers[want[flip].point] = "out" if answers[want[flip].point] == "in" else "in"
        body = types.SimpleNamespace(name=name)
        body.pointContainment = lambda pt: answers[pt]
        vol = expected.body_volume(name, self.p, self.dm)
        body.report = (True, volume if volume is not None else (vol.value if vol else 100.0),
                       bounds if bounds is not None else expected.body_bounds(name, self.p, self.dm))
        return body

    def run_checks(self, tree_ok=True, **per_body):
        log = FakeLog()
        ctx = types.SimpleNamespace(log=log, p=self.p, dm=self.dm, top=types.SimpleNamespace(name="One-way clutch"))
        built = [(n, self.fake_body(n, **per_body.get(n, {}))) for n in bodies.body_names(self.p.adapter)]
        found = [bodies.Found(c, tuple(n), ()) for c, n in bodies.expected_bodies(self.p.adapter).items()]
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
        self.assertEqual((summary["bodies"], summary["expected"], summary["fail"]), (10, 10, 0))
        # 10 bodies x (volume, bounds, probes) plus the top and the five containers.
        self.assertEqual(summary["pass"], 30 + 6)

    def test_a_correct_build_with_the_adapter(self):
        self.p = Params(adapter=True)
        self.dm = derive(self.p)
        records = self.run_checks()
        self.assertEqual([r[0] for r in records], ["summary"])
        summary = records[0][1]
        self.assertEqual((summary["bodies"], summary["expected"], summary["fail"]), (17, 17, 0))
        self.assertEqual(summary["pass"], 17 * 3 + 7)  # the top and six containers

    def test_wrong_volume_bounds_and_probe(self):
        records = self.run_checks(**{
            bodies.RING: {"volume": 9000.0},
            bodies.COVER: {"bounds": (-16.7, -16.7, 14.5, 16.7, 16.7, 19.5)},
            bodies.HUB: {"flip": 2},
        })
        events = [(r[0], r[1].get("name")) for r in records]
        self.assertIn(("body", "Ring"), events)
        self.assertIn(("bounds", "Cover"), events)
        self.assertIn(("probes", "Hub"), events)
        probe = [r for r in records if r[0] == "probe"][0][1]
        self.assertIn("hub", probe["detail"])
        self.assertEqual(records[-1][1]["fail"], 3)

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
