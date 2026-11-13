import importlib
import os
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS
_MODULES = (
    "Graham escapement.Graham escapement",
    "Graham escapement.commands.escapement.entry",
    "Graham escapement.commands.escapement.dialog",
    "Graham escapement.commands.escapement.fusion",
    "Graham escapement.commands.escapement.parts",
    "Graham escapement.commands.escapement.build",
    "Graham escapement.commands.escapement.checks",
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
