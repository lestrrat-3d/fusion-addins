"""Test setup: puts lib/ on sys.path for the geometry tests and builds a deployable copy for the glue tests.

The glue imports `from ...lib import addinkit`, but the add-in folder in git has no `lib/addinkit` (deploy.py adds it).
ADDINS is a temporary directory holding `Planetary gearbox/` with the shared kit copied in, like an installed add-in.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ADDIN = os.path.normpath(os.path.join(_HERE, os.pardir))
_KIT = os.path.normpath(os.path.join(_ADDIN, os.pardir, os.pardir, "lib", "addinkit"))
_LIB = os.path.join(_ADDIN, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _build_addins() -> str:
    root = tempfile.mkdtemp(prefix="planetarygearbox-tests-")
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    dest = os.path.join(root, os.path.basename(_ADDIN))
    shutil.copytree(_ADDIN, dest, ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc", "README.md"))
    shutil.copytree(_KIT, os.path.join(dest, "lib", "addinkit"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return root


ADDINS = _build_addins()
