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
            return importlib.import_module("Crank Handle.commands.crankhandle.dialog")

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
        dialog.advance_placement_focus(inputs, _Sel("throw", 1))
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
        adsk.core.BoolValueCommandInput.cast = lambda x: x
        adsk.core.SelectionCommandInput.cast = lambda x: None
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            return importlib.import_module("Crank Handle.commands.crankhandle.dialog")

    def _inputs(self, **overrides):
        from gen.inputs import INPUT_SPECS

        items = {}
        for spec in INPUT_SPECS:
            # Fusion hands back centimeters for lengths.
            scale = 1.0 if spec.kind == "bool" else 10.0
            items[spec.id] = _Input(spec.id, overrides.get(spec.id, spec.default) / scale)
        return types.SimpleNamespace(itemById=lambda i: items.get(i)), items

    def test_defaults_give_default_params(self):
        dialog = self._dialog()
        inputs, _ = self._inputs()
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual(p, default_params())

    def test_bore_diameter_is_chosen_in_the_dialog(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(shaft_diameter=8.0, flat_depth=0.75)
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual((p.shaft_diameter, p.flat_depth), (8.0, 0.75))

    def test_invalid_value_gives_message(self):
        dialog = self._dialog()
        inputs, items = self._inputs(shaft_diameter=17.0)
        p, err = dialog.read_params(inputs)
        self.assertIsNone(p)
        self.assertEqual(err, "ShaftDiameter leaves less than a 1.6 mm wall in the 20 mm arm")
        items["throw"].isValidExpression = False
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "Throw: invalid value")

    def test_input_order_and_labels(self):
        from gen.inputs import INPUT_SPECS

        self.assertEqual([s.label for s in INPUT_SPECS], ["Shaft bore diameter", "Flat depth", "Bore clearance", "Throw", "Double flat", "Split pin", "Sacrificial bridging"])

    def test_split_pin_check_box(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(split_pin=1.0)
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertTrue(p.split_pin)


if __name__ == "__main__":
    unittest.main()
