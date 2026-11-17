import importlib
import os
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS
_MODULES = (
    "Turbine fan.Turbine fan",
    "Turbine fan.commands.turbinefan.entry",
    "Turbine fan.commands.turbinefan.dialog",
    "Turbine fan.commands.turbinefan.fusion",
    "Turbine fan.commands.turbinefan.parts",
    "Turbine fan.commands.turbinefan.build",
    "Turbine fan.commands.turbinefan.checks",
    "Turbine fan.commands.turbinefan.clutch_parts",
    "Turbine fan.commands.turbinefan.clutch_build",
    "Turbine fan.commands.turbinefan.clutch_checks",
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
