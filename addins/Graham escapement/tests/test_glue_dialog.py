import importlib
import math
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401
from gen.params import default_params

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
            return importlib.import_module("Graham escapement.commands.escapement.dialog")

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
        dialog.advance_placement_focus(inputs, _Sel("pendulum_length", 1))
        dialog.advance_placement_focus(inputs, None)
        self.assertFalse(any(s.hasFocus for s in sels.values()))

    def test_placement_ids_are_in_dialog_order(self):
        dialog = self._dialog()
        self.assertEqual(dialog.PLACEMENT_IDS, (dialog.ORIGIN_ID, dialog.AXIS_ID))


class _Input:
    def __init__(self, input_id, value=0.0, valid=True):
        self.id = input_id
        self.value = value
        self.isValidExpression = valid


class ReadParamsTest(unittest.TestCase):
    """read_params turns the value inputs back into Params and validates them, with adsk mocked."""

    def _dialog(self):
        adsk = mock.MagicMock()
        adsk.core.ValueCommandInput.cast = lambda x: x
        adsk.core.SelectionCommandInput.cast = lambda x: None
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            return importlib.import_module("Graham escapement.commands.escapement.dialog")

    def _inputs(self, **overrides):
        from gen.inputs import INPUT_SPECS

        items = {}
        for spec in INPUT_SPECS:
            # Fusion hands back centimeters for lengths and radians for angles.
            if spec.kind == "length":
                value = spec.default / 10.0
            elif spec.kind == "angle":
                value = math.radians(spec.default)
            else:
                value = spec.default
            items[spec.id] = _Input(spec.id, overrides.get(spec.id, value))
        return types.SimpleNamespace(itemById=lambda i: items.get(i)), items

    def test_defaults_give_default_params(self):
        dialog = self._dialog()
        inputs, _ = self._inputs()
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual(p, default_params())

    def test_invalid_value_gives_message(self):
        dialog = self._dialog()
        inputs, items = self._inputs(pendulum_length=10.0)
        p, err = dialog.read_params(inputs)
        self.assertIsNone(p)
        self.assertEqual(err, "PendulumLength 100 is outside its range [120, 250]")
        items["amplitude"].isValidExpression = False
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "Amplitude: invalid value")

    def test_input_order(self):
        from gen.inputs import INPUT_SPECS

        self.assertEqual([s.id for s in INPUT_SPECS][0], "pendulum_length")


if __name__ == "__main__":
    unittest.main()
