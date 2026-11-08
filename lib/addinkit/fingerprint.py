"""Shipped-set rules and SHA-256 fingerprint for a Fusion add-in folder.

This module runs inside Fusion and under tools/addin.py, so it imports only the
standard library, has no relative imports, and never imports adsk.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping

SHIPPED_DIRS = ("commands", "lib")
OPTIONAL_FILES = ("LICENSE", "NOTICE", "AddInIcon.svg")


def required_files(name: str) -> tuple[str, str, str]:
    """Return the manifest, entry file and config file names of add-in `name`."""
    return (f"{name}.manifest", f"{name}.py", "config.py")


def is_excluded(relpath: str) -> bool:
    """Return True for hidden paths, __pycache__ paths, and *.pyc / *.log files."""
    parts = relpath.split("/")
    for part in parts:
        if part.startswith(".") or part == "__pycache__":
            return True
    return parts[-1].endswith((".pyc", ".log"))


def _sort_key(relpath: str) -> bytes:
    return relpath.encode("utf-8")


def tree_files(root: str, sub: str = "") -> list[str]:
    """List regular files under root/sub as sorted POSIX paths relative to root.

    Excluded paths are skipped. Raises ValueError on a symlinked file or directory.
    A missing root/sub yields an empty list.
    """
    top = os.path.join(root, sub) if sub else root
    if sub and os.path.islink(top):
        raise ValueError(f"symlink not allowed: {sub}")
    if not os.path.isdir(top):
        return []
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(top, topdown=True):
        reldir = os.path.relpath(dirpath, root)
        prefix = "" if reldir == "." else reldir.replace(os.sep, "/") + "/"
        keep = []
        for d in sorted(dirnames):
            rel = prefix + d
            if is_excluded(rel):
                continue
            if os.path.islink(os.path.join(dirpath, d)):
                raise ValueError(f"symlink not allowed: {rel}")
            keep.append(d)
        dirnames[:] = keep
        for f in filenames:
            rel = prefix + f
            if is_excluded(rel):
                continue
            if os.path.islink(os.path.join(dirpath, f)):
                raise ValueError(f"symlink not allowed: {rel}")
            found.append(rel)
    return sorted(found, key=_sort_key)


def shipped_files(root: str, name: str | None = None) -> list[str]:
    """Return the sorted shipped set of the add-in folder at root."""
    if name is None:
        name = os.path.basename(os.path.normpath(root))
    found: list[str] = []
    for rel in required_files(name) + OPTIONAL_FILES:
        path = os.path.join(root, rel)
        if os.path.islink(path):
            raise ValueError(f"symlink not allowed: {rel}")
        if os.path.isfile(path):
            found.append(rel)
    for d in SHIPPED_DIRS:
        found.extend(tree_files(root, d))
    return sorted(found, key=_sort_key)


def digest_map(sources: Mapping[str, str]) -> str:
    """Return the SHA-256 hex digest over files given as {POSIX relpath: filesystem path}."""
    h = hashlib.sha256()
    for rel in sorted(sources, key=_sort_key):
        with open(sources[rel], "rb") as fh:
            data = fh.read()
        h.update(rel.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0" + data)
    return h.hexdigest()


def digest_files(root: str, relpaths: list[str]) -> str:
    """Return the SHA-256 hex digest over relpaths read from root."""
    return digest_map({rel: os.path.join(root, *rel.split("/")) for rel in relpaths})


def compute(root: str, name: str | None = None) -> str:
    """Return the fingerprint of the add-in folder at root."""
    return digest_files(root, shipped_files(root, name))


def short(digest: str) -> str:
    """Return the first 12 characters of digest."""
    return digest[:12]
