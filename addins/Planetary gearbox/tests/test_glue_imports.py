import importlib
import importlib.util
import os
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS
_MODULES = (
    "Planetary gearbox.Planetary gearbox",
    "Planetary gearbox.commands.gearbox.entry",
    "Planetary gearbox.commands.gearbox.dialog",
    "Planetary gearbox.commands.gearbox.fusion",
    "Planetary gearbox.commands.gearbox.parts",
    "Planetary gearbox.commands.gearbox.build",
    "Planetary gearbox.commands.gearbox.checks",
)


class GlueImportsTest(unittest.TestCase):
    """Imports the Fusion glue with adsk mocked out. Added modules leave sys.modules on cleanup."""

    def test_imports(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in _MODULES:
                with self.subTest(module=name):
                    if importlib.util.find_spec(name) is None:
                        self.skipTest(f"{name} not created yet")
                    importlib.import_module(name)


if __name__ == "__main__":
    unittest.main()
