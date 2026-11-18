import importlib
import math
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401
from gen.inputs import INPUT_SPECS
from gen.params import default_params

_ADDINS = _support.ADDINS


class _Input:
    def __init__(self, value):
        self.value = value
        self.isValidExpression = True


class ReadParamsTest(unittest.TestCase):
    """Reads the dialog's inputs back as Params, with adsk mocked."""

    def _dialog(self):
        adsk = mock.MagicMock()
        adsk.core.ValueCommandInput.cast = lambda x: x
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            name = "Plaque stand.commands.plaquestand.dialog"
            sys.modules.pop(name, None)
            module = importlib.import_module(name)
        self.addCleanup(lambda: sys.modules.pop("Plaque stand.commands.plaquestand.dialog", None))
        return module

    def _inputs(self, **overrides):
        items = {}
        for spec in INPUT_SPECS:
            v = overrides.get(spec.id, spec.default)
            # Fusion hands back radians for angles and centimeters for lengths.
            items[spec.id] = _Input(math.radians(v) if spec.kind == "angle" else v / 10.0)
        return items, types.SimpleNamespace(itemById=lambda i: items.get(i))

    def test_defaults_read_back_as_the_default_params(self):
        dialog = self._dialog()
        _, inputs = self._inputs()
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "")
        self.assertEqual(p, default_params())

    def test_input_order_and_labels(self):
        self.assertEqual([s.label for s in INPUT_SPECS],
                         ["Plaque width", "Plaque height", "Plaque thickness", "Recline", "Lip height",
                          "Slot clearance"])

    def test_an_invalid_value_gives_the_gallerys_message(self):
        dialog = self._dialog()
        items, inputs = self._inputs(plaque_width=100.0)
        p, err = dialog.read_params(inputs)
        self.assertIsNone(p)
        self.assertEqual(err, "PlaqueWidth must be from 150 to 400 mm, got 100")
        items["recline"].isValidExpression = False
        p, err = dialog.read_params(inputs)
        self.assertEqual(err, "Recline: invalid value")

    def test_the_recline_comes_back_in_degrees(self):
        dialog = self._dialog()
        _, inputs = self._inputs(recline=20.0)
        self.assertEqual(dialog.read_params(inputs)[0].recline, 20.0)

    def test_a_stand_that_would_tip_sideways_is_rejected(self):
        # The side tip angle rule cannot fail inside the limits (instructions.md); the dialog still reports a message.
        dialog = self._dialog()
        _, inputs = self._inputs(slot_clearance=1.6)
        self.assertIn("SlotClearance must be", dialog.read_params(inputs)[1])


if __name__ == "__main__":
    unittest.main()
