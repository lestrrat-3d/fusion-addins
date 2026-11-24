import importlib
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
            return importlib.import_module("Seven-segment display.commands.sevensegment.dialog")

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
        dialog.advance_placement_focus(inputs, _Sel("digit", 1))
        dialog.advance_placement_focus(inputs, None)
        self.assertFalse(any(s.hasFocus for s in sels.values()))

    def test_placement_ids_are_in_dialog_order(self):
        dialog = self._dialog()
        self.assertEqual(dialog.PLACEMENT_IDS, (dialog.ORIGIN_ID, dialog.AXIS_ID))


class _Input:
    def __init__(self, input_id, value=0):
        self.id = input_id
        self.value = value


class ReadParamsTest(unittest.TestCase):
    """read_params turns the digit spinner back into Params and validates it, with adsk mocked."""

    def _dialog(self):
        adsk = mock.MagicMock()
        adsk.core.IntegerSpinnerCommandInput.cast = lambda x: x
        adsk.core.SelectionCommandInput.cast = lambda x: None
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            return importlib.import_module("Seven-segment display.commands.sevensegment.dialog")

    def _inputs(self, **overrides):
        from gen.inputs import INPUT_SPECS

        items = {spec.id: _Input(spec.id, overrides.get(spec.id, spec.default)) for spec in INPUT_SPECS}
        return types.SimpleNamespace(itemById=lambda i: items.get(i)), items

    def test_defaults_give_default_params(self):
        dialog = self._dialog()
        inputs, _ = self._inputs()
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual(p, default_params())
        self.assertEqual(p.digit, 2)

    def test_every_digit_is_read_back(self):
        dialog = self._dialog()
        for digit in range(10):
            inputs, _ = self._inputs(digit=digit)
            p, err = dialog.read_params(inputs)
            self.assertEqual((err, p.digit), ("", digit))

    def test_out_of_range_digit_gives_the_gallery_message(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(digit=10)
        p, err = dialog.read_params(inputs)
        self.assertIsNone(p)
        self.assertEqual(err, "sevensegment: digit 10 out of range 0..9")

    def test_input_order_and_labels(self):
        from gen.inputs import INPUT_SPECS

        self.assertEqual([s.label for s in INPUT_SPECS], ["Digit"])
        self.assertEqual([(s.minimum, s.maximum, s.default) for s in INPUT_SPECS], [(0, 9, 2)])

    def test_the_spinner_is_added_with_its_range(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            dialog = importlib.import_module("Seven-segment display.commands.sevensegment.dialog")
            inputs = mock.MagicMock()
            dialog.add_inputs(inputs, "Build: abc")
        inputs.addIntegerSpinnerCommandInput.assert_called_once_with("digit", "Digit", 0, 9, 1, 2)
        ids = [c.args[0] for c in inputs.addSelectionInput.call_args_list]
        self.assertEqual(ids, [dialog.ORIGIN_ID, dialog.AXIS_ID])
        texts = [c.args[2] for c in inputs.addTextBoxCommandInput.call_args_list]
        self.assertEqual(texts, ["", "Build: abc"])


if __name__ == "__main__":
    unittest.main()
