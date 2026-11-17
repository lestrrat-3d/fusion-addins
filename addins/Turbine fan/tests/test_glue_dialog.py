import dataclasses
import math
import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401
from gen.params import default_params

_ADDINS = _support.ADDINS
_DIALOG = "Turbine fan.commands.turbinefan.dialog"


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
            return importlib.import_module(_DIALOG)

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

    def test_last_selection_and_other_inputs_move_nothing(self):
        dialog = self._dialog()
        sels, inputs = self._inputs(dialog, (1, 1))
        dialog.advance_placement_focus(inputs, sels[dialog.AXIS_ID])
        dialog.advance_placement_focus(inputs, _Sel("hand", 1))
        dialog.advance_placement_focus(inputs, None)
        self.assertFalse(any(s.hasFocus for s in sels.values()))

    def test_placement_ids_are_in_dialog_order(self):
        dialog = self._dialog()
        self.assertEqual(dialog.PLACEMENT_IDS, (dialog.ORIGIN_ID, dialog.AXIS_ID))


class FlipDirectionTest(PlacementFocusTest):
    """The Flip direction check box reverses the placement axis, and +Z when no axis is selected."""

    def _placement(self, flip, axis):
        dialog = self._dialog()
        dialog.adsk.core.BoolValueCommandInput.cast = lambda x: x
        box = types.SimpleNamespace(value=flip)
        inputs = types.SimpleNamespace(itemById=lambda i: box if i == dialog.FLIP_ID else None)
        picked = {dialog.ORIGIN_ID: None, dialog.AXIS_ID: "axis" if axis is not None else None}
        with mock.patch.object(dialog, "_selected", lambda ins, i: picked[i]), \
                mock.patch.object(dialog, "axis_from_entity", lambda e: axis):
            return dialog.read_placement(inputs)

    def test_flip_off_keeps_the_axis(self):
        frame = self._placement(False, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(dialog_z(frame)[0], 1.0)

    def test_flip_on_reverses_the_axis(self):
        frame = self._placement(True, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(dialog_z(frame)[0], -1.0)

    def test_flip_with_no_axis_builds_towards_minus_z(self):
        self.assertAlmostEqual(dialog_z(self._placement(True, None))[2], -1.0)
        self.assertIsNone(self._placement(False, None))


def dialog_z(frame):
    """The Z direction of a placement frame (u x v)."""
    u, v = frame.u, frame.v
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


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
        adsk = mock.MagicMock()
        adsk.core.ValueCommandInput.cast = lambda x: x
        adsk.core.DropDownCommandInput.cast = lambda x: x
        adsk.core.SelectionCommandInput.cast = lambda x: None
        adsk.core.BoolValueCommandInput.cast = lambda x: x
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            return importlib.import_module(_DIALOG)

    def _inputs(self, **overrides):
        from gen.inputs import INPUT_SPECS

        items = {}
        for spec in INPUT_SPECS:
            v = overrides.get(spec.id, spec.default)
            if spec.kind == "choice":
                items[spec.id] = _Drop(spec.id, v)
            elif spec.kind == "bool":
                items[spec.id] = _Input(spec.id, bool(v))  # a check box
            elif spec.kind == "angle":
                items[spec.id] = _Input(spec.id, math.radians(v))  # Fusion hands back radians for angles
            else:
                items[spec.id] = _Input(spec.id, v / 10.0)  # and centimeters for lengths
        return types.SimpleNamespace(itemById=lambda i: items.get(i)), items

    def test_defaults_give_default_params(self):
        dialog = self._dialog()
        inputs, _ = self._inputs()
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual((p.shaft_diameter, p.flat_depth, p.bore_clearance, p.hand, p.mount, p.placement),
                         (5.0, 0.5, 0.05, 0, 0, None))
        self.assertAlmostEqual(p.blade_pitch, default_params().blade_pitch, places=8)

    def test_choices_and_pitch(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(shaft_diameter=8.0, flat_depth=0.75, blade_pitch=40.0, hand="Left hand")
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual((p.shaft_diameter, p.flat_depth, p.hand, p.mount, p.clutch), (8.0, 0.75, 1, 0, None))
        self.assertAlmostEqual(math.degrees(p.blade_pitch), 40.0, places=6)

    def test_clutch_mount_reads_the_clutch_inputs(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(mount="Clutch", clutch_shaft="608ZZ", clutch_freewheel="CounterClockwise",
                                 shaft_diameter=5.0, hand="Right hand")
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual((p.shaft_diameter, p.flat_depth, p.hand, p.mount), (8.0, 0.75, 1, 1))
        self.assertEqual((p.clutch.shaft, p.clutch.freewheel, p.clutch.adapter), ("608ZZ", "CounterClockwise", True))

    def test_bridging_box_reaches_the_fan_and_the_clutch_params(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(mount="Clutch", sacrificial_bridging=True)
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertTrue(p.sacrificial_bridging)
        self.assertTrue(p.clutch.sacrificial_bridging)
        inputs, _ = self._inputs(mount="Clutch")
        p, _ = dialog.read_params(inputs)
        self.assertFalse(p.sacrificial_bridging)
        self.assertFalse(p.clutch.sacrificial_bridging)
        # Shown in the shaft mount too, where it bridges the hub only: no clutch.
        inputs, _ = self._inputs(mount="Shaft", sacrificial_bridging=True)
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertIsNone(p.clutch)
        self.assertTrue(p.sacrificial_bridging)
        inputs_off, _ = self._inputs(mount="Shaft")
        off = dialog.read_params(inputs_off)[0]
        self.assertFalse(off.sacrificial_bridging)
        self.assertEqual(dataclasses.replace(p, sacrificial_bridging=False), off)

    def test_clutch_error_is_shown(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(mount="Clutch", clutch_bore_clearance=0.9)
        p, err = dialog.read_params(inputs)
        self.assertIsNone(p)
        self.assertTrue(err.startswith("clutch: BoreClearance"), err)

    def test_mount_choice_shows_the_inputs_it_uses(self):
        dialog = self._dialog()
        for mount, shaft_visible in (("Shaft", True), ("Clutch", False)):
            inputs, items = self._inputs(mount=mount)
            for item in items.values():
                item.isVisible = None
            dialog.update_mount_inputs(inputs)
            for i in ("shaft_diameter", "flat_depth", "bore_clearance", "hand"):
                self.assertEqual(items[i].isVisible, shaft_visible, (mount, i))
            for i in ("clutch_shaft", "clutch_freewheel", "clutch_bore_clearance"):
                self.assertEqual(items[i].isVisible, not shaft_visible, (mount, i))
            # Directive: the `Sacrificial bridging` box shows in both mounts, so the mount never changes it.
            for i in ("blade_pitch", "mount", "sacrificial_bridging"):
                self.assertIsNone(items[i].isVisible, (mount, i))

    def test_invalid_value_gives_message(self):
        dialog = self._dialog()
        inputs, items = self._inputs(shaft_diameter=13.0)  # r_b 6.55 is over 6.095, the limit at 192
        p, err = dialog.read_params(inputs)
        self.assertIsNone(p)
        self.assertEqual(err, "ShaftDiameter leaves less than a 1.6 mm wall to the blade sockets")
        items["blade_pitch"].isValidExpression = False
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "Blade pitch: invalid value")

    def test_pitch_out_of_range(self):
        dialog = self._dialog()
        inputs, _ = self._inputs(blade_pitch=45.0)
        self.assertEqual(dialog.read_params(inputs)[1], "BladePitch must lie from 10 to 40 degrees")

    def test_a_drop_down_without_an_item_is_rejected(self):
        dialog = self._dialog()
        inputs, items = self._inputs()
        items["mount"].selectedItem = None
        self.assertEqual(dialog.read_params(inputs)[1], "Mount must be ShaftMount or ClutchMount")


if __name__ == "__main__":
    unittest.main()
