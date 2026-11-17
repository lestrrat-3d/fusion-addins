import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401
from gen.inputs import INPUT_SPECS
from gen.params import default_params

_ADDINS = _support.ADDINS
_DIALOG = "One-way clutch.commands.onewayclutch.dialog"


class _Sel:
    def __init__(self, input_id, count=0):
        self.id = input_id
        self.selectionCount = count
        self.hasFocus = False


def _load(**casts):
    adsk = mock.MagicMock()
    for name, fn in casts.items():
        getattr(adsk.core, name).cast = fn
    fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
    with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
        sys.modules.pop(_DIALOG, None)
        return importlib.import_module(_DIALOG)


class PlacementFocusTest(unittest.TestCase):
    """The placement selections hand the focus on, in dialog order, with adsk mocked."""

    def _inputs(self, dialog, counts=(0, 0)):
        sels = {i: _Sel(i, c) for i, c in zip(dialog.PLACEMENT_IDS, counts)}
        return sels, types.SimpleNamespace(itemById=lambda i: sels.get(i))

    def test_origin_selected_moves_focus_to_axis(self):
        dialog = _load(SelectionCommandInput=lambda x: x)
        sels, inputs = self._inputs(dialog, (1, 0))
        dialog.advance_placement_focus(inputs, sels[dialog.ORIGIN_ID])
        self.assertTrue(sels[dialog.AXIS_ID].hasFocus)
        self.assertFalse(sels[dialog.ORIGIN_ID].hasFocus)

    def test_cleared_origin_keeps_focus(self):
        dialog = _load(SelectionCommandInput=lambda x: x)
        sels, inputs = self._inputs(dialog, (0, 0))
        dialog.advance_placement_focus(inputs, sels[dialog.ORIGIN_ID])
        self.assertFalse(sels[dialog.AXIS_ID].hasFocus)

    def test_last_selection_and_other_inputs_move_nothing(self):
        dialog = _load(SelectionCommandInput=lambda x: x)
        sels, inputs = self._inputs(dialog, (1, 1))
        dialog.advance_placement_focus(inputs, sels[dialog.AXIS_ID])
        dialog.advance_placement_focus(inputs, _Sel("bore_clearance", 1))
        dialog.advance_placement_focus(inputs, None)
        self.assertFalse(any(s.hasFocus for s in sels.values()))

    def test_placement_ids_are_in_dialog_order(self):
        dialog = _load(SelectionCommandInput=lambda x: x)
        self.assertEqual(dialog.PLACEMENT_IDS, (dialog.ORIGIN_ID, dialog.AXIS_ID))


class _Input:
    def __init__(self, input_id, value=0.0, valid=True):
        self.id = input_id
        self.value = value
        self.isValidExpression = valid


class _Drop:
    def __init__(self, input_id, name):
        self.id = input_id
        self.selectedItem = types.SimpleNamespace(name=name) if name is not None else None


class ReadParamsTest(unittest.TestCase):
    """read_params turns the inputs back into Params and validates them, with adsk mocked."""

    def _dialog(self):
        return _load(ValueCommandInput=lambda x: x, BoolValueCommandInput=lambda x: x,
                     DropDownCommandInput=lambda x: x, SelectionCommandInput=lambda x: None)

    def _inputs(self, **overrides):
        items = {}
        for spec in INPUT_SPECS:
            value = overrides.get(spec.id, spec.default)
            if spec.kind == "choice":
                items[spec.id] = _Drop(spec.id, value)
            else:
                # Fusion hands back centimeters for lengths.
                scale = 1.0 if spec.kind == "bool" else 10.0
                items[spec.id] = _Input(spec.id, value / scale)
        return types.SimpleNamespace(itemById=lambda i: items.get(i)), items

    def test_defaults_give_default_params(self):
        dialog = self._dialog()
        inputs, _ = self._inputs()
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual(p, default_params())

    def test_drop_downs_choose_the_preset_and_the_direction(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(shaft="608ZZ-gearbox", freewheel="CounterClockwise")
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual((p.shaft, p.freewheel), ("608ZZ-gearbox", "CounterClockwise"))

    def test_adapter_check_box(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(adapter=1.0)
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertTrue(p.adapter)

    def test_invalid_value_gives_message(self):
        dialog = self._dialog()
        inputs, items = self._inputs(shaft="608ZZ", bore_clearance=0.6)
        p, err = dialog.read_params(inputs)
        self.assertIsNone(p)
        self.assertEqual(err, "BoreClearance must be finite, from 0.05 to 0.5 mm")
        items["bore_clearance"].isValidExpression = False
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "Bore clearance: invalid value")

    def test_empty_drop_down_is_an_unknown_preset(self):
        dialog = self._dialog()
        inputs, items = self._inputs()
        items["shaft"] = _Drop("shaft", None)
        p, err = dialog.read_params(inputs)
        self.assertIsNone(p)
        self.assertIn("unknown shaft preset", err)

    def test_input_order_and_labels(self):
        self.assertEqual([s.label for s in INPUT_SPECS],
                         ["Shaft", "Freewheel", "Bore clearance", "Adapter ring", "Sacrificial bridging"])

    def test_sacrificial_bridging_check_box(self):
        dialog = self._dialog()
        inputs, _ = self._inputs()
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertFalse(p.sacrificial_bridging)
        inputs, _ = self._inputs(sacrificial_bridging=1.0)
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertTrue(p.sacrificial_bridging)


if __name__ == "__main__":
    unittest.main()
