"""Test setup: builds an installed-style copy of the add-in and imports its geometry package through it.

The glue imports `from ...lib import addinkit`, but the add-in folder in git has no `lib/addinkit` (deploy.py adds it).
ADDINS is a temporary directory holding the add-in folder with the shared kit copied in, like an installed add-in.
The geometry package `lib/gen` is imported there as `<add-in folder>.lib.gen`, then aliased as `gen` in `sys.modules`
(the same module objects) so a test can write `from gen.params import default_params`. Nothing puts `lib/` on
`sys.path`.
"""

from __future__ import annotations

import atexit
import importlib
import os
import pkgutil
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ADDIN = os.path.normpath(os.path.join(_HERE, os.pardir))
_KIT = os.path.normpath(os.path.join(_ADDIN, os.pardir, os.pardir, "lib", "addinkit"))


def _build_addins() -> str:
    root = tempfile.mkdtemp(prefix="addin-tests-")
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    dest = os.path.join(root, os.path.basename(_ADDIN))
    shutil.copytree(_ADDIN, dest, ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc", "README.md"))
    shutil.copytree(_KIT, os.path.join(dest, "lib", "addinkit"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return root


def _alias_gen(addins: str) -> None:
    sys.path.insert(0, addins)
    name = f"{os.path.basename(_ADDIN)}.lib.gen"
    pkg = importlib.import_module(name)
    sys.modules["gen"] = pkg
    for info in pkgutil.iter_modules(pkg.__path__):
        sys.modules[f"gen.{info.name}"] = importlib.import_module(f"{name}.{info.name}")


ADDINS = _build_addins()
_alias_gen(ADDINS)
