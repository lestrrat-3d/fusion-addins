"""The command's execute handler and the custom event that runs the build after the command (entry.py), against a
mocked Fusion application."""

import importlib
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS
_PKG = "Seven-segment display.commands.sevensegment"


class EntryTest(unittest.TestCase):
    def setUp(self):
        self.adsk = mock.MagicMock()
        fakes = {"adsk": self.adsk, "adsk.core": self.adsk.core, "adsk.fusion": self.adsk.fusion}
        for patch in (mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path)):
            patch.start()
            self.addCleanup(patch.stop)
        names = [f"{_PKG}.entry", f"{_PKG}.build", f"{_PKG}.dialog"]
        for n in names:
            sys.modules.pop(n, None)
        self.entry = importlib.import_module(f"{_PKG}.entry")
        self.build = importlib.import_module(f"{_PKG}.build")
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in names])
        self.args = mock.MagicMock()
        self.log = mock.MagicMock()
        self.entry._log = self.log

    def test_execute_leaves_the_build_to_the_custom_event(self):
        with mock.patch.object(self.entry.config, "BUILD_AFTER_COMMAND", True), \
                mock.patch.object(self.entry.dialog, "read_params", return_value=("params", "")), \
                mock.patch.object(self.build, "build_display") as build:
            self.entry.command_execute(self.args)
        build.assert_not_called()
        self.assertEqual(self.entry._pending, "params")
        self.entry.app.fireCustomEvent.assert_called_once_with(self.entry._BUILD_EVENT_ID, "")

    def test_execute_builds_at_once_when_the_event_is_off(self):
        with mock.patch.object(self.entry.config, "BUILD_AFTER_COMMAND", False), \
                mock.patch.object(self.entry.dialog, "read_params", return_value=("params", "")), \
                mock.patch.object(self.build, "build_display") as build:
            self.entry.command_execute(self.args)
        build.assert_called_once()
        self.entry.app.fireCustomEvent.assert_not_called()

    def test_the_event_makes_the_archives_then_starts_the_build_command(self):
        self.entry._pending = "params"
        run = self.entry.ui.commandDefinitions.itemById.return_value
        run.execute.return_value = True
        with mock.patch.object(self.entry.config, "ISOLATE_PARTS", True), \
                mock.patch.object(self.build, "prepare_archives", return_value=({"A": "p"}, "/tmp/f")) as prepare:
            self.entry.build_requested(mock.MagicMock())
            self.entry.build_requested(mock.MagicMock())  # nothing is pending any more
        prepare.assert_called_once_with("params", self.log)
        self.assertEqual(self.entry._ready, ("params", {"A": "p"}, "/tmp/f"))
        run.execute.assert_called_once()
        self.assertIsNone(self.entry._pending)

    def test_without_isolation_the_command_builds_without_archives(self):
        self.entry._pending = "params"
        self.entry.ui.commandDefinitions.itemById.return_value.execute.return_value = True
        with mock.patch.object(self.entry.config, "ISOLATE_PARTS", False), \
                mock.patch.object(self.build, "prepare_archives") as prepare:
            self.entry.build_requested(mock.MagicMock())
        prepare.assert_not_called()
        self.assertEqual(self.entry._ready, ("params", None, ""))

    def test_the_build_command_builds_with_the_archives_and_removes_their_folder(self):
        self.entry._ready = ("params", {"A": "p"}, "/tmp/f")
        with mock.patch.object(self.build, "build_display") as build, \
                mock.patch.object(self.entry.shutil, "rmtree") as rm:
            self.entry.run_execute(self.args)
        build.assert_called_once()
        self.assertEqual(build.call_args.args[1:], ("params", self.log, {"A": "p"}))
        rm.assert_called_once_with("/tmp/f", ignore_errors=True)
        self.assertIsNone(self.entry._ready)

    def test_a_failed_build_command_is_logged_shown_and_marked_failed(self):
        self.entry._ready = ("params", None, "")
        with mock.patch.object(self.build, "build_display", side_effect=RuntimeError("boom")):
            self.entry.run_execute(self.args)
        self.assertTrue(self.args.executeFailed)
        self.assertEqual(self.log.write.call_args.args[0], "error")
        self.assertIn("boom", self.entry.ui.messageBox.call_args.args[0])

    def test_a_failure_while_making_the_archives_is_shown_and_starts_no_command(self):
        self.entry._pending = "params"
        run = self.entry.ui.commandDefinitions.itemById.return_value
        with mock.patch.object(self.entry.config, "ISOLATE_PARTS", True), \
                mock.patch.object(self.build, "prepare_archives", side_effect=RuntimeError("no designs")):
            self.entry.build_requested(mock.MagicMock())
        run.execute.assert_not_called()
        self.assertIsNone(self.entry._ready)
        self.assertIn("no designs", self.entry.ui.messageBox.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
