import importlib
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS
_MODULES = (
    "Seven-segment display.Seven-segment display",
    "Seven-segment display.commands.sevensegment.entry",
    "Seven-segment display.commands.sevensegment.dialog",
    "Seven-segment display.commands.sevensegment.fusion",
    "Seven-segment display.commands.sevensegment.parts",
    "Seven-segment display.commands.sevensegment.build",
    "Seven-segment display.commands.sevensegment.checks",
)


class GlueImportsTest(unittest.TestCase):
    """Imports the Fusion glue with adsk mocked out. Added modules leave sys.modules on cleanup."""

    def test_imports(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in _MODULES:
                with self.subTest(module=name):
                    importlib.import_module(name)


if __name__ == "__main__":
    unittest.main()
