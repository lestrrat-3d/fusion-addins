import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS


class _Sel:
    def __init__(self, input_id, count=0):
        self.id = input_id
        self.selectionCount = count
        self.hasFocus = False


class PlacementFocusTest(unittest.TestCase):
    """The placement selections hand the focus on, in dialog order, with adsk mocked."""

    def _dialog(self):
        adsk = mock.MagicMock()
        adsk.core.SelectionCommandInput.cast = lambda x: x
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            return importlib.import_module("Planetary gearbox.commands.gearbox.dialog")

    def _inputs(self, dialog, counts=(0, 0)):
        sels = {i: _Sel(i, c) for i, c in zip(dialog.PLACEMENT_IDS, counts)}
        return sels, types.SimpleNamespace(itemById=lambda i: sels.get(i))

    def test_origin_selected_moves_focus_to_axis(self):
        dialog = self._dialog()
        sels, inputs = self._inputs(dialog, (1, 0))
        dialog.advance_placement_focus(inputs, sels[dialog.ORIGIN_ID])
        self.assertTrue(sels[dialog.AXIS_ID].hasFocus)
        self.assertFalse(sels[dialog.ORIGIN_ID].hasFocus)

    def test_cleared_origin_keeps_focus(self):
        dialog = self._dialog()
        sels, inputs = self._inputs(dialog, (0, 0))
        dialog.advance_placement_focus(inputs, sels[dialog.ORIGIN_ID])
        self.assertFalse(sels[dialog.AXIS_ID].hasFocus)

    def test_last_selection_moves_nothing(self):
        dialog = self._dialog()
        sels, inputs = self._inputs(dialog, (1, 1))
        dialog.advance_placement_focus(inputs, sels[dialog.AXIS_ID])
        self.assertFalse(sels[dialog.ORIGIN_ID].hasFocus)
        self.assertFalse(sels[dialog.AXIS_ID].hasFocus)

    def test_other_input_moves_nothing(self):
        dialog = self._dialog()
        sels, inputs = self._inputs(dialog, (1, 1))
        dialog.advance_placement_focus(inputs, _Sel("module", 1))
        dialog.advance_placement_focus(inputs, None)
        self.assertFalse(any(s.hasFocus for s in sels.values()))

    def test_placement_ids_are_in_dialog_order(self):
        dialog = self._dialog()
        self.assertEqual(dialog.PLACEMENT_IDS, (dialog.ORIGIN_ID, dialog.AXIS_ID))


class _Input:
    def __init__(self, input_id, value=None):
        self.id = input_id
        self.value = value
        self.isEnabled = True


class EarInputsTest(unittest.TestCase):
    """The ear inputs follow the ears check box, with adsk mocked."""

    def _dialog(self):
        adsk = mock.MagicMock()
        adsk.core.BoolValueCommandInput.cast = lambda x: x
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            return importlib.import_module("Planetary gearbox.commands.gearbox.dialog")

    def _inputs(self, checked):
        items = {i: _Input(i) for i in ("ear_count", "ear_bore_diameter", "module")}
        items["ears"] = _Input("ears", checked)
        return items, types.SimpleNamespace(itemById=lambda i: items.get(i))

    def test_unchecked_box_disables_the_ear_inputs(self):
        dialog = self._dialog()
        items, inputs = self._inputs(False)
        dialog.sync_dependent_inputs(inputs)
        self.assertFalse(items["ear_count"].isEnabled)
        self.assertFalse(items["ear_bore_diameter"].isEnabled)
        self.assertTrue(items["module"].isEnabled)
        self.assertTrue(items["ears"].isEnabled)

    def test_checked_box_enables_them_again(self):
        dialog = self._dialog()
        items, inputs = self._inputs(False)
        dialog.sync_dependent_inputs(inputs)
        items["ears"].value = True
        dialog.sync_dependent_inputs(inputs)
        self.assertTrue(items["ear_count"].isEnabled)
        self.assertTrue(items["ear_bore_diameter"].isEnabled)


if __name__ == "__main__":
    unittest.main()
