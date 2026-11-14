import importlib
import math
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen.inputs import INPUT_SPECS
from gen.params import Params, default_params

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


class _Item:
    def __init__(self, name):
        self.name = name


def _mock_adsk():
    adsk = mock.MagicMock()
    for cls in (
        "DropDownCommandInput",
        "IntegerSpinnerCommandInput",
        "ValueCommandInput",
        "BoolValueCommandInput",
        "SelectionCommandInput",
        "TextBoxCommandInput",
    ):
        getattr(adsk.core, cls).cast = lambda x: x
    return adsk


def _import(adsk, *names):
    fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
    with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
        return [importlib.import_module(f"Planetary gearbox.commands.gearbox.{n}") for n in names]


def _fake_inputs(shaft="605ZZ", planet="605ZZ", teeth=(13, 29, 71)):
    """A fake input for every INPUT_SPECS id at its default, with the bearing and tooth values overridden."""
    items = {}
    for spec in INPUT_SPECS:
        if spec.kind == "count":
            value = spec.default
        elif spec.kind == "length":
            value = spec.default / 10
        elif spec.kind == "angle":
            value = spec.default * math.pi / 180
        else:
            value = spec.default
        item = types.SimpleNamespace(id=spec.id, value=value, isValidExpression=True, isEnabled=True)
        if spec.kind == "choice":
            item.selectedItem = _Item(spec.default)
        items[spec.id] = item
    items["planet_bearing"].selectedItem = _Item(planet)
    items["shaft_bearing"].selectedItem = _Item(shaft)
    for name, v in zip(("sun_teeth", "planet_teeth", "ring_teeth"), teeth):
        items[name].value = v
    for placement in ("placement_origin", "placement_axis"):
        items[placement] = types.SimpleNamespace(id=placement, selectionCount=0)
    return items, types.SimpleNamespace(itemById=lambda i: items.get(i))


class KitDefaultsTest(unittest.TestCase):
    """A bearing selector change sets the kit-dependent inputs, with adsk mocked."""

    def setUp(self):
        (self.dialog,) = _import(_mock_adsk(), "dialog")

    def _teeth(self, items):
        return tuple(items[i].value for i in ("sun_teeth", "planet_teeth", "ring_teeth"))

    def test_shaft_selector_sets_the_kit_teeth(self):
        items, inputs = _fake_inputs(shaft="608ZZ", planet="605ZZ")
        self.dialog.apply_kit_defaults(inputs, items["shaft_bearing"])
        self.assertEqual(self._teeth(items), (14, 28, 70))

    def test_planet_selector_back_to_the_default_kit(self):
        items, inputs = _fake_inputs(shaft="605ZZ", planet="605ZZ", teeth=(14, 28, 70))
        self.dialog.apply_kit_defaults(inputs, items["planet_bearing"])
        self.assertEqual(self._teeth(items), (13, 29, 71))

    def test_other_input_and_none_change_nothing(self):
        items, inputs = _fake_inputs(shaft="608ZZ", planet="605ZZ")
        self.dialog.apply_kit_defaults(inputs, items["module"])
        self.dialog.apply_kit_defaults(inputs, None)
        self.assertEqual(self._teeth(items), (13, 29, 71))

    def test_selector_without_item_changes_nothing(self):
        items, inputs = _fake_inputs(shaft="608ZZ", planet="605ZZ")
        items["shaft_bearing"].selectedItem = None
        self.dialog.apply_kit_defaults(inputs, items["shaft_bearing"])
        self.assertEqual(self._teeth(items), (13, 29, 71))


class AddInputsTest(unittest.TestCase):
    def test_selectors_are_drop_downs_listing_the_catalog(self):
        adsk = _mock_adsk()
        (dialog,) = _import(adsk, "dialog")
        inputs = mock.MagicMock()
        dialog.add_inputs(inputs, "Build: x")
        calls = inputs.addDropDownCommandInput.call_args_list
        self.assertEqual([c.args[:2] for c in calls], [("planet_bearing", "Planet bearing"), ("shaft_bearing", "Shaft bearing")])
        self.assertTrue(all(c.args[2] is adsk.core.DropDownStyles.TextListDropDownStyle for c in calls))
        added = inputs.addDropDownCommandInput.return_value.listItems.add.call_args_list
        self.assertEqual([c.args for c in added], [("605ZZ", True, ""), ("608ZZ", False, "")] * 2)


class ReadParamsTest(unittest.TestCase):
    """read_params and the validate handler against fake inputs, with adsk mocked."""

    def setUp(self):
        self.dialog, self.entry = _import(_mock_adsk(), "dialog", "entry")

    def test_defaults_are_valid(self):
        _, inputs = _fake_inputs()
        p, messages = self.dialog.read_params(inputs)
        self.assertEqual(messages, [])
        self.assertIsInstance(p, Params)
        self.assertEqual((p.planet_bearing, p.shaft_bearing), ("605ZZ", "605ZZ"))
        self.assertAlmostEqual(p.module, default_params().module, places=9)
        args = types.SimpleNamespace(inputs=inputs, areInputsValid=None)
        self.entry.command_validate_input(args)
        self.assertIs(args.areInputsValid, True)

    def test_shaft_608_at_the_605_teeth_lists_the_sun_wall_message(self):
        _, inputs = _fake_inputs(shaft="608ZZ")
        p, messages = self.dialog.read_params(inputs)
        self.assertIsNone(p)
        self.assertTrue(messages[0].startswith("the 8.1 mm shaft bore leaves less than one module of wall"), messages)
        args = types.SimpleNamespace(inputs=inputs, areInputsValid=None)
        self.entry.command_validate_input(args)
        self.assertIs(args.areInputsValid, False)

    def test_invalid_expression_is_one_message(self):
        items, inputs = _fake_inputs()
        items["module"].isValidExpression = False
        p, messages = self.dialog.read_params(inputs)
        self.assertEqual((p, messages), (None, ["Module: invalid value"]))


if __name__ == "__main__":
    unittest.main()
