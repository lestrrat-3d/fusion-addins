"""Shared helpers for the test modules. Not a test module itself."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import shutil
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
FAKE_ID = "00000000-0000-4000-8000-000000000001"


def load_module(name: str, path: Path) -> types.ModuleType:
    """Load the Python file at path as a module called name."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # pyright: ignore[reportAttributeAccessIssue]
    return module


deploy = load_module("fusion_addins_deploy", ROOT / "deploy.py")
fp = deploy.load_fp()
KIT_DIR = deploy.KIT_DIR


def scratch_dir(test: unittest.TestCase) -> Path:
    """Return a fresh temp dir under ROOT/.tmp/tests, removed when the test ends."""
    base = ROOT / ".tmp" / "tests"
    base.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.TemporaryDirectory(dir=base)
    test.addCleanup(tmp.cleanup)
    return Path(tmp.name).resolve()


def write(path: Path, data: bytes | str) -> None:
    """Write data to path, creating parent directories. A str is encoded as UTF-8."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)


def make_fake_addin(parent: Path, name: str = "demo", *, extras: bool = True) -> Path:
    """Create a minimal add-in folder under parent and return its path."""
    addin_dir = parent / name
    manifest = {
        "autodeskProduct": "Fusion",
        "type": "addin",
        "id": FAKE_ID,
        "author": "test",
        "description": {"": ""},
        "version": "",
        "runOnStartup": False,
        "supportedOS": "windows|mac",
        "editEnabled": True,
    }
    write(addin_dir / f"{name}.manifest", json.dumps(manifest, indent=4) + "\n")
    write(addin_dir / f"{name}.py", "def run(context):\n    pass\n\n\ndef stop(context):\n    pass\n")
    write(addin_dir / "config.py", "DEBUG = False\n")
    write(addin_dir / "commands" / "__init__.py", "")
    write(addin_dir / "lib" / f"{name}gen" / "__init__.py", "SCALE = 1.0\n")
    if extras:
        write(addin_dir / "tests" / "test_geom.py", "")
        write(addin_dir / "README.md", "# demo\n")
        write(addin_dir / "docs" / "notes.md", "notes\n")
        write(addin_dir / ".tmp" / "run.log", "log\n")
        write(addin_dir / "__pycache__" / "x.cpython-312.pyc", b"\0")
        write(addin_dir / "lib" / f"{name}gen" / "__pycache__" / "y.pyc", b"\0")
    return addin_dir


def bundle_rels(addin_dir: Path) -> list[str]:
    """Return the bundle paths deploy.py builds for addin_dir, in hash order."""
    return list(deploy.bundle_sources(addin_dir))


def fake_checkout(test: unittest.TestCase) -> Path:
    """Copy the kit and LICENSE into scratch and point deploy at the copies for this test."""
    checkout = scratch_dir(test) / "checkout"
    kit = checkout / "lib" / "addinkit"
    for rel in fp.tree_files(str(KIT_DIR)):
        write(kit / rel, (KIT_DIR / rel).read_bytes())
    shutil.copyfile(ROOT / "LICENSE", checkout / "LICENSE")
    for name, value in (("KIT_DIR", kit), ("LICENSE_PATH", checkout / "LICENSE")):
        patcher = mock.patch.object(deploy, name, value)
        patcher.start()
        test.addCleanup(patcher.stop)
    return checkout
