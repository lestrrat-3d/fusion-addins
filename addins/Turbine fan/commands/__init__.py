from __future__ import annotations

from .turbinefan import entry as turbinefan


def start(build_label, digest, log):
    turbinefan.start(build_label, digest, log)


def stop():
    turbinefan.stop()
