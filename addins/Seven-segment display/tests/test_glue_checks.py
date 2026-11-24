"""Runs the build checks against fake bodies: every check passes for the expected values and a wrong one logs a line."""

import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import bodies, expected
from gen.params import default_params
from gen.validate import derive

_ADDINS = _support.ADDINS
_PKG = "Seven-segment display.commands.sevensegment"


class FakeLog:
    enabled = True

    def __init__(self):
        self.records = []

    def write(self, event, fields):
        self.records.append((event, dict(fields)))


class ChecksTest(unittest.TestCase):
    def setUp(self):
        self.adsk = mock.MagicMock()
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

    def fake_body(self, name, bounds=None, solid=True):
        body = types.SimpleNamespace(name=name)
        body.report = (solid, 100.0, bounds if bounds is not None else expected.body_bounds(name, self.dm))
        return body

    def run_checks(self, tree_ok=True, **per_body):
        log = FakeLog()
        ctx = types.SimpleNamespace(log=log, p=self.p, dm=self.dm,
                                    top=types.SimpleNamespace(name="Seven-segment display"))
        built = [(n, self.fake_body(n, **per_body.get(n, {}))) for n in bodies.BODY_NAMES]
        want = bodies.expected_bodies()

        def make(node):
            return bodies.Found(node.name, tuple(want[node.key]), tuple(make(c) for c in node.children))

        found = [make(n) for n in bodies.TREE]
        if not tree_ok:
            found.pop()
        by_body = {id(b): b for _, b in built}
        with mock.patch.object(self.fusion, "body_report", lambda b: by_body[id(b)].report), \
                mock.patch.object(self.fusion, "component_tree", lambda top: (0, found)):
            self.checks.run_all(ctx, built, 1.5)
        return log.records

    def test_a_correct_build_logs_only_the_summary(self):
        records = self.run_checks()
        self.assertEqual([r[0] for r in records], ["summary"])
        summary = records[0][1]
        self.assertEqual((summary["bodies"], summary["expected"], summary["fail"]), (75, 75, 0))
        # 75 bodies x solid, 47 of them also bounds (32 frame and camshaft bodies, the hub and the 14 pivot blocks), plus
        # the top and the 38 containers.
        self.assertEqual(summary["pass"], 75 + 47 + 1 + 39)

    def test_wrong_bounds_and_not_solid(self):
        records = self.run_checks(**{
            "Shaft": {"bounds": (-3.8, -72.2, 25.7, 3.8, 49.0, 33.3)},
            "Cam A": {"solid": False},
        })
        events = [(r[0], r[1].get("name")) for r in records]
        self.assertIn(("bounds", "Shaft"), events)
        self.assertIn(("body", "Cam A"), events)
        self.assertEqual(records[-1][1]["fail"], 2)

    def test_a_body_within_tolerance_passes(self):
        box = list(expected.body_bounds("Shaft", self.dm))
        box[4] += 0.005
        records = self.run_checks(**{"Shaft": {"bounds": tuple(box)}})
        self.assertEqual([r[0] for r in records], ["summary"])

    def test_missing_container_is_reported(self):
        records = self.run_checks(tree_ok=False)
        names = [r[1].get("name") for r in records if r[0] == "container"]
        self.assertEqual(names[0], "Nuts")
        self.assertIn("containers", [r[0] for r in records])

    def test_disabled_log_skips_the_checks(self):
        log = FakeLog()
        log.enabled = False
        ctx = types.SimpleNamespace(log=log)
        self.checks.run_all(ctx, [], 0.0)
        self.assertEqual(log.records, [])


if __name__ == "__main__":
    unittest.main()
